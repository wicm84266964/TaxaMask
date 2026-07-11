# TIF 工作台架构整理第三轮执行清单

日期：2026-07-10

状态：`accepted`；Stage 0-10、真实数据/GPU/可见 3D 技术链和用户科研判断全部完成

需求文档：`docs/tif_workbench_architecture_refactor_round3_requirements_zh.md`

发布对照基线：`1435751` / 当前 `HEAD`，`tif_workbench.py` 为 14,234 物理行

最终 accepted 快照：2026-07-10 架构脚本口径为 5,057 物理行、221 个 Widget 方法、39 个 4 行以内方法、11 处 `.connect()`；显式启用隔离真实蚂蚁体积 fixture 的九组验证共 702 条通过；Dataset601 匹配真实脑体积的 GPU 0 nnU-Net 预测、结果安全导入和 SQLite 重开已通过；可见窗口已确认 display mode、volume canvas、Local Axis 草稿和 A/B/C overlay 同步；用户已确认 Local Axis 解剖方向和 Dataset601 脑区边界合理。

## 执行原则

- 按完整研究工作流拆分，不按零散 helper 或单纯行数拆分。
- 每阶段先建立新责任主体和直接测试，再迁移信号与旧测试，最后删除 wrapper。
- 同阶段必须同时处理代码、Qt 信号、测试、验证套件和兼容入口。
- controller 优先调用现有 service/core/task，不复制安全规则。
- 主 Widget 只保留 shell、跨工作流协调和明确公开入口。
- 每阶段保持可运行、可测试、可单独回退。
- 不修改项目数据格式、训练算法或 GPU renderer 数学。
- 用户确认需求与清单前，不开始代码改动。
- 当前工作树中的 Stage 0-7 实现及 Stage 8 半迁移代码统一标记为 `candidate evidence`；不得因已有代码、旧 review、清单勾选或局部测试通过写成用户已接受。
- 每阶段必须依次达到 `planned → candidate → verified → accepted`；本轮计划确认只把阶段推进到 `planned`，只有用户确认阶段 `accepted` 后才能进入下一阶段。
- 用户确认本清单前冻结业务代码；只允许修订计划、需求、测试台账和信号台账。

## 勾选规则

- 本清单中的 `[ ]` 表示尚无足够候选证据，或仍待实现/复核。
- 本次需求复核前已经出现的 `[x]` 只表示工作树中存在对应自动化候选证据，不表示用户已经批准需求，也不表示真实研究流程已验收。
- 用户确认计划后，每个 Stage 仍须重新形成 `candidate → verified → accepted` 记录；只有 Stage review 明确写出 `accepted`，才代表阶段正式放行，不能只看复选框。
- 涉及真实 TIF、GPU、重切片、训练或 prediction 的人工项，如果缺少安全 fixture，必须保持未勾选并统一进入 Stage 10 真实研究流程验收。

## 每阶段强制联动交付

| 联动项 | 本阶段必须回答的问题 | 完成证据 |
| --- | --- | --- |
| 工作流代码 | 研究动作是否从入口到完成/失败/取消都归同一责任主体？ | controller/service 边界、方法迁移清单、删除或保留 wrapper 的理由 |
| 状态所有权 | Widget 与 controller 是否仍存在两份可写状态或 worker/thread 引用？ | 唯一 owner 清单、重复字段归零或兼容只读说明 |
| Qt 信号 | 控件、Canvas、worker 回调最终连接到谁，重开项目会不会重复触发？ | 信号台账、单次触发/解绑/顺序测试 |
| 自动化测试 | 新责任主体是否被直接测试，旧 Widget 私有 seam 是否同步退场？ | controller/service 测试、关键 GUI 路径、验证 suite 登记 |
| 后台上下文 | 旧任务返回时能否识别 specimen/part/reslice/revision 已变化？ | token/context/stale-result 测试 |
| 研究数据安全 | 原始 TIF、working edit、manual truth、raw prediction、accepted mask/reslice 是否保持角色和来源？ | guard 测试、重开核对、失败恢复记录 |
| 阶段指标 | 主文件是否真实失去责任，而不是只新增转发层？ | 行数、Widget 方法、短 wrapper、`.connect()`、controller 行数对比 |

