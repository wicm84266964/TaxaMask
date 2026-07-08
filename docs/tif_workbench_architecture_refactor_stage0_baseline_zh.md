# TIF 工作台架构整理阶段 0 基线记录

日期：2026-07-08

分支：`codex/tif-workbench-architecture-refactor`

关联文档：

- `docs/tif_workbench_architecture_refactor_requirements_zh.md`
- `docs/tif_workbench_architecture_refactor_execution_checklist_zh.md`

## 阶段 0 目标

阶段 0 的目标是固定当前状态，避免后续架构整理时不知道问题来自原有状态还是重构改动。当前阶段不改运行代码，只记录结构、后台任务、写入入口和测试基线。

## 当前 Git 状态

- 当前分支：`codex/tif-workbench-architecture-refactor`
- 基线采集时，工作区只有架构需求/执行文档变更。
- 尚未改动运行代码。

## 最大文件和测试分布

当前最大文件：

| 行数 | 文件 |
|---:|---|
| 18,081 | `AntSleap/ui/tif_workbench.py` |
| 16,001 | `AntSleap/main.py` |
| 8,127 | `tests/test_tif_workbench.py` |
| 4,894 | `AntSleap/ui/pdf_processing_widget.py` |
| 4,527 | `tests/test_ui_polish_scope.py` |
| 4,493 | `AntSleap/ui/tif_gpu_volume_canvas.py` |
| 3,706 | `tests/test_gui_smoke.py` |
| 2,638 | `AntSleap/core/tif_project.py` |

TIF 相关测试文件基线：

| 行数 | 文件 |
|---:|---|
| 1,119 | `tests/test_tif_project.py` |
| 770 | `tests/test_tif_backend.py` |
| 144 | `tests/test_tif_prediction_import.py` |
| 50 | `tests/test_tif_roi_preview.py` |
| 118 | `tests/test_tif_volume_preview.py` |
| 8,127 | `tests/test_tif_workbench.py` |

## `tif_workbench.py` 结构基线

总行数：18,081

顶层类和函数数量：

- class 数：23
- 函数/方法数：772
- `TifWorkbenchWidget`：约 14,656 行，640 个方法
- `TIF_TRANSLATIONS`：约 831 行

主要顶层类：

| 行号 | 类 | 行数 | 当前职责 |
|---:|---|---:|---|
| 1412 | `MaterialEditorDialog` | 69 | 材料编辑弹窗 |
| 1483 | `TifPartNameDialog` | 19 | part 命名弹窗 |
| 1621 | `TifTrainingResultDialog` | 229 | 训练结果展示弹窗 |
| 1852 | `WheelSafeComboBox` | 3 | UI 小控件 |
| 1857 | `MirroredStatusLabel` | 21 | UI 状态镜像 |
| 1880 | `LazyRegionMaskVolume` | 26 | lazy mask 访问 |
| 1908 | `WheelSafeSlider` | 20 | UI 小控件 |
| 1930 | `WheelSafeSpinBox` | 3 | UI 小控件 |
| 1935 | `TifSpecimenTree` | 17 | specimen 树控件 |
| 1954 | `TifSliceCanvas` | 630 | 2D slice 画布和标注交互 |
| 2586 | `TifVolumeCanvas` | 268 | 3D volume 占位/交互画布 |
| 2880 | `TifImportWorker` | 25 | TIF 导入后台任务 |
| 2907 | `TifBatchImportWorker` | 56 | 批量 TIF 导入后台任务 |
| 2965 | `TifMaterializeWorker` | 42 | metadata-only volume materialize |
| 3009 | `TifVolumePreviewBuildWorker` | 81 | volume/mask preview 构建 |
| 3092 | `TifPartMaskPreviewWorker` | 38 | part mask preview 构建 |
| 3132 | `TifLabelAutoSaveWorker` | 23 | label 自动保存 |
| 3157 | `TifLabelManualSaveWorker` | 25 | label 手动保存 |
| 3184 | `TifPromoteWorkingEditWorker` | 43 | 训练真值接受 |
| 3259 | `TifConfirmPartRoiWorker` | 95 | ROI 确认为 part |
| 3356 | `TifLocalAxisResliceExportWorker` | 21 | Local Axis reslice 导出 |
| 3379 | `TifBackendActionWorker` | 45 | prepare/train/predict 后端动作 |
| 3426 | `TifWorkbenchWidget` | 14,656 | 主工作台 |

