---
name: taxonomy-pdf-harvest
description: Collect legally accessible scholarly PDFs and metadata for taxonomy, biodiversity, new-species, animal-taxonomy, plant-taxonomy, or related literature before TaxaMask PDF evidence screening. Use when the user needs to find, harvest, download, resume, or audit open-access taxonomy PDFs and provenance before PDF screening, figure/caption extraction, candidate review, annotation, or training.
---
# Taxonomy PDF Harvest

Use this agent-neutral skill when an agent needs to collect legally accessible scholarly PDFs and metadata for taxonomy, biodiversity, new-species, animal-taxonomy, or plant-taxonomy literature.

This skill is not Codex-specific. It is intended for any agent or human operator that can read local files, run Python, and manage output folders.

## Agent Entry Point

1. Read `AGENT.md` for the operating workflow and safety boundaries.
2. Read `references/query_patterns.md` when expanding taxon names into practical search queries.
3. Run `scripts/oa_pdf_harvester.py` for search, metadata export, and optional PDF download.

## Capability Boundary

Use only open metadata and legally exposed PDF links. Do not use Sci-Hub, LibGen, paywall bypasses, CAPTCHA bypasses, or logged-in website scraping.

Do not commit harvested PDFs, generated run outputs, private credentials, or local agent state to source control.
