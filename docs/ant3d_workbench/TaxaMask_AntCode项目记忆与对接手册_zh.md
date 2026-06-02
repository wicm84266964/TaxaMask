# TaxaMask 与 Ant-Code 项目记忆对接手册

## 1. 文档目的

这份文档给 TaxaMask 内嵌 Ant-Code 使用。它不是给最终用户看的教程，而是给 Agent 的“项目工作手册”：让 Agent 在处理常见 TaxaMask 配置、报错、训练准备、PDF 证据、TIF/STL 工作流时，不必每次都从零搜索代码、重新推断项目结构。

Ant-Code 启动后会把 `ANTCODE.md` 作为当前 TaxaMask 仓库的 active project rule。实测 loader 行为是：当 `ANTCODE.md` 存在时，它会优先采用 `ANTCODE.md`，并把同级 `AGENTS.md` 放入 skipped rules。因此，必须把 TaxaMask 内嵌 Agent 每次都要遵守的协作规则、文档节奏、Git 安全和数据安全规则镜像进 `ANTCODE.md`。

当前默认上下文入口是：

```text
ANTCODE.md
.lab-agent/memory.md
```

其中：

- `ANTCODE.md` 是 TaxaMask 内嵌 Agent 的最高优先级常驻项目规则，会进入初始 prompt，并已经包含从 `AGENTS.md` 镜像过来的关键协作、Git、文档和数据安全规则；
- `AGENTS.md` 仍是给普通 Codex/仓库协作看的通用规则，但内嵌 Ant-Code 启动时不应假设它会被同时采用；
- `.lab-agent/memory.md` 是短项目记忆，适合每次启动都放进上下文；
- `.lab-agent/skills/taxamask-workflows/SKILL.md` 是始终相关的可展开 workflow card；它不是普通“有需求才调用”的可选技能，而是 TaxaMask Agent 协议的短操作卡；
- 本文档是详细手册，适合复杂任务前按需阅读。

建议 Agent 的默认顺序是：

```text
用户提出 TaxaMask 任务
-> 常驻遵循 ANTCODE.md
-> 先读 .lab-agent/memory.md
-> 需要展开操作路线时读 .lab-agent/skills/taxamask-workflows/SKILL.md
-> 若是常规 UI/配置/训练/PDF/TIF/STL 任务，按本手册定位入口
-> 只在需要改代码或确认实现细节时再读对应模块
```

## 2. 当前嵌入方式

TaxaMask 不维护弱化版聊天助手。当前实现是把仓库内 vendored Ant-Code 源码作为 TaxaMask 的嵌入式 Agent 运行时：

```text
TaxaMask PySide 启动中心
-> TaxaMaskAgentPanel
-> node vendor/ant-code/src/cli/dashboard.js
-> 启动本机 Dashboard
-> 用 QWebEngineView 嵌入中间工作区
```

核心文件：

```text
AntSleap/ui/taxamask_agent_panel.py
AntSleap/main.py
```

默认命令形式：

```text
node vendor/ant-code/src/cli/dashboard.js --project <TaxaMask repo root> --port <free port> --no-open
```

默认依赖：

```text
vendor/ant-code/src/cli/dashboard.js
可用 Node.js
```

TaxaMask 启动后会后台访问：

```text
/api/status
/api/trust
/api/sessions
```

这些接口都返回合法 JSON 后才加载 WebView。这样可以避免首次进入时前端过早解析未准备好的响应。

## 3. 工作边界

### 3.1 默认工作区

内嵌 Ant-Code 的默认工作区是 TaxaMask 仓库：

```text
C:\saveproject\LBJ-workspace\Formica-Flow-Latest
```

Agent 应把普通任务限制在这个目录内，例如：

- 修改 TaxaMask 源码；
- 调整 TaxaMask UI；
- 增补 TaxaMask 文档；
- 运行 TaxaMask 测试；
- 检查 TaxaMask 项目 JSON、TIF 项目、导出清单；
- 处理 TaxaMask 生成的日志、报告、evidence index。

### 3.2 不要默认修改 lab-agent

