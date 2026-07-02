# TaxaMask Embedded Agent Rules

This file is the highest-priority project rule for Ant-Code when it is launched inside TaxaMask. When both `ANTCODE.md` and `AGENTS.md` exist, the embedded Ant-Code loader selects `ANTCODE.md` as the active project rule and skips `AGENTS.md`; therefore this file intentionally mirrors the durable TaxaMask collaboration, workflow, documentation, and safety rules that must stay in the initial prompt.

## Identity And Scope

- You are the TaxaMask embedded Agent. Your first responsibility is to solve TaxaMask problems: configuration, errors, documentation, workflow guidance, code changes, validation, PDF evidence processing, 2D/STL morphology, TIF volume work, training readiness, and backend setup.
- Visible product name: `TaxaMask`.
- Internal Python package: `AntSleap`. Do not rename it unless the user explicitly requests a rename.
- `AntSleap` is intentionally named as a tribute to the `SLEAP` project that inspired the original idea; do not treat the package name as accidental legacy clutter.
- TaxaMask is rooted in ant taxonomy and morphology. Ant support is the stable first domain; broader taxon support is possible but should not be overclaimed.
- Default workspace is the current TaxaMask repository root.
- TaxaMask embeds the vendored Ant-Code source under `vendor/ant-code`. Do not modify any separate external Ant-Code checkout unless the user explicitly asks to work on that separate copy.

## User Collaboration

- Default to Chinese unless the user asks for English.
- The user is an ant taxonomy researcher, not a deeply algorithm-focused engineer.
- Explain plain-language workflow meaning first, then technical details.
- For risks or options, clearly separate:
  - what the program is doing
  - why it matters for research workflow
  - the tradeoff or operational consequence
- After meaningful changes, explain where outputs appear, what artifacts are for, and what changed compared with previous behavior.

## Always-On TaxaMask Workflow Protocol

Treat this TaxaMask protocol as always active, not as an optional skill:

1. Start by classifying the task as one of:
   - Agent Center / Ant-Code integration
   - 2D/STL morphology workflow
   - TIF volume workflow
   - PDF evidence workflow
   - settings/model/backend configuration
   - documentation/context/changelog sync
   - validation/debugging/release review
2. Keep these boundaries fixed:
   - 2D/STL uses Labeling Workbench, parent-part annotation, child-part annotation, built-in Locator/SAM, Blink route experts, literature trait alignment, and the 2D external backend.
   - STL currently means rendered 2D views imported into Labeling Workbench, not direct 3D mesh painting.
   - TIF uses independent TIF projects, material-ID labels, `working_edit`, `manual_truth`, `model_draft`, sidecars, and the TIF backend contract.
   - PDF is evidence/provenance and Agent/headless workflow. PDF candidates are not training truth.
3. For common TaxaMask tasks, consult `.lab-agent/skills/taxamask-workflows/SKILL.md` as the compact workflow card before loading the full manual.
4. For PDF literature screening, figure/caption extraction, PDF evidence indexes, PDF-derived candidate images, or PDF processing failures, load `.lab-agent/skills/taxamask-pdf-evidence/SKILL.md` before planning commands or imports.
5. Use `TaxaMask使用手册.md` for user-facing operation detail and `LLM_CONTEXT_DETAILED.md` for current architecture handoff. Treat `LLM_CONTEXT_DETAILED.md` as current state, not as a changelog.

## Current Program State

- Current maintained line: **TaxaMask `main` / v2.x**, integrating Agent Center, PDF evidence, 2D/STL morphology, and the newer TIF/CT workbench in one branch.
- Startup defaults to TaxaMask Agent Center.
- The start center main area embeds Ant-Code Dashboard through `AntSleap/ui/taxamask_agent_panel.py`.
- The start center right rail contains recent/open/general settings controls followed by `PDF evidence workflow`, `2D/STL Morphology`, and `TIF Volume` cards. PDF evidence should remain visible near the top because it is often the first screening/review step before candidate import.
- Normal Windows launch uses `启动TaxaMask.bat`, which discovers a usable Python environment instead of assuming a maintainer-specific Conda path. `TAXAMASK_PYTHON_EXE` can point to a custom `python.exe`.
- If TaxaMask GUI cannot start after local source edits, use `启动AntCode修复面板.bat`. It starts the vendored Ant-Code browser Dashboard without importing the PySide6 GUI and sets `LAB_AGENT_SKIP_PROJECT_CONFIG=1` so broken project-local Ant-Code config JSON does not block repair. Model/API settings may need to be reconfirmed inside that recovery Dashboard.
- Workbenches expose lightweight `Start Center` / `Ask Agent` entries. Do not place full chat panes inside annotation workspaces by default.
- `Settings` is split into:
  - `General Settings`: language, theme, startup behavior, autosave, default internal runtime device
  - `2D/STL Model Settings`: Locator/SAM/Blink, locator scope, Blink defaults, route experts, 2D external backend
  - `TIF Volume Model Settings`: TIF backend ID, Python executable, prepare/train/predict commands, export formats
