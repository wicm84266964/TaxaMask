# TIF 工作台架构整理第三轮总控计划

日期：2026-07-10

状态：计划已执行；Stage 0-10 候选完成，自动门与隔离真实数据闭环通过，等待用户完成可见验收

说明：本文保留的“冻结”“用户确认后实施”等措辞，是第三轮开始前采用的阶段控制规则；当前实际执行状态以 Stage 0-10 review、执行清单和人工验收卡为准。

关联文档：

- 需求边界：`docs/tif_workbench_architecture_refactor_round3_requirements_zh.md`
- 阶段清单：`docs/tif_workbench_architecture_refactor_round3_execution_checklist_zh.md`
- 方法台账：`docs/tif_workbench_architecture_refactor_round3_method_inventory.md`
- 测试台账：`docs/tif_workbench_architecture_refactor_round3_test_migration_zh.md`
- 信号台账：`docs/tif_workbench_architecture_refactor_round3_signal_migration_zh.md`

## 1. 本轮为什么不能只继续“搬代码”

前两轮已经把一部分 helper、service、worker 和 panel 拆出主文件，但 `TifWorkbenchWidget` 仍然同时掌管多个完整研究动作。一个方法即使被搬到新文件，如果控件信号仍先进入旧 Widget、测试仍直接修改 Widget 私有字段、状态仍在两边都可写，主文件就只是减少了局部代码，没有真正失去责任。

第三轮因此不以“每次删多少行”为唯一进度，而以一个研究工作流是否完整迁出为进度。一个工作流只有同时完成以下事项，才算真正拆出：

1. 研究动作有明确入口，例如“切换 specimen”“保存标注”“确认 ROI”“接受 mask”。
2. 工作流状态只有一个可写所有者，Widget 不再保留可独立修改的副本。
3. 相关 Qt 信号直接连接新 controller 或明确的跨工作流 command。
4. 数据写入继续经过既有 service/core/task 安全规则。
5. 后台结果带完整上下文，旧任务不能写入研究者后来选择的新对象。
6. controller 有直接测试，GUI 测试只保留真实关键操作路径。
7. 旧 Widget wrapper 有明确分类，并在调用方迁移后删除。

### 1.1 前两轮为什么做了两次优化，主文件仍然很大

统一按“文件中的物理行数”统计，第一轮基线 `346598b` 的 `tif_workbench.py` 为 15,353 行；发布基线 `1435751`（当前 `HEAD` 中该文件内容相同）为 14,234 行，净减少 1,119 行。期间曾拆出 layout、训练/预测 panel、Preview 策略和 Local Axis controller，但新增功能、兼容转发和状态镜像又把一部分行数补了回来。

2026-07-10 计划复核时，未提交工作树中的主文件为 8,817 物理行。这个数字是当时的第三轮候选草稿与半迁移快照，不是稳定基线。Stage 10 当前候选为 5,057 行；正式复核同时保留 `HEAD 发布基线`、计划快照和各阶段 review，禁止只报一个更小的数字。

前两轮行数没有继续明显下降，不是因为“没有拆文件”，而是拆分主要发生在外围结构，主 Widget 的责任闭环没有同步迁走：

1. **拆出了工具，没有拆出完整研究动作**：helper、dialog、worker、layout 可以移到别处，但“谁决定何时保存、保存谁、失败后如何恢复、结果回来后刷新谁”仍由 Widget 负责。
2. **状态仍有双份可写副本**：controller 保存一份状态，Widget 为兼容旧显示、旧测试或旧方法再保留一份；只要两边都能改，旧字段和同步代码就不能删除。
3. **Qt 信号仍先进 Widget 再转发**：按钮、快捷键、画布和 worker 回调即使最终调用 controller，只要中间保留 Widget slot，主文件仍要保存连接、包装方法和生命周期字段。
4. **测试锁定旧私有入口**：大量测试直接 patch 或调用 Widget 私有方法、直接写私有字段。为了不一次破坏测试，旧 wrapper 被长期保留，形成“新旧两套入口”。
5. **跨工作流规则与工作流内部规则混在一起**：selection、保存、ROI、mask、preview、reslice、训练结果都通过 Widget 互相调用，使任何一个局部 controller 都无法独立拥有完整闭环。
6. **功能增长抵消了结构减法**：第二轮同时增加安全 guard、资源提示、Agent context、训练/预测和 UI 完善；这些是有价值的功能，但说明不能只用净行数判断某次拆分是否真正完成。
7. **缺少严格退场门**：过去通常以“新文件已建立、测试已通过”为完成信号，没有强制要求重复状态、旧信号目标、旧测试 seam 和纯转发 wrapper 同阶段退出。

