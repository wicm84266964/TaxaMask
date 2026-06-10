# TaxaMask Public Agent Context

This file is the public-safe handoff context for the TaxaMask embedded Agent. It describes the current open-source v1.0 scope and intentionally excludes private machine paths, local logs, private gateways, and historical development notes.

## Product Scope

- Public project name: TaxaMask.
- Internal Python package name: `AntSleap`; keep it for runtime compatibility.
- Primary validated domain: ant taxonomy and morphology.
- Adaptation target: other taxa through profiles and templates, after small-batch validation.
- License: AGPLv3.

Public workflow routes:

- Agent Center / Ant-Code integration.
- PDF literature processing.
- 2D morphology and STL-derived rendered 2D views.
- VLM first-mile drafts and SAM-assisted annotation.
- Parent-part and child-part annotation.
- Blink / heatmap Blink / external Blink child-part experts.
- Parent and child external backend contracts.
- Multimodal, COCO, and YOLO-style dataset export.

## Agent Center

TaxaMask embeds the vendored Ant-Code dashboard from `vendor/ant-code` through `AntSleap/ui/taxamask_agent_panel.py`.

Startup command shape:

```text
node vendor/ant-code/src/cli/dashboard.js --project <repo_root> --port <free_port> --no-open
```

TaxaMask passes `AntSleap/config/taxamask_ant_code.config.json` as the Agent config. That config adds the TaxaMask source-guard hook. The public TaxaMask release does not add external repository skills; the embedded Agent only keeps Ant-Code's bundled generic skills.

Recovery launcher:

- `启动AntCode修复面板.bat`
- Starts the browser dashboard without importing PySide6 or `AntSleap/main.py`.
- Useful when a local source edit prevents the GUI from starting.

## PDF Literature Processing

Main files:

- `AntSleap/ui/pdf_processing_widget.py`
- `core/pdf_processor/pdf_classifier.py`
- `core/pdf_processor/pdf_extractor.py`
- `core/pdf_processor/part_description_extractor.py`
- `AntSleap/core/literature_descriptions.py`
- `tools/agentic/screen_pdfs.py`
- `tools/agentic/extract_figures.py`
- `tools/agentic/import_candidates_to_project.py`

Outputs are evidence and review candidates:

- screening run indexes and CSVs
- extraction SQLite DB
- `accepted_figures/`
- `needs_review_figures/`
- `figure_images/`
- `review_batches/`
- `taxon_part_descriptions`

Safety rule: PDF-derived images and text descriptions must not become training truth automatically.

## 2D/STL Morphology

Main files:

- `AntSleap/main.py`
- `AntSleap/core/project.py`
- `AntSleap/core/stl_project.py`
- `AntSleap/core/stl_rendered_views.py`
- `AntSleap/core/stl_review_bridge.py`

STL support in this public release means rendered 2D review images with provenance. It does not expose a direct mesh-painting workbench.

Large projects should open lightly:

- image groups collapsed
- no automatic first-image load for very large projects
- Locator/SAM loading deferred until annotation or training needs it

## VLM And SAM Drafts

Main files:

- `AntSleap/core/vlm_preannotation.py`
- `tools/agentic/vlm_preannotate_project.py`
- `AntSleap/main.py`

Behavior:

- VLM uses adaptive grid input and returns boxes.
- Boxes are mapped back to the source image.
- Optional SAM draft polygons may be generated.
- Drafts remain reviewable AI labels until accepted.
- Reruns may replace unconfirmed AI drafts but should preserve manual and confirmed labels.

## Blink And Child-Part Experts

Main files:

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

Child-part predictions are candidates and need researcher review.

## External Backend Contracts

Public docs:

- `docs/contracts/external_backend_contract_v1.md`
- `docs/contracts/external_blink_backend_contract_v1.md`

Parent backend:

- `AntSleap/core/external_backend.py`
- Receives a contract JSON and returns prediction JSON.

Child backend:

- `AntSleap/core/external_blink_backend.py`
- Predicts a child box from an existing parent context.

Do not store private command text, API keys, or local paths in committed backend configs.

## Dataset Export

Main files:

- `tools/agentic/export_multimodal_dataset.py`
- `AntSleap/core/project.py`

Exports may include:

- image files
- labels
- COCO annotations
- YOLO labels
- multimodal JSONL
- `model_profile_summary.json`

The model profile summary is important for audit: it records the active parent and child model scheme around training and prediction.

## Public Documentation Roles

- `README.md`: English public landing page.
- `README_zh.md`: Chinese public landing page.
- `TaxaMask使用手册.md`: Chinese public user manual.
- `LLM_CONTEXT_DETAILED.md`: public-safe current Agent context.
- `ANTCODE.md`: stable embedded Agent rules.
- `vendor/ant-code/config/skills/`: bundled generic Ant-Code skills.

Do not reintroduce private changelogs, local handoff logs, private gateway configs, user sessions, model weights, databases, or run outputs into the public branch.

## Validation

Useful public checks:

```bash
python -m py_compile AntSleap/main.py
python -m unittest tests.test_agent_context_routes tests.test_stl_review_bridge tests.test_specimen_linkage_pdf_evidence
```

GUI smoke tests may require a working PySide6/Qt desktop environment.