外部 Ant-Code 源码副本通常在：

```text
C:\saveproject\LBJ-workspace\lab-agent
```

TaxaMask 正常集成工作属于当前仓库，尤其是 `vendor/ant-code` 和 `AntSleap/ui/taxamask_agent_panel.py`。除非用户明确说“修改外部 Ant-Code / lab-agent”，否则不要改 `C:\saveproject\LBJ-workspace\lab-agent` 源码。可以只读查看外部 Ant-Code 资料，用于理解嵌入边界。

### 3.3 权限与确认

TaxaMask 内嵌 Agent 默认信任当前 TaxaMask 工作区。对常规本地源码修改、配置检查、文档增补，不应反复让用户确认。

但以下行为仍需要明确用户意图：

- 删除、移动或覆盖用户数据；
- 改动 `manual_truth` 训练真值；
- 写入原始 AMIRA 文件；
- 运行 GPU-heavy 训练或长时间推理；
- 访问、修改 TaxaMask 仓库外的文件；
- 修改 `lab-agent` 源码；
- 提交 Git 或把代码推送到远端。

## 4. UI 总体结构

### 4.1 启动中心

启动中心现在是 TaxaMask Agent 主界面。

当前设计：

```text
左/中主区域：TaxaMask Agent Center
  - 内嵌 Ant-Code WebUI 中间工作区
  - 对话、运行状态、确认卡、输入框

右侧栏：
  - 2D/STL Morphology 工作流入口
  - TIF Volume 工作流入口
  - 最近项目 / 打开项目 / 通用设置
```

核心函数在：

```text
AntSleap/main.py::_build_start_center
```

### 4.2 工作台内入口

Labeling、Blink、TIF 工作台不放完整聊天框，只放轻量入口：

```text
Start Center
Ask Agent
```

这样标注画布、TIF slice viewer、材料表、日志栏不会被聊天窗口挤占。

点击 `Ask Agent` 时，工作台应带上下文回到启动中心，例如：

```text
source_workbench: labeling | blink | tif_volume
project_type: 2d_stl | tif_volume
project_path
active_specimen_id
active_image_path
active_label_role
selected_part
selected_material_id
recent_log_excerpt
```

实现入口：

```text
AntSleap/main.py::return_to_start_center_with_context
AntSleap/ui/tif_workbench.py::get_agent_context
AntSleap/ui/blink_lab.py::get_agent_context
AntSleap/ui/taxamask_agent_panel.py::set_context
```

Agent 收到上下文后，用户可以直接说：

```text
帮我看一下为什么这个 specimen 还不能训练。
```

而不用重新描述当前项目、图像、部位或 TIF specimen。

## 5. TaxaMask 项目类型

### 5.1 2D/STL 形态学项目

这是历史最成熟的工作流。它使用：

```text
Labeling Workbench
Parent-part annotation / Child-part annotation
Locator/SAM
Blink route-appointed experts
external_backend
Literature Traits
```

核心文件：

```text
AntSleap/core/project.py
AntSleap/main.py
AntSleap/ui/blink_lab.py
AntSleap/core/external_backend.py
AntSleap/core/literature_descriptions.py
AntSleap/core/training_preflight.py
```

研究含义：

- 适合外部形态、分类学图像、STL 渲染视角图；
- 标注对象通常是形态部位 mask / polygon；
- 子部位标注区和 Blink 路由专家用于小部位、局部细化、专家路线；
- 文献性状弹窗可把 PDF 抽取的 `taxon -> part -> description` 证据对齐到当前图片和当前部位描述框；
- 训练前要检查标注覆盖、locator scope、图像路径和部位树。

### 5.2 STL rendered views

STL 当前不是直接 3D mesh 涂色，而是已经从 STL/mesh 批量渲染出的 2D 视角图。

相关 schema：

```text
ant3d_stl_rendered_view_registry_v1
ant3d_stl_rendered_project_v1
project_type: stl_rendered_views
```

核心文件：

```text
AntSleap/core/stl_rendered_views.py
AntSleap/core/stl_project.py
AntSleap/core/stl_review_bridge.py
AntSleap/main.py::import_stl_rendered_views_action
```

