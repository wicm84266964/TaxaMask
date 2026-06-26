import json
import os

from .project import DEFAULT_CATEGORY_SUPERCATEGORY
from .project_sqlite_schema import PROJECT_2D_PROJECT_TYPE, validate_2d_project_schema
from .sqlite_storage import connect_sqlite_database, ensure_integrity_ok, read_project_manifest, resolve_manifest_database_path


SQLITE_PROJECT_STORAGE_BACKEND = "sqlite"


def _json_loads(value, fallback):
    if value in (None, ""):
        return fallback
    try:
        loaded = json.loads(value)
    except Exception:
        return fallback
    return loaded if loaded is not None else fallback


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


def _stored_to_absolute(path, project_dir):
    text = str(path or "").strip()
    if not text:
        return ""
    if os.path.isabs(text):
        return os.path.abspath(os.path.normpath(text))
    return os.path.abspath(os.path.normpath(os.path.join(project_dir, text)))


def _box_from_row(row):
    return [float(row["x1"]), float(row["y1"]), float(row["x2"]), float(row["y2"])]


def _default_label_entry():
    return {
        "parts": {},
        "status": "unlabeled",
        "genus": "Unknown",
        "taxon": "Unknown",
        "taxon_rank": "",
        "taxon_metadata": {},
        "descriptions": {},
        "description_sources": {},
    }


def _load_project_row(connection):
    row = connection.execute(
        """
        SELECT name, project_type, taxonomy_json, locator_scope_json,
               project_template, category_supercategory, taxon_label, settings_json
        FROM projects
        WHERE id = 1
        """
    ).fetchone()
    if row is None:
        raise ValueError("sqlite_project_missing_project_row")
    if str(row["project_type"] or "") != PROJECT_2D_PROJECT_TYPE:
        raise ValueError(f"unsupported_2d_sqlite_project_type:{row['project_type']}")
    return row


def _load_image_rows(connection, project_dir):
    image_paths = []
    image_id_to_path = {}
    rows = connection.execute(
        """
        SELECT id, path
        FROM images
        WHERE status != 'deleted'
        ORDER BY id
        """
    ).fetchall()
    for row in rows:
        image_path = _stored_to_absolute(row["path"], project_dir)
        if not image_path:
            continue
        image_paths.append(image_path)
        image_id_to_path[int(row["id"])] = image_path
    return image_paths, image_id_to_path


def _load_image_groups(connection, image_id_to_path):
    groups = []
    group_rows = connection.execute(
        """
        SELECT id, name, metadata_json
        FROM image_groups
        ORDER BY sort_order, id
        """
    ).fetchall()
    for row in group_rows:
        group = {
            "id": str(row["id"] or ""),
            "name": str(row["name"] or ""),
        }
        metadata = _as_dict(_json_loads(row["metadata_json"], {}))
        if metadata:
            group.update(metadata)
        members = [
            image_id_to_path.get(int(member["image_id"]))
            for member in connection.execute(
                """
                SELECT image_id
                FROM image_group_members
                WHERE group_id = ?
                ORDER BY image_id
                """,
                (row["id"],),
            ).fetchall()
        ]
        members = [path for path in members if path]
        if members:
            group["images"] = members
        groups.append(group)
    return {"custom_groups": groups}


def _load_labels(connection, image_id_to_path):
    labels = {}
    label_id_to_image_path = {}
    label_rows = connection.execute(
        """
        SELECT id, image_id, status, genus, taxon, taxon_rank,
               taxon_metadata_json, descriptions_json, description_sources_json
        FROM labels
        ORDER BY image_id
        """
    ).fetchall()
    for row in label_rows:
        image_path = image_id_to_path.get(int(row["image_id"]))
        if not image_path:
            continue
        entry = _default_label_entry()
        entry["status"] = str(row["status"] or "unlabeled")
        entry["genus"] = str(row["genus"] or "Unknown")
        entry["taxon"] = str(row["taxon"] or entry["genus"] or "Unknown")
        entry["taxon_rank"] = str(row["taxon_rank"] or "")
        entry["taxon_metadata"] = _as_dict(_json_loads(row["taxon_metadata_json"], {}))
        entry["descriptions"] = _as_dict(_json_loads(row["descriptions_json"], {}))
        entry["description_sources"] = _as_dict(_json_loads(row["description_sources_json"], {}))
        labels[image_path] = entry
        label_id_to_image_path[int(row["id"])] = image_path
    return labels, label_id_to_image_path


