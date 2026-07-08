# TIF 工作台架构整理 Stage 2 复核记录

日期：2026-07-08

分支：`codex/tif-workbench-architecture-refactor`

关联需求文档：`docs/tif_workbench_architecture_refactor_requirements_zh.md`

## 阶段目标

Stage 2 的目标是把研究数据安全规则从 GUI 方法中下沉到 core 层。重点保护训练真值、预测导入、raw backup、标签保存和路径覆盖边界，让后续 WebUI、CLI、批处理或新后端入口不能绕过这些规则。

## 新增核心模块

- `AntSleap/core/tif_label_guard.py`
  - 定义 `GuardResult`：`allowed`、`reason`、`message_key`、`details`。
  - 定义 label role 写入矩阵：`working_edit`、`editable_ai_result`、`raw_ai_prediction_backup`、`manual_truth`、`model_draft`。
  - 定义 UI/保存层可编辑 role 检查。
- `AntSleap/core/tif_truth_policy.py`
  - 定义 `manual_truth` 提升规则。
  - 定义训练样本只能使用 `manual_truth`。
- `AntSleap/core/tif_prediction_policy.py`
  - 定义预测导入计划：top-level 写入 `working_edit` + raw backup；part/reslice 写入 `editable_ai_result` + raw backup。
  - 定义预测 shape、dtype、上下文校验。
  - 明确拒绝预测导入写入 `manual_truth`。
- `AntSleap/core/tif_write_guard.py`
  - 定义 `WriteIntent`：目标路径、项目根目录、来源路径、来源 role、目标 role、操作、审计 metadata、是否允许覆盖。
  - 防止目标路径覆盖来源路径、跑出项目目录，或在未声明 overwrite intent 时覆盖已有目标。

## 已接入的高风险入口

- `AntSleap/core/tif_project.py`
  - `register_label_volume()`、`register_part_label_volume()`、`register_part_reslice_label_volume()` 接入 label guard。
  - `promote_working_edit_to_manual_truth()`、part/reslice truth promotion 接入 truth policy、label guard、write guard。
  - `copy_label_layer_to_working_edit()` 接入 label guard 和 write guard。
  - `evaluate_train_ready()` 与 `evaluate_part_train_ready()` 接入 `can_use_role_for_training()`。
- `AntSleap/core/tif_prediction_import.py`
  - 外部 prediction TIF 导入接入 prediction policy 和 write guard。
  - 保持导入目标为 `working_edit`、`raw_ai_prediction_backup`、legacy `model_draft`，不触碰 `manual_truth`。
- `AntSleap/core/tif_backend.py`
  - 后端预测结果导入接入 prediction policy、shape/dtype 校验和 write guard。
  - part/reslice 预测写入 `editable_ai_result` + raw backup。
  - top-level 预测写入 `working_edit` + raw backup + legacy draft。
- `AntSleap/core/amira_import.py`
  - Amira reviewed label 导入写入 `manual_truth` 前加入 reviewed truth import guard 和 write intent。
  - 从 `manual_truth` 复制 `working_edit` 前加入 write intent。
- `AntSleap/core/tif_stack_import.py`
  - 普通 TIF 导入创建空 `working_edit` 前加入 label guard 和 write intent。
- `AntSleap/ui/tif_workbench.py`
  - 编辑层选择、raw backup/manual truth 只读判断、手动保存、自动保存、空编辑层创建入口接入 core label guard。

## 需求文档对照

### 贴合项

- `manual_truth` 不再是普通预测导入目标，只能通过明确核验/提升流程生成。
- 训练 readiness 和后端 contract 仍只使用 `manual_truth`。
- 预测导入默认进入待核验层，并保留 `raw_ai_prediction_backup`。
- raw backup 只能通过带审计 metadata 的 prediction raw backup import 写入，编辑入口会被拒绝。
- 外部 prediction TIF 的 shape、dtype 和 specimen 上下文校验已集中到 `tif_prediction_policy.py`。
- 大规模写入动作已有 `WriteIntent`，高风险入口会声明目标路径、来源路径/role、目标 role、审计 metadata 和 overwrite intent。
- UI 层仍负责显示提示，但关键安全判断已转为调用 core guard。

