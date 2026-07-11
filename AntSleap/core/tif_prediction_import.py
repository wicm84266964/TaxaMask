import json
import copy
import os
import shutil
import uuid
from datetime import datetime

import numpy as np
import tifffile

from .safe_io import atomic_write_json
from .tif_prediction_policy import can_import_prediction_target, validate_external_prediction_import
from .tif_project import TifProjectManager
from .tif_write_guard import WriteIntent, ensure_write_allowed
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


def _require_guard(result, prefix):
    if result:
        return result
    reason = getattr(result, "reason", "denied")
    details = getattr(result, "details", {})
    raise ValueError(f"{prefix}:{reason}:{details}")


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
    validation = validate_external_prediction_import(
        specimen_id=clean_specimen_id,
        prediction_shape_zyx=label_shape,
        expected_shape_zyx=working_shape,
        dtype=volume.dtype,
    )
    if not validation:
        if validation.reason == "external_prediction_shape_mismatch":
            raise ValueError(f"external_prediction_shape_mismatch:{clean_specimen_id}:{label_shape}:{working_shape}")
        raise ValueError(f"external_prediction_import_guard_denied:{validation.reason}:{validation.details}")

    safe_prediction_id = _safe_prediction_id(prediction_id or default_prediction_id_for_tif(source_path))
    source_model_text = str(source_model or "external_tif")
    common_metadata = {
        "source_path": source_path,
        "prediction_id": safe_prediction_id,
        "source_model": source_model_text,
        "import_adapter": TIF_EXTERNAL_PREDICTION_IMPORT_ADAPTER_VERSION,
        "note": "External prediction label TIF imported as editable review result; not training truth.",
    }
    _require_guard(
        can_import_prediction_target(
            "raw_ai_prediction_backup",
            source_role="external_prediction_tif",
            overwrite_existing=True,
            audit_metadata=common_metadata,
        ),
        "tif_prediction_policy_denied",
    )
    _require_guard(
        can_import_prediction_target(
            "working_edit",
            source_role="external_prediction_tif",
            overwrite_existing=True,
            audit_metadata=common_metadata,
        ),
        "tif_prediction_policy_denied",
    )
    _require_guard(
        can_import_prediction_target(
            "model_draft",
            source_role="external_prediction_tif",
            overwrite_existing=False,
            audit_metadata=common_metadata,
        ),
        "tif_prediction_policy_denied",
    )
    backup_rel = os.path.join(
        project_manager.specimen_dir(clean_specimen_id),
        "labels",
        "raw_ai_prediction_backup.ome.zarr",
    ).replace("\\", "/")
    editable_rel = os.path.join(
        project_manager.specimen_dir(clean_specimen_id),
        "labels",
        "working_edit.ome.zarr",
    ).replace("\\", "/")
    draft_rel = os.path.join(
        project_manager.specimen_dir(clean_specimen_id),
        "labels",
        "model_draft",
        f"{safe_prediction_id}.ome.zarr",
    ).replace("\\", "/")
    backup_abs = project_manager.to_absolute(backup_rel)
    editable_abs = project_manager.to_absolute(editable_rel)
    draft_abs = project_manager.to_absolute(draft_rel)
    if os.path.exists(draft_abs):
        raise FileExistsError(draft_abs)
    for target_abs, target_role, allow_overwrite in (
        (backup_abs, "raw_ai_prediction_backup", True),
        (editable_abs, "working_edit", True),
        (draft_abs, "model_draft", False),
    ):
        ensure_write_allowed(
            WriteIntent(
                target_path=target_abs,
                project_root=project_manager.project_dir,
                source_path=source_path,
                source_role="external_prediction_tif",
                target_role=target_role,
                operation="external_prediction_import",
                audit_metadata=common_metadata,
                allow_overwrite=allow_overwrite,
                allowed_roots=(project_manager.project_dir,),
            )
        )

    report_rel = os.path.join(
        project_manager.specimen_dir(clean_specimen_id),
        "labels",
        "import_reports",
        f"{safe_prediction_id}_import_report.json",
    ).replace("\\", "/")
    report_abs = project_manager.to_absolute(report_rel)
    if os.path.exists(report_abs):
        raise FileExistsError(report_abs)

    draft = None
    labels = specimen.setdefault("labels", {})
    specimen_snapshot = copy.deepcopy(specimen)
    previous_train_ready = bool(specimen.get("train_ready"))
    working_edit_existed = bool(str((labels.get("working_edit") or {}).get("path") or "").strip())
    transaction_id = uuid.uuid4().hex
    sidecar_swaps = []

    def write_and_install(target_path, *, role, extra_metadata):
        staged_path = f"{target_path}.pending_{transaction_id}"
        rollback_path = f"{target_path}.rollback_{transaction_id}"
        swap = {
            "target": target_path,
            "staged": staged_path,
            "rollback": rollback_path,
            "rollback_moved": False,
            "installed": False,
        }
        sidecar_swaps.append(swap)
        metadata = write_volume_sidecar(
            staged_path,
            volume,
            role=role,
            spacing_zyx=working_meta.get("spacing_zyx") or working_record.get("spacing_zyx"),
            spacing_unit=working_meta.get("spacing_unit", working_record.get("spacing_unit", "micrometer")),
            orientation=working_meta.get("orientation", working_record.get("orientation", "unknown")),
            source_format="external_prediction_tif",
            extra_metadata=extra_metadata,
        )
        if os.path.exists(target_path):
            os.replace(target_path, rollback_path)
            swap["rollback_moved"] = True
        os.replace(staged_path, target_path)
        swap["installed"] = True
        return metadata

    try:
        backup_meta = write_and_install(
            backup_abs,
            role="raw_ai_prediction_backup",
            extra_metadata=common_metadata,
        )
        editable_meta = write_and_install(
            editable_abs,
            role="working_edit",
            extra_metadata=common_metadata,
        )
        draft_meta = write_and_install(
            draft_abs,
            role="model_draft",
            extra_metadata={**common_metadata, "note": "Legacy read-only copy of the external prediction label TIF."},
        )
        labels["raw_ai_prediction_backup"] = project_manager._volume_payload(
            backup_rel,
            backup_meta["shape_zyx"],
            backup_meta["dtype"],
            backup_meta.get("spacing_zyx"),
            backup_meta.get("spacing_unit", "micrometer"),
            backup_meta.get("orientation", "unknown"),
            backup_meta.get("format", ""),
        )
        labels["raw_ai_prediction_backup"]["role"] = "raw_ai_prediction_backup"
        labels["raw_ai_prediction_backup"]["status"] = "raw_backup"
        labels["raw_ai_prediction_backup"]["prediction_id"] = safe_prediction_id
        labels["raw_ai_prediction_backup"]["source_model"] = source_model_text
        editable = project_manager.register_label_volume(
            clean_specimen_id,
            "working_edit",
            editable_rel,
            editable_meta["shape_zyx"],
            editable_meta["dtype"],
            status="pending_review",
            spacing_zyx=editable_meta.get("spacing_zyx"),
            spacing_unit=editable_meta.get("spacing_unit", "micrometer"),
            orientation=editable_meta.get("orientation", "unknown"),
            fmt=editable_meta.get("format", ""),
            save=False,
            operation="prediction_review_import",
            audit_metadata=common_metadata,
        )
        editable["prediction_id"] = safe_prediction_id
        editable["source_model"] = source_model_text
        draft = project_manager.add_model_draft(
            clean_specimen_id,
            draft_rel,
            draft_meta["shape_zyx"],
            draft_meta["dtype"],
            prediction_id=safe_prediction_id,
            source_model=source_model_text,
            spacing_zyx=draft_meta.get("spacing_zyx"),
            spacing_unit=draft_meta.get("spacing_unit", "micrometer"),
            orientation=draft_meta.get("orientation", "unknown"),
            fmt=draft_meta.get("format", ""),
            save=False,
        )
        specimen["review_status"] = "pending_review"
        specimen["train_ready"] = False
        report = {
            "schema_version": TIF_EXTERNAL_PREDICTION_IMPORT_REPORT_SCHEMA_VERSION,
            "imported_at": _now_iso(),
            "adapter_version": TIF_EXTERNAL_PREDICTION_IMPORT_ADAPTER_VERSION,
            "source_file": source_path,
            "specimen_id": clean_specimen_id,
            "prediction_id": safe_prediction_id,
            "source_model": source_model_text,
            "files": {
                "raw_ai_prediction_backup": backup_rel,
                "working_edit": editable_rel,
                "model_draft": draft_rel,
                "import_report": report_rel,
            },
            "shapes": {
                "working_image_zyx": working_shape,
                "prediction_label_zyx": label_shape,
            },
            "dtype": {
                "prediction_label": str(volume.dtype),
                "raw_ai_prediction_backup": backup_meta["dtype"],
                "working_edit": editable_meta["dtype"],
                "model_draft": draft_meta["dtype"],
            },
            "safety": {
                "imported_role": "working_edit",
                "review_status": "pending_review",
                "working_edit_overwritten": working_edit_existed,
                "manual_truth_overwritten": False,
                "train_ready_changed": previous_train_ready,
            },
            "warnings": [],
            "errors": [],
        }
        atomic_write_json(report_abs, report, indent=2, ensure_ascii=False)
        draft["import_report"] = report_rel
        editable["import_report"] = report_rel
        labels["raw_ai_prediction_backup"]["import_report"] = report_rel
        project_manager.save_project()
    except Exception as exc:
        rollback_errors = []
        specimen.clear()
        specimen.update(specimen_snapshot)
        for swap in reversed(sidecar_swaps):
            try:
                if swap["installed"] and os.path.exists(swap["target"]):
                    shutil.rmtree(swap["target"])
                if swap["rollback_moved"] and os.path.exists(swap["rollback"]):
                    os.replace(swap["rollback"], swap["target"])
                if os.path.exists(swap["staged"]):
                    shutil.rmtree(swap["staged"])
            except Exception as rollback_exc:
                rollback_errors.append(f"{swap['target']}:{rollback_exc}")
        if os.path.exists(report_abs):
            try:
                os.remove(report_abs)
            except OSError as rollback_exc:
                rollback_errors.append(f"{report_abs}:{rollback_exc}")
        if rollback_errors:
            raise RuntimeError(
                f"external_prediction_import_failed:{exc};rollback_failed:{'|'.join(rollback_errors)}"
            ) from exc
        raise

    for swap in sidecar_swaps:
        if swap["rollback_moved"] and os.path.exists(swap["rollback"]):
            shutil.rmtree(swap["rollback"], ignore_errors=True)

    return {
        "working_edit": labels.get("working_edit") or {},
        "raw_ai_prediction_backup": labels.get("raw_ai_prediction_backup") or {},
        "draft": draft,
        "report": report,
        "report_path": report_abs,
    }