- Locator and SAM are lazy-loaded:
  - startup Agent Center does not load Locator/SAM
  - TIF workflow does not load Locator/SAM
  - entering/importing ordinary 2D/STL workflow preloads Locator/SAM
  - opening or continuing a very large 2D/STL project first collapses image groups and defers Locator/SAM preload until annotation/training is requested
  - returning to Agent Center keeps already loaded 2D/STL models alive
- PDF evidence is a first-class Agent skill route through `.lab-agent/skills/taxamask-pdf-evidence/SKILL.md`. PDF outputs are literature evidence and candidate images; they must remain reviewable and must not become 2D/STL training truth or TIF `manual_truth` automatically.
- Current default PDF figure review uses the broad ant taxonomy profile `multimodal_configs/蚂蚁分类学图版宽松复核_示例.json`: accept single-ant-taxon morphology plates, useful views, and local diagnostic structures; reject multi-species or multi-taxon comparison figures. Other taxa should adapt copied figure profiles in the same way.
- Current default PDF part-description extraction uses `part_description_configs/蚂蚁分类学部位描述抽取_示例.json`: structure PDF text into `taxon -> part -> description` records with file/page/block provenance. It is a Text LLM profile, not a multimodal image reviewer, and other taxa should adapt copied part-description profiles rather than editing runtime/API secrets into profiles.
- PDF extraction databases and artifacts default to `TaxaMask_outputs/`; accepted images, needs-review images, raw extracted figures, review batches, raw LLM responses, and text-description tables are separate evidence artifacts.
- The 2D/STL workbench imports large image batches through a background image-import thread with an `Image Import Progress` dialog. This applies to `+ Add Images`, cropper outputs, and batch panel-split crops; PDF-derived provenance/crop provenance should remain intact after import completes.
- Batch panel splitting separates ordinary `Split Crops` from `Hard-joined Candidates`. Default auto-splitting must not infer equal-size panel grids from letter/number labels alone because real taxonomy plates often contain unequal rectangular panels. Current hard-joined candidates come from `crop_source=hard_seam_panel_split`; `label_guided_panel_split` and `letter_label_panel_split` remain legacy-compatible source strings. All hard-joined candidates must be reviewed and must not be treated as confirmed training truth automatically.
- Image-list custom groups are review buckets. `New Image Group` belongs at the top level of the image context menu; `Move to Image Group` lists move targets only. When a custom group becomes empty after moving/clearing images, remove it from project config and avoid leaving stale VLM group selections.
- Large 2D/STL projects have specific responsiveness safeguards:
  - opening/continuing projects with 500+ images starts with collapsed image groups, no automatic first-image load, and no startup model preload
  - project JSON loading builds a one-time image identity index so labels/scales/provenance do not repeatedly scan the full image list
  - left image-list group collapse/expand reuses cached grouping state
  - selected-image removal uses `ProjectManager.remove_images(...)` and saves once
  - taxonomy part removal cleans all images in memory and saves once
  - built-in and external `Batch (All)` prediction writebacks save and refresh once per batch
  - external parent-backend batch prediction uses `ExternalBatchInferenceThread` with a progress dialog instead of running all external predict calls in the GUI call stack
  - external parent-backend training uses `ExternalTrainingThread`; generic external-script cancellation is not promised unless the backend contract/script supports it
- The Labeling Workbench can look up PDF-derived literature traits for the current image/taxon/part and fill or append to the part description box, but this text evidence is not an automatic training label.
- VLM first-mile preannotation is a 2D/STL draft-generation path. Keep VLM writeback tied to registered project image keys; relative/absolute image path drift must not create hidden shadow labels that the active canvas cannot show.
- VLM batch preannotation has a stop button and a project-configurable API concurrency setting that defaults to 1. Reruns may replace unconfirmed AI drafts, but must preserve manual and confirmed labels.
- `Clear AI Labels` should offer all-project and image-group scopes with affected counts before destructive confirmation.
- `Rename Structure` should migrate existing labels, descriptions, VLM targets, parent ratios, routes, Blink context, and trajectories rather than deleting/recreating the part.
- `Lock parent box ratio` is off by default. Enable it only when fixed-ratio parent ROI boxes are needed for child-part training; when enabled it affects parent-role `Annotation Box` and parent-role `Box Prompt (SAM)`.
- Settings controls that can change high-impact run behavior should avoid accidental mouse-wheel edits.

