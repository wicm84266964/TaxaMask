# TIF 工作台架构整理第二轮 Stage 2 复核记录

日期：2026-07-09

分支：`codex/tif-workbench-architecture-refactor`

对应需求文档：`docs/tif_workbench_architecture_refactor_round2_requirements_zh.md`

对应执行清单：`docs/tif_workbench_architecture_refactor_round2_execution_checklist_zh.md`

## 阶段目标

Stage 2 目标是把训练 / 预测面板的 UI 状态协调逻辑从 `TifWorkbenchWidget` 中拆出，降低主 Widget 对预测目标表、模型库、训练结果摘要和后台运行按钮矩阵的直接承担。

## 本阶段改动

新增：

- `AntSleap/ui/tif_backend_panel_controller.py`
  - `TifBackendPanelController`
  - 接管预测目标表刷新、预测目标勾选同步、模型库显示、模型库按钮状态、训练结果摘要显示、后台运行按钮状态和 backend progress UI 更新。
- `tests/test_tif_backend_panel_controller.py`
  - 覆盖预测目标表、训练样本选择、模型库按钮状态、训练结果按钮锁定。

调整：

- `AntSleap/ui/tif_workbench.py`
  - 初始化 `self.backend_panel_controller`。
  - 保留原有 `_predict_*`、`_tif_model_*`、`_refresh_training_result_controls`、`_set_backend_controls_running`、`_selected_backend_samples_for_action`、`_on_tif_backend_progress` 等入口作为薄包装。
  - 真实训练线程启动、预测导入、训练结果注册、manual truth 提升和数据写入策略仍留在原链路。
- `scripts/run_validation_suite.py`
  - 将 `tests.test_tif_backend_panel_controller` 加入 `tif_workbench` 套件，确保默认验证覆盖新测试。

## 已避免的风险点

- 保留旧方法名，避免已有 GUI 测试、Agent 对接和内部调用失效。
- 保留预测目标选择集合的三元组 key：`(specimen_id, part_id, reslice_id)`，避免勾选状态和旧测试断裂。
- controller 的训练样本选择继续调用 `TifBackendWorkflowService.selected_backend_samples_for_action`，没有绕过 train-ready / predict-ready 检查。
- 没有改 `manual_truth`、`editable_ai_result`、prediction draft、训练输出目录、manifest 格式或模型权重文件处理规则。
- 模型库删除仍只删除项目中的登记记录，不删除磁盘上的模型文件。

## 验证记录

使用环境：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe
```

已执行：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m py_compile AntSleap\ui\tif_workbench.py AntSleap\ui\tif_backend_panel_controller.py tests\test_tif_backend_panel_controller.py scripts\run_validation_suite.py
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_backend_panel_controller
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_validation_suite_script
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite tif_services --suite tif_model_backends --suite tif_workbench --timeout 300
```

结果：

- `py_compile` 通过。
- `tests.test_tif_backend_panel_controller`：4 条通过。
- 验证脚本自审：4 条通过。
- `tif_services`：24 条通过。
- `tif_model_backends`：31 条通过。
- `tif_workbench`：224 条通过。

## 阶段结论

Stage 2 通过。训练 / 预测面板的 UI 协调职责已经从主 Widget 中分离出第一层 controller，主文件减少约 450 行直接 UI 状态逻辑。对研究流程来说，本阶段提升的是训练 / 预测入口的可维护性和可测试性；数据安全边界仍由原 service/core guard 管理。

