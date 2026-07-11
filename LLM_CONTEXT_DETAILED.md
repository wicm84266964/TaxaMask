# TaxaMask LLM Context

> Target: embedded AntCode agents, advanced LLM assistants, and developers maintaining the current TaxaMask `main` / v2.x line.
> Last synchronized: 2026-07-11.

This file is the current-state handoff document. It is not a changelog. Do not append dated development logs here. Keep it focused on the program state that an agent needs in order to diagnose, modify, and safely operate TaxaMask.

## 1. Product Scope

TaxaMask is a desktop research workbench for morphology annotation, literature evidence handling, model-assisted review, and dataset export.

The current maintained line contains three user-visible workflow routes:

- PDF evidence route: literature screening, figure/caption extraction, text part-description extraction, SQLite evidence databases, and reviewable candidate images.
- 2D/STL morphology route: specimen images, PDF-derived candidates, STL-rendered 2D views, VLM/SAM drafts, parent/child part annotation, Blink experts, external model backends, and COCO/YOLO/JSONL export.
- TIF/CT route: continuous TIFF stack import, TIF specimen projects, material/label layers, part ROI and part volume extraction, GPU volume preview, Local Axis Reslice, reviewed part/reslice annotation, project-wide train-ready sample collection, nnU-Net v2/custom TIF volume-segmentation backends, trained model library, prediction review import, and training-material capture for future local-axis automation.

Branch release notes are kept under `docs/releases/`. The full 1.2.0 TIF developer-preview release is documented in `docs/releases/1.2.0-tif-preview.md`.

TIF/CT is now integrated into the maintained branch, but it remains less broadly validated than the mature PDF and 2D/STL routes. Current TIF validation is mainly AntScan ant CT oriented. Do not claim broad cross-taxon TIF/CT validation unless new evidence is added.

## 2. Documentation Roles

- `README.md`: public GitHub landing page and installation entrypoint.
- `CHANGELOG_zh.md`: Chinese historical changelog-style document.
- `TaxaMask使用手册.md`: researcher-facing Chinese operating manual.
- `LLM_CONTEXT_DETAILED.md`: current technical handoff for Agent/LLM/developer use.
- `docs/contracts/`: backend contracts that are safe to expose publicly.
- Internal design drafts, task handoffs, local agent sessions, local runtime configs, generated data, model weights, private projects, databases, and CT/TIF stacks must not be published.

Do not recreate older duplicate root context/readme files. Keep this file as the current technical handoff rather than a dated development log.

## 3. Safety Model

AI outputs are draft material until a researcher confirms them.

Do not let automated tools overwrite:

- manual 2D polygons or confirmed masks
- confirmed VLM/SAM drafts
- `manual_truth` TIF label volumes
- source TIFF stacks
- part volumes, part masks, contours, or extraction metadata
- exported Local Axis reslices, unless the user explicitly performs a destructive delete

For TIF part labels, model predictions should land in `editable_ai_result` with a `raw_ai_prediction_backup`, not `manual_truth`.

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

In the TaxaMask `v2.3.0` line, the embedded runtime is aligned with Ant-Code `1.2.4`. This line includes the v2.1.0 long-task/background-terminal controls, gateway timeout/retry hardening, context-budget recovery fixes, interrupted-draft preservation, the bundled taxonomy PDF harvest skill for the PDF evidence stage 0 acquisition workflow, and the TIF/CT annotation-training-prediction loop described below. It intentionally does not adopt standalone Ant-Code global model configuration as the default; the embedded workspace and configuration boundary remains the TaxaMask repository.

Important files:

- `AntSleap/ui/taxamask_agent_panel.py`
- `AntSleap/core/agent_context_routes.py`
- `vendor/ant-code/`

Normal Ask Agent behavior sends compact workbench context, not full private project data. It should include diagnostic route, focused source references, artifact hints, and safety notes.

