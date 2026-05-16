# TIF Project 结构实施设计

> 所属方向：Ant 3D Workbench / TIF Volume Mode
>
> 目标：把 TIF 内部结构标注项目从需求描述转成可编码、可保存、可训练、可恢复的项目结构。

## 1. 设计目标

TIF Project 是一个独立项目类型，不和 STL Project 塞进同一个 JSON。

它要解决的研究问题是：

- 导入完整 TIF stack 或 AMIRA 对齐后的 working volume；
- 按 specimen 编号组织每只蚂蚁的体数据；
- 保存人工标注、模型粗标、当前编辑层；
- 支持按完整 volume 进入训练；
- 支持后续把预测结果导回项目进行人工复核；
- 保持原始科研数据可追溯，不破坏 raw TIF 或 AMIRA 原始文件。

第一阶段只设计 TIF Project，不重构 STL 训练框架。

## 2. 核心原则

- `project.json` 只保存索引、状态和 provenance，不保存大体数据。
- 大型 image volume 和 label volume 使用 sidecar 文件夹保存，首选 OME-Zarr / OME-NGFF。
- 每个 specimen 是左侧栏的主要组织单位。
- `manual_truth`、`model_draft`、`working_edit` 必须分层保存。
- 模型预测不能默认覆盖人工标注。
- TIF label/material map 与 STL label/taxonomy 完全独立。
- 旧 AMIRA 文件只读保存，不写回。

## 3. 推荐目录结构

```text
tif_project/
├─ project.json
├─ specimens/
│  └─ 01-0101-02/
│     ├─ source/
│     │  ├─ raw/
│     │  │  └─ original.tif
│     │  └─ amira_original/
│     │     ├─ project.hx
│     │     ├─ image.resampled
│     │     ├─ labels.labels
│     │     ├─ labels.MaterialStatistics
│     │     └─ labels.surf
│     ├─ working/
│     │  ├─ image.ome.zarr/
│     │  └─ import_report.json
│     ├─ labels/
│     │  ├─ manual_truth.ome.zarr/
│     │  ├─ working_edit.ome.zarr/
│     │  └─ model_draft/
│     │     └─ prediction_20260515_153000.ome.zarr/
│     └─ material_map.json
├─ runs/
│  ├─ prepare_dataset/
│  ├─ train/
│  └─ predict/
├─ models/
├─ exports/
└─ logs/
```

### 3.1 `project.json`

它是什么：

- TIF Project 的入口文件。
- 程序打开项目时先读它，再根据里面的路径找到各个 specimen、volume 和 label。

为什么保存：

- 让项目可以恢复、迁移、检查和训练。
- 避免把大型 TIF/label 数据直接塞进 JSON。

影响流程：

- 打开项目；
- 左侧栏显示 specimen；
- 判断哪些 specimen 可以训练；
- 追踪模型预测来源；
- 生成后端 contract。

如果不保存：

- 项目只能靠文件夹猜测状态，容易混乱。
- 后续训练和复核很难追溯。

### 3.2 `specimens/<specimen_id>/source/`

它是什么：

- 原始来源数据保存区。
- raw TIF、AMIRA `.hx`、`.labels`、`.resampled`、`.surf` 等原始文件都放这里或记录到这里。

为什么保存：

- 科研数据必须能追溯来源。
- 导入转换后如果发现对齐或解析问题，可以回到原始文件检查。

影响流程：

- AMIRA 导入；
- provenance 追踪；
- 后续重新转换；
- 发表或共享数据时说明来源。

如果不保存：

- 很难证明一个 label volume 来自哪份原始数据。
- 后续发现导入错误时无法复查。

### 3.3 `working/image.ome.zarr/`

它是什么：

- 工作台实际读取和显示的 image volume。
- 对 AMIRA 导入来说，它通常来自 `.resampled`，不是 raw TIF。

为什么保存：

- TIF 标注界面需要快速读取当前 slice。
- OME-Zarr 分块保存更适合大体数据编辑和显示。

影响流程：

- slice viewer 显示原图；
- brightness/contrast 调整；
- label overlay 对齐；
- 训练导出时作为输入图像。

如果不保存：

- 每次都读原始 TIF 或 AMIRA 文件会比较慢，也不稳定。
- AMIRA resampled 数据和 label 可能无法正确对齐。

### 3.4 `labels/manual_truth.ome.zarr/`

它是什么：

