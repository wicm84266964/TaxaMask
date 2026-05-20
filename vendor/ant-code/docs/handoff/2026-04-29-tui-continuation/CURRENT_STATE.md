# Current State

## Workspace Clarification

The active continuation repo is `C:\saveproject\LBJ-workspace\lab-agent`.

The sibling path `C:\saveproject\LBJ-workspace\ant-code-latest` is the existing
Ant Code project and the main product/reference baseline for this rebuild.
The clean-room `lab-agent` repository is being built to preserve/replace its
important capabilities, workflows, and interaction quality.

This reference relationship does not mean source copying is allowed. Use
sanitized behavior notes, logs, screenshots, user-described behavior, and the
specification docs in this repo as implementation input. Do not inspect or copy
`ant-code-latest` implementation code while implementing `lab-agent`.

When testing the current implementation, use:

```powershell
cd C:\saveproject\LBJ-workspace\lab-agent
node .\src\cli\index.js tui
```

See `ANT_CODE_LATEST_STATUS.md` for the full warning and debug checklist.

## Worktree State

The `lab-agent` worktree is expected to be dirty. Many modified and untracked
files are the accumulated output of the clean-room rebuild stages, TUI stages,
docs, tests, generated audit artifacts, and handoff package.

Do not run destructive cleanup commands such as `git reset --hard`, `git clean`,
or broad checkout/revert operations unless the user explicitly asks. If a file
was changed in prior stages, treat it as intentional until proven otherwise.

## Latest Confirmed Fixes

The user confirmed these behaviors before this handoff:

- Mouse/native terminal scrolling recovered after terminal mouse tracking and alternate screen behavior were removed.
- `Ctrl+C` exit now works as a two-press confirmation flow.

Additional fixes implemented during the continuation:

- TUI-owned transcript scrolling:
  - After wide pinned-side-panel regressions, the live TUI no longer defaults to
    terminal-native scrollback.
  - Mouse wheel and PageUp/PageDown now drive the TUI transcript viewport in both
    small and large windows.
  - `LogPane` remains fixed-height in the default path so the right-side panel
    can stay pinned and stale/duplicate frames are not pushed into terminal
    scrollback.

- Busy-turn guidance command:
  - `/guide <message>` was added for the TUI.
  - It prepends a guidance prompt to the queue. If a model response is currently
    in flight, it waits for the gateway response boundary, then interrupts before
    tool execution or the next model request, and runs the guidance next.
  - This is a safe checkpoint model for "guide current task"; it is still not
    true live injection into the already in-flight provider request.

- Context length visibility:
  - The top status bar now includes compact token state like `ctx used/window tok c<compactions>`.
  - The compact small-window summary also includes context token counts.
  - The wide status side panel now shows context tokens near the top.

- Shortcut visibility:
  - `Ctrl+O` detail mode now creates a visible transcript entry and status update.
  - A later fix makes `Ctrl+O` fold long assistant paragraphs even when the
    model emitted them without explicit newline breaks; compact mode now shows a
    clear hidden-lines marker and full mode expands the content.
  - Tab, inspector filter, inspector navigation, inspector scroll, and patch-file shortcuts now update activity status.
  - `/keybindings` text now describes mouse wheel and PageUp/PageDown as TUI-owned transcript/panel scrolling.

- Session resume visibility:
  - `/resume <id>` now accepts a unique UUID prefix as well as a full id, path,
    or `latest`, matching what the TUI picker visibly displays.
  - A resumed TUI session now restores bounded retained user/assistant messages
    into `session.messages` and renders them back into the transcript when local
    transcript retention is enabled.
  - The `/sessions` picker now shows a readable session title first, with the
    short id in parentheses as secondary information. New records persist a
    redacted title from the first prompt; older records derive one from retained
    transcript or last prompt when possible.
  - Resume still supports legacy metadata-only records; those restore id/turn
    metadata but have zero retained messages.

Continuation update from the next pass:

- `/guide` copy was tightened across the busy composer hint, footer, and
  `/keybindings` so it no longer implies same-request live injection. It now
  describes the real behavior: interrupt the active turn and run guidance next.
- Footer shortcut text now advertises the real interrupt paths: `Esc` requires
  a second press to confirm while busy, `Ctrl+G` directly requests interrupt,
  and `Ctrl+C` still uses its separate two-press exit confirmation.
