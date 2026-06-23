# TaxaMask 中文使用手册（开发预览版）

> 适用版本：`codex/antscan-stl-tif-rearchitecture` 开发预览分支。

这份手册面向希望用 TaxaMask 处理分类学文献证据、2D / STL 形态标注、TIF / CT 内部结构复核、部位体提取、局部轴重切片和 AI 训练数据整理的研究者。

TaxaMask 的核心原则是：PDF 提取、VLM、SAM、外部模型和 TIF 自动辅助结果都先作为候选材料保存，最终训练真值和正式结果必须由研究者复核确认。

## 1. TaxaMask 是什么

TaxaMask 是一个把“文献证据、形态图像、体数据、人工标注、模型草稿、训练数据导出和智能体辅助改造”放在同一个可追溯工作流里的桌面软件。

当前开发预览版包含四条主要路线：

- PDF 文献证据：筛选论文、提取图版、caption 和文献性状描述。
- 2D / STL 形态标注：标注父部位、子部位，并复核 VLM、SAM 或外部模型草稿。
- TIF / CT 内部结构：导入 TIFF stack，提取 part volume，使用 GPU 体预览和 Local Axis Reslice 复核内部结构。
- Agent Center：检查项目状态、解释报错、辅助配置 profile 和后端，并在研究者确认后修改源码。

TIF / CT 路线目前主要用 AntScan 蚂蚁 CT 数据验证。程序结构没有把 TIF 工作流写死为蚂蚁专用，但还不能宣称已经完成广泛跨类群验证。

## 2. 安装当前开发预览分支

安装前需要准备：

- Git；如果不用 Git，也可以从 GitHub 页面切换到开发预览分支后下载 ZIP。
- Conda 或其他 Python 环境管理工具。
- Python 3.12。
- Node.js 20 或更高版本，并带有 npm，用于内嵌 Agent Center 和修复面板。

如果要安装当前 TIF / CT 开发预览分支，使用：

```bash
git clone --branch codex/antscan-stl-tif-rearchitecture --single-branch https://github.com/wicm84266964/TaxaMask.git
cd TaxaMask
```

创建 Python 环境。推荐环境名为 `taxamask`：

```bash
conda create -n taxamask python=3.12
conda activate taxamask
```

先安装适合机器的 PyTorch。CPU 测试：

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

安装 Agent Center 的 Node 依赖：

```bash
cd vendor/ant-code
npm ci
cd ../..
```

如果需要 SAM 辅助 2D 标注，把 SAM checkpoint 放到：

```text
AntSleap/weights/sam_b.pt
```

模型权重、用户项目、API key、私有 CT 数据、导出结果和本机运行配置都不随仓库发布。

## 3. 启动与显卡检查

已激活环境时运行：

```bash
python AntSleap/main.py
```

Windows 可以双击：

```text
启动TaxaMask.bat
```

脚本会优先寻找本地 `.venv`、当前 Conda 环境、常见 `taxamask` Conda 环境，再兜底旧的 `antsleap` 环境和系统 Python。如果环境在特殊位置，先设置：

```bat
set TAXAMASK_PYTHON_EXE=C:\path\to\python.exe
```

TIF / CT 体预览最好使用 NVIDIA 独显。如果机器同时有核显和 NVIDIA 显卡，请在 Windows 图形设置或 NVIDIA 控制面板中，把当前环境的 `python.exe` 设为高性能 GPU。环境改名后，也要同步更新 `TAXAMASK_PYTHON_EXE` 或 NVIDIA 控制面板里的 python 路径。

打开 TIF 项目后，体预览状态栏会显示当前 OpenGL renderer。这里应能看到 NVIDIA 显卡名称；如果显示 Intel 核显、CPU fallback 或 GPU renderer failed，说明当前三维体预览没有走到理想显卡路径。

如果修改源码后 GUI 无法启动，运行：

```text
启动AntCode修复面板.bat
```

也可以在仓库根目录直接运行：

```bash
node vendor/ant-code/src/cli/dashboard.js --project . --port 7410
```

这个修复面板只启动浏览器版 Ant-Code dashboard，不导入 TaxaMask GUI，适合继续查看报错和修复代码。

## 4. Agent Center

TaxaMask 启动后可以进入 Agent Center。这里适合做四类事情：

