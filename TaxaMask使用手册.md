# TaxaMask 完整中文操作手册

> 适用版本：2026-05-12 开源预整理版
>
> 适用对象：需要独立使用 TaxaMask 进行文献筛选、图片提取、形态学标注、Blink 精修、模型训练与数据导出的研究者
>
> 目标：这份手册的设计目标，是尽量替代“我一点点口头讲给你听”的 onboarding 过程。它不仅说明“按钮在哪里”，更说明：
> - 这个按钮在做什么
> - 它会改哪一层数据
> - 它为什么重要
> - 哪些情况不能把它当成别的功能

---

## 目录

1. [你现在用的到底是什么软件](#1-你现在用的到底是什么软件)
2. [整个工作流总览](#2-整个工作流总览)
3. [首次启动、语言与界面总结构](#3-首次启动语言与界面总结构)
4. [项目管理：新建、打开、保存、搬盘后的路径问题](#4-项目管理新建打开保存搬盘后的路径问题)
5. [PDF 处理模块：从原始 PDF 到候选数据库](#5-pdf-处理模块从原始-pdf-到候选数据库)
6. [数据工具：浏览数据库、查看 CSV、导出粗 JSONL](#6-数据工具浏览数据库查看-csv导出粗-jsonl)
7. [标注工作台：从图片列表到正式标注](#7-标注工作台从图片列表到正式标注)
8. [Cropper 裁剪器：把一张大图拆成多个视角图](#8-cropper-裁剪器把一张大图拆成多个视角图)
9. [Blink 工作台：局部精修、轨迹积累与专家训练](#9-blink-工作台局部精修轨迹积累与专家训练)
10. [模型设置、训练、推理与 AI 标注清理](#10-模型设置训练推理与-ai-标注清理)
11. [导出数据集：Multimodal / COCO / YOLO](#11-导出数据集multimodal--coco--yolo)
12. [恢复边界、常见误区与排错建议](#12-恢复边界常见误区与排错建议)
13. [按钮速查表](#13-按钮速查表)
14. [标准流程模板：照着做的一整套操作路线](#14-标准流程模板照着做的一整套操作路线)
15. [结语：最值得一直记住的三句话](#15-结语最值得一直记住的三句话)

## 1. 你现在用的到底是什么软件

TaxaMask 是一个**综合科研工作台**，里面有两条大主线：

1. **文献处理线**
   - 批量筛选 PDF
   - 提取可能有价值的图像/figure
   - 落库到 SQLite
   - 导出粗数据集供后续复核或进一步处理

2. **标注与训练线**
   - 管理项目和图片
   - 在标注工作台中做手工标注 / SAM 辅助标注 / 自动推理
   - 在 Blink 工作台里做局部精修和轨迹积累
   - 训练定位器、SAM 分割器和 Blink 微观专家
   - 导出正式训练数据集

它不是两个完全独立的软件拼在一起，而是：

- PDF 侧更偏“找资料、筛图、产出候选数据”
- 标注侧更偏“把可用图像变成高质量正式数据”

对你的研究工作来说，最重要的逻辑是：

> **先在文献侧找到值得保留的图，再在标注侧把图变成可信的训练数据。**

---

## 2. 整个工作流总览

### 2.1 推荐使用顺序

对大多数实际研究任务，我建议按下面顺序使用：

1. **准备 API 设置与筛选逻辑方案**
2. **在 PDF Processing 里批量筛 PDF**
3. **把通过筛选的 PDF 做数据提取**
4. **在数据库里检查结果，必要时导出粗 JSONL 或人工筛掉不合适内容**
5. **将真正要做标注的图片导入项目**
6. **在标注工作台里做正式标注或自动推理**
7. **对细部位进入 Blink 做精修**
8. **训练模型 / 重新推理 / 再修订**
9. **导出正式数据集**

### 2.2 为什么要分成两层

不要把 PDF 侧和标注侧混成一个动作。

- **PDF 侧** 解决的是“哪些图值得进入项目”
- **标注侧** 解决的是“这些图怎样变成可靠的训练/研究数据”

这两层分开有两个好处：

1. 你可以先用相对宽松的方式从大量文献里找图
2. 真正昂贵的人工精修工作，只放在已经进入项目的样本上

---

## 3. 首次启动、语言与界面总结构

### 3.0 当前平台支持状态

当前版本主要在 Windows 环境下开发和验证。程序代码已经尽量使用可跨平台的 Python 路径处理方式，也提供了 `CPU only` 运行设备选项，因此 Linux 和 macOS 可以作为后续适配目标；但在正式开源说明中，应把 Linux / macOS 视为**尚未完整实机验收的实验性支持**。

这对使用者的实际含义是：

- Windows：当前最推荐、验证最充分的运行环境。
- Linux：理论上适合服务器或工作站部署，尤其是 NVIDIA CUDA 环境，但仍需要按实际机器验证 GUI、PyTorch、Poppler 和显卡驱动。
- macOS：可以尝试 CPU 路径做项目管理、标注整理和小规模测试；当前版本还没有把 Apple Silicon 的 MPS 加速作为正式支持设备。

如果你只是整理项目、人工标注、检查导出或做很小的数据测试，`CPU only` 可以降低硬件门槛。如果你要训练 Locator、SAM 或 Blink 专家，特别是大量 4K 图像或 `384 / 512` Blink 输入尺寸，仍建议使用 CUDA 版 PyTorch 和 NVIDIA 显卡。

### 3.1 启动后你会看到什么

主界面由三个主要标签页组成：

1. **PDF Processing**
2. **Labeling Workbench**
3. **Blink Workbench**

同时顶部菜单里有：

- `File`
  - `New Project`
  - `Open Project`
  - `Save Project`
  - `Export Dataset`
- `Settings`
  - `Model Settings`
  - `Language`


### 3.2 语言切换

路径：`Settings -> Language -> 中文 / English`

当前版本中，以下区域已经支持较完整的中文显示：

- 主工作台主要按钮和弹窗
- Blink 入口弹窗和 Blink 控制区
- Cropper 裁剪器
- PDF 处理页的重要控制项和运行参数

这对实际操作的意义不是“界面更好看”，而是：

- 你更容易判断某个按钮到底是在启动流程、保存状态，还是只是切换显示模式
- 降低“英文术语看懂了，但实际数据效果误解了”的风险

### 3.3 启动后自动恢复上次项目

如果配置里记着上次项目路径，而且该项目仍存在，程序会尝试恢复上次会话。

这意味着：

- 你重新打开程序时，可能已经直接带着上次的项目状态了
- 如果你不希望继续上次状态，最好明确手动 `Open Project` 或 `New Project`

---

## 4. 项目管理：新建、打开、保存、搬盘后的路径问题

### 4.1 新建项目

路径：`File -> New Project`

步骤：

1. 选一个目录
2. 输入项目名称
3. 选择项目模板
4. 程序会在那个目录下创建 `项目名.json`

当前内置模板有两类：

- `Generic taxonomy mask project`：通用分类学掩码项目，适合植物、昆虫以外类群或还没确定结构标签的新任务
- `Ant morphology (validated example)`：蚂蚁形态学示例，保留当前验证最充分的 `Head / Mesosoma / Gaster` 工作流

如果你研究的是蚂蚁，建议选择蚂蚁模板；如果你研究的是其他类群，建议先选通用模板，再在右侧 `Structures / 结构标签` 里改成自己的结构标签。

#### taxonomy、taxon 和 structure 不要混淆

- `taxonomy` / `Structures`：当前项目要标注的结构标签，例如 Head、Leaf、Flower、Wing
- `taxon` / `分类单元`：当前图片对应的分类单元，例如 Formica、Quercus、某个物种候选名

这两个概念分清楚很重要。前者决定你要画哪些 mask，后者决定这张图属于哪个分类单元。

### 4.2 打开项目

路径：`File -> Open Project`

程序打开项目时会读取：

- `name`
- `images`
- `labels`
- `taxonomy`
- `scales`

#### 非常重要：项目文件必须是合法 JSON

程序打开项目时本质上是直接 `json.load(...)`。

所以：

- 如果项目 JSON 语法是坏的
- 即使图片路径正确
- GUI 也**打不开**

这件事和“图片搬盘”是两回事。不要混淆：

- **路径问题** = JSON 能读，但原图找不到
- **JSONDecodeError** = 项目文件本身就坏了

### 4.3 保存项目

路径：`File -> Save Project`

你做的这些改动都会进项目：

- 图片列表
- taxonomy / structure 标签
- taxon / 分类单元
- polygon 标注
- manual box
- auto box
- Blink trajectory
- scale

建议习惯：

> 做完一段关键工作后主动保存，而不是完全依赖自动保存。

### 4.4 图片搬盘后的路径兜底

当前版本的路径恢复不再写死某个作者本机目录，而是通过本地配置里的 `known_relocated_roots` 做映射。

它适合这种情况：

- 项目 JSON 里还保存着旧图片库根目录
- 图片库整体搬到了新位置
- 文件在新位置仍然保持相同的相对目录结构

#### 这个兜底能解决什么

- 旧项目 JSON 还记着旧路径
- 但图片库只是换了盘或换了根目录
- 只要新位置文件真实存在，就能重新找到图像

本地配置示例：

```json
{
  "known_relocated_roots": [
    {
      "marker": "旧图片库根目录名或路径片段",
      "relocated_root": "D:/new_data_root"
    }
  ]
}
```

#### 这个兜底不能解决什么

- 它不能修坏掉的 JSON
- 它也不是通用路径魔法
- 它需要你明确告诉程序“旧路径片段”和“新根目录”之间的对应关系

### 4.5 图片列表的显示规则

左侧项目图片列表会：

- **已标注图片排在前面**
- **未标注图片排在后面**
- 已标注图片用绿色系文字
- 未标注图片用灰色文字

这有利于你快速判断当前项目的进度，而不是每次都自己数。

---

## 5. PDF 处理模块：从原始 PDF 到候选数据库

这一页负责的不是正式标注，而是“文献发现与初筛”。

它又分两大任务：

1. **PDF Screener（文献筛选）**
2. **Data Extractor（图片与文本提取）**



### 5.1 全局 API 设置区

这部分在页面顶部，属于全局设置。

#### 关键控件

| 控件 | 用途 | 实际影响 |
|---|---|---|
| Text LLM API | 文本模型设置 | 用于 PDF 文献筛选 |
| Multimodal LLM API | 图文模型设置 | 用于启用多模态验证后的 figure 复核 |
| Use same provider as Text LLM | 复用文本模型接口 | 适合文本模型也支持图像输入的情况 |
| Image Detail | 图像输入细节 | 影响多模态模型读取图像的细节程度 |
| Remember API Key | 是否持久化保存密钥 | 勾选后会写入本机设置文件 |
| Save API Settings | 保存当前 API 配置 | 下次启动可自动恢复 |

Text LLM 和 Multimodal LLM 可以不同。实际工作中，常见做法是用较快、较便宜的文本模型先筛 PDF，再用支持图像输入的多模态模型复核 figure。

API key 不属于筛选或图版 profile。它只属于本机运行设置，不应该写进开源模板。

#### 什么时候要改 API Protocol

如果你用的是一些代理或中转服务，而不是标准 OpenAI 直连，那么 `Auto` 不一定总能成功。

特别是你之前已经碰到过的兼容服务场景：

- 某些服务更适合 `Responses API`

建议原则：

- **不知道时先用 Auto**
- 如果模型能连通但报协议类错误，再切到 `Responses API`

### 5.2 逻辑方案（Logic Profile）

这部分分成两条并列方案。

#### 你会看到的控件

- `Select Logic Profile`
- `Figure Extraction / Review Profile`
- `Delete Profile`
- `Advanced Logic Settings`
- `Advanced Figure Settings`

#### 方案的本质

方案不是一个“装饰性配置”。

`Select Logic Profile` 决定 PDF 文献筛选：

- 核心关键词
- 支持性关键词
- 排除关键词
- 目标类群词
- LLM 提示词模板
- 一些运行参数

`Figure Extraction / Review Profile` 决定下游 figure 阶段：

- 怎样识别 caption
- 哪些词算目标分类学证据
- 哪些章节进入 `species_core` 和 `species_extended`
- 期望哪些视图或结构
- 启用多模态验证时，模型按什么规则复核 figure

#### 当前筛选流程

PDF 筛选现在使用 **V2 (CSV Full LLM)** 流程。

关键词词库是辅助材料，真正的 include / exclude / uncertain 判定标准由当前方案里的 LLM 提示词决定。

对实际研究的意义是：你可以把蚂蚁筛选方案复制成植物、甲虫或其他类群方案，只要同步改目标类群词、支持性形态词、排除词和提示词。

Figure profile 也可以复制改写。不开多模态验证时，它仍会影响图文提取阶段；启用多模态验证时，它的复核规则会继续传给多模态模型。

### 5.3 高级逻辑设置（Advanced Logic Settings）

这是最容易误用的一块，因为它看起来像“普通设置”，但其实会直接影响筛选结果。

#### 里面主要有哪些东西

- 核心关键词
- 支持性关键词
- 目标类群关键词
- 强排除词
- 弱排除词
- 生物干扰排除词
- LLM 提示词模板

#### 什么时候应该改这里

适合改的情况：

- 你换了研究对象或目标类群
- 你发现当前方案对某类文献漏得太多
- 你发现某类非目标论文总被误纳入

不建议随意改的情况：

- 只是想“试试能不能更准”
- 对某个词的作用还没有明确经验

更稳妥的做法是：

1. 先另存为新方案
2. 用新方案做一小批测试
3. 确认效果后再作为常用方案

### 5.4 V2 筛选流程

这是现在推荐的主模式。

它的思路是：

1. 先提取每篇 PDF 的文本摘要信息
2. 形成统一 CSV 队列
3. 批量送给 LLM 做完整判断
4. 按置信度和判断结果分流

适合：

- 中大规模筛选
- 想保留恢复能力
- 想保留完整审计轨迹

### 5.5 V2 运行参数：每个都是什么意思

这一组控件直接影响：

- 每篇 PDF 提取多少文本
- 每批发多少记录给 LLM
- 单批字符预算
- 超时与失败拆分策略

#### 参数说明

| 参数 | 含义 | 实际影响 |
|---|---|---|
| Lines/PDF | 每篇 PDF 抽取前多少行文本 | 太少可能丢信息，太多会增加 prompt 负担 |
| Batch Size | 每批送审记录数 | 越大越快，但更容易超出预算 |
| Fallback Batch | 批次太大失败时的备用批次大小 | 拆分失败批时使用 |
| Include Threshold | 纳入阈值 | 越高越严格 |
| Prompt Char Budget | 单批 prompt 字符预算 | 影响是否要拆批 |
| Text Chars/File | 单篇 PDF 最大送审文本长度 | 控制每篇文本截断 |
| LLM Max Tokens | 单次输出 token 上限 | 太低可能截断答案 |
| LLM Timeout(s) | 单次 LLM 请求超时 | 太低会误判网络/服务不稳 |

#### 三个安全开关

| 开关 | 推荐 | 作用 |
|---|---|---|
| Auto Split Failed Batches | 建议开 | 批次失败时自动拆小重试 |
| Resume Interrupted Runs | 建议开 | 允许中断后继续 |
| Isolate V2 Runs | 建议开 | 每次运行单独建目录，减少结果混淆 |

### 5.6 开始批量分类（Start Classification Batch）

运行前你至少要准备好：

1. 输入 PDF 文件夹
2. 输出目录
3. API 配置
4. 方案与模式匹配

#### 这个按钮按下去后会发生什么

程序会记录本次运行参数，并在日志里明确写出：

- 模式
- 每篇提取行数
- 批次大小
- 字符预算
- 超时时间
- 阈值
- 是否允许拆批、恢复、隔离
- 当前 API 协议

这意味着：

> 它不只是“开始运行”，而是在创建一份可追踪的运行上下文。

### 5.7 停止分类（Stop Classification）

这个按钮不是“立刻硬杀进程”。

它的语义是：

- 请求停止
- 等待当前 PDF 或当前批次收尾
- 尽量保存已有结果

所以你看到“正在停止，请等待当前 PDF 完成或超时”的提示时，不代表按钮没反应，而是程序在做**合作式停止**，避免直接把运行状态搞坏。

---

## 6. 数据工具：浏览数据库、查看 CSV、导出粗 JSONL

### 6.1 Data Extractor：从 PDF 到 SQLite 数据库


在第二个标签页里，你会设置：

- 输入文件夹（通常是第一阶段筛出来的 PDF）
- 输出数据库路径（SQLite `.db`）
- 是否启用多模态验证

#### 启用多模态验证意味着什么

勾选后：

- 提取出来的 figure 候选会进一步经过多模态模型复核
- 速度更慢
- 但对“图版结构是否符合当前 Figure profile”“是否真的是目标分类学图版”这类判断更可靠

不勾选时：

- 程序仍可运行
- 但进入的将是 mock/default 路径
- 结果会被导向 **Review / needs_review**，而不是当作真正 accepted

#### 这一步最重要的逻辑边界

提取阶段现在是**整张 figure 优先**，不是自动把 panel 拆成多张小图。

也就是说：

- 程序主要目标是抓到“完整可用的目标分类学 figure”
- 蚂蚁示例默认关注 `lateral / dorsal / head_frontal`
- 其他类群可以通过 Figure profile 改成叶、花、果、种子、生殖器、翅脉、显微结构等字段

这一点在使用时一定要有心理预期。

### 6.2 提取前的确认弹窗为什么很重要

如果真实多模态验证不可用，比如：

- 你没填 API key
- base URL 缺失
- validator 初始化失败
- 你主动没勾选启用多模态验证

程序在开始提取前会弹出确认框。

这不是打扰你，而是在防止一种很危险的误解：

> 你以为自己现在得到的是“真正审核通过的 accepted 图”，但其实只是 mock/default 路径下的临时结果。

### 6.3 提取后的数据库里到底存了什么

核心数据库是 SQLite，关键表包括：

- `pdf_files`
- `figure_records`
- `figure_evidence`
- `extraction_stats`

#### 你最常看的其实是 `figure_records`

它记录了：

- 页面位置
- 物种候选
- 最终置信度
- 是否 accepted
- 是否 comparison figure
- 是否 multiple species
- 检测到哪些视角
- `review_status`
- `multimodal_review_mode`
- `multimodal_model_used`

#### 一定要记住两个状态字段

| 字段 | 代表什么 |
|---|---|
| review_status | 当前结果是 accepted / needs_review / rejected |
| multimodal_review_mode | real / mock / none |

不要只看 `accepted` 一个值来判断图是否真的可靠。

### 6.4 Browse Database：浏览数据库

这个按钮会打开数据库浏览器。

你会看到：

- 左侧表格：每张图的基础记录
- 右侧详情：图片预览 + 文本证据 + 审核状态 + 模型信息

这是你做人工复核时最有用的界面之一。

适合回答这些问题：

- 这张图为什么被 accepted？
- 它是 real 还是 mock？
- 哪些文本证据支持这个判断？
- 图注说的是什么？

### 6.5 View Detailed CSV：查看分类结果 CSV

这通常在分类完成后的结果窗口里打开。

它适合干什么：

- 快速看一批 PDF 的文本摘要和 LLM 决策
- 排查某些 PDF 为什么被排除
- 查 `extract_source` 是 `text_layer / ocr / failed`

### 6.6 Export Raw JSONL：导出粗数据

这个按钮导出的不是最终高质量训练集，而是：

> **从 PDF 自动提取出来的粗数据集**

它适合：

- 做快速验证
- 做外部脚本处理
- 看原始抽取效果

它不适合直接当最终正式训练真值。

程序也会在导出前明确提醒这一点。

### 6.7 PDF 侧常见输出目录

#### V2 筛选典型输出

如果启用隔离运行，常见结构会长这样：

```text
<output_folder>/
├── v2_runs/
│   └── run_.../
│       ├── resume_state/
│       │   ├── run_index.json
│       │   ├── master_queue.csv
│       │   └── csv_batches/
│       ├── core_results/
│       │   ├── master_results.csv
│       │   ├── selected_record_ids.csv
│       │   ├── move_manifest.csv
│       │   ├── final_new_species_reports/
│       │   └── manual_review_uncertain/
│       └── debug_evidence/
│           └── batch_raw_responses/
└── v2_active_run.json
```

#### 提取阶段典型输出

```text
<db_stem>_v2_artifacts/
├── figure_images/
├── review_batches/
└── batch_raw_responses/
```

对研究工作来说，最常看的通常是：

- `final_new_species_reports/`
- `manual_review_uncertain/`
- `figure_records` 数据库内容
- `batch_raw_responses/`（当你要排查模型判断时）

---

## 7. 标注工作台：从图片列表到正式标注


如果你想从工作台进入 Blink，重点找 **`Open in Blink Workbench / 在 Blink 工作台中打开`**。而“当前结构标签”并不是由画布自动猜出来的，而是由 `Structures` 列表里你当前选中的标签决定。

### 7.1 图片导入

工作台里常见的入口有两个：

1. `+ Add Images`
2. `Import & Crop`

#### + Add Images

适合：

- 你已经有单张图片或一批图片文件
- 不需要先拆视角

它会把这些图片加入当前项目，并为每张图初始化标签条目。

#### Remove Image

这是从项目里移除图片及其关联状态，而不是删除你磁盘上的原始文件本体。

但对项目来说，它仍然是高风险操作，因为会一起丢掉该图的标签与比例尺信息。

### 7.2 Structures / 结构标签列表

右侧 `Structures / 结构标签` 面板是整个标注工作的核心入口之一。

#### Add Structure

作用：

- 向当前项目 taxonomy 增加一个结构标签

适合：

- 你当前项目需要新增要标注的结构，例如 Leaf、Flower、Wing、Mandible

#### Remove Structure

这是高危按钮。它不是只把“列表项删掉”，而是：

- 从 taxonomy 中删掉该结构标签
- 同时删除所有图片里这个结构标签对应的：
  - polygon
  - description
  - manual box
  - auto box
  - Blink trajectory

所以它本质上是“全项目删除该结构标签的数据”。

### 7.3 Taxon / 分类单元与描述

工作台右侧的 `Taxon / 分类单元` 下拉框和描述框，是把“图像标注”和“分类学语义”联系起来的关键。

- `Taxon`：给当前图片设置分类单元，可以是属名、种名、候选分类名或你当前项目需要的分类标识
- 描述框：可以记录当前部位的描述文本

这意味着：

- 你不只是画多边形，还能把文字语义一起留下
- 后续多模态导出时，这些文本会真正进入样本

### 7.4 三种主要标注模式

#### Manual Draw

最直接、最可靠，适合做正式真值。

#### Magic Wand (SAM)

点击一点，SAM 预测一个分割结果。

适合：

- 轮廓清楚
- 你想快速出一个初稿，再手修

#### Box Prompt (SAM)

先框一个范围，再让 SAM 在框内分割。

适合：

- 目标结构位置清楚
- 但用点提示不稳定

### 7.5 亮度和对比度滑块

这两个滑块只是显示增强：

- `B:` 亮度
- `C:` 对比度

它们的作用是帮你看清结构，**不会改原图文件，也不会改项目标注数据**。

### 7.6 形态测量（Morphometrics）

勾选 `Enable Morphometrics` 后：

- 会显示 `Scale Tool`
- 会显示 `Measurements` 面板

#### Scale Tool

你先在图上画出一段已知长度，再输入它实际是多少毫米。

程序会把这段像素长度换算成 `pixels_per_mm`。

之后当前部位如果有 polygon，就会自动计算：

- 面积
- 周长

#### 这部分为什么重要

它不是“附赠功能”，而是把标注从纯视觉轮廓提升到可量化形态数据的桥。

不过一定要记住：

- 没设比例尺 → 不能做有效测量
- 没 polygon → 没法算面积和周长

### 7.7 工作台里的自动推理

#### Auto (Current)

只对当前图片跑一轮自动推理。

它的特点是：

- 会把自动预测写入项目
- 但只补“当前还没有的部位”
- 不会直接覆盖已有手工标注

#### Batch (All)

批量推理只针对**当前未标注图片**。

所以它更像“批量补初稿”，而不是“批量覆盖重算全部项目”。

### 7.8 Clear AI Labels

这个按钮不是“清空所有标注”，而是：

- 删除被标记为 `Auto-Annotated` 的自动标签
- 保留人工标注

它适合什么时候用：

- 你试了一轮自动推理，结果不满意
- 想保留手工成果，但清掉自动生成部分重新来

要注意的是：

- 它清的是自动标签语义，不等于“整个项目完全回到没推理过”

---

## 8. Cropper 裁剪器：把一张大图拆成多个视角图

Cropper 的作用不是正式标注，而是：

> 把一张含多个视角或多个子图的大图，拆成你后续要单独处理的视角图。


使用时，真正决定“生成哪些新图片”的不是裁剪列表本身，而是你在原图上画出来的裁剪框。点击 **`Save & Add to Project`** 后，程序会在原图同目录生成类似 `*_view_1.jpg`、`*_view_2.jpg` 的新图片，并把这些裁剪图自动加入当前项目。

### 8.1 常见进入方式

- 工具栏 `Import & Crop`
- 文件列表右键单图时的 `Crop this Image`

### 8.2 基本流程

1. `Load Image`
2. 在图上拖拽画出一个或多个裁剪框
3. `Undo Last Crop` 可以撤销最后一个框
4. `Save & Add to Project`

### 8.3 保存后会发生什么

程序会：

- 在原图附近生成类似 `原图名_view_1.jpg` 的文件
- 自动把这些新裁剪图加入项目

#### 这意味着什么

- 原图不会被修改
- 裁剪图会变成项目里的正式新图片
- 后续可以对每个裁剪图独立标注和训练

这对蚂蚁分类图谱尤其重要，因为一张版面图里常常混着多个视角或多个局部。

---

## 9. Blink 工作台：局部精修、轨迹积累与专家训练

这是本次工作中刚刚被真正“做顺”的部分，所以这里我讲得特别详细。

### 9.1 先记住 Blink 的定位

Blink 不是用来替代大部位定位器的。

它更适合做：

- 小结构精修
- 轨迹积累
- 微观专家训练

也就是：

> **大部位先在工作台解决，细部位再进 Blink。**

### 9.2 从工作台进入 Blink 的正确方式

现在推荐流程是：

1. 在工作台选中图片
2. 在 `Structures / 结构标签` 里选中要精修的目标结构
3. 点击 `Open in Blink Workbench`
4. 在弹窗里确认：
   - `Target Part`
   - `Entry ROI`


这两个概念不要混成一个。Target Part 决定“你要修谁”，Entry ROI 决定“你从哪里放大进去看”。

当前更稳妥的理解方式是：

- **Target Part = 子部位**
- **Entry ROI = 父级/上下文视野**

例如：如果你这次要精修 `Eye`，通常会让：

- `Target Part = Eye`
- `Entry ROI = Head`

#### Target Part 是什么

这次真正要修的部位。

#### Entry ROI 是什么

这次从哪个已有框进入局部视图：

- 手工框
- 自动框

它们的意义不是“要训练谁”，而是“从哪里放大进去”。

### 9.3 进入 Blink 后你看到的是什么

进入后主要会有三类控制内容：

- 部位、工具和专家模型选择
- 局部画布
- Blink 控制区和训练区

当前会话下，程序会：

- 按 Entry ROI 聚焦
- 保留必要上下文框
- 但把真正可编辑的目标收紧到当前 target part


Blink 的阅读逻辑是：先通过较大的 ROI 进入局部区域，再在局部画布里精修当前目标部位，最后根据需要决定是只生成 trajectory，还是正式把结果写回主项目。

### 9.4 `Sync from Workbench`

它的作用是：

- 把主工作台当前这张图的状态重新拉进 Blink

但现在它已经不是“无脑刷新”了。

如果当前 Blink 会话有还没应用的本地修改，程序会先要求你确认是否放弃。

所以它本质上是：

- **同步按钮**
- 不是**强制覆盖按钮**

### 9.5 `BLINK SWITCH`

这是一个最容易被误会的按钮。

它做的只是：

- `NORMAL`
- `INSIDE`
- `OUTSIDE`

三种局部观察/遮罩模式之间的循环切换。

#### 它不做什么

- 不保存标注
- 不生成轨迹
- 不训练模型
- 不写回全局

它只是帮助你从不同视角看局部结构。

### 9.5.1 `AUTO-ANNOTATE DRAFT`

这个按钮的语义是：

> **如果当前部位已经有可用的 Blink 专家，就先让专家给一个局部框，再让基础 SAM 生成一份可精修的 polygon 草稿。**

#### 它适合什么时候用

- 当前目标部位已经训练过专家
- 你希望先拿一个系统起好的初稿，再人工精修

#### 它做的事情

1. 当前路由指定专家先在当前 Entry ROI 里给出一个更准的小框
2. 基础 SAM 用这个框生成 draft polygon
3. 你在这个 draft polygon 基础上继续精修

#### 它不做的事情

- 不会自动生成 shrink 轨迹
- 不会自动写回主项目
- 不会替代后面真正要画的松散 shrink 框

#### 如果你看到报错

最常见的原因是：

- 当前 `父部位 -> 子部位` 路由还没有指定可用专家模型

比如你在 Blink 里把目标设为 `Eye`，但当前项目还没有为 `Head -> Eye` 这类路由指定专家，这个按钮就不会成功。先训练候选专家，再在模型设置或 Blink 当前路由中手动指定。

### 9.5.2 `Draw Box (For SAM Draft)`

这条路是给你这种“我自己更相信手工 prompt 框”的工作方式准备的。

它的语义是：

> **你自己先画一个提示框，基础 SAM 根据这个框起一份草稿 polygon，然后你再精修。**

#### 这和 `Draw Box (For Shrink)` 不是一回事

- `Draw Box (For SAM Draft)` = 给 SAM 的临时提示框
- `Draw Box (For Shrink)` = 后面生成 trajectory 的松散框

这两个框不要混成一个。

#### 推荐理解方式

先用这条路做：

1. 人工给 SAM 一个高质量提示框
2. 拿到 draft polygon
3. 精修 polygon

然后再单独画：

4. 一个更松散的 shrink 框
5. 再执行 `EXECUTE AUTO-SHRINK`

#### 为什么这样设计

因为你前面这个提示框的作用只是：

- 帮基础 SAM 起草

而后面的 shrink 框作用是：

- 给 Blink 生成“从松框收缩到目标结构”的训练轨迹

### 9.6 `EXECUTE AUTO-SHRINK`

这个按钮的语义是：

> **生成轨迹训练材料**

#### 使用前提

你至少要有：

1. 一个松散框
2. 一个黄金标准 polygon

也就是：

- 框 = 起点
- polygon = 最终目标

#### 按下后发生什么

程序会生成一串逐步收缩的轨迹，并立即把这些轨迹存进项目的：

`trajectories[part_name]`

#### 非常关键：这一步已经进入 Blink 训练数据集

也就是说：

- 你**不需要先点 Apply to Global** 才能让它进入 Blink 训练数据
- 只要 Auto-Shrink 成功，trajectory 就已经进项目文件了

#### 这里特别要再强调一次

前面用于给 SAM 起草的提示框：

- 不会自动变成这里的松散框

所以当前更稳妥的实际顺序是：

1. 用 `AUTO-ANNOTATE DRAFT` 或 `Draw Box (For SAM Draft)` 拿草稿
2. 把 polygon 精修准
3. 再切换到 `Draw Box (For Shrink)` 单独画松散框
4. 再执行 `EXECUTE AUTO-SHRINK`

### 9.7 `APPLY TO GLOBAL`

这是另一个最容易和 Auto-Shrink 混淆的按钮。

它的语义是：

> **把这次局部精修结果正式采纳进主项目标注**

#### 它做的事情

- 把 Blink 局部视图里的结果逆投回整张图坐标
- 只写回当前目标部位
- 通知主工作台刷新

#### 它不做的事情

- 它不是训练入库按钮
- 它不是生成 trajectory 的按钮

#### 最好这样理解

- `EXECUTE AUTO-SHRINK` = 保存“训练经验”
- `APPLY TO GLOBAL` = 保存“正式答案”

### 9.8 `TRAIN EXPERT MODEL`

这个按钮只训练：

- 当前选中的部位
- 当前项目里这个部位的 trajectory 数据

它不会：

- 把所有已标注部位混在一起训练
- 自动把普通 polygon 全部当成 Blink 训练数据

所以如果你要训练某个部位的 Blink 专家，真正关键的不是“画了多少 polygon”，而是：

> **这个部位积累了多少条可靠 trajectory。**

训练前你可以在 Blink 工作台里临时调整：

- Epochs
- Batch Size
- Learning Rate
- Weight Decay
- Input Size

其中 `Input Size` 使用预设值，不建议随意填任意尺寸。小部位训练通常可以从 `224` 或 `384` 开始；如果细节很小、显存足够，再考虑 `512`。

训练开始后：

- 进度条会显示大致训练进度
- Training Log 会持续输出 loss 和保存信息
- `STOP TRAINING` 可以在当前 batch / epoch 后合作式停止

训练完成后，新专家会保存为类似：

`expert_v20260512_153000.pth`

它只是一个新的候选模型，不会自动替换你已经指定到路由上的专家。你需要结合训练报告和实际自动标注效果，决定是否把它 `Appoint to Current Route / 指定到当前路由`。

如果当前路由已经有你满意的专家，新训练出来的模型会排到候选列表前面，但不会覆盖原来的路由指定专家。

如果你在大量训练后想记住某个候选的特点，可以在已训练专家列表里选中具体 `.pth` 文件，然后点击 `Edit Note / 编辑备注`。备注只改变列表和项目路由树里的显示名，例如“侧面稳定”“背面 384 较好”，不会重命名模型文件，也不会改变当前路由绑定。删除对应专家文件或整个专家桶时，程序会同步清理这些备注。

### 9.9 Blink 里的脏会话（dirty session）保护

如果你已经在 Blink 里：

- 画了框
- 改了 polygon
- 做了 auto-shrink

但还没应用到全局，程序会把当前会话当作“有未保存局部修改”。

这意味着：

- 切图不会再静默覆盖
- 强制同步前会提醒你
- 开新会话也会先确认

这对细结构标注非常重要，因为这类工作最怕的不是算法慢，而是**改了半天结果被刷新冲掉**。

---

## 10. 模型设置、训练、推理与 AI 标注清理

### 10.1 Model Settings


这里管理三类东西：

1. **训练参数**
2. **推理参数**
3. **外部脚本后端**

#### 训练参数常见项

- Runtime Device
- Epochs
- Batch Size
- Learning Rate
- Weight Decay
- Main Locator Parts / 主定位结构
- Blink Expert Training Defaults / Blink 专家训练默认值

#### Runtime Device / 运行设备

这里控制内置 `Locator / SAM / Blink` 的训练和推理使用什么计算设备：

- `Auto (CUDA if available)`：默认推荐。有 NVIDIA CUDA 环境时用显卡，否则退到 CPU。
- `CPU only`：强制使用 CPU，适合无显卡机器上的安装验证、小规模流程测试或只做标注整理。
- `CUDA GPU`：要求使用 CUDA；如果当前 PyTorch 环境识别不到 CUDA，程序会退到 CPU，但正式训练前应先检查安装环境。

CPU 路径的意义是让项目不把用户群体限制死，但不要把它理解成正式训练推荐配置。Locator、SAM 和 Blink 专家都可以在 CPU 路径上尝试运行，小数据测试可以接受；正式训练，尤其是 Blink 的 `384 / 512` 输入尺寸和 SAM 训练，仍建议使用 CUDA 版 PyTorch 和 NVIDIA 显卡。

外部脚本后端不受这个选项直接控制。外部后端使用你在命令里指定的 Python 环境、脚本和依赖。

#### Main Locator Parts / 主定位结构

这是多类群项目里最容易影响训练结果的一项。

它决定哪些结构会进入内置 Locator 的“大目标定位”训练。一般建议：

- 大而稳定、容易先定位的结构放进 `Main Locator Parts`
- 很小、需要局部放大的结构仍然保留在 `Structures`，但不一定交给主 Locator
- 细部位可以后续用 SAM、Blink 专家或外部脚本后端继续精修

举例：

- 蚂蚁模板通常是 `Head / Mesosoma / Gaster`
- 植物项目可以只把 `Leaf / Flower / Fruit` 这类主结构放进去
- 刚毛、气孔、微小脉序细节这类目标，不建议随手塞进主 Locator，除非你的模型和训练数据本来就是为它们设计的

如果你改了主定位结构，旧的 Locator 权重可能不再匹配当前项目。程序会提醒你重新训练或选择匹配的新模型。

#### Blink Expert Training Defaults / Blink 专家训练默认值

这组参数不是主模型训练参数，而是 Blink 工作台里训练细部位专家时的默认值。

它包括：

- Default Blink Epochs
- Default Blink Batch Size
- Default Blink Learning Rate
- Default Blink Weight Decay
- Default Blink Input Size

保存后，Blink 工作台会自动使用这些默认值。你仍然可以在训练某个具体专家前临时修改。

实际研究中，如果某个细部位专家效果不好，优先检查：

- trajectory 数量是否太少
- 文献缩略图是否太糊
- Learning Rate 是否过大或过小
- Input Size 是否需要提高
- 当前路由上是否仍指定着旧专家，而不是刚训练的新候选

#### 推理参数常见项

- Confidence Threshold
- Adaptive Thresh Ratio
- Noise Floor
- Polygon Simplification
- Box Padding Ratio

#### 这些参数会影响什么

- 检得严不严
- 框会不会过大或过小
- polygon 会不会太碎

#### External Backend / 外部脚本后端

这是一个高级入口，适合有自己模型训练或推理脚本的用户。

它的用途是：

- 让 TaxaMask 调用你的外部训练脚本
- 让 TaxaMask 调用你的外部推理脚本
- 把外部模型输出重新导回当前项目，继续人工复核、再训练和导出

外部后端不要求 TaxaMask 理解你的模型内部结构。TaxaMask 只负责：

1. 创建独立的 `external_runs/` 运行目录
2. 写出 `contract.json`
3. 启动你填写的命令
4. 读取标准预测 JSON 或模型 manifest

命令编辑区是多行文本，可以临时修改长命令。命令中必须保留以下占位符之一：

- `{contract}`
- `{contract_json}`

常见命令形式：

```bash
{python} scripts/train_model.py --contract {contract_json}
```

也可以使用：

```bash
{python} scripts/predict_image.py --contract {contract}
```

点击 `Validate External Backend` 可以检查：

- 外部后端 ID 是否填写
- 是否至少填写了训练命令或推理命令
- 已填写命令是否包含 `{contract}` 或 `{contract_json}`

#### 选择外部后端后会发生什么

如果模型后端选择为 `External Script Backend`：

- `Train Models` 不会启动内置 Locator/SAM 训练线程
- `Auto (Current)` 和 `Batch (All)` 不会调用内置 Locator/SAM 推理
- 程序只会创建 external run、写 contract、运行外部脚本、读回结果

这点很重要。外部后端不是“在内置模型后面再加一步”，而是让外部训练/推理在这次任务里接管模型部分。

外部脚本契约说明在：

`docs/contracts/external_backend_contract_v1.md`

### 10.2 Train Models

工作台里的 `Train Models` 训练的是主模型链，而不是 Blink 微观专家。

它会基于当前项目里已有的标注数据，做：

- Locator 训练
- SAM 分割器训练

如果勾选 `Train Locator only (skip SAM)`，本次训练只训练 Locator，不训练 SAM / parts 分割器。

这个选项适合：

- 基础 SAM 已经能给出足够好的 polygon
- 你当前主要想提高主结构定位能力
- 你想减少一次训练的耗时和显存占用

训练开始后可以点击 `Stop Training`。它不是强制杀进程，而是在当前训练 batch 或 epoch 边界安全停止，尽量避免留下半写入状态。

#### 它需要什么

- 至少有已标注图片
- 结构标签稳定
- 训练预检中至少有可用于 Locator 或 SAM / parts 的样本

### 10.3 Auto (Current)

对当前图片跑一轮推理。

关键点：

- 主要用于补“还没有标注的部位”
- 不会直接覆盖你已有的人工结果

### 10.4 Batch (All)

对当前项目里尚未标注的图片批量推理。

它适合：

- 先批量铺初稿
- 再人工补和进 Blink 精修

### 10.5 Clear AI Labels

这个按钮适合在你“试过自动推理，但决定推倒这轮 AI 初稿”时用。

它会清掉被标为 `Auto-Annotated` 的自动标签结果，但不是简单粗暴地把全部人工成果一起清空。

---

## 11. 导出数据集：Multimodal / COCO / YOLO

路径：`File -> Export Dataset`

### 11.1 Multimodal


适合：

- 后续喂给多模态模型
- 需要同时保留局部裁剪图、全局图和文本描述

输出内容包括：

- `images_global/`
- `crops/`
- `multimodal_dataset.jsonl`

其中每条记录会包含：

- 全局图路径
- 局部裁剪图路径
- 文本描述
- taxon / 分类单元
- taxon_rank
- taxon_metadata
- genus（兼容旧数据处理脚本）
- label
- 局部 segmentation
- 全局 bbox
- source_provenance
- review_status

#### 非常重要：不是所有已画 polygon 的部位都会被导出

当前 Multimodal 导出的一个硬条件是：

> **该部位必须有非空的描述文本（description）**

也就是说，如果你只是：

- 画了 polygon
- 设了 taxon / 分类单元
- 但没有给这个部位留下描述文本

那么它在导出 `multimodal_dataset.jsonl` 时会被直接跳过。

这对操作的实际影响是：

- 如果你准备用 Multimodal 数据集做后续实验，不能只画轮廓
- 还要确保对应部位的描述文本已经填写好
- 否则你会看到“明明画了标注，但 JSONL 里没有这条样本”的情况

当前 Multimodal JSONL 使用：

```text
schema_version = taxamask-multimodal-sample-v1
```

### 11.2 COCO

适合：

- 标准检测/分割训练

输出内容包括：

- `images/`
- `annotations.json`

优先使用手工框；没有手工框时，才从 polygon 自动推导 bbox。

COCO 类别的 `supercategory` 默认使用 `biological_structure`。如果项目模板或项目配置提供了其他值，会按项目配置写出。蚂蚁模板可以继续使用 `ant_part` 作为明确的蚂蚁示例，但通用项目不会被默认写成蚂蚁部位。

### 11.3 YOLO

适合：

- YOLOv8 分割训练

输出包括：

- `images/`
- `labels/`
- `dataset.yaml`

### 11.4 这里一个很重要的研究逻辑

导出不是只是“换个格式”。

它实际上是在决定：

- 你要保留多少语义信息
- 数据以后是给检测、分割，还是多模态模型
- 后续别人是否能审计你这份数据从哪里来

所以导出格式应该根据后续用途选，而不是随便点一个能出文件的就行。

---

## 12. 恢复边界、常见误区与排错建议

### 12.1 最常见误区 1：以为 PDF accepted 就等于正式可用真值

不是。

PDF 侧 accepted 更多表示：

- 在当前筛选/提取逻辑下，它被认为是高价值候选

但它离正式标注真值还有一层距离。

### 12.2 最常见误区 2：以为 Auto-Shrink 就等于已经写回项目

不是。

- Auto-Shrink = trajectory 入库
- Apply to Global = 正式写回主项目

### 12.3 最常见误区 3：以为 Train Expert Model 会拿项目所有标注一起训练

不是。

它只吃：

- 当前部位
- trajectory-backed 样本

### 12.4 最常见误区 4：以为图片搬盘后 GUI 会自动修所有问题

不是。

程序能做的是：

- 按你在本地配置里写好的 `known_relocated_roots` 映射，尝试把旧路径片段解析到新图片库根目录

程序不能做的是：

- 自动修复语法损坏的项目 JSON

### 12.5 最常见误区 5：以为 PDF 侧已经有完整候选审批工作台

现在还没有。

当前现实是：

1. 在数据库里看候选
2. 看 figure 证据和 review 状态
3. 人工决定哪些图真正进入标注项目

这一步仍然是半人工流程，不是完全前端审批流水线。

### 12.6 建议的稳妥使用习惯

1. 大批量 PDF 运行时尽量开启：
   - Auto Split Failed Batches
   - Resume Interrupted Runs
   - Isolate V2 Runs
2. 任何重要标注阶段结束后都主动保存项目
3. Blink 中做完真正要保留的结果后，记得点 `APPLY TO GLOBAL`
4. 要训练 Blink 专家时，优先关注 trajectory 数量，而不是只看 polygon 数量
5. 搬盘后先确认 `known_relocated_roots` 映射和图片路径，再判断是不是 JSON 文件本身损坏

---

## 13. 按钮速查表

### 13.1 主工作台

| 按钮 / 菜单 | 作用 | 会影响什么 |
|---|---|---|
| New Project | 新建项目 | 创建新的项目 JSON |
| Open Project | 打开项目 | 读取项目状态 |
| Save Project | 保存项目 | 持久化当前项目状态 |
| Export Dataset | 导出数据集 | 生成训练/多模态数据 |
| + Add Images | 加图片入项目 | 更新图片列表与标签容器 |
| Import & Crop | 打开裁剪器 | 生成新裁剪图并加入项目 |
| Auto (Current) | 当前图自动推理 | 补充当前图的 AI 标签 |
| Batch (All) | 未标注图批量推理 | 批量补 AI 初稿 |
| Train Models | 训练主模型 | 训练 Locator + SAM |
| Stop Training | 合作式停止主模型训练 | 训练控制 |
| Train Locator only (skip SAM) | 本次只训练 Locator | 训练策略 |
| Clear AI Labels | 清理 AI 初稿 | 删除 Auto-Annotated 标签 |
| Open in Blink Workbench | 显式进入 Blink 工作台 | 创建局部精修会话 |

### 13.2 Blink

| 按钮 | 作用 | 影响层 |
|---|---|---|
| Sync from Workbench | 从工作台重载当前图状态 | 会话层 |
| BLINK SWITCH | 切换观察/遮罩模式 | 显示层 |
| AUTO-ANNOTATE DRAFT | expert 框 → 基础 SAM 草稿 | 局部起稿层 |
| Draw Box (For SAM Draft) | 手工提示框 → 基础 SAM 草稿 | 局部起稿层 |
| EXECUTE AUTO-SHRINK | 生成并保存 trajectory | 训练数据层 |
| APPLY TO GLOBAL | 把局部精修写回正式项目 | 正式标注层 |
| TRAIN EXPERT MODEL | 训练当前部位专家 | Blink 专家模型层 |
| STOP TRAINING | 合作式停止 Blink 专家训练 | 训练控制 |
| Appoint to Current Route | 将候选专家指定到当前父子路由 | 路由配置层 |
| Edit Note | 为候选专家添加展示备注 | 人工记忆标签，不改文件名和路由 |

### 13.3 PDF 处理页

| 按钮 | 作用 | 影响层 |
|---|---|---|
| Save API Settings | 保存 API 配置 | 运行时设置 |
| Advanced Logic Settings | 调整筛选逻辑方案 | 筛选策略 |
| Advanced Figure Settings | 调整图文提取与多模态复核方案 | figure 提取和复核策略 |
| Start Classification Batch | 启动 PDF 筛选 | 分类输出与运行目录 |
| Stop Classification | 合作式停止筛选 | 当前运行状态 |
| Restore Interrupted Run Params | 恢复上次 V2 运行参数 | 续跑准备 |
| Start Extraction Pipeline | 启动 figure 提取 | SQLite 数据库与 artifacts |
| Stop Extraction | 合作式停止提取 | 当前提取运行 |
| Browse Database | 浏览提取结果数据库 | 人工复核 |
| Export Raw JSONL | 导出粗提取数据集 | 粗 JSONL 数据 |

### 13.4 Model Settings

| 按钮 / 控件 | 作用 | 影响层 |
|---|---|---|
| Main Locator Parts | 选择内置 Locator 学哪些主结构 | 主定位器训练范围 |
| Validate External Backend | 校验外部脚本后端配置 | 检查外部后端 ID 和命令占位符 |

---

## 14. 标准流程模板：照着做的一整套操作路线

这一节不是再解释按钮定义，而是把前面已经讲过的功能拼成**可以直接照着走的标准流程**。你以后带别人时，如果对方不想先理解全部原理，也可以先按这些模板操作；等做完一轮，再回头看前面的细节解释，会更容易消化。

---

### 14.1 标准流程模板 A：从原始 PDF 到“进入标注项目的候选图片”

这个模板适合：

- 你手里有一批原始 PDF
- 你想先快速找出可能真正值得标注的图
- 你不想一开始就把全部图片扔进项目里

#### 推荐步骤

**步骤 1：准备 API 与筛选方案**

1. 打开 `PDF Processing`
2. 填好 `Text LLM API`
3. 如果要启用真实多模态验证，再填好 `Multimodal LLM API`
   - 如果你的同一个服务和模型支持图像输入，可以勾选 `Use same provider as Text LLM`
   - 如果文本筛选和图像复核用不同模型，就取消勾选并单独填写
4. 如果你以后还会重复用这套配置，点击 `Save API Settings`
5. 在 `Select Logic Profile` 里选定 PDF 文献筛选方案；如果要试新的筛选逻辑，先去 `Advanced Logic Settings` 里另存为一个新方案
6. 在 `Figure Extraction / Review Profile` 里选定图文提取/复核方案；如果要适配其他类群，先用 `Advanced Figure Settings` 复制模板再修改

**为什么先做这一步**

因为 PDF 侧最容易出问题的不是“按钮不会按”，而是：

- 运行了一整轮，结果发现协议不对
- 选错了目标类群 profile
- 关键词逻辑不是你这次任务需要的
- 文献筛选和图版复核使用了不一致的目标类群

把这些先定好，后面才不至于跑一整晚再返工。

**步骤 2：运行 PDF 筛选**

1. 选择 `Input PDFs`
2. 选择 `Output Dir`
3. 使用默认流程：`V2 (CSV Full LLM)`
4. 建议保持：
   - `Auto Split Failed Batches = 开`
   - `Resume Interrupted Runs = 开`
   - `Isolate V2 Runs = 开`
5. 点击 `Start Classification Batch`

**你要关注什么**

- 日志里是否明确写出了当前模式、batch、timeout、threshold
- 中途是否频繁出现批次错误
- 是否生成了 `v2_runs/run_*/...` 的结果目录

**步骤 3：判断分类结果是否够进入下一步**

跑完后，不要立刻把全部结果都当作可用图像。

先看：

- `core_results/final_new_species_reports/`
- `core_results/manual_review_uncertain/`
- 结果弹窗里的 CSV 细节

**决策原则**

- `final_new_species_reports`：可以优先进入后续提取
- `manual_review_uncertain`：先人工抽查，不要盲目全部放行

**步骤 4：运行 Data Extractor**

1. 在提取页里把输入目录指向上一步通过的 PDF 文件夹
2. 选择输出数据库路径
3. 确认 `Figure Extraction / Review Profile` 是这次任务需要的类群和图版规则
4. 如果你希望更可靠地区分“真正符合目标图版规则的 figure”和“只是看起来像目标图的东西”，建议启用多模态验证
5. 点击 `Start Extraction Pipeline`

**这里最重要的判断点**

如果提取前弹出“mock/default review”确认框，你必须意识到：

> 这轮提取结果更偏“待复核候选”，不是“可直接信任的真 accepted”。

**步骤 5：在数据库里做人类复核**

1. 点击 `Browse Database`
2. 重点看：
   - `review_status`
   - `multimodal_review_mode`
   - 图注与证据文本
3. 不要只看缩略图本身，要结合文本判断它是否真的是你要的图

**最稳妥的进入项目标准**

建议人工优先选择：

- `review_status = accepted`
- 且 `multimodal_review_mode = real`

如果是 `needs_review` 或 `mock`，先人工判断再决定是否导入项目。

#### 这条流程最后得到的是什么

不是“训练数据”，而是：

> 一批已经经过筛选与提取、值得正式进入标注项目的候选图片。

---

### 14.2 标准流程模板 B：从新项目开始，做一轮正式标注与主模型训练

这个模板适合：

- 你刚开始一个新的分类项目
- 你想先建立一套可靠的大部位标注基础
- 目标是训练 Locator / SAM 主链，而不是先做 Blink 专家

#### 推荐步骤

**步骤 1：新建项目并导入图片**

1. `File -> New Project`
2. 给项目起一个明确名字
3. 用 `+ Add Images` 导入图像
4. 如果是一张多视角大图，先用 `Import & Crop` 拆出每个视角，再加入项目

**建议习惯**

- 项目名字尽量对应一个明确任务，不要用含糊名称
- 多视角大图不要直接强行在一张图里标所有结构，拆开后通常更稳

**步骤 2：确认结构标签和分类单元逻辑**

1. 看右侧 `Structures / 结构标签` 是否已经包含本轮需要标注的结构
2. 缺的结构用 `Add Structure` 补充
3. 当前图片的 `Taxon / 分类单元` 在右侧下拉框中设置

**这里最重要的提醒**

- `Remove Structure` 是全项目级删除，不是“只从列表里隐藏一下”
- 结构标签一旦变化，模型结构兼容性也会跟着变化

**步骤 3：在工作台做正式标注**

按可靠性来说，通常建议顺序是：

1. `Manual Draw` 先画最关键的大部位真值
2. 用 `Magic Wand (SAM)` 或 `Box Prompt (SAM)` 辅助补初稿
3. 对明显错误的自动结果做人工修正

**推荐策略**

- 核心大部位先保证稳定手工真值
- SAM 工具用于提速，不要把它当成最终真值来源
- 每做完一张关键图，及时 `Save Project`

**步骤 4：需要测量时再启用形态测量**

1. 勾选 `Enable Morphometrics`
2. 用 `Scale Tool` 设比例尺
3. 再查看面积与周长

**为什么不要一开始就忙着开测量**

因为如果比例尺不稳，测量值就没有研究意义。通常应该先把轮廓标准化，再进入测量阶段。

**步骤 5：训练主模型**

在当前版本里，`Train Models` 不是“只要有标注就一定能开始”的纯傻瓜按钮。

当前主训练入口会先做训练预检，依据项目里已经保存的图片和标注判断哪些样本能进入训练。

训练前更稳妥的判断是：

1. 确保项目里已经有足够的已标注图片
2. 打开 `Settings -> Model Settings` 调整训练与推理参数，并确认 `Main Locator Parts` 只包含这轮要让内置 Locator 学习的主结构
3. 点击 `Train Models`
4. 在训练预检里确认可训练图片数量、结构标签覆盖和排除原因
5. 看训练报告和验证图

**如果你点了训练却立刻报 `Training aborted` 或预检不通过**

优先检查：

- 图片文件是否还存在
- 标注是否已经保存
- polygon 是否有效
- 某些结构标签是否完全没有覆盖
- 当前选择的是内置后端还是外部脚本后端

**训练后你要关注什么**

- 不是只看“训练跑完了没”
- 更要看验证集表现是不是在你当前数据条件下稳定

**步骤 6：回到工作台做一轮自动推理验证**

1. 对单图点 `Auto (Current)`
2. 对一批未标注图点 `Batch (All)`
3. 看自动结果是否足够可用

**如果效果不好怎么办**

- 不要急着继续堆更多自动结果
- 先回头检查：
  - 结构标签是否稳定
  - 大部位真值是否足够干净
  - 模型参数是否过于激进

#### 这条流程最后得到的是什么

你会得到：

- 一个结构清楚的项目
- 一批正式主标注
- 一套可以跑大部位自动化的主模型链

---

### 14.3 标准流程模板 C：用 Blink 做细部位精修、积累 trajectory 并训练专家

这个模板适合：

- 大部位已经有了较稳定的定位和标注
- 你要开始做小结构精修
- 你希望逐步积累 Blink 专家训练数据

#### 推荐步骤

**步骤 1：先在工作台准备好进入条件**

1. 选中一张图片
2. 确保这张图已经有可用 ROI：
   - 手工框，或
   - 自动框
3. 在 `Structures / 结构标签` 里选中这次要精修的目标结构

**为什么这一步必须先在工作台做**

因为 Blink 现在的正确定位不是“从整张图重新开始找”，而是：

> 基于已有大部位或已有 ROI，进入局部精修。

**步骤 2：显式进入 Blink 工作台**

1. 点击 `Open in Blink Workbench`
2. 在弹窗里确认：
   - `Target Part`
   - `Entry ROI`
3. 进入 Blink

**推荐理解方式**

- `Target Part` = 这次真正要修谁
- `Entry ROI` = 你通过哪个框进去看它

不要把这两个概念混成一个。

**步骤 3：在 Blink 里做局部精修**

进入后你可以：

- 如果当前 target 已经有专家，用 `AUTO-ANNOTATE DRAFT` 先起草
- 如果你更相信自己的 prompt 框，用 `Draw Box (For SAM Draft)` 先给基础 SAM 起草
- 用 `Draw Polygon` 精修当前目标部位
- 用 `Draw Box (For Shrink)` 画松框
- 用 `BLINK SWITCH` 切换观察模式

**推荐顺序**

1. 先决定怎么起草：
   - expert 草稿，或
   - 手工框给 SAM 草稿
2. 再把目标部位 polygon 修准
3. 再画一个相对宽松的外框
4. 再用 auto-shrink 生成轨迹

**步骤 4：生成 trajectory**

点击 `EXECUTE AUTO-SHRINK`

满足前提时，它会：

- 生成收缩轨迹
- 立即把 trajectory 写进项目

#### 这里最关键的研究逻辑

这一步的意义是：

> 你在保存“专家该怎样从松框一步步收缩到目标结构”的经验。

它不是在保存最终真值本身，而是在保存**训练过程样本**。

**步骤 5：如果这次局部结果你认可，再正式写回项目**

点击 `APPLY TO GLOBAL`

这一步会：

- 把当前目标部位的局部精修结果投回大图
- 更新主项目正式标签

#### 最稳妥的习惯

- 轨迹生成后，不要想当然地以为正式标注已经更新
- 如果这次精修结果要进入正式项目，记得明确点 `APPLY TO GLOBAL`

**步骤 6：积累到一定量后训练当前部位专家**

点击 `TRAIN EXPERT MODEL`

它当前只会使用：

- 当前项目
- 当前部位
- trajectory-backed 样本

#### 什么时候适合开始训练专家

不是“刚有两三张就急着训”。

更稳妥的判断标准是：

- 这个部位已经积累了多张不同个体、不同姿态、不同质量条件下的 trajectory
- 你已经能稳定地用 Blink 完成这个部位的精修

#### 这条流程最后得到的是什么

你会得到两类东西：

1. **正式项目标签**（通过 `APPLY TO GLOBAL`）
2. **Blink 专家训练材料与专家模型**（通过 `EXECUTE AUTO-SHRINK` + `TRAIN EXPERT MODEL`）

这两者不要混成一回事。

---

### 14.4 标准流程模板 D：当项目搬盘、路径变化或运行中断时，应该怎么稳妥处理

这个模板适合：

- 你整理磁盘或换了存储位置
- V2 运行被中断了
- 项目打开时报路径或 JSON 错误

#### 场景 1：V2 文献筛选中断了

推荐步骤：

1. 保持原来的源目录不变
2. 保持输出目录不变
3. 不要先改一堆参数
4. 点击 `Restore Interrupted Run Params`
5. 确认参数恢复后再继续运行

**不要这样做**

- 一边想续跑，一边顺手换了 prompt、batch、threshold

因为这样很可能让运行签名不一致，程序会拒绝恢复。

#### 场景 2：图片库搬盘后项目打不开图

推荐步骤：

1. 先确认是不是图片路径问题，而不是 JSON 语法问题
2. 如果只是图片库整体搬到了新位置，先在本地配置里写好 `known_relocated_roots` 映射，再尝试打开项目
3. 打开后立刻重新保存项目

**为什么要立刻保存一次**

因为这样能尽快把当前可用路径状态稳定下来，减少后面继续靠兜底逻辑的次数。

#### 场景 3：报 JSONDecodeError

这时不要优先怪路径。

正确判断顺序是：

1. JSON 能不能被正常解析？
2. 如果不能，先修 JSON 语法
3. 语法修好以后，再看图片路径是不是还有效

#### 场景 4：Blink 里改了一半，切图前怕丢

推荐操作：

1. 先判断这次改动是“训练经验”还是“正式结果”
2. 如果 trajectory 已经够用了但正式结果还没确认，可以先不写回全局
3. 如果正式结果也认可了，再点 `APPLY TO GLOBAL`
4. 不要在 dirty session 还没处理完时随便强制同步

---

## 15. 结语：最值得你一直记住的三句话

1. **PDF 侧是在找候选，标注侧才是在造真值。**
2. **Blink 里的 Auto-Shrink 是存训练经验，Apply to Global 才是正式采纳结果。**
3. **路径搬家可兜底，坏 JSON 不会自己变好。**

如果你后面继续扩展这份手册，下一步最值得补的不是再堆功能说明，而是：

- 你们团队内部约定的“accepted / review / 正式入项目”判断标准
- 不同研究任务（筛文献 / 建项目 / Blink 精修）对应的最小数据质量标准
