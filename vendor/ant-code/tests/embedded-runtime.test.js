import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { loadConfig } from "../src/config/load-config.js";
import { createContextWindow } from "../src/core/context-window.js";
import { classifyToolUse } from "../src/agents/delegation-guard.js";
import { mapSessionEventToDashboard } from "../src/dashboard/events.js";
import { createDashboardRuntime } from "../src/dashboard/sessions.js";
import { loadSkills, readSkill } from "../src/skills/registry.js";
import { BUILT_IN_TOOLS } from "../src/tools/definitions.js";
import { createToolRuntime } from "../src/tools/runtime.js";
import { taxamaskSourceWriteDecision } from "../src/permissions/taxamask-source-guard.js";
import {
  createMockVerificationEnv,
  verifyMockGateway
} from "../scripts/verify-gateway-compat.js";

const execFileAsync = promisify(execFile);
const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TAXAMASK_ROOT = path.resolve(PACKAGE_ROOT, "..", "..");
const EXPECTED_SKILLS = [
  "browser-automation",
  "bug-repro",
  "codebase-orientation",
  "document-intake",
  "frontend-verifier",
  "paper-distill",
  "project-intake",
  "release-readiness-review",
  "release-review",
  "taxamask-pdf-evidence",
  "taxonomy-paper-finder",
  "test-failure-triage",
  "unsloth-studio-finetune",
  "web-research"
];

test("embedded dashboard keeps gateway retry state visible through final failure", async () => {
  const failed = mapSessionEventToDashboard({
    type: "gateway_error",
    error: { message: "Gateway returned HTTP 502" }
  });
  assert.equal(failed[0].coalesceKey, "gateway");

  const app = await fs.readFile(path.join(PACKAGE_ROOT, "src", "dashboard", "public", "app.js"), "utf8");
  assert.match(app, /function primaryLiveActivity\(active\)/);
  assert.match(app, /activity\.rawType === "gateway_retry"/);
});

test("embedded delegation guard treats ripgrep file listing by its directory scope", () => {
  const listing = classifyToolUse("rg_files", {
    path: "src/dashboard",
    glob: "**/*.js"
  }, { ok: true }, { complexPrompt: false });
  const search = classifyToolUse("rg_search", {
    path: ".",
    pattern: "gateway"
  }, { ok: true }, { complexPrompt: false });

  assert.equal(listing.broad, false);
  assert.equal(search.broad, true);
});

test("embedded config remains unconfigured without models and preserves an explicit empty list", async (t) => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-empty-models-"));
  t.after(() => fs.rm(cwd, { recursive: true, force: true }));

  const config = await loadConfig({ cwd, env: {} });

  assert.equal(config.modelAlias, "");
  assert.deepEqual(config.models, []);

  await fs.mkdir(path.join(cwd, ".lab-agent"), { recursive: true });
  await fs.writeFile(path.join(cwd, ".lab-agent", "config.json"), JSON.stringify({
    modelAlias: "",
    models: []
  }), "utf8");
  const explicitEmpty = await loadConfig({ cwd, env: {} });
  assert.equal(explicitEmpty.modelAlias, "");
  assert.deepEqual(explicitEmpty.models, []);
});

