# TAXAMASK / FORMICA-FLOW SYSTEM TECHNICAL MANUAL (Deep Dive)

> **Target Audience**: Expert LLM Assistants, Senior Developers
> **Version**: v3.21 (May 12, 2026, training controls + Blink route-appointed expert workflow)
> **Purpose**: Up-to-date architectural, workflow, and governance context for implementation and maintenance.

---

## 0) v3.21 Training Controls / Blink Expert Route Workflow (2026-05-12)

## 0) v3.23 Ant 3D Workbench Completion Pass (2026-05-16)

### 0.0 OME-NGFF sidecar is now a real minimal store
- `AntSleap/core/tif_volume_io.py` still writes `array.npy` for fast internal recovery, but `.ome.zarr/` directories now also contain:
  - `.zgroup`
  - `.zattrs`
  - `0/.zarray`
  - raw uncompressed Zarr v2 chunks
- Metadata records `ome_ngff_complete: true`, `ome_ngff_version: "0.4"`, axes, shape, dtype, spacing, chunk shape, role, and array path.
- This is intentionally a minimal OME-NGFF-compatible store, not a dependency on `zarr` or `ome_zarr`; the current `antsleap` environment still lacks those packages.
- Internal reads continue to use `array.npy`, so old TIF/AMIRA UI behavior remains stable.

### 0.1 TIF training exchange exports
- New module: `AntSleap/core/tif_export.py`.
- Supports project-safe export of train-ready TIF specimens without modifying `manual_truth`.
- Generic exchange formats now include:
  - OME-TIFF
  - plain multi-page TIFF
  - NRRD
  - MHA
  - NIfTI `.nii`
- Export writes `tif_training_export_manifest.json` with specimen ID, modality, shape, source project, label role, exported paths, and material map snapshot path.
- No external `nibabel`, `SimpleITK`, or `pynrrd` dependency is required; NRRD/MHA/NIfTI are written directly for handoff and should still be verified in the target backend environment before large training runs.

### 0.2 nnU-Net / MONAI layout adapters
- `export_nnunet_dataset(...)` writes:
  - `imagesTr/*_0000.nii`
  - `labelsTr/*.nii`
  - `dataset.json`
  - `nnunet_manifest.json`
- `export_monai_dataset(...)` writes:
  - NIfTI / NRRD / MHA copies
  - `monai_datalist.json`
  - `monai_manifest.json`
- Material IDs are preserved in label volumes. Backend-specific class remapping must be explicit and audited.
- `TifBackendRunner.run_action("prepare_dataset")` now creates a training export dataset before running the external prepare command and injects `dataset_manifest` / `dataset_formats` into the contract.

### 0.3 Material map editing is available in the TIF workbench
- `AntSleap/ui/tif_workbench.py` now provides add/edit/delete controls for TIF material maps.
- Users can edit ID, name, display name, display color, and trainable state.
- Material ID `0` is protected as background.
- Deletion is blocked if the material ID is still present in loaded label volumes, preventing orphaned labels that would make research annotations ambiguous.

### 0.4 STL rendered views are now routed into the existing 2D review path
- New project schema: `ant3d_stl_rendered_project_v1`.
- New project type: `stl_rendered_views`.
- New manager: `AntSleap/core/stl_project.py`.
- Main window default tabs are:
  - `Labeling Workbench`
  - `Blink Workbench`
  - `TIF Volume Workbench`
- PDF remains on-demand through `File -> Open PDF Evidence Tools`.
- File menu includes `Import STL Rendered Views to Labeling Workbench`.
- Direct directory import groups rendered-view files by specimen ID and fixed view token, then registers those images in the existing 2D `Labeling Workbench`.
- Opening a JSON with `schema_version: ant3d_stl_rendered_project_v1` and `project_type: stl_rendered_views` is treated as a legacy/lightweight registry import: its views are registered into the Labeling Workbench rather than opened as a separate main workbench.
- STL rendered-view imports record source path/provenance and keep STL surface labels separate from TIF material IDs.

### 0.5 STL rendered views can be registered for 2D review
- New bridge module: `AntSleap/core/stl_review_bridge.py`.
- `import_stl_rendered_views_into_2d_project(...)` imports a directory of rendered views directly into the existing 2D `Labeling Workbench`.
- `register_stl_rendered_views_for_2d_review(...)` remains available for older `StlRenderedProjectManager` registries.
- The 2D project receives image provenance:
  - source type `stl_rendered_view`
  - optional STL project path
  - specimen ID
  - metadata reference
  - fixed view name
  - original source path
- This reuses the existing Labeling Workbench / Blink / Locator/SAM path for surface-view annotation and training while preserving provenance, matching the intended STL-derived 2D review workflow.
- These 2D surface labels remain separate from TIF volume `manual_truth`.

### 0.6 PDF evidence and cross-project linkage helpers
- New lightweight PDF evidence index module: `AntSleap/core/pdf_evidence.py`.
- Schema: `ant3d_pdf_evidence_index_v1`.
- Stores source PDF, page, caption, candidate path, specimen ID, metadata_ref, notes, and provenance.
- It is intentionally evidence/provenance only; it does not write into TIF `manual_truth`.
- New specimen linkage module: `AntSleap/core/specimen_linkage.py`.
- Schema: `ant3d_specimen_linkage_v1`.
- It links independent TIF/STL projects by normalized `metadata_ref` or `specimen_id`, producing JSON/CSV reports without creating a monolithic workspace.

### 0.7 Current validation status
- Full validation on 2026-05-16:
  - `C:\Users\admin\anaconda3\envs\antsleap\python.exe -m unittest discover tests`
  - 193 tests passed.
- Compile validation:
  - `C:\Users\admin\anaconda3\envs\antsleap\python.exe -m compileall -q AntSleap tests`
- Real AMIRA sample path still resolves:
  - `D:\confirm-project\LBJ-workspace\new-project\AMIRA-data`
  - raw TIF, `.hx`, `.resampled`, `.labels`, `.MaterialStatistics`, and `.surf` are detected.

---

## 0) v3.22 Ant 3D Workbench TIF Volume Foundation (2026-05-16)

### 0.0 Independent TIF project type now exists
- New TIF project schema: `ant3d_tif_project_v1`.
- New project type: `tif_volume`.
- `AntSleap/core/tif_project.py` provides `TifProjectManager`, separate from the existing 2D/STL `ProjectManager`.
- TIF project JSON stays lightweight and stores specimen records, paths, material maps, review/train-ready state, model records, run records, and provenance.
- Large image/label data is stored in sidecar directories, not embedded in JSON.
- Current sidecar schema is `ant3d_volume_sidecar_v1`; v3.23 upgrades it from `.npy + metadata.json` only to a minimal OME-NGFF/Zarr v2 sidecar while retaining the `.npy` recovery copy.

### 0.1 TIF label layers and train-ready safety
- TIF label roles are separated:
  - `manual_truth`: human-confirmed training truth
  - `working_edit`: current editable correction layer
  - `model_draft`: model-generated prediction drafts
- Train-ready checks require:
  - specimen marked train-ready
  - working image sidecar exists
  - `manual_truth` sidecar exists
  - material map exists
  - image/label shape match
  - at least one trainable material
- Brush edits and model predictions do not automatically become training truth.
- `working_edit` must be explicitly promoted before it becomes `manual_truth`.

### 0.2 Plain TIF stack import
- New module: `AntSleap/core/tif_stack_import.py`.
- Imports a single `.tif` / `.tiff` stack as a TIF specimen.
- Creates:
  - `working/image.ome.zarr/` lightweight sidecar
  - empty `labels/working_edit.ome.zarr/`
  - `material_map.json`
  - `working/import_report.json`
- Plain TIF import does not create `manual_truth` and does not mark the specimen train-ready.

### 0.3 AMIRA read-only import
- New module: `AntSleap/core/amira_import.py`.
- First target is the observed AMIRA sample structure:
  - raw `.tif`
  - `.hx`
  - `.resampled`
  - `.labels`
  - `.MaterialStatistics`
  - `.surf`
- `.hx` parsing confirms that `.labels` connects to `.resampled`.
- `.resampled + .labels` is treated as the aligned working pair.
- raw TIF is retained as source/provenance, not used as the label overlay base when shapes differ.
- `.labels` HxByteRLE decoding follows the validated AmiraMesh rule:
  - control byte `>127`: literal run of `control & 0x7F`
  - control byte `<=127`: repeat next value `control` times
- The real sample validates as:
  - labels/resampled shape Z/Y/X: `[231, 1218, 1225]`
  - resampled spacing Z/Y/X approximately `[0.99992835521698, 0.600000023841858, 0.600000023841858]`
  - decoded label voxels: `344663550`
  - material statistics count: `19`
- Import writes `manual_truth` and copies it to `working_edit`.
- AMIRA original files are not modified or written back.

### 0.4 TIF Volume Workbench UI
- New UI module: `AntSleap/ui/tif_workbench.py`.
- Main window now owns a separate `self.tif_project` and a `TIF Volume Workbench` tab.
- The primary tab layout is now Labeling Workbench / TIF Volume Workbench / Blink Workbench.
- PDF tools are no longer shown as a default primary tab; they can be opened on demand from `File -> Open PDF Evidence Tools`.
- Opening a JSON with `schema_version: ant3d_tif_project_v1` and `project_type: tif_volume` loads it into the TIF workbench.
- Old 2D/STL TaxaMask JSON projects still load through the existing `ProjectManager`.
- File menu now includes:
  - `New TIF Volume Project`
  - `Import TIF Stack`
  - `Import AMIRA Directory`
  - `Open PDF Evidence Tools`
- TIF workbench supports:
  - specimen list
  - slice slider
  - image display
  - label overlay
  - material map table
  - brightness/contrast/overlay opacity controls
  - brush painting into `working_edit`
  - Ctrl-erase
  - slice-level undo/redo
  - saving `working_edit`
  - explicit promotion of `working_edit` to `manual_truth`
- The UI uses memory-mapped sidecar reads for viewing and releases references when closing/switching projects.

### 0.5 Independent TIF backend contract
- New module: `AntSleap/core/tif_backend.py`.
- Contract schema: `ant3d_tif_backend_contract_v1`.
- Result schema: `ant3d_tif_backend_result_v1`.
- Model manifest schema: `ant3d_tif_model_manifest_v1`.
- Supported actions:
  - `prepare_dataset`
  - `train`
  - `predict`
- TIF backend contract is separate from the existing 2D polygon/box external backend contract.
- Training/prepare contracts select only train-ready specimens and use `manual_truth` as label input.
- Prediction imports only artifacts with role `model_draft`.
- Prediction shape must match the specimen working volume shape before import.
- Imported predictions are copied into `labels/model_draft/` and do not overwrite `manual_truth`.

### 0.6 STL rendered-view grouping foundation
- New module: `AntSleap/core/stl_rendered_views.py`.
- Provides filename parsing and specimen grouping for STL-derived rendered 2D views.
- It expects rendered view filenames to end with a known fixed view token such as `dorsal`, `lateral`, `front`, `ventral`, etc.
- The output registry schema is `ant3d_stl_rendered_view_registry_v1`.
- This is a lightweight foundation only; existing Labeling Workbench, Blink, Locator/SAM, and training logic remain unchanged.

### 0.7 PDF evidence boundary
- `docs/ant3d_workbench/PDF文献证据层边界_zh.md` records the new boundary:
  - PDF remains useful as literature evidence, provenance, and headless/agentic workflow.
  - PDF is no longer positioned as the main Ant 3D Workbench visual annotation entry.
  - Existing PDF code and tools remain intact.
  - PDF candidates must not automatically become TIF `manual_truth`.

### 0.8 Validation status
- Focused validation on 2026-05-16:
  - `python -m unittest tests.test_generic_taxonomy_workflow tests.test_generic_export_schema tests.test_locator_scope tests.test_runtime_device tests.test_part_tree tests.test_window_geometry tests.test_tif_project tests.test_tif_stack_import tests.test_amira_import tests.test_tif_workbench tests.test_tif_backend tests.test_gui_smoke tests.test_stl_rendered_views`
  - 66 tests passed.
