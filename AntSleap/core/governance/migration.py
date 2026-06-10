import copy
import importlib.util
import json
import os
from datetime import datetime, timezone
from typing import Any

try:
    from .view_resolver import resolve_view
except ImportError:
    _resolver_path = os.path.join(os.path.dirname(__file__), "view_resolver.py")
    _resolver_spec = importlib.util.spec_from_file_location(
        "view_resolver_runtime", _resolver_path
    )
    if _resolver_spec is None or _resolver_spec.loader is None:
        raise RuntimeError(f"Unable to load resolver module from: {_resolver_path}")
    _resolver_module = importlib.util.module_from_spec(_resolver_spec)
    _resolver_spec.loader.exec_module(_resolver_module)
    resolve_view = getattr(_resolver_module, "resolve_view")


SCHEMA_VERSION = "v2"


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _load_json_with_repair(path: str) -> tuple[dict[str, Any], bool]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("Input project JSON must be an object.")
        return payload, False
    except json.JSONDecodeError:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()

        last_brace = content.rfind("}")
        if last_brace < 0:
            raise

        fixed = content[: last_brace + 1]
        missing_closes = fixed.count("{") - fixed.count("}")
        if missing_closes > 0:
            fixed += "}" * missing_closes

        payload = json.loads(fixed)
        if not isinstance(payload, dict):
            raise ValueError("Input project JSON must be an object after repair.")
        return payload, True


def migrate_project_views(
    input_path: str,
    output_path: str,
    report_path: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input project not found: {input_path}")

    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}. Use overwrite=True to replace it."
        )

    source_data, input_repaired = _load_json_with_repair(input_path)

    migrated_data: dict[str, Any] = copy.deepcopy(source_data)
    migrated_data["schema_version"] = SCHEMA_VERSION

    labels = migrated_data.get("labels", {})
    if not isinstance(labels, dict):
        raise ValueError("Input project JSON field 'labels' must be an object.")

    resolved = 0
    unknown = 0
    conflicts = 0
    total = 0
    counts_by_view: dict[str, int] = {
        "lateral": 0,
        "dorsal": 0,
        "head_frontal": 0,
        "unknown": 0,
    }

    conflict_ids: list[str] = []
    unknown_ids: list[str] = []

    for label_key, label_data in labels.items():
        if not isinstance(label_data, dict):
            continue

        total += 1
        descriptions = label_data.get("descriptions", {})
        description_blob = ""
        if isinstance(descriptions, dict):
            description_blob = " ".join(str(value) for value in descriptions.values())

        infer_text = f"{label_key} {label_data.get('genus', '')} {description_blob}"
        resolved_view = resolve_view(infer_text)
        view = str(resolved_view.get("view", "unknown"))
        reason = str(resolved_view.get("resolution_reason", "no_signal"))
        confidence = float(resolved_view.get("view_confidence", 0.0))

        label_data["view"] = view
        label_data["view_confidence"] = confidence
        label_data["resolution_reason"] = reason

        if view in counts_by_view:
            counts_by_view[view] += 1

        if reason.startswith("conflict:"):
            conflicts += 1
            conflict_ids.append(str(label_key))
        elif view == "unknown":
            unknown += 1
            unknown_ids.append(str(label_key))
        else:
            resolved += 1

    timestamp = datetime.now(timezone.utc).isoformat()
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "input_path": input_path,
        "output_path": output_path,
        "total": total,
        "resolved": resolved,
        "unknown": unknown,
        "conflicts": conflicts,
        "counts_by_view": counts_by_view,
        "unknown_ids": unknown_ids,
        "conflict_ids": conflict_ids,
        "created_at": timestamp,
        "input_repaired": input_repaired,
    }

    report["totals_match"] = (resolved + unknown + conflicts) == total

    migrated_data["migration"] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": timestamp,
        "input_repaired": input_repaired,
        "report_path": report_path,
        "summary": {
            "total": total,
            "resolved": resolved,
            "unknown": unknown,
            "conflicts": conflicts,
        },
    }

    _ensure_parent_dir(output_path)
    _ensure_parent_dir(report_path)

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(migrated_data, handle, ensure_ascii=False, indent=2)

    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    return report
