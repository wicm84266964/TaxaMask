# TaxaMask 完整中文使用手册（main 稳定版）

> 适用版本：TaxaMask main / v1.1 系列公开稳定线。
>
> 适用对象：希望用 TaxaMask 进行分类学文献证据整理、2D 形态图像标注、STL 渲染视角图复核、VLM / SAM / Blink 草稿复核、模型训练与数据集导出的研究者。
>
> 本手册只描述 main 稳定线中已经公开维护的 PDF、2D/STL、Agent、VLM/SAM、Blink、外部后端和数据集导出流程。开发预览分支的连续切片路线由开发版文档单独维护。

---

## 目录

1. [TaxaMask 是什么](#1-taxamask-是什么)
2. [稳定版工作流总览](#2-稳定版工作流总览)
3. [安装与启动](#3-安装与启动)
4. [启动中心与工作流分流](#4-启动中心与工作流分流)
5. [Agent Center](#5-agent-center)
6. [PDF 文献证据路线](#6-pdf-文献证据路线)
7. [项目管理与数据边界](#7-项目管理与数据边界)
8. [2D / STL 标注工作台](#8-2d--stl-标注工作台)
9. [VLM 与 SAM 草稿](#9-vlm-与-sam-草稿)
10. [父部位与子部位标注](#10-父部位与子部位标注)
11. [Child Expert Session / Blink 路线](#11-child-expert-session--blink-路线)
12. [模型方案与外部后端](#12-模型方案与外部后端)
13. [训练、报告与模型备注](#13-训练报告与模型备注)
14. [数据集导出](#14-数据集导出)
15. [Profile 适配](#15-profile-适配)
16. [Agent 辅助修改源码的安全边界](#16-agent-辅助修改源码的安全边界)
17. [标准操作路线](#17-标准操作路线)
18. [常见误区](#18-常见误区)
19. [文件与按钮速查](#19-文件与按钮速查)
20. [排错与维护建议](#20-排错与维护建议)

---

## 1. TaxaMask 是什么

TaxaMask 是一个面向分类学和形态学研究的桌面工作台。它把文献证据、标本图像、AI 草稿、人工复核标签、模型训练、预测复核和数据集导出组织到同一个可追溯流程里。

它的核心原则是：

- AI 可以帮助提出候选，但不能替代研究者确认。
- 文献证据、候选图像、自动草稿、人工标签和导出数据应该分层保存。
- 每个训练样本都应该能追溯到来源图像、标签、模型方案和人工复核状态。
- 大项目要能稳定处理，而不是每次切换图片或删除标签都全量刷新。
- 研究者应该能通过 Agent Center 用自然语言检查项目、理解报错和调整配置。

main 稳定线目前最成熟的是蚂蚁分类学相关的 2D 形态标注和 PDF 文献证据流程。TaxaMask 的 profile、结构标签和外部后端机制可以扩展到其他类群，但新的类群或新任务应先小批量验证，再扩大处理规模。

## 2. 稳定版工作流总览

main 稳定线可以理解成一条人机协同的数据生产线：

```text
PDF / 图像 / STL 渲染视角
  -> 候选材料
  -> AI 草稿
  -> 人工复核
  -> 训练数据集
  -> 模型预测
  -> 再复核
  -> 可追溯导出
```

TaxaMask 中常见的数据状态包括：

- 原始材料：用户导入的标本图片、文献图版、STL 渲染视角图。
- 候选材料：PDF 筛选和图版提取得到的待复核图像。
- AI 草稿：VLM 框、SAM mask、Locator 预测、Blink 预测、外部后端预测。
- 人工确认标签：研究者确认过的 polygon、mask、框和结构标签。
- 训练素材：确认标签加上必要的 provenance 和模型配置摘要。
- 导出数据：COCO、YOLO、multimodal JSONL 等格式。

最重要的边界是：AI 输出不是训练真值。VLM、SAM、Locator、Blink、外部后端和 PDF 提取结果都只是候选材料，必须由研究者确认后才适合作为 ground truth 或正式训练数据。

## 3. 安装与启动

### 3.1 准备环境

建议准备：

- Git，或从 GitHub 下载 ZIP。
- Conda / Miniconda / Mamba 等 Python 环境管理工具。
- Python 3.12。
- Node.js 20 或更高版本，用于内嵌 Agent Center 和恢复面板。
- Windows 用户建议使用带 CUDA 的 PyTorch 环境进行模型训练和推理。

获取 main 稳定线：

```bash
git clone https://github.com/wicm84266964/TaxaMask.git
cd TaxaMask
```

创建环境的方式取决于本机配置。一个常见做法是：

```bash
conda create -n taxamask python=3.12
conda activate taxamask
pip install -r requirements.txt
```

安装 Agent Center 依赖：

```bash
cd vendor/ant-code
npm install
cd ../..
```

### 3.2 Windows 启动

常用入口：

- `启动TaxaMask.bat`
- `启动AntCode修复面板.bat`

`启动TaxaMask.bat` 会尝试寻找可用 Python 环境。如果你使用自定义环境，可以设置：

```bat
set TAXAMASK_PYTHON_EXE=C:\path\to\python.exe
启动TaxaMask.bat
```

如果 GUI 因为本地源码修改或依赖问题无法启动，可以先运行：

```bat
启动AntCode修复面板.bat
```

这个恢复面板不导入 PySide6 GUI，只启动浏览器版 Agent Center，适合在 GUI 坏掉时继续排查和修复。

### 3.3 Linux / WSL 启动

常用入口：

```bash
bash ./启动TaxaMask.sh
bash ./启动AntCode修复面板.sh
```

如果 WSL 发行版不是 `Ubuntu`，按 `wsl -l -v` 显示的名称设置对应变量。路径无法自动转换时，可以设置 Linux 侧项目路径。

### 3.4 SAM checkpoint

可选 SAM 辅助标注需要准备对应 checkpoint。具体路径以当前设置和 `requirements.txt` / README 说明为准。没有 SAM 权重时，TaxaMask 仍可以用于普通人工标注、PDF 证据处理、Agent Center 和数据集整理。

## 4. 启动中心与工作流分流

TaxaMask 当前不是一打开就进入所有功能混在一起的界面，而是先进入启动中心。

启动中心的意义是：

- 让研究者先选择今天要做 PDF、2D/STL 标注、项目配置还是 Agent 排错。
- 避免无关模型和大工作台提前加载。
- 降低大项目打开时的等待和显存占用。

常见入口包括：

- 最近项目。
- 新建或打开标注项目。
- PDF evidence workflow。
- 2D/STL morphology workflow。
- Agent Center。
- 设置和模型方案配置。

进入 2D/STL 标注工作后，日常标注集中在主 Labeling Workbench。Blink 作为子部位专家路线被整合到主工作流中，而不是要求研究者每天进入一个完全独立的 Blink 工作台。

## 5. Agent Center

Agent Center 是 TaxaMask 内嵌的 Ant-Code 工作区。它可以读取项目摘要、公开文档、后端契约和相关源码位置，帮助研究者完成：

- 解释启动、PDF、VLM、训练、导出或标注报错。
- 检查当前项目是否缺少配置或训练素材。
- 解释某个按钮、设置项或模型方案的作用。
- 修改 profile、后端配置或源码。
- 在 GUI 启动失败时，通过恢复面板继续修复。

Agent Center 的重要边界：

- 默认不发送完整项目 JSON、数据库、API key、私有路径或大文件。
- 默认发送的是紧凑上下文，例如当前工作台、活动图片、选中结构、最近日志摘要、相关源码引用。
- 涉及源码修改时，应让研究者确认风险。
- 优先通过 profile、设置、外部后端脚本解决问题；只有这些不足时才改 TaxaMask 源码。

适合问 Agent 的问题：

```text
帮我检查当前项目为什么训练不了。
这个 VLM 预标注为什么没有写入候选框？
帮我解释这个 PDF 提取报错。
当前外部后端配置缺少什么字段？
我想给某个子部位专家换模型方案，应该改哪里？
```

不适合直接让 Agent 做的事：

- 不经检查批量删除项目数据。
- 把 AI 草稿直接当成最终标签。
- 粘贴 API key 或完整私有数据库内容。
- 在没有备份和确认的情况下重写大量源码。

## 6. PDF 文献证据路线

PDF 路线用于把分类学文献转成可复核证据，而不是自动生成训练真值。

### 6.1 PDF 路线能做什么

它可以帮助完成：

- PDF 筛选：根据分类群、关键词、图版质量、文本证据筛选论文。
- 图像提取：提取页面中的图版、候选图、caption 和附近文本。
- 文献性状描述抽取：按 profile 抽取 taxon、part、description 相关内容。
- 候选材料整理：把提取图像和证据整理成可复核记录。
- provenance 记录：保存 PDF、页码、caption、附近文本、profile 和运行信息。

### 6.2 PDF 输出的含义

PDF 输出通常包括：

- 筛选结果表。
- 图像提取数据库。
- 候选图像文件。
- caption / nearby text。
- 文献性状描述记录。
- evidence index。
- 运行日志和 profile 信息。

这些材料的研究意义是“证据和候选”。它们不会自动进入正式训练集。

### 6.3 推荐操作路线

1. 准备 PDF 文件夹。
2. 选择或编辑 PDF screening profile。
3. 先小批量运行，检查筛选结果是否符合研究目标。
4. 运行图像提取。
5. 复核候选图、caption 和附近文本。
6. 将真正可用的图像导入 2D/STL 标注项目。
7. 在主标注工作台中人工确认结构标签。

### 6.4 常见注意事项

- PDF 提取的图像质量可能不适合训练，需要人工筛选。
- caption 和图像之间可能有错配，需要复核。
- 文献中的结构描述是证据，不等于图像标签。
- 不同期刊和扫描质量会影响提取效果。
- 大批量运行前应先用少量 PDF 调 profile。

## 7. 项目管理与数据边界

TaxaMask 项目 JSON 保存的是项目结构和标注记录，不应该塞入大规模运行输出或私有临时文件。

项目通常包含：

- 图片路径。
- 图片分组。
- taxonomy / structures。
- polygon / mask / boxes。
- VLM 目标和草稿。
- 自动预测框和来源元数据。
- 父子部位关系。
- Blink 轨迹和专家路线。
- 模型配置摘要。
- 导出 provenance。

### 7.1 大项目行为

对于几千张图级别的大项目，TaxaMask 会尽量避免：

- 打开项目时自动加载第一张大图。
- 自动预热 Locator / SAM。
- 删除一张图后跳回第一张。
- 每次小操作都全量保存或刷新整个列表。

这对研究流程的意义是：研究者可以在大项目中保持当前位置，不会因为删除、改标签或批量预测反复丢失复核上下文。

### 7.2 删除与重命名

删除图片应同步清理：

- 标签。
- 自动框。
- VLM 草稿。
- 父子部位上下文。
- Blink 轨迹引用。
- 导出相关 provenance。

重命名结构标签应迁移：

- taxonomy。
- 已有标签。
- 自动框和元数据。
- 描述。
- VLM 目标。
- 父级比例。
- Blink 上下文。
- cascade routes。

这样可以避免研究者因为早期命名不准而不得不删除重建整个项目。

## 8. 2D / STL 标注工作台

2D/STL 是 main 稳定线的核心标注路线。

这里的 STL 指的是：把 mesh/STL 通过外部或辅助流程渲染成 2D 视角图，再进入普通 2D 标注工作台复核。main 稳定线不把 STL 当成可直接在 mesh 表面涂标签的工作流。

### 8.1 常见工具

主标注工作台通常包含：

- 图片列表和分组。
- 当前图片显示画布。
- 结构标签列表。
- polygon / mask 标注工具。
- annotation box。
- SAM 点提示和框提示。
- VLM 草稿框显示。
- 模型预测框显示。
- 父部位与子部位标注区。
- 训练和导出入口。

### 8.2 标签状态

研究者应区分：

- 手工标签：研究者明确画出的标签。
- 未确认 AI 草稿：VLM、SAM、Locator 或外部后端生成，还没确认。
- 已确认 AI 草稿：研究者接受后可作为训练素材。
- 模型预测：用于复核，不自动成为真值。

### 8.3 框、mask 和 polygon

不同任务会用到不同标注形式：

- 框：适合定位、父部位上下文、VLM 初步候选。
- polygon：适合清晰边界的结构标注。
- mask：适合 SAM 草稿或更细致的区域标签。

训练前应确认当前任务需要哪种标注形式。不要因为有框就默认它可以替代 mask 或 polygon。

### 8.4 STL 渲染视角图

STL 渲染视角图进入 2D 工作流后，应像普通图片一样复核：

- 确认视角名称。
- 确认结构是否可见。
- 确认标签是否表示屏幕图像上的可见结构。
- 保留来源和视角 provenance。

这种路线适合把表面形态视角纳入同一套标注和训练数据管理中。

## 9. VLM 与 SAM 草稿

### 9.1 VLM 草稿

VLM first-mile preannotation 用多模态模型先提出粗定位框。它适合在大量图片中快速找到候选部位，但不适合作为最终标签。

当前语义：

- VLM 框是低优先级草稿。
- VLM 可以填充空部位或刷新未确认 VLM 草稿。
- VLM 不应覆盖人工标签、已确认标签或模型预测框。
- VLM 框没有 polygon/mask 时，不适合作为训练真值。

### 9.2 SAM 草稿

SAM 可以根据点提示或框提示生成 mask 草稿。

推荐用法：

1. 用框或点提示 SAM。
2. 检查生成 mask 是否贴合目标结构。
3. 必要时手工修正。
4. 明确确认后再让它进入训练素材。

SAM 的首次使用可能需要加载模型，会比后续操作慢。大项目中不要无意义地预热模型，避免占用显存和时间。

### 9.3 清理 AI 标签

`Clear AI Labels` 应谨慎使用。当前设计应让研究者选择范围：

- 全项目。
- 某个图片分组。

确认弹窗应告诉研究者会影响多少图片和多少标签，避免误清真正人工成果。

## 10. 父部位与子部位标注

很多分类学结构不是孤立出现的。子部位定位常常依赖父部位上下文，例如先确定头部、胸部或腹部区域，再在其中寻找更小结构。

TaxaMask 使用父子部位关系来组织这类任务。

### 10.1 父部位

父部位通常用于：

- 给子部位提供局部上下文。
- 限定子部位搜索范围。
- 为 Blink 或外部 child backend 提供 parent ROI。
- 保持不同图片之间的相对定位稳定。

父级 annotation box 可以作为子部位定位的上下文框。固定宽高比选项默认应谨慎使用，只在研究者确实需要统一父级框比例时开启。

### 10.2 子部位

子部位通常更小、更难直接定位。TaxaMask 可以用：

- 父级 ROI。
- 子部位 loose box。
- Blink auto-shrink 轨迹。
- 子部位专家模型。
- 外部 child backend。

来帮助研究者建立更稳定的子部位标注流程。

### 10.3 训练素材含义

父部位和子部位训练素材不完全相同：

- 父部位训练更像全图定位或分割任务。
- 子部位训练更依赖父部位上下文和局部轨迹。

不要把 auto-shrink 轨迹误解成已经被正式接受的 polygon。轨迹可以训练专家，但正式标签仍以研究者确认的项目标签为准。

## 11. Child Expert Session / Blink 路线

用户面对的概念应写作 **Child Expert Session / 子部位专家会话**。源码中保留 `Blink` 命名，是历史兼容和内部模块名。

### 11.1 Blink 能解决什么

Blink 路线用于学习“从父部位上下文找到子部位”的局部经验。

它可以：

- 使用父部位 ROI 作为上下文。
- 记录 auto-shrink 轨迹。
- 训练 ViT-B Blink 或 heatmap Blink。
- 连接外部 Blink 后端。
- 将预测作为候选返回主工作台复核。

### 11.2 日常推荐方式

日常工作应尽量在主 Labeling Workbench 中完成：

1. 选择父部位。
2. 确认父部位框或 mask。
3. 选择子部位。
4. 给出 loose box 或运行子部位专家。
5. 检查预测结果。
6. 人工确认正式标签。

独立 Blink 窗口更多是兼容和开发 fallback，不应被描述成 main 稳定线的日常主入口。

### 11.3 专家路线

子部位专家可能来自：

- 内置 ViT-B Blink。
- Heatmap Blink。
- External Blink backend。

项目路由表负责记录某个父子部位组合使用哪个专家。指定专家和启用路线应由研究者明确确认。

## 12. 模型方案与外部后端

TaxaMask 的模型接入应尽量通过配置和后端契约完成，而不是把每个实验模型都写死进主程序。

### 12.1 模型方案

模型方案记录：

- 父部位模型来源。
- 子部位专家默认路线。
- 外部后端配置。
- 推理参数。
- 训练参数。
- 当前项目路由。

这样导出数据集时，可以同时记录当时使用的模型方案，方便以后复现实验。

### 12.2 Parent 外部后端

Parent 外部后端通常负责对全图或较大结构输出候选框、mask 或 polygon。

契约文档：

- `docs/contracts/external_backend_contract_v1.md`

后端应通过 contract JSON 接收输入，通过 result JSON 返回结果。不要把私有命令、API key 或本机绝对路径提交到仓库。

### 12.3 Child 外部后端

Child 外部后端负责在父部位上下文内预测子部位候选。

契约文档：

- `docs/contracts/external_blink_backend_contract_v1.md`

返回结果仍然是候选，不能跳过人工复核。

### 12.4 配置优先级

遇到模型接入需求时，推荐顺序是：

1. 先检查现有 profile 是否能配置。
2. 再检查外部后端契约是否能接入。
3. 最后才考虑修改 TaxaMask 源码。

这能减少主程序被临时实验模型污染的风险。

## 13. 训练、报告与模型备注

### 13.1 训练范围

大项目中不一定每次都训练全部图片。训练范围可以用于：

- 全项目训练。
- 按图片分组小批量验证。
- 针对某类样本先做快速实验。

训练报告应记录本次训练范围和图片数量，避免后续误以为“小批验证模型”就是“全项目模型”。

### 13.2 父部位训练

父部位训练通常依赖已经确认的父级标签。训练前建议检查：

- 每个目标结构是否有足够样本。
- train / val 划分是否合理。
- 是否混入未确认 AI 草稿。
- 当前模型方案是否正确。
- 训练输出目录是否安全。

### 13.3 子部位专家训练

子部位专家训练依赖父部位上下文和子部位轨迹/标签。

训练前建议检查：

- 父部位 ROI 是否稳定。
- 子部位目标是否命名一致。
- auto-shrink 轨迹是否来自正确父子组合。
- 当前训练范围是否足够。
- 专家备注是否写清楚。

### 13.4 训练报告

训练完成后，应从训练结果入口查看历史报告。报告用于回答：

- 这次训练用了哪些图片。
- 训练范围是什么。
- 哪些结构样本不足。
- loss / IoU / 可视化结果是否异常。
- 输出模型保存在哪里。

### 13.5 模型备注

模型越来越多时，只看时间戳很难区分。建议给父模型和子专家写备注，例如：

- `小批验证-头部-30张`
- `全项目-高epoch`
- `失败样本补训`
- `外部后端对照`

备注不应改变权重文件名，而是保存在单独的备注记录中，便于安全管理。

## 14. 数据集导出

TaxaMask 支持导出多种训练和复核格式。

常见导出包括：

- multimodal JSONL。
- COCO annotations。
- YOLO labels。
- 图像文件或图像路径引用。
- model profile summary。

### 14.1 导出前检查

导出前建议确认：

- 是否只导出已确认标签。
- 是否混入未确认 AI 草稿。
- 图片路径是否可访问。
- 结构标签是否命名一致。
- 当前模型方案摘要是否正确。
- 输出目录是否不是仓库源码目录中的临时位置。

### 14.2 model profile summary

`model_profile_summary.json` 很重要。它记录导出时使用的父模型、子专家、后端配置摘要和相关 profile。

对研究来说，这能帮助回答：

- 这批数据是用哪个模型方案复核出来的。
- 某个导出文件是否来自同一套配置。
- 后续论文或实验记录是否能追溯当时的模型环境。

## 15. Profile 适配

TaxaMask 通过 profile 把通用程序适配到具体研究任务。

常见 profile 包括：

- PDF screening profile。
- figure extraction profile。
- part description extraction profile。
- VLM prompt profile。
- model profile。
- taxonomy / structure template。

### 15.1 适配新类群

适配新类群时不要直接大批量运行。推荐：

1. 建立结构标签和同义词。
2. 小批量导入图像。
3. 试运行 VLM / SAM / 标注 / 导出。
4. 检查标签语义是否稳定。
5. 再扩大规模。

### 15.2 蚂蚁领域默认优势

TaxaMask 起源于蚂蚁分类学工作，因此蚂蚁相关术语、结构模板和使用路径最成熟。这不是错误假设，而是项目历史和当前验证基础。

对其他类群，程序结构可以支持，但研究者需要自己验证 profile 和模型效果。

## 16. Agent 辅助修改源码的安全边界

Agent 可以帮助修改 TaxaMask，但需要遵守边界。

优先顺序：

1. 解释现象。
2. 检查设置和 profile。
3. 检查项目记录和日志摘要。
4. 修改外部后端脚本或配置。
5. 最后才修改 TaxaMask 源码。

修改源码前应说明：

- 会影响哪个工作流。
- 可能影响哪些数据。
- 如何验证。
- 是否需要备份项目。

不应让 Agent 直接：

- 删除用户数据。
- 提交 API key。
- 把模型权重加入仓库。
- 把私有项目 JSON 或数据库发到远端。
- 把未确认 AI 草稿变成正式标签。

## 17. 标准操作路线

### 17.1 PDF 到标注

1. 准备 PDF 文件夹。
2. 选择 screening profile。
3. 小批量筛选。
4. 检查筛选结果。
5. 提取图版和 caption。
6. 复核候选图像。
7. 将可用图像导入标注项目。
8. 人工标注或复核 AI 草稿。
9. 导出训练数据。

### 17.2 普通图片标注

1. 新建或打开项目。
2. 导入图片。
3. 建立结构标签。
4. 标注父部位。
5. 标注子部位。
6. 使用 SAM/VLM 作为草稿辅助。
7. 确认标签。
8. 训练或导出。

### 17.3 STL 渲染视角图复核

1. 准备 STL 渲染出来的 2D 视角图。
2. 导入项目。
3. 记录视角来源和命名。
4. 像普通 2D 图片一样标注。
5. 导出时保留视角 provenance。

### 17.4 子部位专家训练

1. 标好父部位。
2. 为目标子部位提供足够样本。
3. 运行或记录 auto-shrink 轨迹。
4. 选择训练范围。
5. 训练子部位专家。
6. 查看训练报告。
7. 指定专家到当前路线。
8. 用预测结果辅助复核，而不是直接当真值。

### 17.5 外部后端接入

1. 阅读对应契约。
2. 准备后端脚本。
3. 让脚本读取 contract JSON。
4. 输出 result JSON。
5. 在 TaxaMask 中配置命令模板。
6. 小批量验证。
7. 检查候选结果和 provenance。
8. 扩大运行。

## 18. 常见误区

误区 1：AI 预测框就是训练标签。

正确理解：AI 预测框只是候选。只有研究者确认后，才适合进入训练数据。

误区 2：PDF 图版提取后可以直接训练。

正确理解：PDF 图版是证据来源。图像质量、结构可见性、caption 对应关系都需要复核。

误区 3：STL 路线是在 mesh 上直接涂标签。

正确理解：main 稳定线里，STL 是渲染视角图进入 2D 标注流程。

误区 4：Blink 是一个必须单独打开的日常工作台。

正确理解：用户面对的是主标注工作台里的 Child Expert Session。独立 Blink 窗口更多是兼容和开发 fallback。

误区 5：训练范围越大一定越好。

正确理解：小批量训练适合验证方案，全项目训练适合稳定路线。二者用途不同，报告和备注要写清楚。

误区 6：Agent 可以自动判断所有研究语义。

正确理解：Agent 可以辅助检查和修改，但最终研究判断仍由研究者确认。

## 19. 文件与按钮速查

### 19.1 重要源码位置

```text
AntSleap/main.py                         主窗口、2D/STL 工作台、设置与工作流入口
AntSleap/ui/canvas.py                    2D 标注画布
AntSleap/ui/pdf_processing_widget.py     PDF 工具界面
AntSleap/ui/taxamask_agent_panel.py      Agent Center 面板
AntSleap/ui/blink_lab.py                 Blink 兼容/开发界面
AntSleap/core/project.py                 主项目数据结构、导出和标签管理
AntSleap/core/vlm_preannotation.py       VLM 草稿逻辑
AntSleap/core/sam_helper.py              SAM worker
AntSleap/core/model_profiles.py          模型方案
AntSleap/core/external_backend.py        parent 外部后端
AntSleap/core/external_blink_backend.py  child 外部后端
AntSleap/core/cascade_routes.py          父子部位路线
core/pdf_processor/                      PDF 筛选和图像提取逻辑
tools/agentic/                           命令行辅助工具
docs/contracts/                          外部后端契约
vendor/ant-code/                         内嵌 Agent Center
```

### 19.2 重要文档

```text
README.md                  GitHub 英文入口
README_zh.md               GitHub 中文入口
TaxaMask使用手册.md        当前中文使用手册
LLM_CONTEXT_DETAILED.md    Agent / 大模型对接上下文
ANTCODE.md                 Agent 行为规则
docs/contracts/            外部后端契约
```

### 19.3 常见按钮含义

不同版本 UI 文案可能略有差异，但含义通常如下：

- `Agent Center`：进入自然语言辅助面板。
- `PDF evidence workflow`：进入 PDF 文献证据流程。
- `Labeling Workbench`：进入 2D/STL 标注。
- `VLM preannotation`：生成 VLM 草稿框。
- `SAM point/box prompt`：用点或框生成 SAM 草稿。
- `Clear AI Labels`：按范围清理未确认 AI 标签。
- `Training Results`：查看历史训练报告。
- `Model Settings`：配置模型方案和外部后端。
- `Export`：导出数据集或相关报告。

## 20. 排错与维护建议

### 20.1 GUI 无法启动

先尝试：

```bat
启动AntCode修复面板.bat
```

然后让 Agent 检查：

- Python 环境是否正确。
- PySide6 是否能导入。
- 最近修改了哪些源码。
- 是否有配置 JSON 损坏。

### 20.2 SAM 很慢或无法用

检查：

- checkpoint 是否存在。
- PyTorch 是否能使用目标设备。
- 当前是否真的需要 SAM。
- 是否在大项目中无意义预热。

### 20.3 VLM 请求失败

检查：

- API / gateway 设置。
- prompt profile。
- 并发设置。
- 返回 JSON 是否符合预期。
- 是否触发服务商限速。

### 20.4 训练结果不可信

检查：

- 是否混入未确认 AI 草稿。
- 样本量是否足够。
- train / val 是否合理。
- 训练范围是不是小批验证。
- 标签命名是否一致。
- 模型备注是否清楚。

### 20.5 导出后无法复现

检查：

- 是否保留 `model_profile_summary.json`。
- 是否记录图片来源。
- 是否记录 profile。
- 是否导出的是确认标签。
- 是否保存了项目 JSON 和对应资源路径。

### 20.6 仓库维护

不要提交：

- 私有项目 JSON。
- PDF 运行输出。
- 提取图像输出。
- 本地数据库。
- API key 或 `.env`。
- 模型权重和训练 run。
- 用户运行时配置。
- Agent session 历史。

提交前建议运行：

```bash
git status --short
git diff --check
python -m unittest tests.test_agent_context_routes
```

如果修改了 PDF、VLM、Blink、导出或项目数据结构，应追加对应专项测试。

---

## 结语

TaxaMask main 稳定线的核心不是“让模型自动替研究者判断”，而是把候选证据、AI 草稿、人工复核、训练素材和导出结果放到一个可追溯的研究流程里。

在真实分类学工作中，可靠性来自清楚的证据链和稳定的复核习惯。TaxaMask 的目标是让这条链更省力、更可追溯，也更容易被模型和 Agent 辅助扩展。
