# TIF 工作台架构整理执行清单

日期：2026-07-08

分支：`codex/tif-workbench-architecture-refactor`

关联需求文档：`docs/tif_workbench_architecture_refactor_requirements_zh.md`

## 执行原则

- 本分支以长期维护收益最大化为目标，允许较大架构调整。
- `main` 分支保持稳定，本分支测试通过后再合并。
- 每个阶段都要有明确验收标准，不把多个高风险变化混在一次提交里。
- 保留 `TifWorkbenchWidget` 作为长期外部入口，内部逐步变薄。
- 新增 `AntSleap/services/` 作为 UI 与 core 之间的流程组织层。
- 优先服务蚂蚁三维 TIF 研究流程，不在本轮主动扩大到其他类群泛化。
- 所有涉及研究数据写入的规则必须有核心层入口和单元测试。
- 用户可见文案继续保持中英双语能力。

## 阶段 0：基线和重构护栏

目标：先固定当前可用行为，避免后续不知道是重构破坏了流程，还是原本就不稳定。

基线记录：`docs/tif_workbench_architecture_refactor_stage0_baseline_zh.md`

### 任务

- [x] 记录当前最大文件、核心类、测试分布和 TIF 工作流入口。
- [x] 跑一轮当前 TIF 相关测试，记录基线结果。
- [x] 建立本分支的阶段性验收命令清单。
- [x] 标记 `tif_workbench.py` 内部职责区块：translations、dialogs、canvas、workers、layout、selection、ROI、label edit、backend、preview、local axis。
- [x] 列出所有后台任务及其现有 token/context/busy lock 逻辑。
- [x] 列出所有会写项目数据的入口。
- [x] 列出当前 IO / Project 层入口：volume sidecar、JSON/SQLite、输出目录、训练/预测 run 目录。
- [x] 记录当前 GUI 验证缺口：最初 base Python 环境缺少 `PySide6`，`tests/test_tif_workbench.py` 曾全部跳过；后续已改用 TaxaMask 环境真实执行 GUI 测试。

### 验收

- [x] 有一份当前结构地图。
- [x] 有一份测试基线记录。
- [x] 后续阶段知道哪些文件和流程必须重点保护。
- [x] 已对照需求文档复核阶段 0 方向，并记录阶段 1 前需要关注的验证缺口。

### 建议测试

```powershell
python -m pytest tests/test_tif_project.py tests/test_tif_backend.py tests/test_tif_prediction_import.py
python -m pytest tests/test_tif_roi_preview.py tests/test_tif_volume_preview.py
python -m pytest tests/test_tif_workbench.py
```

## 阶段 1：可见结构拆分

目标：先把低耦合内容从巨型工作台文件拆出，保持程序行为不变。

阶段 1 前置验证缺口：

- [x] 已定位 TaxaMask GUI 运行环境：`C:\Users\admin\anaconda3\envs\taxamask\python.exe`。
- [x] 已确认 TaxaMask 环境能导入 `AntSleap.ui.tif_workbench`。
- [x] TaxaMask 环境虽然没有 `pytest`，但已使用 `python -m unittest tests.test_tif_workbench` 在 GUI 环境真实执行。
- [x] 已确认在 `PySide6` 或 GUI pytest 不可用时，`tests/test_tif_workbench.py` 的 `skipped` 不能被视为 GUI 通过。
- [x] 已额外执行静态编译、TaxaMask 环境 GUI 导入/实例化检查、核心测试，并在 Stage 4-6 用 `taxamask` 环境跑过完整 GUI 回归。

### 新增或调整文件

- [x] `AntSleap/ui/tif_workbench_translations.py`
- [x] `AntSleap/ui/tif_workbench_dialogs.py`
- [x] `AntSleap/ui/tif_workbench_canvas.py`
- [x] `AntSleap/ui/tif_workbench_workers.py`
- [x] `AntSleap/ui/tif_workbench_helpers.py`
- [x] `AntSleap/ui/tif_workbench_layout.py` 已评估并明确延后，不在本轮创建。

### 任务

- [x] 移出翻译表和 `tt()`。
- [x] 移出训练结果弹窗、材料弹窗、part 命名弹窗等 dialog。
- [x] 移出 `TifSliceCanvas`、`TifVolumeCanvas`、wheel-safe 控件等 UI 小类。
- [x] 移出 worker 类，但暂时保持 worker 行为和信号结构不变。
- [x] 移出 ROI/mask 相关纯函数。
- [x] 评估并逐步移出纯 UI layout 构建函数，避免 `tif_workbench.py` 继续承担大型控件装配细节。
- [x] 保持 `AntSleap/ui/tif_workbench.py` 对外导入入口不变。
- [x] 修复 import，避免循环依赖。
- [x] 每拆一个模块跑对应测试。

