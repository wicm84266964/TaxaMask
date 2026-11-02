"""Only reviewed PDF materials may cross into the instance workbench."""
import hashlib
import sqlite3
from pathlib import Path

from .governance.candidate_bridge import export_pdf_candidates
from .instance_project import uid
from .safe_io import atomic_write_json


def reviewed_candidates(database):
    database = Path(database).resolve()
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT source_table,record_id FROM figure_human_reviews WHERE human_status='import_ready'").fetchall()
    allowed = set(rows)
    payload = export_pdf_candidates(str(database))
    return [c for c in payload["candidates"] if (c["source_ref"]["table"], c["source_ref"]["row_id"]) in allowed]


def import_reviewed_materials(project, database, candidates):
    allowed = {c["candidate_stable_id"]: c for c in reviewed_candidates(database)}
    report = {"imported": [], "skipped": [], "errors": []}
    for requested in candidates:
        key = requested["candidate_stable_id"]
        if key not in allowed:
            report["skipped"].append({"candidate_id": key, "reason": "复核状态已变化"})
            continue
        candidate = allowed[key]
        path = Path(candidate["image_path"])
        if not path.is_absolute():
            path = Path(database).resolve().parent / path
        source = candidate.get("pdf_file_path") or candidate.get("pdf_file") or str(candidate["pdf_id"])
        group = "pdf_" + hashlib.sha256(str(source).encode()).hexdigest()
        created, errors = project.import_images([path], source_group=group, provenance=candidate)
        report["imported"].extend(created)
        report["errors"].extend(errors)
        if not created and not errors:
            report["skipped"].append({"candidate_id": key, "reason": "图像已存在"})
    destination = project.root / "imports" / uid("materials")
    destination.mkdir(parents=True)
    atomic_write_json(destination / "report.json", report)
    return destination, report
