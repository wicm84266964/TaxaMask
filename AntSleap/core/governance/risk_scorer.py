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


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _load_candidates(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("candidate_artifact_root_not_object")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("candidate_artifact_missing_candidates")
    return payload


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _score_candidate(candidate: dict[str, Any]) -> tuple[str, list[str], float]:
    confidence = candidate.get("confidence", {})
    if not isinstance(confidence, dict):
        confidence = {}

    signal_keys = (
        "final_confidence",
        "combined_relevance_score",
        "text_image_match_score",
        "confidence_score",
    )

    missing: list[str] = []
    values: list[float] = []
    for key in signal_keys:
        value = _as_float(confidence.get(key))
        if value is None:
            missing.append(key)
        else:
            values.append(value)

    reason_codes: list[str] = []
    if missing:
        for key in missing:
            reason_codes.append(f"missing_signal:{key}")
        return "high", reason_codes, 0.0

    avg_score = sum(values) / len(values)
    if avg_score >= 0.8:
        reason_codes.append("score_high_confidence")
        tier = "low"
    elif avg_score >= 0.6:
        reason_codes.append("score_mid_confidence")
        tier = "medium"
    else:
        reason_codes.append("score_low_confidence")
        tier = "high"

    if not bool(candidate.get("is_taxonomic", False)) and tier == "low":
        tier = "medium"
        reason_codes.append("taxonomic_signal_weak")

    return tier, reason_codes, round(avg_score, 6)


def build_sampling_plan(candidates_path: str, policy_path: str) -> dict[str, Any]:
    policy_result = load_and_validate_policy(policy_path)
    if not bool(policy_result.get("valid", False)):
        first_error = "policy_validation_failed"
        errors = policy_result.get("errors", [])
        if isinstance(errors, list) and errors:
            first_error = str(errors[0].get("message", first_error))
        raise ValueError(first_error)

    policy = policy_result.get("policy", {})
    policy_version = str(policy.get("policy_version", ""))
    review_sampling = policy.get("review_sampling", {})
    if not isinstance(review_sampling, dict):
        raise ValueError("policy_review_sampling_invalid")

    rates = {
        "high": float(review_sampling.get("high", 1.0)),
        "medium": float(review_sampling.get("medium", 0.3)),
        "low": float(review_sampling.get("low", 0.1)),
    }

    payload = _load_candidates(candidates_path)
    candidates = payload.get("candidates", [])

    scored_candidates: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id", "")).strip()
        if not candidate_id:
            continue

        tier, reason_codes, aggregate_score = _score_candidate(item)
        scored_candidates.append(
            {
                "candidate_id": candidate_id,
                "risk_tier": tier,
                "risk_reasons": reason_codes,
                "aggregate_score": aggregate_score,
                "pdf_id": int(item.get("pdf_id", 0) or 0),
                "page_number": int(item.get("page_number", 0) or 0),
                "image_path": str(item.get("image_path", "")),
            }
        )

    scored_candidates.sort(
        key=lambda item: (
            item.get("risk_tier", ""),
            item.get("candidate_id", ""),
        )
    )

    buckets: dict[str, list[dict[str, Any]]] = {"high": [], "medium": [], "low": []}
    for item in scored_candidates:
        tier = str(item.get("risk_tier", "high"))
        buckets.setdefault(tier, []).append(item)

    sampled_by_tier: dict[str, list[str]] = {"high": [], "medium": [], "low": []}
    tier_summary: dict[str, dict[str, Any]] = {}

    for tier in ("high", "medium", "low"):
        entries = sorted(buckets.get(tier, []), key=lambda item: item["candidate_id"])
        count = len(entries)
        sample_count = int(round(count * rates[tier]))
        sample_count = min(sample_count, count)
        sampled = entries[:sample_count]
        sampled_by_tier[tier] = [item["candidate_id"] for item in sampled]
        tier_summary[tier] = {
            "count": count,
            "sample_rate": rates[tier],
            "sample_count": sample_count,
        }

    sampled_candidates = [
        item
        for item in scored_candidates
        if item["candidate_id"]
        in set(sampled_by_tier["high"] + sampled_by_tier["medium"] + sampled_by_tier["low"])
    ]

    return {
        "schema_version": "core2-sampling-v1",
        "policy_version": policy_version,
        "candidates_path": candidates_path,
        "sampling_rates": rates,
        "summary": {
            "total_candidates": len(scored_candidates),
            "tiers": tier_summary,
            "total_sample_count": len(sampled_candidates),
        },
        "candidates": scored_candidates,
        "sampled_by_tier": sampled_by_tier,
        "sampled_candidates": sampled_candidates,
    }


def save_sampling_plan(report: dict[str, Any], output_path: str) -> None:
    _ensure_parent(output_path)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
