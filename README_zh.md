# TaxaMask

**TaxaMask** 是一个面向分类学和形态学研究的开源工作台，用于把文献性状描述整理、标本图像标注、AI 预标注、人工复核、模型训练和数据集导出组织成一条可追溯的研究流程。

TaxaMask 来自真实的蚂蚁分类学研究场景：研究者经常需要在标本图像、形态特征、分类学文献、物种描述、图版 caption、人工标注和机器学习训练数据之间反复切换。TaxaMask 把这些分散环节整合为可组合的工作流入口，让研究者从 VLM 草案和模型粗标开始，通过人工复核不断积累可靠训练材料，逐步迭代到更稳定的自动化精细标注流程。

TaxaMask 还内嵌 Agent Center 智能体工作台。它的设计目标不是让用户先读完几十页专业软件手册，再按固定按钮流程操作；而是让没有代码基础的分类学研究者也能用自然语言询问当前项目状态、配置符合自己需求的模型、规划训练路线、解释错误和运行产物，并把 TaxaMask 改造成适合自己类群和研究习惯的形态。

TaxaMask 不预设每个分类学工作流都必须走同一条固定路线。用户可以围绕自己的类群、图像材料、文献性状描述、标注目标和模型条件，与智能体共同定义从材料整理、预标注、人工复核、模型训练到数据集导出的具体流程。智能体不替代分类学判断，而是帮助研究者把 PDF、图像、标注、训练和导出这些容易分散的步骤组织成更容易审计、调整和继续迭代的研究工作流。

## 图示概览

![TaxaMask 工作流概览](docs/assets/readme/figure_1_taxamask_workflow.png)

TaxaMask 把文献证据、标本图像、模型草稿、人工复核、训练导出和模型反馈放在同一个可追溯项目循环中。Agent Center 位于工作流上层，用自然语言帮助用户检查状态、配置模型、排查错误、适配 profile 和规划训练。

## 三个核心亮点

- **候选材料与训练真值严格分离。** PDF 提取的图版、VLM 生成的草案、模型预测的输出，都不会自动变成训练真值。每一步都留有人工复核入口，这对分类学研究的可追溯性至关重要。
- **内嵌 Agent Center 智能体工作台。** 研究者可以用自然语言询问项目状态、配置模型后端、排查错误、规划 PDF 筛选或训练路线，把 TaxaMask 适配到自己的类群和研究习惯。
- **通过 profile 适配不同类群，不绑定单一分类单元。** 蚂蚁形态学是验证最充分的参考路线；其他具备形态学标注需求的类群可以通过复制 profile 逐步适配，先用小批量数据跑通再扩大。

当前公开版本在蚂蚁形态学和蚁科分类学场景中验证最充分；同时，项目通过 profile 和模板机制，也可以适配到其他具备形态学标注、文献性状描述整理和训练数据集生成需求的分类学工作流。

## 适合哪些研究场景

TaxaMask 主要面向需要把文献性状描述、形态图像和训练数据连接起来的研究者，例如：

- 蚂蚁、昆虫或其他生物类群的分类学研究；
- 新种描述、分类修订、图版整理和形态特征复核；
- 标本图像中的头部、胸部、腹部、附肢、局部结构等 mask 标注；
- 从已有或待筛选的 PDF 文献中提取图版、caption 和文献性状描述；
- 为 SAM、YOLO、COCO 或多模态模型准备可追溯的训练数据集；
- 通过 VLM 预标注、AI 粗标和人工复核逐步迭代到更稳定的自动化精细标注。

## 关键词

分类学图像标注、形态学 mask 分割、VLM 预标注、AI 粗标、人工复核、自动化精细标注、智能体辅助工作流、文献性状描述、蚂蚁分类学、蚁科、昆虫分类学、新种描述、分类修订、PDF 文献筛选、图版提取、caption 信息、训练数据集生成、SAM 辅助标注、COCO/YOLO 导出、biodiversity informatics、taxonomic image annotation、morphological segmentation、species description。

## 当前公开范围

公开 v1.0 版本提供这些可组合入口，而不是规定唯一流程：

- `TaxaMask Agent Center`：内嵌智能体工作台，用自然语言帮助用户定义工作流、检查项目状态、配置模型、排查错误、适配 profile 和规划外部模型接入。
- `PDF Evidence`：筛选分类学 PDF，提取图版、caption 和文献性状描述，并把人工复核后的候选图导入 2D 项目。
- `2D/STL Morphology`：在标注工作台中处理普通形态学图片和 STL 渲染得到的 2D 视角图。
- `Blink / Child-Part Refinement`：在父部位区域内训练或调用子部位专家。
- `VLM Drafts`：为指定结构生成需要人工复核的初步框和可选 SAM 草稿 polygon。
- `External Backends`：通过公开 JSON 契约连接自定义父部位或子部位模型。

![TaxaMask 公开界面概览](docs/assets/readme/figure_2_taxamask_ui_overview.png)

公开界面围绕四个实际入口组织：Agent Center 用于本地工作流辅助，PDF extraction setup 用于准备文献证据，candidate review 用于筛选导入材料，Labeling Workbench 用于可复核形态标注。

## 人工复核循环与参考路线

![TaxaMask 人机协同标注循环](docs/assets/readme/figure_3_human_in_the_loop_cycle.png)

TaxaMask 把 VLM 框、SAM mask、定位器预测和外部后端输出都视为草稿材料，直到研究者完成复核。这样既能利用 AI 减少重复劳动，又不会让生成结果悄悄变成 ground-truth 标签。

![蚂蚁形态学参考工作流](docs/assets/readme/figure_4_ant_morphology_case.png)

蚂蚁形态学是当前版本验证最充分的参考路线。父部位草稿、子部位候选、人工复核 mask 和导出的训练记录会通过项目来源记录保持连接；其他类群可以通过已验证的 profile 和后端契约适配同一模式。

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

这些方式都需要 Node.js 20 或更高版本，并且需要先在 `vendor/ant-code` 中执行过 `npm ci`。

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

## 引用

在 DOI 或论文发布前，可以引用 GitHub 仓库和 release 版本：

```text
TaxaMask: a taxonomy-oriented mask annotation and multimodal dataset workbench.
GitHub repository, version v1.0.0.
```
