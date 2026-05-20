# Ant Code LLM Onboarding Brief

This file is for future LLMs, coding agents, or model adapters that need to
understand this repository quickly without reading the whole codebase first.

## Project Identity

Ant Code is a lab-local coding agent implemented in this repository. The public
CLI name is `ant-code`; the internal implementation codename remains
`lab-agent` for config, storage, protocol, and audit compatibility.

Workspace:

```text
C:\saveproject\LBJ-workspace\lab-agent
```

Primary launch commands:

```powershell
node .\src\cli\index.js tui
ant-code
ant-code tui
ant-code dashboard
npm run check
```

The legacy project has been archived and should not be used as the active
implementation workspace. Future work should modify and test this repository.

## Non-Negotiable Boundaries

- Do not write gateway API keys, provider keys, tokens, or credentials into repo
  files.
- Do not add direct provider-owned cloud endpoints, telemetry, OAuth, remote
  connector discovery, or marketplace auto-discovery.
- Model calls go through the configured lab gateway.
- Tools execute locally through Ant Code's permission engine.
- MCP servers are explicit local stdio processes only.
- Skills are local bounded instruction resources. They do not auto-install
  packages, execute bundled scripts, or contact remote skill marketplaces.
- Recommended no-key MCP entries may be enabled by local config, but every tool
  call still goes through Ant Code's permission engine and environment scrubber.

## Current Product State

The current build is Ant Code 3.0.0 with two local client surfaces: the mature TUI
and the local Dashboard WebUI. `ant-code` still defaults to the TUI;
`ant-code dashboard` starts the WebUI on loopback, default port `7410`, and
opens the browser. Both surfaces share the same core session runtime, local
permission engine, context compaction, model gateway, and `.lab-agent/sessions`
history.

Version lineage is product-generation based. `1.x` covers the old Claude Code
source-derived reference and the first clean-room acceptance baseline; `2.x`
covers the self-owned clean-room architecture, production TUI, local extension
runtime, and orchestration work; `3.x` is the Dashboard/WebUI release line.
Historical acceptance files keep their original version labels as dated
evidence. The current release-line evidence is
`docs/deployment/v3.0-dashboard-acceptance.md`.

Accepted user-facing behavior:

- TUI remains the default for `ant-code`; Dashboard must not regress or rewrite
  existing TUI behavior.
- Large and small terminal scrolling works for long answers.
- Mouse wheel works while model output is streaming.
- The right side panel stays fixed in wide terminals.
- Slash command panels no longer crush the prompt box.
- Routine gateway/tool/turn telemetry is hidden from the compact transcript,
  summarized in detailed mode, and only fully expanded in full detail mode.
- `/resume` and `/sessions` can restore retained session history.
- `/guide <message>` can guide a busy turn at the response boundary.
- `Esc` requires two presses to interrupt a busy turn.
- Common UI and command surfaces are Chinese-first for lab users.
- `/compact` uses model-based summarization through a hidden internal agent
  when the gateway is available and falls back locally otherwise.
- Context protection is proactive. Before every gateway round, the parent
  checks the full prompt payload estimate, including retained messages, tools,
  and current tool results. At the safety threshold it compacts old session
  context on round 0, and compacts older in-flight tool results on later rounds.
  Do not move this check back to "round 0 only"; long tool chains need later
  round protection.
- Session metadata intentionally persists numeric context diagnostics:
  `context.promptTokens`, `context.maxTokens`, and `gatewayRounds[].request.*`
  token estimates must remain numbers. Do not redact these as secrets; only
  redact actual credential fields such as API keys, authorization headers,
  access tokens, passwords, and secrets.
- Token accounting is dual-track. Local estimates are still required before
  gateway requests so Ant Code can decide whether to compact context. Provider
  `usage` is recorded after gateway responses, aggregated into `session.usage`,
  persisted in session metadata, and displayed as "Provider 实报" in TUI status,
  `/context`, `/usage`, and subagent task views when the configured gateway
  reports it.
- Gateway fetches have a small configurable retry budget for transient
  pre-response network failures. `lab.gatewayMaxRetries` and
  `LAB_MODEL_GATEWAY_MAX_RETRIES` control it; HTTP errors, parse errors, and
  user aborts are not retried. Keep retry diagnostics redacted.
- If the user interrupts a streaming assistant answer after visible text has
  arrived, Ant Code preserves that text as an interrupted draft in the TUI and
  local transcript. It is explicitly marked non-final so future turns can
  understand what was interrupted without confusing it with a completed answer.
- Final assistant output health-check code exists but is currently disabled by
  default. Do not re-enable automatic rewrite/retry behavior without explicit
  user approval; it adds another model round and can affect stability in long
  tasks. Keep gateway/context diagnostics active instead.
- Subagents are one-shot task agents by default, but their default budgets are
  now sized for long delegated work. Long child tasks should still return a
  partial summary plus a continuation prompt when they truly need another
  episode instead of acting like a long-lived chat peer.
- The coordinator should route child work by purpose, difficulty, risk, model
  tier, and budget. Lightweight read-only work can use cheap/default models;
  high-risk or deep tasks can use strong models when configured.
- `junior` is the bounded executor profile. It must receive a write scope before
  writing files. `reviewer` is the strict read-only review profile.
- Provider-exposed thinking/reasoning deltas are hidden by default. `/thinking`
  can expose raw thinking in the TUI, including restored local transcript
  records. Raw thinking is persisted under the local session transcript policy
  so `/resume` can recover it, but it must not be uploaded or included in
  print/JSON event output.
- Startup, `/status`, `/map`, and the model system context include workspace
  diagnostics. If cwd only contains `.lab-agent` or `.ant-code` runtime data,
  tell the user local tools and child agents will inspect only that runtime
  directory unless they launch from, or explicitly provide, the target project.
- On Windows, TUI startup attempts to switch the console code page to UTF-8 and
  restore it on exit. Stored session JSON is UTF-8; mojibake usually means the
  terminal display/copy path decoded text incorrectly.
- Parent-agent delegation is no longer prompt-only. `src/agents/delegation-guard.js`
  watches broad parent web/repository exploration during a turn. If the parent
  repeatedly uses `web_search`, research-like `web_fetch`, broad `glob`/`grep`,
  multiple `read_file` calls, or shell-wide scans without `agent_run`, the guard
  appends an `[Ant Code delegation guard]` reminder to the tool result and records
  a `delegation.guard` audit event. Keep this reminder model-visible; hook audit
  alone is not enough because the model would not see it.
- Do not apply delegation guard to subagent-internal tools. Child agents already
  have focused prompts and budgets; the guard is for the parent coordinator only.
- `agent_run` supports background task groups. For broad or slow delegated work,
  the coordinator should call `agent_run` with `background=true`, a shared
  `groupId`, `waitForGroup=all` or `any`, `wakeParent=true`, and a concise
  `wakeReason`. The immediate tool result only says the task started; the child
  continues in the background and writes `.lab-agent/tasks/` plus
  `.lab-agent/task-groups/` records.
- Background group completion creates a short model-visible continuation prompt.
  The TUI auto-runs it when idle and queues it when busy. Full child output must
  stay in task detail/excerpt views; wake prompts should contain summaries and
  ids, not raw transcripts.
