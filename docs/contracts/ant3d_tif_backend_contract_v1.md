# TaxaMask TIF Volume Backend Contract v1

Schema name: `ant3d_tif_backend_contract_v1`

This contract connects external 3D volume-segmentation backends to the TaxaMask TIF Volume workflow. It is for material-ID label-volume prediction, not for 2D/STL box or polygon prediction and not for Local Axis proposal generation.

Use this contract when an external backend such as nnU-Net, MONAI, or a custom script needs to prepare TIF training data, train a volume model, or predict a label volume that TaxaMask can import as a reviewable label layer.

For Local Axis Reslice proposal backends, use `docs/contracts/tif_local_axis_backend_contract_v1.md` instead.

## Scope

TaxaMask is responsible for:

- writing `contract.json`;
- creating a run directory with `outputs/` and `logs/`;
- exporting train-ready part/reslice `manual_truth` samples for `prepare_dataset`;
- falling back to train-ready top-level specimen volumes only when no train-ready part/reslice samples exist;
- launching the configured external command;
- reading `result.json`;
- importing prediction volumes only as reviewable label layers plus `raw_ai_prediction_backup`;
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

`prepare_dataset` exports train-ready samples and their `manual_truth` labels into the configured exchange formats. TaxaMask's UI selects all project-wide train-ready part/reslice samples by default; if none exist, it falls back to train-ready top-level specimen volumes. The bundled adapter writes a nnU-Net v2 layout with `imagesTr/`, `labelsTr/`, `dataset.json`, and `nnunet_part_manifest.json`.

`train` reads or prepares the selected dataset and writes a model manifest and model outputs. The bundled nnU-Net v2 adapter performs the full sequence in one training run: export to `nnUNet_raw`, run `nnUNetv2_plan_and_preprocess`, run `nnUNetv2_train`, then write the TaxaMask model manifest. Real nnU-Net v2 training requires at least two exported training samples; `prepare_dataset` can still run with one sample for layout inspection.

`predict` reads selected part, reslice, or top-level volumes and writes prediction label-volume artifacts that TaxaMask imports as reviewable label layers. Part/reslice predictions become `editable_ai_result`; top-level specimen predictions become pending-review `working_edit` and keep a legacy `model_draft` audit record.

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

TaxaMask ships a real nnU-Net v2 contract adapter:

```bash
{python} -m AntSleap.tools.tif_nnunet_v2_backend --contract {contract_json}
```

The adapter is the default preset for new TIF projects, but this contract remains backend-neutral. Users or an Agent may replace the three editable command fields with a MONAI script, a custom 3D U-Net, or another backend as long as it reads this contract and writes the required result JSON.

Useful nnU-Net v2 adapter options include:

```text
--dataset-id 701
--dataset-name TaxaMaskTifVolumeSegmentation
--configuration 3d_fullres
--fold 0
--trainer nnUNetTrainer
--plans nnUNetPlans
--checkpoint checkpoint_final.pth
--device cuda
--gpu 0
--nnunet-work-dir C:/path/to/nnunet_work
--nnunet-raw C:/path/to/nnUNet_raw
--nnunet-preprocessed C:/path/to/nnUNet_preprocessed
--nnunet-results C:/path/to/nnUNet_results
```

The adapter also accepts command prefixes for wrappers, for example `--predict-command "python my_serial_predict.py"`.

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
      "display_name": "ANTSCAN_0001",
      "modality": "micro_ct",
      "part_ids": ["target_part"]
    }
  ],
  "part_samples": [
    {
      "sample_id": "ANTSCAN_0001_target_part_reslice_001",
      "specimen_id": "ANTSCAN_0001",
      "part_id": "target_part",
      "user_defined_part_name": "Target part",
      "reslice_id": "reslice_001",
      "label_schema_id": "target_part_labels",
      "label_schema": {
        "schema_id": "target_part_labels",
        "labels": [
          {"id": 1, "name": "structure_a", "display_name": "Structure A"},
          {"id": 2, "name": "structure_b", "display_name": "Structure B"}
        ]
      },
      "input_volume": {
        "path": "C:/path/specimens/ANTSCAN_0001/parts/target_part/reslices/reslice_001/image.tif",
        "format": "tiff",
        "shape_zyx": [256, 256, 256],
        "dtype": "uint16",
        "orientation_record": {}
      },
      "label_volume": {
        "path": "",
        "format": "",
        "role": "none",
        "shape_zyx": [],
        "dtype": ""
      }
    }
  ],
  "training_config": {
    "model_family": "custom_tif_backend",
    "normalization": "backend_default",
    "augmentation": "backend_default"
  },
  "safety": {
    "protect_manual_truth": true,
    "allow_editable_ai_result_as_training_label": false,
    "allow_model_draft_as_training_label": false,
    "allow_overwrite_outputs": false
  }
}
```

For `prepare_dataset` and `train`, each selected sample must be train-ready. TaxaMask includes a `label_volume` with `role: "manual_truth"` for those actions. A label schema by itself is not a training sample; it only defines numeric label meaning.

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
      "part_id": "target_part",
      "reslice_id": "reslice_001",
      "prediction_id": "predict_20260702_103000_ANTSCAN_0001_target_part",
      "path": "outputs/ANTSCAN_0001_target_part_prediction.ome.zarr",
      "format": "ant3d_volume_sidecar",
      "role": "editable_ai_result"
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
    "input_part_samples": [
      {"specimen_id": "ANTSCAN_0001", "part_id": "target_part", "reslice_id": "reslice_001"}
    ],
    "input_label_role": "none"
  }
}
```

