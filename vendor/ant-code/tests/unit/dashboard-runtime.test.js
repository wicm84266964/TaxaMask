import assert from "node:assert/strict";
import fs from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { listBackgroundAgentTasks } from "../../src/agents/background-registry.js";
import { createDashboardRuntime } from "../../src/dashboard/sessions.js";
import { createSessionStore } from "../../src/storage/session-store.js";

test("dashboard runtime runs a turn and writes shared session metadata", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createGateway("dashboard answer"), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });

  try {
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "hello dashboard",
      permissionMode: "plan"
    });
    assert.equal(started.ok, true);

    const events = await waitForEvent(runtime, started.sessionId, (event) => event.type === "files_updated");
    assert.match(events.find((event) => event.type === "assistant_final")?.text ?? "", /dashboard answer/);

    const records = await runtime.listSessionRecords();
    assert.equal(records.length, 1);
    assert.equal(records[0].id, started.sessionId);
    assert.equal(records[0].title, "hello dashboard");
  } finally {
    await close(server);
  }
});

test("dashboard runtime exposes model and context status", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createGateway("status answer"), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });

  try {
    const initial = await runtime.status();
    assert.equal(initial.ok, true);
    assert.equal(typeof initial.sessionStatus.model, "string");
    assert.notEqual(initial.sessionStatus.model.length, 0);
    assert.ok(initial.sessionStatus.context.maxTokens > 0);

    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "status please",
      permissionMode: "workspace"
    });
    assert.equal(started.sessionStatus.model, initial.sessionStatus.model);

    const events = await waitForEvent(runtime, started.sessionId, (event) => event.type === "files_updated");
    const final = events.find((event) => event.type === "files_updated")?.sessionStatus;
    assert.equal(final.model, initial.sessionStatus.model);
    assert.ok(final.context.messageTokens > 0);
    assert.equal(final.context.maxTokens, initial.sessionStatus.context.maxTokens);
  } finally {
    await close(server);
  }
});

test("dashboard runtime accumulates per-turn change counters", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createWriteGateway(), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });

  try {
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "write file",
      permissionMode: "workspace"
    });

    const events = await waitForEvent(runtime, started.sessionId, (event) => event.type === "files_updated");
    const finish = events.find((event) => event.type === "activity" && event.toolName === "write_file" && event.status === "completed");
    assert.deepEqual(finish?.changeStats, {
      path: "created.md",
      additions: 2,
      deletions: 0,
      files: 1,
      redacted: false,
      truncated: false,
      approximate: false
    });
    assert.deepEqual(finish?.turnChangeStats, {
      additions: 2,
      deletions: 0,
      files: 1,
      redacted: false,
      truncated: false,
      approximate: false
    });
    assert.deepEqual(events.find((event) => event.type === "files_updated")?.changeStats, finish.turnChangeStats);
  } finally {
    await close(server);
  }
});

test("dashboard runtime reports net per-turn change counters for repeated edits", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  await fs.writeFile(path.join(cwd, "notes.md"), "alpha\nbeta\ngamma\n", "utf8");
  const server = await listen(createRepeatedEditGateway(), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });

  try {
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "edit same file twice",
      permissionMode: "workspace"
    });

    const events = await waitForEvent(runtime, started.sessionId, (event) => event.type === "files_updated");
    const finishes = events.filter((event) => event.type === "activity" && event.toolName === "edit_file" && event.status === "completed");
    assert.equal(finishes.length, 2);
    assert.deepEqual(finishes.map((event) => event.changeStats), [
      {
        path: "notes.md",
        additions: 1,
        deletions: 1,
        files: 1,
        redacted: false,
        truncated: false,
        approximate: false
      },
      {
        path: "notes.md",
        additions: 1,
        deletions: 1,
        files: 1,
        redacted: false,
        truncated: false,
        approximate: false
      }
    ]);
    assert.deepEqual(finishes.at(-1)?.turnChangeStats, {
      additions: 2,
      deletions: 2,
      files: 1,
      redacted: false,
      truncated: false,
      approximate: false
    });
    assert.deepEqual(events.find((event) => event.type === "files_updated")?.changeStats, finishes.at(-1)?.turnChangeStats);
  } finally {
    await close(server);
  }
});

test("dashboard runtime returns collected files when reopening a saved session", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  await fs.writeFile(path.join(cwd, "chart.png"), Buffer.from([0x89, 0x50, 0x4e, 0x47]));
  const server = await listen(createGateway("请查看 chart.png"), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });

  try {
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "image reference",
      permissionMode: "plan"
    });
    await waitForEvent(runtime, started.sessionId, (event) => event.type === "files_updated");

    const reopened = await runtime.readSession(started.sessionId);

    assert.equal(reopened.ok, true);
    assert.equal(reopened.session.cwd, cwd);
    assert.equal(reopened.session.files.some((file) => file.relativePath === "chart.png" && file.kind === "image"), true);
  } finally {
    await close(server);
  }
});

