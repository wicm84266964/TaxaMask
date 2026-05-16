# Ant 3D Workbench 需求对齐记录

> 暂定名称：**Ant 3D Workbench**
>
> 英文定位：
> Open-source 3D annotation for ant morphology: STL surface labeling, TIF volume segmentation, and model-assisted curation for AntScan-style micro-CT datasets.

## 1. 核心定位

Ant 3D Workbench 的核心目标，是把 AntScan-style 的 STL/TIF 三维形态数据转化为可标注、可复核、可训练、可自动预标注、可持续迭代的研究资产。

主路线不是一次性标完，而是：

```text
人工标注
-> 人工复核
-> 训练一个粗糙自动标注模型
-> 用模型预标注更多数据
-> 人工修正与复核
-> 再训练
-> 反复迭代，直到模型达到可用的自动标注能力
```

## 2. 项目类型

STL 和 TIF 是两个独立的 project/workspace 类型，不塞进同一个大 JSON。

原因：

- STL 研究外部形态，核心数据是 STL 渲染出来的多视角 2D 高分辨率图片。
- TIF 研究内部结构，核心数据是连续切片和体数据 label field。
- 两者虽然可能来自同一只蚂蚁，但标注体系、训练方式、复核方式和模型后端都不同。
- 分开保存可以避免 project JSON 过大、过乱、难维护。

## 3. 左侧栏组织方式

左侧栏按 specimen 编号组织，但展示内容随当前模式变化。

STL Mode：

```text
Specimen_01-0101-02
├─ view_1
├─ view_2
├─ ...
└─ label / review status
```

TIF Mode：

```text
Specimen_01-0101-02
├─ TIF stack / working volume
├─ slice navigation
├─ label volume state
└─ review / train-ready status
```

specimen 编号是固定项目编号，不是物种名。物种信息通过总表查询，不作为 STL 训练输入。STL 模型训练目标是认部位，不是认物种。

## 4. STL Project 需求

STL Project 第一阶段不是直接在 3D mesh 上涂色，而是处理已经从 STL/mesh 渲染出来的多视角 2D 图片。

已确认：

- 多视角图由批量导出生成，视角类型固定，约 10 个视角。
- 文件名中包含 specimen 编号和视角名，导入时按命名规则自动分组。
- 渲染图最高可到 64K，是高价值训练图，不是 PDF 压缩图。
- STL 训练框架尽量不大改，继续复用现有 Labeling Workbench、Blink、Locator/SAM、route-appointed expert 和模型迭代逻辑。
- STL 训练可以按图片随机切分训练/验证/测试；如需测试全新个体，可额外导入新的 specimen 做独立验证。
- STL label 类别和 TIF label 类别完全独立。

## 5. TIF Project 需求

TIF Project 是新模块，不复用现有 polygon mask 工作台。

已确认：

- 原始输入第一阶段支持一个完整 TIF stack 文件。
- TIF 模块不能写死为 micro-CT，也要能表示共聚焦等切片 TIF 数据。
- 现有 AMIRA 标注的共聚焦蚂蚁脑数据集是重要兼容目标。
- TIF 标注方式采用 AMIRA-style label field：每个像素/体素保存一个 material ID。
- 用户界面按单张 slice 逐层标注，但训练有效单位通常是完整标注的一整个 volume。
- TIF 不需要 Blink 小部位辅助。
- TIF 不继承 STL 的 Head / Mesosoma / Gaster 三主部位定位器逻辑。

## 6. AMIRA 数据适配

根据当前样例目录，已有数据包含：

```text
raw .tif
.hx
.labels
.MaterialStatistics
.surf
.resampled
```

第一阶段按这个样例结构适配：

- `.hx` 用于判断 `.labels` 连接的是哪个图像体数据。
- 当前样例中 `.labels` 对齐的是 `.resampled`，不是 raw `.tif`。
- raw `.tif` 保留为 source/provenance。
- `.resampled + .labels` 是已有 AMIRA 标注的对齐显示组合。
- `.surf` 暂时作为 AMIRA 派生产物，不作为第一阶段核心标注真值。
- AMIRA 原始文件只读兼容，不修改、不写回。

