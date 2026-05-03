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


def _load_report(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("report_json_root_not_object")
    return payload


def apply_sample_sufficiency_guard(report_path: str, policy_path: str) -> dict[str, Any]:
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

    min_samples = quality_gate.get("min_samples_per_target_view")
    if not isinstance(min_samples, int) or min_samples <= 0:
        raise ValueError("policy_min_samples_invalid")

    report = _load_report(report_path)
    target_view_reports = report.get("target_view_reports")
    if not isinstance(target_view_reports, dict):
        raise ValueError("report_target_view_reports_missing")

    insufficient_views: list[dict[str, Any]] = []
    reason_codes = report.get("reason_codes", [])
    if not isinstance(reason_codes, list):
        reason_codes = []

    for view in target_views:
        view_report = target_view_reports.get(view)
        if not isinstance(view_report, dict):
            insufficient_views.append(
                {
                    "view": view,
                    "sample_count": 0,
                    "reason": "target_view_report_missing",
                }
            )
            continue

        metrics = view_report.get("metrics", {})
        sample_count_value: Any = None
        if isinstance(metrics, dict):
            sample_count_value = metrics.get("sample_count")

        if not isinstance(sample_count_value, (int, float)):
            insufficient_views.append(
                {
                    "view": view,
                    "sample_count": 0,
                    "reason": "sample_count_missing",
                }
            )
            view_report["insufficient_evidence"] = True
            continue

        sample_count = int(sample_count_value)
        if sample_count < min_samples:
            insufficient_views.append(
                {
                    "view": view,
                    "sample_count": sample_count,
                    "reason": "below_min_samples",
                }
            )
            view_report["insufficient_evidence"] = True
        else:
            view_report["insufficient_evidence"] = False

    insufficient_evidence = len(insufficient_views) > 0
    if insufficient_evidence:
        report["global_pass"] = False
        for item in insufficient_views:
            code = (
                f"insufficient_evidence:{item['view']}:"
                f"sample_count={item['sample_count']}:"
                f"min_required={min_samples}"
            )
            if code not in reason_codes:
                reason_codes.append(code)

    report["reason_codes"] = reason_codes
    report["insufficient_evidence"] = insufficient_evidence
    report["insufficient_evidence_threshold"] = min_samples
    report["insufficient_evidence_views"] = insufficient_views
    return report


def save_guarded_report(report: dict[str, Any], output_path: str) -> None:
    _ensure_parent(output_path)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
