# Open Tasks

## Recently Closed Or De-Risked

These items were active during the continuation, but are now either fixed or
validated enough to move out of the immediate bug list:

- Small-window scrolling: user had confirmed small-window scrolling, but the
  pinned-side-panel follow-up exposed a regression. The live TUI is now back on
  TUI-owned wheel scrolling by default and needs another manual smoke pass.
- Resume selection/restoration: user confirmed resume is now working for the
  current retained transcript records.
- Resume picker readability: the picker shows session titles first and ids as
  secondary information.
- `Ctrl+O` folded transcript expansion: raw terminal `Ctrl+O` handling was
  added, the toggle runs globally before command-panel handling, and focused
  tests cover folded resume-like content expanding through the real transcript
  viewport.
- `/help` scroll counter: the ambiguous `2-7 / 7` display was changed to
  Chinese row-range text and command-panel scrolling now clamps to the last
  full page.
- `/help` semantics clarified: the panel is read-only command documentation;
  command selection/execution remains the slash palette opened by typing `/`.
- Long-answer idle/completed scrolling: user confirmed mouse-wheel scrolling is
  normal in both small and large windows.
- `/guide 停止` semantics: exact cancel phrases such as `停止` and `stop` now
  interrupt without creating a guided continuation prompt.
- `/guide` checkpoint semantics: while a model response is in flight, guidance
  now waits for `gateway_response`, interrupts before tool execution or the next
  model request, and then runs the queued guide prompt.
- Stage 4 live transcript/streaming acceptance: the user validated long-answer
  streaming, mouse-wheel review, right-side panel stability, and `Ctrl+O`
  compact/detail/full expansion in the real TUI.
- Stage 5 live tool/permission acceptance: the user asked the agent to create,
  write, and read a file; the permission confirmation box appeared and was
  operable before the write.
- Stage 6 live command-surface acceptance: `/help`, `/status`, `/model`,
  `/context`, `/usage`, `/cost`, `/permissions`, `/gateway`, and
  `/keybindings` were accepted as readable and usable command panels.
- Composer deletion regression: Backspace and Delete were fixed through raw
  Ink input handling and the user confirmed both keys work again.
- Stage 7 partial live acceptance: the user confirmed `/sessions` and
  `/resume` can enter previous conversations, and `/guide` can steer the
  conversation normally.
- `/compact` implementation update: the command now prefers a separate model
  summarization request through the configured lab gateway, keeps recent
  messages exactly, and falls back to local deterministic compaction when the
  gateway is unavailable or summarization fails.
- `/compact` live acceptance: the lab operator confirmed the command is usable
  in the TUI. The release posture is model-summary-first with local fallback,
  and broad rollout still keeps live gateway compatibility as the lab-operator
  gate.
- Stage 8 boundary clarification: MCP calls are available only when servers are
  configured. The current readonly subagent does not depend on MCP; it is a
  local slash-command runner using built-in read-only tools.
- Release packaging boundary: `package.json` now declares an explicit package
  file whitelist so local scratch files and machine-local config are not packed
  into the internal release tarball.

## Stage 7-9 Closure Status

This is the current release-facing closure record. Stage 7 is accepted for the
controlled internal build; Stage 8 remains partial but non-blocking; Stage 9 is
ready once final verification and the external package hash are attached.

### Stage 7: File, Session, And Queue Workflows

Automated / already covered:

- [x] File mention parsing, fuzzy/recent candidate ranking, workspace boundary,
  and insertion are covered by `tests/unit/tui-palettes.test.js`.
- [x] Queue helpers for remove, promote, take, prepend, and busy-safe command
  routing are covered by `tests/unit/tui-workflows.test.js`.
- [x] Session metadata title derivation, retained transcript restore, latest
  resume, encrypted/legacy handling, and cleanup are covered by storage/session
  tests.
- [x] `/guide` checkpoint behavior is covered by workflow/session tests: guide
  waits for the gateway response boundary, then interrupts before tools or the
  next model request; stop phrases cancel without creating continuation prompts.
- [x] `/compact` token-driven behavior, model-summary request path, local
  fallback behavior, and context panel output are covered by context/window,
  session, and TUI command-panel tests.
- [x] Shortcut copy is covered by FooterBar and `/keybindings` tests; raw
  `Ctrl+O`, Backspace, Delete, PageUp/PageDown, and mouse sequence parsing have
  unit coverage.

Release smoke and decision:

- [x] Open `/sessions`; confirm readable title-first records, short id
  disambiguation, status/model/turn/message counts, and encrypted/legacy
  fallback messaging.
- [x] Run `/resume latest` and `/resume <unique-visible-id-prefix>`; confirm
  retained user/assistant transcript messages render back into the conversation
  when available.
