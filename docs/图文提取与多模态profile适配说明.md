# 图文提取与多模态 Profile 适配说明

这份说明面向需要把蚂蚁三视图流程改成其他分类群图版流程的用户。

## 1. 它和 PDF 筛选 profile 的区别

`screener_configs/` 里的 profile 负责 PDF 文献筛选：判断一篇 PDF 是否值得进入后续处理。

`multimodal_configs/` 里的 profile 负责 figure 阶段：决定怎样提取图版、怎样组装 caption 和附近文本证据，以及启用多模态验证时怎样判断候选图是否合格。

两者可以都指向同一个研究对象，例如都选择蚂蚁；也可以分别调宽或调严。

## 2. 默认提供的模板

当前提供：

- `multimodal_configs/蚂蚁三视图提取复核_示例.json`
- `multimodal_configs/通用分类学图版提取复核_模板.json`
- `multimodal_configs/植物分类学图版提取复核_模板.json`

蚂蚁示例是当前验证最充分的路径。通用和植物模板是适配起点，正式批量使用前应先小批量人工检查。

## 3. 主要字段

`taxonomy_terms`：目标分类学证据词。  
它会影响哪些文本块更容易进入候选证据。

`extraction_rules.caption_patterns`：caption 识别模式。  
如果你的文献常用 Plate、Fig、图版等不同写法，可以在这里补充。

`extraction_rules.core_section_hints`：核心证据章节。  
通常放 diagnosis、description、type material、material examined 等。

`extraction_rules.extended_section_hints`：扩展证据章节。  
通常放 key、taxonomic treatment、species account 等。

`review_rules.view_schema.required_or_expected_views`：期望视图或结构字段。  
蚂蚁示例是 `lateral / dorsal / head_frontal`。植物模板则使用 `habit / leaf / flower / fruit_or_seed / diagnostic_detail`。

`review_rules.view_schema.acceptance_mode`：接受模式。

- `require_all_expected_parts`：必须检测到全部期望结构才可接受，适合蚂蚁三视图这类固定图版。
- `model_accept_with_parts_recorded`：模型接受即可，结构字段主要用于记录，适合植物或其他结构组合不固定的图版。

`review_rules.prompt`：多模态模型复核提示词。  
启用真实多模态验证时会使用这里的规则。

## 4. API 设置不在 profile 里

profile 不保存 API key、base_url 或模型名。

API 设置在界面顶部的 `Text LLM API` 和 `Multimodal LLM API` 里配置：

- Text LLM API：用于 PDF 文献筛选。
- Multimodal LLM API：用于图像 + 文本复核。

这样可以用较便宜的文本模型筛文献，再用支持图像输入的模型复核 figure。

## 5. 推荐适配步骤

1. 复制 `通用分类学图版提取复核_模板.json`。
2. 修改 `profile_name` 和 `target_taxon`。
3. 替换 `taxonomy_terms`。
4. 调整核心章节和扩展章节。
5. 把 `required_or_expected_views` 改成目标类群的图版结构。
6. 修改 `accept_if`、`reject_if` 和 prompt。
7. 在 GUI 里选择新 profile。
8. 用 5-20 篇 PDF 小批量试跑。
9. 检查 accepted / review / rejected 和模型理由。
10. 稳定后再批量处理。

## 6. 结果可信度边界

如果没有启用真实多模态验证，或者模型配置不可用，程序会走 mock/default 复核路径。这类结果应进入 Review，而不是直接作为可信 accepted。

即使启用了真实多模态验证，新类群 profile 也需要小批量人工验收。profile 提供的是适配接口，不代表所有分类群已经被同等验证。