test("dashboard runtime sends WebUI client surface in model context", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const requests = [];
  const server = await listen(createRecordingGateway(requests, "dashboard surface answer"), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });

  try {
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "check dashboard surface",
      permissionMode: "plan"
    });
    assert.equal(started.ok, true);
    await waitForEvent(runtime, started.sessionId, (event) => event.type === "files_updated");

    const systemText = requests[0]?.messages?.[0]?.content?.[0]?.text ?? "";
    assert.match(systemText, /Client surface: dashboard WebUI/);
    assert.match(systemText, /not the terminal TUI/);
    assert.doesNotMatch(systemText, /TUI sidebar/);
    assert.doesNotMatch(systemText, /The TUI will automatically continue/);

    const metadata = JSON.parse(await fs.readFile(path.join(cwd, ".lab-agent", "sessions", `${started.sessionId}.json`), "utf8"));
    assert.equal(metadata.clientSurface, "dashboard");
  } finally {
    await close(server);
  }
});

test("dashboard runtime resumes an idle parent when a background subagent completes", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const requests = [];
  const server = await listen(createBackgroundAgentWakeGateway(requests, { childDelayMs: 120 }), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });

  try {
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "delegate background subagent",
      permissionMode: "workspace"
    });
    assert.equal(started.ok, true);

    await waitForEvent(runtime, started.sessionId, () =>
      runtime.listActiveEvents(started.sessionId)
        .some((event) => event.type === "assistant_final" && /background dispatched/.test(event.text ?? ""))
      && runtime.listActiveEvents(started.sessionId)
        .some((event) => event.type === "run_state" && event.running === false)
    );

    const wakeEvents = await waitForEvent(runtime, started.sessionId, () =>
      runtime.listActiveEvents(started.sessionId)
        .some((event) => event.type === "wakeup_queued")
    );
    const wakeupQueued = wakeEvents.find((event) => event.type === "wakeup_queued");
    assert.equal(wakeupQueued?.running, false);

    const finalEvents = await waitForEvent(runtime, started.sessionId, () =>
      runtime.listActiveEvents(started.sessionId)
        .some((event) => event.type === "assistant_final" && /wakeup consumed/.test(event.text ?? ""))
    );
    assert.deepEqual(finalEvents.filter((event) => event.type === "user_message").map((event) => event.text), [
      "delegate background subagent",
      "子智能体完成，主控自动接续"
    ]);
    await waitForCondition(() => listBackgroundAgentTasks({ parentSessionId: started.sessionId }).length === 0);
    assert.equal(listBackgroundAgentTasks({ parentSessionId: started.sessionId }).length, 0);

    const group = JSON.parse(await fs.readFile(path.join(cwd, ".lab-agent", "task-groups", "group-dashboard-bg.json"), "utf8"));
    assert.equal(group.status, "completed");
    assert.match(group.summary, /完成 1/);
    assert.equal(typeof group.wakePromptQueuedAt, "string");
    assert.equal(typeof group.wakePromptConsumedAt, "string");
  } finally {
    await close(server);
  }
});

test("dashboard runtime requires workspace trust before running a turn", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const runtime = createDashboardRuntime({ cwd, env: {} });
  const blocked = await runtime.startTurn({ prompt: "first", permissionMode: "plan" });

  assert.equal(blocked.ok, false);
  assert.equal(blocked.status, 403);
  assert.equal(blocked.trust.trusted, false);
});

test("dashboard runtime queues concurrent turns in same session", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createDelayedGateway(["first answer", "second answer"], 80), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });
  await runtime.trustWorkspace();

  try {
  const first = await runtime.startTurn({ prompt: "first", permissionMode: "plan" });
  const second = await runtime.startTurn({ prompt: "second", sessionId: first.sessionId, permissionMode: "plan" });

  assert.equal(first.ok, true);
    assert.equal(second.ok, true);
    assert.equal(second.queued, true);
    assert.equal(second.queueLength, 1);

    const events = await waitForEvent(runtime, first.sessionId, () =>
      runtime.listActiveEvents(first.sessionId).filter((event) => event.type === "files_updated").length >= 2
    );
    assert.deepEqual(events.filter((event) => event.type === "user_message").map((event) => event.text), ["first", "second"]);
    assert.match(events.filter((event) => event.type === "assistant_final").map((event) => event.text).join("\n"), /first answer/);
    assert.match(events.filter((event) => event.type === "assistant_final").map((event) => event.text).join("\n"), /second answer/);
  } finally {
    await close(server);
  }
});

test("dashboard runtime coalesces repeated live status events", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createGateway("status answer", {
    thinkingChunks: ["one ", "two ", "three "]
  }), "127.0.0.1", 0);
  try {
    const runtime = createDashboardRuntime({
      cwd,
      env: mockGatewayEnv(server)
    });
    await runtime.trustWorkspace();
    const result = await runtime.startTurn({
      prompt: "coalesce live status",
      permissionMode: "workspace"
    });
    await waitForEvent(runtime, result.sessionId, (event) => event.type === "files_updated");

    const events = runtime.listActiveEvents(result.sessionId);
    assert.equal(events.filter((event) => event.type === "activity" && event.coalesceKey === "thinking").length, 1);
    assert.equal(events.filter((event) => event.type === "activity" && event.coalesceKey === "assistant-stream").length, 1);
  } finally {
    await close(server);
  }
});

