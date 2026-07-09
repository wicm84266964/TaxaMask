# TIF/CT 工作台架构

## 目标

TIF/CT 工作台用于处理连续 TIF stack、CT 或显微体数据。它面向内部形态研究，提供体数据查看、ROI/part 提取、volume label、训练预测、结果复核和 Local Axis Reslice。

它不是 2D polygon 标注工作台的简单扩展，而是一条独立体数据路线。

## 数据模型

TIF/CT 项目由轻量入口、SQLite 索引和 sidecar 数据共同组成：

```text
tif_project/
├─ project.tif_sqlite_manifest.json
├─ project.taxamask_tif.sqlite
├─ specimens/
│  └─ specimen_id/
│     ├─ source/
│     ├─ working/
│     ├─ labels/
│     ├─ parts/
│     └─ material_map.json
├─ runs/
├─ models/
└─ exports/
```

SQLite 保存项目索引、路径、状态和 provenance。大型 image/label volume 保存在 sidecar 文件中，不嵌入 SQLite 或 JSON。

## Label role

常见 label role：

- `working_edit`：人工编辑工作层。
- `manual_truth`：人工复核后的训练真值。
- `editable_ai_result`：可编辑 AI 预测结果。
- `raw_ai_prediction_backup`：原始预测备份，只读审计层。

这些 role 的写入规则不应散落在 UI 方法里，而应由 guard/policy 统一控制。

## Specimen、Part 与 Reslice

TIF project 以 specimen 为基本单位。

part 是从 specimen volume 中提取出来的局部结构，例如 head、brain 或其他内部结构。part volume 可以有自己的 image、mask、label 和训练状态。

reslice 是 part 下的派生输出。Local Axis Reslice 会基于局部坐标系导出新的切片方向。reslice 保存 metadata、source provenance 和输出 shape/spacing，不修改原始 stack。

## UI 层

`TifWorkbenchWidget` 是外部入口，但不应长期承担所有业务逻辑。公开架构目标是让它主要负责：

- 控件布局。
- 信号连接。
- 当前选择展示。
- 调用 controller/service。
- 显示反馈和日志。

已拆分或应优先保持拆分的方向：

- layout/page/control panel。
- training/prediction panel controller。
- preview/resource controller。
- Local Axis controller。
- Agent context builder。
- style、translations、dialogs、workers、canvas。

## Service / controller 层

TIF 工作台的复杂动作应尽量由 service/controller 组织：

- Selection：specimen、part、reslice、label role、display mode。
- Label edit：保存、dirty slices、auto-save、manual save。
- Truth promotion：接受 working edit 或 editable AI result 为 `manual_truth`。
- ROI/part：ROI keyframe、mask preview、part 创建。
- Backend workflow：prepare/train/predict 样本选择、合同请求、结果注册。
- Preview/resource：volume preview、mask preview、资源不足分类。
- Local Axis：draft、roll reference、local frame、reslice payload。

这些模块不一定完全脱离 PySide，但它们应尽量把业务规则和 UI 控件细节分开。

## Task / state 层

TIF 操作包含多个后台任务：

- TIF / AMIRA import。
- metadata-only materialize。
- label auto/manual save。
- truth promotion。
- ROI confirm。
- mask preview。
- volume preview。
- backend prepare/train/predict。
- Local Axis export。

统一 task manager 负责：

- task id 和 task type。
- 当前上下文。
- running / finished / failed / cancelled 状态。
- busy lock。
- 完成回调和当前选择匹配。

这样可以降低旧后台任务回调污染当前界面的风险。

## 3D preview 与资源策略

TIF/CT 体预览主要受显卡、OpenGL、体数据大小、系统内存和 Windows 提交内存影响。

设计原则：

- 切片查看和标签编辑应尽量在 3D preview 不可用时继续可用。
- GPU/内存/页面文件不足应显示可理解提示。
- preview 失败不应被解释为项目数据损坏。
- 后台训练正在运行时，3D preview 资源不足属于可预期风险。

## 训练与预测

TIF 训练/预测通过 backend contract 对接外部或内置后端。TaxaMask 负责：

- 选择 train-ready 样本。
- 导出训练数据。
- 启动后端命令。
- 接收 result JSON。
- 注册模型 manifest。
- 将 prediction 导入为可复核草稿。

后端不应直接修改 TaxaMask 主项目，也不应直接写 `manual_truth`。

## Agent 上下文

Ask Agent 应接收压缩后的 TIF 上下文，包括：

- 当前 specimen / part / reslice。
- 当前 label role 和 label schema。
- 当前训练/预测样本摘要。
- backend run 状态。
- preview/resource 状态。
- Local Axis draft/export 状态。
- task/state summary。
- 相关源码和契约引用。

这个上下文用于帮助 Agent 判断用户是卡在保存、预览、训练、预测、导入还是重切片，而不是猜测整个项目数据。
