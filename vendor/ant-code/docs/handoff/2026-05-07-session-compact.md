# 2026-05-07 Ant Code 长会话 Compact 交接

本文件用于在新 Codex 会话中快速接手当前 Ant Code / lab-agent 状态。不要包含 API key、真实用户业务会话原文或私有凭据。

## 基本位置

- 主仓库：`C:\saveproject\LBJ-workspace\lab-agent`
- 常用测试项目：`E:\test-project\LBJ-workspace\new-ptoject`
- 用户技能目录：`C:\saveproject\LBJ-workspace\skill`
- 用户正式备份目录：`C:\saveproject\ant-code项目备份`
- 当前公开命令名：`ant-code`
- 内部包/目录名仍大量保留 `lab-agent`，这不是本轮任务重点。

## 用户偏好

- 默认中文沟通，汇报要短而具体。
- 用户喜欢右侧栏简洁：状态、任务、子智能体这类高频信息可以留，日志/历史/命令类不应长期占右栏。
- 用户喜欢摘录层用于鼠标选择局部复制，首层聊天区不要因为单击就长期保持选中状态。
- 用户在专用测试机上愿意使用完全访问权限；过度保守的权限策略会严重影响体验。
- 大改前要留计划文档，完成后要日志留存；重要稳定点要本地 git 保存。
- 最近踩过 TUI 输入链路大雷，后续 TUI 改动必须保守、可验证、避免新增键位兜底污染正常交互。
- 用户经常用微信语音转文字输入长句，输入栏需要能承受快速分块文本提交。

## 当前重要决策

### 1. `/sessions` 与 `/resume`

最新决策已经落地：

- `/sessions`：负责历史会话选择、恢复、切换和清理。
- `/resume`：只负责当前会话历史分片回看。
- `/resume <序号>`：打开当前会话某个 50 条 transcript 分片。
- `/resume` 不恢复会话，不把旧分片塞回聊天区，不写入 `session.messages`，不增加模型上下文。
- CLI 启动参数 `ant-code --resume latest` 仍保留，属于启动恢复能力，不等同 TUI 内 `/resume latest`。

相关文件：

- `src/cli/tui.js`
- `src/cli/tui/command-panels.js`
- `src/storage/session-store.js`
- `src/commands/registry.js`
- `README.md`
- `docs/specs/mvp-product-spec.md`
- `PROJECT_CHANGELOG.zh-CN.md`

### 2. 长会话内存治理

用户遇到 Node/V8 OOM，堆上限约 4GB。判断核心压力来自 TUI/会话状态长期保留过多可见 transcript、工具结果、子智能体记录和渲染数据，而不是机器物理内存不足。

注意：这不是第一次 OOM 治理。`PROJECT_CHANGELOG.zh-CN.md` 里已有两条相关历史：

- 2026-05-07 “增加 TUI 空闲静默看门狗”：针对 Ant Code TUI 挂机一晚后 Node/V8 heap out of memory，先做保守优化；30 分钟空闲静默待机，暂停心跳刷新和无任务轮询，不清理聊天记录、不改 transcript 保留策略。
- 2026-05-06 “修复超长任务后聊天历史被运行日志/压缩挤掉”：把本地 transcript 与模型上下文分离，恢复时优先展示 `session.transcriptMessages`，避免长任务和上下文压缩让聊天历史不可回看。当前 50 条窗口和 chunk 落盘是在这条基础上的进一步内存收口。

当前已实现方向：

- `session.transcriptMessages` 只保留最新 50 条可见 transcript。
- 旧可见 transcript 按 50 条一个 chunk 落盘到 `.lab-agent/sessions/<session-id>.transcript/chunk-*.json`。
- persisted transcript chunk 不保存 thinking 和 toolCalls。
- `/resume` 只读某一个 chunk 进入命令面板。
- 模型上下文 `session.messages` 不等于 TUI 可见窗口，仍由上下文压缩/摘要逻辑处理。

后续更稳的方向：