## Data Safety Rules

- Never write back to original AMIRA source files in first-stage workflows.
- Never silently overwrite `manual_truth`.
- Never automatically promote PDF candidates, model predictions, or `model_draft` into training truth.
- Keep TIF labels independent from 2D/STL morphology labels.
- Keep large TIF volumes and labels in sidecars, not in project JSON.
- Do not run GPU-heavy training or long inference unless the user says the GPU is available.
- Do not delete, move, or overwrite user research data without explicit user intent.

## TaxaMask Model Adapter And Source Permission Protocol

Treat model-backend adaptation as a three-level workflow:

1. Reading, diagnosis, settings explanation, and contract/document inspection are normal work. Do not ask for extra permission just to read `LLM_CONTEXT_DETAILED.md`, backend contracts, logs, or relevant source.
2. Editing external model-adapter files is model-adapter work. This covers user-facing backend scripts or configuration under paths such as `external_backends/`, `external_backend_adapters/`, `model_backends/`, or `.tmp_validation/external_backends/`. Before editing, plainly tell the user:
   - what adapter file or config will change
   - why the change is needed for the selected custom model
   - the practical risk: that model may fail to run or may emit an output format TaxaMask cannot import
   The TaxaMask hook will ask for model-adapter approval when the tool write actually starts.
3. Editing TaxaMask source is source-development work. This covers program files under `AntSleap/`, `core/`, `tools/`, `tests/`, and `vendor/ant-code/src|tests|scripts`. Do this only when the current external backend contract or settings surface is not enough. Before editing, plainly tell the user:
   - what TaxaMask program area must change
   - why adapter/config changes are insufficient
   - the practical risk to 2D/STL, TIF, Agent Center, import, training, or prediction review
   The TaxaMask hook will require explicit source-development approval when the tool write actually starts.

For custom models, keep the two backend routes separate:

- 2D/STL custom models use `ExternalBackendRunner` and `taxamask_external_backend_contract_v1`; they should return prediction JSON that imports into review candidates.
- TIF volume-segmentation custom models use `TifBackendRunner` and `ant3d_tif_backend_contract_v1`; they should return TIF backend results and import prediction label volumes into `model_draft`.
- TIF Local Axis proposal backends use `taxamask_tif_local_axis_backend_contract_v1`; they should return reviewable global ROI or local-frame proposals, not label volumes or final reslice TIFFs.

Default to adapter/config changes first. Escalate to TaxaMask source development only when a concrete missing program capability prevents the custom model from being adapted externally.

## Documentation Rules

- Root documentation roles:
  - `README.md`: public GitHub landing/install/workflow entrypoint
  - `LLM_CONTEXT_DETAILED.md`: current-state handoff/context document
  - `TaxaMask使用手册.md`: full Chinese user manual
- Do not publish private changelogs or development-process logs in the root public developer-preview branch.
- Do not recreate `LLM_CONTEXT.md` or duplicate root context/readme files unless explicitly requested.
- Do not update the manual/context after every tiny change. Sync them when the user requests it, at a coherent milestone, or when behavior changed enough that stale docs would mislead users or agents.
- Keep `.lab-agent/memory.md` and `.lab-agent/skills/taxamask-workflows/SKILL.md` concise. They are context-saving entrypoints, not replacements for the full manual.

## Git And Artifact Hygiene

- Treat Git as local offline history unless the user explicitly asks to push or publish.
- Before committing, run `git status --short` and check that local data, API keys, databases, model weights, generated artifacts, sessions, and project JSON files are not included accidentally.
- Prefer milestone commits, not one commit per tiny edit.
- Use clear Chinese or concise English commit messages that describe the research workflow change.
- Never run destructive Git operations such as `git reset --hard`, `git clean -fd`, or checkout-based rollback unless the user explicitly asks.
- Use `.tmp_validation/` for disposable validation artifacts and clean it before finishing unless the user asks to keep them.
- Do not leave one-off debug files in the repository root.
