# TaxaMask 第四轮架构优化 Stage 0 正式基线复核

日期：2026-07-11

状态：`verified / Gate A pending`

分支：`codex/taxamask-architecture-refactor-round4`

基线提交：`ae3c050`

需求文档：`docs/taxamask_architecture_refactor_round4_requirements_zh.md`

执行清单：`docs/taxamask_architecture_refactor_round4_execution_checklist_zh.md`

## 1. 结论

Stage 0 已建立可重复的结构、方法、状态、信号、异步任务、测试依赖和性能基线。当前没有修改 `AntSleap/main.py` 业务代码，也没有改变 2D、Blink、TIF、PDF、Agent、训练、预测、项目格式或研究数据角色。

主窗口第四轮具备进入 Stage 1 的技术条件，但按 Gate A 规则，必须先由用户确认本基线和模块边界。

## 2. 新增验证工具

- `scripts/analyze_main_window_architecture.py`
  - 使用 Python AST 统计类、方法、长方法、连接、状态字段和异步入口。
  - 扫描生产代码和测试对 `main.py`、MainWindow 方法和顶层类的引用。
  - 为 390 个 MainWindow 方法分配初始工作流和 Stage 1-8。
  - 生成机器可读 JSON、方法/状态/兼容台账和信号/异步台账。
- `scripts/benchmark_main_window_workflows.py`
  - 使用 offscreen Qt、软件 OpenGL、临时 SQLite 项目和 8x8 测试图。
  - 不读取或写入用户配置、真实项目、模型权重或私有数据。
  - 每次测量使用独立 Python 进程，输出 10 次中位数和 P95。
  - 记录 Qt 子进程失败尝试并重试，不静默丢弃环境异常。
- `tests/test_main_window_architecture_analysis.py`
  - 固定 Stage 0 AST 基线并检查工作流/Stage 分类和台账章节。
- `tests/test_main_window_performance_benchmark.py`
  - 检查中位数、nearest-rank P95、临时输出和无私有数据约束。
- `scripts/run_validation_suite.py`
  - 新增 `taxamask_architecture_round4` suite，并继续保证所有 `tests/test_*.py` 都在默认库存内。

一次性机器数据位于 `.tmp_validation/round4_stage0/`，不进入 Git：

- `architecture_report.json`
- `performance_baseline.json`
- `performance_smoke.json`

## 3. 正式结构基线

| 指标 | Stage 0 正式值 |
| --- | ---: |
| `main.py` 物理行 | 16,024 |
| 顶层类 | 22 |
| 顶层函数 | 35 |
| 顶层类直接方法 | 592 |
| 私有方法 | 413 |
| 全文件 `.connect(...)` | 194 |
| 直接 `self.<field> = ...` 状态赋值行 | 658 |
| `MainWindow` 物理行 | 9,483 |
| `MainWindow` 方法 | 390 |
| `MainWindow` `.connect(...)` | 128 |
| `MainWindow.__init__` | 668 行 |
| MainWindow 不少于 50 行的方法 | 42 |
| MainWindow 不少于 100 行的方法 | 10 |
| MainWindow 唯一可写状态字段 | 238 |
| MainWindow AST 状态赋值出现次数 | 418 |
| `main.py` 兼容导入位置 | 14 |
| 五个关键测试文件直接依赖行 | 324 |
| 关键测试私有引用出现次数 | 142 |
| 关键测试唯一私有引用 | 51 |
| QThread/Python thread/QTimer/start 异步入口 | 16 |

需求研究阶段曾使用文本缩进/简单正则估算 594 个方法、414 个私有方法、675 个状态赋值行和 192 个关键测试引用行。Stage 0 使用 AST 与更完整引用模式后，正式值修正为 592、413、658 和 324。后续阶段统一使用本报告口径。

## 4. 责任分配基线

390 个 MainWindow 方法已全部分配到 Stage 1-8：

