# TaxaMask 第四轮架构优化：主窗口需求与设计草案

文档编号：TaxaMask Architecture Refactor Round 4

日期：2026-07-11

状态：`accepted`；用户于 2026-07-11 接受第 14 节全部建议方案，业务代码迁移尚未开始，下一步为 Stage 0 正式基线

工作分支：`codex/taxamask-architecture-refactor-round4`

分支基线：`d710cf0`（当前线上 `main`）

## 1. 项目定位

本项目正式定义为 **TaxaMask 第四轮架构优化**。前三轮虽然主要围绕 TIF 工作台展开，但本质上已经在整理 TaxaMask 的整体任务生命周期、数据安全、信号连接、测试结构和 Agent 上下文；第四轮继续沿用同一架构优化序列，核心范围转向 `AntSleap/main.py` 和 `MainWindow`。

第四轮目标是让启动中心、项目打开、2D/STL 标注、Blink、PDF evidence、Agent、训练、预测、VLM 和设置等工作流能够分别维护、测试和恢复。已经验收的 TIF controller、GPU 预览、Local Axis、标签角色和性能策略视为稳定内部子系统；第四轮只整理主窗口与 TIF 的进入、退出、项目路由、主题/语言和 Agent context 对接，不重新拆 TIF 内部工作流。若主窗口迁移暴露 TIF 集成回归，可以做对接修复，但不得借机启动新的 TIF 内部架构轮次。

本项目不是为了机械减少行数。主要收益目标是：

- 单个研究工作流的代码阅读和审查范围减少 60%-85%。
- 常见问题定位时间减少 30%-50%。
- 同文件修改冲突风险减少 40%-60%。
- 在明确加入惰性初始化和重复刷新治理后，启动速度改善 5%-15%，常见工作流切换改善 10%-25%，超过 250 ms 的 UI 阻塞事件减少 20%-50%。
- 只移动代码而不改变初始化/刷新策略时，不宣称性能提升，允许的预期仅为 0%-3%。

上述维护比例是基于当前文件规模和修改集中度的工程目标，不是已经实测的结果。Stage 0 必须建立可重复性能基线，最终只使用前后实测值对外报告。

## 2. 当前实测基线

统一使用 UTF-8 源文件物理行和 Python AST 统计：

| 指标 | 当前值 |
| --- | ---: |
| `AntSleap/main.py` 物理行 | 16,024 |
| 顶层类 | 22 |
| 顶层函数 | 35 |
| 全文件方法 | 594 |
| 全文件 `.connect(...)` | 194 |
| 私有方法 | 414 |
| `self.<field> = ...` 状态赋值行 | 675 |
| `MainWindow` 物理行 | 9,483 |
| `MainWindow` 方法 | 390 |
| `MainWindow` `.connect(...)` | 128 |
| `MainWindow` 不少于 50 行的方法 | 42 |
| `MainWindow` 不少于 100 行的方法 | 10 |
| `MainWindow.__init__` | 668 行 |
| 其他独立线程、Widget、Dialog、Panel 类 | 约 4,793 行 |
| 2026-04-01 以来修改 `main.py` 的提交 | 47 |
| 同期累计增删 | 18,711 行 |
| 五个关键测试文件直接引用 main/MainWindow/Dialog 的行 | 192 |

最大责任块包括：

- `ModelSettingsDialog`：2,135 行、67 个方法、22 处信号连接，`__init__` 为 800 行。
- `RouteManagementPanel`：667 行、34 个方法。
- `MainWindow`：9,483 行、390 个方法、128 处信号连接。
- `MainWindow._compact_agent_context`：202 行。
- `MainWindow.refresh_ui`：190 行。
- `MainWindow.open_project_path`：150 行。

当前问题不是单个算法太复杂，而是多个研究工作流共享同一个 UI 状态容器、初始化顺序和信号网络。近三个多月所有相关改动集中在同一路径，导致改 Agent、Blink、项目打开或训练时都需要重新判断其他工作流是否受影响。

## 3. 研究工作流边界

### 3.1 启动与运行环境

- Qt WebEngine、WSL/Linux 软件渲染环境变量必须在导入 `cv2`、PySide6 和 WebEngine 前设置。
- runtime log、`faulthandler`、全局异常处理和日志清理行为保持可追溯。
- Windows、Linux、macOS 和源码/包两种导入方式继续兼容。
- 启动失败时仍能留下可定位日志，不能因拆模块丢失早期异常。