def _load_polygons(connection, labels, label_id_to_image_path):
    grouped = {}
    rows = connection.execute(
        """
        SELECT label_id, part_name, polygon_index, points_json
        FROM label_polygons
        ORDER BY label_id, part_name, polygon_index, id
        """
    ).fetchall()
    for row in rows:
        image_path = label_id_to_image_path.get(int(row["label_id"]))
        if not image_path:
            continue
        part_name = str(row["part_name"] or "").strip()
        points = _as_list(_json_loads(row["points_json"], []))
        if not part_name or not points:
            continue
        grouped.setdefault(image_path, {}).setdefault(part_name, []).append(points)

    for image_path, parts in grouped.items():
        entry = labels.setdefault(image_path, _default_label_entry())
        multi_polygons = {}
        for part_name, polygons in parts.items():
            entry.setdefault("parts", {})[part_name] = polygons[0]
            if len(polygons) > 1:
                multi_polygons[part_name] = polygons
        if multi_polygons:
            entry["part_polygons"] = multi_polygons


def _load_label_boxes(connection, labels, label_id_to_image_path):
    rows = connection.execute(
        """
        SELECT label_id, part_name, box_type, x1, y1, x2, y2, metadata_json
        FROM label_boxes
        ORDER BY label_id, id
        """
    ).fetchall()
    for row in rows:
        image_path = label_id_to_image_path.get(int(row["label_id"]))
        if not image_path:
            continue
        part_name = str(row["part_name"] or "").strip()
        box_type = str(row["box_type"] or "manual").strip() or "manual"
        if not part_name:
            continue
        entry = labels.setdefault(image_path, _default_label_entry())
        if box_type == "shrink_loose":
            entry.setdefault("shrink_loose_boxes", {})[part_name] = _box_from_row(row)
        else:
            entry.setdefault("boxes", {})[part_name] = _box_from_row(row)
            metadata = _as_dict(_json_loads(row["metadata_json"], {}))
            if metadata:
                entry.setdefault("box_meta", {})[part_name] = metadata


def _load_auto_boxes(connection, labels, image_id_to_path):
    rows = connection.execute(
        """
        SELECT image_id, part_name, source, x1, y1, x2, y2,
               confidence, review_status, run_id, raw_response_ref, metadata_json
        FROM auto_boxes
        ORDER BY image_id, id
        """
    ).fetchall()
    for row in rows:
        image_path = image_id_to_path.get(int(row["image_id"]))
        if not image_path:
            continue
        part_name = str(row["part_name"] or "").strip()
        if not part_name:
            continue
        entry = labels.setdefault(image_path, _default_label_entry())
        entry.setdefault("auto_boxes", {})[part_name] = _box_from_row(row)
        metadata = _as_dict(_json_loads(row["metadata_json"], {}))
        metadata.setdefault("source", str(row["source"] or ""))
        metadata.setdefault("review_status", str(row["review_status"] or "draft"))
        if row["confidence"] is not None:
            metadata.setdefault("confidence", float(row["confidence"]))
        if row["run_id"]:
            metadata.setdefault("source_run_id", str(row["run_id"]))
        if row["raw_response_ref"]:
            metadata.setdefault("raw_response_ref", str(row["raw_response_ref"]))
            metadata.setdefault("report_path", str(row["raw_response_ref"]))
        entry.setdefault("auto_box_meta", {})[part_name] = metadata


def _load_trajectories(connection, labels, label_id_to_image_path):
    rows = connection.execute(
        """
        SELECT label_id, child_part_name, trajectory_json, parent_context_json
        FROM blink_trajectories
        ORDER BY label_id, id
        """
    ).fetchall()
    for row in rows:
        image_path = label_id_to_image_path.get(int(row["label_id"]))
        if not image_path:
            continue
        child_part = str(row["child_part_name"] or "").strip()
        if not child_part:
            continue
        trajectory = _as_dict(_json_loads(row["trajectory_json"], {}))
        parent_context = _as_dict(_json_loads(row["parent_context_json"], {}))
        if parent_context:
            trajectory["parent_context"] = parent_context
        labels.setdefault(image_path, _default_label_entry()).setdefault("trajectories", {})[child_part] = trajectory


def _load_scales(connection, image_id_to_path):
    scales = {}
    rows = connection.execute(
        """
        SELECT image_id, pixels_per_mm
        FROM image_scales
        ORDER BY image_id
        """
    ).fetchall()
    for row in rows:
        image_path = image_id_to_path.get(int(row["image_id"]))
        if image_path:
            scales[image_path] = float(row["pixels_per_mm"])
    return scales


