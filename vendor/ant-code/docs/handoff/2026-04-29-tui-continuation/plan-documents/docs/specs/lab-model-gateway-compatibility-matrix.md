# Lab Model Gateway Compatibility Matrix

This matrix defines what a real gateway must support before Ant Code can be broadly deployed in the lab. It is provider-independent and describes only the client-to-gateway contract.

## Required Surface

| Area | Client behavior | Gateway requirement | Validation |
| --- | --- | --- | --- |
| Endpoint selection | Sends model traffic only to `LAB_MODEL_GATEWAY_URL`. | Expose a lab-owned chat endpoint reachable from lab clients. | `node src/cli/index.js gateway` |
| Protocol mode | Defaults to `lab-agent-gateway`; can translate to `openai-chat`. | Expose either the lab-owned protocol or an OpenAI Chat Completions compatible route. | Unit tests and live compat check |
| Health endpoint | Sends `GET` only when `--live` is explicit. | Expose `LAB_MODEL_GATEWAY_HEALTH_URL` with a 2xx ready status. | `node src/cli/index.js gateway --live` |
| Protocol version | Sends `protocolVersion: "lab-agent-gateway.v1"`. | Accept or explicitly reject unsupported protocol versions with a clear HTTP error. | `npm run verify:gateway`; live compat check |
| Request diagnostics metadata | Sends `metadata.capabilities` and `metadata.request` with booleans/counts only. | Ignore unknown metadata safely; optionally log counts for operator correlation. | Unit tests and live compat check |
| Boundary metadata | Sends `metadata.boundary` declaring local tool execution and gateway-only provider credentials. | Treat as non-authoritative diagnostics metadata; do not infer authorization from it. | Unit tests and live compat check |
| Model alias | Sends a lab alias from `LAB_AGENT_MODEL` or config. | Resolve alias server-side; do not require provider model IDs in the client. | Live compat check |
| Messages | Sends provider-independent `{ role, content }` messages. | Accept text messages without provider-specific fields. | Live compat check |
| Non-streaming text | Normalizes `content` text blocks into assistant text. | Return JSON with `content: [{ "type": "text", "text": "..." }]`. | Unit tests and live compat check |
| Tool calls | Executes supported tools locally after permission checks. | Return `toolCalls` with stable `id`, `name`, and object `input`. | Tool-call rollout phase |
| Tool results | Sends bounded `toolResults` after local execution. | Accept follow-up requests that include tool results. | Tool-call rollout phase |
| Streaming SSE | Parses `text/event-stream` records. | Emit supported record types or fall back to non-streaming. | Streaming rollout phase |
| Streaming NDJSON | Parses `application/x-ndjson` records. | Emit one JSON record per line or fall back to non-streaming. | Streaming rollout phase |
| HTTP errors | Normalizes non-2xx responses into bounded redacted errors. | Use meaningful HTTP status codes and bounded response bodies. | Gateway health/error tests |
| Parse errors | Returns a client-side `GATEWAY_RESPONSE_PARSE_ERROR`. | Keep responses valid JSON or valid stream records. | Gateway health/error tests |
| No local provider keys | Never reads provider keys for model requests. | Own provider credentials inside gateway infrastructure. | Environment review |
| Adapter authentication | Sends `Authorization: Bearer` only when `LAB_MODEL_GATEWAY_API_KEY` is configured. | Treat this as adapter access control, not provider credential pass-through. | OpenAI-compatible client test |
| Audit IDs | Displays only local output today. | Recommended: include request IDs in gateway logs for operator correlation. | Operator review |

## Required Request Shape

```json
{
  "protocolVersion": "lab-agent-gateway.v1",
  "model": "lab-default",
  "messages": [
    { "role": "user", "content": "hello" }
  ],
  "tools": [],
  "toolResults": [],
  "stream": false,
  "metadata": {
    "client": "lab-agent",
    "sessionId": "optional-session-id",
    "capabilities": {
      "tools": true,
      "toolResults": true,
      "streaming": false
    },
    "boundary": {
      "toolExecution": "local-client",
      "providerCredentials": "gateway-only",
      "remoteTools": false
    },
    "request": {
      "messageCount": 1,
      "toolCount": 0,
      "toolResultCount": 0
    }
  }
}
```