阶段 1 layout 结论：已评估 `_build_layout()`，但暂缓创建 `tif_workbench_layout.py`。原因是当前 layout 与控件初始化、信号连接和状态属性强绑定；更适合在 Stage 3 service/controller 与 Stage 4 状态对象初步落地后再拆，详见 `docs/tif_workbench_architecture_refactor_stage1_review_zh.md`。

### 验收

- [x] `TifWorkbenchWidget` 能正常导入和实例化。
- [x] 原有按钮、弹窗、canvas、worker 信号行为不变。
- [x] `tif_workbench.py` 行数明显下降。
- [x] GUI 测试不因为 import 或对象名变化失败。

### 建议测试

```powershell
python -m pytest tests/test_ui_localization.py tests/test_window_geometry.py
python -m pytest tests/test_tif_workbench.py
python -m pytest tests/test_tif_gpu_volume_canvas.py
```

## 阶段 2：核心安全规则下沉

目标：把保护研究数据的规则从 UI 方法里移到 core，确保任何入口都不能绕过。

### 新增或调整文件

- [x] `AntSleap/core/tif_label_guard.py`
- [x] `AntSleap/core/tif_write_guard.py`
- [x] `AntSleap/core/tif_truth_policy.py`
- [x] `AntSleap/core/tif_prediction_policy.py`
- [x] `tests/test_tif_label_guard.py`
- [x] `tests/test_tif_write_guard.py`
- [x] `tests/test_tif_truth_policy.py`
- [x] `tests/test_tif_prediction_policy.py`

### 任务

- [x] 定义 label role 写入矩阵：`working_edit`、`editable_ai_result`、`raw_ai_prediction_backup`、`manual_truth`。
- [x] 定义 `manual_truth` 只能由明确核验动作生成的 guard。
- [x] 定义预测导入只能进入待核验层和 raw backup 的 guard。
- [x] 定义 `raw_ai_prediction_backup` 只读审计规则，避免任何编辑入口把它当作可修改标签层。
- [x] 定义外部预测导入 shape、dtype、上下文校验策略。
- [x] 定义 source overwrite guard，防止覆盖原始 TIF 或非目标输出。
- [x] 定义大规模写入 intent：目标路径、来源 role、目标 role、审计 metadata、是否允许覆盖。
- [x] 明确 IO / Project 边界：项目文件、volume sidecar、JSON/SQLite、输出目录必须通过受控 project/core 接口写入。
- [x] 将 UI 中对应判断逐步替换为 core guard 调用。
- [x] 所有 guard 返回结构化结果：`allowed`、`reason`、`message_key`、`details`。

### 验收

- [x] 训练只使用 `manual_truth` 的规则在 core 层可测试。
- [x] 预测导入不覆盖 `manual_truth` 的规则在 core 层可测试。
- [x] raw backup 只读和审计 metadata 的规则在 core 层可测试。
- [x] 原始 TIF、非目标输出和历史 run 结果不会被无意覆盖。
- [x] UI 不再独自决定关键数据安全规则。
- [x] 新入口必须调用 guard 才能写研究数据。

### 建议测试

```powershell
python -m pytest tests/test_tif_project.py tests/test_tif_backend.py tests/test_tif_prediction_import.py
python -m pytest tests/test_tif_label_guard.py tests/test_tif_write_guard.py tests/test_tif_truth_policy.py tests/test_tif_prediction_policy.py
```

## 阶段 3：Service / Controller 层

目标：把完整研究动作从 Widget 方法里抽出，让 UI 只负责触发和呈现。

### 新增目录和文件

- [x] `AntSleap/services/__init__.py`
- [x] `AntSleap/services/tif_selection_controller.py`
- [x] `AntSleap/services/tif_label_edit_service.py`
- [x] `AntSleap/services/tif_truth_promotion_service.py`
- [x] `AntSleap/services/tif_roi_part_service.py`
- [x] `AntSleap/services/tif_backend_workflow_service.py`
- [x] `AntSleap/services/tif_volume_preview_service.py`
- [x] `AntSleap/services/tif_local_axis_service.py`

### 任务

