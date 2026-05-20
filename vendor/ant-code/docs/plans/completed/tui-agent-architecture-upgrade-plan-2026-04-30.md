# Ant Code TUI 与智能体调度大改造计划

日期：2026-04-30

## 目标

本计划用于审核下一轮大改动。审核通过前，只保留当前验收通过版本，不改业务实现。

当前验收通过版本已备份到：

`C:\saveproject\ant-code项目备份\lab-agent-重构版-验收通过-源码目录-20260430-154808`

下一轮目标是把当前 `lab-agent` 从“可交付 MVP”升级为更稳定的产品型代码智能体，重点补齐：

1. 稳定 TUI 底层布局和滚动模型。
2. 独立侧栏、独立弹层、独立输入区。
3. 单一命令/快捷键注册源。
4. 可观察、可恢复、可取消的子智能体任务系统。
5. 本地 agent 配置文件化。
6. MCP 持久连接和诊断能力。
7. 本地 skill 体系增强，但不接入远端 skill marketplace。

## 边界

本轮允许大规模重构当前仓库：

`C:\saveproject\LBJ-workspace\lab-agent`

不维护旧归档项目，不把旧项目恢复为工作仓库。

不把任何本地网关 API key、用户密钥、`.env` 内容写入仓库。

不做远端 skill marketplace 或远端 skill 搜索生态。

允许参考 opencode 和旧 Ant Code 的产品思路、交互边界和架构组织，但当前实现以 `lab-agent` 的代码、配置、测试和本地网关协议为准。

## 总体架构改造

### Stage 1：TUI 布局内核重构

目标：彻底减少滚轮、窗口缩放、右侧栏、斜杠面板之间的相互干扰。

计划改动：

- 拆分当前 `src/cli/tui.js` 的主循环，把布局、事件路由、弹层、会话渲染、输入框拆成独立模块。
- 新增 TUI shell：
  - 顶部状态栏。
  - 主聊天滚动区。
  - 右侧 inspector/status/tasks 面板。
  - 底部输入区。
  - overlay 弹层区。
  - footer 提示区。
- 弹层改为覆盖式 overlay，不再挤压主聊天和输入框。
- `/help`、`/resume`、`/sessions`、model picker、slash palette、权限框、问题框统一走 overlay stack。
- 大窗口右侧栏固定在可视区域，不再跟随 transcript 滚动。
- 小窗口保持主聊天优先，右侧信息降级为 compact summary 或 overlay。

验收点：

- 大窗口和小窗口都能滚动查看完整聊天历史。
- 窗口放大缩小时不出现重复界面残影。
- slash palette 不挤压输入框。
- `/resume` 和 `/help` 可在较大空间内展示，不塞进小框。
- 右侧栏在大窗口下固定显示。

### Stage 2：真实滚动区域与鼠标事件路由

目标：把滚动从“全局方向事件”升级为“区域感知滚动”。

计划改动：

- 新增 `ScrollableRegion` 抽象：
  - `scrollBy`
  - `scrollToBottom`
  - `scrollToTop`
  - `isPinnedToBottom`
  - `maxOffset`
  - `visibleRange`
  - `newContentWhileScrolledUp`
- 鼠标 wheel 解析保留坐标，按 x/y 路由到聊天区、右侧栏或当前 overlay。
- 聊天区流式输出时：
  - 如果用户在底部，自动跟随。
  - 如果用户向上看历史，不强制拉回底部。
  - 新内容到达时显示“有新内容，回到底部”的提示。
- 右侧栏有独立滚动 offset。
- overlay 有独立滚动 offset。
- PageUp/PageDown、方向键、滚轮使用同一套滚动 API。
- 重新审视终端 mouse mode 与文本选择冲突：
  - 默认优先保证滚轮和交互。
  - 必要时提供选择文本模式或快捷键切换。

验收点：

- 生成中滚轮不会闪回顶部或底部。
- 鼠标在聊天区滚动只滚聊天。
- 鼠标在右侧栏滚动只滚右侧栏。
- 鼠标在 overlay 上滚动只滚 overlay。
- 用户向上查看历史时，模型继续输出不打断阅读。

### Stage 3：命令、帮助、快捷键单一注册表

目标：避免 `/help`、`/keybindings`、FooterBar、实际行为互相不一致。

计划改动：

