import json
import os
import shutil
import time
from dataclasses import dataclass

from .project import (
    AUTO_BOX_REVIEW_DRAFT,
    AUTO_BOX_SOURCE_VLM,
    DEFAULT_CATEGORY_SUPERCATEGORY,
)
from .project_sqlite_schema import (
    PROJECT_2D_PROJECT_TYPE,
    create_2d_project_database,
    json_text,
)
from .safe_io import atomic_write_json
from .sqlite_storage import ensure_integrity_ok, write_project_manifest
from .path_identity import canonical_path


MIGRATION_REPORT_SCHEMA_VERSION = "taxamask-2d-json-to-sqlite-migration-v1"
DEFAULT_LEGACY_VLM_RUN_ID = "legacy_vlm_import"


@dataclass
class ProjectSQLiteMigrationResult:
    source_json_path: str
    database_path: str
    manifest_path: str
    report_path: str
    legacy_json_backup_path: str
    stats: dict
    integrity_check: list


def _timestamp():
    return time.strftime("%Y%m%d_%H%M%S")


def _fsync_directory(path):
    try:
        dir_fd = os.open(path or ".", os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def _remove_sqlite_files(path):
    base = os.path.abspath(str(path))
    for candidate in (base, f"{base}-wal", f"{base}-shm"):
        try:
            if os.path.exists(candidate):
                os.remove(candidate)
        except OSError:
            pass


def _sqlite_artifact_exists(path):
    base = os.path.abspath(str(path))
    return any(os.path.exists(candidate) for candidate in (base, f"{base}-wal", f"{base}-shm"))


def _same_file_path(left, right):
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(os.path.abspath(str(right)))


def default_sqlite_database_path(json_project_path):
    source = os.path.abspath(str(json_project_path))
    directory = os.path.dirname(source) or "."
    stem = os.path.splitext(os.path.basename(source))[0] or "project"
    return os.path.join(directory, f"{stem}.taxamask.sqlite")


def default_sqlite_manifest_path(json_project_path):
    source = os.path.abspath(str(json_project_path))
    directory = os.path.dirname(source) or "."
    stem = os.path.splitext(os.path.basename(source))[0] or "project"
    return os.path.join(directory, f"{stem}.sqlite_manifest.json")


def default_migration_report_path(json_project_path):
    source = os.path.abspath(str(json_project_path))
    directory = os.path.dirname(source) or "."
    stem = os.path.splitext(os.path.basename(source))[0] or "project"
    report_dir = os.path.join(directory, f"{stem}.migration_reports")
    return os.path.join(report_dir, f"{stem}.sqlite_migration_{_timestamp()}.json")


def _legacy_json_backup_path(json_project_path):
    source = os.path.abspath(str(json_project_path))
    directory = os.path.dirname(source) or "."
    filename = os.path.basename(source)
    stem, ext = os.path.splitext(filename)
    stem = stem or "project"
    ext = ext or ".json"
    backup_dir = os.path.join(directory, f"{stem}.legacy_json_backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, f"{stem}.{_timestamp()}{ext}.bak")
    suffix = 2
    while os.path.exists(backup_path):
        backup_path = os.path.join(backup_dir, f"{stem}.{_timestamp()}_{suffix}{ext}.bak")
        suffix += 1
    return backup_path


def _copy_legacy_json_backup(json_project_path):
    backup_path = _legacy_json_backup_path(json_project_path)
    tmp_path = f"{backup_path}.tmp"
    try:
        shutil.copy2(json_project_path, tmp_path)
        os.replace(tmp_path, backup_path)
        _fsync_directory(os.path.dirname(backup_path) or ".")
        return backup_path
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


def _stored_project_path(raw_path):
    text = str(raw_path or "").strip()
    if not text:
        return ""
    if os.path.isabs(text):
        return os.path.normpath(text)
    return os.path.normpath(text).replace("\\", "/")


def _absolute_identity(stored_path, project_dir):
    if not stored_path:
        return ""
    text = str(stored_path)
    if os.path.isabs(text):
        absolute = os.path.abspath(os.path.normpath(text))
    else:
        absolute = os.path.abspath(os.path.normpath(os.path.join(project_dir, text)))
    return os.path.normcase(os.path.normpath(absolute))


def _append_image_path(image_paths, path_by_identity, raw_path, project_dir):
    stored_path = _stored_project_path(raw_path)
    identity = _absolute_identity(stored_path, project_dir)
    if not stored_path or not identity:
        return ""
    if identity not in path_by_identity:
        path_by_identity[identity] = stored_path
        image_paths.append(stored_path)
    return path_by_identity[identity]


def _iter_mapping_keys(value):
    if not isinstance(value, dict):
        return []
    return list(value.keys())


def _build_image_paths(project_data, project_dir):
    image_paths = []
    path_by_identity = {}

    for raw_path in project_data.get("images", []) or []:
        _append_image_path(image_paths, path_by_identity, raw_path, project_dir)

    for key in ("labels", "scales", "image_provenance"):
        for raw_path in _iter_mapping_keys(project_data.get(key, {})):
            _append_image_path(image_paths, path_by_identity, raw_path, project_dir)

    image_groups = project_data.get("image_groups", {})
    custom_groups = image_groups.get("custom_groups", []) if isinstance(image_groups, dict) else []
    if isinstance(custom_groups, dict):
        custom_groups = [{"id": group_id, "name": group_name} for group_id, group_name in custom_groups.items()]
    for group in custom_groups if isinstance(custom_groups, list) else []:
        if not isinstance(group, dict):
            continue
        for raw_path in group.get("images", []) or []:
            _append_image_path(image_paths, path_by_identity, raw_path, project_dir)

    return image_paths, path_by_identity


def _stored_path_for_raw(raw_path, project_dir, path_by_identity):
    stored_path = _stored_project_path(raw_path)
    identity = _absolute_identity(stored_path, project_dir)
    return path_by_identity.get(identity, stored_path)


def _sanitize_dict(value):
    return dict(value) if isinstance(value, dict) else {}


def _sanitize_list(value):
    return list(value) if isinstance(value, list) else []


def _label_has_saved_content(label_data):
    if not isinstance(label_data, dict):
        return False
    for key in (
        "parts",
        "boxes",
        "auto_boxes",
        "auto_box_meta",
        "descriptions",
        "description_sources",
        "shrink_loose_boxes",
        "trajectories",
    ):
        if label_data.get(key):
            return True
    if str(label_data.get("status", "unlabeled") or "unlabeled") != "unlabeled":
        return True
    if str(label_data.get("genus", "Unknown") or "Unknown") not in ("", "Unknown"):
        return True
    if str(label_data.get("taxon", "Unknown") or "Unknown") not in ("", "Unknown"):
        return True
    if str(label_data.get("taxon_rank", "") or ""):
        return True
    taxon_metadata = label_data.get("taxon_metadata", {})
    return isinstance(taxon_metadata, dict) and bool(taxon_metadata)


def _label_status(label_data):
    if not isinstance(label_data, dict):
        return "unlabeled"
    status = str(label_data.get("status", "") or "").strip()
    if status:
        return status
    return "labeled" if label_data.get("parts") else "unlabeled"


def _clean_box(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        box = [float(item) for item in value]
    except Exception:
        return None
    if box[2] <= box[0] or box[3] <= box[1]:
        return None
    return box


def _clean_point(value):
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        return [float(value[0]), float(value[1])]
    except Exception:
        return None


def _looks_like_point(value):
    return _clean_point(value) is not None


def _polygon_from_points(points):
    clean = []
    for point in points if isinstance(points, list) else []:
        clean_point = _clean_point(point)
        if clean_point:
            clean.append(clean_point)
    return clean if len(clean) >= 3 else []


def _polygons_from_legacy_value(value):
    if not isinstance(value, list) or not value:
        return []
    if _looks_like_point(value[0]):
        polygon = _polygon_from_points(value)
        return [polygon] if polygon else []

    polygons = []
    for polygon_candidate in value:
        polygon = _polygon_from_points(polygon_candidate)
        if polygon:
            polygons.append(polygon)
    return polygons


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _confidence_from_meta(meta):
    if not isinstance(meta, dict):
        return 0.0
    value = meta.get("confidence", 0.0)
    if isinstance(value, dict):
        for key in ("final_confidence", "confidence", "score", "value"):
            if key in value:
                return _safe_float(value.get(key), 0.0)
        return 0.0
    return _safe_float(value, 0.0)


def _auto_box_run_id(source, meta):
    if not isinstance(meta, dict):
        meta = {}
    run_id = str(meta.get("source_run_id") or meta.get("run_id") or "").strip()
    if run_id:
        return run_id
    if source == AUTO_BOX_SOURCE_VLM:
        return DEFAULT_LEGACY_VLM_RUN_ID
    return ""


def _raw_response_ref(meta):
    if not isinstance(meta, dict):
        return ""
    return str(meta.get("raw_response_ref") or meta.get("report_path") or "").strip()


def _project_settings_payload(project_data, source_json_path):
    known = {
        "name",
        "images",
        "labels",
        "taxonomy",
        "locator_scope",
        "project_template",
        "category_supercategory",
        "taxon_label",
        "scales",
        "image_provenance",
        "image_groups",
        "vlm_preannotation",
        "blink_context_roi_parents",
        "parent_box_aspect_ratios",
        "model_profiles",
        "cascade_routes",
    }
    unknown_top_level = {
        key: value
        for key, value in project_data.items()
        if key not in known
    } if isinstance(project_data, dict) else {}
    return {
        "legacy_json_source": os.path.abspath(str(source_json_path)),
        "vlm_preannotation": _sanitize_dict(project_data.get("vlm_preannotation", {})),
        "blink_context_roi_parents": _sanitize_dict(project_data.get("blink_context_roi_parents", {})),
        "parent_box_aspect_ratios": _sanitize_dict(project_data.get("parent_box_aspect_ratios", {})),
        "image_groups": _sanitize_dict(project_data.get("image_groups", {})),
        "model_profiles": _sanitize_dict(project_data.get("model_profiles", {})),
        "cascade_routes": _sanitize_dict(project_data.get("cascade_routes", {})),
        "unknown_top_level": unknown_top_level,
    }


def _insert_project_settings(connection, project_data, source_json_path):
    taxonomy = _sanitize_list(project_data.get("taxonomy", []))
    locator_scope = _sanitize_list(project_data.get("locator_scope", []))
    settings = _project_settings_payload(project_data, source_json_path)
    taxonomy_part_count = 0
    connection.execute(
        """
        UPDATE projects
        SET name = ?,
            project_type = ?,
            taxonomy_json = ?,
            locator_scope_json = ?,
            project_template = ?,
            category_supercategory = ?,
            taxon_label = ?,
            settings_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
        """,
        (
            str(project_data.get("name") or "Untitled"),
            PROJECT_2D_PROJECT_TYPE,
            json_text(taxonomy),
            json_text(locator_scope),
            str(project_data.get("project_template") or ""),
            str(project_data.get("category_supercategory") or DEFAULT_CATEGORY_SUPERCATEGORY),
            str(project_data.get("taxon_label") or "Taxon"),
            json_text(settings),
        ),
    )
    for index, part_name in enumerate(taxonomy):
        clean_part = str(part_name or "").strip()
        if not clean_part:
            continue
        connection.execute(
            """
            INSERT OR IGNORE INTO taxonomy_parts (part_name, sort_order)
            VALUES (?, ?)
            """,
            (clean_part, index),
        )
        taxonomy_part_count += 1
    return taxonomy_part_count


def _insert_model_profiles(connection, model_profiles):
    profiles_payload = _sanitize_dict(model_profiles)
    active_id = str(profiles_payload.get("active_profile_id") or "").strip()
    profiles = profiles_payload.get("profiles", [])
    count = 0
    if isinstance(profiles, list):
        for index, profile in enumerate(profiles, start=1):
            if not isinstance(profile, dict):
                continue
            profile_id = str(profile.get("profile_id") or profile.get("id") or f"profile_{index}").strip()
            if not profile_id:
                continue
            connection.execute(
                """
                INSERT OR REPLACE INTO model_profiles (profile_id, profile_json, is_active)
                VALUES (?, ?, ?)
                """,
                (profile_id, json_text(profile), 1 if profile_id == active_id else 0),
            )
            count += 1
    elif profiles_payload:
        connection.execute(
            """
            INSERT OR REPLACE INTO model_profiles (profile_id, profile_json, is_active)
            VALUES (?, ?, ?)
            """,
            ("__legacy_model_profiles__", json_text(profiles_payload), 1),
        )
        count = 1
    return count


def _custom_groups(project_data):
    image_groups = project_data.get("image_groups", {})
    if not isinstance(image_groups, dict):
        return []
    groups = image_groups.get("custom_groups", [])
    if isinstance(groups, dict):
        groups = [{"id": group_id, "name": group_name} for group_id, group_name in groups.items()]
    return groups if isinstance(groups, list) else []


def _safe_group_id(value, fallback):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text).strip("_")
    return clean or fallback


def _insert_image_groups(connection, project_data):
    count = 0
    inserted_group_ids = set()
    for index, group in enumerate(_custom_groups(project_data), start=1):
        if not isinstance(group, dict):
            continue
        name = str(group.get("name") or "").strip()
        if not name:
            continue
        group_id = _safe_group_id(group.get("id"), f"custom_{index}")
        metadata = {key: value for key, value in group.items() if key not in {"id", "name", "images"}}
        connection.execute(
            """
            INSERT OR REPLACE INTO image_groups (id, name, sort_order, metadata_json)
            VALUES (?, ?, ?, ?)
            """,
            (group_id, name[:80], index, json_text(metadata)),
        )
        count += 1
        inserted_group_ids.add(group_id)
    return count, inserted_group_ids


def _insert_images(connection, image_paths, provenance_by_path, progress, stats):
    image_id_by_path = {}
    total = progress["total"]
    for image_path in image_paths:
        provenance = provenance_by_path.get(image_path, {})
        group_id = ""
        if isinstance(provenance, dict):
            group_id = str(provenance.get("manual_image_group") or "").strip()
        cursor = connection.execute(
            """
            INSERT INTO images (path, filename, group_id, status)
            VALUES (?, ?, ?, ?)
            """,
            (image_path, os.path.basename(image_path), group_id, "active"),
        )
        image_id_by_path[image_path] = int(cursor.lastrowid)
        progress["done"] += 1
        _emit_progress(progress["callback"], progress["done"], total, f"写入图片索引: {image_path}")
    stats["image_count"] = len(image_id_by_path)
    return image_id_by_path


def _insert_image_group_members(
    connection,
    project_data,
    image_id_by_path,
    path_by_identity,
    project_dir,
    inserted_group_ids,
    provenance_by_path,
):
    count = 0
    seen = set()

    def insert_member(image_id, group_id):
        nonlocal count
        if not image_id or not group_id or group_id not in inserted_group_ids or (image_id, group_id) in seen:
            return
        connection.execute(
            """
            INSERT OR IGNORE INTO image_group_members (image_id, group_id)
            VALUES (?, ?)
            """,
            (image_id, group_id),
        )
        seen.add((image_id, group_id))
        count += 1

    for index, group in enumerate(_custom_groups(project_data), start=1):
        if not isinstance(group, dict):
            continue
        group_id = _safe_group_id(group.get("id"), f"custom_{index}")
        if group_id not in inserted_group_ids:
            continue
        for raw_path in group.get("images", []) or []:
            image_path = _stored_path_for_raw(raw_path, project_dir, path_by_identity)
            insert_member(image_id_by_path.get(image_path), group_id)

    for image_path, image_id in image_id_by_path.items():
        provenance = provenance_by_path.get(image_path, {})
        if not isinstance(provenance, dict):
            continue
        group_id = str(provenance.get("manual_image_group") or "").strip()
        insert_member(image_id, group_id)

    return count


def _insert_scales(connection, scales_by_path, image_id_by_path):
    count = 0
    for image_path, scale in scales_by_path.items():
        image_id = image_id_by_path.get(image_path)
        if not image_id:
            continue
        metadata = {}
        if isinstance(scale, dict):
            metadata = dict(scale)
            scale_value = (
                scale.get("pixels_per_mm")
                or scale.get("pixel_per_mm")
                or scale.get("value")
            )
        else:
            scale_value = scale
        try:
            pixels_per_mm = float(scale_value)
        except Exception:
            continue
        if pixels_per_mm <= 0:
            continue
        connection.execute(
            """
            INSERT OR REPLACE INTO image_scales (image_id, pixels_per_mm, metadata_json)
            VALUES (?, ?, ?)
            """,
            (image_id, pixels_per_mm, json_text(metadata)),
        )
        count += 1
    return count


def _insert_provenance(connection, provenance_by_path, image_id_by_path):
    count = 0
    for image_path, provenance in provenance_by_path.items():
        if not isinstance(provenance, dict):
            continue
        image_id = image_id_by_path.get(image_path)
        if not image_id:
            continue
        connection.execute(
            """
            INSERT OR REPLACE INTO image_provenance (image_id, provenance_json)
            VALUES (?, ?)
            """,
            (image_id, json_text(provenance)),
        )
        count += 1
    return count


def _collect_part_names(label_data):
    part_names = []
    if not isinstance(label_data, dict):
        return part_names
    for key in (
        "parts",
        "boxes",
        "auto_boxes",
        "auto_box_meta",
        "descriptions",
        "description_sources",
        "shrink_loose_boxes",
        "trajectories",
    ):
        bucket = label_data.get(key, {})
        if not isinstance(bucket, dict):
            continue
        for part_name in bucket.keys():
            clean_part = str(part_name or "").strip()
            if clean_part and clean_part not in part_names:
                part_names.append(clean_part)
    return part_names


def _insert_label_parts(connection, label_id, label_data):
    for part_name in _collect_part_names(label_data):
        connection.execute(
            """
            INSERT OR IGNORE INTO label_parts (label_id, part_name)
            VALUES (?, ?)
            """,
            (label_id, part_name),
        )


def _insert_polygons(connection, label_id, label_data):
    count = 0
    parts = label_data.get("parts", {}) if isinstance(label_data, dict) else {}
    if not isinstance(parts, dict):
        return 0
    for part_name, points in parts.items():
        clean_part = str(part_name or "").strip()
        if not clean_part:
            continue
        polygons = _polygons_from_legacy_value(points)
        for polygon_index, polygon in enumerate(polygons):
            connection.execute(
                """
                INSERT INTO label_polygons (label_id, part_name, polygon_index, points_json, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                (label_id, clean_part, polygon_index, json_text(polygon), "legacy_json"),
            )
            count += 1
    return count


def _insert_label_boxes(connection, label_id, label_data, key, box_type):
    count = 0
    boxes = label_data.get(key, {}) if isinstance(label_data, dict) else {}
    if not isinstance(boxes, dict):
        return 0
    for part_name, box_value in boxes.items():
        clean_part = str(part_name or "").strip()
        clean_box = _clean_box(box_value)
        if not clean_part or not clean_box:
            continue
        connection.execute(
            """
            INSERT INTO label_boxes (label_id, part_name, box_type, x1, y1, x2, y2, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (label_id, clean_part, box_type, clean_box[0], clean_box[1], clean_box[2], clean_box[3], json_text({})),
        )
        count += 1
    return count


def _insert_blink_trajectories(connection, label_id, label_data):
    count = 0
    trajectories = label_data.get("trajectories", {}) if isinstance(label_data, dict) else {}
    if not isinstance(trajectories, dict):
        return 0
    for child_part, payload in trajectories.items():
        clean_child = str(child_part or "").strip()
        if not clean_child:
            continue
        payload = payload if isinstance(payload, dict) else {"legacy_payload": payload}
        parent_context = payload.get("parent_context", {})
        if not isinstance(parent_context, dict):
            parent_context = {}
        parent_part = str(parent_context.get("parent_part") or "").strip()
        trajectory_payload = {key: value for key, value in payload.items() if key != "parent_context"}
        connection.execute(
            """
            INSERT OR REPLACE INTO blink_trajectories (
                label_id, child_part_name, parent_part_name,
                trajectory_json, parent_context_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (label_id, clean_child, parent_part, json_text(trajectory_payload), json_text(parent_context)),
        )
        count += 1
    return count


def _insert_auto_boxes(connection, image_id, label_data, vlm_runs):
    auto_box_count = 0
    review_count = 0
    boxes = label_data.get("auto_boxes", {}) if isinstance(label_data, dict) else {}
    meta_by_part = label_data.get("auto_box_meta", {}) if isinstance(label_data, dict) else {}
    if not isinstance(boxes, dict):
        return auto_box_count, review_count
    if not isinstance(meta_by_part, dict):
        meta_by_part = {}
    for part_name, box_value in boxes.items():
        clean_part = str(part_name or "").strip()
        clean_box = _clean_box(box_value)
        if not clean_part or not clean_box:
            continue
        meta = meta_by_part.get(clean_part, {})
        meta = dict(meta) if isinstance(meta, dict) else {}
        source = str(meta.get("source") or "").strip()
        review_status = str(meta.get("review_status") or AUTO_BOX_REVIEW_DRAFT).strip() or AUTO_BOX_REVIEW_DRAFT
        run_id = _auto_box_run_id(source, meta)
        if run_id and source == AUTO_BOX_SOURCE_VLM:
            vlm_runs.setdefault(run_id, {"image_ids": set(), "image_box_counts": {}, "box_count": 0})
            vlm_runs[run_id]["image_ids"].add(image_id)
            vlm_runs[run_id]["image_box_counts"][image_id] = vlm_runs[run_id]["image_box_counts"].get(image_id, 0) + 1
            vlm_runs[run_id]["box_count"] += 1
        cursor = connection.execute(
            """
            INSERT INTO auto_boxes (
                image_id, part_name, source, x1, y1, x2, y2,
                confidence, review_status, run_id, raw_response_ref, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                image_id,
                clean_part,
                source,
                clean_box[0],
                clean_box[1],
                clean_box[2],
                clean_box[3],
                _confidence_from_meta(meta),
                review_status,
                run_id,
                _raw_response_ref(meta),
                json_text(meta),
            ),
        )
        auto_box_id = int(cursor.lastrowid)
        if review_status:
            connection.execute(
                """
                INSERT INTO auto_box_reviews (auto_box_id, review_status, reviewer_note)
                VALUES (?, ?, ?)
                """,
                (auto_box_id, review_status, str(meta.get("reviewer_note") or "")),
            )
            review_count += 1
        auto_box_count += 1
    return auto_box_count, review_count


def _insert_vlm_runs(connection, project_data, vlm_runs):
    settings = project_data.get("vlm_preannotation", {})
    settings = settings if isinstance(settings, dict) else {}
    count = 0
    result_count = 0
    prompt_profile_id = str(settings.get("prompt_profile_id") or "").strip()
    target_parts = settings.get("target_parts", [])
    processing_scope = str(settings.get("processing_scope") or "").strip()
    image_group = str(settings.get("image_group") or "").strip()
    for run_id, payload in sorted(vlm_runs.items()):
        connection.execute(
            """
            INSERT OR REPLACE INTO vlm_runs (
                run_id, status, prompt_profile_id, target_parts_json,
                processing_scope, image_group, settings_json, summary_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "imported_from_legacy_json",
                prompt_profile_id,
                json_text(target_parts if isinstance(target_parts, list) else []),
                processing_scope,
                image_group,
                json_text(settings),
                json_text({"imported_auto_box_count": int(payload.get("box_count", 0) or 0)}),
            ),
        )
        count += 1
        for image_id in sorted(payload.get("image_ids", set())):
            image_box_count = int(payload.get("image_box_counts", {}).get(image_id, 0) or 0)
            connection.execute(
                """
                INSERT OR REPLACE INTO vlm_image_results (run_id, image_id, status, box_count)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, image_id, "imported_from_legacy_json", image_box_count),
            )
            result_count += 1
    return count, result_count


def _insert_labels(connection, image_paths, image_id_by_path, labels_by_path, progress, stats, vlm_runs):
    total = progress["total"]
    for image_path in image_paths:
        label_data = labels_by_path.get(image_path, {})
        label_data = label_data if isinstance(label_data, dict) else {}
        image_id = image_id_by_path[image_path]
        descriptions = label_data.get("descriptions", {})
        description_sources = label_data.get("description_sources", {})
        cursor = connection.execute(
            """
            INSERT INTO labels (
                image_id, status, genus, taxon, taxon_rank,
                taxon_metadata_json, descriptions_json, description_sources_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                image_id,
                _label_status(label_data),
                str(label_data.get("genus") or "Unknown"),
                str(label_data.get("taxon") or label_data.get("genus") or "Unknown"),
                str(label_data.get("taxon_rank") or ""),
                json_text(_sanitize_dict(label_data.get("taxon_metadata", {}))),
                json_text(descriptions if isinstance(descriptions, dict) else {}),
                json_text(description_sources if isinstance(description_sources, dict) else {}),
            ),
        )
        label_id = int(cursor.lastrowid)
        _insert_label_parts(connection, label_id, label_data)
        stats["polygon_count"] += _insert_polygons(connection, label_id, label_data)
        stats["manual_box_count"] += _insert_label_boxes(connection, label_id, label_data, "boxes", "manual")
        stats["shrink_loose_box_count"] += _insert_label_boxes(
            connection,
            label_id,
            label_data,
            "shrink_loose_boxes",
            "shrink_loose",
        )
        stats["trajectory_count"] += _insert_blink_trajectories(connection, label_id, label_data)
        auto_count, review_count = _insert_auto_boxes(connection, image_id, label_data, vlm_runs)
        stats["auto_box_count"] += auto_count
        stats["auto_box_review_count"] += review_count
        if _label_has_saved_content(label_data):
            stats["nonempty_label_count"] += 1
        progress["done"] += 1
        _emit_progress(progress["callback"], progress["done"], total, f"写入标注: {image_path}")
    stats["label_count"] = len(image_paths)


def _normalize_path_mapping(project_data, key, project_dir, path_by_identity):
    result = {}
    mapping = project_data.get(key, {})
    if not isinstance(mapping, dict):
        return result
    for raw_path, payload in mapping.items():
        stored_path = _stored_path_for_raw(raw_path, project_dir, path_by_identity)
        if stored_path:
            result[stored_path] = payload
    return result


def _empty_stats():
    return {
        "image_count": 0,
        "label_count": 0,
        "nonempty_label_count": 0,
        "polygon_count": 0,
        "manual_box_count": 0,
        "shrink_loose_box_count": 0,
        "auto_box_count": 0,
        "auto_box_review_count": 0,
        "trajectory_count": 0,
        "scale_count": 0,
        "provenance_count": 0,
        "image_group_count": 0,
        "image_group_member_count": 0,
        "taxonomy_part_count": 0,
        "model_profile_count": 0,
        "vlm_run_count": 0,
        "vlm_image_result_count": 0,
    }


def _emit_progress(progress_callback, done, total, message):
    if progress_callback:
        progress_callback(int(done), int(total), str(message or ""))


def _write_migration_report(report_path, payload):
    atomic_write_json(report_path, payload, indent=2, ensure_ascii=False)
    return report_path


def migrate_legacy_2d_json_to_sqlite(
    json_project_path,
    database_path=None,
    manifest_path=None,
    report_path=None,
    progress_callback=None,
):
    source_json = canonical_path(json_project_path)
    if not os.path.exists(source_json):
        raise FileNotFoundError(source_json)

    target_db = canonical_path(database_path or default_sqlite_database_path(source_json))
    target_manifest = canonical_path(manifest_path or default_sqlite_manifest_path(source_json))
    target_report = canonical_path(report_path or default_migration_report_path(source_json))

    if _same_file_path(source_json, target_manifest):
        raise ValueError("sqlite_manifest_must_not_overwrite_legacy_json")
    if _same_file_path(source_json, target_db):
        raise ValueError("sqlite_database_must_not_overwrite_legacy_json")
    if _same_file_path(source_json, target_report):
        raise ValueError("sqlite_report_must_not_overwrite_legacy_json")
    if _same_file_path(target_db, target_manifest) or _same_file_path(target_db, target_report):
        raise ValueError("sqlite_database_path_conflicts_with_output")
    if _same_file_path(target_manifest, target_report):
        raise ValueError("sqlite_manifest_path_conflicts_with_report")
    if _sqlite_artifact_exists(target_db):
        raise FileExistsError(target_db)
    if os.path.exists(target_manifest):
        raise FileExistsError(target_manifest)
    if os.path.exists(target_report):
        raise FileExistsError(target_report)

    _emit_progress(progress_callback, 0, 0, "读取旧 JSON 项目")
    try:
        with open(source_json, "r", encoding="utf-8") as handle:
            project_data = json.load(handle)
    except Exception as exc:
        _emit_progress(progress_callback, 0, 0, f"读取旧 JSON 失败: {exc}")
        raise
    if not isinstance(project_data, dict):
        raise ValueError("legacy_project_json_not_object")

    project_dir = os.path.dirname(source_json) or "."
    image_paths, path_by_identity = _build_image_paths(project_data, project_dir)
    labels_by_path = _normalize_path_mapping(project_data, "labels", project_dir, path_by_identity)
    scales_by_path = _normalize_path_mapping(project_data, "scales", project_dir, path_by_identity)
    provenance_by_path = _normalize_path_mapping(project_data, "image_provenance", project_dir, path_by_identity)

    stats = _empty_stats()
    total = 6 + len(image_paths) + len(image_paths)
    progress = {"done": 1, "total": total, "callback": progress_callback}
    _emit_progress(progress_callback, progress["done"], total, "旧 JSON 已读取，开始创建 SQLite")

    tmp_db = f"{target_db}.tmp_migration_{os.getpid()}_{int(time.time() * 1000)}"
    _remove_sqlite_files(tmp_db)
    final_db_created = False
    final_manifest_created = False
    final_report_created = False
    legacy_backup_path = ""
    conn = None
    try:
        conn = create_2d_project_database(tmp_db)
        with conn:
            stats["taxonomy_part_count"] = _insert_project_settings(conn, project_data, source_json)
            stats["model_profile_count"] = _insert_model_profiles(conn, project_data.get("model_profiles", {}))
            stats["image_group_count"], inserted_group_ids = _insert_image_groups(conn, project_data)
            image_id_by_path = _insert_images(conn, image_paths, provenance_by_path, progress, stats)
            stats["image_group_member_count"] = _insert_image_group_members(
                conn,
                project_data,
                image_id_by_path,
                path_by_identity,
                project_dir,
                inserted_group_ids,
                provenance_by_path,
            )
            stats["scale_count"] = _insert_scales(conn, scales_by_path, image_id_by_path)
            stats["provenance_count"] = _insert_provenance(conn, provenance_by_path, image_id_by_path)
            vlm_runs = {}
            _insert_labels(conn, image_paths, image_id_by_path, labels_by_path, progress, stats, vlm_runs)
            vlm_count, vlm_result_count = _insert_vlm_runs(conn, project_data, vlm_runs)
            stats["vlm_run_count"] = vlm_count
            stats["vlm_image_result_count"] = vlm_result_count

        progress["done"] += 1
        _emit_progress(progress_callback, progress["done"], total, "写入项目设置和索引")
        integrity = ensure_integrity_ok(conn)
        progress["done"] += 1
        _emit_progress(progress_callback, progress["done"], total, "SQLite 完整性检查通过")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        conn = None

        os.makedirs(os.path.dirname(target_db) or ".", exist_ok=True)
        os.replace(tmp_db, target_db)
        _remove_sqlite_files(tmp_db)
        _fsync_directory(os.path.dirname(target_db) or ".")
        final_db_created = True
        progress["done"] += 1
        _emit_progress(progress_callback, progress["done"], total, "SQLite 数据库已生成")

        legacy_backup_path = _copy_legacy_json_backup(source_json)
        progress["done"] += 1
        _emit_progress(progress_callback, progress["done"], total, "旧 JSON 已复制到 legacy 备份")

        report_payload = {
            "schema_version": MIGRATION_REPORT_SCHEMA_VERSION,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "source_json_path": source_json,
            "database_path": target_db,
            "manifest_path": target_manifest,
            "legacy_json_backup_path": legacy_backup_path,
            "project_name": str(project_data.get("name") or "Untitled"),
            "stats": dict(stats),
            "integrity_check": list(integrity),
        }
        _write_migration_report(target_report, report_payload)
        final_report_created = True

        manifest_extra = {
            "legacy_json_source": os.path.basename(source_json),
            "legacy_json_backup": os.path.relpath(legacy_backup_path, os.path.dirname(target_manifest) or ".").replace("\\", "/"),
            "migration_report": os.path.relpath(target_report, os.path.dirname(target_manifest) or ".").replace("\\", "/"),
            "migration_stats": dict(stats),
        }
        write_project_manifest(
            target_manifest,
            PROJECT_2D_PROJECT_TYPE,
            str(project_data.get("name") or "Untitled"),
            target_db,
            extra=manifest_extra,
        )
        final_manifest_created = True
        progress["done"] += 1
        _emit_progress(progress_callback, progress["done"], total, "迁移 manifest 和报告已写入")

        return ProjectSQLiteMigrationResult(
            source_json_path=source_json,
            database_path=target_db,
            manifest_path=target_manifest,
            report_path=target_report,
            legacy_json_backup_path=legacy_backup_path,
            stats=stats,
            integrity_check=integrity,
        )
    except Exception:
        _emit_progress(progress_callback, progress.get("done", 0) if isinstance(progress, dict) else 0, progress.get("total", 0) if isinstance(progress, dict) else 0, "迁移失败，旧 JSON 未被修改")
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        _remove_sqlite_files(tmp_db)
        if final_manifest_created:
            try:
                os.remove(target_manifest)
            except OSError:
                pass
        if final_report_created:
            try:
                os.remove(target_report)
            except OSError:
                pass
        if final_db_created:
            _remove_sqlite_files(target_db)
        if legacy_backup_path:
            try:
                os.remove(legacy_backup_path)
            except OSError:
                pass
        raise
