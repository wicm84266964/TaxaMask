import { createSession, runSessionTurn } from "../core/session.js";
import { clearSessionContext, compactSessionContextWithModel, summarizeContextWindow } from "../core/context-window.js";
import { createLabModelGateway } from "../model-gateway/client.js";
import { resolveWorkspaceTrust, trustWorkspace as saveWorkspaceTrust } from "../permissions/workspace-trust.js";
import { createSessionStore } from "../storage/session-store.js";
import { loadConfig } from "../config/load-config.js";
import { cloneWorkflowState } from "../tools/workflow-tools.js";
import { mapSessionEventToDashboard, permissionRequestToActivity } from "./events.js";
import { applyPermissionMode, approvalDisplayMeta, approvalKeyFor, buildApprovalPreview, normalizePermissionMode, permissionModeSummary } from "./permissions.js";
import { collectSessionFiles } from "./files.js";
import { getAntCodeVersion } from "../version.js";

const MAX_EVENTS = 500;
const MAX_QUEUE = 20;
const DEFAULT_TRANSCRIPT_PAGE_LIMIT = 100;
const MAX_TRANSCRIPT_PAGE_LIMIT = 200;
const VISIBLE_TRANSCRIPT_ROLES = new Set(["user", "assistant"]);

/**
 * @param {{ cwd: string; env?: NodeJS.ProcessEnv }} options
 */
