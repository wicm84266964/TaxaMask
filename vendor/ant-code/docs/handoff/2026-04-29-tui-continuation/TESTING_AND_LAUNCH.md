# Testing And Launch

## Launch The TUI

Use the local repo path explicitly:

```powershell
cd C:\saveproject\LBJ-workspace\lab-agent
node .\src\cli\index.js tui
```

Do not use a global `ant-code` command unless you first verify where it points.

## Full Check

```powershell
cd C:\saveproject\LBJ-workspace\lab-agent
npm run check
```

This passed at handoff time, passed again after the `/resume` and `Ctrl+O`
visibility fixes with 220 tests, passed again after the Chinese UI localization
pass with 223 tests, and passed after the context token/window pass with 225
tests. A follow-up aligned the repo model config and automatic compaction budget
to 200k and passed with 227 tests. The latest resume/detail/help-panel follow-up
passed with 229 tests. The latest wide-layout/live-scroll and `/guide 停止`
follow-up passed with 230 tests. The latest `/guide` checkpoint interrupt
follow-up passed with 231 tests. The latest Esc interrupt confirmation follow-up
passed with 232 tests. The latest Backspace/Delete raw input follow-up passed
with 238 tests. The Stage 7-9 closure pass re-ran `npm run check` on
2026-04-29 and again passed with 238 tests. After the compact/MCP/subagent
capability-context clarification, `npm run check` passed with 239 tests. After
the `/compact` model-summary-first upgrade, `npm run check` passed with 241
tests.

## Release Verification

```powershell
cd C:\saveproject\LBJ-workspace\lab-agent
npm run verify:release
```

This passed on 2026-04-29. It ran the full check suite, install readiness, mock
gateway compatibility, readiness-document verification, release-seal check, and
regenerated the endpoint, SBOM, license, provenance, RC, and audit-report
artifacts.

Additional local deployment diagnostics:

```powershell
node .\src\cli\index.js doctor
node .\src\cli\index.js gateway
```

`doctor` ran successfully with expected rollout warnings: `ant-code` is not
linked on PATH, `LAB_AGENT_CONFIG` is unset, live gateway URLs are unset,
allowed hosts are not explicitly configured, and metadata encryption is off for
the local standard-sensitivity checkout. The dry `gateway` command correctly
reported that `LAB_MODEL_GATEWAY_URL` is not configured. No gateway API key was
written to repository files.

## Focused Tests

```powershell
npm test -- tests/unit/tui-workflows.test.js
npm test -- tests/unit/commands.test.js
npm test -- tests/unit/tui-format.test.js
npm test -- tests/unit/tui-interaction.test.js
node --test tests\unit\storage.test.js tests\unit\session.test.js tests\unit\tui-format.test.js tests\unit\tui-command-panels.test.js
node --test tests\unit\tui-format.test.js tests\unit\tui-frame.test.js tests\unit\tui-command-panels.test.js tests\unit\tui-interaction.test.js tests\unit\tui-inspector.test.js tests\unit\commands.test.js
node --test tests\unit\config.test.js tests\unit\context-window.test.js tests\unit\tui-command-panels.test.js tests\unit\tui-frame.test.js tests\unit\commands.test.js
node --test tests\unit\config.test.js tests\unit\context-window.test.js tests\unit\session.test.js tests\unit\tui-command-panels.test.js tests\unit\commands.test.js
```

## Gateway Configuration

The user has a local model gateway. Do not write API keys into tracked files.

Use environment variables or ignored local config. The gateway URL pattern used in testing was:

```powershell
$env:LAB_MODEL_GATEWAY_URL="http://localhost:8080"
$env:LAB_MODEL_GATEWAY_PROTOCOL="openai-chat"
$env:LAB_AGENT_MODEL="claude-sonnet-4-5-20250929"
$env:LAB_AGENT_CONTEXT_MAX_TOKENS="200000"
```

If an API key is needed, set it only in the local shell or ignored local config.

Model context windows can be configured per alias in `lab-agent.config.json`
using `contextTokens`, `maxContextTokens`, or `contextWindowTokens`. The root
repo config currently advertises `200000` context tokens for all three lab
aliases and sets `context.maxTokens` to `200000`, so automatic compaction happens
when the estimated active context reaches that 200k budget. `context.maxTokens`
or `LAB_AGENT_CONTEXT_MAX_TOKENS` still controls the local compaction threshold.

## Manual Test Prompts

Long answer scroll test:

```text
请详细说明你当前有哪些本地工具能力、权限边界、上下文压缩机制和不能做的事情，尽量分很多段回答。
```

Busy guidance test:

```text
请对当前仓库做一次较长的结构分析，并给出后续 TUI 优化建议。
```

While it is working:

