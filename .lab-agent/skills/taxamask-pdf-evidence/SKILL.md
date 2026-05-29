---
name: taxamask-pdf-evidence
description: TaxaMask PDF evidence workflow skill. Use when the task involves adapting taxonomy PDF screening conditions for a user's target taxon, configuring PDF screening profiles, configuring figure/caption extraction and multimodal review profiles, running PDF literature screening, extracting figure/caption evidence, creating PDF evidence indexes, handling PDF-derived candidate images, importing reviewed PDF candidates into a TaxaMask 2D project, explaining PDF processing failures, or deciding whether PDF outputs can be used for annotation or training.
---
# TaxaMask PDF Evidence

Use this skill for PDF literature work inside TaxaMask. The hard part is not starting the command; it is adapting the screening and figure-extraction conditions to the researcher's own taxon. Treat PDF outputs as evidence and review candidates, not training truth.

## First Route

1. Read `ANTCODE.md` and `.lab-agent/memory.md` first if they are not already active.
2. Treat PDF work as `PDF evidence`, not as a visual annotation workbench.
3. Run the Stage-Gated Guide. Do not dump the whole PDF workflow in one answer.
4. Use `AntSleap/ui/pdf_processing_widget.py` only when the user needs the GUI evidence tools. Prefer Agent-led profile adaptation and headless commands for repeatable runs.
5. Use these headless entrypoints for Agent-run workflows:
   - `tools/agentic/screen_pdfs.py` for literature screening.
   - `tools/agentic/extract_figures.py` for figure/caption extraction and review.
   - `tools/governance/export_pdf_candidates.py` and `AntSleap/core/governance/candidate_bridge.py` for candidate artifacts from extraction DBs.
   - `tools/agentic/import_candidates_to_project.py` only after candidate review/routing.
6. Use `AntSleap/core/pdf_evidence.py` when explicit PDF/page/caption/specimen provenance records are needed.

## Stage-Gated Guide

Guide the researcher one stage at a time. In each answer, handle only the current stage, ask at most three questions, and state the next stage in one sentence. Prefer requirement-confirmation interactions: offer concise choices or short fields the researcher can confirm, instead of writing a long explanation. Do not include a full command list, full profile checklist, and all output artifacts until the user reaches that stage.

1. Credential And Runtime Gate: configure text LLM key/model first; configure multimodal model only if image review will be used.
2. Target-Taxon Adaptation Gate: adapt PDF screening conditions to the user's taxon.
3. Figure/Data Processing Gate: adapt figure extraction and multimodal review conditions to the user's taxon.
4. Run And Results Gate: then explain exact commands/GUI actions, output paths, and review/import artifacts.

If a stage is already complete, briefly acknowledge it and move to the next stage. If the user asks for an overview, give a short four-step outline, then return to the current stage.

## Requirement Confirmation Pattern

Use this interaction style for PDF guidance:

- Ask only the information needed for the current stage.
- Prefer a compact confirmation block with choices, for example: `Key/model configured? yes/no/need help`, `Multimodal review? use vision model / local triage only / decide later`.
- For target-taxon adaptation, ask for the target group and screening goal first; ask detailed include/exclude refinements only after that answer.
- For figure/data adaptation, ask accepted figure types and rejected figure types first; ask detailed structure/view terms only after that answer.
- After the user answers, restate the chosen requirements in 2-4 short bullets and ask whether to proceed to the next stage.

## Credential And Runtime Gate

Do this before profile adaptation or commands. Explain that without a text LLM key/model, PDF screening cannot run normally. Keep the response short.

- Check whether the text LLM API key is configured. Never ask the user to paste a secret key into chat; ask them to enter it in the TaxaMask PDF GUI or configure it in the local runtime used for headless commands.
- Check text LLM base URL, model name, and API protocol. If these are missing or obviously placeholders, guide the user to configure them first.
- If multimodal validation is enabled or figure review needs image understanding, check multimodal key/base URL/model. If it reuses the text provider, confirm the text provider is vision-capable; otherwise ask for separate multimodal settings.
- If the user wants only local/mock figure routing, explain that it is useful for candidate triage but not trusted acceptance.
- After credentials are ready, move to target-taxon and profile adaptation in the next turn. Do not explain the full workflow yet. Do not let a valid key/model substitute for wrong biological criteria.

## Target-Taxon Adaptation Gate

Do not assume the user studies ants. Do not assume the default profile is correct. Start this stage only after credentials are ready or the user explicitly asks to plan profiles first. Ask a short set of questions before commands:

