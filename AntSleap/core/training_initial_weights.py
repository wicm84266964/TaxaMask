"""Project-registry evidence for weights used to start a training run."""

from __future__ import annotations

import os

from .file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from .location_registry import register_location, resolve_locations
from .project_integrity_registry import (
    commit_project_data_version,
    get_training_baseline_snapshot,
    registry_state,
)
from .project_traceability import new_project_data_version_id
from .sqlite_storage import connect_sqlite_database


def _normalise_entries(entries):
    result = []
    seen = set()
    for item in entries or []:
        slot = str(item.get("slot") or "").strip()
        path = os.path.abspath(os.fspath(item.get("path") or ""))
        if not slot or slot in seen:
            raise ValueError("initial_weight_slot_invalid")
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        seen.add(slot)
        expected = item.get("expected")
        if expected is not None:
            observed = compute_fingerprint(path, FULL_FILE_ALGORITHM)
            if any(
                observed.get(key) != expected.get(key)
                for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
            ):
                raise ValueError(f"initial_weight_publisher_hash_mismatch:{slot}")
        result.append({"slot": slot, "path": path, "expected": expected})
    return result


def inspect_initial_weight_registration(project_manager, entries):
    clean = _normalise_entries(entries)
    data_version_id = str(
        project_manager.project_data.get("project_data_version_id") or ""
    )
    snapshot = get_training_baseline_snapshot(
        project_manager.current_database_path, data_version_id
    )
    registered = {
        item["owner_key"]: item
        for item in snapshot["files"]
        if item.get("owner_kind") == "model_weight"
        and item.get("role") == "initial_weights"
    }
    refs = [
        item["location"]["opaque_ref"]
        for item in registered.values()
        if item.get("location", {}).get("location_kind") == "opaque_ref"
    ]
    locations = resolve_locations(
        refs,
        database_path=getattr(
            project_manager, "location_registry_database_path", None
        ),
    )
    statuses = []
    for item in clean:
        record = registered.get(item["slot"])
        observed = compute_fingerprint(item["path"], FULL_FILE_ALGORITHM)
        status = "missing"
        if record is not None:
            location = record.get("location") or {}
            registered_path = ""
            if location.get("location_kind") == "managed_relative":
                registered_path = os.path.abspath(
                    os.path.join(
                        project_manager.project_dir,
                        *str(location.get("relative_path") or "").split("/"),
                    )
                )
            elif location.get("location_kind") == "opaque_ref":
                registered_path = os.path.abspath(
                    os.fspath(locations.get(location.get("opaque_ref")) or "")
                )
            if os.path.normcase(registered_path) != os.path.normcase(item["path"]):
                status = "location_changed"
            else:
                status = "verified" if all(
                    observed.get(key) == record.get(key)
                    for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
                ) else "mismatch"
        statuses.append(
            {
                "slot": item["slot"],
                "path": item["path"],
                "status": status,
                "observed": observed,
            }
        )
    return {
        "verified": all(item["status"] == "verified" for item in statuses),
        "items": statuses,
    }


def register_initial_weight_version(project_manager, entries, *, note):
    clean_note = str(note or "").strip()
    if not clean_note:
        raise ValueError("initial_weight_registration_note_required")
    clean = _normalise_entries(entries)
    if not clean:
        return {"changed": False, "data_version_id": str(project_manager.project_data.get("project_data_version_id") or "")}
    changes = []
    for item in clean:
        expected = item["expected"] or compute_fingerprint(
            item["path"], FULL_FILE_ALGORITHM
        )
        opaque_ref = register_location(
            item["path"],
            entry_kind="file",
            database_path=getattr(
                project_manager, "location_registry_database_path", None
            ),
        )
        changes.append(
            {
                "owner_kind": "model_weight",
                "owner_key": item["slot"],
                "role": "initial_weights",
                "media_type": "application/octet-stream",
                "expected": expected,
                "location": {
                    "location_kind": "opaque_ref",
                    "opaque_ref": opaque_ref,
                },
                "runtime_path": item["path"],
                "change_metadata": {"note": clean_note},
            }
        )
    connection = connect_sqlite_database(project_manager.current_database_path)
    try:
        with connection:
            state = registry_state(connection)
            result = commit_project_data_version(
                connection,
                project_id=project_manager.project_data["project_id"],
                parent_data_version_id=state["current_data_version_id"],
                new_data_version_id=new_project_data_version_id(),
                changes=changes,
                reason="initial_training_weights_registered",
            )
            if result.get("changed"):
                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                if "tif_projects" in tables:
                    from .tif_sqlite_migration import _insert_project_row

                    payload = dict(project_manager.project_data)
                    payload["project_data_version_id"] = result["data_version_id"]
                    _insert_project_row(connection, payload)
                else:
                    from .project_sqlite_writer import write_project_metadata

                    write_project_metadata(
                        connection,
                        project_manager,
                        project_data_version_id=result["data_version_id"],
                    )
    finally:
        connection.close()
    if result.get("changed"):
        project_manager.project_data["project_data_version_id"] = result[
            "data_version_id"
        ]
        project_manager._pending_project_data_version_id = ""
    return result


__all__ = [
    "inspect_initial_weight_registration",
    "register_initial_weight_version",
]
