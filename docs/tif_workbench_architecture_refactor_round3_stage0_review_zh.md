# TIF 工作台架构整理第三轮 Stage 0 正式复核记录

日期：2026-07-10

状态：`accepted`（用户已授权按清单连续推进；本阶段自动门通过，研究门按无真实 fixture 的基线限制记录）

发布对照提交：`98e5ae938de804ea7d3cf6259108b1cb0eddbdf3`

需求文档：`docs/tif_workbench_architecture_refactor_round3_requirements_zh.md`

执行清单：`docs/tif_workbench_architecture_refactor_round3_execution_checklist_zh.md`

## 阶段目标

建立可重复的职责、信号、测试和兼容依赖地图，并先把已经提前进入 Stage 6 半迁移状态的候选工作树恢复到“可导入、可关闭、可跑完整分层验证”的正式实施起点。Stage 0 不新增研究功能，不改变数据格式、训练算法、Local Axis 数学或 GPU renderer 数学。

## 双基线

| 指标 | 发布对照基线 | Stage 0 正式结束工作树 |
| --- | ---: | ---: |
| `tif_workbench.py` 物理行数 | 14,234 | 8,574 |
| Widget 方法数 | 664 | 417 |
| 4 行以内方法数 | 147 | 150 |
| 主文件 `.connect(...)` 数 | 251 | 114 |
| 盘点测试数 | 397 | 397 |
| 直接访问 Widget 私有状态的测试数 | 155 | 138 |
| 私有引用出现次数 | 569 | 410 |
| 被测试直接依赖的不同私有名称 | 133 | 74 |

正式结束指标由以下命令重复生成：

`C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\analyze_tif_workbench_architecture.py --json .tmp_validation\tif_round3_stage0_formal_metrics.json --summary`

## 审计资产

- `scripts/analyze_tif_workbench_architecture.py`：AST 统计物理行、Widget 方法、薄方法、Qt 连接和测试私有依赖。
- `docs/tif_workbench_architecture_refactor_round3_method_inventory.md`：方法职责初始地图。
- `docs/tif_workbench_architecture_refactor_round3_test_migration_zh.md`：旧测试 seam 迁移台账。
- `docs/tif_workbench_architecture_refactor_round3_signal_migration_zh.md`：控件、Canvas、timer、worker 信号台账。
- `tests/test_tif_workbench_architecture_analysis.py`：验证审计输出覆盖方法、信号和私有测试依赖。

## 候选起点恢复

完整基线第一次运行暴露 Stage 6 半迁移断点，不能把“静态编译通过”误当成工作台可运行：

- 补回 Volume state 属性代理定义，使 `TifWorkbenchWidget` 可导入。
- 将 Morphology、Clip-plane depth 和 still timer 信号纳入 `TifVolumeRenderController` 的 Signal Router，不恢复旧 Widget wrapper。
- 补齐 Volume controller 的状态提示、renderer 释放和 slider 交互接口。
- 将 Preview、Selection、Lifecycle、Part Mask 和 Local Axis 对旧 Widget Volume 私有入口的调用改到 Volume controller。
- 修正 CPU fallback Canvas 的顶层 Workbench contract，保持 Local Axis 拖拽、resize 调度和状态 overlay 行为。
- 将 Volume worker、GPU texture、background preview 和 Local Axis redraw 的测试 patch seam 迁到新 controller/模块。

这些修改不是新增 Stage 6 功能，而是把现有候选草稿恢复成可验证起点；正式 Stage 6 仍需重新审查状态唯一性、信号合同、worker stale context、GPU/CPU fallback 和 controller 大小。

## 自动门

环境：`C:\Users\admin\anaconda3\envs\taxamask\python.exe`（Python 3.10.19）

- `tif_core`：82 条通过。
- `tif_storage_safety`：16 条通过。
- `tif_services`：24 条通过。
- `tif_preview_export`：106 条通过。
- `tif_workbench`：243 条通过。
- `tif_layout`：5 条通过。
- `tif_architecture_round3`：2 条通过。
- `gui_smoke`：94 条通过。
- `ui_polish`：83 条通过。
- 候选 controller 与主文件均通过 `py_compile`。
- `git diff --check` 无空白错误，仅有既有 LF/CRLF 提示。

## 研究门

仓库没有可安全直接使用的真实 TIF/GPU 项目 fixture，本阶段没有伪造人工结果。Stage 0 只确认自动化基线和既有行为可启动；真实蚂蚁 TIF、GPU preview、reslice 和训练/prediction 分别留到 Stage 6、7、8、10 明确验收，旧发布记录不能替代这些阶段的新验收。

## 对照需求文档

- 符合“按完整研究工作流拆分”，没有按行数机械删除安全逻辑。
- 方法、状态、Qt 信号、Canvas/timer/worker 回调和旧测试 seam 均进入台账。
- 未修改项目格式、SQLite schema、训练算法、Local Axis 数学或 GPU renderer 数学。
- 资源不足仍与数据损坏分开；项目关闭会释放 renderer/memmap，临时目录不再因半迁移异常被占用。
- 发布基线、阶段起点和阶段终点分开记录，不用 8,574 行冒充已完成架构。

## 阶段结论

Stage 0 自动门通过，方向未偏离需求文档。用户已授权按清单连续推进，因此本阶段记为 `accepted`，进入 Stage 1：Workbench Shell、View Contract 与 Signal Router。