最大方法：

| 行号 | 方法 | 行数 | 当前风险点 |
|---:|---|---:|---|
| 3430 | `TifWorkbenchWidget.__init__` | 897 | 控件创建、状态初始化、信号连接混在一起 |
| 11140 | `TifWorkbenchWidget._build_layout` | 558 | 大型布局装配 |
| 11699 | `TifWorkbenchWidget._apply_soft_style` | 345 | 样式集中在主类 |
| 4679 | `TifWorkbenchWidget._update_texts` | 245 | 翻译和 UI 状态耦合 |
| 5044 | `TifWorkbenchWidget.get_agent_context` | 163 | 状态摘要依赖 Widget 内部属性 |
| 16499 | `TifWorkbenchWidget.render_volume_preview` | 119 | 预览、缓存、GPU/CPU 路由耦合 |
| 12532 | `TifWorkbenchWidget.load_part` | 113 | selection、volume、label、UI 刷新耦合 |
| 12992 | `TifWorkbenchWidget._ensure_working_edit_volume` | 111 | 编辑层创建、注册、保存、UI 状态耦合 |

## 职责区块地图

当前粗略职责区块：

| 起始行 | 区块 | 说明 |
|---:|---|---|
| 169 | module helpers | ROI、bbox、mask、颜色、主题等辅助函数 |
| 569 | translations | `TIF_TRANSLATIONS` 中英双语表 |
| 1402 | `tt()` | 翻译入口 |
| 1412 | dialogs | 材料、part 命名、训练结果弹窗 |
| 1954 | canvas | 2D slice 和 3D volume 画布 |
| 2880 | workers | Qt worker 类 |
| 3426 | workbench | `TifWorkbenchWidget` 主类 |
| 4328 | button/style | 按钮角色和样式 |
| 4679 | localization | 文案刷新 |
| 5044 | agent context | agent 上下文摘要 |
| 5208 | backend config | 后端配置 UI 读写 |
| 5875 | result comparison | 结果对比、预测目标 |
| 6783 | slice navigation | 切片、显示模式 |
| 7186 | annotation tools | 标注工具按钮和模式 |
| 7246 | save/autosave | dirty slices、自动保存、手动保存 |
| 8056 | async cleanup/import | 导入、materialize、预览、ROI、后端线程清理 |
| 10369 | backend workflow | 训练就绪、样本选择、后端启动 |
| 11140 | layout | 主布局构建 |
| 12229 | project loading | 项目刷新、specimen/part 加载 |
| 12646 | materials | 材料表、标签表、分组标签 |
| 12893 | label volume loading | label/mask volume 加载 |
| 13482 | local axis | local axis draft、roll reference、reslice |
| 14438 | volume preview | 3D volume preview、GPU/CPU、缓存 |
| 16730 | annotation edit | brush、lasso、undo/redo、保存 |
| 17715 | export | training export、part package、截图、local axis manifest |

按方法名粗分的主类职责规模：

| 职责 | 方法数 | 方法行数 |
|---|---:|---:|
| UI 文案/布局/样式 | 85 | 3,023 |
| selection / state | 80 | 1,919 |
| ROI / part / mask | 75 | 1,651 |
| label edit / save | 91 | 1,533 |
| backend / train / predict | 68 | 1,312 |
| volume 3D preview | 128 | 1,899 |
| local axis | 41 | 772 |
| import / export | 10 | 193 |
| 其他 | 62 | 1,711 |

