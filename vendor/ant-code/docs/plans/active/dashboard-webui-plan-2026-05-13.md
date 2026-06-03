# Ant Code Dashboard WebUI 计划

状态：已执行；本文保留为 Dashboard 初版计划和验收记录，后续行为以 `PROJECT_CHANGELOG.zh-CN.md` 与部署/验收文档为准
创建日期：2026-05-13
适用仓库：`C:\saveproject\LBJ-workspace\lab-agent`
正式产品名：Ant Code
新增入口：`ant-code dashboard`

## 一句话目标

在不改变现有 TUI 行为的前提下，为 Ant Code 新增一个本机 WebUI Dashboard，让不习惯 TUI 的实验室成员可以用干净、简洁、可追踪但默认折叠的界面启动和管理智能体任务。

## 当前基线和背景

当前仓库目录名仍是 `lab-agent`，但正式对外产品名和命令是 Ant Code。现有 `ant-code` 命令默认启动 TUI，这对有编程基础的用户较友好，但实验室内大量非程序员用户对 TUI 的输入方式、滚动记录、工具过程和权限确认不够适应。

Ant Code 已经具备核心智能体能力、工具权限引擎、会话存储、事件归一化和 TUI 交互层。Dashboard 不应该重写这些核心能力，也不应该把 TUI 原样搬到浏览器里，而应该新增一个 Web adapter，把同一套核心能力呈现为更适合普通实验室用户的任务工作台。

## 参考体验

Dashboard 的交互可以参考 Codex 的干净过程展示模式：

- 模型工作时只展示一个轻量、可闪烁的活动标题，不展示思考过程正文。
- 每次工具调用折叠成一行摘要，例如“读取了 4 个文件”“生成了 report.pdf”“正在运行脚本”。
- 任务最终回复完成后，自动折叠本轮所有过程，只保留最终回复和可展开的过程记录。
- 右侧提供图片、文件、产物预览栏，方便用户检查生成结果。
- 左侧按项目文件夹和任务线程组织历史会话。

该参考只吸收可观察的产品交互，不复制任何内部实现。

## 硬性边界

### 本轮必须遵守

- `ant-code` 现有默认行为保持不变，继续启动 TUI。
- 新增 `ant-code dashboard` 作为 WebUI 启动入口。
- Dashboard 第一版只支持本机访问。
- 默认监听地址为 `127.0.0.1`。
- 默认端口为 `7410`。
- 不提供局域网分享入口，不实现 `--share`。
- 不新增远程访问、多人协作、云端同步能力。
- 不修改现有 TUI 实现文件。实现阶段如发现必须改 `src/cli/tui.js` 或 `src/cli/tui/` 下文件，必须先暂停并重新确认。
- Dashboard 与 TUI 共享会话历史存储，不能另起一套不兼容的历史系统。
- 第一版必须提供与 TUI 一致语义的三层权限选择。
- 权限确认弹窗必须在网页输入栏顶部弹出，而不是隐藏在日志、右栏或浏览器原生确认框里。
- 需求核对必须复用现有 `ask_user` 工具，在网页输入栏顶部显示独立核对面板；它不同于权限确认，不能把需求澄清误做成权限审批。
- Dashboard 必须提供明确关闭路径，不能让用户只能依赖静默后台进程。

### 本轮不做

- 不做局域网或公网访问。
- 不做账号体系。
- 不做团队协作和多人同时编辑。
- 不做复杂流程图。
- 不把完整工具日志默认铺开展示。
- 不展示模型思考链路。
- 不做 Office 文档在线编辑。
- 不追求第一版预览所有文件格式。
- 不重构 TUI 布局、按键、滚动、权限弹窗或终端渲染。

## 产品结构

Dashboard 采用三栏布局：

```text
左侧：项目与任务线程
中间：对话、最终回复、折叠活动流
右侧：图片、文件、报告、表格和代码预览
```

### 左侧：项目与线程

左侧用于管理当前打开项目文件夹下的任务会话：

- 显示当前项目文件夹。
- 显示共享会话历史中的任务线程。
- 支持新建任务。
- 支持切换历史任务。
- 支持从历史任务继续对话。
- 每个线程显示标题、状态、最后更新时间和权限模式摘要。
- Dashboard 创建或更新的会话必须写入现有 `.lab-agent/sessions` 存储，使 TUI 后续可以继续读取或恢复。

第一版只要求管理当前工作目录下的会话；跨项目聚合可以后续增强。

