# Ant Code 项目演进日志

本文件用于记录 `lab-agent` 仓库内 Ant Code 重构版的每日关键改动、验收结果和后续风险。以后每次较大改动都应在文件顶部追加一条新记录，方便人工回看项目历史。

维护规则：

- 使用中文记录，优先写清楚“为什么改、改了什么、怎么验收、还有什么风险”。
- 每条记录按日期倒序追加。
- 不记录本地网关 API key、真实用户会话原文、私有凭据或敏感业务数据。
- 如果涉及外部项目，只记录产品思路或公开文档参考，不粘贴外部源码实现。
- 如果只做很小的文案或配置修正，也要至少记录影响范围和验证方式。

## 2026-05-29：Dashboard 后台子智能体状态与自动唤醒闭环

本次补齐 Dashboard 对后台子智能体组的运行状态展示和自动唤醒消费链路。此前核心会话和工具运行时已经会发出 `subagent_group_started`、`subagent_group_progress`、`subagent_group_wakeup` 事件，TUI 也能在子智能体页签观察这些状态并自动续跑主控；但 Dashboard 事件映射层没有接入这些生命周期，主智能体结束本轮后页面容易显示为空闲，用户无法判断后台子智能体是否仍在运行，且子智能体完成后生成的 wake prompt 只写入任务组记录，没有被 Dashboard 父会话消费。

主要变化：

- Dashboard 事件映射新增后台子任务组事件：保留 group/task/profile/waitFor/wakeParent/summary 等非敏感元数据，不把唤醒提示正文透传到前端活动对象。
- Dashboard 前端新增后台子智能体状态缓存：主轮次 `assistant_final`、`files_updated`、`run_state=false` 时只清理普通运行状态，不清理仍在运行或等待唤醒的后台子任务组。
- 右上角 `run-status` 在主轮次结束但后台组仍活跃时显示“子智能体运行中”，后台组完成并等待唤醒时显示“等待子智能体唤醒”，避免误报空闲。
- 输入栏上方现有 `live-status` 改为可折叠的后台子智能体摘要区：默认紧凑展示，展开后显示每个组的 profile、group、task、等待策略、唤醒策略和最新进度。
- 后台运行时的 progress/wakeup 通知补带 `waitFor` 和 `wakeParent`，避免 Dashboard 在只收到后续事件时依赖前序 started 事件猜测唤醒策略。
- Dashboard runtime 在收到原始 `subagent_group_wakeup` 后会创建内部 `wakeup` 队列项：父会话忙时排队，父会话空闲时立即自动续跑主控，模型上下文收到完整 wake prompt，但前端只显示“子智能体完成，主控自动接续”。
- Dashboard 收到后端 `wakeup_queued` 事件后会清理对应后台组的 waiting 状态，状态条从“等待子智能体唤醒”切到“主控续跑已排队/主控接续中”，避免唤醒成功后灯还停在等待态。
- 任务组记录新增 `wakePromptConsumedAt` 字段，用于区分“wake prompt 已生成”与“Dashboard 父会话已消费”，便于排查后续类似“跑完但没回主控”的问题。

验证：

```powershell
node --check src\dashboard\events.js
node --check src\dashboard\public\app.js
node --check src\dashboard\sessions.js
node --check src\tools\runtime.js
node --check src\agents\task-group-store.js
node --test tests\unit\dashboard-events.test.js tests\unit\dashboard-ui.test.js tests\unit\dashboard-runtime.test.js tests\unit\tools.test.js
node --test tests\unit\session.test.js --test-name-pattern "background agent_run|agent_run events"
```

已知风险：

- 后台状态目前随当前页面会话事件流展示；切换到历史会话时不会从磁盘任务组记录重建一整套后台明细。
- 自动续跑依赖 Dashboard 后端进程仍在运行；只刷新浏览器可以恢复事件流，但代码更新后需要重启 Dashboard 后端进程才能加载新 runtime。

## 2026-05-28：Dashboard 模型配置、视觉子智能体与紧凑交互收口

在图片附件直传基础上，本次补齐 Dashboard 的模型管理和视觉任务处理设计：用户可以在 WebUI 底部看到当前模型、切换已注册模型、添加/更新同一网关下的模型配置，并声明模型是否支持图片；当主模型是文本模型但同一网关内存在已配置视觉模型时，系统会用专门的 `visual-verifier` 视觉子智能体先处理图片，再把中文视觉证据报告交给主模型继续推理。当前仍保持“单网关/当前 key 生效”的边界，不做 DeepSeek 与小米等不同网关的混用路由。补充实现后，Dashboard 会把不同 URL/key 保存为可切换的“网关档案”：模型下拉框只展示当前活跃档案内的模型，但可以在同一面板切回已保存网关，不需要每次重新输入配置。

主要变化：

- 模型配置新增 `models[].modalities`、`models[].agentModelTiers`、`agents.vision` 和 `agents.modelTiers.vision`，内置 MiMo 配置区分 `mimo-v2.5-pro` 文本主模型与 `mimo-v2.5` 文本+图片视觉模型。
- Dashboard 底部模型状态支持展示文本/视觉/thinking 标签、切换当前网关内已注册模型、切换已保存网关档案、保存网关 URL/API key/模型 ID/上下文窗口/子智能体模型/视觉子智能体，并可选择保存后同步子智能体默认模型。
- 保存新 URL 或新 API key 时会自动保存当前网关档案，再把新网关设为唯一活跃档案；同一网关且未输入新 key 时，保存模型会追加/更新该网关内模型。
- 修复 Dashboard 进程继承 `LAB_MODEL_GATEWAY_URL` / `LAB_AGENT_MODEL` 等环境变量时，本地保存的 DeepSeek 档案会被全局小米环境覆盖的问题：首次无本地配置时仍可用环境变量初始化；一旦 `.lab-agent/config.json` 存在，Dashboard 的模型/网关读取以本地档案为准。
- 模型下拉新增删除已注册模型：删除仅作用于当前活跃网关档案，至少保留一个模型；如果被删模型是当前主模型、子智能体 tier 或视觉子智能体，会自动回退/清理对应引用，避免错误测试模型长期残留。
- 修复模型下拉删除按钮第一次点击后面板被外层点击监听误关闭的问题；第一次点击会留在面板内显示“再次点击确认删除”的红色提示，第二次才执行删除。
- 核心会话处理图片输入时：主模型支持图片则直接发送图片块；主模型不支持图片但同网关视觉子智能体可用时，先调用 `visual-verifier` 生成视觉证据报告；同网关没有视觉模型时，阻止图片任务并给出明确错误。
- 新增 `visual-verifier` 子智能体画像、视觉路由触发词、上下文触发指导和预算解析；它专门处理截图、图片、OCR、前端视觉回归、布局遮挡/裁切/对齐/可读性等需要多模态复核的任务。
- OpenAI Chat Completions adapter 支持把 Ant Code 图片块转换为 `image_url` data URL；lab gateway protocol 在非敏感 metadata 中标记 `capabilities.images`。
- Dashboard 需求确认框改为单一内部滚动/可拖动区域，标题说明下移到底部操作栏，默认约展示 2.5 个选项，减少长对话中遮挡草稿和中间输出。
- Dashboard 输入区和运行栏进一步压缩：主输入框改为两行，权限说明移到同一行，运行队列说明与标题同一行，清空上下文按钮使用危险红色，右下角增删统计恢复红绿颜色。
- 引导交互收口：队列项内保留精确“引导”按钮；顶部按钮只在“任务运行中且输入框有内容”时显示“引导对话”，不再提供重复的“引导队首”入口。

验证：

```powershell
node --check src\dashboard\public\app.js
node --check src\dashboard\sessions.js
node --check src\config\load-config.js
node --check src\core\session.js
node --test tests\unit\dashboard-ui.test.js tests\unit\dashboard-runtime.test.js tests\unit\dashboard-server.test.js
node --test tests\unit\agent-budget-contract.test.js tests\unit\agent-profiles-config.test.js tests\unit\agent-router.test.js tests\unit\config.test.js tests\unit\gateway-health.test.js tests\unit\gateway-protocol.test.js tests\unit\session.test.js
```

打包验证：

```powershell
npm run verify:readiness
npm run build:exe
.\dist\ant-code-windows-x64\ant-code.exe --version
Get-FileHash -Algorithm SHA256 .\dist\ant-code-windows-x64\ant-code.exe
```

结果：Windows x64 打包目录已更新，`ant-code.exe --version` 输出 `ant-code 3.0.0`。最终 SHA256 以 `dist\ant-code-windows-x64\RELEASE-MANIFEST.md` 和本轮交付说明为准。

已知风险：

- 视觉兜底只在当前活跃网关已注册视觉模型时可用；当前不支持一个文本网关运行主模型、另一个视觉网关处理图片。
- Dashboard 可保存多个网关档案，但运行时仍只有一个档案处于活跃状态；档案切换不是多 key 混合路由。
- 模型是否真实支持视觉仍以用户配置和 provider 实际响应为准；Ant Code 只负责把附件链路、视觉模型配置和错误诊断打通。
- Dashboard 空间压缩主要按当前三栏桌面工作流调优，极窄窗口仍走移动端换行布局，后续需要真实用户反馈继续微调。

## 2026-05-25：Dashboard 图片附件链路与模型侧直传

参考 OpenClaw 对 WebUI 图片上传和非视觉模型的处理思路，本次先落实 Ant Code 自身的附件层和网关传输层：Dashboard 可以选择或粘贴图片，运行时把图片作为本轮用户输入附件发送给模型网关；不在界面上维护“是否视觉模型”的显式配置，非视觉模型或不支持图片的兼容网关由 provider 自身返回不支持/报错。

主要变化：

- Dashboard 输入框新增图片附件按钮、粘贴图片支持和附件预览条，单轮最多 6 张图片，单张限制 8MB。
- `/api/turns`、Dashboard runtime、核心 session turn 都支持携带 `attachments`，允许“只发图片”的回合进入模型调用。
- OpenAI-compatible adapter 将用户图片块转换为 Chat Completions 的 `image_url` data URL 格式；lab gateway protocol 在请求 metadata 中标记本轮包含图片能力。
- 会话 metadata、transcript、归档和事件只保存图片名称、MIME、大小与 redacted 标记，不落盘 base64 图片正文。

验证：

```powershell
node --check src\dashboard\public\app.js
node --check src\dashboard\sessions.js
node --check src\core\session.js
node --check src\model-gateway\openai-chat.js
node --check src\model-gateway\protocol.js
node --test tests\unit\gateway-protocol.test.js tests\unit\dashboard-runtime.test.js tests\unit\session.test.js tests\unit\dashboard-ui.test.js
```

结果：目标测试 `93 pass / 0 fail`。

已知风险：

- 目前实现的是“图片直传给模型端”，不是独立 OCR/视觉工具；文本模型是否能识图由 provider/model 决定。
- 被中断的图片回合仍以现有中断草稿路径为主，极端情况下只保留文本草稿，不额外恢复图片正文；这是刻意避免把 base64 写入持久化历史的结果。

## 2026-05-22：开启 MiMo 思考模式测试路径

为验证小米 MiMo thinking 模式在多轮工具调用后是否会因 `reasoning_content` 回传不完整而返回 400，本次将当前 MiMo 主模型和子智能体模型都切换为 provider-exposed thinking，并让 OpenAI-compatible 网关请求实际携带小米思考参数。代码配置沿用 OpenAI SDK 的 `extra_body` 命名口径，实际 HTTP JSON 会将 `thinking.type = "enabled"` 合并到请求顶层。

主要变化：

- `mimo-v2.5-pro` 和 `mimo-v2.5` 的模型配置改为 `thinking: true`。
- 模型配置新增 `openaiExtraBody`，由 OpenAI-compatible 请求构造合并到请求顶层，当前 MiMo 配置值为 `{ "thinking": { "type": "enabled" } }`。
- `/model` 输出和模型选择测试同步更新为 MiMo thinking 口径。

验证：

```powershell
node --check src\model-gateway\client.js
node --check src\model-gateway\models.js
node --check src\model-gateway\openai-chat.js
node --check src\config\load-config.js
node --test tests\unit\gateway-protocol.test.js tests\unit\config.test.js tests\unit\commands.test.js tests\unit\session.test.js tests\unit\agents.test.js --test-name-pattern "OpenAI-compatible requests include configured provider extra_body|loads bundled config|model command|model use command|reasoning_content|OpenAI-compatible tool continuations|streamed thinking persists"
```

结果：目标测试 `158 pass / 0 fail`；本地构造请求确认当前主模型请求体包含顶层 `thinking.type = "enabled"`。

已知风险：

- 当前 `reasoning_content` 回传链路能覆盖普通长度的主会话和子智能体工具续轮，但超长 reasoning 仍会按既有 OOM 防护只保留尾部预览。若 MiMo 对“完整回传”严格校验，真实超长工具会话仍可能触发 400，需要后续把“模型上下文回传原文”和“UI/日志预览截断”拆成两套存储策略。

## 2026-05-17：版本号统一为 3.0.0 并补齐版本沿革

用户指出版本号长期停留在 `1.1.0`，但项目已经从早期 Claude Code 源码参考/复刻阶段，演进到自研 clean-room 架构、TUI，再到当前 Dashboard/WebUI，应按产品代际重新校准版本号。本次将当前发布线统一为 Ant Code `3.0.0`。

日志查验结论：

- 旧源码版的来源和风险证据保留在 `docs/handoff/2026-04-29-tui-continuation/plan-documents/docs/phase-0/`，其中明确记录旧仓库起点来自 Claude Code 源码参考，且旧仓库应冻结为污染参考实现，不能作为当前源码供体。
- 当前仓库的历史验收材料保留了 `v1.0`、`v1.1`、`v1.2`、`v1.3`、`v1.4` 的阶段记录；这些文件作为时间线证据不改写为 3.0。
- Dashboard/WebUI 从 2026-05-13 起在本文件持续记录，包含 Dashboard 初版、界面优化、富渲染、流式草稿、历史分页、SSE 恢复、会话删除和变更统计等修复。

主要变化：

- `package.json`、`package-lock.json`、`npm-shrinkwrap.json` 根版本统一为 `3.0.0`。
- 新增 `src/version.js`，让 `--version`、工作区信任记录和 MCP `clientInfo.version` 从同一包版本来源读取，避免后续再次出现版本漂移。
- 新增 `docs/deployment/v3.0-dashboard-acceptance.md`，按产品代际说明 `1.x`、`2.x`、`3.x` 的划分和当前 Dashboard 验收口径。
- 更新 README、中文使用说明、安装文档、RC 文档、LLM onboarding 和审计生成脚本，当前发布口径统一为 Ant Code `3.0.0`。

验证：

```powershell
npm version 3.0.0 --no-git-tag-version
npm run audit:sbom
npm run audit:licenses
npm run audit:report
npm run audit:rc
node --check src\version.js
node --check src\cli\index.js
node --check src\cli\tui.js
node --check src\dashboard\sessions.js
node --check src\diagnostics\doctor.js
node --check src\mcp\runtime.js
node src\cli\index.js --version
npm run build:exe
.\dist\ant-code-windows-x64\ant-code.exe --version
```

最终验证补充：`npm run check` 通过，覆盖 syntax、forbidden endpoint、provenance、dependency policy 和 650 个单元/集成测试；Windows x64 分发包已重新生成，`ant-code.exe --version` 输出 `ant-code 3.0.0`，SHA256 为 `FAEE95965AED26028C88C4D2F8635D75692164298FAD32E62A215C05BF1441FE`。

## 2026-05-16：Dashboard 引导后消息与草稿串轮修复

修复 Dashboard 在引导对话后，继续发送下一条消息时偶发旧用户消息重复显示、上一轮“思考”草稿片段提前出现在回复栏的问题。根因是前端每次发送都会重建同一会话的 SSE 连接，而后端新订阅会回放 active session 缓存事件；同时 Dashboard 草稿只按模型 round 分组，上一轮被引导中断后没有最终回复收束，下一轮 round 重新从 1 开始时可能复用旧草稿节点。

主要变化：

- Dashboard runtime 为 active 事件增加单调 `sequence` 和当前 `turnId`，`/api/events` 支持 `after` 游标并写出 SSE `id`，重连时只回放游标之后的新事件。
- Dashboard 前端同一会话继续发送时不再无条件断开并重连事件流；确需重连时带上最后处理过的 sequence。
- Dashboard 草稿按 `turnId + round` 隔离；收到新 turn 或中断事件时会收束当前草稿，避免上一轮草稿混入下一轮回复栏。
- 刷新重开仍在运行的会话时，历史 transcript 只返回当前轮之前的稳定消息，当前轮用户输入、草稿和最终回复统一通过 SSE 游标回放恢复，避免刷新落在收尾窗口时同一轮既来自历史又来自事件流。
- Dashboard 历史展示从模型上下文内存窗口中拆出来：打开会话默认只渲染最近 100 条可见消息，顶部滚到边界后通过 `/api/sessions/:id/transcript?before=...&limit=100` 从 `.transcript` 归档 chunk 继续加载更早记录；运行中的会话会把归档历史和当前内存稳定窗口去重分页，避免长会话聊到后面看不到早期对话，也避免一次性渲染超长 DOM。
- 左侧任务线程新增会话常用操作：可复制会话 ID，非运行中的历史会话可二次确认后删除；后端同步删除 metadata 与 transcript chunk，运行中会话会被 409 拒绝删除。
- 保留“思考”作为可见草稿区域名称；provider thinking/reasoning 仍按既有策略隐藏。

验证：

```powershell
node --check src\core\session.js
node --check src\dashboard\sessions.js
node --check src\dashboard\server.js
node --check src\dashboard\public\app.js
node --test tests\unit\dashboard-events.test.js tests\unit\dashboard-files.test.js tests\unit\dashboard-markdown.test.js tests\unit\dashboard-rich-assets.test.js tests\unit\dashboard-structured-data.test.js tests\unit\dashboard-permissions.test.js tests\unit\dashboard-runtime.test.js tests\unit\dashboard-server.test.js tests\unit\dashboard-ui.test.js tests\unit\storage.test.js
git diff --check
git diff -- src\cli\tui.js src\cli\tui
```

## 2026-05-16：Dashboard 右下角变更统计口径修复

修复 Dashboard 输入框右下角红绿增删数字“反直觉”的问题。根因有两层：文件工具原本直接从简化 unified diff 里数 `+/-` 行，而该 diff 会把旧文件整体标成删除、新文件整体标成新增，导致改一行大文件也可能显示成整文件增删；同时 Dashboard 本轮统计按每次工具调用累计，同一个文件连续编辑会重复累加文件数和中间过程。

主要变化：

- 文件工具新增不暴露正文的行级 `changeStats`，用公共前后缀裁剪加 LCS 计算真实行级增删；超大比较会标记 `approximate`。
- `write_file`、`edit_file` 在工具结果中附带不可枚举的内部变更快照，模型上下文、hook 摘要和持久化 JSON 不会携带文件内容快照。
- `runSessionTurn` 为每轮维护 Dashboard 专用变更 tracker：同一文件从第一次修改前到最新内容计算净变更，文件数按最终仍有差异的唯一文件计数；如果改回原样，本轮统计会回到 `+0 -0 / 0 文件`。
- Dashboard 事件映射保留单次工具变更明细，同时传递本轮净统计；前端右下角优先展示本轮净统计，近似统计会显示“近似”提示。
- 保持 TUI 文件不变。

验证：

```powershell
node --check src\core\session.js
node --check src\tools\diff.js
node --check src\tools\file-tools.js
node --check src\dashboard\events.js
node --check src\core\events.js
node --check src\dashboard\sessions.js
node --check src\dashboard\public\app.js
node --test tests\unit\dashboard-events.test.js tests\unit\dashboard-files.test.js tests\unit\dashboard-markdown.test.js tests\unit\dashboard-rich-assets.test.js tests\unit\dashboard-structured-data.test.js tests\unit\dashboard-permissions.test.js tests\unit\dashboard-runtime.test.js tests\unit\dashboard-server.test.js tests\unit\dashboard-ui.test.js tests\unit\storage.test.js tests\unit\tools.test.js
node --test tests\unit\session.test.js tests\unit\events.test.js tests\unit\tools.test.js
git diff --check
git diff -- src\cli\tui.js src\cli\tui
```

## 2026-05-14：Dashboard 流式草稿轻量渲染

修复 Dashboard 在模型持续生成大量 Markdown 表格、结构化数据或其他富渲染内容时页面卡住的问题。根因是每个 `assistant_draft` 流式增量都会对本轮草稿全文重新执行完整 Markdown 渲染、文件引用扫描、富渲染 hydrate 和贴底滚动；当草稿中不断增长大表格时，浏览器主线程会被反复解析和重建 DOM 占满，导致输入、滚动和“引导对话”点击都无法及时响应。

主要变化：

- Assistant 草稿渲染增加 180ms 节流，多个流式 chunk 合并刷新，避免每个增量都重绘聊天 DOM。
- 草稿阶段新增 Markdown lightweight 模式：表格、fenced 代码块、Mermaid、JSON/YAML/CSV/TSV、块级公式和图片先显示轻量文本预览，不创建完整表格 DOM、不加载 KaTeX/Mermaid/YAML vendor、不执行富渲染 hydrate。
- 草稿阶段跳过普通文本文件引用扫描，最终回复和历史消息仍保留完整文件链接、图片 lightbox、代码复制、公式、流程图、数据表和目录等能力。
- 草稿贴底滚动也纳入节流后的真实渲染点，减少流式期间反复读取和写入 `scrollHeight` 带来的布局压力。
- 最终回复到达后，临时草稿节点会统一收束为一条默认折叠的“思考过程”薄条；点击后只展开轻量草稿正文，不混入工具调用细节，避免图表测试中像出现两份回答。
- Dashboard 前端为 SSE 事件增加 id 级幂等保护，避免 EventSource 重连或重新订阅时后端重放已有事件，导致最终回复被再次追加成两条同样消息。
- “思考过程”折叠时会用最终回复文本过滤同源草稿：如果流式草稿已经等同最终正文，只保留一条薄折叠标题并标记“已汇入最终回复”，不再把完整最终答案塞进折叠详情。
- 当“思考过程”没有额外可展开草稿时，折叠条仍可点击展开，并显示“本轮流式草稿已合并到最终回复，没有额外过程内容。”，避免用户误以为控件失效。
- Markdown 表格分隔行兼容紧凑居中写法，例如 `|:-:|`，避免 Todo List 生命周期表这类最终回复因分隔符短横较少而退化成普通文本。
- 长内容目录不再使用浏览器自动编号的 `<ol>`，改为无序锚点列表并保留标题原文，避免已有编号标题如 `6.8 附录` 被渲染成 `15.6.8 附录`。
- Windows exe 分发包补齐 Dashboard 静态资源：打包脚本会带上 `src/dashboard/public`，Dashboard 服务在 exe 模式下按 `packageRoot` 定位前端资源，避免 API 能启动但首页和 `/assets/*` 返回 404。
- 重新生成 Windows x64 分发包 `dist\ant-code-windows-x64`，包内 Dashboard 资源已包含 SSE 去重、思考过程空态展开、目录编号修复和富内容渲染优化；新 `ant-code.exe` SHA256 为 `8832214F112FEA51006A4F795AAAFCA8519AF1307BCA0631579B3277D4B69D9F`。
- 本次按用户要求暂不加入“大内容保护”或最终回复行数截断；最终消息仍完整富渲染。

验证：

```powershell
node --test tests\unit\dashboard-markdown.test.js tests\unit\dashboard-ui.test.js tests\unit\dashboard-rich-assets.test.js tests\unit\dashboard-structured-data.test.js
node --test tests\unit\dashboard-events.test.js tests\unit\dashboard-files.test.js tests\unit\dashboard-markdown.test.js tests\unit\dashboard-rich-assets.test.js tests\unit\dashboard-structured-data.test.js tests\unit\dashboard-permissions.test.js tests\unit\dashboard-runtime.test.js tests\unit\dashboard-server.test.js tests\unit\dashboard-ui.test.js
node --check src\dashboard\public\app.js
node --check src\dashboard\public\markdown.js
node --test tests\unit\dashboard-markdown.test.js
node --test tests\unit\dashboard-server.test.js
node scripts\check-syntax.js
git diff --check
git diff -- src\cli\tui.js src\cli\tui
npm run build:exe
.\dist\ant-code-windows-x64\ant-code.exe --version
打包后 Dashboard HTTP 烟测：`/`、`/assets/app.js`、`/assets/markdown.js`、`/assets/styles.css` 均返回 200，并确认包内资源包含 `processedEventIds`、`draft-summary-note`、`md-toc-list`。
```

## 2026-05-14：Dashboard Mermaid 错误渲染收口

修复 Dashboard 在浏览器底部反复出现 `Syntax error in text / mermaid version 11.15.0` 的问题。原因是 Mermaid 语法错误时默认会生成一张错误图并插入临时 DOM，外层虽然捕获了异常并在组件内显示“流程图无法渲染”，但临时错误 DOM 仍可能残留到页面底部。

主要变化：

- Dashboard Mermaid vendor 初始化增加 `suppressErrorRendering: true`，让 Mermaid 只抛出解析/绘制异常，不再生成全局错误图。
- 重新构建本地 Dashboard rich-renderers vendor bundle，确保浏览器实际加载的资源也带有该配置。
- Mermaid 失败回退后会把该块标记为已处理，避免同一块重复 hydrate 时反复触发错误流程。
- 新增 `dashboard-rich-assets` 单测，检查源码入口、生成后的 vendor bundle 和前端回退逻辑都保留该防护。

验证：

```powershell
npm run build:dashboard-assets
node --test tests\unit\dashboard-rich-assets.test.js tests\unit\dashboard-markdown.test.js tests\unit\dashboard-structured-data.test.js
node --check src\dashboard\vendor\rich-entry.js
node --check src\dashboard\public\rich-renderers.js
node --check src\dashboard\public\vendor\rich-renderers.js
git diff --check
git diff -- src\cli\tui.js src\cli\tui
```

补充 smoke：临时启动 `ant-code dashboard --port 17411 --no-open`，确认首页、hydrator 和 vendor bundle 正常返回，且 vendor bundle 内容包含 `suppressErrorRendering`，随后通过 `/api/shutdown` 关闭服务。

## 2026-05-14：Dashboard 富渲染路径边界复查

在本地 KaTeX 公式、Mermaid 流程图、JSON/YAML 数据树、CSV/TSV 数据表、图片集 lightbox 翻页、长内容目录已经验收通过后，继续按“类似 PNG 预览回归”的角度做二次排查，重点补齐右侧预览、历史会话、嵌套 Markdown 文档和本地文件链接的边界。

主要变化：

- 切换历史会话或新建任务时，右侧预览区会回到“任务产物会显示在这里”的空状态，避免继续显示上一个会话或工作区的旧文件内容。
- 右侧 Markdown 文档预览现在会把相对图片和本地文件链接按该 Markdown 文件所在目录解析，例如 `reports/report.md` 中的 `images/chart.png` 会预览 `reports/images/chart.png`，不再误按工作区根目录查找。
- Markdown 中指向本机文件的链接会渲染为 Dashboard 文件预览按钮，点击后仍在右侧栏打开；普通 `https://` 链接继续作为外部链接打开。
- 普通文本里的带目录文件引用会保留目录信息，避免 `reports/round-1/final.md` 被截成 `final.md`；同时增加可预览扩展名白名单，避免 `example.com` 这类裸域名被误当成本地文件。
- `data:image` 只允许用于 Markdown 图片语法，不允许作为普通链接直通；空 alt 图片也能进入图片按钮/lightbox 流程。

验证：

```powershell
node --test tests\unit\dashboard-ui.test.js
node --test tests\unit\dashboard-markdown.test.js
node --test tests\unit\dashboard-events.test.js tests\unit\dashboard-files.test.js tests\unit\dashboard-markdown.test.js tests\unit\dashboard-structured-data.test.js tests\unit\dashboard-permissions.test.js tests\unit\dashboard-runtime.test.js tests\unit\dashboard-server.test.js tests\unit\dashboard-ui.test.js
npm run check
git diff --check
git diff -- src\cli\tui.js src\cli\tui
```

补充 smoke：临时启动 `ant-code dashboard --port 17410 --no-open`，确认 `/api/status`、首页、`app.js`、`markdown.js`、`rich-renderers.js`、本地 vendor bundle 和 KaTeX CSS 均返回 200，随后通过 `/api/shutdown` 关闭服务。浏览器自动化连接本次超时，已用 HTTP smoke 覆盖静态资源和服务可用性。

## 2026-05-14：Dashboard PNG 预览与会话工作区修正

修复 Dashboard 右侧 PNG 产物预览回归：右侧栏现在只收集真实存在的文件，历史会话打开时会重新带回该会话的产物列表，文件预览接口支持通过 `sessionId` 使用会话自身的工作区路径解析，避免从不同项目文件夹进入同一个 WebUI 后按 Dashboard 启动目录查错文件。聊天 Markdown 中的相对图片也统一改写为本机 `/api/files/raw` 图片通道，并带当前会话上下文。

补充边界说明：PNG/JPG 预览属于浏览器侧文件展示，不等于模型已经获得图片视觉输入。当前模型如果只收到图片路径而没有文本内容或视觉工具结果，仍可能出现“模型本轮没有返回可展示正文。”这类网关空正文兜底；后续若要“根据图片内容对话”，需要专门接入图片读取/视觉输入能力。

验证：

```powershell
node --check src\dashboard\files.js
node --check src\dashboard\sessions.js
node --check src\dashboard\server.js
node --check src\dashboard\public\app.js
node --test tests\unit\dashboard-runtime.test.js
node --test tests\unit\dashboard-files.test.js tests\unit\dashboard-server.test.js
git diff --check
git diff -- src\cli\tui.js src\cli\tui
```

## 2026-05-14：Dashboard 排队取消交互修正

修正 Dashboard 运行中队列只能新增、不能撤回的问题。队列面板现在会在未开始的排队项旁显示“取消”，后端新增排队项取消接口，取消后会同步刷新队列和引导状态；已经进入当前轮次的任务仍通过发送按钮的“运行中/中断”处理。

验证：

```powershell
node --test tests\unit\dashboard-runtime.test.js tests\unit\dashboard-server.test.js
node --check src\dashboard\sessions.js
node --check src\dashboard\server.js
node --check src\dashboard\public\app.js
```

## 2026-05-14：Dashboard 报告型富渲染增强

用户确认下一轮 WebUI 渲染不走“代码 diff 审阅增强”方向，而是面向实验室报告、公式、流程、结构化数据和图片结果阅读。按 `docs/plans/completed/dashboard-report-rendering-plan-2026-05-14.md` 的 Stage 0-7 执行并归档，补齐 Dashboard 报告型渲染能力，仍不修改 TUI。

主要变化：

- Dashboard Markdown 解析增加行内/块级数学公式、Mermaid fenced block、JSON/YAML/CSV/TSV 数据 fenced block，以及长回复目录 metadata。
- 新增本地 Dashboard 富渲染 bundle：`katex`、`mermaid`、`yaml` 作为 npm 依赖进入锁文件；`scripts/build-dashboard-assets.js` 用本地 `esbuild` 生成 `src/dashboard/public/vendor/` 资源，不使用 CDN。
- 公式通过 KaTeX 本地渲染，失败时保留原公式文本；块级公式使用深灰报告组件和局部横向滚动。
- Mermaid 图通过本地 bundle 渲染为深灰主题图表，支持原文切换和失败回退，安全级别使用 strict。
- JSON/YAML 数据渲染为可展开数据树；CSV/TSV 渲染为数据表并提供“复制为 TSV”；右侧 `.json`、`.yaml`、`.yml`、`.csv`、`.tsv` 文件预览从普通文本升级为“数据预览”。
- 多张 Markdown 图片会形成轻量图片组；右侧图片文件和聊天图片共用 lightbox，支持上一张/下一张、图片计数、键盘方向键和 Esc。
- 长回复和右侧 Markdown 文档在标题较多时生成折叠目录，点击后平滑跳转，并用 `scroll-margin-top` 避免被顶部状态条遮挡。
- 新增 `src/dashboard/public/structured-data.js`、`src/dashboard/public/rich-renderers.js`、`src/dashboard/vendor/rich-entry.js`，避免继续把富渲染逻辑塞进 `app.js`。

验证：

```powershell
npm run build:dashboard-assets
node --test tests\unit\dashboard-markdown.test.js tests\unit\dashboard-structured-data.test.js tests\unit\dashboard-files.test.js tests\unit\dashboard-ui.test.js
node --check src\dashboard\public\app.js
node --check src\dashboard\public\markdown.js
node --check src\dashboard\public\rich-renderers.js
node --check src\dashboard\public\structured-data.js
npm run check:dependencies
npm run check
npm run verify:readiness
git diff -- src\cli\tui.js src\cli\tui
```

补充说明：

- 新增依赖后同步更新 `package-lock.json` 和 `npm-shrinkwrap.json`，依赖策略检查通过。
- 计划档案已归入 completed；本地 Edge smoke 已覆盖公式、Mermaid、数据预览、图片集和目录，TUI diff 为空。

## 2026-05-13：Dashboard WebUI 初步界面优化完成

在第一版 Dashboard 跑通后，继续根据实验室同学的使用反馈做视觉和交互收口，目标是让 WebUI 更像一个本机工作台，而不是厚重的后台管理页，同时保持与 TUI 的运行时和会话历史共用。

主要变化：

- 中央聊天区顶部去掉重复的“本机工作台/会话标题”大标题，改为约 42px 的薄状态栏，只保留“本地通用智能体”和空闲/运行中/等待/失败/完成状态。
- 会话标题继续由左侧线程列表承担，中央区专注对话内容；旧 `session-title` DOM 和对应 JS 依赖已移除。
- Todo/Plan 进度改为固定在薄状态栏下方的细进度条，聊天内容滚动时不会消失；点击可展开完整 Todo/Plan 明细，聊天区里的任务进度卡仍保持摘要展示。
- 运行中状态点统一改为绿色，顶部状态、输入栏动态提示、TodoList 进行中标记保持同一语义颜色；等待为黄色，失败为红色，完成为柔和绿色。
- 整体背景从纯深灰调整为石墨黑、冷青灰和深炭灰的克制渐变；右侧文件预览栏的副标题、文件 meta 和空状态灰字提亮，增强可读性。
- 空状态主标题从“描述你想完成的实验室任务”改为“我将全力配合你的工作”，让 WebUI 初始画面更像协作伙伴而不是表单说明。
- 顶部“本地通用智能体”提示用非技术文案表达本机语境，避免向非编程用户直接暴露 `127.0.0.1`；完整本机访问语义保留在 hover 提示和启动信息中。
- TodoList 固定细条放在聊天标题区域下方、聊天滚动区上方，既能让用户看到任务进度，又不把过程细节堆进聊天记录；展开态展示完整 Todo/Plan。
- 用户消息保持独立短气泡，Ant Code 大段回复、临时草稿、最终回复和折叠过程记录继续区分显示，降低长对话中寻找用户输入的成本。
- 右侧产物栏保留图片、文本、Markdown、PDF 第一版预览范围；图片支持大图 lightbox，长 Markdown/文本有独立滚动文档容器。
- 本次仍只修改 Dashboard 前端：`src/dashboard/public/app.js`、`src/dashboard/public/index.html`、`src/dashboard/public/styles.css`，不改 TUI。

维护文档同步：

- `PROJECT_CHANGELOG.zh-CN.md` 追加本条界面优化记录，并整理此前 misplaced 的 `2026-05-01：OpenCode 式需求确认和工作流侧栏对齐` 条目顺序，使 2026-05-01 位于 2026-04-30 之前。
- `LLM_ONBOARDING.md` 更新当前产品状态：`ant-code` 默认仍是 TUI，`ant-code dashboard` 是本机 WebUI，二者共用核心 session runtime、权限引擎、上下文压缩和 `.lab-agent/sessions` 历史。
- 大模型/网关对接文档更新到当前程序状态：`docs/specs/lab-model-gateway-protocol.md`、`docs/specs/lab-model-gateway-compatibility-matrix.md`、`docs/deployment/model-adapter-gateway-readiness.md`、`docs/deployment/lab-gateway-rollout-checklist.md` 均补齐 Dashboard/TUI 共用运行时、OpenAI-compatible 模式不再默认发送 `tool_choice: "auto"`、客户端会带 `x-session-affinity` 作为会话亲和提示、SSE/NDJSON 流式 record 必须到达即派发，以及 Dashboard 草稿流式显示依赖该行为。
- 复查 2026-05-13 本地 Git 历史：`0ea8c95 完成 Dashboard WebUI 初版`、`4e18a0b 优化 Dashboard 初版界面`、`a680317 补充 Dashboard 优化维护记录` 均已有对应日志；本次补齐的是顺序整理与大模型对接/部署文档同步。

验证：

```powershell
node --check src\dashboard\public\app.js
node --test tests\unit\dashboard-events.test.js tests\unit\dashboard-runtime.test.js tests\unit\dashboard-ui.test.js
node --test tests\unit\dashboard-events.test.js tests\unit\dashboard-files.test.js tests\unit\dashboard-markdown.test.js tests\unit\dashboard-permissions.test.js tests\unit\dashboard-runtime.test.js tests\unit\dashboard-server.test.js tests\unit\dashboard-ui.test.js
node scripts\check-syntax.js
git diff --check
```

补充复核：

- 临时端口启动 Dashboard，确认页面、CSS 和新文案可正常加载。
- `git diff -- src\cli\tui.js src\cli\tui` 为空，确认未改动 TUI。
- 已本地提交：`4e18a0b 优化 Dashboard 初版界面`。
- 维护文档补充提交：`a680317 补充 Dashboard 优化维护记录`；本次顺序整理和模型对接文档同步会单独提交留档。

## 2026-05-13：新增本机 Dashboard WebUI 入口

用户反馈实验室中不少成员不适应 TUI，希望提供更干净、美观的 WebUI，同时不能影响现有 `ant-code` 默认 TUI。新增 `ant-code dashboard` 作为本机 Dashboard 入口，默认 `127.0.0.1:7410`，端口冲突时自动递增，启动后自动打开浏览器，且第一版拒绝 `0.0.0.0` 等非回环地址。

主要变化：

- 新增 `src/dashboard/`：本机 HTTP 服务、共享会话读取、任务事件流、权限审批桥接、文件预览和深灰色三栏前端。
- `ant-code` 默认行为保持不变；`ant-code tui` 仍显式启动 TUI。
- Dashboard 复用核心 session runtime、工具权限引擎和 `.lab-agent/sessions`，不创建独立历史目录。
- 工具调用在 WebUI 中默认折叠为活动行；模型 thinking 正文不展示，只显示“正在分析任务”等状态。
- 运行中的“正在分析 / 正在生成 / 正在请求模型”不再堆叠到聊天窗口，改为输入栏上方固定动态提示；子智能体运行时显示独立动态 chip，完成后只保留折叠过程记录。
- 可见 assistant 正文流现在会按模型轮次显示为聊天区临时草稿卡，避免用户长时间只能等待最终消息；最终回复到达后，临时草稿统一折叠为“思考过程”薄条，主对话突出最终回复。provider thinking/reasoning 仍然不展示正文，只保留状态提示。
- 修复 lab-agent-gateway SSE/NDJSON 解析器此前“读完整个响应后再派发事件”的行为，改为完整 record 到达即派发，确保 Dashboard 草稿是真实时流式显示，而不是最终前瞬间补出来。
- Todo/Plan 进度在聊天区以轻量任务进度面板展示，避免界面过度精简后变成黑箱；面板会随 `todo_write`、`plan_update` 和最终同步更新同一个实例。
- Dashboard 视觉从硬线条三栏分割调整为深灰工作台：外层留白、弱边框、柔和面板层级，减少后台管理系统式割裂感；品牌 A、顶部“本机工作台”和进度强调色从偏绿色改为更克制的大理石灰系。
- 网页中提供计划确认、工作区权限、完全访问三层权限模式；审批弹窗位于输入栏顶部，支持允许一次、本会话允许、拒绝和取消。
- Dashboard 现在接入现有 `ask_user` 需求核对能力：模型需要澄清需求时，网页输入栏顶部会显示独立核对面板，支持选项、补充文本、确认和取消；回答会作为工具结果回到同一轮任务，不与权限审批混用。
- Dashboard 补齐运行态交互：发送按钮在任务运行中显示为“运行中”，点击即中断当前任务；运行中继续输入并回车会进入当前会话队列，不再被 409 拒绝；队列栏提供“引导对话”按钮，用当前输入生成 guide continuation 并中断当前轮次后优先继续。
- Dashboard 修复排队后的引导入口：回车排队导致输入框清空时，“引导对话”仍可点击并接管队首排队消息；排队项旁增加轻量“引导”按钮，可指定某条队列消息转为引导且不会重复执行原排队项。
- Dashboard 优化“引导对话”点击反馈：点击后队列栏立即显示“正在登记/引导已接管/正在按引导继续”等状态，避免用户误以为卡住；这些反馈保持在输入栏上方，不向聊天记录堆叠提示。
- Dashboard 权限模式视觉与 TUI 风险语义对齐：工作区权限使用黄色标记，完全访问使用红色标记，保持深灰基调下的克制强调。
- Dashboard 补齐工作区信任：首次进入 WebUI 会在输入栏上方要求确认当前本机工作区，高敏模式下按当前 Dashboard 进程确认；未信任前不会启动模型 turn。
- Dashboard 补齐上下文操作确认：清空上下文和压缩上下文都改为网页内确认面板，确认后调用与 TUI 相同的 `clearSessionContext` / `compactSessionContextWithModel` 能力。
- 右侧文件栏支持图片、文本、Markdown、代码、PDF 预览；图片预览可点击打开大图层，并支持遮罩、关闭按钮或 Esc 退出；Office/二进制文件第一版显示文件卡片和打开入口。
- Dashboard 补齐 Markdown 渲染：Ant Code 回复和右侧 `.md` 预览支持标题、列表、代码块和 pipe table，表格以网页表格展示并保留横向滚动，不再把 `| --- |` 原文直接铺给用户。
- Dashboard 对话区过滤内部消息：历史 transcript 只展示 `user` 和 `assistant`，不再把 system/developer/tool 等给 Ant Code 的系统上下文当成用户聊天内容显示。
- Dashboard Markdown 第一批富渲染补齐：支持 Markdown 链接、图片内嵌和点击放大、任务列表、引用块、代码块复制按钮和 diff/patch 高亮；用户消息仍保持偏纯文本展示。
- Dashboard 会话现在在模型 system context 中显式标记 `Client surface: dashboard WebUI`，并移除全局提示词里的 TUI-only sidebar/自动继续措辞；TUI、chat、print 入口仍通过同一核心 session runtime 使用各自客户端语义。
- 右侧 Markdown/文本预览改为明确的独立滚动文档容器，并统一使用深灰细滚动条，长文档可以直接拖动查看完整内容。
- Dashboard 提供显式关闭路径：网页左下角“关闭 Dashboard”确认后会停止本机 WebUI 服务；前台终端也可以用 `Ctrl+C` 关闭。
- 新增 Dashboard 单元测试覆盖 CLI 参数、本机 host 限制、端口递增、事件映射、权限映射、拒绝写入不落盘、共享 session metadata 和文件预览边界。

验证：

- `npm run check` 通过，575 个测试全部通过。
- 复核确认没有修改 `src/cli/tui.js` 和 `src/cli/tui/`。
- 针对 UI 修正补充验证：dashboard 相关 23 个单元测试通过；真实流式 smoke 确认运行中聊天区 activity 卡为 0，完成后 live 提示隐藏，只保留用户消息、折叠过程记录和最终回复。
- 针对进度面板补充验证：`dashboard-runtime` 新增 workflow snapshot 测试通过；真实页面 smoke 确认聊天区只有 1 个任务进度面板，并从 `0/3` 更新到 `3/3`。
- 针对草稿流式补充验证：新增 gateway SSE 回归测试，确认流未关闭前已经收到 `text_delta`；真实页面 smoke 确认中途出现 1 张草稿卡，最终草稿卡归零并收束为默认折叠的“思考过程”。
- 针对需求核对补充验证：`dashboard-runtime` 覆盖 `ask_user` 正常确认和取消后继续任务，`dashboard-server` 覆盖 `/api/questions/:id` 回写路由。
- 针对新增运行态交互补充验证：`dashboard-runtime` 覆盖工作区信任 gate、运行中排队、中断当前 turn、guide 排队并中断、清空/压缩上下文；`dashboard-server` 覆盖 `/api/trust`、`/api/turns/interrupt`、`/api/turns/guide`、`/api/context/clear`、`/api/context/compact`。
- 针对 Markdown 渲染补充验证：`dashboard-markdown` 覆盖 pipe table、代码块防误解析、HTML 转义和列表分组；dashboard targeted tests 27 个全部通过。
- 针对 WebUI 对话可见性和富渲染补充验证：`dashboard-ui` 覆盖内部 role 过滤，`dashboard-markdown` 覆盖链接/图片/任务列表/引用块/unsafe URL 拦截/diff 高亮。
- 针对 Dashboard 被误判为 TUI 的提示词问题补充验证：`context` 覆盖 dashboard/TUI client surface 文案，`dashboard-runtime` 覆盖发给模型的 system message 和 metadata.clientSurface；相关 60 个 context/dashboard/session 单测通过，`src/cli/tui.js` 和 `src/cli/tui/` 无 diff。

## 2026-05-08：TUI 流式输出合批刷新，降低长跑 V8 heap 压力

### 补充修正：Mimo OpenAI-compatible 首轮请求兼容性

- 用户在切换小米 Mimo 后观察到：历史会话中途恢复基本可用，但新会话首轮偶发 `HTTP 500 KVTransferError / WaitingForInput`、`GATEWAY_STREAM_INTERRUPTED` 或长时间无 token；同一工作区的长历史会话反而因 provider 缓存命中较高更稳定。
- 对照本地 `opencode` 实现后确认：opencode 通过 AI SDK 发送 OpenAI-compatible 请求，普通首轮带 `tools` 但不会强制发送 `tool_choice: auto`；同时会通过 header 传会话亲和信息。
- 修复：
  - OpenAI-compatible 请求构造不再在存在 tools 时默认写入 `tool_choice: "auto"`；只有调用方显式传 `toolChoice` 时才发送该字段，降低兼容网关走异常 tool-routing/decode 路径的概率。
  - 网关请求新增 `x-session-affinity: <sessionId>` header，帮助兼容网关把同一会话路由到稳定亲和后端。
  - 网关客户端把 Mimo `KVTransferError` / `WaitingForInput` 类 HTTP 5xx、以及流式读取中断纳入现有温和重试链路；重试不改变 messages/tools/tool results，不截断模型上下文。
  - `gateway_retry` 事件新增 `stage`，TUI 中可看到是 `fetch`、`http`、`read_body` 还是 `parse_body` 阶段重试。

### 补充修正：Mimo 下子智能体并发与任务栏状态稳定性

- 用户观察到：Mimo 历史会话中有时一次拉起过多子智能体，右侧任务栏数量和主聊天框中的子任务卡片对不上，后台子智能体也更容易卡住。
- 修复：
  - 父会话同批只读 `agent_run` 并行上限改为 `agents.orchestration.maxParallelReadonlyAgentRuns` 配置驱动；Mimo 当前配置为 2，DeepSeek 备份配置为 3。
  - 系统提示不再硬编码“1-2”或“2-3”个子智能体，而是读取当前只读并行预算，要求模型按任务独立性和配置预算派发。
  - 任务组 store 对同一个 `groupId` 的 `ensureGroup/updateGroup` 加同进程串行合并，避免多个后台子任务几乎同时启动/完成时覆盖彼此的 `taskIds`、进度或唤醒状态。
  - 父会话在同一批 `agent_run` 中检测重复 `taskId`，自动给后续重复项加后缀，避免主界面生命周期卡片互相覆盖导致“只看到一个子任务”。
- 该修复只调整编排与任务记录一致性，不截断 messages/tool results，不减少模型可见上下文。

### 补充验证

```powershell
node --check src\model-gateway\client.js
node --check src\model-gateway\openai-chat.js
node --check src\core\session.js
node --check src\cli\tui.js
node --check src\agents\task-group-store.js
node --check src\agents\orchestration-config.js
node --check src\config\load-config.js
node --check src\context\builder.js
node --test tests\unit\gateway-protocol.test.js tests\unit\gateway-health.test.js
node --test tests\unit\agent-task-group-store.test.js tests\unit\context.test.js
node --test tests\unit\config.test.js tests\unit\session.test.js
```

### 补充修正：压缩后长跑仍触发 OOM，grep 扫描误读模型权重

- 用户在 Mimo 长任务压缩后继续运行，仍看到 Node/V8 heap 接近 4GB 后 OOM。
- 复查现场会话后确认：最新 session metadata 只有约 158KB，最近 task JSON 也只是十几到几十 KB；上下文压缩已执行，`207 -> 8` 表示旧模型上下文被总结、近期消息保留，并不是压缩未生效。
- 真正高风险路径在工具执行阶段：子智能体任务要求对 `AntSleap/` 做全量 grep，而测试项目下存在约 3.64GB 的 `.pt/.pth/.db` 等模型权重/数据文件；旧 `grep` 会把未排除扩展名的文件用 `readFile(..., "utf8")` 整文件读入并 `split` 成行，扫描过程中即可把 V8 堆推到上限，尚未进入模型请求或压缩链路。
- 修复：`grep` 改为逐行流式读取文本文件，并跳过 `.pt/.pth/.db/.onnx/.safetensors/.npy/.npz/.pkl` 等明确二进制/模型/数据扩展名，同时加入 4KB NUL 头部探测；源码文本的匹配行仍完整返回给模型，不改变工具结果进入模型上下文的策略。

### 补充验证

```powershell
node --check src\tools\file-tools.js
node --test tests\unit\tools.test.js
```

### 补充配置：DeepSeek 额度耗尽后临时切换到小米 Mimo v2.5

- 用户表示 DeepSeek 额度已耗尽，需要先保存一份 DeepSeek 配置，等额度恢复后继续测试 DeepSeek。
- 已将当前 DeepSeek 仓库配置备份到 `config/lab-agent.deepseek-backup.json`。
- 当前 `lab-agent.config.json` 临时切换为小米 Mimo：
  - `modelAlias: mimo-v2.5`
  - `models` 只保留 `mimo-v2.5`
  - `agents.modelTiers.cheap/default/strong` 全部指向 `mimo-v2.5`，主智能体和子智能体使用同一模型。
  - `lab.gatewayUrl` 指向小米 OpenAI-compatible chat completions endpoint。
  - `contextTokens/maxTokens/resumeMaxTokens` 按 Mimo v2.5 的 400k 口径配置。
- 本日志不记录 API key。

### 补充验证

```powershell
node -e "JSON.parse(require('fs').readFileSync('lab-agent.config.json','utf8')); console.log('json ok')"
```

### 补充修正：跨 turn 首轮请求缓存命中突然跌到几千 token

- 用户在长会话中发现没有换话题时，provider 缓存命中从约 `300k/312k` 突然跌到 `5.4k/312k`，导致该轮首个请求产生大额未命中 token。
- 复查现场会话 `aa490240-2fe9-4020-babc-8cb5d625946c`：异常轮第 1 个 gateway 请求为 `297398 prompt / 5376 cached`，同一轮后续工具续轮立即恢复到 `298833 / 298240 cached`、`311660 / 311168 cached`。
- 根因不是 provider 缓存失效，而是 Ant Code 把会随文件改动/验证次数变化的 `workflow context` 作为独立 system 消息插在完整历史之前。上一轮工具或验证改变 workflow 统计后，下一轮首请求的历史前缀被动态 system 块打断，provider 只能命中最前面的 system prompt。
- 现在 `workflow context` 仍会进入模型上下文，但改为附加到当前 user 消息的第一段，完整历史消息保持紧跟 system/compact summary 之后，从而保留跨 turn 的大段稳定前缀缓存。
- 新增回归：带 workflow changes/validations 的请求必须保持 `system + 历史 user/assistant + 当前 user` 顺序，workflow 摘要只出现在当前 user 消息内。

### 补充验证

```powershell
node --check src\core\session.js
node --test tests\unit\session.test.js
node --test tests\unit\context-window.test.js tests\unit\tui-command-panels.test.js
```

### 补充修正：退出后重新进入会话上下文缩水

- 用户发现同一条长会话在运行中模型输入可达到 100k-200k 量级，但退出后通过 `/sessions` 重新进入，下一轮模型输入只剩 30k-40k 左右。
- 复查 `D:\confirm-project\LBJ-workspace\Formica-Flow-confirm` 的现场会话后确认：完整 transcript archive 仍在磁盘上，并不是落盘丢失；缩水来自 resume 链路单独使用旧上限 `resumeMaxMessages=200`、`resumeMaxTokens=200000`、`resumeMaxBytes=1000000`。
- 现在 resume context 默认与 active context 预算对齐：仓库配置调整为 `resumeMaxMessages=100000`、`resumeMaxTokens=500000`、`resumeMaxBytes=2000000`。
- 配置加载增加归一化保护：如果项目旧配置仍写着更低的 resume 上限，会自动抬到 active context 预算；只有显式环境变量 `LAB_AGENT_CONTEXT_RESUME_MAX_*` 会作为调试开关保留更小 resume 预算。
- 新增回归覆盖：旧项目低 resume 配置会被抬升；306 条 transcript archive 在 500k/2MB active budget 内退出重进后完整恢复。

### 补充验证

```powershell
node --check src\config\load-config.js
node --check src\core\session.js
node --test tests\unit\config.test.js tests\unit\session.test.js
```

### 补充修正：中断后 resume 触发 OpenAI-compatible 400

- 用户中断一轮回复后退出并重进，下一轮出现 `GATEWAY_HTTP_ERROR: HTTP 400`。现场 provider 错误为：`assistant message with 'tool_calls' must be followed by tool messages`。
- 根因是中断发生在 assistant 已返回 tool_calls、但对应 tool 结果尚未全部写回时，模型上下文持久化留下了半截 assistant tool-call 链；恢复会话后 OpenAI-compatible 协议拒绝这个非法消息序列。
- 新增上下文修复：保存、恢复、构造下一轮模型输入前都会检查 assistant tool_calls 是否紧跟完整 tool messages。完整链路保留；悬空链路只移除 toolCalls 字段，保留 assistant 可见文本和 thinking，避免丢上下文。
- 补充回归：构造带悬空 tool call 的 interrupted metadata，resume 后下一轮请求不再带非法 tool_calls，但仍保留 thinking。

### 补充验证

```powershell
node --check src\core\session.js
node --test tests\unit\session.test.js
node --test tests\unit\gateway-protocol.test.js tests\unit\storage.test.js
```

### 补充修正

- 合批刷新后发现状态栏会在“生成回答”和“思考中”之间来回跳动。原因是正文已经开始后，后续 thinking-only 批次仍会覆盖 activity status。现改为一旦进入回答阶段，后续 thinking 批次只累计字节和预览，不再把状态拉回“思考中”。
- 继续收口流式状态来源：`gateway_stream_start` 不再把 activity status 改成“流式输出”；stream 顶部标签优先按已有正文/thinking 判断，避免“接收中/思考中/生成回答”反复闪烁。
- 子智能体右侧任务栏已有多个任务时，主聊天区可能只看到部分任务卡片。现改为任务记录刷新时同步补齐当前会话的 running/queued 子任务卡片，并更新已有任务卡片，避免只依赖 `agent_run` 启动事件。
- 以上仍只影响 TUI 显示层，不改变模型上下文、工具结果或 thinking 回传。

### 补充验证

```powershell
node --check src\cli\tui.js
node --test tests\unit\tui-frame.test.js tests\unit\tui-components.test.js tests\unit\tui-command-panels.test.js
node --test tests\unit\session.test.js tests\unit\tools.test.js tests\unit\agents.test.js
```

### 补充修正：agent_run 缺 query 时不再让任务详情 ENOENT

- 用户在新会话测试子智能体时遇到一次失败：`Missing required input field: query`，随后第二次子智能体立刻成功。现场判断为模型第一次生成 `agent_run` 参数时缺了必填 `query`，不是 DeepSeek/Mimo 路由污染，也不是子智能体实际启动后失败。
- 之前 session 层会先为 `agent_run` 分配 `taskId` 并在 TUI 展示任务卡片，但工具输入校验失败发生在 `runSubagent()` 之前，因此不会写 `.lab-agent/tasks/<taskId>.json`，双击详情时又会出现 `ENOENT`。
- 现在 `agent_run` 会接受常见别名 `message` / `prompt` / `task` / `instruction` / `instructions` 作为 `query`，降低模型把参数名写偏导致失败的概率。
- 如果 `agent_run` 仍然缺少必填字段，但已经有 `taskId`，运行时会写入一条 `failed` 任务记录，TUI 详情可以正常显示“子智能体未启动”和输入校验失败原因，不再误报任务记录读取失败。
- 已确认仓库源码与全局 npm 安装包中的 `src/tools/runtime.js` 一致；新启动的 `ant-code` 会吃到该修复。

### 补充验证

```powershell
node --check src\tools\runtime.js
node --test tests\unit\tools.test.js
```

### 补充修正：Mimo reasoning-only 被长度截断时自动追正文

- 用户在新会话中看到占位提示：`模型本轮没有返回可展示正文。已收到 116506 字节 reasoning/thinking 流，按隐私策略未展示。`
- 复查现场会话 `24edeaf2-bdf1-42b8-b60a-47068219a361` 的最后一轮：`stopReason=length`，`completion_tokens=32768`，其中 `reasoning_tokens=32678`，`textBytes=0`，`thinkingBytes=116506`。这说明 Mimo 本轮几乎把全部输出预算花在 reasoning/thinking 中，直到长度上限截断，尚未产出普通正文；不是 TUI 把正文藏了，也不是上下文恢复缩水。
- 关闭终端后复盘 thinking 预览，确认其中出现重复 planning 自循环：同一句 `Let me now create the entries and edit the files.` 重复 136 次，若干格式检查和 changelog 计划句重复 40-90 次。因此这次不是进程层面的无限循环，而是 provider reasoning 内部自循环，最终被 `length` 截断。
- 保持通用 output health check 默认关闭，避免普通短回答触发额外网关请求；但新增强制恢复条件：当最终轮 `无工具调用 + textBytes=0 + thinking>=1KB + stopReason=length/max_tokens/token_limit` 时，自动追加一轮本地修复提示，要求模型立刻给用户可见正文。
- 新增重复 thinking 检测：当 hidden thinking 内存在高频重复段且没有正文时，记录 `repetitive_thinking_loop`，同样触发一次本地修复提示，要求模型跳出循环直接回答。
- 该修复不展示 hidden thinking，不改动工具结果/文件读取结果进入上下文的策略，只是在确定坏输出时多追一轮最终正文，并在 `metadata.outputHealth[]` 中记录 `reasoning_only_length` / `repetitive_thinking_loop`。
- 已确认当前仓库源码与全局 npm 安装包中的 `src/core/session.js` 是同一份内容；新启动的 `ant-code` 会吃到该修复。

### 补充验证

```powershell
node --check src\core\session.js
node --test tests\unit\session.test.js
```

### 补充配置：Mimo 自动压缩阈值下调到 256k

- 用户实测发现小米 `mimo-v2.5` 与 DeepSeek 行为不同，长上下文会更明显影响注意力和最终收束，因此不适合继续按接近 400k 上限才触发自动压缩。
- 保持 Mimo 硬上下文上限和 resume 预算为 `400000` tokens，避免恢复链路缩水；仅将 `context.promptCompactRatio` 设为 `0.64`，让自动压缩在约 `256000` tokens 时触发。
- 这样仍保留 400k 作为异常长任务/恢复/硬预算空间，但普通长会话会更早摘要，降低 Mimo 在 300k+ 上下文中注意力漂移和 reasoning 自循环的概率。
- 配置校验新增 `context.promptCompactRatio` 合法性检查，必须是 `0-1` 之间的小数，避免误写成 `64` 或其他无效值。

### 补充验证

```powershell
node -e "const fs=require('fs'); const c=JSON.parse(fs.readFileSync('lab-agent.config.json','utf8')); console.log(c.context.maxTokens * c.context.promptCompactRatio, c.context.maxTokens, c.context.resumeMaxTokens)"
node --check src\config\load-config.js
node --test tests\unit\config.test.js
```

### 背景

用户在 `D:\confirm-project\LBJ-workspace\Formica-Flow-confirm` 进行高强度长任务压测时，再次观察到 Node/V8 在接近 4GB heap limit 处触发 `JavaScript heap out of memory`。复查现场会话 metadata 约 646KB、当前模型上下文约 414KB，最后一轮 provider prompt 约 211k tokens 且缓存命中约 210k tokens，说明恢复工具结果和 thinking 进入模型上下文的链路生效，但落盘数据量本身远不足以解释 4GB 堆占用。

### 判断

- 这次 OOM 更可能来自 TUI 运行态高频状态更新：流式 `assistant_delta` / `assistant_thinking_delta` 每个小片段都会触发 React state 更新和重渲染。
- AntEvent v2 的 token 级 `assistant_text_delta` / `assistant_thinking_delta` 也会逐条走 `reduceAntEvent()`，每次 clone 当前事件状态，长跑时会放大 heap 压力。
- 这次修复只处理显示层运行态，不重新压缩模型上下文，不截断工具结果、grep/read 文件结果，也不移除 thinking 回传。

### 改动

- TUI 新增 50ms 流式 delta buffer，把高频正文和 thinking 片段合批后再刷新 `stream` 和 activity 计数。
- 在工具开始/结束、gateway 边界、最终回答、中断、错误、turn complete 等边界事件前同步 flush buffer，避免最后一批流式内容丢失。
- AntEvent v2 对 token 级正文/thinking delta 不再逐条更新 `antState`；仍保留总事件计数，结构化边界事件继续正常 reduce。
- `assistant_final` 改为直接使用同步 flush 后的 stream 快照，避免依赖 React state 异步刷新。

### 验证

```powershell
node --check src\cli\tui.js
node --test tests\unit\tui-frame.test.js tests\unit\tui-format.test.js tests\unit\tui-components.test.js
node --test tests\integration\ant-event-output.test.js tests\unit\event-reducer.test.js tests\unit\events.test.js
```

### 后续风险

- 当前修复降低的是 TUI 高频渲染/状态 clone 压力；如果继续把单进程长跑到数百轮、并同时打开大量子智能体，仍建议观察 Node 工作集是否会出现新的非流式增长点。
- 后续如再出现 OOM，应优先采样 heap snapshot 或对 TUI render/update 次数加轻量计数，而不是回退模型上下文保留策略。

## 2026-05-08：thinking 重新进入模型上下文与 resume 链路

### 背景

用户确认希望把 `thinking` 重新接回上下文，不只是保留工具结果正文，还要保留模型在工具调用前后的推理痕迹，这样后续 turn 可以继续沿着同一条工具链路走，减少重复跑文件 / grep / fetch 的概率。

### 改动

- `session.messages` 在构造下一轮模型输入时不再剥离 `thinking`。
- `contextMessages` 和 transcript 持久化也保留 `thinking`，resume 后可继续回传。
- 上下文预算估算同步按完整消息计算，避免 thinking 回流后仍按旧预算低估。
- TUI 仍按既有折叠策略展示 thinking，显示层没有额外改成强制展开。

### 验证

- 流式 thinking 回归改成验证：落盘后 resume 能恢复 thinking，下一轮 OpenAI-compatible 请求会带上对应的 `reasoning_content`。
- `npm run check` 仍需通过，确保上下文估算和持久化改动没有破坏其他路径。

## 2026-05-08：turn 结束后保留工具消息进入下一轮上下文

### 背景

长任务压测里确认过一个更深的链路问题：工具结果在单轮执行期间会进入临时 `messages`，但 turn 结束后只持久化了 user + final assistant，`tool` 消息没进后续上下文和 resume 数据。这样下一轮会话虽然还在同一进程里，但模型输入会回落，刚读过的文件证据和工具调用链会断开，缓存命中也被白白浪费。

### 改动

- `appendSessionMessages()` 现在会把本轮真实新增的 user / assistant(tool-call) / tool / final assistant 一起写回 `session.messages` 和 transcript。
- `tool` 角色消息现在可以被持久化和恢复，`toolCallId` / `name` 会一并保留。
- `contextMessages` 改为保留工具调用链，恢复会话时可以直接继续吃到上轮工具证据。
- 归档的 transcript chunk 也按同样规则保留工具消息，避免 resume 只剩正文不剩工具链。

### 验证

- 新增单测覆盖“下一轮请求带上 tool 消息”和“resume 后仍能恢复 tool 证据”。
- 尚未做更大规模长跑压测，但这次修复针对的是 turn 结束后的持久上下文漏写，路径已经对齐。

## 2026-05-08：恢复工具、读文件、grep/web fetch 结果全量进入模型上下文

### 背景

用户在长会话压测中发现：此前为降低 TUI/运行时内存占用而引入的截断和 in-flight 工具消息压缩，不只是影响显示层，也会让模型下一轮拿不到完整工具结果。用户明确要求：TUI 展示优化可以做，但不能牺牲模型上下文；工具结果、读取文件结果、grep 结果、web fetch 结果默认必须完整进入模型上下文。

### 改动

- `serializeToolResult()` 不再按 `maxBytes` 截断工具 JSON；序列化结果默认完整进入模型续轮。
- `read_file` 默认读取完整 UTF-8 文件；只有模型显式传 `maxBytes` 时才按显式上限读取。
- `grep` 默认返回全部匹配和完整匹配行；`glob` 默认返回全部匹配；只有显式 `maxMatches` 时才限制。
- shell / git 输出默认完整保留，不再按本地固定字节数截断。
- `web_fetch` 和 MCP fetch 包装层默认完整返回抓取正文；只有显式 `maxBytes` / `maxLength` 时才截断。
- `document_intake` 默认完整返回可解析文本；只有显式 `maxBytes` 时才拒绝超限文件。
- 主会话和子智能体运行链路移除 in-flight tool result summary，不再把旧工具消息替换成 `[compacted tool result]`。
- 子智能体不再自动给 `read_file`、`grep`、`glob`、`web_fetch`、`document_intake` 注入预算上限；相关 profile/system prompt 改为默认保留完整证据，仅在用户/模型明确要求有限摘录时传 `maxBytes/maxMatches`。
- `lab-agent.config.json` 和默认配置中的 `inFlightCompactRatio` / `inFlightKeepRecentTools` 置为 `null`，避免后续误判为仍有运行时工具压缩。
- TUI 子智能体预算展示移除 `toolResult<=...`，避免 UI 暗示工具结果仍会被预算截断。

### 保留边界

- 显式工具参数仍生效：如果模型自己传了 `maxBytes` 或 `maxMatches`，工具会尊重该请求。
- 正式上下文 compact 机制仍存在：当整体会话超过配置的 `context.maxTokens/maxBytes` 时，仍可能触发会话级 compact；本次移除的是工具结果/文件结果的隐式早截断和 in-flight 摘要压缩。
- diff 生成、skill 内容、hook 输出、workflow 摘要等非“模型工具结果证据主链路”的本地保护仍保持原有边界。

### 验证

```powershell
node --check src\core\session.js
node --check src\agents\runner.js
node --check src\tools\web-tools.js
node --check src\tools\document-tools.js
node --check src\tools\runtime.js
node --check src\tools\git-tools.js
node --test tests\unit\tools.test.js
node --test tests\unit\session.test.js
node --test tests\unit\agents.test.js
node --test tests\unit\config.test.js tests\unit\tui-command-panels.test.js tests\unit\agent-budget-contract.test.js tests\unit\context-window.test.js
git diff --check
npm run check
```

结果：`npm run check` 通过，语法检查 155 files passed，全量测试 537 pass / 0 fail。

## 2026-05-07：限制 thinking/reasoning 运行时预览，避免长工具轮 OOM

### 背景

用户在 `D:\confirm-project\LBJ-workspace\Formica-Flow-confirm` 跑超长任务时全程监控到 Node/V8 在约 3.8GB 工作集、V8 heap 约 4GB 附近触发 `JavaScript heap out of memory`。复查落盘 `.lab-agent` 数据发现 session metadata 约 178KB、transcript 约 75KB，远不足以解释 4GB 堆占用。进一步排查确认更可疑的是 OpenAI-compatible `reasoning_content` / thinking 在多轮工具续跑中被完整保留并回传：每轮 thinking 会进入 gateway aggregate、TUI live stream、主会话/子智能体 assistant message，并在后续工具续轮中作为 `reasoning_content` 回传。

### 改动

- 新增 thinking 预览预算：默认最多保留最新 256KB，超过后从前部截断，仍保留总 thinking 字节数。
- OpenAI-compatible streaming aggregate 不再无限拼接完整 reasoning_content；只保留最新预览，并在 raw summary 中标记 `thinkingTruncated`。
- 主会话和子智能体的 thinking 捕获改为尾部预览，工具续轮仍可携带必要的最新 reasoning_content，但不会反复塞入全量历史 thinking。
- TUI live stream 和完成后的 assistant entry 只保存 thinking 预览；`/thinking` 文案从“原文”收口为“预览”，超长内容提示保留最新片段。
- 补充测试覆盖：超长 reasoning_content 续轮只回传尾部最新片段，streaming raw 仍统计总字节但不保留全量原文。

### 验证

```powershell
node --test tests\unit\gateway-protocol.test.js tests\unit\session.test.js tests\unit\tui-format.test.js tests\unit\commands.test.js
```

结果：123 pass / 0 fail。

## 2026-05-07：落实 `/sessions` 与 `/resume` 的产品分工

### 背景

用户在长会话内存治理讨论中重新定义两者职责：`/sessions` 保持已经习惯的历史会话恢复/切换入口；`/resume` 不再重复恢复会话，而是服务当前会话的 50 条 transcript 分片回看。

### 改动

- `session.transcriptMessages` 保持最新 50 条可见窗口，完整可见 transcript 按 50 条写入 `.lab-agent/sessions/<session-id>.transcript/chunk-*.json`。
- 新增 transcript chunk 只读接口，可按当前会话 archive 和分片序号读取单个分片。
- TUI 内 `/resume` 无参数打开当前会话分片列表，`/resume <分片序号>` 打开对应分片；内容只进入命令面板，不写回聊天列表、`session.messages` 或模型上下文。
- `/sessions` 的会话选择与恢复流程保持不变。
- 斜杠命令、README 和 MVP spec 文案同步：TUI 内恢复会话用 `/sessions`，当前会话历史回看用 `/resume`；CLI 启动参数 `ant-code --resume latest` 仍保留为启动恢复能力。
- 清理旧的 `/resume latest` TUI 说明，避免用户和后续智能体误判。

### 验证

```powershell
node --test tests\unit\storage.test.js tests\unit\tui-command-panels.test.js tests\unit\tui-format.test.js
npm run check
```

结果：针对性测试 59 pass / 0 fail；全量检查 532 pass / 0 fail。

## 2026-05-07：修复语音转文字长输入被前段覆盖

### 背景

用户反馈微信语音输入转换出一长串文字时，底部输入栏疑似吞掉前半部分。

### 根因

TUI 输入栏此前用 React state 快照计算草稿更新：`setInputDraft` 接收当前 `inputBuffer/inputCursor`，算出下一版文本后再分别 `setInputBuffer` 和 `setInputCursor`。普通键入通常没问题，但输入法/微信语音转文字可能在极短时间内分多块提交文本；第二块到达时 React 还没完成第一块渲染，仍用旧快照计算，导致后半块覆盖前半块。

### 改动

- 输入栏和 `ask_user` 自定义回答栏都改为同步 draft mirror：先更新本地 ref 和 `stateRef.current`，再触发 React state 渲染。
- 粘贴、普通文本输入、删除、光标移动、历史回填、文件补全、消息回退到输入栏都统一走同步草稿路径。
- 增加单测模拟连续分块输入，确保旧快照不会覆盖前一段文字。

### 验证

```powershell
npm test -- tests/unit/tui-frame.test.js tests/unit/tui-input-editor.test.js tests/unit/tui-format.test.js
npm run check
```

结果：针对性测试 70 pass / 0 fail；全量检查 530 pass / 0 fail。

## 2026-05-07：子智能体预算保护阀改为软着陆并保留完整输出

### 背景

用户指出子智能体工具输出超过 `320000 bytes` 后直接暂停过于死板：任务明明已经收集了不少有效信息，却没有机会先汇总给主智能体继续拆批处理。随后要求把同类预算保护都做成软着陆，并复核是否还有遗漏项会触发机械硬刹车。

### 对照

- Ant Code 此前的 `maxOutputBytes` 属于子智能体全局工具输出累计保护阀，一旦命中就直接返回机械 partial。
- OpenCode 的主要策略更靠前：默认 `tool_output.max_bytes=51200`、`max_lines=2000`，单次工具输出超限时把全文写入 truncation 目录，只把预览和路径提示交给模型；上下文压力更早被局部化。
- Ant Code 当前已有单次工具结果截断和 in-flight 工具消息压缩，本次继续保持保守，不改变权限、安全和用户中断边界，只改“预算/失败保护阀导致信息丢失”的路径。

### 改动

- `maxOutputBytes`、`maxDurationMs`、`maxRounds`、`maxToolCalls`、`maxConsecutiveFailures`、`maxPermissionDenials`、`webSearchUnavailable` 命中后不再优先机械 partial，而是进入无工具软着陆：清空下一轮可用工具，向子智能体追加“不要再调用工具，基于已有上下文生成阶段汇报”的用户消息。
- 阶段汇报要求包含已完成发现、已检查证据、剩余缺口和可拆分的 continuation plan，方便主智能体继续分小批次派发。
- 如果同一轮模型一次性请求多个工具，前一个工具触发软着陆后，后续未执行工具会回填 `AGENT_TOOL_SKIPPED_AFTER_GUARDRAIL`，保证模型 tool-call 协议完整，同时避免继续消耗输出/时间预算。
- 如果模型在软着陆轮仍尝试调用工具，保留原有 `finalReportToolLoop` 保护，避免空转。
- 任务进度文案从“网页来源失败”拆出通用输出预算文案，避免误导。
- 子智能体最终长输出不再只塞进任务 JSON：任务记录保存头尾预览，完整文本写入 `.lab-agent/task-outputs/<task-id>.txt`，摘录层/子智能体详情会按需读取侧车文件展示完整输出。
- 工具结果序列化从“只保留开头”改为“头尾保留、中间省略”，并允许配置的 `maxToolResultBytes` 最高到 `256KB`。
- shell 输出截断也改为头尾保留，并记录 `stdoutBytes` / `stderrBytes`，避免长命令只看到开头看不到最终错误。

### 复核结论

- 预算类保护阀已覆盖软着陆路径。
- 仍保留硬停的路径是有意的：未配置网关、权限策略拒绝启动、hook 阻断、用户中断、模型在无工具阶段仍请求工具的 `finalReportToolLoop`。
- 这些硬停不属于“已有信息被预算上限吞掉”的场景，暂不软化。

### 验证

```powershell
npm test -- tests/unit/agents.test.js tests/unit/tools.test.js tests/unit/agent-task-store.test.js tests/unit/agent-budget-contract.test.js tests/unit/tui-command-panels.test.js
npm run check
```

结果：针对性测试 105 pass / 0 fail；全量检查 529 pass / 0 fail。

## 2026-05-07：落地 ANTCODE.md 项目规则记忆入口

### 背景

用户希望 Ant Code 参考 Claude Code 的 `CLAUDE.md`、OpenCode/Codex 常见的 agent 规则文件模式，建立 Ant Code 自己的项目级维护习惯文件，同时避免一次性读取多个工具的规则文件导致冲突或上下文膨胀。

### 改动

- 新增 `ANTCODE.md` 作为 Ant Code 原生项目规则文件，定位为可提交 Git 的稳定项目规则。
- 项目主规则按优先级只读取一个：`ANTCODE.md` → `AGENTS.md` → `AGENT.md` → `CLAUDE.md` → `LAB_AGENT.md`。
- `.lab-agent/memory.md` 继续作为本地追加记忆加载，定位低于主项目规则。
- `/memory` 现在显示当前生效的主项目规则、被跳过的兼容文件和本地记忆文件。
- 主上下文中加入 project memory discipline：遵循项目规则；当用户在对话中明确表达长期偏好、习惯或希望以后采用的工作方式时，主动把简洁记忆追加到 `.lab-agent/memory.md`。
- `ANTCODE.md` 只用于应随仓库共享的稳定维护规则；个人工作流偏好放在 `.lab-agent/memory.md`；不得记录密钥、凭据或大段原始 transcript。

### 验证

```powershell
npm test -- tests/unit/memory.test.js tests/unit/context.test.js tests/unit/commands.test.js
npm run check
```

## 2026-05-07：提高 Markdown 代码块在黑底 TUI 中的可读性

### 背景

用户反馈大模型回复中的 fenced code block 在黑底 TUI 中使用浅灰 dim 样式，阅读不清晰。

### 改动

- 新增 `code` 语义色，默认使用低饱和但更清晰的 `#cbd5e1`。
- assistant 回复中的 Markdown 代码块不再使用 `dimColor`，改为 `code` 色渲染，保留代码围栏和语言标记。
- 补充单测，确保代码块不会被误解析成表格，也不会继续使用 dim 灰。

### 验证

```powershell
npm test -- tests/unit/tui-markdown-table.test.js tests/unit/tui-theme.test.js
npm run check
```

## 2026-05-07：增加 TUI 空闲静默看门狗

### 背景

用户将 Ant Code TUI 挂机一晚后遇到 Node/V8 heap out of memory。当前阶段不改动昨日刚验收的会话 transcript 保留逻辑，也不调整右侧子智能体面板，只先处理“对话结束后长期空转”的保守优化。

### 改动

- 新增 30 分钟空闲静默看门狗：仅在已信任、已进入主界面、非 busy、非流式输出、无审批/问题/弹层、无运行中后台任务或子智能体任务时进入 `静默待机`。
- 静默待机期间暂停 TUI 心跳刷新，并在没有运行中任务时停止任务轮询，减少长时间挂机的无意义状态刷新。
- 任意键盘、鼠标或原始输入会唤醒 TUI，状态显示为 `已唤醒`。该机制不清理聊天记录、不修改 session/transcript 保留策略、不改变右侧栏展示结构。
- 支持通过 `LAB_AGENT_TUI_IDLE_SILENT_MS` 调整阈值；设为 `0` 或负数可关闭该看门狗。

### 验证

```powershell
npm test -- tests/unit/tui-frame.test.js
npm run check
```

## 2026-05-06：修复超长任务后聊天历史被运行日志/压缩挤掉

### 背景

用户在 Ant Code 中执行超长任务时，任务接近尾声后聊天框突然看不到之前的对话，最终完成后也无法在当前聊天框回看早期内容。该问题发生在长任务、高工具调用量和可能触发上下文压缩的组合场景。

### 根因

- TUI 聊天框内存 `entries` 只有 200 条上限，且此前用 `slice(-200)` 机械保留最后 200 条。超长任务会产生大量 `gateway`、`tool`、`tools`、`turn`、`workflow` 等运行过程条目，这些低价值遥测条目会把早期用户/助手对话挤出屏幕历史。
- 本地 metadata 的 `transcript.messages` 此前直接来自 `session.messages`。而 `session.messages` 是模型上下文窗口，会被自动压缩裁成 recent messages；因此触发压缩后，恢复会话也只能看到压缩后的少量上下文消息，而不是完整本地 transcript。

### 改动

- 新增 `limitTranscriptEntries()`：TUI 超过内存上限时优先丢弃运行遥测条目，而不是优先丢用户/助手对话。
- 新增 `session.transcriptMessages`：本地 transcript 与模型上下文分离。`session.messages` 继续可压缩、只服务模型输入；`transcriptMessages` 用于本地会话恢复和聊天回看，不随上下文压缩缩短。
- metadata 中新增 `transcript.contextMessages` 保存压缩后的模型上下文，`transcript.messages` 保存完整可恢复聊天记录；旧 metadata 仍兼容原结构恢复。
- TUI 恢复会话时优先展示 `session.transcriptMessages`，并在恢复提示里区分“已恢复消息”和“模型上下文保留”。

### 验证

```powershell
node --test tests/unit/session.test.js tests/unit/tui-frame.test.js
```

## 2026-05-06：调整 DeepSeek 子智能体默认模型为 Flash

### 背景

用户确认 DeepSeek 主智能体应继续使用 `deepseek-v4-pro`，但子智能体不应默认全部使用 Pro。`deepseek-v4-flash` 性能足够强，适合承接探索、研究、验证、复核和执行切片，形成“主控 Pro + 子智能体 Flash”的成本/协作结构。

### 根因

Ant Code 子智能体并不是硬继承父模型；`resolveAgentModel()` 会按 profile/路由的 `modelTier` 查 `agents.modelTiers`。此前仓库默认配置中 `cheap=flash`，但 `default=pro`、`strong=pro`，因此 verifier/reviewer/junior/code-worker 等 default/strong profile 会继续跑 Pro。

### 改动

- 保持顶层 `modelAlias: deepseek-v4-pro` 不变，主控仍使用 Pro。
- 将仓库默认 `agents.modelTiers.cheap/default/strong` 全部映射到 `deepseek-v4-flash`。
- 同步测试项目 `E:\test-project\LBJ-workspace\new-ptoject\.lab-agent\config.json` 的 `agents.modelTiers`，避免项目级配置现场继续显示混乱。
- 补充单测，固定“父模型 Pro，子智能体三档 Flash”的路由预期。

### 验证

```powershell
node --test tests/unit/config.test.js tests/unit/agent-budget-contract.test.js
```

## 2026-05-06：修复输入栏闪烁光标消失

### 背景

用户反馈 TUI 输入栏的闪烁光标不见了。排查确认输入栏不是依赖终端默认光标，而是由 TUI 手动渲染 cursor segment，并额外把终端原生光标定位到输入框位置。

### 根因

- 大段粘贴/长多行输入会进入 `compactMultilineDraftLines()` 摘要显示分支，该分支返回纯文本行，没有携带 cursor segment，所以反色视频块光标会消失。
- 空闲态此前不会推进 `pulse`，如果界面恰好停在隐藏光标帧，闪烁光标会一直保持不可见；忙碌/流式输出时才会恢复跳动。

### 改动

- 大段粘贴摘要首行末尾增加 cursor segment，保留压缩展示同时继续显示闪烁光标。
- TUI 空闲态也低频推进输入框心跳；忙碌/流式输出仍保持高频刷新，摘录层继续暂停刷新，避免破坏鼠标选择复制。
- 补充单测覆盖“大段粘贴输入仍包含 cursor segment”。

### 验证

```powershell
node --test tests/unit/tui-format.test.js tests/unit/tui-input-editor.test.js tests/unit/tui-frame.test.js
```

## 2026-05-06：修复 DeepSeek thinking + tool calls 兼容错误

### 背景

用户在 `E:\test-project\LBJ-workspace\new-ptoject` 中让 DeepSeek 测试 Ant Code 工具时遇到 `GATEWAY_HTTP_ERROR: HTTP 400`。会话记录显示第 1 轮 DeepSeek 已正常返回工具调用，第 2 轮回填 5 个工具结果时失败；当时上下文只有约 9k 本地估算 token，不是上下文上限问题。最小真实探针复现到 DeepSeek 返回：`The reasoning_content in the thinking mode must be passed back to the API.`

### 根因

DeepSeek thinking mode 在工具调用续轮中要求客户端把上一轮 assistant 的 `reasoning_content` 原样传回。Ant Code 之前把 `reasoning_content` 只作为 TUI hidden thinking 捕获和落盘，构造 OpenAI-compatible 第二轮请求时没有放回 assistant message，导致 DeepSeek 合理拒绝请求。

### 改动

- OpenAI-compatible 请求构造现在会把 assistant message 上的 `thinking.text` / `reasoning_content` 转成 `reasoning_content` 字段。
- OpenAI-compatible 响应规范化新增内存级 `thinkingText`，用于 DeepSeek 工具续轮回传；raw summary 仍不保存 thinking 原文，避免日志/metadata 泄露。
- 主会话工具调用轮在把 assistant tool_calls 放回消息队列时，同时附上该轮 thinking，供下一轮 OpenAI-compatible 请求使用。
- 子智能体 runner 也同步修复同一问题：model-driven subagent 在工具调用续轮中会保留上一轮 thinking，避免 `agent_run` 第二轮被 DeepSeek 拒绝。
- gateway HTTP error 现在会把当前 round 的错误 code/status/message/details 写入 `gatewayRounds[].error`，details 继续走本地敏感信息脱敏，方便后续定位 provider 400/401/5xx 的真实原因。

### 兼容排查

- 已确认本次 HTTP 400 不是 key、网络、上下文窗口或工具 schema 数量导致。
- 其它潜在 OpenAI-compatible 差异包括 `stream_options.include_usage`、assistant tool call 的 `content:null`、不同 provider 的工具参数 JSON 宽容度；本次只修已被 DeepSeek 官方行为证实的问题，不扩大请求协议面。

### 验证

```powershell
node --test tests/unit/gateway-protocol.test.js tests/unit/session.test.js
node --test tests/unit/agents.test.js
node --test tests/integration/print-mode-gateway.test.js
npm run check
```

另用本机 DeepSeek 配置执行最小真实探针：带 `thinking` 的 assistant tool call + tool result 续轮已返回 `ok: true`，不再出现 HTTP 400。用户随后测试发现 `agent_run` 子智能体还有同类遗漏，已补子 runner 回归测试覆盖。

## 2026-05-06：DeepSeek 上下文窗口与项目配置继承修复

### 背景

用户在 DeepSeek 网关测试中遇到 `GATEWAY_HTTP_ERROR: HTTP 400`，同时发现 TUI/状态面板中的模型窗口和自动压缩阈值又回到旧的 200k/256k 附近。经排查，仓库 DeepSeek 默认模型仍写着 `contextTokens: 128000`，且普通项目目录存在 `.lab-agent/config.json` 时，配置加载会跳过仓库 bundled `lab-agent.config.json`，从内置 200k 默认重新起步。

### 改动

- 将 `deepseek-v4-pro` 与 `deepseek-v4-flash` 的 `contextTokens` 调整为 `1000000`。
- 将本地自动压缩阈值 `context.maxTokens` 调整为 `500000`，`context.maxBytes` 调整为 `2000000`。
- 修改配置加载顺序为：内置默认 < 仓库 bundled 配置 < 项目配置 < `LAB_AGENT_CONFIG` < 环境变量。
- 这样项目级 `.lab-agent/config.json` 即使只保存 key 或少量覆盖项，也不会让模型列表、MCP、skills、上下文窗口退回内置旧默认。
- `/model` 模型列表的 token 格式化补齐百万级显示，`1000000` 显示为 `1M` 而不是 `1000k`。
- 本机测试项目 `E:\test-project\LBJ-workspace\new-ptoject\.lab-agent\config.json` 已同步更新为 1M 模型窗口和 500k 本地压缩阈值；未记录或打印真实 key。

### 验证

```powershell
node --test tests/unit/config.test.js tests/unit/commands.test.js
node -e "import('./src/config/load-config.js').then(async ({loadConfig})=>{const c=await loadConfig({cwd:'E:/test-project/LBJ-workspace/new-ptoject',env:{}}); console.log(c.context.maxTokens, c.models.map(m=>m.contextTokens).join(','));})"
```

## 2026-05-06：恢复网关 fetch 重试与中断草稿保留

### 背景

此前在排查网关不稳定和“生成中中断会丢掉整段草稿”时曾做过两项改动，但因为后续 TUI 输入事故回滚，这两项没有进入稳定提交。用户要求重新移植并实现，且不要再影响已稳定的权限切换、鼠标点击和摘录层输入路径。

### 改动

- 网关 fetch 重试：
  - 新增 `lab.gatewayMaxRetries` 配置，默认 2，环境变量为 `LAB_MODEL_GATEWAY_MAX_RETRIES`，允许范围 0-5。
  - `createLabModelGateway()` 只对“尚未拿到 HTTP 响应前”的 fetch 异常重试；HTTP 状态码错误、解析错误和用户 abort 不重试。
  - 每次重试发出 `gateway_retry` 事件，并把 attempts / retryHistory 写入规范化网关错误详情，便于区分 provider 瞬断和本地策略阻断。
  - `/gateway` 健康检查报告显示 fetch retry 预算。
- 中断草稿保留：
  - 会话运行中捕获已流出的 `assistant_delta` 和 thinking delta。
  - 用户中断时，如果已经收到可见助手正文，TUI 会插入一条“中断草稿”消息，方便继续纠偏和摘录复制。
  - 草稿随本地 transcript 保存为“中断草稿，非最终回复”，恢复会话后可见；下一轮模型上下文也能看到这次未完成草稿，避免用户纠偏时模型完全失忆。
  - thinking 仍按现有 transcript/redaction 策略保存和隐藏展示，不额外暴露到复制文本。

### 风险控制

- 未改动 Windows console mode、raw input、mouse hit-testing、摘录层选择逻辑。
- 网关重试上限可设为 0 关闭。
- 中断草稿只在已收到可见正文时保存；如果只收到 thinking 或尚无输出，则仍只记录本地中断。

### 验证

```powershell
node --test tests/unit/config.test.js tests/unit/gateway-health.test.js tests/unit/session.test.js
node scripts/check-syntax.js
git diff --check
npm run check
ant-code gateway
```

## 2026-05-06：TUI Windows 输入事故复盘与稳定版留档

### 背景

用户要求追查：为什么 DeepSeek 切换后 TUI 权限切换、鼠标点击和摘录层突然集中失效；这到底是“智能体改崩”，还是原本就有的隐藏 bug。同时要求确认此前“网关重试 + 中断草稿保留”的修改是否因回滚丢失，并将当前稳定状态保存到本地 git。

### 结论

- DeepSeek/key 配置不是因果源头，只是时间上挨得近。
- 根因是旧版 Windows TUI 终端输入模式链路已有隐藏缺陷：
  - `runWindowsConsoleModeScript()` 只判断 PowerShell 进程是否启动，没有要求脚本 `status === 0`。
  - 在当前机器上 `powershell.exe` 可启动但 `Add-Type` console mode 脚本失败，`pwsh.exe` 才成功；旧逻辑因此不会继续尝试 `pwsh.exe`。
  - `enableWindowsConsoleMouseInput()` 在脚本真正成功前就把 `windowsConsoleInputEnabled` 标为 true，导致后续跳过重新校准。
  - 鼠标模式历史上启用了 `1003` 任意移动追踪，raw 输入解析加入后会产生事件风暴和卡顿。
- 最近智能体的 TUI raw 输入补丁不是从零制造根因，但确实让旧雷变成高频路径：
  - raw Shift+Tab、raw mouse fallback、摘录层/选择模式频繁切换都更依赖 Windows console input mode 正确恢复。
  - raw 与 Ink 双通道同时处理同一次点击时，会把单击误判成双击。

### 处理

- 新增事故复盘文档：`docs/audit/tui-windows-input-incident-2026-05-06.md`。
- 保留现有修复：
  - PowerShell console mode helper 只把 `status === 0` 视为成功。
  - Windows console input enabled 标记只在脚本成功后设置。
  - 鼠标 reporting 不再启用 `1003` 任意移动追踪。
  - resize 和退出摘录层后仍强制校准一次 console input mode。
  - raw/Ink 点击按坐标和短时间窗口去重。
  - 窄屏 footer 固定一行，权限模式不会被挤掉。

### 回滚影响核查

用户提到此前曾要求“增加网关重试、增加判断记录，并考虑中断时保留模型草稿”。当前代码状态如下：

- 仍然存在：
  - 上下文预算诊断。
  - `metadata.gatewayRounds[]`。
  - provider usage 记录。
  - 异常最终回复健康检查入口，但默认关闭。
- 当前没有完整落地：
  - `src/model-gateway/client.js` 没有 gateway fetch 自动重试。
  - 流式回复被用户中断时，`finishInterruptedTurn()` 仍只保存 `Turn interrupted by the local user.`，不会把已经流式显示的 assistant 草稿写入 transcript。

这两项应视为后续待设计能力，不能在后续交接中误写成已完成。

### 验证

```powershell
node --test tests/unit/tui-interaction.test.js tests/unit/tui-frame.test.js tests/unit/tui-format.test.js
node scripts/check-syntax.js
npm run check
git diff --check
ant-code gateway
```

用户已复测确认：权限切换和摘录层恢复正常。

## 2026-05-06：TUI 快捷键与鼠标点击输入链路修复

### 背景

用户在切换 DeepSeek 配置后继续遇到 TUI 交互异常：权限模式快捷键无法切换，鼠标点击聊天消息无法进入摘录层。最初排查发现当前进程环境中仍残留旧小米网关变量，但用户重启终端后问题仍存在，因此继续检查 TUI 输入事件链路。

### 发现

- 全局 `ant-code` 确认是 junction 到当前仓库，不是旧 npm 包。
- `debugTuiInput(...)` 在多个新日志点被调用，但源码里缺少函数定义；一旦权限切换或鼠标点击路径触发，会产生运行时异常。
- Shift+Tab 只覆盖了部分终端序列，Windows Terminal / kitty 风格序列和拆包场景可能漏识别。
- 鼠标点击主要依赖 Ink 的 `useInput` 路径；如果终端把鼠标序列只送到 raw stdin，聊天消息点击会表现为没有反应。
- `LAB_AGENT_TUI_DEBUG_INPUT=1` 诊断日志只看传入的 `props.env`，缺少直接读取 `process.env` 的兜底，导致实际排查时可能没有日志落盘。

### 处理

- `src/cli/tui.js`
  - 补齐 `debugTuiInput`，并让 `debugRawInput` / `debugTuiInput` 同时检查 `props.env` 与 `process.env`。
  - raw stdin 输入层新增鼠标点击 fallback：直接解析 SGR/X10/urxvt 鼠标点击序列，复用消息块 hit-testing 与双击摘录层逻辑。
  - 增加 raw/Ink 鼠标点击去重，避免同一次点击被两条输入路径重复处理后误判为双击。
  - Shift+Tab fallback 支持输入拆包：保留未完成的 `Esc` 序列尾巴，下一次 raw chunk 到来后再合并识别。
  - 增加 `terminal_resize`、`permission_switch`、`raw_mouse_click`、`mouse_transcript_entry hit/miss` 调试日志，便于后续定位是终端未发送、TUI 未解析，还是命中区域不对。

- `src/cli/tui/interaction.js`
  - `rawShiftTabPresses` 增加更多终端序列识别：`\x1b[1;2\t`、`\x1b[9;2u`、`\x1b[9;2~`、`\x1b[\t`。

- `tests/unit/tui-interaction.test.js`
  - 补充 Shift+Tab 多终端序列覆盖。

### 验证

```powershell
node --test tests/unit/tui-interaction.test.js tests/unit/tui-frame.test.js tests/unit/tui-format.test.js
node scripts/check-syntax.js
npm run check
git diff --check
```

结果：

- 针对性 TUI 测试：65 pass / 0 fail。
- 语法检查：154 files passed。
- 全量检查：503 pass / 0 fail。
- diff whitespace 检查通过。
- 在清空当前进程旧网关环境变量后，`E:\test-project\LBJ-workspace\new-ptoject` 下 `ant-code gateway` 仍显示 DeepSeek configured。

### 复测建议

在新终端中设置 `LAB_AGENT_TUI_DEBUG_INPUT=1` 后启动 TUI，依次测试 Shift+Tab、单击消息块、双击消息块。若仍异常，查看 `%TEMP%\lab-agent-tui-input.log`，重点看是否出现 `permission_switch`、`raw_mouse_click`、`mouse_transcript_entry hit/miss`。

### 补充：终端模式诊断日志

- 继续保留正常 TUI 交互不变，不新增用户可见快捷键或入口。
- 仅在 `LAB_AGENT_TUI_DEBUG_INPUT=1` 时追加终端模式日志，用于判断是否启用了 mouse tracking、是否进入了摘录/原生选择模式、Windows console input mode 是否按预期切换。
- 新增日志事件包括：
  - `terminal_app_mode enter/exit`
  - `terminal_mouse enable/disable reason=...`
  - `terminal_selection enter reason=...`
  - `windows_console_mouse enable before=... after=...`
  - `windows_console_selection restore before=... after=...`
  - `windows_console_input restore before=... after=...`
- Windows console mode before/after 采样只在 debug 开启时执行，避免普通启动额外多跑 PowerShell 快照。
- 后续复测日志显示 `windows_console_mouse enable ... status=1`，说明 mouse tracking 对应的 Windows console input mode 实际没有切换成功。复现后确认同一段 `Add-Type` 脚本在 `powershell.exe` 下可能失败，但在 `pwsh.exe` 下成功；原 `runWindowsConsoleModeScript()` 只判断“进程是否启动”，没有判断脚本退出码，导致 `powershell.exe` 返回 status=1 时不会继续尝试 `pwsh.exe`。
- 修复 `runWindowsConsoleModeScript()`：只有 `status === 0` 才视为成功并返回，否则继续尝试后续 PowerShell 可执行文件；debug 日志同步记录实际成功的 `exe=...`，方便确认是 `powershell.exe` 还是 `pwsh.exe` 完成切换。
- 用户复测后确认权限切换和摘录层恢复，但反馈三项体验问题：小窗口看不到权限展示、切换/点击存在卡顿、单击消息块不再显示选中效果。日志显示 mouse tracking 打开后仍启用了 `1003` 任意移动事件，鼠标移动会产生大量 `35;x;yM` 事件；同时 raw stdin 和 Ink 会各自处理同一次点击，导致单击被误判为双击并直接进入摘录层。
- 调整鼠标模式：只启用 click/drag 需要的 `1000/1002/1006/1015/1007`，不再启用 `1003` 任意移动追踪，减少鼠标移动造成的事件风暴和卡顿。
- 调整 raw/Ink 点击去重：改为按坐标和短时间窗口去重，避免同一次点击在 raw 与 Ink 两条路径中被连续处理成双击；单击应恢复消息块高亮提示，双击才进入摘录层。
- 小窗口权限展示固定为单行：`PermissionFooter` 和 `FooterBar` 明确 `height=1` 并截断长文案，窄屏下权限切换提示压缩为 `S+Tab`，避免长 footer 把权限行挤出视图。
- 再次复核后保留一次强制 console mode 校准：resize 和退出摘录层后仍会重新校准 Windows console input mode，但 mouse reporting 仍不启用 `1003` 任意移动追踪。`enableWindowsConsoleMouseInput()` 也改为只有脚本 `status=0` 才把内部状态标为已启用，防止脚本失败后后续误跳过校准。

## 2026-05-06：review gate 调整为阶段型精准复核

### 背景

用户指出原 review gate 触发太容易：只要 prompt 出现权限、MCP、install 等关键词，或者小范围文件改动，就可能在最终回答前提醒 reviewer/verifier。实际使用中，用户更需要复核的是长任务关键节点，而不是纯诊断、小问题确认或一两个文件的小改动。

### 处理

- `src/agents/review-policy.js`
  - 移除“修改文件数”作为触发条件。
  - 移除关键词单独触发 review gate 的逻辑。
  - 改为三类阶段 gate：
    - 计划复核：创建达到阈值的 todo/plan 且尚未正式执行时触发。
    - 交付复核：多个 todo/plan step 已完成，准备最终汇报前触发。
    - 异常复核：长任务或实现型子任务出现 partial、blocked、failed 时触发。
  - 单个 `web_fetch` blocked 或普通诊断工具失败不再触发，避免 fetch/MCP 可用性测试被误判成需要复核。

- `src/config/load-config.js`
  - review gate 配置校验支持 `planThreshold`、`deliveryThreshold`，默认继续沿用 `todoThreshold`。

- `LLM_ONBOARDING.md`
  - 更新维护提醒：review gate 是阶段型提醒，禁止重新引入文件数或关键词单独触发。

### 验证

```powershell
node --test tests/unit/review-policy.test.js tests/unit/config.test.js
npm run check
```

结果：针对性测试 `31 pass / 0 fail`，全量检查 `503 pass / 0 fail`。

## 2026-05-06：web_fetch 改为 MCP 优先抓取并增强 URL 容错

### 背景

用户实测出现两类问题：

- `tool - web_fetch failed ... WEB_URL_REQUIRED`：模型调用内置抓取工具时传入了空 URL、别名字段或缺少协议的 URL，工具容错不足。
- `tool - web_fetch blocked ... decision=deny`：抓取链路仍容易被网络权限或内置实现细节影响。用户建议尝试把 MCP 作为主要 fetch 工具。

### 处理

- `src/tools/runtime.js`
  - `web_fetch` 对模型仍保持同一个公开工具名，但运行时默认变为 `mcp-first`：
    - 优先调用推荐的 `fetch` MCP：`mcp_call(fetch/fetch)`。
    - MCP 不存在、未启用、启动失败或请求失败时，自动回退到 Ant Code 内置抓取器。
    - 支持配置 `web.fetchProvider: "mcp-first" | "builtin" | "mcp-only"`。
  - `web_fetch` 参数容错增强：
    - 支持 `target`、`uri`、`href`、`link` 自动映射为 `url`。
    - 支持 `example.com/docs` 这类无协议公网地址自动补 `https://`。
    - 支持 `localhost:3000` / `127.0.0.1:3000` 自动补 `http://`。
  - MCP fetch 返回结果会被归一化为原 `web_fetch` 结果结构，并标记 `provider: "mcp-fetch"`，便于 TUI 和日志识别。

- `config/skills/web-research/SKILL.md`、`src/context/builder.js`、`src/agents/profiles.js`
  - 明确 `web_fetch` 现在是 MCP 优先、内置兜底的稳定公开入口。
  - 联网研究子智能体提示词改为优先使用 fetch MCP / GitHub MCP，再使用内置抓取兜底。

- `LLM_ONBOARDING.md`
  - 记录 `web_fetch` 不再是“纯内置工具”，后续维护网络权限时要同时保持 MCP 和内置兜底两条链路一致。

### 验证

- 新增 MCP fetch fixture 与单元测试：
  - `web_fetch` 能优先走 `fetch` MCP 并归一化结果。
  - `web_fetch` 能接受 `target` 别名。
  - MCP fetch 返回超大内容时，`web_fetch` 包装层仍会按 `maxBytes` 二次截断。
  - 原有 loopback HTML 到 Markdown 的内置抓取测试继续覆盖兜底路径。
- 全量检查：

```powershell
npm run check
```

结果：`500 pass / 0 fail`。

## 2026-05-05：权限链路复查与 MCP 网络误拦修复

### 背景

用户指出 `tool web_fetch blocked` 的根因很可能来自早期“本地代码智能体”设计下的保守默认策略，希望沿着这个逻辑继续排查是否还有类似权限阻拦。复查重点放在三类容易残留旧策略的位置：

- 配置默认值和模板是否还默认 `lab-only`。
- 主会话、子智能体、MCP runtime 是否完整传递 `networkMode/allowedHosts/fullAccess`。
- MCP/Skill/browser/network 等二级入口是否有自己的硬拦或信息缺失。

### 发现

- 根配置已是 `approved-web`，但 `src/config/load-config.js` 的无配置默认值仍是 `lab-only`，标准实验室模板也还是 `lab-only`。
- MCP runtime 对 `network` 风险工具没有向权限引擎提供 URL/host，导致 `approved-web` 无法按 allowlist 判断，只能返回“network request has no declared host”，在后台子智能体里表现为累计 permission denied。
- 主会话创建 MCP runtime 时漏传 `allowedHosts`，即使项目配置允许某个 host，主智能体直接走 MCP network tool 时也可能误触发确认。

### 处理

- `src/mcp/runtime.js`
  - MCP network 工具现在会从 `url/uri/link/endpoint/target` 等参数中提取真实 URL。
  - DuckDuckGo/SearXNG/GitHub 类 MCP 在没有显式 URL 参数时，会声明自己的 provider host。
  - 这样 `approved-web` 可以正确区分“已批准 host 直接允许”和“未知 host 询问”，不再退化成无 host 的笼统确认。

- `src/core/session.js`
  - 主会话创建 MCP runtime 时补传 `allowedHosts`，与内置工具和子智能体链路对齐。

- `src/config/load-config.js`、`config/lab-agent.lab-template.json`
  - 标准默认网络模式从 `lab-only` 调整为 `approved-web`。
  - 高敏模板仍保持 `lab-only/offline` 约束，不放宽敏感场景。

- `src/tools/env-scrubber.js`、`src/tools/shell-tools.js`
  - 普通/工作区模式继续清洗 shell 子进程中的 token、API key 等敏感环境变量。
  - `fullAccess` 模式下 shell 命令不再清洗这些变量，避免测试机最高权限长任务中脚本拿不到必要凭据。
  - MCP 子进程仍使用 per-server `envAllowlist`，避免把所有本机密钥直接交给第三方 stdio server。

- `tests/unit/mcp.test.js`、`tests/integration/print-mode-gateway.test.js`
  - 新增 MCP network allowlist 回归测试。
  - 新增 print-mode 主会话 MCP allowedHosts 传递测试，防止主智能体路径再次漏传。

- `tests/unit/tools.test.js`
  - 新增 `fullAccess` shell env 回归测试，确认最高权限 shell 能读到 runtime env 中的 secret-like 变量。

- `LLM_ONBOARDING.md`
  - 增加维护提醒：创建嵌套 MCP runtime 时必须同时传递 `networkMode` 和 `allowedHosts`。

### 验证

```powershell
node --test tests\integration\print-mode-gateway.test.js tests\unit\mcp.test.js tests\unit\config.test.js
node --test tests\unit\mcp.test.js tests\unit\permissions.test.js tests\unit\config.test.js tests\unit\tools.test.js
```

结果均为 `0 fail`。最终仍需跑全量 `npm run check`。

## 2026-05-05：子智能体 token 拆行展示与 web_fetch 阻断策略调整

### 背景

用户指出右侧“子智能体”面板不像状态面板一样拆行显示 tokens，Provider 输入/输出/合计仍挤在一行里。随后用户反馈工具侧经常出现 `tool web_fetch blocked`，需要判断是代理问题还是权限问题。

现场复查：

- 当前进程环境变量里没有显式 `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY`。
- Windows 系统代理已开启，注册表显示 `127.0.0.1:7897`，Ant Code 的 `resolveProxyForUrl()` 能正确解析到该代理。
- 因此 `tool web_fetch blocked` 主要不是代理失效，而是默认 `networkMode: lab-only` 对未 allowlist host 直接 `deny`，模型抓普通网页时会被本地权限策略挡掉。

### 处理

- `src/cli/tui/components.js`
  - 右侧“子智能体”面板的任务 tokens 改为分组短行：
    - `模型输入（估算）`
    - `输入：x/y tokens`
    - `Provider 实报`
    - `输入/缓存命中/输出/合计`
  - 缓存命中沿用会话状态栏的 `x/y tokens (z%)` 格式。

- `src/cli/tui/command-panels.js`
  - 子智能体实时详情/摘录详情中的 Provider 实报也改为短行展示。

- `lab-agent.config.json`
  - 默认 `networkMode` 从 `lab-only` 调整为 `approved-web`。
  - 结果：未列入 allowlist 的网页不再直接 deny，而是进入权限确认；完全访问模式仍会自动允许网络工具。
  - 默认 allowedHosts 增加 `r.jina.ai`，作为网页正文 reader mirror 备用入口。

- `src/agents/profiles.js`、`config/skills/web-research/SKILL.md`
  - web/readonly researcher 提示词补充：
    - GitHub 优先 github MCP、raw.githubusercontent.com、api.github.com。
    - 普通 HTML fetch 被阻断或反爬时，先用搜索摘要、官方 API/raw 文件，必要时使用 `r.jina.ai` reader mirror 并在 caveats 中说明。

### 验证

```powershell
node --test tests\unit\tui-frame.test.js tests\unit\tui-command-panels.test.js
```

结果：`46 pass / 0 fail`。随后继续执行配置/网络相关测试和全量检查。

## 2026-05-05：对齐 Mimo 模型窗口 400k 与本地压缩阈值 256k

### 背景

用户发现右侧状态栏仍显示“模型窗口 200k / 本地压缩阈值 200k”，与此前讨论的“模型窗口 40w、本地 256k 自动压缩”策略不一致。复查确认不是 TUI 显示 bug，而是当前 `lab-agent.config.json` 仍保留 200k 配置。

### 处理

- `lab-agent.config.json`
  - `mimo-v2.5` 与 `mimo-v2.5-pro` 的 `contextTokens` 从 `200000` 调整为 `400000`。
  - `context.maxTokens` 从 `200000` 调整为 `256000`。
  - `context.maxBytes` 从 `800000` 调整为 `1024000`，继续按约 4 bytes/token 的本地估算口径对齐。

- 测试与维护文档
  - 更新 `/model` 和配置测试中的 200k 预期为 400k/256k。
  - 更新 `LLM_ONBOARDING.md`，明确当前 Mimo 模型窗口和本地压缩预算的区别。

### 说明

侧栏里的两个数字含义不同：

- `模型窗口`：当前模型配置的 provider/model context window，现在是 `400k tokens`。
- `本地压缩阈值`：Ant Code 请求前预算和自动压缩使用的本地阈值，现在是 `256k tokens`。

## 2026-05-05：Provider 实报增加缓存命中展示

### 背景

用户发现当前 token 侧栏虽然显示“累计输入”，但它并不能很好解释真实使用体感；最近 session 的 provider 原始 usage 实际返回了 `prompt_tokens_details.cached_tokens`，说明可以展示最近一轮输入里有多少 token 命中了 provider 缓存。

### 处理

- `src/core/provider-usage.js`
  - Provider usage 聚合新增 `cachedPromptTokens` 与 `lastCachedPromptTokens`。
  - 支持 OpenAI-compatible 常见字段：
    - `prompt_tokens_details.cached_tokens`
    - `input_tokens_details.cached_tokens`
    - `cache_read_input_tokens`
    - 以及若干 camelCase/兼容命名。
  - usage totals 改为递归累加嵌套数值字段，避免缓存命中只存在嵌套 details 时无法累计。

- `src/core/context-window.js`
  - context summary 增加最近与累计 provider 缓存命中 tokens 字段。

- `src/cli/tui/components.js`
  - 右侧“状态”面板在 provider 返回缓存字段时显示：
    - `缓存命中：x/y tokens (z%)`
  - 不支持或未返回缓存字段时不显示该行，避免侧栏噪音。

- `src/cli/tui/command-panels.js`
  - `/usage` 的累计和最近 provider usage 增加缓存命中摘要。

- `src/agents/runner.js`
  - 子智能体 provider usage 进度同步携带缓存命中字段，后续任务面板可复用。

### 验证

```powershell
node --test tests\unit\session.test.js tests\unit\tui-frame.test.js tests\unit\tui-command-panels.test.js tests\unit\agents.test.js
```

结果：`92 pass / 0 fail`。随后继续执行全量检查。

## 2026-05-05：修正右侧栏 Provider 实报可读性

### 背景

用户指出：Provider 实报 tokens 已经接入，但右侧栏“状态”面板空间较窄，原先把输入/输出/合计写在一行时容易被截断；界面上也没有明显提示应该去哪里查看完整 usage。

### 处理

- `src/cli/tui/components.js`
  - 状态面板不再用单行长文本展示 Provider 实报。
  - 拆成短行显示：
    - `Provider 实报`
    - `输入：... tokens`
    - `输出：... tokens`
    - `合计：... tokens`
    - 可选的累计输入和报告次数。
  - 右侧栏状态 footer 明确提示：`/context` 或 `/usage` 查看完整用量。

- `tests/unit/tui-frame.test.js`
  - 增加状态侧栏 Provider 实报拆行渲染测试。
  - 增加 footer 中 `/context`、`/usage` 完整用量提示的断言。

### 验证

```powershell
node --test tests\unit\tui-frame.test.js tests\unit\tui-command-panels.test.js
npm run check
```

结果：

- TUI 定向测试：`46 pass / 0 fail`。
- 全量检查：`493 pass / 0 fail`。

## 2026-05-05：补齐 provider 实报 tokens 链路

### 背景

用户指出：上下文和子智能体 tokens 显示不能只停留在本地估算，provider 返回的真实 `usage` 应该是一等能力。此前非流式响应和 lab gateway 协议已经能保留 `usage`，但 OpenAI-compatible 流式路径没有请求 `include_usage`，stream parser 也没有把最终 usage chunk 接回；主会话和子智能体界面仍主要展示估算。

### 处理

- `src/model-gateway/openai-chat.js`
  - OpenAI-compatible 流式请求增加 `stream_options: { include_usage: true }`。
  - SSE parser 捕获最终 usage chunk，并把 `response.usage` 传回统一 gateway response。

- `src/core/provider-usage.js`
  - 新增 provider usage 聚合工具：
    - 保留最近一次 provider 原始 usage。
    - 累加 provider 报告次数和常见 token 字段。
    - 同时支持 `prompt_tokens/completion_tokens/total_tokens` 与 `input_tokens/output_tokens` 口径。
    - 对疑似凭据字段做脱敏。

- `src/core/session.js`、`src/core/context-window.js`
  - 每次 gateway response 后把 provider 实报累加进 `session.usage`。
  - session metadata 持久化 `usage` 和 `lastProviderUsage`，resume 后继续保留。
  - 上下文摘要新增 provider 最近输入/输出/合计 tokens 和累计 tokens 字段。
  - 本地估算继续保留，用于请求前预算判断和自动压缩；provider 实报用于请求后的真实统计。

- `src/agents/runner.js`
  - 子智能体每轮模型响应后写入 provider 实报字段到 task `budgetProgress`。
  - 右侧栏和详情面板可同时看到本地估算与 provider 实报。

- TUI 与斜杠命令展示
  - 状态栏、`/context`、`/usage`、右侧“子智能体”面板和子智能体详情新增 provider 实报显示。
  - 文案明确区分“本地估算”和“Provider 实报”，避免误以为压缩判断已经拿到 provider 真实值。

### 验证

```powershell
node --test tests\unit\gateway-protocol.test.js tests\unit\session.test.js tests\unit\agents.test.js tests\unit\tui-command-panels.test.js tests\unit\tui-frame.test.js tests\unit\commands.test.js
npm run check
```

结果：

- 针对性测试：`150 pass / 0 fail`。
- 全量检查：`492 pass / 0 fail`。

### 结论

现在 Ant Code 是双轨口径：

- 请求前：继续使用本地估算，负责上下文预算和自动压缩。
- 响应后：优先显示 provider 实报，进入 `/usage`、session metadata、右侧状态和子智能体任务记录。

## 2026-05-05：补齐子智能体模型输入 tokens 显示

### 背景

用户指出前一次“子智能体显示对齐”偏到了状态展示，真正要排查的是子智能体的 tokens 显示。此前右侧栏和子智能体详情面板只显示工具调用数、工具输出 bytes，只有发生 in-flight compact 时才偶尔出现 `ctx≈...`，无法判断每个子智能体自己的模型输入 tokens 是否接近上下文上限。

### 处理

- `src/agents/runner.js`
  - 子智能体每次向 gateway 发起模型请求前，使用和主智能体相同的 `estimatePromptPayload()` 估算逻辑。
  - 估算口径跟随实际 gateway 协议：`lab-agent-gateway` 和 `openai-chat` 都按真实请求体形状计算。
  - 将最近一轮子智能体模型输入诊断写入 task 的 `budgetProgress`：
    - `promptBytes`
    - `promptTokens`
    - `promptRound`
    - `maxTokens`
    - `promptMessageTokens`
    - `promptToolSchemaTokens`
    - `promptToolResultTokens`
  - 工具执行后的进度更新会保留最近一次 prompt token 估算，不再把 token 字段覆盖掉。

- `src/cli/tui/components.js`
  - 右侧“子智能体”面板在每个任务下显示 `模型输入 <tokens>/<maxTokens> tokens（估算）`。
  - 这和主会话右侧栏的“模型输入 tokens/上下文上限”保持同一类语义。

- `src/cli/tui/command-panels.js`
  - 子智能体详情/实时面板的“预算/上下文”区域显示：
    - `模型输入≈x/上限 tokens`
    - `模型轮=n`
    - `拆分：消息 / 工具定义 / 工具结果`
  - 用于判断子智能体是否被工具输出、工具 schema 或历史消息撑大。

- `tests/unit/agents.test.js`
  - 增加子智能体 task 记录落盘 token 诊断字段的回归测试。

- `tests/unit/tui-frame.test.js`、`tests/unit/tui-command-panels.test.js`
  - 增加右侧栏和详情面板展示 token 估算的回归断言。

### 验证

```powershell
node --test tests\unit\agents.test.js tests\unit\tui-frame.test.js tests\unit\tui-command-panels.test.js
```

结果：`65 pass / 0 fail`。

### 结论

现在主智能体和子智能体的 tokens 显示口径已经基本对齐：

- 主智能体：会话级最近模型输入 tokens。
- 子智能体：每个 task 的最近模型输入 tokens。
- 二者都用本地估算，展示时明确标注“估算”。

如果后续 gateway 返回 provider 级 `usage.prompt_tokens`，可以再扩展为“本地估算 / provider 实报”双轨显示。

## 2026-05-05：对齐子智能体显示链路，补齐任务组与后台完成状态

### 背景

用户指出子智能体相关显示仍有不同步的问题，需要把聊天框、右侧栏和 `/agents` 输出统一对齐，避免后台任务组已经启动但界面仍显示“暂无子智能体任务”，或者后台任务完成后聊天卡还停留在“运行中”。

### 处理

- `src/cli/tui/components.js`
  - 右侧栏“子智能体”面板现在会同时显示单任务记录和任务组记录。
  - 当只有后台任务组、尚未产生可见单任务记录时，不再误报“本会话暂无子智能体任务”。
  - 任务组与单任务都使用一致的状态标记逻辑，`partial` 统一显示为 `[..]`，避免聊天区和侧栏出现不同符号。

- `src/cli/tui.js`
  - 切换会话时一并清空任务组缓存，避免旧会话的后台组残留在新会话侧栏。
  - 后台任务组完成/进度事件到达时，会按最新任务记录刷新聊天区里的子任务卡，不再长期停留在“子任务后台运行中”。
  - 子任务组自动唤醒主控的提示仍保留，但视觉上会先同步子任务本身的真实状态，再显示组完成。

- `src/commands/runtime.js`
  - `/agents tasks`、`/agents groups`、`/agents group <group-id>` 的输出文案改为中文状态词。
  - `/agents tasks` 现在明确提示用 `/agents task <task-id>` 查看详情、用 `/agents continue <task-id>` 续跑阶段暂停任务，减少 `resume` / `task` 语义重复。

- `src/agents/orchestrator.js`
  - 子任务树输出的收尾提示改为中文化的 `task/continue` 路线，和当前 UI 命名保持一致。

- `tests/unit/tui-frame.test.js`
  - 增加后台任务组先于任务记录出现的侧栏回归测试。
  - 增加阶段暂停任务在侧栏显示 `[..]` 的回归测试。

### 验证

```powershell
node --test tests\unit\tui-frame.test.js tests\unit\tui-format.test.js tests\unit\tui-command-panels.test.js tests\unit\commands.test.js tests\unit\tools.test.js tests\unit\session.test.js
npm run check
```

结果：

- 定向测试通过：`193 pass / 0 fail`。
- 全量检查通过：`490 pass / 0 fail`。

### 结论

这次修复主要是把“子智能体状态来源”统一起来：

- 聊天框看单任务真实状态。
- 右侧栏看单任务 + 任务组的聚合状态。
- `/agents` 看可恢复、可继续、可查看组的完整记录。

后续如果再补子智能体 UI，应该优先沿着这条状态链扩展，而不是另起一套展示口径。

## 2026-05-05：强化上下文预算诊断，并暂时关闭异常最终回复自恢复

### 背景

用户在 `E:\test-project\LBJ-workspace\new-ptoject` 的 AntScan 长任务中遇到两次异常生成：

- 一次最终回复只有 `Ver`。
- 一次最终回复像模型内部草稿，开头为 `Now I need to...`，并在短片段处截断。

会话 metadata 显示本轮 `status=completed`、`gatewayErrors=0`、工具调用均正常，但 `context.promptBytes=226549`、`promptRound=10`，且 token 计数字段被误脱敏成 `[redacted]`，无法事后判断是否接近上下文窗口或 provider 输出预算。

### 处理

- `src/core/session.js`
  - 每轮 gateway 请求前都执行 prompt budget 预检，不再只在 turn 第 0 轮检查。
  - 自动压缩触发从“硬上限才触发”改为带安全余量的阈值，默认 `0.82 * context.maxTokens/maxBytes`。
  - 第 0 轮触发时会强制执行会话级 `/compact` 路径；后续工具轮触发时会强制压缩旧工具结果，避免长工具输出继续塞进下一轮 prompt。
  - 每轮 gateway 请求/响应写入 `metadata.gatewayRounds[]`，包含 prompt bytes/tokens 估算、message/tool/schema 数、response text/thinking bytes、stopReason 和 provider usage。
  - 最终回复健康检查代码暂时保留但默认关闭，不会自动追加修复提示或重试模型请求；后续如需启用必须先人工确认。
  - `metadata.outputHealth[]` 结构保留，用于未来显式启用时记录。

- `src/core/inflight-compaction.js`
  - 增加 `force` 模式，供每轮 prompt budget 预检在已接近阈值时立即压缩旧工具结果。
  - 修复 `inFlightKeepRecentTools: 0` 不能生效的问题。

- `src/core/context-window.js`
  - 将 prompt 估算改为更接近实际网关请求体的字节估算。
  - OpenAI-compatible 协议下，已经作为 `role=tool` 消息进入 `messages` 的工具结果不再被 `toolResults` 重复计入。
  - lab-agent 原生协议继续按请求体中的 `messages + tools + toolResults + metadata` 估算。

- `src/storage/session-store.js`
  - 修复通用 metadata 脱敏过宽的问题：`promptTokens`、`maxTokens`、`*_tokens` 等数值诊断不再被当作密钥 token 脱敏。
  - 仍然继续脱敏 API key、secret、password、authorization、access token 等真正敏感字段。

- `tests/unit/session.test.js`
  - 增加后续工具轮触发 in-flight 压缩的回归测试。
  - 增加 `Ver` 异常最终回复在健康检查关闭时不会自动重试的回归测试。
  - 增加 session metadata 保留 token 诊断和 provider usage 的回归测试。

- `tests/unit/context-window.test.js`
  - 增加 OpenAI-compatible prompt 估算不重复计算已表示工具结果的回归测试。

### 结论

这次 AntScan 会话从现有证据看更像 provider/gateway 输出异常，而不是 Ant Code 本地权限或工具失败；但旧版本确实缺少足够的上下文诊断。新版本以后能更明确地区分：

- 上下文/工具结果接近预算导致的压缩或警告。
- provider 返回 `length/max_tokens` 等 stop reason。
- 模型把内部草稿或 reasoning 当最终正文吐出的异常。

注意：第三类目前只保留诊断/代码入口，自动重试默认关闭，避免未经确认增加额外模型轮次。

### 验证

```powershell
node --test tests\unit\context-window.test.js tests\unit\session.test.js
npm run check
```

结果：

- 定向上下文/会话测试通过：`34 pass / 0 fail`。
- 全量检查通过：`488 pass / 0 fail`。

## 2026-05-05：修复 TUI 启动期 requestExit 初始化顺序错误

### 背景

后台子智能体退出保护落地后，用户启动 `ant-code` / `node .\src\cli\index.js tui` 时遇到：

```text
Cannot access 'requestExit' before initialization
src/cli/tui.js:2183:64
```

这是 React 首次渲染 `TuiApp` 时触发的 JavaScript TDZ 问题：`submitInput` 的 `useCallback` 依赖数组提前读取了 `requestExit`，但 `requestExit` 的 `const` 定义位置在更下方。

### 处理

- `src/cli/tui.js`
  - 将 `runningBackgroundCount`、`requestBackgroundExit`、`requestExit` 三个退出相关 callback 移到 `submitInput` 之前。
  - 保持 `/exit`、Ctrl+C 二次退出、后台任务退出保护的行为不变，只修正初始化顺序。

### 验证

```powershell
npm run check:syntax
node --test tests\unit\tui-frame.test.js tests\unit\commands.test.js tests\unit\tools.test.js
npm run check
```

结果：

- 语法检查通过。
- TUI/命令/工具相关定向测试通过：`119 pass / 0 fail`。
- 全量检查通过：`484 pass / 0 fail`。

## 2026-05-05：区分“主控本轮结束”和“后台子任务仍在运行”

### 背景

用户实测后台子智能体任务组功能成功：子任务后台运行、完成后自动唤醒主控并汇总。但运行过程中发现一个状态表达问题：右侧栏还能看到后台子任务进行中，聊天框却因为 `agent_run background=true` 工具调用本身返回 `ok:true` 而显示“子任务完成”，容易误解为整个任务已经结束。

### 处理

- `src/core/session.js`
  - `agent_run` 的 `tool_finish.taskStatus` 优先采用工具返回的真实 `taskStatus` 或 `result.status`。
  - 后台 `agent_run` 启动成功时保持 `running`，不再被通用 `ok:true => completed` 推导覆盖。

- `src/cli/tui.js`
  - `running` 子任务在聊天区显示为“子任务后台运行中”。
  - `subagent_group_started` 显示为“子任务组后台运行中”，正文明确“后台运行中；完成后自动唤醒主控/仅记录结果”。
  - “子任务组完成”和“主控自动续跑”只在后台组真正达到等待条件并生成 wake prompt 后显示。

- `tests/unit/session.test.js`
  - 增加回归测试，确认后台 `agent_run` 的 finish 事件在 group wakeup 前保持 `taskStatus=running`。

### 验证

```powershell
node --test tests\unit\session.test.js tests\unit\tui-frame.test.js tests\unit\tools.test.js
```

结果：`93 pass / 0 fail`。随后继续执行全量检查。

## 2026-05-05：子智能体后台任务组与主控自动唤醒编排

### 背景

用户观察到，当前主控虽然已经有 delegation guard 提醒，但 `agent_run` 仍是“同一轮工具结果同步返回”的机制。模型派发子智能体后仍处在同一轮 assistant 生成中，容易急着自己继续收尾，不愿等待 reviewer、verifier 或 web-researcher 这类慢任务完成。对长任务来说，这会降低子智能体分工价值，也会让主会话吞掉更多工具上下文。

用户确认希望更接近 OMO 类“主控调度器”机制：主控派发后台子任务后可以结束当前阶段；后台组完成后，结果以 continuation prompt 的方式自动唤醒主控继续汇总、更新 todo、决定下一批分发或最终回答。

### 处理

- `src/tools/definitions.js`、`src/tools/runtime.js`
  - `agent_run` 增加 `background`、`groupId`、`waitForGroup`、`wakeParent`、`wakeReason`。
  - `background:true` 时先走同一套权限检查，再创建 task/group，启动独立后台 `AbortController`，立即把 taskId/groupId 返回给主控。
  - 后台任务不被普通主 turn 中断杀掉。
  - 任务完成后聚合 group 状态并生成短 wake prompt。
  - 支持 `waitFor=all/any/none`；`any` 现在按第一条终态任务触发组完成判断。

- `src/agents/task-group-store.js`、`src/agents/wakeup.js`、`src/agents/background-registry.js`
  - 新增 `.lab-agent/task-groups/<groupId>.json` 任务组存储。
  - 新增后台任务进程内 registry，支持按 session 或 group 列出、取消、判断是否仍在运行。
  - wake prompt 只放任务摘要、状态、task id 和主控下一步约束，避免把完整子任务输出塞回主会话。

- `src/core/session.js`
  - 接入 background group 事件转发。
  - 增加 `review gate`：最终回答前，如果有高风险 prompt、写入、partial/blocked 子任务、多步工作流状态反复变化且未看到 reviewer/verifier，会向模型可见上下文注入复核提醒。
  - 修复 review gate 误触发：普通 `token=...` 文本或测试 transcript 不会凭空多触发一轮模型请求。

- `src/cli/tui.js`、`src/cli/tui/components.js`
  - 聊天区显示“子任务组已启动 / 子任务组完成 / 主控自动续跑或已排队”。
  - TUI 空闲时收到 wake prompt 会自动调用主控继续处理；忙时进入队列。
  - 右侧“子智能体”面板顶部新增任务组聚合，显示 group id、状态、自动唤醒状态和最新进度，同时保留单任务工具/预算明细。
  - TUI 退出时，如果后台任务仍在运行，二次确认后先停止后台任务，等待任务完全停止后才允许真正退出。

- `src/commands/runtime.js`
  - 增加 `/agents groups`、`/agents group <group-id>`、`/agents wake <group-id>`、`/agents cancel-group <group-id>`。
  - `/agents cancel-group` 不只改 JSON 状态，还会中止当前进程内匹配 group 的后台 controller。

- `src/hooks/events.js`、`src/hooks/builtins.js`、`src/hooks/registry.js`
  - 新增 `subagent.group.started`、`subagent.group.completed`、`subagent.group.wakeup_queued`、`review.gate`。
  - `/logs` 和 hooks audit 能看到后台组生命周期和复核提醒。

- `src/context/builder.js`、`src/agents/profiles.js`
  - 主控 prompt 增加后台派发与等待语义：复杂/广域/慢任务使用 `agent_run background=true`、共享 `groupId`、`wakeParent=true`。
  - 子智能体 profile prompt 强调 bounded episode、结构化摘要、避免无意义 JSON 或超大原始输出。

- 文档：
  - 新增并完成 `docs/plans/completed/subagent-background-wakeup-orchestration-plan-2026-05-05.md`。
  - 更新 `docs/plans/README.md` 和 `LLM_ONBOARDING.md`。

### 验证

```powershell
node --test tests/unit/review-policy.test.js tests/unit/agent-task-group-store.test.js tests/unit/commands.test.js
node --test tests/unit/tui-frame.test.js tests/unit/tools.test.js tests/unit/agent-task-group-store.test.js
npm run check
```

结果：

- 定向测试均通过。
- 全量检查通过：语法检查、禁用端点扫描、来源校验、依赖策略、单元测试全部通过；`484 pass / 0 fail`。

### 剩余注意

- `agent_run` 默认仍保持同步，只有模型显式传 `background:true` 或配置 `defaultForModelAgentRun=true` 才会后台运行。
- 后台 wake prompt 是摘要，不包含完整子任务 transcript；完整输出仍通过任务详情/摘录层查看。
- Review gate 第一版是 remind，不硬阻断；如果模型仍长期跳过 reviewer/verifier，可再考虑配置级 require。

## 2026-05-04：新增 Delegation Guard，强化主控向子智能体派发

### 背景

用户实测发现，小米 `mimo-v2.5-pro` 作为主控时，即使 system prompt 已写明 delegation-first，仍经常自己调用 `web_search`、`web_fetch`、`grep`、`read_file` 或 shell 搜索命令完成联网研究和大范围代码排查。这样会把大量原始证据塞进主会话，浪费强模型上下文，也让子智能体面板无法体现实际协作。

对 oh-my-openagent 本地实现的审阅结论是：它对子智能体派发不是纯硬拦截，而是强 prompt 加运行时 hook 提醒；对模型/角色路由和特定 planning agent 权限才使用硬约束。因此本轮采用更适合 Ant Code 的混合策略：**强 prompt + 内置 delegation guard，默认只提醒不阻断**。

### 处理

- `src/context/builder.js`、`src/agents/profiles.js`
  - 强化主控提示词，把“建议优先派发”改成明确触发条件。
  - 仓库级排查、审计、重构、安全/性能/架构分析触发 `explorer`/`planner`。
  - 联网资料、GitHub/文档/最新信息触发 `web-researcher`。
  - UI/browser 行为触发 `browser-verifier`。
  - 明确主控直接读/抓只适用于单文件、单 URL 或子智能体已定位后的精确复核。

- `src/agents/delegation-guard.js`
  - 新增纯逻辑 guard 模块。
  - 按 turn 统计主控广域行为：`web_search`、GitHub/docs 类 `web_fetch`、广域 `glob`、根目录 `grep`、多文件 `read_file`、`rg/git grep/Get-ChildItem -Recurse/curl/wget` 等 shell 扫描。
  - 复杂 prompt 会降低触发敏感度。
  - `agent_run` 成功出现后标记本轮已委派，不再提醒。

- `src/core/session.js`
  - 将 guard 接入父会话工具执行链路。
  - 子智能体 runner 不走该链路，因此不会误伤子智能体内部的读/搜工具。
  - 达到阈值时，把 `[Ant Code delegation guard]` 提醒追加进工具 JSON 结果，使主控模型下一步能看到。
  - 同时发出 `delegation_guard` 事件。

- `src/hooks/events.js`、`src/hooks/registry.js`、`src/hooks/builtins.js`
  - 新增 `delegation.guard` 审计事件。
  - `/logs` 可看到 guard 触发记录，包括 level、tool、broadActions 和 reason。

- `src/config/load-config.js`、`lab-agent.config.json`、`config/lab-agent.*.json`
  - 增加 `agents.delegationGuard` 配置。
  - 默认启用 `mode=remind`，普通模板阈值 `3/5`，高敏模板阈值 `2/4`。
  - 支持 `enabled=false` 或 `mode=off` 关闭。

### 验证

```powershell
node --test tests/unit/delegation-guard.test.js tests/unit/config.test.js tests/unit/session.test.js
```

结果：

- 定向 47 项测试通过。
- 覆盖单 URL/单文件不误伤、广域仓库排查提醒、联网研究提醒、`agent_run` 后停止提醒、shell 全仓扫描识别、主会话工具结果注入提醒。

后续仍需观察真实模型行为：如果 Mimo 仍反复无视提醒，可以把第二阶段强提醒升级为要求下一步先调用 `agent_run`，但本轮暂不硬阻断。

## 2026-05-04：修复 agent_run 启动阶段误判为空 shell 命令和 blocked 任务 ENOENT

### 背景

用户继续实测 `verifier` 子智能体后，TUI 显示：

- `profile=verifier`
- 状态为“被权限策略阻止”
- 双击或 `/agents task <task-id>` 读取详情时出现 `ENOENT`，因为 `.lab-agent/tasks/<task-id>.json` 不存在。

模型自查进一步指出：此前修复的是“子智能体内部运行命令时的 execute profile 权限”，但这次失败发生在更早的“父会话启动 `agent_run` 工具”阶段。

### 根因

- `agent_run` 会根据目标 profile 计算风险：
  - `verifier` / `browser-verifier` 是 `mode: "execute"`。
  - 因此启动 `verifier` 的 `agent_run` 请求风险是 `execute`。
- `decidePermission()` 旧逻辑把所有 `risk === "execute"` 都交给 `decideCommand()`。
- `decideCommand()` 是专门给 `bash` / `powershell` 的 shell 命令分类器，需要 `request.command`。
- `agent_run` 不是 shell 命令，没有 `command` 字段，于是被误判为 `empty commands are not executable`。
- 另外，session 层会先分配 taskId 并发出 TUI 生命周期事件；但如果 `agent_run` 在权限审批阶段被拦，`runSubagent()` 没有进入，所以原本不会创建任务 JSON，导致详情视图读取 ENOENT。

### 处理

- `src/permissions/policy-engine.js`
  - 增加 `isShellCommandRequest()`。
  - 只有真正的 `powershell` / `bash`，或带有 `command` 字段的 execute 请求，才进入 `decideCommand()`。
  - 非 shell 的 `execute` 风险工具（例如 `agent_run` 启动 verifier）使用执行型工具权限语义：
    - `fullAccess`：直接允许。
    - `workspaceCommands` 已批准：允许。
    - 普通模式：ask。
    - readonly 锁定：deny。

- `src/tools/runtime.js`
  - `agent_run` 在权限拒绝或用户拒绝时调用 `writeBlockedAgentTaskRecord()`。
  - blocked 记录会写入 `.lab-agent/tasks/<task-id>.json`，包含 profile、状态、阻止原因、输出说明和 `AGENT_RUN_BLOCKED` 错误。
  - TUI 双击和 `/agents task <task-id>` 因此能打开详情，不再出现 ENOENT。

- 回归测试：
  - `tests/unit/permissions.test.js`
    - 覆盖 `fullAccess + agent_run(verifier)` 不再进入空 shell 命令拒绝。
    - 覆盖普通执行型 `agent_run` 返回 ask，且不是 `empty commands`。
  - `tests/unit/tools.test.js`
    - 覆盖 `fullAccess + verifier agent_run` 可以越过权限层，进入网关未配置失败路径，并创建正常失败任务记录。
    - 覆盖 blocked `agent_run` 会写 blocked 任务记录，供 TUI 详情视图读取。

### 验证

```powershell
node --test tests\unit\permissions.test.js tests\unit\tools.test.js tests\unit\agents.test.js tests\unit\session.test.js
npm run check
```

结果：

- 定向 114 项测试通过。
- 全量检查通过；462 项测试通过，0 失败。

## 2026-05-04：修复 verifier/browser-verifier 执行型子智能体权限映射

### 背景

用户在 `E:\test-project\LBJ-workspace\new-ptoject` 目录启动 Ant Code，让智能体自查三档权限和工具能力。桌面记录文件 `权限问题与报错.txt` 显示父智能体大部分工具正常，但 `verifier` 子智能体三次尝试执行命令都失败，并出现 `empty commands are not executable`。同一类风险也会影响 `browser-verifier`、`test-failure-triage`、`release-readiness-review`、`browser-automation` 等依赖执行型子智能体的工作流。

排查 `.lab-agent/sessions/0ab79fb4-f19b-4576-9ca8-9dff7927857e.json` 后确认：

- 该 session 已正常落盘为 `completed`，时间范围约为 2026-05-04 18:29:33 - 20:10:27（Asia/Shanghai）。
- transcript 尾部停在“要我开始修吗？”这类普通 assistant 回复，没有记录后续正式修复 turn。
- `.lab-agent` 下没有发现独立 crash/error 日志文件；因此本次“突然退出”更像发生在下一次输入或下一 turn 早期，未能写入 transcript。

### 根因

- `src/agents/runner.js` 的 `createAgentPolicy()` 把 `profile.mode === "execute"` 归入 readonly。
- 这会让 `verifier` / `browser-verifier` 的权限语义和产品设计不一致：
  - 它们应该“可运行验证命令，但不写源文件”。
  - 旧逻辑会在非完全访问场景下把它们当作只读代理，导致非 allowlist 命令被拒。
- 另外，部分模型可能会用 `cmd`、`script`、`commandText` 这类常见字段表达 shell 命令。旧 runtime 只认 `command`，因此会把真实意图误报成空命令。

### 处理

- `src/agents/runner.js`
  - 从 readonly 判定中移除 `execute` profile。
  - 将 `workspaceCommands` 自动同意范围扩展到 `write-capable` 和 `execute`，前提是父会话允许命令或处于完全访问模式。
  - 保持 `workspaceWrites` 只对有写 scope 的 `write-capable` profile 开放；`verifier` / `browser-verifier` 不获得写文件权限。

- `src/tools/runtime.js`
  - 在工具 schema 校验前对 shell 输入做轻量归一化。
  - `powershell` / `bash` 如果缺少 `command`，会尝试接受 `cmd`、`script`、`commandText`，减少模型字段名偏差导致的误判。

- 回归测试：
  - `tests/unit/agents.test.js`
    - 新增 `verifier execute subagent can run validation commands without write tools`，验证 `verifier` 能运行 PowerShell 验证命令，同时不会获得 `write_file` / `edit_file`。
  - `tests/unit/tools.test.js`
    - 新增 `shell runtime accepts common command field aliases`，验证 `cmd` 能被正确归一化为 shell 命令。

### 验证

- 定向测试：

```powershell
node --test tests\unit\agents.test.js tests\unit\tools.test.js tests\unit\permissions.test.js
```

结果：90 项通过，0 失败。

- 全量检查：

```powershell
npm run check
```

结果：语法检查、禁用端点扫描、来源校验、依赖策略、单元测试全部通过；458 项测试通过，0 失败。

### 剩余注意

- 本次没有找到独立 crash 日志，只能确认最新 session 文件本身是 `completed`。
- 如果后续仍遇到 TUI 直接退出，需要保留退出发生前后的终端输出，并优先检查下一 turn 是否出现未捕获异常。
- bash/WSL 环境中 `node` 不在 PATH 是环境限制；Windows PowerShell 下 node 正常。

## 2026-05-04：撤销子智能体默认模型-工具循环轮数上限

### 背景

用户在长任务实测中看到子智能体阶段性暂停，原因是“工具循环上限 64 轮”。这说明此前虽然已经撤销了 `maxToolCalls` 工具调用次数上限，但子智能体仍保留 `maxRounds` 模型-工具循环轮数上限；`explorer.deep` 等内置/配置预算会继续把 48/64/96 轮作为硬暂停条件。

这和当前产品策略冲突：TUI 已经具备子智能体实时工具动态、任务详情入口、手动中断、输出预算、运行时间预算、连续失败和权限拒绝保护阀。长任务不应再因为固定轮数被中途打断。

### 处理

- `src/agents/budget.js`
  - 默认 `maxRounds` 从 `64` 改为 `null`，表示子智能体默认没有固定模型-工具循环轮数上限。
  - 内置预算 `explorer.quick/deep`、`readonly-researcher`、`web-researcher`、`planner`、`junior`、`code-worker`、`verifier`、`reviewer`、`browser-verifier` 移除固定 `maxRounds`。
  - `checkBudget()` 只有在 `maxRounds` 是正整数时才触发 `maxRounds` 阶段暂停。
  - `normalizeBudget()` 支持 `maxRounds: null`，允许项目/用户配置显式表达“无限轮”。

- `src/agents/runner.js`
  - 子智能体主循环从 `for (... <= budget.maxRounds)` 改为无限循环，由最终回答、中断、运行时间、输出量、连续失败、权限拒绝等保护阀结束。
  - 保留显式 `agents.maxRounds` 或 `agents.budgets.*.maxRounds` 正整数配置的限轮能力，方便需要强保护的环境手动开启。

- 配置文件和模板：
  - `lab-agent.config.json`
  - `config/lab-agent.lab-template.json`
  - `config/lab-agent.high-sensitivity-template.json`
  - 移除 `explorer.deep`、`junior.deep`、`code-worker.deep` 等预算里的 64/96 轮固定上限。

- 展示层：
  - 子智能体任务详情预算行在没有固定轮数上限时显示 `rounds=无限制`。
  - 右侧子智能体列表中预算短标记从 `r?` 改为 `r∞`，避免用户误以为还有隐藏轮数上限。
  - `/agents route` 的预算展示把 null 格式化为 `无限制`。

### 保留边界

- `maxToolCalls` 默认仍为 `null`，不限制工具调用次数。
- 仍保留这些保护阀：
  - `maxDurationMs`
  - `maxOutputBytes`
  - `maxToolResultBytes`
  - `maxReadFileBytes`
  - `maxWebFetchBytes`
  - `maxConsecutiveFailures`
  - `maxPermissionDenials`
  - 用户手动中断
- 如果你未来想在特定高敏环境恢复轮数上限，可以在配置中显式写：

```json
{
  "agents": {
    "maxRounds": 200
  }
}
```

或针对单个 profile：

```json
{
  "agents": {
    "budgets": {
      "explorer.deep": {
        "maxRounds": 200
      }
    }
  }
}
```

### 验证

已执行：

```powershell
node --test tests\unit\agents.test.js tests\unit\agent-budget-contract.test.js tests\unit\agent-router.test.js tests\unit\agent-profiles-config.test.js tests\unit\config.test.js
npm run check
```

结果：

- 新增回归：默认 `maxRounds=null` 时，模型驱动 explorer 连续执行 70 轮工具调用后仍能正常完成，不再被旧 64 轮上限暂停。
- 显式 `maxRounds=2/3/5` 的配置限轮测试仍通过。
- 全量检查通过：语法、禁用端点、provenance、依赖策略和 456 个单元测试全部通过。

## 2026-05-04：三档权限链路严格审计和补漏

### 背景

用户指出：不只是“完全访问”要排查，`计划确认`、`工作区权限`、`完全访问` 三条权限链路都要查清楚，避免 UI 显示一种权限、工具层却按另一套边界执行。

后续实测发现：权限问题修完后，读取失败原因从 `path outside workspace` 变成了底层 `ENOENT`。这说明权限已经放行到工具层，但用户和模型仍看不清到底尝试读取了哪个路径，尤其 Windows 绝对路径被模型带外层引号时，容易变成不存在的相对路径。

本次按链路检查：TUI/CLI 会话状态、slash 命令 policy 生成、审批缓存、文件/文档工具、shell 命令、MCP/skill、子智能体继承。

### 处理

- 外部路径行为统一：
  - `计划确认`：工作区外读写会弹确认；确认后实际工具可以执行。
  - `工作区权限`：工作区内非敏感读写/常规命令自动同意；工作区外路径仍弹确认。
  - `完全访问`：文件、文档、shell、MCP、browser、network、memory、skill fork、子智能体都继承最高权限并自动同意。
- `document_intake` 修复：
  - 之前策略层把它当作文档读取直接 allow，但工具层仍报 `DOCUMENT_PATH_OUTSIDE_WORKSPACE`。
  - 现在工作区外文档也按外部读取弹确认，确认后放行。
- shell 命令路径边界补漏：
  - `Get-Content` 这类只读命令如果显式引用工作区外绝对路径，也会先弹确认。
  - 工作区权限下自动同意的命令如果引用工作区外绝对路径，也会转为确认。
  - `offline` 网络命令仍优先按网络策略 deny，不会被 URL 中的 `/...` 误判成路径确认。
- 审批缓存更精确：
  - `本会话允许同类请求` 的 key 增加 `sensitive/normal`、`outside/workspace`、具体 path/pattern/server/tool。
  - 避免“允许读取一个外部路径”后，另一个外部路径被粗粒度工具名缓存误放行。
  - TUI 使用 `Shift+Tab` 切换权限模式时，会清空本会话同类批准缓存，防止不同权限模式之间串味。
- slash 命令和子智能体继承最新会话权限：
  - `/mcp`、`/agents run`、`/agents continue`、`/agents orchestrate` 改为优先读取 `sessionInfo` 的最新权限，而不是启动时的旧 CLI 参数。
  - 保留 `/agents review` 的只读边界：复核子任务即使在完全访问下也不写文件，这是产品语义边界，不是权限漏传。
- slash 命令权限状态统一：
  - 新增统一的权限状态推导逻辑，`/status`、`/permissions`、`/memory add`、`/background worktree`、`/agents run/continue/orchestrate` 都从同一套 `permissionMode -> readonly/allowWrite/allowCommand/fullAccess` 状态生成策略。
  - 修复只传 `sessionInfo.permissionMode="fullAccess"`、但没有同步传 `fullAccess: true` 时，命令层显示和实际执行可能不一致的问题。
  - `/background worktree` 和 `/background cleanup-worktree` 现在也经过权限引擎；计划确认模式先询问，工作区权限/完全访问按当前模式执行后再进入 git worktree 前置条件检查。
- 文件/文档路径工具容错：
  - `read_file`、`list_files`、`edit_file`、`document_intake` 会剥离安全的外层引号，避免 `"C:\path\file.txt"` 被当成带引号字符的假路径。
  - 真实不存在的文件不再只暴露 `ENOENT`，而是返回 `FILE_NOT_FOUND` / `DIRECTORY_NOT_FOUND` / `DOCUMENT_NOT_FOUND`，并带上解析后的路径和原始输入 path。
- shell 路径扫描误报修复：
  - 修复 `.lab-agent/worktrees/task-id` 这类嵌套相对路径被扫描器截出 `/worktrees/` 并误判为 `C:\worktrees` 的问题。
  - 增加回归测试，确保工作区权限下的相对 worktree 路径不会被错误当成工作区外路径确认。

### 保留边界

- Git pathspec 仍限制在当前 repo/workspace 内，这是 Git 工具语义边界。
- mention picker 仍只浏览当前 workspace，这是 UI 选择器语义边界。
- 子智能体 worktree 路径仍由 `.lab-agent/worktrees` 管理，不接受任意外部 worktree 根。

### 验证

已执行：

```powershell
node --check src\commands\runtime.js
node --test tests\unit\commands.test.js tests\unit\permissions.test.js tests\unit\tools.test.js tests\unit\mcp.test.js tests\unit\tui-format.test.js
npm run check
```

结果：

- 针对性权限链路测试：159 pass / 0 fail。
- 全量检查：语法、禁用端点、provenance、依赖策略和 454 个单元测试全部通过。

## 2026-05-04：修复 ask_user 确认选项和自定义输入重叠

### 背景

用户反馈：模型用 `ask_user` 确认需求时，A/B 选项和“自定义”输入栏出现重叠。复查后确认，新增底部权限模式提示条后，TUI 的可视布局已经为权限条预留了 1 行，但底层终端光标定位仍按旧的“输入框下方只有 footer”计算，导致 question 模式下自定义输入光标可能写到选项区域，视觉上表现为选项和自定义栏重叠。

### 处理

- `src/cli/tui/layout.js`
  - `resolveTuiFrame()` 的 `prompt` 区域计算纳入 `permissionFooterRows`。
  - 新增 `permissionFooter` 区域，让 PromptBox、权限提示条和 FooterBar 在 frame 层有明确顺序。

- `src/cli/tui.js`
  - `positionTerminalCursorForComposer()` 不再用 `size.rows - 2` 估算输入区行号。
  - 光标定位改为读取真实 `frame.regions.prompt`，因此 question 模式、多行输入、权限提示条和 footer 之间不会互相覆盖。

- `tests/unit/tui-frame.test.js`
  - 增加回归测试：question prompt 下 `permissionFooter` 必须位于 composer 下方，footer 位于权限条下方，三者不重叠。

### 验证

已执行：

```powershell
node --check src\cli\tui.js
node --check src\cli\tui\layout.js
node --test tests\unit\tui-frame.test.js tests\unit\tui-format.test.js tests\unit\tui-scroll-region.test.js
```

结果：相关语法检查通过，55 个 TUI 布局/格式测试全部通过。后续已继续执行全量检查。

## 2026-05-04：修复完全访问模式下文件工具仍报 workspace 外路径

### 背景

用户反馈：已经切换到“完全访问”权限，但模型调用工具时仍会报 `path outside workspace`。复查后确认，权限引擎层已经支持 `fullAccess` 并返回 allow，但文件/文档工具内部仍有旧的 `resolveWorkspacePath()` workspace-only 硬校验，导致“审批层允许，工具执行层拒绝”的不一致。

### 处理

- `src/tools/runtime.js`
  - 调用内置工具时把当前会话 `policy` 传入工具执行层。
  - 调整参数合并顺序，确保 `policy` 只能来自会话运行时，模型工具参数不能伪造 `fullAccess`。

- `src/tools/file-tools.js`
  - `read_file`、`list_files`、`glob`、`grep`、`write_file`、`edit_file` 在 `policy.fullAccess` 为真时允许绝对路径或跳出 workspace 的路径。
  - 普通/工作区权限仍保留 workspace 边界和 symlink escape 防护。
  - workspace 外路径返回时使用可识别的绝对显示路径，workspace 内仍返回相对路径。

- `src/tools/document-tools.js`
  - `document_intake` 在完全访问模式下允许读取 workspace 外的本地文档。

- `src/tools/definitions.js`
  - 更新工具说明，明确完全访问模式可以处理 workspace 外本地路径。

- `tests/unit/tools.test.js`
  - 增加完全访问读写 workspace 外文件的回归测试。
  - 增加工作区权限仍不能写 workspace 外文件的回归测试。
  - 增加完全访问读取 workspace 外文档的回归测试。

### 验证

已执行：

```powershell
node --check src\tools\runtime.js
node --check src\tools\file-tools.js
node --check src\tools\document-tools.js
node --test tests\unit\tools.test.js tests\unit\permissions.test.js
```

结果：语法检查通过，55 个权限/工具测试全部通过。

## 2026-05-04：修复摘录层鼠标选区被动态刷新擦除

### 背景

用户反馈：摘录层刚修好后可以稳定用鼠标选择片段，但近期又出现“选中一会儿白色选区自动消失”。复查后确认，摘录层虽然已经不再渲染动态状态栏和页脚，但后台仍可能因为模型忙碌/流式输出的 `pulse` 心跳、运行中子智能体任务轮询、以及消息块实时同步 effect 触发 Ink 重绘。终端原生鼠标选区一旦遇到 TUI 重绘，就会被擦掉。

### 处理

- `src/cli/tui.js`
  - `message-excerpt` 打开时暂停 `pulse` 心跳定时器，并把 `commandPanel.kind` 加入依赖，确保进入摘录层的瞬间会清理旧 interval。
  - `message-excerpt` 打开时暂停子智能体/后台任务列表轮询，避免运行中任务每秒刷新擦除选区。
  - `message-excerpt` 打开时不再根据 `selectedEntry` 变化重建摘录 panel，防止后台 transcript 或任务记录变化引起静态摘录层刷新。
  - 退出摘录层后仍恢复正常 TUI 鼠标滚动模式。

### 验证

已执行：

```powershell
node --check src\cli\tui.js
node --test tests\unit\tui-frame.test.js tests\unit\tui-command-panels.test.js
```

结果：

- 相关语法检查通过。
- 42 个 TUI 面板/布局测试全部通过。
- `npm run check` 全量通过：语法、禁用端点、来源、依赖策略和 428 个测试全部通过。

## 2026-05-04：输入区新增当前权限模式提示

### 背景

用户指出：当前没有一个足够直观的位置展示 Ant Code 正处于哪种权限模式。虽然状态栏和 `/permissions` 能查看权限，但长任务和频繁切换权限时，最好在输入区附近常驻显示，避免误以为已经处于“工作区权限”或“完全访问”。

### 处理

- `src/cli/tui/components.js`
  - 新增 `PermissionFooter`，固定显示在输入框下方。
  - 三档权限用不同颜色区分：
    - `计划确认`：绿色，表示风险最低，写入、命令和外部能力需要确认。
    - `工作区权限`：黄色，表示有自动执行风险，工作区内常规操作会自动同意。
    - `完全访问`：红色，表示测试机最高权限，所有本地工具、MCP、浏览器、网络和任意路径操作自动同意。
  - 右侧固定显示 `Shift+Tab 切换`，把切换入口放在高频视野里。
  - 说明文字按终端宽度做单行截断，避免小窗口下把输入区挤坏。

- `src/cli/tui.js`
  - 将权限提示条接入主 TUI 布局，位置在 `PromptBox` 和页脚快捷键提示之间。
  - `resolveTuiLayoutRows()` 增加 `permissionFooterRows=1`，保证主聊天区、斜杠命令面板和会话面板都把这行纳入高度计算。

- `src/cli/tui/format.js`
  - 将计划模式的短标签统一为 `计划确认`，和 `/keybindings`、`/permissions` 的三档文案保持一致。

- `tests/unit/tui-frame.test.js`
  - 增加权限提示条渲染测试，覆盖三档模式和窄窗口截断。
  - 更新底部弹层/会话面板布局测试，确保新增 1 行不会破坏终端高度预算。

### 验证

已执行：

```powershell
node --test tests\unit\tui-frame.test.js
node --check src\cli\tui.js
node --check src\cli\tui\components.js
node --check src\cli\tui\format.js
```

结果：

- `tui-frame` 23 个测试全部通过。
- 相关 TUI 文件语法检查通过。
- `npm run check` 全量通过：语法、禁用端点、来源、依赖策略和 428 个测试全部通过。

## 2026-05-04：核查并修复子智能体完全访问权限传递

### 背景

用户要求确认：子智能体在“完全访问权限”下是否真的具备不被权限层拦截的能力。代码审查发现，权限引擎本身已经会在 `fullAccess` 下自动允许本地工具、MCP、browser、network、memory、路径访问和非空 shell 命令；但子智能体 runner 仍有一层非权限审批的硬约束：write-capable profile 在没有 `writeScope` 时会移除写入/命令/MCP/skill 等工具，并把策略置为 readonly。这导致“完全访问”对 `junior` / `code-worker` 的写入能力仍可能不完整。

### 处理

- `src/agents/runner.js`
  - `fullAccess` 下不再因为缺少 `writeScope` 移除 write-capable 子智能体的写入、命令、MCP、skill 和 workflow 工具。
  - `createAgentPolicy()` 在 `fullAccess` 下不再把缺少 `writeScope` 的 write-capable profile 降级成 readonly。
  - `fullAccess` 下对子智能体内部工具策略设置 `workspaceWrites/workspaceCommands=true`，确保传入 tool runtime 的权限策略和测试机最高权限一致。
  - user prompt 中不再在 `fullAccess` 下提示“缺少 writeScope，写工具已禁用”，避免模型被旧提示误导。

- `tests/unit/agents.test.js`
  - 增加回归测试：`junior` 在 `fullAccess` 下即使没有 `writeScope`，仍能收到 `write_file` / `powershell` 工具并成功写入文件。

- `tests/unit/tools.test.js`
  - 增加回归测试：`agent_run` 在 `fullAccess` 下启动 write-capable 子智能体不会触发审批回调。

### 当前边界

- `fullAccess` 放开的是权限审批和 writeScope 降级，不会凭空给某个 profile 增加其本来没有声明的工具。例如 `reviewer` 本身不含 `write_file`，仍保持只读复核分工。
- 如果要让任意子智能体都能写文件，需要改变 profile 工具定义；目前保持“profile 是能力/职责边界，fullAccess 是审批/权限边界”的设计。

### 验证

已执行：

```powershell
node --test tests\unit\agents.test.js
node --test tests\unit\tools.test.js
npm run check
```

结果：`npm run check` 通过，427 个测试全部通过。

## 2026-05-04：稳定摘录页鼠标选区，并放开完全访问下的 skill fork 工具白名单

### 背景

用户反馈：在摘录页中用鼠标拖选文字时，白色选区会自动消失，导致不知道是否已经选中/复制成功。复核后判断原因不是“退出后选区残留”，而是摘录页仍带动态状态栏和页脚，TUI 心跳刷新会不断重绘屏幕，从而冲掉终端原生选区。

用户还指出：完全访问权限下，`skill_run` 仍受 skill frontmatter 的 `allowed-tools` 硬限制影响，导致最高权限无法直接使用 `web-research` / `browser-automation` 这类能力，需要绕到特定 profile 的子智能体。这个行为和“测试机完全访问模式”的预期不一致。

### 处理

- `src/cli/tui.js`
  - 摘录页渲染改为静态内容层，不再显示动态 `StatusBar` 和 `FooterBar`。
  - 保留摘录页原生鼠标选择模式，避免 pulse/spinner/cursor 刷新覆盖终端白色选区。
  - 退出摘录页时仍恢复正常 TUI 鼠标模式，但不主动清掉用户刚选中的文本。

- `src/tools/runtime.js`
  - `skill_run` 的 fork skill 在普通权限下继续尊重 skill 的 `allowed-tools`。
  - 当父会话处于 `fullAccess` 时，fork skill 使用其基础 agent profile 的完整工具集，不再被 skill `allowed-tools` 当作硬墙挡住。
  - system 提示中明确记录 full access 已激活，说明这是父会话显式授权的测试机模式。

- `tests/unit/tools.test.js`
  - 增加回归测试：skill frontmatter 只允许 `skill_list`，但在 `fullAccess` 下，基于 `web-researcher` 的 skill fork 仍可调用 `web_fetch`。

### 验证

已执行：

```powershell
node --test tests\unit\tools.test.js
node --test tests\unit\tui-frame.test.js tests\unit\tui-command-panels.test.js
npm run check
```

结果：`npm run check` 通过，425 个测试全部通过。

## 2026-05-04：子智能体详情层改为显示最新尾部输出

### 背景

用户指出：如果子智能体详情层的输出预览有显示上限，而预览一直停留在开头内容，那么后续即使子智能体仍在运行，界面也会像卡住一样。这会削弱运行态详情层“确认后台还活着”的价值。

### 处理

- `src/cli/tui/command-panels.js`
  - 子智能体详情层标题从“输出预览”调整为“最新输出预览”。
  - 当输出超过预览行数时，改为显示尾部最新内容，而不是固定显示开头。
  - 在尾部预览前提示“上方还有 N 行；这里显示最新内容”，并继续提示可用 `Enter/C` 进入冻结摘录层查看完整内容。
  - 工具调用列表仍保持“最近 12 条”策略，和最新输出预览一起构成运行中活跃信号。

- `tests/unit/tui-command-panels.test.js`
  - 增加子智能体长输出测试，确认详情层不再展示旧开头行，而是展示最新末尾行。

### 验证

已执行：

```powershell
node --test tests\unit\tui-command-panels.test.js
npm run check
```

结果：`npm run check` 通过，424 个测试全部通过。

## 2026-05-04：修复同一终端反复启动 TUI 时起始确认界面黑屏

### 背景

用户反馈：第一次运行 `ant-code` 可以看到起始确认界面；用两次 `Ctrl+C` 退出后，在同一个终端再次运行 `ant-code`，确认界面只闪一下然后变黑，但按 `Enter` 仍能正常进入。这说明 TUI 输入状态还在，主要问题集中在终端备用屏幕/清屏/重绘状态恢复。

### 处理

- `src/cli/tui.js`
  - 启动后的 resize 初始化 effect 不再无条件清屏。
  - 首次 resize 只同步终端尺寸和鼠标模式；只有真正窗口尺寸变化后才执行完整清屏重绘。
  - 退出 TUI 时在离开备用屏幕、关闭 bracketed paste、恢复光标后，追加 reset/清行/换行序列，减少同一终端下一次启动残留在不可见或空白状态的概率。

### 验证

已执行：

```powershell
node --check src\cli\tui.js
node --test tests\unit\tui-frame.test.js tests\unit\tui-interaction.test.js
node --test tests\unit\tui-command-panels.test.js
npm run check
```

结果：`npm run check` 通过，422 个测试全部通过。

## 2026-05-04：摘录面板完整展示超宽 Markdown 表格

### 背景

用户确认主会话中表格超出聊天框时是否会被省略，并希望摘录面板承担“完整查看和复制”的职责。此前主聊天区会对大表格摘要或压缩列宽，摘录面板虽然关闭了“大表格摘要”，但仍按固定宽度渲染，超长单元格可能被截短。

随后用户指出：“超宽内容不能在表格内自动换行吗？这样列出来还叫表格？”因此本条记录同步修正：摘录层不应把表格退化成“行 N / 列名：内容”的清单，而应保持表格形态，在单元格内部折行。

### 处理

- `src/cli/tui/markdown-table.js`
  - `renderTable()` 增加 `wrapCells` 和 `minColumnWidth` 选项。
  - 新增表格内单元格折行渲染：当表格超过可用宽度时，每个单元格按列宽拆成多条物理表格行。
  - 折行后的每一行仍保持 `|...|` 管道表格形态，并继续标记 `noWrap`，避免二次软换行破坏边界。

- `src/cli/tui/command-panels.js`
  - 主聊天区策略不变：仍以摘要/压缩保护 TUI 边界，避免表格撑破布局。
  - 摘录面板强制使用完整表格渲染，并对超宽单元格做表格内自动换行，不再退化成键值清单。
  - “复制整段/复制到最新”的 assistant 表格复制路径同步：复制出的内容也是完整折行表格，不使用省略号。

- `tests/unit/tui-command-panels.test.js`、`tests/unit/tui-markdown-table.test.js`
  - 增加表格内折行测试，确认超宽表格仍由多行 `|...|` 表格行组成。
  - 确认长单元格内容按顺序完整保留，不出现省略号。
  - 确认剪贴板格式和摘录面板展示采用同一套折行表格逻辑。

### 验证

已执行：

```powershell
node --test tests\unit\tui-command-panels.test.js
node --test tests\unit\tui-markdown-table.test.js
npm run check
```

结果：`npm run check` 通过，423 个测试全部通过。

## 2026-05-04：子智能体卡片新增实时详情层和冻结摘录层

### 背景

用户希望子智能体不要再像黑箱一样只在结束后返回摘要。运行中需要能看到“它还活着、正在调用什么工具、预算/上下文是否接近上限”；但真正复制内容时又不能被实时刷新打断鼠标选择。因此本次把子智能体卡片从单层摘录改成双层模式。

### 处理

- `src/cli/tui/command-panels.js`
  - 新增 `createAgentTaskLivePanel()`，作为子智能体运行态详情层。
  - 详情层显示任务标题、task id、profile、状态、模型/路由信息、最新进度、预算/上下文进度、最近工具调用、输出预览、续跑提示和错误信息。
  - 详情层明确提示 `Enter/C` 进入冻结摘录层；冻结层继续使用无边框摘录面板，便于鼠标拖选复制。

- `src/cli/tui.js`
  - 双击普通助手/用户消息仍进入摘录面板。
  - 双击子智能体任务卡片改为先进入 `子智能体详情`。
  - 在详情层按 `Enter`、`C` 或 `E` 会冻结到子智能体摘录层。
  - 打开详情层时，即使右侧栏不在子智能体面板，也会继续轮询任务记录，保证运行态信息能刷新。
  - 详情层保持正常 TUI 鼠标/滚轮；只有冻结摘录层才切换到终端原生选择模式，避免刷新破坏局部复制。

- `src/agents/task-store.js`
  - 子智能体工具调用记录保留 `inputSummary`，让详情层能显示工具实际处理的目标摘要。

- `tests/unit/tui-command-panels.test.js`、`tests/unit/agent-task-store.test.js`
  - 覆盖子智能体实时详情层展示、冻结提示、预算/上下文进度、工具输入摘要持久化。

### 验证

已执行：

```powershell
node --test tests\unit\tui-command-panels.test.js
node --test tests\unit\agent-task-store.test.js
node --test tests\unit\tui-frame.test.js
npm run check
```

结果：`npm run check` 通过，420 个单元/集成测试全部通过。

## 2026-05-04：权限模式简化为计划、工作区权限、完全访问

### 背景

用户确认当前权限体系不需要保留旧的五档内部模式，希望 TUI 和真实后端行为都收敛为三档：

- `plan`：需要权限的写入、命令、MCP、浏览器和联网能力都要确认。
- `workspace`：工作区内非敏感写入和常规本地命令自动同意。
- `fullAccess`：专用测试机模式，所有本地工具、MCP、浏览器、网络和任意路径操作自动同意。

### 处理

- `src/cli/tui/format.js`、`src/cli/tui/command-panels.js`、`src/commands/registry.js`
  - TUI 权限循环只保留 `计划 -> 工作区权限 -> 完全访问`。
  - `/permissions` 面板、状态面板和 `/keybindings` 文案同步为三档权限。
  - “只读锁定”从模式名中拆出，作为独立状态显示，避免出现第四种模式名。

- `src/permissions/policy-engine.js`
  - 新增 `policy.fullAccess` 真实后端放行逻辑。
  - 完全访问模式会自动允许敏感路径、工作区外读写、MCP、浏览器、网络、memory 和 shell 命令。
  - 空 shell 命令仍按无效命令拒绝。

- `src/core/session.js`、`src/cli/index.js`、`src/cli/interactive.js`、`src/cli/tui.js`
  - `fullAccess` 从 CLI/TUI 入口贯通到会话、print mode、交互模式和 transcript metadata。
  - 新增 `--full-access` CLI 参数；`--auto-approve` 继续表示工作区权限。
  - 新会话默认继承当前 TUI 权限模式；恢复会话优先使用历史 metadata 中保存的权限模式。

- `src/commands/runtime.js`、`src/tools/runtime.js`、`src/agents/runner.js`
  - slash 命令、内置工具、MCP runtime、skill fork、agent_run 和子智能体运行时都接入 `fullAccess`。
  - `/status` 与 `/permissions` 输出补充 `permissionMode`、`permissionReadonlyLocked` 和 `fullAccess`。

### 验证

已执行针对性测试：

```powershell
node --test tests\unit\permissions.test.js tests\unit\tui-format.test.js tests\unit\tui-command-panels.test.js tests\unit\commands.test.js tests\unit\cli-args.test.js
```

## 2026-05-04：明确权限模式切换的生效边界

### 背景

用户确认 Shift+Tab 切换权限模式是否应当从下一次对话/命令生效，而不是改变正在运行中的模型轮次。代码检查确认：主模型轮次、子智能体和工具 runtime 都是在启动时读取权限快照，运行中切换不会重建当前轮次权限；但 TUI 文案只显示“模式已切换”，容易误解为会影响当前正在执行的轮次。

### 处理

- `src/cli/tui.js`
  - Shift+Tab 切换后，聊天区提示补充“后续提示/命令生效”。
  - 忙碌状态下切换时，额外说明“当前运行中的轮次保留启动时权限”。

- `src/commands/registry.js`
  - `/keybindings` 中的 Shift+Tab 说明同步为后续提示/命令生效。

### 验证

已执行针对性测试：

```powershell
node --test tests\unit\commands.test.js tests\unit\tui-format.test.js
```

## 2026-05-03：修复 Markdown 表格改造缺陷，并取消子智能体工具调用次数硬上限

### 背景

用户用 Ant Code 自身执行表格渲染改造计划，作为长任务能力测试。测试过程中观察到子智能体在探索阶段触到工具调用次数上限后失败，后续主智能体更少使用探索型子智能体。用户明确要求撤销子智能体工具调用次数硬上限。同时，复核发现表格改造存在三处问题：窄窗口表格仍可能撑破聊天框、代码块围栏被吞掉、摘录面板的表格复制策略需要重新定稿。最终产品决策是：主聊天区保守渲染以保护布局，摘录面板和消息块复制优先输出渲染后的对齐表格文本，而不是原始 Markdown。

### 处理

- `src/cli/tui/markdown-table.js`
  - 新增 Markdown 表格解析和渲染模块。
  - 保留 fenced code block 的 opening/closing fence 和语言标记，避免代码回答退化。
  - 大表格/极窄窗口摘要会按可用宽度截断，避免摘要本身撑破布局。
  - 支持调用方关闭“大表格摘要”，让摘录面板和复制路径可以输出完整渲染表格。

- `src/cli/tui/format.js`
  - assistant 正文按 Markdown 块处理。
  - 表格渲染改为在 `transcriptRows()` 已知真实聊天区宽度后执行，不再使用固定 120 列。
  - 表格行带 `noWrap`，但生成前已经按真实宽度压缩，窄窗口不会再撑破聊天框。

- `src/cli/tui/command-panels.js`
  - 消息摘录面板渲染 assistant Markdown 表格，便于在无边框摘录层中直接拖选干净文本。
  - 新增 display clipboard formatter，消息块复制和“从这里到最新”会复制渲染后的对齐表格文本。
  - 用户消息保持原始文本，不把用户输入中的 Markdown 表格自动重排。

- `src/cli/tui.js`
  - 消息块复制路径接入 display clipboard formatter，避免摘录面板和剪贴板输出不一致。

- `src/agents/budget.js`
  - 默认 `maxToolCalls` 改为 `null`。
  - `checkBudget()` 不再因为工具调用次数停止子智能体。
  - 仍保留模型-工具轮次、运行时间、输出字节、连续失败、权限拒绝等保护阀。

- `lab-agent.config.json`、`config/lab-agent.lab-template.json`、`config/lab-agent.high-sensitivity-template.json`
  - 移除默认子智能体 `maxToolCalls` 配置。

- `src/agents/runner.js`、`src/agents/router.js`、`src/cli/tui/components.js`
  - 文案从“工具预算/工具上限”调整为时间、输出、权限和轮次保护。
  - 子智能体侧栏不再显示工具调用次数上限，只显示已调用工具数和输出字节。

- `.gitignore`
  - 忽略整个 `.lab-agent/` 运行目录，避免测试/会话记录被误提交。

### 验证

已执行：

```powershell
node --test tests\unit\tui-markdown-table.test.js tests\unit\tui-format.test.js tests\unit\tui-command-panels.test.js tests\unit\agent-budget-contract.test.js tests\unit\config.test.js tests\unit\tui-frame.test.js
npm run check
```

结果：`npm run check` 通过，412 个测试全绿。

额外手工探针：

- 窄窗口 `width=50` 时，复杂中英文表格最大显示宽度从修复前的 114 降到 40。
- 代码块回复保留 ```js 和 closing fence。
- 模拟 500 次子智能体工具记录后，`checkBudget()` 不再返回 `maxToolCalls`。

## 2026-05-03：建立 Markdown 表格渲染改造计划和 Git 回档点

### 背景

用户发现当前 TUI 对 Markdown 表格类回答支持不足，表格会在聊天区割裂。经过对当前 Ink 渲染链路和 opencode 开源 TUI 渲染方式的对比，确认问题根因是 Ant Code 当前把 assistant 正文先拆成普通文本行，再做二次软换行，导致表格失去块级结构。

### 处理

- 在正式改造前提交当前已验收版本，作为失败时的 Git 回档点：

```text
a1a69c6 保存：表格渲染改造前稳定版
```

- 新增待审核计划文档：

```text
docs/plans/active/tui-markdown-table-rendering-plan-2026-05-03.md
```

- 计划明确本次只在现有 Ink TUI 内增加 Markdown 表格块级预处理和渲染，不再尝试整体迁移 OpenTUI。
- 计划包含 5 个阶段：表格解析、表格布局渲染、接入 transcript、自动测试、人工验证。

### 验证

- 提交前执行严格密钥扫描，确认仓库内没有 GitHub PAT、`tp-` 长 token、OpenAI/Anthropic 风格密钥。
- `git status --short` 在提交后为空，当前工作区干净。

## 2026-05-03：接入内置 GitHub 只读 MCP，避免 GitHub 调研依赖普通网页抓取

### 背景

用户确认 GitHub 任务中普通 `web_fetch` 抓 `github.com` HTML 页面容易被挡，希望不再依赖 Docker 版 GitHub MCP，也不希望为了 MCP 额外安装 Go 或本地二进制。需求是：让智能体可以像普通 MCP 一样调用 GitHub 能力，同时 token 只保存在本机环境变量，不写进仓库。

### 处理

- `lab-agent.config.json`
  - 新增 `github` MCP server，默认启用。
  - 使用 `node package:scripts/github-mcp-server.js` 启动内置只读 MCP 适配器，不依赖 Docker/Go。
  - `GITHUB_PERSONAL_ACCESS_TOKEN` 只通过 `envAllowlist` 从用户环境变量传入 MCP 子进程。
  - 配置 `GITHUB_READ_ONLY=1`，并只声明只读工具风险。
  - 给 GitHub MCP 单次请求配置 `requestTimeoutMs: 30000`，避免首次联网读取因 10 秒默认 MCP 超时误失败。

- `scripts/github-mcp-server.js`
  - 新增内置 GitHub 只读 MCP server。
  - 支持常用只读工具：
    - `get_file_contents`
    - `search_repositories`
    - `list_branches`
    - `list_releases`
    - `get_latest_release`
    - `list_issues`
    - `get_issue`
    - `list_pull_requests`
    - `get_pull_request`
    - `get_pull_request_files`
  - 文件内容通过 `raw.githubusercontent.com` 读取；仓库/issue/PR 元数据通过 GitHub REST API 读取。
  - token 仅从 `GITHUB_PERSONAL_ACCESS_TOKEN` 环境变量读取，不打印、不落盘。

- `src/mcp/runtime.js`
  - 支持 MCP server 参数中的 `package:` 前缀，把包内脚本解析为安装包根目录下的绝对路径。
  - 支持每个 MCP server 单独配置 `requestTimeoutMs`。

- `src/agents/profiles.js`
  - `readonly-researcher` / `web-researcher` 的 MCP 白名单加入 `github`。
  - GitHub 相关提示词改为优先使用 `github` MCP，其次 raw/API，最后才考虑普通网页 fetch。

### 验证

已执行：

```powershell
node --test tests\unit\mcp.test.js tests\unit\config.test.js tests\unit\agent-profiles-config.test.js
node scripts\check-syntax.js
```

结果：相关测试全部通过，语法检查通过。

已执行实际 MCP 读取验证：

```powershell
github MCP get_file_contents github/github-mcp-server README.md
```

结果：成功读取公开仓库 README，未打印 token。

## 2026-05-03：修复研究型子智能体在 GitHub 来源被挡后直接暂停的问题

### 背景

用户发现 `readonly-researcher` 在研究 GitHub 项目时，虽然已经成功抓取了 GitHub raw 文件、GitHub API contents 和搜索结果，但后续遇到多次 `github.com` 页面权限拒绝后直接进入“阶段暂停”，没有基于已有证据生成最终汇报。

### 原因

此前“网页来源失败预算达到后，停止继续抓取并要求模型基于已有证据生成最终报告”的兜底只对 `web-researcher` 生效。`readonly-researcher` 虽然承担同类研究任务，但仍按普通预算逻辑处理，达到 `maxPermissionDenials` 后会直接 partial。

### 处理

- `src/agents/runner.js`
  - 将失败预算后的最终报告兜底扩展到 `readonly-researcher`。
  - `readonly-researcher` 和 `web-researcher` 现在都会在权限拒绝/连续失败达到保护阀时停止继续调用工具，并用已有成功搜索/抓取结果生成最终报告。
  - 修复“累计权限拒绝已经达标，但最后一次工具调用是成功抓取 raw/API 来源”时仍被判为普通预算暂停的问题。现在研究型子智能体一旦命中来源拒绝保护阀，就会切入无工具最终汇报，不再因为累计拒绝计数把已有证据丢成 partial。

- `src/agents/profiles.js`
  - 为 `readonly-researcher` 和 `web-researcher` 增加 GitHub 来源策略：
    - 已知文件优先使用 `raw.githubusercontent.com`。
    - 目录发现优先使用 `api.github.com` contents endpoint。
    - 避免反复抓取被挡的 `github.com` HTML 页面。
    - 多个来源被阻止时，把 blocked URL 放入 caveats，并基于已成功证据汇报。

- `tests/unit/agents.test.js`
  - 新增 `readonly-researcher` 连续 GitHub fetch 被挡后仍生成最终报告的回归测试。
  - 新增“GitHub HTML 多次被挡，但 raw/API/可访问来源已有成功证据”的混合序列回归测试，覆盖用户实测的 U-Net 调研类场景。

- `tests/unit/agent-profiles-config.test.js`
  - 增加 GitHub raw/API 策略和最终报告兜底提示词断言。

### 验证

已执行：

```powershell
node --test tests\unit\agents.test.js tests\unit\agent-profiles-config.test.js
```

结果：23 个测试全部通过。

## 2026-05-03：增强主智能体强委派提示词，降低父会话 token 浪费

### 背景

用户反馈主智能体虽然知道有子智能体，但实际使用时仍常常自己读取项目文件和网页资料，导致最强模型承担大量低价值上下文消耗。随后对比公开 OMO 实现后确认：OMO 不是完全硬路由，而是通过强编排提示词、子会话工具、模型分层和 hook 模式组合，让主控 agent 更倾向于委派。

### 处理

- `src/context/builder.js`
  - 在全局 system prompt 中新增 `Delegation-first mandate`。
  - 明确父会话是“昂贵的全局注意力”，非平凡任务默认先编排再执行。
  - 规定非平凡任务判定：2 步以上、未知架构、多文件、联网资料、UI/浏览器验收、高风险、长 prompt、多 todo 等。
  - 要求仓库调查优先用 `explorer agent_run`，联网资料优先用 `web-researcher agent_run`，复杂实现前优先用 `planner` 和只读发现代理。
  - 强调早期探索使用 `modelTier=cheap`，让 `mimo-v2.5` 等低成本模型吸收批量文件/网页上下文。

- `src/agents/profiles.js`
  - 更新隐藏内置 `build` profile 的主控提示词。
  - 将“默认委派、直接执行是例外”的行为写入 build agent。
  - 要求非平凡任务进入：可见任务状态 -> 并行只读发现 -> 综合 -> 局部实现 -> 验证 -> 严格复核 -> 最终报告。
  - 明确不应由父会话直接做大规模仓库读取、宽泛 grep 或重复网页抓取。

- `tests/unit/context.test.js`
  - 增加全局启动上下文中强委派规则、低成本模型提示和 `mimo-v2.5` 的断言。

- `tests/unit/agent-profiles-config.test.js`
  - 增加 build profile 中强委派、批量读取约束、低成本模型分层和新控制流的断言。

### 验证

已执行：

```powershell
node --test tests\unit\context.test.js tests\unit\agent-profiles-config.test.js tests\unit\agent-router.test.js tests\unit\agents.test.js
```

结果：31 个测试全部通过。

## 2026-05-03：修复 TUI 输入栏长单行内容被截断不可见

### 背景

用户发现一个 P0 体验问题：TUI 输入栏只能显示一行，输入超过一行宽度的内容后，后半段会像被“吞掉”一样不可见，用户无法确认自己正在输入或粘贴的长 prompt。

### 原因

输入编辑器原本只按显式换行符 `\n` 拆分草稿行，不会按终端输入框宽度做软换行。第一轮修复后，软换行只在组件渲染时生效，但真实 TUI 调用 `resolveTuiLayoutRows()` 时没有把 `width` 传入高度估算，导致外层仍按单行输入框分配高度，续行被裁掉。渲染层还只给 prompt 前缀上色，续行内容会落回默认白色，视觉上像覆盖了前面的输入。

### 处理

- `src/cli/tui/input-editor.js`
  - `visibleDraftLineEntries()` 支持按显示列宽软换行。
  - `composerSegments()` 支持传入 `columns`，并在软换行后仍正确保留 cursor 段。
  - 软换行逻辑考虑中文等宽字符显示宽度，避免宽字符撑破输入框。
  - 新增输入框垂直光标移动逻辑，支持在显式多行和软换行视觉行之间用 Up/Down 移动。

- `src/cli/tui/format.js`
  - `promptLines()` / `promptDraftLines()` 支持 `draftColumns`。
  - 普通输入、busy 队列输入、ask_user 自定义回答都使用相同软换行逻辑。

- `src/cli/tui/components.js`
  - `PromptBox` 按实际输入框宽度传入可用列数。

- `src/cli/tui.js`
  - 主 TUI 调用 `resolveTuiLayoutRows()` 时传入真实终端 `width`，确保高度估算和组件渲染使用同一个输入框宽度。
  - `estimatePromptBoxRows()` 使用相同宽度估算输入栏行数。
  - 普通输入框外框最多 5 行，内部最多显示光标附近 3 行草稿；长输入通过 Up/Down 在输入框内移动查看，避免过度挤占上方聊天区域。
  - 普通输入态中，只要输入框有内容，Up/Down 优先在输入草稿的视觉行之间移动光标；聊天区继续由鼠标滚轮、PageUp/PageDown 等方式滚动，Ctrl+Up/Down 保留为历史 prompt 调取。

- `src/cli/tui/components.js`
  - 输入栏所有文本段统一使用 prompt 颜色，避免续行变成默认白色。

### 验证

已执行相关 TUI 单测：

```powershell
node --test tests\unit\tui-input-editor.test.js tests\unit\tui-format.test.js tests\unit\tui-frame.test.js tests\unit\tui-command-panels.test.js
```

结果：63 个测试全部通过。

已执行全量检查：

```powershell
npm run check
```

结果：语法检查、禁用端点扫描、provenance、依赖策略和 366 个测试全部通过。

## 2026-05-03：修复子智能体运行时边界与提示词契约二轮问题

### 背景

用户给出五项严格 review finding，集中在子智能体运行时边界和提示词契约不一致：

- `code-worker` 提示词要求缺少 `writeScope` 不写，但运行时没有像 `junior` 一样硬限制写工具。
- `browser-verifier` 是浏览器验收角色，但 `agent_run` 权限风险仍接近普通 execute/read 语义。
- 主 system prompt 中对子智能体并发/串行规则存在重复段落，容易让模型抓到旧规则。
- 多个 profile 的 `outputContract.required` 字段和自然语言 `Return:` 字段不完全一致。
- `build` profile 是完整父级主控，若作为普通子智能体暴露，会误导用户和模型。

### 处理

- `src/agents/runner.js`
  - 将 `requiresWriteScope()` 扩展为所有 `write-capable` profile，而不再只依赖个别 profile 名称。
  - 当写入型子智能体缺少 `writeScope` 时，运行时移除：
    - `write_file`
    - `edit_file`
    - `powershell`
    - `bash`
    - `mcp_call`
    - `skill_run`
    - `todo_write`
    - `plan_update`
  - 同时把子智能体 policy 强制为 readonly，避免“提示词说不能写，但运行时仍有写能力”的漂移。
  - 新增 `allowHiddenProfile` 内部开关：普通 `runSubagent` 不再能启动 hidden profile，但 `skill_run` 这类内部生成的 hidden skill 子代理可以显式运行。

- `src/tools/runtime.js`
  - 新增 `agentRunRisk(profile)`：
    - `browser-verifier` / `purpose: browser` 使用 `browser` 风险。
    - `write-capable` 使用 `write` 风险。
    - `execute` 使用 `execute` 风险。
    - 其他默认 `read`。
  - `skill_run` fork 子代理通过内部 `allowHiddenProfile: true` 运行，避免 hidden 语义收紧后误伤项目 skill。

- `src/context/builder.js`
  - 清理重复的本地能力/编排说明。
  - 保留 `Subagent routing guide` 和 `Complex-task orchestration` 作为唯一权威路由策略。

- `src/agents/profiles.js`
  - `build.hidden = true`，并将 profile 列表/普通 profile 获取逻辑改为默认过滤 hidden。
  - 普通 `/agents`、`/capabilities`、正常 `agent_run` 和正常 `runSubagent` 不再展示或启动 `build/default`。
  - 只有内部显式 `includeHidden` 的调用才能获取 hidden profile。
  - 对齐 output contract 字段：
    - `explorer` 增加 `confidence`。
    - `planner` 增加 `assumptions`、`writeScopeSuggestions`、`handoffPrompt`。
    - `verifier` 使用 `recommendedNextFix`、`residualValidationGaps`。
    - `code-worker` 增加 `needsParentAction`。

- `LLM_ONBOARDING.md`
  - 记录 hidden `build` 是父级协调器 doctrine，不是普通子智能体。
  - 记录写入型子智能体必须有 `writeScope`，否则运行时移除写/命令/MCP call/skill run/工作流写工具。
  - 记录 `browser-verifier` 在 `agent_run` 边界使用 browser-risk 审批。
  - 记录 profile output contract 必须和自然语言 Return 字段保持一致。

### 二轮复核补充

初轮修复后发现一个延伸问题：仅把 `build` 标记为 hidden 还不够，默认 `getAgentProfile()` 仍可直接取到 hidden profile，导致 `/agents run build` 或模型 `agent_run build` 仍有机会把父级主控当子智能体启动。

二轮修复后：

- `listAgentProfiles()` 默认不返回 hidden profile。
- `getAgentProfile()` 默认不返回 hidden profile，包括 hidden alias。
- 只有 `includeHidden: true` 的内部调用可以访问 hidden profile。
- 新增测试验证：
  - 普通 profile 标签不包含 `build/default`。
  - 普通 `runSubagent({ profileName: "build" })` 返回 `AGENT_PROFILE_NOT_FOUND`。
  - `skill_run` fork hidden skill 子代理仍然可用。

### 验证

已执行定向测试：

```powershell
node --test tests\unit\agents.test.js tests\unit\tools.test.js tests\unit\agent-profiles-config.test.js tests\unit\context.test.js tests\unit\commands.test.js
```

结果：100 个测试全部通过。

已执行全量检查：

```powershell
npm run check
```

结果：语法检查、禁用端点扫描、provenance、依赖策略和 361 个测试全部通过。

## 2026-05-03：升级主智能体与子智能体提示词，补齐复杂任务编排协议

### 背景

用户检查主智能体和子智能体提示词后指出：当前基础分工已经存在，但提示词太短、太简单，尤其主智能体缺少复杂任务的设计。用户希望参考 oh-my-openagent 这类公开项目的多智能体编排思路：强主智能体负责全局调度和长任务状态，子智能体按角色、难度和模型档位做 one-shot 专项任务，再由主智能体回收、汇总、推进 todo 和继续分发。

### 处理

- `src/context/builder.js`
  - 新增 `Coordinator operating model`。
  - 要求主智能体先区分任务类型：直接回答、小型本地编辑、宽范围仓库任务、外部研究、UI/浏览器验收、高风险/安全/发布任务、阻塞/含糊任务。
  - 对宽范围或高风险任务明确控制循环：
    - `intake -> classify -> plan -> delegate readonly exploration -> synthesize -> implement scoped slices -> verify -> review -> report`
  - 要求主智能体维护 `todo_write` / `plan_update`，把它作为用户可见的长期任务地图。
  - 强化子任务调度规则：
    - 2-3 个独立只读 `agent_run` 可以同批并行。
    - 写入型、审批重、浏览器和 verifier 任务默认顺序推进。
    - 每个子任务要给出 `title`、`purpose`、`difficulty`、`risk`、`modelTier`、范围、输出期望和验收条件。
    - `cheap/default/strong` 模型档位要按任务难度和风险显式选择。
  - 明确主智能体拥有最终综合责任：不得把 raw child JSON、隐藏日志或未过滤 transcript 当最终答案直接丢给用户。

- `src/agents/profiles.js`
  - `build` 从简短身份说明升级为父协调器提示词，强调分类、规划、并发只读探索、综合、局部实现、验证、严格审查和最终报告。
  - `explorer` 强化为证据地图角色：先 `list_files/glob/grep/git_status/git_diff`，少量 `read_file maxBytes` 精读，输出 file/path 证据、置信度、未解问题和下一步。
  - `readonly-researcher` 强化本地/外部资料研究边界：区分事实、推断、不确定性和 follow-up。
  - `planner` 强化可执行计划输出：假设、约束、writeScope、doNotTouch、验收条件、验证梯度和 handoff prompt。
  - `verifier` 强化验证梯度：从最小命令到更大范围验证，失败时提取可修复原因，不输出原始长日志。
  - `code-worker` / `junior` 强化执行边界：必须尊重 writeScope/doNotTouch，不能扩大任务，不能回滚无关用户改动，长任务按可续跑切片返回。
  - `reviewer` 强化严格复核：优先 bug、回归、权限/安全、数据丢失、UX 破坏和缺失验证， findings first。
  - `web-researcher` 强化来源纪律：优先官方/主源/仓库/标准/变更日志，一个来源被拦不等于整个任务失败。
  - `browser-verifier` 强化 UI 验收：目标、启动方式、viewport、步骤、可复现观察、截图/文本证据、剩余未测场景。
  - 内部 `compaction` / `summary` / `title` 也补充了更明确的保留内容和过滤边界。

- `src/agents/runner.js`
  - 在每个子智能体请求的 system prompt 中新增 `Delegated operating doctrine`。
  - 统一要求子智能体把 delegated prompt 和 context pack 视为完整任务边界，不能接管父会话全部任务。
  - 要求按 checkpoint-first 工作：map -> inspect/fetch/run -> conclude。
  - 明确“证据够了就停止调用工具并写报告”，避免把预算耗尽在原始资料收集上。
  - 明确除非输出契约要求 JSON，否则不要输出 raw JSON，而是使用稳定标题和字段方便父智能体综合。

- `LLM_ONBOARDING.md`
  - 记录新的 coordinator 控制循环。
  - 特别提醒后续维护者不要把 profile prompt 缩回一行 persona。

### 参考方式

- 只抽取公开多智能体编排项目的架构思想：强主调度、角色分工、one-shot 子任务、难度/模型档位路由、结果回收和继续分发。
- 没有复制外部项目的私有源码或提示词文本。

### 验证

已执行定向测试：

```powershell
node --test tests\unit\context.test.js tests\unit\agent-profiles-config.test.js tests\unit\agents.test.js
```

结果：24 个测试全部通过。

已执行全量检查：

```powershell
npm run check
```

结果：语法检查、禁用端点扫描、provenance、依赖策略和 357 个测试全部通过。

## 2026-05-03：修正上下文 token 统计口径，纳入工具结果和文件读取内容

### 背景

用户指出：大模型读取文件后，文件内容实际会进入后续模型请求，理应计入上下文；但右侧栏和 `/context` 里的 token 数字看起来只统计了会话消息，没有反映刚读入的大文件内容。经检查，原实现的 `summarizeContextWindow()` 主要统计持久化 `session.messages`，而本轮工具调用产生的 `tool` message 是临时加入当前 gateway 请求的 `messages` 数组，参与模型输入但没有被 UI 的上下文数字完整体现。

### 处理

- 新增 `estimatePromptPayload()`，按实际发往网关的完整 payload 做本地估算：
  - `messages`：system prompt、workflow context、历史 transcript、本轮用户输入、assistant tool call、tool message。
  - `tools`：工具定义/schema。
  - `toolResults`：协议层可能单独携带的工具结果。
- `runSessionTurn()` 每次发送网关请求前都会计算：
  - `promptTokensEstimate`
  - `promptBytesEstimate`
  - `promptMessageTokensEstimate`
  - `promptToolSchemaTokensEstimate`
  - `promptToolResultTokensEstimate`
- TUI 的状态栏和状态面板从“transcript tokens”改为优先显示“最近模型输入 tokens”。
- `/context` 面板明确区分：
  - `最近模型输入`：最近一次真实网关请求的完整输入估算。
  - `已保留 transcript`：当前会话持久保留的用户/助手消息估算。
  - 拆分显示：消息 / 工具定义 / 工具结果。
- Slash `/status` 等文本摘要也从 `tokens=` 改为 `modelInput=` + `transcript=`，避免把两个口径混在一起。

### 重要说明

- 这是本地估算，仍不是供应商 tokenizer 的精确计数。
- 如果网关后续返回可靠的 provider `usage.prompt_tokens`，可以再把真实 usage 作为权威显示。
- 当前修复已经保证：`read_file` 等工具返回的大段文件内容，在下一次模型请求前会被计入“最近模型输入”估算，而不是只看持久 transcript。

### 追加修正：自动压缩触发也改用完整模型输入口径

用户进一步指出：如果显示统计口径原来有问题，那么自动触发 `/compact` 的判断也可能有同样问题。复查后确认：持久会话压缩原先主要看 `session.messages`，工具轮中虽然已有 in-flight tool result 压缩保护，但首轮请求前的 system prompt、工具 schema、workflow context 和完整 prompt payload 没有统一参与自动压缩判断。

已追加修正：

- 首轮 gateway 请求前先计算完整 prompt payload。
- 如果 `messages + tools + toolResults` 的估算 tokens/bytes 已超过上下文窗口，会先调用 `compactSessionContextWithModel()`，完成压缩后重建本轮请求。
- 自动压缩事件原因标记为 `automatic_prompt_budget`，方便 `/logs` 和后续审计分辨。
- 工具轮中间的 in-flight tool result 压缩会把工具 schema / toolResults 的固定开销预留出来，避免只压缩 message 部分但总 prompt 仍接近上限。
- 新增测试覆盖：完整 prompt payload 超预算时，会先请求 compaction agent，再发正常模型请求。

### 验证

已执行定向测试：

```powershell
node --test tests\unit\context-window.test.js tests\unit\session.test.js tests\unit\tui-command-panels.test.js tests\unit\commands.test.js
node --test tests\unit\session.test.js tests\unit\context-window.test.js
```

结果：相关测试全部通过。

已执行全量检查：

```powershell
npm run check
```

结果：语法检查、禁用端点扫描、provenance、依赖策略和 355 个测试全部通过。

## 2026-05-03：产品化“自动同意”权限模式，减少长任务确认风暴

### 背景

用户在长任务中遇到读写和命令审批弹窗过多的问题：一个任务可能需要连续确认几十次，严重影响使用体验。用户希望适当放开自动同意，但明确要求边界是“工作区外文件不自动同意”，敏感路径仍要强确认。

### 处理

- 将 TUI 中原来内部名为 `bypassPermissions` 的模式产品化为用户可理解的“自动同意”。
  - 状态栏、权限面板和模式切换提示不再显示 `bypass-local` / `bypassPermissions`。
  - 文案明确说明：自动同意只覆盖工作区内非敏感读写和常规本地命令。
- 新增 CLI 入口：
  - `--auto-approve`
  - `--auto-approve-workspace`
  两者都会启用当前会话的 `allowWrite=true` 和 `allowCommand=true`，方便长任务或 print mode 自动化。
- 保留更细粒度旧入口：
  - `--allow-write`
  - `--allow-command`
- 强化 shell 自动同意边界：
  - 结构化文件工具仍由文件工具自身保证不能写出工作区。
  - 对 `powershell` / `bash` 自动同意增加显式路径目标检查。
  - 当命令的 `-LiteralPath`、`-Path`、`-Destination`、`-OutFile`、常见写入命令首个路径参数或 shell 重定向目标指向工作区外时，不会自动放行，而是继续要求确认。
  - 修正第一次实现中过度匹配的问题：不会再把错误输出文本里的路径，例如 `Write-Error "path=C:\secret-project\file.txt"`，误判成真实文件目标。
- README 和 `LLM_ONBOARDING.md` 同步记录“自动同意不是无限 bypass”，避免未来维护时把安全边界改丢。

### 验证

已执行定向测试：

```powershell
node --test tests\unit\permissions.test.js tests\unit\session.test.js
node --test tests\unit\permissions.test.js tests\unit\tui-format.test.js tests\unit\tui-command-panels.test.js tests\unit\cli-args.test.js
```

结果均通过。

已执行全量检查：

```powershell
npm run check
```

结果：语法检查、禁用端点扫描、provenance、依赖策略和 352 个测试全部通过。

### 使用方式

- TUI：按 `Shift+Tab` 循环到“自动同意”模式。
- CLI：使用 `ant-code --auto-approve`。
- 该模式会减少工作区内长任务的普通读写/命令确认，但不会自动同意工作区外文件、疑似密钥路径、高危命令或联网命令。

## 2026-05-03：强化长任务子智能体编排和预算策略

### 背景

用户继续测试超长任务时指出：主智能体不应该只是取消自身工具轮次上限，还应该在面对大项目、多 todo、跨模块任务时优先规划并分批调用子智能体；同时子智能体预算不能继续被统一压在 16 轮，否则仍会出现运行到一半 partial/暂停的问题。

### 处理

- 主智能体 system context 增加“协调者优先”规则：
  - 大任务先写 todo/plan。
  - 先并发启动 2-3 个只读 `agent_run` 做代码探索、研究、计划或复核。
  - 汇总第一批结果后，再用 `junior` / `code-worker` 执行带 `writeScope` 和验收标准的局部实现。
  - 子任务返回 `partial`、`budgetExceeded` 或 `continuationPrompt` 时，视为阶段性成果，继续拆小续跑或向用户说明 task id 和剩余切片，避免把原始 JSON 当最终正文。
- `agent_run` 工具 schema 增加 `title`、`purpose`、`difficulty`、`risk`、`modelTier` 字段，允许主智能体显式声明任务难度和模型档位。
- 如果 `agent_run` 标记为 `difficulty=deep` 或 `risk=high` 但没有显式传 `modelTier`，运行时会自动推断为 `strong`，避免难任务误用轻量档位。
- 子智能体 profile 默认轮次整体上调：
  - `explorer` / `readonly-researcher` / `web-researcher` / `browser-verifier`：48 轮。
  - `planner`：32 轮。
  - `verifier` / `reviewer`：48 轮。
  - `junior` / `code-worker`：64 轮，deep 预算可到 96 轮。
- `src/agents/budget.js` 默认预算从偏短保护阀调整为长任务友好预算：
  - 默认 64 轮、180 次工具调用、30 分钟、320KB 工具输出预算。
  - deep implementation 预算提升到 96 轮、260 次工具调用、45 分钟。
  - web/search 来源级失败和权限拒绝容忍度提升到 6 次，并继续要求把被阻止来源写入 caveats。
- 项目配置和模板把 `agents.maxRounds` 改为 `null`，表示不再用项目级总闸覆盖 profile/budget 的精细配置；仍保留 `LAB_AGENT_AGENT_MAX_ROUNDS` 作为人工调试保险丝。
- `LLM_ONBOARDING.md` 补充当前主/子智能体预算原则和常见误区，提醒后续模型不要重新引入低项目级全局上限。

### 验证

已执行定向测试：

```powershell
node --test tests\unit\agent-budget-contract.test.js tests\unit\agents.test.js tests\unit\context.test.js tests\unit\config.test.js tests\unit\session.test.js
```

结果：59 个相关测试全部通过。

已执行全量检查：

```powershell
npm run check
```

结果：语法检查、禁用端点扫描、provenance、依赖策略和 349 个测试全部通过。

人工侧建议后续用一个跨模块长任务观察：

- 主智能体是否先生成 todo/plan。
- 是否先调用多个只读子智能体，而不是自己长时间单线读取。
- 子智能体卡片是否显示较高预算并能持续运行。
- partial 时是否给出可读汇总或续跑建议，而不是只返回原始 JSON。

## 2026-05-03：取消主智能体默认工具轮次上限

### 背景

用户在测试 10 个 todo 的长任务时，主智能体在最终助手响应前触发 `tool_limit`，TUI 显示“工具上限”。用户明确指出主智能体执行状态在 TUI 中可见，如果陷入无限循环或工具卡住，可以人工中断；默认硬上限会误伤正常长任务。

### 处理

- 主智能体默认 `limits.maxToolRounds` 改为 `null`，表示不设置工具轮次上限。
- `lab-agent.config.json`、实验室模板和高敏模板同步把主会话 `maxToolRounds` 改为 `null`。
- 主会话循环从固定 `for round <= maxToolRounds` 改为无限循环，由最终助手响应、错误、人工中断、上下文压缩和工具/权限自身机制结束。
- 保留高级手动保险丝：
  - 如果用户显式设置 `LAB_AGENT_MAX_TOOL_ROUNDS=数字`，仍会启用主会话工具轮次上限。
  - 如果项目配置 `limits.maxToolRounds` 为正整数，也仍会启用上限。
- TUI 的上限提示从“工具调用上限”改为更准确的“工具轮次上限”，并显示当前上限和待执行工具数。
- 子智能体预算和工具输出上限不受影响，仍用于防止子任务无界消耗。

### 验证

已执行：

```powershell
node --test tests\unit\session.test.js tests\unit\config.test.js tests\unit\tui-format.test.js
```

结果：62 个相关测试全部通过。覆盖点包括：默认主会话无上限、显式 `LAB_AGENT_MAX_TOOL_ROUNDS=2` 时仍会触发中文 `tool_limit`、配置校验仍拒绝非法 0 值。

## 2026-05-02：会话恢复入口去重，明确 `/sessions` 与 `/resume` 分工

### 背景

用户验收会话恢复功能后指出，`/sessions` 和无参数 `/resume` 都会弹出会话选择器，体验上重复。讨论后确定产品分工：`/sessions` 负责可视化选择历史会话，`/resume` 只保留命令式快速恢复能力。

### 处理

- `/sessions` 保持原有会话选择器：
  - 展示标题、最近提示、时间、状态、消息数和模型。
  - 选中后回车恢复对应会话。
- `/resume latest` 保持直接恢复最近会话。
- `/resume <session-id>` 保持直接恢复指定会话或唯一 id 前缀。
- 无参数 `/resume` 不再打开会话选择框，改为显示说明面板：
  - 提示用 `/sessions` 选择历史会话。
  - 提示用 `/resume latest` 或 `/resume <session-id>` 快速恢复。
- 将相关面板测试名称从 “resume command panel” 修正为 “sessions command panel”，避免测试文案继续误导。

### 验证

已执行：

```powershell
node --test tests\unit\tui-command-panels.test.js tests\unit\tui-frame.test.js tests\unit\commands.test.js
```

结果：70 个相关测试全部通过。

## 2026-05-02：thinking 原文改为本地 transcript 可恢复

### 背景

用户指出 `/thinking` 只能在当前 TUI 进程中查看，恢复历史会话后只剩 thinking 字节数，无法复盘模型当时的推理/判断过程。当前项目已经有 hooks、权限确认和本地 transcript 策略，用户明确要求把 provider 暴露的 thinking/reasoning 原文落盘，便于后续查验。

### 处理

- 主会话运行时会捕获 streaming `assistant_thinking_delta`，并随最终 assistant message 写入本地 session transcript。
- `/resume` 恢复会话时会恢复 assistant message 上的 thinking 原文；输入 `/thinking` 后可展开历史回复中的 thinking。
- 下一轮发给模型的历史 messages 会自动剥离 `thinking` 字段，避免把内部 reasoning 反复注入上下文、影响模型注意力或增加 token 成本。
- context window 的预算估算也剥离 `thinking` 字段，避免长 thinking 触发过早 compact。
- TUI `/thinking`、模型面板和快捷键文案从“仅内存/不落盘”改为“默认隐藏，本地 transcript 可恢复”。

### 验证

- 新增单测覆盖：streaming thinking 会写入 `.lab-agent/sessions/*.json`，`/resume` 后仍在 restored messages 中，并且下一轮 gateway request 不携带 `thinking` 字段。
- 更新 TUI 格式测试，验证完成后的静态 transcript 和恢复后的 transcript 都能按 `/thinking` 开关展开。
- 已运行：
  - `node --test tests\unit\session.test.js tests\unit\tui-format.test.js tests\unit\commands.test.js tests\integration\ant-event-output.test.js`

### 注意

- thinking 仍默认隐藏，不进入普通复制文本；用户需要显式 `/thinking` 展开查看。
- AntEvent/print JSON 的 partial thinking delta 仍不作为可打印事件输出；落盘位置是本地 session transcript 的 assistant message metadata。

## 2026-05-02：修复 Hooks 审核发现的后台生命周期和命名问题

### 背景

对 Hooks 实现做严格审核后发现三个体验细节仍会影响用户判断或退出行为：非阻断 command hook 可能因子进程和 pipe 引用拖住 Node 退出；默认敏感路径 hook 名称仍叫 `deny-sensitive-files`，和当前“只记录、不阻断”的行为不一致；后台 hook 被调度后 `/hooks` 不能显示运行中状态。

### 处理

- 默认敏感路径 hook 从 `deny-sensitive-files` 改名为 `record-sensitive-files`。
- 新增 `recordSensitiveFiles` builtin；旧 `denySensitiveFiles` builtin 保留为兼容别名，避免已有项目配置失效。
- audit store 新增 `status` 和 `updatedAt`，支持 `running`、`completed`、`failed`、`blocked`、`skipped` 状态。
- 非阻断 command hook 调度时先写入 running 记录，完成后原地更新为 completed/failed，不再只在结束后出现。
- 后台 command hook 的 child process、stdout/stderr pipe 和 timeout 尝试 `unref`，避免 Ant Code 进程仅因后台 hook 未结束而被拖住。
- `/hooks` 审计概览增加“运行中”计数。

### 验证

- 补充 hooks 单测：
  - 默认 hook 名称为 `record-sensitive-files`，不再出现误导性的 `deny-sensitive-files`。
  - 旧 `denySensitiveFiles` builtin 仍可通过项目配置调用。
  - 后台 command hook 调度后立即显示 `running`，完成后更新为 `completed`。
  - `/hooks` 报告显示运行中数量。

## 2026-05-02：复查 Hooks 权限强度，改为轻量审计优先

### 背景

用户进一步指出，不能只处理密钥文件；Hooks v1 整体都需要排查是否“权限关得太死”，因为过度阻断会直接影响智能体执行效率和产品体验。排查重点从单个 `.env` 扩展到默认 blocking 策略、command hook 执行方式、compact/permission/todo/subagent 等事件是否可能误伤长任务。

### 处理

- 默认内置 hooks 全部改为轻量审计/记录，不再默认注册 blocking hook。
- `recordSensitiveFiles` 保留为敏感路径命中记录，继续把最终决策交给权限强确认，不在 hooks 层阻断。
- 允许 blocking 的事件收缩为仅 `tool.before`：
  - `permission.denied` 已经是拒绝后的审计事件，不再允许额外阻断。
  - `compact.before` 不再允许阻断，避免长任务因为 hooks 配置导致上下文压缩失败。
  - `file.changed`、`todo.updated`、`session.*`、`subagent.*` 均保持审计/后台自动化语义。
- 非阻断 command hook 改为后台异步调度；例如用户配置 `npm run check` 或格式化 hook，不会卡住模型/工具主流程。
- 未 trusted 的项目 command hook 仍然同步记录为 skipped，不执行项目命令。
- blocking command hook 仍只在 trusted workspace 且 `tool.before + blocking:true` 下同步等待，用于少数明确的危险操作预检。

### 验证

- 补充 hooks 单测：
  - 默认 `record-sensitive-files` 不再是 blocking hook。
  - 非阻断 command hook 会快速返回并在后台完成审计记录。
  - 原有 trusted / untrusted command hook、敏感 env scrub、session hook、工具/文件/todo/权限审计仍保持可用。

### 后续风险

- 用户如果手动配置 `tool.before` blocking hook，仍可能因脚本过慢或误判影响工具执行；这是显式高级能力，不应作为默认策略。
- 后台 command hook 的执行结果会稍后进入 `/hooks` 和 `/logs`，不是工具调用返回前立即可见。

## 2026-05-02：调整敏感文件权限策略，避免 Hooks 牺牲日常可用性

### 背景

Hooks v1 初版把 `.env`、凭据、token、私钥等敏感路径在 `tool.before` 阶段直接硬拦。用户指出这会让日常密钥轮换、模型配置维护变成必须人工手改，和 opencode、源码版 Ant Code 等代码智能体的使用体验相比过于保守。新的产品原则是：敏感信息访问要明显提醒并强确认，但不能因为安全兜底牺牲智能体的正常工作能力。

### 处理

- 权限策略从“敏感路径一律 deny”改为“敏感路径强确认 ask”：
  - `read_file` / `document_intake` 等敏感读取会弹出权限确认，批准后才会把内容交给模型。
  - `write_file` / `edit_file` 写入 `.env` 等敏感文件时，即使当前会话已经允许普通工作区写入，也仍会单独要求强确认。
  - readonly 会话仍然拒绝敏感写入。
  - 工作区外写入仍然默认拒绝，不因为文件名像 `.env` 而放宽。
- Hooks 内置 `recordSensitiveFiles` 不再抢先阻断敏感路径，而是记录“命中敏感路径，交由权限强确认处理”。
- TUI 和 interactive 审批提示增加敏感信息强确认说明，提醒批准后相关内容或变更可能进入模型上下文。
- `write_file` / `edit_file` 对敏感文件返回脱敏 diff，只显示路径和字节变化，不展示旧 key 或新 key。

### 验证

- 补充权限单测：敏感读取返回 `ask + sensitive`，敏感写入在普通写入已允许时仍要求单独确认，readonly 敏感写入拒绝。
- 补充 hooks 单测：敏感路径命中不会被 hook 硬拦，而是进入权限层。
- 补充工具单测：批准后可写 `.env`，拒绝后不写入，敏感文件 write/edit diff 不包含旧密钥或新密钥。

### 后续风险

- 用户批准敏感读取后，文件内容会进入模型上下文；这是有意设计的“强确认后可用”模式，不应再被 hooks 静默拦截。
- 后续如果新增 `git_diff`、搜索、MCP 文件类工具的敏感内容展示能力，也要遵守同样原则：先强确认，再脱敏可脱敏的输出。

## 2026-05-02：完成 Hooks v1 本地运行时 Stage 1-8

### 背景

用户审核通过 Hooks v1 方案后，要求一次性完成 Stage 1-8，并在完成后严格审查。目标是把工具调用、权限拒绝、文件变更、todo 更新、子智能体生命周期、上下文压缩和会话生命周期从“模型自觉记录”提升为“系统可审计事件”，后续可承接自动验证、规范化运行习惯和安全兜底。

### 处理

- 新增 hooks 核心模块：
  - `src/hooks/events.js`：统一事件名、可阻断事件、payload 脱敏、摘要和路径匹配辅助。
  - `src/hooks/registry.js`：读取 `config.hooks`，合并默认内置 hooks，支持 `when.paths` / `when.tools` 匹配、`managedOnly`、超时、输出上限和阻断合法性校验。
  - `src/hooks/runner.js`：执行 builtin / command hook，防递归，command hook 走超时、输出截断和环境变量白名单。
  - `src/hooks/builtins.js`：实现审计、敏感路径命中记录、文件/todo/subagent/compact/session 记录等 builtin hooks。
  - `src/hooks/audit-store.js`：当前进程内 ring buffer 审计记录，供 `/hooks` 和 `/logs` 查看。
  - `src/hooks/report.js`：中文 `/hooks` 报告。
- 配置层：
  - 默认启用 `hooks.enabled=true`。
  - 默认不配置自动测试 command hook，只启用内置审计和敏感路径强确认记录。
  - 增加 `hooks.disableAll`、`managedOnly`、`defaultTimeoutMs`、`maxOutputBytes`、`envAllowlist`、`events` 校验。
- 工具运行时：
  - 所有合法工具调用进入 `tool.before`，完成进入 `tool.after`，失败进入 `tool.failed`。
  - 权限拒绝进入 `permission.denied`。
  - `write_file` / `edit_file` 成功写入后进入 `file.changed`。
  - `todo_write` 成功后进入 `todo.updated`。
  - `recordSensitiveFiles` 在 `tool.before` 阶段记录 `.env`、凭据、私钥、token 类路径命中；是否允许访问交给权限强确认。
- 子智能体：
  - `runSubagent` 创建任务后记录 `subagent.started`。
  - 成功、失败、partial/paused 分别记录 `subagent.completed`、`subagent.failed`、`subagent.paused`。
  - TUI 后台任务、slash `/agents run/continue/review/orchestrate`、skill fork、agent tool 均透传 hooks trusted 状态。
- compact 和 session：
  - `compactSessionContextWithModel` 记录 `compact.before` / `compact.after`，包含压缩前后 tokens、messages、strategy、fallbackReason。
  - `createSession` 记录 `session.start`。
  - 会话 metadata 持久化完成后记录 `session.end`。
  - 每轮用户提示进入 `user.prompt`，只保留脱敏摘要和字节数。
- TUI / slash：
  - 新增 `/hooks`，中文显示开关、事件注册、hook 列表、审计概览、最近记录和失败/阻断记录。
  - `/hooks` 加入 TUI inspector 输出命令集合，但不重新占用右侧栏。
  - 项目 command hooks 只有在 TUI 已信任工作区并传入 `trusted=true` 时执行；普通 chat/print 默认只跑 builtin hooks。

### 安全边界

- command hook 不继承完整环境变量，只保留 allowlist；即使用户把 `LAB_SECRET_TOKEN` 写进 allowlist，也会被敏感 key 过滤。
- command hook 默认非阻断；复查后仅 `tool.before` 允许显式阻断。
- hook 自身执行不会递归触发 hooks。
- `/hooks` 审计记录只在当前进程内保存，不写入 session transcript。

### 验证

- 新增 `tests/unit/hooks.test.js`，覆盖：
  - 默认 hooks 和路径匹配。
  - builtin 审计和敏感路径强确认记录。
  - command hook 未 trusted 跳过、trusted 执行、敏感 env 不泄露。
  - 工具、文件变更、todo、权限拒绝事件。
  - compact before/after 事件。
  - `/hooks` 中文报告内容。
- 更新配置和命令单测，覆盖默认 hooks 配置、非法 blocking 配置拒绝、slash `/hooks` 输出。
- 已通过目标测试集：
  - `node --test tests/unit/hooks.test.js tests/unit/config.test.js tests/unit/commands.test.js tests/unit/tools.test.js tests/unit/context-window.test.js tests/unit/agents.test.js`

### 后续风险

- 第一版 command hook 只支持本地命令，不支持 HTTP hooks、插件市场或远端 managed settings。
- `session.end` 当前绑定在 metadata 写入后，覆盖正常 turn 结束；如果用户直接关闭进程，退出期 hook 不保证执行。
- 自动 `npm run check` hook 仍只作为配置示例能力，未默认开启，避免拖慢日常 TUI。

## 2026-05-02：建立大改计划档案制度并新增 Hooks v1 待审方案

### 背景

用户要求以后每次大改都先形成可审核的详细计划，并希望把此前多轮 stage 计划文档集中管理，避免散落在普通文档目录或聊天记录里。当前 `docs/plans` 已有多份计划，但缺少 `active/completed` 状态区分、统一索引和后续维护规则。

### 处理

- 新增 `docs/plans/README.md`：
  - 明确所有核心大改必须先写计划、经用户审核后再执行。
  - 规定计划文档必须包含目标、基线、参考、边界、stage、验收、风险、回滚和测试。
  - 规定待审/未完成计划放入 `docs/plans/active/`，已完成计划放入 `docs/plans/completed/`。
- 新增待审计划：
  - `docs/plans/active/hooks-v1-local-runtime-plan-2026-05-02.md`
  - 内容覆盖本地 Hooks v1 的事件模型、配置草案、安全策略、模块拆分、8 个实施 stage、验收脚本和待用户确认的问题。
- 整理已完成计划归档：
  - `docs/plans/completed/tui-agent-architecture-upgrade-plan-2026-04-30.md`
  - `docs/plans/completed/external-capabilities-agent-orchestration-upgrade-plan-2026-05-01.md`
  - `docs/plans/completed/subagent-orchestration-v2-design-2026-05-01.md`
- 同步更新引用路径：
  - `LLM_ONBOARDING.md`
  - `PROJECT_CHANGELOG.zh-CN.md`
  - `docs/deployment/v1.3-agent-extension-acceptance.md`
  - `docs/deployment/v1.4-orchestration-acceptance.md`
  - `docs/provenance/modules/capabilities.md`

### 验证

- 使用 `rg` 确认旧路径 `docs/plans/<plan>.md` 不再残留。
- 检查 `docs/plans` 目录结构只保留 `README.md`、`active/`、`completed/`。
- 本次只改文档和引用路径，不修改运行逻辑。

## 2026-05-02：补齐外部专业 skill 工具白名单

### 背景

用户反馈 Ant Code 在汇报中指出外部专业 skill 的 `allowedTools` 为空数组，容易让模型误以为这些 skill 没有声明可用工具。根因不是外部目录本身，而是这些 `SKILL.md` 的 frontmatter 没有 `allowed-tools` 字段。

### 处理

- 为 6 个外部专业 skill 补充 `allowed-tools`：
  - `ant_render_batch` / `ant_render_retry`：`powershell, read_file, list_files, glob`
  - `antscan_incremental_download`：`powershell, read_file, list_files, glob`
  - `paper-distill`：`powershell, read_file, list_files, glob, document_intake`
  - `taxonomy-ai-intel`：`web_search, web_fetch, powershell, read_file, document_intake, mcp_list, mcp_call`
  - `unsloth-studio-finetune`：`powershell, read_file, list_files, glob`
- 保持权限边界不变：`allowed-tools` 只是 skill 元数据和子智能体工具范围提示，不绕过 shell、网络、写入或 MCP 审批。

### 验证

- 使用 `/skills` 验证外部 skill 列表已显示 `tools=...`。
- 使用本地脚本确认 6 个外部专业 skill 的 `allowedTools` 都不为空。

## 2026-05-02：接入实验室外部专业 skill 包

### 背景

用户在 `C:\saveproject\LBJ-workspace\skill` 维护了一组面向日常专业工作流的本地 skill，包括蚂蚁 STL 渲染、AntScan 增量下载、论文蒸馏、taxonomy × AI 文献筛选和 Unsloth Studio 微调。此前 Ant Code 只默认加载 `config/skills`，并且 skill loader 对“外部绝对路径”和“直接指向一个 skill 包目录”的兼容不够稳，容易漏加载或把 README 当成 skill。

### 处理

- `lab-agent.config.json`
  - 注册外部专业 skill roots：
    - `ant-render-exporter\skills`
    - `antscan-data-crawl\skills`
    - `paper_distill_skill_bundle_v6_zh\skills`
    - `taxonomy-ai-intel\skills`
    - `unsloth-studio-finetune-portable`
  - 保留原有 `config/skills`，因此内置通用 skill 和外部专业 skill 会一起出现在 `/skills`、`skill_list` 和模型系统上下文中。
- `src/skills/registry.js`
  - 配置路径先统一解析成绝对路径，再做去重和允许判断，支持 Windows 绝对路径和正斜杠/反斜杠混用。
  - 如果一个配置 root 自身包含 `SKILL.md`，只加载这个 `SKILL.md`，不再把同目录的 `README.md` 或交接文档误注册成独立 skill。
  - 保持安全边界：skill 是本地指令资源；实际执行脚本仍走 `powershell` / `bash` / 普通工具权限审批。
- 外部 skill 适配
  - `ant_render_batch`、`ant_render_retry`：把失效的旧 `D:\OpenClaw...` 路径改为当前 `C:\saveproject\LBJ-workspace\skill\ant-render-exporter\ant-blender-batch-exporter`，并给出 `Push-Location` 包装。
  - `antscan_incremental_download`：补充从任意 cwd 启动时的 `$root`、`PYTHONPATH`、`Push-Location` 包装，避免未安装 editable 包时找不到 `antscan_downloader`。
  - `paper-distill`：补充本机 bundle root 和 fallback `python -m app.paper_distill` 的路径包装。
  - `taxonomy-ai-intel`：补充本机 skill root，并把 `fetch_candidates.py`、`validate_report.py`、`export_digest.py` 改成可从任意项目 cwd 调用的 PowerShell 包装。
  - `unsloth-studio-finetune`：补充 Ant Code 本机 skill root，明确运行日志、缓存、runtime 不应落到当前 coding 项目根目录。

### 验证

- 新增单测覆盖外部绝对路径 skill root：
  - 能加载工作区外的直接 skill 包目录。
  - 能加载工作区外的容器型 skill root。
  - 不把同目录 `README.md` 当成 skill。
- 已用本机真实外部 skill 路径验证可发现 16 个 skill：10 个内置通用 skill + 6 个外部专业 skill。

## 2026-05-02：任务侧栏二级分类收敛

### 背景

用户指出右侧栏 `任务` 已经通过 `[>]`、`[ ]`、`[✓]` 等标记展示待办和计划步骤状态，再额外拆成 `当前` 和 `待处理` 会重复表达，增加切换成本。

### 处理

- `任务` 侧栏二级分类从 `[当前] 待处理 已完成 全部` 调整为 `[未完成] 已完成 全部`。
- `未完成` 聚合所有非 completed 的待办和计划步骤，包含进行中、等待、取消等未完成状态。
- 默认打开 `任务` 侧栏时进入 `未完成` 分类，更贴近用户查看下一步工作和当前进展的常用场景。
- 保留 `已完成` 与 `全部`，方便验收时查看完成项或完整工作流。

### 验证

- 更新 TUI frame 单测，确认 `未完成` 同时显示进行中和等待项，并排除已完成项。
- 后续全量检查随本轮修改统一执行。

## 2026-05-02：右侧栏重命名并增加任务/子智能体分类

### 背景

用户指出原右侧栏 `待办` 实际包含待办、计划、改动、验证，不只是 todo；原 `任务` 主要展示子智能体任务。继续使用旧命名会让信息架构含混。同时，子智能体任务中运行中、暂停/失败、已完成混在一起，真实长任务里会非常繁杂。

### 处理

- 侧栏命名
  - `待办` 改为 `任务`，表示会话工作流：待办、计划、改动、验证。
  - `任务` 改为 `子智能体`，表示后台/派发出去的 agent task。
  - 侧栏大标签现在是 `状态 / 任务 / 子智能体`。
- `任务` 侧栏二级分类
  - 增加 `[当前] 待处理 已完成 全部`。
  - `当前` 只看进行中的待办/计划步骤。
  - `待处理` 显示未完成项，包含 pending 和 in_progress。
  - `已完成` 显示 completed 项。
  - `全部` 显示完整待办和计划。
- `子智能体` 侧栏二级分类
  - 增加 `[活跃] 暂停/失败 已完成 全部`。
  - `活跃` 显示 queued/running。
  - `暂停/失败` 显示 partial/failed/blocked/interrupted。
  - `已完成` 显示 completed。
  - `全部` 按状态优先级和更新时间排序，避免旧失败项压住正在运行任务。
- 交互
  - `Tab` 继续切换大侧栏。
  - 输入区为空时，当前侧栏为 `任务` 或 `子智能体` 时，`←/→` 切换二级分类。
  - 当前侧栏为 `状态` 时，`←/→` 仍切换大侧栏。
  - 输入草稿中 `←/→` 仍用于移动光标。
- 测试
  - 更新 footer 和 `/keybindings` 文案断言。
  - 新增任务侧栏分类过滤测试。
  - 新增子智能体侧栏活跃/暂停失败/已完成分类测试。

### 验证

已执行：

```powershell
node --check .\src\cli\tui.js
node --check .\src\cli\tui\components.js
node --check .\src\cli\tui\format.js
node --check .\src\commands\registry.js
node --test .\tests\unit\tui-frame.test.js .\tests\unit\commands.test.js
```

结果：61 pass / 0 fail。

### 影响

- 右侧栏更接近真实产品概念：任务是主会话工作流，子智能体是派发任务状态。
- 运行中、失败/暂停、完成项不再混在一个列表里。
- 旧 view id 仍保持 `workflow`/`tasks`，降低改动风险；只改变用户可见命名和交互。

## 2026-05-02：右侧任务栏改为本会话视图，取消根任务硬截断

### 背景

用户在进入项目文件夹但尚未恢复历史会话时，右侧栏已经显示旧子智能体任务，容易误以为这些任务属于当前新会话。用户还指出任务栏出现 `... 还有 7 个根任务`，但没有明确展开入口，导致剩余任务不可达。

### 处理

- `src/cli/tui.js`
  - 右侧任务栏加载任务时改用 `parentSessionId=session.id` 过滤。
  - 新会话只显示当前会话启动或关联的子智能体任务。
  - 工作区级历史任务仍保留在 `.lab-agent/tasks` 中，可通过 `/agents tasks` 查看。
- `src/cli/tui/components.js`
  - 任务侧栏空态改为 `本会话暂无子智能体任务`，并提示工作区历史任务使用 `/agents tasks`。
  - 标题从 `任务树：N` 改为 `本会话任务：N`，避免和工作区全局任务混淆。
  - 移除只显示前 10 个根任务的硬截断；侧栏内容可通过滚轮或侧栏滚动查看。
- `tests/unit/tui-frame.test.js`
  - 更新任务栏文案断言。
  - 新增 12 个根任务场景，确保不会再出现不可展开的 `还有 N 个根任务` 截断提示。

### 验证

已执行：

```powershell
node --test .\tests\unit\tui-frame.test.js
```

后续还需随本轮收尾执行完整 `npm run check`。

### 影响

- 右侧任务栏现在代表“当前会话的子任务状态”，更符合用户对侧栏状态区的直觉。
- 旧会话/旧项目任务不会在新会话中突然冒出来。
- 需要查工作区全量任务时，使用 `/agents tasks` 或 `/background tasks`。

## 2026-05-02：移除右侧栏提示历史，改用 Ctrl+方向键召回 prompt

### 背景

用户指出右侧栏 `历史` 实际只展示最近提交过的用户 prompt，不是完整会话历史；完整对话已经在主聊天区可见，这个常驻侧栏价值低，还会增加 `Tab` 切换成本。同时当前普通 `↑/↓` 已承担聊天区滚动职责，继续用它召回历史 prompt 会造成交互冲突。

### 处理

- `src/cli/tui/format.js`
  - 右侧栏标签从 `状态 / 待办 / 任务 / 历史` 收束为 `状态 / 待办 / 任务`。
  - 删除 `历史` 标题和颜色分支，避免后续不可达状态回流。
- `src/cli/tui/components.js`
  - `SidePanel` 不再接收或渲染 prompt history。
  - 删除 `historyPanelLines()`，保留右侧栏给状态、待办和子智能体任务。
- `src/cli/tui.js`
  - 保留内部 `history` 状态，用于 prompt 召回。
  - 普通 `↑/↓` 明确用于聊天区滚动。
  - `Ctrl+↑ / Ctrl+↓` 改为召回上一条/下一条已提交 prompt，避开滚动冲突。
- `src/commands/registry.js`
  - `/keybindings` 文案改为 `Ctrl+↑/Ctrl+↓：召回上一条/下一条已提交提示`。
  - 右侧栏切换说明改为 `状态、待办、任务`。
- 测试
  - 更新 `tui-frame` 和 `commands` 单测，确保侧栏不再出现 `历史`，快捷键说明与真实行为一致。

### 验证

已执行：

```powershell
node --check .\src\cli\tui.js
node --check .\src\cli\tui\format.js
node --check .\src\cli\tui\components.js
node --check .\src\commands\registry.js
node --test .\tests\unit\tui-frame.test.js .\tests\unit\commands.test.js
```

结果：58 pass / 0 fail。

### 影响

- 右侧栏更干净，`Tab` 只在三个高价值视图间切换。
- 输入历史能力没有删除，只是从常驻展示改为按需召回。
- 普通上下方向键不再和历史 prompt 召回抢职责，滚动窗口的预期更稳定。

## 2026-05-02：右侧栏瘦身，运行记录仅保留 /logs 入口

### 背景

用户在真实项目中持续使用右侧栏后反馈：`状态`、`待办`、`任务`、`历史`是真正高频有效的信息；原 `命令` 栏与 `/help` 重复，原 `检查/Inspector` 栏偏开发期黑匣子，长期占据右侧栏会增加切换成本。用户明确要求不保留 `/inspector` 兼容别名，只留下 `/logs` 一个按需入口。

### 处理

- `src/cli/tui/format.js`
  - 右侧栏标签收束为 `状态 / 待办 / 任务 / 历史`。
  - 移除不可达的 `命令`、`检查` 侧栏标题和颜色分支，防止后续旧状态回流。
- `src/cli/tui/components.js`
  - `SidePanel` 不再渲染持久命令列表或 Inspector 内容。
  - FooterBar 改为提示 `/logs 运行日志`，右侧栏提示只描述当前产品态标签。
- `src/commands/registry.js` / `src/commands/runtime.js`
  - 新增 `/logs` 命令说明和快捷键说明。
  - 删除旧 Inspector 快捷键文案；不提供 `/inspector` 别名。
  - 非 TUI 模式下 `/logs` 只说明它是交互式 TUI 的当前进程内日志入口。
- `src/cli/tui/command-panels.js`
  - 新增 `createLogsPanel()`，复用原本进程内运行记录数据，但改为底部命令面板显示。
  - `/logs` 顶部标签支持 `Tab`、`Left/Right` 切换日志类型。
- `src/cli/tui.js`
  - 移除 `Ctrl+T`、`Ctrl+N/P`、`Ctrl+F/B`、`Ctrl+R/E` 这些旧 Inspector 全局快捷键。
  - `/logs [all|command|diff|tool|approval|gateway|context]` 打开运行日志面板。
  - `/logs` 标签切换会真正切换过滤类型，而不是只改变标签高亮。
  - 运行记录仍在当前 TUI 进程内保留，用于排查命令、工具、审批、网关和上下文事件；不写入 session transcript。
- `src/cli/tui/inspector.js`
  - 用户可见提示从“检查页 / Inspector 快捷键”改为“/logs 面板”。
  - 普通日志内容提示使用 Up/Down 或滚轮滚动；diff 详情提示用户需要完整 diff 时使用 `/diff`。
- 测试
  - 更新 `tui-frame`、`tui-command-panels`、`commands` 单测，确保右侧栏不再出现 `命令/检查`，快捷键不再宣传 `Ctrl+T`，并覆盖 `/logs` 面板过滤标签。

### 验证

已执行：

```powershell
node --test tests\unit\tui-frame.test.js tests\unit\tui-command-panels.test.js tests\unit\commands.test.js tests\unit\tui-inspector.test.js
```

结果：69 pass / 0 fail。

### 影响

- 用户日常右侧栏切换路径变短，重点集中在状态、待办、子智能体任务和历史。
- 调试信息仍可通过 `/logs` 查看，不再常驻占用右栏。
- 旧的 `Ctrl+T` 等低频 Inspector 快捷键被移除；以后日志面板内只保留通用面板滚动和标签切换方式。
- 没有 `/inspector` 兼容别名，避免产品文案和用户习惯继续分叉。

## 2026-05-02：修正 Ctrl+O 详情模式误折叠最终回复

### 背景

用户指出 `Ctrl+O` 的紧凑/详细/完整模式会默认折叠大模型最终回复，导致长回答必须切到详细或完整模式才能看完。这个行为不符合主流代码智能体体验：工具调用、thinking、过程流水可以折叠，但最终 assistant 正文应当默认完整展示。

### 处理

- `src/cli/tui/format.js`
  - 调整 `assistant` transcript 渲染规则。
  - 最终回复正文不再进入 `foldBodyLines`，只做软换行和普通展示。
  - `thinking` 展开内容仍然受 `Ctrl+O` 详情模式控制，避免隐私/长思考内容挤占主聊天区。
  - 工具卡片、子智能体过程、权限详情、错误详情、大段用户粘贴文本仍保持原有折叠策略。
- `tests/unit/tui-format.test.js`
  - 将旧的“assistant 长正文会折叠”测试改为“assistant 最终回复在 compact 模式也完整可见”。
  - 覆盖长段落、resume 后长 assistant 内容等场景。

### 验证

已执行：

```powershell
npm test -- tests/unit/tui-format.test.js
```

结果：25 pass / 0 fail。

### 影响

- `Ctrl+O` 现在主要用于切换过程信息密度，而不是隐藏最终答复。
- 长最终回复会增加聊天区可滚动高度，这是预期行为；用户可以用鼠标滚轮或方向键查看完整回答。
- 运行过程仍会自动降噪，不会回到早期“工具流水堆满聊天框”的状态。

## 2026-05-01：子智能体长网页研究的中途证据压缩与收尾汇报修正

### 背景

用户复盘最近一次 `booking-ui-refactored` 项目测试时指出：

- `web-researcher` 已经成功获取大量搜索结果和网页内容，但第 4 次来源权限拒绝后保存为 `partial`，没有生成子智能体自己的最终综合调研报告。
- 主智能体虽然能兜底汇总，但这会让主智能体被迫接收更多不稳定上下文，而且用户通常不会再手动继续一个已经被主智能体接手的 partial 子任务。
- 网页搜索子智能体上下文增长很快，实测接近 17w token，逼近 200k 上限。
- 需要确认现有自动 compact 机制：主会话已有回合结束后的模型压缩，但子智能体工具循环中途没有自动 compact。

### 处理

- 新增 `src/core/inflight-compaction.js`
  - 提供“进行中工具上下文压缩器”。
  - 当活跃工具循环消息估算 token 达到配置阈值时，把较早的 tool result 原文替换成结构化摘要。
  - 保留最近若干条工具结果原文，避免模型失去刚刚获取的细节。
  - 保留 URL、搜索结果标题、状态码、截断标记、错误/权限拒绝等关键信息。
- `src/agents/runner.js`
  - 子智能体每轮工具结果写入后，执行 in-flight tool compaction。
  - `web-researcher` 遇到 `maxPermissionDenials` / `maxConsecutiveFailures` 这类来源级保护阀时，不再优先 partial 暂停。
  - 达到保护阀后会先压缩旧工具结果，再进入“无工具最终汇报轮”，要求模型基于已有结果输出最终报告和 caveats。
  - 最终汇报轮不再被普通 `maxRounds` 抢断。
- `src/core/session.js`
  - 主会话工具循环也接入 in-flight tool compaction。
  - 这不是替代原有 `/compact` 或回合结束模型压缩，而是避免一个长工具回合中 raw tool output 过度膨胀。
- `src/config/load-config.js` / `lab-agent.config.json`
  - 新增默认配置：
    - `context.inFlightCompactRatio: 0.68`
    - `context.inFlightKeepRecentTools: 4`
  - 含义：估算上下文超过 68% 时压缩旧工具结果，保留最近 4 条工具结果原文。
- `tests/unit/context-window.test.js`
  - 覆盖 in-flight tool result 压缩行为。
- `tests/unit/agents.test.js`
  - 覆盖长网页研究中旧工具结果被压缩后仍能继续完成。
  - 覆盖来源拒绝达到上限后生成最终报告，而不是只返回 partial。
- `tests/unit/config.test.js`
  - 覆盖新增配置默认值。

### 当前机制说明

- 主会话：
  - 已有模型压缩 `/compact` 和自动压缩。
  - 自动压缩在“回合结束、写入 user/assistant 到 session.messages 后”触发。
  - 本次新增的是“回合进行中工具结果压缩”，用于长工具链。
- 子智能体：
  - 之前没有独立 contextWindow，也没有模型 compact。
  - 本次新增工具结果压缩，解决网页研究、长文件读取等任务中 raw evidence 反复进入上下文的问题。
  - 子智能体最终返回给主智能体的仍是有界输出，不应把全部原始网页结果直接塞回主会话。

### 验证

已执行：

```powershell
node --test .\tests\unit\context-window.test.js .\tests\unit\agents.test.js .\tests\unit\session.test.js .\tests\unit\config.test.js
```

结果：53 pass / 0 fail。

### 风险和边界

- in-flight 压缩是结构化摘要，不是再调用大模型压缩；它用于中途控上下文和保留证据要点。
- 主会话完整历史压缩仍由模型 compaction agent 负责。
- 子智能体暂未实现完整“模型式上下文 compact + 继续同一子任务”的长期记忆链；如果未来需要超长研究任务，可以在本机制基础上继续升级为子智能体私有 contextWindow。

## 2026-05-01：放宽 web 子智能体单源失败策略，避免 GitHub 被拦后无最终汇报

### 背景

用户实测联网子智能体已经可以获取网页信息，但当 GitHub 等单个来源被网络策略拦截一次后，任务直接中断。虽然前面已有搜索或抓取结果，主聊天区没有拿到最终汇报，只看到子任务暂停或工具失败记录。

复盘后确认有两层原因：

- `web-researcher` 的权限拒绝预算过严，单源失败容易被当成整个研究任务失败。
- 工具循环在预算命中时会优先返回 partial，导致工具结果还没交回模型生成最终报告。

### 处理

- `src/agents/budget.js`
  - 将 `web-researcher.standard.maxPermissionDenials` 调整为 4。
  - 将 `web-researcher.standard.maxConsecutiveFailures` 调整为 4。
- `lab-agent.config.json`
  - 同步放宽项目默认 `web-researcher` 预算。
  - 将常见公开代码研究来源加入默认 `allowedHosts`：`github.com`、`raw.githubusercontent.com`、`api.github.com`。
- `src/agents/runner.js`
  - `web_search` 失败不再一次就暂停；连续失败才判断搜索后端不可用。
  - `web_fetch` / `mcp_call` 的单个来源失败或权限拦截会先回传给模型，让模型把该来源列入 caveats。
  - 如果 web 子智能体达到来源失败保护阀，不再继续给工具定义，而是要求模型“不要再调用工具，基于已有结果写最终报告”。
- `tests/unit/agents.test.js`
  - 增加“单个 GitHub/source fetch 被拦后仍生成最终报告”的回归。
  - 增加“连续来源被拦后进入无工具最终汇报轮”的回归。
  - 修正 repeated tool mock gateway，使它能模拟 `web_search` / `web_fetch`，不再误用 `read_file`。
- `tests/unit/config.test.js`
  - 覆盖 GitHub 公开域默认白名单和 web-researcher 新预算。

### 验证

已执行：

```powershell
node --test .\tests\unit\agents.test.js .\tests\unit\agent-budget-contract.test.js .\tests\unit\config.test.js
```

结果：32 pass / 0 fail。

### 风险和边界

- 如果用户环境显式设置 `LAB_AGENT_NETWORK_MODE=offline`，联网工具仍会被策略拦截。
- 如果 GitHub 本身网络不可达、代理异常或被远端限流，子智能体会把它作为来源 caveat，而不是保证一定能抓取成功。
- 如果所有搜索后端连续不可用，仍会阶段性暂停并建议配置 SearXNG/搜索 MCP，避免空转预算。

## 2026-05-01：主会话支持同批只读子智能体并发执行

### 背景

用户指出：普通主智能体派发多个子智能体时仍是线性执行，效率低；参考 OMO 这类调度型智能体，独立只读调查任务应该可以并发下达、并发回收。

复盘后确认：

- `/agents orchestrate <任务>` 已有最多 3 个只读子任务并发的底座。
- 但模型在普通对话中直接返回多个 `agent_run` 工具调用时，`src/core/session.js` 的工具循环仍按 `for...of` 串行执行。
- 这会让多个 `explorer` / `researcher` / `planner` 等互不依赖的只读任务排队等待，浪费长任务调度时间。

### 处理

- `src/core/session.js`
  - 将工具调用执行改为批处理。
  - 同一批工具调用中，连续的 `agent_run` 会根据 profile 判断是否可并发。
  - 只有 `profile.mode === "readonly"` 且未显式 `parallel:false` 的 `agent_run` 会并发。
  - 单批并发上限为 3，防止模型一次派太多子任务压垮网关和本地任务栏。
  - 写入型、浏览器/执行型、验证型、需要权限确认的工具仍保持串行。
  - 保持 tool result 返回顺序与模型原始 toolCalls 顺序一致，避免网关续轮上下文错乱。
- `src/tools/runtime.js`
  - 暴露 runtime 的 `cwd` 和 `config`，供主会话判断 agent profile 类型。
- `src/tools/definitions.js`
  - `agent_run` schema 增加 `parallel` 布尔字段，允许模型显式设置 `parallel:false`。
- `src/context/builder.js`
  - 系统提示明确：同批多个只读 `agent_run` 可以并发；写入、浏览器、验证、审批重的任务应顺序执行。

### 验证

已新增单测：

```powershell
node --test .\tests\unit\session.test.js
```

结果：17 pass / 0 fail。

关键覆盖：

- 同一轮返回两个 `explorer` 子任务时，第二个 `tool_start` 会出现在第一个 `tool_finish` 前，证明不是线性排队。
- 即使并发完成顺序不同，返回给模型的 tool result 顺序仍保持原始 toolCall 顺序。

### 风险和边界

- 目前并发只放开 readonly profile；`verifier` 虽然通常只读/执行检查，但可能运行命令，因此仍不自动并发。
- `mcp_call`、浏览器自动化和写文件任务仍应保守串行，避免共享状态冲突。
- 这不是完全后台 detach；主智能体仍等待这些同批子任务结果后再进入下一轮汇总。

## 2026-05-01：修复 Windows 系统代理下的联网搜索通路

### 背景

用户本机一直开启全局代理，但 Ant Code 的 `web_search` 仍然失败。现场诊断后确认：

- Windows 系统代理已开启，地址为 `127.0.0.1:7897`。
- PowerShell / 浏览器可以访问 DuckDuckGo。
- Node 22 原生 `fetch` 不会自动读取 Windows 系统代理。
- 当前 shell 里还存在 `LAB_AGENT_NETWORK_MODE=offline`，会让 Ant Code 权限策略拦截联网工具。

这导致“用户以为已经全局代理，但 Node/Ant Code 实际没有走代理”的错位。

### 处理

- 新增 `src/net/proxy.js`：
  - 优先读取显式 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`。
  - 没有环境变量时，在 Windows 下读取注册表系统代理。
  - 自动绕过 `localhost` / `127.0.0.1` / `::1`，避免本地服务和本地测试被代理截胡。
  - 提供 `withProxyEnvironment`，让 MCP 子进程继承代理环境。
- 升级 `src/tools/web-tools.js`：
  - `web_fetch` / `web_search` 在有代理时走 HTTP CONNECT 隧道。
  - 保留 DuckDuckGo HTML fallback。
  - 支持代理下 HTTPS、重定向和 chunked 响应解析。
- 升级 `src/mcp/runtime.js`：
  - MCP stdio server 启动前注入代理环境变量。
  - 让 DuckDuckGo MCP、fetch MCP、Playwright MCP 等外部工具更容易使用同一代理。
- `lab-agent.config.json` 明确设置 `networkMode: "lab-only"`，配合 allowedHosts 允许网关和 DuckDuckGo。
  - 注意：环境变量 `LAB_AGENT_NETWORK_MODE=offline` 仍会覆盖项目配置。

### 验证

已执行：

```powershell
node --input-type=module -e "<direct web_fetch/web_search smoke>"
node --test .\tests\unit\tools.test.js .\tests\unit\mcp.test.js
node .\scripts\check-syntax.js
```

结果：

- `web_fetch https://example.com/` 成功，HTTP 200。
- `web_search "ant code github"` 成功返回 DuckDuckGo HTML 搜索结果。
- 针对性测试：34 pass / 0 fail。
- 语法检查通过。

### 风险和边界

- 如果用户 shell 或系统环境仍设置 `LAB_AGENT_NETWORK_MODE=offline`，联网工具仍会被策略拦截。
- 本实现支持 HTTP/HTTPS 代理；SOCKS 代理仍建议通过代理软件暴露 HTTP mixed port。
- DuckDuckGo 仍是公网搜索，可能被限流；长期更稳的方案仍是实验室自建 SearXNG 或可控搜索 MCP。

## 2026-05-01：thinking 展开开关与子智能体输出限流修复

### 背景

用户实测子智能体并行读项目时出现三类问题：

- 主回答复制出来时能看到 `thinking 已隐藏` 提示，说明 thinking 保护生效，但用户需要一个显式开关按需展开。
- `explorer` 子智能体读代码太“老实”，连续 `read_file` 多个源码文件，工具输出超过 160,000 bytes 后 partial，没来得及产出审计结论。
- `web-researcher` 在搜索后端不可用时连续调用失败，浪费工具轮次并给出空结果。

### 处理

- thinking 展示：
  - 新增 `/thinking` TUI 命令，支持 `/thinking on`、`/thinking off`。
  - 默认隐藏 provider 暴露的 thinking/reasoning，只显示字节数。
  - 当时设计为只在当前 TUI 内存展示原文，不写入会话 metadata；该策略已在 2026-05-02 按用户要求改为本地 transcript 可恢复。
  - Footer、`/help`、`/keybindings`、模型选择器和模型面板文案同步更新。
- 子智能体工具限流：
  - `src/agents/budget.js` 增加子任务工具输出细分预算：
    - `maxToolResultBytes`
    - `maxReadFileBytes`
    - `maxWebFetchBytes`
    - `maxSearchResults`
    - `maxFileMatches`
  - `src/agents/runner.js` 在子智能体执行工具前自动套限额：
    - `read_file.maxBytes`
    - `grep/glob.maxMatches`
    - `web_fetch/document_intake.maxBytes`
    - `web_search.maxResults`
  - 子智能体工具记录增加 `inputSummary`，partial 时能看出读了哪个文件、用了多少 `maxBytes`。
  - 工具结果序列化按子智能体预算截断，避免单次结果拖垮整个子任务。
- 子智能体提示词：
  - `explorer` / `readonly-researcher` 系统提示明确要求 scan-first：
    - 先 `list_files` / `glob` / `grep`。
    - 再小片段 `read_file`。
    - 禁止连续全量读取多个大文件。
  - 通用子智能体系统提示新增“Tool budget discipline”段，强调不要倾倒大段原始证据。
- 搜索失败早停：
  - `web-researcher` 遇到 `web_search` 失败会返回 partial，并提示配置 SearXNG / 搜索 MCP 或改用已有知识/可访问 URL。
  - 避免重复搜索失败导致连续工具失败上限。

### 修改文件

- `src/agents/budget.js`
- `src/agents/profiles.js`
- `src/agents/runner.js`
- `src/agents/continuation.js`
- `src/cli/tui.js`
- `src/cli/tui/components.js`
- `src/cli/tui/format.js`
- `src/cli/tui/command-panels.js`
- `src/cli/tui/workflows.js`
- `src/commands/registry.js`
- `tests/unit/agents.test.js`
- `tests/unit/agent-budget-contract.test.js`
- `tests/unit/tui-format.test.js`
- `tests/unit/tui-frame.test.js`
- `tests/unit/commands.test.js`

### 验证

已执行：

```powershell
node --test tests/unit/tui-format.test.js
node --test tests/unit/tui-frame.test.js
node --test tests/unit/commands.test.js
node --test tests/unit/agents.test.js
node --test tests/unit/agent-budget-contract.test.js
```

结果：

- thinking 默认隐藏、展开显示、复制保护均有单测覆盖。
- 子智能体大文件读取会被自动限制为 `maxBytes=8192`。
- `web-researcher` 搜索后端不可用时返回 partial，不再连续空转。

### 风险和边界

- `/thinking` 原先只影响本次 TUI 内存视图；该限制已在 2026-05-02 取消，保留的本地 transcript 可以恢复 thinking 原文。
- 子智能体输出限流会降低爆 buffer 概率，但复杂审计任务仍应拆成模块级子任务。
- 公网搜索能力仍依赖实际网络、SearXNG 或搜索 MCP 后端；本次只改失败行为，不伪造搜索结果。

## 2026-05-01：子智能体混合后台展示，右侧任务栏实时可观察

### 背景

用户认可“混合模式”：主智能体通过 `agent_run` 调用子智能体时仍等待结果，以便继续推理；但界面上不要把子任务过程噪声堆进聊天框，而是像 opencode 一样保留后台任务入口和运行状态。用户也明确不希望展示 thinking，只希望知道子智能体还活着、正在调用什么工具、完成后有清晰提示。

### 处理

- `src/core/session.js`
  - 在执行 `agent_run` 前预分配稳定 `taskId`。
  - `tool_start` / `tool_finish` 事件携带 `taskId`、`profile`、`taskStatus`，TUI 可以把开始和完成绑定到同一张任务卡片。
- `src/tools/definitions.js`、`src/tools/runtime.js`
  - `agent_run` 输入 schema 允许内部 `taskId`。
  - 工具运行时把预分配 `taskId` 传给 `runSubagent`，避免任务记录和 UI 卡片错位。
- `src/cli/tui.js`
  - `agent_run` 开始时聊天框出现“子任务已启动”卡片，完成/失败/partial 时更新同一张卡片，而不是重复刷多条工具日志。
  - 有 running/queued 子任务或正在查看任务栏时，TUI 自动轮询 `.lab-agent/tasks`，右侧任务栏会持续刷新。
  - `agent_run` 仍保持同步语义：主智能体拿到子任务结果后继续当前轮次；显式后台仍使用 `/background run <profile> <任务>`。
- `src/cli/tui/components.js`
  - 右侧任务栏显示 model tier、模型、预算、工具进度、最近工具和最新进展。
  - 入口文案改为 `/agents task <task-id>` 和 `/background run <profile> <任务>`。
- `src/cli/tui/format.js`
  - 新增 `agent` 类型任务卡片渲染：运行中、完成、partial、阻止、失败都有独立标记。
  - 常规工具/网关过程仍按原来的折叠逻辑处理，不污染主聊天。
- `src/commands/runtime.js`
  - `/agents task <task-id>` 作为 `/agents resume/show <task-id>` 的清晰别名。
  - 修正旧的 `/background` 禁用说明，避免和当前 TUI 后台能力矛盾。

### 验证

已执行：

```powershell
node --test tests/unit/session.test.js tests/unit/tui-format.test.js tests/unit/tui-frame.test.js tests/unit/agents.test.js tests/unit/config.test.js tests/unit/agent-router.test.js
```

结果：78 pass / 0 fail。

新增覆盖：

- `agent_run` 事件稳定携带同一个 `taskId`。
- 子智能体生命周期卡片展示为“子智能体 - 子任务完成/暂停/失败”等状态。
- 右侧任务栏显示预算和最近工具进度。

### 风险和边界

- 当前 `agent_run` 是“UI 后台化 + 主轮次等待结果”，不是完全 detach。主智能体需要子任务结论时仍会等待。
- 真正 detach 的显式后台路径是 `/background run <profile> <任务>`；模型工具层如需未来支持 `mode=detach`，还需要再设计结果回收机制。
- 右侧栏轮询依赖本地 task store 文件刷新；如果外部进程直接改坏 `.lab-agent/tasks`，列表视图会忽略坏记录，详情命令会报告错误。

## 2026-05-01：注册 Mimo v2.5 作为子智能体低成本模型 tier

### 背景

用户测试子智能体读取项目代码已成功，希望把 `mimo-v2.5` 作为 `mimo-v2.5-pro` 的低成本平替模型，用于 explorer/researcher 等弱场景任务，以便实际观察主智能体和子智能体是否按不同模型 tier 协作。

### 处理

- `lab-agent.config.json` 增加模型：
  - `mimo-v2.5`：低成本 quick/read-only 子任务模型，200k context。
  - `mimo-v2.5-pro`：默认和强模型，200k context。
- `agents.modelTiers` 增加映射：
  - `cheap -> mimo-v2.5`
  - `default -> mimo-v2.5-pro`
  - `strong -> mimo-v2.5-pro`
- 更新配置测试，确保项目配置同时注册两个模型，并验证 agent tier 映射。

### 验证

已执行：

```powershell
node --test tests/unit/config.test.js tests/unit/agent-router.test.js tests/unit/agents.test.js
```

结果：27 pass / 0 fail。

### 风险和边界

- `mimo-v2.5` 只是在配置层注册为 cheap tier；具体任务是否选它由 router 的 `modelTier` 决策决定。
- 当前 `reviewer` 和深度/高风险任务仍会走 `strong`，也就是 `mimo-v2.5-pro`。

## 2026-05-01：子智能体编排 v2 落地，默认 one-shot + 路由预算 + 严格复核

### 背景

用户希望吸收 opencode one-shot task agent 的稳定性和成本优势，同时参考 Oh My OpenAgent 的“主智能体全局调度、子智能体按角色分工、轻重任务按模型路由”的产品思路。设计审核时也明确要求避免沿用对方的众神命名风格，因此复核角色改为通用的 `reviewer` / “严格复核智能体”。

### 处理

- 新增设计文档：
  - `docs/plans/completed/subagent-orchestration-v2-design-2026-05-01.md`
  - 明确 Coordinator / Planner / Explorer / Researcher / Junior / Verifier / Reviewer / Browser Verifier 的边界。
  - 明确默认 one-shot，长任务通过 partial + continue 分段续跑。
- 新增 agent v2 基础模块：
  - `src/agents/contracts.js`：统一 findings/research/plan/patch/verification/review/partial 输出 contract。
  - `src/agents/budget.js`：新增 `maxRounds`、`maxToolCalls`、`maxDurationMs`、`maxOutputBytes`、连续失败和权限拒绝预算。
  - `src/agents/context-pack.js`：生成最小上下文包，避免把完整主会话历史塞给子智能体。
  - `src/agents/continuation.js`：预算触顶时生成 partial summary 和 continuation prompt。
  - `src/agents/review-policy.js`：提供高风险任务复核判断。
- 升级内置 profiles：
  - 新增 `junior`：执行型子任务代理，要求 `writeScope` 后才允许写文件。
  - 新增 `reviewer`：严格复核智能体，只读挑错、审查风险和测试缺口。
  - `code-worker` 保留兼容，并加执行型角色 metadata。
  - profile 支持 `role`、`purpose`、`modelTier`、`budget`、`canSpawnAgents` 等字段。
- 升级 Router：
  - `src/agents/router.js` 升级到 version 2。
  - 输出 `purpose`、`difficulty`、`risk`、`modelTier`、`budget` 和复核建议。
  - 实现任务类型到 `explorer/researcher/planner/junior/verifier/reviewer/browser-verifier` 的路由。
  - implementation 默认建议 `junior`，高风险或严格审查建议 `reviewer`。
- 升级 Runner：
  - `src/agents/runner.js` 接入 route decision、context pack、model tier 和 budget。
  - 子智能体不再只在轮数触顶时报 `AGENT_TOOL_LIMIT`，而是返回 `partial` 阶段结果。
  - `junior` 未提供 `writeScope` 时移除写入工具，防止无边界写文件。
  - 子任务结果写入 contract summary、budget、continuation prompt。
- 升级任务存储和命令：
  - `src/agents/task-store.js` 升级到 task record v2，保存 purpose/difficulty/risk/modelTier/contextPack/budget/partial 信息。
  - `/agents continue <task-id>` 可根据 continuation prompt 续跑 partial 任务。
  - `/agents review <task-id>` 可对任务结果启动 `reviewer` 严格复核。
  - `agent_run` 工具 schema 支持 `writeScope`、`acceptance`、`contextPack`。
- 升级 TUI 任务栏：
  - 右侧任务树展示 profile/purpose/difficulty/risk/model tier/预算和 partial 暂停原因。

### 验证

已新增和更新测试：

- `tests/unit/agent-budget-contract.test.js`
- `tests/unit/agent-router.test.js`
- `tests/unit/agent-task-store.test.js`
- `tests/unit/agents.test.js`

已执行针对性测试：

```powershell
node --test tests/unit/agent-router.test.js tests/unit/agent-task-store.test.js tests/unit/agent-budget-contract.test.js tests/unit/agents.test.js
```

结果：17 pass / 0 fail。

### 风险和边界

- `reviewer` 默认只读，不修改文件；自动复核策略应避免小任务过度打扰。
- `junior` 只有拿到明确 `writeScope` 才能写，后续仍需继续完善路径级 scope enforcement。
- 当前模型 tier 可以全部映射到同一个模型；后续接入便宜模型后只需改配置。
- partial 续跑是 one-shot episode 串联，不是长期在线子智能体。

## 2026-05-01：放宽工具轮次保护阀，并澄清“任意项目目录启动”的语义

### 背景

用户指出：从 `E:\tmp-file` 启动 Ant Code 是为了验证它在任意项目目录中的表现，不应该被解释成只能从 `lab-agent` 源码根目录启动。同时，子智能体存在工具轮数限制，用户担心跑超长任务时会频繁中断。

复盘后确认：

- Ant Code 的产品语义应是“从当前 cwd 所在项目启动并操作当前项目”。
- 只有当 cwd 本身只包含 `.lab-agent` / `.ant-code` 运行数据目录时，才需要提醒用户当前目录可能不是目标项目。
- 主智能体工具轮次之前硬编码为 3，比子智能体更紧，确实容易让多步工具任务过早撞到 `tool_limit`。
- 子智能体工具轮次之前提升到 5-6，但对长调查、MCP/browser/web 搜索等任务仍偏短。

### 处理

- 新增 `src/core/tool-rounds.js`：
  - 主会话默认 `limits.maxToolRounds = 16`。
  - 子智能体默认 `agents.maxRounds = 16`。
  - 提供 `resolveMainToolRounds` / `resolveSubagentToolRounds`，统一解析保护阀。
- `src/core/session.js`：
  - 移除主会话硬编码 `MAX_TOOL_ROUNDS = 3`。
  - 改为读取配置/环境变量。
  - 到达上限时返回中文解释，说明这是防无限工具循环保护，并提示可调高 `LAB_AGENT_MAX_TOOL_ROUNDS` 或 `limits.maxToolRounds`。
- `src/agents/runner.js`：
  - 子智能体上限改为 `agents.maxRounds` 优先，其次 profile `maxRounds`，最后默认 16，方便用环境变量/项目配置统一覆盖内置 profile。
  - 子智能体到达上限时返回中文错误，提示可通过 `LAB_AGENT_AGENT_MAX_ROUNDS` 或 `agents.maxRounds` 调整。
- `src/agents/profiles.js`：
  - `explorer`、`readonly-researcher`、`web-researcher`、`code-worker` 调整为 16 轮。
  - `planner`、`verifier`、`browser-verifier` 调整为 12 轮。
- 配置和部署模板：
  - `lab-agent.config.json` 增加 `limits.maxToolRounds: 16` 和 `agents.maxRounds: 16`。
  - `config/lab-agent.lab-template.json` 同步 16 轮默认值。
  - `config/lab-agent.high-sensitivity-template.json` 使用更保守的 12 轮默认值。
  - `docs/deployment/pre-launch-security-config.md` 增加 `LAB_AGENT_MAX_TOOL_ROUNDS` / `LAB_AGENT_AGENT_MAX_ROUNDS`。
- 工作区诊断文案调整：
  - 不再写“请从源码仓库根目录启动”这种容易误导的说法。
  - 改为“要调查哪个项目，就从哪个项目目录启动；如果 cwd 只有运行数据，需要确认目标路径”。

### 验证

已执行针对性测试：

```powershell
node --test tests\unit\config.test.js tests\unit\context.test.js tests\unit\tui-format.test.js tests\unit\agent-profiles-config.test.js tests\unit\agents.test.js tests\unit\session.test.js
node scripts\check-syntax.js
```

结果：

- 针对性测试：66 pass / 0 fail。
- 语法检查：125 files passed。

### 风险和边界

- 工具轮次放宽会增加复杂任务的网关请求次数和工具调用次数，这是为了降低正常长任务误中断的概率。
- 轮次上限仍然必须存在，用于防止模型无限工具循环、反复搜索、反复 MCP 调用或持续触发审批。
- 如果用户明确要跑超长任务，可以临时设置更高的环境变量；但不建议默认无限制。

## 2026-05-01：修复子智能体验收误判、工作区误启动提示和 Windows 中文编码保护

### 背景

用户测试“主智能体调用 explorer 子智能体”时，模型返回了乱码文本，并且子智能体结论说当前工作空间是 `E:\tmp-file`，只包含 `.lab-agent\sessions` 和 `.lab-agent\tasks`。这暴露出三个问题：

- `thinking` 显示“因隐私策略隐藏”，用户不确定这是不是正常行为。
- 子智能体确实被调用了，但继承了启动时的 cwd；如果从运行数据目录启动，就只能调查运行数据而不是源码仓库。
- explorer 等子智能体默认工具轮数过低，复杂一点的只读调查容易在返回最终结论前触发 `AGENT_TOOL_LIMIT`。
- 会话 JSON 中中文原文正常，但终端复制/显示可能出现 UTF-8/GBK 乱码。

### 处理

- 确认并保留 `thinking` 隐藏策略：
  - TUI 只显示 thinking 字节数和“已隐藏/因隐私策略隐藏”。
  - 原始 thinking 当时仍作为 memory-only 事件处理，不进入可复制输出；2026-05-02 起本地 session transcript 会保留 assistant message 的 thinking 以支持 `/resume` 复盘。
- 新增 `src/core/workspace-diagnostics.js`：
  - 检测源码标记（如 `.git`、`package.json`、`src/`、`tests/`、`README.md` 等）。
  - 检测当前 cwd 是否只包含 `.lab-agent` / `.ant-code` 运行数据目录。
  - 生成中文警告：当前 cwd 可能不是源码仓库，应从源码根目录启动。
- 将工作区诊断接入：
  - `buildInitialContext` 会把诊断结果写入 system prompt，但不暴露完整绝对路径，保持路径最小化。
  - `createSession` 保存 `workspaceDiagnostic`，TUI 启动页和确认框会显示提醒。
  - `/status` / `/map` 的 repository map 会展示工作区警告，便于命令行模式排查。
- 提升子智能体可用性：
  - `DEFAULT_AGENT_TOOL_ROUNDS` 从 2 提升到 5。
  - `explorer`、`readonly-researcher`、`web-researcher`、`code-worker` 明确配置 `maxRounds: 6`。
  - `planner`、`verifier`、`browser-verifier` 配置 `maxRounds: 5`。
  - 这样只读调查有足够空间完成“读文件/搜索/汇总”的闭环。
- Windows TUI 编码保护：
  - TUI 启动时尝试将 Windows 控制台 Input/Output code page 切到 UTF-8（65001）。
  - 退出时恢复启动前 code page。
  - 会话存储本身已验证为 UTF-8 正常，这一改动主要降低终端显示/复制链路乱码概率。

### 验证

已执行：

```powershell
node --test tests/unit/context.test.js tests/unit/tui-format.test.js tests/unit/agent-profiles-config.test.js tests/unit/commands.test.js
node scripts/check-syntax.js
npm run check
```

结果：

- 针对性测试：74 pass / 0 fail。
- 完整检查：290 pass / 0 fail。
- 语法、禁用端点、provenance、依赖策略全部通过。

### 风险和边界

- 工作区诊断只是提示和模型上下文约束，不会阻止用户从非源码目录启动。
- Windows code page 切换依赖本机控制台能力；如果终端或宿主复制链路仍强制用非 UTF-8，可能还需要用户手动执行 `chcp 65001` 或换用 Windows Terminal。
- 子智能体工具轮数提高会增加单次复杂任务的网关调用次数，但能显著降低“查到一半没总结”的失败率。

## 2026-05-01：完成外部能力 Stage 7-10，落地子智能体路由、并行只读任务树和权限审计

### 背景

前一轮已经完成外部能力 Stage 1-6：MCP 推荐配置、内置网络抓取/搜索、文档 intake、本地 skill pack。用户验收后要求继续完成 Stage 7-10，把“可以手动调用子智能体”升级为“主智能体知道什么时候该调配子智能体”，并且长任务需要更像成熟代码智能体：先派只读调查、计划、验证等子任务，右侧栏能看到任务状态，同时不能因为 MCP/browser/network 能力增强而牺牲安全边界。

### 处理

- 扩展内置 agent profile 到 v2：
  - 增加 `triggerHints`、`skills`、`mcpServers`、`outputContract`。
  - 为 `explorer`、`readonly-researcher`、`planner`、`verifier`、`code-worker` 补齐触发提示和输出契约。
  - 新增 `web-researcher`，专门处理联网搜索、网页抓取、来源整理。
  - 新增 `browser-verifier`，专门处理浏览器/前端/TUI/Web UI 验收。
- 新增 `src/agents/router.js`：
  - 根据用户任务文本识别 web、browser、repository、planning、verification、implementation 信号。
  - 输出主推荐 profile、候选评分、推荐子任务、是否可并行和风险提示。
  - 新增 `/agents route <任务>`，用户可以直接查看调度判断。
- 新增 `src/agents/orchestrator.js`：
  - 新增 `/agents orchestrate <任务>`。
  - 只自动并行启动只读子任务，避免并发写文件、并发浏览器动作或隐藏高风险审批。
  - 写入型 `code-worker`、执行型 `verifier/browser-verifier` 保留为串行建议。
  - 创建父任务记录和子任务记录，形成可追踪任务树。
- 任务可观察性增强：
  - `createAgentTaskStore` 增加 `parentTaskId`、`title`、`route` 字段。
  - `/agents tasks` 和 `/tasks` 改为展示任务树。
  - TUI 右侧“任务”栏改为任务树视图，能看到父任务、子任务、状态和最新进度。
- 子智能体边界增强：
  - `runSubagent` 会把 profile 的 `skills` 和 `mcpServers` 写入子智能体 system prompt。
  - 子智能体 MCP runtime 会按 profile 限制可见 MCP server。
  - 工具运行时会阻止子智能体读取或运行未声明的 skill/MCP server。
  - 子智能体仍不能递归调用 `agent_run`。
- 权限和审计增强：
  - 工具风险类别扩展到 `network`、`browser`、`document`、`mcp`、`memory`。
  - `document_intake` 标记为 `document` 风险，强调有界本地文本抽取。
  - Playwright MCP 浏览器动作标记为 `browser` 风险。
  - Memory MCP 读写标记为 `memory` 风险，其中写长期记忆需要审批。
  - MCP 子进程默认 scrub API key、token、secret、password、OAuth、SSH_AUTH_SOCK、AWS、Anthropic/OpenAI key 等敏感环境变量。
  - MCP server 可通过显式 `envAllowlist`/`envAllow` 保留经审查的必要变量。
  - `/mcp status` 现在能看到被 scrub 的环境变量名，便于排查“为什么 MCP 没拿到某个 env”。
- 文档更新：
  - 更新 `LLM_ONBOARDING.md`，写清 router/orchestrator、profile v2、风险类别、MCP env scrub、常见开发坑。
  - 更新外部能力计划文档状态为 Stage 1-10 已完成。
  - 新增 `docs/deployment/v1.4-orchestration-acceptance.md`，包含人工验收脚本。

### 验证

已执行针对性测试：

```powershell
node --test tests/unit/agent-profiles-config.test.js tests/unit/agent-router.test.js tests/unit/agent-task-store.test.js tests/unit/permissions.test.js tests/unit/mcp.test.js
node scripts/check-syntax.js
```

当前正在以 `npm run check` 作为最终收口验证；该命令覆盖语法、禁用端点、provenance、依赖策略和完整测试套件。

### 风险和边界

- `/agents orchestrate` 只自动启动只读并行子任务；不会自动并行写代码。
- 浏览器、MCP、网络和长期记忆写入仍走权限策略。
- 如果模型不主动用 `/agents route` 或 `agent_run`，router 不会神奇替模型决策；当前是“系统提示 + 可调用工具 + 手动命令”的组合。
- 子智能体输出契约是提示词和测试保障，不是强 JSON schema 强制解析；后续如果要机器合并子任务结果，可以再做严格结构化返回。

## 2026-05-01：切换默认模型到 Mimo v2.5 Pro / Token Plan 网关

### 背景

原先测试 key 的额度已经耗尽，用户提供了新的 Token Plan OpenAI-compatible 网关、API key 和模型名，需要让全局 `ant-code` 与当前仓库默认模型都切换到新模型。

### 处理

- 将仓库默认模型从旧 Claude 别名切换为 `mimo-v2.5-pro`。
- 将 `lab-agent.config.json` 的模型列表收敛为 `mimo-v2.5-pro`，上下文窗口保持 `200000` tokens。
- API key 未写入仓库文件。
- 使用 Windows 用户级环境变量持久化以下运行配置：
  - `LAB_MODEL_GATEWAY_URL`
  - `LAB_MODEL_GATEWAY_API_KEY`
  - `LAB_MODEL_GATEWAY_PROTOCOL=openai-chat`
  - `LAB_AGENT_MODEL=mimo-v2.5-pro`
  - `LAB_AGENT_NETWORK_MODE=lab-only`
- 将网关地址修正为 OpenAI Chat Completions 完整接口路径 `/v1/chat/completions`，因为当前客户端不会自动拼接该路径。

### 验证

已执行：

```powershell
ant-code gateway
'ant-code smoke test' | ant-code -p --output-format text
```

结果：

- 全局 `ant-code` 已读取到 `mimo-v2.5-pro`。
- `ant-code gateway` 显示 OpenAI-compatible 网关 URL 和 `lab-only` 网络策略均通过。
- 最小真实模型请求成功返回文本。

## 2026-05-01：TUI 消息块操作、复制、回退编辑和重生成

### 背景

用户希望 Ant Code 不再依赖终端原生文本选择来复制聊天内容，因为原生复制经常会把右侧栏、边框和无关 UI 一起复制进去。用户更希望像 opencode 一样把聊天记录视为“消息块”：可以选中某个用户/助手消息块，对这条消息执行复制、回退编辑、重新生成等操作。

### 处理

- 为 TUI transcript 的每条 entry 增加稳定 `id`，并在 `transcriptViewport` 返回的每一行上保留 `entryId`、`entryKind` 和 `selectable` 元数据。
- 新增鼠标主键点击解析：
  - 支持 SGR、X10、urxvt 常见鼠标上报格式。
  - 点击聊天区内的消息行会定位到对应消息块。
  - 仍保留原有鼠标滚轮滚动逻辑。
- 新增“消息操作”底部面板：
  - `复制当前消息块`
  - `复制从这里到最新`
  - 用户消息额外支持 `回退到这里并放回输入栏`
  - 用户消息额外支持 `从这里重新生成`
- 复制不再依赖终端选择：
  - Windows 下使用 PowerShell `Set-Clipboard` 写入系统剪贴板。
  - 复制失败时会在会话和 Inspector 中提示原因。
- 用户消息发送时记录 `checkpointMessagesLength`：
  - 回退编辑会把 `session.messages` 截断到该用户消息发送前。
  - 可见 transcript 会截断到该消息之前，并把消息正文放回输入栏。
  - 从此处重新生成会先做同样截断，再自动重新提交该条用户消息。
- 恢复会话时会根据恢复的 `messages` 重新构建 checkpoint，因此恢复出来的用户消息也可以回退和重生成。
- 明确产品边界：
  - 对话回退只影响模型上下文和 TUI transcript。
  - 不会自动撤销之前工具已经写入或修改的文件。
- `/keybindings` 和底部 Footer 增加“鼠标点击消息块”的提示。

### 验证

已执行：

```powershell
node --test tests\unit\tui-format.test.js tests\unit\tui-interaction.test.js
node scripts\check-syntax.js
npm run check
```

结果：

- TUI format / interaction 针对性单测通过：32 pass / 0 fail。
- 语法检查通过：120 files。
- 全量检查通过：278 pass / 0 fail。
- 禁用端点扫描、provenance 检查和依赖策略检查均通过。

### 后续人工验收重点

- 点击一条用户消息或助手消息，确认该消息块出现选中高亮，并弹出“消息操作”面板。
- 选择“复制当前消息块”，粘贴到外部编辑器，确认只包含当前消息块正文，不包含右侧栏和边框。
- 选择“复制从这里到最新”，确认会复制从选中消息开始的后续主要对话内容。
- 对用户消息选择“回退到这里并放回输入栏”，确认：
  - 后续对话从当前 TUI 中消失。
  - 该用户消息正文回到输入框。
  - 文件系统已发生的改动不会自动撤销。
- 对用户消息选择“从这里重新生成”，确认：
  - 后续对话被截断。
  - Ant Code 自动从该条用户消息重新发起一轮。

## 2026-05-01：修复 MCP 调用审批未接入导致 blocked/tool_limit

### 背景

用户在 TUI 中看到：

- `[blocked] mcp - mcp_call blocked`
- `decision=ask`
- 随后出现“工具上限：在最终助手响应前已达到工具调用上限”

这说明 MCP 工具调用被权限系统判定为“需要询问用户”，但没有正常进入审批弹窗，导致工具直接返回 blocked。模型拿不到 MCP 结果后继续尝试工具，最终撞到工具轮数上限。

### 处理

- 将 `mcp_call` 的 `decision=ask` 接入普通工具审批链路：
  - TUI 会弹出权限确认框。
  - CLI interactive 也会询问批准。
  - 用户批准后才真正调用 MCP tool。
- 子智能体和 slash `/mcp call` 路径也接入同一个 MCP 审批回调。
- “本会话始终允许”不再粗暴匹配所有 MCP：
  - 改成按 `server/tool` 粒度匹配，例如 `mcp:local-echo:echo`。
  - 避免批准一次 MCP 调用后放开所有 MCP 工具。
- MCP 审批预览中明确显示：
  - server
  - tool
  - arguments 字节数或参数摘要

### 验证

已执行：

```powershell
node --test tests\unit\mcp.test.js tests\integration\print-mode-gateway.test.js
node --test tests\unit\tui-format.test.js tests\unit\commands.test.js
node scripts\check-syntax.js
```

结果：

- MCP / print-mode gateway 针对性测试通过：26 pass / 0 fail。
- TUI format / commands 针对性测试通过：61 pass / 0 fail。
- 语法检查通过：120 files。

## 2026-05-01：Inspector 普通列表不再误用红色

### 背景

用户在 TUI 中输入 `/mcp` 查看 MCP 配置时，右侧 Inspector 出现大量红色文本，容易被误认为是报错。实际原因是 Inspector 的通用文本高亮把所有 `- ` 开头的项目符号都当作 diff 删除行处理。

### 处理

- 将 Inspector 普通命令输出和 diff/patch 输出的着色逻辑分开。
- 普通命令输出中的 `- fetch`、`- playwright` 等列表项不再染红。
- 只有真正 diff/patch 视图中的删除行才使用红色。
- 保留错误、阻塞、危险操作继续使用红色，降低 UI 语义歧义。

### 验证

已执行：

```powershell
node --test tests\unit\tui-inspector.test.js tests\unit\tui-frame.test.js
node scripts\check-syntax.js
```

结果：

- TUI inspector / frame 针对性单测通过：19 pass / 0 fail。
- 语法检查通过：120 files。

## 2026-05-01：MCP 默认启用策略调整

### 背景

用户指出：当前项目已经脱离 Claude 生态，Stage 1-6 选用的是实验室主动挑选的开源 MCP 和本地 skill，不应继续把所有推荐 MCP 默认 disabled，否则会削弱开箱即用的外部能力体验。

### 处理

- 将自包含、免 key、开源 MCP 调整为默认启用：
  - `fetch`
  - `duckduckgo-search`
  - `playwright`
  - `filesystem`
  - `memory`
  - `sequential-thinking`
- 保留按配置启用：
  - `searxng`：需要实验室本地 SearXNG 服务。
  - `sqlite`：需要明确数据库路径和数据使用场景。
- `/mcp doctor` 语义调整：
  - 普通 `/mcp doctor` 只检查配置和启动命令，不自动拉起 MCP 进程。
  - `/mcp doctor --live` 才会真正启动 enabled MCP 并发现 tools。
- 更新 system context、计划文档和 provenance，避免继续表达“推荐 MCP 默认关闭”的旧策略。

### 验证

已执行：

```powershell
node --test tests\unit\commands.test.js tests\unit\mcp.test.js tests\unit\context.test.js
node -e "JSON.parse(require('fs').readFileSync('lab-agent.config.json','utf8')); console.log('json ok')"
```

结果：

- commands / mcp / context 针对性单测通过：50 pass / 0 fail。
- `lab-agent.config.json` JSON 解析通过。

## 2026-05-01：外部能力与 skill/MCP 落地 Stage 1-6

### 背景

用户确认先做计划中的 Stage 1-6，即先把 MCP、内置联网能力、文档解析和本地 skill pack 落地；Stage 7 之后的子智能体 router、并行调度和任务树等验收通过后再做。

### 处理

- 新增能力注册表：
  - `src/capabilities/registry.js`
  - 新增 `/capabilities` 命令，显示内置工具、MCP、skills、子智能体。
- 新增推荐 no-key MCP 清单：
  - `fetch`
  - `duckduckgo-search`
  - `searxng`
  - `playwright`
  - `memory`
  - `filesystem`
  - `sequential-thinking`
  - `sqlite`
- 推荐 MCP 均默认关闭，并补充 `/mcp doctor`：
  - disabled 状态不会拉起第三方进程。
  - enabled 状态会检查命令和工具发现结果。
- 新增内置网络工具：
  - `web_fetch`：受网络权限策略控制，支持 text/markdown/html。
  - `web_search`：优先 SearXNG 配置，默认 DuckDuckGo HTML fallback，结果需要模型引用来源。
- 新增本地文档工具：
  - `document_intake`：支持 txt/md/json/csv/xml/html 和轻量 docx/pptx/xlsx 解析。
  - PDF 不在 clean-room core 内做二进制解析，提示通过 MarkItDown 或外部转换器处理。
- 新增本地 skill pack：
  - `web-research`
  - `browser-automation`
  - `document-intake`
  - `project-intake`
  - `bug-repro`
  - `frontend-verifier`
  - `release-review`
- skills registry 增加 bundled skill root，确保全局运行时也能看到仓库自带 `config/skills`。
- 更新子智能体 profiles，让默认 build/research/planner/verifier/code-worker 能看到 `web_fetch`、`web_search`、`document_intake` 等新能力。
- 更新 `LLM_ONBOARDING.md`，记录新能力层、常见坑和 Stage 7-10 尚未落地的边界。
- 更新计划文档状态，标注 Stage 1-6 已实现待验收，Stage 7-10 暂缓。

### 验证

已执行：

```powershell
node --test tests\unit\tools.test.js
node --test tests\unit\commands.test.js
node scripts\check-syntax.js
node --test tests\unit\agent-profiles-config.test.js tests\unit\agents.test.js
npm run check
```

结果：

- tools 单测通过：25 pass / 0 fail。
- commands 单测通过：40 pass / 0 fail。
- agent profiles / agents 单测通过：7 pass / 0 fail。
- 语法检查通过：120 files。
- 全量检查通过：syntax、forbidden endpoints、provenance、dependency policy、274 tests 全部通过。

- 补充 `docs/provenance/modules/capabilities.md`，让新能力注册模块纳入 clean-room provenance 审计。
- 修正 agent 单测隔离：无网关降级用例显式使用空测试环境，避免本机真实 `LAB_MODEL_GATEWAY_URL` 影响测试判断。
- 没有把本地网关 API key、cookie、token 或真实会话内容写入仓库。

## 2026-05-01：外部能力与子智能体编排升级计划

### 背景

当前 Ant Code 已完成 clean-room TUI、会话恢复、compact、权限、todo/plan 侧栏、基础 MCP/skill/subagent 能力，但用户指出：相比旧版 Ant Code 和 opencode，当前版本的 skill、MCP、子智能体生态仍偏弱。如果只具备读代码、写代码、改代码能力，会限制它对项目对接、外部资料获取和复杂任务调度的把控度。

### 处理

- 新增计划文档：
  - `docs/plans/completed/external-capabilities-agent-orchestration-upgrade-plan-2026-05-01.md`
- 计划中明确下一轮升级目标：
  - 免 key 网络检索和网页抓取。
  - 浏览器自动化。
  - 文档解析。
  - 本地 skill pack。
  - 更强的子智能体 profiles、router、并行任务和右侧任务树。
  - MCP doctor、skills doctor、capability registry。
- 计划中记录了 opencode 和旧 Ant Code 的可借鉴点：
  - opencode 的只读 task agent、内置 fetch、MCP 自动发现和统一权限。
  - 旧 Ant Code 的内部化 skills、sidecar worker、能力清单和验证入口。
- 同时明确不做事项：
  - 不接入远端 skill marketplace。
  - 不默认安装任意第三方 skill。
  - 不做 Anthropic 原生协议。
  - 不把旧 Ant Code 的 `.claude` 目录直接搬进当前实现。

### 验证

本次只新增计划文档和维护日志，没有改业务代码，未运行测试。

## 2026-05-01：待办完成状态同步修复

### 背景

用户实测确认：`todo_write` 已能正常唤出右侧“待办”栏并显示任务，但任务结束时右栏没有可靠同步为完成状态。这个问题会让用户误以为任务仍在进行，即使主聊天区已经给出完成结论。

### 处理

- 扩展 workflow 状态归一化，适配中文母语环境：
  - `完成`、`已完成`、`成功`、`通过`、`结束` 等归一化为 `completed`。
  - `进行中`、`执行中`、`处理中`、`正在进行`、`已开始`、`当前` 等归一化为 `in_progress`。
  - `待办`、`待处理`、`未开始`、`等待`、`未完成` 等归一化为 `pending`。
  - `取消`、`跳过` 等归一化为 `cancelled`。
- workflow item 支持更多模型常见字段：
  - 状态字段除 `status` 外，也接受 `state`、`progress`。
  - 布尔字段 `done`、`completed`、`checked`、`finished` 可直接表示完成。
  - `active`、`current`、`running`、`started` 可表示进行中。
- 增加 session 级最终态兜底：
  - 如果模型最终回答明确表示“全部完成 / 已完成”，但漏掉最后一次 `todo_write` / `plan_update`，本地会把仍处于 `in_progress` 的项同步为 `completed`。
  - 在强完成语义下，也会把仍为 `pending` 的可见项同步为 `completed`。
  - 如果最终回答包含“未完成 / 失败 / 无法完成 / blocked”等语义，不做自动完成，避免误报。
- 增加 TUI 事件 `workflow_updated`：
  - 本地兜底同步发生时，右侧栏自动切到“待办”。
  - 侧栏滚动位置归零。
  - 主日志追加一条“状态同步”记录，方便回看。

### 验证

执行过：

```powershell
node --test tests\unit\tools.test.js
node --test tests\unit\session.test.js
node --test tests\unit\events.test.js
npm run check
```

结果：

- workflow 工具测试通过：21 pass / 0 fail。
- session 主循环测试通过：11 pass / 0 fail。
- AntEvent 事件测试通过：6 pass / 0 fail。
- 全量检查通过：265 pass / 0 fail。

### 后续小修：主会话过程日志折叠

用户继续反馈：主会话框里持续堆叠 `gateway`、`tool`、`run/edit/ok` 等过程日志，虽然能说明系统在运行，但完成后会显得臃肿，影响阅读真正的人机对话。

处理：

- 调整 TUI transcript 渲染层，不改变底层事件、工具执行或 inspector 记录。
- `Ctrl+O` 三档现在对运行过程的含义更清晰：
  - 紧凑：隐藏成功的网关、工具、轮次等 routine telemetry，只保留用户消息、助手回答、错误、审批、失败/阻止的工具。
  - 详细：把连续 routine telemetry 合并成一条“过程 - 已收起 N 条运行过程”摘要。
  - 完整：展开原始 gateway/tool/turn 过程日志，便于排查。
- 失败、被阻止、中断的工具调用仍在紧凑模式直接显示，避免重要风险被折叠掉。

补充验证：

```powershell
node --test tests\unit\tui-format.test.js
node --test tests\unit\tui-frame.test.js
node --test tests\unit\tui-format.test.js tests\unit\tui-scroll-region.test.js tests\unit\tui-interaction.test.js
node scripts/check-syntax.js
npm run check
```

结果：全量检查通过，267 pass / 0 fail。

## 2026-05-01：OpenCode 式需求确认和工作流侧栏对齐

### 背景

用户询问 Ant Code 是否具备 OpenCode 那类“核对用户需求时弹出选择栏、可勾选需求或填写自定义内容、确认后再发送给模型”的流程，同时确认长任务规划时 todo 是否会像 OpenCode 一样同步显示在侧栏。

本次处理参考了 OpenCode 公开仓库中的设计思路：模型侧通过结构化 question/todo 工具表达交互意图，TUI 订阅会话状态并负责渲染选择、确认和 todo 视图。没有引入 OpenCode 源码，也没有新增外部依赖。

### 修改内容

1. `ask_user` 工具能力增强
   - `ask_user` 从普通文本问答升级为支持：
     - 单选选项。
     - 多选 checklist。
     - 自定义补充输入。
     - Enter 确认。
     - Esc 取消。
   - 工具 schema 增加：
     - `header`
     - `multiple`
     - `allowCustom`
     - `confirmLabel`
   - `choices` 现在兼容字符串数组，也兼容对象数组，例如 `{ label, description, selected }`。

2. TUI 底部确认区
   - 没有采用新的悬浮弹层，避免再次影响主聊天框、滚轮和 resize。
   - 选择问题直接渲染在稳定的底部输入区域：
     - `↑/↓` 移动选项。
     - `Space` 勾选多选项。
     - `Enter` 提交当前选择或自定义输入。
     - `Esc` 取消问题。
   - 自定义输入复用现有输入编辑器，因此 Backspace/Delete、中文宽字符光标、Ctrl+A/E/K/U 等路径仍走原有稳定逻辑。

3. 模型行为提示
   - system context 增加明确约束：
     - 多步骤任务应使用 `todo_write` / `plan_update`，让 TUI 侧栏可跟踪进度。
     - 需求不明确时应使用 `ask_user`，需要 checklist 时设置 `multiple=true`，允许补充时设置 `allowCustom`。

4. 侧栏 todo 结论
   - 当前项目已经有 OpenCode-like 的右侧工作流侧栏：
     - `status` 页展示待办、计划、改动、验证数量。
     - `待办` 页展示 todo、plan、最近改动、最近验证。
   - 触发条件是模型调用 `todo_write` / `plan_update`，或用户使用 `/todo` / `/plan`。
   - 本次补了系统提示，提升模型在长任务中主动维护侧栏 todo 的概率。

### 修改文件

- `src/tools/definitions.js`
- `src/cli/tui.js`
- `src/cli/tui/components.js`
- `src/cli/tui/format.js`
- `src/context/builder.js`
- `tests/unit/tui-format.test.js`
- `tests/unit/tools.test.js`
- `PROJECT_CHANGELOG.zh-CN.md`
- `LLM_ONBOARDING.md`

### 验证

执行过：

```powershell
node scripts/check-syntax.js
node --test tests\unit\tui-format.test.js tests\unit\tools.test.js
npm run check
```

结果：

- 语法检查通过。
- 针对性单测通过：50 pass / 0 fail。
- 全量检查通过：261 pass / 0 fail。

注意：第一次直接运行全量检查时，本机终端环境带有真实 lab gateway 环境变量，导致两个“无网关降级路径”的子智能体单测失败；清理当前 PowerShell 子进程内的 gateway 相关环境变量后，全量检查通过。没有打印或写入任何密钥到仓库文件。

### 后续小修：确认后推动 workflow 同步

用户实测发现：`ask_user` 选择栏可以出现，但右侧“待办”栏仍显示“暂无待办”。为降低模型确认后漏调 workflow 工具的概率，并提升工具调用后的可见性，补充两点：

- `ask_user` 的返回结果在有选项时附带 `workflowReminder`，提示模型如果确认结果会启动多步骤任务，应先调用 `todo_write` / `plan_update` 再最终回答。
- TUI 收到 `todo_write` 或 `plan_update` 成功事件后，自动切换到右侧“待办”面板，并把侧栏滚动位置归零。

补充验证：

```powershell
node scripts/check-syntax.js
node --test tests\unit\tui-format.test.js tests\unit\tui-frame.test.js tests\unit\tools.test.js
```

结果：50 pass / 0 fail。

### 后续小修：todo 字符串数组和大段粘贴

用户继续实测发现两个问题：

1. 模型确认后会规划 todolist，并自动切到“待办”，但待办仍为空。
2. 大段多行文本粘贴进输入栏时，会把底部输入区域和聊天框布局撑坏；回车也容易在未编辑完成前触发发送。

处理：

- `todo_write` / `plan_update` 的 workflow item 归一化增强：
  - 支持字符串数组，例如 `items: ["确认需求", "验证侧栏"]`。
  - 支持常见对象字段：`content`、`text`、`title`、`task`、`description`、`label`、`name`、`value`。
  - `todo_write` 支持 `items`、`todos`、`tasks`、`list`。
  - `plan_update` 支持 `steps`、`plan`、`items`。
  - 避免模型工具调用成功但因为字段形态不同而把列表归一化为空。
- TUI 启用 bracketed paste：
  - 粘贴多行文本会作为一个整体插入草稿，不再把每个换行当作提交键。
  - 粘贴内容会清理 bracketed paste 控制序列和不可见控制字符。
- 底部输入栏新增大段文本紧凑显示：
  - 大段多行草稿显示为黄色摘要，例如 `{12 lines, 86 bytes 粘贴文本}`。
  - 避免输入框被多行内容撑开。
- 聊天区对大段用户粘贴文本也做紧凑显示：
  - 默认折叠成 `{N lines, N bytes 粘贴文本}`。
  - `Ctrl+O` 可切换完整/折叠显示。

补充验证：

```powershell
node scripts/check-syntax.js
node --test tests\unit\tools.test.js tests\unit\tui-format.test.js tests\unit\tui-frame.test.js tests\unit\tui-input-editor.test.js
```

结果：55 pass / 0 fail。

### 后续小修：完成状态同步

用户实测发现：待办可以正常唤出并显示，但模型完成任务时右侧待办栏没有同步为完成状态。

处理：

- 扩展 workflow status 归一化：
  - `complete`、`finished`、`success`、`succeeded`、`passed`、`pass`、`ok` 都归一化为 `completed`。
  - `current`、`active`、`running`、`started`、`doing`、`working`、`wip` 都归一化为 `in_progress`。
  - `todo`、`open`、`queued`、`not_started` 都归一化为 `pending`。
  - `cancel`、`skipped` 等归一化为 `cancelled`。
- 系统提示补充：
  - 多步骤任务开始时应把当前项标为 `in_progress`。
  - 最终回答前，应调用 `todo_write` / `plan_update` 把已完成项更新为 `completed`。
- `ask_user` 的 `workflowReminder` 也补充最终回答前同步完成状态的提示。

补充验证：

```powershell
node scripts/check-syntax.js
node --test tests\unit\tools.test.js tests\unit\context.test.js
```

结果：23 pass / 0 fail。

## 2026-04-30：从零重构到可交付 Ant Code 内部版

### 背景

本轮工作从 `C:\saveproject\LBJ-workspace\lab-agent` 这个新实现仓库推进，目标是把实验室使用的 Ant Code 从历史参考项目迁移到可维护、可验收、可本地部署的新版本。旧项目 `ant-code-latest` 已按用户要求归档到 `C:\saveproject\ant-code项目备份`，后续迭代只维护 `lab-agent`。

重构过程中，旧项目和 OpenCode 主要作为交互体验、功能边界、用户预期和产品思路参考；实际代码、配置、测试、文档和运行时实现都落在 `lab-agent` 仓库内。项目持续遵守本地网关、权限确认、MCP 显式配置、skill 本地化、无密钥入仓的安全边界。

### 分阶段开发流水

下面按本轮从零重构的实际推进顺序记录。日期以验收文档和本次连续开发节点为准，同一天内的多轮修复合并为阶段记录。

#### Phase 0：旧项目审计与 clean-room 边界建立

- 阅读和整理旧项目能力边界，只把可观察行为、用户预期、审计结论和净化后的产品规格作为输入。
- 建立不复制旧源码、不引入旧 bundle/source map、不接入 provider 私有端点、不写入密钥的基本边界。
- 形成初始文档体系：
  - 产品规格。
  - MVP 架构。
  - 数据边界。
  - 工具和权限模型。
  - provenance policy。
  - forbidden endpoint 检查。
- 明确 `lab-agent` 是当前唯一实现仓库，旧 `ant-code-latest` 只作为历史参考和后续归档对象。

#### v1.0：MVP 内部可运行版

- 搭建 Node CLI 项目骨架，公开命令逐步对齐为 `ant-code`，保留 `lab-agent` 作为内部兼容别名。
- 建立配置加载体系：
  - 环境变量。
  - `lab-agent.config.json`。
  - lab template。
  - high-sensitivity template。
- 建立 lab gateway 协议边界：
  - 模型请求只发往显式配置的实验室网关。
  - provider key 不进入客户端仓库。
  - OpenAI-compatible adapter 作为本地网关兼容路径。
- 建立本地工具系统：
  - 读文件。
  - glob/grep。
  - 写文件。
  - 精确替换编辑。
  - PowerShell 命令。
  - git status/diff。
  - todo/plan/workflow 工具。
- 建立权限系统：
  - workspace 内外路径判断。
  - secret-like path 拒绝。
  - 写操作 ask/allow/deny。
  - 命令风险分类。
  - 网络模式约束。
- 建立 session metadata：
  - bounded metadata。
  - transcript retention。
  - zero-retention high-sensitivity 模式。
  - session cleanup。
  - resume 基础能力。
- 建立 release seal 和审计脚本：
  - dependency policy。
  - forbidden endpoints。
  - provenance completeness。
  - release audit。
  - SBOM / license summary。
- v1.0 重点是“能安全跑起来”和“可审计”，TUI 体验只作为早期预览。

#### v1.1：体验对齐第一轮

- 目标：从“安全 MVP”推进到“像日常代码智能体一样能用”。
- 打通 gateway SSE streaming：
  - assistant delta。
  - gateway stream start/stop。
  - assistant final。
  - turn complete。
- TUI 开始实时渲染模型输出，而不是只在结束后显示。
- 支持 provider-exposed thinking/reasoning delta 的可见摘要，但保持隐私边界。
- 增加 tool-call argument streaming 和本地工具运行状态显示。
- Startup surface 展示 Ant Code 身份、模型、网关、权限模式、网络模式和本地工具边界。
- Prompt composer 增强：
  - slash command discovery。
  - workspace file mentions。
  - `!` 本地 shell 模式。
  - busy 时队列提示。
  - permission mode cycling。
  - 更清晰的 approval modal 文案。
- `/model` 增加 TUI selector，`/model list` 和 `/model use <model-id>` 支持直接命令切换。
- product commands 覆盖 model、cost/usage、context、keybindings、sessions、memory、MCP、agents 等表面。
- 对还没做完的远端/高级能力，改为明确的 lab-local disabled state，而不是假装可用。
- v1.1 验证记录：
  - `npm run verify:release` 通过。
  - 当时测试规模约 176 个。
  - `node src/cli/index.js -p "Reply exactly: sonnet-ready"` 等 smoke 通过。

#### 2026-04-29：v1.1 后续 TUI 修复和真实终端反馈

- 修正 `/guide <message>` 的产品语义：
  - 不声明能注入同一个 in-flight model request。
  - 明确为中断当前活跃 turn 后运行 guidance。
- FooterBar 和 `/keybindings` 对齐真实快捷键：
  - `Esc`/`Ctrl+G` 中断路径。
  - `Ctrl+C` 两次确认退出。
  - 小窗口 scrollback 说明。
- 修复小窗口滚动策略：
  - 起初小窗口只能方向键查看。
  - 后续改为让原生终端 scrollback 和 TUI owned scroll layout 分工。
  - 多次处理“滚轮闪回顶部/底部”和“固定界面残影”。
- 修复大窗口重复界面：
  - 清理 startup/resize 后残留帧。
  - 减少 idle pulse redraw 导致的重复界面。
  - 重新计算 transcript row budget。
- 修复 `Ctrl+O` 折叠/展开不可见问题：
  - 支持 compact/detail/full。
  - 对没有显式换行的长段落也能折叠和展开。
- 修复 `/resume`：
  - 支持 `/resume latest`。
  - 支持可见 UUID 前缀匹配。
  - 支持恢复 bounded retained user/assistant messages。
  - legacy metadata-only 记录仍只恢复 id/turn 状态。
- `/sessions` picker 从 id 优先改为标题优先，短 id 只作为辅助识别。
- 2026-04-29 后续验证：
  - targeted TUI 测试通过。
  - 全量 `npm run check` 从约 218 个测试推进到约 220 个测试通过。

#### v1.2：TUI polish 九阶段收口

- Stage 1 renderer/theme：
  - 建立 semantic theme tokens。
  - sky-blue 成为默认主题。
  - 保留 ant-code、terminal-default、no-color。
  - 增加 bounded frame tests。
- Stage 2 composer/input：
  - 输入框支持插入光标。
  - 支持 CJK 宽字符显示列。
  - 支持 Left/Right、Home/End、Delete、Ctrl+A/E/K/U/W、Ctrl+J。
  - 修复 Backspace/Delete 原始终端序列兼容问题。
- Stage 3 popovers/interrupts：
  - 建立 popover priority。
  - 忙碌状态下 `Esc` 改为两次确认中断。
  - `Ctrl+G` 作为直接中断路径。
  - `Ctrl+C` 两次确认退出。
  - 增加可见 interrupt feedback。
- Stage 4 transcript/streaming：
  - 长回答流式输出可读。
  - 鼠标滚轮可查看历史。
  - 右侧栏保持稳定。
  - `Ctrl+O` compact/detail/full 已在真实 TUI 通过验收。
- Stage 5 tool/permission UX：
  - 工具执行状态更清楚。
  - 写文件权限确认框在 live create/write/read 流程中可操作。
  - 用户验收：智能体自己创建文件、写入、读取，中途权限确认框可操作。
- Stage 6 command product surfaces：
  - `/help`、`/status`、`/model`、`/context`、`/usage`、`/cost`、`/permissions`、`/gateway`、`/keybindings` 可读可用。
  - 常用 UI 和斜杠命令尽量中文化。
  - Slash palette 中 `Esc` 退出提示显眼化。
- Stage 7 workflow closure：
  - `/sessions` title-first picker 可读。
  - `/resume latest` 恢复保留 transcript。
  - `/resume <prefix>` 可匹配会话。
  - busy prompt 进入 `/queue`。
  - `@` 文件 mention 支持 fuzzy/recent candidates。
  - `/guide` 可在长任务中生效。
  - `/guide 停止` 只取消，不创建 continuation prompt。
  - `/compact` 可调用并使用模型摘要优先、本地 fallback 兜底。
  - 快捷键验收覆盖 `Ctrl+O`、`Tab`、`Shift+Tab`、`Ctrl+T`、`Ctrl+N/P`、`Ctrl+F/B`、`Ctrl+R/E`、`PageUp/PageDown`、两次 `Esc`、`Ctrl+G`、两次 `Ctrl+C`。
- Stage 8 release posture：
  - 早期 MCP stdio runtime 已存在。
  - `/mcp` 可列出服务器、工具，并通过权限边界调用。
  - `/agents run readonly-researcher` 有只读子智能体路径。
  - 当时 richer skill/task/background 仍是 partial/non-blocking，后续在 v1.3 补齐。
- Stage 9 release hardening：
  - `npm run check` 通过。
  - `npm run verify:release` 通过。
  - release/audit/generated docs 刷新。
  - v1.2 结束时测试规模约 241 个。

#### 2026-04-30：交付版备份、旧项目归档和全局安装切换

- 用户确认 v1.2 基本可交付后，将验收通过版本复制到备份目录。
- 旧 `ant-code-latest` 源码目录按“重构前”归档到 `C:\saveproject\ant-code项目备份`。
- `lab-agent-release-evidence` 也按用户要求归档到备份文件夹。
- 全局安装切换到当前 `lab-agent` 重构版。
- 修正默认 `ant-code` 行为：
  - 用户发现 `ant-code` 仍进入旧行模式 prompt。
  - 调整后 `ant-code` 直接进入 TUI。
  - `ant-code chat` 保留为显式行模式。
- README 更新为当前 v1.2/v1.3 状态和全局命令行为。

#### 2026-04-30：OpenCode/旧项目产品对比后的架构升级计划

- 用户要求深度对比旧 Ant Code 和 OpenCode，在交互体验、后端逻辑、模型调用、工具链、子智能体、skill、MCP 上找后续升级点。
- 得出的升级方向：
  - 更稳定的 TUI shell 和滚动模型。
  - 固定侧栏。
  - 统一 command/keybinding registry。
  - 可观察、可恢复、可取消的子智能体任务系统。
  - agent 配置文件化。
  - MCP 持久连接和诊断能力。
  - 本地 skill 体系增强。
  - 后台任务和 worktree 隔离。
  - OpenTUI 是否迁移的技术评估。
- 用户审核通过后，形成 `docs/plans/completed/tui-agent-architecture-upgrade-plan-2026-04-30.md`。
- 用户要求除远端 skill marketplace 外，其余升级点均可推进。

#### v1.3 Stage 1：TUI 布局内核重构

- 拆分 `src/cli/tui.js` 的职责，把布局、事件路由、面板、输入、滚动等逻辑逐步下沉到 `src/cli/tui/` 模块。
- 建立新的 TUI shell：
  - 顶部状态栏。
  - 主聊天区域。
  - 固定右侧 status/todo/tasks/inspector/history/commands 面板。
  - 底部输入区。
  - slash/resume/help 等命令面板。
  - footer 提示区。
- 修复命令面板挤压输入框的问题。
- `/resume` 面板恢复较大可读空间，不再塞进窄小框内。
- 右侧栏从“跟随 transcript 拉长”改为固定在可视区域。
- 小窗口布局保留聊天优先。

#### v1.3 Stage 2：真实滚动区域与鼠标事件路由

- 新增/完善 `ScrollableRegion` 抽象。
- 滚动状态支持：
  - `scrollBy`。
  - `scrollToTop`。
  - `scrollToBottom`。
  - `isPinnedToBottom`。
  - `maxOffset`。
  - visible range。
  - scrolled-up reading state。
- 鼠标 wheel 解析支持 SGR、legacy X10 和 stdin chunk buffer。
- wheel 事件根据坐标路由到：
  - docked command panel。
  - side panel。
  - main transcript。
- 解决 resize 后滚轮失效、滚动条不可拖、输出文字不可选、输入删除失效等回归。
- 最终用户反馈：鼠标滚轮恢复正常，放大缩小时只有短暂卡顿，随后继续修复到正常。

#### v1.3 Stage 3：命令、帮助、快捷键单一注册表

- `src/commands/registry.js` 成为 slash command 和 keybinding 的主要元数据来源。
- `/help`、`/keybindings`、FooterBar、slash palette 尽量从同一 registry 派生。
- 常用内容中文化：
  - 命令标题。
  - 命令说明。
  - 分类。
  - 禁用原因。
  - footer 提示。
- 明确 `/help` 是展示可用命令，不是选择菜单。
- 强化 `Esc` 退出 slash command 的提示。
- 调整 `Ctrl+T`：
  - 从陌生的 inspector 过滤快捷键，转为右侧栏顶部可见小标签/过滤状态的一部分。
  - 让用户能通过 Tab/左右键理解侧栏切换。
- 修复 `/keybindings` 和真实行为不一致的问题。

#### v1.3 Stage 4：子智能体任务系统

- 新增 agent task store。
- 每个子任务记录：
  - task id。
  - parent session id。
  - child session id。
  - profile。
  - prompt。
  - status。
  - timestamps。
  - progress。
  - tool summary。
  - output summary。
  - cancel metadata。
- `agent_run` 创建可追踪子任务，而不是只返回一次性文本。
- TUI 右侧栏新增 Tasks 视图。
- `/agents tasks` 可查看任务。
- `/agents resume <task-id>` / `/agents cancel <task-id>` 相关文案和命令表面补齐。
- 修复用户发现的 `research` profile 找不到问题：
  - 保留 `readonly-researcher`。
  - 增加 `research` 兼容 alias。
  - `/agents` 能展示当前可用 profile。

#### v1.3 Stage 5：Agent 配置文件化

- 支持从本地 markdown/config 读取 agent profiles。
- 支持来源：
  - `.lab-agent/agents/*.md`。
  - `.ant-code/agents/*.md`。
  - `lab-agent.config.json` 中的 `agents.profiles`。
- frontmatter 支持：
  - name。
  - description。
  - mode。
  - model。
  - tools。
  - disallowedTools。
  - permissionMode。
  - maxRounds。
  - color。
  - hidden。
  - skills。
  - mcpServers。
  - background。
  - isolation。
- 内置 profile 扩展为：
  - build/default。
  - planner。
  - explorer。
  - verifier。
  - code-worker。
  - readonly-researcher/research。
  - hidden internal agents。
- 主智能体上下文中加入可调用子智能体的说明。

#### v1.3 Stage 6：Compact/Title/Summary 内部 agent 化

- 新增 `src/agents/internal.js`。
- `/compact` 不再只是本地算法压缩，优先通过 hidden `compaction` internal agent 调用模型摘要。
- context-window 保存策略信息：
  - `agent:compaction`。
  - fallback reason。
  - before tokens。
  - after tokens。
  - summary tokens。
- 网关不可用时保留本地 redacted fallback。
- session 持久化/恢复 `lastInternalAgent` 等内部 metadata。
- 用户确认 `/compact` 可调用，并希望补齐模型摘要机制；本阶段已完成。

#### v1.3 Stage 7：MCP 持久运行时

- `src/mcp/runtime.js` 从短生命周期 stdio 调用升级为 persistent runtime。
- 支持：
  - server status。
  - disabled server 状态。
  - tool cache。
  - reconnect。
  - disconnect。
  - stderr summary。
  - prompts/list。
  - resources/list。
  - resources/read。
  - tools/list。
  - tools/call。
- `/mcp` 命令支持：
  - status。
  - tools。
  - prompts。
  - resources。
  - read-resource。
  - reconnect。
  - disconnect。
- `mcp_list` model tool 支持 `tools/prompts/resources/resource`。
- 修复 runtime 泄漏：
  - session turn finally close。
  - `/mcp` command finally close。
  - subagent MCP runtime finally close。
- Windows `npx` 启动归一化为 `cmd /c npx ...`。
- root config 和 lab template 增加默认关闭的 MCP 推荐项：
  - filesystem。
  - memory。
  - playwright。

#### v1.3 Stage 8：Skill 体系增强

- `src/skills/registry.js` 支持更完整 frontmatter。
- 新增字段：
  - `argument-hint`。
  - `context`。
  - `agent`。
  - `paths`。
  - `hooks`。
- `context: fork` 返回 fork-ready，并通过 hidden skill subagent 执行。
- `src/tools/runtime.js` 在没有显式 config 时会加载 config，保证 skill fork 子任务能拿到配置。
- 新增本地 skills：
  - `config/skills/codebase-orientation/SKILL.md`。
  - `config/skills/test-failure-triage/SKILL.md`。
  - `config/skills/release-readiness-review/SKILL.md`。
- 保持安全约束：
  - 不接入远端 marketplace。
  - 不自动执行 skill 脚本。
  - 不自动下载第三方 skill。
  - 只把 skill 当成本地 bounded instruction 或 fork 子任务输入。

#### v1.3 Stage 9：后台任务和 worktree 隔离

- 新增 `src/agents/worktree.js`。
- 支持在 git 仓库内显式创建 worktree：
  - `.lab-agent/worktrees/<taskId>`。
- `runSubagent` 支持 `taskId` 和 `childSessionId`。
- `/background` 从 disabled 表面升级为可用命令。
- 命令支持：
  - `/background run <profile> <task>`。
  - `/background list`。
  - `/background show <task-id>`。
  - `/background cancel <task-id>`。
  - `/background worktree <task-id>`。
  - `/background cleanup-worktree <task-id>`。
- TUI 中 `/background run` 使用独立 AbortController，不设置主 session busy。
- `/background cancel` 可中断本进程内后台 controller 并更新任务状态。
- Busy 状态下 `/background` 被加入 immediate command 白名单。

#### v1.3 Stage 10：OpenTUI 技术底座评估

- 查询并记录 `@opentui/core` 和 `@opentui/react` 的版本、许可证和依赖。
- 发现 OpenTUI 引入：
  - native optional packages。
  - Windows x64/arm64 包。
  - `bun-ffi-structs`。
  - `yoga-layout`。
  - `react-reconciler`。
- 结合当前 Ink TUI 已通过滚动/overlay/resize 验收，决定不在 deadline build 中迁移。
- 新增 `docs/architecture/opentui-poc-2026-04-30.md` 记录结论。

#### v1.3 Stage 11：测试、验收和文档收尾

- 更新/新增测试覆盖：
  - context-window compaction。
  - session resume。
  - MCP fake server/runtime。
  - skill parser/fork。
  - command registry。
  - agent profiles。
  - agent task store。
  - TUI workflows。
  - TUI command panels。
  - TUI inspector。
  - scroll region。
  - mouse event parsing/routing。
  - input editor。
- 更新 docs：
  - README。
  - deployment docs。
  - provenance modules。
  - architecture OpenTUI decision。
  - v1.3 acceptance。
  - upgrade plan status。
- 完整验证：
  - `npm run check` 通过。
  - 260 tests pass / 0 fail。
  - `git diff --check` 通过。
  - MCP 默认启用数量为 0。
  - 配置 JSON 可解析。
  - 未发现残留 MCP/Playwright 测试进程。

### 完成的主要能力

1. CLI 与全局命令
   - 将公开命令统一为 `ant-code`，保留 `lab-agent` 兼容入口。
   - 修正默认 `ant-code` 命令行为，使其直接进入 TUI，而不是旧的行模式交互。
   - 完成当前重构版的全局安装切换。

2. TUI 主体验
   - 重构 TUI 布局，形成顶部状态、主聊天区、固定右侧栏、底部输入区、命令面板和 footer 提示。
   - 修复多轮窗口缩放、大小窗口滚动、鼠标滚轮、滚动条、重复界面残影、输入框挤压、Backspace/Delete 失效等问题。
   - Slash palette、`/help`、`/resume`、`/sessions` 等从挤压布局调整为更稳定的底部/主区域面板，不再破坏聊天框边界。
   - 大窗口下右侧栏固定显示，主聊天滚动和右侧栏滚动解耦。
   - 小窗口下保持聊天优先，滚轮可查看完整历史。
   - 生成中滚轮不再闪回顶部或底部，用户向上看历史时不会被强制拉回最新输出。
   - 增强 sky-blue 风格，改善上下文、工具状态、流式输出节奏和小窗口布局。

3. 中文化和命令可发现性
   - 将常用 UI、斜杠命令说明、FooterBar、`/help`、`/keybindings` 等内容尽量改为中文展示。
   - 明确 `/help` 当前是命令说明面板，不是可执行选择菜单。
   - 强化 slash palette 中 `Esc` 退出提示的可见度。
   - 对 `Ctrl+T`、`Ctrl+N/P`、`Ctrl+F/B` 等低频快捷键补充实际触发条件说明。

4. 会话、恢复和上下文
   - 修复 `/resume` 和 `--resume`，支持恢复之前保留的会话记录。
   - `/resume` 选择会话时优先展示标题，而不是只展示难以识别的 id。
   - 右侧栏上下文显示从“会话数”改为 `tokens / context window`。
   - 配置中为当前实验室模型设置 200k 上下文窗口。
   - `/compact` 改为优先调用隐藏 `compaction` internal agent 进行模型摘要，保留本地 fallback。
   - 达到上下文阈值后自动触发 compact，继续会话时把压缩摘要纳入上下文。

5. 中断、排队和 `/guide`
   - 将忙碌状态下中断改为两次 `Esc` 确认：第一次提示，第二次真正中断。
   - `/guide <message>` 调整为在当前模型调用结束边界后打断后续工具/下一轮模型请求，再优先运行引导提示。
   - `/guide 停止` 会取消当前后续任务，不再生成新的引导继续提示。
   - Busy 状态下普通输入进入队列，`/guide`、`/queue`、`/background` 等必要命令可立即处理。

6. 工具、权限和工作流
   - 保持本地工具权限边界：读、写、命令、网络/MCP 分级判断。
   - 写文件、编辑文件、命令执行继续走本地权限确认框。
   - 用户已 live 验收：智能体自己创建文件、写入、读取，中途权限确认框可操作。
   - 保留 todo、plan、validation、changed files、delivery status 等工作流状态。

7. 子智能体系统
   - 支持内置 profile：`build`、`explorer`、`readonly-researcher`/`research`、`planner`、`verifier`、`code-worker`。
   - 支持 hidden internal agents：`compaction`、`title`、`summary` 等内部能力。
   - 主智能体 system context 中说明可通过 `agent_run` 调配子智能体。
   - 子任务记录包含 parent session、child session、profile、status、progress、tool summary、output summary 等信息。
   - `/agents`、`/agents tasks`、`/agents run` 等命令可查看和使用本地子智能体。
   - 支持本地 agent markdown/config 配置扩展。

8. Skill 体系
   - 新增本地 skill registry，支持 `SKILL.md` 和 frontmatter。
   - 支持字段：`name`、`description`、`when_to_use`、`allowed-tools`、`argument-hint`、`model`、`context`、`agent`、`paths`、`hooks`。
   - `skill_read` / `/skills show` 提供 bounded instruction。
   - `skill_run` 默认 instruction-only，不执行 skill 目录里的脚本。
   - `context: fork` skill 通过隐藏子智能体运行，仍走普通工具和权限策略。
   - 内置三个本地技能：
     - `codebase-orientation`：接手陌生仓库和 handoff。
     - `test-failure-triage`：测试/构建失败定位。
     - `release-readiness-review`：交付前审查。

9. MCP 体系
   - MCP runtime 从临时调用升级为持久 stdio runtime。
   - 支持 server status、tools cache、prompts、resources、read-resource、reconnect、disconnect、stderr 摘要和 timeout。
   - 支持 Windows 下 `npx` 通过 `cmd /c npx ...` 正常启动。
   - 修复 MCP runtime 生命周期泄漏，session turn、slash command、subagent 调用结束后会关闭 runtime。
   - 推荐但默认关闭的 MCP：
     - `filesystem`
     - `memory`
     - `playwright`
   - 高敏模板保持 MCP 空列表，避免敏感项目误触 `npx` 拉包或启动外部进程。

10. 后台任务和 worktree
    - 新增 `/background run/list/show/cancel/worktree/cleanup-worktree`。
    - 后台任务使用独立 AbortController，不阻塞主聊天输入。
    - 支持显式 git worktree 隔离，路径位于 `.lab-agent/worktrees/<taskId>`。
    - 不默认启用远端执行。

11. OpenTUI 评估
    - 对 `@opentui/core` 和 `@opentui/react` 做了轻量 POC/依赖评估。
    - 结论：当前交付版不迁移 OpenTUI，继续使用 Ink + Stage 1/2 ScrollableRegion 架构。
    - 原因：当前 TUI 滚动/overlay 已通过验收；OpenTUI 会引入新的 native optional dependency、Windows 兼容和 release seal 审查风险。

12. 文档和交付记录
    - 更新 README、部署文档、provenance、acceptance、plan 状态文档。
    - 新增 `docs/architecture/opentui-poc-2026-04-30.md`。
    - 新增 `docs/deployment/v1.3-agent-extension-acceptance.md`。
    - 更新 `docs/plans/completed/tui-agent-architecture-upgrade-plan-2026-04-30.md`，标记 Stage 6-11 完成。
    - 新增本文件 `PROJECT_CHANGELOG.zh-CN.md`。
    - 新增 `LLM_ONBOARDING.md`，供后续大模型/智能体快速理解项目。

### 用户已验收内容

- 大窗口和小窗口长回答滚轮正常。
- 生成中滚动不再闪回。
- 右侧栏固定显示体验通过。
- `/resume` 和 `/sessions` 可进入之前会话。
- `/guide` 可正常引导对话。
- 两次 `Esc` 中断逻辑通过。
- Slash command 展示和 `Esc` 退出提示通过。
- 权限确认框可操作。
- 文件创建、写入、读取工作流通过。
- `/compact` 可调用，模型摘要机制已补齐。
- 常用斜杠命令已测试通过。
- UI 交互整体通过。

### 自动验证

最终检查命令：

```powershell
npm run check
```

结果：

- 语法检查通过。
- forbidden endpoint 扫描通过。
- provenance 检查通过。
- dependency policy 检查通过。
- Node test 全量通过：260 pass / 0 fail。
- `git diff --check` 通过。
- 配置 JSON 可解析。
- MCP 默认启用数量为 0。

### 当前限制和后续注意事项

- 由于当日模型额度到达上限，用户尚未发送真实模型内容测试子智能体完整调度链路；斜杠命令和 UI 已验收。
- MCP 推荐项默认关闭；启用前需要实验室确认是否允许本机 `npx` 拉包和运行对应 stdio server。
- 真实 lab gateway 的 live smoke 仍应在目标部署环境执行。
- 不要把真实网关 key 写入 `lab-agent.config.json`、模板文件、README 或任何仓库文件。
- 后续如果要迁移 OpenTUI，应另开分支做 Windows PowerShell 长时间 resize/wheel soak，再进行依赖审查。
- 后续每次大改动都应更新本日志和 `LLM_ONBOARDING.md` 的当前状态段。
