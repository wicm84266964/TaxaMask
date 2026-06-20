# TaxaMask TIF Local Axis Backend Contract v1

日期：2026-06-20

本契约用于把局部轴重切片相关 AI 后端接入 TaxaMask。它服务 `Local Axis Reslice / 局部轴重切片` 工作流，不是脑部专用接口。

Local Axis 后端的任务不是直接生成最终 TIFF，也不是直接修改 TaxaMask 项目 JSON。它只负责提出可复核建议：

```text
global_roi_proposal
local_frame_proposal
```

TaxaMask 负责保存训练素材、调用后端、导入 proposal、人工复核、接受后确定性导出 `image.tif` / `metadata.json` / 可选 `mask.tif`。

## 与现有模型后端规则的关系

本契约沿用 TaxaMask 现有模型接入习惯：

- TaxaMask 写出 `contract.json`。
- 外部脚本通过 `{contract}` 或 `{contract_json}` 接收任务。
- 每次运行都有 `run_dir`、`logs`、`outputs`、`result_json`。
- 训练后写 `model_manifest`。
- 推理结果进入 TaxaMask 作为 reviewable proposal。
- 后端不得直接修改项目 JSON。

它与现有 TIF volume backend 的区别是输出语义不同：

```text
AntSleap/core/tif_backend.py
  -> prediction_label_volume

tif_local_axis_backend_contract_v1
  -> global_roi_proposals / local_frame_proposals
```

## 脚本调用方式

外部脚本必须支持：

```bash
python your_local_axis_backend.py --contract C:/path/to/contract.json
```

TaxaMask 命令配置中可以使用：

```text
{python}
{contract}
{contract_json}
{run_dir}
```

## Schema 名称

```text
contract schema: taxamask_tif_local_axis_backend_contract_v1
result schema:   taxamask_tif_local_axis_backend_result_v1
manifest schema: taxamask_tif_local_axis_model_manifest_v1
```

## Actions

第一版建议支持：

```text
prepare_dataset
train
predict_global_roi
predict_local_frame
predict
```

含义：

- `prepare_dataset`：从 TaxaMask 项目中导出 Local Axis 训练 manifest。
- `train`：读取训练 manifest，训练或微调 Local Axis 模型。
- `predict_global_roi`：从 full volume 提出目标部位候选。
- `predict_local_frame`：从 part volume 提出局部坐标系候选。
- `predict`：组合入口，可以同时返回 global ROI 和 local frame proposals。

## Coordinate Rules

坐标必须显式声明，不能依赖屏幕视角。

通用规则：

- 体数据索引顺序使用 `zyx`。
- bbox 使用 `[z1, y1, x1, z2, y2, x2]`。
- bbox 最小端 inclusive，最大端 exclusive，便于直接对应 NumPy 裁剪。
- full volume proposal 使用 `coordinate_space: "full_volume_voxel_zyx"`。
- part 内 local frame proposal 使用 `coordinate_space: "part_volume_voxel_zyx"`。
- `spacing_zyx` 必须随输入一起提供。
- 脑部模板的 `left_eye` / `right_eye` 以标本自身解剖左右为准，不以屏幕左右为准。

## Contract 示例

