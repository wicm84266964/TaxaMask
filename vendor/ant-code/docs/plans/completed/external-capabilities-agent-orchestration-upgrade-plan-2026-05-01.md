# Ant Code 外部能力与子智能体编排升级计划

日期：2026-05-01

状态：Stage 1-10 已实现；Stage 7-10 完成 agent profile v2、router、并行只读子任务、任务树、安全权限审计、文档和测试收尾。

## 目标

本计划用于把当前 Ant Code 从“本地代码助手 + 基础子智能体”升级为“具备外部信息获取、网页抓取、浏览器操控、文档解析、技能工作流和可观察子智能体调度”的实验室级代码智能体。

本轮升级重点不是接入更多大模型协议，而是补齐当前较弱的能力层：

1. 免 key 或本地可运行的网络检索、网页抓取和资料提取。
2. 可控的浏览器自动化能力。
3. 面向实验室工作流的本地 skill pack。
4. 更像 opencode 的子任务调度：只读研究、规划、实现、验证、浏览器验收可分工。
5. 更像旧 Ant Code 的技能生态：skill 可以带说明、模板、脚本、资源和验证入口，但不依赖 Claude 生态。
6. 在 TUI 右侧栏和日志中可观察每个子任务、MCP 调用、skill 工作流的状态。

## 当前基线

当前 `lab-agent` 已有：

- OpenAI-compatible 本地网关模型调用。
- 基础 TUI、会话、恢复、compact、权限审批、todo/plan 侧栏。
- 内置工具：文件读写、grep/glob、git diff/status、PowerShell/bash、MCP list/call、skill list/read/run、agent_run、todo/plan、ask_user。
- 子智能体 profiles：
  - `build`
  - `explorer`
  - `readonly-researcher` / `researcher` / `research`
  - `planner`
  - `verifier`
  - `code-worker`
  - 内部 `compaction`、`title`、`summary`
- 本地 skills：
  - `codebase-orientation`
  - `release-readiness-review`
  - `test-failure-triage`
- MCP 配置样例：
  - `filesystem`
  - `memory`
  - `playwright`

主要短板：

- 没有稳定的一等 `web_fetch`、`web_search`、`browser`、`document_intake` 能力。
- MCP 只是可调用通道，缺少推荐配置、doctor、启用向导、能力说明和验收。
- skill 目前更接近“说明文档”，没有成体系覆盖网络研究、浏览器、文档、项目接手、bug 复现等常用任务。
- 子智能体目前能运行，但调度策略仍偏手工；主智能体不会稳定地根据任务类型自动拆分和并行调度。
- 右侧栏能显示 todo/agent 信息，但还不是完整的任务树/能力运行面板。

## 2026-05-01 实施状态

已落地 Stage 1-10：

- Stage 1：新增 capability registry 和 `/capabilities`，可列出内置工具、MCP、skills、子智能体。
- Stage 2：新增 no-key MCP 推荐配置和 `/mcp doctor`；自包含开源 MCP 默认启用，SearXNG/SQLite 等依赖本地服务或数据源的项目继续按配置启用；普通 doctor 不自动拉起第三方服务。
- Stage 3：新增内置 `web_fetch`、`web_search`，统一走网络权限策略。
- Stage 4：落地 `browser-automation` skill，并启用 `playwright` MCP 默认配置；具体页面导航、点击、输入仍受权限策略控制。
- Stage 5：新增 `document_intake` 工具和 `document-intake` skill；核心支持文本/HTML/轻量 Office 文档，PDF 需 MarkItDown 或外部转换。
- Stage 6：新增本地 skill pack：`web-research`、`browser-automation`、`document-intake`、`project-intake`、`bug-repro`、`frontend-verifier`、`release-review`。

未开始：