- Compile validation:
  - `python -m compileall AntSleap/core AntSleap/ui AntSleap/main.py tests`
- Environment note:
  - Validation used `C:\Users\admin\anaconda3\envs\antsleap\python.exe`.
  - The environment currently has `numpy`, `tifffile`, `PySide6`, and `PIL`.
  - It does not currently have `pytest`, `zarr`, or `ome_zarr`, so tests were run with `unittest`, and the first volume sidecar is the lightweight recoverable format described above.

### 0.0 Main workbench training controls
- `MainWindow` now keeps a `self.trainer` reference and exposes `Stop Training`.
- `TrainingThread` accepts `train_segmenter`; when false, it trains the Locator stage only and skips the SAM/parts stage.
- Locator and SAM loops now pass `stop_callback=self.isInterruptionRequested` into engine train/validate calls and return early on cancellation.
- The workbench checkbox label is `Train Locator only (skip SAM)`.
- The right-side training log console is taller and expands with the workbench inspector scroll area.

### 0.1 Model Settings now includes Blink expert defaults
- `Settings -> Model Settings -> Training` includes `Runtime Device` with `auto|cpu|cuda`.
- The runtime device preference is saved as config key `runtime_device`.
- `AntEngine.set_device_preference(...)` moves built-in Locator/SAM runtime modules to the resolved device, rebuilds optimizers, clears the base SAM predictor cache, and clears loaded cascade experts.
- `BlinkLabWidget` receives the same runtime device preference and passes it into both Blink auto-shrink trajectory generation (`BlinkRefiner`) and expert training (`BlinkTrainingThread -> BlinkExpertTrainer`).
- CPU mode is intended for installation validation, annotation-centric workflows, and small smoke tests. CUDA remains the practical recommendation for real Locator/SAM/Blink training.
- Platform status: Windows is the primary validated desktop environment. Linux is the main cross-platform target for lab workstations, servers, CUDA training, batch processing, and headless tools. macOS is only a CPU-only source trial path for lightweight annotation, project review, teaching, and small smoke tests. Apple Silicon MPS is not part of the first compatibility target and should not be exposed as a runtime device until real Mac hardware validates SAM, torchvision, Ultralytics, and related model paths.
- `Settings -> Model Settings -> Training` includes Blink expert defaults:
  - `blink_epochs`
  - `blink_batch`
  - `blink_lr`
  - `blink_weight_decay`
  - `blink_input_size`
- These values are saved through config keys:
  - `blink_train_epochs`
  - `blink_train_batch`
  - `blink_train_lr`
  - `blink_train_weight_decay`
  - `blink_train_input_size`
- The dialog tabs are scrollable so long Training / Inference / External Backend configuration remains reachable on normal screens.
- Several GUI combo boxes now use `NoWheelComboBox` to avoid accidental wheel-triggered selection changes.

### 0.2 Blink expert training is versioned and report-backed
- `BlinkExpertTrainer` no longer writes the current run to `best_expert.pth`.
- New runs save versioned candidates under the child-part bucket:
  - `weights/experts/{part}/expert_vYYYYMMDD_HHMMSS.pth`
- Within one run, the best checkpoint by loss is saved to that run's versioned candidate file.
- Checkpoints now carry metadata such as:
  - `input_size`
  - `learning_rate`
  - `weight_decay`
  - `epochs`
  - `batch_size`
  - `best_loss`
- `MicroExpertLocator` accepts `image_size`; non-224 pretrained ViT initialization interpolates position embeddings.
- Supported Blink input-size presets are `224`, `384`, and `512`.
- Training generates structured artifacts:
  - `training_log.csv`
  - `metrics_plot.png`
  - `validation_samples.png`
  - `validation_index.csv`
  - `report_summary.json`
  - `val_details/`
- `BlinkExpertTrainingReportDialog` shows summary, metrics, and validation-box previews.

### 0.3 Route appointment is the runtime authority for Blink experts
- `best_expert.pth` remains only as `LEGACY_EXPERT_FILENAME` for legacy global cascade manifest fallback.
- Current GUI training, expert registry, and route inference do not use `best_expert.pth` as the default selected expert.
- `BlinkLabWidget` uses `Appoint to Current Route` rather than an active-expert file operation.
- If the current parent -> child route already has an appointed expert, new training only registers the new file as a candidate and does not overwrite the appointed expert.
- `AUTO-ANNOTATE DRAFT` requires a route-appointed expert for the current parent -> target route.
- `ProjectManager.register_cascade_route_candidate(...)` is candidate-only; `ProjectManager.appoint_cascade_route_expert(...)` is the only path that changes the route-appointed expert.

### 0.4 Blink expert notes are display metadata, not renames
- `AntSleap/core/expert_notes.py` stores optional human notes in `weights/experts/expert_notes.json`.
- Notes are keyed by stable `expert_id` values such as `Mandible/expert_v20260512_153000.pth`.
- The Blink expert registry and `Settings -> Model Settings -> Project Route Management` display notes as `note (expert_id)`.
- Route payloads, model loading, deletion safety, and appointment logic still use the real `expert_id`; note text must never be treated as a filename or route key.
- Clearing a note removes its sidecar entry. Deleting an expert file or child-part expert bucket also clears matching note entries.

---

## 0) v3.20 Locator Scope UI / Agentic Contract Alignment (2026-05-05)

### 0.0 Model Settings now exposes locator scope
- `Settings -> Model Settings -> Training` includes `Main Locator Parts`.
- This is the GUI editor for project `locator_scope`.
- `locator_scope` controls which structures the built-in Locator learns as large, stable targets.
- Full project `taxonomy` / `Structures` can still contain smaller targets for SAM, Blink experts, or an external backend.
- Saving Model Settings writes the selected locator scope into the project JSON through `ProjectManager.set_locator_scope(...)`.
- If the locator scope length no longer matches the loaded Locator head, `MainWindow.refresh_ui()` rebuilds the runtime Locator head and warns that the user must retrain or select a matching model.

### 0.1 Agentic PDF/profile contract now mirrors PDF Processing
- `AntSleap/config/agentic_pipeline_contract.json` now has explicit required inputs:
  - `screener_config`
  - `figure_profile`
- Stage 10 passes the screener profile to `tools/agentic/screen_pdfs.py --config`.
- Stage 20 passes the figure extraction/review profile to `tools/agentic/extract_figures.py --figure-profile`.
- `tools/agentic/run_agentic_pipeline.py` accepts:
  - `--screener-config`
  - `--figure-profile`
- The default examples remain ant-oriented so the validated ant path is still visible, but the contract is now profile-replaceable for other taxa.

### 0.2 Agentic artifact gating and actual figure artifact paths
- `tools/agentic/run_agentic_pipeline.py` now supports contract-level `required_artifacts`.
- A stage can be blocked by missing upstream output files, not only by missing user-provided inputs.
- This prevents later stages from becoming runnable before generated files such as `routing_decisions.json`, `pdf_candidates_raw.json`, or `project_agentic_import.json` actually exist.
- Stage 20 figure extraction artifacts follow `EnhancedPDFExtractionSystem` behavior:
  - output DB: `{db}`
  - figure images: `{db_artifacts_dir}/figure_images`
  - review batches: `{db_artifacts_dir}/review_batches`
- `{db_artifacts_dir}` is resolved by `run_agentic_pipeline.py` as `<db parent>/<db stem>_v2_artifacts`.

### 0.3 Documentation corrections
- `docs/PDF筛选profile适配说明.md` now uses the current CLI flags:
  - `--pdf-source-dir`
  - `--out`
  - `--config`
- `docs/Formica_flow使用手册.md` now explains `Main Locator Parts` and moves `Validate External Backend` to the Model Settings button table.

---

## 1) v3.19 Generic Workbench / External Backend Delta (2026-05-03)

### 0.0 Product naming and compatibility boundary
- External product/UI name is now `TaxaMask`.
- Main window title is `TaxaMask Workbench`.
- Internal package/directory name remains `AntSleap`; do not rename imports or package paths casually.
- Root documentation roles: `README.md` is the public GitHub landing page and installation entrypoint; `CHANGELOG_zh.md` is the Chinese historical changelog; `LLM_CONTEXT_DETAILED.md` is the current-state handoff/context document.

### 0.1 Project templates
- New file: `AntSleap/core/project_templates.py`.
- Built-in templates:
  - `generic_taxonomy`: display `Generic taxonomy mask project`, taxonomy `Object / Region / Structure`, locator scope `Object`, category supercategory `biological_structure`, taxon label `Taxon`.
  - `ant_default`: display `Ant morphology (validated example)`, taxonomy and locator scope `Head / Mesosoma / Gaster`, category supercategory `ant_part`, taxon label `Genus`.
- GUI new-project flow explicitly asks for a template and defaults to generic.
- `ProjectManager()` and `ProjectManager.create_project(..., template_id=None)` still default to the ant template for internal/legacy compatibility. If UI or agent code wants generic behavior, pass `template_id=PROJECT_TEMPLATE_GENERIC`.

### 0.2 Taxon metadata compatibility
- Label entries now normalize to:
  - `taxon`
  - `taxon_rank`
  - `taxon_metadata`
  - compatibility `genus`
- `ProjectManager._normalize_label_taxon_fields(...)` fills these fields during load.
- `get_taxon(...)`, `set_taxon(...)`, and `list_taxa()` are the preferred APIs.
- `get_genus(...)` / `set_genus(...)` remain wrappers for old code.
- UI displays `Taxon` and `Structures` separately.

### 0.3 Export schema state
- `AntSleap/core/project.py` declares:
  - `DEFAULT_CATEGORY_SUPERCATEGORY = "biological_structure"`
  - `MULTIMODAL_SAMPLE_SCHEMA_VERSION = "taxamask-multimodal-sample-v1"`
- COCO categories use project `category_supercategory` or default `biological_structure`.
- YOLO `dataset.yaml` writes quoted YAML-safe scalar strings via `json.dumps(..., ensure_ascii=False)`.
- Multimodal JSONL rows now include:
  - `schema_version = taxamask-multimodal-sample-v1`
  - `taxon`, `taxon_rank`, `taxon_metadata`
  - compatibility `genus`
  - `annotation_status = workbench_export`
  - `review_status`
  - `source_provenance`
- `tools/agentic/export_multimodal_dataset.py` summary schema is now `taxamask-multimodal-export-summary-v1`.

### 0.4 Relocated path recovery
- Hardcoded author-machine relocation from `Formica-Flow_output` to `C:\savedata\Formica-Flow_output` was removed from core runtime behavior.
- Config key `known_relocated_roots` is now available in `AntSleap/core/config.py`.
- `ProjectManager.set_known_relocated_roots([...])` accepts mappings:
  - `marker`
  - `relocated_root`
- `MainWindow` passes config `known_relocated_roots` into the project manager at startup.
- `ProjectManager.get_image_path_health()`, `preview_image_path_remap(...)`, and `apply_image_path_remap(...)` now support explicit missing-image checks and conservative project path remapping.
- GUI entry: `File -> Check / Relocate Project Images`.
- Remapping updates only currently missing image paths and only accepts unique filename matches under the selected new root. Duplicate filenames remain unresolved to avoid linking labels to the wrong specimen image.
- Runtime config storage now uses platform user config locations via `AntSleap/core/platform_paths.py`:
  - Windows: `%APPDATA%/TaxaMask/user_config.json`
  - Linux: `~/.config/taxamask/user_config.json` or `$XDG_CONFIG_HOME/taxamask/user_config.json`
  - macOS: `~/Library/Application Support/TaxaMask/user_config.json`
- A repository-root `user_config.json` remains a migration source only. First run copies it to the platform config path and leaves the old file untouched.

