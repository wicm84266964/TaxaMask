import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { collectSessionFiles, previewFile, resolveWorkspaceFile } from "../../src/dashboard/files.js";

test("dashboard file preview blocks paths outside workspace", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-files-"));
  const outside = path.join(os.tmpdir(), "outside-dashboard-file.txt");

  const resolved = resolveWorkspaceFile(cwd, outside);

  assert.equal(resolved.ok, false);
  assert.equal(resolved.status, 403);
});

test("dashboard previews markdown as text content", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-files-"));
  await fs.writeFile(path.join(cwd, "report.md"), "# Report\n\nDone.", "utf8");

  const result = await previewFile(cwd, "report.md");

  assert.equal(result.ok, true);
  assert.equal(result.file.kind, "markdown");
  assert.match(result.file.content, /Report/);
});

test("dashboard previews structured data files as data content", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-files-"));
  await fs.writeFile(path.join(cwd, "data.json"), "{\"ok\":true}", "utf8");
  await fs.writeFile(path.join(cwd, "table.csv"), "name,value\nsample,12\n", "utf8");

  const json = await previewFile(cwd, "data.json");
  const csv = await previewFile(cwd, "table.csv");

  assert.equal(json.ok, true);
  assert.equal(json.file.kind, "data");
  assert.equal(csv.ok, true);
  assert.equal(csv.file.kind, "data");
});

test("dashboard previews png images through raw workspace URLs", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-files-"));
  await fs.writeFile(path.join(cwd, "chart.png"), Buffer.from([0x89, 0x50, 0x4e, 0x47]));

  const result = await previewFile(cwd, "chart.png");

  assert.equal(result.ok, true);
  assert.equal(result.file.kind, "image");
  assert.equal(result.file.rawUrl, "/api/files/raw?path=chart.png");
});

test("dashboard previews nested markdown assets through workspace-relative paths", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-files-"));
  await fs.mkdir(path.join(cwd, "reports", "images"), { recursive: true });
  await fs.writeFile(path.join(cwd, "reports", "report.md"), "![图](images/chart.png)", "utf8");
  await fs.writeFile(path.join(cwd, "reports", "images", "chart.png"), Buffer.from([0x89, 0x50, 0x4e, 0x47]));

  const markdown = await previewFile(cwd, "reports/report.md");
  const image = await previewFile(cwd, "reports/images/chart.png");

  assert.equal(markdown.ok, true);
  assert.equal(markdown.file.relativePath, path.join("reports", "report.md"));
  assert.equal(image.ok, true);
  assert.equal(image.file.kind, "image");
});

test("dashboard collects workflow and mentioned files inside workspace", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-files-"));
  await fs.writeFile(path.join(cwd, "chart.png"), Buffer.from([0x89, 0x50, 0x4e, 0x47]));
  await fs.writeFile(path.join(cwd, "report.md"), "# Report\n", "utf8");
  const session = {
    cwd,
    workflow: {
      changes: [
        { path: "report.md", created: true, toolName: "write_file" }
      ]
    }
  };

  const files = collectSessionFiles(session, "see chart.png and C:\\outside\\secret.txt");

  assert.equal(files.some((file) => file.relativePath === "report.md"), true);
  assert.equal(files.some((file) => file.relativePath === "chart.png"), true);
  assert.equal(files.some((file) => file.path.includes("secret.txt")), false);
});

test("dashboard skips mentioned image files that do not exist", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-files-"));
  const session = { cwd, workflow: { changes: [] } };

  const files = collectSessionFiles(session, "see missing.png");

  assert.equal(files.some((file) => file.relativePath === "missing.png"), false);
});

test("dashboard collects mentioned files when persisted workflow changes are summarized", async () => {
  const cwd = await fs.mkdtemp(path.join(os.tmpdir(), "dashboard-files-"));
  await fs.writeFile(path.join(cwd, "chart.png"), Buffer.from([0x89, 0x50, 0x4e, 0x47]));
  const session = {
    cwd,
    workflow: {
      changes: { total: 1, created: 1, edited: 0, diffTruncated: 0 }
    }
  };

  const files = collectSessionFiles(session, "see chart.png");

  assert.equal(files.some((file) => file.relativePath === "chart.png"), true);
});