- Stage 7：Agent profile v2 和 router 已落地；profile 支持 `triggerHints`、`skills`、`mcpServers`、`outputContract`；新增 `web-researcher`、`browser-verifier` 专用 profile；`/agents route <任务>` 可解释调度建议。
- Stage 8：并行只读子任务和任务树已落地；`/agents orchestrate <任务>` 只启动安全的只读并行任务，写入/执行型任务保留为串行建议；`/agents tasks` 和右侧任务栏显示父子任务树。
- Stage 9：权限和审计增强已落地；风险类别扩展到 `network`、`browser`、`document`、`mcp`、`memory`；MCP 子进程默认 scrub 敏感环境变量，并支持显式 `envAllowlist`。
- Stage 10：新增 agent router/task-tree/权限/MCP env scrub 测试；更新 `LLM_ONBOARDING.md`、`PROJECT_CHANGELOG.zh-CN.md` 和人工验收脚本。

## 参考结论

### opencode 值得借鉴的点

opencode 的强点不在复杂角色数量，而在边界清晰：

- 主代理工具层内置 `fetch`、代码搜索、LSP diagnostics、MCP 自动发现和权限审批。
- `agent` 工具专门用于只读调查任务，子代理只拿搜索/读取类工具，不允许修改文件。
- 子代理是 stateless，一次任务一次报告，主代理可并行启动多个调查任务。
- 工具权限统一进入审批系统，MCP 工具也不绕过权限。
- 配置里把不同 agent 的模型和 token 上限独立出来。

适合我们借鉴：

- 只读研究代理默认可并行。
- 子代理输出固定结构，便于主会话摘要和右侧栏展示。
- 内置网络抓取/搜索能力，不完全依赖外部 MCP。
- MCP 工具发现后进入统一权限模型。

不直接照搬：

- 不引入 Anthropic 协议依赖。
- 不照搬源码实现。
- 不把所有能力塞进同一个 `agent` 工具描述，Ant Code 应该保留 profile 化和中文 TUI。

### 旧 Ant Code 值得借鉴的点

旧版强在“技能生态厚度”：

- `.claude/skills` 中有 paper、literature、excel、powerpoint、render、download、finetune 等技能包。
- 技能不仅是提示词，还可以带 templates、scripts、references、runtime、sidecar worker。
- 有 global sync、verify、doctor、能力清单和维护文档。
- AgentTool、SkillTool、MCPTool、LocalAgentTask/RemoteAgentTask 都围绕“能力可被发现和编排”组织。

适合我们借鉴：

- skill 目录结构：`SKILL.md` + `scripts/` + `templates/` + `references/` + `assets/`。
- skill 自测入口和能力清单。
- sidecar worker 只做叶子任务，主编排留在 Ant Code。
- 全局安装后仍能发现项目内/用户内 skills。

不直接恢复：

- 不恢复 `.claude` 作为主目录。
- 不接入 Claude 官方 marketplace。
- 不把旧项目的大体积 runtime、dist、node_modules、日志、缓存搬回当前仓库。

## 设计原则

1. 默认安全：自包含开源 MCP 可以默认启用，但网络、浏览器、文件写入、长期记忆和外部服务访问仍需要权限策略约束。
2. 免 key 优先：首批只选不用 API key 的能力；需要 key 的服务只作为后续可选项。
3. 本地优先：MCP、skill、脚本和 sidecar 都在本地运行，不自动拉远端 marketplace。
4. 权限统一：文件写入、命令执行、网络访问、浏览器动作、MCP 调用都走同一权限引擎。
5. 可观察：每次 tool、MCP、skill、subagent 都能在 TUI 看到状态和结果摘要。
6. 可诊断：提供 `/mcp doctor`、`/skills doctor`、`/agents tasks` 一类命令。
7. 可回滚：每个 stage 尽量独立，不把所有风险压到一次大提交。
8. 不写入密钥：不得把本地网关 API key、cookie、token、真实 `.env` 写入仓库。

## 首批外部能力清单

### MCP 候选

