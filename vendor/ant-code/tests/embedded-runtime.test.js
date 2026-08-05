import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import test from "node:test";

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
