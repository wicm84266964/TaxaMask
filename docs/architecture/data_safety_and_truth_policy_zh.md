# 研究数据安全与真值策略

## 总原则

TaxaMask 的数据安全目标是：**让 AI 和自动化流程提高效率，但不让它们静默污染研究真值。**

这对分类学和形态学研究尤其重要。一个错误的自动预测如果被当作真值进入训练集，会影响后续模型、图版复核和结果可信度。因此 TaxaMask 把候选、草稿、人工编辑和训练真值分成不同层级。

## 核心数据角色

### `manual_truth`

`manual_truth` 是人工复核后的训练真值。它是最受保护的数据层。

规则：

- 不能被模型预测自动覆盖。
- 不能被普通编辑草稿静默替换。
- 只能通过明确的接受、提升或人工确认动作生成。
- 训练样本优先使用它，而不是使用未复核 prediction draft。

### `working_edit`

`working_edit` 是研究者正在编辑的工作层。

规则：

- 可以保存、自动保存、继续修改。
- 可以作为人工复核过程的一部分。
- 不等于训练真值，除非用户明确接受为 `manual_truth`。

### `editable_ai_result`

`editable_ai_result` 是可编辑 AI 预测结果。

规则：

- 预测导入优先进入这个层级。
- 用户可以打开、修正、比较和接受。
- 不应直接替换 `manual_truth`。
- 接受前应保留来源、run、模型和输入目标信息。

### `raw_ai_prediction_backup`

`raw_ai_prediction_backup` 保存原始预测备份。

规则：

- 用于审计和回溯。
- 不应被画笔、擦除或普通编辑动作修改。
- 可以帮助判断导入后哪些差异来自模型，哪些来自人工修正。

### PDF evidence

PDF evidence 包括候选文献、图版、caption、附近文本和结构化部位描述。

规则：

- 它是 evidence/provenance，不是训练真值。
- PDF 图版可以成为候选材料，但进入训练前必须人工审查。
- PDF 文献路径、下载来源和筛选结果应可审计。

### VLM / locator / SAM draft

VLM 框、Locator 框、SAM mask 和 Blink 轨迹都属于候选或辅助材料。

规则：

- 默认不能自动覆盖正式人工标注。
- 可以进入 review queue、candidate layer 或辅助 UI。
- 只有经过人工确认后，才可进入正式标注或训练数据。

## TIF/CT 数据安全

TIF/CT 路线额外强调：

- 原始 TIF stack 不被覆盖。
- AMIRA 原始文件只读导入，不写回。
- sidecar label 与 image volume 分层保存。
- Local Axis reslice 是派生输出，不是原始 stack 的修改。
- 训练/预测 run 输出保留在 run 目录，不直接改写核心项目真值。

## 写入 guard

高风险写入应经过统一 guard：

- label role 是否允许写。
- 目标路径是否在项目目录内。
- 是否可能覆盖 source stack。
- 是否把 AI draft 提升成 truth。
- 当前 task context 是否仍匹配用户选择。

这些 guard 的目标不是让程序复杂，而是避免未来新增入口时绕过研究数据安全边界。

## 训练样本准入

一个样本成为训练样本，至少应满足：

- 有明确 specimen / part / reslice 上下文。
- image 与 label shape 匹配。
- label schema 或 material map 可解释。
- 人工真值存在且状态允许训练。
- 用户或流程明确标记 train-ready。

只创建 label schema、只生成预测结果、只保存草稿，都不等于样本已可训练。

## 用户可见行为

当程序拒绝某个操作时，应尽量说明原因，例如：

- 当前层是 raw backup，只读。
- 当前预测结果还未人工复核。
- label shape 与 image shape 不匹配。
- 后台保存或训练任务尚未完成。
- 系统资源不足，当前只能继续切片查看或稍后重试 3D preview。

这种解释对研究者很重要，因为它能区分“数据坏了”和“程序正在保护数据”。
