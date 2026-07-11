# TIF 工作台架构整理第三轮 Stage 8 正式复核记录

日期：2026-07-10

状态：`accepted`（自动门与架构门通过；真实训练、prediction 和外部 TIF 人工验收留 Stage 10）

需求文档：`docs/tif_workbench_architecture_refactor_round3_requirements_zh.md`

## 完整研究动作

训练样本诊断 → 选择模型和 backend → 启动 prepare/train/predict → 等待保存与写锁协调 → 接收进度、完成、失败或取消 → 登记训练模型和结果摘要 → 比较 manual truth / editable AI result 的 region → 打开或在 3D 中定位 → 外部 prediction 导入或批量接受 → 经 truth promotion guard 写入受控角色并刷新。

## Backend Panel 状态与信号

- 新增 `TifBackendPanelState`，唯一保存后台 thread/worker/task/action、进度、run/result 路径、pending selection、保存后待启动动作、训练结果摘要/模型路径和 prediction 选择状态。
- Shell 删除全部 Backend/Training/Predict 默认状态副本；Widget 同名 descriptor 仅作 Stage 9 前定向兼容代理，不产生第二份存储。
- Backend controller 继承 `QObject`，完整接管任务启动、进度、完成、失败、取消、线程清理、训练结果摘要、模型登记和保存后恢复。
- 训练样本诊断、排除原因、模型库和 prediction target 选择归 Backend controller；样本资格继续由 `TifBackendWorkflowService` 和 project/core 判断。
- 21 条 Backend 控件信号经 Signal Router 直接绑定，重复 `bind_signals()` 保持 21 条，不累积连接。

## Result Review 状态与信号

- 新增 `TifResultReviewState`，唯一保存 refreshing、stale、opening target 和 region mask cache。
- 结果 source、region、比较表、3D 定位、外部 prediction 导入和批量接受归 `TifResultReviewController`。
- 9 条 Result Review 信号经 Signal Router 直接绑定，旧 radio/tab/button Widget slot 已删除。
- 打开结果和接受后重选目标统一调用 Selection workflow command，不再直接操作树控件私有入口。
- Result Review 不读取 Backend controller 的内部 state，批量选择通过 `selected_predict_refs()` 公共查询命令。

## 数据安全与失败恢复

- 训练选择继续只接收 service 判定为 train-ready 的样本；训练诊断明确解释 manual truth、schema、shape 和 reslice 缺口。
- prediction 与外部 TIF 只写 editable review/raw prediction 路径，不写 manual truth。
- AI 接受必须调用 `truth_promotion_service.promote_reviewed_refs(..., save=True)`。
- Backend write lock、异步保存后再启动、覆盖 editable result 提示、取消和失败时 run/result 路径保留均有测试。
- 后台完成继续使用 task context 判断是否刷新/重选当前目标；旧任务不会无条件抢回焦点。

## 测试迁移

新增 `tests/test_tif_result_review_controller.py` 5 条直接合同：

- 9 条信号幂等与 state 唯一。
- 打开目标必须走 Selection command。
- AI 接受必须走 truth promotion service。
- 外部 prediction 导入保持 manual truth 不变。
- controller 无跨工作流 state 读取且小于 3,000 行。

扩展 `tests/test_tif_backend_panel_controller.py`：Backend 21 条信号幂等、运行时 state 唯一，以及既有样本资格、模型库、运行锁和结果控件测试。旧 Widget backend/result 测试 seam 已迁到对应 controller。新 Result Review 测试已登记到 `scripts/run_validation_suite.py` 和架构 GUI key-path 分组。

## 全层自动门

- `tif_core`：82
- `tif_storage_safety`：16
- `tif_services`：24
- `tif_preview_export`：106
- `tif_workbench`：275
- `tif_layout`：5
- `tif_architecture_round3`：2
- `gui_smoke`：94
- `ui_polish`：83

合计 687 条全部通过。

## 架构指标

| 指标 | Stage 7 | Stage 8 |
| --- | ---: | ---: |
| 主文件物理行数 | 7,932 | 6,738 |
| Widget 方法数 | 427 | 367 |
| 薄方法数 | 186 | 180 |
| 主文件 `.connect()` | 96 | 56 |
| 私有测试引用次数 | 392 | 372 |
| Backend controller | 510 | 1,327 |
| Result Review controller | 0 | 707 |

两个 controller 都低于 3,000 行硬限制；主文件连接数已低于 Stage 9 的 80 条目标。方法数和薄 wrapper 仍未达 Stage 9 门槛，因此不能把 Stage 8 的行数下降当成第三轮最终完成。

## 需求方向复核

- Panel controller 负责训练样本诊断、模型库和 backend action：通过源码边界与直接测试证明。
- Result Review 负责结果比较、region、批量选择、接受和外部导入：通过 controller 直接测试与 GUI key-path 证明。
- 数据角色、shape、promotion 和 backend contract 未复制到 UI controller：继续调用 service/core。
- 训练、预测、结果信号直连责任主体：主文件无对应直接 `.connect()`。
- training/prediction/result controller 之间无内部 state 读取。
- 真实模型运行、真实外部 prediction TIF、角色来源人工核对：留 Stage 10，不伪造结论。

## 阶段结论

Stage 8 自动门、架构门和需求方向通过，记为 `accepted`。进入 Stage 9：Coordinator、兼容清理与主 Widget 收束。