```json
{
  "schema_version": "taxamask_tif_local_axis_backend_contract_v1",
  "action": "predict",
  "backend_id": "external_local_axis",
  "project_json": "C:/path/project.ant3d.json",
  "run_id": "predict_20260620_153000_external_local_axis",
  "run_dir": "C:/path/project/runs/local_axis/predict_20260620_153000_external_local_axis",
  "dataset_dir": "C:/path/project/runs/local_axis/.../dataset",
  "output_dir": "C:/path/project/runs/local_axis/.../outputs",
  "result_json": "C:/path/project/runs/local_axis/.../result.json",
  "log_dir": "C:/path/project/runs/local_axis/.../logs",
  "model_manifest": "C:/path/models/local_axis/model_manifest.json",
  "template_id": "head",
  "target_part_name": "head",
  "specimens": [
    {
      "specimen_id": "ANTSCAN_0001",
      "input_volume": {
        "path": "C:/path/specimens/ANTSCAN_0001/working_volume.ome.zarr",
        "format": "ome.zarr",
        "shape_zyx": [1600, 900, 900],
        "dtype": "uint16",
        "spacing_zyx": [2.0, 2.0, 2.0],
        "spacing_unit": "micrometer",
        "orientation": "source_tiff_pages"
      },
      "parts": [
        {
          "part_id": "head",
          "part_name": "head",
          "part_image": {
            "path": "C:/path/specimens/ANTSCAN_0001/parts/head/image.ome.zarr",
            "format": "ome.zarr",
            "shape_zyx": [320, 260, 240],
            "dtype": "uint16",
            "spacing_zyx": [2.0, 2.0, 2.0]
          },
          "part_mask": {
            "path": "C:/path/specimens/ANTSCAN_0001/parts/head/mask.ome.zarr",
            "format": "ome.zarr",
            "shape_zyx": [320, 260, 240],
            "dtype": "uint8",
            "available": true
          },
          "parent_bbox_zyx": [200, 310, 180, 520, 570, 420]
        }
      ]
    }
  ],
  "training_config": {
    "model_family": "local_axis",
    "global_roi_enabled": true,
    "local_frame_enabled": true,
    "normalization": "backend_default",
    "augmentation": "backend_default"
  },
  "safety": {
    "output_is_reviewable_proposal": true,
    "do_not_write_project_json": true,
    "do_not_write_manual_truth": true,
    "do_not_create_final_reslice": true,
    "allow_overwrite_outputs": false
  }
}
```

## Result 示例

后端必须把结果写到 `contract["result_json"]`。

```json
{
  "schema_version": "taxamask_tif_local_axis_backend_result_v1",
  "contract_schema_version": "taxamask_tif_local_axis_backend_contract_v1",
  "status": "success",
  "action": "predict",
  "backend_id": "external_local_axis",
  "run_id": "predict_20260620_153000_external_local_axis",
  "artifacts": [
    {
      "type": "global_roi_proposals",
      "path": "outputs/global_roi_proposals.json",
      "format": "json"
    },
    {
      "type": "local_frame_proposals",
      "path": "outputs/local_frame_proposals.json",
      "format": "json"
    }
  ],
  "metrics": {
    "summary": {
      "specimen_count": 1,
      "global_roi_proposal_count": 1,
      "local_frame_proposal_count": 1
    }
  },
  "warnings": [],
  "errors": [],
  "provenance": {
    "started_at": "2026-06-20T15:30:00+08:00",
    "finished_at": "2026-06-20T15:31:10+08:00",
    "model_manifest": "C:/path/models/local_axis/model_manifest.json",
    "input_specimens": ["ANTSCAN_0001"],
    "input_label_role": "none"
  }
}
```

## Global ROI Proposals

`global_roi_proposals.json` 示例：

```json
{
  "schema_version": "taxamask_tif_local_axis_global_roi_proposals_v1",
  "template_id": "head",
  "model_id": "external_local_axis/head_roi_v1",
  "proposals": [
    {
      "global_proposal_id": "roi_ANTSCAN_0001_001",
      "specimen_id": "ANTSCAN_0001",
      "template_id": "head",
      "coordinate_space": "full_volume_voxel_zyx",
      "bbox_zyx": [200, 310, 180, 520, 570, 420],
      "center_zyx": [360.0, 440.0, 300.0],
      "confidence": 0.82,
      "model_id": "external_local_axis/head_roi_v1",
      "model_version": "v1",
      "status": "proposed",
      "hard_case_flags": ["transverse_source_slices"]
    }
  ]
}
```

TaxaMask 导入规则：

- 缺少 `bbox_zyx` 和 `center_zyx` 的记录应拒绝。
- `status` 默认归一化为 `proposed`。
- 导入后只写入 specimen 级 proposal。
- 接受后才允许创建或更新 part。

## Local Frame Proposals

`local_frame_proposals.json` 示例：