### 中间：任务对话和折叠过程

中间区域是主工作区：

- 用户自然语言输入。
- Agent 最终回复。
- 工具调用和执行状态。
- 权限确认。
- 错误和恢复提示。

默认展示策略：

- 用户消息完整展示。
- Assistant 最终回复完整展示。
- Agent 需要澄清需求时，显示“需求核对”面板，支持单选、多选和补充文本，用户确认后同一轮任务继续运行。
- 执行过程默认折叠。
- 工具调用默认折叠成一行标题。
- 当前正在执行的工具可以显示轻量进度状态。
- 任务完成后，本轮过程自动折叠，只保留“过程记录”入口。
- 不展示思考过程正文，只展示类似“正在分析任务”“正在检查文件”的用户可理解状态。

示例活动标题：

```text
正在理解任务
正在查看项目文件
读取了 4 个文件
正在运行数据处理脚本
生成了 2 个文件
等待权限确认
任务已完成
```

### 右侧：产物与文件预览

右侧栏用于降低用户查找结果文件的成本：

- 展示当前任务涉及的文件。
- 展示最近生成和修改的文件。
- 点击最终回复中的文件路径或文件名时，在右侧打开预览。
- 支持只读预览，不在第一版做复杂编辑。

第一版预览范围：

- 图片：`png`、`jpg`、`jpeg`、`gif`、`webp`。
- 文本：`txt`、`log`、`json`、`csv`、`tsv`。
- Markdown：`md`、`markdown`。
- 代码：常见源码文件，按纯文本只读预览即可。
- PDF：浏览器内嵌预览或下载/打开入口。

第一版对 Word、Excel、PPT 等 Office 文件只要求显示文件卡片、路径、大小和打开入口；后续根据实验室实际反馈再增强预览。

## CLI 需求

新增命令：

```powershell
ant-code dashboard
```

默认行为：

- 从当前工作目录启动 Dashboard。
- 绑定 `127.0.0.1`。
- 使用端口 `7410`。
- 端口被占用时，自动向后寻找可用端口。
- 启动成功后自动打开默认浏览器。
- 控制台输出本地访问地址和当前项目路径。
- 关闭方式必须清楚：网页中提供“关闭 Dashboard”确认入口；终端前台运行时也可以使用 `Ctrl+C`。

建议支持参数：

```powershell
ant-code dashboard --port 8080
ant-code dashboard --host 127.0.0.1
ant-code dashboard --no-open
ant-code dashboard --project .
```

约束：

- `--host` 第一版只允许 `127.0.0.1`、`localhost` 或等价本机回环地址。
- 不提供 `--share`。
- 不提供 `0.0.0.0` 绑定。
- 现有 `ant-code`、`ant-code tui`、`ant-code -p`、`ant-code doctor`、`ant-code gateway` 行为保持兼容。

## 权限模型

Dashboard 第一版必须对齐 TUI 的三层权限语义：

```text
计划确认：写入、命令和外部能力需要确认后执行。
工作区权限：工作区内非敏感读写和常规本地命令自动同意。
完全访问：测试机模式，所有本地工具、MCP、浏览器、网络和任意路径操作自动同意。
```

Dashboard UI 需要提供：

- 当前权限模式展示。
- 三层权限切换控件。
- 权限模式说明。
- 当前会话同类批准状态。
- 权限请求弹窗。

权限请求弹窗位置：

- 必须出现在输入栏顶部。
- 弹窗应阻塞当前待批准工具调用，但不阻塞用户查看历史和右侧预览。
- 不使用浏览器原生 `confirm()`。
- 不藏到右侧栏。

权限请求弹窗内容：

- 操作类型。
- 工具名或命令名。
- 目标文件或命令摘要。
- 风险说明。
- 可预览的 diff、文件路径或命令参数。
- 操作按钮：
  - 允许一次。
  - 本会话允许同类请求。
  - 拒绝。
  - 取消。

所有 Dashboard 权限决策必须仍然走现有本地权限引擎和 `approvalCallback`，不能在前端绕过策略。

## 会话与存储

Dashboard 与 TUI 共享现有会话存储：

```text
.lab-agent/sessions/
```

要求：