test("dashboard runtime emits assistant draft events while streaming visible text", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createGateway("streamed dashboard answer", {
    thinkingChunks: ["secret reasoning"],
    textChunks: ["streamed ", "dashboard ", "answer"]
  }), "127.0.0.1", 0);
  try {
    const runtime = createDashboardRuntime({
      cwd,
      env: mockGatewayEnv(server)
    });
    await runtime.trustWorkspace();
    const result = await runtime.startTurn({
      prompt: "stream draft",
      permissionMode: "workspace"
    });
    await waitForEvent(runtime, result.sessionId, (event) => event.type === "files_updated");

    const drafts = runtime.listActiveEvents(result.sessionId).filter((event) => event.type === "assistant_draft");
    assert.equal(drafts.map((event) => event.text).join(""), "streamed dashboard answer");
    assert.equal(runtime.listActiveEvents(result.sessionId).some((event) => /secret reasoning/.test(JSON.stringify(event))), false);
  } finally {
    await close(server);
  }
});

test("dashboard runtime replays active events after the requested sequence only", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createGateway("streamed dashboard answer", {
    textChunks: ["streamed ", "dashboard ", "answer"]
  }), "127.0.0.1", 0);
  try {
    const runtime = createDashboardRuntime({
      cwd,
      env: mockGatewayEnv(server)
    });
    await runtime.trustWorkspace();
    const result = await runtime.startTurn({
      prompt: "stream draft",
      permissionMode: "workspace"
    });
    const cursor = result.eventCursor;
    await waitForEvent(runtime, result.sessionId, (event) => event.type === "files_updated");

    const replayed = [];
    const unsubscribe = runtime.subscribe(result.sessionId, (event) => replayed.push(event), {
      afterSequence: cursor
    });
    unsubscribe?.();

    assert.deepEqual(replayed.filter((event) => event.type === "user_message").map((event) => event.text), ["stream draft"]);
    assert.equal(replayed.some((event) => event.type === "assistant_draft"), true);
    assert.equal(replayed.every((event) => event.sequence > cursor), true);
    assert.equal(new Set(replayed.map((event) => event.turnId).filter(Boolean)).size, 1);
  } finally {
    await close(server);
  }
});

test("dashboard runtime exposes running active sessions for refresh recovery", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createHangingStreamGateway(), "127.0.0.1", 0);
  try {
    const runtime = createDashboardRuntime({
      cwd,
      env: mockGatewayEnv(server)
    });
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "recover streaming draft",
      permissionMode: "workspace"
    });
    await waitForEvent(runtime, started.sessionId, (event) => event.type === "assistant_draft");

    const records = await runtime.listSessionRecords();
    const active = records.find((record) => record.id === started.sessionId);
    const reopened = await runtime.readSession(started.sessionId);
    const replayed = [];
    const unsubscribe = runtime.subscribe(started.sessionId, (event) => replayed.push(event), {
      afterSequence: reopened.session.eventCursor
    });
    unsubscribe?.();

    assert.equal(active.running, true);
    assert.equal(reopened.session.active, true);
    assert.equal(reopened.session.running, true);
    assert.equal(reopened.session.eventCursor, 0);
    assert.deepEqual(replayed.filter((event) => event.type === "user_message").map((event) => event.text), ["recover streaming draft"]);
    assert.equal(replayed.some((event) => event.type === "assistant_draft" && /partial draft/.test(event.text)), true);
    runtime.interruptTurn(started.sessionId, "test-cleanup");
    await waitForEvent(runtime, started.sessionId, (event) => event.type === "run_state" && event.running === false);
  } finally {
    await close(server);
  }
});

test("dashboard runtime omits the active turn transcript during refresh recovery", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createGateway("stable answer"), "127.0.0.1", 0);
  try {
    const runtime = createDashboardRuntime({
      cwd,
      env: mockGatewayEnv(server)
    });
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "refresh during final",
      permissionMode: "workspace"
    });
    await waitForEvent(runtime, started.sessionId, (event) => event.type === "assistant_final");

    const reopened = await runtime.readSession(started.sessionId);
    const replayed = [];
    const unsubscribe = runtime.subscribe(started.sessionId, (event) => replayed.push(event), {
      afterSequence: reopened.session.eventCursor
    });
    unsubscribe?.();

    assert.equal(reopened.session.active, true);
    assert.equal(reopened.session.running, true);
    assert.deepEqual(reopened.session.transcript, []);
    assert.equal(reopened.session.eventCursor, 0);
    assert.deepEqual(replayed.filter((event) => event.type === "user_message").map((event) => event.text), ["refresh during final"]);
    assert.match(replayed.find((event) => event.type === "assistant_final")?.text ?? "", /stable answer/);
    await waitForEvent(runtime, started.sessionId, (event) => event.type === "run_state" && event.running === false);
  } finally {
    await close(server);
  }
});

test("dashboard runtime emits workflow snapshots for visible progress", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createTodoGateway(), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });

  try {
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "show todo progress",
      permissionMode: "workspace"
    });
    assert.equal(started.ok, true);

    await waitForEvent(runtime, started.sessionId, (event) => event.type === "files_updated");
    const snapshots = runtime.listActiveEvents(started.sessionId).filter((event) => event.type === "workflow_snapshot");

    assert.equal(snapshots.length >= 2, true);
    assert.deepEqual(snapshots[0].workflow.todos.map((item) => item.status), ["in_progress", "pending"]);
    assert.deepEqual(snapshots.at(-1).workflow.todos.map((item) => item.status), ["completed", "completed"]);
    assert.equal(snapshots.at(-1).summary.completed, 2);
  } finally {
    await close(server);
  }
});