If the GUI cannot start, use the recovery dashboard script. It avoids importing the PySide6 GUI and starts the browser-based Ant-Code dashboard.

For long-running terminal jobs started by Agent Center, prefer registered background terminal tasks. Use `background_shell` for long commands, `background_terminal_list` before restarting servers/viewers/downloads/renders/training jobs, and `background_terminal_cancel` to clean up stale registered terminal tasks. This keeps PDF extraction, candidate import, preview generation, backend services, and training commands visible and cancellable from the Agent Center path.

Do not send API keys, private gateway URLs, large project JSON, database contents, TIF sidecars, or full local logs into prompts unless the user explicitly approves a specific diagnostic extraction.

## 6. 2D/STL Route

Main source areas:

- `AntSleap/main.py` (startup and compatibility facade only)
- `AntSleap/ui/main_window_shell.py`
- `AntSleap/ui/main_window_project_lifecycle.py`
- `AntSleap/ui/main_window_image_navigation.py`
- `AntSleap/ui/main_window_image_grouping.py`
- `AntSleap/ui/main_window_part_tree.py`
- `AntSleap/ui/main_window_annotation.py`
- `AntSleap/ui/main_window_blink_context.py`
- `AntSleap/ui/main_window_blink_workflow.py`
- `AntSleap/ui/main_window_model_management.py`
- `AntSleap/ui/main_window_training.py`
- `AntSleap/ui/main_window_prediction.py`
- `AntSleap/ui/main_window_vlm.py`
- `AntSleap/ui/main_window_export.py`
- `AntSleap/ui/main_window_presentation.py`
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

Current fourth-round MainWindow architecture state (verified candidate 2026-07-11):

- `AntSleap/main.py` is 763 physical lines. `MainWindow` has a 36-line class body, one 13-line constructor, no direct writable state assignments, and no direct Qt connections.
- Workflow behavior is owned by focused mixins listed above. `main.py` keeps historical class/function re-exports for compatibility; do not move workflow implementations back into the facade.
- The architecture audit scans 30 responsibility modules and records 194 real `connect/connect_once` bindings. The public MainWindow class itself owns zero direct bindings.
- PDF and TIF workbenches are created on first entry. Re-selecting the same 2D image reuses the loaded pixmap; file-list updates use local row/status updates where possible.
- Image import, SAM prompts, parent/child training, batch prediction, VLM, and dataset export are project-bound tasks. Normal project switching is blocked while they run, and callbacks verify the originating ProjectManager/path before applying or saving results.
- Blink child-training callbacks are bound to the concrete worker and its startup project path. A stale worker may leave its model file as an auditable artifact, but it must not register, appoint, or enable a route in the current project.
- `active_project_kind` is the visible shell mode. `last_workbench_kind` remembers the most recent `image` or `tif` workbench while Start Center/Agent is visible, so recent-project and shutdown routing must not infer project type from the `start` page alone.
- VLM callbacks also verify worker run ID. Stale run/project results must not write the current SQLite project; they may retain an independent artifacts summary for audit.
- AI drafts, confirmed labels, manual truth, PDF candidates, STL-rendered evidence, Blink trajectories, and TIF label roles remain distinct.
- Direct private implementation references to methods defined in MainWindow dropped from 146 to zero. GUI contract tests still call inherited workflow methods through a real window and are tracked separately.

## 7. PDF Evidence Route

Main source areas:

- `AntSleap/ui/pdf_processing_widget.py`
- `core/pdf_processor/`
- `tools/agentic/`
- `screener_configs/`
- `part_description_configs/`
- `vendor/ant-code/config/skills/taxonomy-pdf-harvest/`

PDF processing creates evidence, candidates, captions, figure clips, and provenance. It does not create training truth automatically.

Expected Agent behavior:

