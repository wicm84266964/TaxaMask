# TIF 工作台架构整理 Stage 6 复核记录

日期：2026-07-08

分支：`codex/tif-workbench-architecture-refactor`

对应需求文档：`docs/tif_workbench_architecture_refactor_requirements_zh.md`

对应执行清单：`docs/tif_workbench_architecture_refactor_execution_checklist_zh.md`

## 阶段目标

Stage 6 的目标是把架构整理收束成一个可审计的版本节点：必要文档同步、候选版本说明、最终 TIF 回归验证、git 状态检查和合并前提醒。

## 文档同步

- `README.md`
  - 已复核，未修改。
  - 原因：公开安装入口、TIF/CT 工作流入口、平台支持和用户可见能力没有因本轮内部架构整理改变；README 当前已说明 TIF/CT 工作台、manual truth、raw backup、训练/预测和 GPU preview。
- `CHANGELOG_zh.md`
  - 已在本地新增 2026-07-08 开发阶段记录，说明 TIF 工作台架构整理、数据边界、统一 task/state 和分层回归测试。
  - 注意：当前仓库 `.gitignore` 忽略根目录 `CHANGELOG_zh.md`，因此普通提交不会包含该文件；可提交的版本说明已放入 `docs/releases/2.4.0-tif-architecture-refactor_zh.md`。
- `LLM_CONTEXT_DETAILED.md`
  - 已同步当前架构状态，说明后续 agent 应优先把新业务规则放入 core/service/task 层，而不是继续堆入 `TifWorkbenchWidget`。
- `docs/releases/2.4.0-tif-architecture-refactor_zh.md`
  - 已新增候选版本说明。
  - 建议版本号：`v2.4.0`。

## 最终验证记录

均使用 TaxaMask 环境：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_architecture_test_groups tests.test_tif_label_guard tests.test_tif_write_guard tests.test_tif_truth_policy tests.test_tif_prediction_policy tests.test_tif_project tests.test_tif_backend tests.test_tif_stack_import tests.test_amira_import tests.test_tif_prediction_import
```

结果：82 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_selection_controller tests.test_tif_label_edit_service tests.test_tif_truth_promotion_service tests.test_tif_roi_part_service tests.test_tif_backend_workflow_service tests.test_tif_volume_preview_service tests.test_tif_local_axis_service tests.test_tif_task_context tests.test_tif_task_state tests.test_tif_task_manager tests.test_tif_workbench_states
```

结果：24 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_roi_preview tests.test_tif_volume_preview tests.test_tif_gpu_volume_canvas tests.test_tif_export tests.test_tif_local_axis_reslice tests.test_tif_local_axis_ai tests.test_tif_local_axis_batch
```

结果：94 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_workbench
```

结果：213 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_backend.TifBackendTests.test_tif_trainer_adapter_smoke_closes_review_retrain_loop tests.test_tif_workbench.TifWorkbenchTests.test_tif_batch_import_worker_registers_multiple_stacks_metadata_only tests.test_tif_workbench.TifWorkbenchTests.test_confirm_roi_worker_creates_part_and_writes_accepted_mask tests.test_tif_workbench.TifWorkbenchTests.test_auto_save_writes_working_edit_after_brush_change tests.test_tif_workbench.TifWorkbenchTests.test_accept_selected_ai_results_promotes_batch_to_manual_truth tests.test_tif_workbench.TifWorkbenchTests.test_train_finished_updates_training_result_panel_and_prediction_manifest tests.test_tif_workbench.TifWorkbenchTests.test_stale_background_volume_preview_context_is_cancelled tests.test_tif_workbench.TifWorkbenchTests.test_3d_mask_mode_falls_back_from_gpu_canvas_to_cpu_pixmap_canvas
```

结果：8 tests OK。

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m compileall AntSleap tests\tif_architecture_test_groups.py tests\test_tif_architecture_test_groups.py
```

结果：通过。

```powershell
git diff --check
```

结果：无空白错误；仅出现 Windows 工作区 LF/CRLF 提示。

## Git 与输出检查

- `.tmp_validation/` 不存在，无需清理。
- `git status --short` 中的待提交内容为源码、测试和文档；被 `.gitignore` 忽略的 `CHANGELOG_zh.md` 不在普通待提交列表中。
- `git status --short --ignored` 显示数据库、项目 JSON、`TaxaMask_outputs/`、`artifacts/`、本地配置等仍处于 ignored 状态，没有进入待提交列表。
- 未执行 `git push`，符合本地离线 Git 工作流要求。

## 合并前建议

- 建议本地提交信息：`整理 TIF 工作台架构与分层回归测试`。
- 合并回 `main` 前，建议再次运行：
  - `tests.test_tif_workbench`
  - `tests.test_tif_architecture_test_groups`
  - `core_safety`
  - `service_task`
  - `preview_export`
  - `research_smoke`
- 如果要发正式 GitHub release，可基于 `docs/releases/2.4.0-tif-architecture-refactor_zh.md` 整理公开 release notes。

## Stage 6 结论

Stage 6 已完成：必要文档和版本说明已同步，TIF 架构最终验证通过，PySide 工作台测试在 `taxamask` 环境真实执行且未被跳过，git 状态未显示运行输出或私有数据进入待提交列表。
