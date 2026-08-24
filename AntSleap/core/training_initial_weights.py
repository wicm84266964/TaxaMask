"""Project-registry evidence for weights used to start a training run."""

from __future__ import annotations

import hashlib
import json
import os
import stat

from .file_integrity import FULL_FILE_ALGORITHM
from .location_registry import register_location, resolve_locations
from .project_integrity_registry import (
    commit_project_data_version,
    get_training_baseline_snapshot,
    registry_state,
)
from .project_traceability import new_project_data_version_id
from .safe_io import read_bytes_bounded_in_root
from .sqlite_storage import connect_sqlite_database


MAX_INITIAL_WEIGHT_BYTES = 4 * 1024 * 1024 * 1024
_INITIAL_WEIGHT_READ_CHUNK_BYTES = 4 * 1024 * 1024


def _is_link_or_reparse(result):
    attributes = int(getattr(result, "st_file_attributes", 0) or 0)
    reparse_flag = int(
        getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400) or 0x400
    )
    return stat.S_ISLNK(result.st_mode) or bool(attributes & reparse_flag)


def _require_regular_initial_weight(result):
    if _is_link_or_reparse(result) or not stat.S_ISREG(result.st_mode):
        raise ValueError("initial_weight_unsafe_entry")


def _stable_file_id(result):
    inode = int(getattr(result, "st_ino", 0) or 0)
    if not inode:
        return None
    return (int(getattr(result, "st_dev", 0) or 0), inode)


def _same_file_identity(left, right):
    left_id = _stable_file_id(left)
    right_id = _stable_file_id(right)
    if left_id is not None and right_id is not None:
        return left_id == right_id
    return (
        int(getattr(left, "st_size", -1))
        == int(getattr(right, "st_size", -2))
        and int(getattr(left, "st_mtime_ns", 0) or 0)
        == int(getattr(right, "st_mtime_ns", 0) or 0)
    )


def _same_file_content_state(left, right):
    return (
        _same_file_identity(left, right)
        and int(getattr(left, "st_size", -1))
        == int(getattr(right, "st_size", -2))
        and int(getattr(left, "st_mtime_ns", 0) or 0)
        == int(getattr(right, "st_mtime_ns", 0) or 0)
    )


def _read_initial_weight_descriptor(path, *, include_payload=False):
    """Hash, and optionally retain, one weight from one no-follow descriptor."""

    before = os.lstat(path)
    _require_regular_initial_weight(before)
    if int(before.st_size) > MAX_INITIAL_WEIGHT_BYTES:
        raise ValueError("initial_weight_too_large")

    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        _require_regular_initial_weight(opened)
        if not _same_file_identity(before, opened):
            raise ValueError("initial_weight_identity_changed_during_open")
        if not _same_file_content_state(before, opened):
            raise ValueError("initial_weight_changed_during_open")

        digest = hashlib.new(FULL_FILE_ALGORITHM)
        chunks = [] if include_payload else None
        size_bytes = 0
        while True:
            remaining = MAX_INITIAL_WEIGHT_BYTES - size_bytes
            chunk = os.read(
                descriptor,
                min(_INITIAL_WEIGHT_READ_CHUNK_BYTES, remaining + 1),
            )
            if not chunk:
                break
            size_bytes += len(chunk)
            if size_bytes > MAX_INITIAL_WEIGHT_BYTES:
                raise ValueError("initial_weight_too_large")
            digest.update(chunk)
            if chunks is not None:
                chunks.append(chunk)

        opened_after = os.fstat(descriptor)
        final_entry = os.lstat(path)
        _require_regular_initial_weight(opened_after)
        _require_regular_initial_weight(final_entry)
        if not _same_file_content_state(opened, opened_after):
            raise ValueError("initial_weight_changed_during_read")
        if not _same_file_content_state(opened_after, final_entry):
            raise ValueError("initial_weight_identity_changed_during_read")
        if size_bytes != int(opened_after.st_size):
            raise ValueError("initial_weight_size_changed_during_read")
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    result = {
        "observed": {
            "entry_kind": "file",
            "size_bytes": size_bytes,
            "hash_algorithm": FULL_FILE_ALGORITHM,
            "digest": digest.hexdigest(),
        }
    }
    if chunks is not None:
        result["payload"] = b"".join(chunks)
    return result


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
        result.append({"slot": slot, "path": path, "expected": expected})
    return result


def inspect_initial_weight_registration(
    project_manager,
    entries,
    *,
    include_payload=False,
):
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
        read_result = _read_initial_weight_descriptor(
            item["path"],
            include_payload=include_payload,
        )
        observed = read_result["observed"]
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
        result = {
            "slot": item["slot"],
            "path": item["path"],
            "status": status,
            "observed": observed,
        }
        if include_payload and status == "verified":
            result["payload"] = read_result["payload"]
        statuses.append(result)
    return {
        "verified": all(item["status"] == "verified" for item in statuses),
        "items": statuses,
    }


def read_verified_initial_weight(project_manager, entry):
    """Return verified bytes and evidence without reopening the registered path."""

    inspected = inspect_initial_weight_registration(
        project_manager,
        [entry],
        include_payload=True,
    )
    item = inspected["items"][0]
    if item["status"] != "verified":
        raise ValueError(
            f"initial_weight_not_verified:{item['slot']}:{item['status']}"
        )
    return item


