import hashlib
import importlib.util
import json
import os
import random
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
derive_group_key = _load_callable("grouping.py", "derive_group_key")


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


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _dataset_fingerprint(samples: list[dict[str, str]]) -> str:
    parts = [f"{item['sample_id']}|{item['view']}" for item in samples]
    payload = "\n".join(sorted(parts))
    return _hash_text(payload)


def _membership_fingerprint(
    train: list[dict[str, str]], val: list[dict[str, str]]
) -> str:
    parts = [f"train|{item['sample_id']}" for item in train] + [
        f"val|{item['sample_id']}" for item in val
    ]
    payload = "\n".join(sorted(parts))
    return _hash_text(payload)


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _collect_samples(project_data: dict[str, Any]) -> list[dict[str, str]]:
    labels = project_data.get("labels", {})
    if not isinstance(labels, dict):
        raise ValueError("Project field 'labels' must be an object.")

    samples: list[dict[str, str]] = []
    for image_path, label_data in labels.items():
        if not isinstance(label_data, dict):
            continue

        parts = label_data.get("parts", {})
        if not isinstance(parts, dict) or len(parts) == 0:
            continue

        explicit_view = label_data.get("view")
        if isinstance(explicit_view, str) and explicit_view.strip():
            view = explicit_view.strip()
            reason = "label:view"
        else:
            descriptions = label_data.get("descriptions", {})
            context_blob = ""
            if isinstance(descriptions, dict):
                context_blob = " ".join(str(value) for value in descriptions.values())
            resolved = resolve_view(str(image_path), context_blob)
            view = str(resolved.get("view", "")).strip()
            reason = str(resolved.get("resolution_reason", "no_signal"))

        if not view:
            raise ValueError(f"view_missing_for_split:{image_path}")

        samples.append(
            {
                "sample_id": str(image_path),
                "image_path": str(image_path),
                "view": view,
                "view_reason": reason,
                "group_key": derive_group_key(str(image_path)),
            }
        )

    samples.sort(key=lambda item: item["sample_id"])
    return samples


def build_split_manifest(
    project_path: str,
    seed: int,
    val_ratio: float = 0.2,
) -> dict[str, Any]:
    if not (0.0 < val_ratio < 1.0):
        raise ValueError("val_ratio must be between 0 and 1.")

    project_data = _load_json_with_repair(project_path)
    samples = _collect_samples(project_data)
    if not samples:
        raise ValueError("No labeled samples available for split.")

    groups: dict[str, list[dict[str, str]]] = {}
    for item in samples:
        groups.setdefault(item["view"], []).append(item)

    train: list[dict[str, str]] = []
    val: list[dict[str, str]] = []
    counts_by_view: dict[str, dict[str, int]] = {}

    def split_view_entries(
        entries: list[dict[str, str]],
        seed_token: str,
        ratio: float,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        grouped: dict[str, list[dict[str, str]]] = {}
        for entry in entries:
            grouped.setdefault(entry["group_key"], []).append(entry)

        total_count = len(entries)
        if total_count <= 1:
            return entries, []

        target_val = int(round(total_count * ratio))
        target_val = max(1, target_val)
        target_val = min(total_count - 1, target_val)

        group_keys = sorted(grouped.keys())
        rng = random.Random(seed_token)
        rng.shuffle(group_keys)

        val_group_keys: set[str] = set()
        val_count = 0
        for group_key in group_keys:
            if val_count >= target_val:
                break

            group_size = len(grouped[group_key])
            remaining_train_if_taken = total_count - (val_count + group_size)
            if remaining_train_if_taken < 1:
                continue

            val_group_keys.add(group_key)
            val_count += group_size

        if not val_group_keys:
            for group_key in sorted(group_keys, key=lambda key: len(grouped[key])):
                if total_count - len(grouped[group_key]) >= 1:
                    val_group_keys.add(group_key)
                    break

        view_val: list[dict[str, str]] = []
        view_train: list[dict[str, str]] = []
        for group_key, group_entries in grouped.items():
            if group_key in val_group_keys:
                view_val.extend(group_entries)
            else:
                view_train.extend(group_entries)

        view_train.sort(key=lambda item: item["sample_id"])
        view_val.sort(key=lambda item: item["sample_id"])
        return view_train, view_val

    for view in sorted(groups.keys()):
        entries = sorted(groups[view], key=lambda item: item["sample_id"])
        view_train, view_val = split_view_entries(entries, f"{seed}:{view}", val_ratio)

        val.extend(view_val)
        train.extend(view_train)

        counts_by_view[view] = {
            "total": len(entries),
            "train": len(view_train),
            "val": len(view_val),
        }

    train.sort(key=lambda item: item["sample_id"])
    val.sort(key=lambda item: item["sample_id"])

    manifest: dict[str, Any] = {
        "project_path": project_path,
        "seed": int(seed),
        "val_ratio": float(val_ratio),
        "total_samples": len(samples),
        "train_count": len(train),
        "val_count": len(val),
        "dataset_fingerprint": _dataset_fingerprint(samples),
        "membership_fingerprint": _membership_fingerprint(train, val),
        "counts_by_view": counts_by_view,
        "train": train,
        "val": val,
    }

    return manifest


def save_split_manifest(manifest: dict[str, Any], output_path: str) -> None:
    _ensure_parent(output_path)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
