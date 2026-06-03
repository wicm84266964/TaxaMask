# External Blink Backend Contract v1

This contract is for child-part annotation inside an existing parent ROI.
It is separate from `external_backend_contract_v1.md`, which is for whole-image parent-part prediction.

## Input Contract

TaxaMask writes a JSON contract and calls the configured command with `{contract}` or `{contract_json}`.

```json
{
  "schema_version": "taxamask_external_blink_contract_v1",
  "action": "predict_child",
  "backend_id": "custom_blink_backend",
  "project_json": "C:/path/project.json",
  "image_path": "C:/path/specimen.png",
  "parent_part": "Head",
  "child_part": "Mandible",
  "parent_box": [10.0, 20.0, 300.0, 260.0],
  "prediction_json": "C:/path/external_blink_runs/.../predictions/Mandible.prediction.json",
  "model_manifest": "C:/path/model_manifest.json",
  "run_dir": "C:/path/external_blink_runs/...",
  "log_dir": "C:/path/external_blink_runs/.../logs",
  "safety": {
    "output_is_reviewable_draft": true,
    "do_not_write_manual_truth": true
  }
}
```

The external backend should treat `parent_box` as global image coordinates in `[x1, y1, x2, y2]` format.

## Required Output

The external script must write `prediction_json` with this schema:

```json
{
  "schema_version": "taxamask_blink_prediction_v1",
  "child_part": "Mandible",
  "box": [80.0, 120.0, 130.0, 170.0],
  "score": 0.86,
  "model_id": "external_blink/mandible_v1"
}
```

`box` must also be global image coordinates. TaxaMask will use it as a SAM prompt and save the result as a reviewable AI draft, not as manual truth.

## Optional Output

The script may include a polygon:

```json
{
  "polygon": [[80.0, 120.0], [130.0, 120.0], [130.0, 170.0], [80.0, 170.0]]
}
```

Current TaxaMask integration primarily consumes the box and still uses the local SAM path for polygon generation.

## Operational Notes

- The command must include `{contract}` or `{contract_json}`.
- The first implemented action is `predict_child`.
- Training via an external Blink backend can be added later with a separate `train_child` action.
- The external script should not edit the project JSON directly.
