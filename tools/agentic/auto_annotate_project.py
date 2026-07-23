import argparse
import json
import os
import sys
from typing import Any

from PIL import Image


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
ANTSLEAP_ROOT = os.path.join(REPO_ROOT, "AntSleap")
if ANTSLEAP_ROOT not in sys.path:
    sys.path.insert(0, ANTSLEAP_ROOT)

from core.project import (  # noqa: E402
    AUTO_BOX_REVIEW_CONFIRMED,
    AUTO_BOX_REVIEW_DRAFT,
    AUTO_BOX_SOURCE_MODEL,
    ProjectManager,
)


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str, payload: dict[str, Any]) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _extract_prediction_payload(payload: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    polygons: dict[str, Any] = {}
    auto_boxes: dict[str, Any] = {}
    if not isinstance(payload, dict):
        return polygons, auto_boxes
    if isinstance(payload.get("polygons"), dict):
        polygons = payload.get("polygons", {})
        if isinstance(payload.get("auto_boxes"), dict):
            auto_boxes = payload.get("auto_boxes", {})
        return polygons, auto_boxes
    for key, value in payload.items():
        if key.endswith("_BOX") and isinstance(value, list):
            xs = [point[0] for point in value if isinstance(point, (list, tuple)) and len(point) >= 2]
            ys = [point[1] for point in value if isinstance(point, (list, tuple)) and len(point) >= 2]
            if xs and ys:
                auto_boxes[key.replace("_BOX", "")] = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]
        elif isinstance(value, list):
            polygons[key] = value
    return polygons, auto_boxes


def _prediction_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        records = payload.get("predictions")
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
        images = payload.get("images")
        if isinstance(images, dict):
            return [
                {"image_path": image_path, "payload": prediction}
                for image_path, prediction in images.items()
            ]
        return [
            {"image_path": image_path, "payload": prediction}
            for image_path, prediction in payload.items()
            if isinstance(image_path, str) and isinstance(prediction, dict)
        ]
    return []


def _image_size(path: str) -> tuple[float, float] | None:
    try:
        with Image.open(path) as image:
            width, height = image.size
        return float(width), float(height)
    except Exception:
        return None


def _clean_box(raw_box: Any, image_size: tuple[float, float] | None) -> list[float] | None:
    if not isinstance(raw_box, (list, tuple)) or len(raw_box) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(value) for value in raw_box]
    except Exception:
        return None
    if image_size is not None:
        width, height = image_size
        x1 = max(0.0, min(x1, width - 0.1))
        x2 = max(0.0, min(x2, width - 0.1))
        y1 = max(0.0, min(y1, height - 0.1))
        y2 = max(0.0, min(y2, height - 0.1))
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]


def _clean_polygon(raw_points: Any, image_size: tuple[float, float] | None) -> list[list[float]] | None:
    if not isinstance(raw_points, list) or len(raw_points) < 3:
        return None
    clean: list[list[float]] = []
    for point in raw_points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            x = float(point[0])
            y = float(point[1])
        except Exception:
            continue
        if image_size is not None:
            width, height = image_size
            x = max(0.0, min(x, width - 0.1))
            y = max(0.0, min(y, height - 0.1))
        clean.append([x, y])
    return clean if len(clean) >= 3 else None


def _is_unconfirmed_ai_draft(manager: ProjectManager, image_path: str, part_name: str) -> bool:
    labels_entry = manager.project_data.get("labels", {}).get(image_path, {})
    if not isinstance(labels_entry, dict):
        return False
    descriptions = labels_entry.get("descriptions", {}) if isinstance(labels_entry.get("descriptions", {}), dict) else {}
    if descriptions.get(part_name) != "Auto-Annotated":
        return False
    meta = labels_entry.get("auto_box_meta", {}) if isinstance(labels_entry.get("auto_box_meta", {}), dict) else {}
    part_meta = meta.get(part_name, {}) if isinstance(meta.get(part_name), dict) else {}
    return str(part_meta.get("review_status") or AUTO_BOX_REVIEW_DRAFT).strip() != AUTO_BOX_REVIEW_CONFIRMED


