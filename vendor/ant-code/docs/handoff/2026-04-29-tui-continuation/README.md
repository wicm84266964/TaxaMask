# Ant Code TUI Continuation Handoff

Date: 2026-04-29

This folder is a handoff package for continuing the current Ant Code TUI rebuild work in a new conversation.

## Repository

Active repository:

```powershell
C:\saveproject\LBJ-workspace\lab-agent
```

The user tests with:

```powershell
cd C:\saveproject\LBJ-workspace\lab-agent
node .\src\cli\index.js tui
```

Do not assume the global `ant-code` command points at this repo. The older/global install may point elsewhere.

The worktree is expected to contain many uncommitted changes from the staged
rebuild. Do not reset, clean, or revert unrelated files unless the user
explicitly asks.

Important sibling workspace note:

```text
C:\saveproject\LBJ-workspace\ant-code-latest
```

is the existing Ant Code project and the main product/reference baseline for
the rebuild. `lab-agent` is the new clean-room implementation repo. Use
`ant-code-latest` to understand target behavior and user expectations through
sanitized notes/logs/observable behavior, but implement and test new code in
`lab-agent`. See `ANT_CODE_LATEST_STATUS.md` before testing or debugging
command-launch confusion.

## Current Theme

The preferred visual direction is OpenCode-like with a sky-blue base theme. The current TUI has already moved toward this direction, but interaction polish is still in progress.

## Safety Boundary

Continue the clean-room approach. Do not read or copy leaked Claude Code source. It is acceptable to reproduce observable behavior and event-model ideas from public behavior, public docs, or clean-room notes.

Do not persist the user's local gateway API key in repo files. The user has a local gateway, but secrets should stay in environment variables or local ignored config.

When in doubt, preserve the current `lab-agent` implementation and continue
from the handoff notes rather than restarting the rebuild.

## Read These Files First

1. `CURRENT_STATE.md`
2. `OPEN_TASKS.md`
3. `PLAN_DOCUMENT_STATUS.md`
4. `ANT_CODE_LATEST_STATUS.md`
5. `TESTING_AND_LAUNCH.md`
6. `FINAL_HANDOFF_PROMPT.md`

`NEXT_SESSION_PROMPT.md` is the earlier handoff prompt draft. Prefer
`FINAL_HANDOFF_PROMPT.md` for a new continuation conversation.

## Included Planning Documents

Planning/specification documents from the main `docs/` tree were copied into:

```text
plan-documents/docs/
```

The copies preserve the original relative paths. Use `PLAN_DOCUMENT_STATUS.md`
to see which plan items are implemented, partial, or still pending.
