import argparse
import json
import os
import sys
from typing import Any


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
ANTSLEAP_ROOT = os.path.join(REPO_ROOT, "AntSleap")
if ANTSLEAP_ROOT not in sys.path:
    sys.path.insert(0, ANTSLEAP_ROOT)

from core.governance.candidate_bridge import export_pdf_candidates  # noqa: E402
from core.project import ProjectManager  # noqa: E402


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str, payload: dict[str, Any]) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _records_from_payload(payload: Any, key: str) -> list[dict[str, Any]]:
    records = payload
    if isinstance(payload, dict):
        records = payload.get(key, payload.get("records", []))
    if not isinstance(records, list):
        return []
    return [item for item in records if isinstance(item, dict)]


def _resolve_image_path(raw_path: str, db_path: str = "") -> str:
    candidates: list[str] = []
    if raw_path:
        expanded = os.path.expanduser(os.path.expandvars(raw_path))
        candidates.append(expanded)
        if not os.path.isabs(expanded):
            candidates.append(os.path.join(REPO_ROOT, expanded))
            if db_path:
                candidates.append(os.path.join(os.path.dirname(os.path.abspath(db_path)), expanded))
    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if os.path.exists(normalized):
            return os.path.abspath(normalized)
    return os.path.abspath(os.path.normpath(candidates[0])) if candidates else ""


def _candidate_index(candidates_path: str, db_path: str) -> dict[str, dict[str, Any]]:
    if candidates_path:
        payload = _load_json(candidates_path)
    elif db_path:
        payload = export_pdf_candidates(os.path.abspath(db_path), mode="candidate_only")
    else:
        raise ValueError("candidates_or_db_required")

    index: dict[str, dict[str, Any]] = {}
    for candidate in _records_from_payload(payload, "candidates"):
        for key in ("candidate_id", "candidate_stable_id"):
            value = candidate.get(key)
            if isinstance(value, str) and value.strip():
                index[value.strip()] = candidate
    return index


def _allowed_candidate_ids(routing_path: str, buckets: set[str]) -> tuple[set[str], dict[str, dict[str, Any]]]:
    payload = _load_json(routing_path)
    decisions = _records_from_payload(payload, "decisions")
    allowed: set[str] = set()
    decision_index: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        candidate_id = str(decision.get("candidate_id", "") or "").strip()
        if not candidate_id:
            continue
        decision_index[candidate_id] = decision
        if str(decision.get("bucket", "") or "") in buckets:
            allowed.add(candidate_id)
    return allowed, decision_index


def _build_provenance(candidate: dict[str, Any], decision: dict[str, Any], db_path: str) -> dict[str, Any]:
    source_ref = candidate.get("source_ref", {})
    if not isinstance(source_ref, dict):
        source_ref = {}
    return {
        "schema_version": "formica-image-provenance-v1",
        "source_type": "pdf_candidate",
        "candidate_id": str(candidate.get("candidate_id", "") or ""),
        "candidate_stable_id": str(candidate.get("candidate_stable_id", "") or ""),
        "source_db": os.path.abspath(db_path) if db_path else str(source_ref.get("db_path", "") or ""),
        "source_ref": source_ref,
        "pdf_id": candidate.get("pdf_id"),
        "pdf_file": str(candidate.get("pdf_file", "") or ""),
        "pdf_file_path": str(candidate.get("pdf_file_path", "") or ""),
        "page_number": candidate.get("page_number"),
        "figure_index": candidate.get("image_id"),
        "image_file_name": str(candidate.get("image_file_name", "") or ""),
        "species_candidate": str(candidate.get("species_candidate", "") or ""),
        "review_status": str(candidate.get("review_status", "") or ""),
        "multimodal_review_mode": str(candidate.get("multimodal_review_mode", "") or ""),
        "multimodal_model_used": str(candidate.get("multimodal_model_used", "") or ""),
        "routing": {
            "bucket": str(decision.get("bucket", "") or ""),
            "view": str(decision.get("view", "") or ""),
            "confidence": decision.get("confidence"),
            "risk_tier": str(decision.get("risk_tier", "") or ""),
            "route_reasons": decision.get("route_reasons", []),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import routed PDF candidates into a Formica-Flow project JSON.")
    parser.add_argument("--project", required=True, help="Input project JSON.")
    parser.add_argument("--out", required=True, help="Output project JSON.")
    parser.add_argument("--routing", required=True, help="Routing decisions JSON.")
    parser.add_argument("--candidates", default="", help="Candidate artifact JSON. If omitted, --db is used.")
    parser.add_argument("--db", default="", help="PDF extraction DB used when --candidates is omitted.")
    parser.add_argument("--buckets", default="Core-2", help="Comma-separated routing buckets to import.")
    parser.add_argument("--status", default="needs_review", help="Project label status for imported candidate images.")
    parser.add_argument("--manifest", default="", help="Optional import manifest JSON path.")
    args = parser.parse_args()

    project_path = os.path.abspath(args.project)
    out_project = os.path.abspath(args.out)
    routing_path = os.path.abspath(args.routing)
    candidates_path = os.path.abspath(args.candidates) if args.candidates else ""
    db_path = os.path.abspath(args.db) if args.db else ""
    manifest_path = os.path.abspath(args.manifest) if args.manifest else os.path.splitext(out_project)[0] + "_import_manifest.json"
    buckets = {item.strip() for item in str(args.buckets).split(",") if item.strip()}
    import_status = str(args.status or "needs_review").strip() or "needs_review"
    os.makedirs(os.path.dirname(out_project) or os.getcwd(), exist_ok=True)

    allowed_ids, decision_index = _allowed_candidate_ids(routing_path, buckets)
    candidates = _candidate_index(candidates_path, db_path)

    manager = ProjectManager()
    manager.load_project(project_path)
    manager.current_project_path = out_project

    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    existing_images = set(manager.project_data.get("images", []))

    for candidate_id in sorted(allowed_ids):
        candidate = candidates.get(candidate_id)
        if candidate is None:
            skipped.append({"candidate_id": candidate_id, "reason": "candidate_not_found"})
            continue
        image_path = _resolve_image_path(str(candidate.get("image_path", "") or ""), db_path)
        if not image_path or not os.path.exists(image_path):
            skipped.append({"candidate_id": candidate_id, "reason": "image_not_found", "image_path": image_path})
            continue

        if image_path not in existing_images:
            manager.add_images([image_path])
            existing_images.add(image_path)
        manager.project_data.setdefault("labels", {}).setdefault(
            image_path,
            {"parts": {}, "status": import_status, "genus": "Unknown", "descriptions": {}},
        )
        manager.project_data["labels"][image_path]["status"] = import_status

        provenance = _build_provenance(candidate, decision_index.get(candidate_id, {}), db_path)
        manager.set_image_provenance(image_path, provenance, save=False)
        imported.append({"candidate_id": candidate_id, "image_path": image_path, "provenance": provenance})

    manager.save_project()

    manifest = {
        "schema_version": "formica-candidate-import-manifest-v1",
        "project_input": project_path,
        "project_output": out_project,
        "routing_path": routing_path,
        "candidates_path": candidates_path,
        "db_path": db_path,
        "buckets": sorted(buckets),
        "import_status": import_status,
        "allowed_candidate_count": len(allowed_ids),
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "imported": imported,
        "skipped": skipped,
    }
    _write_json(manifest_path, manifest)

    print(f"imported_count={len(imported)}")
    print(f"skipped_count={len(skipped)}")
    print(f"project_output={out_project}")
    print(f"manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