## 7. TIF 标注界面

第一阶段必须具备：

- 原图 slice 显示；
- label overlay 半透明叠加；
- material/部位颜色列表；
- 画笔涂抹；
- Ctrl 或类似快捷键快速擦除；
- 画笔大小调节；
- Ctrl+Z 撤销/重做；
- 亮度调节；
- 对比度调节；
- overlay 透明度调节；
- 简单复核状态。

简单状态可先设为：

```text
未开始
标注中
完整标注
已复核
可训练
```

## 8. TIF 保存格式

TIF project JSON 保持轻量，只保存：

- specimen 编号；
- 文件路径；
- material map；
- review / train-ready 状态；
- 模型记录；
- provenance。

大型体数据和标签数据放 sidecar，不嵌入 JSON。

开源社区格式选择：

- **首选长期 sidecar 格式：OME-Zarr / OME-NGFF**  
  适合大型生物成像体数据，支持分块读取、标准 metadata，也支持关联 label images。
- **导出/交换格式：OME-TIFF**  
  适合传统显微图像和较直观的 TIF 栈交换。
- **模型/医学影像生态导出：NIfTI / NRRD / MHA / 3D TIFF**  
  用于 nnU-Net、MONAI 或 3D Slicer 等外部工具时按需导出。
- **不做第一阶段写回：AMIRA `.labels`**  
  因为写回成本高，且可能破坏原始数据。

### 8.1 开源社区格式选择原则

本项目的 TIF/volume 标注不要发明私有大格式。长期保存和对外交换都尽量对接开源社区已经认可的格式。

推荐分层如下：

```text
项目内部长期工作格式：OME-Zarr / OME-NGFF
对显微图像社区交换：OME-TIFF
对模型训练/医学影像工具交换：NIfTI / NRRD / MHA / 3D TIFF
对旧 AMIRA 数据：只读导入，不作为第一阶段写回目标
```

#### OME-Zarr / OME-NGFF

这是 TIF 工作台推荐的长期 sidecar 格式。

它是什么：

- OME 是 Open Microscopy Environment，主要服务生物成像数据和显微图像 metadata。
- Zarr 是分块保存大型多维数组的开放格式。
- OME-Zarr / OME-NGFF 把两者结合起来，用开放 metadata 描述大体积图像、坐标轴、物理尺度、多分辨率层级和 labels。

为什么适合我们：

- 一整只蚂蚁的 TIF stack 或脑部分区 label volume 可能很大。
- 标注工作台通常只看当前 slice 或局部区域，不应该每次都整卷读入内存。
- 分块保存适合快速读取某一层、某一块，也适合后续 Web/本地混合查看。
- OME-NGFF 本身支持 image + labels 的组织方式，和我们“原图体数据 + label field”的结构匹配。

对研究流程的意义：

- 用户可以长期保存一个 specimen 的工作体数据和人工真值。
- 后续换模型、换后端、换机器时，只要读 OME-Zarr 和 project JSON，就能恢复标注状态。
- 不依赖 AMIRA/Avizo 私有工作流，也不把大体数据塞进 JSON。

如果不用它：

- 只用单个大 TIF 时，局部编辑和频繁保存会比较笨重。
- 只用 `.npy` / `.h5` 虽然开发简单，但对外部 bioimaging 工具和开源社区互通性弱。

#### OME-TIFF

这是推荐保留的显微图像交换格式，而不是主要编辑格式。

它是什么：

- OME-TIFF 是带 OME-XML metadata 的多页 TIFF。
- 它比普通 TIF 更清楚地保存维度、通道、Z 层、物理尺度等信息。

为什么保留：