因此第三轮的核心不是把更多函数剪切到新文件，而是让每个研究工作流的状态、命令、Qt 信号、后台回调和直接测试一起迁走。只有旧入口确实退场，主文件行数才会形成不可逆的下降。

## 2. 当前工作树处置原则

当前工作树已经存在 Stage 0-7 的未提交候选实现，Stage 8 Result Review 也已出现未完成的半迁移代码。候选内容包括 Shell/View/Signal Router、Selection/Lifecycle、Annotation、ROI、Part Mask/Material、Volume、Local Axis、Result Review、测试、分析脚本以及对 `tif_workbench.py` 的大幅修改。这些内容在本计划确认前统一视为“未批准候选草稿”，不能自动视为用户已经接受的实施结果，也不能据此跳过需求核对。

2026-07-10 本次冻结时，架构脚本对当前工作树给出的快照为：主文件 7,353 行、Widget 方法 398 个、4 行以内薄方法 181 个、`.connect()` 90 处、测试私有引用 392 次。PowerShell `Get-Content | Measure-Object -Line` 对末尾换行的口径不同，显示 6,885；正式阶段统一以 `scripts/analyze_tif_workbench_architecture.py` 的 `splitlines()` 口径为准。这个快照说明主文件物理行数已经下降，但方法、薄包装、信号和测试耦合仍未达到收束目标，因此不得把“行数已小”解释为第三轮已经完成。

需求确认前执行以下冻结规则：

- 不继续修复、扩展或验证任何候选业务实现；尤其不继续当前 Stage 8 半迁移，也不提前进入 Stage 9。
- 不删除、覆盖或用破坏性 Git 命令回退现有候选草稿。
- 不把当前候选草稿提交为正式里程碑。
- 台账和 Stage review 中出现的“completed/已完成”在确认前只表示“候选实现曾达到当时的自动检查”，不代表正式阶段批准。
- 用户确认后，先对 Stage 0-7 和 Stage 8 半迁移状态做一次“按本计划重新审计”，再决定保留、修订或安全地重做局部内容。
- 若现有候选实现与本计划冲突，以用户确认后的本计划和需求文档为准。

## 3. 不可突破的研究数据边界

第三轮只调整 UI 工作流、状态归属、任务协调、信号和测试结构，不改变以下研究契约：

- 不修改 TIF 项目格式、SQLite schema、label sidecar、reslice manifest 和训练数据契约。
- 不修改训练算法、Local Axis 数学和 GPU renderer 数学。
- 原始 TIF 永不被编辑结果、mask materialize 或 prediction 覆盖。
- working edit、manual truth、raw prediction、accepted result 必须保持角色可区分、来源可追踪。
- 自动保存结果不能清除同一切片后来产生的新编辑。
- AI 结果和外部 prediction 不能绕过 truth promotion guard。
- ROI、mask、reslice 和保存后台任务不能把旧结果写到新 specimen、part 或 reslice。
- 资源不足、任务取消和数据损坏必须分别提示，避免研究者误判数据是否损坏。

## 4. 目标结构

最终 `TifWorkbenchWidget` 只负责：

- 创建顶层工作台和稳定的 view contract。
- 注册、启动和销毁各工作流 controller。
- 承担少量真正跨工作流的协调规则。
- 提供顶层消息、日志、翻译刷新和少量外部公开入口。

工作流 controller 负责本工作流的状态转换和界面命令；service/core/task 继续负责路径、shape、角色、写入 guard 和后台执行。Controller 不复制安全规则，也不通过获得整个 Widget 的任意访问权来形成新的大文件。

## 5. 每阶段统一执行模板

Stage 1-9 必须按同一顺序执行，不允许只搬方法后补测试：

