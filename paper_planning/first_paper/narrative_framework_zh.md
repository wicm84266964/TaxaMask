# TaxaMask 第一篇文章叙事骨架

> 当前定位：本文聚焦 PDF 文献证据到 2D/STL 蚂蚁形态性状标注与训练数据导出的链路。TaxaMask 代码库中的 TIF/CT 体数据链路作为平台扩展存在，但不在第一篇中展开评估。

## 暂定题目

TaxaMask：文献证据驱动的分类学形态性状标注与小部位训练工作流——以入侵蚁为验证案例

英文可对应：

TaxaMask: an agent-assisted workflow from taxonomic literature evidence to morphology trait annotation

## 一句话主线

TaxaMask 从分类学 PDF 中抽取图版和部位描述，将文献知识整理为可追溯证据，并转化为蚂蚁头部性状的父子 route；随后在 2D 图像/STL 渲染视图中完成候选标注、小部位 Blink 训练、人工确权和训练数据导出。

## 核心故事

分类学形态研究的起点不是标注软件，而是文献。蚂蚁的复眼、上颚、触角柄节等性状定义和诊断描述，分散在分类学论文的正文、图版和 caption 中。研究者过去需要先翻 PDF、理解性状和部位关系，再进入标注工具手工配置标签、模型和训练流程。TaxaMask 要解决的是这条手工鸿沟：让文献知识进入标注工作台。

## 三大贡献

### 1. 文献知识进入标注工作台的完整链路

PDF 图版、caption/邻近文本和部位描述被整理为 evidence layer，再进入性状表、父子 route、标注工作台、人工确权和数据集导出。贡献重点是“文献知识如何连接到标注与训练数据生产”，不是提出新的分割模型。

### 2. 父子 route 与 Blink 小部位训练策略

TaxaMask 将 `Head -> Eye`、`Head -> Mandible`、`Head -> Scape` 这类结构关系转化为可训练 route。Blink 不是和 SAM/Locator 并列的模型，而是基于父级上下文、trajectory 和 route expert 的小部位训练策略。

### 3. 隐私敏感场景下的内嵌通用智能体协同

Ant-Code Agent Center 作为本地通用智能体，横跨 PDF、route、标注、训练和导出阶段，读取项目状态、配置、日志、后端契约和源码线索，帮助研究者诊断问题、适配模型，同时保留人工确权和权限边界。

## 验证对象

主案例：红火蚁 `Solenopsis invicta`

补充验证：小火蚁 `Wasmannia auropunctata`

验证的三个头部 route：

| route | 中文 | 验证意义 |
|---|---|---|
| `Head -> Eye` | 头部 -> 复眼 | 边界相对稳定，验证基础小部位 route |
| `Head -> Mandible` | 头部 -> 上颚 | 分类学诊断性强，展示小部位精修价值 |
| `Head -> Scape` | 头部 -> 触角柄节 | 头部附肢节段，受姿态和角度影响，避免整根触角分割歧义 |

## 文章结构

### 1. Introduction

第一段：分类学形态知识首先存在于文献中。

第二段：现有工具能标注、分割、训练，但不理解 PDF 中的性状知识。

第三段：蚂蚁头部小部位是典型难点，需要父级上下文。

第四段：实验室隐私数据和复杂模型配置使外部成品智能体不适合直接使用。

第五段：提出三大贡献。

### 2. System Overview

第一篇只画和讨论如下链路：

```text
PDF literature
-> evidence DB
-> trait table
-> parent-child route candidates
-> 2D/STL annotation workbench
-> draft annotation
-> human confirmation
-> dataset export
```

需要明确写入：

Ant-Code Agent Center acts as a cross-stage interaction layer for querying project state, diagnosing errors, inspecting backend contracts, and continuing the workflow without manually navigating long documentation.

边界声明：

The TIF volume workbench exists in the TaxaMask codebase but is not evaluated in this study.

### 3. Methods

