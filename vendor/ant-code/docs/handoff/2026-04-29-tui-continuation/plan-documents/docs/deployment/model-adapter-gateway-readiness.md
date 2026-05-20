# Model Adapter Gateway Readiness

Ant Code uses a model gateway/model adapter layer for model traffic. This layer is not a remote tool server. Local files, shell commands, git state, MCP calls, and edit approvals stay inside the local Ant Code client.

## Boundary

Required boundary:

- Tools execute on the local client.
- The model gateway receives prompts, tool definitions, and bounded tool results only when model turns are requested.
- Provider credentials live inside the gateway/model adapter service boundary, not in the local Ant Code shell.
- `LAB_MODEL_GATEWAY_API_KEY`, when used, is only a gateway access token for that adapter. Do not place provider API keys in the local client environment.
- Remote tools are disabled by default and are not required for MVP.
- A loopback adapter at `127.0.0.1` is acceptable for local models.
- A lab-only or VPN-only adapter is preferred for shared GPU or hosted models.
- Public exposure is optional and must add authentication, TLS, rate limits, audit IDs, and data-retention review.

## Required Endpoints

- `LAB_MODEL_GATEWAY_URL`: provider-independent chat endpoint.
- `LAB_MODEL_GATEWAY_PROTOCOL`: optional protocol selector. Defaults to `lab-agent-gateway`; use `openai-chat` for OpenAI Chat Completions compatible local adapters.
- `LAB_MODEL_GATEWAY_API_KEY`: optional bearer token for the configured adapter URL.
- `LAB_MODEL_GATEWAY_HEALTH_URL`: optional health endpoint for explicit live checks.

Health checks never carry prompts, tool definitions, tool results, provider keys, or transcript content.

For an OpenAI-compatible loopback adapter:

```sh
LAB_MODEL_GATEWAY_PROTOCOL=openai-chat
LAB_MODEL_GATEWAY_URL=http://127.0.0.1:8080/v1/chat/completions
LAB_MODEL_GATEWAY_HEALTH_URL=http://127.0.0.1:8080/health
LAB_AGENT_NETWORK_MODE=offline
```

## Compatibility Evidence

Dry mock check:

```sh
npm run verify:gateway
```

Live text report:

```sh
node scripts/verify-gateway-compat.js --live
```

Live JSON evidence:

```sh
node scripts/verify-gateway-compat.js --live --json
```

The JSON evidence is intentionally non-sensitive. It records protocol version, model alias, network mode, configured endpoint booleans, chat normalization status, and the local-tool boundary declaration.

## Gateway Responsibilities

The gateway/model adapter owns:

- provider credential storage
- model alias routing
- quota and rate limiting
- gateway-side retention policy
- gateway-side audit IDs
- optional provider failover

The local client owns:

- workspace file reads and writes
- local command execution
- git state inspection
- local MCP process execution
- approval prompts
- metadata retention for local session summaries

## Rollout Questions

Before broad use, record answers for:

- Is the adapter loopback, lab-only, VPN-only, or public?
- Which model aliases are allowed?
- What data classes may be sent through this adapter?
- What retention policy applies to gateway logs?
- What audit ID appears in gateway logs for a compatibility check?
- Who owns rollback if the adapter fails or returns malformed responses?