### 边界说明

- `AntSleap/core/tif_volume_io.py` 仍保留低级通用 IO 函数，供测试、导出、临时 sidecar 和底层工具使用。
- Stage 2 没有把所有低级 IO 函数改成强制要求 `WriteIntent` 参数，因为这会一次性影响大量非研究真值写入场景。
- 当前制度化边界落在高风险 project/import/backend/UI 保存入口。后续 Stage 3 service 化时，应继续把新写入入口统一导向这些受控接口。

## 新增测试

- `tests/test_tif_label_guard.py`
  - 覆盖 label role 写入矩阵、raw backup 只读、manual truth explicit review、scope-specific editable role。
- `tests/test_tif_truth_policy.py`
  - 覆盖 manual truth 提升规则、raw backup/model draft 不能提升、训练只能使用 manual truth。
- `tests/test_tif_prediction_policy.py`
  - 覆盖 prediction import plan、manual truth target 拒绝、shape/dtype/context 校验。
- `tests/test_tif_write_guard.py`
  - 覆盖 source overwrite、项目目录边界、已有目标 overwrite intent。
- `tests/test_tif_project.py`
  - 新增 raw backup 不能提升为 manual truth 的集成回归。
- `tests/test_tif_backend.py`
  - 新增 backend prediction artifact 声称 `manual_truth` 时不会导入、不会修改训练真值的回归。

## 验证记录

### 已通过

```powershell
python -m py_compile AntSleap\core\tif_label_guard.py AntSleap\core\tif_write_guard.py AntSleap\core\tif_truth_policy.py AntSleap\core\tif_prediction_policy.py AntSleap\core\tif_project.py AntSleap\core\tif_prediction_import.py AntSleap\core\tif_backend.py AntSleap\ui\tif_workbench.py
```

```powershell
python -m pytest tests/test_tif_label_guard.py tests/test_tif_write_guard.py tests/test_tif_truth_policy.py tests/test_tif_prediction_policy.py tests/test_tif_project.py tests/test_tif_backend.py tests/test_tif_prediction_import.py
```

结果：`65 passed`。

```powershell
python -m pytest tests/test_tif_stack_import.py tests/test_amira_import.py tests/test_tif_project.py tests/test_tif_backend.py tests/test_tif_prediction_import.py tests/test_tif_label_guard.py tests/test_tif_write_guard.py tests/test_tif_truth_policy.py tests/test_tif_prediction_policy.py
```

结果：`79 passed`。

```powershell
python -m pytest tests/test_tif_roi_preview.py tests/test_tif_volume_preview.py tests/test_tif_export.py
```

结果：`24 passed`。

### 仍未完成的 GUI 阻断验证

默认 Python 环境没有 `PySide6`，因此 `tests/test_tif_workbench.py`、`tests/test_tif_gpu_volume_canvas.py`、`tests/test_ui_localization.py`、`tests/test_window_geometry.py` 仍不能在默认环境视为通过。

当前约束保持不变：

- 不向默认环境安装 `PySide6`。
- GUI / PySide6 验证应使用 `C:\Users\admin\anaconda3\envs\taxamask\python.exe`。
- `taxamask` 环境当前已确认有 `PySide6`，但未确认有 `pytest`；没有用户明确同意前不安装测试工具。

## Stage 2 结论

Stage 2 已达到“核心安全规则下沉”的主要目标：训练真值、预测导入、raw backup、标签保存和导入写入路径已经有 core 层 guard 与单元测试覆盖。

下一阶段应进入 Stage 3：Service / Controller 层。重点从“规则集中”转向“完整研究动作从 Widget 中抽离”，优先处理 label save、truth promotion、ROI part creation、backend workflow 和 preview request。
