# TIF 工作台架构整理第三轮需求文档

日期：2026-07-10

状态：`accepted`；Stage 0-10 全部完成，用户已确认 Local Axis 解剖方向和 Dataset601 脑区边界合理

第一轮基线：`346598b`；第二轮候选合并：`1435751`

## 当前状态

`AntSleap/ui/tif_workbench.py` Stage 0 统一按物理行统计为 14,234 行（此前约 13,482 是 PowerShell 管道的非空行口径），由 `TifWorkbenchWidget` 继续担任公开 PySide 入口和中央协调器。前两轮已经拆出翻译、弹窗、画布、worker、helper、layout、训练/预测面板、Preview 部分策略、Local Axis 部分状态、样式和 Agent context，也将重要数据安全规则下沉到 core/service/task 层。

现在的问题不再是“完全没有分层”，而是主 Widget 仍同时协调多个完整研究工作流：

- specimen / part / reslice 选择和项目生命周期。
- 2D 标签编辑、自动保存、手动保存和 manual truth 提升。
- ROI 草稿、关键切片、确认 part 和 mask 初始化。
- part mask / material 编辑、预览、接受和保存。
- 2D/3D preview、GPU/CPU fallback、overlay 和资源状态。
- Local Axis 三点交互、overlay、重切片和 manifest 导出。
- 训练、预测、结果比较、AI 结果接受和外部预测导入。

发布基线 `1435751` 的主文件为 14,234 物理行。Stage 0 初始审计曾记录约 664 个方法、251 处 Qt `.connect(...)` 和约 147 个不超过 4 行的方法；这些指标描述的是第三轮迁移前的架构耦合。计划复核期间曾记录 8,817 行的半迁移快照；Stage 10 最终状态为 5,057 行、221 个 Widget 方法、39 个不超过 4 行的方法和 11 处 `.connect()`。历史快照用于解释迁移过程，最终验收以 Stage 10 指标、测试、信号和研究安全闭环为准。

现有测试大量直接访问 Widget 私有方法和字段，阻止新 controller 真正成为受测责任主体。第三轮必须为每个阶段分别记录发布基线、阶段起点和阶段终点，并以状态、信号、测试和研究安全闭环判断完成，不能只以行数下降判断。

## 第三轮总目标

第三轮按完整研究工作流拆分，而不是继续零散移动 helper。每个工作流必须有清晰的：

- controller 入口和状态所有者。
- Qt 信号连接范围。
- service/core/task 调用边界。
- 错误、恢复和用户提示出口。
- controller 直接测试与关键 GUI 集成测试。
- 旧 Widget 兼容入口退场条件。

最终 `TifWorkbenchWidget` 主要负责：创建顶层工作台、注册控制器、持有稳定 view 接口、协调少量跨工作流事件、显示顶层消息和保留少量明确公开入口。

## 研究工作流原则

- 自动保存和旧后台回调不能覆盖研究者随后完成的新编辑。
- 保存结果必须明确是 working edit、manual truth 或其他受控角色。
- ROI 确认必须创建正确 part，并保持 shape、坐标轴和来源可审计。
- part mask 草稿、预览和正式写入必须明确区分。
- Preview 资源失败不能被误报为 TIF 数据损坏。
- Local Axis 旧导出不能抢回当前 specimen/part/reslice。
- AI 结果接受不能绕过 manual truth 和 raw prediction 保护规则。
- 项目关闭、切换目标和后台训练时，未保存内容与写锁状态必须可解释。

## 非目标

- 不修改 TIF 项目格式、SQLite schema、label sidecar、reslice manifest 或训练契约。
- 不重新设计训练算法、Local Axis 数学或 GPU renderer。
- 不把其他类群泛化作为本轮默认产品目标。
- 不为压行数删除安全 guard、错误摘要、审计 metadata 或恢复入口。
- 不一次性重写全部工作流。
- 不长期保留“新代码存在，但测试和信号仍只走旧 Widget”的双轨状态。
- 不把 `tests/test_tif_workbench.py` 机械拆成多个同样耦合私有字段的大文件。

## 目标架构

### 1. Workbench Shell / View / Signal Router

建议新增 `tif_workbench_shell.py`、`tif_workbench_view.py`、`tif_workbench_signal_router.py`。

将 `__init__` 中状态初始化、控制器注册、布局创建和信号绑定分开。控制器只获得本工作流所需的 view 接口，不默认获得整个 Widget 的任意私有访问权。Signal router 按工作流登记、审计和解除连接，防止项目重开或 controller 重建造成重复触发。

### 2. Selection / Project Lifecycle

建议新增 `tif_selection_workflow_controller.py` 和 `tif_project_lifecycle_controller.py`，扩展现有 `services/tif_selection_controller.py`。

完整负责：打开/关闭项目、刷新 specimen tree、切换 specimen/part/reslice、切换前未保存确认、旧任务作废、恢复当前上下文状态。Selection 决定唯一研究上下文，各工作流订阅上下文事件，不再由 Widget 手工调用几十个刷新方法。

### 3. Annotation / Save / Truth