- Work one stage at a time: stage 0 PDF/literature source readiness, key/model readiness, screening criteria, figure-review criteria, then run/result diagnosis.
- At stage 0, first ask whether the researcher already has a PDF folder. If not, use `vendor/ant-code/config/skills/taxonomy-pdf-harvest/SKILL.md` to plan lawful open-access taxonomy PDF harvest before screening.
- Stage 0 harvest outputs are `records.csv`, `doi_list.txt`, `summary.json`, `download_manifest.csv`, and `pdfs/`. Treat `download_manifest.csv` and metadata records as source/provenance audit artifacts.
- Harvest boundaries: use only open metadata and legally exposed PDF links. Do not use Sci-Hub, LibGen, paywall bypasses, CAPTCHA bypasses, or logged-in website scraping.
- Keep provenance visible: PDF path, page, caption, nearby text, profile, and extraction status.
- Do not merge PDF output into labels without researcher review.

## 8. TIF/CT Project Model

Main source areas:

- `AntSleap/core/tif_project.py`
- `AntSleap/core/tif_volume_io.py`
- `AntSleap/core/tif_backend.py`
- `AntSleap/ui/tif_workbench.py`
- `docs/contracts/ant3d_tif_backend_contract_v1.md`
- `docs/contracts/tif_local_axis_backend_contract_v1.md`

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
- label schemas for part/reslice segmentation training
- label roles: `working_edit`, `manual_truth`, `editable_ai_result`, `raw_ai_prediction_backup`; legacy full-specimen model drafts may still appear as `model_draft`
- part records
- part ROI records
- part masks and contours
- extraction metadata
- Local Axis reslice records
- TIF segmentation model library records

Legacy TIF project JSON is now a migration source rather than the preferred active project store. Large volumes live in project sidecar directories.

Plain TIFF stack import creates an image volume but not trusted training truth. AMIRA-style imports can provide label volumes, but label shape/material consistency must be checked before treating a specimen as train-ready.

Current TIF volume-segmentation training semantics:

- A label schema defines numeric label meaning. It is not a training sample by itself.
- For `prepare_dataset` and `train`, the workbench first collects all project-wide train-ready part/reslice samples that have reviewed `manual_truth`, matching image/label shape, a bound nonempty label schema, valid label IDs, and verified train-ready status.
- If there are no train-ready part/reslice samples, it falls back to train-ready top-level specimen volumes.
- `prepare_dataset` can run with one exported sample for layout inspection. The bundled real nnU-Net v2 train adapter requires at least two exported training samples before calling nnU-Net.
- Prediction import writes a review layer plus `raw_ai_prediction_backup`. For part/reslice targets the review layer is `editable_ai_result`; for top-level specimen targets it is pending-review `working_edit` plus a legacy `model_draft` audit record. It must never auto-overwrite `manual_truth`.
- Successful train runs register a TIF segmentation model record in the project model library. The record stores model manifest, run/result paths, trained samples, label schema IDs, notes, and usability metadata. Deleting a model-library record removes only the registration, not weights or run artifacts.

TIF has two different external-backend concepts:

- Volume segmentation backend: `AntSleap/core/tif_backend.py` and `docs/contracts/ant3d_tif_backend_contract_v1.md`. It prepares train-ready part/reslice or top-level `manual_truth` data, runs editable prepare/train/predict commands, imports part/reslice predictions as `editable_ai_result` plus `raw_ai_prediction_backup`, and imports top-level predictions as pending-review `working_edit` plus `raw_ai_prediction_backup` and a legacy `model_draft` audit record.
- Default TIF volume backend preset: `taxamask_tif_nnunet_v2_backend`, implemented by `AntSleap/tools/tif_nnunet_v2_backend.py`. It exports nnU-Net v2 `.nii.gz` raw datasets, calls `nnUNetv2_plan_and_preprocess`, `nnUNetv2_train`, and `nnUNetv2_predict`, writes a TaxaMask model manifest, and remaps compact nnU-Net labels back to the project label-schema IDs before import.
- The TIF backend contract is backend-neutral. Users or Agent tasks may replace the editable command fields with MONAI, a custom 3D U-Net, or another backend if it reads `ant3d_tif_backend_contract_v1` and writes `ant3d_tif_backend_result_v1`.
- Local Axis proposal backend: `AntSleap/core/tif_local_axis_ai.py` and `docs/contracts/tif_local_axis_backend_contract_v1.md`. It proposes global ROI or local-frame candidates for review. It must not directly create final reslice TIFFs or write `manual_truth`.