- Background subagent status wording is intentionally split. A successful
  `agent_run background=true` tool result means the child task was accepted and
  is running, not that the child task finished. The TUI should show
  "子任务后台运行中" / "子任务组后台运行中" until the group reaches its wait condition
  and queues the parent wake prompt.
- TUI exit protection is intentional. If background tasks are running, Ctrl+C or
  `/exit` must confirm, cancel background controllers, wait for them to stop,
  and only then allow a real process exit.
- Review gate is a reminder gate, not a hard policy gate. It is stage-based:
  plan review after a large todo/plan is created before execution, delivery
  review after many workflow items are completed, and exception review after
  complex subagent/tool work returns partial/blocked/failed. Do not reintroduce
  file-count or keyword-only triggers; they were too noisy for routine diagnosis
  and quick iteration.
- Dashboard is designed for lab users who do not like TUI. It should stay clean,
  dark-gray, local-first, and low-noise: no repeated empty "generating" cards,
  no raw system/developer/tool messages in the chat, no TUI-only UX language in
  model context, and no complex slash-command requirement for common WebUI
  interactions.
- Dashboard top chrome is a thin local status bar. It should say
  "本地通用智能体" and show a compact idle/running/waiting/error/done status
  marker. Conversation titles belong in the left thread list, not in the center
  chat header.
- Dashboard Todo/Plan progress should stay visible as a thin strip below the
  local status bar and above the transcript scroll area. Clicking it expands
  full Todo/Plan details; the transcript can keep its lighter workflow summary.
- Dashboard color direction is graphite/dark gray with restrained cool gray and
  cool green accents. Running dots are green, workspace permission is yellow,
  full access is red, and right-pane muted text must remain readable.
- Dashboard empty state currently says "我将全力配合你的工作". Keep that tone:
  companionable and work-ready, not a form instruction.
- Dashboard rich rendering is report-oriented, not code-review-heavy. Assistant
  replies and right-pane Markdown/data previews support local KaTeX math,
  Mermaid diagrams, JSON/YAML trees, CSV/TSV data tables, image galleries with
  lightbox navigation, and folded long-content tables of contents. Keep user
  prompts mostly plain text. Rich renderers must use local bundled assets only,
  never CDN scripts or fonts, and every renderer must preserve a raw-text
  fallback. Mermaid must initialize with `suppressErrorRendering: true`; invalid
  Mermaid should stay as a local "流程图无法渲染，可查看原文。" fallback inside the
  block, not create a Mermaid error diagram at the bottom of the page.
- Dashboard streaming assistant drafts must remain lightweight. Draft chunks are
  throttled and rendered with `renderMarkdown(..., { lightweight: true })`;
  heavyweight tables, KaTeX, Mermaid, structured data previews, image galleries,
  file-reference scanning, and rich hydration should wait for final assistant
  messages or right-pane previews so the browser remains interactive during long
  generations.

Latest full verification:

```powershell
node --test tests\unit\dashboard-events.test.js tests\unit\dashboard-files.test.js tests\unit\dashboard-markdown.test.js tests\unit\dashboard-rich-assets.test.js tests\unit\dashboard-structured-data.test.js tests\unit\dashboard-permissions.test.js tests\unit\dashboard-runtime.test.js tests\unit\dashboard-server.test.js tests\unit\dashboard-ui.test.js
node --check src\dashboard\public\app.js
node --check src\dashboard\public\markdown.js
node scripts\check-syntax.js
git diff --check
```

Result on 2026-05-14 after Dashboard streaming draft lightweight rendering:
Dashboard targeted tests passed, syntax check passed for 179 files, static diff
check passed, and `src/cli/tui.js` / `src/cli/tui/` had no diff.

## Architecture Map

Important paths:

- `src/cli/index.js`: CLI entrypoint and default command routing.
- `src/cli/tui.js`: main Ink TUI shell and runtime wiring.
- `src/cli/tui/`: TUI layout, rendering, panels, input, scroll, palettes, and
  interaction helpers.
- `src/dashboard/`: local Dashboard WebUI server, event mapping, permission
  bridge, shared session/history access, and file preview helpers.
- `src/dashboard/public/`: browser UI for Dashboard.
- `src/dashboard/public/vendor/`: checked-in local Dashboard rich-rendering
  bundle and KaTeX font/CSS assets generated from reviewed npm dependencies.
- `src/dashboard/vendor/`: source entry used by the Dashboard vendor build.
- `src/core/session.js`: interactive/print session orchestration.
- `src/core/workspace-diagnostics.js`: source-marker and runtime-data cwd
  checks used by TUI, `/status`, `/map`, and model system context.
- `src/core/context-window.js`: token budget, compaction, model-summary
  fallback, and context summaries.
- `src/context/builder.js`: system context and model behavior protocol.
- `src/model-gateway/`: lab gateway client, OpenAI-compatible adapter path, and
  streaming normalization.
- `src/tools/`: local tool definitions and runtime permission integration.
- `src/hooks/`: local hooks runtime, event matching, builtin hooks, command
  hook execution, current-process audit store, and `/hooks` report formatting.
- `src/tools/web-tools.js`: built-in `web_fetch` and `web_search`.
- `src/tools/document-tools.js`: lightweight local document intake for text,
  HTML, and Office zip formats.
- `src/permissions/`: workspace, secret-path, command, and network policy.
- `src/commands/registry.js`: single source for slash command and keybinding
  metadata.
- `src/commands/runtime.js`: slash command execution.
- `src/capabilities/registry.js`: capability inventory for built-in tools, MCP,
  skills, and agents.
- `src/agents/`: agent profiles, runner, internal agents, task store, and
  worktree isolation.
- `src/agents/router.js`: orchestration-v2 router for purpose/difficulty/risk,
  model tier, budget, and review recommendations.
- `src/agents/budget.js`: child task budget resolution and budget trackers.
- `src/agents/context-pack.js`: bounded context packs for one-shot subagents.
- `src/agents/contracts.js`: output contracts for findings, plans, patches,
  verification, review, and partial continuation.
- `src/agents/continuation.js`: partial result and continuation prompt helpers.
- `src/agents/review-policy.js`: high-risk review recommendation helpers.
- `src/agents/orchestrator.js`: parallel read-only subtask orchestration and
  task-tree formatting.
- `src/agents/task-group-store.js`: background subagent task group records and
  group status aggregation.
- `src/agents/background-registry.js`: current-process background agent
  controller registry used by TUI exit and `/agents cancel-group`.
- `src/agents/wakeup.js`: short continuation prompt builder for completed
  background task groups.
- `src/skills/`: local skill registry.
- `src/mcp/runtime.js`: persistent stdio MCP runtime.
- `src/mcp/recommended.js`: disabled-by-default no-key MCP recommendations.
- `config/skills/`: checked-in local lab-owned skills.
- `lab-agent.config.json`: local project config for this repo.
- `config/lab-agent.lab-template.json`: lab rollout template.
- `config/lab-agent.high-sensitivity-template.json`: restricted template.
- `docs/plans/README.md`: plan archive index and rules for future major
  changes.
