import { renderMarkdown } from "./markdown.js";
import { hydrateRichContent } from "./rich-renderers.js";
import { visibleTranscriptRole } from "./transcript.js";

const state = {
  cwd: "",
  sessions: [],
  currentSessionId: null,
  eventSource: null,
  eventSourceSessionId: null,
  lastEventSequence: 0,
  permissionMode: "plan",
  pendingApproval: null,
  pendingQuestion: null,
  trust: null,
  queue: [],
  queueCancelling: new Set(),
  sessionsLoading: false,
  sessionsStatusTimer: null,
  deletingSessions: new Set(),
  deleteConfirmSessionId: "",
  files: [],
  liveTitle: "",
  liveActivities: new Map(),
  backgroundSubagents: new Map(),
  completedActivities: [],
  running: false,
  pendingGuide: null,
  guideSubmitting: false,
  workflow: null,
  workflowNode: null,
  workflowExpanded: false,
  assistantDrafts: new Map(),
  transcriptPaging: {
    cursor: null,
    hasMore: false,
    loading: false,
    error: "",
    total: 0
  },
  transcriptHistoryNode: null,
  activeTurnId: "",
  processedEventIds: new Set(),
  lastAssistantFinalSignature: "",
  sessionStatus: null,
  turnChangeStats: { additions: 0, deletions: 0, files: 0, redacted: false, truncated: false, approximate: false },
  lightboxItems: [],
  lightboxIndex: 0
};

const els = {
  projectPath: document.querySelector("#project-path"),
  threadList: document.querySelector("#thread-list"),
  refreshSessions: document.querySelector("#refresh-sessions"),
  sessionsStatus: document.querySelector("#sessions-status"),
  newTask: document.querySelector("#new-task"),
  runStatus: document.querySelector("#run-status"),
  workflowStrip: document.querySelector("#workflow-strip"),
  transcript: document.querySelector("#transcript"),
  emptyState: document.querySelector("#empty-state"),
  promptInput: document.querySelector("#prompt-input"),
  sendButton: document.querySelector("#send-button"),
  permissionMode: document.querySelector("#permission-mode"),
  modeDescription: document.querySelector("#mode-description"),
  liveStatus: document.querySelector("#live-status"),
  liveTitle: document.querySelector("#live-title"),
  liveSubtasks: document.querySelector("#live-subtasks"),
  approvalPanel: document.querySelector("#approval-panel"),
  questionPanel: document.querySelector("#question-panel"),
  fileList: document.querySelector("#file-list"),
  previewBody: document.querySelector("#preview-body"),
  imageLightbox: document.querySelector("#image-lightbox"),
  lightboxBackdrop: document.querySelector("#lightbox-backdrop"),
  lightboxClose: document.querySelector("#lightbox-close"),
  lightboxPrevious: document.querySelector("#lightbox-previous"),
  lightboxNext: document.querySelector("#lightbox-next"),
  lightboxImage: document.querySelector("#lightbox-image"),
  lightboxTitle: document.querySelector("#lightbox-title"),
  lightboxCounter: document.querySelector("#lightbox-counter"),
  lightboxOpen: document.querySelector("#lightbox-open"),
  collapsePreview: document.querySelector("#collapse-preview"),
  shutdownButton: document.querySelector("#shutdown-button"),
  headerShutdownButton: document.querySelector("#header-shutdown-button"),
  shutdownPanel: document.querySelector("#shutdown-panel"),
  shutdownCancel: document.querySelector("#shutdown-cancel"),
  shutdownConfirm: document.querySelector("#shutdown-confirm"),
  trustPanel: document.querySelector("#trust-panel"),
  queuePanel: document.querySelector("#queue-panel"),
  contextPanel: document.querySelector("#context-panel"),
  contextClear: document.querySelector("#context-clear"),
  contextCompact: document.querySelector("#context-compact"),
  modelStatus: document.querySelector("#model-status"),
  contextStatus: document.querySelector("#context-status"),
  changeStatus: document.querySelector("#change-status")
};

const MODE_DESCRIPTIONS = {
  plan: "写入、命令和外部能力需要确认后执行",
  workspace: "工作区内非敏感读写和常规本地命令自动同意",
  fullAccess: "测试机模式，所有本地工具、MCP、浏览器、网络和任意路径操作自动同意"
};
const LOCAL_FILE_EXTENSIONS = new Set([
  "png", "jpg", "jpeg", "gif", "webp", "svg",
  "pdf",
  "md", "markdown", "txt", "log",
  "json", "csv", "tsv", "yaml", "yml",
  "js", "mjs", "cjs", "ts", "tsx", "jsx", "css", "html", "xml",
  "py", "ps1", "cmd", "sh", "java", "c", "cpp", "h", "hpp", "cs", "go", "rs", "php", "rb", "sql", "toml", "ini",
  "doc", "docx", "xls", "xlsx", "ppt", "pptx"
]);
const FILE_REFERENCE_PATTERN = /(?:[A-Za-z0-9_.-]+[\\/])*[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,8}(?::\d+)?/g;
const DRAFT_RENDER_INTERVAL_MS = 180;

await init();

async function init() {
  bindEvents();
  observeRunStatus();
  const status = await getJson("/api/status");
  state.cwd = status.cwd;
  updateSessionStatus(status.sessionStatus);
  els.projectPath.textContent = status.cwd;
  await loadTrust();
  await loadSessions();
  updateSendButton();
  renderComposerStatus();
}

function observeRunStatus() {
  updateRunStatusTone();
  new MutationObserver(updateRunStatusTone).observe(els.runStatus, { childList: true, characterData: true, subtree: true });
}

function updateRunStatusTone() {
  const status = els.runStatus.textContent.trim();
  let tone = "idle";
  if (/失败|拒绝/.test(status)) {
    tone = "error";
  } else if (/等待|待/.test(status)) {
    tone = "waiting";
  } else if (/运行|启动|引导|中断|停止|收尾|排队/.test(status)) {
    tone = "running";
  } else if (/完成/.test(status)) {
    tone = "done";
  }
  els.runStatus.dataset.tone = tone;
}

function bindEvents() {
  els.refreshSessions.addEventListener("click", () => loadSessions({ feedback: true }));
  els.newTask.addEventListener("click", newTask);
  els.sendButton.addEventListener("click", () => {
    if (state.running) {
      interruptTurn();
      return;
    }
    sendPrompt();
  });
  els.promptInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      sendPrompt();
    }
  });
  els.promptInput.addEventListener("input", syncGuideButton);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      hideImageLightbox();
    } else if (event.key === "ArrowLeft") {
      moveLightbox(-1);
    } else if (event.key === "ArrowRight") {
      moveLightbox(1);
    }
  });
  els.permissionMode.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-mode]");
    if (!button) return;
    setPermissionMode(button.dataset.mode);
  });
  els.collapsePreview.addEventListener("click", () => {
    document.body.classList.toggle("preview-collapsed");
  });
  els.shutdownButton.addEventListener("click", showShutdownPanel);
  els.headerShutdownButton.addEventListener("click", showShutdownPanel);
  els.shutdownCancel.addEventListener("click", hideShutdownPanel);
  els.shutdownConfirm.addEventListener("click", shutdownDashboard);
  els.lightboxBackdrop.addEventListener("click", hideImageLightbox);
  els.lightboxClose.addEventListener("click", hideImageLightbox);
  els.lightboxPrevious.addEventListener("click", () => moveLightbox(-1));
  els.lightboxNext.addEventListener("click", () => moveLightbox(1));
  els.contextClear.addEventListener("click", () => showContextConfirm("clear"));
  els.contextCompact.addEventListener("click", () => showContextConfirm("compact"));
  els.transcript.addEventListener("scroll", handleTranscriptScroll);
  els.workflowStrip.addEventListener("click", (event) => {
    if (!event.target.closest("button[data-action='toggle-workflow']")) {
      return;
    }
    state.workflowExpanded = !state.workflowExpanded;
    renderWorkflowStrip();
  });
}

async function loadTrust() {
  const result = await getJson("/api/trust").catch((error) => ({ ok: false, error: error.message }));
  if (!result.ok) {
    showError(result.error ?? "无法读取工作区信任状态");
    return;
  }
  state.trust = result.trust;
  renderTrustPanel();
}

async function loadSessions(options = {}) {
  const feedback = options.feedback === true;
  if (feedback) {
    setSessionsRefreshState("loading", "刷新中");
  }
  try {
    const result = await getJson("/api/sessions");
    state.sessions = result.sessions ?? [];
    renderSessions();
    if (feedback) {
      setSessionsRefreshState("success", `已刷新 ${state.sessions.length} 个会话`);
    }
  } catch (error) {
    if (feedback) {
      setSessionsRefreshState("error", "刷新失败");
    }
    showError(error.message ?? "刷新会话失败");
  }
}

function renderSessions() {
  els.threadList.innerHTML = "";
  if (state.sessions.length === 0) {
    const empty = document.createElement("div");
    empty.className = "thread-meta";
    empty.textContent = "暂无历史任务";
    els.threadList.append(empty);
    return;
  }
  for (const session of state.sessions) {
    const item = document.createElement("div");
    item.className = `thread-item${session.id === state.currentSessionId ? " active" : ""}`;
    item.innerHTML = `
      <button type="button" class="thread-open">
        <div class="thread-title">${escapeHtml(session.title || "未命名任务")}</div>
        <div class="thread-meta">${escapeHtml(sessionMeta(session))}</div>
      </button>
      ${state.deleteConfirmSessionId === session.id
        ? `
          <div class="thread-delete-confirm">
            <div class="thread-delete-title">确认删除这个会话？</div>
            <div class="thread-delete-copy">历史记录和 transcript 分片会被删除，操作不可撤销。</div>
            <div class="thread-actions">
              <button type="button" class="thread-action" data-action="cancel-delete" data-session-id="${escapeHtml(session.id)}">保留</button>
              <button type="button" class="thread-action danger strong" data-action="confirm-delete" data-session-id="${escapeHtml(session.id)}" ${state.deletingSessions.has(session.id) ? "disabled" : ""}>确认删除</button>
            </div>
          </div>
        `
        : `
          <div class="thread-actions">
            <button type="button" class="thread-action" data-action="copy-id" data-session-id="${escapeHtml(session.id)}" title="复制会话 ID">复制 ID</button>
            <button type="button" class="thread-action danger" data-action="delete" data-session-id="${escapeHtml(session.id)}" ${session.running ? "disabled" : ""} title="${session.running ? "会话运行中，结束后可删除" : "删除会话"}">删除</button>
          </div>
        `}
    `;
    item.querySelector(".thread-open").addEventListener("click", () => openSession(session.id));
    item.querySelectorAll("button[data-action]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        handleSessionAction(button.dataset.action, button.dataset.sessionId);
      });
    });
    els.threadList.append(item);
  }
}

function sessionMeta(session) {
  const parts = [
    session.running ? "运行中" : session.status || "unknown",
    session.queueLength > 0 ? `${session.queueLength} 排队` : null,
    formatTime(session.modifiedAt)
  ].filter(Boolean);
  return parts.join(" · ");
}

