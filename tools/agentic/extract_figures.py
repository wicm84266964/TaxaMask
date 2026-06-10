import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.pdf_processor.figure_profile import load_figure_profile, profile_display_name  # noqa: E402
from core.pdf_processor.part_description_profile import (  # noqa: E402
    load_part_description_profile,
    profile_display_name as part_profile_display_name,
)


def _load_json_dict(path: str) -> dict[str, Any]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"config_root_not_object:{path}")
    return payload


def _write_json(path: str, payload: dict[str, Any]) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _pdf_files(source_dir: str) -> list[str]:
    return [str(path) for path in sorted(Path(source_dir).glob("*.pdf"))]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TaxaMask figure extraction without the Qt GUI.")
    parser.add_argument("--pdf-source-dir", required=True, help="Directory containing PDFs.")
    parser.add_argument("--db", required=True, help="Output SQLite DB path.")
    parser.add_argument("--multimodal-config", default="", help="Optional multimodal validator config JSON.")
    parser.add_argument("--figure-profile", default="", help="Optional figure extraction/review profile JSON.")
    parser.add_argument("--multimodal-profile", default="", help="Alias for --figure-profile.")
    parser.add_argument("--part-description-profile", default="", help="Optional pure-text taxon part-description extraction profile JSON.")
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""), help="Multimodal API key.")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", ""), help="Multimodal API base URL.")
    parser.add_argument("--model", default="", help="Multimodal model name.")
    parser.add_argument("--provider", default="newapi", help="Provider key for generated multimodal config.")
    parser.add_argument("--api-protocol", default="auto", help="auto, chat_completions, or responses.")
    parser.add_argument("--text-api-key", default="", help="Text LLM API key for taxon part-description extraction.")
    parser.add_argument("--text-base-url", default="", help="Text LLM API base URL for taxon part-description extraction.")
    parser.add_argument("--text-model", default="", help="Text LLM model for taxon part-description extraction.")
    parser.add_argument("--text-api-protocol", default="auto", help="Text LLM protocol: auto, chat_completions, or responses.")
    parser.add_argument("--disable-part-description-extraction", action="store_true", help="Skip text-only taxon part-description extraction.")
    parser.add_argument("--disable-multimodal-validation", action="store_true", help="Use local/mock review path.")
    parser.add_argument("--save-images", action="store_true", help="Save figure clips to files.")
    parser.add_argument("--run-index", default="", help="Optional run index JSON path.")
    args = parser.parse_args()

    source_dir = os.path.abspath(args.pdf_source_dir)
    db_path = os.path.abspath(args.db)
    output_dir = os.path.dirname(db_path) or os.getcwd()
    run_index_path = os.path.abspath(args.run_index) if args.run_index else os.path.join(output_dir, "figure_extraction_run_index.json")
    os.makedirs(output_dir, exist_ok=True)

    pdfs = _pdf_files(source_dir) if os.path.isdir(source_dir) else []
    started = time.time()
    figure_profile_path = os.path.abspath(args.figure_profile or args.multimodal_profile) if (args.figure_profile or args.multimodal_profile) else ""
    part_description_profile_path = os.path.abspath(args.part_description_profile) if args.part_description_profile else ""
    try:
        figure_profile = load_figure_profile(figure_profile_path) if figure_profile_path else load_figure_profile(None)
        figure_profile_name = profile_display_name(figure_profile) or "default"
        part_description_profile = (
            load_part_description_profile(part_description_profile_path)
            if part_description_profile_path
            else load_part_description_profile(None)
        )
        part_description_profile_name = part_profile_display_name(part_description_profile) or "default"
    except Exception as exc:
        figure_profile = None
        figure_profile_name = ""
        part_description_profile = None
        part_description_profile_name = ""
        status = "failed"
        error = f"profile_load_failed:{exc}"
        run_index = {
            "schema_version": "taxamask-figure-extraction-run-v1",
            "status": status,
            "source_dir": source_dir,
            "db_path": db_path,
            "pdf_count": len(pdfs),
            "figure_profile_path": figure_profile_path,
            "figure_profile_name": figure_profile_name,
            "part_description_profile_path": part_description_profile_path,
            "part_description_profile_name": part_description_profile_name,
            "started_at_unix": started,
            "finished_at_unix": time.time(),
            "duration_seconds": 0,
            "results": [],
            "summary": {},
            "error": error,
        }
        _write_json(run_index_path, run_index)
        print(error, file=sys.stderr)
        return 2

    run_index: dict[str, Any] = {
        "schema_version": "taxamask-figure-extraction-run-v1",
        "status": "running",
        "source_dir": source_dir,
        "db_path": db_path,
        "pdf_count": len(pdfs),
        "figure_profile_path": figure_profile_path,
        "figure_profile_name": figure_profile_name,
        "part_description_profile_path": part_description_profile_path,
        "part_description_profile_name": part_description_profile_name,
        "started_at_unix": started,
        "finished_at_unix": None,
        "duration_seconds": None,
        "results": [],
        "summary": {},
        "error": "",
    }
    _write_json(run_index_path, run_index)

    extractor: Any | None = None
    status = "passed"
    error = ""
    results: list[dict[str, Any]] = []
    multimodal_config = _load_json_dict(args.multimodal_config)
    if args.api_key or args.base_url or args.model:
        provider = str(args.provider or "newapi").strip().lower() or "newapi"
        multimodal_config.setdefault("providers", {})
        provider_config = multimodal_config["providers"].setdefault(provider, {})
        if args.api_key:
            provider_config["api_key"] = args.api_key
        if args.base_url:
            provider_config["base_url"] = args.base_url
        if args.model:
            provider_config["model"] = args.model
        multimodal_config["default_provider"] = provider
        multimodal_config["api_protocol"] = args.api_protocol
    text_part_config: dict[str, Any] = {
        "enabled": not bool(args.disable_part_description_extraction),
        "default_provider": "text_llm",
        "api_protocol": args.text_api_protocol,
        "providers": {
            "text_llm": {
                "api_key": args.text_api_key,
                "base_url": args.text_base_url,
                "model": args.text_model,
            }
        },
    }

    try:
        from core.pdf_processor.pdf_extractor import EnhancedPDFExtractionSystem  # noqa: E402

        extractor = EnhancedPDFExtractionSystem(
            output_db_path=db_path,
            save_images_to_files=bool(args.save_images),
            enable_multimodal_validation=not bool(args.disable_multimodal_validation),
            multimodal_config=multimodal_config,
            text_part_config=text_part_config,
            figure_profile=figure_profile,
            figure_profile_path=figure_profile_path,
            part_description_profile=part_description_profile,
            part_description_profile_path=part_description_profile_path,
        )
        for pdf_path in pdfs:
            try:
                result = extractor.extract_from_pdf(pdf_path)
                results.append({"pdf_path": pdf_path, "ok": True, "result": result, "error": ""})
            except Exception as exc:
                results.append({"pdf_path": pdf_path, "ok": False, "result": None, "error": str(exc)})
    except Exception as exc:
        status = "failed"
        error = str(exc)
    finally:
        if extractor is not None:
            extractor.close()

    finished = time.time()
    total = len(results)
    ok_count = sum(1 for item in results if bool(item.get("ok", False)))
    failed_count = total - ok_count
    if status != "failed":
        if failed_count:
            status = "partial" if ok_count else "failed"
        else:
            status = "passed"
    run_index.update(
        {
            "status": status,
            "finished_at_unix": finished,
            "duration_seconds": round(finished - started, 3),
            "results": results,
            "summary": {
                "total_pdfs": total,
                "successful_pdfs": ok_count,
                "failed_pdfs": failed_count,
                "figure_profile_name": figure_profile_name,
                "part_description_profile_name": part_description_profile_name,
                "multimodal_validation_enabled": not bool(args.disable_multimodal_validation),
                "part_description_extraction_enabled": not bool(args.disable_part_description_extraction),
                "text_part_model": str(args.text_model or ""),
                "multimodal_provider": str(multimodal_config.get("default_provider", "") or ""),
                "multimodal_model": str(
                    (
                        multimodal_config.get("providers", {})
                        .get(str(multimodal_config.get("default_provider", "") or ""), {})
                        .get("model", "")
                    )
                    or ""
                ),
            },
            "error": error,
        }
    )
    _write_json(run_index_path, run_index)

    print(f"status={status}")
    print(f"pdf_count={len(pdfs)}")
    print(f"successful_pdfs={ok_count}")
    print(f"run_index={run_index_path}")
    return 0 if status in {"passed", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
