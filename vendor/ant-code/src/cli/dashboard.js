#!/usr/bin/env node
import { parseArgs } from "./args.js";
import { startDashboard } from "../dashboard/server.js";
import { resolvePackageRoot } from "../version.js";
import { helpText } from "../ui/output.js";
import { getAntCodeVersion } from "../version.js";

async function main() {
  const args = parseArgs(["dashboard", ...process.argv.slice(2)]);
  if (args.help) {
    console.log(helpText());
    return;
  }
  if (args.version) {
    console.log(`ant-code ${await getAntCodeVersion(resolvePackageRoot())}`);
    return;
  }
  const result = await startDashboard({
    cwd: process.cwd(),
    env: process.env,
    packageRoot: resolvePackageRoot(),
    host: args.dashboard.host,
    port: args.dashboard.port,
    open: args.dashboard.open,
    project: args.dashboard.project,
    parentPid: args.dashboard.parentPid
  });
  console.log(`Ant Code Dashboard running at ${result.url}`);
  console.log(`Project: ${result.cwd}`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
