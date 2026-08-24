import copy
import hashlib
import json
import logging
import ntpath
import os
import re
import shutil
import uuid
from datetime import datetime

from .safe_io import (
    AdvisoryFileLock,
    UnsafeFilesystemPath,
    atomic_write_json,
    atomic_write_json_in_root,
    backup_file,
    isolate_regular_file_in_root,
    read_json_bounded_in_root,
)
from .path_identity import canonical_path, paths_overlap, paths_refer_to_same_file
from .sqlite_storage import LEGACY_JSON_BACKEND, PROJECT_MANIFEST_SCHEMA_VERSION, SQLITE_BACKEND, write_project_manifest
from .tif_label_guard import can_write_label_role
from .tif_materials import has_trainable_material, read_material_map, write_material_map
from .tif_truth_policy import can_promote_to_manual_truth, can_use_role_for_training
from .tif_volume_io import (
    VOLUME_SIDECAR_FORMAT,
    begin_volume_sidecar_replacement,
    read_volume_metadata,
    volume_sidecar_exists,
)
from .tif_write_guard import WriteIntent, ensure_write_allowed
from .project_traceability import (
    PROJECT_KIND_TIF,
    ensure_project_traceability,
    new_project_data_version_id,
    new_project_traceability,
)


TIF_PROJECT_SCHEMA_VERSION = "ant3d_tif_project_v1"
TIF_PROJECT_TYPE = "tif_volume"
DEFAULT_TIF_PROJECT_FILENAME = "project.json"
TIF_PROJECT_BACKUP_LIMIT = 30
TIF_PROJECT_BACKUP_MIN_INTERVAL_SECONDS = 300
TIF_VOLUME_CLEANUP_WARNING_LIMIT = 100
TIF_VOLUME_CLEANUP_WARNING_MAX_BYTES = 8 * 1024 * 1024
TIF_VOLUME_CLEANUP_WARNING_SCHEMA_VERSION = "taxamask_tif_volume_cleanup_warnings_v1"
TIF_VOLUME_CLEANUP_WARNING_RELATIVE_PATH = os.path.join(
    "logs", "tif_volume_cleanup_warnings.json"
)
TIF_VOLUME_CLEANUP_WARNING_LOCK_TIMEOUT_SECONDS = 5.0
TIF_REVIEW_STATUSES = {"not_started", "in_progress", "fully_annotated", "reviewed", "train_ready"}
TIF_PART_STATUSES = {"draft", "roi_confirmed", "mask_preview", "mask_in_progress", "reviewed", "ready_for_labeling", "predicted_pending_review", "train_ready", "failed"}
TIF_PART_SYSTEM_STATUSES = {"cut_pending_labeling", "predicted_pending_review", "verified_train_ready", "failed"}
TIF_PART_LABEL_ROLES = {"manual_truth", "editable_ai_result", "raw_ai_prediction_backup"}
TIF_PART_ROI_STATUSES = {"draft", "confirmed", "part_created", "cancelled"}
LOCAL_AXIS_PROPOSAL_STATUSES = {"proposed", "needs_review", "accepted", "rejected", "exported"}
TIF_LABEL_SCHEMA_EXPORT_SCHEMA_VERSION = "taxamask_tif_label_schema_v1"