- 人工确认后的 label volume。
- 它是训练默认读取的真值层。

为什么保存：

- 训练数据必须基于人工确认结果。
- 这是项目里最重要、最需要保护的标注资产。

影响流程：

- `prepare_dataset` 只默认读取这一层；
- train-ready 检查依赖这一层；
- 模型迭代质量依赖这一层。

如果不保存：

- 模型训练会混入草稿或未确认结果。
- 数据可信度会下降。

### 3.5 `labels/model_draft/`

它是什么：

- 模型自动预测产生的粗标结果。
- 可以有多个 prediction，每个 prediction 独立保存。

为什么保存：

- 粗标是为了提高人工修正效率，不是直接当真值。
- 多个模型或多轮模型可能对同一 specimen 产生不同预测。

影响流程：

- 用户可以选择某个预测作为参考；
- 可以复制到 `working_edit` 进行修正；
- 可以比较不同模型效果。

如果不分层保存：

- 模型结果可能污染人工真值。
- 用户很难知道某个标注是人画的还是模型画的。

### 3.6 `labels/working_edit.ome.zarr/`

它是什么：

- 当前正在编辑的 label volume。
- 可以由空白标签、人工真值副本、或模型草稿副本生成。

为什么保存：

- 用户在复核过程中需要中间状态。
- 不能每一笔都直接写入人工真值。

影响流程：

- 画笔涂抹；
- Ctrl 快速擦除；
- undo/redo；
- 人工修正模型粗标；
- 完成复核后再提升为 `manual_truth`。

如果不保存：

- 用户的中途修改很难恢复。
- 误操作可能直接污染训练真值。

### 3.7 `material_map.json`

它是什么：

- material ID 到内部结构名称、颜色、训练开关的映射。

为什么保存：

- 模型只认识整数 ID，但研究者需要看到实际脑区或内部结构名称。
- AMIRA 导入时需要保留原 material 定义。

影响流程：

- label overlay 显示颜色；
- 画笔选择当前部位；
- 训练时决定哪些 label 参与；
- 导出时保留名称和颜色。

如果不保存：

- `1`、`2`、`3` 代表什么会丢失。
- 后续训练和复核无法可靠解释。

## 4. `project.json` 草案

```json
{
  "schema_version": "ant3d_tif_project_v1",
  "project_type": "tif_volume",
  "project_id": "tif_project_20260515_001",
  "name": "Ant brain TIF segmentation",
  "created_at": "2026-05-15T15:30:00+08:00",
  "updated_at": "2026-05-15T15:30:00+08:00",
  "specimens": [
    {
      "specimen_id": "01-0101-02",
      "display_name": "01-0101-02",
      "metadata_ref": "master_table:01-0101-02",
      "modality": "confocal",
      "source": {
        "raw_tif": "specimens/01-0101-02/source/raw/original.tif",
        "amira_hx": "specimens/01-0101-02/source/amira_original/project.hx",
        "amira_labels": "specimens/01-0101-02/source/amira_original/labels.labels",
        "amira_resampled": "specimens/01-0101-02/source/amira_original/image.resampled"
      },
      "working_volume": {
        "path": "specimens/01-0101-02/working/image.ome.zarr",
        "format": "ome_zarr",
        "shape_zyx": [231, 1218, 1225],
        "dtype": "uint8",
        "spacing_zyx": [1.0, 1.0, 1.0],
        "spacing_unit": "micrometer",
        "orientation": "unknown"
      },
      "labels": {
        "manual_truth": {
          "path": "specimens/01-0101-02/labels/manual_truth.ome.zarr",
          "format": "ome_zarr",
          "status": "reviewed"
        },
        "working_edit": {
          "path": "specimens/01-0101-02/labels/working_edit.ome.zarr",
          "format": "ome_zarr",
          "status": "in_progress"
        },
        "model_drafts": []
      },
      "material_map": "specimens/01-0101-02/material_map.json",
      "review_status": "reviewed",
      "train_ready": true,
      "provenance": {
        "import_method": "amira_import_adapter_v1",
        "source_dataset": "AMIRA-data sample",
        "notes": "AMIRA labels aligned to resampled volume."
      }
    }
  ],
  "models": [],
  "runs": []
}
```

## 5. 字段解释

### `schema_version`

是什么：

- 项目文件格式版本。

为什么保存：

- 后续字段升级时，旧项目仍可被迁移。

影响流程：

- 打开项目时先判断是否支持该版本。