function handleSessionAction(action, sessionId) {
  if (!sessionId) {
    return;
  }
  if (action === "delete") {
    state.deleteConfirmSessionId = sessionId;
    renderSessions();
    return;
  }
  if (action === "cancel-delete") {
    state.deleteConfirmSessionId = "";
    renderSessions();
    return;
  }
  if (action === "confirm-delete") {
    deleteSession(sessionId);
    return;
  }
  if (action === "copy-id") {
    copySessionId(sessionId);
  }
}

async function openSession(id) {
  const result = await getJson(`/api/sessions/${encodeURIComponent(id)}`);
  if (!result.ok) {
    showError(result.error?.message ?? result.error ?? "无法读取会话");
    return;
  }
  state.currentSessionId = id;
  disconnectEvents();
  hideApproval();
  hideQuestion();
  hideContextConfirm();
  clearTranscript();
  resetLiveStatus();
  state.queue = [];
  state.queueCancelling.clear();
  clearPendingGuide();
  state.activeTurnId = "";
  resetEventReplayState();
  state.deleteConfirmSessionId = "";
  renderQueuePanel();
  updateSessionStatus(result.session.sessionStatus ?? { model: result.session.model, context: result.session.context });
  resetTurnChangeStats();
  state.files = result.session.files ?? [];
  renderFiles();
  resetPreview();
  els.runStatus.textContent = result.session.status || "历史";
  setTranscriptPaging(result.session.transcriptPage);
  renderTranscriptMessages(result.session.transcript ?? []);
  scrollTranscript({ force: true });
  if (result.session.active && result.session.running) {
    rememberEventCursor(result.session.eventCursor);
    ensureEventsConnected(id);
    els.runStatus.textContent = result.session.status === "引导中" ? "引导中" : "运行中";
    setLiveTitle(result.session.status === "引导中" ? "正在按引导继续" : "正在恢复运行中的任务");
    state.running = true;
    updateSendButton();
  }
  renderSessions();
}

async function deleteSession(sessionId) {
  if (!sessionId || state.deletingSessions.has(sessionId)) {
    return;
  }
  state.deletingSessions.add(sessionId);
  renderSessions();
  const result = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE"
  }).then((response) => response.json()).catch((error) => ({ ok: false, error: error.message }));
  state.deletingSessions.delete(sessionId);
  state.deleteConfirmSessionId = "";
  if (!result.ok) {
    showError(result.error ?? "删除会话失败");
    renderSessions();
    return;
  }
  if (state.currentSessionId === sessionId) {
    newTask();
  }
  await loadSessions();
}

function setSessionsRefreshState(tone, message = "") {
  if (state.sessionsStatusTimer) {
    clearTimeout(state.sessionsStatusTimer);
    state.sessionsStatusTimer = null;
  }
  state.sessionsLoading = tone === "loading";
  els.refreshSessions.disabled = state.sessionsLoading;
  els.refreshSessions.dataset.state = tone;
  els.refreshSessions.textContent = tone === "success" ? "✓" : tone === "error" ? "!" : "↻";
  els.refreshSessions.title = message || "刷新";
  if (els.sessionsStatus) {
    els.sessionsStatus.textContent = message;
    els.sessionsStatus.dataset.tone = tone;
  }
  if (tone === "success" || tone === "error") {
    state.sessionsStatusTimer = setTimeout(() => {
      els.refreshSessions.dataset.state = "idle";
      els.refreshSessions.textContent = "↻";
      els.refreshSessions.title = "刷新";
      if (els.sessionsStatus) {
        els.sessionsStatus.textContent = "";
        els.sessionsStatus.dataset.tone = "idle";
      }
      state.sessionsStatusTimer = null;
    }, 1800);
  }
}

async function copySessionId(sessionId) {
  try {
    await navigator.clipboard.writeText(sessionId);
    appendActivity({
      title: "会话 ID 已复制",
      detail: sessionId,
      severity: "success",
      collapsed: true
    });
  } catch {
    showError("复制会话 ID 失败");
  }
}

function newTask() {
  state.currentSessionId = null;
  disconnectEvents();
  hideApproval();
  hideQuestion();
  hideContextConfirm();
  clearTranscript();
  state.files = [];
  state.queue = [];
  state.queueCancelling.clear();
  state.completedActivities = [];
  clearPendingGuide();
  state.activeTurnId = "";
  resetEventReplayState();
  state.deleteConfirmSessionId = "";
  resetLiveStatus();
  resetTurnChangeStats();
  renderQueuePanel();
  renderFiles();
  resetPreview();
  els.runStatus.textContent = "空闲";
  els.promptInput.focus();
}

async function sendPrompt() {
  const prompt = els.promptInput.value.trim();
  if (!prompt) {
    return;
  }
  if (!state.trust?.trusted) {
    showTrustPanel();
    return;
  }
  els.sendButton.disabled = true;
  els.runStatus.textContent = state.running ? "已排队" : "启动中";
  const result = await postJson("/api/turns", {
    prompt,
    sessionId: state.currentSessionId,
    permissionMode: state.permissionMode
  }).catch((error) => ({ ok: false, error: error.message }));
  els.sendButton.disabled = false;
  if (!result.ok) {
    if (result.trust) {
      state.trust = result.trust;
      renderTrustPanel();
    }
    showError(result.error ?? "任务启动失败");
    els.runStatus.textContent = result.status === 403 ? "待信任" : "失败";
    updateSendButton();
    return;
  }
  els.promptInput.value = "";
  state.queue = result.queue ?? state.queue;
  updateSessionStatus(result.sessionStatus);
  updateTurnChangeStats(result.changeStats, { replace: true });
  renderQueuePanel();
  updateSendButton();
  const previousSessionId = state.currentSessionId;
  state.currentSessionId = result.sessionId;
  if (previousSessionId !== result.sessionId) {
    resetEventReplayState();
  }
  rememberEventCursor(result.eventCursor);
  ensureEventsConnected(result.sessionId);
  await loadSessions();
}

async function interruptTurn() {
  if (!state.currentSessionId) {
    return;
  }
  els.sendButton.disabled = true;
  els.sendButton.textContent = "中断中";
  const result = await postJson("/api/turns/interrupt", {
    sessionId: state.currentSessionId,
    reason: "user"
  }).catch((error) => ({ ok: false, error: error.message }));
  els.sendButton.disabled = false;
  if (!result.ok) {
    showError(result.error ?? "中断失败");
  }
  updateSessionStatus(result.sessionStatus);
  updateSendButton();
}

