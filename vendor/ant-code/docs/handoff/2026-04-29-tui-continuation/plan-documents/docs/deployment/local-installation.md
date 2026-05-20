# Ant Code Local Installation

This guide is for installing Ant Code v1.0 from the lab-owned checkout or package on a local workstation. It assumes tools run locally and model traffic, when enabled, goes through the model gateway/model adapter layer.

## Local Checkout

From the repository root:

```sh
npm install
npm run verify:install
npm run verify:release
node src/cli/index.js doctor
node src/cli/index.js tui
node src/cli/index.js -p "/status"
```

This repository uses reviewed public open-source runtime dependencies for the terminal UI layer. `npm install` installs the locked dependency graph from `package-lock.json`; packed internal releases carry the same graph through `npm-shrinkwrap.json`. Release checks verify the reviewed allowlist, lockfile integrity, dependency SBOM, license summary, shrinkwrap parity, and provenance notes.

## Linked CLI

For daily local use from any project directory:

```sh
npm link
ant-code --version
ant-code doctor
ant-code tui
ant-code -p "/status"
ant-code
```

`lab-agent` is also exposed as a compatibility alias for internal scripts, but user-facing instructions should prefer `ant-code`.

## PowerShell Environment

For a local model adapter or lab model gateway:

```powershell
$env:LAB_MODEL_GATEWAY_URL = "http://127.0.0.1:8787/v1/chat"
$env:LAB_MODEL_GATEWAY_HEALTH_URL = "http://127.0.0.1:8787/health"
$env:LAB_AGENT_NETWORK_MODE = "offline"
ant-code gateway
ant-code gateway --live
```

For an OpenAI Chat Completions compatible local adapter:

```powershell
$env:LAB_MODEL_GATEWAY_PROTOCOL = "openai-chat"
$env:LAB_MODEL_GATEWAY_URL = "http://localhost:8080/v1/chat/completions"
$env:LAB_MODEL_GATEWAY_API_KEY = "<adapter-access-token>"
$env:LAB_AGENT_MODEL = "claude-sonnet-4-5-20250929"
$env:LAB_AGENT_NETWORK_MODE = "offline"
node src/cli/index.js -p "hello"
node src/cli/index.js tui
```

`LAB_MODEL_GATEWAY_API_KEY` is a local adapter access token. Do not commit it to config files; use a PowerShell session variable, a Windows user environment variable, or another lab-approved secret store.

Optional TUI appearance variables:

```powershell
$env:LAB_AGENT_TUI_THEME = "sky-blue"       # default sky-blue theme
$env:LAB_AGENT_NO_COLOR = "1"               # no-color fallback for low-color terminals
```

For high-sensitivity projects:

```powershell
$env:LAB_AGENT_SENSITIVITY = "high"
$env:LAB_AGENT_NETWORK_MODE = "lab-only"
ant-code doctor
```

## Startup Checks

Before distributing a candidate, run:

```sh
npm run verify:install
npm run verify:release
ant-code doctor
ant-code -p "/map"
ant-code -p "/verify suggest"
```

Expected result:

- Install readiness passes.
- Release verification passes.
- Doctor shows no unexpected errors.
- Slash commands work without model gateway access.
- The v1.0 acceptance record in `docs/deployment/v1.0-acceptance.md` matches the configured delivery environment.

## Troubleshooting

- If `ant-code` is not found, rerun `npm link` from the repository root or use `node src/cli/index.js`.
- If the TUI is not comfortable in the current terminal, use line-mode `ant-code chat` or print mode with `ant-code -p`.
- If `doctor` says the model gateway is not configured, local slash commands still work; set `LAB_MODEL_GATEWAY_URL` only when model turns are needed.
- If live gateway checks fail in `offline` mode, use a loopback adapter such as `127.0.0.1` or switch to a lab-approved `lab-only` host.
- If metadata retention is too broad for the project, set `LAB_AGENT_SENSITIVITY=high` or use the high-sensitivity config template.
- If command approvals are confusing, use `/status`, `/next`, and `/report` to inspect the current local workflow state before continuing.