- Dashboard 创建的会话应能被 TUI 历史列表看到。
- Dashboard 继续的会话应保留上下文、消息和 transcript archive。
- TUI 创建的会话应能被 Dashboard 左侧线程读取。
- 存储仍使用现有 transcript 策略、保留天数和加密配置。
- Dashboard 可在 metadata 中增加轻量来源标记，例如 `client: "dashboard"`，但不能破坏 TUI resume。
- 不新增 `.dashboard/sessions` 或其他不兼容历史根目录。

如果实现阶段发现现有 `mode` 字段只接受 `interactive` / `print`，第一版应优先保持核心存储兼容，可以用 `interactive` 作为运行模式，并在 metadata 扩展字段中记录 Dashboard 来源。

## 技术架构建议

建议新增 Dashboard adapter，而不是改 TUI：

```text
src/core / src/agents / src/tools / src/storage
        ↑
        ├─ src/cli/tui         现有 TUI，保持不动
        └─ src/dashboard       新增 WebUI adapter
```

建议新增模块边界：

```text
src/dashboard/
  server.js          本机 HTTP 服务启动、端口选择、浏览器打开
  routes.js          API 路由
  events.js          core events 到 dashboard activity 的映射
  sessions.js        共享 session store 的读取、恢复和索引
  files.js           文件索引、安全读取和预览元数据
  permissions.js     Web approval callback 桥接
  public/            第一版前端静态资源或构建产物
```

前端可以先采用轻量静态资源加原生浏览器能力实现，或在依赖策略允许的前提下引入更完整的前端构建。无论选择哪种方式，都需要保持发布包和依赖审计可控。

## 事件展示模型

Dashboard 不直接把所有底层事件铺给用户，而是转换为用户能理解的 activity：

| Ant/core 事件 | Dashboard 展示 |
| --- | --- |
| `turn_start` | 开始任务 |
| `gateway_request_start` | 正在请求模型 |
| `assistant_thinking_start` | 正在分析任务 |
| `assistant_delta` | 可见正文草稿 |
| `tool_use_start` / `tool_start` | 正在执行工具 |
| `tool_result` | 工具完成、阻止或失败 |
| `assistant_final` | 最终回复 |
| `turn_result` | 任务完成 |
| `gateway_error` | 模型请求失败 |
| approval callback | 等待权限确认 |

展示原则：

- 默认标题化和折叠化。
- 用户可展开查看输入摘要、输出摘要、失败原因和可安全展示的日志。
- 对 partial streaming 做节流，避免页面频繁抖动。
- 可见正文 delta 不等到最终回复才展示，按模型 round 作为临时草稿卡显示在聊天区；最终回复到达后，草稿卡统一折叠为“草稿记录”，主对话只突出最终回复。
- provider thinking / reasoning delta 不作为草稿展示，只能转成“正在分析任务”一类状态提示，避免泄露隐藏思考。
- lab-agent-gateway 的 SSE/NDJSON 流必须按完整 record 增量派发事件，不能等整个响应结束后再解析，否则 WebUI 草稿会退化成最终回复前不可见。
- `ask_user` 事件展示为输入栏上方的需求核对面板，允许用户回答后继续当前 tool round；该面板不进入权限审批通道，不绕过工具 runtime。
- 对敏感内容继续使用现有 redaction 和 transcript 策略。

## 文件预览安全边界

文件预览必须遵守本地项目边界和权限策略：

- 默认只预览当前工作区内文件。
- 对工作区外路径，必须显示风险提示，并由权限引擎决定是否允许访问。
- 文本预览需要限制大小，超限时显示摘要和打开入口。
- 二进制文件不尝试当文本读取。
- 文件路径显示要清晰，但避免在可导出日志中泄露不必要的私密路径。
- 删除、覆盖、执行文件等操作不能从预览栏直接绕过权限。

## 视觉和交互要求

Dashboard 面向实验室普通用户，整体视觉应干净、简洁、美观：

- 首页就是任务界面，不做营销式 landing page。
- 不展示复杂指令。
- 不用大面积终端黑底作为主视觉。
- 不做流程图式任务展示。
- 折叠卡片要清楚显示状态、工具类型和结果。
- 输入区始终稳定可见。
- 权限弹窗位于输入栏顶部，视觉层级高于执行流。
- 右侧预览栏允许收起，避免小屏挤压主任务。
- 小屏幕下可降级为左侧抽屉、主对话、右侧预览抽屉。

## 视觉设计标准

Dashboard 第一版必须以深灰色为基调，参考 Codex 可观察到的产品审美：克制、干净、现代、低噪声，像一个专业桌面工作台，而不是传统后台管理系统或终端皮肤。

