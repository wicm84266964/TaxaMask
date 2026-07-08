# TIF 工作台架构整理第二轮执行清单

日期：2026-07-09

分支：`codex/tif-workbench-architecture-refactor`

需求文档：`docs/tif_workbench_architecture_refactor_round2_requirements_zh.md`

第一轮基线提交：`346598b`（`整理 TIF 工作台架构与分层回归测试`）

## 执行原则

- 第二轮只在第一轮稳定基础上继续拆 UI，不重新设计数据格式。
- 先提交或明确保留当前未提交补丁，再开始第二轮代码改动。
- 每个阶段只拆一个高内聚方向，不把 layout、3D、Local Axis、训练预测混在一次大改里。
- 保留 `TifWorkbenchWidget` 外部入口和现有测试导入路径。
- 保留 objectName，避免 GUI smoke 和用户习惯断裂。
- 所有新增用户可见提示继续保持中英双语。
- 所有新控制器必须优先调用现有 service/core/task 层，不绕过第一轮 guard。
- 涉及 GPU、memmap、页面文件、显存和 OpenGL 的改动必须有人工验收记录。

## 已踩坑与避免事项

这些事项来自第一轮架构整理、回归修复和人工验收中已经出现过的问题。第二轮执行时必须主动规避，避免重复消耗人工检查时间。

### 已发生问题复盘

- [ ] 不要把“程序能打开”当作 TIF 工作台验收完成；第一轮已经证明界面能启动时，仍可能存在右侧栏溢出、按钮漏翻译、Local Axis 点选失效、资源不足崩溃等局部回归。
- [ ] 每次移动 UI 构建代码后，必须复核对应属性初始化顺序；第一轮曾因 helper 调用早于 `_panel_title_labels`、`_section_title_labels` 等注册表初始化而暴露隐患。
- [ ] 每次移动训练/预测/Local Axis 按钮或标签后，必须复核翻译表和刷新入口；第一轮曾出现训练与预测区域重新漏出英文按钮。
- [ ] 每次改右侧栏、滚动区域、页面栈或尺寸策略后，必须用普通窗口和最大化窗口各看一次；第一轮曾复发“右侧栏内容被顶出可视范围”的问题。
- [ ] 每次触碰 preview busy lock、任务锁、按钮启用矩阵或 Local Axis 页状态后，必须跑并人工复核三点参考链路；第一轮曾出现“观察侧剖切面/三个 roll reference 点点击无响应”。
- [ ] Local Axis 的三点点选、侧剖切面观察、roll reference 对齐、重切片导出、保存重开是一条链路，不能拆成互不相关的小验收；其中任一环节失效都会直接影响研究标注和部位重切片可信度。
- [ ] 不要把重切片画面模糊、mask 外接框包含周边组织等现象自动归因于本轮架构拆分；这类问题可能来自原有重采样、显示分辨率、mask 裁剪策略或外接矩形逻辑，必须先确认旧版本行为再决定是否作为新需求处理。
- [ ] 每次给后台任务增加 token/context 校验后，必须确认旧任务不会污染当前 specimen/part/reslice，同时也不能误拦截当前任务的合法回调；否则会出现按钮状态不恢复、导出完成不刷新或刷新到错误对象。
- [ ] 遇到 `WinError 1455 页面文件太小` 时，先按 Windows 提交内存/页面文件/训练 worker 占用排查；第一轮已经确认它不等同于 TIF 数据损坏，也不能让它继续变成 CRITICAL ERROR。
- [ ] 清理残留进程时必须区分孤儿 `multiprocessing.spawn` 和正在训练的有效进程；第一轮排查过后台训练会显著增加提交内存，误杀有效训练会浪费长时间实验。
- [ ] 自动化测试通过后仍要记录哪些链路没有人工看过，尤其是 GPU 3D preview、真实 TIF 重切片清晰度、真实训练/预测输出导入；这些不是纯单元测试能完全替代的。
- [ ] 如果新增 controller/service 改变了状态摘要、方法入口或按钮语义，必须同步检查给 Agent/AntCode 读取的对接文件和状态输出；否则询问 Agent 可能基于过时字段给出错误判断。

### 环境与依赖

- [ ] 始终使用 TaxaMask Conda 环境运行 GUI 和测试：`C:\Users\admin\anaconda3\envs\taxamask\python.exe`。
- [ ] 不要因为 base/default Python 缺少 `PySide6` 就安装新依赖；TaxaMask 环境已有 PySide6，应切换解释器而不是改环境。
- [ ] `tests/test_tif_workbench.py`、`tests/test_gui_smoke.py`、`tests/test_ui_polish_scope.py` 如果因为缺少 PySide6 被 skip，不能算 GUI 验证通过。
- [ ] 当前项目主要用 `unittest` 跑测试；不要假设 `taxamask` 环境一定安装了 `pytest`。