| Stage | 初始方法数 | 主要责任 |
| --- | ---: | --- |
| Stage 1 | 15 | runtime、worker、基础 Widget |
| Stage 2 | 37 | dialog、settings、route、report |
| Stage 3 | 49 | shell、Start Center、Agent、TIF 顶层集成 |
| Stage 4 | 53 | project lifecycle、SQLite、迁移、关闭和恢复 |
| Stage 5 | 62 | image navigation、part tree、PDF/literature bridge |
| Stage 6 | 55 | annotation、SAM、Blink |
| Stage 7 | 88 | training、model、VLM、prediction、export |
| Stage 8 | 31 | 暂未按名称可靠分类，需在收束阶段人工复核 |

兼容类型：

| 类型 | 方法数 | 含义 |
| --- | ---: | --- |
| public/source compatibility | 38 | 有生产调用或明确公开语义 |
| signal compatibility | 59 | 当前作为 Qt signal target |
| test compatibility | 66 | 当前主要由测试直接访问 |
| internal/unreferenced | 227 | 不能直接删除，迁移时逐项复核动态调用和 UI 生命周期 |

顶层类中，Stage 1 可迁移类共 11 个、约 506 行；Stage 2 可迁移 Dialog/Panel 共 10 个、约 4,282 行。`ModelSettingsDialog` 单类 2,135 行、67 个方法、22 条连接，Stage 2 必须拆 view 构建、值映射、验证和 Agent context，不能整体搬成第二个巨型文件。

完整台账：

- `docs/taxamask_architecture_refactor_round4_method_inventory.md`
- `docs/taxamask_architecture_refactor_round4_signal_inventory_zh.md`

## 5. 建议模块边界

Stage 1-7 建议冻结以下责任名称。具体文件可以在实施中按规模拆分，但不得合并成新的大类：

| Stage | 建议模块 |
| --- | --- |
| 1 | `app_runtime.py`、`main_window_workers.py`、`main_window_widgets.py` |
| 2 | `training_report_dialogs.py`、`route_management_panel.py`、`model_settings_dialog.py`、`main_window_dialogs.py`、`literature_description_dialog.py` |
| 3 | `main_window_shell.py`、`main_window_view.py`、`main_window_signal_router.py`、`main_window_coordinator.py`、`main_window_start_center.py`、`main_window_agent_context.py` |
| 4 | `main_window_project_controller.py` |
| 5 | `main_window_image_navigation_controller.py`、`main_window_literature_controller.py` |
| 6 | `main_window_annotation_controller.py`、`main_window_blink_controller.py` |
| 7 | `main_window_training_controller.py`、`main_window_vlm_controller.py`、`main_window_prediction_controller.py` |

强制边界：

- `main.py` 继续作为启动和兼容门面。
- 新 controller 使用受限 view/state/dependency，不默认持有完整 MainWindow。
- 项目关闭、待保存和跨工作流 busy 决策只由 coordinator 串行决定。
- TIF 内部 controller 不进入第四轮拆分范围。
- 历史 `from main import ...` 和 `from AntSleap.main import ...` 通过 re-export 保持。

## 6. 性能正式基线

环境：

- Python：`C:\Users\admin\anaconda3\envs\taxamask\python.exe`
- Qt：offscreen
- OpenGL：software
- 每个样本为独立 Python 进程
- 10 个成功样本
- 5 个失败尝试，Windows return code `3221226505`，均在下一次尝试成功

| 指标 | 中位数 | P95 |
| --- | ---: | ---: |
| 进程总时长 | 8,042.651 ms | 8,989.628 ms |
| 启动到 Start Center 可交互 | 4,442.775 ms | 5,053.232 ms |
| 导入 `AntSleap.main` 及依赖 | 4,189.770 ms | 4,816.998 ms |
| 构造 MainWindow | 237.394 ms | 473.743 ms |
| 进入 2D/STL | 19.863 ms | 21.507 ms |
| 进入 TIF 空工作台 | 76.008 ms | 86.949 ms |
| 打开小型 2D SQLite 项目 | 12.428 ms | 13.583 ms |
| image 切换 | 0.377 ms | 0.430 ms |
| part 切换 | 0.264 ms | 0.348 ms |
| Model Settings 打开/取消 | 68.006 ms | 81.481 ms |
| Agent context 接受 | 226.276 ms | 233.864 ms |
| Start Center RSS | 598.883 MB | 599.465 MB |
| 2D/STL RSS | 600.898 MB | 601.418 MB |
| TIF 空工作台 RSS | 602.125 MB | 602.777 MB |
| 同步操作超过 100 ms | 1 | 1 |
| 同步操作超过 250 ms | 0 | 0 |

