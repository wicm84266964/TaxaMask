import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { visibleTranscriptRole } from "../../src/dashboard/public/transcript.js";

test("dashboard transcript hides internal prompt roles", () => {
  assert.equal(visibleTranscriptRole("user"), "user");
  assert.equal(visibleTranscriptRole("assistant"), "assistant");
  assert.equal(visibleTranscriptRole("system"), null);
  assert.equal(visibleTranscriptRole("developer"), null);
  assert.equal(visibleTranscriptRole("tool"), null);
});

test("dashboard app keeps directory paths when linkifying file references", async () => {
  const appPath = path.resolve("src/dashboard/public/app.js");
  const source = await fs.readFile(appPath, "utf8");
  const harness = `
    const document = {
      querySelector() {
        return {
          addEventListener() {},
          classList: { add() {}, remove() {}, toggle() {} },
          dataset: {},
          textContent: "",
          innerHTML: "",
          append() {},
          replaceChildren() {},
          querySelectorAll() { return []; },
          querySelector() { return null; }
        };
      },
      addEventListener() {},
      createTreeWalker(root) {
        const nodes = root.nodes;
        let index = -1;
        return {
          get currentNode() { return nodes[index]; },
          nextNode() {
            index += 1;
            return index < nodes.length;
          }
        };
      },
      createDocumentFragment() {
        return { children: [], append(value) { this.children.push(value); } };
      },
      createElement(tag) {
        return {
          tag,
          className: "",
          type: "",
          dataset: {},
          textContent: "",
          children: [],
          append(value) { this.children.push(value); }
        };
      },
      createTextNode(text) {
        return { nodeType: 3, textContent: text };
      }
    };
    const NodeFilter = { SHOW_TEXT: 4, FILTER_REJECT: 0, FILTER_ACCEPT: 1 };
    const window = {};
    const navigator = { clipboard: { writeText() {} } };
    const requestAnimationFrame = () => {};
    class EventSource {}
  `;
  const code = source
    .replace(/import[^\n]+\n/g, "")
    .replace("await init();", "")
    .replace(/export\s+/g, "");
  const module = await import(`data:text/javascript,${encodeURIComponent(`${harness}\n${code}\nexport { replaceFileReferences };`)}`);
  const textNode = {
    nodeValue: "请看 reports/round-1/final.md、images/chart.png 和 example.com",
    parentElement: { closest: () => null },
    replaced: null,
    replaceWith(value) { this.replaced = value; }
  };

  module.replaceFileReferences(textNode, "reports/round-1");

  const buttons = textNode.replaced.children.filter((item) => item.tag === "button");
  assert.deepEqual(buttons.map((button) => button.dataset.file), [
    "reports/round-1/final.md",
    "reports/round-1/images/chart.png"
  ]);
});

test("dashboard app folds assistant drafts after the final answer", async () => {
  const source = await fs.readFile(path.resolve("src/dashboard/public/app.js"), "utf8");

  assert.match(source, /if \(event\.type === "assistant_final"\) \{/);
  assert.match(source, /collapseAssistantDrafts\(event\.text\)/);
  assert.match(source, /<span>思考过程<\/span>/);
  assert.match(source, /已收起 · \$\{visibleDrafts\.length\} 轮/);
  assert.match(source, /已收起 · 已汇入最终回复/);
  assert.match(source, /draft-summary-note/);
  assert.match(source, /本轮流式草稿已合并到最终回复，没有额外过程内容。/);
  assert.match(source, /renderMessageText\(body, draft\.text, \{ markdown: true, lightweight: true \}\)/);
  assert.match(source, /isDuplicateDraftText\(draft\.text, finalText\)/);
  assert.doesNotMatch(source, /draft-summary\.js/);
});

test("dashboard app guards replayed events from appending duplicate final messages", async () => {
  const source = await fs.readFile(path.resolve("src/dashboard/public/app.js"), "utf8");

  assert.match(source, /processedEventIds: new Set\(\)/);
  assert.match(source, /shouldSkipDashboardEvent\(payload\)/);
  assert.match(source, /state\.processedEventIds\.has\(id\)/);
  assert.match(source, /lastAssistantFinalSignature/);
  assert.match(source, /state\.lastAssistantFinalSignature === finalSignature/);
});

test("dashboard app keeps event streams and drafts scoped to the active turn", async () => {
  const source = await fs.readFile(path.resolve("src/dashboard/public/app.js"), "utf8");

  assert.match(source, /eventSourceSessionId/);
  assert.match(source, /lastEventSequence/);
  assert.match(source, /ensureEventsConnected\(result\.sessionId\)/);
  assert.match(source, /params\.set\("after", String\(state\.lastEventSequence\)\)/);
  assert.match(source, /function beginEventTurn\(event\)/);
  assert.match(source, /collapseAssistantDrafts\(\)/);
  assert.match(source, /const roundKey = `\$\{turnKey\}:\$\{Number\.isFinite\(event\.round\)/);
});

test("dashboard app exposes session actions and reconnects active sessions", async () => {
  const source = await fs.readFile(path.resolve("src/dashboard/public/app.js"), "utf8");

  assert.match(source, /data-action="delete"/);
  assert.match(source, /data-action="copy-id"/);
  assert.match(source, /thread-delete-confirm/);
  assert.match(source, /确认删除这个会话/);
  assert.match(source, /setSessionsRefreshState\("loading", "刷新中"\)/);
  assert.match(source, /已刷新 \$\{state\.sessions\.length\} 个会话/);
  assert.match(source, /handleTranscriptScroll/);
  assert.match(source, /loadOlderTranscript/);
  assert.match(source, /\/transcript\?\$\{new URLSearchParams/);
  assert.match(source, /previousTop \+ delta/);
  assert.match(source, /加载更早记录/);
  assert.match(source, /function copySessionId\(sessionId\)/);
  assert.match(source, /function deleteSession\(sessionId\)/);
  assert.match(source, /method: "DELETE"/);
  assert.match(source, /result\.session\.active && result\.session\.running/);
  assert.match(source, /rememberEventCursor\(result\.session\.eventCursor\)/);
  assert.match(source, /ensureEventsConnected\(id\)/);
});

test("dashboard app labels approximate change stats when present", async () => {
  const source = await fs.readFile(path.resolve("src/dashboard/public/app.js"), "utf8");

  assert.match(source, /approximate: false/);
  assert.match(source, /stats\.approximate \? "近似" : null/);
});
