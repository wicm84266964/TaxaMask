# Vendored Ant-Code Runtime

This directory contains the Ant-Code runtime embedded by TaxaMask for the local agent panel and dashboard workflow.

The vendored copy is not the primary public product in this repository. It is included so TaxaMask can launch its local assistant features from source without requiring a separate Ant-Code checkout.

## What Is Included

- `src/`: local agent runtime, dashboard server, permission checks, session store, and tool adapters.
- `config/`: reusable configuration templates and generic built-in skills.
- `scripts/`: utility scripts needed for syntax checks, local diagnostics, and optional dashboard asset rebuilds.
- `package.json`, `package-lock.json`, and `npm-shrinkwrap.json`: the locked Node.js dependency graph used by the vendored runtime.

Historical planning notes, handoff documents, upstream release evidence, and old test fixtures are intentionally not part of the TaxaMask public source release.

## Configuration

TaxaMask points the embedded runtime to `AntSleap/config/taxamask_ant_code.config.json`.

Model gateway credentials should be supplied through local user configuration or environment variables. Do not commit real API keys or private gateway tokens.

Common environment variables recognized by the runtime include:

- `LAB_AGENT_CONFIG`
- `LAB_MODEL_GATEWAY_PROTOCOL`
- `LAB_MODEL_GATEWAY_URL`
- `LAB_MODEL_GATEWAY_HEALTH_URL`
- `LAB_MODEL_GATEWAY_API_KEY`
- `LAB_AGENT_MODEL`

## Local Checks

From this directory:

```powershell
npm ci
npm run check:syntax
node .\src\cli\index.js doctor
```

The top-level TaxaMask documentation remains the user-facing installation and workflow reference.
