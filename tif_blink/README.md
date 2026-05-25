# TIF-Blink

TIF-Blink is an experimental brain-region segmentation framework for TaxaMask TIF volume work.

It is not a direct port of the 2D/STL Blink workbench. The migrated idea is:

- Blink-style inside/outside masked views.
- Boundary uncertainty bands instead of SAM prompt boxes.
- U-Net/nnU-Net-style multi-class segmentation.
- Prediction outputs remain drafts and must not overwrite `manual_truth`.

## First Prototype Scope

- Generate boundary bands from material-ID labels.
- Create `normal`, `inside_band`, and `outside_band` training views.
- Train a small 2.5D U-Net from adjacent TIF slices.
- Weight loss on boundary bands to target over-expanded brain regions and ambiguous borders.
- Optionally train grouped `normal / inside_band / outside_band` views with boundary-focused supervision and consistency loss.
- Track boundary-band Dice separately from whole-slice Dice.
- Optionally use boundary-density balanced slice sampling.
- Map TaxaMask material IDs such as `5` or `37` to compact model class indices during training.
- Save `best.pt`, `last.pt`, `history.json`, and `model_manifest.json` for auditable runs.
- Restore checkpoints for whole-volume draft prediction.
- Load train-ready TaxaMask TIF specimens from `manual_truth` and save predictions only as `model_draft`.

This package is intentionally independent from the main GUI while the algorithm is still experimental.

## Safety Defaults

Boundary bands are generated from human labels. They are used for Blink-style masked views and boundary-weighted loss, but they are not included as model input channels by default because inference will not have human boundary bands available.

Grouped-view training is opt-in through `TifBlinkTrainConfig(use_grouped_views=True)` or the CLI `--grouped-views` flag. The simple single-view training path remains available for smoke tests and baseline comparisons.

See `TRAINING_DESIGN_zh.md` for the current implementation plan.