#### 3.1 PDF evidence extraction

PDF 筛选、图版提取、caption/邻近文本、部位描述抽取、SQLite evidence DB。

#### 3.2 Trait table and parent-child route construction

从文献描述整理标准化部位表，生成 route candidate，经研究者复核后写入工作台。

如果自动 route 生成还没有完整验证，正文中使用“文献证据支持的 route candidate”或“经研究者确认的 route”，避免直接声称完全自动构建父子树。

#### 3.3 2D/STL annotation workbench

普通 2D 图像和 STL 渲染视图进入同一工作台；不直接编辑 STL mesh。

#### 3.4 Replaceable draft annotation models

VLM 负责冷启动候选框，Locator 负责主部位定位，SAM 负责草稿 mask。模型可替换，不是论文算法核心。

#### 3.5 Blink small-part training strategy

父级框、loose box、trajectory、route expert、训练后用于后续小部位起稿。强调 Blink 是小部位训练策略，不是与 SAM/Locator 同级的通用分割模型。

#### 3.6 Human confirmation and dataset export

AI 草稿必须人工确认；未复核草稿不进入训练；导出 COCO/YOLO/JSONL 等格式。

#### 3.7 Ant-Code collaboration layer

本地通用智能体读取项目状态、配置、日志、契约和源码线索；协助排错、适配后端和解释流程；不替代分类学确权。

## Results

### 4.1 Case study setup

红火蚁为主，小火蚁为补充；说明文献数量、图像来源、route 选择原因。

### 4.2 PDF evidence extraction

展示文献数、图版数、部位描述条目数、accepted/needs_review/rejected。

### 4.3 Trait table and route candidates

展示 `Head -> Eye`、`Head -> Mandible`、`Head -> Scape` 的证据来源、自动候选、人工修正和最终确认。

### 4.4 Main-part model for parent context

训练或验证 Head / Mesosoma / Gaster 主部位模型，说明 Head 父级上下文如何提供小部位 route 的起点。

### 4.5 Small-part Blink route validation

展示三个小部位 route 的 VLM/SAM 草稿、Blink trajectory、route expert 训练结果、人工确认统计。

### 4.6 Dataset export and audit outputs

最终图像数、mask 数、结构数、导出格式、manifest/report。

### 4.7 Ant-Code case vignette

至少一个来自红火蚁验证过程：

| 场景 | Ant-Code 协同价值 |
|---|---|
| `Head -> Mandible` route 训练后未自动起稿 | 读取 route manifest/log，发现 expert 未指定或未启用 |
| PDF evidence 被误认为训练真值 | 解释 evidence/candidate 与 training truth 边界 |
| 后端 contract 报错 | 读取 contract/log，指出配置或 schema 问题 |

## Discussion

核心收束：

- TaxaMask 不是新分割算法，而是让文献知识进入形态标注和训练数据生产。
- PDF 图版适合流程验证和冷启动，但不代表最终高精度生产数据。
- 父子 route 和 Blink 让蚂蚁头部小部位标注更可控。
- Ant-Code 的价值在于隐私敏感、本地项目上下文、开放式协同，而不是简单流程脚本。
- 其他类群可通过 profile 和模板迁移，但需要重新验证。
- 未来工作将探索把文献证据驱动的父子 route 方法扩展到其他诊断性状密集类群，并在更高分辨率的标本图像或 STL 渲染视图上验证 Scape 等姿态敏感小部位的精修上限。
- TIF/CT 体数据链路属于平台扩展，另文评估。

## 建议图表

Figure 1：第一篇总流程图。

Figure 2：文献描述到 `Head -> Mandible` route 的例子。

Figure 3：Blink 小部位训练流程。

Figure 4：红火蚁/小火蚁验证结果。

Table 1：路径覆盖表，传统做法 vs TaxaMask。

Table 2：性状证据与 route 表。

Table 3：标注、确权和导出统计。

Table 4：Ant-Code case vignette。
