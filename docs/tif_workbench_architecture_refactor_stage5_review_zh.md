# TIF 工作台架构整理 Stage 5 复核记录

日期：2026-07-08

分支：`codex/tif-workbench-architecture-refactor`

对应需求文档：`docs/tif_workbench_architecture_refactor_requirements_zh.md`

对应执行清单：`docs/tif_workbench_architecture_refactor_execution_checklist_zh.md`

## 阶段目标

Stage 5 的目标不是单纯增加测试数量，而是把 TIF 架构测试从“主要靠完整 GUI 工作台”整理成更专业的分层回归体系。

对研究工作流来说，这能让预测导入、训练真值保护、ROI、Local Axis、保存队列、训练/预测和 3D 预览的问题更容易定位：如果是 core 规则错，就看 core 测试；如果是 service/task 状态错，就看 service/task 测试；GUI 测试只承担真实按钮和关键路径集成。

## 新增测试分组

新增 `tests/tif_architecture_test_groups.py`：

- `core_safety`
  - 覆盖 label guard、write guard、truth policy、prediction policy、project、backend、TIF/Amira import、prediction import。
- `service_task`
  - 覆盖 selection、label edit、truth promotion、ROI service、backend workflow、volume preview service、local axis service、task context/state/manager、workbench state summary。
- `preview_export`
  - 覆盖 ROI preview、volume preview、GPU canvas、export、Local Axis reslice/AI/batch。
- `gui_key_path`
  - 保留完整 `tests.test_tif_workbench` 作为 PySide 工作台关键集成回归。
- `research_smoke`
  - 只挑关键研究路径：
    - TIF batch import metadata-only。
    - ROI 创建 part 并写入 accepted mask。
    - auto-save 保存 working edit。
    - editable AI result 接受为 manual truth。
    - 训练完成后进入预测。
    - 旧后台 preview context 被取消。
    - GPU mask fallback。
    - 训练-预测-核验-再训练闭环。

新增 `tests/test_tif_architecture_test_groups.py`：

- 验证测试分组引用的模块可导入。
- 验证研究安全 checklist 每项都有明确测试映射。
- 验证 smoke 分组覆盖主要 TIF 研究路径。

## 必须覆盖项对照

- 预测导入不会覆盖 `manual_truth`
  - `tests.test_tif_backend.TifBackendTests.test_part_predict_result_imports_editable_ai_result_without_touching_manual_truth`
  - `tests.test_tif_backend.TifBackendTests.test_top_level_predict_result_imports_current_labels_without_touching_training_truth`
  - `tests.test_tif_backend.TifBackendTests.test_backend_prediction_artifact_cannot_import_as_manual_truth`
- `raw_ai_prediction_backup` 只用于审计
  - `tests.test_tif_label_guard.TifLabelGuardTests.test_label_role_write_matrix_protects_truth_and_raw_backup`
  - `tests.test_tif_project.TifProjectTests.test_raw_backup_cannot_be_promoted_to_manual_truth`
  - `tests.test_tif_label_edit_service.TifLabelEditServiceTests.test_raw_backup_save_is_blocked`
- 未核验结果不能进入训练
  - `tests.test_tif_backend.TifBackendTests.test_predict_contract_accepts_objectively_ready_part_without_manual_truth`
  - `tests.test_tif_workbench.TifWorkbenchTests.test_part_training_action_reports_missing_training_truth_without_top_level_fallback`
  - `tests.test_tif_truth_policy.TifTruthPolicyTests.test_training_uses_manual_truth_only`
- 保存失败不会清空 dirty 状态
  - `tests.test_tif_workbench.TifWorkbenchTests.test_unsaved_working_edit_prompt_can_cancel_close_and_save`
  - `tests.test_tif_workbench.TifWorkbenchTests.test_background_auto_save_keeps_later_same_slice_edits_dirty`
- 旧任务结果不会写入当前切换后的 part
  - `tests.test_tif_task_manager.TifTaskManagerTests.test_context_matching_blocks_stale_results`
  - `tests.test_tif_workbench.TifWorkbenchTests.test_stale_background_volume_preview_context_is_cancelled`
  - `tests.test_tif_workbench.TifWorkbenchTests.test_stale_background_volume_preview_result_is_ignored`
- ROI 输出 shape 与 bbox 一致
  - `tests.test_tif_roi_preview.TifRoiPreviewTests.test_roi_bbox_crop_and_shape_are_zyx`
  - `tests.test_tif_roi_part_service.TifRoiPartServiceTests.test_confirm_part_roi_request_is_structured_and_sized`
