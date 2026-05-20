# Ant Code Dashboard 报告型渲染增强计划

状态：已完成
创建日期：2026-05-14
适用仓库：`C:\saveproject\LBJ-workspace\lab-agent`
正式产品名：Ant Code
关联入口：`ant-code dashboard`

## 一句话目标

在不强化代码审阅负担、不影响 TUI 的前提下，为 Dashboard WebUI 增加更适合实验室报告、实验材料和结构化结果阅读的富渲染能力：数学公式、Mermaid 流程图、JSON/YAML/CSV 数据预览、图片集预览和长内容目录。

## 需求结论

本轮做：

- 数学公式：支持行内公式和块级公式。
- Mermaid 流程图：支持常见流程图、时序图、状态图等图形化表达。
- JSON/YAML/CSV 结构化预览：把数据结果变成可展开、可扫描的“数据预览”，而不是普通代码块。
- 图片集预览：多张图片自动组织成缩略图带和可翻页大图。
- 长内容目录：长报告、方案书、实验记录自动生成轻量目录，方便跳转。

本轮明确不做：

- 不把重点放在代码 diff 审阅上。
- 不增加红绿增删柱、复杂 hunk 展开、文件级代码审查面板。
- 不把聊天框内表格继续复杂化；当前 Markdown 表格效果第一阶段已足够。
- 不让用户消息默认富渲染成复杂版式，避免粘贴内容被误解释。

## 当前基线

当前 Dashboard 已具备这些渲染能力：

- `src/dashboard/public/markdown.js`
  - 标题、段落、无序/有序列表。
  - 任务列表。
  - 引用块。
  - pipe table。
  - fenced code block 和复制按钮。
  - Markdown 链接和图片。
  - 图片点击进入大图 lightbox。
  - 基础 diff/patch 高亮，但这不是下一阶段重点。
- `src/dashboard/public/app.js`
  - Assistant 回复按 Markdown 渲染。
  - 用户消息保持偏纯文本。
  - 右侧 `.md` 文件预览复用 Markdown 渲染。
  - 图片文件、PDF、文本文件已有第一版右侧预览。
  - 消息里的文件引用可以打开右侧预览。
- `src/dashboard/files.js`
  - `.json`、`.csv`、`.tsv`、`.yaml`、`.yml` 当前归入文本预览。
  - 图片文件当前支持 `.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`。
- `tests/unit/dashboard-markdown.test.js`
  - 已覆盖表格、代码块防误解析、HTML 转义、列表、链接、图片、任务列表、引用块、unsafe URL、diff 高亮。

因此本轮应扩展现有轻量 Markdown 管线和右侧预览，不应重写整个 WebUI。

## 设计原则

- 面向非代码用户：把输出解释成“报告、公式、流程、数据、图片”，少使用代码审阅术语。
- 默认清爽：富渲染结果应像报告组件，不要把每个 block 都做成厚重卡片。
- 可回退：任何公式、图表、数据解析失败，都必须保留原文入口。
- 本机优先：不得通过 CDN 加载 KaTeX、Mermaid 或其他远程脚本/字体。
- 安全优先：不允许 Markdown HTML 直通；Mermaid 和数据预览不得执行用户内容里的脚本。
- TUI 隔离：本计划只改 Dashboard WebUI 和相关 Dashboard 单测，不修改 `src/cli/tui.js` 或 `src/cli/tui/`。
- 用户输入克制：用户消息仍以纯文本为主；富渲染主要服务 assistant 回复和右侧文件/产物预览。
- 可访问：重要控件支持键盘聚焦；图片翻页、目录跳转、数据展开有明确按钮语义。

## 设计稿

### 1. 数学公式

适用位置：

- Assistant 回复。
- 右侧 Markdown 文件预览。
- 后续可扩展到实验报告类文件预览。

支持语法：

```text
行内：$E = mc^2$
块级：
$$
\int_0^1 x^2 dx = \frac{1}{3}
$$
```

界面表现：

- 行内公式跟随正文基线，不破坏段落节奏。
- 块级公式居中显示，外层使用轻量横向滚动容器，避免长公式撑破聊天宽度。
- 块级公式左上角可显示小标签“公式”。
- 渲染失败时显示原始公式文本，并给出“公式无法渲染”的轻提示，不阻塞整条回复。

安全和依赖：

- 首选本地 npm 依赖 `katex`。
- KaTeX CSS、字体和 JS 都必须来自本地包或打包产物，不使用 CDN。
- 渲染结果只允许 KaTeX 生成的安全 HTML，不允许用户 HTML 注入。

### 2. Mermaid 流程图

适用位置：

