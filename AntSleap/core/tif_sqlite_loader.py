import json
import os

from .sqlite_storage import connect_sqlite_database, ensure_integrity_ok, read_project_manifest, resolve_manifest_database_path
from .tif_project import TIF_PROJECT_SCHEMA_VERSION, TIF_PROJECT_TYPE
from .tif_sqlite_schema import TIF_SQLITE_PROJECT_TYPE, validate_tif_project_schema


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


def _volume_record(row):
    if not row:
        return {
            "path": "",
            "format": "",
            "shape_zyx": [],
            "dtype": "",
            "spacing_zyx": [],
            "spacing_unit": "micrometer",
            "orientation": "unknown",
        }
    if "shape_zyx_json" not in row and isinstance(row, dict):
        record = dict(row)
        record.setdefault("path", "")
        record.setdefault("format", "")
        record.setdefault("shape_zyx", [])
        record.setdefault("dtype", "")
        record.setdefault("spacing_zyx", [])
        record.setdefault("spacing_unit", "micrometer")
        record.setdefault("orientation", "unknown")
        return record
    record = {
        "path": str(row["path"] or ""),
        "format": str(row["format"] or ""),
        "shape_zyx": _as_list(_json_loads(row["shape_zyx_json"], [])),
        "dtype": str(row["dtype"] or ""),
        "spacing_zyx": _as_list(_json_loads(row["spacing_zyx_json"], [])),
        "spacing_unit": str(row["spacing_unit"] or "micrometer"),
        "orientation": str(row["orientation"] or "unknown"),
    }
    status = str(row.get("status") or "")
    if status:
        record["status"] = status
    metadata = _as_dict(_json_loads(row.get("metadata_json"), {}))
    for key, value in metadata.items():
        if key not in record:
            record[key] = value
    return record


def _empty_labels():
    return {
        "manual_truth": _volume_record(None),
        "working_edit": _volume_record(None),
        "raw_ai_prediction_backup": _volume_record(None),
        "model_drafts": [],
    }


def _empty_part_labels():
    return {
        "manual_truth": _volume_record(None),
        "editable_ai_result": _volume_record(None),
        "raw_ai_prediction_backup": _volume_record(None),
    }


def _load_project_row(connection):
    row = connection.execute(
        """
        SELECT project_id, name, project_type, legacy_schema_version,
               view_settings_json, metadata_json, created_at, updated_at
        FROM tif_projects
        WHERE id = 1
        """
    ).fetchone()
    if row is None:
        raise ValueError("sqlite_tif_project_missing_project_row")
    if str(row["project_type"] or "") != TIF_SQLITE_PROJECT_TYPE:
        raise ValueError(f"unsupported_tif_sqlite_project_type:{row['project_type']}")
    return row


def _load_volume_assets(connection):
    rows = connection.execute(
        """
        SELECT *
        FROM volume_assets
        ORDER BY id
        """
    ).fetchall()
    by_id = {}
    by_specimen_role = {}
    by_part_role = {}
    for row in rows:
        asset_id = int(row["id"])
        by_id[asset_id] = row
        specimen_id = int(row["specimen_id"])
        role = str(row["role"] or "")
        by_specimen_role.setdefault(specimen_id, {}).setdefault(role, []).append(row)
        part_id = row["part_id"]
        if part_id is not None:
            by_part_role.setdefault(int(part_id), {}).setdefault(role, []).append(row)
    return by_id, by_specimen_role, by_part_role


def _load_label_layers(connection, volume_assets_by_id):
    rows = connection.execute(
        """
        SELECT *
        FROM label_layers
        ORDER BY id
        """
    ).fetchall()
    by_specimen = {}
    for row in rows:
        specimen_id = int(row["specimen_id"])
        role = str(row["role"] or "")
        asset = volume_assets_by_id.get(int(row["volume_asset_id"]))
        record = _volume_record(asset)
        record["status"] = str(row["status"] or record.get("status", ""))
        if row["prediction_id"]:
            record["prediction_id"] = str(row["prediction_id"])
        if row["source_model"]:
            record["source_model"] = str(row["source_model"])
        metadata = _as_dict(_json_loads(row["metadata_json"], {}))
        for key, value in metadata.items():
            if key not in record:
                record[key] = value
        labels = by_specimen.setdefault(specimen_id, _empty_labels())
        if role in {"manual_truth", "working_edit", "raw_ai_prediction_backup"}:
            labels[role] = record
        elif role == "model_draft":
            labels.setdefault("model_drafts", []).append(record)
    return by_specimen


