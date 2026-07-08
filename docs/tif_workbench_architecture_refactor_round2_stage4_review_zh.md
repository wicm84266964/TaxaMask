# TIF 工作台架构整理第二轮 Stage 4 复核记录

日期：2026-07-09

分支：`codex/tif-workbench-architecture-refactor`

对应需求文档：`docs/tif_workbench_architecture_refactor_round2_requirements_zh.md`

对应执行清单：`docs/tif_workbench_architecture_refactor_round2_execution_checklist_zh.md`

## 阶段目标

Stage 4 目标是把 Local Axis 三点参考、观察侧剖切面、roll reference 状态、草稿归属和导出前请求组装从 `tif_workbench.py` 中进一步收束出来，同时保留第一轮修复：preview busy lock 不能阻止 Local Axis 三点草稿交互。

## 本阶段改动

新增：

- `AntSleap/ui/tif_local_axis_controller.py`
  - 集中管理 Local Axis 草稿是否属于当前 specimen/part/reslice。
  - 集中管理 preview busy lock 例外：`volume_preview` / `mask_preview` 不阻止三点草稿交互。
  - 集中管理 roll reference 按钮同步、pick target、三点参考写入、清空 reference、A/B/C 平面对齐。
  - 集中管理导出前 payload 组装，继续调用 `TifLocalAxisService`。
  - 提供 export context 匹配入口，后续如果继续收束 worker callback，可以复用同一处判断。
- `tests/test_tif_local_axis_controller.py`
  - 覆盖草稿随 part 切换失效。
  - 覆盖 preview busy lock 下仍可进入 roll reference 点选。
  - 覆盖三点参考对齐后导出 payload 仍包含 `reference_plane`、`point_c`、训练来源和 provenance。

调整：

- `AntSleap/ui/tif_workbench.py`
  - 初始化 `self.local_axis_controller`。
  - 保留旧方法名作为薄 wrapper，例如 `copy_source_z_axis_to_local_axis_draft()`、`set_local_axis_pick_target()`、`pick_local_axis_roll_reference_at()`、`align_local_axis_to_reference_plane()`、`_current_local_axis_reslice_payload()`。
  - 主 Widget 继续保留 3D 投影、canvas 坐标转换、overlay 绘制、worker 线程启动和真实导出完成回调。
  - 不改变重切片算法、输出路径、reslice manifest、training sample、mask 导出策略或数据格式。
- `scripts/run_validation_suite.py`
  - 将 `tests.test_tif_local_axis_controller` 加入 `tif_workbench` 套件。
- `tests/tif_architecture_test_groups.py`
  - 将 backend panel controller 和 Local Axis controller 测试加入 GUI key path 分组。

## 已避免的风险点

- 没有删除 `TifWorkbenchWidget` 的旧入口，现有 GUI 测试、Agent 调用和 AntCode 对接仍可用旧方法名。
- 没有把 preview busy lock 当成普通写锁拦截三点点选；Local Axis 草稿交互继续忽略 `volume_preview` / `mask_preview`。
- 没有移动 3D canvas 坐标投影和 overlay 绘制，避免三点点击位置、观察侧剖切面深度和可视反馈发生隐性变化。
- 没有改变重切片覆盖范围、插值方式或 mask 裁剪策略；重切片清晰度和外接矩形行为仍按原逻辑。
- 新增测试进入验证脚本，避免“新测试存在但全量验证漏跑”的问题。

## 验证记录

使用环境：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe
```

已执行：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m py_compile AntSleap\ui\tif_workbench.py AntSleap\ui\tif_local_axis_controller.py
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_local_axis_controller
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_validation_suite_script
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite tif_preview_export --suite tif_workbench --timeout 300
```

结果：

- `py_compile` 通过。
- `tests.test_tif_local_axis_controller`：3 条通过。
- 验证脚本自审：4 条通过。
- `tif_preview_export`：106 条通过。
- `tif_workbench`：227 条通过。

## 人工验收建议

- 打开真实 TIF part，切到 3D preview。
- 点击 roll reference A/B/C 三个按钮，确认观察侧剖切面开启后可点三个参考点。
- 执行一次 A/B/C 平面对齐和重切片导出。
- 保存项目并重开，确认 reslice 记录仍在，并能被选中查看。

## 阶段结论

Stage 4 通过。当前版本把 Local Axis 的 UI 状态规则从主 Widget 中集中到 controller，主文件减少约 300 行，同时保留真实研究链路的旧入口和数据语义。对用户流程来说，本阶段主要降低的是“三点参考、重切片导出、切换 part/reslice 后状态错乱”的维护风险。

