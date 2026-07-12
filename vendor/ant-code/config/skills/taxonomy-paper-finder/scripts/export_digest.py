#!/usr/bin/env python3
# pyright: reportAny=false, reportExplicitAny=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false, reportImplicitStringConcatenation=false
"""Export agent-authored screening reports to digest artifacts."""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_CONFIG = SKILL_ROOT / "config" / "runtime-paths.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def slugify(value: str) -> str:
    parts = [part for part in "".join(ch.lower() if ch.isalnum() else "-" for ch in value).split("-") if part]
    return "-".join(parts) or "item"


def resolve_runtime_paths(runtime_cfg_path: Path) -> dict[str, Path]:
    cfg = read_json(runtime_cfg_path)
    runtime_root = (runtime_cfg_path.parent / str(cfg["runtime_root"])).resolve()
    return {
        "runtime_root": runtime_root,
        "candidates_dir": runtime_root / str(cfg.get("candidates_dir", "candidates")),
        "reports_dir": runtime_root / str(cfg.get("reports_dir", "reports")),
        "digests_dir": runtime_root / str(cfg.get("digests_dir", "digests")),
        "papers_dir": runtime_root / str(cfg.get("papers_dir", "papers")),
    }


def build_digest_payload(report: dict[str, Any]) -> dict[str, Any]:
    session = report["session"]
    digest_ready = report["digest_ready"]
    inspected = report["inspected_candidates"]
    inspected_by_id = {
        str(item.get("candidate_id", "")).strip(): item
        for item in inspected
        if str(item.get("candidate_id", "")).strip()
    }

    selected_cards: list[dict[str, Any]] = []
    for card in digest_ready.get("shortlist_cards", []):
        cid = str(card.get("candidate_id", "")).strip()
        paper = inspected_by_id[cid]["paper"]
        selected_cards.append(
            {
                "candidate_id": cid,
                "title": paper.get("title", ""),
                "source": paper.get("source", ""),
                "url": paper.get("url", ""),
                "headline": card.get("headline", ""),
                "why_it_matters": card.get("why_it_matters", ""),
            }
        )

    deep_reads: list[dict[str, Any]] = []
    for item in digest_ready.get("deep_read_briefs", []):
        cid = str(item.get("candidate_id", "")).strip()
        paper = inspected_by_id[cid]["paper"]
        deep_reads.append(
            {
                "candidate_id": cid,
                "title": paper.get("title", ""),
                "source": paper.get("source", ""),
                "url": paper.get("url", ""),
                "narrative": item.get("narrative", ""),
            }
        )

    detailed_analysis: list[dict[str, Any]] = []
    for item in digest_ready.get("detailed_analysis", []):
        cid = str(item.get("candidate_id", "")).strip()
        paper = inspected_by_id[cid]["paper"]
        detailed_analysis.append(
            {
                "candidate_id": cid,
                "title": paper.get("title", ""),
                "source": paper.get("source", ""),
                "url": paper.get("url", ""),
                "analysis": item.get("analysis", ""),
            }
        )

    return {
        "digest_date": digest_ready["digest_date"],
        "label": digest_ready["label"],
        "generated_at": session.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "session_id": session["session_id"],
        "overview": digest_ready["overview"],
        "selection_rationale": digest_ready["selection_rationale"],
        "selected_cards": selected_cards,
        "deep_reads": deep_reads,
        "detailed_analysis": detailed_analysis,
        "next_dialogue_prompts": digest_ready.get("next_dialogue_prompts", []),
        "counts": digest_ready["counts"],
    }


