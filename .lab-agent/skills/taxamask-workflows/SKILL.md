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

- `2D/STL morphology`: ordinary morphology images plus STL-rendered 2D views. Uses the Labeling Workbench as the daily surface, with the integrated `Parent-child refinement / Blink` panel for child structures, Locator/SAM, route-appointed experts, and the 2D external backend. The standalone Blink widget is compatibility/development fallback, not the normal operator route.
- `TIF volume`: continuous TIF/AMIRA-style volumes. Uses TIF Volume Workbench, material IDs, `working_edit`, `manual_truth`, `model_draft`, TIF export, and the TIF backend contract.
- `PDF evidence`: screens PDFs and extracts figure/caption evidence. Load `.lab-agent/skills/taxamask-pdf-evidence/SKILL.md` for PDF runs, candidate import, evidence indexes, or PDF failure triage. Results are candidate/evidence artifacts and must not automatically become training truth.
- `Agent Center`: natural-language configuration, error triage, PDF workflow orchestration, training-readiness checks, and project documentation support.

## Safety Boundaries

- Never write back to original AMIRA source files.
- Never turn PDF candidates or model predictions into `manual_truth` automatically.
- TIF labels are material-ID label fields and are independent from 2D/STL structure labels.
- Keep large TIF volumes in sidecars, not project JSON.
- Do not run GPU-heavy training/inference unless the user says the GPU is available.
- Use `.tmp_validation/` for disposable checks and clean it before finishing.
- Do not modify `C:\saveproject\LBJ-workspace\lab-agent` source unless the user explicitly asks to work on Ant-Code itself.

## Settings Map

- General Settings: language, theme, startup behavior, autosave, and default internal runtime device.
- 2D/STL Model Settings: built-in Locator/SAM/Blink training and inference, locator scope, parent-context box aspect ratios, Blink defaults, route expert management, and the 2D external backend.
- TIF Volume Model Settings: TIF backend defaults, Python executable, prepare/train/predict commands, export formats, and validation.
- TIF backend commands must include `{contract}` or `{contract_json}`.

## Model Loading Rule

Locator and SAM are lazy-loaded:

- Startup Agent Center does not load Locator or SAM.
- TIF workflow does not load Locator or SAM.
- Entering/opening/importing the 2D/STL workflow preloads Locator and SAM.
- Returning to the Agent Center keeps already loaded 2D/STL models alive.
- On application close, the SAM worker thread should shut down cleanly.

## User Explanation Style

Explain in Chinese by default. Start with what the program is doing in research-workflow terms, then explain why it matters, then name the operational consequence or tradeoff. Keep code details available but secondary unless the user asks for them.
