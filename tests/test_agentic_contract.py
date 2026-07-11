import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AgenticContractTests(unittest.TestCase):
    def _run_node_contract(self, script):
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for Ant-Code runtime contract tests")
        with tempfile.TemporaryDirectory() as tmp:
            script_path = Path(tmp) / "ant_code_contract_check.mjs"
            script_path.write_text(textwrap.dedent(script), encoding="utf-8")
            result = subprocess.run(
                ["node", str(script_path)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_contract_stage_ids_are_unique(self):
        contract_path = PROJECT_ROOT / "AntSleap" / "config" / "agentic_pipeline_contract.json"
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
        stage_ids = [stage["id"] for stage in payload["stages"]]
        self.assertEqual(len(stage_ids), len(set(stage_ids)))
        self.assertIn("stage_30_candidate_bridge_and_routing", stage_ids)

    def test_pdf_and_figure_profiles_are_agentic_inputs(self):
        contract_path = PROJECT_ROOT / "AntSleap" / "config" / "agentic_pipeline_contract.json"
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
        input_ids = {item["id"] for item in payload["required_inputs"]}
        self.assertIn("screener_config", input_ids)
        self.assertIn("figure_profile", input_ids)
        self.assertIn("part_description_profile", input_ids)
        defaults = {item["id"]: item.get("default", "") for item in payload["required_inputs"]}
        self.assertEqual(
            defaults["figure_profile"],
            "multimodal_configs/蚂蚁分类学图版宽松复核_示例.json",
        )
        self.assertEqual(
            defaults["part_description_profile"],
            "part_description_configs/蚂蚁分类学部位描述抽取_示例.json",
        )

        stages = {stage["id"]: stage for stage in payload["stages"]}
        screening_command = stages["stage_10_literature_screening"]["command"]
        figure_command = stages["stage_20_figure_extraction"]["command"]
        self.assertIn("--config", screening_command)
        self.assertIn("{screener_config}", screening_command)
        self.assertIn("--figure-profile", figure_command)
        self.assertIn("{figure_profile}", figure_command)
        self.assertIn("--part-description-profile", figure_command)
        self.assertIn("{part_description_profile}", figure_command)
        self.assertIn("{db_artifacts_dir}/figure_images", stages["stage_20_figure_extraction"]["outputs"])
        self.assertIn("{db_artifacts_dir}/review_batches", stages["stage_20_figure_extraction"]["outputs"])
        self.assertEqual(stages["stage_20_figure_extraction"]["title"], "Figure extraction and multimodal review")
        self.assertNotIn("triptych evidence", json.dumps(payload, ensure_ascii=False).lower())

    def test_ant_code_source_write_hook_requests_dashboard_approval(self):
        script = textwrap.dedent(
            f"""
            import assert from "node:assert/strict";
            import fs from "node:fs/promises";
            import os from "node:os";
            import path from "node:path";
            import {{ createToolRuntime }} from {json.dumps((PROJECT_ROOT / "vendor" / "ant-code" / "src" / "tools" / "runtime.js").resolve().as_uri())};

            const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "ant-code-source-approval-"));
            await fs.mkdir(path.join(cwd, "AntSleap", "ui"), {{ recursive: true }});
            const target = "AntSleap/ui/example.py";
            const approvals = [];
            const runtime = createToolRuntime({{
              cwd,
              config: {{
                hooks: {{
                  enabled: true,
                  events: {{
                    "tool.before": [
                      {{
                        name: "taxamask-source-readonly",
                        type: "builtin",
                        builtin: "denyTaxaMaskSourceWrites",
                        blocking: true,
                        managed: true,
                        when: {{ tools: ["write_file"] }}
                      }}
                    ]
                  }}
                }}
              }},
              policy: {{ workspace: cwd, approvals: {{ workspaceWrites: true }} }},
              hooksTrusted: true,
              approve: async (request) => {{
                approvals.push(request);
                return true;
              }}
            }});

            const result = await runtime.execute("write_file", {{ path: target, content: "value = 1\\n" }});
            assert.equal(result.ok, true);
            assert.equal(approvals.length, 1);
            assert.equal(approvals[0].toolName, "write_file");
            assert.equal(approvals[0].decision.sensitive, true);
            assert.match(approvals[0].decision.reason, /TaxaMask source development permission/);
            assert.equal(await fs.readFile(path.join(cwd, target), "utf8"), "value = 1\\n");
            """
        )
        self._run_node_contract(script)

    def test_ant_code_truncates_oversized_tool_results_before_model_context(self):
        result_module = (PROJECT_ROOT / "vendor" / "ant-code" / "src" / "tools" / "result.js").resolve().as_uri()
        self._run_node_contract(
            f"""
            import assert from "node:assert/strict";
            import {{ serializeToolResult }} from {json.dumps(result_module)};

            const small = serializeToolResult({{ ok: true, result: {{ value: "ok" }} }});
            assert.equal(small.truncated, false);
            assert.equal(small.omittedBytes, 0);

            const large = serializeToolResult({{ ok: true, result: {{ entries: "x".repeat(600_000) }} }});
            assert.equal(large.truncated, true);
            assert.ok(large.bytes <= 256 * 1024);
            assert.ok(large.originalBytes > large.bytes);
            assert.ok(large.omittedBytes > 0);
            assert.match(large.content, /tool result truncated/);

            const tiny = serializeToolResult({{ ok: true, result: "x".repeat(1000) }}, {{ maxBytes: 24 }});
            assert.equal(tiny.truncated, true);
            assert.ok(tiny.bytes <= 24);
            """
        )

    def test_ant_code_retries_a_gateway_response_without_visible_content(self):
        session_module = (PROJECT_ROOT / "vendor" / "ant-code" / "src" / "core" / "session.js").resolve().as_uri()
        self._run_node_contract(
            f"""
            import assert from "node:assert/strict";
            import {{ analyzeAssistantOutputHealth, summarizeToolCalls }} from {json.dumps(session_module)};

            const empty = analyzeAssistantOutputHealth(
              {{ text: "", content: [], toolCalls: [], stopReason: "stop", raw: {{ textBytes: 0, thinkingBytes: 0 }} }},
              "模型本轮没有返回可展示正文。",
              null
            );
            assert.equal(empty.ok, false);
            assert.equal(empty.mustRetry, true);
            assert.deepEqual(empty.reasons, ["empty_visible_response"]);

            const visible = analyzeAssistantOutputHealth(
              {{ text: "已完成诊断。", content: [{{ type: "text", text: "已完成诊断。" }}], toolCalls: [], stopReason: "stop", raw: {{}} }},
              "已完成诊断。",
              null
            );
            assert.equal(visible.ok, true);

            const visibleReasoningFallback = analyzeAssistantOutputHealth(
              {{ text: "来自兼容网关的可见正文", content: [{{ type: "text", text: "来自兼容网关的可见正文" }}], toolCalls: [], stopReason: "stop", raw: {{ textBytes: 0, thinkingBytes: 120 }} }},
              "来自兼容网关的可见正文",
              {{ text: "", bytes: 120 }}
            );
            assert.equal(visibleReasoningFallback.ok, true);

            const toolSummary = summarizeToolCalls(
              [{{ id: "call-1", name: "list_files", input: {{ path: "." }} }}],
              [{{ content: '{{"ok": true', ok: true, blocked: false, interrupted: false, decision: null, truncated: true }}]
            );
            assert.equal(toolSummary[0].ok, true);
            assert.equal(toolSummary[0].truncated, true);
            """
        )

    def test_generated_agentic_artifacts_gate_downstream_stages(self):
        contract_path = PROJECT_ROOT / "AntSleap" / "config" / "agentic_pipeline_contract.json"
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
        stages = {stage["id"]: stage for stage in payload["stages"]}
        self.assertIn(
            "{output_dir}/core2_orchestrated/routing_decisions.json",
            stages["stage_40_agentic_import_to_project"]["required_artifacts"],
        )
        self.assertIn(
            "{output_dir}/core2_orchestrated/pdf_candidates_raw.json",
            stages["stage_40_agentic_import_to_project"]["required_artifacts"],
        )
        self.assertIn(
            "{output_dir}/project_agentic_import.json",
            stages["stage_50_batch_auto_annotation"]["required_artifacts"],
        )
        self.assertIn(
            "{output_dir}/project_agentic_import.json",
            stages["stage_60_multimodal_dataset_export"]["required_artifacts"],
        )

    def test_dry_run_writes_machine_readable_plan(self):
        script_path = PROJECT_ROOT / "tools" / "agentic" / "run_agentic_pipeline.py"
        out_dir = PROJECT_ROOT / "artifacts" / "agentic_pipeline_test"
        out_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--dry-run",
                "--out",
                str(out_dir),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        plan_path = out_dir / "agentic_run_plan.json"
        self.assertTrue(plan_path.exists())
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(plan["status"], "dry_run")
        self.assertGreaterEqual(len(plan["stages"]), 5)
        blocked = [stage for stage in plan["stages"] if stage["blocked_reasons"]]
        self.assertTrue(blocked)

    def test_dry_run_accepts_profile_overrides(self):
        script_path = PROJECT_ROOT / "tools" / "agentic" / "run_agentic_pipeline.py"
        out_dir = PROJECT_ROOT / "artifacts" / "agentic_pipeline_profile_test"
        out_dir.mkdir(parents=True, exist_ok=True)
        screener_config = PROJECT_ROOT / "screener_configs" / "通用分类学新种筛选_V2模板.json"
        figure_profile = PROJECT_ROOT / "multimodal_configs" / "通用分类学图版提取复核_模板.json"
        part_description_profile = PROJECT_ROOT / "part_description_configs" / "通用分类学部位描述抽取_模板.json"
        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--dry-run",
                "--out",
                str(out_dir),
                "--screener-config",
                str(screener_config),
                "--figure-profile",
                str(figure_profile),
                "--part-description-profile",
                str(part_description_profile),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        plan_path = out_dir / "agentic_run_plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertTrue(plan["inputs"]["screener_config"]["exists"])
        self.assertTrue(plan["inputs"]["figure_profile"]["exists"])
        self.assertTrue(plan["inputs"]["part_description_profile"]["exists"])
        stages = {stage["stage_id"]: stage for stage in plan["stages"]}
        self.assertIn(str(screener_config), stages["stage_10_literature_screening"]["command"])
        self.assertIn(str(figure_profile), stages["stage_20_figure_extraction"]["command"])
        self.assertIn(str(part_description_profile), stages["stage_20_figure_extraction"]["command"])
        self.assertTrue(
            any(
                path.endswith("taxamask_literature_v2_artifacts/figure_images")
                for path in stages["stage_20_figure_extraction"]["outputs"]
            )
        )
        self.assertTrue(stages["stage_40_agentic_import_to_project"]["missing_artifacts"])
        self.assertIn("missing_artifacts:", "\n".join(stages["stage_40_agentic_import_to_project"]["blocked_reasons"]))


if __name__ == "__main__":
    unittest.main()
