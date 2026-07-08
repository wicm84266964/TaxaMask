# TIF 工作台架构整理第二轮 Stage 1 复核记录

日期：2026-07-09

分支：`codex/tif-workbench-architecture-refactor`

对应需求文档：`docs/tif_workbench_architecture_refactor_round2_requirements_zh.md`

对应执行清单：`docs/tif_workbench_architecture_refactor_round2_execution_checklist_zh.md`

## 阶段目标

Stage 1 目标是拆出第一批 Layout / 页面骨架代码，降低 `TifWorkbenchWidget` 对右侧栏、任务页和基础控件容器的直接承担，同时保持现有 objectName、信号连接和业务流程不变。

## 本阶段改动

新增：

- `AntSleap/ui/tif_workbench_layout.py`
  - `make_panel`
  - `make_section`
  - `make_task_page`
  - `make_right_sidebar_responsive`
  - `relax_right_sidebar_widget_width`
- `AntSleap/ui/tif_workbench_pages.py`
  - `build_task_pages`
- `AntSleap/ui/tif_workbench_control_panels.py`
  - `build_right_control_panel`
- `tests/test_tif_workbench_layout.py`

调整：

- `AntSleap/ui/tif_workbench.py`
  - 保留 `_make_panel`、`_make_section`、`_make_task_page`、`_make_right_sidebar_responsive` 作为兼容薄包装。
  - 任务 tab/page 创建改由 `build_task_pages` 负责。
  - 右侧栏 panel 和 operation status section 创建改由 `build_right_control_panel` 负责。
- `scripts/run_validation_suite.py`
  - 新增 `tif_layout` 套件，确保新增 layout 测试进入默认验证。

## 已避免的第一轮踩坑

- 保留了 `tifTaskTabs`、`tifTrainingModeTabs`、`tifPartTaskPage`、`tifDisplayTaskPage`、`tifAnnotationTaskPage`、`tifTrainingTaskPage`、`tifResultCompareTaskPage` 等 objectName。
- 右侧栏响应式规则继续保留，避免重新出现最大化后右栏溢出。
- 本阶段只拆 UI 容器和页面骨架，没有触碰 Local Axis busy lock、训练/预测业务规则、数据安全 guard 或项目存储格式。
- 复核过程中发现 `_section_title_labels` 初始化顺序问题，已改为显式初始化后再调用右侧栏 helper。

## 验证记录

使用环境：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe
```

已执行：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m py_compile AntSleap\ui\tif_workbench.py AntSleap\ui\tif_workbench_layout.py AntSleap\ui\tif_workbench_pages.py AntSleap\ui\tif_workbench_control_panels.py tests\test_tif_workbench_layout.py
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_workbench_layout
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_workbench.TifWorkbenchTests.test_right_sidebar_visible_pages_do_not_overflow_control_panel
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_validation_suite_script
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite tif_layout --timeout 120
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite gui_smoke --timeout 120
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite ui_polish --timeout 120
```

结果：

- `py_compile` 通过。
- `tests.test_tif_workbench_layout`：5 条通过。
- 右侧栏溢出回归测试通过。
- 验证脚本自审通过。
- `tif_layout`：5 条通过。
- `gui_smoke`：94 条通过，按 3 条一组分块执行。
- `ui_polish`：83 条通过，按 5 条一组分块执行。

备注：

- 曾尝试将 `tif_layout`、`gui_smoke`、`ui_polish` 合并到一次命令中执行，但外层工具在约 304 秒处超时，未形成有效通过证据。本阶段最终采用分 suite 执行结果作为验收证据。

## 阶段结论

Stage 1 通过。当前拆分已经建立 Layout / Pages / Control Panels 三个低耦合 UI 骨架模块，并通过 GUI 回归验证。下一阶段可以进入训练/预测面板控制器拆分，但仍应避免触碰 core guard 和项目数据格式。
