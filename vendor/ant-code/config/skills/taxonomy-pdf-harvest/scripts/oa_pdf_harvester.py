#!/usr/bin/env python3
"""
Open-access literature PDF harvester.

Given one or more keyword queries, this script collects bibliographic records
from OpenAlex, Crossref, and Europe PMC, deduplicates them by DOI/title, then
downloads legally exposed PDF URLs. Optional Unpaywall lookup can improve PDF
coverage when an email is supplied.

Outputs:
  records.csv              all deduplicated records
  doi_list.txt             normalized DOI list
  download_manifest.csv    one row per record with status and source URL
  pdfs/                    downloaded PDFs

This tool does not bypass paywalls and does not use Sci-Hub/LibGen.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


USER_AGENT = "oa-pdf-harvester/0.1 (mailto:please-set-email@example.com)"
OPENALEX_ENDPOINT = "https://api.openalex.org/works"
CROSSREF_ENDPOINT = "https://api.crossref.org/works"
EUROPEPMC_ENDPOINT = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
UNPAYWALL_ENDPOINT = "https://api.unpaywall.org/v2"
MANIFEST_FIELDS = [
    "status",
    "doi",
    "title",
    "year",
    "journal",
    "source",
    "pdf_path",
    "pdf_url",
    "message",
]


@dataclass
class Record:
    source: str
    source_id: str = ""
    doi: str = ""
    title: str = ""
    year: str = ""
    journal: str = ""
    authors: str = ""
    landing_url: str = ""
    pdf_urls: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        doi = normalize_doi(self.doi)
        if doi:
            return f"doi:{doi}"
        title = normalize_title(self.title)
        if title:
            return f"title:{hashlib.sha1(title.encode('utf-8')).hexdigest()}"
        return f"source:{self.source}:{self.source_id}"


def normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.I)
    value = re.sub(r"^doi:\s*", "", value, flags=re.I)
    return value.strip().lower()


def normalize_title(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip().lower()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(v) for v in value if v)
    value = re.sub(r"<[^>]+>", " ", str(value))
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def safe_filename(value: str, max_len: int = 140) -> str:
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.I)
    value = value.strip().replace("/", "_").replace("\\", "_")
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._-")
    return (value[:max_len] or "record")


def request_json(url: str, params: dict[str, Any], timeout: int, email: str = "") -> dict[str, Any]:
    encoded = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    full_url = f"{url}?{encoded}"
    headers = {"User-Agent": build_user_agent(email)}
    req = urllib.request.Request(full_url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return json.loads(data.decode("utf-8"))


def build_user_agent(email: str = "") -> str:
    if email:
        return f"oa-pdf-harvester/0.1 (mailto:{email})"
    return USER_AGENT


def extract_author_names_openalex(item: dict[str, Any]) -> str:
    names: list[str] = []
    for authorship in item.get("authorships") or []:
        author = authorship.get("author") or {}
        name = author.get("display_name")
        if name:
            names.append(str(name))
    return "; ".join(names[:20])


def extract_author_names_crossref(item: dict[str, Any]) -> str:
    names: list[str] = []
    for author in item.get("author") or []:
        parts = [author.get("given"), author.get("family")]
        name = " ".join(p for p in parts if p)
        if name:
            names.append(name)
    return "; ".join(names[:20])


def unique_urls(urls: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if not url:
            continue
        url = str(url).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def openalex_records(
    query: str,
    limit: int,
    timeout: int,
    email: str,
    year_from: str = "",
    year_to: str = "",
    per_page: int = 200,
) -> list[Record]:
    records: list[Record] = []
    cursor = "*"
    filters: list[str] = []
    if year_from:
        filters.append(f"from_publication_date:{year_from}-01-01")
    if year_to:
        filters.append(f"to_publication_date:{year_to}-12-31")
    while len(records) < limit:
        params: dict[str, Any] = {
            "search": query,
            "per-page": min(per_page, limit - len(records), 200),
            "cursor": cursor,
        }
        if filters:
            params["filter"] = ",".join(filters)
        if email:
            params["mailto"] = email
        data = request_json(OPENALEX_ENDPOINT, params, timeout, email)
        results = data.get("results") or []
        if not results:
            break
        for item in results:
            ids = item.get("ids") or {}
            doi = normalize_doi(ids.get("doi") or item.get("doi"))
            primary = item.get("primary_location") or {}
            best_oa = item.get("best_oa_location") or {}
            locations = item.get("locations") or []
            pdf_urls = [best_oa.get("pdf_url"), primary.get("pdf_url")]
            for loc in locations:
                pdf_urls.append((loc or {}).get("pdf_url"))
            host = primary.get("source") or best_oa.get("source") or {}
            records.append(
                Record(
                    source="openalex",
                    source_id=str(item.get("id") or ""),
                    doi=doi,
                    title=clean_text(item.get("display_name") or item.get("title")),
                    year=str(item.get("publication_year") or ""),
                    journal=clean_text(host.get("display_name") or ""),
                    authors=extract_author_names_openalex(item),
                    landing_url=str(best_oa.get("landing_page_url") or primary.get("landing_page_url") or item.get("id") or ""),
                    pdf_urls=unique_urls(pdf_urls),
                    raw=item,
                )
            )
            if len(records) >= limit:
                break
        next_cursor = (data.get("meta") or {}).get("next_cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(0.1)
    return records


def crossref_records(
    query: str,
    limit: int,
    timeout: int,
    email: str,
    year_from: str = "",
    year_to: str = "",
    per_page: int = 100,
) -> list[Record]:
    records: list[Record] = []
    cursor = "*"
    filters: list[str] = ["type:journal-article"]
    if year_from:
        filters.append(f"from-pub-date:{year_from}-01-01")
    if year_to:
        filters.append(f"until-pub-date:{year_to}-12-31")
    while len(records) < limit:
        params: dict[str, Any] = {
            "query.bibliographic": query,
            "rows": min(per_page, limit - len(records), 1000),
            "cursor": cursor,
            "filter": ",".join(filters),
        }
        if email:
            params["mailto"] = email
        data = request_json(CROSSREF_ENDPOINT, params, timeout, email)
        message = data.get("message") or {}
        items = message.get("items") or []
        if not items:
            break
        for item in items:
            date_parts = (((item.get("published-print") or item.get("published-online") or item.get("created") or {}).get("date-parts")) or [[]])[0]
            year = str(date_parts[0]) if date_parts else ""
            pdf_urls = []
            for link in item.get("link") or []:
                content_type = str(link.get("content-type") or "").lower()
                url = link.get("URL")
                if "pdf" in content_type or (url and ".pdf" in str(url).lower()):
                    pdf_urls.append(url)
            records.append(
                Record(
                    source="crossref",
                    source_id=str(item.get("URL") or item.get("DOI") or ""),
                    doi=normalize_doi(item.get("DOI")),
                    title=clean_text(item.get("title")),
                    year=year,
                    journal=clean_text(item.get("container-title")),
                    authors=extract_author_names_crossref(item),
                    landing_url=str(item.get("URL") or ""),
                    pdf_urls=unique_urls(pdf_urls),
                    raw=item,
                )
            )
            if len(records) >= limit:
                break
        next_cursor = message.get("next-cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(0.1)
    return records


def europepmc_records(
    query: str,
    limit: int,
    timeout: int,
    email: str,
    year_from: str = "",
    year_to: str = "",
    per_page: int = 100,
) -> list[Record]:
    records: list[Record] = []
    cursor = "*"
    epmc_query = query
    if year_from and year_to:
        epmc_query = f"({query}) AND FIRST_PDATE:[{year_from}-01-01 TO {year_to}-12-31]"
    elif year_from:
        epmc_query = f"({query}) AND FIRST_PDATE:[{year_from}-01-01 TO 3000-12-31]"
    elif year_to:
        epmc_query = f"({query}) AND FIRST_PDATE:[0001-01-01 TO {year_to}-12-31]"
    while len(records) < limit:
        params: dict[str, Any] = {
            "query": epmc_query,
            "format": "json",
            "pageSize": min(per_page, limit - len(records), 1000),
            "cursorMark": cursor,
            "resultType": "core",
        }
        data = request_json(EUROPEPMC_ENDPOINT, params, timeout, email)
        results = ((data.get("resultList") or {}).get("result")) or []
        if not results:
            break
        for item in results:
            pdf_urls: list[str] = []
            fulltext = item.get("fullTextUrlList") or {}
            for entry in fulltext.get("fullTextUrl") or []:
                kind = str(entry.get("documentStyle") or entry.get("availability") or entry.get("site") or "").lower()
                url = entry.get("url")
                if url and ("pdf" in kind or ".pdf" in str(url).lower()):
                    pdf_urls.append(url)
            pmcid = item.get("pmcid")
            if pmcid:
                pdf_urls.append(f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/")
            records.append(
                Record(
                    source="europepmc",
                    source_id=str(item.get("id") or ""),
                    doi=normalize_doi(item.get("doi")),
                    title=clean_text(item.get("title")),
                    year=str(item.get("pubYear") or ""),
                    journal=clean_text(item.get("journalTitle") or ""),
                    authors=clean_text(item.get("authorString") or ""),
                    landing_url=str(item.get("fullTextUrlList", {}).get("fullTextUrl", [{}])[0].get("url", "") if item.get("fullTextUrlList") else ""),
                    pdf_urls=unique_urls(pdf_urls),
                    raw=item,
                )
            )
            if len(records) >= limit:
                break
        next_cursor = data.get("nextCursorMark")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(0.1)
    return records


def unpaywall_pdf_urls(doi: str, email: str, timeout: int) -> list[str]:
    doi = normalize_doi(doi)
    if not doi or not email:
        return []
    quoted = urllib.parse.quote(doi, safe="")
    try:
        data = request_json(f"{UNPAYWALL_ENDPOINT}/{quoted}", {"email": email}, timeout, email)
    except Exception:
        return []
    urls = []
    best = data.get("best_oa_location") or {}
    urls.append(best.get("url_for_pdf"))
    for loc in data.get("oa_locations") or []:
        urls.append((loc or {}).get("url_for_pdf"))
    return unique_urls(urls)


def extract_pdf_links_from_html(base_url: str, data: bytes, limit: int = 8) -> list[str]:
    text = data.decode("utf-8", "ignore")
    candidates: list[str] = []
    patterns = [
        r"""href=["']([^"']+?\.pdf(?:\?[^"']*)?)["']""",
        r"""href=["']([^"']*?/download/pdf/?(?:\?[^"']*)?)["']""",
        r"""content=["']([^"']+?\.pdf(?:\?[^"']*)?)["']""",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.I):
            url = html.unescape(match.strip())
            if not url:
                continue
            candidates.append(urllib.parse.urljoin(base_url, url))
            if len(candidates) >= limit:
                return unique_urls(candidates)
    return unique_urls(candidates)