设计约束：

- 主背景使用深灰或近黑灰，不使用纯黑大面积背景。
- 面板使用分层深灰，通过细边框、轻微明度差和有限阴影区分层级。
- 主文字使用高对比浅色，次级说明使用中性灰，避免低对比导致阅读疲劳。
- 强调色只用于状态、选中项、主要按钮和权限风险提示，不做大面积彩色渐变。
- 品牌标识、顶部工作台标签和进度强调使用石灰/大理石灰系，不使用荧光绿或强绿色作为主强调色。
- 状态色保持克制：成功、等待、风险、错误各有清晰但不过饱和的颜色。
- 左侧线程栏、中间对话区、右侧预览栏要有稳定比例和清楚边界。
- 折叠工具调用采用安静的单行活动项，带图标、状态点、标题和可展开控件。
- 最终回复应比过程记录更突出，过程记录默认退后。
- 输入区要像工作台的主操作面板，始终清晰可见，不被日志或预览挤压。
- 权限弹窗应是高层级浮层，但保持克制，不使用浏览器原生弹窗。
- 右侧预览栏应像文件检阅面板，图片、PDF、Markdown 和代码预览要有统一的暗色容器。
- 所有按钮、标签、卡片和弹窗的圆角应保持克制，默认不超过 8px。
- 不使用装饰性光斑、渐变球、复杂背景纹理或营销页式 hero。
- 不允许文字溢出、控件重叠、布局抖动或 hover 后改变布局尺寸。
- 桌面和窄屏都必须通过浏览器截图检查，截图中界面需要达到可交付产品质感。

## 分阶段实施计划

### Stage 0：冻结边界和设计原型

状态：待执行

工作：

- 确认 Dashboard 不修改 TUI 文件。
- 确认 `ant-code dashboard` 的 CLI 参数设计。
- 确认三栏布局、活动折叠、右侧预览、权限弹窗位置。
- 确认共享 `.lab-agent/sessions` 策略。

验收：

- 本计划文档通过审核。
- 任务范围没有开放式冲突。

### Stage 1：CLI 入口和本机服务骨架

状态：待执行

工作：

- 在 CLI 中新增 `dashboard` 子命令。
- 新增 Dashboard server 模块。
- 默认绑定 `127.0.0.1:7410`。
- 实现端口冲突自动递增。
- 启动后自动打开浏览器。
- 支持 `--port`、`--host`、`--no-open`、`--project`。

验收：

```powershell
ant-code
ant-code tui
ant-code dashboard
ant-code dashboard --no-open
ant-code dashboard --port 7411
```

- 前两个命令仍进入 TUI。
- Dashboard 命令启动本机服务。
- `--host 0.0.0.0` 被拒绝。

### Stage 2：共享会话索引和线程列表

状态：待执行

工作：

- 复用现有 `createSessionStore()`。
- 读取 `.lab-agent/sessions` 会话记录。
- 在左侧显示线程列表。
- 支持新建 Dashboard 会话。
- 支持打开 TUI 创建的历史会话。

验收：

- TUI 产生的历史会话能在 Dashboard 看到。
- Dashboard 产生的历史会话能被 TUI 历史机制读取。
- transcript 保留策略和加密策略不被绕过。

### Stage 3：任务运行和活动流

状态：待执行

工作：

- WebUI 输入框发送用户需求。
- 后端复用核心 session/turn 运行能力。
- 使用事件流向前端推送任务状态。
- 将 core/ant events 转换为 Dashboard activity。
- 工具调用默认折叠。
- 最终回复完成后自动折叠过程记录。

验收：

- 用户能从网页发起一次完整任务。
- Assistant 最终回复可见。
- 工具调用不默认铺满页面。
- 过程记录可展开。
- 不展示模型思考正文。

### Stage 4：权限确认和三层权限模式

状态：待执行

工作：

- Dashboard 显示当前权限模式。
- 支持切换计划确认、工作区权限、完全访问。
- 将权限模式映射到现有 session permission state。
- Web approval callback 弹出输入栏顶部确认框。
- 实现允许一次、本会话允许、拒绝、取消。
- 权限结果写入活动流。

验收：

- 计划确认模式下写文件会弹出网页权限确认。
- 弹窗出现在输入栏顶部。
- 拒绝后不会发生文件修改。
- 允许一次只放行当前请求。
- 本会话允许对同类请求生效。
- 工作区权限和完全访问语义与 TUI 一致。