建议新增 `tif_annotation_workflow_controller.py`，继续使用并扩展 `tif_label_edit_service.py`、`tif_truth_promotion_service.py`。

完整负责：working edit 加载、brush/contour 编辑、dirty tracking、自动保存快照与 generation/token、手动保存、失败恢复、manual truth 提升、切换/关闭/训练前未保存确认。edit volume、dirty slices 和 save 状态只能有一个可写所有者。

### 4. ROI-to-Part

建议新增 `tif_roi_workflow_controller.py`，扩展 `tif_roi_part_service.py`。

完整负责：ROI 草稿、关键切片、插值外壳、保存/取消/恢复、同步或后台确认、创建 part、初始化 accepted mask、完成后选择和旧任务拒绝。几何与写入请求由 service 验证，controller 负责用户动作与 task context。

### 5. Part Mask / Material

建议新增 `tif_part_mask_workflow_controller.py`；现有 service 不足时再新增 `services/tif_part_mask_service.py`。

完整负责：material schema、关键切片、复制/插值/清除/contour、后台 mask preview、接受/取消、正式保存和 metadata-only materialize。必须明确 draft、preview、accepted/editable 三种状态，preview 不能自动成为 manual truth。

### 6. Volume Preview / Rendering

扩展 `tif_preview_controller.py`，必要时新增 `tif_volume_render_controller.py`，继续使用 `tif_volume_preview_service.py`。

完整负责：2D/3D 显示参数、volume/mask/ROI source、still/drag 请求、cache、取消、过期结果、GPU texture、CPU fallback、资源提示和 overlay 汇总。Annotation、ROI、Part Mask、Local Axis 通过稳定 overlay provider 提供快照，Preview 不拥有其业务状态；renderer 数学与 workflow 协调保持分离。

### 7. Local Axis / Reslice

扩展 `tif_local_axis_controller.py`；规模需要时新增 `tif_local_axis_export_controller.py`。

完整负责：三点和 roll reference、slice/volume hit test、拖动、overlay、摘要、真实 reslice worker 生命周期、完成后选择、旧任务拒绝和 training manifest。第二轮遗留在 Widget 中的 overlay、导出和信号必须一起迁移。

### 8. Training / Prediction / Result Review

保留并收束 `tif_backend_panel_controller.py`，新增 `tif_result_review_controller.py`。

Panel controller 负责训练样本诊断、模型库和 backend action；Result review 负责结果比较、region、批量选择、接受、外部 prediction TIF 导入。数据角色、安全提升和 backend contract 继续由 service/core 决定。

### 9. Cross-workflow Coordinator

建议新增 `tif_workbench_coordinator.py`，只处理真正跨工作流的规则：selection 刷新顺序、未保存编辑是否阻止切换/训练、backend write lock、preview busy 与 Local Axis 点选关系、顶层状态栏和 Agent context 更新。Coordinator 不得重新变成第二个巨型 Widget。

## 信号连接迁移要求

第三轮必须把 Qt 信号连接当作架构的一部分，而不是搬完方法后继续连接旧 Widget wrapper。

1. 每个工作流有显式 `bind_signals()` / `unbind_signals()`，或由统一 signal router 注册。
2. 工作流接管后，相关 signal 直接连接 controller slot 或 coordinator command。
3. 不长期保留 `button.clicked -> Widget wrapper -> Controller` 空转链路。
4. 临时 wrapper 必须登记调用方、测试依赖和删除阶段。
5. 防止项目重开、语言刷新或 controller 重建造成重复连接。
6. 测试必须证明关键按钮一次点击只触发一次研究动作。
7. controller/Widget 销毁后，后台信号不能写入旧界面。
8. objectName、快捷键、tab 顺序和翻译刷新保持不变，除非另行确认。

## 测试迁移要求

### 测试分层

1. **Core / Service**：数据角色、路径、shape、guard 和纯业务结果。
2. **Workflow Controller**：使用小型 fake view、fake task adapter 和明确 state，直接验证完整动作与状态转换。
3. **Signal Contract**：验证控件连接目标、单次触发、解除连接和跨工作流事件顺序。
4. **GUI Key-path**：只保留研究者真实操作路径，如自动保存、ROI 确认、mask 预览接受、Local Axis 导出、训练后预测入口和 AI 结果接受。

### 旧测试迁移规则

- 每拆一个工作流，先建立 controller 直接测试，再迁移 Widget 私有测试。
- 新测试不得通过 `widget._private_field = ...` 构造 controller 内部状态。
- 需要控制状态时，使用公共 command、state dataclass、fake dependency 或明确 test seam。
- Widget wrapper 只做过渡测试，不得成为新测试默认入口。
- 旧测试分类为：保留 GUI 集成、迁移 controller、迁移 service、删除重复覆盖。
- `tests/test_tif_workbench.py` 最终只覆盖 shell、coordinator 和少量端到端路径。
- 每阶段同步 `scripts/run_validation_suite.py` 和 `tests/tif_architecture_test_groups.py`。

## 兼容入口退场策略

每个旧 Widget 方法登记为：