async function guideTurn(queueItemId = "") {
  const source = guideSource(queueItemId);
  if (!source || !state.currentSessionId || !state.running || state.guideSubmitting) {
    return;
  }
  const clientId = `guide-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  state.guideSubmitting = true;
  setPendingGuide({
    clientId,
    sessionId: state.currentSessionId,
    phase: "registering",
    preview: source.preview
  });
  hideApproval();
  hideQuestion();
  els.runStatus.textContent = "引导中";
  setLiveTitle("正在登记引导");
  const result = await postJson("/api/turns/guide", {
    sessionId: state.currentSessionId,
    guidance: source.guidance,
    queueItemId: source.queueItemId,
    permissionMode: state.permissionMode
  }).catch((error) => ({ ok: false, error: error.message }));
  state.guideSubmitting = false;
  if (!result.ok) {
    if (state.pendingGuide?.clientId === clientId) {
      clearPendingGuide();
    } else {
      renderQueuePanel();
    }
    showError(result.error ?? "引导失败");
    return;
  }
  els.promptInput.value = "";
  state.queue = result.queue ?? state.queue;
  updateSessionStatus(result.sessionStatus);
  hideApproval();
  hideQuestion();
  setPendingGuide({
    clientId,
    sessionId: state.currentSessionId,
    phase: result.stopped ? "stopped" : "registered",
    preview: source.preview
  });
  syncGuideButton();
}

async function cancelQueuedTurn(queueItemId) {
  if (!queueItemId || !state.currentSessionId || state.queueCancelling.has(queueItemId)) {
    return;
  }
  state.queueCancelling.add(queueItemId);
  renderQueuePanel();
  const result = await postJson("/api/turns/queue/cancel", {
    sessionId: state.currentSessionId,
    queueItemId
  }).catch((error) => ({ ok: false, error: error.message }));
  state.queueCancelling.delete(queueItemId);
  if (!result.ok) {
    showError(result.error ?? "取消排队失败");
    renderQueuePanel();
    return;
  }
  state.queue = result.queue ?? state.queue.filter((item) => item.id !== queueItemId);
  updateSessionStatus(result.sessionStatus);
  if (result.item?.kind === "guide" && state.pendingGuide?.phase !== "continuing") {
    clearPendingGuide();
  } else {
    renderQueuePanel();
  }
  syncGuideButton();
}

function connectEvents(sessionId) {
  disconnectEvents();
  state.eventSourceSessionId = sessionId;
  const params = new URLSearchParams({ sessionId });
  if (state.lastEventSequence > 0) {
    params.set("after", String(state.lastEventSequence));
  }
  state.eventSource = new EventSource(`/api/events?${params.toString()}`);
  state.eventSource.addEventListener("dashboard", (event) => {
    const payload = JSON.parse(event.data);
    if (shouldSkipDashboardEvent(payload)) {
      return;
    }
    rememberEventCursor(payload.sequence);
    handleDashboardEvent(payload);
  });
}

function ensureEventsConnected(sessionId) {
  if (state.eventSource && state.eventSourceSessionId === sessionId) {
    return;
  }
  connectEvents(sessionId);
}

function disconnectEvents() {
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
  state.eventSourceSessionId = null;
}

function resetEventReplayState() {
  state.lastEventSequence = 0;
  state.processedEventIds.clear();
}

function rememberEventCursor(value) {
  const sequence = Number(value);
  if (Number.isInteger(sequence) && sequence > state.lastEventSequence) {
    state.lastEventSequence = sequence;
  }
}

function handleDashboardEvent(event) {
  hideEmptyState();
  updateSessionStatus(event.sessionStatus);
  updateTurnChangeStats(event.turnChangeStats ?? event.changeStats, {
    replace: event.type === "run_state" || event.type === "files_updated" || Boolean(event.turnChangeStats)
  });
  if (event.type === "user_message") {
    beginEventTurn(event);
    updateTurnChangeStats(null, { reset: true });
    state.lastAssistantFinalSignature = "";
    appendMessage("user", event.queuedKind === "guide" ? "引导" : event.queuedKind === "wakeup" ? "子智能体" : "你", event.text);
    state.running = true;
    if (event.queuedKind === "guide") {
      els.runStatus.textContent = "引导中";
      setPendingGuide({
        sessionId: state.currentSessionId,
        phase: "continuing",
        preview: event.text
      });
      setLiveTitle("正在按引导继续");
    } else {
      els.runStatus.textContent = "运行中";
      setLiveTitle("正在处理你的任务");
    }
    updateSendButton();
    return;
  }
  if (event.type === "run_state") {
    if (event.running === true) {
      beginEventTurn(event);
    } else if (event.running === false && event.turnId === state.activeTurnId) {
      state.activeTurnId = "";
    }
    state.running = event.running === true;
    state.queue = event.queue ?? [];
    if (state.running && event.current?.kind === "guide") {
      setPendingGuide({
        sessionId: state.currentSessionId,
        phase: "continuing",
        preview: event.current.preview ?? state.pendingGuide?.preview ?? ""
      });
      els.runStatus.textContent = "引导中";
      setLiveTitle("正在按引导继续");
    } else if (!state.running) {
      clearPendingGuide();
      if (state.backgroundSubagents.size > 0) {
        els.runStatus.textContent = "等待子智能体唤醒";
        state.liveActivities.clear();
        updateLiveStatus();
      } else {
        els.runStatus.textContent = "空闲";
        resetLiveStatus();
      }
    } else {
      els.runStatus.textContent = "运行中";
      renderQueuePanel();
    }
    updateSendButton();
    return;
  }
  if (event.type === "guide_queued") {
    state.queue = event.queue ?? [];
    setPendingGuide({
      sessionId: state.currentSessionId,
      phase: "registered",
      preview: event.guidance ?? event.item?.preview ?? state.pendingGuide?.preview ?? ""
    });
    els.runStatus.textContent = "引导中";
    return;
  }
  if (event.type === "prompt_queued" || event.type === "queue_updated") {
    state.queue = event.queue ?? [];
    syncPendingGuideFromQueue();
    els.runStatus.textContent = state.pendingGuide ? "引导中" : state.running ? "运行中" : "已排队";
    return;
  }
  if (event.type === "wakeup_queued") {
    state.queue = event.queue ?? state.queue;
    clearBackgroundSubagentStatus(event.groupId);
    renderQueuePanel();
    els.runStatus.textContent = event.running ? "主控续跑已排队" : "主控接续中";
    setLiveTitle("子智能体已唤醒主控");
    updateSendButton();
    return;
  }
  if (event.type === "queue_item_cancelled") {
    state.queue = event.queue ?? [];
    state.queueCancelling.delete(event.item?.id);
    updateSessionStatus(event.sessionStatus);
    if (event.item?.kind === "guide" && state.pendingGuide?.phase !== "continuing") {
      clearPendingGuide();
    } else {
      renderQueuePanel();
    }
    els.runStatus.textContent = state.queue.length > 0 ? `${state.queue.length} 条排队中` : state.running ? "运行中" : "空闲";
    return;
  }
  if (event.type === "turn_interrupt_requested") {
    if (event.reason === "guided") {
      hideApproval();
      hideQuestion();
      setPendingGuide({
        sessionId: state.currentSessionId,
        phase: "interrupting",
        preview: state.pendingGuide?.preview ?? state.queue.find((item) => item.kind === "guide")?.preview ?? ""
      });
      els.runStatus.textContent = "引导中";
      setLiveTitle("引导已接管，等待当前轮次收束");
    } else {
      els.runStatus.textContent = "中断中";
      setLiveTitle("正在中断当前任务");
    }
    return;
  }
  if (event.type === "guide_stopped") {
    state.queue = event.queue ?? [];
    setPendingGuide({
      sessionId: state.currentSessionId,
      phase: "stopped",
      preview: event.guidance ?? ""
    });
    els.runStatus.textContent = "停止中";
    setLiveTitle("正在停止当前任务");
    return;
  }
  if (event.type === "context_cleared") {
    hideContextConfirm();
    appendActivity({
      title: "上下文已清空",
      detail: contextSummaryLine(event.after),
      severity: "success",
      collapsed: true
    });
    return;
  }
  if (event.type === "activity") {
    if (event.rawType === "turn_interrupted") {
      collapseAssistantDrafts();
    }
    if (isBackgroundSubagentActivity(event)) {
      handleBackgroundSubagentActivity(event);
      return;
    }
    handleActivity(event);
    if (event.status === "waiting") els.runStatus.textContent = "等待确认";
    else if (event.status === "running") els.runStatus.textContent = state.pendingGuide ? "引导中" : "运行中";
    else if (event.status === "failed") els.runStatus.textContent = "失败";
    return;
  }
  if (event.type === "workflow_snapshot") {
    renderWorkflowPanel(event.workflow, event.summary);
    return;
  }
  if (event.type === "assistant_draft") {
    beginEventTurn(event);
    appendAssistantDraft(event);
    els.runStatus.textContent = state.pendingGuide ? "引导中" : "运行中";
    state.running = true;
    updateSendButton();
    return;
  }
  if (event.type === "approval_required") {
    if (event.activity) handleActivity(event.activity);
    showApproval(event.approval);
    els.runStatus.textContent = "等待确认";
    setLiveTitle("等待权限确认");
    return;
  }
  if (event.type === "question_required") {
    showQuestion(event.question);
    els.runStatus.textContent = "等待核对";
    setLiveTitle("等待需求核对");
    return;
  }
  if (event.type === "question_resolved") {
    hideQuestion();
    if (event.interrupted && state.pendingGuide) {
      els.runStatus.textContent = "引导中";
      setLiveTitle("引导已接管，等待当前轮次收束");
      updateSendButton();
      return;
    }
    appendMessage("user", "你", questionResolutionText(event));
    els.runStatus.textContent = "运行中";
    state.running = true;
    updateSendButton();
    setLiveTitle(event.cancelled ? "继续处理需求核对结果" : "继续处理你的确认");
    return;
  }
  if (event.type === "approval_resolved") {
    hideApproval();
    if (event.interrupted && state.pendingGuide) {
      els.runStatus.textContent = "引导中";
      setLiveTitle("引导已接管，等待当前轮次收束");
      updateSendButton();
      return;
    }
    els.runStatus.textContent = event.allowed ? "运行中" : "已拒绝";
    if (!event.allowed) {
      resetLiveStatus();
    }
    return;
  }
  if (event.type === "assistant_final") {
    beginEventTurn(event);
    const finalSignature = normalizeComparableText(event.text);
    if (finalSignature && state.lastAssistantFinalSignature === finalSignature) {
      clearAssistantDrafts();
      return;
    }
    state.lastAssistantFinalSignature = finalSignature;
    collapseAssistantDrafts(event.text);
    collapseCompletedActivities();
    if (state.backgroundSubagents.size > 0) {
      state.running = false;
      state.liveActivities.clear();
      updateLiveStatus();
    } else {
      resetLiveStatus();
    }
    clearPendingGuide();
    appendMessage("assistant", "Ant Code", event.text);
    state.activeTurnId = "";
    els.runStatus.textContent = state.backgroundSubagents.size > 0 ? "等待子智能体唤醒" : "收尾中";
    updateSendButton();
    return;
  }
  if (event.type === "files_updated") {
    state.files = event.files ?? [];
    renderFiles();
    if (shouldKeepGuideFeedback()) {
      els.runStatus.textContent = "引导中";
      updateLiveStatus();
    } else {
      if (state.backgroundSubagents.size > 0) {
        els.runStatus.textContent = "等待子智能体唤醒";
        state.running = false;
        state.liveActivities.clear();
        updateLiveStatus();
      } else {
        els.runStatus.textContent = "完成";
        resetLiveStatus();
      }
      clearPendingGuide();
    }
    updateSendButton();
    loadSessions();
    return;
  }
  if (event.type === "error") {
    if (state.pendingGuide && isInterruptError(event.message)) {
      els.runStatus.textContent = "引导中";
      updateLiveStatus();
      updateSendButton();
      return;
    }
    resetLiveStatus();
    clearPendingGuide();
    showError(event.message ?? "任务失败");
    els.runStatus.textContent = "失败";
    updateSendButton();
  }
}

function shouldSkipDashboardEvent(event) {
  if (!event || typeof event !== "object" || !event.id) {
    return false;
  }
  const id = String(event.id);
  if (state.processedEventIds.has(id)) {
    return true;
  }
  state.processedEventIds.add(id);
  if (state.processedEventIds.size > 1200) {
    state.processedEventIds = new Set(Array.from(state.processedEventIds).slice(-800));
  }
  return false;
}

function beginEventTurn(event) {
  const turnId = typeof event.turnId === "string" ? event.turnId : "";
  if (!turnId) {
    return;
  }
  if (state.activeTurnId && state.activeTurnId !== turnId) {
    collapseAssistantDrafts();
  }
  state.activeTurnId = turnId;
}

function renderTranscriptMessages(messages, options = {}) {
  const nodes = [];
  for (const message of messages) {
    const role = visibleTranscriptRole(message.role);
    if (!role) {
      continue;
    }
    nodes.push(createMessageNode(role, role === "assistant" ? "Ant Code" : "你", messageText(message.content)));
  }
  if (options.prepend) {
    hideEmptyState();
    const anchor = transcriptFirstContentNode();
    for (const node of nodes) {
      els.transcript.insertBefore(node, anchor);
    }
    return nodes;
  }
  for (const node of nodes) {
    appendTranscriptNode(node);
  }
  return nodes;
}

function setTranscriptPaging(page = null) {
  state.transcriptPaging = {
    cursor: page?.cursor ?? page?.nextCursor ?? null,
    hasMore: page?.hasMore === true,
    loading: false,
    error: "",
    total: Number.isFinite(page?.total) ? page.total : 0
  };
  renderTranscriptHistoryStatus();
}

function renderTranscriptHistoryStatus() {
  if (!state.currentSessionId) {
    removeTranscriptHistoryStatus();
    return;
  }
  const paging = state.transcriptPaging;
  if (!paging.hasMore && !paging.loading && !paging.error) {
    removeTranscriptHistoryStatus();
    return;
  }
  if (!state.transcriptHistoryNode) {
    state.transcriptHistoryNode = document.createElement("button");
    state.transcriptHistoryNode.type = "button";
    state.transcriptHistoryNode.className = "history-loader";
    state.transcriptHistoryNode.addEventListener("click", () => loadOlderTranscript());
  }
  state.transcriptHistoryNode.disabled = paging.loading;
  state.transcriptHistoryNode.dataset.state = paging.error ? "error" : paging.loading ? "loading" : "idle";
  state.transcriptHistoryNode.textContent = paging.error
    ? "加载失败，点击重试"
    : paging.loading
      ? "正在加载更早记录"
      : "加载更早记录";
  if (els.transcript.firstChild !== state.transcriptHistoryNode) {
    els.transcript.insertBefore(state.transcriptHistoryNode, els.transcript.firstChild);
  }
}

function removeTranscriptHistoryStatus() {
  state.transcriptHistoryNode?.remove();
  state.transcriptHistoryNode = null;
}

function transcriptFirstContentNode() {
  if (state.transcriptHistoryNode?.parentElement === els.transcript) {
    return state.transcriptHistoryNode.nextSibling;
  }
  return els.emptyState?.parentElement === els.transcript ? els.emptyState.nextSibling : els.transcript.firstChild;
}

function handleTranscriptScroll() {
  if (els.transcript.scrollTop > 180) {
    return;
  }
  if (!state.transcriptPaging.hasMore || state.transcriptPaging.loading) {
    return;
  }
  loadOlderTranscript();
}

async function loadOlderTranscript() {
  if (!state.currentSessionId || !state.transcriptPaging.hasMore || state.transcriptPaging.loading) {
    return;
  }
  const before = state.transcriptPaging.cursor;
  state.transcriptPaging.loading = true;
  state.transcriptPaging.error = "";
  renderTranscriptHistoryStatus();
  const previousHeight = els.transcript.scrollHeight;
  const previousTop = els.transcript.scrollTop;
  const result = await getJson(`/api/sessions/${encodeURIComponent(state.currentSessionId)}/transcript?${new URLSearchParams({
    before: before ?? "",
    limit: "100"
  }).toString()}`).catch((error) => ({ ok: false, error: error.message }));
  state.transcriptPaging.loading = false;
  if (!result.ok) {
    state.transcriptPaging.error = result.error ?? "加载失败";
    renderTranscriptHistoryStatus();
    return;
  }
  state.transcriptPaging.cursor = result.transcriptPage?.cursor ?? result.transcriptPage?.nextCursor ?? null;
  state.transcriptPaging.hasMore = result.transcriptPage?.hasMore === true;
  state.transcriptPaging.total = Number.isFinite(result.transcriptPage?.total) ? result.transcriptPage.total : state.transcriptPaging.total;
  renderTranscriptMessages(result.transcript ?? [], { prepend: true });
  state.transcriptPaging.error = "";
  renderTranscriptHistoryStatus();
  const delta = els.transcript.scrollHeight - previousHeight;
  els.transcript.scrollTop = previousTop + delta;
}

function renderWorkflowPanel(workflow, summary = null) {
  if (!workflow || (!workflow.todos?.length && !workflow.plan?.steps?.length)) {
    state.workflow = null;
    state.workflowExpanded = false;
    renderWorkflowStrip();
    return;
  }
  hideEmptyState();
  state.workflow = workflow;
  if (!state.workflowNode) {
    state.workflowNode = document.createElement("section");
    state.workflowNode.className = "workflow-panel";
    els.transcript.append(state.workflowNode);
  }
  const totals = summary ?? summarizeWorkflow(workflow);
  const percent = totals.total > 0 ? Math.round((totals.completed / totals.total) * 100) : 0;
  state.workflowNode.innerHTML = `
    <div class="workflow-head">
      <div>
        <div class="workflow-kicker">任务进度</div>
        <div class="workflow-title">${totals.completed}/${totals.total} 已完成</div>
      </div>
      <div class="workflow-percent">${percent}%</div>
    </div>
    <div class="workflow-meter"><span style="width: ${percent}%"></span></div>
    ${workflow.todos?.length ? workflowSection("Todo", workflow.todos) : ""}
    ${workflow.plan?.steps?.length ? workflowSection("Plan", workflow.plan.steps) : ""}
  `;
  renderWorkflowStrip();
  scrollTranscript();
}

function renderWorkflowStrip() {
  if (!state.workflow || (!state.workflow.todos?.length && !state.workflow.plan?.steps?.length)) {
    els.workflowStrip.classList.add("hidden");
    els.workflowStrip.innerHTML = "";
    return;
  }
  const totals = summarizeWorkflow(state.workflow);
  const percent = totals.total > 0 ? Math.round((totals.completed / totals.total) * 100) : 0;
  const activeItem = currentWorkflowItem(state.workflow);
  const title = activeItem
    ? `正在：${activeItem.content ?? activeItem.title ?? ""}`
    : totals.completed === totals.total && totals.total > 0
      ? "任务已完成"
      : "等待下一步";
  els.workflowStrip.classList.remove("hidden");
  els.workflowStrip.innerHTML = `
    <button class="workflow-strip-toggle" type="button" data-action="toggle-workflow" aria-expanded="${state.workflowExpanded ? "true" : "false"}">
      <span class="workflow-strip-label">任务进度</span>
      <strong>${totals.completed}/${totals.total}</strong>
      <span class="workflow-strip-current">${escapeHtml(title)}</span>
      <span class="workflow-strip-percent">${percent}%</span>
      <span class="workflow-strip-chevron">${state.workflowExpanded ? "收起" : "展开"}</span>
    </button>
    <div class="workflow-strip-meter"><span style="width: ${percent}%"></span></div>
    ${state.workflowExpanded ? `<div class="workflow-strip-detail">
      ${state.workflow.todos?.length ? workflowSection("Todo", state.workflow.todos, Number.POSITIVE_INFINITY) : ""}
      ${state.workflow.plan?.steps?.length ? workflowSection("Plan", state.workflow.plan.steps, Number.POSITIVE_INFINITY) : ""}
    </div>` : ""}
  `;
}

function currentWorkflowItem(workflow) {
  const items = [...(workflow.todos ?? []), ...(workflow.plan?.steps ?? [])];
  return items.find((item) => normalizeWorkflowStatus(item.status) === "in_progress")
    ?? items.find((item) => normalizeWorkflowStatus(item.status) === "pending")
    ?? null;
}

function workflowSection(label, items, limit = 8) {
  return `
    <div class="workflow-section">
      <div class="workflow-section-title">${label}</div>
      <div class="workflow-list">
        ${items.slice(0, limit).map((item) => workflowItem(item)).join("")}
      </div>
    </div>
  `;
}

function workflowItem(item) {
  const status = normalizeWorkflowStatus(item.status);
  return `
    <div class="workflow-item ${status}">
      <span class="workflow-mark"></span>
      <span class="workflow-text">${escapeHtml(item.content ?? item.title ?? "")}</span>
    </div>
  `;
}

function normalizeWorkflowStatus(status) {
  if (status === "completed" || status === "in_progress" || status === "cancelled") {
    return status;
  }
  return "pending";
}

function summarizeWorkflow(workflow) {
  const items = [...(workflow.todos ?? []), ...(workflow.plan?.steps ?? [])];
  return {
    total: items.length,
    pending: items.filter((item) => item.status === "pending").length,
    in_progress: items.filter((item) => item.status === "in_progress").length,
    completed: items.filter((item) => item.status === "completed").length,
    cancelled: items.filter((item) => item.status === "cancelled").length
  };
}

function appendMessage(kind, label, text) {
  const wasAtBottom = isTranscriptNearBottom();
  const node = createMessageNode(kind, label, text);
  appendTranscriptNode(node);
  scrollTranscript({ onlyIfNearBottom: true, wasAtBottom });
}

function createMessageNode(kind, label, text) {
  hideEmptyState();
  const node = document.createElement("article");
  node.className = `message ${kind}`;
  node.innerHTML = `
    <div class="message-label">${escapeHtml(label)}</div>
    <div class="message-body"></div>
  `;
  renderMessageText(node.querySelector(".message-body"), text ?? "", { markdown: kind === "assistant" });
  return node;
}

function appendTranscriptNode(node) {
  hideEmptyState();
  els.transcript.append(node);
}

function appendAssistantDraft(event) {
  const wasAtBottom = isTranscriptNearBottom();
  hideEmptyState();
  const turnKey = typeof event.turnId === "string" && event.turnId ? event.turnId : state.activeTurnId || "turn";
  const roundKey = `${turnKey}:${Number.isFinite(event.round) ? String(event.round) : "current"}`;
  let draft = state.assistantDrafts.get(roundKey);
  if (!draft) {
    const node = document.createElement("article");
    node.className = "message assistant draft-message";
    const label = Number.isFinite(event.round) ? `思考 · 第 ${event.round} 轮` : "思考";
    node.innerHTML = `
      <div class="message-label">${escapeHtml(label)}</div>
      <div class="message-body"></div>
    `;
    draft = {
      round: Number.isFinite(event.round) ? event.round : null,
      text: "",
      node,
      body: node.querySelector(".message-body"),
      renderTimer: null,
      lastRenderAt: 0,
      renderedText: ""
    };
    state.assistantDrafts.set(roundKey, draft);
    els.transcript.append(node);
  }
  draft.text += String(event.text ?? "");
  scheduleDraftRender(draft);
  scrollTranscript({ onlyIfNearBottom: true, wasAtBottom });
  setLiveTitle("正在生成回复");
}

function scheduleDraftRender(draft) {
  const elapsed = Date.now() - draft.lastRenderAt;
  if (elapsed >= DRAFT_RENDER_INTERVAL_MS) {
    renderAssistantDraft(draft);
    return;
  }
  if (draft.renderTimer) {
    return;
  }
  draft.renderTimer = setTimeout(() => {
    draft.renderTimer = null;
    renderAssistantDraft(draft);
  }, DRAFT_RENDER_INTERVAL_MS - elapsed);
}

function renderAssistantDraft(draft, options = {}) {
  const wasAtBottom = isTranscriptNearBottom();
  if (draft.renderTimer) {
    clearTimeout(draft.renderTimer);
    draft.renderTimer = null;
  }
  if (!options.force && draft.renderedText === draft.text) {
    return;
  }
  draft.renderedText = draft.text;
  draft.lastRenderAt = Date.now();
  renderMessageText(draft.body, draft.text, { markdown: true, lightweight: true });
  scrollTranscript({ onlyIfNearBottom: true, wasAtBottom });
}

function appendActivity(activity) {
  const wasAtBottom = isTranscriptNearBottom();
  const node = document.createElement("div");
  node.className = `activity-card ${activity.severity ?? "info"}${activity.collapsed ? "" : " open"}`;
  node.innerHTML = `
    <div class="activity-head">
      <span class="status-dot"></span>
      <div class="activity-title">${escapeHtml(activity.title)}</div>
      <span class="chevron">⌄</span>
    </div>
    <div class="activity-detail">${escapeHtml(activity.detail ?? "")}</div>
  `;
  node.querySelector(".activity-head").addEventListener("click", () => {
    node.classList.toggle("open");
  });
  els.transcript.append(node);
  scrollTranscript({ onlyIfNearBottom: true, wasAtBottom });
}

function handleActivity(activity) {
  if (activity.status === "running" || activity.status === "waiting") {
    updateLiveActivity(activity);
    return;
  }
  const shouldKeep = activity.status === "failed" || activity.status === "blocked" || isMeaningfulCompletedActivity(activity);
  removeLiveActivity(activity);
  if (shouldKeep) {
    state.completedActivities.push(activity);
  }
}

function isBackgroundSubagentActivity(activity) {
  return activity?.backgroundSubagent === true || String(activity?.rawType ?? "").startsWith("subagent_group_");
}

function handleBackgroundSubagentActivity(activity) {
  const key = activity.coalesceKey || activity.groupId || activity.taskId || activity.id;
  const previous = state.backgroundSubagents.get(key) ?? {};
  const merged = {
    ...previous,
    ...activity,
    groupId: activity.groupId ?? previous.groupId ?? null,
    taskId: activity.taskId ?? previous.taskId ?? null,
    profile: activity.profile ?? previous.profile ?? null,
    waitFor: activity.waitFor ?? previous.waitFor ?? null,
    wakeParent: typeof activity.wakeParent === "boolean" ? activity.wakeParent : previous.wakeParent ?? null,
    summary: activity.summary || activity.detail || previous.summary || "",
    wakePromptQueued: activity.wakePromptQueued === true || previous.wakePromptQueued === true,
    status: backgroundSubagentDisplayStatus(activity, previous)
  };
  if (backgroundSubagentVisible(merged)) {
    state.backgroundSubagents.set(key, merged);
  } else {
    state.backgroundSubagents.delete(key);
  }
  updateLiveStatus();
  if (!state.running && state.backgroundSubagents.size > 0) {
    els.runStatus.textContent = merged.status === "waiting" ? "等待子智能体唤醒" : "子智能体运行中";
  }
}

function clearBackgroundSubagentStatus(groupId) {
  const id = String(groupId ?? "").trim();
  if (id) {
    state.backgroundSubagents.delete(`subagent-group:${id}`);
    for (const [key, item] of state.backgroundSubagents.entries()) {
      if (item.groupId === id) {
        state.backgroundSubagents.delete(key);
      }
    }
  } else {
    state.backgroundSubagents.clear();
  }
  updateLiveStatus();
}

function backgroundSubagentDisplayStatus(activity, previous) {
  if (activity.rawType === "subagent_group_wakeup" || activity.wakePromptQueued === true) {
    return "waiting";
  }
  if (activity.rawType === "subagent_group_started") {
    return "running";
  }
  if (activity.completed === true) {
    const wakeParent = typeof activity.wakeParent === "boolean" ? activity.wakeParent : previous.wakeParent;
    const waitFor = activity.waitFor ?? previous.waitFor;
    return wakeParent !== false && waitFor !== "none" ? "waiting" : (activity.status ?? "completed");
  }
  return activity.status ?? previous.status ?? "running";
}

function backgroundSubagentVisible(activity) {
  return activity.status === "running" || activity.status === "waiting";
}

function updateLiveActivity(activity) {
  const key = activity.coalesceKey || activity.toolUseId || activity.id;
  state.liveActivities.set(key, activity);
  setLiveTitle(activity.title || "正在处理");
}

function removeLiveActivity(activity) {
  const key = activity.coalesceKey || activity.toolUseId || activity.id;
  state.liveActivities.delete(key);
  updateLiveStatus();
}

function setLiveTitle(title) {
  state.liveTitle = title;
  updateLiveStatus();
}

function updateLiveStatus() {
  const active = Array.from(state.liveActivities.values()).filter((activity) => activity.status === "running" || activity.status === "waiting");
  const background = Array.from(state.backgroundSubagents.values()).filter(backgroundSubagentVisible);
  const visible = state.running || active.length > 0 || background.length > 0 || state.liveTitle;
  els.liveStatus.classList.toggle("hidden", !visible);
  if (!visible) {
    els.liveTitle.textContent = "";
    els.liveSubtasks.innerHTML = "";
    return;
  }
  const primary = active.find((activity) => activity.toolName !== "agent_run") || active[0];
  const subtasks = active.filter((activity) => activity.toolName === "agent_run");
  els.liveTitle.textContent = background.length > 0 && (!primary || primary.title === "开始任务")
    ? background.some((item) => item.status === "running") ? "子智能体后台运行中" : "等待子智能体唤醒主控"
    : primary?.title === "开始任务" && subtasks.length > 0
    ? "子智能体运行中"
    : primary?.title || state.liveTitle || "正在处理";
  els.liveSubtasks.innerHTML = "";
  for (const task of subtasks.slice(0, 4)) {
    const chip = document.createElement("div");
    chip.className = "live-chip";
    chip.innerHTML = `<span class="chip-pulse" aria-hidden="true"></span>${escapeHtml(task.profile ? `${task.profile} 子任务运行中` : "子智能体运行中")}`;
    els.liveSubtasks.append(chip);
  }
  for (const item of background.slice(0, 4)) {
    const chip = document.createElement("div");
    chip.className = "live-chip";
    const profile = item.profile ? `${item.profile} ` : "";
    chip.innerHTML = `<span class="chip-pulse" aria-hidden="true"></span>${escapeHtml(item.status === "waiting" ? `${profile}等待唤醒` : `${profile}后台运行`)}`;
    els.liveSubtasks.append(chip);
  }
}

function resetLiveStatus() {
  state.running = false;
  state.liveTitle = "";
  state.liveActivities.clear();
  state.backgroundSubagents.clear();
  updateLiveStatus();
  updateSendButton();
}

function updateSessionStatus(status) {
  if (!status || typeof status !== "object") {
    renderComposerStatus();
    return;
  }
  state.sessionStatus = {
    ...state.sessionStatus,
    ...status,
    context: status.context ?? state.sessionStatus?.context ?? null
  };
  renderComposerStatus();
}

function updateTurnChangeStats(stats, options = {}) {
  if (options.reset) {
    resetTurnChangeStats();
    return;
  }
  if (!stats || typeof stats !== "object") {
    renderComposerStatus();
    return;
  }
  const normalized = normalizeChangeStats(stats);
  if (options.replace) {
    state.turnChangeStats = normalized;
  } else {
    state.turnChangeStats = {
      additions: state.turnChangeStats.additions + normalized.additions,
      deletions: state.turnChangeStats.deletions + normalized.deletions,
      files: state.turnChangeStats.files + normalized.files,
      redacted: state.turnChangeStats.redacted || normalized.redacted,
      truncated: state.turnChangeStats.truncated || normalized.truncated,
      approximate: state.turnChangeStats.approximate || normalized.approximate
    };
  }
  renderComposerStatus();
}

function resetTurnChangeStats() {
  state.turnChangeStats = { additions: 0, deletions: 0, files: 0, redacted: false, truncated: false, approximate: false };
  renderComposerStatus();
}

function normalizeChangeStats(stats) {
  return {
    additions: nonNegativeInteger(stats.additions),
    deletions: nonNegativeInteger(stats.deletions),
    files: nonNegativeInteger(stats.files),
    redacted: stats.redacted === true,
    truncated: stats.truncated === true,
    approximate: stats.approximate === true
  };
}

function renderComposerStatus() {
  if (!els.modelStatus || !els.contextStatus || !els.changeStatus) {
    return;
  }
  const model = state.sessionStatus?.model || "default";
  const context = state.sessionStatus?.context ?? null;
  els.modelStatus.textContent = `模型 ${model}`;
  els.contextStatus.textContent = `上下文 ${formatContextUsage(context)}`;

  const stats = state.turnChangeStats ?? {};
  const hasChanges = nonNegativeInteger(stats.additions) > 0 || nonNegativeInteger(stats.deletions) > 0 || stats.redacted === true;
  els.changeStatus.classList.toggle("hidden", !hasChanges);
  if (hasChanges) {
    const suffix = [
      stats.files ? `${stats.files} 文件` : null,
      stats.redacted ? "敏感差异已隐藏" : null,
      stats.truncated ? "已截断" : null,
      stats.approximate ? "近似" : null
    ].filter(Boolean).join(" · ");
    els.changeStatus.innerHTML = `
      <span class="change-label">本轮</span>
      <span class="change-add">+${nonNegativeInteger(stats.additions)}</span>
      <span class="change-del">-${nonNegativeInteger(stats.deletions)}</span>
      ${suffix ? `<span class="change-meta">· ${escapeHtml(suffix)}</span>` : ""}
    `;
  } else {
    els.changeStatus.replaceChildren();
  }
}

function formatContextUsage(context) {
  if (!context || typeof context !== "object") {
    return "-- / --";
  }
  const used = firstFiniteNumber(
    context.promptTokens,
    context.providerPromptTokens,
    context.promptMessageTokens,
    context.messageTokens
  );
  const limit = firstFiniteNumber(context.maxTokens, context.modelMaxTokens);
  const percent = Number.isFinite(used) && Number.isFinite(limit) && limit > 0
    ? ` · ${Math.min(999, Math.round((used / limit) * 100))}%`
    : "";
  return `${formatTokenCount(used)} / ${formatTokenCount(limit)}${percent}`;
}

function firstFiniteNumber(...values) {
  for (const value of values) {
    const number = Number(value);
    if (Number.isFinite(number)) {
      return number;
    }
  }
  return null;
}

function formatTokenCount(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "--";
  }
  if (number >= 1000000) {
    return `${trimNumber(number / 1000000)}M`;
  }
  if (number >= 1000) {
    return `${trimNumber(number / 1000)}k`;
  }
  return String(Math.round(number));
}

function trimNumber(value) {
  return value >= 10 ? String(Math.round(value)) : value.toFixed(1).replace(/\.0$/, "");
}

function nonNegativeInteger(value) {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : 0;
}

function collapseCompletedActivities() {
  if (state.completedActivities.length === 0) {
    return;
  }
  const node = document.createElement("details");
  node.className = "activity-summary";
  node.innerHTML = `
    <summary>过程记录 · ${state.completedActivities.length} 项</summary>
    <div class="activity-summary-list"></div>
  `;
  const list = node.querySelector(".activity-summary-list");
  for (const activity of state.completedActivities.slice(-12)) {
    const item = document.createElement("div");
    item.className = `summary-row ${activity.severity ?? "info"}`;
    item.innerHTML = `
      <span class="status-dot"></span>
      <span>${escapeHtml(activity.title)}</span>
    `;
    list.append(item);
  }
  els.transcript.append(node);
  state.completedActivities = [];
  scrollTranscript({ onlyIfNearBottom: true });
}

function clearAssistantDrafts() {
  for (const draft of state.assistantDrafts.values()) {
    if (draft.renderTimer) {
      clearTimeout(draft.renderTimer);
      draft.renderTimer = null;
    }
    draft.node.remove();
  }
  state.assistantDrafts.clear();
}

function collapseAssistantDrafts(finalText = "") {
  const capturedDrafts = Array.from(state.assistantDrafts.values()).filter((draft) => draft.text.trim().length > 0);
  clearAssistantDrafts();
  if (capturedDrafts.length === 0) {
    return;
  }
  const visibleDrafts = capturedDrafts.filter((draft) => !isDuplicateDraftText(draft.text, finalText));
  const node = document.createElement("details");
  node.className = `draft-summary${visibleDrafts.length === 0 ? " compact" : ""}`;
  const meta = visibleDrafts.length > 0 ? `已收起 · ${visibleDrafts.length} 轮` : "已收起 · 已汇入最终回复";
  node.innerHTML = `
    <summary>
      <span class="status-dot"></span>
      <span>思考过程</span>
      <span class="draft-summary-meta">${meta}</span>
    </summary>
    <div class="draft-summary-list">
      ${visibleDrafts.length === 0 ? `<div class="draft-summary-note">本轮流式草稿已合并到最终回复，没有额外过程内容。</div>` : ""}
    </div>
  `;
  const list = node.querySelector(".draft-summary-list");
  for (const draft of visibleDrafts) {
    const item = document.createElement("section");
    item.className = "draft-summary-item";
    const title = document.createElement("div");
    title.className = "draft-summary-title";
    title.textContent = Number.isFinite(draft.round) ? `第 ${draft.round} 轮` : "思考";
    const body = document.createElement("div");
    body.className = "message-body";
    renderMessageText(body, draft.text, { markdown: true, lightweight: true });
    item.append(title, body);
    list.append(item);
  }
  els.transcript.append(node);
  scrollTranscript({ onlyIfNearBottom: true });
}

function isMeaningfulCompletedActivity(activity) {
  if (activity.toolName === "agent_run") {
    return true;
  }
  return ["write_file", "edit_file", "powershell", "bash", "web_fetch", "web_search", "document_intake"].includes(activity.toolName);
}

function isDuplicateDraftText(draftText, finalText) {
  const draft = normalizeComparableText(draftText);
  const final = normalizeComparableText(finalText);
  if (!draft || !final) {
    return false;
  }
  if (draft === final) {
    return true;
  }
  const minLength = Math.min(draft.length, final.length);
  const maxLength = Math.max(draft.length, final.length);
  if (minLength < 120 || minLength / maxLength < 0.82) {
    return false;
  }
  return draft.includes(final) || final.includes(draft);
}

function normalizeComparableText(text) {
  return String(text ?? "")
    .replace(/\s+/g, " ")
    .trim();
}

function showApproval(approval) {
  state.pendingApproval = approval;
  const display = approval.display && typeof approval.display === "object" ? approval.display : {};
  const title = display.title || `需要权限确认 · ${approval.toolName}`;
  const explanation = display.explanation || "";
  const severityClass = display.severity ? ` ${display.severity}` : "";
  const allowSessionLabel = display.allowSessionLabel || "本会话允许";
  els.approvalPanel.classList.remove("hidden");
  els.approvalPanel.className = `approval-panel${severityClass}`;
  els.approvalPanel.innerHTML = `
    <div class="approval-title">${escapeHtml(title)}</div>
    <div class="approval-preview">${escapeHtml([
      explanation,
      approval.reason,
      approval.sensitive ? "敏感信息强确认：批准后相关内容可能进入模型上下文。" : "",
      approval.outsideWorkspace ? "目标位于工作区外，需要明确确认。" : "",
      ...(approval.preview ?? [])
    ].filter(Boolean).join("\n"))}</div>
    <div class="approval-actions">
      <button type="button" data-action="allow-once">允许一次</button>
      <button type="button" data-action="allow-session">${escapeHtml(allowSessionLabel)}</button>
      <button type="button" data-action="deny" class="danger">拒绝</button>
      <button type="button" data-action="cancel">取消</button>
    </div>
  `;
  els.approvalPanel.querySelectorAll("button[data-action]").forEach((button) => {
    button.addEventListener("click", () => resolveApproval(button.dataset.action));
  });
}

async function resolveApproval(action) {
  if (!state.pendingApproval) return;
  const approvalId = state.pendingApproval.id;
  await postJson(`/api/approvals/${encodeURIComponent(approvalId)}`, { action });
}

function hideApproval() {
  state.pendingApproval = null;
  els.approvalPanel.className = "approval-panel hidden";
  els.approvalPanel.innerHTML = "";
}

function showQuestion(question) {
  state.pendingQuestion = {
    ...question,
    selectedChoices: new Set((question.choices ?? []).filter((choice) => choice.selected).map((choice) => choice.value ?? choice.label)),
    customDraft: ""
  };
  renderQuestionPanel();
}

function renderQuestionPanel() {
  const question = state.pendingQuestion;
  if (!question) return;
  els.questionPanel.classList.remove("hidden");
  const choices = question.choices ?? [];
  els.questionPanel.innerHTML = `
    <div class="question-title">${escapeHtml(question.header ?? "需求核对")}</div>
    <div class="question-copy">${escapeHtml(question.question ?? "请确认需求")}</div>
    ${choices.length ? `<div class="question-choices">${choices.map((choice) => questionChoiceButton(choice, question)).join("")}</div>` : ""}
    ${question.allowCustom ? `<textarea class="question-input" rows="2" placeholder="${choices.length ? "补充其他要求，可留空" : "输入你的回答"}"></textarea>` : ""}
    <div class="question-actions">
      <button type="button" data-action="submit">${escapeHtml(question.confirmLabel ?? "确认")}</button>
      <button type="button" data-action="cancel">取消</button>
    </div>
  `;
  els.questionPanel.querySelectorAll("button[data-choice]").forEach((button) => {
    button.addEventListener("click", () => toggleQuestionChoice(button.dataset.choice));
  });
  els.questionPanel.querySelector("button[data-action='submit']").addEventListener("click", submitQuestion);
  els.questionPanel.querySelector("button[data-action='cancel']").addEventListener("click", cancelQuestion);
  const input = els.questionPanel.querySelector(".question-input");
  if (input) {
    input.value = question.customDraft ?? "";
    input.addEventListener("input", () => {
      question.customDraft = input.value;
    });
    if (choices.length === 0) {
      input.focus();
    }
  }
}

function questionChoiceButton(choice, question) {
  const value = String(choice.value ?? choice.label);
  const selected = question.selectedChoices.has(value);
  return `
    <button type="button" class="question-choice${selected ? " selected" : ""}" data-choice="${escapeHtml(value)}" aria-pressed="${selected ? "true" : "false"}">
      <span>${escapeHtml(choice.label ?? value)}</span>
      ${choice.description ? `<small>${escapeHtml(choice.description)}</small>` : ""}
    </button>
  `;
}

function toggleQuestionChoice(value) {
  const question = state.pendingQuestion;
  if (!question) return;
  rememberQuestionDraft();
  if (question.multiple) {
    if (question.selectedChoices.has(value)) {
      question.selectedChoices.delete(value);
    } else {
      question.selectedChoices.add(value);
    }
  } else {
    question.selectedChoices = new Set([value]);
  }
  renderQuestionPanel();
}

async function submitQuestion() {
  const question = state.pendingQuestion;
  if (!question) return;
  rememberQuestionDraft();
  const selectedChoices = Array.from(question.selectedChoices);
  const customAnswer = (question.customDraft ?? "").trim();
  await postJson(`/api/questions/${encodeURIComponent(question.id)}`, {
    selectedChoices,
    customAnswer,
    answer: customAnswer,
    cancelled: false
  });
}

async function cancelQuestion() {
  const question = state.pendingQuestion;
  if (!question) return;
  await postJson(`/api/questions/${encodeURIComponent(question.id)}`, {
    cancelled: true,
    answer: "",
    selectedChoices: []
  });
}

function hideQuestion() {
  state.pendingQuestion = null;
  els.questionPanel.classList.add("hidden");
  els.questionPanel.innerHTML = "";
}

function showTrustPanel() {
  renderTrustPanel();
}

function renderTrustPanel() {
  if (!state.trust || state.trust.trusted) {
    els.trustPanel.classList.add("hidden");
    els.trustPanel.innerHTML = "";
    return;
  }
  els.trustPanel.classList.remove("hidden");
  const perProcess = state.trust.requiresPerProcessConfirmation
    ? "当前为高敏模式，本次确认只授权当前 Dashboard 进程。"
    : "确认后会记录这个工作区，下次从同一路径启动可继续使用。";
  els.trustPanel.innerHTML = `
    <div>
      <div class="trust-title">信任此工作区？</div>
      <div class="trust-copy">${escapeHtml(state.trust.displayPath ?? state.cwd)}</div>
      <div class="trust-copy">${escapeHtml(perProcess)}</div>
    </div>
    <div class="trust-actions">
      <button type="button" data-action="trust">信任并继续</button>
    </div>
  `;
  els.trustPanel.querySelector("button[data-action='trust']").addEventListener("click", confirmTrust);
}

async function confirmTrust() {
  const button = els.trustPanel.querySelector("button[data-action='trust']");
  if (button) {
    button.disabled = true;
    button.textContent = "保存中";
  }
  const result = await postJson("/api/trust", {}).catch((error) => ({ ok: false, error: error.message }));
  if (!result.ok) {
    showError(result.error ?? "工作区信任保存失败");
    renderTrustPanel();
    return;
  }
  state.trust = result.trust;
  renderTrustPanel();
  updateSendButton();
  els.promptInput.focus();
}

function renderQueuePanel() {
  const visible = state.running || state.queue.length > 0 || state.pendingGuide;
  els.queuePanel.classList.toggle("hidden", !visible);
  if (!visible) {
    els.queuePanel.innerHTML = "";
    return;
  }
  const guideFeedback = state.pendingGuide ? renderGuideFeedback(state.pendingGuide) : "";
  const queueItems = state.queue.slice(0, 6).map((item, index) => renderQueueItem(item, index)).join("");
  const hiddenQueueCount = Math.max(0, state.queue.length - 6);
  els.queuePanel.innerHTML = `
    <div class="queue-head">
      <div>
        <div class="queue-title">${state.queue.length > 0 ? `${state.queue.length} 条排队中` : "当前任务运行中"}</div>
        <div class="queue-copy">输入新内容回车会进入队列，未开始的队列可以取消。</div>
      </div>
      <button type="button" id="guide-button" ${guideButtonDisabled() ? "disabled" : ""}>${guideButtonText()}</button>
    </div>
    ${guideFeedback}
    ${queueItems ? `<div class="queue-list">${queueItems}${hiddenQueueCount ? `<div class="queue-more">还有 ${hiddenQueueCount} 条排队内容未展开</div>` : ""}</div>` : ""}
  `;
  els.queuePanel.querySelector("#guide-button")?.addEventListener("click", () => guideTurn());
  els.queuePanel.querySelectorAll("[data-guide-queue-id]").forEach((button) => {
    button.addEventListener("click", () => guideTurnFromQueue(button.dataset.guideQueueId));
  });
  els.queuePanel.querySelectorAll("[data-cancel-queue-id]").forEach((button) => {
    button.addEventListener("click", () => cancelQueuedTurn(button.dataset.cancelQueueId));
  });
  syncGuideButton();
}

function renderQueueItem(item, index) {
  const isCancelling = state.queueCancelling.has(item.id);
  return `
    <div class="queue-item${item.kind === "guide" ? " guide" : ""}">
      <span>${index + 1}</span>
      <strong>${item.kind === "guide" ? "引导" : "排队"}</strong>
      <em>${escapeHtml(item.preview ?? "")}</em>
      <div class="queue-actions">
        ${item.kind === "guide" ? "" : `<button type="button" class="queue-guide-button" data-guide-queue-id="${escapeHtml(item.id)}" ${isCancelling ? "disabled" : ""}>引导</button>`}
        <button type="button" class="queue-cancel-button" data-cancel-queue-id="${escapeHtml(item.id)}" ${isCancelling ? "disabled" : ""}>${isCancelling ? "取消中" : "取消"}</button>
      </div>
    </div>
  `;
}

function setPendingGuide(guide) {
  state.pendingGuide = {
    ...state.pendingGuide,
    ...guide,
    preview: previewText(guide.preview ?? state.pendingGuide?.preview ?? "")
  };
  renderQueuePanel();
  updateLiveStatus();
}

function clearPendingGuide() {
  state.pendingGuide = null;
  renderQueuePanel();
}

function syncPendingGuideFromQueue() {
  if (state.pendingGuide) {
    const stillQueued = state.queue.some((item) => item.kind === "guide");
    if (!stillQueued && !state.running && state.pendingGuide.phase === "registered") {
      clearPendingGuide();
      return;
    }
    renderQueuePanel();
    return;
  }
  const queuedGuide = state.queue.find((item) => item.kind === "guide");
  if (queuedGuide) {
    setPendingGuide({
      sessionId: state.currentSessionId,
      phase: "registered",
      preview: queuedGuide.preview ?? ""
    });
    return;
  }
  renderQueuePanel();
}

function renderGuideFeedback(guide) {
  const copy = guideCopy(guide.phase);
  const preview = guide.preview ? `<div class="guide-preview">${escapeHtml(guide.preview)}</div>` : "";
  return `
    <div class="guide-feedback ${escapeHtml(guide.phase ?? "registered")}">
      <span class="chip-pulse" aria-hidden="true"></span>
      <div class="guide-feedback-body">
        <strong>${escapeHtml(copy.title)}</strong>
        <small>${escapeHtml(copy.detail)}</small>
        ${preview}
      </div>
    </div>
  `;
}

function guideCopy(phase) {
  if (phase === "registering") {
    return {
      title: "正在登记引导",
      detail: "点击已生效，正在把这条要求放到下一轮优先处理。"
    };
  }
  if (phase === "interrupting") {
    return {
      title: "引导已接管",
      detail: "正在等待当前轮次收束，随后会优先按这条引导继续。"
    };
  }
  if (phase === "continuing") {
    return {
      title: "正在按引导继续",
      detail: "当前回复已经切到引导后的续跑。"
    };
  }
  if (phase === "stopped") {
    return {
      title: "已收到停止引导",
      detail: "正在停止当前轮次，不会再创建新的引导续跑。"
    };
  }
  return {
    title: "引导已登记",
    detail: "下一轮会优先按这条引导继续。"
  };
}

function guideSource(queueItemId = "") {
  const queuedItem = queueItemId
    ? state.queue.find((item) => item.id === queueItemId && item.kind !== "guide" && !state.queueCancelling.has(item.id))
    : state.queue.find((item) => item.kind !== "guide" && !state.queueCancelling.has(item.id));
  if (queueItemId && !queuedItem) {
    return null;
  }
  if (queueItemId) {
    return {
      guidance: queuedItem.preview ?? "",
      queueItemId: queuedItem.id,
      preview: queuedItem.preview ?? ""
    };
  }
  const guidance = els.promptInput.value.trim();
  if (guidance) {
    return { guidance, queueItemId: "", preview: guidance };
  }
  if (!queuedItem) {
    return null;
  }
  return {
    guidance: queuedItem.preview ?? "",
    queueItemId: queuedItem.id,
    preview: queuedItem.preview ?? ""
  };
}

function guideTurnFromQueue(queueItemId) {
  if (!queueItemId || state.guideSubmitting) {
    return;
  }
  guideTurn(queueItemId);
}

function guideButtonText() {
  if (state.guideSubmitting || state.pendingGuide?.phase === "registering") return "登记中";
  if (els.promptInput.value.trim()) return "引导对话";
  if (state.queue.some((item) => item.kind !== "guide")) return "引导队首";
  if (state.pendingGuide?.phase === "interrupting") return "接管中";
  if (state.pendingGuide?.phase === "continuing") return "引导中";
  return "引导对话";
}

function guideButtonDisabled() {
  return !state.running || state.guideSubmitting || !guideSource();
}

function syncGuideButton() {
  const button = els.queuePanel.querySelector("#guide-button");
  if (!button) return;
  button.disabled = guideButtonDisabled();
  button.textContent = guideButtonText();
}

function shouldKeepGuideFeedback() {
  return ["registering", "registered", "interrupting"].includes(state.pendingGuide?.phase);
}

function isInterruptError(message) {
  return /aborted|abort|interrupted|中断|取消/i.test(String(message ?? ""));
}

function updateSendButton() {
  if (!state.trust?.trusted) {
    els.sendButton.textContent = "待信任";
    els.sendButton.disabled = false;
    return;
  }
  if (state.running) {
    els.sendButton.textContent = "运行中";
    els.sendButton.title = "点击中断当前任务";
  } else {
    els.sendButton.textContent = "发送";
    els.sendButton.title = "发送";
  }
  els.sendButton.disabled = false;
}

function showContextConfirm(action) {
  const isClear = action === "clear";
  els.contextPanel.classList.remove("hidden");
  els.contextPanel.innerHTML = `
    <div>
      <div class="context-title">${isClear ? "清空上下文？" : "压缩上下文？"}</div>
      <div class="context-copy">${isClear ? "这会清除当前会话的模型上下文，历史记录仍可在左侧查看。" : "这会整理较早上下文，保留近期对话并写入压缩摘要。"}</div>
    </div>
    <div class="context-confirm-actions">
      <button type="button" data-action="cancel">取消</button>
      <button type="button" data-action="${action}" class="${isClear ? "danger" : ""}">${isClear ? "确认清空" : "确认压缩"}</button>
    </div>
  `;
  els.contextPanel.querySelector("button[data-action='cancel']").addEventListener("click", hideContextConfirm);
  els.contextPanel.querySelector(`button[data-action='${action}']`).addEventListener("click", () => runContextAction(action));
}

function hideContextConfirm() {
  els.contextPanel.classList.add("hidden");
  els.contextPanel.innerHTML = "";
}

async function runContextAction(action) {
  const endpoint = action === "clear" ? "/api/context/clear" : "/api/context/compact";
  const button = els.contextPanel.querySelector(`button[data-action='${action}']`);
  if (button) {
    button.disabled = true;
    button.textContent = action === "clear" ? "清空中" : "压缩中";
  }
  const result = await postJson(endpoint, {
    sessionId: state.currentSessionId,
    permissionMode: state.permissionMode
  }).catch((error) => ({ ok: false, error: error.message }));
  if (!result.ok) {
    showError(result.error ?? "上下文操作失败");
    hideContextConfirm();
    return;
  }
  state.currentSessionId = result.sessionId ?? state.currentSessionId;
  hideContextConfirm();
  appendActivity({
    title: action === "clear" ? "上下文已清空" : "上下文已压缩",
    detail: action === "clear" ? contextSummaryLine(result.after) : compactResultLine(result.result),
    severity: "success",
    collapsed: true
  });
  updateSessionStatus(result.sessionStatus);
}

function contextSummaryLine(summary) {
  return summary ? `${summary.messages ?? 0} 条上下文消息，摘要 ${summary.summaryBytes ?? 0} 字节` : "";
}

function compactResultLine(result) {
  if (!result) return "";
  return result.compacted
    ? `${result.beforeMessages ?? "-"} -> ${result.afterMessages ?? "-"}，摘要 ${result.summaryBytes ?? 0} 字节`
    : `未压缩：${result.reason ?? "无需压缩"}`;
}

function rememberQuestionDraft() {
  const question = state.pendingQuestion;
  if (!question) return;
  const input = els.questionPanel.querySelector(".question-input");
  if (input) {
    question.customDraft = input.value;
  }
}

function questionResolutionText(event) {
  if (event.cancelled) {
    return "已取消需求核对";
  }
  const parts = [];
  for (const choice of event.selectedChoices ?? []) {
    if (choice && !parts.includes(choice)) {
      parts.push(choice);
    }
  }
  if (event.answer && !parts.includes(event.answer)) {
    parts.push(event.answer);
  }
  return parts.length > 0 ? `需求核对：${parts.join("；")}` : "已确认需求核对";
}

function showShutdownPanel() {
  els.shutdownPanel.classList.remove("hidden");
}

function hideShutdownPanel() {
  els.shutdownPanel.classList.add("hidden");
}

async function shutdownDashboard() {
  els.shutdownConfirm.disabled = true;
  els.shutdownConfirm.textContent = "正在关闭";
  disconnectEvents();
  await postJson("/api/shutdown", {}).catch(() => null);
  document.body.classList.add("dashboard-closed");
  els.runStatus.textContent = "已关闭";
  els.transcript.innerHTML = `
    <div class="empty-state">
      <div class="empty-kicker">Ant Code Dashboard</div>
      <div class="empty-title">Dashboard 已关闭</div>
      <div class="empty-copy">本机 WebUI 服务已经停止，可以关闭这个页面。再次使用时重新运行 ant-code dashboard。</div>
    </div>
  `;
}

function renderFiles() {
  els.fileList.innerHTML = "";
  if (state.files.length === 0) {
    const empty = document.createElement("div");
    empty.className = "thread-meta";
    empty.textContent = "暂无产物";
    els.fileList.append(empty);
    return;
  }
  for (const file of state.files) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "file-item";
    item.innerHTML = `
      <div class="file-name">${escapeHtml(file.name)}</div>
      <div class="file-meta">${escapeHtml(file.kind)} · ${escapeHtml(file.source ?? "file")}</div>
    `;
    item.addEventListener("click", () => openFile(file.relativePath));
    els.fileList.append(item);
  }
}

function currentImageFiles() {
  return state.files
    .filter((file) => file.kind === "image")
    .map((file) => ({
      name: file.name,
      rawUrl: rawFileUrl(file.relativePath),
      relativePath: file.relativePath
    }));
}

async function openFile(filePath) {
  if (!filePath) return;
  const result = await getJson(filePreviewUrl(filePath));
  els.previewBody.className = "preview-body";
  if (!result.ok) {
    els.previewBody.innerHTML = `<div class="office-card">${escapeHtml(result.error ?? "无法预览文件")}</div>`;
    return;
  }
  const file = result.file;
  if (file.kind === "image") {
    els.previewBody.innerHTML = `
      <button class="preview-image-button" type="button" aria-label="打开 ${escapeHtml(file.name)} 大图">
        <img class="preview-image" alt="${escapeHtml(file.name)}" src="${file.rawUrl}" />
      </button>
    `;
    els.previewBody.querySelector(".preview-image-button")?.addEventListener("click", () => {
      const images = currentImageFiles();
      const index = Math.max(0, images.findIndex((item) => item.relativePath === file.relativePath));
      showImageLightbox(file, images.length ? images : [file], index);
    });
  } else if (file.kind === "pdf") {
    els.previewBody.innerHTML = `<iframe class="preview-frame" title="${escapeHtml(file.name)}" src="${file.rawUrl}"></iframe>`;
  } else if (file.kind === "office" || file.kind === "binary") {
    els.previewBody.innerHTML = `<div class="office-card"><strong>${escapeHtml(file.name)}</strong><p>${escapeHtml(file.message ?? "此文件第一版不直接预览。")}</p><p>${escapeHtml(file.relativePath)}</p><a class="open-file" href="${file.rawUrl}" target="_blank" rel="noreferrer">打开文件</a></div>`;
  } else if (file.kind === "markdown") {
    els.previewBody.classList.add("document-preview-body");
    const article = document.createElement("article");
    article.className = "markdown-document markdown-body";
    article.tabIndex = 0;
    article.setAttribute("aria-label", `${file.name} Markdown 内容`);
    renderMessageText(article, file.content ?? "", { markdown: true, basePath: parentDirectory(file.relativePath) });
    els.previewBody.replaceChildren(article);
  } else if (file.kind === "data") {
    els.previewBody.classList.add("document-preview-body");
    const article = document.createElement("article");
    article.className = "markdown-document markdown-body";
    article.tabIndex = 0;
    article.setAttribute("aria-label", `${file.name} 数据预览`);
    renderMessageText(article, fencedDataForFile(file), { markdown: true });
    els.previewBody.replaceChildren(article);
  } else {
    els.previewBody.classList.add("document-preview-body");
    els.previewBody.innerHTML = `<pre class="preview-code" tabindex="0" aria-label="${escapeHtml(file.name)} 文档内容">${escapeHtml(file.content ?? "")}</pre>`;
  }
}

function resetPreview(message = "任务产物会显示在这里") {
  els.previewBody.className = "preview-body";
  els.previewBody.innerHTML = `<div class="preview-placeholder">${escapeHtml(message)}</div>`;
}

function fencedDataForFile(file) {
  const language = dataLanguageForExtension(file.extension);
  return `\`\`\`${language}\n${file.content ?? ""}\n\`\`\``;
}

