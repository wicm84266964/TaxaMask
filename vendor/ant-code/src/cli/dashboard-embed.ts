#!/usr/bin/env node
import path from "node:path";
import { parseArgs } from "./args.ts";
import { startDashboard } from "../dashboard/server.ts";
import { ensureConfigV2 } from "../config-v2/activate.ts";
import { resolvePackageRoot } from "../version.ts";

const ROOT_DIR = resolvePackageRoot();

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const dashboardCwd = path.resolve(process.cwd(), args.dashboard.project ?? ".");
  await ensureConfigV2({ cwd: dashboardCwd, env: process.env });
  const result = await startDashboard({
    cwd: process.cwd(),
    env: process.env,
    packageRoot: ROOT_DIR,
    host: args.dashboard.host,
    port: args.dashboard.port,
    open: args.dashboard.open,
    project: args.dashboard.project
  });
  console.log(`Ant Code Dashboard running at ${result.url}`);
  console.log(`Project: ${result.cwd}`);
  console.log("Close it from the Dashboard sidebar, or press Ctrl+C in this terminal.");
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