def render_markdown(digest: dict[str, Any]) -> str:
    lines = [
        f"# {digest['label']}",
        "",
        f"Date: {digest['digest_date']}",
        f"Session: {digest['session_id']}",
        "",
        "## Overview",
        "",
        digest["overview"],
        "",
        "## Why these made the cut",
        "",
        digest["selection_rationale"],
        "",
        "## Shortlist",
        "",
    ]

    for index, card in enumerate(digest["selected_cards"], start=1):
        lines.append(f"### {index}. {card['title']}")
        lines.append(f"- Source: {card['source']}")
        lines.append(f"- URL: {card['url']}")
        lines.append(f"- Headline: {card['headline']}")
        lines.append(f"- Why it matters: {card['why_it_matters']}")
        lines.append("")

    lines.extend(["## Top deep reads", ""])
    for index, item in enumerate(digest["deep_reads"], start=1):
        lines.append(f"### {index}. {item['title']}")
        lines.append(f"- Source: {item['source']}")
        lines.append(f"- URL: {item['url']}")
        lines.append(item["narrative"])
        lines.append("")

    lines.extend(["## Detailed analysis", ""])
    for item in digest["detailed_analysis"]:
        lines.append(f"### {item['title']}")
        lines.append(item["analysis"])
        lines.append("")

    prompts = digest.get("next_dialogue_prompts", [])
    if prompts:
        lines.extend(["## Next dialogue prompts", ""])
        for prompt in prompts:
            lines.append(f"- {prompt}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_html(digest: dict[str, Any], archive_name: str) -> str:
    card_html = []
    for card in digest["selected_cards"]:
        slug = slugify(card["title"])
        card_html.append(
            f"<article class=\"card\"><h3 id=\"{html.escape(slug)}\">{html.escape(card['title'])}</h3>"
            f"<p><strong>{html.escape(card['headline'])}</strong></p>"
            f"<p>{html.escape(card['why_it_matters'])}</p>"
            f"<p><span>{html.escape(card['source'])}</span> · <a href=\"{html.escape(card['url'])}\">paper link</a></p></article>"
        )

    deep_html = []
    for item in digest["deep_reads"]:
        deep_html.append(
            f"<article class=\"deep-read\"><h3>{html.escape(item['title'])}</h3>"
            f"<p><span>{html.escape(item['source'])}</span> · <a href=\"{html.escape(item['url'])}\">paper link</a></p>"
            f"<p>{html.escape(item['narrative'])}</p></article>"
        )

    detail_html = []
    for item in digest["detailed_analysis"]:
        detail_html.append(
            f"<article class=\"analysis\"><h3>{html.escape(item['title'])}</h3>"
            f"<p><span>{html.escape(item['source'])}</span> · <a href=\"{html.escape(item['url'])}\">paper link</a></p>"
            f"<p>{html.escape(item['analysis'])}</p></article>"
        )

    prompt_html = "".join(f"<li>{html.escape(prompt)}</li>" for prompt in digest.get("next_dialogue_prompts", []))
    prompt_section = f"<section><h2>Next dialogue prompts</h2><ul>{prompt_html}</ul></section>" if prompt_html else ""

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{html.escape(digest['label'])}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #f6f7fb; color: #1a1d24; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }}
    section {{ margin-top: 2rem; }}
    .hero, .card, .deep-read, .analysis {{ background: white; border-radius: 16px; padding: 1rem 1.1rem; box-shadow: 0 8px 24px rgba(19, 28, 45, 0.08); margin-top: 1rem; }}
    .meta {{ color: #5a6373; display: flex; gap: 1rem; flex-wrap: wrap; }}
    a {{ color: #3057d5; }}
  </style>
</head>
<body>
  <main>
    <section class=\"hero\">
      <p class=\"meta\"><span>{html.escape(digest['digest_date'])}</span><span>{html.escape(archive_name)}</span></p>
      <h1>{html.escape(digest['label'])}</h1>
      <p>{html.escape(digest['overview'])}</p>
      <p><strong>Selection rationale:</strong> {html.escape(digest['selection_rationale'])}</p>
    </section>
    <section>
      <h2>Shortlist</h2>
      {''.join(card_html)}
    </section>
    <section>
      <h2>Top deep reads</h2>
      {''.join(deep_html)}
    </section>
    <section>
      <h2>Detailed analysis</h2>
      {''.join(detail_html)}
    </section>
    {prompt_section}
  </main>
</body>
</html>
"""


def build_archive_index(digests_dir: Path) -> None:
    latest_by_date: dict[str, tuple[str, str]] = {}
    for json_file in digests_dir.glob("*.digest.json"):
        payload = read_json(json_file)
        digest_date = str(payload.get("digest_date", ""))
        title = str(payload.get("label", json_file.stem))
        html_name = json_file.name.replace(".digest.json", ".digest.html")
        current = latest_by_date.get(digest_date)
        if current is None or html_name > current[0]:
            latest_by_date[digest_date] = (html_name, title)

    rows = []
    for digest_date, (html_name, title) in sorted(latest_by_date.items(), reverse=True):
        rows.append(
            f"<li><a href=\"{html.escape(html_name)}\">{html.escape(digest_date)} — {html.escape(title)}</a></li>"
        )

    index_html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Taxonomy Paper Finder digest archive</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #f6f7fb; color: #1a1d24; }}
    main {{ max-width: 860px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }}
    .panel {{ background: white; border-radius: 16px; padding: 1rem 1.1rem; box-shadow: 0 8px 24px rgba(19, 28, 45, 0.08); }}
  </style>
</head>
<body>
  <main>
    <section class=\"panel\">
      <h1>Taxonomy Paper Finder digest archive</h1>
      <ul>{''.join(rows)}</ul>
    </section>
  </main>
</body>
</html>
"""
    write_text(digests_dir / "index.html", index_html)


def export_report(report_path: Path, runtime_cfg_path: Path) -> dict[str, Path]:
    report = read_json(report_path)
    digest = build_digest_payload(report)
    runtime_paths = resolve_runtime_paths(runtime_cfg_path)
    digests_dir = runtime_paths["digests_dir"]
    reports_dir = runtime_paths["reports_dir"]
    digests_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    base_name = f"{digest['digest_date']}.{stamp}"

    report_archive_path = reports_dir / f"{base_name}.screening-report.json"
    json_path = digests_dir / f"{base_name}.digest.json"
    md_path = digests_dir / f"{base_name}.digest.md"
    html_path = digests_dir / f"{base_name}.digest.html"

    write_json(report_archive_path, report)
    write_json(json_path, digest)
    write_text(md_path, render_markdown(digest))
    write_text(html_path, render_html(digest, html_path.name))
    build_archive_index(digests_dir)

    return {
        "report": report_archive_path,
        "json": json_path,
        "markdown": md_path,
        "html": html_path,
        "index": digests_dir / "index.html",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, help="Screening report JSON path")
    parser.add_argument("--runtime", default=str(DEFAULT_RUNTIME_CONFIG), help="Runtime paths JSON path")
    args = parser.parse_args()

    paths = export_report(Path(args.report).resolve(), Path(args.runtime).resolve())
    print(str(paths["report"]))
    print(str(paths["json"]))
    print(str(paths["markdown"]))
    print(str(paths["html"]))
    print(str(paths["index"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
