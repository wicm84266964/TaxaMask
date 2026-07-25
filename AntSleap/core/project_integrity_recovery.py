"""User-facing inspection and redacted diagnostics for Registry mismatches."""

from __future__ import annotations

import os

from .file_integrity import compute_fingerprint
from .location_registry import (
    LocationRegistryError,
    read_registered_locations,
    require_safe_existing_path,
)
from .project_integrity_registry import (
    ProjectIntegrityRegistryError,
    _safe_runtime_target,
    get_training_baseline_snapshot,
)
from .safe_io import atomic_write_json


class ProjectIntegrityRecoveryError(ValueError):
    def __init__(self, code, summary=None):
        self.code = str(code or "integrity_recovery_error")
        super().__init__(str(summary or self.code))


def _project_root(project_manager):
    source = (
        getattr(project_manager, "current_project_path", "")
        or getattr(project_manager, "current_database_path", "")
    )
    if not source:
        raise ProjectIntegrityRecoveryError("project_root_unavailable")
    return os.path.abspath(os.path.dirname(os.path.abspath(source)) or os.curdir)


def _managed_recovery_source(project_manager, location):
    if str(location.get("path_base") or "") != "project_root":
        raise ProjectIntegrityRecoveryError("source_path_unsafe")
    try:
        runtime_path, _clean_relative = _safe_runtime_target(
            _project_root(project_manager),
            location.get("relative_path"),
        )
    except ProjectIntegrityRegistryError as exc:
        raise ProjectIntegrityRecoveryError(
            "source_path_unsafe",
            f"source_path_unsafe:{exc.code}",
        ) from exc
    return runtime_path


def _require_safe_recovery_source(path, *, expected_kind=None):
    raw = os.fspath(path)
    if not raw:
        raise FileNotFoundError(raw)
    absolute = os.path.abspath(raw)
    try:
        return require_safe_existing_path(
            absolute,
            expected_kind=expected_kind,
        )
    except LocationRegistryError as exc:
        if exc.code == "location_path_missing":
            raise FileNotFoundError(absolute) from exc
        if exc.code == "location_path_unreadable":
            raise PermissionError(absolute) from exc
        raise ProjectIntegrityRecoveryError(
            "source_path_unsafe",
            f"source_path_unsafe:{exc.code}",
        ) from exc


def _issue_runtime_source(project_manager, issue):
    """Resolve a recovery issue from its recorded locator, not UI path text."""

    location_kind = str(issue.get("location_kind") or "")
    expected_kind = (issue.get("expected") or {}).get("entry_kind")
    if location_kind == "managed_relative":
        return _managed_recovery_source(
            project_manager,
            {
                "path_base": "project_root",
                "relative_path": issue.get("location_ref"),
            },
        )
    if location_kind == "opaque_ref":
        location_ref = str(issue.get("location_ref") or "")
        try:
            records = read_registered_locations(
                [location_ref],
                database_path=getattr(
                    project_manager, "location_registry_database_path", None
                ),
            )
        except LocationRegistryError as exc:
            raise ProjectIntegrityRecoveryError(
                "opaque_location_unavailable"
            ) from exc
        record = records.get(location_ref)
        if not isinstance(record, dict) or not record.get("path"):
            raise ProjectIntegrityRecoveryError("opaque_location_unavailable")
        if expected_kind and str(record.get("entry_kind") or "") != str(
            expected_kind
        ):
            raise ProjectIntegrityRecoveryError("source_path_unsafe")
        return os.fspath(record["path"])
    raw = issue.get("runtime_path") or ""
    if not raw:
        raise ProjectIntegrityRecoveryError("source_path_unsafe")
    return raw


