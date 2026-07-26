import json
import os

from .project_sqlite_schema import (
    PROJECT_2D_PROJECT_TYPE,
    json_text,
    new_image_uid,
    validate_2d_project_schema,
    validate_image_uid,
)
from .sqlite_storage import connect_sqlite_database, ensure_integrity_ok
from .training_truth import (
    LABEL_PART_METADATA_FIELD,
    TRAINING_TRUTH_METADATA_KEY,
    sanitize_training_truth_record,
)


AUTO_BOX_SOURCE_VLM = "vlm_first_mile"
AUTO_BOX_REVIEW_DRAFT = "draft"


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


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


def _clean_points(points):
    clean = []
    for point in points if isinstance(points, list) else []:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            clean.append([float(point[0]), float(point[1])])
        except Exception:
            continue
    return clean if len(clean) >= 3 else []


def _project_dir(project_manager):
    path = os.path.abspath(str(project_manager.current_project_path or ""))
    return os.path.dirname(path) or "."


def _stored_path(project_manager, image_path):
    try:
        rel_path = project_manager._to_relative(image_path)
    except Exception:
        rel_path = str(image_path or "")
    text = str(rel_path or "").strip()
    if not text:
        text = str(image_path or "")
    if os.path.isabs(text):
        return os.path.normpath(text)
    return os.path.normpath(text).replace("\\", "/")


def _image_identity(project_manager, image_path):
    try:
        return project_manager._path_identity(image_path)
    except Exception:
        return os.path.normcase(os.path.normpath(os.path.abspath(str(image_path or ""))))


def _registered_image_key(project_manager, image_path):
    identity = _image_identity(project_manager, image_path)
    for candidate in project_manager.project_data.get("images", []) or []:
        if _image_identity(project_manager, candidate) == identity:
            return candidate
    return image_path


def _label_entry(project_manager, image_path):
    key = _registered_image_key(project_manager, image_path)
    entry = project_manager.project_data.get("labels", {}).get(key, {})
    if not isinstance(entry, dict):
        entry = {}
    return key, entry


def _label_part_names(label_data):
    names = []
    for key in (
        "parts",
        "boxes",
        "auto_boxes",
        "auto_box_meta",
        "descriptions",
        "description_sources",
        LABEL_PART_METADATA_FIELD,
        "shrink_loose_boxes",
        "trajectories",
    ):
        bucket = label_data.get(key, {})
        if not isinstance(bucket, dict):
            continue
        for part_name in bucket.keys():
            clean = str(part_name or "").strip()
            if clean and clean not in names:
                names.append(clean)
    return names


def _auto_box_confidence(meta):
    if not isinstance(meta, dict):
        return 0.0
    value = meta.get("confidence", 0.0)
    if isinstance(value, dict):
        for key in ("final_confidence", "confidence", "score", "value"):
            if key in value:
                try:
                    return float(value.get(key) or 0.0)
                except Exception:
                    return 0.0
        return 0.0
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _auto_box_run_id(source, meta):
    if not isinstance(meta, dict):
        meta = {}
    run_id = str(meta.get("source_run_id") or meta.get("run_id") or "").strip()
    if run_id:
        return run_id
    return ""


def _raw_response_ref(meta):
    if not isinstance(meta, dict):
        return ""
    return str(meta.get("raw_response_ref") or meta.get("report_path") or "").strip()


def _vlm_settings(project_manager):
    settings = project_manager.project_data.get("vlm_preannotation", {})
    return settings if isinstance(settings, dict) else {}


def _ensure_vlm_run(connection, project_manager, run_id, *, status="running"):
    clean_run_id = str(run_id or "").strip()
    if not clean_run_id:
        return ""
    settings = _vlm_settings(project_manager)
    connection.execute(
        """
        INSERT INTO vlm_runs (
            run_id, status, prompt_profile_id, target_parts_json,
            processing_scope, image_group, settings_json, summary_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            status = excluded.status,
            prompt_profile_id = excluded.prompt_profile_id,
            target_parts_json = excluded.target_parts_json,
            processing_scope = excluded.processing_scope,
            image_group = excluded.image_group,
            settings_json = excluded.settings_json
        """,
        (
            clean_run_id,
            str(status or "running"),
            str(settings.get("prompt_profile_id") or ""),
            json_text(settings.get("target_parts", []) if isinstance(settings.get("target_parts"), list) else []),
            str(settings.get("processing_scope") or ""),
            str(settings.get("image_group") or ""),
            json_text(settings),
            json_text({}),
        ),
    )
    return clean_run_id


def _connect_project(project_manager):
    db_path = os.path.abspath(str(project_manager.current_database_path or ""))
    if not db_path:
        raise ValueError("sqlite_project_missing_database_path")
    connection = connect_sqlite_database(db_path)
    try:
        validate_2d_project_schema(connection)
        return connection
    except Exception:
        connection.close()
        raise


