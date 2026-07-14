---
name: taxamask-pdf-evidence
description: Guide TaxaMask PDF screening, figure and caption extraction, literature evidence review, and safe candidate import for a researcher's target taxon.
---
# TaxaMask PDF Evidence

Use this skill for PDF literature work inside TaxaMask. Adapt the workflow to the researcher's taxon instead of assuming the bundled examples are already suitable. PDF outputs are evidence and review candidates, never training truth by themselves.

## Read First

1. Read `ANTCODE.md` for repository and safety rules.
2. Read `LLM_CONTEXT_DETAILED.md`, especially the PDF evidence and Agent Center sections.
3. Use `vendor/ant-code/config/skills/taxonomy-paper-finder/SKILL.md` when papers still need to be discovered or lawfully acquired.
4. Use this skill after PDFs exist, or when the user needs to plan screening, extraction, review, or candidate import.

## Stage-Gated Guide

Handle one stage per reply. Ask at most three questions about the current stage, summarize the confirmed requirements briefly, and move forward only when the current stage is resolved.

0. Literature source: determine whether PDFs already exist or whether the user needs daily monitoring, topic search, selected-paper acquisition, or batch open-access acquisition.
1. Credential and runtime gate: confirm the text LLM provider; confirm a vision-capable provider only when multimodal figure review is requested.
2. Target-taxon screening gate: adapt PDF inclusion, exclusion, uncertainty, and confusing-context rules.
3. Figure and data gate: adapt accepted figure types, rejected figure types, target structures, and expected views.
4. Run and results gate: explain the exact command or GUI action, output locations, review artifacts, and the remaining human decisions.

Do not dump all stages at once. If a stage is already complete, acknowledge it and continue to the next unresolved stage.

## Credential Safety

- Never ask the user to paste an API key into chat.
- Configure keys in the TaxaMask PDF GUI or the local runtime used by the headless command.
- Never write keys into screening, figure-review, or part-description profiles.
- Confirm base URL, model name, and API protocol as well as the key.
- A mock or local-only multimodal pass may route candidates, but it must not be described as trusted acceptance.

## Adapt The Research Criteria

Before editing profiles, confirm:

- Target taxon: family, genus, species group, or other scope, including useful synonyms and OCR variants.
- Screening goal: new species, revision, redescription, new record, identification key, or broader morphology evidence.
- Inclusion and exclusion boundary: which publication types should pass and which should not.
- Common false positives: ecology, molecular phylogeny, conservation, host or symbiont papers, off-target taxa, or field-specific confounders.
- Useful figures: habitus, diagnostic structures, genitalia, plates, keys, tables, maps, or other target-specific evidence.
- Rejected figures: plots, trees, maps-only items, comparison-only plates, off-target organisms, or low-evidence images.
- Structures and views that a taxonomist for this group expects to inspect.

Prefer conservative first-pass thresholds. Preserve uncertain items for human review instead of silently excluding potentially useful taxonomic evidence.

## Profile Rules

Keep three concerns separate when custom profiles are needed:

- Screening profile: decides which PDFs are relevant.
- Figure extraction and review profile: decides which extracted figure candidates are accepted, rejected, or uncertain.
- Part-description profile: structures PDF text into provenance-backed taxon, part, and description records.

Copy the closest template to a new descriptive file. Do not edit a reusable template in place.

Starting points:

- `screener_configs/通用分类学新种筛选_V2模板.json`
- `screener_configs/植物分类学新种筛选_V2模板.json`
- `screener_configs/蚂蚁新种筛选_V2示例.json`
- `multimodal_configs/通用分类学图版提取复核_模板.json`
- `multimodal_configs/植物分类学图版提取复核_模板.json`
- `multimodal_configs/蚂蚁分类学图版宽松复核_示例.json`
- `part_description_configs/通用分类学部位描述抽取_模板.json`
- `part_description_configs/植物分类学部位描述抽取_模板.json`
- `part_description_configs/蚂蚁分类学部位描述抽取_示例.json`

Validate edited JSON before a run. Start with a small sample and review false positives and false negatives before processing a large PDF collection.

## Headless Entry Points

Screen existing PDFs:

```powershell
python tools\agentic\screen_pdfs.py --pdf-source-dir <pdf_dir> --out <run_dir> --config <screening_profile_json>
```

Extract figures, captions, and optional structured literature descriptions:

```powershell
python tools\agentic\extract_figures.py --pdf-source-dir <pdf_dir> --db <output_db> --figure-profile <figure_profile_json> --part-description-profile <part_description_profile_json> --save-images
```

Export and import reviewed candidates:

```powershell
python tools\governance\export_pdf_candidates.py --db <extraction_db> --out <candidate_json>
python tools\agentic\import_candidates_to_project.py --project <project_json> --out <review_project_json> --routing <routing_json> --db <extraction_db> --status needs_review
```

Use `AntSleap/ui/pdf_processing_widget.py` when the user wants the GUI. Use `AntSleap/core/pdf_evidence.py` when explicit PDF, page, caption, specimen, or image provenance records are needed.

## Output Meaning

Explain where each artifact appears and what it is for:

- Screening run directories contain run indexes, queues, results, and evidence used to triage papers.
- The extraction SQLite database stores figure records, captions, surrounding text, structured descriptions, and review state.
- `accepted_figures/` contains import-ready candidates, but they still require researcher review before becoming trusted labels.
- `needs_review_figures/` contains uncertain candidates that should not be promoted automatically.
- `figure_images/` contains raw extracted candidates and is not an acceptance folder.
- Review batches and raw model responses are diagnostic evidence for auditing model decisions.
- Imported images remain 2D review candidates with PDF provenance.

## Safety Boundary

- Never promote PDF candidates directly into training truth.
- Never write PDF outputs into TIF `manual_truth`.
- Never overwrite reviewed annotations during candidate import.
- Preserve source PDF, page number, caption or nearby text, source image, exported image, model and review mode, profile paths, and run index paths.
- Treat model decisions as draft routing until a researcher reviews them.
- Use only open metadata and lawfully exposed PDF links. Do not bypass paywalls, authentication, CAPTCHAs, or access controls.
- Do not run a large batch until the researcher accepts the adapted screening and figure-review criteria.

## Researcher-Facing Explanation

Explain in plain language:

- what the workflow will read;
- where the database, candidate images, indexes, and reports will appear;
- which decisions are made by models;
- which decisions still require human review;
- why PDF evidence is not automatically trusted training data.
