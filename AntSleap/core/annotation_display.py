"""Researcher-facing 2D annotation status without rewriting stored truth."""

from __future__ import annotations

from .training_truth import (
    TRAINING_SOURCE_BLINK_EXPERT,
    TRAINING_SOURCE_EXTERNAL_MODEL,
    TRAINING_SOURCE_LEGACY_AI_UNKNOWN,
    TRAINING_SOURCE_LEGACY_JOURNAL_RECOVERY,
    TRAINING_SOURCE_LEGACY_MANUAL,
    TRAINING_SOURCE_MANUAL,
    TRAINING_SOURCE_MODEL,
    TRAINING_SOURCE_VLM,
    resolve_part_training_trust,
)

SCREEN_CONFIRMED = "confirmed"
SCREEN_PENDING = "pending_review"
SCREEN_EMPTY = "unlabeled_or_check"

CAT_NEEDS_CHECK = "needs_check"
CAT_MIXED = "mixed"
CAT_CONFIRMED_ONLY = "confirmed_only"
CAT_DRAFT_ONLY = "draft_only"
CAT_HELPER_ONLY = "helper_only"
CAT_UNLABELED = "unlabeled"

SOURCE_LABEL_KEYS = {
    TRAINING_SOURCE_MANUAL: "hand-drawn",
    TRAINING_SOURCE_LEGACY_MANUAL: "historical manual",
    TRAINING_SOURCE_MODEL: "SAM / model",
    TRAINING_SOURCE_VLM: "VLM",
    TRAINING_SOURCE_BLINK_EXPERT: "child expert",
    TRAINING_SOURCE_EXTERNAL_MODEL: "external model",
    TRAINING_SOURCE_LEGACY_AI_UNKNOWN: "AI draft",
    TRAINING_SOURCE_LEGACY_JOURNAL_RECOVERY: "recovered",
}


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _has_polygon(points):
    return bool(points) and len(points) >= 3


def classify_part(entry, part_name):
    entry = _as_dict(entry)
    part_name = str(part_name or "").strip()
    parts = _as_dict(entry.get("parts"))
    auto_boxes = _as_dict(entry.get("auto_boxes"))
    boxes = _as_dict(entry.get("boxes"))
    shrink = _as_dict(entry.get("shrink_loose_boxes"))
    has_poly = _has_polygon(parts.get(part_name))
    decision = resolve_part_training_trust(entry, part_name) if part_name else {}
    state = str(decision.get("state") or "")
    source = str(decision.get("source") or "")
    if state == "conflict":
        kind = "conflict"
        screen = SCREEN_EMPTY
        label_key = "needs check"
    elif has_poly and state == "draft":
        kind = "draft"
        screen = SCREEN_PENDING
        label_key = "review-pending"
    elif has_poly:
        kind = "confirmed"
        screen = SCREEN_CONFIRMED
        label_key = "confirmed"
        if not state:
            source = source or TRAINING_SOURCE_MANUAL
    elif part_name in auto_boxes:
        kind = "box_only"
        screen = SCREEN_PENDING
        label_key = "box only"
    elif part_name in boxes or part_name in shrink:
        kind = "helper"
        screen = SCREEN_PENDING
        label_key = "helper box"
    else:
        kind = "empty"
        screen = SCREEN_EMPTY
        label_key = ""
    return {
        "part": part_name,
        "kind": kind,
        "screen": screen,
        "source": source,
        "source_label_key": SOURCE_LABEL_KEYS.get(source, ""),
        "label_key": label_key,
        "has_polygon": has_poly,
        "reason": str(decision.get("reason") or ""),
    }


def classify_image_entry(entry):
    entry = _as_dict(entry)
    parts = _as_dict(entry.get("parts"))
    auto_boxes = _as_dict(entry.get("auto_boxes"))
    boxes = _as_dict(entry.get("boxes"))
    shrink = _as_dict(entry.get("shrink_loose_boxes"))
    names = set(parts) | set(auto_boxes) | set(boxes) | set(shrink)
    descriptions = _as_dict(entry.get("descriptions"))
    names.update(descriptions)
    has_conflict = False
    has_confirmed = False
    has_draft = False
    has_box_only = False
    has_helper = False
    part_states = {}
    for name in names:
        state = classify_part(entry, name)
        part_states[name] = state
        kind = state["kind"]
        if kind == "conflict":
            has_conflict = True
        elif kind == "confirmed":
            has_confirmed = True
        elif kind == "draft":
            has_draft = True
        elif kind == "box_only":
            has_box_only = True
        elif kind == "helper":
            has_helper = True
    pending_items = has_draft or has_box_only
    if has_conflict:
        category = CAT_NEEDS_CHECK
        screen = SCREEN_EMPTY
    elif has_confirmed and pending_items:
        category = CAT_MIXED
        screen = SCREEN_PENDING
    elif has_confirmed:
        category = CAT_CONFIRMED_ONLY
        screen = SCREEN_CONFIRMED
    elif pending_items:
        category = CAT_DRAFT_ONLY
        screen = SCREEN_PENDING
    elif has_helper:
        category = CAT_HELPER_ONLY
        screen = SCREEN_PENDING
    else:
        category = CAT_UNLABELED
        screen = SCREEN_EMPTY
    return {
        "category": category,
        "screen": screen,
        "part_states": part_states,
        "has_conflict": has_conflict,
        "has_confirmed": has_confirmed,
        "has_draft": has_draft,
        "has_box_only": has_box_only,
        "has_helper": has_helper,
    }


def empty_image_counts():
    return {
        CAT_NEEDS_CHECK: 0,
        CAT_MIXED: 0,
        CAT_CONFIRMED_ONLY: 0,
        CAT_DRAFT_ONLY: 0,
        CAT_HELPER_ONLY: 0,
        CAT_UNLABELED: 0,
        SCREEN_CONFIRMED: 0,
        SCREEN_PENDING: 0,
        SCREEN_EMPTY: 0,
    }


def add_image_counts(counts, classification):
    counts = dict(counts or empty_image_counts())
    category = classification.get("category") or CAT_UNLABELED
    screen = classification.get("screen") or SCREEN_EMPTY
    counts[category] = int(counts.get(category, 0) or 0) + 1
    counts[screen] = int(counts.get(screen, 0) or 0) + 1
    return counts
