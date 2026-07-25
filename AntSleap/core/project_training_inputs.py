"""Resolve immutable 2D project training samples from the SQLite Registry."""

from __future__ import annotations

import json
import os

from .location_registry import resolve_locations
from .project_integrity_registry import (
    get_training_baseline_snapshot,
    read_materialized_registry_payloads,
    resolve_training_baseline_inputs,
)


def _read_materialized_json(entry):
    materializer = entry.get("materializer")
    if not isinstance(materializer, dict):
        raise ValueError("registry_snapshot_materializer_missing")
    path = str(materializer.get("runtime_path") or "")
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("registry_snapshot_payload_invalid")
    return payload


def _effective_allowed_image_uids(
    database_path,
    snapshot,
    allowed_image_uids,
    max_samples,
    *,
    include_parts=False,
):
    allowed = (
        {str(value) for value in allowed_image_uids}
        if allowed_image_uids is not None
        else None
    )
    limit = int(max_samples or 0)
    if limit <= 0:
        return allowed

    source_uids = {
        str(item.get("owner_key") or "")
        for item in snapshot.get("files", [])
        if item.get("role") == "source_image"
    }
    materialized = read_materialized_registry_payloads(
        database_path,
        snapshot,
        roles={"label_schema", "human_confirmed_label"},
    )
    schema_entries = [
        item
        for item in snapshot.get("files", [])
        if item.get("role") == "label_schema"
    ]
    if len(schema_entries) != 1:
        raise ValueError("registry_label_schema_missing_or_ambiguous")
    schema = materialized.get(str(schema_entries[0].get("file_id") or ""), {})
    taxonomy = {
        str(value)
        for value in (schema.get("taxonomy") or [])
        if str(value)
    }
    locator_scope = {
        str(value)
        for value in (schema.get("locator_scope") or [])
        if str(value)
    }
    candidates = []
    for item in snapshot.get("files", []):
        if item.get("role") != "human_confirmed_label":
            continue
        image_uid = str(item.get("owner_key") or "")
        if image_uid not in source_uids:
            continue
        payload = materialized.get(str(item.get("file_id") or ""), {})
        parts = payload.get("parts") if isinstance(payload, dict) else {}
        if not isinstance(parts, dict):
            continue
        part_names = {str(name) for name in parts}
        if not (part_names & locator_scope):
            continue
        if include_parts and not (part_names & taxonomy):
            continue
        candidates.append(image_uid)
    candidates = sorted(set(candidates))
    if allowed is not None:
        candidates = [uid for uid in candidates if uid in allowed]
    return set(candidates[:limit])


def _selected_registry_file_ids(
    snapshot,
    *,
    allowed_image_uids=None,
    included_initial_weight_slots=(),
):
    allowed = (
        {str(value) for value in allowed_image_uids}
        if allowed_image_uids is not None
        else None
    )
    weight_slots = {str(value) for value in included_initial_weight_slots or ()}
    selected = []
    for item in snapshot.get("files", []):
        role = str(item.get("role") or "")
        owner_key = str(item.get("owner_key") or "")
        if role in {"source_image", "human_confirmed_label"}:
            if allowed is not None and owner_key not in allowed:
                continue
        elif role == "initial_weights" and owner_key not in weight_slots:
            continue
        selected.append(str(item.get("file_id") or ""))
    return selected


