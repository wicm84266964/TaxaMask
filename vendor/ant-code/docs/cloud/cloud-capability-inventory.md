# Claude Cloud Capability Inventory

This inventory records Claude / Anthropic cloud-linked capabilities found in the old repository and the clean-room decision for each.

## Classification

| Class | Meaning |
| --- | --- |
| Remove | Do not implement in the new repository. |
| Replace | Rebuild using lab-owned infrastructure. |
| Reimplement from public docs | Implement only from public API/protocol docs. |
| Defer | Not needed for the first clean-room milestone. |

## Inventory

| Capability | Old repository evidence | Cloud dependency | Decision | Impact on lab use |
| --- | --- | --- | --- | --- |
| Claude.ai / Console OAuth login | `src/constants/oauth.ts`, `src/commands/login` | `platform.claude.com`, `claude.com`, `api.anthropic.com`, OAuth scopes | Replace | Low for local coding if lab gateway auth exists; high only for official account features |
| Claude model API transport | `src/services/api/claude.ts`, `@anthropic-ai/sdk` | Model API or compatible proxy | Reimplement from public docs | Core capability; must be rebuilt through lab model gateway |
| Claude.ai Remote Control / bridge | `src/bridge/**`, `src/commands/bridge` | OAuth, `/v1/environments/bridge`, `/v1/sessions`, work polling, WebSocket/SSE | Remove for MVP; possible lab-owned replacement later | Low to medium; terminal workflow remains, web/mobile control is lost |
| Cloud remote sessions / Teleport / CCR | `src/utils/teleport.tsx`, `src/utils/teleport/api.ts`, `src/remote`, `src/cli/transports/ccrClient.ts` | `/v1/sessions`, `/v1/code/sessions`, session ingress | Remove; replace with SSH/K8s/Slurm runner if needed | Medium for cloud workflows; low for local code editing |
| Scheduled remote agents | `src/tools/RemoteTriggerTool`, `src/skills/bundled/scheduleRemoteAgents.ts` | `/v1/code/triggers`, Claude.ai scheduled pages | Replace with lab scheduler later | Low for interactive coding; medium for automation |
| Claude.ai managed MCP servers | `src/services/mcp/claudeai.ts` | `/v1/mcp_servers`, OAuth `user:mcp_servers` scope, MCP proxy | Replace with local/lab MCP registry | Low if lab uses local MCP; medium if relying on Claude connectors |
| Official MCP registry | `src/services/mcp/officialRegistry.ts` | `api.anthropic.com/mcp-registry` | Remove or replace with lab allowlist | Low; lab registry is safer |
| MCP proxy metadata | `src/constants/oauth.ts` | `mcp-proxy.anthropic.com`, Claude client metadata document | Remove | Low; local MCP does not need it |
| Files API attachments | `src/services/api/filesApi.ts`, `src/utils/teleport/gitBundle.ts` | `/v1/files` | Reimplement only if using public Files API; default replace with local/lab object storage | Low for local files; medium for cloud remote sessions |
| Settings sync | `src/services/settingsSync` | `/api/claude_code/user_settings` | Replace with lab config management or Git-managed settings | Low for individuals; high for fleet consistency |
| Team memory sync | `src/services/teamMemorySync` | `/api/claude_code/team_memory` | Replace with lab Git/private storage | Medium; useful capability but must be lab-owned |
| Remote managed settings | `src/services/remoteManagedSettings` | `/api/claude_code/settings` | Replace with lab policy service | Medium to high for 100+ users |
| Policy limits | `src/services/policyLimits` | `/api/claude_code/policy_limits` | Replace with local/lab policy engine | High for safe deployment |
| GrowthBook / Statsig feature gates | `src/services/analytics/growthbook.ts`, many imports | Remote feature config | Remove; replace with static config flags | Low; simplifies reliability |
| Datadog telemetry | `src/services/analytics/datadog.ts` | Datadog intake endpoint | Remove | No product impact; security benefit |
| First-party event logging / metrics | `src/services/analytics/*`, `src/utils/telemetry/*` | `api.anthropic.com/api/claude_code/metrics` and event endpoints | Remove; optional local diagnostics only | No core impact |
| Feedback / bug report upload | `src/components/Feedback.tsx`, `src/commands/feedback` | `api.anthropic.com/api/claude_cli_feedback` | Remove | Low |
| Transcript sharing | `src/components/FeedbackSurvey/submitTranscriptShare.ts` | `api.anthropic.com/api/claude_code_shared_session_transcripts` | Remove | No core impact; high data-safety benefit |
| Grove / privacy training notice | `src/services/api/grove.ts`, `src/components/grove` | account settings and Grove endpoints | Remove | No lab product impact |
| Metrics opt-out status | `src/services/api/metricsOptOut.ts` | `/api/claude_code/organizations/metrics_enabled` | Remove | No lab product impact |
| Official marketplace auto-install | `src/utils/plugins/officialMarketplaceStartupCheck.ts` | official marketplace source / GCS / GitHub | Replace with lab plugin registry | Low; lab-controlled plugins are preferred |
| Plugin marketplace manager | `src/utils/plugins/marketplaceManager.ts` | URL/GitHub/npm/local sources, official marketplace assumptions | Reimplement from lab spec | Medium; needed but should be simplified |
| Chrome extension handoff | `src/commands/chrome`, `src/utils/claudeInChrome`, `src/components/ClaudeInChromeOnboarding.tsx` | `claude.ai/chrome` | Defer / remove | Low |
| Desktop handoff / native installer links | `src/components/DesktopHandoff.tsx`, `src/utils/desktopDeepLink.ts` | `claude.ai/download`, `claude.ai/api/desktop/...` | Remove | Low |
| Upgrade / billing / extra usage | `src/commands/upgrade`, `src/commands/extra-usage`, billing URLs | Claude subscription and billing pages | Remove | Low for lab gateway usage |
| WebFetch domain info precheck | `src/tools/WebFetchTool/utils.ts` | `api.anthropic.com/api/web/domain_info` | Replace with local allowlist / DNS policy | Low to medium; safer to self-own |
| Voice STT | `src/voice`, `src/services/voiceStreamSTT.ts`, `src/commands/voice` | Cloud STT / feature gate | Defer; replace with local or lab STT if needed | Low for coding MVP |
| Auto-updater / native installer | `src/cli/update.ts`, `src/utils/nativeInstaller` | official package update channels | Replace with lab release channel | Medium for operations |
| Public docs helper | `src/tools/AgentTool/built-in/claudeCodeGuideAgent.ts` | `platform.claude.com/llms.txt` | Replace with static/public docs references | Low |

## Keep As Public/Standard Concepts

These concepts are useful and can be clean-room reimplemented:

- Terminal coding agent loop.
- Tool calling with model messages.
- File read/write/edit/search tools.
- Shell execution with explicit permission gates.
- MCP client support.
- Local memory files.
- Slash commands.
- Subagents.
- Hooks.
- Local plugin / skill registry.
- Local or lab-managed session transcripts.

## Do Not Carry Forward

The new repository should not implement these in MVP:

- Claude.ai account login.
- Claude.ai Remote Control.
- Claude cloud remote sessions.
- Claude scheduled remote agents.
- Claude.ai connector discovery.
- Anthropic telemetry, feedback, transcript upload, feature gates.
- Official marketplace auto-install.
- Claude billing and upgrade flows.

