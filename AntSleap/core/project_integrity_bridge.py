"""Bind live project saves to the SQLite integrity registry."""

from __future__ import annotations

import copy
import os
from collections.abc import Mapping

from .file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from .location_registry import register_location
from .project_integrity_registry import (
    LABEL_SNAPSHOT_SCHEMA_ID,
    REGISTRY_READY,
    canonical_snapshot_text,
    commit_project_data_version,
    register_project_baseline,
    registry_state,
    relocate_project_asset,
)
from .project_traceability import PROJECT_KIND_2D, new_project_data_version_id
from .training_preflight import sanitize_box, sanitize_polygon
from .training_truth import get_part_training_truth, resolve_part_training_trust


PROJECT_SCHEMA_SNAPSHOT_ID = "taxamask_2d_training_schema_v1"


def _project_root(project_manager):
    source = (
        getattr(project_manager, "current_project_path", "")
        or getattr(project_manager, "current_database_path", "")
    )
    return os.path.abspath(os.path.dirname(os.path.abspath(source)) or os.curdir)


def _managed_relative(root, path):
    root_abs = os.path.abspath(root)
    path_abs = os.path.abspath(os.fspath(path))
    try:
        if os.path.normcase(os.path.commonpath([root_abs, path_abs])) != os.path.normcase(
            root_abs
        ):
            return ""
    except ValueError:
        return ""
    relative = os.path.relpath(path_abs, root_abs).replace("\\", "/")
    if relative == ".." or relative.startswith("../"):
        return ""
    return relative


def _source_location(project_manager, image_path):
    relative = _managed_relative(_project_root(project_manager), image_path)
    if relative:
        return {
            "location_kind": "managed_relative",
            "path_base": "project_root",
            "relative_path": relative,
        }
    opaque_ref = register_location(
        image_path,
        entry_kind="file",
        database_path=getattr(
            project_manager, "location_registry_database_path", None
        ),
    )
    return {"location_kind": "opaque_ref", "opaque_ref": opaque_ref}


def _confirmed_label_snapshot(project_manager, image_path, image_uid):
    label_entry = project_manager.project_data.get("labels", {}).get(image_path, {})
    if not isinstance(label_entry, Mapping):
        label_entry = {}
    raw_parts = label_entry.get("parts", {})
    raw_boxes = label_entry.get("boxes", {})
    raw_trajectories = label_entry.get("trajectories", {})
    if not isinstance(raw_parts, Mapping):
        raw_parts = {}
    if not isinstance(raw_boxes, Mapping):
        raw_boxes = {}
    if not isinstance(raw_trajectories, Mapping):
        raw_trajectories = {}
    parts = {}
    boxes = {}
    review = {}
    legacy_count = 0
    for part_name in sorted(str(name) for name in raw_parts):
        decision = resolve_part_training_trust(label_entry, part_name)
        if decision.get("state") == "conflict":
            raise ValueError(f"training_truth_conflict:{image_uid}:{part_name}")
        if not decision.get("eligible"):
            continue
        polygon = sanitize_polygon(raw_parts.get(part_name))
        if len(polygon) < 3:
            continue
        parts[part_name] = polygon
        box = sanitize_box(raw_boxes.get(part_name))
        if box is not None:
            boxes[part_name] = box
        truth = get_part_training_truth(label_entry, part_name)
        if truth is None:
            legacy_count += 1
        review[part_name] = {
            "source": str(decision.get("source") or ""),
            "review_status": str(decision.get("review_status") or ""),
            "accepted_via": str(decision.get("accepted_via") or ""),
        }
    if not parts:
        return None, legacy_count
    trajectories = {
        part_name: copy.deepcopy(raw_trajectories[part_name])
        for part_name in parts
        if part_name in raw_trajectories
        and isinstance(raw_trajectories[part_name], (Mapping, list, tuple))
    }
    payload = {
        "schema_version": LABEL_SNAPSHOT_SCHEMA_ID,
        "image_uid": image_uid,
        "parts": parts,
        "boxes": boxes,
        "trajectories": trajectories,
        "review": review,
    }
    return canonical_snapshot_text(payload), legacy_count


def _schema_snapshot(project_manager):
    payload = {
        "schema_version": PROJECT_SCHEMA_SNAPSHOT_ID,
        "taxonomy": list(project_manager.project_data.get("taxonomy", []) or []),
        "locator_scope": list(
            project_manager.project_data.get("locator_scope", []) or []
        ),
        "project_template": str(
            project_manager.project_data.get("project_template") or ""
        ),
        "category_supercategory": str(
            project_manager.project_data.get("category_supercategory") or ""
        ),
        "taxon_label": str(project_manager.project_data.get("taxon_label") or ""),
    }
    return canonical_snapshot_text(payload)


