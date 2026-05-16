# TIF 后端契约 v1 实施设计

> 所属方向：Ant 3D Workbench / TIF Volume Mode / External Backend
>
> 契约名：`ant3d_tif_backend_contract_v1`

## 1. 设计目标

TIF 后端契约用于把外部 volume segmentation 模型接入 Ant 3D Workbench。

它要解决的问题是：

- 前端项目保存为 OME-Zarr 和 project JSON；
- 不同模型后端可能需要 NIfTI、NRRD、MHA、3D TIFF 或自定义格式；
- 用户希望尝试 nnU-Net、MONAI 或其他模型；
- 模型预测只能作为草稿导入，不能污染人工真值；
- 每轮训练和预测都必须可追溯。

这个契约只服务 TIF/volume segmentation，不复用 STL/2D 的 polygon、box、SAM mask contract。

## 2. 调用方式

外部脚本建议统一接受：

```bash
python tif_backend.py --contract C:/path/to/contract.json
```

前端负责：

- 写出 contract JSON；
- 创建 run directory；
- 启动外部脚本；
- 读取 result JSON；
- 把预测导入 `model_draft`；
- 登记模型记录和运行记录。

后端负责：

- 读取 contract JSON；
- 执行 `prepare_dataset`、`train` 或 `predict`；
- 只写入 contract 指定的输出目录；
- 写出 result JSON；
- 不修改 raw TIF、AMIRA 原始文件或 `manual_truth`。

## 3. 支持动作

```text
prepare_dataset
train
predict
```

### 3.1 `prepare_dataset`

它做什么：

- 从 TIF project 中读取 train-ready specimen；
- 检查 working image、manual truth、material map；
- 将 OME-Zarr 转成后端需要的训练格式；
- 生成 dataset manifest。

为什么需要：

- 不同模型吃的数据格式不一样。
- 用户不应该手工整理几十个 specimen 的体数据。

输出：

- 后端训练数据目录；
- dataset manifest；
- 检查报告；
- result JSON。

### 3.2 `train`

它做什么：

- 读取 prepared dataset；
- 训练模型；
- 写出模型权重、模型 manifest、日志和指标。

为什么需要：

- 本项目核心路线是标注、复核、训练、粗标、再复核、再训练。

输出：

- model directory；
- model manifest；
- training metrics；
- training logs；
- result JSON。

### 3.3 `predict`

它做什么：

- 对指定 specimen 的 working image volume 做自动预测；
- 写出 label volume；
- 前端将其导入 `model_draft`。

为什么需要：

- 让模型帮用户粗标，用户再人工修正。

输出：

- 每个 specimen 一个 prediction label volume；
- prediction manifest；
- result JSON。

## 4. Contract JSON 草案

```json
{
  "schema_version": "ant3d_tif_backend_contract_v1",
  "action": "predict",
  "backend_id": "nnunet_v2_adapter",
  "project_json": "C:/path/tif_project/project.json",
  "run_id": "predict_20260515_153000_nnunet_v2_adapter",
  "run_dir": "C:/path/tif_project/runs/predict/predict_20260515_153000_nnunet_v2_adapter",
  "dataset_dir": "C:/path/tif_project/runs/prepare_dataset/dataset_20260515_120000",
  "model_manifest": "C:/path/tif_project/models/model_20260515_140000/model_manifest.json",
  "output_dir": "C:/path/tif_project/runs/predict/predict_20260515_153000_nnunet_v2_adapter/outputs",
  "result_json": "C:/path/tif_project/runs/predict/predict_20260515_153000_nnunet_v2_adapter/result.json",
  "specimens": [
    {
      "specimen_id": "01-0101-02",
      "modality": "micro_ct",
      "input_volume": {
        "path": "C:/path/tif_project/specimens/01-0101-02/working/image.ome.zarr",
        "format": "ome_zarr",
        "shape_zyx": [231, 1218, 1225],
        "dtype": "uint8",
        "spacing_zyx": [1.0, 1.0, 1.0],
        "spacing_unit": "micrometer",
        "orientation": "unknown"
      },
      "label_volume": {
        "path": "",
        "format": "",
        "role": "none"
      },
      "material_map": "C:/path/tif_project/specimens/01-0101-02/material_map.json"
    }
  ],
  "training_config": {
    "model_family": "nnunet_v2",
    "task_name": "ant_brain_regions",
    "patch_size": null,
    "epochs": null,
    "normalization": "backend_default",
    "augmentation": "backend_default"
  },
  "safety": {
    "protect_manual_truth": true,
    "allow_model_draft_as_training_label": false,
    "allow_overwrite_outputs": false
  }
}
```

