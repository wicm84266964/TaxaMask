import assert from "node:assert/strict";
import test from "node:test";
import { buildTaskTree, formatTaskTree } from "../../src/agents/orchestrator.js";
import { formatAgentRoute, routeAgentTask } from "../../src/agents/router.js";

test("agent router selects web researcher for external research prompts", () => {
  const route = routeAgentTask({
    cwd: process.cwd(),
    config: { agents: { profiles: [] } },
    prompt: "帮我联网搜索最新资料并整理来源"
  });

  assert.equal(route.primaryProfile, "web-researcher");
  assert.equal(route.version, 2);
  assert.equal(route.decision.purpose, "research");
  assert.equal(route.decision.modelTier, "cheap");
  assert.equal(route.signals.web, true);
  assert.ok(route.suggestedTasks.some((task) => task.profile === "web-researcher"));
  assert.match(formatAgentRoute(route), /web-researcher/);
});

test("agent router plans parallel readonly tasks for broad codebase implementation work", () => {
  const route = routeAgentTask({
    cwd: process.cwd(),
    config: { agents: { profiles: [] } },
    prompt: "调查这个大仓库的架构，计划 stage，然后修复一个代码问题"
  });

  const parallel = route.suggestedTasks.filter((task) => task.parallelSafe);
  assert.ok(parallel.length >= 2);
  assert.ok(parallel.some((task) => task.profile === "explorer"));
  assert.ok(parallel.some((task) => task.profile === "planner"));
  assert.ok(route.suggestedTasks.some((task) => task.profile === "junior" && task.parallelSafe === false));
  assert.equal(route.decision.difficulty, "deep");
  assert.ok(route.suggestedTasks.some((task) => task.profile === "junior" && task.budget.maxRounds === null));
});

test("agent router recommends reviewer for high-risk review prompts", () => {
  const route = routeAgentTask({
    cwd: process.cwd(),
    config: { agents: { profiles: [] } },
    prompt: "请严格审查这次全局安装和权限配置改动，找安全风险"
  });

  assert.equal(route.primaryProfile, "reviewer");
  assert.equal(route.decision.purpose, "review");
  assert.equal(route.decision.risk, "high");
  assert.equal(route.decision.modelTier, "strong");
  assert.equal(route.reviewRecommended, true);
  assert.ok(route.suggestedTasks.some((task) => task.profile === "reviewer"));
});

test("task tree nests orchestrated child tasks under parent task", () => {
  const tree = buildTaskTree([
    {
      id: "orchestrate-1",
      profile: "router",
      title: "子智能体编排",
      status: "completed",
      updatedAt: "2026-05-01T00:00:02.000Z"
    },
    {
      id: "orchestrate-1-route-1",
      parentTaskId: "orchestrate-1",
      profile: "explorer",
      status: "completed",
      prompt: "inspect",
      updatedAt: "2026-05-01T00:00:01.000Z"
    }
  ]);

  assert.equal(tree.length, 1);
  assert.equal(tree[0].children.length, 1);
  assert.match(formatTaskTree(tree.flatMap((task) => [task, ...task.children])), /orchestrate-1-route-1/);
});