test("embedded config scopes environment keys to the matching gateway endpoint", async (t) => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-config-key-scope-"));
  t.after(() => fs.rm(cwd, { recursive: true, force: true }));
  await fs.mkdir(path.join(cwd, ".lab-agent"), { recursive: true });
  const configPath = path.join(cwd, ".lab-agent", "config.json");
  await fs.writeFile(configPath, JSON.stringify({
    modelAlias: "project-model",
    models: [{ id: "project-model" }],
    lab: {
      gatewayUrl: "https://project.gateway.example/v1/chat/completions",
      gatewayProtocol: "openai-chat"
    }
  }), "utf8");

  const differentEndpoint = await loadConfig({
    cwd,
    env: {
      LAB_MODEL_GATEWAY_URL: "https://environment.gateway.example/v1/chat/completions",
      LAB_MODEL_GATEWAY_PROTOCOL: "openai-chat",
      LAB_MODEL_GATEWAY_API_KEY: "environment-key",
      LAB_AGENT_MODEL: "environment-model"
    }
  });
  assert.equal(differentEndpoint.lab.gatewayUrl, "https://project.gateway.example/v1/chat/completions");
  assert.equal(differentEndpoint.lab.gatewayApiKey, null);
  assert.equal(differentEndpoint.configSources.lab.gatewayApiKey.type, "project");

  const keyWithoutEndpoint = await loadConfig({
    cwd,
    env: { LAB_MODEL_GATEWAY_API_KEY: "orphan-environment-key" }
  });
  assert.equal(keyWithoutEndpoint.lab.gatewayUrl, "https://project.gateway.example/v1/chat/completions");
  assert.equal(keyWithoutEndpoint.lab.gatewayApiKey, null);
  assert.equal(keyWithoutEndpoint.configSources.lab.gatewayApiKey.type, "project");

  await fs.writeFile(configPath, JSON.stringify({
    modelAlias: "project-model",
    models: [{ id: "project-model" }],
    lab: {
      gatewayUrl: "https://shared.gateway.example/v1/chat/completions",
      gatewayProtocol: "openai-chat"
    }
  }), "utf8");
  const sameEndpoint = await loadConfig({
    cwd,
    env: {
      LAB_MODEL_GATEWAY_URL: "https://shared.gateway.example/v1/chat/completions",
      LAB_MODEL_GATEWAY_PROTOCOL: "openai-chat",
      LAB_MODEL_GATEWAY_API_KEY: "shared-environment-key"
    }
  });
  assert.equal(sameEndpoint.lab.gatewayApiKey, "shared-environment-key");
  assert.equal(sameEndpoint.configSources.lab.gatewayApiKey.type, "environment");
});

test("embedded config keeps global models visible for the same project gateway", async (t) => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-model-merge-"));
  t.after(() => fs.rm(cwd, { recursive: true, force: true }));
  const globalPath = path.join(cwd, "global-config.json");
  const gatewayUrl = "https://shared.gateway.example/v1/chat/completions";
  await fs.writeFile(globalPath, JSON.stringify({
    modelAlias: "deepseek-v4-pro",
    models: [
      { id: "deepseek-v4-flash", label: "Global Flash" },
      { id: "deepseek-v4-pro", label: "DeepSeek V4 Pro" }
    ],
    lab: {
      gatewayUrl,
      gatewayProtocol: "openai-chat",
      gatewayProfiles: [{
        id: "global-shared",
        gatewayUrl,
        gatewayProtocol: "openai-chat",
        modelAlias: "deepseek-v4-pro",
        models: [{ id: "deepseek-v4-flash" }, { id: "deepseek-v4-pro" }]
      }]
    }
  }), "utf8");
  await fs.mkdir(path.join(cwd, ".lab-agent"), { recursive: true });
  await fs.writeFile(path.join(cwd, ".lab-agent", "config.json"), JSON.stringify({
    modelAlias: "deepseek-v4-flash",
    models: [{ id: "deepseek-v4-flash", label: "Project Flash" }],
    lab: {
      gatewayUrl,
      gatewayProtocol: "openai-chat",
      gatewayProfiles: [{
        id: "project-shared",
        gatewayUrl,
        gatewayProtocol: "openai-chat",
        modelAlias: "deepseek-v4-flash",
        models: [{ id: "deepseek-v4-flash" }]
      }]
    }
  }), "utf8");

  const config = await loadConfig({ cwd, env: { LAB_AGENT_CONFIG: globalPath } });

  assert.equal(config.modelAlias, "deepseek-v4-flash");
  assert.deepEqual(config.models.map((model) => model.id), ["deepseek-v4-flash", "deepseek-v4-pro"]);
  assert.deepEqual(config.lab.gatewayProfiles[0].models.map((model) => model.id), [
    "deepseek-v4-flash",
    "deepseek-v4-pro"
  ]);
});