1. **冻结行为基线**：记录当前研究动作、输入、输出、失败提示和恢复方式。
2. **定义状态所有者**：列出 controller 独占状态、只读共享状态和禁止复制状态。
3. **定义 view contract**：只暴露本工作流需要的控件读写接口。
4. **建立直接测试**：先用 fake view、fake service、fake task 验证状态转换。
5. **迁移业务入口**：将完整 command 和回调移入 controller。
6. **迁移 Qt 信号**：控件信号直接连接 controller；跨工作流事件连接 coordinator。
7. **迁移旧测试**：按台账迁到 controller、service 或保留为 GUI key-path。
8. **清理兼容层**：通过 `rg` 或 AST 确认调用方，再删除无意义 wrapper 和重复状态。
9. **分层验证**：先窄测试，再工作流 suite，再 GUI smoke/UI polish。
10. **Stage 复核**：记录方法、信号、测试、指标、风险和人工验收结果。

### 5.1 每个工作流必须同时交付的五张清单

| 清单 | 必须回答的问题 | 不满足时的处理 |
| --- | --- | --- |
| 研究动作清单 | 研究者从哪里进入、完成什么、得到什么文件或状态、失败后如何恢复？ | 不允许只按类名或文件名拆分 |
| 状态所有权清单 | 哪些状态唯一可写、哪些只读共享、哪些镜像必须删除？ | 存在双写即不得通过阶段 |
| 信号清单 | 控件、画布、快捷键、timer、worker 的最终 target 和解绑方式是什么？ | 仍经纯转发 Widget slot 必须登记并限期删除 |
| 测试清单 | 哪些迁到 controller/service，哪些保留 GUI key-path，哪些旧测试删除？ | 只补新测试、不迁旧 seam 不算完成 |
| 数据安全清单 | 写入角色、上下文快照、stale task、取消、失败恢复和重开如何验证？ | 任一 guard 回退立即停止阶段 |

### 5.2 阶段批准门

每个 Stage 采用五种状态，文档不得混用：

- `draft`：需求仍在讨论，业务代码冻结。
- `planned`：用户已确认本阶段需求、边界、信号和测试计划，可以开始实现。
- `candidate`：已有实现和局部测试，但尚未完成需求逐条复核或用户批准。
- `verified`：代码、状态、信号、测试、验证套件和人工检查均满足退出条件。
- `accepted`：用户确认本阶段可作为下一阶段基线。

状态顺序为 `draft → planned → candidate → verified → accepted`。只有 `accepted` 才能进入下一 Stage。自动测试全绿最多把阶段推进到 `verified`，不能替代用户对研究工作流和数据安全边界的确认。当前所有既有拆分和 review 均最多属于 `candidate evidence`，在本计划获批前不继承正式阶段结论。

阶段推进采用双门禁：

1. **自动门**：直接 controller/service 测试、所属工作流 suite、相邻安全 suite、信号契约、架构指标和 `py_compile` 全部通过。
2. **研究门**：本阶段对应的真实蚂蚁 TIF 操作已核对；涉及 GPU、重切片、训练或 prediction 的阶段必须明确记录尚未人工验证的部分。

任何阶段只要状态所有权、信号目标或旧测试 seam 仍未迁完，即使局部测试全绿，也只能保持 `candidate`。

### 5.3 工作流级交付矩阵