| 名称 | 包/来源 | 默认 | 用途 | 风险与取舍 |
|---|---|---|---|---|
| `fetch` | `mcp-server-fetch` | 关闭 | 抓取 URL，转 text/markdown/html | 稳定、免 key；需要限制响应大小和 host 权限 |
| `duckduckgo-search` | `duckduckgo-mcp-server` | 关闭 | 无 key 搜索网页 | 方便但可能被限流；不能承诺结果稳定 |
| `searxng` | `mcp-searxng` | 关闭 | 连接实验室自建 SearXNG | 推荐作为长期搜索方案；需要用户配置实例 URL |
| `playwright` | `@playwright/mcp` | 关闭 | 浏览器打开、点击、输入、截图、页面快照 | 能力强但上下文重；必须权限隔离 |
| `memory` | `@modelcontextprotocol/server-memory` | 关闭 | 本地知识图谱/长期记忆 | 可选；避免未确认内容污染记忆 |
| `filesystem` | `@modelcontextprotocol/server-filesystem` | 关闭 | 标准 MCP 文件系统 | 与内置文件工具重叠；主要用于兼容 MCP 生态 |
| `sequential-thinking` | `@modelcontextprotocol/server-sequential-thinking` | 关闭 | 复杂任务结构化思考 | 可选；不能代替 todo/plan 和真实验证 |
| `sqlite` | `mcp-server-sqlite` | 关闭 | 查询本地 SQLite 数据 | 适合后续数据分析；首轮不强依赖 |

### 非 MCP 本地工具候选

| 名称 | 来源 | 用途 | 判断 |
|---|---|---|---|
| `web_fetch` 内置工具 | Ant Code 自己实现 | 免 MCP 的基础 URL 抓取和 Markdown 转换 | 应作为一等工具实现 |
| `web_search` 内置工具 | DuckDuckGo/SearXNG adapter | 统一搜索接口 | 应提供，但结果需标注来源和不稳定性 |
| `document_intake` | `markitdown` 或本地脚本 | PDF/Word/PPT/Excel/HTML 转 Markdown | 对实验室很有价值 |
| `browser_verify` | Playwright CLI workflow | 前端页面验收、截图、DOM 检查 | 推荐用 skill + CLI，减少 MCP 上下文负担 |

## 首批本地 skill pack

### `web-research`

用途：

- 根据问题搜索网页。
- 抓取 3-5 个来源。
- 生成带来源链接的摘要。
- 标注时间敏感性、来源可信度和无法验证的点。

依赖：

- `web_search`
- `web_fetch`
- 可选 `duckduckgo-search` / `searxng` MCP

验收：

- 能回答一个需要联网查证的问题。
- 输出必须包含来源。
- 网络关闭时能明确说明缺少网络能力。

### `browser-automation`

用途：

- 打开本地或远端网页。
- 点击、输入、截图、观察页面。
- 做前端验收和回归测试。

依赖：

- Playwright CLI workflow
- 可选 `@playwright/mcp`

验收：

- 能打开本地 dev server。
- 能截图并描述关键 UI。
- 能对按钮/输入框做一次交互。
- 浏览器权限弹窗可被用户拒绝或允许。

### `document-intake`

用途：

- 把 PDF、Word、PPT、Excel、HTML 转成 Markdown 或结构化摘要。
- 输出文档标题、章节、表格、图片占位和待核查项。

依赖：

- `markitdown`
- 本地文件读取权限

验收：

- 对一个小 PDF 或 docx 生成摘要。
- 对 Excel 输出 sheet 名称和表格预览。
- 大文件有截断提示。

### `project-intake`

用途：

- 接手陌生仓库。
- 识别技术栈、入口、测试命令、配置文件、风险点。
- 生成“下一步改动建议”。

依赖：

- `glob`
- `grep`
- `read_file`
- `git_status`
- 可选 `agent_run explorer`

验收：

- 能在当前仓库输出结构化项目画像。
- 不修改文件。

### `bug-repro`

用途：

- 复现 bug。
- 定位最小触发路径。
- 区分环境问题、实现问题、测试问题。
- 给出修复建议和验证命令。

依赖：

- `powershell` / `bash`
- `grep`
- `read_file`
- `verifier`

验收：

