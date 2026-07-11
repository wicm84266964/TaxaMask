# TaxaMask 第四轮架构优化 Stage 3 Review

日期：2026-07-11

状态：`verified`；按用户连续执行授权进入 Stage 4，不推送 GitHub

## 1. Main Window Shell 拆分

- `main_window_shell.py`：状态初始化、顶层 2D 视图、工作台装配和启动收尾。
- `main_window_start_center.py`：Start Center、quick panel、project console、最近项目和工作流卡片。
- `main_window_agent_context.py`：Agent context 收集、字段预算、路由增强、PDF prompt 和工作流转交。
- `main_window_view.py`：只包含显示 Start Center、切 tab、刷新摘要和 Agent 状态的受限 view adapter。
- `main_window_signal_router.py`：按稳定 key 保证跨工作台信号只绑定一次。
- `main_window_coordinator.py`：串行处理 2D/TIF/Agent/返回 Start Center 的顶层转换，拒绝重入。
- `main_window_shell_dependencies.py`：shell 显式依赖面，不反向导入 MainWindow。

`MainWindow.__init__` 从 668 行降到 13 行，通过显式 factory 注入 ConfigManager、ProjectManager、数据库和 Engine，保留测试及外部调试对 `AntSleap.main` 的 patch 协议。

## 2. 信号治理

PDF、TIF、Blink 的 Start Center、Agent、label update 和 route refresh 共 8 条跨工作台连接改由 `connect_once` 管理。重复使用同一 key 不会再次连接。

架构审计脚本现在扫描第四轮已拆模块，并把 `connect_once` 作为受控连接登记；总连接仍为 194 条，没有把迁出的信号误报为消失，也没有把 router 内部 `signal.connect` 重复计数。

## 3. Agent 与导航

- Agent context 的允许字段、TIF/Blink/PDF/设置诊断字段和总字符预算未改变。
- `agent_context_routes.py` 的源码定位已改为 `main_window_agent_context.py`。
- Start Center 工作流卡、各工作台返回按钮和跨工作台 Agent 请求经过 coordinator。
- Agent Dashboard/WebEngine 仍在 Start Center 独立 panel；TIF GPU renderer 不与 Agent 生命周期绑定。

## 4. PDF/TIF 惰性创建

PDF Evidence Widget 和 TIF Workbench 不再在程序启动时创建：

- 首次打开 PDF 工具时创建 PDF Widget，之后复用同一对象和上下文。
- 首次进入或打开 TIF 项目时创建 TIF Workbench，之后复用同一对象、项目管理器和 GPU renderer。
- 测试可通过 `_pdf_widget_factory` / `_tif_workbench_factory` 注入隔离工厂，不读取本机 API 配置或私有数据。

对研究工作流的实际含义：启动中心更快、空闲内存更低；第一次进入 TIF 会出现约 0.34 秒的一次性加载，后续切换不再重复创建。PDF/TIF 项目格式、TIF label role、manual_truth、editable_ai_result 和 GPU 渲染策略均未改变。

## 5. 结构变化

| 指标 | Stage 2 | Stage 3 | 变化 |
| --- | ---: | ---: | ---: |
| `main.py` 物理行 | 9,985 | 8,394 | -1,591（-15.9%） |
| MainWindow 直接类体 | 9,489 | 7,892 | -1,597 |
| MainWindow 直接方法 | 390 | 351 | -39 |
| `MainWindow.__init__` | 668 行 | 13 行 | -655（-98.1%） |
| MainWindow 直接 `.connect()` | 128 | 51 | -77 |
| 第四轮架构总连接 | 194 | 194 | 0 |

Stage 0 至 Stage 3，`main.py` 已从 16,024 行降到 8,394 行，减少 7,630 行（47.6%）。

## 6. 性能

最终候选使用 10 个成功独立进程样本；6 次已知 offscreen Qt `3221226505` 失败尝试由独立重试恢复。

| 指标 | Stage 0 | Stage 3 | 变化 |
| --- | ---: | ---: | ---: |
| Start Center 可交互中位数 | 4,442.775 ms | 4,329.607 ms | -2.5% |
| Start Center P95 | 5,053.232 ms | 4,899.332 ms | -3.0% |
| import 中位数 | 4,189.770 ms | 4,201.125 ms | +0.3% |
| MainWindow 构造中位数 | 237.394 ms | 120.879 ms | -49.1% |
| 进入 2D/STL | 19.863 ms | 19.914 ms | +0.3% |
| 首次进入 TIF | 76.008 ms | 343.611 ms | 一次性惰性创建成本 |
| Agent context | 226.276 ms | 226.211 ms | 基本不变 |
| Start Center RSS | 598.883 MB | 573.078 MB | -4.3% |

纯启动路径中位数和 P95 均未回退；主窗口构造和初始内存有实质改善。首次 TIF 超过 250 ms，作为明确的首次加载事件保留，并列入 Stage 9 人工验收。

## 7. 验证

- 第四轮架构/Stage 1-3 工具测试：25 条通过。
- GUI smoke：94 条按 3 条隔离分块全部通过。
- UI polish：83 条按 5 条隔离分块全部通过。
- Agent/UI localization/report/runtime：64 条按 5 条隔离分块全部通过。
- TIF shell/signal/Agent/GPU 与 PDF safety：51 条通过。
- Blink/locator：103 条通过。
- generic VLM/STL：55 条通过。
- 2D SQLite：38 条通过。
- package/source import、`py_compile` 和 `git diff --check` 通过。

## 8. 结论

Stage 3 达到 `verified`。Start Center、Agent、PDF/TIF 首次创建、跨工作台导航和信号单次绑定已有独立责任与回归证据。按连续执行授权形成独立本地提交后进入 Stage 4 项目生命周期与存储路由。