| Stage | 完整研究工作流 | 唯一状态所有者 | 必须直连的信号/回调 | 主要直接测试 | 研究产物与安全重点 |
| --- | --- | --- | --- | --- | --- |
| 1 | 工作台启动、顶层页面、关闭与解绑 | Shell registry/lifecycle | Start Center、Agent、日志、destroy | shell/view/router contract | 不改变研究数据，只保证界面生命周期稳定 |
| 2 | 打开项目、选择 specimen/part/reslice、切换与关闭 | Selection/Lifecycle | 树选择、项目打开/关闭、上下文广播 | selection/lifecycle controller + GUI switch | 旧任务不能写到后来选择的对象 |
| 3 | 标签编辑、undo/redo、自动/手动保存、truth promotion | Annotation | 工具、画布、快捷键、timer、save worker | revision/save/truth controller | working edit 与 manual truth 可追踪，新 revision 不被旧保存清除 |
| 4 | ROI 草稿、关键切片、确认 part、初始化 mask、选择新 part | ROI | bbox、画布 drag、保存/确认/取消、confirm worker | geometry/draft/confirm/stale task | bbox/shape/axis/source 不变，取消不删 accepted part |
| 5 | part mask/material 编辑、preview、接受、保存与重开 | Part Mask/Material | material、contour/voxel、preview/accept/save worker | mask/material state + persistence | accepted mask 和 material metadata 不错位、不覆盖原始 TIF |
| 6 | 2D/3D volume preview、overlay、GPU/CPU fallback | Preview/Rendering | slice/axis/display、renderer、resource callbacks | render state/resource/fallback | 显示失败不被误报为数据损坏，缓存不跨对象污染 |
| 7 | Local Axis 三点、roll reference、reslice、选择与重开 | Local Axis/Reslice | canvas picking、overlay、worker | geometry/task/manifest + GUI key-path | 数学不变，reslice manifest 与来源可追踪 |
| 8 | 样本诊断、训练、预测、结果比较、AI 接受、外部导入 | Training/Prediction/Review | panel、worker、result accept/import | backend/review/promotion/import | raw prediction 不触碰 manual truth，训练样本客观合规 |
| 9 | 跨工作流协调、兼容退场、主 Widget 收束 | Coordinator | workflow commands only | coordinator ordering + architecture | 只协调上下文与顺序，不吞回各工作流内部状态 |
| 10 | 全量自动验证与真实 TIF/GPU 验收 | 无新增状态 | 全部 signal contract | 全套 suite + 真实研究流程 | 输出、角色、重开、失败恢复和后台切换全部无回退 |

任一阶段未满足退出条件，不进入下一阶段。

## 6. Stage 0：基线、地图与冻结点

### 研究目的

确认第三轮是在什么真实程序状态上开始，避免用不同的行数口径或遗漏私有测试依赖来制造“已经优化”的假象。

### 必须产出

- 统一使用物理行数统计主文件、Widget 方法、短 wrapper 和 `.connect()`。
- 方法台账覆盖源码调用、测试调用、信号调用和兼容类型。
- 测试台账标明目标层及旧测试去向。
- 信号台账标明控件、signal、旧目标、新目标、是否允许重复连接和解除时机。
- 记录完整自动化基线和真实 TIF 浅验收基线。
- 明确正式实施基线究竟采用“当前 HEAD”还是“当前未提交候选草稿”。

### 退出条件

- 基线可以重复生成。
- 所有工作流都有方法、状态、信号、测试和 service 依赖清单。
- 用户确认正式实施基线。
- 本阶段不改变程序行为。

## 7. Stage 1：Workbench Shell、View Contract 与 Signal Router

### 完整工作流边界

负责工作台启动、controller 注册、布局装配、公共视图接口、信号登记、项目关闭时解绑和顶层入口，不负责标注、ROI、mask、preview 或训练内部规则。

### 状态与信号

- Shell 只持有 controller 注册表和顶层生命周期状态。
- Signal router 记录每条连接的所有者、bind/unbind 状态和重复连接审计。
- Start Center、Ask Agent、Show Log 等顶层信号可先迁移验证框架。
- objectName、快捷键、tab 顺序和翻译刷新保持不变。

### 测试

- 重复 bind 不会造成一次点击触发两次。
- unbind/destroy 后信号不再写旧界面。
- controller 只获得最小 view contract。
- GUI smoke 和 UI polish 保持通过。

### 退出条件

- `__init__` 不再混合全部工作流初始化与绑定。
- 新工作流可以通过统一生命周期注册和解除。
- Shell 未吸收任何具体研究工作流逻辑。

## 8. Stage 2：Selection 与 Project Lifecycle

### 研究动作闭环

打开项目 → 构建 specimen/part/reslice 树 → 选择研究对象 → 切换前处理未保存内容 → 广播唯一上下文 → 取消或作废旧任务 → 刷新各工作流 → 关闭项目并清理写任务。

### 唯一状态

- project、specimen、part、reslice、source role 和 selection revision 由 Selection/Lifecycle 唯一维护。
- 其他 controller 只接收不可随意修改的上下文快照。
- Widget 不再维护第二套可写 selection 字段。

### 信号与测试

- specimen/part/reslice 树信号直接进入 Selection controller。
- project open/close/refresh 进入 Lifecycle controller。
- 测试覆盖切换顺序、未保存询问、旧 preview/save/reslice 作废、关闭后回调隔离。
- GUI key-path 保留连续切换、保存重开和后台任务中切换。

### 退出条件

