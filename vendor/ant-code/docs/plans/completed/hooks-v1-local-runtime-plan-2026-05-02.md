# Ant Code Hooks v1 本地运行时计划

日期：2026-05-02

状态：已完成。Stage 1-8 已在 2026-05-02 落地，详见 `PROJECT_CHANGELOG.zh-CN.md` 同日记录。

适用仓库：

`C:\saveproject\LBJ-workspace\lab-agent`

## 一句话目标

为 Ant Code 增加一层本地、受控、可审计的 Hooks 运行时，把“记录、安全兜底、自动验证、子任务生命周期同步、上下文压缩审计”等重复性工作从模型自觉变成系统流程。

## 背景

当前 Ant Code 已具备：

- TUI、会话恢复、上下文压缩、`/logs`、`/status`、`/doctor`。
- 工具运行时：读写文件、grep/glob、git、shell、MCP、skill、agent、todo/plan、ask_user。
- 权限系统：读写、命令、网络、浏览器、MCP、memory 等风险类别。
- 子智能体：profile v2、router、任务树、后台任务、子任务状态面板。
- skill 和 MCP：本地 skill registry、推荐 MCP、外部专业 skill 路径。

当前短板：

- 没有统一 hook bus，工具、子智能体、compact、todo、文件改动等事件无法被统一审计和编排。
- 自动验证仍主要依赖模型记忆或用户手工要求。
- 权限拒绝、危险路径、敏感文件、子任务失败等运行时事件缺少统一的可查询记录。
- skill frontmatter 已预留 `hooks` 字段，但当前没有实际运行时承接。

## 参考结论

### 源码版 Ant Code 可借鉴点

源码版文档和可观察结构显示，它的 hooks 更接近 Claude Code 风格：

- 事件覆盖广：`PreToolUse`、`PostToolUse`、`PermissionDenied`、`UserPromptSubmit`、`SessionStart`、`SessionEnd`、`SubagentStart`、`SubagentStop`、`PreCompact`、`PostCompact`、`TaskCreated`、`TaskCompleted`、`FileChanged`。
- 配置和策略分离：settings 中定义 hooks，policy settings 可控制只允许 managed hooks。
- 安全开关明确：`disableAllHooks`、`allowManagedHooksOnly`、`allowedHttpHookUrls`、`httpHookAllowedEnvVars`。
- hook 输出可以作为附加上下文、阻断错误或审计消息进入运行时。

适合吸收：

- 事件覆盖面。
- blocking / non-blocking 区分。
- hooks 总开关和 managed-only 思路。
- 超时、输出限制、日志和失败降级。

不直接吸收：

- Claude 生态路径、远端 marketplace、远程 managed settings。
- HTTP hooks 第一版不做。
- 旧源码实现细节不复制。

### opencode 可借鉴点

opencode 的 hooks 主要通过插件系统提供，事件命名更贴近产品行为：

- `tool.execute.before`
- `tool.execute.after`
- `file.edited`
- `permission.asked`
- `permission.replied`
- `session.compacted`
- `session.idle`
- `todo.updated`
- `tui.toast.show`
- `shell.env`

适合吸收：

- 更直观的事件命名。
- todo、文件编辑、权限请求、TUI 提示等产品化事件。
- 插件化的长远方向。

不直接吸收：

- 第一版不做插件市场。
- 第一版不做远程安装和自动下载。
- 第一版不把 hooks 设计成新的复杂生态入口。

## v1 范围

第一版只做“本地核心 hooks”。

做：

- 本地事件总线。
- 配置解析和 hook 匹配。
- 内置 builtin hooks。
- 本地 command hooks。
- 工具、权限、文件、todo、subagent、compact、session 事件接入。
- `/hooks` 状态面板。
- `/logs` 联动记录。
- 单测和文档。

不做：

- HTTP hooks。
- 远端 marketplace。
- npm 插件 hooks。
- 自动下载 hook 包。
- 跨机器同步 hooks。
- 复杂 GUI hook 编辑器。

## 事件模型

v1 事件名采用 Ant Code 自己的简洁命名：

```text
session.start
session.end
user.prompt

tool.before
tool.after
tool.failed
permission.denied

file.changed
todo.updated

subagent.started
subagent.completed
subagent.failed
subagent.paused

compact.before
compact.after
```

事件 payload 必须满足：

- 不包含完整密钥、`.env` 原文或未脱敏命令环境。
- 大文本字段截断。
- 文件路径保留绝对路径或相对 cwd 的可读路径。
- 工具输入只保留摘要和必要字段。
- 工具输出默认只保留摘要、字节数、状态码。

## 配置草案

配置放入 `lab-agent.config.json`：

