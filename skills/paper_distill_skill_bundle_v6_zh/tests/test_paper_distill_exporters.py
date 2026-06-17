from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.paper_distill.exporters import PaperDistillExporter
from app.paper_distill.layout import build_paths
from app.paper_distill.models import (
    ConversationPlan,
    ConversationThreadPlan,
    ConversationTurnEntry,
    ExportFormat,
    ExportRequest,
    QaEntry,
)
from app.paper_distill.store import PaperArtifactStore


class PaperDistillExporterTests(unittest.TestCase):
    def test_exports_jsonl_and_json_with_stable_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            artifacts_root = workspace_root / "artifacts"
            store = PaperArtifactStore(artifacts_root)
            exporter = PaperDistillExporter(store)

            first_paths = build_paths(
                artifacts_root=artifacts_root,
                cache_root=workspace_root / "cache",
                paper_id="paper-a",
            )
            second_paths = build_paths(
                artifacts_root=artifacts_root,
                cache_root=workspace_root / "cache",
                paper_id="paper-b",
            )
            store.append_entries(
                first_paths,
                [
                    QaEntry(
                        qa_id="qa_0002",
                        paper_id="paper-a",
                        ordinal=2,
                        question="Q2",
                        answer="A2",
                        evidence_text="E2",
                        evidence_locator="section-2",
                        source_hash="sha256:a",
                        prompt_version="v1",
                        backend_kind="mock",
                        model_name="mock-model",
                    ),
                    QaEntry(
                        qa_id="qa_0001",
                        paper_id="paper-a",
                        ordinal=1,
                        question="Q1",
                        answer="A1",
                        evidence_text="E1",
                        evidence_locator="section-1",
                        source_hash="sha256:a",
                        prompt_version="v1",
                        backend_kind="mock",
                        model_name="mock-model",
                    ),
                ],
            )
            store.append_entries(
                second_paths,
                [
                    QaEntry(
                        qa_id="qa_0001",
                        paper_id="paper-b",
                        ordinal=1,
                        question="QB1",
                        answer="AB1",
                        evidence_text="EB1",
                        evidence_locator="section-1",
                        source_hash="sha256:b",
                        prompt_version="v1",
                        backend_kind="mock",
                        model_name="mock-model",
                    )
                ],
            )

            jsonl_output = workspace_root / "export.jsonl"
            json_output = workspace_root / "export.json"
            jsonl_result = exporter.export(
                ExportRequest(
                    artifacts_root=artifacts_root,
                    output_path=jsonl_output,
                    format=ExportFormat.JSONL,
                )
            )
            json_result = exporter.export(
                ExportRequest(
                    artifacts_root=artifacts_root,
                    output_path=json_output,
                    format=ExportFormat.JSON,
                )
            )

            jsonl_rows = [
                json.loads(line)
                for line in jsonl_output.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            json_payload = json.loads(json_output.read_text(encoding="utf-8"))

            self.assertEqual(jsonl_result.record_count, 3)
            self.assertEqual(json_result.record_count, 3)
            self.assertEqual([row["qa_id"] for row in jsonl_rows], ["qa_0001", "qa_0002", "qa_0001"])
            self.assertEqual(json_payload["record_count"], 3)
            self.assertEqual(json_payload["records"][0]["paper_id"], "paper-a")

    def test_exports_conversation_jsonl_grouped_by_paper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            artifacts_root = workspace_root / "artifacts"
            store = PaperArtifactStore(artifacts_root)
            exporter = PaperDistillExporter(store)

            first_paths = build_paths(
                artifacts_root=artifacts_root,
                cache_root=workspace_root / "cache",
                paper_id="paper-a",
            )
            second_paths = build_paths(
                artifacts_root=artifacts_root,
                cache_root=workspace_root / "cache",
                paper_id="paper-b",
            )
            store.append_entries(
                first_paths,
                [
                    QaEntry(
                        qa_id="qa_0001",
                        paper_id="paper-a",
                        ordinal=1,
                        question="Q1",
                        answer="A1",
                        evidence_text="E1",
                        evidence_locator="section-1",
                        source_hash="sha256:a",
                        prompt_version="v1",
                        backend_kind="mock",
                        model_name="mock-model",
                    ),
                    QaEntry(
                        qa_id="qa_0002",
                        paper_id="paper-a",
                        ordinal=2,
                        question="Q2",
                        answer="A2",
                        evidence_text="E2",
                        evidence_locator="section-2",
                        source_hash="sha256:a",
                        prompt_version="v1",
                        backend_kind="mock",
                        model_name="mock-model",
                    ),
                ],
            )
            store.append_entries(
                second_paths,
                [
                    QaEntry(
                        qa_id="qa_0001",
                        paper_id="paper-b",
                        ordinal=1,
                        question="QB1",
                        answer="AB1",
                        evidence_text="EB1",
                        evidence_locator="section-1",
                        source_hash="sha256:b",
                        prompt_version="v1",
                        backend_kind="mock",
                        model_name="mock-model",
                    )
                ],
            )

            output_path = workspace_root / "conversation.jsonl"
            result = exporter.export(
                ExportRequest(
                    artifacts_root=artifacts_root,
                    output_path=output_path,
                    format=ExportFormat.CONVERSATION_JSONL,
                )
            )

            rows = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            self.assertEqual(result.record_count, 2)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["record_type"], "conversation")
            self.assertEqual(rows[0]["paper_id"], "paper-a")
            self.assertEqual(rows[0]["turn_count"], 2)
            self.assertEqual(
                rows[0]["messages"],
                [
                    {"role": "user", "content": "Q1"},
                    {"role": "assistant", "content": "A1"},
                    {"role": "user", "content": "Q2"},
                    {"role": "assistant", "content": "A2"},
                ],
            )
            self.assertEqual(rows[1]["paper_id"], "paper-b")
            self.assertEqual(rows[1]["turn_count"], 1)

    def test_exports_conversation_jsonl_from_conversation_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            artifacts_root = workspace_root / "artifacts"
            store = PaperArtifactStore(artifacts_root)
            exporter = PaperDistillExporter(store)

            paths = build_paths(
                artifacts_root=artifacts_root,
                cache_root=workspace_root / "cache",
                paper_id="paper-a",
            )
            store.save_conversation_plan(
                paths,
                ConversationPlan(
                    paper_id="paper-a",
                    paper_title="Paper A",
                    source_hash="sha256:a",
                    conversation_plan_version="cp-v1",
                    target_turn_count=3,
                    threads=(
                        ConversationThreadPlan(
                            thread_id="thread-01",
                            topic="Study goal and design",
                            rationale="Set up context",
                            turn_budget=2,
                            must_cover=("goal", "design"),
                            start_context="Thread 1 context",
                        ),
                        ConversationThreadPlan(
                            thread_id="thread-02",
                            topic="Results",
                            rationale="Cover results",
                            turn_budget=1,
                            must_cover=("result",),
                            start_context="Thread 2 context",
                        ),
                    ),
                ),
            )
            store.append_conversation_entries(
                paths,
                [
                    ConversationTurnEntry(
                        turn_id="turn_0001",
                        conversation_id="paper-a--thread-01",
                        paper_id="paper-a",
                        thread_id="thread-01",
                        thread_topic="Study goal and design",
                        ordinal=1,
                        thread_turn_index=1,
                        question="Q1",
                        answer="A1",
                        evidence_text="E1",
                        evidence_locator="section-1",
                        source_hash="sha256:a",
                        prompt_version="v2",
                        backend_kind="mock",
                        model_name="mock-model",
                    ),
                    ConversationTurnEntry(
                        turn_id="turn_0002",
                        conversation_id="paper-a--thread-01",
                        paper_id="paper-a",
                        thread_id="thread-01",
                        thread_topic="Study goal and design",
                        ordinal=2,
                        thread_turn_index=2,
                        question="Q2",
                        answer="A2",
                        evidence_text="E2",
                        evidence_locator="section-2",
                        source_hash="sha256:a",
                        prompt_version="v2",
                        backend_kind="mock",
                        model_name="mock-model",
                    ),
                    ConversationTurnEntry(
                        turn_id="turn_0003",
                        conversation_id="paper-a--thread-02",
                        paper_id="paper-a",
                        thread_id="thread-02",
                        thread_topic="Results",
                        ordinal=3,
                        thread_turn_index=1,
                        question="Q3",
                        answer="A3",
                        evidence_text="E3",
                        evidence_locator="section-3",
                        source_hash="sha256:a",
                        prompt_version="v2",
                        backend_kind="mock",
                        model_name="mock-model",
                    ),
                ],
            )

            output_path = workspace_root / "conversation-v2.jsonl"
            result = exporter.export(
                ExportRequest(
                    artifacts_root=artifacts_root,
                    output_path=output_path,
                    format=ExportFormat.CONVERSATION_JSONL,
                )
            )

            rows = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            self.assertEqual(result.record_count, 2)
            self.assertEqual(rows[0]["schema"], "paper_distill_conversation/v2")
            self.assertEqual(rows[0]["thread_id"], "thread-01")
            self.assertEqual(rows[0]["planned_turn_budget"], 2)
            self.assertEqual(rows[0]["turn_count"], 2)
            self.assertEqual(rows[1]["thread_id"], "thread-02")
            self.assertEqual(rows[1]["turn_count"], 1)

    def test_export_rejects_missing_artifact_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            exporter = PaperDistillExporter(PaperArtifactStore(workspace_root / "artifacts"))

            with self.assertRaisesRegex(ValueError, "does not exist"):
                _ = exporter.export(
                    ExportRequest(
                        artifacts_root=workspace_root / "missing-root",
                        output_path=workspace_root / "export.jsonl",
                        format=ExportFormat.JSONL,
                    )
                )


if __name__ == "__main__":
    _ = unittest.main()
