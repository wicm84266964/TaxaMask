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


def _load_metrics(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("metrics_json_root_not_object")

    metrics_by_view = payload.get("metrics_by_view")
    if not isinstance(metrics_by_view, dict):
        raise ValueError("metrics_by_view_missing")

    return payload


def _as_float(value: Any, field: str, view: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"invalid_metric:{view}:{field}")
    return float(value)


def build_redline_report(metrics_path: str, policy_path: str) -> dict[str, Any]:
    policy_result = load_and_validate_policy(policy_path)
    if not bool(policy_result.get("valid", False)):
        first_error = "policy_validation_failed"
        errors = policy_result.get("errors", [])
        if isinstance(errors, list) and errors:
            first_error = str(errors[0].get("message", first_error))
        raise ValueError(first_error)

    policy = policy_result.get("policy", {})
    target_views = policy.get("target_views", [])
    if not isinstance(target_views, list) or not target_views:
        raise ValueError("policy_target_views_invalid")

    quality_gate = policy.get("quality_gate", {})
    if not isinstance(quality_gate, dict):
        raise ValueError("policy_quality_gate_invalid")

    pass_rate_min = float(quality_gate.get("pass_rate_min", 0.95))
    overlap_min = float(quality_gate.get("boundary_overlap_min", 0.75))
    loc_error_max = float(quality_gate.get("localization_error_px_max", 15.0))

    metrics_payload = _load_metrics(metrics_path)
    metrics_by_view = metrics_payload.get("metrics_by_view", {})

    view_reports: dict[str, dict[str, Any]] = {}
    global_reason_codes: list[str] = []

    for view in target_views:
        metric_entry = metrics_by_view.get(view)
        if not isinstance(metric_entry, dict):
            reason = f"missing_target_view_metrics:{view}"
            view_reports[view] = {
                "available": False,
                "pass": False,
                "reason_codes": [reason],
                "checks": {
                    "pass_rate": False,
                    "boundary_overlap": False,
                    "localization_error_px": False,
                },
            }
            global_reason_codes.append(reason)
            continue

        pass_rate = _as_float(metric_entry.get("pass_rate"), "pass_rate", view)
        overlap = _as_float(metric_entry.get("boundary_overlap"), "boundary_overlap", view)
        loc_err = _as_float(
            metric_entry.get("localization_error_px"), "localization_error_px", view
        )
        sample_count = _as_float(metric_entry.get("sample_count"), "sample_count", view)

        checks = {
            "pass_rate": pass_rate >= pass_rate_min,
            "boundary_overlap": overlap >= overlap_min,
            "localization_error_px": loc_err <= loc_error_max,
        }

        reasons: list[str] = []
        if not checks["pass_rate"]:
            reasons.append(f"target_view_fail:{view}:pass_rate")
        if not checks["boundary_overlap"]:
            reasons.append(f"target_view_fail:{view}:boundary_overlap")
        if not checks["localization_error_px"]:
            reasons.append(f"target_view_fail:{view}:localization_error_px")

        view_pass = all(checks.values())
        view_reports[view] = {
            "available": True,
            "pass": view_pass,
            "reason_codes": reasons,
            "checks": checks,
            "metrics": {
                "sample_count": int(sample_count),
                "pass_rate": pass_rate,
                "boundary_overlap": overlap,
                "localization_error_px": loc_err,
            },
        }
        global_reason_codes.extend(reasons)

    global_pass = len(global_reason_codes) == 0
    report = {
        "schema_version": "core2-redline-v1",
        "policy_version": str(policy.get("policy_version", "")),
        "metrics_path": metrics_path,
        "target_views": list(target_views),
        "thresholds": {
            "pass_rate_min": pass_rate_min,
            "boundary_overlap_min": overlap_min,
            "localization_error_px_max": loc_error_max,
        },
        "target_view_reports": view_reports,
        "global_pass": global_pass,
        "reason_codes": global_reason_codes,
    }
    return report


def save_redline_report(report: dict[str, Any], output_path: str) -> None:
    _ensure_parent(output_path)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