### 3.2 Start Center / 工作流导航 / Agent

- Start Center、最近项目、项目摘要、Agent 状态和三个工作流入口有独立 view/controller 边界。
- `Agent Center`、2D/STL、TIF、PDF evidence 之间切换时保留当前项目和现场上下文。
- Agent context 继续经过紧凑字段预算、路由增强和中英文展示，不丢失 TIF、Blink、PDF 或设置诊断字段。
- Agent Dashboard/WebEngine 的生命周期不与 TIF GPU renderer 重新耦合。

### 3.3 项目生命周期与存储路由

- 新建、打开、最近项目、关闭、迁移、SQLite database 到 manifest 定位、备份、legacy JSON 导出和图片路径迁移形成一个明确责任主体。
- 2D SQLite、TIF SQLite、STL rendered project 和 legacy JSON 的识别顺序保持不变。
- 项目切换前处理待保存状态和后台任务；旧项目回调不能刷新新项目。
- 不修改项目 schema、manifest、SQLite 表、sidecar、备份目录或迁移结果格式。

### 3.4 2D/STL 图像与标注工作流

- 图像导入、panel split、image group、文件列表、part tree、当前图像/部位选择和标注画布刷新有明确所有者。
- PDF candidate provenance、文献描述、STL rendered views 和普通图像继续保持可审计来源。
- 自动框、VLM 草稿和外部模型预测不能自动成为人工确认真值。
- 删除图片、删除标签、批量接受 AI 草稿等高风险动作保留确认、保存和恢复边界。

### 3.5 Blink / SAM / 模型路由

- Blink 入口、parent-child context、auto shrink、专家训练、路由选择和模型说明分别对接稳定 command/state。
- SAM point/box prompt、加载状态和失败回调不依赖 MainWindow 私有字段拼接。
- Parent 2D/STL、Blink child、TIF volume segmentation 和 TIF Local Axis 后端仍是四条独立路线。

### 3.6 训练、预测、VLM 与导出

- 内置训练、外部训练、训练报告、模型列表、预测、批量推理、VLM 预标注和 dataset export 分离 worker 生命周期与 UI 协调。
- 每个后台结果带当前 project/image/part/run context；停止、失败和旧回调有统一处理规则。
- VLM 候选、external prediction、auto box 和 manual annotation 的来源与 review status 不改变。
- 大批量运行继续保留进度、取消、日志和部分失败总结。

### 3.7 设置、主题和语言

- General、2D/STL model、TIF model、PDF multimodal API 设置继续使用现有配置格式和验证规则。
- 主题、语言、objectName、菜单、快捷键、tab 顺序和按钮语义不变，除非单独确认 UI 需求。
- 设置对话框调用 Ask Agent 时继续提供当前配置诊断，但不暴露 API key 或私有路径内容。

## 4. 数据安全与兼容边界

本轮必须保持：

- 原始图片、原始 TIF/CT、AMIRA、STL 和 PDF 不被覆盖。
- 2D SQLite 和 TIF SQLite schema 不变。
- 2D manual annotation、AI draft、external prediction 和 review metadata 角色不变。
- TIF `working_edit`、`manual_truth`、`editable_ai_result`、`raw_ai_prediction_backup`、accepted mask 和 reslice 角色不变。
- PDF evidence 只作为文献证据和候选来源，不自动进入 2D 或 TIF 训练真值。
- 模型权重、训练输出、run folder 和导出目录结构不变。
- 当前 `main.py` 的公开导入保持兼容。迁移期间 `from main import MainWindow`、`from AntSleap.main import ModelSettingsDialog` 等入口通过显式 re-export 保留，直到调用方和测试完成迁移。
- 不通过删除日志、错误提示、安全 guard、翻译或恢复入口达成行数目标。

## 5. 非目标

- 不在 TaxaMask 第四轮中继续拆 TIF 内部 controller，不重写 GPU renderer 或 Local Axis 数学。
- 不修改 Locator、SAM、Blink、VLM、训练或预测算法。
- 不改变项目格式、数据库 schema、模型 manifest 或 backend contract。
- 不重新设计主界面视觉结构。
- 不把所有逻辑移动到一个新的巨大 controller。
- 不一次性重写 `MainWindow`。
- 不把代码移动和性能提升混为一谈。
- 不在中间阶段更新根目录 `CHANGELOG_zh.md` 或 `LLM_CONTEXT_DETAILED.md`；只在用户验收整体候选或明确要求同步时更新。