function dataLanguageForExtension(extension) {
  const ext = String(extension ?? "").toLowerCase();
  if (ext === ".yaml" || ext === ".yml") return "yaml";
  if (ext === ".csv") return "csv";
  if (ext === ".tsv") return "tsv";
  return "json";
}

function showImageLightbox(file, items = null, index = 0) {
  const gallery = Array.isArray(items) && items.length > 0 ? items : [file];
  state.lightboxItems = gallery;
  state.lightboxIndex = Math.max(0, Math.min(index, gallery.length - 1));
  renderLightboxImage();
  els.imageLightbox.classList.remove("hidden");
  document.body.classList.add("lightbox-opened");
  els.lightboxClose.focus();
}

function renderLightboxImage() {
  const file = state.lightboxItems[state.lightboxIndex] ?? {};
  els.lightboxTitle.textContent = file.name || "图片预览";
  els.lightboxImage.alt = file.name || "图片预览";
  els.lightboxImage.src = file.rawUrl;
  els.lightboxOpen.href = file.rawUrl;
  const total = state.lightboxItems.length;
  els.lightboxCounter.textContent = total > 1 ? `${state.lightboxIndex + 1} / ${total}` : "";
  els.lightboxPrevious.classList.toggle("hidden", total <= 1);
  els.lightboxNext.classList.toggle("hidden", total <= 1);
}