## 强制基线指标

Stage 0 必须可重复生成：

- 主文件物理行数、Widget 方法数、4 行以内薄方法数、`.connect()` 数；后续阶段统一使用物理行口径。
- 每个旧 Widget 方法在源码、测试和信号中的调用位置。
- 主要测试对 Widget 私有字段/方法的直接引用数量。
- 当前完整验证结果和真实人工验收基线。

一次性输出只放 `.tmp_validation/`；需要长期保留的脚本放 `scripts/`，审计结果放本架构文档目录。

## 工作流迁移完成定义

- [x] controller/service 边界已建立。
- [x] 工作流状态有明确唯一所有者。
- [x] 相关 Qt 信号直接连接新责任主体。
- [x] 旧 Widget 调用点已分类并迁移。
- [x] controller/service 直接测试已建立。
- [x] 关键 GUI 路径不过度访问私有状态。
- [x] 验证脚本和架构测试分组已同步。
- [x] wrapper 已删除，或登记公开兼容理由和删除阶段。
- [x] Stage 记录包含方法、信号、测试、指标和研究流程影响。
- [x] 自动门与真实研究门均已记录；未人工验证项未省略。

## 迁移台账

Stage 0 建议新增：

- `tif_workbench_architecture_refactor_round3_test_migration_zh.md`
- `tif_workbench_architecture_refactor_round3_signal_migration_zh.md`

每条旧测试记录：测试名、所属工作流、当前私有依赖、目标层、迁移阶段、新测试名和旧测试处理方式。

每条信号记录：控件/objectName、signal、当前目标、目标 controller/command、是否允许重复连接、关闭时是否断开、对应测试和迁移阶段。

## 阶段 0：基线与迁移地图

### 目标

把剩余职责、调用依赖、信号和测试耦合形成可审计地图，避免边拆边猜。

### 任务

- [x] 记录 `HEAD` 与非干净候选工作树；按双基线审计，不清除用户现有改动。
- [x] 生成强制基线指标。
- [x] 将方法归入 Selection、Annotation、ROI、Part Mask、Preview、Local Axis、Backend/Result、Lifecycle、Shell/Coordinator。
- [x] 建立测试和信号迁移台账。
- [x] 标记真正外部公开调用的方法，不默认所有旧方法都是 API。
- [x] 运行现有一键验证并记录 skip、超时和环境。
- [x] 记录无安全真实 fixture 的限制；真实 TIF/GPU 验收明确留到 Stage 6-10，不伪造人工结论。

### 验收

- [x] 每个工作流都有方法、字段、信号、测试和 service 依赖清单。
- [x] 所有 wrapper 有来源分类。
- [x] 基线可重复生成；仅修复已有半迁移断点，不新增研究功能。

## 阶段 1：Shell、View Contract 与 Signal Router

### 建议文件

- `AntSleap/ui/tif_workbench_shell.py`
- `AntSleap/ui/tif_workbench_view.py`
- `AntSleap/ui/tif_workbench_signal_router.py`
- `tests/test_tif_workbench_shell.py`
- `tests/test_tif_workbench_signal_router.py`

### 任务

- [x] 分开状态初始化、controller 注册、布局创建和信号绑定。
- [x] 定义最小 view contract 或控件注册表。
- [x] 定义 controller 生命周期：创建、bind、project opened、selection changed、closing、unbind、destroy。
- [x] Signal router 支持工作流登记和重复连接审计。
- [x] 暂只迁移低风险信号，保持 objectName、tab、快捷键和翻译。

### 验收

- [x] `__init__` 明显缩短且不再混合全部业务信号。
- [x] Shell/View/Router 不读取工作流内部状态；workflow controller 的 Widget 依赖按 Stage 2-9 继续收束。
- [x] 重复 bind 不会让按钮触发两次。
- [x] GUI smoke 和 UI polish 不回退。

## 阶段 2：Selection 与 Project Lifecycle

### 建议文件

- `tif_selection_workflow_controller.py`
- `tif_project_lifecycle_controller.py`
- 对应 controller 测试

### 任务

