import json
import os
import time
from dataclasses import dataclass

from .safe_io import atomic_write_json
from .sqlite_storage import (
    SQLITE_BACKUP_LIMIT,
    SQLITE_BACKUP_MIN_INTERVAL_SECONDS,
    backup_sqlite_database,
    ensure_integrity_ok,
    read_project_manifest,
    resolve_manifest_database_path,
    write_project_manifest,
)


@dataclass
class SQLiteProjectBackupResult:
    source_manifest_path: str
    source_database_path: str
    backup_database_path: str
    backup_manifest_path: str
    integrity_check: list


@dataclass
class LegacyJSONExportResult:
    manifest_path: str
    output_path: str
    project_type: str
    stats: dict


def _timestamp():
    return time.strftime("%Y%m%d_%H%M%S")


def _abs(path):
    return os.path.abspath(str(path))


def _manifest_dir(manifest_path):
    return os.path.dirname(_abs(manifest_path)) or "."


def _resolve_manifest_reference(manifest_path, value):
    text = str(value or "").strip()
    if not text:
        return ""
    if os.path.isabs(text):
        return os.path.normpath(text)
    return os.path.normpath(os.path.join(_manifest_dir(manifest_path), text))


def _relative_reference(path, base_dir):
    text = str(path or "").strip()
    if not text:
        return ""
    try:
        return os.path.relpath(text, base_dir).replace("\\", "/")
    except ValueError:
        return os.path.abspath(text)


def _rebase_manifest_path_key(payload, source_manifest_path, backup_manifest_dir, key):
    value = str(payload.get(key) or "").strip()
    if not value:
        return
    resolved = _resolve_manifest_reference(source_manifest_path, value)
    payload[key] = _relative_reference(resolved, backup_manifest_dir)


def _backup_manifest_path_for_database(backup_database_path):
    backup_db = _abs(backup_database_path)
    if backup_db.endswith(".sqlite.bak"):
        return backup_db[: -len(".sqlite.bak")] + ".sqlite_manifest.json"
    stem, _ext = os.path.splitext(backup_db)
    return f"{stem}.sqlite_manifest.json"


def _prune_orphan_backup_manifests(backup_dir, backup_stem):
    try:
        names = os.listdir(backup_dir)
    except OSError:
        return
    live_databases = {
        name[: -len(".sqlite.bak")]
        for name in names
        if name.startswith(f"{backup_stem}.") and name.endswith(".sqlite.bak")
    }
    manifest_paths = [
        os.path.join(backup_dir, name)
        for name in names
        if name.startswith(f"{backup_stem}.") and name.endswith(".sqlite_manifest.json")
    ]
    manifest_paths.sort(key=lambda item: os.path.getmtime(item), reverse=True)
    for manifest_path in manifest_paths:
        name = os.path.basename(manifest_path)
        base = name[: -len(".sqlite_manifest.json")]
        if base not in live_databases or manifest_paths.index(manifest_path) >= SQLITE_BACKUP_LIMIT:
            try:
                os.remove(manifest_path)
            except OSError:
                pass


