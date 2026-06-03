"""Lookup helpers for PDF-extracted taxon/part descriptions."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import csv
from pathlib import Path
from typing import Any


LITERATURE_DESCRIPTION_SOURCE_SCHEMA = "taxamask-literature-description-source-v1"


PART_KEY_ALIASES: dict[str, list[str]] = {
    "body_habitus": ["body", "habitus", "whole body", "整体", "体型", "体态"],
    "head": ["head", "cephalic", "clypeus", "frons", "vertex", "occipital", "头部", "头"],
    "mandible": ["mandible", "mandibles", "mandibular", "masticatory margin", "teeth", "上颚", "大颚"],
    "antenna_scape": ["antenna", "antennae", "scape", "funiculus", "antennal", "触角", "柄节"],
    "eye_ocelli": ["eye", "eyes", "ocellus", "ocelli", "复眼", "单眼"],
    "mesosoma": ["mesosoma", "alitrunk", "mesosomal", "中躯"],
    "pronotum": ["pronotum", "pronotal", "前胸背板"],
    "mesonotum": ["mesonotum", "mesonotal", "mesopleuron", "mesopleura", "中胸"],
    "propodeum": ["propodeum", "propodeal", "propodeal spine", "propodeal spines", "并胸腹节"],
    "petiole": ["petiole", "petiolar", "node", "petiolar node", "腹柄节"],
    "postpetiole": ["postpetiole", "postpetiolar", "后腹柄节"],
    "gaster": ["gaster", "gastral", "tergite", "sternite", "abdomen", "腹部", "膨腹部"],
    "legs": ["leg", "legs", "femur", "femora", "tibia", "tibiae", "tarsus", "tarsi", "足", "腿"],
    "sculpture": ["sculpture", "sculpturing", "striation", "reticulation", "punctation", "体表雕刻"],
    "pilosity_pubescence": ["pilosity", "pubescence", "seta", "setae", "hair", "hairs", "毛被", "立毛"],
    "color": ["color", "colour", "颜色"],
    "measurements": ["measurement", "measurements", "hl", "hw", "sl", "el", "wl", "ci", "si", "测量"],
    "caste_stage": ["worker", "queen", "male", "gyne", "ergatoid", "larva", "caste", "品级", "性型"],
}


BROAD_PART_KEYS: dict[str, list[str]] = {
    "head": ["head", "mandible", "antenna_scape", "eye_ocelli"],
    "mesosoma": ["mesosoma", "pronotum", "mesonotum", "propodeum"],
    "gaster": ["gaster", "petiole", "postpetiole"],
}


def default_literature_db_path(repo_root: str) -> str:
    return os.path.abspath(
        os.path.join(repo_root, "TaxaMask_outputs", "pdf_extraction", "taxamask_literature.db")
    )


def candidate_literature_db_paths(
    *,
    repo_root: str,
    provenance: dict[str, Any] | None = None,
    extra_paths: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    paths: list[str] = []
    provenance = provenance if isinstance(provenance, dict) else {}
    source_ref = provenance.get("source_ref", {})
    if not isinstance(source_ref, dict):
        source_ref = {}

    for value in (
        provenance.get("source_db"),
        source_ref.get("db_path"),
        *(extra_paths or []),
        default_literature_db_path(repo_root),
    ):
        text = str(value or "").strip()
        if not text:
            continue
        expanded = os.path.abspath(os.path.expanduser(text))
        if os.path.isdir(expanded) or not os.path.splitext(expanded)[1]:
            expanded = os.path.join(expanded, "taxamask_literature.db")
        normalized = os.path.normcase(os.path.normpath(expanded))
        if normalized not in {os.path.normcase(os.path.normpath(item)) for item in paths}:
            paths.append(os.path.abspath(expanded))
    return paths


def infer_literature_db_path_from_artifact_image(image_path: str) -> str:
    """Infer the sibling literature database from a PDF extraction artifact image path."""
    text = str(image_path or "").strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    parts = path.parts
    for index, part in enumerate(parts):
        if not str(part).endswith("_v2_artifacts"):
            continue
        stem = str(part)[: -len("_v2_artifacts")]
        if not stem:
            continue
        artifact_dir = Path(*parts[: index + 1])
        candidate = artifact_dir.parent / f"{stem}.db"
        return os.path.abspath(os.fspath(candidate))
    return ""


def infer_figure_id_from_exported_image_name(image_path: str) -> int | None:
    name = os.path.basename(str(image_path or ""))
    match = re.search(r"__(?:accepted|review)_(\d+)__", name, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def resolve_literature_context(
    db_path: str,
    *,
    image_path: str = "",
    provenance: dict[str, Any] | None = None,
    taxon_hint: str = "",
    allow_filename_figure_id: bool = True,
    allow_taxon_match: bool = False,
) -> dict[str, Any]:
    context = {
        "source_db": os.path.abspath(str(db_path or "")),
        "figure_id": None,
        "pdf_file_id": None,
        "pdf_file": "",
        "pdf_file_path": "",
        "page_number": None,
        "figure_index": None,
        "image_file_name": os.path.basename(str(image_path or "")),
        "species_candidate": _clean_taxon(taxon_hint),
        "link_mode": "image_provenance",
        "available": False,
        "reason": "",
    }
    if not db_path or not os.path.exists(db_path):
        context["reason"] = "literature_db_missing"
        return context

    provenance = provenance if isinstance(provenance, dict) else {}
    source_ref = provenance.get("source_ref", {})
    if not isinstance(source_ref, dict):
        source_ref = {}
    if provenance.get("species_candidate"):
        context["species_candidate"] = _clean_taxon(provenance.get("species_candidate"))

    connection = sqlite3.connect(db_path)
    try:
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        if not _table_exists(cursor, "taxon_part_descriptions"):
            context["reason"] = "taxon_part_descriptions_missing"
            return context
        if not _table_exists(cursor, "figure_records"):
            pdf_id = _as_int(provenance.get("pdf_id") or provenance.get("pdf_file_id"))
            if pdf_id is not None:
                context["pdf_file_id"] = pdf_id
                _attach_pdf_file(cursor, context)
                context["available"] = True
            elif allow_taxon_match and _attach_taxon_match_context(cursor, context):
                context["available"] = True
            else:
                context["reason"] = "figure_records_missing"
            return context

        explicit_figure_id = False
        figure_id = None
        if str(source_ref.get("table", "") or "").strip() == "figure_records":
            figure_id = _as_int(source_ref.get("row_id"))
            explicit_figure_id = figure_id is not None
        if figure_id is None:
            figure_id = _as_int(provenance.get("figure_id"))
            explicit_figure_id = figure_id is not None

        row = _figure_row_by_id(cursor, figure_id) if explicit_figure_id else None
        if row is None:
            row = _figure_row_by_image(cursor, image_path, allow_name_match=allow_filename_figure_id)
        if row is None:
            exported_figure_id = _figure_id_from_import_ready_manifest(db_path, image_path)
            row = _figure_row_by_id(cursor, exported_figure_id) if exported_figure_id is not None else None
        if row is None and allow_filename_figure_id:
            inferred_figure_id = infer_figure_id_from_exported_image_name(image_path)
            row = _figure_row_by_id(cursor, inferred_figure_id) if inferred_figure_id is not None else None
        if row is None and provenance.get("pdf_id"):
            context["pdf_file_id"] = _as_int(provenance.get("pdf_id"))
            _attach_pdf_file(cursor, context)
            context["available"] = context["pdf_file_id"] is not None
            context["reason"] = "" if context["available"] else "figure_context_missing"
            return context
        if row is None and allow_taxon_match and _attach_taxon_match_context(cursor, context):
            context["available"] = True
            context["reason"] = ""
            return context
        if row is None:
            context["reason"] = "figure_context_missing"
            return context

        context.update(
            {
                "figure_id": _as_int(row["id"]),
                "pdf_file_id": _as_int(row["pdf_file_id"]),
                "page_number": _as_int(row["page_number"]),
                "figure_index": _as_int(row["figure_index"]),
                "image_file_name": str(row["image_file_name"] or context["image_file_name"]),
                "species_candidate": _clean_taxon(row["species_candidate"]) or context["species_candidate"],
                "pdf_file": str(row["pdf_file"] or ""),
                "pdf_file_path": str(row["pdf_file_path"] or ""),
                "link_mode": "image_provenance",
                "available": True,
                "reason": "",
            }
        )
        return context
    finally:
        connection.close()


def query_literature_part_descriptions(
    db_path: str,
    *,
    context: dict[str, Any] | None = None,
    current_part: str = "",
    search_text: str = "",
    taxon_hint: str = "",
    limit: int = 200,
) -> list[dict[str, Any]]:
    if not db_path or not os.path.exists(db_path):
        return []
    context = context if isinstance(context, dict) else {}
    pdf_file_id = _as_int(context.get("pdf_file_id"))
    species = _clean_taxon(context.get("species_candidate")) or _clean_taxon(taxon_hint)
    keys, text_terms = _search_keys_and_terms(search_text or current_part)

    clauses = []
    params: list[Any] = []
    if pdf_file_id is not None:
        clauses.append("pdf_file_id = ?")
        params.append(pdf_file_id)
    if species and species.lower() != "unknown":
        clauses.append("(taxon_name = ? OR taxon_name = '' OR ? = '')")
        params.extend([species, species])
    if keys or text_terms:
        search_clauses = []
        if keys:
            placeholders = ",".join("?" for _ in keys)
            search_clauses.append(f"LOWER(part_key) IN ({placeholders})")
            params.extend([key.lower() for key in keys])
        for term in text_terms[:10]:
            like = f"%{term.lower()}%"
            search_clauses.extend(
                [
                    "LOWER(part_key) LIKE ?",
                    "LOWER(part_label) LIKE ?",
                    "LOWER(description_text) LIKE ?",
                ]
            )
            params.extend([like, like, like])
        clauses.append("(" + " OR ".join(search_clauses) + ")")

    where_sql = "WHERE " + " AND ".join(clauses) if clauses else ""
    connection = sqlite3.connect(db_path)
    try:
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        if not _table_exists(cursor, "taxon_part_descriptions"):
            return []
        cursor.execute(
            f"""
            SELECT id, pdf_file_id, file_name, file_path, file_hash, taxon_name,
                   caste_or_stage, part_key, part_label, description_text,
                   source_pages, source_block_refs, source_blocks, model_used,
                   confidence, review_status, created_at
            FROM taxon_part_descriptions
            {where_sql}
            ORDER BY
                CASE WHEN taxon_name = ? THEN 0 WHEN taxon_name = '' THEN 1 ELSE 2 END,
                part_key ASC,
                confidence DESC,
                id ASC
            LIMIT ?
            """,
            [*params, species, max(1, int(limit or 200))],
        )
        return [_record_from_row(row, db_path=db_path, context=context) for row in cursor.fetchall()]
    finally:
        connection.close()


def query_literature_text_blocks(
    db_path: str,
    *,
    context: dict[str, Any] | None = None,
    current_part: str = "",
    search_text: str = "",
    taxon_hint: str = "",
    scope: str = "taxon",
    limit: int = 200,
) -> list[dict[str, Any]]:
    if not db_path or not os.path.exists(db_path):
        return []
    context = context if isinstance(context, dict) else {}
    pdf_file_id = _as_int(context.get("pdf_file_id"))
    if pdf_file_id is None:
        return []
    species = _clean_taxon(context.get("species_candidate")) or _clean_taxon(taxon_hint)
    keys, text_terms = _search_keys_and_terms(search_text or current_part)
    terms = _unique([*text_terms, *keys])

    clauses = ["pdf_file_id = ?"]
    params: list[Any] = [pdf_file_id]
    if str(scope or "").strip().lower() in {"taxon", "current_taxon", "species"} and species and species.lower() != "unknown":
        clauses.append("(llm_taxon_name = ? OR llm_taxon_name = '' OR ? = '')")
        params.extend([species, species])
    if terms:
        search_clauses = []
        for term in terms[:12]:
            like = f"%{term.lower()}%"
            search_clauses.extend(
                [
                    "LOWER(text_content) LIKE ?",
                    "LOWER(section_hint) LIKE ?",
                    "LOWER(text_type) LIKE ?",
                    "LOWER(llm_role) LIKE ?",
                    "LOWER(llm_taxon_name) LIKE ?",
                    "LOWER(block_ref) LIKE ?",
                ]
            )
            params.extend([like, like, like, like, like, like])
        clauses.append("(" + " OR ".join(search_clauses) + ")")

    where_sql = "WHERE " + " AND ".join(clauses)
    connection = sqlite3.connect(db_path)
    try:
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        if not _table_exists(cursor, "pdf_text_blocks"):
            return []
        cursor.execute(
            f"""
            SELECT id, pdf_file_id, file_name, file_path, file_hash, block_ref,
                   page_number, block_index, section_hint, text_type, text_content,
                   llm_role, llm_taxon_name, llm_confidence, model_used, created_at
            FROM pdf_text_blocks
            {where_sql}
            ORDER BY
                CASE WHEN llm_taxon_name = ? THEN 0 WHEN llm_taxon_name = '' THEN 1 ELSE 2 END,
                page_number ASC,
                block_index ASC,
                id ASC
            LIMIT ?
            """,
            [*params, species, max(1, int(limit or 200))],
        )
        return [_text_block_record_from_row(row, db_path=db_path, context=context) for row in cursor.fetchall()]
    finally:
        connection.close()


def build_description_source(record: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context if isinstance(context, dict) else {}
    link_mode = str(context.get("link_mode") or "image_provenance")
    source_kind = "pdf_taxon_part_description"
    if link_mode == "taxon_match_not_image_provenance":
        source_kind = "pdf_taxon_part_description_species_match"
    return {
        "schema_version": LITERATURE_DESCRIPTION_SOURCE_SCHEMA,
        "source": source_kind,
        "link_mode": link_mode,
        "image_provenance_matched": link_mode != "taxon_match_not_image_provenance",
        "source_db": str(record.get("source_db") or context.get("source_db") or ""),
        "record_id": record.get("id"),
        "pdf_file_id": record.get("pdf_file_id") or context.get("pdf_file_id"),
        "figure_id": context.get("figure_id"),
        "pdf_file": str(record.get("file_name") or context.get("pdf_file") or ""),
        "pdf_file_path": str(record.get("file_path") or context.get("pdf_file_path") or ""),
        "page_number": context.get("page_number"),
        "taxon_name": str(record.get("taxon_name") or ""),
        "species_candidate": str(context.get("species_candidate") or ""),
        "caste_or_stage": str(record.get("caste_or_stage") or ""),
        "part_key": str(record.get("part_key") or ""),
        "part_label": str(record.get("part_label") or ""),
        "source_pages": list(record.get("source_pages") or []),
        "source_block_refs": list(record.get("source_block_refs") or []),
        "confidence": float(record.get("confidence") or 0.0),
        "review_status": str(record.get("review_status") or ""),
    }


def build_text_block_source(record: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context if isinstance(context, dict) else {}
    link_mode = str(context.get("link_mode") or "image_provenance")
    return {
        "schema_version": LITERATURE_DESCRIPTION_SOURCE_SCHEMA,
        "source": "pdf_text_block",
        "link_mode": link_mode,
        "image_provenance_matched": link_mode != "taxon_match_not_image_provenance",
        "source_db": str(record.get("source_db") or context.get("source_db") or ""),
        "record_id": record.get("id"),
        "pdf_file_id": record.get("pdf_file_id") or context.get("pdf_file_id"),
        "figure_id": context.get("figure_id"),
        "pdf_file": str(record.get("file_name") or context.get("pdf_file") or ""),
        "pdf_file_path": str(record.get("file_path") or context.get("pdf_file_path") or ""),
        "page_number": record.get("page_number") or context.get("page_number"),
        "species_candidate": str(context.get("species_candidate") or ""),
        "block_ref": str(record.get("block_ref") or ""),
        "llm_role": str(record.get("llm_role") or ""),
        "llm_taxon_name": str(record.get("llm_taxon_name") or ""),
        "confidence": float(record.get("llm_confidence") or 0.0),
    }


def _search_keys_and_terms(search_text: str) -> tuple[list[str], list[str]]:
    raw = str(search_text or "").strip()
    if not raw:
        return [], []
    lowered = raw.lower()
    keys: list[str] = []
    terms: list[str] = []

    for key, aliases in PART_KEY_ALIASES.items():
        values = [key, *aliases]
        if any(lowered == str(value).lower() or lowered in str(value).lower() or str(value).lower() in lowered for value in values):
            keys.append(key)
            for broad_key, broad_values in BROAD_PART_KEYS.items():
                if key == broad_key:
                    keys.extend(broad_values)
            terms.extend(str(value).lower() for value in values)

    for token in re.split(r"[\s,;，；/|]+", raw):
        token = token.strip()
        if token:
            terms.append(token.lower())

    return _unique(keys), _unique(terms)


def _figure_row_by_id(cursor: sqlite3.Cursor, figure_id: int | None) -> sqlite3.Row | None:
    if figure_id is None:
        return None
    cursor.execute(
        """
        SELECT f.id, f.pdf_file_id, f.page_number, f.figure_index,
               f.image_file_path, f.image_file_name, f.species_candidate,
               p.file_name AS pdf_file, p.file_path AS pdf_file_path
        FROM figure_records f
        LEFT JOIN pdf_files p ON p.id = f.pdf_file_id
        WHERE f.id = ?
        """,
        (figure_id,),
    )
    return cursor.fetchone()


def _figure_row_by_image(cursor: sqlite3.Cursor, image_path: str, *, allow_name_match: bool = True) -> sqlite3.Row | None:
    image_path = str(image_path or "").strip()
    if not image_path:
        return None
    abs_path = os.path.abspath(os.path.expanduser(image_path))
    base_name = os.path.basename(image_path)
    name_clause = "OR LOWER(f.image_file_name) = LOWER(?)" if allow_name_match else ""
    params: tuple[Any, ...]
    if allow_name_match:
        params = (image_path, abs_path, base_name)
    else:
        params = (image_path, abs_path)
    cursor.execute(
        f"""
        SELECT f.id, f.pdf_file_id, f.page_number, f.figure_index,
               f.image_file_path, f.image_file_name, f.species_candidate,
               p.file_name AS pdf_file, p.file_path AS pdf_file_path
        FROM figure_records f
        LEFT JOIN pdf_files p ON p.id = f.pdf_file_id
        WHERE LOWER(f.image_file_path) = LOWER(?)
           OR LOWER(f.image_file_path) = LOWER(?)
           {name_clause}
        ORDER BY f.id ASC
        LIMIT 1
        """,
        params,
    )
    return cursor.fetchone()


def _figure_id_from_import_ready_manifest(db_path: str, image_path: str) -> int | None:
    image_text = str(image_path or "").strip()
    if not image_text:
        return None
    db = Path(str(db_path or "")).expanduser()
    artifacts_dir = db.parent / f"{db.stem}_v2_artifacts"
    stats_dir = artifacts_dir / "stats"
    if not stats_dir.exists():
        return None
    abs_image = os.path.normcase(os.path.normpath(os.path.abspath(os.path.expanduser(image_text))))
    image_name = os.path.basename(image_text)
    inferred_db = infer_literature_db_path_from_artifact_image(image_text)
    allow_name_match = (
        bool(inferred_db)
        and os.path.normcase(os.path.normpath(os.path.abspath(inferred_db)))
        == os.path.normcase(os.path.normpath(os.path.abspath(os.fspath(db))))
    )
    for manifest in sorted(stats_dir.glob("*_import_ready_figures.csv")):
        try:
            with open(manifest, "r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    exported_path = str(row.get("exported_image_path", "") or "").strip()
                    exported_name = str(row.get("exported_image_name", "") or "").strip()
                    if exported_path:
                        exported_norm = os.path.normcase(os.path.normpath(os.path.abspath(os.path.expanduser(exported_path))))
                        if exported_norm == abs_image:
                            return _as_int(row.get("figure_id"))
                    if allow_name_match and exported_name and exported_name == image_name:
                        return _as_int(row.get("figure_id"))
        except Exception:
            continue
    return None


def _attach_pdf_file(cursor: sqlite3.Cursor, context: dict[str, Any]) -> None:
    pdf_file_id = _as_int(context.get("pdf_file_id"))
    if pdf_file_id is None or not _table_exists(cursor, "pdf_files"):
        return
    cursor.execute("SELECT file_name, file_path FROM pdf_files WHERE id = ?", (pdf_file_id,))
    row = cursor.fetchone()
    if row:
        if isinstance(row, sqlite3.Row):
            context["pdf_file"] = str(row["file_name"] or "")
            context["pdf_file_path"] = str(row["file_path"] or "")
        else:
            context["pdf_file"] = str(row[0] or "")
            context["pdf_file_path"] = str(row[1] or "")


def _attach_taxon_match_context(cursor: sqlite3.Cursor, context: dict[str, Any]) -> bool:
    species = _clean_taxon(context.get("species_candidate"))
    if not species or species.lower() in {"unknown", "unknown taxon", "n/a", "none", "null"}:
        context["reason"] = "taxon_hint_missing"
        return False
    if not _table_exists(cursor, "taxon_part_descriptions"):
        context["reason"] = "taxon_part_descriptions_missing"
        return False
    cursor.execute(
        """
        SELECT taxon_name
        FROM taxon_part_descriptions
        WHERE LOWER(taxon_name) = LOWER(?)
        LIMIT 1
        """,
        (species,),
    )
    row = cursor.fetchone()
    if not row:
        context["reason"] = "taxon_description_missing"
        return False
    if isinstance(row, sqlite3.Row):
        context["species_candidate"] = _clean_taxon(row["taxon_name"]) or species
    else:
        context["species_candidate"] = _clean_taxon(row[0]) or species
    context["link_mode"] = "taxon_match_not_image_provenance"
    context["pdf_file_id"] = None
    context["figure_id"] = None
    context["pdf_file"] = ""
    context["pdf_file_path"] = ""
    return True


def _record_from_row(row: sqlite3.Row, *, db_path: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _as_int(row["id"]),
        "pdf_file_id": _as_int(row["pdf_file_id"]),
        "file_name": str(row["file_name"] or ""),
        "file_path": str(row["file_path"] or ""),
        "file_hash": str(row["file_hash"] or ""),
        "taxon_name": str(row["taxon_name"] or ""),
        "caste_or_stage": str(row["caste_or_stage"] or ""),
        "part_key": str(row["part_key"] or ""),
        "part_label": str(row["part_label"] or ""),
        "description_text": str(row["description_text"] or ""),
        "source_pages": _json_list(row["source_pages"]),
        "source_block_refs": _json_list(row["source_block_refs"]),
        "source_blocks": _json_list(row["source_blocks"]),
        "model_used": str(row["model_used"] or ""),
        "confidence": float(row["confidence"] or 0.0),
        "review_status": str(row["review_status"] or ""),
        "created_at": str(row["created_at"] or ""),
        "source_db": os.path.abspath(db_path),
        "context": dict(context),
    }


def _text_block_record_from_row(row: sqlite3.Row, *, db_path: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _as_int(row["id"]),
        "pdf_file_id": _as_int(row["pdf_file_id"]),
        "file_name": str(row["file_name"] or ""),
        "file_path": str(row["file_path"] or ""),
        "file_hash": str(row["file_hash"] or ""),
        "block_ref": str(row["block_ref"] or ""),
        "page_number": _as_int(row["page_number"]),
        "block_index": _as_int(row["block_index"]),
        "section_hint": str(row["section_hint"] or ""),
        "text_type": str(row["text_type"] or ""),
        "text_content": str(row["text_content"] or ""),
        "llm_role": str(row["llm_role"] or ""),
        "llm_taxon_name": str(row["llm_taxon_name"] or ""),
        "llm_confidence": float(row["llm_confidence"] or 0.0),
        "model_used": str(row["model_used"] or ""),
        "created_at": str(row["created_at"] or ""),
        "source_db": os.path.abspath(db_path),
        "context": dict(context),
    }


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        payload = json.loads(value)
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _clean_taxon(value: Any) -> str:
    return str(value or "").strip()


def _as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result
