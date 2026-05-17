# TaxaMask Agent 启动中心与 PDF Skill 设计

## 1. 设计目标

TaxaMask 的主工作台已经承担了标注、切片浏览、材料表、模型配置和日志展示，继续在标注界面内塞入聊天窗口会破坏操作空间。更合适的位置是启动中心：启动中心本来就是进入 2D/STL、TIF、项目打开和设置的调度页，天然适合作为智能体主界面。

本设计目标是在 TaxaMask 启动中心主区域嵌入 Ant-Code 分发版 WebUI，让分类学家和形态学研究者可以用自然语言完成配置、排错、PDF 文献处理和训练准备，而不需要理解 Python 命令、contract JSON、外部模型后端和代码智能体操作。2D/STL 与 TIF 两个工作流入口放到右侧快捷栏上下排列，作为直接进入工作台的轻量入口。

核心原则：

- 启动中心主区域给 `TaxaMask Agent` / Ant-Code WebUI，保证对话、任务线程和结果展示有足够空间。
- `2D/STL morphology annotation` 和 `TIF volume annotation` 移到右侧快捷栏，上下排列，仍然醒目但不挤占 Agent 主界面。
- Agent 不是普通客服聊天气泡，而是由 Ant-Code WebUI 承载的“任务线程 + 状态 + 确认卡 + 产物预览 + 技能入口”。
- TaxaMask 不修改 Ant-Code 源码；只调用 Ant-Code 分发版 `ant-code.exe` 启动本机 Dashboard，并在 TaxaMask 的 WebView 内做轻量展示适配。
- TaxaMask 内嵌视图只显示 Ant-Code 的中间工作区：对话、运行状态、确认卡和输入框。Ant-Code 原生左侧任务线程栏和右侧产物预览栏在 TaxaMask 中隐藏，避免和 TaxaMask 自己的启动页入口挤在一起。
- PDF Processing 下沉为 Agent skill，保留批处理能力和 evidence/provenance 输出，不再作为主视觉工作台。

## 2. 为什么参考 Ant-Code WebUI

Ant-Code WebUI 已经验证了一套适合非命令行用户的交互模式：

- 左侧任务线程：用户不用记住命令历史，可以回到之前的任务。
- 中间对话区：过程折叠，结果清楚呈现。
- 权限/确认面板：重要动作执行前必须让用户确认。
- 运行状态：用户能看到“空闲、运行、等待确认、失败、完成”。
- 产物预览：生成的文件、图片、PDF、Markdown 可以直接查看。
- 权限模式：默认计划确认，不让模型随意写文件或执行命令。

TaxaMask 不重新实现一套弱化版 Agent，而是把 Ant-Code 分发版 Dashboard 放进启动中心主区域。右侧栏只负责承载 2D/STL 与 TIF 的直接入口；权限确认可以在 TaxaMask 包装层中简化为默认信任当前工作区。

## 3. 启动中心布局

建议启动中心采用左右结构：

```text
TaxaMask Start Center
┌──────────────────────────────────────────────┬──────────────────────┐
│ TaxaMask Agent Center                         │ 2D/STL 工作流入口     │
│ Ant-Code Dashboard                            │ 进入 / 新建 / 设置    │
│ 任务线程 / 对话 / 状态 / 产物反馈              ├──────────────────────┤
│ 输入框：描述你想做什么                         │ TIF 工作流入口        │
│                                              │ 进入 / 新建 / 设置    │
│                                              ├──────────────────────┤
│                                              │ 继续上次项目          │
│                                              │ 打开项目 / 通用设置   │
└──────────────────────────────────────────────┴──────────────────────┘
```

右侧工作流栏建议宽度：

- 默认 340-390 px；
- 只放高频入口和最近项目操作；
- 启动中心窗口宽度不足时，右侧工作流栏可以移动到底部或改成折叠入口；
- 不进入 Labeling / Blink / TIF 工作台主界面，避免占用标注空间。

## 4. 工作台内的快捷入口