def _load_provenance(connection, image_id_to_path):
    provenance = {}
    rows = connection.execute(
        """
        SELECT image_id, provenance_json
        FROM image_provenance
        ORDER BY image_id
        """
    ).fetchall()
    for row in rows:
        image_path = image_id_to_path.get(int(row["image_id"]))
        if image_path:
            provenance[image_path] = _as_dict(_json_loads(row["provenance_json"], {}))
    return provenance


def _apply_group_members_to_provenance(image_groups, image_provenance):
    for group in image_groups.get("custom_groups", []):
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("id") or "").strip()
        if not group_id:
            continue
        for image_path in group.get("images", []) or []:
            if not image_path:
                continue
            image_provenance.setdefault(image_path, {}).setdefault("manual_image_group", group_id)


def _load_model_profiles(connection, settings):
    rows = connection.execute(
        """
        SELECT profile_id, profile_json, is_active
        FROM model_profiles
        ORDER BY is_active DESC, profile_id
        """
    ).fetchall()
    if not rows:
        return _as_dict(settings.get("model_profiles", {}))
    profiles = []
    active_profile_id = ""
    for row in rows:
        profile = _as_dict(_json_loads(row["profile_json"], {}))
        profile.setdefault("profile_id", str(row["profile_id"] or ""))
        profiles.append(profile)
        if int(row["is_active"] or 0) and not active_profile_id:
            active_profile_id = str(row["profile_id"] or "")
    if not active_profile_id and profiles:
        active_profile_id = str(profiles[0].get("profile_id") or "")
    return {
        "active_profile_id": active_profile_id,
        "profiles": profiles,
    }


def load_2d_sqlite_project_data(database_path, *, project_dir=None):
    db_abs = os.path.abspath(str(database_path))
    base_dir = os.path.abspath(str(project_dir or os.path.dirname(db_abs) or "."))
    connection = connect_sqlite_database(db_abs)
    try:
        validate_2d_project_schema(connection)
        integrity = ensure_integrity_ok(connection)
        connection.row_factory = lambda cursor, row: {column[0]: row[index] for index, column in enumerate(cursor.description)}
        project_row = _load_project_row(connection)
        settings = _as_dict(_json_loads(project_row["settings_json"], {}))
        image_paths, image_id_to_path = _load_image_rows(connection, base_dir)
        image_groups = _load_image_groups(connection, image_id_to_path)
        labels, label_id_to_image_path = _load_labels(connection, image_id_to_path)
        _load_polygons(connection, labels, label_id_to_image_path)
        _load_label_boxes(connection, labels, label_id_to_image_path)
        _load_auto_boxes(connection, labels, image_id_to_path)
        _load_trajectories(connection, labels, label_id_to_image_path)
        scales = _load_scales(connection, image_id_to_path)
        image_provenance = _load_provenance(connection, image_id_to_path)
        _apply_group_members_to_provenance(image_groups, image_provenance)

        for image_path in image_paths:
            labels.setdefault(image_path, _default_label_entry())

        project_data = {
            "name": str(project_row["name"] or "Untitled"),
            "images": image_paths,
            "labels": labels,
            "taxonomy": _as_list(_json_loads(project_row["taxonomy_json"], [])),
            "locator_scope": _as_list(_json_loads(project_row["locator_scope_json"], [])),
            "project_template": str(project_row["project_template"] or ""),
            "category_supercategory": str(project_row["category_supercategory"] or DEFAULT_CATEGORY_SUPERCATEGORY),
            "taxon_label": str(project_row["taxon_label"] or "Taxon"),
            "scales": scales,
            "image_provenance": image_provenance,
            "image_groups": image_groups,
            "vlm_preannotation": _as_dict(settings.get("vlm_preannotation", {})),
            "blink_context_roi_parents": _as_dict(settings.get("blink_context_roi_parents", {})),
            "parent_box_aspect_ratios": _as_dict(settings.get("parent_box_aspect_ratios", {})),
            "model_profiles": _load_model_profiles(connection, settings),
            "cascade_routes": _as_dict(settings.get("cascade_routes", {})),
        }
        return {
            "project_data": project_data,
            "integrity_check": integrity,
        }
    finally:
        connection.close()


def load_2d_sqlite_project_manifest(manifest_path):
    manifest_abs = os.path.abspath(str(manifest_path))
    manifest = read_project_manifest(manifest_abs)
    database_path = resolve_manifest_database_path(manifest_abs, manifest)
    loaded = load_2d_sqlite_project_data(database_path, project_dir=os.path.dirname(manifest_abs) or ".")
    loaded["manifest"] = manifest
    loaded["manifest_path"] = manifest_abs
    loaded["database_path"] = database_path
    return loaded