- 检查当前项目、配置和运行错误。
- 引导 PDF 文献处理、2D/STL 标注、TIF/CT 复核和数据集导出。
- 解释外部模型后端契约。
- 在确认后辅助修改公开源码或模型适配脚本。

没有 API key 时，TaxaMask GUI 和 Agent Center 面板仍应可以打开。需要模型回答、VLM 草稿或外部模型调用时，用户需要在本机配置模型网关或 API 设置。

## 5. PDF 文献证据

PDF 文献处理用于把分类学论文转成可复核材料：

- PDF 筛选结果：哪些论文可能符合目标类群和研究目的。
- 图版和 caption：哪些图像适合进入候选池。
- 文本部位描述：把 PDF 正文整理成 `taxon -> part -> description` 记录。
- provenance：保留 PDF 文件、页码、caption、附近文本和 profile 信息。

常用 headless 命令：

```bash
python tools/agentic/screen_pdfs.py --pdf-source-dir pdf_folder --out out_folder --config screener_configs/蚂蚁新种筛选_V2示例.json
```

```bash
python tools/agentic/extract_figures.py --pdf-source-dir pdf_folder --db out_folder/literature.db --figure-profile multimodal_configs/蚂蚁分类学图版宽松复核_示例.json --part-description-profile part_description_configs/蚂蚁分类学部位描述抽取_示例.json
```

PDF 图像和文本是证据或候选材料，不会自动成为训练真值。

## 6. 2D / STL 形态标注

2D / STL 路线可以处理：

- 普通形态学图像。
- PDF 提取后人工复核过的候选图。
- STL 或 mesh 渲染得到的 2D 视角图。

STL 在这里指“渲染后的 2D 视角图进入普通标注工作台”，不是直接在三维 mesh 上涂标签。

Labeling Workbench 负责人工标注和复核：

- 父部位标注：较大的稳定结构，例如 head、mesosoma、gaster 或研究者自定义结构。
- 子部位标注：依赖父部位上下文的小结构。
- 文献描述框：查询 PDF-derived literature traits，并把有来源的描述填入当前部位说明。
- AI 草稿复核：模型或 VLM 结果必须由研究者确认后才适合作为训练材料。

## 7. VLM、SAM 与 Blink 草稿

VLM first-mile preannotation 会把图片切成轻量网格，让多模态模型返回结构框，再映射回原图。SAM 可以根据框生成草稿 polygon。

Blink 路线用于从父部位上下文中定位子部位。当前支持：

- ViT-B Blink。
- Heatmap Blink。
- External Blink backend。

这些输出都写入项目作为可复核草稿：

- 未确认 AI 标签可以重新生成。
- 手工标签和已确认标签应被保留。
- 批量 VLM 默认并发较保守，适合先小批量验证。
- 外部后端预测必须人工复核后才适合进入训练真值。

## 8. TIF / CT 工作台

TIF 工作台用于处理 TIFF stack 体数据。它的当前定位是内部结构复核、部位体提取和局部轴重切片，不是直接替代 2D 标注路线。

典型流程：

1. 打开 AntScan 或其他 TIFF stack。
2. 在 specimen 下查看 full volume。
3. 使用 ROI 和关键切片轮廓创建目标 part，例如 head。
4. 通过关键切片插值生成预览 mask。
5. 接受 part mask，写入 part volume。
6. 在 part volume 中使用 3D 体预览、Z/Y/X 多方向切片和剖切截面检查结构。
7. 进入 Local Axis Reslice，对该 part volume 设置局部重切片轴。
8. 导出重切片结果。

TIF 工作台复用 TaxaMask 的 specimen、part、mask、contours 和 extraction metadata。原始 TIFF stack 不会被修改。

## 9. 3D 体预览与剖切

TIF 工作台提供 GPU 体预览，用来在三维空间中检查 full volume 或 part volume。

当前可用的观察能力包括：

- 体渲染预览。
- mask boundary / masked image 叠加。
- Z/Y/X 多方向切片浏览。
- 观察侧裁切和清晰截面显示。
- 局部结构检查模式。
- 体预览状态栏显示当前 renderer、GPU 状态和 CPU fallback 提示。

剖切和截面只改变屏幕显示，不会修改保存的 TIFF、mask、part volume 或训练数据。

如果旋转或缩放很卡，优先检查：