启动中心是 Agent 的主界面，但用户在 Labeling Workbench、Blink Workbench 或 TIF Volume Workbench 操作时，仍可能临时想问模型问题，例如：

- 当前 specimen 是否可以训练？
- 最近的报错是什么意思？
- 这个 TIF 后端要怎么配置？
- 为什么导入的预测不能直接变成 manual_truth？
- 现在应该回到哪个流程继续？

因此每个工作台需要一个轻量入口，但不应该放完整聊天框。

### 4.1 推荐交互

工作台顶部工具栏右侧增加两个轻量动作：

```text
[启动中心] [询问 Agent]
```

或使用一个小型 `Agent` 图标按钮：

```text
[Agent]
```

点击 `启动中心`：

- 直接回到启动中心；
- 保持当前项目仍然打开；
- 启动中心主区域 Agent 显示“来自某工作台”的上下文。

点击 `询问 Agent`：

- 不在工作台内展开完整聊天；
- 打开一个小型快捷菜单或小浮层；
- 提供 3-5 个上下文动作；
- 复杂对话一律跳回启动中心 Agent 主界面。

TIF 工作台示例：

```text
TaxaMask Agent

- 检查当前 specimen 是否可训练
- 解释最近错误
- 配置 TIF 后端
- 回到 Agent 中心继续对话
```

2D/STL 工作台示例：

```text
TaxaMask Agent

- 检查当前项目训练覆盖
- 解释最近训练/推理日志
- 配置 2D/STL 外部后端
- 回到 Agent 中心继续对话
```

### 4.2 上下文传递

从工作台跳回启动中心时，Agent 应收到当前操作上下文，而不是让用户重新描述现场。

建议上下文字段：

```text
source_workbench: tif_volume | labeling | blink | pdf_evidence
project_path
project_type
active_specimen_id
active_image_path
active_label_role
selected_material_id
selected_part
recent_log_excerpt
last_error
```

Agent 主界面显示：

```text
来自：TIF Volume Workbench
项目：brain_volume_project
Specimen：ANT_001
当前层：manual_truth
最近日志：...
```

这样用户可以在标注中途点击 `询问 Agent`，回到启动中心后直接说：

```text
帮我看一下这个为什么不能训练。
```

而不需要重新说明项目、specimen 和标注层。

### 4.3 为什么不在工作台放完整聊天

不建议在标注工作区内放完整聊天窗口，原因：

- 标注、切片浏览、材料表、右侧检查器已经占满空间；
- 聊天窗口会挤压画布或 TIF slice viewer；
- 用户在工作台内最需要的是快速判断和下一步动作，不是长对话；
- 长任务、配置、PDF skill 和报错排查更适合回到启动中心集中处理；
- 启动中心有足够空间展示任务卡、确认卡和产物预览。

因此最终边界是：

```text
工作台 = 专注操作区
启动中心 = Agent 调度中心
工作台 Agent 按钮 = 快捷入口，不承载完整聊天
```

## 5. 侧栏组成

### 5.1 顶部状态区

显示用户真正关心的信息，而不是开发者运行时细节。

建议字段：

- `模型连接`：已连接 / 未配置 / 连接失败；
- `当前工作流`：未选择 / 2D-STL / TIF / PDF 文献；
- `当前项目`：无项目 / 项目名 / 最近项目；
- `状态`：空闲 / 正在分析 / 等待确认 / 正在执行 / 完成 / 失败。

示例：

```text
TaxaMask Agent
模型：Mimo v2.5 Pro 已连接
当前：TIF volume project
状态：等待确认
```

### 5.2 快捷任务入口

用研究任务表达，不用代码任务表达。

建议默认按钮：

- `配置 TIF 训练后端`
- `检查 TIF 是否可训练`
- `处理 PDF 文献`
- `分析最近报错`
- `生成下一步计划`

### 5.3 对话与任务卡

对话只负责表达意图，真正执行靠任务卡。

用户说：

