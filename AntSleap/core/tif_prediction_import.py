import json
import os
import shutil
from datetime import datetime

import numpy as np
import tifffile

from .safe_io import atomic_write_json
from .tif_project import TifProjectManager
from .tif_volume_io import read_volume_metadata, volume_sidecar_exists, write_volume_sidecar


TIF_EXTERNAL_PREDICTION_IMPORT_REPORT_SCHEMA_VERSION = "ant3d_external_prediction_tif_import_report_v1"
TIF_EXTERNAL_PREDICTION_IMPORT_ADAPTER_VERSION = "external_prediction_tif_import_adapter_v1"


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _now_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_prediction_id(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)
    return clean.strip("_") or f"external_prediction_{_now_stamp()}"


def default_prediction_id_for_tif(tif_path):
    stem = os.path.splitext(os.path.basename(str(tif_path or "")))[0]
    return _safe_prediction_id(f"{stem}_{_now_stamp()}")


def _read_label_tif(path):
    array = tifffile.imread(path)
    volume = np.asarray(array)
    if volume.ndim > 3:
        squeezed = np.squeeze(volume)
        if squeezed.ndim == 3:
            volume = squeezed
        else:
            raise ValueError(f"unsupported_prediction_tif_dimensions:{volume.shape}")
    if volume.ndim != 3:
        raise ValueError(f"external_prediction_tif_must_be_3d:{volume.shape}")
    if not np.issubdtype(volume.dtype, np.integer):
        raise ValueError(f"prediction_label_tif_must_be_integer_dtype:{volume.dtype}")
    return volume


def import_external_prediction_tif(
    project_manager,
    specimen_id,
    tif_path,
    prediction_id="",
    source_model="external_tif",
):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    clean_specimen_id = str(specimen_id or "").strip()
    if not clean_specimen_id:
        raise ValueError("specimen_id_required")
    source_path = os.path.abspath(str(tif_path))
    if not os.path.exists(source_path):
        raise FileNotFoundError(source_path)
    if os.path.splitext(source_path)[1].lower() not in {".tif", ".tiff"}:
        raise ValueError(f"not_tif_file:{source_path}")

    specimen = project_manager.get_specimen(clean_specimen_id, default=None)
    if specimen is None:
        raise KeyError(f"unknown_specimen_id:{clean_specimen_id}")
    working_record = specimen.get("working_volume") or {}
    working_path = project_manager.to_absolute(working_record.get("path", ""))
    if not working_path or not volume_sidecar_exists(working_path):
        raise ValueError(f"working_volume_missing:{clean_specimen_id}")

    working_meta = read_volume_metadata(working_path)
    working_shape = [int(value) for value in working_meta.get("shape_zyx", working_record.get("shape_zyx", []))]
    volume = _read_label_tif(source_path)
    label_shape = [int(value) for value in volume.shape]
    if label_shape != working_shape:
        raise ValueError(f"external_prediction_shape_mismatch:{clean_specimen_id}:{label_shape}:{working_shape}")

    safe_prediction_id = _safe_prediction_id(prediction_id or default_prediction_id_for_tif(source_path))
    draft_rel = os.path.join(
        project_manager.specimen_dir(clean_specimen_id),
        "labels",
        "model_draft",
        f"{safe_prediction_id}.ome.zarr",
    ).replace("\\", "/")
    draft_abs = project_manager.to_absolute(draft_rel)
    if os.path.exists(draft_abs):
        raise FileExistsError(draft_abs)

    report_rel = os.path.join(
        project_manager.specimen_dir(clean_specimen_id),
        "labels",
        "model_draft",
        f"{safe_prediction_id}_import_report.json",
    ).replace("\\", "/")
    report_abs = project_manager.to_absolute(report_rel)
    if os.path.exists(report_abs):
        raise FileExistsError(report_abs)

    source_model_text = str(source_model or "external_tif")
    draft = None
    try:
        metadata = write_volume_sidecar(
            draft_abs,
            volume,
            role="model_draft",
            spacing_zyx=working_meta.get("spacing_zyx") or working_record.get("spacing_zyx"),
            spacing_unit=working_meta.get("spacing_unit", working_record.get("spacing_unit", "micrometer")),
            orientation=working_meta.get("orientation", working_record.get("orientation", "unknown")),
            source_format="external_prediction_tif",
            extra_metadata={
                "source_path": source_path,
                "prediction_id": safe_prediction_id,
                "source_model": source_model_text,
                "import_adapter": TIF_EXTERNAL_PREDICTION_IMPORT_ADAPTER_VERSION,
                "note": "External prediction label TIF imported as model_draft only; not manual_truth.",
            },
        )
        draft = project_manager.add_model_draft(
            clean_specimen_id,
            draft_rel,
            metadata["shape_zyx"],
            metadata["dtype"],
            prediction_id=safe_prediction_id,
            source_model=source_model_text,
            spacing_zyx=metadata.get("spacing_zyx"),
            spacing_unit=metadata.get("spacing_unit", "micrometer"),
            orientation=metadata.get("orientation", "unknown"),
            fmt=metadata.get("format", ""),
            save=False,
        )
        report = {
            "schema_version": TIF_EXTERNAL_PREDICTION_IMPORT_REPORT_SCHEMA_VERSION,
            "imported_at": _now_iso(),
            "adapter_version": TIF_EXTERNAL_PREDICTION_IMPORT_ADAPTER_VERSION,
            "source_file": source_path,
            "specimen_id": clean_specimen_id,
            "prediction_id": safe_prediction_id,
            "source_model": source_model_text,
            "files": {
                "model_draft": draft_rel,
                "import_report": report_rel,
            },
            "shapes": {
                "working_image_zyx": working_shape,
                "prediction_label_zyx": label_shape,
            },
            "dtype": {
                "prediction_label": str(volume.dtype),
                "model_draft": metadata["dtype"],
            },
            "safety": {
                "imported_role": "model_draft",
                "manual_truth_overwritten": False,
                "train_ready_changed": False,
            },
            "warnings": [],
            "errors": [],
        }
        atomic_write_json(report_abs, report, indent=2, ensure_ascii=False)
        draft["import_report"] = report_rel
        project_manager.save_project()
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