### 0.5 External script backend
- New file: `AntSleap/core/external_backend.py`.
- New contract doc: `docs/contracts/external_backend_contract_v1.md`.
- Core schema constants:
  - `taxamask_external_backend_contract_v1`
  - `taxamask_prediction_v1`
  - `taxamask_model_manifest_v1`
- `ExternalBackendRunner` creates run directories under `external_runs/` with:
  - `contract.json`
  - `dataset/`
  - `model/`
  - `predictions/`
  - `logs/*stdout.log`
  - `logs/*stderr.log`
- Commands support placeholders:
  - `{python}`
  - `{contract_json}` or `{contract}`
  - `{run_dir}`
- External prediction import filters labels against current project taxonomy and returns internal `polygons` / `auto_boxes` payload.
- External training and prediction are deliberately isolated from built-in Locator/SAM:
  - external training does not create `TrainingThread`
  - external prediction does not call `engine.predict_full_pipeline()`
  - external models are not stored in built-in `weights/locator_*.pth` or `weights/sam_decoder_lora_*.pth`

### 0.6 Model Settings UI
- `Settings -> Model Settings` tab order:
  1. Training
  2. Inference
  3. External Backend
- Training tab includes `Main Locator Parts`, the user-facing editor for project `locator_scope`.
- External Backend tab is an advanced entry. It contains a short operator note explaining:
  - TaxaMask calls user scripts
  - commands run in isolated `external_runs`
  - scripts receive contract JSON via `{contract}` or `{contract_json}`
  - built-in Locator/SAM does not run for external backend tasks
- External commands are multiline `QTextEdit` editors, not single-line fields.
- `Validate External Backend` checks:
  - backend id is present
  - at least train or predict command is present
  - each populated command contains `{contract}` or `{contract_json}`
- Save also runs the same validation.

### 0.7 Tests / validation
- New/expanded tests:
  - `tests/test_generic_taxonomy_workflow.py`
  - `tests/test_generic_export_schema.py`
- Current focused validation:
  - `python -m pytest tests\test_generic_export_schema.py tests\test_generic_taxonomy_workflow.py tests\test_locator_scope.py tests\test_agentic_multimodal_export.py tests\test_api_runtime_settings_schema.py`
  - 30 passed.
- Compile validation:
  - `python -m compileall AntSleap\core AntSleap\ui AntSleap\main.py tools\agentic\export_multimodal_dataset.py`

---

## 1) v3.18 Figure Extraction / Multimodal Profile Delta (2026-05-03)

- Figure extraction and multimodal review now share a downstream `Figure Extraction / Review Profile`.
- New profile utilities live in `core/pdf_processor/figure_profile.py`.
- New example/template profiles live under `multimodal_configs/`:
  - `蚂蚁三视图提取复核_示例.json`
  - `通用分类学图版提取复核_模板.json`
  - `植物分类学图版提取复核_模板.json`
- `EnhancedPDFExtractionSystem` now accepts `figure_profile` / `figure_profile_path` and uses the profile for:
  - taxonomy evidence terms
  - caption and figure-reference patterns
  - core/extended evidence section hints
  - evidence text length limits
  - auxiliary terms
  - required or expected detected figure parts
  - acceptance mode (`require_all_expected_parts` or `model_accept_with_parts_recorded`)
- `MultimodalValidator` now reads the same figure profile for:
  - review system prompt and user instructions
  - allowed `detected_views` / detected structure fields
  - category values
  - mock fallback terms and required parts
- Ant triptych behavior remains the built-in default and shipped example. Generic and plant templates no longer inherit `lateral / dorsal / head_frontal` as required acceptance fields.
- `AntSleap/ui/pdf_processing_widget.py` now separates:
  - `Select Logic Profile` for PDF screening
  - `Figure Extraction / Review Profile` for figure extraction, evidence assembly, and multimodal review
- GUI API settings are now role-based:
  - Text LLM API for PDF screening
  - Multimodal LLM API for figure image+text review
  - Multimodal can reuse Text LLM provider or use a separate vision-capable model/provider.
- `screener_configs/api_runtime_settings.example.json` is now `taxamask-api-runtime-settings-v2` and contains separate `text_llm` / `multimodal_llm` sections.
- `tools/agentic/extract_figures.py` supports `--figure-profile` and the compatibility alias `--multimodal-profile`; run indexes record figure profile metadata and multimodal runtime summary.
- New tests:
  - `tests/test_figure_profile.py`
  - `tests/test_api_runtime_settings_schema.py`
- Validation run on 2026-05-03:
  - `python -m unittest tests.test_figure_profile tests.test_api_runtime_settings_schema`
  - `python -m unittest tests.test_config_cleanup tests.test_agentic_contract tests.test_agentic_candidate_import tests.test_figure_profile tests.test_api_runtime_settings_schema`
  - `python -m py_compile core/pdf_processor/figure_profile.py core/pdf_processor/pdf_extractor.py core/pdf_processor/multimodal_validator.py AntSleap/ui/pdf_processing_widget.py tools/agentic/extract_figures.py`
- Residual validation caveat: the base environment used during this pass lacks `fitz`, so real PDF extraction smoke tests were not executed here. The extractor profile injection was checked with a minimal `fitz` stub, and full PDF runs should be repeated in the normal PDF-capable environment.

## 0.1) v3.17 Open-Source Preparation Delta (2026-05-03)

- `TaxaMask` is now the external open-source project name. `AntSleap` remains the current package/GUI directory name for runtime stability before any later deliberate rename.
- The former README development log is centralized in `CHANGELOG_zh.md`; it is Chinese-only and also includes the earlier pre-release history.
- Root documentation has been intentionally reduced to two maintained files: `CHANGELOG_zh.md` and `LLM_CONTEXT_DETAILED.md`.
- `.gitignore` now blocks local project JSON, `user_config.json`, API runtime settings, databases, weights, experiment outputs, generated artifacts, and bundled local binaries.
- `screener_configs/api_runtime_settings.json` was removed because it contained local secret material; `screener_configs/api_runtime_settings.example.json` is the safe template.
- Runtime device selection now flows through `AntSleap/core/runtime_device.py` with `auto|cpu|cuda` semantics.
- `AntEngine`, `TrainableSAM`, `SAMWorker`, `tools/agentic/train_project.py`, and `tools/agentic/auto_annotate_project.py` now support hardware-neutral CPU/CUDA selection.
- `requirements-torch-cpu.txt` and `requirements-torch-cu121.txt` provide explicit install paths for CPU-only and CUDA workstations.
- `docs/跨物种适配严格审查报告.md` records the current strict review of non-ant adaptation readiness.
- PDF screening cross-taxon adaptation was corrected: V2 no longer appends ant-specific decision criteria in code; biological include/exclude/uncertain semantics now come from the selected screener profile.
- New V2 screener profiles were added under `screener_configs/`: ant example, generic taxonomy template, and plant taxonomy template.
- `AntSleap/ui/pdf_processing_widget.py` now exposes `llm_system_prompt` in Advanced Logic Settings and shows keyword lexicons in V2 as editable helper lexicons.
- `docs/PDF筛选profile适配说明.md` explains how to adapt the ant PDF screening profile to other taxa.

## 1) v3.16 Delta Summary (2026-04-27)

### 0.0 Agentic orchestration now exists as a headless sidecar layer
- The current repository includes `tools/agentic/` with command-line wrappers for:
  - `screen_pdfs.py`
  - `extract_figures.py`
  - `import_candidates_to_project.py`
  - `auto_annotate_project.py`
  - `train_project.py`
  - `export_multimodal_dataset.py`
  - `run_agentic_pipeline.py`
- The agentic layer is intended for code agents and batch orchestration, not for replacing the Qt GUI.
- The safe automation model is:
  - run commands
  - read/write JSON, SQLite, run indexes, manifests, and reports
  - preserve failures and review candidates as artifacts
  - keep the human GUI as the researcher-facing control surface

### 0.1 Agentic pipeline contract is now machine-readable
- `AntSleap/config/agentic_pipeline_contract.json` describes the stages from literature input to multimodal dataset export.
- The contract carries:
  - required inputs
  - commands
  - expected outputs
  - quality gates
  - autonomy/model-inference gates
  - non-negotiable controls
- `tools/agentic/run_agentic_pipeline.py` can build dry-run plans and execute currently runnable safe stages.
- During `--execute-ready`, the runner refreshes input existence after each stage, so outputs produced earlier in the pipeline can unblock later stages.
- Model-backed auto annotation remains gated unless `--allow-model-inference` is supplied.

### 0.2 Project image provenance is now part of project persistence
- `AntSleap/core/project.py` now includes an `image_provenance` map in `project_data`.
- Added helpers:
  - `set_image_provenance(image_path, provenance, save=True)`
  - `get_image_provenance(image_path)`
- Load/save behavior:
  - old projects without `image_provenance` still load
  - provenance is saved relative to the project file when possible
  - loaded provenance is resolved back to runtime absolute image paths
  - `remove_image(...)` also removes provenance for that image
- `export_multimodal_dataset(...)` now emits:
  - `schema_version = taxamask-multimodal-sample-v1`
  - `taxon` / `taxon_rank` / `taxon_metadata`
  - compatibility `genus`
  - `source_provenance`
- This is the bridge that lets a future dataset row trace back to source PDF, page, figure/candidate id, review status, and routing context.

### 0.3 PDF optional dependencies are now import-safe
- `core/pdf_processor/__init__.py` catches `ModuleNotFoundError` for optional classifier/extractor/validator imports.
- `core/pdf_processor/pdf_classifier.py` now treats:
  - `openai`
  - `pdf2image`
  as optional imports.
- If `openai` is missing, LLM screening does not initialize an SDK client and downstream rows can fall back to review-oriented handling.
- If `pdf2image` is missing, OCR image fallback returns no lines rather than preventing the module from importing.
- This matters for agents because many validation or project-import tasks do not need LLM/OCR support, and should remain runnable in lighter environments.

### 0.4 Candidate import is conservative by default
- `tools/agentic/import_candidates_to_project.py` accepts `--status`, defaulting to `needs_review`.
- Imported PDF-derived images get project label status `needs_review` unless explicitly overridden.
- The contract import stage passes `--status needs_review`.
- Operational consequence:
  - PDF-derived images can be visible in a project and traceable through provenance
  - they are not silently promoted into trusted labels or training data

### 0.5 Figure extraction CLI uses batch-friendly partial success semantics
- `tools/agentic/extract_figures.py` returns:
  - `passed` when all PDFs succeed
  - `partial` when at least one PDF succeeds and at least one fails
  - `failed` when no PDF succeeds or setup fails
- `partial` exits with code 0 so later governance stages can continue using the successful candidate set.
- Failed PDFs remain recorded in the run index.
- This is important for real literature folders where zero-byte or corrupt PDFs should be routed for review, not allowed to block all candidate extraction.

### 0.6 Validated state on the 2026-04-27 test batch
- Environment:
  - `C:\Users\admin\anaconda3\envs\antsleap\python.exe`
- Test PDF folder:
  - `E:\test-project\LBJ-workspace\Formica-Flow-Latest\test-pdf`
- Observed validation:
  - agent unit tests passed
  - PDF screening processed 8 PDFs, recorded 3 zero-byte PDFs, and extracted text from 5 readable PDFs
  - figure extraction processed the 5 readable PDFs and produced 30 candidates, with overall status `partial`
  - Core-2 governance passed, and all 30 candidates routed to `Ambiguous`
  - explicit Ambiguous import smoke test wrote 30 `needs_review` candidates with provenance
  - real `AntEngine` auto-annotation invocation worked, but saved 0 labels for the unsuitable PDF candidate batch
  - 1-epoch training smoke test passed without saving official weights
  - multimodal export produced 48 trusted labeled JSONL rows and validated references successfully
  - full `run_agentic_pipeline.py --execute-ready` executed safe runnable stages successfully

---

## 1) v3.15 Delta Summary (2026-04-22)

