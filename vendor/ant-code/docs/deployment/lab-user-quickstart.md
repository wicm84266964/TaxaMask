# Ant Code Lab User Quickstart

This quickstart is for lab members using Ant Code on a local research project. It avoids legacy-source language and focuses on safe daily use.

## First Run

From the project directory:

```sh
node src/cli/index.js doctor
node src/cli/index.js -p "/status"
node src/cli/index.js -p "/map"
node src/cli/index.js
```

After package linking or installation, use:

```sh
ant-code doctor
ant-code -p "/status"
ant-code
```

Expected result:

- `doctor` reports local readiness checks.
- `/status` shows session, repository, delivery, and validation state.
- `/map` shows project type, manifests, key directories, and likely test entrypoints.
- Interactive mode starts with the `ant-code>` prompt.

## Connecting The Lab Gateway

Use the lab-provided configuration or environment variables:

```powershell
$env:LAB_MODEL_GATEWAY_URL = "https://gateway.example.invalid/v1/chat"
$env:LAB_MODEL_GATEWAY_HEALTH_URL = "https://gateway.example.invalid/health"
$env:LAB_AGENT_NETWORK_MODE = "lab-only"
```

Then verify:

```sh
ant-code gateway
ant-code gateway --live
```

The local client should never require provider API keys. Provider credentials belong inside the lab gateway service.

## Daily Code Workflow

Useful local commands:

```sh
ant-code -p "/files"
ant-code -p "/diff --stat"
ant-code -p "/verify suggest"
ant-code -p "/next"
ant-code -p "/report"
```

For code changes:

1. Ask Ant Code to inspect before editing.
2. Review write approvals carefully.
3. Use `/edit --dry-run <path> <old text> => <new text>` when you want a local preview.
4. Run `/verify run suggested` after code changes.
5. Use `/report` before handing work to another person.

## Sensitive Research Data

For unpublished papers, private datasets, human-subject-adjacent material, or restricted partner code:

```powershell
$env:LAB_AGENT_SENSITIVITY = "high"
$env:LAB_AGENT_NETWORK_MODE = "lab-only"
```

High sensitivity mode forces zero-retention local metadata and rejects broad network modes. Keep MCP servers disabled unless the project owner approves them.

## Safety Rules

- Do not put provider API keys in the local Ant Code shell.
- Do not approve writes or shell commands you do not understand.
- Do not enable public plugin registries or arbitrary MCP servers for sensitive projects.
- Prefer `/status`, `/next`, and `/report` when deciding whether a task is actually complete.
- Use `/sessions cleanup` when local retention policy allows metadata cleanup.

## Rollback

To disable model turns quickly:

```powershell
Remove-Item Env:\LAB_MODEL_GATEWAY_URL -ErrorAction SilentlyContinue
Remove-Item Env:\LAB_MODEL_GATEWAY_HEALTH_URL -ErrorAction SilentlyContinue
$env:LAB_AGENT_NETWORK_MODE = "offline"
```

Ant Code can still run local slash commands such as `/status`, `/map`, `/sessions cleanup`, and `/doctor` without gateway access.