test("embedded context budget never exceeds the selected model window", () => {
  const context = createContextWindow({
    modelAlias: "smaller-model",
    models: [{ id: "smaller-model", contextTokens: 128000 }],
    context: { maxTokens: 400000, maxBytes: 1600000 }
  });

  assert.equal(context.modelMaxTokens, 128000);
  assert.equal(context.maxTokens, 128000);
  assert.equal(context.maxBytes, 512000);
});

test("embedded dashboard keeps no-key profiles isolated from environment credentials", async (t) => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-no-key-profile-"));
  t.after(() => fs.rm(cwd, { recursive: true, force: true }));
  const runtime = createDashboardRuntime({
    cwd,
    env: {
      LAB_MODEL_GATEWAY_URL: "https://environment.gateway.example/v1/chat/completions",
      LAB_MODEL_GATEWAY_PROTOCOL: "openai-chat",
      LAB_MODEL_GATEWAY_API_KEY: "environment-key",
      LAB_AGENT_MODEL: "environment-model"
    }
  });

  await runtime.saveModelConfig({
    gatewayUrl: "https://no-key.gateway.example/v1/chat/completions",
    gatewayProtocol: "openai-chat",
    modelId: "no-key-a",
    modalities: ["text"],
    switchToModel: true
  });
  const saved = await runtime.saveModelConfig({
    gatewayUrl: "https://no-key.gateway.example/v1/chat/completions",
    gatewayProtocol: "openai-chat",
    modelId: "no-key-b",
    modalities: ["text"],
    switchToModel: true
  });
  const environmentProfile = saved.gatewayProfiles.find((profile) => profile.gatewayUrl.includes("environment.gateway"));
  const noKeyProfile = saved.gatewayProfiles.find((profile) => profile.gatewayUrl.includes("no-key.gateway"));

  const environmentSwitch = await runtime.switchGatewayProfile({ profileId: environmentProfile.id });
  assert.equal(environmentSwitch.gatewayConfig.apiKeyConfigured, true);
  const noKeySwitch = await runtime.switchGatewayProfile({ profileId: noKeyProfile.id });
  assert.equal(noKeySwitch.gatewayConfig.apiKeyConfigured, false);
  const deleted = await runtime.deleteModelConfig({ modelId: "no-key-a" });
  assert.equal(deleted.gatewayConfig.apiKeyConfigured, false);

  const local = JSON.parse(await fs.readFile(path.join(cwd, ".lab-agent", "config.json"), "utf8"));
  assert.equal(local.lab.gatewayApiKey, null);
  assert.equal(local.lab.gatewayProfiles.find((profile) => profile.id === noKeyProfile.id).gatewayApiKey, null);
  assert.equal(local.lab.gatewayProfiles.find((profile) => profile.id === environmentProfile.id).gatewayApiKey, undefined);
});

