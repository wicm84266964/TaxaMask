# TIF 工作台架构整理第二轮 Stage 3 复核记录

日期：2026-07-09

分支：`codex/tif-workbench-architecture-refactor`

对应需求文档：`docs/tif_workbench_architecture_refactor_round2_requirements_zh.md`

对应执行清单：`docs/tif_workbench_architecture_refactor_round2_execution_checklist_zh.md`

## 阶段目标

Stage 3 目标是把 TIF 预览和资源不足处理从主 Widget 的零散异常路径中收束出来，尤其避免 Windows 页面文件 / 提交内存不足时直接抛出 CRITICAL ERROR，让用户误以为项目数据损坏。

## 本阶段改动

新增：

- `AntSleap/core/tif_resource_policy.py`
  - 分类 `WinError 1455` / 页面文件不足、`MemoryError`、GPU/OpenGL preview 失败、普通 volume IO 失败。
  - 返回结构化 `TifResourceIssue`，供 UI、状态摘要和测试使用。
- `AntSleap/ui/tif_preview_controller.py`
  - 提供 `safe_load_volume_sidecar`。
  - 统一记录最近一次资源问题。
  - 将资源问题显示到 slice/3D preview 状态、训练状态栏和 operation feedback。
- `tests/test_tif_resource_policy.py`
- `tests/test_tif_preview_controller.py`

调整：

- `AntSleap/ui/tif_workbench.py`
  - 初始化 `self.preview_controller`。
  - 新增 `_safe_load_volume_sidecar`、`_preview_resource_summary` 等薄入口。
  - 将 `load_specimen`、`load_part`、`_reload_label_volume`、`_load_edit_volume`、`_reload_part_mask_volume`、`_ensure_working_edit_volume` 中关键 `load_volume_sidecar` 调用改为安全加载。
  - `_current_state_summary()` 增加 `preview_resource`，供 Agent/日志判断当前是否为资源受限。
  - `volume_status_text()` 和 `_volume_status_summary_text()` 在资源受限时优先返回可理解提示。
  - GPU preview build / mask texture 失败会记录为资源问题，但仍保留现有 CPU fallback 行为。
- `AntSleap/ui/tif_workbench_translations.py`
  - 新增资源不足提示中文翻译。
- `scripts/run_validation_suite.py`
  - 将新增资源策略和 preview controller 测试加入 `tif_preview_export` 套件。

## 已避免的风险点

- 不改变 TIF sidecar 格式、label 格式、manual truth / editable AI result 语义。
- 不把资源不足误报为项目损坏；提示明确说明“项目数据没有被修改”。
- 不吞掉状态：资源问题会进入 `_current_state_summary()["preview_resource"]`。
- 不改变正常机器上的 3D preview 路径；GPU 失败仍按原逻辑 CPU fallback。
- edit volume 打开失败时保持 `edit_volume is None`，避免对不可写/未打开数组继续编辑。

## 验证记录

使用环境：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe
```

已执行：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m py_compile AntSleap\core\tif_resource_policy.py AntSleap\ui\tif_preview_controller.py AntSleap\ui\tif_workbench.py tests\test_tif_resource_policy.py tests\test_tif_preview_controller.py scripts\run_validation_suite.py
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_resource_policy
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_preview_controller
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_validation_suite_script
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite tif_preview_export --suite tif_workbench --timeout 300
```

结果：

- `py_compile` 通过。
- `tests.test_tif_resource_policy`：4 条通过。
- `tests.test_tif_preview_controller`：2 条通过。
- 验证脚本自审：4 条通过。
- `tif_preview_export`：106 条通过。
- `tif_workbench`：224 条通过。

## 人工验收建议

- 显卡空闲时打开真实 TIF 项目，确认 3D preview 正常，不因为资源 policy 降级。
- 后台训练占用资源时打开同一项目，确认页面文件 / 提交内存不足时显示可理解提示，程序不崩。
- 资源释放后重新点击 specimen / part，确认可以重新加载 volume。

## 阶段结论

Stage 3 通过。当前版本已经把最容易造成 CRITICAL ERROR 的 volume/memmap 打开失败收敛为可恢复资源状态。对研究流程来说，本阶段提升的是“大体数据 + 后台训练并行时”的可解释性和恢复能力，降低用户误判项目数据损坏的概率。

