# Ant Code

This repository is the clean-room rebuild workspace for Ant Code, the lab-local coding agent.

Ant Code is the public project name. The internal implementation codename remains `lab-agent` for protocol, config, local state, and audit compatibility. See `docs/branding/public-identity.md`.

It starts from an empty implementation baseline. The design documents in `docs/` describe the audit findings, provenance policy, product scope, security boundary, and MVP architecture. They were prepared as clean planning artifacts for an independent implementation based on public documentation and lab-owned requirements.

Do not copy source code, tests, package manifests, generated bundles, source maps, prompts, or runtime assets from the legacy reference repository into this repository. The legacy repository is treated as contaminated reference material only.

## Current State

- Current release: Ant Code 3.0.0 Dashboard/WebUI line
- Implementation source: Clean-room Ant Code with mature TUI, local extension runtime, orchestration, and Dashboard
- Copied artifacts: planning and audit documents only
- Provenance rule: independent clean-room implementation
- Public CLI: `ant-code`
- Compatibility CLI alias: `lab-agent`

## Version Lineage

Ant Code version numbers now follow product generations:

- `1.x`: the old Claude Code source-derived AntCode reference and the first clean-room acceptance baseline.
- `2.x`: the self-owned clean-room architecture, production TUI, local extension runtime, and orchestration work.
- `3.x`: the Dashboard/WebUI release line over the same local runtime and session store.

The detailed lineage and acceptance evidence are recorded in `docs/deployment/v3.0-dashboard-acceptance.md`. Historical v1.x/v1.2/v1.3/v1.4 acceptance files are preserved as dated evidence and are not rewritten to the current version.

## Quick Install

For external Windows distribution, use the executable release directory instead
of the npm tarball:

```powershell
npm run build:exe
.\dist\ant-code-windows-x64\ant-code.exe --version
.\dist\ant-code-windows-x64\ant-code.exe doctor
```