```text
我有一批 AMIRA 文件，想训练一个脑区分割模型。
```

Agent 生成：

```text
建议工作流：TIF 体数据

我将准备：
1. 新建或打开 TIF 项目
2. 导入 AMIRA 目录
3. 检查 working volume 与 label volume 是否对齐
4. 检查 manual_truth 是否可用于训练
5. 建议配置 nnU-Net 或 MONAI 后端

[创建 TIF 项目] [选择 AMIRA 目录] [只生成计划]
```

### 5.4 确认卡

所有会改变配置、项目、文件或启动长任务的动作都必须以确认卡呈现。

示例：

```text
配置 TIF nnU-Net 后端

将执行：
- 导出格式设为 nifti
- Python 环境设为 antsleap
- 训练来源限制为 manual_truth
- 预测结果导入为 model_draft
- 不覆盖人工真值

[应用配置] [只生成命令] [取消]
```

### 5.5 产物预览

Ant-Code WebUI 有独立产物栏；TaxaMask 侧栏空间更小，可以做成折叠区。

展示对象：

- PDF 筛选结果 JSON / CSV；
- 提取出的 figure images；
- PDF evidence index；
- TIF training export manifest；
- TIF backend contract；
- 训练日志；
- 错误摘要；
- 建议修复步骤。

文件可以提供 `打开文件夹`、`打开证据工具`、`复制路径`、`导入项目` 等操作。

## 6. 权限和安全边界

默认权限模式应是 `计划确认`，而不是自动执行。

建议模式：

- `计划确认`：默认。所有写入、配置改动、训练启动都要确认。
- `项目内自动`：只允许 TaxaMask 项目内安全动作自动执行，例如读取状态、生成计划、检查路径。
- `维护模式`：面向开发者或高级用户，允许更宽的命令执行，但不作为分类学家默认入口。

必须确认的动作：

- 修改 TIF/2D-STL 后端配置；
- 导出训练数据；
- 启动训练或推理；
- 导入模型预测；
- 将 `model_draft` 提升为 `manual_truth`；
- 删除、覆盖、移动项目文件；
- 批量处理 PDF 并写入数据库/输出目录。

禁止自动动作：

- PDF candidate 自动写入 TIF `manual_truth`；
- 模型预测自动覆盖人工真值；
- 未确认即执行外部训练命令；
- 未确认即修改用户 API key 或长期配置。

## 7. Agent 与 TaxaMask 的工具边界

Agent 不应直接随意写项目 JSON，而应通过 TaxaMask 提供的领域工具调用。

第一批工具建议：

### 7.1 通用工具

- `get_taxamask_status`
  - 返回当前项目、工作流、最近项目、模型连接状态、可用 skill。
- `open_workflow`
  - 打开 2D/STL、TIF、PDF evidence 工具。
- `read_recent_logs`
  - 读取最近 TaxaMask 日志和指定 run 日志。
- `explain_error`
  - 将错误栈、stderr、run index 转成研究者能看懂的解释。

### 7.2 TIF 工具

- `check_tif_project_readiness`
  - 检查 specimen、working volume、manual_truth、material map、shape 对齐。
- `configure_tif_backend`
  - 写入 TIF 后端配置，但需要确认卡。
- `export_tif_training_dataset`
  - 导出训练数据，需要确认卡。
- `run_tif_backend_action`
  - 执行 prepare/train/predict，需要确认卡。
- `import_tif_prediction_draft`
  - 只允许导入为 `model_draft`。

### 7.3 2D/STL 工具

- `configure_2d_stl_backend`
  - 配置 2D/STL 外部脚本后端。
- `check_2d_training_readiness`
  - 检查标注覆盖、locator scope、缺失图片。
- `import_stl_rendered_views`
  - 导入 rendered views 到 Labeling Workbench。

### 7.4 PDF Skill 工具

PDF Processing 应作为 Agent skill 暴露，而不是继续让用户手动调大量参数。

建议 skill 名：

```text
taxamask_pdf_literature_skill
```