- [x] 统一 project/specimen/part/reslice context。
- [x] 选择信号直接连接 Selection controller。
- [x] 定义 selection changing/changed 事件和刷新顺序。
- [x] 统一关闭、刷新和切换前未保存询问。
- [x] 统一取消或作废旧 preview、ROI、save、reslice context。
- [x] 迁移对应 Widget 私有测试并删除转发 wrapper。

### 验收

- [x] 各工作流收到同一上下文。
- [x] 旧任务不能刷新新选择。
- [x] 项目关闭后无回调写旧界面。
- [x] Widget 不再维护多份 selection 状态。

### 人工验收

- [x] 隔离真实蚂蚁体积项目连续切换两个 specimen、part、reslice，并往返恢复选择。
- [x] 隔离真实蚂蚁体积上下文模拟旧 Preview 完成后切换 specimen，旧任务被取消且不覆盖既有 cache/当前选择。
- [x] 真实蚂蚁体积隔离项目保存重开后，part/reslice 选择恢复符合旧行为。

## 阶段 3：Annotation、Save 与 Manual Truth

### 建议文件

- `tif_annotation_workflow_controller.py`
- 扩展 `tif_label_edit_service.py`、`tif_truth_promotion_service.py`
- `tests/test_tif_annotation_workflow_controller.py`

### 任务

- [x] 定义 Annotation state 和唯一所有者。
- [x] 迁移 brush、contour、slice edit 和 dirty tracking 信号。
- [x] 迁移 auto-save snapshot、generation/token、完成和失败处理。
- [x] 迁移手动保存、状态标签和未保存确认。
- [x] 迁移 truth promotion command，继续调用安全 service。
- [x] 将旧测试迁移到 service/controller/GUI key path。
- [x] 删除测试专用和信号专用 wrapper。

### 验收

- [x] 自动保存不清除稍后产生的新 dirty edit。
- [x] 保存失败保留 dirty 状态并可重试。
- [x] truth promotion 拒绝不允许的 source role。
- [x] 切换、关闭、训练前提示行为不变。
- [x] 保存按钮和快捷键只触发一次 command。

### 人工验收

- [x] 隔离真实蚂蚁体积 working edit 完成多切片编辑、自动保存快照和最终手动保存。
- [x] 隔离真实蚂蚁体积自动保存快照后继续编辑同一切片，较新 revision 保持 dirty，最终保存后存在。
- [x] 真实蚂蚁体积隔离项目完成部位标注手动保存、SQLite 重开和标注文件核对。
- [x] 隔离真实蚂蚁体积 part editable result 经 Truth Promotion 提升为 manual truth，raw prediction backup 路径和内容不变；连续 5 次稳定通过。

## 阶段 4：ROI-to-Part

### 任务

- [x] 新增 `tif_roi_workflow_controller.py` 和直接测试。
- [x] 迁移 ROI 绘制、拖动、关键切片和 overlay 快照。
- [x] 迁移草稿保存、取消和恢复。
- [x] 迁移同步/后台确认和 task context。
- [x] 迁移 part 创建、mask 初始化和完成后选择。
- [x] ROI 控件信号直接绑定 controller。

### 验收

- [x] 坐标轴、shape 和 bbox 规则无回退。
- [x] 旧任务不能创建到新 specimen。
- [x] 新 part、accepted mask 和选择正确。
- [x] 取消草稿不误删已接受 part。

### 人工验收

- [x] 真实蚂蚁体积隔离项目创建跨关键切片 ROI/mask contour 并确认 part。
- [x] 真实蚂蚁体积隔离项目检查 part bbox、非空 accepted mask 和 mask 范围。
- [x] 真实蚂蚁体积隔离项目保存重开确认 part/reslice 记录稳定。

## 阶段 5：Part Mask 与 Material

### 任务

- [x] 新增 `tif_part_mask_workflow_controller.py` 和直接测试。
- [x] 迁移 material 表、添加、编辑、删除和当前 material。
- [x] 迁移关键切片、复制、插值、清除和 contour。
- [x] 迁移 preview worker、stale result、接受和取消。
- [x] 迁移正式保存与 metadata-only materialize。
- [x] 明确 draft、preview、accepted/editable 状态。

