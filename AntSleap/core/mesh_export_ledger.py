from __future__ import annotations

import datetime as _datetime
import json
import re
import sqlite3
from pathlib import PurePosixPath

from .sqlite_storage import connect_sqlite_database


MESH_EXPORT_SCHEMA_VERSION = "taxamask_mesh_export_sqlite_v1"
MESH_EXPORT_STATUSES = frozenset(
    {"pending", "running", "complete", "incomplete", "failed"}
)
MESH_ITEM_KINDS = frozenset({"raw", "preview"})
_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,240}$")

_REQUIRED_TABLES = {
    "mesh_export_runs",
    "mesh_export_items",
    "mesh_export_reviews",
}


class MeshExportLedgerError(ValueError):
    pass


def _now_iso():
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def _safe_id(value, field):
    text = str(value or "").strip()
    if not _ID_RE.fullmatch(text):
        raise MeshExportLedgerError(f"invalid_{field}")
    return text


def _relative_path(value, field):
    text = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(text)
    if (
        not text
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or ":" in path.parts[0]
    ):
        raise MeshExportLedgerError(f"invalid_{field}")
    return path.as_posix()


def _json_text(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def initialize_mesh_export_schema(connection):
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS mesh_export_runs (
            export_id TEXT PRIMARY KEY,
            record_schema_version TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('pending', 'running', 'complete', 'incomplete', 'failed')
            ),
            retry_of TEXT,
            attempt INTEGER NOT NULL DEFAULT 1 CHECK (attempt >= 1),
            project_id TEXT NOT NULL,
            specimen_id TEXT NOT NULL,
            part_id TEXT NOT NULL DEFAULT '',
            reslice_id TEXT NOT NULL DEFAULT '',
            source_data_version_id TEXT NOT NULL,
            target_location_ref TEXT NOT NULL,
            target_path_base TEXT NOT NULL DEFAULT 'external_location',
            target_relative_path TEXT NOT NULL,
            source_relative_path TEXT NOT NULL,
            source_entry_kind TEXT NOT NULL CHECK (
                source_entry_kind IN ('file', 'directory')
            ),
            source_size_bytes INTEGER NOT NULL CHECK (source_size_bytes >= 0),
            source_hash_algorithm TEXT NOT NULL,
            source_digest TEXT NOT NULL,
            source_hashed_at TEXT NOT NULL,
            coordinates_json TEXT NOT NULL,
            requested_labels_json TEXT NOT NULL,
            options_json TEXT NOT NULL DEFAULT '{}',
            stl_item_count INTEGER NOT NULL DEFAULT 0 CHECK (stl_item_count >= 0),
            completed_item_count INTEGER NOT NULL DEFAULT 0 CHECK (completed_item_count >= 0),
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            error_code TEXT NOT NULL DEFAULT '',
            error_summary TEXT NOT NULL DEFAULT '',
            error_stage TEXT NOT NULL DEFAULT '',
            recoverable INTEGER NOT NULL DEFAULT 1 CHECK (recoverable IN (0, 1)),
            recovery_action TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (retry_of) REFERENCES mesh_export_runs(export_id)
        );

        CREATE TABLE IF NOT EXISTS mesh_export_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            export_id TEXT NOT NULL,
            artifact_id TEXT NOT NULL,
            label_id INTEGER NOT NULL,
            label_name TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('raw', 'preview')),
            role TEXT NOT NULL DEFAULT 'mesh',
            relative_path TEXT NOT NULL,
            entry_kind TEXT NOT NULL DEFAULT 'file' CHECK (entry_kind = 'file'),
            size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
            hash_algorithm TEXT NOT NULL DEFAULT 'sha256',
            digest TEXT NOT NULL,
            vertex_count INTEGER NOT NULL CHECK (vertex_count >= 0),
            face_count INTEGER NOT NULL CHECK (face_count >= 0),
            bounds_xyz_mm_json TEXT NOT NULL,
            component_count INTEGER NOT NULL CHECK (component_count >= 0),
            watertight INTEGER NOT NULL CHECK (watertight IN (0, 1)),
            scale_status TEXT NOT NULL,
            processing_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (export_id, artifact_id),
            UNIQUE (export_id, relative_path),
            FOREIGN KEY (export_id) REFERENCES mesh_export_runs(export_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS mesh_export_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            export_id TEXT NOT NULL,
            review_status TEXT NOT NULL CHECK (
                review_status IN ('verified', 'needs_attention')
            ),
            error_code TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '',
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (export_id) REFERENCES mesh_export_runs(export_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_mesh_export_runs_status
        ON mesh_export_runs(status);
        CREATE INDEX IF NOT EXISTS idx_mesh_export_runs_specimen
        ON mesh_export_runs(specimen_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_mesh_export_items_export
        ON mesh_export_items(export_id, label_id, kind);
        CREATE INDEX IF NOT EXISTS idx_mesh_export_reviews_export
        ON mesh_export_reviews(export_id, created_at);
        """
    )
    run_columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(mesh_export_runs)").fetchall()
    }
    if "options_json" not in run_columns:
        connection.execute(
            "ALTER TABLE mesh_export_runs ADD COLUMN options_json TEXT NOT NULL DEFAULT '{}'"
        )


def validate_mesh_export_schema(connection):
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    missing = sorted(_REQUIRED_TABLES - tables)
    if missing:
        raise MeshExportLedgerError(
            f"missing_mesh_export_tables:{','.join(missing)}"
        )
    return True


class MeshExportLedger:
    def __init__(self, database_path):
        self.database_path = str(database_path)
        connection = self._connect()
        connection.close()

    def _connect(self):
        connection = connect_sqlite_database(self.database_path)
        connection.row_factory = sqlite3.Row
        with connection:
            initialize_mesh_export_schema(connection)
            validate_mesh_export_schema(connection)
        return connection

    def create_pending(self, record):
        source = dict(record or {})
        export_id = _safe_id(source.get("export_id"), "export_id")
        retry_of = (
            _safe_id(source.get("retry_of"), "retry_of")
            if source.get("retry_of")
            else None
        )
        created_at = str(source.get("created_at") or _now_iso())
        connection = self._connect()
        try:
            with connection:
                if retry_of:
                    prior = connection.execute(
                        """
                        SELECT status, attempt, project_id, specimen_id, part_id,
                               reslice_id, source_digest, requested_labels_json,
                               options_json
                        FROM mesh_export_runs WHERE export_id = ?
                        """,
                        (retry_of,),
                    ).fetchone()
                    if prior is None or str(prior[0]) not in {
                        "incomplete",
                        "failed",
                    }:
                        raise MeshExportLedgerError(
                            "retry_requires_incomplete_or_failed_export"
                        )
                    current_scope = (
                        str(source.get("project_id") or ""),
                        str(source.get("specimen_id") or ""),
                        str(source.get("part_id") or ""),
                        str(source.get("reslice_id") or ""),
                    )
                    prior_scope = tuple(
                        str(prior[index] or "") for index in range(2, 6)
                    )
                    if prior_scope != current_scope:
                        raise MeshExportLedgerError(
                            "retry_scope_changed_create_new_export"
                        )
                    if str(prior[6] or "") != str(
                        source.get("source_digest") or ""
                    ):
                        raise MeshExportLedgerError(
                            "retry_source_changed_create_new_export"
                        )
                    prior_label_ids = sorted(
                        int(item["label_id"])
                        for item in json.loads(str(prior[7] or "[]"))
                    )
                    current_label_ids = sorted(
                        int(item["label_id"])
                        for item in (source.get("requested_labels") or [])
                    )
                    if prior_label_ids != current_label_ids:
                        raise MeshExportLedgerError(
                            "retry_labels_changed_create_new_export"
                        )
                    prior_options = json.loads(str(prior[8] or "{}"))
                    if prior_options != dict(source.get("options") or {}):
                        raise MeshExportLedgerError(
                            "retry_options_changed_create_new_export"
                        )
                    attempt = int(prior[1]) + 1
                else:
                    attempt = int(source.get("attempt") or 1)
                connection.execute(
                    """
                    INSERT INTO mesh_export_runs (
                        export_id, record_schema_version, status, retry_of, attempt,
                        project_id, specimen_id, part_id, reslice_id,
                        source_data_version_id, target_location_ref,
                        target_path_base, target_relative_path,
                        source_relative_path, source_entry_kind,
                        source_size_bytes, source_hash_algorithm, source_digest,
                        source_hashed_at, coordinates_json, requested_labels_json,
                        options_json, created_at
                    ) VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        export_id,
                        MESH_EXPORT_SCHEMA_VERSION,
                        retry_of,
                        attempt,
                        _safe_id(source.get("project_id"), "project_id"),
                        _safe_id(source.get("specimen_id"), "specimen_id"),
                        str(source.get("part_id") or ""),
                        str(source.get("reslice_id") or ""),
                        _safe_id(
                            source.get("source_data_version_id"),
                            "source_data_version_id",
                        ),
                        _safe_id(
                            source.get("target_location_ref"),
                            "target_location_ref",
                        ),
                        "external_location",
                        _relative_path(
                            source.get("target_relative_path"),
                            "target_relative_path",
                        ),
                        _relative_path(
                            source.get("source_relative_path"),
                            "source_relative_path",
                        ),
                        str(source.get("source_entry_kind") or ""),
                        int(source.get("source_size_bytes") or 0),
                        str(source.get("source_hash_algorithm") or ""),
                        str(source.get("source_digest") or ""),
                        str(source.get("source_hashed_at") or created_at),
                        _json_text(source.get("coordinates") or {}),
                        _json_text(source.get("requested_labels") or []),
                        _json_text(source.get("options") or {}),
                        created_at,
                    ),
                )
            return self.load(export_id)
        finally:
            connection.close()

    def mark_running(self, export_id):
        return self._transition(
            export_id,
            from_statuses={"pending", "incomplete"},
            status="running",
            started_at=_now_iso(),
            finished_at=None,
            error_code="",
            error_summary="",
            error_stage="",
            recovery_action="",
        )

    def add_item(self, export_id, item):
        clean_export_id = _safe_id(export_id, "export_id")
        source = dict(item or {})
        kind = str(source.get("kind") or "")
        if kind not in MESH_ITEM_KINDS:
            raise MeshExportLedgerError("invalid_mesh_item_kind")
        connection = self._connect()
        try:
            with connection:
                row = connection.execute(
                    "SELECT status FROM mesh_export_runs WHERE export_id = ?",
                    (clean_export_id,),
                ).fetchone()
                if row is None or str(row[0]) not in {"running", "incomplete"}:
                    raise MeshExportLedgerError("mesh_item_run_not_writable")
                connection.execute(
                    """
                    INSERT INTO mesh_export_items (
                        export_id, artifact_id, label_id, label_name, kind,
                        relative_path, size_bytes, hash_algorithm, digest,
                        vertex_count, face_count, bounds_xyz_mm_json,
                        component_count, watertight, scale_status,
                        processing_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        clean_export_id,
                        _safe_id(source.get("artifact_id"), "artifact_id"),
                        int(source.get("label_id")),
                        str(source.get("label_name") or ""),
                        kind,
                        _relative_path(source.get("relative_path"), "relative_path"),
                        int(source.get("size_bytes") or 0),
                        str(source.get("hash_algorithm") or "sha256"),
                        str(source.get("digest") or ""),
                        int(source.get("vertex_count") or 0),
                        int(source.get("face_count") or 0),
                        _json_text(source.get("bounds_xyz_mm") or []),
                        int(source.get("component_count") or 0),
                        int(bool(source.get("watertight"))),
                        str(source.get("scale_status") or ""),
                        _json_text(source.get("processing") or {}),
                        str(source.get("created_at") or _now_iso()),
                    ),
                )
            return self.load(clean_export_id)
        finally:
            connection.close()

    def finish(
        self,
        export_id,
        status,
        *,
        error_code="",
        error_summary="",
        error_stage="",
        recoverable=True,
        recovery_action="",
    ):
        clean_status = str(status or "")
        if clean_status not in {"complete", "incomplete", "failed"}:
            raise MeshExportLedgerError("invalid_mesh_export_finish_status")
        record = self.load(export_id)
        item_count = len(record["items"])
        if clean_status == "complete" and item_count == 0:
            raise MeshExportLedgerError("complete_mesh_export_requires_items")
        return self._transition(
            export_id,
            from_statuses={"pending", "running", "incomplete"},
            status=clean_status,
            finished_at=_now_iso(),
            stl_item_count=item_count,
            completed_item_count=item_count if clean_status == "complete" else 0,
            error_code=str(error_code or ""),
            error_summary=str(error_summary or "")[:1000],
            error_stage=str(error_stage or ""),
            recoverable=int(bool(recoverable)),
            recovery_action=str(recovery_action or ""),
        )

    def _transition(self, export_id, *, from_statuses, status, **fields):
        clean_export_id = _safe_id(export_id, "export_id")
        if status not in MESH_EXPORT_STATUSES:
            raise MeshExportLedgerError("invalid_mesh_export_status")
        allowed_fields = {
            "started_at",
            "finished_at",
            "stl_item_count",
            "completed_item_count",
            "error_code",
            "error_summary",
            "error_stage",
            "recoverable",
            "recovery_action",
        }
        if set(fields) - allowed_fields:
            raise MeshExportLedgerError("invalid_mesh_export_transition_field")
        assignments = ["status = ?"]
        values = [status]
        for key, value in fields.items():
            assignments.append(f"{key} = ?")
            values.append(value)
        placeholders = ",".join("?" for _ in from_statuses)
        values.extend([clean_export_id, *sorted(from_statuses)])
        connection = self._connect()
        try:
            with connection:
                cursor = connection.execute(
                    f"""
                    UPDATE mesh_export_runs SET {', '.join(assignments)}
                    WHERE export_id = ? AND status IN ({placeholders})
                    """,
                    tuple(values),
                )
                if cursor.rowcount != 1:
                    raise MeshExportLedgerError("invalid_mesh_export_transition")
            return self.load(clean_export_id)
        finally:
            connection.close()

    def add_review(self, export_id, status, *, error_code="", summary="", details=None):
        clean_export_id = _safe_id(export_id, "export_id")
        if status not in {"verified", "needs_attention"}:
            raise MeshExportLedgerError("invalid_mesh_export_review_status")
        connection = self._connect()
        try:
            with connection:
                exists = connection.execute(
                    "SELECT 1 FROM mesh_export_runs WHERE export_id = ?",
                    (clean_export_id,),
                ).fetchone()
                if not exists:
                    raise MeshExportLedgerError("mesh_export_not_found")
                connection.execute(
                    """
                    INSERT INTO mesh_export_reviews (
                        export_id, review_status, error_code, summary,
                        details_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        clean_export_id,
                        status,
                        str(error_code or ""),
                        str(summary or "")[:1000],
                        _json_text(details or {}),
                        _now_iso(),
                    ),
                )
            return self.load(clean_export_id)
        finally:
            connection.close()

    def load(self, export_id):
        clean_export_id = _safe_id(export_id, "export_id")
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM mesh_export_runs WHERE export_id = ?",
                (clean_export_id,),
            ).fetchone()
            if row is None:
                raise MeshExportLedgerError("mesh_export_not_found")
            record = dict(row)
            for key in ("coordinates_json", "requested_labels_json", "options_json"):
                record[key.removesuffix("_json")] = json.loads(record.pop(key))
            record["items"] = []
            for item_row in connection.execute(
                "SELECT * FROM mesh_export_items WHERE export_id = ? ORDER BY id",
                (clean_export_id,),
            ).fetchall():
                item = dict(item_row)
                item["bounds_xyz_mm"] = json.loads(
                    item.pop("bounds_xyz_mm_json")
                )
                item["processing"] = json.loads(item.pop("processing_json"))
                item["watertight"] = bool(item["watertight"])
                record["items"].append(item)
            record["reviews"] = []
            for review_row in connection.execute(
                "SELECT * FROM mesh_export_reviews WHERE export_id = ? ORDER BY id",
                (clean_export_id,),
            ).fetchall():
                review = dict(review_row)
                review["details"] = json.loads(review.pop("details_json"))
                record["reviews"].append(review)
            return record
        finally:
            connection.close()

    def list_exports(
        self,
        *,
        specimen_id="",
        part_id=None,
        reslice_id=None,
        statuses=(),
    ):
        clauses = []
        values = []
        if specimen_id:
            clauses.append("specimen_id = ?")
            values.append(str(specimen_id))
        if part_id is not None:
            clauses.append("part_id = ?")
            values.append(str(part_id or ""))
        if reslice_id is not None:
            clauses.append("reslice_id = ?")
            values.append(str(reslice_id or ""))
        clean_statuses = [str(value) for value in statuses if str(value)]
        if clean_statuses:
            if any(value not in MESH_EXPORT_STATUSES for value in clean_statuses):
                raise MeshExportLedgerError("invalid_mesh_export_status_filter")
            clauses.append(
                f"status IN ({','.join('?' for _ in clean_statuses)})"
            )
            values.extend(clean_statuses)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        connection = self._connect()
        try:
            rows = connection.execute(
                f"SELECT export_id FROM mesh_export_runs {where} ORDER BY created_at DESC",
                tuple(values),
            ).fetchall()
        finally:
            connection.close()
        return [self.load(str(row[0])) for row in rows]


__all__ = [
    "MESH_EXPORT_SCHEMA_VERSION",
    "MESH_EXPORT_STATUSES",
    "MeshExportLedger",
    "MeshExportLedgerError",
    "initialize_mesh_export_schema",
    "validate_mesh_export_schema",
]