- Research target: target group, family, genus, or species scope; include common names and scientific names if useful.
- Screening goal: new species only, new genus, new combination, redescription, new record, revision, identification key, or broader taxonomy literature.
- Include/exclude boundary: which paper types should pass, and which should be excluded even if they mention the target taxon.
- Confusing organisms or contexts: host/parasite/symbiont, ecology, molecular phylogeny, conservation, medical/agricultural papers, or other taxa that commonly create false positives.
- Do not cover figure/data processing here unless the user already provided screening answers; that belongs to the next stage.

If the user already supplied these, summarize the inferred screening-profile changes and ask for confirmation only when the consequences are ambiguous.

## Figure/Data Processing Gate

Start this stage only after the PDF screening criteria are clear. Ask what figures and evidence should survive data processing:

- Accepted figures: whole organism, habitus, diagnostic structure, genitalia, plates, maps, keys, tables, or other target-specific figure types.
- Rejected figures: phylogeny, ecology, experimental plots, comparison-only plates, non-target taxa, maps only, tables only, or low-evidence images.
- Target structures/views: the structures or views a taxonomist for this group expects to inspect.

Summarize the needed figure-review profile changes, then ask whether to create/edit the profile. Do not jump to extraction commands until this is accepted.

## Profile Adaptation

Create or select three separate profiles when a non-default workflow is needed:

- Screening profile: controls which PDFs pass the literature screening stage.
- Figure extraction/review profile: controls which extracted figure/caption candidates are accepted, rejected, or marked uncertain.
- Part-description profile: controls how pure PDF text is structured into `taxon -> part -> description` records.

Do not edit reusable templates in place. Copy a template to a new descriptive JSON file, then edit the copy. Never store API keys in profile JSON.

Template starting points:

- Generic screening: `screener_configs/通用分类学新种筛选_V2模板.json`
- Plant screening: `screener_configs/植物分类学新种筛选_V2模板.json`
- Ant screening example: `screener_configs/蚂蚁新种筛选_V2示例.json`
- Generic figure review: `multimodal_configs/通用分类学图版提取复核_模板.json`
- Plant figure review: `multimodal_configs/植物分类学图版提取复核_模板.json`
- Ant figure review example: `multimodal_configs/蚂蚁分类学图版宽松复核_示例.json`
- Generic part-description extraction: `part_description_configs/通用分类学部位描述抽取_模板.json`
- Plant part-description extraction: `part_description_configs/植物分类学部位描述抽取_模板.json`
- Ant part-description extraction example: `part_description_configs/蚂蚁分类学部位描述抽取_示例.json`

Current ant default: the ant figure review example is intentionally broad. It accepts single ant species/taxon morphology figures such as habitus, useful body views, head or local diagnostic structures, and same-taxon plate combinations. It rejects multi-species or multi-taxon comparison figures. This is a profile adaptation pattern similar to what other taxa should do with their own copied templates, not a hard-coded algorithm fork.

### Screening Profile Checklist

When adapting the screening profile:

- Replace `TARGET_GROUP`, `TARGET_FAMILY`, `TARGET_GENUS`, and any placeholder text in prompts and keyword lists.
- Fill `taxonomic_group_keywords` with target taxon names, synonyms, major higher taxa, common names, and likely OCR variants.
- Keep or edit `required_keywords` according to the goal: `sp. nov.`, `gen. nov.`, `new combination`, `redescription`, `new record`, `revision`, etc.
- Tune `supportive_keywords` for taxonomy evidence: diagnosis, description, morphology, type material, holotype, paratype, material examined, key, distribution.
- Tune `strong_exclude_keywords`, `weak_exclude_keywords`, and `biological_exclude_keywords` for known false positives in that field.
- Rewrite `llm_system_prompt`, `llm_prompt_template`, and `llm_batch_prompt_template` so include/exclude/uncertain are defined for the user's target taxon, not for ants or a generic organism.
- Keep JSON-only LLM output requirements and the expected `include|exclude|uncertain` decision schema.
- Use conservative thresholds at first. For exploratory screening, prefer reviewable uncertainty over silently excluding useful taxonomy papers.

### Figure Extraction And Review Profile Checklist

When adapting the figure/data-processing profile:

- Set `target_taxon.display_name` and `target_taxon.scientific_scope`.
- Edit `taxonomy_terms` to include target taxon names, morphology terms, type-material terms, and field-specific section terms.
- Edit `rejection_terms` for false figure types: maps only, trees, tables, experimental plots, ecological photos, comparison-only plates, off-target organisms.
- Adjust `extraction_rules.caption_patterns` only if the literature uses unusual figure labels.
- Adjust `section_hint_map`, `core_section_hints`, and `extended_section_hints` if the field uses special section names.
- Review `species_name_patterns` if names are not standard binomials or if OCR commonly breaks names.
- Rewrite `review_rules.acceptance_goal`, `accept_if`, and `reject_if` for the user's desired candidate figures.
- Replace ant-specific view requirements. Set `review_rules.view_schema.required_or_expected_views`, `acceptance_mode`, and `view_terms` to structures/views that matter for the target taxon.
- Rewrite `review_rules.prompt.system_prompt` and `user_instructions` so the multimodal reviewer knows the target group and accepted figure types.
- Treat mock/default multimodal review as tentative. It can route candidates to review, not accept evidence automatically.

