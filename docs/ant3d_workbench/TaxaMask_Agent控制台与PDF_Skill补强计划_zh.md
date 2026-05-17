# TaxaMask Agent 控制台与 PDF Skill 补强计划

## 1. 本轮校正目标

这次修改不是继续扩大 STL 的三维标注方向，而是把昨天的大改动收回到 TaxaMask 的真实研究场景里：

- `STL` 只作为高分辨率渲染出的 2D 视角图来源，进入既有 Labeling / Blink / Locator-SAM 流程。
- `TIF` 是本轮主要新增方向，用于共聚焦、CT 切片或体数据，标签体系独立于 2D/STL 的形态部位 polygon。
- `PDF` 作为证据和候选来源接入 Agent skill，不能把候选图、caption 或模型判断直接变成训练真值。
- 启动页继续嵌入 Ant-Code 打包版 WebUI，不修改 `lab-agent` 源码；TaxaMask 外层补一个项目控制台，让研究者先看到当前项目状态，再用 Agent 处理配置、排错、PDF 和训练计划。

## 2. STL 边界

程序应表达为：

```text
STL/mesh -> 外部工具或设备导出高分辨率 2D views -> TaxaMask Labeling Workbench -> Blink / Locator-SAM
```

不应表达为：

```text
STL mesh -> TaxaMask 内部三维体表涂色 / 3D mesh segmentation
```

实际改动：

- 保留 `stl_rendered_views` 项目和导入桥接。
- 启动页和 Agent 规则明确写成 `STL rendered 2D views only`。
- 不新增 3D viewer、mesh painter 或 mesh label 数据结构。

## 3. TIF 边界

TIF 继续作为独立体数据项目：

- specimen 是训练样本的基本单位。
- `manual_truth` 是唯一可训练真值。
- `working_edit` 是当前人工编辑层。
- `model_draft` 是模型预测草稿，必须复核后才可能进入真值。
- 共聚焦和 CT 数据都通过 TIF/AMIRA-style volume + material ID 的路线进入。

本轮不重写 TIF 主流程，只在启动页控制台显示 specimen 和 train-ready 摘要，让用户能看到 TIF 项目是否已经接近训练条件。

## 4. PDF Skill 补强

现状问题：

- `PdfProcessingWidget` 和 `tools/agentic/screen_pdfs.py`、`extract_figures.py` 已经存在。
- `ANTCODE.md` 和 `taxamask-workflows` 只把 PDF 当成一个路线提到，缺少像默认 workflow skill 一样的专门入口。

改动目标：

- 新增 `.lab-agent/skills/taxamask-pdf-evidence/SKILL.md`。
- 在 `ANTCODE.md`、`.lab-agent/memory.md`、`.lab-agent/skills/taxamask-workflows/SKILL.md` 中短链到这个 skill。
- skill 明确 PDF 的产物用途：screening run index、figure extraction DB、candidate/evidence index、2D project `needs_review` candidate。
- skill 明确禁止动作：PDF candidate 不自动成为 2D/STL 训练真值，不进入 TIF `manual_truth`。

## 5. 启动页控制台

TaxaMask 启动页保留 Ant-Code WebUI 主区域，但在 TaxaMask 外层增加一个轻量项目控制台。

显示信息：

- 当前工作流和当前项目。
- 2D/STL 图像数量和已有人工作图像数量。
- STL 数据边界提示：只处理渲染 2D views。
- TIF specimen 总数和 train-ready 数量。
- PDF evidence skill 状态和候选需复核提示。
- Ant-Code Dashboard 是否运行。

这样做的研究意义：

- 用户打开软件后不必先问 Agent 才知道当前项目处于什么状态。
- TIF 是否有可训练真值一眼可见。
- PDF 入口会被理解为证据/候选工作流，而不是训练真值入口。
- Ant-Code 仍然用打包版 exe，TaxaMask 只是做外层调度和状态呈现。

## 6. 验证计划

使用用户指定的 conda 环境：

```powershell
C:\Users\admin\anaconda3\envs\antsleap\python.exe
```

计划运行：

```powershell
C:\Users\admin\anaconda3\envs\antsleap\python.exe -m py_compile AntSleap\main.py AntSleap\ui\taxamask_agent_panel.py
C:\Users\admin\anaconda3\envs\antsleap\python.exe -m unittest tests.test_gui_smoke tests.test_ui_polish_scope tests.test_ui_localization
```

本轮不运行 GPU-heavy 训练或真实大体数据推理。