## 9. TIF Workbench

Main file:

- `AntSleap/ui/tif_workbench.py`

The TIF workbench supports:

- opening/importing TIF projects
- specimen tree navigation
- slice review across Z/Y/X axes
- material map inspection/editing with visible swatches and color picker support
- explicit annotation tools: brush, eraser, picker, and pan
- label-schema creation/import/export/binding before label selection
- annotation cursor radius preview for brush/eraser/picker
- save-status feedback for dirty working-edit slices
- editable AI result review, raw prediction backup display, and acceptance to `manual_truth`
- undo/redo and annotation shortcuts
- ROI and key-slice contour workflow
- part volume creation
- mask preview and accepted part mask writing
- GPU/CPU volume preview
- full volume and part volume view modes
- Local Axis Reslice in the right-side work area
- training-material manifest export for Local Axis data capture
- TIF backend prepare/train/predict controls
- train-ready sample diagnostics and top-level fallback
- trained model library selection, notes, model-manifest handoff, and registration-only deletion

Current TIF workbench architecture notes:

Current third-round TIF architecture state (accepted 2026-07-10):

- `AntSleap/ui/tif_workbench.py` is 5,041 physical lines, with 219 Widget methods and 11 direct `.connect(...)` calls. The release baseline was 14,234 lines.
- Full workflow owners now live in `tif_selection_workflow_controller.py`, `tif_project_lifecycle_controller.py`, `tif_annotation_workflow_controller.py`, `tif_roi_workflow_controller.py`, `tif_part_mask_workflow_controller.py`, `tif_volume_render_controller.py`, `tif_local_axis_controller.py`, `tif_backend_panel_controller.py`, and `tif_result_review_controller.py`.
- `tif_workbench_view_builder.py`, `tif_workbench_view.py`, `tif_workbench_signal_router.py`, `tif_workbench_coordinator.py`, and `tif_workbench_shell.py` own widget construction, view access, signal contracts, cross-workflow locks/order, and shell lifecycle. Do not move these responsibilities back into the public Widget.
- Display mode changes must go through `TifWorkbenchWidget.on_display_mode_changed(...)`; direct writes can desynchronize the combo, internal state, stacked canvas, controls, and render request.
- GPU canvas signals `render_failed`, `render_info_changed`, and `render_stats_changed` must connect directly to `TifVolumeRenderController`. The corresponding Widget wrappers were intentionally removed; do not reconnect signals to `TifWorkbenchWidget` or recreate pass-through methods.
- GPU canvas mouse interactions also call `TifVolumeRenderController` directly: rotate, pan, interaction-finish scheduling, and wheel zoom. Both offscreen QLabel and embedded QOpenGLWidget paths must follow this rule; Local Axis endpoint interactions remain owned by `TifLocalAxisController`.
- Selection loading must avoid duplicate work on the GUI thread: load the editable mapping before the visible label layer, reuse that same copy-on-write mapping when the selected role is `working_edit`/`editable_ai_result`, suppress intermediate slice rendering, and render once after all selection state is ready. Shared mappings must be released once by object identity.
- While specimen/part/reslice selection is loading, every volume-render request must be coalesced rather than executed. After selection state is complete, schedule exactly one render on the next Qt event so large reslices use the existing background preview builder instead of synchronously downsampling on the GUI thread.
- Large saved reslices must enter the background preview-build route before GPU upload. Do not restore the old synchronous `build_volume_texture_from_source` exception for reslices: a real 765 x 1577 x 1428 GAGA reslice made selection appear unresponsive. Full-volume GPU policy remains separate.
- Selection-triggered image/label memmaps are detached immediately but closed in a background release thread. The release waits for any previous preview-build thread before closing mappings, so responsiveness must not introduce use-after-close races. CPU background preview loops may yield to the UI, but their numerical output must remain identical.
- When entering a part or reslice, label-schema UI restoration must prioritize the persisted `part.training.label_schema_id` over the combo box's previous browsing selection. Binding was already persisted; the accepted follow-up fix corrected only restoration priority.
- Selection loading completion is explicit. A completed part/specimen selection must not leave the operation status saying that loading is still in progress.
- The visible acceptance machine currently requires the supported CPU 3D fallback because Qt/OpenGL renderer initialization is unstable. Treat this as renderer/driver compatibility, not TIF corruption. CPU fallback was accepted for this round; embedded/offscreen GPU paths remain covered by contracts and tests.
- Top-level prediction results are `working_edit/pending_review` plus `raw_ai_prediction_backup/raw_backup` and model draft. SQLite migration must preserve all three roles. Never auto-promote a reviewed-looking prediction into `manual_truth`.
- Train-readiness diagnostics must not report image/label shape mismatch when manual truth is absent. Report shape mismatch only when both records exist.
- Real acceptance evidence used an isolated 294×294×284 ant head and a Dataset601 647×647×195 ant-brain volume. The researcher accepted the Local Axis anatomy and considered the Dataset601 brain-region boundaries reasonable. This is an ant-domain validation, not a cross-taxon claim.
- Final post-acceptance validation after Agent-context alignment: 778 tests across 11 suites, with one environment-dependent skip; changed/new Python files compile and `git diff --check` passes.
- The current controllers are workflow owners but are not fully decoupled ports: most still hold the complete Widget, production lifecycle-hook subscriptions remain incomplete, `TifVolumeRenderController` and `TifPartMaskWorkflowController` exceed the suggested 1,500-line review threshold, and 140 tests still reference private implementations. Do not claim complete controller isolation.
- Detailed requirements, Stage 0-10 evidence, and the post-acceptance risk audit are under `docs/tif_workbench_architecture_refactor_round3_*`, especially `docs/tif_workbench_architecture_refactor_round3_post_acceptance_audit_zh.md`.

