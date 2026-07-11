# TaxaMask 第四轮架构优化 Stage 7 正式复核记录

日期：2026-07-11

状态：`verified`；按用户连续执行授权进入 Stage 8，不推送 GitHub

## 1. 本阶段范围

Stage 7 将模型运行、训练、预测、VLM 和导出从 `AntSleap/main.py` 迁入五个独立 mixin：

- `main_window_model_management.py`：模型列表、parent model profile、route 状态、选择/删除和共享项目任务 context。
- `main_window_training.py`：preflight、内置/外部训练、停止、OOM retry 和报告浏览。
- `main_window_prediction.py`：单图/批量、内置/外部 prediction、AI label 清理和确认。
- `main_window_vlm.py`：scope、worker 队列、并发、取消、candidate 应用、SQLite run 和 AI draft 接受。
- `main_window_export.py`：dataset export worker、进度、成功和失败总结。
- `main_window_stage7_dependencies.py`：上述模块共享的显式依赖。

四个通用图片路径/分组方法补入 `main_window_image_navigation.py`，避免 VLM 模块成为其他工作流的路径工具宿主。

## 2. 跨项目数据安全

新增统一 project task context：同时记录 ProjectManager 实例和标准化项目入口路径。

- 图片导入、训练、内外部批量预测、VLM 或 dataset export 运行时，用户打开/新建 2D 或 TIF 项目会被阻止。
- parent training 成功回调只更新启动训练时的项目 profile；项目已变化时记录 `stale_project_task_result_skipped` 并丢弃。
- 内置和外部 batch inference 每个 result 与 finished 回调都验证 project context；旧回调不会调用当前项目的 `save_project()`。
- VLM worker result 同时验证 worker run id 和 project context；旧 run 或旧项目结果不会应用 candidate、写 SQLite run 或保存当前项目。
- VLM 旧项目 run 仍可在原 artifacts 目录形成 `stale_project` 独立总结，便于审计，但不进入新项目数据库。
- dataset export 的正常 UI 路径阻止项目切换；回调仍做 context 复核，避免旧任务在新项目界面显示成功结果。
- 关闭程序时，内部 batch inference、parent training 和 dataset export 也纳入 busy 检查。

## 3. 研究数据角色

- prediction、external prediction 和 VLM candidate 仍写为 AI draft，不自动成为 manual truth。
- `accept_current_image_ai_drafts` 与 batch accept 仍只确认已有 polygon 的草稿；box-only draft 保持待处理，不能进入训练。
- clear AI 仍按选择 scope 删除 AI 标注，保留 manual/confirmed label。
- VLM SQLite image result 与 run summary 的 schema、来源字段和 artifacts 路径不变。
- 训练算法、模型 contract、SQLite schema 和 TIF 内部架构均未修改。

## 4. 测试与依赖迁移

训练、预测、VLM 和模型管理测试 patch 已改到真实实现模块。新增 `test_main_window_stage7_training_prediction.py`，验证：

- 五个 Stage 7 方法由对应 mixin 提供且不反向导入 MainWindow。
- project context 同时要求 manager 实例和路径一致。
- stale training success 不更新新项目模型 profile。
- stale VLM run result 被忽略。
- stale project VLM result 取消队列且不写项目。
- dataset export 运行时阻止项目切换。

五个新模块再次通过字节码 `LOAD_GLOBAL` 审计，未发现未声明依赖；第四轮真实连接总数保持 194 条。

## 5. 结构变化

| 指标 | Stage 6 | Stage 7 | 变化 |
| --- | ---: | ---: | ---: |
| `main.py` 物理行 | 3,932 | 1,305 | -2,627（-66.8%） |
| MainWindow 直接类体 | 3,416 | 779 | -2,637（-77.2%） |
| MainWindow 直接方法 | 130 | 13 | -117（-90.0%） |
| MainWindow 直接连接 | 32 | 3 | -29 |
| 第四轮架构总连接 | 194 | 194 | 0 |

Stage 0 至 Stage 7，`main.py` 从 16,024 行降到 1,305 行，减少 14,719 行（91.9%），已达到 2,000 行以下目标。

## 6. 性能

10 个独立进程样本；7 个正常退出，3 个在完整结果打印后出现已记录的 offscreen Qt return code `3221226505`。

| 指标 | Stage 6 | Stage 7 | 变化 |
| --- | ---: | ---: | ---: |
| Start Center 中位数 | 4,253.760 ms | 4,331.381 ms | +1.8% |
| Start Center P95 | 4,989.076 ms | 5,208.650 ms | +4.4% |
| import 中位数 | 4,131.069 ms | 4,197.276 ms | +1.6% |
| MainWindow 构造 | 117.242 ms | 122.926 ms | +4.8% |
| 小型 2D 项目打开 | 12.420 ms | 13.287 ms | +7.0% |
| 图片切换 | 0.389 ms | 0.406 ms | +4.5% |
| 部位切换 | 0.252 ms | 0.262 ms | +3.9% |
| 首次进入 TIF | 333.978 ms | 343.551 ms | +2.9% |
| Start Center RSS | 573.135 MB | 573.174 MB | +0.01% |

小型 2D 打开相对回退 7.0%，超过 5% 中位数门；绝对增加 0.867 ms，新增项目任务 busy/context guard 是该路径的新安全工作。此项不以行数替代，保留为 Stage 8 复测和性能治理任务。其他中位数与 P95 均在门内。

## 7. 自动化验证

- 第四轮架构套件：47 条通过。
- Blink/locator 与训练 preflight：103 条通过。
- Agent/SAM 与运行时：64 条通过。
- generic VLM/STL/export：55 条通过。
- 2D SQLite：38 条通过。
- GUI smoke：94 条按 3 条隔离分块全部通过。
- UI polish：83 条按 5 条隔离分块全部通过。
- Stage 7 context contract：7 条通过。
- 新增/修改 Python 文件 `py_compile` 通过，`git diff --check` 通过。

## 8. 结论

Stage 7 达到 `verified`。训练、预测、VLM 和导出已从主文件拆出，后台结果具备项目/run context 防污染保护，AI draft 与 manual truth 角色保持不变。小型 2D 打开相对回退进入 Stage 8 治理清单。按连续执行授权形成独立本地提交后进入 Stage 8。
