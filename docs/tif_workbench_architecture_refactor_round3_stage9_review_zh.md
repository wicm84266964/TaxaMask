# TIF 工作台架构整理第三轮 Stage 9 正式复核记录

日期：2026-07-10

状态：`accepted`（主 Widget 收束、自动门与架构门通过；真实 TIF/GPU 研究流程人工验收留 Stage 10）

需求文档：`docs/tif_workbench_architecture_refactor_round3_requirements_zh.md`

## 本阶段目标

Stage 9 不再拆某一个单独功能，而是收束前八个阶段留下的公共壳层：只把真正跨工作流的写锁和任务协调放入 Coordinator，删除已经没有调用方的 Widget 转发方法，把控件创建与布局移出主文件，并确认选择、标注、ROI、部位 mask、三维预览、Local Axis、训练预测和结果复核仍通过同一套数据安全规则。

对研究工作流的直接意义是：打开项目、切换 specimen/part/reslice、保存标注、生成部位、接受 mask、执行重切片、训练预测和接受 AI 结果仍保持原有操作顺序，但每一步现在有清晰责任主体；后续修复某一环节时，不必再在一万多行文件中同时承担状态、信号、布局和任务生命周期风险。

## Coordinator 边界

- 新增 `TifWorkbenchCoordinator`，只负责后台写锁、通用 busy task、preview task ignore policy 和跨工作流提示文案。
- ROI 写锁标题、后台任务冲突顺序和 preview ignore 顺序均有直接测试。
- Coordinator 不持有 brush、ROI keyframe、mask volume、render cache、result review 等工作流内部状态。
- 所有生产工作流通过 `workbench.coordinator` 查询或阻止跨流程写入，不再调用 Widget 旧写锁 wrapper。

## View Builder 与主壳层

- 新增 `TifWorkbenchViewBuilder`，机械迁移原有控件创建和布局装配；控件参数、`objectName`、tab 顺序和已有可见行为保持不变。
- `TifWorkbenchWidget.__init__` 收束为 11 行，只负责调用 Shell 初始化、View Builder 创建/布局和启动挂接。
- 原 `_build_layout` 已从主 Widget 删除。
- View Builder 为 1,220 行；Shell 212 行；View scope 28 行；Signal Router 44 行；Coordinator 78 行，均低于 3,000 行限制。
- 启动烟测确认根对象名、训练 backend 按钮、3 个任务 tab 和 129 条 Router 连接正常建立。

## Wrapper 与状态清理

- 删除 30 个 AST/调用清单确认无调用的方法、11 个 Backend Widget 转发入口、9 个 ROI/Preview/Annotation 内部 wrapper、旧 layout wrapper 和旧写锁协调层。
- 大量显式 getter/setter 改为统一 descriptor，旧字段只定向代理 controller state，不形成第二份可写存储。
- 保留 `close_project`、`paint_at_widget_position`、`undo`、`redo`、`promote_working_edit` 等稳定公开入口，因为 canvas、快捷键、外部模块或关键 GUI 测试仍依赖其语义。
- 39 个不超过 4 行的方法中，公开兼容入口保留稳定边界；少量内部短方法负责格式化、控件启停或当前值查询，并非“Widget wrapper → Controller”的空转信号链。
- 主文件剩余 11 处 `.connect()` 只涉及 GPU canvas 运行信号和 TIF 导入 worker/thread 生命周期；按钮 `clicked` 已不再连接主 Widget wrapper。

## 测试与信号对接

- `tests/test_tif_workbench.py` 当前保留 220 条完整 Widget 与关键 GUI 路径测试，不再是唯一行为测试入口。
- Selection、Project Lifecycle、Annotation、ROI、Part Mask、Volume Render、Local Axis、Backend、Result Review、Shell 和 Coordinator 共有 58 条直接责任主体测试。
- Preview 资源不足测试已从删除的 Widget seam 迁到 `preview_controller.safe_load_volume_sidecar()` 和 `preview_controller.state_summary()`。
- 架构分析测试改为确认主文件保留必要 renderer/thread 信号且不含按钮 `clicked` 信号，符合“信号直连新责任主体”的需求。
- 新 controller、Coordinator 和架构测试均已进入 `scripts/run_validation_suite.py` 与架构分组。

## 全层自动门

使用项目真实 GUI 环境 `C:\Users\admin\anaconda3\envs\taxamask\python.exe` 执行，未使用缺少 PySide6 的 base Python 伪通过：

- `tif_core`：82
- `tif_storage_safety`：16
- `tif_services`：24
- `tif_preview_export`：106
- `tif_workbench`：278
- `tif_layout`：5
- `tif_architecture_round3`：4
- `gui_smoke`：94
- `ui_polish`：83

合计 692 条全部通过。

## 架构指标

| 指标 | Stage 8 | Stage 9 |
| --- | ---: | ---: |
| 主文件物理行数 | 6,738 | 5,045 |
| Widget 方法数 | 367 | 221 |
| 4 行以内方法 | 180 | 39 |
| 主文件 `.connect()` | 56 | 11 |
| 私有测试引用次数 | 372 | 361 |
| `__init__` | 已拆分前状态 | 11 行 |
| `_build_layout` | 主文件内 | 已移出 |

主文件低于原计划 7,500–9,000 行下界。这里不是通过删除错误处理、翻译、审计或测试实现，而是把 1,220 行 View Builder、多个已验收 workflow controller 及状态责任移到独立模块；692 条全层自动门仍全部通过，因此按“优于目标且功能保护无回退”接受，不人为把代码填回主文件。

最大单一新模块为 `tif_volume_render_controller.py` 2,649 行，低于 3,000 行硬限制；超过建议 1,500 行的 Part Mask 和 Volume Render controller 已复核，其体量来自完整工作流、GPU/CPU 回退和任务生命周期，没有继续混入其他工作流状态。

## 需求方向复核

- Selection / Project Lifecycle 继续是 specimen、part、reslice 上下文入口。
- Annotation 保存、ROI 确认、mask 接受、truth promotion、prediction 导入和 reslice 导出继续调用现有 service/core guard。
- manual truth、raw prediction、working edit、accepted mask 和原始 TIF 角色没有改名或改写策略。
- Qt 控件信号主要由 Signal Router 直连 controller，主 Widget 不再承担按钮转发层。
- controller state 没有在 Widget 中恢复第二份可写副本。
- Coordinator 只协调跨工作流锁，不吸收具体研究逻辑。
- 项目格式、SQLite schema、训练算法、Local Axis 数学和 GPU renderer 数学均未修改。

## 阶段结论

Stage 9 的主文件收束、兼容清理、信号迁移、状态唯一性、直接测试和九组自动门均通过，记为 `accepted`。进入 Stage 10：执行全部修改文件编译、最终九组验证、信号合同、验证脚本登记、Git/临时文件卫生检查，并明确列出需要用户用真实蚂蚁 TIF/GPU 数据完成的人工验收项目。
