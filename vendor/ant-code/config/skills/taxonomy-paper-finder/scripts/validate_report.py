#!/usr/bin/env python3
# pyright: reportAny=false, reportExplicitAny=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false
"""Validate screening reports against caps and consistency rules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CAP_RECOMMENDED = 5
CAP_SHORTLIST = 8
CAP_DEEP_READS = 3


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_ids(report: dict[str, Any]) -> set[str]:
    return {
        str(item.get("candidate_id", ""))
        for item in report.get("inspected_candidates", [])
        if str(item.get("candidate_id", "")).strip()
    }


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    session = report.get("session")
    if not isinstance(session, dict):
        errors.append("session must be an object")
        return errors

    if not _is_non_empty_string(session.get("session_id")):
        errors.append("session.session_id must be a non-empty string")
    if not _is_non_empty_string(session.get("generated_at")):
        errors.append("session.generated_at must be a non-empty string")
    if not _is_non_empty_string(session.get("user_goal")):
        errors.append("session.user_goal must be a non-empty string")

    review_mode = str(session.get("review_mode", "")).strip()
    valid_review_modes = {
        "interactive-review",
        "multisource-seeded-review",
        "topic-search",
        "batch-harvest",
        "export-only",
    }
    if review_mode not in valid_review_modes:
        errors.append(
            "session.review_mode must be one of interactive-review, multisource-seeded-review, "
            "topic-search, batch-harvest, export-only"
        )

    sources = session.get("sources", [])
    if not isinstance(sources, list) or not sources:
        errors.append("session.sources must be a non-empty list")
    else:
        invalid_sources = [
            src
            for src in sources
            if str(src) not in {"arxiv", "biorxiv", "pubmed", "openalex", "crossref", "europepmc"}
        ]
        if invalid_sources:
            errors.append("session.sources contains invalid source values")

    inspected = report.get("inspected_candidates", [])
    if not isinstance(inspected, list) or not inspected:
        errors.append("inspected_candidates must be a non-empty list")
        return errors

    candidate_ids = _candidate_ids(report)
    if len(candidate_ids) != len(inspected):
        errors.append("inspected_candidates contain missing or duplicate candidate_id values")

    for idx, item in enumerate(inspected):
        if not _is_non_empty_string(item.get("candidate_id")):
            errors.append(f"inspected_candidates[{idx}] candidate_id must be a non-empty string")

        paper = item.get("paper")
        if not isinstance(paper, dict):
            errors.append(f"inspected_candidates[{idx}] missing paper object")
        else:
            if not _is_non_empty_string(paper.get("source")):
                errors.append(f"inspected_candidates[{idx}] paper.source must be non-empty")
            if not _is_non_empty_string(paper.get("title")):
                errors.append(f"inspected_candidates[{idx}] paper.title must be non-empty")
            if not _is_non_empty_string(paper.get("url")):
                errors.append(f"inspected_candidates[{idx}] paper.url must be non-empty")

        inspection_level = str(item.get("inspection_level", "")).strip()
        if inspection_level not in {"metadata", "abstract", "html", "pdf"}:
            errors.append(f"inspected_candidates[{idx}] inspection_level is invalid")

        decision = item.get("decision")
        if not isinstance(decision, dict):
            errors.append(f"inspected_candidates[{idx}] missing decision object")
            continue
        outcome = str(decision.get("outcome", "")).strip()
        reasons = decision.get("reasons", [])
        if outcome not in {"shortlist", "watchlist", "reject", "defer"}:
            errors.append(f"inspected_candidates[{idx}] has invalid decision outcome")
        if not isinstance(reasons, list) or not any(str(x).strip() for x in reasons):
            errors.append(f"inspected_candidates[{idx}] must include at least one non-empty decision reason")

        evidence = item.get("evidence", [])
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"inspected_candidates[{idx}] must include evidence entries")
        else:
            valid_ev = False
            for evidence_item in evidence:
                if not isinstance(evidence_item, dict):
                    continue
                url = str(evidence_item.get("url", "")).strip()
                note = str(evidence_item.get("note", "")).strip()
                if url or note:
                    valid_ev = True
                    break
            if not valid_ev:
                errors.append(f"inspected_candidates[{idx}] evidence requires at least one url or note")

    recs = report.get("recommendations", {})
    if not isinstance(recs, dict):
        errors.append("recommendations must be an object")
        return errors

    primary = recs.get("primary", [])
    shortlist = recs.get("shortlist_order", [])
    deep_reads = recs.get("deep_reads", [])

    if not isinstance(primary, list):
        errors.append("recommendations.primary must be a list")
        primary = []
    if not isinstance(shortlist, list):
        errors.append("recommendations.shortlist_order must be a list")
        shortlist = []
    if not isinstance(deep_reads, list):
        errors.append("recommendations.deep_reads must be a list")
        deep_reads = []

    if len(primary) > CAP_RECOMMENDED:
        errors.append("recommendations.primary exceeds 5-item cap")
    if len(shortlist) > CAP_SHORTLIST:
        errors.append("recommendations.shortlist_order exceeds 8-item cap")
    if len(deep_reads) > CAP_DEEP_READS:
        errors.append("recommendations.deep_reads exceeds 3-item cap")

    shortlist_ids = [str(item).strip() for item in shortlist if str(item).strip()]
    primary_ids = [str(item).strip() for item in primary if str(item).strip()]
    deep_ids = [str(item.get("candidate_id", "")).strip() for item in deep_reads if isinstance(item, dict)]

    if len(set(shortlist_ids)) != len(shortlist_ids):
        errors.append("recommendations.shortlist_order contains duplicates")
    if len(set(primary_ids)) != len(primary_ids):
        errors.append("recommendations.primary contains duplicates")
    if len(set(deep_ids)) != len(deep_ids):
        errors.append("recommendations.deep_reads contains duplicate candidate_id entries")

    shortlist_set = set(shortlist_ids)
    primary_set = set(primary_ids)
    deep_set = set(deep_ids)

    if not primary_set.issubset(shortlist_set):
        errors.append("recommendations.primary must be subset of shortlist_order")
    if not shortlist_set.issubset(candidate_ids):
        errors.append("recommendations.shortlist_order references unknown candidate_id")
    if not deep_set.issubset(shortlist_set):
        errors.append("recommendations.deep_reads must be subset of shortlist_order")

    outcomes_by_id: dict[str, str] = {}
    for item in inspected:
        cid = str(item.get("candidate_id", "")).strip()
        decision = item.get("decision", {}) if isinstance(item.get("decision"), dict) else {}
        outcomes_by_id[cid] = str(decision.get("outcome", "")).strip()
    for cid in shortlist_set:
        if outcomes_by_id.get(cid) != "shortlist":
            errors.append(f"candidate '{cid}' is in shortlist_order but decision outcome is not shortlist")

    digest_ready = report.get("digest_ready", {})
    if not isinstance(digest_ready, dict):
        errors.append("digest_ready must be an object")
        return errors

    cards = digest_ready.get("shortlist_cards", [])
    deep_briefs = digest_ready.get("deep_read_briefs", [])
    details = digest_ready.get("detailed_analysis", [])
    counts = digest_ready.get("counts", {})

    if not isinstance(cards, list):
        errors.append("digest_ready.shortlist_cards must be a list")
        cards = []
    if not isinstance(deep_briefs, list):
        errors.append("digest_ready.deep_read_briefs must be a list")
        deep_briefs = []
    if not isinstance(details, list):
        errors.append("digest_ready.detailed_analysis must be a list")
        details = []

    card_ids = {str(item.get("candidate_id", "")).strip() for item in cards if isinstance(item, dict)}
    deep_brief_ids = {str(item.get("candidate_id", "")).strip() for item in deep_briefs if isinstance(item, dict)}
    detail_ids = {str(item.get("candidate_id", "")).strip() for item in details if isinstance(item, dict)}

    if card_ids != shortlist_set:
        errors.append("digest_ready.shortlist_cards candidate IDs must match recommendations.shortlist_order")
    if deep_brief_ids != deep_set:
        errors.append("digest_ready.deep_read_briefs candidate IDs must match recommendations.deep_reads")
    if not detail_ids.issubset(shortlist_set):
        errors.append("digest_ready.detailed_analysis candidate IDs must be shortlist members")

    if not isinstance(counts, dict):
        errors.append("digest_ready.counts must be an object")
    else:
        if int(counts.get("recommended_total", -1)) != len(primary_ids):
            errors.append("digest_ready.counts.recommended_total inconsistent with recommendations.primary")
        if int(counts.get("selected_total", -1)) != len(shortlist_ids):
            errors.append("digest_ready.counts.selected_total inconsistent with recommendations.shortlist_order")
        if int(counts.get("deep_read_total", -1)) != len(deep_ids):
            errors.append("digest_ready.counts.deep_read_total inconsistent with recommendations.deep_reads")
        if int(counts.get("inspected_total", -1)) != len(inspected):
            errors.append("digest_ready.counts.inspected_total inconsistent with inspected_candidates")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, help="Screening report JSON path")
    args = parser.parse_args()

    report_path = Path(args.report).resolve()
    report = read_json(report_path)
    errors = validate_report(report)
    if errors:
        for line in errors:
            print(f"ERROR: {line}")
        return 1
    print("OK: screening report is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