export function createDashboardRuntime(options) {
  const active = new Map();
  let processTrusted = false;

  return {
    cwd: options.cwd,
    env: options.env ?? process.env,
    active,
    async status() {
      const config = await loadConfig({ cwd: options.cwd, env: options.env });
      return {
        ok: true,
        sessionStatus: sessionStatusFromConfig(config)
      };
    },
    async trustStatus() {
      return {
        ok: true,
        trust: await resolveDashboardTrust({ cwd: options.cwd, env: options.env ?? process.env, processTrusted })
      };
    },
    async trustWorkspace() {
      await saveWorkspaceTrust({
        cwd: options.cwd,
        env: options.env ?? process.env,
        version: await getAntCodeVersion()
      });
      processTrusted = true;
      return {
        ok: true,
        trust: await resolveDashboardTrust({ cwd: options.cwd, env: options.env ?? process.env, processTrusted })
      };
    },
    async listSessionRecords() {
      const config = await loadConfig({ cwd: options.cwd, env: options.env });
      const store = createSessionStore({ cwd: options.cwd, transcript: config.transcript, env: options.env ?? process.env });
      const records = await store.listSessionRecords();
      const persisted = records.map((record) => ({
        id: record.id,
        title: record.title || record.prompt || "未命名任务",
        status: record.status ?? "unknown",
        model: record.model ?? "",
        modifiedAt: record.modifiedAt,
        finishedAt: record.finishedAt ?? null,
        transcriptMessages: record.transcriptMessages ?? 0,
        readable: record.readable !== false,
        encrypted: record.encrypted === true
      }));
      const byId = new Map(persisted.map((record) => [record.id, record]));
      for (const state of active.values()) {
        const activeRecord = activeSessionRecord(state, byId.get(state.session.id));
        byId.set(activeRecord.id, activeRecord);
      }
      return Array.from(byId.values()).sort(compareSessionRecords);
    },
    async readSession(selector) {
      const config = await loadConfig({ cwd: options.cwd, env: options.env });
      const store = createSessionStore({ cwd: options.cwd, transcript: config.transcript, env: options.env ?? process.env });
      const activeState = active.get(String(selector ?? ""));
      const result = await store.readMetadata(selector);
      if (!result.ok && !activeState) {
        return result;
      }
      const metadata = result.ok ? result.metadata ?? {} : {};
      const session = activeState?.session ?? {};
      const storedTranscript = result.ok ? await readStoredTranscriptMessages(store, metadata) : [];
      const transcript = activeState
        ? mergeTranscriptMessages(storedTranscript, stableActiveTranscriptMessages(activeState))
        : storedTranscript;
      const transcriptPage = createTranscriptPage(transcript);
      const finalText = activeState?.finalOutput || assistantTranscriptText(transcript);
      return {
        ok: true,
        session: {
          id: activeState?.session.id ?? metadata.id,
          title: session.title || metadata.title || metadata.prompt || "未命名任务",
          status: activeState ? activeDashboardStatus(activeState) : metadata.status ?? "unknown",
          cwd: session.cwd ?? metadata.cwd ?? options.cwd,
          prompt: session.prompt ?? metadata.prompt ?? "",
          outputBytes: metadata.outputBytes ?? 0,
          model: session.model ?? metadata.model ?? "",
          context: metadata.context ?? null,
          active: Boolean(activeState),
          running: activeState?.running === true,
          eventCursor: activeState ? activeReplayCursor(activeState) : null,
          sessionStatus: activeState ? sessionStatusSummary(activeState.session) : sessionStatusFromMetadata(metadata),
          permission: permissionModeSummary(activeState?.session ?? metadata),
          transcript: transcriptPage.messages,
          transcriptPage: transcriptPage.summary,
          files: collectSessionFiles({
            cwd: session.cwd ?? metadata.cwd ?? options.cwd,
            workflow: session.workflow ?? metadata.workflow ?? null
          }, finalText),
          workflow: session.workflow ?? metadata.workflow ?? null,
          modifiedAt: result.modifiedAt ?? null,
          finishedAt: metadata.finishedAt ?? null
        }
      };
    },
    async readTranscriptPage(input = {}) {
      const sessionId = String(input.sessionId ?? input.id ?? "").trim();
      if (!sessionId) {
        return { ok: false, status: 400, error: "缺少会话 ID" };
      }
      const config = await loadConfig({ cwd: options.cwd, env: options.env });
      const store = createSessionStore({ cwd: options.cwd, transcript: config.transcript, env: options.env ?? process.env });
      const activeState = active.get(sessionId);
      const result = await store.readMetadata(sessionId);
      if (!result.ok && !activeState) {
        return { ok: false, status: 404, error: result.error?.message ?? "会话不存在" };
      }
      const metadata = result.ok ? result.metadata ?? {} : {};
      const storedTranscript = result.ok ? await readStoredTranscriptMessages(store, metadata) : [];
      const transcript = activeState
        ? mergeTranscriptMessages(storedTranscript, stableActiveTranscriptMessages(activeState))
        : storedTranscript;
      const page = createTranscriptPage(transcript, {
        before: input.before,
        limit: input.limit
      });
      return {
        ok: true,
        sessionId: activeState?.session.id ?? metadata.id ?? sessionId,
        transcript: page.messages,
        transcriptPage: page.summary
      };
    },
    async deleteSession(input = {}) {
      const sessionId = String(input.sessionId ?? input.id ?? "").trim();
      if (!sessionId) {
        return { ok: false, status: 400, error: "请选择要删除的会话" };
      }
      const activeState = active.get(sessionId);
      if (activeState?.running) {
        return { ok: false, status: 409, error: "会话正在运行，结束或中断后再删除" };
      }
      if (activeState) {
        active.delete(sessionId);
      }
      const config = await loadConfig({ cwd: options.cwd, env: options.env });
      const store = createSessionStore({ cwd: options.cwd, transcript: config.transcript, env: options.env ?? process.env });
      const result = await store.deleteSession(sessionId);
      if (!result.ok && activeState) {
        return { ok: true, sessionId, activeDeleted: true, persistedDeleted: false };
      }
      if (!result.ok) {
        return { ok: false, status: 404, error: result.error?.message ?? "会话不存在" };
      }
      return { ok: true, sessionId: result.id, deleted: result.deleted, activeDeleted: Boolean(activeState), persistedDeleted: true };
    },
    async startTurn(input) {
      const prompt = String(input.prompt ?? "").trim();
      if (!prompt) {
        return { ok: false, status: 400, error: "请输入任务需求" };
      }
      const trust = await resolveDashboardTrust({ cwd: options.cwd, env: options.env ?? process.env, processTrusted });
      if (!trust.trusted) {
        return { ok: false, status: 403, error: "请先确认工作区信任", trust };
      }
      const mode = normalizePermissionMode(input.permissionMode);
      const state = await ensureTurnState(active, {
        cwd: options.cwd,
        env: options.env,
        sessionId: input.sessionId,
        mode
      });
      state.hooksTrusted = trust.trusted;
      const eventCursor = state.eventSequence;

      if (state.running) {
        const item = enqueuePrompt(state, prompt, mode, "prompt");
        appendDashboardEvent(state, {
          type: "prompt_queued",
          id: eventId("prompt-queued"),
          item: publicQueueItem(item),
          queue: queueSnapshot(state),
          queueLength: state.queuedPrompts.length,
          at: new Date().toISOString()
        });
        appendQueueUpdated(state);
        return {
          ok: true,
          queued: true,
          sessionId: state.session.id,
          eventCursor,
          queue: queueSnapshot(state),
          queueLength: state.queuedPrompts.length,
          permission: permissionModeSummary(state.session),
          sessionStatus: sessionStatusSummary(state.session)
        };
      }

      beginPrompt(state, createQueueItem(prompt, mode, "prompt"), options.env);
      return {
        ok: true,
        sessionId: state.session.id,
        eventCursor,
        permission: permissionModeSummary(state.session),
        sessionStatus: sessionStatusSummary(state.session)
      };
    },
    interruptTurn(sessionId, reason = "user") {
      const state = active.get(sessionId);
      if (!state) {
        return { ok: false, status: 404, error: "会话不存在" };
      }
      if (!state.running) {
        return { ok: false, status: 409, error: "当前没有正在运行的任务" };
      }
      requestTurnInterrupt(state, reason);
      return { ok: true, sessionId: state.session.id, queue: queueSnapshot(state), sessionStatus: sessionStatusSummary(state.session) };
    },
    cancelQueuedTurn(input = {}) {
      const state = active.get(input.sessionId);
      if (!state) {
        return { ok: false, status: 404, error: "会话不存在" };
      }
      const queueItemId = String(input.queueItemId ?? "").trim();
      if (!queueItemId) {
        return { ok: false, status: 400, error: "请选择要取消的排队消息" };
      }
      const queueItemIndex = state.queuedPrompts.findIndex((item) => item.id === queueItemId);
      if (queueItemIndex < 0) {
        return { ok: false, status: 404, error: "排队消息不存在或已被处理" };
      }
      const [removed] = state.queuedPrompts.splice(queueItemIndex, 1);
      const publicItem = publicQueueItem(removed);
      appendDashboardEvent(state, {
        type: "queue_item_cancelled",
        id: eventId("queue-cancelled"),
        item: publicItem,
        queue: queueSnapshot(state),
        queueLength: state.queuedPrompts.length,
        running: state.running,
        sessionStatus: sessionStatusSummary(state.session),
        changeStats: { ...state.turnChangeStats },
        at: new Date().toISOString()
      });
      appendQueueUpdated(state);
      return {
        ok: true,
        sessionId: state.session.id,
        item: publicItem,
        queue: queueSnapshot(state),
        queueLength: state.queuedPrompts.length,
        sessionStatus: sessionStatusSummary(state.session)
      };
    },
    guideTurn(input) {
      const state = active.get(input.sessionId);
      if (!state) {
        return { ok: false, status: 404, error: "会话不存在" };
      }
      if (!state.running) {
        return { ok: false, status: 409, error: "当前没有正在运行的任务" };
      }
      const queueItemId = String(input.queueItemId ?? "").trim();
      const queueItemIndex = queueItemId
        ? state.queuedPrompts.findIndex((item) => item.id === queueItemId && item.kind !== "guide")
        : -1;
      const queuedItem = queueItemIndex >= 0 ? state.queuedPrompts[queueItemIndex] : null;
      if (queueItemId && !queuedItem) {
        return { ok: false, status: 404, error: "排队消息不存在或已被处理" };
      }
      const guidance = String(queuedItem?.guidance ?? input.guidance ?? input.prompt ?? "").trim();
      if (!guidance) {
        return { ok: false, status: 400, error: "请输入引导内容" };
      }
      if (queuedItem) {
        state.queuedPrompts.splice(queueItemIndex, 1);
      }
      if (isStopGuidance(guidance)) {
        requestTurnInterrupt(state, "guide-stop");
        appendDashboardEvent(state, {
          type: "guide_stopped",
          id: eventId("guide-stop"),
          guidance: previewText(guidance),
          queue: queueSnapshot(state),
          at: new Date().toISOString()
        });
        return { ok: true, stopped: true, sessionId: state.session.id, queue: queueSnapshot(state), sessionStatus: sessionStatusSummary(state.session) };
      }

      const mode = normalizePermissionMode(input.permissionMode ?? state.currentPermissionMode);
      const item = createQueueItem(buildGuidePrompt(guidance, state.currentPrompt), mode, "guide", guidance);
      state.queuedPrompts.unshift(item);
      state.queuedPrompts = state.queuedPrompts.slice(0, MAX_QUEUE);
      appendDashboardEvent(state, {
        type: "guide_queued",
        id: eventId("guide"),
        item: publicQueueItem(item),
        guidance: previewText(guidance),
        queue: queueSnapshot(state),
        queueLength: state.queuedPrompts.length,
        at: new Date().toISOString()
      });
      appendQueueUpdated(state);
      requestTurnInterrupt(state, "guided");
      return {
        ok: true,
        queued: true,
        sessionId: state.session.id,
        queue: queueSnapshot(state),
        queueLength: state.queuedPrompts.length,
        sessionStatus: sessionStatusSummary(state.session)
      };
    },
    async clearContext(input = {}) {
      const trust = await resolveDashboardTrust({ cwd: options.cwd, env: options.env ?? process.env, processTrusted });
      if (!trust.trusted) {
        return { ok: false, status: 403, error: "请先确认工作区信任", trust };
      }
      if (!input.sessionId) {
        return { ok: false, status: 400, error: "当前没有可清空上下文的会话" };
      }
      const mode = normalizePermissionMode(input.permissionMode);
      const state = await ensureTurnState(active, {
        cwd: options.cwd,
        env: options.env,
        sessionId: input.sessionId,
        mode
      });
      if (state.running) {
        return { ok: false, status: 409, error: "任务运行中，结束或中断后再清空上下文" };
      }
      const before = summarizeContextWindow(state.session);
      const after = clearSessionContext(state.session);
      appendDashboardEvent(state, {
        type: "context_cleared",
        id: eventId("context-clear"),
        before,
        after,
        sessionStatus: sessionStatusSummary(state.session),
        at: new Date().toISOString()
      });
      return { ok: true, sessionId: state.session.id, before, after, sessionStatus: sessionStatusSummary(state.session) };
    },
    async compactContext(input = {}) {
      const trust = await resolveDashboardTrust({ cwd: options.cwd, env: options.env ?? process.env, processTrusted });
      if (!trust.trusted) {
        return { ok: false, status: 403, error: "请先确认工作区信任", trust };
      }
      if (!input.sessionId) {
        return { ok: false, status: 400, error: "当前没有可压缩上下文的会话" };
      }
      const mode = normalizePermissionMode(input.permissionMode);
      const state = await ensureTurnState(active, {
        cwd: options.cwd,
        env: options.env,
        sessionId: input.sessionId,
        mode
      });
      if (state.running) {
        return { ok: false, status: 409, error: "任务运行中，结束或中断后再压缩上下文" };
      }
      const before = summarizeContextWindow(state.session);
      const result = await compactSessionContextWithModel(state.session, {
        force: true,
        reason: "manual",
        gateway: createLabModelGateway(state.session.config),
        env: options.env,
        hooksTrusted: trust.trusted
      });
      const after = summarizeContextWindow(state.session);
      appendDashboardEvent(state, {
        type: "context_compacted",
        id: eventId("context-compact"),
        ...result,
        before,
        after,
        sessionStatus: sessionStatusSummary(state.session),
        at: new Date().toISOString()
      });
      return { ok: true, sessionId: state.session.id, result, before, after, sessionStatus: sessionStatusSummary(state.session) };
    },
    subscribe(sessionId, send, options = {}) {
      const state = active.get(sessionId);
      if (!state) {
        return null;
      }
      state.listeners.add(send);
      const afterSequence = nonNegativeInteger(options.afterSequence);
      for (const event of state.events) {
        if (nonNegativeInteger(event.sequence) > afterSequence) {
          send(event);
        }
      }
      return () => {
        state.listeners.delete(send);
      };
    },
    listActiveEvents(sessionId) {
      return active.get(sessionId)?.events ?? [];
    },
    async sessionCwd(sessionId) {
      const id = String(sessionId ?? "").trim();
      if (!id) {
        return { ok: false, status: 400, error: "缺少会话 ID" };
      }
      const activeState = active.get(id);
      if (activeState?.session?.cwd) {
        return { ok: true, cwd: activeState.session.cwd };
      }
      const config = await loadConfig({ cwd: options.cwd, env: options.env });
      const store = createSessionStore({ cwd: options.cwd, transcript: config.transcript, env: options.env ?? process.env });
      const result = await store.readMetadata(id);
      if (!result.ok) {
        return { ok: false, status: 404, error: "会话不存在" };
      }
      return { ok: true, cwd: result.metadata?.cwd ?? options.cwd };
    },
    resolveApproval(approvalId, action) {
      for (const state of active.values()) {
        const pending = state.pendingApprovals.get(approvalId);
        if (!pending) {
          continue;
        }
        state.pendingApprovals.delete(approvalId);
        const allowed = action === "allow-once" || action === "allow-session";
        if (action === "allow-session") {
          state.sessionApprovals.add(pending.approvalKey);
        }
        appendDashboardEvent(state, {
          type: "approval_resolved",
          id: eventId("approval-resolved"),
          approvalId,
          action,
          allowed,
          at: new Date().toISOString()
        });
        pending.resolve(allowed);
        return { ok: true };
      }
      return { ok: false, status: 404, error: "审批请求不存在或已处理" };
    },
    resolveQuestion(questionId, answer = {}) {
      for (const state of active.values()) {
        const pending = state.pendingQuestions.get(questionId);
        if (!pending) {
          continue;
        }
        state.pendingQuestions.delete(questionId);
        const result = normalizeQuestionAnswer(answer, pending.question);
        appendDashboardEvent(state, {
          type: "question_resolved",
          id: eventId("question-resolved"),
          questionId,
          answer: result.answer,
          selectedChoice: result.selectedChoice,
          selectedChoices: result.selectedChoices,
          cancelled: result.cancelled === true,
          at: new Date().toISOString()
        });
        pending.resolve(result);
        return { ok: true };
      }
      return { ok: false, status: 404, error: "需求核对请求不存在或已处理" };
    },
    sessionFiles(sessionId) {
      const state = active.get(sessionId);
      if (!state) {
        return [];
      }
      return collectSessionFiles(state.session, state.finalOutput);
    }
  };
}