### Git 与文件状态

- [ ] 开始第二轮代码前先确认当前未提交补丁是否已单独提交，避免第一轮补丁和第二轮深拆混在一起。
- [ ] 检查待提交内容必须用 `git status --short`，不能只看 `git diff --stat`；后者不会显示未跟踪的新文件。
- [ ] 提交前必须确认没有本地项目 JSON、SQLite 数据库、TIF/CT stack、模型权重、run outputs、API 配置或私有研究数据进入 Git。

### 阶段节奏与回退点

- [ ] 每个阶段必须先完成本阶段 review、验证和本地提交，再进入下一阶段；不要把上一阶段补丁和下一阶段深拆混在一个提交里。
- [ ] 如果人工验收发现回归，先默认排查“本阶段刚移动或包装过的代码路径”，不要立刻扩大改动范围。
- [ ] 修复阶段内回归后，必须重跑该阶段建议验证和相关人工链路，再继续下一阶段。
- [ ] 每阶段 review 文档必须写清楚：改了哪些文件、哪些职责被移出主 Widget、哪些用户行为保持不变、自动测试结果、还需要人工看的真实数据链路。

### GUI 拆分

- [ ] 拆 layout 时必须保留现有 objectName；GUI smoke 和用户操作习惯依赖这些标识。
- [ ] 右侧栏必须在普通窗口和最大化窗口下都能滚动，不得再次出现控件被顶出屏幕且无法访问。
- [ ] 新增或移动按钮、标签、提示时必须同时检查中文翻译表，避免训练/预测等区域重新漏出英文。
- [ ] 不要一次性拆 layout、训练预测页、3D preview 和 Local Axis；否则人工验收成本会爆炸。
- [ ] 拆出的 builder/controller 如果依赖 `self` 上的注册表或状态容器，例如 `_panel_title_labels`、`_section_title_labels`、页面字典、按钮字典，必须确认这些属性在调用前已经初始化。
- [ ] 从主 Widget 移走 helper 时，先保留薄 wrapper 兼容入口；已有测试、Agent 对接文件或内部调用可能还引用旧方法名。
- [ ] 拆分 UI 组合代码时，不能只检查“控件能创建”；还要检查信号连接、按钮启用状态、滚动区域、翻译刷新和对象名是否仍由原链路驱动。
- [ ] UI helper 只负责创建和登记控件，不应顺手改业务规则、保存策略、训练/预测策略或数据格式；这些要留到对应 controller/service 阶段处理。

### Local Axis / Reslice

- [ ] 第一轮曾出现 preview busy lock 阻止 Local Axis 三点参考选择的问题；第二轮拆控制器时必须保留“预览类 busy 不阻止三点草稿交互”的规则。
- [ ] 三点选择、观察侧剖切面、roll reference、重切片导出和保存重开必须作为同一条人工验收链路复核。
- [ ] 切换 specimen / part / reslice 后，旧 Local Axis 导出回调不能抢焦点或刷新到当前界面。

### 后台任务与资源不足

- [ ] 后台训练运行时，不要把 3D preview / memmap 打开失败直接判定为架构回归；需要先检查 Windows 提交内存、页面文件、显存和残留 worker。
- [ ] `WinError 1455 页面文件太小` 多半表示 Windows 提交内存耗尽，不等同于物理内存用尽，也不等同于项目文件损坏。
- [ ] 清理进程时不能误杀正在训练的主进程和直属 worker；只能在确认 `multiprocessing.spawn` 的 `parent_pid` 已不存在时清理孤儿 worker。
- [ ] 第二轮应把资源不足做成可恢复提示或只读/预览受限状态，避免用户看到 CRITICAL ERROR 后误以为数据损坏。

### 测试与验证

- [ ] 新增任何 `tests/test_*.py` 后，必须加入 `scripts/run_validation_suite.py` 的默认套件，并由 `tests/test_validation_suite_script.py` 自审。
- [ ] 测试清单自审必须用相对路径生成模块名，避免把 Windows 绝对路径误拼成假模块名。
- [ ] GUI 大套件需要分块跑；`gui_smoke` 和 `ui_polish` 已经因为整组进程收尾慢暴露过超时风险。
- [ ] 自动化测试通过不等于 GPU 视觉验收通过；3D preview、重切片清晰度和真实显卡行为仍需人工看一眼。
- [ ] 全量验证完成后要清理 `__pycache__` 和 `.tmp_validation/test_*` 这类一次性验证产物，不要把临时痕迹混进工作区。
- [ ] `py_compile` 和轻量单测只能证明导入/局部契约没坏，不能代替真实 TIF 项目启动、右侧栏显示、Local Axis 三点、训练/预测按钮和 3D 预览验收。
- [ ] 新增测试要覆盖“防回归点”，尤其是曾经出过问题的右侧栏溢出、英文漏翻译、preview busy lock、旧任务回调上下文、资源不足提示。
- [ ] 如果某个 GUI 套件超时，要先分块定位失败范围，不要直接把整组测试视为失败或通过。
- [ ] 测试过程中如果后台还有训练、预测或残留 worker，要先记录资源状态；GPU/memmap 相关失败需要区分“资源被占满”和“代码回归”。

