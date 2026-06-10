import json
import os
from typing import Any


def _normalize_path(path: str) -> str:
    return os.path.normpath(str(path)).replace("\\", "/").lower().strip()


def _candidate_keys(path: str, project_dir: str | None) -> list[str]:
    raw = str(path).strip()
    if not raw:
        return []

    candidates: list[str] = [
        _normalize_path(raw),
        _normalize_path(os.path.abspath(raw)),
    ]

    if project_dir:
        candidates.append(_normalize_path(os.path.abspath(os.path.join(project_dir, raw))))

    unique: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if item and item not in seen:
            unique.append(item)
            seen.add(item)
    return unique


def _resolve_existing_path(path: str, project_path: str | None) -> str:
    raw = str(path).strip()
    if not raw:
        raise ValueError("manifest_path_empty")

    candidates: list[str] = []
    if os.path.isabs(raw):
        candidates.append(raw)
    else:
        candidates.append(raw)

        if project_path:
            project_dir = os.path.dirname(os.path.abspath(project_path))
            candidates.append(os.path.join(project_dir, raw))

        repo_root = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        candidates.append(os.path.join(repo_root, raw))

    seen: set[str] = set()
    for candidate in candidates:
        absolute_candidate = os.path.abspath(candidate)
        key = _normalize_path(absolute_candidate)
        if key in seen:
            continue
        seen.add(key)
        if os.path.exists(absolute_candidate):
            return absolute_candidate

    raise FileNotFoundError(f"manifest_not_found:{raw}")


def _load_json_object(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"manifest_root_not_object:{path}")
    return payload


def _extract_sample_ids(entries: Any) -> list[str]:
    if not isinstance(entries, list):
        return []

    output: list[str] = []
    for entry in entries:
        sample_id: str | None = None
        if isinstance(entry, dict):
            value = entry.get("sample_id")
            if isinstance(value, str):
                sample_id = value
        elif isinstance(entry, str):
            sample_id = entry

        if isinstance(sample_id, str):
            normalized = sample_id.strip()
            if normalized:
                output.append(normalized)

    return output


def _extract_core2_ids(train_manifest: dict[str, Any]) -> set[str]:
    explicit_ids = _extract_sample_ids(train_manifest.get("core2_train"))
    if explicit_ids:
        return set(explicit_ids)

    derived: set[str] = set()
    records = train_manifest.get("records", [])
    if not isinstance(records, list):
        return derived

    for record in records:
        if not isinstance(record, dict):
            continue
        if not bool(record.get("include_in_core2_train", False)):
            continue
        sample_id = record.get("sample_id")
        if isinstance(sample_id, str) and sample_id.strip():
            derived.add(sample_id.strip())

    return derived


def _build_labeled_index(
    labeled_data: list[tuple[str, dict[str, Any]]],
    project_dir: str | None,
) -> dict[str, tuple[str, dict[str, Any]]]:
    index: dict[str, tuple[str, dict[str, Any]]] = {}
    for image_path, label_data in labeled_data:
        keys = _candidate_keys(image_path, project_dir)

        if project_dir:
            try:
                rel = os.path.relpath(os.path.abspath(image_path), project_dir)
                keys.extend(_candidate_keys(rel, project_dir))
            except ValueError:
                pass

        for key in keys:
            index.setdefault(key, (image_path, label_data))

    return index


def _select_partition(
    sample_ids: list[str],
    core2_ids: set[str],
    index: dict[str, tuple[str, dict[str, Any]]],
    project_dir: str | None,
    seen_images: set[str],
) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    selected: list[tuple[str, dict[str, Any]]] = []
    missing: list[str] = []

    for sample_id in sample_ids:
        if sample_id not in core2_ids:
            continue

        matched: tuple[str, dict[str, Any]] | None = None
        for key in _candidate_keys(sample_id, project_dir):
            candidate = index.get(key)
            if candidate is not None:
                matched = candidate
                break

        if matched is None:
            missing.append(sample_id)
            continue

        image_path = matched[0]
        image_key = _normalize_path(os.path.abspath(image_path))
        if image_key in seen_images:
            continue

        seen_images.add(image_key)
        selected.append(matched)

    return selected, missing


def load_training_split_from_manifests(
    labeled_data: list[tuple[str, dict[str, Any]]],
    split_manifest_path: str,
    train_manifest_path: str,
    project_path: str | None = None,
) -> dict[str, Any]:
    if not labeled_data:
        raise ValueError("no_labeled_data")

    split_path = _resolve_existing_path(split_manifest_path, project_path)
    train_path = _resolve_existing_path(train_manifest_path, project_path)

    split_manifest = _load_json_object(split_path)
    train_manifest = _load_json_object(train_path)

    split_train_ids = _extract_sample_ids(split_manifest.get("train"))
    split_val_ids = _extract_sample_ids(split_manifest.get("val"))
    if not split_train_ids and not split_val_ids:
        raise ValueError("split_manifest_missing_train_val")

    core2_ids = _extract_core2_ids(train_manifest)
    if not core2_ids:
        raise ValueError("train_manifest_missing_core2_ids")

    project_dir = None
    if project_path:
        project_dir = os.path.dirname(os.path.abspath(project_path))

    labeled_index = _build_labeled_index(labeled_data, project_dir)
    seen_images: set[str] = set()

    train_data, missing_train_ids = _select_partition(
        split_train_ids,
        core2_ids,
        labeled_index,
        project_dir,
        seen_images,
    )
    val_data, missing_val_ids = _select_partition(
        split_val_ids,
        core2_ids,
        labeled_index,
        project_dir,
        seen_images,
    )

    if not train_data:
        raise ValueError("manifest_split_empty_train")
    if not val_data:
        raise ValueError("manifest_split_empty_val")

    result = {
        "train": train_data,
        "val": val_data,
        "split_manifest_path": split_path,
        "train_manifest_path": train_path,
        "membership_fingerprint": str(split_manifest.get("membership_fingerprint", "")),
        "missing_train_ids": missing_train_ids,
        "missing_val_ids": missing_val_ids,
        "core2_reference_count": len(core2_ids),
    }
    return result
