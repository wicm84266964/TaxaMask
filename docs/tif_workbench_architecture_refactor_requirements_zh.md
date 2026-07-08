# TIF 工作台长期架构整理需求文档

日期：2026-07-08

分支：`codex/tif-workbench-architecture-refactor`

执行清单：`docs/tif_workbench_architecture_refactor_execution_checklist_zh.md`

## 背景

当前 TIF 工作台已经能支撑 TaxaMask 的核心三维标注、部位 ROI、mask 编辑、训练、预测、结果核验和 3D 预览流程，但 `AntSleap/ui/tif_workbench.py` 已增长到约 1.8 万行。这个文件同时承担 UI 构建、状态管理、后台任务、数据写入、训练预测入口、3D 预览和研究数据安全规则，后续继续叠加功能会提高维护成本。

本分支的目标不是简单把大文件拆小，而是把 TIF 工作台整理成长期可维护、可测试、可扩展的专业软件架构。

## 总目标

将 TIF 工作台从“巨型 GUI 工作台文件”整理为分层架构：

- UI 层只负责显示、用户输入、按钮状态和结果呈现。
- Service / Controller 层负责组织完整研究动作。
- Core / Domain 层负责稳定业务规则和研究数据安全边界。
- Task 层统一管理后台任务生命周期。
- IO / Project 层统一处理项目文件、volume sidecar、JSON/SQLite 和输出目录。

最终效果是：以后增加新功能时，不需要继续把逻辑塞进一个巨型 Widget；即使出现问题，也能快速判断属于 UI、状态、后台任务、项目读写、训练预测，还是研究数据安全规则。

## 研究流程优先级

本次架构整理必须优先保护以下真实研究流程：

1. TIF / Amira 导入。
2. Specimen 与 part 选择。
3. ROI 草稿、ROI 确认和部位体数据创建。
4. mask 关键切片、预览、接受和编辑。
5. working edit / editable AI result 保存。
6. training truth 接受，即 `manual_truth` 生成。
7. 训练数据准备、训练、预测和预测结果导入。
8. 预测结果复核、批量接受和结果对比。
9. 3D volume preview、ROI preview、mask preview 和 GPU/CPU fallback。
10. Local Axis / Reslice 导出和训练 manifest 导出。

## 架构目标

### UI 层

建议保留 `TifWorkbenchWidget` 作为外部入口，但让它逐步变薄。

目标职责：

- 创建和布局控件。
- 连接信号和槽。
- 从控件收集用户输入。
- 调用 service/controller。
- 根据返回结果刷新界面。
- 显示消息框、进度、日志和错误摘要。

不应长期放在 UI 层的职责：

- 判断某个标签是否可以成为训练真值。
- 直接决定预测导入写入哪个 label role。
- 直接写 volume sidecar。
- 直接管理多个后台任务的 token、取消和回调匹配。
- 直接保存复杂业务状态。

### Service / Controller 层

新增或整理为 GUI 无关的服务对象，优先方向：

- `TifSelectionController`：管理当前 specimen、part、reslice、label role、display mode。
- `TifLabelEditService`：处理 working edit / editable AI result 的加载、保存、dirty slice、undo/redo 元数据。
- `TifTruthPromotionService`：处理接受训练真值和批量接受 AI 结果。
- `TifRoiPartService`：处理 ROI 草稿、keyframe、mask preview、part 创建。
- `TifBackendWorkflowService`：处理 prepare/train/predict 的选择、前置检查、contract 请求和结果注册。
- `TifVolumePreviewService`：处理 volume preview、mask preview、cache key、ROI texture budget。
- `TifLocalAxisService`：处理 local axis draft、roll reference、reslice payload 和 manifest 导出。

这些 service 应尽量不依赖 PySide 控件。需要 UI 交互的地方返回结构化结果，由 UI 决定如何显示。

### Core / Domain 层

将研究数据安全规则沉到核心层，形成统一 guard：

- `manual_truth` 只能由明确核验动作生成。
- 训练只使用已核验的 `manual_truth`。
- 预测结果默认进入待核验层，不能直接污染训练真值。
- 原始预测备份必须只读并保留审计信息。
- 外部预测导入必须校验 shape、dtype、specimen/part/reslice 上下文。
- 保存和导出必须避免覆盖原始 TIF。
- 大规模写入动作必须有明确目标路径、来源角色和审计 metadata。

建议新增或整理：

- `AntSleap/core/tif_label_guard.py`
- `AntSleap/core/tif_write_guard.py`
- `AntSleap/core/tif_truth_policy.py`
- `AntSleap/core/tif_prediction_policy.py`

### Task 层

统一后台任务生命周期，而不是每个流程各自散落管理 `QThread`。

目标能力：

- 每个任务有 task id / token / context。
- 任务开始、进度、完成、失败、取消使用统一结构。
- 旧任务回调不能刷新当前已切换的 specimen / part / reslice。
- busy lock 统一计算，避免按钮状态和真实后台状态不一致。
- 支持取消、清理、错误摘要和日志路径保留。

建议新增：