- 全部工作流使用同一上下文对象或 revision。
- 旧任务不能刷新或写入新选择。
- 项目关闭后无后台回调写旧界面。

## 9. Stage 3：Annotation、Save 与 Manual Truth

### 研究动作闭环

加载当前切片标签 → 选择 brush/contour 等工具 → 编辑并记录 dirty revision → 自动保存或手动保存 → 根据保存快照清理对应 revision → 失败时保留 dirty 和重试入口 → 在受控条件下提升 manual truth。

### 唯一状态

- tool mode、brush size、undo/redo、dirty slices、slice revisions、save generation 和运行中 save task 归 Annotation controller。
- Widget 不保留可独立写入的 `working_edit_dirty` 等副本。
- 保存快照必须包含 project/specimen/part/reslice/slice/source role/revision。

### 信号与回调

- 工具按钮、画布编辑、undo/redo、保存按钮和快捷键直接进入 Annotation controller。
- 自动保存与手动保存 worker 的 finished/failed 直接回到 Annotation controller。
- truth promotion 仍调用现有安全 service，不在 controller 复制角色规则。

### 测试

- 保存过程中继续编辑同一切片，新 revision 保持 dirty。
- 保存失败不丢 dirty，允许重试。
- 手动保存与运行中的自动保存按确定顺序协调。
- 未保存关闭、切换和训练前询问保持一致。
- raw prediction 等不允许来源不能提升为 manual truth。
- 保存按钮和快捷键一次操作只触发一次保存 command。

### 退出条件

- Annotation 状态只有一个可写所有者。
- 保存 worker 不再调用旧 Widget 私有完成槽。
- 旧测试不再直接设置 Widget dirty 字段。
- 仅保留确有外部调用的公开保存入口。

## 10. Stage 4：ROI-to-Part

### 研究动作闭环

进入 ROI 模式 → 在多个关键切片绘制或调整 ROI → 保存/恢复草稿 → 生成 overlay 快照 → 确认 ROI → 通过 service 校验 shape、坐标轴和 bbox → 创建 part → 初始化 mask 角色 → 选择新 part；取消时只清理草稿。

### 状态与信号

- ROI 关键切片、控制点、drag state、draft revision、confirm task context 归 ROI controller。
- ROI 画布、关键切片、确认、取消和恢复信号直接进入 controller。
- 完成后通过 Selection command 选择新 part，ROI controller 不直接改全局 selection 字段。

### 测试

- 坐标轴、shape、bbox 和来源 metadata 不变。
- 旧确认任务不能在后来选择的 specimen 创建 part。
- 取消草稿不删除已接受 part。
- 新 part、accepted mask 初始化和选择顺序正确。

### 退出条件

- ROI 从绘制到 part 创建形成一个独立可测闭环。
- Widget 不再持有 ROI 草稿和 worker 生命周期。

## 11. Stage 5：Part Mask 与 Material

### 研究动作闭环

加载 part mask/material → 增删改 material → 在关键切片编辑 contour/voxel → 复制、插值或清除 → 构建 preview → 检查后接受或取消 → 正式保存或 metadata-only materialize → 重开验证。

### 唯一状态

- draft、preview、accepted/editable 必须是不同状态，不能共用一个含义模糊的 mask 字段。
- material id、名称、颜色和 voxel 映射由 controller state 管理，正式约束继续由 service 校验。
- preview task 带 part、mask revision 和 material revision。

### 信号与测试

- material 表、关键切片、复制、插值、preview、接受、取消、保存信号直接进入 controller。
- 测试覆盖旧 preview 不覆盖新编辑、删除 material 不遗留孤立 voxel id、preview 不自动成为 manual truth、materialize 不覆盖原始 TIF。
- GUI key-path 覆盖跨切片编辑、取消重建 preview、接受保存和重开。

### 退出条件

- draft/preview/accepted 角色清晰并有直接测试。
- Widget 不再持有 mask 编辑和 preview worker 的重复状态。

## 12. Stage 6：Volume Preview 与 Rendering

### 研究动作闭环

选择显示 source → 计算 cache key → 发起 drag/still preview → GPU texture 或 CPU fallback → 合成 Annotation/ROI/Mask/Local Axis overlay → 显示资源状态 → 取消或拒绝 stale result。

### 边界