```json
{
  "schema_version": "taxamask_tif_local_axis_frame_proposals_v1",
  "template_id": "head",
  "model_id": "external_local_axis/head_frame_v1",
  "proposals": [
    {
      "frame_proposal_id": "frame_ANTSCAN_0001_head_001",
      "specimen_id": "ANTSCAN_0001",
      "part_id": "head",
      "template_id": "head",
      "coordinate_space": "part_volume_voxel_zyx",
      "origin_zyx": [160.0, 130.0, 120.0],
      "output_axis_start_zyx": [80.0, 130.0, 120.0],
      "output_axis_end_zyx": [240.0, 130.0, 120.0],
      "roll_reference": {
        "pair_id": "left_eye_right_eye",
        "point_a": {
          "role": "left_eye",
          "zyx": [150.0, 105.0, 95.0],
          "anatomical_side": "left"
        },
        "point_b": {
          "role": "right_eye",
          "zyx": [151.0, 157.0, 94.0],
          "anatomical_side": "right"
        }
      },
      "local_frame": {
        "origin_zyx": [160.0, 130.0, 120.0],
        "x_axis": [0.0, 1.0, 0.0],
        "y_axis": [0.0, 0.0, 1.0],
        "z_axis": [1.0, 0.0, 0.0],
        "output_axis": "z_axis"
      },
      "confidence": 0.76,
      "landmark_scores": {
        "origin": 0.82,
        "output_axis_start": 0.73,
        "output_axis_end": 0.78,
        "left_eye": 0.71,
        "right_eye": 0.75
      },
      "missing_landmarks": [],
      "model_id": "external_local_axis/head_frame_v1",
      "model_version": "v1",
      "status": "proposed",
      "hard_case_flags": []
    }
  ]
}
```

TaxaMask 导入规则：

- 缺少 `origin_zyx` 或 output axis 的记录应拒绝。
- `roll_reference` 可以缺失，但必须标记 `missing_landmarks`，UI 应显示 needs review。
- `local_frame` 可由 TaxaMask 根据 origin、output axis、roll reference 重新计算；后端给出的 `local_frame` 作为参考和审计字段。
- 导入后只写入 part 级 proposal。
- 接受后才允许执行正式 reslice export。

## Model Manifest

训练结束后，后端应写 `model_manifest`：

```json
{
  "schema_version": "taxamask_tif_local_axis_model_manifest_v1",
  "model_id": "external_local_axis/head_frame_v1",
  "backend_id": "external_local_axis",
  "template_id": "head",
  "model_type": "local_frame",
  "created_at": "2026-06-20T16:00:00+08:00",
  "trained_from": {
    "training_manifest": "C:/path/dataset/local_axis_training_manifest.json",
    "sample_count": 120,
    "usable_sample_count": 103
  },
  "input_contract": {
    "input_space": "part_volume_voxel_zyx",
    "requires_part_mask": false,
    "requires_spacing": true
  },
  "output_contract": {
    "artifact_type": "local_frame_proposals",
    "schema_version": "taxamask_tif_local_axis_frame_proposals_v1"
  },
  "weights": {
    "main": "model.pt"
  },
  "notes": ""
}
```

## 训练数据规则

训练 manifest 只能默认导出人工确认并可训练的记录：

```text
human_confirmed = true
usable_for_training = true
```

AI proposal 未经复核前不能作为训练真值。用户编辑并接受后，可以记录为：

```text
source: AI proposed + human edited
```

这样可以保留模型贡献，同时保证训练标签最终来自人工确认。

## Operational Notes

- 第一版可以先支持外部脚本和 JSON proposal import。
- 内置 baseline 也必须按 proposal 规则进入 review queue。
- high confidence proposal 也不能静默导出正式 TIFF。
- 外部脚本报错时，TaxaMask 应保留 `contract.json`、`logs/*stderr.log`、`result.json` 或缺失结果状态，方便后续排错。
- 本契约不规定具体模型结构；3D U-Net、heatmap landmark detector、检测模型或组合模型都可以接入，只要输出符合 proposal schema。
