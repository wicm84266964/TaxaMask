import json
import os
import shutil
from datetime import datetime

from .safe_io import atomic_write_json, backup_file
from .sqlite_storage import LEGACY_JSON_BACKEND, PROJECT_MANIFEST_SCHEMA_VERSION, SQLITE_BACKEND, write_project_manifest
from .tif_materials import has_trainable_material, read_material_map, write_material_map
from .tif_volume_io import VOLUME_SIDECAR_FORMAT, copy_volume_sidecar, read_volume_metadata, volume_sidecar_exists


TIF_PROJECT_SCHEMA_VERSION = "ant3d_tif_project_v1"
TIF_PROJECT_TYPE = "tif_volume"
DEFAULT_TIF_PROJECT_FILENAME = "project.json"
TIF_PROJECT_BACKUP_LIMIT = 30
TIF_PROJECT_BACKUP_MIN_INTERVAL_SECONDS = 300
TIF_REVIEW_STATUSES = {"not_started", "in_progress", "fully_annotated", "reviewed", "train_ready"}
TIF_PART_STATUSES = {"draft", "roi_confirmed", "mask_preview", "reviewed"}
TIF_PART_ROI_STATUSES = {"draft", "confirmed", "part_created", "cancelled"}
LOCAL_AXIS_PROPOSAL_STATUSES = {"proposed", "needs_review", "accepted", "rejected", "exported"}


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


