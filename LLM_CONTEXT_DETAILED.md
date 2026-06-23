# TaxaMask Main Branch LLM Context

> **Target audience**: Ant-Code / LLM agents and maintainers working on the TaxaMask main branch.
>
> **Scope**: main / public stable line. This context describes the stable public workflows that are present on main.
>
> **Purpose**: give an agent enough project state to answer questions, inspect bugs, and make safe code changes without rereading the entire repository first.

---

## 1. Product Identity

- Public project name: **TaxaMask**.
- Internal Python package name: `AntSleap`; keep this name for runtime compatibility and historical continuity.
- Origin: ant taxonomy and morphology research.
- Current stable claim: strongest validation is ant morphology, PDF evidence, 2D/STL image annotation, AI draft review, and dataset export.
- Other taxa are possible through profile and template adaptation, but should be validated on small batches before scaling.
- License: AGPLv3.

## 2. Public Main Workflow Routes

Main has these user-facing routes:

1. **Agent Center**
   - Natural-language project inspection, error explanation, profile/backend help, and confirmed code edits.
2. **PDF literature evidence**
   - Screening, figure/caption extraction, literature part-description extraction, candidate review, provenance.
3. **2D morphology annotation**
   - Parent-part and child-part labels on ordinary specimen images.
4. **STL-derived rendered 2D views**
   - Mesh/STL views are rendered outside or through helper routes, then reviewed as 2D images.
5. **VLM and SAM drafts**
   - First-mile proposals and draft masks; always review candidates.
6. **Child Expert Session / Blink route**
   - Child-part localization from parent context using ViT-B Blink, heatmap Blink, or external Blink backend.
7. **External backend contracts**
   - Parent and child backends through public JSON contracts.
8. **Dataset export**
   - Multimodal JSONL, COCO, YOLO, and model profile summaries.

## 3. Agent Center Architecture

Key files:

- `AntSleap/main.py`
- `AntSleap/ui/taxamask_agent_panel.py`
- `AntSleap/core/agent_context_routes.py`
- `AntSleap/config/taxamask_ant_code.config.json`
- `vendor/ant-code/`
- `.lab-agent/skills/taxamask-workflows/SKILL.md`

Startup command shape:

```text
node vendor/ant-code/src/cli/dashboard.js --project <repo_root> --port <free_port> --no-open
```

Recovery launcher:

- `启动AntCode修复面板.bat`
- Opens the browser dashboard without importing the PySide6 GUI.
- Useful after local code edits break GUI startup.

Agent safety rules:

- Do not send API keys, full project JSON, databases, large outputs, or private paths by default.
- Prefer compact context cards and file paths.
- Ask for explicit confirmation before modifying TaxaMask source code.
- Prefer profile/backend changes over source changes when that is enough.
- Explain workflow consequence in plain language for the researcher.

## 4. PDF Literature Evidence

Key files:

- `AntSleap/ui/pdf_processing_widget.py`
- `core/pdf_processor/pdf_classifier.py`
- `core/pdf_processor/pdf_extractor.py`
- `core/pdf_processor/part_description_extractor.py`
- `AntSleap/core/literature_descriptions.py`
- `tools/agentic/screen_pdfs.py`
- `tools/agentic/extract_figures.py`
- `tools/agentic/import_candidates_to_project.py`

Important output concepts:

- screening run index and CSVs
- extraction SQLite DB
- accepted figure files
- needs-review figure files
- raw figure images
- review batches
- `taxon_part_descriptions`
- provenance connecting PDF path, page, caption, nearby text, profile, and extraction status

Safety rule: PDF-derived material is evidence and candidate data. It must not become training truth automatically.

## 5. 2D / STL Morphology

Key files:

- `AntSleap/main.py`
- `AntSleap/core/project.py`
- `AntSleap/core/stl_project.py`
- `AntSleap/core/stl_rendered_views.py`
- `AntSleap/core/stl_review_bridge.py`

Main project data includes:

- image paths and groups
- taxonomy / structures
- labels and masks
- descriptions
- auto boxes and metadata
- VLM targets and drafts
- parent/child context
- Blink trajectories and route experts
- model profile summaries
- export provenance

STL in main means rendered 2D review images. Do not imply direct mesh painting in the stable branch.

Large-project behavior:

- image groups collapse for very large projects
- first image is not loaded automatically in large projects
- Locator/SAM loading is deferred until the user requests annotation/training
- batch prediction and delete operations should save efficiently and not repeatedly reload the first image

## 6. VLM And SAM Draft Semantics

Key files:

- `AntSleap/core/vlm_preannotation.py`
- `tools/agentic/vlm_preannotate_project.py`
- `AntSleap/core/sam_helper.py`
- `AntSleap/main.py`

Current rules:

- VLM first-mile preannotation uses adaptive grid input and returns boxes.
- Boxes are mapped back to the source image.
- SAM can convert point/box prompts into draft masks.
- VLM boxes without polygon masks are review artifacts, not training truth.
- Manual labels and confirmed AI drafts have highest priority.
- Model/external predictions may replace unconfirmed AI drafts.
- VLM reruns may fill empty parts or refresh unconfirmed VLM drafts.
- No automatic route should overwrite manual or confirmed labels.

## 7. Child Expert Session / Blink Route

User-facing wording should be **Child Expert Session / 子部位专家会话**.

Historical code names may still include:

- `blink`
- `BlinkLabWidget`
- `launch_blink_from_workbench`

Key files:

- `AntSleap/ui/blink_lab.py`
- `AntSleap/core/cascade_routes.py`
- `AntSleap/core/blink_expert_manifest.py`
- `AntSleap/core/blink_expert_backends.py`
- `AntSleap/core/blink_trainer.py`
- `AntSleap/core/blink_heatmap_dataset.py`
- `AntSleap/core/blink_heatmap_trainer.py`
- `AntSleap/core/external_blink_backend.py`

Supported child route backends:

- `vit_b_blink`
- `heatmap_blink`
- `external_blink`

Child predictions are candidates. They require researcher review before becoming training labels.

Structure rename and deletion must migrate or clean:

- labels
- descriptions
- auto boxes/meta
- shrink boxes
- trajectories
- VLM targets
- parent ratios
- Blink parent context
- cascade routes

## 8. External Backend Contracts

Public docs:

- `docs/contracts/external_backend_contract_v1.md`
- `docs/contracts/external_blink_backend_contract_v1.md`

Parent backend:

- key file: `AntSleap/core/external_backend.py`
- receives contract JSON
- returns prediction JSON
- predictions are candidates

Child backend:

- key file: `AntSleap/core/external_blink_backend.py`
- predicts a child box from parent context
- result goes back into review flow

Do not commit private command text, local Python paths, API keys, or gateway URLs in backend configs.

## 9. Dataset Export

Key files:

- `tools/agentic/export_multimodal_dataset.py`
- `AntSleap/core/project.py`

Exports may include:

- image files or image references
- label JSON
- COCO annotations
- YOLO labels
- multimodal JSONL
- `model_profile_summary.json`

The model profile summary is important. It records which parent and child model scheme was active when data was exported.

## 10. Public Documentation Roles

- `README.md`: English public landing page and installation entrypoint.
- `README_zh.md`: Chinese public landing page.
- `TaxaMask使用手册.md`: Chinese researcher-facing main-branch user manual.
- `LLM_CONTEXT_DETAILED.md`: public-safe main-branch Agent/LLM context.
- `CHANGELOG_zh.md`: Chinese historical changelog.
- `ANTCODE.md`: stable embedded Agent rules.
- `docs/contracts/`: public model backend contracts.

Do not recreate private design/handoff documents in main unless the user explicitly asks for private local docs. Do not publish local sessions, tasks, runtime settings, model weights, databases, run outputs, or project data.

## 11. Main Branch Validation Hints

Useful checks:

```bash
python -m py_compile AntSleap/main.py
python -m unittest tests.test_agent_context_routes tests.test_stl_review_bridge tests.test_specimen_linkage_pdf_evidence
```

Additional checks depend on installed optional dependencies and desktop GUI availability.

## 12. What Agents Should Not Do On Main

- Do not treat AI drafts as ground truth.
- Do not overwrite manual labels with automatic predictions.
- Do not commit private runtime files, local data, API keys, model weights, or generated outputs.
- Do not push without checking staged file lists.

## 13. Short Mental Model

For main, TaxaMask is:

```text
PDF evidence + 2D/STL morphology annotation + AI draft review + dataset export + Agent-assisted configuration
```
