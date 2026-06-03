---
name: taxamask-workflows
description: Always-relevant TaxaMask workflow card for the embedded Agent. Use for TaxaMask operation, configuration, troubleshooting, documentation, or code changes involving the Agent Center, 2D/STL morphology annotation, TIF volume segmentation, PDF evidence processing, model/backend settings, training readiness, or project safety boundaries.
when_to_use: Treat this skill as the default TaxaMask domain protocol. Read or run it at the start of any TaxaMask task unless the request is completely unrelated to this repository.
allowed-tools: read_file, list_files, glob, grep, git_status, git_diff, shell, plan_update
context: instruction
paths:
  - ANTCODE.md
  - .lab-agent/memory.md
  - .lab-agent/skills/taxamask-pdf-evidence/SKILL.md
  - TaxaMask使用手册.md
  - LLM_CONTEXT_DETAILED.md
  - docs/ant3d_workbench/
---
# TaxaMask Workflows

Use this skill as the compact operating map for TaxaMask. It is not merely an optional helper: `ANTCODE.md` mirrors the highest-priority TaxaMask rules into the initial prompt, and this skill is the first expandable workflow card. Do not load the full manual by default. Load targeted docs only when the task needs detail.

## First Read

1. Treat `ANTCODE.md` as the always-on TaxaMask Agent protocol.
2. Read `.lab-agent/memory.md` for current project memory and code map.
3. Use this skill to choose the workflow route and safety boundary before answering or editing.
4. Read deeper docs only when needed:
   - user operation details: `TaxaMask使用手册.md`
   - current architecture handoff: `LLM_CONTEXT_DETAILED.md`
   - Agent integration: `docs/ant3d_workbench/TaxaMask_AntCode项目记忆与对接手册_zh.md`
   - Agent/PDF skill design: `docs/ant3d_workbench/TaxaMask_Agent侧栏与PDF_Skill设计_zh.md`
   - PDF evidence operations: `.lab-agent/skills/taxamask-pdf-evidence/SKILL.md`
   - TIF implementation contracts: `docs/ant3d_workbench/TIF项目结构实施设计_zh.md` and `docs/ant3d_workbench/TIF后端契约_v1_实施设计_zh.md`

## Current Product Shape

- Visible product name: TaxaMask.
- Internal Python package: `AntSleap`, kept for compatibility and project history.
- Startup page: TaxaMask Agent Center with embedded Ant-Code dashboard in the main area.
- Right rail: direct workflow cards for `2D/STL Morphology` and `TIF Volume`.
- Workbenches keep only lightweight `Start Center` / `Ask Agent` entries, not full chat panels.
- PDF is an evidence/provenance and agent/headless workflow, not the primary visual workbench.

## Workflow Routes

Choose the route before editing or advising:

- `2D/STL morphology`: ordinary morphology images plus STL-rendered 2D views. Uses the Labeling Workbench as the daily surface, with `Parent-part annotation` and `Child-part annotation` sections for parent boxes, child structures, project model profiles, Locator/SAM, route-appointed child experts, literature trait alignment, and the 2D external backend. The standalone Blink widget is compatibility/development fallback, not the normal operator route.
- `TIF volume`: continuous TIF/AMIRA-style volumes. Uses TIF Volume Workbench, material IDs, `working_edit`, `manual_truth`, `model_draft`, TIF export, and the TIF backend contract.
- `PDF evidence`: screens PDFs, extracts figure/caption evidence, writes accepted and needs-review figure artifacts, and can structure pure PDF text into `taxon -> part -> description` records. Load `.lab-agent/skills/taxamask-pdf-evidence/SKILL.md` for PDF runs, candidate import, evidence indexes, literature trait lookup, or PDF failure triage. The current default ant figure review profile is the broad `蚂蚁分类学图版宽松复核_示例`: it accepts single-ant-taxon morphology figures and local diagnostic structures, and rejects multi-species/multi-taxon comparison figures. The current default part-description profile is `part_description_configs/蚂蚁分类学部位描述抽取_示例.json`; it uses Text LLM text blocks only, not images. Results are candidate/evidence artifacts and must not automatically become training truth.
- `Agent Center`: natural-language configuration, error triage, PDF workflow orchestration, training-readiness checks, and project documentation support.

## Safety Boundaries

- Never write back to original AMIRA source files.
- Never turn PDF candidates or model predictions into `manual_truth` automatically.
- TIF labels are material-ID label fields and are independent from 2D/STL structure labels.
- Keep large TIF volumes in sidecars, not project JSON.
- TIF is currently experimental. Do not keep pushing TIF Ask Agent / embedded WebEngine changes when the user has asked to pause TIF work. Known black-screen logs include `QQuickWidget ... no QRhi` and `OpenGL is not compatible with this QQuickWidget`; treat this as a graphics-backend isolation issue.
- Do not run GPU-heavy training/inference unless the user says the GPU is available.
- Use `.tmp_validation/` for disposable checks and clean it before finishing.
- Do not modify `C:\saveproject\LBJ-workspace\lab-agent` source unless the user explicitly asks to work on Ant-Code itself.