def _load_material_maps(connection):
    rows = connection.execute(
        """
        SELECT specimen_id, path
        FROM material_maps
        ORDER BY id
        """
    ).fetchall()
    return {int(row["specimen_id"]): str(row["path"] or "") for row in rows}


def _load_parts(connection, volume_assets_by_id, volume_assets_by_part_role=None):
    volume_assets_by_part_role = volume_assets_by_part_role or {}
    rows = connection.execute(
        """
        SELECT *
        FROM parts
        ORDER BY id
        """
    ).fetchall()
    by_id = {}
    by_specimen = {}
    for row in rows:
        part = {
            "part_id": str(row["part_id"] or ""),
            "display_name": str(row["display_name"] or row["part_id"] or ""),
            "status": str(row["status"] or "draft"),
            "image": _volume_record(volume_assets_by_id.get(int(row["image_asset_id"])) if row["image_asset_id"] is not None else None),
            "mask": _volume_record(volume_assets_by_id.get(int(row["mask_asset_id"])) if row["mask_asset_id"] is not None else None),
            "labels": _empty_part_labels(),
            "contours_path": str(row["contours_path"] or ""),
            "extraction_path": str(row["extraction_path"] or ""),
            "parent_bbox_zyx": _as_list(_json_loads(row["parent_bbox_zyx_json"], [])),
            "source": _as_dict(_json_loads(row["source_json"], {})),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or row["created_at"] or ""),
            "metadata": _as_dict(_json_loads(row["metadata_json"], {})),
            "view_settings": _as_dict(_json_loads(row["view_settings_json"], {})),
        }
        row_id = int(row["id"])
        metadata = part["metadata"]
        training = _as_dict(metadata.pop("training", {}))
        system_status = str(metadata.pop("system_status", "") or training.get("system_status", "") or "cut_pending_labeling")
        part["training"] = training
        part["system_status"] = system_status
        part["user_tags"] = _as_list(metadata.pop("user_tags", []))
        by_role = volume_assets_by_part_role.get(row_id, {})
        role_map = {
            "part_manual_truth": "manual_truth",
            "part_editable_ai_result": "editable_ai_result",
            "part_raw_ai_prediction_backup": "raw_ai_prediction_backup",
        }
        for stored_role, label_role in role_map.items():
            rows_for_role = by_role.get(stored_role) or []
            if rows_for_role:
                part["labels"][label_role] = _volume_record(rows_for_role[-1])
        by_id[row_id] = part
        by_specimen.setdefault(int(row["specimen_id"]), []).append(part)
    return by_id, by_specimen


def _load_part_rois(connection):
    rows = connection.execute(
        """
        SELECT *
        FROM part_rois
        ORDER BY id
        """
    ).fetchall()
    by_specimen = {}
    for row in rows:
        roi = {
            "roi_id": str(row["roi_id"] or ""),
            "display_name": str(row["display_name"] or row["roi_id"] or ""),
            "status": str(row["status"] or "draft"),
            "bbox_zyx": _as_list(_json_loads(row["bbox_zyx_json"], [])),
            "linked_part_id": str(row["linked_part_id"] or ""),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or row["created_at"] or ""),
            "metadata": _as_dict(_json_loads(row["metadata_json"], {})),
        }
        by_specimen.setdefault(int(row["specimen_id"]), []).append(roi)
    return by_specimen