- 对一个故意失败的测试能给出失败原因和下一步。

### `frontend-verifier`

用途：

- 针对 TUI/Web UI 做验收。
- 检查小窗口、大窗口、滚动、布局、输入、快捷键、截图。

依赖：

- Playwright CLI 或本地 TUI smoke scripts。
- 可选浏览器 MCP。

验收：

- 能形成“通过/失败/截图证据/复现步骤”报告。

### `release-review`

用途：

- 发版前检查文档、计划状态、测试、配置、全局安装、备份。

依赖：

- 现有 `release-readiness-review` 扩展。

验收：

- 能列出发布阻塞项和非阻塞风险。

## 子智能体编排升级

### Agent profile v2

每个 profile 增加更明确的字段：

```json
{
  "name": "web-researcher",
  "mode": "readonly",
  "model": "claude-haiku-4-5-20251001",
  "tools": ["web_search", "web_fetch", "mcp_list", "mcp_call", "skill_read"],
  "skills": ["web-research"],
  "mcpServers": ["fetch", "duckduckgo-search", "searxng"],
  "maxRounds": 3,
  "background": true,
  "outputContract": "research-report-v1",
  "triggerHints": ["联网查证", "搜索资料", "查公开信息", "找文档"]
}
```

新增推荐 profiles：

| profile | 模式 | 作用 |
|---|---|---|
| `web-researcher` | readonly | 联网搜索、网页抓取、来源摘要 |
| `browser-verifier` | execute | 浏览器交互和前端验收 |
| `document-analyst` | readonly | 文档解析和摘要 |
| `project-cartographer` | readonly | 陌生仓库梳理 |
| `bug-reproducer` | execute | 复现问题和定位失败 |
| `implementation-worker` | write-capable | 局部实现，替代宽泛 code-worker 的部分场景 |
| `reviewer` | readonly/execute | 代码审查和发布审查 |

保留现有 profiles，但逐步让新 profiles 承担更具体任务。

### Router 规则

主智能体获得一个轻量 router，不强行替模型决策，但在 system prompt 和工具描述中明确建议：

- 需要网页信息：优先派 `web-researcher`。
- 需要浏览器验收：优先派 `browser-verifier`。
- 需要读大仓库：先派 1-3 个 `project-cartographer` / `explorer` 并行查不同区域。
- 需要改代码：主智能体先生成 todo，必要时派 `implementation-worker` 做局部修改。
- 需要验证：派 `verifier` 或 `bug-reproducer`。
- 用户要求只读：只允许 readonly/execute 且禁止写入。

### 输出协议

子智能体最终输出必须尽量包含：

```json
{
  "result": "直接结论",
  "evidence": ["文件、URL、命令或截图证据"],
  "actionsTaken": ["做过的工具调用或检查"],
  "changedFiles": [],
  "risks": ["剩余风险"],
  "nextActions": ["建议下一步"]
}
```

TUI 可以把该结构压成：

- 子任务状态
- 最近动作
- 结论摘要
- 证据数量
- 风险数量

## TUI 与可观察性升级

### 右侧任务树

新增或增强右侧栏视图：

- `待办`
- `子任务`
- `能力`
- `MCP`
- `技能`
- `上下文`

任务树展示：

- 主任务 todo/plan。
- 子智能体 task。
- 当前运行的 MCP 工具。
- 当前运行的 skill workflow。
- 浏览器验收步骤。

状态标记：

- `○` 待开始
- `●` 进行中
- `✓` 完成
- `!` 失败
- `?` 被阻止/等待审批

### 主聊天区展示策略

避免工具过程再次堆满主对话：

- 成功的 routine tool/MCP/skill 默认折叠。
- 失败、被拒绝、权限等待、中断必须可见。
- `Ctrl+O` 三档继续控制：紧凑、详细、完整。
- 子智能体结果用摘要卡片显示，不把完整子会话塞进主聊天。

### 命令建议

新增或增强：