### Stage 5：右侧文件与预览栏

状态：待执行

工作：

- 从工具事件、文件路径和最终回复中收集任务相关文件。
- 右侧显示生成/修改/引用文件。
- 实现图片预览。
- 实现文本、Markdown、代码预览。
- 实现 PDF 预览或打开入口。
- Office 文件显示文件卡片和打开入口。

验收：

- 生成图片后能在右侧预览。
- 生成 Markdown 或文本后能在右侧预览。
- PDF 能在右侧查看或打开。
- 大文件不会卡死页面。
- 工作区外文件不会被静默读取。

### Stage 6：视觉打磨和回归测试

状态：待执行

工作：

- 调整三栏响应式布局。
- 落实深灰基调和 Codex 式克制审美。
- 打磨折叠活动卡、最终回复和权限弹窗视觉。
- 补充单元测试和集成 smoke test。
- 使用浏览器截图验证桌面和窄屏布局。
- 检查 TUI 文件未被修改。

验收：

```powershell
npm run check
```

必须通过。另需人工验证：

- `ant-code` 默认 TUI 仍可启动。
- Dashboard 首屏无需复杂指令即可发起任务。
- 权限弹窗位置正确。
- 任务完成后过程自动折叠。
- 右侧预览栏可用。

## 执行清单

> 执行阶段必须在本文档中更新勾选状态，不能只记录在聊天里。每个阶段完成后，应补充实际改动文件、验证命令和遗留风险。

### Stage 0：冻结边界和设计原型

- [x] 确认 `ant-code` 默认入口继续启动 TUI。
- [x] 确认 `ant-code dashboard` 是唯一新增 WebUI 主入口。
- [x] 确认 Dashboard 第一版只监听本机回环地址。
- [x] 确认默认端口为 `7410`，端口冲突时自动递增。
- [x] 确认不提供 `--share`、`0.0.0.0` 或局域网访问能力。
- [x] 确认 Dashboard 与 TUI 共享 `.lab-agent/sessions`。
- [x] 确认三栏布局：左侧线程、中间对话、右侧预览。
- [x] 确认权限弹窗固定在输入栏顶部。
- [x] 确认实现阶段不修改 `src/cli/tui.js` 和 `src/cli/tui/`。

复核记录：

- 2026-05-13：已核对现有入口位于 `src/cli/index.js`，TUI 实现集中在 `src/cli/tui.js` 和 `src/cli/tui/`，Dashboard 将新增在 `src/dashboard/`。
- 2026-05-13：复核通过；无需修改 Stage 0 结论，进入 Stage 1。

### Stage 1：CLI 入口和本机服务骨架

- [x] 扩展 CLI 参数解析，识别 `dashboard` 子命令。
- [x] 解析 `--port` 参数。
- [x] 解析 `--host` 参数，并限制为本机回环地址。
- [x] 解析 `--no-open` 参数。
- [x] 解析 `--project` 参数。
- [x] 新增 Dashboard server 启动模块。
- [x] 实现默认 `127.0.0.1:7410` 监听。
- [x] 实现端口占用后的递增选择。
- [x] 实现启动成功后的浏览器自动打开。
- [x] 输出 Dashboard 本地 URL 和项目路径。
- [x] 增加 CLI 参数解析测试。
- [x] 增加本机 host 限制测试。

复核记录：

- 2026-05-13：第一轮复核通过 `node --check src/dashboard/server.js`、`node --check src/dashboard/sessions.js`、`node --check src/dashboard/events.js`、`node --test tests/unit/cli-args.test.js`。
- 2026-05-13：第二轮复核通过 `node --test tests/unit/dashboard-server.test.js`，确认 host 限制、端口标准化和端口递增。

### Stage 2：共享会话索引和线程列表

- [x] 复用 `createSessionStore()` 读取现有会话记录。
- [x] 实现 Dashboard 会话列表 API。
- [x] 在左侧线程栏展示当前工作区会话。
- [x] 展示会话标题、状态、更新时间和权限模式摘要。
- [x] 支持打开 TUI 创建的历史会话。
- [x] 支持 Dashboard 新建会话并写入共享 store。
- [x] 支持 Dashboard 继续历史会话。
- [x] 确认 transcript retention 策略继续生效。
- [x] 确认 transcript encryption 策略继续生效。
- [x] 增加共享会话读取和兼容性测试。

