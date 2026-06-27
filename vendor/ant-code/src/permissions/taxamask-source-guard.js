import path from "node:path";
import { approvalKeyFor } from "./approval-keys.js";

export const TAXAMASK_AUTH_NONE = "none";
export const TAXAMASK_AUTH_ADAPTER = "taxamask.adapter";
export const TAXAMASK_AUTH_SOURCE = "taxamask.source_development";

const SOURCE_ROOTS = Object.freeze([
  "AntSleap",
  "core",
  "tools",
  "tests",
  "vendor/ant-code/src",
  "vendor/ant-code/tests",
  "vendor/ant-code/scripts"
]);

const SOURCE_EXTENSIONS = Object.freeze([
  ".py",
  ".js",
  ".jsx",
  ".ts",
  ".tsx",
  ".css",
  ".html",
  ".mjs",
  ".cjs",
  ".sh",
  ".ps1",
  ".bat",
  ".cmd"
]);

const DEFAULT_ADAPTER_ROOTS = Object.freeze([
  "external_backends",
  "external_backend_adapters",
  "model_backends",
  ".tmp_validation/external_backends"
]);

const DEFAULT_ADAPTER_EXTENSIONS = Object.freeze([
  ".py",
  ".js",
  ".mjs",
  ".cjs",
  ".json",
  ".yaml",
  ".yml",
  ".toml",
  ".md",
  ".txt",
  ".ps1",
  ".sh",
  ".bat",
  ".cmd"
]);

const SOURCE_WRITE_TOOLS = new Set(["write_file", "edit_file"]);

const SHELL_WRITE_PATTERNS = Object.freeze([
  /\b(Set-Content|Add-Content|Out-File|New-Item|Copy-Item|Move-Item|Remove-Item)\b/i,
  /\b(del|erase|rm|mv|cp|touch|mkdir|rmdir)\b/i,
  /\b(git\s+(checkout|restore|reset|apply))\b/i,
  /(?:^|[^>])>>?\s*\S+/,
  /\bapply_patch\b/i
]);

const BROAD_SHELL_MUTATION_PATTERNS = Object.freeze([
  /\b(git\s+(checkout|restore|reset|apply|merge|rebase|clean))\b/i,
  /\bapply_patch\b/i
]);

export function isTaxaMaskSourcePath(cwd, candidate) {
  const relative = toRelativePath(cwd, candidate);
  if (!relative) {
    return false;
  }
  const extension = path.extname(relative).toLowerCase();
  if (!SOURCE_EXTENSIONS.includes(extension)) {
    return false;
  }
  return SOURCE_ROOTS.some((root) => relative === root || relative.startsWith(`${root}/`));
}

export function isTaxaMaskAdapterPath(cwd, candidate, policy = {}) {
  const relative = toRelativePath(cwd, candidate);
  if (!relative) {
    return false;
  }
  const extension = path.extname(relative).toLowerCase();
  const extensions = normalizeList(policy.adapterExtensions, DEFAULT_ADAPTER_EXTENSIONS);
  if (!extensions.includes(extension)) {
    return false;
  }
  const roots = normalizeList(policy.adapterRoots, DEFAULT_ADAPTER_ROOTS);
  return roots.some((root) => relative === root || relative.startsWith(`${root}/`));
}

