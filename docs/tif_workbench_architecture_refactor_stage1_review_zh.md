# TIF 工作台架构整理 Stage 1 复核记录

日期：2026-07-08

分支：`codex/tif-workbench-architecture-refactor`

关联需求文档：`docs/tif_workbench_architecture_refactor_requirements_zh.md`

## 阶段目标

Stage 1 的目标是先拆出低耦合、可见结构内容，保持程序行为不变，不提前重写训练、预测、保存或 ROI 业务规则。

## 已完成拆分

- `AntSleap/ui/tif_workbench_translations.py`
  - 迁出 `TIF_TRANSLATIONS` 和 `tt()`。
- `AntSleap/ui/tif_workbench_dialogs.py`
  - 迁出 `MaterialEditorDialog`、`TifPartNameDialog`、`TifTrainingResultDialog` 和 `summarize_tif_training_result()`。
- `AntSleap/ui/tif_workbench_canvas.py`
  - 迁出 wheel-safe 控件、`MirroredStatusLabel`、`LazyRegionMaskVolume`、`TifSpecimenTree`、`TifSliceCanvas`、`TifVolumeCanvas` 和 `create_tif_volume_canvas()`。
- `AntSleap/ui/tif_workbench_helpers.py`
  - 迁出 ROI/mask 相关 helper：bbox 裁剪、ROI keyframe 标准化、contour 转局部坐标、ROI shell mask 初始化、reslice volume 打开等。
- `AntSleap/ui/tif_workbench_workers.py`
  - 迁出 TIF import、batch import、materialize、volume preview、part mask preview、label auto/manual save、truth promote、ROI confirm、local axis export、backend action worker。

## 兼容性处理

`AntSleap/ui/tif_workbench.py` 继续 re-export 以下旧入口，避免测试、外部调用或 monkeypatch 路径突然失效：

- `TifWorkbenchWidget`
- `TifSliceCanvas`
- `TifVolumeCanvas`
- `create_tif_volume_canvas`
- `MaterialEditorDialog`
- `TifPartNameDialog`
- `TifTrainingResultDialog`
- `summarize_tif_training_result`
- 所有原 worker 类
- `_tif_write_label_slice_snapshots`
- 迁出的 ROI/mask helper 名称

## 需求文档对照

### 贴合项

- 符合“保留 `TifWorkbenchWidget` 作为外部入口”的要求。
- 符合“先拆低耦合内容：翻译表、弹窗、canvas、worker、纯函数”的迁移策略。
- 没有改变研究数据写入规则，避免在 Stage 1 就混入安全策略重写。
- ROI/mask helper 已从 Widget 主体移出，为 Stage 2 下沉核心安全规则和 Stage 3 service 化铺路。
- worker 已集中到专门模块，为 Stage 4 task manager 统一生命周期管理铺路。

### 暂缓项

- `AntSleap/ui/tif_workbench_layout.py` 尚未创建。
- `_build_layout()` 仍在 `TifWorkbenchWidget` 内。

暂缓原因：

- 当前 layout 构建强依赖大量 `self.xxx` 控件初始化顺序。
- 如果在 Stage 1 强行拆 layout，容易把控件创建、状态初始化、信号连接和布局装配同时打散，增加无意义风险。
- 更合理的顺序是在 Stage 3 service/controller 和 Stage 4 状态对象初步成型后，再把 layout builder 拆为只负责装配控件的薄层。

结论：

- Stage 1 没有偏离需求文档。
- `layout.py` 暂缓不影响长期架构目标，但必须在后续 UI 瘦身阶段重新处理。

## 验证记录

### 已通过

```powershell
python -m py_compile AntSleap\ui\tif_workbench.py AntSleap\ui\tif_workbench_canvas.py AntSleap\ui\tif_workbench_workers.py AntSleap\ui\tif_workbench_helpers.py AntSleap\ui\tif_workbench_dialogs.py AntSleap\ui\tif_workbench_translations.py
```

```powershell
python -m pytest tests/test_tif_project.py tests/test_tif_backend.py tests/test_tif_prediction_import.py tests/test_tif_roi_preview.py tests/test_tif_volume_preview.py
```

结果：`68 passed`。

```powershell
$env:QT_QPA_PLATFORM='offscreen'
C:\Users\admin\anaconda3\envs\taxamask\python.exe -c "import sys; from PySide6.QtWidgets import QApplication; app=QApplication.instance() or QApplication(sys.argv); from AntSleap.ui.tif_workbench import TifWorkbenchWidget, TifSliceCanvas, TifVolumeCanvas; w=TifWorkbenchWidget(lang='en'); print(type(w).__name__, isinstance(w.canvas, TifSliceCanvas), isinstance(w.volume_canvas, TifVolumeCanvas)); w.close(); app.processEvents()"
```

结果：`TifWorkbenchWidget True True`。

### 仍未完成的 GUI 阻断验证

默认 Python 环境没有 `PySide6`，以下测试不能在默认环境视为通过：

```powershell
python -m pytest tests/test_tif_gpu_volume_canvas.py tests/test_ui_localization.py tests/test_window_geometry.py
python -m pytest tests/test_tif_workbench.py
```

当前约束：

- 不再向默认环境安装 `PySide6`。
- `taxamask` 环境有 `PySide6 6.10.1`，但当前未确认有 `pytest`。
- 合并前必须在实际 GUI 环境完成等价 GUI 验证，或经用户允许给 `taxamask` 环境补齐测试工具。

## 行数变化

- Stage 0 基线：`AntSleap/ui/tif_workbench.py` 约 `18,081` 行。
- Stage 1 后：`AntSleap/ui/tif_workbench.py` 约 `14,954` 行。
- 主文件减少约 `3,127` 行。

## Stage 1 结论

Stage 1 已达到“可见结构拆分”的主要目标：主文件明显变薄，低耦合 UI 和 worker 代码已有专门模块承接，旧外部入口保持兼容。

下一阶段应进入 Stage 2：核心安全规则下沉。重点不再是继续搬 UI，而是把研究数据安全边界从 GUI 方法中抽出，形成可测试的 core guard。
