# Delegation Guard 与主控派发强化计划

状态：已完成，等待用户验收  
创建日期：2026-05-04  
适用仓库：`C:\saveproject\LBJ-workspace\lab-agent`  
回档点：`d7762ea checkpoint: before delegation guard orchestration upgrade`

## 一句话目标

让 Ant Code 主智能体在联网研究、大范围代码排查和复杂长任务中更稳定地派发子智能体，把主控模型从“亲自搜、亲自抓、亲自扫全仓”的高成本路径拉回到“调度、汇总、决策”的角色。

## 当前基线

当前主提示词已经包含 delegation-first 规则：

- 仓库调查优先 `explorer`。
- 联网信息优先 `web-researcher`。
- 长任务优先并行派发 2-3 个只读子任务。
- 主控负责汇总子结果、维护 todo/plan、最终决策。

但这些主要仍是软提示。实测中，部分模型会直接调用 `web_search`、`web_fetch`、`read_file`、`grep` 或 shell 搜索命令，绕过子智能体。这样会带来三个问题：

- 主控上下文被大量原始证据占用，影响后续决策。
- 轻量调研没有路由到低成本模型，增加成本。
- 子智能体面板和任务记录空置，用户难以判断系统是否在按预期协作。

## 参考结论

本轮参考 oh-my-openagent 的本地实现后，结论是它采用混合策略：

- 子智能体派发：强 prompt + 工具执行后提醒注入，不是立即硬阻断。
- 模型/角色路由：运行时 hook 可直接改 agent。
- 特定角色权限：planning agent 等有硬边界。
- 长任务闭环：通过 loop 和 verification prompt 持续推进。

本轮 Ant Code 不照搬命名和实现，只吸收机制：**先增强 prompt，再增加运行时 delegation guard，在不阻断正常操作的前提下把提醒写回模型可见的工具结果。**

## 本轮做什么

1. 强化主控提示词，使派发触发条件更明确。
2. 增加内置 delegation guard，统计主控直接使用广域工具的行为。
3. 当主控连续执行广域搜索/抓取/读取但未调用 `agent_run` 时，把系统提醒追加到工具结果中。
4. 让 guard 区分“精确读一个文件/URL”和“大范围排查”。
5. 为 guard 增加配置项、测试和日志记录。
6. 在 `/logs` 或 hook audit 中保留 guard 触发记录，方便验收。

## 本轮不做什么

- 不硬性禁止主控直接读文件。
- 不取消主控的 `web_search`、`web_fetch`、`read_file`、`grep` 工具。
- 不把所有任务都强制派发给子智能体。
- 不引入外部 OMO 依赖。
- 不调整权限模式语义。
- 不改变子智能体预算和权限链路，除非测试发现 guard 必须读取这些状态。

## 设计原则

- 主控仍可处理小任务：直接回答、单文件定位、用户给定精确路径/URL 时不强迫派发。
- 广域探索优先子智能体：全仓扫描、多文件排查、联网调研、GitHub/文档资料收集触发提醒。
- 先提醒，不阻断：默认只注入系统提醒，避免长任务被 guard 卡死。
- 提醒要进入模型上下文：普通 hook audit 不够，必须追加到工具返回结果，让模型下一步能看到。
- 记录但不刷屏：TUI 用户只需要看到简短状态，详细原因放 `/logs`。

## 触发识别

### 联网研究触发

计入广域联网行为：

- `web_search`。
- 连续多个 `web_fetch`。
- `web_fetch` 目标是 GitHub、Raw GitHub、文档站、论文站、包管理站等外部资料。
- shell 命令中出现 `curl`、`Invoke-WebRequest`、`wget` 抓取外部 URL。

允许主控直接执行的轻量行为：

- 用户明确给出单个 URL，主控直接 `web_fetch` 一次。
- 子智能体已经返回 URL，主控补抓 1-2 个精确来源做最终核对。

### 仓库探索触发

计入广域仓库行为：

