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


def _clear_tif_index_tables(connection):
    for table_name in TIF_INDEX_TABLES:
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
    except Exception:
        return specimen
    enriched = dict(specimen)
    enriched["material_map_payload"] = payload
    return enriched


def flush_tif_project_changes(project_manager, *, integrity_check=False):
    connection = _connect_project(project_manager)
    stats = _empty_stats()
    try:
        with connection:
            _insert_project_row(connection, project_manager.project_data)
            _clear_tif_index_tables(connection)
            for specimen in project_manager.project_data.get("specimens", []) or []:
                if isinstance(specimen, dict):
                    _insert_specimen_tree(connection, _specimen_with_material_payload(project_manager, specimen), stats)
            for model in project_manager.project_data.get("models", []) or []:
                if isinstance(model, dict):
                    stats["model_count"] += int(bool(_insert_model(connection, model)))
            for run in project_manager.project_data.get("runs", []) or []:
                if isinstance(run, dict):
                    run_id, inserted = _insert_run(connection, run)
                    stats["run_count"] += int(bool(inserted))
                    stats["run_artifact_count"] += _insert_run_artifacts(connection, run_id, run)
        if integrity_check:
            ensure_integrity_ok(connection)
        return stats
    finally:
        connection.close()
