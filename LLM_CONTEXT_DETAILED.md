# TaxaMask Developer Preview LLM Context

> Target: advanced LLM assistants and developers maintaining the developer preview branch.
> Branch scope: `codex/antscan-stl-tif-rearchitecture`.
> Last synchronized: 2026-06-27.

This file is the current-state handoff document. It is not a changelog. Do not append dated development logs here. Keep it focused on the program state that an agent needs in order to diagnose, modify, and safely operate TaxaMask.

## 1. Product Scope

TaxaMask is a desktop research workbench for morphology annotation, literature evidence handling, model-assisted review, and dataset export.

The developer preview branch contains two maintained routes:

- 2D/STL morphology route: PDF evidence, specimen images, STL-rendered 2D views, VLM/SAM drafts, parent/child part annotation, Blink experts, external model backends, and COCO/YOLO/JSONL export.
- TIF/CT route: continuous TIFF stack import, TIF specimen projects, material/label layers, part ROI and part volume extraction, GPU volume preview, Local Axis Reslice, and training-material capture for future local-axis automation.

Branch release notes are kept under `docs/releases/`. The full 1.2.0 TIF developer-preview release is documented in `docs/releases/1.2.0-tif-preview.md`.

The stable `main` branch keeps its own main-only documentation. Do not copy TIF/CT wording into main docs unless the user explicitly decides to promote that route.

## 2. Documentation Roles

- `README.md`: public GitHub landing page and installation entrypoint for this branch.
- `README_zh.md`: Chinese public branch overview.
- `TaxaMask使用手册.md`: researcher-facing Chinese operating manual.
- `LLM_CONTEXT_DETAILED.md`: current technical handoff for Agent/LLM/developer use.
- `docs/contracts/`: backend contracts that are safe to expose publicly.
- Internal design drafts, task handoffs, local agent sessions, local runtime configs, generated data, model weights, private projects, databases, and CT/TIF stacks must not be published.

The root `CHANGELOG_zh.md` is intentionally not part of this developer-preview public branch. Historical development logs should stay private or be maintained separately.

## 3. Safety Model

AI outputs are draft material until a researcher confirms them.

Do not let automated tools overwrite:

- manual 2D polygons or confirmed masks
- confirmed VLM/SAM drafts
- `manual_truth` TIF label volumes
- source TIFF stacks
- part volumes, part masks, contours, or extraction metadata
- exported Local Axis reslices, unless the user explicitly performs a destructive delete

For TIF labels, model predictions should land in `model_draft`, not `manual_truth`.

For Local Axis automation, future model outputs should be proposals that require review. They should not directly create final reslice outputs without explicit researcher confirmation.

## 4. Launch And Runtime

Primary launch scripts:

- `启动TaxaMask.bat`
- `启动TaxaMask.sh`
- `tools/start_antsleap_high_performance_gpu.ps1`
- `启动AntCode修复面板.bat`
- `启动AntCode修复面板.sh`

The Windows launcher prefers a Conda environment named `taxamask`, then falls back to older `antsleap` environment names. If `TAXAMASK_PYTHON_EXE` is set, it wins.

This developer branch enables the TIF workflow by default through `TAXAMASK_ENABLE_TIF_WORKFLOW=1` in the launch scripts unless the user overrides it.

For TIF/CT GPU preview, the active Python executable should be assigned to the NVIDIA high-performance GPU in Windows Graphics settings or NVIDIA Control Panel. The app can help set OpenGL-related environment variables, but Windows hybrid-GPU routing ultimately depends on the selected `python.exe` path and driver policy.

The TIF workbench status text and renderer overlay should be used to confirm whether rendering is using NVIDIA, integrated graphics, or CPU fallback.

## 5. Agent Center

The embedded Agent Center uses the first-party `vendor/ant-code/` runtime.

Important files:

- `AntSleap/ui/taxamask_agent_panel.py`
- `AntSleap/core/agent_context_routes.py`
- `vendor/ant-code/`

Normal Ask Agent behavior sends compact workbench context, not full private project data. It should include diagnostic route, focused source references, artifact hints, and safety notes.

If the GUI cannot start, use the recovery dashboard script. It avoids importing the PySide6 GUI and starts the browser-based Ant-Code dashboard.

Do not send API keys, private gateway URLs, large project JSON, database contents, TIF sidecars, or full local logs into prompts unless the user explicitly approves a specific diagnostic extraction.

## 6. 2D/STL Route

Main source areas:

- `AntSleap/main.py`
- `AntSleap/core/project.py`
- `AntSleap/ui/canvas.py`
- `AntSleap/core/vlm_preannotation.py`
- `AntSleap/core/sam_helper.py`
- `AntSleap/core/model_profiles.py`
- `AntSleap/core/external_backend.py`
- `AntSleap/core/external_blink_backend.py`
- `AntSleap/core/cascade_routes.py`
- `AntSleap/ui/blink_lab.py`

Current researcher-facing route:

1. Open or create a 2D/STL project.
2. Import specimen images, PDF-derived candidates, or STL-rendered 2D views.
3. Use VLM boxes and SAM masks only as drafts.
4. Confirm formal annotations manually.
5. Use Child Expert Session / Blink for parent-context child-part refinement.
6. Train or route internal/external models.
7. Export reviewed datasets.

Storage state:

- New 2D projects are SQLite-backed by default.
- The project entry file is `*.sqlite_manifest.json`; it points to the adjacent `*.taxamask.sqlite` database.
- Opening an old 2D JSON project prompts for migration to SQLite, creates a migration report and legacy JSON backup, then opens the manifest.
- Opening the same old JSON again should reuse the existing migrated manifest instead of rerunning migration.
- If a user accidentally selects the SQLite database file itself, the GUI tries to locate the matching manifest and opens that entry file.

Important semantics:

- STL is handled as rendered 2D review images, not direct mesh painting.
- VLM boxes are low-priority drafts.
- Model predictions may replace unconfirmed AI drafts, but not manual or confirmed labels.
- Child Expert Session is the user-facing wording. `Blink` remains in code for historical compatibility.
- Large projects should avoid eager first-image loading, unnecessary model warmup, and repeated full-tree refreshes.

## 7. PDF Evidence Route

Main source areas:

- `AntSleap/ui/pdf_processing_widget.py`
- `core/pdf_processor/`
- `tools/agentic/`
- `screener_configs/`
- `part_description_configs/`

PDF processing creates evidence, candidates, captions, figure clips, and provenance. It does not create training truth automatically.

Expected Agent behavior:

- Work one stage at a time: key/model readiness, screening criteria, figure-review criteria, then run/result diagnosis.
- Keep provenance visible: PDF path, page, caption, nearby text, profile, and extraction status.
- Do not merge PDF output into labels without researcher review.

## 8. TIF/CT Project Model

Main source areas:

- `AntSleap/core/tif_project.py`
- `AntSleap/core/tif_volume_io.py`
- `AntSleap/core/tif_backend.py`
- `AntSleap/ui/tif_workbench.py`
- `docs/contracts/ant3d_tif_backend_contract_v1.md`

The TIF project is independent from the 2D/STL project model.

Storage state:

- New TIF projects are SQLite-backed by default.
- The TIF project entry file is `*.tif_sqlite_manifest.json`; it points to the adjacent `*.taxamask_tif.sqlite` database.
- Old TIF JSON projects can migrate to SQLite with a progress dialog.
- TIF sidecar volumes, labels, part volumes, masks, contours, and reslice outputs remain in normal project folders. The database stores project index records, paths, metadata, review state, and provenance.
- If a user accidentally selects the TIF SQLite database file itself, the GUI tries to locate and open the matching manifest.

Core records:

- specimen records
- sidecar volume paths
- material maps
- label roles: `working_edit`, `manual_truth`, `model_draft`
- part records
- part ROI records
- part masks and contours
- extraction metadata
- Local Axis reslice records

Legacy TIF project JSON is now a migration source rather than the preferred active project store. Large volumes live in project sidecar directories.

Plain TIFF stack import creates an image volume but not trusted training truth. AMIRA-style imports can provide label volumes, but label shape/material consistency must be checked before treating a specimen as train-ready.

## 9. TIF Workbench

Main file:

- `AntSleap/ui/tif_workbench.py`

The TIF workbench supports:

- opening/importing TIF projects
- specimen tree navigation
- slice review across Z/Y/X axes
- material map inspection/editing with visible swatches and color picker support
- explicit annotation tools: brush, eraser, picker, and pan
- annotation cursor radius preview for brush/eraser/picker
- save-status feedback for dirty working-edit slices
- undo/redo and annotation shortcuts
- ROI and key-slice contour workflow
- part volume creation
- mask preview and accepted part mask writing
- GPU/CPU volume preview
- full volume and part volume view modes
- Local Axis Reslice in the right-side work area
- training-material manifest export for Local Axis data capture

The TIF workbench should remain a specialized TIF route. Do not force its controls into the 2D/STL main labeling workflow.

## 10. Part ROI And Part Volume Extraction

Main files:

- `AntSleap/core/tif_part_extraction.py`
- `AntSleap/core/tif_project.py`
- `AntSleap/ui/tif_workbench.py`