- `/mcp`
- `/mcp doctor`
- `/mcp enable <name>`
- `/mcp disable <name>`
- `/mcp tools <name>`
- `/skills`
- `/skills doctor`
- `/skills read <name>`
- `/agents`
- `/agents tasks`
- `/agents run <profile> <task>`
- `/agents router`
- `/capabilities`

所有命令必须进入统一 command registry，`/help`、`/keybindings`、slash palette 自动同步。

## 分阶段实施计划

### Stage 1：能力注册表与配置模型

目标：

- 建立统一 capability registry。
- 区分 built-in tools、MCP servers、skills、agents。
- 每个能力有中文说明、风险等级、默认启用状态、依赖检查、验收命令。

改动范围：

- `src/config`
- `src/tools`
- `src/mcp`
- `src/skills`
- `src/agents`
- `docs`

验收：

- `/capabilities` 能列出工具、MCP、skills、agents。
- 禁用的能力显示原因。
- 不配置任何 MCP 时，内置能力仍可用。

### Stage 2：MCP no-key pack 与 doctor

目标：

- 在 `lab-agent.config.json` 增加推荐 no-key MCP；自包含能力默认启用，依赖本地服务或数据源的能力按配置启用。
- 新增 `/mcp doctor`。
- 检查命令是否存在、包能否启动、工具能否列出、权限是否生效。

首批配置：

- `fetch`
- `duckduckgo-search`
- `searxng`
- `playwright`
- `memory`
- `filesystem`
- `sequential-thinking`

验收：

- `/mcp` 能显示所有推荐 MCP 及启用状态。
- `/mcp doctor` 能说明缺少 Node/Python/uv/npx 或包启动失败。
- 启用任意 MCP 后，`mcp_list` 能列出工具。
- `mcp_call` 仍走权限引擎。

### Stage 3：内置 `web_fetch` 和 `web_search`

目标：

- 不依赖 MCP 也能做基础网页抓取和搜索。
- 给模型一个稳定的一等网络工具。

计划：

- `web_fetch`：
  - 支持 URL。
  - 支持 text/markdown/html。
  - 限制大小和超时。
  - 标记来源 URL、状态码、content-type、截断状态。
- `web_search`：
  - 优先 SearXNG 配置。
  - fallback 到 DuckDuckGo HTML 搜索。
  - 输出标题、URL、摘要、来源、时间。

验收：

- 网络开启并批准后可抓取指定 URL。
- 网络关闭或未授权时清楚报错。
- 搜索结果不写死，不伪造来源。
- 失败时不让模型假装查到了。

### Stage 4：浏览器自动化双路线

目标：

- 支持复杂网页交互。
- 同时控制上下文膨胀。

路线：

- 轻量验收优先用 `browser-automation` skill + Playwright CLI。
- 需要模型逐步控制页面时启用 `@playwright/mcp`。

验收：

- 能打开本地页面。
- 能点击、输入、截图。
- 用户可拒绝浏览器 MCP 或网络访问。
- 运行结束后主聊天只保留摘要，截图/步骤进入任务记录。

### Stage 5：文档解析与资料 intake

目标：

- 让 Ant Code 能处理 PDF/Word/PPT/Excel 等资料。

计划：

- 新增 `document-intake` skill。
- 使用 `markitdown` 或本地 Python/Node 适配层。
- 输出 Markdown 摘要、表格预览、图片占位、截断提示。

验收：

- 对小 PDF/docx/xlsx 生成摘要。
- 大文件不会刷爆上下文。
- 不把私有文档原文大段输出到主聊天。

### Stage 6：本地 skill pack 落地

目标：

- 建立实验室常用 skill 基础包。

首批 skills：

- `web-research`
- `browser-automation`
- `document-intake`
- `project-intake`
- `bug-repro`
- `frontend-verifier`
- `release-review`

验收：

- `/skills` 能列出全部 skill。
- `/skills read <name>` 能读到中文用途和触发场景。
- `skill_run` 能把对应工作流注入子任务。
- 每个 skill 有最小 smoke 验收说明。

### Stage 7：Agent profile v2 与 router