`dist\ant-code-windows-x64\` is the package to hand to external users. It
contains the executable, config templates, skills, and deployment/audit docs; it
does not include `src/`, tests, `node_modules`, handoff notes, or planning
notes.

Chinese quickstart users can open `README.zh-CN.md` and run the interactive
gateway setup script:

```powershell
.\dist\ant-code-windows-x64\configure-gateway.ps1
```

Install the packaged CLI with Node.js 20+ and npm:

```powershell
npm install -g .\dist\ant-code-cli-3.0.0.tgz
ant-code --version
ant-code doctor
```

The npm tarball is an internal install/smoke-test artifact and includes source
files by npm design. Do not use it as the source-protected external
distribution.

For checkout development, install locked dependencies from the repository root:

```powershell
npm ci
npm run verify:install
node .\src\cli\index.js doctor
```

## Gateway Config

Use a JSON config for durable model/gateway settings, and keep only the gateway
token in the environment. In a project-specific `lab-agent.config.json`:

```json
{
  "modelAlias": "my-coding-model",
  "models": [
    {
      "id": "my-coding-model",
      "label": "My Coding Model",
      "thinking": false,
      "modalities": ["text"],
      "reasoningContentMode": "visible-when-no-content",
      "contextTokens": 200000
    },
    {
      "id": "my-vision-model",
      "label": "My Vision Model",
      "thinking": false,
      "modalities": ["text", "image"],
      "contextTokens": 200000
    }
  ],
  "networkMode": "lab-only",
  "allowedHosts": ["gateway.example.com"],
  "lab": {
    "gatewayProtocol": "openai-chat",
    "gatewayUrl": "https://gateway.example.com/v1/chat/completions",
    "gatewayHealthUrl": "https://gateway.example.com/health"
  },
  "agents": {
    "modelTiers": {
      "cheap": "my-coding-model",
      "default": "my-coding-model",
      "strong": "my-coding-model",
      "vision": "my-vision-model"
    },
    "vision": {
      "enabled": true,
      "model": "my-vision-model",
      "autoUseWhenMainModelTextOnly": true
    }
  }
}
```

For external Windows users, `configure-gateway.ps1` defaults to
`approved-web`, which keeps network access visible and allowlisted while
enabling built-in `web_search` and common `web_fetch` sources such as
DuckDuckGo, GitHub raw/API, and `r.jina.ai`. Choose `lab-only` in the script
when public web access must be disabled.

For a shared machine config, copy `config/lab-agent.lab-template.json` to a
stable location and set `LAB_AGENT_CONFIG` to that file. Store gateway auth
separately:

```powershell
[Environment]::SetEnvironmentVariable("LAB_AGENT_CONFIG", "C:\ant-code\lab-agent.config.json", "User")
[Environment]::SetEnvironmentVariable("LAB_MODEL_GATEWAY_API_KEY", "<gateway-access-token>", "User")
```

Open a new terminal, then verify:

```powershell
ant-code doctor
ant-code gateway --live
ant-code -p "Reply exactly: ready"
```

`gatewayProtocol` is `openai-chat` for OpenAI Chat Completions compatible
gateways, or `lab-agent-gateway` for the native Ant Code lab protocol. See
`docs/deployment/local-installation.md` for the full installation and
configuration guide.

To switch to another gateway later, edit only these durable config fields:

- `modelAlias`: model used by the main agent.
- `models`: model ids shown in Ant Code. Use `modalities: ["text", "image"]`
  only for models that should receive image inputs.
- `agents.modelTiers`: model ids used by subagents; set all tiers to the same
  id when you want main and subagents to use one model. The optional `vision`
  tier is used by the visual verifier profile.
- `agents.vision`: same-gateway visual fallback for image attachments when the
  selected main model is text-only.
- `lab.gatewayProtocol`, `lab.gatewayUrl`, and optional
  `lab.gatewayHealthUrl`.
- `allowedHosts`: include the gateway host when `networkMode` is `lab-only` or
  `approved-web`.

Dashboard can edit the same local model configuration from the model selector
near the composer. The selector shows text/image/thinking labels, switches among
registered models, and can save gateway URL, access token, model id, context
window, subagent defaults, and the visual subagent model. Ant Code still uses one
active gateway/key at a time; it does not route text models through one provider
and image models through another provider in the same turn.

Environment variables such as `LAB_AGENT_MODEL`, `LAB_AGENT_MODELS`,
`LAB_MODEL_GATEWAY_PROTOCOL`, `LAB_MODEL_GATEWAY_URL`,
`LAB_MODEL_GATEWAY_HEALTH_URL`, and `LAB_MODEL_GATEWAY_API_KEY` override JSON
for the current process. If a model switch seems to ignore the JSON, check the
terminal environment first.

## Local Commands

```sh
npm run doctor
npm run check
npm run check:release-seal
npm run check:dependencies
npm run verify:install
npm run verify:gateway
npm run verify:readiness
npm run audit:sbom
npm run audit:licenses
npm run audit:rc
npm run mock-gateway -- --port 8787
node src/cli/index.js --version
node src/cli/index.js
node src/cli/index.js tui
node src/cli/index.js gateway
node src/cli/index.js chat
node src/cli/index.js -p "hello"
```

After package linking or installation, use the public command name:

```sh
ant-code --version
ant-code
ant-code tui
ant-code chat
ant-code --resume latest
ant-code -p "hello"
```

Print mode calls `LAB_MODEL_GATEWAY_URL` when configured. For local development, point it at the mock lab gateway:

```sh
LAB_MODEL_GATEWAY_URL=http://127.0.0.1:8787/v1/chat node src/cli/index.js -p "hello"
LAB_MODEL_GATEWAY_URL=http://127.0.0.1:8787/v1/chat node src/cli/index.js -p "please read_file README.md"
LAB_MODEL_GATEWAY_URL=http://127.0.0.1:8787/v1/chat node src/cli/index.js -p "please git_status"
LAB_MODEL_GATEWAY_URL=http://127.0.0.1:8787/v1/chat node src/cli/index.js -p "please git_diff stat"
LAB_MODEL_GATEWAY_URL=http://127.0.0.1:8787/v1/chat node src/cli/index.js --allow-write -p "please write_file scratch.txt hello"
LAB_MODEL_GATEWAY_URL=http://127.0.0.1:8787/v1/chat node src/cli/index.js -p "please powershell Get-Location"
LAB_MODEL_GATEWAY_URL=http://127.0.0.1:8787/v1/chat LAB_MODEL_GATEWAY_HEALTH_URL=http://127.0.0.1:8787/health node src/cli/index.js gateway --live
node src/cli/index.js -p "/status"
node src/cli/index.js -p "/status --json"
node src/cli/index.js -p "/files"
node src/cli/index.js -p "/map"
node src/cli/index.js -p "/diff"
node src/cli/index.js -p "/review"
node src/cli/index.js -p "/verify"
node src/cli/index.js -p "/verify suggest"
node src/cli/index.js -p "/verify run suggested"
node src/cli/index.js -p "/report"
node src/cli/index.js -p "/next"
node src/cli/index.js -p "/run Get-Location"
node src/cli/index.js -p "/sessions show latest"
node src/cli/index.js -p "/gateway"
node src/cli/index.js -p "/mcp"
node src/cli/index.js -p "/agents run readonly-researcher find Ant Code"
node src/cli/index.js -p "/memory add Prefer local-only analysis."
node src/cli/index.js -p "/sessions cleanup"
```

For an OpenAI Chat Completions compatible local adapter, use the protocol selector and keep the adapter token in the process environment:

```sh
LAB_MODEL_GATEWAY_PROTOCOL=openai-chat \
LAB_MODEL_GATEWAY_URL=http://127.0.0.1:8080/v1/chat/completions \
LAB_MODEL_GATEWAY_HEALTH_URL=http://127.0.0.1:8080/health \
LAB_MODEL_GATEWAY_API_KEY=<adapter-access-token> \
LAB_AGENT_MODEL=claude-sonnet-4-5-20250929 \
LAB_AGENT_MODELS=claude-sonnet-4-5-20250929,claude-sonnet-4-5-20250929-thinking,claude-haiku-4-5-20251001 \
LAB_AGENT_NETWORK_MODE=offline \
node src/cli/index.js -p "hello"
```

`LAB_MODEL_GATEWAY_API_KEY` is an adapter access token for the configured gateway, not a provider API key. Tool calls returned by compatible gateways are still executed locally through Ant Code's permission engine.

Terminal UI:

```sh
node src/cli/index.js tui
```

The default TUI is an Ink/React-powered v1.2/v1.3 interaction layer over the existing session runtime. It uses a conversation-first layout with an Ant Code startup logo surface, live assistant draft rendering, provider-exposed thinking/reasoning deltas when the configured adapter streams them, streamed tool-call argument drafts, and local tool run status. Gateway, turn, and tool events remain available as low-noise status lines. Wide terminals include fixed side panels for status, todos, subagent tasks, inspector output, prompt history, and command shortcuts; use `Tab` to switch main side tabs and `Left/Right` on an empty input to switch side tabs or inspector filters. The layout listens for terminal resize events and recalculates transcript, overlay, input, and side panel regions when the window changes. Use `/` for the slash palette, `@` for workspace file mentions, `!` for local shell mode through `/run`, `/model` for the in-session model picker, `/model use <model-id>` for direct switching, `Shift+Tab` to cycle permission modes, `Ctrl+J` for multi-line prompts, `Ctrl+O` for compact/detail/full transcript detail, `Ctrl+T` as an inspector filter fallback, `Ctrl+N/P` to switch Inspector items, `Ctrl+F/B` to scroll long Inspector output, `Ctrl+R/E` to switch files inside parsed patch output, `y` to approve once, `n` to deny, and `a` to approve matching requests for the current process-local session. If a model turn is busy, typing a new prompt and pressing Enter queues it for the current session; `/guide`, `/queue`, `/background`, and key status panels can still run immediately. Diff and patch output is parsed into a local file-by-file patch browser with per-file additions, deletions, and hunk counts, with highlighted patch lines inside Inspector. The TUI implementation is split into `src/cli/tui.js` plus reusable modules under `src/cli/tui/`. The line-mode `chat` command remains available as the plain fallback.

Dashboard WebUI:

```sh
node src/cli/index.js dashboard
node src/cli/index.js dashboard --port 7410 --no-open
```

`ant-code dashboard` starts a local-only WebUI on `127.0.0.1:7410` by default and opens the browser unless `--no-open` is set. The first release deliberately rejects non-loopback hosts such as `0.0.0.0`; it is not a LAN sharing mode. Dashboard reuses the same core session runtime, permission engine, and `.lab-agent/sessions` history as the TUI. Its dark gray three-panel layout shows project threads on the left, folded task activity and final replies in the center, and generated or referenced files on the right. Tool calls are folded into concise activity rows, model thinking text is not shown, and permission requests appear as a web confirmation panel above the input box with allow-once, allow-session, deny, and cancel actions. The WebUI asks for workspace trust before running turns; while a turn is running, Enter queues new text and the send button switches to a running/interruption action. If the input contains typed guidance during a running turn, Dashboard shows an explicit "引导对话" action for steering the current task; individual queued items also provide their own guide action. Background subagent groups are surfaced in the collapsible live-status strip; for `background=true` and `wakeParent=true`, Dashboard consumes the group wake prompt, queues it while the parent turn is busy, auto-runs it when idle, and records `wakePromptConsumedAt` in the task group file. Context clear and compact actions use in-page confirmations. The file preview panel supports images, text, Markdown, code, PDF, and first-release Office/binary file cards. To stop the Dashboard service, use the sidebar "关闭 Dashboard" action or press `Ctrl+C` in the terminal that launched it.

The v1.2 interaction polish work starts with theme tokens and an input editor core. `LAB_AGENT_TUI_THEME=sky-blue` is the default sky-blue theme; `ant-code`, `terminal-default`, and `no-color` are also available. Set `NO_COLOR=1` or `LAB_AGENT_NO_COLOR=1` for no-color output. The composer now tracks an insertion cursor, renders a blinking cursor segment, handles wide CJK character widths, and supports common editing keys such as Left/Right, Home/End, Delete, Ctrl+A/E/K/U/W, and Ctrl+J for newlines.

`--auto-approve` enables session-scoped approval for workspace-internal non-sensitive writes and ordinary local mutating commands; TUI users can cycle to the same “自动同意” mode with `Shift+Tab`. `--allow-write` and `--allow-command` remain separate lower-level flags. `--readonly` overrides write/command approvals. Writes outside the workspace, suspicious secret paths, high-risk commands, and network-capable commands still block or ask for explicit confirmation.
`ant-code` starts the interactive terminal loop by default; `ant-code chat` remains an explicit alias. When a tool request needs approval, it asks locally. Interactive approvals can be granted once or for matching requests in the current process-local session only.

Useful local slash commands include `/model`, `/model list`, `/model use <model-id>`, `/cost`, `/usage`, `/context`, `/keybindings`, `/files [path]`, `/map`, `/diff [--stat] [path ...]`, `/review [summary|stat|files|patch]`, `/verify suggest`, `/verify run <command>`, `/verify run suggested`, `/next`, `/report`, `/run <command>`, `/edit <path> <old text> => <new text>`, `/edit --dry-run <path> <old text> => <new text>`, `/agents`, `/agents run <profile> <query>`, `/agents tasks`, `/background list`, `/background cancel <task-id>`, `/skills`, and `/mcp`. These commands use the same workspace boundary and permission engine as model-triggered tools. Deferred cloud-style commands such as `/rewind`, `/branch`, `/stash`, `/theme`, `/feedback`, and `/fast` are visible but return lab-local disabled-state guidance rather than invoking cloud or marketplace behavior.

Interactive sessions also include session-local `/todo`, `/plan`, recorded file changes, validation history, and concise delivery status after model turns. Model tools can call `todo_read`, `todo_write`, `plan_update`, and `ask_user`; todo, plan, change, and validation details stay in memory for the active process, while metadata stores only bounded counts/status summaries. Failed shell validations keep a bounded redacted excerpt in memory and are injected into the next model turn as local workflow context so the assistant can repair before reporting completion. `/status`, `/next`, and `/report` use consistent sectioned text output and show whether the session is `blocked`, `needs_validation`, `verified`, `in_progress`, or `idle`, plus a task lifecycle stage: `inspect`, `plan`, `edit`, `validate`, `repair`, or `ready`. `/status --json` preserves a machine-readable status form. Passing validation is treated as stale if later file changes are recorded. Raw validation commands, full command output, workflow file paths, todo text, and plan text are not written into session metadata. `ant-code --resume latest` remains a startup option for loading local bounded metadata. Inside the TUI, `/sessions` restores or switches saved sessions, while `/resume` views the current session's archived 50-message transcript chunks without changing chat state or model context.
`/map`, `/status`, `/next`, and `/report` can include a lightweight repository map derived from local manifests and top-level directories. The map summarizes project type, package managers, script names, key directories, and likely source/test entrypoints without persisting raw file contents.

Interactive conversation context has a configurable local token budget. Older messages are automatically compacted by the hidden `compaction` internal agent when the model gateway is available, with local redacted fallback when it is not; `/compact` can force this manually. Persisted metadata stores bounded recent messages plus context counters and summary metadata, not raw compacted transcript text. The TUI keeps the latest visible transcript window in memory and archives older visible transcript records into `.lab-agent/sessions/<session-id>.transcript/chunk-*.json`; `/resume` opens those chunks for current-session review and copying only.

Model-triggered read-only git tools include `git_status` and `git_diff`. They invoke `git` with argument arrays, reject pathspecs that escape the workspace, and bound stdout/stderr before returning results to the model.
Model-triggered `edit_file` performs an exact-replacement preflight before writing. It rejects empty old text, no-op edits, invalid replacement counts, missing old text, and unexpected replacement counts with stable error codes. Dry-run edits return a bounded diff preview and byte-count summary without modifying files.

Configured MCP servers are explicit local stdio processes only. The checked-in root config and lab template recommend disabled `filesystem`, `memory`, and `playwright` MCP entries for lab approval; no marketplace discovery or automatic server enablement is performed.
Subagents are local-only. Built-in profiles include `build`, `explorer`, `readonly-researcher`/`research`, `planner`, `verifier`, `code-worker`, and hidden internal agents. The planner profile is reserved for complex-task plan packages after parent-side requirement confirmation; its generated `requirements.md`, `task-plan.md`, `execution-checklist.md`, and `manifest.json` are stored under `.lab-agent/plans/<plan-id>/` for traceability and can be opened through the normal file preview flow. Local skill files can provide bounded instructions, and `context: fork` skills run through a hidden child subagent while still using ordinary tools and permissions. Project memory is stored at `.lab-agent/memory.md`; local session metadata is stored under `.lab-agent/sessions/` and can be cleaned by retention policy.
Print and interactive turns persist bounded session metadata only; prompts and assistant outputs are not written into metadata.

Every model turn receives an Ant Code behavior protocol through the lab gateway context: inspect before editing, validate after code changes, repair failed validation before claiming completion, and finish with a concise change/validation/risk summary. Project memory is included with bounded relative-path labels.

Local installation material lives in `docs/deployment/local-installation.md`. The v1.0 acceptance record lives in `docs/deployment/v1.0-acceptance.md`. Model adapter readiness lives in `docs/deployment/model-adapter-gateway-readiness.md`. Real lab gateway rollout materials live in `docs/deployment/lab-user-quickstart.md`, `docs/deployment/lab-gateway-rollout-checklist.md`, `docs/deployment/release-candidate-package.md`, `docs/specs/lab-model-gateway-compatibility-matrix.md`, and `docs/deployment/pre-launch-security-config.md`. The lab-owned config starting point is `config/lab-agent.lab-template.json`.
For sensitive research projects, use `LAB_AGENT_SENSITIVITY=high` or `config/lab-agent.high-sensitivity-template.json`; this forces zero-retention local metadata and rejects broad network modes.

## Design History

The original planning baseline lives in `docs/phase-1/README.md`, `docs/specs/mvp-product-spec.md`, and `docs/architecture/mvp-architecture.md`.