- 给 TUI 可见 transcript 再加字节上限，而不只是条数上限。
- 对单条超大消息做侧车化或摘要化，防止 28 条消息但单条极大仍撑爆。

### 3. Thinking / reasoning 显示

当前文案已经收口：

- `/thinking` 只展开当前会话可见窗口内的 thinking/reasoning。
- 新的 persisted transcript chunk 不保存 thinking。
- 旧说法“可在 /resume 后恢复 thinking”已经从当前代码和文档中移除。

相关文件：

- `src/cli/tui.js`
- `src/cli/tui/format.js`
- `src/cli/tui/command-panels.js`
- `tests/unit/tui-format.test.js`

### 4. 子智能体与长任务

近期已做的关键改动：

- 主智能体提示词和子智能体 profiles 已强化复杂任务编排。
- 默认取消子智能体 model-tool round 硬上限，避免长任务跑到 64 轮直接暂停。
- 子智能体预算保护阀改为软着陆：命中输出、轮次、失败、权限拒绝等预算后，优先要求子智能体基于已有信息生成阶段汇报，而不是机械中断。
- 子智能体长输出写入 sidecar，任务 JSON 只保存摘要/预览。
- 子智能体后台任务组支持自动唤醒主控汇总。
- TUI 聊天区对子智能体任务有提示，双击可进入详情/摘录层；运行态详情可刷新，冻结后适合复制。
- 当前 DeepSeek 配置中，父模型用 pro，子智能体模型层倾向 flash。

相关文件常见入口：

- `src/agents/runner.js`
- `src/agents/profiles.js`
- `src/agents/budget.js`
- `src/agents/task-store.js`
- `src/agents/task-group-store.js`
- `src/tools/runtime.js`
- `src/cli/tui.js`
- `src/cli/tui/command-panels.js`

### 5. 权限模式

用户最终希望只保留三档：

- plan：所有写入/命令等需要确认，风险最低，绿色显示。
- workspace：工作区内常规操作自动同意，工作区外和敏感路径仍询问，黄色显示。
- fullAccess：专用测试机使用，所有命令和路径默认自动同意。

已排查并修复过多处 fullAccess 链路遗漏，包括 `agent_run` 被 `execute` 风险误送入空 command 分类导致拒绝的问题。后续如遇 `path outside workspace`，要检查整个 permission policy 链，而不是只看顶层开关。

### 6. DeepSeek 与网关

用户明确要求 DeepSeek 作为 Ant Code 后续模型路径，不要切回小米 Mimo。不要在文档或回复中打印 key。

目标配置：

- `gatewayUrl`: `https://api.deepseek.com/chat/completions`
- `gatewayProtocol`: `openai-chat`
- 主模型：`deepseek-v4-pro`
- 子智能体/cheap/default 可优先 `deepseek-v4-flash`
- DeepSeek 上下文目标：模型窗口 1,000,000 tokens，自动压缩阈值 500,000 tokens。

已处理过的问题：

- OpenAI-compatible reasoning_content 兼容问题。
- 网关 retry 和异常记录增强。
- 中断时保留 assistant draft 的方向曾经因回滚丢失，后续已重新移植。

仍要注意：

- 用户 key 可能在项目级 `.lab-agent/config.json` 或环境变量中，不要明文输出。
- 如果 TUI 快捷键/鼠标突然失效，不要先怀疑模型 key，优先查 raw input、terminal mouse tracking、overlay focus、hit testing。

### 7. Web fetch / MCP

当前理解：

- `web_fetch` 入口优先可走 MCP fetch 后端，内置 fetch 脚本作为 fallback 或早期遗留能力。
- MCP fetch 不需要 GitHub key，不收费，本地 stdio 启动。
- 之前很多 `web_fetch blocked` 是网络权限策略过保守或 host 未批准，不一定是网络代理问题。
- GitHub 专用 MCP 可选，但需要 GitHub token；用户曾拿到 token，但不要记录或打印。

### 8. Hooks

已落地本地核心 hooks，定位是记录、规范化运行习惯、轻量安全审计，不应牺牲智能体性能。

