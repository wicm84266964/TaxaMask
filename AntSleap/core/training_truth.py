"""Canonical per-part trust metadata for 2D training labels."""

from __future__ import annotations

from collections.abc import Mapping


LABEL_PART_METADATA_FIELD = "label_part_metadata"
TRAINING_TRUTH_METADATA_KEY = "training_truth_v1"

TRAINING_SOURCE_MANUAL = "manual"
TRAINING_SOURCE_LEGACY_MANUAL = "legacy_manual"
TRAINING_SOURCE_LEGACY_AI_UNKNOWN = "legacy_ai_unknown"
TRAINING_SOURCE_BLINK_EXPERT = "blink_expert"
TRAINING_SOURCE_MODEL = "model_prediction"
TRAINING_SOURCE_EXTERNAL_MODEL = "external_model_prediction"
TRAINING_SOURCE_VLM = "vlm_first_mile"
TRAINING_SOURCE_AUTO_SHRINK = "taxamask_auto_shrink"

TRAINING_REVIEW_DRAFT = "draft"
TRAINING_REVIEW_CONFIRMED = "confirmed"

TRAINING_ACCEPT_MANUAL_EDIT = "manual_edit"
TRAINING_ACCEPT_SELECTED_AI = "accept_selected_ai"
TRAINING_ACCEPT_LEGACY_CONFIRMED_AI = "legacy_confirmed_ai"
TRAINING_ACCEPT_DERIVED_TRUTH = "derived_from_confirmed_truth"

_VALID_REVIEW_STATUSES = frozenset(
    {TRAINING_REVIEW_DRAFT, TRAINING_REVIEW_CONFIRMED}
)
_MANUAL_SOURCES = frozenset(
    {TRAINING_SOURCE_MANUAL, TRAINING_SOURCE_LEGACY_MANUAL}
)
_AI_SOURCES = frozenset(
    {
        TRAINING_SOURCE_LEGACY_AI_UNKNOWN,
        TRAINING_SOURCE_BLINK_EXPERT,
        TRAINING_SOURCE_MODEL,
        TRAINING_SOURCE_EXTERNAL_MODEL,
        TRAINING_SOURCE_VLM,
    }
)
_DERIVED_SOURCES = frozenset({TRAINING_SOURCE_AUTO_SHRINK})
_VALID_SOURCES = _MANUAL_SOURCES | _AI_SOURCES | _DERIVED_SOURCES
_VALID_ACCEPTED_VIA = frozenset(
    {
        TRAINING_ACCEPT_MANUAL_EDIT,
        TRAINING_ACCEPT_SELECTED_AI,
        TRAINING_ACCEPT_DERIVED_TRUTH,
    }
)


def _as_mapping(value):
    return value if isinstance(value, Mapping) else {}


def _clean_text(value):
    return str(value or "").strip()


def sanitize_training_truth_record(value):
    """Return a strict persisted truth record, or ``None`` when malformed."""

    if not isinstance(value, Mapping):
        return None
    source = _clean_text(value.get("source"))
    review_status = _clean_text(value.get("review_status")).lower()
    accepted_via = _clean_text(value.get("accepted_via"))
    if source not in _VALID_SOURCES or review_status not in _VALID_REVIEW_STATUSES:
        return None
    if accepted_via and accepted_via not in _VALID_ACCEPTED_VIA:
        return None
    if review_status == TRAINING_REVIEW_DRAFT and accepted_via:
        return None
    if review_status == TRAINING_REVIEW_CONFIRMED:
        if source in _MANUAL_SOURCES and accepted_via != TRAINING_ACCEPT_MANUAL_EDIT:
            return None
        if source in _AI_SOURCES and accepted_via != TRAINING_ACCEPT_SELECTED_AI:
            return None
        if source in _DERIVED_SOURCES and accepted_via != TRAINING_ACCEPT_DERIVED_TRUTH:
            return None
    elif source in _MANUAL_SOURCES:
        return None
    clean = {
        "source": source,
        "review_status": review_status,
    }
    if accepted_via:
        clean["accepted_via"] = accepted_via
    return clean


