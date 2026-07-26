import hashlib
import math
import os

from PIL import Image

from .training_truth import resolve_part_training_trust


def sanitize_polygon(points):
    clean_points = []
    if not isinstance(points, (list, tuple)):
        return clean_points

    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            x = float(point[0])
            y = float(point[1])
        except Exception:
            continue
        if not math.isfinite(x) or not math.isfinite(y):
            continue
        clean_points.append([x, y])

    return clean_points if len(clean_points) >= 3 else []


def sanitize_box(box):
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None

    try:
        clean_box = [float(value) for value in box]
    except Exception:
        return None

    if not all(math.isfinite(value) for value in clean_box):
        return None

    x1, y1, x2, y2 = clean_box
    if x2 <= x1 or y2 <= y1:
        return None
    return clean_box


def _normalize_size_pair(size_like):
    if not isinstance(size_like, (list, tuple)) or len(size_like) < 2:
        return None
    try:
        width = int(size_like[0])
        height = int(size_like[1])
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None
    return (width, height)


def format_size_pair(size_pair):
    normalized = _normalize_size_pair(size_pair)
    if normalized is None:
        return "unknown"
    return f"{normalized[0]}x{normalized[1]}"


def lower_locator_size_options(current_size_pair, max_options=4):
    normalized = _normalize_size_pair(current_size_pair)
    if normalized is None:
        return []

    width, height = normalized
    ratios = [0.85, 0.7, 0.55, 0.4]
    options = []
    seen = set()
    for ratio in ratios:
        next_width = max(64, int(round(width * ratio)))
        next_height = max(64, int(round(height * ratio)))
        candidate = (next_width, next_height)
        if candidate[0] >= width and candidate[1] >= height:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        options.append(candidate)
        if len(options) >= max_options:
            break
    return options


def stable_train_val_split(samples, val_ratio=0.2, sample_uid_by_path=None):
    uid_map = dict(sample_uid_by_path or {})

    def stable_key(item):
        path = str(item[0])
        identity = str(uid_map.get(path) or path)
        return hashlib.sha1(identity.encode("utf-8")).hexdigest()

    ordered = sorted(
        list(samples or []),
        key=stable_key,
    )
    if not ordered:
        return [], []
    if len(ordered) == 1:
        return ordered, ordered

    val_count = max(1, int(round(len(ordered) * float(val_ratio))))
    val_count = min(val_count, len(ordered) - 1)

    val_data = ordered[:val_count]
    train_data = ordered[val_count:]

    if not train_data:
        train_data = list(val_data)
    if not val_data:
        val_data = list(train_data)
    return train_data, val_data


def _format_size_counts(size_counts):
    ordered = sorted(size_counts.items(), key=lambda item: item[0])
    return ", ".join(f"{size} ({count})" for size, count in ordered) if ordered else "none"


def _count_part_coverage(samples, ordered_parts):
    counts = {part_name: 0 for part_name in (ordered_parts or [])}
    for _image_path, label_entry in list(samples or []):
        parts = label_entry.get("parts", {}) if isinstance(label_entry, dict) else {}
        for part_name in counts.keys():
            if part_name in parts and parts[part_name]:
                counts[part_name] += 1
    return counts


