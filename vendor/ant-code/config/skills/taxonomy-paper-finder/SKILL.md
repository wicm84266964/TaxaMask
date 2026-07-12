---
name: taxonomy-paper-finder
description: Discover, review, recommend, and legally acquire taxonomy papers. Use for daily literature monitoring, topic searches, evidence-based shortlists, deep-read selection, or resumable open-access PDF harvests.
allowed-tools: web_search, web_fetch, powershell, read_file, document_intake, mcp_list, mcp_call
---

# Taxonomy Paper Finder

## Mission

Provide one literature workflow for taxonomy research:

1. discover candidates
2. inspect evidence
3. recommend only strong papers
4. optionally retrieve legally accessible PDFs
5. preserve metadata, decisions, and download provenance

Agent judgment owns the shortlist. Scripts fetch, normalize, validate, bridge,
download, and export; they do not make the final editorial decision.

## Modes

- `daily-review`: recent arXiv, bioRxiv, and PubMed monitoring with an editable shortlist and up to three deep reads.
- `topic-search`: focused review for a taxon, method, region, journal, or research question.
- `shortlist-download`: convert reviewed primary, shortlist, or deep-read papers into resumable open-PDF harvest inputs.
- `batch-harvest`: search OpenAlex, Crossref, and Europe PMC and optionally download legally exposed PDFs at scale.
- `export-only`: validate an existing screening report and export JSON, Markdown, and HTML digests.

## Default Daily Workflow

1. Run `scripts/fetch_candidates.py` to create normalized candidate records.
2. Inspect candidate landing pages, abstracts, HTML, and only the most relevant PDFs.
3. Record evidence and decisions in a screening report matching `references/schemas/screening-report.schema.json`.
4. Keep about five primary recommendations, at most eight shortlist papers, and at most three deep reads. Do not pad weak results.
5. Run `scripts/validate_report.py`, then `scripts/export_digest.py`.
6. Ask before downloading. If approved, run `scripts/bridge_to_harvest.py` with `deep-reads` by default, then pass its `records.csv` to `scripts/oa_pdf_harvester.py`.

```powershell
python scripts\fetch_candidates.py
python scripts\validate_report.py --report "<screening-report.json>"
python scripts\export_digest.py --report "<screening-report.json>"
python scripts\bridge_to_harvest.py `
  --report "<screening-report.json>" `
  --output "runs\selected-papers" `
  --selection deep-reads
python scripts\oa_pdf_harvester.py `
  --records-input "runs\selected-papers\records.csv" `
  --output "runs\selected-papers" `
  --candidate-only --resume
```

## Batch Harvest Workflow

Use `references/query_patterns.md` to expand taxon names, run metadata search first,
review `records.csv`, then start a bounded or resumable download.

```powershell
python scripts\oa_pdf_harvester.py `
  --query "Tephritidae sp. nov." `
  --query "Tephritidae taxonomic revision" `
  --output "runs\tephritidae" `
  --max-results 2000 `
  --search-only
```

## Safety Boundary

- Use open metadata and legally exposed PDF links only.
- Never use Sci-Hub, LibGen, paywall bypasses, CAPTCHA bypasses, or logged-in scraping.
- Default daily review is metadata-first and does not automatically download all candidates.
- Do not commit credentials, runtime state, screening outputs, manifests, or PDFs.
- Downloaded PDFs may have article-level redistribution restrictions; check licenses before sharing.
