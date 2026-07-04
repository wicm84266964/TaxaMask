# Taxonomy PDF Harvest

Purpose: collect legally accessible scholarly PDFs and metadata for taxonomy and biodiversity literature. This package is agent-neutral: any AI agent can use it if it can read files and run Python.

Do not use Sci-Hub, LibGen, paywall bypasses, CAPTCHA bypasses, or logged-in website scraping. This package uses open metadata and legally exposed PDF links only.

Downloaded PDFs may still carry article-level license restrictions. Do not redistribute harvested PDFs unless the specific article license permits redistribution.

## Contents

```text
taxonomy-pdf-harvest/
├── AGENT.md
├── SKILL.md
├── scripts/
│   └── oa_pdf_harvester.py
└── references/
    └── query_patterns.md
```

## Preferred Two-Stage Workflow

Use two stages for serious jobs. This avoids losing progress when a download run hits slow hosts.

### 1. Search only

```powershell
python ".\scripts\oa_pdf_harvester.py" `
  --query "Tephritidae sp. nov." `
  --query "Tephritidae spp. nov." `
  --query "Tephritidae gen. nov." `
  --query "Tephritidae new species" `
  --query "Tephritidae new genus" `
  --query "Tephritidae taxonomic revision" `
  --query "Tephritidae taxonomy" `
  --output ".\runs\tephritidae_search" `
  --max-results 2000 `
  --search-only
```

Outputs: `records.csv`, `doi_list.txt`, `summary.json`.

### 2. Download from records.csv

```powershell
python ".\scripts\oa_pdf_harvester.py" `
  --records-input ".\runs\tephritidae_search\records.csv" `
  --output ".\runs\tephritidae_pdf_2020_2026" `
  --year-from 2020 `
  --year-to 2026 `
  --sort recent `
  --candidate-only `
  --resume `
  --timeout 10 `
  --delay 0.1
```

This writes `download_manifest.csv` incrementally, so Ctrl+C, crashes, or host timeouts do not erase progress.

## Safe Test Download

For a bounded test:

```powershell
python ".\scripts\oa_pdf_harvester.py" `
  --records-input ".\runs\tephritidae_search\records.csv" `
  --output ".\runs\tephritidae_100pdf_test" `
  --year-from 2020 `
  --year-to 2026 `
  --sort recent `
  --candidate-only `
  --download-limit 100 `
  --max-pdf-mb 30 `
  --timeout 10 `
  --delay 0.05 `
  --resume
```

Use `--max-records-to-check N` for exploratory runs. Use `--reset-manifest` only when starting a fresh manifest intentionally.

## Optional Unpaywall

Use Unpaywall when candidate URLs are sparse:

```powershell
python ".\scripts\oa_pdf_harvester.py" `
  --records-input ".\runs\tephritidae_search\records.csv" `
  --output ".\runs\tephritidae_unpaywall_fill" `
  --email "name@example.com" `
  --use-unpaywall `
  --unpaywall-missing-only `
  --candidate-only `
  --resume
```

For fast initial tests, skip Unpaywall. It adds one API lookup per DOI when enabled.

## Data Sources

Search uses:

- OpenAlex Works
- Crossref Works
- Europe PMC

PDF download uses PDF URLs exposed by those records, plus optional Unpaywall. The script validates `%PDF` file headers before saving. For public HTML landing pages, it can follow obvious PDF links in the page HTML; it does not log in, submit forms, or bypass access controls.

## Outputs

Each run folder contains:

- `records.csv` - deduplicated metadata table
- `doi_list.txt` - normalized DOI list
- `download_manifest.csv` - status per record, written incrementally
- `summary.json` - run counts
- `pdfs/` - downloaded PDFs

`download_manifest.csv` is the operational truth. Keep it.

## Useful Parameters

- `--search-only`: stop after metadata search.
- `--records-input PATH`: download from an existing `records.csv`.
- `--resume`: append to manifest and skip already downloaded/existing records.
- `--reset-manifest`: start a fresh manifest.
- `--candidate-only`: skip records that have no candidate PDF URL.
- `--download-limit N`: stop after N successful PDFs.
- `--max-records-to-check N`: stop after checking N records.
- `--max-pdf-mb N`: skip oversized PDFs.
- `--sort recent`: process newer records first.
- `--year-from YYYY --year-to YYYY`: filter either search results or `records.csv`.
- `--use-unpaywall --email EMAIL`: add Unpaywall PDF lookup.
- `--unpaywall-missing-only`: only call Unpaywall when no candidate URL exists.

## Query Expansion

Read `references/query_patterns.md` when expanding a taxon. Good defaults:

```text
<taxon> sp. nov.
<taxon> spp. nov.
<taxon> gen. nov.
<taxon> new species
<taxon> new genus
<taxon> taxonomic revision
<taxon> taxonomy
```

Avoid plain `fruit fly` unless Drosophilidae contamination is acceptable. For true fruit flies, prefer `Tephritidae`.

## Failure Handling

- `no_pdf_url`: no configured source exposed a candidate PDF URL.
- `failed`: candidate URLs were tried but did not yield a valid PDF.
- `not_pdf`: the URL returned HTML, a landing page, an error page, or another non-PDF response.
- `http_403`: the server refused direct download; keep the row for later alternate handling.
- `too_large`: skipped because `--max-pdf-mb` was set.
- `exists`: the PDF already exists and was skipped.
- API `429` / rate limit: wait and rerun the same command, preferably with `--email` and smaller batches.

Rerun with `--resume` to continue. Do not delete failed rows; they are useful for later retry or alternate workflows.

## Open Source Hygiene

Keep local agent state, credentials, downloaded PDFs, and generated harvest outputs out of the repository. Commit the skill instructions, script, references, license, and lightweight validation notes only.