def _can_model_replace(manager: ProjectManager, image_path: str, part_name: str, only_new: bool) -> bool:
    labels_by_part = manager.get_labels(image_path)
    has_label = part_name in labels_by_part
    auto_boxes = manager.get_auto_boxes(image_path)
    has_auto_box = isinstance(auto_boxes, dict) and part_name in auto_boxes
    if not has_label and not has_auto_box:
        return True
    meta = manager.get_auto_box_meta(image_path)
    part_meta = meta.get(part_name, {}) if isinstance(meta, dict) and isinstance(meta.get(part_name), dict) else {}
    review_status = str(part_meta.get("review_status") or AUTO_BOX_REVIEW_DRAFT).strip()
    if review_status == AUTO_BOX_REVIEW_CONFIRMED:
        return False
    if has_label and not _is_unconfirmed_ai_draft(manager, image_path, part_name):
        return False
    if not only_new:
        return True
    return has_label or has_auto_box


def _apply_payload(
    manager: ProjectManager,
    image_path: str,
    payload: Any,
    only_new: bool,
    save_drafts_only: bool = False,
) -> dict[str, Any]:
    polygons, auto_boxes = _extract_prediction_payload(payload)
    taxonomy = set(manager.project_data.get("taxonomy", []))
    image_size = _image_size(image_path)

    saved = 0
    rejected: list[dict[str, str]] = []
    part_names = list(polygons.keys())
    if save_drafts_only:
        for part_name in auto_boxes.keys():
            if part_name not in polygons:
                part_names.append(part_name)

    for part_name in part_names:
        raw_points = polygons.get(part_name)
        clean_part = str(part_name).strip()
        if not clean_part:
            rejected.append({"part": str(part_name), "reason": "empty_part"})
            continue
        if taxonomy and clean_part not in taxonomy:
            rejected.append({"part": clean_part, "reason": "unknown_taxonomy"})
            continue
        if not _can_model_replace(manager, image_path, clean_part, only_new):
            rejected.append({"part": clean_part, "reason": "already_labeled"})
            continue
        clean_box = _clean_box(auto_boxes.get(clean_part), image_size)
        clean_polygon = _clean_polygon(raw_points, image_size)
        if clean_polygon is None and not save_drafts_only:
            rejected.append({"part": clean_part, "reason": "invalid_polygon"})
            continue
        if clean_box is None:
            if clean_polygon is None:
                rejected.append({"part": clean_part, "reason": "invalid_box"})
                continue
            xs = [point[0] for point in clean_polygon]
            ys = [point[1] for point in clean_polygon]
            clean_box = _clean_box([min(xs), min(ys), max(xs), max(ys)], image_size)
        if save_drafts_only:
            update_auto_box = getattr(manager, "update_auto_box", None)
            if callable(update_auto_box) and clean_box is not None:
                update_auto_box(
                    image_path,
                    clean_part,
                    clean_box,
                    description_text="Auto-Annotated",
                    source_meta={"source": AUTO_BOX_SOURCE_MODEL, "review_status": AUTO_BOX_REVIEW_DRAFT},
                    save=False,
                )
            else:
                manager.update_label(
                    image_path,
                    clean_part,
                    [],
                    "Auto-Annotated",
                    auto_box=clean_box,
                    save=False,
                    training_source=AUTO_BOX_SOURCE_MODEL,
                    training_review_status=AUTO_BOX_REVIEW_DRAFT,
                    training_accepted_via="",
                )
        else:
            manager.update_label(
                image_path,
                clean_part,
                clean_polygon,
                "Auto-Annotated",
                auto_box=clean_box,
                save=False,
                training_source=AUTO_BOX_SOURCE_MODEL,
                training_review_status=AUTO_BOX_REVIEW_DRAFT,
                training_accepted_via="",
            )
            update_auto_box = getattr(manager, "update_auto_box", None)
            if callable(update_auto_box) and clean_box is not None:
                update_auto_box(
                    image_path,
                    clean_part,
                    clean_box,
                    source_meta={"source": AUTO_BOX_SOURCE_MODEL, "review_status": AUTO_BOX_REVIEW_DRAFT},
                    save=False,
                )
        saved += 1
    return {"image_path": image_path, "detected_count": len(polygons), "saved_count": saved, "rejected": rejected}