复核记录：

- 2026-05-13：实现复用 `createSessionStore()`，Dashboard 不新增独立 session 根目录。
- 2026-05-13：复核现有 `tests/unit/storage.test.js` 覆盖 retention/encryption；最终整体验证需运行完整测试。
- 2026-05-13：新增 `tests/unit/dashboard-runtime.test.js`，确认 Dashboard 任务完成后会写入共享 session metadata。

### Stage 3：任务运行和折叠活动流

- [x] 实现 WebUI 输入框发送任务需求。
- [x] 后端复用核心 session/turn 执行能力。
- [x] 建立任务事件流通道。
- [x] 将 core/ant events 映射为 Dashboard activity。
- [x] 将工具开始事件显示为折叠标题。
- [x] 将工具完成事件显示为结果摘要。
- [x] 将模型思考事件显示为“正在分析任务”等状态标题。
- [x] 禁止展示思考正文。
- [x] 将“正在分析 / 正在生成 / 正在请求模型”等运行态合并到固定动态提示区。
- [x] 子智能体运行时在固定动态提示区显示独立状态 chip。
- [x] 避免高频运行态在聊天窗口连续堆叠无内容卡片。
- [x] 在聊天区展示 todo/plan 轻量任务进度面板，避免任务进展变成黑箱。
- [x] todo/plan 更新时复用同一进度面板，不重复堆叠。
- [x] 实现 Assistant 最终回复展示。
- [x] 实现任务完成后自动折叠本轮过程。
- [x] 实现过程记录的手动展开和收起。
- [x] 增加 activity 映射测试。

复核记录：

- 2026-05-13：`tests/unit/dashboard-events.test.js` 通过，确认 thinking 不泄露正文、工具完成映射为折叠摘要。
- 2026-05-13：人工代码复核确认前端 activity 支持点击展开/收起，最终回复独立展示。
- 2026-05-13：`tests/unit/dashboard-runtime.test.js` 通过，确认 Web 输入到核心 turn 执行、事件流和最终回复链路可用。
- 2026-05-13：根据 UI 反馈修正运行态展示：重复 thinking/generating 状态通过 `coalesceKey` 合并，前端改为输入区上方固定 live status；真实流式 smoke 验证运行中聊天区 activity 卡为 0，完成后只保留折叠过程记录和最终回复。
- 2026-05-13：根据进度可见性反馈新增 `workflow_snapshot`，Dashboard 聊天区显示 todo/plan 进度面板；真实 smoke 验证面板从 `0/3` 更新到 `3/3`，且页面只保留 1 个进度面板。
- 2026-05-29：根据后台子智能体可观察性和唤醒测试反馈，Dashboard 接入 `subagent_group_started/progress/wakeup`，在 live status 中展示后台组状态，并在 `subagent_group_wakeup` 后通过内部 `wakeup` 队列消费 wake prompt；忙时排队，空闲时自动续跑主控，任务组记录写入 `wakePromptConsumedAt`。

### Stage 4：三层权限和网页确认弹窗

- [x] 显示当前权限模式。
- [x] 实现计划确认、工作区权限、完全访问三层切换。
- [x] 将权限模式映射到 session permission state。
- [x] 实现 Web approval callback 桥接。
- [x] 在输入栏顶部渲染权限确认弹窗。
- [x] 展示工具名、操作类型、目标路径或命令摘要。
- [x] 展示风险说明和可用预览。
- [x] 实现“允许一次”。
- [x] 实现“本会话允许同类请求”。
- [x] 实现“拒绝”。
- [x] 实现“取消”。
- [x] 将权限决策写入活动流。
- [x] 验证拒绝后不会发生文件修改。
- [x] 增加权限 callback 单元测试。
- [ ] 增加权限弹窗浏览器 smoke test。
- [x] 接入 `ask_user` 的 Web userInputCallback。
- [x] 在输入栏顶部渲染需求核对面板。
- [x] 支持需求核对的单选、多选、补充文本、确认和取消。
- [x] 确认需求核对回答会回到同一轮工具结果并继续任务。
- [x] 增加需求核对运行时和路由测试。

复核记录：