_LOGGER = logging.getLogger(__name__)


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_path_fragment(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    clean = clean.strip("_")
    if not clean or clean in {".", ".."} or not clean.strip("."):
        return "specimen"
    return clean


def _safe_part_id(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    clean = clean.strip("_")
    if not clean or clean in {".", ".."} or not clean.strip("."):
        return "part"
    return clean


def _safe_roi_id(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    clean = clean.strip("_")
    if not clean or clean in {".", ".."} or not clean.strip("."):
        return "roi"
    return clean


def _safe_record_id(value, fallback="record"):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    clean = clean.strip("_")
    if not clean or clean in {".", ".."} or not clean.strip("."):
        return str(fallback or "record")
    return clean


def _tif_shape_from_metadata(path):
    try:
        import tifffile

        with tifffile.TiffFile(path) as tif:
            shape = getattr(tif.series[0], "shape", ()) if tif.series else ()
        return [int(value) for value in shape] if shape else []
    except Exception:
        return []


def _default_project_data(name="Untitled TIF Project", project_id=None):
    now = _now_iso()
    traceability = new_project_traceability(PROJECT_KIND_TIF, project_id=project_id)
    return {
        **traceability,
        "schema_version": TIF_PROJECT_SCHEMA_VERSION,
        "project_type": TIF_PROJECT_TYPE,
        "name": str(name or "Untitled TIF Project"),
        "created_at": now,
        "updated_at": now,
        "specimens": [],
        "label_schemas": [],
        "part_user_tags": [],
        "models": [],
        "runs": [],
        "view_settings": {},
    }


class TifProjectManager:
    def __init__(self):
        self.project_data = _default_project_data()
        self.current_project_path = None
        self.current_storage_backend = LEGACY_JSON_BACKEND
        self.current_database_path = ""
        self.current_asset_root = ""
        self._legacy_json_write_enabled = False
        self._pending_project_data_version_id = ""
        self._pending_integrity_dirty_assets = set()
        self._traceability_backfill_needed = False
        self.volume_cleanup_warnings = []
        self._volume_cleanup_warning_dirty_ids = set()

    @property
    def project_dir(self):
        if self.current_asset_root:
            return canonical_path(self.current_asset_root)
        if not self.current_project_path:
            return os.getcwd()
        return os.path.dirname(os.path.abspath(self.current_project_path))

    def _snapshot_runtime_state(self):
        return {
            "project_data": copy.deepcopy(self.project_data),
            "current_project_path": self.current_project_path,
            "current_storage_backend": self.current_storage_backend,
            "current_database_path": self.current_database_path,
            "current_asset_root": self.current_asset_root,
            "legacy_json_write_enabled": self._legacy_json_write_enabled,
            "pending_project_data_version_id": self._pending_project_data_version_id,
            "pending_integrity_dirty_assets": set(self._pending_integrity_dirty_assets),
            "traceability_backfill_needed": self._traceability_backfill_needed,
            "volume_cleanup_warnings": copy.deepcopy(self.volume_cleanup_warnings),
            "volume_cleanup_warning_dirty_ids": set(
                self._volume_cleanup_warning_dirty_ids
            ),
        }

    def _restore_runtime_state(self, state):
        self.project_data = state["project_data"]
        self.current_project_path = state["current_project_path"]
        self.current_storage_backend = state["current_storage_backend"]
        self.current_database_path = state["current_database_path"]
        self.current_asset_root = state["current_asset_root"]
        self._legacy_json_write_enabled = state["legacy_json_write_enabled"]
        self._pending_project_data_version_id = state["pending_project_data_version_id"]
        self._pending_integrity_dirty_assets = state["pending_integrity_dirty_assets"]
        self._traceability_backfill_needed = state["traceability_backfill_needed"]
        self.volume_cleanup_warnings = state["volume_cleanup_warnings"]
        self._volume_cleanup_warning_dirty_ids = state[
            "volume_cleanup_warning_dirty_ids"
        ]

    def _remove_sqlite_artifacts(self, database_path):
        base = os.path.abspath(str(database_path or ""))
        for candidate in (base, f"{base}-wal", f"{base}-shm"):
            try:
                if os.path.exists(candidate):
                    os.remove(candidate)
            except OSError:
                pass

    def _default_sqlite_paths_for_new_project(self, project_dir):
        directory = os.path.abspath(str(project_dir))
        return (
            os.path.join(directory, "project.tif_sqlite_manifest.json"),
            os.path.join(directory, "project.taxamask_tif.sqlite"),
        )

    def _create_sqlite_project_storage(self, name, project_dir):
        from .tif_sqlite_schema import create_tif_project_database

        manifest_path, database_path = self._default_sqlite_paths_for_new_project(project_dir)
        if os.path.exists(manifest_path):
            raise FileExistsError(manifest_path)
        if any(os.path.exists(candidate) for candidate in (database_path, f"{database_path}-wal", f"{database_path}-shm")):
            raise FileExistsError(database_path)

        conn = None
        manifest_owned = False
        try:
            conn = create_tif_project_database(database_path)
            conn.close()
            conn = None
            manifest_owned = True
            write_project_manifest(
                manifest_path,
                TIF_PROJECT_TYPE,
                self.project_data.get("name", name or "Untitled TIF Project"),
                database_path,
                extra={
                    "tif_asset_root": ".",
                    "created_as": "sqlite_default",
                },
            )
            self.current_project_path = canonical_path(manifest_path)
            self.current_database_path = canonical_path(database_path)
            self.current_storage_backend = SQLITE_BACKEND
            self.current_asset_root = canonical_path(project_dir)
            self.save_project()
            return self.current_project_path
        except Exception:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            if manifest_owned:
                try:
                    os.remove(manifest_path)
                except OSError:
                    pass
            self._remove_sqlite_artifacts(database_path)
            self.current_storage_backend = LEGACY_JSON_BACKEND
            self.current_database_path = ""
            self.current_asset_root = ""
            self._legacy_json_write_enabled = False
            raise

    def create_project(self, name, project_dir, project_id=None, storage_backend=SQLITE_BACKEND):
        previous_state = self._snapshot_runtime_state()
        try:
            return self._create_project_in_place(
                name,
                project_dir,
                project_id=project_id,
                storage_backend=storage_backend,
            )
        except Exception:
            self._restore_runtime_state(previous_state)
            raise

    def _create_project_in_place(self, name, project_dir, project_id=None, storage_backend=SQLITE_BACKEND):
        os.makedirs(project_dir, exist_ok=True)
        self.project_data = _default_project_data(name=name, project_id=project_id)
        self._pending_project_data_version_id = ""
        self._pending_integrity_dirty_assets = set()
        self._traceability_backfill_needed = False
        self.volume_cleanup_warnings = []
        self._volume_cleanup_warning_dirty_ids = set()
        if storage_backend == SQLITE_BACKEND:
            return self._create_sqlite_project_storage(name, project_dir)
        if storage_backend not in (LEGACY_JSON_BACKEND, "json"):
            raise ValueError(f"unsupported_tif_project_storage_backend:{storage_backend}")
        self.current_project_path = canonical_path(os.path.join(project_dir, DEFAULT_TIF_PROJECT_FILENAME))
        self.current_storage_backend = LEGACY_JSON_BACKEND
        self.current_database_path = ""
        self.current_asset_root = ""
        self._legacy_json_write_enabled = True
        self.save_project()
        return self.current_project_path

    def load_project(self, path):
        previous_state = self._snapshot_runtime_state()
        try:
            return self._load_project_in_place(path)
        except Exception:
            self._restore_runtime_state(previous_state)
            raise

    def _load_project_in_place(self, path):
        self._pending_project_data_version_id = ""
        self._pending_integrity_dirty_assets = set()
        self.volume_cleanup_warnings = []
        self._volume_cleanup_warning_dirty_ids = set()
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("tif_project_json_not_object")
        if self._is_sqlite_manifest_payload(payload):
            from .tif_sqlite_loader import load_tif_sqlite_project_manifest

            loaded_sqlite = load_tif_sqlite_project_manifest(path)
            self.current_project_path = canonical_path(path)
            self.project_data = self._normalize_loaded_project_data(loaded_sqlite["project_data"])
            self.current_storage_backend = SQLITE_BACKEND
            self.current_database_path = canonical_path(loaded_sqlite.get("database_path", ""))
            self._legacy_json_write_enabled = False
            manifest = loaded_sqlite.get("manifest", {}) if isinstance(loaded_sqlite.get("manifest"), dict) else {}
            asset_root = str(manifest.get("tif_asset_root") or "").strip()
            if asset_root:
                if os.path.isabs(asset_root):
                    self.current_asset_root = canonical_path(asset_root)
                else:
                    self.current_asset_root = canonical_path(os.path.join(os.path.dirname(canonical_path(path)), asset_root))
            else:
                self.current_asset_root = os.path.dirname(canonical_path(path))
            if self._traceability_backfill_needed:
                self.save_project()
                self._traceability_backfill_needed = False
            self._load_volume_cleanup_warnings()
            return self.project_data
        self.current_storage_backend = LEGACY_JSON_BACKEND
        self.current_database_path = ""
        self.current_asset_root = ""
        self._legacy_json_write_enabled = False
        if payload.get("schema_version") != TIF_PROJECT_SCHEMA_VERSION:
            raise ValueError(f"unsupported_tif_project_schema:{payload.get('schema_version')}")
        if payload.get("project_type") != TIF_PROJECT_TYPE:
            raise ValueError(f"not_tif_volume_project:{payload.get('project_type')}")
        self.current_project_path = canonical_path(path)
        self.project_data = self._normalize_loaded_project_data(payload)
        self._load_volume_cleanup_warnings()
        return self.project_data

    def _is_sqlite_manifest_payload(self, payload):
        return (
            isinstance(payload, dict)
            and payload.get("schema_version") == PROJECT_MANIFEST_SCHEMA_VERSION
            and payload.get("storage_backend") == SQLITE_BACKEND
        )

    def is_sqlite_project(self):
        return getattr(self, "current_storage_backend", "json") == SQLITE_BACKEND

    def enable_legacy_json_writes_for_compatibility(self, enabled=True):
        self._legacy_json_write_enabled = bool(enabled)

    def _normalize_loaded_project_data(self, payload):
        self._traceability_backfill_needed = ensure_project_traceability(
            payload, PROJECT_KIND_TIF
        )
        specimens = payload.get("specimens", [])
        if not isinstance(specimens, list):
            raise ValueError("tif_project_specimens_not_list")
        payload["models"] = [
            self._normalize_model_record(item)
            for item in (payload.get("models", []) if isinstance(payload.get("models", []), list) else [])
            if isinstance(item, dict)
        ]
        payload["runs"] = [
            self._normalize_run_record(item)
            for item in (payload.get("runs", []) if isinstance(payload.get("runs", []), list) else [])
            if isinstance(item, dict)
        ]
        payload["label_schemas"] = [
            self._normalize_label_schema(item)
            for item in (payload.get("label_schemas", []) if isinstance(payload.get("label_schemas", []), list) else [])
            if isinstance(item, dict)
        ]
        payload["part_user_tags"] = [
            self._normalize_part_user_tag(item, index)
            for index, item in enumerate(payload.get("part_user_tags", []) if isinstance(payload.get("part_user_tags", []), list) else [])
            if isinstance(item, dict)
        ]
        payload.setdefault("view_settings", {})
        payload.setdefault("updated_at", payload.get("created_at", _now_iso()))
        for specimen in specimens:
            if isinstance(specimen, dict):
                specimen["metadata"] = self._normalize_specimen_metadata(specimen)
                specimen["parts"] = self._normalize_parts(specimen)
                specimen["part_rois"] = self._normalize_part_rois(specimen)
        return payload

    def save_project(self):
        if not self.current_project_path:
            raise ValueError("tif_project_path_not_set")
        pending_data_version_id = self._pending_project_data_version_id
        pending_dirty_assets = set(
            getattr(self, "_pending_integrity_dirty_assets", set())
        )
        self.project_data["updated_at"] = _now_iso()
        try:
            if self.is_sqlite_project():
                from .tif_sqlite_writer import flush_tif_project_changes

                result = flush_tif_project_changes(
                    self, project_data_version_id=pending_data_version_id or None
                )
            else:
                if not getattr(self, "_legacy_json_write_enabled", False):
                    raise RuntimeError("legacy_tif_json_project_is_read_only; migrate to SQLite or export a legacy JSON copy")
                project_path = os.path.abspath(self.current_project_path)
                os.makedirs(os.path.dirname(project_path), exist_ok=True)
                self._backup_current_project_file(project_path)
                result = atomic_write_json(
                    project_path,
                    self.legacy_json_payload(project_path),
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception:
            raise
        resolved_data_version_id = str(
            (result or {}).get("data_version_id")
            if isinstance(result, dict)
            else ""
        )
        if resolved_data_version_id:
            self.project_data["project_data_version_id"] = resolved_data_version_id
        if pending_data_version_id:
            self._pending_project_data_version_id = ""
        self._pending_integrity_dirty_assets.difference_update(
            pending_dirty_assets
        )
        return result

    def _mark_manual_truth_data_changed(self):
        if not self._pending_project_data_version_id:
            self._pending_project_data_version_id = new_project_data_version_id()
        return self._pending_project_data_version_id

    def _mark_integrity_asset_dirty(self, owner_key, role):
        clean_key = str(owner_key or "").strip()
        clean_role = str(role or "").strip()
        if not clean_key or not clean_role:
            raise ValueError("integrity_dirty_asset_identity_required")
        self._pending_integrity_dirty_assets.add((clean_key, clean_role))
        return self._mark_manual_truth_data_changed()

    def integrity_registry_state(self):
        if not self.is_sqlite_project():
            return {"status": "legacy_read_only"}
        from .project_integrity_registry import registry_state
        from .sqlite_storage import connect_sqlite_database

        connection = connect_sqlite_database(self.current_database_path)
        try:
            return registry_state(connection)
        finally:
            connection.close()

    def initialize_integrity_baseline(
        self,
        *,
        legacy_truth_attestation=False,
        note="",
        progress_callback=None,
        cancel_check=None,
    ):
        from .tif_integrity_bridge import register_tif_project_baseline

        self.save_project()
        return register_tif_project_baseline(
            self,
            legacy_truth_attestation=legacy_truth_attestation,
            note=note,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )

    def _relative_to_project_path(self, path, project_path):
        text = str(path or "").strip()
        if not text:
            return ""
        if os.path.isabs(text):
            absolute = os.path.abspath(os.path.normpath(text))
        else:
            absolute = self.to_absolute(text)
        try:
            target_dir = os.path.dirname(os.path.abspath(project_path or self.current_project_path or "")) or "."
            return os.path.relpath(absolute, target_dir).replace("\\", "/")
        except ValueError:
            return absolute

    def _rebase_volume_record_paths(self, record, project_path):
        if not isinstance(record, dict):
            return record
        for key in ("path", "metadata_path", "preview_path"):
            if record.get(key):
                record[key] = self._relative_to_project_path(record.get(key), project_path)
        return record

    def legacy_json_payload(self, project_path=None):
        target_project_path = os.path.abspath(str(project_path or self.current_project_path or DEFAULT_TIF_PROJECT_FILENAME))
        payload = json.loads(json.dumps(self.project_data, ensure_ascii=False))
        payload["label_schemas"] = [
            self._normalize_label_schema(item)
            for item in payload.get("label_schemas", []) if isinstance(item, dict)
        ]
        payload["part_user_tags"] = [
            self._normalize_part_user_tag(item, index)
            for index, item in enumerate(payload.get("part_user_tags", []) if isinstance(payload.get("part_user_tags"), list) else [])
            if isinstance(item, dict)
        ]
        for specimen in payload.get("specimens", []) if isinstance(payload.get("specimens"), list) else []:
            if not isinstance(specimen, dict):
                continue
            for key in ("metadata_ref", "material_map"):
                if specimen.get(key):
                    specimen[key] = self._relative_to_project_path(specimen.get(key), target_project_path)
            self._rebase_volume_record_paths(specimen.get("working_volume"), target_project_path)
            labels = specimen.get("labels", {})
            if isinstance(labels, dict):
                for role in ("manual_truth", "working_edit", "raw_ai_prediction_backup"):
                    self._rebase_volume_record_paths(labels.get(role), target_project_path)
                for draft in labels.get("model_drafts", []) if isinstance(labels.get("model_drafts"), list) else []:
                    self._rebase_volume_record_paths(draft, target_project_path)
            for part in specimen.get("parts", []) if isinstance(specimen.get("parts"), list) else []:
                if not isinstance(part, dict):
                    continue
                self._rebase_volume_record_paths(part.get("image"), target_project_path)
                self._rebase_volume_record_paths(part.get("mask"), target_project_path)
                for key in ("contours_path", "extraction_path"):
                    if part.get(key):
                        part[key] = self._relative_to_project_path(part.get(key), target_project_path)
                metadata = part.get("metadata", {})
                if isinstance(metadata, dict):
                    for reslice in metadata.get("local_axis_reslices", []) if isinstance(metadata.get("local_axis_reslices"), list) else []:
                        if not isinstance(reslice, dict):
                            continue
                        for key in ("image_path", "mask_path", "metadata_path", "preview_path"):
                            if reslice.get(key):
                                reslice[key] = self._relative_to_project_path(reslice.get(key), target_project_path)
                        reslice_labels = reslice.get("labels", {})
                        if isinstance(reslice_labels, dict):
                            for role in ("manual_truth", "editable_ai_result", "raw_ai_prediction_backup"):
                                self._rebase_volume_record_paths(reslice_labels.get(role), target_project_path)
                part_labels = part.get("labels", {})
                if isinstance(part_labels, dict):
                    for role in ("manual_truth", "editable_ai_result", "raw_ai_prediction_backup"):
                        self._rebase_volume_record_paths(part_labels.get(role), target_project_path)
        for model in payload.get("models", []) if isinstance(payload.get("models"), list) else []:
            if not isinstance(model, dict):
                continue
            for key in ("model_path", "model_manifest", "training_manifest_path"):
                if model.get(key):
                    model[key] = self._relative_to_project_path(model.get(key), target_project_path)
        for run in payload.get("runs", []) if isinstance(payload.get("runs"), list) else []:
            if not isinstance(run, dict):
                continue
            for key in ("run_dir", "contract_json", "result_json"):
                if run.get(key):
                    run[key] = self._relative_to_project_path(run.get(key), target_project_path)
            for artifact in run.get("artifacts", []) if isinstance(run.get("artifacts"), list) else []:
                if isinstance(artifact, dict) and artifact.get("path"):
                    artifact["path"] = self._relative_to_project_path(artifact.get("path"), target_project_path)
        return payload

    def _project_sidecar_stem(self, project_path=None):
        path = os.path.abspath(project_path or self.current_project_path or "")
        stem, _ext = os.path.splitext(os.path.basename(path))
        return stem or "project"

    def _project_backup_dir(self, project_path=None):
        path = os.path.abspath(project_path or self.current_project_path or "")
        if not path:
            return ""
        return os.path.join(os.path.dirname(path), f"{self._project_sidecar_stem(path)}.project_backups")

    def _backup_current_project_file(self, project_path):
        backup_dir = self._project_backup_dir(project_path)
        if not backup_dir:
            return ""
        try:
            return backup_file(
                project_path,
                backup_dir,
                stem=self._project_sidecar_stem(project_path),
                suffix=".json.bak",
                limit=TIF_PROJECT_BACKUP_LIMIT,
                min_interval_seconds=TIF_PROJECT_BACKUP_MIN_INTERVAL_SECONDS,
            )
        except Exception as exc:
            print(f"TIF project backup skipped: {exc}")
            return ""

    def to_relative(self, path):
        if not path:
            return ""
        text = str(path)
        if not os.path.isabs(text):
            return text.replace("\\", "/")
        try:
            return os.path.relpath(text, self.project_dir).replace("\\", "/")
        except ValueError:
            return text

    def to_absolute(self, path):
        if not path:
            return ""
        text = str(path)
        if os.path.isabs(text):
            return os.path.normpath(text)
        return os.path.normpath(os.path.join(self.project_dir, text))

    def _require_guard(self, result, prefix):
        if result:
            return result
        reason = getattr(result, "reason", "denied")
        details = getattr(result, "details", {})
        raise ValueError(f"{prefix}:{reason}:{details}")

    def _ensure_project_write_allowed(
        self,
        target_path,
        *,
        source_path="",
        source_role="",
        target_role="",
        operation="",
        audit_metadata=None,
        allow_overwrite=False,
    ):
        intent = WriteIntent(
            target_path=str(target_path or ""),
            project_root=self.project_dir,
            source_path=str(source_path or ""),
            source_role=str(source_role or ""),
            target_role=str(target_role or ""),
            operation=str(operation or ""),
            audit_metadata=dict(audit_metadata or {}) if isinstance(audit_metadata, dict) else {},
            allow_overwrite=bool(allow_overwrite),
            allowed_roots=(self.project_dir,),
            protected_paths=(),
        )
        return ensure_write_allowed(intent)

    def _apply_project_mutation_transaction(self, callback, *, save=True):
        project_snapshot = copy.deepcopy(self.project_data)
        pending_version_snapshot = self._pending_project_data_version_id
        pending_assets_snapshot = set(self._pending_integrity_dirty_assets)
        try:
            result = callback()
            self._mark_manual_truth_data_changed()
            if save:
                self.save_project()
            return result
        except Exception:
            self.project_data = project_snapshot
            self._pending_project_data_version_id = pending_version_snapshot
            self._pending_integrity_dirty_assets = pending_assets_snapshot
            raise

    @property
    def volume_cleanup_warning_path(self):
        if not self.current_project_path:
            return ""
        return os.path.join(
            self.project_dir,
            TIF_VOLUME_CLEANUP_WARNING_RELATIVE_PATH,
        )

    @staticmethod
    def _bounded_cleanup_warning_text(value, limit):
        text = str(value or "")
        if len(text) <= limit:
            return text
        return f"{text[: max(0, limit - 14)]}...<truncated>"

    def _cleanup_warning_path_reference(self, path):
        text = str(path or "").strip()
        if not text:
            return ""

        def external_reference(candidate=""):
            digest_source = str(candidate or text).replace("\\", "/")
            basename = digest_source.rstrip("/").rsplit("/", 1)[-1]
            safe_basename = _safe_record_id(basename, "path")[:96]
            digest = hashlib.sha256(
                digest_source.encode("utf-8", errors="surrogatepass")
            ).hexdigest()
            return f"external_path_{safe_basename}_sha256_{digest}"

        windows_drive, _windows_tail = ntpath.splitdrive(text)
        if text.startswith(("~/", "~\\")) or (
            windows_drive and not ntpath.isabs(text)
        ):
            return external_reference()

        if not self.current_project_path:
            return external_reference()

        # Treat Windows paths as paths even when a sidecar is opened on POSIX.
        # This prevents a foreign absolute path from being mistaken for a safe
        # project-relative filename after a project is moved across platforms.
        if os.name != "nt":
            if windows_drive or text.startswith("\\"):
                return external_reference()

        native_text = text.replace("\\", os.sep).replace("/", os.sep)
        candidate = ""
        try:
            project_root = canonical_path(self.project_dir)
            if not project_root:
                return external_reference()
            candidate = canonical_path(
                native_text
                if os.path.isabs(native_text)
                else os.path.join(project_root, native_text)
            )
            common = os.path.commonpath([project_root, candidate])
            if os.path.normcase(common) != os.path.normcase(project_root):
                return external_reference(candidate)
            relative = os.path.relpath(candidate, project_root).replace("\\", "/")
            if (
                os.path.isabs(relative)
                or relative == ".."
                or relative.startswith("../")
            ):
                return external_reference(candidate)
            return self._bounded_cleanup_warning_text(relative, 4096)
        except (OSError, TypeError, ValueError):
            return external_reference(candidate)

    @staticmethod
    def _looks_like_absolute_path(value):
        text = str(value or "").strip()
        if not text:
            return False
        drive, _tail = ntpath.splitdrive(text)
        native_text = text.replace("\\", os.sep).replace("/", os.sep)
        normalized = text.replace("\\", "/")
        return (
            bool(drive)
            or ntpath.isabs(text)
            or os.path.isabs(native_text)
            or normalized.startswith("../")
            or normalized.startswith("~/")
        )

    def _cleanup_warning_error_text(
        self,
        value,
        *,
        target_path="",
        rollback_path="",
    ):
        text = str(value or "")
        known_paths = []
        for candidate in (target_path, rollback_path):
            raw = str(candidate or "").strip()
            if not raw:
                continue
            reference = self._cleanup_warning_path_reference(raw)
            variants = {raw, raw.replace("\\", "/"), raw.replace("/", "\\")}
            try:
                canonical = canonical_path(raw)
            except (OSError, TypeError, ValueError):
                canonical = ""
            if canonical:
                variants.update(
                    {
                        canonical,
                        canonical.replace("\\", "/"),
                        canonical.replace("/", "\\"),
                    }
                )
            for variant in sorted(variants, key=len, reverse=True):
                if variant:
                    known_paths.append((variant, reference))
        for raw, reference in sorted(
            known_paths,
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            flags = re.IGNORECASE if ntpath.splitdrive(raw)[0] else 0
            text = re.sub(re.escape(raw), reference, text, flags=flags)

        quoted_path = re.compile(
            r"(?P<quote>['\"])(?P<value>.*?)(?P=quote)"
        )

        def replace_quoted(match):
            candidate = match.group("value")
            if not self._looks_like_absolute_path(candidate):
                return match.group(0)
            quote = match.group("quote")
            reference = self._cleanup_warning_path_reference(candidate)
            return f"{quote}{reference}{quote}"

        text = quoted_path.sub(replace_quoted, text)

        # Unknown unquoted paths can legally contain spaces. Redact the whole
        # span up to an unambiguous record delimiter. If no delimiter exists,
        # the ambiguous trailing text is intentionally redacted with the path.
        windows_token = re.compile(
            r"(?<![A-Za-z0-9_])(?:[A-Za-z]:[\\/]|\\{1,2})[^\r\n,;'\"<>]+"
        )
        posix_token = re.compile(r"(?<![:A-Za-z0-9_.~])/(?:[^\r\n,;'\"<>]+)")
        relative_external_token = re.compile(
            r"(?<![A-Za-z0-9_])(?:\.\.[\\/]|~[\\/]|[A-Za-z]:(?![\\/]))"
            r"[^\r\n,;'\"<>]+"
        )
        text = windows_token.sub(
            lambda match: self._cleanup_warning_path_reference(match.group(0)),
            text,
        )
        text = posix_token.sub(
            lambda match: self._cleanup_warning_path_reference(match.group(0)),
            text,
        )
        text = relative_external_token.sub(
            lambda match: self._cleanup_warning_path_reference(match.group(0)),
            text,
        )
        return self._bounded_cleanup_warning_text(text, 4096)

    def _normalize_volume_cleanup_warning(self, warning):
        source = warning if isinstance(warning, dict) else {}
        target_path = source.get("target_path")
        rollback_path = source.get("rollback_path")
        record = {
            "recorded_at": self._bounded_cleanup_warning_text(
                source.get("recorded_at") or _now_iso(), 64
            ),
            "status": "committed_cleanup_incomplete",
            "data_commit_status": "committed",
            "cleanup_scope": "rollback_backup_only",
            "operation": self._bounded_cleanup_warning_text(
                source.get("operation") or "volume_replacement_commit", 160
            ),
            "role": self._bounded_cleanup_warning_text(source.get("role"), 160),
            "target_path": self._cleanup_warning_path_reference(
                target_path
            ),
            "rollback_path": self._cleanup_warning_path_reference(
                rollback_path
            ),
            "error": self._cleanup_warning_error_text(
                source.get("error"),
                target_path=target_path,
                rollback_path=rollback_path,
            ),
        }
        warning_id = str(source.get("warning_id") or "").strip()
        if (
            not warning_id
            or len(warning_id) > 160
            or not re.fullmatch(r"[A-Za-z0-9._-]+", warning_id)
        ):
            identity_source = {
                key: str(source.get(key) or "")
                for key in (
                    "recorded_at",
                    "operation",
                    "role",
                    "target_path",
                    "rollback_path",
                    "error",
                )
            }
            digest = hashlib.sha256(
                json.dumps(
                    identity_source,
                    sort_keys=True,
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
            warning_id = f"cleanup_warning_legacy_{digest}"
        record["warning_id"] = warning_id
        return record

    def _merge_volume_cleanup_warnings(self, *warning_groups):
        merged = {}
        for group in warning_groups:
            for item in group or []:
                if not isinstance(item, dict):
                    continue
                warning = self._normalize_volume_cleanup_warning(item)
                warning_id = warning["warning_id"]
                if warning_id in merged:
                    del merged[warning_id]
                merged[warning_id] = warning
        return list(merged.values())[-TIF_VOLUME_CLEANUP_WARNING_LIMIT:]

    def _validated_volume_cleanup_warning_payload(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("maintenance_warning_payload_not_object")
        if (
            payload.get("schema_version")
            != TIF_VOLUME_CLEANUP_WARNING_SCHEMA_VERSION
        ):
            raise ValueError("maintenance_warning_schema_unsupported")
        if payload.get("record_type") not in {
            None,
            "tif_volume_cleanup_maintenance_warnings",
        }:
            raise ValueError("maintenance_warning_record_type_unsupported")
        stored_project_id = payload.get("project_id")
        current_project_id = self.project_data.get("project_id")
        if (
            not isinstance(current_project_id, str)
            or not current_project_id.strip()
        ):
            raise ValueError("maintenance_warning_current_project_id_missing")
        if (
            not isinstance(stored_project_id, str)
            or not stored_project_id.strip()
        ):
            raise ValueError("maintenance_warning_stored_project_id_missing")
        if stored_project_id != current_project_id:
            raise ValueError("maintenance_warning_project_mismatch")
        records = payload.get("warnings", [])
        if not isinstance(records, list):
            raise ValueError("maintenance_warning_records_not_list")
        return self._merge_volume_cleanup_warnings(
            records[-TIF_VOLUME_CLEANUP_WARNING_LIMIT:]
        )

    def _runtime_log_volume_cleanup_warning(self, event, warning, **extra):
        try:
            try:
                from AntSleap.app_runtime import runtime_log_event
            except ImportError:
                from app_runtime import runtime_log_event
            fields = dict(warning or {})
            fields.update(extra)
            runtime_log_event(event, **fields)
        except Exception:
            return

    def _persist_volume_cleanup_warnings(self):
        path = self.volume_cleanup_warning_path
        if not path:
            return ""
        pending_warnings = self._merge_volume_cleanup_warnings(
            self.volume_cleanup_warnings
        )
        self.volume_cleanup_warnings = pending_warnings
        self._volume_cleanup_warning_dirty_ids.intersection_update(
            warning["warning_id"] for warning in pending_warnings
        )
        try:
            current_project_id = self.project_data.get("project_id")
            if (
                not isinstance(current_project_id, str)
                or not current_project_id.strip()
            ):
                raise ValueError("maintenance_warning_current_project_id_missing")
            lock_path = f"{path}.lock"
            with AdvisoryFileLock(
                lock_path,
                trusted_root=self.project_dir,
                timeout=TIF_VOLUME_CLEANUP_WARNING_LOCK_TIMEOUT_SECONDS,
            ):
                persisted_warnings = []
                if os.path.lexists(path):
                    try:
                        persisted_payload = read_json_bounded_in_root(
                            path,
                            trusted_root=self.project_dir,
                            max_bytes=TIF_VOLUME_CLEANUP_WARNING_MAX_BYTES,
                        )
                        persisted_warnings = (
                            self._validated_volume_cleanup_warning_payload(
                                persisted_payload
                            )
                        )
                    except UnsafeFilesystemPath:
                        raise
                    except (UnicodeDecodeError, ValueError) as exc:
                        recovery_error = self._cleanup_warning_error_text(
                            f"{type(exc).__name__}: {exc}",
                            target_path=path,
                        )
                        isolate_regular_file_in_root(
                            path,
                            f"{path}.rejected",
                            trusted_root=self.project_dir,
                        )
                        self._runtime_log_volume_cleanup_warning(
                            "tif_volume_cleanup_warning_sidecar_isolated",
                            {},
                            error=recovery_error,
                            recovery_action="isolate_invalid_regular_sidecar",
                        )
                dirty_ids = set(self._volume_cleanup_warning_dirty_ids)
                new_pending_warnings = [
                    warning
                    for warning in pending_warnings
                    if warning["warning_id"] in dirty_ids
                ]
                warnings = self._merge_volume_cleanup_warnings(
                    persisted_warnings,
                    new_pending_warnings,
                )
                payload = {
                    "schema_version": TIF_VOLUME_CLEANUP_WARNING_SCHEMA_VERSION,
                    "record_type": "tif_volume_cleanup_maintenance_warnings",
                    "project_id": current_project_id,
                    "updated_at": _now_iso(),
                    "max_records": TIF_VOLUME_CLEANUP_WARNING_LIMIT,
                    "warnings": warnings,
                }
                atomic_write_json_in_root(
                    path,
                    payload,
                    trusted_root=self.project_dir,
                    max_bytes=TIF_VOLUME_CLEANUP_WARNING_MAX_BYTES,
                    indent=2,
                    ensure_ascii=False,
                )
                self.volume_cleanup_warnings = warnings
                self._volume_cleanup_warning_dirty_ids.difference_update(
                    warning["warning_id"] for warning in new_pending_warnings
                )
        except Exception as exc:
            return self._cleanup_warning_error_text(
                f"{type(exc).__name__}: {exc}",
                target_path=path,
            )
        return ""

    def _load_volume_cleanup_warnings(self):
        self.volume_cleanup_warnings = []
        self._volume_cleanup_warning_dirty_ids = set()
        path = self.volume_cleanup_warning_path
        if not path or not os.path.lexists(path):
            return []
        try:
            payload = read_json_bounded_in_root(
                path,
                trusted_root=self.project_dir,
                max_bytes=TIF_VOLUME_CLEANUP_WARNING_MAX_BYTES,
            )
            self.volume_cleanup_warnings = (
                self._validated_volume_cleanup_warning_payload(payload)
            )
        except Exception as exc:
            error = self._cleanup_warning_error_text(
                f"{type(exc).__name__}: {exc}",
                target_path=path,
            )
            _LOGGER.warning("Could not load TIF volume cleanup warnings: %s", error)
            self._runtime_log_volume_cleanup_warning(
                "tif_volume_cleanup_warning_load_failed",
                {},
                error=error,
            )
            self.volume_cleanup_warnings = []
        return self.volume_cleanup_warnings

    def _commit_volume_replacement_cleanup(self, replacement, *, operation, role=""):
        try:
            cleanup_error = str(replacement.commit() or "")
        except Exception as exc:
            cleanup_error = f"{type(exc).__name__}: {exc}"
        if not cleanup_error:
            return ""
        warning = self._normalize_volume_cleanup_warning(
            {
                "warning_id": f"cleanup_warning_{uuid.uuid4().hex}",
                "recorded_at": _now_iso(),
                "operation": str(operation or "volume_replacement_commit"),
                "role": str(
                    role
                    or (getattr(replacement, "metadata", {}) or {}).get("role", "")
                ),
                "target_path": str(getattr(replacement, "target", "") or ""),
                "rollback_path": str(
                    getattr(replacement, "rollback_path", "") or ""
                ),
                "error": cleanup_error,
            }
        )
        self.volume_cleanup_warnings.append(warning)
        self._volume_cleanup_warning_dirty_ids.add(warning["warning_id"])
        if len(self.volume_cleanup_warnings) > TIF_VOLUME_CLEANUP_WARNING_LIMIT:
            del self.volume_cleanup_warnings[:-TIF_VOLUME_CLEANUP_WARNING_LIMIT]
        self._runtime_log_volume_cleanup_warning(
            "tif_volume_replacement_cleanup_incomplete",
            warning,
        )
        try:
            persistence_error = self._persist_volume_cleanup_warnings()
        except Exception as exc:
            persistence_error = f"{type(exc).__name__}: {exc}"
        if persistence_error:
            _LOGGER.warning(
                "Could not persist TIF volume cleanup warning: %s",
                persistence_error,
            )
            self._runtime_log_volume_cleanup_warning(
                "tif_volume_cleanup_warning_persist_failed",
                warning,
                persistence_error=persistence_error,
            )
        _LOGGER.warning(
            "Volume replacement committed but backup cleanup was incomplete: %s",
            warning,
        )
        return cleanup_error

    def _apply_volume_replacement_transaction(
        self,
        source_path,
        target_path,
        callback,
        *,
        role,
        integrity_owner_key="",
        mark_manual_truth_changed=True,
        save=True,
        transactions=None,
    ):
        project_snapshot = copy.deepcopy(self.project_data) if transactions is None else None
        pending_version_snapshot = self._pending_project_data_version_id
        pending_assets_snapshot = set(self._pending_integrity_dirty_assets)
        replacement = begin_volume_sidecar_replacement(source_path, target_path, role=role)
        if transactions is not None:
            transactions.append(replacement)
        try:
            result = callback(replacement.metadata)
            if integrity_owner_key:
                self._mark_integrity_asset_dirty(integrity_owner_key, role)
            elif mark_manual_truth_changed:
                self._mark_manual_truth_data_changed()
            if save:
                self.save_project()
        except Exception as exc:
            if project_snapshot is not None:
                self.project_data = project_snapshot
            self._pending_project_data_version_id = pending_version_snapshot
            self._pending_integrity_dirty_assets = pending_assets_snapshot
            if transactions is None:
                try:
                    replacement.rollback()
                except Exception as rollback_exc:
                    raise RuntimeError(
                        f"volume_record_update_failed:{exc};rollback_failed:{rollback_exc}"
                    ) from exc
            raise
        if transactions is None:
            self._commit_volume_replacement_cleanup(
                replacement,
                operation="volume_replacement_commit",
                role=role,
            )
        return result

    def specimen_dir(self, specimen_id):
        return os.path.join("specimens", _safe_path_fragment(specimen_id))

    def part_dir(self, specimen_id, part_id):
        return os.path.join(self.specimen_dir(specimen_id), "parts", _safe_part_id(part_id)).replace("\\", "/")

    def create_specimen_scaffold(self, specimen_id, material_map=None, modality="unknown", metadata_ref="", display_name=""):
        clean_id = self._validate_new_specimen_id(specimen_id, require_storage_available=True)
        specimen_root = self.to_absolute(self.specimen_dir(clean_id))
        try:
            for rel in ("source/raw", "source/amira_original", "working", "labels/model_draft", "exports", "logs"):
                os.makedirs(os.path.join(specimen_root, rel), exist_ok=True)
            material_map_rel = os.path.join(self.specimen_dir(clean_id), "material_map.json").replace("\\", "/")
            write_material_map(self.to_absolute(material_map_rel), material_map or {}, source=(material_map or {}).get("source", "manual") if isinstance(material_map, dict) else "manual")
            specimen = self.add_specimen(
                clean_id,
                display_name=display_name or clean_id,
                metadata_ref=metadata_ref,
                modality=modality,
                material_map=material_map_rel,
                save=False,
            )
            self.save_project()
            return specimen
        except Exception:
            self.discard_specimen_scaffold(clean_id, save=False)
            raise

    def add_specimen(
        self,
        specimen_id,
        display_name="",
        metadata_ref="",
        modality="unknown",
        source=None,
        working_volume=None,
        labels=None,
        material_map="",
        review_status="not_started",
        train_ready=False,
        provenance=None,
        metadata=None,
        save=True,
    ):
        clean_id = self._validate_new_specimen_id(specimen_id)
        if review_status not in TIF_REVIEW_STATUSES:
            review_status = "not_started"

        specimen = {
            "specimen_id": clean_id,
            "display_name": str(display_name or clean_id),
            "metadata_ref": str(metadata_ref or ""),
            "modality": str(modality or "unknown"),
            "source": dict(source or {}),
            "working_volume": self._normalize_volume_record(working_volume),
            "labels": self._normalize_labels(labels),
            "material_map": self.to_relative(material_map),
            "review_status": review_status,
            "train_ready": bool(train_ready),
            "provenance": dict(provenance or {}),
            "metadata": dict(metadata or {}),
            "parts": [],
            "part_rois": [],
        }
        self.project_data.setdefault("specimens", []).append(specimen)
        self._mark_manual_truth_data_changed()
        if save:
            self.save_project()
        return specimen

    def get_specimen(self, specimen_id, default=None):
        clean_id = str(specimen_id or "").strip()
        for specimen in self.project_data.get("specimens", []):
            if specimen.get("specimen_id") == clean_id:
                return specimen
        return default

    def set_review_status(self, specimen_id, status, train_ready=None, save=True):
        if status not in TIF_REVIEW_STATUSES:
            raise ValueError(f"invalid_tif_review_status:{status}")
        specimen = self._require_specimen(specimen_id)
        specimen["review_status"] = status
        if train_ready is not None:
            specimen["train_ready"] = bool(train_ready)
        elif status == "train_ready":
            specimen["train_ready"] = True
        else:
            specimen["train_ready"] = False
        self._mark_manual_truth_data_changed()
        if save:
            self.save_project()
        return specimen

    def register_working_volume(self, specimen_id, path, shape_zyx, dtype, spacing_zyx=None, spacing_unit="unknown", orientation="unknown", fmt=VOLUME_SIDECAR_FORMAT, save=True, scale_verified=None):
        specimen = self._require_specimen(specimen_id)
        specimen["working_volume"] = self._volume_payload(
            path,
            shape_zyx,
            dtype,
            spacing_zyx,
            spacing_unit,
            orientation,
            fmt,
            scale_verified=scale_verified,
        )
        self._mark_integrity_asset_dirty(
            f"specimen.{specimen_id}.working", "source_volume"
        )
        if save:
            self.save_project()
        return specimen["working_volume"]

    def register_label_volume(
        self,
        specimen_id,
        role,
        path,
        shape_zyx,
        dtype,
        status="available",
        spacing_zyx=None,
        spacing_unit="unknown",
        orientation="unknown",
        fmt=VOLUME_SIDECAR_FORMAT,
        save=True,
        operation="register_existing_label_record",
        explicit_review=False,
        audit_metadata=None,
        scale_verified=None,
    ):
        if role not in {"manual_truth", "working_edit"}:
            raise ValueError(f"unsupported_label_role:{role}")
        guard = can_write_label_role(
            role,
            operation=operation or "register_existing_label_record",
            explicit_review=explicit_review,
            audit_metadata=audit_metadata,
            overwrite_existing=bool((path or "").strip()),
        )
        self._require_guard(guard, "tif_label_guard_denied")
        specimen = self._require_specimen(specimen_id)
        specimen["labels"][role] = self._volume_payload(
            path,
            shape_zyx,
            dtype,
            spacing_zyx,
            spacing_unit,
            orientation,
            fmt,
            scale_verified=scale_verified,
        )
        specimen["labels"][role]["status"] = str(status or "available")
        if role == "manual_truth":
            if explicit_review:
                specimen["labels"][role]["review_audit"] = (
                    self._manual_truth_review_audit(
                        specimen["labels"][role],
                        review_action=operation,
                        source_role="registered_manual_truth",
                        specimen_id=specimen_id,
                        part_id="",
                    )
                )
            self._mark_integrity_asset_dirty(
                f"specimen.{specimen_id}.manual_truth", "manual_truth"
            )
        if save:
            self.save_project()
        return specimen["labels"][role]

    def add_model_draft(self, specimen_id, path, shape_zyx, dtype, prediction_id, source_model="", spacing_zyx=None, spacing_unit="unknown", orientation="unknown", fmt=VOLUME_SIDECAR_FORMAT, save=True, scale_verified=None):
        specimen = self._require_specimen(specimen_id)
        draft = self._volume_payload(
            path,
            shape_zyx,
            dtype,
            spacing_zyx,
            spacing_unit,
            orientation,
            fmt,
            scale_verified=scale_verified,
        )
        draft.update(
            {
                "prediction_id": str(prediction_id or ""),
                "source_model": str(source_model or ""),
                "role": "model_draft",
                "status": "draft",
            }
        )
        specimen["labels"].setdefault("model_drafts", []).append(draft)
        if save:
            self.save_project()
        return draft

    def add_or_update_label_schema(self, schema_id, labels=None, user_defined_part_name="", display_name="", save=True):
        schema_id = _safe_record_id(schema_id, fallback="label_schema")
        schemas = self.project_data.setdefault("label_schemas", [])
        existing = None
        for schema in schemas:
            if isinstance(schema, dict) and str(schema.get("schema_id") or "") == schema_id:
                existing = schema
                break
        record = self._normalize_label_schema(
            {
                "schema_id": schema_id,
                "display_name": display_name or schema_id,
                "user_defined_part_name": user_defined_part_name,
                "labels": labels or [],
                "created_at": (existing or {}).get("created_at") or _now_iso(),
                "updated_at": _now_iso(),
            }
        )
        if existing is None:
            schemas.append(record)
        else:
            existing.clear()
            existing.update(record)
            record = existing
        self._mark_manual_truth_data_changed()
        if save:
            self.save_project()
        return record

    def export_label_schema(self, schema_id, output_path):
        schema = self.get_label_schema(schema_id, default=None)
        if schema is None:
            raise KeyError(f"label_schema_not_found:{schema_id}")
        record = self._normalize_label_schema(schema)
        if not record.get("labels"):
            raise ValueError(f"label_schema_empty:{schema_id}")
        payload = {
            "schema_version": TIF_LABEL_SCHEMA_EXPORT_SCHEMA_VERSION,
            "exported_at": _now_iso(),
            "source_project": {
                "project_id": str(self.project_data.get("project_id") or ""),
                "project_name": str(self.project_data.get("name") or ""),
            },
            "label_schema": record,
            "notes": [
                "TaxaMask TIF label schema export.",
                "Label IDs and colors are preserved so volume-segmentation training datasets remain comparable across projects.",
            ],
        }
        atomic_write_json(output_path, payload, indent=2, ensure_ascii=False)
        return payload

    def import_label_schema(self, path, *, schema_id=None, replace=True, save=True):
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("label_schema_import_root_not_object")
        if payload.get("schema_version") == TIF_LABEL_SCHEMA_EXPORT_SCHEMA_VERSION and isinstance(payload.get("label_schema"), dict):
            source = dict(payload.get("label_schema") or {})
        elif any(key in payload for key in ("schema_id", "labels", "user_defined_part_name")):
            source = dict(payload)
        else:
            raise ValueError(f"unsupported_label_schema_file:{payload.get('schema_version', '')}")
        if schema_id:
            source["schema_id"] = str(schema_id)
        record = self._normalize_label_schema(source)
        if not record.get("labels"):
            raise ValueError(f"label_schema_empty:{record.get('schema_id', '')}")
        schemas = self.project_data.setdefault("label_schemas", [])
        existing = self.get_label_schema(record.get("schema_id"), default=None)
        if existing is not None and not replace:
            raise FileExistsError(f"label_schema_exists:{record.get('schema_id')}")
        if existing is None:
            schemas.append(record)
        else:
            existing.clear()
            existing.update(record)
            record = existing
        record["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return record

    def get_label_schema(self, schema_id, default=None):
        wanted = str(schema_id or "").strip()
        for schema in self.project_data.get("label_schemas", []) or []:
            if isinstance(schema, dict) and str(schema.get("schema_id") or "") == wanted:
                return schema
        return default

    def label_schema_ids(self, schema_id):
        schema = self.get_label_schema(schema_id, default=None)
        if schema is None:
            return set()
        ids = set()
        for label in schema.get("labels", []) or []:
            if not isinstance(label, dict):
                continue
            try:
                ids.add(int(label.get("id")))
            except (TypeError, ValueError):
                continue
        ids.add(0)
        return ids

    def upsert_part_user_tag(self, tag_id, label="", color="#6B8AFD", order_index=None, save=True):
        tag_id = _safe_record_id(tag_id, fallback="tag")
        tags = self.project_data.setdefault("part_user_tags", [])
        existing = None
        for tag in tags:
            if isinstance(tag, dict) and str(tag.get("tag_id") or "") == tag_id:
                existing = tag
                break
        record = self._normalize_part_user_tag(
            {
                "tag_id": tag_id,
                "label": label or tag_id,
                "color": color or "#6B8AFD",
                "order_index": len(tags) if order_index is None else order_index,
                "created_at": (existing or {}).get("created_at") or _now_iso(),
                "updated_at": _now_iso(),
            },
            len(tags) if order_index is None else order_index,
        )
        if existing is None:
            tags.append(record)
        else:
            existing.clear()
            existing.update(record)
            record = existing
        tags.sort(key=lambda item: int((item or {}).get("order_index", 0)))
        if save:
            self.save_project()
        return record

    def set_part_user_tag_order(self, tag_ids, save=True):
        wanted = [str(item or "").strip() for item in (tag_ids or []) if str(item or "").strip()]
        tags = self.project_data.setdefault("part_user_tags", [])
        ordered = []
        seen = set()
        by_id = {
            str((tag or {}).get("tag_id") or ""): tag
            for tag in tags
            if isinstance(tag, dict) and str((tag or {}).get("tag_id") or "")
        }
        for tag_id in wanted:
            if tag_id in by_id and tag_id not in seen:
                ordered.append(by_id[tag_id])
                seen.add(tag_id)
        remaining = [
            tag for tag in tags
            if isinstance(tag, dict) and str((tag or {}).get("tag_id") or "") not in seen
        ]
        remaining.sort(key=lambda item: int((item or {}).get("order_index", 0)))
        ordered.extend(remaining)
        now = _now_iso()
        for index, tag in enumerate(ordered):
            tag["order_index"] = index
            tag["updated_at"] = now
        self.project_data["part_user_tags"] = ordered
        if save:
            self.save_project()
        return list(ordered)

    def delete_part_user_tag(self, tag_id, save=True):
        wanted = str(tag_id or "").strip()
        if not wanted:
            return False
        tags = self.project_data.setdefault("part_user_tags", [])
        original_count = len(tags)
        self.project_data["part_user_tags"] = [
            tag for tag in tags
            if not (isinstance(tag, dict) and str(tag.get("tag_id") or "") == wanted)
        ]
        deleted = len(self.project_data["part_user_tags"]) != original_count
        if not deleted:
            return False
        self.set_part_user_tag_order([str((tag or {}).get("tag_id") or "") for tag in self.project_data.get("part_user_tags", [])], save=False)
        for specimen in self.project_data.get("specimens", []) or []:
            if not isinstance(specimen, dict):
                continue
            for part in specimen.get("parts", []) or []:
                if not isinstance(part, dict):
                    continue
                existing_tags = [str(item) for item in (part.get("user_tags") or [])]
                clean_tags = [item for item in existing_tags if item != wanted]
                if clean_tags != existing_tags:
                    part["user_tags"] = clean_tags
                    part["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return True

    def set_part_user_tags(self, specimen_id, part_id, tag_ids, save=True):
        part = self._require_part(specimen_id, part_id)
        known = {
            str(tag.get("tag_id") or "")
            for tag in self.project_data.get("part_user_tags", []) or []
            if isinstance(tag, dict)
        }
        clean = []
        for tag_id in tag_ids or []:
            text = str(tag_id or "").strip()
            if text and text in known and text not in clean:
                clean.append(text)
        part["user_tags"] = clean
        part["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return clean

    def set_part_training_metadata(
        self,
        specimen_id,
        part_id,
        *,
        user_defined_part_name=None,
        label_schema_id=None,
        active_reslice_id=None,
        system_status=None,
        opened_for_review=None,
        save=True,
    ):
        part = self._require_part(specimen_id, part_id)
        training = part.setdefault("training", {})
        if user_defined_part_name is not None:
            training["user_defined_part_name"] = str(user_defined_part_name or "")
        if label_schema_id is not None:
            training["label_schema_id"] = str(label_schema_id or "")
        if active_reslice_id is not None:
            training["active_reslice_id"] = str(active_reslice_id or "")
        if system_status is not None:
            clean_status = str(system_status or "").strip()
            if clean_status not in TIF_PART_SYSTEM_STATUSES:
                raise ValueError(f"invalid_tif_part_system_status:{clean_status}")
            training["system_status"] = clean_status
        if opened_for_review is not None:
            training["opened_for_review"] = bool(opened_for_review)
        training["updated_at"] = _now_iso()
        part["updated_at"] = _now_iso()
        if any(
            value is not None
            for value in (
                user_defined_part_name,
                label_schema_id,
                active_reslice_id,
                system_status,
            )
        ):
            self._mark_manual_truth_data_changed()
        if save:
            self.save_project()
        return training

    def register_part_label_volume(
        self,
        specimen_id,
        part_id,
        role,
        path,
        shape_zyx,
        dtype,
        status="available",
        prediction_id="",
        source_model="",
        spacing_zyx=None,
        spacing_unit="unknown",
        orientation="unknown",
        fmt=VOLUME_SIDECAR_FORMAT,
        save=True,
        operation="register_existing_label_record",
        explicit_review=False,
        audit_metadata=None,
        scale_verified=None,
    ):
        role = str(role or "").strip()
        if role not in TIF_PART_LABEL_ROLES:
            raise ValueError(f"unsupported_part_label_role:{role}")
        guard = can_write_label_role(
            role,
            operation=operation or "register_existing_label_record",
            explicit_review=explicit_review,
            audit_metadata=audit_metadata,
            overwrite_existing=bool((path or "").strip()),
        )
        self._require_guard(guard, "tif_label_guard_denied")
        part = self._require_part(specimen_id, part_id)
        labels = part.setdefault("labels", self._normalize_part_labels(None))
        record = self._volume_payload(
            path,
            shape_zyx,
            dtype,
            spacing_zyx,
            spacing_unit,
            orientation,
            fmt,
            scale_verified=scale_verified,
        )
        record["role"] = role
        record["status"] = str(status or "available")
        if prediction_id:
            record["prediction_id"] = str(prediction_id)
        if source_model:
            record["source_model"] = str(source_model)
        if role == "manual_truth":
            labels["manual_truth"] = record
            if explicit_review:
                record["review_audit"] = self._manual_truth_review_audit(
                    record,
                    review_action=operation,
                    source_role="registered_manual_truth",
                    specimen_id=specimen_id,
                    part_id=part_id,
                )
            self._mark_integrity_asset_dirty(
                f"part.{specimen_id}.{part_id}.manual_truth", "manual_truth"
            )
            self.set_part_training_metadata(
                specimen_id,
                part_id,
                system_status="verified_train_ready",
                save=False,
            )
        elif role == "editable_ai_result":
            labels["editable_ai_result"] = record
            self.set_part_training_metadata(
                specimen_id,
                part_id,
                system_status="predicted_pending_review",
                save=False,
            )
        else:
            labels["raw_ai_prediction_backup"] = record
        part["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return record

    def _part_label_container(self, specimen_id, part_id, reslice_id=""):
        part = self._require_part(specimen_id, part_id)
        clean_reslice_id = str(reslice_id or "").strip()
        if clean_reslice_id:
            reslice = self.get_part_reslice(specimen_id, part_id, clean_reslice_id, default=None)
            if reslice is None:
                raise KeyError(f"unknown_part_reslice_id:{specimen_id}:{part_id}:{clean_reslice_id}")
            return reslice.setdefault("labels", self._normalize_part_labels(reslice.get("labels"))), part, reslice
        return part.setdefault("labels", self._normalize_part_labels(None)), part, None

    def part_label_record(self, specimen_id, part_id, role="manual_truth", reslice_id=""):
        role = str(role or "").strip()
        if role not in TIF_PART_LABEL_ROLES:
            return {}
        try:
            labels, _part, _reslice = self._part_label_container(specimen_id, part_id, reslice_id)
        except Exception:
            return {}
        return (labels or {}).get(role) or {}

    def register_part_reslice_label_volume(
        self,
        specimen_id,
        part_id,
        reslice_id,
        role,
        path,
        shape_zyx,
        dtype,
        status="available",
        prediction_id="",
        source_model="",
        spacing_zyx=None,
        spacing_unit="unknown",
        orientation="local_axis_reslice",
        fmt=VOLUME_SIDECAR_FORMAT,
        save=True,
        operation="register_existing_label_record",
        explicit_review=False,
        audit_metadata=None,
        scale_verified=None,
    ):
        role = str(role or "").strip()
        if role not in TIF_PART_LABEL_ROLES:
            raise ValueError(f"unsupported_part_label_role:{role}")
        guard = can_write_label_role(
            role,
            operation=operation or "register_existing_label_record",
            explicit_review=explicit_review,
            audit_metadata=audit_metadata,
            overwrite_existing=bool((path or "").strip()),
        )
        self._require_guard(guard, "tif_label_guard_denied")
        labels, part, reslice = self._part_label_container(specimen_id, part_id, reslice_id)
        if reslice is None:
            raise ValueError("reslice_id_required_for_reslice_label")
        record = self._volume_payload(
            path,
            shape_zyx,
            dtype,
            spacing_zyx,
            spacing_unit,
            orientation,
            fmt,
            scale_verified=scale_verified,
        )
        record["role"] = role
        record["status"] = str(status or "available")
        record["coordinate_space"] = "local_axis_reslice_voxel_zyx"
        record["reslice_id"] = str(reslice_id or "")
        if prediction_id:
            record["prediction_id"] = str(prediction_id)
        if source_model:
            record["source_model"] = str(source_model)
        labels[role] = record
        reslice["updated_at"] = _now_iso()
        part["updated_at"] = _now_iso()
        if role == "manual_truth":
            if explicit_review:
                record["review_audit"] = self._manual_truth_review_audit(
                    record,
                    review_action=operation,
                    source_role="registered_manual_truth",
                    specimen_id=specimen_id,
                    part_id=part_id,
                    reslice_id=reslice_id,
                )
            self._mark_integrity_asset_dirty(
                f"reslice.{specimen_id}.{part_id}.{reslice_id}.manual_truth",
                "manual_truth",
            )
            self.set_part_training_metadata(
                specimen_id,
                part_id,
                active_reslice_id=str(reslice_id or ""),
                system_status="verified_train_ready",
                save=False,
            )
        elif role == "editable_ai_result":
            self.set_part_training_metadata(
                specimen_id,
                part_id,
                active_reslice_id=str(reslice_id or ""),
                system_status="predicted_pending_review",
                save=False,
            )
        if save:
            self.save_project()
        return record

    def _manual_truth_review_audit(
        self,
        source_record,
        *,
        review_action,
        source_role,
        specimen_id,
        part_id,
        reslice_id="",
    ):
        source = source_record if isinstance(source_record, dict) else {}
        audit = {
            "action": str(review_action or "").strip() or "manual_truth_promotion",
            "explicit_review": True,
            "reviewed_at": _now_iso(),
            "source_role": str(source_role or ""),
            "specimen_id": str(specimen_id or ""),
            "part_id": str(part_id or ""),
            "reslice_id": str(reslice_id or ""),
        }
        for key in (
            "model_id",
            "model_version",
            "source_model",
            "prediction_id",
        ):
            value = str(source.get(key) or "").strip()
            if value:
                audit[key] = value
        return audit

    def promote_part_reslice_editable_result_to_manual_truth(
        self,
        specimen_id,
        part_id,
        reslice_id,
        source_role="editable_ai_result",
        mark_train_ready=True,
        save=True,
        review_action="promote_part_reslice_editable_result_to_manual_truth",
        _replacement_transactions=None,
    ):
        labels, part, reslice = self._part_label_container(specimen_id, part_id, reslice_id)
        if reslice is None:
            raise ValueError("reslice_id_required_for_reslice_label")
        clean_review_action = str(review_action or "").strip() or "promote_part_reslice_editable_result_to_manual_truth"
        policy = can_promote_to_manual_truth(
            source_role,
            explicit_review=True,
            review_ready=True,
            opened_for_review=(part.get("training") or {}).get("opened_for_review"),
            audit_metadata={
                "review_action": clean_review_action,
                "specimen_id": specimen_id,
                "part_id": part_id,
                "reslice_id": reslice_id,
            },
        )
        self._require_guard(policy, "tif_truth_policy_denied")
        write_guard = can_write_label_role(
            "manual_truth",
            operation="promote_editable_ai_result_to_manual_truth",
            source_role=source_role,
            explicit_review=True,
            audit_metadata={
                "review_action": clean_review_action,
                "specimen_id": specimen_id,
                "part_id": part_id,
                "reslice_id": reslice_id,
            },
        )
        self._require_guard(write_guard, "tif_label_guard_denied")
        if source_role not in {"editable_ai_result", "manual_truth"}:
            raise ValueError(f"unsupported_part_manual_truth_source:{source_role}")
        source = labels.get(source_role) or {}
        source_path = source.get("path", "")
        if not source_path:
            raise ValueError(f"part_reslice_label_source_missing:{source_role}")
        review_audit = self._manual_truth_review_audit(
            source,
            review_action=clean_review_action,
            source_role=source_role,
            specimen_id=specimen_id,
            part_id=part_id,
            reslice_id=reslice_id,
        )
        target_path = (labels.get("manual_truth") or {}).get("path")
        if not target_path:
            target_path = os.path.join(self.part_dir(specimen_id, part_id), "reslices", _safe_record_id(reslice_id, "reslice"), "labels", "manual_truth.ome.zarr").replace("\\", "/")
        source_abs = self.to_absolute(source_path)
        target_abs = self.to_absolute(target_path)
        if paths_refer_to_same_file(source_abs, target_abs):
            if source_role != "manual_truth":
                raise ValueError("part_reslice_editable_ai_result_manual_truth_same_path")

            def apply_existing_truth():
                labels["manual_truth"]["status"] = "reviewed"
                labels["manual_truth"]["review_audit"] = dict(review_audit)
                if mark_train_ready:
                    self.set_part_training_metadata(specimen_id, part_id, active_reslice_id=str(reslice_id or ""), system_status="verified_train_ready", save=False)
                return labels["manual_truth"]

            return self._apply_project_mutation_transaction(apply_existing_truth, save=save)
        if paths_overlap(source_abs, target_abs):
            raise ValueError("part_reslice_manual_truth_source_target_path_overlap")
        self._ensure_project_write_allowed(
            target_abs,
            source_path=source_abs,
            source_role=source_role,
            target_role="manual_truth",
            operation="truth_promotion",
            allow_overwrite=True,
            audit_metadata={"review_action": clean_review_action},
        )
        def apply_replacement(metadata):
            labels["manual_truth"] = self._volume_payload(
                target_path,
                metadata["shape_zyx"],
                metadata["dtype"],
                metadata.get("spacing_zyx"),
                metadata.get("spacing_unit", "unknown"),
                metadata.get("orientation", "local_axis_reslice"),
                metadata.get("format", VOLUME_SIDECAR_FORMAT),
            )
            labels["manual_truth"]["role"] = "manual_truth"
            labels["manual_truth"]["status"] = "reviewed"
            labels["manual_truth"]["coordinate_space"] = "local_axis_reslice_voxel_zyx"
            labels["manual_truth"]["reslice_id"] = str(reslice_id or "")
            labels["manual_truth"]["review_audit"] = dict(review_audit)
            reslice["updated_at"] = _now_iso()
            part["updated_at"] = _now_iso()
            if mark_train_ready:
                self.set_part_training_metadata(specimen_id, part_id, active_reslice_id=str(reslice_id or ""), system_status="verified_train_ready", save=False)
            return labels["manual_truth"]

        return self._apply_volume_replacement_transaction(
            source_abs,
            target_abs,
            apply_replacement,
            role="manual_truth",
            integrity_owner_key=(
                f"reslice.{specimen_id}.{part_id}.{reslice_id}.manual_truth"
            ),
            save=save,
            transactions=_replacement_transactions,
        )

    def promote_part_editable_result_to_manual_truth(
        self,
        specimen_id,
        part_id,
        source_role="editable_ai_result",
        mark_train_ready=True,
        save=True,
        review_action="promote_part_editable_result_to_manual_truth",
        _replacement_transactions=None,
    ):
        part = self._require_part(specimen_id, part_id)
        labels = part.setdefault("labels", self._normalize_part_labels(None))
        clean_review_action = str(review_action or "").strip() or "promote_part_editable_result_to_manual_truth"
        policy = can_promote_to_manual_truth(
            source_role,
            explicit_review=True,
            review_ready=True,
            opened_for_review=(part.get("training") or {}).get("opened_for_review"),
            audit_metadata={
                "review_action": clean_review_action,
                "specimen_id": specimen_id,
                "part_id": part_id,
            },
        )
        self._require_guard(policy, "tif_truth_policy_denied")
        write_guard = can_write_label_role(
            "manual_truth",
            operation="promote_editable_ai_result_to_manual_truth",
            source_role=source_role,
            explicit_review=True,
            audit_metadata={
                "review_action": clean_review_action,
                "specimen_id": specimen_id,
                "part_id": part_id,
            },
        )
        self._require_guard(write_guard, "tif_label_guard_denied")
        if source_role not in {"editable_ai_result", "manual_truth"}:
            raise ValueError(f"unsupported_part_manual_truth_source:{source_role}")
        source = labels.get(source_role) or {}
        source_path = source.get("path", "")
        if not source_path:
            raise ValueError(f"part_label_source_missing:{source_role}")
        review_audit = self._manual_truth_review_audit(
            source,
            review_action=clean_review_action,
            source_role=source_role,
            specimen_id=specimen_id,
            part_id=part_id,
        )
        target_path = (labels.get("manual_truth") or {}).get("path")
        if not target_path:
            target_path = os.path.join(self.part_dir(specimen_id, part_id), "labels", "manual_truth.ome.zarr").replace("\\", "/")
        source_abs = self.to_absolute(source_path)
        target_abs = self.to_absolute(target_path)
        if paths_refer_to_same_file(source_abs, target_abs):
            if source_role != "manual_truth":
                raise ValueError("part_editable_ai_result_manual_truth_same_path")

            def apply_existing_truth():
                labels["manual_truth"]["status"] = "reviewed"
                labels["manual_truth"]["review_audit"] = dict(review_audit)
                if mark_train_ready:
                    self.set_part_training_metadata(specimen_id, part_id, system_status="verified_train_ready", save=False)
                return labels["manual_truth"]

            return self._apply_project_mutation_transaction(apply_existing_truth, save=save)
        if paths_overlap(source_abs, target_abs):
            raise ValueError("part_manual_truth_source_target_path_overlap")
        self._ensure_project_write_allowed(
            target_abs,
            source_path=source_abs,
            source_role=source_role,
            target_role="manual_truth",
            operation="truth_promotion",
            allow_overwrite=True,
            audit_metadata={"review_action": clean_review_action},
        )
        def apply_replacement(metadata):
            labels["manual_truth"] = self._volume_payload(
                target_path,
                metadata["shape_zyx"],
                metadata["dtype"],
                metadata.get("spacing_zyx"),
                metadata.get("spacing_unit", "unknown"),
                metadata.get("orientation", "unknown"),
                metadata.get("format", VOLUME_SIDECAR_FORMAT),
            )
            labels["manual_truth"]["role"] = "manual_truth"
            labels["manual_truth"]["status"] = "reviewed"
            labels["manual_truth"]["review_audit"] = dict(review_audit)
            if mark_train_ready:
                self.set_part_training_metadata(specimen_id, part_id, system_status="verified_train_ready", save=False)
            part["updated_at"] = _now_iso()
            return labels["manual_truth"]

        return self._apply_volume_replacement_transaction(
            source_abs,
            target_abs,
            apply_replacement,
            role="manual_truth",
            integrity_owner_key=f"part.{specimen_id}.{part_id}.manual_truth",
            save=save,
            transactions=_replacement_transactions,
        )

    def evaluate_part_editable_result_review_ready(self, specimen_id, part_id, reslice_id="", validate_label_ids=True):
        part = self._require_part(specimen_id, part_id)
        training = part.get("training") or {}
        clean_reslice_id = str(reslice_id or "").strip()
        editable = self.part_label_record(specimen_id, part_id, "editable_ai_result", reslice_id=clean_reslice_id)
        schema_id = str(training.get("label_schema_id") or "")
        schema = self.get_label_schema(schema_id, default={}) if schema_id else {}
        schema_labels = []
        for item in (schema.get("labels", []) if isinstance(schema, dict) else []):
            if not isinstance(item, dict):
                continue
            try:
                label_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            schema_labels.append(
                {
                    "id": label_id,
                    "name": str(item.get("name") or f"label_{label_id}"),
                    "display_name": str(item.get("display_name") or item.get("name") or f"Label {label_id}"),
                }
            )
        checks = {
            "editable_ai_result_exists": self._volume_record_exists(editable),
            "label_ids_known": False,
            "opened_for_review": bool(training.get("opened_for_review")),
        }
        if checks["editable_ai_result_exists"] and validate_label_ids:
            label_report = self.validate_part_label_ids(
                specimen_id,
                part_id,
                "editable_ai_result",
                reslice_id=clean_reslice_id,
            )
        elif checks["editable_ai_result_exists"] and schema_id and schema_labels:
            label_report = {
                "ok": True,
                "reasons": [],
                "unknown_label_ids": [],
                "label_ids": [],
                "skipped": "label_id_scan_deferred",
            }
        elif checks["editable_ai_result_exists"]:
            label_report = {
                "ok": False,
                "reasons": ["label_schema_missing"],
                "unknown_label_ids": [],
                "label_ids": [],
            }
        else:
            label_report = {
                "ok": False,
                "reasons": ["editable_ai_result_missing"],
                "unknown_label_ids": [],
                "label_ids": [],
            }
        checks["label_ids_known"] = bool(label_report.get("ok"))
        reason_labels = {
            "editable_ai_result_exists": "editable_ai_result_missing",
            "label_ids_known": "unknown_label_ids",
            "opened_for_review": "editable_ai_result_not_opened_for_review",
        }
        reasons = [reason_labels[key] for key, passed in checks.items() if not passed]
        if not checks["label_ids_known"]:
            for reason in label_report.get("reasons", []) or []:
                if reason not in reasons and reason != "editable_ai_result_missing":
                    reasons.append(reason)
        return {
            "specimen_id": str(specimen_id or ""),
            "part_id": str(part_id or ""),
            "reslice_id": clean_reslice_id,
            "checks": checks,
            "reasons": reasons,
            "review_ready": checks["editable_ai_result_exists"] and checks["label_ids_known"],
            "opened_for_review": checks["opened_for_review"],
            "label_report": label_report,
            "label_ids_checked": bool(checks["editable_ai_result_exists"] and validate_label_ids),
            "label_schema_id": schema_id,
            "label_schema_labels": schema_labels,
            "label_ids": list(label_report.get("label_ids") or []),
            "unknown_label_ids": list(label_report.get("unknown_label_ids") or []),
            "can_accept_without_open_warning": checks["editable_ai_result_exists"] and checks["label_ids_known"],
            "can_accept_now": checks["editable_ai_result_exists"] and checks["label_ids_known"] and checks["opened_for_review"],
        }

    def build_part_review_acceptance_report(self, part_refs, require_opened_for_review=True):
        refs = []
        seen = set()
        for ref in part_refs or []:
            if not isinstance(ref, dict):
                continue
            specimen_id = str(ref.get("specimen_id") or "").strip()
            part_id = str(ref.get("part_id") or "").strip()
            reslice_id = str(ref.get("reslice_id") or "").strip()
            key = (specimen_id, part_id, reslice_id)
            if specimen_id and part_id and key not in seen:
                seen.add(key)
                refs.append({"specimen_id": specimen_id, "part_id": part_id, "reslice_id": reslice_id})
        ready = []
        not_opened = []
        blocked = []
        for ref in refs:
            report = self.evaluate_part_editable_result_review_ready(ref["specimen_id"], ref["part_id"], ref.get("reslice_id", ""))
            item = {**ref, "reasons": list(report.get("reasons") or []), "report": report}
            if not report.get("review_ready"):
                blocked.append(item)
                continue
            if not report.get("opened_for_review"):
                not_opened.append(item)
                if require_opened_for_review:
                    blocked.append(item)
                    continue
            ready.append(ref)
        return {
            "refs": refs,
            "ready": ready,
            "not_opened": not_opened,
            "blocked": blocked,
            "require_opened_for_review": bool(require_opened_for_review),
            "count": len(refs),
            "ready_count": len(ready),
            "not_opened_count": len(not_opened),
            "blocked_count": len(blocked),
        }

    def promote_reviewed_part_results_to_manual_truth(
        self,
        part_refs,
        require_opened_for_review=True,
        save=True,
        review_action="promote_reviewed_part_results_to_manual_truth",
    ):
        report = self.build_part_review_acceptance_report(
            part_refs,
            require_opened_for_review=require_opened_for_review,
        )
        refs = report["ready"]
        blocked = report["blocked"]
        if blocked:
            raise ValueError(f"part_review_not_ready:{blocked}")
        promoted = []
        project_snapshot = copy.deepcopy(self.project_data)
        pending_version_snapshot = self._pending_project_data_version_id
        pending_assets_snapshot = set(self._pending_integrity_dirty_assets)
        replacements = []
        try:
            for ref in refs:
                if ref.get("reslice_id"):
                    manual = self.promote_part_reslice_editable_result_to_manual_truth(
                        ref["specimen_id"],
                        ref["part_id"],
                        ref.get("reslice_id", ""),
                        mark_train_ready=True,
                        save=False,
                        review_action=review_action,
                        _replacement_transactions=replacements,
                    )
                else:
                    manual = self.promote_part_editable_result_to_manual_truth(
                        ref["specimen_id"],
                        ref["part_id"],
                        mark_train_ready=True,
                        save=False,
                        review_action=review_action,
                        _replacement_transactions=replacements,
                    )
                promoted.append({**ref, "manual_truth": manual})
            if save and promoted:
                self.save_project()
        except Exception as exc:
            self.project_data = project_snapshot
            self._pending_project_data_version_id = pending_version_snapshot
            self._pending_integrity_dirty_assets = pending_assets_snapshot
            rollback_errors = []
            for replacement in reversed(replacements):
                try:
                    replacement.rollback()
                except Exception as rollback_exc:
                    rollback_errors.append(str(rollback_exc))
            if rollback_errors:
                raise RuntimeError(
                    f"part_truth_batch_failed:{exc};rollback_failed:{'|'.join(rollback_errors)}"
                ) from exc
            raise
        for replacement in replacements:
            self._commit_volume_replacement_cleanup(
                replacement,
                operation="batch_volume_replacement_commit",
                role="manual_truth",
            )
        return {"promoted": promoted, "count": len(promoted)}

    def validate_part_label_ids(self, specimen_id, part_id, role="manual_truth", reslice_id=""):
        part = self._require_part(specimen_id, part_id)
        training = part.get("training") or {}
        schema_id = str(training.get("label_schema_id") or "")
        schema_ids = self.label_schema_ids(schema_id)
        record = self.part_label_record(specimen_id, part_id, role, reslice_id=reslice_id)
        path = record.get("path", "")
        result = {
            "specimen_id": str(specimen_id or ""),
            "part_id": str(part_id or ""),
            "reslice_id": str(reslice_id or ""),
            "role": str(role or ""),
            "label_schema_id": schema_id,
            "ok": False,
            "unknown_label_ids": [],
            "label_ids": [],
            "reasons": [],
        }
        if not schema_id or not schema_ids:
            result["reasons"].append("label_schema_missing")
            return result
        if not self._volume_record_exists(record):
            result["reasons"].append(f"{role}_missing")
            return result
        try:
            from .tif_volume_io import load_volume_sidecar
            import numpy as np

            array = load_volume_sidecar(self.to_absolute(path), mmap_mode="r")
            values = sorted(int(value) for value in np.unique(array))
        except Exception as exc:
            result["reasons"].append(f"label_volume_unreadable:{exc}")
            return result
        result["label_ids"] = values
        unknown = [value for value in values if value not in schema_ids]
        result["unknown_label_ids"] = unknown
        if unknown:
            result["reasons"].append("unknown_label_ids")
        result["ok"] = not result["reasons"]
        return result

    def copy_label_layer_to_working_edit(self, specimen_id, source_role="manual_truth", draft_index=-1, save=True):
        specimen = self._require_specimen(specimen_id)
        labels = specimen.get("labels") or {}
        if source_role == "manual_truth":
            source = labels.get("manual_truth") or {}
        elif source_role == "model_draft":
            drafts = labels.get("model_drafts") or []
            source = drafts[draft_index] if drafts else {}
        else:
            raise ValueError(f"unsupported_working_edit_source:{source_role}")
        source_path = source.get("path", "")
        if not source_path:
            raise ValueError(f"source_label_missing:{source_role}")

        target_path = labels.get("working_edit", {}).get("path")
        if not target_path:
            target_path = os.path.join(self.specimen_dir(specimen_id), "labels", "working_edit.ome.zarr").replace("\\", "/")
        source_abs = self.to_absolute(source_path)
        target_abs = self.to_absolute(target_path)
        if paths_refer_to_same_file(source_abs, target_abs):
            raise ValueError(f"source_target_label_same:{source_role}")
        if paths_overlap(source_abs, target_abs):
            raise ValueError(f"source_target_label_path_overlap:{source_role}")
        manual_truth_path = (labels.get("manual_truth") or {}).get("path", "")
        manual_truth_abs = self.to_absolute(manual_truth_path)
        if manual_truth_abs and paths_refer_to_same_file(target_abs, manual_truth_abs):
            raise ValueError("working_edit_manual_truth_same_path")
        if manual_truth_abs and paths_overlap(target_abs, manual_truth_abs):
            raise ValueError("working_edit_manual_truth_path_overlap")
        if (
            source_role != "manual_truth"
            and manual_truth_abs
            and paths_refer_to_same_file(source_abs, manual_truth_abs)
        ):
            raise ValueError(f"source_manual_truth_same_path:{source_role}")
        if (
            source_role != "manual_truth"
            and manual_truth_abs
            and paths_overlap(source_abs, manual_truth_abs)
        ):
            raise ValueError(f"source_manual_truth_path_overlap:{source_role}")
        write_guard = can_write_label_role(
            "working_edit",
            operation="copy_label_layer_to_working_edit",
            source_role=source_role,
            audit_metadata={"source_role": source_role, "specimen_id": specimen_id},
            overwrite_existing=True,
        )
        self._require_guard(write_guard, "tif_label_guard_denied")
        self._ensure_project_write_allowed(
            target_abs,
            source_path=source_abs,
            source_role=source_role,
            target_role="working_edit",
            operation="copy_label_layer_to_working_edit",
            allow_overwrite=True,
            audit_metadata={"source_role": source_role},
        )

        def apply_replacement(metadata):
            specimen["labels"]["working_edit"] = self._volume_payload(
                target_path,
                metadata["shape_zyx"],
                metadata["dtype"],
                metadata.get("spacing_zyx"),
                metadata.get("spacing_unit", "unknown"),
                metadata.get("orientation", "unknown"),
                metadata.get("format", VOLUME_SIDECAR_FORMAT),
            )
            specimen["labels"]["working_edit"]["status"] = f"copied_from_{source_role}"
            specimen["review_status"] = "in_progress"
            specimen["train_ready"] = False
            return specimen["labels"]["working_edit"]

        return self._apply_volume_replacement_transaction(
            source_abs,
            target_abs,
            apply_replacement,
            role="working_edit",
            mark_manual_truth_changed=False,
            save=save,
        )

    def promote_working_edit_to_manual_truth(self, specimen_id, mark_train_ready=True, save=True):
        specimen = self._require_specimen(specimen_id)
        working = (specimen.get("labels") or {}).get("working_edit") or {}
        source_path = working.get("path", "")
        if not source_path:
            raise ValueError("working_edit_missing")
        policy = can_promote_to_manual_truth(
            "working_edit",
            explicit_review=True,
            review_ready=True,
            audit_metadata={"review_action": "promote_working_edit_to_manual_truth", "specimen_id": specimen_id},
        )
        self._require_guard(policy, "tif_truth_policy_denied")
        write_guard = can_write_label_role(
            "manual_truth",
            operation="promote_working_edit_to_manual_truth",
            source_role="working_edit",
            explicit_review=True,
            audit_metadata={"review_action": "promote_working_edit_to_manual_truth", "specimen_id": specimen_id},
        )
        self._require_guard(write_guard, "tif_label_guard_denied")
        target_path = (specimen.get("labels") or {}).get("manual_truth", {}).get("path")
        if not target_path:
            target_path = os.path.join(self.specimen_dir(specimen_id), "labels", "manual_truth.ome.zarr").replace("\\", "/")
        source_abs = self.to_absolute(source_path)
        target_abs = self.to_absolute(target_path)
        if paths_refer_to_same_file(source_abs, target_abs):
            raise ValueError("working_edit_manual_truth_same_path")
        if paths_overlap(source_abs, target_abs):
            raise ValueError("working_edit_manual_truth_path_overlap")
        self._ensure_project_write_allowed(
            target_abs,
            source_path=source_abs,
            source_role="working_edit",
            target_role="manual_truth",
            operation="truth_promotion",
            allow_overwrite=True,
            audit_metadata={"review_action": "promote_working_edit_to_manual_truth"},
        )
        def apply_replacement(metadata):
            specimen["labels"]["manual_truth"] = self._volume_payload(
                target_path,
                metadata["shape_zyx"],
                metadata["dtype"],
                metadata.get("spacing_zyx"),
                metadata.get("spacing_unit", "unknown"),
                metadata.get("orientation", "unknown"),
                metadata.get("format", VOLUME_SIDECAR_FORMAT),
            )
            specimen["labels"]["manual_truth"]["status"] = "reviewed"
            specimen["review_status"] = "train_ready" if mark_train_ready else "reviewed"
            specimen["train_ready"] = bool(mark_train_ready)
            return specimen["labels"]["manual_truth"]

        return self._apply_volume_replacement_transaction(
            source_abs,
            target_abs,
            apply_replacement,
            role="manual_truth",
            integrity_owner_key=f"specimen.{specimen_id}.manual_truth",
            save=save,
        )

    def evaluate_train_ready(self, specimen_id):
        specimen = self._require_specimen(specimen_id)
        checks = {}
        reasons = []

        checks["operator_marked_train_ready"] = bool(specimen.get("train_ready")) or specimen.get("review_status") == "train_ready"
        working = specimen.get("working_volume") or {}
        manual = (specimen.get("labels") or {}).get("manual_truth") or {}
        material_rel = specimen.get("material_map", "")

        checks["working_volume_exists"] = self._volume_record_exists(working)
        checks["manual_truth_exists"] = self._volume_record_exists(manual)
        training_guard = can_use_role_for_training(
            "manual_truth",
            record_exists=checks["manual_truth_exists"],
            status=manual.get("status", ""),
            review_audit=manual.get("review_audit"),
            training=manual.get("training"),
        )
        checks["training_role_allowed"] = bool(training_guard)
        checks["material_map_exists"] = bool(material_rel) and os.path.exists(self.to_absolute(material_rel))

        working_shape = self._volume_shape(working)
        manual_shape = self._volume_shape(manual)
        checks["shape_matches"] = bool(working_shape and manual_shape and list(working_shape) == list(manual_shape))

        material_map = None
        if checks["material_map_exists"]:
            try:
                material_map = read_material_map(self.to_absolute(material_rel))
            except Exception:
                material_map = None
        checks["has_trainable_material"] = has_trainable_material(material_map)

        reason_labels = {
            "operator_marked_train_ready": "specimen_not_marked_train_ready",
            "working_volume_exists": "working_volume_missing",
            "manual_truth_exists": "manual_truth_missing",
            "training_role_allowed": training_guard.reason or "training_requires_manual_truth",
            "material_map_exists": "material_map_missing",
            "shape_matches": "image_label_shape_mismatch",
            "has_trainable_material": "no_trainable_material",
        }
        for key, passed in checks.items():
            if passed:
                continue
            if key == "shape_matches" and not (checks["working_volume_exists"] and checks["manual_truth_exists"]):
                continue
            reason = reason_labels[key]
            if reason not in reasons:
                reasons.append(reason)

        return {
            "specimen_id": specimen.get("specimen_id"),
            "train_ready": all(checks.values()),
            "checks": checks,
            "reasons": reasons,
        }

    def list_train_ready_specimens(self):
        ready = []
        for specimen in self.project_data.get("specimens", []):
            result = self.evaluate_train_ready(specimen.get("specimen_id"))
            if result["train_ready"]:
                ready.append(specimen)
        return ready

    def evaluate_part_train_ready(self, specimen_id, part_id, reslice_id="", validate_label_ids=True):
        specimen = self._require_specimen(specimen_id)
        part = self._require_part(specimen_id, part_id)
        checks = {}
        reasons = []
        training = part.get("training") or {}
        labels = part.get("labels") or {}
        active_reslice_id = str(reslice_id or training.get("active_reslice_id") or "").strip()
        reslice = self.get_part_reslice(specimen_id, part_id, active_reslice_id, default=None) if active_reslice_id else None
        if reslice is None:
            reslices = self.list_part_reslices(specimen_id, part_id)
            reslice = reslices[-1] if reslices else None
            active_reslice_id = str((reslice or {}).get("reslice_id") or "")

        part_image = part.get("image") or {}
        manual = self.part_label_record(specimen_id, part_id, "manual_truth", reslice_id=active_reslice_id)
        schema_id = str(training.get("label_schema_id") or "")
        schema = self.get_label_schema(schema_id, default=None)

        checks["part_record_exists"] = bool(part)
        checks["part_volume_exists"] = self._volume_record_exists(part_image)
        checks["reslice_record_exists"] = bool(reslice and active_reslice_id)
        checks["reslice_output_exists"] = bool((reslice or {}).get("image_path") and os.path.exists(self.to_absolute((reslice or {}).get("image_path", ""))))
        checks["label_schema_exists"] = bool(schema and schema.get("labels"))
        checks["manual_truth_exists"] = self._volume_record_exists(manual)
        training_guard = can_use_role_for_training(
            "manual_truth",
            record_exists=checks["manual_truth_exists"],
            status=manual.get("status", ""),
            review_audit=manual.get("review_audit"),
            training=manual.get("training"),
        )
        checks["training_role_allowed"] = bool(training_guard)

        input_shape = self._path_volume_shape((reslice or {}).get("image_path", "")) if reslice else []
        part_shape = input_shape or self._volume_shape(part_image)
        manual_shape = self._volume_shape(manual)
        checks["shape_matches"] = bool(part_shape and manual_shape and list(part_shape) == list(manual_shape))

        if checks["manual_truth_exists"] and validate_label_ids:
            label_report = self.validate_part_label_ids(specimen_id, part_id, "manual_truth", reslice_id=active_reslice_id)
        elif checks["manual_truth_exists"]:
            label_report = {"ok": True, "reasons": [], "skipped": "label_id_scan_deferred"}
        else:
            label_report = {"ok": False, "reasons": ["manual_truth_missing"]}
        checks["label_ids_known"] = bool(label_report.get("ok"))

        checks["operator_marked_train_ready"] = (
            str(training.get("system_status") or part.get("system_status") or "") == "verified_train_ready"
            or str(part.get("status") or "") == "train_ready"
        )

        reason_labels = {
            "part_record_exists": "part_record_missing",
            "part_volume_exists": "part_volume_missing",
            "reslice_record_exists": "reslice_record_missing",
            "reslice_output_exists": "reslice_output_missing",
            "label_schema_exists": "label_schema_missing",
            "manual_truth_exists": "manual_truth_missing",
            "training_role_allowed": training_guard.reason or "training_requires_manual_truth",
            "shape_matches": "part_label_shape_mismatch",
            "label_ids_known": "unknown_label_ids",
            "operator_marked_train_ready": "part_not_marked_train_ready",
        }
        for key, passed in checks.items():
            if passed:
                continue
            if key == "shape_matches" and not (checks["part_volume_exists"] and checks["manual_truth_exists"]):
                continue
            reason = reason_labels[key]
            if reason not in reasons:
                reasons.append(reason)
        if not checks["label_ids_known"]:
            for reason in label_report.get("reasons", []) or []:
                if reason not in reasons and reason != "manual_truth_missing":
                    reasons.append(reason)

        return {
            "specimen_id": specimen.get("specimen_id"),
            "part_id": part.get("part_id"),
            "reslice_id": active_reslice_id,
            "label_schema_id": schema_id,
            "train_ready": all(checks.values()),
            "checks": checks,
            "reasons": reasons,
            "label_report": label_report,
            "input_shape_zyx": part_shape,
            "label_record": manual,
        }

    def evaluate_part_predict_ready(self, specimen_id, part_id, reslice_id=""):
        specimen = self._require_specimen(specimen_id)
        part = self._require_part(specimen_id, part_id)
        training = part.get("training") or {}
        part_image = part.get("image") or {}
        active_reslice_id = str(reslice_id or training.get("active_reslice_id") or "").strip()
        reslice = self.get_part_reslice(specimen_id, part_id, active_reslice_id, default=None) if active_reslice_id else None
        if reslice is None:
            reslices = self.list_part_reslices(specimen_id, part_id)
            reslice = reslices[-1] if reslices else None
            active_reslice_id = str((reslice or {}).get("reslice_id") or "")

        schema_id = str(training.get("label_schema_id") or "")
        schema = self.get_label_schema(schema_id, default=None)
        checks = {
            "part_record_exists": bool(part),
            "part_volume_exists": self._volume_record_exists(part_image),
            "reslice_record_exists": bool(reslice and active_reslice_id),
            "reslice_output_exists": bool((reslice or {}).get("image_path") and os.path.exists(self.to_absolute((reslice or {}).get("image_path", "")))),
            "label_schema_exists": bool(schema and schema.get("labels")),
        }
        reason_labels = {
            "part_record_exists": "part_record_missing",
            "part_volume_exists": "part_volume_missing",
            "reslice_record_exists": "reslice_record_missing",
            "reslice_output_exists": "reslice_output_missing",
            "label_schema_exists": "label_schema_missing",
        }
        reasons = [reason_labels[key] for key, passed in checks.items() if not passed]
        input_shape = self._path_volume_shape((reslice or {}).get("image_path", "")) if reslice else []
        part_shape = input_shape or self._volume_shape(part_image)
        return {
            "specimen_id": specimen.get("specimen_id"),
            "part_id": part.get("part_id"),
            "reslice_id": active_reslice_id,
            "label_schema_id": schema_id,
            "predict_ready": all(checks.values()),
            "checks": checks,
            "reasons": reasons,
            "input_shape_zyx": part_shape,
        }

    def list_train_ready_parts(self, specimen_ids=None):
        wanted = {str(item) for item in specimen_ids} if specimen_ids else None
        ready = []
        for specimen in self.project_data.get("specimens", []) or []:
            specimen_id = str((specimen or {}).get("specimen_id") or "")
            if wanted is not None and specimen_id not in wanted:
                continue
            for part in (specimen or {}).get("parts", []) or []:
                if not isinstance(part, dict):
                    continue
                result = self.evaluate_part_train_ready(specimen_id, part.get("part_id", ""))
                if result["train_ready"]:
                    ready.append({"specimen": specimen, "part": part, "readiness": result})
        return ready

    def add_part(
        self,
        specimen_id,
        part_id,
        display_name="",
        image=None,
        mask=None,
        parent_bbox_zyx=None,
        source=None,
        contours_path="",
        extraction_path="",
        status="draft",
        metadata=None,
        save=True,
    ):
        specimen = self._require_specimen(specimen_id)
        clean_id = self._validate_new_part_id(specimen, part_id)
        if status not in TIF_PART_STATUSES:
            status = "draft"
        now = _now_iso()
        part = {
            "part_id": clean_id,
            "display_name": str(display_name or clean_id),
            "status": status,
            "system_status": "cut_pending_labeling",
            "user_tags": [],
            "image": self._normalize_volume_record(image),
            "mask": self._normalize_volume_record(mask),
            "labels": self._normalize_part_labels(None),
            "training": {},
            "contours_path": self.to_relative(contours_path),
            "extraction_path": self.to_relative(extraction_path),
            "parent_bbox_zyx": self._normalize_bbox_zyx(parent_bbox_zyx),
            "source": dict(source or {"parent_specimen_id": specimen.get("specimen_id"), "parent_volume_role": "working_volume"}),
            "created_at": now,
            "updated_at": now,
            "metadata": dict(metadata or {}),
            "view_settings": {},
        }
        specimen.setdefault("parts", []).append(part)
        self._mark_manual_truth_data_changed()
        if save:
            self.save_project()
        return part

    def get_part(self, specimen_id, part_id, default=None):
        specimen = self.get_specimen(specimen_id, default=None)
        if specimen is None:
            return default
        wanted = str(part_id or "").strip()
        wanted_safe = _safe_part_id(wanted)
        for part in specimen.get("parts", []) or []:
            current = str((part or {}).get("part_id", "") or "").strip()
            if current == wanted or current == wanted_safe:
                return part
        return default

    def list_parts(self, specimen_id):
        specimen = self._require_specimen(specimen_id)
        return list(specimen.get("parts", []) or [])

    def add_part_roi(
        self,
        specimen_id,
        roi_id,
        display_name="",
        bbox_zyx=None,
        status="draft",
        linked_part_id="",
        metadata=None,
        save=True,
    ):
        specimen = self._require_specimen(specimen_id)
        clean_id = self._validate_new_roi_id(specimen, roi_id)
        if status not in TIF_PART_ROI_STATUSES:
            status = "draft"
        now = _now_iso()
        roi = {
            "roi_id": clean_id,
            "display_name": str(display_name or clean_id),
            "status": status,
            "bbox_zyx": self._normalize_bbox_zyx(bbox_zyx),
            "linked_part_id": str(linked_part_id or ""),
            "created_at": now,
            "updated_at": now,
            "metadata": dict(metadata or {}),
        }
        specimen.setdefault("part_rois", []).append(roi)
        if save:
            self.save_project()
        return roi

    def get_part_roi(self, specimen_id, roi_id, default=None):
        specimen = self.get_specimen(specimen_id, default=None)
        if specimen is None:
            return default
        wanted = str(roi_id or "").strip()
        wanted_safe = _safe_roi_id(wanted)
        for roi in specimen.get("part_rois", []) or []:
            current = str((roi or {}).get("roi_id", "") or "").strip()
            if current == wanted or current == wanted_safe:
                return roi
        return default

    def list_part_rois(self, specimen_id, include_cancelled=False):
        specimen = self._require_specimen(specimen_id)
        rois = list(specimen.get("part_rois", []) or [])
        if include_cancelled:
            return rois
        return [roi for roi in rois if (roi or {}).get("status") != "cancelled"]

    def update_part_roi(self, specimen_id, roi_id, bbox_zyx=None, status=None, display_name=None, linked_part_id=None, metadata=None, save=True):
        if status is not None and status not in TIF_PART_ROI_STATUSES:
            raise ValueError(f"invalid_tif_part_roi_status:{status}")
        roi = self.get_part_roi(specimen_id, roi_id, default=None)
        if roi is None:
            raise KeyError(f"unknown_part_roi_id:{specimen_id}:{roi_id}")
        if bbox_zyx is not None:
            roi["bbox_zyx"] = self._normalize_bbox_zyx(bbox_zyx)
        if status is not None:
            roi["status"] = status
        if display_name is not None:
            roi["display_name"] = str(display_name or roi.get("roi_id", ""))
        if linked_part_id is not None:
            roi["linked_part_id"] = str(linked_part_id or "")
        if isinstance(metadata, dict):
            roi.setdefault("metadata", {}).update(metadata)
        roi["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return roi

    def discard_part_roi(self, specimen_id, roi_id, save=True):
        specimen = self._require_specimen(specimen_id)
        roi = self.get_part_roi(specimen_id, roi_id, default=None)
        if roi is None:
            return {"removed_roi": False}
        roi["status"] = "cancelled"
        roi["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return {"removed_roi": True}

    def update_part_status(self, specimen_id, part_id, status, save=True):
        if status not in TIF_PART_STATUSES:
            raise ValueError(f"invalid_tif_part_status:{status}")
        part = self.get_part(specimen_id, part_id, default=None)
        if part is None:
            raise KeyError(f"unknown_part_id:{specimen_id}:{part_id}")
        part["status"] = status
        part["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return part

    def update_part_view_settings(self, specimen_id, part_id, settings, save=True):
        part = self.get_part(specimen_id, part_id, default=None)
        if part is None:
            raise KeyError(f"unknown_part_id:{specimen_id}:{part_id}")
        clean = {}
        if isinstance(settings, dict):
            for key, value in settings.items():
                if value is None:
                    continue
                clean[str(key)] = value
        part.setdefault("view_settings", {}).update(clean)
        part["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return part

    def list_part_reslices(self, specimen_id, part_id):
        part = self._require_part(specimen_id, part_id)
        return list(part.setdefault("metadata", {}).setdefault("local_axis_reslices", []))

    def get_part_reslice(self, specimen_id, part_id, reslice_id, default=None):
        wanted = str(reslice_id or "").strip()
        wanted_safe = _safe_record_id(wanted, fallback="reslice")
        for record in self.list_part_reslices(specimen_id, part_id):
            current = str((record or {}).get("reslice_id", "") or "").strip()
            if current in {wanted, wanted_safe}:
                return record
        return default

    def add_part_reslice(self, specimen_id, part_id, reslice_record, save=True):
        part = self._require_part(specimen_id, part_id)
        record = self._normalize_reslice_record(reslice_record, specimen_id, part_id)
        records = part.setdefault("metadata", {}).setdefault("local_axis_reslices", [])
        self._ensure_unique_record_id(records, "reslice_id", record["reslice_id"], "duplicate_part_reslice_id")
        records.append(record)
        part["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return record

    def update_part_reslice(self, specimen_id, part_id, reslice_id, updates, save=True):
        record = self.get_part_reslice(specimen_id, part_id, reslice_id, default=None)
        if record is None:
            raise KeyError(f"unknown_part_reslice_id:{specimen_id}:{part_id}:{reslice_id}")
        if not isinstance(updates, dict):
            return record
        for key, value in updates.items():
            if key in {"reslice_id", "specimen_id", "part_id", "created_at"}:
                continue
            record[str(key)] = value
        record["updated_at"] = _now_iso()
        part = self._require_part(specimen_id, part_id)
        part["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return record

    def list_global_axis_proposals(self, specimen_id, filters=None):
        specimen = self._require_specimen(specimen_id)
        records = list(specimen.setdefault("metadata", {}).setdefault("local_axis_global_proposals", []))
        return self._filter_records(records, filters)

    def get_global_axis_proposal(self, specimen_id, proposal_id, default=None):
        wanted = str(proposal_id or "").strip()
        wanted_safe = _safe_record_id(wanted, fallback="global_proposal")
        for record in self.list_global_axis_proposals(specimen_id):
            current = str((record or {}).get("global_proposal_id", "") or "").strip()
            if current in {wanted, wanted_safe}:
                return record
        return default

    def add_global_axis_proposal(self, specimen_id, proposal_record, save=True):
        specimen = self._require_specimen(specimen_id)
        record = self._normalize_global_axis_proposal(proposal_record, specimen_id)
        records = specimen.setdefault("metadata", {}).setdefault("local_axis_global_proposals", [])
        self._ensure_unique_record_id(records, "global_proposal_id", record["global_proposal_id"], "duplicate_global_axis_proposal_id")
        records.append(record)
        if save:
            self.save_project()
        return record

    def update_global_axis_proposal(self, specimen_id, proposal_id, updates, save=True):
        record = self.get_global_axis_proposal(specimen_id, proposal_id, default=None)
        if record is None:
            raise KeyError(f"unknown_global_axis_proposal_id:{specimen_id}:{proposal_id}")
        if isinstance(updates, dict):
            for key, value in updates.items():
                if key in {"global_proposal_id", "specimen_id", "created_at"}:
                    continue
                record[str(key)] = value
        record["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return record

    def list_local_frame_proposals(self, specimen_id, part_id, filters=None):
        part = self._require_part(specimen_id, part_id)
        records = list(part.setdefault("metadata", {}).setdefault("local_axis_frame_proposals", []))
        return self._filter_records(records, filters)

    def get_local_frame_proposal(self, specimen_id, part_id, proposal_id, default=None):
        wanted = str(proposal_id or "").strip()
        wanted_safe = _safe_record_id(wanted, fallback="frame_proposal")
        for record in self.list_local_frame_proposals(specimen_id, part_id):
            current = str((record or {}).get("frame_proposal_id", "") or "").strip()
            if current in {wanted, wanted_safe}:
                return record
        return default

    def add_local_frame_proposal(self, specimen_id, part_id, proposal_record, save=True):
        part = self._require_part(specimen_id, part_id)
        record = self._normalize_local_frame_proposal(proposal_record, specimen_id, part_id)
        records = part.setdefault("metadata", {}).setdefault("local_axis_frame_proposals", [])
        self._ensure_unique_record_id(records, "frame_proposal_id", record["frame_proposal_id"], "duplicate_local_frame_proposal_id")
        records.append(record)
        part["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return record

    def update_local_frame_proposal(self, specimen_id, part_id, proposal_id, updates, save=True):
        record = self.get_local_frame_proposal(specimen_id, part_id, proposal_id, default=None)
        if record is None:
            raise KeyError(f"unknown_local_frame_proposal_id:{specimen_id}:{part_id}:{proposal_id}")
        if isinstance(updates, dict):
            for key, value in updates.items():
                if key in {"frame_proposal_id", "specimen_id", "part_id", "created_at"}:
                    continue
                record[str(key)] = value
        record["updated_at"] = _now_iso()
        part = self._require_part(specimen_id, part_id)
        part["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return record

    def register_local_axis_model(self, model_record, save=True):
        record = self._normalize_local_axis_model(model_record)
        models = self.project_data.setdefault("models", [])
        self._ensure_unique_record_id(models, "model_id", record["model_id"], "duplicate_local_axis_model_id")
        models.append(record)
        if save:
            self.save_project()
        return record

    def list_local_axis_models(self, filters=None):
        records = [
            record
            for record in self.project_data.get("models", []) or []
            if isinstance(record, dict) and self._is_local_axis_model_record(record)
        ]
        return self._filter_records(records, filters)

    def get_local_axis_model(self, model_id, default=None):
        wanted = str(model_id or "").strip()
        for record in self.list_local_axis_models():
            if str(record.get("model_id", "") or "").strip() == wanted:
                return record
        return default

    def register_tif_segmentation_model_from_manifest(self, manifest_path, model_record=None, save=True):
        manifest_abs = self.to_absolute(manifest_path)
        manifest = {}
        if manifest_abs and os.path.exists(manifest_abs):
            with open(manifest_abs, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                manifest = loaded
        source = dict(model_record or {})

        def fill(key, value):
            if value in (None, "", [], {}):
                return
            current = source.get(key)
            if current in (None, "", [], {}):
                source[key] = value

        nnunet = manifest.get("nnunet") if isinstance(manifest.get("nnunet"), dict) else {}
        model_output = str(nnunet.get("model_output_dir") or "").strip()
        if model_output and not os.path.isabs(model_output) and manifest_abs:
            model_output = os.path.abspath(
                os.path.join(os.path.dirname(manifest_abs), model_output)
            )
        fill("model_id", manifest.get("model_id"))
        fill("backend_id", manifest.get("backend_id"))
        fill("model_family", manifest.get("model_family"))
        fill("input_scope", manifest.get("input_scope"))
        fill("label_schema_ids", manifest.get("label_schema_ids"))
        fill("trained_specimens", manifest.get("trained_specimens"))
        fill("trained_parts", manifest.get("trained_parts"))
        fill("trained_top_level_volumes", manifest.get("trained_top_level_volumes"))
        fill("model_path", model_output)
        fill("model_manifest", manifest_abs or manifest_path)
        fill("training_manifest_path", source.get("dataset_manifest"))
        fill("usable_for_research_prediction", manifest.get("usable_for_research_prediction"))
        fill("created_at", manifest.get("created_at"))
        if "training_samples" not in source:
            source["training_samples"] = len(manifest.get("trained_parts") or manifest.get("trained_top_level_volumes") or [])
        return self.register_tif_segmentation_model(source, save=save)

    def register_tif_segmentation_model(self, model_record, save=True):
        record = self._normalize_tif_segmentation_model(model_record)
        models = self.project_data.setdefault("models", [])
        wanted_id = str(record.get("model_id") or "").strip()
        wanted_manifest = str(record.get("model_manifest") or "").strip()
        wanted_manifest_abs = os.path.normcase(os.path.abspath(self.to_absolute(wanted_manifest))) if wanted_manifest else ""
        for index, existing in enumerate(models):
            if not isinstance(existing, dict):
                continue
            existing_id = str(existing.get("model_id") or "").strip()
            existing_manifest = str(existing.get("model_manifest") or "").strip()
            existing_manifest_abs = os.path.normcase(os.path.abspath(self.to_absolute(existing_manifest))) if existing_manifest else ""
            same_id = bool(wanted_id and existing_id == wanted_id)
            same_manifest = bool(wanted_manifest_abs and existing_manifest_abs == wanted_manifest_abs)
            if same_id or same_manifest:
                normalized_existing = self._normalize_model_record(existing)
                if not record.get("notes") and normalized_existing.get("notes"):
                    record["notes"] = normalized_existing.get("notes", "")
                record["created_at"] = normalized_existing.get("created_at") or record.get("created_at") or _now_iso()
                record["updated_at"] = _now_iso()
                models[index] = record
                if save:
                    self.save_project()
                return record
        models.append(record)
        if save:
            self.save_project()
        return record

    def list_tif_segmentation_models(self, filters=None):
        records = []
        for record in self.project_data.get("models", []) or []:
            if not isinstance(record, dict) or self._is_local_axis_model_record(record):
                continue
            if self._is_tif_segmentation_model_record(record) or str(record.get("model_manifest") or "").strip():
                records.append(record)
        return self._filter_records(records, filters)

    def get_tif_segmentation_model(self, model_id, default=None):
        wanted = str(model_id or "").strip()
        wanted_abs = os.path.normcase(os.path.abspath(self.to_absolute(wanted))) if wanted else ""
        for record in self.list_tif_segmentation_models():
            current_id = str(record.get("model_id") or "").strip()
            current_manifest = str(record.get("model_manifest") or "").strip()
            current_manifest_abs = os.path.normcase(os.path.abspath(self.to_absolute(current_manifest))) if current_manifest else ""
            if wanted in {current_id, current_manifest} or (wanted_abs and current_manifest_abs == wanted_abs):
                return record
        return default

    def update_tif_segmentation_model_notes(self, model_id, notes, save=True):
        record = self.get_tif_segmentation_model(model_id, default=None)
        if record is None:
            raise KeyError(f"unknown_tif_segmentation_model_id:{model_id}")
        record["notes"] = str(notes or "")
        record["updated_at"] = _now_iso()
        if save:
            self.save_project()
        return record

    def delete_tif_segmentation_model(self, model_id, save=True):
        wanted = str(model_id or "").strip()
        wanted_abs = os.path.normcase(os.path.abspath(self.to_absolute(wanted))) if wanted else ""
        models = self.project_data.setdefault("models", [])
        kept = []
        removed = None
        for record in models:
            current_manifest = str((record or {}).get("model_manifest") or "").strip() if isinstance(record, dict) else ""
            current_manifest_abs = os.path.normcase(os.path.abspath(self.to_absolute(current_manifest))) if current_manifest else ""
            if (
                removed is None
                and isinstance(record, dict)
                and not self._is_local_axis_model_record(record)
                and (
                    wanted in {str(record.get("model_id") or "").strip(), current_manifest}
                    or (wanted_abs and current_manifest_abs == wanted_abs)
                )
            ):
                removed = record
            else:
                kept.append(record)
        self.project_data["models"] = kept
        if removed is not None and save:
            self.save_project()
        return removed

    def add_local_axis_run(self, run_record, save=True):
        record = self._normalize_local_axis_run(run_record)
        runs = self.project_data.setdefault("runs", [])
        self._ensure_unique_record_id(runs, "run_id", record["run_id"], "duplicate_local_axis_run_id")
        runs.append(record)
        if save:
            self.save_project()
        return record

    def list_local_axis_runs(self, filters=None):
        records = [
            record
            for record in self.project_data.get("runs", []) or []
            if isinstance(record, dict) and self._is_local_axis_run_record(record)
        ]
        return self._filter_records(records, filters)

    def get_local_axis_run(self, run_id, default=None):
        wanted = str(run_id or "").strip()
        for record in self.list_local_axis_runs():
            if str(record.get("run_id", "") or "").strip() == wanted:
                return record
        return default

    def discard_part(self, specimen_id, part_id, remove_storage=True, save=True, unlink_linked_rois=False):
        if remove_storage and not save:
            raise ValueError("discard_part_storage_removal_requires_save")
        specimen = self._require_specimen(specimen_id)
        specimen_snapshot = copy.deepcopy(specimen)
        wanted = str(part_id or "").strip()
        wanted_safe = _safe_part_id(wanted)
        parts = specimen.setdefault("parts", [])
        removed_part = None
        kept = []
        for part in parts:
            current = str((part or {}).get("part_id", "") or "").strip()
            if removed_part is None and current in {wanted, wanted_safe}:
                removed_part = part
            else:
                kept.append(part)
        specimen["parts"] = kept

        if unlink_linked_rois and removed_part is not None:
            removed_part_id = str(removed_part.get("part_id") or wanted)
            for roi in specimen.get("part_rois", []) or []:
                if str((roi or {}).get("linked_part_id") or "") in {wanted, wanted_safe, removed_part_id}:
                    roi["status"] = "cancelled"
                    roi["linked_part_id"] = ""
                    roi["updated_at"] = _now_iso()

        removed_storage = False
        storage_cleanup_error = ""
        part_root = ""
        pending_delete_root = ""
        if remove_storage and removed_part is not None:
            part_root = os.path.abspath(self.to_absolute(self.part_dir(specimen_id, removed_part.get("part_id", ""))))
            parts_root = os.path.abspath(self.to_absolute(os.path.join(self.specimen_dir(specimen_id), "parts")))
            try:
                is_safe_storage = (
                    os.path.commonpath([parts_root, part_root]) == parts_root
                    and os.path.normcase(part_root) != os.path.normcase(parts_root)
                )
            except ValueError:
                is_safe_storage = False
            if is_safe_storage and os.path.exists(part_root):
                pending_delete_root = f"{part_root}.delete_pending_{uuid.uuid4().hex}"

        try:
            if pending_delete_root:
                os.replace(part_root, pending_delete_root)
                removed_storage = True
            if save and (removed_part is not None or removed_storage):
                self.save_project()
        except Exception as exc:
            rollback_errors = []
            specimen.clear()
            specimen.update(specimen_snapshot)
            if pending_delete_root and os.path.exists(pending_delete_root):
                try:
                    if os.path.exists(part_root):
                        raise FileExistsError(part_root)
                    os.replace(pending_delete_root, part_root)
                except Exception as rollback_exc:
                    rollback_errors.append(str(rollback_exc))
            if rollback_errors:
                raise RuntimeError(
                    f"discard_part_failed:{exc};rollback_failed:{'|'.join(rollback_errors)}"
                ) from exc
            raise

        if pending_delete_root and os.path.exists(pending_delete_root):
            try:
                shutil.rmtree(pending_delete_root)
            except OSError as exc:
                storage_cleanup_error = str(exc)
        return {
            "removed_part": removed_part is not None,
            "removed_storage": removed_storage,
            "storage_cleanup_error": storage_cleanup_error,
        }

    def _require_specimen(self, specimen_id):
        specimen = self.get_specimen(specimen_id, default=None)
        if specimen is None:
            raise KeyError(f"unknown_specimen_id:{specimen_id}")
        return specimen

    def _require_part(self, specimen_id, part_id):
        part = self.get_part(specimen_id, part_id, default=None)
        if part is None:
            raise KeyError(f"unknown_part_id:{specimen_id}:{part_id}")
        return part

    def discard_specimen_scaffold(self, specimen_id, save=True):
        clean_id = str(specimen_id or "").strip()
        specimens = self.project_data.setdefault("specimens", [])
        original_specimens = list(specimens)
        before = len(specimens)
        self.project_data["specimens"] = [item for item in specimens if item.get("specimen_id") != clean_id]
        removed_specimen = len(self.project_data["specimens"]) != before

        specimen_root = os.path.abspath(self.to_absolute(self.specimen_dir(clean_id)))
        specimens_root = os.path.abspath(os.path.join(self.project_dir, "specimens"))
        removed_storage = False
        try:
            is_safe_storage = (
                os.path.commonpath([specimens_root, specimen_root]) == specimens_root
                and os.path.normcase(specimen_root) != os.path.normcase(specimens_root)
            )
        except ValueError:
            is_safe_storage = False
        pending_delete_root = ""
        storage_cleanup_error = ""
        if is_safe_storage and os.path.exists(specimen_root):
            if save:
                pending_delete_root = f"{specimen_root}.delete_pending_{uuid.uuid4().hex}"
            else:
                shutil.rmtree(specimen_root)
                removed_storage = True

        try:
            if pending_delete_root:
                os.replace(specimen_root, pending_delete_root)
                removed_storage = True
            if save and (removed_specimen or removed_storage):
                self.save_project()
        except Exception as exc:
            rollback_errors = []
            self.project_data["specimens"] = original_specimens
            if pending_delete_root and os.path.exists(pending_delete_root):
                try:
                    if os.path.exists(specimen_root):
                        raise FileExistsError(specimen_root)
                    os.replace(pending_delete_root, specimen_root)
                except Exception as rollback_exc:
                    rollback_errors.append(str(rollback_exc))
            if rollback_errors:
                raise RuntimeError(
                    f"discard_specimen_failed:{exc};rollback_failed:{'|'.join(rollback_errors)}"
                ) from exc
            raise

        if pending_delete_root and os.path.exists(pending_delete_root):
            try:
                shutil.rmtree(pending_delete_root)
            except OSError as exc:
                storage_cleanup_error = str(exc)
        return {
            "removed_specimen": removed_specimen,
            "removed_storage": removed_storage,
            "storage_cleanup_error": storage_cleanup_error,
        }

    def _validate_new_specimen_id(self, specimen_id, require_storage_available=False):
        clean_id = str(specimen_id or "").strip()
        if not clean_id:
            raise ValueError("specimen_id_required")
        if self.get_specimen(clean_id, default=None) is not None:
            raise ValueError(f"duplicate_specimen_id:{clean_id}")

        new_dir = os.path.normcase(os.path.normpath(self.specimen_dir(clean_id)))
        for specimen in self.project_data.get("specimens", []):
            existing_id = str(specimen.get("specimen_id", "") or "").strip()
            if not existing_id:
                continue
            existing_dir = os.path.normcase(os.path.normpath(self.specimen_dir(existing_id)))
            if existing_dir == new_dir:
                raise ValueError(f"specimen_storage_path_collision:{clean_id}:{existing_id}:{new_dir}")

        if require_storage_available:
            specimen_root = self.to_absolute(self.specimen_dir(clean_id))
            if os.path.exists(specimen_root):
                if not os.path.isdir(specimen_root):
                    raise FileExistsError(f"specimen_storage_path_exists:{self.specimen_dir(clean_id)}")
                with os.scandir(specimen_root) as entries:
                    has_existing_content = any(entries)
                if has_existing_content:
                    raise FileExistsError(f"specimen_storage_dir_not_empty:{self.specimen_dir(clean_id)}")
                raise FileExistsError(f"specimen_storage_path_exists:{self.specimen_dir(clean_id)}")
        return clean_id

    def _validate_new_part_id(self, specimen, part_id):
        clean_id = _safe_part_id(part_id)
        used_ids = {
            str((part or {}).get("part_id", "") or "").strip().lower()
            for part in specimen.get("parts", []) or []
        }
        if clean_id.lower() in used_ids:
            raise ValueError(f"duplicate_part_id:{clean_id}")

        new_dir = os.path.normcase(os.path.normpath(self.part_dir(specimen.get("specimen_id", ""), clean_id))).lower()
        for part in specimen.get("parts", []) or []:
            existing_id = str((part or {}).get("part_id", "") or "").strip()
            if not existing_id:
                continue
            existing_dir = os.path.normcase(os.path.normpath(self.part_dir(specimen.get("specimen_id", ""), existing_id))).lower()
            if existing_dir == new_dir:
                raise ValueError(f"part_storage_path_collision:{clean_id}:{existing_id}:{new_dir}")
        return clean_id

    def _validate_new_roi_id(self, specimen, roi_id):
        clean_id = _safe_roi_id(roi_id)
        used_ids = {
            str((roi or {}).get("roi_id", "") or "").strip().lower()
            for roi in specimen.get("part_rois", []) or []
            if (roi or {}).get("status") != "cancelled"
        }
        if clean_id.lower() in used_ids:
            raise ValueError(f"duplicate_part_roi_id:{clean_id}")
        return clean_id

    def _normalize_volume_record(self, record):
        if not isinstance(record, dict):
            return {
                "path": "",
                "format": "",
                "shape_zyx": [],
                "dtype": "",
                "spacing_zyx": [],
                "spacing_unit": "unknown",
                "scale_verified": False,
                "orientation": "unknown",
            }
        clean = dict(record)
        clean["path"] = self.to_relative(clean.get("path", ""))
        clean.setdefault("format", "")
        clean.setdefault("shape_zyx", [])
        clean.setdefault("dtype", "")
        clean.setdefault("spacing_zyx", [])
        clean.setdefault("spacing_unit", "unknown")
        clean["scale_verified"] = clean.get("scale_verified") is True
        clean.setdefault("orientation", "unknown")
        return clean

    def _normalize_labels(self, labels):
        source = labels if isinstance(labels, dict) else {}
        return {
            "manual_truth": self._normalize_volume_record(source.get("manual_truth")),
            "working_edit": self._normalize_volume_record(source.get("working_edit")),
            "raw_ai_prediction_backup": self._normalize_volume_record(source.get("raw_ai_prediction_backup")),
            "model_drafts": list(source.get("model_drafts", [])) if isinstance(source.get("model_drafts", []), list) else [],
        }

    def _normalize_part_labels(self, labels):
        source = labels if isinstance(labels, dict) else {}
        return {
            "manual_truth": self._normalize_volume_record(source.get("manual_truth")),
            "editable_ai_result": self._normalize_volume_record(source.get("editable_ai_result") or source.get("working_edit")),
            "raw_ai_prediction_backup": self._normalize_volume_record(source.get("raw_ai_prediction_backup") or source.get("model_draft")),
        }

    def _normalize_label_schema(self, schema):
        source = schema if isinstance(schema, dict) else {}
        schema_id = _safe_record_id(source.get("schema_id") or source.get("id") or source.get("name") or "label_schema", fallback="label_schema")
        labels = []
        used_ids = set()
        for item in source.get("labels", []) if isinstance(source.get("labels", []), list) else []:
            if not isinstance(item, dict):
                continue
            try:
                label_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            if label_id < 0 or label_id in used_ids:
                continue
            used_ids.add(label_id)
            labels.append(
                {
                    "id": label_id,
                    "name": str(item.get("name") or f"label_{label_id}"),
                    "display_name": str(item.get("display_name") or item.get("name") or f"Label {label_id}"),
                    "color": str(item.get("color") or "#F94144"),
                    "trainable": bool(item.get("trainable", label_id != 0)),
                }
            )
        labels.sort(key=lambda item: int(item.get("id", 0)))
        created_at = str(source.get("created_at") or _now_iso())
        return {
            "schema_id": schema_id,
            "display_name": str(source.get("display_name") or source.get("name") or schema_id),
            "user_defined_part_name": str(source.get("user_defined_part_name") or source.get("part_name") or ""),
            "labels": labels,
            "created_at": created_at,
            "updated_at": str(source.get("updated_at") or created_at),
        }

    def _normalize_part_user_tag(self, tag, index=0):
        source = tag if isinstance(tag, dict) else {}
        tag_id = _safe_record_id(source.get("tag_id") or source.get("id") or source.get("label") or f"tag_{int(index) + 1}", fallback="tag")
        created_at = str(source.get("created_at") or _now_iso())
        try:
            order_index = int(source.get("order_index", index))
        except (TypeError, ValueError):
            order_index = int(index)
        return {
            "tag_id": tag_id,
            "label": str(source.get("label") or source.get("name") or tag_id),
            "color": str(source.get("color") or "#6B8AFD"),
            "order_index": order_index,
            "created_at": created_at,
            "updated_at": str(source.get("updated_at") or created_at),
        }

    def _normalize_parts(self, specimen):
        source = specimen.get("parts", [])
        if not isinstance(source, list):
            return []
        clean_parts = []
        used_ids = set()
        used_dirs = set()
        for index, record in enumerate(source):
            part = self._normalize_part_record(record, fallback_id=f"part_{index + 1}", specimen_id=specimen.get("specimen_id", ""))
            base_id = _safe_part_id(part.get("part_id") or f"part_{index + 1}")
            candidate = base_id
            suffix = 2
            while True:
                key = candidate.lower()
                storage = os.path.normcase(os.path.normpath(self.part_dir(specimen.get("specimen_id", ""), candidate))).lower()
                if key not in used_ids and storage not in used_dirs:
                    break
                candidate = f"{base_id}_{suffix}"
                suffix += 1
            part["part_id"] = candidate
            used_ids.add(candidate.lower())
            used_dirs.add(os.path.normcase(os.path.normpath(self.part_dir(specimen.get("specimen_id", ""), candidate))).lower())
            clean_parts.append(part)
        return clean_parts

    def _normalize_part_rois(self, specimen):
        source = specimen.get("part_rois", [])
        if not isinstance(source, list):
            return []
        clean_rois = []
        used_ids = set()
        for index, record in enumerate(source):
            roi = self._normalize_part_roi_record(record, fallback_id=f"roi_{index + 1}")
            base_id = _safe_roi_id(roi.get("roi_id") or f"roi_{index + 1}")
            candidate = base_id
            suffix = 2
            while candidate.lower() in used_ids:
                candidate = f"{base_id}_{suffix}"
                suffix += 1
            roi["roi_id"] = candidate
            used_ids.add(candidate.lower())
            clean_rois.append(roi)
        return clean_rois

    def _normalize_part_roi_record(self, record, fallback_id="roi"):
        source = record if isinstance(record, dict) else {}
        status = str(source.get("status", "draft") or "draft")
        if status not in TIF_PART_ROI_STATUSES:
            status = "draft"
        roi_id = _safe_roi_id(source.get("roi_id") or source.get("id") or fallback_id)
        created_at = str(source.get("created_at") or _now_iso())
        return {
            "roi_id": roi_id,
            "display_name": str(source.get("display_name") or source.get("name") or roi_id),
            "status": status,
            "bbox_zyx": self._normalize_bbox_zyx(source.get("bbox_zyx")),
            "linked_part_id": str(source.get("linked_part_id", "") or ""),
            "created_at": created_at,
            "updated_at": str(source.get("updated_at") or created_at),
            "metadata": dict(source.get("metadata") or {}),
            "view_settings": dict(source.get("view_settings") or {}),
        }

    def _normalize_part_record(self, record, fallback_id="part", specimen_id=""):
        source = record if isinstance(record, dict) else {}
        status = str(source.get("status", "draft") or "draft")
        if status not in TIF_PART_STATUSES:
            status = "draft"
        part_id = _safe_part_id(source.get("part_id") or source.get("id") or fallback_id)
        created_at = str(source.get("created_at") or _now_iso())
        metadata = dict(source.get("metadata") or {})
        training = dict(source.get("training") or {})
        system_status = str(source.get("system_status") or training.get("system_status") or "").strip()
        if system_status not in TIF_PART_SYSTEM_STATUSES:
            system_status = "cut_pending_labeling"
        training.setdefault("system_status", system_status)
        metadata["local_axis_reslices"] = [
            self._normalize_reslice_record(item, item.get("specimen_id") or specimen_id, part_id)
            for item in metadata.get("local_axis_reslices", []) or []
            if isinstance(item, dict)
        ]
        metadata["local_axis_frame_proposals"] = [
            self._normalize_local_frame_proposal(item, item.get("specimen_id") or specimen_id, part_id)
            for item in metadata.get("local_axis_frame_proposals", []) or []
            if isinstance(item, dict)
        ]
        metadata["local_axis_batch_failures"] = [
            self._normalize_local_axis_batch_failure(item)
            for item in metadata.get("local_axis_batch_failures", []) or []
            if isinstance(item, dict)
        ]
        return {
            "part_id": part_id,
            "display_name": str(source.get("display_name") or source.get("name") or part_id),
            "status": status,
            "system_status": system_status,
            "user_tags": self._normalize_list(source.get("user_tags"), str),
            "image": self._normalize_volume_record(source.get("image")),
            "mask": self._normalize_volume_record(source.get("mask")),
            "labels": self._normalize_part_labels(source.get("labels")),
            "training": training,
            "contours_path": self.to_relative(source.get("contours_path", "")),
            "extraction_path": self.to_relative(source.get("extraction_path", "")),
            "parent_bbox_zyx": self._normalize_bbox_zyx(source.get("parent_bbox_zyx")),
            "source": dict(source.get("source") or {}),
            "created_at": created_at,
            "updated_at": str(source.get("updated_at") or created_at),
            "metadata": metadata,
            "view_settings": dict(source.get("view_settings") or {}),
        }

    def _normalize_bbox_zyx(self, bbox):
        if not isinstance(bbox, (list, tuple)):
            return []
        if len(bbox) == 6:
            try:
                return [
                    [int(bbox[0]), int(bbox[3])],
                    [int(bbox[1]), int(bbox[4])],
                    [int(bbox[2]), int(bbox[5])],
                ]
            except (TypeError, ValueError):
                return []
        if len(bbox) != 3:
            return []
        clean = []
        try:
            for pair in bbox:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    return []
                start = int(pair[0])
                end = int(pair[1])
                clean.append([start, end])
        except (TypeError, ValueError):
            return []
        return clean

    def _volume_payload(self, path, shape_zyx, dtype, spacing_zyx=None, spacing_unit="unknown", orientation="unknown", fmt=VOLUME_SIDECAR_FORMAT, scale_verified=None):
        shape = [int(value) for value in (shape_zyx or [])]
        spacing = [float(value) for value in (spacing_zyx or [])] if spacing_zyx else []
        verified_scale = scale_verified is True
        if scale_verified is None and str(fmt or "") == VOLUME_SIDECAR_FORMAT:
            try:
                metadata = read_volume_metadata(self.to_absolute(path))
                metadata_spacing = [
                    float(value) for value in metadata.get("spacing_zyx", [])
                ]
                metadata_unit = str(metadata.get("spacing_unit") or "unknown")
                verified_scale = (
                    metadata.get("scale_verified") is True
                    and metadata_spacing == spacing
                    and metadata_unit.strip().lower()
                    == str(spacing_unit or "unknown").strip().lower()
                )
            except (OSError, TypeError, ValueError):
                verified_scale = False
        return {
            "path": self.to_relative(path),
            "format": str(fmt or ""),
            "shape_zyx": shape,
            "dtype": str(dtype or ""),
            "spacing_zyx": spacing,
            "spacing_unit": str(spacing_unit or "unknown"),
            "scale_verified": verified_scale,
            "orientation": str(orientation or "unknown"),
        }

    def _volume_record_exists(self, record):
        path = (record or {}).get("path", "")
        if not path:
            return False
        abs_path = self.to_absolute(path)
        if (record or {}).get("format") == VOLUME_SIDECAR_FORMAT:
            return volume_sidecar_exists(abs_path)
        return os.path.exists(abs_path)

    def _volume_shape(self, record):
        if not isinstance(record, dict):
            return []
        if record.get("shape_zyx"):
            return [int(value) for value in record.get("shape_zyx", [])]
        path = record.get("path", "")
        if path and record.get("format") == VOLUME_SIDECAR_FORMAT and volume_sidecar_exists(self.to_absolute(path)):
            try:
                return [int(value) for value in read_volume_metadata(self.to_absolute(path)).get("shape_zyx", [])]
            except Exception:
                return []
        return []

    def _path_volume_shape(self, path):
        text = str(path or "").strip()
        if not text:
            return []
        abs_path = self.to_absolute(text)
        if volume_sidecar_exists(abs_path):
            try:
                return [int(value) for value in read_volume_metadata(abs_path).get("shape_zyx", [])]
            except Exception:
                return []
        if os.path.exists(abs_path):
            try:
                import tifffile

                return [int(value) for value in tifffile.memmap(abs_path).shape]
            except Exception:
                return _tif_shape_from_metadata(abs_path)
        return []

    def _normalize_specimen_metadata(self, specimen):
        source = (specimen or {}).get("metadata") if isinstance(specimen, dict) else {}
        metadata = dict(source or {})
        specimen_id = str((specimen or {}).get("specimen_id", "") or "")
        metadata["local_axis_global_proposals"] = [
            self._normalize_global_axis_proposal(item, specimen_id)
            for item in metadata.get("local_axis_global_proposals", []) or []
            if isinstance(item, dict)
        ]
        return metadata

    def _normalize_status(self, status, default="proposed"):
        clean = str(status or default).strip()
        return clean if clean in LOCAL_AXIS_PROPOSAL_STATUSES else default

    def _normalize_list(self, values, cast=str):
        if not isinstance(values, (list, tuple)):
            return []
        clean = []
        for value in values:
            try:
                clean.append(cast(value))
            except (TypeError, ValueError):
                continue
        return clean

    def _normalize_point_zyx(self, values):
        if not isinstance(values, (list, tuple)) or len(values) != 3:
            return []
        try:
            return [float(values[0]), float(values[1]), float(values[2])]
        except (TypeError, ValueError):
            return []

    def _normalize_axis_vector(self, values):
        return self._normalize_point_zyx(values)

    def _normalize_spacing_zyx(self, values):
        spacing = self._normalize_point_zyx(values)
        if len(spacing) != 3 or any(float(value) <= 0 for value in spacing):
            return []
        return spacing

    def _normalize_local_frame(self, frame):
        source = frame if isinstance(frame, dict) else {}
        clean = {
            "origin_zyx": self._normalize_point_zyx(source.get("origin_zyx") or source.get("origin")),
            "x_axis": self._normalize_axis_vector(source.get("x_axis")),
            "y_axis": self._normalize_axis_vector(source.get("y_axis")),
            "z_axis": self._normalize_axis_vector(source.get("z_axis")),
            "output_axis": str(source.get("output_axis") or "z_axis"),
            "coordinate_space": str(source.get("coordinate_space") or "part_volume_voxel_zyx"),
        }
        spacing = self._normalize_spacing_zyx(source.get("spacing_zyx"))
        if spacing:
            clean["spacing_zyx"] = spacing
        if isinstance(source.get("roll_reference"), dict):
            clean["roll_reference"] = dict(source.get("roll_reference"))
        if isinstance(source.get("reference_plane"), dict):
            clean["reference_plane"] = dict(source.get("reference_plane"))
        return clean

    def _normalize_reslice_record(self, record, specimen_id, part_id):
        source = record if isinstance(record, dict) else {}
        now = _now_iso()
        created_at = str(source.get("created_at") or now)
        reslice_id = _safe_record_id(source.get("reslice_id") or source.get("id") or f"reslice_{datetime.now().strftime('%Y%m%d_%H%M%S')}", fallback="reslice")
        return {
            "reslice_id": reslice_id,
            "specimen_id": str(source.get("specimen_id") or specimen_id or ""),
            "part_id": str(source.get("part_id") or part_id or ""),
            "display_name": str(source.get("display_name") or reslice_id),
            "template_id": str(source.get("template_id") or ""),
            "status": str(source.get("status") or "exported"),
            "image_path": self.to_relative(source.get("image_path", "")),
            "mask_path": self.to_relative(source.get("mask_path", "")),
            "metadata_path": self.to_relative(source.get("metadata_path", "")),
            "preview_path": self.to_relative(source.get("preview_path", "")),
            "local_frame": self._normalize_local_frame(source.get("local_frame")),
            "reslice_params": dict(source.get("reslice_params") or {}),
            "source": dict(source.get("source") or {}),
            "labels": self._normalize_part_labels(source.get("labels")),
            "training": dict(source.get("training") or {}),
            "training_sample": dict(source.get("training_sample") or {}),
            "provenance": dict(source.get("provenance") or {}),
            "created_at": created_at,
            "updated_at": str(source.get("updated_at") or created_at),
        }

    def _normalize_local_axis_batch_failure(self, record):
        source = record if isinstance(record, dict) else {}
        now = _now_iso()
        created_at = str(source.get("created_at") or now)
        failure_id = _safe_record_id(source.get("failure_id") or source.get("id") or f"failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}", fallback="failed")
        return {
            "failure_id": failure_id,
            "proposal_id": str(source.get("proposal_id") or ""),
            "template_id": str(source.get("template_id") or ""),
            "reason": str(source.get("reason") or ""),
            "detail": str(source.get("detail") or ""),
            "model_id": str(source.get("model_id") or ""),
            "model_version": str(source.get("model_version") or ""),
            "created_at": created_at,
            "updated_at": str(source.get("updated_at") or created_at),
        }

    def _normalize_global_axis_proposal(self, record, specimen_id):
        source = record if isinstance(record, dict) else {}
        now = _now_iso()
        created_at = str(source.get("created_at") or now)
        proposal_id = _safe_record_id(source.get("global_proposal_id") or source.get("proposal_id") or source.get("id") or f"global_proposal_{datetime.now().strftime('%Y%m%d_%H%M%S')}", fallback="global_proposal")
        return {
            "global_proposal_id": proposal_id,
            "specimen_id": str(source.get("specimen_id") or specimen_id or ""),
            "template_id": str(source.get("template_id") or ""),
            "coordinate_space": str(source.get("coordinate_space") or "full_volume_voxel_zyx"),
            "bbox_zyx": self._normalize_bbox_zyx(source.get("bbox_zyx")),
            "center_zyx": self._normalize_point_zyx(source.get("center_zyx")),
            "confidence": float(source.get("confidence", 0.0) or 0.0),
            "model_id": str(source.get("model_id") or ""),
            "model_version": str(source.get("model_version") or ""),
            "status": self._normalize_status(source.get("status")),
            "hard_case_flags": self._normalize_list(source.get("hard_case_flags"), str),
            "input_data": dict(source.get("input_data") or {}),
            "failure_reason": str(source.get("failure_reason") or ""),
            "reviewer_notes": str(source.get("reviewer_notes") or ""),
            "review_audit": dict(
                source.get("review_audit")
                or (source.get("provenance") or {}).get("review_audit")
                or {}
            ),
            "review_history": [
                dict(item)
                for item in (
                    source.get("review_history")
                    or (source.get("provenance") or {}).get("review_history")
                    or []
                )
                if isinstance(item, dict)
            ],
            "provenance": dict(source.get("provenance") or {}),
            "created_at": created_at,
            "updated_at": str(source.get("updated_at") or created_at),
        }

    def _normalize_local_frame_proposal(self, record, specimen_id, part_id):
        source = record if isinstance(record, dict) else {}
        now = _now_iso()
        created_at = str(source.get("created_at") or now)
        proposal_id = _safe_record_id(source.get("frame_proposal_id") or source.get("proposal_id") or source.get("id") or f"frame_proposal_{datetime.now().strftime('%Y%m%d_%H%M%S')}", fallback="frame_proposal")
        return {
            "frame_proposal_id": proposal_id,
            "specimen_id": str(source.get("specimen_id") or specimen_id or ""),
            "part_id": str(source.get("part_id") or part_id or ""),
            "template_id": str(source.get("template_id") or ""),
            "coordinate_space": str(source.get("coordinate_space") or "part_volume_voxel_zyx"),
            "origin_zyx": self._normalize_point_zyx(source.get("origin_zyx")),
            "output_axis_start_zyx": self._normalize_point_zyx(source.get("output_axis_start_zyx")),
            "output_axis_end_zyx": self._normalize_point_zyx(source.get("output_axis_end_zyx")),
            "roll_reference": dict(source.get("roll_reference") or {}),
            "local_frame": self._normalize_local_frame(source.get("local_frame")),
            "source_axis": dict(source.get("source_axis") or {}),
            "confidence": float(source.get("confidence", 0.0) or 0.0),
            "landmark_scores": dict(source.get("landmark_scores") or {}),
            "missing_landmarks": self._normalize_list(source.get("missing_landmarks"), str),
            "model_id": str(source.get("model_id") or ""),
            "model_version": str(source.get("model_version") or ""),
            "status": self._normalize_status(source.get("status")),
            "hard_case_flags": self._normalize_list(source.get("hard_case_flags"), str),
            "input_data": dict(source.get("input_data") or {}),
            "failure_reason": str(source.get("failure_reason") or ""),
            "reviewer_notes": str(source.get("reviewer_notes") or ""),
            "review_audit": dict(
                source.get("review_audit")
                or (source.get("provenance") or {}).get("review_audit")
                or {}
            ),
            "review_history": [
                dict(item)
                for item in (
                    source.get("review_history")
                    or (source.get("provenance") or {}).get("review_history")
                    or []
                )
                if isinstance(item, dict)
            ],
            "provenance": dict(source.get("provenance") or {}),
            "created_at": created_at,
            "updated_at": str(source.get("updated_at") or created_at),
        }

    def _normalize_local_axis_model(self, record):
        source = record if isinstance(record, dict) else {}
        now = _now_iso()
        created_at = str(source.get("created_at") or now)
        model_id = str(source.get("model_id") or "").strip()
        if not model_id:
            model_id = _safe_record_id(f"local_axis_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}", fallback="local_axis_model")
        return {
            "model_id": model_id,
            "model_version": str(source.get("model_version") or ""),
            "profile_scope": str(source.get("profile_scope") or "tif_local_axis"),
            "template_id": str(source.get("template_id") or ""),
            "model_type": str(source.get("model_type") or "local_frame"),
            "backend_type": str(source.get("backend_type") or ""),
            "backend_id": str(source.get("backend_id") or ""),
            "input_contract": dict(source.get("input_contract") or {}),
            "output_contract": dict(source.get("output_contract") or {}),
            "model_path": self.to_relative(source.get("model_path", "")),
            "model_manifest": self.to_relative(source.get("model_manifest", "")),
            "training_manifest_path": self.to_relative(source.get("training_manifest_path", "")),
            "notes": str(source.get("notes") or ""),
            "created_at": created_at,
            "updated_at": str(source.get("updated_at") or created_at),
        }

    def _is_local_axis_model_record(self, record):
        source = record if isinstance(record, dict) else {}
        if source.get("profile_scope") == "tif_local_axis":
            return True
        if source.get("backend_type") == "external_local_axis":
            return True
        if source.get("model_type") in {"local_frame", "global_roi", "global_roi_and_local_frame"}:
            return True
        return False

    def _is_tif_segmentation_model_record(self, record):
        source = record if isinstance(record, dict) else {}
        if source.get("profile_scope") == "tif_segmentation":
            return True
        if source.get("model_type") == "tif_segmentation":
            return True
        family = str(source.get("model_family") or "")
        if family in {"nnunet_v2_tif_region", "nnunet_v2_part_reslice"}:
            return True
        return False

    def _normalize_tif_segmentation_model(self, record):
        source = record if isinstance(record, dict) else {}
        now = _now_iso()
        created_at = str(source.get("created_at") or now)
        model_id = str(source.get("model_id") or "").strip()
        if not model_id:
            base = source.get("model_manifest") or source.get("run_id") or f"tif_segmentation_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            model_id = _safe_record_id(base, fallback="tif_segmentation_model")
        try:
            training_samples = int(source.get("training_samples", 0) or 0)
        except (TypeError, ValueError):
            training_samples = 0
        clean = {
            "model_id": model_id,
            "model_version": str(source.get("model_version") or ""),
            "profile_scope": str(source.get("profile_scope") or "tif_segmentation"),
            "template_id": str(source.get("template_id") or ""),
            "model_type": str(source.get("model_type") or "tif_segmentation"),
            "backend_type": str(source.get("backend_type") or "external_segmentation"),
            "backend_id": str(source.get("backend_id") or ""),
            "model_family": str(source.get("model_family") or ""),
            "input_scope": str(source.get("input_scope") or ""),
            "label_schema_ids": self._normalize_list(source.get("label_schema_ids"), str),
            "trained_specimens": self._normalize_list(source.get("trained_specimens"), str),
            "trained_parts": list(source.get("trained_parts", []) or []) if isinstance(source.get("trained_parts", []), list) else [],
            "trained_top_level_volumes": list(source.get("trained_top_level_volumes", []) or []) if isinstance(source.get("trained_top_level_volumes", []), list) else [],
            "training_samples": training_samples,
            "usable_for_research_prediction": bool(source.get("usable_for_research_prediction", True)),
            "run_id": str(source.get("run_id") or ""),
            "run_dir": self.to_relative(source.get("run_dir", "")),
            "result_json": self.to_relative(source.get("result_json", "")),
            "input_contract": dict(source.get("input_contract") or {}),
            "output_contract": dict(source.get("output_contract") or {}),
            "model_path": self.to_relative(source.get("model_path", "")),
            "model_manifest": self.to_relative(source.get("model_manifest", "")),
            "training_manifest_path": self.to_relative(source.get("training_manifest_path", "")),
            "notes": str(source.get("notes") or ""),
            "created_at": created_at,
            "updated_at": str(source.get("updated_at") or created_at),
        }
        for key, value in source.items():
            if key not in clean:
                clean[str(key)] = value
        return clean

    def _normalize_model_record(self, record):
        source = record if isinstance(record, dict) else {}
        if self._is_local_axis_model_record(source):
            return self._normalize_local_axis_model(source)
        if self._is_tif_segmentation_model_record(source):
            return self._normalize_tif_segmentation_model(source)
        clean = dict(source)
        for key in ("model_path", "model_manifest", "training_manifest_path"):
            if key in clean:
                clean[key] = self.to_relative(clean.get(key, ""))
        return clean

    def _normalize_local_axis_run(self, record):
        source = record if isinstance(record, dict) else {}
        now = _now_iso()
        created_at = str(source.get("created_at") or now)
        run_id = _safe_record_id(source.get("run_id") or f"local_axis_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}", fallback="local_axis_run")
        clean = {
            "run_id": run_id,
            "workflow": str(source.get("workflow") or "tif_local_axis"),
            "action": str(source.get("action") or source.get("run_type") or ""),
            "backend_id": str(source.get("backend_id") or ""),
            "model_id": str(source.get("model_id") or ""),
            "template_id": str(source.get("template_id") or ""),
            "specimen_ids": self._normalize_list(source.get("specimen_ids"), str),
            "part_ids": self._normalize_list(source.get("part_ids"), str),
            "run_dir": self.to_relative(source.get("run_dir", "")),
            "contract_json": self.to_relative(source.get("contract_json", "")),
            "result_json": self.to_relative(source.get("result_json", "")),
            "result_status": str(source.get("result_status") or source.get("status") or ""),
            "metrics": dict(source.get("metrics") or {}),
            "warnings": list(source.get("warnings", []) or []) if isinstance(source.get("warnings", []), list) else [],
            "errors": list(source.get("errors", []) or []) if isinstance(source.get("errors", []), list) else [],
            "created_at": created_at,
            "updated_at": str(source.get("updated_at") or created_at),
        }
        return clean

    def _is_local_axis_run_record(self, record):
        source = record if isinstance(record, dict) else {}
        if source.get("workflow") == "tif_local_axis":
            return True
        if source.get("model_family") == "local_axis":
            return True
        if source.get("action") in {"predict_global_roi", "predict_local_frame"}:
            return True
        return False

    def _normalize_run_record(self, record):
        source = record if isinstance(record, dict) else {}
        if self._is_local_axis_run_record(source):
            return self._normalize_local_axis_run(source)
        clean = dict(source)
        for key in ("run_dir", "contract_json", "result_json"):
            if key in clean:
                clean[key] = self.to_relative(clean.get(key, ""))
        return clean

    def _ensure_unique_record_id(self, records, key, value, error_prefix):
        wanted = str(value or "").strip()
        for record in records or []:
            if str((record or {}).get(key, "") or "").strip() == wanted:
                raise ValueError(f"{error_prefix}:{wanted}")

    def _filter_records(self, records, filters=None):
        if not isinstance(filters, dict) or not filters:
            return records
        result = []
        for record in records:
            keep = True
            for key, expected in filters.items():
                value = (record or {}).get(key)
                if isinstance(expected, (list, tuple, set)):
                    if value not in expected:
                        keep = False
                        break
                elif value != expected:
                    keep = False
                    break
            if keep:
                result.append(record)
        return result