def build_training_preflight(
    images,
    labels_by_image,
    taxonomy,
    locator_scope,
    *,
    sample_uid_by_path=None,
):
    taxonomy_list = [str(part).strip() for part in (taxonomy or []) if str(part).strip()]
    locator_scope_list = [
        str(part).strip() for part in (locator_scope or []) if str(part).strip()
    ]
    taxonomy_set = set(taxonomy_list)
    locator_scope_set = set(locator_scope_list)

    locator_part_counts = {part: 0 for part in locator_scope_list}
    parts_part_counts = {part: 0 for part in taxonomy_list}

    locator_samples = []
    parts_samples = []
    warnings = []
    excluded_missing_images = []
    excluded_invalid_images = []
    excluded_zero_annotation_images = []
    excluded_invalid_annotation_images = []
    excluded_auto_draft_images = []
    excluded_untrusted_images = []
    excluded_untrusted_parts = []

    locator_exact_size_counts = {}

    for image_path in list(images or []):
        label_entry = labels_by_image.get(image_path, {}) if isinstance(labels_by_image, dict) else {}
        raw_parts = label_entry.get("parts", {}) if isinstance(label_entry, dict) else {}
        raw_boxes = label_entry.get("boxes", {}) if isinstance(label_entry, dict) else {}
        raw_descriptions = label_entry.get("descriptions", {}) if isinstance(label_entry, dict) else {}

        if not os.path.exists(image_path):
            excluded_missing_images.append(str(image_path))
            continue

        try:
            with Image.open(image_path) as image_ref:
                width, height = image_ref.size
        except Exception:
            excluded_invalid_images.append(str(image_path))
            continue

        valid_parts = {}
        valid_boxes = {}
        skipped_untrusted_parts = []
        for part_name, points in (raw_parts or {}).items():
            clean_part_name = str(part_name).strip()
            if clean_part_name not in taxonomy_set:
                continue
            trust = resolve_part_training_trust(label_entry, clean_part_name)
            if not trust.get("eligible"):
                detail = {
                    "image_path": str(image_path),
                    **trust,
                }
                skipped_untrusted_parts.append(detail)
                excluded_untrusted_parts.append(detail)
                continue

            clean_points = sanitize_polygon(points)
            if not clean_points:
                continue

            valid_parts[clean_part_name] = clean_points
            clean_box = sanitize_box((raw_boxes or {}).get(clean_part_name))
            if clean_box:
                valid_boxes[clean_part_name] = clean_box

        if not valid_parts:
            if skipped_untrusted_parts and raw_parts:
                excluded_untrusted_images.append(str(image_path))
                if any(
                    detail.get("reason")
                    in {
                        "legacy_auto_annotated_draft",
                        "legacy_confirmed_ai_has_auto_draft_marker",
                    }
                    for detail in skipped_untrusted_parts
                ):
                    excluded_auto_draft_images.append(str(image_path))
            elif raw_parts:
                excluded_invalid_annotation_images.append(str(image_path))
            else:
                excluded_zero_annotation_images.append(str(image_path))
            continue

        locator_valid_parts = {
            part_name: points
            for part_name, points in valid_parts.items()
            if part_name in locator_scope_set
        }
        taxonomy_valid_parts = {
            part_name: points
            for part_name, points in valid_parts.items()
            if part_name in taxonomy_set
        }

        if locator_valid_parts:
            locator_samples.append(
                (
                    image_path,
                    {
                        "parts": dict(locator_valid_parts),
                        "boxes": {
                            part_name: valid_boxes[part_name]
                            for part_name in locator_valid_parts.keys()
                            if part_name in valid_boxes
                        },
                    },
                )
            )
            exact_size_key = format_size_pair((int(width), int(height)))
            locator_exact_size_counts[exact_size_key] = locator_exact_size_counts.get(exact_size_key, 0) + 1

        if taxonomy_valid_parts:
            parts_samples.append(
                (
                    image_path,
                    {
                        "parts": dict(taxonomy_valid_parts),
                        "boxes": {
                            part_name: valid_boxes[part_name]
                            for part_name in taxonomy_valid_parts.keys()
                            if part_name in valid_boxes
                        },
                    },
                )
            )

        for part_name in locator_valid_parts.keys():
            locator_part_counts[part_name] = locator_part_counts.get(part_name, 0) + 1
        for part_name in taxonomy_valid_parts.keys():
            parts_part_counts[part_name] = parts_part_counts.get(part_name, 0) + 1

    selected_locator_size = None
    if locator_exact_size_counts:
        exact_pairs = [_normalize_size_pair(size_key.split("x")) for size_key in locator_exact_size_counts.keys()]
        exact_pairs = [pair for pair in exact_pairs if pair is not None]
        if exact_pairs:
            if len(exact_pairs) == 1:
                selected_locator_size = exact_pairs[0]
            else:
                selected_locator_size = min(exact_pairs, key=lambda pair: (pair[0] * pair[1], pair[0], pair[1]))

    mixed_native_resolutions = len(locator_exact_size_counts) > 1

    if excluded_missing_images:
        warnings.append(
            f"Excluded {len(excluded_missing_images)} image(s) missing on disk from training."
        )
    if excluded_invalid_images:
        warnings.append(
            f"Excluded {len(excluded_invalid_images)} unreadable image(s) from training."
        )
    if excluded_invalid_annotation_images:
        warnings.append(
            f"Excluded {len(excluded_invalid_annotation_images)} image(s) whose saved annotations were invalid."
        )
    if excluded_auto_draft_images:
        warnings.append(
            f"Excluded {len(excluded_auto_draft_images)} image(s) with only unreviewed Auto-Annotated drafts from training."
        )
    conflict_count = sum(
        1 for detail in excluded_untrusted_parts if detail.get("state") == "conflict"
    )
    draft_count = sum(
        1 for detail in excluded_untrusted_parts if detail.get("state") == "draft"
    )
    if draft_count:
        warnings.append(
            f"Excluded {draft_count} unconfirmed part annotation(s) from training."
        )
    if conflict_count:
        warnings.append(
            f"Excluded {conflict_count} part annotation(s) with conflicting trust metadata from training."
        )
    if excluded_zero_annotation_images:
        warnings.append(
            f"Excluded {len(excluded_zero_annotation_images)} zero-annotation image(s) from training."
        )

    if not locator_samples:
        warnings.append(
            "No locator-eligible images were found. The locator stage will be skipped."
        )
    elif len(locator_samples) == 1:
        warnings.append(
            "Only 1 locator-eligible image was found; training and validation will reuse the same image."
        )

    if not parts_samples:
        warnings.append(
            "No SAM/parts-eligible images were found. The SAM stage will be skipped."
        )
    elif len(parts_samples) == 1:
        warnings.append(
            "Only 1 SAM/parts-eligible image was found; training and validation will reuse the same image."
        )

    for part_name in locator_scope_list:
        if locator_part_counts.get(part_name, 0) <= 0:
            warnings.append(
                f"Locator coverage is 0 for '{part_name}', so that locator part will not be trained."
            )

    for part_name in taxonomy_list:
        if parts_part_counts.get(part_name, 0) <= 0:
            warnings.append(
                f"SAM/parts coverage is 0 for '{part_name}', so that part will not enter SAM training."
            )

    locator_train_data, locator_val_data = stable_train_val_split(
        locator_samples, sample_uid_by_path=sample_uid_by_path
    )
    parts_train_data, parts_val_data = stable_train_val_split(
        parts_samples, sample_uid_by_path=sample_uid_by_path
    )
    locator_train_part_counts = _count_part_coverage(locator_train_data, locator_scope_list)
    locator_val_part_counts = _count_part_coverage(locator_val_data, locator_scope_list)
    parts_train_part_counts = _count_part_coverage(parts_train_data, taxonomy_list)
    parts_val_part_counts = _count_part_coverage(parts_val_data, taxonomy_list)

    return {
        "taxonomy": list(taxonomy_list),
        "locator_scope": list(locator_scope_list),
        "locator_samples": locator_samples,
        "parts_samples": parts_samples,
        "locator_train_data": locator_train_data,
        "locator_val_data": locator_val_data,
        "parts_train_data": parts_train_data,
        "parts_val_data": parts_val_data,
        "locator_image_count": len(locator_samples),
        "parts_image_count": len(parts_samples),
        "locator_part_counts": locator_part_counts,
        "parts_part_counts": parts_part_counts,
        "locator_train_part_counts": locator_train_part_counts,
        "locator_val_part_counts": locator_val_part_counts,
        "parts_train_part_counts": parts_train_part_counts,
        "parts_val_part_counts": parts_val_part_counts,
        "selected_locator_size": selected_locator_size,
        "mixed_native_resolutions": mixed_native_resolutions,
        "locator_exact_size_counts": locator_exact_size_counts,
        "locator_size_summary": _format_size_counts(locator_exact_size_counts),
        "lower_locator_size_options": lower_locator_size_options(selected_locator_size)
        if selected_locator_size
        else [],
        "warnings": warnings,
        "excluded_missing_images": excluded_missing_images,
        "excluded_invalid_images": excluded_invalid_images,
        "excluded_zero_annotation_images": excluded_zero_annotation_images,
        "excluded_invalid_annotation_images": excluded_invalid_annotation_images,
        "excluded_auto_draft_images": excluded_auto_draft_images,
        "excluded_untrusted_images": excluded_untrusted_images,
        "excluded_untrusted_parts": excluded_untrusted_parts,
    }


