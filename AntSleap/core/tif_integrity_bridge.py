"""SQLite integrity bridge for TIF projects and reviewed label volumes."""

from __future__ import annotations

import copy
import os
from collections.abc import Mapping

from .file_integrity import (
    FULL_FILE_ALGORITHM,
    QUICK_FILE_ALGORITHM,
    TREE_ALGORITHM,
    compute_fingerprint,
)
from .location_registry import register_location
from .project_integrity_registry import (
    REGISTRY_READY,
    canonical_snapshot_text,
    commit_project_data_version,
    register_project_baseline,
    registry_state,
)
from .project_traceability import PROJECT_KIND_TIF, new_project_data_version_id


TIF_SCHEMA_SNAPSHOT_ID = "taxamask_tif_training_schema_v1"
LOCAL_AXIS_TRUTH_SNAPSHOT_ID = "taxamask_tif_local_axis_truth_v1"


def _strip_paths(value):
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            clean_key = str(key)
            if clean_key in {
                "path",
                "contours_path",
                "extraction_path",
                "output_dir",
                "run_dir",
                "source_model",
                "result_json",
                "project_json",
            }:
                continue
            if clean_key.endswith("_path") or clean_key.endswith("_dir"):
                continue
            if clean_key in {"created_at", "updated_at"}:
                continue
            result[clean_key] = _strip_paths(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_strip_paths(item) for item in value]
    return value


def _schema_snapshot(project_manager):
    specimens = []
    for specimen in project_manager.project_data.get("specimens", []) or []:
        if not isinstance(specimen, Mapping):
            continue
        specimen_payload = {
            "specimen_id": str(specimen.get("specimen_id") or ""),
            "review_status": str(specimen.get("review_status") or ""),
            "train_ready": bool(specimen.get("train_ready")),
            "material_map": _strip_paths(
                specimen.get("material_map_payload")
                or specimen.get("material_map_metadata")
                or {}
            ),
            "parts": [],
        }
        for part in specimen.get("parts", []) or []:
            if not isinstance(part, Mapping):
                continue
            specimen_payload["parts"].append(
                {
                    "part_id": str(part.get("part_id") or ""),
                    "training": _strip_paths(part.get("training") or {}),
                    "reslices": [
                        _strip_paths(reslice)
                        for reslice in (
                            (part.get("metadata") or {}).get(
                                "local_axis_reslices", []
                            )
                            if isinstance(part.get("metadata"), Mapping)
                            else []
                        )
                        if isinstance(reslice, Mapping)
                    ],
                }
            )
        specimens.append(specimen_payload)
    payload = {
        "schema_version": TIF_SCHEMA_SNAPSHOT_ID,
        "label_schemas": _strip_paths(
            project_manager.project_data.get("label_schemas", []) or []
        ),
        "specimens": specimens,
    }
    return canonical_snapshot_text(payload)


def _schema_entry(project_manager):
    return {
        "owner_kind": "project",
        "owner_key": str(project_manager.project_data.get("project_id") or ""),
        "role": "label_schema",
        "media_type": "application/json",
        "schema_id": TIF_SCHEMA_SNAPSHOT_ID,
        "snapshot_text": _schema_snapshot(project_manager),
    }


def _local_axis_truth_entries(project_manager):
    for specimen in project_manager.project_data.get("specimens", []) or []:
        if not isinstance(specimen, Mapping):
            continue
        specimen_id = str(specimen.get("specimen_id") or "").strip()
        for part in specimen.get("parts", []) or []:
            if not isinstance(part, Mapping):
                continue
            part_id = str(part.get("part_id") or "").strip()
            metadata = part.get("metadata") if isinstance(part.get("metadata"), Mapping) else {}
            for reslice in metadata.get("local_axis_reslices", []) or []:
                if not isinstance(reslice, Mapping):
                    continue
                training = reslice.get("training") if isinstance(reslice.get("training"), Mapping) else {}
                training_sample = reslice.get("training_sample") if isinstance(reslice.get("training_sample"), Mapping) else {}
                human_confirmed = bool(
                    training_sample.get(
                        "human_confirmed", training.get("human_confirmed")
                    )
                )
                usable = bool(
                    training_sample.get(
                        "usable_for_training",
                        training.get("usable_for_training", True),
                    )
                )
                if not human_confirmed or not usable:
                    continue
                reslice_id = str(reslice.get("reslice_id") or "").strip()
                payload = {
                    "schema_version": LOCAL_AXIS_TRUTH_SNAPSHOT_ID,
                    "specimen_id": specimen_id,
                    "part_id": part_id,
                    "reslice_id": reslice_id,
                    "template_id": str(reslice.get("template_id") or ""),
                    "training_sample": _strip_paths(training_sample),
                    "training": _strip_paths(training),
                    "local_frame": _strip_paths(reslice.get("local_frame") or {}),
                    "roll_reference": _strip_paths(reslice.get("roll_reference") or {}),
                    "reslice_params": _strip_paths(reslice.get("reslice_params") or {}),
                }
                yield {
                    "owner_kind": "tif_asset",
                    "owner_key": f"reslice.{specimen_id}.{part_id}.{reslice_id}.local_axis_truth",
                    "role": "human_confirmed_label",
                    "media_type": "application/json",
                    "schema_id": LOCAL_AXIS_TRUTH_SNAPSHOT_ID,
                    "snapshot_text": canonical_snapshot_text(payload),
                }