function moveLightbox(delta) {
  if (els.imageLightbox.classList.contains("hidden") || state.lightboxItems.length <= 1) {
    return;
  }
  const total = state.lightboxItems.length;
  state.lightboxIndex = (state.lightboxIndex + delta + total) % total;
  renderLightboxImage();
}

function hideImageLightbox() {
  if (els.imageLightbox.classList.contains("hidden")) {
    return;
  }
  els.imageLightbox.classList.add("hidden");
  document.body.classList.remove("lightbox-opened");
  els.lightboxImage.removeAttribute("src");
  state.lightboxItems = [];
  state.lightboxIndex = 0;
}

function setPermissionMode(mode) {
  state.permissionMode = mode;
  els.permissionMode.querySelectorAll("button").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });
  els.modeDescription.textContent = MODE_DESCRIPTIONS[mode] ?? MODE_DESCRIPTIONS.plan;
}

function clearTranscript() {
  clearAssistantDraftTimers();
  els.transcript.innerHTML = "";
  state.transcriptHistoryNode = null;
  els.transcript.append(els.emptyState);
  els.emptyState.classList.remove("hidden");
  state.workflow = null;
  state.workflowNode = null;
  state.workflowExpanded = false;
  renderWorkflowStrip();
  state.assistantDrafts.clear();
  state.transcriptPaging = {
    cursor: null,
    hasMore: false,
    loading: false,
    error: "",
    total: 0
  };
  state.activeTurnId = "";
  resetEventReplayState();
  state.lastAssistantFinalSignature = "";
}