```json
{
  "hooks": {
    "enabled": true,
    "disableAll": false,
    "managedOnly": false,
    "defaultTimeoutMs": 30000,
    "maxOutputBytes": 12000,
    "envAllowlist": ["PATH", "SystemRoot", "TEMP", "TMP"],
    "events": {
      "tool.before": [
        {
          "name": "record-sensitive-files",
          "type": "builtin",
          "builtin": "recordSensitiveFiles",
          "blocking": false
        }
      ],
      "file.changed": [
        {
          "name": "npm-check-after-js-edit",
          "type": "command",
          "command": "npm run check",
          "when": {
            "paths": ["src/**/*.js", "tests/**/*.js"]
          },
          "blocking": false,
          "timeoutMs": 120000
        }
      ]
    }
  }
}
```

## Hook 类型

### builtin

由 Ant Code 内置实现，适合安全、审计、状态同步。

第一版内置：

- `auditToolUse`
- `auditPermissionDenied`
- `recordSensitiveFiles`（`denySensitiveFiles` 保留为兼容别名）
- `recordFileChanged`
- `recordTodoUpdated`
- `recordSubagentLifecycle`
- `compactAudit`

### command

本地命令 hook，适合验证和格式化。

约束：

- 默认 `blocking: false`。
- 必须有超时。
- 输出截断。
- 环境变量走 allowlist。
- 在 trusted workspace 下才执行项目配置的 command hook。
- command hook 本身进入审计日志。
- 非阻断 command hook 后台异步调度，不能卡住模型/工具主流程。
- 后台 command hook 在 `/hooks` 中先显示为 running，完成后更新为 completed/failed。
- 后台 command hook 的子进程和计时器会 unref，避免仅因 hook 未结束而拖住 Ant Code 退出。

## 安全策略

1. `hooks.enabled` 为 false 或 `hooks.disableAll` 为 true 时，所有 hooks 停用。
2. command hook 默认非阻断。
3. 只有 `tool.before` 允许显式 `blocking: true`，用于阻止具体危险工具调用。
4. `permission.denied`、`compact.before`、`file.changed`、`todo.updated`、`session.*`、`subagent.*` 都是审计或后台自动化事件，不应阻断主流程。
5. `file.changed` 自动验证失败第一版不阻断主流程，只在 `/hooks`、`/logs` 和状态中记录。
6. hook 输出最多保留 `maxOutputBytes`。
7. hook 输入 payload 脱敏。
8. hook command 不继承 API key、网关 key、token、cookie 等敏感环境变量。
9. hook 执行失败不应导致 TUI 卡死。
10. hook 循环防护：hook 自己触发的工具/命令不再递归触发 hooks。
11. 项目级 hooks 只在 trusted workspace 执行。

## 新增模块

计划新增：

```text
src/hooks/events.js          事件名、payload 规范、脱敏和摘要工具
src/hooks/registry.js        从 config 加载 hooks，按事件和条件匹配
src/hooks/runner.js          执行 builtin/command hook，处理超时、输出、失败
src/hooks/builtins.js        内置安全和审计 hook
src/hooks/audit-store.js     最近 hook 执行记录，供 /hooks 和 /logs 查询
tests/unit/hooks.test.js     单测
```

## 接入点

### Stage 1：事件模型和配置解析

状态：已完成。

改动：

- 新增 `src/hooks/events.js`。
- 新增 `src/hooks/registry.js`。
- 支持 `hooks.enabled`、`disableAll`、`defaultTimeoutMs`、`maxOutputBytes`、`events`。
- 支持 `when.paths` 的简单 glob 匹配。

验收：

- 单测能验证配置启用/禁用。
- 能按事件名列出匹配 hooks。
- 无配置时不改变现有行为。

### Stage 2：Hook runner 和审计记录

状态：已完成。

改动：

- 新增 `src/hooks/runner.js`。
- 新增 `src/hooks/audit-store.js`。
- 支持 builtin 和 command。
- command 支持 timeout、output cap、env allowlist。

验收：

- 成功 hook 有记录。
- 失败 hook 有错误摘要。
- 超时 hook 不阻塞 TUI。
- 输出过长被截断。

### Stage 3：工具执行前后和权限拒绝

状态：已完成。

接入：

- `src/tools/runtime.js`

事件：

- `tool.before`
- `tool.after`
- `tool.failed`
- `permission.denied`

验收：

- 调用 `read_file`、`grep`、`powershell` 时有 hook 记录。
- 被权限拒绝时有 `permission.denied` 记录。
- `tool.before` blocking hook 可以阻止危险目标。

### Stage 4：文件变更和 todo 更新

状态：已完成。

接入：

- `write_file`
- `edit_file`
- `todo_write`
- 工作流状态记录。

事件：

- `file.changed`
- `todo.updated`

验收：

- 文件写入/编辑后能看到文件变更 hook。
- todo 更新后 `/hooks` 能显示最近 todo 事件。
- 配置 `npm run check` 后，JS/TS 文件改动可触发 command hook。

### Stage 5：子智能体生命周期

状态：已完成。

接入：

- `src/agents/runner.js`
- 任务 store 状态更新点。

事件：

- `subagent.started`
- `subagent.completed`
- `subagent.failed`
- `subagent.paused`

