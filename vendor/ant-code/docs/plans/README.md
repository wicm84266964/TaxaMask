# Ant Code 大改计划档案

日期：2026-05-02

本目录用于管理 Ant Code 每次较大架构、TUI、智能体、外部能力、运行时策略变更前的计划文档。

以后凡是会影响核心交互、工具执行、权限模型、子智能体调度、MCP/skill 能力、上下文管理或发布验收的大改，都必须先在这里形成计划，待用户审核通过后再动工。

## 目录规则

```text
docs/plans/
  README.md
  active/      待审核、已审核但尚未完全执行的计划
  completed/   已完成或已阶段性关闭的计划归档
```

## 写作规则

每份计划文档至少包含：

1. 日期、状态、适用仓库。
2. 一句话目标。
3. 当前基线和问题背景。
4. 参考来源和可借鉴点。
5. 明确边界：本轮做什么、不做什么。
6. 分 stage 的实施计划。
7. 每个 stage 的验收方法。
8. 风险、回滚、测试和文档更新要求。

计划通过后，执行中要在原文档里更新 stage 状态，不能只写在聊天记录中。

计划完成后，将文档从 `active/` 移入 `completed/`，并更新本索引。

## 当前待审计划

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| `active/dashboard-webui-plan-2026-05-13.md` | 待审核，尚未执行 | Ant Code Dashboard WebUI 新入口计划：`ant-code dashboard`、本机访问、共享会话、折叠活动流、右侧预览和网页权限弹窗。 |
| `active/tui-markdown-table-rendering-plan-2026-05-03.md` | 待审核/部分曾实验 | Markdown 表格块级渲染改造计划；当前仍保留在 active，后续需确认是否继续、关闭或重写。 |

## 已完成计划

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| `completed/tui-agent-architecture-upgrade-plan-2026-04-30.md` | 已完成 | TUI 与智能体调度第一轮大改，包括 overlay、滚动、右侧栏、MCP、skills、background 和文档收尾。 |
| `completed/external-capabilities-agent-orchestration-upgrade-plan-2026-05-01.md` | 已完成 | 外部能力、MCP、web/browser/document/skill、agent profile v2、router 和并行只读任务升级。 |
| `completed/subagent-orchestration-v2-design-2026-05-01.md` | 已完成 | 子智能体编排 v2 设计和实现依据，包括主调度器、one-shot 子任务池、模型路由、预算、任务可观察性。 |
| `completed/hooks-v1-local-runtime-plan-2026-05-02.md` | 已完成 | 本地 Hooks v1：运行时事件、审计、安全拦截、command hook、子智能体/compact/session 接入和 `/hooks` 状态面板。 |
| `completed/delegation-guard-orchestration-plan-2026-05-04.md` | 已完成 | 主控强 prompt 与 delegation guard：广域搜索/读取时向模型可见工具结果注入子智能体派发提醒，并写入 `/logs` 审计。 |
| `completed/subagent-background-wakeup-orchestration-plan-2026-05-05.md` | 已完成 | 子智能体后台运行、任务组等待、完成后自动唤醒主控、review gate、按组取消和 TUI 任务组展示升级。 |
| `completed/dashboard-report-rendering-plan-2026-05-14.md` | 已完成 | Dashboard 报告型富渲染增强：数学公式、Mermaid、JSON/YAML/CSV 数据预览、图片集 lightbox 和长内容目录。 |

## 后续维护要求

- 不要把用户 API key、网关 key、`.env` 内容或私密路径样本写入计划文档。
- 如果计划引用旧源码或外部项目，只记录产品行为、公开文档、可观察机制和净化后的设计结论。
- 大改执行后同步更新：
  - `PROJECT_CHANGELOG.zh-CN.md`
  - `LLM_ONBOARDING.md`
  - 相关 `docs/deployment/` 验收记录
  - 相关 `docs/provenance/` 模块说明
- 如果计划被放弃，也要保留在 `completed/` 或另建状态说明，避免以后重复踩坑。
