from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from typing import Sequence

import numpy as np

from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import (
    load_volume_sidecar,
    read_volume_metadata,
    volume_sidecar_exists,
    write_volume_sidecar,
)

from .sample import TifBlinkSample


TIF_BLINK_PREDICTION_REPORT_SCHEMA_VERSION = "tif_blink_prediction_report_v1"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_id(value: str) -> str:
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)
    return clean.strip("_") or f"tif_blink_{_now_stamp()}"


def _require_manager(project_manager) -> TifProjectManager:
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    return project_manager


def load_train_ready_samples(
    project_manager: TifProjectManager,
    specimen_ids: Sequence[str] | None = None,
    require_train_ready: bool = True,
) -> list[TifBlinkSample]:
    manager = _require_manager(project_manager)
    if specimen_ids is None:
        specimens = manager.list_train_ready_specimens() if require_train_ready else manager.project_data.get("specimens", [])
    else:
        specimens = []
        for specimen_id in specimen_ids:
            specimen = manager.get_specimen(str(specimen_id), default=None)
            if specimen is None:
                raise KeyError(f"unknown_specimen_id:{specimen_id}")
            if require_train_ready:
                readiness = manager.evaluate_train_ready(str(specimen_id))
                if not readiness["train_ready"]:
                    raise ValueError(f"specimen_not_train_ready:{specimen_id}:{','.join(readiness['reasons'])}")
            specimens.append(specimen)

    samples: list[TifBlinkSample] = []
    for specimen in specimens:
        specimen_id = str(specimen.get("specimen_id") or "")
        working = specimen.get("working_volume") or {}
        manual = (specimen.get("labels") or {}).get("manual_truth") or {}
        image_path = manager.to_absolute(working.get("path", ""))
        label_path = manager.to_absolute(manual.get("path", ""))
        if not volume_sidecar_exists(image_path):
            raise FileNotFoundError(image_path)
        if not volume_sidecar_exists(label_path):
            raise FileNotFoundError(label_path)
        image = load_volume_sidecar(image_path)
        label = load_volume_sidecar(label_path)
        if tuple(image.shape) != tuple(label.shape):
            raise ValueError(f"image_label_shape_mismatch:{specimen_id}:{image.shape}:{label.shape}")
        samples.append(TifBlinkSample(image=image, label=label, specimen_id=specimen_id))
    return samples


def save_prediction_as_model_draft(
    project_manager: TifProjectManager,
    specimen_id: str,
    prediction: np.ndarray,
    prediction_id: str = "",
    source_model: str = "tif_blink",
    model_manifest: str = "",
) -> dict:
    manager = _require_manager(project_manager)
    clean_specimen_id = str(specimen_id or "").strip()
    if not clean_specimen_id:
        raise ValueError("specimen_id_required")
    specimen = manager.get_specimen(clean_specimen_id, default=None)
    if specimen is None:
        raise KeyError(f"unknown_specimen_id:{clean_specimen_id}")

    working = specimen.get("working_volume") or {}
    working_path = manager.to_absolute(working.get("path", ""))
    if not volume_sidecar_exists(working_path):
        raise ValueError(f"working_volume_missing:{clean_specimen_id}")
    working_meta = read_volume_metadata(working_path)
    working_shape = [int(value) for value in working_meta.get("shape_zyx", working.get("shape_zyx", []))]
    pred = np.asarray(prediction)
    if pred.ndim != 3:
        raise ValueError(f"prediction_must_be_zyx:{pred.shape}")
    if [int(value) for value in pred.shape] != working_shape:
        raise ValueError(f"prediction_shape_mismatch:{clean_specimen_id}:{list(pred.shape)}:{working_shape}")
    if not np.issubdtype(pred.dtype, np.integer):
        raise ValueError(f"prediction_must_be_integer_dtype:{pred.dtype}")

    safe_prediction_id = _safe_id(prediction_id or f"tif_blink_{clean_specimen_id}_{_now_stamp()}")
    draft_rel = os.path.join(
        manager.specimen_dir(clean_specimen_id),
        "labels",
        "model_draft",
        f"{safe_prediction_id}.ome.zarr",
    ).replace("\\", "/")
    draft_abs = manager.to_absolute(draft_rel)
    report_rel = os.path.join(
        manager.specimen_dir(clean_specimen_id),
        "labels",
        "model_draft",
        f"{safe_prediction_id}_prediction_report.json",
    ).replace("\\", "/")
    report_abs = manager.to_absolute(report_rel)
    if os.path.exists(draft_abs):
        raise FileExistsError(draft_abs)
    if os.path.exists(report_abs):
        raise FileExistsError(report_abs)

    draft = None
    try:
        metadata = write_volume_sidecar(
            draft_abs,
            pred,
            role="model_draft",
            spacing_zyx=working_meta.get("spacing_zyx") or working.get("spacing_zyx"),
            spacing_unit=working_meta.get("spacing_unit", working.get("spacing_unit", "micrometer")),
            orientation=working_meta.get("orientation", working.get("orientation", "unknown")),
            source_format="tif_blink_prediction",
            extra_metadata={
                "prediction_id": safe_prediction_id,
                "source_model": str(source_model or "tif_blink"),
                "model_manifest": str(model_manifest or ""),
                "note": "TIF-Blink prediction imported as model_draft only; manual_truth is not overwritten.",
            },
        )
        draft = manager.add_model_draft(
            clean_specimen_id,
            draft_rel,
            metadata["shape_zyx"],
            metadata["dtype"],
            prediction_id=safe_prediction_id,
            source_model=str(source_model or "tif_blink"),
            spacing_zyx=metadata.get("spacing_zyx"),
            spacing_unit=metadata.get("spacing_unit", "micrometer"),
            orientation=metadata.get("orientation", "unknown"),
            fmt=metadata.get("format", ""),
            save=False,
        )
        report = {
            "schema_version": TIF_BLINK_PREDICTION_REPORT_SCHEMA_VERSION,
            "created_at": _now_iso(),
            "specimen_id": clean_specimen_id,
            "prediction_id": safe_prediction_id,
            "source_model": str(source_model or "tif_blink"),
            "model_manifest": str(model_manifest or ""),
            "files": {
                "model_draft": draft_rel,
                "prediction_report": report_rel,
            },
            "shape_zyx": [int(value) for value in pred.shape],
            "dtype": str(pred.dtype),
            "safety": {
                "imported_role": "model_draft",
                "manual_truth_overwritten": False,
                "train_ready_changed": False,
            },
            "warnings": [],
            "errors": [],
        }
        os.makedirs(os.path.dirname(report_abs), exist_ok=True)
        with open(report_abs, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        draft["prediction_report"] = report_rel
        manager.save_project()
    except Exception:
        if draft is not None:
            drafts = ((specimen.get("labels") or {}).get("model_drafts") or [])
            specimen.setdefault("labels", {})["model_drafts"] = [
                item
                for item in drafts
                if item.get("path") != draft_rel and item.get("prediction_id") != safe_prediction_id
            ]
        if os.path.exists(draft_abs):
            shutil.rmtree(draft_abs, ignore_errors=True)
        if os.path.exists(report_abs):
            try:
                os.remove(report_abs)
            except OSError:
                pass
        raise

    return {
        "draft": draft,
        "report": report,
        "report_path": report_abs,
    }