- 很多显微图像软件、ImageJ/Fiji、Bio-Formats 生态都能理解 OME-TIFF。
- 用户拿到外部数据时，常见输入仍然可能是 `.tif` / `.ome.tif`。

限制：

- 对非常大的 volume 和频繁 slice 编辑，不如 OME-Zarr 灵活。
- 可以作为导入/导出格式，但不建议作为我们反复编辑保存的唯一核心格式。

#### NIfTI / NRRD / MHA / 3D TIFF

这些格式主要用于模型后端和外部工具交换。

它们分别适合什么：

- `NIfTI (.nii/.nii.gz)`：医学影像和 nnU-Net 生态常见，很多 3D segmentation 模型支持。
- `NRRD / .seg.nrrd`：3D Slicer 等工具对 segmentation/labelmap 很友好。
- `MHA / MHD`：ITK/SimpleITK、MONAI 等医学影像处理生态常见。
- `3D TIFF`：某些模型后端和显微图像处理脚本可直接使用，但通常需要额外 spacing metadata。

本项目中的定位：

- 它们是 export/import adapter，不是主项目保存格式。
- TIF 后端需要什么格式，就由 `prepare_dataset` 阶段从 OME-Zarr 转换出去。
- 模型预测完成后，再把结果导回 `model_draft` 层。

#### AMIRA `.labels`

这是兼容旧数据的读取格式，不是第一阶段编辑保存格式。

它是什么：

- AMIRA/Avizo 的 label field 文件，每个体素保存一个 material ID。
- 我们拿到的现有蚂蚁脑分区数据属于这一类。

为什么第一阶段只读：

- 写回 AMIRA 原生格式需要额外适配成本。
- 写错可能破坏原始科研数据。
- 我们真正需要的是读出原始共聚焦标注，转成开放格式，作为训练和迁移学习的数据来源。

第一阶段策略：

- 原始 AMIRA 文件只读保存。
- 导入后转换为本项目可编辑的 OME-Zarr label volume。
- 修改后的人工结果保存到 `manual_truth.ome.zarr` 或 `working_edit.ome.zarr`。

推荐项目结构：

```text
tif_project/
├─ project.json
├─ specimens/
│  └─ 01-0101-02/
│     ├─ source/
│     │  └─ raw.tif
│     ├─ working/
│     │  ├─ brain.resampled
│     │  └─ working_volume.ome.zarr/
│     ├─ labels/
│     │  ├─ manual_truth.ome.zarr/
│     │  ├─ model_draft.ome.zarr/
│     │  └─ working_edit.ome.zarr/
│     └─ material_map.json
├─ models/
├─ exports/
└─ logs/
```

## 9. 人工真值、模型草稿和编辑层

TIF 标注分三层：

```text
manual_truth
```

人工确认过、可以进入训练的数据。

```text
model_draft
```

模型粗标结果，不是训练真值。

```text
working_edit
```

用户正在修正的编辑副本。

强约束：

- 模型预测不能默认覆盖人工标注。
- 人工标注价值高于模型标注。
- 模型预测只能作为草稿或候选。
- 只有人工复核或明确接受后，才能成为训练真值。

## 10. TIF 独立模型后端

TIF 后端必须独立于当前 STL/2D 后端。

原因：

- STL/2D 输出 polygon / box。
- TIF 输出 3D label volume。
- 两者数据结构、训练任务、预测结果完全不同。

采用新的 contract：

```text
ant3d_tif_backend_contract_v1
```

支持：

- `prepare_dataset`
- `train`
- `predict`

目标：

- 不锁死 nnU-Net；
- 可接入 nnU-Net、MONAI 或其他模型；
- 可支持共聚焦模型向 micro-CT 数据的迁移实验；
- 预测结果统一进入 `model_draft`，不污染 `manual_truth`。

### 10.1 TIF 后端 contract v1 中文版

这个 contract 的作用，是规定前端工作台和外部模型后端怎么交接数据。它不规定必须使用哪个模型，只规定“你要训练/预测时，输入什么，输出什么，哪些东西不能碰”。

