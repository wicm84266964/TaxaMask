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
