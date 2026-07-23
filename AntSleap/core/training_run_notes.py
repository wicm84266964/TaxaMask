"""Editable notes kept separate from immutable training-run facts."""

from __future__ import annotations

import json
import os
import re
import stat
import threading
from contextlib import contextmanager
from pathlib import Path

from AntSleap.core.safe_io import atomic_write_json
from AntSleap.core.training_run_recorder import (
    TRAINING_RUN_LEDGER_FILENAME,
    _connect_training_run_ledger,
)


TRAINING_RUN_NOTE_SCHEMA_VERSION = "taxamask_training_run_note_v1"
TRAINING_RUN_NOTES_DIRNAME = "_training_run_notes"
NOTE_FIELDS = ("purpose", "importance", "conclusion", "follow_up", "note")
MAX_NOTE_FIELD_LENGTH = 4000
NOTE_RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "note_ref",
        "run_id",
        "created_at",
        "updated_at",
        "purpose",
        "importance",
        "conclusion",
        "follow_up",
        "note",
        "has_content",
    }
)
_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?:(?<![^\W_])[A-Za-z]:[\\/]|\\\\|"
    r"(?<![^\W_])(?<!:)/{2}(?=[^/\s])|"
    r"(?<![^\W_])(?<!/)/(?:[^/\s]+(?:/|$))|"
    r"(?<![^\W_])~[\\/])"
)
_SECRET_PATTERN = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|password|secret)\s*[:=]",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERN = re.compile(
    r"(?:\bBearer\s+[A-Za-z0-9._~+/=-]{8,}|"
    r"\bsk-[A-Za-z0-9_-]{8,}|"
    r"\bgh[pousr]_[A-Za-z0-9]{8,}|"
    r"\bAKIA[0-9A-Z]{12,}|"
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)


def _utc_now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _clean_id(value, field_name):
    text = str(value or "").strip()
    if not text or len(text) > 240 or not _ID_PATTERN.fullmatch(text):
        raise ValueError(f"invalid_{field_name}")
    return text


def note_ref_for_run(run_id):
    return f"training_note_{_clean_id(run_id, 'run_id')}"


def sanitize_note_text(value):
    text = str(value or "").replace("\x00", "").strip()
    if len(text) > MAX_NOTE_FIELD_LENGTH:
        text = text[:MAX_NOTE_FIELD_LENGTH]
    if _ABSOLUTE_PATH_PATTERN.search(text):
        raise ValueError("training_note_absolute_path_not_allowed")
    if _SECRET_PATTERN.search(text):
        raise ValueError("training_note_secret_not_allowed")
    if _SECRET_VALUE_PATTERN.search(text):
        raise ValueError("training_note_secret_not_allowed")
    return text


class TrainingRunNoteError(ValueError):
    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def _is_reparse(stat_result):
    attributes = int(getattr(stat_result, "st_file_attributes", 0) or 0)
    flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400) or 0x400)
    return bool(attributes & flag)


class _NoteLock:
    def __init__(self, path):
        self.path = os.path.abspath(os.fspath(path))
        self.handle = None

    def acquire(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if os.path.lexists(self.path):
            result = os.lstat(self.path)
            if stat.S_ISLNK(result.st_mode) or _is_reparse(result) or not stat.S_ISREG(result.st_mode):
                raise TrainingRunNoteError("note_lock_unsafe")
        flags = os.O_RDWR | os.O_CREAT | int(getattr(os, "O_BINARY", 0))
        flags |= int(getattr(os, "O_NOFOLLOW", 0))
        descriptor = os.open(self.path, flags, 0o600)
        handle = os.fdopen(descriptor, "r+b", closefd=True)
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
                os.fsync(handle.fileno())
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError):
            handle.close()
            return False
        self.handle = handle
        return True

    def release(self):
        handle, self.handle = self.handle, None
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except (OSError, IOError):
            pass
        finally:
            handle.close()