### 验收

- [x] Preview 不自动写成 manual truth。
- [x] 旧 preview 不覆盖新编辑。
- [x] material 删除不留下不可解释 voxel id。
- [x] materialize 不覆盖原始 TIF。
- [x] mask 保存重开一致。

### 人工验收

- [x] 隔离真实蚂蚁体积新增材料 3，跨切片编辑、保存并 SQLite 重开核对。
- [x] 隔离真实蚂蚁体积构建 mask preview、清除、修改关键切片、重建不同结果并接受。
- [x] 隔离真实蚂蚁体积保存重开后 material 3、working edit 和 accepted part mask 均稳定，标注保存不覆盖 mask。

## 阶段 6：Volume Preview 与 Rendering

### 任务

- [x] 扩展 `tif_preview_controller.py`，必要时新增 `tif_volume_render_controller.py`。
- [x] 迁移 display、quality、ROI/mask source、transfer function 等信号。
- [x] 迁移 still/drag 请求、cache key、取消和 stale result。
- [x] 迁移 GPU texture 与 CPU pixmap fallback 协调。
- [x] 定义 Annotation、ROI、Part Mask、Local Axis overlay provider。
- [x] 移出大型 overlay 和 render 协调方法。
- [x] 迁移直接修改 Widget preview 私有字段的测试。
- [x] 保留 renderer 数学和 GPU canvas 既有测试。

### 验收

- [x] Preview controller 可用 fake view/state 直接测试。
- [x] 资源不足与数据损坏提示分开。
- [x] still/drag cache、取消和 stale context 无回退。
- [x] GPU 不可用时能恢复 CPU 显示。
- [x] Preview 不直接修改其他工作流内部状态。

### 人工验收

- [x] 检查真实 3D source、mask 和 Local Axis overlay；真实头部 CPU 3D fallback 截图与状态文件一致。ROI 数学/裁剪链由真实数据自动门覆盖。
- [x] 本机 OpenGL renderer 初始化不稳定，GPU 拖动质量恢复项不适用；正式 CPU 3D fallback 已验证稳定。GPU 交互性能作为后续驱动兼容专项，不阻塞本轮 accepted。
- [x] 真实 GPU prediction 运行、写锁/任务状态合同和可见只读提示均通过；本轮未执行真实训练，训练性能体验留后续模型训练专项，不影响结果安全验收。

## 阶段 7：Local Axis 与 Reslice

### 任务

- [x] 扩展 `tif_local_axis_controller.py`；规模需要时新增 export controller。
- [x] 迁移 slice/volume hit test、拖动和 overlay provider。
- [x] 迁移草稿摘要和按钮状态。
- [x] 迁移真实 reslice worker 生命周期。
- [x] 迁移完成后的记录、选择和 stale context 拒绝。
- [x] 迁移 training manifest 导出。
- [x] 画布和控件信号直接连接 controller。
- [x] 删除第二轮遗留转发 wrapper。

### 验收

- [x] 三点参考和 roll reference 行为不变。
- [x] preview busy lock 不阻止合法点选。
- [x] 旧导出不能抢回新 part/reslice 焦点。
- [x] reslice 和训练 manifest 格式不变。

### 人工验收

- [x] 真实头部输出 Z、Roll A/B 和平面 C 已由用户观察并确认符合解剖方向。
- [x] 对真实蚂蚁体积隔离副本执行 Local Axis 重切片并生成 image/metadata。
- [x] 隔离真实蚂蚁体积旧 Preview 任务完成时已切换 specimen，任务取消且当前选择不跳回；Local Axis stale 合同另有直接测试。
- [x] SQLite 重开后核对真实体积 reslice 记录与选择恢复。

## 阶段 8：Result Review 与 Backend Panel 收束

### 任务

- [x] 保持训练样本诊断、模型库和 backend action 在 panel controller。
- [x] 新增 `tif_result_review_controller.py` 和直接测试。
- [x] 迁移结果比较、region、批量选择和接受。
- [x] 迁移外部 prediction TIF 导入。
- [x] 迁移 AI 结果受控提升和完成后刷新。
- [x] 训练、预测、结果信号直接连接目标 controller。
- [x] 迁移 Widget backend/result 私有测试。

