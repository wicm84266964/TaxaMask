# TaxaMask 第四轮架构优化执行清单

日期：2026-07-11

状态：`Stage 9 automation verified / researcher acceptance pending`；Stage 1-9 实施与自动化验证已连续完成，等待统一人工验收；Stage 0 之后未再推送 GitHub

需求文档：`docs/taxamask_architecture_refactor_round4_requirements_zh.md`

工作分支：`codex/taxamask-architecture-refactor-round4`

分支基线：`d710cf0`（创建分支时的线上 `main`）

## 1. 已确认范围

- [x] 本项目定义为 TaxaMask 第四轮架构优化。
- [x] 前三轮 TIF 工作台改进视为 TaxaMask 第一至第三轮架构优化。
- [x] 第四轮核心处理 `AntSleap/main.py` 和 `MainWindow`。
- [x] 已验收的 TIF 内部 controller、GPU preview、Local Axis、标签角色和性能策略保持冻结。
- [x] 允许修复主窗口迁移暴露的 TIF 集成回归，但不继续拆 TIF 内部结构。
- [x] 包含基于实测热点的有限性能治理。
- [x] 不改变 UI 视觉结构、项目格式、SQLite schema、算法、模型 contract 和研究数据角色。
- [x] 第四轮持续保留历史 `main` 导入兼容。
- [x] 最终验收前不合并 `main`、不创建新 Release。

## 2. 当前基线快照

以下为需求研究阶段已取得的初始快照。Stage 0 必须使用可重复脚本重新生成并留档，不能直接把本表当成正式基线证据。

| 指标 | 初始快照 | Stage 0 正式值 | 最终值 |
| --- | ---: | ---: | ---: |
| `main.py` 物理行 | 16,024 | 16,024 | 763 |
| 顶层类 | 22 | 22 | 1（MainWindow 兼容外壳） |
| 顶层函数 | 35 | 35 | 0；启动函数迁入 runtime 模块后 re-export |
| 全文件方法 | 592（AST 正式口径） | 592 | 1（MainWindow.__init__） |
| 全文件 `.connect(...)` | 194 | 194 | 0；30 个责任模块合计 194 |
| 私有方法 | 413（Stage 0 纠正初始估算） | 413 | 0 个实现私有方法 |
| 状态赋值行 | 658（Stage 0 纠正初始估算） | 658 | MainWindow 直接可写状态 0 |
| `MainWindow` 物理行 | 9,483 | 9,483 | 36 |
| `MainWindow` 方法 | 390 | 390 | 1 |
| `MainWindow` `.connect(...)` | 128 | 128 | 0 |
| `MainWindow.__init__` | 668 行 | 668 行 | 13 行 |
| 不少于 100 行的 MainWindow 方法 | 10 | 10 | 0 |
| 五个关键测试文件直接引用 main/MainWindow/Dialog 的行 | 324（Stage 0 完整模式） | 324 | MainWindow 直接私有引用 0 |

历史修改热度初始快照：2026-04-01 以来 47 个提交修改 `main.py`，累计增删 18,711 行。Stage 0 需记录统计命令、时间范围和结果文件。

## 3. 阶段状态规则

每个 Stage 使用以下状态：

- `planned`：责任、风险、测试和验收已经设计。
- `candidate`：代码和测试已落地，但尚未完成全部验证。
- `verified`：自动化、静态审计、性能非回退和阶段文档通过。
- `accepted`：位于用户确认门，并已获得用户明确接受。

低风险 Stage 不要求用户逐阶段等待，但必须达到 `verified` 才能继续。出现以下情况时必须暂停并增加用户确认门：

- 项目写入、SQLite、迁移、备份或导出行为变化。
- manual annotation、AI draft、prediction、TIF truth role 或来源 metadata 变化。
- 后台任务取消、关闭项目或陈旧回调规则变化。
- 用户可见入口、按钮、菜单、工作流顺序或错误提示语义变化。
- 性能优化需要改变加载时机并可能影响首次操作体验。

## 4. 五个用户确认门

| 确认门 | 范围 | 状态 |
| --- | --- | --- |
| Gate A | 需求与 Stage 0 正式基线 | accepted（2026-07-11） |
| Gate B | Stage 1-2 Runtime/Worker/Dialog/Settings | review recorded；verified 后已连续执行 |
| Gate C | Stage 3-4 Shell/Agent/项目生命周期 | review recorded；verified 后已连续执行 |
| Gate D | Stage 5-8 全工作流迁移与整体候选 | review recorded；verified 后已连续执行 |
| Gate E | Stage 9 真实研究流程终验 | automation verified；等待人工验收 |