def training_run_initial_weight_evidence(
    project_manager,
    record,
    *,
    run_dir,
    slot,
):
    """Verify that one historical run manifest includes its registered weight."""

    clean_slot = str(slot or "").strip()
    if not clean_slot:
        raise ValueError("training_run_initial_weight_slot_missing")
    clean_run_dir = os.path.abspath(os.fspath(run_dir))
    project_ref = record.get("project_ref") or {}
    data_version_id = str(project_ref.get("project_data_version_id") or "")
    if not data_version_id:
        raise ValueError("training_run_data_version_missing")
    snapshot = get_training_baseline_snapshot(
        project_manager.current_database_path,
        data_version_id,
    )
    registered = [
        item
        for item in snapshot.get("files", [])
        if item.get("owner_kind") == "model_weight"
        and item.get("owner_key") == clean_slot
        and item.get("role") == "initial_weights"
    ]
    if len(registered) != 1:
        raise ValueError("training_run_initial_weight_registry_entry_missing")
    registered_weight = registered[0]

    manifest_ref = record.get("integrity_manifest")
    if not isinstance(manifest_ref, dict):
        raise ValueError("training_run_integrity_manifest_missing")
    if manifest_ref.get("path_base") != "run_root":
        raise ValueError("training_run_integrity_manifest_path_invalid")
    relative_path = str(manifest_ref.get("relative_path") or "")
    manifest_path = os.path.abspath(
        os.path.join(clean_run_dir, *relative_path.split("/"))
    )
    try:
        inside_run = os.path.normcase(
            os.path.commonpath([clean_run_dir, manifest_path])
        ) == os.path.normcase(clean_run_dir)
    except ValueError:
        inside_run = False
    expected_size = manifest_ref.get("size_bytes")
    if (
        not relative_path
        or not inside_run
        or not isinstance(expected_size, int)
        or isinstance(expected_size, bool)
        or expected_size <= 0
    ):
        raise ValueError("training_run_integrity_manifest_path_invalid")
    manifest_bytes = read_bytes_bounded_in_root(
        manifest_path,
        trusted_root=clean_run_dir,
        max_bytes=expected_size,
    )
    manifest_identity = {
        "entry_kind": "file",
        "size_bytes": len(manifest_bytes),
        "hash_algorithm": FULL_FILE_ALGORITHM,
        "digest": hashlib.sha256(manifest_bytes).hexdigest(),
    }
    for field in ("entry_kind", "size_bytes", "hash_algorithm", "digest"):
        if manifest_identity.get(field) != manifest_ref.get(field):
            raise ValueError(
                f"training_run_integrity_manifest_mismatch:{field}"
            )
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("training_run_integrity_manifest_invalid") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != "taxamask_integrity_manifest_v1"
        or manifest.get("run_id") != record.get("run_id")
        or manifest.get("status") != "verified"
    ):
        raise ValueError("training_run_integrity_manifest_invalid")
    included = [
        item
        for item in manifest.get("files", [])
        if isinstance(item, dict)
        and item.get("file_id") == registered_weight.get("file_id")
        and item.get("role") == "initial_weights"
        and item.get("status") == "verified"
    ]
    if len(included) != 1:
        raise ValueError("training_run_initial_weight_not_in_verified_inputs")
    run_weight = included[0]
    run_entry_kind = run_weight.get("entry_kind")
    registered_entry_kind = registered_weight.get("entry_kind")
    if run_entry_kind == "external_reference":
        if registered_entry_kind != "file" or not run_weight.get(
            "external_location_ref"
        ):
            raise ValueError(
                "training_run_initial_weight_evidence_mismatch:entry_kind"
            )
    elif run_entry_kind != registered_entry_kind:
        raise ValueError(
            "training_run_initial_weight_evidence_mismatch:entry_kind"
        )
    for field in (
        "size_bytes",
        "hash_algorithm",
        "digest",
        "data_version_id",
    ):
        if run_weight.get(field) != registered_weight.get(field):
            raise ValueError(
                f"training_run_initial_weight_evidence_mismatch:{field}"
            )
    return {
        "slot": clean_slot,
        "file_id": str(registered_weight.get("file_id") or ""),
        "data_version_id": data_version_id,
        "fingerprint": {
            key: registered_weight.get(key)
            for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
        },
        "integrity_manifest": {
            "path_base": "run_root",
            "relative_path": relative_path,
            "size_bytes": manifest_identity["size_bytes"],
            "hash_algorithm": manifest_identity["hash_algorithm"],
            "digest": manifest_identity["digest"],
        },
    }


def register_initial_weight_version(project_manager, entries, *, note):
    clean_note = str(note or "").strip()
    if not clean_note:
        raise ValueError("initial_weight_registration_note_required")
    clean = _normalise_entries(entries)
    if not clean:
        return {"changed": False, "data_version_id": str(project_manager.project_data.get("project_data_version_id") or "")}
    for item in clean:
        observed = _read_initial_weight_descriptor(item["path"])["observed"]
        expected = item["expected"]
        if expected is not None and any(
            observed.get(key) != expected.get(key)
            for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
        ):
            raise ValueError(
                f"initial_weight_publisher_hash_mismatch:{item['slot']}"
            )
        item["observed"] = observed
    changes = []
    for item in clean:
        expected = item["expected"] or item["observed"]
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
    "read_verified_initial_weight",
    "register_initial_weight_version",
    "training_run_initial_weight_evidence",
]
