# TaxaMask 架构总览

## 定位

TaxaMask 是面向分类学和形态学研究的本地开源工作台。它的核心目标不是让 AI 自动替代研究者，而是把文献证据、图像候选、人工标注、模型训练、预测复核和数据 provenance 组织成可追踪的研究流程。

当前主要路线包括：

- PDF Evidence：从分类学 PDF 中筛选候选文献、图版、caption 和部位描述。
- 2D/STL Morphology：基于高分辨率外部形态图像或 STL 渲染视图进行标注、Blink 辅助和模型迭代。
- TIF/CT Workbench：面向连续 TIF stack、CT 或显微体数据进行体数据查看、部位切分、volume label、训练预测和 Local Axis Reslice。
- Agent Center：内嵌本地 Agent，用于解释当前工作台状态、辅助排错、审查配置和在用户确认后修改本地代码。

这些路线共享一个设计原则：**AI 输出必须先进入可复核状态，不能自动成为研究真值。**

## 高层模块

```text
TaxaMask
├─ UI layer
│  ├─ PDF processing widgets
│  ├─ 2D/STL labeling workbench
│  ├─ TIF/CT workbench
│  └─ Agent Center panel
├─ Service / controller layer
│  ├─ selection and state controllers
│  ├─ label editing services
│  ├─ truth promotion services
│  ├─ backend workflow services
│  └─ preview / resource controllers
├─ Core / domain layer
│  ├─ project models
│  ├─ data safety policies
│  ├─ import/export logic
│  ├─ backend contracts
│  └─ task context/state
├─ Storage layer
│  ├─ SQLite project indexes
│  ├─ lightweight JSON manifests
│  ├─ sidecar volumes and labels
│  └─ run/model/export directories
└─ Embedded Agent runtime
   ├─ context routing
   ├─ workflow skills
   └─ local repair / review dashboard
```

## Project 类型

TaxaMask 不把所有研究数据塞进一个大项目格式。不同路线对应不同项目语义：

- 2D/STL 项目保存图片、标注、多视角视图、模型配置和候选框复核状态。
- TIF/CT 项目保存 specimen、volume sidecar、label layer、part、ROI、Local Axis reslice、训练预测 run 和模型库记录。
- PDF evidence 输出是候选证据和 provenance，不是训练真值项目。

这种拆分可以减少大 JSON 损坏风险，也避免把外部形态、内部结构和文献证据混成含义不清的单一状态。

## UI 与业务规则的边界

UI 层负责：

- 显示图像、切片、体预览和表格。
- 收集用户输入。
- 触发 service/controller。
- 展示错误、日志和运行状态。

业务规则应尽量进入 core/service 层：

- 哪些 label role 可以写入。
- AI prediction 如何进入 review draft。
- `manual_truth` 何时可以生成。
- 训练样本如何判定 train-ready。
- 后台任务如何匹配当前 specimen / part / reslice。

这样做的意义是：如果未来增加 WebUI、CLI、批处理或新的训练后端，不需要重新从 PySide Widget 中抽业务逻辑。

## 后台任务模型

TaxaMask 里很多操作都可能很慢：PDF 解析、图像导入、TIF materialize、volume preview、auto-save、训练、预测和 Local Axis export。架构上应把这些操作视为 task：

- task 有明确类型、上下文、运行状态和结果。
- UI 只根据 task state 刷新按钮和提示。
- 旧 task 回调必须确认上下文仍匹配当前选择，不能刷新错误 specimen 或 part。
- 资源不足时应尽量转成可理解提示，而不是让研究者误判为数据损坏。

## 开源文档策略

TaxaMask 公开架构文档保留的是设计边界、数据安全原则、主要工作流和验收摘要。原始施工日志、临时交接文档、本地路径和私有运行记录不应进入公开仓库。