export function taxamaskSourceWriteDecision(payload = {}, options = {}) {
  const toolName = String(payload.toolName ?? "");
  const input = payload.input ?? {};
  const cwd = options.cwd ?? payload.cwd ?? process.cwd();
  const policy = options.policy ?? {};
  const directTargets = collectDirectTargets(payload, input);
  const sourceAuth = normalizeTaxaMaskAuth(
    options.authorization
      ?? payload.taxamaskPermissionScope
      ?? payload.taxamaskAuthorization
  );
  const sourceTarget = directTargets.find((candidate) => isTaxaMaskSourcePath(cwd, candidate));
  const adapterTarget = directTargets.find((candidate) => isTaxaMaskAdapterPath(cwd, candidate, policy));

  if (SOURCE_WRITE_TOOLS.has(toolName) && sourceTarget) {
    if (sourceAuth === TAXAMASK_AUTH_SOURCE) {
      return allowDecision(TAXAMASK_AUTH_SOURCE, sourceTarget);
    }
    return approvalDecision(
      TAXAMASK_AUTH_SOURCE,
      sourceTarget,
      `${toolName} needs TaxaMask source development permission`,
      "TaxaMask source development",
      sourceApprovalMessage(sourceTarget)
    );
  }

  if ((toolName === "powershell" || toolName === "bash") && sourceTarget) {
    const command = String(input.command ?? "");
    if (looksLikeSourceMutatingShell(command)) {
      if (sourceAuth === TAXAMASK_AUTH_SOURCE) {
        return allowDecision(TAXAMASK_AUTH_SOURCE, sourceTarget);
      }
      return approvalDecision(
        TAXAMASK_AUTH_SOURCE,
        sourceTarget,
        "shell command needs TaxaMask source development permission",
        "TaxaMask source development",
        sourceApprovalMessage(sourceTarget)
      );
    }
  }

  if (toolName === "powershell" || toolName === "bash") {
    const command = String(input.command ?? "");
    if (looksLikeBroadSourceMutation(command)) {
      if (adapterTarget && !sourceTarget) {
        if (sourceAuth === TAXAMASK_AUTH_ADAPTER || sourceAuth === TAXAMASK_AUTH_SOURCE) {
          return allowDecision(sourceAuth, adapterTarget);
        }
        return approvalDecision(
          TAXAMASK_AUTH_ADAPTER,
          adapterTarget,
          "broad shell mutation needs TaxaMask model-adapter permission",
          "TaxaMask model adapter",
          adapterApprovalMessage(adapterTarget)
        );
      }
      if (sourceAuth === TAXAMASK_AUTH_SOURCE) {
        return allowDecision(TAXAMASK_AUTH_SOURCE, "TaxaMask source tree");
      }
      return approvalDecision(
        TAXAMASK_AUTH_SOURCE,
        "TaxaMask source tree",
        "broad shell mutation needs TaxaMask source development permission",
        "TaxaMask source development",
        sourceApprovalMessage("TaxaMask source tree")
      );
    }
  }

  if (toolName === "mcp_call" && isFilesystemWriteMcpCall(input) && sourceTarget) {
    if (sourceAuth === TAXAMASK_AUTH_SOURCE) {
      return allowDecision(TAXAMASK_AUTH_SOURCE, sourceTarget);
    }
    return approvalDecision(
      TAXAMASK_AUTH_SOURCE,
      sourceTarget,
      "filesystem MCP call needs TaxaMask source development permission",
      "TaxaMask source development",
      sourceApprovalMessage(sourceTarget)
    );
  }

  if (SOURCE_WRITE_TOOLS.has(toolName) && adapterTarget) {
    if (sourceAuth === TAXAMASK_AUTH_ADAPTER || sourceAuth === TAXAMASK_AUTH_SOURCE) {
      return allowDecision(sourceAuth, adapterTarget);
    }
    return approvalDecision(
      TAXAMASK_AUTH_ADAPTER,
      adapterTarget,
      `${toolName} needs TaxaMask model-adapter permission`,
      "TaxaMask model adapter",
      adapterApprovalMessage(adapterTarget)
    );
  }

  if ((toolName === "powershell" || toolName === "bash") && adapterTarget) {
    const command = String(input.command ?? "");
    if (looksLikeSourceMutatingShell(command)) {
      if (sourceAuth === TAXAMASK_AUTH_ADAPTER || sourceAuth === TAXAMASK_AUTH_SOURCE) {
        return allowDecision(sourceAuth, adapterTarget);
      }
      return approvalDecision(
        TAXAMASK_AUTH_ADAPTER,
        adapterTarget,
        "shell command needs TaxaMask model-adapter permission",
        "TaxaMask model adapter",
        adapterApprovalMessage(adapterTarget)
      );
    }
  }

  if (toolName === "mcp_call" && isFilesystemWriteMcpCall(input) && adapterTarget) {
    if (sourceAuth === TAXAMASK_AUTH_ADAPTER || sourceAuth === TAXAMASK_AUTH_SOURCE) {
      return allowDecision(sourceAuth, adapterTarget);
    }
    return approvalDecision(
      TAXAMASK_AUTH_ADAPTER,
      adapterTarget,
      "filesystem MCP call needs TaxaMask model-adapter permission",
      "TaxaMask model adapter",
      adapterApprovalMessage(adapterTarget)
    );
  }

  return { blocked: false };
}

export function normalizeTaxaMaskAuth(value) {
  const text = String(value ?? "").trim().toLowerCase();
  if ([
    "source",
    "source_development",
    "taxamask.source",
    "taxamask.source_development",
    "taxamask-source-development"
  ].includes(text)) {
    return TAXAMASK_AUTH_SOURCE;
  }
  if ([
    "adapter",
    "model_adapter",
    "external_backend_adapter",
    "taxamask.adapter",
    "taxamask.model_adapter",
    "taxamask-model-adapter"
  ].includes(text)) {
    return TAXAMASK_AUTH_ADAPTER;
  }
  return TAXAMASK_AUTH_NONE;
}

export function looksLikeSourceMutatingShell(command) {
  const text = String(command ?? "");
  return SHELL_WRITE_PATTERNS.some((pattern) => pattern.test(text));
}

export function looksLikeBroadSourceMutation(command) {
  const text = String(command ?? "");
  return BROAD_SHELL_MUTATION_PATTERNS.some((pattern) => pattern.test(text));
}

function collectDirectTargets(payload, input) {
  const targets = [];
  addTarget(targets, input.path);
  addTarget(targets, input.file);
  addTarget(targets, input.targetPath);
  addTarget(targets, input.destination);
  addTarget(targets, input.output);
  addTarget(targets, input.outFile);
  for (const value of payload.targetPaths ?? []) {
    addTarget(targets, value);
  }
  addNestedTargets(targets, input.arguments);
  addNestedTargets(targets, input.args);
  for (const value of sourcePathsMentionedInCommand(input.command)) {
    addTarget(targets, value);
  }
  return Array.from(new Set(targets));
}