核心边界：

- TIF 后端只能处理 TIF/volume segmentation 任务。
- TIF 后端不复用 STL/2D 的 box、polygon、SAM mask contract。
- 后端不能直接覆盖 `manual_truth`。
- 后端预测结果只能写成新的结果文件，由前端导入为 `model_draft`。
- 人工确认后，才允许把某个预测结果提升为训练真值。

#### 10.1.1 必须支持的动作

```text
prepare_dataset
train
predict
```

`prepare_dataset` 是训练前的数据整理。

它做什么：

- 从项目里选出 train-ready 的 specimen。
- 检查 image volume、label volume、material map 是否存在。
- 检查 image 和 label 的 shape 是否匹配。
- 按后端需要导出成 NIfTI、NRRD、MHA、3D TIFF 或后端自定义目录。

为什么重要：

- 不同模型吃的数据格式不一样。
- 用户不应该手工整理几十只蚂蚁的大体数据目录。
- 这一步可以把错误提前暴露，例如标签维度不匹配、某个 material 缺失、spacing 信息不完整。

`train` 是模型训练。

它做什么：

- 读取 `prepare_dataset` 生成的数据集。
- 使用指定模型后端训练，例如 nnU-Net、MONAI 或未来其他模型。
- 输出模型权重、训练日志、指标和配置快照。

为什么重要：

- 我们的目标是不断迭代自动标注能力。
- 每一次训练都要能追溯：用了哪些 specimen、哪些 label、哪个 material map、哪个模型配置。

`predict` 是模型粗标。

它做什么：

- 对未标注或待复核的 specimen volume 做自动预测。
- 输出一个 label volume。
- 前端导入后放在 `model_draft` 层。

为什么重要：

- 模型预测只是草稿，方便人工修正。
- 它不能覆盖人工真值，否则会降低数据可信度。

#### 10.1.2 contract 输入字段

下面字段是概念设计，后续实现时可以变成 JSON。

`contract_version`

- 是什么：contract 版本号，例如 `ant3d_tif_backend_contract_v1`。
- 为什么保存：防止未来字段升级后，新旧后端混用。
- 影响流程：前端可以判断某个后端是否兼容当前项目。

`action`

- 是什么：本次要执行的动作，取值为 `prepare_dataset`、`train` 或 `predict`。
- 为什么保存：同一个后端入口可以根据动作执行不同任务。
- 影响流程：决定后端是整理数据、训练模型，还是生成预测。

`project_id`

- 是什么：当前 TIF project 的标识。
- 为什么保存：训练结果和预测结果要能追溯到哪个项目。
- 影响流程：日志、模型记录、导出目录都可以挂回这个项目。

`specimen_ids`

- 是什么：本次参与训练或预测的 specimen 编号列表，例如 `01-0101-02`。
- 为什么保存：训练不是按物种名，而是按 specimen 数据集合。
- 影响流程：用户以后能知道某个模型到底看过哪些蚂蚁个体。

`input_volumes`

- 是什么：每个 specimen 对应的图像体数据路径，通常指向 `working_volume.ome.zarr`，也可以是 prepare 后导出的 `.nii.gz` / `.nrrd` / `.mha`。
- 为什么保存：模型需要知道原始灰度图像在哪里。
- 影响流程：预测和训练都从这里读取图像。

`label_volumes`

- 是什么：训练时使用的人工 label volume 路径，通常来自 `manual_truth.ome.zarr`。
- 为什么保存：模型训练必须只使用人工确认过的数据。
- 影响流程：如果这里只给了 `model_draft`，系统应拒绝或要求明确确认。

`material_map`

- 是什么：material ID 到部位名称、颜色、训练含义的映射。
- 为什么保存：模型只看到整数，研究者需要知道 1、2、3 分别代表哪个脑区或内部结构。
- 影响流程：训练、显示、导出、预测颜色都依赖它。

`modality`