- `LogPane` scrollback sizing now has a deterministic helper and unit coverage
  proving small-window scrollback mode expands transcript/live rows without
  fixing the pane height.

Continuation update after live user feedback:

- The user reported that opening the UI in a large window could show a duplicate
  old interface above the current one. `src/cli/tui.js` now clears terminal
  scrollback as well as the visible screen during startup/resize redraws
  (`ESC[3J` + `ESC[2J` + home) to avoid exposing stale frames when the terminal
  grows.
- The user reported that small-window mouse wheel review snapped back while
  trying to inspect middle history. Idle pulse redraws were removed, so the TUI
  no longer re-renders every 260ms while idle.
- After the pinned-side-panel regression, `src/cli/tui/interaction.js` keeps
  native scrollback disabled by default. The live TUI uses mouse reporting and
  in-app transcript offsets for wheel/PageUp/PageDown scrolling.

Continuation update after large-window scroll feedback:

- The user confirmed small-window scrolling is normal, but large-window mouse
  wheel review could only show the latest fixed content. Native scrollback mode
  is now enabled for all terminal heights, and `LogPane` renders the full
  transcript row count instead of capping scrollback transcript rows at 180.
  PageUp/PageDown remain available for in-app review.

Continuation update after Chinese UI localization pass:

- Common visible TUI copy is now Chinese-first for lab users: startup/trust
  prompts, footer hints, command panels, palettes, Inspector labels, streaming
  phase labels, permission/exit prompts, queue/session/resume status entries,
  and `Ctrl+O` folded-content markers.
- Slash command discovery is also Chinese-first: `/help`, `/keybindings`,
  slash palette categories/descriptions, and disabled-command explanations now
  describe the local behavior in Chinese while preserving command names,
  environment variables, tool names, protocol/status identifiers, and stable
  internal keys.
- The change intentionally does not translate runtime interfaces that would
  affect automation or gateway/tool contracts.

Continuation update after context token/window pass:

- Config now has two related but distinct token controls:
  - `models[].contextTokens` / `maxContextTokens` / `contextWindowTokens` describe the configured model window. The default local Ant Code model aliases now expose `200000` context tokens.
  - `context.maxTokens` is the local active-context compaction threshold. It now defaults to `200000` and can be overridden with `LAB_AGENT_CONTEXT_MAX_TOKENS`.
- TUI context display is token-first instead of message/session-count-first:
  - Status bar and compact summary show `used/model-window` tokens when a model window is known, falling back to the local threshold otherwise.
  - The wide status side panel and `/context` panel show both the model window and the local compaction threshold; in the default repo config both are 200k.
  - `/model` and the model picker show context window metadata for configured aliases.
- Context summaries and compaction results now carry estimated token counts, and over-budget compaction considers messages, bytes, and estimated tokens.

Continuation update after model config/context-limit alignment:

- A root `lab-agent.config.json` now explicitly configures the three current
  lab model aliases with `contextTokens: 200000`.
- The repo config also sets `context.maxTokens: 200000`, `maxBytes: 800000`,
  and a high `maxMessages` guard so normal automatic compaction is driven by
  estimated tokens reaching the 200k context limit, not by a 20-message count.
- Automatic `context_compacted` events now include before/after token counts.

Continuation update after resume/detail/help live feedback:

- `/resume` picker and direct resume behavior were retested by the user and are
  working for current retained transcript records. The picker shows readable
  titles first, with the short id as secondary information.
- `Ctrl+O` detail expansion is a real global transcript detail mode
  (`compact -> detailed -> full`). A follow-up patch added raw terminal
  `Ctrl+O` byte handling so terminals that do not report Ink's structured
  `key.ctrl/name=o` event still toggle detail mode. The handler now runs before
  command panels so it remains a global view shortcut.
- The folded marker such as `... 已折叠 8 行；Ctrl+O 查看详细内容`
  is produced by the transcript formatter, not by resume itself. In the current
  behavior, the first `Ctrl+O` expands that 8-line case because detailed mode
  shows up to 80 assistant rows.
- `/help` is currently a read-only command/help panel. It is not a selectable
  command launcher. Use `/` for the selectable slash palette.
- The help/command panel scroll counter was clarified from ambiguous
  `2-7 / 7` text to `显示第 2-7 行，共 7 行`, and command-panel scrolling now
  clamps to the last full page instead of allowing fake positions like
  `7-7 / 7`.

Continuation update after large-window/live-scroll feedback:

