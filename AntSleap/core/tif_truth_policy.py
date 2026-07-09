from .tif_label_guard import (
    ROLE_EDITABLE_AI_RESULT,
    ROLE_MANUAL_TRUTH,
    ROLE_MODEL_DRAFT,
    ROLE_RAW_AI_PREDICTION_BACKUP,
    ROLE_WORKING_EDIT,
    allow,
    deny,
)


PROMOTABLE_TRUTH_SOURCES = {ROLE_WORKING_EDIT, ROLE_EDITABLE_AI_RESULT}


def can_promote_to_manual_truth(
    source_role,
    *,
    explicit_review=False,
    review_ready=True,
    opened_for_review=None,
    require_opened_for_review=False,
    audit_metadata=None,
):
    clean_source = str(source_role or "").strip()
    details = {
        "source_role": clean_source,
        "explicit_review": bool(explicit_review),
        "review_ready": bool(review_ready),
        "opened_for_review": opened_for_review,
        "require_opened_for_review": bool(require_opened_for_review),
        "audit_keys": sorted((audit_metadata or {}).keys()) if isinstance(audit_metadata, dict) else [],
    }
    if not explicit_review:
        return deny("manual_truth_requires_explicit_review", details=details)
    if clean_source == ROLE_RAW_AI_PREDICTION_BACKUP:
        return deny("raw_ai_prediction_backup_cannot_be_promoted_to_manual_truth", details=details)
    if clean_source == ROLE_MODEL_DRAFT:
        return deny("model_draft_cannot_be_promoted_to_manual_truth", details=details)
    if clean_source == ROLE_MANUAL_TRUTH:
        return allow("manual_truth_already_reviewed", details=details)
    if clean_source not in PROMOTABLE_TRUTH_SOURCES:
        return deny("unsupported_manual_truth_source_role", details=details)
    if not review_ready:
        return deny("manual_truth_source_not_review_ready", details=details)
    if require_opened_for_review and opened_for_review is False:
        return deny("manual_truth_source_not_opened_for_review", details=details)
    return allow("manual_truth_promotion_policy_allowed", details=details)


def can_use_role_for_training(role, *, status="", record_exists=True):
    clean_role = str(role or "").strip()
    clean_status = str(status or "").strip()
    details = {"role": clean_role, "status": clean_status, "record_exists": bool(record_exists)}
    if clean_role != ROLE_MANUAL_TRUTH:
        return deny("training_requires_manual_truth", details=details)
    if not record_exists:
        return deny("manual_truth_missing", details=details)
    return allow("training_manual_truth_allowed", details=details)
