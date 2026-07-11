# TaxaMask 第四轮架构优化 Stage 4 Review

日期：2026-07-11

状态：`verified / Gate C review recorded`；按用户连续执行授权进入 Stage 5，不推送 GitHub

## 1. 项目生命周期迁移

`main_window_project_lifecycle.py` 当前 1,224 行，集中负责：

- 默认输出目录、startup project、最近项目和新建入口。
- 2D SQLite、TIF SQLite、STL、legacy 2D JSON 和 legacy TIF JSON 类型识别。
- SQLite database 到 manifest 定位、legacy migration 和已有 migration 复用。
- SQLite backup、legacy JSON export 和 migration report。
- 项目打开、关闭、后台 worker 停止、延迟保存、项目绑定视图刷新和图片路径重定位。
- PDF/TIF 首次工作台创建入口与项目模式 tab 切换。

`main_window_project_dependencies.py` 只提供显式存储/迁移/Qt 依赖，不导入 MainWindow。`AntSleap.main` 继续通过继承保留全部旧方法入口。

## 2. 数据安全修复

延迟保存现在记录计划保存时的项目路径。回调触发时若当前项目路径已经改变：

1. 记录 `stale_project_save_skipped` runtime 事件。
2. 清空旧项目 pending save。
3. 不调用新项目的 `save_project`。

备份/legacy export 是用户明确发起的当前项目维护操作。如果维护前刚清理了旧项目的过期保存，维护入口会显式保存当前项目，再生成备份或导出，确保审计文件包含最新图片和标注。

这一规则防止旧项目任务污染新项目，同时不牺牲当前项目备份的完整性。

## 3. 格式与角色保持

未修改以下长期数据 contract：

- 2D/TIF SQLite schema version、manifest 和 database 命名。
- legacy JSON migration report、backup 目录和 legacy export 结构。
- STL rendered-view schema、2D review 注册和 provenance。
- TIF specimen/sidecar、label schema、manual_truth、working_edit、editable_ai_result 和 raw backup。
- 项目图片路径重定位及 known relocated roots。

PDF evidence、模型预测或 AI 草稿仍不会自动升级为训练真值。

## 4. 测试对接

legacy migration 和项目打开测试原先 patch `main_module.themed_yes_no_question`。方法迁出后补丁已迁到 `main_window_project_lifecycle`，避免自动化测试弹出真实确认框。

新增 Stage 4 contract 测试验证：

- `MainWindow.open_project_path/closeEvent/_flush_pending_project_save` 由新模块提供。
- 项目生命周期模块不反向导入 MainWindow。
- 旧项目定时保存切换到新项目后不会产生任何保存调用。

## 5. 结构变化

| 指标 | Stage 3 | Stage 4 | 变化 |
| --- | ---: | ---: | ---: |
| `main.py` 物理行 | 8,394 | 7,207 | -1,187（-14.1%） |
| MainWindow 直接类体 | 7,892 | 6,703 | -1,189 |
| MainWindow 直接方法 | 351 | 283 | -68 |
| MainWindow 直接 `.connect()` | 51 | 51 | 0 |
| 第四轮架构总连接 | 194 | 194 | 0 |

Stage 0 至 Stage 4，`main.py` 从 16,024 行降到 7,207 行，减少 8,817 行（55.0%）。

## 6. 性能

10 个成功独立进程样本；6 次已知 offscreen Qt `3221226505` 失败尝试由独立重试恢复。

| 指标 | Stage 3 | Stage 4 | 变化 |
| --- | ---: | ---: | ---: |
| Start Center 中位数 | 4,329.607 ms | 4,238.036 ms | -2.1% |
| Start Center P95 | 4,899.332 ms | 4,341.384 ms | -11.4% |
| import 中位数 | 4,201.125 ms | 4,113.548 ms | -2.1% |
| MainWindow 构造 | 120.879 ms | 118.656 ms | -1.8% |
| 小型 2D 项目打开 | 12.834 ms | 12.933 ms | +0.8% |
| 首次进入 TIF | 343.611 ms | 334.902 ms | -2.5% |
| Start Center RSS | 573.078 MB | 573.266 MB | +0.03% |

纯迁移路径无超过 5% 的中位数回退，启动 P95 进一步改善。

## 7. 验证

- 第四轮架构/Stage 1-4 工具测试：29 条通过。
- GUI smoke：94 条按 3 条隔离分块全部通过。
- UI polish：83 条按 5 条隔离分块全部通过。
- 2D SQLite：38 条通过。
- TIF storage safety：16 条通过。
- Stage 4 聚焦新建/打开/迁移/维护测试：10 条通过。
- Stage 3 已通过的 Agent、Blink、VLM/STL 与 TIF shell/GPU 证据保持有效；本阶段未改对应算法或数据角色。
- package/source import、`py_compile` 和 `git diff --check` 通过。

## 8. Gate C 结论

Stage 3-4 达到 `verified`，Gate C review 和数据安全审计已形成。Start Center、Agent、2D/TIF/STL 打开关闭的最终可见人工验收按连续执行授权统一留到 Stage 9。现在形成独立本地提交并进入 Stage 5。