- [x] 抽 `TifSelectionController`：当前 specimen、part、reslice、label role、display mode。
- [x] 抽 `TifLabelEditService`：加载编辑层、dirty slices、保存请求、保存结果处理。
- [x] 抽 `TifTruthPromotionService`：单个和批量接受 AI 结果为训练真值。
- [x] 抽 `TifRoiPartService`：ROI 草稿、keyframe、mask preview、确认创建 part。
- [x] 抽 `TifBackendWorkflowService`：训练/预测前置检查、样本选择、manifest 选择、结果注册。
- [x] 抽 `TifVolumePreviewService`：preview request、cache key、mask preview、ROI budget。
- [x] 抽 `TifLocalAxisService`：local axis draft、roll reference、reslice payload。
- [x] UI 方法改为薄包装：收集输入、调用 service、刷新界面。
- [x] service 返回结构化结果和下一步动作建议，由 UI 决定消息框、状态栏、按钮刷新和日志呈现。
- [x] service 不直接拼接危险输出路径；涉及写入时调用 project/core guard 或 project manager。

### 验收

- [x] service 不直接依赖 PySide 控件。
- [x] service 能在无 GUI 测试中运行或模拟。
- [x] GUI 测试数量可以减少对内部细节的依赖。
- [x] `TifWorkbenchWidget` 中核心业务方法明显缩短。

### 建议测试

```powershell
python -m pytest tests/test_tif_project.py tests/test_tif_backend.py tests/test_tif_prediction_import.py
python -m pytest tests/test_tif_workbench.py
```

新增测试建议：

- [x] `tests/test_tif_selection_controller.py`
- [x] `tests/test_tif_label_edit_service.py`
- [x] `tests/test_tif_truth_promotion_service.py`
- [x] `tests/test_tif_roi_part_service.py`
- [x] `tests/test_tif_backend_workflow_service.py`
- [x] `tests/test_tif_volume_preview_service.py`
- [x] `tests/test_tif_local_axis_service.py`

阶段 3 复核结论：已完成 service/controller 第一轮落地。UI 仍保留 `TifWorkbenchWidget` 外部入口，但 label save、truth promotion、ROI part 创建、backend 样本选择、volume/mask preview request、local axis draft/frame/reslice payload 等关键动作已通过 service 组织。完整复核见 `docs/tif_workbench_architecture_refactor_stage3_review_zh.md`。

## 阶段 4：统一任务管理和状态对象

目标：降低后台任务、旧回调、隐式状态导致的连锁故障。

### 新增或调整文件

- [x] `AntSleap/core/tif_task_context.py`
- [x] `AntSleap/core/tif_task_state.py`
- [x] `AntSleap/ui/tif_tasks.py`
- [x] `AntSleap/services/tif_task_manager.py`

### 状态对象

- [x] `TifSelectionState`
- [x] `TifEditState`
- [x] `TifPreviewState`
- [x] `TifBackendState`
- [x] `TifRoiState`
- [x] `TifLocalAxisState`

### 任务

- [x] 定义统一 task context：specimen、part、reslice、label role、display mode、request key。
- [x] 定义统一 task result：task id、status、context、payload、error、started_at、finished_at。
- [x] 定义统一 busy lock：保存、ROI 创建、训练、预测、local axis export、preview build。
- [x] 第一批纳入 task manager：label save、ROI 创建、backend train/predict、volume preview build。
- [x] 第二批纳入 task manager：TIF import、Amira import、materialize、local axis export、mask preview。
- [x] 所有异步回调先做 context match，再允许刷新 UI 或写状态。
- [x] 取消任务后必须恢复控件状态并保留可读错误/取消原因。

### 验收

- [x] 用户切换 specimen / part 后，旧任务结果不会刷新错误界面。
- [x] 后台任务失败后 busy lock 能恢复。
- [x] 重复点击不会重复启动冲突任务。
- [x] 保存队列、训练队列、预览队列不会互相死等。
- [x] task 状态可被 agent context 或日志摘要读取。

### 建议测试

```powershell
python -m pytest tests/test_tif_task_context.py tests/test_tif_task_state.py
python -m pytest tests/test_tif_workbench.py
```

阶段 4 复核结论：已完成统一 task manager、task context/state、busy lock 与状态摘要第一轮落地。label save、truth promotion、ROI 创建、backend train/predict、TIF/Amira import、materialize、Local Axis export、volume preview、mask preview 已纳入统一任务账本；旧回调写 UI 前增加 context/path/token 检查。完整复核见 `docs/tif_workbench_architecture_refactor_stage4_review_zh.md`。

## 阶段 5：测试分层和回归清理

目标：把测试从过度依赖 GUI，调整为 core/service/unit 与 GUI 关键路径组合。

### 任务

- [x] 将纯业务规则测试移到 core/service 单元测试。
- [x] GUI 测试保留关键用户路径和控件集成。
- [x] 删除或改写过度依赖内部实现细节的脆弱测试。
- [x] 增加真实研究流程 smoke tests。
- [x] 建立 TIF 架构回归测试分组。

### 必须覆盖的研究安全测试