## Settings Map

- General Settings: language, theme, startup behavior, autosave, and default internal runtime device.
- 2D/STL Model Settings: Profile, Parent-part annotation, Child-part annotation, Inference, and Advanced Extensions pages. The active project model profile controls parent backend, child default backend, locator scope, parent-context box aspect ratios, VLM target parts, and inference defaults.
- Advanced Extensions is the main switching/configuration surface for high-impact custom parent and child model sources. Parent-part and Child-part pages should remain operator-facing summaries plus ordinary training parameters.
- Parent-part backends: built-in Locator/SAM or external parent backend through `docs/contracts/external_backend_contract_v1.md`.
- Child-part route backends: `vit_b_blink`, `heatmap_blink`, or `external_blink`. External Blink uses `docs/contracts/external_blink_backend_contract_v1.md` and predicts a child box from an existing parent box.
- PDF extraction defaults to `TaxaMask_outputs/` for databases and run artifacts unless the user chooses another result folder.
- TIF Volume Model Settings: TIF backend defaults, Python executable, prepare/train/predict commands, export formats, and validation.
- TIF backend commands must include `{contract}` or `{contract_json}`.
- 2D/STL exports write `model_profile_summary.json`; inspect it when asking which active profile, parent backend, child backend, and route experts were associated with a dataset export.

## Custom Model Adaptation Permission Levels

- Level 1: read, diagnose, explain settings, inspect logs, inspect contracts, and point to relevant docs/source. No extra permission is needed.
- Level 2: edit an external model-adapter script or config under `external_backends/`, `external_backend_adapters/`, `model_backends/`, or `.tmp_validation/external_backends/`. Before editing, tell the user the file, the reason, and the risk that the selected custom model may fail or emit an incompatible result. The TaxaMask hook asks for model-adapter approval at tool execution time.
- Level 3: edit TaxaMask source under `AntSleap/`, `core/`, `tools/`, `tests/`, or `vendor/ant-code/src|tests|scripts`. Escalate here only when the existing external backend contract or settings cannot support the required model behavior. Before editing, tell the user what program area changes, why adapter/config is insufficient, and the risk to 2D/STL, TIF, Agent Center, import, training, or review. The TaxaMask hook asks for source-development approval at tool execution time.

Keep parent 2D/STL, child Blink, and TIF custom model routes separate. Whole-image/parent 2D/STL uses `ExternalBackendRunner` and `taxamask_external_backend_contract_v1`; child-part Blink uses `ExternalBlinkBackendRunner` and `taxamask_external_blink_contract_v1`; TIF uses `TifBackendRunner` and `ant3d_tif_backend_contract_v1`.

## Model Profile / Blink Debug Map

- Profile schema and migration: `AntSleap/core/model_profiles.py`, `AntSleap/core/project.py`.
- Route backend fields and legacy fallback: `AntSleap/core/cascade_routes.py`.
- Blink backend dispatch: `AntSleap/core/blink_expert_backends.py`, `AntSleap/core/cascade_manager.py`.
- ViT-B and heatmap expert manifests: `AntSleap/core/blink_expert_manifest.py`.
- Heatmap Blink train/infer: `AntSleap/core/blink_heatmap_dataset.py`, `AntSleap/core/blink_heatmap_trainer.py`.
- External Blink contract runner: `AntSleap/core/external_blink_backend.py`.
- Main UI settings and route expert panel: `AntSleap/main.py::ModelSettingsDialog`.
- Compatibility Blink training UI: `AntSleap/ui/blink_lab.py`.

When a child route fails, check in order: selected child part and parent context, parent box existence, route enabled state, `expert_backend`, manifest/weights path for internal backends, or `predict_command` for `external_blink`.

## Model Loading Rule

Locator and SAM are lazy-loaded:

- Startup Agent Center does not load Locator or SAM.
- TIF workflow does not load Locator or SAM.
- Entering/opening/importing the 2D/STL workflow preloads Locator and SAM.
- Returning to the Agent Center keeps already loaded 2D/STL models alive.
- On application close, the SAM worker thread should shut down cleanly.

## User Explanation Style

Explain in Chinese by default. Start with what the program is doing in research-workflow terms, then explain why it matters, then name the operational consequence or tradeoff. Keep code details available but secondary unless the user asks for them.