function clearAssistantDraftTimers() {
  for (const draft of state.assistantDrafts.values()) {
    if (draft.renderTimer) {
      clearTimeout(draft.renderTimer);
      draft.renderTimer = null;
    }
  }
}

function hideEmptyState() {
  els.emptyState.classList.add("hidden");
}

function showError(message) {
  hideEmptyState();
  appendActivity({
    title: "发生错误",
    detail: message,
    severity: "danger",
    collapsed: false
  });
}

function scrollTranscript(options = {}) {
  if (options.onlyIfNearBottom && options.wasAtBottom === false) {
    return;
  }
  const scrollToBottom = () => {
    els.transcript.scrollTop = els.transcript.scrollHeight;
  };
  scrollToBottom();
  requestAnimationFrame(() => {
    scrollToBottom();
    setTimeout(scrollToBottom, 0);
  });
}

function isTranscriptNearBottom(threshold = 96) {
  return els.transcript.scrollHeight - els.transcript.scrollTop - els.transcript.clientHeight <= threshold;
}

async function getJson(url) {
  const response = await fetch(url);
  return response.json();
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
  return response.json();
}

function messageText(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content.map((item) => {
    if (typeof item === "string") return item;
    if (item && typeof item === "object" && "text" in item) return item.text ?? "";
    return "";
  }).join("");
}