- 是什么：数据来源类型，例如 `confocal`、`micro_ct`、`unknown`。
- 为什么保存：共聚焦和 micro-CT 的灰度、饱和度、边缘清晰度差异很大。
- 影响流程：后端可以选择不同 normalization、增强策略或迁移学习方案。

`spacing`

- 是什么：体素物理尺寸，例如 Z/Y/X 每个方向多少 micrometer。
- 为什么保存：3D 模型和 3D 重建需要真实比例。
- 影响流程：影响模型重采样、三维测量、3D Slicer/AMIRA 外部查看。

`orientation`

- 是什么：体数据轴向信息，例如 Z/Y/X 的顺序和方向。
- 为什么保存：避免左右、上下、前后方向混乱。
- 影响流程：影响 overlay 是否对齐，也影响 3D 输出是否翻转。

`output_dir`

- 是什么：后端写出训练数据、模型、预测结果的位置。
- 为什么保存：避免后端随便写进项目目录。
- 影响流程：前端只从指定输出目录导入后端结果。

`training_config`

- 是什么：训练参数，例如模型类型、epoch、patch size、batch size、增强策略。
- 为什么保存：保证训练可复现。
- 影响流程：同一批数据换参数后，模型结果可以被比较。

`model_record`

- 是什么：预测时使用的模型信息，包括模型路径、模型名称、训练来源、版本。
- 为什么保存：一个预测结果必须知道是谁生成的。
- 影响流程：人工复核时可以判断某批粗标来自哪个模型。

`protect_manual_truth`

- 是什么：数据安全开关，默认 `true`。
- 为什么保存：强制防止后端覆盖人工真值。
- 影响流程：后端只能写新文件，不能修改 `manual_truth`。

#### 10.1.3 contract 输出字段

`status`

- 是什么：本次任务结果，例如 `success`、`failed`、`partial_success`。
- 为什么保存：前端需要知道后端是否完成。
- 影响流程：失败时不能把结果导入项目。

`artifacts`

- 是什么：后端生成的文件清单，例如训练数据目录、模型权重、预测 label volume、日志。
- 为什么保存：前端要从这里找到可导入结果。
- 影响流程：导入 `model_draft`、登记模型记录、查看训练日志都依赖它。

`prediction_outputs`

- 是什么：每个 specimen 的预测 label volume 路径。
- 为什么保存：预测通常是一只蚂蚁一个结果。
- 影响流程：前端按 specimen 导入，不混淆样本。

`metrics`

- 是什么：训练或验证指标，例如 loss、Dice、每个 material 的分割质量。
- 为什么保存：判断模型是否变好了。
- 影响流程：决定是否用新模型继续预标注更多数据。

`warnings`

- 是什么：不阻断任务但需要注意的问题，例如 spacing 缺失、某个 material 样本太少。
- 为什么保存：研究者需要知道结果可信度风险。
- 影响流程：影响是否把模型用于更大规模粗标。

`errors`

- 是什么：导致任务失败的问题，例如 shape 不匹配、label 文件缺失、模型文件不存在。
- 为什么保存：方便定位失败原因。
- 影响流程：用户可以回到项目里修复对应 specimen 或数据层。

`provenance`

- 是什么：任务来源记录，包括 contract 版本、后端名称、后端版本、执行时间、输入 specimen、输入 label 层。
- 为什么保存：科研数据需要可追溯。
- 影响流程：以后发表、共享或复查模型结果时，能说明数据和模型来源。

#### 10.1.4 后端不能做的事

- 不能修改原始 AMIRA 文件。
- 不能覆盖 raw TIF。
- 不能覆盖 `manual_truth`。
- 不能把 `model_draft` 自动当作训练真值。
- 不能把 STL label 类别和 TIF material map 混用。
- 不能假设所有 TIF 都是 micro-CT，也不能假设所有 TIF 都是共聚焦。

#### 10.1.5 第一阶段最小实现

第一阶段不追求复杂调度，只要做到：