- [x] 预测导入不会覆盖 `manual_truth`。
- [x] `raw_ai_prediction_backup` 只用于审计。
- [x] 未核验结果不能进入训练。
- [x] 保存失败不会清空 dirty 状态。
- [x] 旧任务结果不会写入当前切换后的 part。
- [x] ROI 输出 shape 与 bbox 一致。
- [x] 训练样本选择只使用可训练样本。
- [x] Local Axis export 不在后端写锁期间执行。

### 必须保留的 GUI 关键路径

- [x] 打开 TIF 工作台。
- [x] 导入 TIF / Amira。
- [x] 创建 part。
- [x] 保存标注。
- [x] 接受训练真值。
- [x] 准备训练数据。
- [x] 训练完成后进入预测。
- [x] 预测导入后进入核验。
- [x] GPU preview fallback。

阶段 5 复核结论：已建立 TIF 架构回归测试分组，明确 core safety、service/task、preview/export、GUI key path 与 research smoke 的边界；必须覆盖的研究安全项均映射到现有或新增测试证据。完整复核见 `docs/tif_workbench_architecture_refactor_stage5_review_zh.md`。

## 阶段 6：文档、版本和合并准备

目标：让架构升级成为一个清晰版本节点，而不是一堆难追踪的内部改动。

### 任务

- [x] 更新 `README.md` 中与 TIF 工作流入口或平台支持相关的公开说明。
- [x] 如果行为变化较大，更新 `CHANGELOG_zh.md`。
- [x] 如果架构状态需要交接，更新 `LLM_CONTEXT_DETAILED.md`。
- [x] 准备版本说明，建议版本号：`2.3.0` 或 `2.4.0`。
- [x] 跑完整测试或至少 TIF 相关完整测试。
- [x] 确认 `tests/test_tif_workbench.py` 不再因为缺少 `PySide6` 全部跳过，或已在项目实际 GUI 环境完成等价验证。
- [x] 检查 `git status --short`，确认没有运行输出、模型权重、数据库、临时文件被纳入。
- [x] 在本地提交阶段性里程碑。
- [x] 合并回 `main` 前做最终 smoke test。

### 建议最终测试

```powershell
python -m pytest tests/test_tif_project.py tests/test_tif_backend.py tests/test_tif_prediction_import.py
python -m pytest tests/test_tif_roi_preview.py tests/test_tif_volume_preview.py tests/test_tif_gpu_volume_canvas.py
python -m pytest tests/test_tif_local_axis_reslice.py tests/test_tif_workbench.py
python -m pytest tests/test_gui_smoke.py tests/test_ui_localization.py
```

## 阶段性提交建议

- [x] `记录 TIF 工作台架构整理需求与执行清单`
- [x] `拆分 TIF 工作台翻译弹窗与画布模块`
- [x] `集中 TIF 标签写入与训练真值保护规则`
- [x] `抽离 TIF 标签保存与真值接受服务`
- [x] `抽离 TIF ROI 与后端流程服务`
- [x] `统一 TIF 后台任务上下文与状态管理`
- [x] `补充分层测试并准备 TIF 架构升级版本`

## 最终成功标准

- [x] `tif_workbench.py` 不再承担多数业务规则。
- [x] 新增功能优先进入 service/core/task 层，而不是继续堆到 Widget。
- [x] 研究数据安全规则有集中入口和单元测试。
- [x] 后台任务有统一生命周期管理。
- [x] 主要 TIF 工作流可以通过分层测试定位问题。
- [x] 未来支持批处理、WebUI、本地 API 或更多训练后端时，不需要从 GUI 文件里大规模抽逻辑。

阶段 6 复核结论：已完成文档同步、候选版本说明、最终 TIF 架构验证和 git 状态检查。`README.md` 经复核无需修改，因为公开 TIF 入口、平台支持和用户工作流说明未改变；`CHANGELOG_zh.md`、`LLM_CONTEXT_DETAILED.md` 和 `docs/releases/2.4.0-tif-architecture-refactor_zh.md` 已同步。完整复核见 `docs/tif_workbench_architecture_refactor_stage6_review_zh.md`。

## 何时暂停并复核

以下情况需要暂停继续重构，先复核设计：

- [ ] 同一处逻辑必须同时改 UI、service、core、project 四层才能工作。
- [ ] 新 service 开始直接操作 PySide 控件。
- [ ] core guard 需要依赖当前按钮状态才能判断是否允许写入。
- [ ] 测试只能通过完整 GUI 才能验证一个核心安全规则。
- [ ] 任何流程可能让预测结果直接成为训练真值。
- [ ] 任何流程可能覆盖原始 TIF 或无法追溯输出来源。