def get_part_training_truth(label_entry, part_name):
    if not isinstance(label_entry, Mapping):
        return None
    clean_part = _clean_text(part_name)
    metadata_by_part = _as_mapping(label_entry.get(LABEL_PART_METADATA_FIELD))
    part_metadata = _as_mapping(metadata_by_part.get(clean_part))
    if TRAINING_TRUTH_METADATA_KEY not in part_metadata:
        return None
    return sanitize_training_truth_record(
        part_metadata.get(TRAINING_TRUTH_METADATA_KEY)
    )


def set_part_training_truth(
    label_entry,
    part_name,
    *,
    source,
    review_status,
    accepted_via="",
):
    if not isinstance(label_entry, dict):
        raise TypeError("training_truth_label_entry_not_dict")
    clean_part = _clean_text(part_name)
    if not clean_part:
        raise ValueError("training_truth_part_name_missing")
    clean = sanitize_training_truth_record(
        {
            "source": source,
            "review_status": review_status,
            "accepted_via": accepted_via,
        }
    )
    if clean is None:
        raise ValueError("training_truth_record_invalid")
    metadata_by_part = label_entry.setdefault(LABEL_PART_METADATA_FIELD, {})
    if not isinstance(metadata_by_part, dict):
        metadata_by_part = {}
        label_entry[LABEL_PART_METADATA_FIELD] = metadata_by_part
    part_metadata = metadata_by_part.setdefault(clean_part, {})
    if not isinstance(part_metadata, dict):
        part_metadata = {}
        metadata_by_part[clean_part] = part_metadata
    part_metadata[TRAINING_TRUTH_METADATA_KEY] = clean
    return dict(clean)


def remove_part_training_truth(label_entry, part_name):
    if not isinstance(label_entry, dict):
        return False
    clean_part = _clean_text(part_name)
    metadata_by_part = label_entry.get(LABEL_PART_METADATA_FIELD)
    if not isinstance(metadata_by_part, dict) or clean_part not in metadata_by_part:
        return False
    part_metadata = metadata_by_part.get(clean_part)
    if not isinstance(part_metadata, dict) or TRAINING_TRUTH_METADATA_KEY not in part_metadata:
        return False
    del part_metadata[TRAINING_TRUTH_METADATA_KEY]
    if not part_metadata:
        del metadata_by_part[clean_part]
    if not metadata_by_part:
        label_entry.pop(LABEL_PART_METADATA_FIELD, None)
    return True


