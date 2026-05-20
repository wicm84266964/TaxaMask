# Ant Code Release Candidate Package

This package defines what must be attached to an Ant Code release candidate before it is distributed beyond the maintainer's own workstation. It is intentionally local-first and clean-room oriented: the evidence proves the client was built from this repository, validated through the lab gateway boundary, and configured for research-data protection.

## Freeze Criteria

A release candidate is frozen only when all conditions are true:

- The source directory is frozen for packaging.
- The candidate commit hash is recorded when version control is used, or the package SHA256 is recorded for local-only distribution.
- `npm run verify:release` passes on the candidate commit.
- `node scripts/verify-gateway-compat.js --live` passes against the deployed lab gateway before broad rollout.
- `node src/cli/index.js doctor` has no error checks in the target deployment environment.
- `node src/cli/index.js gateway --live` succeeds when live gateway access is enabled.
- High-sensitivity projects have an explicit zero-retention or encrypted-metadata decision.

## Required Evidence Bundle

Attach these artifacts to the release candidate note:

- Candidate commit hash when available, or package SHA256 for local-only distribution, plus package version.
- `npm run verify:release` summary.
- `node src/cli/index.js doctor` output from the deployment environment.
- `node src/cli/index.js gateway --live` output or a documented reason live gateway access is deferred.
- `node scripts/verify-gateway-compat.js --live` output before broad rollout.
- `docs/audit/mvp-release-audit.generated.md`.
- `docs/audit/endpoint-manifest.generated.json`.
- `docs/audit/provenance-summary.generated.md`.
- `docs/audit/release-candidate-summary.generated.md`.
- `docs/audit/dependency-sbom.generated.json`.
- `docs/audit/dependency-license-summary.generated.md`.
- `docs/deployment/v1.0-acceptance.md`.
- Final lab-managed config path or a redacted copy derived from `config/lab-agent.lab-template.json`.
- High-sensitivity config decision when applicable, derived from `config/lab-agent.high-sensitivity-template.json`.

## Functional Acceptance

Run these checks in a scratch workspace with no private datasets:

```sh
node src/cli/index.js -p "/status"
node src/cli/index.js -p "/map"
node src/cli/index.js -p "/verify suggest"
node src/cli/index.js -p "/next"
node src/cli/index.js -p "/report"
node src/cli/index.js -p "please read_file README.md"
node src/cli/index.js --allow-write -p "please write_file scratch-ant-code.txt hello"
```

Expected results:

- Local slash commands work without contacting the model gateway.
- Model turns use only the configured lab adapter endpoint and protocol (`LAB_MODEL_GATEWAY_URL`, `LAB_MODEL_GATEWAY_PROTOCOL`, and optional gateway adapter auth).
- File writes require explicit local approval or an explicit print-mode flag.
- Outputs remain bounded and do not include raw secret files.
- `/status`, `/next`, and `/report` explain the delivery state and validation needs clearly.

## High-Sensitivity Projects

For unpublished papers, private datasets, human-subject-adjacent material, or restricted partner code:

- Use `LAB_AGENT_SENSITIVITY=high` or `config/lab-agent.high-sensitivity-template.json`.
- Keep `LAB_AGENT_NETWORK_MODE=lab-only` or `offline`.
- Require zero-retention local metadata unless the project owner approves encrypted local metadata.
- Keep provider credentials only inside the lab gateway service boundary.
- Disable non-reviewed MCP servers and plugins.
- Retain only redacted release evidence.

## Distribution Checklist

- Public user-facing name is Ant Code.
- Public CLI command is `ant-code`.
- `lab-agent` remains only a compatibility alias/internal codename.
- Install instructions point to the lab-owned package or local checkout, not public auto-update channels.
- Lab policy documents the allowed gateway host, model aliases, metadata retention, MCP allowlist, and support contact.
- Users receive rollback instructions before first use.

## Rollback And Disablement

The fastest safe rollback is local configuration:

```sh
set LAB_MODEL_GATEWAY_URL=
set LAB_MODEL_GATEWAY_HEALTH_URL=
set LAB_MODEL_GATEWAY_API_KEY=
set LAB_AGENT_NETWORK_MODE=offline
```

Then remove or replace the lab-managed config referenced by `LAB_AGENT_CONFIG`.

For local metadata cleanup, run:

```sh
node src/cli/index.js -p "/sessions cleanup"
```

Rollback is complete when:

- `node src/cli/index.js gateway` reports that live gateway access is unavailable or disabled.
- `node src/cli/index.js doctor` has no unexpected broad-network configuration.
- Local slash commands still work for diagnostics and cleanup.

## Sign-Off

Record these approvals in the lab release note:

- Maintainer approval.
- Lab gateway operator approval.
- Data/security owner approval for the intended sensitivity class.
- Rollback owner and contact path.