Important functions:

- `crop_volume_to_part(...)`
- `add_rectangular_keyframe(...)`
- `add_polygon_keyframe(...)`
- `interpolate_masks_from_keyframes(...)`
- `build_preview_mask_from_contours(...)`
- `write_part_mask(...)`

The intended workflow is:

1. Use full volume / slices / 3D preview to locate a target part.
2. Draw ROI and key-slice contours.
3. Preview interpolated mask.
4. Accept part mask.
5. Crop part volume.
6. Work on the part volume rather than reslicing the full source TIFF.

Part outputs live under the selected specimen and part. The source TIFF stack must stay unchanged.

## 11. GPU Volume Preview

Main file:

- `AntSleap/ui/tif_gpu_volume_canvas.py`

Important class:

- `TifGpuVolumeOffscreenWidget`

Important methods:

- `set_volume_data(...)`
- `set_mask_data(...)`
- `set_render_state(...)`
- `volume_shape_scale(...)`

Current preview behavior:

- Offscreen GPU rendering is the preferred path to reduce conflicts between Qt WebEngine / Ant-Code and OpenGL canvas composition.
- CPU fallback exists for unsupported or failed GPU rendering, but it is not the target for heavy CT inspection.
- The renderer supports volume tint/transfer settings, mask boundary display, masked image display, zoom, pan, view rotation, near/front clipping, observation-side clip plane, and local-axis overlays.
- The clip-plane section is display-only. It should not mutate source data, labels, part volumes, masks, or reslice outputs.
- Section rendering is intentionally texture-like and integrated with the current volume tint, because the user needs fine local structure inspection without a detached CT-slice panel feel.
- Missing shader uniforms can trigger GPU fallback. If a visual change adds shader parameters, update both offscreen and embedded GPU paths and add tests.

Performance expectations:

- Dynamic slider/drag interactions should use lighter rendering when possible.
- Static inspection can use higher-quality display, but it should not over-smooth local structures until they look blurrier than the moving preview.
- Zoom should preserve as much local detail as the loaded preview texture allows. It cannot recover detail removed by prior downsampling.

## 12. Local Axis Reslice

Main files:

- `AntSleap/core/tif_local_axis_reslice.py`
- `AntSleap/core/tif_local_axis_ai.py`
- `AntSleap/core/tif_local_axis_batch.py`
- `AntSleap/core/tif_local_axis_signal.py`
- `AntSleap/ui/tif_workbench.py`
- `docs/contracts/tif_local_axis_backend_contract_v1.md`

Local Axis Reslice is a generic part-volume workflow. It is not Brain Reslice. The first practical template is head/brain-oriented, but module names and data fields must stay generic.

Current researcher workflow:

1. Create and select a part volume.
2. Switch to part 3D preview.
3. Show source/output axes.
4. Copy locked source Z axis into an editable output Z axis draft.
5. Drag output-axis endpoints or drag the axis body inside the 3D preview.
6. Enable observation-side clip plane.
7. Pick roll reference A/B on the clip plane.
8. Check right-side summary and optional axis details.
9. Export confirmed reslice.
10. Select `part -> Reslices -> reslice item` to review the exported reslice image.

Critical semantics:

- Source Z axis is a locked reference showing original TIFF slice direction.
- Editable output Z axis is the actual reslice advance axis.
- Roll reference point pair is for in-plane direction standardization and review. It is not a second slicing axis.
- Reslice direction is strictly based on the editable output Z axis.
- Grayscale image reslicing uses linear interpolation.
- Mask/label reslicing uses nearest-neighbor interpolation.
- Export writes a new reslice item. It must not delete or overwrite source TIFF, original part volume, part mask, contours, or extraction metadata.

Reslice outputs:

- `specimens/<specimen_id>/parts/<part_id>/reslices/<reslice_id>/image.tif`
- `specimens/<specimen_id>/parts/<part_id>/reslices/<reslice_id>/metadata.json`
- optional `mask.tif`
- project record in `part.metadata.local_axis_reslices[]`

The left tree structure is:

```text
specimen
  part
    Reslices
      reslice item
```

Selecting a part loads the original part volume. Selecting a reslice item loads the exported `image.tif` and optional `mask.tif`.

## 13. Local Axis Training Material Capture

Current TIF/CT automation stance:

- Data capture is in scope.
- Fully integrated training/inference is not yet the daily UI workflow.
- Backend scaffolding and contracts may exist, but researcher-facing operation should remain review-first.

Each exported Local Axis reslice should record a `training_sample` both in `metadata.json` and in the project reslice record.

The sample should include:

- specimen and part identifiers
- template identifier when relevant
- source part image path, shape, and spacing
- mask availability
- parent bounding box or part extraction context
- locked source axis
- initial editable axis
- final editable axis
- origin
- roll reference point pair
- local frame
- reslice parameters
- output paths
- human confirmation flags
- `usable_for_training`
- operator notes
- timestamps
- software version
- provenance

`export_local_axis_training_manifest(...)` should prefer saved `training_sample` records instead of reconstructing loose fields. This keeps future AI training data auditable.

Future training/inference should follow the 2D external-backend style:

1. TaxaMask exports a contract and dataset manifest.
2. External backend trains or predicts.
3. Backend outputs proposals.
4. Researcher reviews proposals.
5. Only accepted proposals can drive formal output.

## 14. Local Axis Signals And QC

Main file:

- `AntSleap/core/tif_local_axis_signal.py`

Body signal and QC plots are auxiliary only.

Reasoning:

- AntScan specimens vary in posture, container shape, and source slice direction.
- Small individuals may be scanned roughly head-to-tail or tail-to-head in tubes.
- Larger individuals may be oriented irregularly in box-like containers.
- Some larger individuals are cut transversely or obliquely so head, thorax, and abdomen may appear together.
- Therefore body signal should not be treated as the primary anatomical localization algorithm.

Allowed uses:

- navigation hints
- anomaly detection
- sample quality checks
- rough source-Z signal interpretation

Avoid showing heavy QC panels by default in the main TIF workbench.

## 15. External Backend Contracts

2D/STL contracts:

- `docs/contracts/external_backend_contract_v1.md`
- `docs/contracts/external_blink_backend_contract_v1.md`

TIF contracts:

- `docs/contracts/ant3d_tif_backend_contract_v1.md`
- `docs/contracts/tif_local_axis_backend_contract_v1.md`

Contract rules:

- Commands should receive paths to contract JSON, not private data pasted into prompts.
- Backend result JSON must declare schema/version/status.
- Model outputs should be drafts/proposals.
- Importers should validate shape, material ID, schema version, and provenance.
- External backend failures should be recorded without corrupting project state.

## 16. Ask Agent Routing

Main file:

- `AntSleap/core/agent_context_routes.py`

Expected route keys:

- `general_settings`
- `stl_model_settings`
- `tif_model_settings`
- `labeling`
- `blink`
- `tif_volume`
- `pdf_evidence`

Route hints should point to current sections in this file, source files, and public contracts. Do not point Agent prompts at obsolete changelog headings.

Ask Agent context should stay compact. It should help the agent know what to inspect, not dump project files or private data.

## 17. Validation Expectations

Use focused tests when modifying a route.

Common commands:

```powershell
python -m unittest tests.test_agent_context_routes
python -m unittest tests.test_tif_project tests.test_tif_part_extraction tests.test_tif_local_axis_reslice tests.test_tif_local_axis_batch tests.test_tif_local_axis_ai
python -m unittest tests.test_tif_workbench tests.test_tif_gpu_volume_canvas
python -m unittest tests.test_gui_smoke
python -m compileall AntSleap
git diff --check
```

For TIF renderer changes, validate both:

- GPU path does not fall back unexpectedly.
- CPU fallback still gives a usable preview when GPU is unavailable.

For Local Axis changes, validate:

- source Z and output Z overlay labels do not overlap.
- output axis endpoint/body dragging updates the draft and summary.
- roll reference picking uses the observation-side clip plane.
- exported reslice item loads its own `image.tif`.
- source TIFF and original part volume remain unchanged.
- `training_sample` is written and manifest export reads it.

## 18. Files That Must Stay Out Of Public Commits

Do not commit:

- private TIF/CT stacks
- exported part/reslice TIFFs
- local TaxaMask project JSON
- SQLite databases
- model weights/checkpoints/training runs
- API keys, gateway tokens, private runtime configs, `.env`
- `.lab-agent/config.json`
- `.lab-agent/sessions/`
- generated local outputs
- private design drafts or development logs

Use `.tmp_validation/` for disposable validation artifacts and clean it before finishing.

## 19. Maintainer Guidance For Future Agents

When the user asks about a behavior, explain it in research workflow terms first.

For example:

- what the program is doing
- why it matters for annotation, review, training, export, or trustworthiness
- what tradeoff it creates

Prefer stable, auditable solutions over clever shortcuts. The user needs to process real research datasets, including large AntScan batches and thousands of 2D/STL candidate images. Data safety and recovery matter more than hidden automation.

Do not assume TIF/CT is fully validated across taxa. The data model is generic, but current validation is mainly AntScan ant CT work.