- `list_files` 目标为 `.`, 仓库根, `src`, `app`, `packages`, `lib` 等大目录。
- `glob` pattern 包含 `**/*`, `**/*.ts`, `**/*.tsx`, `**/*.js`, `**/*.py` 等广域模式。
- `grep` 在大目录中搜索，或连续多次 grep 不同关键词。
- `read_file` 连续读取多个不同文件，或累计读取字节超过阈值。
- shell 命令中出现 `rg`, `grep -R`, `git grep`, `Get-ChildItem -Recurse`, `dir /s` 等全局扫描。

允许主控直接执行的轻量行为：

- 用户明确给出单个文件路径。
- 子智能体已经定位文件后，主控读取少量片段复核。
- 小型 bug 修复只涉及 1-2 个已知文件。

### 复杂任务触发

用户 prompt 含有以下信号时，guard 阈值降低：

- 中文：全面、整个项目、全仓、排查、审计、重构、对比、架构、安全、性能、长任务、所有文件。
- 英文：full, entire, audit, refactor, architecture, security, performance, investigate, all files, codebase。
- 已创建 4 个以上 todo，或任务运行中持续产生多轮工具调用。

## 提醒策略

默认阈值：

- 第 3 次广域行为且本 turn 尚未调用 `agent_run`：注入一次普通提醒。
- 第 5 次广域行为且仍未调用 `agent_run`：注入一次强提醒。
- 调用 `agent_run` 后，本 turn guard 状态重置为 satisfied。

普通提醒示例：

```text
[Ant Code delegation guard]
你已经连续执行多次广域搜索/读取，但本轮尚未调用 agent_run。
请把后续大范围探索交给 explorer、web-researcher 或 planner 子智能体；主控只保留少量精确复核和最终汇总。
```

强提醒示例：

```text
[Ant Code delegation guard - strong]
本轮广域工具调用已超过建议阈值，继续由主控直接搜/读会消耗主上下文。
下一步请优先调用 agent_run，并将任务拆成 bounded slices：profile、scope、expected output、acceptance。
```

## 实施清单

### Stage 1：强化主控提示词（已完成）

文件：

- `src/context/builder.js`
- `src/agents/profiles.js`

内容：

- 将 delegation-first 从建议性语言改成触发条件表。
- 明确主控直接读/搜的例外场景。
- 加入“收到 delegation guard 提醒后，下一步优先派发 agent_run”的规则。

验收：

- `/status` 或实际会话 system prompt 中能看到明确触发条件。
- 测试 prompt 提到全仓排查或联网调研时，模型更倾向先派发子智能体。

### Stage 2：新增 guard 状态模块（已完成）

文件：

- `src/agents/delegation-guard.js` 或 `src/core/delegation-guard.js`

内容：

- 按 session/turn 维护 guard 状态。
- 记录广域行为计数、网络行为计数、仓库行为计数、直接读取字节估算、已调用子智能体标记。
- 提供 `observeToolStart`、`observeToolFinish`、`buildReminder`、`resetTurn` 等小接口。

验收：

- 单元测试能覆盖计数、重置和 agent_run satisfied 状态。
- 不污染不同 session。

### Stage 3：接入工具执行链路（已完成）

文件：

- `src/core/session.js`
- `src/tools/runtime.js`

内容：

- 在主控 turn 的工具执行过程中观察工具调用。
- `agent_run` 调用后标记当前 turn 已委派。
- 对主控工具结果追加 guard reminder。
- 子智能体内部工具调用不触发父级 guard，避免子智能体被误提醒。

验收：

- 主控连续 `web_search/web_fetch` 可触发提醒。
- 主控连续 `grep/read_file` 可触发提醒。
- 子智能体内部执行 `grep/read_file` 不触发父级提醒。

### Stage 4：实现广域识别规则（已完成）

文件：

- `src/agents/delegation-guard.js`
- `tests/unit/delegation-guard.test.js`

内容：

- 识别大目录、广域 glob、全局 grep、shell 搜索命令。
- 识别精确路径/URL 例外。
- 识别复杂 prompt 降低阈值。

验收：

- `read_file src/foo.ts` 不触发。
- 连续读取多个不同文件触发。
- `glob **/*.ts` 触发。
- 用户给单个 URL 的一次 `web_fetch` 不触发。
- `web_search` 后多次 `web_fetch` 触发。

### Stage 5：配置与开关（已完成）

文件：