def _default_project_data(name="Untitled TIF Project", project_id=None):
    now = _now_iso()
    return {
        "schema_version": TIF_PROJECT_SCHEMA_VERSION,
        "project_type": TIF_PROJECT_TYPE,
        "project_id": project_id or f"tif_project_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "name": str(name or "Untitled TIF Project"),
        "created_at": now,
        "updated_at": now,
        "specimens": [],
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

    @property
    def project_dir(self):
        if self.current_asset_root:
            return os.path.abspath(self.current_asset_root)
        if not self.current_project_path:
            return os.getcwd()
        return os.path.dirname(os.path.abspath(self.current_project_path))

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
        manifest_created = False
        try:
            conn = create_tif_project_database(database_path)
            conn.close()
            conn = None
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
            manifest_created = True
            self.current_project_path = os.path.abspath(manifest_path)
            self.current_database_path = os.path.abspath(database_path)
            self.current_storage_backend = SQLITE_BACKEND
            self.current_asset_root = os.path.abspath(str(project_dir))
            self.save_project()
            return self.current_project_path
        except Exception:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            if manifest_created:
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
        os.makedirs(project_dir, exist_ok=True)
        self.project_data = _default_project_data(name=name, project_id=project_id)
        if storage_backend == SQLITE_BACKEND:
            return self._create_sqlite_project_storage(name, project_dir)
        if storage_backend not in (LEGACY_JSON_BACKEND, "json"):
            raise ValueError(f"unsupported_tif_project_storage_backend:{storage_backend}")
        self.current_project_path = os.path.join(os.path.abspath(project_dir), DEFAULT_TIF_PROJECT_FILENAME)
        self.current_storage_backend = LEGACY_JSON_BACKEND
        self.current_database_path = ""
        self.current_asset_root = ""
        self._legacy_json_write_enabled = True
        self.save_project()
        return self.current_project_path

    def load_project(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("tif_project_json_not_object")
        if self._is_sqlite_manifest_payload(payload):
            from .tif_sqlite_loader import load_tif_sqlite_project_manifest

            loaded_sqlite = load_tif_sqlite_project_manifest(path)
            self.current_project_path = os.path.abspath(path)
            self.project_data = self._normalize_loaded_project_data(loaded_sqlite["project_data"])
            self.current_storage_backend = SQLITE_BACKEND
            self.current_database_path = loaded_sqlite.get("database_path", "")
            self._legacy_json_write_enabled = False
            manifest = loaded_sqlite.get("manifest", {}) if isinstance(loaded_sqlite.get("manifest"), dict) else {}
            asset_root = str(manifest.get("tif_asset_root") or "").strip()
            if asset_root:
                if os.path.isabs(asset_root):
                    self.current_asset_root = os.path.normpath(asset_root)
                else:
                    self.current_asset_root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)), asset_root))
            else:
                self.current_asset_root = os.path.dirname(os.path.abspath(path))
            return self.project_data
        self.current_storage_backend = LEGACY_JSON_BACKEND
        self.current_database_path = ""
        self.current_asset_root = ""
        self._legacy_json_write_enabled = False
        if payload.get("schema_version") != TIF_PROJECT_SCHEMA_VERSION:
            raise ValueError(f"unsupported_tif_project_schema:{payload.get('schema_version')}")
        if payload.get("project_type") != TIF_PROJECT_TYPE:
            raise ValueError(f"not_tif_volume_project:{payload.get('project_type')}")
        self.current_project_path = os.path.abspath(path)
        self.project_data = self._normalize_loaded_project_data(payload)
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
        self.project_data["updated_at"] = _now_iso()
        if self.is_sqlite_project():
            from .tif_sqlite_writer import flush_tif_project_changes

            return flush_tif_project_changes(self)
        if not getattr(self, "_legacy_json_write_enabled", False):
            raise RuntimeError("legacy_tif_json_project_is_read_only; migrate to SQLite or export a legacy JSON copy")
        project_path = os.path.abspath(self.current_project_path)
        os.makedirs(os.path.dirname(project_path), exist_ok=True)
        self._backup_current_project_file(project_path)
        atomic_write_json(project_path, self.legacy_json_payload(project_path), indent=2, ensure_ascii=False)

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
        for specimen in payload.get("specimens", []) if isinstance(payload.get("specimens"), list) else []:
            if not isinstance(specimen, dict):
                continue
            for key in ("metadata_ref", "material_map"):
                if specimen.get(key):
                    specimen[key] = self._relative_to_project_path(specimen.get(key), target_project_path)
            self._rebase_volume_record_paths(specimen.get("working_volume"), target_project_path)
            labels = specimen.get("labels", {})
            if isinstance(labels, dict):
                for role in ("manual_truth", "working_edit"):
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
        if save:
            self.save_project()
        return specimen

    def register_working_volume(self, specimen_id, path, shape_zyx, dtype, spacing_zyx=None, spacing_unit="micrometer", orientation="unknown", fmt=VOLUME_SIDECAR_FORMAT, save=True):
        specimen = self._require_specimen(specimen_id)
        specimen["working_volume"] = self._volume_payload(path, shape_zyx, dtype, spacing_zyx, spacing_unit, orientation, fmt)
        if save:
            self.save_project()
        return specimen["working_volume"]

    def register_label_volume(self, specimen_id, role, path, shape_zyx, dtype, status="available", spacing_zyx=None, spacing_unit="micrometer", orientation="unknown", fmt=VOLUME_SIDECAR_FORMAT, save=True):
        if role not in {"manual_truth", "working_edit"}:
            raise ValueError(f"unsupported_label_role:{role}")
        specimen = self._require_specimen(specimen_id)
        specimen["labels"][role] = self._volume_payload(path, shape_zyx, dtype, spacing_zyx, spacing_unit, orientation, fmt)
        specimen["labels"][role]["status"] = str(status or "available")
        if save:
            self.save_project()
        return specimen["labels"][role]

    def add_model_draft(self, specimen_id, path, shape_zyx, dtype, prediction_id, source_model="", spacing_zyx=None, spacing_unit="micrometer", orientation="unknown", fmt=VOLUME_SIDECAR_FORMAT, save=True):
        specimen = self._require_specimen(specimen_id)
        draft = self._volume_payload(path, shape_zyx, dtype, spacing_zyx, spacing_unit, orientation, fmt)
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
        if os.path.normcase(os.path.abspath(source_abs)) == os.path.normcase(os.path.abspath(target_abs)):
            raise ValueError(f"source_target_label_same:{source_role}")
        metadata = copy_volume_sidecar(source_abs, target_abs, role="working_edit")
        specimen["labels"]["working_edit"] = self._volume_payload(
            target_path,
            metadata["shape_zyx"],
            metadata["dtype"],
            metadata.get("spacing_zyx"),
            metadata.get("spacing_unit", "micrometer"),
            metadata.get("orientation", "unknown"),
            metadata.get("format", VOLUME_SIDECAR_FORMAT),
        )
        specimen["labels"]["working_edit"]["status"] = f"copied_from_{source_role}"
        specimen["review_status"] = "in_progress"
        specimen["train_ready"] = False
        if save:
            self.save_project()
        return specimen["labels"]["working_edit"]

    def promote_working_edit_to_manual_truth(self, specimen_id, mark_train_ready=True, save=True):
        specimen = self._require_specimen(specimen_id)
        working = (specimen.get("labels") or {}).get("working_edit") or {}
        source_path = working.get("path", "")
        if not source_path:
            raise ValueError("working_edit_missing")
        target_path = (specimen.get("labels") or {}).get("manual_truth", {}).get("path")
        if not target_path:
            target_path = os.path.join(self.specimen_dir(specimen_id), "labels", "manual_truth.ome.zarr").replace("\\", "/")
        source_abs = self.to_absolute(source_path)
        target_abs = self.to_absolute(target_path)
        if os.path.normcase(os.path.abspath(source_abs)) == os.path.normcase(os.path.abspath(target_abs)):
            raise ValueError("working_edit_manual_truth_same_path")
        metadata = copy_volume_sidecar(source_abs, target_abs, role="manual_truth")
        specimen["labels"]["manual_truth"] = self._volume_payload(
            target_path,
            metadata["shape_zyx"],
            metadata["dtype"],
            metadata.get("spacing_zyx"),
            metadata.get("spacing_unit", "micrometer"),
            metadata.get("orientation", "unknown"),
            metadata.get("format", VOLUME_SIDECAR_FORMAT),
        )
        specimen["labels"]["manual_truth"]["status"] = "reviewed"
        specimen["review_status"] = "train_ready" if mark_train_ready else "reviewed"
        specimen["train_ready"] = bool(mark_train_ready)
        if save:
            self.save_project()
        return specimen["labels"]["manual_truth"]

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
            "material_map_exists": "material_map_missing",
            "shape_matches": "image_label_shape_mismatch",
            "has_trainable_material": "no_trainable_material",
        }
        for key, passed in checks.items():
            if not passed:
                reasons.append(reason_labels[key])

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
            "image": self._normalize_volume_record(image),
            "mask": self._normalize_volume_record(mask),
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

    def discard_part(self, specimen_id, part_id, remove_storage=True, save=True):
        specimen = self._require_specimen(specimen_id)
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

        removed_storage = False
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
                shutil.rmtree(part_root)
                removed_storage = True

        if save and (removed_part is not None or removed_storage):
            self.save_project()
        return {"removed_part": removed_part is not None, "removed_storage": removed_storage}

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
        if is_safe_storage and os.path.exists(specimen_root):
            shutil.rmtree(specimen_root)
            removed_storage = True

        if save and (removed_specimen or removed_storage):
            self.save_project()
        return {"removed_specimen": removed_specimen, "removed_storage": removed_storage}

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
                "spacing_unit": "micrometer",
                "orientation": "unknown",
            }
        clean = dict(record)
        clean["path"] = self.to_relative(clean.get("path", ""))
        clean.setdefault("format", "")
        clean.setdefault("shape_zyx", [])
        clean.setdefault("dtype", "")
        clean.setdefault("spacing_zyx", [])
        clean.setdefault("spacing_unit", "micrometer")
        clean.setdefault("orientation", "unknown")
        return clean

    def _normalize_labels(self, labels):
        source = labels if isinstance(labels, dict) else {}
        return {
            "manual_truth": self._normalize_volume_record(source.get("manual_truth")),
            "working_edit": self._normalize_volume_record(source.get("working_edit")),
            "model_drafts": list(source.get("model_drafts", [])) if isinstance(source.get("model_drafts", []), list) else [],
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
            "image": self._normalize_volume_record(source.get("image")),
            "mask": self._normalize_volume_record(source.get("mask")),
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

    def _volume_payload(self, path, shape_zyx, dtype, spacing_zyx=None, spacing_unit="micrometer", orientation="unknown", fmt=VOLUME_SIDECAR_FORMAT):
        shape = [int(value) for value in (shape_zyx or [])]
        spacing = [float(value) for value in (spacing_zyx or [])] if spacing_zyx else []
        return {
            "path": self.to_relative(path),
            "format": str(fmt or ""),
            "shape_zyx": shape,
            "dtype": str(dtype or ""),
            "spacing_zyx": spacing,
            "spacing_unit": str(spacing_unit or "micrometer"),
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

    def _normalize_model_record(self, record):
        source = record if isinstance(record, dict) else {}
        if self._is_local_axis_model_record(source):
            return self._normalize_local_axis_model(source)
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