def write_project_metadata(connection, project_manager, *, project_data_version_id=None):
    project_data = project_manager.project_data
    settings = {
        "project_id": str(project_data.get("project_id") or ""),
        "project_data_version_id": str(
            project_data_version_id or project_data.get("project_data_version_id") or ""
        ),
        "vlm_preannotation": _as_dict(project_data.get("vlm_preannotation", {})),
        "blink_context_roi_parents": _as_dict(project_data.get("blink_context_roi_parents", {})),
        "parent_box_aspect_ratios": _as_dict(project_data.get("parent_box_aspect_ratios", {})),
        "image_groups": _as_dict(project_data.get("image_groups", {})),
        "model_profiles": _as_dict(project_data.get("model_profiles", {})),
        "cascade_routes": _as_dict(project_data.get("cascade_routes", {})),
    }
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
            json_text(_as_list(project_data.get("taxonomy", []))),
            json_text(_as_list(project_data.get("locator_scope", []))),
            str(project_data.get("project_template") or ""),
            str(project_data.get("category_supercategory") or "biological_structure"),
            str(project_data.get("taxon_label") or "Taxon"),
            json_text(settings),
        ),
    )
    connection.execute("DELETE FROM taxonomy_parts")
    for index, part_name in enumerate(_as_list(project_data.get("taxonomy", []))):
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

    active_group_ids = []
    for index, group in enumerate(_as_list(_as_dict(project_data.get("image_groups", {})).get("custom_groups", [])), start=1):
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("id") or "").strip()
        name = str(group.get("name") or "").strip()
        if not group_id or not name:
            continue
        active_group_ids.append(group_id)
        metadata = {key: value for key, value in group.items() if key not in {"id", "name", "images"}}
        connection.execute(
            """
            INSERT INTO image_groups (id, name, sort_order, metadata_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                sort_order = excluded.sort_order,
                metadata_json = excluded.metadata_json
            """,
            (group_id, name[:80], index, json_text(metadata)),
        )
    if active_group_ids:
        placeholders = ",".join("?" for _ in active_group_ids)
        connection.execute(
            f"DELETE FROM image_groups WHERE id NOT IN ({placeholders})",
            tuple(active_group_ids),
        )
    else:
        connection.execute("DELETE FROM image_groups")

    connection.execute("DELETE FROM model_profiles")
    profiles_payload = _as_dict(project_data.get("model_profiles", {}))
    active_id = str(profiles_payload.get("active_profile_id") or "").strip()
    for index, profile in enumerate(_as_list(profiles_payload.get("profiles", [])), start=1):
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


def _upsert_image(connection, project_manager, image_path):
    stored = _stored_path(project_manager, image_path)
    provenance = _as_dict(project_manager.project_data.get("image_provenance", {}).get(image_path, {}))
    group_id = str(provenance.get("manual_image_group") or "").strip()
    image_uids = project_manager.project_data.setdefault("image_uids", {})
    image_uid = str(image_uids.get(image_path) or "").strip()
    if image_uid:
        image_uid = validate_image_uid(image_uid)
    else:
        existing = connection.execute(
            "SELECT image_uid FROM images WHERE path = ?", (stored,)
        ).fetchone()
        image_uid = str(existing[0] or "").strip() if existing else ""
        if not image_uid:
            image_uid = new_image_uid()
    connection.execute(
        """
        INSERT INTO images (image_uid, path, filename, group_id, status)
        VALUES (?, ?, ?, ?, 'active')
        ON CONFLICT(path) DO UPDATE SET
            image_uid = CASE
                WHEN images.image_uid = '' THEN excluded.image_uid
                ELSE images.image_uid
            END,
            filename = excluded.filename,
            group_id = excluded.group_id,
            status = 'active',
            updated_at = CURRENT_TIMESTAMP
        """,
        (image_uid, stored, os.path.basename(str(image_path or stored)), group_id),
    )
    row = connection.execute(
        "SELECT id, image_uid FROM images WHERE path = ?", (stored,)
    ).fetchone()
    if not row:
        raise ValueError(f"sqlite_image_upsert_failed:{stored}")
    image_uids[image_path] = validate_image_uid(row[1])
    return int(row[0]), stored