function renderMessageText(node, text, options = {}) {
  node.classList.toggle("markdown-body", options.markdown === true);
  const html = options.markdown
    ? renderMarkdown(text ?? "", { basePath: options.basePath, lightweight: options.lightweight === true })
    : escapeHtml(text ?? "");
  node.innerHTML = html;
  if (!options.lightweight) {
    linkifyFileTextNodes(node, options.basePath);
  }
  bindRichContent(node, { lightweight: options.lightweight === true });
}

function renderLinkedText(node, text) {
  node.textContent = text ?? "";
  linkifyFileTextNodes(node);
  bindRichContent(node);
}

function bindRichContent(node, options = {}) {
  node.querySelectorAll("[data-file]").forEach((link) => {
    link.addEventListener("click", () => openFile(link.dataset.file));
  });
  node.querySelectorAll("[data-image-src]").forEach((button) => {
    const rawUrl = imagePreviewUrl(button.dataset.imageSrc ?? "");
    if (rawUrl) {
      button.dataset.imageRawUrl = rawUrl;
      const image = button.querySelector("img");
      if (image) {
        image.src = rawUrl;
      }
    }
    button.addEventListener("click", () => {
      const imageButtons = Array.from(node.querySelectorAll("[data-image-src]"));
      const items = imageButtons.map((item) => ({
        name: item.dataset.imageAlt || "图片预览",
        rawUrl: item.dataset.imageRawUrl || imagePreviewUrl(item.dataset.imageSrc ?? "")
      })).filter((item) => item.rawUrl);
      const index = Math.max(0, imageButtons.indexOf(button));
      showImageLightbox({
        name: button.dataset.imageAlt || "图片预览",
        rawUrl: button.dataset.imageRawUrl || imagePreviewUrl(button.dataset.imageSrc ?? "")
      }, items, index);
    });
  });
  node.querySelectorAll(".md-copy-code").forEach((button) => {
    button.addEventListener("click", () => copyCodeBlock(button));
  });
  if (!options.lightweight) {
    hydrateRichContent(node);
  }
}

