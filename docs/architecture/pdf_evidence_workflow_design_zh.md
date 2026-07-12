# PDF Evidence 工作流设计

## 定位

PDF Evidence 是 TaxaMask 的文献证据路线。它帮助研究者从分类学文献中筛选 PDF、提取图版、caption、附近文本和部位描述，为后续标注和复核提供候选材料。

它不是训练真值入口。PDF 输出的图像和文本都应被视为 evidence/provenance，只有经过研究者确认后才可能进入标注或训练流程。

## 工作流

```text
Paper discovery, selected acquisition, batch harvest, or existing PDF folder
-> PDF screening
-> figure and caption extraction
-> candidate review
-> structured part descriptions
-> optional import into annotation workflow
```

### Stage 0：文献发现与合法 PDF 获取

当研究者还没有 PDF 文件夹时，Agent 先确认任务是每日文献推荐、专题检索、获取已经筛选的文献，还是批量采集。统一入口是内嵌 `taxonomy-paper-finder` Skill。

默认策略：

- 发现和推荐先检查元数据、摘要和证据，不自动下载全部候选。
- 每日推荐约 5 篇主要文献、最多 8 篇候选和 3 篇深读，不用弱结果凑数。
- 从筛选报告进入下载时先征得确认，默认只衔接 `deep-reads`。
- 批量采集先导出并复核 `records.csv`，再开始有边界、可续跑的下载。

边界：

- 不使用付费墙绕过、验证码绕过或非法来源。
- 保存 DOI、URL、下载状态和来源记录。
- 下载失败也应记录原因，方便人工补全。
- 保存筛选决定和证据 URL，使“为何推荐”和“从哪里获得”都可以复核。

### PDF 筛选

筛选阶段判断 PDF 是否可能包含目标分类群、形态描述或可用图版。

输出应包含：

- 接受 / 拒绝 / 需要复核。
- 触发原因。
- 证据片段索引。
- profile 名称和版本。

### 图版与 caption 提取

图版提取关注分类学形态图版，而不是任意图片。

输出应区分：

- accepted candidate。
- needs-review candidate。
- rejected candidate。

候选图像不应直接成为训练图像。它们需要经过图像质量、分类单元、视角和部位语义复核。

### 部位描述结构化

PDF 文本可整理为：

```text
taxon -> part -> description -> source reference
```

这些描述可以辅助标注者判断形态边界，例如诊断性结构、刚毛、刻纹或部位比例，但不能替代人工图像标注。

## Profile 设计

PDF 和多模态 profile 应保存生物学规则、筛选逻辑和提示词模板，但不保存：

- API key。
- 私有 base URL。
- 本地运行路径。
- 长篇原始 PDF 文本。

模型配置属于本地 runtime settings，profile 属于可分享研究逻辑。

## 与 2D/STL 和 TIF 的关系

PDF Evidence 可以为 2D/STL 或 TIF 研究提供：

- 候选图版。
- 形态描述。
- taxon/provenance 线索。
- 复核队列。

但它不应直接：

- 创建 `manual_truth`。
- 自动确认训练样本。
- 覆盖人工标注。
- 把 PDF 图版无审查地加入训练集。

## Agent 辅助

Ask Agent 在 PDF route 中应先判断当前阶段：

- 用户是否已有 PDF 文件夹。
- 是否需要每日推荐、专题检索、精选文献获取或批量采集。
- 下载是否已经得到用户确认，精选下载是否保持默认 `deep-reads` 范围。
- 是否已配置筛选/多模态模型。
- 当前输出目录和数据库是否存在。
- 当前任务是筛选、提取、复核还是导入。

Agent 不应一次性倾倒完整流程，而应围绕当前阶段给出可执行建议。