- The user confirmed long-answer mouse-wheel scrolling is normal in both small
  and large windows when the turn is idle/completed.
- Recent session metadata showed that `/guide 停止` had been wrapped as a
  "continue the task using this guidance" prompt, so the model continued the
  original project-inspection task. `/guide 停止`, `/guide stop`, and similar
  exact cancel phrases now interrupt the active turn without creating a guided
  continuation prompt.
- TUI-owned scrolling is now the default for narrow, wide, idle, and streaming
  layouts. This keeps wheel input on the TUI viewport instead of terminal
  scrollback and avoids stale duplicate frames above the current view.
- Wide layouts now keep the right-side panel pinned with the current screen
  while the transcript viewport scrolls. This matches the expectation that
  context/status/todo-style side information remains visible while the
  transcript is reviewed.
- A later regression report tied the old duplicate-frame bug to the pinned
  side-panel/native-scrollback split and to notices adding rows without reducing
  the main body height. The current fix subtracts notice/queue rows from the
  body height and keeps the live TUI on the fixed-height TUI-owned scroll path.
- `/guide <message>` no longer aborts an in-flight model response immediately.
  It records a pending guide interrupt, waits until `gateway_response`, then
  aborts before tool execution or assistant-final persistence. `/guide 停止`
  uses the same checkpoint when the model is still responding, but does not
  create a guided continuation.

Continuation update after Stage 4-6 live acceptance:

- The user accepted Stage 4 transcript/streaming behavior in the real TUI:
  long-answer streaming, mouse-wheel review, right-side panel stability, and
  `Ctrl+O` compact/detail/full expansion all passed.
- The user accepted Stage 5 tool/permission behavior by asking the agent to
  create, write, and read a file. The permission confirmation box appeared
  before the write and was operable.
- The user accepted Stage 6 command product surfaces: `/help`, `/status`,
  `/model`, `/context`, `/usage`, `/cost`, `/permissions`, `/gateway`, and
  `/keybindings` were readable and usable.
- Backspace and Delete were fixed through raw Ink input handling after a
  regression in the composer, and the user confirmed both keys work again.

Continuation update after compact semantics review:

- `/compact` now matches the expected product model more closely: it first
  sends older transcript context to the configured lab model gateway for a
  bounded summarization request, keeps the recent messages exact, and stores the
  returned summary as the compacted context used by later turns.
- If the gateway is missing or the summarization response fails/comes back
  empty, `/compact` falls back to the earlier local deterministic summary path
  and records the fallback reason. UI panels show whether the latest compaction
  used `模型摘要` or `本地摘要`.
- Automatic over-budget compaction uses the same model-summary-first path, then
  falls back locally if needed.
- The model's initial context now states that `/compact` prefers model
  summarization, MCP servers are optional, and readonly subagents do not depend
  on MCP.

Final delivery closure update:

- The lab operator confirmed `/compact` is usable in the TUI. The accepted
  behavior is model-summary-first through the configured lab gateway, with
  `本地摘要` fallback and a visible fallback reason when the gateway path is
  unavailable.
- Stage 7 is closed for the current controlled internal build. Sessions/resume,
  `/guide`, `/compact`, long-output scrolling, `Ctrl+O`, command panels, and
  permission flows have direct operator acceptance; queue, file mention, and
  less common shortcut edge cases are covered by automated tests and explicit
  non-blocking release decisions.
- Stage 8 remains partial but non-blocking: MCP stdio and readonly agents are
  functional, while skills/richer extension panels/background/branch/rewind
  depth stays deferred.
- Release packaging now uses an explicit npm `files` whitelist so machine-local
  scratch files and `lab-agent.config.json` are not included in the internal
  tarball.

## Important Files Changed In The Latest Pass

- `src/cli/tui.js`
- `src/cli/tui/command-panels.js`
- `src/cli/tui/components.js`
- `src/cli/tui/format.js`
- `src/cli/tui/interaction.js`
- `src/cli/tui/workflows.js`
- `src/cli/tui/inspector.js`
- `src/commands/registry.js`
- `src/commands/runtime.js`
- `src/config/load-config.js`
- `src/core/context-window.js`
- `src/core/session.js`
- `src/model-gateway/models.js`
- `lab-agent.config.json`
- `tests/unit/commands.test.js`
- `tests/unit/config.test.js`
- `tests/unit/context-window.test.js`
- `tests/unit/tui-command-panels.test.js`
- `tests/unit/tui-frame.test.js`
- `tests/unit/tui-inspector.test.js`
- `tests/unit/tui-interaction.test.js`
- `tests/unit/tui-palettes.test.js`
- `tests/unit/tui-workflows.test.js`