def _iter_volume_assets(project_manager):
    for specimen in project_manager.project_data.get("specimens", []) or []:
        if not isinstance(specimen, Mapping):
            continue
        specimen_id = str(specimen.get("specimen_id") or "").strip()
        working = specimen.get("working_volume")
        if isinstance(working, Mapping) and working.get("path"):
            yield {
                "owner_key": f"specimen.{specimen_id}.working",
                "role": "source_volume",
                "path": working.get("path"),
                "record": working,
            }
        labels = specimen.get("labels") or {}
        manual = labels.get("manual_truth") if isinstance(labels, Mapping) else None
        if isinstance(manual, Mapping) and manual.get("path"):
            yield {
                "owner_key": f"specimen.{specimen_id}.manual_truth",
                "role": "manual_truth",
                "path": manual.get("path"),
                "record": manual,
            }
        for part in specimen.get("parts", []) or []:
            if not isinstance(part, Mapping):
                continue
            part_id = str(part.get("part_id") or "").strip()
            image = part.get("image")
            if isinstance(image, Mapping) and image.get("path"):
                yield {
                    "owner_key": f"part.{specimen_id}.{part_id}.image",
                    "role": "training_image",
                    "path": image.get("path"),
                    "record": image,
                }
            mask = part.get("mask")
            if isinstance(mask, Mapping) and mask.get("path"):
                yield {
                    "owner_key": f"part.{specimen_id}.{part_id}.mask",
                    "role": "training_context",
                    "path": mask.get("path"),
                    "record": mask,
                }
            part_labels = part.get("labels") or {}
            part_manual = (
                part_labels.get("manual_truth")
                if isinstance(part_labels, Mapping)
                else None
            )
            if isinstance(part_manual, Mapping) and part_manual.get("path"):
                yield {
                    "owner_key": f"part.{specimen_id}.{part_id}.manual_truth",
                    "role": "manual_truth",
                    "path": part_manual.get("path"),
                    "record": part_manual,
                }
            metadata = part.get("metadata") or {}
            reslices = (
                metadata.get("local_axis_reslices", [])
                if isinstance(metadata, Mapping)
                else []
            )
            for reslice in reslices or []:
                if not isinstance(reslice, Mapping):
                    continue
                reslice_id = str(reslice.get("reslice_id") or "").strip()
                if reslice.get("image_path"):
                    yield {
                        "owner_key": (
                            f"reslice.{specimen_id}.{part_id}.{reslice_id}.image"
                        ),
                        "role": "training_image",
                        "path": reslice.get("image_path"),
                        "record": reslice,
                    }
                if reslice.get("mask_path"):
                    reslice_training = (
                        reslice.get("training")
                        if isinstance(reslice.get("training"), Mapping)
                        else {}
                    )
                    confirmed_mask = bool(
                        reslice_training.get("human_confirmed")
                        and reslice_training.get("usable_for_training", True)
                    )
                    yield {
                        "owner_key": (
                            f"reslice.{specimen_id}.{part_id}.{reslice_id}.mask"
                        ),
                        "role": (
                            "manual_truth"
                            if confirmed_mask
                            else "training_context"
                        ),
                        "path": reslice.get("mask_path"),
                        "record": reslice,
                    }
                reslice_labels = reslice.get("labels") or {}
                reslice_manual = (
                    reslice_labels.get("manual_truth")
                    if isinstance(reslice_labels, Mapping)
                    else None
                )
                if isinstance(reslice_manual, Mapping) and reslice_manual.get("path"):
                    yield {
                        "owner_key": (
                            f"reslice.{specimen_id}.{part_id}.{reslice_id}.manual_truth"
                        ),
                        "role": "manual_truth",
                        "path": reslice_manual.get("path"),
                        "record": reslice_manual,
                    }