test("dashboard runtime pauses for ask_user and resumes with the answer", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createQuestionGateway(), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });

  try {
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "clarify requirement",
      permissionMode: "workspace"
    });
    assert.equal(started.ok, true);

    const waitingEvents = await waitForEvent(runtime, started.sessionId, (event) => event.type === "question_required");
    const question = waitingEvents.find((event) => event.type === "question_required")?.question;
    assert.equal(question?.header, "需求核对");
    assert.equal(question?.question, "输出格式选哪种？");
    assert.equal(question?.multiple, true);
    assert.equal(question?.allowCustom, true);
    assert.deepEqual(question?.choices.map((choice) => choice.label), ["Markdown", "PDF"]);

    const resolved = runtime.resolveQuestion(question.id, {
      selectedChoices: ["md"],
      customAnswer: "同时保留图表说明"
    });
    assert.equal(resolved.ok, true);

    const finalEvents = await waitForEvent(runtime, started.sessionId, (event) => event.type === "files_updated");
    const resolvedEvent = finalEvents.find((event) => event.type === "question_resolved");
    assert.equal(resolvedEvent?.answer, "同时保留图表说明");
    assert.deepEqual(resolvedEvent?.selectedChoices, ["Markdown"]);
    assert.match(finalEvents.find((event) => event.type === "assistant_final")?.text ?? "", /Markdown/);
    assert.match(finalEvents.find((event) => event.type === "assistant_final")?.text ?? "", /图表说明/);
  } finally {
    await close(server);
  }
});

test("dashboard runtime resolves cancelled ask_user requests", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createQuestionGateway(), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });

  try {
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "cancel clarification",
      permissionMode: "workspace"
    });
    assert.equal(started.ok, true);

    const waitingEvents = await waitForEvent(runtime, started.sessionId, (event) => event.type === "question_required");
    const question = waitingEvents.find((event) => event.type === "question_required")?.question;
    const resolved = runtime.resolveQuestion(question.id, { cancelled: true });
    assert.equal(resolved.ok, true);

    const finalEvents = await waitForEvent(runtime, started.sessionId, (event) => event.type === "files_updated");
    const resolvedEvent = finalEvents.find((event) => event.type === "question_resolved");
    assert.equal(resolvedEvent?.cancelled, true);
    assert.match(finalEvents.find((event) => event.type === "assistant_final")?.text ?? "", /已取消/);
  } finally {
    await close(server);
  }
});

test("dashboard approval denial blocks a requested file write", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createToolGateway(), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });

  try {
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "write file",
      permissionMode: "plan"
    });
    assert.equal(started.ok, true);

    const events = await waitForEvent(runtime, started.sessionId, (event) => event.type === "approval_required");
    const approval = events.find((event) => event.type === "approval_required")?.approval;
    assert.equal(approval?.toolName, "write_file");

    const denied = runtime.resolveApproval(approval.id, "deny");
    assert.equal(denied.ok, true);

    await waitForEvent(runtime, started.sessionId, (event) => event.type === "files_updated");
    await assert.rejects(() => fs.stat(path.join(cwd, "denied.md")), /ENOENT/);
  } finally {
    await close(server);
  }
});

test("dashboard runtime interrupts the current turn", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createHangingStreamGateway(), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });
  await runtime.trustWorkspace();

  try {
    const started = await runtime.startTurn({
      prompt: "interrupt me",
      permissionMode: "workspace"
    });
    assert.equal(started.ok, true);
    await waitForEvent(runtime, started.sessionId, (event) => event.type === "assistant_draft");

    const interrupted = runtime.interruptTurn(started.sessionId, "user");
    assert.equal(interrupted.ok, true);

    const events = await waitForEvent(runtime, started.sessionId, (event) => event.type === "run_state" && event.running === false);
    assert.equal(events.some((event) => event.type === "turn_interrupt_requested"), true);
    assert.equal(events.some((event) => event.rawType === "turn_interrupted" || event.coalesceKey === "turn"), true);
  } finally {
    await close(server);
  }
});

test("dashboard runtime queues guide prompts and interrupts active work", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createDelayedGateway(["old answer", "guided answer"], 80), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });
  await runtime.trustWorkspace();

  try {
    const started = await runtime.startTurn({
      prompt: "draft old plan",
      permissionMode: "workspace"
    });
    assert.equal(started.ok, true);

    const guided = runtime.guideTurn({
      sessionId: started.sessionId,
      guidance: "改成先检查测试",
      permissionMode: "workspace"
    });
    assert.equal(guided.ok, true);
    assert.equal(guided.queued, true);
    assert.equal(guided.queue[0].kind, "guide");

    const events = await waitForEvent(runtime, started.sessionId, () =>
      runtime.listActiveEvents(started.sessionId).filter((event) => event.type === "files_updated").length >= 2
    );
    assert.equal(events.some((event) => event.type === "guide_queued"), true);
    assert.equal(events.some((event) => event.type === "turn_interrupt_requested" && event.reason === "guided"), true);
    assert.match(events.filter((event) => event.type === "user_message").map((event) => event.text).join("\n"), /改成先检查测试/);
  } finally {
    await close(server);
  }
});

