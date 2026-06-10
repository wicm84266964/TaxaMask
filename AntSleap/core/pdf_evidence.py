import json
import os
from datetime import datetime


PDF_EVIDENCE_INDEX_SCHEMA_VERSION = "taxamask_pdf_evidence_index_v1"


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_evidence_record(record):
    if not isinstance(record, dict):
        raise ValueError("pdf_evidence_record_not_object")
    source_pdf = str(record.get("source_pdf", "") or "").strip()
    evidence_id = str(record.get("evidence_id", "") or "").strip()
    if not evidence_id:
        base = os.path.splitext(os.path.basename(source_pdf))[0] or "pdf_evidence"
        page = str(record.get("page", "") or "").strip()
        specimen = str(record.get("specimen_id", "") or "").strip()
        evidence_id = "_".join(item for item in [base, specimen, page] if item)
    return {
        "evidence_id": evidence_id,
        "source_pdf": source_pdf,
        "page": record.get("page", None),
        "caption": str(record.get("caption", "") or ""),
        "specimen_id": str(record.get("specimen_id", "") or ""),
        "metadata_ref": str(record.get("metadata_ref", "") or ""),
        "candidate_path": str(record.get("candidate_path", "") or ""),
        "notes": str(record.get("notes", "") or ""),
        "provenance": dict(record.get("provenance", {}) if isinstance(record.get("provenance", {}), dict) else {}),
    }


def create_pdf_evidence_index(records=None):
    return {
        "schema_version": PDF_EVIDENCE_INDEX_SCHEMA_VERSION,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "records": [normalize_evidence_record(item) for item in (records or [])],
    }


def read_pdf_evidence_index(path):
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("pdf_evidence_index_not_object")
    if payload.get("schema_version") != PDF_EVIDENCE_INDEX_SCHEMA_VERSION:
        raise ValueError(f"unsupported_pdf_evidence_schema:{payload.get('schema_version')}")
    payload["records"] = [normalize_evidence_record(item) for item in payload.get("records", [])]
    return payload


def write_pdf_evidence_index(path, payload):
    clean = create_pdf_evidence_index((payload or {}).get("records", []) if isinstance(payload, dict) else [])
    if isinstance(payload, dict):
        clean["created_at"] = payload.get("created_at", clean["created_at"])
    clean["updated_at"] = _now_iso()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(clean, handle, ensure_ascii=False, indent=2)
    return clean


def add_pdf_evidence_record(index_path, record):
    if os.path.exists(index_path):
        payload = read_pdf_evidence_index(index_path)
    else:
        payload = create_pdf_evidence_index()
    clean_record = normalize_evidence_record(record)
    records = [item for item in payload.get("records", []) if item.get("evidence_id") != clean_record["evidence_id"]]
    records.append(clean_record)
    payload["records"] = records
    return write_pdf_evidence_index(index_path, payload)
