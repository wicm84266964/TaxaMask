import path from "node:path";

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

export function taxamaskSourceWriteDecision(payload = {}, options = {}) {
  const toolName = String(payload.toolName ?? "");
  const input = payload.input ?? {};
  const cwd = options.cwd ?? payload.cwd ?? process.cwd();
  const directTargets = collectDirectTargets(payload, input);
  const sourceTarget = directTargets.find((candidate) => isTaxaMaskSourcePath(cwd, candidate));

  if (SOURCE_WRITE_TOOLS.has(toolName) && sourceTarget) {
    return blockDecision(sourceTarget, `${toolName} cannot modify TaxaMask source files`);
  }

  if ((toolName === "powershell" || toolName === "bash") && sourceTarget) {
    const command = String(input.command ?? "");
    if (looksLikeSourceMutatingShell(command)) {
      return blockDecision(sourceTarget, "shell command appears to modify TaxaMask source files");
    }
  }

  if (toolName === "powershell" || toolName === "bash") {
    const command = String(input.command ?? "");
    if (looksLikeBroadSourceMutation(command)) {
      return blockDecision("TaxaMask source tree", "broad shell mutation could modify TaxaMask source files");
    }
  }

  if (toolName === "mcp_call" && isFilesystemWriteMcpCall(input) && sourceTarget) {
    return blockDecision(sourceTarget, "filesystem MCP call cannot modify TaxaMask source files");
  }

  return { blocked: false };
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