- `docs/plans/active/`: plans awaiting review or not fully implemented.
- `docs/plans/completed/tui-agent-architecture-upgrade-plan-2026-04-30.md`:
  completed TUI/agent architecture upgrade plan and stage status.
- `docs/deployment/v1.3-agent-extension-acceptance.md`: current acceptance
  record.
- `PROJECT_CHANGELOG.zh-CN.md`: human-readable Chinese project history.

Maintenance records and model-adapter handoff:

- `PROJECT_CHANGELOG.zh-CN.md`: append user-visible product and architecture
  changes here first. Use Chinese, newest entry at the top, and include
  motivation, changed scope, verification, and remaining risks.
- `docs/specs/lab-model-gateway-protocol.md`: canonical client-to-gateway
  protocol for lab-owned/provider-independent adapters and OpenAI-compatible
  adapter mode.
- `docs/specs/lab-model-gateway-compatibility-matrix.md`: compatibility matrix
  for gateway protocol behavior and supported adapter features.
- `docs/deployment/model-adapter-gateway-readiness.md`: operational checklist
  for model adapter owners: endpoint variables, security boundary,
  compatibility evidence, and rollout questions.
- `docs/deployment/lab-gateway-rollout-checklist.md`: rollout checklist before
  broad lab use.
- `src/model-gateway/client.js`: runtime gateway client used by sessions.
- `src/model-gateway/openai-chat.js`: OpenAI Chat Completions compatible
  request/response normalization.
- `src/model-gateway/protocol.js` and `src/model-gateway/streaming.js`:
  provider-independent request/response and streaming normalization.
- `scripts/verify-gateway-compat.js`: mock/live gateway compatibility check
  used by release and adapter readiness evidence.

## Runtime Flow

At a high level:

1. CLI loads config from environment and local config files.
2. TUI, Dashboard, or print mode creates a session.
3. The context builder injects the Ant Code behavior protocol, workspace
   diagnostics, local memory, available tools, agents, skills, MCP boundaries,
   and the current client surface. Dashboard sessions must say `Client surface:
   dashboard WebUI`; do not let TUI-only display limits leak into WebUI model
   context.
4. Model requests are sent to the configured lab gateway.
5. Tool calls returned by the gateway execute locally through the permission
   engine.
6. Tool results are bounded, redacted where needed, and returned to the model
   loop.
7. Before each following gateway round, old in-flight tool output may be
   compacted when the full prompt estimate approaches the configured context
   budget.
8. Final visible assistant output health retry is disabled by default. If it is
   explicitly re-enabled in the future, it should remain one-shot only.
9. Session metadata persists bounded counters, summaries, gateway round
   diagnostics, provider usage when available, output health records, and recent
   messages according to transcript policy.

Dashboard process lifetime:

- `ant-code dashboard` is a foreground local server by default.
- Users can stop it from the WebUI sidebar with the "关闭 Dashboard" confirmation
  action, which calls the local shutdown endpoint and exits the dashboard
  process.
- Users can also stop it with `Ctrl+C` in the terminal that launched it.

Dashboard UI behavior:

- Running-only statuses such as thinking, model request, streaming, and routine
  tool start should update the fixed live status strip above the composer, not
  append repeated empty cards to the transcript.
- Visible assistant text deltas should stream into temporary draft cards in the
  transcript by model round. Do not join different rounds into one long draft.
  When the final assistant reply arrives, collapse those draft cards into a
  folded draft record and leave the final reply as the primary message.
- For lab-agent-gateway SSE/NDJSON streams, the gateway parser must dispatch
  complete records as they arrive. Reading the whole stream before parsing makes
  Dashboard drafts appear only at the end, which breaks the intended UX.
- Provider thinking/reasoning deltas are not visible drafts. Keep them hidden
  behind status-only UI.
- Requirement clarification is separate from permission approval. Dashboard
  should surface `ask_user` as a question panel above the composer, support
  choices and optional custom text, and resume the same tool round through the
  `userInputCallback` result.
- Dashboard has an explicit workspace trust gate above the composer. Do not
  start a model turn before the current local workspace is trusted; high
  sensitivity sessions require a per-process confirmation even when a trust
  record already exists.
- While a Dashboard turn is running, pressing Enter in the main composer queues
  the new prompt for the same session. The send button itself changes to a
  running/interruption affordance; clicking it interrupts the active turn.
- The Dashboard queue panel owns the "引导对话" action. It should turn the
  current composer text, or the first queued prompt when the composer is empty,
  into guidance for the active turn, enqueue that guide prompt ahead of ordinary
  queued prompts, and interrupt the active turn so the guide can continue next.
  Queue rows may also expose a small guide action for choosing a specific queued
  prompt. Do not expose this as a slash-command requirement in the WebUI.
- After a Dashboard guide click, keep explicit feedback in the queue panel:
  registering, interrupting/current-turn boundary, and continuing states should
  be visible there without appending extra transcript messages.
- Dashboard context clear and context compact actions require an in-page
  confirmation panel and should call the same context helpers used by the TUI.
- `agent_run` while active appears as a live subtask chip. Finished or failed
  meaningful work may be summarized later in the folded process record.
- Todo/plan state is not noise. Dashboard should show it as a single lightweight
  workflow progress panel in the transcript and update that panel in place when
  `workflow_snapshot` events arrive.
- Dashboard image previews in the right pane should be inspectable: clicking an
  image opens a dark lightbox, with close button, backdrop click, and Esc close.
  These previews are browser-side file display, not model visual input. Unless a
  future tool or gateway response explicitly supplies image content to the
  model, do not claim Ant Code inspected PNG/JPG pixels.
- Dashboard Markdown/text previews in the right pane should use an obvious
  scrollable document surface so long files can be dragged and read in full.
- Dashboard right-pane previews are session and document scoped. When switching
  sessions or starting a new task, clear stale preview content. When rendering a
  Markdown file preview, resolve its relative images, local file links, and
  plain file references from that Markdown file's directory, not blindly from
  the Dashboard process cwd. Local file links should stay inside the Dashboard
  right-pane preview flow; unknown bare domains such as `example.com` should not
  become local file buttons.
- Dashboard assistant replies and `.md` previews should render basic Markdown,
  including pipe tables. Keep user prompts mostly plain text so pasted content
  stays easy to scan and does not turn into unintended rich layout.
- Dashboard transcript history must only show user/assistant messages in the
  main conversation. Internal roles such as system, developer, and tool are
  context for Ant Code, not user-facing chat bubbles.
- Dashboard Markdown rendering should keep growing beyond TUI constraints:
  links, inline images/lightbox, task lists, blockquotes, copyable code blocks,
  and diff highlighting are expected first-class WebUI behavior.
- The transcript should stay sparse: user prompts, visible temporary drafts,
  final replies, approvals, errors, todo/plan progress, and folded process
  summaries when useful.

Background subagent wakeup flow:

1. The parent model calls `agent_run` with `background=true`.
2. The runtime creates or updates a task group and starts the child with an
   independent `AbortController`.
3. The immediate tool result returns `taskId`, `groupId`, and running status.
4. The child task writes normal task records as it runs.
5. When the group satisfies `waitForGroup`, the runtime writes `wakePrompt` and
   emits `subagent_group_wakeup`.