验收：

- 调用 `agent_run` 后能看到 started。
- 成功、失败、暂停都能记录对应状态。
- 右侧子智能体面板不被 hook 记录刷屏。

### Stage 6：compact 和 session

状态：已完成。

接入：

- `src/core/context-window.js`
- TUI `/compact`
- session start/end 的现有入口。

事件：

- `compact.before`
- `compact.after`
- `session.start`
- `session.end`

验收：

- 手动 `/compact` 后能看到压缩前后 tokens、strategy、fallback。
- session start 不应明显变慢。
- session end hook 超时要短，不能拖住退出。

### Stage 7：`/hooks` 展示和 `/logs` 联动

状态：已完成。

改动：

- 新增 slash command `/hooks`。
- TUI slash 面板新增中文说明。
- `/logs` 继续展示运行日志，`/hooks` 专门展示 hook 状态。

`/hooks` 展示：

- hooks 是否启用。
- 注册事件数量。
- 当前 hooks 列表。
- 最近执行记录。
- 最近失败记录。
- blocking hooks 标识。

验收：

- `/hooks` 可读、中文清晰。
- 不需要进入右侧栏也能看 hook 状态。
- hook 失败不会显示成普通红色报错刷屏，除非它真的阻断了主流程。

### Stage 8：测试、文档、变更日志

状态：已完成。

改动：

- 新增 unit tests。
- 更新 `LLM_ONBOARDING.md`。
- 更新 `PROJECT_CHANGELOG.zh-CN.md`。
- 更新 provenance 文档。
- 如有外显行为，新增 deployment acceptance。

验收：

```powershell
cd C:\saveproject\LBJ-workspace\lab-agent
node --check .\src\hooks\events.js
node --check .\src\hooks\registry.js
node --check .\src\hooks\runner.js
node --check .\src\hooks\builtins.js
node --test .\tests\unit\hooks.test.js
npm run check
```

## 推荐内置默认行为

第一版建议默认启用审计型 builtin hooks：

- 工具调用摘要记录。
- 权限拒绝记录。
- 文件变更记录。
- todo 更新记录。
- 子智能体生命周期记录。
- compact 记录。

默认不启用自动 `npm run check`，只在示例配置和 `/hooks` 文档里说明。原因：

- 不同项目测试命令不同。
- 自动跑全量测试可能拖慢长任务。
- 第一版先稳定机制，避免影响当前可用体验。

## 风险和回滚

风险：

- hook command 卡住或输出过多。
- 用户显式配置的 `tool.before` blocking hook 误杀正常工具。
- 文件变更事件触发过频。
- TUI 日志被 hook 记录刷屏。
- 配置错误导致用户误以为工具坏了。

缓解：

- 总开关 `hooks.enabled=false`。
- `disableAll=true` 作为强制关闭。
- command hook 默认非阻断。
- 非阻断 command hook 异步调度，避免测试/格式化 hook 阻塞智能体继续工作。
- 输出限制和超时。
- `/hooks` 清楚显示 hook 来源和最近失败。
- 日志分级，非阻断失败不使用强错误样式。
- 敏感路径由权限层强确认，不由 hooks 一刀切阻断，避免正常密钥维护不可用。

回滚：

- 删除或关闭 `hooks` 配置即可恢复旧行为。
- 新增 hook 模块不应改变未启用配置下的工具执行路径。
- 若 TUI 出现问题，保留 `/logs`，不把 hook 状态塞回右侧栏。

## 用户验收脚本

1. 启动 TUI：

```powershell
cd C:\saveproject\LBJ-workspace\lab-agent
node .\src\cli\index.js tui
```

2. 运行 `/hooks`。

预期：能看到 hooks 开关、内置 hooks、最近记录为空或少量 session 记录。

3. 让智能体只读读取一个文件。

预期：`tool.before`、`tool.after` 有审计记录。

4. 让智能体修改一个小文件。

预期：`file.changed` 有记录，右侧任务状态不被打乱。

5. 尝试读取 `.env` 或伪造敏感路径。

预期：出现敏感信息强确认；拒绝时不会读取，批准时允许继续，并在 `/hooks` 记录敏感路径命中。

6. 调用一个子智能体。

预期：`subagent.started` 和完成/失败/暂停状态有记录。

7. 执行 `/compact`。

预期：`compact.before`、`compact.after` 记录 tokens、策略和结果。

8. 配置一个非阻断 `npm run check` hook 后修改 JS 文件。

预期：hook 执行结果进入 `/hooks` 和 `/logs`，失败不阻断主对话。

## 审核问题

需要用户确认：

1. v1 是否默认启用审计型 builtin hooks？
2. v1 是否默认启用 `recordSensitiveFiles` 审计 hook，而不是 blocking hook？
3. command hook 是否只允许 trusted workspace？
4. `/hooks` 是否仅做 slash command，不重新加到右侧栏？
5. 自动测试 hook 是否保持示例配置，不默认开启？