## 5. 每阶段强制联动交付

| 联动项 | 必须回答的问题 | 完成证据 |
| --- | --- | --- |
| 责任迁移 | 新模块是否拥有完整工作流，而不是只存 helper？ | 方法/类迁移台账、调用图、保留入口理由 |
| 状态所有权 | MainWindow 和 controller 是否存在两份可写状态？ | state/worker/thread owner 清单 |
| Qt 信号 | 控件和 worker 最终连接到谁，是否重复触发？ | 连接/解绑台账、单次触发测试 |
| 后台上下文 | 旧项目、旧图像或旧 run 的回调是否会污染当前状态？ | token/context/stale-result 测试 |
| 自动化测试 | 新责任主体是否被直接测试？ | controller/view model/runtime 测试和 GUI key path |
| 性能 | 当前阶段是否回退，优化是否有真实证据？ | 中位数、P95、RSS 和 UI stall 对比 |
| 研究数据安全 | 2D/TIF/PDF/模型角色和来源是否保持？ | schema/guard/import/export/reopen 测试 |
| 兼容入口 | `main.py` re-export 和外部调用是否稳定？ | import contract 测试、调用方清单 |
| 阶段指标 | 主文件是否真实失去责任？ | 行数、方法、connect、私有引用对比 |
| 恢复 | 本阶段失败能否独立回退？ | 独立提交、失败路径测试、review 记录 |

## 6. Stage 0：正式基线与迁移台账

状态：`verified / Gate A accepted`

### 6.1 结构与调用基线

- [x] 新增可重复架构统计脚本，不依赖一次性终端输出。
- [x] 记录物理行、类、函数、方法、长方法、`.connect()`、状态字段和 import 数量。
- [x] 为 390 个 MainWindow 方法登记责任工作流、调用方、信号、测试和目标 Stage。
- [x] 为 22 个顶层类登记公开导入、测试调用、外部兼容和目标 Stage。
- [x] 统计 MainWindow 私有字段/方法在生产代码和测试中的引用。
- [x] 统计动态 QThread、worker、QTimer、延迟保存和预加载入口。
- [x] 统计 `from main import ...`、`from AntSleap.main import ...` 和源码模式 fallback import。
- [x] 输出 `docs/taxamask_architecture_refactor_round4_method_inventory.md`。
- [x] 输出 `docs/taxamask_architecture_refactor_round4_signal_inventory_zh.md`。
- [x] 输出 `docs/taxamask_architecture_refactor_round4_stage0_review_zh.md`。

### 6.2 自动化与性能基线

- [x] 建立无私有数据的启动和工作流导航 fixture。
- [x] 固定 Python：`C:\Users\admin\anaconda3\envs\taxamask\python.exe`。
- [x] 每项重复 10 次，记录中位数和 P95。
- [x] 测量进程启动到 Start Center 可交互。
- [x] 测量 Start Center 进入 2D/STL。
- [x] 测量 Start Center 进入 TIF 空工作台。
- [x] 测量打开小型 2D SQLite 项目并显示首图。
- [x] 测量 2D 项目 image/part 切换。
- [x] 测量 Model Settings 打开/关闭。
- [x] 测量 Agent Center 接受 context。
- [x] 记录空闲、2D、TIF 空工作台 RSS。
- [x] 记录超过 100 ms 和 250 ms 的同步 UI 操作事件。
- [x] 运行当前完整自动化测试库存：1,091 条，1 条环境相关 skip，其余通过。

### 6.3 Gate A

- [x] Stage 0 review 达到 `verified`。
- [x] 用户确认正式基线、最终模块边界和执行顺序。
- [x] Gate A 标记 `accepted` 后进入 Stage 1。

## 7. Stage 1：Runtime、Worker 与基础 Widget

状态：`verified`

### 7.1 Runtime/bootstrap

- [x] 提取最早期 Qt WebEngine、WSL/Linux 和软件渲染环境准备到 `AntSleap/app_runtime.py`。
- [x] 保证环境变量仍在 `cv2`、PySide6 和 WebEngine 前设置。
- [x] 提取 runtime log、日志清理、`faulthandler` 和全局异常入口。
- [x] 验证 package/source 两种导入方式；跨平台逻辑保留，最终平台实机验收留在 Stage 9。

### 7.2 Worker 与基础 Widget