- 前端能生成一个标准 request JSON。
- 后端按 request JSON 整理数据、训练或预测。
- 后端输出一个标准 result JSON。
- 前端读取 result JSON，把预测导入 `model_draft`。
- 用户人工复核后，再手动提升为 `manual_truth`。

## 11. TIF 训练准备标准

第一阶段只做简单判断：

- specimen 状态为可训练；
- working image volume 存在；
- label volume 存在；
- material_map 存在；
- image/label shape 匹配。

不做复杂 slice 级评分。

## 12. PDF 模块

PDF Processing 不再作为主界面核心模块。

第一阶段处理方式：

- 从主界面注释/隐藏 PDF Processing；
- 不删除底层代码；
- 保留 headless / tools / agentic 能力；
- 后续单独设计一个 PDF skill，移植给智能体使用。

## 13. 收口前核对清单

目前一级方向基本已经对齐。剩下需要补充的不是“项目到底做什么”的问题，而是进入实施前要把几个边界写清楚，避免后面编码时出现理解偏差。

### 13.1 Project 打开和创建流程

建议确认：

- 新建项目时明确选择 `STL Project` 或 `TIF Project`。
- 打开项目时根据 project type 自动进入对应界面。
- 不做一个同时塞入 STL 和 TIF 的大 workspace。

为什么要确认：

- 这会决定主界面第一层入口怎么设计。
- 也会决定旧 TaxaMask 项目如何迁移或兼容。

对研究流程的影响：

- 用户做体表渲染图标注时，不会被 TIF/volume 功能干扰。
- 用户做 TIF 内部结构标注时，也不会混进 STL/Blink 训练逻辑。

### 13.2 TIF project JSON 最小字段

建议下一步单独写一个 schema 草案，至少覆盖：

- project type；
- project id/name；
- specimen 列表；
- 每个 specimen 的 source volume；
- working volume；
- manual truth；
- model draft；
- working edit；
- material map；
- modality；
- spacing；
- orientation；
- review status；
- model records；
- provenance。

为什么要确认：

- 这是后面 TIF 模块读写项目文件的基础。
- JSON 只保存索引和状态，大体数据仍然保存在 OME-Zarr sidecar。

对研究流程的影响：

- 用户以后可以清楚知道某只蚂蚁有哪些原始数据、哪些人工标注、哪些模型预测、哪些结果已经可训练。

### 13.3 Material map 规则

建议确认：

- material ID 是否从 0 开始，其中 0 通常代表 background；
- 每个 material 至少保存 name、display color、训练是否启用；
- AMIRA 导入时尽量保留原始 material ID；
- 新建 TIF 项目时允许用户自己建立内部结构 label 表；
- STL label 类别和 TIF material map 永远分开。

为什么要确认：

- 模型训练只认识整数 ID，但研究者需要看到真实脑区或内部结构名称。
- 如果 ID 被随意重排，旧数据、模型预测和人工复核会很难追溯。

对研究流程的影响：

- 同一批脑区分区标注可以稳定进入多轮训练。
- 后续导出到外部工具时，颜色和名称不会乱。

### 13.4 AMIRA 导入器边界

建议确认：

- 第一阶段只支持当前样例中出现的 `.hx + .resampled + .labels + raw .tif` 结构。
- `.hx` 负责判断 label 对齐哪个 working volume。
- raw `.tif` 只作为 source/provenance 保留。
- 如果 raw TIF、resampled volume、labels shape 不一致，必须显示警告。
- 不修改、不覆盖 AMIRA 原始文件。

为什么要确认：

- AMIRA/Avizo 的项目结构可能很灵活，第一阶段不能承诺兼容所有变体。
- 我们只需要先把当前真实数据集稳定导入，转成开放工作格式。

对研究流程的影响：

- 现有共聚焦蚂蚁脑标注数据可以作为第一批训练数据。
- 不会因为导入器写回错误破坏原始科研文件。

### 13.5 TIF 标注保存和人工确认流程