def _load_part_reslices(connection, parts_by_id):
    rows = connection.execute(
        """
        SELECT *
        FROM part_reslices
        ORDER BY id
        """
    ).fetchall()
    for row in rows:
        part = parts_by_id.get(int(row["part_id"]))
        if part is None:
            continue
        training = _as_dict(_json_loads(row["training_json"], {}))
        labels = _as_dict(training.pop("_reslice_labels", {}))
        record = {
            "reslice_id": str(row["reslice_id"] or ""),
            "part_id": part.get("part_id", ""),
            "display_name": str(row["display_name"] or row["reslice_id"] or ""),
            "template_id": str(row["template_id"] or ""),
            "status": str(row["status"] or "exported"),
            "image_path": str(row["image_path"] or ""),
            "mask_path": str(row["mask_path"] or ""),
            "metadata_path": str(row["metadata_path"] or ""),
            "preview_path": str(row["preview_path"] or ""),
            "local_frame": _as_dict(_json_loads(row["local_frame_json"], {})),
            "reslice_params": _as_dict(_json_loads(row["reslice_params_json"], {})),
            "source": _as_dict(_json_loads(row["source_json"], {})),
            "labels": {
                "manual_truth": _volume_record(labels.get("manual_truth")),
                "editable_ai_result": _volume_record(labels.get("editable_ai_result")),
                "raw_ai_prediction_backup": _volume_record(labels.get("raw_ai_prediction_backup")),
            },
            "training": training,
            "training_sample": _as_dict(_json_loads(row["training_sample_json"], {})),
            "provenance": _as_dict(_json_loads(row["provenance_json"], {})),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or row["created_at"] or ""),
        }
        part.setdefault("metadata", {}).setdefault("local_axis_reslices", []).append(record)


def _load_global_axis_proposals(connection):
    rows = connection.execute(
        """
        SELECT *
        FROM global_axis_proposals
        ORDER BY id
        """
    ).fetchall()
    by_specimen = {}
    for row in rows:
        record = {
            "global_proposal_id": str(row["proposal_id"] or ""),
            "template_id": str(row["template_id"] or ""),
            "coordinate_space": str(row["coordinate_space"] or "full_volume_voxel_zyx"),
            "bbox_zyx": _as_list(_json_loads(row["bbox_zyx_json"], [])),
            "center_zyx": _as_list(_json_loads(row["center_zyx_json"], [])),
            "confidence": float(row["confidence"] or 0.0),
            "model_id": str(row["model_id"] or ""),
            "model_version": str(row["model_version"] or ""),
            "status": str(row["status"] or "proposed"),
            "hard_case_flags": _as_list(_json_loads(row["hard_case_flags_json"], [])),
            "input_data": _as_dict(_json_loads(row["input_data_json"], {})),
            "failure_reason": str(row["failure_reason"] or ""),
            "reviewer_notes": str(row["reviewer_notes"] or ""),
            "provenance": _as_dict(_json_loads(row["provenance_json"], {})),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or row["created_at"] or ""),
        }
        by_specimen.setdefault(int(row["specimen_id"]), []).append(record)
    return by_specimen


def _load_local_frame_proposals(connection, parts_by_id):
    rows = connection.execute(
        """
        SELECT *
        FROM local_frame_proposals
        ORDER BY id
        """
    ).fetchall()
    for row in rows:
        part = parts_by_id.get(int(row["part_id"]))
        if part is None:
            continue
        record = {
            "frame_proposal_id": str(row["proposal_id"] or ""),
            "part_id": part.get("part_id", ""),
            "template_id": str(row["template_id"] or ""),
            "coordinate_space": str(row["coordinate_space"] or "part_volume_voxel_zyx"),
            "origin_zyx": _as_list(_json_loads(row["origin_zyx_json"], [])),
            "output_axis_start_zyx": _as_list(_json_loads(row["output_axis_start_zyx_json"], [])),
            "output_axis_end_zyx": _as_list(_json_loads(row["output_axis_end_zyx_json"], [])),
            "roll_reference": _as_dict(_json_loads(row["roll_reference_json"], {})),
            "local_frame": _as_dict(_json_loads(row["local_frame_json"], {})),
            "source_axis": _as_dict(_json_loads(row["source_axis_json"], {})),
            "confidence": float(row["confidence"] or 0.0),
            "landmark_scores": _as_dict(_json_loads(row["landmark_scores_json"], {})),
            "missing_landmarks": _as_list(_json_loads(row["missing_landmarks_json"], [])),
            "model_id": str(row["model_id"] or ""),
            "model_version": str(row["model_version"] or ""),
            "status": str(row["status"] or "proposed"),
            "hard_case_flags": _as_list(_json_loads(row["hard_case_flags_json"], [])),
            "input_data": _as_dict(_json_loads(row["input_data_json"], {})),
            "failure_reason": str(row["failure_reason"] or ""),
            "reviewer_notes": str(row["reviewer_notes"] or ""),
            "provenance": _as_dict(_json_loads(row["provenance_json"], {})),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or row["created_at"] or ""),
        }
        part.setdefault("metadata", {}).setdefault("local_axis_frame_proposals", []).append(record)


