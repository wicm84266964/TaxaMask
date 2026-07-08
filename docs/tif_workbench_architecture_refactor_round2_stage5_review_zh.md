# TIF 工作台架构整理第二轮 Stage 5 复核记录

日期：2026-07-09

分支：`codex/tif-workbench-architecture-refactor`

对应需求文档：`docs/tif_workbench_architecture_refactor_round2_requirements_zh.md`

对应执行清单：`docs/tif_workbench_architecture_refactor_round2_execution_checklist_zh.md`

## 阶段目标

Stage 5 目标是把 `tif_workbench.py` 进一步收束为协调器，删除已经由 controller/service 接管的重复逻辑，同时保留外部测试、Agent/AntCode 和旧方法名需要的兼容入口。

## 本阶段改动

新增：

- `AntSleap/ui/tif_workbench_style.py`
  - 承接 TIF 工作台专属样式表和 canvas 背景色。
  - 主 Widget 不再直接维护 300 多行 stylesheet 字符串。
- `AntSleap/ui/tif_agent_context.py`
  - 承接 TIF 工作台提供给 Agent/AntCode 的状态字典。
  - 保留训练样本规则、GPU/preview 状态、Local Axis / reslice 相关状态摘要和任务摘要字段。
- `tests/test_tif_workbench_style.py`
  - 锁定关键 objectName、滚动区域、保存状态标签和 canvas 背景色仍在样式表中。
- `tests/test_tif_agent_context.py`
  - 锁定 `TifWorkbenchWidget.get_agent_context()` 仍返回 TIF Agent 所需核心字段。

调整：

- `AntSleap/ui/tif_workbench.py`
  - `_apply_soft_style()` 改为调用 `build_tif_workbench_stylesheet()`。
  - `get_agent_context()` 改为调用 `TifAgentContextBuilder.build()`。
  - 保留 `_tif_canvas_background()` 兼容入口，避免现有测试和画布背景引用断裂。
- `scripts/run_validation_suite.py`
  - 将新增 Agent context 和样式测试加入 `tif_workbench` 套件。
- `tests/tif_architecture_test_groups.py`
  - 将新增测试加入 GUI key path 分组。

## 行数变化

- 第二轮前置基线 `d98c38d`：`tif_workbench.py` 约 14,694 行。
- Stage 4 提交 `68ab6d5` 后：约 13,928 行。
- Stage 5 当前：约 13,388 行。
- Stage 5 本阶段净减少：约 540 行。
- 第二轮累计净减少：约 1,306 行。

执行清单原目标写的是“减少 2500-4000 行，或有明确解释为何未达到”。本阶段没有继续追求 2500-4000 行，原因是：

- 训练/预测、标签保存、part mask、Local Axis overlay、真实导出 worker 等大块仍是高业务风险区域。
- 这些链路直接影响研究数据写入、manual truth 安全、重切片结果和训练入口，不适合作为 Stage 5 的机械清理对象。
- 现有测试和 Agent/AntCode 仍依赖部分旧方法名，因此保留薄 wrapper 比立即删除更稳。
- 当前收益主要来自职责密度下降，而不是强行压缩行数。

## 已避免的风险点

- 不改变 UI objectName，避免 GUI smoke、右侧栏和用户操作习惯断裂。
- 不改变任何 TIF 项目数据格式、label sidecar、reslice manifest、训练样本选择或预测导入策略。
- 不改变 Local Axis 三点、观察侧剖切面、重切片导出语义。
- 不改变 Agent 对接公开入口 `get_agent_context()`，只移动其内部组装逻辑。
- 新增 `tests/test_*.py` 已加入验证脚本，避免全量验证漏跑。

## 验证记录

使用环境：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe
```

已执行：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m py_compile AntSleap\ui\tif_workbench.py AntSleap\ui\tif_agent_context.py AntSleap\ui\tif_workbench_style.py tests\test_tif_agent_context.py tests\test_tif_workbench_style.py scripts\run_validation_suite.py
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_agent_context tests.test_tif_workbench_style
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_validation_suite_script
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_workbench.TifWorkbenchTests.test_tif_workbench_theme_switch_updates_panels_and_canvas_background
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_workbench.TifWorkbenchTests.test_ask_agent_context_includes_tif_view_and_annotation_training_focus
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_agent_context_routes
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_gui_smoke.GuiSmokeTests.test_agent_context_compaction_keeps_pdf_and_tif_route_fields
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite tif_workbench --suite tif_layout --suite ui_polish --timeout 300
```

结果：

- `py_compile` 通过。
- `tests.test_tif_agent_context` + `tests.test_tif_workbench_style`：2 条通过。
- 验证脚本自审：4 条通过。
- TIF theme 关键测试：1 条通过。
- TIF Agent context 关键测试：1 条通过。
- Agent route 测试：6 条通过。
- GUI smoke 中 Agent compact 关键测试：1 条通过。
- `tif_workbench`：229 条通过。
- `tif_layout`：5 条通过。
- `ui_polish`：83 条通过。

## 人工验收建议

- 打开 TIF 工作台，确认深色/浅色主题下右侧栏、保存状态、训练/预测区域和 Local Axis 区域样式正常。
- 点击 Ask Agent，确认 Agent 仍能识别当前是 TIF 工作台，并能看到 specimen/part、3D preview、训练样本、Local Axis 状态摘要。

## 阶段结论

Stage 5 通过。主 Widget 继续保留公开入口，但样式表和 Agent 状态对接已经移出主文件。对研究流程来说，本阶段不改变任何标注、保存、训练、预测或重切片结果，主要收益是降低主文件阅读密度，并让 Agent 对接字段有独立测试保护。

