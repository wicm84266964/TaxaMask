import json
import os
import shutil
import time
from dataclasses import dataclass

from .safe_io import atomic_write_json
from .sqlite_storage import ensure_integrity_ok, write_project_manifest
from .tif_project import TIF_PROJECT_SCHEMA_VERSION, TIF_PROJECT_TYPE, TifProjectManager
from .tif_sqlite_schema import TIF_SQLITE_PROJECT_TYPE, create_tif_project_database, json_text


TIF_MIGRATION_REPORT_SCHEMA_VERSION = "taxamask-tif-json-to-sqlite-migration-v1"


@dataclass
class TifSQLiteMigrationResult:
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


def default_tif_sqlite_database_path(json_project_path):
    source = os.path.abspath(str(json_project_path))
    directory = os.path.dirname(source) or "."
    stem = os.path.splitext(os.path.basename(source))[0] or "project"
    return os.path.join(directory, f"{stem}.taxamask_tif.sqlite")


def default_tif_sqlite_manifest_path(json_project_path):
    source = os.path.abspath(str(json_project_path))
    directory = os.path.dirname(source) or "."
    stem = os.path.splitext(os.path.basename(source))[0] or "project"
    return os.path.join(directory, f"{stem}.tif_sqlite_manifest.json")


def default_tif_migration_report_path(json_project_path):
    source = os.path.abspath(str(json_project_path))
    directory = os.path.dirname(source) or "."
    stem = os.path.splitext(os.path.basename(source))[0] or "project"
    report_dir = os.path.join(directory, f"{stem}.tif_migration_reports")
    return os.path.join(report_dir, f"{stem}.tif_sqlite_migration_{_timestamp()}.json")


def _legacy_json_backup_path(json_project_path):
    source = os.path.abspath(str(json_project_path))
    directory = os.path.dirname(source) or "."
    filename = os.path.basename(source)
    stem, ext = os.path.splitext(filename)
    stem = stem or "project"
    ext = ext or ".json"
    backup_dir = os.path.join(directory, f"{stem}.legacy_tif_json_backups")
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


def _emit_progress(progress_callback, done, total, message):
    if progress_callback:
        progress_callback(int(done), int(total), str(message or ""))


def _write_migration_report(report_path, payload):
    atomic_write_json(report_path, payload, indent=2, ensure_ascii=False)
    return report_path


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


def _dict_without_keys(value, excluded_keys):
    clean = dict(value) if isinstance(value, dict) else {}
    for key in excluded_keys:
        clean.pop(key, None)
    return clean


def _empty_stats():
    return {
        "specimen_count": 0,
        "volume_asset_count": 0,
        "label_layer_count": 0,
        "material_map_count": 0,
        "part_count": 0,
        "part_roi_count": 0,
        "part_reslice_count": 0,
        "global_axis_proposal_count": 0,
        "local_frame_proposal_count": 0,
        "model_count": 0,
        "run_count": 0,
        "run_artifact_count": 0,
        "event_count": 0,
    }


def _insert_project_row(connection, project_data):
    metadata_payload = {
        key: value
        for key, value in project_data.items()
        if key
        not in {
            "schema_version",
            "project_type",
            "project_id",
            "name",
            "created_at",
            "updated_at",
            "specimens",
            "models",
            "runs",
            "view_settings",
        }
    }
    connection.execute(
        """
        UPDATE tif_projects
        SET project_id = ?,
            name = ?,
            project_type = ?,
            legacy_schema_version = ?,
            view_settings_json = ?,
            metadata_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
        """,
        (
            str(project_data.get("project_id") or ""),
            str(project_data.get("name") or "Untitled TIF Project"),
            TIF_SQLITE_PROJECT_TYPE,
            str(project_data.get("schema_version") or TIF_PROJECT_SCHEMA_VERSION),
            json_text(_as_dict(project_data.get("view_settings"))),
            json_text(metadata_payload),
        ),
    )