### 验收

- [x] 训练只使用客观满足条件的样本。
- [x] Prediction import 不触碰 manual truth。
- [x] AI 结果接受经过 truth promotion guard。
- [x] Backend write lock 无回退。
- [x] 训练后的预测入口和结果摘要正常。

### 人工验收

- [x] 隔离真实蚂蚁项目核对训练诊断与模型库：缺 reslice 时明确列出 record/image 缺失并阻止训练，无登记模型时保持空状态。
- [x] 隔离真实蚂蚁项目检查训练选择阻止逻辑和 prediction target 表；不满足条件时入口不误选样本。
- [x] 在可见界面对照 Dataset601 来源、working edit/raw backup 角色、17 个实际标签和多切片彩色区域；科研合理性仍由用户判断。
- [x] 隔离真实尺寸项目导入正确 shape 外部 prediction，manual truth 不变；错误 shape 被拒绝且不新增 draft。

## 阶段 9：Coordinator、兼容清理与主 Widget 收束

### 任务

- [x] 将真正跨工作流规则集中到 coordinator 并逐条测试。
- [x] 按调用清单删除信号兼容、测试兼容和内部 wrapper。
- [x] 审查剩余短方法并记录公开兼容理由。
- [x] 审查主文件剩余 `.connect(...)` 是否属于 renderer/worker 生命周期协调。
- [x] 清理重复状态、死代码和已迁移 worker/thread 字段。
- [x] 将 `tests/test_tif_workbench.py` 收缩为完整 Widget/关键 GUI 路径，并由 controller/shell/coordinator 直接测试承担责任测试。
- [x] 检查 import 循环、生命周期和启动烟测。

### 量化验收

- [x] 主文件 5,057 行；低于 7,500-9,000 目标区间，但拆出代码均有责任模块和全层测试，不人为回填。
- [x] Widget 方法数低于 350（221）。
- [x] 主文件 `.connect(...)` 低于 80（11）。
- [x] 4 行以内方法低于 40（39）；公开入口和内部短 helper 的保留理由已复核。
- [x] `__init__` 低于 300 行（11）。
- [x] `_build_layout` 已移出主 Widget。
- [x] 无新增超过 3,000 行的单一 controller/builder。

### 架构验收

- [x] 新测试默认直接测试 controller/service。
- [x] Qt 信号不经过无意义 Widget 转发层。
- [x] 工作流 state 无重复可写副本。
- [x] Coordinator 未吸收工作流内部逻辑。

## 阶段 10：全量验证与候选收口

### 自动化任务

- [x] 对全部调整文件运行 `py_compile`（最终 42 个修改/新增 Python 文件）。
- [x] 运行 core/storage/service、preview/export、workbench、layout、GUI smoke、UI polish 和架构分组（该阶段快照显式启用真实 fixture，共 698 条；当前最终门为 702 条）。
- [x] 运行 signal contract 测试（含 67 条责任主体/信号/状态/登记合同）。
- [x] 检查新增测试进入验证脚本，并补齐 ROI 与 Volume Render 漏登。
- [x] 使用 `C:\Users\admin\anaconda3\envs\taxamask\python.exe`，排除缺 PySide6 伪通过。
- [x] 运行 `git diff --check`。
- [x] 检查 Git 状态，排除 TIF、SQLite、模型、run outputs、API 配置，并清理本轮明确临时文件。