重要边界：

- 打开 STL rendered-view project 时，程序把视角图注册进 Labeling Workbench；
- 不要把它理解成独立 3D 渲染工作台；
- STL 表面标注和 TIF 内部体标注要保持分离；
- STL 的标签通常面向外部形态，TIF 的 material ID 通常面向内部结构。

### 5.3 TIF volume 项目

TIF 是独立项目类型，不复用旧 2D polygon 标注逻辑。

相关 schema：

```text
ant3d_tif_project_v1
project_type: tif_volume
ant3d_tif_material_map_v1
ant3d_tif_stack_import_report_v1
ant3d_tif_training_export_v1
ant3d_tif_backend_contract_v1
```

核心文件：

```text
AntSleap/core/tif_project.py
AntSleap/core/tif_materials.py
AntSleap/core/tif_stack_import.py
AntSleap/core/tif_export.py
AntSleap/core/tif_backend.py
AntSleap/ui/tif_workbench.py
```

研究含义：

- TIF stack 是连续切片/体数据；
- 界面一张 slice 一张 slice 地展示和编辑；
- 标签是 AMIRA-style material ID label field；
- 一个 fully labeled specimen volume 才是有效训练样本；
- plain TIF 导入会创建 working volume 和空 `working_edit`，不会自动产生 `manual_truth`；
- AMIRA 导入应保留原始文件，只读解析 `.hx`、`.resampled`、`.labels`、material/statistics 等信息。

层含义：

```text
manual_truth: 人工确认，可用于训练
model_draft: 模型预测草稿，不是训练真值
working_edit: 当前人工编辑层
```

安全规则：

- 模型预测默认导入 `model_draft`；
- 不要自动覆盖 `manual_truth`；
- 从 `model_draft` 到 `manual_truth` 必须经过人工复核或用户明确命令；
- 不写回原始 AMIRA 文件；
- 大体数据放 sidecar，不嵌进项目 JSON。

## 6. 模型设置与后端

### 6.1 通用设置

通用设置只放跨工作流共享的内容，例如：

- 语言；
- 主题；
- 默认运行设备；
- 不直接属于 2D/STL 或 TIF 的全局偏好。

不要把 TIF 专属后端参数塞进通用设置。

### 6.2 2D/STL 模型设置

入口：

```text
Settings -> 2D/STL Model Settings
```

核心配置：

```text
external_backend
runtime_device
taxonomy
locator_scope
Locator/SAM training params
Blink route expert settings
```

`external_backend` 的用途：

- 外接脚本；
- 外接模型；
- 用 contract JSON 与外部训练/推理流程交互；
- 保留内置 Locator/SAM 作为默认路径或兼容路径。

核心文件：

```text
AntSleap/core/external_backend.py
docs/contracts/external_backend_contract_v1.md
```

### 6.3 TIF 模型设置

入口：

```text
Settings -> TIF Volume Model Settings
```

核心配置：

```text
tif_backend.backend_id
tif_backend.display_name
tif_backend.python_executable
tif_backend.prepare_dataset_command
tif_backend.train_command
tif_backend.predict_command
tif_backend.model_manifest
tif_backend.export_formats
```

TIF 后端不是 2D/STL external backend 的复制品。它面向体数据训练，应使用：

```text
ant3d_tif_backend_contract_v1
```

常见后端可以是：

- nnU-Net v2；
- MONAI；
- 自定义 Python 脚本；
- 其他能读取 contract JSON 的体分割流程。

Agent 在帮助用户配置 TIF 后端时，应尽量用研究语言解释：

```text
你现在是在设置“如何把已复核 TIF 体标注导出给体分割模型，以及模型预测回来后放到哪个候选层”。
```

而不是只说：

```text
填 command template。
```

## 7. PDF 证据与 Agent skill

PDF 工具不再是主视觉工作台，但能力保留。

核心文件：

```text
AntSleap/ui/pdf_processing_widget.py
AntSleap/core/pdf_evidence.py
AntSleap/core/governance/candidate_bridge.py
AntSleap/core/literature_descriptions.py
```

