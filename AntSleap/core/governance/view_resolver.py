import re
from typing import Any


CANONICAL_VIEWS = ("lateral", "dorsal", "head_frontal", "unknown")

_LATERAL_MARKERS = (
    "lateral",
    "profile",
    "side view",
    "side-view",
    "side_view",
)
_DORSAL_MARKERS = (
    "dorsal",
    "top view",
    "top-view",
    "top_view",
)
_HEAD_STRONG_MARKERS = (
    "head frontal",
    "frontal head",
    "head view",
    "head-view",
    "head_view",
)


def _normalize_text(*parts: str) -> str:
    merged = " ".join(part for part in parts if part)
    lowered = merged.lower().replace("_", " ").replace("-", " ")
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def resolve_view(filename_or_text: str, context_text: str = "") -> dict[str, Any]:
    text = _normalize_text(filename_or_text, context_text)

    candidates: list[tuple[str, float, str]] = []

    if _contains_any(text, _LATERAL_MARKERS):
        candidates.append(("lateral", 0.95, "marker:lateral"))

    if _contains_any(text, _DORSAL_MARKERS):
        candidates.append(("dorsal", 0.95, "marker:dorsal"))

    if _contains_any(text, _HEAD_STRONG_MARKERS):
        candidates.append(("head_frontal", 0.90, "marker:head_frontal"))

    if "head" in text and not candidates:
        candidates.append(("head_frontal", 0.60, "marker:head_weak"))

    if re.search(r"\bview\s*\d+\b", text) and not candidates:
        return {
            "view": "unknown",
            "view_confidence": 0.40,
            "resolution_reason": "ambiguous:view_index_only",
        }

    unique_views = list(dict.fromkeys(item[0] for item in candidates))

    if len(unique_views) == 1:
        selected = next(item for item in candidates if item[0] == unique_views[0])
        return {
            "view": selected[0],
            "view_confidence": selected[1],
            "resolution_reason": selected[2],
        }

    if len(unique_views) > 1:
        joined = ",".join(unique_views)
        return {
            "view": "unknown",
            "view_confidence": 0.30,
            "resolution_reason": f"conflict:multi_view_signals:{joined}",
        }

    return {
        "view": "unknown",
        "view_confidence": 0.10,
        "resolution_reason": "no_signal",
    }
