# TaxaMask 第四轮架构优化 Stage 8 与 Gate D 正式复核记录

日期：2026-07-11

状态：`verified with recorded performance gaps / Gate D review recorded`；按连续执行授权进入 Stage 9，不推送 GitHub

## 1. 本阶段范围

Stage 8 完成 MainWindow shell 收束、模块尺寸治理、信号/测试审计和最终候选性能复测：

- `main_window_presentation.py` 接管菜单、全局刷新、General/2D/TIF settings、语言、主题和日志显示。
- `main_window_image_grouping.py` 接管图片分组、panel crop identity 和项目图片路径匹配，避免 navigation 模块超过 1,500 行。
- `main_window_presentation_dependencies.py` 提供 presentation 显式依赖。
- project busy guard 的翻译延后到真正检测到任务时，正常项目打开不再做 6 次无效翻译。

MainWindow 类体现在只保留两个公开 SAM 信号和 13 行构造器。

## 2. 结构与状态审计

| 指标 | Stage 7 | Stage 8 | 变化 |
| --- | ---: | ---: | ---: |
| `main.py` 物理行 | 1,305 | 763 | -542（-41.5%） |
| MainWindow 类体 | 779 | 36 | -743（-95.4%） |
| MainWindow 直接方法 | 13 | 1 | -12 |
| MainWindow 直接状态写入 | 24 | 0 | -24 |
| MainWindow 直接连接 | 3 | 0 | -3 |
| 第四轮架构总连接 | 194 | 194 | 0 |
| MainWindow 直接私有测试引用 | 0 | 0 | 0 |

Stage 0 至 Stage 8，`main.py` 从 16,024 行降到 763 行，减少 15,261 行（95.2%）。MainWindow 直接私有实现测试引用按 Stage 0 口径从 146 次降到 0；GUI 测试通过实例调用继承 workflow 私有 contract 的 146 次仍保留，分析脚本不再把两者混为一项。

最大 workflow 模块为 `main_window_image_navigation.py` 1,392 行；project lifecycle、VLM、training 和 presentation 均低于 1,500 行建议上限。

## 3. 信号与后台生命周期

- 架构扫描 30 个责任模块，Qt `connect/connect_once` 总数保持 194 条。
- MainWindow 类体不再直接连接信号；shell signal router 仍管理 PDF/TIF/Blink 跨工作台连接。
- child training 五类信号保持单次连接。
- VLM worker 以 worker/run id 连接结果和 finished 回调。
- project-bound worker 通过 busy gate 与 project context 双重保护。
- 未发现生产模块反向导入 MainWindow。

## 4. Stage 8 性能

10 个独立进程样本；6 个正常退出，4 个在完整结果打印后出现已记录的 offscreen Qt return code `3221226505`。

| 指标 | Stage 7 | Stage 8 | 变化 |
| --- | ---: | ---: | ---: |
| Start Center 中位数 | 4,331.381 ms | 4,403.103 ms | +1.7% |
| Start Center P95 | 5,208.650 ms | 4,646.161 ms | -10.8% |
| import 中位数 | 4,197.276 ms | 4,272.629 ms | +1.8% |
| MainWindow 构造 | 122.926 ms | 122.501 ms | -0.3% |
| 小型 2D 项目打开 | 13.287 ms | 13.210 ms | -0.6% |
| 小型 2D 项目打开 P95 | 16.172 ms | 13.835 ms | -14.5% |
| 图片切换 | 0.406 ms | 0.393 ms | -3.2% |
| 部位切换 | 0.262 ms | 0.260 ms | -0.9% |
| 首次进入 TIF | 343.551 ms | 348.106 ms | +1.3% |
| Start Center RSS | 573.174 MB | 573.268 MB | +0.02% |

busy guard 惰性翻译降低了项目打开中位数和 P95，但相对 Stage 6 的 12.420 ms 仍慢 6.4%，绝对差 0.790 ms。

## 5. 第四轮性能目标实况

| 指标 | Stage 0 | Stage 8 | 结果 |
| --- | ---: | ---: | --- |
| Start Center 中位数 | 4,442.775 ms | 4,403.103 ms | -0.9%，未达到 5%-15% stretch 目标 |
| MainWindow 构造 | 237.394 ms | 122.501 ms | -48.4% |
| 图片切换 | 0.377 ms | 0.393 ms | +4.3%，未达到改善目标 |
| 部位切换 | 0.264 ms | 0.260 ms | -1.6%，未达到 10%-25% stretch 目标 |
| 小型 2D 项目打开 | 12.428 ms | 13.210 ms | +6.3%，新增安全 guard 后绝对增加 0.782 ms |
| Start Center RSS | 598.883 MB | 573.268 MB | -4.3%，略低于 5% stretch 目标 |
| 同步操作超过 250 ms | 0 | 1 | 首次进入惰性 TIF 工作台，未达到减少目标 |

未达标原因：启动时间约 97% 消耗在 PyTorch、OpenCV、Qt/WebEngine 和工作流模块导入；第四轮保留了历史公开 import 兼容。图片/部位小 fixture 已低于 0.4 ms，测量主要受 Qt event loop 噪声影响。TIF 工作台改为首次进入创建，因此约 348 ms 从启动阶段转移到首次使用阶段。以上不作为功能失败，但也不宣称达到 stretch 目标。

## 6. 自动化验证

- 第四轮架构套件：54 条通过。
- GUI smoke：94 条按 3 条隔离分块全部通过。
- UI polish：83 条按 5 条隔离分块全部通过。
- Stage 8 contract：6 条通过。
- Stage 5-7 已通过的 SQLite、Blink、Agent/SAM、VLM/STL、TIF backend 证据保持有效。
- 新增/修改 Python 文件 `py_compile` 通过，字节码全局依赖审计无缺失。

## 7. Gate D 结论

Stage 5-8 达到 `verified`。结构、信号、模块尺寸、测试对接和跨项目数据安全候选审计通过；性能 stretch gaps 已按真实数据留档。按用户连续执行授权不暂停确认，进入 Stage 9 完整自动化与真实研究流程验收准备。