def _runtime_path(project_manager, value):
    path = project_manager.to_absolute(value)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return os.path.abspath(path)


def relocate_tif_project_asset(project_manager, issue, new_path):
    from .project_integrity_registry import (
        get_registry_version_snapshot,
        registry_state,
        relocate_project_asset,
    )
    from .sqlite_storage import connect_sqlite_database

    owner_key = str(issue.get("owner_key") or "")
    role = str(issue.get("role") or "")
    candidate = os.path.abspath(os.fspath(new_path))
    matched = next(
        (
            item
            for item in _iter_volume_assets(project_manager)
            if item["owner_key"] == owner_key and item["role"] == role
        ),
        None,
    )
    if matched is None:
        raise ValueError("registered_tif_asset_not_found")
    connection = connect_sqlite_database(project_manager.current_database_path)
    try:
        with connection:
            state = registry_state(connection)
            snapshot = get_registry_version_snapshot(
                connection, state["current_data_version_id"]
            )
            asset = next(
                (
                    item
                    for item in snapshot["files"]
                    if item.get("owner_kind") == "tif_asset"
                    and item.get("owner_key") == owner_key
                    and item.get("role") == role
                ),
                None,
            )
            if asset is None:
                raise ValueError("registered_tif_asset_not_found")
            result = relocate_project_asset(
                connection,
                project_id=project_manager.project_data["project_id"],
                asset_id=asset["asset_id"],
                location=_location(
                    project_manager,
                    candidate,
                    asset["entry_kind"],
                ),
                runtime_path=candidate,
            )
    finally:
        connection.close()

    record = matched["record"]
    relative = project_manager.to_relative(candidate)
    if owner_key.endswith(".image") and "image_path" in record:
        record["image_path"] = relative
    elif owner_key.endswith(".mask") and "mask_path" in record:
        record["mask_path"] = relative
    else:
        record["path"] = relative
    version_before = project_manager.project_data.get("project_data_version_id")
    project_manager.save_project()
    if project_manager.project_data.get("project_data_version_id") != version_before:
        raise RuntimeError("tif_relocation_must_not_create_data_version")
    return result


def _location(project_manager, runtime_path, entry_kind):
    root = os.path.abspath(project_manager.project_dir)
    path = os.path.abspath(runtime_path)
    try:
        inside = os.path.normcase(os.path.commonpath([root, path])) == os.path.normcase(
            root
        )
    except ValueError:
        inside = False
    if inside:
        relative = os.path.relpath(path, root).replace("\\", "/")
        return {
            "location_kind": "managed_relative",
            "path_base": "project_root",
            "relative_path": relative,
        }
    opaque_ref = register_location(
        path,
        entry_kind=entry_kind,
        database_path=getattr(
            project_manager, "location_registry_database_path", None
        ),
    )
    return {"location_kind": "opaque_ref", "opaque_ref": opaque_ref}


def _asset_entry(project_manager, item):
    runtime_path = _runtime_path(project_manager, item["path"])
    is_directory = os.path.isdir(runtime_path)
    if item["role"] == "source_volume" and not is_directory:
        algorithm = QUICK_FILE_ALGORITHM
    elif is_directory:
        algorithm = TREE_ALGORITHM
    else:
        algorithm = FULL_FILE_ALGORITHM
    expected = compute_fingerprint(runtime_path, algorithm)
    return {
        "owner_kind": "tif_asset",
        "owner_key": item["owner_key"],
        "role": item["role"],
        "media_type": "application/octet-stream",
        "expected": expected,
        "location": _location(
            project_manager, runtime_path, expected["entry_kind"]
        ),
        "runtime_path": runtime_path,
    }


def build_tif_baseline_entries(
    project_manager, *, progress_callback=None, cancel_check=None
):
    entries = [_schema_entry(project_manager), *_local_axis_truth_entries(project_manager)]
    assets = list(_iter_volume_assets(project_manager))
    legacy_truth_count = 0
    for index, item in enumerate(assets, start=1):
        if cancel_check is not None and cancel_check():
            raise RuntimeError("integrity_baseline_cancelled")
        if item["role"] == "manual_truth":
            review_audit = item["record"].get("review_audit")
            training = item["record"].get("training")
            explicitly_confirmed = isinstance(training, Mapping) and bool(
                training.get("human_confirmed")
            )
            if not isinstance(review_audit, Mapping) and not explicitly_confirmed:
                legacy_truth_count += 1
        entry = _asset_entry(project_manager, item)
        entry.pop("runtime_path", None)
        entries.append(entry)
        if progress_callback is not None:
            progress_callback(index, len(assets), item["owner_key"])
    return entries, legacy_truth_count


