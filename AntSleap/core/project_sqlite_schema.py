import json

from .sqlite_storage import (
    connect_sqlite_database,
    get_schema_version,
    initialize_schema_migrations,
    record_schema_version,
)


PROJECT_2D_SCHEMA_NAME = "taxamask_2d_project"
PROJECT_2D_SCHEMA_VERSION = 1
PROJECT_2D_PROJECT_TYPE = "2d_image_annotation"
REQUIRED_2D_TABLES = {
    "projects",
    "images",
    "image_groups",
    "image_group_members",
    "labels",
    "label_parts",
    "label_polygons",
    "label_boxes",
    "auto_boxes",
    "auto_box_reviews",
    "image_scales",
    "image_provenance",
    "taxonomy_parts",
    "model_profiles",
    "vlm_runs",
    "vlm_image_results",
    "blink_trajectories",
    "label_events",
    "schema_migrations",
}
REQUIRED_2D_COLUMNS = {
    "projects": {
        "id",
        "name",
        "project_type",
        "schema_version",
        "taxonomy_json",
        "locator_scope_json",
        "project_template",
        "category_supercategory",
        "taxon_label",
        "settings_json",
    },
    "images": {"id", "path", "filename", "group_id", "status", "width", "height"},
    "labels": {
        "id",
        "image_id",
        "status",
        "genus",
        "taxon",
        "taxon_rank",
        "taxon_metadata_json",
        "descriptions_json",
        "description_sources_json",
    },
    "label_polygons": {"id", "label_id", "part_name", "polygon_index", "points_json", "source"},
    "label_boxes": {"id", "label_id", "part_name", "box_type", "x1", "y1", "x2", "y2", "metadata_json"},
    "auto_boxes": {
        "id",
        "image_id",
        "part_name",
        "source",
        "x1",
        "y1",
        "x2",
        "y2",
        "confidence",
        "review_status",
        "run_id",
        "raw_response_ref",
        "metadata_json",
    },
    "vlm_runs": {"run_id", "status", "prompt_profile_id", "target_parts_json", "settings_json", "summary_json"},
    "vlm_image_results": {"id", "run_id", "image_id", "status", "raw_response_ref", "error_message", "box_count"},
    "blink_trajectories": {
        "id",
        "label_id",
        "child_part_name",
        "parent_part_name",
        "trajectory_json",
        "parent_context_json",
    },
    "label_events": {"id", "image_id", "label_id", "event_type", "payload_json"},
}


def _existing_tables(connection):
    cursor = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {str(row[0]) for row in cursor.fetchall()}


def validate_2d_project_schema(connection):
    missing = sorted(REQUIRED_2D_TABLES - _existing_tables(connection))
    if missing:
        raise ValueError(f"missing_2d_sqlite_tables:{','.join(missing)}")
    for table_name, required_columns in sorted(REQUIRED_2D_COLUMNS.items()):
        cursor = connection.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {str(row[1]) for row in cursor.fetchall()}
        missing_columns = sorted(required_columns - existing_columns)
        if missing_columns:
            raise ValueError(f"missing_2d_sqlite_columns:{table_name}:{','.join(missing_columns)}")
    return True


