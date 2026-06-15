# TaxaMask 中文使用手册（公开版）

> 适用版本：TaxaMask v1.0.0 公开源码版（2026-06-09）

这份手册面向希望用 TaxaMask 做分类学文献性状描述整理、2D 形态学标注、STL 渲染视角图复核、模型草稿复核和数据集导出的研究者。

## 1. TaxaMask 是什么

TaxaMask 是一个把“文献性状描述、形态图像、人工标注、模型草稿和训练数据导出”放在同一研究流程里的工作台。

它的核心原则是：模型输出和 PDF 提取结果都是候选材料，最终训练真值必须由研究者复核确认。

## 2. 安装环境

安装前需要准备：

- Git；如果不用 Git，也可以从 GitHub 下载 ZIP。
- Conda 或其他 Python 环境管理工具。
- Python 3.12，作为当前公开源码版推荐版本。
- Node.js 20 或更高版本，并带有 npm，用于内嵌 Agent Center 和 Ant-Code dashboard。

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

然后先安装适合机器的 PyTorch：

```bash
pip install -r requirements-torch-cpu.txt
```

或 NVIDIA CUDA 12.1：

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

公开仓库不包含 `node_modules`。如果跳过这一步，TaxaMask 主界面可能仍可启动，但 Agent Center、浏览器 dashboard 和修复面板可能无法正常工作。

如果需要 SAM 辅助标注，把 SAM checkpoint 放到：

```text
AntSleap/weights/sam_b.pt
```

权重、用户项目、API key 和运行产物都不随公开仓库发布。

TaxaMask 可以在没有 API key 的情况下打开，Agent Center dashboard 也可以先打开。需要模型回答、VLM 草稿或外部模型调用时，用户需要在本机配置模型网关或 API 设置，不要把这些私有配置写入仓库文件。

## 3. 启动

已激活环境时运行：

```bash
python AntSleap/main.py
```

Windows 可以双击：

```text
启动TaxaMask.bat
```

脚本会寻找本地 `.venv`、当前 Conda 环境、常见 `taxamask` Conda 环境和系统 Python。如果环境在特殊位置，先设置：

```bat
set TAXAMASK_PYTHON_EXE=C:\path\to\python.exe
```

如果你修改源码后 GUI 无法启动，运行：

```text
启动AntCode修复面板.bat
```

它只启动浏览器版 Ant-Code dashboard，不导入 TaxaMask GUI，适合继续查看报错和修复代码。也可以在仓库根目录直接运行：

```bash
node vendor/ant-code/src/cli/dashboard.js --project . --port 7410
```

这两种方式都需要 Node.js 20 或更高版本，并且需要先完成 `vendor/ant-code` 里的 `npm ci`。

## 4. Agent Center

TaxaMask 启动后默认进入 Agent Center。这里的 Agent 适合做四类事情：

- 检查当前项目、设置和运行错误。
- 引导 PDF 文献处理、2D/STL 标注、VLM 草稿和数据集导出。
- 解释外部模型后端契约。
- 在确认后辅助修改公开源码或模型适配脚本。

Agent 上下文只发送紧凑摘要和相关路径，不默认发送完整项目 JSON、API key、数据库或大模型原始响应。

## 5. PDF 文献处理

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

重要边界：PDF 图像和文本是证据或候选材料，不会自动成为训练真值。

## 6. 2D/STL Morphology

2D/STL Morphology 是当前公开版最主要的标注路线。

它可以处理：

- 普通形态学图像。
- PDF 提取后人工复核过的候选图。
- STL 或 mesh 渲染得到的 2D 视角图。

STL 在公开版中指“渲染后的 2D 视角图进入普通标注工作台”，不是直接在三维 mesh 上涂标签。

## 7. Labeling Workbench

Labeling Workbench 负责人工标注和复核：

- 父部位标注：较大的稳定结构，例如 head、mesosoma、gaster 或研究者自定义结构。
- 子部位标注：依赖父部位上下文的小结构。
- 文献描述框：可查询 PDF-derived literature traits，并把来源明确的描述填入当前部位说明。
- AI 草稿复核：模型或 VLM 结果必须由研究者确认后才适合作为训练材料。

大项目打开时会尽量保持轻量：图片组默认折叠，避免一进项目就加载第一张大图或预加载模型。

## 8. VLM 与 SAM 草稿

VLM first-mile preannotation 会把图片切成轻量网格，让多模态模型返回结构框，再映射回原图。SAM 可以根据框生成草稿 polygon。

这些输出写入项目作为可复核草稿：

- 未确认 AI 标签可以重新生成。
- 手工标签和已确认标签应被保留。
- 批量 VLM 默认并发较保守，适合先小批量验证。

如果草稿显示异常，优先检查当前图片路径是否与项目记录一致。

## 9. Blink 子部位专家

Blink 路线用于从父部位上下文中定位子部位。公开版支持：

- ViT-B Blink。
- Heatmap Blink。
- External Blink backend。

子部位专家适合做“局部结构”的候选定位。它的结果仍需要人工复核，不应直接视为正式标注。

## 10. 外部模型后端

TaxaMask 通过 JSON 契约连接外部模型：

- 父部位后端契约：`docs/contracts/external_backend_contract_v1.md`
- 子部位 Blink 后端契约：`docs/contracts/external_blink_backend_contract_v1.md`

外部后端负责训练或预测；TaxaMask 负责生成 contract、接收 result、把结果放回项目供研究者复核。

如果 Agent 要修改外部适配脚本，它应先说明修改哪个文件、为什么需要修改、可能影响哪个模型。修改 TaxaMask 主源码时，风险更高，需要更明确的确认。

## 11. 数据集导出

公开版主要导出：

- Multimodal JSONL。
- COCO 风格数据。
- YOLO 风格数据。
- 模型 profile 摘要。

导出完成后，检查输出目录中的图片、标签、标注 JSON 和 `model_profile_summary.json`。后者用于记录导出时使用的父部位/子部位模型方案，方便以后追溯数据来源。

## 12. Profile 适配

适配新类群时，建议复制模板再改：

- PDF 筛选：`screener_configs/`
- 图版提取与复核：`multimodal_configs/`
- PDF 部位描述抽取：`part_description_configs/`
- 项目结构模板：`json_projects/templates/`

不要把 API key 写进 profile。先用小批量 PDF 和图片验证，再扩大规模。

## 13. 不应上传的内容

公开仓库不应包含：

- `.lab-agent/config.json`、sessions、task outputs 等本机 Agent 运行状态。
- API key、用户 runtime settings、真实项目 JSON。
- SQLite 数据库、PDF 输出、图像输出、训练报告。
- 模型权重、训练 checkpoints、缓存目录。
- 个人机器路径和私有网关地址。

这些内容已经通过 `.gitignore` 作为默认保护对象。