def _run_engine_predictions(manager: ProjectManager, confidence: float, only_new: bool = False, device: str = "auto") -> list[dict[str, Any]]:
    from core.engine import AntEngine  # Imported lazily because this can initialize model weights.

    engine = AntEngine(num_classes=len(manager.get_locator_scope()), device=device)
    records: list[dict[str, Any]] = []
    for image_path in manager.project_data.get("images", []):
        if only_new and manager.get_labels(image_path):
            continue
        payload = engine.predict_full_pipeline(
            image_path,
            manager.project_data.get("taxonomy", []),
            manager.get_locator_scope(),
            conf_thresh=confidence,
        )
        records.append({"image_path": image_path, "payload": payload})
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply batch auto-annotation predictions to a TaxaMask project JSON.")
    parser.add_argument("--project", required=True, help="Input project JSON.")
    parser.add_argument("--out", required=True, help="Output project JSON.")
    parser.add_argument("--predictions", default="", help="Prediction JSON. Omit only with --run-engine.")
    parser.add_argument("--run-engine", action="store_true", help="Run AntEngine.predict_full_pipeline for each project image.")
    parser.add_argument("--only-new", action="store_true", help="Do not overwrite already-labeled parts.")
    parser.add_argument("--draft-boxes-only", action="store_true", help="Write only draft auto_boxes instead of training-eligible polygons.")
    parser.add_argument("--confidence", type=float, default=0.35, help="Inference confidence threshold for --run-engine.")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto", help="Compute device preference for --run-engine.")
    parser.add_argument("--report", default="", help="Optional annotation report JSON path.")
    args = parser.parse_args()

    project_path = os.path.abspath(args.project)
    out_project = os.path.abspath(args.out)
    report_path = os.path.abspath(args.report) if args.report else os.path.splitext(out_project)[0] + "_auto_annotation_report.json"
    os.makedirs(os.path.dirname(out_project) or os.getcwd(), exist_ok=True)

    manager = ProjectManager()
    manager.load_project(project_path)
    manager.current_project_path = out_project
    manager.enable_legacy_json_writes_for_compatibility(True)

    if args.run_engine:
        records = _run_engine_predictions(manager, float(args.confidence), only_new=bool(args.only_new), device=args.device)
    elif args.predictions:
        records = _prediction_records(_load_json(os.path.abspath(args.predictions)))
    else:
        raise SystemExit("--predictions is required unless --run-engine is set")

    image_lookup = {os.path.abspath(path): path for path in manager.project_data.get("images", [])}
    results: list[dict[str, Any]] = []
    for record in records:
        raw_image_path = str(record.get("image_path", "") or "")
        abs_image_path = os.path.abspath(raw_image_path)
        image_path = image_lookup.get(abs_image_path, manager._to_absolute(raw_image_path))
        if not image_path or not os.path.exists(image_path):
            results.append({"image_path": raw_image_path, "detected_count": 0, "saved_count": 0, "rejected": [{"part": "", "reason": "image_not_found"}]})
            continue
        if image_path not in manager.project_data.get("images", []):
            manager.add_images([image_path])
        results.append(_apply_payload(manager, image_path, record.get("payload"), bool(args.only_new), save_drafts_only=bool(args.draft_boxes_only)))

    manager.save_project()
    report = {
        "schema_version": "formica-auto-annotation-report-v1",
        "project_input": project_path,
        "project_output": out_project,
        "prediction_source": "engine" if args.run_engine else os.path.abspath(args.predictions),
        "draft_boxes_only": bool(args.draft_boxes_only),
        "image_count": len(results),
        "saved_label_count": sum(int(item.get("saved_count", 0) or 0) for item in results),
        "rejected_count": sum(len(item.get("rejected", []) or []) for item in results),
        "results": results,
    }
    _write_json(report_path, report)

    print(f"image_count={report['image_count']}")
    print(f"saved_label_count={report['saved_label_count']}")
    print(f"rejected_count={report['rejected_count']}")
    print(f"project_output={out_project}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