test("embedded dashboard clears stale gateway metadata and agent routes", async (t) => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-gateway-cleanup-"));
  t.after(() => fs.rm(cwd, { recursive: true, force: true }));
  await fs.mkdir(path.join(cwd, ".lab-agent"), { recursive: true });
  await fs.writeFile(path.join(cwd, ".lab-agent", "config.json"), JSON.stringify({
    modelAlias: "alpha-main",
    models: [{ id: "alpha-main" }, { id: "alpha-agent" }],
    agents: {
      modelTiers: { cheap: "alpha-agent", default: "alpha-agent", strong: "alpha-agent" },
      vision: { enabled: false, model: null }
    },
    allowedHosts: ["alpha.gateway.example", "beta.gateway.example"],
    lab: {
      gatewayUrl: "https://alpha.gateway.example/v1/chat/completions",
      gatewayHealthUrl: "https://alpha.gateway.example/health",
      gatewayProtocol: "openai-chat",
      gatewayApiKey: "alpha-key",
      activeGatewayProfile: "profile-alpha",
      gatewayProfiles: [
        {
          id: "profile-alpha",
          gatewayUrl: "https://alpha.gateway.example/v1/chat/completions",
          gatewayHealthUrl: "https://alpha.gateway.example/health",
          gatewayProtocol: "openai-chat",
          gatewayApiKey: "alpha-key",
          modelAlias: "alpha-main",
          models: [{ id: "alpha-main" }, { id: "alpha-agent" }]
        },
        {
          id: "profile-beta",
          gatewayUrl: "https://beta.gateway.example/v1/chat/completions",
          gatewayProtocol: "openai-chat",
          gatewayApiKey: null,
          modelAlias: "beta-main",
          models: [{ id: "beta-main" }]
        }
      ]
    }
  }), "utf8");
  const runtime = createDashboardRuntime({ cwd, env: {} });

  const switched = await runtime.switchGatewayProfile({ profileId: "profile-beta" });
  assert.deepEqual(switched.agentModelTiers, {});
  assert.equal(switched.visionAgent.enabled, false);

  const health = await runtime.saveModelConfig({
    gatewayUrl: "https://beta.gateway.example/v1/chat/completions",
    gatewayHealthUrl: "",
    gatewayProtocol: "openai-chat",
    modelId: "beta-main",
    switchToModel: true
  });
  assert.equal(health.gatewayConfig.gatewayHealthUrl, "");

  const local = JSON.parse(await fs.readFile(path.join(cwd, ".lab-agent", "config.json"), "utf8"));
  assert.equal(local.lab.gatewayHealthUrl, null);
  assert.equal(local.agents.modelTiers, undefined);
  assert.equal(local.agents.vision.enabled, false);
});

test("embedded dashboard removes hosts owned only by a deleted gateway", async (t) => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-gateway-host-cleanup-"));
  t.after(() => fs.rm(cwd, { recursive: true, force: true }));
  const runtime = createDashboardRuntime({ cwd, env: {} });

  await runtime.saveModelConfig({
    gatewayUrl: "https://old-gateway.example/v1/chat/completions",
    gatewayProtocol: "openai-chat",
    gatewayApiKey: "old-key",
    modelId: "old-model",
    modalities: ["text"],
    switchToModel: true
  });
  const current = await runtime.saveModelConfig({
    gatewayUrl: "https://new-gateway.example/v1/chat/completions",
    gatewayProtocol: "openai-chat",
    gatewayApiKey: "new-key",
    modelId: "new-model",
    modalities: ["text"],
    switchToModel: true
  });
  await runtime.deleteGatewayProfile({ profileId: current.gatewayConfig.activeProfileId });

  const local = JSON.parse(await fs.readFile(path.join(cwd, ".lab-agent", "config.json"), "utf8"));
  assert.equal(local.allowedHosts.includes("new-gateway.example"), false);
  assert.equal(local.allowedHosts.includes("old-gateway.example"), true);
});

test("embedded dashboard removes an unused health host when the URL is cleared", async (t) => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-health-host-cleanup-"));
  t.after(() => fs.rm(cwd, { recursive: true, force: true }));
  const runtime = createDashboardRuntime({ cwd, env: {} });

  await runtime.saveModelConfig({
    gatewayUrl: "https://chat.gateway.example/v1/chat/completions",
    gatewayHealthUrl: "https://health-only.example/status",
    gatewayProtocol: "openai-chat",
    gatewayApiKey: "gateway-key",
    modelId: "gateway-model",
    switchToModel: true
  });
  const saved = await runtime.saveModelConfig({
    gatewayUrl: "https://chat.gateway.example/v1/chat/completions",
    gatewayHealthUrl: "",
    gatewayProtocol: "openai-chat",
    modelId: "gateway-model",
    switchToModel: true
  });

  assert.equal(saved.gatewayConfig.gatewayHealthUrl, "");
  const local = JSON.parse(await fs.readFile(path.join(cwd, ".lab-agent", "config.json"), "utf8"));
  assert.equal(local.lab.gatewayHealthUrl, null);
  assert.equal(local.allowedHosts.includes("health-only.example"), false);
  assert.equal(local.allowedHosts.includes("chat.gateway.example"), true);
});