说明：这是按方法名关键词的粗略统计，用于阶段 0 架构地图，不作为精确依赖图。

## 后台任务基线

当前 worker 和信号：

| Worker | 行号 | signals | cancel |
|---|---:|---|---|
| `TifImportWorker` | 2880 | progress, finished, failed | 否 |
| `TifBatchImportWorker` | 2907 | progress, finished | 否 |
| `TifMaterializeWorker` | 2965 | progress, finished, failed | 否 |
| `TifVolumePreviewBuildWorker` | 3009 | progress, finished, failed | 是 |
| `TifPartMaskPreviewWorker` | 3092 | progress, finished, failed | 是 |
| `TifLabelAutoSaveWorker` | 3132 | finished, failed | 否 |
| `TifLabelManualSaveWorker` | 3157 | finished, failed | 否 |
| `TifPromoteWorkingEditWorker` | 3184 | finished, failed | 否 |
| `TifConfirmPartRoiWorker` | 3259 | progress, finished, failed | 否 |
| `TifLocalAxisResliceExportWorker` | 3356 | progress, finished, failed | 否 |
| `TifBackendActionWorker` | 3379 | progress, finished, failed | 是 |

当前分散状态：

- label save：`_label_auto_save_thread`、`_label_auto_save_worker`、`_label_auto_save_token`、`_label_auto_save_handled_tokens`、`_label_manual_save_thread`、`_label_manual_save_worker`、`_label_manual_save_token`
- promote：`_promote_thread`、`_promote_worker`、`_promote_request`
- import/materialize：`_tif_import_thread`、`_tif_import_worker`、`_tif_import_jobs`、`_tif_materialize_thread`、`_tif_materialize_worker`
- ROI/mask：`_part_mask_preview_thread`、`_part_mask_preview_worker`、`_part_mask_preview_token`、`_part_mask_preview_context`、`_confirm_part_roi_thread`、`_confirm_part_roi_worker`
- backend：`_tif_backend_thread`、`_tif_backend_worker`、`_tif_backend_action`、`_tif_backend_pending_selection`
- preview：`_volume_preview_build_thread`、`_volume_preview_build_worker`、`_volume_preview_build_token`、`_volume_preview_pending_token`
- local axis export：`_local_axis_reslice_export_thread`、`_local_axis_reslice_export_worker`、`_local_axis_reslice_export_context`

当前 busy lock 主要由 `_backend_write_lock_active()` 汇总：

- 后端训练/预测
- ROI 确认为 part
- Local Axis reslice export
- 手动保存
- 训练真值接受

注意：自动保存和 volume preview build 有独立处理路径，后续 task manager 需要统一描述其生命周期和 UI 锁行为。

## 写入入口基线

### UI 主类直接或间接写入入口

需要在阶段 2/3 重点下沉或 service 化的方法：

- `_save_active_volume_view_settings`
- `export_label_schema_dialog`
- `delete_selected_part_user_tag`
- `delete_selected_tif_model_record`
- `_on_label_auto_save_finished`
- `save_working_edit_async`
- `_on_label_manual_save_finished`
- `import_amira_directory_dialog`
- `_confirm_part_roi_request_sync`
- `cancel_part_roi_draft`
- `delete_current_part_volume`
- `delete_part_volume`
- `finish_part_contour_drag`
- `delete_current_part_keyframe`
- `clear_part_mask_keyframes`
- `add_current_rect_keyframe`
- `accept_part_mask_preview`
- `accept_selected_ai_results`
- `delete_selected_material`
- `_ensure_working_edit_volume`
- `_finalize_full_edit_save_metadata`
- `_finalize_part_editable_save_metadata`
- `save_working_edit`
- `_save_part_editable_label`
- `_save_part_mask_edit`
- `promote_working_edit`
- `copy_latest_model_draft_to_working_edit`
- `export_training_dataset`
- `export_current_part_package`
- `export_current_rendering_screenshot`
- `export_current_local_axis_reslice`
- `export_local_axis_training_manifest_dialog`

