# TIF 工作台架构整理 Stage 4 复核记录

日期：2026-07-08

分支：`codex/tif-workbench-architecture-refactor`

对应需求文档：`docs/tif_workbench_architecture_refactor_requirements_zh.md`

对应执行清单：`docs/tif_workbench_architecture_refactor_execution_checklist_zh.md`

## 阶段目标

Stage 4 的目标是把后台任务、旧回调和散落状态先纳入统一账本，降低“用户已经切换 specimen / part，但旧 worker 结果又刷新当前界面”的风险。

对研究流程来说，这一步主要保护 TIF 导入、工作体构建、标签保存、ROI 创建、训练/预测、3D 预览、mask 预览和 Local Axis Reslice 导出这些长耗时动作。它不会改变 TIF 数据格式，也不改变训练真值和预测结果的核心规则；重点是让后台动作的开始、进度、完成、失败、取消和上下文匹配有统一记录。

## 新增或调整模块

- `AntSleap/core/tif_task_context.py`
  - 定义 `TifTaskContext`，包含 specimen、volume scope、part、reslice、label role、display mode、request key。
  - 提供 `matches()`，用于判断旧任务结果是否仍对应当前界面。
- `AntSleap/core/tif_task_state.py`
  - 定义 `TifTaskState`，包含 task id、task type、status、context、payload、error、started_at、finished_at、progress 和 message。
- `AntSleap/services/tif_task_manager.py`
  - 统一管理任务开始、进度、完成、失败、取消。
  - 统一 busy lock，覆盖 label save、truth promotion、ROI 创建、backend、TIF/Amira import、materialize、Local Axis export、volume preview、mask preview。
  - 终态任务不会被 late worker signal 覆盖，避免“用户取消”被误记成“程序失败”。
- `AntSleap/ui/tif_tasks.py`
  - 提供 Qt widget 到 task context 的 adapter。
- `AntSleap/services/tif_workbench_states.py`
  - 新增 `TifEditState`、`TifPreviewState`、`TifBackendState`、`TifRoiState`、`TifLocalAxisState`。
  - `TifSelectionState` 保留在 `AntSleap/services/tif_selection_controller.py`。

## 已纳入 task manager 的链路

- 标签保存：
  - `label_auto_save`
  - `label_manual_save`
- 训练真值接受：
  - `truth_promotion`
- ROI / mask：
  - `confirm_part_roi`
  - `mask_preview`
- 后端训练/预测：
  - `backend_action`
- 导入和体数据构建：
  - `tif_import`
  - `amira_import`
  - `tif_materialize`
- 预览：
  - `volume_preview`
- Local Axis：
  - `local_axis_export`

## 复核发现与补漏

复核 Stage 4 清单时发现并补了几处初稿疏漏：

1. 自动保存原本已经有 task 记录，但未进入统一 busy lock。已补为 `label_auto_save` 也参与写锁，避免自动保存和训练、导入、项目结构变更同时写状态。
2. `materialize` 初稿未完整登记 task。已补开始、进度、完成、失败记录，并在用户切换 specimen 后不强制跳回旧任务对应样本。
3. `local_axis_export` 初稿未完整进入 task manager。已补开始、进度、完成、失败记录，并在用户切换 part 后不强制切换到旧导出结果。
4. `backend_action` 初稿未完整进入 task manager。已补训练/预测 action、样本范围、进度、完成、失败、取消记录；取消后的 late failure 不再覆盖取消状态。
5. `truth_promotion` 初稿未完整进入 task manager。已补 task 记录和上下文匹配，旧回调不再强行刷新当前视图。
6. `part mask preview` 空结果路径原本可能清理线程但不结束 task。已补失败记录，避免留下运行中的假锁。
7. 等待 auto-save 时如果 worker 没有 result/error，原本可能只清线程不结束 task。已补取消记录，避免幽灵 busy lock。

## 与需求文档对照

- “每个任务有 task id / token / context”：已覆盖高风险后台链路。部分同步 UI 动作仍不创建 task，这是有意保留；它们没有后台旧回调风险。
- “任务开始、进度、完成、失败、取消使用统一结构”：已由 `TifTaskManager` 和 `TifTaskState` 承担。
- “旧任务回调不能刷新当前已切换的 specimen / part / reslice”：已在 label save、volume preview、mask preview、ROI 创建、materialize、backend、truth promotion、Local Axis export 等链路加入 context 或结果路径检查。
- “busy lock 统一计算”：已由 `TifTaskManager.busy_locked()` 接入 `_backend_write_lock_active()`。
- “状态对象可打印摘要”：`get_agent_context()` 已包含 `tif_task_summary` 和 `tif_state_summary`。

## 验证记录

均使用 TaxaMask 环境：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m compileall AntSleap\core\tif_task_context.py AntSleap\core\tif_task_state.py AntSleap\services\tif_task_manager.py AntSleap\services\tif_workbench_states.py AntSleap\ui\tif_tasks.py AntSleap\ui\tif_workbench.py
```

结果：通过。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_task_context tests.test_tif_task_state tests.test_tif_task_manager tests.test_tif_workbench_states tests.test_tif_selection_controller tests.test_tif_label_edit_service tests.test_tif_truth_promotion_service tests.test_tif_roi_part_service tests.test_tif_backend_workflow_service tests.test_tif_volume_preview_service tests.test_tif_local_axis_service
```

结果：24 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_label_guard tests.test_tif_write_guard tests.test_tif_truth_policy tests.test_tif_prediction_policy tests.test_tif_backend tests.test_tif_project tests.test_tif_stack_import tests.test_amira_import tests.test_tif_prediction_import
```

结果：79 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_workbench
```

结果：213 tests OK。

## 研究流程影响

- 切换样本或部位时，旧后台预览、导出、保存、训练/预测回调更难污染当前界面。
- 后台任务失败或取消后，按钮锁会按统一 task 状态恢复，减少“明明没在跑但按钮还锁着”的风险。
- agent context 现在能看到任务摘要和状态摘要，后续排查“训练/保存/预览卡在哪里”会更直接。
- 自动保存也进入写锁，更符合训练真值和标签保存的数据安全边界。

## 延后事项

- 这一步没有把所有 Widget 实例属性都完全迁入状态对象。Stage 4 先完成可读状态摘要和高风险后台链路接入；后续 Stage 5/6 再继续压缩 GUI 状态密度。
- `tif_workbench_layout.py` 仍延后。当前 task manager 和状态摘要已落地，后续拆 layout 时会更安全。
- 仍有少量同步动作只通过 service/core guard 管理，没有单独 task。只要它们不产生后台旧回调，就不属于 Stage 4 的高风险优先范围。