## 6. 目标架构

### 6.1 `main.py`：启动入口与兼容门面

最终主要负责：

- 最早期运行环境准备。
- 应用启动和全局异常入口。
- 导入并创建 `MainWindow`。
- 对历史公开类提供阶段性 re-export。

`main.py` 不再直接承载完整设置 UI、训练报告、项目路由、图像列表、Blink、VLM 和预测实现。

### 6.2 Main Window Shell / View / Signal Router

建议建立主窗口 shell、受限 view adapter 和 signal router：

- Shell 创建顶层窗口、工作区、状态栏和 controller。
- View adapter 只暴露指定控件和展示命令，不允许 controller 任意访问完整 MainWindow。
- Signal router 登记静态连接、动态 worker 连接、解绑和单次触发检查。
- Coordinator 只处理 active workflow、active project、未保存状态、后台 busy 和跨工作流导航，不承载具体标注或模型算法。

### 6.3 建议责任模块

具体文件名在 Stage 0 复核后冻结，建议责任边界如下：

| 模块责任 | 包含内容 | 不应包含 |
| --- | --- | --- |
| runtime/bootstrap | 环境、日志、异常、应用启动 | Qt 页面业务 |
| workers | inference、training、import、export worker | MainWindow 控件访问 |
| settings/dialogs | model/general/TIF settings、报告、文献对话框 | 项目全局生命周期 |
| start center/navigation | 卡片、最近项目、摘要、工作流切换 | 2D 标注细节 |
| agent context | context 收集、压缩、路由和转交 | WebEngine 进程实现 |
| project lifecycle | 新建/打开/迁移/关闭/备份/路径恢复 | 标注算法 |
| image navigation | image group、文件列表、part tree、选择 | 训练 worker |
| annotation/SAM | 画布动作、SAM prompt、保存和来源状态 | Blink 训练 |
| Blink workflow | parent-child context、auto shrink、专家训练 | TIF controller 内部逻辑 |
| training/model | 模型列表、preflight、训练、报告 | VLM candidate 写入 |
| VLM/prediction/export | VLM run、预测导入、review、批推理、导出 | project schema 变更 |
| coordinator | 跨工作流顺序和 busy/unsaved 决策 | 各工作流具体实现 |

## 7. 信号、状态和后台任务要求

1. 每个 controller 明确拥有的状态、worker/thread 引用和信号范围。
2. 控件信号优先直接连接 controller command，不长期保留 `button -> MainWindow wrapper -> controller`。
3. 动态 worker 信号必须在结束、取消、关闭项目和销毁窗口时清理。
4. 同一动作一次点击只执行一次；主题/语言刷新和项目重开不得重复连接。
5. 后台结果必须验证 project/image/part/run token，拒绝陈旧结果。
6. 未保存确认、项目关闭和写任务继续由 coordinator 串行决定，不能由多个 controller 同时弹窗。
7. 新 controller 不默认持有完整 MainWindow；必须使用 port/protocol、view adapter、state 或显式依赖。
8. 现有 `QTimer.singleShot`、异步预加载和延迟保存必须登记触发条件和取消条件。

## 8. 量化目标

### 8.1 结构目标

| 指标 | 当前 | 候选验收目标 |
| --- | ---: | ---: |
| `main.py` 物理行 | 16,024 | 2,000 以下，主要作为 bootstrap/re-export |
| `MainWindow` 类物理行 | 9,483 | 4,500 以下 |
| `MainWindow` 方法 | 390 | 220 以下 |
| `MainWindow.__init__` | 668 行 | 300 行以下 |
| `MainWindow` `.connect(...)` | 128 | 60 以下 |
| 不少于 100 行的 MainWindow 方法 | 10 | 2 以下，且逐项说明 |
| 单个新 workflow controller | - | 建议 800-1,500 行；超过 1,500 行强制复核 |
| 单个新 dialog/panel 文件 | - | 建议 1,500 行以下；复杂模型设置可拆 view/mapper/validator |
| 旧测试对 MainWindow 私有实现引用 | Stage 0 精确统计 | 至少减少 60% |

`main.py` 行数下降主要来自真实责任迁移。兼容 re-export、早期 runtime guard 和必要入口不因追求数字删除。

