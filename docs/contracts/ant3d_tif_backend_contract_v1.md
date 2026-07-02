# TaxaMask TIF Volume Backend Contract v1

Schema name: `ant3d_tif_backend_contract_v1`

This contract connects external 3D volume-segmentation backends to the TaxaMask TIF Volume workflow. It is for material-ID label-volume prediction, not for 2D/STL box or polygon prediction and not for Local Axis proposal generation.

Use this contract when an external backend such as nnU-Net, MONAI, or a custom script needs to prepare TIF training data, train a volume model, or predict a label volume that TaxaMask can import as `model_draft`.

For Local Axis Reslice proposal backends, use `docs/contracts/tif_local_axis_backend_contract_v1.md` instead.

## Scope

TaxaMask is responsible for:

- writing `contract.json`;
- creating a run directory with `outputs/` and `logs/`;
- exporting train-ready specimens from `manual_truth` for `prepare_dataset`;
- launching the configured external command;
- reading `result.json`;
- importing prediction volumes only as `model_draft`;
- recording run and model provenance.

The external backend is responsible for:

- reading the contract JSON path passed through `{contract}` or `{contract_json}`;
- writing artifacts only under the contract output paths;
- writing the required result JSON;
- leaving source TIF, AMIRA files, `working_edit`, and `manual_truth` unchanged.

## Actions

Supported actions:

```text
prepare_dataset
train
predict
```

`prepare_dataset` exports train-ready specimens and their `manual_truth` labels into the configured exchange formats.

`train` reads a prepared dataset and writes a model manifest and model outputs.

`predict` reads specimen working volumes and writes prediction label-volume artifacts that TaxaMask imports as `model_draft`.

## Command Template

TaxaMask command fields must include one of these placeholders:

```text
{contract}
{contract_json}
```

Common template:

```bash
{python} your_tif_backend.py --contract {contract_json}
```

Available placeholders:

```text
{python}
{contract}
{contract_json}
{run_dir}
```

## Contract Example

```json
{
  "schema_version": "ant3d_tif_backend_contract_v1",
  "action": "predict",
  "backend_id": "custom_tif_backend",
  "project_json": "C:/path/project.tif_sqlite_manifest.json",
  "run_id": "predict_20260702_103000_custom_tif_backend",
  "run_dir": "C:/path/project/runs/predict/predict_20260702_103000_custom_tif_backend",
  "dataset_dir": "C:/path/project/runs/prepare_dataset/.../dataset",
  "model_manifest": "C:/path/model_manifest.json",
  "output_dir": "C:/path/project/runs/predict/.../outputs",
  "result_json": "C:/path/project/runs/predict/.../result.json",
  "specimens": [
    {
      "specimen_id": "ANTSCAN_0001",
      "modality": "micro_ct",
      "input_volume": {
        "path": "C:/path/specimens/ANTSCAN_0001/working/image.ome.zarr",
        "format": "ome.zarr",
        "shape_zyx": [1600, 900, 900],
        "dtype": "uint16",
        "spacing_zyx": [2.0, 2.0, 2.0],
        "spacing_unit": "micrometer",
        "orientation": "source_tiff_pages"
      },
      "label_volume": {
        "path": "",
        "format": "",
        "role": "none",
        "shape_zyx": [],
        "dtype": ""
      },
      "material_map": "C:/path/specimens/ANTSCAN_0001/material_map.json"
    }
  ],
  "training_config": {
    "model_family": "custom_tif_backend",
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

For `prepare_dataset` and `train`, each selected specimen must be train-ready. TaxaMask includes a `label_volume` with `role: "manual_truth"` for those actions.

For `predict`, `label_volume.role` is `none`; the backend should predict from `input_volume` and must not require `manual_truth`.

## Result Example

The backend must write the result to `contract["result_json"]`.

```json
{
  "schema_version": "ant3d_tif_backend_result_v1",
  "contract_schema_version": "ant3d_tif_backend_contract_v1",
  "status": "success",
  "action": "predict",
  "backend_id": "custom_tif_backend",
  "run_id": "predict_20260702_103000_custom_tif_backend",
  "artifacts": [
    {
      "type": "prediction_label_volume",
      "specimen_id": "ANTSCAN_0001",
      "prediction_id": "predict_20260702_103000_ANTSCAN_0001",
      "path": "outputs/ANTSCAN_0001_prediction.ome.zarr",
      "format": "ome.zarr",
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
    "started_at": "2026-07-02T10:30:00+08:00",
    "finished_at": "2026-07-02T10:42:00+08:00",
    "model_manifest": "C:/path/model_manifest.json",
    "input_specimens": ["ANTSCAN_0001"],
    "input_label_role": "none"
  }
}
```

## Prediction Import Rules

TaxaMask imports only artifacts with:

```text
type = prediction_label_volume
role = model_draft
```

Import validation checks:

- `schema_version` is `ant3d_tif_backend_result_v1`;
- `contract_schema_version` is `ant3d_tif_backend_contract_v1`;
- status is `success` or `partial_success`;
- specimen ID exists in the active TIF project;
- prediction sidecar exists;
- prediction shape matches the specimen working volume shape.

Imported predictions are copied into:

```text
specimens/<specimen_id>/labels/model_draft/<prediction_id>.ome.zarr
```

They do not overwrite `manual_truth`. A researcher must review the prediction, edit if needed, and explicitly promote reviewed work to `manual_truth`.

## Training Export Rules

`prepare_dataset` exports only train-ready specimens by default. A train-ready specimen should have:

- working image sidecar;
- `manual_truth` label sidecar;
- material map;
- matching image and label shape;
- at least one trainable material;
- explicit train-ready review status.

Supported exchange formats are:

```text
ome_tiff
tiff
nrrd
mha
nifti
```

The export manifest is typically named:

```text
tif_training_export_manifest.json
```

## Model Manifest

Training backends should write a model manifest using:

```text
schema_version: ant3d_tif_model_manifest_v1
```

Recommended fields:

```json
{
  "schema_version": "ant3d_tif_model_manifest_v1",
  "model_id": "custom_tif_backend/model_20260702_103000",
  "backend_id": "custom_tif_backend",
  "model_family": "custom_tif_backend",
  "created_at": "2026-07-02T10:30:00+08:00",
  "trained_specimens": ["ANTSCAN_0001"],
  "label_role": "manual_truth",
  "weights": {
    "main": "model.pt"
  },
  "metrics": {
    "summary": {}
  }
}
```

## Safety

External TIF backends must not:

- modify source TIF stacks;
- modify AMIRA/Avizo source files;
- overwrite `manual_truth`;
- treat `model_draft` as training truth by default;
- write final Local Axis reslices;
- mix TIF material IDs with 2D/STL structure labels;
- assume all volumes are micro-CT or all volumes are confocal.

Shape, schema, and provenance failures should stop import and preserve the run artifacts for diagnosis.