## 阶段 0：第二轮前置收口

目标：确认第一轮候选版本和后续补丁处于可审计状态，避免第二轮开始后混淆责任。

### 任务

- [ ] 记录当前 Git 状态。
- [ ] 确认第一轮主体提交为 `346598b`。
- [ ] 审核当前未提交文件，确认没有本地数据、模型权重、运行输出、API key 或项目数据库进入待提交。
- [ ] 将第一轮后续 UI 回归修复、验证脚本和新增测试整理为一个单独提交，或明确记录为第二轮前置补丁。
- [ ] 运行一键验证脚本，确认默认测试套件可完整跑完。
- [ ] 记录人工验收状态：主界面、右侧栏、翻译、Local Axis 三点、重切片、GPU 预览是否已验证。

### 验收

- [ ] Git 状态清楚，不把第一轮补丁和第二轮代码混在一起。
- [ ] 有明确可回退节点。
- [ ] 当前分支没有误包含私有研究数据。

### 建议验证

```powershell
git status --short
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --timeout 300
```

## 阶段 1：Layout / 页面骨架拆分

目标：把控件创建、页面组合和右侧栏布局从 `tif_workbench.py` 中拆出第一批，降低主 Widget 文件密度。

### 新增或调整文件

- [ ] `AntSleap/ui/tif_workbench_layout.py`
- [ ] `AntSleap/ui/tif_workbench_pages.py`
- [ ] `AntSleap/ui/tif_workbench_control_panels.py`
- [ ] `tests/test_tif_workbench_layout.py`

### 任务

- [ ] 盘点 `_build_layout()`、右侧栏、训练页、预测页、Local Axis 页、preview 页的控件创建代码。
- [ ] 先拆纯控件创建函数，不改变信号连接和业务逻辑。
- [ ] 保留现有 objectName。
- [ ] 保留现有中英文文案来源。
- [ ] 确保右侧栏滚动区域、最大化窗口和控件尺寸策略不回退。
- [ ] 对拆出的 layout 函数增加轻量测试，确认关键控件存在。

### 验收

- [ ] 程序能正常启动并进入 TIF 工作台。
- [ ] 右侧栏不溢出。
- [ ] 训练/预测/Local Axis 页面关键按钮仍可见。
- [ ] GUI smoke 和 UI polish 相关测试通过。

### 建议验证

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m py_compile AntSleap\ui\tif_workbench.py AntSleap\ui\tif_workbench_layout.py
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite gui_smoke --suite ui_polish --timeout 120
```

## 阶段 2：训练 / 预测面板控制器

目标：把训练和预测页面的按钮状态、模型库 UI、后端前置检查和结果呈现从主 Widget 中拆出。

### 新增或调整文件

- [ ] `AntSleap/ui/tif_backend_panel_controller.py`
- [ ] `tests/test_tif_backend_panel_controller.py`

### 任务

- [ ] 盘点训练/预测相关 UI 方法：后端配置、样本检查、训练启动、预测启动、模型库刷新、模型删除、结果导入。
- [ ] 将按钮启用/禁用矩阵移到 controller。
- [ ] controller 调用 `TifBackendWorkflowService`、`TifTaskManager` 和现有 project/core guard。
- [ ] 保留训练/预测中文文案和错误提示。
- [ ] 保留 run-scoped 输出目录、manifest、日志路径和取消状态。
- [ ] 对模型库删除、训练样本选择、prediction draft 导入入口增加 controller 层测试。

### 验收

- [ ] 训练/预测按钮中文正常。
- [ ] 没有训练样本时显示可理解提示。
- [ ] 训练和预测不会绕过 `manual_truth` / prediction policy。
- [ ] 取消或失败后按钮状态能恢复。

### 建议验证

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite tif_services --suite tif_model_backends --suite tif_workbench --timeout 300
```

## 阶段 3：Preview / 资源控制器

目标：把 3D preview、mask preview、memmap 加载和资源不足提示整理到专门控制器或 policy 中。

### 新增或调整文件

- [ ] `AntSleap/ui/tif_preview_controller.py`
- [ ] `AntSleap/core/tif_resource_policy.py`
- [ ] `tests/test_tif_resource_policy.py`
- [ ] `tests/test_tif_preview_controller.py`

### 任务