function linkifyFileTextNodes(root, basePath = "") {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent || parent.closest("a, button, code, pre")) {
        return NodeFilter.FILTER_REJECT;
      }
      FILE_REFERENCE_PATTERN.lastIndex = 0;
      return FILE_REFERENCE_PATTERN.test(node.nodeValue ?? "")
        ? NodeFilter.FILTER_ACCEPT
        : NodeFilter.FILTER_REJECT;
    }
  });
  const nodes = [];
  while (walker.nextNode()) {
    nodes.push(walker.currentNode);
  }
  for (const textNode of nodes) {
    replaceFileReferences(textNode, basePath);
  }
}

function replaceFileReferences(textNode, basePath = "") {
  const text = textNode.nodeValue ?? "";
  const fragment = document.createDocumentFragment();
  let lastIndex = 0;
  FILE_REFERENCE_PATTERN.lastIndex = 0;
  for (const match of text.matchAll(FILE_REFERENCE_PATTERN)) {
    const value = match[0];
    const index = match.index ?? 0;
    if (!isLikelyLocalFileReference(value)) {
      continue;
    }
    if (index > lastIndex) {
      fragment.append(document.createTextNode(text.slice(lastIndex, index)));
    }
    const button = document.createElement("button");
    button.className = "file-link";
    button.type = "button";
    button.dataset.file = resolveDisplayFilePath(value, basePath);
    button.textContent = value;
    fragment.append(button);
    lastIndex = index + value.length;
  }
  if (lastIndex < text.length) {
    fragment.append(document.createTextNode(text.slice(lastIndex)));
  }
  textNode.replaceWith(fragment);
}

function isLikelyLocalFileReference(value) {
  const withoutLine = normalizeFileReferencePath(value);
  const extension = withoutLine.split(".").pop()?.toLowerCase() ?? "";
  return LOCAL_FILE_EXTENSIONS.has(extension);
}

function resolveDisplayFilePath(value, basePath = "") {
  const path = String(value ?? "").trim().replace(/\\/g, "/");
  const base = String(basePath ?? "").trim().replace(/\\/g, "/").replace(/^\.\/+/, "").replace(/\/+$/, "");
  if (!path || !base || path.startsWith("/") || /^[A-Za-z]:[\\/]/.test(path) || path.startsWith("../")) {
    return path;
  }
  const normalizedPath = path.replace(/^\.\/+/, "");
  if (isWorkspaceRelativeToBase(normalizedPath, base)) {
    return normalizeRelativePath(normalizedPath);
  }
  return normalizeRelativePath(`${base}/${normalizedPath}`);
}

function normalizeFileReferencePath(value) {
  return String(value ?? "").replace(/:\d+$/, "");
}

function parentDirectory(filePath) {
  const normalized = String(filePath ?? "").replace(/\\/g, "/");
  const index = normalized.lastIndexOf("/");
  if (index <= 0) {
    return "";
  }
  return normalized.slice(0, index);
}

function filePreviewUrl(filePath) {
  return apiFileUrl("/api/files", filePath);
}

function rawFileUrl(filePath) {
  return apiFileUrl("/api/files/raw", filePath);
}

function apiFileUrl(endpoint, filePath) {
  const params = new URLSearchParams();
  params.set("path", normalizeFileReferencePath(filePath));
  if (state.currentSessionId) {
    params.set("sessionId", state.currentSessionId);
  }
  return `${endpoint}?${params.toString()}`;
}

function imagePreviewUrl(src) {
  const value = String(src ?? "").trim();
  if (!value || /^data:image\//i.test(value) || /^https?:\/\//i.test(value) || value.startsWith("/api/files/raw?")) {
    return value;
  }
  if (value.startsWith("/")) {
    return value;
  }
  return rawFileUrl(value.replace(/^\.\//, ""));
}

function normalizeRelativePath(value) {
  const stack = [];
  for (const part of String(value ?? "").split("/")) {
    if (!part || part === ".") {
      continue;
    }
    if (part === "..") {
      if (stack.length > 0 && stack[stack.length - 1] !== "..") {
        stack.pop();
      } else {
        stack.push(part);
      }
      continue;
    }
    stack.push(part);
  }
  return stack.join("/");
}

function isWorkspaceRelativeToBase(value, basePath = "") {
  const firstBaseSegment = String(basePath ?? "").split("/").filter(Boolean)[0];
  return Boolean(firstBaseSegment) && String(value ?? "").startsWith(`${firstBaseSegment}/`);
}

async function copyCodeBlock(button) {
  const frame = button.closest(".md-code-frame");
  const text = frame?.querySelector("code")?.textContent ?? "";
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "已复制";
    setTimeout(() => {
      button.textContent = "复制";
    }, 1200);
  } catch {
    button.textContent = "复制失败";
    setTimeout(() => {
      button.textContent = "复制";
    }, 1400);
  }
}

function previewText(value, max = 120) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  return text.length <= max ? text : `${text.slice(0, max - 3)}...`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString();
}