- `AntSleap/ui/tif_workbench.py` remains the public PySide workbench entry, but new business rules should preferentially go into `AntSleap/core`, `AntSleap/services`, or the TIF task layer.
- TIF workbench helper modules now hold canvas/widgets, dialogs, translations, workers, layout/page builders, control panels, styling, Agent context assembly, and extracted helper functions.
- Core guards define label write safety, prediction import policy, truth promotion policy, and source/target write intent checks.
- Service/controller modules cover selection state, label edit requests, truth promotion, ROI part requests, backend workflow selection, preview/resource failure classification, volume preview requests, training/prediction panel state, and Local Axis draft/frame/reslice payloads.
- `AntSleap/core/tif_task_context.py`, `AntSleap/core/tif_task_state.py`, `AntSleap/services/tif_task_manager.py`, and `AntSleap/ui/tif_tasks.py` provide the unified task lifecycle. TIF import, Amira import, materialize, label save, truth promotion, ROI creation, backend train/predict, Local Axis export, volume preview, and mask preview are tracked with task context/state.
- `get_agent_context()` exposes `tif_task_summary` and `tif_state_summary`; use these before guessing whether the user is blocked by saving, training, prediction, import, preview, or Local Axis export.
- TIF architecture regression groups are defined in `tests/tif_architecture_test_groups.py`.
- Second-round TIF architecture notes are documented in `docs/tif_workbench_architecture_refactor_round2_requirements_zh.md`, `docs/tif_workbench_architecture_refactor_round2_execution_checklist_zh.md`, and the Stage 0-6 review files. The checklist includes mandatory pitfall checks for TaxaMask environment use, right-sidebar overflow, English text leaks, Local Axis three-point picking, resource exhaustion, validation artifacts, and Agent/AntCode context sync.

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