def _insert_specimen(connection, specimen):
    return int(
        connection.execute(
            """
            INSERT INTO specimens (
                specimen_id, display_name, metadata_ref, modality,
                review_status, train_ready, source_json, provenance_json,
                metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(specimen.get("specimen_id") or ""),
                str(specimen.get("display_name") or specimen.get("specimen_id") or ""),
                str(specimen.get("metadata_ref") or ""),
                str(specimen.get("modality") or "unknown"),
                str(specimen.get("review_status") or "not_started"),
                1 if bool(specimen.get("train_ready")) else 0,
                json_text(_as_dict(specimen.get("source"))),
                json_text(_as_dict(specimen.get("provenance"))),
                json_text(_dict_without_keys(specimen.get("metadata"), {"local_axis_global_proposals"})),
                str(specimen.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
                str(specimen.get("updated_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
            ),
        ).lastrowid
    )


def _volume_has_content(record):
    if not isinstance(record, dict):
        return False
    if str(record.get("path") or "").strip():
        return True
    if record.get("shape_zyx"):
        return True
    if str(record.get("dtype") or "").strip():
        return True
    return False


def _insert_volume_asset(connection, specimen_row_id, record, *, role, asset_key="", part_row_id=None, status=""):
    if not _volume_has_content(record):
        return None
    cursor = connection.execute(
        """
        INSERT INTO volume_assets (
            specimen_id, part_id, asset_key, role, path, format,
            shape_zyx_json, dtype, spacing_zyx_json, spacing_unit,
            orientation, status, source_format, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(specimen_row_id),
            int(part_row_id) if part_row_id is not None else None,
            str(asset_key or role or ""),
            str(role or record.get("role") or "unknown"),
            str(record.get("path") or ""),
            str(record.get("format") or ""),
            json_text(_as_list(record.get("shape_zyx"))),
            str(record.get("dtype") or ""),
            json_text(_as_list(record.get("spacing_zyx"))),
            str(record.get("spacing_unit") or "micrometer"),
            str(record.get("orientation") or "unknown"),
            str(status or record.get("status") or ""),
            str(record.get("source_format") or ""),
            json_text(
                {
                    key: value
                    for key, value in record.items()
                    if key
                    not in {
                        "path",
                        "format",
                        "shape_zyx",
                        "dtype",
                        "spacing_zyx",
                        "spacing_unit",
                        "orientation",
                        "status",
                        "source_format",
                    }
                }
            ),
        ),
    )
    return int(cursor.lastrowid)


def _insert_label_layer(connection, specimen_row_id, volume_asset_id, record, *, role):
    if not volume_asset_id:
        return None
    cursor = connection.execute(
        """
        INSERT INTO label_layers (
            specimen_id, volume_asset_id, role, status, prediction_id,
            source_model, is_active, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(specimen_row_id),
            int(volume_asset_id),
            str(role or record.get("role") or ""),
            str(record.get("status") or ""),
            str(record.get("prediction_id") or ""),
            str(record.get("source_model") or ""),
            1,
            json_text(
                {
                    key: value
                    for key, value in record.items()
                    if key
                    not in {
                        "path",
                        "format",
                        "shape_zyx",
                        "dtype",
                        "spacing_zyx",
                        "spacing_unit",
                        "orientation",
                        "status",
                        "prediction_id",
                        "source_model",
                    }
                }
            ),
        ),
    )
    return int(cursor.lastrowid)


def _insert_material_map(connection, specimen_row_id, specimen):
    material_map = _as_dict(specimen.get("material_map_payload"))
    materials = _as_list(material_map.get("materials"))
    cursor = connection.execute(
        """
        INSERT INTO material_maps (specimen_id, path, source, materials_json, metadata_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            int(specimen_row_id),
            str(specimen.get("material_map") or ""),
            str(material_map.get("source") or "manual"),
            json_text(materials),
            json_text(
                {
                    key: value
                    for key, value in material_map.items()
                    if key not in {"source", "materials", "schema_version"}
                }
            ),
        ),
    )
    return int(cursor.lastrowid)


def _insert_part_shell(connection, specimen_row_id, part):
    metadata_payload = _dict_without_keys(part.get("metadata"), {"local_axis_reslices", "local_axis_frame_proposals"})
    metadata_payload["training"] = _as_dict(part.get("training"))
    metadata_payload["system_status"] = str(part.get("system_status") or "")
    metadata_payload["user_tags"] = _as_list(part.get("user_tags"))
    cursor = connection.execute(
        """
        INSERT INTO parts (
            specimen_id, part_id, display_name, status,
            contours_path, extraction_path, parent_bbox_zyx_json,
            source_json, metadata_json, view_settings_json,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(specimen_row_id),
            str(part.get("part_id") or ""),
            str(part.get("display_name") or part.get("part_id") or ""),
            str(part.get("status") or "draft"),
            str(part.get("contours_path") or ""),
            str(part.get("extraction_path") or ""),
            json_text(_as_list(part.get("parent_bbox_zyx"))),
            json_text(_as_dict(part.get("source"))),
            json_text(metadata_payload),
            json_text(_as_dict(part.get("view_settings"))),
            str(part.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
            str(part.get("updated_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
        ),
    )
    return int(cursor.lastrowid)


def _update_part_asset_refs(connection, part_row_id, image_asset_id, mask_asset_id):
    connection.execute(
        """
        UPDATE parts
        SET image_asset_id = ?,
            mask_asset_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            int(image_asset_id) if image_asset_id else None,
            int(mask_asset_id) if mask_asset_id else None,
            int(part_row_id),
        ),
    )


