import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { applyTaxaMaskEmbedMode } from "../../src/dashboard/public/app-embed.ts";
import { taxamaskSourceWriteDecision } from "../../src/permissions/taxamask-source-guard.ts";
import { loadSkills } from "../../src/skills/registry.ts";
import { BUILT_IN_TOOLS } from "../../src/tools/definitions.ts";
import { formatToolResultForModel } from "../../src/tools/result-view.ts";
import { bundledRgCandidates, rgSearchTool, toWindowsPathIfWslMount, wslWindowsRgCandidates } from "../../src/tools/rg-tools.ts";
import { parseBingHtml, parseWikipediaQueryJson, wikipediaLanguageForQuery } from "../../src/tools/web-tools.ts";

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const TAXAMASK_ROOT = path.resolve(PACKAGE_ROOT, "..", "..");

function fakeClassList() {
  const values = new Set<string>();
  return {
    add: (...items: string[]) => {
      for (const item of items) {
        values.add(item);
      }
    },
    remove: (...items: string[]) => {
      for (const item of items) {
        values.delete(item);
      }
    },
    contains: (item: string) => values.has(item),
    values
  };
}

test("package version and engines match the TaxaMask 2.0 TypeScript embed", async () => {
  const pkg = JSON.parse(await fs.readFile(path.join(PACKAGE_ROOT, "package.json"), "utf8"));
  assert.equal(pkg.version, "2.0.5-taxamask.1");
  assert.equal(pkg.engines.node, ">=22.18");
  assert.equal(pkg.bin["ant-code"], "./src/cli/index.ts");
});

test("TaxaMask source-write guard distinguishes source vs adapter writes", () => {
  const cwd = TAXAMASK_ROOT;
  const source = taxamaskSourceWriteDecision({
    toolName: "write_file",
    input: { path: "AntSleap/main.py" }
  }, { cwd });
  assert.equal(source.blocked, true);
  assert.equal(source.requiresApproval, true);
  assert.equal(source.scope, "taxamask.source_development");

  const adapter = taxamaskSourceWriteDecision({
    toolName: "write_file",
    input: { path: "external_backends/example.py" }
  }, { cwd });
  assert.equal(adapter.blocked, true);
  assert.equal(adapter.requiresApproval, true);
  assert.equal(adapter.scope, "taxamask.adapter");
});

test("Dashboard embed bootstrap applies taxamask-embed when taxamask_embed is in the query", () => {
  const html = { classList: fakeClassList(), style: {} as { colorScheme?: string } };
  const body = { classList: fakeClassList() };
  const previousDocument = globalThis.document;
  const previousLocation = globalThis.location;
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value: { documentElement: html, body }
  });
  try {
    assert.equal(applyTaxaMaskEmbedMode(""), false);
    assert.equal(html.classList.contains("taxamask-embed"), false);
    assert.equal(applyTaxaMaskEmbedMode("?taxamask_embed=1"), true);
    assert.equal(html.classList.contains("taxamask-embed"), true);
    assert.equal(body.classList.contains("taxamask-embed-body"), true);
    assert.equal(applyTaxaMaskEmbedMode("?taxamask_embed=1&taxamask_theme=light"), true);
    assert.equal(html.classList.contains("taxamask-embed-light"), true);
  } finally {
    Object.defineProperty(globalThis, "document", {
      configurable: true,
      value: previousDocument
    });
    if (previousLocation !== undefined) {
      Object.defineProperty(globalThis, "location", {
        configurable: true,
        value: previousLocation
      });
    }
  }
});

test("standalone git write tools are on the built-in tool list", () => {
  const names = BUILT_IN_TOOLS.map((tool) => tool.name);
  for (const name of ["git_status", "git_diff", "git_commit", "git_add", "git_branch", "git_stash"]) {
    assert.equal(names.includes(name), true, `missing ${name}`);
  }
});

test("embed stylesheet covers 2.0 settings and reasoning controls", async () => {
  const css = await fs.readFile(path.join(PACKAGE_ROOT, "src", "dashboard", "public", "styles.css"), "utf8");
  assert.equal(css.includes(".taxamask-embed .reasoning-effort-control"), true);
  assert.equal(css.includes(".taxamask-embed .settings-rail"), true);
  assert.equal(css.includes(".taxamask-embed .settings-default-scope-picker button"), true);
  assert.equal(css.includes(".taxamask-embed .atmosphere"), true);
  assert.equal(css.includes("html.taxamask-embed-light"), true);
  assert.equal(css.includes("html.taxamask-embed-light .composer"), true);
  assert.equal(css.includes(".settings-field-stack textarea"), true);
  assert.equal(css.includes("color-scheme: light !important"), true);
  assert.equal(css.includes("#15191d"), false);
});