- 新增统一 command registry：
  - command id
  - slash 名称
  - 中文标题
  - 中文描述
  - category
  - aliases
  - keybind
  - enabled/disabled reason
  - action handler
  - panel renderer
- `/help` 从 registry 自动生成。
- `/keybindings` 从 registry 和 keybind registry 自动生成。
- FooterBar 只展示真实可用快捷键。
- slash palette 从同一 registry 读取。
- Ctrl+N/P、Ctrl+F/B、Ctrl+T 等低频快捷键保留，但必须在 help 中说明触发条件。
- 可考虑引入 leader key，例如 `Ctrl+X`，减少和输入编辑快捷键冲突。

验收点：

- `/help` 中出现的命令都能解释真实行为。
- `/keybindings` 中出现的快捷键都能实际触发，或明确标注触发条件。
- FooterBar 没有虚假快捷键。
- slash palette 的 Esc 退出提示继续保持高可见性。

### Stage 4：子智能体任务系统

目标：把当前一次性 `agent_run` 升级为可观察、可恢复、可取消的子任务/子会话系统。

计划改动：

- 新增 task/session 数据模型：
  - task id
  - parent session id
  - child session id
  - agent profile
  - prompt
  - status
  - created/started/finished time
  - latest progress
  - tool call summary
  - output summary
  - cancel/resume metadata
- `agent_run` 创建子任务记录。
- 子智能体运行时写入 child transcript。
- TUI 右侧栏新增 Tasks 视图。
- 聊天区中的 agent tool 结果显示：
  - agent 类型
  - 任务描述
  - 当前状态
  - 最近工具执行
  - task id
- 支持 `/agents tasks` 查看任务。
- 支持 `/agents resume <task-id>` 继续或查看子任务。
- 支持取消运行中的本地子任务。
- 允许同步子任务和本地后台子任务。
- 后台子任务默认仍走本进程任务队列，先不依赖 tmux。

验收点：

- 主智能体调用子智能体时，用户能看到它在做什么。
- 子智能体失败时能看到失败原因。
- 子任务完成后能查看结果和关键工具调用。
- 恢复会话后仍能看到历史子任务记录。

### Stage 5：Agent 配置文件化

目标：让实验室可以持续扩展 agent，而不是只改源码内置 profile。

计划改动：

- 支持读取：
  - `.lab-agent/agents/*.md`
  - `.ant-code/agents/*.md`
  - `lab-agent.config.json` 的 `agents.profiles`
- agent markdown frontmatter 支持：
  - `name`
  - `description`
  - `mode`
  - `model`
  - `tools`
  - `disallowedTools`
  - `permissionMode`
  - `maxRounds`
  - `color`
  - `hidden`
  - `skills`
  - `mcpServers`
  - `background`
  - `isolation`
- 内置 agent 调整为：
  - build/default
  - planner
  - explorer
  - verifier
  - code-worker
  - compaction hidden agent
  - title hidden agent
  - summary hidden agent
- `/agents` 展示来源、能力、工具、模型、是否 hidden。
- 主智能体 system prompt 中明确说明可调用 `agent_run` 分派任务。

验收点：

- 新增一个本地 agent markdown 后，`/agents` 能看到。
- 模型能根据任务选择 explorer/planner/verifier/code-worker。
- hidden agent 不出现在普通选择列表，但内部功能能调用。

### Stage 6：上下文压缩、标题、摘要内部 agent 化

目标：把 compact/title/summary 从散落的特殊逻辑升级为统一内部 agent。

计划改动：

- `/compact` 走 hidden compaction agent。
- 会话标题生成走 hidden title agent。
- 长会话摘要走 hidden summary agent。
- compact 仍保留本地 fallback。
- TUI compact 面板显示：
  - 策略：模型压缩或本地 fallback。
  - before tokens。
  - after tokens。
  - summary tokens。
  - fallback reason。
- 达到上下文阈值时自动触发 compact。

验收点：

- 手动 `/compact` 可看到模型压缩状态。
- 网关不可用时降级本地摘要并显示原因。
- 上下文达到阈值后自动压缩。
- resume 后 compacted summary 能继续进入上下文。

### Stage 7：MCP 持久运行时

目标：从临时 stdio 调用升级为可诊断、可缓存、可复用的 MCP 管理器。

计划改动：

