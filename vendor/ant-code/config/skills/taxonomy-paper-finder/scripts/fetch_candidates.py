#!/usr/bin/env python3
# pyright: reportAny=false, reportExplicitAny=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false
"""Fetch and normalize candidate records from arXiv, bioRxiv, and PubMed."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FETCH_CONFIG = SKILL_ROOT / "config" / "fetch-candidates-config.json"
DEFAULT_RUNTIME_CONFIG = SKILL_ROOT / "config" / "runtime-paths.json"

LOCAL_TAXONOMY_KEYWORDS = [
    "taxonomy",
    "taxonomic",
    "species",
    "biodiversity",
    "insect",
    "ecology",
    "phylogeny",
    "specimen",
]

LOCAL_AI_SUPPORT_KEYWORDS = [
    "classification",
    "segmentation",
    "retrieval",
    "multimodal",
    "vision language",
    "transformer",
    "foundation model",
    "fine tuning",
    "dataset",
    "benchmark",
    "annotation",
]

LOCAL_OFF_DOMAIN_KEYWORDS = [
    "clinical",
    "hospital",
    "oncology",
    "radiology",
    "patient",
    "diagnosis",
    "cohort",
    "disease",
    "therapy",
    "treatment",
    "tuberculosis",
]

REMOTE_TAXONOMY_TERMS = ["taxonomy", "species", "biodiversity", "insect", "ecology"]
REMOTE_AI_TERMS = [
    "classification",
    "multimodal",
    "benchmark",
    "dataset",
    "foundation model",
    "vision language",
    "deep learning",
    "transfer",
]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def compact_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_doi(value: str) -> str:
    value = compact_whitespace(value)
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.I)
    value = re.sub(r"^doi:\s*", "", value, flags=re.I)
    return value.lower()


def significant_term_tokens(term: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", term.lower()) if len(token) >= 4]


def matches_query_term(text: str, term: str) -> bool:
    normalized_text = compact_whitespace(text).lower()
    normalized_term = compact_whitespace(term).lower()
    if not normalized_term:
        return False
    text_tokens = set(re.findall(r"[a-z0-9]+", normalized_text))
    term_tokens_all = re.findall(r"[a-z0-9]+", normalized_term)
    if normalized_term in normalized_text:
        if len(term_tokens_all) == 1 and len(term_tokens_all[0]) < 4:
            return term_tokens_all[0] in text_tokens
        return True

    term_tokens = significant_term_tokens(normalized_term)
    if not term_tokens:
        return False
    return all(token in text_tokens for token in term_tokens)


def extract_query_matches(title: str, abstract: str, terms: list[str]) -> list[str]:
    hay = f"{title} {abstract}"
    return [term for term in terms if matches_query_term(hay, term)]


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", compact_whitespace(text).lower()))


def keyword_hits(tokens: set[str], keywords: list[str]) -> int:
    hits = 0
    for key in keywords:
        parts = [p for p in re.findall(r"[a-z0-9]+", key.lower()) if len(p) >= 4]
        if parts and all(p in tokens for p in parts):
            hits += 1
    return hits


def should_keep_live_record(rec: dict[str, Any]) -> bool:
    if rec.get("query_matches"):
        return True
    text = f"{rec.get('title', '')} {rec.get('abstract', '')}"
    tokens = tokenize(text)
    taxonomy_hits = keyword_hits(tokens, LOCAL_TAXONOMY_KEYWORDS)
    ai_support_hits = keyword_hits(tokens, LOCAL_AI_SUPPORT_KEYWORDS)
    off_domain_hits = keyword_hits(tokens, LOCAL_OFF_DOMAIN_KEYWORDS)
    return taxonomy_hits > 0 and ai_support_hits > 0 and off_domain_hits == 0


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for rec in records:
        key = f"{rec.get('source')}:{rec.get('source_id')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def filter_live_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [rec for rec in records if should_keep_live_record(rec)]


def fetch_url_json_or_text(url: str, timeout: int, retries: int, pause_s: float) -> Any:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            text_l = text.lstrip()
            if text_l.startswith("{") or text_l.startswith("["):
                return json.loads(text)
            return text
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < retries:
                time.sleep(pause_s)
    raise RuntimeError(f"request failed for {url}: {last_exc}")


def build_arxiv_query() -> str:
    taxonomy_clause = " OR ".join(f'all:"{term}"' for term in REMOTE_TAXONOMY_TERMS)
    ai_clause = " OR ".join(f'all:"{term}"' for term in REMOTE_AI_TERMS)
    return f"({taxonomy_clause}) AND ({ai_clause})"


def build_pubmed_query() -> str:
    taxonomy_clause = " OR ".join(f'"{term}"[Title/Abstract]' for term in REMOTE_TAXONOMY_TERMS)
    ai_clause = " OR ".join(f'"{term}"[Title/Abstract]' for term in REMOTE_AI_TERMS)
    return f"({taxonomy_clause}) AND ({ai_clause})"


def normalize_record(
    source: str,
    source_id: str,
    title: str,
    abstract: str,
    authors: list[str],
    published_at: str,
    url: str,
    query_terms: list[str],
    pdf_url: str = "",
    html_url: str = "",
    doi_url: str = "",
    doi: str = "",
    journal: str = "",
) -> dict[str, Any]:
    matches = extract_query_matches(title, abstract, query_terms)
    tags = sorted({m.split()[0].lower() for m in matches if m})
    inspection_hint = "abstract" if compact_whitespace(abstract) else "metadata"
    available_formats: list[str] = [inspection_hint]
    if html_url:
        available_formats.append("html")
    if pdf_url:
        available_formats.append("pdf")
    normalized_doi = normalize_doi(doi or doi_url)
    return {
        "source": source,
        "source_id": source_id,
        "doi": normalized_doi,
        "title": compact_whitespace(title),
        "abstract": compact_whitespace(abstract),
        "authors": [compact_whitespace(a) for a in authors if compact_whitespace(a)],
        "published_at": published_at,
        "year": published_at[:4] if published_at[:4].isdigit() else "",
        "journal": compact_whitespace(journal),
        "url": url,
        "landing_url": url,
        "pdf_urls": [pdf_url] if pdf_url else [],
        "tags": tags,
        "query_matches": matches,
        "normalization": {
            "normalized_at": datetime.now(timezone.utc).isoformat(),
            "record_key": f"{source}:{source_id}",
        },
        "source_links": {
            "landing_page": url,
            "abstract_url": url,
            **({"html_url": html_url} if html_url else {}),
            **({"pdf_url": pdf_url} if pdf_url else {}),
            **({"doi_url": doi_url} if doi_url else {}),
        },
        "reading_hints": {
            "inspection_hint": inspection_hint,
            "available_formats": available_formats,
            "priority_hint": "high" if matches else "medium",
        },
    }


def fetch_arxiv(cfg: dict[str, Any], terms: list[str], limits: dict[str, Any]) -> list[dict[str, Any]]:
    max_n = int(limits["max_per_source"])
    timeout = int(limits["request_timeout_seconds"])
    retries = int(limits["retries"])
    pause_s = float(limits["retry_pause_seconds"])
    query = build_arxiv_query()
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_n,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = f"{cfg['url']}?{urllib.parse.urlencode(params)}"
    text = fetch_url_json_or_text(url, timeout=timeout, retries=retries, pause_s=pause_s)
    if not isinstance(text, str):
        return []

    root = ET.fromstring(text)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out: list[dict[str, Any]] = []
    for entry in root.findall("a:entry", ns):
        source_id = compact_whitespace(entry.findtext("a:id", default="", namespaces=ns)).split("/")[-1]
        title = entry.findtext("a:title", default="", namespaces=ns)
        abstract = entry.findtext("a:summary", default="", namespaces=ns)
        published_at = entry.findtext("a:published", default="", namespaces=ns)
        authors = [x.findtext("a:name", default="", namespaces=ns) for x in entry.findall("a:author", ns)]
        url_link = entry.findtext("a:id", default="", namespaces=ns)
        pdf_url = ""
        for link in entry.findall("a:link", ns):
            if link.attrib.get("title") == "pdf" and link.attrib.get("href"):
                pdf_url = str(link.attrib.get("href"))
                break
        if not source_id or not title:
            continue
        out.append(
            normalize_record(
                "arxiv",
                source_id,
                title,
                abstract,
                authors,
                published_at,
                url_link,
                terms,
                pdf_url=pdf_url,
                html_url=f"https://arxiv.org/html/{source_id}" if source_id else "",
            )
        )
    return out


def fetch_biorxiv(cfg: dict[str, Any], terms: list[str], limits: dict[str, Any]) -> list[dict[str, Any]]:
    max_n = int(limits["max_per_source"])
    timeout = int(limits["request_timeout_seconds"])
    retries = int(limits["retries"])
    pause_s = float(limits["retry_pause_seconds"])
    base_url = cfg["url"].rstrip("/")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start = "2024-01-01"
    url = f"{base_url}/{start}/{today}/0"
    payload = fetch_url_json_or_text(url, timeout=timeout, retries=retries, pause_s=pause_s)
    if not isinstance(payload, dict):
        return []

    records: list[dict[str, Any]] = []
    for row in payload.get("collection", [])[: max_n * 10]:
        title = compact_whitespace(str(row.get("title", "")))
        abstract = compact_whitespace(str(row.get("abstract", "")))
        if not title:
            continue
        doi = str(row.get("doi", "")).strip()
        version = str(row.get("version", "1")).strip() or "1"
        source_id = doi or version or title[:60]
        landing = f"https://www.biorxiv.org/content/{doi}v{version}" if doi else "https://www.biorxiv.org"
        record = normalize_record(
            "biorxiv",
            source_id,
            title,
            abstract,
            [compact_whitespace(a) for a in str(row.get("authors", "")).split(";") if a.strip()],
            str(row.get("date", "")),
            landing,
            terms,
            pdf_url=f"{landing}.full.pdf" if doi else "",
            html_url=f"{landing}.full" if doi else "",
            doi_url=f"https://doi.org/{doi}" if doi else "",
            doi=doi,
            journal=str(row.get("server", "bioRxiv")),
        )
        if terms and not should_keep_live_record(record):
            continue
        records.append(record)
        if len(records) >= max_n:
            break
    return records


def parse_pubmed_abstracts_xml(xml_text: str) -> dict[str, str]:
    root = ET.fromstring(xml_text)
    abstracts_by_pmid: dict[str, str] = {}
    for article in root.findall(".//PubmedArticle"):
        pmid = compact_whitespace("".join(article.findtext(".//PMID", default="")))
        if not pmid:
            continue
        parts: list[str] = []
        for abstract_text in article.findall(".//Abstract/AbstractText"):
            label = compact_whitespace(abstract_text.attrib.get("Label", ""))
            text = compact_whitespace("".join(abstract_text.itertext()))
            if not text:
                continue
            parts.append(f"{label}: {text}" if label else text)
        abstracts_by_pmid[pmid] = compact_whitespace(" ".join(parts))
    return abstracts_by_pmid


def extract_pubmed_links(row: dict[str, Any]) -> tuple[str, str, str]:
    doi = ""
    doi_url = ""
    html_url = ""
    for article_id in row.get("articleids", []):
        if not isinstance(article_id, dict):
            continue
        idtype = str(article_id.get("idtype", "")).lower()
        value = str(article_id.get("value", "")).strip()
        if not value:
            continue
        if idtype == "doi" and not doi_url:
            doi = normalize_doi(value)
            doi_url = f"https://doi.org/{value}"
        if idtype in {"pmc", "pmcid"} and not html_url:
            pmc_id = value if value.upper().startswith("PMC") else f"PMC{value}"
            html_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/"
    return doi, doi_url, html_url


def fetch_pubmed(cfg: dict[str, Any], terms: list[str], limits: dict[str, Any]) -> list[dict[str, Any]]:
    max_n = int(limits["max_per_source"])
    timeout = int(limits["request_timeout_seconds"])
    retries = int(limits["retries"])
    pause_s = float(limits["retry_pause_seconds"])

    esearch_params = {
        "db": "pubmed",
        "retmode": "json",
        "retmax": str(max_n),
        "sort": "pub date",
        "term": build_pubmed_query(),
    }
    esearch_url = f"{cfg['esearch_url']}?{urllib.parse.urlencode(esearch_params)}"
    esearch_payload = fetch_url_json_or_text(esearch_url, timeout=timeout, retries=retries, pause_s=pause_s)
    if not isinstance(esearch_payload, dict):
        return []
    ids = esearch_payload.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    esummary_params = {"db": "pubmed", "retmode": "json", "id": ",".join(ids)}
    esummary_url = f"{cfg['esummary_url']}?{urllib.parse.urlencode(esummary_params)}"
    esummary_payload = fetch_url_json_or_text(esummary_url, timeout=timeout, retries=retries, pause_s=pause_s)
    if not isinstance(esummary_payload, dict):
        return []

    efetch_params = {"db": "pubmed", "retmode": "xml", "id": ",".join(ids)}
    efetch_url = f"{cfg['efetch_url']}?{urllib.parse.urlencode(efetch_params)}"
    efetch_payload = fetch_url_json_or_text(efetch_url, timeout=timeout, retries=retries, pause_s=pause_s)
    abstract_lookup = parse_pubmed_abstracts_xml(efetch_payload) if isinstance(efetch_payload, str) else {}

    result = esummary_payload.get("result", {})
    out: list[dict[str, Any]] = []
    for pmid in ids:
        row = result.get(pmid, {})
        title = compact_whitespace(str(row.get("title", "")))
        if not title:
            continue
        abstract = compact_whitespace(abstract_lookup.get(str(pmid), ""))
        names = [x.get("name", "") for x in row.get("authors", []) if isinstance(x, dict)]
        published_at = str(row.get("pubdate", ""))
        landing = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        doi, doi_url, html_url = extract_pubmed_links(row)
        out.append(
            normalize_record(
                "pubmed",
                str(pmid),
                title,
                abstract,
                names,
                published_at,
                landing,
                terms,
                html_url=html_url,
                doi_url=doi_url,
                doi=doi,
                journal=str(row.get("fulljournalname", "")),
            )
        )
    return out


def fallback_records() -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [
        normalize_record(
            "arxiv",
            "offline-demo-1",
            "Species-level insect classification with multimodal transformers",
            "We evaluate transfer learning strategies for insect taxonomy using image-text metadata.",
            ["A. Researcher", "B. Scientist"],
            now,
            "https://arxiv.org/abs/0000.00001",
            ["insect image recognition", "multimodal model biology"],
            pdf_url="https://arxiv.org/pdf/0000.00001.pdf",
            html_url="https://arxiv.org/html/0000.00001",
        ),
        normalize_record(
            "biorxiv",
            "offline-demo-2",
            "A curated biodiversity benchmark for species identification",
            "Dataset paper describing taxonomy-relevant benchmarking and annotation protocol.",
            ["C. Biologist"],
            now,
            "https://www.biorxiv.org/content/10.1101/000000v1",
            ["biodiversity foundation model", "species classification deep learning"],
            pdf_url="https://www.biorxiv.org/content/10.1101/000000v1.full.pdf",
            html_url="https://www.biorxiv.org/content/10.1101/000000v1.full",
            doi_url="https://doi.org/10.1101/000000",
            doi="10.1101/000000",
            journal="bioRxiv",
        ),
    ]


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


def fetch_all_candidates(fetch_cfg_path: Path, runtime_cfg_path: Path) -> Path:
    cfg = read_json(fetch_cfg_path)
    limits = cfg["limits"]
    terms = [term for group in cfg.get("watch_groups", []) for term in group.get("query_terms", [])]
    sources = cfg.get("sources", {})
    runtime_paths = resolve_runtime_paths(runtime_cfg_path)

    records: list[dict[str, Any]] = []
    errors: dict[str, str] = {}

    if sources.get("arxiv", {}).get("enabled"):
        try:
            records.extend(fetch_arxiv(sources["arxiv"], terms, limits))
        except Exception as exc:  # noqa: BLE001
            errors["arxiv"] = str(exc)
        time.sleep(float(limits["between_source_pause_seconds"]))

    if sources.get("biorxiv", {}).get("enabled"):
        try:
            records.extend(fetch_biorxiv(sources["biorxiv"], terms, limits))
        except Exception as exc:  # noqa: BLE001
            errors["biorxiv"] = str(exc)
        time.sleep(float(limits["between_source_pause_seconds"]))

    if sources.get("pubmed", {}).get("enabled"):
        try:
            records.extend(fetch_pubmed(sources["pubmed"], terms, limits))
        except Exception as exc:  # noqa: BLE001
            errors["pubmed"] = str(exc)

    records = filter_live_records(dedupe_records(records))
    used_fallback = False
    if not records:
        records = fallback_records()
        used_fallback = True

    stamp = utc_stamp()
    output_path = runtime_paths["candidates_dir"] / f"{stamp}.paper-records.json"
    write_json(
        output_path,
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "taxonomy-paper-finder",
            "record_count": len(records),
            "used_fallback": used_fallback,
            "errors": errors,
            "records": records,
        },
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_FETCH_CONFIG), help="Fetch config JSON path")
    parser.add_argument("--runtime", default=str(DEFAULT_RUNTIME_CONFIG), help="Runtime paths JSON path")
    args = parser.parse_args()

    output = fetch_all_candidates(Path(args.config).resolve(), Path(args.runtime).resolve())
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
