---
name: taxamask-pdf-evidence
description: TaxaMask PDF evidence workflow skill. Use when the task involves PDF literature screening, figure/caption extraction, PDF evidence indexes, PDF-derived candidate images, importing PDF candidates into a TaxaMask 2D project, explaining PDF processing failures, Poppler/PyMuPDF/OCR/API issues, or deciding whether PDF outputs can be used for annotation or training.
---
# TaxaMask PDF Evidence

Use this skill for PDF literature work inside TaxaMask. Keep the role of PDF outputs clear: PDFs create evidence and review candidates, not training truth.

## First Route

1. Read `ANTCODE.md` and `.lab-agent/memory.md` first if they are not already active.
2. Treat PDF work as `PDF evidence`, not as a visual annotation workbench.
3. Use `AntSleap/ui/pdf_processing_widget.py` only when the user needs the GUI evidence tools.
4. Use headless commands for Agent-run workflows:
   - `tools/agentic/screen_pdfs.py` for literature screening.
   - `tools/agentic/extract_figures.py` for figure/caption extraction.
   - `tools/agentic/import_candidates_to_project.py` for reviewed candidate import into a 2D project.
   - `tools/governance/export_pdf_candidates.py` and `AntSleap/core/governance/candidate_bridge.py` for candidate artifacts from extraction DBs.
5. Use `AntSleap/core/pdf_evidence.py` for evidence index records when a task needs explicit PDF/page/caption/specimen provenance.

## Safety Rules

- Never promote PDF candidates directly into training truth.
- Never write PDF outputs into TIF `manual_truth`.
- Import PDF-derived images into 2D projects only as reviewable candidates, usually with status `needs_review`.
- Preserve source PDF, page number, caption/nearby text, candidate image path, model/review mode, and run index paths.
- Warn when multimodal review used mock/default fallback; such outputs belong in review, not accepted evidence.
- Do not store API keys in profiles or committed files.

## Common Workflows

### Screen PDFs

Use when the user wants to find target papers before figure extraction.

```powershell
python tools\agentic\screen_pdfs.py --pdf-source-dir <pdf_dir> --out <run_dir> --config <profile_json>
```

Outputs include `run_index.json` and classifier artifacts under the chosen run directory.

### Extract Figures And Captions

Use when the user wants figure images, captions, and evidence in a SQLite DB.

```powershell
python tools\agentic\extract_figures.py --pdf-source-dir <pdf_dir> --db <output_db> --figure-profile <profile_json> --save-images
```

Outputs include a figure extraction DB, saved figure images when requested, and `figure_extraction_run_index.json`.

### Import Candidates Into A 2D Project

Use only after candidate routing or user review has identified images worth bringing into the 2D workflow.

```powershell
python tools\agentic\import_candidates_to_project.py --project <project_json> --out <review_project_json> --routing <routing_json> --db <extraction_db> --status needs_review
```

This should create reviewable 2D project entries with PDF provenance. It must not create TIF labels or training truth.

## Explanation Pattern

When answering the researcher, explain:

- What the PDF workflow will read: source PDFs, profile, API/runtime settings.
- What it will produce: run index, DB, candidate images, evidence index, reports.
- What remains manual: candidate review, specimen matching, and any promotion into training data.
- What is unsafe to automate: training truth, TIF `manual_truth`, or accepted taxonomic evidence without review.
