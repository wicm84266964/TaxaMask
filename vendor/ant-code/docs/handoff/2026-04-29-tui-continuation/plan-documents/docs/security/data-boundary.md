# Research Data Boundary

This document defines the data boundary for the clean-room lab code assistant.

## Primary Rule

Research data must not leave lab-approved infrastructure unless a project owner explicitly approves the destination and the approval is recorded.

Default behavior is local-first and lab-gateway-only.

## Data Classes

| Class | Examples | Default handling |
| --- | --- | --- |
| Public code | Open-source dependencies, public examples | May be sent to approved model gateway |
| Internal code | Lab scripts, unpublished methods, project tools | Lab gateway only |
| Sensitive research data | Raw data, patient/subject data, unpublished measurements, proprietary datasets | Do not send by default; require explicit policy exception |
| Credentials | API keys, SSH keys, cloud tokens, cookies, OAuth tokens | Never send to model; scrub from env and logs |
| Personal data | Names, emails, student IDs, human subject metadata | Treat as sensitive unless explicitly public |
| Transcripts | Prompts, model responses, tool results | Local by default; retention-limited; optional encryption |
| Tool outputs | Shell output, diffs, test logs | Same class as content included in the output |

## Approved Data Flows

Allowed by default:

- User terminal to local clean-room agent process.
- Local agent to lab model gateway.
- Local agent to local filesystem within approved workspace.
- Local agent to local shell after permission check.
- Local agent to local or lab-approved MCP servers.
- Local agent to lab policy/config service.
- Local agent to lab plugin/skill registry.

Conditionally allowed:

- Local agent to public internet for package/docs lookup, only if the project policy allows web access.
- Local agent to lab object storage for large attachments.
- Local agent to lab scheduler or compute runner.

Forbidden by default:

- `claude.ai`
- `api.anthropic.com` except through an explicitly approved lab gateway design
- `platform.claude.com`
- Datadog intake
- GrowthBook / Statsig remote config
- Feedback endpoints
- Transcript upload endpoints
- Official marketplace auto-install endpoints
- Unapproved third-party MCP servers

## Model Traffic Boundary

All model requests must go through `LAB_MODEL_GATEWAY_URL` or an equivalent lab-approved endpoint.

The client must not directly read or use:

- `ANTHROPIC_API_KEY`
- Claude.ai OAuth tokens
- Console OAuth tokens
- Unscoped user cloud credentials

The gateway owns:

- Provider routing.
- Quota.
- Audit policy.
- Optional redaction.
- Model allowlist.
- Request/response retention policy.

The local client owns:

- User confirmation.
- Workspace scoping.
- Tool execution policy.
- Local transcript policy.
- Secret scrubbing before request construction.

## Local Transcript Policy

Default:

- Store transcripts/session metadata locally under a lab-owned config directory.
- Do not upload transcripts.
- Do not include raw secrets.
- Retain for a bounded period or bounded size.
- For high-sensitivity projects, set retention to zero so new local session metadata is not persisted.
- When encryption is required, keep key material outside repository config and pass it through the local environment.
- Conversation compaction summaries are session-local process memory only. Metadata may record context counts and byte totals, but not raw compacted text.

Recommended settings:

- `LAB_AGENT_TRANSCRIPT_RETENTION_DAYS=30` for normal projects.
- `LAB_AGENT_TRANSCRIPT_RETENTION_DAYS=0` for high-sensitivity projects.
- `LAB_AGENT_SENSITIVITY=high` for sensitive research projects; this forces metadata disabled / zero-retention and rejects broad network modes.
- `LAB_AGENT_TRANSCRIPT_ENCRYPTION=required` on shared workstations.
- `LAB_AGENT_TRANSCRIPT_KEY` supplied by the local operator or lab secret manager when encryption is enabled.
- `transcript.includeToolOutput=policy` so high-risk command output can be redacted.
- `context.maxMessages`, `context.maxBytes`, `context.keepRecentMessages`, and `context.summaryBytes` sized to the lab gateway model window and project sensitivity.

## Shell and Subprocess Boundary

Default subprocess policy:

- Scrub sensitive environment variables.
- Block known credential files from reads unless explicitly approved.
- Require confirmation for writes outside the workspace.
- Require confirmation for network commands if project policy is offline.
- Deny destructive recursive operations unless a human approves the exact path.

Environment variables to scrub by default:

- `*_API_KEY`
- `*_TOKEN`
- `*_SECRET`
- `*_PASSWORD`
- `AWS_*`
- `GITHUB_TOKEN`
- `SSH_AUTH_SOCK`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- OAuth token variables

## MCP Boundary

Default:

- Local stdio MCP is allowed only from configured paths.
- HTTP MCP is allowed only from lab-approved hosts.
- MCP server environment variables are scrubbed unless explicitly allowlisted.
- MCP tools inherit the same permission engine as built-in tools.

Forbidden by default:

- Auto-discovering Claude.ai MCP servers.
- Auto-installing official MCP servers.
- Passing raw lab credentials to unreviewed MCP servers.

## Plugin and Skill Boundary

Default:

- Plugins and skills come from the lab registry or local project paths.
- Plugin packages must be version-pinned.
- Registry entries must include owner, source, checksum, and review status.
- Auto-update is disabled unless the lab registry signs releases.

Forbidden by default:

- Official marketplace auto-install.
- Unpinned GitHub marketplace installs.
- Runtime plugin downloads from arbitrary URLs.

## Network Policy

The clean-room client should support these modes:

| Mode | Behavior |
| --- | --- |
| `offline` | No network except loopback. |
| `lab-only` | Lab gateway, lab config, lab MCP, lab registry only. |
| `approved-web` | Lab endpoints plus explicit web allowlist. |
| `open-dev` | Developer mode for non-sensitive repos only; must show warning. |

Default for lab deployment: `lab-only`.

High-sensitivity mode permits only `offline` or `lab-only`. `approved-web` and `open-dev` are rejected for high-sensitivity sessions.

## Audit Requirements

Every release must produce:

- Dependency SBOM.
- Dependency license summary.
- Network endpoint manifest.
- Plugin registry manifest.
- Model gateway config summary.
- Policy defaults summary.
- Transcript retention summary.
- Known exceptions list.

Every exception must record:

- Requester.
- Project.
- Data class.
- Destination.
- Expiration date.
- Approver.

## Initial Denylist

The new repository should fail CI if these strings appear in runtime code without an explicit test fixture exception:

- `claude.ai`
- `api.anthropic.com/api/claude_code`
- `platform.claude.com/oauth`
- `mcp-proxy.anthropic.com`
- `http-intake.logs.us5.datadoghq.com`
- `growthbook`
- `statsig`
- `datadog`
- `shared_session_transcripts`
- `claude_cli_feedback`
