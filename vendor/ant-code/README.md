# Ant-Code Agent Center Runtime

This directory contains the first-party Ant Code Agent Center runtime embedded by TaxaMask for the local agent panel and dashboard workflow.

Ant-Code is part of the TaxaMask source release, not a third-party dependency. The `vendor/ant-code` directory name is retained for runtime layout compatibility and to keep the Node dashboard package isolated from the Python workbench.

## Versioning

The embedded runtime version label follows the Ant-Code formal release line. This copy tracks standalone Ant Code 2.0 TypeScript (`2.0.5-taxamask.1`): the upstream version plus TaxaMask host adaptations. An unmodified synchronization uses the upstream version directly, such as `2.0.5`. If TaxaMask carries embedded-only adaptations on top of that release line, it uses `<upstream version>-taxamask.<N>`. The suffix counts only TaxaMask-specific changes and resets to `.1` when the upstream release label changes. Version-label updates and source synchronization are separate reviewed operations; the label alone must not be treated as proof that every upstream bug fix is present. The embedded version is independent of the TaxaMask application version. Node.js 22.18+ is required. The CLI entry is `src/cli/index.ts`.


## What Is Included

- `src/`: local agent runtime, dashboard server, permission checks, session store, and tool adapters.
- `config/`: reusable configuration templates and generic built-in skills.
- `scripts/`: utility scripts needed for syntax checks, local diagnostics, and optional dashboard asset rebuilds.
- `package.json`, `package-lock.json`, and `npm-shrinkwrap.json`: the locked Node.js dependency graph used by the Agent Center runtime.

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
node .\src\cli\index.ts doctor
```

The top-level TaxaMask documentation remains the user-facing installation and workflow reference.
