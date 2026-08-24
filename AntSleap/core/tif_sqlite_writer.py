from .sqlite_storage import connect_sqlite_database, ensure_integrity_ok
from .tif_materials import read_material_map
from .tif_sqlite_migration import (
    _insert_model,
    _insert_project_row,
    _insert_run,
    _insert_run_artifacts,
    _insert_specimen_tree,
    _empty_stats,
)
from .tif_sqlite_schema import validate_tif_project_schema
from .tif_storage_schema import insert_run_storage_records


TIF_INDEX_TABLES = (
    "tif_events",
    "tif_run_artifacts",
    "tif_runs",
    "tif_models",
    "local_frame_proposals",
    "global_axis_proposals",
    "part_reslices",
    "part_rois",
    "parts",
    "material_maps",
    "label_layers",
    "volume_assets",
    "specimens",
)


def _connect_project(project_manager):
    db_path = str(getattr(project_manager, "current_database_path", "") or "")
    if not db_path:
        raise ValueError("tif_sqlite_project_missing_database_path")
    connection = connect_sqlite_database(db_path)
    try:
        validate_tif_project_schema(connection)
        return connection
    except Exception:
        connection.close()
        raise


def _clear_tif_index_tables(connection, *, preserve_events=False):
    table_names = (
        tuple(table for table in TIF_INDEX_TABLES if table != "tif_events")
        if preserve_events
        else TIF_INDEX_TABLES
    )
    for table_name in table_names:
        connection.execute(f"DELETE FROM {table_name}")


def _specimen_with_material_payload(project_manager, specimen):
    if not isinstance(specimen, dict):
        return specimen
    if specimen.get("material_map_payload"):
        return specimen
    material_path = str(specimen.get("material_map") or "").strip()
    if not material_path:
        return specimen
    try:
        payload = read_material_map(project_manager.to_absolute(material_path))
    except Exception as exc:
        specimen_id = str(specimen.get("specimen_id") or "")
        raise ValueError(f"tif_material_map_read_failed:{specimen_id}:{material_path}:{exc}") from exc
    enriched = dict(specimen)
    enriched["material_map_payload"] = payload
    return enriched


def _rewrite_tif_project_index_tables(
    connection,
    project_manager,
    *,
    preserve_events=False,
):
    stats = _empty_stats()
    _insert_project_row(connection, project_manager.project_data)
    _clear_tif_index_tables(connection, preserve_events=preserve_events)
    for specimen in project_manager.project_data.get("specimens", []) or []:
        if isinstance(specimen, dict):
            _insert_specimen_tree(
                connection,
                _specimen_with_material_payload(project_manager, specimen),
                stats,
            )
    for model in project_manager.project_data.get("models", []) or []:
        if isinstance(model, dict):
            stats["model_count"] += int(bool(_insert_model(connection, model)))
    for run in project_manager.project_data.get("runs", []) or []:
        if isinstance(run, dict):
            run_id, inserted = _insert_run(connection, run)
            stats["run_count"] += int(bool(inserted))
            stats["run_artifact_count"] += _insert_run_artifacts(
                connection, run_id, run
            )
            storage_stats = insert_run_storage_records(connection, run_id, run)
            stats["run_asset_ref_count"] = (
                int(stats.get("run_asset_ref_count", 0))
                + int(storage_stats["run_asset_ref_count"])
            )
            stats["materialization_count"] = (
                int(stats.get("materialization_count", 0))
                + int(storage_stats["materialization_count"])
            )
    return stats


def flush_tif_project_changes(
    project_manager,
    *,
    integrity_check=False,
    project_data_version_id=None,
):
    from .tif_integrity_bridge import commit_tif_project_integrity_changes

    connection = _connect_project(project_manager)
    try:
        with connection:
            stats = _rewrite_tif_project_index_tables(
                connection, project_manager
            )
            integrity_result = commit_tif_project_integrity_changes(
                connection,
                project_manager,
                candidate_data_version_id=project_data_version_id,
            )
            resolved_data_version_id = str(
                integrity_result.get("data_version_id")
                or project_manager.project_data.get("project_data_version_id")
                or ""
            )
            project_payload = dict(project_manager.project_data)
            project_payload["project_data_version_id"] = resolved_data_version_id
            _insert_project_row(connection, project_payload)
        if integrity_check:
            ensure_integrity_ok(connection)
        stats["data_version_id"] = resolved_data_version_id
        stats["integrity"] = integrity_result
        return stats
    finally:
        connection.close()