6. The TUI runs the wake prompt immediately if idle, or queues it if another
   turn is active.
7. `/agents group`, `/agents wake`, and `/agents cancel-group` provide manual
   inspection, wake, and cancellation paths.

## Hooks Runtime

Hooks v1 is implemented as a local, auditable runtime layer. It is not a remote
plugin market and it must not become a telemetry channel.

Supported events:

```text
session.start
session.end
user.prompt
tool.before
tool.after
tool.failed
permission.denied
file.changed
todo.updated
subagent.started
subagent.completed
subagent.failed
subagent.paused
subagent.group.started
subagent.group.completed
subagent.group.wakeup_queued
delegation.guard
review.gate
compact.before
compact.after
```

Key modules:

- `src/hooks/events.js`: event names, blocking event rules, path matching,
  payload summaries, and redaction.
- `src/hooks/registry.js`: merges default builtin hooks with `config.hooks`
  entries and validates hook config.
- `src/hooks/runner.js`: executes builtin and command hooks with recursion
  protection, timeouts, output caps, and environment allowlisting.
- `src/hooks/builtins.js`: audit hooks plus `recordSensitiveFiles`
  (`denySensitiveFiles` remains as a compatibility alias).
- `src/hooks/audit-store.js`: current-process ring buffer for recent hook
  records.
- `src/hooks/report.js`: human-readable `/hooks` output.

Default behavior:

- Builtin audit hooks are enabled by default.
- `record-sensitive-files` records secret-like file paths in `tool.before` and
  then leaves the final decision to the permission engine.
- Secret-like file reads and writes are not silently allowed. They require a
  sensitive strong-confirmation approval, even when general workspace edit
  approval is active. Readonly sessions still deny sensitive writes.
- `write_file` and `edit_file` redact diffs for secret-like paths, so approved
  key rotation does not echo old or new secret values through tool results.
- Command hooks are skipped unless the caller passes `hooksTrusted=true` /
  slash command `trusted=true`. The TUI passes this only after workspace trust.
- Command hooks receive a scrubbed env allowlist. Secret-like env names are
  filtered even if mistakenly allowlisted.
- Non-blocking command hooks run asynchronously after being scheduled, so
  validation hooks such as `npm run check` do not hold the model/tool turn.
- `/hooks` shows non-blocking command hooks as `running` while the process is
  still active, then updates the same audit record to `completed` or `failed`.
  Background hook child processes and timers are unref'ed so they should not
  keep Ant Code alive during shutdown.
- Only `tool.before` may block, and only when a hook explicitly sets
  `blocking: true`. Permission-denied, compact, file-changed, todo, session, and
  subagent hooks are audit/automation events, not hard gates.
- `/hooks` shows hook registration and audit state. `/logs` can also inspect
  `/hooks` command output, but hook records are not stored in transcript
  metadata.

Common pitfall: do not wire hook commands through the normal tool runtime, or
they can recurse and inflate tool logs. Use `runHooks` directly and let
`runner.js` enforce recursion protection.

Common pitfall: do not reintroduce hard-deny behavior for `.env` maintenance.
The product policy is practical permissioning: ask loudly for sensitive access,
then honor the user's approval while keeping generated diffs redacted.

Common pitfall: do not describe `bypassPermissions` as raw bypass. It is the
TUI/legacy internal enum behind the user-facing "自动同意" mode. That mode
auto-allows workspace-internal non-sensitive writes and ordinary local mutating
commands only. Workspace-outside writes, suspicious secret paths, high-risk
commands, and network-capable commands must still be blocked or explicitly
confirmed. For CLI automation, `--auto-approve` sets the same workspace write
and command approvals.

Common pitfall: do not make default hooks synchronous policy gates. Hooks should
record, normalize, or kick off background validation by default. Blocking should
be rare and local to a `tool.before` preflight that prevents a concrete unsafe
operation.

Common pitfall: do not make background `agent_run` bypass permissions. The
background path must run the same launch approval and child policy derivation as
the synchronous path. `fullAccess`, workspace approval, and plan mode must keep
their existing semantics.

Common pitfall: do not drop `allowedHosts` when creating nested MCP runtimes.
Both the main session and child/subagent MCP runtime must receive
`networkMode` and `allowedHosts`; otherwise `approved-web` falls back into
spurious approval prompts for network MCP tools.

Common pitfall: do not scrub shell command secrets in `fullAccess` mode. The
normal and workspace modes should keep secret-looking env vars out of child
shells, but full-access is the explicit test-machine mode and must let shell
commands inherit the runtime environment. MCP child processes are different:
they still rely on per-server `envAllowlist` because they may launch third-party
stdio servers.

Common pitfall: do not store full child transcripts in wake prompts. Wake prompts
are model-visible continuation nudges, so keep them short and point to task ids.
The detailed output belongs in `.lab-agent/tasks/` and the TUI excerpt/detail
views.

Common pitfall: do not add prompt-only review gate triggers for words like
`token`. Resume/compaction tests and real user prompts can mention redacted
tokens as text. Review gate should be tied to real task activity such as writes,
partial/blocked tools, workflow changes, or explicit high-risk work.

## External Capability Layer

Stage 1-10 of the external-capability and orchestration upgrade has landed. The
agent now exposes:

- `/capabilities`: inventory for built-in tools, MCP servers, local skills, and
  subagent profiles.
- `/mcp doctor`: disabled recommended MCP entries plus live checks for enabled
  stdio servers.
- `/skills doctor`: bundled skill pack checks.
- `web_fetch`: stable public fetch tool. Runtime is MCP-first by default: it
  tries the configured `fetch` MCP and falls back to the built-in bounded
  HTTP(S) fetcher when MCP is unavailable. Set `web.fetchProvider` to `builtin`
  or `mcp-only` for explicit behavior.
- Built-in `web_search`: SearXNG when configured, DuckDuckGo HTML fallback
  otherwise. Search is best-effort and still controlled by network policy.
- Built-in `document_intake`: local extraction for text, Markdown, JSON, CSV,
  XML, HTML, and lightweight DOCX/PPTX/XLSX zip XML content. PDFs require an
  external converter such as MarkItDown through a skill workflow.

Bundled local skills:

- `web-research`
- `browser-automation`
- `document-intake`
- `project-intake`
- `bug-repro`
- `frontend-verifier`
- `release-review`

Recommended no-key MCP servers are configured in this repo. Self-contained
entries may be enabled by default in `lab-agent.config.json`; service-bound
entries such as SearXNG and SQLite remain disabled until configured:

- `fetch`
- `duckduckgo-search`
- `searxng`
- `playwright`
- `memory`
- `filesystem`
- `sequential-thinking`
- `sqlite`

Common pitfalls:

- Do not assume MCP servers are available just because they are listed; check
  enabled state and `/mcp doctor`.
- Do not assume an enabled MCP server means its tools can run silently. Network,
  browser, memory writes, filesystem writes, and unknown MCP tools still require
  the appropriate policy decision or user approval.
- Do not treat `web_fetch` as purely built-in anymore. It is intentionally a
  compatibility wrapper around the preferred fetch MCP with a built-in fallback;
  keep both permission paths in sync when changing network policy.
