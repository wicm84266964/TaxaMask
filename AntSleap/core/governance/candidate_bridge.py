import hashlib
import json
import os
import sqlite3
from typing import Any


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _stable_candidate_id(
    pdf_file_path: str,
    page_number: int,
    image_file_name: str,
    image_index: int,
) -> str:
    base = (
        f"{str(pdf_file_path).strip().lower()}|"
        f"{int(page_number)}|"
        f"{str(image_file_name).strip().lower()}|"
        f"{int(image_index)}"
    )
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]
    return f"cand_{digest}"


def export_pdf_candidates(db_path: str, mode: str = "candidate_only") -> dict[str, Any]:
    if mode != "candidate_only":
        raise ValueError("bridge_mode_not_allowed")

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"db_not_found:{db_path}")

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='figure_records'")
        has_v2_table = cursor.fetchone() is not None
        if has_v2_table:
            cursor.execute(
                """
                SELECT
                    f.id,
                    f.pdf_file_id,
                    f.page_number,
                    f.figure_index,
                    f.image_file_path,
                    f.image_file_name,
                    f.final_confidence,
                    f.final_confidence,
                    0.0,
                    f.species_confidence,
                    f.accepted,
                    p.file_name,
                    p.file_path,
                    f.species_candidate,
                    f.review_status,
                    f.category,
                    f.multimodal_review_mode,
                    f.multimodal_model_used
                FROM figure_records f
                LEFT JOIN pdf_files p ON p.id = f.pdf_file_id
                ORDER BY f.pdf_file_id, f.page_number, f.figure_index, f.id
                """
            )
        else:
            cursor.execute(
                """
                SELECT
                    i.id,
                    i.pdf_file_id,
                    i.page_number,
                    i.image_index,
                    i.image_file_path,
                    i.image_file_name,
                    i.final_confidence,
                    i.combined_relevance_score,
                    i.text_image_match_score,
                    i.confidence_score,
                    i.is_taxonomic,
                    p.file_name,
                    p.file_path,
                    '' AS species_candidate,
                    'legacy' AS review_status,
                    '' AS category,
                    'legacy' AS multimodal_review_mode,
                    '' AS multimodal_model_used
                FROM images i
                LEFT JOIN pdf_files p ON p.id = i.pdf_file_id
                ORDER BY i.pdf_file_id, i.page_number, i.image_index, i.id
                """
            )
        rows = cursor.fetchall()
    finally:
        connection.close()

    candidates: list[dict[str, Any]] = []
    for row in rows:
        (
            image_id,
            pdf_file_id,
            page_number,
            image_index,
            image_file_path,
            image_file_name,
            final_confidence,
            combined_relevance_score,
            text_image_match_score,
            confidence_score,
            is_taxonomic,
            pdf_file_name,
            pdf_file_path,
            species_candidate,
            review_status,
            category,
            multimodal_review_mode,
            multimodal_model_used,
        ) = row

        source_table = "figure_records" if has_v2_table else "images"

        candidate_id = f"pdf{int(pdf_file_id or 0)}_page{int(page_number or 0)}_img{int(image_index or 0)}"
        candidate_stable_id = _stable_candidate_id(
            str(pdf_file_path or ""),
            int(page_number or 0),
            str(image_file_name or ""),
            int(image_index or 0),
        )
        candidates.append(
            {
                "candidate_id": candidate_id,
                "candidate_stable_id": candidate_stable_id,
                "image_id": int(image_id),
                "pdf_id": int(pdf_file_id or 0),
                "pdf_file": str(pdf_file_name or ""),
                "pdf_file_path": str(pdf_file_path or ""),
                "page_number": int(page_number or 0),
                "image_path": str(image_file_path or ""),
                "image_file_name": str(image_file_name or ""),
                "source_type": "pdf_extractor_db",
                "source_ref": {
                    "db_path": db_path,
                    "table": source_table,
                    "row_id": int(image_id),
                },
                "confidence": {
                    "final_confidence": _as_float(final_confidence),
                    "combined_relevance_score": _as_float(combined_relevance_score),
                    "text_image_match_score": _as_float(text_image_match_score),
                    "confidence_score": _as_float(confidence_score),
                },
                "is_taxonomic": bool(is_taxonomic),
                "species_candidate": str(species_candidate or ""),
                "review_status": str(review_status or ""),
                "category": str(category or ""),
                "multimodal_review_mode": str(multimodal_review_mode or ""),
                "multimodal_model_used": str(multimodal_model_used or ""),
            }
        )

    return {
        "schema_version": "core2-candidate-bridge-v1",
        "mode": mode,
        "source_db": db_path,
        "total_candidates": len(candidates),
        "candidates": candidates,
    }


def save_candidate_artifact(artifact: dict[str, Any], output_path: str) -> None:
    _ensure_parent(output_path)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(artifact, handle, ensure_ascii=False, indent=2)