建议确认：

- `working_edit` 是当前编辑层。
- 用户点击确认或完成复核后，才写入/更新 `manual_truth`。
- `model_draft` 只能作为草稿显示和修正。
- 模型预测导入时如果已有人工真值，默认不覆盖。
- 可以从 `model_draft` 复制一份到 `working_edit` 进行人工修正。

为什么要确认：

- 这是保证“人工标注价值高于模型标注”的核心安全机制。

对研究流程的影响：

- 粗标可以提高效率，但不会污染已经确认过的训练集。
- 训练集可信度更容易解释和复查。

### 13.6 TIF 训练导出和结果回收

建议确认：

- 训练只读取 `manual_truth`，不默认读取 `model_draft`。
- `prepare_dataset` 负责把 OME-Zarr 转成后端需要的格式。
- `predict` 输出结果统一导入为 `model_draft`。
- 每次训练和预测都登记 model record。

为什么要确认：

- 这样可以让 nnU-Net、MONAI 或其他模型共享同一个前端项目结构。

对研究流程的影响：

- 用户可以比较不同模型、不同训练轮次的效果。
- 每个预测结果都能追溯到具体模型和训练数据来源。

### 13.7 PDF 模块下沉边界

建议确认：

- 主界面不再显示完整 PDF Processing 大面板。
- 底层代码暂时保留，不删除。
- 后续迁移为智能体 skill/headless workflow。
- 迁移后 PDF 结果更多作为文献证据、图像来源和 provenance，而不是核心训练图来源。

为什么要确认：

- PDF 工作流不再服务当前 AntScan-style STL/TIF 主目标。
- 但旧能力仍可能对文献筛查和证据整理有价值。

对研究流程的影响：

- 主界面会更聚焦 STL/TIF 标注和训练。
- 文献处理交给智能体自动化，更符合现在的技术条件。

## 14. 需求对齐收尾方案

需求对齐阶段到这里收尾。后续不再把下面内容视为“需求未确认”，而是进入实施设计和编码拆分。

已经转入实施设计的内容：

- OME-Zarr 项目目录结构、TIF project JSON 草案、specimen 字段、material map、train-ready 判断，已进入 `TIF项目结构实施设计_zh.md`。
- AMIRA 只读导入、`.hx + .resampled + .labels` 对齐关系、shape 检查、material map 生成，已进入 `AMIRA导入适配实施设计_zh.md`。
- TIF 独立后端 contract、`prepare_dataset / train / predict`、result JSON、model manifest、安全规则，已进入 `TIF后端契约_v1_实施设计_zh.md`。

建议下一阶段按这个顺序推进：

```text
第一步：实现 TIF Project 最小骨架
-> 第二步：实现 AMIRA 样例只读导入
-> 第三步：实现 TIF slice viewer + label overlay
-> 第四步：实现画笔编辑、擦除、撤销重做、透明度/亮度/对比度
-> 第五步：接入 TIF backend contract 的 prepare_dataset / predict 最小闭环
-> 第六步：再处理 STL 项目轻量迁移和 PDF skill 下沉
```

暂不进入本阶段的内容：

- TIF 画笔性能优化细节，等 TIF 标注工作台 UI 设计时处理。
- STL Project 导入命名解析规则，等 STL 轻量迁移设计时处理。
- PDF skill 迁移方案，等智能体 skill 设计时处理。

收尾判断：

- 产品定位已确认。
- STL/TIF 双 project 体系已确认。
- TIF 使用 AMIRA-style label field 已确认。
- OME-Zarr / OME-NGFF 作为 TIF 长期工作格式已确认。
- AMIRA 原始文件只读导入、不写回已确认。
- TIF 模型后端独立于 STL/2D 后端已确认。
- 模型预测不得覆盖人工真值已确认。
- PDF 模块从主界面下沉为后续 skill 已确认。

因此，本文件后续只作为需求基线保存。真正的实现讨论从三份实施设计文档继续展开。