- [ ] 梳理 `image_volume`、`label_volume`、`edit_volume`、`part_mask_volume` 的加载入口。
- [ ] 对 `WinError 1455`、`MemoryError`、OpenGL 初始化失败、GPU fallback 增加统一分类。
- [ ] 资源不足时允许项目继续打开，必要时进入只读或编辑受限状态。
- [ ] UI 显示明确提示：系统提交内存/页面文件不足、显存不足、预览暂不可用、可关闭训练或降低 worker。
- [ ] 避免 preview 失败直接触发 CRITICAL ERROR。
- [ ] 将资源状态写入状态摘要，供 Agent 和日志使用。

### 验收

- [ ] 在资源不足时，用户不会误以为项目文件损坏。
- [ ] 资源恢复后可以重新加载 specimen 或 preview。
- [ ] 3D preview 正常机器上不降级。
- [ ] mask/label 加载失败不会污染保存状态。

### 建议验证

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite tif_preview_export --suite tif_workbench --timeout 300
```

人工验收：

- [ ] 显卡空闲时打开真实 TIF 项目，确认 3D preview 正常。
- [ ] 后台训练运行时打开 TIF 项目，确认资源不足提示可理解且程序不崩。

## 阶段 4：Local Axis UI 控制器

目标：把 Local Axis 三点参考、观察侧剖切面、roll reference 状态和导出按钮状态从主 Widget 中进一步拆出。

### 新增或调整文件

- [ ] `AntSleap/ui/tif_local_axis_controller.py`
- [ ] `tests/test_tif_local_axis_controller.py`

### 任务

- [ ] 盘点 Local Axis UI 方法：draft 创建、target 点、axis 点、roll reference 点、侧剖切面、导出、reslice 树刷新。
- [ ] 保留第一轮修复：preview busy lock 不应阻止 Local Axis 三点草稿交互。
- [ ] controller 调用 `TifLocalAxisService` 和 task manager。
- [ ] 旧任务回调必须匹配 specimen/part/reslice 后才刷新 UI。
- [ ] 增加三点选择、导出按钮状态、切换 part 后旧导出不抢焦点的测试。

### 验收

- [ ] 三个参考点可点选。
- [ ] 观察侧剖切面可用于 roll reference。
- [ ] 重切片导出可用。
- [ ] 切换 specimen/part 后旧导出结果不污染当前界面。

### 建议验证

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --suite tif_preview_export --suite tif_workbench --timeout 300
```

人工验收：

- [ ] 使用真实 TIF part 点选三个参考点。
- [ ] 执行一次重切片。
- [ ] 保存项目并重开，确认 reslice 记录仍在。

## 阶段 5：主 Widget 收束和兼容清理

目标：整理主 Widget 作为协调器，删除重复包装、死代码和明显过时的内部 helper。

### 任务

- [ ] 对 `tif_workbench.py` 做方法分组复查。
- [ ] 删除已经由 controller/service 接管的重复逻辑。
- [ ] 保留外部测试依赖的兼容入口，必要时加薄 wrapper。
- [ ] 检查 import 循环和启动性能。
- [ ] 记录主文件行数变化。
- [ ] 更新第二轮复核记录。

### 验收

- [ ] `tif_workbench.py` 行数减少 2500-4000 行，或有明确解释为何未达到。
- [ ] 现有 GUI 测试不因方法移动大面积脆裂。
- [ ] 文档说明后续新增功能优先落到 controller/service/core/task。

## 阶段 6：第二轮验证和候选版本收口

目标：将第二轮整理收束为可审计候选版本。

### 任务

- [ ] 运行全量一键验证。
- [ ] 运行 `py_compile` 覆盖新增 controller/layout/resource 文件。
- [ ] 人工验收主界面、TIF 打开、3D preview、Local Axis、训练/预测入口、保存重开。
- [ ] 检查 Git 状态，排除本地项目、数据库、模型权重、run outputs、API 配置。
- [ ] 新增第二轮复核记录。
- [ ] 视需要更新 `LLM_CONTEXT_DETAILED.md`，但不把它当作每个小改动的流水账。

### 验收

- [ ] 自动化全量测试通过。
- [ ] 人工浅验收通过。
- [ ] GPU/资源相关边界已记录。
- [ ] 可以作为第二轮候选提交或 PR。

### 建议验证

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --timeout 300
git status --short
```

## 第二轮完成判断

满足以下条件时，第二轮可以认为完成：

- [ ] 至少 layout、backend panel、preview、Local Axis 四个方向中完成三个。
- [ ] `tif_workbench.py` 职责密度明显下降。
- [ ] 训练/预测、3D preview、Local Axis 的 UI 状态更容易单独测试。
- [ ] 资源不足错误能被用户理解并恢复。
- [ ] 第一轮数据安全和任务生命周期收益没有回退。
- [ ] 用户完成真实项目人工验收后确认可以合并。
