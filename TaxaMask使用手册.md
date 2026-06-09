# TaxaMask 完整中文操作手册

> 适用版本：TaxaMask 开源正式版 v1.0（2026-06-09）：Agent Center / Ask Agent 路由 / PDF 文献证据闭环 / 2D-STL 大项目标注 / SAM 与 VLM 草稿复核 / 父部位与子部位标注 / 模型方案与 Blink 后端切换 / TIF 离屏 GPU 体预览 / 数据集导出
>
> 适用对象：需要独立使用 TaxaMask 进行 Agent 辅助配置、PDF 文献证据处理、2D/STL 形态学标注、TIF 体数据标注、Blink 精修、模型训练与数据导出的研究者
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
3. [首次启动：Agent Center、语言与界面总结构](#3-首次启动agent-center语言与界面总结构)
4. [项目管理：新建、打开、保存、搬盘后的路径问题](#4-项目管理新建打开保存搬盘后的路径问题)
5. [PDF 处理模块：从原始 PDF 到候选数据库](#5-pdf-处理模块从原始-pdf-到候选数据库)
6. [数据工具：浏览数据库、查看 CSV、导出粗 JSONL](#6-数据工具浏览数据库查看-csv导出粗-jsonl)
7. [2D/STL 标注工作台：从图片列表到正式标注](#7-2dstl-标注工作台从图片列表到正式标注)
8. [Cropper 裁剪器：把一张大图拆成多个视角图](#8-cropper-裁剪器把一张大图拆成多个视角图)
9. [主工作台内子部位标注：轨迹积累与专家训练](#9-主工作台内子部位标注轨迹积累与专家训练)
10. [TIF 体数据工作台：切片、材料表与体分割后端](#10-tif-体数据工作台切片材料表与体分割后端)
11. [模型设置、训练、推理与 AI 标注清理](#11-模型设置训练推理与-ai-标注清理)
12. [导出数据集：Multimodal / COCO / YOLO 与 TIF 训练体](#12-导出数据集multimodal--coco--yolo-与-tif-训练体)
13. [恢复边界、常见误区与排错建议](#13-恢复边界常见误区与排错建议)
14. [按钮速查表](#14-按钮速查表)
15. [标准流程模板：照着做的一整套操作路线](#15-标准流程模板照着做的一整套操作路线)
16. [结语：最值得一直记住的三句话](#16-结语最值得一直记住的三句话)

## 当前版本先读：启动中心、Agent 与三条工作流

2026-05-17 这一版之后，TaxaMask 的入口逻辑已经明显变化。旧版本更像“先进入 PDF 或标注工作台，再按按钮操作”；当前版本更像“先进入启动中心，由 Agent 和右侧工作流入口帮你分流”。

第一次使用时，建议先按这个顺序理解：

1. **启动中心 / TaxaMask Agent Center**
   - 中间主区域是内嵌的 Ant-Code Agent。
   - 你可以用自然语言让它帮你解释报错、检查项目、规划训练、整理 PDF 文献处理任务或修改配置。
   - 它默认工作在当前 TaxaMask 仓库，不需要用户理解 Python 命令或 contract JSON。
   - 工作台里的 `Ask Agent / 询问 Agent` 会发送短上下文索引卡片，包括当前页面、诊断路线、建议阅读的大模型对接文件位置、相关源码/契约位置和安全边界；它不会把长文档、完整命令或项目大文件整段复制进聊天框。
   - 如果你通过 Ant-Code 自行修改 TaxaMask 源码后把 GUI 改到无法启动，可以关闭 TaxaMask，双击根目录的 `启动AntCode修复面板.bat`。这个修复面板直接在浏览器里启动 Ant-Code，不依赖 TaxaMask GUI，因此可用于继续排查和修复代码。

2. **2D/STL Morphology 工作流**
   - 适合普通形态图片和从 STL/mesh 渲染出来的多视角 2D 图。
   - 进入后主要使用 Labeling Workbench。父部位标注和子部位标注已经合并到主标注工作台右侧，不再需要日常切换到独立 Blink Workbench。
   - 如果项目刚开始还没有 Locator / Blink 训练素材，可以先用 VLM 第一公里预标注生成草稿框和 SAM 草稿，再人工复核。
   - 这里的 STL 不是直接在 3D mesh 上涂色，而是把已经渲染好的 STL 视角图注册到现有 2D 标注工作台。

3. **TIF Volume 工作流**
   - 适合连续切片 TIF、AMIRA/Avizo 标注数据和内部结构体数据。
   - 它有独立的 TIF 项目、材料表、slice 拖条、`working_edit`、`manual_truth` 和 `model_draft` 标签层。
   - 它不使用 2D/STL 的 Locator/SAM/Blink 训练路线，而是通过独立 TIF 后端契约连接 nnU-Net、MONAI 或自定义体分割脚本。
   - 这一条线目前仍带实验性质，稳定性低于 2D/STL 主路线。当前三维体预览默认采用离屏 GPU 渲染，已降低旧版 TIF OpenGL 画布与内嵌 Ant-Code WebEngine 同窗口冲突的概率；如果仍遇到黑屏或 Qt 图形后端异常，先保存/关闭 TIF 项目或重启程序，不要在未保存编辑时反复切换。

4. **PDF Evidence / 文献证据工作流**
   - PDF 处理不再作为主界面的第一工作台。
   - 它更适合作为 Agent skill、起始页右侧快捷栏里的 `PDF evidence workflow`，或 `File -> Open PDF Evidence Tools` 打开的证据工具。
   - PDF 结果是文献证据、候选图像和 provenance，不会自动变成 TIF 的 `manual_truth` 或 2D/STL 的正式训练真值。

5. **模型加载边界**
   - 程序启动时不再默认加载 Locator 和 SAM。
   - 进入 TIF 工作流也不会加载 Locator/SAM。
   - 一般进入或导入 2D/STL 工作流时，才预加载 Locator 和 SAM。
   - 打开几百张到几千张的大型 2D/STL 项目时，会先轻量进入工作台：左侧图片分组折叠，不自动加载第一张图，也暂不预热 Locator/SAM。你选中图片或请求标注/训练时再加载对应模型。
   - 一旦加载过，回到启动中心不会卸载，方便你在 2D/STL 和 Agent 之间来回切换。

这个变化对研究流程的意义是：你不需要一开始就为所有模型和所有数据类型付出启动成本，也不需要把 PDF、STL、TIF 三类完全不同的数据塞进同一个界面里。TaxaMask 现在更强调“先选工作流，再做标注或训练”。

## 1. 你现在用的到底是什么软件

TaxaMask 是一个**面向分类学和形态学研究的综合科研工作台**。它从蚂蚁分类学图像标注起步，后来扩展到 STL 渲染视角图、TIF/AMIRA 体数据和 Agent 辅助配置。

当前版本里，它有四个核心组成：

1. **Agent Center**
   - 用自然语言完成配置、排错、任务规划和文献处理调度
   - 对接内嵌 Ant-Code，适合不想直接写命令的研究者

2. **PDF 文献证据线**
   - 批量筛选 PDF
   - 提取可能有价值的图像/figure
   - 落库到 SQLite
   - 作为候选证据和 provenance，供后续复核或进一步处理

3. **2D/STL 形态学标注与训练线**
   - 管理普通项目图片和 STL 渲染视角图
   - 在标注工作台中做手工标注 / SAM 辅助标注 / 自动推理
   - 在主标注工作台右侧的子部位标注区里做局部精修和轨迹积累
   - 训练定位器、SAM 分割器和 Blink 微观专家
   - 导出正式训练数据集

4. **TIF 体数据标注与训练线**
   - 新建或打开独立 TIF 项目
   - 导入 TIF stack 或 AMIRA 目录
   - 按 slice 浏览、材料 ID 标注和修订内部结构
   - 导出可训练体数据，并调用独立体分割后端

它不是几个软件随便拼在一起，而是按数据来源和研究用途分工：

- Agent Center 负责“我想做什么、哪里出错、怎么配置”
- PDF 侧负责“资料从哪里来、证据是什么”
- 2D/STL 侧负责“外部形态图像如何变成可靠 mask”
- TIF 侧负责“内部结构体数据如何变成可训练 label volume”

对你的研究工作来说，最重要的逻辑是：

> **先选对工作流，再把候选数据变成可信的人工真值。**

---

## 2. 整个工作流总览

### 2.1 推荐使用顺序

对大多数实际研究任务，我建议先问自己一个问题：

> 我现在手里的是 PDF 文献、普通/渲染图片，还是连续 TIF 体数据？

然后按下面分流：

| 你手里的数据 | 推荐入口 | 后续动作 |
|---|---|---|
| 大量 PDF 文献 | Agent Center 或 PDF Evidence Tools | 筛选、提取 figure、生成 evidence index |
| 普通 2D 形态图 | 2D/STL Morphology | 导入图片、画 mask、训练 Locator/SAM/Blink |
| STL/mesh 已渲染视角图 | 2D/STL Morphology | 按 specimen 注册视角图，进入 Labeling Workbench 标注 |
| TIF stack / AMIRA 数据 | TIF Volume | 导入体数据、检查 material map、修订 slice、导出训练体 |
| 不知道怎么配置或报错 | Agent Center | 让 Agent 带上下文检查项目和设置 |

如果你是从零开始整理一批材料，可以按下面顺序：

1. **准备 API 设置与筛选逻辑方案**
2. **在 Agent Center 或 PDF Evidence Tools 里批量筛 PDF**
3. **把通过筛选的 PDF 做数据提取**
4. **在数据库里检查结果，必要时导出粗 JSONL 或人工筛掉不合适内容**
5. **按数据类型进入 2D/STL 或 TIF 项目**
6. **在对应工作台里做正式人工标注或修订**
7. **需要细部位时，在主标注工作台右侧的子部位标注区完成精修**
8. **训练模型 / 运行预测 / 人工复核 / 再修订**
9. **导出正式数据集**

### 2.2 为什么要分成两层

不要把 PDF、2D/STL 和 TIF 混成一个动作。

- **PDF 侧** 解决的是“哪些文献、图版或候选记录值得关注”
- **2D/STL 侧** 解决的是“外部形态图像怎样变成可靠 polygon/mask”
- **TIF 侧** 解决的是“连续体数据怎样变成可靠 material-ID label volume”

这两层分开有两个好处：

1. 你可以先用相对宽松的方式从大量文献或数据中找候选材料
2. 真正昂贵的人工精修工作，只放在已经进入正确工作流的样本上
3. 2D/STL 的 Locator/SAM/Blink 逻辑不会误套到 TIF 的体分割任务上
4. TIF 的 `manual_truth`、`working_edit`、`model_draft` 不会和 2D polygon 标注混在一起

---

## 3. 首次启动：Agent Center、语言与界面总结构

### 3.0 当前平台支持状态

当前版本的跨平台策略已经收口为：**Windows 继续作为最稳的桌面入口，Linux 是下一阶段重点跨平台训练/服务器入口，macOS 只做 CPU-only 源码级轻量试用**。

这对使用者的实际含义是：

- Windows：当前最推荐、验证最充分的运行环境。
- Linux：本轮非 Windows 的重点目标，适合实验室服务器或工作站部署，尤其是 NVIDIA CUDA 环境；仍需要按实际机器验证 GUI、PyTorch、Poppler 和显卡驱动。
- macOS：可以尝试 CPU 路径做项目管理、标注整理、教学演示和小规模测试；Apple Silicon 的 MPS 加速不进入第一轮支持目标。

如果你只是整理项目、人工标注、检查导出或做很小的数据测试，`CPU only` 可以降低硬件门槛。如果你要训练 Locator、SAM 或 Blink 专家，特别是大量 4K 图像或 `384 / 512` Blink 输入尺寸，仍建议使用 CUDA 版 PyTorch 和 NVIDIA 显卡。macOS 用户可以自行尝试适合本机的 PyTorch / SAM 组合，但这属于高级实验路径，不等同于 TaxaMask 已经正式支持 MPS。

### 3.1 正常启动和修复启动

在 Windows 上，推荐先双击仓库根目录的 `启动TaxaMask.bat`。

这个脚本不再绑定某一台维护电脑的固定 Conda 路径。它会按顺序寻找：

- 仓库里的 `.venv`、`venv` 或 `env`
- 当前已经激活的 Conda 环境
- 常见位置里的 `antsleap` Conda 环境
- 系统 PATH 上的 `python`

如果你的 Python 环境放在其他位置，可以先设置环境变量 `TAXAMASK_PYTHON_EXE`，让它指向具体的 `python.exe`。脚本启动前会检查这个 Python 能不能导入 `PySide6`；如果不能，会直接提示你换环境或安装依赖，而不是让 TaxaMask 打开半截后报一长串错误。

跨平台或其他环境仍可以在已配置好的 Python 环境里运行：

```text
python AntSleap/main.py
```

如果你使用内置 Ant-Code 自行修改 TaxaMask 源码，结果把 GUI 改到无法启动，请不要反复双击正常启动脚本。此时使用根目录的：

```text
启动AntCode修复面板.bat
```

这个脚本只依赖 Node.js 20 或更新版本，不导入 TaxaMask 的 Python GUI，也不需要 PySide6。它会在浏览器里打开 Ant-Code Dashboard，让你继续查看文件、解释报错、撤回或修正刚才的代码改动。

需要注意两点：

- 修复面板优先保证“能打开来修”，因此会跳过项目本地的 Ant-Code 配置文件；如果 `.lab-agent/config.json` 正常但里面存了你的模型/API 设置，修复面板里可能需要重新确认模型接口。
- 如果 Node.js 不在常见位置，可以设置 `TAXAMASK_NODE_EXE` 指向具体 `node.exe`；如果默认端口被占用，可以设置 `TAXAMASK_ANTCODE_PORT`。

### 3.2 启动后你会看到什么

当前版本启动后，默认进入 **TaxaMask Agent Center / 启动中心**。

这个页面分两块：

1. **中间主区域：TaxaMask Agent**
   - 嵌入 Ant-Code 的简洁 WebUI。
   - 用于自然语言对话、配置检查、报错解释、PDF 任务规划、训练准备检查。
   - TaxaMask 只显示中间工作区，不显示 Ant-Code 原生的左侧栏和右侧栏，避免界面拥挤。

2. **右侧快捷栏**
   - `Continue last project`：继续上次项目。
   - `Open any project`：打开任意 TaxaMask 项目。
   - `General Settings`：语言、主题、启动行为、自动保存和默认计算设备。
   - `PDF evidence workflow`：让 Agent 规划 PDF 文献证据流程，或直接打开 PDF 工具。
   - `2D/STL Morphology`：进入普通图片和 STL 渲染视角图标注。
   - `TIF Volume`：进入 TIF/AMIRA 体数据标注。

进入工作流后，主界面不是把所有工作台同时排成一排，而是按任务模式切换：

1. **启动模式**：只显示 `Start Center / 启动中心`，中间是 TaxaMask Agent，右侧是最近项目、PDF evidence、2D/STL 和 TIF 入口。
2. **2D/STL 模式**：显示 `Labeling Workbench`，用于普通形态图像和 STL 渲染视角图；父部位标注和子部位标注都在这个主标注工作台右侧完成。
3. **TIF 模式**：只显示 `TIF Volume Workbench`，用于连续切片、材料层和体数据后端。

PDF 工具不再默认占据主标签页，需要时从起始页右侧的 PDF evidence 入口、`File -> Open PDF Evidence Tools` 打开，或交给 Agent 按常驻 TaxaMask 工作流协议和 headless 工具调度。

同时顶部菜单里有：

- `File`
  - `Start Center`
  - `New Project`
  - `New TIF Volume Project`
  - `Open Project`
  - `Save Project`
  - `Import STL Rendered Views to Labeling Workbench`
  - `Open PDF Evidence Tools`
  - `Export Dataset`
- `Workflow`
  - `2D/STL Morphology Workflow`
  - `TIF Volume Workflow`
  - `Create 2D/STL project`
  - `Create TIF project`
  - `Import STL Rendered Views to Labeling Workbench`
- `Settings`
  - `General Settings`
  - `2D/STL Model Settings`
  - `TIF Volume Model Settings`


### 3.3 启动中心里的 Agent 怎么用

你可以把 Agent 当成“懂 TaxaMask 项目的工作流助手”，而不是普通聊天框。适合直接问：

```text
帮我检查当前 TIF 项目为什么还不能训练。
```

```text
我想用 nnU-Net 训练这批 TIF，帮我看设置缺什么。
```

```text
解释最近一次导入 AMIRA 的报错。
```

```text
帮我处理这批 PDF 文献，提取图版和 caption，结果只作为 evidence。
```

工作台顶部的 `Start Center / 启动中心` 和 `Ask Agent / 询问 Agent` 是快捷入口。点击后会把当前项目、工作台、active specimen、当前部位或材料层、最近日志等上下文带回启动中心，避免你重新描述现场。

目前 TIF 工作台的 `Ask Agent` 仍建议谨慎使用：当前三维体预览已改为离屏 GPU 渲染，降低了旧版嵌入式 OpenGL 画布和 Ant-Code WebEngine 的 Qt 图形后端冲突风险。TIF 仍是实验性链路；如果遇到黑屏或渲染异常，优先保存并关闭 TIF 项目或重启程序，再单独排查。

`Ask Agent` 现在不是简单复制当前页面内容，而是生成一张短的“诊断索引卡片”。这张卡片通常包含：

- 当前来自哪个页面或工作台
- 当前项目、图像、specimen、部位或 material 的简要信息
- 最近日志摘要
- 诊断路线，例如 2D/STL 外部后端、TIF 后端、主标注工作台、Blink 精修或 PDF evidence
- 建议 Agent 阅读的 `LLM_CONTEXT_DETAILED.md` 章节
- 相关源码、契约文档和可能需要检查的运行产物
- 安全边界，例如不要自动把 PDF 候选或 TIF `model_draft` 当成训练真值

这对排错的意义是：Agent 不需要在整份文档里盲找，也不需要你手动解释“我现在在哪个界面”。它会先根据索引卡片定位相关文档和源码，再决定是否需要读取项目 JSON、日志、contract 或运行结果。

出于数据安全和对话长度控制，`Ask Agent` 不会默认发送完整命令文本、API key、项目大 JSON、TIF sidecar、PDF 运行产物或整段大模型对接文档。它只发送摘要和路径；如果 Agent 需要深入检查，会按路径读取具体文件。

### 3.4 Agent 写入权限：外部后端适配与源码开发

TaxaMask Agent 现在把写入权限分成三层：

- 普通排查：读取设置、日志、文档、契约和源码，不需要额外弹窗。
- 外部模型后端适配：修改自定义模型用的外部脚本或配置时，会出现轻确认。这类修改可能让某个自定义模型跑不起来，或让预测结果格式不符合导入要求，但不会放开 TaxaMask 主程序源码。
- TaxaMask 源码开发：修改 TaxaMask 程序本身时，会出现强确认。这可能影响 2D/STL、TIF、Agent Center、导入、训练或结果复核。只有当外部后端契约或设置项不足以完成适配时，才应该进入这一层。

对自定义模型来说，2D/STL 和 TIF 是两条不同线路。2D/STL 外部后端负责输出可复核的候选框或 polygon；TIF 外部后端负责把体分割预测写回 `model_draft`。Agent 在申请源码开发前，应该先说明为什么仅改外部后端脚本或配置不够。

### 3.5 语言切换

路径：`Settings -> General Settings`

当前版本中，以下区域已经支持较完整的中文显示：

- 主工作台主要按钮和弹窗
- 主工作台子部位标注区
- Cropper 裁剪器
- PDF 处理页的重要控制项和运行参数

这对实际操作的意义不是“界面更好看”，而是：

- 你更容易判断某个按钮到底是在启动流程、保存状态，还是只是切换显示模式
- 降低“英文术语看懂了，但实际数据效果误解了”的风险

### 3.6 启动后自动恢复上次项目

如果 `General Settings` 里的启动行为设为继续上次项目，而且配置里记着上次项目路径，同时该项目仍存在，程序会尝试恢复上次会话。

这意味着：

- 你重新打开程序时，可以直接带着上次的项目状态继续工作
- 如果你希望每次先回到 Agent Center，可以在 `General Settings` 中把启动行为设为 `Show Start Center`

如果上次项目是上千张图量级的 2D/STL 大项目，程序会先用轻量方式进入工作台：左侧图片分组默认折叠，不会立刻选中并加载第一张原图。你可以先确认项目已经打开，再展开 `Original Images`、`Split Crops`、`Hard-joined Candidates` 或其他分组，选择真正要复核的图片。

### 3.7 为什么现在不默认加载 Locator 和 SAM

旧版本默认启动时就会尝试加载 SAM/Locator。当前版本改成了惰性加载：

- 打开 TaxaMask 到启动中心：不加载 Locator/SAM。
- 进入 TIF Volume：不加载 Locator/SAM。
- 进入 2D/STL Morphology：一般会预加载 Locator/SAM。
- 打开上千张图量级的 2D/STL 大项目：先不做启动时模型预加载，等你点击自动标注或训练时再加载。
- 从 2D/STL 回到启动中心：已经加载的模型保留，不反复卸载。

这对研究者的实际好处是：如果你今天只是整理 TIF 项目、配置后端、处理 PDF 或让 Agent 帮你排错，就不会一启动就占用显存和等待 SAM 初始化。只有真正进入需要 2D/SAM 辅助标注的工作流时，才付出模型加载成本。

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

当前版本的路径恢复不再写死某个作者本机目录。推荐先使用主菜单里的：

```text
File -> Check / Relocate Project Images
```

它会先统计当前项目里多少图片路径可访问、多少路径缺失。若有缺失，你可以选择新的图片库根目录，程序会显示一份重定位预览；只有你确认后，才会把缺失图片路径改写到项目里并保存。

这个工具只会修复当前缺失的图片路径，并且只接受在新根目录下能唯一匹配文件名的图片。若同名图片出现多份，它会留在未解决列表，避免把某只标本的标注错误连到另一张图上。

当前项目加载时会把项目图片、标签、比例尺和图片来源记录统一到同一张图片的绝对路径身份。也就是说，如果旧项目里同一张图片一边以相对路径保存、一边因为 VLM 预标注写入了绝对路径草稿，程序会在打开项目时尽量合并到同一张图下。这可以避免“草稿其实保存了，但当前工作台看不到，必须退出再进才显示”的情况。

高级兜底仍然可以通过本地配置里的 `known_relocated_roots` 做映射。

本地配置现在保存在系统用户配置目录，而不是仓库根目录：

- Windows：`%APPDATA%/TaxaMask/user_config.json`
- Linux：`~/.config/taxamask/user_config.json`
- macOS：`~/Library/Application Support/TaxaMask/user_config.json`

如果旧版本在仓库根目录留下了 `user_config.json`，程序首次运行时会复制一份到新的系统配置目录，但不会删除旧文件。

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
- 如果项目里同时有原图、切分图、硬拼接候选或待手动切分图，列表会按 `Original Images / Split Crops / Hard-joined Candidates / Manual Split Needed` 这类分组显示，点击分组表头可以折叠或展开

这有利于你快速判断当前项目的进度，而不是每次都自己数。

在上千张图片的项目里，折叠某个分组只是改变左侧列表显示，不会重新读取原图文件。程序会复用刚算好的分组结果，因此可以用它快速隐藏大批量原图，只看裁剪图或待处理队列。

右键图片列表时，`New Image Group / 新建图片分组` 会直接出现在右键菜单第一层。`Move to Image Group / 移动到图片分组` 子菜单只负责把选中的图片移动到已有目标分组。自定义分组里的最后一张图片被移走后，这个空分组会从左侧栏、移动目标和 VLM 分组选择里自动清理；如果以后还要用同样的整理篮子，可以重新新建。

500 张以上图片的项目首次打开或继续上次项目时，左侧图片分组会先折叠显示，例如只显示 `Original Images (1200)` 这样的表头。这样做是为了避免刚进入项目时一次性创建上千个列表行、再自动加载第一张大图造成界面像卡死。图片没有丢失；点击分组表头即可展开。

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
| Test Text LLM | 测试文本模型 | 发送极小纯文本请求，确认文本模型配置可用 |
| Test Multimodal LLM | 测试多模态模型 | 发送程序生成的小 PNG 和文字，确认视觉模型配置可用 |
| Remember API Key | 是否持久化保存密钥 | 勾选后会写入本机设置文件 |
| Save API Settings | 保存当前 API 配置 | 下次启动可自动恢复 |

Text LLM 和 Multimodal LLM 可以不同。实际工作中，常见做法是用较快、较便宜的文本模型先筛 PDF，再用支持图像输入的多模态模型复核 figure。

API key 不属于筛选或图版 profile。它只属于本机运行设置，不应该写进开源模板。

建议在真正开始筛选或提取前先点一次测试按钮。多模态测试使用程序内部生成的小图片，不依赖某张本地测试图，所以即使你移动了结果文件夹或测试数据，也不会因为测试图路径丢失而误判模型不可用。

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

当前默认的蚂蚁 figure profile 是 `蚂蚁分类学图版宽松复核_示例`。它不再要求 `lateral + dorsal + head_frontal` 三视图齐全，而是保留单一蚂蚁物种/单一分类单元的分类学形态图版：整体 habitus、多视角图、头部、局部诊断结构或同物种图版组合都可以进入 evidence review。多物种或多分类单元比较图、地图/系统树/表格/生态实验图、非蚂蚁主体仍会被拒绝。

`Part Description Profile` 决定纯文本部位描述抽取：

- 用哪些部位桶整理原文形态描述
- 文本模型按什么提示词输出 `物种/分类单元 -> 部位 -> 文中描述`
- 哪些文本块角色写入 `pdf_text_blocks`
- 本次运行使用的部位描述方案会记录到 `part_extraction_runs`

当前默认的蚂蚁 part-description profile 是 `蚂蚁分类学部位描述抽取_示例`。它只读取 PDF 原文文本块，不输入图片；输出是带文件名、文件路径、hash、页码和 block_ref 的文献证据，不是图像标签，也不是训练真值。

#### 当前筛选流程

PDF 筛选现在使用 **V2 (CSV Full LLM)** 流程。

关键词词库是辅助材料，真正的 include / exclude / uncertain 判定标准由当前方案里的 LLM 提示词决定。

对实际研究的意义是：你可以把蚂蚁筛选方案复制成植物、甲虫或其他类群方案，只要同步改目标类群词、支持性形态词、排除词和提示词。

Figure profile 和 Part Description Profile 都可以复制改写。不开多模态验证时，figure profile 仍会影响图文提取阶段；启用多模态验证时，它的复核规则会继续传给多模态模型。Part Description Profile 则影响文本部位桶和文本整理提示词。其他物种使用者的适配方式和这次蚂蚁默认 profile 迁移类似：复制模板，替换目标类群、接受图版类型、拒绝图版类型、结构字段、部位桶和提示词。

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
| Lines/PDF | 每篇 PDF 抽取前多少行文本，当前默认 50 行 | 太少可能漏掉新种证据；50 行比旧的 30 行更稳，但会略微增加 prompt 负担 |
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
- 结果文件夹
- 数据库文件名（SQLite `.db`）
- 是否启用多模态验证

现在不要把这里理解成“只选一个数据库文件”。结果文件夹里会同时保存：

- SQLite 数据库索引
- `<数据库名>_v2_artifacts/` 运行产物文件夹
- 提取出的原始候选图、accepted 图、needs-review 图、review batch 和 raw LLM response

默认情况下，这些运行产物会放在 `TaxaMask_outputs/` 下，而不是堆在 `AntSleap/` 主程序文件夹中。

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
- 蚂蚁默认方案关注单一物种/单一分类单元的整体图、多视角图、头部和局部诊断结构，不要求三视图齐全
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
- `pdf_text_blocks`
- `taxon_part_descriptions`
- `part_extraction_runs`

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

#### 纯文本性状表的意义

`taxon_part_descriptions` 不是图片标签，而是文本模型从 PDF 原文中整理出的：

```text
物种/分类单元 -> 部位 -> 文献描述
```

它会保留来源 PDF、页码、block_ref 和置信度。后续你在标注工作台中打开“文献性状”弹窗时，程序会按当前图片的 PDF 来源、物种提示和当前部位去检索这些记录。

### 6.4 Open Database File：浏览数据库

这个按钮会让你直接选择一个已有 `.db` 文件，然后打开数据库浏览器。

你会看到：

- 左侧表格：每张图的基础记录
- 右侧详情：图片预览 + 文本证据 + 审核状态 + 模型信息
- 顶部翻页栏：显示总记录数、当前页范围、上一页/下一页/首页/末页，并可调整每页行数
- 筛选/搜索栏：按 accepted、needs_review、rejected、人工状态、多模态 real/mock、物种名、PDF 名、caption、证据文本、部位描述和备注检索
- 图库视图：以缩略图卡片快速扫图
- 人工复核区：用直接可点的选项为当前记录保存 `human_accepted / human_rejected / import_ready / needs_crop` 和备注
- 操作按钮：打开图片、打开所在文件夹、打开来源 PDF、导出当前筛选 CSV、复制当前筛选出的图片，或将当前筛选中未被人工拒绝/需裁剪的记录批量设为 `import_ready`

这是你做人工复核时最有用的界面之一。

默认每页显示 500 行，这是为了避免大数据库一次性塞进表格导致界面卡顿；它不是数据库总数限制。上百篇 PDF 的提取结果可以通过翻页逐页完整检查。

表格列宽可以手动拖动调整，长路径列不会在每次刷新后强行撑开。人工复核时可以先只点出 `human_rejected` 或 `needs_crop` 的失败项，最后用“当前筛选全部设为可导入/通过”把剩余可通过记录批量写成 `import_ready`；这个批量按钮不会覆盖已经人工拒绝或标为需裁剪的记录。

人工复核状态会写入独立的 `figure_human_reviews` 表，不会覆盖模型原始的 `accepted`、`review_status` 或多模态判断。这样后续还能同时追溯“大模型当时怎么判”和“研究者最终怎么判”。导出 CSV 和复制图片都按当前筛选条件执行，适合先筛出 `import_ready` 或 `needs_crop` 后再集中导入/裁剪。

“清空筛选”只会重置搜索、筛选、排序和页码，不会删除数据库记录或人工备注。因为它会打断当前复核视角，界面会用红色按钮并弹出确认框。

适合回答这些问题：

- 这张图为什么被 accepted？
- 它是 real 还是 mock？
- 哪些文本证据支持这个判断？
- 图注说的是什么？
- 同一 PDF / 同一物种有没有已经抽取出的部位性状描述？

如果一个结果文件夹里有多个数据库，不要依赖程序自动猜。现在更推荐直接用 `Open Database File` 选择你要浏览的具体 `.db`。

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
<result_folder>/
├── <db_name>.db
└── <db_stem>_v2_artifacts/
    ├── figure_images/
    ├── accepted_figures/
    ├── needs_review_figures/
    ├── review_batches/
    └── batch_raw_responses/
```

其中：

- `accepted_figures/`：通过真实或当前规则接受的图像副本，适合优先作为 2D 项目导入候选。
- `needs_review_figures/`：程序认为需要人工复核的图像副本。
- `figure_images/`：原始提取候选图集合，不等于都适合导入。
- `review_batches/` 和 `batch_raw_responses/`：用于排查多模态模型为什么接受或拒绝某批图。

### 6.8 提取续跑怎么理解

如果你用同一个结果文件夹和同一个数据库文件名再次运行，程序会检查每篇 PDF 是否已有完整提取结果。

- 已完整处理过的 PDF 可以跳过，适合中断后继续跑。
- 如果某篇 PDF 需要重新处理，程序会先清理该 PDF 在数据库里的旧 figure/text/evidence 记录，再写入新结果。
- 这不是简单“永远追加”，也不是无条件“整库覆盖”；它更接近按 PDF 维度的可恢复运行。

实际建议：

- 同一批同一配置中断后，继续用同一个结果文件夹和数据库。
- 如果你换了 prompt、profile、模型或阈值，最好新建一个结果文件夹或数据库名，方便比较两轮结果。

对研究工作来说，最常看的通常是：

- `final_new_species_reports/`
- `manual_review_uncertain/`
- `figure_records` 数据库内容
- `accepted_figures/`
- `needs_review_figures/`
- `batch_raw_responses/`（当你要排查模型判断时）

---

## 7. 2D/STL 标注工作台：从图片列表到正式标注


这一章讲的是 **2D/STL Morphology** 工作流，不是 TIF 体数据工作流。

这里处理两类图像：

- 普通 2D 形态图片、文献候选图、显微图或相机图。
- 已经从 STL/mesh 渲染出来的固定视角 2D 图。

当前 STL 路线不是直接打开一个 3D 模型渲染视图让你在 mesh 上涂色，而是把一批渲染好的视角图注册到现有 Labeling Workbench。这样可以继续复用已经验证过的 polygon 标注、Locator/SAM、父部位标注、子部位标注和导出逻辑。

如果你要做小部位精修，重点看右侧 **`Child-part annotation / 子部位标注`** 小区，而不是再找独立 Blink 工作台入口。当前结构标签由 `Structures` 列表里你选中的标签决定：选中 `Head` 这类父部位时，主要使用 `Parent-part annotation / 父部位标注` 区和正式标注框；选中 `Mandible` 这类子部位时，右侧会显示当前父级、父级框和路由专家状态。

如果项目还没有任何训练素材，可以先用 **`VLM预标注`** 或 **`VLM批量预标`** 做第一公里预标注。它会让多模态大模型在自适应轻量网格输入图上提出粗定位候选框，再用 SAM 生成草稿 polygon。注意：这些结果只是 AI 草稿，必须经过空格确认、当前图像一键通过或人工重画后，才能成为训练材料。

### 7.1 图片导入

工作台里常见的入口有两个：

1. `+ Add Images`
2. `Import & Crop`

#### + Add Images

适合：

- 你已经有单张图片或一批图片文件
- 不需要先拆视角

它会把这些图片加入当前项目，并为每张图初始化标签条目。

一次选择很多图片时，例如从 PDF 提取结果的 `accepted_figures/` 文件夹批量导入几十到几百张候选图，程序会弹出 `图片导入进度` 窗口，并在后台登记图片和保存项目。导入完成后左侧图片列表会统一刷新；这时界面不应该再像“卡死”一样长时间无响应。

需要注意：从 PDF 链路导入的图片仍然只是候选图/证据图。它们进入项目后还需要人工查看、必要时裁剪或标注，不会自动变成正式训练真值。

#### Batch Split Plates / 批量切分拼图

这个功能用于把 PDF 图版、显微拼图或多视角版面图切成单独候选图。当前不引入额外深度模型，只使用轻量规则算法：

- 对白边、浅灰/偏黄纸底、JPEG 压缩后不纯白的分隔带，会用自适应浅色背景判断提高检出率。
- 默认自动切分不再仅凭 `A / B / C / D`、`133 / 134 / 135` 这类面板标号推导统一网格。真实论文图版里的面板常常大小不同，单靠标号强行等分很容易把一个大视图切碎。
- 对无白边、硬贴在一起的图，只有存在明显场景突变或边界证据时，程序才会生成 `hard_seam_panel_split` 候选裁剪图；没有可靠边界时会跳过，交给人工裁剪更安全。
- 硬拼接候选仍需要人工复核。它们可以帮你减少手动画框工作量，但不要把它们当成已经确认的训练真值。

白边/浅色分隔条生成的裁剪图会进入 `Split Crops` 分组。无白边硬拼接生成的候选裁剪图会单独进入 `Hard-joined Candidates / 硬拼接候选` 分组，并在来源记录里保留 `crop_source=hard_seam_panel_split`。旧项目中如果已有 `crop_source=label_guided_panel_split` 或 `letter_label_panel_split`，程序仍会按硬拼接候选兼容显示。某张硬拼接图被标记为 `candidate_split`，意思是“程序生成了候选切分，请复核”，不是“已经可靠完成正式切分”。

#### Remove Image

这是从项目里移除图片及其关联状态，而不是删除你磁盘上的原始文件本体。

但对项目来说，它仍然是高风险操作，因为会一起丢掉该图的标签与比例尺信息。

如果你一次选中很多图片，例如从 PDF 链路筛进来后又人工判定不适合的一批候选图，程序会批量移除这些项目记录，并只保存一次项目文件。它会同步清理该图在项目里的标签、比例尺、PDF/裁剪来源记录和图片分组引用，但不会删除原始图片文件。

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

在上千张图片的项目里，这个操作现在会先在内存里清理所有图片对应结构的数据，然后只保存一次项目文件。它仍然是高危动作，只是不会因为每张图重复写 JSON 而让界面长时间卡住。

#### Rename Structure

如果结构标签名称早期写得不够严谨，例如后来发现某个部位名需要改得更规范，可以先选中这个结构，再点击 `Rename Structure / 重命名结构标签`。

它不是简单改列表文字，而是会把项目里相关引用一起迁移，包括：

- 已有 polygon、描述、人工框和 AI 草稿框；
- VLM 目标部位设置；
- 父子 route、Blink 父级上下文和训练 trajectory；
- 父级框长宽比设置；
- 模型方案里和这个结构有关的选择。

这适合“名称要修正，但已有标注成果还要保留”的情况。它不适合把两个不同结构强行合并；如果新名称已经存在，程序会拒绝重命名，避免把两类标注混到一起。

### 7.3 当前图片物种、文献性状与描述

工作台右侧的 `Current image taxon / 当前图片物种` 下拉框和描述框，是把“图像标注”和“分类学语义”联系起来的关键。

- `Current image taxon / 当前图片物种`：给当前图片设置分类单元，可以是属名、种名、候选分类名或你当前项目需要的分类标识。它是图片级元数据，不会改变 `Structures / 结构标签` 列表。
- `Literature Traits / 文献性状`：从当前图片关联的 PDF 数据库里检索文献抽取出的物种/部位描述。
- 描述框：记录当前选中部位的描述文本，可以手写，也可以从文献性状弹窗里应用或追加。

这意味着：

- 你不只是画多边形，还能把文字语义一起留下
- 后续多模态导出时，这些文本会真正进入样本

如果当前图片来自 PDF 提取链路，并且项目保存了来源数据库或 PDF provenance，点击 `Literature Traits / 文献性状` 后，程序会优先检索当前图片关联 PDF、当前物种和当前部位的结构化描述。找不到时，可以在弹窗里切到原文块搜索，并选择“当前物种优先”或“当前 PDF 全文”。选中描述并应用后，描述框会更新，来源信息会写入项目的 `description_sources`，当前图片物种也会尽量从文献来源自动回填。

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

#### Annotation Box / 标注框

这是主工作台里新增的正式框选工具。它和 `Box Prompt (SAM)` 不同：

- `Box Prompt (SAM)` 只是给 SAM 一个临时提示，不保存为正式框角色。
- `Annotation Box` 会写入当前部位的标注框。

当你选中父部位时，例如 `Head`，`Annotation Box` 画出的 `Head box` 同时也是后续 `Head -> Mandible`、`Head -> Eye` 这类子部位精修的父级上下文。

父级框固定长宽比默认是关闭的。只有当你准备训练小部位定位器、希望父级 ROI 视野保持一致时，才在右侧子部位标注区勾选 `Lock parent box ratio / 锁定父级框比例`。勾选后，父部位的 `Annotation Box` 和父部位的 `Box Prompt (SAM)` 都会按设置中的父级比例约束；取消勾选后恢复自由拖框。

当你选中子部位时，例如 `Mandible`，`Annotation Box` 默认自由比例，不会继承 `Head` 的固定比例。

#### Loose Shrink Box / 收缩松框

这是画布上方工具栏里的另一个框选工具，只用于 Blink 自动收缩的起始范围。

它和 `Annotation Box` 的区别是：

- `Annotation Box` 保存正式标注框。
- `Loose Shrink Box` 只保存到 `shrink_loose_boxes`，用于自动收缩 trajectory，不覆盖正式标注框。

`Loose Shrink Box` 只适合选中子部位时使用。父部位上下文框仍然用 `Annotation Box` 绘制。

### 7.5 亮度和对比度滑块

这两个滑块只是显示增强：

- `Brightness / 亮度`
- `Contrast / 对比度`

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

#### VLM预标注 / VLM批量预标 / VLM 第一公里预标注

这个按钮适合项目最开始没有 Locator/SAM/Blink 素材时使用。

推荐步骤：

1. 先在 `Settings -> 2D/STL Model Settings -> Inference` 里找到 `AI Multimodal Pre-Annotation`。
2. 勾选要交给 VLM 的目标部位。这个列表和 `Main Locator Parts` 分开，建议勾具体解剖结构，例如 `Head / Mesosoma / Gaster / Eye / Mandible`，不要只勾 `Object / Region / Structure` 这类泛称。
3. 设置 `VLM Batch Scope`：`All imported images` 跑项目所有图片，`Images in selected list group` 只跑左侧图片列表中的某一类。
4. 如果批量范围选择按分组处理，可以在 `VLM Image Group` 里选择 `Split Crops / Hard-joined Candidates / Original Images / Manual Split Needed`。通常从 PDF 版面图裁剪后，建议优先选择 `Split Crops`；如果要专门检查无白边硬拼接的候选裁剪，再选择 `Hard-joined Candidates`。
5. 设置 `VLM API Concurrency / VLM API 并发数`。默认是 `1`，适合大多数有速率限制或计费敏感的 API key；只有服务商明确允许并发请求时再调高。几千张图的大任务调高并发会更快，但也更容易触发限速、账单增加或账号风控。
6. 在 PDF Evidence Tools 里配置 Multimodal LLM API。缺少 API 时，VLM 弹窗里的按钮会直接跳到 API 设置区。
7. 回到标注工作台，点击 `VLM预标注` 只跑当前图，或点击 `VLM批量预标` 按设置的批量范围运行。
8. 程序会生成自适应轻量网格 VLM 输入图、调用多模态模型、写入橙色 `aibox`，并尽量用 SAM 生成 `Auto-Annotated` 草稿 polygon。程序会把模型给出的网格坐标映射回原始图片坐标；像素框解析只作为兼容旧响应的 fallback。

运行时会弹出一个进度窗口。它会分开显示：

- 当前进度和步骤，例如准备输入图、调用 VLM、解析结果、写入草稿、生成 SAM 草稿；
- 当前处理到第几张图片；
- 当前图片名。长文件名会缩短显示，完整路径可通过悬浮提示查看。

批量窗口里有 `Stop VLM Batch / 停止 VLM 批量`。如果发现目标部位、API 设置或分组选错，可以停止当前批量任务。停止后程序不会继续派发剩余图片请求；已经发出去的请求会等待安全返回，然后写出 cancelled 摘要。关闭进度窗口时也会先询问是否停止，而不是让几千张图任务在后台悄悄跑完。

对单张图片来说，`write / SAM / report` 这几步可能很快连续完成；框和 SAM 草稿不是逐个部位慢慢刷出，而是在当前图片结果写回后一起出现在画布上。当前版本会统一项目图片路径，避免同一张图被相对路径和绝对路径分成两份记录，因此正常情况下不需要退出工作台再进来才能看到 VLM/SAM 草稿。

复核方式：

- 当前部位草稿正确时，可以按空格确认；
- 当前图像整体草稿都可接受时，可以点 `Accept current image AI drafts`，它只作用于当前图像；
- 草稿不对时，直接重新框选该部位并调用 SAM，人工结果会覆盖旧 AI 草稿；
- 没有 polygon 的纯 `aibox` 不会因为一键通过而进入训练。

重新运行 VLM 或父部位自动标注时，程序会替换未确认的 AI 草稿，但会保留人工标签和已经确认通过的标签。也就是说，第一次 VLM 结果不满意时可以重跑；研究者已经手工修过或确认过的结果不会被新一轮草稿直接覆盖。

这对研究流程的意义是：VLM 帮你省掉最初大量重复画 SAM 提示框的工作，但训练数据仍由研究者复核把关。

#### Auto (Current)

只对当前图片跑一轮自动推理。

它的特点是：

- 会把自动预测写入项目
- 但只补“当前还没有的部位”
- 不会直接覆盖已有手工标注

#### Batch (All)

批量推理只针对**当前未标注图片**。

所以它更像“批量补初稿”，而不是“批量覆盖重算全部项目”。

内置 Locator/SAM 的批量推理会在后台线程里运行，结果回到项目后统一保存和刷新列表。选择外部父部位后端时，`Batch (All)` 也会打开进度窗口并在后台逐张调用外部预测脚本；每张图返回后写入 AI 草稿，批量结束后再统一保存项目。这样大项目批量补初稿时，界面不会因为外部脚本逐张预测而像卡死。

### 7.8 Clear AI Labels

这个按钮不是“清空所有标注”，而是：

- 删除被标记为 `Auto-Annotated` 的自动标签
- 保留人工标注

它适合什么时候用：

- 你试了一轮自动推理，结果不满意
- 想保留手工成果，但清掉自动生成部分重新来

要注意的是：

- 它清的是自动标签语义，不等于“整个项目完全回到没推理过”
- 点击后会先选择清除范围：可以清除全部项目图片，也可以只清除某个图片分组里的 AI 标签
- 确认前会显示将影响多少张图片、多少个 AI 标签；适合在几千张图项目里只重跑某个分组，而不是误清全项目

---

## 8. Cropper 裁剪器：把一张大图拆成多个视角图

Cropper 的作用不是正式标注，而是：

> 把一张含多个视角或多个子图的大图，拆成你后续要单独处理的视角图。


使用时，真正决定“生成哪些新图片”的不是裁剪列表本身，而是你在原图上画出来的裁剪框。点击 **`Save & Add to Project`** 后，程序会在原图同目录生成类似 `原图名__crop_001.jpg`、`原图名__crop_002.jpg` 的新图片，并把这些裁剪图自动加入当前项目。

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

- 在原图附近生成类似 `原图名__crop_001.jpg` 的文件
- 自动把这些新裁剪图加入项目
- 记录裁剪来源、裁剪框和原图尺寸，便于 PDF 来源图片后续继续追溯

如果一次保存了很多裁剪图，加入项目的步骤也会走图片导入进度窗口；裁剪文件已经生成在磁盘上，进度窗口显示的是这些新图正在被登记到当前项目 JSON 中。

#### 这意味着什么

- 原图不会被修改
- 裁剪图会变成项目里的正式新图片
- 后续可以对每个裁剪图独立标注和训练

这对蚂蚁分类图谱尤其重要，因为一张版面图里常常混着多个视角或多个局部。

### 8.4 待手动切分队列和切分图

2D 标注工作台左侧图片列表里的 **`待手动切分`** 是一个复核队列，不是一个永久文件夹。它表示：程序认为这张原始版面图可能有硬拼接或自动切分不可靠，需要研究者手动裁剪。

当你对这类图片使用裁剪器并保存裁剪图后：

- 原图会从 **`待手动切分`** 队列中移出，标记为已完成手动切分
- 新生成的 `__crop_001` / `__panel_001` 图片会进入 **`切分图`** 分类
- 裁剪图不会继承原图的“待手动切分”状态
- 如果旧项目里已经有某张原图派生出的裁剪图，刷新列表时也会把它视为已经处理过

如果某张图的切分状态不符合你的实际复核结果，可以在图片列表中右键，使用 **`标记为已完成手动切分`**、**`标记为待手动切分`** 或 **`清除切分状态`** 手动修正。

---

## 9. 主工作台内子部位标注：轨迹积累与专家训练

当前版本里，Blink 已经不再作为日常必须进入的独立工作台。它的高频能力被合并到 2D/STL `Labeling Workbench` 右侧的 **`Child-part annotation / 子部位标注`** 小区。

这次变化的核心意义是：

> **你始终在主标注工作台的大图坐标里工作，小部位精修、trajectory 积累和当前子部位专家训练都在同一个界面完成。**

旧的独立 Blink widget 仍保留为兼容和开发回退，但普通标注流程不再依赖 `Open in Blink Workbench`、局部会话和 `APPLY TO GLOBAL`。

### 9.1 先记住 Blink 的定位

Blink 不是用来替代大部位定位器的。它更适合做：

- 小结构精修
- 收缩轨迹积累
- 微观专家训练
- 父部位到子部位的路由专家自动起稿

也就是：

> **大部位先在主工作台解决，细部位也留在主工作台里借助子部位标注流程完成。**

### 9.2 父部位、子部位和父级上下文

父部位通常来自 `2D/STL Model Settings -> Main Locator Parts`。蚂蚁模板里常见的是：

- `Head`
- `Mesosoma`
- `Gaster`

不在主定位结构里的部位通常视为子部位，例如：

- `Mandible`
- `Eye`
- `Antenna`

当你选中一个子部位时，右侧子部位标注区会显示：

- 当前路由，例如 `Head -> Mandible`
- 父级上下文
- 父级框是否存在
- 路由专家状态

如果程序能从项目记忆、部位树或已有 route 里判断父级，会自动显示；如果有多个可能父级，你可以在父级上下文下拉框里手动选择。这个选择会记入项目，后续再选这个子部位时不用反复指定。

### 9.3 父级框和固定长宽比

父级框不是额外的新数据层。你选中父部位后，用 `Annotation Box / 标注框` 画出的正式框，就是该父部位自己的框，同时也是子部位精修的上下文 ROI。

例如：

```text
选中 Head
-> 用 Annotation Box 画 Head box
-> 这个框可作为 Head -> Mandible 的父级上下文
```

父级框固定长宽比默认关闭。这样日常核对 VLM 预标注、用 SAM 框选父部位或画最小外接框时，鼠标拖框会保持自然跟手。

当你准备训练小部位定位器、希望父级 ROI 的视野比例更一致时，可以在右侧勾选 `Lock parent box ratio / 锁定父级框比例`。开启后，父部位的 `Annotation Box` 和父部位的 `Box Prompt (SAM)` 都会按设置中的父级比例约束。这样做的目的是减少后续把父级区域缩放到固定训练尺寸时对小部位细节的拉伸。

子部位框和收缩松框不会继承父级比例，它们保持自由比例。

### 9.4 画布上方的三种框工具

为了避免把框的含义藏在右侧栏里，当前版本把框的身份直接放在画布上方工具栏：

- `Box Prompt (SAM)`：临时提示 SAM，不保存为正式标注框。
- `Annotation Box / 标注框`：保存当前部位的正式框。选中父部位时，它也是父级上下文框；选中子部位时，它是子部位正式框。
- `Loose Shrink Box / 收缩松框`：只用于子部位自动收缩的起点，保存到 `shrink_loose_boxes`。

这三种框不要混在一起。

`Annotation Box` 会更新当前部位的正式框，和 polygon 一起作为项目标注的一部分。

`Loose Shrink Box` 只保存到 `shrink_loose_boxes`，用于自动收缩 trajectory 的起点。它不会覆盖正式子部位框，也不用于父部位。

右侧子部位标注区只显示当前 route、父级上下文、父级框和专家状态，并提供用已有父框起草、自动收缩和训练按钮。

### 9.5 Annotate child from existing parent box / 用已有父框标注子部位

这个按钮的语义是：

> **当前 `父部位 -> 子部位` route 已经有可用专家时，让专家先给子部位框，再让基础 SAM 生成草稿 polygon。**

使用前提：

- 当前选中的是子部位
- 当前子部位有父级上下文
- 父级框已经存在
- 当前 route 已启用且指定了可用专家

当前 route 的专家不再被固定理解为 ViT-B Blink。它会按 route 记录里的 `expert_backend` 分流：

- `vit_b_blink`：使用原来的 ViT-B Blink 专家；
- `heatmap_blink`：使用热力图中心点 + 宽高回归的子部位专家；
- `external_blink`：调用你配置的外部 Blink 推理脚本。

这个按钮只使用已经存在的父级框，不会重新跑一遍父部位自动标注。这样做的意义是：父部位框仍然由人工或主模型先确认，子部位专家只在这个局部视野里起草小结构。

如果路由专家未配置，右侧会提示，并可以点击 `Configure Route Expert / 配置路由专家` 直接进入设置中的当前 route。

自动标注成功后，草稿 polygon 和子部位框会直接显示在主画布上，使用的是整张图的全局坐标，不需要再点 `Apply to Global`。

### 9.6 Run auto-shrink / 执行自动收缩

这个按钮的语义是：

> **用当前子部位 polygon 和收缩松框生成训练 trajectory。**

使用前提：

- 当前选中的是子部位
- 父级上下文和父级框存在
- 子部位 polygon 已经画好或确认过
- 已经在画布上方选择 `Loose Shrink Box` 并画过一个松框

按下后，程序会把 trajectory 存入：

```text
trajectories[part_name]
```

并同时记录 `parent_context`，包括父部位、父级框和来源。这对后续训练很重要，因为专家需要知道“这个小部位是在什么大部位视野里学到的”。

如果你已经连续给很多图片画好了子部位 polygon 和 `Loose Shrink Box / 收缩松框`，可以使用同一行的批量自动收缩按钮。它会在当前 `父部位 -> 子部位` route 下检查哪些图片已经具备父框、子部位 polygon 和收缩松框，并为这些图片批量生成 trajectory。已有 trajectory 的图片会跳过，缺少 polygon、松框或父框的图片会在确认提示中计数说明。

自动收缩步数可以在 `2D/STL Model Settings -> Child-part annotation / 子部位标注` 中调整，默认是 `20` 步。20 步会保存包含起始帧在内的 21 帧 trajectory。步数越多，训练材料更细，但数据量和训练时间也会增加；快速跑通流程时先用默认值比较稳。

### 9.7 Train current child expert / 训练当前子部位专家

这个按钮只训练当前 `父部位 -> 子部位` 路由下的子部位专家。训练参数来自当前 2D/STL 模型方案里的 `Child-part annotation / 子部位标注` 页。

当前第一版支持两类内置训练：

- 默认子后端为 `ViT-B Blink Expert` 时，训练原来的 ViT-B Blink 专家；
- 默认子后端为 `Heatmap Blink Expert` 时，训练热力图 Blink 专家。

`External Blink Expert` 第一版主要用于推理接入。外部训练命令作为配置项保留，但真正是否能训练，要看你的外部脚本是否实现相应契约。

它不会把所有部位混在一起训练，也不会把普通 polygon 全部当成 Blink trajectory。真正关键的是：

> **这个子部位是否已经积累了足够多、足够可靠的 trajectory。**

训练完成后，新模型会写出权重和 manifest，并作为 route candidate 出现在 `2D/STL Model Settings -> Inference` 页的路由专家配置中。manifest 会记录它属于 `vit_b_blink` 还是 `heatmap_blink`，避免热力图专家被误当成 ViT-B 专家加载。

当前版本还可以在 `Child-part annotation / 子部位标注` 中选择 Blink 训练方案：

- `方案一：全图/内视角/外视角随机`：保留原方案，会随机使用父框全图、当前框内视角和外视角，并同时监督下一步框和最终框。
- `方案二：全图/内视角随机`：去掉目标可能被遮掉的外视角，只在父框全图和当前框内视角之间训练。
- `方案三：先全图后内视角`：前半段先用父框全图学粗定位，后半段再用内视角学继续收紧。

这三个方案是为了让你后续用上千张图、不同轮次去实测哪种收缩学习更稳。它们不会改变正式标注真值，只影响 Blink/热力图 Blink 子部位专家怎样从 trajectory 中构造训练样本。

子部位训练和父部位训练共用主工作台右侧的训练进度条。训练时可以用同一行的停止按钮安全请求停止；训练完成后，右侧训练进度栏中的 `训练结果 / Training Results` 按钮可以打开历史训练结果浏览器，统一查看父部位和子部位训练报告。

### 9.8 Configure Route Expert / 配置路由专家

主工作台只显示当前 route 的状态，不展示完整专家树。原因是：标注时最重要的是“我现在能不能用这条父子链路”，而不是在狭窄右侧栏里管理所有模型。

当你点击 `Configure Route Expert` 时，程序会：

- 打开 `2D/STL Model Settings`
- 自动切到 `Inference / 推理` 页里的路由专家配置区域
- 尝试定位当前 `parent -> child` route
- 如果 route 不存在，会先登记一个候选 route

在路由专家配置里，route 会显示 parent、child、启用状态、专家后端、专家 manifest、输入尺寸、最低置信度和备注。选择专家时应尽量选 manifest 中 parent/child 与当前 route 一致的候选；类型不一致时程序会给出明确提示，而不是静默混用。

这能避免研究者看到“未指定专家”却不知道去哪里设置。

### 9.9 推荐操作顺序

以 `Head -> Mandible` 为例：

1. 选中 `Head`。
2. 用 `Annotation Box` 画 Head 父级框。默认是自由比例；如果这批数据要用于固定父级 ROI 的小部位训练，再勾选 `Lock parent box ratio`。
3. 选中 `Mandible`。
4. 检查右侧父级上下文是否为 `Head`，必要时手动选择。
5. 如果已有 route expert，点击 `Annotate child from existing parent box / 用已有父框标注子部位` 起草。
6. 手工修准 Mandible polygon。
7. 在画布上方选择 `Loose Shrink Box`，画一个覆盖 Mandible 的松框。
8. 点击 `Run auto-shrink` 保存 trajectory。
9. 积累足够 trajectory 后，点击 `Train current child expert`。
10. 到 `Configure Route Expert` 里查看候选专家并决定是否指定到当前 route。

这条路线的好处是：你不需要离开主图，也不需要在局部坐标和全局坐标之间来回理解映射。

---

## 10. TIF 体数据工作台：切片、材料表与体分割后端

TIF Volume Workbench 是独立于 2D/STL 的体数据工作流。它适合连续切片、AMIRA/Avizo 标注数据、micro-CT、confocal 或其他能表示为 stack 的体数据。

最重要的一点是：

> TIF 的训练单位不是单张 polygon 图片，而是一个带 material-ID label volume 的 specimen 体数据。
>
> 当前 TIF 路径属于实验性扩展，灵感来自 AntScan 一类体数据集需求。它已经具备项目结构、导入、切片查看、材料表、工作编辑层和导出/后端契约，但稳定性和验证程度低于 2D/STL 主标注路线。

### 10.1 新建或打开 TIF 项目

常见入口：

- 启动中心右侧 `TIF Volume`
- `Workflow -> TIF Volume Workflow`
- `File -> New TIF Volume Project`
- `File -> Open Project` 打开 `project_type = tif_volume` 的项目 JSON

TIF 项目 JSON 只保存 specimen、路径、材料表、状态、后端记录和 provenance。真正的大体数据保存在项目旁边的 sidecar 目录里，不会塞进 JSON。

### 10.2 导入 TIF stack

入口：

- TIF 工作台内 `Import TIF stack`
- 或主菜单中的 TIF 导入入口

导入后会创建：

- `working/image.ome.zarr/`：当前用于显示和训练准备的工作体数据
- `labels/working_edit.ome.zarr/`：可编辑草稿层
- `material_map.json`：材料 ID、名称、颜色和是否可训练
- `working/import_report.json`：导入报告

普通 TIF stack 导入后不会自动拥有 `manual_truth`，也不会自动标记为可训练。因为它只是原始体数据，还没有人工确认的标签体。

### 10.3 导入 AMIRA 目录

AMIRA/Avizo 目录通常包含：

- raw `.tif`
- `.hx`
- `.resampled`
- `.labels`
- `.MaterialStatistics`
- `.surf`

当前适配重点是只读导入 AMIRA 已有标注。程序会优先使用 `.hx` 中连接的 `.resampled + .labels` 作为对齐的图像/标签对，而不是盲目把 `.labels` 叠到 raw TIF 上。

导入 AMIRA 后，已有标签会进入：

- `manual_truth`：原始人工真值层
- `working_edit`：可继续编辑的副本

原始 AMIRA 文件不会被写回或修改。

### 10.4 三个标签层一定要分清

| 层 | 含义 | 能不能直接训练 |
|---|---|---|
| `manual_truth` | 人工确认过的训练真值 | 可以 |
| `working_edit` | 当前正在编辑的草稿/修订层 | 不能直接当真值，需显式提升 |
| `model_draft` | 模型预测导入的草稿层 | 不能，必须人工复核 |

这对研究可信度很关键。模型预测、PDF 候选或临时 brush 修改都不能绕过人工确认直接变成训练真值。

### 10.5 Slice 浏览与材料表

TIF 工作台的核心操作是按 slice 浏览：

- 底部 slice 拖条用于快速查看连续帧。
- 亮度、对比度和 overlay opacity 用于看清灰度结构和标签叠加。
- 材料表控制 material ID、显示名、颜色和是否参与训练。
- 材料 ID `0` 作为背景受到保护。

如果某个 material ID 已经出现在标签体里，删除它会被阻止，避免标签体里留下无法解释的孤儿 ID。

### 10.6 3D 体预览与 GPU 清晰模式

显示模式切到 `三维体预览` 后，可以用只读 3D 视图检查整体形态和内部结构。它适合在真正切片编辑前寻找脑部、腺体或其他内部区域的大致空间位置。

基本操作：

- 左键拖动：旋转体数据。
- 右键拖动：平移画面，方向类似“抓住图像移动”。
- 滚轮：缩放，适合放大到头部或脑区。
- `重置 3D 视角`：恢复默认外部视角，并清空视点深度和近端剖切。

几个滑条的含义：

| 控件 | 什么时候用 | 注意 |
|---|---|---|
| 密度阈值 | 外层太厚或背景噪声太多时调高；内部淡结构消失时调低 | 它改变显示的灰度起点，不改变原始数据 |
| 渲染质量 | 停止拖动后想看更清楚时调高，3090 可尝试 1024 到 2048，必要时再往上 | 数值越高，上传到 GPU 的体纹理越大 |
| 光线采样 | 内部层次不稳定、细线断续时调高 | 主要增加 GPU 计算量，不一定明显增加显存 |
| 清晰模式 | 想看脑部、细小内部结构或原始 16-bit 灰度层次时打开 | 画面可能更有颗粒感，但比平滑模式更少“雾化” |
| 视点深度 | 想把观察点推进样本内部时调高 | 它只是移动视点，不切掉数据 |
| 近端剖切 | 外层组织挡住内部结构时调高 | 它从当前屏幕近端切掉一部分体数据 |

这个 3D 视图不能直接改标签。需要精确修订 material ID 时，仍然要回到 `切片复核`，在 `working_edit` 上用 brush 编辑。

如果右上角显示的 GPU 不是 RTX 3090，通常需要在 Windows 图形设置或 NVIDIA 控制面板里把 Python/TaxaMask 指定为高性能显卡。仓库里也提供了 `tools/start_antsleap_high_performance_gpu.ps1`，用于以高性能 GPU 环境变量启动程序。

### 10.7 Brush 编辑与提升为 manual_truth

TIF 的第一阶段编辑方式以 brush 为主：

- 选择材料 ID 后在当前 slice 上涂改 `working_edit`
- Ctrl 或对应擦除操作用于快速擦除
- 支持 slice 级 undo/redo
- 保存当前 `working_edit`
- 人工确认后，显式提升 `working_edit` 到 `manual_truth`

这里和 2D polygon 工作台不同。TIF 不需要用 Blink 训练局部专家，也不会走 2D 的 SAM 魔棒逻辑。

### 10.8 TIF 训练后端设置

入口：

- `Settings -> TIF Volume Model Settings`
- 或 TIF 工作台内的后端配置区域

这里设置的是体分割后端，不是 2D/STL 的 Locator/SAM。

常见字段包括：

- backend ID
- Python executable
- `prepare_dataset` command
- `train` command
- `predict` command
- export formats

命令里必须保留：

- `{contract}`
- 或 `{contract_json}`

这样 TaxaMask 才能把本次任务的项目路径、训练体、输出目录、label role 和 material map 以 contract JSON 形式交给外部脚本。

### 10.9 nnU-Net、MONAI 和自定义脚本怎么理解

TIF 后端不是被写死成 nnU-Net。当前设计是：

- nnU-Net v2 可以作为候选后端
- MONAI 可以作为候选后端
- 你自己的体分割脚本也可以作为后端

TaxaMask 负责把 train-ready 的体数据导出成后端能读取的布局，例如 nnU-Net 风格目录或 MONAI datalist；真正训练和预测由你配置的外部命令完成。

预测结果导回时会进入 `model_draft`，不会覆盖 `manual_truth`。如果你觉得预测质量可以用，也需要先人工检查，再决定是否把修订后的 `working_edit` 提升为训练真值。

### 10.10 TIF train-ready 检查

一个 TIF specimen 要进入训练，至少应满足：

- 已标记 train-ready
- 工作图像 sidecar 存在
- `manual_truth` sidecar 存在
- `material_map.json` 存在
- 图像和标签 shape 匹配
- 至少有一个可训练 material

如果 Agent 或后端提示“当前 TIF 不能训练”，通常先查这几项。

---

## 11. 模型设置、训练、推理与 AI 标注清理

### 11.1 Model Settings


当前设置分成三类，不要混在一起：

1. **General Settings / 通用设置**
   - 语言
   - 主题
   - 启动行为
   - 自动保存
   - 默认计算设备

2. **2D/STL Model Settings**
   - 当前项目的模型方案
   - 父部位标注方案
   - 子部位标注方案
   - 推理参数和 route 专家管理
   - 2D/STL 外部脚本后端

3. **TIF Volume Model Settings**
   - TIF 体分割后端默认配置
   - Python 解释器
   - prepare/train/predict 命令
   - 导出格式和后端校验

通用设置不再重复承担具体模型训练参数。具体训练配置放在对应工作流自己的模型设置里。

#### 2D/STL Model Settings 的五个页签

当前 `2D/STL Model Settings` 不再只是散落的训练参数，而是围绕“当前项目使用哪套模型方案”组织。

1. `Profile / 方案`
   - 新建、复制、删除和设为当前模型方案；
   - 修改方案显示名称和说明；
   - 保存后写入当前项目 JSON。

2. `Parent-part annotation / 父部位标注`
   - 显示当前父部位模型来源摘要；
   - 设置内置 Locator/SAM 训练参数、主定位结构、运行设备和父级框长宽比；
   - 真正切换父部位模型来源时，到 `Advanced Extensions / 高级拓展` 里改。

3. `Child-part annotation / 子部位标注`
   - 显示当前默认子部位专家来源摘要；
   - 设置 Blink 训练默认值和热力图 Blink 参数；
   - 真正切换默认子部位专家来源或配置自定义子部位脚本时，到 `Advanced Extensions / 高级拓展` 里改。

4. `Inference / 推理`
   - 设置主模型推理阈值、框扩张、噪声下限和 polygon 简化；
   - 设置 VLM 第一公里预标注目标部位；
   - 管理 `父部位 -> 子部位` route 专家。

5. `Advanced Extensions / 高级拓展`
   - 集中选择父部位模型来源：内置 `Built-in Locator + SAM` 或自定义父部位拓展；
   - 集中选择默认子部位专家来源：`ViT-B Blink Expert`、`Heatmap Blink Expert` 或自定义子部位拓展；
   - 配置父部位和子部位自定义脚本、命令和 manifest。

这样设计的目的，是让普通标注和训练参数留在父部位/子部位页，而“会改变整条训练或推理链路的高影响切换”集中在高级拓展里。用户不需要猜到底该在方案页、父部位页还是子部位页切换模型来源。

#### 模型方案是什么

模型方案是保存在当前项目 JSON 里的 2D/STL 模型配置快照。它记录：

- 父部位用内置 Locator/SAM 还是外部父部位后端；
- 主定位结构、训练参数、父级框长宽比；
- 子部位默认使用 ViT-B Blink、热力图 Blink 还是外部 Blink；
- 推理阈值和 VLM 预标注目标部位。

这对研究流程的意义是：同一个项目可以保留多套方案，例如“快速验证用内置热力图 Locator + 热力图子部位专家”和“外部模型实验方案”。切换当前方案后，`Auto (Current)`、`Batch (All)`、子部位训练和审计日志都会使用当前方案，而不是靠你记住一堆分散参数。

旧项目打开时会自动补一个默认方案 `builtin_heatmap_default`，并把已有的主定位结构、父级框比例和 Blink 默认参数同步进去。

#### 2D/STL 训练参数常见项

以下内容属于 `2D/STL Model Settings`：

- Runtime Device
- Epochs
- Batch Size
- Learning Rate
- Weight Decay
- Main Locator Parts / 主定位结构
- AI Multimodal Pre-Annotation / AI 多模态预标注
- Parent Box Aspect Ratios / 父级框长宽比
- Blink Expert Training Defaults / Blink 专家训练默认值
- Heatmap Blink Parameters / 热力图 Blink 参数
- External Blink Backend / 外部 Blink 后端

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
- 细部位可以后续用 SAM、主工作台子部位标注区、Blink 路由专家或外部脚本后端继续精修

举例：

- 蚂蚁模板通常是 `Head / Mesosoma / Gaster`
- 植物项目可以只把 `Leaf / Flower / Fruit` 这类主结构放进去
- 刚毛、气孔、微小脉序细节这类目标，不建议随手塞进主 Locator，除非你的模型和训练数据本来就是为它们设计的

如果你改了主定位结构，旧的 Locator 权重可能不再匹配当前项目。程序会提醒你重新训练或选择匹配的新模型。

#### AI Multimodal Pre-Annotation / AI 多模态预标注

这里控制 `VLM预标注` 和 `VLM批量预标` 会把哪些项目部位交给多模态大模型预标注，以及 `VLM批量预标` 的批量图片范围。

它和 `Main Locator Parts` 是两件事：

- `Main Locator Parts` 决定内置 Locator 训练哪些主结构；
- `AI Multimodal Pre-Annotation` 决定 VLM 先帮哪些已有部位画草稿框。

实际使用建议：

- 选择你希望 VLM 预标注的具体部位；
- 小范围试用时直接在工作台点击 `VLM预标注`；
- 批量处理可以选择所有导入图像，也可以只选择左侧列表里的某个图片分组，例如只跑 `Split Crops`；
- `VLM API Concurrency / VLM API 并发数` 默认是 `1`，用于保护限速 key 和账单。你的服务商明确允许并行请求时可以调高；如果不确定，保持默认更稳；
- 批量运行前程序会二次确认，包括将要处理的图片数量和分组名称；
- 运行报告、VLM 输入图和 raw response 会保存在项目同级 `vlm_preannotation/` 目录。

批量运行期间可以从进度窗口停止任务。停止不是强行杀掉已经发出的网络请求，而是停止继续派发剩余图片，并等待已发出的请求收尾。这样既能避免一个错误设置跑完整个几千张任务，也能尽量保护项目 JSON、报告文件和 API 响应记录不留下半写入状态。

所有 VLM/SAM 结果默认都是草稿。训练预检会跳过未复核的 `Auto-Annotated` 草稿，防止未经人工确认的框和 polygon 污染训练集。重新运行 VLM 时，程序会替换未确认 AI 草稿，但保留人工标签和已经确认通过的标签。

#### Parent Box Aspect Ratios / 父级框长宽比

这组设置控制主工作台里父部位 `Annotation Box` 的默认比例。例如蚂蚁项目中常见默认是：

- `Head`: `1 : 1`
- `Mesosoma`: `4:3`
- `Gaster`: `4:3`

界面里直接按“宽 : 高”输入，例如 `4 : 3`，不需要把比例先在脑子里换算成 `1.3333`。如果某个部位暂时不需要固定比例，可以留空。

固定长宽比默认不会自动启用。只有你在主工作台右侧勾选 `Lock parent box ratio / 锁定父级框比例` 时，这些比例才会影响父部位的 `Annotation Box` 和父部位的 `Box Prompt (SAM)`。子部位正式框和收缩松框仍然是自由比例。

这对研究流程的意义是：父部位框可以保持稳定视野，后续子部位专家训练时不必把一个随手画出的任意形状 ROI 强行变形到固定训练尺寸。

#### Blink Expert Training Defaults / Blink 专家训练默认值

这组参数不是主模型训练参数，而是主工作台子部位标注区训练细部位专家时的默认值。

它包括：

- Default Blink Epochs
- Default Blink Batch Size
- Default Blink Learning Rate
- Default Blink Weight Decay
- Default Blink Input Size

保存后，主工作台中的 `Train current child expert` 会使用这些默认值。

实际研究中，如果某个细部位专家效果不好，优先检查：

- trajectory 数量是否太少
- 文献缩略图是否太糊
- Learning Rate 是否过大或过小
- Input Size 是否需要提高
- 当前路由上是否仍指定着旧专家，而不是刚训练的新候选

Blink 训练方案也是这里的重要参数。快速验证时可以先保留方案一；如果你怀疑外视角中目标缺失会干扰训练，可以试方案二；如果你希望模型先从父级全图学粗定位，再学局部收紧，可以试方案三。建议一次只改一个变量，并用 `训练结果` 浏览器回看验证图和报告。

#### Heatmap Blink Parameters / 热力图 Blink 参数

热力图 Blink 是新增的子部位专家后端。它的输入仍然是父部位框内的局部图像，但学习目标不是 ViT-B 的直接框回归，而是：

- 子部位中心点热力图；
- 子部位框宽高回归。

它适合先做较容易起步的小部位验证，例如 `Eye`、`Mandible` 这类在父部位内位置相对稳定、标注成本不高的结构。当前参数包括：

- `Heatmap Input Size`：父 ROI 缩放后的训练尺寸；
- `Heatmap Sigma`：中心点热力图峰值的扩散范围；
- `WH Loss Weight`：宽高回归损失权重；
- `Center Loss Weight`：中心点热力图损失权重。

研究操作上，如果你只是要快速跑通流程，热力图 Blink 往往比直接追求复杂小模型更容易排查：它的输出可以理解为“先找中心，再估计框大小”。但它仍然需要父级框和足够的 trajectory 数据。

#### Child Custom Extension / 子部位自定义拓展

这是子部位 route 的外部脚本入口，现在主要在 `Advanced Extensions / 高级拓展` 里配置。它和父部位自定义拓展不同。

它只负责这个任务：

```text
已有父部位框 + 当前图片 + parent/child 名称
-> 外部脚本返回子部位框
-> TaxaMask 用这个框调用本地 SAM 生成可复核草稿
```

命令中同样需要保留 `{contract}` 或 `{contract_json}`。契约文件在：

`docs/contracts/external_blink_backend_contract_v1.md`

第一版重点支持 `predict_child` 推理。外部脚本不应该直接修改项目 JSON，也不应该把结果写成人工真值。

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

#### 2D/STL Advanced Extensions / 高级拓展

这是一个高级入口，适合有自己模型训练或推理脚本的用户。它集中管理两类高影响设置：

- 父部位模型来源：内置 Locator/SAM 或自定义父部位脚本；
- 默认子部位专家来源：ViT-B Blink、热力图 Blink 或自定义子部位脚本。

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

如果当前模型方案的父部位后端选择为 `External Parent Backend`，或者兼容旧设置里模型后端选择为 `External Script Backend`：

- `Train Models` 不会启动内置 Locator/SAM 训练线程
- `Auto (Current)` 和 `Batch (All)` 不会调用内置 Locator/SAM 推理
- 程序只会创建 external run、写 contract、运行外部脚本、读回结果

这点很重要。外部后端不是“在内置模型后面再加一步”，而是让外部训练/推理在这次任务里接管模型部分。

外部父部位训练和外部批量推理都会放在后台任务里运行。也就是说，长时间训练脚本或逐张预测脚本运行时，TaxaMask 主界面仍应保持可操作，并会阻止你在任务未完成时直接关闭程序。需要注意的是，任意外部脚本的“安全取消”需要外部后端自己支持；TaxaMask 不会随意强杀未知训练脚本，以免留下半写入模型或日志。

如果只是想给子部位 route 使用外部模型，不要把父部位模型来源切成自定义父部位拓展；应在高级拓展里配置子部位自定义拓展，并在 route 专家中指定 `external_blink`。

2D/STL 外部脚本契约说明在：

`docs/contracts/external_backend_contract_v1.md`

TIF 后端不使用这份 2D 契约。TIF 使用独立的 `ant3d_tif_backend_contract_v1`，配置入口在 `TIF Volume Model Settings`。

### 11.2 Train Models

工作台里的 `Train Models` 训练的是主模型链，而不是 Blink 微观专家。

它会基于当前项目里已有的标注数据，做：

- Locator 训练
- SAM 分割器训练

现在它会读取当前模型方案里的父部位后端。如果当前方案是内置父部位后端，就训练 Locator/SAM；如果当前方案是外部父部位后端，就按外部后端契约运行你配置的训练命令。

内置父部位训练成功后，当前模型方案会记录本次生成的 Locator / SAM 权重文件名。这样以后导出数据集或排查模型效果时，可以知道这套方案当时绑定的是哪批父部位模型。

如果勾选 `Train Locator only (skip SAM)`，本次训练只训练 Locator，不训练 SAM / parts 分割器。

这个选项适合：

- 基础 SAM 已经能给出足够好的 polygon
- 你当前主要想提高主结构定位能力
- 你想减少一次训练的耗时和显存占用

训练开始后可以点击 `Stop Training`。它不是强制杀进程，而是在当前训练 batch 或 epoch 边界安全停止，尽量避免留下半写入状态。

主工作台右侧训练进度栏现在是父部位训练和子部位专家训练共用的进度区。标题行里的 `Training Results / 训练结果` 会打开历史训练结果浏览器：

- 父部位报告来自 Locator/SAM 主训练；
- 子部位报告来自 ViT-B Blink 或热力图 Blink 专家训练；
- 浏览器只负责统一列出历史报告，详情仍分别打开原来的父部位训练报告窗口或 Blink 训练报告窗口；
- 列表中会显示类型、目标部位、后端、Blink 训练方案、验证样本数、时间和报告文件夹。

这对研究复盘很实用：你可以先从统一列表找到某次训练，再进入对应详情看指标图、验证样本和具体失败案例，而不用记住父部位报告和子部位报告分别保存在哪个 `experiments/` 子目录里。

#### 它需要什么

- 至少有已标注图片
- 结构标签稳定
- 训练预检中至少有可用于 Locator 或 SAM / parts 的样本

### 11.3 Auto (Current)

对当前图片跑一轮推理。

关键点：

- 主要用于补“还没有标注的部位”
- 不会直接覆盖你已有的人工结果
- 使用当前模型方案里的父部位后端和推理参数
- 推理日志会记录模型方案、父部位后端和 route 后端，方便以后知道这批 AI 草稿是哪套方案产出的

### 11.4 Batch (All)

对当前项目里尚未标注的图片批量推理。

它适合：

- 先批量铺初稿
- 再人工补和进 Blink 精修

批量推理和当前图推理一样读取当前模型方案。换句话说，如果你刚切换了方案，批量前最好先用 `Auto (Current)` 在少量图片上确认效果，再跑全项目。

### 11.5 Clear AI Labels

这个按钮适合在你“试过自动推理，但决定推倒这轮 AI 初稿”时用。

它会清掉被标为 `Auto-Annotated` 的自动标签结果，但不是简单粗暴地把全部人工成果一起清空。

当前版本会先弹出范围选择：

- `All project images / 全部项目图片`：清除全项目 AI 标签；
- `Images in selected list group / 指定图片分组`：只清除某个左侧图片分组里的 AI 标签。

第二个确认窗口会说明将影响多少张图片、多少个 AI 标签。对于几千张图项目，建议优先按分组清理，例如只清 `Split Crops` 或某个自定义复核分组，避免把已经复核过的其他部分一起清掉。

### 11.6 设置区域的鼠标滚轮保护

设置页里的关键数字参数和下拉项已经做了滚轮保护。也就是说，你用鼠标滚轮浏览设置页面时，鼠标经过某个数值框、滑块或下拉框，不会悄悄把 VLM 并发、Blink 自动收缩步数、验证报告比例或 PDF 设置选项改掉。

如果要修改这些参数，请先点击控件，再用键盘输入、拖动滑块或明确选择下拉项。这个设计是为了避免大批量训练、预标注和导出前，因为一次无意滚轮导致参数被改动。

---

## 12. 导出数据集：Multimodal / COCO / YOLO 与 TIF 训练体

路径：`File -> Export Dataset`

导出时会弹出进度窗口，显示当前正在处理的图片或写出的文件。导出在后台线程中执行，主界面不会因为大项目导出而看起来卡死。

导出完成后，TaxaMask 会自动打开本次数据集所在文件夹，并弹出导出样本数提示。这样你可以立刻检查 `images/`、`labels/`、`annotations.json`、`multimodal_dataset.jsonl` 或 `model_profile_summary.json` 是否已经写出。

如果导出还没有完成又再次点击导出，程序会提示“数据集正在导出中”，避免同一目录里同时写入两套半成品。

### 12.1 Multimodal


适合：

- 后续喂给多模态模型
- 需要同时保留局部裁剪图、全局图和文本描述

输出内容包括：

- `images_global/`
- `crops/`
- `multimodal_dataset.jsonl`
- `model_profile_summary.json`

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

`model_profile_summary.json` 是这次导出的模型方案审计摘要。它记录当前 active profile、父部位后端、子部位默认后端、推理参数和 route 专家后端/manifest 摘要。它不保存 API key，也不会写入外部命令全文，只保留复现实验和排查结果所需的模型线索。

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

### 12.2 COCO

适合：

- 标准检测/分割训练

输出内容包括：

- `images/`
- `annotations.json`

优先使用手工框；没有手工框时，才从 polygon 自动推导 bbox。

COCO 类别的 `supercategory` 默认使用 `biological_structure`。如果项目模板或项目配置提供了其他值，会按项目配置写出。蚂蚁模板可以继续使用 `ant_part` 作为明确的蚂蚁示例，但通用项目不会被默认写成蚂蚁部位。

### 12.3 YOLO

适合：

- YOLOv8 分割训练

输出包括：

- `images/`
- `labels/`
- `dataset.yaml`

### 12.4 TIF 训练体导出

TIF 的导出不走普通 2D 的 COCO/YOLO 逻辑。它导出的是体数据和 material-ID label volume。

常见导出包括：

- OME-TIFF
- plain multi-page TIFF
- NRRD
- MHA
- NIfTI `.nii`
- nnU-Net 风格目录
- MONAI datalist

导出时会写入 manifest，例如：

- `tif_training_export_manifest.json`
- `nnunet_manifest.json`
- `monai_manifest.json`

这些 manifest 的作用是说明：

- 哪个 specimen 被导出
- 图像和标签 shape 是什么
- label role 是不是 `manual_truth`
- material map 当时是什么
- 输出文件分别在哪里

这对后续训练和审计很重要，因为体分割模型训练失败时，你需要能追溯到底是数据 shape、材料 ID、导出格式，还是外部脚本配置出了问题。

### 12.5 这里一个很重要的研究逻辑

导出不是只是“换个格式”。

它实际上是在决定：

- 你要保留多少语义信息
- 数据以后是给检测、分割，还是多模态模型
- 后续别人是否能审计你这份数据从哪里来

所以导出格式应该根据后续用途选，而不是随便点一个能出文件的就行。

---

## 13. 恢复边界、常见误区与排错建议

### 13.1 最常见误区 1：以为 PDF accepted 就等于正式可用真值

不是。

PDF 侧 accepted 更多表示：

- 在当前筛选/提取逻辑下，它被认为是高价值候选

但它离正式标注真值还有一层距离。

### 13.2 最常见误区 2：以为 Auto-Shrink 就等于正式 polygon 已经修好了

不是。

- Auto-Shrink = 根据已经确认的 polygon 和收缩松框保存 trajectory
- 正式 polygon = 你在主工作台画布上看到并保存的当前子部位标注

当前主工作台合并版不再要求你点 `Apply to Global`。但 Auto-Shrink 仍然不是“自动修好 polygon”的按钮，它保存的是训练经验。

### 13.3 最常见误区 3：以为 Train Expert Model 会拿项目所有标注一起训练

不是。

它只吃：

- 当前部位
- trajectory-backed 样本

### 13.4 最常见误区 4：以为图片搬盘后 GUI 会自动修所有问题

不是。

程序能做的是：

- 通过 `File -> Check / Relocate Project Images` 统计缺失图片并预览可修复路径
- 按你在本地配置里写好的 `known_relocated_roots` 映射，尝试把旧路径片段解析到新图片库根目录

程序不能做的是：

- 自动修复语法损坏的项目 JSON
- 在同名图片有多份时替你猜哪一张才是正确标本图

### 13.5 最常见误区 5：以为 PDF 侧已经有完整候选审批工作台

现在还没有。

当前现实是：

1. 在数据库里看候选
2. 看 figure 证据和 review 状态
3. 人工决定哪些图真正进入标注项目

这一步仍然是半人工流程，不是完全前端审批流水线。

### 13.6 最常见误区 6：以为 TIF 的 model_draft 可以直接训练

不是。

`model_draft` 是模型预测草稿。它可以帮助你加速检查和修订，但不能直接作为训练真值。

稳妥流程是：

1. 导入预测为 `model_draft`
2. 人工检查和修订到 `working_edit`
3. 明确确认后提升到 `manual_truth`
4. 再作为 train-ready specimen 参与训练

### 13.7 建议的稳妥使用习惯

1. 大批量 PDF 运行时尽量开启：
   - Auto Split Failed Batches
   - Resume Interrupted Runs
   - Isolate V2 Runs
2. 任何重要标注阶段结束后都主动保存项目
3. 做子部位精修时，先确认父级上下文和父级框，再画子部位 polygon
4. 要训练 Blink 专家时，优先关注 trajectory 数量，而不是只看 polygon 数量
5. 搬盘后先用 `Check / Relocate Project Images` 检查图片路径，再判断是不是 JSON 文件本身损坏
6. TIF 预测结果先当作 `model_draft`，不要直接当成 `manual_truth`

---

## 14. 按钮速查表

### 14.1 主工作台

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
| VLM预标注 / VLM Pre-Label | 多模态模型生成当前图第一公里草稿框 | 只影响当前图 |
| VLM批量预标 / VLM Batch Pre-Label | 多模态模型批量生成第一公里草稿框 | 全部导入图像，或左侧列表中的指定分组 |
| Accept current image AI drafts | 一键通过当前图像已有 AI polygon 草稿 | 只影响当前图像，不确认纯框草稿 |
| Train Models | 训练主模型 | 训练 Locator + SAM |
| Stop Training | 合作式停止主模型训练 | 训练控制 |
| Train Locator only (skip SAM) | 本次只训练 Locator | 训练策略 |
| Clear AI Labels | 清理 AI 初稿 | 删除 Auto-Annotated 标签 |
| Ask Agent | 发送主标注现场的短诊断索引卡片 | 当前图像、部位、日志和 Agent 路由 |
| Annotation Box | 绘制正式标注框 | 父部位框 / 子部位框 |
| Lock parent box ratio | 父部位框按设置比例锁定 | 影响父部位 Annotation Box 和父部位 Box Prompt (SAM) |
| Parent context | 指定当前子部位父级 | 记忆 child -> parent |
| Configure Route Expert | 打开当前 `父部位 -> 子部位` 路由专家配置 | 项目 route manifest |
| Annotate child from existing parent box | 用已有父框和路由专家起草子部位 | 当前子部位草稿 |
| Loose Shrink Box | 绘制自动收缩起点框 | `shrink_loose_boxes` |
| Run auto-shrink | 生成并保存 trajectory | Blink 训练数据层 |
| Train current child expert | 训练当前路由的子部位专家 | Blink 专家候选模型 |

### 14.2 兼容 Blink 回退界面

| 按钮 | 作用 | 影响层 |
|---|---|---|
| Sync from Workbench | 从工作台重载当前图状态 | 会话层 |
| BLINK SWITCH | 点击后切换观察/遮罩模式 | 显示层 |
| AUTO-ANNOTATE DRAFT | expert 框 → 基础 SAM 草稿 | 局部起稿层 |
| Draw Box (For SAM Draft) | 手工提示框 → 基础 SAM 草稿 | 局部起稿层 |
| EXECUTE AUTO-SHRINK | 生成并保存 trajectory | 训练数据层 |
| APPLY TO GLOBAL | 把兼容局部会话结果写回正式项目 | 正式标注层 |
| TRAIN EXPERT MODEL | 训练当前部位专家 | Blink 专家模型层 |
| STOP TRAINING | 合作式停止 Blink 专家训练 | 训练控制 |
| Appoint to Current Route | 将候选专家指定到当前 `父部位 -> 子部位` 路由 | 路由配置层 |
| Edit Note | 为候选专家添加展示备注 | 人工记忆标签，不改文件名和路由 |

普通 2D/STL 标注现在优先使用 14.1 中的主工作台子部位标注区按钮。这个兼容 Blink 回退界面主要用于旧项目检查、开发验证或特殊排错。

### 14.3 TIF 工作台

| 按钮 / 控件 | 作用 | 影响层 |
|---|---|---|
| Import TIF stack | 导入连续 TIF stack | 创建 working image 与 working_edit |
| Import AMIRA Directory | 只读导入 AMIRA/Avizo 数据 | 创建 manual_truth 与 working_edit |
| Slice slider | 浏览连续切片 | 显示层 |
| Display mode: 3D volume | 只读旋转查看体数据 | 观察层，不改标签 |
| Render quality / Ray samples / Clarity mode | 提高 GPU 体预览清晰度 | 观察层，增加显存或计算负载 |
| Inside depth / Front cut | 进入体内或切掉近端遮挡组织 | 观察层，不写回数据 |
| Material map | 编辑材料 ID、名称、颜色和 trainable 状态 | TIF 标签语义层 |
| Save working edit | 保存当前可编辑标签层 | `working_edit` |
| Promote working edit to manual truth | 将人工确认后的编辑提升为训练真值 | `manual_truth` |
| Export train-ready TIF volumes | 导出可训练体数据 | 后端训练交接 |
| Prepare / Train / Predict backend | 调用 TIF 外部后端 | external TIF run |
| Ask Agent | 带上下文回到 Agent Center | 问题诊断与配置辅助 |

### 14.4 PDF 处理页

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
| Open Database File | 选择并浏览具体 `.db` 数据库 | 人工复核 |
| Export Raw JSONL | 导出粗提取数据集 | 粗 JSONL 数据 |

### 14.5 Model Settings

| 按钮 / 控件 | 作用 | 影响层 |
|---|---|---|
| General Settings | 设置语言、主题、启动行为和默认设备 | 全局使用习惯 |
| 2D/STL Model Settings | 设置模型方案、父部位后端、子部位后端、推理和 2D 外部后端 | 2D/STL 工作流 |
| TIF Volume Model Settings | 设置 TIF 外部后端和导出格式 | TIF 工作流 |
| Profile / 方案 | 新建、复制、删除或切换当前模型方案 | 当前项目 JSON 的 `model_profiles` |
| Parent-part annotation | 设置父部位 Locator/SAM 或外部父部位后端 | 主结构定位和父级框 |
| Child-part annotation | 设置 ViT-B Blink、热力图 Blink 或外部 Blink 默认后端 | 子部位 route 专家训练/推理 |
| Inference | 设置推理阈值、VLM 预标注和 route 专家管理 | AI 草稿和父子 route |
| Main Locator Parts | 选择内置 Locator 学哪些主结构 | 主定位器训练范围 |
| Validate External Backend | 校验外部脚本后端配置 | 检查外部后端 ID 和命令占位符 |
| Validate External Blink Backend | 校验外部 Blink 子部位后端配置 | 检查 external_blink ID 和命令占位符 |
| Validate TIF Backend | 校验 TIF 后端配置 | 检查 TIF backend ID、导出格式和命令占位符 |
| Ask Agent | 发送当前设置页的短诊断索引卡片 | Agent 根据路由表定位大模型对接文件、源码和契约 |
| 外部后端适配确认 | Agent 修改自定义模型对接脚本或配置前确认 | 只放行外部模型适配区，不放开 TaxaMask 源码 |
| 源码开发模式确认 | Agent 修改 TaxaMask 程序源码前强确认 | 用户知情后才允许改程序本身 |

---

## 15. 标准流程模板：照着做的一整套操作路线

这一节不是再解释按钮定义，而是把前面已经讲过的功能拼成**可以直接照着走的标准流程**。你以后带别人时，如果对方不想先理解全部原理，也可以先按这些模板操作；等做完一轮，再回头看前面的细节解释，会更容易消化。

---

### 15.1 标准流程模板 A：从原始 PDF 到“进入标注项目的候选图片”

这个模板适合：

- 你手里有一批原始 PDF
- 你想先快速找出可能真正值得标注的图
- 你不想一开始就把全部图片扔进项目里

#### 推荐步骤

**步骤 1：准备 API 与筛选方案**

1. 从启动中心让 Agent 准备 PDF 任务，或通过 `File -> Open PDF Evidence Tools` 打开 PDF 工具
2. 填好 `Text LLM API`
3. 如果要启用真实多模态验证，再填好 `Multimodal LLM API`
   - 如果你的同一个服务和模型支持图像输入，可以勾选 `Use same provider as Text LLM`
   - 如果文本筛选和图像复核用不同模型，就取消勾选并单独填写
4. 如果你以后还会重复用这套配置，点击 `Save API Settings`
5. 在 `Select Logic Profile` 里选定 PDF 文献筛选方案；如果要试新的筛选逻辑，先去 `Advanced Logic Settings` 里另存为一个新方案
6. 在 `Figure Extraction / Review Profile` 里选定图文提取/复核方案；蚂蚁默认方案是宽松分类学图版复核，不再要求三视图齐全；如果要适配其他类群，先用 `Advanced Figure Settings` 复制模板再修改
7. 在 `Part Description Profile` 里选定纯文本部位描述抽取方案；如果要适配其他类群，先复制 `part_description_configs/` 里的模板，改目标类群、部位桶和文本整理提示词

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
2. 选择结果文件夹，并填写数据库文件名
3. 确认 `Figure Extraction / Review Profile` 是这次任务需要的类群和图版规则；默认蚂蚁方案会保留单一物种/单一分类单元的整体图、多视角图和局部诊断结构图，但拒绝多物种比较图
4. 如果你希望更可靠地区分“真正符合目标图版规则的 figure”和“只是看起来像目标图的东西”，建议启用多模态验证
5. 点击 `Start Extraction Pipeline`

**这里最重要的判断点**

如果提取前弹出“mock/default review”确认框，你必须意识到：

> 这轮提取结果更偏“待复核候选”，不是“可直接信任的真 accepted”。

**步骤 5：在数据库里做人类复核**

1. 点击 `Open Database File`
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

### 15.2 标准流程模板 B：从新项目开始，做一轮正式标注与主模型训练

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
2. 打开 `Settings -> 2D/STL Model Settings` 调整训练与推理参数，并确认 `Main Locator Parts` 只包含这轮要让内置 Locator 学习的主结构
3. 点击 `Train Models`
4. 在训练预检里确认可训练图片数量、结构标签覆盖和排除原因
5. 看训练报告和验证图

训练结束后，也可以点击右侧训练进度栏的 `训练结果`，从历史列表中重新打开这次父部位训练报告。这个入口不会把父部位和子部位报告混成一个详情页，只是把历史报告集中列出来，方便你复核和比较。

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

### 15.3 标准流程模板 C：在主标注工作台做细部位精修、积累 trajectory 并训练专家

这个模板适合：

- 大部位已经有了较稳定的定位和标注
- 你要开始做小结构精修
- 你希望逐步积累 Blink 专家训练数据

#### 推荐步骤

**步骤 1：先在工作台准备好进入条件**

1. 选中一张图片
2. 在 `Structures / 结构标签` 里先选中父部位，例如 `Head`
3. 用 `Annotation Box` 画父级框；默认自由比例，需要固定父级 ROI 训练时再勾选 `Lock parent box ratio`
4. 再选中这次要精修的子部位，例如 `Mandible`

**为什么这一步必须先在工作台做**

因为子部位标注现在的正确定位不是“从整张图重新开始找”，而是：

> 基于已有大部位或已有 ROI，进入局部精修。

**步骤 2：确认父级上下文和路由**

1. 看右侧 `Child-part annotation / 子部位标注`
2. 确认 `Current route` 是否类似 `Head -> Mandible`
3. 如果父级不对，在 `Parent context` 下拉框里改成正确父部位
4. 如果 route expert 未指定，点击 `Configure Route Expert`

**推荐理解方式**

- 子部位 = 这次真正要修谁
- 父级上下文 = 你通过哪个大部位框给它提供局部视野

不要把这两个概念混成一个。

**步骤 3：在主画布里做子部位精修**

你可以：

- 如果当前 route 已经有专家，用 `Annotate child from existing parent box / 用已有父框标注子部位` 先起草
- 如果你更相信自己的 prompt 框，用 `Box Prompt (SAM)` 先给基础 SAM 起草
- 用 `Draw Polygon` 精修当前目标部位
- 用 `Loose Shrink Box` 画自动收缩松框

**推荐顺序**

1. 先决定怎么起草：
   - route expert 草稿，或
   - 手工框给 SAM 草稿
2. 再把目标部位 polygon 修准
3. 再画一个相对宽松的外框
4. 再用 auto-shrink 生成轨迹

**步骤 4：生成 trajectory**

点击 `Run auto-shrink`

满足前提时，它会：

- 生成收缩轨迹
- 立即把 trajectory 写进项目

#### 这里最关键的研究逻辑

这一步的意义是：

> 你在保存“专家该怎样从松框一步步收缩到目标结构”的经验。

它不是在保存最终真值本身，而是在保存**训练过程样本**。

**步骤 5：确认正式标注已经在主画布中**

当前合并版没有独立局部会话，也不需要 `APPLY TO GLOBAL`。你在主画布里修准的 polygon 和正式标注框，本来就是项目的全局坐标标注。

你需要确认的是：

- 当前子部位 polygon 已经修准
- 当前子部位正式框不是误用的收缩松框
- 项目已经自动保存或你已经手动保存

#### 最稳妥的习惯

- 轨迹生成后，不要想当然地以为 polygon 也被自动修好了
- 收缩松框只是训练起点，不是正式标注框

**步骤 6：积累到一定量后训练当前部位专家**

点击 `Train current child expert`

它当前只会使用：

- 当前项目
- 当前部位
- trajectory-backed 样本

如果这次要做正式对比实验，可以先在 `2D/STL Model Settings -> Child-part annotation` 中选择 Blink 训练方案：方案一保留原全图/内视角/外视角随机，方案二去掉外视角，方案三先全图后内视角。训练完成后用右侧 `训练结果` 浏览器打开对应子部位报告，重点看验证样本里蓝/青色预测框和绿色目标框是否稳定贴近。

#### 什么时候适合开始训练专家

不是“刚有两三张就急着训”。

更稳妥的判断标准是：

- 这个部位已经积累了多张不同个体、不同姿态、不同质量条件下的 trajectory
- 你已经能稳定地用 Blink 完成这个部位的精修

#### 这条流程最后得到的是什么

你会得到两类东西：

1. **正式项目标签**（主画布 polygon / annotation box）
2. **Blink 专家训练材料与专家模型**（通过 `Run auto-shrink` + `Train current child expert`）

这两者不要混成一回事。

---

### 15.4 标准流程模板 D：当项目搬盘、路径变化或运行中断时，应该怎么稳妥处理

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
2. 如果只是图片库整体搬到了新位置，打开项目后运行 `File -> Check / Relocate Project Images`
3. 选择新的图片库根目录，核对预览里的旧路径和新路径
4. 确认无误后应用重定位并保存项目

**为什么要立刻保存一次**

因为这样能尽快把当前可用路径状态稳定下来，减少后面继续靠兜底逻辑或手工配置的次数。

#### 场景 3：报 JSONDecodeError

这时不要优先怪路径。

正确判断顺序是：

1. JSON 能不能被正常解析？
2. 如果不能，先修 JSON 语法
3. 语法修好以后，再看图片路径是不是还有效

#### 场景 4：子部位精修到一半，切图前怕丢

推荐操作：

1. 先判断这次改动是“正式 polygon/box”还是“trajectory 训练经验”
2. 正式 polygon/box 在主工作台全局坐标里保存
3. trajectory 需要先画收缩松框，再执行 `Run auto-shrink`
4. 重要标注阶段结束后主动保存一次项目

---

## 16. 结语：最值得你一直记住的三句话

1. **PDF 侧是在找候选，标注侧才是在造真值。**
2. **Blink Auto-Shrink 是存训练经验，主画布上的 polygon/annotation box 才是正式标注。**
3. **路径搬家可兜底，坏 JSON 不会自己变好。**

如果你后面继续扩展这份手册，下一步最值得补的不是再堆功能说明，而是：

- 你们团队内部约定的“accepted / review / 正式入项目”判断标准
- 不同研究任务（筛文献 / 建项目 / Blink 精修）对应的最小数据质量标准
