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

    def test_ant_code_can_skip_project_config_without_loading_user_defaults(self):
        config_module = (PROJECT_ROOT / "vendor" / "ant-code" / "src" / "config" / "load-config.js").resolve().as_uri()
        self._run_node_contract(
            f"""
            import assert from "node:assert/strict";
            import fs from "node:fs/promises";
            import os from "node:os";
            import path from "node:path";
            import {{ loadConfig }} from {json.dumps(config_module)};

            const root = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-config-boundary-"));
            const cwd = path.join(root, "project");
            const home = path.join(root, "home");
            await fs.mkdir(path.join(cwd, ".lab-agent"), {{ recursive: true }});
            await fs.mkdir(path.join(home, ".ant-code"), {{ recursive: true }});
            await fs.writeFile(
              path.join(cwd, ".lab-agent", "config.json"),
              JSON.stringify({{ modelAlias: "project-only-model", models: [{{ id: "project-only-model" }}] }}),
              "utf8"
            );
            await fs.writeFile(
              path.join(home, ".ant-code", "lab-agent.config.json"),
              JSON.stringify({{ modelAlias: "user-default-model", models: [{{ id: "user-default-model" }}] }}),
              "utf8"
            );
            const explicitPath = path.join(root, "explicit-config.json");
            await fs.writeFile(
              explicitPath,
              JSON.stringify({{ modelAlias: "explicit-model", models: [{{ id: "explicit-model" }}] }}),
              "utf8"
            );

            const project = await loadConfig({{ cwd, env: {{ HOME: home, USERPROFILE: home }} }});
            assert.equal(project.modelAlias, "project-only-model");
            assert.equal(project.projectConfigPath, path.join(cwd, ".lab-agent", "config.json"));

            const skipped = await loadConfig({{
              cwd,
              env: {{ HOME: home, USERPROFILE: home, LAB_AGENT_SKIP_PROJECT_CONFIG: "true" }}
            }});
            assert.notEqual(skipped.modelAlias, "project-only-model");
            assert.notEqual(skipped.modelAlias, "user-default-model");
            assert.equal(skipped.projectConfigPath, null);
            assert.equal(skipped.lab.configPath, null);

            const explicit = await loadConfig({{
              cwd: path.join(root, "empty-project"),
              env: {{ LAB_AGENT_CONFIG: explicitPath }}
            }});
            assert.equal(explicit.modelAlias, "explicit-model");
            assert.equal(explicit.lab.configPath, explicitPath);

            const projectOverExplicit = await loadConfig({{
              cwd,
              env: {{ LAB_AGENT_CONFIG: explicitPath }}
            }});
            assert.equal(projectOverExplicit.modelAlias, "project-only-model");
            assert.equal(projectOverExplicit.configSources.modelAlias.type, "project");
            """
        )

    def test_ant_code_project_config_writes_are_atomic(self):
        config_store_module = (PROJECT_ROOT / "vendor" / "ant-code" / "src" / "dashboard" / "config-store.js").resolve().as_uri()
        self._run_node_contract(
            f"""
            import assert from "node:assert/strict";
            import fs from "node:fs/promises";
            import os from "node:os";
            import path from "node:path";
            import {{ atomicWriteJsonConfig, mutateJsonConfig }} from {json.dumps(config_store_module)};

            const root = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-atomic-config-"));
            const filePath = path.join(root, ".lab-agent", "config.json");
            await atomicWriteJsonConfig(filePath, {{ models: [{{ id: "base" }}] }});
            await Promise.all(Array.from({{ length: 6 }}, (_, index) => mutateJsonConfig(filePath, (config) => ({{
              ...config,
              models: [...(config.models ?? []), {{ id: `model-${{index}}` }}]
            }}))));

            const saved = JSON.parse(await fs.readFile(filePath, "utf8"));
            assert.equal(saved.models.length, 7);
            assert.deepEqual(
              (await fs.readdir(path.dirname(filePath))).filter((name) => name.endsWith(".tmp") || name.endsWith(".lock")),
              []
            );
            """
        )

    def test_ant_code_project_config_write_failure_preserves_previous_file(self):
        config_store_module = (PROJECT_ROOT / "vendor" / "ant-code" / "src" / "dashboard" / "config-store.js").resolve().as_uri()
        self._run_node_contract(
            f"""
            import assert from "node:assert/strict";
            import fs from "node:fs/promises";
            import os from "node:os";
            import path from "node:path";
            import {{ atomicWriteJsonConfig, mutateJsonConfig }} from {json.dumps(config_store_module)};

            const root = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-config-rollback-"));
            const filePath = path.join(root, ".lab-agent", "config.json");
            await atomicWriteJsonConfig(filePath, {{ modelAlias: "stable-model" }});
            await assert.rejects(mutateJsonConfig(filePath, () => {{
              throw new Error("fault injection");
            }}), /fault injection/);

            assert.deepEqual(JSON.parse(await fs.readFile(filePath, "utf8")), {{ modelAlias: "stable-model" }});
            assert.deepEqual(
              (await fs.readdir(path.dirname(filePath))).filter((name) => name.endsWith(".tmp") || name.endsWith(".lock")),
              []
            );
            """
        )

    def test_ant_code_project_config_only_overrides_environment_fields_it_defines(self):
        sessions_module = (PROJECT_ROOT / "vendor" / "ant-code" / "src" / "dashboard" / "sessions.js").resolve().as_uri()
        self._run_node_contract(
            f"""
            import assert from "node:assert/strict";
            import fs from "node:fs/promises";
            import os from "node:os";
            import path from "node:path";
            import {{ createDashboardRuntime }} from {json.dumps(sessions_module)};

            const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-partial-project-config-"));
            await fs.mkdir(path.join(cwd, ".lab-agent"), {{ recursive: true }});
            await fs.writeFile(
              path.join(cwd, ".lab-agent", "config.json"),
              JSON.stringify({{ transcript: {{ retentionDays: 7 }} }}),
              "utf8"
            );
            const runtime = createDashboardRuntime({{
              cwd,
              env: {{
                LAB_MODEL_GATEWAY_URL: "https://env.gateway.example/v1/chat/completions",
                LAB_MODEL_GATEWAY_PROTOCOL: "openai-chat",
                LAB_MODEL_GATEWAY_API_KEY: "env-key",
                LAB_AGENT_MODEL: "env-model"
              }}
            }});

            const fallback = await runtime.status();
            assert.equal(fallback.gatewayConfig.gatewayUrl, "https://env.gateway.example/v1/chat/completions");
            assert.equal(fallback.gatewayConfig.gatewayProtocol, "openai-chat");
            assert.equal(fallback.gatewayConfig.apiKeyConfigured, true);
            assert.equal(fallback.sessionStatus.model, "env-model");
            assert.equal(fallback.gatewayConfig.sources.gatewayUrl.type, "environment");

            await fs.writeFile(
              path.join(cwd, ".lab-agent", "config.json"),
              JSON.stringify({{
                modelAlias: "project-model",
                models: [{{ id: "project-model" }}],
                lab: {{
                  gatewayUrl: "https://project.gateway.example/v1/chat/completions",
                  gatewayProtocol: "openai-chat"
                }}
              }}),
              "utf8"
            );
            const project = await runtime.status();
            assert.equal(project.gatewayConfig.gatewayUrl, "https://project.gateway.example/v1/chat/completions");
            assert.equal(project.sessionStatus.model, "project-model");
            assert.equal(project.gatewayConfig.sources.gatewayUrl.type, "project");
            assert.equal(project.gatewayConfig.sources.apiKey.type, "environment");
            """
        )

    def test_ant_code_file_preview_blocks_link_escape(self):
        files_module = (PROJECT_ROOT / "vendor" / "ant-code" / "src" / "dashboard" / "files.js").resolve().as_uri()
        self._run_node_contract(
            f"""
            import assert from "node:assert/strict";
            import fs from "node:fs/promises";
            import os from "node:os";
            import path from "node:path";
            import {{ previewFile, readRawFile }} from {json.dumps(files_module)};

            const root = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-dashboard-link-"));
            const cwd = path.join(root, "workspace");
            const outside = path.join(root, "outside");
            await fs.mkdir(cwd);
            await fs.mkdir(outside);
            await fs.writeFile(path.join(outside, "secret.txt"), "secret", "utf8");
            await fs.symlink(outside, path.join(cwd, "escape"), process.platform === "win32" ? "junction" : "dir");

            const preview = await previewFile(cwd, path.join("escape", "secret.txt"));
            const raw = await readRawFile(cwd, path.join("escape", "secret.txt"));
            assert.equal(preview.ok, false);
            assert.equal(preview.status, 403);
            assert.equal(raw.ok, false);
            assert.equal(raw.status, 403);
            """
        )

    def test_ant_code_separates_visible_transcript_from_model_context(self):
        store_module = (PROJECT_ROOT / "vendor" / "ant-code" / "src" / "storage" / "session-store.js").resolve().as_uri()
        self._run_node_contract(
            f"""
            import assert from "node:assert/strict";
            import fs from "node:fs/promises";
            import os from "node:os";
            import path from "node:path";
            import {{ createSessionStore }} from {json.dumps(store_module)};

            const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-session-archives-"));
            const store = createSessionStore({{ cwd }});
            const visible = await store.writeTranscriptChunks("session-a", [
              {{ role: "user", content: "visible question" }},
              {{ role: "assistant", content: [{{ type: "text", text: "visible answer" }}] }}
            ]);
            const model = await store.writeTranscriptChunks("session-a", [
              {{ role: "user", content: "internal model context" }}
            ], {{}}, {{ suffix: "model-context" }});

            assert.ok(visible.chunks[0].file.includes("session-a.transcript"));
            assert.ok(model.chunks[0].file.includes("session-a.model-context"));
            assert.notEqual(visible.chunks[0].file, model.chunks[0].file);
            const sessionsRoot = path.join(cwd, ".lab-agent", "sessions");
            assert.equal((await fs.stat(path.join(sessionsRoot, "session-a.transcript"))).isDirectory(), true);
            assert.equal((await fs.stat(path.join(sessionsRoot, "session-a.model-context"))).isDirectory(), true);

            await store.writeMetadata({{ id: "session-a", status: "completed" }});
            const deleted = await store.deleteSession("session-a");
            assert.equal(deleted.ok, true);
            await assert.rejects(fs.stat(path.join(sessionsRoot, "session-a.transcript")), {{ code: "ENOENT" }});
            await assert.rejects(fs.stat(path.join(sessionsRoot, "session-a.model-context")), {{ code: "ENOENT" }});
            """
        )

    def test_ant_code_does_not_compact_without_prior_conversation(self):
        context_module = (PROJECT_ROOT / "vendor" / "ant-code" / "src" / "core" / "context-window.js").resolve().as_uri()
        self._run_node_contract(
            f"""
            import assert from "node:assert/strict";
            import {{ compactSessionContextWithModel, createContextWindow }} from {json.dumps(context_module)};

            let gatewayCalls = 0;
            let compactingSignals = 0;
            const session = {{
              id: "first-question",
              cwd: process.cwd(),
              config: {{ context: {{ maxMessages: 1, maxBytes: 1, maxTokens: 1 }} }},
              messages: []
            }};
            session.contextWindow = createContextWindow(session.config);
            const result = await compactSessionContextWithModel(session, {{
              force: true,
              reason: "automatic_prompt_budget",
              gateway: {{
                configured: true,
                async sendChat() {{
                  gatewayCalls += 1;
                  return {{ ok: true, data: {{ text: "should not run" }} }};
                }}
              }},
              async onBeforeCompact() {{
                compactingSignals += 1;
              }}
            }});

            assert.equal(result.compacted, false);
            assert.equal(result.reason, "nothing_to_compact");
            assert.equal(gatewayCalls, 0);
            assert.equal(compactingSignals, 0);
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
