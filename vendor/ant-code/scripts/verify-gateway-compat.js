#!/usr/bin/env node
import { fileURLToPath } from "node:url";
import { createMockGatewayServer } from "./mock-gateway.js";
import { loadConfig } from "../src/config/load-config.js";
import { createLabModelGateway } from "../src/model-gateway/client.js";
import { runGatewayHealth } from "../src/model-gateway/health.js";
import { GATEWAY_PROTOCOL_VERSION } from "../src/model-gateway/protocol.js";

const MOCK_MODEL_ALIAS = "compatibility-mock";

if (isMainModule()) {
  const args = new Set(process.argv.slice(2));
  const live = args.has("--live");
  const json = args.has("--json");
  const result = live ? await verifyLiveGateway() : await verifyMockGateway();

  if (json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    for (const line of formatCompatibilityReport(result)) {
      console.log(line);
    }
  }

  process.exitCode = result.ok ? 0 : 1;
}

export async function verifyMockGateway() {
  const server = await listen(createMockGatewayServer(), "127.0.0.1");
  try {
    const baseUrl = serverUrl(server);
    return await verifyGateway({
      mode: "mock",
      env: createMockVerificationEnv(baseUrl),
      mock: {
        gatewayUrl: `${baseUrl}/v1/chat`,
        healthUrl: `${baseUrl}/health`,
        modelAlias: MOCK_MODEL_ALIAS
      }
    });
  } finally {
    await close(server);
  }
}

/**
 * Mock verification intentionally inherits nothing from the user's shell.
 * @param {string} baseUrl
 */
export function createMockVerificationEnv(baseUrl) {
  return {
    LAB_AGENT_SKIP_PROJECT_CONFIG: "true",
    LAB_AGENT_MODEL: MOCK_MODEL_ALIAS,
    LAB_AGENT_NETWORK_MODE: "offline",
    LAB_MODEL_GATEWAY_URL: `${baseUrl}/v1/chat`,
    LAB_MODEL_GATEWAY_HEALTH_URL: `${baseUrl}/health`,
    LAB_MODEL_GATEWAY_PROTOCOL: "lab-agent-gateway",
    LAB_MODEL_GATEWAY_MAX_RETRIES: "0",
    LAB_MODEL_GATEWAY_TIMEOUT_MS: "5000",
    LAB_MODEL_GATEWAY_IDLE_TIMEOUT_MS: "5000"
  };
}

async function verifyLiveGateway() {
  return verifyGateway({
    mode: "live",
    env: process.env
  });
}

/**
 * @param {{ mode: string; env: NodeJS.ProcessEnv; mock?: { gatewayUrl: string; healthUrl: string; modelAlias: string } }} options
 */
async function verifyGateway(options) {
  const checks = [];
  const cwd = process.cwd();
  const health = await runGatewayHealth({
    cwd,
    env: options.env,
    live: true,
    timeoutMs: 5000
  });

  const healthIssues = health.checks.filter((check) => (
    check.status === "error" || (options.mode === "live" && check.status === "warn")
  ));
  checks.push({
    name: "health",
    status: health.ok && healthIssues.length === 0 ? "ok" : "error",
    message: summarizeHealth(health, healthIssues)
  });

  const config = await loadConfig({ cwd, env: options.env });
  if (options.mode === "mock") {
    config.modelAlias = options.mock.modelAlias;
    config.networkMode = "offline";
    config.allowedHosts = ["127.0.0.1"];
    config.lab = {
      ...config.lab,
      gatewayUrl: options.mock.gatewayUrl,
      gatewayHealthUrl: options.mock.healthUrl,
      gatewayProtocol: "lab-agent-gateway",
      gatewayApiKey: null,
      gatewayMaxRetries: 0,
      gatewayTimeoutMs: 5000,
      gatewayIdleTimeoutMs: 5000
    };
  }
  const gateway = createLabModelGateway(config);
  const chat = await gateway.sendChat({
    messages: [{ role: "user", content: "compatibility ping" }],
    tools: []
  });

  checks.push(chat.ok
    ? {
        name: "chat",
        status: chat.data.text ? "ok" : "error",
        message: chat.data.text ? "text response normalized" : "gateway returned no text"
      }
    : {
        name: "chat",
        status: "error",
        message: `${chat.error?.code ?? "GATEWAY_ERROR"}: ${chat.error?.message ?? "request failed"}`
      });

  return {
    mode: options.mode,
    ok: checks.every((check) => check.status === "ok"),
    evidence: buildEvidence({
      mode: options.mode,
      config,
      health,
      chatOk: chat.ok
    }),
    checks
  };
}

/**
 * @param {{ checks: Array<{ name: string; status: string; message: string }> }} health
 * @param {Array<{ name: string; status: string; message: string }>} issues
 */
function summarizeHealth(health, issues) {
  if (issues.length === 0) {
    return "configuration, policy, and live health endpoint passed";
  }
  return issues.map((check) => `${check.name}: ${check.message}`).join("; ");
}

/**
 * @param {{ mode: string; config: Record<string, any>; health: Record<string, any>; chatOk: boolean }} input
 */
function buildEvidence(input) {
  return {
    mode: input.mode,
    protocolVersion: GATEWAY_PROTOCOL_VERSION,
    gatewayProtocol: input.config.lab?.gatewayProtocol ?? "lab-agent-gateway",
    modelAlias: input.config.modelAlias,
    networkMode: input.config.networkMode,
    gatewayConfigured: Boolean(input.config.lab?.gatewayUrl),
    healthConfigured: Boolean(input.config.lab?.gatewayHealthUrl),
    liveHealth: Boolean(input.health.live),
    chatNormalized: input.chatOk,
    boundary: {
      toolExecution: "local-client",
      providerCredentials: "gateway-only",
      remoteTools: false
    }
  };
}

/**
 * @param {{ mode: string; ok: boolean; checks: Array<{ name: string; status: string; message: string }> }} result
 */
function formatCompatibilityReport(result) {
  return [
    "Ant Code model gateway compatibility",
    `mode: ${result.mode}`,
    `protocol: ${result.evidence.protocolVersion}`,
    `gateway protocol: ${result.evidence.gatewayProtocol}`,
    `model: ${result.evidence.modelAlias}`,
    `network: ${result.evidence.networkMode}`,
    "boundary: tools=local-client, providerCredentials=gateway-only, remoteTools=false",
    "",
    ...result.checks.map((check) => `${formatStatus(check.status)} ${check.name}: ${check.message}`),
    "",
    "Evidence JSON:",
    "  node scripts/verify-gateway-compat.js --live --json"
  ];
}

/**
 * @param {string} status
 */
function formatStatus(status) {
  return status === "ok" ? "[ok]" : "[error]";
}

/**
 * @param {import("node:http").Server} server
 * @param {string} host
 */
function listen(server, host) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, host, () => {
      server.off("error", reject);
      resolve(server);
    });
  });
}

/**
 * @param {import("node:http").Server} server
 */
function close(server) {
  return new Promise((resolve, reject) => {
    server.close((error) => error ? reject(error) : resolve(undefined));
  });
}

/**
 * @param {import("node:http").Server} server
 */
function serverUrl(server) {
  const address = server.address();
  if (!address || typeof address === "string") {
    throw new Error("server did not expose an address");
  }
  return `http://127.0.0.1:${address.port}`;
}

function isMainModule() {
  return process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
}