### 8.2 性能目标

Stage 0 必须在同一机器、同一 Python 环境、同一 fixture 下记录至少 10 次重复测量的中位数和 P95：

- 进程启动到 Start Center 可交互。
- Start Center 进入 2D/STL。
- Start Center 进入 TIF 空工作台。
- 打开小型 2D SQLite 项目并显示首图。
- 2D 项目内切换 image/part。
- 打开/关闭 Model Settings。
- 打开 Agent Center 到可接受 context。
- 空闲 RSS、进入 2D 后 RSS、进入 TIF 空工作台后 RSS。
- 超过 100 ms 和 250 ms 的主线程阻塞事件数量。

验收线：

- 纯迁移阶段任何关键路径中位数不得回退超过 5%，P95 不得回退超过 10%。
- 启动惰性加载完成后，Start Center 可交互中位数目标改善 5%-15%。
- 重复刷新和信号治理完成后，常见工作流切换中位数目标改善 10%-25%。
- 超过 250 ms 的主线程阻塞事件目标减少 20%-50%。
- 非 TIF 空闲/2D 状态 RSS 目标减少 5%-15%；TIF 大体积内存由 volume 数据主导，本轮不承诺明显下降。
- 未达到性能改善不等于架构失败，但必须诚实报告；不能以行数下降代替性能证据。

### 8.3 维护收益目标

- 单个工作流常规修改的主要源码审查范围控制在 800-2,000 行，预计比当前 MainWindow 范围减少 60%-85%。
- 新增功能默认只修改一个 workflow controller/view、对应 service/core 和测试，不再修改完整 MainWindow。
- 问题日志和 Agent route 能指向明确责任模块，问题定位时间目标减少 30%-50%。
- 连续阶段提交分布到独立模块，同文件修改冲突风险目标减少 40%-60%。
- 每个阶段记录实际修改文件数、主文件变化、测试迁移和缺陷定位时间；最终用实证修正上述估算。

## 9. 测试设计

### 9.1 测试层次

1. **Runtime/bootstrap**：环境变量设置顺序、日志、异常入口、包/源码导入兼容。
2. **Dialog/view model**：设置值映射、验证、翻译、主题和 Agent context。
3. **Workflow controller**：使用 fake view/state/dependency 验证完整命令和状态转换。
4. **Signal contract**：连接目标、单次触发、动态解绑、关闭后回调和顺序。
5. **Project lifecycle**：2D/TIF/STL/legacy 路由、迁移、备份、关闭和陈旧回调。
6. **GUI key path**：启动、打开项目、图像/部位切换、Blink、Agent、TIF、PDF、训练和导出入口。
7. **真实人工验收**：使用研究者现有代表性项目，不把私有数据提交到仓库。

### 9.2 测试迁移规则

- 每迁移一个责任块，先建立新模块直接测试，再迁移 `tests/test_gui_smoke.py`、`tests/test_blink_bridge.py`、`tests/test_ui_localization.py`、`tests/test_ui_polish_scope.py` 和 `tests/test_reporting_routes.py` 的直接调用。
- `AntSleap.main` 保留兼容 re-export 测试，但新行为测试不得默认从 `main.py` 导入实现类。
- 新测试不得通过大量 `window._private_field = ...` 拼装状态；使用 command/state/fake dependency。
- GUI smoke 只保留真实入口和跨模块集成，不承担所有业务分支。
- 每阶段更新测试台账、信号台账、公开兼容入口和私有引用数量。
- 不删除测试以制造通过；重复测试删除必须说明等价覆盖位置。

## 10. 分阶段研究工作流

每个 Stage 必须依次达到 `planned -> candidate -> verified`，但不要求研究者对每个低风险搬迁阶段逐项人工确认。建议设置五个用户确认门：需求与 Stage 0 基线、Stage 2 独立模块迁移、Stage 4 项目生命周期、Stage 8 整体候选、Stage 9 真实研究流程终验。任何涉及项目写入、真值角色、后台回调或可见工作流变化的阶段，即使不在固定确认门，也必须暂停并请求确认。

### Stage 0：正式基线与迁移台账

- 固化行数、类、方法、信号、状态字段、公开导入、测试引用和近期修改热区。
- 建立性能测量工具和小型无私有数据 fixture。
- 为 390 个 MainWindow 方法标记责任、调用方、信号、测试和迁移阶段。
- 输出风险分级和最终文件名建议，用户确认后进入 Stage 1。

