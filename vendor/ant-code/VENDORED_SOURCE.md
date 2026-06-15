# Vendored Ant-Code Source

This directory contains a local copy of the Ant-Code source used for TaxaMask integration work.

- Source path: local Ant-Code development checkout used to prepare this vendored snapshot.
- Source base commit: `7b6dcd8` (`feat(dashboard): close subagent wakeup loop`)
- Source snapshot: current local worktree on 2026-06-03, including the untracked `src/agents/plan-package-store.js` and `tests/unit/plan-package-store.test.js` development files.
- Copy method: files tracked by the source repository's `git ls-files`, plus the two development files above.
- Excluded local/runtime content: `.git`, `node_modules`, `dist`, `.tmp`, `logs`, and other untracked local files.

Keep TaxaMask-specific interface changes in this vendored copy unless the user explicitly asks to modify the original Ant-Code source tree.