- 当前 OpenGL renderer 是否为 NVIDIA 显卡。
- 是否误用了核显或 CPU fallback。
- 静止高清、采样步数、透明累积模式是否设置过高。
- 当前 volume 是否远超 GPU 显存或纹理限制。

## 10. Local Axis Reslice

Local Axis Reslice 用于对某个 part volume 进行局部坐标系重切片。它不是 Brain Reslice，脑部只是第一个验证模板。

最小闭环：

1. 先用 TIF 工作台创建目标 part volume。
2. 在 part volume 中显示原始 TIFF Z 轴，作为锁定的 source direction reference。
3. 从 source Z-axis 复制 editable output Z-axis。
4. 在 3D 体预览中拖动轴的两端，确定重切片推进方向。
5. 设置 roll reference point pair，例如脑部模板中的 left / right reference points。
6. 检查右侧栏中轴和参照点的关系参数。
7. 导出重切片后的 `image.tif` 和 `metadata.json`。
8. 如果 part 已有 mask，可额外导出 `mask.tif`。

重切片方向严格由 editable output Z-axis 决定。roll reference point pair 用于方向标准化和后续复核，不改变“沿这根主轴切片”的基本逻辑。

导出结果挂在：

```text
specimen
  -> part
     -> Reslices
        -> reslice item
           -> image.tif
           -> metadata.json
           -> mask.tif, 如果存在 part mask
```

灰度图像重切片使用 linear interpolation。mask / label 重切片使用 nearest-neighbor interpolation，避免标签值被插值污染。

## 11. TIF 训练素材记录

当前开发预览版已经开始把人工处理过程设计成可训练素材来源，但现阶段重点是数据收集和结构规范，不是直接内置一个成熟自动定位模型。

应被记录的关键材料包括：

- 原始 specimen 和 part volume 的身份。
- ROI、关键切片轮廓和 part mask。
- source Z-axis。
- editable output Z-axis。
- local frame: origin、x_axis、y_axis、z_axis。
- roll reference point pair。
- reslice 参数、导出路径和 provenance metadata。

这些记录未来可用于训练局部结构定位、部位提取和 local frame 预测模型。当前阶段仍以人工确认结果为可信数据来源。

## 12. 外部模型后端

TaxaMask 通过 JSON 契约连接外部模型：

- 父部位后端契约：`docs/contracts/external_backend_contract_v1.md`
- 子部位 Blink 后端契约：`docs/contracts/external_blink_backend_contract_v1.md`
- TIF local-axis 后端契约：`docs/contracts/tif_local_axis_backend_contract_v1.md`

外部后端负责训练或预测；TaxaMask 负责生成 contract、接收 result、把结果放回项目供研究者复核。

当前 TIF/CT 路线的 AI 方向先保留训练素材记录和后端契约位置。具体模型训练与推理链路需要在后续确定模型方案后再补齐。

## 13. 数据集导出

2D 路线主要导出：

- Multimodal JSONL。
- COCO 风格数据。
- YOLO 风格数据。
- 模型 profile 摘要。

TIF / CT 路线当前主要导出：

- part volume 相关记录。
- local-axis reslice 的 `image.tif`。
- reslice `metadata.json`。
- 可选 `mask.tif`。
- 用于后续训练的人工操作记录。

导出完成后，应检查输出目录中的图像、标签、metadata 和项目树引用是否一致。

## 14. Profile 适配

适配新类群时，建议复制模板再改：

- PDF 筛选：`screener_configs/`
- 图版提取与复核：`multimodal_configs/`
- PDF 部位描述抽取：`part_description_configs/`
- 项目结构模板：`json_projects/templates/`

不要把 API key 写进 profile。先用小批量 PDF、图片或 TIFF stack 验证，再扩大规模。

## 15. 数据边界

TaxaMask 仓库只应包含源码、公开配置模板和公开文档。以下内容应保留在用户本机：

- 私有 CT / TIF 数据。
- 本地 TaxaMask project JSON。
- 导出的 part volume、resliced TIFF 和训练输出。
- SQLite 数据库。
- 模型权重和 checkpoints。
- API key、私有网关地址和 `.env`。
- Agent session、task records 和本机运行缓存。

这些内容已由 `.gitignore` 默认排除。公开发布前仍建议用 `git status --short` 检查一次 staged 文件清单。