- [x] 迁移 inference、VLM、training、image import、external inference/training 和 export worker到 `main_window_workers.py`。
- [x] 迁移 NoWheel 控件和 ImageGroup drag/drop Widget 到 `main_window_widgets.py`。
- [x] Worker 不直接访问 MainWindow 控件，只通过输入、Signal、结果 payload 和显式 translator 通信。
- [x] `main.py` 保留兼容 re-export，旧 worker 构造调用协议保持。
- [x] 新模块直接测试、import contract、GUI smoke、UI polish、Agent、Blink、VLM 和 SQLite 回归通过。
- [x] 关键启动路径中位数改善约 5.1%，P95 改善约 11.5%，无性能回退。

## 8. Stage 2：Dialog、Report、Route 与 Settings

状态：`verified`

- [x] 迁移 TrainingPreflightDialog。
- [x] 迁移 TrainingReportDialog 和 TrainingResultBrowserDialog。
- [x] 迁移 LiteratureDescriptionDialog。
- [x] 迁移 RouteManagementPanel。
- [x] 迁移 GeneralSettingsDialog、TifModelSettingsDialog 和 ModelSettingsDialog。
- [x] 将 800 行 ModelSettings `__init__` 拆为页面构建、值映射、验证和 Agent context。
- [x] 保持设置 schema、默认值、backend contract、主题、语言和 objectName。
- [x] 设置 Ask Agent 不暴露 API key 或私有配置内容，并更新到新模块源码定位。
- [x] 迁移本地化、UI polish、报告和 GUI smoke 测试到新实现模块。
- [x] `AntSleap.main` 兼容导出测试通过。
- [x] 输出 Stage 1-2 review 和结构/性能对比。

### 8.1 Gate B

- [x] Stage 1-2 达到 `verified`。
- [ ] 用户检查设置、报告、文献和 route UI 无可见回归；按连续执行授权统一留到 Stage 9。
- [x] Gate B review 留档完成；按用户连续执行授权进入 Stage 3，不暂停等待 accepted。

## 9. Stage 3：Main Window Shell、Start Center 与 Agent

状态：`verified`

- [x] 分离 MainWindow 状态初始化和顶层 UI 创建；`__init__` 从 668 行降到 13 行。
- [x] 建立 shell、受限 view adapter、signal router 和 coordinator 骨架。
- [x] 迁移 Start Center、quick panel、project console 和 workflow card。
- [x] 迁移最近项目摘要和 Agent 状态摘要。
- [x] 迁移 Agent context 收集、压缩、路由增强和中英文 prompt。
- [x] 保持 Agent Center、2D/STL、TIF、PDF evidence 导航和返回上下文。
- [x] 保持 Agent WebEngine 与 TIF GPU renderer 的隔离策略，并按首次进入创建 PDF/TIF 工作台。
- [x] 信号单次触发和重复绑定测试通过；架构总连接保持 194 条。

## 10. Stage 4：项目生命周期与存储路由

状态：`verified`

- [x] 迁移默认目录、startup project、最近项目和 open/create 入口。
- [x] 迁移 2D SQLite、TIF SQLite、STL 和 legacy JSON 类型识别。
- [x] 迁移 database 到 manifest 定位和 legacy migration。
- [x] 迁移 backup、legacy export、migration report 和图片路径恢复。
- [x] 统一项目关闭、待保存、后台任务停止和陈旧回调规则。
- [x] 旧项目任务不能刷新新项目或覆盖当前状态；延迟保存冻结计划项目路径。
- [x] 不改变 SQLite schema、manifest、sidecar 和备份目录。
- [x] 2D/TIF/STL 新建、打开、迁移、关闭、重开和失败恢复测试通过。
- [x] 输出 Stage 3-4 review 和数据安全审计。

### 10.1 Gate C

- [x] Stage 3-4 达到 `verified`。
- [ ] 用户验收 Start Center、Agent、2D/TIF/STL 项目打开和关闭；按连续执行授权统一留到 Stage 9。
- [x] Gate C review 留档完成；按用户连续执行授权进入 Stage 5，不暂停等待 accepted。

## 11. Stage 5：2D 图像导航、Part Tree 与文献桥接

状态：`verified`

- [x] 迁移 image import 和导入控制状态。
- [x] 迁移 panel split、crop provenance 和 manual split review。
- [x] 迁移 image group、训练 scope、文件列表和右键动作。
- [x] 迁移 part tree、image/part selection 和选择恢复。
- [x] 迁移 PDF/STL provenance 和 literature description bridge。
- [x] 删除图片、移动分组和清理标签保持确认与保存边界。
- [x] 当前图像/部位切换不重复加载 pixmap；小 fixture 图片/部位切换中位数分别为 0.381/0.249 ms。
- [x] 文件列表、part tree、文献描述和 SQLite 重开测试通过。
- [x] Stage 5 review：`docs/taxamask_architecture_refactor_round4_stage5_review_zh.md`。