- 新增 MCP manager：
  - server status
  - persistent client
  - tool cache
  - reconnect
  - disconnect
  - stderr 摘要
  - timeout
  - tool list changed refresh
- 支持 stdio MCP 作为第一优先级。
- 后续可支持显式配置的 HTTP/SSE MCP，但必须是 lab-approved config，不做自动发现。
- 支持 MCP prompts/resources：
  - `/mcp prompts`
  - `/mcp resources`
  - `/mcp read-resource`
- TUI inspector 显示 MCP 连接状态。
- agent 可声明需要的 MCP server；未配置时该 agent 显示不可用原因。

验收点：

- 没有 MCP 配置时提示清楚。
- 配置一个本地 fake MCP server 后，工具列表可见。
- 调用 MCP 工具经过权限策略。
- MCP server 崩溃后状态显示 failed，并可重连。

### Stage 8：Skill 体系增强

目标：保留安全边界，同时让 skill 真正帮助模型工作。

计划改动：

- 保留本地 skill，不接入远端 skill marketplace。
- 支持 skill frontmatter：
  - `name`
  - `description`
  - `when_to_use`
  - `allowed-tools`
  - `argument-hint`
  - `model`
  - `context: fork`
  - `agent`
  - `paths`
  - `hooks`
- `/skills` 展示 skill 来源、适用场景、允许工具。
- `skill_read` 继续提供 bounded instruction。
- `skill_run` 默认仍是 instruction-only。
- 对 `context: fork` 的 skill，允许通过子智能体执行，但必须走普通工具和权限策略。
- 不自动执行 skill 目录里的脚本。

验收点：

- 本地新增 skill 后 `/skills` 能看到。
- 模型能读取 skill 指令后应用到任务。
- fork skill 会产生可查看的子任务记录。
- skill 声明的工具边界能生效。

### Stage 9：工作区隔离与后台任务

目标：支持更强的任务并行和风险隔离，但保持默认简单。

计划改动：

- 本地后台 agent：
  - 独立 AbortController。
  - 独立 child transcript。
  - 独立任务状态。
  - 输出文件或任务记录持久化。
- worktree isolation：
  - 仅在 git 仓库内启用。
  - 用户或 agent 明确请求时创建临时 worktree。
  - 任务完成后显示改动位置和清理建议。
- 不默认启用远端执行。
- 远端 agent 只预留接口，除非实验室后续提供明确 remote runner 配置。

验收点：

- 后台任务运行时主会话仍可继续输入。
- 用户能查看后台任务完成状态。
- worktree 任务不会直接污染主工作区。
- 取消后台任务能停止后续模型/工具轮次。

### Stage 10：TUI 技术底座评估

目标：判断是否从 Ink 迁移到 OpenTUI。

计划改动：

- 做一个小型 OpenTUI proof-of-concept：
  - transcript scrollbox
  - fixed sidebar
  - prompt
  - overlay
  - mouse wheel
  - Windows PowerShell 运行
- 如果 OpenTUI 在当前 Node/npm/Windows 环境稳定，则迁移主 TUI。
- 如果依赖、构建或 Windows 兼容风险过高，则保留 Ink，但使用 Stage 1/2 的 ScrollableRegion 架构。
- 不在没有 POC 证据时直接替换整个 TUI。

验收点：

- 有明确 POC 结论。
- 若迁移，必须保留 `node .\src\cli\index.js tui` 启动方式。
- 若不迁移，当前 Ink TUI 也必须完成滚动和 overlay 重构。

### Stage 11：测试、验收、文档

计划改动：

- 新增或更新单元测试：
  - scroll math
  - mouse coordinate routing
  - overlay stack
  - command registry
  - keybindings
  - agent config parser
  - task store
  - MCP manager fake server
  - skill parser
  - compact hidden agent fallback
- 新增集成测试：
  - mock gateway 流式输出。
  - agent_run 子任务。
  - compact 模型摘要。
  - resume 恢复子任务和 compact summary。
- 手工验收清单：
  - 大窗口滚轮。
  - 小窗口滚轮。
  - 生成中滚轮。
  - 斜杠命令 overlay。
  - help/resume/sessions。
  - 权限确认框。
  - guide。
  - ESC 两次中断。
  - MCP 无配置和 fake 配置。
  - skill。
  - 后台 agent。
- 最终运行：
  - `npm run check`
  - `node .\src\cli\index.js tui`
