# Claude Cloud Capability Gap Analysis

This document explains how removing Claude / Anthropic cloud-linked capabilities affects real lab usage.

## Summary

For the lab's stated goal, the highest-value capabilities are local code understanding, local file editing, shell execution, permission control, local MCP, local memory, subagents, and a trusted model gateway.

Most Claude cloud capabilities improve convenience, account management, cross-device access, enterprise policy, or official ecosystem integration. They are not required for local code work and should not be carried into the clean-room MVP.

## Impact Levels

| Impact | Meaning |
| --- | --- |
| Low | Users keep core local coding workflow. |
| Medium | Some workflow convenience or team coordination is lost. |
| High | Must be replaced before broad deployment. |

## Practical Impact

| Removed cloud capability | User-visible loss | Actual impact | Replacement path |
| --- | --- | --- | --- |
| OAuth login and Claude account state | No `/login` to Claude.ai, no subscription status, no official account switching | Low if lab gateway provides auth | Lab token or lab SSO |
| Remote Control / bridge | Cannot continue a local terminal session from Claude.ai web/mobile | Low to medium | Optional lab web console later |
| Cloud remote sessions | Cannot launch official cloud coding environments | Medium for remote PR workflows, low for local research workstations | SSH/K8s/Slurm runner |
| Scheduled remote agents | No Claude-hosted scheduled jobs | Low for daily coding, medium for automation | Lab cron/queue worker |
| Claude.ai connectors | No automatic Slack/Drive/GitHub connector list from Claude.ai | Medium if currently used | Lab MCP registry and audited connectors |
| Settings sync | Settings do not follow users through Claude cloud | Medium for 100+ user deployment | Git-managed lab profile or internal config service |
| Team memory sync | No cloud-shared memory per repo | Medium | Private Git repo, object store, or internal memory service |
| Remote managed settings / policy limits | No official admin policy enforcement | High for safe broad deployment | Must build local policy engine before rollout |
| Official marketplace | No official plugin auto-install/discovery | Low | Lab-curated signed plugin registry |
| Telemetry / feedback / transcript upload | No official diagnostics and feedback loop | Low | Local logs, opt-in lab diagnostics |
| Files API | No cloud attachment download/upload by file ID | Low for local files, medium for remote sessions | Local paths, lab object storage |
| Chrome/Desktop/Mobile handoff | No Chrome extension or desktop app handoff | Low | Defer |
| Voice STT | No voice dictation | Low | Defer or local STT |
| Billing/extra usage/rate-limit screens | No official billing integration | Low | Lab gateway quota dashboard |

## Capabilities That Must Be Rebuilt Before Lab-wide Use

1. Lab model gateway integration
   - Required because all model traffic must pass through lab-controlled routing, logging policy, quota policy, and redaction policy.

2. Permission engine
   - Required because the agent will touch source code and potentially sensitive research files.
   - Must support file allow/deny rules, command allow/deny rules, interactive approvals, and managed policy overlays.

3. Local session storage
   - Required for continuity, debugging, and auditability.
   - Must support transcript disablement, retention limits, and optional encryption.

4. Lab policy distribution
   - Required for 100+ users.
   - Replaces remote managed settings and policy limits.

5. Lab MCP registry
   - Required if connectors are part of the workflow.
   - Must support allowlists, signed packages, version pinning, and secret handling.

6. Lab plugin / skill registry
   - Required to avoid uncontrolled plugin installation.
   - Should be curated by maintainers.

## Capabilities That Can Wait

- Web or mobile remote control.
- Cloud remote agent scheduling.
- Chrome extension.
- Voice input.
- Public marketplace compatibility.
- Desktop app handoff.
- Rich usage/billing UI.

## MVP Feature Set

The clean-room MVP should include:

- Interactive terminal session.
- Non-interactive print mode.
- File read / write / edit.
- Glob / grep.
- Bash and PowerShell execution.
- Permission engine.
- Model gateway adapter.
- Local MCP stdio/http client.
- Local memory files.
- Slash commands.
- Subagents with tool scopes.
- Local session store.
- Lab-managed settings.

The MVP should explicitly exclude:

- `claude.ai` URLs.
- `api.anthropic.com/api/claude_code/*` endpoints.
- `/v1/sessions` remote-session endpoints.
- `/v1/code/*` endpoints.
- `/v1/mcp_servers` Claude.ai connector discovery.
- Datadog, GrowthBook, Statsig, or first-party telemetry.

## Migration Strategy

Use a staged adoption path:

1. Build MVP for local coding in a private new repository.
2. Test with 5-10 maintainers on low-sensitivity repositories.
3. Add lab policy distribution and plugin registry.
4. Expand to 20-30 users in one research group.
5. Freeze old tool for normal use.
6. Expand to the full lab after data-boundary review.

