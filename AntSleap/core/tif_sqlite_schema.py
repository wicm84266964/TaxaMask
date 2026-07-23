import json

from .project_integrity_registry import (
    initialize_project_integrity_registry_schema,
    validate_project_integrity_registry_schema,
)
from .training_run_recorder import (
    initialize_training_run_ledger_schema,
    validate_training_run_ledger_schema,
)
from .mesh_export_ledger import (
    initialize_mesh_export_schema,
    validate_mesh_export_schema,
)
from .sqlite_storage import (
    connect_sqlite_database,
    get_schema_version,
    initialize_schema_migrations,
    record_schema_version,
)


TIF_SQLITE_SCHEMA_NAME = "taxamask_tif_project"
TIF_SQLITE_SCHEMA_VERSION = 1
TIF_SQLITE_PROJECT_TYPE = "tif_volume"

REQUIRED_TIF_TABLES = {
    "tif_projects",
    "specimens",
    "volume_assets",
    "label_layers",
    "material_maps",
    "parts",
    "part_rois",
    "part_reslices",
    "global_axis_proposals",
    "local_frame_proposals",
    "tif_models",
    "tif_runs",
    "tif_run_artifacts",
    "tif_events",
    "schema_migrations",
}

REQUIRED_TIF_COLUMNS = {
    "tif_projects": {
        "id",
        "project_id",
        "name",
        "project_type",
        "schema_version",
        "legacy_schema_version",
        "settings_json",
        "view_settings_json",
        "metadata_json",
    },
    "specimens": {
        "id",
        "project_id",
        "specimen_id",
        "display_name",
        "metadata_ref",
        "modality",
        "review_status",
        "train_ready",
        "source_json",
        "provenance_json",
        "metadata_json",
    },
    "volume_assets": {
        "id",
        "specimen_id",
        "part_id",
        "asset_key",
        "role",
        "path",
        "format",
        "shape_zyx_json",
        "dtype",
        "spacing_zyx_json",
        "spacing_unit",
        "orientation",
        "status",
        "source_format",
        "metadata_json",
    },
    "label_layers": {
        "id",
        "specimen_id",
        "volume_asset_id",
        "role",
        "status",
        "prediction_id",
        "source_model",
        "is_active",
        "metadata_json",
    },
    "material_maps": {"id", "specimen_id", "path", "source", "materials_json", "metadata_json"},
    "parts": {
        "id",
        "specimen_id",
        "part_id",
        "display_name",
        "status",
        "image_asset_id",
        "mask_asset_id",
        "contours_path",
        "extraction_path",
        "parent_bbox_zyx_json",
        "source_json",
        "metadata_json",
        "view_settings_json",
    },
    "part_rois": {
        "id",
        "specimen_id",
        "roi_id",
        "display_name",
        "status",
        "bbox_zyx_json",
        "linked_part_id",
        "linked_part_row_id",
        "metadata_json",
    },
    "part_reslices": {
        "id",
        "part_id",
        "reslice_id",
        "display_name",
        "template_id",
        "status",
        "image_path",
        "mask_path",
        "metadata_path",
        "preview_path",
        "local_frame_json",
        "reslice_params_json",
        "source_json",
        "training_json",
        "training_sample_json",
        "provenance_json",
    },
    "global_axis_proposals": {
        "id",
        "specimen_id",
        "proposal_id",
        "template_id",
        "coordinate_space",
        "bbox_zyx_json",
        "center_zyx_json",
        "confidence",
        "model_id",
        "model_version",
        "status",
        "hard_case_flags_json",
        "input_data_json",
        "failure_reason",
        "reviewer_notes",
        "provenance_json",
    },
    "local_frame_proposals": {
        "id",
        "part_id",
        "proposal_id",
        "template_id",
        "coordinate_space",
        "origin_zyx_json",
        "output_axis_start_zyx_json",
        "output_axis_end_zyx_json",
        "roll_reference_json",
        "local_frame_json",
        "source_axis_json",
        "confidence",
        "landmark_scores_json",
        "missing_landmarks_json",
        "model_id",
        "model_version",
        "status",
        "hard_case_flags_json",
        "input_data_json",
        "failure_reason",
        "reviewer_notes",
        "provenance_json",
    },
    "tif_models": {
        "model_id",
        "model_version",
        "profile_scope",
        "template_id",
        "model_type",
        "backend_type",
        "backend_id",
        "input_contract_json",
        "output_contract_json",
        "model_path",
        "model_manifest",
        "training_manifest_path",
        "notes",
        "metadata_json",
    },
    "tif_runs": {
        "run_id",
        "workflow",
        "action",
        "backend_id",
        "model_id",
        "template_id",
        "specimen_ids_json",
        "part_ids_json",
        "run_dir",
        "contract_json",
        "result_json",
        "result_status",
        "metrics_json",
        "warnings_json",
        "errors_json",
        "metadata_json",
    },
    "tif_run_artifacts": {
        "id",
        "run_id",
        "artifact_type",
        "role",
        "path",
        "format",
        "specimen_id",
        "part_id",
        "prediction_id",
        "metadata_json",
    },
    "tif_events": {"id", "specimen_id", "part_id", "run_id", "event_type", "payload_json"},
}


