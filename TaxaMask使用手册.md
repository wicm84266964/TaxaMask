# TaxaMask 完整中文使用手册（main 稳定版）

> 适用版本：TaxaMask main / v1.1 系列公开稳定线。
>
> 适用对象：希望用 TaxaMask 进行分类学文献证据整理、2D 形态图像标注、STL 渲染视角图复核、VLM / SAM / Blink 草稿复核、模型训练与数据集导出的研究者。
>
> 本手册只描述 main 稳定线中已经公开维护的 PDF、2D/STL、Agent、VLM/SAM、Blink 和数据集导出流程。

---

## 目录

1. [TaxaMask 是什么](#1-taxamask-是什么)
2. [稳定版工作流总览](#2-稳定版工作流总览)
3. [安装与启动](#3-安装与启动)
4. [Agent Center](#4-agent-center)
5. [PDF 文献证据路线](#5-pdf-文献证据路线)
6. [项目管理](#6-项目管理)
7. [2D / STL 标注工作台](#7-2d--stl-标注工作台)
8. [VLM 与 SAM 草稿](#8-vlm-与-sam-草稿)
9. [子部位专家会话与 Blink 路线](#9-子部位专家会话与-blink-路线)
10. [外部模型后端](#10-外部模型后端)
11. [数据集导出](#11-数据集导出)
12. [Profile 适配](#12-profile-适配)
13. [数据边界与安全规则](#13-数据边界与安全规则)
14. [标准操作路线](#14-标准操作路线)
15. [常见误区](#15-常见误区)
16. [按钮和文件速查](#16-按钮和文件速查)

## 1. TaxaMask 是什么

TaxaMask 是一个面向分类学和形态学研究的桌面工作台。它把文献证据、标本图像、AI 草稿、人工复核标签、训练数据导出和模型反馈组织到同一个可追溯流程里。

main 稳定线的核心路线是：

- PDF 文献证据：筛选论文、提取图版、caption 和文献性状描述。
- 2D 形态标注：在图片上标注父部位和子部位 mask / polygon。
- STL 渲染视角复核：把 STL 或 mesh 渲染成 2D 视角图后进入普通标注工作台。
- VLM / SAM 草稿：用多模态模型和 SAM 生成待复核草稿。
- 子部位专家会话：围绕父部位上下文积累局部结构训练素材，并连接 Blink、heatmap Blink 或外部 Blink 后端。
- 数据集导出：导出 multimodal JSONL、COCO、YOLO 风格数据和模型 profile 摘要。
- Agent Center：用自然语言辅助检查项目、解释报错、调整 profile、配置后端和修改源码。

TaxaMask 起源于真实蚂蚁分类学工作，因此蚂蚁领域的术语、模板和验证路线最成熟。其他类群可以通过 profile、结构标签和项目模板逐步适配，但每个新类群都应先小批量复核，再扩大处理规模。

## 2. 稳定版工作流总览

推荐把 TaxaMask 理解成一条人机协同的证据和训练数据生产线：

```text
PDF / 图像 / STL 渲染视角
  -> 候选材料
  -> AI 草稿
  -> 人工复核
  -> 训练数据集
  -> 模型预测
  -> 再复核
```

最重要的边界是：AI 输出不是训练真值。VLM、SAM、Locator、Blink、外部后端和 PDF 提取结果都只是候选材料，必须由研究者确认后才适合作为 ground truth 或正式数据集。

## 3. 安装与启动

安装前需要准备：

- Git，或从 GitHub 下载 ZIP。
- Conda 或其他 Python 环境管理工具。
- Python 3.12。
- Node.js 20 或更高版本，用于内嵌 Agent Center 和修复面板。

获取 main 稳定线：

```bash
git clone https://github.com/wicm84266964/TaxaMask.git
cd TaxaMask
```

创建环境：

```bash
conda create -n taxamask python=3.12
conda activate taxamask
```

安装 PyTorch。CPU 测试可用：

```bash
pip install -r requirements-torch-cpu.txt
```

NVIDIA CUDA 12.1 可用：

```bash
pip install -r requirements-torch-cu121.txt
```

安装基础依赖：

```bash
pip install -r requirements.txt
```

安装 Agent Center 依赖：

```bash
cd vendor/ant-code
npm ci
cd ../..
```

可选 SAM 辅助标注需要将 checkpoint 放到：

```text
AntSleap/weights/sam_b.pt
```

启动 TaxaMask：

```bash
python AntSleap/main.py
```

Windows 用户也可以运行：

```text
启动TaxaMask.bat
```

如果 GUI 因源码改动无法启动，可以运行：

```text
启动AntCode修复面板.bat
```

或直接运行：

```bash
node vendor/ant-code/src/cli/dashboard.js --project . --port 7410
```

修复面板不导入 PySide6 GUI，适合在界面损坏时继续让 Agent 检查和修复问题。

## 4. Agent Center

Agent Center 是 TaxaMask 内嵌的 Ant-Code 工作区。它可以读取项目上下文、公开文档、后端契约和源码位置，帮助研究者完成：

- 检查当前项目状态。
- 解释 PDF、VLM、训练、导出或启动报错。
- 查找相关 profile、配置项和后端契约。
- 修改 profile、启动脚本、适配器或源码。
- 生成安全的排错计划和验证命令。

Agent 的写入应遵守三层边界：

- Profile / 配置改动：风险较低，但仍需说明会影响哪个工作流。
- 外部后端适配：修改脚本和契约对接，适合接入实验室自己的模型。
- TaxaMask 主源码修改：风险较高，必须清楚说明影响范围并得到研究者确认。

Agent 上下文不会默认发送完整项目 JSON、数据库、API key、模型权重或大文件。它应发送短摘要和路径，需要深入时再读取具体文件。

## 5. PDF 文献证据路线

PDF 路线用于把分类学论文变成可复核证据：

- 论文筛选：判断论文是否可能包含目标类群或目标材料。
- 图版提取：提取 figure、caption 和附近文本。
- 文献性状描述：整理为 `taxon -> part -> description` 记录。
- 候选复核：把 accepted、needs_review 等状态明确分开。
- provenance：保留 PDF、页码、caption、附近文本、profile 和运行信息。

常用命令：

```bash
python tools/agentic/screen_pdfs.py --pdf-source-dir pdf_folder --out out_folder --config screener_configs/蚂蚁新种筛选_V2示例.json
```

```bash
python tools/agentic/extract_figures.py --pdf-source-dir pdf_folder --db out_folder/literature.db --figure-profile multimodal_configs/蚂蚁分类学图版宽松复核_示例.json --part-description-profile part_description_configs/蚂蚁分类学部位描述抽取_示例.json
```

PDF 输出是证据和候选材料，不应自动写入训练真值。

## 6. 项目管理

TaxaMask 项目记录源材料、图像列表、结构标签、人工标签、AI 草稿、模型设置、导出记录和 provenance。

常见项目动作：

- 新建项目：选择模板，设置 taxonomy / structure 标签。
- 打开项目：读取 JSON 项目文件。
- 保存项目：保存当前标注、配置和 provenance。
- 图片搬盘后修复路径：使用路径重定位功能或手动修正项目中的路径。
- 删除图片或结构：应清理相关 labels、auto boxes、VLM targets、parent ratios、Blink context 和 cascade routes。

术语不要混淆：

- taxon：生物分类单元，例如某个物种或属。
- taxonomy / structures：项目要标注的结构标签，例如 head、mandible、gaster。
- label：某张图片上某个结构的具体 polygon / mask / box。

## 7. 2D / STL 标注工作台

2D / STL 是 main 稳定线的核心标注路线。

可处理材料：

- 普通形态学图像。
- PDF 提取后人工复核过的候选图。
- STL 或 mesh 渲染出来的 2D 视角图。

STL 在 main 中表示“渲染视角图进入 2D 标注流程”，不是直接在三维 mesh 上涂标签。

主要标注方式：

- Manual Draw：手工画 polygon。
- Magic Wand / SAM：用点提示生成草稿 mask。
- Box Prompt / SAM：用框提示生成草稿 mask。
- Annotation Box：绘制候选框或父部位框。
- Loose Shrink Box：为子部位专家积累松框和收缩轨迹。

Labeling Workbench 中常见结构：

- 左侧图片列表和分组。
- 中央画布。
- 右侧 structures / labels / 文献描述 / 子部位控制区。
- 顶部模型、草稿、清理和导出相关按钮。

大项目打开时应保持轻量：图片组默认折叠，不自动加载第一张大图，也不预热 Locator / SAM，等用户选择图片或请求标注时再加载。

## 8. VLM 与 SAM 草稿

VLM first-mile preannotation 用多模态模型先提出粗定位框。SAM 可以根据框或点提示生成草稿 mask。

当前语义：

- VLM 框是低优先级草稿。
- 模型预测框是中优先级草稿。
- 手工标签和已确认草稿最高优先级。
- 重新运行 VLM 不应覆盖手工标签、已确认标签或模型预测框。
- 重新运行模型预测可以替换未确认 AI 草稿，但不得覆盖手工和已确认标签。

Box-only VLM 草稿可以帮助研究者找到候选部位，但不能直接作为训练样本。只有生成 polygon / mask 并由研究者确认后，才适合进入训练数据。

## 9. 子部位专家会话与 Blink 路线

main 中用户面对的概念应写作 **Child Expert Session / 子部位专家会话**。历史源码里仍有 Blink、BlinkLabWidget、launch_blink_from_workbench 等名称，这些是兼容性和内部命名，不应让普通用户误以为每天需要进入一个独立 Blink 工作台。

子部位专家路线解决的问题是：在已有父部位上下文中定位更小的局部结构，例如在 head 中定位 mandible 或 eye。

支持后端：

- ViT-B Blink。
- Heatmap Blink。
- External Blink backend。

推荐流程：

1. 先标注父部位。
2. 在父部位上下文中画子部位或松框。
3. 使用 auto-shrink / trajectory 积累局部训练素材。
4. 训练当前子部位专家或连接外部后端。
5. 将预测作为候选草稿导回工作台。
6. 人工复核后再确认。

子部位专家不应直接改写训练真值。它的输出仍然是候选。

## 10. 外部模型后端

TaxaMask main 通过 JSON 契约连接外部模型。

父部位后端契约：

```text
docs/contracts/external_backend_contract_v1.md
```

子部位 Blink 后端契约：

```text
docs/contracts/external_blink_backend_contract_v1.md
```

TaxaMask 负责生成 contract JSON，外部后端负责训练或预测，然后返回 result JSON。TaxaMask 再把预测结果放回项目，供研究者复核。

外部后端配置不应提交真实本机路径、私有 API key、私有网关地址或实验室内部命令。

## 11. 数据集导出

main 稳定线主要导出：

- Multimodal JSONL。
- COCO annotations。
- YOLO labels。
- 图片文件副本或相对路径。
- `model_profile_summary.json`。

`model_profile_summary.json` 用于记录导出时使用的模型方案、父部位 / 子部位路线、后端配置摘要和 provenance。它让后续训练结果能追溯到当时的数据和模型设置。

导出前应检查：

- 标签是否已经人工确认。
- AI 草稿是否仍是未确认状态。
- 图片路径是否有效。
- structure 名称是否和项目模板一致。
- profile 是否是当前实验想要的版本。

## 12. Profile 适配

适配新类群时，建议复制模板再修改，不要直接覆盖示例文件。

常见 profile 位置：

- PDF 筛选：`screener_configs/`
- 图版提取与多模态复核：`multimodal_configs/`
- PDF 文献性状描述抽取：`part_description_configs/`
- 项目模板：`json_projects/templates/`

新类群适配建议：

1. 先确定结构标签和同义词。
2. 用少量 PDF 和图片跑完整流程。
3. 检查 VLM 框、SAM mask 和导出 JSON。
4. 修正 profile 文本和后端设置。
5. 扩大到正式批量。

不要把 API key 写进 profile。

## 13. 数据边界与安全规则

公开仓库不应包含：

- 私有项目 JSON。
- API key、`.env`、私有网关地址。
- SQLite 数据库。
- PDF 运行输出、图像输出、训练输出。
- 模型权重、checkpoint、实验 run。
- Agent sessions、tasks、本机运行缓存。
- 个人机器路径。

这些内容应留在本机，由 `.gitignore` 保护。提交前应运行 `git status --short` 检查 staged 文件。

## 14. 标准操作路线

PDF 到标注：

1. 准备 PDF 目录。
2. 选择 PDF screening profile。
3. 执行筛选。
4. 提取 figure、caption 和文献描述。
5. 人工复核候选图。
6. 导入有用候选图到项目。
7. 进入 Labeling Workbench。
8. 标注或复核 AI 草稿。
9. 导出训练数据集。

普通图片标注：

1. 新建 TaxaMask 项目。
2. 添加图片。
3. 配置 structures。
4. 手工标注父部位。
5. 使用 SAM 或 VLM 生成草稿。
6. 人工确认。
7. 训练或连接模型。
8. 复核预测。
9. 导出数据。

子部位专家：

1. 确认父部位标签。
2. 选择子部位。
3. 标注或画松框。
4. 积累轨迹。
5. 训练子部位专家或连接外部后端。
6. 把预测作为候选导回。
7. 人工复核。

## 15. 常见误区

误区 1：AI 草稿就是训练真值。

正确理解：AI 草稿只是候选。必须由研究者确认后才适合作为训练真值。

误区 2：PDF 图版提取后可以自动训练。

正确理解：PDF 图版是证据来源和候选材料。图像质量、caption 关系和结构位置都需要复核。

误区 3：STL 路线是在三维模型上直接标注。

正确理解：main 中 STL 是渲染视角图路线，进入的是 2D 标注工作台。

误区 4：子部位专家会话可以替代人工判断。

正确理解：它只减少重复定位劳动，预测仍需要复核。

误区 5：外部后端返回的结果可以直接覆盖项目。

正确理解：外部后端只能生成候选结果。TaxaMask 应保留人工复核边界。

## 16. 按钮和文件速查

常见入口：

- `启动TaxaMask.bat`：启动 GUI。
- `启动AntCode修复面板.bat`：GUI 损坏时打开浏览器修复面板。
- `vendor/ant-code/src/cli/dashboard.js`：Agent Center dashboard 入口。
- `AntSleap/main.py`：主 GUI 入口。
- `AntSleap/ui/pdf_processing_widget.py`：PDF 工具界面。
- `AntSleap/core/project.py`：2D 项目数据结构和导出逻辑。
- `AntSleap/core/vlm_preannotation.py`：VLM 草稿生成逻辑。
- `AntSleap/core/external_backend.py`：父部位外部后端。
- `AntSleap/core/external_blink_backend.py`：子部位外部后端。
- `docs/contracts/external_backend_contract_v1.md`：父部位后端契约。
- `docs/contracts/external_blink_backend_contract_v1.md`：子部位后端契约。
- `LLM_CONTEXT_DETAILED.md`：给 Agent / 大模型看的 main 稳定线上下文。
- `TaxaMask使用手册.md`：给研究者看的中文使用手册。

最值得记住的三句话：

1. TaxaMask 的核心是可追溯人工复核，不是自动把 AI 输出变成真值。
2. PDF、VLM、SAM、Blink 和外部模型都提供候选材料，最终判断在研究者。
3. main 稳定线专注 PDF、2D/STL、Agent 和模型草稿复核；开发预览路线单独维护自己的文档。
