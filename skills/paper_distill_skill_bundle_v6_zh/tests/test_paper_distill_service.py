from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.paper_distill.models import BackendConfig, CacheStatus, KnowledgeMap, PreparedPrefix, RunRequest
from app.paper_distill.service import (
    _answer_is_undercontextualized,
    _has_vague_quantitative_placeholder,
    _has_unresolved_reference,
    _infer_source_language,
    _looks_near_duplicate_question,
    _normalize_knowledge_map_payload,
    _question_lacks_explicit_anchor,
    _question_requests_unsupported_conditions,
    _reuses_evidence_cluster,
    build_service,
    estimate_target_count,
)


SAMPLE_PAPER = """# Sample Distillation Paper

## Background

This paper introduces a concise background section.

## Method

The method focuses on a deterministic testing workflow.

## Results

The results emphasize repeatable local execution.
"""


class PaperDistillServiceTests(unittest.TestCase):
    def _sample_knowledge_map(self) -> KnowledgeMap:
        return KnowledgeMap(
            paper_id="paper-zh",
            paper_title="中文论文",
            source_hash="sha256:test",
            knowledge_map_version="km-v1",
            content_profile="body_available",
            primary_language="zh",
            study_goal="评价0.2%高效氯氰菊酯粉剂对田间红火蚁的防治效果。",
            study_object="田间红火蚁蚁巢及工蚁群体",
            experimental_design="田间单蚁巢处理试验。",
            sections_present=("摘要", "材料与方法", "结果与分析"),
            treatments_or_conditions=("50 g/巢", "100 g/巢", "空白对照"),
            core_metrics=("活蚁巢数量", "工蚁诱集数量", "死亡率"),
            key_findings=("短期内显著下降",),
            limitations=("持效性较差",),
            recommendations=("慎重使用触杀性粉剂",),
        )

    def test_infer_source_language_treats_chinese_papers_with_english_metadata_as_zh(self) -> None:
        source = "\n".join(
            [
                "Journal of Plant Protection DOI:10.13802/example",
                "摘要: 利用0.2%高效氯氰菊酯粉剂对田间红火蚁蚁巢进行单蚁巢处理，分析粉剂施用剂量和次数对红火蚁种群数量及蚁巢迁移的影响。"
                * 12,
                "Solenopsis invicta Buren",
            ]
        )

        inferred = _infer_source_language(source)

        self.assertEqual(inferred, "zh")

    def test_normalize_knowledge_map_prefers_inferred_source_language_when_confident(self) -> None:
        knowledge_map = _normalize_knowledge_map_payload(
            payload={
                "primary_language": "en",
                "study_goal": "研究目标",
                "study_object": "研究对象",
                "experimental_design": "实验设计",
                "key_findings": ["结果1"],
            },
            paper_id="paper-001",
            paper_title="中文论文",
            source_hash="sha256:test",
            source_language="zh",
        )

        self.assertEqual(knowledge_map.primary_language, "zh")

    def test_has_unresolved_reference_rejects_figure_table_shorthand(self) -> None:
        knowledge_map = self._sample_knowledge_map()

        self.assertTrue(
            _has_unresolved_reference(
                question="图1说明了什么？",
                answer="表1显示死亡率升高。",
                knowledge_map=knowledge_map,
            )
        )

    def test_question_lacks_explicit_anchor_rejects_context_dependent_prompt(self) -> None:
        knowledge_map = self._sample_knowledge_map()

        self.assertTrue(
            _question_lacks_explicit_anchor(
                question="为什么它会出现这种恢复趋势？",
                knowledge_map=knowledge_map,
            )
        )
        self.assertFalse(
            _question_lacks_explicit_anchor(
                question="在田间红火蚁单蚁巢处理试验中，0.2%高效氯氰菊酯粉剂为什么只表现出短期压低后又快速恢复的趋势？",
                knowledge_map=knowledge_map,
            )
        )

    def test_question_lacks_explicit_anchor_rejects_meta_study_opening(self) -> None:
        knowledge_map = self._sample_knowledge_map()

        self.assertTrue(
            _question_lacks_explicit_anchor(
                question="这项田间红火蚁单蚁巢处理试验有哪些主要局限？",
                knowledge_map=knowledge_map,
            )
        )
        self.assertFalse(
            _question_lacks_explicit_anchor(
                question="田间红火蚁单蚁巢处理试验有哪些主要局限？",
                knowledge_map=knowledge_map,
            )
        )

    def test_answer_is_undercontextualized_for_complex_question(self) -> None:
        knowledge_map = self._sample_knowledge_map()

        self.assertTrue(
            _answer_is_undercontextualized(
                question="50 g/巢和100 g/巢处理后1 d分别下降多少？随后恢复趋势和含义如何？",
                answer="下降了，随后又恢复。",
                knowledge_map=knowledge_map,
            )
        )
        self.assertTrue(
            _answer_is_undercontextualized(
                question="在田间红火蚁单蚁巢处理试验中，0.2%高效氯氰菊酯粉剂为什么只表现出短期压低后又快速恢复的趋势？",
                answer=(
                    "这说明它只有短期抑制作用。"
                    "50 g/巢和100 g/巢处理后1 d相关指标下降，但5~9 d后又恢复到处理前水平。"
                ),
                knowledge_map=knowledge_map,
            )
        )
        self.assertFalse(
            _answer_is_undercontextualized(
                question="50 g/巢和100 g/巢处理后1 d分别下降多少？随后恢复趋势和含义如何？",
                answer=(
                    "在田间红火蚁单蚁巢处理试验中，50 g/巢和100 g/巢处理后1 d，"
                    "活蚁巢数量分别下降55.17%和66.04%，工蚁诱集数量分别下降31.79%和51.95%。"
                    "但5~9 d后相关指标基本恢复到处理前水平，说明这种粉剂只有短期抑制作用，持效性较差。"
                ),
                knowledge_map=knowledge_map,
            )
        )

    def test_answer_is_undercontextualized_rejects_meta_study_opening(self) -> None:
        knowledge_map = self._sample_knowledge_map()

        self.assertTrue(
            _answer_is_undercontextualized(
                question="田间红火蚁单蚁巢处理试验有哪些主要局限？",
                answer=(
                    "这项田间红火蚁单蚁巢处理试验的局限主要在于持效性较差，"
                    "而且结果更适合解释短期抑制，不足以支持长期防效判断。"
                ),
                knowledge_map=knowledge_map,
            )
        )
        self.assertFalse(
            _answer_is_undercontextualized(
                question="田间红火蚁单蚁巢处理试验有哪些主要局限？",
                answer=(
                    "田间红火蚁单蚁巢处理试验的局限主要在于持效性较差，"
                    "相关指标在短期下降后又快速恢复，因此这类粉剂更适合解释短期抑制，"
                    "不足以支持长期防效判断。"
                    "如果要评估长期控制价值，还需要结合更长观察期和后续种群恢复情况进一步验证。"
                ),
                knowledge_map=knowledge_map,
            )
        )

    def test_looks_near_duplicate_question_rejects_minor_rephrasing(self) -> None:
        self.assertTrue(
            _looks_near_duplicate_question(
                question="在田间单蚁巢试验中，50 g/巢和100 g/巢施药后为什么说它只是短期压低，5—21 d恢复趋势怎样，21 d时蚁巢增加率分别是多少？",
                existing_questions=(
                    "在田间单蚁巢试验中，50 g/巢和100 g/巢施用后，为什么说它的防效主要是短期压低，这种恢复趋势在5—21 d内表现得怎样，21 d时蚁巢增加率分别是多少？",
                ),
            )
        )
        self.assertFalse(
            _looks_near_duplicate_question(
                question="在100 g/巢重复施药试验中，1次、2次和3次施药后1 d的抑制差异分别是多少？",
                existing_questions=(
                    "在田间单蚁巢试验中，50 g/巢和100 g/巢施用后，为什么说它的防效主要是短期压低，这种恢复趋势在5—21 d内表现得怎样？",
                ),
            )
        )

    def test_has_vague_quantitative_placeholder_rejects_missing_explicit_values(self) -> None:
        self.assertTrue(
            _has_vague_quantitative_placeholder(
                question="在50、100和200 g/巢处理后，活蚁巢数量和工蚁诱集数量分别下降了多少？",
                answer=(
                    "在田间红火蚁单蚁巢处理中，50 g/巢和100 g/巢处理后活蚁巢数量分别下降55.17%和66.04%，"
                    "200 g/巢表现为更高剂量下进一步压低；工蚁诱集数量也显示更强的短期抑制。"
                ),
            )
        )
        self.assertFalse(
            _has_vague_quantitative_placeholder(
                question="在50 g/巢、100 g/巢和200 g/巢处理后，活蚁巢数量和工蚁诱集数量分别下降了多少？",
                answer=(
                    "50 g/巢、100 g/巢和200 g/巢处理后，活蚁巢数量分别下降55.17%、66.04%和70.00%，"
                    "工蚁诱集数量分别下降31.79%、51.95%和60.00%。"
                ),
            )
        )

    def test_question_requests_unsupported_conditions_rejects_partial_evidence(self) -> None:
        self.assertTrue(
            _question_requests_unsupported_conditions(
                question="在50、100和200 g/巢处理后，活蚁巢数量和工蚁诱集数量分别下降了多少？",
                evidence_text="50 g/巢和100 g/巢处理1 d后，活蚁巢数量降幅分别达55.17%和66.04%，工蚁诱集数量降幅分别达31.79%和51.95%。",
            )
        )
        self.assertFalse(
            _question_requests_unsupported_conditions(
                question="在50、100和200 g/巢处理后，活蚁巢数量和工蚁诱集数量分别下降了多少？",
                evidence_text="50、100和200 g/巢处理1 d后，活蚁巢数量分别下降55.17%、66.04%和70.00%，工蚁诱集数量分别下降31.79%、51.95%和60.00%。",
            )
        )

    def test_reuses_evidence_cluster_rejects_same_result_series_rephrasing(self) -> None:
        self.assertTrue(
            _reuses_evidence_cluster(
                question="除了看蚁巢和工蚁数量变化，还需要关注红火蚁在受0.2%高效氯氰菊酯粉剂后如何进行空间重组。就田间单蚁巢处理结果看，50、100和200 g/巢处理下，处理蚁巢死亡率、蚁巢增加率和分巢率各自随剂量增加呈现什么趋势？",
                evidence_text="在50、100和200 g/巢粉剂处理区内，处理蚁巢死亡率分别为40.00%、50.00%和100.00%，蚁巢增加率分别为100.00%、83.33%和42.86%，分巢率分别为80.00%、66.67%和42.86%。",
                evidence_locator="结果与分析 2.3.1；表1",
                existing_thread_turns=(
                    {
                        "question": "在田间红火蚁单蚁巢受0.2%高效氯氰菊酯粉剂处理后，随着施药剂量从50 g/巢增加到200 g/巢，处理蚁巢死亡率、蚁巢增加率和分巢率分别呈现什么变化？",
                        "answer": "剂量升高时死亡率升高而蚁巢增加率和分巢率下降。",
                        "evidence_text": "在50、100和200 g/巢粉剂处理区内，处理蚁巢死亡率分别为40.00%、50.00%和100.00%，蚁巢增加率分别为100.00%、83.33%和42.86%，分巢率分别为80.00%、66.67%和42.86%。",
                        "evidence_locator": "结果与分析 2.3.1；表1",
                    },
                ),
            )
        )
        self.assertFalse(
            _reuses_evidence_cluster(
                question="在田间红火蚁单蚁巢受0.2%高效氯氰菊酯粉剂处理后，新蚁巢通常会在原处理蚁巢多远的范围内出现，这种空间迁移更像近距离重建还是远距离扩散？",
                evidence_text="新蚁巢的迁移距离十分有限，一般会出现在原处理蚁巢的0.26~2.23 m范围内。",
                evidence_locator="讨论；表1",
                existing_thread_turns=(
                    {
                        "question": "在田间红火蚁单蚁巢受0.2%高效氯氰菊酯粉剂处理后，随着施药剂量从50 g/巢增加到200 g/巢，处理蚁巢死亡率、蚁巢增加率和分巢率分别呈现什么变化？",
                        "answer": "剂量升高时死亡率升高而蚁巢增加率和分巢率下降。",
                        "evidence_text": "在50、100和200 g/巢粉剂处理区内，处理蚁巢死亡率分别为40.00%、50.00%和100.00%，蚁巢增加率分别为100.00%、83.33%和42.86%，分巢率分别为80.00%、66.67%和42.86%。",
                        "evidence_locator": "结果与分析 2.3.1；表1",
                    },
                ),
            )
        )

    def test_estimate_target_count_grows_with_source_size_and_structure(self) -> None:
        short_source = "# Short\n\nA concise abstract-like note.\n"
        long_source = "\n".join(
            [
                "# Long Study",
                "## Background",
                ("Background detail. " * 40).strip(),
                "## Methods",
                ("Methods detail with measurements and tables. " * 60).strip(),
                "## Results",
                ("Results detail with Table 1, Table 2, Fig. 1, and Fig. 2. " * 80).strip(),
                "## Discussion",
                ("Discussion detail with interpretation and limitations. " * 50).strip(),
            ]
        )

        short_count = estimate_target_count(normalized_source=short_source)
        long_count = estimate_target_count(normalized_source=long_source)

        self.assertGreaterEqual(short_count, 6)
        self.assertGreater(long_count, short_count)

    def test_estimate_target_count_caps_abstract_only_sources(self) -> None:
        abstract_only_source = "\n".join(
            [
                "# Abstract-only Paper",
                "摘要: " + ("This abstract repeats the core finding and comparison. " * 160).strip(),
                "Abstract: " + ("This abstract repeats the core finding and comparison. " * 160).strip(),
            ]
        )

        estimated = estimate_target_count(normalized_source=abstract_only_source)

        self.assertLessEqual(estimated, 10)

    def test_estimate_target_count_uses_density_cap_with_knowledge_map(self) -> None:
        dense_source = "结果数据与讨论。" * 4000
        knowledge_map = KnowledgeMap(
            paper_id="paper-001",
            paper_title="长论文",
            source_hash="sha256:test",
            knowledge_map_version="km-v1",
            content_profile="body_available",
            primary_language="zh",
            study_goal="评价多种处理对目标害虫的影响。",
            study_object="目标害虫",
            experimental_design="田间试验设计",
            sections_present=("摘要", "材料与方法", "结果与分析", "讨论"),
            treatments_or_conditions=("处理1", "处理2", "处理3", "处理4", "处理5", "处理6"),
            core_metrics=("指标1", "指标2", "指标3", "指标4", "指标5", "指标6"),
            key_findings=("发现1", "发现2", "发现3", "发现4", "发现5", "发现6", "发现7"),
            limitations=("局限1", "局限2", "局限3"),
            recommendations=("建议1", "建议2", "建议3"),
        )

        estimated = estimate_target_count(normalized_source=dense_source, knowledge_map=knowledge_map)

        self.assertLessEqual(estimated, 17)

    def test_run_resume_and_restart_with_mock_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            paper_path = workspace_root / "paper.md"
            _ = paper_path.write_text(SAMPLE_PAPER, encoding="utf-8")
            artifacts_root = workspace_root / "artifacts"
            cache_root = workspace_root / "cache"
            service = build_service()
            backend = BackendConfig(kind="mock", model_name="mock-model")

            first = service.run(
                RunRequest(
                    paper_path=paper_path,
                    artifacts_root=artifacts_root,
                    cache_root=cache_root,
                    target_count=2,
                    batch_size=1,
                    backend=backend,
                )
            )
            second = service.run(
                RunRequest(
                    paper_path=paper_path,
                    artifacts_root=artifacts_root,
                    cache_root=cache_root,
                    target_count=4,
                    batch_size=2,
                    backend=backend,
                )
            )
            restarted = service.run(
                RunRequest(
                    paper_path=paper_path,
                    artifacts_root=artifacts_root,
                    cache_root=cache_root,
                    target_count=1,
                    batch_size=1,
                    backend=backend,
                    restart=True,
                )
            )

            self.assertEqual(first.accepted_count, 2)
            self.assertEqual(first.entries_written, 2)
            self.assertEqual(first.cache_status.value, "created")
            self.assertEqual(second.accepted_count, 4)
            self.assertEqual(second.entries_written, 2)
            self.assertEqual(second.cache_status.value, "reused")
            self.assertEqual(restarted.accepted_count, 1)

            ledger_path = restarted.artifact_dir / "qa_entries.jsonl"
            rows = [
                json.loads(line)
                for line in ledger_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["qa_id"], "qa_0001")

    def test_run_uses_auto_target_count_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            paper_path = workspace_root / "paper.md"
            _ = paper_path.write_text(SAMPLE_PAPER, encoding="utf-8")
            artifacts_root = workspace_root / "artifacts"
            cache_root = workspace_root / "cache"
            service = build_service()
            backend = BackendConfig(kind="mock", model_name="mock-model")

            result = service.run(
                RunRequest(
                    paper_path=paper_path,
                    artifacts_root=artifacts_root,
                    cache_root=cache_root,
                    target_count=None,
                    batch_size=2,
                    backend=backend,
                    auto_target_count=True,
                    min_target_count=5,
                    max_target_count=7,
                )
            )

            self.assertEqual(result.target_count, 7)
            self.assertEqual(result.accepted_count, 7)

    def test_run_persists_knowledge_map(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            paper_path = workspace_root / "paper.md"
            _ = paper_path.write_text(SAMPLE_PAPER, encoding="utf-8")
            artifacts_root = workspace_root / "artifacts"
            cache_root = workspace_root / "cache"
            service = build_service()
            backend = BackendConfig(kind="mock", model_name="mock-model")

            result = service.run(
                RunRequest(
                    paper_path=paper_path,
                    artifacts_root=artifacts_root,
                    cache_root=cache_root,
                    target_count=2,
                    batch_size=1,
                    backend=backend,
                )
            )

            knowledge_map_path = result.artifact_dir / "knowledge_map.json"
            payload = json.loads(knowledge_map_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["paper_id"], result.paper_id)
            self.assertIn("study_goal", payload)
            self.assertIn("key_findings", payload)

    def test_run_completes_early_when_generation_saturates(self) -> None:
        class SaturatingBackend:
            def __init__(self) -> None:
                self.call_count = 0

            def prepare_prefix(self, **_: object) -> PreparedPrefix:
                return PreparedPrefix(
                    cache_key="cache-key",
                    prefix_hash="prefix-hash",
                    backend_kind="mock",
                    backend_ref="fake-backend",
                    cache_status=CacheStatus.CREATED,
                )

            def generate_json_object(self, **_: object) -> dict[str, object]:
                self.call_count += 1
                if self.call_count == 1:
                    return {
                        "content_profile": "body_available",
                        "primary_language": "zh",
                        "study_goal": "说明试验设计与结果。",
                        "study_object": "田间红火蚁蚁巢及工蚁群体",
                        "experimental_design": "田间单蚁巢处理试验。",
                        "sections_present": ["摘要", "结果与分析", "讨论"],
                        "treatments_or_conditions": ["50 g/巢", "100 g/巢", "空白对照"],
                        "core_metrics": ["活蚁巢数量", "工蚁诱集数量"],
                        "key_findings": ["1 d内下降", "随后恢复"],
                        "limitations": ["持效性差"],
                        "recommendations": ["慎重使用"],
                    }
                if self.call_count == 2:
                    return {
                        "threads": [
                            {
                                "topic": "核心结果",
                                "rationale": "覆盖主要方法和结果。",
                                "turn_budget": 4,
                                "must_cover": ["处理设置", "1 d结果", "恢复趋势"],
                                "start_context": "先说明试验设置，再概括主要结果和恢复趋势。",
                            }
                        ]
                    }
                if self.call_count == 3:
                    return {
                        "items": [
                            {
                                "question": "在这项田间红火蚁单蚁巢处理试验中，0.2%高效氯氰菊酯粉剂设置了哪些处理，并主要监测哪些指标？",
                                "answer": "在这项田间红火蚁单蚁巢处理试验中，研究设置了50 g/巢和100 g/巢处理，并配有空白对照，主要监测活蚁巢数量和工蚁诱集数量。这种设计既能比较药剂的短期压制效果，也能为后续恢复趋势判断提供基础。",
                                "evidence_text": "设置50 g/巢、100 g/巢处理和空白对照，记录活蚁巢数量与工蚁诱集数量。",
                                "evidence_locator": "材料与方法",
                            }
                        ]
                    }
                if self.call_count == 4:
                    return {
                        "items": [
                            {
                                "question": "在这项田间红火蚁单蚁巢处理试验中，0.2%高效氯氰菊酯粉剂施药后1 d和随后几天的种群变化说明了什么？",
                                "answer": "在这项田间红火蚁单蚁巢处理试验中，0.2%高效氯氰菊酯粉剂在施药后1 d能明显压低活蚁巢数量和工蚁诱集数量，但随后几天相关指标又逐步恢复。这说明该粉剂的效果主要停留在短期压制阶段，持效性较差，不能提供稳定控制。",
                                "evidence_text": "施药后1 d明显下降，随后逐步恢复。",
                                "evidence_locator": "结果与分析",
                            }
                        ]
                    }
                return {
                    "items": [
                        {
                            "question": "在这项田间红火蚁单蚁巢处理试验中，0.2%高效氯氰菊酯粉剂施药后1 d和随后几天的种群变化说明了什么？",
                            "answer": "在这项田间红火蚁单蚁巢处理试验中，0.2%高效氯氰菊酯粉剂在施药后1 d能明显压低活蚁巢数量和工蚁诱集数量，但随后几天相关指标又逐步恢复。这说明该粉剂的效果主要停留在短期压制阶段，持效性较差，不能提供稳定控制。",
                            "evidence_text": "施药后1 d明显下降，随后逐步恢复。",
                            "evidence_locator": "结果与分析",
                        }
                    ]
                }

        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            paper_path = workspace_root / "paper.md"
            _ = paper_path.write_text(SAMPLE_PAPER, encoding="utf-8")
            artifacts_root = workspace_root / "artifacts"
            cache_root = workspace_root / "cache"
            service = build_service()
            backend = BackendConfig(
                kind="mock",
                model_name="fake-model",
            )

            with patch("app.paper_distill.service.build_backend", return_value=SaturatingBackend()):
                result = service.run(
                    RunRequest(
                        paper_path=paper_path,
                        artifacts_root=artifacts_root,
                        cache_root=cache_root,
                        target_count=4,
                        batch_size=1,
                        backend=backend,
                    )
                )

            self.assertEqual(result.accepted_count, 2)
            self.assertEqual(result.target_count, 2)

    def test_run_persists_conversation_plan_and_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            paper_path = workspace_root / "paper.md"
            _ = paper_path.write_text(SAMPLE_PAPER, encoding="utf-8")
            artifacts_root = workspace_root / "artifacts"
            cache_root = workspace_root / "cache"
            service = build_service()
            backend = BackendConfig(kind="mock", model_name="mock-model")

            result = service.run(
                RunRequest(
                    paper_path=paper_path,
                    artifacts_root=artifacts_root,
                    cache_root=cache_root,
                    target_count=4,
                    batch_size=2,
                    backend=backend,
                )
            )

            conversation_plan_path = result.artifact_dir / "conversation_plan.json"
            conversation_entries_path = result.artifact_dir / "conversation_entries.jsonl"
            plan_payload = json.loads(conversation_plan_path.read_text(encoding="utf-8"))
            conversation_rows = [
                json.loads(line)
                for line in conversation_entries_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            self.assertEqual(plan_payload["paper_id"], result.paper_id)
            self.assertIn("threads", plan_payload)
            self.assertEqual(len(conversation_rows), 4)
            self.assertIn("thread_id", conversation_rows[0])
            self.assertIn("thread_topic", conversation_rows[0])

    def test_prefix_hash_mismatch_requires_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory)
            paper_path = workspace_root / "paper.md"
            _ = paper_path.write_text(SAMPLE_PAPER, encoding="utf-8")
            artifacts_root = workspace_root / "artifacts"
            cache_root = workspace_root / "cache"
            service = build_service()
            backend = BackendConfig(kind="mock", model_name="mock-model")

            _ = service.run(
                RunRequest(
                    paper_path=paper_path,
                    artifacts_root=artifacts_root,
                    cache_root=cache_root,
                    target_count=2,
                    batch_size=1,
                    backend=backend,
                )
            )

            with patch(
                "app.paper_distill.service.build_stable_prefix",
                side_effect=lambda *, title, normalized_source: f"MUTATED\n{normalized_source}",
            ):
                with self.assertRaisesRegex(ValueError, "Use --restart"):
                    _ = service.run(
                        RunRequest(
                            paper_path=paper_path,
                            artifacts_root=artifacts_root,
                            cache_root=cache_root,
                            target_count=3,
                            batch_size=1,
                            backend=backend,
                        )
                    )


if __name__ == "__main__":
    _ = unittest.main()
