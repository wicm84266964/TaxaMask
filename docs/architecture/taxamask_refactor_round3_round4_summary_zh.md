# TaxaMask 第三、第四轮架构优化公开汇总

## 文档定位

本文是 TaxaMask 第三轮 TIF 工作台优化与第四轮主窗口优化的长期公开记录。它汇总原需求、执行清单、逐 Stage 复核、方法与信号台账、性能报告和验收结论，替代这些施工流水在公开仓库中的逐份保存。

原始阶段记录仍可通过 Git 历史追溯，但当前公开文档只保留稳定结论、研究安全边界和后续维护需要知道的事实。

## 版本选择

- `v2.3.0` 标签和 Release 附件保持为 2026-07-09 的稳定发布快照。
- 最新 `main` 包含第三轮 TIF 工作台优化和第四轮 TaxaMask 主窗口优化。
- 第四轮已完成自动化验证和主要交互项验收，但没有逐项人工覆盖 TaxaMask 全部功能。因此，Release 快照适合更保守的使用场景，最新 `main` 适合希望使用新架构与后续修复的用户。

## 为什么继续优化

前两轮已经把 TIF 的安全规则、任务状态、页面布局和部分控制器从大文件中拆出，但两个入口仍承担了过多职责：

- `AntSleap/ui/tif_workbench.py` 同时协调 specimen、part、reslice、标注、ROI、训练预测、3D 预览和 Local Axis。
- `AntSleap/main.py` 同时承载程序外壳、项目生命周期、2D 标注、Blink、PDF、Agent、训练预测和导出。
- 测试和 Qt 信号仍有一部分直接依赖入口类的私有实现，移动代码后容易出现“新模块存在，但真实按钮仍连旧方法”的双轨状态。
- 大体积 TIF/reslice 切换时，任何同步标签扫描、体预览降采样或 memmap 释放都会让研究者感觉程序短暂无响应。

优化目标不是单纯减少行数，而是让每条研究工作流有明确负责人，并让测试、信号和 Agent 上下文一起迁移到新责任模块。

## 冻结边界

两轮优化都遵守以下边界：

- 不改变现有项目格式、SQLite/sidecar 语义和训练后端契约。
- 不让 AI prediction、PDF evidence 或 box-only draft 自动成为训练真值。
- `manual_truth` 只能由明确的人工复核或受保护的 promotion 流程产生。
- 不通过删除错误处理、审计信息、翻译或安全 guard 来降低行数。
- 保留历史公开导入入口，避免外部脚本和既有测试突然失效。
- 真实研究数据只用于隔离验收，不进入仓库。

## 第三轮：TIF 工作台按研究流程拆分

### 拆分范围

第三轮把 TIF 工作台按完整研究动作划分为责任控制器和协调层：

1. Selection / Lifecycle：specimen、part、reslice 选择，恢复与项目生命周期。
2. Annotation / Save / Truth：标签编辑、保存、真值提升和写入保护。
3. ROI-to-Part：ROI 草稿、确认、part volume 创建和 accepted mask 初始化。
4. Part Mask / Material：材料标签表、关键切片、插值、预览、接受与重开恢复。
5. Volume Preview：2D/3D 预览、GPU/CPU fallback、资源错误和交互控制。
6. Local Axis / Reslice：三点参考、局部坐标、重切片、保存和重开。
7. Backend / Result Review：训练、预测、导入、分组复核和角色保护。
8. Shell / View / Signal Router / Coordinator：顶层工作台、跨流程协调和连接治理。

### 信号与测试迁移

- 工作流按钮优先直连对应 controller，不再经过只做转发的 Widget wrapper。
- GPU canvas 的失败、统计、旋转、平移和缩放由 Volume Render controller 负责。
- Local Axis 端点交互继续由 Local Axis controller 负责，避免 3D 普通交互与解剖参考点混用。
- 每个工作流先建立 controller/service 直接测试，再保留必要的真实 Widget 集成测试。
- 项目重开、语言刷新和 controller 重建不得造成重复连接或一次点击触发多次研究动作。

### 大体积数据响应性

第三轮验收后又根据真实 GAGA reslice 卡顿完成针对性收口：

