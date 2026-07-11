# TaxaMask 第四轮架构优化 Stage 1 Review

日期：2026-07-11

状态：`verified`；按用户要求连续进入 Stage 2，不推送 GitHub

## 1. 责任迁移

- `AntSleap/app_runtime.py`：169 行，负责 Qt/WebEngine/WSL 环境准备、runtime log、日志清理、`faulthandler` 和异常记录。
- `AntSleap/ui/main_window_workers.py`：380 行，负责 inference、VLM、training、image import、external inference/training 和 dataset export worker。
- `AntSleap/ui/main_window_widgets.py`：76 行，负责 NoWheel 控件和 image group drag/drop list。
- `AntSleap/main.py`：继续 re-export 全部旧类名，生产调用、测试 monkeypatch 和 `from main import ...` 不变。

Stage 1 没有修改项目格式、SQLite、标注角色、训练算法、VLM schema、Blink 路由、TIF 或 PDF 工作流。

## 2. 循环依赖处理

训练、内置批推理和外部批推理 worker 原本直接调用 `main.py` 的 `tr()`。新 worker 不反向导入 `main.py`，而是提供默认 identity translator；MainWindow 创建真实 worker 后通过 `worker.translate = tr` 注入翻译函数。

第一次候选把 `translate=` 作为构造关键字传入，GUI smoke 中使用旧签名的 FakeExternalBatchThread 发现不兼容。最终方案恢复旧构造调用协议，实例创建后再注入；这同时保护外部 patch 和测试替身。

## 3. 导入顺序与兼容

- `app_runtime.py` 不导入 PySide6、OpenCV 或 PyTorch。
- `main.py` 在 `import cv2` 和 PySide6 前调用 `_prepare_qt_runtime_environment()`。
- package 模式 `import AntSleap.main` 和源码模式 `sys.path + import main` 均通过。
- `main.InferenceThread is main_window_workers.InferenceThread` 等 re-export identity 已验证。
- runtime 私有旧名称仍作为 alias 保留。

## 4. 结构变化

| 指标 | Stage 0 | Stage 1 | 变化 |
| --- | ---: | ---: | ---: |
| `main.py` 物理行 | 16,024 | 15,389 | -635（-4.0%） |
| 顶层类 | 22 | 11 | -11 |
| 顶层类直接方法 | 592 | 570 | -22 |
| `MainWindow` 方法 | 390 | 390 | 0 |
| `MainWindow` `.connect()` | 128 | 128 | 0 |

MainWindow 增加 6 行显式 translator 注入，因此类体从 9,483 行变为 9,489 行。这些行属于解除 worker 循环依赖和保持旧构造协议的明确依赖，不是新增业务责任。

## 5. 性能对比

10 个成功独立进程样本；Stage 1 候选发生 6 次 offscreen Qt 失败尝试，均由独立重试恢复并记录。

| 指标 | Stage 0 中位数 | Stage 1 中位数 | 变化 |
| --- | ---: | ---: | ---: |
| Start Center 可交互 | 4,442.775 ms | 4,217.980 ms | -5.1% |
| import | 4,189.770 ms | 3,990.554 ms | -4.8% |
| MainWindow 构造 | 237.394 ms | 223.857 ms | -5.7% |
| 进入 2D/STL | 19.863 ms | 19.024 ms | -4.2% |
| 进入 TIF 空工作台 | 76.008 ms | 72.343 ms | -4.8% |
| Agent context | 226.276 ms | 209.063 ms | -7.6% |
| Start Center RSS | 598.883 MB | 598.521 MB | -0.1% |

Start Center P95 从 5,053.232 ms 降到 4,470.789 ms，改善约 11.5%。Stage 1 达到纯迁移非回退门，但初始 RSS 仍约 599 MB，真正惰性工作台创建仍需 Stage 3/8。

## 6. 验证

- 第四轮架构/性能/Stage 1 工具测试：13 条通过。
- GUI smoke：94 条分块通过。
- UI polish：83 条分块通过。
- Agent/UI localization/report/runtime：64 条通过。
- Blink/locator：103 条通过。
- generic VLM/STL：55 条通过。
- 2D SQLite：38 条通过。
- 更新 Python 文件 `py_compile` 通过。
- `git diff --check` 通过。

一次直接单进程组合 GUI 测试超过 5 分钟后主动终止；按项目验证器分块重跑全部通过，不作为功能失败。

## 7. 结论

Stage 1 达到 `verified`。Runtime、worker 和基础 Widget 已有真实责任模块、直接测试、兼容 re-export 和性能非回退证据。按用户连续执行要求，形成独立本地提交后进入 Stage 2，不推送 GitHub。

