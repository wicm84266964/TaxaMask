# Screening report template

## Session

- session_id:
- generated_at:
- review_mode: interactive
- user_goal:
- sources: [arxiv, biorxiv, pubmed]

## Inspected candidates

For each candidate:

- candidate_id:
- paper: source / source_id / title / url
- inspection_level: metadata|abstract|html|pdf
- decision: outcome + reasons + confidence
- evidence: url(s) and/or note(s)

## Recommendations

- primary (<=5): []
- shortlist_order (<=8): []
- deep_reads (<=3): [{ candidate_id, why_read, focus_questions }]

## Digest ready

- digest_date:
- label:
- overview:
- selection_rationale:
- shortlist_cards: [{ candidate_id, headline, why_it_matters }]
- deep_read_briefs: [{ candidate_id, narrative }]
- detailed_analysis: [{ candidate_id, analysis }]
- next_dialogue_prompts: []
- counts: { inspected_total, recommended_total, selected_total, deep_read_total }
