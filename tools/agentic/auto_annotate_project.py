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

from core.project import ProjectManager  # noqa: E402


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


def _apply_payload(
    manager: ProjectManager,
    image_path: str,
    payload: Any,
    only_new: bool,
) -> dict[str, Any]:
    polygons, auto_boxes = _extract_prediction_payload(payload)
    taxonomy = set(manager.project_data.get("taxonomy", []))
    existing_parts = set(manager.get_labels(image_path).keys())
    image_size = _image_size(image_path)

    saved = 0
    rejected: list[dict[str, str]] = []
    for part_name, raw_points in polygons.items():
        clean_part = str(part_name).strip()
        if not clean_part:
            rejected.append({"part": str(part_name), "reason": "empty_part"})
            continue
        if taxonomy and clean_part not in taxonomy:
            rejected.append({"part": clean_part, "reason": "unknown_taxonomy"})
            continue
        if only_new and clean_part in existing_parts:
            rejected.append({"part": clean_part, "reason": "already_labeled"})
            continue
        clean_polygon = _clean_polygon(raw_points, image_size)
        if clean_polygon is None:
            rejected.append({"part": clean_part, "reason": "invalid_polygon"})
            continue
        clean_box = _clean_box(auto_boxes.get(clean_part), image_size)
        if clean_box is None:
            xs = [point[0] for point in clean_polygon]
            ys = [point[1] for point in clean_polygon]
            clean_box = _clean_box([min(xs), min(ys), max(xs), max(ys)], image_size)
        manager.update_label(
            image_path,
            clean_part,
            clean_polygon,
            "Auto-Annotated",
            auto_box=clean_box,
            save=False,
        )
        existing_parts.add(clean_part)
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
    parser = argparse.ArgumentParser(description="Apply batch auto-annotation predictions to a Formica-Flow project JSON.")
    parser.add_argument("--project", required=True, help="Input project JSON.")
    parser.add_argument("--out", required=True, help="Output project JSON.")
    parser.add_argument("--predictions", default="", help="Prediction JSON. Omit only with --run-engine.")
    parser.add_argument("--run-engine", action="store_true", help="Run AntEngine.predict_full_pipeline for each project image.")
    parser.add_argument("--only-new", action="store_true", help="Do not overwrite already-labeled parts.")
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
        results.append(_apply_payload(manager, image_path, record.get("payload"), bool(args.only_new)))

    manager.save_project()
    report = {
        "schema_version": "formica-auto-annotation-report-v1",
        "project_input": project_path,
        "project_output": out_project,
        "prediction_source": "engine" if args.run_engine else os.path.abspath(args.predictions),
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
