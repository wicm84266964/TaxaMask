# TIF 工作台架构整理第二轮需求文档

日期：2026-07-09

分支：`codex/tif-workbench-architecture-refactor`

第一轮基线提交：`346598b`（`整理 TIF 工作台架构与分层回归测试`）

执行清单：`docs/tif_workbench_architecture_refactor_round2_execution_checklist_zh.md`

## 当前状态

第一轮架构整理已经把 TIF 工作台从单一巨型 GUI 文件推进到初步分层结构：

- `AntSleap/ui/tif_workbench.py` 从约 18081 行降到约 15353 行。
- 已拆出翻译、弹窗、canvas、worker、helper 和 Qt task adapter。
- 已新增 `AntSleap/services/`，承接 selection、label edit、truth promotion、ROI、backend workflow、volume preview、local axis、task manager 和状态摘要。
- 已新增 core guard/policy，集中保护 `manual_truth`、预测草稿、raw backup、写入路径和训练样本规则。
- 已建立 core/service/task/GUI 分层测试，并补充一键验证脚本。

第一轮解决了最危险的数据安全和后台任务问题，但 `tif_workbench.py` 仍然较大，UI layout、训练/预测页面控制、3D preview 交互和 Local Axis UI 仍与主 Widget 深度耦合。第二轮目标是在第一轮稳定性的基础上继续瘦身 UI 层，而不是重新改动研究数据格式或训练真值规则。

## 第二轮总目标

第二轮的目标是把 TIF 工作台从“已有分层地基的大型 Widget”继续整理为更清晰的页面/控制器结构：

- UI layout 从主 Widget 中拆出，减少控件装配和业务状态混杂。
- 训练/预测页面控制逻辑从主 Widget 中拆出，保持 service/core 规则不变。
- 3D preview 和 Local Axis 交互控制逻辑进一步模块化，降低 GPU/Qt 交互对主 Widget 的冲击。
- 运行资源不足时，程序给出可理解、可恢复的提示，而不是直接抛出 CRITICAL ERROR。
- 继续保持真实 TIF 研究流程优先，不为了抽象漂亮而牺牲日常标注、重切片、训练和预测稳定性。

## 非目标

第二轮不主动做以下事情：

- 不改变 TIF 项目数据格式。
- 不改变 SQLite manifest / sidecar 文件存储语义。
- 不改变 `manual_truth`、`editable_ai_result`、`raw_ai_prediction_backup` 的核心规则。
- 不重写 3D renderer 或训练后端。
- 不把 TIF 工作流泛化为非蚂蚁类群的新产品承诺。
- 不在真实 GPU/TIF 验收不足时一次性大规模改动所有 UI 页面。

## 重点研究流程

第二轮必须继续保护以下日常研究链路：

1. 打开 TIF 项目，切换 specimen、part 和 reslice。
2. 查看 3D volume preview、ROI preview、mask preview。
3. 使用 Local Axis 三点参考、观察侧剖切面和重切片导出。
4. 编辑 working edit / editable AI result，并保存、重开确认。
5. 接受 AI 结果为训练真值。
6. 准备训练数据、启动训练、选择模型、启动预测。
7. 导入预测结果并保持 prediction draft 与 manual truth 分离。
8. 在后台训练或系统资源紧张时，界面能明确提示哪些功能暂不可用。

## 架构目标

### 1. Layout / Page 层

新增或整理 UI layout 模块，目标是让 `TifWorkbenchWidget` 不再直接承担大段控件装配细节。

建议方向：

- `AntSleap/ui/tif_workbench_layout.py`
- `AntSleap/ui/tif_workbench_pages.py`
- `AntSleap/ui/tif_workbench_control_panels.py`

这些模块应主要负责创建控件、设置 objectName、组合页面和暴露控件引用。它们不应直接决定训练真值、预测导入、写入路径或后台任务生命周期。

### 2. Training / Prediction UI Controller