def backup_sqlite_project_manifest(
    manifest_path,
    backup_dir=None,
    *,
    stem=None,
    min_interval_seconds=SQLITE_BACKUP_MIN_INTERVAL_SECONDS,
):
    source_manifest = _abs(manifest_path)
    manifest = read_project_manifest(source_manifest)
    source_database = resolve_manifest_database_path(source_manifest, manifest)
    target_dir = _abs(backup_dir or os.path.join(os.path.dirname(source_database) or ".", "project.sqlite_backups"))
    os.makedirs(target_dir, exist_ok=True)
    backup_stem = stem or os.path.splitext(os.path.basename(source_database))[0] or "project"
    backup_database = backup_sqlite_database(
        source_database,
        target_dir,
        stem=backup_stem,
        min_interval_seconds=min_interval_seconds,
    )
    if not backup_database:
        return SQLiteProjectBackupResult(
            source_manifest_path=source_manifest,
            source_database_path=source_database,
            backup_database_path="",
            backup_manifest_path="",
            integrity_check=[],
        )

    import sqlite3

    conn = sqlite3.connect(backup_database)
    try:
        integrity = ensure_integrity_ok(conn)
    finally:
        conn.close()

    backup_manifest = _backup_manifest_path_for_database(backup_database)
    backup_manifest_dir = os.path.dirname(backup_manifest) or "."
    extra = {
        key: value
        for key, value in manifest.items()
        if key not in {"schema_version", "storage_backend", "database_path", "created_at", "updated_at"}
    }
    for key in ("migration_report", "legacy_json_backup", "tif_asset_root", "project_asset_root"):
        _rebase_manifest_path_key(extra, source_manifest, backup_manifest_dir, key)
    extra["backup_source_manifest"] = _relative_reference(source_manifest, backup_manifest_dir)
    extra["backup_source_database"] = _relative_reference(source_database, backup_manifest_dir)
    extra["backup_created_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    extra["backup_open_hint"] = "Open this manifest with TaxaMask to inspect the SQLite backup."

    write_project_manifest(
        backup_manifest,
        manifest.get("project_type", ""),
        manifest.get("name", "Untitled"),
        backup_database,
        extra=extra,
    )
    _prune_orphan_backup_manifests(target_dir, backup_stem)
    return SQLiteProjectBackupResult(
        source_manifest_path=source_manifest,
        source_database_path=source_database,
        backup_database_path=_abs(backup_database),
        backup_manifest_path=_abs(backup_manifest),
        integrity_check=integrity,
    )


def sqlite_project_migration_report_path(manifest_path):
    source_manifest = _abs(manifest_path)
    manifest = read_project_manifest(source_manifest)
    report_path = _resolve_manifest_reference(source_manifest, manifest.get("migration_report", ""))
    return report_path if report_path and os.path.exists(report_path) else ""


def _json_stats(payload, project_type):
    if project_type == "tif_volume":
        specimens = payload.get("specimens", []) if isinstance(payload, dict) else []
        parts = 0
        rois = 0
        reslices = 0
        for specimen in specimens if isinstance(specimens, list) else []:
            if not isinstance(specimen, dict):
                continue
            specimen_parts = specimen.get("parts", [])
            parts += len(specimen_parts) if isinstance(specimen_parts, list) else 0
            specimen_rois = specimen.get("part_rois", [])
            rois += len(specimen_rois) if isinstance(specimen_rois, list) else 0
            for part in specimen_parts if isinstance(specimen_parts, list) else []:
                metadata = part.get("metadata", {}) if isinstance(part, dict) else {}
                records = metadata.get("local_axis_reslices", []) if isinstance(metadata, dict) else []
                reslices += len(records) if isinstance(records, list) else 0
        return {
            "specimen_count": len(specimens) if isinstance(specimens, list) else 0,
            "part_count": parts,
            "part_roi_count": rois,
            "part_reslice_count": reslices,
        }

    images = payload.get("images", []) if isinstance(payload, dict) else []
    labels = payload.get("labels", {}) if isinstance(payload, dict) else {}
    nonempty = 0
    for label in labels.values() if isinstance(labels, dict) else []:
        if isinstance(label, dict) and any(label.get(key) for key in ("parts", "boxes", "auto_boxes", "trajectories")):
            nonempty += 1
    return {
        "image_count": len(images) if isinstance(images, list) else 0,
        "label_count": len(labels) if isinstance(labels, dict) else 0,
        "nonempty_label_count": nonempty,
    }


def export_sqlite_project_to_legacy_json(manifest_path, output_path):
    source_manifest = _abs(manifest_path)
    manifest = read_project_manifest(source_manifest)
    project_type = str(manifest.get("project_type") or "")
    if project_type == "tif_volume":
        from .tif_project import TifProjectManager

        manager = TifProjectManager()
        manager.load_project(source_manifest)
        payload = manager.legacy_json_payload(output_path)
    else:
        from .project import ProjectManager

        manager = ProjectManager()
        manager.load_project(source_manifest)
        payload = manager.legacy_json_payload(output_path)

    output_abs = _abs(output_path)
    atomic_write_json(output_abs, payload, indent=2, ensure_ascii=False)
    return LegacyJSONExportResult(
        manifest_path=source_manifest,
        output_path=output_abs,
        project_type=project_type,
        stats=_json_stats(payload, project_type),
    )


def read_json_file(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