test("dashboard runtime converts queued prompts into guides without duplicating them", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createDelayedGateway(["old answer", "guided answer"], 80), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });
  await runtime.trustWorkspace();

  try {
    const started = await runtime.startTurn({
      prompt: "draft old plan",
      permissionMode: "workspace"
    });
    assert.equal(started.ok, true);

    const queued = await runtime.startTurn({
      sessionId: started.sessionId,
      prompt: "改成先检查测试",
      permissionMode: "workspace"
    });
    assert.equal(queued.ok, true);
    assert.equal(queued.queued, true);
    assert.equal(queued.queueLength, 1);

    const guided = runtime.guideTurn({
      sessionId: started.sessionId,
      queueItemId: queued.queue[0].id,
      permissionMode: "workspace"
    });
    assert.equal(guided.ok, true);
    assert.equal(guided.queued, true);
    assert.equal(guided.queue.length, 1);
    assert.equal(guided.queue[0].kind, "guide");
    assert.match(guided.queue[0].preview, /改成先检查测试/);
    assert.equal(guided.queue.some((item) => item.kind === "prompt" && /改成先检查测试/.test(item.preview)), false);

    const events = await waitForEvent(runtime, started.sessionId, () =>
      runtime.listActiveEvents(started.sessionId).filter((event) => event.type === "files_updated").length >= 2
    );
    assert.equal(events.some((event) => event.type === "guide_queued"), true);
    assert.equal(events.some((event) => event.type === "turn_interrupt_requested" && event.reason === "guided"), true);
    assert.deepEqual(events.filter((event) => event.type === "user_message").map((event) => event.text), [
      "draft old plan",
      "改成先检查测试"
    ]);
  } finally {
    await close(server);
  }
});

test("dashboard runtime stores guide transcript using visible guidance only", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createDelayedGateway(["old answer", "guided answer"], 80), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });
  await runtime.trustWorkspace();

  try {
    const started = await runtime.startTurn({
      prompt: "draft old plan",
      permissionMode: "workspace"
    });
    assert.equal(started.ok, true);

    const guided = runtime.guideTurn({
      sessionId: started.sessionId,
      guidance: "改成先检查测试",
      permissionMode: "workspace"
    });
    assert.equal(guided.ok, true);
    assert.equal(guided.queued, true);

    await waitForEvent(runtime, started.sessionId, () =>
      runtime.listActiveEvents(started.sessionId).filter((event) => event.type === "files_updated").length >= 2
    );

    const reopened = await runtime.readSession(started.sessionId);
    assert.equal(reopened.ok, true);
    assert.equal(reopened.session.prompt, "改成先检查测试");
    assert.equal(
      reopened.session.transcript.some((message) => message.role === "user" && message.content === "改成先检查测试"),
      true
    );
    assert.equal(JSON.stringify(reopened.session.transcript).includes("User guidance for the interrupted active turn"), false);
    assert.equal(JSON.stringify(reopened.session.transcript).includes("Original active prompt"), false);

    const metadata = JSON.parse(await fs.readFile(path.join(cwd, ".lab-agent", "sessions", `${started.sessionId}.json`), "utf8"));
    assert.equal(metadata.prompt, "改成先检查测试");
    assert.equal(
      metadata.transcript.messages.some((message) => message.role === "user" && message.content === "改成先检查测试"),
      true
    );
    assert.equal(JSON.stringify(metadata.transcript.messages).includes("User guidance for the interrupted active turn"), false);
    assert.equal(JSON.stringify(metadata.transcript.messages).includes("Original active prompt"), false);
  } finally {
    await close(server);
  }
});

test("dashboard runtime cancels queued prompts before they run", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createDelayedGateway(["first answer", "second answer"], 80), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });
  await runtime.trustWorkspace();

  try {
    const started = await runtime.startTurn({
      prompt: "first",
      permissionMode: "workspace"
    });
    const queued = await runtime.startTurn({
      sessionId: started.sessionId,
      prompt: "second should cancel",
      permissionMode: "workspace"
    });
    assert.equal(queued.ok, true);
    assert.equal(queued.queued, true);

    const cancelled = runtime.cancelQueuedTurn({
      sessionId: started.sessionId,
      queueItemId: queued.queue[0].id
    });
    assert.equal(cancelled.ok, true);
    assert.equal(cancelled.queueLength, 0);

    const events = await waitForEvent(runtime, started.sessionId, (event) => event.type === "run_state" && event.running === false);
    assert.equal(events.some((event) => event.type === "queue_item_cancelled"), true);
    assert.deepEqual(events.filter((event) => event.type === "user_message").map((event) => event.text), ["first"]);
    assert.doesNotMatch(events.filter((event) => event.type === "assistant_final").map((event) => event.text).join("\n"), /second answer/);
  } finally {
    await close(server);
  }
});