```text
/guide 先不要扩展范围，优先检查小窗口滚动和快捷键反馈。
```

Stop while it is working:

```text
/guide 停止
```

Expected result: the active turn is interrupted immediately or at the next model
response boundary, and no new guided continuation prompt is created. The session
metadata should not show a new prompt that wraps `停止` with "Continue the task
using this guidance."

Checkpoint behavior to verify manually:

- During an active model response, `/guide <message>` should show that guidance
  was registered, wait for the current model response to finish, then interrupt
  before tool execution or the next model request.
- `/guide 停止` should use the same safe boundary when possible, but should not
  enqueue a continuation prompt.

Compact test:

```text
/compact
```

Expected result: with `LAB_MODEL_GATEWAY_URL` configured, `/compact` should
prefer a separate model summarization request, report `模型摘要`, keep recent
messages exact, and use the returned summary as compacted context for later
turns. If the gateway is unavailable or the summarization response fails, it
should report a clear local fallback reason and use `本地摘要`.

Shortcut discovery:

```text
/keybindings
```

Esc interrupt smoke test:

- Start a long-running prompt.
- Press `Esc` once while it is busy.
- Expected result: the TUI shows an interrupt confirmation and the turn keeps
  running.
- Press `Esc` again before the confirmation expires.
- Expected result: the active turn is interrupted.
- Press `Ctrl+G` while busy.
- Expected result: the active turn is interrupted directly after any open
  popover is closed.

Help panel smoke test:

```text
/help
```

Expected result: `/help` is a read-only command documentation panel. Use
Left/Right or Tab to switch help categories, Up/Down to scroll within the
current category, and Esc to close. If the panel scrolls, the row counter should
read like `显示第 2-7 行，共 7 行`, not an ambiguous page count.

Chinese UI smoke test:

```text
/help
/keybindings
/status
/permissions
/context
/sessions
```

Expected result: common labels, help text, footer hints, popovers, Inspector
labels, and disabled-command explanations are Chinese-first. Stable command
names, environment variables, model ids, protocol names, and tool identifiers
remain unchanged.

Context token/window smoke test:

```text
/context
/usage
/status
/model
```

Expected result: context is shown by estimated tokens as current session
tokens / 200k context limit. The side panel should not present context as a
session/message count.

Resume visibility:

```text
/sessions
/resume latest
/resume <unique-visible-id-prefix>
```

Expected result: the picker shows readable titles first with short ids in
parentheses, plus status/model/turn and retained message count where available.
Resume then renders retained user/assistant messages back into the conversation.
Legacy records may show zero restored messages.

Detail-mode visibility:

```text
Ctrl+O
```

Expected result: compact mode folds long assistant paragraphs with a hidden-line
marker, detail shows more, and full expands all retained transcript text. In
terminals that emit raw Ctrl+O bytes rather than Ink structured key events, the
same toggle should still work.

Wide side-panel scroll:

```text
最大化或拉宽终端到右侧栏出现，然后生成一段长回答。
```

Expected result: the right-side panel stays pinned while the transcript scrolls.
Switching the side panel with Tab should not jump the terminal view back to the
bottom. During active streaming and after completion, wheel scrolling should use
the TUI viewport instead of snapping terminal scrollback back to the newest
output. Dragging the terminal scrollbar should not reveal a duplicate/stale TUI
frame above the current screen.

## Manual Acceptance Recorded

On 2026-04-29, the user accepted Stage 4 through Stage 6 in the live TUI:

- Stage 4 transcript/streaming: long-answer streaming, mouse-wheel review,
  right-side panel stability, and `Ctrl+O` detail expansion passed.
- Stage 5 tool/permission UX: the agent created, wrote, and read a file; the
  permission confirmation box appeared and was operable before the write.
- Stage 6 command product surfaces: `/help`, `/status`, `/model`, `/context`,
  `/usage`, `/cost`, `/permissions`, `/gateway`, and `/keybindings` were
  readable and usable.
- Composer deletion regression: Backspace and Delete were fixed and confirmed
  working after the raw-input fallback update.

Final Stage 7 delivery decision on 2026-04-29:

- `/sessions` and `/resume` can enter previous conversations, with readable
  title-first records.
- `/guide` was confirmed usable for steering conversations, and exact stop
  phrases such as `/guide 停止` are covered by the checkpoint-interrupt tests.
- `/compact` was confirmed usable. The command now prefers a separate model
  summarization request through the configured lab gateway, keeps recent
  messages exact, and falls back to `本地摘要` with a visible reason when
  needed.
- Queue, file-mention, and broad shortcut edge cases are covered by automated
  tests and are accepted as non-blocking for the controlled internal handoff.
- Stage 8 is intentionally partial/non-blocking: local MCP and readonly agents
  exist; richer extension panels remain deferred.