能力：

- `screen_pdfs`
  - 调用现有 PDF screening profile 和 `tools/agentic/screen_pdfs.py`。
- `extract_figures`
  - 调用 figure extraction/review profile 和 `tools/agentic/extract_figures.py`。
- `build_pdf_evidence_index`
  - 将 source PDF、page、caption、candidate path、specimen ID、metadata_ref 写入 evidence index。
- `import_pdf_candidates_to_project`
  - 导入到 2D Labeling Workbench，默认状态为 `needs_review`。
- `summarize_pdf_run`
  - 根据 run index、SQLite DB、输出目录生成可读报告。
- `explain_pdf_failure`
  - 解释 API、Poppler、PyMuPDF、OCR、空 PDF、模型 fallback 等常见问题。

PDF skill 的自然语言示例：

```text
帮我筛选这个文件夹里的新种描述论文。
```

Agent 生成：

```text
PDF 文献筛选任务

将使用：
- 筛选 profile：蚂蚁新种筛选 V2
- 输出目录：artifacts/pdf_runs/...
- API：当前 TaxaMask 文献处理设置
- 运行模式：V2，每次运行独立文件夹

结果不会自动进入训练集。
筛出的图像会作为 candidate/evidence，需要人工复核。

[开始筛选] [更换 profile] [取消]
```

再比如：

```text
把这批 PDF 图版抽出来，保留 caption 和页码。
```

Agent 生成：

```text
PDF 图文提取任务

将生成：
- SQLite 文献数据库
- figure images
- caption / nearby text
- multimodal review 结果
- PDF evidence index

这些结果只作为文献证据和候选来源，不会写入 TIF manual_truth。

[开始提取] [只生成计划] [取消]
```

## 8. 与现有 PDF Processing 的关系

短期不删除 `PdfProcessingWidget`，但主路径应逐步从“大面板手动操作”迁移到 Agent skill。

建议阶段：

1. 保留 `File -> Open PDF Evidence Tools`，用于查看证据和调试旧流程；
2. 启动中心 Agent 先接入 `tools/agentic` 命令；
3. 将 PDF profile、API settings、run index 读取包装成 skill；
4. Agent 运行 PDF skill 后，把产物显示为 evidence/report 卡；
5. 后续再决定是否将完整 PDF GUI 降级为高级工具。

这样用户不需要懂代码，也不需要打开另一个代码智能体去操控 TaxaMask 项目。

## 9. 实现方案

### 9.1 UI 层

新增 Qt 组件：

```text
AntSleap/ui/taxamask_agent_panel.py
```

建议主要类：

```text
TaxaMaskAgentPanel(QWidget)
AgentStatusCard(QWidget)
AgentTaskCard(QWidget)
AgentApprovalCard(QWidget)
AgentArtifactList(QWidget)
AgentComposer(QWidget)
```

启动中心主区域挂载：

```text
MainWindow._build_start_center()
  -> left: existing workflow cards
  -> right: TaxaMaskAgentPanel
```

### 9.2 Runtime 层

新增：

```text
AntSleap/ui/taxamask_agent_panel.py
```

职责：

- 查找 Ant-Code 分发版可执行文件；
- 启动 `ant-code.exe dashboard --project <TaxaMask workspace> --port <local port> --no-open`；
- 用 `QWebEngineView` 在启动中心主区域嵌入 Dashboard；
- Dashboard 服务就绪后调用 `/api/trust`，让当前 TaxaMask 工作区默认进入可信状态；
- 从标注工作台或 TIF 工作台跳回启动中心时，把当前 specimen、图片、标签层和最近日志写入对话输入框，方便用户继续询问。

### 9.3 与 Ant-Code 的复用方式

当前采用直接嵌入 Ant-Code 分发版 Dashboard 的方式，而不是把 `lab-agent` 源码作为 TaxaMask 依赖来改。

边界：