训练和预测页面现在已经有 service/core 支撑，第二轮应把 UI 控制逻辑进一步拆出。

目标职责：

- 根据当前 project / selection / backend state 刷新训练与预测按钮。
- 组织训练前置检查结果展示。
- 组织模型库选择、备注、删除和预测入口状态。
- 将用户动作转给 `TifBackendWorkflowService` 和 task manager。

建议文件：

- `AntSleap/ui/tif_backend_panel_controller.py`

### 3. Preview / GPU Resource Controller

3D preview 和 mask preview 涉及 GPU、OpenGL、memmap、大数组和缓存。第二轮应把资源状态和错误恢复策略从主 Widget 中进一步拆出。

目标能力：

- 统一 preview 请求、取消、降级、失败提示。
- 对 `WinError 1455`、显存不足、OpenGL fallback、memmap 打开失败提供可理解提示。
- 避免资源不足时整个程序进入 CRITICAL ERROR。
- 将资源状态纳入状态摘要，方便 Agent 和日志排查。

建议文件：

- `AntSleap/ui/tif_preview_controller.py`
- `AntSleap/core/tif_resource_policy.py`

### 4. Local Axis UI Controller

Local Axis 的核心计算和 service 已存在，但 UI 交互仍较密集。第二轮应继续拆薄。

目标职责：

- 管理三点参考选择、观察侧剖切面、roll reference 状态和导出按钮状态。
- 将 Local Axis draft 与当前 selection/context 绑定。
- 将 UI 结果转给 `TifLocalAxisService` 和 task manager。
- 保持三点选择和重切片操作在 preview busy 状态下仍按第一轮修复后的规则运行。

建议文件：

- `AntSleap/ui/tif_local_axis_controller.py`

### 5. 主 Widget 收束

第二轮完成后，`TifWorkbenchWidget` 应更接近“入口和协调器”：

- 初始化 project、service、controller。
- 接收高层 signal。
- 协调页面切换。
- 统一刷新总状态。
- 保留兼容入口和外部测试导入路径。

不追求一次性把 `tif_workbench.py` 减到很小，但应继续降低主文件职责密度。

## 成功标准

第二轮完成后应满足：

- `tif_workbench.py` 行数继续明显下降，目标减少 2500-4000 行。
- layout / backend panel / preview / Local Axis 至少三个方向完成独立控制器或模块。
- 训练、预测、3D preview、Local Axis 的按钮状态更容易定位和测试。
- 资源不足错误不会直接变成 CRITICAL ERROR，而是以可恢复状态提示用户。
- 第一轮的数据安全 guard 和 service/task 架构保持不被绕过。
- 一键验证脚本继续覆盖所有测试文件。
- 真实人工验收至少覆盖：界面启动、右侧栏、TIF 打开、3D preview、Local Axis 三点、重切片、保存重开、训练/预测入口。

## 风险与控制

第二轮比第一轮更容易触碰 Qt 控件初始化顺序、信号连接、3D canvas 生命周期和按钮刷新。因此必须按小阶段推进：

- 每阶段只拆一个页面或控制器。
- 每阶段保留原外部入口和 objectName。
- 每阶段跑对应 GUI 和 service 测试。
- GPU/3D preview 相关阶段必须在真实显卡空闲时人工复核。
- 如果某阶段导致人工验收成本明显上升，应停在当前阶段，不继续深拆。

## 需要用户确认的问题

1. 第二轮是否继续放在当前分支，还是从当前状态新建 `codex/tif-workbench-architecture-refactor-round2` 分支？
2. 是否先提交当前未提交的第一轮补丁和测试，再开始第二轮代码改动？
3. 第二轮是否把 `tif_workbench.py` 行数降到 12000 以下作为硬目标，还是以稳定拆分为主？
4. 资源不足时是否允许进入只读/预览受限模式，而不是阻止整个项目打开？
5. 第二轮是否优先拆 TIF 页面，暂不触碰 PDF、2D/STL 和 Agent Center？