### 0.0 2026-04-22 project route manifests now use `project-v2` with nested expert history/candidates
- `AntSleap/core/cascade_routes.py` now declares `PROJECT_ROUTE_MANIFEST_VERSION = "project-v2"`.
- Current route records now support:
  - nested `appointed_expert`
  - nested `expert_candidates`
  - flattened compatibility fields (`expert_id`, `expert_part`, `expert_filename`)
- Legacy flat route entries still load and sanitize forward compatibly, so older project JSON can migrate into the newer route structure without losing the current appointed expert.

### 0.1 2026-04-22 project route management UI is now a real tree view, not a flat table
- `RouteManagementPanel` in `AntSleap/main.py` now renders a parent -> route -> expert tree.
- Route actions are now scoped by selected node type:
  - parent node: no route action buttons
  - route node: enable/disable and delete
  - expert node: appoint selected expert
- This changed the route-management surface from a flat list mentality into a branch-based project route view.

### 0.2 2026-04-22 third-layer expert nodes now prefer project-persisted history/candidates, with runtime discovery only as supplemental input
- `RouteManagementPanel._route_expert_candidates(...)` now merges:
  - persisted project route candidates/history
  - runtime-discoverable experts from the cascade manager
  - current appointed expert forced into the merged list when present
- Current expert-node statuses can include:
  - `Appointed`
  - `History`
  - `Missing file history`
  - `Discoverable`
  - `Available`
- `Missing file history` expert nodes can now be deleted from the route tree when they are persisted history entries, no longer exist on disk, and are not the current appointed expert.
- This cleanup removes only the current project's `expert_candidates` history entry. It does not delete model files and does not alter the current appointed expert.
- Operational consequence:
  - the current project's stored expert history is treated as the primary route record
  - discoverable experts remain visible and appointable, but they are now a supplement rather than the main source of truth

### 0.3 2026-04-22 current project-managed cascade participation is controlled by route-tree state, not a global master toggle
- `ModelSettingsDialog` no longer exposes the old global cascade master checkbox.
- For the project-managed route path, effective participation is now determined by:
  - route existence in the current project manifest
  - route enabled/disabled state in project data
  - appointed-expert availability on disk
- Legacy global route manifests remain only as a compatibility fallback when no project route manifest is available.

### 0.4 2026-04-22 Blink expert training now has a visible log panel driven by trainer -> thread -> UI signaling
- `BlinkLabWidget` now includes a dedicated `Training Log` panel with `training_log_console` and `Clear Log` action.
- `BlinkTrainingThread` emits `log_signal`, and `BlinkLabWidget.train_expert_model()` wires that signal into `append_training_log(...)`.
- The current path is now:
  - trainer emits log lines
  - training thread forwards them through `log_signal`
  - Blink UI appends them into the visible log console during `TRAIN EXPERT MODEL`

### 0.5 2026-04-22 expert-bucket deletion is now a high-risk, two-step flow with current-project impact disclosure
- `AntSleap/ui/blink_lab.py` now provides:
  - `BucketDeletePreviewDialog`
  - `BucketDeleteTypeConfirmDialog`
  - current-project route-impact summaries before deletion
- Current bucket delete flow is:
  1. preview bucket path and deletable files
  2. preview matching route branches in the currently open project
  3. choose whether to delete matching current-project route branches too, default checked
  4. type the exact child-part name in a second confirmation dialog
  5. delete bucket files from disk only after both confirmations succeed
  6. optionally remove matching route branches from the currently open project only
- Important boundary:
  - other projects are not scanned or modified
  - this should not be described as a new cross-project expert-registry persistence system

### 0.6 2026-04-22 targeted UI polish improved checked-state visibility and dialog-button affordance
- `AntSleap/ui/style.py` now strengthens generic checked indicators for radio buttons and checkboxes in the scientific theme.
- The targeted custom dialogs that use themed `QDialogButtonBox` styling now present clearer `OK` / `Cancel` button affordance.
- Follow-up scope extension:
  - `AntSleap/ui/style.py` now also provides shared themed `QMessageBox` helpers for confirmation prompts
  - `AntSleap/main.py`, `AntSleap/ui/blink_lab.py`, and `AntSleap/ui/pdf_processing_widget.py` now route their global confirmation flows through that helper layer
  - covered cases now include `Yes/No`, `OK/Cancel`, and the PDF extraction `Continue/Cancel` warning dialog
  - this closes the earlier gap where global confirmation popups could still show the old default button appearance even after custom dialog buttons were updated

---

## Earlier retained delta summary

### 0.0 2026-04-21 the main GUI `Train Models` path now uses saved annotations plus structured preflight, not manifest gating
- The active GUI training path is now built around `AntSleap/core/training_preflight.py`.
- `build_training_preflight(...)` walks the current project image list and current saved labels, then admits samples only when they satisfy actual saved-data requirements:
  - image exists on disk
  - image is readable
  - polygon annotations sanitize successfully
  - at least one valid annotated part remains after sanitization
- This means the normal workbench training path no longer depends on:
  - filename/text-based view gating
  - manifest-based train/val gating
- Current exclusions are explicit and surfaced back to the operator:
  - missing images
  - unreadable images
  - zero-annotation images
  - invalid-annotation images

### 0.1 2026-04-21 `TrainingPreflightDialog` replaced the old plain-text preflight message box
- `AntSleap/main.py` now routes GUI training through `TrainingPreflightDialog`.
- The dialog explicitly tells the operator that the main Train Models path now uses saved annotations and image files rather than view/manifest gating.
- The dialog has structured tabs for:
  - Overview
  - Coverage
  - Warnings
- Coverage is separated into locator and SAM/parts sections, with total/train/val counts for each.

### 0.2 2026-04-21 locator size is now a true `(width, height)` pair through train, save, load, and infer
- `build_training_preflight(...)` now records exact native size pairs for locator-eligible images in `locator_exact_size_counts`.
- If all eligible locator images share one native size, that exact size becomes the locator training size.
- If eligible locator images mix sizes, current behavior is:
  - `mixed_native_resolutions = True`
  - selected locator size becomes the smallest exact eligible tier by area
  - lower retry options are precomputed as smaller exact size pairs
- `TrainingThread` now passes that exact pair into `TwoStageDataset(..., mode='locator', input_size=(w, h))`.
- `predict_full_pipeline(...)` uses `engine.locator_resolution` as a true width/height pair and reports it in output metadata.
- Locator checkpoints now save `meta.locator_size` and can restore it on load.

### 0.3 2026-04-21 mixed-resolution and legacy-checkpoint handling are now explicit instead of silent
- If mixed locator resolutions are present, `TrainingPreflightDialog` shows a specific mixed-resolution warning before the run starts.
- If locator training hits OOM, the GUI can offer retry sizes based on `lower_locator_size_options` from the same preflight snapshot.
- If a selected locator checkpoint lacks saved size metadata, load now enters a legacy-confirmation path:
  - the checkpoint is treated as legacy `512x512` only after explicit user confirmation
  - otherwise the selection is cancelled/reverted
- This prevents older checkpoints from silently masquerading as size-aware modern ones.

### 0.4 2026-04-21 locator supervision now uses `valid_parts_mask` and masked-loss semantics
- `TwoStageDataset` locator mode now returns four tensors per sample:
  - image tensor
  - heatmap target
  - WH target
  - `valid_parts_mask`
- `AntSleap/core/engine.py` now uses that mask in:
  - heatmap loss aggregation
  - WH loss aggregation
  - locator pixel-error calculation
- Operational consequence:
  - unlabeled channels no longer dilute the average loss
  - unlabeled channels no longer fabricate pixel-error contributions
  - stage-1 training/validation metrics now reflect only actually supervised parts

### 0.5 2026-04-21 preflight now reports total/train/val coverage separately for locator and SAM
- `build_training_preflight(...)` now materializes separate coverage maps for:
  - locator total/train/val
  - SAM total/train/val
- `describe_training_preflight(...)` and `TrainingPreflightDialog` both expose those distinctions.
- This matters because a project can have:
  - enough Head examples for locator training
  - while still having sparse Mandible or Eye examples for SAM/parts training
- The operator no longer has to infer that imbalance from a generic warning string.

### 0.6 2026-04-21 first-stage reporting is now structured and per-sample inspectable
- `AntSleap/core/reporter.py` now writes structured experiment artifacts:
  - `training_log.csv`
  - `metrics_plot.png`
  - `validation_samples.png`
  - `validation_index.csv`
  - `report_summary.json`
  - `val_details/` detail overlays
- `engine.generate_report(...)` now returns these structured paths to the GUI.
- `TrainingReportDialog` now consumes:
  - `report_summary.json`
  - `validation_index.csv`
  - `val_details/`
- The report dialog therefore no longer behaves like a single-image viewer only; it is now a structured inspection surface.

### 0.7 2026-04-21 cascade routing became project-scoped in the active product path
- When Blink opens with a parent/context ROI and a child target part, that parent -> child context can register a project route candidate.
- Project route persistence now continues in `project-v2` form, with backward-compatible migration from older flat route records.
- `RouteManagementPanel` in `AntSleap/main.py` exposes project route management inside `Settings -> Model Settings`.
- Operators can now:
  - refresh the route tree
  - appoint a concrete expert checkpoint to a route
  - enable or disable that route
  - delete the route from the current project manifest
- Deleting a route removes only the current project record; it does not prevent Blink from registering the same parent -> child relation again later as a candidate.

### 0.8 2026-04-21 single and batch inference now use the active project route manifest
- `MainWindow.run_prediction()` now passes `self._active_project_route_manifest()` into `predict_full_pipeline(...)`.
- `MainWindow.run_batch_inference()` now passes the same project route manifest into `InferenceThread`, which forwards it to `predict_full_pipeline(...)`.
- `predict_full_pipeline(...)` now prefers the project route manifest when it contains routes.
- Legacy global route manifest is still readable as a fallback only when the project route manifest is absent or empty.

### 0.9 2026-04-21 the old global cascade master toggle and old manifest-training config keys are now obsolete
- `AntSleap/core/config.py` now treats the following keys as obsolete and removes them during load/save:
  - `train_split_manifest_path`
  - `train_core2_manifest_path`
  - `train_allow_random_fallback`
  - `inf_enable_cascade_experts`
- Current runtime meaning:
  - there is no active global cascade master toggle in current UI/runtime behavior
  - there is no active manifest-path config controlling the main GUI training path
- Important boundary:
  - governance scripts and policy files still exist for evaluation/candidate tooling
  - but they should not be described as the active gate for normal GUI training anymore

### 0.0 2026-04-10 same-image 4K refinement in the main workbench no longer reloads the current image
- Same-image point edits were previously able to refresh the left list, reselect the same image, reload that image, and call `fit_to_view()`, which snapped 4K refinement back to full-image fit.
- Current behavior in `AntSleap/main.py` is now:
  - compare the selected path to `self.current_image`
  - if it is the same image and the canvas already holds a valid pixmap, update overlays/metadata without reloading the image
  - still reload/refit normally when the operator actually switches to a different image

### 0.1 2026-04-10 Blink is now explicit-entry / explicit-sync driven, not auto-pushed from main-workbench edits
- The main workbench no longer auto-calls `blink_lab.refresh_from_workbench(...)` after:
  - `on_polygon_completed(...)`
  - current-image prediction application
  - current-image batch result arrival
- Current accepted Blink interaction model:
  - entering Blink from `Open in Blink Workbench` passes current labels/manual boxes/auto boxes explicitly into `start_session(...)`
  - later Blink refresh is operator-triggered via `Sync from Workbench`
  - formal return from Blink to the main project remains `APPLY TO GLOBAL`

### 0.2 2026-04-10 point-edit persistence now uses delayed autosave instead of immediate whole-project JSON rewrite
- `ProjectManager.update_label(...)` and `delete_label(...)` now accept `save=False`, allowing memory-first state updates for high-frequency polygon edits.
- `MainWindow` now owns a single-shot delayed-save mechanism with a current accepted default of:
  - `3000 ms`