class TrainingRunNoteStore:
    """Atomic note store whose references are deterministically bound to run IDs."""

    def __init__(self, runs_root, *, database_path=None):
        self.runs_root = Path(runs_root).resolve()
        self.notes_root = self.runs_root / TRAINING_RUN_NOTES_DIRNAME
        self.database_path = os.path.abspath(
            os.fspath(
                database_path
                or (self.runs_root / TRAINING_RUN_LEDGER_FILENAME)
            )
        )
        self._mutex = threading.RLock()
        self.projection_errors = []
        connection = _connect_training_run_ledger(self.database_path)
        connection.close()

    def _ensure_safe_notes_root(self, *, create):
        if create:
            os.makedirs(self.notes_root, exist_ok=True)
        if not os.path.lexists(self.notes_root):
            return False
        result = os.lstat(self.notes_root)
        if stat.S_ISLNK(result.st_mode) or _is_reparse(result) or not stat.S_ISDIR(
            result.st_mode
        ):
            raise TrainingRunNoteError("notes_root_unsafe")
        resolved = str(self.notes_root.resolve(strict=True))
        try:
            if os.path.normcase(os.path.commonpath([str(self.runs_root), resolved])) != os.path.normcase(
                str(self.runs_root)
            ):
                raise TrainingRunNoteError("notes_root_unsafe")
        except ValueError as exc:
            raise TrainingRunNoteError("notes_root_unsafe") from exc
        return True

    def _read_regular_json(self, path, error_code):
        result = os.lstat(path)
        if stat.S_ISLNK(result.st_mode) or _is_reparse(result) or not stat.S_ISREG(
            result.st_mode
        ):
            raise TrainingRunNoteError(error_code)
        flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
        flags |= int(getattr(os, "O_NOFOLLOW", 0))
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "r", encoding="utf-8", closefd=True) as handle:
            return json.load(handle)

    @contextmanager
    def _activity_guard(self, run_id):
        with self._mutex:
            self._ensure_safe_notes_root(create=True)
            lock = _NoteLock(str(self.path_for_run(run_id)) + ".activity.lock")
            if not lock.acquire():
                raise TrainingRunNoteError("note_busy")
            try:
                yield
            finally:
                lock.release()

    def path_for_run(self, run_id):
        clean_run_id = _clean_id(run_id, "run_id")
        return self.notes_root / f"{note_ref_for_run(clean_run_id)}.json"

    def load(self, run_id):
        clean_run_id = _clean_id(run_id, "run_id")
        connection = _connect_training_run_ledger(self.database_path)
        try:
            row = connection.execute(
                "SELECT note_json FROM training_run_notes WHERE run_id = ?",
                (clean_run_id,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return {}
        try:
            payload = json.loads(str(row["note_json"]))
        except (TypeError, ValueError) as exc:
            raise TrainingRunNoteError("training_run_note_ledger_invalid") from exc
        self._validate_note(payload, run_id)
        self._load_bound_run(run_id)
        return payload

    def save(
        self,
        run_id,
        *,
        purpose=None,
        importance=None,
        conclusion=None,
        follow_up=None,
        note=None,
        expected_updated_at=None,
    ):
        clean_run_id = _clean_id(run_id, "run_id")
        with self._activity_guard(clean_run_id):
            clean_run_id, run_record = self._load_bound_run(clean_run_id)
            note_ref = note_ref_for_run(clean_run_id)
            existing = self.load(clean_run_id)
            if existing:
                if expected_updated_at != existing.get("updated_at"):
                    raise TrainingRunNoteError("note_conflict")
            elif expected_updated_at is not None:
                raise TrainingRunNoteError("note_conflict")
            now = _utc_now()
            payload = {
                "schema_version": TRAINING_RUN_NOTE_SCHEMA_VERSION,
                "note_ref": note_ref,
                "run_id": clean_run_id,
                "created_at": existing.get("created_at") or now,
                "updated_at": now,
            }
            for field, value in (
                ("purpose", purpose),
                ("importance", importance),
                ("conclusion", conclusion),
                ("follow_up", follow_up),
                ("note", note),
            ):
                if value is None:
                    value = existing.get(field, "")
                payload[field] = sanitize_note_text(value)
            payload["has_content"] = any(payload[field] for field in NOTE_FIELDS)
            if run_record.get("note_ref") != note_ref:
                raise ValueError("training_run_note_ref_mismatch")
            note_json = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            connection = _connect_training_run_ledger(self.database_path)
            try:
                with connection:
                    if existing:
                        cursor = connection.execute(
                            """
                            UPDATE training_run_notes
                            SET schema_version = ?, note_ref = ?, updated_at = ?,
                                note_json = ?
                            WHERE run_id = ? AND updated_at = ?
                            """,
                            (
                                TRAINING_RUN_NOTE_SCHEMA_VERSION,
                                note_ref,
                                now,
                                note_json,
                                clean_run_id,
                                expected_updated_at,
                            ),
                        )
                        if cursor.rowcount != 1:
                            raise TrainingRunNoteError("note_conflict")
                    else:
                        connection.execute(
                            """
                            INSERT INTO training_run_notes (
                                run_id, schema_version, note_ref, created_at,
                                updated_at, note_json
                            ) VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                clean_run_id,
                                TRAINING_RUN_NOTE_SCHEMA_VERSION,
                                note_ref,
                                payload["created_at"],
                                now,
                                note_json,
                            ),
                        )
            except TrainingRunNoteError:
                raise
            except Exception as exc:
                raise TrainingRunNoteError("training_run_note_ledger_write_failed") from exc
            finally:
                connection.close()
            try:
                self._ensure_safe_notes_root(create=True)
                atomic_write_json(
                    self.path_for_run(clean_run_id), payload, indent=2
                )
            except Exception as exc:
                self.projection_errors.append(
                    {
                        "run_id": clean_run_id,
                        "error_type": type(exc).__name__,
                    }
                )
            return dict(payload)

    def has_note(self, run_id):
        payload = self.load(run_id)
        return bool(payload.get("has_content"))

    update = save

    def _load_bound_run(self, run_id):
        clean_run_id = _clean_id(run_id, "run_id")
        connection = _connect_training_run_ledger(self.database_path)
        try:
            row = connection.execute(
                "SELECT record_json FROM training_runs WHERE run_id = ?",
                (clean_run_id,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise TrainingRunNoteError("training_run_note_orphan")
        try:
            record = json.loads(str(row["record_json"]))
        except (TypeError, ValueError) as exc:
            raise TrainingRunNoteError(
                "training_run_note_binding_invalid"
            ) from exc
        if (
            not isinstance(record, dict)
            or record.get("schema_version") != "taxamask_training_run_v1"
            or record.get("run_id") != clean_run_id
        ):
            raise ValueError("training_run_note_binding_invalid")
        return clean_run_id, record

    def _validate_note(self, payload, run_id):
        clean_run_id = _clean_id(run_id, "run_id")
        if (
            not isinstance(payload, dict)
            or set(payload) != set(NOTE_RECORD_FIELDS)
            or payload.get("schema_version") != TRAINING_RUN_NOTE_SCHEMA_VERSION
            or payload.get("run_id") != clean_run_id
            or payload.get("note_ref") != note_ref_for_run(clean_run_id)
        ):
            raise ValueError("training_run_note_invalid")
        for field in NOTE_FIELDS:
            sanitize_note_text(payload.get(field, ""))
        if not isinstance(payload.get("has_content"), bool):
            raise ValueError("training_run_note_invalid")