- [x] While a turn is busy, submit a normal prompt; open `/queue`; delete,
  promote, and run queued prompts. Release decision: covered by automated
  workflow tests and accepted as non-blocking for the current internal handoff.
- [x] Use `@` file mention candidates in a real prompt; confirm fuzzy/recent
  entries insert cleanly and the draft remains editable. Release decision:
  covered by file-mention unit tests and accepted as non-blocking for the
  current internal handoff.
- [x] Run `/guide <message>` during a long task; confirm it registers guidance,
  waits for the model response boundary when needed, interrupts before tools or
  the next model request, and runs the guide next.
- [x] Run `/guide 停止` during a long task; confirm it cancels without creating
  a guided continuation prompt.
- [x] Run `/compact` after a substantial conversation; confirm the command is
  callable and usable. Current behavior prefers model summarization through the
  configured gateway and falls back to local deterministic compaction if needed.
- [x] Perform shortcut release smoke: `Ctrl+O`, `Tab`, `Shift+Tab`, `Ctrl+T`,
  `Ctrl+N/P`, `Ctrl+F/B`, `Ctrl+R/E` when patch data exists,
  `PageUp/PageDown`, `Esc` twice while busy, `Ctrl+G`, and two-press `Ctrl+C`.
  Release decision: targeted live checks plus automated shortcut, raw-input,
  and copy coverage are accepted; patch-file navigation remains conditional on
  patch data.

Stage 7 exit criterion:

- Met for controlled internal delivery on 2026-04-29. Remaining improvements
  are polish/regression-harness work, not release blockers.

### Stage 8: Agent, MCP, And Local Extension Panels

Release posture:

- [x] MCP stdio runtime exists and is tested for server listing, tool listing,
  calls through the permission boundary, and unknown-risk blocking.
- [x] `/mcp` command surfaces configured servers/tools and local call results.
- [x] Readonly subagent profile exists and `/agents run readonly-researcher ...`
  is tested. It uses local built-in read-only tools and does not depend on MCP
  server configuration.
- [x] Write-capable subagents intentionally return
  `AGENT_PROFILE_UNSUPPORTED`; this is covered by tests.
- [x] Slash palette and command runtime expose deferred local-extension states
  for `/skills`, `/tasks`, `/background`, `/branch`, `/rewind`, `/stash`, and
  `/theme` instead of pretending they are implemented.
- [x] Full product panels for MCP/agents/skills and richer task/subagent cards
  remain deferred Stage 8 depth with an explicit non-blocking release decision.

Stage 8 exit criterion for the current internal build:

- Treat Stage 8 as partial but non-blocking: local MCP and readonly agents are
  functional; skills/richer extension panels are explicitly disabled or
  deferred with user-visible reasons.

### Stage 9: Release Hardening

Automated / documentation tasks:

- [x] `npm run check` passed after the latest Backspace/Delete fix with 238
  tests.
- [x] Stage 4-6 live acceptance is recorded in handoff and deployment docs.
- [x] Stage 7-9 TODO ownership is explicit in this document.
- [x] Re-ran `npm run check` on 2026-04-29 after the Stage 7-9 documentation
  refresh and compact/MCP/subagent capability clarification; 239 tests passed.
- [x] Re-ran `npm run check` after upgrading `/compact` to model-summary-first
  behavior with local fallback; 241 tests passed.
- [x] Ran `npm run verify:release` on 2026-04-29; it passed through check,
  install, mock gateway compatibility, readiness docs, release seal, and audit
  generation.
- [x] Refreshed generated audit/release artifacts through
  `npm run verify:release`.
- [x] Record final live smoke outcome in the deployment acceptance summary.
- [x] Record gateway live compatibility evidence or a documented deferral.
  Current deferral: this workstation has no `LAB_MODEL_GATEWAY_URL` or
  `LAB_MODEL_GATEWAY_HEALTH_URL` configured, so mock compatibility passed but
  live gateway evidence must be attached by the lab operator before broad
  model-enabled rollout.
- [x] Record the final candidate commit/package hash outside the package before
  distribution.

Stage 9 exit criterion:

- `npm run check` and release verification pass, remaining live/gateway items
  are recorded, and the final acceptance summary names any deferred Stage 8
  product depth as non-blocking.

## P0: Closed For Current Delivery

The items below are retained as future regression-smoke instructions. They are
not blockers for the current controlled internal handoff.

1. Stage 7 file/session/queue workflow pass
   - Launch the TUI directly from `lab-agent`.
   - Open `/sessions` and confirm the readable title-first picker is still
     usable after the latest input/scroll fixes.
   - Use `/resume latest` or a unique visible id prefix and confirm retained
     transcript messages render back into the conversation when available.
   - While a turn is busy, submit a normal prompt and confirm it appears in the
     queue; open `/queue`, then delete/promote/run queued prompts.
   - Use `@` file mentions and confirm fuzzy/recent candidates insert without
     corrupting the draft.