### Core / Project / IO 写入入口

当前核心层主要写入入口：

- `AntSleap/core/tif_project.py`
  - `save_project`
  - `register_working_volume`
  - `register_label_volume`
  - `register_part_label_volume`
  - `register_part_reslice_label_volume`
  - `promote_part_reslice_editable_result_to_manual_truth`
  - `promote_part_editable_result_to_manual_truth`
  - `promote_reviewed_part_results_to_manual_truth`
  - `copy_label_layer_to_working_edit`
  - `promote_working_edit_to_manual_truth`
  - `discard_part_roi`
  - `delete_tif_segmentation_model`
  - `discard_part`
  - `discard_specimen_scaffold`
- `AntSleap/core/tif_backend.py`
  - `create_run_dir`
  - `write_contract`
  - `import_prediction_result`
  - `_register_run`
- `AntSleap/core/tif_prediction_import.py`
  - `import_external_prediction_tif`
- `AntSleap/core/tif_stack_import.py`
  - `import_tif_stack`
  - `register_tif_stack_metadata`
  - `materialize_registered_tif_stack`
- `AntSleap/core/tif_part_extraction.py`
  - `write_contours_json`
  - `delete_keyframe`
  - `export_part_package`
  - `write_part_mask`
- `AntSleap/core/tif_volume_io.py`
  - `write_volume_sidecar`
  - `create_volume_sidecar_memmap`
  - `save_volume_array`
  - `flush_volume_array`
  - `create_empty_label_sidecar_like`
  - `copy_volume_sidecar`
- `AntSleap/core/tif_export.py`
  - `write_ome_tiff_volume`
  - `write_tiff_volume`
  - `write_nrrd_volume`
  - `write_mha_volume`
  - `write_nifti_volume`
  - `export_tif_training_dataset`
  - `export_tif_part_training_dataset`
  - `export_nnunet_dataset`
  - `export_tif_part_nnunet_dataset`
  - `export_monai_dataset`
- `AntSleap/core/tif_local_axis_reslice.py`
  - `export_part_reslice`
- `AntSleap/core/tif_local_axis_ai.py`
  - `import_local_axis_proposals`
  - `register_local_axis_model_manifest`
  - `export_local_axis_training_manifest`
  - `write_contract`
  - `import_backend_result`

后续阶段 2 的 guard 应优先覆盖 label role 写入、truth promotion、prediction import、source overwrite、大规模写入 intent；阶段 3 的 service 应优先减少 UI 直接调用这些写入入口的数量。

## IO / Project 层入口

当前 IO / Project 边界包括：

- 项目 manifest / legacy JSON：`TifProjectManager.save_project()`
- SQLite artifacts：`tif_project.py` 和 `tif_sqlite_migration.py`
- volume sidecar：`tif_volume_io.py`
- contours JSON：`tif_part_extraction.py`
- 训练/预测 run 目录：`tif_backend.py`、工具后端
- prediction import reports：`tif_prediction_import.py`
- local axis manifest / run 目录：`tif_local_axis_ai.py`
- training export / part package / screenshot sidecar：`tif_export.py`、`tif_part_extraction.py`、UI export 方法

阶段 2 需要明确：这些入口哪些属于项目内部受控写入，哪些属于用户选择的导出位置，哪些属于可删除/覆盖的临时或 run 输出。

## 测试基线

已执行命令：

```powershell
python -m pytest tests/test_tif_project.py tests/test_tif_backend.py tests/test_tif_prediction_import.py
python -m pytest tests/test_tif_roi_preview.py tests/test_tif_volume_preview.py
python -m pytest tests/test_tif_workbench.py
python -m pytest -rs tests/test_tif_workbench.py
```

结果：