Required gateway behavior:

- Treat `metadata.sessionId` as a correlation hint, not an authentication token.
- Treat metadata capabilities/counts as diagnostics hints only; never infer authorization from them.
- Treat boundary metadata as a compatibility declaration only; tools remain local unless a future reviewed protocol changes this.
- Reject malformed JSON without returning stack traces.
- Apply gateway-side quota, model allowlist, provider routing, and retention policy.
- Never ask the local client for provider credentials.

## OpenAI Chat Compatible Request Shape

When `LAB_MODEL_GATEWAY_PROTOCOL=openai-chat`, the client sends Chat Completions compatible JSON:

```json
{
  "model": "lab-default",
  "messages": [
    { "role": "system", "content": "local tools only" },
    { "role": "user", "content": "hello" }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "read_file",
        "description": "Read a bounded UTF-8 text file region inside the active workspace.",
        "parameters": { "type": "object" }
      }
    }
  ],
  "tool_choice": "auto",
  "stream": false
}
```

Returned `choices[0].message.tool_calls` are converted back into local Ant Code `toolCalls`; local execution, approval, and bounded `tool` result handoff remain unchanged.

## Required Non-Streaming Response Shape

```json
{
  "id": "gateway-message-id",
  "model": "resolved-lab-model",
  "content": [
    { "type": "text", "text": "assistant response" }
  ],
  "toolCalls": [],
  "stopReason": "stop",
  "usage": {
    "promptBytes": 123,
    "completionBytes": 45
  }
}
```

Compatibility notes:

- `id`, `model`, `stopReason`, and `usage` may be null or omitted in MVP, but they are recommended for auditability.
- Text content must be bounded by gateway policy.
- Unknown content blocks are ignored by the MVP client.

## Required Tool-Call Shape

```json
{
  "id": "gateway-message-id",
  "model": "resolved-lab-model",
  "content": [],
  "toolCalls": [
    {
      "id": "tool-1",
      "name": "read_file",
      "input": { "path": "README.md", "maxBytes": 4096 }
    }
  ],
  "stopReason": "tool_use"
}
```

Compatibility notes:

- The gateway may request tools, but the local client remains the policy authority.
- Unknown tool names are not executed.
- Write and shell tools require explicit local approval.
- Tool recursion is bounded by the local client.

## Accepted Stream Records

The client accepts either SSE `data:` frames or NDJSON records with these types:

| Type | Required fields | Effect |
| --- | --- | --- |
| `message_start` | `id`, `model` optional | Starts a streamed assistant message. |
| `text_delta` | `text` | Appends text. |
| `content_delta` | `text` | Appends text. |
| `message_delta` | `text` optional | Appends text when present. |
| `message_stop` | `stopReason` optional | Ends the assistant message. |

Unsupported stream record types are ignored in MVP.

## Error Compatibility

| Scenario | Client result | Gateway recommendation |
| --- | --- | --- |
| Gateway URL missing | `GATEWAY_NOT_CONFIGURED` | Provide deployment config. |
| Network policy deny | `GATEWAY_NETWORK_BLOCKED` | Use lab-owned hosts and allowlists. |
| Timeout or fetch failure | `GATEWAY_TIMEOUT` or `GATEWAY_FETCH_ERROR` | Keep health endpoint simple and observable. |
| Non-2xx response | `GATEWAY_HTTP_ERROR` with bounded body | Return short JSON error bodies. |
| Invalid JSON or stream | `GATEWAY_RESPONSE_PARSE_ERROR` | Validate gateway serializers. |

## Rollout Status Template

| Requirement | Status | Evidence |
| --- | --- | --- |
| Dry gateway diagnostic | pending | Attach command output. |
| Live health diagnostic | pending | Attach command output and gateway request ID. |
| Live non-streaming chat | pending | Attach compatibility check output. |
| Tool-call round trip | pending | Attach scratch-workspace command output. |
| Streaming SSE | optional | Attach stream fixture or mark unsupported. |
| Streaming NDJSON | optional | Attach stream fixture or mark unsupported. |
| Gateway audit correlation | pending | Attach operator audit event ID. |
| Provider-key isolation | pending | Attach environment review. |