2. Busy-turn guidance and stop behavior release smoke
   - Start a long-running prompt.
   - While it is streaming or using tools, type:

     ```text
     /guide focus on the smallest patch and run tests first
     ```

   - Expected behavior: while the model is responding, the current response is
     allowed to reach the gateway boundary, then the turn is interrupted before
     tools/next request; guidance appears as a guide event and runs next.
   - Automated session coverage verifies the post-`gateway_response` interrupt
     skips tool execution; live validation in a real long task is still needed.
   - Also test:

     ```text
     /guide 停止
     ```

   - Expected behavior: current turn is interrupted at the same safe boundary
     when possible, and no guided continuation prompt is created.

3. Shortcut release smoke
   - In the live TUI, verify these have visible effects:
     - `Ctrl+O`: cycles compact/detail/full, creates a visible status/event,
       and folds long paragraphs in compact mode. Raw terminal handling and
       transcript expansion tests now exist, but a final physical-terminal
       smoke pass is still useful.
     - `Tab`: cycles wide side panel.
     - `Shift+Tab`: cycles permission mode.
     - `Ctrl+T`: cycles inspector filter.
     - `Ctrl+N` / `Ctrl+P`: inspector item navigation.
     - `Ctrl+F` / `Ctrl+B`: inspector scroll.
     - `Ctrl+R` / `Ctrl+E`: patch-file navigation when patch data exists.
     - `PageUp` / `PageDown`: in-app scroll.
     - `Esc`: closes the top popover first; if no popover is open and the TUI is
       busy, first press shows interrupt confirmation and second press interrupts.
     - `Ctrl+G`: closes the top popover first; if no popover is open and the TUI
       is busy, directly interrupts the active turn.
     - `Ctrl+C`: first press shows confirmation, second exits.
   - Automated shortcut documentation coverage now checks `/keybindings` and
     FooterBar text for the advertised interrupt, inspector, and scroll hints.
   - Resume no longer needs to block the shortcut audit, but a release smoke can
     still include `/sessions`, `/resume latest`, and a unique truncated UUID
     prefix.

4. `/compact` model-summary live validation
   - Unit tests cover token-driven compaction, model-summary request shape,
     fallback behavior, and continued use of the compacted summary.
   - Release acceptance should still confirm, in a real gateway-backed TUI
     session, that `/compact` visibly reports `模型摘要`, keeps recent messages
     usable, and falls back clearly when the gateway is unavailable.

## P1: Engineering Follow-Ups

1. Build a deterministic TUI interaction test for scroll behavior.
   - Partially addressed: unit coverage verifies mouse sequence parsing,
     TUI-owned scroll mode selection, transcript viewport scrolling, and the old
     dormant native-scrollback layout helper.
   - Tests still do not cover real terminal mouse behavior.
   - Consider `node-pty` or a small terminal harness if dependency policy allows it.

2. Decide whether native terminal scrollback should return as an explicit mode.
   - The latest live choice is TUI-owned scrolling by default because native
     scrollback plus pinned side panels caused duplicate/stale frame regressions.
   - If terminal scrollbar history is required later, add it as an explicit mode
     with separate layout constraints rather than mixing it into the default TUI.

3. Improve `/guide` product design.
   - Current implementation is checkpoint-interrupt-and-run-next while a model
     response is in flight, with immediate interrupt still used outside that
     response window.
   - Clearer UI copy now says the command waits for the model response boundary
     before guiding.
   - Consider a queue mode indicator: `Queue` vs `Guide`.

4. Add a right-side context meter polish pass.
   - The status bar, compact summary, side panel, `/context`, and `/model`
     now show estimated tokens and configured model windows.
   - A more OpenCode-like visual meter could still be better.
   - Keep it local and privacy-preserving; do not expose raw hidden thinking.

5. Decide whether deeper non-TUI slash command reports should be localized.
   - Common discovery and TUI surfaces are Chinese-first now.
   - Some diagnostic/report bodies intentionally still expose stable English
     keys or provider/tool terminology for automation and debugging.

## P2: Product Polish Backlog

1. Better live-stream rhythm and task animation.
   - Current stream panel summarizes thinking, draft text, and tool status.
   - It still needs closer "high-quality agent TUI" polish for long tasks.

2. Tool cards and inspector UX.
   - Improve status icons, spacing, and progressive disclosure.
   - Keep terminal text readable in small windows.

3. Theme refinement.
   - User likes the current sky-blue direction.
   - Avoid naming it after the user's anecdote; use neutral names like `sky`.

4. More complete shortcut discoverability.
   - Footer should stay compact.
   - `/keybindings` can carry the fuller list.

5. Packaging readiness.
   - Once manual TUI validation passes, update release/readiness docs if needed.
