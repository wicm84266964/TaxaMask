# Ant Code Local Maintenance Notes

This is the canonical Ant Code project rules file for this repository. `AGENT.md` is retained as a compatibility file for Codex-style tooling, but Ant Code should prefer this file when loading project rules.

This repository contains the first-party Ant-Code runtime embedded by TaxaMask. Keep large local release archives and machine-specific backups outside the source repository.

## Git Workflow

- Use local Git commits as the normal version history, even when no GitHub remote is used.
- Commit after a user-accepted milestone, a completed stage group, or a risky refactor that may need rollback.
- Prefer clear Chinese commit messages for user-facing milestones, for example:
  - `保存：v1.5 子智能体编排与 hooks 稳定版`
  - `修复：写入型子智能体 writeScope 边界`
- Use tags for formal local release points:

```powershell
git tag lab-agent-v1.5
```

- Before committing, run:

```powershell
npm run check
git status --short
```

- Do not commit API keys, adapter tokens, `.env` files, local session transcripts, or machine-only scratch files.
- If a large change is exploratory, create a backup archive first or use a separate branch, then merge/commit only after manual acceptance.

## Backup Policy

- Git is for precise file-level history and rollback.
- Zip/folder backups are for physical safety and deadline handoff.
- For major accepted versions, use Git commits or tags. Keep any compressed backup copies outside the repository.

## Review Checklist

- Confirm the TUI still launches from this repo with:

```powershell
node .\src\cli\index.js tui
```

- Confirm the global install points to this repo when testing the `ant-code` command.
- Keep public README and deployment documentation accurate when architecture, prompts, agents, MCP, skills, hooks, or permissions change.
- Treat `lab-agent.config.json` as local product configuration. It may contain model names, allowed hosts, MCP entries, and skill paths, but it must not contain secret tokens.
