# PDF 文献证据层边界

> 所属方向：Ant 3D Workbench / Literature Evidence

## 1. 当前定位

PDF Processing 不再作为 Ant 3D Workbench 的主标注入口。

新的主流程是：

```text
STL rendered-view surface annotation
TIF volume annotation
model-assisted curation
```

PDF 能力保留为文献证据和 provenance 工具，主要服务：

- 文献筛查；
- 图版和 caption 提取；
- 候选图像来源记录；
- 分类学证据整理；
- headless / agentic 批处理。

## 2. 为什么下沉

PDF 图像通常来自论文压缩图版，分辨率和来源控制弱于 AntScan-style STL/TIF 数据。

对训练自动标注模型而言：

- STL 渲染图和 TIF 体数据是更稳定的主训练材料；
- PDF 图像更适合提供证据、出处、候选线索；
- PDF 结果不应默认进入高质量训练集。

## 3. 当前实现边界

本轮不删除 PDF 底层代码。

保留：

- `core/pdf_processor/`；
- `tools/agentic/screen_pdfs.py`；
- `tools/agentic/extract_figures.py`；
- `tools/agentic/import_candidates_to_project.py`；
- 已有 profile 配置和测试。

本轮不做：

- 完整 PDF skill 迁移；
- 删除 GUI PDF widget；
- 把 PDF 图像提升为 STL/TIF 主训练来源；
- 把 PDF candidate 自动写入 TIF `manual_truth`；
- 把 PDF candidate 自动写入 STL rendered-view specimen registry。

## 4. 后续建议

后续如果迁移为 agent skill，建议保留这些输出：

- source PDF path；
- page number；
- figure/caption；
- species/taxon candidate；
- extraction confidence；
- review status；
- link to STL/TIF specimen when manually confirmed；
- provenance record。

PDF evidence 可以和 specimen ID 关联，但必须是轻量引用，不应把文献证据塞进 TIF 或 STL 项目主 truth layer。

## 5. 对研究流程的意义

用户仍然可以利用 PDF 自动筛查和图文提取寻找候选材料。

但在 Ant 3D Workbench 的新架构里：

- STL rendered views 负责外部形态主标注；
- TIF volumes 负责内部结构主标注；
- PDF evidence 负责说明“这个图像、描述或候选记录来自哪里”。

这样可以保护训练数据可信度，同时保留文献工作的可追溯价值。