test("embedded dashboard preserves custom gateway ids and collapses endpoint duplicates", async (t) => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-custom-gateway-id-"));
  t.after(() => fs.rm(cwd, { recursive: true, force: true }));
  await fs.mkdir(path.join(cwd, ".lab-agent"), { recursive: true });
  await fs.writeFile(path.join(cwd, ".lab-agent", "config.json"), JSON.stringify({
    modelAlias: "legacy-model",
    models: [{ id: "legacy-model" }],
    allowedHosts: ["buddy.example"],
    lab: {
      gatewayUrl: "https://buddy.example/v1/chat/completions",
      gatewayProtocol: "openai-chat",
      gatewayApiKey: "generated-key",
      activeGatewayProfile: "gw-stale-generated",
      gatewayProfiles: [
        {
          id: "legacy-custom-id",
          gatewayUrl: "https://buddy.example/v1/chat/completions",
          gatewayProtocol: "openai-chat",
          gatewayApiKey: "legacy-key",
          modelAlias: "legacy-model",
          models: [{ id: "legacy-model" }]
        },
        {
          id: "gw-stale-generated",
          gatewayUrl: "https://buddy.example/v1/chat/completions",
          gatewayProtocol: "openai-chat",
          gatewayApiKey: "generated-key",
          modelAlias: "legacy-model",
          models: [{ id: "legacy-model" }]
        }
      ]
    }
  }), "utf8");
  const runtime = createDashboardRuntime({ cwd, env: {} });

  const saved = await runtime.saveModelConfig({
    gatewayUrl: "https://buddy.example/v1/chat/completions",
    gatewayProtocol: "openai-chat",
    gatewayApiKey: "replacement-key",
    modelId: "edited-model",
    previousModelId: "legacy-model",
    switchToModel: true
  });
  assert.equal(saved.gatewayConfig.activeProfileId, "legacy-custom-id");
  assert.deepEqual(saved.gatewayProfiles.map((profile) => profile.id), ["legacy-custom-id"]);

  const localAfterSave = JSON.parse(await fs.readFile(path.join(cwd, ".lab-agent", "config.json"), "utf8"));
  assert.equal(localAfterSave.lab.gatewayProfiles.length, 1);
  assert.equal(localAfterSave.lab.gatewayProfiles[0].gatewayApiKey, "replacement-key");

  const deleted = await runtime.deleteGatewayProfile({ profileId: "legacy-custom-id" });
  assert.equal(deleted.ok, true);
  assert.deepEqual(deleted.gatewayProfiles, []);
  const localAfterDelete = JSON.parse(await fs.readFile(path.join(cwd, ".lab-agent", "config.json"), "utf8"));
  assert.deepEqual(localAfterDelete.lab.gatewayProfiles, []);
  assert.equal(localAfterDelete.lab.gatewayApiKey, null);
  assert.equal(localAfterDelete.allowedHosts.includes("buddy.example"), false);
});