test("dashboard runtime deletes completed saved sessions", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createGateway("delete answer"), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });

  try {
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "delete me",
      permissionMode: "workspace"
    });
    await waitForEvent(runtime, started.sessionId, (event) => event.type === "files_updated");

    const deleted = await runtime.deleteSession({ sessionId: started.sessionId });

    assert.equal(deleted.ok, true);
    assert.equal((await runtime.readSession(started.sessionId)).ok, false);
    assert.equal((await runtime.listSessionRecords()).some((record) => record.id === started.sessionId), false);
  } finally {
    await close(server);
  }
});

test("dashboard runtime pages archived transcript history for display", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const runtime = createDashboardRuntime({ cwd, env: {} });
  const store = createSessionStore({ cwd });
  const messages = Array.from({ length: 155 }, (_, index) => ({
    role: index % 2 === 0 ? "user" : "assistant",
    content: index % 2 === 0
      ? `prompt ${index + 1}`
      : [{ type: "text", text: `answer ${index + 1}` }]
  }));
  const archive = await store.writeTranscriptChunks("archived-dashboard-session", messages);
  await store.writeMetadata({
    id: "archived-dashboard-session",
    prompt: "archived prompt",
    title: "archived prompt",
    status: "completed",
    transcript: {
      version: 2,
      messages: messages.slice(-50),
      archive
    }
  });

  const reopened = await runtime.readSession("archived-dashboard-session");
  const older = await runtime.readTranscriptPage({
    sessionId: "archived-dashboard-session",
    before: reopened.session.transcriptPage.cursor,
    limit: 100
  });

  assert.equal(reopened.ok, true);
  assert.equal(reopened.session.transcript.length, 100);
  assert.equal(transcriptText(reopened.session.transcript[0]), "answer 56");
  assert.equal(reopened.session.transcript.at(-1).content, "prompt 155");
  assert.equal(reopened.session.transcriptPage.hasMore, true);
  assert.equal(reopened.session.transcriptPage.cursor, "55");
  assert.equal(reopened.session.transcriptPage.total, 155);
  assert.equal(older.ok, true);
  assert.equal(older.transcript.length, 55);
  assert.equal(older.transcript[0].content, "prompt 1");
  assert.equal(older.transcript.at(-1).content, "prompt 55");
  assert.equal(older.transcriptPage.hasMore, false);
});

test("dashboard runtime refuses deleting running sessions", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createHangingStreamGateway(), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });

  try {
    await runtime.trustWorkspace();
    const started = await runtime.startTurn({
      prompt: "do not delete running",
      permissionMode: "workspace"
    });
    await waitForEvent(runtime, started.sessionId, (event) => event.type === "assistant_draft");

    const deleted = await runtime.deleteSession({ sessionId: started.sessionId });

    assert.equal(deleted.ok, false);
    assert.equal(deleted.status, 409);
    assert.equal(runtime.active.has(started.sessionId), true);
    runtime.interruptTurn(started.sessionId, "test-cleanup");
    await waitForEvent(runtime, started.sessionId, (event) => event.type === "run_state" && event.running === false);
  } finally {
    await close(server);
  }
});

test("dashboard runtime clears and compacts context after confirmation routes call runtime", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-runtime-"));
  const server = await listen(createGateway("context answer"), "127.0.0.1", 0);
  const runtime = createDashboardRuntime({ cwd, env: mockGatewayEnv(server) });
  await runtime.trustWorkspace();

  try {
    const started = await runtime.startTurn({
      prompt: "context seed",
      permissionMode: "workspace"
    });
    await waitForEvent(runtime, started.sessionId, (event) => event.type === "files_updated");

    const cleared = await runtime.clearContext({ sessionId: started.sessionId, permissionMode: "workspace" });
    assert.equal(cleared.ok, true);
    assert.equal(cleared.after.messages, 0);

    runtime.active.get(started.sessionId).session.messages = [
      { role: "user", content: "older context" },
      { role: "assistant", content: [{ type: "text", text: "older answer" }] },
      { role: "user", content: "new context" },
      { role: "assistant", content: [{ type: "text", text: "new answer" }] }
    ];
    const compacted = await runtime.compactContext({ sessionId: started.sessionId, permissionMode: "workspace" });
    assert.equal(compacted.ok, true);
    assert.equal(["local", "agent:compaction", "none"].includes(compacted.result.strategy), true);
    assert.equal(runtime.listActiveEvents(started.sessionId).some((event) => event.type === "context_compacted"), true);
  } finally {
    await close(server);
  }
});

async function waitForEvent(runtime, sessionId, predicate) {
  const existing = runtime.listActiveEvents(sessionId);
  if (existing.some(predicate)) {
    return existing;
  }
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      unsubscribe?.();
      reject(new Error("Timed out waiting for dashboard event"));
    }, 5000);
    let unsubscribe;
    unsubscribe = runtime.subscribe(sessionId, (event) => {
      if (predicate(event)) {
        clearTimeout(timeout);
        unsubscribe?.();
        resolve(runtime.listActiveEvents(sessionId));
      }
    });
  });
}

async function waitForCondition(predicate, timeoutMs = 5000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await predicate()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  assert.fail("Timed out waiting for condition");
}

function transcriptText(message) {
  if (typeof message?.content === "string") {
    return message.content;
  }
  if (!Array.isArray(message?.content)) {
    return "";
  }
  return message.content.map((item) => item?.text ?? "").join("");
}

