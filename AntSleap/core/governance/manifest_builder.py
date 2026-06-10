import importlib.util
import json
import os
from typing import Any


def _load_callable(module_filename: str, callable_name: str):
    module_path = os.path.join(os.path.dirname(__file__), module_filename)
    spec = importlib.util.spec_from_file_location(
        f"{module_filename}_runtime", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, callable_name)


resolve_view = _load_callable("view_resolver.py", "resolve_view")
load_and_validate_policy = _load_callable("policy_loader.py", "load_and_validate_policy")


def _load_json_with_repair(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("Project JSON root must be an object.")
        return payload
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
            raise ValueError("Project JSON root must be an object after repair.")
        return payload


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def build_train_manifest(project_path: str, policy_path: str) -> dict[str, Any]:
    policy_result = load_and_validate_policy(policy_path)
    if not bool(policy_result.get("valid", False)):
        first_error = "policy_validation_failed"
        errors = policy_result.get("errors", [])
        if isinstance(errors, list) and errors:
            first_error = str(errors[0].get("message", first_error))
        raise ValueError(first_error)

    policy = policy_result.get("policy", {})
    target_views = set(policy.get("target_views", []))
    excluded_training_views = set(policy.get("excluded_training_views", []))

    project_data = _load_json_with_repair(project_path)
    labels = project_data.get("labels", {})
    if not isinstance(labels, dict):
        raise ValueError("Project field 'labels' must be an object.")

    records: list[dict[str, Any]] = []

    for image_path, label_data in labels.items():
        if not isinstance(label_data, dict):
            continue
        parts = label_data.get("parts", {})
        if not isinstance(parts, dict) or len(parts) == 0:
            continue

        explicit_view = label_data.get("view")
        if isinstance(explicit_view, str) and explicit_view.strip():
            view = explicit_view.strip()
            view_source = "label:view"
        else:
            descriptions = label_data.get("descriptions", {})
            context_blob = ""
            if isinstance(descriptions, dict):
                context_blob = " ".join(str(value) for value in descriptions.values())
            resolved = resolve_view(str(image_path), context_blob)
            view = str(resolved.get("view", "unknown")).strip() or "unknown"
            view_source = str(resolved.get("resolution_reason", "resolver:no_signal"))

        if view in excluded_training_views:
            include_in_core2_train = False
            route_reason = f"excluded_training_view:{view}"
        elif view == "unknown":
            include_in_core2_train = False
            route_reason = "excluded_unknown_view"
        elif view not in target_views:
            include_in_core2_train = False
            route_reason = f"excluded_non_target_view:{view}"
        else:
            include_in_core2_train = True
            route_reason = "core2_target_view"

        records.append(
            {
                "sample_id": str(image_path),
                "image_path": str(image_path),
                "view": view,
                "view_source": view_source,
                "route_reason": route_reason,
                "include_in_core2_train": include_in_core2_train,
            }
        )

    records.sort(key=lambda item: item["sample_id"])
    core2_train = [item for item in records if item["include_in_core2_train"]]
    excluded = [item for item in records if not item["include_in_core2_train"]]

    manifest = {
        "schema_version": "v2",
        "policy_version": str(policy.get("policy_version", "")),
        "project_path": project_path,
        "target_views": sorted(target_views),
        "excluded_training_views": sorted(excluded_training_views),
        "summary": {
            "total_records": len(records),
            "core2_train_count": len(core2_train),
            "excluded_count": len(excluded),
        },
        "records": records,
        "core2_train": core2_train,
        "excluded": excluded,
    }
    return manifest


def save_manifest(manifest: dict[str, Any], output_path: str) -> None:
    _ensure_parent(output_path)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