test("embedded dashboard isolates API keys by gateway profile", async (t) => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-gateway-key-isolation-"));
  t.after(() => fs.rm(cwd, { recursive: true, force: true }));
  const runtime = createDashboardRuntime({ cwd, env: {} });

  const first = await runtime.saveModelConfig({
    saveTarget: "project",
    gatewayUrl: "https://old-gateway.example/v1/chat/completions",
    gatewayProtocol: "openai-chat",
    gatewayApiKey: "old-secret-key",
    modelId: "old-model",
    label: "Old Model",
    modalities: ["text"],
    switchToModel: true
  });
  assert.equal(first.ok, true);

  const sameGateway = await runtime.saveModelConfig({
    saveTarget: "project",
    gatewayUrl: "https://old-gateway.example/v1/chat/completions",
    gatewayProtocol: "openai-chat",
    modelId: "old-model-2",
    label: "Old Model 2",
    modalities: ["text"],
    switchToModel: true
  });
  assert.equal(sameGateway.ok, true);
  assert.equal(sameGateway.gatewayConfig.apiKeyConfigured, true);

  const newGateway = await runtime.saveModelConfig({
    saveTarget: "project",
    gatewayUrl: "https://new-gateway.example/v1/chat/completions",
    gatewayProtocol: "openai-chat",
    modelId: "new-model",
    label: "New Model",
    modalities: ["text"],
    switchToModel: true
  });
  assert.equal(newGateway.ok, true);
  assert.equal(newGateway.gatewayConfig.apiKeyConfigured, false);

  const local = JSON.parse(await fs.readFile(path.join(cwd, ".lab-agent", "config.json"), "utf8"));
  assert.equal(local.lab.gatewayApiKey, null);
  const oldProfile = local.lab.gatewayProfiles.find((profile) => profile.gatewayUrl.includes("old-gateway.example"));
  assert.equal(oldProfile.gatewayApiKey, "old-secret-key");
});

test("embedded dashboard does not reactivate an old gateway after clearing the active one", async (t) => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-gateway-delete-"));
  t.after(() => fs.rm(cwd, { recursive: true, force: true }));
  const runtime = createDashboardRuntime({ cwd, env: {} });

  await runtime.saveModelConfig({
    saveTarget: "project",
    gatewayUrl: "https://old-gateway.example/v1/chat/completions",
    gatewayProtocol: "openai-chat",
    gatewayApiKey: "expired-old-key",
    modelId: "old-model",
    modalities: ["text"],
    switchToModel: true
  });
  await runtime.saveModelConfig({
    saveTarget: "project",
    gatewayUrl: "https://new-gateway.example/v1/chat/completions",
    gatewayProtocol: "openai-chat",
    gatewayApiKey: "new-key",
    modelId: "new-model",
    modalities: ["text"],
    switchToModel: true
  });

  const deletedModel = await runtime.deleteModelConfig({ modelId: "new-model" });
  assert.equal(deletedModel.ok, true);
  assert.equal(deletedModel.clearedGateway, true);
  assert.equal(deletedModel.gatewayConfig.gatewayUrl, "");
  assert.equal(deletedModel.gatewayConfig.apiKeyConfigured, false);
  assert.deepEqual(deletedModel.models, []);
  assert.equal(deletedModel.gatewayProfiles.some((profile) => profile.current), false);

  const restored = await runtime.saveModelConfig({
    saveTarget: "project",
    gatewayUrl: "https://new-gateway.example/v1/chat/completions",
    gatewayProtocol: "openai-chat",
    gatewayApiKey: "new-key",
    modelId: "new-model",
    modalities: ["text"],
    switchToModel: true
  });
  const deletedGateway = await runtime.deleteGatewayProfile({
    profileId: restored.gatewayConfig.activeProfileId
  });
  assert.equal(deletedGateway.ok, true);
  assert.equal(deletedGateway.clearedGateway, true);
  assert.equal(deletedGateway.gatewayConfig.gatewayUrl, "");
  assert.equal(deletedGateway.gatewayConfig.apiKeyConfigured, false);
  assert.deepEqual(deletedGateway.models, []);
  assert.equal(deletedGateway.gatewayProfiles.some((profile) => profile.current), false);

  const local = JSON.parse(await fs.readFile(path.join(cwd, ".lab-agent", "config.json"), "utf8"));
  assert.equal(local.modelAlias, "");
  assert.deepEqual(local.models, []);
  assert.equal(local.lab.gatewayUrl, null);
  assert.equal(local.lab.gatewayApiKey, null);
  assert.equal(local.lab.activeGatewayProfile, "");
});

