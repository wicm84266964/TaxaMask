# PDF 筛选 Profile 适配说明

> 适用范围：TaxaMask PDF Evidence Tools / V2 screening
>
> 目标：说明如何把默认蚂蚁新种筛选逻辑，调整为其他类群的分类学文献筛选逻辑。

---

## 控制筛选逻辑的位置

PDF 文献筛选的目标类群、纳入标准和排除标准由 profile 控制。相关文件位于：

```text
screener_configs/*.json
```

GUI 中的位置：

```text
PDF Evidence Tools -> Select Logic Profile -> Advanced Logic Settings
```

命令行中也可以指定：

```bash
python tools/agentic/screen_pdfs.py --pdf-source-dir pdf_folder --out out_folder --config screener_configs/蚂蚁新种筛选_V2示例.json
```

---

## 推荐保留的示例文件

当前仓库提供了这几类 profile：

- `蚂蚁新种筛选_V2示例.json`
  - 作为正式参考示例。
  - 展示如何筛“蚂蚁分类学新种/新分类单元报道”。

- `通用分类学新种筛选_V2模板.json`
  - 作为改其他动物、昆虫、化石或显微类群时的起点。
  - 使用前必须替换 `TARGET_GROUP`、`TARGET_FAMILY`、`TARGET_GENUS`。

- `植物分类学新种筛选_V2模板.json`
  - 作为植物分类学方向的起点。
  - 使用前建议替换目标科、属和器官术语。

---

## 每个字段在做什么

### `processing_mode`

它在做什么：标记这个 profile 属于 V2 筛选流程。

为什么重要：公开版的筛选标准由 V2 profile 明确控制，避免程序在 profile 之外追加某个历史类群的固定判定规则。

建议：新建跨类群筛选 profile 时使用：

```json
"processing_mode": "v2"
```

### `required_keywords`

它在做什么：记录“新种/新分类单元”相关核心词，比如 `sp. nov.`、`new species`、`gen. nov.`。

为什么重要：这些词帮助程序和研究者判断 PDF 是否有分类学描述信号。

怎么改：通常不需要大改，但不同学科可加入本领域常见写法，如植物中的 `comb. nov.`。

### `supportive_keywords`

它在做什么：记录支持性分类学词汇，例如 morphology、diagnosis、holotype、material examined。

为什么重要：这些词不是单独判定依据，但能提示文献更像分类学论文。

怎么改：把蚂蚁部位词换成目标类群的结构词。例如植物可加入 leaf、flower、fruit；甲虫可加入 pronotum、elytra、aedeagus。

### `taxonomic_group_keywords`

它在做什么：记录目标类群名称。

为什么重要：这是跨类群适配中最该改的字段。蚂蚁 profile 里是 Formicidae、ant、ants；如果筛植物或甲虫，必须换成对应类群。

怎么改：

```json
"taxonomic_group_keywords": [
  "coleoptera",
  "carabidae",
  "beetle",
  "beetles"
]
```

### `strong_exclude_keywords`

它在做什么：记录强排除方向，例如 ecology、behavior、algorithm、medical。

为什么重要：这些词帮助把“不是分类学新种描述”的论文挡出去。

注意：不要把过宽的词放进去。比如植物方向如果把 `flora` 放进强排除，可能会误伤植物分类学论文。

### `weak_exclude_keywords`

它在做什么：记录弱排除词，例如 note、correction、comment。

为什么重要：这些词只能降低信心，不应该直接一票否决。

### `biological_exclude_keywords`

它在做什么：记录容易和目标类群混淆的生物对象。

为什么重要：蚂蚁任务里，微生物、真菌、病毒、寄生蜂/蝇经常出现在“ant-associated” 文献中，但它们不是“蚂蚁本身的新种描述”。其他类群也会有类似干扰。

怎么改：按目标类群的常见混淆对象写。例如植物方向可排除 endophyte、pathogen、pollinator；昆虫方向可排除 host plant、parasite、microbiome。

### `llm_system_prompt`

它在做什么：告诉大模型扮演什么角色。

为什么重要：如果筛植物，系统提示词不应继续写“昆虫分类学专家”或“蚂蚁分类学专家”。

### `llm_batch_prompt_template`

它在做什么：这是 V2 的核心筛选提示词。

为什么重要：include / exclude / uncertain 的真正生物学含义由这里定义。

必须保留的占位符：

```text
{records_json}
{expected_record_count}
```

建议保留的输出格式：

```json
{"record_id":"<原值>","decision":"include|exclude|uncertain","confidence":0-1,"reason":"一句话理由"}
```

---

## 从蚂蚁改成其他类群的最小步骤

1. 复制 `蚂蚁新种筛选_V2示例.json` 或 `通用分类学新种筛选_V2模板.json`。
2. 改文件名，例如 `甲虫新种筛选_V2.json`。
3. 把 `taxonomic_group_keywords` 换成目标类群。
4. 把 `supportive_keywords` 中的形态词换成目标类群结构词。
5. 把 `biological_exclude_keywords` 换成该类群常见干扰对象。
6. 改 `llm_system_prompt`。
7. 改 `llm_batch_prompt_template` 中的任务描述和 include / exclude / uncertain 标准。
8. 在 GUI 里选择这个 profile，先用小批量 PDF 测试。

---

## 重要边界

V2 现在不会在程序内部硬追加“蚂蚁新种报道”的判定标准。程序只追加通用的 record_id 和 JSON 完整性约束。

这意味着：

- 蚂蚁逻辑保留在蚂蚁 profile 里；
- 其他类群逻辑由对应 profile 控制；
- 如果 profile 写得不清楚，模型会按不清楚的规则筛选；
- 不同类群第一次使用时，应先抽样复核，不要直接把结果当作可信候选集。