性能解释：

- 模块导入约占 Start Center 可交互时间的 94%，第四轮性能收益重点应是惰性导入和惰性工作台创建，而不是只压缩 MainWindow 构造代码。
- MainWindow 构造中位数约 237 ms，但 P95 约 474 ms，说明 Qt/offscreen 初始化仍有波动。
- Agent context 接受是当前唯一稳定超过 100 ms 的同步操作，Stage 3 应测量字段收集、压缩和 Agent panel 更新各自耗时。
- image/part 小 fixture 切换低于 1 ms，不代表大型真实项目；Stage 9 仍需研究者真实项目验收。
- 约 599 MB 初始 RSS 主要来自启动时导入 PyTorch、OpenCV、Qt/WebEngine 和各工作台。Stage 1/3/8 可验证惰性导入/创建，但不得影响首次进入工作流的可解释加载。
- 5 次 offscreen 子进程失败是环境稳定性证据，不计入成功样本性能值，也不能被解释为业务崩溃已经修复或不存在。

## 7. 自动化验证

命令：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --timeout 1200
```

结果：18 个 suite，共 1,091 条测试；1 条环境相关 skip，其余通过。

| Suite | 数量 |
| --- | ---: |
| tif_core | 90 |
| tif_storage_safety | 16 |
| tif_services | 25 |
| tif_preview_export | 108 |
| tif_model_backends | 31 |
| tif_workbench | 318，1 skip |
| gui_smoke | 94 |
| ui_polish | 83 |
| tif_layout | 5 |
| pdf_safety | 4 |
| validation_tooling | 4 |
| tif_architecture_round3 | 4 |
| taxamask_architecture_round4 | 5 |
| sqlite_2d | 38 |
| agentic_misc | 64 |
| blink_locator | 103 |
| pdf_literature | 44 |
| generic_vlm_stl | 55 |

新增/修改 Python 文件已通过 `py_compile`，`git diff --check` 通过。

## 8. Stage 0 风险判断

1. **高风险：早期导入顺序**。Qt/WSL/WebEngine 环境变量必须在 `cv2`、PySide6 和 WebEngine 前设置；Stage 1 runtime 提取必须有独立进程 import 测试。
2. **高风险：MainWindow 状态规模**。238 个唯一可写字段和 418 次 AST 赋值说明不能只把方法搬到 controller 后继续任意读写完整 MainWindow。
3. **高风险：项目生命周期**。Stage 4 涉及 SQLite/legacy/TIF/STL 路由、关闭和后台任务，必须在 Gate C 人工确认。
4. **中风险：ModelSettingsDialog**。2,135 行和 800 行 `__init__` 需要内部拆层，整体搬迁只能降低 `main.py` 行数，不能改善维护。
5. **中风险：信号网络**。194 条连接中 128 条位于 MainWindow；59 个方法目前是 signal compatibility，迁移必须同步信号测试。
6. **中风险：测试私有依赖**。五个关键测试文件有 142 次、51 种私有引用，第四轮目标至少减少 60%。
7. **环境风险：offscreen Qt**。10 个成功性能样本需要 5 次额外重试；真实可见窗口和 WebEngine/GPU 行为必须留到后续人工门验证。

## 9. Gate A 待用户确认

建议接受 Stage 0，并按原顺序进入 Stage 1：

1. 接受 AST 正式基线及对旧估算数字的修正。
2. 接受 390 个 MainWindow 方法的 Stage 1-8 初始分配；31 个 unclassified 方法在 Stage 8 人工收束。
3. 接受第 5 节建议模块边界。
4. 接受性能重点优先检查 import/lazy initialization 和 Agent context，而不是承诺每次拆文件都提升速度。
5. 接受 offscreen 子进程失败作为环境风险保留，不将其误报为研究工作流失败。
6. Gate A 接受后进入 Stage 1；Stage 1-2 完成并 verified 后在 Gate B 再进行用户确认。