def _schema_entry(project_manager):
    project_id = str(project_manager.project_data.get("project_id") or "")
    return {
        "owner_kind": "project",
        "owner_key": project_id,
        "role": "label_schema",
        "media_type": "application/json",
        "schema_id": PROJECT_SCHEMA_SNAPSHOT_ID,
        "snapshot_text": _schema_snapshot(project_manager),
    }


def _source_entry(project_manager, image_path, image_uid):
    return {
        "owner_kind": "image",
        "owner_key": image_uid,
        "role": "source_image",
        "media_type": "application/octet-stream",
        "expected": compute_fingerprint(image_path, FULL_FILE_ALGORITHM),
        "location": _source_location(project_manager, image_path),
    }


def _label_entry(project_manager, image_path, image_uid):
    snapshot_text, legacy_count = _confirmed_label_snapshot(
        project_manager, image_path, image_uid
    )
    if snapshot_text is None:
        return None, legacy_count
    return (
        {
            "owner_kind": "image",
            "owner_key": image_uid,
            "role": "human_confirmed_label",
            "media_type": "application/json",
            "schema_id": LABEL_SNAPSHOT_SCHEMA_ID,
            "snapshot_text": snapshot_text,
        },
        legacy_count,
    )


def build_2d_baseline_entries(
    project_manager, *, progress_callback=None, cancel_check=None
):
    entries = [_schema_entry(project_manager)]
    legacy_truth_count = 0
    records = list(project_manager.iter_image_records())
    total = len(records)
    for index, record in enumerate(records, start=1):
        if cancel_check is not None and cancel_check():
            raise RuntimeError("integrity_baseline_cancelled")
        image_path = record["image_path"]
        image_uid = record["image_uid"]
        entries.append(_source_entry(project_manager, image_path, image_uid))
        label, legacy_count = _label_entry(
            project_manager, image_path, image_uid
        )
        legacy_truth_count += legacy_count
        if label is not None:
            entries.append(label)
        if progress_callback is not None:
            progress_callback(index, total, image_path)
    return entries, legacy_truth_count


def register_2d_project_baseline(
    project_manager,
    *,
    legacy_truth_attestation=False,
    note="",
    progress_callback=None,
    cancel_check=None,
):
    if not project_manager.is_sqlite_project():
        raise ValueError("sqlite_project_required")
    entries, legacy_count = build_2d_baseline_entries(
        project_manager,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )
    new_version = new_project_data_version_id()
    from .sqlite_storage import connect_sqlite_database
    from .project_sqlite_writer import write_project_metadata

    connection = connect_sqlite_database(project_manager.current_database_path)
    try:
        with connection:
            snapshot = register_project_baseline(
                connection,
                project_kind=PROJECT_KIND_2D,
                project_id=project_manager.project_data["project_id"],
                data_version_id=new_version,
                entries=entries,
                baseline_metadata={
                    "legacy_truth_count": legacy_count,
                    "legacy_truth_attestation": bool(legacy_truth_attestation),
                    "note": str(note or "").strip(),
                },
            )
            write_project_metadata(
                connection,
                project_manager,
                project_data_version_id=new_version,
            )
    finally:
        connection.close()
    project_manager.project_data["project_data_version_id"] = new_version
    project_manager._pending_project_data_version_id = ""
    return snapshot


def _active_asset(connection, owner_kind, owner_key, role):
    return connection.execute(
        """
        SELECT a.asset_id, r.digest, r.size_bytes, r.hash_algorithm, r.entry_kind,
               l.location_kind, l.path_base, l.relative_path, l.opaque_ref
        FROM integrity_assets a
        JOIN integrity_asset_heads h ON h.asset_id = a.asset_id AND h.tombstoned = 0
        JOIN integrity_asset_revisions r ON r.revision_id = h.revision_id
        LEFT JOIN integrity_locations l ON l.asset_id = a.asset_id AND l.is_active = 1
        WHERE a.owner_kind = ? AND a.owner_key = ? AND a.role = ?
        """,
        (owner_kind, owner_key, role),
    ).fetchone()


def _tombstone_change(owner_kind, owner_key, role):
    return {
        "change_kind": "tombstone",
        "owner_kind": owner_kind,
        "owner_key": owner_key,
        "role": role,
        "media_type": "application/octet-stream",
    }