def describe_part_coverage(part_counts, ordered_parts):
    return ", ".join(
        f"{part_name}={int(part_counts.get(part_name, 0))}" for part_name in (ordered_parts or [])
    )


def describe_training_preflight(preflight):
    locator_train_count = len(preflight.get("locator_train_data", []) or [])
    locator_val_count = len(preflight.get("locator_val_data", []) or [])
    parts_train_count = len(preflight.get("parts_train_data", []) or [])
    parts_val_count = len(preflight.get("parts_val_data", []) or [])

    lines = [
        f"Locator eligible images: total {int(preflight.get('locator_image_count', 0))} | train {locator_train_count} | val {locator_val_count}",
        f"SAM/parts eligible images: total {int(preflight.get('parts_image_count', 0))} | train {parts_train_count} | val {parts_val_count}",
    ]

    locator_size = _normalize_size_pair(preflight.get("selected_locator_size"))
    if locator_size:
        lines.append(f"Locator training size: {format_size_pair(locator_size)}")

    lines.append(
        f"Locator coverage total: {describe_part_coverage(preflight.get('locator_part_counts', {}), preflight.get('locator_scope', []))}"
    )
    lines.append(
        f"Locator coverage train: {describe_part_coverage(preflight.get('locator_train_part_counts', {}), preflight.get('locator_scope', []))}"
    )
    lines.append(
        f"Locator coverage val: {describe_part_coverage(preflight.get('locator_val_part_counts', {}), preflight.get('locator_scope', []))}"
    )
    lines.append(
        f"SAM coverage total: {describe_part_coverage(preflight.get('parts_part_counts', {}), preflight.get('taxonomy', []))}"
    )
    lines.append(
        f"SAM coverage train: {describe_part_coverage(preflight.get('parts_train_part_counts', {}), preflight.get('taxonomy', []))}"
    )
    lines.append(
        f"SAM coverage val: {describe_part_coverage(preflight.get('parts_val_part_counts', {}), preflight.get('taxonomy', []))}"
    )

    locator_size_summary = str(preflight.get("locator_size_summary", "none") or "none")
    if locator_size_summary != "none":
        lines.append(f"Eligible locator image sizes: {locator_size_summary}")

    warnings = list(preflight.get("warnings", []))
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in warnings)

    return "\n".join(lines)