### `project_type`

是什么：

- 项目类型，TIF 项目固定为 `tif_volume`。

为什么保存：

- 打开项目时自动进入 TIF Volume Mode。

影响流程：

- 防止把 STL 项目误交给 TIF 工作台。

### `specimen_id`

是什么：

- 固定 specimen 编号，不是物种名。

为什么保存：

- 对齐用户已有数据编号体系。
- 可以通过总表查询物种和采集信息。

影响流程：

- 左侧栏分组；
- 训练集组织；
- provenance 追踪。

### `metadata_ref`

是什么：

- 指向外部总表的引用。

为什么保存：

- 避免把很长的物种名和总表信息塞进项目文件。

影响流程：

- 用户需要查物种信息时可以跳回总表。
- 模型训练不把物种身份作为输入。

### `modality`

是什么：

- 成像方式，例如 `confocal`、`micro_ct`、`unknown`。

为什么保存：

- 共聚焦和 micro-CT 的图像外观差异很大。

影响流程：

- 后端可以选择不同 normalization 或迁移学习策略。

### `shape_zyx`

是什么：

- volume 的 Z/Y/X 尺寸。

为什么保存：

- 检查 image 和 label 是否对齐。

影响流程：

- overlay；
- 训练导出；
- 导入预测。

### `spacing_zyx`

是什么：

- 每个体素在 Z/Y/X 方向的物理尺寸。

为什么保存：

- 3D 重建和测量需要真实比例。

影响流程：

- 外部工具导出；
- 模型重采样；
- 体积测量。

### `orientation`

是什么：

- 体数据方向信息。

为什么保存：

- 避免左右、前后、上下方向混乱。

影响流程：

- 三维查看；
- 与外部软件互通；
- 多数据集比较。

第一阶段可以允许 `unknown`，但必须保留字段。

### `review_status`

是什么：

- 当前 specimen 的标注复核状态。

建议取值：

```text
not_started
in_progress
fully_annotated
reviewed
train_ready
```

为什么保存：

- 用户需要知道哪些 volume 还没标，哪些可以训练。

影响流程：

- 左侧栏状态显示；
- 训练前筛选；
- 项目进度管理。

### `train_ready`

是什么：

- 是否允许进入训练集。

为什么保存：

- 单独布尔值可以让训练前筛选更直接。

影响流程：

- `prepare_dataset` 默认只选择 `train_ready: true` 的 specimen。

## 6. `material_map.json` 草案

```json
{
  "schema_version": "ant3d_tif_material_map_v1",
  "source": "amira_import_adapter_v1",
  "materials": [
    {
      "id": 0,
      "name": "background",
      "display_name": "Background",
      "color": "#000000",
      "trainable": false,
      "source_name": "Exterior"
    },
    {
      "id": 1,
      "name": "LO_L",
      "display_name": "LO_L",
      "color": "#ff4b4b",
      "trainable": true,
      "source_name": "LO_L"
    }
  ]
}
```

规则：

- `id` 尽量保留 AMIRA 原始 material ID。
- `0` 默认作为 background。
- `name` 用于程序和后端。
- `display_name` 用于界面显示。
- `color` 用于 overlay。
- `trainable` 决定是否进入训练目标。
- `source_name` 记录 AMIRA 原始名称。

## 7. Train-ready 最小判断

第一阶段只做简单判断：

- `train_ready` 为 `true`；
- working image volume 存在；
- `manual_truth` label volume 存在；
- `material_map.json` 存在；
- image volume 与 label volume 的 shape 一致；
- 至少有一个 `trainable: true` 的 material。

不做复杂 slice 质量评分。

## 8. 第一阶段不做

- 不把 STL 和 TIF 合并为一个大 project。
- 不把 raw TIF 直接当作唯一工作格式。
- 不把模型预测自动写入 `manual_truth`。
- 不写回 AMIRA `.labels`。
- 不要求所有项目必须有完整物种名。
- 不在 TIF 训练中使用 STL 的 Head/Mesosoma/Gaster locator 逻辑。

## 9. 验收标准

实现后至少应满足：

- 可以新建 `ant3d_tif_project_v1` 项目；
- 可以打开项目并看到 specimen 列表；
- 每个 specimen 能显示 working volume、label 状态、material map；
- 可以区分人工真值、模型草稿和当前编辑层；
- 可以判断哪些 specimen 可训练；
- 可以生成给 TIF 后端使用的 contract 输入。