- Preview controller 负责请求、缓存、取消、stale 判定和显示协调。
- Renderer 继续负责既有数学和绘制，不吸收研究业务状态。
- 各工作流通过只读 overlay provider 提供显示数据，Preview 不直接修改它们的内部状态。

### 信号与测试

- display、quality、source、transfer function、drag/release 信号直接进入 Preview controller。
- 测试覆盖 still/drag cache、释放后高质量恢复、取消、stale context、GPU 失败转 CPU、资源不足与数据损坏分开提示。
- 保留 renderer 数学和 GPU canvas 既有测试。

### 退出条件

- Preview 可用 fake providers 和 fake renderer 独立测试。
- 训练占用资源时，2D 标注仍可继续且提示可理解。

## 13. Stage 7：Local Axis 与 Reslice

### 研究动作闭环

选择 part → 在 slice/volume 点选三点及 roll reference → 更新草稿摘要和 overlay → 提交 reslice → worker 执行 → 校验完成上下文 → 写入 reslice 记录和 manifest → 通过 Selection command 选择新 reslice。

### 状态与信号

- 三点、roll reference、drag/hit-test、draft revision 和 reslice task context 归 Local Axis controller。
- 画布点击、拖动、清除、执行和导出信号直接进入 controller。
- 导出结果不得直接覆盖当前 selection；必须经过上下文校验后调用 Selection command。

### 测试

- 三点和 roll reference 行为保持不变。
- preview busy lock 不误阻止合法点选。
- 旧导出不能抢回新 part/reslice 焦点。
- reslice 和 training manifest 格式保持不变。

### 退出条件

- 从点选到真实 reslice 记录形成独立闭环。
- 第二轮遗留 Widget 转发槽完成迁移或登记公开理由。

## 14. Stage 8：Training、Prediction、Result Review 与 Backend Panel

### 研究动作闭环

诊断训练样本 → 选择模型/后端 → 启动训练或预测 → 接收结果摘要 → 比较 region 和批量选择 → 导入外部 prediction 或接受 AI 结果 → 经 truth promotion guard 写入受控角色 → 刷新当前结果。

### 边界

- Backend panel controller 保留训练样本诊断、模型库和 backend action。
- Result Review controller 负责结果比较、region、批量选择、外部导入和接受流程。
- 数据资格、写锁、角色与 shape guard 继续由 service/core 决定。

### 按完整研究工作流拆分

Stage 8 不作为一个笼统的“训练模块”一次搬完，而按四条可独立核对、最终互相衔接的研究闭环实施：

1. **样本诊断与模型准备**：读取当前项目上下文 → 统计可训练样本及排除理由 → 选择模型/后端 → 刷新模型库。状态归 Backend panel controller；样本资格仍由既有 service 判断。
2. **训练任务**：确认诊断结果 → 获取 backend write lock → 启动 worker → 报告进度/取消/失败 → 登记模型产物 → 解锁并刷新入口。线程、worker、task token 和 running 状态不得继续在 Widget 与 controller 双写。
3. **预测任务与外部导入**：确定 specimen/part/reslice 与模型 → 启动预测或选择外部 TIF → 校验 shape/context/role → 写入 raw prediction → 刷新结果。任何路径都不得直接写 manual truth。
4. **结果比较与接受**：选择结果来源和 region → 生成比较行与摘要 → 打开或在 3D 中定位 → 批量选择 → 经 truth promotion service 接受 → 刷新 Annotation 和 Result Review。Result Review controller 只编排审阅，不复制角色和 promotion 安全规则。

每条闭环先完成状态和直接测试，再迁移控件信号与 worker 回调，最后删除 Widget wrapper。四条闭环全部完成前，Stage 8 只能保持 `candidate`。

### 信号与测试

- 训练、预测、模型选择、结果比较、导入和接受信号直接进入对应 controller。
- 测试覆盖训练样本资格、backend write lock、prediction 不触碰 manual truth、外部 TIF shape/context 错误、AI 接受必须经过 promotion guard。
- GUI key-path 覆盖训练后预测入口、结果摘要、比较接受和外部导入。

信号迁移必须记录：控件/worker signal、旧 Widget slot、新责任主体、重复 bind 防护、项目关闭时解绑方式，以及旧任务返回时使用的 project/specimen/part/reslice/model token。测试迁移必须同步做到：

