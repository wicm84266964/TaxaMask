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


def _count_pdfs(source_dir: str) -> int:
    return len(list(Path(source_dir).glob("*.pdf")))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TaxaMask PDF literature screening without the Qt GUI.")
    parser.add_argument("--pdf-source-dir", required=True, help="Directory containing PDFs.")
    parser.add_argument("--out", required=True, help="Output directory for screening artifacts.")
    parser.add_argument("--config", default="", help="Optional classifier config JSON.")
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""), help="LLM API key.")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", ""), help="LLM API base URL.")
    parser.add_argument("--model", default="gpt-5.4", help="LLM model name.")
    parser.add_argument("--run-index", default="", help="Optional run index JSON path.")
    args = parser.parse_args()

    source_dir = os.path.abspath(args.pdf_source_dir)
    output_dir = os.path.abspath(args.out)
    run_index_path = os.path.abspath(args.run_index) if args.run_index else os.path.join(output_dir, "run_index.json")
    os.makedirs(output_dir, exist_ok=True)

    started = time.time()
    config = _load_json_dict(args.config)
    run_index: dict[str, Any] = {
        "schema_version": "taxamask-pdf-screening-run-v1",
        "status": "running",
        "source_dir": source_dir,
        "output_dir": output_dir,
        "config_path": os.path.abspath(args.config) if args.config else "",
        "model": args.model,
        "pdf_count": _count_pdfs(source_dir) if os.path.isdir(source_dir) else 0,
        "started_at_unix": started,
        "finished_at_unix": None,
        "duration_seconds": None,
        "result": None,
        "error": "",
    }
    _write_json(run_index_path, run_index)

    try:
        from core.pdf_processor.pdf_classifier import LLMScreenPDFClassifier

        classifier = LLMScreenPDFClassifier(
            source_folder=source_dir,
            output_folder=output_dir,
            api_key=args.api_key,
            base_url=args.base_url,
            model=args.model,
            config=config,
        )
        result = classifier.batch_classify()
        status = "passed"
        error = ""
    except Exception as exc:
        result = None
        status = "failed"
        error = str(exc)

    finished = time.time()
    run_index.update(
        {
            "status": status,
            "finished_at_unix": finished,
            "duration_seconds": round(finished - started, 3),
            "result": result,
            "error": error,
        }
    )
    _write_json(run_index_path, run_index)

    print(f"status={status}")
    print(f"pdf_count={run_index['pdf_count']}")
    print(f"run_index={run_index_path}")
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