def _existing_tables(connection):
    cursor = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {str(row[0]) for row in cursor.fetchall()}


def validate_tif_project_schema(connection):
    missing = sorted(REQUIRED_TIF_TABLES - _existing_tables(connection))
    if missing:
        raise ValueError(f"missing_tif_sqlite_tables:{','.join(missing)}")
    for table_name, required_columns in sorted(REQUIRED_TIF_COLUMNS.items()):
        cursor = connection.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {str(row[1]) for row in cursor.fetchall()}
        missing_columns = sorted(required_columns - existing_columns)
        if missing_columns:
            raise ValueError(f"missing_tif_sqlite_columns:{table_name}:{','.join(missing_columns)}")
    validate_project_integrity_registry_schema(connection)
    validate_training_run_ledger_schema(connection)
    validate_mesh_export_schema(connection)
    return True


def initialize_tif_project_schema(connection):
    initialize_schema_migrations(connection)
    current_version = get_schema_version(connection, TIF_SQLITE_SCHEMA_NAME)
    if current_version > TIF_SQLITE_SCHEMA_VERSION:
        raise ValueError(f"unsupported_tif_sqlite_schema_version:{current_version}")
    if current_version == TIF_SQLITE_SCHEMA_VERSION:
        with connection:
            initialize_project_integrity_registry_schema(connection)
            initialize_training_run_ledger_schema(connection)
            initialize_mesh_export_schema(connection)
        validate_tif_project_schema(connection)
        return current_version

    with connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tif_projects (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                project_id TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL DEFAULT 'Untitled TIF Project',
                project_type TEXT NOT NULL DEFAULT 'tif_volume',
                schema_version INTEGER NOT NULL DEFAULT 1,
                legacy_schema_version TEXT NOT NULL DEFAULT '',
                settings_json TEXT NOT NULL DEFAULT '{}',
                view_settings_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS specimens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL DEFAULT 1,
                specimen_id TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL DEFAULT '',
                metadata_ref TEXT NOT NULL DEFAULT '',
                modality TEXT NOT NULL DEFAULT 'unknown',
                review_status TEXT NOT NULL DEFAULT 'not_started',
                train_ready INTEGER NOT NULL DEFAULT 0,
                source_json TEXT NOT NULL DEFAULT '{}',
                provenance_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES tif_projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS volume_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                specimen_id INTEGER NOT NULL,
                part_id INTEGER,
                asset_key TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'unknown',
                path TEXT NOT NULL DEFAULT '',
                format TEXT NOT NULL DEFAULT '',
                shape_zyx_json TEXT NOT NULL DEFAULT '[]',
                dtype TEXT NOT NULL DEFAULT '',
                spacing_zyx_json TEXT NOT NULL DEFAULT '[]',
                spacing_unit TEXT NOT NULL DEFAULT 'micrometer',
                orientation TEXT NOT NULL DEFAULT 'unknown',
                status TEXT NOT NULL DEFAULT '',
                source_format TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (specimen_id) REFERENCES specimens(id) ON DELETE CASCADE,
                FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS label_layers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                specimen_id INTEGER NOT NULL,
                volume_asset_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT '',
                prediction_id TEXT NOT NULL DEFAULT '',
                source_model TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (specimen_id) REFERENCES specimens(id) ON DELETE CASCADE,
                FOREIGN KEY (volume_asset_id) REFERENCES volume_assets(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS material_maps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                specimen_id INTEGER NOT NULL UNIQUE,
                path TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'manual',
                materials_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (specimen_id) REFERENCES specimens(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                specimen_id INTEGER NOT NULL,
                part_id TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                image_asset_id INTEGER,
                mask_asset_id INTEGER,
                contours_path TEXT NOT NULL DEFAULT '',
                extraction_path TEXT NOT NULL DEFAULT '',
                parent_bbox_zyx_json TEXT NOT NULL DEFAULT '[]',
                source_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                view_settings_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(specimen_id, part_id),
                FOREIGN KEY (specimen_id) REFERENCES specimens(id) ON DELETE CASCADE,
                FOREIGN KEY (image_asset_id) REFERENCES volume_assets(id) ON DELETE SET NULL,
                FOREIGN KEY (mask_asset_id) REFERENCES volume_assets(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS part_rois (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                specimen_id INTEGER NOT NULL,
                roi_id TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                bbox_zyx_json TEXT NOT NULL DEFAULT '[]',
                linked_part_id TEXT NOT NULL DEFAULT '',
                linked_part_row_id INTEGER,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(specimen_id, roi_id),
                FOREIGN KEY (specimen_id) REFERENCES specimens(id) ON DELETE CASCADE,
                FOREIGN KEY (linked_part_row_id) REFERENCES parts(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS part_reslices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_id INTEGER NOT NULL,
                reslice_id TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                template_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'exported',
                image_path TEXT NOT NULL DEFAULT '',
                mask_path TEXT NOT NULL DEFAULT '',
                metadata_path TEXT NOT NULL DEFAULT '',
                preview_path TEXT NOT NULL DEFAULT '',
                local_frame_json TEXT NOT NULL DEFAULT '{}',
                reslice_params_json TEXT NOT NULL DEFAULT '{}',
                source_json TEXT NOT NULL DEFAULT '{}',
                training_json TEXT NOT NULL DEFAULT '{}',
                training_sample_json TEXT NOT NULL DEFAULT '{}',
                provenance_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(part_id, reslice_id),
                FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS global_axis_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                specimen_id INTEGER NOT NULL,
                proposal_id TEXT NOT NULL,
                template_id TEXT NOT NULL DEFAULT '',
                coordinate_space TEXT NOT NULL DEFAULT 'full_volume_voxel_zyx',
                bbox_zyx_json TEXT NOT NULL DEFAULT '[]',
                center_zyx_json TEXT NOT NULL DEFAULT '[]',
                confidence REAL NOT NULL DEFAULT 0.0,
                model_id TEXT NOT NULL DEFAULT '',
                model_version TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'proposed',
                hard_case_flags_json TEXT NOT NULL DEFAULT '[]',
                input_data_json TEXT NOT NULL DEFAULT '{}',
                failure_reason TEXT NOT NULL DEFAULT '',
                reviewer_notes TEXT NOT NULL DEFAULT '',
                provenance_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(specimen_id, proposal_id),
                FOREIGN KEY (specimen_id) REFERENCES specimens(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS local_frame_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_id INTEGER NOT NULL,
                proposal_id TEXT NOT NULL,
                template_id TEXT NOT NULL DEFAULT '',
                coordinate_space TEXT NOT NULL DEFAULT 'part_volume_voxel_zyx',
                origin_zyx_json TEXT NOT NULL DEFAULT '[]',
                output_axis_start_zyx_json TEXT NOT NULL DEFAULT '[]',
                output_axis_end_zyx_json TEXT NOT NULL DEFAULT '[]',
                roll_reference_json TEXT NOT NULL DEFAULT '{}',
                local_frame_json TEXT NOT NULL DEFAULT '{}',
                source_axis_json TEXT NOT NULL DEFAULT '{}',
                confidence REAL NOT NULL DEFAULT 0.0,
                landmark_scores_json TEXT NOT NULL DEFAULT '{}',
                missing_landmarks_json TEXT NOT NULL DEFAULT '[]',
                model_id TEXT NOT NULL DEFAULT '',
                model_version TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'proposed',
                hard_case_flags_json TEXT NOT NULL DEFAULT '[]',
                input_data_json TEXT NOT NULL DEFAULT '{}',
                failure_reason TEXT NOT NULL DEFAULT '',
                reviewer_notes TEXT NOT NULL DEFAULT '',
                provenance_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(part_id, proposal_id),
                FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tif_models (
                model_id TEXT PRIMARY KEY,
                model_version TEXT NOT NULL DEFAULT '',
                profile_scope TEXT NOT NULL DEFAULT 'tif_local_axis',
                template_id TEXT NOT NULL DEFAULT '',
                model_type TEXT NOT NULL DEFAULT '',
                backend_type TEXT NOT NULL DEFAULT '',
                backend_id TEXT NOT NULL DEFAULT '',
                input_contract_json TEXT NOT NULL DEFAULT '{}',
                output_contract_json TEXT NOT NULL DEFAULT '{}',
                model_path TEXT NOT NULL DEFAULT '',
                model_manifest TEXT NOT NULL DEFAULT '',
                training_manifest_path TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tif_runs (
                run_id TEXT PRIMARY KEY,
                workflow TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL DEFAULT '',
                backend_id TEXT NOT NULL DEFAULT '',
                model_id TEXT NOT NULL DEFAULT '',
                template_id TEXT NOT NULL DEFAULT '',
                specimen_ids_json TEXT NOT NULL DEFAULT '[]',
                part_ids_json TEXT NOT NULL DEFAULT '[]',
                run_dir TEXT NOT NULL DEFAULT '',
                contract_json TEXT NOT NULL DEFAULT '',
                result_json TEXT NOT NULL DEFAULT '',
                result_status TEXT NOT NULL DEFAULT '',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                warnings_json TEXT NOT NULL DEFAULT '[]',
                errors_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tif_run_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT '',
                path TEXT NOT NULL DEFAULT '',
                format TEXT NOT NULL DEFAULT '',
                specimen_id TEXT NOT NULL DEFAULT '',
                part_id TEXT NOT NULL DEFAULT '',
                prediction_id TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES tif_runs(run_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tif_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                specimen_id INTEGER,
                part_id INTEGER,
                run_id TEXT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (specimen_id) REFERENCES specimens(id) ON DELETE SET NULL,
                FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE SET NULL,
                FOREIGN KEY (run_id) REFERENCES tif_runs(run_id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tif_specimens_project ON specimens(project_id);
            CREATE INDEX IF NOT EXISTS idx_tif_specimens_review_status ON specimens(review_status);
            CREATE INDEX IF NOT EXISTS idx_tif_volume_assets_specimen_role ON volume_assets(specimen_id, role);
            CREATE INDEX IF NOT EXISTS idx_tif_volume_assets_path ON volume_assets(path);
            CREATE INDEX IF NOT EXISTS idx_tif_label_layers_specimen_role ON label_layers(specimen_id, role);
            CREATE INDEX IF NOT EXISTS idx_tif_parts_specimen ON parts(specimen_id);
            CREATE INDEX IF NOT EXISTS idx_tif_parts_status ON parts(status);
            CREATE INDEX IF NOT EXISTS idx_tif_part_rois_specimen ON part_rois(specimen_id);
            CREATE INDEX IF NOT EXISTS idx_tif_part_rois_status ON part_rois(status);
            CREATE INDEX IF NOT EXISTS idx_tif_part_reslices_part ON part_reslices(part_id);
            CREATE INDEX IF NOT EXISTS idx_tif_global_axis_specimen_status ON global_axis_proposals(specimen_id, status);
            CREATE INDEX IF NOT EXISTS idx_tif_local_frame_part_status ON local_frame_proposals(part_id, status);
            CREATE INDEX IF NOT EXISTS idx_tif_models_scope ON tif_models(profile_scope);
            CREATE INDEX IF NOT EXISTS idx_tif_runs_workflow_status ON tif_runs(workflow, result_status);
            CREATE INDEX IF NOT EXISTS idx_tif_run_artifacts_run ON tif_run_artifacts(run_id);
            CREATE INDEX IF NOT EXISTS idx_tif_events_specimen ON tif_events(specimen_id);
            CREATE INDEX IF NOT EXISTS idx_tif_events_part ON tif_events(part_id);
            CREATE INDEX IF NOT EXISTS idx_tif_events_run ON tif_events(run_id);
            """
        )
        initialize_project_integrity_registry_schema(connection)
        initialize_training_run_ledger_schema(connection)
        initialize_mesh_export_schema(connection)
        connection.execute(
            """
            INSERT OR IGNORE INTO tif_projects (id, name, project_type, schema_version)
            VALUES (1, 'Untitled TIF Project', ?, ?)
            """,
            (TIF_SQLITE_PROJECT_TYPE, TIF_SQLITE_SCHEMA_VERSION),
        )
    record_schema_version(connection, TIF_SQLITE_SCHEMA_NAME, TIF_SQLITE_SCHEMA_VERSION)
    validate_tif_project_schema(connection)
    return TIF_SQLITE_SCHEMA_VERSION


def create_tif_project_database(db_path):
    connection = connect_sqlite_database(db_path)
    try:
        initialize_tif_project_schema(connection)
        return connection
    except Exception:
        connection.close()
        raise


def json_text(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