- **公开兼容入口**：外部模块确实调用，保留稳定语义。
- **信号兼容入口**：仅旧 `.connect()` 使用，信号迁移后删除。
- **测试兼容入口**：仅旧测试使用，新测试落地后删除。
- **内部重复入口**：调用点迁移后立即删除。

删除前必须通过 `rg` 或 AST 清单确认无调用方，不能只因方法很短就删除。

## 量化目标

- `tif_workbench.py` 从 14,234 物理行下降到 **7,500-9,000 行**。
- 主 Widget 方法数从约 664 降到 **350 以下**。
- 主文件 `.connect(...)` 从约 251 降到 **80 以下**。
- 4 行以内 wrapper 从约 147 降到 **40 以下**，剩余项均有公开兼容理由。
- `__init__` 降到 **300 行以内**。
- `_build_layout` 降到 **250 行以内**或完全移出。
- 不新增超过 3,000 行的单一 controller。
- 单个 workflow controller 建议 800-1,500 行；超过 1,500 行必须复核边界。

这些是结构验收线，不得通过删除错误处理、翻译、审计信息或测试达成。

## 建议迁移顺序

1. Shell / View / Signal Router 与迁移台账。
2. Selection / Project Lifecycle。
3. Annotation / Save / Truth。
4. ROI-to-Part。
5. Part Mask / Material。
6. Volume Preview / Rendering。
7. Local Axis / Reslice。
8. Result Review 与 Backend panel 收束。
9. Coordinator、wrapper 清理和主 Widget 收束。

先拆 Selection，因为所有工作流依赖 specimen/part/reslice 上下文；随后拆 Annotation 保存，因为 ROI、mask、训练和项目关闭都依赖未保存状态。

## 数据安全与恢复要求

- 后台结果必须带 task id 和 project/specimen/part/reslice/source role 等上下文。
- 旧任务不得刷新新选择或写入新上下文。
- 保存、ROI 确认、mask 接受、truth promotion、预测导入和 reslice 导出继续经过现有 service/core guard。
- 自动保存失败必须保留 dirty 状态和重试入口。
- 项目关闭必须明确处理未保存编辑和运行中的写任务。
- 资源不足与数据损坏继续分开提示。
- 临时验证文件只放 `.tmp_validation/`，结束前清理。

## 文档与审计

- 每阶段新增 `tif_workbench_architecture_refactor_round3_stageN_review_zh.md`。
- 每份记录列出迁移的方法、信号、测试、保留 wrapper、行数变化和研究流程影响。
- 每阶段记录主文件行数、方法数、`.connect()` 数和薄 wrapper 数。
- 中间阶段不更新根目录 `CHANGELOG_zh.md` 或 `LLM_CONTEXT_DETAILED.md`。
- 用户确认整体候选状态，或不同步会造成危险指导时，再同步根文档。

## 成功标准

- Annotation、ROI、Part Mask、Preview、Local Axis、Result Review 至少五个完整工作流有独立 controller 和直接测试。
- Selection / Project Lifecycle 成为唯一上下文入口。
- Qt 信号主要连接新责任主体，不再依赖 Widget 薄包装。
- `tests/test_tif_workbench.py` 不再是所有 TIF UI 行为的唯一主要测试入口。
- controller 测试无需完整 Widget 私有状态即可验证状态转换。
- manual truth、raw prediction、原始 TIF、reslice 和训练数据安全无回退。
- 主文件达到量化目标；未达到项必须逐条说明真实调用依赖，不能只写“风险较高”。
- 自动化验证通过，用户完成真实 TIF/GPU 人工验收。
- 每个 Stage 都有 `planned → candidate → verified → accepted` 的明确证据；计划确认、局部测试通过或既有候选 review 均不得代替阶段验收。

## 需要用户确认的问题

1. 是否同意目标行数为 7,500-9,000，而不是一次降到 5,000 以下？
2. 是否同意迁移顺序为 Selection → Annotation/Save → ROI → Part Mask → Preview → Local Axis → Result Review？
3. 是否同意旧 Widget 私有方法只作阶段性兼容，新测试直接对接 controller/service？
4. 是否同意 controller/signal router 接管控件信号后，删除仅用于转发的 Widget slot？
5. 是否同意每个工作流形成可回退阶段，不做一次性大爆炸重写？
6. 是否同意本轮不修改数据格式和训练算法，严格限定在 UI 工作流、任务协调、信号和测试结构？
7. 第三轮候选版本是否继续作为 2.x 架构整理版本？版本号不影响 Stage 0。

## 用户确认结果（2026-07-10）

1. 接受最终主文件低于原 7,500–9,000 建议区间；拆出代码都有明确责任主体和全层测试，不人为回填。
2. 接受完整研究工作流迁移顺序和 Stage 0-10 分阶段执行结果。
3. 接受新测试直接对接 controller/service，Widget 私有入口仅保留必要兼容。
4. 接受 signal router/controller 接管信号并删除纯转发 slot。
5. 接受分阶段可回退迁移，而非一次性重写。
6. 确认本轮未修改数据格式、训练算法、Local Axis 数学或 renderer 数学。
7. 用户确认真实头部 Local Axis 解剖方向符合，Dataset601 脑区边界合理，第三轮候选最终 accepted。