- Network MCP tools should declare concrete URL/provider hosts to the permission
  engine. `fetch`-style tools extract `url`/`uri` arguments; DuckDuckGo/SearXNG
  search tools use their provider host. Missing host data causes an approval
  prompt in `approved-web` and can look like a false block in background agents.
- `web_search` results can be rate-limited or sparse. Cite fetched URLs and say
  when search quality is weak.
- `document_intake` is intentionally lightweight. Use a dedicated converter for
  scanned PDFs, complex tables, or rich slide decks.
- Subagent profiles now include v2 metadata: `triggerHints`, `skills`,
  `mcpServers`, and `outputContract`.
- The built-in `build` profile is the parent coordinator doctrine, not a
  normal child profile. It is hidden and internal-only: `/agents`, normal
  `agent_run`, and normal `runSubagent` calls should not expose or launch it.
  Internal callers that intentionally run hidden agents must opt in explicitly
  (`includeHidden` / `allowHiddenProfile`), as `skill_run` fork agents do.
- All write-capable child profiles require an explicit `writeScope`. If it is
  missing, runtime removes write tools, shell tools, mutating workflow tools,
  `mcp_call`, and `skill_run`, and forces the child policy to readonly even if
  the parent session allows writes. Prompt wording and runtime permissions must
  stay aligned here.
- `browser-verifier` uses browser-risk approval at the `agent_run` boundary.
  Do not downgrade it to generic read/execute approval just because the concrete
  browser action may be routed through shell or MCP.
- Keep each profile `outputContract.required` aligned with the fields named in
  that profile's natural-language Return instruction. The task sidebar and
  parent synthesis rely on stable structured summaries.
- Subagents inherit the parent cwd. Launching from `E:\tmp-file` is valid if
  that is the target project; if it only contains `.lab-agent` runtime data,
  child agents will correctly inspect only runtime data.
- Tool rounds are a safety bound for model-tool loops, not an answer length
  limit. Main turns have no default `limits.maxToolRounds`; the user can watch
  the TUI and interrupt manually. Subagents use profile/budget-specific limits
  by default, and project `agents.maxRounds: null` means "do not apply a global
  clamp over profile budgets".
  `LAB_AGENT_MAX_TOOL_ROUNDS` and `LAB_AGENT_AGENT_MAX_ROUNDS` can still add
  deliberate manual fuses for debugging or constrained environments.
- For broad work, the main coordinator prompt tells the model to create
  todo/plan state, launch 2-3 readonly `agent_run` tasks first, synthesize their
  findings, then delegate scoped `junior`/`code-worker` implementation slices
  with explicit `writeScope` and acceptance criteria.
- The main system prompt now carries an explicit coordinator control loop:
  `intake -> classify -> plan -> delegate readonly exploration -> synthesize ->
  implement scoped slices -> verify -> review -> report`. Keep that doctrine
  intact when editing prompts; it is what makes the strong parent agent behave
  like a long-task orchestrator rather than a single chat worker.
- Built-in profile prompts are intentionally more detailed than simple role
  labels. Each profile declares how it should map evidence, conserve context,
  handle partial/budget states, and hand work back to the parent. Do not shrink
  them to one-line personas during cleanup.
- `agent_run` accepts `purpose`, `difficulty`, `risk`, and `modelTier`. If a
  caller marks a task as `difficulty=deep` or `risk=high` without a model tier,
  runtime routing promotes it to the configured `strong` tier.
- `/agents route <task>` explains which profile should handle a task and why.
- `/agents orchestrate <task>` starts parallel read-only child tasks when the
  route is safe to parallelize, then records a parent task tree. Write-capable
  and execute/browser tasks remain serial suggestions unless explicitly run.
- Profile-scoped subagents can only see declared MCP servers and declared
  skills when those fields are present.

## Agent Orchestration Notes

Built-in user-facing profiles:

- `explorer`: read-only repository and call-chain investigation.
- `readonly-researcher`: legacy-compatible read-only research alias
  (`research`, `researcher`).
- `web-researcher`: external web/search/fetch work with source summaries.
- `planner`: staged plans and validation routes.
- `verifier`: local test/failure verification.
- `browser-verifier`: browser/frontend acceptance using Playwright-capable
  paths when approved.
- `code-worker`: scoped edits under parent permission policy.

The router prefers specialized profiles: web prompts route to
`web-researcher`, browser/frontend prompts route to `browser-verifier`, broad
codebase prompts route to `explorer` and `planner` first, and implementation
prompts keep `code-worker` as a serial/write-capable suggestion.

Task records live under `.lab-agent/tasks`. The right TUI panel and
`/agents tasks` render a task tree. Child task full output stays in task
records; the main chat should show task IDs and concise findings.

Orchestration deliberately starts only read-only parallel child tasks. This is
to avoid concurrent edits, hidden browser actions, and ambiguous permission
prompts. Use explicit `/agents run code-worker ...` or normal model tool calls
for edits after the read-only findings are available.

## Permission And Audit Notes

Risk classes currently include:

- `read`: workspace-bounded read-only tools.
- `write`: file edits and workflow state writes.
- `execute`: PowerShell/bash commands.
- `network`: web fetch/search and network-capable actions.
- `browser`: browser automation actions that may expose page/session state.
- `document`: bounded local document extraction.
- `mcp`: unknown or generic MCP operations.
- `memory`: local long-term memory reads/writes, with writes requiring approval.

MCP child processes use a scrubbed environment by default. API keys, tokens,
passwords, OAuth variables, SSH auth sockets, AWS variables, Anthropic/OpenAI
keys, and similar secret-looking variables are removed before spawn unless the
server config explicitly lists them in `envAllowlist`/`envAllow`.

Common development traps:

- Do not call `agent_run` recursively from a subagent; `runSubagent` removes
  `agent_run` from child tool definitions.
- Do not make `build` visible or launchable as a child agent. It has broad
  coordinator tools and is meant to shape the main system prompt, not to become
  a near-parent nested worker.
- Do not relax write-capable child agents by prompt text alone. If a profile
  can write, runtime must require `writeScope`; otherwise prompt and permission
  behavior drift apart under long tasks.
- Do not reintroduce a low project-level `agents.maxRounds` unless you
  intentionally want to clamp every built-in and custom profile. Prefer
  `agents.budgets.<profile>` or `<profile>.<difficulty>` entries so cheap
  research, deep implementation, and review can have different budgets.
- If the parent model tries to do a very large task alone, check
  `src/context/builder.js` before only raising budgets. The desired behavior is
  coordinator-first: todo/plan, parallel readonly discovery, scoped execution,
  then verification/review.
- If router tests unexpectedly prefer `readonly-researcher`, check scoring
  priority against specialized `web-researcher`.
- If `/agents orchestrate` appears to do nothing, the route may contain only
  execute/write-capable suggestions; use `/agents route <task>` to inspect it.
- If a subagent cannot see a skill or MCP server, inspect its profile-scoped
  `skills` and `mcpServers` fields before changing the global config.
- Subagents must use scan-first repository investigation. Prefer
  `list_files`/`glob`/`grep` before `read_file`, and keep `read_file.maxBytes`
  small. The runner now clamps child tool inputs, but prompts should still ask
  for focused snippets instead of whole-file dumps.