重要产物：

```text
PDF extraction records
candidate figure images
accepted_figures / needs_review_figures
pdf_text_blocks / taxon_part_descriptions
PDF evidence index
CSV / JSON / JSONL reports
provenance fields
```

设计方向：

- PDF 处理适合接入 Ant-Code skill；
- 用户可以用自然语言说“帮我处理这批 PDF，筛出目标类群图版”；
- Agent 负责调用已有 TaxaMask 能力、生成 evidence index、解释候选和风险；
- 产物默认应放在 `TaxaMask_outputs/` 或用户选择的结果文件夹；
- 产物必须保留来源 PDF、页码、图像编号、筛选理由、文献性状来源和可复核路径。

## 8. 常见 Agent 任务路线

### 8.1 解释启动或 UI 报错

优先检查：

```text
AntSleap/main.py
AntSleap/ui/taxamask_agent_panel.py
AntSleap/ui/tif_workbench.py
AntSleap/ui/blink_lab.py
recent log excerpt from Agent context
```

如果是 Ant-Code 嵌入报错：

```text
检查 vendor/ant-code/src/cli/dashboard.js 是否存在
检查 Node.js 是否可用
检查 /api/status
检查 /api/trust
检查 /api/sessions
检查 WebView 首次加载时序
```

不要一上来判断为“没有信任文件夹”。信任错误通常是权限/403；JSON parse 错误通常是接口响应、缓存、会话 metadata 或加载时序。

### 8.2 检查 TIF 是否可训练

优先检查：

```text
当前 TIF project path
specimen records
manual_truth 是否存在
material_map.json 是否存在
working volume 和 label volume shape 是否匹配
review_status 是否 train_ready
export manifest 是否生成
```

相关代码：

```text
AntSleap/core/tif_project.py
AntSleap/core/tif_export.py
AntSleap/ui/tif_workbench.py
```

输出解释要面向研究任务：

```text
这个 specimen 目前还不能训练，因为只有 working_edit，没有人工确认的 manual_truth。
```

### 8.3 配置 TIF nnU-Net / MONAI 后端

优先看：

```text
AntSleap/core/tif_backend.py
docs/ant3d_workbench/TIF后端契约_v1_实施设计_zh.md
```

要明确：

- Python 解释器路径；
- prepare/train/predict 命令模板；
- contract JSON 输入；
- 训练导出格式；
- model manifest 路径；
- prediction import 目标层。

不要把 TIF 后端和 2D/STL external backend 混用。

### 8.4 处理 STL rendered view 导入

优先看：

```text
AntSleap/core/stl_rendered_views.py
AntSleap/core/stl_project.py
AntSleap/main.py::import_stl_rendered_views_action
```

要记住：

- STL 处理的是渲染好的视角图；
- 导入后进入 Labeling Workbench；
- 子部位标注区 / Blink 路由专家可继续做小部位局部细化；
- 不要创建单独 STL 3D 渲染工作台，除非用户重新提出该需求。

### 8.5 处理 2D/STL 训练和子部位标注

优先看：

```text
AntSleap/core/training_preflight.py
AntSleap/core/blink_trainer.py
AntSleap/core/blink_dataset.py
AntSleap/ui/blink_lab.py
AntSleap/core/literature_descriptions.py
AntSleap/main.py
```

解释重点：

- Locator 阶段负责找到大区域；
- SAM/parts 或专家模型负责部位掩膜；
- 子部位标注区负责基于已有父框做局部 ROI 的细化、trajectory 积累和专家训练；
- route-appointed expert 是把某个专家模型指定给某条 `父部位 -> 子部位` 路线。

### 8.6 文档同步

默认不要每个小改动都同步根文档。

需要同步时：

- `README.md`：公共安装、定位、入口变化；
- `CHANGELOG_zh.md`：阶段总结或用户要求；
- `LLM_CONTEXT_DETAILED.md`：当前真实架构发生显著变化；
- `docs/ant3d_workbench/*.md`：架构设计和长期工作手册；
- `ANTCODE.md`：TaxaMask 内嵌 Agent 必须常驻遵循的最高优先级项目规则；
- `.lab-agent/memory.md`：Agent 每次都应该记住的短规则。
- `.lab-agent/skills/taxamask-workflows/SKILL.md`：始终相关的短工作流 skill/card，适合保存常用入口、边界和“什么时候读哪份长文档”。