function sourcePathsMentionedInCommand(command) {
  const text = String(command ?? "");
  if (!text) {
    return [];
  }
  const matches = new Set();
  const tokenPattern = /"([^"]+)"|'([^']+)'|`([^`]+)`|([^\s"'`|;&<>]+)/g;
  for (const match of text.matchAll(tokenPattern)) {
    const token = cleanCommandToken(match[1] ?? match[2] ?? match[3] ?? match[4] ?? "");
    const sourceCandidate = sourceCandidateFromToken(token);
    if (sourceCandidate) {
      matches.add(sourceCandidate);
    }
  }
  return [...matches];
}

function addTarget(targets, value) {
  if (typeof value === "string" && value.trim()) {
    targets.push(cleanCommandToken(value));
  }
}

function addNestedTargets(targets, value, key = "") {
  if (typeof value === "string") {
    if (isPathLikeKey(key)) {
      addTarget(targets, value);
    }
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      addNestedTargets(targets, item, key);
    }
    return;
  }
  if (!value || typeof value !== "object") {
    return;
  }
  for (const [entryKey, entryValue] of Object.entries(value)) {
    addNestedTargets(targets, entryValue, entryKey);
  }
}

function blockDecision(target, reason) {
  return {
    blocked: true,
    target,
    reason,
    message: `TaxaMask source is read-only for the embedded Agent: ${safeLabel(target)}`
  };
}

function allowDecision(scope, target) {
  return {
    blocked: false,
    allowed: true,
    scope,
    target
  };
}

function approvalDecision(scope, target, reason, title, message) {
  const approvalKey = approvalKeyFor({
    toolName: "write_file",
    input: { path: target },
    decision: {
      sensitive: true,
      outsideWorkspace: false,
      targetPath: target,
      resolvedPath: target
    }
  });
  return {
    blocked: true,
    requiresApproval: true,
    scope,
    target,
    reason,
    title,
    message,
    approvalKey
  };
}

function sourceApprovalMessage(target) {
  return [
    "TaxaMask source development permission is required.",
    `Target: ${safeLabel(target)}`,
    "This can change the TaxaMask program itself, including 2D/STL, Agent Center, imports, or training behavior."
  ].join(" ");
}

function adapterApprovalMessage(target) {
  return [
    "TaxaMask model-adapter permission is required.",
    `Target: ${safeLabel(target)}`,
    "This can change an external backend adapter used for training or prediction, but it does not unlock TaxaMask source files."
  ].join(" ");
}

function toRelativePath(cwd, candidate) {
  const text = String(candidate ?? "").trim();
  if (!text) {
    return "";
  }
  const withoutFileUri = text.startsWith("file://") ? text.replace(/^file:\/+/, "") : text;
  const resolved = path.isAbsolute(withoutFileUri)
    ? path.resolve(withoutFileUri)
    : path.resolve(cwd || process.cwd(), withoutFileUri);
  return toPosix(path.relative(path.resolve(cwd || process.cwd()), resolved)).replace(/^\.\//, "");
}

function toPosix(value) {
  return String(value ?? "").split(path.sep).join("/");
}

function normalizeList(value, fallback) {
  const source = Array.isArray(value) && value.length > 0 ? value : fallback;
  return Array.from(new Set(source
    .map((item) => String(item ?? "").trim().replace(/\\/g, "/").replace(/^\.\/+/, "").replace(/\/+$/, ""))
    .filter(Boolean)));
}

function safeLabel(candidate) {
  return String(candidate ?? "").replace(/\\/g, "/");
}

function cleanCommandToken(value) {
  return String(value ?? "")
    .trim()
    .replace(/^['"`]+|['"`]+$/g, "")
    .replace(/^[({[]+/, "")
    .replace(/[),\].}]+$/g, "")
    .replace(/^\.[\\/]/, "");
}

function sourceCandidateFromToken(token) {
  const text = String(token ?? "").replace(/\\/g, "/");
  if (!text) {
    return "";
  }
  const roots = [
    "AntSleap/",
    "core/",
    "tools/",
    "tests/",
    "vendor/ant-code/src/",
    "vendor/ant-code/tests/",
    "vendor/ant-code/scripts/"
  ];
  for (const root of roots) {
    const index = text.toLowerCase().indexOf(root.toLowerCase());
    if (index >= 0) {
      return text.slice(index);
    }
  }
  return text;
}

function isPathLikeKey(key) {
  return /^(path|paths|file|files|target|targetPath|targetPaths|destination|dest|output|outFile|filename|uri)$/i
    .test(String(key ?? ""));
}

function isFilesystemWriteMcpCall(input) {
  const server = String(input.server ?? "").toLowerCase();
  const tool = String(input.tool ?? "").toLowerCase();
  return server.includes("filesystem")
    && /^(write_file|edit_file|create_directory|move_file|delete_file)$/i.test(tool);
}

