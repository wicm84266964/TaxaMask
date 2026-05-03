import json
from typing import Any


def _error(code: str, field: str, message: str) -> dict[str, str]:
    return {"code": code, "field": field, "message": message}


def validate_policy(policy: dict[str, Any]) -> tuple[bool, list[dict[str, str]]]:
    errors: list[dict[str, str]] = []

    required_top = (
        "policy_version",
        "target_views",
        "excluded_training_views",
        "quality_gate",
        "routing",
        "review_sampling",
        "bridge",
        "locator_upgrade_trigger",
    )

    for key in required_top:
        if key not in policy:
            errors.append(_error("missing_field", key, f"Missing required field '{key}'."))

    if errors:
        return False, errors

    target_views = policy.get("target_views")
    if not isinstance(target_views, list) or not target_views:
        errors.append(
            _error("invalid_type", "target_views", "Field 'target_views' must be a non-empty list.")
        )

    excluded_views = policy.get("excluded_training_views")
    if not isinstance(excluded_views, list):
        errors.append(
            _error(
                "invalid_type",
                "excluded_training_views",
                "Field 'excluded_training_views' must be a list.",
            )
        )

    quality_gate = policy.get("quality_gate")
    if not isinstance(quality_gate, dict):
        errors.append(_error("invalid_type", "quality_gate", "Field 'quality_gate' must be an object."))
    else:
        pass_rate = quality_gate.get("pass_rate_min")
        overlap = quality_gate.get("boundary_overlap_min")
        loc_err = quality_gate.get("localization_error_px_max")
        min_samples = quality_gate.get("min_samples_per_target_view")

        if not isinstance(pass_rate, (int, float)) or not (0.0 <= float(pass_rate) <= 1.0):
            errors.append(_error("invalid_value", "quality_gate.pass_rate_min", "Must be in [0, 1]."))
        if not isinstance(overlap, (int, float)) or not (0.0 <= float(overlap) <= 1.0):
            errors.append(
                _error("invalid_value", "quality_gate.boundary_overlap_min", "Must be in [0, 1].")
            )
        if not isinstance(loc_err, (int, float)) or float(loc_err) < 0:
            errors.append(
                _error("invalid_value", "quality_gate.localization_error_px_max", "Must be >= 0.")
            )
        if not isinstance(min_samples, int) or min_samples <= 0:
            errors.append(
                _error("invalid_value", "quality_gate.min_samples_per_target_view", "Must be a positive integer.")
            )

    routing = policy.get("routing")
    if not isinstance(routing, dict):
        errors.append(_error("invalid_type", "routing", "Field 'routing' must be an object."))
    else:
        for key in ("core2", "frontier", "ambiguous"):
            if key not in routing:
                errors.append(_error("missing_field", f"routing.{key}", f"Missing routing section '{key}'."))

    review_sampling = policy.get("review_sampling")
    if not isinstance(review_sampling, dict):
        errors.append(
            _error("invalid_type", "review_sampling", "Field 'review_sampling' must be an object.")
        )
    else:
        for key in ("high", "medium", "low"):
            value = review_sampling.get(key)
            if not isinstance(value, (int, float)) or not (0.0 <= float(value) <= 1.0):
                errors.append(
                    _error(
                        "invalid_value",
                        f"review_sampling.{key}",
                        "Sampling rates must be numeric in [0, 1].",
                    )
                )

    bridge = policy.get("bridge")
    if not isinstance(bridge, dict):
        errors.append(_error("invalid_type", "bridge", "Field 'bridge' must be an object."))
    else:
        mode = bridge.get("mode")
        if mode != "candidate_only":
            errors.append(
                _error("invalid_value", "bridge.mode", "Only 'candidate_only' is allowed in this phase.")
            )

    trigger = policy.get("locator_upgrade_trigger")
    if not isinstance(trigger, dict):
        errors.append(
            _error("invalid_type", "locator_upgrade_trigger", "Field 'locator_upgrade_trigger' must be an object.")
        )
    else:
        consecutive = trigger.get("consecutive_fail_runs")
        gap = trigger.get("single_run_pass_rate_gap")
        if not isinstance(consecutive, int) or consecutive <= 0:
            errors.append(
                _error("invalid_value", "locator_upgrade_trigger.consecutive_fail_runs", "Must be a positive integer.")
            )
        if not isinstance(gap, (int, float)) or not (0.0 <= float(gap) <= 1.0):
            errors.append(
                _error(
                    "invalid_value",
                    "locator_upgrade_trigger.single_run_pass_rate_gap",
                    "Must be in [0, 1].",
                )
            )

    return len(errors) == 0, errors


def load_policy(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("Policy JSON root must be an object.")

    return payload


def load_and_validate_policy(path: str) -> dict[str, Any]:
    payload = load_policy(path)
    valid, errors = validate_policy(payload)
    return {
        "path": path,
        "valid": valid,
        "error_count": len(errors),
        "errors": errors,
        "policy": payload,
    }