## Prediction Import Rules

TaxaMask imports only artifacts with:

```text
type = prediction_label_volume
role = editable_ai_result
```

Import validation checks:

- `schema_version` is `ant3d_tif_backend_result_v1`;
- `contract_schema_version` is `ant3d_tif_backend_contract_v1`;
- status is `success` or `partial_success`;
- specimen ID exists in the active TIF project;
- part ID exists when `part_id` is present;
- prediction sidecar exists;
- prediction shape matches the selected part, reslice, or top-level input shape.

Imported part predictions are copied into:

```text
specimens/<specimen_id>/parts/<part_id>/labels/raw_ai_prediction_backup.ome.zarr
specimens/<specimen_id>/parts/<part_id>/labels/editable_ai_result.ome.zarr
```

Imported reslice predictions are copied into the corresponding reslice label directory:

```text
specimens/<specimen_id>/parts/<part_id>/reslices/<reslice_id>/labels/raw_ai_prediction_backup.ome.zarr
specimens/<specimen_id>/parts/<part_id>/reslices/<reslice_id>/labels/editable_ai_result.ome.zarr
```

Imported top-level specimen predictions are copied into:

```text
specimens/<specimen_id>/labels/raw_ai_prediction_backup.ome.zarr
specimens/<specimen_id>/labels/working_edit.ome.zarr
specimens/<specimen_id>/labels/model_draft/<prediction_id>.ome.zarr
```

They do not overwrite `manual_truth`. A researcher must review the prediction, edit if needed, and explicitly promote reviewed work to `manual_truth`.

## Training Export Rules

`prepare_dataset` and `train` export all project-wide train-ready part/reslice samples by default. If no train-ready part/reslice samples exist, TaxaMask falls back to train-ready top-level specimen volumes.

A train-ready part/reslice sample should have:

- a part record;
- a part volume;
- a three-point local-axis reslice record and exported reslice image;
- a user label schema;
- a part/reslice `manual_truth` label sidecar;
- matching image and label shape;
- label IDs that exist in the active label schema;
- explicit part train-ready review status.

A train-ready top-level fallback specimen should have:

- a specimen record;
- a working image sidecar;
- a `manual_truth` label sidecar;
- a material map with at least one trainable material;
- matching image and label shape;
- explicit specimen train-ready review status.

Supported exchange formats are:

```text
ome_tiff
tiff
nrrd
mha
nifti
```

The generic part export manifest is typically named:

```text
tif_part_training_export_manifest.json
```

The nnU-Net v2 part export also writes:

```text
imagesTr/
labelsTr/
imagesTs/              # created by the nnU-Net adapter when needed
dataset.json
nnunet_part_manifest.json
splits_final.json
```

The bundled nnU-Net v2 adapter exports `.nii.gz` by default and uses compact nnU-Net label IDs by default. This means TaxaMask label IDs such as `2` and `5` can be remapped to nnU-Net classes `1` and `2` for training, while `nnunet_part_manifest.json` and the model manifest record:

```json
"label_id_mapping": {
  "source_to_nnunet": {"0": 0, "2": 1, "5": 2},
  "nnunet_to_source": {"0": 0, "1": 2, "2": 5}
}
```

Prediction import restores the TaxaMask label IDs before writing the review layer, so the researcher reviews the same label numbers defined in the project label schema. Part/reslice imports write `editable_ai_result`; top-level imports write pending-review `working_edit` and preserve a legacy `model_draft` audit copy.

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
  "trained_parts": [
    {"specimen_id": "ANTSCAN_0001", "part_id": "target_part", "reslice_id": "reslice_001"}
  ],
  "input_scope": "part_reslice",
  "label_role": "manual_truth",
  "label_schema_ids": ["target_part_labels"],
  "weights": {
    "main": "model.pt"
  },
  "nnunet": {
    "dataset_id": 701,
    "dataset_name": "TaxaMaskTifVolumeSegmentation",
    "configuration": "3d_fullres",
    "fold": "0",
    "trainer": "nnUNetTrainer",
    "plans": "nnUNetPlans",
    "checkpoint": "checkpoint_final.pth",
    "raw_root": "C:/path/nnUNet_raw",
    "preprocessed_root": "C:/path/nnUNet_preprocessed",
    "results_root": "C:/path/nnUNet_results",
    "model_output_dir": "C:/path/nnUNet_results/Dataset701_TaxaMaskTifVolumeSegmentation/nnUNetTrainer__nnUNetPlans__3d_fullres",
    "label_id_mode": "compact",
    "label_id_mapping": {
      "source_to_nnunet": {"0": 0, "2": 1},
      "nnunet_to_source": {"0": 0, "1": 2}
    }
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
- treat `working_edit`, `editable_ai_result`, `raw_ai_prediction_backup`, or legacy `model_draft` as training truth by default;
- write final Local Axis reslices;
- silently mix incompatible part label schemas in one nnU-Net dataset;
- mix TIF material IDs with 2D/STL structure labels;
- assume all volumes are micro-CT or all volumes are confocal.

Shape, schema, and provenance failures should stop import and preserve the run artifacts for diagnosis.