- Current workbench point-edit path:
  - update/delete label with `save=False`
  - mark project dirty
  - restart the single-shot autosave timer
  - refresh list/UI immediately in memory
- Immediate flush is still preserved before state-boundary operations such as image switch, new/open project, image add/import/delete, export, training, manual save, and close.

### 0.3 2026-04-10 explicit same-image Blink refresh can preserve the local viewport
- `AntSleap/ui/blink_lab.py` now threads a `preserve_view` flag through explicit same-image refresh paths so Blink can skip `fit_to_view()` when refreshing the same image intentionally.

### 0.4 2026-04-10 legacy 10-view specimen trees can now be normalized with a dedicated repository tool
- `tools/rename_pngs_with_folder_prefix.py` was added for early 4K/8K specimen exports where many specimen folders reused the same fixed 10-view PNG basenames.
- The tool renames each PNG to `<folder_name>_<original_png_name>` and supports preview-first dry runs plus explicit `--apply` execution.

### 0.0 2026-04-02 stable-release frontend alignment imported the accepted dual-theme workbench into LBJ-workspace
- The stable LBJ-workspace branch now carries the approved frontend theme work from the separate test branch.
- `AntSleap/ui/style.py` is now the stable branch source of truth for:
  - dual themes (`dark` / `light`)
  - semantic button palettes
  - surface-role panel styling
- The stable release should now be understood as:
  - the backend/workflow-stable branch
  - with the newer accepted frontend theme system merged in

### 0.1 Theme switching is now a full stable-release workflow feature, not just a shell-level stylesheet change
- `AntSleap/main.py` now:
  - stores the current theme in config
  - exposes theme switching from the settings menu
  - reapplies theme-aware styles to major toolbar/workbench action buttons
  - propagates theme changes into child workbenches
- The stable branch now explicitly re-themes:
  - top workbench actions (`Export Dataset`, `Import & Crop`, `Open in Blink Workbench`)
  - left-side `+ Add Images`
  - workbench AI action buttons
  - `PdfProcessingWidget`
  - `BlinkLabWidget`
- This specifically fixes the earlier stable-branch risk where neutral buttons could keep the previous mode's palette after switching themes.

### 0.2 Blink and PDF child panels now participate in the stable theme system
- `AntSleap/ui/blink_lab.py` now exposes stable-release theme refresh behavior for:
  - status/readability styling
  - training-settings readability
  - semantic action buttons
- `AntSleap/ui/pdf_processing_widget.py` now re-themes:
  - semantic action buttons
  - the processing log console
- Operational consequence:
  - switching between light and dark themes should no longer leave the literature-mining or Blink areas visually stranded in an older palette.

### 0.3 The 2026-04-02 merge explicitly did not replace the stable release's backend/workflow logic
- During the merge, the following stable behaviors were re-checked and preserved:
  - project-scoped `blink_context_roi_parents`
  - explicit workbench-driven Blink entry sessions
  - remembered parent/context ROI reuse per project
  - runtime synchronization after locator/segmenter deletion
  - persistence of remembered Blink context in project save/load
- This should be treated as a **frontend alignment into the stable branch**, not as a new backend refactor.

### 0.0 2026-03-19 same-day additions: Blink/workbench bridge, localization cleanup, and recovery boundaries
- Blink is no longer just a passive side panel that happens to receive the current image. The workbench now launches an **explicit Blink session** with two operator decisions:
  - which **target part** is being refined
  - which **entry ROI** (manual box or auto box) is used to enter the local view
- For the workbench-driven path, Blink now opens on the chosen ROI instead of defaulting to the full image.
- Blink session state now distinguishes three different intents that were previously easy to blur together:
  - **view mode switching** (`BLINK SWITCH`)
  - **trajectory/training-data generation** (`EXECUTE AUTO-SHRINK`)
  - **formal project writeback** (`APPLY TO GLOBAL`)
- `APPLY TO GLOBAL` is now target-part-scoped: only the current target part is written back from local view to the global project.
- Dirty Blink sessions are now protected from silent overwrite during same-image workbench refresh or forced sync.
- Chinese UI cleanup landed across the main workbench, PDF runtime control panel, Blink lab, and cropper dialog.
- Project path resolution now supports user-configured `known_relocated_roots` mappings for relocated image trees.
- Normal GUI project loading still requires syntactically valid JSON. A moved path can be remapped; a truncated JSON file cannot be auto-salvaged by the standard GUI loader.

### 0.1 Screening V2 baseline from v3.10 is retained
- `core/pdf_processor/pdf_classifier.py` still defaults to `processing_mode = "v2"`.
- Screening remains CSV-first + full LLM validation with stable `RID000001` style record mapping.
- Legacy heuristic-first screening remains available as explicit rollback mode.

### 0.2 Same-day screening follow-up changes
- Default screening `pdf_extract_timeout_seconds` is now `30` (previously `180`).
- Screening V2 now persists `extract_source` (`text_layer` / `ocr` / `failed`) into queue/results/statistics for operator visibility.
- Resume usability improved with interrupted-run parameter restore support and clearer resume-skip reasons.

### 0.3 Triptych Extractor V2.0 replaced the old image-object-centric extraction semantics
- `core/pdf_processor/pdf_extractor.py` now builds **whole figure-region candidates** rather than treating each raw embedded image object as the accepted unit.
- Candidate discovery is broader than before: it uses both page image rects and drawing/vector rects, then clusters nearby visual regions into figure candidates.
- Accepted target unit is now a **whole ant triptych figure**; small maps / scale bars / insets may remain if the main subject is still the triptych figure.
- Comparison figures and multi-species figures are explicitly kept out of accepted outputs.

### 0.4 Figure-level persistence + layered text evidence
- Extraction persistence is now figure-centric:
  - `pdf_files`
  - `figure_records`
  - `figure_evidence`
  - `extraction_stats`
- Evidence is stored in three layers:
  - `figure_local`
  - `species_core`
  - `species_extended`
- Per-run extraction artifacts now live under `<db_stem>_v2_artifacts/` and include:
  - `figure_images/`
  - `review_batches/`
  - `batch_raw_responses/`

### 0.4.1 Same-day crop precision follow-up
- After the initial V2.0 rebuild, saved figure crops were tightened by separating:
  - a wider internal `context_bbox` for caption/local evidence search
  - a tighter `clip_bbox` for the actual saved PNG and multimodal image input
- Edge-adjacent caption/body text trimming was added before PNG save, specifically to reduce the new whole-figure crop tendency to include nearby text.
- A retained manual acceptance bundle currently exists under `.tmp_validation/real_triptych_crop_check_keep/` and contains:
  - `output/real_crop_validation.db`
  - `output/real_crop_validation_v2_artifacts/figure_images/`
  - `validation_summary.json`
- Real-PDF spot checks from `C:\saveproject\Formica-Flow_output\11.27-newspecies-pdf\llm-check` showed that external caption/body text leakage was reduced substantially, while whole triptych figures remained generally usable.

### 0.5 Extraction-side multimodal review now follows the GPT-5.4 / OpenAI-compatible path
- `core/pdf_processor/multimodal_validator.py` now batches **multiple figure candidates per request** instead of reviewing one image at a time.
- Transport supports `responses` and `chat_completions`.
- For `gmn.chuangzuoli.com + gpt-5.4`, provider-aware normalization now mirrors the screening-side compatibility path and prefers `/responses` when appropriate.
- Requests now ask for structured JSON outputs via schema-style constraints instead of free-form narrative answers.

### 0.6 Hard acceptance gates + safe fallback semantics
- A figure is accepted only when:
  - real multimodal review actually ran
  - confidence passed threshold
  - it is not `comparison_figure`
  - it is not `multiple_species`
  - required views are present: `lateral + dorsal + head_frontal`
- Mock/default review no longer silently accepts or silently discards figures.
- Non-real review is routed into `Review` with `mock_review_only` semantics.

### 0.7 Extraction UI/operator safeguards were added
- Extraction startup now has a preflight check and **confirmation dialog** if the run would use mock/default review instead of real multimodal review.
- Main extraction logs now warn:
  - at startup when real multimodal review is disabled/misconfigured/init-failed
  - per PDF when figures fell back to mock/default review and were routed to `Review`
- DB viewer detail now shows figure-level category/status/species plus multimodal review mode/model metadata.

### 0.8 Governance bridge compatibility was updated for figure-level extraction
- `candidate_bridge.py` now exports from `figure_records` when present, instead of assuming the legacy `images` table.
- Bridge output now includes `review_status`, `multimodal_review_mode`, `multimodal_model_used`, and `species_candidate` for extracted figure candidates.

### 0.9 v3.9 governance baseline retained
- Core-2 governance chain, acceptance suite, and orchestrator remain available as the downstream baseline. The normal GUI `Train Models` path now uses saved annotations plus structured training preflight.

### 0.10 2026-03-20 accepted UI polish: semantic roles, non-danger save semantics, and final font baseline
- `AntSleap/ui/style.py` is now the UI source of truth for five shared button roles:
  - `commit`
  - `run`
  - `neutral`
  - `destructive`
  - `stop`
- Non-destructive save/writeback actions should not use the destructive palette.
- Accepted current examples:
  - `AntSleap/ui/cropper.py`: `Save & Add to Project` is part of the normal commit/save path.
  - `AntSleap/ui/blink_lab.py`: `APPLY TO GLOBAL` is formal project writeback for accepted annotation state.
  - PDF stop/cancel controls use the `stop` palette rather than delete/danger semantics.
- Final accepted mixed-script font policy after the same-day trial:
  - Latin UI text prefers `Cambria`
  - Chinese UI text prefers `Microsoft YaHei UI`, `Microsoft YaHei`
  - Chinese serif options remain later in the fallback chain, but they are no longer the preferred default.
  - Monospace input/log surfaces remain `Consolas`, `Courier New`.
- `register_windows_scholarly_ui_fonts()` is now called during Windows startup before `MainWindow()` is constructed; this is the current mitigation for Qt not reliably discovering the requested fonts in this environment.

### 0.11 2026-03-23 locator scope was split from full project taxonomy
- `AntSleap/core/project.py` now persists both:
  - full project `taxonomy`
  - `locator_scope`
- New projects default both lists to the current macro set:
  - `Head`
  - `Mesosoma`
  - `Gaster`
- This means the main heatmap locator now defaults to the major-part workflow instead of trying to learn all known small parts from the same output head.
- Legacy compatibility was preserved deliberately:
  - if an older project JSON lacks `locator_scope`, the saved taxonomy is reused as the locator scope so old projects are not silently reinterpreted.

### 0.12 2026-03-23 Blink data semantics were tightened around parent crops and draft-first local annotation
- Blink trajectories now persist `parent_context` together with `frames`, including:
  - `parent_part`
  - `parent_box`
  - `source`
- `BlinkTrajectoryDataset` now uses that parent context to train on the parent crop instead of silently reverting to full-image semantics.
- Default explicit cascade routes now exist for the current ant workflow:
  - `Head -> Mandible`
  - `Head -> Eye`
- Blink local annotation now supports two draft-first paths before manual refinement:
  - **route-appointed expert box -> base SAM draft polygon** (`AUTO-ANNOTATE DRAFT`)
  - **manual prompt box -> base SAM draft polygon** (`Draw Box (For SAM Draft)`)
- These prompt boxes are intentionally temporary and are not treated as the later loose shrink box.

### 0.13 2026-03-23 researcher-facing Blink guidance and startup geometry were tightened
- Blink entry dialog now explicitly explains the intended child/parent semantics:
  - `Target Part` = child part to refine
  - `Entry ROI` = parent/context region Blink will zoom into
  - current guidance explicitly mentions `Eye -> Head`
- Blink status labels now wrap long guidance/error messages instead of clipping them in the control panel.
- Main window startup is now screen-aware:
  - preferred startup size remains `1600x1000`
  - on normal screens it opens centered
  - on smaller work areas the geometry is clamped into the visible region before centering

