#!/usr/bin/env python3
"""Convert reviewed paper selections into Taxonomy Paper Finder harvest inputs."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


RECORD_FIELDS = ["source", "source_id", "doi", "title", "year", "journal", "authors", "landing_url", "pdf_urls"]
SELECTIONS = {"deep-reads", "primary", "shortlist"}


def normalize_doi(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text, flags=re.I)
    text = re.sub(r"^doi:\s*", "", text, flags=re.I)
    return text.lower()


def selected_candidate_ids(report: dict[str, Any], selection: str) -> list[str]:
    if selection not in SELECTIONS:
        raise ValueError(f"unsupported selection: {selection}")
    recommendations = report.get("recommendations", {})
    if selection == "deep-reads":
        values = [item.get("candidate_id", "") for item in recommendations.get("deep_reads", [])]
    elif selection == "primary":
        values = recommendations.get("primary", [])
    else:
        values = recommendations.get("shortlist_order", [])
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate_id = str(value).strip()
        if candidate_id and candidate_id not in seen:
            result.append(candidate_id)
            seen.add(candidate_id)
    return result


def _as_authors(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _as_pdf_urls(paper: dict[str, Any]) -> str:
    values = paper.get("pdf_urls", [])
    if isinstance(values, str):
        urls = [item.strip() for item in values.split("|") if item.strip()]
    elif isinstance(values, list):
        urls = [str(item).strip() for item in values if str(item).strip()]
    else:
        urls = []
    source_links = paper.get("source_links", {}) if isinstance(paper.get("source_links"), dict) else {}
    pdf_url = str(source_links.get("pdf_url", "")).strip()
    if pdf_url and pdf_url not in urls:
        urls.append(pdf_url)
    return "|".join(urls)


def paper_to_harvest_row(paper: dict[str, Any]) -> dict[str, str]:
    source_links = paper.get("source_links", {}) if isinstance(paper.get("source_links"), dict) else {}
    published_at = str(paper.get("published_at", "")).strip()
    doi = normalize_doi(paper.get("doi") or source_links.get("doi_url"))
    landing_url = str(
        paper.get("landing_url") or source_links.get("landing_page") or paper.get("url") or ""
    ).strip()
    return {
        "source": str(paper.get("source", "")).strip(),
        "source_id": str(paper.get("source_id", "")).strip(),
        "doi": doi,
        "title": str(paper.get("title", "")).strip(),
        "year": str(paper.get("year") or (published_at[:4] if published_at[:4].isdigit() else "")),
        "journal": str(paper.get("journal", "")).strip(),
        "authors": _as_authors(paper.get("authors", [])),
        "landing_url": landing_url,
        "pdf_urls": _as_pdf_urls(paper),
    }


def bridge_report(report: dict[str, Any], selection: str = "deep-reads") -> list[dict[str, str]]:
    inspected = report.get("inspected_candidates", [])
    papers_by_id = {
        str(item.get("candidate_id", "")).strip(): item.get("paper", {})
        for item in inspected
        if isinstance(item, dict) and isinstance(item.get("paper"), dict)
    }
    rows: list[dict[str, str]] = []
    missing: list[str] = []
    for candidate_id in selected_candidate_ids(report, selection):
        paper = papers_by_id.get(candidate_id)
        if paper is None:
            missing.append(candidate_id)
            continue
        row = paper_to_harvest_row(paper)
        if not row["title"] or not row["landing_url"]:
            raise ValueError(f"selected candidate lacks title or landing URL: {candidate_id}")
        rows.append(row)
    if missing:
        raise ValueError(f"selected candidates are missing from inspected_candidates: {', '.join(missing)}")
    return rows


def write_harvest_inputs(output_dir: Path, rows: list[dict[str, str]]) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "records.csv"
    doi_path = output_dir / "doi_list.txt"
    with records_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECORD_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    dois = sorted({row["doi"] for row in rows if row["doi"]})
    doi_path.write_text("\n".join(dois) + ("\n" if dois else ""), encoding="utf-8")
    return {"records": records_path, "doi_list": doi_path}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge a reviewed shortlist into PDF harvest inputs.")
    parser.add_argument("--report", required=True, help="Screening report JSON path")
    parser.add_argument("--output", required=True, help="Output directory for records.csv and doi_list.txt")
    parser.add_argument("--selection", choices=sorted(SELECTIONS), default="deep-reads")
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    rows = bridge_report(report, args.selection)
    outputs = write_harvest_inputs(Path(args.output).resolve(), rows)
    print(
        json.dumps(
            {
                "selection": args.selection,
                "record_count": len(rows),
                "records_csv": str(outputs["records"]),
                "doi_list": str(outputs["doi_list"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