## 12. Stage 6：Annotation、SAM 与 Blink

状态：`verified`

- [x] 迁移 annotation box/polygon、工具状态和 measurement。
- [x] 迁移 SAM preload、point/box prompt、成功和失败回调。
- [x] 迁移 Blink parent-child context 和 workbench 入口。
- [x] 迁移 Blink auto annotate、auto shrink、batch shrink 和专家训练。
- [x] 迁移 route expert settings 和 parent model context。
- [x] Parent 2D/STL、Blink child、TIF volume、TIF Local Axis 后端保持独立。
- [x] AI 草稿、manual annotation 和 prediction 来源角色不变。
- [x] Blink bridge、SAM、route、训练策略和 GUI key-path 测试通过。
- [x] SAM 回调按 prompt 发起时的 image/part/description 写回；图片切换后不污染新图片。
- [x] Blink 子训练 progress/result/error/cancelled/finished 信号保持单次连接。
- [x] Stage 6 review：`docs/taxamask_architecture_refactor_round4_stage6_review_zh.md`。

## 13. Stage 7：Training、Prediction、VLM 与 Export

状态：`verified`

- [x] 迁移模型列表、preflight、内置/外部训练和停止流程。
- [x] 迁移训练报告发现、打开和结果浏览。
- [x] 迁移 prediction、external prediction 和 batch inference。
- [x] 迁移 VLM scope、worker 队列、进度、取消和 SQLite run 记录。
- [x] 迁移 VLM candidate 应用和 AI draft 接受。
- [x] 迁移 dataset export worker 和完成/失败总结。
- [x] 后台结果验证 project/image/part/run context。
- [x] VLM、prediction、manual truth 和 provenance 角色不变。
- [x] 训练、预测、VLM、导出和停止/失败恢复测试通过。
- [x] 图片导入、训练、批量预测、VLM 或导出运行时阻止切换项目。
- [x] 旧训练/预测/VLM 回调不会保存或更新新项目。
- [x] Stage 7 review：`docs/taxamask_architecture_refactor_round4_stage7_review_zh.md`。

## 14. Stage 8：Shell 收束、测试迁移与性能治理

状态：`verified with recorded performance gaps`

- [x] 清理只转发的 MainWindow wrapper；类体只保留构造器和公开信号。
- [x] 清理 MainWindow 直接可写状态和连接；直接状态写入 0、直接连接 0，总连接仍为 194。
- [x] 本轮未新增持有完整 MainWindow 的 controller；既有 coordinator/view adapter 只持有 callable 或受限 view contract，workflow owner 明确为 mixin。
- [x] MainWindow 直接私有实现测试引用从 Stage 0 的 146 次降到 0 次；继承 workflow 的 GUI contract 私有调用仍保留 146 次并单独统计。
- [x] 新增 Stage 5-8 contract 测试默认直接对接真实 mixin/runtime 模块。
- [x] 实施 PDF/TIF 惰性工作台、同图 pixmap 复用、文件列表局部更新、project task context、busy guard 惰性翻译和信号去重。
- [x] Stage 8 对 Stage 7 的纯迁移路径中位数回退低于 5%，P95 除 Agent context 波动外无业务路径超过 10%。
- [ ] Start Center 可交互中位数目标改善 5%-15%。
- [ ] 常见工作流切换中位数目标改善 10%-25%。
- [ ] 超过 250 ms 的主线程阻塞事件目标减少 20%-50%。
- [ ] 非 TIF 空闲/2D RSS 目标减少 5%-15%。
- [x] 未达到性能目标时已记录真实数据和原因，不以行数替代。
- [x] 输出 Stage 5-8 review、性能报告和剩余风险。
- [x] Stage 8 review：`docs/taxamask_architecture_refactor_round4_stage8_review_zh.md`。

### 14.1 Gate D

- [x] Stage 5-8 达到 `verified`，性能 stretch gaps 已单列。
- [x] 结构、信号、测试、性能和数据安全候选审计完成。
- [ ] 用户确认进入真实研究流程终验；按连续执行授权统一留到 Stage 9 人工验收。
- [x] Gate D review 留档完成；不暂停，进入 Stage 9 自动化终验。

## 15. Stage 9：完整回归与真实研究流程终验

状态：`automation verified / researcher acceptance pending`

### 15.1 自动化终验

