# Project Memory

## TaxaMask embedded Ant-Code operating memory

This workspace is the TaxaMask repository at `C:\saveproject\LBJ-workspace\Formica-Flow-Latest`. When Ant-Code is launched from TaxaMask, it is embedded in the TaxaMask start center and should treat this repository as its default working area.

Primary rule source:
- `ANTCODE.md` is the highest-priority always-on project rule for the embedded TaxaMask Agent. It mirrors the core TaxaMask workflow protocol into the initial prompt.
- Use this `.lab-agent/memory.md` as short operational memory after `ANTCODE.md`.
- Use `.lab-agent/skills/taxamask-workflows/SKILL.md` as the always-relevant compact workflow card for Agent Center, 2D/STL, TIF, PDF evidence, settings, and training-readiness tasks.
- Use `.lab-agent/skills/taxamask-pdf-evidence/SKILL.md` for PDF literature screening, figure/caption extraction, PDF evidence indexes, PDF-derived candidates, candidate import, and PDF failure triage.
- For deeper architecture details, read `docs/ant3d_workbench/TaxaMask_AntCode项目记忆与对接手册_zh.md` before broad refactors.

Core product stance:
- Keep the visible product name as TaxaMask.
- `AntSleap` remains the internal Python package name and is historically intentional.
- TaxaMask started from ant taxonomy image/PDF annotation, then expanded toward STL rendered morphology views and TIF volume segmentation.
- The first stable domain remains ant taxonomy and morphology. Do not overclaim broad multi-taxon support unless the user asks.

Ant-Code embedding boundary:
- TaxaMask embeds the vendored Ant-Code source under `vendor/ant-code`; it no longer starts the distributed `ant-code.exe` package from `lab-agent/dist`.
- TaxaMask starts it through `AntSleap/ui/taxamask_agent_panel.py` using Node.js:
  `node vendor/ant-code/src/cli/dashboard.js --project <TaxaMask repo root> --port <free local port> --no-open`.
- The old distributed executable is not a launch fallback. Process cleanup still recognizes old `ant-code.exe dashboard` commands only to remove historical orphan dashboard processes for this TaxaMask project.
- The embedded view defaults to workspace trust for this TaxaMask repository. Most local TaxaMask edits should not require repeated confirmation, but destructive actions, deleting data, changing external tools, or touching files outside this repo still need explicit user intent.
- Normal embedded Agent integration work belongs in this repo, especially `vendor/ant-code` and `AntSleap/ui/taxamask_agent_panel.py`. Do not modify the external `C:\saveproject\LBJ-workspace\lab-agent` tree unless the user explicitly asks to work on that separate copy.

UI structure to remember:
- Start center is now the Agent center. The embedded Ant-Code middle workspace is the main area.
- The right rail contains stacked workflow cards for `2D/STL Morphology` and `TIF Volume`.
- Labeling, Blink, and TIF workbenches should stay focused on annotation. They expose lightweight `Start Center` / `Ask Agent` entries instead of full chat panels.
- Labeling Workbench uses `Parent-part annotation` and `Child-part annotation` sections for parent boxes, child structures, Blink route experts, and literature trait alignment.
- When returning from a workbench to the Agent center, pass context such as `source_workbench`, `project_type`, `project_path`, active specimen/image/part/material, and recent logs.

