import json
from typing import Any


def _load_records(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    records: Any = payload
    if isinstance(payload, dict):
        if isinstance(payload.get("decisions"), list):
            records = payload.get("decisions")
        elif isinstance(payload.get("candidates"), list):
            records = payload.get("candidates")
        elif isinstance(payload.get("records"), list):
            records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError("candidate_records_not_list")

    return [item for item in records if isinstance(item, dict)]


def check_candidate_dedup(input_path: str) -> dict[str, Any]:
    records = _load_records(input_path)

    seen: set[str] = set()
    duplicate_ids: set[str] = set()
    collected_ids: list[str] = []

    for record in records:
        candidate_id = record.get("candidate_stable_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            candidate_id = record.get("candidate_id")

        if not isinstance(candidate_id, str) or not candidate_id.strip():
            continue

        normalized = candidate_id.strip()
        collected_ids.append(normalized)
        if normalized in seen:
            duplicate_ids.add(normalized)
        else:
            seen.add(normalized)

    report = {
        "input_path": input_path,
        "total_records": len(records),
        "id_count": len(collected_ids),
        "unique_id_count": len(seen),
        "duplicate_count": len(duplicate_ids),
        "duplicate_ids": sorted(duplicate_ids),
    }
    return report


def compare_candidate_id_sets(path_a: str, path_b: str) -> dict[str, Any]:
    ids_a = {
        str(item.get("candidate_stable_id") or item.get("candidate_id"))
        for item in _load_records(path_a)
        if isinstance(item.get("candidate_stable_id") or item.get("candidate_id"), str)
    }
    ids_b = {
        str(item.get("candidate_stable_id") or item.get("candidate_id"))
        for item in _load_records(path_b)
        if isinstance(item.get("candidate_stable_id") or item.get("candidate_id"), str)
    }

    return {
        "path_a": path_a,
        "path_b": path_b,
        "count_a": len(ids_a),
        "count_b": len(ids_b),
        "same_id_set": ids_a == ids_b,
        "only_in_a": sorted(ids_a - ids_b),
        "only_in_b": sorted(ids_b - ids_a),
    }
