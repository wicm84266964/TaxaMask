# TaxaMask 外部模型后端脚本契约 v1

本契约用于把你自己的训练或推理脚本接入 TaxaMask。它可以作为开发者或辅助智能体改造 YOLO、Detectron、Mask R-CNN、SAM2 等模型脚本时的接口说明。

TaxaMask 不需要理解你的模型内部结构，只负责三件事：

1. 写出 `contract.json`。
2. 启动你的外部脚本。
3. 读取你的 `taxamask_prediction_v1` 或 `taxamask_model_manifest_v1` 结果。

## 脚本调用方式

每个脚本必须接受：

```bash
python your_script.py --contract /path/to/contract.json
```

在 TaxaMask 的命令配置中可以使用：

- `{python}`
- `{contract_json}` 或 `{contract}`
- `{run_dir}`

`contract.json` 中的 `action` 会是：

- `prepare_dataset`
- `train`
- `predict`

你可以用一个脚本处理三个 action，也可以写三个脚本。

## contract.json 字段

```json
{
  "schema_version": "taxamask_external_backend_contract_v1",
  "action": "train",
  "backend_id": "custom_external_backend",
  "project_json": "/path/to/project.json",
  "taxonomy": ["Leaf", "Flower", "Fruit"],
  "locator_scope": ["Leaf"],
  "run_dir": "/path/to/external_runs/20260503_103000_train_custom_external_backend",
  "dataset_dir": "/path/to/external_runs/.../dataset",
  "model_dir": "/path/to/external_runs/.../model",
  "image_path": "",
  "prediction_json": "",
  "model_manifest": "/path/to/external_runs/.../model/taxamask_model_manifest.json",
  "log_dir": "/path/to/external_runs/.../logs"
}
```

## prepare_dataset 要求

读取 `project_json`，把 TaxaMask 项目中的标注转换为你的模型训练格式，写入 `dataset_dir`。

建议同时写：

```text
dataset_dir/dataset_manifest.json
```

## train 要求

读取 `dataset_dir`，训练你的模型，把模型文件写入 `model_dir`。

训练结束必须写：

```json
{
  "schema_version": "taxamask_model_manifest_v1",
  "model_id": "custom_external_backend/20260503_103000",
  "backend_id": "custom_external_backend",
  "taxonomy": ["Leaf", "Flower", "Fruit"],
  "locator_scope": ["Leaf"],
  "label_order": ["Leaf", "Flower", "Fruit"],
  "weights": {
    "main": "model.pt"
  }
}
```

保存路径必须是 `contract["model_manifest"]`。

## predict 要求

读取：

- `contract["image_path"]`
- `contract["model_manifest"]`
- `contract["taxonomy"]`

输出路径必须是 `contract["prediction_json"]`。

输出格式：

```json
{
  "schema_version": "taxamask_prediction_v1",
  "image_path": "/path/to/image.jpg",
  "polygons": {
    "Leaf": [[120, 80], [500, 90], [480, 430]]
  },
  "boxes": {
    "Leaf": [120, 80, 500, 430]
  },
  "scores": {
    "Leaf": 0.91
  },
  "model_id": "custom_external_backend/20260503_103000"
}
```

规则：

- `polygons` 的键必须属于当前项目 `taxonomy`。
- `boxes` 可选，有 polygon 时 TaxaMask 会直接作为候选 mask 导入。
- TaxaMask 默认不覆盖人工标注，只导入新候选。
- 外部脚本报错时，TaxaMask 会保留 `logs/*stderr.log` 和 `contract.json`，用于研究者、开发者或辅助智能体继续排查脚本。