Main code map:
- `AntSleap/main.py`: PySide main window, start center, menus, workflow routing, settings dialogs, Agent context handoff.
- `AntSleap/ui/taxamask_agent_panel.py`: embedded Ant-Code dashboard wrapper and WebView display adaptation.
- `AntSleap/ui/tif_workbench.py`: dedicated TIF volume workbench, slice UI, material controls, TIF backend buttons.
- `AntSleap/ui/blink_lab.py`: Blink refinement workbench and route expert training UI.
- `AntSleap/core/project.py`: legacy/current 2D morphology project manager.
- `AntSleap/core/stl_project.py` and `AntSleap/core/stl_rendered_views.py`: STL rendered-view registry/project support.
- `AntSleap/core/tif_project.py`: TIF project schema and specimen records.
- `AntSleap/core/tif_materials.py`: AMIRA-style material map.
- `AntSleap/core/tif_stack_import.py`: plain TIF stack import.
- `AntSleap/core/tif_export.py`: train-ready TIF volume export.
- `AntSleap/core/tif_backend.py`: external TIF backend contract runner.
- `AntSleap/core/external_backend.py`: 2D/STL external backend contract runner.
- `AntSleap/core/literature_descriptions.py`: PDF-derived literature trait lookup and provenance bridge for the Labeling Workbench description box.
- `AntSleap/ui/pdf_processing_widget.py` and `AntSleap/core/pdf_evidence.py`: PDF evidence tools and indexes.
- `tools/agentic/screen_pdfs.py`, `tools/agentic/extract_figures.py`, and `tools/agentic/import_candidates_to_project.py`: headless PDF evidence and candidate workflows used by Agent tasks.
- Default PDF figure review profile: `multimodal_configs/蚂蚁分类学图版宽松复核_示例.json`. It accepts single-ant-taxon morphology plates, including habitus, multi-view plates, head/local diagnostic structures, and same-taxon plate combinations; it rejects multi-species/multi-taxon comparison figures. Other taxa should copy a template and adapt the same profile fields rather than editing API/runtime secrets into profiles.
- Default PDF part-description profile: `part_description_configs/蚂蚁分类学部位描述抽取_示例.json`. It is a pure-text Text LLM profile for structuring PDF descriptions as `taxon -> part -> description`; it does not use images, does not store API/runtime secrets, and records source file/page/block provenance through `pdf_text_blocks`, `taxon_part_descriptions`, and `part_extraction_runs`.
- PDF extraction databases and artifacts default to `TaxaMask_outputs/`; accepted figure copies go to `accepted_figures/`, reviewable candidates go to `needs_review_figures/`, and raw extracted figures remain in `figure_images/`.

Project types:
- 2D/STL morphology uses the existing Labeling Workbench with parent-part annotation, child-part annotation, Locator/SAM, Blink route experts, and optional literature trait lookup. STL data means rendered 2D views from STL/mesh assets, not direct 3D mesh painting.
- STL rendered-view registry schema is `ant3d_stl_rendered_view_registry_v1`; STL rendered project schema is `ant3d_stl_rendered_project_v1` with project type `stl_rendered_views`.
- Opening an STL rendered-view project registers views into the Labeling Workbench; it is not a separate 3D renderer workbench.
- TIF project schema is `ant3d_tif_project_v1` with project type `tif_volume`.
- TIF labels are AMIRA-style material ID label fields and are independent from 2D/STL morphology labels.
- TIF layers must remain separate: `manual_truth` is human-confirmed training truth, `model_draft` is model output for review, and `working_edit` is the editable layer.

Training/backend rules:
- 2D/STL model settings and TIF volume model settings are separate.
- 2D/STL can use built-in Locator/SAM or `external_backend`.
- TIF uses `tif_backend` and the `ant3d_tif_backend_contract_v1` contract. It may target nnU-Net, MONAI, or custom scripts, but should not be hardwired to one model family.
- TIF prediction import must not overwrite `manual_truth` by default. Import predictions as `model_draft` or another reviewable candidate layer unless the user explicitly asks for a reviewed promotion path.
- Use the user-provided conda environment for validation when needed:
  `C:\Users\admin\anaconda3\envs\antsleap\python.exe`.

Research safety defaults:
- Do not write back to original AMIRA source files in first-stage workflows.
- Keep TIF project JSON lightweight; large volumes and labels belong in sidecar files/directories.
- Preserve provenance for PDF, STL rendered views, TIF imports, backend exports, and model predictions.
- PDF outputs are candidate/evidence artifacts. Import PDF-derived images only as reviewable 2D candidates such as `needs_review`; never automatically promote them to training truth or TIF `manual_truth`.
- PDF-derived literature descriptions can fill or append to the current part description box, but they remain provenance-backed text evidence rather than automatic truth labels.
- Avoid root-level temporary files. Use `.tmp_validation/` for disposable validation and clean it before finishing.
- Do not include local databases, model weights, user configs, generated artifacts, sessions, or API keys in Git.

Common validation commands:
- Compile check:
  `C:\Users\admin\anaconda3\envs\antsleap\python.exe -m py_compile AntSleap\main.py AntSleap\ui\taxamask_agent_panel.py`
- Focused UI checks:
  `C:\Users\admin\anaconda3\envs\antsleap\python.exe -m unittest tests.test_gui_smoke tests.test_tif_workbench tests.test_ui_polish_scope`
- Broader checks should be chosen based on touched modules. Do not run GPU-heavy training/inference unless the user says the GPU is free.

How to answer the user:
- Default to Chinese.
- Explain first in research workflow terms: what the program does, why it matters, and what operational tradeoff it creates.
- When changing behavior or outputs, say where files appear and what each artifact is for.
- For common TaxaMask tasks, consult this memory and the detailed Ant-Code integration guide before rereading the whole codebase.