test("TaxaMask dashboard embed entry does not load the full CLI graph", async () => {
  const entry = await fs.readFile(path.join(PACKAGE_ROOT, "src", "cli", "dashboard-embed.ts"), "utf8");
  assert.equal(entry.includes("startDashboard"), true);
  assert.equal(entry.includes("../tui.ts"), false);
  assert.equal(entry.includes("../interactive.ts"), false);
  assert.equal(entry.includes("../diagnostics/doctor.ts"), false);
});

test("TaxaMask bundled skills remain loadable from the shipped registry", async () => {
  const skills = await loadSkills({ cwd: TAXAMASK_ROOT, config: {}, env: {} });
  const names = skills.map((skill) => skill.name);
  assert.equal(names.includes("taxamask-pdf-evidence"), true);
  assert.equal(names.includes("taxonomy-paper-finder"), true);
});

test("bundled ripgrep resolves to an existing executable instead of a bare rg command", async () => {
  const env = { LAB_AGENT_PACKAGE_ROOT: PACKAGE_ROOT };
  const candidates = bundledRgCandidates(env);
  assert.equal(candidates.some((item) => item.endsWith("rg.exe") || item.endsWith(`${path.sep}rg`)), true);
  const existing = [];
  for (const candidate of candidates) {
    try {
      await fs.access(candidate);
      existing.push(candidate);
    } catch {
      // Skip missing optional platform packages.
    }
  }
  assert.equal(existing.length > 0, true, "expected vendored rg.exe next to @vscode/ripgrep");
  const result = await rgSearchTool({
    cwd: TAXAMASK_ROOT,
    path: "AntSleap/main.py",
    pattern: "def ",
    maxResults: 3
  });
  assert.equal("error" in result, false);
  assert.equal(Array.isArray(result.matches) && result.matches.length > 0, true);
  assert.equal(String(result.command ?? "").startsWith("rg "), true);
  assert.equal(
    toWindowsPathIfWslMount("/mnt/c/saveproject/LBJ-workspace/Formica-Flow-Latest/AntSleap/main.py"),
    "C:\\saveproject\\LBJ-workspace\\Formica-Flow-Latest\\AntSleap\\main.py"
  );
  const wslCandidates = wslWindowsRgCandidates({
    WSL_DISTRO_NAME: "Ubuntu",
    LAB_AGENT_PACKAGE_ROOT: PACKAGE_ROOT
  });
  assert.equal(wslCandidates.some((item) => item.endsWith(`${path.sep}rg.exe`)), true);
});

test("model-facing skill_list and rg_count views keep the actual payload", () => {
  const skillView = formatToolResultForModel("skill_list", {
    ok: true,
    result: [
      { name: "taxamask-pdf-evidence", description: "PDF evidence" },
      { name: "taxonomy-paper-finder", description: "literature search" }
    ]
  });
  assert.match(skillView.content, /skills=2/);
  assert.match(skillView.content, /taxamask-pdf-evidence/);
  assert.equal(skillView.content.includes("\n{}"), false);

  const countView = formatToolResultForModel("rg_count", {
    ok: true,
    result: { command: "rg --count-matches", mode: "matches", count: 17 }
  });
  assert.match(countView.content, /count=17/);
  assert.equal(countView.content.includes("matches=0"), false);

  const mcpView = formatToolResultForModel("mcp_list", { ok: true, result: [] });
  assert.match(mcpView.content, /servers=0/);

  const todoView = formatToolResultForModel("todo_read", {
    ok: true,
    result: [{ id: "1", status: "pending", content: "inspect workspace" }]
  });
  assert.match(todoView.content, /todos=1/);
  assert.match(todoView.content, /inspect workspace/);
});

test("wikipedia and bing parsers keep encyclopedia and HTML search results", () => {
  const results = parseWikipediaQueryJson({
    query: {
      search: [
        {
          title: "Camponotus",
          snippet: "A genus of <span class=\"searchmatch\">ants</span> in the subfamily Formicinae."
        }
      ]
    }
  }, "en");
  assert.equal(wikipediaLanguageForQuery("Camponotus japonicus"), "en");
  assert.equal(wikipediaLanguageForQuery("日本弓背蚁"), "zh");
  assert.equal(results.length, 1);
  assert.equal(results[0].title, "Camponotus");
  assert.equal(results[0].url, "https://en.wikipedia.org/wiki/Camponotus");
  assert.equal(results[0].engine, "wikipedia");

  const bing = parseBingHtml(`
    <li class="b_algo">
      <h2><a href="https://www.antweb.org/description.do?genus=solenopsis">Solenopsis invicta</a></h2>
      <cite>https://www.antweb.org › description</cite>
      <p>Red imported fire ant species page.</p>
    </li>
  `);
  assert.equal(bing.length, 1);
  assert.equal(bing[0].url, "https://www.antweb.org/description.do?genus=solenopsis");
  assert.equal(bing[0].engine, "bing");
});