def _insert_part_roi(connection, specimen_row_id, roi, part_row_by_part_id):
    linked_part_id = str(roi.get("linked_part_id") or "")
    linked_part_row_id = part_row_by_part_id.get(linked_part_id)
    cursor = connection.execute(
        """
        INSERT INTO part_rois (
            specimen_id, roi_id, display_name, status, bbox_zyx_json,
            linked_part_id, linked_part_row_id, metadata_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(specimen_row_id),
            str(roi.get("roi_id") or ""),
            str(roi.get("display_name") or roi.get("roi_id") or ""),
            str(roi.get("status") or "draft"),
            json_text(_as_list(roi.get("bbox_zyx"))),
            linked_part_id,
            int(linked_part_row_id) if linked_part_row_id else None,
            json_text(_as_dict(roi.get("metadata"))),
            str(roi.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
            str(roi.get("updated_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
        ),
    )
    return int(cursor.lastrowid)


def _insert_part_reslice(connection, part_row_id, record):
    training_payload = _as_dict(record.get("training"))
    if isinstance(record.get("labels"), dict):
        training_payload["_reslice_labels"] = _as_dict(record.get("labels"))
    cursor = connection.execute(
        """
        INSERT INTO part_reslices (
            part_id, reslice_id, display_name, template_id, status,
            image_path, mask_path, metadata_path, preview_path,
            local_frame_json, reslice_params_json, source_json,
            training_json, training_sample_json, provenance_json,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(part_row_id),
            str(record.get("reslice_id") or ""),
            str(record.get("display_name") or record.get("reslice_id") or ""),
            str(record.get("template_id") or ""),
            str(record.get("status") or "exported"),
            str(record.get("image_path") or ""),
            str(record.get("mask_path") or ""),
            str(record.get("metadata_path") or ""),
            str(record.get("preview_path") or ""),
            json_text(_as_dict(record.get("local_frame"))),
            json_text(_as_dict(record.get("reslice_params"))),
            json_text(_as_dict(record.get("source"))),
            json_text(training_payload),
            json_text(_as_dict(record.get("training_sample"))),
            json_text(_as_dict(record.get("provenance"))),
            str(record.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
            str(record.get("updated_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
        ),
    )
    return int(cursor.lastrowid)


def _insert_global_axis_proposal(connection, specimen_row_id, record):
    cursor = connection.execute(
        """
        INSERT INTO global_axis_proposals (
            specimen_id, proposal_id, template_id, coordinate_space,
            bbox_zyx_json, center_zyx_json, confidence, model_id,
            model_version, status, hard_case_flags_json, input_data_json,
            failure_reason, reviewer_notes, provenance_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(specimen_row_id),
            str(record.get("global_proposal_id") or record.get("proposal_id") or ""),
            str(record.get("template_id") or ""),
            str(record.get("coordinate_space") or "full_volume_voxel_zyx"),
            json_text(_as_list(record.get("bbox_zyx"))),
            json_text(_as_list(record.get("center_zyx"))),
            float(record.get("confidence", 0.0) or 0.0),
            str(record.get("model_id") or ""),
            str(record.get("model_version") or ""),
            str(record.get("status") or "proposed"),
            json_text(_as_list(record.get("hard_case_flags"))),
            json_text(_as_dict(record.get("input_data"))),
            str(record.get("failure_reason") or ""),
            str(record.get("reviewer_notes") or ""),
            json_text(_as_dict(record.get("provenance"))),
            str(record.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
            str(record.get("updated_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
        ),
    )
    return int(cursor.lastrowid)


def _insert_local_frame_proposal(connection, part_row_id, record):
    cursor = connection.execute(
        """
        INSERT INTO local_frame_proposals (
            part_id, proposal_id, template_id, coordinate_space,
            origin_zyx_json, output_axis_start_zyx_json,
            output_axis_end_zyx_json, roll_reference_json,
            local_frame_json, source_axis_json, confidence,
            landmark_scores_json, missing_landmarks_json,
            model_id, model_version, status, hard_case_flags_json,
            input_data_json, failure_reason, reviewer_notes,
            provenance_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(part_row_id),
            str(record.get("frame_proposal_id") or record.get("proposal_id") or ""),
            str(record.get("template_id") or ""),
            str(record.get("coordinate_space") or "part_volume_voxel_zyx"),
            json_text(_as_list(record.get("origin_zyx"))),
            json_text(_as_list(record.get("output_axis_start_zyx"))),
            json_text(_as_list(record.get("output_axis_end_zyx"))),
            json_text(_as_dict(record.get("roll_reference"))),
            json_text(_as_dict(record.get("local_frame"))),
            json_text(_as_dict(record.get("source_axis"))),
            float(record.get("confidence", 0.0) or 0.0),
            json_text(_as_dict(record.get("landmark_scores"))),
            json_text(_as_list(record.get("missing_landmarks"))),
            str(record.get("model_id") or ""),
            str(record.get("model_version") or ""),
            str(record.get("status") or "proposed"),
            json_text(_as_list(record.get("hard_case_flags"))),
            json_text(_as_dict(record.get("input_data"))),
            str(record.get("failure_reason") or ""),
            str(record.get("reviewer_notes") or ""),
            json_text(_as_dict(record.get("provenance"))),
            str(record.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
            str(record.get("updated_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
        ),
    )
    return int(cursor.lastrowid)


def _insert_model(connection, record):
    model_id = str(record.get("model_id") or record.get("model_manifest") or record.get("run_id") or "").strip()
    if not model_id:
        model_id = f"legacy_tif_model_{int(time.time() * 1000)}"
    cursor = connection.execute(
        """
        INSERT OR REPLACE INTO tif_models (
            model_id, model_version, profile_scope, template_id,
            model_type, backend_type, backend_id, input_contract_json,
            output_contract_json, model_path, model_manifest,
            training_manifest_path, notes, metadata_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            model_id,
            str(record.get("model_version") or ""),
            str(record.get("profile_scope") or ""),
            str(record.get("template_id") or ""),
            str(record.get("model_type") or ""),
            str(record.get("backend_type") or ""),
            str(record.get("backend_id") or ""),
            json_text(_as_dict(record.get("input_contract"))),
            json_text(_as_dict(record.get("output_contract"))),
            str(record.get("model_path") or ""),
            str(record.get("model_manifest") or ""),
            str(record.get("training_manifest_path") or ""),
            str(record.get("notes") or ""),
            json_text(
                {
                    key: value
                    for key, value in record.items()
                    if key
                    not in {
                        "model_id",
                        "model_version",
                        "profile_scope",
                        "template_id",
                        "model_type",
                        "backend_type",
                        "backend_id",
                        "input_contract",
                        "output_contract",
                        "model_path",
                        "model_manifest",
                        "training_manifest_path",
                        "notes",
                        "created_at",
                        "updated_at",
                    }
                }
            ),
            str(record.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
            str(record.get("updated_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
        ),
    )
    return cursor.rowcount


def _insert_run(connection, record):
    run_id = str(record.get("run_id") or "").strip()
    if not run_id:
        run_id = f"legacy_tif_run_{int(time.time() * 1000)}"
    cursor = connection.execute(
        """
        INSERT OR REPLACE INTO tif_runs (
            run_id, workflow, action, backend_id, model_id, template_id,
            specimen_ids_json, part_ids_json, run_dir, contract_json,
            result_json, result_status, metrics_json, warnings_json,
            errors_json, metadata_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            str(record.get("workflow") or ""),
            str(record.get("action") or record.get("run_type") or ""),
            str(record.get("backend_id") or ""),
            str(record.get("model_id") or ""),
            str(record.get("template_id") or ""),
            json_text(_as_list(record.get("specimen_ids"))),
            json_text(_as_list(record.get("part_ids"))),
            str(record.get("run_dir") or ""),
            str(record.get("contract_json") or ""),
            str(record.get("result_json") or ""),
            str(record.get("result_status") or record.get("status") or ""),
            json_text(_as_dict(record.get("metrics"))),
            json_text(_as_list(record.get("warnings"))),
            json_text(_as_list(record.get("errors"))),
            json_text(
                {
                    key: value
                    for key, value in record.items()
                    if key
                    not in {
                        "run_id",
                        "workflow",
                        "action",
                        "run_type",
                        "backend_id",
                        "model_id",
                        "template_id",
                        "specimen_ids",
                        "part_ids",
                        "run_dir",
                        "contract_json",
                        "result_json",
                        "result_status",
                        "status",
                        "metrics",
                        "warnings",
                        "errors",
                        "created_at",
                        "updated_at",
                    }
                }
            ),
            str(record.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
            str(record.get("updated_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")),
        ),
    )
    return run_id, cursor.rowcount


def _insert_run_artifacts(connection, run_id, record):
    artifacts = _as_list(record.get("artifacts"))
    count = 0
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        connection.execute(
            """
            INSERT INTO tif_run_artifacts (
                run_id, artifact_type, role, path, format,
                specimen_id, part_id, prediction_id, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(run_id),
                str(artifact.get("type") or artifact.get("artifact_type") or ""),
                str(artifact.get("role") or ""),
                str(artifact.get("path") or ""),
                str(artifact.get("format") or ""),
                str(artifact.get("specimen_id") or ""),
                str(artifact.get("part_id") or ""),
                str(artifact.get("prediction_id") or ""),
                json_text(
                    {
                        key: value
                        for key, value in artifact.items()
                        if key not in {"type", "artifact_type", "role", "path", "format", "specimen_id", "part_id", "prediction_id"}
                    }
                ),
            ),
        )
        count += 1
    return count


def _insert_specimen_tree(connection, specimen, stats):
    specimen_row_id = _insert_specimen(connection, specimen)
    stats["specimen_count"] += 1

    working_asset_id = _insert_volume_asset(
        connection,
        specimen_row_id,
        _as_dict(specimen.get("working_volume")),
        role="working_image",
        asset_key="working_volume",
    )
    if working_asset_id:
        stats["volume_asset_count"] += 1

    labels = _as_dict(specimen.get("labels"))
    for role in ("manual_truth", "working_edit"):
        record = _as_dict(labels.get(role))
        asset_id = _insert_volume_asset(connection, specimen_row_id, record, role=role, asset_key=f"labels.{role}", status=record.get("status", ""))
        if asset_id:
            stats["volume_asset_count"] += 1
            _insert_label_layer(connection, specimen_row_id, asset_id, record, role=role)
            stats["label_layer_count"] += 1
    for draft_index, draft in enumerate(_as_list(labels.get("model_drafts"))):
        record = _as_dict(draft)
        asset_id = _insert_volume_asset(
            connection,
            specimen_row_id,
            record,
            role="model_draft",
            asset_key=f"labels.model_drafts.{draft_index}",
            status=record.get("status", "draft"),
        )
        if asset_id:
            stats["volume_asset_count"] += 1
            _insert_label_layer(connection, specimen_row_id, asset_id, record, role="model_draft")
            stats["label_layer_count"] += 1

    if str(specimen.get("material_map") or "").strip() or specimen.get("material_map_payload"):
        _insert_material_map(connection, specimen_row_id, specimen)
        stats["material_map_count"] += 1

    part_row_by_part_id = {}
    parts = _as_list(specimen.get("parts"))
    for part in parts:
        if not isinstance(part, dict):
            continue
        part_row_id = _insert_part_shell(connection, specimen_row_id, part)
        part_id = str(part.get("part_id") or "")
        part_row_by_part_id[part_id] = part_row_id
        stats["part_count"] += 1
        image_asset_id = _insert_volume_asset(connection, specimen_row_id, _as_dict(part.get("image")), role="part_image", asset_key=f"parts.{part_id}.image", part_row_id=part_row_id)
        if image_asset_id:
            stats["volume_asset_count"] += 1
        mask_asset_id = _insert_volume_asset(connection, specimen_row_id, _as_dict(part.get("mask")), role="part_mask", asset_key=f"parts.{part_id}.mask", part_row_id=part_row_id)
        if mask_asset_id:
            stats["volume_asset_count"] += 1
        if image_asset_id or mask_asset_id:
            _update_part_asset_refs(connection, part_row_id, image_asset_id, mask_asset_id)

        part_labels = _as_dict(part.get("labels"))
        for role in ("manual_truth", "editable_ai_result", "raw_ai_prediction_backup"):
            record = _as_dict(part_labels.get(role))
            asset_id = _insert_volume_asset(
                connection,
                specimen_row_id,
                record,
                role=f"part_{role}",
                asset_key=f"parts.{part_id}.labels.{role}",
                part_row_id=part_row_id,
                status=record.get("status", ""),
            )
            if asset_id:
                stats["volume_asset_count"] += 1
                _insert_label_layer(connection, specimen_row_id, asset_id, record, role=f"part_{role}")
                stats["label_layer_count"] += 1

        metadata = _as_dict(part.get("metadata"))
        for reslice in _as_list(metadata.get("local_axis_reslices")):
            if isinstance(reslice, dict):
                _insert_part_reslice(connection, part_row_id, reslice)
                stats["part_reslice_count"] += 1
        for proposal in _as_list(metadata.get("local_axis_frame_proposals")):
            if isinstance(proposal, dict):
                _insert_local_frame_proposal(connection, part_row_id, proposal)
                stats["local_frame_proposal_count"] += 1

    for roi in _as_list(specimen.get("part_rois")):
        if isinstance(roi, dict):
            _insert_part_roi(connection, specimen_row_id, roi, part_row_by_part_id)
            stats["part_roi_count"] += 1

    for proposal in _as_list(_as_dict(specimen.get("metadata")).get("local_axis_global_proposals")):
        if isinstance(proposal, dict):
            _insert_global_axis_proposal(connection, specimen_row_id, proposal)
            stats["global_axis_proposal_count"] += 1


def _load_and_normalize_tif_project(source_json):
    manager = TifProjectManager()
    project_data = manager.load_project(source_json)
    if project_data.get("schema_version") != TIF_PROJECT_SCHEMA_VERSION:
        raise ValueError(f"unsupported_tif_project_schema:{project_data.get('schema_version')}")
    if project_data.get("project_type") != TIF_PROJECT_TYPE:
        raise ValueError(f"not_tif_volume_project:{project_data.get('project_type')}")
    project_dir = os.path.dirname(os.path.abspath(source_json)) or "."
    for specimen in project_data.get("specimens", []) or []:
        if not isinstance(specimen, dict):
            continue
        material_rel = str(specimen.get("material_map") or "")
        if not material_rel:
            continue
        material_abs = manager.to_absolute(material_rel)
        if not os.path.exists(material_abs):
            continue
        try:
            with open(material_abs, "r", encoding="utf-8") as handle:
                material_payload = json.load(handle)
            if isinstance(material_payload, dict):
                specimen["material_map_payload"] = material_payload
        except Exception:
            specimen["material_map_payload"] = {}
    return project_data, project_dir


def _validate_output_paths(source_json, target_db, target_manifest, target_report):
    if _same_file_path(source_json, target_manifest):
        raise ValueError("tif_sqlite_manifest_must_not_overwrite_legacy_json")
    if _same_file_path(source_json, target_db):
        raise ValueError("tif_sqlite_database_must_not_overwrite_legacy_json")
    if _same_file_path(source_json, target_report):
        raise ValueError("tif_sqlite_report_must_not_overwrite_legacy_json")
    if _same_file_path(target_db, target_manifest) or _same_file_path(target_db, target_report):
        raise ValueError("tif_sqlite_database_path_conflicts_with_output")
    if _same_file_path(target_manifest, target_report):
        raise ValueError("tif_sqlite_manifest_path_conflicts_with_report")
    if _sqlite_artifact_exists(target_db):
        raise FileExistsError(target_db)
    if os.path.exists(target_manifest):
        raise FileExistsError(target_manifest)
    if os.path.exists(target_report):
        raise FileExistsError(target_report)


def migrate_legacy_tif_json_to_sqlite(
    json_project_path,
    database_path=None,
    manifest_path=None,
    report_path=None,
    progress_callback=None,
):
    source_json = os.path.abspath(str(json_project_path))
    if not os.path.exists(source_json):
        raise FileNotFoundError(source_json)

    target_db = os.path.abspath(str(database_path or default_tif_sqlite_database_path(source_json)))
    target_manifest = os.path.abspath(str(manifest_path or default_tif_sqlite_manifest_path(source_json)))
    target_report = os.path.abspath(str(report_path or default_tif_migration_report_path(source_json)))
    _validate_output_paths(source_json, target_db, target_manifest, target_report)

    _emit_progress(progress_callback, 0, 0, "读取旧 TIF JSON 项目")
    project_data, _project_dir = _load_and_normalize_tif_project(source_json)
    specimens = [item for item in _as_list(project_data.get("specimens")) if isinstance(item, dict)]
    stats = _empty_stats()
    total = 6 + len(specimens)
    progress = {"done": 1, "total": total}
    _emit_progress(progress_callback, progress["done"], total, "旧 TIF JSON 已读取，开始创建 SQLite")

    tmp_db = f"{target_db}.tmp_migration_{os.getpid()}_{int(time.time() * 1000)}"
    _remove_sqlite_files(tmp_db)
    final_db_created = False
    final_manifest_created = False
    final_report_created = False
    legacy_backup_path = ""
    conn = None
    try:
        conn = create_tif_project_database(tmp_db)
        with conn:
            _insert_project_row(conn, project_data)
            for specimen in specimens:
                _insert_specimen_tree(conn, specimen, stats)
                progress["done"] += 1
                _emit_progress(progress_callback, progress["done"], total, f"迁移 specimen: {specimen.get('specimen_id', '')}")
            for model in _as_list(project_data.get("models")):
                if isinstance(model, dict):
                    stats["model_count"] += int(bool(_insert_model(conn, model)))
            for run in _as_list(project_data.get("runs")):
                if isinstance(run, dict):
                    run_id, inserted = _insert_run(conn, run)
                    stats["run_count"] += int(bool(inserted))
                    stats["run_artifact_count"] += _insert_run_artifacts(conn, run_id, run)

        progress["done"] += 1
        _emit_progress(progress_callback, progress["done"], total, "写入 TIF 项目索引")
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
        _emit_progress(progress_callback, progress["done"], total, "TIF SQLite 数据库已生成")

        legacy_backup_path = _copy_legacy_json_backup(source_json)
        progress["done"] += 1
        _emit_progress(progress_callback, progress["done"], total, "旧 TIF JSON 已复制到 legacy 备份")

        report_payload = {
            "schema_version": TIF_MIGRATION_REPORT_SCHEMA_VERSION,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "source_json_path": source_json,
            "database_path": target_db,
            "manifest_path": target_manifest,
            "legacy_json_backup_path": legacy_backup_path,
            "project_name": str(project_data.get("name") or "Untitled TIF Project"),
            "stats": dict(stats),
            "integrity_check": list(integrity),
        }
        _write_migration_report(target_report, report_payload)
        final_report_created = True

        manifest_extra = {
            "legacy_json_source": os.path.basename(source_json),
            "legacy_json_backup": os.path.relpath(legacy_backup_path, os.path.dirname(target_manifest) or ".").replace("\\", "/"),
            "migration_report": os.path.relpath(target_report, os.path.dirname(target_manifest) or ".").replace("\\", "/"),
            "tif_asset_root": os.path.relpath(os.path.dirname(source_json) or ".", os.path.dirname(target_manifest) or ".").replace("\\", "/"),
            "migration_stats": dict(stats),
        }
        write_project_manifest(
            target_manifest,
            TIF_SQLITE_PROJECT_TYPE,
            str(project_data.get("name") or "Untitled TIF Project"),
            target_db,
            extra=manifest_extra,
        )
        final_manifest_created = True
        progress["done"] += 1
        _emit_progress(progress_callback, progress["done"], total, "TIF 迁移 manifest 和报告已写入")

        return TifSQLiteMigrationResult(
            source_json_path=source_json,
            database_path=target_db,
            manifest_path=target_manifest,
            report_path=target_report,
            legacy_json_backup_path=legacy_backup_path,
            stats=stats,
            integrity_check=integrity,
        )
    except Exception:
        _emit_progress(progress_callback, progress.get("done", 0), progress.get("total", 0), "TIF 迁移失败，旧 JSON 未被修改")
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