- 2026-05-13：`tests/unit/dashboard-permissions.test.js` 通过，确认三层权限状态映射和同类审批 key。
- 2026-05-13：代码复核发现“计划确认”不应传 `readonly: true` 锁死会话，已修正为非锁定 plan 模式并再次复核。
- 2026-05-13：`tests/unit/dashboard-runtime.test.js` 增加拒绝写文件审批用例，确认拒绝后 `denied.md` 不会被创建。
- 2026-05-13：补齐 Dashboard `ask_user` 需求核对桥接：后端 `userInputCallback` 生成 `question_required`，前端在输入栏顶部显示核对面板，确认/取消通过 `/api/questions/:id` 回写工具结果；`dashboard-runtime` 和 `dashboard-server` targeted tests 通过。

### Stage 5：右侧文件和产物预览

- [x] 从工具事件中收集生成、修改和引用文件。
- [x] 从最终回复中识别可点击文件路径。
- [x] 实现右侧文件列表。
- [x] 实现图片预览。
- [x] 实现文本预览。
- [x] 实现 Markdown 预览。
- [x] 实现代码只读预览。
- [x] 实现 PDF 内嵌预览或打开入口。
- [x] 实现 Office 文件卡片和打开入口。
- [x] 限制大文件读取大小。
- [x] 阻止二进制文件被当作文本读取。
- [x] 对工作区外路径显示风险提示并走权限策略。
- [x] 增加文件预览路径边界测试。

复核记录：

- 2026-05-13：`tests/unit/dashboard-files.test.js` 首轮发现普通文件名提取过宽，已收紧正则。
- 2026-05-13：修正后重新运行 `node --test tests/unit/dashboard-files.test.js tests/unit/cli-args.test.js`，复核通过。

### Stage 6：视觉打磨、测试和文档收尾

- [x] 完成桌面三栏布局打磨。
- [x] 柔化三栏边界，减少硬线条分割感。
- [x] 完成窄屏抽屉式降级。
- [x] 落实深灰色视觉基调。
- [x] 对齐 Codex 式克制、干净、现代的审美方向。
- [x] 打磨折叠活动卡片。
- [x] 打磨最终回复排版。
- [x] 打磨权限弹窗视觉层级。
- [x] 检查按钮、标签、卡片和弹窗圆角不超过 8px。
- [x] 检查没有装饰性光斑、渐变球、复杂背景纹理或营销页式 hero。
- [x] 检查没有文字溢出、控件重叠或布局抖动。
- [x] 验证输入区始终稳定可见。
- [x] 使用浏览器截图验证桌面布局。
- [x] 使用浏览器截图验证窄屏布局。
- [x] 使用浏览器截图验证权限弹窗位置。
- [x] 确认 `src/cli/tui.js` 未被修改。
- [x] 确认 `src/cli/tui/` 未被修改。
- [x] 运行 `npm run check`。
- [x] 更新 `README.md`。
- [x] 更新 `README.zh-CN.md`。
- [x] 更新 `PROJECT_CHANGELOG.zh-CN.md`。
- [x] 更新 `LLM_ONBOARDING.md`。
- [x] 更新 `docs/deployment/local-installation.md`。
- [x] 更新相关 provenance 和验收文档。
- [x] 将计划实际执行状态同步到本文档。
- [x] 补充 Dashboard 显式关闭入口和关闭说明。
- [x] 验证关闭入口会触发本机服务退出，而不是静默后台常驻。

复核记录：

- 2026-05-13：Dashboard 本机服务启动并通过 `Invoke-WebRequest` 验证 `/api/status`、`/`、`/assets/styles.css`、`/assets/app.js`、`/api/sessions` 均可响应。
- 2026-05-13：Codex in-app browser 插件初始化连续超时；随后使用本机 Playwright Chromium 生成桌面、窄屏和权限弹窗截图，第一轮桌面截图发现输入区被挤出视口，已修复 `.workspace`/`.app-shell` 高度约束并二次截图通过。
- 2026-05-13：`git diff -- src/cli/tui.js src/cli/tui` 无输出，确认未修改 TUI 实现文件。
- 2026-05-13：`npm run check` 通过，575 个测试全部通过；新增 provenance 后 release gate 通过。
- 2026-05-13：根据关闭生命周期反馈，新增 `/api/shutdown`、页面“关闭 Dashboard”确认入口和终端关闭提示； targeted server test 复核关闭路由先响应再触发关停回调。
- 2026-05-13：根据视觉反馈调整深灰工作台质感：外层留白、弱边框、低噪声面板层级替代硬切割线；生成桌面、窄屏、live 子任务和最终清爽态截图留档于 `.tmp/dashboard-qa/`。
- 2026-05-13：根据运行态交互反馈，新增 Dashboard 工作区信任 gate、运行中排队、发送按钮点击中断、队列栏“引导对话”、清空/压缩上下文确认；`node --test tests/unit/dashboard-runtime.test.js tests/unit/dashboard-server.test.js` 复核通过。

