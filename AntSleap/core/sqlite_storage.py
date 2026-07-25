import os
import sqlite3
import time
from pathlib import Path

from .safe_io import atomic_write_json


SQLITE_BACKEND = "sqlite"
LEGACY_JSON_BACKEND = "legacy_json"
PROJECT_MANIFEST_SCHEMA_VERSION = "taxamask-project-manifest-v1"
SQLITE_BACKUP_LIMIT = 30
SQLITE_BACKUP_MIN_INTERVAL_SECONDS = 300


def connect_sqlite_database(db_path):
    path = os.path.abspath(str(db_path))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def connect_sqlite_database_readonly(db_path):
    """Open an existing SQLite database without creating files or changing WAL state."""

    path = os.path.abspath(os.fspath(db_path))
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"{Path(path).as_uri()}?mode=ro", uri=True)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA query_only = ON")
    return connection


def initialize_schema_migrations(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schema_name TEXT NOT NULL,
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(schema_name, version)
        )
        """
    )
    connection.commit()


def get_schema_version(connection, schema_name):
    cursor = connection.execute(
        """
        SELECT MAX(version)
        FROM schema_migrations
        WHERE schema_name = ?
        """,
        (str(schema_name),),
    )
    row = cursor.fetchone()
    return int(row[0] or 0) if row else 0


def record_schema_version(connection, schema_name, version):
    connection.execute(
        """
        INSERT OR IGNORE INTO schema_migrations (schema_name, version)
        VALUES (?, ?)
        """,
        (str(schema_name), int(version)),
    )
    connection.commit()


def run_integrity_check(connection):
    cursor = connection.execute("PRAGMA integrity_check")
    rows = [str(row[0]) for row in cursor.fetchall()]
    return rows or ["no_result"]


def ensure_integrity_ok(connection):
    result = run_integrity_check(connection)
    if result != ["ok"]:
        raise ValueError(f"sqlite_integrity_check_failed:{result}")
    return result


def project_manifest_payload(project_type, name, database_path, *, extra=None):
    payload = {
        "schema_version": PROJECT_MANIFEST_SCHEMA_VERSION,
        "project_type": str(project_type or ""),
        "name": str(name or "Untitled"),
        "storage_backend": SQLITE_BACKEND,
        "database_path": str(database_path or ""),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if isinstance(extra, dict):
        for key, value in extra.items():
            if key not in {"schema_version", "storage_backend", "database_path"}:
                payload[key] = value
    return payload


def write_project_manifest(manifest_path, project_type, name, database_path, *, extra=None):
    manifest_abs = os.path.abspath(str(manifest_path))
    manifest_dir = os.path.dirname(manifest_abs) or "."
    db_text = str(database_path or "")
    if db_text and os.path.isabs(db_text):
        try:
            db_text = os.path.relpath(db_text, manifest_dir).replace("\\", "/")
        except ValueError:
            db_text = os.path.abspath(db_text)
    payload = project_manifest_payload(project_type, name, db_text, extra=extra)
    atomic_write_json(manifest_abs, payload, indent=2, ensure_ascii=False)
    return payload


def read_project_manifest(manifest_path):
    import json

    manifest_abs = os.path.abspath(str(manifest_path))
    with open(manifest_abs, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("project_manifest_not_object")
    if payload.get("schema_version") != PROJECT_MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"unsupported_project_manifest_schema:{payload.get('schema_version')}")
    if payload.get("storage_backend") != SQLITE_BACKEND:
        raise ValueError(f"unsupported_storage_backend:{payload.get('storage_backend')}")
    return payload


def resolve_manifest_database_path(manifest_path, payload=None):
    manifest_abs = os.path.abspath(str(manifest_path))
    data = payload or read_project_manifest(manifest_abs)
    db_path = str(data.get("database_path", "") or "").strip()
    if not db_path:
        raise ValueError("project_manifest_missing_database_path")
    if os.path.isabs(db_path):
        return os.path.normpath(db_path)
    return os.path.normpath(os.path.join(os.path.dirname(manifest_abs), db_path))


def backup_sqlite_database(db_path, backup_dir=None, *, stem=None, min_interval_seconds=SQLITE_BACKUP_MIN_INTERVAL_SECONDS):
    source = os.path.abspath(str(db_path))
    if not os.path.exists(source):
        return ""
    target_dir = os.path.abspath(str(backup_dir or os.path.join(os.path.dirname(source), "project.sqlite_backups")))
    os.makedirs(target_dir, exist_ok=True)
    backup_stem = stem or os.path.splitext(os.path.basename(source))[0] or "project"

    existing = [
        os.path.join(target_dir, name)
        for name in os.listdir(target_dir)
        if name.startswith(f"{backup_stem}.") and name.endswith(".sqlite.bak")
    ]
    if existing and min_interval_seconds:
        latest_mtime = max(os.path.getmtime(item) for item in existing if os.path.exists(item))
        if time.time() - latest_mtime < min_interval_seconds:
            return ""

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(target_dir, f"{backup_stem}.{timestamp}.sqlite.bak")
    suffix = 2
    while os.path.exists(backup_path):
        backup_path = os.path.join(target_dir, f"{backup_stem}.{timestamp}_{suffix}.sqlite.bak")
        suffix += 1
    tmp_path = f"{backup_path}.tmp"
    try:
        source_conn = sqlite3.connect(source)
        target_conn = sqlite3.connect(tmp_path)
        try:
            source_conn.backup(target_conn)
            target_conn.commit()
        finally:
            target_conn.close()
            source_conn.close()
        os.replace(tmp_path, backup_path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise

    backups = sorted(
        [
            os.path.join(target_dir, name)
            for name in os.listdir(target_dir)
            if name.startswith(f"{backup_stem}.") and name.endswith(".sqlite.bak")
        ],
        key=lambda item: os.path.getmtime(item),
        reverse=True,
    )
    for old_backup in backups[SQLITE_BACKUP_LIMIT:]:
        try:
            os.remove(old_backup)
        except OSError:
            pass
    return backup_path


def read_database_schema_version(db_path, schema_name):
    """Read a project schema version without creating or changing the database."""

    connection = connect_sqlite_database_readonly(db_path)
    try:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
        ).fetchone()
        return get_schema_version(connection, schema_name) if table else 0
    finally:
        connection.close()


def _execute_script_in_transaction(connection, sql_script):
    """Execute a SQL script without sqlite3.executescript's implicit commit."""

    statement = ""
    for character in str(sql_script or ""):
        statement += character
        if character == ";" and sqlite3.complete_statement(statement):
            if statement.strip():
                connection.execute(statement)
            statement = ""
    if statement.strip():
        if not sqlite3.complete_statement(statement):
            raise sqlite3.OperationalError("sqlite_migration_incomplete_sql_statement")
        connection.execute(statement)


