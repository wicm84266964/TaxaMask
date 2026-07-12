# Taxonomy Paper Finder Operator Guide

Taxonomy Paper Finder combines literature discovery, evidence-based recommendation,
digest export, and lawful open-access PDF acquisition in one Skill.

## Capability Map

| Need | Entry point | Main output |
|---|---|---|
| Daily recent-paper monitoring | `scripts/fetch_candidates.py` | `runtime/candidates/*.paper-records.json` |
| Human/agent review | browser + screening schema | screening report JSON |
| Report validation | `scripts/validate_report.py` | validation result |
| Daily digest export | `scripts/export_digest.py` | JSON, Markdown, HTML |
| Selected-paper handoff | `scripts/bridge_to_harvest.py` | `records.csv`, `doi_list.txt` |
| Topic metadata search | `scripts/oa_pdf_harvester.py --search-only` | `records.csv`, `doi_list.txt`, `summary.json` |
| Open PDF acquisition | `scripts/oa_pdf_harvester.py --records-input` | PDFs and `download_manifest.csv` |

## Review Policy

- Agent judgment, not keyword score, owns shortlist formation.
- Ideal primary recommendations: about 5.
- Shortlist hard cap: 8.
- Deep-read hard cap: 3.
- If only two papers are strong, return two.
- Escalate from metadata to abstract, HTML, and PDF only as needed.
- Preserve evidence URLs and explain why each paper stayed or dropped.

## Selected PDF Handoff

The bridge supports `deep-reads`, `primary`, and `shortlist`. It defaults to
`deep-reads` to avoid unnecessary downloads.

```powershell
python scripts\bridge_to_harvest.py `
  --report "<screening-report.json>" `
  --output "runs\review-20260712" `
  --selection deep-reads
```

The generated `records.csv` uses the same fields consumed by the harvester:
source, source ID, DOI, title, year, journal, authors, landing URL, and PDF URLs.

## Resumable Download

```powershell
python scripts\oa_pdf_harvester.py `
  --records-input "runs\review-20260712\records.csv" `
  --output "runs\review-20260712" `
  --candidate-only `
  --resume `
  --timeout 10
```

`download_manifest.csv` is the operational truth. Keep failed and unavailable
rows for later retry; do not silently discard them.

## Topic Batch Search

Search sources are OpenAlex, Crossref, and Europe PMC. Optional Unpaywall lookup
can fill DOI records with missing open-PDF URLs.

```powershell
python scripts\oa_pdf_harvester.py `
  --query "<taxon> sp. nov." `
  --query "<taxon> new species" `
  --query "<taxon> taxonomic revision" `
  --output "runs\<taxon>" `
  --search-only
```

Use `--download-limit`, `--max-records-to-check`, and `--max-pdf-mb` for bounded
tests. Use `--resume` for long runs. Use `--reset-manifest` only for an intentional
fresh run.

## Legal And Data Boundary

- No Sci-Hub, LibGen, paywall or CAPTCHA bypass, or logged-in scraping.
- Respect API terms, robots policies, and article-level licenses.
- Do not publish downloaded PDFs unless their licenses permit redistribution.
- Keep `.lab-agent`, credentials, runtime folders, manifests, digests, and PDFs
  out of source control.