## 测试要求

必须覆盖：

- CLI 参数解析：`dashboard`、`--port`、`--host`、`--no-open`、`--project`。
- 默认命令兼容：无参数 `ant-code` 仍走 TUI。
- 本机访问限制：拒绝 `0.0.0.0`。
- 端口冲突递增。
- 会话列表读取共享 store。
- Dashboard 事件折叠映射。
- 权限 approval callback 的 allow once / allow session / deny / cancel。
- 需求核对 `ask_user` callback 的 confirm / cancel / choices / custom answer。
- 工作区信任 gate：未信任前不启动 turn，高敏模式保留进程级确认语义。
- 运行中输入队列：同一会话运行中继续发送应进入队列，当前 turn 完成或中断后自动继续。
- 当前任务中断：发送按钮运行中切换为可点击中断状态，后端通过 `AbortController` 中断当前 turn。
- 引导对话：运行中且输入框有新内容时，顶部按钮将输入转为 guide prompt；排队行提供轻量“引导”按钮以指定某条未开始消息。顶部按钮不再在输入为空时接管队首排队消息，避免和队列项内的精确引导入口重复。引导项优先入队并中断当前轮次，不要求用户输入 slash command；点击后必须在同一队列栏即时显示“正在登记/引导已接管/正在按引导继续”等状态，避免用户误判为卡住。
- 上下文清空和压缩：网页内确认后调用共享上下文 helper，空会话不凭空创建上下文操作会话。
- 文件预览路径边界。
- Markdown 渲染：Ant Code 回复和右侧 `.md` 文件至少支持标题、列表、代码块和 pipe table；用户输入保持偏纯文本展示。
- WebUI 可见对话：历史消息只展示 `user` / `assistant`，system/developer/tool 等内部上下文不进入主对话气泡。
- Markdown 第一批增强：支持链接、图片预览/放大、任务列表、引用块、代码复制和 diff 高亮。

建议补充：

- Playwright 或等价浏览器 smoke test。
- 典型任务截图留档。
- 窄屏布局截图。
- 权限弹窗截图。

## 风险和控制

| 风险 | 控制 |
| --- | --- |
| WebUI 实现牵连 TUI | 新增 `src/dashboard/`，TUI 文件只读；如必须改 TUI，先暂停确认。 |
| 共享会话导致 TUI resume 破坏 | 继续使用现有 metadata 和 transcript archive；新增字段必须向后兼容。 |
| 权限在 WebUI 中被绕过 | 所有高风险动作仍走现有权限引擎和 approval callback。 |
| WebUI 队列/中断破坏 TUI 行为 | 队列、guide 和 AbortController 状态只放在 `src/dashboard/sessions.js` 的 adapter 进程内；TUI 文件保持不变。 |
| 用户误以为可以局域网访问 | 第一版只绑定 `127.0.0.1`，拒绝 `0.0.0.0`。 |
| 活动流过度技术化 | core event 到 activity 做用户语义映射，默认折叠。 |
| 预览大文件卡顿 | 文件大小限制、分片读取或摘要展示。 |
| 新依赖影响发布审计 | 优先轻量实现；新增依赖必须通过 dependency policy 和 audit。 |

## 回滚方式

Dashboard 应作为新增模块交付。若实现失败，回滚应只需要移除：

```text
src/dashboard/
```

以及 CLI 中 `dashboard` 分支和相关测试，不应影响：

```text
src/cli/tui.js
src/cli/tui/
src/core/
src/tools/
src/storage/
```

如果后续实现阶段需要改 core/session/storage，应保证改动有单元测试，并明确证明 TUI 行为保持兼容。

## 文档更新要求

实现完成后需要同步更新：

- `README.md`
- `README.zh-CN.md`
- `PROJECT_CHANGELOG.zh-CN.md`
- `LLM_ONBOARDING.md`
- `docs/deployment/local-installation.md`
- 相关 `docs/deployment/` 验收记录
- 相关 `docs/provenance/` 模块说明

计划完成或阶段性关闭后，将本文档从 `docs/plans/active/` 移入 `docs/plans/completed/`，并更新 `docs/plans/README.md`。