class _MigrationTransactionConnection:
    """Keep migration callbacks inside the transaction owned by the caller."""

    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def commit(self):
        # Schema initializers commit during normal database creation. During a
        # migration, only the outer transaction may make changes durable.
        return None

    def rollback(self):
        # Let the outer migration handler roll back the complete operation.
        return None

    def executescript(self, sql_script):
        return _execute_script_in_transaction(self._connection, sql_script)


def migrate_sqlite_database_atomically(
    db_path,
    *,
    schema_name,
    target_version,
    source_versions,
    initialize_schema,
    validate_schema,
    validate_source_schema,
    unsupported_version_error,
):
    """Migrate in one writer transaction so concurrent saves cannot be lost."""

    source = os.path.abspath(os.fspath(db_path))
    if not os.path.isfile(source):
        raise FileNotFoundError(source)
    target_version = int(target_version)
    allowed_source_versions = {int(value) for value in source_versions}
    migration_connection = sqlite3.connect(source, timeout=30.0, isolation_level=None)
    migration_connection.execute("PRAGMA foreign_keys = ON")
    migration_connection.execute("PRAGMA busy_timeout = 30000")
    transaction_started = False
    backup_path = ""
    try:
        try:
            migration_connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
        except sqlite3.OperationalError as exc:
            if "busy" in str(exc).lower() or "locked" in str(exc).lower():
                raise sqlite3.OperationalError("sqlite_migration_source_busy") from exc
            raise

        table = migration_connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
        ).fetchone()
        current_version = (
            get_schema_version(migration_connection, schema_name) if table else 0
        )
        if current_version == target_version:
            migration_connection.rollback()
            transaction_started = False
            return {"migrated": False, "backup_path": ""}
        if current_version not in allowed_source_versions:
            raise ValueError(f"{unsupported_version_error}:{current_version}")

        # BEGIN IMMEDIATE keeps every other writer waiting from before this
        # snapshot until the schema transaction commits or rolls back.
        backup_path = backup_sqlite_database(source, min_interval_seconds=0)
        backup_connection = connect_sqlite_database_readonly(backup_path)
        try:
            ensure_integrity_ok(backup_connection)
        finally:
            backup_connection.close()

        transactional_connection = _MigrationTransactionConnection(migration_connection)
        validate_source_schema(transactional_connection, current_version)
        initialize_schema(transactional_connection)
        validate_schema(transactional_connection)
        ensure_integrity_ok(transactional_connection)
        migration_connection.commit()
        transaction_started = False
    except Exception:
        if transaction_started:
            migration_connection.rollback()
        raise
    finally:
        migration_connection.close()
    return {"migrated": True, "backup_path": backup_path}