async function ensureTurnState(active, options) {
  let state = options.sessionId ? active.get(options.sessionId) : null;
  if (state) {
    applyPermissionMode(state.session, options.mode);
    return state;
  }
  const session = await createSession({
    cwd: options.cwd,
    mode: "interactive",
    clientSurface: "dashboard",
    env: options.env,
    resume: options.sessionId || null,
    readonly: false,
    allowWrite: options.mode === "workspace",
    allowCommand: options.mode === "workspace",
    fullAccess: options.mode === "fullAccess"
  });
  applyPermissionMode(session, options.mode);
  state = createTurnState(session);
  active.set(session.id, state);
  return state;
}

function createTurnState(session) {
  return {
    session,
    status: "idle",
    running: false,
    controller: null,
    currentPrompt: "",
    currentTurnId: "",
    currentTranscriptStart: 0,
    currentPermissionMode: "plan",
    turnChangeStats: emptyChangeStats(),
    queuedPrompts: [],
    events: [],
    eventSequence: 0,
    listeners: new Set(),
    sessionApprovals: new Set(),
    pendingApprovals: new Map(),
    pendingQuestions: new Map(),
    finalOutput: "",
    hooksTrusted: false
  };
}

function assistantTranscriptText(messages = []) {
  if (!Array.isArray(messages)) {
    return "";
  }
  return messages
    .filter((message) => message?.role === "assistant")
    .map((message) => messageContentText(message.content))
    .filter(Boolean)
    .join("\n");
}