Current TIF/CT Local Axis automation stance:

- Data capture is in scope.
- Fully integrated Local Axis training/inference is not yet the daily UI workflow.
- Backend scaffolding and contracts may exist for Local Axis proposals, but researcher-facing operation should remain review-first.

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

Future Local Axis training/inference should follow the 2D external-backend style:

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

The first contract is for TIF volume segmentation, project-wide train-ready part/reslice or top-level sample export, model-manifest production, model-library registration, and review-layer prediction import with raw prediction backup. The second contract is for Local Axis ROI/frame proposals. Do not route nnU-Net/MONAI-style label-volume prediction tasks to the Local Axis contract.

Contract rules:

- Commands should receive paths to contract JSON, not private data pasted into prompts.
- Backend result JSON must declare schema/version/status.
- Model outputs should be drafts/proposals.
- Importers should validate shape, material ID, schema version, and provenance.
- External backend failures should be recorded without corrupting project state.
- The bundled nnU-Net v2 adapter requires at least two samples for real training; one-sample `prepare_dataset` is useful for export inspection only.

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

For `labeling`, source hints must point to `main_window_agent_context.py`, `main_window_annotation.py`, `main_window_blink_context.py`, and `main_window_vlm.py`, not to removed implementations in `AntSleap/main.py`. The first project artifacts are the 2D SQLite manifest/database, active image, annotation provenance, route records, project task context, and recent log excerpt.

For `tif_volume`, the context should expose label schema ID, train-ready part/reslice count, train-ready top-level count, selected training scope, selected/registered model-library state, backend command presence, active backend action, run folder, result JSON, recent log excerpt, selection-loading state, background preview state, pending post-selection render state, and deferred volume-array release state. This lets the Agent distinguish a blocked selection callback from normal background preview preparation or old-memory release, and explain whether the user is blocked by missing labels, missing review acceptance, missing nnU-Net commands, insufficient sample count, or prediction model selection. Full label-ID scans must remain deferred during selection and run only at manual-truth acceptance or strict training-readiness validation.

For `pdf_evidence`, Ask Agent routing must preserve the stage 0 acquisition context. If the user has no PDF folder yet, the Agent should load `taxonomy-pdf-harvest` from `vendor/ant-code/config/skills/taxonomy-pdf-harvest/SKILL.md` before the downstream PDF evidence skill; if PDFs already exist, it can continue directly to key/model readiness and screening/extraction setup.

## 17. Validation Expectations

Use focused tests when modifying a route.

Common commands:

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_agent_context_routes
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_project tests.test_tif_part_extraction tests.test_tif_local_axis_reslice tests.test_tif_local_axis_batch tests.test_tif_local_axis_ai
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_tif_workbench tests.test_tif_gpu_volume_canvas
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_gui_smoke
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --timeout 300
git diff --check
```

Current fourth-round full validation inventory: 18 suites and 1,149 tests, with one environment-dependent TIF workbench skip and all remaining tests passing. This includes strict stale-result coverage for SAM, image import, parent/child training, recent workbench routing, and Blink route ownership, plus TIF core/storage/services/preview/backends/workbench, GUI smoke, UI polish, layout, PDF safety/literature, validation tooling, TIF round-three architecture, TaxaMask round-four architecture, 2D SQLite, Agent, Blink/locator, and generic VLM/STL/export.

Embedded Ant-Code tool results are capped at 256 KiB before they enter model context. A large `list_files` result must be marked `truncated` while preserving its tool success/failure metadata; it must not force a new first-turn TaxaMask context into immediate compaction. A gateway response with no visible text and no tool call is an output-health failure and receives one concise repair retry instead of being accepted as a placeholder-only answer.

Use the TaxaMask environment above for GUI/TIF validation. Do not install PySide6 into the default Python environment to satisfy skipped GUI tests.

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