test("TaxaMask source guard covers configuration files and background shells", async () => {
  const configPath = path.join(TAXAMASK_ROOT, "AntSleap", "config", "taxamask_ant_code.config.json");
  const config = JSON.parse(await fs.readFile(configPath, "utf8"));
  const guardedTools = config.hooks.events["tool.before"][0].when.tools;
  assert.equal(guardedTools.includes("background_shell"), true);

  const configWrite = taxamaskSourceWriteDecision({
    toolName: "write_file",
    input: { path: "AntSleap/config/taxamask_ant_code.config.json" }
  }, { cwd: TAXAMASK_ROOT });
  assert.equal(configWrite.blocked, true);
  assert.equal(configWrite.requiresApproval, true);
  assert.equal(configWrite.scope, "taxamask.source_development");

  for (const skillPath of [
    "skills/paper_distill_skill_bundle_v6_zh/skills/paper_distill/SKILL.md",
    "vendor/ant-code/config/skills/taxonomy-paper-finder/SKILL.md"
  ]) {
    const skillWrite = taxamaskSourceWriteDecision({
      toolName: "edit_file",
      input: { path: skillPath }
    }, { cwd: TAXAMASK_ROOT });
    assert.equal(skillWrite.blocked, true, skillPath);
    assert.equal(skillWrite.scope, "taxamask.source_development", skillPath);
  }

  const backgroundWrite = taxamaskSourceWriteDecision({
    toolName: "background_shell",
    input: { command: "Set-Content -Path AntSleap/main.py -Value unsafe" }
  }, { cwd: TAXAMASK_ROOT });
  assert.equal(backgroundWrite.blocked, true);
  assert.equal(backgroundWrite.requiresApproval, true);
  assert.equal(backgroundWrite.scope, "taxamask.source_development");
});

test("TaxaMask loads every bundled skill and exposes only registered tools", async () => {
  const config = {
    skills: {
      enabled: true,
      includeProjectDefaults: false,
      includeEnvironmentPaths: false
    }
  };
  const skills = await loadSkills({ cwd: TAXAMASK_ROOT, config, env: {} });
  const names = skills.map((skill) => skill.name).sort();
  const toolNames = new Set(BUILT_IN_TOOLS.map((tool) => tool.name));

  assert.deepEqual(names, EXPECTED_SKILLS);
  for (const skill of skills) {
    for (const toolName of skill.allowedTools) {
      assert.equal(toolNames.has(toolName), true, `${skill.name} references unknown tool ${toolName}`);
    }
  }

  const releaseReview = skills.find((skill) => skill.name === "release-readiness-review");
  assert.deepEqual(releaseReview.paths, [
    "README.md",
    "LLM_CONTEXT_DETAILED.md",
    "TaxaMask使用手册.md",
    "scripts/",
    "requirements.txt",
    "vendor/ant-code/package.json"
  ]);
  for (const declaredPath of releaseReview.paths) {
    await fs.access(path.join(TAXAMASK_ROOT, declaredPath));
  }

  for (const name of ["paper-distill", "unsloth-studio-finetune", "taxonomy-paper-finder"]) {
    const loaded = await readSkill({ cwd: TAXAMASK_ROOT, config, env: {}, name });
    assert.equal(loaded.ok, true, name);
    assert.equal(loaded.skill.contentTruncated, false, name);
  }

  const runtime = createToolRuntime({ cwd: TAXAMASK_ROOT, config });
  const listed = await runtime.execute("skill_list", {});
  assert.equal(listed.ok, true);
  assert.deepEqual(listed.result.map((skill) => skill.name).sort(), EXPECTED_SKILLS);
});

