import json
import os
from datetime import datetime

from .tif_materials import has_trainable_material, read_material_map, write_material_map
from .tif_volume_io import VOLUME_SIDECAR_FORMAT, copy_volume_sidecar, read_volume_metadata, volume_sidecar_exists


TIF_PROJECT_SCHEMA_VERSION = "ant3d_tif_project_v1"
TIF_PROJECT_TYPE = "tif_volume"
DEFAULT_TIF_PROJECT_FILENAME = "project.json"
TIF_REVIEW_STATUSES = {"not_started", "in_progress", "fully_annotated", "reviewed", "train_ready"}


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_path_fragment(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    return clean.strip("_") or "specimen"


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
    }


class TifProjectManager:
    def __init__(self):
        self.project_data = _default_project_data()
        self.current_project_path = None

    @property
    def project_dir(self):
        if not self.current_project_path:
            return os.getcwd()
        return os.path.dirname(os.path.abspath(self.current_project_path))

    def create_project(self, name, project_dir, project_id=None):
        os.makedirs(project_dir, exist_ok=True)
        self.project_data = _default_project_data(name=name, project_id=project_id)
        self.current_project_path = os.path.join(os.path.abspath(project_dir), DEFAULT_TIF_PROJECT_FILENAME)
        self.save_project()
        return self.current_project_path

    def load_project(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("tif_project_json_not_object")
        if payload.get("schema_version") != TIF_PROJECT_SCHEMA_VERSION:
            raise ValueError(f"unsupported_tif_project_schema:{payload.get('schema_version')}")
        if payload.get("project_type") != TIF_PROJECT_TYPE:
            raise ValueError(f"not_tif_volume_project:{payload.get('project_type')}")
        specimens = payload.get("specimens", [])
        if not isinstance(specimens, list):
            raise ValueError("tif_project_specimens_not_list")
        payload.setdefault("models", [])
        payload.setdefault("runs", [])
        payload.setdefault("updated_at", payload.get("created_at", _now_iso()))
        self.project_data = payload
        self.current_project_path = os.path.abspath(path)
        return self.project_data

    def save_project(self):
        if not self.current_project_path:
            raise ValueError("tif_project_path_not_set")
        self.project_data["updated_at"] = _now_iso()
        os.makedirs(os.path.dirname(os.path.abspath(self.current_project_path)), exist_ok=True)
        with open(self.current_project_path, "w", encoding="utf-8") as handle:
            json.dump(self.project_data, handle, ensure_ascii=False, indent=2)

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

    def create_specimen_scaffold(self, specimen_id, material_map=None, modality="unknown", metadata_ref="", display_name=""):
        specimen_root = self.to_absolute(self.specimen_dir(specimen_id))
        for rel in ("source/raw", "source/amira_original", "working", "labels/model_draft", "exports", "logs"):
            os.makedirs(os.path.join(specimen_root, rel), exist_ok=True)
        material_map_rel = os.path.join(self.specimen_dir(specimen_id), "material_map.json").replace("\\", "/")
        write_material_map(self.to_absolute(material_map_rel), material_map or {}, source=(material_map or {}).get("source", "manual") if isinstance(material_map, dict) else "manual")
        specimen = self.add_specimen(
            specimen_id,
            display_name=display_name or specimen_id,
            metadata_ref=metadata_ref,
            modality=modality,
            material_map=material_map_rel,
            save=False,
        )
        self.save_project()
        return specimen

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
        save=True,
    ):
        clean_id = str(specimen_id or "").strip()
        if not clean_id:
            raise ValueError("specimen_id_required")
        if self.get_specimen(clean_id, default=None) is not None:
            raise ValueError(f"duplicate_specimen_id:{clean_id}")
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
        metadata = copy_volume_sidecar(self.to_absolute(source_path), self.to_absolute(target_path), role="working_edit")
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
        metadata = copy_volume_sidecar(self.to_absolute(source_path), self.to_absolute(target_path), role="manual_truth")
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

    def _require_specimen(self, specimen_id):
        specimen = self.get_specimen(specimen_id, default=None)
        if specimen is None:
            raise KeyError(f"unknown_specimen_id:{specimen_id}")
        return specimen

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