function activeTranscriptMessages(state) {
  if (Array.isArray(state.session.transcriptMessages) && state.session.transcriptMessages.length > 0) {
    return state.session.transcriptMessages;
  }
  return Array.isArray(state.session.messages) ? state.session.messages : [];
}

function stableActiveTranscriptMessages(state) {
  const messages = activeTranscriptMessages(state);
  if (!state?.running || !state.currentTurnId) {
    return messages;
  }
  const start = Number(state.currentTranscriptStart);
  if (!Number.isInteger(start) || start < 0) {
    return messages;
  }
  return messages.slice(0, Math.min(start, messages.length));
}

async function readStoredTranscriptMessages(store, metadata) {
  const fallback = Array.isArray(metadata?.transcript?.messages) ? metadata.transcript.messages : [];
  const archive = metadata?.transcript?.archive;
  if (!archive || !Array.isArray(archive.chunks) || archive.chunks.length === 0) {
    return fallback;
  }
  const messages = [];
  for (const chunk of archive.chunks.slice().sort((a, b) => nonNegativeInteger(a?.index) - nonNegativeInteger(b?.index))) {
    const result = await store.readTranscriptChunk(archive, chunk.index);
    if (!result.ok) {
      return fallback;
    }
    messages.push(...(result.messages ?? []));
  }
  return messages.length > 0 ? messages : fallback;
}