def register_tif_project_baseline(
    project_manager,
    *,
    legacy_truth_attestation=False,
    note="",
    progress_callback=None,
    cancel_check=None,
):
    if not project_manager.is_sqlite_project():
        raise ValueError("sqlite_project_required")
    entries, legacy_count = build_tif_baseline_entries(
        project_manager,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )
    new_version = new_project_data_version_id()
    from .sqlite_storage import connect_sqlite_database
    from .tif_sqlite_migration import _insert_project_row

    connection = connect_sqlite_database(project_manager.current_database_path)
    try:
        with connection:
            snapshot = register_project_baseline(
                connection,
                project_kind=PROJECT_KIND_TIF,
                project_id=project_manager.project_data["project_id"],
                data_version_id=new_version,
                entries=entries,
                baseline_metadata={
                    "legacy_truth_count": legacy_count,
                    "legacy_truth_attestation": bool(legacy_truth_attestation),
                    "note": str(note or "").strip(),
                },
            )
            payload = copy.deepcopy(project_manager.project_data)
            payload["project_data_version_id"] = new_version
            _insert_project_row(connection, payload)
    finally:
        connection.close()
    project_manager.project_data["project_data_version_id"] = new_version
    project_manager._pending_project_data_version_id = ""
    return snapshot


def _active_assets(connection):
    rows = connection.execute(
        """
        SELECT a.owner_key, a.role, a.asset_id, r.digest, r.size_bytes,
               r.hash_algorithm, r.entry_kind, l.location_kind, l.path_base,
               l.relative_path, l.opaque_ref
        FROM integrity_assets a
        JOIN integrity_asset_heads h ON h.asset_id = a.asset_id AND h.tombstoned = 0
        JOIN integrity_asset_revisions r ON r.revision_id = h.revision_id
        LEFT JOIN integrity_locations l ON l.asset_id = a.asset_id AND l.is_active = 1
        WHERE a.owner_kind = 'tif_asset'
        """
    ).fetchall()
    return {(str(row[0]), str(row[1])): row for row in rows}


def _same_location(row, location):
    if row is None:
        return False
    current = {
        "location_kind": str(row[7] or ""),
        "path_base": str(row[8] or ""),
        "relative_path": str(row[9] or ""),
        "opaque_ref": str(row[10] or ""),
    }
    return all(
        str(current.get(key) or "") == str(location.get(key) or "")
        for key in ("location_kind", "path_base", "relative_path", "opaque_ref")
    )


def commit_tif_project_integrity_changes(
    connection,
    project_manager,
    *,
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
    current_assets = _active_assets(connection)
    current_keys = set()
    truth_entries = list(_local_axis_truth_entries(project_manager))
    changes = [_schema_entry(project_manager), *truth_entries]
    current_keys.update(
        (item["owner_key"], item["role"]) for item in truth_entries
    )
    refresh_training_files = bool(candidate_data_version_id)
    for item in _iter_volume_assets(project_manager):
        key = (item["owner_key"], item["role"])
        current_keys.add(key)
        row = current_assets.get(key)
        runtime_path = _runtime_path(project_manager, item["path"])
        entry_kind = "directory" if os.path.isdir(runtime_path) else "file"
        location = _location(project_manager, runtime_path, entry_kind)
        if row is None or not _same_location(row, location) or refresh_training_files:
            change = _asset_entry(project_manager, item)
            changes.append(change)
    for key, row in current_assets.items():
        if key in current_keys:
            continue
        changes.append(
            {
                "change_kind": "tombstone",
                "owner_kind": "tif_asset",
                "owner_key": key[0],
                "role": key[1],
                "media_type": "application/octet-stream",
            }
        )
    candidate = candidate_data_version_id or new_project_data_version_id()
    return commit_project_data_version(
        connection,
        project_id=str(project_manager.project_data.get("project_id") or ""),
        parent_data_version_id=state["current_data_version_id"],
        new_data_version_id=candidate,
        changes=changes,
        reason="tif_training_facts_changed",
    )


__all__ = [
    "LOCAL_AXIS_TRUTH_SNAPSHOT_ID",
    "TIF_SCHEMA_SNAPSHOT_ID",
    "build_tif_baseline_entries",
    "commit_tif_project_integrity_changes",
    "register_tif_project_baseline",
    "relocate_tif_project_asset",
]