- If `web-researcher` reports `webSearchUnavailable`, configure SearXNG/search
  MCP or provide concrete URLs. Do not retry blind web searches in a loop.
- Avoid using the raw terminal selection for chat copying; message-block
  operations are the intended UX.

## Models And Context

The project config currently defaults to the OpenAI-compatible Token Plan
gateway model alias `mimo-v2.5-pro` with a configured 400k token model window.
The local compaction budget is 256k tokens. The right side panel displays both
the provider/model window and the local compaction threshold. Automatic
compaction is token-budget driven.

`/compact` prefers hidden internal model compaction:

- Internal agent: `compaction`
- Success strategy: model summary
- Fallback: bounded local redacted summary
- Persisted metadata: counts and strategy only, not raw compacted transcript
  text

## TUI Notes

The TUI is currently Ink/React based. OpenTUI was evaluated but not adopted for
this release because the accepted Ink layout works and OpenTUI would add native
dependency and Windows validation risk.

Core TUI behavior:

- Wide terminal: transcript plus fixed right side panel.
- Narrow terminal: chat-first compact layout.
- Scroll routing is region-aware.
- Slash palette and command panels are docked/overlay-like surfaces that should
  not resize or corrupt the prompt.
- `Tab` switches side tabs.
- Left/Right switch side tabs or inspector filters only when the prompt is
  empty.
- `Ctrl+O` cycles transcript detail modes.
- `/thinking` toggles raw provider thinking/reasoning visibility for the
  current TUI session only.
- `Ctrl+T` is an inspector filter fallback.
- `Ctrl+N/P` changes inspector items when available.
- `Ctrl+F/B` scrolls long inspector output.

When changing TUI behavior, run targeted TUI tests and manually smoke test:

- Long answer in large window.
- Long answer in small window.
- Resize while content exists.
- Streaming output while scrolled up.
- `/help`, `/resume`, `/sessions`, slash palette, permissions modal.
- Backspace/Delete and CJK input.

## Slash Commands

Command metadata lives in `src/commands/registry.js`. Keep `/help`,
`/keybindings`, footer hints, and actual behavior aligned with that registry.

Common commands:

- `/help`
- `/status`
- `/model`, `/model list`, `/model use <model-id>`
- `/context`
- `/usage`, `/cost`
- `/files`, `/map`, `/diff`, `/review`
- `/verify suggest`, `/verify run <command>`, `/verify run suggested`
- `/todo`, `/plan`
- `/sessions`, `/resume`
- `/compact`
- `/guide`
- `/agents`, `/agents tasks`, `/agents run <profile> <query>`
- `/background list`, `/background run`, `/background show`,
  `/background cancel`
- `/skills`, `/skills show`, `/skills run`
- `/mcp`, `/mcp tools`, `/mcp prompts`, `/mcp resources`,
  `/mcp read-resource`, `/mcp reconnect`, `/mcp disconnect`

Deferred or disabled cloud-style commands should return clear lab-local
guidance instead of silently failing or invoking remote services.

## Agents

Built-in visible profiles:

- `explorer`
- `readonly-researcher`
- `research` alias
- `planner`
- `verifier`
- `code-worker`
- `junior`
- `reviewer`
- `web-researcher`
- `browser-verifier`

Hidden internal profiles:

- `build` / `default`: parent coordinator doctrine, internal-only and not a
  normal child agent
- `compaction`
- title/summary-style internal agents
- hidden skill child agents

Agent task records include status, parent session id, child session id, profile,
prompt summary, progress, tool summary, output summary, timestamps, and cancel
metadata. Background tasks use independent abort controllers.

Child agent tool calls are intentionally bounded:

- `read_file` gets a small `maxBytes` cap by default.
- `grep` and `glob` get `maxMatches` caps.
- `web_fetch` and `document_intake` get bounded `maxBytes`.
- `web_search` gets a bounded `maxResults`.
- serialized tool results are capped before they are sent back to the child
  model.

These caps prevent the common failure mode where a child explorer reads many
large files and exhausts its output budget before producing a conclusion.

Worktree isolation is explicit and local:

```text
.lab-agent/worktrees/<taskId>
```

Do not enable remote runners unless the lab later provides an explicit reviewed
runner config.

## Skills

Local skills are loaded from configured skill paths, including:

```text
config/skills
C:\saveproject\LBJ-workspace\skill\ant-render-exporter\skills
C:\saveproject\LBJ-workspace\skill\antscan-data-crawl\skills
C:\saveproject\LBJ-workspace\skill\paper_distill_skill_bundle_v6_zh\skills
C:\saveproject\LBJ-workspace\skill\taxonomy-ai-intel\skills
C:\saveproject\LBJ-workspace\skill\unsloth-studio-finetune-portable
```

Checked-in general skills:

- `codebase-orientation`
- `test-failure-triage`
- `release-readiness-review`

External lab professional skills currently registered on this machine:

- `ant_render_batch`
- `ant_render_retry`
- `antscan_incremental_download`
- `paper-distill`
- `taxonomy-ai-intel`
- `unsloth-studio-finetune`

External skill packages may live outside the active coding workspace. Ant Code
can load their `SKILL.md` files through `skills.paths`, but normal file tools
still respect the active workspace boundary. If a skill asks for a bundled
script, use the PowerShell wrapper in that skill and let permissions approve the
shell command; do not assume `read_file` can inspect arbitrary files under the
external skill root.

Supported frontmatter includes:

- `name`
- `description`
- `when_to_use`
- `allowed-tools`
- `argument-hint`
- `model`
- `context`
- `agent`
- `paths`
- `hooks`

`context: fork` means the skill can run through a hidden child subagent. It does
not mean scripts should be executed automatically.

## MCP

MCP runtime is local stdio only. It supports:

- persistent clients
- status
- tool cache
- tools/list and tools/call
- prompts/list
- resources/list
- resources/read
- reconnect
- disconnect
- stderr summaries
- timeout handling
- Windows `npx` normalization through `cmd /c`

Recommended disabled entries:

- `filesystem`
- `memory`
- `playwright`

The high-sensitivity template intentionally has no MCP server entries.

## Storage And Privacy

Local state lives under `.lab-agent/` by default:

- session metadata
- memory
- task records
- optional worktrees

Persisted metadata is bounded. Provider-exposed thinking is stored with retained
assistant transcript messages for local resume/review, but it is stripped from
future model-context requests and remains hidden unless `/thinking` is enabled.
Secrets and full command output should not be written to metadata.

Project memory:

```text
ANTCODE.md
.lab-agent/memory.md
```

`ANTCODE.md` is the preferred stable project-rule file when present; fallback
compatibility files are loaded only when higher-priority rule files are absent.
`.lab-agent/memory.md` is for local user habits and working preferences. When
the user clearly states a durable preference or desired future working style,
append a concise note there instead of merely acknowledging it. Do not store
secrets, credentials, or large raw transcripts in memory files.

## Verification

Default full gate:

```powershell
npm run check
```

Release-oriented commands:

```powershell
npm run verify:install
npm run verify:gateway
npm run verify:readiness
npm run check:release-seal
npm run audit
```