## 5. 输入字段解释

### `schema_version`

是什么：

- 契约版本，固定为 `ant3d_tif_backend_contract_v1`。

为什么保存：

- 避免未来 contract 升级后，旧后端误读新字段。

影响流程：

- 前端启动后端前先检查兼容性。

### `action`

是什么：

- 本次动作：`prepare_dataset`、`train` 或 `predict`。

为什么保存：

- 同一个后端脚本可以按动作执行不同任务。

影响流程：

- 决定后端是整理数据、训练模型，还是生成粗标。

### `backend_id`

是什么：

- 后端名称，例如 `nnunet_v2_adapter`、`monai_adapter`。

为什么保存：

- 用户可能同时测试多个模型家族。

影响流程：

- 模型记录；
- 运行日志；
- 预测来源追踪。

### `project_json`

是什么：

- 当前 TIF project 的入口文件路径。

为什么保存：

- 后端需要读取 specimen、material map 和 volume 路径。

影响流程：

- prepare/train/predict 都从这里追溯项目来源。

### `run_id` 和 `run_dir`

是什么：

- 本次任务的唯一编号和输出目录。

为什么保存：

- 每次训练和预测都要独立记录。

影响流程：

- 防止覆盖旧结果；
- 便于复查失败日志；
- 便于比较不同训练轮次。

### `dataset_dir`

是什么：

- `prepare_dataset` 输出或 `train` 输入的数据集目录。

为什么保存：

- 模型训练通常不直接读取项目结构，而是读取整理后的训练目录。

影响流程：

- train action 从这里读取数据。

### `model_manifest`

是什么：

- 模型说明文件路径。

为什么保存：

- 预测时必须知道用的是哪个模型。

影响流程：

- prediction provenance；
- 模型版本管理；
- 用户比较模型效果。

### `specimens`

是什么：

- 本次任务涉及的 specimen 列表。

为什么保存：

- 训练和预测都不是按物种名，而是按 specimen 数据集合。

影响流程：

- 后端知道处理哪些 volume；
- 前端知道结果要导回哪些 specimen。

### `input_volume`

是什么：

- 图像体数据，通常是 working image OME-Zarr。

为什么保存：

- 模型需要灰度图像作为输入。

影响流程：

- prepare_dataset 转换；
- train 读取；
- predict 推理。

### `label_volume`

是什么：

- 训练时使用的 label volume。

规则：

- train/prepare_dataset 默认只能使用 `manual_truth`。
- predict 时可以为空。
- 不允许默认使用 `model_draft` 作为训练真值。

为什么保存：

- 保证模型训练基于人工确认数据。

影响流程：

- 数据可信度；
- 训练集筛选；
- 后续发表或共享时说明训练来源。

### `material_map`

是什么：

- material ID 和部位名称、颜色、训练开关的映射文件。

为什么保存：

- 模型只看到整数 ID，用户需要知道每个 ID 的生物学含义。

影响流程：

- 训练类别；
- 预测颜色；
- 指标按 material 输出。

### `training_config`

是什么：

- 后端训练参数。

为什么保存：

- 模型结果必须可复现。

影响流程：

- 比较不同模型；
- 复训；
- 迁移学习实验。

第一阶段可以允许很多字段为 `null`，代表使用后端默认值。

### `safety`

是什么：

- 数据安全策略。

为什么保存：

- 防止模型输出覆盖人工真值。

影响流程：

- 后端只能写到 `output_dir`；
- 前端导入时只进 `model_draft`；
- 需要人工确认才能进入 `manual_truth`。

## 6. Result JSON 草案

```json
{
  "schema_version": "ant3d_tif_backend_result_v1",
  "contract_schema_version": "ant3d_tif_backend_contract_v1",
  "status": "success",
  "action": "predict",
  "backend_id": "nnunet_v2_adapter",
  "run_id": "predict_20260515_153000_nnunet_v2_adapter",
  "artifacts": [
    {
      "type": "prediction_label_volume",
      "specimen_id": "01-0101-02",
      "path": "outputs/01-0101-02_prediction.ome.zarr",
      "format": "ome_zarr",
      "role": "model_draft"
    }
  ],
  "metrics": {
    "summary": {},
    "by_material": {}
  },
  "warnings": [],
  "errors": [],
  "provenance": {
    "started_at": "2026-05-15T15:30:00+08:00",
    "finished_at": "2026-05-15T15:42:00+08:00",
    "model_manifest": "C:/path/tif_project/models/model_20260515_140000/model_manifest.json",
    "input_specimens": ["01-0101-02"],
    "input_label_role": "none"
  }
}
```