- TaxaMask 优先通过环境变量 `TAXAMASK_ANT_CODE_EXE` 定位分发版可执行文件；
- 未设置环境变量时，默认查找相邻 `lab-agent/dist/ant-code-windows-x64/ant-code.exe`；
- 仍未找到时，回退到系统 PATH 中的 `ant-code.exe` / `ant-code.cmd` / `ant-code`；
- TaxaMask 只负责启动、嵌入、默认信任当前工作区和传递当前研究上下文；
- Ant-Code 的模型网关、会话、任务执行、工具和长任务能力由分发版自身提供；
- 不在 TaxaMask 中重写一个功能较弱的规则助手。

这条路线的好处是：分类学家看到的是 TaxaMask 启动中心里的完整 Agent 主界面；底层仍是完整 Ant-Code 智能体能力，后续升级 Ant-Code 只需要替换分发包或指定新的 exe。

## 10. 第一阶段 MVP

第一阶段目标是把 Ant-Code 分发版 Dashboard 在 TaxaMask 启动中心内稳定跑通。

范围：

- 启动中心主区域 Ant-Code Agent；
- 启动中心右侧 2D/STL 与 TIF 工作流快捷栏；
- 工作台顶部轻量 `启动中心 / 询问 Agent` 入口；
- 从工作台跳转到 Agent 时携带当前项目、specimen、标注层、最近日志等上下文；
- 调用 Ant-Code 分发版 exe 启动 Dashboard；
- 在 TaxaMask WebView 中嵌入 Ant-Code WebUI，并让它占据启动页主界面；
- TaxaMask 嵌入模式隐藏 Ant-Code 原生左侧栏和右侧栏，只保留中间对话/任务执行区域；
- 当前 TaxaMask 工作区默认通过 Ant-Code 工作区信任；
- 隐藏不适合内嵌侧栏的关闭/权限模式控件；
- 保留 Ant-Code 的真实模型、工具、会话和长任务能力。

第一阶段可直接交给 Ant-Code 的自然语言：

```text
帮我配置 nnU-Net
帮我检查 TIF 是否可以训练
帮我处理 PDF 文献
分析最近报错
打开 TIF 工作流
打开 2D/STL 工作流
```

## 11. 第二阶段

接入真实模型网关：

- 读取 TaxaMask/Ant-Code gateway 配置；
- 支持 OpenAI-compatible chat completions；
- 将 TaxaMask 状态和可用工具注入模型；
- 支持工具调用，但工具执行先生成确认卡；
- 保存轻量会话记录；
- 支持长任务日志追踪。

## 12. 第三阶段

完整 skill 化：

- PDF 文献 skill；
- TIF 训练后端 skill；
- STL rendered-view 导入 skill；
- 报错诊断 skill；
- 文档/需求检索 skill；
- 多轮长任务执行和阶段复核。

## 13. 用户体验边界

好的体验应该是：

```text
用户表达研究目标
-> Agent 生成可理解计划
-> 用户确认
-> TaxaMask 执行安全领域动作
-> Agent 总结产物、风险和下一步
```

不是：

```text
用户被迫填写 Python 命令
用户被迫理解 contract JSON
用户被迫打开代码智能体操作项目
模型直接黑箱修改训练真值
```

## 14. 关键验收标准

- 启动中心仍然清晰，不因 Agent 主界面和工作流入口互相挤压而变乱；
- 新用户能用一句话进入 TIF / PDF / STL 任务；
- Agent 所有写入和长任务都有确认卡；
- PDF skill 能复用现有 profile、API settings、headless tools；
- PDF 结果默认是 evidence/candidate，不自动成为训练真值；
- TIF 训练设置不再要求用户手填全部命令；
- 训练/推理错误能被转成普通研究者能理解的解释；
- 工作台界面不被聊天框占用；
- 工作台内有清楚的 `启动中心 / 询问 Agent` 快捷入口；
- 从工作台进入 Agent 后，用户不需要重新描述当前项目和 specimen；
- 对专家用户来说像“研究助手”，而不是“代码 IDE”。