def initialize_2d_project_schema(connection):
    initialize_schema_migrations(connection)
    current_version = get_schema_version(connection, PROJECT_2D_SCHEMA_NAME)
    if current_version > PROJECT_2D_SCHEMA_VERSION:
        raise ValueError(f"unsupported_2d_sqlite_schema_version:{current_version}")
    if current_version == PROJECT_2D_SCHEMA_VERSION:
        validate_2d_project_schema(connection)
        return current_version

    with connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT NOT NULL DEFAULT 'Untitled',
                project_type TEXT NOT NULL DEFAULT '2d_image_annotation',
                schema_version INTEGER NOT NULL DEFAULT 1,
                taxonomy_json TEXT NOT NULL DEFAULT '[]',
                locator_scope_json TEXT NOT NULL DEFAULT '[]',
                project_template TEXT NOT NULL DEFAULT '',
                category_supercategory TEXT NOT NULL DEFAULT 'biological_structure',
                taxon_label TEXT NOT NULL DEFAULT 'Taxon',
                settings_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL DEFAULT '',
                group_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                width INTEGER,
                height INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS image_groups (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS image_group_members (
                image_id INTEGER NOT NULL,
                group_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (image_id, group_id),
                FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
                FOREIGN KEY (group_id) REFERENCES image_groups(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'unlabeled',
                genus TEXT NOT NULL DEFAULT 'Unknown',
                taxon TEXT NOT NULL DEFAULT 'Unknown',
                taxon_rank TEXT NOT NULL DEFAULT '',
                taxon_metadata_json TEXT NOT NULL DEFAULT '{}',
                descriptions_json TEXT NOT NULL DEFAULT '{}',
                description_sources_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS label_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label_id INTEGER NOT NULL,
                part_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(label_id, part_name),
                FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS label_polygons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label_id INTEGER NOT NULL,
                part_name TEXT NOT NULL,
                polygon_index INTEGER NOT NULL DEFAULT 0,
                points_json TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS label_boxes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label_id INTEGER NOT NULL,
                part_name TEXT NOT NULL,
                box_type TEXT NOT NULL DEFAULT 'manual',
                x1 REAL NOT NULL,
                y1 REAL NOT NULL,
                x2 REAL NOT NULL,
                y2 REAL NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS blink_trajectories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label_id INTEGER NOT NULL,
                child_part_name TEXT NOT NULL,
                parent_part_name TEXT NOT NULL DEFAULT '',
                trajectory_json TEXT NOT NULL DEFAULT '{}',
                parent_context_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(label_id, child_part_name),
                FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS auto_boxes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER NOT NULL,
                part_name TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                x1 REAL NOT NULL,
                y1 REAL NOT NULL,
                x2 REAL NOT NULL,
                y2 REAL NOT NULL,
                confidence REAL DEFAULT 0.0,
                review_status TEXT NOT NULL DEFAULT 'draft',
                run_id TEXT NOT NULL DEFAULT '',
                raw_response_ref TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS auto_box_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auto_box_id INTEGER NOT NULL,
                review_status TEXT NOT NULL,
                reviewer_note TEXT NOT NULL DEFAULT '',
                reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (auto_box_id) REFERENCES auto_boxes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS image_scales (
                image_id INTEGER PRIMARY KEY,
                pixels_per_mm REAL NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS image_provenance (
                image_id INTEGER PRIMARY KEY,
                provenance_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS taxonomy_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_name TEXT NOT NULL UNIQUE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS model_profiles (
                profile_id TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS vlm_runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'initialized',
                prompt_profile_id TEXT NOT NULL DEFAULT '',
                target_parts_json TEXT NOT NULL DEFAULT '[]',
                processing_scope TEXT NOT NULL DEFAULT '',
                image_group TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT,
                settings_json TEXT NOT NULL DEFAULT '{}',
                summary_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS vlm_image_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                image_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                raw_response_ref TEXT NOT NULL DEFAULT '',
                error_message TEXT NOT NULL DEFAULT '',
                box_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(run_id, image_id),
                FOREIGN KEY (run_id) REFERENCES vlm_runs(run_id) ON DELETE CASCADE,
                FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS label_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER,
                label_id INTEGER,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE SET NULL,
                FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_images_path ON images(path);
            CREATE INDEX IF NOT EXISTS idx_images_status ON images(status);
            CREATE INDEX IF NOT EXISTS idx_labels_status ON labels(status);
            CREATE INDEX IF NOT EXISTS idx_labels_taxon ON labels(taxon);
            CREATE INDEX IF NOT EXISTS idx_label_polygons_label_part ON label_polygons(label_id, part_name);
            CREATE INDEX IF NOT EXISTS idx_label_boxes_label_part ON label_boxes(label_id, part_name);
            CREATE INDEX IF NOT EXISTS idx_auto_boxes_image ON auto_boxes(image_id);
            CREATE INDEX IF NOT EXISTS idx_auto_boxes_source ON auto_boxes(source);
            CREATE INDEX IF NOT EXISTS idx_auto_boxes_review_status ON auto_boxes(review_status);
            CREATE INDEX IF NOT EXISTS idx_vlm_image_results_run ON vlm_image_results(run_id);
            CREATE INDEX IF NOT EXISTS idx_blink_trajectories_label ON blink_trajectories(label_id);
            CREATE INDEX IF NOT EXISTS idx_blink_trajectories_parent_child ON blink_trajectories(parent_part_name, child_part_name);
            CREATE INDEX IF NOT EXISTS idx_label_events_image ON label_events(image_id);
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO projects (id, name, project_type, schema_version)
            VALUES (1, 'Untitled', ?, ?)
            """,
            (PROJECT_2D_PROJECT_TYPE, PROJECT_2D_SCHEMA_VERSION),
        )
    record_schema_version(connection, PROJECT_2D_SCHEMA_NAME, PROJECT_2D_SCHEMA_VERSION)
    validate_2d_project_schema(connection)
    return PROJECT_2D_SCHEMA_VERSION


def create_2d_project_database(db_path):
    connection = connect_sqlite_database(db_path)
    try:
        initialize_2d_project_schema(connection)
        return connection
    except Exception:
        connection.close()
        raise


def json_text(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
