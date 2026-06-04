import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from PIL import Image


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
ANTSLEAP_ROOT = os.path.join(REPO_ROOT, "AntSleap")
for path in (REPO_ROOT, ANTSLEAP_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

from core.project import ProjectManager  # noqa: E402
from core.vlm_preannotation import (  # noqa: E402
    load_vlm_api_config_from_runtime_settings,
    parse_vlm_response,
    run_vlm_preannotation,
)


def _write_json(path: str, payload: dict[str, Any]) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _image_size(path: str) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _target_parts(manager: ProjectManager, parts_arg: str) -> list[str]:
    if parts_arg.strip():
        requested = [part.strip() for part in parts_arg.split(",") if part.strip()]
        taxonomy = set(manager.project_data.get("taxonomy", []))
        return [part for part in requested if not taxonomy or part in taxonomy]
    if hasattr(manager, "get_vlm_preannotation_target_parts"):
        return manager.get_vlm_preannotation_target_parts()
    settings = manager.project_data.get("vlm_preannotation", {})
    if isinstance(settings, dict):
        taxonomy = set(manager.project_data.get("taxonomy", []))
        return [
            str(part).strip()
            for part in settings.get("target_parts", [])
            if str(part).strip() and (not taxonomy or str(part).strip() in taxonomy)
        ]
    return []


def _records_from_prediction_fixture(
    prediction_json: str,
    manager: ProjectManager,
    target_parts: list[str],
    grid_cols: int,
    grid_rows: int,
    min_confidence: float,
) -> list[dict[str, Any]]:
    payload = _load_json(prediction_json)
    images_payload = payload.get("images") if isinstance(payload, dict) else None
    if not isinstance(images_payload, dict):
        images_payload = payload if isinstance(payload, dict) else {}

    records: list[dict[str, Any]] = []
    for raw_image_path, raw_response in images_payload.items():
        image_path = manager._to_absolute(str(raw_image_path))
        if not os.path.exists(image_path):
            records.append(
                {
                    "image_path": str(raw_image_path),
                    "status": "failed",
                    "saved_box_count": 0,
                    "rejected": [{"part": "", "reason": "image_not_found"}],
                }
            )
            continue
        if isinstance(raw_response, str):
            response_text = raw_response
        else:
            response_text = json.dumps(raw_response, ensure_ascii=False)
        candidates, rejected, _parsed = parse_vlm_response(
            response_text,
            target_parts,
            _image_size(image_path),
            grid_cols=grid_cols,
            grid_rows=grid_rows,
            min_confidence=min_confidence,
        )
        records.append(
            {
                "image_path": image_path,
                "status": "passed",
                "candidates": candidates,
                "rejected": rejected,
                "saved_box_count": 0,
            }
        )
    return records


def _apply_candidates(manager: ProjectManager, image_path: str, candidates: list[dict[str, Any]], only_new: bool) -> int:
    existing_parts = set(manager.get_labels(image_path).keys())
    saved = 0
    for candidate in candidates:
        part_name = str(candidate.get("part", "") or "").strip()
        box = candidate.get("box_xyxy")
        if not part_name or not box:
            continue
        if only_new and (part_name in existing_parts or part_name in manager.get_auto_boxes(image_path)):
            continue
        note = "Auto-Annotated"
        if hasattr(manager, "update_auto_box"):
            if manager.update_auto_box(image_path, part_name, box, description_text=note, save=False):
                saved += 1
        else:
            manager.update_label(image_path, part_name, [], note, auto_box=box, save=False)
            saved += 1
    return saved


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VLM first-mile box preannotation for a TaxaMask project.")
    parser.add_argument("--project", required=True, help="Input project JSON.")
    parser.add_argument("--out", required=True, help="Output project JSON.")
    parser.add_argument("--images", default="", help="Comma-separated image paths. Defaults to project images.")
    parser.add_argument("--parts", default="", help="Comma-separated target parts. Defaults to locator/common ant parts.")
    parser.add_argument("--api-settings", default=str(Path(REPO_ROOT) / "screener_configs" / "api_runtime_settings.json"))
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", ""))
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--model", default="")
    parser.add_argument("--api-protocol", default="")
    parser.add_argument("--grid-cols", type=int, default=12, help="Legacy parser fallback for old grid-coordinate fixtures.")
    parser.add_argument("--grid-rows", type=int, default=12, help="Legacy parser fallback for old grid-coordinate fixtures.")
    parser.add_argument("--min-confidence", type=float, default=0.25)
    parser.add_argument("--only-new", action="store_true", help="Do not add boxes for already labeled parts.")
    parser.add_argument("--dry-run", action="store_true", help="Create VLM input images and reports without calling the model.")
    parser.add_argument("--prediction-json", default="", help="Offline fixture containing raw VLM responses or detections.")
    parser.add_argument("--artifacts-dir", default="", help="Directory for VLM input images and reports.")
    parser.add_argument("--report", default="", help="Summary report JSON path.")
    args = parser.parse_args()

    project_path = os.path.abspath(args.project)
    out_project = os.path.abspath(args.out)
    artifacts_dir = os.path.abspath(args.artifacts_dir) if args.artifacts_dir else os.path.join(
        os.path.dirname(out_project) or os.getcwd(),
        "vlm_preannotation",
    )
    report_path = os.path.abspath(args.report) if args.report else os.path.splitext(out_project)[0] + "_vlm_preannotation_report.json"
    os.makedirs(os.path.dirname(out_project) or os.getcwd(), exist_ok=True)
    os.makedirs(artifacts_dir, exist_ok=True)

    manager = ProjectManager()
    manager.load_project(project_path)
    manager.current_project_path = out_project
    target_parts = _target_parts(manager, args.parts)
    if not target_parts:
        print("error=no_vlm_target_parts_configured", file=sys.stderr)
        return 2

    if args.images.strip():
        image_paths = [manager._to_absolute(item.strip()) for item in args.images.split(",") if item.strip()]
    else:
        image_paths = list(manager.project_data.get("images", []))

    api_config = load_vlm_api_config_from_runtime_settings(args.api_settings)
    if args.base_url:
        api_config["base_url"] = args.base_url
    if args.api_key:
        api_config["api_key"] = args.api_key
    if args.model:
        api_config["model"] = args.model
    if args.api_protocol:
        api_config["api_protocol"] = args.api_protocol

    records: list[dict[str, Any]] = []
    if args.prediction_json:
        records = _records_from_prediction_fixture(
            os.path.abspath(args.prediction_json),
            manager,
            target_parts,
            args.grid_cols,
            args.grid_rows,
            args.min_confidence,
        )
    else:
        for image_path in image_paths:
            if not os.path.exists(image_path):
                records.append(
                    {
                        "image_path": image_path,
                        "status": "failed",
                        "saved_box_count": 0,
                        "rejected": [{"part": "", "reason": "image_not_found"}],
                    }
                )
                continue
            try:
                result = run_vlm_preannotation(
                    image_path,
                    target_parts,
                    artifacts_dir,
                    api_config=api_config,
                    grid_cols=args.grid_cols,
                    grid_rows=args.grid_rows,
                    min_confidence=args.min_confidence,
                    dry_run=bool(args.dry_run),
                )
                records.append(
                    {
                        "image_path": image_path,
                        "status": result.get("status"),
                        "candidates": result.get("candidates", []),
                        "rejected": result.get("rejected", []),
                        "overlay_path": result.get("overlay", {}).get("overlay_path", ""),
                        "report_path": result.get("report_path", ""),
                        "saved_box_count": 0,
                    }
                )
            except Exception as exc:
                records.append(
                    {
                        "image_path": image_path,
                        "status": "failed",
                        "saved_box_count": 0,
                        "rejected": [{"part": "", "reason": str(exc)}],
                    }
                )

    total_saved = 0
    if not args.dry_run:
        project_images = set(manager.project_data.get("images", []))
        for record in records:
            if record.get("status") not in {"passed", "fixture"}:
                continue
            image_path = str(record.get("image_path", "") or "")
            if image_path and image_path not in project_images and os.path.exists(image_path):
                manager.add_images([image_path])
                project_images.add(image_path)
            saved = _apply_candidates(manager, image_path, list(record.get("candidates", []) or []), bool(args.only_new))
            record["saved_box_count"] = saved
            total_saved += saved
        manager.save_project()

    report = {
        "schema_version": "taxamask-vlm-preannotation-project-report-v1",
        "project_input": project_path,
        "project_output": out_project,
        "artifacts_dir": artifacts_dir,
        "dry_run": bool(args.dry_run),
        "target_parts": target_parts,
        "image_count": len(records),
        "candidate_count": sum(len(item.get("candidates", []) or []) for item in records),
        "saved_box_count": total_saved,
        "rejected_count": sum(len(item.get("rejected", []) or []) for item in records),
        "records": records,
    }
    _write_json(report_path, report)
    if args.dry_run:
        manager.current_project_path = out_project
        manager.save_project()

    print(f"image_count={report['image_count']}")
    print(f"candidate_count={report['candidate_count']}")
    print(f"saved_box_count={report['saved_box_count']}")
    print(f"project_output={out_project}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
