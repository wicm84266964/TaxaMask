/**
 * @param {unknown} error
 * @param {{ code?: string; message?: string; status?: number; details?: Record<string, any> }} context
 */
export function normalizeGatewayError(error, context = {}) {
  const code = context.code ?? inferCode(error);
  return {
    code,
    message: redactGatewayText(context.message ?? inferMessage(error)),
    status: context.status ?? null,
    details: redactDetails(context.details ?? {}),
    diagnostics: gatewayTroubleshootingHints(code, context.status ?? null),
    redacted: true
  };
}

/**
 * @param {unknown} error
 */
export function isGatewayStreamInterruptedError(error) {
  if (!error || typeof error !== "object") {
    return false;
  }
  const name = "name" in error ? String(error.name ?? "") : "";
  const code = "code" in error ? String(error.code ?? "") : "";
  const message = error instanceof Error ? error.message : String(error);
  return name === "AbortError"
    || code === "ABORT_ERR"
    || code === "UND_ERR_ABORTED"
    || /aborted|abort|terminated|premature close|stream.*interrupted/i.test(message);
}

/**
 * @param {Record<string, any>} error
 */
export function formatGatewayError(error) {
  const lines = [
    `Gateway error: ${error.code ?? "GATEWAY_ERROR"}`,
    `message: ${error.message ?? "request failed"}`
  ];
  if (error.status) {
    lines.push(`http status: ${error.status}`);
  }
  const diagnostics = Array.isArray(error.diagnostics) ? error.diagnostics : [];
  if (diagnostics.length > 0) {
    lines.push("diagnostics:");
    lines.push(...diagnostics.map((hint) => `- ${hint}`));
  }
  return lines.join("\n");
}

/**
 * @param {string} code
 * @param {number | null} status
 */
export function gatewayTroubleshootingHints(code, status = null) {
  if (code === "GATEWAY_NOT_CONFIGURED") {
    return [
      "Set LAB_MODEL_GATEWAY_URL to the lab gateway chat endpoint.",
      "Run /gateway or ant-code gateway before retrying the model turn."
    ];
  }
  if (code === "GATEWAY_NETWORK_BLOCKED") {
    return [
      "Check LAB_AGENT_NETWORK_MODE and LAB_AGENT_ALLOWED_HOSTS.",
      "Use lab-only with a gateway host on the allowlist, or offline only for loopback testing."
    ];
  }
  if (code === "GATEWAY_HTTP_ERROR") {
    if (status === 401 || status === 403) {
      return ["Check lab gateway authentication and user authorization at the gateway service."];
    }
    if (status === 404) {
      return ["Check that LAB_MODEL_GATEWAY_URL points to the chat route, usually /v1/chat."];
    }
    if (status && status >= 500) {
      return ["Check gateway server logs using the local session id and retry after the service is healthy."];
    }
    return ["Check gateway route, method, and reverse proxy configuration."];
  }
  if (code === "GATEWAY_RESPONSE_PARSE_ERROR") {
    return [
      "Verify the gateway returns JSON, text/event-stream, or application/x-ndjson in the supported protocol shape.",
      "Run npm run verify:gateway or node scripts/verify-gateway-compat.js --live."
    ];
  }
  if (code === "GATEWAY_TIMEOUT") {
    return [
      "Check gateway latency, model queue health, and reverse proxy timeout settings.",
      "Retry with a smaller prompt or after the gateway worker is healthy."
    ];
  }
  return ["Run /gateway --live and verify the configured lab gateway endpoint."];
}

/**
 * @param {string} value
 */
export function redactGatewayText(value) {
  return String(value)
    .replace(/(https?:\/\/)([^/\s:@]+):([^@\s/]+)@/gi, "$1[redacted]@")
    .replace(/([?&](?:api_?key|token|secret|password)=)[^&\s]+/gi, "$1[redacted]")
    .replace(/((?:api_?key|token|secret|password)\s*=\s*)\S+/gi, "$1[redacted]")
    .replace(/(Bearer\s+)[A-Za-z0-9._~+/=-]+/gi, "$1[redacted]")
    .replace(/(--?(?:api-?key|token|secret|password)(?:=|\s+))\S+/gi, "$1[redacted]");
}

/**
 * @param {unknown} error
 */
function inferCode(error) {
  if (error && typeof error === "object" && "name" in error && error.name === "AbortError") {
    return "GATEWAY_TIMEOUT";
  }
  return "GATEWAY_FETCH_ERROR";
}

/**
 * @param {unknown} error
 */
function inferMessage(error) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

/**
 * @param {Record<string, any>} details
 */
function redactDetails(details) {
  return JSON.parse(JSON.stringify(details, (_key, value) => (
    typeof value === "string" ? redactGatewayText(value) : value
  )));
}