- `AntSleap/ui/tif_tasks.py`：Qt task adapter。
- `AntSleap/core/tif_task_state.py`：任务状态结构。
- `AntSleap/core/tif_task_context.py`：任务上下文匹配规则。

### 状态层

逐步把散落的实例属性收束为明确状态对象：

- `TifSelectionState`
- `TifEditState`
- `TifPreviewState`
- `TifBackendState`
- `TifRoiState`
- `TifLocalAxisState`

状态对象应可序列化或至少可打印摘要，便于测试和错误排查。

## 建议目录结构

```text
AntSleap/
  core/
    tif_label_guard.py
    tif_prediction_policy.py
    tif_truth_policy.py
    tif_write_guard.py
    tif_task_context.py
    tif_task_state.py
  services/
    __init__.py
    tif_selection_controller.py
    tif_label_edit_service.py
    tif_truth_promotion_service.py
    tif_roi_part_service.py
    tif_backend_workflow_service.py
    tif_volume_preview_service.py
    tif_local_axis_service.py
  ui/
    tif_workbench.py
    tif_workbench_dialogs.py
    tif_workbench_canvas.py
    tif_workbench_workers.py
    tif_workbench_translations.py
    tif_workbench_layout.py
    tif_tasks.py
```

## 迁移策略

### 阶段 1：可见结构拆分

目标：先把低耦合内容从 `tif_workbench.py` 拆出。

内容：

- 翻译表和 `tt()`。
- 弹窗类。
- `TifSliceCanvas`、`TifVolumeCanvas`。
- worker 类。
- 独立纯函数。

验收：

- `TifWorkbenchWidget` 外部导入路径不变。
- 原有 GUI 流程行为不变。
- TIF 工作台测试通过。

### 阶段 2：研究数据安全核心化

目标：把最重要的数据保护规则从 UI 下沉到核心层。

内容：

- `manual_truth` 接受规则。
- 预测导入和 raw backup 规则。
- working edit / editable AI result 写入规则。
- 训练样本选择规则。
- 路径和覆盖保护规则。

验收：

- 单元测试覆盖所有安全规则。
- GUI 只调用受控接口。
- 任何新入口默认不能绕过安全规则。

### 阶段 3：Service / Controller 化

目标：把完整研究动作从 Widget 方法中抽出。

优先顺序：

1. Label save / dirty slice / auto-save。
2. Truth promotion / AI result acceptance。
3. ROI to part creation。
4. Backend prepare/train/predict workflow。
5. Volume preview request/cache。
6. Local axis / reslice export。

验收：

- service 层有 GUI 无关测试。
- GUI 测试只保留关键用户路径。
- 主要流程可通过 service 单独运行或模拟。

### 阶段 4：统一任务管理和状态对象

目标：降低后台任务和隐式状态导致的连锁故障。

内容：

- 引入统一 task manager。
- 统一 token/context 校验。
- 统一 busy lock。
- 引入 selection/edit/preview/backend/ROI/local axis 状态对象。

验收：

- 旧任务结果不会刷新错误界面。
- 后台取消后控件状态可恢复。
- 训练/预测/保存/预览之间不会互相踩锁。
- 状态摘要可用于日志、测试和 agent context。

## 测试要求

新增或加强单元测试：

- label role 写入规则。
- truth promotion guard。
- prediction import guard。
- source overwrite guard。
- ROI bbox / keyframe / mask preview 纯逻辑。
- backend sample selection。
- task context 匹配。
- dirty slice 保存和失败恢复。

保留 GUI 集成测试：

- 打开 TIF 工作台。
- 导入 TIF。
- 创建 part。
- 保存标注。
- 接受训练真值。
- 准备训练数据。
- 训练完成后进入预测。
- 预测导入后进入核验。
- GPU preview fallback。

## 成功标准

本次架构整理完成后，应满足：

- `tif_workbench.py` 不再承担多数业务规则。
- 新增功能优先加到 service/core/task 层，而不是继续堆到 Widget。
- 研究数据安全规则有集中入口和单元测试。
- 后台任务有统一生命周期管理。
- 主要 TIF 工作流可以通过分层测试定位问题。
- 未来支持批处理、WebUI、本地 API 或更多训练后端时，不需要从 GUI 文件里大规模抽逻辑。

## 需要用户确认的问题

1. 是否接受本分支作为一次较大的架构升级，而不是小范围修补？
2. 是否允许新增 `AntSleap/services/` 目录，作为 UI 与 core 之间的流程组织层？
3. 是否优先保证蚂蚁三维 TIF 研究流程，不把其他类群泛化作为本轮目标？
4. 是否希望本轮完成后发布为一个明确版本，例如 `2.3.0` 或 `2.4.0`？
5. 是否接受在重构期间临时增加较多测试文件，以换取后期维护稳定性？
6. 是否希望 task manager 一次性覆盖所有后台任务，还是先覆盖保存、训练、预测、ROI 创建这几个高价值任务？
7. 是否保留 `TifWorkbenchWidget` 作为长期兼容入口，避免外部代码和测试大面积改 import？
8. 是否要求所有新的用户可见提示继续保持中英双语？