- `src/config/load-config.js`
- `lab-agent.config.json`
- `config/lab-agent.lab-template.json`

建议配置：

```json
{
  "agents": {
    "delegationGuard": {
      "enabled": true,
      "mode": "remind",
      "softThreshold": 3,
      "strongThreshold": 5
    }
  }
}
```

验收：

- 配置缺省时启用提醒模式。
- `enabled=false` 时完全不触发。
- 非法配置能被 config test 捕获。

### Stage 6：日志与 TUI 可观察性（已完成）

文件：

- `src/hooks/builtins.js` 或现有 logs/audit 相关模块
- `src/cli/tui.js`
- `src/cli/tui/components.js`

内容：

- guard 触发时写入运行日志，记录 tool、reason、count、threshold。
- 聊天框只显示模型收到的简短提醒；右侧栏不新增永久栏目。
- `/logs` 可查 guard 触发历史。

验收：

- `/logs` 能看到 delegation guard 记录。
- 提醒不刷屏，同一阈值每 turn 只出现一次。

### Stage 7：测试与回归（已完成）

文件：

- `tests/unit/delegation-guard.test.js`
- `tests/unit/session.test.js`
- `tests/unit/tools.test.js`
- 相关 TUI 格式测试如有必要再补

验收：

- `npm run check` 通过。
- 主控工具上限仍为无限或当前配置值，不因 guard 回退。
- `agent_run` 并行只读批处理不受影响。
- 权限模式 plan/workspace/fullAccess 不受影响。

### Stage 8：文档和日志更新（已完成）

文件：

- `PROJECT_CHANGELOG.zh-CN.md`
- `LLM_ONBOARDING.md`
- 本计划文档

内容：

- 记录新增 delegation guard。
- 更新开发坑点：主控派发不能只靠 prompt，运行时提醒必须写入模型可见工具结果。
- 完成后将计划移入 `docs/plans/completed/` 并更新 `docs/plans/README.md`。

验收：

- 用户能通过文档理解 guard 的目标、边界和关闭方法。

## 执行结果

完成日期：2026-05-04

- 已强化主控 system prompt 和 build profile prompt。
- 已新增 `src/agents/delegation-guard.js`。
- 已接入父会话工具执行链路，提醒会写回模型可见工具结果。
- 已新增 `delegation.guard` hook audit 事件，`/logs` 可查。
- 已新增配置项 `agents.delegationGuard`，默认启用提醒模式。
- 已新增 `tests/unit/delegation-guard.test.js`，并补充 config/session 回归测试。

定向验证：

```powershell
node --test tests/unit/delegation-guard.test.js tests/unit/config.test.js tests/unit/session.test.js
```

结果：47 项通过，0 失败。

## 风险与回滚

风险：

- 提醒过于频繁，影响模型正常执行。
- 识别广域行为时误判精确读取。
- 模型看到提醒后过度派发，导致小任务变慢。

缓解：

- 默认只提醒不阻断。
- 每 turn 每个阈值只提醒一次。
- 保留 `enabled=false` 配置。
- 精确文件和单 URL 有白名单路径。

回滚：

- 使用本计划创建后的 git checkpoint 回退。
- 或关闭 `agents.delegationGuard.enabled=false`。

## 手工验收提示词

### 联网研究

```text
请调研 GitHub 上一个开源项目的实现思路，找它的主要目录结构、依赖、核心算法和可借鉴点。你需要引用来源，尽量节省主会话上下文。
```

预期：

- 主控应优先调用 `web-researcher`。
- 如果主控直接 `web_search/web_fetch` 多次，工具结果中出现 delegation guard 提醒。

### 全仓排查

```text
请只读模式全面排查当前项目的权限链路，找出所有可能导致 fullAccess 被误拦截的路径，给出文件位置和风险排序。
```

预期：

- 主控应优先调用 `explorer` 或 `planner`。
- 如果主控直接 `grep/read_file` 多次，工具结果中出现 delegation guard 提醒。

### 小任务不误伤

```text
请读取 src/cli/index.js，告诉我 ant-code 默认入口做了什么。只读，不要修改。
```

预期：

- 主控可以直接读取单个文件。
- 不应出现 delegation guard 提醒。
