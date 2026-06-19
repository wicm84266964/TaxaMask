# TaxaMask：生物形态身体部位分割、Mask 标注与分类学数据集构建

[![DOI](https://zenodo.org/badge/1264598942.svg)](https://doi.org/10.5281/zenodo.20619867)

**TaxaMask** 是一个面向生物形态身体部位 mask 标注、分类学性状整理与多模态训练数据集构建的开源桌面工作台。

TaxaMask 起源于真实蚂蚁分类学研究，也面向蚂蚁以外的形态学分类场景。它把分类学文献、标本图像、AI 辅助 mask 标注、人工复核、模型训练和数据集导出连接在同一个可追溯项目循环中，支持 Segment Anything（SAM）草稿 mask、视觉语言模型（VLM）first-mile 建议、父/子部位层级标注，以及面向计算机视觉和多模态 fine-tuning 的 COCO / JSONL / YOLO 数据集导出。

TaxaMask 还内嵌 **Agent Center**。研究者可以用自然语言检查项目状态、理解报错信息、调整 profile、配置模型后端，并在确认后修改项目代码。这个设计让每个实验室都能围绕自己的类群、图像来源、标注目标和本地模型条件改造 TaxaMask。

## 图示概览

![TaxaMask 工作流概览](docs/assets/readme/figure_1_taxamask_workflow.png)

TaxaMask 通过项目记录连接源材料、候选图像、AI 草稿、人工确认标签、导出数据集和模型反馈。研究者可以从文献筛选、图像提取进入标注、复核、训练、预测检查和数据集导出，并持续保留材料来源与处理过程。

## 两条主线

### 1. 可追溯形态标注与训练数据构建

TaxaMask 把分类学材料按状态组织起来：源材料、候选材料、AI 草稿、人工确认标签和导出数据集在项目中分层记录。PDF 图版、caption、文献性状描述、标本图像、STL 渲染视角图、VLM 框、SAM mask、模型预测和人工 mask 都能进入同一条复核链路，但不会自动混成训练真值。

这条主线面向的是形态学训练数据从哪里来、经过哪些处理、哪些结果由人工确认。TaxaMask 支持：

- 使用可编辑分类学 profile 进行 PDF 文献筛选、图版提取和 caption 提取。
- 将文献性状描述整理为带来源记录的 `taxon -> part -> description` 数据。
- 在 2D 标注工作台中处理父部位和子部位标注。
- 将 STL 渲染视角图作为可复核 2D 形态图像处理。
- 使用 VLM 生成 first-mile 草稿框，并可结合 SAM 生成草稿 mask。
- 对 AI 草稿和外部模型预测进行人工复核。
- 支持 Blink、heatmap Blink 或外部 Blink 后端等路线特定的子部位专家。
- 通过公开 JSON 契约连接父部位和子部位模型后端。
- 导出 multimodal JSONL、COCO 和 YOLO 风格数据集。

### 2. 智能体辅助的项目改造

TaxaMask 内嵌 Agent Center。它可以读取项目记录、profile、运行日志、后端契约和相关源码上下文，把自然语言请求转化为可确认的改动方案。研究者可以用它检查项目状态、理解报错信息、调整 profile、配置模型后端，也可以在确认后修改适配器、启动脚本或相关源码。

这条主线面向的是不同实验室如何把 TaxaMask 改造成适合自己项目的工具。研究者可以围绕具体问题让 Agent Center 帮助改造项目，例如：

- 当前项目处于什么状态？
- 正在使用哪个 profile 或模型后端？
- PDF 筛选、VLM 草稿或训练步骤为什么失败？
- 新类群、身体部位词表或本地模型路线应该如何配置？
- 这个项目需要修改哪个 profile、适配器、启动脚本或源码文件？
- 能否为当前实验室的标注路线增加或调整一个工作流入口？

科学判断和最终代码改动仍由研究者确认。TaxaMask 不包含模型权重、私有数据集、本地项目、API key、运行输出或用户运行时配置。

![TaxaMask 公开界面概览](docs/assets/readme/figure_2_taxamask_ui_overview.png)

公开界面围绕四个实际入口组织：Agent Center 用于本地工作流辅助，PDF extraction setup 用于准备文献证据，candidate review 用于筛选导入材料，Labeling Workbench 用于可复核形态标注。

恢复提示：源码改动可能导致 GUI 在启动阶段报错，使内嵌 Agent Center 无法打开。遇到这种情况时，可以使用独立的 Ant-Code 修复面板：Windows 运行 `启动AntCode修复面板.bat`，Ubuntu/Linux/WSL 运行 `bash ./启动AntCode修复面板.sh`，然后在浏览器 Dashboard 中继续让 Ant-Code 检查、修改和修复问题。浏览器 Dashboard 也可以读取当前项目中的 Ant-Code 历史聊天记录。

## 适用范围

TaxaMask 面向需要连接生物结构、分类学文献、标本图像、AI 草稿、人工复核和训练数据导出的形态学分类项目。当前公开版本在蚂蚁形态学流程中验证最充分，profile 系统则用于适配其他类群和身体部位词表。

## 身体部位术语

TaxaMask 使用可编辑 profile，把通用生物结构词、昆虫和节肢动物身体部位词，以及具体类群自己的标签体系连接起来。在昆虫或蚂蚁工作流中，常见搜索词包括 insect body parts、arthropod、head、thorax 或 mesosoma、abdomen 或 gaster、antennae、mandibles、legs、wings、appendages，以及更细粒度的标本结构。研究者可以把这些标签组织成父部位和子部位，用于 mask segmentation、instance segmentation、分类学性状标注、人工复核 SAM / VLM 草稿，以及 COCO / JSONL / YOLO 数据集导出。

TaxaMask 的核心是 mask、身体部位标签和可追溯训练数据。keypoint 或 landmark 类工作流更适合作为 profile 级扩展处理，不是当前默认导出契约。

## 人工复核循环

![TaxaMask 人机协同标注循环](docs/assets/readme/figure_3_human_in_the_loop_cycle.png)

TaxaMask 把 VLM 框、SAM mask、定位器预测和外部后端输出都视为草稿材料，直到研究者完成复核。这样既能利用 AI 减少重复劳动，也能让生成结果和 ground-truth 标签保持清晰边界。

## 验证参考路线

![蚂蚁形态学参考工作流](docs/assets/readme/figure_4_ant_morphology_case.png)

当前公开版本在蚂蚁形态学流程中验证最充分。在参考案例中，TaxaMask 用于组织文献筛选、图像提取、VLM first-mile 预标注、人工复核、父部位标注、模型训练、预测检查和数据集导出。

其他类群可以沿用同样的流程结构，通过调整 profile、先复核小批量数据、验证模型行为，再逐步扩大使用范围。

## 关键词

生物身体部位分割、organism body part segmentation、insect body parts、arthropod morphology、head、thorax、abdomen、antennae、mandibles、legs、wings、appendages、specimen image segmentation、automatic mask annotation drafts、mask annotation、实例分割、分类学图像标注、形态学 mask 标注、Segment Anything、SAM 辅助标注、视觉语言模型、VLM 预标注、deep learning、computer vision、fine-grained classification datasets、多模态数据集、COCO 数据集、JSONL 数据集、YOLO 格式、fine-tuning、可追溯工作流、数据集来源记录、AI 辅助标注、人工复核、形态学分割、分类学文献、新种描述、分类检索表、图版提取、caption 提取、训练数据集构建、智能体辅助工作流、源码辅助改造、可定制标注流程、生物多样性信息学、phenomics、生物影像、标本数字化、昆虫形态学、蚂蚁形态学、蚂蚁分类学、蚁科。

## 许可证

TaxaMask 源码采用 GNU Affero General Public License v3.0。该协议允许商用，但修改版和网络服务需要遵守 AGPLv3 的源码公开义务，并保留来源和版权信息。详见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。

`vendor/ant-code/` 下内置的 Ant-Code Agent Center 是 TaxaMask 的一等原创源码组成部分。该目录名是为了运行时布局兼容而保留，不应被理解为第三方依赖，也不应从 TaxaMask 项目的署名范围中排除。

如果 TaxaMask 帮助了你的研究，请引用仓库或发布版本。引用信息见 [CITATION.cff](CITATION.cff)。

## 平台支持

TaxaMask 当前以源码方式发布，目标是让研究者能从源码运行工作台、验证小项目，并在 Linux CUDA 工作站上处理较重的训练任务。

- Windows 10/11 是目前验证最充分的桌面环境。
- Linux 是实验室工作站、CUDA 训练和批处理的主要目标平台。
- macOS 可以尝试轻量 CPU 复核和小规模标注，但 Apple Silicon 加速不是 v1.0 的验证目标。

安装基础依赖前，请先安装与你机器匹配的 PyTorch 版本。

## 安装

安装前准备：

- Git，用于克隆源码；如果没有 Git，也可以从 GitHub 下载 ZIP。
- Conda 或其他 Python 环境管理工具。
- 推荐使用 Python 3.12，这是当前公开源码版主要验证的 Python 版本。
- Node.js 20 或更高版本，并带有 npm，用于内嵌 Agent Center / Ant-Code dashboard。

先获取源码：

```bash
git clone https://github.com/wicm84266964/TaxaMask.git
cd TaxaMask
```

如果没有安装 Git，也可以在 GitHub 页面下载 ZIP，解压后在 `TaxaMask` 文件夹中打开终端。

然后创建 Python 环境。推荐 Conda 环境名为 `taxamask`：

```bash
conda create -n taxamask python=3.12
conda activate taxamask
```

先安装适合你机器的 PyTorch。CPU 测试：

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

安装内嵌 Agent Center 的 Node 依赖：

```bash
cd vendor/ant-code
npm ci
cd ../..
```

这一步用于启动内嵌 Ant-Code dashboard 和修复面板。公开仓库不包含 `node_modules`，所以克隆后需要在本机安装一次。

如果要使用 SAM 辅助标注，需要把 SAM checkpoint 放到：

```text
AntSleap/weights/sam_b.pt
```

模型权重不随仓库发布。

PDF 处理可以直接使用 PyMuPDF，但部分备用图像提取路径会通过 `pdf2image` 依赖 Poppler。不同系统的 Poppler 安装方式见 [平台安装说明](docs/platform_setup.md)。

TaxaMask 可以在没有 API key 的情况下启动。Agent Center dashboard 可以先打开；但模型聊天、VLM 草稿和外部模型路线需要用户在本机配置模型网关或 API 设置。不要把真实 key、私有网关地址或运行时配置提交到仓库。

## 更新源码

如果你已经克隆过仓库，可以用下面的命令获取最新源码修复：

```bash
git pull --ff-only origin main
```

更新后，只有在依赖文件发生变化时，才需要重新运行 `pip install -r requirements.txt`，或进入 `vendor/ant-code` 后重新运行 `npm ci`。

## 启动

已激活环境时：

```bash
python AntSleap/main.py
```

Windows 用户可以双击 `启动TaxaMask.bat`。脚本会寻找本地 `.venv`、当前 Conda 环境、常见 `taxamask` Conda 环境和系统 Python。也可以显式指定：

```bat
set TAXAMASK_PYTHON_EXE=C:\path\to\python.exe
```

Ubuntu/Linux 或 WSL 终端用户可以使用同名 shell 脚本：

```bash
bash ./启动TaxaMask.sh
```

如果本地源码修改导致 GUI 无法启动，可以直接启动随仓库附带的 Ant-Code dashboard，不需要导入 PySide6 GUI：

```bash
node vendor/ant-code/src/cli/dashboard.js --project . --port 7410
```

Windows 用户也可以运行 `启动AntCode修复面板.bat`，它会额外自动寻找 Node.js。Ubuntu/Linux 或 WSL 终端用户可以运行：

```bash
bash ./启动AntCode修复面板.sh
```

浏览器 Dashboard 可以在 TaxaMask GUI 无法导入时继续进行代码检查、修改和排错，也可以读取当前项目中的 Ant-Code 历史聊天记录。这些方式都需要 Node.js 20 或更高版本，并且需要先在 `vendor/ant-code` 中执行过 `npm ci`。

Ubuntu/WSL 下 TaxaMask 会默认用外部浏览器打开 Ant-Code Dashboard，而不是内嵌 Qt WebEngine；这是为了避开部分 Linux/WSLg EGL/OpenGL 驱动导致的段错误。如果你确认本机 Qt WebEngine 稳定，可以设置 `TAXAMASK_ANTCODE_BROWSER_MODE=0` 恢复内嵌模式。在浏览器模式中，TaxaMask 的“询问 Agent”按钮会打开浏览器并把当前工作台上下文复制到剪贴板，请粘贴到浏览器里的 Ant-Code 输入框后再发送。

如果 TaxaMask GUI 是由 Windows Python 启动，但 Ant-Code / Node 依赖安装在 WSL Ubuntu 里，请先让 GUI 使用 WSL 启动内嵌 Agent：

```bash
# 在 Ubuntu / WSL 里执行一次
cd /mnt/c/path/to/TaxaMask/vendor/ant-code
npm ci
```

```bat
set TAXAMASK_ANTCODE_RUNTIME=wsl
set TAXAMASK_WSL_DISTRO=Ubuntu
启动TaxaMask.bat
```

如果你的发行版名称不是 `Ubuntu`，把 `TAXAMASK_WSL_DISTRO` 改成 `wsl -l -v` 显示的名称。特殊路径无法自动转换时，可以额外设置 `TAXAMASK_WSL_PROJECT_DIR=/home/.../TaxaMask`。

## 常见研究流程

1. 从 TaxaMask Agent Center 开始。
2. 用 PDF Evidence 筛选文献，提取图版、caption 和文献性状描述。
3. 把人工复核后的候选图或普通形态图导入 2D 项目。
4. 在 Labeling Workbench 中标注父部位和子部位。
5. 把 VLM 或 SAM 输出当作草稿，不直接当作训练真值。
6. 训练或连接父部位 / 子部位后端。
7. 人工复核预测结果。
8. 导出 multimodal JSONL、COCO 或 YOLO 风格数据集。

## Profile 适配

适配新类群时，建议复制模板再修改，不要直接覆盖示例文件：

- PDF 筛选：`screener_configs/`
- 图版提取与多模态复核：`multimodal_configs/`
- PDF 文献性状描述抽取：`part_description_configs/`
- 项目结构模板：`json_projects/templates/`

先用小批量 PDF 和图片跑通，再扩大规模。不同类群的 profile 行为需要分别验证。

## 外部模型契约

- [父部位外部后端契约](docs/contracts/external_backend_contract_v1.md)
- [子部位 Blink 外部后端契约](docs/contracts/external_blink_backend_contract_v1.md)

外部后端的预测结果都是候选材料，必须经过研究者复核后，才适合进入训练真值或正式数据集。

## 目录结构

```text
AntSleap/                  Python 包和 Qt 工作台
core/pdf_processor/         PDF 筛选与图文提取逻辑
tools/agentic/              Headless 工作流工具
tools/governance/           数据治理和审计辅助工具
screener_configs/           PDF 筛选模板和示例
multimodal_configs/         图版提取与多模态复核 profile
part_description_configs/   PDF 文献性状描述抽取 profile
json_projects/templates/    干净项目模板
docs/contracts/             外部模型后端契约
vendor/ant-code/            一等源码组成部分：Ant-Code Agent Center 运行时
tests/                      单元测试和工作流测试
TaxaMask使用手册.md           中文公开使用手册
```

内部包名 `AntSleap` 会继续保留，用于运行稳定性和历史兼容；公开项目名是 TaxaMask。

## 文档

- [中文使用手册](TaxaMask使用手册.md)
- [平台安装说明](docs/platform_setup.md)
- [PDF 筛选 profile 适配说明](docs/PDF筛选profile适配说明.md)
- [图文提取与多模态 profile 适配说明](docs/图文提取与多模态profile适配说明.md)
- [父部位外部后端契约](docs/contracts/external_backend_contract_v1.md)
- [子部位 Blink 外部后端契约](docs/contracts/external_blink_backend_contract_v1.md)

## 谁适合使用 TaxaMask？

TaxaMask 适合需要完成以下工作的研究者或研究小组：

- 为形态学、分类学、生物多样性或 phenomics 项目标注生物身体部位 mask。
- 从标本图像、分类学图版或 STL 渲染形态图中构建人工复核过的分割数据集。
- 把分类学性状描述、图注、标本图像、AI 草稿和最终标签放入同一个可审计项目。
- 使用 SAM 或 VLM 输出作为待复核草稿，而不是直接当作 ground truth。
- 导出 multimodal JSONL、COCO 或 YOLO 风格数据集，用于计算机视觉、VLM 或自定义 fine-tuning 工作流。
- 根据新的类群、身体部位词表、本地模型后端或实验室标注路线改造同一套流程。

目前验证最充分的场景是蚂蚁形态学（Formicidae），但 profile 系统设计上面向任意基于形态的分类学类群。

## 引用

如果 TaxaMask 帮助了你的研究，请引用软件发布版本：

```text
TaxaMask: a taxonomy-oriented mask annotation and multimodal dataset workbench.
Zenodo DOI (all versions): https://doi.org/10.5281/zenodo.20619867
```