def _write_group_members_for_image(connection, project_manager, image_id, image_path):
    connection.execute("DELETE FROM image_group_members WHERE image_id = ?", (image_id,))
    group_ids = set()
    provenance = _as_dict(project_manager.project_data.get("image_provenance", {}).get(image_path, {}))
    manual_group = str(provenance.get("manual_image_group") or "").strip()
    if manual_group:
        group_ids.add(manual_group)
    identity = _image_identity(project_manager, image_path)
    for group in _as_list(_as_dict(project_manager.project_data.get("image_groups", {})).get("custom_groups", [])):
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("id") or "").strip()
        if not group_id:
            continue
        for member in group.get("images", []) or []:
            if _image_identity(project_manager, member) == identity:
                group_ids.add(group_id)
                break
    for group_id in sorted(group_ids):
        exists = connection.execute("SELECT 1 FROM image_groups WHERE id = ?", (group_id,)).fetchone()
        if not exists:
            continue
        connection.execute(
            """
            INSERT OR IGNORE INTO image_group_members (image_id, group_id)
            VALUES (?, ?)
            """,
            (image_id, group_id),
        )


def write_image_state(connection, project_manager, image_path):
    image_key, label_data = _label_entry(project_manager, image_path)
    image_id, _stored = _upsert_image(connection, project_manager, image_key)

    connection.execute("DELETE FROM labels WHERE image_id = ?", (image_id,))
    connection.execute("DELETE FROM auto_boxes WHERE image_id = ?", (image_id,))
    connection.execute("DELETE FROM image_scales WHERE image_id = ?", (image_id,))
    connection.execute("DELETE FROM image_provenance WHERE image_id = ?", (image_id,))

    descriptions = _as_dict(label_data.get("descriptions", {}))
    description_sources = _as_dict(label_data.get("description_sources", {}))
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
            str(label_data.get("status") or ("labeled" if label_data.get("parts") else "unlabeled")),
            str(label_data.get("genus") or "Unknown"),
            str(label_data.get("taxon") or label_data.get("genus") or "Unknown"),
            str(label_data.get("taxon_rank") or ""),
            json_text(_as_dict(label_data.get("taxon_metadata", {}))),
            json_text(descriptions),
            json_text(description_sources),
        ),
    )
    label_id = int(cursor.lastrowid)

    for part_name in _label_part_names(label_data):
        part_metadata = _as_dict(
            _as_dict(label_data.get(LABEL_PART_METADATA_FIELD, {})).get(part_name, {})
        )
        clean_metadata = dict(part_metadata)
        if TRAINING_TRUTH_METADATA_KEY in clean_metadata:
            clean_truth = sanitize_training_truth_record(
                clean_metadata.get(TRAINING_TRUTH_METADATA_KEY)
            )
            if clean_truth is None:
                clean_metadata[TRAINING_TRUTH_METADATA_KEY] = clean_metadata.get(
                    TRAINING_TRUTH_METADATA_KEY
                )
            else:
                clean_metadata[TRAINING_TRUTH_METADATA_KEY] = clean_truth
        connection.execute(
            """
            INSERT OR IGNORE INTO label_parts (label_id, part_name, metadata_json)
            VALUES (?, ?, ?)
            """,
            (label_id, part_name, json_text(clean_metadata)),
        )

    parts = _as_dict(label_data.get("parts", {}))
    multi_parts = _as_dict(label_data.get("part_polygons", {}))
    for part_name, points in parts.items():
        clean_part = str(part_name or "").strip()
        if not clean_part:
            continue
        polygons = multi_parts.get(clean_part) if isinstance(multi_parts.get(clean_part), list) else [points]
        for polygon_index, polygon in enumerate(polygons):
            clean_points = _clean_points(polygon)
            if not clean_points:
                continue
            connection.execute(
                """
                INSERT INTO label_polygons (label_id, part_name, polygon_index, points_json, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                (label_id, clean_part, polygon_index, json_text(clean_points), "project_manager"),
            )

    for box_key, box_type in (("boxes", "manual"), ("shrink_loose_boxes", "shrink_loose")):
        for part_name, box_value in _as_dict(label_data.get(box_key, {})).items():
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

    auto_boxes = _as_dict(label_data.get("auto_boxes", {}))
    auto_meta = _as_dict(label_data.get("auto_box_meta", {}))
    for part_name, box_value in auto_boxes.items():
        clean_part = str(part_name or "").strip()
        clean_box = _clean_box(box_value)
        if not clean_part or not clean_box:
            continue
        meta = dict(auto_meta.get(clean_part, {})) if isinstance(auto_meta.get(clean_part, {}), dict) else {}
        source = str(meta.get("source") or "").strip()
        review_status = str(meta.get("review_status") or AUTO_BOX_REVIEW_DRAFT).strip() or AUTO_BOX_REVIEW_DRAFT
        run_id = _auto_box_run_id(source, meta)
        if run_id and source == AUTO_BOX_SOURCE_VLM:
            _ensure_vlm_run(connection, project_manager, run_id)
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
                _auto_box_confidence(meta),
                review_status,
                run_id,
                _raw_response_ref(meta),
                json_text(meta),
            ),
        )
        auto_box_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO auto_box_reviews (auto_box_id, review_status, reviewer_note)
            VALUES (?, ?, ?)
            """,
            (auto_box_id, review_status, str(meta.get("reviewer_note") or "")),
        )

    for child_part, payload in _as_dict(label_data.get("trajectories", {})).items():
        clean_child = str(child_part or "").strip()
        if not clean_child:
            continue
        trajectory = dict(payload) if isinstance(payload, dict) else {"legacy_payload": payload}
        parent_context = trajectory.pop("parent_context", {})
        parent_context = parent_context if isinstance(parent_context, dict) else {}
        connection.execute(
            """
            INSERT OR REPLACE INTO blink_trajectories (
                label_id, child_part_name, parent_part_name,
                trajectory_json, parent_context_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                label_id,
                clean_child,
                str(parent_context.get("parent_part") or ""),
                json_text(trajectory),
                json_text(parent_context),
            ),
        )

    scale = project_manager.project_data.get("scales", {}).get(image_key)
    if scale is not None:
        try:
            scale_value = float(scale)
        except Exception:
            scale_value = 0.0
        if scale_value > 0:
            connection.execute(
                """
                INSERT OR REPLACE INTO image_scales (image_id, pixels_per_mm, metadata_json)
                VALUES (?, ?, ?)
                """,
                (image_id, scale_value, json_text({})),
            )

    provenance = project_manager.project_data.get("image_provenance", {}).get(image_key)
    if isinstance(provenance, dict) and provenance:
        connection.execute(
            """
            INSERT OR REPLACE INTO image_provenance (image_id, provenance_json)
            VALUES (?, ?)
            """,
            (image_id, json_text(provenance)),
        )
    _write_group_members_for_image(connection, project_manager, image_id, image_key)
    return image_id


def delete_images(connection, project_manager, image_paths):
    for image_path in image_paths or []:
        stored = _stored_path(project_manager, image_path)
        connection.execute("DELETE FROM images WHERE path = ?", (stored,))


def flush_project_changes(
    project_manager,
    *,
    image_paths=None,
    deleted_image_paths=None,
    integrity_check=False,
    project_data_version_id=None,
):
    from .project_integrity_bridge import commit_2d_project_integrity_changes

    connection = _connect_project(project_manager)
    try:
        with connection:
            delete_images(connection, project_manager, deleted_image_paths or [])
            for image_path in image_paths or []:
                write_image_state(connection, project_manager, image_path)
            integrity_result = commit_2d_project_integrity_changes(
                connection,
                project_manager,
                image_paths=image_paths or [],
                deleted_image_paths=deleted_image_paths or [],
                candidate_data_version_id=project_data_version_id,
            )
            resolved_data_version_id = str(
                integrity_result.get("data_version_id")
                or project_manager.project_data.get("project_data_version_id")
                or ""
            )
            write_project_metadata(
                connection,
                project_manager,
                project_data_version_id=resolved_data_version_id,
            )
        if integrity_check:
            ensure_integrity_ok(connection)
        return {
            "data_version_id": resolved_data_version_id,
            "integrity": integrity_result,
        }
    finally:
        connection.close()


def record_vlm_image_result(project_manager, run_id, image_path, *, status="done", error_message="", raw_response_ref="", box_count=0):
    connection = _connect_project(project_manager)
    try:
        with connection:
            _ensure_vlm_run(connection, project_manager, run_id, status="running")
            image_key = _registered_image_key(project_manager, image_path)
            image_id, _stored = _upsert_image(connection, project_manager, image_key)
            connection.execute(
                """
                INSERT INTO vlm_image_results (
                    run_id, image_id, status, raw_response_ref, error_message, box_count
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, image_id) DO UPDATE SET
                    status = excluded.status,
                    raw_response_ref = excluded.raw_response_ref,
                    error_message = excluded.error_message,
                    box_count = excluded.box_count,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    str(run_id or ""),
                    image_id,
                    str(status or ""),
                    str(raw_response_ref or ""),
                    str(error_message or ""),
                    int(box_count or 0),
                ),
            )
    finally:
        connection.close()


def finish_vlm_run(project_manager, run_id, *, status="finished", summary=None):
    connection = _connect_project(project_manager)
    try:
        with connection:
            _ensure_vlm_run(connection, project_manager, run_id, status=status)
            connection.execute(
                """
                UPDATE vlm_runs
                SET status = ?, finished_at = CURRENT_TIMESTAMP, summary_json = ?
                WHERE run_id = ?
                """,
                (str(status or "finished"), json_text(summary or {}), str(run_id or "")),
            )
    finally:
        connection.close()