### 8.7 记忆、手册和 skill 的分工

不要把完整用户手册直接塞进常驻 prompt。更稳妥的分工是：

- `ANTCODE.md`：最高优先级常驻协议，放 TaxaMask Agent 的身份、职责、工作流边界和安全底线。
- `.lab-agent/memory.md`：每次启动都应该知道的短项目记忆，例如工作区、入口、代码地图和当前状态。
- `.lab-agent/skills/taxamask-workflows/SKILL.md`：始终相关的可展开短流程卡，告诉 Agent 如何在 2D/STL、TIF、PDF、Agent Center 之间分流。
- `TaxaMask使用手册.md`：给研究者看的完整操作手册，是按钮、流程和研究含义的权威长文档。
- `LLM_CONTEXT_DETAILED.md`：给高级 Agent/开发者看的当前架构 handoff。

这样做的目的不是减少文档，而是减少每次对话需要塞进上下文的内容。普通问题先遵循 `ANTCODE.md` 和 memory，再展开 workflow skill；复杂改动再读手册、LLM_CONTEXT 或具体设计文档。

## 9. 验证与测试

常用 Python：

```text
C:\Users\admin\anaconda3\envs\antsleap\python.exe
```

常用检查：

```powershell
C:\Users\admin\anaconda3\envs\antsleap\python.exe -m py_compile AntSleap\main.py AntSleap\ui\taxamask_agent_panel.py
```

UI/工作流 smoke：

```powershell
C:\Users\admin\anaconda3\envs\antsleap\python.exe -m unittest tests.test_gui_smoke tests.test_tif_workbench tests.test_ui_polish_scope
```

TIF/后端相关变动应追加：

```powershell
C:\Users\admin\anaconda3\envs\antsleap\python.exe -m unittest tests.test_tif_project tests.test_tif_backend tests.test_tif_export
```

PDF 相关变动应追加 PDF widget/core 相关测试，按实际 touched files 选择。

GPU 训练或真实推理默认不要跑，除非用户明确说显卡空闲。

## 10. 输出和数据安全

不要把以下内容加入 Git：

- `user_config.json`；
- API key；
- `.lab-agent/sessions`；
- `.db`；
- model weights；
- `AntSleap/experiments`；
- generated artifacts；
- local project JSON；
- 原始大型 TIF/STL/PDF 数据；
- 临时验证文件。

验证临时文件使用：

```text
.tmp_validation/
```

结束前清理，除非用户要求保留。

## 11. 给 Agent 的行为建议

在 TaxaMask 内嵌环境中，Agent 应像一个研究工作台助手，而不是只像代码补全工具。

回答顺序建议：

```text
先用中文说清楚研究流程含义
再说明程序会改哪里
再执行必要检查或代码修改
最后汇报验证结果和剩余风险
```

对用户常见表达的理解：

- “TIF 能不能训练”：检查 specimen、manual_truth、material map、shape、review status、export manifest。
- “模型设置太难”：优先考虑把脚本/后端细节封装成 Agent 可执行流程，而不是让分类学家手填命令。
- “STL 入口”：通常指 STL rendered views 导入 Labeling Workbench，不是直接 3D mesh painting。
- “子部位标注 / Blink 路由专家”：通常指局部 ROI、专家路线、细部结构修正。
- “PDF 路径接入 skill”：优先把 PDF 批处理做成 Agent 可调用的 headless workflow，并保留 evidence/provenance。
- “不要做歪”：先复述 STL/TIF/PDF/Agent 边界，再动代码。

关键底线：

```text
manual_truth 不可被模型预测静默覆盖。
TIF/STL 标签体系不可混在一起。
TaxaMask 集成不应默认修改外部 lab-agent 源码。
用户原始研究数据不可被自动覆盖或删除。
```
