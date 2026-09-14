"""Researcher-facing TIF status labels. Display only; does not rewrite stored roles."""

from __future__ import annotations

REVIEW_STATUS_LABELS = {
    "not_started": "not yet started",
    "in_progress": "in progress",
    "fully_annotated": "fully annotated",
    "reviewed": "reviewed",
    "train_ready": "marked train-ready",
}

SYSTEM_STATUS_LABELS = {
    "cut_pending_labeling": "cut, pending labeling",
    "predicted_pending_review": "editable result pending review",
    "predicted_pending_review_model": "prediction pending review",
    "verified_train_ready": "reviewed for training",
    "failed": "failed",
    "draft": "draft",
    "exported": "exported",
}

TRAIN_READY_REASON_LABELS = {
    "manual_truth_missing": "Training truth is missing; accept the current editable labels as training truth first.",
    "part_not_marked_train_ready": "Part has not been marked as verified train-ready.",
    "part_record_missing": "Part record is missing.",
    "part_volume_missing": "Part image is missing.",
    "reslice_record_missing": "Reslice record is missing.",
    "reslice_output_missing": "Reslice image is missing.",
    "label_schema_missing": "Label schema is missing or empty.",
    "part_label_shape_mismatch": "Part label shape does not match the part/reslice image.",
    "unknown_label_ids": "Label IDs are not all defined in the bound label schema.",
    "label_volume_unreadable": "Label volume cannot be read.",
    "specimen_not_marked_train_ready": "Specimen has not been marked train-ready.",
    "working_volume_missing": "Working image is missing.",
    "material_map_missing": "Material map is missing.",
    "image_label_shape_mismatch": "Image and label shapes do not match.",
    "no_trainable_material": "No trainable material is defined in the material map.",
    "training_requires_manual_truth": "Training truth is missing; accept the current editable labels as training truth first.",
}

STORAGE_ROLE_LABELS = {
    "working_edit": "editable working layer",
    "manual_truth": "reviewed training truth",
    "editable_ai_result": "editable result layer",
    "raw_ai_prediction_backup": "original prediction backup",
    "model_draft": "read-only prediction copy",
    "working_volume": "working volume",
    "source": "source volume",
}

STORAGE_STATUS_LABELS = {
    "candidate": "cleanup candidate",
    "blocked": "protected / blocked",
    "protected": "protected",
    "registered cache": "registered cache",
    "dry-run": "preview only",
}


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _text(value):
    return str(value or "").strip()


def part_has_model_source(part):
    part = _as_dict(part)
    labels = _as_dict(part.get("labels"))
    if _as_dict(labels.get("raw_ai_prediction_backup")).get("path"):
        return True
    if _as_dict(labels.get("model_draft")).get("path"):
        return True
    if _as_dict(labels.get("raw_ai_prediction_backup")).get("relative_path"):
        return True
    training = _as_dict(part.get("training"))
    for key in ("prediction_run_id", "model_id", "backend_run_id", "imported_prediction_id"):
        if _text(training.get(key)):
            return True
    editable = _as_dict(labels.get("editable_ai_result"))
    origin = _text(editable.get("source") or editable.get("origin") or editable.get("from_role")).lower()
    if any(token in origin for token in ("predict", "model", "nnunet", "ai")):
        return True
    return False


def specimen_has_model_source(specimen):
    specimen = _as_dict(specimen)
    labels = _as_dict(specimen.get("labels"))
    drafts = labels.get("model_drafts") or []
    if drafts:
        return True
    if _as_dict(labels.get("raw_ai_prediction_backup")).get("path"):
        return True
    return False


def review_status_label(status):
    key = _text(status) or "not_started"
    return REVIEW_STATUS_LABELS.get(key, "unrecognized status")


def system_status_label(status, has_model_source=False):
    key = _text(status) or "draft"
    if key == "predicted_pending_review" and has_model_source:
        return SYSTEM_STATUS_LABELS["predicted_pending_review_model"]
    return SYSTEM_STATUS_LABELS.get(key, "unrecognized status")


def format_train_ready_reasons(reasons, translate=None):
    translate = translate or (lambda text: text)
    readable = []
    for reason in reasons or []:
        text = _text(reason)
        if not text:
            continue
        key = text.split(":", 1)[0]
        label = translate(TRAIN_READY_REASON_LABELS.get(key, text))
        if ":" in text and key in TRAIN_READY_REASON_LABELS:
            label = f"{label} ({text.split(':', 1)[1]})"
        readable.append(label)
    return readable


def storage_role_label(role):
    key = _text(role)
    return STORAGE_ROLE_LABELS.get(key, key or "unrecognized status")


def storage_status_label(status):
    key = _text(status)
    return STORAGE_STATUS_LABELS.get(key, key or "unrecognized status")