def _load_models(connection):
    rows = connection.execute(
        """
        SELECT *
        FROM tif_models
        ORDER BY created_at, model_id
        """
    ).fetchall()
    models = []
    for row in rows:
        metadata = _as_dict(_json_loads(row["metadata_json"], {}))
        record = dict(metadata)
        record.update(
            {
                "model_id": str(row["model_id"] or ""),
                "model_version": str(row["model_version"] or ""),
                "profile_scope": str(row["profile_scope"] or ""),
                "template_id": str(row["template_id"] or ""),
                "model_type": str(row["model_type"] or ""),
                "backend_type": str(row["backend_type"] or ""),
                "backend_id": str(row["backend_id"] or ""),
                "input_contract": _as_dict(_json_loads(row["input_contract_json"], {})),
                "output_contract": _as_dict(_json_loads(row["output_contract_json"], {})),
                "model_path": str(row["model_path"] or ""),
                "model_manifest": str(row["model_manifest"] or ""),
                "training_manifest_path": str(row["training_manifest_path"] or ""),
                "notes": str(row["notes"] or ""),
                "created_at": str(row["created_at"] or ""),
                "updated_at": str(row["updated_at"] or row["created_at"] or ""),
            }
        )
        models.append(record)
    return models


def _load_runs(connection):
    rows = connection.execute(
        """
        SELECT *
        FROM tif_runs
        ORDER BY created_at, run_id
        """
    ).fetchall()
    runs = []
    for row in rows:
        metadata = _as_dict(_json_loads(row["metadata_json"], {}))
        record = dict(metadata)
        record.update(
            {
                "run_id": str(row["run_id"] or ""),
                "workflow": str(row["workflow"] or ""),
                "action": str(row["action"] or ""),
                "backend_id": str(row["backend_id"] or ""),
                "model_id": str(row["model_id"] or ""),
                "template_id": str(row["template_id"] or ""),
                "specimen_ids": _as_list(_json_loads(row["specimen_ids_json"], [])),
                "part_ids": _as_list(_json_loads(row["part_ids_json"], [])),
                "run_dir": str(row["run_dir"] or ""),
                "contract_json": str(row["contract_json"] or ""),
                "result_json": str(row["result_json"] or ""),
                "result_status": str(row["result_status"] or ""),
                "metrics": _as_dict(_json_loads(row["metrics_json"], {})),
                "warnings": _as_list(_json_loads(row["warnings_json"], [])),
                "errors": _as_list(_json_loads(row["errors_json"], [])),
                "created_at": str(row["created_at"] or ""),
                "updated_at": str(row["updated_at"] or row["created_at"] or ""),
            }
        )
        artifacts = _load_run_artifacts(connection, record["run_id"])
        if artifacts:
            record["artifacts"] = artifacts
        runs.append(record)
    return runs


def _load_run_artifacts(connection, run_id):
    rows = connection.execute(
        """
        SELECT *
        FROM tif_run_artifacts
        WHERE run_id = ?
        ORDER BY id
        """,
        (run_id,),
    ).fetchall()
    artifacts = []
    for row in rows:
        metadata = _as_dict(_json_loads(row["metadata_json"], {}))
        record = dict(metadata)
        record.update(
            {
                "type": str(row["artifact_type"] or ""),
                "role": str(row["role"] or ""),
                "path": str(row["path"] or ""),
                "format": str(row["format"] or ""),
                "specimen_id": str(row["specimen_id"] or ""),
                "part_id": str(row["part_id"] or ""),
                "prediction_id": str(row["prediction_id"] or ""),
            }
        )
        artifacts.append(record)
    return artifacts