- specimen/part/reslice 加载期间合并三维重绘请求，选择完成后只调度一次后台预览。
- 大型 reslice 不再在 GUI 线程同步构建 3D texture。
- 旧 memmap 从界面状态中立即分离，在后台等待旧预览任务结束后再安全关闭。
- 侧栏即时状态不再对约 3.45 GB 标签执行完整 `np.unique`；严格标签编号核验仍在真正提升训练真值时由后台执行。
- 标签表重开恢复优先使用 part 已持久化的 `label_schema_id`，不再被下拉框上一次浏览选择覆盖。

这些变化的实际意义是：切换大型个体、part 或重切片时，界面不再因为完整体数据扫描或同步预览计算而长时间占住；训练真值校验仍保持严格。

### 最终结构指标

| 指标 | 第三轮起点 | 最终状态 |
| --- | ---: | ---: |
| `tif_workbench.py` 物理行数 | 14,234 | 5,041 |
| Widget 方法数 | 约 664 | 219 |
| 4 行以内薄方法 | 约 147 | 39 |
| Widget 直接 Qt 连接 | 251 | 11 |
| `__init__` | 混合大量状态与布局 | 11 行 |

主文件下降约 64.6%，但不宣称控制器已经完全解耦。部分 controller 仍持有完整 Widget，部分模块仍超过建议审阅尺寸，私有实现测试也尚未全部迁移为公开契约测试。

### 第三轮验收

- 九组最终自动门共 702 条测试通过。
- Agent 上下文对齐后的相关回归为 11 个 suite、778 条测试，其中 1 条按环境跳过，其余通过。
- 真实蚂蚁体积在隔离项目中完成选择、mask、ROI-to-Part、Local Axis、SQLite 重开和预测导入验证，源数据哈希保持不变。
- 真实 CUDA 预测重开可恢复 working edit、raw prediction backup 和 model draft，且不会覆盖 `manual_truth`。
- 研究者确认 Local Axis 解剖方向符合预期，Dataset601 蚂蚁脑区边界合理。该结论只代表蚂蚁领域实证，不扩展为跨类群承诺。
- 本机 Qt/OpenGL 初始化不稳定时使用受支持的 CPU 3D fallback；这属于 renderer/驱动兼容性，不代表 TIF 数据损坏。

## 第四轮：TaxaMask 主窗口按全局工作流拆分

### 拆分范围

第四轮冻结第三轮已验收的 TIF 内部结构，集中处理 `AntSleap/main.py` 和 `MainWindow`：

1. Runtime / Worker：运行线程、通用 worker 和生命周期收口。
2. Dialog / Settings：设置页、参数映射、验证和 Agent context。
3. Shell / Agent：主窗口外壳、Start Center、导航和内嵌 Agent。
4. Project Lifecycle：项目打开、保存、防止运行任务期间切换项目。
5. 2D Navigation / Literature：图片、部位、分组和 PDF evidence 桥接。
6. Annotation / SAM / Blink：标注、SAM、父子专家和 Blink 上下文。
7. Training / Prediction / VLM / Export：训练、预测、多模态草稿和导出。
8. Presentation / Audit：主题、本地化、设置入口和架构审计。

`main.py` 现在只保留启动入口、兼容 re-export 和轻量 `MainWindow` 组合；新业务逻辑应进入对应 workflow 模块，而不是重新堆回入口文件。

### 信号、状态与 Agent 对齐

- MainWindow 类体不再直接写入工作流状态，也不直接建立 Qt 连接。
- 架构扫描覆盖 30 个责任模块；第五轮推理失败提示接入后，真实 `connect/connect_once` 总数为 198，连接仍由责任模块管理。
- PDF、TIF 和 Blink 的跨工作台事件继续由 signal router/coordinator 管理。
- 动态 worker 回调绑定 worker/run identity，过期任务结果不能刷新新项目或新选择。
- MainWindow 直接私有实现测试引用从 146 次降到 0；真实窗口上的 workflow contract 测试继续保留。
- 内嵌 Agent 的 labeling route 已指向 `main_window_agent_context.py`、`main_window_annotation.py`、`main_window_blink_context.py` 和 `main_window_vlm.py`，不再提示已经从 `main.py` 删除的方法。
- Agent 首问工具输出限制为 256 KiB；空正文网关响应会补发一次简短正文请求，避免第一次提问立即压缩或看不到回答。

### 最终结构指标

