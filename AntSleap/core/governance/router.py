import importlib.util
import json
import os
from typing import Any


def _load_callable(module_filename: str, callable_name: str):
    module_path = os.path.join(os.path.dirname(__file__), module_filename)
    spec = importlib.util.spec_from_file_location(
        f"{module_filename}_runtime", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, callable_name)


load_and_validate_policy = _load_callable("policy_loader.py", "load_and_validate_policy")
resolve_view = _load_callable("view_resolver.py", "resolve_view")


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _load_candidates(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    records: Any = payload
    if isinstance(payload, dict):
        records = payload.get("candidates", payload.get("records", []))

    if not isinstance(records, list):
        raise ValueError("candidate_records_not_list")

    output: list[dict[str, Any]] = []
    for item in records:
        if isinstance(item, dict):
            output.append(item)
    return output


def _derive_confidence(candidate: dict[str, Any]) -> float:
    confidence = candidate.get("confidence", {})
    if not isinstance(confidence, dict):
        confidence = {}

    final_conf = _as_float(confidence.get("final_confidence"))
    if final_conf is not None:
        return final_conf

    values = [
        _as_float(confidence.get("combined_relevance_score")),
        _as_float(confidence.get("text_image_match_score")),
        _as_float(confidence.get("confidence_score")),
    ]
    clean = [value for value in values if value is not None]
    if not clean:
        return 0.0
    return sum(clean) / len(clean)


def _derive_view(candidate: dict[str, Any]) -> tuple[str, str]:
    explicit_view = candidate.get("view")
    if isinstance(explicit_view, str) and explicit_view.strip():
        return explicit_view.strip(), "candidate:view"

    text = str(candidate.get("image_file_name", "") or candidate.get("image_path", ""))
    resolved = resolve_view(text, "")
    view = str(resolved.get("view", "unknown")).strip() or "unknown"
    reason = str(resolved.get("resolution_reason", "resolver:no_signal"))
    return view, reason


def route_candidates(candidates_path: str, policy_path: str) -> dict[str, Any]:
    policy_result = load_and_validate_policy(policy_path)
    if not bool(policy_result.get("valid", False)):
        first_error = "policy_validation_failed"
        errors = policy_result.get("errors", [])
        if isinstance(errors, list) and errors:
            first_error = str(errors[0].get("message", first_error))
        raise ValueError(first_error)

    policy = policy_result.get("policy", {})
    policy_version = str(policy.get("policy_version", ""))
    target_views = set(policy.get("target_views", []))

    routing = policy.get("routing", {})
    if not isinstance(routing, dict):
        raise ValueError("policy_routing_invalid")

    core2 = routing.get("core2", {})
    frontier = routing.get("frontier", {})
    ambiguous = routing.get("ambiguous", {})

    core2_min_confidence = float(core2.get("min_confidence", 0.8))
    disallow_risk_tiers = set(core2.get("disallow_risk_tiers", []))
    require_quality_pass = bool(core2.get("require_quality_pass", True))
    frontier_min_confidence = float(frontier.get("min_confidence", 0.55))
    frontier_max_confidence = float(frontier.get("max_confidence", 0.8))
    frontier_views = set(frontier.get("include_views", []))
    ambiguous_max_confidence = float(ambiguous.get("max_confidence", 0.55))

    candidates = _load_candidates(candidates_path)
    decisions: list[dict[str, Any]] = []

    for item in candidates:
        candidate_id = str(item.get("candidate_id", "")).strip()
        if not candidate_id:
            continue

        view, view_source = _derive_view(item)
        confidence = _derive_confidence(item)

        explicit_risk = item.get("risk_tier")
        if isinstance(explicit_risk, str) and explicit_risk.strip():
            risk_tier = explicit_risk.strip()
        else:
            if confidence < ambiguous_max_confidence:
                risk_tier = "high"
            elif confidence < core2_min_confidence:
                risk_tier = "medium"
            else:
                risk_tier = "low"

        quality_pass = bool(item.get("quality_pass", True))
        signal_conflict = bool(item.get("signal_conflict", False))
        research_like = bool(item.get("research_like", False)) or item.get("is_taxonomic") is False
        reasons: list[str] = []

        if signal_conflict:
            bucket = "Ambiguous"
            reasons.append("signal_conflict")
        elif view == "unknown":
            bucket = "Ambiguous"
            reasons.append("unknown_view")
        elif confidence < ambiguous_max_confidence:
            bucket = "Ambiguous"
            reasons.append("low_confidence")
        elif research_like:
            bucket = "Frontier"
            reasons.append("research_like_record")
        elif view in frontier_views:
            bucket = "Frontier"
            reasons.append(f"frontier_view:{view}")
        elif frontier_min_confidence <= confidence < frontier_max_confidence:
            bucket = "Frontier"
            reasons.append("frontier_confidence_band")
        elif (
            view in target_views
            and confidence >= core2_min_confidence
            and (not require_quality_pass or quality_pass)
            and risk_tier not in disallow_risk_tiers
        ):
            bucket = "Core-2"
            reasons.append("core2_target_confident")
        elif view in target_views:
            bucket = "Ambiguous"
            if confidence < core2_min_confidence:
                reasons.append("core2_confidence_below_min")
            if require_quality_pass and not quality_pass:
                reasons.append("core2_quality_not_passed")
            if risk_tier in disallow_risk_tiers:
                reasons.append(f"core2_disallowed_risk:{risk_tier}")
        else:
            bucket = "Frontier"
            reasons.append(f"non_target_view:{view}")

        if not reasons:
            reasons.append("route_default_guard")

        decisions.append(
            {
                "candidate_id": candidate_id,
                "bucket": bucket,
                "route_reasons": reasons,
                "view": view,
                "view_source": view_source,
                "confidence": round(confidence, 6),
                "risk_tier": risk_tier,
                "quality_pass": quality_pass,
            }
        )

    decisions.sort(key=lambda item: item["candidate_id"])
    buckets = {"Core-2": [], "Frontier": [], "Ambiguous": []}
    for item in decisions:
        buckets[item["bucket"]].append(item["candidate_id"])

    return {
        "schema_version": "core2-routing-v1",
        "policy_version": policy_version,
        "candidates_path": candidates_path,
        "summary": {
            "total_candidates": len(decisions),
            "core2_count": len(buckets["Core-2"]),
            "frontier_count": len(buckets["Frontier"]),
            "ambiguous_count": len(buckets["Ambiguous"]),
        },
        "buckets": buckets,
        "decisions": decisions,
    }


def save_routing_report(report: dict[str, Any], output_path: str) -> None:
    _ensure_parent(output_path)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