### 0.14 2026-03-31 workbench comfort/UI consistency pass
- The accepted UI baseline now also includes:
  - easier-to-grab splitter handles in the labeling workbench and Blink
  - calmer right-side inspector/tree/scroll surfaces
  - explicit radio/checkbox styling instead of platform-default islands
  - wider brightness / contrast sliders for easier fine control
  - less blackout-heavy Blink masking during local refinement
- These changes were intentionally fatigue-oriented only; they do not alter annotation or Blink workflow semantics.

### 0.15 2026-03-31 Blink parent/context memory became project-scoped operator knowledge
- `AntSleap/core/project.py` now persists `blink_context_roi_parents` inside project data.
- Blink entry no longer treats the earlier hard-coded parent preference path as current source of truth.
- Current behavior is:
  - no remembered relation yet -> Blink does not silently guess a biologically meaningful parent ROI
  - explicit operator choice -> saved into current project as target-part → parent/context relation
  - later entry for the same target part in the same project -> remembered parent/context ROI is reused automatically
  - if the operator later enters Blink using the target part itself as ROI, that remembered parent relation is cleared
- This keeps anatomy/context decisions local to the project and auditable instead of pretending the software can infer universal taxonomy structure.

### 0.16 2026-03-31 model-selector controls were clarified and runtime-synchronized
- The destructive sidecar buttons next to `Locator` and `Segmenter` now use explicit, stateful wording:
  - English: `Del`
  - Chinese: `删除`
  - tooltips explicitly state that the selected model file will be deleted from disk
  - buttons disable automatically when the current selection is not actually deletable
- Locator deletion now targets the real `locator_<timestamp>.pth` filename.
- Runtime state now follows the selector after deletion:
  - deleting the active segmenter returns runtime to `Base SAM`
  - deleting the final trained locator resets runtime to base/untrained state
- The English `Locator / Segmenter / Del` rows now share an aligned grid, fixing the earlier visual drift caused by label/content width differences.

### 0.17 2026-03-31 screening V2 folder semantics were rewritten in meaning-first UI copy
- The old abstract checkbox label `Isolate V2 Runs` is no longer the main user-facing wording.
- Current UI wording is now:
  - English: `V2: separate folder per run`
  - Chinese: `V2：每次运行独立文件夹`
- Tooltip wording now explicitly explains the operational meaning:
  - each V2 run writes to its own subfolder under `Output Dir`
  - this prevents different screening runs from mixing results together
- Runtime logs were updated to describe the same option with the same mental model.

---

## 1) System Directory Map (Current)

```text
Formica-Flow-Latest-confirm/
├── AntSleap/
│   ├── main.py
│   ├── ui/
│   │   ├── pdf_processing_widget.py
│   │   ├── blink_lab.py
│   │   ├── style.py
│   │   └── cropper.py
│   ├── core/
│   │   ├── config.py
│   │   ├── cascade_routes.py
│   │   ├── taxonomy_defaults.py
│   │   ├── engine.py
│   │   ├── window_geometry.py
│   │   ├── blink_dataset.py
│   │   ├── blink_refiner.py
│   │   ├── blink_trainer.py
│   │   ├── project.py
│   │   ├── reporter.py
│   │   ├── training_preflight.py
│   │   └── governance/
│   │       ├── view_contract.py
│   │       ├── migration.py
│   │       ├── view_resolver.py
│   │       ├── policy_loader.py
│   │       ├── splitter.py
│   │       ├── grouping.py
│   │       ├── manifest_builder.py
│   │       ├── training_manifest_loader.py
│   │       ├── evaluator.py
│   │       ├── redline_gate.py
│   │       ├── sample_guard.py
│   │       ├── headview_monitor.py
│   │       ├── candidate_bridge.py
│   │       ├── risk_scorer.py
│   │       ├── router.py
│   │       ├── idempotency.py
│   │       └── locator_trigger.py
├── core/pdf_processor/
│   ├── pdf_classifier.py
│   ├── pdf_extractor.py
│   └── multimodal_validator.py
├── tools/governance/
│   ├── validate_contract.py
│   ├── migrate_project_views.py
│   ├── test_view_resolver.py
│   ├── validate_policy.py
│   ├── build_split_manifest.py
│   ├── check_leakage_groups.py
│   ├── build_train_manifest.py
│   ├── dry_run_training_split.py
│   ├── calc_per_view_metrics.py
│   ├── build_redline_report.py
│   ├── check_sample_sufficiency.py
│   ├── build_headview_monitor.py
│   ├── export_pdf_candidates.py
│   ├── build_sampling_plan.py
│   ├── route_candidates.py
│   ├── check_candidate_dedup.py
│   ├── eval_locator_trigger.py
│   ├── run_acceptance_suite.py
│   └── run_core2_pipeline.py
├── docs/core2_governance_runbook.md
├── screener_configs/
│   ├── api_runtime_settings.example.json
│   ├── 蚂蚁新种筛选_V2示例.json
│   ├── 通用分类学新种筛选_V2模板.json
│   └── 植物分类学新种筛选_V2模板.json
├── CHANGELOG_zh.md
└── LLM_CONTEXT_DETAILED.md
```

---

## 2) Governance Policy Contract (Core-2 retained tooling)

`AntSleap/config/view_policy_core2.json` remains the policy source of truth for the retained Core-2 governance tooling.

It is **not** the active gating source for the main GUI `Train Models` workflow anymore.

### 2.1 Target views
- Main: `lateral`, `dorsal`
- Excluded from main training: `head_frontal`

### 2.2 Quality gate
- `pass_rate_min = 0.95`
- `boundary_overlap_min = 0.75`
- `localization_error_px_max = 15.0`
- `min_samples_per_target_view = 30`

### 2.3 Routing policy
- Core-2: high confidence + target view + quality pass + no high-risk tier
- Frontier: head view or medium confidence band
- Ambiguous: unknown/conflict/low confidence

### 2.4 Sampling policy
- `high = 1.0`
- `medium = 0.3`
- `low = 0.1`

### 2.5 Trigger policy
- `consecutive_fail_runs = 2`
- `single_run_pass_rate_gap = 0.05`

### 2.6 Bridge mode
- `candidate_only` (hard restriction)

---

## 3) Training Integration (main.py)

### 3.1 Active GUI training inputs
The current GUI `Train Models` path takes its inputs from:
- project images in `ProjectManager`
- saved labels / boxes in project JSON
- current project taxonomy
- current project locator scope

It does **not** currently depend on manifest files for normal GUI training eligibility.

### 3.2 Active training preflight behavior
`MainWindow` now calls `build_training_preflight(images, labels_by_image, taxonomy, locator_scope)` before starting training.

That preflight computes:
- locator-eligible sample list
- SAM/parts-eligible sample list
- stable train/val split on the current eligible sample sets
- per-part coverage totals for total/train/val
- exact native locator size distribution
- mixed-resolution warning state
- lower locator retry size options

### 3.3 Active training-thread behavior
`TrainingThread` now:
- receives the preflight snapshot directly
- sets `engine.locator_resolution` from `selected_locator_size`
- constructs locator datasets from `locator_train_data` and `locator_val_data`
- constructs SAM datasets from `parts_train_data` and `parts_val_data`
- skips a stage cleanly if there are no eligible samples for that stage

### 3.4 Reporting behavior
After training, `TrainingThread` calls `engine.generate_report(...)` and emits the structured report payload back to the UI.

### 3.5 Governance boundary note
Core-2 governance code and scripts remain in the repo for deterministic evaluation/candidate work.
They are no longer the active gating mechanism for the standard GUI training button.

---

## 4) Candidate Flow (Current Practical Semantics)

### 4.1 PDF extraction persistence
`EnhancedPDFExtractionSystem` now stores **figure-level** extraction outputs to SQLite plus run-scoped figure images / batch artifacts.

Current crop semantics are intentionally split:
- `context_bbox`: wider, internal-only, used for caption/local evidence discovery
- `figure_bbox`: persisted clip bbox, matching the actual saved PNG that users inspect

### 4.2 Candidate bridge
`export_pdf_candidates.py` transforms DB **figure records** into candidate artifacts:
- includes provenance (`source_ref`)
- includes confidence fields
- includes figure review metadata (`review_status`, `multimodal_review_mode`, `multimodal_model_used`, `species_candidate`)
- mode must be `candidate_only`

### 4.3 Risk and routing
- `build_sampling_plan.py`: assigns risk tiers and sampled subset by policy rates
- `route_candidates.py`: emits Core-2/Frontier/Ambiguous routing with reason codes

### 4.4 Human review reality
There is no dedicated candidate-approval UI tab yet.
Operators review via DB viewer/artifacts and manually import approved images for annotation.
If extraction could not use real multimodal review, the current UI now warns before the run starts and also warns again in the main extraction log after each affected PDF.

---

## 5) Acceptance & Orchestration

### 5.1 Acceptance suite
`run_acceptance_suite.py` executes:
- `CHK_CONTRACT_V2`
- `CHK_SPLIT_DETERMINISM`
- `CHK_HEADVIEW_BLOCK`
- `CHK_REDLINE_TARGET_VIEW`
- `CHK_BRIDGE_MODE`
- `CHK_SAMPLING_RATES`
- `CHK_IDEMPOTENCY_DEDUP`

Output: `acceptance_summary.json` with `all_pass` and failing IDs.

### 5.2 End-to-end pipeline
`run_core2_pipeline.py` stages migration→split→metrics→redline→candidates→sampling→routing→trigger→acceptance.

Output: `run_index.json` with:
- global status (`passed`/`failed`)
- failing stage marker
- artifact pointers

---

## 6) Standard Verification Commands

### 6.1 Candidate verification chain
```bash
python tools/governance/export_pdf_candidates.py --db ant_literature.db --out artifacts/core2/pdf_candidates_raw.json --mode candidate_only
python tools/governance/build_sampling_plan.py --candidates artifacts/core2/pdf_candidates_raw.json --policy AntSleap/config/view_policy_core2.json --out artifacts/core2/review_sampling_report.json
python tools/governance/route_candidates.py --candidates artifacts/core2/pdf_candidates_raw.json --policy AntSleap/config/view_policy_core2.json --out artifacts/core2/routing_decisions.json
python tools/governance/check_candidate_dedup.py --input artifacts/core2/routing_decisions.json
```

### 6.2 Full acceptance
```bash
python tools/governance/run_acceptance_suite.py --artifacts artifacts/core2 --policy AntSleap/config/view_policy_core2.json --out artifacts/core2/acceptance_summary.json
```

### 6.3 One-command pipeline
```bash
python tools/governance/run_core2_pipeline.py --project test-head.json --db ant_literature.db --policy AntSleap/config/view_policy_core2.json --out artifacts/core2
```

### 6.4 Screening/runtime sanity
```bash
python -m py_compile core/pdf_processor/pdf_classifier.py core/pdf_processor/pdf_extractor.py core/pdf_processor/multimodal_validator.py AntSleap/ui/pdf_processing_widget.py AntSleap/core/governance/candidate_bridge.py
python -m py_compile AntSleap/main.py AntSleap/ui/blink_lab.py AntSleap/core/project.py AntSleap/core/taxonomy_defaults.py AntSleap/core/window_geometry.py AntSleap/core/training_preflight.py AntSleap/core/cascade_routes.py AntSleap/core/reporter.py
python -m unittest tests.test_training_preflight tests.test_config_cleanup tests.test_reporting_routes tests.test_locator_resolution_metadata tests.test_locator_scope tests.test_blink_bridge tests.test_ui_localization tests.test_macro_micro_pipeline tests.test_window_geometry
python AntSleap/main.py
```

---

## 7) Known Gaps (Current)