目标：

- 子智能体从“可手动调用”升级为“主智能体知道何时调用”。

计划：

- 扩展 profile schema。
- 增加 `triggerHints`、`skills`、`mcpServers`、`outputContract`。
- system prompt 强化调度规则。
- `agent_run` 根据 profile 限制工具、skills、MCP。

验收：

- 用户提出联网任务时，模型倾向调用 `web-researcher` 或相关工具。
- 用户提出前端验收时，模型倾向使用 `browser-verifier`。
- 用户提出大仓库调查时，模型能先派只读子任务。
- 子智能体输出结构稳定。

### Stage 8：并行子任务和任务树

目标：

- 提升长任务效率和可观察性。

计划：

- 允许主智能体在单轮中启动多个只读子任务。
- 任务树展示并行状态。
- 子任务完成后主智能体拿摘要继续工作。
- 支持取消运行中的子任务。

验收：

- 一个复杂问题能并行启动 2 个只读调查任务。
- 右侧栏能看到每个子任务状态。
- 主聊天不会被完整子任务日志刷屏。
- 失败的子任务能显示失败原因。

### Stage 9：安全、权限和审计

目标：

- 网络/浏览器/MCP 能力强起来后，不能牺牲安全边界。

计划：

- 扩展 permission risk：
  - `network`
  - `browser`
  - `document`
  - `mcp`
  - `memory`
- host allowlist。
- MCP env scrub。
- 浏览器 cookie/session 警告。
- 大文件和敏感内容输出限制。

验收：

- 网络请求可按 host 审批。
- 浏览器动作可审批。
- MCP 子进程不继承敏感环境变量，除非显式允许。
- 任何失败/阻止都清楚显示。

### Stage 10：文档、测试与发布验收

目标：

- 把能力变成可维护产品，而不是一次性补丁。

计划：

- 更新 `LLM_ONBOARDING.md`。
- 更新 `PROJECT_CHANGELOG.zh-CN.md`。
- 增加 `/mcp doctor`、`/skills doctor`、agent router 测试。
- 增加 TUI 任务树格式测试。
- 增加至少一份人工验收脚本。

验收：

- `npm run check` 通过。
- 新增能力在未启用外部 MCP 时不会破坏默认启动。
- 启用 no-key MCP 后可完成 smoke 测试。
- 文档说明清楚哪些能力需要网络、浏览器或额外本地包。

## 不在本轮做的事

- 不接入远端 skill marketplace。
- 不默认安装任意第三方 skill。
- 不做 Anthropic 原生协议。
- 不接入需要 API key 的搜索服务作为默认能力。
- 不把旧 Ant Code 的 `.claude` 目录直接搬进当前实现。
- 不把浏览器 cookie、账号态或网页内容自动上传到模型之外的服务。

## 审核关注点

审核时建议重点看：

1. 是否同意首批 no-key MCP 清单。
2. 是否同意 `web_fetch` / `web_search` 做成内置工具，而不是只依赖 MCP。
3. 是否同意 browser MCP 默认启用，但页面导航、点击、输入按任务审批。
4. 是否同意 skill pack 采用 Ant Code 自有目录和格式，不直接沿用 `.claude`。
5. 是否同意 agent router 只做“建议和引导”，不做不可解释的黑盒自动调度。
6. 是否需要把文献检索、生信数据、Excel/PPT 这些实验室工作流放入首批 skill，还是先做通用能力。

## 推荐执行顺序

建议审核通过后按以下节奏推进：

1. Stage 1-2：先把能力注册、MCP doctor、推荐配置打牢。
2. Stage 3-4：补网络抓取、搜索、浏览器。
3. Stage 5-6：补文档解析和本地 skill pack。
4. Stage 7-8：升级子智能体 router、并行任务和右侧任务树。
5. Stage 9-10：做安全审计、全量测试、文档和发布验收。

这样做的好处是：外部能力先能被发现和诊断，再让模型使用，最后再把使用过程纳入子智能体编排和 TUI 可观察性。
