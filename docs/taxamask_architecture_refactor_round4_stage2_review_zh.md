# TaxaMask 第四轮架构优化 Stage 2 Review

日期：2026-07-11

状态：`verified / Gate B review recorded`；按用户连续执行授权进入 Stage 3，不推送 GitHub

## 1. 责任迁移

- `main_window_i18n.py`：集中主窗口中英文翻译表与 `tr/ui_text`。
- `main_window_dialog_support.py`：集中对话框共用的后端标签、路由状态、Agent 摘要和运行时常量。
- `training_report_dialogs.py`：训练预检、训练报告和结果浏览。
- `route_management_panel.py`：项目 parent -> child 路由、专家候选、备注与删除恢复规则。
- `settings_dialogs.py`：通用设置和 TIF 后端默认设置。
- `main_window_dialogs.py`：导出、Blink 入口和文献描述对话框。
- `model_settings_dialog.py` 及 `model_settings_*`：2D/STL 模型设置的界面构建、Blink 数据集、方案映射/验证、Agent 上下文。

`AntSleap.main` 继续 re-export 原有 10 个类名。项目格式、SQLite schema、模型 contract、默认值、objectName、主题、语言、TIF 数据角色和训练算法均未改变。

## 2. ModelSettings 拆分结果

原类约 2,135 行、67 个方法，`__init__` 约 800 行。当前结构：

| 模块 | 行数 | 责任 |
| --- | ---: | --- |
| `model_settings_dialog.py` | 77 | 状态准备、组合 mixin、兼容类入口 |
| `model_settings_view.py` | 778 | 页面构建与信号连接 |
| `model_settings_dataset.py` | 299 | Blink shrink 数据集浏览与删除 |
| `model_settings_profile.py` | 814 | 方案映射、值同步、backend 验证 |
| `model_settings_agent.py` | 238 | Agent 摘要、比例验证、最终值输出 |
| `model_settings_dependencies.py` | 140 | 明确依赖边界 |

`ModelSettingsDialog.__init__` 当前不超过 65 行；页面构建拆为 profile/extension、parent、child、inference 和 action 五段。没有把旧类整体搬成新的两千行文件。

## 3. 测试与信号迁移

迁移期间自动化测试发现并修复三类问题：

1. 页面构建方法不能继续读取旧 `__init__` 局部变量 `lang`，现统一从 `self.lang` 取得。
2. Python 星号导入默认忽略下划线辅助函数，依赖模块现显式开放设置 mixin 所需依赖。
3. 测试原先 patch `main_module.themed_yes_no_question` 和文献查询函数；类迁出后补丁点已迁到真实实现模块，避免测试弹出等待人工点击的确认框。

这意味着测试和信号连接已经对接拆分后的真实代码归属，而不是依靠 `main.py` 的旧内部实现。

## 4. Agent 上下文同步

`AntSleap/core/agent_context_routes.py` 已更新源码定位：

- 通用设置指向 `settings_dialogs.py`。
- 2D/STL 设置上下文指向 `model_settings_agent.py`。
- 模型方案快照指向 `model_settings_profile.py`。
- TIF 设置指向 `settings_dialogs.py`。

Ask Agent 仍只发送命令是否存在、contract placeholder、validation summary 和模型/路由摘要，不发送完整私有命令或 API key。

## 5. 结构变化

| 指标 | Stage 1 | Stage 2 | 变化 |
| --- | ---: | ---: | ---: |
| `main.py` 物理行 | 15,389 | 9,985 | -5,404（-35.1%） |
| 顶层类 | 11 | 1 | -10 |
| 顶层类直接方法 | 570 | 390 | -180 |
| `MainWindow` 方法 | 390 | 390 | 0 |
| `MainWindow` `.connect()` | 128 | 128 | 0 |

Stage 1-2 合计使 `main.py` 从 Stage 0 的 16,024 行降到 9,985 行，减少 6,039 行（37.7%）。MainWindow 类体仍为 9,489 行，后续 Stage 3-8 才处理其内部责任。

## 6. 性能对比

Stage 2 使用两组共 20 个成功独立进程样本；6 次已知 offscreen Qt `3221226505` 失败尝试均由独立重试恢复。

| 指标 | Stage 1 中位数 | Stage 2 中位数 | 变化 |
| --- | ---: | ---: | ---: |
| Start Center 可交互 | 4,217.980 ms | 4,283.806 ms | +1.6% |
| import | 3,990.554 ms | 4,060.627 ms | +1.8% |
| MainWindow 构造 | 223.857 ms | 221.220 ms | -1.2% |
| 模型设置打开/关闭 | 65.031 ms | 66.099 ms | +1.6% |
| Agent context | 209.063 ms | 220.644 ms | +5.5% |
| Start Center RSS | 598.521 MB | 598.695 MB | +0.03% |

Start Center P95 为 4,653.110 ms，相对 Stage 1 增加约 4.1%，仍低于 Stage 0 的 5,053.232 ms。Agent context 相对 Stage 1 有约 5.5% 波动，但仍比 Stage 0 中位数 226.276 ms 快约 2.5%；该路径未修改上下文算法，保留为后续 Stage 3 Agent 迁移的重点基线。

## 7. 验证

- 第四轮架构/性能/Stage 1-2 工具测试：18 条通过。
- GUI smoke：94 条按项目默认 3 条隔离分块全部通过。
- UI polish：83 条按项目默认 5 条隔离分块全部通过。
- Agent/UI localization/report/runtime：64 条按 5 条隔离分块全部通过。
- Blink/locator：103 条通过。
- generic VLM/STL：55 条通过。
- 2D SQLite：38 条通过。
- package 与 source 两种导入方式通过。
- 更新 Python 文件 `py_compile` 通过，`git diff --check` 通过。

较大的 GUI 分块会在断言全部通过后触发已知 Qt offscreen 进程退出错误，因此正式证据使用项目固定的小分块隔离方式。

## 8. Gate B 结论

Stage 1-2 达到 `verified`，Gate B review 已形成。自动化证据覆盖设置、报告、路由、文献、Agent、Blink、VLM 和 SQLite；可见界面人工检查按用户连续执行授权统一留到 Stage 9。现在形成独立本地提交并进入 Stage 3，不推送 GitHub。