function mergeTranscriptMessages(baseMessages, tailMessages) {
  const base = Array.isArray(baseMessages) ? baseMessages : [];
  const tail = Array.isArray(tailMessages) ? tailMessages : [];
  if (base.length === 0) {
    return tail;
  }
  if (tail.length === 0) {
    return base;
  }
  const maxOverlap = Math.min(base.length, tail.length);
  for (let size = maxOverlap; size > 0; size -= 1) {
    if (sameTranscriptSlice(base.slice(base.length - size), tail.slice(0, size))) {
      return base.concat(tail.slice(size));
    }
  }
  return base.concat(tail);
}

function sameTranscriptSlice(left, right) {
  if (left.length !== right.length) {
    return false;
  }
  return left.every((message, index) => transcriptMessageKey(message) === transcriptMessageKey(right[index]));
}

function transcriptMessageKey(message) {
  return JSON.stringify(message ?? null);
}

function createTranscriptPage(messages, options = {}) {
  const visible = Array.isArray(messages)
    ? messages.filter((message) => VISIBLE_TRANSCRIPT_ROLES.has(String(message?.role ?? "")))
    : [];
  const limit = clampTranscriptPageLimit(options.limit);
  const end = transcriptCursorIndex(options.before, visible.length);
  const start = Math.max(0, end - limit);
  const pageMessages = visible.slice(start, end);
  return {
    messages: pageMessages,
    summary: {
      cursor: start > 0 ? String(start) : null,
      nextCursor: start > 0 ? String(start) : null,
      hasMore: start > 0,
      total: visible.length,
      returned: pageMessages.length,
      start,
      end
    }
  };
}

function clampTranscriptPageLimit(value) {
  const number = Number(value);
  if (!Number.isInteger(number) || number <= 0) {
    return DEFAULT_TRANSCRIPT_PAGE_LIMIT;
  }
  return Math.min(number, MAX_TRANSCRIPT_PAGE_LIMIT);
}

function transcriptCursorIndex(value, fallback) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  const number = Number(value);
  if (!Number.isInteger(number)) {
    return fallback;
  }
  return Math.max(0, Math.min(number, fallback));
}

function activeReplayCursor(state) {
  if (!state?.running || !state.currentTurnId) {
    return state?.eventSequence ?? 0;
  }
  const index = state.events.findIndex((event) => event.turnId === state.currentTurnId);
  return index > 0 ? nonNegativeInteger(state.events[index - 1].sequence) : 0;
}

function activeSessionRecord(state, persisted = null) {
  const modifiedAt = latestEventTime(state) ?? persisted?.modifiedAt ?? new Date().toISOString();
  return {
    id: state.session.id,
    title: state.session.title || persisted?.title || state.session.prompt || "未命名任务",
    status: activeDashboardStatus(state),
    model: state.session.model ?? persisted?.model ?? "",
    modifiedAt,
    finishedAt: persisted?.finishedAt ?? null,
    transcriptMessages: persisted?.transcriptMessages ?? activeTranscriptMessages(state).length,
    readable: persisted?.readable !== false,
    encrypted: persisted?.encrypted === true,
    active: true,
    running: state.running === true,
    queueLength: state.queuedPrompts.length
  };
}

function latestEventTime(state) {
  const latest = state.events.at(-1)?.at;
  return typeof latest === "string" ? latest : null;
}

function activeDashboardStatus(state) {
  if (state.running) {
    return state.queuedPrompts.some((item) => item.kind === "guide") ? "引导中" : "running";
  }
  return state.status || state.session.status || "active";
}

function compareSessionRecords(a, b) {
  return String(b.modifiedAt ?? "").localeCompare(String(a.modifiedAt ?? ""));
}

function messageContentText(content) {
  if (typeof content === "string") {
    return content;
  }
  if (!Array.isArray(content)) {
    return "";
  }
  return content.map((item) => {
    if (typeof item === "string") return item;
    if (item && typeof item === "object" && "text" in item) return String(item.text ?? "");
    return "";
  }).filter(Boolean).join("\n");
}

function beginPrompt(state, item, env) {
  applyPermissionMode(state.session, item.permissionMode);
  state.running = true;
  state.status = "running";
  state.currentPrompt = item.prompt;
  state.currentTurnId = eventId("turn");
  state.currentTranscriptStart = activeTranscriptMessages(state).length;
  state.currentPermissionMode = item.permissionMode;
  state.turnChangeStats = emptyChangeStats();
  state.controller = new AbortController();
  appendDashboardEvent(state, {
    type: "run_state",
    id: eventId("run-state"),
    running: true,
    turnId: state.currentTurnId,
    queue: queueSnapshot(state),
    current: publicQueueItem(item),
    sessionStatus: sessionStatusSummary(state.session),
    changeStats: { ...state.turnChangeStats },
    at: new Date().toISOString()
  });
  appendDashboardEvent(state, {
    type: "user_message",
    id: eventId("user"),
    text: item.kind === "guide" ? item.guidance : item.prompt,
    turnId: state.currentTurnId,
    queuedKind: item.kind,
    at: new Date().toISOString()
  });
  runTurnInBackground(state, item, env);
}