## 7. 输出字段解释

### `status`

是什么：

- 任务状态：`success`、`failed`、`partial_success`。

为什么保存：

- 前端需要判断是否能导入结果。

影响流程：

- 失败结果不进入 `model_draft`。

### `artifacts`

是什么：

- 后端生成的文件清单。

为什么保存：

- 前端只根据清单导入结果，不扫描未知目录。

影响流程：

- 导入预测；
- 登记模型；
- 查看日志。

### `metrics`

是什么：

- 训练或验证指标。

为什么保存：

- 用户需要判断模型是否有进步。

影响流程：

- 决定是否扩大自动粗标范围；
- 比较共聚焦模型和 micro-CT 适配模型。

### `warnings`

是什么：

- 非致命但影响可信度的问题。

例子：

- spacing 缺失；
- 某个 material 样本很少；
- volume 被重采样；
- 预测输出 shape 与输入略有差异但已修正。

为什么保存：

- 科研工作需要知道结果风险。

### `errors`

是什么：

- 导致任务失败的问题。

例子：

- shape 不匹配；
- label volume 缺失；
- model manifest 不存在；
- 输出目录不可写。

为什么保存：

- 用户可以据此回到项目修复数据。

### `provenance`

是什么：

- 本次任务的来源记录。

为什么保存：

- 每个模型和预测结果都要能追溯。

影响流程：

- 发表数据；
- 复查模型；
- 让智能体继续调试后端。

## 8. Model Manifest 草案

训练成功后，后端必须写出模型 manifest。

```json
{
  "schema_version": "ant3d_tif_model_manifest_v1",
  "model_id": "nnunet_v2_adapter/model_20260515_140000",
  "backend_id": "nnunet_v2_adapter",
  "model_family": "nnunet_v2",
  "task_name": "ant_brain_regions",
  "created_at": "2026-05-15T14:00:00+08:00",
  "trained_from_project": "C:/path/tif_project/project.json",
  "trained_specimens": ["01-0101-02", "01-0101-03"],
  "label_role": "manual_truth",
  "material_map_snapshot": "material_map_snapshot.json",
  "modality": {
    "source": "confocal",
    "target": "micro_ct",
    "adaptation_note": "initial confocal-to-micro-CT experiment"
  },
  "weights": {
    "main": "weights/model.pt"
  },
  "metrics": {
    "summary": {},
    "by_material": {}
  }
}
```

为什么需要：

- 预测结果必须知道来自哪个模型。
- 后续多模型比较、迁移学习、版本回退都依赖它。

## 9. 安全规则

后端必须遵守：

- 不修改 raw TIF；
- 不修改 AMIRA 原始文件；
- 不修改 `manual_truth`；
- 不把 `model_draft` 默认当训练真值；
- 不把 STL label 和 TIF material 混用；
- 不假设所有数据都是 micro-CT；
- 不假设所有数据都是共聚焦；
- 不写入 contract 指定目录以外的位置。

前端导入结果时必须遵守：

- `prediction_label_volume` 只能导入 `model_draft`；
- 如果同一 specimen 已有人工真值，默认不覆盖；
- 用户明确选择后，才可复制 prediction 到 `working_edit`；
- 用户复核确认后，才可提升为 `manual_truth`。

## 10. 第一阶段最小实现

第一阶段可以先做到：

- 前端生成 contract JSON；
- 后端读取 contract JSON；
- `prepare_dataset` 生成一个 dataset manifest；
- `train` 写出 model manifest；
- `predict` 写出 prediction label volume 和 result JSON；
- 前端读取 result JSON 并导入 `model_draft`；
- 所有任务保留日志和 provenance。

第一阶段不强制：

- 内置 nnU-Net；
- 内置 MONAI；
- 图形化管理复杂训练参数；
- 自动调参；
- 分布式训练；
- 云端训练。

## 11. 验收标准

- Contract JSON 能清楚表达 train/predict 需要的 specimen、image、label、material map；
- 后端输出 result JSON 后，前端能找到预测 label volume；
- 预测结果导入后只出现在 `model_draft`；
- 人工真值没有被覆盖；
- 每次训练和预测都有 run_id、日志、模型记录；
- 同一个项目可以接入不同模型后端。
