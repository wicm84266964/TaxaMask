"""Resolve immutable 2D project training samples from the SQLite Registry."""

from __future__ import annotations

import json
import os

from .location_registry import resolve_locations
from .project_integrity_registry import (
    get_training_baseline_snapshot,
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


def _limit(records, max_samples):
    selected = list(records or [])
    return selected[:max_samples] if int(max_samples) > 0 else selected


def resolve_2d_project_training_dataset(
    run,
    project_manager,
    *,
    data_version_id=None,
    max_samples=0,
    allowed_image_uids=None,
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
    opaque_refs = [
        item["location"]["opaque_ref"]
        for item in snapshot["files"]
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
    )
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
        {str(value) for value in allowed_image_uids}
        if allowed_image_uids is not None
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
        "resolved_inputs": resolved,
        "source_paths_by_uid": dict(sources),
        "label_snapshots_by_uid": dict(labels),
        "locator_records": _limit(locator_records, max_samples),
        "parts_records": _limit(parts_records, max_samples),
        "sample_uid_by_path": sample_uid_by_path,
    }


__all__ = ["resolve_2d_project_training_dataset"]
