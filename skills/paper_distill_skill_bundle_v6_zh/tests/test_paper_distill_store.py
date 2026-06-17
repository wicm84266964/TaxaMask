from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.paper_distill.layout import build_paths
from app.paper_distill.models import (
    Checkpoint,
    ConversationPlan,
    ConversationThreadPlan,
    ConversationTurnEntry,
    KnowledgeMap,
    QaEntry,
    RunStatus,
)
from app.paper_distill.store import PaperArtifactStore


class PaperArtifactStoreTests(unittest.TestCase):
    def test_appends_entries_and_persists_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            store = PaperArtifactStore(root / "artifacts")
            paths = build_paths(
                artifacts_root=root / "artifacts",
                cache_root=root / "cache",
                paper_id="paper-1",
            )
            entries = [
                QaEntry(
                    qa_id="qa_0001",
                    paper_id="paper-1",
                    ordinal=1,
                    question="Q1",
                    answer="A1",
                    evidence_text="E1",
                    evidence_locator="section-1",
                    source_hash="sha256:abc",
                    prompt_version="v1",
                    backend_kind="mock",
                    model_name="mock-model",
                ),
                QaEntry(
                    qa_id="qa_0002",
                    paper_id="paper-1",
                    ordinal=2,
                    question="Q2",
                    answer="A2",
                    evidence_text="E2",
                    evidence_locator="section-2",
                    source_hash="sha256:abc",
                    prompt_version="v1",
                    backend_kind="mock",
                    model_name="mock-model",
                ),
            ]
            checkpoint = Checkpoint(
                paper_id="paper-1",
                paper_title="Paper 1",
                paper_path=str(root / "paper.md"),
                source_hash="sha256:abc",
                cache_key="cache-1",
                prefix_hash="prefix-1",
                backend_kind="mock",
                backend_ref="mock:cache-1",
                model_name="mock-model",
                prompt_version="v1",
                target_count=2,
                batch_size=1,
                accepted_count=2,
                next_ordinal=3,
                status=RunStatus.COMPLETED,
            )
            knowledge_map = KnowledgeMap(
                paper_id="paper-1",
                paper_title="Paper 1",
                source_hash="sha256:abc",
                knowledge_map_version="km-v1",
                content_profile="body_available",
                primary_language="en",
                study_goal="Study the treatment effect.",
                study_object="Worker ants",
                experimental_design="Field treatment experiment.",
                sections_present=("Background", "Method", "Results"),
                treatments_or_conditions=("50 g/mound", "100 g/mound"),
                core_metrics=("mound density", "mortality"),
                key_findings=("Finding 1", "Finding 2"),
                limitations=("Short persistence",),
                recommendations=("Use only for emergency control",),
            )
            conversation_plan = ConversationPlan(
                paper_id="paper-1",
                paper_title="Paper 1",
                source_hash="sha256:abc",
                conversation_plan_version="cp-v1",
                target_turn_count=2,
                threads=(
                    ConversationThreadPlan(
                        thread_id="thread-01",
                        topic="Study goal and design",
                        rationale="Set up the context.",
                        turn_budget=2,
                        must_cover=("goal", "design"),
                        start_context="This thread introduces the study context.",
                    ),
                ),
            )
            conversation_entries = [
                ConversationTurnEntry(
                    turn_id="turn_0001",
                    conversation_id="paper-1--thread-01",
                    paper_id="paper-1",
                    thread_id="thread-01",
                    thread_topic="Study goal and design",
                    ordinal=1,
                    thread_turn_index=1,
                    question="Q1",
                    answer="A1",
                    evidence_text="E1",
                    evidence_locator="section-1",
                    source_hash="sha256:abc",
                    prompt_version="v1",
                    backend_kind="mock",
                    model_name="mock-model",
                ),
                ConversationTurnEntry(
                    turn_id="turn_0002",
                    conversation_id="paper-1--thread-01",
                    paper_id="paper-1",
                    thread_id="thread-01",
                    thread_topic="Study goal and design",
                    ordinal=2,
                    thread_turn_index=2,
                    question="Q2",
                    answer="A2",
                    evidence_text="E2",
                    evidence_locator="section-2",
                    source_hash="sha256:abc",
                    prompt_version="v1",
                    backend_kind="mock",
                    model_name="mock-model",
                ),
            ]

            store.append_entries(paths, entries)
            store.append_conversation_entries(paths, conversation_entries)
            store.save_checkpoint(paths, checkpoint)
            store.save_knowledge_map(paths, knowledge_map)
            store.save_conversation_plan(paths, conversation_plan)

            loaded_entries = store.load_entries(paths)
            loaded_conversation_entries = store.load_conversation_entries(paths)
            loaded_checkpoint = store.load_checkpoint(paths)
            loaded_knowledge_map = store.load_knowledge_map(paths)
            loaded_conversation_plan = store.load_conversation_plan(paths)

            self.assertEqual([entry.qa_id for entry in loaded_entries], ["qa_0001", "qa_0002"])
            self.assertEqual([entry.turn_id for entry in loaded_conversation_entries], ["turn_0001", "turn_0002"])
            self.assertIsNotNone(loaded_checkpoint)
            if loaded_checkpoint is None:
                self.fail("Checkpoint should exist after save_checkpoint.")
            self.assertEqual(loaded_checkpoint.accepted_count, 2)
            self.assertIsNotNone(loaded_knowledge_map)
            if loaded_knowledge_map is None:
                self.fail("Knowledge map should exist after save_knowledge_map.")
            self.assertEqual(loaded_knowledge_map.study_goal, "Study the treatment effect.")
            self.assertIsNotNone(loaded_conversation_plan)
            if loaded_conversation_plan is None:
                self.fail("Conversation plan should exist after save_conversation_plan.")
            self.assertEqual(loaded_conversation_plan.threads[0].thread_id, "thread-01")

            store.clear_artifact(paths)
            self.assertEqual(store.load_entries(paths), [])
            self.assertEqual(store.load_conversation_entries(paths), [])
            self.assertIsNone(store.load_checkpoint(paths))
            self.assertIsNone(store.load_knowledge_map(paths))
            self.assertIsNone(store.load_conversation_plan(paths))

    def test_jsonl_ledgers_preserve_readable_utf8_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            store = PaperArtifactStore(root / "artifacts")
            paths = build_paths(
                artifacts_root=root / "artifacts",
                cache_root=root / "cache",
                paper_id="paper-zh",
            )
            qa_entry = QaEntry(
                qa_id="qa_0001",
                paper_id="paper-zh",
                ordinal=1,
                question="这篇研究主要想回答什么问题？",
                answer="研究比较不同处理对田间红火蚁的短期抑制效果。",
                evidence_text="摘要：比较不同处理对田间红火蚁的影响。",
                evidence_locator="摘要",
                source_hash="sha256:zh",
                prompt_version="v1",
                backend_kind="mock",
                model_name="mock-model",
            )
            conversation_entry = ConversationTurnEntry(
                turn_id="turn_0001",
                conversation_id="paper-zh--thread-01",
                paper_id="paper-zh",
                thread_id="thread-01",
                thread_topic="研究设计与结果",
                ordinal=1,
                thread_turn_index=1,
                question="这项研究的处理设置是什么？",
                answer="研究设置了不同剂量处理和空白对照。",
                evidence_text="材料与方法：设置不同剂量处理和对照。",
                evidence_locator="材料与方法",
                source_hash="sha256:zh",
                prompt_version="v1",
                backend_kind="mock",
                model_name="mock-model",
            )

            store.append_entries(paths, [qa_entry])
            store.append_conversation_entries(paths, [conversation_entry])

            qa_text = paths.qa_entries_path.read_text(encoding="utf-8")
            conversation_text = paths.conversation_entries_path.read_text(encoding="utf-8")

            self.assertIn("这篇研究主要想回答什么问题？", qa_text)
            self.assertIn("研究设计与结果", conversation_text)
            self.assertNotIn("\\u8fd9", qa_text)
            self.assertNotIn("\\u7814", conversation_text)


if __name__ == "__main__":
    _ = unittest.main()