- 更新文档：
  - README
  - deployment docs
  - provenance docs
  - acceptance docs
  - handoff docs

## 执行顺序

建议审核通过后按以下顺序一次性推进，但每个阶段完成后本地验证再进入下一阶段：

1. Stage 1 + Stage 2：先解决 TUI 底层。
2. Stage 3：统一命令和快捷键。
3. Stage 4 + Stage 5：升级子智能体和 agent 配置。
4. Stage 6：统一 compact/title/summary。
5. Stage 7 + Stage 8：MCP 和 skill 增强。
6. Stage 9：后台任务和 worktree 隔离。
7. Stage 10：OpenTUI POC 和是否迁移决策。
8. Stage 11：完整验证和文档刷新。

## 风险与回滚

- 当前验收版本已经备份，若大改失败，可从备份目录恢复。
- TUI 底层是最高风险区，必须先建立滚动/overlay 测试再大改。
- OpenTUI 迁移必须有 POC 证据，不应盲迁。
- 后台任务和 worktree 隔离可能引入状态复杂度，默认开关应保守。
- MCP 远端能力必须只由显式配置启用，不做自动发现。
- Skill 脚本不自动执行，避免权限边界失控。

## 本轮不做

- 不接入远端 skill marketplace。
- 不做自动下载第三方 skill。
- 不写入本地网关 API key。
- 不维护旧归档项目。

## 执行状态更新：2026-04-30

Stage 1-5 已在前序轮次完成并通过用户验收。本次继续完成 Stage 6-11：

| Stage | 状态 | 完成内容 |
| --- | --- | --- |
| Stage 6：上下文压缩、标题、摘要内部 agent 化 | 已完成 | `/compact` 优先通过 hidden `compaction` internal agent 调用模型摘要，保留本地 fallback，并在 session metadata 中记录策略、token 计数和 fallback 原因。 |
| Stage 7：MCP 持久运行时 | 已完成 | stdio MCP runtime 支持持久连接、工具缓存、status、tools、prompts、resources、read-resource、reconnect、disconnect、stderr 摘要、disabled server 状态和 Windows `npx` 启动归一化。 |
| Stage 8：Skill 体系增强 | 已完成 | skill frontmatter 扩展到 `argument-hint`、`context`、`agent`、`paths`、`hooks`；`context: fork` 通过 hidden skill subagent 执行；默认 skills 保持本地 instruction-only。 |
| Stage 9：工作区隔离与后台任务 | 已完成 | `/background` 支持 run/list/show/cancel/worktree/cleanup-worktree；后台任务使用独立 AbortController 和 child transcript；显式 worktree 创建在 `.lab-agent/worktrees/` 下。 |
| Stage 10：TUI 技术底座评估 | 已完成 | 记录 OpenTUI POC 结论：当前版本不迁移，保留 Ink + ScrollableRegion 架构，避免 deadline build 引入未审阅 native 依赖风险。 |
| Stage 11：测试、验收、文档 | 已完成 | 新增/更新 Stage 6-11 相关单元测试、配置模板、provenance、OpenTUI 评估和 v1.3 验收文档；`npm run check` 已在 2026-04-30 通过，260 个测试全绿。 |

新增交付文档：

- `docs/architecture/opentui-poc-2026-04-30.md`
- `docs/deployment/v1.3-agent-extension-acceptance.md`

推荐 MCP/skill 配置状态：

- `lab-agent.config.json` 和 `config/lab-agent.lab-template.json` 内置 `filesystem`、`memory`、`playwright` 三个常用 MCP 示例，但全部 `enabled: false`，需要实验室显式启用。
- `config/lab-agent.high-sensitivity-template.json` 保持 MCP 空列表，避免敏感项目误触 `npx` 包执行。
- `config/skills` 保留三个本地 lab-owned skills：`codebase-orientation`、`test-failure-triage`、`release-readiness-review`。

剩余手工验收建议：

- 启动 `node .\src\cli\index.js tui`，检查 `/mcp` 在推荐 MCP 分级默认配置下的说明是否清楚。
- 如实验室允许临时拉包，可手动启用一个本地 MCP server 后检查 `/mcp status`、`/mcp tools` 和权限确认。
- 用 `/skills`、`/skills show test-failure-triage`、`/skills run test-failure-triage <失败摘要>` 检查 fork skill 子任务记录。