def merge_records(records: Iterable[Record]) -> list[Record]:
    merged: dict[str, Record] = {}
    for rec in records:
        rec.doi = normalize_doi(rec.doi)
        key = rec.key
        if key not in merged:
            rec.pdf_urls = unique_urls(rec.pdf_urls)
            merged[key] = rec
            continue
        existing = merged[key]
        existing.pdf_urls = unique_urls(existing.pdf_urls + rec.pdf_urls)
        for attr in ("doi", "title", "year", "journal", "authors", "landing_url"):
            if not getattr(existing, attr) and getattr(rec, attr):
                setattr(existing, attr, getattr(rec, attr))
        existing.source = unique_join(existing.source, rec.source)
        if rec.source_id:
            existing.source_id = unique_join(existing.source_id, rec.source_id)
    return list(merged.values())


def unique_join(left: str, right: str) -> str:
    parts = []
    for value in (left, right):
        for part in str(value or "").split(";"):
            part = part.strip()
            if part and part not in parts:
                parts.append(part)
    return ";".join(parts)


def download_pdf(
    url: str,
    dest: Path,
    timeout: int,
    email: str,
    min_bytes: int = 1024,
    max_bytes: int = 0,
    follow_html: bool = True,
) -> tuple[bool, str]:
    headers = {"User-Agent": build_user_agent(email), "Accept": "application/pdf,*/*;q=0.8"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = str(resp.headers.get("Content-Type") or "").lower()
            first = resp.read(8192)
            probe = first[:2048].lstrip()
            is_pdf = probe.startswith(b"%PDF") or ("application/pdf" in content_type and b"%PDF" in first[:4096])
            if not is_pdf:
                if follow_html and ("html" in content_type or probe.startswith(b"<!DOCTYPE") or probe.startswith(b"<html")):
                    for pdf_url in extract_pdf_links_from_html(resp.geturl(), first):
                        success, message = download_pdf(
                            pdf_url,
                            dest,
                            timeout,
                            email,
                            min_bytes=min_bytes,
                            max_bytes=max_bytes,
                            follow_html=False,
                        )
                        if success:
                            return True, f"{message}; followed_html={pdf_url}"
                return False, f"not_pdf content_type={content_type[:80]}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(dest.suffix + ".part")
            size = 0
            too_large = False
            with tmp.open("wb") as f:
                f.write(first)
                size += len(first)
                if max_bytes and size > max_bytes:
                    too_large = True
                while True:
                    if too_large:
                        break
                    chunk = resp.read(1024 * 128)
                    if not chunk:
                        break
                    f.write(chunk)
                    size += len(chunk)
                    if max_bytes and size > max_bytes:
                        too_large = True
                        break
            if too_large:
                tmp.unlink(missing_ok=True)
                return False, f"too_large bytes>{max_bytes}"
            if size < min_bytes:
                tmp.unlink(missing_ok=True)
                return False, f"too_small bytes={size}"
            tmp.replace(dest)
            return True, f"bytes={size}"
    except urllib.error.HTTPError as exc:
        return False, f"http_{exc.code}"
    except urllib.error.URLError as exc:
        return False, f"url_error {exc.reason}"
    except Exception as exc:
        return False, f"error {type(exc).__name__}: {exc}"


def write_records_csv(path: Path, records: list[Record]) -> None:
    fields = ["source", "source_id", "doi", "title", "year", "journal", "authors", "landing_url", "pdf_urls"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for rec in records:
            writer.writerow(
                {
                    "source": rec.source,
                    "source_id": rec.source_id,
                    "doi": rec.doi,
                    "title": rec.title,
                    "year": rec.year,
                    "journal": rec.journal,
                    "authors": rec.authors,
                    "landing_url": rec.landing_url,
                    "pdf_urls": " | ".join(rec.pdf_urls),
                }
            )


def write_doi_list(path: Path, records: list[Record]) -> None:
    dois = sorted({rec.doi for rec in records if rec.doi})
    path.write_text("\n".join(dois) + ("\n" if dois else ""), encoding="utf-8")


def read_records_csv(path: Path) -> list[Record]:
    records: list[Record] = []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pdf_urls = [url.strip() for url in (row.get("pdf_urls") or "").split("|") if url.strip()]
            records.append(
                Record(
                    source=row.get("source", ""),
                    source_id=row.get("source_id", ""),
                    doi=normalize_doi(row.get("doi", "")),
                    title=row.get("title", ""),
                    year=row.get("year", ""),
                    journal=row.get("journal", ""),
                    authors=row.get("authors", ""),
                    landing_url=row.get("landing_url", ""),
                    pdf_urls=unique_urls(pdf_urls),
                )
            )
    return records


def completed_manifest_keys(path: Path) -> set[str]:
    if not path.exists() or path.stat().st_size == 0:
        return set()
    keys: set[str] = set()
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            status = (row.get("status") or "").strip()
            if status not in {"downloaded", "exists", "dry_run"}:
                continue
            rec = Record(
                source=row.get("source", ""),
                doi=row.get("doi", ""),
                title=row.get("title", ""),
                year=row.get("year", ""),
                journal=row.get("journal", ""),
            )
            keys.add(rec.key)
    return keys


def filter_records(records: list[Record], year_from: str = "", year_to: str = "") -> list[Record]:
    if not year_from and not year_to:
        return records
    low = int(year_from) if year_from else None
    high = int(year_to) if year_to else None
    filtered: list[Record] = []
    for rec in records:
        try:
            year = int(str(rec.year)[:4])
        except Exception:
            continue
        if low is not None and year < low:
            continue
        if high is not None and year > high:
            continue
        filtered.append(rec)
    return filtered


def sort_records(records: list[Record], mode: str) -> list[Record]:
    if mode == "none":
        return records
    if mode == "recent":
        return sorted(records, key=lambda r: (int(str(r.year)[:4]) if str(r.year)[:4].isdigit() else -1, r.title.lower()), reverse=True)
    if mode == "oldest":
        return sorted(records, key=lambda r: (int(str(r.year)[:4]) if str(r.year)[:4].isdigit() else 9999, r.title.lower()))
    if mode == "title":
        return sorted(records, key=lambda r: r.title.lower())
    return records


def run(args: argparse.Namespace) -> int:
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    all_records: list[Record] = []

    if args.records_input:
        records_input = Path(args.records_input).resolve()
        print(f"[records-input] {records_input}", flush=True)
        records = read_records_csv(records_input)
        print(f"[records-input] {len(records)} records", flush=True)
    else:
        if not args.query:
            raise SystemExit("Error: provide --query at least once, or provide --records-input.")
        sources = set(args.sources)
        per_source_limit = max(1, args.max_results)
        for query in args.query:
            print(f"[search] {query}", flush=True)
            if "openalex" in sources:
                try:
                    recs = openalex_records(query, per_source_limit, args.timeout, args.email, args.year_from, args.year_to)
                    print(f"  openalex: {len(recs)}", flush=True)
                    all_records.extend(recs)
                except Exception as exc:
                    print(f"  openalex failed: {exc}", file=sys.stderr, flush=True)
            if "crossref" in sources:
                try:
                    recs = crossref_records(query, per_source_limit, args.timeout, args.email, args.year_from, args.year_to)
                    print(f"  crossref: {len(recs)}", flush=True)
                    all_records.extend(recs)
                except Exception as exc:
                    print(f"  crossref failed: {exc}", file=sys.stderr, flush=True)
            if "europepmc" in sources:
                try:
                    recs = europepmc_records(query, per_source_limit, args.timeout, args.email, args.year_from, args.year_to)
                    print(f"  europepmc: {len(recs)}", flush=True)
                    all_records.extend(recs)
                except Exception as exc:
                    print(f"  europepmc failed: {exc}", file=sys.stderr, flush=True)
        records = merge_records(all_records)

    records = filter_records(records, args.year_from, args.year_to)
    records = sort_records(records, args.sort)
    write_records_csv(output / "records.csv", records)
    write_doi_list(output / "doi_list.txt", records)
    print(f"[dedup] {len(records)} records", flush=True)

    if args.search_only:
        summary = {
            "records": len(records),
            "doi_count": len({rec.doi for rec in records if rec.doi}),
            "records_with_candidate_pdf_url": sum(1 for rec in records if rec.pdf_urls),
            "output": str(output),
            "mode": "search_only",
        }
        (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] {json.dumps(summary, ensure_ascii=False)}", flush=True)
        return 0

    manifest_path = output / "download_manifest.csv"
    pdf_dir = output / "pdfs"
    downloaded = 0
    skipped = 0
    failed = 0
    completed_keys = set()
    append_manifest = args.resume and manifest_path.exists() and manifest_path.stat().st_size > 0 and not args.reset_manifest
    if args.resume and not args.reset_manifest:
        completed_keys = completed_manifest_keys(manifest_path)
    with manifest_path.open("a" if append_manifest else "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if not append_manifest:
            writer.writeheader()
            f.flush()
        checked = 0
        for index, rec in enumerate(records, start=1):
            if args.download_limit and downloaded >= args.download_limit:
                break
            if args.resume and rec.key in completed_keys:
                skipped += 1
                continue
            urls = list(rec.pdf_urls)
            if args.candidate_only and not urls:
                continue
            checked += 1
            if args.max_records_to_check and checked > args.max_records_to_check:
                break
            if args.email and args.use_unpaywall and rec.doi and (not args.unpaywall_missing_only or not urls):
                urls = unique_urls(urls + unpaywall_pdf_urls(rec.doi, args.email, args.timeout))
            stem_base = rec.doi or rec.title or rec.source_id or f"record_{index}"
            stem = f"{index:06d}_{safe_filename(stem_base)}"
            dest = pdf_dir / f"{stem}.pdf"
            if dest.exists() and not args.overwrite:
                skipped += 1
                writer.writerow(row_for_manifest("exists", rec, dest, "", "already_exists"))
                f.flush()
                continue
            if not urls:
                failed += 1
                writer.writerow(row_for_manifest("no_pdf_url", rec, "", "", "no_candidate_pdf_url"))
                f.flush()
                continue
            ok = False
            last_message = ""
            last_url = ""
            for url in urls:
                last_url = url
                if args.dry_run:
                    ok = True
                    last_message = "dry_run"
                    break
                max_bytes = int(args.max_pdf_mb * 1024 * 1024) if args.max_pdf_mb else 0
                success, message = download_pdf(url, dest, args.timeout, args.email, max_bytes=max_bytes)
                last_message = message
                if success:
                    ok = True
                    downloaded += 1
                    writer.writerow(row_for_manifest("downloaded", rec, dest, url, message))
                    f.flush()
                    break
                time.sleep(args.delay)
            if not ok:
                failed += 1
                writer.writerow(row_for_manifest("failed", rec, "", last_url, last_message))
                f.flush()
            elif args.dry_run:
                skipped += 1
                writer.writerow(row_for_manifest("dry_run", rec, dest, last_url, last_message))
                f.flush()
            time.sleep(args.delay)

    summary = {
        "records": len(records),
        "downloaded": downloaded,
        "skipped": skipped,
        "failed_or_no_url": failed,
        "output": str(output),
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] {json.dumps(summary, ensure_ascii=False)}", flush=True)
    return 0


def row_for_manifest(status: str, rec: Record, path: Path | str, url: str, message: str) -> dict[str, str]:
    return {
        "status": status,
        "doi": rec.doi,
        "title": rec.title,
        "year": rec.year,
        "journal": rec.journal,
        "source": rec.source,
        "pdf_path": str(path) if path else "",
        "pdf_url": url,
        "message": message,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Harvest open-access literature PDFs by keyword.")
    parser.add_argument("--query", action="append", help="Keyword query. Repeat for multiple queries.")
    parser.add_argument("--output", required=True, help="Output run folder.")
    parser.add_argument("--records-input", default="", help="Existing records.csv to use for download-only/resume workflows.")
    parser.add_argument("--max-results", type=int, default=500, help="Maximum results per source per query.")
    parser.add_argument("--email", default="", help="Email for polite API use and optional Unpaywall lookup.")
    parser.add_argument("--year-from", default="", help="Start year, e.g. 2020.")
    parser.add_argument("--year-to", default="", help="End year, e.g. 2026.")
    parser.add_argument("--sort", choices=["recent", "oldest", "title", "none"], default="recent", help="Record order before writing/downloading.")
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["openalex", "crossref", "europepmc"],
        choices=["openalex", "crossref", "europepmc"],
        help="Metadata sources to query.",
    )
    parser.add_argument("--use-unpaywall", action="store_true", help="Use Unpaywall PDF lookup for DOI records.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds.")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between download attempts.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PDFs.")
    parser.add_argument("--resume", action="store_true", help="Append to an existing manifest and skip records already marked downloaded/exists/dry_run.")
    parser.add_argument("--reset-manifest", action="store_true", help="Ignore any previous manifest and start a new one.")
    parser.add_argument("--dry-run", action="store_true", help="Collect records and candidate URLs without downloading.")
    parser.add_argument("--search-only", action="store_true", help="Collect records and DOI list, then stop before manifest/download processing.")
    parser.add_argument("--download-limit", type=int, default=0, help="Stop after downloading this many PDFs. 0 means no limit.")
    parser.add_argument("--candidate-only", action="store_true", help="During downloads, skip records that do not already have a candidate PDF URL.")
    parser.add_argument("--max-records-to-check", type=int, default=0, help="During downloads, stop after checking this many records. 0 means no limit.")
    parser.add_argument("--max-pdf-mb", type=float, default=0, help="Skip PDFs larger than this many MB. 0 means no limit.")
    parser.add_argument("--unpaywall-missing-only", action="store_true", help="Only query Unpaywall for records without an existing candidate PDF URL.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