- Candidate pool is not yet a front-end approval panel.
- No DB-native approval/rejection column synchronized with governance routing outputs.
- Triptych extraction is still **whole-figure first**; automatic panel splitting (`lateral` / `dorsal` / `head_frontal`) is not yet implemented.
- Candidate discovery is broader than legacy raw image-object extraction but remains visually rect-seeded (image/drawing region based), not caption-first.
- Downstream consumers should rely on `review_status` + `multimodal_review_mode`, not only a boolean accepted/taxonomic flag.
- Final ingestion into annotation project is still manual.
- No built-in provider health probe panel; gateway/protocol/model entitlement checks are still operator-driven via logs and external diagnostics.
- Blink still does not support magic-wand click -> draft polygon inside the local workbench.
- Blink entry guidance is explicit now, and project-scoped remembered parent/context relations now exist, but the repo still lacks a mature taxonomy-driven parent ROI recommender.
- Blink still has no batch "annotate remaining images" mode; current Blink semantics remain intentionally single-session and ROI-scoped.

---

## 8) Dependency Notes

- PDF extraction requires Poppler binaries for some `pdf2image` fallback paths. The bundled/local Windows path convention is `external_tools/poppler/`; Linux users usually install `poppler-utils`; macOS CPU-only trial users usually install Poppler through Homebrew.
- Poppler discovery is centralized in `core/pdf_processor/poppler_discovery.py`, exposed through `core.pdf_processor`, logged by PDF OCR fallback code, and displayed in the PDF Processing UI so missing Poppler is presented as a setup issue rather than an API/model failure.
- Segmentation relies on SAM base weights (`sam_b.pt`) under `AntSleap/weights/`.
- Local validation note: `antsleap` is the maintainer's current Windows test conda environment name, not a public requirement or recommended environment name.
- Install a platform-appropriate PyTorch build before the rest of the dependencies when possible; CUDA and CPU wheels are split into `requirements-torch-cu121.txt` and `requirements-torch-cpu.txt`. macOS users should not install the CUDA requirements file; MPS remains an advanced user experiment outside the first supported runtime policy.
- Runtime device policy remains `auto / cpu / cuda`. `auto` selects CUDA when PyTorch reports CUDA availability; otherwise it uses CPU. The GUI does not expose MPS.
- `AntSleap/core/runtime_device.py` remains importable in lightweight environments without PyTorch and resolves to CPU in that case.
- Cross-platform validation guidance lives in `docs/platform_setup.md`, including Windows/Linux/macOS smoke expectations, project relocation workflow, Poppler notes, and the MPS non-goal.

---

## 9) Extended Deep Context (Restored Detail Layer)

> This section restores the high-granularity handoff depth expected by advanced LLM/developer sessions.
> It complements Sections 0-8 and is intentionally verbose.

### 9.1 Module A — PDF Screening & Extraction (`core/pdf_processor/`)

#### 9.1.1 Screening profile architecture
- Screening logic is profile-driven (`screener_configs/*.json`) rather than hardcoded to a single taxonomic group.
- Active runtime controls include mode, batching, confidence threshold, prompt templates, API protocol, timeout, split/resume/isolation toggles, and prompt-size / output-size guards.
- Local `api_runtime_settings.json` stores API endpoint/model/protocol runtime preferences and is ignored by Git; `api_runtime_settings.example.json` is the committed safe template.
- UI profile switching and persistence are wired in `AntSleap/ui/pdf_processing_widget.py`.
- Current shipped first-test default profile targets `gpt-5.4` with `80/40` batch sizing, `100000` prompt-char budget, `1600` chars/file, `12000` max output tokens, `240s` request timeout, and `30s` per-PDF extraction timeout.

#### 9.1.2 Screening execution channels (mode-based)
- **V2 (default)**: CSV-first + full LLM validation for all extracted rows.
- **Legacy (fallback)**: heuristic-first + selective LLM review path.
- Runtime dispatch is V2-only via `batch_classify()` for user-facing PDF screening. The old Legacy rule-prefilter UI/profile path has been removed.

#### 9.1.3 V2 classification artifacts and routing outputs
- `v2_active_run.json` at output root coordinates interrupted-run recovery.
- Per-run grouped artifacts, by default under `v2_runs/run_*/` when the UI option now labeled `V2: separate folder per run` (config key `isolate_v2_runs`) is enabled:
  - `resume_state/master_queue.csv`
  - `resume_state/csv_batches/*.csv`
  - `resume_state/run_index.json`
  - `core_results/master_results.csv`
  - `core_results/selected_record_ids.csv`
  - `core_results/move_manifest.csv`
  - `core_results/llm_enhanced_classification_details.csv`
  - `debug_evidence/batch_raw_responses/*.txt`
- routing directories:
  - `core_results/final_new_species_reports/`
  - `core_results/manual_review_uncertain/`
- Semantics:
  - `resume_state/` = resumable execution checkpoints
  - `core_results/` = operator-facing outputs and copied PDFs
  - `debug_evidence/` = raw LLM evidence and troubleshooting artifacts

#### 9.1.4 Extraction persistence
- `EnhancedPDFExtractionSystem` stores extraction outputs into SQLite and optional file images.
- Key constructor controls:
  - `output_db_path`
  - `save_images_to_files`
  - `enable_multimodal_validation`
  - `multimodal_config`
- With `save_images_to_files=True`, extracted **figure clips** are persisted under `<db_stem>_v2_artifacts/figure_images/`.
- The same artifact root also keeps:
  - `review_batches/` (per-batch candidate manifests)
  - `batch_raw_responses/` (raw multimodal outputs)

Saved clip generation now uses a tighter clip path than the internal evidence window:
- image candidate discovery still starts from clustered visual rects
- evidence selection still uses the wider internal context region
- actual PNG save uses the tighter clip bbox, with edge text trimming before `page.get_pixmap(..., clip=...)`

#### 9.1.5 Extraction DB model (conceptual, current)
- `pdf_files`
- `figure_records`
- `figure_evidence`
- `extraction_stats`

`figure_records` now holds figure-level fields such as:
- `page_number`
- `figure_index`
- `candidate_id`
- `figure_bbox`
- `caption_text`
- `local_context_text`
- `species_candidate`
- `final_confidence`
- `accepted`
- `comparison_figure`
- `multiple_species`
- `detected_views`
- `review_status`
- `multimodal_validated`
- `multimodal_review_mode`
- `multimodal_model_used`

`figure_evidence` stores layered text evidence with levels:
- `figure_local`
- `species_core`
- `species_extended`

UI-side export utilities and the governance bridge now consume these figure-level records instead of depending on the legacy `images/text_blocks/image_text_relations` semantics.

---

### 9.2 Module B — Labeling Workbench & Runtime (`AntSleap/main.py`)

#### 9.2.1 Main data loop
1. Image import into project store
2. Manual/SAM-assisted annotation into `labels`
3. Taxonomy-aware training preparation
4. Locator/SAM training
5. Inference writeback and report generation

#### 9.2.2 Training integration (current)
- GUI training now starts from `build_training_preflight(...)`, not from governance manifest loading.
- Preflight evaluates the current saved project annotations and real image files, then builds the stage-specific train/val sample lists.
- `TrainingPreflightDialog` is the operator-facing gate before the thread starts.
- If there are no eligible locator samples, the locator stage is skipped.
- If there are no eligible SAM/parts samples, the SAM stage is skipped.
- If locator training hits OOM, the GUI can offer retry at a lower exact size pair from preflight.

#### 9.2.3 Runtime signals and UX
- Background threads emit log/progress/result signals to avoid UI blocking.
- Training and inference workflows are now more explicit about source artifacts, selected locator resolution, route usage, and structured validation outputs.

#### 9.2.3.1 Current structured training-report outputs
- `TrainingReportDialog` now reads structured payloads including:
  - `report_summary.json`
  - `validation_index.csv`
  - `val_details/` detail overlays
- The validation table is deterministic and browseable by row, rather than being only a static stitched preview.

#### 9.2.4 Workbench → Blink explicit entry flow (current)
Current operator path:
1. select an image in the workbench
2. select the target part in the taxonomy list
3. click **`Open in Blink Workbench`**
4. in the Blink entry dialog, choose:
   - **Target Part** = the part to refine in this session
   - **Entry ROI** = the existing manual box or auto box used to enter the local view
5. the dialog now explicitly explains that:
   - **Target Part** is the child part to refine
   - **Entry ROI** is the parent/context region Blink will zoom into
   - current guidance explicitly mentions `Eye -> Head`
6. if the project already remembers a parent/context ROI for this target part, the dialog reuses that remembered context by default
7. if the project does not remember one yet, Blink does not silently guess; the operator must choose explicitly
8. Blink receives a concrete session payload instead of trying to infer user intent from the current image alone
9. if a parent part and child target part are now known for the session, the project can register that parent -> child relation as a candidate project route

Practical meaning for research workflow:
- large-part localization and small-part refinement are now connected explicitly
- the operator can enter through a biologically useful parent region (for example, a head box) without hardcoding a complete taxonomy graph first
- once that choice is made, the same project can remember it instead of forcing the operator to restate the same parent relation every session
- the same session path can also seed a project route candidate for later single-image or batch inference use

#### 9.2.5 Blink local session semantics (`AntSleap/ui/blink_lab.py`)
Current Blink session behavior is intentionally split into different layers:

**A. What the local view is for**
- Blink opens in a local ROI-focused view
- context boxes may remain visible for orientation
- editable polygon work is restricted to the **target part** of the current session

**B. What each main Blink button means**
- **`Sync from Workbench`**
  - reloads workbench annotations into Blink
  - if the Blink session has unapplied local edits, the user must explicitly discard them before the sync can overwrite local state
- **`BLINK SWITCH`**
  - cycles masking/view mode only: `NORMAL` → `INSIDE` → `OUTSIDE`
  - this does not save labels and does not generate training data
- **`AUTO-ANNOTATE DRAFT`**
  - requires a route-appointed expert for the current parent -> target route
  - the appointed target-part expert predicts a local box inside the session ROI
  - base SAM turns that box into a draft polygon
  - the draft polygon is then refined manually by the researcher
- **`Draw Box (For SAM Draft)`**
  - lets the researcher draw a temporary SAM prompt box manually
  - base SAM turns that prompt into a draft polygon immediately
  - this prompt box is intentionally separate from the later shrink box semantics
- **`EXECUTE AUTO-SHRINK`**
  - requires a loose box plus a golden polygon for the current part
  - generates the shrink trajectory
  - stores that trajectory into project `trajectories` immediately
  - this is the main path for Blink training-data accumulation
- **`APPLY TO GLOBAL`**
  - projects local refined annotation back into full-image coordinates
  - writes back only the current target part
  - this is how the refined result becomes the formal workbench/project annotation
- **`TRAIN EXPERT MODEL`**
  - trains only the current part
  - uses trajectory-backed samples for that part across the current project
  - it does not train on all annotated parts in the project

**C. What is now visible during Blink expert training**
- Blink now includes a visible `Training Log` panel in the training area.
- The UI clears that panel at the start of a new run, appends an initial start message, and then streams trainer logs through the Blink training thread signal chain.
- This makes local-expert training easier to inspect during long annotation sessions.

#### 9.2.6 Current data semantics: trajectory vs formal annotation
The current system now makes an important distinction:

- **Draft-assist prompt box**
  - used only to obtain an initial draft polygon from base SAM
  - can come from the route-appointed expert path or the manual prompt-box path
  - is intentionally **not** persisted as the formal shrink box

- **Trajectory data** (`trajectories[part_name]`)
  - produced by `EXECUTE AUTO-SHRINK`
  - used by `BlinkTrajectoryDataset` and `BlinkExpertTrainer`
  - saved immediately when auto-shrink succeeds
  - now also stores `parent_context` (`parent_part`, `parent_box`, `source`) for macro→micro training semantics

- **Formal annotation data** (`parts`, `boxes`, `auto_boxes`)
  - updated by `APPLY TO GLOBAL`
  - this is what the main workbench treats as the accepted project result

