# PDF 蚂蚁分类学图版宽松复核 Profile 方案

> 状态：用户已确认；代码、默认配置、入口文档和验证记录已同步。
>
> 范围：PDF Evidence / Figure Extraction / Multimodal Review profile。本文不改变主标注工作台训练逻辑，也不把 PDF 候选自动提升为训练真值。

## 1. 背景判断

当前主标注和训练工作流已经不再以“三视图齐全”为入口条件。主工作台训练依据项目中真实存在的图像和已保存标注进行预检；AntScan / STL rendered-view 数据也已经进入多视角登记和审阅语境。

PDF 多模态复核这边曾保留历史默认的“蚂蚁三视图”目标。该 profile 要求候选 figure 同时包含 `lateral`、`dorsal`、`head_frontal`，适合早期整张三视图图版筛选，但会误伤当前更宽的多视角形态图版需求。

因此确认将默认逻辑迁移为“蚂蚁分类学图版宽松复核 profile”，用于从 PDF 中保留更广义的分类学形态证据图版。

## 2. 新 Profile 目标

新 profile 的目标不是判断“是否三视图齐全”，而是判断：

```text
这张 PDF figure 是否是可用于蚂蚁分类学证据审阅的单一物种/单一分类单元形态图版。
```

它应接受：

- 单一蚂蚁物种或单一分类单元的 habitus / whole body / overview 图。
- 侧面、背面、腹面、正面、头部、局部结构等任一或多种视角。
- 包含多个小图的同一物种图版组合。
- 包含大颚、触角、柄节、后腹柄节、腹部、足、毛被、雕刻、比例尺等诊断结构的图版。
- 带有少量地图、比例尺、局部 inset 的图版，只要主体仍是形态图版。

它应拒绝：

- 多物种或多分类单元比较图。
- 仅地图、系统树、表格、生态场景、巢穴照片、实验图、统计图。
- 主体不是蚂蚁或目标分类群。
- 图像和 caption / 附近文本明显冲突。
- 证据不足以判断其为分类学形态图版的候选。

## 3. 与现有三视图 Profile 的差异

现有三视图 profile：

- `acceptance_goal`：只接受单一物种蚂蚁三视图整张 figure。
- `required_or_expected_views`：`lateral`、`dorsal`、`head_frontal`。
- `acceptance_mode`：`require_all_expected_parts`。
- 结果倾向：严格保留三视图图版，漏掉单视角、局部结构、多视角但不完整的图版。

新宽松 profile：

- `acceptance_goal`：接受单一物种/分类单元的蚂蚁分类学形态图版。
- `required_or_expected_views`：改为可记录的视角/结构字段，不作为全部必需条件。
- `acceptance_mode`：建议使用 `model_accept_with_parts_recorded`。
- 结果倾向：保留更多可审阅候选，由人工和后续 provenance 决定是否进入项目候选。

## 4. 建议视角与结构字段

建议把 `detected_views` 从三视图改成“视角 + 结构类型”的宽字段集合：

- `habitus_or_overview`
- `lateral`
- `dorsal`
- `ventral`
- `frontal`
- `head`
- `diagnostic_structure`
- `mandible`
- `antenna_or_scape`
- `mesosoma`
- `petiole_or_postpetiole`
- `gaster`
- `legs`
- `pilosity_or_sculpture`
- `plate_combination`

这些字段的作用是记录模型看到了什么，而不是要求每一项都出现。

## 5. Prompt 设计原则

多模态模型应被要求做“宽松候选保留”，而不是强终裁。

建议 system prompt 表达：

```text
你是严谨的蚂蚁分类学图版审稿助手。你将收到 PDF figure 候选及其 caption、附近文本、物种核心文本。请判断该候选是否为单一蚂蚁物种或单一分类单元的分类学形态图版。不要要求三视图齐全；任一有分类学形态价值的视角或诊断结构都可以接受。若是多物种比较、非蚂蚁主体、仅地图/系统树/表格/生态/实验图，或图文明显冲突，应拒绝。只输出 JSON。
```

建议 user instructions 强调：

- `accept=true` 表示“值得进入 PDF evidence review”，不是训练真值。
- 不要求 `lateral + dorsal + head_frontal` 同时存在。
- `detected_views` 用于记录可见视角或结构。
- 对单一物种图版组合应接受。
- 对证据不足但可能有用的候选，优先给 `uncertain` 或较低 confidence，而不是自信拒绝。

## 6. Profile 文件决策

确认使用文件：

```text
multimodal_configs/蚂蚁分类学图版宽松复核_示例.json
```

旧三视图示例不再保留为推荐或默认 profile：

```text
multimodal_configs/蚂蚁三视图提取复核_示例.json
```

原因是当前 AntScan / 多视角证据工作流已经不再以三视图齐全为目标；继续保留旧 profile 容易让 PDF 候选复核误回到历史筛选标准。

## 7. 当前默认行为

确认将 GUI 默认 Figure Extraction / Review Profile 从“内置蚂蚁三视图”迁移为“内置蚂蚁分类学图版宽松复核”。

README headless 示例、Agentic pipeline contract、PDF evidence skill 和内置默认 profile 也已同步到：

```text
multimodal_configs/蚂蚁分类学图版宽松复核_示例.json
```

## 8. 输出与数据安全边界

新 profile 只影响 PDF 候选筛选和复核状态，不改变训练数据边界。

输出仍应保持：

- PDF source path。
- page number。
- candidate id。
- caption。
- figure_local / species_core / species_extended evidence。
- model/review mode。
- review status。
- detected_views。
- species_candidate。

PDF 候选进入 2D 项目时仍应默认是 `needs_review`，不能自动成为正式标注或训练 truth。

## 9. 验证记录与后续建议

已完成聚焦验证：

```powershell
python -m unittest tests.test_figure_profile tests.test_agent_context_routes tests.test_agentic_contract
python -m py_compile core\pdf_processor\figure_profile.py core\pdf_processor\pdf_extractor.py core\pdf_processor\multimodal_validator.py AntSleap\ui\pdf_processing_widget.py
```

严格复核修正：

- 修正用户手册中残留的“蚂蚁示例默认关注三视图”说明，改为当前宽松分类学图版默认。
- 补强 accepted 门槛：真实多模态结果必须同时满足 `accept=true`、置信度、非比较/非多物种 flags、真实 review、profile parts 规则和可接受 category。若 category 已是 comparison/multi/non/other/uncertain，即使模型漏打 `comparison_figure` 或 `multiple_species`，也不会进入 accepted。
- 新增回归测试，覆盖“模型返回 accept=true 但 category=comparison_or_multi_species”的冲突结果。

实现后建议按小批量真实 PDF 验证：

1. 用新 profile 跑 5-10 篇包含多视角图版的蚂蚁分类学 PDF。
2. 对比旧三视图 profile：
   - 是否减少单视角/局部结构图版误拒。
   - 是否增加地图、系统树、生态照片等误收。
3. 检查 DB Viewer 中 evidence 是否仍能追溯到 caption 和文本块。
4. 检查 mock/default review 是否仍只进入 `needs_review`，不自动 accepted。
5. 抽样导出 candidate artifact，确认 `detected_views` 和 `review_status` 可读。

## 10. 已确认决策

本方案按以下决策实现：

1. 多物种比较图一律拒绝。
2. 纯局部结构图，例如只有大颚或触角，只要 caption 或附近文本明确对应单一蚂蚁物种/分类单元，可以接受。
3. GUI 默认直接迁移到新宽松 profile；旧三视图逻辑不再作为默认或示例保留。