Useful targeted tests:

```powershell
node --test tests/unit/context-window.test.js tests/unit/session.test.js tests/unit/mcp.test.js tests/unit/tools.test.js tests/unit/commands.test.js tests/unit/agents.test.js tests/unit/agent-task-store.test.js tests/unit/tui-workflows.test.js tests/unit/tui-command-panels.test.js tests/unit/tui-inspector.test.js
```

Before reporting success after code changes:

1. Run the smallest relevant tests.
2. Run `npm run check` when the change affects shared behavior or release
   readiness.
3. Update docs and `PROJECT_CHANGELOG.zh-CN.md` for meaningful changes.
4. Confirm no real keys or credentials were added.
5. Confirm MCP recommendations remain disabled unless the user explicitly asked
   to enable them.

## Repeated Pitfalls To Avoid

These issues consumed significant development time. Future agents should read
this section before touching TUI, session, MCP, skills, or install behavior.

### Do Not Work In The Wrong Repository

The active implementation repo is:

```text
C:\saveproject\LBJ-workspace\lab-agent
```

The legacy `ant-code-latest` directory was archived and should not be treated as
the current implementation. If a TUI fix appears to have no effect, first verify
which executable and source path are being launched:

```powershell
where ant-code
Get-Command ant-code
node .\src\cli\index.js tui
```

Do not debug global behavior while accidentally running an older globally
installed package.

### Do Not Reopen The Clean-Room/Leak Boundary By Accident

Even when comparing product behavior against older projects, do not paste or
port legacy source code, prompts, generated bundles, source maps, runtime
assets, or private endpoint wiring into this repository.

Allowed inputs are product-level observations, public docs, lab-owned specs,
tests you write yourself, and clean-room implementation work.

### Do Not Store Gateway Secrets In Files

Never write a real value for any of these into repo files:

```text
LAB_MODEL_GATEWAY_API_KEY
OPENAI_API_KEY
ANTHROPIC_API_KEY
LAB_AGENT_TRANSCRIPT_KEY
```

Examples in docs should use placeholders such as `<adapter-access-token>`.
Tests may use fake strings like `test-secret` only when asserting redaction.

### Do Not Auto-Enable MCP Servers

The recommended `filesystem`, `memory`, and `playwright` MCP entries are
disabled by default. Keep them disabled unless the user explicitly asks to
enable one for a local experiment.

Enabling an MCP server may run `npx`, download packages, spawn a stdio process,
and expose additional local tools. This must remain an explicit lab decision.

High-sensitivity templates should keep the MCP server list empty.

### Always Close MCP Runtimes

MCP stdio servers can leak orphan Node processes if the runtime is not closed.
When adding a new path that creates an MCP runtime, use `try/finally` and call
`close()` after:

- session turns
- slash commands
- subagent calls
- tests

After MCP-related tests, it is useful to inspect processes:

```powershell
Get-CimInstance Win32_Process -Filter "name = 'node.exe'" |
  Select-Object ProcessId,CommandLine
```

### Windows `npx` Needs Special Handling

On Windows/PowerShell, spawning `npx` directly can fail. The MCP runtime
normalizes this to:

```text
cmd /c npx ...
```

Do not remove this behavior when refactoring `src/mcp/runtime.js`.

### TUI Scrolling Is Fragile

The hardest bugs were scroll and resize regressions. Avoid quick local fixes
that only pass one terminal size.

Common failure modes:

- large window renders a duplicate stale frame above the current UI
- small window mouse wheel snaps to top or bottom
- model streaming pulls the user back to the bottom while they read history
- right side panel scrolls with the transcript
- slash palette or `/resume` panel crushes the input box
- resize breaks Backspace/Delete handling
- terminal mouse mode prevents text selection or native scrollback unexpectedly

### Windows TUI Input Mode Incident

On 2026-05-06 the Windows TUI hit a latent input-mode bug after raw
`Shift+Tab` and raw mouse fallback changes. Read
`docs/audit/tui-windows-input-incident-2026-05-06.md` before touching terminal
input, mouse mode, excerpt selection mode, or raw stdin parsing.

Key rules from that incident:

- Treat a spawned PowerShell process as success only when the script exits with
  `status === 0`.
- Try later PowerShell executables such as `pwsh.exe` when `powershell.exe`
  starts but the script fails.
- Set `windowsConsoleInputEnabled` only after the console mode script succeeds.
- Do not enable `1003` arbitrary mouse movement tracking in the main TUI.
- Deduplicate raw and Ink mouse paths so one physical click cannot become two
  transcript clicks.
- Always manually smoke test `Shift+Tab`, single-click highlight, double-click
  excerpt, `Esc` from excerpt, terminal resize, and narrow footer visibility.

Before changing TUI layout or scroll code, inspect these areas:

- `src/cli/tui.js`
- `src/cli/tui/scroll-region.js`
- `src/cli/tui/frame.js`
- `src/cli/tui/input-editor.js`
- `src/cli/tui/components.js`
- `tests/unit/tui-scroll-region.test.js`
- `tests/unit/tui-frame.test.js`
- `tests/unit/tui-input-editor.test.js`
- `tests/unit/tui-command-panels.test.js`

Manual smoke is required for high-risk TUI changes:

- large terminal long answer
- small terminal long answer
- resize large to small and back
- stream while scrolled up
- mouse wheel over transcript
- mouse wheel over right side panel
- `/help`, `/resume`, `/sessions`, slash palette
- Backspace/Delete after resize

### Side Panel Must Stay Independent

The right panel exists so users can watch context, todo, tasks, inspector, and
commands without losing their place in the transcript. Do not make it part of
the transcript scroll height again.

`Tab` and empty-input Left/Right should switch panel tabs without forcing the
main transcript back to the bottom.

### Slash Panels Should Not Crush The Composer

The slash palette, `/resume`, `/sessions`, `/help`, permissions, and question
surfaces should be bounded panels above the composer or explicit modal-style
surfaces. They should not reflow the whole app in a way that narrows the
composer until text spills outside the border.

The `Esc` close hint must remain visually prominent for slash discovery.

### `/help` Is Documentation, Not A Command Picker

The current `/help` panel explains available commands. Users should not expect
Up/Down to select and execute a command from `/help`.

Slash command selection belongs to the slash palette opened by typing `/`.

### Keep Command Copy And Actual Behavior In Sync

When adding or changing a command/keybinding, update the single registry first
and then verify:

- `/help`
- `/keybindings`
- footer hints
- slash palette
- actual key event handling
- tests

Do not advertise shortcuts that only work in a narrow hidden condition unless
the condition is stated clearly.

### `Ctrl+T`, `Ctrl+N/P`, And `Ctrl+F/B` Are Conditional

These shortcuts are mostly inspector conveniences:

- `Ctrl+T`: inspector filter/tab fallback.
- `Ctrl+N/P`: next/previous inspector item when there are multiple items.
- `Ctrl+F/B`: scroll long inspector output.

If the inspector content is short, these may appear to do nothing. Do not treat
that as a bug without checking whether there is enough content or more than one
item to navigate.

### `Ctrl+O` Must Visibly Change Transcript Detail

