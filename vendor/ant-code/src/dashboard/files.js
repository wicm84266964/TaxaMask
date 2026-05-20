import fs from "node:fs/promises";
import { statSync } from "node:fs";
import path from "node:path";

const DATA_EXTENSIONS = new Set([".json", ".csv", ".tsv", ".yaml", ".yml"]);
const TEXT_EXTENSIONS = new Set([".txt", ".log", ".json", ".csv", ".tsv", ".md", ".markdown", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".css", ".html", ".xml", ".yaml", ".yml", ".py", ".ps1", ".cmd", ".sh", ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".php", ".rb", ".sql", ".toml", ".ini"]);
const IMAGE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp"]);
const PREVIEWABLE_IMAGE_EXTENSIONS = new Set([...IMAGE_EXTENSIONS, ".svg"]);
const OFFICE_EXTENSIONS = new Set([".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]);
const MAX_TEXT_BYTES = 512 * 1024;
const MAX_RAW_BYTES = 20 * 1024 * 1024;

/**
 * @param {string} cwd
 * @param {string} requestedPath
 */
export async function previewFile(cwd, requestedPath) {
  const resolved = resolveWorkspaceFile(cwd, requestedPath);
  if (!resolved.ok) {
    return resolved;
  }
  const stat = await fs.stat(resolved.path).catch(() => null);
  if (!stat || !stat.isFile()) {
    return { ok: false, status: 404, error: "文件不存在或不是普通文件" };
  }
  const ext = path.extname(resolved.path).toLowerCase();
  const base = baseFile(resolved.path, cwd, stat);
  if (PREVIEWABLE_IMAGE_EXTENSIONS.has(ext)) {
    return { ok: true, file: { ...base, kind: "image", rawUrl: rawUrl(base.relativePath) } };
  }
  if (ext === ".pdf") {
    return { ok: true, file: { ...base, kind: "pdf", rawUrl: rawUrl(base.relativePath) } };
  }
  if (OFFICE_EXTENSIONS.has(ext)) {
    return { ok: true, file: { ...base, kind: "office", rawUrl: rawUrl(base.relativePath), message: "第一版提供文件卡片和打开入口，在线预览后续增强。" } };
  }
  if (TEXT_EXTENSIONS.has(ext) || stat.size <= MAX_TEXT_BYTES) {
    if (stat.size > MAX_TEXT_BYTES) {
      return { ok: true, file: { ...base, kind: "text", truncated: true, content: await readTextHead(resolved.path) } };
    }
    return { ok: true, file: { ...base, kind: fileKindForTextExtension(ext), content: await fs.readFile(resolved.path, "utf8") } };
  }
  return { ok: true, file: { ...base, kind: "binary", rawUrl: rawUrl(base.relativePath), message: "二进制文件不在网页中直接预览。" } };
}

/**
 * @param {string} cwd
 * @param {string} requestedPath
 */
export async function readRawFile(cwd, requestedPath) {
  const resolved = resolveWorkspaceFile(cwd, requestedPath);
  if (!resolved.ok) {
    return resolved;
  }
  const stat = await fs.stat(resolved.path).catch(() => null);
  if (!stat || !stat.isFile()) {
    return { ok: false, status: 404, error: "文件不存在或不是普通文件" };
  }
  if (stat.size > MAX_RAW_BYTES) {
    return { ok: false, status: 413, error: "文件过大，已阻止内嵌预览" };
  }
  return {
    ok: true,
    path: resolved.path,
    contentType: contentTypeForPath(resolved.path),
    bytes: await fs.readFile(resolved.path)
  };
}

/**
 * @param {Record<string, any>} session
 * @param {string} finalOutput
 */
export function collectSessionFiles(session, finalOutput = "") {
  const cwd = session?.cwd ?? process.cwd();
  const items = [];
  const changes = Array.isArray(session?.workflow?.changes) ? session.workflow.changes : [];
  for (const change of changes) {
    addFile(items, cwd, change.path, {
      source: change.created ? "created" : change.edited ? "edited" : "changed",
      toolName: change.toolName ?? null
    });
  }
  for (const candidate of extractPaths(finalOutput)) {
    addFile(items, cwd, candidate, { source: "mentioned" });
  }
  return dedupeFiles(items);
}

/**
 * @param {string} cwd
 * @param {string} requestedPath
 */
export function resolveWorkspaceFile(cwd, requestedPath) {
  const root = path.resolve(cwd);
  const text = String(requestedPath ?? "").trim();
  if (!text) {
    return { ok: false, status: 400, error: "缺少文件路径" };
  }
  const resolved = path.resolve(root, text);
  if (!isInside(root, resolved)) {
    return { ok: false, status: 403, error: "第一版只允许预览当前工作区内文件" };
  }
  return { ok: true, path: resolved };
}

/**
 * @param {string} cwd
 * @param {string} target
 */
export function fileSummary(cwd, target) {
  const resolved = path.resolve(cwd, target);
  return {
    path: resolved,
    relativePath: path.relative(cwd, resolved) || path.basename(resolved),
    name: path.basename(resolved),
    kind: kindForPath(resolved)
  };
}

function baseFile(filePath, cwd, stat) {
  return {
    path: filePath,
    relativePath: path.relative(cwd, filePath) || path.basename(filePath),
    name: path.basename(filePath),
    extension: path.extname(filePath).toLowerCase(),
    size: stat.size,
    modifiedAt: stat.mtime.toISOString()
  };
}

async function readTextHead(filePath) {
  const handle = await fs.open(filePath, "r");
  try {
    const buffer = Buffer.alloc(MAX_TEXT_BYTES);
    const read = await handle.read(buffer, 0, MAX_TEXT_BYTES, 0);
    return buffer.subarray(0, read.bytesRead).toString("utf8");
  } finally {
    await handle.close();
  }
}

function rawUrl(relativePath) {
  return `/api/files/raw?path=${encodeURIComponent(relativePath)}`;
}

function contentTypeForPath(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === ".png") return "image/png";
  if (ext === ".jpg" || ext === ".jpeg") return "image/jpeg";
  if (ext === ".gif") return "image/gif";
  if (ext === ".webp") return "image/webp";
  if (ext === ".svg") return "image/svg+xml";
  if (ext === ".pdf") return "application/pdf";
  return "application/octet-stream";
}

function kindForPath(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (PREVIEWABLE_IMAGE_EXTENSIONS.has(ext)) return "image";
  if (ext === ".pdf") return "pdf";
  if (ext === ".md" || ext === ".markdown") return "markdown";
  if (DATA_EXTENSIONS.has(ext)) return "data";
  if (TEXT_EXTENSIONS.has(ext)) return "text";
  if (OFFICE_EXTENSIONS.has(ext)) return "office";
  return "file";
}

function fileKindForTextExtension(ext) {
  if (ext === ".md" || ext === ".markdown") {
    return "markdown";
  }
  if (DATA_EXTENSIONS.has(ext)) {
    return "data";
  }
  return "text";
}

function extractPaths(text) {
  const matches = String(text ?? "").match(/(?:[A-Za-z]:[\\/][^\s"'<>|]+|(?:\.{1,2}[\\/])?[A-Za-z0-9_.-]+[\\/][A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,8}|[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,8})/g);
  return matches ?? [];
}

function addFile(items, cwd, target, meta = {}) {
  const value = String(target ?? "").trim();
  if (!value) {
    return;
  }
  const resolved = path.isAbsolute(value) ? value : path.resolve(cwd, value);
  if (!isInside(cwd, resolved)) {
    return;
  }
  if (!fileExists(resolved)) {
    return;
  }
  items.push({
    ...fileSummary(cwd, path.relative(cwd, resolved)),
    ...meta
  });
}

function dedupeFiles(items) {
  const seen = new Set();
  const out = [];
  for (const item of items) {
    const key = item.path.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    out.push(item);
  }
  return out;
}

function isInside(root, target) {
  const relative = path.relative(path.resolve(root), path.resolve(target));
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function fileExists(filePath) {
  try {
    const stat = statSync(filePath);
    return stat.isFile();
  } catch {
    return false;
  }
}
