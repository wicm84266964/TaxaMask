from dataclasses import dataclass

import numpy as np

from .tif_label_guard import (
    ROLE_EDITABLE_AI_RESULT,
    ROLE_MANUAL_TRUTH,
    ROLE_MODEL_DRAFT,
    ROLE_RAW_AI_PREDICTION_BACKUP,
    ROLE_WORKING_EDIT,
    allow,
    can_write_label_role,
    deny,
)


@dataclass(frozen=True)
class PredictionImportPlan:
    scope: str
    review_role: str
    raw_backup_role: str = ROLE_RAW_AI_PREDICTION_BACKUP
    legacy_draft_role: str = ROLE_MODEL_DRAFT

    def to_dict(self):
        return {
            "scope": self.scope,
            "review_role": self.review_role,
            "raw_backup_role": self.raw_backup_role,
            "legacy_draft_role": self.legacy_draft_role,
        }


def prediction_import_plan(scope):
    clean_scope = str(scope or "top_level_volume").strip()
    if clean_scope in {"part", "part_reslice"}:
        return PredictionImportPlan(scope=clean_scope, review_role=ROLE_EDITABLE_AI_RESULT)
    if clean_scope in {"top_level", "top_level_volume", "specimen"}:
        return PredictionImportPlan(scope="top_level_volume", review_role=ROLE_WORKING_EDIT)
    raise ValueError(f"unsupported_prediction_import_scope:{scope}")


def _shape_list(value):
    try:
        return [int(item) for item in (value or [])]
    except TypeError:
        return []


def validate_prediction_volume(
    *,
    prediction_shape_zyx,
    expected_shape_zyx,
    dtype,
    context=None,
    shape_reason="prediction_shape_mismatch",
):
    prediction_shape = _shape_list(prediction_shape_zyx)
    expected_shape = _shape_list(expected_shape_zyx)
    details = {
        "prediction_shape_zyx": prediction_shape,
        "expected_shape_zyx": expected_shape,
        "dtype": str(dtype or ""),
        "context": dict(context or {}) if isinstance(context, dict) else {},
    }
    try:
        np_dtype = np.dtype(dtype)
    except TypeError:
        return deny("prediction_label_dtype_invalid", details=details)
    if len(prediction_shape) != 3:
        return deny("prediction_label_must_be_3d", details=details)
    if not np.issubdtype(np_dtype, np.integer):
        return deny("prediction_label_tif_must_be_integer_dtype", details=details)
    if prediction_shape != expected_shape:
        return deny(shape_reason, details=details)
    return allow("prediction_volume_matches_context", details=details)


def validate_external_prediction_import(
    *,
    specimen_id,
    prediction_shape_zyx,
    expected_shape_zyx,
    dtype,
    part_id="",
    reslice_id="",
):
    return validate_prediction_volume(
        prediction_shape_zyx=prediction_shape_zyx,
        expected_shape_zyx=expected_shape_zyx,
        dtype=dtype,
        context={
            "specimen_id": str(specimen_id or ""),
            "part_id": str(part_id or ""),
            "reslice_id": str(reslice_id or ""),
            "source": "external_prediction_tif",
        },
        shape_reason="external_prediction_shape_mismatch",
    )


def can_import_prediction_target(
    target_role,
    *,
    source_role="prediction_label_volume",
    overwrite_existing=False,
    audit_metadata=None,
):
    clean_target = str(target_role or "").strip()
    details = {
        "target_role": clean_target,
        "source_role": str(source_role or ""),
        "overwrite_existing": bool(overwrite_existing),
    }
    if clean_target == ROLE_MANUAL_TRUTH:
        return deny("prediction_import_must_not_target_manual_truth", details=details)
    if clean_target == ROLE_RAW_AI_PREDICTION_BACKUP:
        return can_write_label_role(
            clean_target,
            operation="prediction_raw_backup_import",
            source_role=source_role,
            audit_metadata=audit_metadata,
            overwrite_existing=overwrite_existing,
        )
    if clean_target in {ROLE_WORKING_EDIT, ROLE_EDITABLE_AI_RESULT}:
        return can_write_label_role(
            clean_target,
            operation="prediction_review_import",
            source_role=source_role,
            audit_metadata=audit_metadata,
            overwrite_existing=overwrite_existing,
        )
    if clean_target == ROLE_MODEL_DRAFT:
        return can_write_label_role(
            clean_target,
            operation="model_draft_import",
            source_role=source_role,
            audit_metadata=audit_metadata,
            overwrite_existing=overwrite_existing,
        )
    return deny("unsupported_prediction_import_target_role", details=details)