test("embedded git status and diff tools execute through the permission runtime", async (t) => {
  try {
    await execFileAsync("git", ["--version"]);
  } catch {
    t.skip("git executable is not available");
    return;
  }

  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "taxamask-embedded-git-"));
  t.after(() => fs.rm(cwd, { recursive: true, force: true }));
  await execFileAsync("git", ["init"], { cwd });
  await fs.writeFile(path.join(cwd, "notes.txt"), "before\n", "utf8");
  await execFileAsync("git", ["add", "notes.txt"], { cwd });
  await execFileAsync("git", ["-c", "user.email=test@example.invalid", "-c", "user.name=Test User", "commit", "-m", "init"], { cwd });
  await fs.writeFile(path.join(cwd, "notes.txt"), "after\n", "utf8");

  const runtime = createToolRuntime({ cwd });
  const status = await runtime.execute("git_status", {});
  const diff = await runtime.execute("git_diff", { pathspecs: ["notes.txt"] });

  assert.equal(status.ok, true);
  assert.match(status.result.stdout, /notes\.txt/);
  assert.equal(diff.ok, true);
  assert.match(diff.result.stdout, /\+after/);
});

test("mock gateway verification ignores user config and credentials", async (t) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "ant-code-mock-isolation-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const realSecret = "real-user-gateway-secret-must-not-leak";
  const providerSecret = "real-provider-secret-must-not-leak";
  const configPath = path.join(root, "user-lab-agent.config.json");
  await fs.writeFile(configPath, JSON.stringify({
    modelAlias: "user-private-model",
    networkMode: "offline",
    lab: {
      gatewayUrl: "http://127.0.0.1:1/v1/chat",
      gatewayHealthUrl: "http://127.0.0.1:1/health",
      gatewayApiKey: realSecret
    }
  }), "utf8");

  const polluted = {
    LAB_AGENT_CONFIG: configPath,
    LAB_AGENT_MODEL: "user-shell-model",
    LAB_MODEL_GATEWAY_URL: "http://127.0.0.1:1/v1/chat",
    LAB_MODEL_GATEWAY_HEALTH_URL: "http://127.0.0.1:1/health",
    LAB_MODEL_GATEWAY_API_KEY: realSecret,
    OPENAI_API_KEY: providerSecret
  };
  const previous = new Map(
    Object.keys(polluted).map((key) => [key, process.env[key]])
  );
  Object.assign(process.env, polluted);

  const originalFetch = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (input, init = {}) => {
    requests.push({
      url: String(input),
      authorization: new Headers(init.headers).get("authorization"),
      body: init.body ? String(init.body) : ""
    });
    return originalFetch(input, init);
  };

  try {
    const mockEnv = createMockVerificationEnv("http://127.0.0.1:54321");
    assert.equal(Object.hasOwn(mockEnv, "LAB_AGENT_CONFIG"), false);
    assert.equal(Object.hasOwn(mockEnv, "LAB_MODEL_GATEWAY_API_KEY"), false);
    assert.equal(Object.hasOwn(mockEnv, "OPENAI_API_KEY"), false);

    const result = await verifyMockGateway();

    assert.equal(result.ok, true);
    assert.equal(result.mode, "mock");
    assert.equal(result.evidence.modelAlias, "compatibility-mock");
    assert.equal(requests.length, 2);
    const urls = requests.map((request) => new URL(request.url));
    assert.deepEqual(urls.map((url) => url.pathname).sort(), ["/health", "/v1/chat"]);
    assert.equal(new Set(urls.map((url) => url.origin)).size, 1);
    assert.equal(urls.every((url) => url.hostname === "127.0.0.1"), true);
    assert.equal(urls.every((url) => url.port !== "1"), true);
    assert.equal(requests.every((request) => request.authorization === null), true);
    const chatRequest = requests.find((request) => new URL(request.url).pathname === "/v1/chat");
    assert.equal(JSON.parse(chatRequest.body).model, "compatibility-mock");
    assert.equal(JSON.stringify(result).includes(realSecret), false);
    assert.equal(JSON.stringify(result).includes(providerSecret), false);
  } finally {
    globalThis.fetch = originalFetch;
    for (const [key, value] of previous) {
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  }
});