- Backend panel controller 直接测试样本诊断、模型库、锁、任务状态和 stale callback。
- Result Review controller 直接测试 source/region、比较刷新、选择、外部导入和接受命令。
- service/core 测试继续负责样本资格、shape/role guard、truth promotion 和持久化安全。
- `tests/test_tif_workbench.py` 只保留训练入口、结果摘要、外部导入、接受结果等少量真实 GUI 路径，不再直接写 controller 私有 state。
- 新测试必须登记进 `scripts/run_validation_suite.py` 和架构测试分组；旧 seam 删除与新测试落地必须在同一阶段完成。

### 退出条件

- Backend panel 与 Result Review 责任不重叠。
- Widget 不再持有结果比较和接受流程的内部状态。
- Widget 不再持有训练/预测 worker、thread、selected refs、refreshing 或 result cache 的可写副本。
- 所有训练、预测、导入和接受信号单次触发，重开项目不会累积连接。
- raw prediction、external prediction 和 manual truth 的角色边界有直接自动测试证据。

## 15. Stage 9：Cross-workflow Coordinator 与主 Widget 收束

### 只允许保留的跨工作流规则

- selection changing 前询问 Annotation 未保存状态。
- 项目关闭前协调运行中的写任务。
- ROI 创建 part 后请求 Selection 切换。
- Local Axis 创建 reslice 后请求 Selection 切换。
- 训练/预测资源状态影响 Preview 提示，但不修改 Preview 内部数据。
- AI 接受后通知 Annotation/Result Review 刷新当前角色。

Coordinator 不得接管 brush、ROI 点、mask voxel、render cache、Local Axis 数学或结果比较等工作流内部逻辑。

### 清理与量化验收

- 删除仅用于信号转发、测试兼容和内部重复调用的 Widget wrapper。
- 清理已迁移 worker/thread 字段、重复状态和死代码。
- `tests/test_tif_workbench.py` 仅保留 shell、coordinator 和少量 GUI key-path。
- 主文件目标为 7,500-9,000 物理行，Widget 方法少于 350，`.connect()` 少于 80，4 行以内 wrapper 少于 40。
- `__init__` 少于 300 行，`_build_layout` 少于 250 行或移出。
- 单个 controller 建议 800-1,500 行；超过 1,500 行必须复核，禁止新增超过 3,000 行的 controller。

当前冻结快照的主文件行数已经低于原定 7,500 下界，因此 Stage 9 不为满足区间而人为加回代码。最终判断采用“责任边界优先、上限约束为主”：主文件建议保持不高于 8,000 行；若低于 7,500 行且可读性、公开入口和安全 guard 完整，视为优于目标。真正的硬门是 Widget 方法少于 350、`.connect()` 少于 80、4 行以内 wrapper 少于 40、状态无双写和测试不再锁定旧私有入口。

Stage 9 的收束顺序固定为：先迁移剩余调用方和测试 → 再删除 descriptor/薄 wrapper → 再清理重复状态和 worker/thread 字段 → 最后评估是否需要 coordinator。不得为了压方法数把各工作流内部规则重新塞进 coordinator，也不得删除数据安全 guard。

### 退出条件

- 主 Widget 的剩余责任可以逐条解释为 shell、公开入口或真正跨工作流协调。
- 工作流状态不存在两份可写副本。
- Qt 信号不再经过无意义 Widget 转发层。

## 16. Stage 10：全量验证与真实研究验收

### 自动验证顺序

1. 对本轮调整文件运行 `py_compile`。
2. 运行当前阶段 controller/service 窄测试。
3. 运行 core safety、storage safety、service/task、preview/export、workbench、layout、GUI smoke、UI polish 和架构分组。
4. 运行 signal contract，确认单次触发、解绑和跨工作流事件顺序。
5. 确认新增测试已加入验证脚本和架构测试分组。
6. 运行架构指标脚本并与 Stage 0 比较。
7. 运行 `git diff --check` 和 `git status --short`，排除数据、模型、数据库、配置和临时输出。

### 用户真实 TIF/GPU 验收

- 打开真实项目，连续切换 specimen、part 和 reslice。
- 编辑多个标签切片，在自动保存期间继续编辑同一切片，再手动保存并重开。
- 完成 ROI-to-Part，并核对新 part、mask 范围和来源。
- 完成 material/mask 编辑、preview、取消、重建、接受、保存和重开。
- 查看真实 GPU preview，并验证资源不足或 CPU fallback 提示。
- 完成 Local Axis 三点、真实重切片、切换目标和重开核对。
- 检查训练样本、模型、预测、结果比较、AI 接受和外部 prediction 导入。
- 在后台任务运行时切换目标，确认旧结果不抢焦点、不写错上下文。

