# TaxaMask：形态部位 Mask 标注、文献证据复核与三维形态工作台

[![DOI](https://zenodo.org/badge/1264598942.svg)](https://doi.org/10.5281/zenodo.20619867)

[English README](README.md)

**TaxaMask** 是一个面向生物体表与体内形态结构掩码标注的开源桌面工作台，旨在把文献证据、人工复核、AI 自动标注、模型训练和结果回流整合为一个可追溯闭环，让模型在真实研究数据中不断迭代，逐步承担更多重复性标注工作。

## 作者先说几句

现在已经是智能体时代了。README 后面那些巨长无比的介绍，各位完全可以扔给智能体去读，让它帮你总结哪些部分和你的类群、数据、工作流有关。人类的话，可以先听我说几句。

首先，我是一位分类学工作者。大学时期做得最多的事情，就是给各种虫子统计数量和粗分类。什么都懂一点点，什么都不精通。当年最大的愿望，就是把这种繁琐的工作自动化。因此，便有了今天这个项目。

TaxaMask 的核心想法，就是用 AI 尽可能减少人类重复工作。这一点首先体现在部位标注上：项目里有 VLM 预标注按钮，可以把部位粗标注交给多模态大模型；SAM 或其他模型再继续生成 mask 草稿。研究者需要做得最多的，是审查 AI 生成的内容，审查、修改、堆叠更多数据集，让它继续学习如何标注。最终，我们希望把越来越多重复性的标注工作交给 AI。

减少重复工作还体现在另一件事上：我彻底摒弃了旧时代专业软件那种让人看到就想吐的超长使用说明。TaxaMask 直接内嵌了一个类似 Codex、OpenCode 这类工具的 Agent Center。你可以根据自己研究的类群改配置，修改想要使用的预测模型，甚至把 TaxaMask 在你的本地仓库改成少女粉色都没问题。如果你发现改着改着 TaxaMask 无法启动了，也无所谓，Ant-Code 还有一个兜底 Dashboard，可以在这里管理历史会话，继续让智能体帮你排查和修复；它不受 TaxaMask 主窗口是否能启动的影响。

至于 micro-CT，也就是页面里的 TIF 入口，这条路线的灵感来自我看到 AntScan 这类很棒的数据集发布。那时候我在想，这种超高精度的 micro-CT 数据，不管是体表结构还是体内结构，都是极好的研究素材。我既然已经做了体表结构的自动标注系统，为什么不试试把体内结构也做了呢？于是便有了 TIF 这条与三维体渲染相关的路径：用来查看体数据、定位部位、绘制更精细的体数据 mask，并导出局部轴重切片。

当然，AI 给出的东西先是草稿，不是结论。TaxaMask 尽量把源数据、人工判断、模型预测和训练导出连接起来，让你能回头检查一个结果是怎么来的，也能继续把确认过的数据喂回模型，让它下一次少麻烦你一点。

## 正式介绍

TaxaMask 起源于真实蚂蚁分类学研究，也面向蚂蚁以外的形态学分类场景。它把分类学文献、标本图像、STL 渲染形态视角图、AI 辅助 mask 草稿、人工复核、模型训练和数据集导出连接在同一个可追溯项目循环中，支持 Segment Anything（SAM）草稿 mask、视觉语言模型（VLM）first-mile 建议、父/子部位层级标注，以及面向计算机视觉和多模态 fine-tuning 的 JSONL、COCO、YOLO 风格数据集导出。

当前 `main` 是 v2.x 的主动维护线。它保留 2D/STL 形态标注和 PDF 文献证据作为公开用户最核心的使用场景，同时把内嵌 Agent Center 和新的 TIF/CT 三维工作台整合在同一条维护主线上。TIF/CT 路线目前主要用 AntScan 蚂蚁 CT 数据进行开发和验证；数据结构没有写死蚂蚁，但还不宣称已经完成广泛跨类群验证。

## 图示概览

![TaxaMask 工作流概览](docs/assets/readme/figure_1_taxamask_workflow.png)

TaxaMask 通过项目记录连接源材料、候选图像、AI 草稿、人工确认标签、导出数据集和模型反馈。研究者可以从文献筛选、图像提取进入标注、复核、训练、预测检查和数据集导出，并持续保留材料来源与处理过程。

![TaxaMask 公开界面概览](docs/assets/readme/figure_2_taxamask_ui_overview.png)

公开界面围绕实际工作流入口组织：Agent Center 用于本地工作流辅助，PDF Evidence 用于文献证据，candidate review 用于筛选导入材料，2D/STL Morphology 用于可复核 mask 标注，TIF Volume 用于内部三维形态工作。

## 核心工作流

TaxaMask 现在包含四条相互连接的研究路线：

```text
PDF 文献证据
  -> 图版 / caption 提取
  -> 候选材料复核
  -> 可追溯文献证据

2D / STL 形态标注
  -> 父部位和子部位标注
  -> AI 草稿与人工复核
  -> 训练数据集导出

TIF / CT 内部结构
  -> specimen 导入
  -> 整只体数据粗切 ROI 定位
  -> 整只体数据手绘 mask 关键切片
  -> 部位体与部位 mask 生成
  -> 3D 预览与局部轴重切片导出

Agent Center
  -> 工作流检查
  -> 报错解释
  -> profile 与后端配置辅助
  -> 研究者确认后的代码修改
```

TaxaMask 的核心设计仍然是人工复核的形态学数据。AI 输出、导入预测和自动建议都先作为草稿材料保存，只有研究者接受后才适合作为训练真值或正式结果。

## 2D / STL 形态工作台

2D/STL 工作流是 TaxaMask 当前最成熟的标注路线。它面向需要把标本照片、分类学图版、显微图像或 STL/mesh 渲染视角图转化为可审计身体部位 mask 和训练数据集的研究者。

TaxaMask 把形态学材料按复核状态组织起来：源材料、候选材料、AI 草稿、人工确认标签、模型预测和导出数据集在项目记录中保持区分。PDF 图版、caption、文献性状描述、标本图像、STL 渲染视角图、VLM 框、SAM mask、外部后端预测和人工 mask 都能进入同一条复核链路，但不会自动混成训练真值。

当前 2D/STL 能力包括：

- 将普通形态图片和 STL 渲染视角图导入 Labeling Workbench。
- 把 STL 视角图作为可复核 2D 形态图像处理，同时保留 specimen 和 view provenance。
- 支持父部位和子部位身体结构标注，适合层级化形态学任务。
- 通过可编辑 profile 管理身体部位词表，便于实验室适配昆虫、蚂蚁、节肢动物、植物或其他基于形态的类群。
- 使用 VLM 生成 first-mile 草稿框，并可结合 SAM 生成草稿 mask。
- 对 AI 草稿、locator 预测、子部位专家和外部模型输出进行人工复核。
- 通过 Blink、heatmap Blink 或外部 Blink 风格后端进行子部位精修。
- 2D 项目使用 SQLite 主存储，适合较大的标注和复核项目，并保留旧 JSON 项目迁移能力。
- 导出 multimodal JSONL、COCO 和 YOLO 风格数据集，用于计算机视觉、VLM 或自定义 fine-tuning 工作流。

TaxaMask 的核心是 mask、身体部位标签和可追溯训练数据。keypoint 或 landmark 类工作流更适合作为 profile 级扩展处理，不是当前默认导出契约。

## PDF 文献证据与 Provenance

TaxaMask 包含文献证据路线，让形态数据集能够持续连接到产生候选材料的论文、图版和文字描述来源。

当前 PDF 与证据能力包括：

- 使用可编辑分类学 profile 进行 PDF 文献筛选。
- 提取 figure 和 caption，并区分 accepted 与 needs-review 输出。
- 将文献性状描述整理为带来源记录的 `taxon -> part -> description` 数据。
- 图像进入形态项目之前先进行候选材料复核。
- 提供 headless 工具，用于 PDF 筛选、候选生成、VLM 复核和导出工作流。

PDF 输出是证据和候选材料。它们不能未经研究者复核就直接变成 2D/STL 训练真值或 TIF 的 `manual_truth`。

## 身体部位词表与类群适配

TaxaMask 使用可编辑 profile，把通用生物结构词、昆虫和节肢动物身体部位词，以及具体类群自己的标签体系连接起来。在昆虫或蚂蚁工作流中，常见搜索词包括 head、thorax 或 mesosoma、abdomen 或 gaster、antennae、mandibles、legs、wings、appendages，以及更细粒度的标本结构。

其他类群可以沿用同样的流程结构，通过调整 profile、先复核小批量数据、验证模型行为，再逐步扩大使用范围。

![TaxaMask 人机协同标注循环](docs/assets/readme/figure_3_human_in_the_loop_cycle.png)

TaxaMask 把 VLM 框、SAM mask、locator 预测、TIF proposal 和外部后端输出都视为草稿材料，直到研究者完成复核。这样既能利用 AI 减少重复劳动，也能让生成结果和 ground-truth 标签保持清晰边界。

![蚂蚁形态学参考工作流](docs/assets/readme/figure_4_ant_morphology_case.png)

TaxaMask 目前在蚂蚁形态学流程中验证最充分。在参考案例中，它用于组织文献筛选、图像提取、VLM first-mile 预标注、人工复核、父部位标注、模型训练、预测检查和数据集导出。

## 谁适合使用 TaxaMask？

TaxaMask 适合需要完成以下工作的研究者或研究小组：

- 为形态学、分类学、生物多样性或 phenomics 项目标注生物身体部位 mask。
- 从标本图像、分类学图版、显微图像或 STL 渲染形态视角图中构建人工复核过的分割数据集。
- 把分类学性状描述、图注、标本图像、AI 草稿、模型预测和最终标签放入同一个可审计项目。
- 使用 SAM、VLM、Locator、Blink 或外部后端输出作为待复核草稿，而不是直接当作 ground truth。
- 导出 multimodal JSONL、COCO 或 YOLO 风格数据集，用于计算机视觉、VLM 或自定义 fine-tuning 工作流。
- 根据新的类群、身体部位词表、本地模型后端或实验室标注路线改造同一套流程。
- 在需要处理 TIFF stack 或 CT 派生体数据时，把工作流扩展到内部形态三维检查、部位体提取和局部轴重切片。

## TIF / CT 三维工作台

TIF/CT 工作流把 TaxaMask 从外部形态图像扩展到内部体数据形态学。它面向 TIFF stack 或 CT 派生体数据：原始扫描方向、标本体态和目标结构方向可能在不同样本之间差异很大，因此不能简单依赖原始 Z 轴或体信号自动定位。

当前 TIF/CT 能力包括：

- 将 TIFF stack 导入为 specimen。
- 查看整只体数据和已经提取出的 part volume。
- 在整只体数据中用关键切片 ROI 矩形做粗切定位。
- 在整只体数据中用手绘轮廓关键切片做精切 part mask。
- 在整只体数据中预览轮廓自动填充，确认 ROI 后同时生成 part image 和 part mask。
- 进入已提取的 part volume 后可继续复核或修订 mask，但不引入 part 下再切 subpart 的第三级结构。
- GPU 三维体预览，支持 streaming texture 构建、缓存复用、裁切、transfer-function presets、主题化背景、截面检查和 mask 边界观察。
- ROI 高细节 3D 检查，用于在不修改源数据的情况下复核局部结构。
- 大体数据可先进行 metadata-only TIF 注册，再显式 materialize 工作体数据。
- TIF 项目使用 SQLite 主索引，体数据、mask 和导出结果保存在 sidecar 文件中。
- Z/Y/X 多方向切片浏览。
- 对选中的 part volume 使用 Local Axis Reslice。
- 将原始 TIFF Z 轴作为锁定的 source direction reference 显示。
- 从 source Z-axis 复制可编辑的 output Z-axis。
- 使用 roll reference point pair 记录方向标准化参照点。
- 导出重切片后的灰度 `image.tif` 和 `metadata.json`。
- 如果该 part 已有 mask，可额外导出 `mask.tif`。
- 记录人工部位提取和局部轴确认过程，为后续模型训练准备数据材料。

Local Axis Reslice 是通用模块，不是脑部专用模块。第一个验证模板是 head / brain oriented，但底层保存的是通用 local frame metadata，而不是 brain-only 字段。

实现说明：TIF/CT 三维预览是 TaxaMask 为 PySide6 / PyOpenGL TIF 工作台编写的独立实现。它使用的是体数据可视化领域常见的 GPU 思路，例如 3D texture、transfer mapping、ray marching、clipping 和 section inspection。交互目标参考了 Drishti 等成熟科学体数据可视化工具的使用体验。

## 局部轴重切片概念

重切片结果挂在 specimen 的某个 part 下，而不是修改原始 TIFF。

```text
specimen
  -> parts
     -> head
        -> mask
        -> contours
        -> reslices
           -> reslice item
              -> image.tif
              -> metadata.json
              -> mask.tif, 如果存在 part mask
```

原始 TIFF stack 始终不被修改。一次 reslice 会记录：

- source volume 和 part volume 身份信息
- source Z-axis reference
- editable output Z-axis
- local frame: origin, x axis, y axis, z axis
- roll reference point pair
- spacing 和 interpolation 设置
- 导出路径和 provenance metadata

灰度图像重切片使用 linear interpolation。mask / label 重切片使用 nearest-neighbor interpolation，避免标签值被插值污染。

## Agent Center

TaxaMask 内嵌第一方 Ant-Code Agent Center，目录为 `vendor/ant-code/`。它用于检查项目状态、解释报错、查看 profile 和后端设置，并在研究者确认后辅助修改代码。

模型凭据、私有网关和用户运行时设置属于本机配置，不包含在仓库中。内嵌运行时默认读取：

```text
AntSleap/config/taxamask_ant_code.config.json
```

没有 API key 时，TaxaMask GUI 仍应能够启动。模型聊天、VLM 草稿和外部模型路线需要用户在本机完成配置。

## 数据边界

TaxaMask 仓库只包含源码和公开工作流文档。私有 CT 数据、本地项目文件、导出结果、模型权重、运行时设置、API key 和内部规划笔记应保留在用户本机，并默认由 `.gitignore` 排除。

## 安装

TaxaMask 以源码方式发布。

当前验证目标：

- Windows 10/11：主要桌面工作流。
- Linux 工作站：CUDA 训练和批处理。
- macOS：可尝试轻量 CPU 复核，但 Apple Silicon 加速不是当前验证目标。

安装前准备：

- Git，或从 GitHub 下载 ZIP。
- Conda 或其他 Python 环境管理工具。
- Python 3.12。
- Node.js 20 或更新版本，用于内嵌 Agent Center dashboard。

克隆当前维护主线：

```bash
git clone https://github.com/wicm84266964/TaxaMask.git
cd TaxaMask
```

如果需要预印本提交时的冻结状态，请使用 `preprint-submission` 分支或 `v1.4.0` release：

```bash
git clone --branch preprint-submission --single-branch https://github.com/wicm84266964/TaxaMask.git
cd TaxaMask
```

创建并激活 Python 环境：

```bash
conda create -n taxamask python=3.12
conda activate taxamask
```

先安装 PyTorch。CPU 测试：

```bash
pip install -r requirements-torch-cpu.txt
```

NVIDIA CUDA 12.1：

```bash
pip install -r requirements-torch-cu121.txt
```

再安装基础依赖：

```bash
pip install -r requirements.txt
```

安装 Agent Center 依赖：

```bash
cd vendor/ant-code
npm ci
cd ../..
```

可选的 SAM 辅助 2D 标注需要将 SAM checkpoint 放到：

```text
AntSleap/weights/sam_b.pt
```

模型权重不随仓库发布。

## 启动

在已激活环境中运行：

```bash
python AntSleap/main.py
```

Windows 用户也可以运行：

```bat
启动TaxaMask.bat
```

Linux 或 WSL 用户可以运行：

```bash
bash ./启动TaxaMask.sh
```

如果源码改动导致 GUI 无法启动，可以直接启动 Agent Center 修复面板：

```bash
node vendor/ant-code/src/cli/dashboard.js --project . --port 7410
```

Windows 下也可以运行 `启动AntCode修复面板.bat`。

### TIF / CT 显卡注意事项

TIF/CT 体预览最好让 Python 解释器使用 NVIDIA 独显。在同时有核显和 NVIDIA 显卡的 Windows 机器上，请在 Windows 图形设置或 NVIDIA 控制面板中，把当前环境的 `python.exe` 设为高性能显卡。`启动TaxaMask.bat` 现在会优先寻找 `taxamask` Conda 环境，再兜底旧的 `antsleap` 环境；如果你曾经设置过 `TAXAMASK_PYTHON_EXE`，环境改名后也要同步改到新的 `python.exe`。打开 TIF 项目后，可以看体预览状态栏显示的 OpenGL renderer，用它确认当前是否真的在使用 NVIDIA 显卡，而不是核显或 CPU 回退。

## 目录结构

```text
AntSleap/                  Python package 和 Qt 工作台
AntSleap/core/             Project、TIF、部位提取、导出和后端逻辑
AntSleap/ui/               桌面 UI、2D 标注、PDF、TIF 和 Agent 面板
core/pdf_processor/         PDF 筛选和提取逻辑
tools/agentic/              Headless PDF、candidate、VLM 和导出工具
tif_blink/                  TIF-local 模型路线实验和辅助代码
tif_blink_nnunet/           面向 nnU-Net 的 TIF 辅助路线
screener_configs/           PDF 筛选模板和示例
multimodal_configs/         图文提取和复核 profiles
part_description_configs/   文献性状描述提取 profiles
json_projects/templates/    干净项目模板
docs/contracts/             公开后端契约和 TIF local-axis 契约
vendor/ant-code/            第一方 Agent Center runtime
tests/                      单元测试和工作流测试
TaxaMask使用手册.md           中文使用手册
```

内部包名 `AntSleap` 会继续保留，用于运行稳定性，也作为对最初启发本项目的 SLEAP 项目的致意。公开项目名是 TaxaMask。

## 典型流程

PDF 文献证据路线：

1. 配置或改造 PDF screening profile。
2. 提取图版、caption 和文献性状描述。
3. 复核 accepted 与 needs-review 输出。
4. 将有用候选材料导入 TaxaMask 项目。

2D / STL 形态标注路线：

1. 导入标本图像或 STL 渲染视角图。
2. 标注父部位和子部位形态结构。
3. 将 VLM、SAM 和模型预测都视为草稿。
4. 人工确认标签。
5. 导出训练数据集。

TIF / CT 路线：

1. 打开 AntScan 或其他 TIFF stack。
2. 使用 ROI 和关键切片 mask 创建 specimen part。
3. 提取 part volume。
4. 在 3D 和多方向切片中复核该部位。
5. 将 source Z-axis 复制成 editable local output axis。
6. 设置 roll reference points 作为方向标准化参照。
7. 导出重切片后的 part TIFF 和 metadata。

## 外部后端契约

- [父部位外部后端契约](docs/contracts/external_backend_contract_v1.md)
- [子部位 Blink 外部后端契约](docs/contracts/external_blink_backend_contract_v1.md)
- [TIF local-axis 后端契约](docs/contracts/tif_local_axis_backend_contract_v1.md)

外部后端预测都是待复核候选结果。研究者确认前，不应把它们当作训练真值。

## 文档

- [中文使用手册](TaxaMask使用手册.md)
- [平台安装说明](docs/platform_setup.md)
- [PDF 筛选 profile 适配说明](docs/PDF筛选profile适配说明.md)
- [图文提取与多模态 profile 适配说明](docs/图文提取与多模态profile适配说明.md)
- [外部后端契约](docs/contracts/)

## 关键词

生物形态标注、分类学图像标注、分类学文献证据、PDF 图版提取、caption 提取、AI 辅助标注、人工复核、训练数据集构建、COCO 导出、YOLO 导出、VLM 预标注、SAM 辅助标注、STL 形态复核、CT 形态学、TIFF stack、TIF 工作台、AntScan、三维体预览、GPU 体渲染、部位体提取、关键切片 mask 插值、局部轴重切片、形态分割、内部形态学、蚂蚁分类学、蚁科、生物多样性信息学、Agent Center

## 引用

如果 TaxaMask 帮助了你的研究，请引用软件发布版本：

```text
TaxaMask: a taxonomy-oriented morphology annotation, evidence review, and dataset workbench.
Zenodo DOI (all versions): https://doi.org/10.5281/zenodo.20619867
```

## 许可证

TaxaMask 源码采用 GNU Affero General Public License v3.0。该协议允许商用，但修改版和网络服务需要遵守 AGPLv3 的源码公开义务。详见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。

`vendor/ant-code/` 下内置的 Ant-Code Agent Center 是 TaxaMask 的第一方源码组成部分。该目录名是为了运行时布局兼容而保留，不应被理解为第三方依赖，也不应从 TaxaMask 项目的署名范围中排除。
