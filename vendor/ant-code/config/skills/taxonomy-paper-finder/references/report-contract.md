# Screening report contract

`screening-report.schema.json` is the canonical artifact between browser review and digest export.

## Required sections

1. `session` metadata
2. `inspected_candidates` with inspection level, decision, and evidence
3. `recommendations` with primary (<=5), shortlist order (<=8), deep reads (<=3)
4. `digest_ready` narrative payload used directly by exporter

## Integrity expectations

- Every inspected candidate has a decision.
- Every inspected candidate includes evidence (`url` and/or `note`).
- `shortlist_order` and `deep_reads` candidate IDs must exist in inspected candidates.
- `digest_ready` counts and sections stay consistent with recommendations.
