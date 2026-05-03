import re
from typing import Any


def normalize_sample_id(sample_id: str) -> str:
    normalized = str(sample_id).replace("\\", "/").lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def derive_group_key(sample_id: str) -> str:
    key = normalize_sample_id(sample_id)
    key = re.sub(r"_view_\d+", "", key)
    key = re.sub(r"view\s*\d+", "", key)
    key = re.sub(r"pdf_\d+_page_\d+_img_\d+", "pdf_page_image", key)
    key = re.sub(r"\s+", " ", key).strip()
    return key


def detect_group_leakage(
    train_entries: list[dict[str, Any]],
    val_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    train_map: dict[str, list[str]] = {}
    val_map: dict[str, list[str]] = {}

    for entry in train_entries:
        sample_id = str(entry.get("sample_id", ""))
        if not sample_id:
            continue
        group_key = derive_group_key(sample_id)
        train_map.setdefault(group_key, []).append(sample_id)

    for entry in val_entries:
        sample_id = str(entry.get("sample_id", ""))
        if not sample_id:
            continue
        group_key = derive_group_key(sample_id)
        val_map.setdefault(group_key, []).append(sample_id)

    collisions: list[dict[str, Any]] = []
    for group_key in sorted(set(train_map.keys()) & set(val_map.keys())):
        collisions.append(
            {
                "group_key": group_key,
                "train_samples": sorted(train_map[group_key]),
                "val_samples": sorted(val_map[group_key]),
            }
        )

    return collisions
