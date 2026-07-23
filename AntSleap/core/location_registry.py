"""Machine-local SQLite mappings from opaque references to filesystem paths."""

from __future__ import annotations

import datetime as _datetime
import os
import sqlite3
import stat
import unicodedata
import uuid
from pathlib import Path

from .platform_paths import user_config_dir
from .project_traceability import validate_traceability_id


LOCATION_REGISTRY_FILENAME = "location_registry.sqlite"
LOCATION_REGISTRY_SCHEMA_VERSION = 1
LOCATION_ENTRY_KINDS = frozenset({"file", "directory"})

_REQUIRED_TABLES = frozenset({"location_registry_meta", "locations"})
_REQUIRED_COLUMNS = {
    "location_registry_meta": {
        "registry_id",
        "schema_version",
        "created_at",
    },
    "locations": {
        "location_ref",
        "entry_kind",
        "absolute_path",
        "path_key",
        "created_at",
    },
}
_REQUIRED_TRIGGERS = frozenset(
    {
        "trg_locations_immutable_update",
        "trg_locations_immutable_delete",
    }
)


class LocationRegistryError(ValueError):
    def __init__(self, code, summary=None):
        self.code = str(code or "location_registry_error")
        super().__init__(str(summary or self.code))


def _raise(code, summary=None):
    raise LocationRegistryError(code, summary)


def _now_iso():
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def _safe_location_ref(value):
    try:
        return validate_traceability_id(value, "location_ref")
    except ValueError as exc:
        raise LocationRegistryError("invalid_location_ref") from exc


def _clean_entry_kind(value):
    entry_kind = str(value or "").strip()
    if entry_kind not in LOCATION_ENTRY_KINDS:
        _raise("invalid_location_entry_kind")
    return entry_kind


def _is_reparse_point(stat_result):
    attributes = int(getattr(stat_result, "st_file_attributes", 0) or 0)
    flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400) or 0x400)
    return bool(attributes & flag)


def _absolute_path(value):
    try:
        raw = os.fspath(value)
    except TypeError as exc:
        raise LocationRegistryError("invalid_location_path") from exc
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        _raise("invalid_location_path")
    if any(ord(character) < 32 or ord(character) == 127 for character in raw):
        _raise("invalid_location_path")
    return os.path.abspath(raw)


def _absolute_chain(path):
    absolute = _absolute_path(path)
    drive, tail = os.path.splitdrive(absolute)
    anchor = f"{drive}{os.sep}" if drive else os.sep
    relative = tail.lstrip("\\/")
    current = anchor
    yield current
    for part in [item for item in relative.replace("\\", "/").split("/") if item]:
        current = os.path.join(current, part)
        yield current


def _entry_kind(stat_result):
    if stat.S_ISREG(stat_result.st_mode):
        return "file"
    if stat.S_ISDIR(stat_result.st_mode):
        return "directory"
    _raise("location_special_entry_not_allowed")


def _require_safe_existing_path(path, *, expected_kind=None):
    clean_kind = _clean_entry_kind(expected_kind) if expected_kind else None
    chain = list(_absolute_chain(path))
    absolute = chain[-1]
    for index, current in enumerate(chain):
        is_target = index == len(chain) - 1
        try:
            result = os.lstat(current)
        except FileNotFoundError as exc:
            raise LocationRegistryError("location_path_missing") from exc
        except OSError as exc:
            raise LocationRegistryError("location_path_unreadable") from exc
        if stat.S_ISLNK(result.st_mode) or _is_reparse_point(result):
            _raise("location_link_not_allowed")
        observed_kind = _entry_kind(result)
        if not is_target and observed_kind != "directory":
            _raise("location_parent_not_directory")
        if is_target and clean_kind and observed_kind != clean_kind:
            _raise("location_kind_mismatch")
    return absolute


def _ensure_safe_directory(path):
    absolute = _absolute_path(path)
    for current in _absolute_chain(absolute):
        if not os.path.lexists(current):
            try:
                os.mkdir(current)
            except FileExistsError:
                pass
            except OSError as exc:
                raise LocationRegistryError(
                    "location_registry_directory_create_failed"
                ) from exc
        _require_safe_existing_path(current, expected_kind="directory")
    return absolute


