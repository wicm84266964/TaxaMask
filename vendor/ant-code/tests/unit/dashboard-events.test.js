import assert from "node:assert/strict";
import test from "node:test";
import { mapSessionEventToDashboard } from "../../src/dashboard/events.js";

test("dashboard maps thinking to folded activity without text", () => {
  const events = mapSessionEventToDashboard({
    type: "assistant_thinking_delta",
    text: "secret reasoning"
  });

  assert.equal(events.length, 1);
  assert.equal(events[0].type, "activity");
  assert.equal(events[0].title, "正在分析任务");
  assert.equal(events[0].coalesceKey, "thinking");
  assert.doesNotMatch(JSON.stringify(events[0]), /secret reasoning/);
});

test("dashboard maps visible assistant deltas to draft events", () => {
  const events = mapSessionEventToDashboard({
    type: "assistant_delta",
    round: 2,
    text: "visible draft",
    bytes: 13
  });

  assert.equal(events.length, 1);
  assert.equal(events[0].type, "assistant_draft");
  assert.equal(events[0].round, 2);
  assert.equal(events[0].text, "visible draft");
  assert.equal(events[0].bytes, 13);
});

test("dashboard maps normalized assistant text deltas to draft events", () => {
  const events = mapSessionEventToDashboard({
    type: "assistant_text_delta",
    payload: {
      round: 3,
      text: "normalized draft",
      bytes: 16
    }
  });

  assert.equal(events.length, 1);
  assert.equal(events[0].type, "assistant_draft");
  assert.equal(events[0].round, 3);
  assert.equal(events[0].text, "normalized draft");
});

test("dashboard maps streaming status to coalesced live activity", () => {
  const events = mapSessionEventToDashboard({
    type: "gateway_stream_start",
    round: 1
  });

  assert.equal(events.length, 1);
  assert.equal(events[0].type, "activity");
  assert.equal(events[0].status, "running");
  assert.equal(events[0].coalesceKey, "assistant-stream");
});

test("dashboard marks agent_run activity for live subtask display", () => {
  const events = mapSessionEventToDashboard({
    type: "tool_start",
    name: "agent_run",
    toolCallId: "agent-1",
    profile: "explorer"
  });

  assert.equal(events.length, 1);
  assert.equal(events[0].toolName, "agent_run");
  assert.equal(events[0].profile, "explorer");
  assert.equal(events[0].coalesceKey, "tool:agent-1");
});

test("dashboard maps tool finish to concise result", () => {
  const events = mapSessionEventToDashboard({
    type: "tool_finish",
    name: "write_file",
    toolCallId: "tool-1",
    ok: true,
    resultBytes: 120
  });

  assert.equal(events.length, 1);
  assert.equal(events[0].title, "写入文件已完成");
  assert.equal(events[0].status, "completed");
  assert.equal(events[0].collapsed, true);
});

test("dashboard carries compact file change counters without diff text", () => {
  const events = mapSessionEventToDashboard({
    type: "tool_finish",
    name: "edit_file",
    toolCallId: "tool-2",
    ok: true,
    changeStats: {
      path: "src/app.js",
      additions: 3,
      deletions: 1,
      files: 1,
      truncated: true
    }
  });

  assert.deepEqual(events[0].changeStats, {
    path: "src/app.js",
    additions: 3,
    deletions: 1,
    files: 1,
    redacted: false,
    truncated: true,
    approximate: false
  });
  assert.doesNotMatch(JSON.stringify(events[0]), /diff --git|@@ -/);
});

test("dashboard carries empty per-turn change counters", () => {
  const events = mapSessionEventToDashboard({
    type: "tool_finish",
    name: "edit_file",
    toolCallId: "tool-3",
    ok: true,
    turnChangeStats: {
      additions: 0,
      deletions: 0,
      files: 0
    }
  });

  assert.deepEqual(events[0].turnChangeStats, {
    additions: 0,
    deletions: 0,
    files: 0,
    redacted: false,
    truncated: false,
    approximate: false
  });
});
