from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from app.paper_distill.fs import absolute_path
from app.paper_distill.exporters import PaperDistillExporter
from app.paper_distill.layout import DEFAULT_ARTIFACTS_ROOT, DEFAULT_CACHE_ROOT
from app.paper_distill.models import BackendConfig, ExportFormat, ExportRequest, RunRequest
from app.paper_distill.service import build_service
from app.paper_distill.store import PaperArtifactStore


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the standalone paper distillation subsystem."
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run or resume paper distillation.")
    _ = run_parser.add_argument("--paper", required=True, help="Path to the paper markdown file.")
    target_selection = run_parser.add_mutually_exclusive_group(required=True)
    _ = target_selection.add_argument("--target-count", type=int)
    _ = target_selection.add_argument("--auto-target-count", action="store_true")
    _ = run_parser.add_argument("--min-target-count", type=int, default=6)
    _ = run_parser.add_argument("--max-target-count", type=int, default=24)
    _ = run_parser.add_argument("--batch-size", type=int, default=3)
    _ = run_parser.add_argument("--workspace-root", default=None)
    _ = run_parser.add_argument("--artifacts-root", default=None)
    _ = run_parser.add_argument("--cache-root", default=None)
    _ = run_parser.add_argument(
        "--backend",
        choices=["mock", "openai-compatible"],
        default=os.getenv("PAPER_DISTILL_BACKEND", "mock"),
    )
    _ = run_parser.add_argument(
        "--model",
        default=os.getenv("PAPER_DISTILL_MODEL", "mock-model"),
    )
    _ = run_parser.add_argument(
        "--base-url",
        default=os.getenv("PAPER_DISTILL_BASE_URL"),
    )
    _ = run_parser.add_argument(
        "--api-key",
        default=os.getenv("PAPER_DISTILL_API_KEY"),
    )
    _ = run_parser.add_argument("--timeout-seconds", type=float, default=120.0)
    _ = run_parser.add_argument("--temperature", type=float, default=0.2)
    _ = run_parser.add_argument("--restart", action="store_true")

    export_parser = subparsers.add_parser("export", help="Export distilled QA records.")
    export_selection = export_parser.add_mutually_exclusive_group(required=True)
    _ = export_selection.add_argument("--artifact-dir", default=None)
    _ = export_selection.add_argument("--artifacts-root", default=None)
    _ = export_parser.add_argument("--format", choices=["json", "jsonl", "conversation-jsonl"], required=True)
    _ = export_parser.add_argument("--output", required=True)

    args = parser.parse_args(list(argv) if argv is not None else None)
    command = getattr(args, "command", None)
    if command == "run":
        return _run_command(args)
    if command == "export":
        return _export_command(args)
    parser.print_help()
    return 0


def _run_command(args: argparse.Namespace) -> int:
    workspace_root = _workspace_root(getattr(args, "workspace_root", None))
    artifacts_root = _resolve_root(workspace_root, getattr(args, "artifacts_root", None), DEFAULT_ARTIFACTS_ROOT)
    cache_root = _resolve_root(workspace_root, getattr(args, "cache_root", None), DEFAULT_CACHE_ROOT)
    service = build_service()
    backend = BackendConfig(
        kind=str(getattr(args, "backend")),
        model_name=str(getattr(args, "model")),
        base_url=_optional_string(getattr(args, "base_url", None)),
        api_key=_optional_string(getattr(args, "api_key", None)),
        timeout_seconds=float(getattr(args, "timeout_seconds")),
        temperature=float(getattr(args, "temperature")),
    )
    request = RunRequest(
        paper_path=absolute_path(workspace_root / str(getattr(args, "paper")))
        if not Path(str(getattr(args, "paper"))).is_absolute()
        else absolute_path(Path(str(getattr(args, "paper")))),
        artifacts_root=artifacts_root,
        cache_root=cache_root,
        target_count=(
            int(getattr(args, "target_count"))
            if getattr(args, "target_count", None) is not None
            else None
        ),
        batch_size=int(getattr(args, "batch_size")),
        backend=backend,
        auto_target_count=bool(getattr(args, "auto_target_count", False)),
        min_target_count=int(getattr(args, "min_target_count")),
        max_target_count=int(getattr(args, "max_target_count")),
        restart=bool(getattr(args, "restart", False)),
    )
    try:
        result = service.run(request)
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"paper_id={result.paper_id}")
    print(f"artifact_dir={result.artifact_dir}")
    print(f"target_count={result.target_count}")
    print(f"accepted_count={result.accepted_count}")
    print(f"entries_written={result.entries_written}")
    print(f"cache_status={result.cache_status.value}")
    print(f"status={result.run_status.value}")
    return 0


def _export_command(args: argparse.Namespace) -> int:
    artifact_dir_value = _optional_string(getattr(args, "artifact_dir", None))
    artifacts_root_value = _optional_string(getattr(args, "artifacts_root", None))
    exporter_root = (
        absolute_path(Path(artifact_dir_value)).parent
        if artifact_dir_value is not None
        else absolute_path(Path(artifacts_root_value))
        if artifacts_root_value is not None
        else absolute_path(Path.cwd())
    )
    exporter = PaperDistillExporter(PaperArtifactStore(exporter_root))
    request = ExportRequest(
        artifact_dir=absolute_path(Path(artifact_dir_value)) if artifact_dir_value else None,
        artifacts_root=(
            absolute_path(Path(artifacts_root_value))
            if artifacts_root_value
            else None
        ),
        output_path=absolute_path(Path(str(getattr(args, "output")))),
        format=ExportFormat(str(getattr(args, "format"))),
    )
    try:
        result = exporter.export(request)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"output={result.output_path}")
    print(f"format={result.format.value}")
    print(f"record_count={result.record_count}")
    return 0


def _workspace_root(raw_value: object) -> Path:
    if isinstance(raw_value, str) and raw_value.strip():
        return absolute_path(Path(raw_value))
    env_root = os.getenv("AGENT_WORKSPACE_ROOT")
    if env_root:
        return absolute_path(Path(env_root))
    return absolute_path(Path.cwd())


def _resolve_root(workspace_root: Path, raw_value: object, default_relative: Path) -> Path:
    if isinstance(raw_value, str) and raw_value.strip():
        path = Path(raw_value)
        if path.is_absolute():
            return absolute_path(path)
        return absolute_path(workspace_root / path)
    return absolute_path(workspace_root / default_relative)


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