- [x] 完整验证库存通过：18 个 suite、1,140 条测试，1 条环境相关 skip。
- [x] 全目录 Python `compileall` 通过。
- [x] 静态调用、公开导入、信号连接、字节码全局依赖和私有引用审计通过。
- [x] `git diff --check` 通过。
- [x] `.tmp_validation/` 临时产物清理完成。
- [x] Agent labeling route 与源码提示对齐当前 round4 workflow owner。
- [x] Stage 9 review：`docs/taxamask_architecture_refactor_round4_stage9_review_zh.md`。
- [x] 统一人工验收卡：`docs/taxamask_architecture_refactor_round4_acceptance_zh.md`。

### 15.2 研究者人工验收

- [ ] 启动程序并确认 Start Center 可交互。
- [ ] 打开、关闭并重开代表性 2D SQLite 项目。
- [ ] 导入图像、切换 image/part、完成标注保存并重开确认。
- [ ] 检查 panel split、image group 和文献描述来源。
- [ ] 进入 Blink，检查 parent-child context、自动流程和训练入口。
- [ ] 打开代表性 TIF 项目，切换 specimen/part/reslice 和 3D preview。
- [ ] 确认 TIF 标签表、manual truth、AI result 和 Local Axis 行为无回归。
- [ ] 打开 PDF evidence workflow 并确认候选只作为证据/候选。
- [ ] 打开 Agent Center，确认各工作流上下文准确。
- [ ] 打开 General、2D/STL Model、TIF Model 和 PDF API 设置。
- [ ] 运行代表性训练、预测、VLM 或导出小规模流程。
- [ ] 切换中英文和深浅主题。
- [ ] 关闭程序，确认后台任务、待保存和日志行为可解释。

### 15.3 Gate E

- [ ] 用户确认真实研究流程符合预期。
- [ ] 第四轮候选标记 `accepted`。
- [x] `LLM_CONTEXT_DETAILED.md` 已同步 verified candidate 当前状态；accepted 状态待用户确认。
- [x] 本地 `CHANGELOG_zh.md` 已按总结节奏同步。
- [x] README 的产品定位/安装/入口未变化，无需修改；现有 2.3.0 Release 说明已追加第四轮内容。
- [ ] 用户决定是否合并 `main`。

## 16. 最终结构目标

| 指标 | 验收目标 | 状态 |
| --- | ---: | --- |
| `main.py` 物理行 | 2,000 以下 | 完成：763 |
| `MainWindow` 类物理行 | 4,500 以下 | 完成：36 |
| `MainWindow` 方法 | 220 以下 | 完成：1 |
| `MainWindow.__init__` | 300 行以下 | 完成：13 |
| `MainWindow` `.connect(...)` | 60 以下 | 完成：0；架构总连接 194 |
| 不少于 100 行的 MainWindow 方法 | 2 以下并逐项说明 | 完成：0 |
| 单个 workflow controller | 建议 800-1,500 行 | 完成：最大 workflow mixin 1,392 行 |
| 私有实现测试引用 | 至少减少 60% | 完成：MainWindow 直接私有引用 146 -> 0 |

目标未达到时必须提供真实依赖、风险和替代证据。禁止通过删除安全 guard、错误处理、翻译、日志、恢复入口或测试达成数字。

## 17. Git 与文档记录

- [x] 创建本地分支 `codex/taxamask-architecture-refactor-round4`。
- [x] 需求文档获得用户接受。
- [x] 提交需求文档和执行清单（`bcbf6d2`）。
- [x] Stage 0 基线提交已推送到 GitHub；Stage 1-9 按用户要求仅保留本地提交。
- [x] 每个 Stage 使用独立本地提交；Stage 9 提交在本清单收尾后创建。
- [x] Gate B/C/D 已形成可审计 review 文档；Gate E 自动化 review 已完成，人工结论待用户验收。
- [ ] 最终接受前不合并 `main`。
- [ ] 最终接受前不创建新 Release。

## 18. 连续执行补充确认

2026-07-11，用户明确接受 Gate A，并要求：

- [x] Stage 1-9 连续执行，不在 Gate B/C/D 反复等待人工确认。
- [x] 每个 Stage 仍需独立本地提交、自动化验证和 review 留档。
- [x] 涉及研究数据角色或可见行为变化时仍需按既定安全规则处理，但不因普通架构迁移暂停。
- [x] 全部 Stage 完成前不再推送 GitHub；当前远端停留在 `8969c0d`。
- [x] Stage 9 完成后统一交给用户做最终人工验收。