def resolve_2d_project_training_dataset(
    run,
    project_manager,
    *,
    data_version_id=None,
    max_samples=0,
    allowed_image_uids=None,
    included_initial_weight_slots=(),
    include_parts=False,
    detail_progress_callback=None,
    cancel_check=None,
):
    """Verify a fixed Registry version and return Dataset-ready trusted records."""

    database_path = str(
        getattr(project_manager, "current_database_path", "") or ""
    )
    is_sqlite_project = getattr(project_manager, "is_sqlite_project", None)
    if (
        not database_path
        or not callable(is_sqlite_project)
        or not is_sqlite_project()
    ):
        raise ValueError("sqlite_project_required_for_training")
    project_root = os.path.dirname(
        os.path.abspath(project_manager.current_project_path)
    )
    snapshot = get_training_baseline_snapshot(database_path, data_version_id)
    effective_allowed_image_uids = _effective_allowed_image_uids(
        database_path,
        snapshot,
        allowed_image_uids,
        max_samples,
        include_parts=include_parts,
    )
    selected_file_ids = _selected_registry_file_ids(
        snapshot,
        allowed_image_uids=effective_allowed_image_uids,
        included_initial_weight_slots=included_initial_weight_slots,
    )
    selected_file_id_set = set(selected_file_ids)
    opaque_refs = [
        item["location"]["opaque_ref"]
        for item in snapshot["files"]
        if str(item.get("file_id") or "") in selected_file_id_set
        if isinstance(item.get("location"), dict)
        and item["location"].get("location_kind") == "opaque_ref"
    ]
    opaque_locations = resolve_locations(
        opaque_refs,
        database_path=getattr(
            project_manager, "location_registry_database_path", None
        ),
    )
    resolved = resolve_training_baseline_inputs(
        database_path,
        snapshot,
        project_root=project_root,
        run_root=run.run_dir,
        opaque_locations=opaque_locations,
        detail_progress_callback=detail_progress_callback,
        cancel_check=cancel_check,
        issue_verification_batch=True,
        selected_file_ids=selected_file_ids,
    )
    verification_batch = resolved.pop("verification_batch")
    schema_entries = [
        item for item in resolved["files"] if item["role"] == "label_schema"
    ]
    if len(schema_entries) != 1:
        raise ValueError("registry_label_schema_missing_or_ambiguous")
    schema = _read_materialized_json(schema_entries[0])
    taxonomy = list(schema.get("taxonomy") or [])
    locator_scope = list(schema.get("locator_scope") or [])
    sources = {
        item["owner_key"]: str(item["location"]["runtime_path"])
        for item in resolved["files"]
        if item["role"] == "source_image"
        and isinstance(item.get("location"), dict)
    }
    labels = {
        item["owner_key"]: _read_materialized_json(item)
        for item in resolved["files"]
        if item["role"] == "human_confirmed_label"
    }
    allowed = (
        set(effective_allowed_image_uids)
        if effective_allowed_image_uids is not None
        else None
    )

    locator_records = []
    parts_records = []
    sample_uid_by_path = {}
    for image_uid in sorted(set(sources) & set(labels)):
        if allowed is not None and image_uid not in allowed:
            continue
        image_path = sources[image_uid]
        payload = labels[image_uid]
        raw_parts = (
            payload.get("parts")
            if isinstance(payload.get("parts"), dict)
            else {}
        )
        raw_boxes = (
            payload.get("boxes")
            if isinstance(payload.get("boxes"), dict)
            else {}
        )
        locator_parts = {
            name: raw_parts[name]
            for name in locator_scope
            if name in raw_parts
        }
        trainable_parts = {
            name: raw_parts[name] for name in taxonomy if name in raw_parts
        }
        if locator_parts:
            locator_records.append(
                (
                    image_path,
                    {
                        "parts": locator_parts,
                        "boxes": {
                            name: raw_boxes[name]
                            for name in locator_parts
                            if name in raw_boxes
                        },
                    },
                )
            )
        if trainable_parts:
            parts_records.append(
                (
                    image_path,
                    {
                        "parts": trainable_parts,
                        "boxes": {
                            name: raw_boxes[name]
                            for name in trainable_parts
                            if name in raw_boxes
                        },
                    },
                )
            )
        sample_uid_by_path[image_path] = image_uid
    return {
        "database_path": database_path,
        "project_root": project_root,
        "project_id": resolved["project_id"],
        "data_version_id": resolved["data_version_id"],
        "taxonomy": taxonomy,
        "locator_scope": locator_scope,
        "source_count": len(sources),
        "verification_batch": verification_batch,
        "resolved_inputs": resolved,
        "source_paths_by_uid": dict(sources),
        "label_snapshots_by_uid": dict(labels),
        "locator_records": locator_records,
        "parts_records": parts_records,
        "sample_uid_by_path": sample_uid_by_path,
    }


__all__ = ["resolve_2d_project_training_dataset"]