## Verification Already Run

This passed after the latest changes:

```powershell
npm run check
```

The check included syntax, forbidden endpoint scan, provenance, dependency
policy, and all tests. Current test count after the latest compact and release
closure work: 241 passing.

The Stage 7-9 closure pass re-ran the same full check on 2026-04-29, and it
again passed with 238 tests. After the compact/MCP/subagent capability-context
clarification, `npm run check` passed with 239 tests. After upgrading
`/compact` to model-summary-first behavior with local fallback, `npm run check`
passed with 241 tests.

Release verification also passed:

```powershell
npm run verify:release
```

This covered the full check suite, install readiness, mock gateway compatibility,
readiness docs, release seal, and regenerated audit/release artifacts.

Local deployment diagnostics were also run:

```powershell
node .\src\cli\index.js doctor
node .\src\cli\index.js gateway
```

`doctor` completed with expected rollout warnings for this workstation:
`ant-code` is not linked on PATH, `LAB_AGENT_CONFIG` is unset, live gateway URLs
are unset, allowed hosts are not explicitly configured, and local standard-mode
metadata encryption is off. The dry `gateway` command correctly reported that
`LAB_MODEL_GATEWAY_URL` is not configured, so live gateway evidence remains a
lab-operator item before broad model-enabled rollout.

Focused context/token validation also passed:

```powershell
node --test tests\unit\config.test.js tests\unit\context-window.test.js tests\unit\tui-command-panels.test.js tests\unit\tui-frame.test.js tests\unit\commands.test.js
```

This focused run covered model context-window config, `LAB_AGENT_CONTEXT_MAX_TOKENS`,
token-first context panels, model picker/model command context display, and the
native scrollback frame assertions.

Focused model-config/context-limit alignment validation also passed:

```powershell
node --test tests\unit\config.test.js tests\unit\context-window.test.js tests\unit\session.test.js tests\unit\tui-command-panels.test.js tests\unit\commands.test.js
```

This focused run covered the root 200k model config, default 200k compaction
budget, no premature default message-count compaction, and automatic compaction
when the token threshold is reached.

Focused localization/TUI validation also passed:

```powershell
node --test tests\unit\tui-format.test.js tests\unit\tui-frame.test.js tests\unit\tui-command-panels.test.js tests\unit\tui-interaction.test.js tests\unit\tui-inspector.test.js tests\unit\commands.test.js
```

Focused continuation validation also passed:

```powershell
npm test -- tests/unit/tui-frame.test.js tests/unit/tui-format.test.js tests/unit/commands.test.js tests/unit/tui-workflows.test.js
```

The focused run covered footer/keybinding copy, `/guide` workflow helpers, and
small-window scrollback layout budgeting. It does not replace live mouse-wheel
validation in a real small terminal.

Focused `/guide` checkpoint validation also passed:

```powershell
node --test tests\unit\session.test.js tests\unit\tui-frame.test.js tests\unit\commands.test.js tests\unit\tui-workflows.test.js tests\unit\tui-interaction.test.js
```

This focused run covered the new `gateway_response` interrupt boundary, verified
tool execution is skipped after a guide/stop checkpoint abort, and refreshed
footer/keybinding copy.

Focused Esc interrupt confirmation validation also passed:

```powershell
node --test tests\unit\tui-interaction.test.js tests\unit\tui-frame.test.js tests\unit\commands.test.js tests\unit\tui-format.test.js
```

This focused run covered the new two-press Esc interrupt confirmation helper,
FooterBar copy, `/keybindings` copy, and existing bounded TUI format snapshots.

## Known Product Semantics

Busy input currently has two paths:

- Normal prompt while busy: queued and runs after the current turn.
- `/guide <message>` while busy: queues guidance at the front. During an active
  model response, it waits for the gateway response boundary and then interrupts
  before tools or the next model request. Outside that model-response window, it
  interrupts the active turn immediately and runs the guide next.
- `/guide 停止` / `/guide stop`: uses the same boundary behavior when possible,
  but only cancels the current turn and does not enqueue guidance.

True "send guidance into the same active provider request" is not implemented.
That would require provider/runtime support. The current behavior is a
cooperative checkpoint interrupt after the model response returns.