function runTurnInBackground(state, item, env) {
  const controller = state.controller;
  const eventStartIndex = state.events.length;
  queueMicrotask(async () => {
    try {
      const result = await runSessionTurn(state.session, {
        prompt: item.prompt,
        displayPrompt: item.kind === "guide" ? item.guidance : item.prompt,
        env,
        stream: true,
        signal: controller.signal,
        hooksTrusted: state.hooksTrusted,
        approvalCallback: (request) => askApproval(state, request),
        userInputCallback: (request) => askQuestion(state, request),
        onEvent: (event) => {
          for (const mapped of mapSessionEventToDashboard(event)) {
            mapped.turnId = state.currentTurnId;
            mapped.sessionStatus = sessionStatusSummary(state.session);
            if (mapped.type === "activity" && mapped.changeStats) {
              if (mapped.turnChangeStats) {
                state.turnChangeStats = normalizeChangeStats(mapped.turnChangeStats);
              } else {
                accumulateTurnChangeStats(state, mapped.changeStats);
                mapped.turnChangeStats = { ...state.turnChangeStats };
              }
            }
            appendDashboardEvent(state, mapped);
          }
          if (event.type === "tool_finish" && (event.name === "todo_write" || event.name === "plan_update")) {
            appendWorkflowSnapshot(state, event.name);
          }
          if (event.type === "workflow_updated") {
            appendWorkflowSnapshot(state, event.reason ?? "workflow_updated");
          }
        }
      });
      state.finalOutput = result.output ?? "";
      const turnEvents = state.events.slice(eventStartIndex);
      if (!result.interrupted && !turnEvents.some((event) => event.type === "assistant_final")) {
        appendDashboardEvent(state, {
          type: "assistant_final",
          id: eventId("assistant-final"),
          text: state.finalOutput,
          turnId: state.currentTurnId,
          at: new Date().toISOString()
        });
      }
      appendDashboardEvent(state, {
        type: "files_updated",
        id: eventId("files"),
        turnId: state.currentTurnId,
        files: collectSessionFiles(state.session, state.finalOutput),
        sessionStatus: sessionStatusSummary(state.session),
        changeStats: { ...state.turnChangeStats },
        at: new Date().toISOString()
      });
      state.status = result.interrupted ? "interrupted" : "completed";
    } catch (error) {
      appendDashboardEvent(state, {
        type: "error",
        id: eventId("error"),
        message: error instanceof Error ? error.message : String(error),
        at: new Date().toISOString()
      });
      state.status = "failed";
    } finally {
      if (state.controller === controller) {
        state.controller = null;
      }
      state.running = false;
      state.currentPrompt = "";
      const next = state.queuedPrompts.shift();
      if (next) {
        appendQueueUpdated(state);
        beginPrompt(state, next, env);
      } else {
        appendDashboardEvent(state, {
          type: "run_state",
          id: eventId("run-state"),
          running: false,
          turnId: state.currentTurnId,
          queue: queueSnapshot(state),
          sessionStatus: sessionStatusSummary(state.session),
          changeStats: { ...state.turnChangeStats },
          at: new Date().toISOString()
        });
        state.currentTurnId = "";
        state.currentTranscriptStart = activeTranscriptMessages(state).length;
      }
    }
  });
}

function requestTurnInterrupt(state, reason) {
  appendDashboardEvent(state, {
    type: "turn_interrupt_requested",
    id: eventId("interrupt"),
    reason,
    queue: queueSnapshot(state),
    at: new Date().toISOString()
  });
  cancelPendingInteractions(state, reason);
  if (state.controller && !state.controller.signal.aborted) {
    state.controller.abort(reason);
  }
}

function cancelPendingInteractions(state, reason) {
  for (const [approvalId, pending] of Array.from(state.pendingApprovals.entries())) {
    state.pendingApprovals.delete(approvalId);
    appendDashboardEvent(state, {
      type: "approval_resolved",
      id: eventId("approval-resolved"),
      approvalId,
      action: reason,
      allowed: false,
      interrupted: true,
      at: new Date().toISOString()
    });
    pending.resolve(false);
  }
  for (const [questionId, pending] of Array.from(state.pendingQuestions.entries())) {
    state.pendingQuestions.delete(questionId);
    const result = normalizeQuestionAnswer({ cancelled: true }, pending.question);
    appendDashboardEvent(state, {
      type: "question_resolved",
      id: eventId("question-resolved"),
      questionId,
      answer: result.answer,
      selectedChoice: result.selectedChoice,
      selectedChoices: result.selectedChoices,
      cancelled: true,
      interrupted: true,
      at: new Date().toISOString()
    });
    pending.resolve(result);
  }
}

function askQuestion(state, request) {
  const questionId = eventId("question");
  const payload = normalizeQuestionRequest(request, questionId);
  const promise = new Promise((resolve) => {
    state.pendingQuestions.set(questionId, { resolve, question: payload });
  });
  appendDashboardEvent(state, {
    type: "question_required",
    id: questionId,
    question: payload,
    at: payload.at
  });
  return promise;
}