| 测试 | 结果 | 说明 |
|---|---|---|
| `tests/test_tif_project.py tests/test_tif_backend.py tests/test_tif_prediction_import.py` | 55 passed | 核心 project/backend/prediction import 基线通过 |
| `tests/test_tif_roi_preview.py tests/test_tif_volume_preview.py` | 13 passed | ROI preview 和 volume preview 核心逻辑通过 |
| `tests/test_tif_workbench.py` | 211 skipped | 当前环境缺少 `PySide6`，GUI 工作台测试未实际执行 |

当前 Python：

```text
C:\Users\admin\anaconda3\python.exe
```

当前 GUI 验证环境补充：

- base Python 环境中 `PySide6` 不可导入，适合继续运行不依赖 GUI 的核心 pytest。
- TaxaMask 项目环境位于 `C:\Users\admin\anaconda3\envs\taxamask\python.exe`。
- TaxaMask 环境能导入 `AntSleap.ui.tif_workbench` 和 `TifWorkbenchWidget`。
- TaxaMask 环境当前没有 `pytest`，因此还不能直接运行 `tests/test_tif_workbench.py`。
- `requirements.txt` 已声明 `PySide6>=6.0.0`，说明 GUI 依赖属于 TaxaMask 运行环境要求。

阶段 1 开始拆 UI 文件前，至少需要保证以下之一：

1. 在 TaxaMask 环境安装/启用 pytest 后重跑 `tests/test_tif_workbench.py`。
2. 使用另一个已带 pytest 的项目实际 GUI 测试环境执行工作台测试。
3. 如果短期无法启用 GUI pytest，则阶段 1 必须额外执行 TaxaMask 环境导入检查、base 环境静态编译和核心单元测试，并把 GUI 工作台测试缺口保留为合并前阻断项。

## 阶段 0 对照需求文档复核

### 未偏离的部分

- 需求文档要求保留 `TifWorkbenchWidget` 外部入口；阶段 0 没有改代码，保持不变。
- 需求文档要求长期分层为 UI、Service、Core、Task、IO/Project；阶段 0 已记录各层当前入口和耦合位置。
- 需求文档强调研究数据安全；阶段 0 已列出 UI 和 core 中的写入入口，为阶段 2 guard 化做准备。
- 需求文档强调后台任务生命周期；阶段 0 已列出当前 worker、thread/token/context/busy lock 分布。
- 需求文档强调测试分层；阶段 0 已记录当前核心测试可执行，GUI 测试因环境缺口未执行。

### 发现的疏漏和补充要求

- GUI 测试基线不是绿色通过。base 环境中它们因缺 PySide6 跳过；TaxaMask 环境能导入 GUI，但缺 pytest。后续不能把 `test_tif_workbench.py` 作为已验证证据，直到项目 GUI 测试环境可实际执行。
- 自动保存和 volume preview build 的 lifecycle 没有完全进入 `_backend_write_lock_active()` 的同一模型，阶段 4 task manager 需要特别覆盖。
- `TifBatchImportWorker` 没有 failed signal，阶段 4 统一 task result 时需要统一错误路径。
- UI 仍有多个方法直接调用 project/core 写入入口，阶段 2/3 需要先建 guard/service，再逐步替换。
- `TIF_TRANSLATIONS` 是 831 行的大块结构，阶段 1 应优先拆出，降低主文件体积和翻译维护成本。
- `_build_layout` 和 `_apply_soft_style` 体积较大，阶段 1 拆文件时不应只拆弹窗/worker，也应评估 layout/style 拆分。

## 阶段 0 结论

阶段 0 已完成“结构地图、后台任务、写入入口、测试基线、IO/Project 边界”的记录。当前方向与需求文档一致，但进入阶段 1 前必须把 GUI 测试环境缺口作为显式验证管理项。

建议下一步：

1. 更新执行清单，勾选阶段 0 已完成项。
2. 在执行清单中加入“TaxaMask GUI 环境可导入但缺 pytest”的验证缺口，作为阶段 1 检查项或合并前阻断项。
3. 开始阶段 1：优先拆翻译表、弹窗、canvas、worker、helpers，并保持 `TifWorkbenchWidget` 外部入口不变。