def resolve_part_training_trust(label_entry, part_name):
    """Resolve training eligibility without mutating legacy project data."""

    clean_part = _clean_text(part_name)
    entry = _as_mapping(label_entry)
    descriptions = _as_mapping(entry.get("descriptions"))
    has_auto_marker = descriptions.get(clean_part) == "Auto-Annotated"

    metadata_by_part = _as_mapping(entry.get(LABEL_PART_METADATA_FIELD))
    part_metadata = _as_mapping(metadata_by_part.get(clean_part))
    has_explicit_truth = TRAINING_TRUTH_METADATA_KEY in part_metadata
    explicit_truth = sanitize_training_truth_record(
        part_metadata.get(TRAINING_TRUTH_METADATA_KEY)
    )

    if has_explicit_truth:
        if explicit_truth is None:
            return _decision(
                clean_part,
                eligible=False,
                state="conflict",
                source="unknown",
                review_status="invalid",
                reason="training_truth_metadata_invalid",
            )
        if has_auto_marker and explicit_truth["review_status"] == TRAINING_REVIEW_CONFIRMED:
            return _decision(
                clean_part,
                eligible=False,
                state="conflict",
                reason="confirmed_truth_has_auto_draft_marker",
                **explicit_truth,
            )
        if explicit_truth["review_status"] != TRAINING_REVIEW_CONFIRMED:
            return _decision(
                clean_part,
                eligible=False,
                state="draft",
                reason="training_truth_not_confirmed",
                **explicit_truth,
            )
        return _decision(
            clean_part,
            eligible=True,
            state="confirmed",
            reason="explicit_confirmed_truth",
            **explicit_truth,
        )

    auto_meta_by_part = _as_mapping(entry.get("auto_box_meta"))
    has_auto_meta = clean_part in auto_meta_by_part and isinstance(
        auto_meta_by_part.get(clean_part), Mapping
    )
    auto_meta = _as_mapping(auto_meta_by_part.get(clean_part))
    auto_source = _clean_text(auto_meta.get("source")) or TRAINING_SOURCE_LEGACY_AI_UNKNOWN
    auto_status = _clean_text(auto_meta.get("review_status")).lower()

    if has_auto_marker:
        if has_auto_meta and auto_status == TRAINING_REVIEW_CONFIRMED:
            return _decision(
                clean_part,
                eligible=False,
                state="conflict",
                source=auto_source,
                review_status=auto_status,
                reason="legacy_confirmed_ai_has_auto_draft_marker",
            )
        return _decision(
            clean_part,
            eligible=False,
            state="draft",
            source=auto_source,
            review_status=auto_status or TRAINING_REVIEW_DRAFT,
            reason="legacy_auto_annotated_draft",
        )

    if has_auto_meta:
        if auto_status == TRAINING_REVIEW_CONFIRMED:
            return _decision(
                clean_part,
                eligible=True,
                state="confirmed",
                source=auto_source,
                review_status=auto_status,
                accepted_via=TRAINING_ACCEPT_LEGACY_CONFIRMED_AI,
                reason="legacy_confirmed_ai",
            )
        if auto_status in {"", TRAINING_REVIEW_DRAFT}:
            return _decision(
                clean_part,
                eligible=False,
                state="draft",
                source=auto_source,
                review_status=auto_status or TRAINING_REVIEW_DRAFT,
                reason="legacy_ai_not_confirmed",
            )
        return _decision(
            clean_part,
            eligible=False,
            state="conflict",
            source=auto_source,
            review_status=auto_status,
            reason="legacy_ai_review_status_invalid",
        )

    return _decision(
        clean_part,
        eligible=True,
        state="confirmed",
        source=TRAINING_SOURCE_LEGACY_MANUAL,
        review_status=TRAINING_REVIEW_CONFIRMED,
        accepted_via=TRAINING_ACCEPT_MANUAL_EDIT,
        reason="legacy_manual_truth",
    )


def _decision(
    part_name,
    *,
    eligible,
    state,
    source,
    review_status,
    reason,
    accepted_via="",
):
    result = {
        "part_name": part_name,
        "eligible": bool(eligible),
        "state": state,
        "source": source,
        "review_status": review_status,
        "reason": reason,
    }
    if accepted_via:
        result["accepted_via"] = accepted_via
    return result


__all__ = [
    "LABEL_PART_METADATA_FIELD",
    "TRAINING_ACCEPT_MANUAL_EDIT",
    "TRAINING_ACCEPT_DERIVED_TRUTH",
    "TRAINING_ACCEPT_SELECTED_AI",
    "TRAINING_REVIEW_CONFIRMED",
    "TRAINING_REVIEW_DRAFT",
    "TRAINING_SOURCE_BLINK_EXPERT",
    "TRAINING_SOURCE_AUTO_SHRINK",
    "TRAINING_SOURCE_EXTERNAL_MODEL",
    "TRAINING_SOURCE_LEGACY_AI_UNKNOWN",
    "TRAINING_SOURCE_LEGACY_MANUAL",
    "TRAINING_SOURCE_MANUAL",
    "TRAINING_SOURCE_MODEL",
    "TRAINING_SOURCE_VLM",
    "TRAINING_TRUTH_METADATA_KEY",
    "get_part_training_truth",
    "remove_part_training_truth",
    "resolve_part_training_trust",
    "sanitize_training_truth_record",
    "set_part_training_truth",
]
