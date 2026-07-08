# TIF 工作台架构整理 Stage 3 复核记录

日期：2026-07-08

分支：`codex/tif-workbench-architecture-refactor`

对应需求文档：`docs/tif_workbench_architecture_refactor_requirements_zh.md`

对应执行清单：`docs/tif_workbench_architecture_refactor_execution_checklist_zh.md`

## 阶段目标

Stage 3 的目标是新增 GUI 无关的 Service / Controller 层，把完整研究动作从 `TifWorkbenchWidget` 里逐步抽出。UI 继续作为外部入口和显示层，但不再独自决定 label 保存、训练真值接受、ROI 创建、训练/预测样本选择、体预览请求和 Local Axis 导出 payload 等关键流程。

## 已完成内容

- 新增 `AntSleap/services/`：
  - `tif_service_result.py`
  - `tif_selection_controller.py`
  - `tif_label_edit_service.py`
  - `tif_truth_promotion_service.py`
  - `tif_roi_part_service.py`
  - `tif_backend_workflow_service.py`
  - `tif_volume_preview_service.py`
  - `tif_local_axis_service.py`
- `TifWorkbenchWidget` 已初始化并调用这些 service。
- label role 选择、label save request、truth promotion、ROI part 创建请求、backend 训练/预测样本选择、volume/mask preview request、Local Axis draft/frame/reslice payload、Local Axis training manifest 请求已进入 service/controller 层。
- service 返回 `ServiceResult`，UI 负责消息框、状态栏、日志、按钮刷新和渲染刷新。
- service 层未直接依赖 PySide6 控件。

## 复核发现与补漏

复核时发现两处 Stage 3 初稿疏漏：

1. `TifVolumePreviewService` 已有测试，但 UI 尚未实际调用。已补为 `_volume_preview_request()` 和 `_volume_mask_preview_request()` 调用 service 生成工作台原生 cache key/request，保留原有缓存结构和 GPU/CPU 预览行为。
2. `TifLocalAxisService` 初稿只覆盖 manifest 导出请求，未覆盖需求中的 local axis draft、roll reference、reslice payload。已补 `build_initial_draft()`、`clear_roll_reference_points()`、`build_local_frame()` 和 `build_reslice_payload()`，并让 UI 调用。

另外，GUI 集成测试暴露 `TifBackendWorkflowService.train_ready_part_refs()` 曾触发昂贵的 label id 扫描。已修复为训练样本选择阶段使用 `evaluate_part_train_ready(..., validate_label_ids=False)`，保持原有大体数据性能边界。严格 label id 校验仍保留在 core 层可用，不在按钮选择阶段提前扫描。

## 与需求文档对照

- “UI 只负责显示、用户输入、按钮状态和结果呈现”：已部分达成。Stage 3 覆盖关键动作入口，但 `TifWorkbenchWidget` 仍有大量 UI 与状态更新代码，后续 Stage 4/5 继续收束。
- “Service / Controller 层负责组织完整研究动作”：已完成第一轮落地，覆盖 label、truth、ROI、backend、preview、local axis。
- “Core / Domain 层负责稳定业务规则和研究数据安全边界”：Stage 2 已完成，Stage 3 service 已调用 core/project guard，不绕开数据安全规则。
- “service 应尽量不依赖 PySide 控件”：已验证 `AntSleap/services` 中无 `PySide6`、`Qt`、`QWidget`、`QMessageBox`、`QThread`、`QApplication` 依赖。
- “主要流程可通过 service 单独运行或模拟”：已新增无 GUI service 单元测试。

## 验证记录

均使用 TaxaMask 环境：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m compileall AntSleap\services AntSleap\ui\tif_workbench.py
```

结果：通过。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_selection_controller tests.test_tif_label_edit_service tests.test_tif_truth_promotion_service tests.test_tif_roi_part_service tests.test_tif_backend_workflow_service tests.test_tif_volume_preview_service tests.test_tif_local_axis_service
```

结果：15 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_project tests.test_tif_backend tests.test_tif_prediction_import tests.test_tif_stack_import tests.test_amira_import tests.test_tif_label_guard tests.test_tif_write_guard tests.test_tif_truth_policy tests.test_tif_prediction_policy
```

结果：79 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_roi_preview tests.test_tif_volume_preview tests.test_tif_export
```

结果：24 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_workbench
```

结果：211 tests OK。

## 研究流程影响

- 标注保存：dirty slice 快照和保存前 guard 更集中，降低误写 `manual_truth` 或只读备份层的风险。
- AI 结果核验：接受为训练真值的路径进入 `TifTruthPromotionService`，更容易测试“只有核验后才能进入训练真值”。
- ROI / part：ROI 确认请求进入 service，后续 Stage 4 接统一 task manager 时会更容易挂接 token/context。
- 训练/预测：样本选择进入 service，并保留大体数据性能边界，避免选择阶段提前扫描 label id。
- 3D 预览：preview request/cache key 进入 service，原有缓存结构保持不变。
- Local Axis：draft、roll reference、frame、reslice payload 可在无 GUI 环境测试，有利于后续训练 manifest 和批量导出可信度。

## 延后事项

- `TifWorkbenchWidget` 仍然很大，Stage 3 只完成关键业务动作的服务化，不追求一次性拆完 layout 或所有 UI 状态刷新。
- 统一 task manager、context token、busy lock 和状态对象属于 Stage 4。
- `tif_workbench_layout.py` 继续延后到状态对象和 task manager 初步稳定后再拆，避免把强耦合 layout 提前硬拆。
