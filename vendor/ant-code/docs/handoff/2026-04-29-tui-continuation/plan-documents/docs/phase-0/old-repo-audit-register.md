# Old Repository Audit Register

This register records the Phase 0 audit of the old Ant Code repository.

## Audited Repository

```text
C:\saveproject\LBJ-workspace\ant-code-latest
```

## Audit Date

2026-04-28

## Audit Purpose

The audit supports a clean-room rebuild for lab-internal use. The goals are:

- Identify cloud-linked Claude / Anthropic capabilities.
- Identify old-source contamination risks.
- Identify data-boundary risks for sensitive research use.
- Produce migration guidance for a new clean-room repository.

This is an engineering provenance and security audit note, not legal advice.

## Repository Condition

Observed:

- No `.git` directory in the working tree.
- No root-level `LICENSE`, `NOTICE`, or `COPYING` file.
- Existing project documents explicitly state that the old repository was built from leaked Claude Code source.
- Large amount of product-specific naming remains in source files.
- Large amount of inline source map material remains in source files.

Implication:

- The old repository should be treated as contaminated source.
- It should not be used as a code donor for the clean-room repository.
- It may be retained as restricted audit evidence and behavior reference.

## Commands Used

The audit used read-only shell inspection and ripgrep scans.

```powershell
Get-ChildItem -Force
rg --files
Get-Content -LiteralPath MAINTENANCE_LOG.md -TotalCount 240
Get-Content -LiteralPath LLM_HANDOFF.md -TotalCount 260
Get-Content -LiteralPath CHANGELOG.md -TotalCount 220
Get-Content -LiteralPath package.json
Get-ChildItem -LiteralPath src -Directory
rg -n "claude\.ai|api\.anthropic\.com|/api/claude_code|oauth|OAuth|bridge|remote|teleport|growthbook|statsig|datadog|feedback|transcript|survey|marketplace|Desktop|Chrome|voice|STT|metrics|settings|team_memory|policy_limits|files" src bin scripts runtime .env.example README.md LLM_HANDOFF.md MAINTENANCE_LOG.md CHANGELOG.md
```

Additional aggregate scans counted:

- source files and line counts under `src`
- keyword matches for `Claude`, `Anthropic`, `growthbook`, `statsig`, `datadog`
- endpoint matches for `claude.ai`, `api.anthropic.com`, `/v1/sessions`, `/v1/code`, `/api/claude_code`
- inline source-map markers

## Key Evidence

Project provenance evidence:

- `LLM_HANDOFF.md`: states that the project is based on leaked Claude Code source.
- `CHANGELOG.md`: states that `1.0.0` started from Claude Code source.
- `MAINTENANCE_LOG.md`: records later privacy hardening around Anthropic direct traffic.

Cloud capability evidence:

- `src/constants/oauth.ts`: OAuth endpoints, scopes, MCP proxy URL, account flows.
- `src/bridge/**`: Remote Control and bridge session behavior.
- `src/utils/teleport*`: remote sessions, cloud session events, archive and title APIs.
- `src/tools/RemoteTriggerTool`: scheduled remote agent trigger API.
- `src/services/mcp/claudeai.ts`: Claude.ai managed MCP server discovery.
- `src/services/settingsSync`: cloud user settings sync.
- `src/services/teamMemorySync`: cloud team memory sync.
- `src/services/remoteManagedSettings`: cloud managed settings.
- `src/services/policyLimits`: cloud org policy limits.
- `src/services/analytics/**`: telemetry, GrowthBook, Datadog, first-party event logging.
- `src/components/FeedbackSurvey/submitTranscriptShare.ts`: transcript upload endpoint.
- `src/utils/plugins/officialMarketplaceStartupCheck.ts`: official marketplace auto-install.

## Quantitative Snapshot

| Metric | Result |
| --- | ---: |
| TS/JS source files under `src` | 1,934 |
| TS/JS source lines under `src` | 483,891 |
| Files containing `Claude` | 770 |
| Files containing `Anthropic` | 322 |
| Files containing `Claude Code` | 110 |
| Files containing `growthbook` | 177 |
| Files containing `statsig` | 38 |
| Files containing `datadog` | 23 |
| Files containing inline `sourceMappingURL=data:application/json` | 547 |

Endpoint / cloud-reference snapshot:

| Pattern | Files | Matches |
| --- | ---: | ---: |
| `/v1/sessions` | 12 | 41 |
| `https://claude.ai` | 17 | 33 |
| `/v1/code` | 16 | 28 |
| `/api/claude_code` | 12 | 16 |
| `https://api.anthropic.com` | 11 | 15 |
| `https://platform.claude.com` | 7 | 12 |
| `/v1/files` | 2 | 5 |
| `/v1/mcp_servers` | 2 | 2 |
| `mcp-proxy.anthropic.com` | 1 | 1 |
| `http-intake.logs.us5.datadoghq.com` | 1 | 1 |

## High-Risk Areas

| Area | Risk |
| --- | --- |
| `src/bridge/**` | Private remote-control protocol and OAuth-backed cloud polling. |
| `src/utils/teleport*` and `src/remote/**` | Cloud session APIs and remote worker assumptions. |
| `src/services/analytics/**` | Telemetry and remote feature flags. |
| `src/services/*Sync/**` | Cloud sync of settings and memory. |
| `src/services/policyLimits/**` | Cloud policy enforcement that must be lab-owned. |
| `src/services/mcp/claudeai.ts` | Claude.ai connector discovery and OAuth scopes. |
| `src/utils/plugins/**` | Official marketplace assumptions and remote installs. |
| Inline source maps | Strong source fingerprint; must not be used in clean-room implementation. |

## Limitations

- No commit history is available, so this audit cannot attribute changes by author or time.
- No license audit of all transitive dependencies was completed in Phase 0.
- No legal conclusion is provided.
- The audit focuses on source and endpoint evidence, not runtime packet capture.
- Generated artifacts under `dist`, `tmp`, and `outputs` were not treated as new implementation sources.

## Phase 0 Result

The old repository is classified as:

```text
contaminated-reference-only
```

Allowed uses:

- restricted audit evidence
- behavior inventory
- migration test design
- security gap analysis

Forbidden uses:

- copying code into the new repository
- copying type definitions or schemas
- copying UI structure
- copying private endpoint clients
- using inline source maps as source material