| 指标 | 第四轮起点 | 最终状态 |
| --- | ---: | ---: |
| `main.py` 物理行数 | 16,024 | 763 |
| MainWindow 类体 | 大型混合类 | 36 行 |
| MainWindow 构造器 | 混合初始化 | 13 行 |
| MainWindow 直接方法 | 390 个待归属方法 | 1 |
| MainWindow 直接状态写入 | 多处分散写入 | 0 |
| MainWindow 直接 Qt 连接 | 多处分散连接 | 0 |
| 全部责任模块真实连接 | 未集中审计 | 198 |

最大 workflow 模块低于 1,500 行建议审阅线。`main.py` 行数下降 95.2%，其收益主要是降低跨工作流修改风险和提高测试定位能力，不应直接等同于 95.2% 的运行速度提升。

### 性能实测

相对 Stage 0 基线：

- MainWindow 构造中位数由 237.394 ms 降至 122.501 ms，改善 48.4%。
- Start Center RSS 由 598.883 MB 降至 573.268 MB，改善 4.3%。
- Start Center 中位数改善 0.9%，未达到原 5%-15% stretch 目标。
- 图片切换、部位切换和小型 2D 项目打开处于亚毫秒或十余毫秒量级，变化主要受 Qt event loop 与新增安全 guard 影响，没有达到全部 stretch 目标。
- TIF 工作台改为首次进入时创建，约 348 ms 成本从程序启动转移到首次进入 TIF。

启动时间约 97% 消耗在 PyTorch、OpenCV、Qt/WebEngine 和兼容模块导入。第四轮选择保留历史公开 import 兼容，因此没有用破坏兼容性的激进延迟导入换取更漂亮的启动数字。

### 第四轮验收

- 完整验证覆盖 18 个 suite、1,149 条测试。
- 1 条环境相关 TIF workbench 测试跳过，其余通过。
- 严格复核覆盖项目切换、过期异步结果、SAM、图片导入、父子训练、Blink 路由、PDF/TIF 桥接和导出边界。
- 研究者已测试主要交互项，暂未发现问题。
- 未对 TaxaMask 全功能逐项完成人工测试，因此最终状态记录为 `accepted with recorded manual coverage gaps`。
- 未逐项覆盖的 2D/Blink/VLM/PDF/导出扩展路径仍是后续日常使用中的人工复核清单，不能被自动化测试结论替代。

## 对研究工作流的影响

对研究者而言，入口和数据语义保持不变：

- 仍从同一主界面进入 PDF、2D/STL、TIF/CT 和 Agent Center。
- 仍按 specimen、part、reslice 和标签角色组织 TIF 数据。
- AI 结果仍先进入待复核层，不能自动污染训练真值。
- 大体积 TIF 切换更少在主界面同步执行完整扫描和预览计算。
- 出现问题时，维护者可以根据 workflow、controller、task 和 signal owner 定位，而不需要在两个一万多行入口文件中搜索全部逻辑。

## 已知边界与后续维护

- 不宣称所有 controller 已完全脱离完整 Widget/MainWindow。
- 不宣称所有私有实现测试都已迁移为公开 contract。
- 不宣称 GPU/OpenGL 在所有显卡和驱动上均可用；CPU fallback 仍是受支持路径。
- 不宣称第四轮完成 TaxaMask 全功能逐项人工验收。
- 不应把新功能重新写回 `main.py` 或 `tif_workbench.py`；应先确定其所属研究工作流。
- 修改信号时必须同步 owner、连接、断开、过期回调保护和对应测试。
- 修改 Agent 路由时必须同步当前源码位置、上下文字段、压缩策略和可见面板行为。
- 修改真值、预测导入或导出时必须继续遵守 `manual_truth`、review draft 和 provenance 边界。

## 长期验证入口

- 当前架构说明：`docs/architecture/taxamask_architecture_overview_zh.md`
- TIF/CT 架构：`docs/architecture/tif_ct_workbench_architecture_zh.md`
- TIF 整理公开计划：`docs/architecture/tif_workbench_refactor_plan_zh.md`
- TIF 验证摘要：`docs/validation/tif_architecture_refactor_validation_zh.md`
- 数据安全与真值政策：`docs/architecture/data_safety_and_truth_policy_zh.md`
- Release 说明：`docs/releases/2.3.0-tif-architecture-refactor_zh.md`

阶段方法表、信号清单、逐 Stage review 和一次性验收卡不再作为当前公开树中的长期文档；需要历史审计时使用 Git 历史。