`Ctrl+O` cycles compact/detail/full transcript rendering. It previously failed
when content was folded but not actually expandable in view.

When touching transcript formatting, ensure long assistant paragraphs, resume
metadata blocks, and folded lines visibly change across all three modes.

### `/guide` Is Not Same-Request Injection

`/guide <message>` does not inject text into an already in-flight model request.
Its accepted behavior is:

1. Wait for the current model response boundary when needed.
2. Interrupt before subsequent tools or the next model request.
3. Queue the guidance prompt at the front.
4. Run the guided continuation next.

`/guide 停止` should cancel instead of creating a continuation prompt.

### Resume Should Show Titles, Not Just IDs

Users cannot choose prior sessions from raw UUIDs. Keep `/resume` and
`/sessions` title-first, with short ids as secondary disambiguators.

Resume should restore retained transcript messages when metadata retention
allows it. Legacy metadata-only sessions may only restore id/turn state.

### Context Display Should Use Tokens

Do not regress the right side context display to message/session counts. The
user requested:

```text
current tokens / configured context window
```

Current Mimo lab model windows are configured as 400k tokens, with local
compaction budget at 256k tokens.

### Compact Should Prefer Model Summarization

The accepted `/compact` behavior is not merely an algorithmic truncation. It
should prefer hidden internal-agent model summarization through the configured
gateway and fall back to local redacted compaction only when the gateway is
unavailable or summarization fails.

The UI/status output should make the strategy visible.

### Requirement Confirmation Uses `ask_user`

Ant Code now has an OpenCode-inspired requirement confirmation path through
the existing `ask_user` tool. Do not add a separate popup architecture unless
there is a strong reason. TUI and Dashboard should both route this through the
same runtime callback semantics.

Use `ask_user` when user requirements are ambiguous or when the model needs the
user to confirm a checklist before a long task. The TUI supports this in the
bottom input area; Dashboard supports it as a question panel above the composer.
Both paths support:

- Plain text answers.
- Single-choice options.
- Multi-choice options with `multiple: true`.
- Optional custom text with `allowCustom: true`.
- `Enter` to confirm and `Esc` to cancel.

Choice entries may be strings or objects such as:

```json
{
  "label": "Keep Chinese-first UI",
  "description": "Use Chinese for common visible interface text",
  "selected": true
}
```

The result keeps backward compatibility with `answer` and `selectedChoice`, and
adds `selectedChoices` plus `customAnswer` when relevant. When choices are
present, the result also includes a `workflowReminder` asking the model to
update `todo_write` and/or `plan_update` before the final answer if the
confirmation starts multi-step work.

### Long Tasks Should Maintain Sidebar Todo State

The right sidebar already has a workflow/todo panel. It is populated from the
session-local workflow state, not from free-form chat text.

For multi-step implementation or review tasks, use:

- `todo_write` for the visible todo list.
- `plan_update` for the step plan.

Workflow item inputs are deliberately tolerant because models often emit
slightly different shapes. `todo_write` accepts `items`, `todos`, `tasks`, or
`list`; `plan_update` accepts `steps`, `plan`, or `items`. Items may be strings
or objects with fields such as `content`, `text`, `title`, `task`,
`description`, `label`, `name`, or `value`.

Workflow status values are also tolerant. Common variants such as `complete`,
`finished`, `success`, `passed`, and `ok` normalize to `completed`; Chinese
variants such as `完成`, `已完成`, `进行中`, `待办`, and `未开始` are also
recognized. Object fields such as `state`, `progress`, `done`, `completed`,
`checked`, `active`, and `running` are accepted because models often emit these
shapes. Models should still prefer the canonical statuses: `pending`,
`in_progress`, `completed`, and `cancelled`.

The sidebar shows todo items, plan steps, recent file changes, and validation
records. If the model only writes a natural-language plan in the chat, the
sidebar will remain empty. The TUI auto-focuses the workflow sidebar after a
successful `todo_write` or `plan_update` tool call.

Important: before the final answer of a multi-step turn, update visible
completed todo/plan items with `todo_write` and/or `plan_update`. There is a
local final-answer fallback that can sync obvious "all completed" cases into the
sidebar, but it is a guardrail, not a substitute for explicit workflow tool
updates.

### Large Paste Handling

The TUI enables bracketed paste mode. Large multi-line pasted text should be
inserted as one draft, not submitted line-by-line. The prompt box compacts big
multi-line drafts into a yellow summary like:

```text
> {12 lines, 860 bytes 粘贴文本}
```

The transcript also compacts large user pasted prompts by default. `Ctrl+O`
cycles detail mode when exact pasted content needs to be inspected. If changing
raw terminal mode, paste handling, or composer rendering, retest multi-line
paste in Windows PowerShell because this area is easy to regress.

### Transcript Telemetry Folding

Successful `gateway`, `tool`, `tools`, routine `turn`, and workflow sync entries
are display telemetry, not the core conversation. In compact mode, the main
chat hides these successful routine entries; in detailed mode, consecutive
routine entries collapse into one summary line; in full mode, they expand.
Blocked, failed, or interrupted tools must remain visible even in compact mode.

Do not remove the underlying events or inspector records just to reduce visual
noise. The folding belongs in TUI transcript rendering.

### Do Not Break Backspace/Delete

Backspace/Delete failed during scroll/resize fixes before. If editing terminal
raw input, mouse parsing, or resize handling, rerun input editor tests and
manually type/delete after resizing the terminal.

### Background Tasks Must Not Block The Main Chat

`/background run` should use an independent `AbortController` and should not
set the main session `busy` state. `/background cancel <task-id>` should update
the task record and abort an in-process controller when present.

### Worktree Isolation Must Be Explicit

Do not create worktrees automatically. Only create them when the user or agent
explicitly requests a worktree/background-isolated path.

Worktrees belong under:

```text
.lab-agent/worktrees/<taskId>
```

### Avoid Runtime Dependency Churn

The release seal reviews runtime dependencies through
`scripts/verify-release-seal.js`, lockfile/shrinkwrap evidence, generated
SBOM/license artifacts, and module provenance markers. Adding runtime
dependencies requires dependency policy updates, lockfile/shrinkwrap refresh,
SBOM/license regeneration, and release-seal evidence.

OpenTUI was evaluated and deferred for this reason, among others.

### `rg` May Fail In This Desktop Environment

`rg` is preferred when available, but on this Windows Codex desktop it can fail
with a WindowsApps permission error. If that happens, use PowerShell
`Select-String` / `Get-ChildItem` fallbacks instead of getting stuck.

### Do Not Clean Or Reset The Worktree Casually

This project often has many uncommitted changes from long-running staged
development. Do not run destructive commands such as:

```powershell
git reset --hard
git clean -fd
git checkout -- .
```

Only remove or revert files when the user explicitly asks and the target is
clearly identified.

### Documentation Must Track Meaningful Changes

For any meaningful feature, architecture, security, or UX change, update:

- `PROJECT_CHANGELOG.zh-CN.md`
- `LLM_ONBOARDING.md` when future agents need to know the new rule
- relevant docs under `docs/deployment`, `docs/provenance`, or `docs/plans`
- tests or acceptance notes when behavior is externally visible