### Stage 1：Runtime、Worker 与小型基础 Widget

- 提取最早期 runtime/bootstrap，验证导入顺序。
- 提取 inference、VLM、training、import、export worker。
- 提取 NoWheel 控件和 ImageGroup drag/drop Widget。
- 保持 `main.py` re-export，不改变 MainWindow 行为。

### Stage 2：Dialog、Report、Route 与 Settings

- 迁移 training preflight/report/result browser、literature dialog、route panel、general/TIF/model settings。
- 将 800 行 ModelSettings `__init__` 拆为页面构建、值映射、验证和 Agent context。
- 同步本地化、主题、设置 schema 和 GUI 测试。

### Stage 3：Main Window Shell、Start Center 与 Agent Context

- 分离 MainWindow 状态初始化、顶层布局、Start Center、project console 和工作流导航。
- 分离 Agent context 收集、压缩和路由转交。
- 建立受限 view adapter、signal router 和 coordinator 骨架。

### Stage 4：项目生命周期与存储路由

- 迁移新建、打开、最近项目、迁移、关闭、备份、legacy export 和路径恢复。
- 覆盖 2D/TIF/STL/SQLite/legacy JSON 的完整路由和失败恢复。
- 未保存确认、后台任务关闭和陈旧回调形成统一 contract。

### Stage 5：2D 图像导航、Part Tree 与文献桥接

- 迁移 image import、panel split、image group、文件列表、part tree 和 image/part selection。
- 迁移 PDF/STL provenance 和 literature description bridge。
- 保持当前标注画布刷新、选择恢复和删除安全行为。

### Stage 6：Annotation、SAM 与 Blink

- 迁移 annotation box/polygon、SAM prompt、measurement。
- 迁移 Blink context、auto annotate、auto shrink、专家训练和 route settings。
- 信号直接对接责任 controller，删除只转发的 MainWindow wrapper。

### Stage 7：Training、Prediction、VLM 与 Export

- 迁移训练 preflight/worker/report、模型选择、预测和批量 inference。
- 迁移 VLM run、进度、取消、candidate 应用、AI draft 接受和 SQLite run 记录。
- 迁移 dataset export，并验证部分失败、停止和重开恢复。

### Stage 8：Shell 收束、测试迁移与性能治理

- 清理兼容 wrapper 和重复状态。
- 完成 signal router、动态 worker 连接和 controller 生命周期审计。
- 对明确测出的启动和切换热点实施惰性加载、刷新合并或缓存复用。
- 达成结构、私有测试引用和性能非回退门。

### Stage 9：完整回归与真实研究流程验收

- 运行完整自动化测试、编译、静态调用和差异检查。
- 使用代表性 2D SQLite、Blink、TIF、PDF evidence 和 Agent 流程人工验收。
- 核对训练、预测、VLM、导出、项目关闭和失败恢复。
- 用户确认后再同步 `LLM_CONTEXT_DETAILED.md`、`CHANGELOG_zh.md` 和 Release 说明，并决定是否合并回 `main`。

## 11. 每阶段强制交付

每个阶段必须同时提供：

- 责任迁移清单和保留入口理由。
- 状态所有权清单。
- Qt 信号连接/解绑台账。
- 新模块直接测试和 GUI key-path 测试。
- 行数、方法、信号、私有测试引用对比。
- 启动/切换/内存非回退结果。
- 对 2D、Blink、TIF、PDF、Agent、训练和预测的影响说明。
- 可单独回退的本地提交。
- 阶段 review 文档和 `verified` 记录；五个关键确认门另记用户 `accepted`。

## 12. 失败恢复与 Git 策略

- 所有工作保留在 `codex/taxamask-architecture-refactor-round4`，用户确认候选前不直接提交到 `main`。
- 每个 Stage 使用独立提交，失败时回退该 Stage，不跨阶段混合回滚。
- 不修改用户项目或把私有项目复制进仓库；临时 fixture 只放 `.tmp_validation/` 并在结束前清理。
- 不使用 destructive Git 命令。
- 是否推送该优化分支、何时合并、是否更新现有 Release，均在候选验收后由用户确认。

## 13. 成功标准