- 训练样本选择只使用可训练样本
  - `tests.test_tif_backend_workflow_service.TifBackendWorkflowServiceTests.test_training_prefers_train_ready_parts`
  - `tests.test_tif_backend.TifBackendTests.test_contract_uses_manual_truth_for_prepare_dataset`
  - `tests.test_tif_export.TifExportTests.test_part_training_export_uses_resliced_part_and_manual_truth`
- Local Axis export 不在后端写锁期间执行
  - `tests.test_tif_workbench.TifWorkbenchTests.test_backend_write_lock_blocks_project_mutations`
  - `tests.test_tif_workbench.TifWorkbenchTests.test_task_manager_preview_lock_blocks_project_mutations`

## 与需求文档对照

- “将纯业务规则测试移到 core/service 单元测试”：已完成第一轮。Stage 2/3/4 新增规则与 workflow service 均有非 GUI 测试，Stage 5 新增分组把它们固定为 core/service/task 回归入口。
- “GUI 测试保留关键用户路径和控件集成”：完整 `tests.test_tif_workbench` 保留；新增 research smoke 分组只选关键路径，减少日常定位成本。
- “删除或改写过度依赖内部实现细节的脆弱测试”：本阶段未大规模删除旧 GUI 测试，原因是它们仍覆盖现有行为。实际清理策略改为先建立分组，后续发现脆弱测试再迁移到 core/service/task 层。
- “增加真实研究流程 smoke tests”：已建立 `research_smoke` 分组，复用并显式暴露已有真实闭环测试。
- “建立 TIF 架构回归测试分组”：已由 `tests/tif_architecture_test_groups.py` 完成。

## 验证记录

均使用 TaxaMask 环境：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_architecture_test_groups
```

结果：3 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_label_guard tests.test_tif_write_guard tests.test_tif_truth_policy tests.test_tif_prediction_policy tests.test_tif_project tests.test_tif_backend tests.test_tif_stack_import tests.test_amira_import tests.test_tif_prediction_import
```

结果：79 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_selection_controller tests.test_tif_label_edit_service tests.test_tif_truth_promotion_service tests.test_tif_roi_part_service tests.test_tif_backend_workflow_service tests.test_tif_volume_preview_service tests.test_tif_local_axis_service tests.test_tif_task_context tests.test_tif_task_state tests.test_tif_task_manager tests.test_tif_workbench_states
```

结果：24 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_roi_preview tests.test_tif_volume_preview tests.test_tif_gpu_volume_canvas tests.test_tif_export tests.test_tif_local_axis_reslice tests.test_tif_local_axis_ai tests.test_tif_local_axis_batch
```

结果：94 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_backend.TifBackendTests.test_tif_trainer_adapter_smoke_closes_review_retrain_loop tests.test_tif_workbench.TifWorkbenchTests.test_tif_batch_import_worker_registers_multiple_stacks_metadata_only tests.test_tif_workbench.TifWorkbenchTests.test_confirm_roi_worker_creates_part_and_writes_accepted_mask tests.test_tif_workbench.TifWorkbenchTests.test_auto_save_writes_working_edit_after_brush_change tests.test_tif_workbench.TifWorkbenchTests.test_accept_selected_ai_results_promotes_batch_to_manual_truth tests.test_tif_workbench.TifWorkbenchTests.test_train_finished_updates_training_result_panel_and_prediction_manifest tests.test_tif_workbench.TifWorkbenchTests.test_stale_background_volume_preview_context_is_cancelled tests.test_tif_workbench.TifWorkbenchTests.test_3d_mask_mode_falls_back_from_gpu_canvas_to_cpu_pixmap_canvas
```

结果：8 tests OK。

## 研究流程影响

- 以后修改预测导入或训练真值规则时，可以先跑 `core_safety`，不用先启动完整 GUI。
- 修改 task manager、保存队列、状态摘要时，可以先跑 `service_task`。
- 修改 3D 预览、ROI、Local Axis、导出时，可以先跑 `preview_export`。
- 发布前仍保留完整 `tests.test_tif_workbench`，确保实际 PySide 工作台没有被分层测试遗漏。

## 延后事项

- 本阶段没有删除大量旧 GUI 测试。它们仍然是当前行为的重要保护网，等 Stage 6 或后续维护中发现具体脆弱测试，再逐个迁移或收缩。
- `README.md` / `CHANGELOG_zh.md` / `LLM_CONTEXT_DETAILED.md` 同步放到 Stage 6 处理，避免中间阶段频繁改长期文档。