function createGateway(text, options = {}) {
  return http.createServer(async (req, res) => {
    for await (const _ of req) {
      // Drain request body.
    }
    if ((Array.isArray(options.thinkingChunks) && options.thinkingChunks.length > 0)
      || (Array.isArray(options.textChunks) && options.textChunks.length > 0)) {
      res.writeHead(200, { "content-type": "text/event-stream" });
      res.write(`data: ${JSON.stringify({ type: "message_start", id: "mock-dashboard-stream", model: "mock-model" })}\n\n`);
      for (const chunk of options.thinkingChunks ?? []) {
        res.write(`data: ${JSON.stringify({ type: "thinking_delta", text: chunk })}\n\n`);
      }
      const textChunks = Array.isArray(options.textChunks) && options.textChunks.length > 0
        ? options.textChunks
        : [text];
      for (const chunk of textChunks) {
        res.write(`data: ${JSON.stringify({ type: "text_delta", text: chunk })}\n\n`);
      }
      res.write(`data: ${JSON.stringify({ type: "message_stop", stopReason: "stop" })}\n\n`);
      return res.end();
    }
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({
      id: "mock-dashboard-response",
      model: "mock-model",
      content: [{ type: "text", text }],
      toolCalls: [],
      stopReason: "stop"
    }));
  });
}

function createRecordingGateway(requests, text) {
  return http.createServer(async (req, res) => {
    let body = "";
    for await (const chunk of req) {
      body += Buffer.from(chunk).toString("utf8");
    }
    requests.push(JSON.parse(body));
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({
      id: `recording-${requests.length}`,
      model: "mock-model",
      content: [{ type: "text", text }],
      toolCalls: [],
      stopReason: "stop"
    }));
  });
}

function createBackgroundAgentWakeGateway(requests, options = {}) {
  let parentCalls = 0;
  return http.createServer(async (req, res) => {
    const body = await readGatewayJson(req);
    requests.push(body);
    const sessionId = String(body.metadata?.sessionId ?? body.sessionId ?? "");
    res.writeHead(200, { "content-type": "application/json" });

    if (sessionId.startsWith("agent-explorer-")) {
      await new Promise((resolve) => setTimeout(resolve, options.childDelayMs ?? 0));
      res.end(JSON.stringify({
        id: "dashboard-background-child-final",
        model: "mock-model",
        content: [{ type: "text", text: "dashboard background child done" }],
        toolCalls: [],
        stopReason: "stop"
      }));
      return;
    }

    parentCalls += 1;
    if (parentCalls === 1) {
      res.end(JSON.stringify({
        id: "dashboard-background-agent-run",
        model: "mock-model",
        content: [],
        toolCalls: [
          {
            id: "delegate-background-explorer",
            name: "agent_run",
            input: {
              profile: "explorer",
              taskId: "task-dashboard-bg",
              groupId: "group-dashboard-bg",
              query: "inspect current workspace in background",
              background: true,
              waitForGroup: "all",
              wakeParent: true
            }
          }
        ],
        stopReason: "tool_calls"
      }));
      return;
    }

    res.end(JSON.stringify({
      id: `dashboard-background-parent-final-${parentCalls}`,
      model: "mock-model",
      content: [{ type: "text", text: parentCalls === 2 ? "background dispatched" : "wakeup consumed" }],
      toolCalls: [],
      stopReason: "stop"
    }));
  });
}

function createDelayedGateway(texts, delayMs) {
  let calls = 0;
  return http.createServer(async (req, res) => {
    for await (const _ of req) {
      // Drain request body.
    }
    const text = texts[Math.min(calls, texts.length - 1)];
    calls += 1;
    await new Promise((resolve) => setTimeout(resolve, delayMs));
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({
      id: `delayed-${calls}`,
      model: "mock-model",
      content: [{ type: "text", text }],
      toolCalls: [],
      stopReason: "stop"
    }));
  });
}

async function readGatewayJson(req) {
  let body = "";
  for await (const chunk of req) {
    body += Buffer.from(chunk).toString("utf8");
  }
  return JSON.parse(body || "{}");
}

function createHangingStreamGateway() {
  return http.createServer(async (req, res) => {
    for await (const _ of req) {
      // Drain request body.
    }
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.write(`data: ${JSON.stringify({ type: "message_start", id: "hanging", model: "mock-model" })}\n\n`);
    res.write(`data: ${JSON.stringify({ type: "text_delta", text: "partial draft" })}\n\n`);
  });
}

function createToolGateway() {
  let calls = 0;
  return http.createServer(async (req, res) => {
    for await (const _ of req) {
      // Drain request body.
    }
    calls += 1;
    res.writeHead(200, { "content-type": "application/json" });
    if (calls === 1) {
      res.end(JSON.stringify({
        id: "tool-request",
        model: "mock-model",
        content: [],
        toolCalls: [
          {
            id: "write-1",
            name: "write_file",
            input: {
              path: "denied.md",
              content: "should not be written"
            }
          }
        ],
        stopReason: "tool_calls"
      }));
      return;
    }
    res.end(JSON.stringify({
      id: "final-after-deny",
      model: "mock-model",
      content: [{ type: "text", text: "write was denied" }],
      toolCalls: [],
      stopReason: "stop"
    }));
  });
}