def _path_key(path):
    normalised = os.path.normcase(os.path.normpath(_absolute_path(path)))
    return unicodedata.normalize("NFC", normalised)


def default_location_registry_path(config_dir=None):
    root = Path(config_dir) if config_dir is not None else user_config_dir()
    return root / LOCATION_REGISTRY_FILENAME


def _database_path(database_path=None):
    return _absolute_path(
        database_path
        if database_path is not None
        else default_location_registry_path()
    )


def _prepare_database_file(database_path):
    path = _database_path(database_path)
    _ensure_safe_directory(os.path.dirname(path) or os.curdir)
    if os.path.lexists(path):
        return _require_safe_existing_path(path, expected_kind="file")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    flags |= int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        return _require_safe_existing_path(path, expected_kind="file")
    except OSError as exc:
        raise LocationRegistryError("location_registry_create_failed") from exc
    else:
        os.close(descriptor)
    return _require_safe_existing_path(path, expected_kind="file")


def _initialize_schema(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS location_registry_meta (
            registry_id INTEGER PRIMARY KEY CHECK (registry_id = 1),
            schema_version INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS locations (
            location_ref TEXT PRIMARY KEY,
            entry_kind TEXT NOT NULL CHECK (entry_kind IN ('file', 'directory')),
            absolute_path TEXT NOT NULL,
            path_key TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_locations_immutable_update
        BEFORE UPDATE ON locations
        BEGIN
            SELECT RAISE(ABORT, 'location_mapping_immutable');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_locations_immutable_delete
        BEFORE DELETE ON locations
        BEGIN
            SELECT RAISE(ABORT, 'location_mapping_immutable');
        END
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO location_registry_meta (
            registry_id, schema_version, created_at
        ) VALUES (1, ?, ?)
        """,
        (LOCATION_REGISTRY_SCHEMA_VERSION, _now_iso()),
    )


def validate_location_registry_schema(connection):
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if _REQUIRED_TABLES - tables:
        _raise("missing_location_registry_tables")
    for table_name, required in _REQUIRED_COLUMNS.items():
        columns = {
            str(row[1])
            for row in connection.execute(
                f"PRAGMA table_info({table_name})"
            ).fetchall()
        }
        if required - columns:
            _raise("missing_location_registry_columns")
    triggers = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        ).fetchall()
    }
    if _REQUIRED_TRIGGERS - triggers:
        _raise("missing_location_registry_triggers")
    row = connection.execute(
        """
        SELECT schema_version FROM location_registry_meta
        WHERE registry_id = 1
        """
    ).fetchone()
    if row is None or int(row[0] or 0) != LOCATION_REGISTRY_SCHEMA_VERSION:
        _raise("unsupported_location_registry_schema_version")
    return True


def _require_integrity_ok(connection):
    result = [str(row[0]) for row in connection.execute("PRAGMA quick_check")]
    if result != ["ok"]:
        _raise("location_registry_integrity_check_failed")


def connect_location_registry(database_path=None):
    path = _prepare_database_file(database_path)
    connection = None
    try:
        connection = sqlite3.connect(path, timeout=5.0)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA busy_timeout = 5000")
        _require_safe_existing_path(path, expected_kind="file")
        with connection:
            _initialize_schema(connection)
            validate_location_registry_schema(connection)
        _require_integrity_ok(connection)
        return connection
    except LocationRegistryError:
        if connection is not None:
            connection.close()
        raise
    except sqlite3.DatabaseError as exc:
        if connection is not None:
            connection.close()
        raise LocationRegistryError("location_registry_database_invalid") from exc


def _connect_location_registry_readonly(database_path=None):
    path = _database_path(database_path)
    if not os.path.lexists(path):
        _raise("location_registry_missing")
    _require_safe_existing_path(path, expected_kind="file")
    connection = None
    try:
        connection = sqlite3.connect(f"{Path(path).as_uri()}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        _require_safe_existing_path(path, expected_kind="file")
        validate_location_registry_schema(connection)
        _require_integrity_ok(connection)
        return connection
    except LocationRegistryError:
        if connection is not None:
            connection.close()
        raise
    except sqlite3.DatabaseError as exc:
        if connection is not None:
            connection.close()
        raise LocationRegistryError("location_registry_database_invalid") from exc


def _validate_registered_path(path, entry_kind, expected_path_key):
    observed = _require_safe_existing_path(path, expected_kind=entry_kind)
    if _path_key(observed) != expected_path_key:
        _raise("location_changed_during_registration")
    return observed


def register_location(
    path,
    *,
    entry_kind,
    location_ref=None,
    database_path=None,
):
    """Register an immutable machine-local path and return its opaque ID."""

    clean_kind = _clean_entry_kind(entry_kind)
    absolute = _require_safe_existing_path(path, expected_kind=clean_kind)
    clean_ref = _safe_location_ref(location_ref) if location_ref else None
    path_key = _path_key(absolute)
    connection = connect_location_registry(database_path)
    try:
        with connection:
            existing_path = connection.execute(
                """
                SELECT location_ref, entry_kind, absolute_path
                FROM locations WHERE path_key = ?
                """,
                (path_key,),
            ).fetchone()
            if existing_path:
                existing_ref = str(existing_path[0])
                if str(existing_path[1]) != clean_kind:
                    _raise("location_kind_conflict")
                if clean_ref and clean_ref != existing_ref:
                    _raise("location_path_already_registered")
                _validate_registered_path(
                    str(existing_path[2]), clean_kind, path_key
                )
                return existing_ref

            if clean_ref:
                existing_ref = connection.execute(
                    """
                    SELECT entry_kind, absolute_path, path_key
                    FROM locations WHERE location_ref = ?
                    """,
                    (clean_ref,),
                ).fetchone()
                if existing_ref:
                    _raise("location_ref_conflict")
            else:
                clean_ref = _safe_location_ref(f"location_{uuid.uuid4().hex}")

            connection.execute(
                """
                INSERT INTO locations (
                    location_ref, entry_kind, absolute_path, path_key, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (clean_ref, clean_kind, absolute, path_key, _now_iso()),
            )
            _validate_registered_path(absolute, clean_kind, path_key)
        return clean_ref
    finally:
        connection.close()


def _resolve_records(location_refs, database_path=None):
    clean_refs = [_safe_location_ref(value) for value in location_refs]
    if not clean_refs:
        return {}
    connection = _connect_location_registry_readonly(database_path)
    try:
        resolved = {}
        for location_ref in clean_refs:
            row = connection.execute(
                """
                SELECT entry_kind, absolute_path, path_key
                FROM locations WHERE location_ref = ?
                """,
                (location_ref,),
            ).fetchone()
            if not row:
                _raise("location_ref_not_found")
            entry_kind = _clean_entry_kind(row[0])
            stored_path = str(row[1] or "")
            if not os.path.isabs(stored_path):
                _raise("stored_location_path_invalid")
            if _path_key(stored_path) != str(row[2] or ""):
                _raise("stored_location_path_invalid")
            absolute = _require_safe_existing_path(
                stored_path, expected_kind=entry_kind
            )
            resolved[location_ref] = {
                "entry_kind": entry_kind,
                "path": Path(absolute),
            }
        return resolved
    finally:
        connection.close()


def resolve_location(
    location_ref,
    *,
    expected_kind=None,
    database_path=None,
):
    clean_ref = _safe_location_ref(location_ref)
    expected = _clean_entry_kind(expected_kind) if expected_kind else None
    record = _resolve_records([clean_ref], database_path)[clean_ref]
    if expected and record["entry_kind"] != expected:
        _raise("location_kind_mismatch")
    return record["path"]


def resolve_locations(location_refs, *, database_path=None):
    """Resolve opaque IDs for runtime use without serialising their paths."""

    if isinstance(location_refs, (str, bytes)):
        _raise("invalid_location_ref_collection")
    records = _resolve_records(list(location_refs), database_path)
    return {location_ref: record["path"] for location_ref, record in records.items()}


__all__ = [
    "LOCATION_ENTRY_KINDS",
    "LOCATION_REGISTRY_FILENAME",
    "LOCATION_REGISTRY_SCHEMA_VERSION",
    "LocationRegistryError",
    "connect_location_registry",
    "default_location_registry_path",
    "register_location",
    "resolve_location",
    "resolve_locations",
    "validate_location_registry_schema",
]