- `main.py` 成为清晰的启动/兼容门面，而不是业务实现仓库。
- MainWindow 只保留顶层 shell、明确 view 和少量跨工作流协调。
- 项目生命周期、2D navigation、Annotation/SAM、Blink、Training、VLM/Prediction/Export、Agent 和 Settings 均有明确责任主体。
- 新 controller 不依赖完整 MainWindow 私有状态。
- 信号和 worker 生命周期可以审计，旧回调不能污染新项目或新选择。
- 2D/TIF 数据角色、SQLite、sidecar、模型和导出格式无变化。
- 自动化和真实研究流程验收通过。
- 结构目标达到；未达到项逐条提供真实依赖和后续风险，不用“已拆分”笼统代替证据。
- 性能使用前后实测报告；没有改善时明确写出，不用主文件行数冒充速度收益。

## 14. 建议方案与待确认事项

以下是建议默认方案。用户可以整体接受，也可以逐项修改。

1. **轮次定位**：建议确认本项目是 TaxaMask 第四轮架构优化，核心处理 `main.py/MainWindow`；前三轮 TIF 工作台改进统一视为 TaxaMask 第一至第三轮架构优化。第四轮冻结已验收的 TIF 内部结构，只允许必要的主窗口集成修复。
2. **性能范围**：建议包含有限性能治理。先由 Stage 0 测出启动、工作流切换、重复刷新和 UI 阻塞热点，再做惰性初始化、刷新合并和信号去重；不凭感觉改性能。
3. **结构目标**：建议保留 `main.py` 2,000 行以下、MainWindow 4,500 行以下的目标，但把责任迁移和测试闭环置于行数之前。未达数字但边界合理时允许提交证据说明，不为压行数制造第二个大文件。
4. **迁移顺序**：建议采用 Runtime/Worker -> Dialog/Settings -> Shell/Agent -> Project Lifecycle -> 2D Navigation -> Annotation/SAM/Blink -> Training/VLM/Prediction/Export -> 收束验收。该顺序先处理可独立迁移内容，再进入项目写入和研究工作流。
5. **兼容入口**：建议整个第四轮保留 `from main import ...` 和 `from AntSleap.main import ...` re-export。仓库内部调用完成迁移后仍可长期保留少量稳定导出，避免外部脚本突然失效。
6. **功能冻结**：建议确认第四轮不改变 UI 视觉结构、项目格式、SQLite schema、训练算法、模型 contract 和研究数据角色。发现独立功能需求时另开需求，不混入架构迁移。
7. **确认节奏**：建议每个 Stage 自动形成 `candidate -> verified`，用户只在五个关键门确认：Stage 0 基线、Stage 2 独立模块、Stage 4 项目生命周期、Stage 8 整体候选、Stage 9 真实终验。涉及写入、真值或可见行为变化时随时增加确认门。
8. **性能与人工验收**：建议 Stage 0 使用无私有数据 fixture 建立至少 10 次重复测量；Stage 9 由研究者使用现有代表性 2D、Blink、TIF、PDF 和 Agent 流程人工验收。自动化结果不能代替真实研究流程判断。
9. **分支策略**：建议需求确认并提交文档后，将 `codex/taxamask-architecture-refactor-round4` 推送到 GitHub 作为第三个真实线上分支，便于备份和查看；在 Stage 9 最终接受前不合并 `main`，也不创建新 Release。

## 15. 用户确认结果

2026-07-11，用户确认“按建议接受”，形成以下正式约束：

1. 本项目是 TaxaMask 第四轮架构优化；前三轮 TIF 工作台改进统一视为 TaxaMask 第一至第三轮架构优化。
2. 第四轮核心处理 `main.py/MainWindow`，冻结已验收的 TIF 内部结构，只允许必要的主窗口集成修复。
3. 性能治理只处理 Stage 0 实测热点，不凭感觉修改初始化、刷新或信号策略。
4. 保留 `main.py` 2,000 行以下、MainWindow 4,500 行以下的候选目标，但责任迁移、测试和数据安全优先于行数。
5. 采用文档规定的迁移顺序和五个用户确认门。
6. 第四轮持续保留历史 `main` 导入兼容。
7. 不改变 UI 视觉结构、项目格式、SQLite schema、算法、模型 contract 和研究数据角色。
8. Stage 0 建立无私有数据性能基线，Stage 9 使用代表性真实研究流程终验。
9. 需求文档与执行清单提交后可推送第四轮分支；最终验收前不合并 `main`、不创建新 Release。