function askApproval(state, request) {
  const approvalKey = approvalKeyFor(request);
  if (state.sessionApprovals.has(approvalKey)) {
    appendDashboardEvent(state, {
      type: "approval_auto_allowed",
      id: eventId("approval-auto"),
      title: "已按本会话批准继续",
      approvalKey,
      at: new Date().toISOString()
    });
    return true;
  }
  const approvalId = eventId("approval");
  const payload = {
    id: approvalId,
    toolName: request.toolName,
    risk: request.definition?.risk ?? "unknown",
    reason: request.decision?.reason ?? "需要确认后继续",
    sensitive: request.decision?.sensitive === true,
    outsideWorkspace: request.decision?.outsideWorkspace === true,
    preview: buildApprovalPreview(request),
    display: approvalDisplayMeta(request),
    input: sanitizeApprovalInput(request.input ?? {}),
    decision: request.decision ?? {},
    approvalKey,
    at: new Date().toISOString()
  };
  appendDashboardEvent(state, {
    type: "approval_required",
    id: approvalId,
    approval: payload,
    activity: permissionRequestToActivity(request),
    at: payload.at
  });
  return new Promise((resolve) => {
    state.pendingApprovals.set(approvalId, { resolve, approvalKey });
  });
}

function appendWorkflowSnapshot(state, reason) {
  const workflow = cloneWorkflowState(state.session.workflow);
  const hasItems = workflow.todos.length > 0 || workflow.plan.steps.length > 0;
  if (!hasItems) {
    return;
  }
  appendDashboardEvent(state, {
    type: "workflow_snapshot",
    id: eventId("workflow"),
    reason,
    workflow,
    summary: summarizeWorkflowSnapshot(workflow),
    at: new Date().toISOString()
  });
}

function summarizeWorkflowSnapshot(workflow) {
  const items = [...workflow.todos, ...(workflow.plan?.steps ?? [])];
  return {
    total: items.length,
    pending: items.filter((item) => item.status === "pending").length,
    in_progress: items.filter((item) => item.status === "in_progress").length,
    completed: items.filter((item) => item.status === "completed").length,
    cancelled: items.filter((item) => item.status === "cancelled").length
  };
}

function sessionStatusFromConfig(config) {
  const pseudoSession = {
    config,
    model: config.modelAlias,
    messages: [],
    contextWindow: null,
    usage: null
  };
  return sessionStatusSummary(pseudoSession);
}

function sessionStatusFromMetadata(metadata = {}) {
  return {
    model: metadata.model ?? "",
    context: metadata.context ?? null
  };
}

function sessionStatusSummary(session) {
  return {
    model: session?.model ?? session?.config?.modelAlias ?? "",
    context: summarizeContextWindow(session ?? {})
  };
}

function emptyChangeStats() {
  return {
    additions: 0,
    deletions: 0,
    files: 0,
    redacted: false,
    truncated: false,
    approximate: false
  };
}

function accumulateTurnChangeStats(state, stats) {
  if (!stats || typeof stats !== "object") {
    return;
  }
  state.turnChangeStats ??= emptyChangeStats();
  state.turnChangeStats.additions += nonNegativeInteger(stats.additions);
  state.turnChangeStats.deletions += nonNegativeInteger(stats.deletions);
  state.turnChangeStats.files += Math.max(0, nonNegativeInteger(stats.files));
  state.turnChangeStats.redacted ||= stats.redacted === true;
  state.turnChangeStats.truncated ||= stats.truncated === true;
  state.turnChangeStats.approximate ||= stats.approximate === true;
}

function normalizeChangeStats(stats) {
  return {
    additions: nonNegativeInteger(stats?.additions),
    deletions: nonNegativeInteger(stats?.deletions),
    files: nonNegativeInteger(stats?.files),
    redacted: stats?.redacted === true,
    truncated: stats?.truncated === true,
    approximate: stats?.approximate === true
  };
}

function nonNegativeInteger(value) {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : 0;
}

function enqueuePrompt(state, prompt, permissionMode, kind) {
  const item = createQueueItem(prompt, permissionMode, kind);
  state.queuedPrompts.push(item);
  state.queuedPrompts = state.queuedPrompts.slice(0, MAX_QUEUE);
  return item;
}

function createQueueItem(prompt, permissionMode = "plan", kind = "prompt", guidance = "") {
  const text = String(prompt ?? "").trim();
  return {
    id: eventId("queue"),
    prompt: text,
    permissionMode: normalizePermissionMode(permissionMode),
    kind,
    guidance: String(guidance || text).trim(),
    at: new Date().toISOString()
  };
}

function appendQueueUpdated(state) {
  appendDashboardEvent(state, {
    type: "queue_updated",
    id: eventId("queue-updated"),
    turnId: state.currentTurnId || null,
    queue: queueSnapshot(state),
    queueLength: state.queuedPrompts.length,
    running: state.running,
    sessionStatus: sessionStatusSummary(state.session),
    changeStats: { ...state.turnChangeStats },
    at: new Date().toISOString()
  });
}

function queueSnapshot(state) {
  return state.queuedPrompts.map(publicQueueItem);
}

function publicQueueItem(item) {
  return {
    id: item.id,
    kind: item.kind,
    preview: previewText(item.kind === "guide" ? item.guidance : item.prompt),
    permissionMode: item.permissionMode,
    at: item.at
  };
}

function previewText(value, max = 120) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  return text.length <= max ? text : `${text.slice(0, max - 3)}...`;
}