function createWriteGateway() {
  let calls = 0;
  return http.createServer(async (req, res) => {
    for await (const _ of req) {
      // Drain request body.
    }
    calls += 1;
    res.writeHead(200, { "content-type": "application/json" });
    if (calls === 1) {
      res.end(JSON.stringify({
        id: "write-request",
        model: "mock-model",
        content: [],
        toolCalls: [
          {
            id: "write-1",
            name: "write_file",
            input: {
              path: "created.md",
              content: "alpha\nbeta"
            }
          }
        ],
        stopReason: "tool_calls"
      }));
      return;
    }
    res.end(JSON.stringify({
      id: "write-final",
      model: "mock-model",
      content: [{ type: "text", text: "write complete" }],
      toolCalls: [],
      stopReason: "stop"
    }));
  });
}

function createRepeatedEditGateway() {
  let calls = 0;
  return http.createServer(async (req, res) => {
    for await (const _ of req) {
      // Drain request body.
    }
    calls += 1;
    res.writeHead(200, { "content-type": "application/json" });
    if (calls === 1) {
      res.end(JSON.stringify({
        id: "edit-request-1",
        model: "mock-model",
        content: [],
        toolCalls: [
          {
            id: "edit-1",
            name: "edit_file",
            input: {
              path: "notes.md",
              oldText: "beta",
              newText: "delta"
            }
          }
        ],
        stopReason: "tool_calls"
      }));
      return;
    }
    if (calls === 2) {
      res.end(JSON.stringify({
        id: "edit-request-2",
        model: "mock-model",
        content: [],
        toolCalls: [
          {
            id: "edit-2",
            name: "edit_file",
            input: {
              path: "notes.md",
              oldText: "gamma",
              newText: "omega"
            }
          }
        ],
        stopReason: "tool_calls"
      }));
      return;
    }
    res.end(JSON.stringify({
      id: "edit-final",
      model: "mock-model",
      content: [{ type: "text", text: "edits complete" }],
      toolCalls: [],
      stopReason: "stop"
    }));
  });
}

function createTodoGateway() {
  let calls = 0;
  return http.createServer(async (req, res) => {
    for await (const _ of req) {
      // Drain request body.
    }
    calls += 1;
    res.writeHead(200, { "content-type": "application/json" });
    if (calls === 1) {
      res.end(JSON.stringify({
        id: "todo-request",
        model: "mock-model",
        content: [],
        toolCalls: [
          {
            id: "todo-1",
            name: "todo_write",
            input: {
              items: [
                { content: "确认需求", status: "进行中" },
                { content: "汇总结果", status: "待办" }
              ]
            }
          }
        ],
        stopReason: "tool_calls"
      }));
      return;
    }
    res.end(JSON.stringify({
      id: "todo-final",
      model: "mock-model",
      content: [{ type: "text", text: "全部待办已完成。" }],
      toolCalls: [],
      stopReason: "stop"
    }));
  });
}

function createQuestionGateway() {
  let calls = 0;
  return http.createServer(async (req, res) => {
    let body = "";
    for await (const chunk of req) {
      body += Buffer.from(chunk).toString("utf8");
    }
    calls += 1;
    res.writeHead(200, { "content-type": "application/json" });
    if (calls === 1) {
      res.end(JSON.stringify({
        id: "question-request",
        model: "mock-model",
        content: [],
        toolCalls: [
          {
            id: "question-1",
            name: "ask_user",
            input: {
              header: "需求核对",
              question: "输出格式选哪种？",
              choices: [
                { label: "Markdown", value: "md", description: "生成可直接阅读的 Markdown" },
                { label: "PDF", value: "pdf" }
              ],
              multiple: true,
              allowCustom: true,
              confirmLabel: "继续"
            }
          }
        ],
        stopReason: "tool_calls"
      }));
      return;
    }

    const parsed = JSON.parse(body);
    const toolResults = parsed.toolResults ?? [];
    const answerText = JSON.stringify(toolResults);
    const cancelled = toolResults.some((result) => {
      try {
        return JSON.parse(result.content)?.result?.cancelled === true;
      } catch {
        return false;
      }
    });
    res.end(JSON.stringify({
      id: "question-final",
      model: "mock-model",
      content: [{
        type: "text",
        text: cancelled
          ? "已取消需求核对。"
          : `已按 Markdown 继续，并保留图表说明。${answerText.includes("workflowReminder") ? " 已收到 workflow 提醒。" : ""}`
      }],
      toolCalls: [],
      stopReason: "stop"
    }));
  });
}

function listen(server, host, port) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, host, () => resolve(server));
  });
}

function close(server) {
  return new Promise((resolve) => {
    if (!server.listening) {
      resolve();
      return;
    }
    server.close(resolve);
  });
}

function mockGatewayEnv(server, extra = {}) {
  const address = server.address();
  return {
    LAB_MODEL_GATEWAY_URL: `http://127.0.0.1:${address.port}`,
    LAB_MODEL_GATEWAY_PROTOCOL: "lab-agent-gateway",
    LAB_MODEL_GATEWAY_MAX_RETRIES: "0",
    ...extra
  };
}