- Assistant 回复中的 fenced code block：```` ```mermaid ````。
- 右侧 Markdown 文件预览。

界面表现：

- 默认渲染为图表，顶部小标签显示“流程图”。
- 图表区域背景与 WebUI 深灰审美一致，边框轻，留白足。
- 图表过宽时容器横向滚动，不压缩到难以阅读。
- 提供“查看原文”切换按钮，用于审查 Mermaid 源文本。
- 渲染失败时回退为普通代码块，并显示短错误，不堆叠技术栈信息。

安全和依赖：

- 首选本地 npm 依赖 `mermaid`，按需加载，避免没有图表时增加启动负担。
- 禁用或严格限制 Mermaid 中的 HTML label、外链脚本、交互回调。
- 渲染容器要与普通 Markdown HTML 隔离，避免图表源文本造成 DOM 注入。
- 不通过外部 URL 加载图表库、主题或字体。

### 3. JSON/YAML/CSV 结构化预览

适用位置：

- Assistant 回复中的 `json`、`yaml`、`yml`、`csv`、`tsv` fenced code block。
- 右侧 `.json`、`.yaml`、`.yml`、`.csv`、`.tsv` 文件预览。

命名方式：

- UI 中不叫“代码预览”，统一叫“数据预览”。

JSON/YAML 表现：

- 顶部摘要：对象/数组类型、字段数、数组长度、是否截断。
- 默认展开前 2 层，深层节点折叠。
- 字符串、数字、布尔、null 使用低调但清晰的颜色区分。
- 长字符串默认截断，可展开。
- 保留“查看原文”切换。
- 解析失败时回退普通文本。

CSV/TSV 表现：

- 表头固定在预览区域顶部。
- 默认展示前若干行，底部提示总行数或“已截断”。
- 支持横向滚动。
- 空值、长值保持可读，不把表格撑爆。
- 提供“复制为 TSV”按钮，方便实验数据转贴到表格软件。

依赖选择：

- JSON 使用浏览器/Node 原生解析。
- CSV/TSV 第一版可以实现一个小型本地解析器，覆盖常见引号、逗号、换行转义；如果复杂度上升，再评估 `papaparse`。
- YAML 首选本地 npm 依赖 `yaml`；如不引入依赖，第一版只在右侧原文预览中保留 YAML 文本，不伪装成结构化树。

### 4. 图片集预览

适用位置：

- Assistant 回复中连续或同段出现 2 张以上图片。
- 右侧产物栏中文件列表含多张图片。
- 后续可扩展到某一输出目录的图片组。

界面表现：

- 消息内多图显示为轻量缩略图网格或横向缩略图带。
- 点击任一图片进入已有 lightbox。
- lightbox 增加上一张/下一张、图片计数、文件名/alt 文案。
- 支持键盘 `←` / `→` 翻页，`Esc` 关闭。
- 不自动播放，不做复杂相册动画。

数据来源：

- Markdown 图片语法。
- 右侧文件列表中的 image kind。
- `collectSessionFiles` 收集到的图片产物。

安全和边界：

- 继续沿用现有 safe URL 规则。
- 远程图片如果后续允许，仍要只通过浏览器普通 image 加载，不走额外脚本。
- 本地工作区图片通过现有 `/api/files/raw` 路径读取，继续受工作区边界限制。

### 5. 长内容目录

适用位置：

- Assistant 长回复。
- 右侧 Markdown 文件预览。

触发条件建议：

- 标题数量不少于 3 个；或
- 文本长度超过约 2500 字符；或
- Markdown block 数量超过约 12 个。

界面表现：

- Assistant 回复顶部显示一个薄目录条，默认折叠，只显示“目录 · N 节”。
- 展开后显示 H2/H3 为主的层级列表，点击滚动到对应位置。
- 右侧 Markdown 文件预览可使用 sticky 小目录，放在文档内容顶部或右上角，不遮挡正文。
- 不在短回复中显示目录，避免噪音。

实现细节：

- Markdown parser 输出 heading id。
- id 使用稳定 slug，并处理重复标题。
- 目录只从已渲染的安全 Markdown block 生成，不从 raw HTML 生成。

## 技术方案

### 模块拆分建议

建议新增或调整以下 Dashboard 专属模块：

- `src/dashboard/public/markdown.js`
  - 继续负责 Markdown block 解析和基础 HTML 输出。
  - 新增数学块、Mermaid 块、结构化代码块、heading id/TOC 元数据。
- `src/dashboard/public/rich-renderers.js`
  - 负责浏览器端富组件 hydration：公式、Mermaid、数据树、图片集、目录。
- `src/dashboard/public/structured-data.js`
  - 负责 JSON/YAML/CSV/TSV 解析、摘要、截断和安全 HTML 片段。
- `src/dashboard/public/gallery.js`
  - 负责图片组状态、lightbox 上一张/下一张、键盘交互。
- `src/dashboard/files.js`
  - 将 `.json`、`.yaml`、`.yml`、`.csv`、`.tsv` 预览 kind 从普通 `text` 细分为 `data` 或 `structuredText`。

实际实现时可以根据代码复杂度合并模块，但不要把所有逻辑继续塞进 `app.js`。

### 依赖和打包策略

当前 Dashboard 前端是浏览器原生 ESM 文件，不能直接在浏览器中裸 import npm 包名。新增依赖时需要先确定本地打包策略。

推荐策略：

1. 新增 `scripts/build-dashboard-assets.js`，用现有 `esbuild` 把浏览器端富渲染依赖打包成 Dashboard 静态资源。
2. 生成的 vendor 文件放在 `src/dashboard/public/vendor/`，并在审计文档中说明来源。
3. `package-lock.json` 和 `npm-shrinkwrap.json` 必须同步。
4. `npm run check:dependencies` 必须通过。
5. 不允许从 CDN、远程 URL 或运行时 npm install 加载渲染库。

依赖候选：

- 数学公式：`katex`。
- Mermaid 图：`mermaid`。
- YAML：`yaml`。
- CSV：优先自研小解析器；必要时再评估 `papaparse`。

如果引入 `mermaid` 导致包体或启动性能明显上升，应改为按需动态加载 vendor bundle，并在首次渲染图表时显示轻量加载状态。

## 执行清单

### Stage 0：方案冻结和依赖评估

- [x] 确认本计划只服务 Dashboard，不修改 TUI。
- [x] 确认第一批实现全部包含：数学公式、Mermaid、JSON/YAML/CSV、图片集、长内容目录。
- [x] 评估 `katex`、`mermaid`、`yaml`、CSV 解析策略。
- [x] 确认是否新增 Dashboard vendor bundle 构建脚本。
- [x] 记录新增依赖的安全边界和包体影响。

验收：

- [x] 计划文档更新到已确认状态。
- [x] 依赖方案有明确选择：引入、暂缓或自研。

执行记录：采用本地 npm 依赖 `katex`、`mermaid`、`yaml`；CSV/TSV 使用 Dashboard 本地轻量解析器。新增 `scripts/build-dashboard-assets.js`，用本地 `esbuild` 生成 Dashboard vendor bundle 和 KaTeX CSS/fonts，不使用 CDN。

### Stage 1：Markdown parser 和占位结构

- [x] 扩展 `parseMarkdownBlocks`，识别 `$...$`、`$$...$$`。
- [x] 识别 `mermaid` fenced code block。
- [x] 识别 `json`、`yaml`、`yml`、`csv`、`tsv` fenced code block。
- [x] 为 heading 生成稳定 id 和 TOC 元数据。
- [x] 输出安全占位 HTML，后续由 hydration 绑定。
- [x] 保持原有表格、链接、图片、任务列表、引用块、代码复制行为不回退。

验收：

- [x] `tests/unit/dashboard-markdown.test.js` 覆盖新 block 类型。
- [x] 旧 Markdown 单测全部通过。
- [x] unsafe HTML/unsafe URL 仍被拦截。

### Stage 2：数学公式渲染

- [x] 引入或接入本地 KaTeX 渲染资源。
- [x] 行内公式在段落中稳定渲染。
- [x] 块级公式支持横向滚动和失败回退。
- [x] 右侧 Markdown 预览与聊天消息一致。
- [x] 长公式不撑破移动端和窄窗口布局。

验收：

- [x] 单测覆盖正常公式、非法公式、HTML 注入文本。
- [x] 手工 smoke 覆盖行内/块级公式。
- [x] 无 CDN 请求。

### Stage 3：结构化数据预览

- [x] JSON code block 渲染为数据树。
- [x] `.json` 右侧文件预览渲染为数据树。
- [x] YAML code block 和 `.yaml` / `.yml` 文件按最终依赖方案渲染或回退。
- [x] CSV/TSV code block 渲染为数据表。
- [x] `.csv` / `.tsv` 右侧文件预览渲染为数据表。
- [x] 提供原文切换。
- [x] 大数据有行数/字段数/截断提示，避免卡住浏览器。

验收：

- [x] 单测覆盖 JSON object、JSON array、CSV quote、TSV、parse failure。
- [x] 右侧预览 API 不突破工作区边界。
- [x] 大文件仍受现有大小限制或新增更严格限制。

### Stage 4：Mermaid 流程图渲染

- [x] 接入本地 Mermaid vendor bundle。
- [x] 支持 `flowchart`、`sequenceDiagram`、`stateDiagram` 等常见图。
- [x] 图表失败回退为源码。
- [x] 图表主题适配 Dashboard 深灰视觉。
- [x] 禁止 Mermaid 中危险 HTML/脚本能力。
- [x] 图表过宽可横向滚动。

验收：

- [x] 单测覆盖 Mermaid block 占位和失败回退。
- [x] 手工 smoke 覆盖 Mermaid 图。
- [x] 无远程脚本请求。

### Stage 5：图片集预览和 lightbox 翻页

- [x] Markdown 多图自动形成图片组。
- [x] 右侧图片文件列表支持按当前列表翻页。
- [x] lightbox 增加上一张/下一张、计数、文件名/alt。
- [x] 支持键盘 `←` / `→` / `Esc`。
- [x] 单张图片保持现有简洁体验。

验收：

- [x] 单测或 DOM smoke 覆盖多图 data attributes。
- [x] 手工 smoke 覆盖聊天图片组和右侧文件图片组。
- [x] 图片 URL 安全规则保持不放宽。

### Stage 6：长内容目录

- [x] Assistant 长回复按触发条件显示折叠目录。
- [x] 右侧 Markdown 文档预览支持目录跳转。
- [x] 短回复不显示目录。
- [x] 重复标题 id 稳定去重。
- [x] 滚动定位不遮挡顶部状态条和 TodoList 进度条。

验收：

- [x] 单测覆盖 heading id、重复标题、TOC 触发条件。
- [x] 手工 smoke 覆盖长回复、长 Markdown 文件、短回复无目录。

### Stage 7：视觉收口、验证和文档更新

- [x] 深灰视觉统一：公式、流程图、数据树、数据表、图片集、目录都使用 Dashboard 当前石墨灰审美。
- [x] 移动/窄宽度检查：不横向撑破主布局，必要时局部滚动。
- [x] 更新 `LLM_ONBOARDING.md` 的 Dashboard 渲染状态。
- [x] 更新 `PROJECT_CHANGELOG.zh-CN.md`。
- [x] 如新增依赖，更新 dependency SBOM/license/audit 相关产物。

验收命令建议：

```powershell
node --test tests\unit\dashboard-markdown.test.js tests\unit\dashboard-files.test.js tests\unit\dashboard-ui.test.js
node --check src\dashboard\public\markdown.js
node --check src\dashboard\public\app.js
node scripts\check-syntax.js
npm run check:dependencies
git diff --check
```

如新增构建脚本或依赖：

```powershell
npm run check
npm run audit
```

最终验证记录：

- `npm run build:dashboard-assets` 通过。
- Dashboard Markdown、结构化数据、文件预览、UI、server、runtime、events、permissions 相关单测通过。
- `node scripts\check-syntax.js` 通过。
- `npm run check:dependencies` 通过。
- `npm run audit:sbom` 与 `npm run audit:licenses` 已更新审计产物。
- `npm run check` 通过，616 项测试全部通过。
- `npm run verify:readiness` 通过。
- `git diff --check` 通过，仅提示 changelog 工作区换行会按仓库规则归一化。
- `git diff -- src\cli\tui.js src\cli\tui` 为空。
- Edge 本地浏览器 smoke 覆盖目录、公式、Mermaid、数据树、数据表、图片集、原文切换；没有发现 Dashboard 富渲染阻塞问题。

## 风险和回滚

风险：

- Mermaid 包体较大，可能影响 Dashboard 首屏加载。
- 数学/图表渲染库生成 HTML/SVG，安全策略必须严格。
- YAML/CSV 边界复杂，错误解析可能误导用户。
- 长报告目录如果太显眼，会破坏简洁感。
- 图片集如果自动聚合过度，可能让单图报告显得拥挤。

回滚策略：

- 每类富渲染都必须有 feature-level fallback：公式回源码、Mermaid 回代码块、数据预览回文本、图片集回单图列表、目录可隐藏。
- 实现时尽量按 stage 小步提交；任一富渲染失败时，可以只关闭该类 renderer，不影响基础 Markdown。
- 不修改 TUI，因此 Dashboard 渲染问题不应影响 `ant-code` 默认入口。

## 完成定义

- Dashboard 能稳定渲染公式、Mermaid、JSON/YAML/CSV、图片集和长内容目录。
- Assistant 回复和右侧 Markdown/数据文件预览都能使用这些能力。
- 渲染失败有原文回退。
- 没有引入远程 CDN 或运行时联网依赖。
- TUI 无 diff。
- 相关单测、静态检查、依赖检查通过。