function buildGuidePrompt(guidance, activePrompt = "") {
  const text = String(guidance ?? "").trim();
  const original = String(activePrompt ?? "").trim();
  const lines = [
    "User guidance for the interrupted active turn:",
    text,
    "",
    "Continue the task using this guidance. If partial work from the interrupted turn is already visible, avoid repeating it unless needed."
  ];
  if (original && !includesPromptContext(text, original)) {
    lines.push("", "Original active prompt:", original);
  }
  return lines.join("\n");
}

function includesPromptContext(text, original) {
  if (!text || !original) {
    return false;
  }
  return normalizeGuideText(text).includes(normalizeGuideText(original));
}

function normalizeGuideText(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim().toLowerCase();
}

function isStopGuidance(guidance) {
  const normalized = String(guidance ?? "")
    .trim()
    .toLowerCase()
    .replace(/[。.!！\s]+$/g, "");
  return /^(停止|停下|取消|中止|终止|abort|cancel|stop)(当前(任务|轮次|请求))?$/.test(normalized);
}

function appendDashboardEvent(state, event) {
  state.eventSequence += 1;
  const normalized = {
    at: new Date().toISOString(),
    id: event.id ?? eventId(event.type ?? "event"),
    sequence: state.eventSequence,
    ...event
  };
  if ((normalized.status === "running" || normalized.status === "waiting") && normalized.coalesceKey) {
    const existingIndex = state.events.findIndex((item) =>
      item.type === "activity"
      && item.coalesceKey === normalized.coalesceKey
      && (item.status === "running" || item.status === "waiting")
    );
    if (existingIndex >= 0) {
      state.events[existingIndex] = normalized;
      for (const listener of state.listeners) {
        listener(normalized);
      }
      return;
    }
  }
  state.events.push(normalized);
  if (state.events.length > MAX_EVENTS) {
    state.events.splice(0, state.events.length - MAX_EVENTS);
  }
  for (const listener of state.listeners) {
    listener(normalized);
  }
}

async function resolveDashboardTrust(options) {
  const config = await loadConfig({ cwd: options.cwd, env: options.env });
  const trust = await resolveWorkspaceTrust({
    cwd: options.cwd,
    env: options.env,
    sensitivity: config.security?.sensitivity
  });
  return {
    trusted: options.processTrusted === true || trust.trusted === true,
    persisted: Boolean(trust.record),
    requiresPerProcessConfirmation: trust.requiresPerProcessConfirmation === true,
    sensitivity: config.security?.sensitivity ?? "standard",
    displayPath: trust.displayPath,
    storePath: trust.storePath,
    workspaceId: trust.workspaceId,
    record: trust.record
  };
}

function sanitizeApprovalInput(input) {
  const sanitized = {};
  for (const [key, value] of Object.entries(input)) {
    if (/token|api[_-]?key|secret|password|authorization|credential/i.test(key)) {
      sanitized[key] = "[redacted]";
    } else if (typeof value === "string") {
      sanitized[key] = value.length > 500 ? `${value.slice(0, 497)}...` : value;
    } else {
      sanitized[key] = value;
    }
  }
  return sanitized;
}

function normalizeQuestionRequest(request, id) {
  const choices = Array.isArray(request?.choices)
    ? request.choices.map(normalizeQuestionChoice).filter(Boolean)
    : [];
  return {
    id,
    header: String(request?.header ?? "需求核对"),
    question: String(request?.question ?? request?.prompt ?? "请确认需求"),
    choices,
    multiple: Boolean(request?.multiple || request?.selectionMode === "multi"),
    allowCustom: choices.length === 0 || request?.allowCustom !== false,
    confirmLabel: String(request?.confirmLabel ?? "确认"),
    at: new Date().toISOString()
  };
}

function normalizeQuestionChoice(choice) {
  if (typeof choice === "string") {
    const label = choice.trim();
    return label ? { label, value: label, selected: false } : null;
  }
  if (!choice || typeof choice !== "object") {
    return null;
  }
  const label = String(choice.label ?? choice.text ?? choice.value ?? "").trim();
  if (!label) {
    return null;
  }
  return {
    label,
    value: String(choice.value ?? label),
    description: typeof choice.description === "string" ? choice.description : "",
    selected: choice.selected === true
  };
}

function normalizeQuestionAnswer(answer, question) {
  const choices = Array.isArray(question?.choices) ? question.choices : [];
  const cancelled = answer?.cancelled === true;
  if (cancelled) {
    return {
      answer: "",
      selectedChoice: null,
      selectedChoices: [],
      customAnswer: null,
      cancelled: true,
      workflowReminder: null
    };
  }
  const selectedValues = Array.isArray(answer?.selectedChoices)
    ? answer.selectedChoices.map(String)
    : typeof answer?.selectedChoice === "string"
      ? [answer.selectedChoice]
      : [];
  const selectedChoices = selectedValues
    .map((value) => choices.find((choice) => choice.value === value || choice.label === value)?.label ?? value)
    .filter(Boolean);
  const customAnswer = String(answer?.customAnswer ?? answer?.answer ?? "").trim();
  const resolvedAnswer = customAnswer || selectedChoices.join(", ");
  return {
    answer: resolvedAnswer,
    selectedChoice: selectedChoices[0] ?? null,
    selectedChoices,
    customAnswer: customAnswer || null,
    cancelled: false,
    workflowReminder: choices.length > 0
      ? "If this confirmation starts multi-step work, update the visible workflow state with todo_write and/or plan_update. Before the final response, mark completed visible items as completed."
      : null
  };
}

function eventId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
