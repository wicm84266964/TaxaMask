import json
import math
import os
from typing import Any


CANONICAL_VIEWS = ("lateral", "dorsal", "head_frontal", "unknown")


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _load_records(path: str, label: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    records: Any = payload
    if isinstance(payload, dict):
        records = payload.get("records", payload.get("samples", []))

    if not isinstance(records, list):
        raise ValueError(f"metric_input_incomplete:{label}_records_not_list")

    output: list[dict[str, Any]] = []
    for item in records:
        if isinstance(item, dict):
            output.append(item)
    return output


def _require_text(record: dict[str, Any], key: str, sample_fallback: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"metric_input_incomplete:{sample_fallback}:missing_{key}")
    return value.strip()


def _parse_bbox(record: dict[str, Any], sample_id: str, source: str) -> tuple[float, float, float, float]:
    bbox = record.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError(f"metric_input_incomplete:{sample_id}:{source}_bbox_invalid")

    try:
        x1 = float(bbox[0])
        y1 = float(bbox[1])
        x2 = float(bbox[2])
        y2 = float(bbox[3])
    except (TypeError, ValueError):
        raise ValueError(f"metric_input_incomplete:{sample_id}:{source}_bbox_non_numeric")

    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"metric_input_incomplete:{sample_id}:{source}_bbox_degenerate")
    return x1, y1, x2, y2


def _iou(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    inter_w = max(0.0, ix2 - ix1)
    inter_h = max(0.0, iy2 - iy1)
    inter_area = inter_w * inter_h

    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    denom = area_a + area_b - inter_area
    if denom <= 0:
        return 0.0
    return inter_area / denom


def _center_error_px(
    box_a: tuple[float, float, float, float],
    box_b: tuple[float, float, float, float],
) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    acx = (ax1 + ax2) / 2.0
    acy = (ay1 + ay2) / 2.0
    bcx = (bx1 + bx2) / 2.0
    bcy = (by1 + by2) / 2.0
    return math.dist((acx, acy), (bcx, bcy))


def calculate_per_view_metrics(pred_path: str, gt_path: str) -> dict[str, Any]:
    pred_records = _load_records(pred_path, "pred")
    gt_records = _load_records(gt_path, "gt")

    gt_map: dict[str, dict[str, Any]] = {}
    for gt_record in gt_records:
        sample_id = _require_text(gt_record, "sample_id", "gt_record")
        if sample_id in gt_map:
            raise ValueError(f"metric_input_incomplete:{sample_id}:duplicate_gt")
        gt_map[sample_id] = gt_record

    pred_ids: set[str] = set()
    per_view_accumulator: dict[str, dict[str, float]] = {}

    for pred_record in pred_records:
        sample_id = _require_text(pred_record, "sample_id", "pred_record")
        pred_ids.add(sample_id)

        gt_record = gt_map.get(sample_id)
        if gt_record is None:
            raise ValueError(f"metric_input_incomplete:missing_gt:{sample_id}")

        view = _require_text(gt_record, "view", sample_id)
        pred_bbox = _parse_bbox(pred_record, sample_id, "pred")
        gt_bbox = _parse_bbox(gt_record, sample_id, "gt")

        overlap = _iou(pred_bbox, gt_bbox)
        loc_err = _center_error_px(pred_bbox, gt_bbox)
        sample_pass = 1.0 if (overlap >= 0.5 and loc_err <= 20.0) else 0.0

        bucket = per_view_accumulator.setdefault(
            view,
            {
                "sample_count": 0.0,
                "pass_count": 0.0,
                "overlap_sum": 0.0,
                "loc_err_sum": 0.0,
            },
        )
        bucket["sample_count"] += 1.0
        bucket["pass_count"] += sample_pass
        bucket["overlap_sum"] += overlap
        bucket["loc_err_sum"] += loc_err

    for gt_sample_id in gt_map.keys():
        if gt_sample_id not in pred_ids:
            raise ValueError(f"metric_input_incomplete:missing_prediction:{gt_sample_id}")

    def finalize(view: str, stats: dict[str, float]) -> dict[str, Any]:
        count = int(stats["sample_count"])
        pass_count = int(stats["pass_count"])
        if count <= 0:
            return {
                "sample_count": 0,
                "pass_count": 0,
                "pass_rate": 0.0,
                "boundary_overlap": 0.0,
                "localization_error_px": 0.0,
            }

        return {
            "sample_count": count,
            "pass_count": pass_count,
            "pass_rate": round(stats["pass_count"] / count, 6),
            "boundary_overlap": round(stats["overlap_sum"] / count, 6),
            "localization_error_px": round(stats["loc_err_sum"] / count, 6),
        }

    ordered_views = sorted(
        per_view_accumulator.keys(),
        key=lambda item: (
            CANONICAL_VIEWS.index(item) if item in CANONICAL_VIEWS else len(CANONICAL_VIEWS),
            item,
        ),
    )
    metrics_by_view = {
        view: finalize(view, per_view_accumulator[view]) for view in ordered_views
    }

    result = {
        "schema_version": "core2-metrics-v1",
        "pred_path": pred_path,
        "gt_path": gt_path,
        "total_samples": len(pred_records),
        "views_present": ordered_views,
        "metrics_by_view": metrics_by_view,
    }
    return result


def save_per_view_metrics(report: dict[str, Any], output_path: str) -> None:
    _ensure_parent(output_path)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