### 建议验证

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite core_safety --suite service_task --timeout 300
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite tif_preview_export --suite tif_workbench --suite tif_layout --timeout 300
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite gui_smoke --suite ui_polish --timeout 300
git diff --check
git status --short
```

具体 suite 名以 Stage 0 确认的当前脚本为准；新增 workflow suite 必须写入复核记录。

### 用户真实研究流程验收

- [x] 打开隔离真实蚂蚁体积项目并完成 specimen/part/reslice 连续切换与 SQLite 重开。
- [x] 隔离真实蚂蚁体积完成标签编辑、自动保存 revision、手动保存和 SQLite 重开核对。
- [x] 在真实蚂蚁体积隔离副本完成一次 ROI-to-Part。
- [x] 隔离真实蚂蚁体积完成 material 新增、mask preview 清除/重建/接受、保存和重开核对。
- [x] 在可见窗口检查 renderer：本机 OpenGL 初始化不稳定，正式 CPU 3D fallback 正常显示真实体积、状态和 overlay，未误报数据损坏。
- [x] 在真实蚂蚁体积隔离副本完成三点/roll reference、真实重切片和重开选择。
- [x] 真实 GPU 0 + Dataset601 匹配脑体积预测技术链、结果安全导入、SQLite 重开、可见三维源体和彩色 prediction overlay 已通过；用户已确认脑区边界合理，真实训练作为后续独立专项。
- [x] 隔离真实蚂蚁体积旧 Preview task 切换 specimen 后被取消且不覆盖 cache/选择；ROI、Local Axis、Backend stale context 另有直接合同测试。

### 文档收口

- [x] 新增 Stage 0-10 复核记录。
- [x] 将测试和信号迁移台账更新为最终状态。
- [x] 用户已确认候选；本轮同步 `CHANGELOG_zh.md` 和 `LLM_CONTEXT_DETAILED.md`。
- [x] 本轮未改变公共定位、安装、平台或工作流入口，因此不改 `README.md`。

## 阶段回退规则

- 每个工作流使用独立、可审查提交；用户未要求前不提交。
- 一个阶段验证失败时，先修复该阶段，不叠加下一工作流。
- 不使用 `git reset --hard`、`git clean -fd` 或 checkout 式破坏性回退。
- 若 controller 必须任意访问整个 Widget，暂停并修订 view contract。
- 若安全规则被复制到 UI controller，停止并改回调用 service/core。
- 人工验收与自动化冲突时，以研究数据安全和可恢复性优先。

## 第三轮完成判断

- [x] Selection、Annotation、ROI、Part Mask、Preview、Local Axis、Result Review 边界清晰。
- [x] 至少五个工作流完成 controller、信号和测试的完整迁移。
- [x] 责任测试已按台账迁到 controller/service；保留的 Widget 私有 seam 只服务完整 GUI 路径，不再是唯一架构入口。
- [x] 主 Widget 达到并优于量化目标。
- [x] 自动化、真实 GPU 预测和源码边界证明数据格式、manual truth、raw prediction、原始 TIF 和 reslice 安全无回退；GPU 验收中发现并修复顶层 raw backup 未写入 SQLite 的缺口。
- [x] 全量自动化验证通过（当时显式真实 fixture 为 698 条；新增回归后当前最终门为 702 条）。
- [x] 用户完成真实头部 Local Axis 和 Dataset601 脑区边界判断并确认候选版本。


## 2026-07-10 可见状态同步补充复核

- [x] 修复显示模式下拉框、内部 `display_mode`、`view_stack` 和实际渲染调用不同步；Qt `currentIndexChanged(int)` 不再被误当作模式字符串。
- [x] 结果评审控制器和 Agent 面板切换统一通过显示模式入口，不再直接写 `display_mode`。
- [x] 部位选择加载结束后清除“正在加载”语义，并写入明确完成反馈；同一部位重新加载不清除 Local Axis 草稿。
- [x] 隔离真实头部可见窗口确认：`display_mode=volume`、下拉框为 volume、当前 `view_stack` 为 volume canvas、草稿输出 Z 存在、Roll A/B 和平面 C 均已设置。
- [x] 中央视图为真实三维体预览，mask 内图像和 Local Axis overlay 可见；截图位于 `.tmp_validation/round3_manual_acceptance/visible_window_after_state_fix.png`。
- [x] 本机可见 OpenGL 初始化不稳定时，正式 CPU 3D fallback 可恢复显示且不误报数据损坏；隔离验收入口固定使用该安全回退。
- [x] 用户确认当前输出 Z、A/B/C 符合真实蚂蚁头部解剖方向。
- [x] 用户确认 Dataset601 结果的脑区边界合理。

最终自动门：九组共 **702 条全部通过**；46 个变更/新增 Python 文件 `py_compile` 通过，`git diff --check` 通过，Git 状态无 TIF、SQLite、模型权重或运行产物。