## Common Workflows

### 1. Adapt Profiles First

Use this route for most researchers, but apply it stage by stage. First finish credentials, then screening criteria, then figure/data criteria. Copy the closest screening and figure-review templates only after the relevant stage is accepted.

Suggested output paths:

- Screening profile: `screener_configs/<target>_pdf_screening_v2.json`
- Figure profile: `multimodal_configs/<target>_figure_review.json`
- Part-description profile: `part_description_configs/<target>_part_descriptions.json`

Validate that the edited JSON is parseable before running. If possible, run a small sample folder first and inspect false positives/false negatives with the user. If credentials are still missing, stop here and guide key/model setup instead of pretending the run can proceed.

### 2. Screen PDFs

Use when the user wants to find target papers before figure extraction.

```powershell
python tools\agentic\screen_pdfs.py --pdf-source-dir <pdf_dir> --out <run_dir> --config <screening_profile_json>
```

Outputs include `run_index.json`, `master_queue.csv`, `master_results.csv`, debug/evidence artifacts, copied/sorted PDFs when configured, and a runtime config snapshot. Explain that screening results are a triage layer, not a final taxonomic decision.

### 3. Extract Figures And Captions

Use when the user wants figure images, captions, surrounding evidence text, taxon part-description text evidence, and a SQLite DB.

```powershell
python tools\agentic\extract_figures.py --pdf-source-dir <pdf_dir> --db <output_db> --figure-profile <figure_profile_json> --part-description-profile <part_description_profile_json> --save-images --text-api-key <configured_outside_chat> --text-base-url <base_url> --text-model <text_model>
```

Add `--disable-multimodal-validation` only when the user accepts local/mock review. Add `--disable-part-description-extraction` when the user only wants figure/caption evidence and does not want the pure-text Text LLM pass. Headless part-description extraction runs as real LLM work only when `--text-api-key`, `--text-base-url`, and `--text-model` are provided; otherwise it records `skipped` and figure extraction continues. Outputs include the extraction SQLite DB, saved figure images when requested, and `figure_extraction_run_index.json`.

Current extraction DB tables include:
- `figure_records`: figure candidates and review status.
- `figure_evidence`: caption/local/species-core/species-extended original evidence.
- `pdf_text_blocks`: original PDF text blocks labeled by the Text LLM, with file name, file path, file hash, page number, and block_ref.
- `taxon_part_descriptions`: the main `taxon -> part -> description` output, with source pages/block refs and source block payloads.
- `part_extraction_runs`: real/mock/skipped/failed status for the pure-text structuring pass, including the part-description profile used.

Explain that part descriptions are structured literature evidence, not visual labels and not training truth.

### 4. Export And Import Candidates

Use export/routing only after the extraction DB exists and candidate status is reviewable.

```powershell
python tools\governance\export_pdf_candidates.py --db <extraction_db> --out <candidate_json>
python tools\agentic\import_candidates_to_project.py --project <project_json> --out <review_project_json> --routing <routing_json> --db <extraction_db> --status needs_review
```

Candidate import should create reviewable 2D project entries with PDF provenance. It must not create TIF labels, overwrite annotations, or create training truth.

## Safety Rules

- Never promote PDF candidates directly into training truth.
- Never write PDF outputs into TIF `manual_truth`.
- Import PDF-derived images into 2D projects only as reviewable candidates, usually with status `needs_review`.
- Preserve source PDF, page number, caption/nearby text, candidate image path, model/review mode, run index paths, profile paths, and candidate/routing status.
- Warn when multimodal review used mock/default fallback; such outputs belong in review, not accepted evidence.
- Do not store API keys in profiles or committed files.
- Do not run large PDF batches until the user accepts the adapted screening and figure-review criteria.
- Do not expose, echo, commit, or log raw API keys.

## Explanation Pattern

When answering the researcher, explain in Chinese by default. Keep each turn focused on the current stage:

- Stage 1: explain only key/model readiness and where to configure it.
- Stage 2: explain only PDF screening conditions and what profile changes they imply.
- Stage 3: explain only figure/data processing conditions and what figure-review profile changes they imply.
- Stage 4: explain exact run steps, where outputs appear, what artifacts mean, and what remains manual.
- Always keep the safety boundary visible: PDF evidence and candidates do not become training truth or TIF `manual_truth` automatically.
