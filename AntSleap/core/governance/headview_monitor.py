import json
import os
from typing import Any


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


def build_head_view_monitor(metrics_path: str) -> dict[str, Any]:
    payload = _load_metrics(metrics_path)
    metrics_by_view = payload.get("metrics_by_view", {})
    head_metrics = metrics_by_view.get("head_frontal")

    if not isinstance(head_metrics, dict):
        return {
            "schema_version": "core2-head-monitor-v1",
            "metrics_path": metrics_path,
            "status": "no_headview_samples",
            "blocking": False,
            "sample_count": 0,
            "head_view_metrics": None,
        }

    sample_count_value = head_metrics.get("sample_count", 0)
    if not isinstance(sample_count_value, (int, float)):
        sample_count_value = 0

    sample_count = int(sample_count_value)
    if sample_count <= 0:
        return {
            "schema_version": "core2-head-monitor-v1",
            "metrics_path": metrics_path,
            "status": "no_headview_samples",
            "blocking": False,
            "sample_count": 0,
            "head_view_metrics": {
                "pass_rate": float(head_metrics.get("pass_rate", 0.0) or 0.0),
                "boundary_overlap": float(head_metrics.get("boundary_overlap", 0.0) or 0.0),
                "localization_error_px": float(
                    head_metrics.get("localization_error_px", 0.0) or 0.0
                ),
            },
        }

    monitor = {
        "schema_version": "core2-head-monitor-v1",
        "metrics_path": metrics_path,
        "status": "observed",
        "blocking": False,
        "sample_count": sample_count,
        "head_view_metrics": {
            "pass_rate": float(head_metrics.get("pass_rate", 0.0) or 0.0),
            "boundary_overlap": float(head_metrics.get("boundary_overlap", 0.0) or 0.0),
            "localization_error_px": float(
                head_metrics.get("localization_error_px", 0.0) or 0.0
            ),
        },
    }
    return monitor


def save_head_view_monitor(monitor: dict[str, Any], output_path: str) -> None:
    _ensure_parent(output_path)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(monitor, handle, ensure_ascii=False, indent=2)