重要原则：

- 敏感操作更多走强确认和审计，不应硬阻断用户合理任务。
- 后台 command hook 要避免拖住进程退出。
- `/hooks` 应能看到 scheduled/running/completed 这类运行状态。
- hook 命名要准确，避免 `deny-sensitive-files` 这种已经不再硬拒绝的误导命名。

### 9. TUI 输入与选择

已做过的稳定化：

- 输入栏支持多行，最多显示 5 行，方向键在输入内容内移动光标。
- 同步 draft mirror 修复微信语音转文字/输入法快速分块提交时前半段被覆盖的问题。
- 摘录层 borderless，方便鼠标局部选择复制，不混入右侧边框。
- 表格在聊天区和摘录层已有渲染，摘录层可以渲染完整表格并 wrap 超宽单元格。
- 当前不建议轻易改 raw input fallback、鼠标点击解析、Shift+Tab 权限切换链路。

### 10. 项目记忆

已落地 `ANTCODE.md` 项目规则记忆入口，并保留 `.lab-agent/memory.md`。

当前原则：

- 用户明确表达“以后我习惯这样做”或“以后按这种方式工作”时，智能体可以主动写入记忆，不必只等 `/memory add`。
- 提示词不要过度保守，测试阶段允许更积极记录用户工作习惯。
- `ANTCODE.md` 是项目级、人类可见维护习惯；`.lab-agent/memory.md` 是 Ant Code 自己的项目记忆。

## 当前工作区状态

最近一次本地 git 提交：

- `d88d67b 保存：子智能体软着陆与 TUI 记忆输入稳定版`

当前工作区仍有未提交改动，主要包含：

- session transcript 50 条内存窗口与 chunk 落盘。
- `/resume` 当前会话分片查看器。
- `/sessions` 与 `/resume` 文档和命令文案收口。
- thinking 文案与测试同步。
- `src/ui/output.js` 是此前已有的无关改动，本轮没有触碰，不要误回滚。

当前 `git status --short` 里应看到这些文件被修改：

- `PROJECT_CHANGELOG.zh-CN.md`
- `README.md`
- `docs/specs/mvp-product-spec.md`
- `src/cli/tui.js`
- `src/cli/tui/command-panels.js`
- `src/cli/tui/format.js`
- `src/commands/registry.js`
- `src/core/session.js`
- `src/storage/session-store.js`
- `src/ui/output.js`（已有无关改动）
- `tests/unit/session.test.js`
- `tests/unit/storage.test.js`
- `tests/unit/tui-command-panels.test.js`
- `tests/unit/tui-format.test.js`

## 最近验证结果

最近已通过：

```powershell
node --test tests\unit\storage.test.js tests\unit\tui-command-panels.test.js tests\unit\tui-format.test.js
npm run check
git diff --check
```

全量 `npm run check` 结果：

- syntax / forbidden endpoint / provenance / dependency policy 均通过。
- `npm test`：532 pass / 0 fail。

注意：全量检查是在 README/spec/changelog 文档收口前跑过一次；文档收口后又跑了相关单测和 `git diff --check`。如准备提交，建议再跑一次 `npm run check`。

## 新会话接手建议

1. 先运行：

```powershell
cd C:\saveproject\LBJ-workspace\lab-agent
git status --short
```

2. 不要回滚 `src/ui/output.js`，它是已有无关改动。

3. 如用户要求保存当前稳定点，建议先复跑：

```powershell
npm run check
git diff --check
```

4. 如验证 TUI 新分工：

- 启动 `ant-code`。
- 输入 `/sessions`，应看到历史会话选择器。
- 输入 `/resume`，应看到当前会话分片列表。
- 用 `Up/Down` 选择分片，`Enter` 打开。
- 输入 `/resume 1`，应直接打开第 1 个分片。
- 打开的分片只在命令面板中显示，不改变聊天区和模型上下文。

5. 如用户继续讨论 OOM，优先方向不是降低 50 条窗口，而是增加 TUI 可见窗口字节上限和单条超大消息侧车化。