def commit_2d_project_integrity_changes(
    connection,
    project_manager,
    *,
    image_paths,
    deleted_image_paths,
    candidate_data_version_id=None,
):
    state = registry_state(connection)
    if state["status"] != REGISTRY_READY:
        return {
            "changed": False,
            "data_version_id": str(
                project_manager.project_data.get("project_data_version_id") or ""
            ),
            "registry_status": state["status"],
        }
    project_id = str(project_manager.project_data.get("project_id") or "")
    changes = [_schema_entry(project_manager)]
    for image_path in sorted(set(image_paths or [])):
        image_key = (
            project_manager._registered_image_key_for_path(image_path) or image_path
        )
        image_uid = project_manager.get_image_uid(image_key)
        current_source = _active_asset(
            connection, "image", image_uid, "source_image"
        )
        new_location = _source_location(project_manager, image_key)
        current_location = None
        if current_source is not None:
            current_location = {
                "location_kind": str(current_source[5] or ""),
                "path_base": str(current_source[6] or ""),
                "relative_path": str(current_source[7] or ""),
                "opaque_ref": str(current_source[8] or ""),
            }
        if current_source is None or any(
            str(current_location.get(key) or "") != str(new_location.get(key) or "")
            for key in ("location_kind", "path_base", "relative_path", "opaque_ref")
        ):
            source_change = _source_entry(
                project_manager, image_key, image_uid
            )
            source_change["runtime_path"] = os.path.abspath(image_key)
            changes.append(source_change)

        label_change, _legacy_count = _label_entry(
            project_manager, image_key, image_uid
        )
        current_label = _active_asset(
            connection, "image", image_uid, "human_confirmed_label"
        )
        if label_change is not None:
            changes.append(label_change)
        elif current_label is not None:
            changes.append(
                _tombstone_change(
                    "image", image_uid, "human_confirmed_label"
                )
            )

    uid_map = project_manager.project_data.get("image_uids", {})
    for deleted_path in sorted(set(deleted_image_paths or [])):
        image_uid = str(uid_map.get(deleted_path) or "").strip()
        if not image_uid:
            continue
        for role in ("source_image", "human_confirmed_label"):
            if _active_asset(connection, "image", image_uid, role) is not None:
                changes.append(_tombstone_change("image", image_uid, role))

    candidate = candidate_data_version_id or new_project_data_version_id()
    return commit_project_data_version(
        connection,
        project_id=project_id,
        parent_data_version_id=state["current_data_version_id"],
        new_data_version_id=candidate,
        changes=changes,
        reason="project_training_facts_changed",
    )


def relocate_2d_project_images(project_manager, remap_matches):
    """Verify unchanged image content before updating any project path."""

    from .project_integrity_registry import get_registry_version_snapshot
    from .sqlite_storage import connect_sqlite_database

    connection = connect_sqlite_database(project_manager.current_database_path)
    relocated = []
    rejected = []
    try:
        with connection:
            state = registry_state(connection)
            if state["status"] != REGISTRY_READY:
                raise ValueError("integrity_baseline_missing")
            snapshot = get_registry_version_snapshot(
                connection, state["current_data_version_id"]
            )
            source_assets = {
                item["owner_key"]: item
                for item in snapshot["files"]
                if item.get("owner_kind") == "image"
                and item.get("role") == "source_image"
            }
            for item in remap_matches or []:
                old_path = os.path.normpath(str(item.get("old_path") or ""))
                new_path = os.path.abspath(str(item.get("new_path") or ""))
                image_uid = str(project_manager.get_image_uid(old_path) or "")
                asset = source_assets.get(image_uid)
                if not old_path or not new_path or asset is None:
                    rejected.append(
                        {**dict(item), "reason": "registered_source_not_found"}
                    )
                    continue
                try:
                    result = relocate_project_asset(
                        connection,
                        project_id=project_manager.project_data["project_id"],
                        asset_id=asset["asset_id"],
                        location=_source_location(project_manager, new_path),
                        runtime_path=new_path,
                    )
                except Exception as exc:
                    rejected.append(
                        {
                            **dict(item),
                            "reason": getattr(exc, "code", str(exc)),
                        }
                    )
                    continue
                relocated.append({**dict(item), "operation": result})
    finally:
        connection.close()
    return {"relocated": relocated, "rejected": rejected}


__all__ = [
    "PROJECT_SCHEMA_SNAPSHOT_ID",
    "build_2d_baseline_entries",
    "commit_2d_project_integrity_changes",
    "register_2d_project_baseline",
    "relocate_2d_project_images",
]