This distinction matters operationally:
- a sample can already contribute to Blink training after auto-shrink
- but the refined polygon/box is not considered formally adopted until apply-to-global happens

#### 9.2.7 Dirty-session protection (current)
Current same-image/runtime safety rules:
- main-workbench point edits do not auto-refresh Blink at all anymore
- if Blink has unapplied edits, explicit sync from workbench is blocked
- starting a new Blink session on top of dirty local state requires explicit discard confirmation
- forcing sync is an intentional destructive action, not a silent background overwrite

For researchers, this reduces the risk of losing fine local edits while still allowing the workbench and Blink to coexist in one session.

#### 9.2.8 Current Chinese UI status
Major researcher-facing Chinese UI coverage now includes:
- workbench dialogs and operator labels in `main.py`
- Blink entry dialog and Blink control/status text in `blink_lab.py`
- cropper workflow text in `cropper.py`
- PDF runtime-control labels and related dialogs in `pdf_processing_widget.py`

Blink control/status readability also improved operationally:
- long status/error labels now wrap instead of clipping in the control panel
- the model-selector delete controls are now explicit and stateful instead of presenting as ambiguous red blocks
- the English model-selector rows now use shared alignment rather than drifting visually
- the PDF screener V2 folder option now uses meaning-first wording instead of the older abstract `Isolate` phrasing

This was implemented as targeted translation cleanup using the existing UI translation pattern, not as a new i18n framework rewrite.

#### 9.2.9 Project route management in active UI/runtime behavior
- Route management now lives under `Settings -> Model Settings -> Inference -> Project Route Management`.
- The UI is now a tree rather than a flat table:
  - parent node
  - route node
  - expert node(s)
- Route rows currently show:
  - parent
  - child
  - enabled
  - expert
  - runtime status
  - registration source
- Third-layer expert nodes now prefer the current project's persisted appointed/history experts.
- Runtime-discoverable experts still appear, but only as supplemental candidates.
- Runtime status can distinguish cases such as:
  - enabled
  - disabled
  - expert not appointed yet
  - expert file missing
- Current route semantics are intentionally conservative:
  - Blink can register a candidate
  - operator appoints the expert
  - operator enables the route
  - inference uses it if it is valid
- Current route persistence semantics are:
  - `project-v2` manifest format
  - nested `appointed_expert`
  - nested `expert_candidates`
  - backward-compatible migration from older flat route records
- The repo still does **not** implement route auto-scoring or automatic route approval.

#### 9.2.10 Expert-registry delete behavior in Blink
- There are now two distinct delete paths in the expert registry:
  - deleting a selected expert file
  - deleting a selected child-part expert bucket
- Bucket delete is intentionally treated as high-risk because it can invalidate route branches in the current project.
- The operator now sees:
  - a preview of files that will be deleted
  - the matching current-project routes that reference that child part
  - an explicit cleanup checkbox for current-project route branches
  - a second typed-confirmation requirement
- If cleanup is enabled, the current project removes matching route branches after successful bucket deletion.
- If cleanup is disabled, the current project keeps those route branches, and they can later surface missing-expert behavior until manually cleaned.

---

### 9.3 Module C — Governance Core (`AntSleap/core/governance/`)

#### 9.3.1 View contract and migration
- `view_contract.py`: validates schema (`v2`) and required fields.
- `migration.py`: upgrades legacy records into contract-compliant structure.

#### 9.3.2 Resolver and policy loading
- `view_resolver.py`: canonicalizes view labels/signals.
- `policy_loader.py`: strict policy validation with explicit error reporting.

#### 9.3.3 Deterministic split and leakage controls
- `splitter.py`: deterministic split generation with stable membership fingerprint.
- `grouping.py`: leak/collision checks across train/val groups.

#### 9.3.4 Manifest generation and loading
- `manifest_builder.py`: composes train/eval manifest from policy and record eligibility.
- `training_manifest_loader.py`: maps manifest sample IDs back to labeled project entries.

#### 9.3.5 Metrics and quality gates
- `evaluator.py`: per-view metric calculator.
- `redline_gate.py`: target-view threshold gate with reason codes.
- `sample_guard.py`: enforces sample sufficiency; can force global fail on low evidence.
- `headview_monitor.py`: head-view monitor-only report (non-blocking).

#### 9.3.6 Candidate governance
- `candidate_bridge.py`: DB→candidate artifact export (`candidate_only` mode).
- `risk_scorer.py`: risk-tier assignment and policy-based sampling plan.
- `router.py`: Core-2/Frontier/Ambiguous routing with route reasons.
- `idempotency.py`: stable ID set comparison + dedup diagnostics.

#### 9.3.7 Trigger logic
- `locator_trigger.py`: evaluates recommendation trigger from run-history patterns:
  - consecutive target-view failures
  - single-run pass-rate gap threshold

---

### 9.4 Governance CLI Surface (`tools/governance/`)

#### 9.4.1 Contract/migration/resolver/policy
- `validate_contract.py`
- `migrate_project_views.py`
- `test_view_resolver.py`
- `validate_policy.py`

#### 9.4.2 Split and leakage
- `build_split_manifest.py`
- `check_split_determinism.py`
- `check_leakage_groups.py`

#### 9.4.3 Train/eval manifests
- `build_train_manifest.py`
- `dry_run_training_split.py`
- `check_headview_block.py`

#### 9.4.4 Metrics/redline/sufficiency/head monitor
- `calc_per_view_metrics.py`
- `build_redline_report.py`
- `check_redline_report.py`
- `check_sample_sufficiency.py`
- `build_headview_monitor.py`

#### 9.4.5 Candidate path and routing
- `export_pdf_candidates.py`
- `build_sampling_plan.py`
- `check_sampling_rates.py`
- `route_candidates.py`
- `check_candidate_dedup.py`
- `check_bridge_mode.py`

#### 9.4.6 Trigger and suites
- `eval_locator_trigger.py`
- `run_acceptance_suite.py`
- `run_core2_pipeline.py`
- `check_docs_policy_sync.py`

#### 9.4.7 Recovery boundary note
- Governance-side migration/rebuild tools can help with schema normalization and downstream view contracts.
- They should **not** be described as the same thing as normal GUI project opening.
- Current practical boundary:
  - moved image paths may be recovered by `ProjectManager` path fallback when `known_relocated_roots` is configured and the relocated files exist
  - malformed/truncated JSON still requires external/manual/governance-side recovery before the GUI can load it

---

### 9.5 Acceptance Contract (Operational)

Current acceptance suite check IDs:
- `CHK_CONTRACT_V2`
- `CHK_SPLIT_DETERMINISM`
- `CHK_HEADVIEW_BLOCK`
- `CHK_REDLINE_TARGET_VIEW`
- `CHK_BRIDGE_MODE`
- `CHK_SAMPLING_RATES`
- `CHK_IDEMPOTENCY_DEDUP`

Acceptance output contract:
- `all_pass: bool`
- `failing_check_ids: string[]`
- per-check command/output/exit_code details

---

### 9.6 End-to-End Orchestrator Contract

`run_core2_pipeline.py` stage model:
1. migrate project
2. build train manifest
3. build split run1
4. build split run2
5. check split determinism
6. check leakage
7. calc per-view metrics
8. build redline report
9. sample sufficiency guard
10. build head monitor
11. export candidates
12. build sampling plan
13. route candidates
14. dedup check
15. evaluate locator trigger
16. run acceptance suite

`run_index.json` fields include:
- `status` (`passed`/`failed`)
- `failed_stage`
- `stages[]` with command/exit/output
- normalized artifact pointers

---

### 9.7 Data Structure Examples (Current)

#### 9.7.1 Candidate artifact (bridge output)
```json
{
  "schema_version": "core2-candidate-bridge-v1",
  "mode": "candidate_only",
  "source_db": "ant_literature.db",
  "total_candidates": 0,
  "candidates": [
    {
      "candidate_id": "pdf1_page3_img1",
      "candidate_stable_id": "cand_xxxxxxxx",
      "pdf_id": 1,
      "page_number": 3,
      "image_path": "triptych_v2_v2_artifacts/figure_images/pdf1_p003_f001_triptych.png",
      "source_ref": {"db_path": "...", "table": "figure_records", "row_id": 1},
      "confidence": {
        "final_confidence": 0.92,
        "combined_relevance_score": 0.92,
        "text_image_match_score": 0.0,
        "confidence_score": 0.83
      },
      "species_candidate": "Formica aurata",
      "review_status": "accepted",
      "category": "ant_triptych",
      "multimodal_review_mode": "real",
      "multimodal_model_used": "gpt-5.4"
    }
  ]
}
```

#### 9.7.2 Sampling report
```json
{
  "schema_version": "core2-sampling-v1",
  "sampling_rates": {"high": 1.0, "medium": 0.3, "low": 0.1},
  "summary": {
    "total_candidates": 100,
    "tiers": {
      "high": {"count": 12, "sample_rate": 1.0, "sample_count": 12},
      "medium": {"count": 38, "sample_rate": 0.3, "sample_count": 11},
      "low": {"count": 50, "sample_rate": 0.1, "sample_count": 5}
    }
  }
}
```

#### 9.7.3 Routing report
```json
{
  "schema_version": "core2-routing-v1",
  "summary": {"core2_count": 0, "frontier_count": 0, "ambiguous_count": 0},
  "decisions": [
    {
      "candidate_id": "...",
      "bucket": "Core-2",
      "route_reasons": ["core2_target_confident"],
      "view": "lateral",
      "confidence": 0.91,
      "risk_tier": "low"
    }
  ]
}
```

#### 9.7.4 Redline report
```json
{
  "schema_version": "core2-redline-v1",
  "global_pass": false,
  "target_views": ["lateral", "dorsal"],
  "target_view_reports": {
    "lateral": {
      "checks": {"pass_rate": true, "boundary_overlap": true, "localization_error_px": true}
    },
    "dorsal": {
      "checks": {"pass_rate": false, "boundary_overlap": true, "localization_error_px": true}
    }
  }
}
```

---

### 9.8 Candidate Review Reality (Critical UX Note)

- Current candidate pool is **not** a visual approval panel in the workbench.
- Review path remains hybrid:
  1. browse extraction DB in PDF widget
  2. inspect governance artifacts
  3. manually import approved images to annotation project

This is intentional in current phase and documented as a known gap for future UI integration.

---

### 9.9 Current BLINK/Cascade Runtime Notes (No Longer Historical-Only)

BLINK is now an active current UI/runtime path, not just continuity context:
- coordinate mapping still provides global/local consistency between workbench and Blink views
- trajectory-based supervision remains the data backbone for Blink micro-expert training
- session semantics are now explicit enough to support practical coarse→fine annotation work inside the current product

Current boundary:
- explicit workbench→Blink entry and local refinement are production-relevant current behavior
- cascade gating and broader expert routing remain more experimental than the entry/writeback/session model itself

---

### 9.10 Practical Handoff Checklist for Next Agent

Before modifying governance behavior:
1. Confirm policy values in `AntSleap/config/view_policy_core2.json`.
2. Re-run `run_acceptance_suite.py` on target artifacts.
3. Verify `run_core2_pipeline.py` still outputs deterministic `run_index.json`.
4. Preserve candidate-only bridge mode unless explicitly expanding ingestion policy.

Before modifying workbench/Blink behavior:
5. Re-check the difference between:
   - `EXECUTE AUTO-SHRINK` = save trajectory training material
   - `APPLY TO GLOBAL` = write refined annotation back to formal project state
6. Preserve target-part-only writeback unless the user explicitly asks to broaden local-session commit scope.
7. Preserve dirty-session protection unless the user explicitly accepts silent-overwrite risk.
8. Do not claim that GUI project loading can auto-repair malformed JSON unless such a repair path is actually implemented.

Cross-doc requirement:
9. Keep `CHANGELOG_zh.md` and `LLM_CONTEXT_DETAILED.md` in sync when workflow semantics or recovery boundaries change.
