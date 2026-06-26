import argparse
import json
import os
import sys
from typing import Any


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
ANTSLEAP_ROOT = os.path.join(REPO_ROOT, "AntSleap")
if ANTSLEAP_ROOT not in sys.path:
    sys.path.insert(0, ANTSLEAP_ROOT)

from core.project import ProjectManager  # noqa: E402
from core.project import MULTIMODAL_SAMPLE_SCHEMA_VERSION  # noqa: E402
from core.safe_io import atomic_write_json  # noqa: E402


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _write_json(path: str, payload: dict[str, Any]) -> None:
    atomic_write_json(path, payload, indent=2, ensure_ascii=False)


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                records.append(payload)
    return records


def _load_json_dict(path: str) -> dict[str, Any]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_not_object:{path}")
    return payload


def _write_jsonl(path: str, records: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _enrich_jsonl(output_dir: str, run_id: str, model_provenance: dict[str, Any]) -> None:
    jsonl_path = os.path.join(output_dir, "multimodal_dataset.jsonl")
    records = _read_jsonl(jsonl_path)
    if not records:
        return
    for record in records:
        record.setdefault("schema_version", MULTIMODAL_SAMPLE_SCHEMA_VERSION)
        record.setdefault("source_provenance", {})
        record["export_run_id"] = run_id
        record["model_provenance"] = model_provenance
    _write_jsonl(jsonl_path, records)


def _validate_export(output_dir: str) -> dict[str, Any]:
    jsonl_path = os.path.join(output_dir, "multimodal_dataset.jsonl")
    records = _read_jsonl(jsonl_path)
    missing_refs: list[dict[str, str]] = []
    required_fields = {
        "id",
        "image_global",
        "image_local",
        "text",
        "label",
        "taxon",
        "taxon_rank",
        "taxon_metadata",
        "segmentation_local",
        "bbox_global",
        "bbox_original",
        "schema_version",
        "source_provenance",
        "export_run_id",
        "model_provenance",
    }
    missing_fields: list[dict[str, str]] = []

    for index, record in enumerate(records):
        record_id = str(record.get("id", f"row_{index}") or f"row_{index}")
        for field in sorted(required_fields):
            if field not in record:
                missing_fields.append({"id": record_id, "field": field})
        for ref_field in ("image_global", "image_local"):
            rel_path = str(record.get(ref_field, "") or "")
            if not rel_path:
                missing_refs.append({"id": record_id, "field": ref_field, "path": rel_path})
                continue
            abs_path = os.path.normpath(os.path.join(output_dir, rel_path))
            if not os.path.exists(abs_path):
                missing_refs.append({"id": record_id, "field": ref_field, "path": abs_path})

    return {
        "jsonl_path": jsonl_path,
        "record_count": len(records),
        "missing_reference_count": len(missing_refs),
        "missing_field_count": len(missing_fields),
        "missing_references": missing_refs[:50],
        "missing_fields": missing_fields[:50],
        "valid": os.path.exists(jsonl_path) and not missing_refs and not missing_fields,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a TaxaMask project as a multimodal JSONL dataset.")
    parser.add_argument("--project", required=True, help="Input TaxaMask project JSON or SQLite manifest.")
    parser.add_argument("--out", required=True, help="Output dataset directory.")
    parser.add_argument("--crop-size", type=int, default=512, help="Local crop size in pixels.")
    parser.add_argument("--global-size", type=int, default=1024, help="Max global image size in pixels.")
    parser.add_argument("--summary", default="", help="Optional export summary JSON path.")
    parser.add_argument("--run-id", default="", help="Run id to attach to every JSONL row.")
    parser.add_argument("--model-provenance", default="", help="Optional JSON file describing model weights/config used upstream.")
    args = parser.parse_args()

    project_path = os.path.abspath(args.project)
    output_dir = os.path.abspath(args.out)
    os.makedirs(output_dir, exist_ok=True)

    manager = ProjectManager()
    manager.load_project(project_path)
    exported_count = manager.export_multimodal_dataset(
        output_dir,
        crop_size=max(1, int(args.crop_size)),
        global_size=max(1, int(args.global_size)),
    )
    model_profile_summary_path = ""
    if hasattr(manager, "write_model_profile_export_summary"):
        model_profile_summary_path = manager.write_model_profile_export_summary(
            output_dir,
            export_format="multimodal",
        )
    run_id = args.run_id.strip() or os.path.basename(os.path.normpath(output_dir)) or "multimodal_export"
    model_provenance = _load_json_dict(args.model_provenance)
    _enrich_jsonl(output_dir, run_id, model_provenance)
    validation = _validate_export(output_dir)
    summary = {
        "schema_version": "taxamask-multimodal-export-summary-v1",
        "project_path": project_path,
        "output_dir": output_dir,
        "crop_size": max(1, int(args.crop_size)),
        "global_size": max(1, int(args.global_size)),
        "run_id": run_id,
        "model_provenance_path": os.path.abspath(args.model_provenance) if args.model_provenance else "",
        "model_profile_summary_path": os.path.abspath(model_profile_summary_path) if model_profile_summary_path else "",
        "exported_count": int(exported_count),
        "validation": validation,
    }
    summary_path = os.path.abspath(args.summary) if args.summary else os.path.join(output_dir, "export_summary.json")
    _write_json(summary_path, summary)

    print(f"exported_count={exported_count}")
    print(f"valid={str(bool(validation.get('valid'))).lower()}")
    print(f"summary={summary_path}")
    return 0 if bool(validation.get("valid")) or exported_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
