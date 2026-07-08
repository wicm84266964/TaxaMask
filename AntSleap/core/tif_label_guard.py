from dataclasses import dataclass, field


ROLE_WORKING_EDIT = "working_edit"
ROLE_EDITABLE_AI_RESULT = "editable_ai_result"
ROLE_RAW_AI_PREDICTION_BACKUP = "raw_ai_prediction_backup"
ROLE_MANUAL_TRUTH = "manual_truth"
ROLE_MODEL_DRAFT = "model_draft"

EDITABLE_LABEL_ROLES = {ROLE_WORKING_EDIT, ROLE_EDITABLE_AI_RESULT}
READ_ONLY_LABEL_ROLES = {ROLE_RAW_AI_PREDICTION_BACKUP, ROLE_MODEL_DRAFT}
TRAINING_TRUTH_ROLE = ROLE_MANUAL_TRUTH

TOP_LEVEL_REVIEW_ROLE = ROLE_WORKING_EDIT
PART_REVIEW_ROLE = ROLE_EDITABLE_AI_RESULT
RAW_BACKUP_ROLE = ROLE_RAW_AI_PREDICTION_BACKUP


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    reason: str = ""
    message_key: str = ""
    details: dict = field(default_factory=dict)

    def __bool__(self):
        return bool(self.allowed)

    def to_dict(self):
        return {
            "allowed": bool(self.allowed),
            "reason": str(self.reason or ""),
            "message_key": str(self.message_key or ""),
            "details": dict(self.details or {}),
        }


def allow(reason="allowed", message_key="", **details):
    payload = details.get("details") if set(details.keys()) == {"details"} and isinstance(details.get("details"), dict) else details
    return GuardResult(True, reason=str(reason or "allowed"), message_key=str(message_key or ""), details=dict(payload or {}))


def deny(reason, message_key="", **details):
    payload = details.get("details") if set(details.keys()) == {"details"} and isinstance(details.get("details"), dict) else details
    return GuardResult(False, reason=str(reason or "denied"), message_key=str(message_key or reason or "denied"), details=dict(payload or {}))


def ensure_allowed(result, prefix="tif_guard_denied"):
    if result:
        return result
    payload = result.to_dict() if isinstance(result, GuardResult) else {"allowed": False, "reason": str(result)}
    raise ValueError(f"{prefix}:{payload.get('reason', 'denied')}:{payload.get('details', {})}")


def _operation(value):
    return str(value or "").strip()


def _role(value):
    return str(value or "").strip()


def _has_audit_metadata(audit_metadata):
    if not isinstance(audit_metadata, dict):
        return False
    for key in ("prediction_id", "source_model", "source_path", "run_id", "import_report", "reviewed_by", "review_action"):
        if str(audit_metadata.get(key) or "").strip():
            return True
    return False


def can_write_label_role(
    role,
    *,
    operation="",
    source_role="",
    explicit_review=False,
    audit_metadata=None,
    overwrite_existing=False,
):
    clean_role = _role(role)
    clean_operation = _operation(operation)
    clean_source_role = _role(source_role)
    audit = dict(audit_metadata or {}) if isinstance(audit_metadata, dict) else {}
    details = {
        "role": clean_role,
        "operation": clean_operation,
        "source_role": clean_source_role,
        "explicit_review": bool(explicit_review),
        "overwrite_existing": bool(overwrite_existing),
    }

    if clean_role == ROLE_WORKING_EDIT:
        allowed_ops = {
            "register_label_volume",
            "register_existing_label_record",
            "create_empty_edit_layer",
            "edit",
            "manual_save",
            "auto_save",
            "copy_label_layer_to_working_edit",
            "prediction_review_import",
            "top_level_prediction_review_import",
        }
        if clean_operation in allowed_ops:
            return allow("working_edit_write_allowed", details=details)
        return deny("working_edit_operation_not_allowed", details=details)

    if clean_role == ROLE_EDITABLE_AI_RESULT:
        allowed_ops = {
            "register_part_label_volume",
            "register_existing_label_record",
            "create_empty_edit_layer",
            "edit",
            "manual_save",
            "auto_save",
            "prediction_review_import",
            "part_prediction_review_import",
        }
        if clean_operation in allowed_ops:
            return allow("editable_ai_result_write_allowed", details=details)
        return deny("editable_ai_result_operation_not_allowed", details=details)

    if clean_role == ROLE_RAW_AI_PREDICTION_BACKUP:
        allowed_ops = {"prediction_raw_backup_import", "register_existing_label_record"}
        if clean_operation not in allowed_ops:
            return deny("raw_ai_prediction_backup_is_read_only", details=details)
        if clean_operation == "prediction_raw_backup_import" and not _has_audit_metadata(audit):
            return deny("raw_ai_prediction_backup_requires_audit_metadata", details={**details, "audit_keys": sorted(audit.keys())})
        return allow("raw_ai_prediction_backup_audit_write_allowed", details={**details, "audit_keys": sorted(audit.keys())})

    if clean_role == ROLE_MANUAL_TRUTH:
        promotion_ops = {
            "truth_promotion",
            "explicit_review_promotion",
            "promote_working_edit_to_manual_truth",
            "promote_editable_ai_result_to_manual_truth",
        }
        registration_ops = {
            "register_existing_label_record",
            "reviewed_truth_import",
            "amira_truth_import",
        }
        if clean_operation in promotion_ops:
            if not explicit_review:
                return deny("manual_truth_requires_explicit_review", details=details)
            return allow("manual_truth_promotion_allowed", details=details)
        if clean_operation in registration_ops:
            return allow("manual_truth_existing_record_registration_allowed", details=details)
        return deny("manual_truth_write_not_allowed_without_review", details=details)

    if clean_role == ROLE_MODEL_DRAFT:
        if clean_operation in {"model_draft_import", "register_existing_label_record"}:
            return allow("model_draft_write_allowed", details=details)
        return deny("model_draft_is_not_editable_training_truth", details=details)

    return deny("unknown_label_role", details=details)


def require_editable_label_role(role, *, scope="top_level"):
    clean_role = _role(role)
    clean_scope = str(scope or "top_level").strip()
    required = PART_REVIEW_ROLE if clean_scope in {"part", "part_reslice"} else TOP_LEVEL_REVIEW_ROLE
    details = {"role": clean_role, "scope": clean_scope, "required_role": required}
    if clean_role == required:
        return allow("editable_label_role_allowed", details=details)
    if clean_role == ROLE_RAW_AI_PREDICTION_BACKUP:
        return deny("raw_ai_prediction_backup_is_read_only", details=details)
    if clean_role == ROLE_MANUAL_TRUTH:
        return deny("manual_truth_is_not_directly_editable", details=details)
    if clean_role == ROLE_MODEL_DRAFT:
        return deny("model_draft_is_read_only", details=details)
    return deny("label_role_not_editable_for_scope", details=details)
