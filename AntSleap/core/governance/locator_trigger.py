import json
import os
from typing import Any


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _load_history(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("history_root_not_object")
    runs = payload.get("runs")
    if not isinstance(runs, list) or len(runs) == 0:
        raise ValueError("history_runs_missing")
    return payload


def _target_views_for_run(run: dict[str, Any], fallback: list[str]) -> list[str]:
    target_views = run.get("target_views")
    if isinstance(target_views, list) and target_views:
        return [str(item) for item in target_views]
    return fallback


def evaluate_locator_upgrade_trigger(history_path: str) -> dict[str, Any]:
    payload = _load_history(history_path)
    runs = payload.get("runs", [])

    policy = payload.get("policy", {})
    if not isinstance(policy, dict):
        policy = {}

    consecutive_fail_runs = int(policy.get("consecutive_fail_runs", 2))
    single_run_pass_rate_gap = float(policy.get("single_run_pass_rate_gap", 0.05))

    default_target_views = payload.get("target_views", ["lateral", "dorsal"])
    if not isinstance(default_target_views, list) or not default_target_views:
        default_target_views = ["lateral", "dorsal"]
    default_target_views = [str(item) for item in default_target_views]

    run_assessment: list[dict[str, Any]] = []
    consecutive_streak = 0
    triggered = False
    reason_codes: list[str] = []

    for index, raw_run in enumerate(runs):
        if not isinstance(raw_run, dict):
            continue

        run_id = str(raw_run.get("run_id", f"run_{index+1}"))
        target_views = _target_views_for_run(raw_run, default_target_views)

        target_view_reports = raw_run.get("target_view_reports", {})
        if not isinstance(target_view_reports, dict):
            target_view_reports = {}

        run_fail = False
        pass_rates: list[float] = []
        failed_views: list[str] = []

        for view in target_views:
            view_report = target_view_reports.get(view, {})
            if not isinstance(view_report, dict):
                run_fail = True
                failed_views.append(view)
                continue

            if not bool(view_report.get("pass", False)):
                run_fail = True
                failed_views.append(view)

            metrics = view_report.get("metrics", {})
            if isinstance(metrics, dict):
                pass_rate_value = metrics.get("pass_rate")
                if isinstance(pass_rate_value, (int, float)):
                    pass_rates.append(float(pass_rate_value))

        if run_fail:
            consecutive_streak += 1
        else:
            consecutive_streak = 0

        gap = 0.0
        if len(pass_rates) >= 2:
            gap = max(pass_rates) - min(pass_rates)

        if consecutive_streak >= consecutive_fail_runs:
            code = f"trigger_consecutive_failures:{run_id}:streak={consecutive_streak}"
            if code not in reason_codes:
                reason_codes.append(code)
            triggered = True

        if gap > single_run_pass_rate_gap:
            code = f"trigger_pass_rate_gap:{run_id}:gap={round(gap, 6)}"
            if code not in reason_codes:
                reason_codes.append(code)
            triggered = True

        run_assessment.append(
            {
                "run_id": run_id,
                "target_views": target_views,
                "run_fail": run_fail,
                "failed_views": failed_views,
                "pass_rate_gap": round(gap, 6),
                "consecutive_fail_streak": consecutive_streak,
            }
        )

    return {
        "schema_version": "core2-locator-trigger-v1",
        "history_path": history_path,
        "triggered": triggered,
        "trigger_rules": {
            "consecutive_fail_runs": consecutive_fail_runs,
            "single_run_pass_rate_gap": single_run_pass_rate_gap,
        },
        "reason_codes": reason_codes,
        "runs_evaluated": run_assessment,
    }


def save_locator_trigger(report: dict[str, Any], output_path: str) -> None:
    _ensure_parent(output_path)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