def inspect_project_integrity(
    project_manager, *, progress_callback=None, cancel_check=None
):
    snapshot = get_training_baseline_snapshot(
        project_manager.current_database_path,
        project_manager.project_data.get("project_data_version_id"),
    )
    refs = [
        item["location"]["opaque_ref"]
        for item in snapshot["files"]
        if item.get("location", {}).get("location_kind") == "opaque_ref"
    ]
    opaque = read_registered_locations(
        refs,
        database_path=getattr(
            project_manager, "location_registry_database_path", None
        ),
    )
    items = []
    entries = list(snapshot["files"])
    for index, entry in enumerate(entries, start=1):
        if cancel_check is not None and cancel_check():
            raise RuntimeError("integrity_check_cancelled")
        if progress_callback is not None:
            progress_callback(
                index - 1,
                len(entries),
                str(entry.get("role") or "file"),
            )
        location = entry.get("location")
        if not isinstance(location, dict):
            continue
        runtime_path = ""
        location_ref = ""
        managed = location.get("location_kind") == "managed_relative"
        if managed:
            location_ref = str(location.get("relative_path") or "")
        else:
            location_ref = str(location.get("opaque_ref") or "")
        observed = None
        error_code = ""
        try:
            if managed:
                runtime_path = _managed_recovery_source(
                    project_manager,
                    location,
                )
            else:
                record = opaque.get(location_ref)
                if not isinstance(record, dict) or not record.get("path"):
                    raise ProjectIntegrityRecoveryError(
                        "opaque_location_unavailable"
                    )
                runtime_path = os.path.abspath(os.fspath(record["path"]))
            runtime_path = _require_safe_recovery_source(
                runtime_path,
                expected_kind=entry.get("entry_kind"),
            )
            observed = compute_fingerprint(
                runtime_path, entry["hash_algorithm"]
            )
        except FileNotFoundError:
            status = "missing"
            error_code = "source_missing"
        except PermissionError:
            status = "incomplete"
            error_code = "source_read_denied"
        except Exception as exc:
            status = "incomplete"
            error_code = getattr(exc, "code", "integrity_check_failed")
        else:
            matches = all(
                observed.get(key) == entry.get(key)
                for key in (
                    "entry_kind",
                    "size_bytes",
                    "hash_algorithm",
                    "digest",
                )
            )
            status = "verified" if matches else "mismatch"
            error_code = "" if matches else "source_digest_mismatch"
        items.append(
            {
                "asset_id": entry["asset_id"],
                "owner_kind": entry["owner_kind"],
                "owner_key": entry["owner_key"],
                "role": entry["role"],
                "runtime_path": runtime_path,
                "location_kind": location.get("location_kind"),
                "location_ref": location_ref,
                "expected": {
                    key: entry.get(key)
                    for key in (
                        "entry_kind",
                        "size_bytes",
                        "hash_algorithm",
                        "digest",
                    )
                },
                "observed": observed,
                "status": status,
                "error_code": error_code,
            }
        )
    if progress_callback is not None:
        progress_callback(len(entries), len(entries), "complete")
    return {
        "project_id": snapshot["project_id"],
        "data_version_id": snapshot["data_version_id"],
        "status": (
            "verified"
            if all(item["status"] == "verified" for item in items)
            else "needs_attention"
        ),
        "items": items,
    }


def write_redacted_integrity_diagnostic(report, output_path):
    redacted_items = []
    for item in report.get("items", []):
        redacted_items.append(
            {
                key: item.get(key)
                for key in (
                    "asset_id",
                    "owner_kind",
                    "owner_key",
                    "role",
                    "location_kind",
                    "location_ref",
                    "expected",
                    "observed",
                    "status",
                    "error_code",
                )
            }
        )
        redacted_items[-1]["file_name"] = os.path.basename(
            str(item.get("runtime_path") or "")
        )
    payload = {
        "schema_version": "taxamask_integrity_diagnostic_v1",
        "project_id": report.get("project_id"),
        "data_version_id": report.get("data_version_id"),
        "status": report.get("status"),
        "items": redacted_items,
    }
    atomic_write_json(output_path, payload, indent=2)
    return os.path.abspath(os.fspath(output_path))


def register_current_asset_version(project_manager, issue, *, note):
    clean_note = str(note or "").strip()
    if not clean_note:
        raise ValueError("integrity_new_version_note_required")
    if issue.get("owner_kind") not in {"image", "tif_asset"}:
        raise ValueError("integrity_asset_new_version_not_supported")
    runtime_path = _require_safe_recovery_source(
        _issue_runtime_source(project_manager, issue),
        expected_kind=(issue.get("expected") or {}).get("entry_kind"),
    )
    observed = compute_fingerprint(runtime_path, issue["expected"]["hash_algorithm"])
    if issue.get("owner_kind") == "tif_asset":
        from .tif_integrity_bridge import _location

        location = _location(
            project_manager, runtime_path, observed["entry_kind"]
        )
    else:
        from .project_integrity_bridge import _source_location

        location = _source_location(project_manager, runtime_path)
    from .project_integrity_registry import commit_project_data_version, registry_state
    from .project_traceability import new_project_data_version_id
    from .sqlite_storage import connect_sqlite_database

    connection = connect_sqlite_database(project_manager.current_database_path)
    try:
        with connection:
            state = registry_state(connection)
            result = commit_project_data_version(
                connection,
                project_id=project_manager.project_data["project_id"],
                parent_data_version_id=state["current_data_version_id"],
                new_data_version_id=new_project_data_version_id(),
                changes=[
                    {
                        "owner_kind": issue["owner_kind"],
                        "owner_key": issue["owner_key"],
                        "role": issue["role"],
                        "media_type": "application/octet-stream",
                        "expected": observed,
                        "location": location,
                        "runtime_path": runtime_path,
                        "change_metadata": {"note": clean_note},
                    }
                ],
                reason="researcher_registered_new_file_version",
            )
            if result.get("changed"):
                if issue.get("owner_kind") == "tif_asset":
                    from .tif_sqlite_migration import _insert_project_row

                    project_payload = dict(project_manager.project_data)
                    project_payload["project_data_version_id"] = result[
                        "data_version_id"
                    ]
                    _insert_project_row(connection, project_payload)
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
    "ProjectIntegrityRecoveryError",
    "inspect_project_integrity",
    "register_current_asset_version",
    "write_redacted_integrity_diagnostic",
]