### 最终完成条件

- Stage 0-10 均有复核记录。
- 测试和信号台账更新为最终状态。
- 数据格式、manual truth、raw prediction、原始 TIF、reslice 和训练安全无回退。
- 量化目标达到；未达项有真实调用依赖和后续处置说明。
- 全量自动验证通过。
- 用户完成真实蚂蚁 TIF/GPU 验收并确认候选版本。

## 17. 每阶段复核报告固定内容

每个 `stageN_review` 至少记录：

- 本阶段对应的研究动作闭环。
- 新状态所有者与删除的重复状态。
- 迁移的方法及保留 wrapper 理由。
- 迁移的 Qt 信号、最终目标和解绑方式。
- 迁移、保留、删除的测试及验证 suite。
- stale task、失败恢复和数据角色 guard 的验证结果。
- 主文件行数、Widget 方法数、短 wrapper、`.connect()` 和 controller 行数。
- 自动验证结果、人工验收结果和已知风险。
- 与需求文档的逐条偏差检查。

## 18. 需求确认后第一步

用户确认本计划后，不直接续写当前 Stage 8 半迁移。第一步先进行“现有候选草稿审计”：

1. 以当前 `HEAD` 的 14,234 行作为发布对照基线，以用户确认时的工作树作为实施起点；二者都保留，不用单一数字替代。
2. 检查现有 `tif_workbench.py` 是否存在重复方法、临时锚点或半迁移状态。
3. 对 Stage 0-7 按本计划重新检查状态唯一性、信号直连、测试迁移和退出条件；原有 review 只作候选证据。
4. 单独审计 Stage 8 Result Review 半迁移代码，先恢复为可编译、可测试、边界明确的候选状态，不把修复过程计作 Stage 8 通过。
5. 从 Stage 0 开始逐阶段形成新的 `candidate`、`verified` 和 `accepted` 结论；前一阶段未 `accepted` 时不进入下一阶段。

## 19. 需要用户确认的决策

1. 是否同意以完整研究工作流为拆分单位，并采用 Stage 0-10 顺序？
2. 是否同意主文件目标为 7,500-9,000 物理行，而不是以低于 5,000 行为硬目标？
3. 是否同意 Selection/Lifecycle 成为唯一 project/specimen/part/reslice 上下文入口？
4. 是否同意新测试默认直接测试 controller/service，旧 Widget 私有测试按台账迁移？
5. 是否同意信号迁移后删除纯转发 Widget slot，只保留有真实外部调用的公开入口？
6. 是否同意每阶段必须同时通过状态、信号、测试、数据安全和人工验收门禁？
7. 是否同意本轮不修改数据格式、训练算法、Local Axis 数学和 GPU renderer 数学？
8. 对当前已存在的 Stage 0-7 候选草稿和 Stage 8 半迁移代码，正式实施时选择：保留并逐阶段重新审计，还是在不使用破坏性 Git 命令的前提下另建安全基线后重做？

## 20. 用户确认表

以下项目全部确认后，代码阶段才解冻：

| 决策 | 建议默认值 | 用户结论 |
| --- | --- | --- |
| 拆分单位 | 按完整研究工作流，不按零散 helper | 待确认 |
| 阶段顺序 | Stage 0-10 严格顺序 | 待确认 |
| 主文件目标 | 7,500-9,000 物理行，同时满足责任和测试门禁 | 待确认 |
| 上下文入口 | Selection/Lifecycle 唯一管理 specimen/part/reslice | 待确认 |
| 测试策略 | 新测试直测 controller/service，GUI 只保留关键真实路径 | 待确认 |
| 信号策略 | 信号直连责任主体，删除纯转发 Widget slot | 待确认 |
| 安全边界 | 不改数据格式、训练算法、Local Axis/GPU 数学 | 待确认 |
| 候选代码处置 | 建议保留工作树、逐 Stage 重新审计，不直接视为完成 | 待确认 |
| 阶段放行 | 自动门与研究门都通过，用户接受后才进入下一阶段 | 待确认 |