def load_tif_sqlite_project_data(database_path):
    db_abs = os.path.abspath(str(database_path))
    connection = connect_sqlite_database(db_abs)
    try:
        validate_tif_project_schema(connection)
        integrity = ensure_integrity_ok(connection)
        connection.row_factory = lambda cursor, row: {column[0]: row[index] for index, column in enumerate(cursor.description)}
        project_row = _load_project_row(connection)
        volume_assets_by_id, _volume_assets_by_specimen_role, volume_assets_by_part_role = _load_volume_assets(connection)
        label_layers_by_specimen = _load_label_layers(connection, volume_assets_by_id)
        material_maps_by_specimen = _load_material_maps(connection)
        parts_by_id, parts_by_specimen = _load_parts(connection, volume_assets_by_id, volume_assets_by_part_role)
        part_rois_by_specimen = _load_part_rois(connection)
        _load_part_reslices(connection, parts_by_id)
        _load_local_frame_proposals(connection, parts_by_id)
        global_axis_by_specimen = _load_global_axis_proposals(connection)

        specimens = []
        rows = connection.execute(
            """
            SELECT *
            FROM specimens
            ORDER BY id
            """
        ).fetchall()
        for row in rows:
            specimen_id = int(row["id"])
            metadata = _as_dict(_json_loads(row["metadata_json"], {}))
            metadata["local_axis_global_proposals"] = global_axis_by_specimen.get(specimen_id, [])
            specimen = {
                "specimen_id": str(row["specimen_id"] or ""),
                "display_name": str(row["display_name"] or row["specimen_id"] or ""),
                "metadata_ref": str(row["metadata_ref"] or ""),
                "modality": str(row["modality"] or "unknown"),
                "source": _as_dict(_json_loads(row["source_json"], {})),
                "working_volume": _volume_record(
                    next(
                        (
                            asset
                            for asset in volume_assets_by_id.values()
                            if int(asset["specimen_id"]) == specimen_id and str(asset["role"] or "") == "working_image"
                        ),
                        None,
                    )
                ),
                "labels": label_layers_by_specimen.get(specimen_id, _empty_labels()),
                "material_map": material_maps_by_specimen.get(specimen_id, ""),
                "review_status": str(row["review_status"] or "not_started"),
                "train_ready": bool(row["train_ready"]),
                "provenance": _as_dict(_json_loads(row["provenance_json"], {})),
                "metadata": metadata,
                "parts": parts_by_specimen.get(specimen_id, []),
                "part_rois": part_rois_by_specimen.get(specimen_id, []),
                "created_at": str(row["created_at"] or ""),
                "updated_at": str(row["updated_at"] or row["created_at"] or ""),
            }
            specimens.append(specimen)

        project_data = {
            "schema_version": TIF_PROJECT_SCHEMA_VERSION,
            "project_type": TIF_PROJECT_TYPE,
            "project_id": str(project_row["project_id"] or ""),
            "name": str(project_row["name"] or "Untitled TIF Project"),
            "created_at": str(project_row["created_at"] or ""),
            "updated_at": str(project_row["updated_at"] or project_row["created_at"] or ""),
            "specimens": specimens,
            "models": _load_models(connection),
            "runs": _load_runs(connection),
            "view_settings": _as_dict(_json_loads(project_row["view_settings_json"], {})),
        }
        metadata = _as_dict(_json_loads(project_row["metadata_json"], {}))
        project_data["label_schemas"] = _as_list(metadata.pop("label_schemas", []))
        project_data["part_user_tags"] = _as_list(metadata.pop("part_user_tags", []))
        for key, value in metadata.items():
            if key not in project_data:
                project_data[key] = value
        return {
            "project_data": project_data,
            "integrity_check": integrity,
        }
    finally:
        connection.close()


def load_tif_sqlite_project_manifest(manifest_path):
    manifest_abs = os.path.abspath(str(manifest_path))
    manifest = read_project_manifest(manifest_abs)
    if manifest.get("project_type") != TIF_SQLITE_PROJECT_TYPE:
        raise ValueError(f"unsupported_tif_sqlite_manifest_project_type:{manifest.get('project_type')}")
    database_path = resolve_manifest_database_path(manifest_abs, manifest)
    loaded = load_tif_sqlite_project_data(database_path)
    loaded["manifest"] = manifest
    loaded["manifest_path"] = manifest_abs
    loaded["database_path"] = database_path
    return loaded
