from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.paper_distill.cli import main
from app.paper_distill.models import CacheStatus, DistillRunResult, RunRequest, RunStatus


SAMPLE_PAPER = """# CLI Paper

## Overview

This paper is used for CLI validation.

## Findings

The findings remain deterministic under the mock backend.
"""


class PaperDistillCliTests(unittest.TestCase):
    def test_run_command_supports_auto_target_count(self) -> None:
        class _CapturingService:
            def __init__(self) -> None:
                self.request: RunRequest | None = None

            def run(self, request: RunRequest) -> DistillRunResult:
                self.request = request
                return DistillRunResult(
                    paper_id="paper-1",
                    artifact_dir=Path("artifacts"),
                    accepted_count=7,
                    entries_written=7,
                    cache_status=CacheStatus.CREATED,
                    run_status=RunStatus.COMPLETED,
                    target_count=7,
                )

        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            paper_path = workspace_root / "paper.md"
            _ = paper_path.write_text(SAMPLE_PAPER, encoding="utf-8")
            service = _CapturingService()
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                patch("app.paper_distill.cli.build_service", return_value=service),
                patch("sys.stdout", stdout),
                patch("sys.stderr", stderr),
            ):
                exit_code = main(
                    [
                        "run",
                        "--workspace-root",
                        str(workspace_root),
                        "--paper",
                        "paper.md",
                        "--auto-target-count",
                        "--min-target-count",
                        "5",
                        "--max-target-count",
                        "7",
                        "--batch-size",
                        "2",
                        "--backend",
                        "mock",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIsNotNone(service.request)
            self.assertTrue(service.request.auto_target_count)
            self.assertEqual(service.request.min_target_count, 5)
            self.assertEqual(service.request.max_target_count, 7)
            self.assertIn("target_count=7", stdout.getvalue())

    def test_run_command_does_not_resolve_paper_path_in_cli(self) -> None:
        class _CapturingService:
            def __init__(self) -> None:
                self.paper_path: Path | None = None

            def run(self, request: RunRequest) -> DistillRunResult:
                self.paper_path = request.paper_path
                return DistillRunResult(
                    paper_id="paper-1",
                    artifact_dir=Path("artifacts"),
                    accepted_count=1,
                    entries_written=1,
                    cache_status=CacheStatus.CREATED,
                    run_status=RunStatus.COMPLETED,
                )

        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            paper_path = workspace_root / "paper.md"
            _ = paper_path.write_text(SAMPLE_PAPER, encoding="utf-8")
            service = _CapturingService()
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                patch("app.paper_distill.cli.build_service", return_value=service),
                patch("app.paper_distill.cli.Path.resolve", side_effect=AssertionError("Path.resolve should not be used for --paper")),
                patch("sys.stdout", stdout),
                patch("sys.stderr", stderr),
            ):
                exit_code = main(
                    [
                        "run",
                        "--workspace-root",
                        str(workspace_root),
                        "--paper",
                        "paper.md",
                        "--target-count",
                        "1",
                        "--batch-size",
                        "1",
                        "--backend",
                        "mock",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(service.paper_path, paper_path)

    def test_run_and_export_commands_work_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            paper_path = workspace_root / "paper.md"
            _ = paper_path.write_text(SAMPLE_PAPER, encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()

            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                exit_code = main(
                    [
                        "run",
                        "--workspace-root",
                        str(workspace_root),
                        "--paper",
                        "paper.md",
                        "--target-count",
                        "3",
                        "--batch-size",
                        "2",
                        "--backend",
                        "mock",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("status=completed", stdout.getvalue())

            artifacts_root = workspace_root / "data" / "paper_distill" / "papers"
            output_path = workspace_root / "export.jsonl"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                export_code = main(
                    [
                        "export",
                        "--artifacts-root",
                        str(artifacts_root),
                        "--format",
                        "jsonl",
                        "--output",
                        str(output_path),
                    ]
                )

            rows = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(export_code, 0)
            self.assertEqual(len(rows), 3)
            self.assertIn("record_count=3", stdout.getvalue())

    def test_export_missing_root_fails_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            missing_root = workspace_root / "missing-artifacts"
            output_path = workspace_root / "export.jsonl"
            stdout = io.StringIO()
            stderr = io.StringIO()

            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                export_code = main(
                    [
                        "export",
                        "--artifacts-root",
                        str(missing_root),
                        "--format",
                        "jsonl",
                        "--output",
                        str(output_path),
                    ]
                )

            self.assertEqual(export_code, 1)
            self.assertFalse(missing_root.exists())
            self.assertFalse(output_path.exists())
            self.assertIn("does not exist", stderr.getvalue())

    def test_run_rejects_symlinked_paper_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            real_paper_path = workspace_root / "real-paper.md"
            _ = real_paper_path.write_text(SAMPLE_PAPER, encoding="utf-8")
            symlink_path = workspace_root / "paper-link.md"
            try:
                symlink_path.symlink_to(real_paper_path)
            except (NotImplementedError, OSError, PermissionError):
                self.skipTest("Symlink creation is not available in this environment.")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                exit_code = main(
                    [
                        "run",
                        "--workspace-root",
                        str(workspace_root),
                        "--paper",
                        "paper-link.md",
                        "--target-count",
                        "1",
                        "--batch-size",
                        "1",
                        "--backend",
                        "mock",
                    ]
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("symlinked or reparse-point", stderr.getvalue())


if __name__ == "__main__":
    _ = unittest.main()
