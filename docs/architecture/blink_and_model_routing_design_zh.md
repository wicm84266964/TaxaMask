# Blink 与模型路由设计

## 定位

2D/STL Morphology 路线基于高分辨率外部形态图像或 STL 渲染视图进行标注。TaxaMask 在这条路线中组合了人工 polygon、Locator、SAM、Blink 和 route-appointed experts。

核心目标是让模型逐步辅助研究者，而不是把所有部位都交给单一模型一次性自动标完。

## Locator / SAM 两阶段

TaxaMask 的 2D 标注路线可以理解为：

```text
Locator: 找到目标结构大致区域
SAM / Segmenter: 在区域内生成像素级 mask
Human review: 研究者确认、修正或拒绝
```

这种拆分的好处是：

- Locator 学习空间位置和部位候选。
- Segmenter 负责边界细节。
- 人工复核保持最终真值可信。

## Blink 思想

Blink 是一种小部位 refinement 思路。它强调在局部和全局之间来回切换：

- inside-view：观察框内局部纹理和细节。
- outside-view：观察框外上下文和解剖连接。
- trajectory：记录边界收缩或调整过程。

Blink 的目标不是只保存一个最终框，而是让模型学习“如何找到边界”的过程。

## 级联专家

不同结构的边界逻辑不同。例如头部、大颚、眼、触角、胸腹连接等，可能需要不同专家模型。

TaxaMask 的长期方向是：

- 主工作台处理大结构和稳定区域。
- 小部位或难结构进入 Blink / expert route。
- route 由项目配置或用户选择决定。
- 专家输出仍为 draft，需要人工确认。

## 模型路由治理

“多模型”本身不是问题，缺少治理的模型堆叠才是问题。

模型路由应有：

- profile：当前模型方案。
- parent route：主部位或上游模型。
- child expert：子部位或专家模型。
- backend contract：外部训练/预测接口。
- result manifest：运行结果和模型来源。
- acceptance policy：预测能否进入正式标注。

## 训练数据边界

训练数据应来自人工确认状态，而不是未复核 AI 输出。

候选来源包括：

- 人工 polygon。
- 人工修正后的 SAM mask。
- 人工确认后的 Blink 轨迹。
- 人工接受后的 expert prediction。

不应直接训练：

- 原始 VLM 框。
- 未确认 Locator 输出。
- 未复核 SAM mask。
- PDF 候选图版。

## 与 TIF/CT 的关系

2D/STL 与 TIF/CT 的模型体系不同：

- 2D/STL 处理外部形态图像和 polygon/mask。
- TIF/CT 处理体数据 label field 和 volume segmentation。
- Local Axis 输出局部坐标系 proposal，而不是 label mask。

它们可以共享后端 contract 思想和 Agent Center，但不应共享同一套 label schema 或训练样本语义。

## 验收方向

Blink 和模型路由的质量不能只看模型能否运行，还要看：

- 输出是否进入正确 draft 层。
- 人工复核是否清晰。
- route 是否能解释为什么调用某个 expert。
- 失败时是否保留原始人工标注。
- 配置是否不保存 API key 或本地私有路径。
