"""Crash-recoverable publication of training weights into managed storage.

The publisher deliberately stops at the managed-model boundary.  Training
entrypoints remain responsible for registering the returned file artifacts in
their training run, marking that run successful, and then calling
``activate``.  Only individual weight files are returned as run artifacts;
the mutable ``publication.json`` state file is never one of them.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from AntSleap.core.file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from AntSleap.core.integrity_manifest_service import (
    IntegrityManifestError,
    validate_relative_path,
)
from AntSleap.core.safe_io import atomic_write_json


PUBLICATION_SCHEMA_VERSION = "taxamask_training_weight_publication_v1"
PUBLICATION_FILENAME = "publication.json"
PUBLICATION_STATUS_PENDING = "pending_activation"
PUBLICATION_STATUS_ACTIVE = "active"
TRAINING_BUNDLE_DIRECTORY = "training_runs"
PUBLICATION_LOCK_FILENAME = ".training_weight_publication.lock"

_TEMP_DIRECTORY_PREFIX = ".taxamask-weight-publish-"
_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_HEX_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_TYPE_PATTERN = re.compile(
    r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$"
)
_TERMINAL_FAILURE_STATUSES = frozenset(
    {"failed", "cancelled", "interrupted"}
)
_LIVE_RUN_STATUSES = frozenset({"pending", "running"})
_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "status",
        "created_at",
        "activated_at",
        "artifacts",
    }
)
_ARTIFACT_FIELDS = frozenset(
    {
        "artifact_id",
        "role",
        "path_base",
        "relative_path",
        "entry_kind",
        "size_bytes",
        "hash_algorithm",
        "digest",
        "media_type",
    }
)
_ARTIFACT_INPUT_FIELDS = frozenset(
    {"artifact_id", "role", "relative_path", "media_type"}
)


class TrainingWeightPublicationError(RuntimeError):
    """Base error for a rejected or incomplete weight publication."""

    def __init__(self, code, summary, *, recoverable=True):
        super().__init__(summary)
        self.code = str(code)
        self.summary = str(summary)
        self.recoverable = bool(recoverable)


class UnsafePublicationEntry(TrainingWeightPublicationError):
    """A path, link, special entry, or persisted field is unsafe."""


class PublicationAlreadyExists(TrainingWeightPublicationError):
    """The run already owns a final or unfinished publication."""


class PublicationIntegrityError(TrainingWeightPublicationError):
    """Copied content or a publication manifest failed verification."""


class ActivePublicationImmutable(TrainingWeightPublicationError):
    """An active publication cannot be overwritten or rewritten."""


class PublicationLockBusy(TrainingWeightPublicationError):
    """Another GUI or headless process currently owns the publication root."""


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _validate_id(value, field_name):
    text = str(value or "").strip()
    if not text or len(text) > 240 or not _ID_PATTERN.fullmatch(text):
        raise UnsafePublicationEntry(
            f"invalid_{field_name}",
            f"The {field_name} is not a safe stable identifier.",
            recoverable=False,
        )
    return text


def _validate_relative(value):
    if not isinstance(value, str):
        raise UnsafePublicationEntry(
            "invalid_relative_path",
            "A publication artifact path is invalid.",
            recoverable=False,
        )
    try:
        return validate_relative_path(value)
    except IntegrityManifestError as exc:
        raise UnsafePublicationEntry(
            "invalid_relative_path",
            "A publication artifact path is invalid.",
            recoverable=False,
        ) from exc


def _is_reparse_point(stat_result):
    attributes = int(getattr(stat_result, "st_file_attributes", 0) or 0)
    flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400) or 0x400)
    return bool(attributes & flag)


def _safe_lstat(path):
    try:
        result = os.lstat(os.fspath(path))
    except OSError as exc:
        raise UnsafePublicationEntry(
            "filesystem_entry_unavailable",
            "A required publication filesystem entry is unavailable.",
        ) from exc
    if stat.S_ISLNK(result.st_mode) or _is_reparse_point(result):
        raise UnsafePublicationEntry(
            "filesystem_link_not_allowed",
            "Links and filesystem reparse points are not allowed in a publication.",
            recoverable=False,
        )
    return result


def _require_directory(path):
    result = _safe_lstat(path)
    if not stat.S_ISDIR(result.st_mode):
        raise UnsafePublicationEntry(
            "safe_directory_required",
            "A publication path must be a normal directory.",
            recoverable=False,
        )
    return result


def _require_regular_file(path):
    result = _safe_lstat(path)
    if not stat.S_ISREG(result.st_mode):
        raise UnsafePublicationEntry(
            "safe_regular_file_required",
            "A publication artifact must be a normal file.",
            recoverable=False,
        )
    return result


def _require_existing_components_safe(path):
    """Reject a managed root reached through an existing link or reparse point."""

    absolute = os.path.abspath(os.fspath(path))
    drive, tail = os.path.splitdrive(absolute)
    if tail.startswith((os.sep, os.altsep or os.sep)):
        current = drive + os.sep
        tail = tail.lstrip("\\/")
    else:
        current = drive or os.curdir
    for segment in [part for part in re.split(r"[\\/]", tail) if part]:
        current = os.path.join(current, segment)
        if os.path.lexists(current):
            result = os.lstat(current)
            if stat.S_ISLNK(result.st_mode) or _is_reparse_point(result):
                raise UnsafePublicationEntry(
                    "filesystem_link_not_allowed",
                    "The managed model path contains a link or reparse point.",
                    recoverable=False,
                )


def _join_under(root, relative_path):
    clean = _validate_relative(relative_path)
    root_abs = os.path.abspath(os.fspath(root))
    target = os.path.abspath(os.path.join(root_abs, *clean.split("/")))
    try:
        inside = os.path.normcase(os.path.commonpath([root_abs, target])) == os.path.normcase(
            root_abs
        )
    except ValueError:
        inside = False
    if not inside:
        raise UnsafePublicationEntry(
            "path_outside_publication_root",
            "A publication artifact path leaves its managed root.",
            recoverable=False,
        )
    return target, clean


def _require_safe_source(root, relative_path):
    target, clean = _join_under(root, relative_path)
    current = os.path.abspath(os.fspath(root))
    _require_directory(current)
    parts = clean.split("/")
    for segment in parts[:-1]:
        current = os.path.join(current, segment)
        _require_directory(current)
    _require_regular_file(target)
    return target


def _safe_read_json(path):
    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    try:
        descriptor = os.open(os.fspath(path), flags)
        with os.fdopen(descriptor, "r", encoding="utf-8", closefd=True) as handle:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode) or _is_reparse_point(opened):
                raise UnsafePublicationEntry(
                    "safe_regular_file_required",
                    "The publication manifest must be a normal file.",
                    recoverable=False,
                )
            payload = json.load(handle)
    except TrainingWeightPublicationError:
        raise
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise PublicationIntegrityError(
            "publication_manifest_unreadable",
            "The publication manifest is missing or unreadable.",
        ) from exc
    if not isinstance(payload, dict):
        raise PublicationIntegrityError(
            "publication_manifest_invalid",
            "The publication manifest is invalid.",
            recoverable=False,
        )
    return payload


def _scan_safe_tree(root):
    """Return relative regular files and directories without following links."""

    root_abs = os.path.abspath(os.fspath(root))
    _require_directory(root_abs)
    files = set()
    directories = set()
    stack = [(root_abs, "")]
    while stack:
        physical, relative = stack.pop()
        try:
            children = list(os.scandir(physical))
        except OSError as exc:
            raise UnsafePublicationEntry(
                "publication_tree_unreadable",
                "The publication directory cannot be inspected safely.",
            ) from exc
        for child in children:
            try:
                result = child.stat(follow_symlinks=False)
            except OSError as exc:
                raise UnsafePublicationEntry(
                    "publication_tree_unreadable",
                    "The publication directory changed during inspection.",
                ) from exc
            if child.is_symlink() or _is_reparse_point(result):
                raise UnsafePublicationEntry(
                    "filesystem_link_not_allowed",
                    "The publication contains a link or reparse point.",
                    recoverable=False,
                )
            child_relative = (
                f"{relative}/{child.name}" if relative else child.name
            ).replace("\\", "/")
            if stat.S_ISDIR(result.st_mode):
                directories.add(child_relative)
                stack.append((child.path, child_relative))
            elif stat.S_ISREG(result.st_mode):
                files.add(child_relative)
            else:
                raise UnsafePublicationEntry(
                    "special_filesystem_entry_not_allowed",
                    "The publication contains a special filesystem entry.",
                    recoverable=False,
                )
    return files, directories


def _remove_safe_tree(root):
    """Delete a previously safe tree while rechecking every removed entry."""

    root_abs = os.path.abspath(os.fspath(root))
    files, directories = _scan_safe_tree(root_abs)
    for relative in sorted(files, key=lambda item: (item.count("/"), item), reverse=True):
        target, _clean = _join_under(root_abs, relative)
        _require_regular_file(target)
        os.unlink(target)
    for relative in sorted(
        directories, key=lambda item: (item.count("/"), item), reverse=True
    ):
        target, _clean = _join_under(root_abs, relative)
        _require_directory(target)
        os.rmdir(target)
    _require_directory(root_abs)
    os.rmdir(root_abs)


def _fsync_directory(path):
    try:
        descriptor = os.open(os.fspath(path), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


class _ManagedPublicationLock:
    """A non-blocking, process-wide lock stored inside the managed model root."""

    def __init__(self, path):
        self.path = os.path.abspath(os.fspath(path))
        self.handle = None

    def acquire(self):
        if os.path.lexists(self.path):
            _require_regular_file(self.path)
        flags = os.O_RDWR | os.O_CREAT | int(getattr(os, "O_BINARY", 0))
        flags |= int(getattr(os, "O_NOFOLLOW", 0))
        try:
            descriptor = os.open(self.path, flags, 0o600)
        except OSError as exc:
            raise UnsafePublicationEntry(
                "publication_lock_unavailable",
                "The managed publication lock cannot be opened safely.",
            ) from exc
        handle = os.fdopen(descriptor, "r+b", closefd=True)
        try:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode) or _is_reparse_point(opened):
                raise UnsafePublicationEntry(
                    "publication_lock_unsafe",
                    "The managed publication lock is not a normal file.",
                    recoverable=False,
                )
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
        except TrainingWeightPublicationError:
            handle.close()
            raise
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


def _runtime_result(payload, bundle_path):
    result = dict(payload)
    result["artifacts"] = [dict(item) for item in payload["artifacts"]]
    result["bundle_path"] = os.path.abspath(os.fspath(bundle_path))
    result["manifest_path"] = os.path.join(result["bundle_path"], PUBLICATION_FILENAME)
    return result


class TrainingWeightPublisher:
    """Publish immutable weight files, then activate them after run success."""

    def __init__(self, managed_model_root):
        text = os.fspath(managed_model_root)
        if not str(text or "").strip():
            raise UnsafePublicationEntry(
                "managed_model_root_missing",
                "A managed model root is required.",
                recoverable=False,
            )
        self.managed_model_root = os.path.abspath(text)
        self.training_runs_root = os.path.join(
            self.managed_model_root, TRAINING_BUNDLE_DIRECTORY
        )
        self._lock_path = os.path.join(
            self.managed_model_root, PUBLICATION_LOCK_FILENAME
        )
        self._mutex = threading.RLock()
        self._ensure_roots()

    def publish_pending(self, run_id, staging_root, artifacts):
        """Copy and verify staged weight files, then atomically publish pending.

        ``artifacts`` is a non-empty list of dictionaries containing a stable
        ``artifact_id`` and a safe POSIX ``relative_path`` beneath
        ``staging_root``.  ``role`` defaults to ``output_weights`` and
        ``media_type`` defaults to ``application/octet-stream``.
        """

        clean_run_id = _validate_id(run_id, "run_id")
        staging = os.path.abspath(os.fspath(staging_root))
        normalised = self._normalise_artifacts(artifacts)
        with self._mutex, self._exclusive_process_operation():
            _require_directory(staging)
            final_path = self._bundle_path(clean_run_id)
            if os.path.lexists(final_path) or self._unfinished_for_run(clean_run_id):
                raise PublicationAlreadyExists(
                    "publication_already_exists",
                    "This training run already has a publication.",
                    recoverable=False,
                )
            token = secrets.token_hex(8)
            temp_name = f"{_TEMP_DIRECTORY_PREFIX}{clean_run_id}.{token}"
            temp_path = os.path.join(self.training_runs_root, temp_name)
            os.mkdir(temp_path)
            try:
                published_artifacts = []
                for item in normalised:
                    source = _require_safe_source(staging, item["relative_path"])
                    target, internal = _join_under(temp_path, item["relative_path"])
                    self._make_safe_parent_directories(temp_path, internal)
                    fingerprint = self._copy_verified_file(source, target)
                    relative_path = (
                        f"{TRAINING_BUNDLE_DIRECTORY}/{clean_run_id}/{internal}"
                    )
                    artifact = {
                        "artifact_id": item["artifact_id"],
                        "role": item["role"],
                        "path_base": "managed_model_root",
                        "relative_path": relative_path,
                        "entry_kind": "file",
                        "size_bytes": fingerprint["size_bytes"],
                        "hash_algorithm": FULL_FILE_ALGORITHM,
                        "digest": fingerprint["digest"],
                        "media_type": item["media_type"],
                    }
                    published_artifacts.append(artifact)
                payload = {
                    "schema_version": PUBLICATION_SCHEMA_VERSION,
                    "run_id": clean_run_id,
                    "status": PUBLICATION_STATUS_PENDING,
                    "created_at": _utc_now(),
                    "activated_at": None,
                    "artifacts": published_artifacts,
                }
                self._validate_manifest(payload, expected_run_id=clean_run_id)
                atomic_write_json(
                    os.path.join(temp_path, PUBLICATION_FILENAME), payload, indent=2
                )
                self._verify_bundle(temp_path, payload, allow_stale_tmp=False)
                self._rename_pending_bundle(temp_path, final_path)
            except Exception:
                if os.path.lexists(temp_path):
                    try:
                        _remove_safe_tree(temp_path)
                    except (OSError, TrainingWeightPublicationError):
                        # Recovery will preserve an unsafe tree for manual review.
                        pass
                raise
            return _runtime_result(payload, final_path)

    def activate(self, run_id, run_record):
        """Activate a verified pending bundle after its recorder run succeeded."""

        clean_run_id = _validate_id(run_id, "run_id")
        with self._mutex, self._exclusive_process_operation():
            return self._activate_locked(clean_run_id, run_record)

    def recover(self, run_record_resolver):
        """Recover pending publications without deleting any unsafe tree.

        The resolver must return a run-record dictionary or ``None`` when the
        run does not exist.  Resolver exceptions are treated as uncertainty and
        therefore require manual review rather than deletion.
        """

        if not callable(run_record_resolver):
            raise TypeError("run_record_resolver must be callable")
        report = {
            "activated": [],
            "cleaned": [],
            "active": [],
            "waiting": [],
            "manual_review": [],
        }
        with self._mutex, self._exclusive_process_operation():
            try:
                children = sorted(os.scandir(self.training_runs_root), key=lambda item: item.name)
            except OSError as exc:
                raise UnsafePublicationEntry(
                    "publication_root_unreadable",
                    "The managed publication root cannot be inspected.",
                ) from exc
            for child in children:
                temp_run_id = self._run_id_from_temp_name(child.name)
                if temp_run_id is not None:
                    try:
                        run_record = run_record_resolver(temp_run_id)
                        status = self._resolved_run_status(temp_run_id, run_record)
                    except Exception as exc:
                        report["manual_review"].append(
                            {
                                "entry": child.name,
                                "run_id": temp_run_id,
                                "reason": getattr(
                                    exc, "code", "run_record_resolution_failed"
                                ),
                            }
                        )
                        continue
                    if status in _LIVE_RUN_STATUSES:
                        try:
                            _scan_safe_tree(child.path)
                        except (OSError, TrainingWeightPublicationError) as exc:
                            report["manual_review"].append(
                                {
                                    "entry": child.name,
                                    "run_id": temp_run_id,
                                    "reason": getattr(exc, "code", "inspection_failed"),
                                }
                            )
                        else:
                            report["waiting"].append(temp_run_id)
                    elif (
                        status == "succeeded"
                        or status in _TERMINAL_FAILURE_STATUSES
                        or run_record is None
                    ):
                        try:
                            _remove_safe_tree(child.path)
                        except (OSError, TrainingWeightPublicationError) as exc:
                            report["manual_review"].append(
                                {
                                    "entry": child.name,
                                    "run_id": temp_run_id,
                                    "reason": getattr(exc, "code", "cleanup_failed"),
                                }
                            )
                        else:
                            report["cleaned"].append(child.name)
                    else:
                        report["manual_review"].append(
                            {
                                "entry": child.name,
                                "run_id": temp_run_id,
                                "reason": "run_status_unknown",
                            }
                        )
                    continue

                try:
                    run_id = _validate_id(child.name, "run_id")
                    _require_directory(child.path)
                    payload = self._load_manifest(child.path, expected_run_id=run_id)
                    self._verify_bundle(child.path, payload, allow_stale_tmp=True)
                except (OSError, TrainingWeightPublicationError) as exc:
                    report["manual_review"].append(
                        {
                            "entry": child.name,
                            "run_id": child.name if _ID_PATTERN.fullmatch(child.name) else None,
                            "reason": getattr(exc, "code", "inspection_failed"),
                        }
                    )
                    continue

                try:
                    run_record = run_record_resolver(run_id)
                    status = self._resolved_run_status(run_id, run_record)
                except Exception as exc:
                    report["manual_review"].append(
                        {
                            "entry": child.name,
                            "run_id": run_id,
                            "reason": getattr(
                                exc, "code", "run_record_resolution_failed"
                            ),
                        }
                    )
                    continue
                if payload["status"] == PUBLICATION_STATUS_ACTIVE:
                    try:
                        self._require_success_record(
                            run_id, run_record, payload["artifacts"]
                        )
                    except TrainingWeightPublicationError as exc:
                        report["manual_review"].append(
                            {
                                "entry": child.name,
                                "run_id": run_id,
                                "reason": exc.code,
                            }
                        )
                    else:
                        report["active"].append(run_id)
                    continue
                if status == "succeeded":
                    try:
                        self._activate_locked(run_id, run_record)
                    except TrainingWeightPublicationError as exc:
                        report["manual_review"].append(
                            {
                                "entry": child.name,
                                "run_id": run_id,
                                "reason": exc.code,
                            }
                        )
                    else:
                        report["activated"].append(run_id)
                elif status in _LIVE_RUN_STATUSES:
                    report["waiting"].append(run_id)
                elif status in _TERMINAL_FAILURE_STATUSES or run_record is None:
                    try:
                        _remove_safe_tree(child.path)
                    except (OSError, TrainingWeightPublicationError) as exc:
                        report["manual_review"].append(
                            {
                                "entry": child.name,
                                "run_id": run_id,
                                "reason": getattr(exc, "code", "cleanup_failed"),
                            }
                        )
                    else:
                        report["cleaned"].append(run_id)
                else:
                    report["manual_review"].append(
                        {
                            "entry": child.name,
                            "run_id": run_id,
                            "reason": "run_status_unknown",
                        }
                    )
        return report

    def list_active(self, run_record_resolver):
        """Return only active bundles that still match a succeeded SQLite run."""

        if not callable(run_record_resolver):
            raise TypeError("run_record_resolver must be callable")
        result = {"publications": [], "rejected": []}
        with self._mutex, self._exclusive_process_operation():
            try:
                children = sorted(
                    os.scandir(self.training_runs_root), key=lambda item: item.name
                )
            except OSError as exc:
                raise UnsafePublicationEntry(
                    "publication_root_unreadable",
                    "The managed publication root cannot be inspected.",
                ) from exc
            for child in children:
                if child.name.startswith(_TEMP_DIRECTORY_PREFIX):
                    continue
                run_id = child.name
                try:
                    clean_run_id = _validate_id(run_id, "run_id")
                    _require_directory(child.path)
                    payload = self._load_manifest(
                        child.path, expected_run_id=clean_run_id
                    )
                    if payload["status"] != PUBLICATION_STATUS_ACTIVE:
                        continue
                    self._verify_bundle(child.path, payload, allow_stale_tmp=False)
                    run_record = run_record_resolver(clean_run_id)
                    self._require_success_record(
                        clean_run_id, run_record, payload["artifacts"]
                    )
                except (OSError, TrainingWeightPublicationError) as exc:
                    result["rejected"].append(
                        {
                            "run_id": run_id if _ID_PATTERN.fullmatch(run_id) else None,
                            "reason": getattr(exc, "code", "inspection_failed"),
                        }
                    )
                    continue
                except Exception:
                    result["rejected"].append(
                        {"run_id": run_id, "reason": "run_record_resolution_failed"}
                    )
                    continue
                result["publications"].append(_runtime_result(payload, child.path))
        return result

    @contextmanager
    def _exclusive_process_operation(self):
        self._ensure_roots()
        lock = _ManagedPublicationLock(self._lock_path)
        if not lock.acquire():
            raise PublicationLockBusy(
                "publication_lock_busy",
                "Another process is currently publishing or recovering training weights.",
            )
        try:
            yield
        finally:
            lock.release()

    def _ensure_roots(self):
        _require_existing_components_safe(self.managed_model_root)
        os.makedirs(self.managed_model_root, exist_ok=True)
        _require_directory(self.managed_model_root)
        if os.path.lexists(self.training_runs_root):
            _require_directory(self.training_runs_root)
        else:
            os.mkdir(self.training_runs_root)
        _require_directory(self.training_runs_root)

    def _bundle_path(self, run_id):
        target = os.path.abspath(os.path.join(self.training_runs_root, run_id))
        try:
            inside = os.path.normcase(
                os.path.commonpath([self.training_runs_root, target])
            ) == os.path.normcase(self.training_runs_root)
        except ValueError:
            inside = False
        if not inside:
            raise UnsafePublicationEntry(
                "publication_path_outside_root",
                "The publication target leaves the managed model root.",
                recoverable=False,
            )
        return target

    def _unfinished_for_run(self, run_id):
        prefix = f"{_TEMP_DIRECTORY_PREFIX}{run_id}."
        try:
            return any(child.name.startswith(prefix) for child in os.scandir(self.training_runs_root))
        except OSError as exc:
            raise UnsafePublicationEntry(
                "publication_root_unreadable",
                "The managed publication root cannot be inspected.",
            ) from exc

    def _normalise_artifacts(self, artifacts):
        if not isinstance(artifacts, (list, tuple)) or not artifacts:
            raise UnsafePublicationEntry(
                "publication_artifacts_missing",
                "At least one training weight artifact is required.",
                recoverable=False,
            )
        result = []
        ids = set()
        paths = set()
        path_parts = []
        for item in artifacts:
            if not isinstance(item, dict) or set(item) - _ARTIFACT_INPUT_FIELDS:
                raise UnsafePublicationEntry(
                    "publication_artifact_invalid",
                    "A publication artifact declaration is invalid.",
                    recoverable=False,
                )
            artifact_id = _validate_id(item.get("artifact_id"), "artifact_id")
            role = _validate_id(item.get("role") or "output_weights", "artifact_role")
            if role not in {"output_weights", "model_manifest"}:
                raise UnsafePublicationEntry(
                    "publication_artifact_role_invalid",
                    "The model publisher only accepts output weights and model manifests.",
                    recoverable=False,
                )
            relative = _validate_relative(item.get("relative_path"))
            media_type = str(item.get("media_type") or "application/octet-stream").strip()
            if not _MEDIA_TYPE_PATTERN.fullmatch(media_type):
                raise UnsafePublicationEntry(
                    "artifact_media_type_invalid",
                    "A publication artifact media type is invalid.",
                    recoverable=False,
                )
            path_key = relative.casefold()
            if artifact_id in ids or path_key in paths:
                raise UnsafePublicationEntry(
                    "publication_artifact_duplicate",
                    "Publication artifact identifiers and paths must be unique.",
                    recoverable=False,
                )
            if relative.casefold() in {
                PUBLICATION_FILENAME.casefold(),
                f"{PUBLICATION_FILENAME}.tmp".casefold(),
            }:
                raise UnsafePublicationEntry(
                    "publication_manifest_path_reserved",
                    "The publication manifest path is reserved.",
                    recoverable=False,
                )
            segments = tuple(part.casefold() for part in relative.split("/"))
            if any(
                segments[: len(other)] == other
                or other[: len(segments)] == segments
                for other in path_parts
            ):
                raise UnsafePublicationEntry(
                    "publication_artifact_path_conflict",
                    "Publication artifact paths cannot contain one another.",
                    recoverable=False,
                )
            ids.add(artifact_id)
            paths.add(path_key)
            path_parts.append(segments)
            result.append(
                {
                    "artifact_id": artifact_id,
                    "role": role,
                    "relative_path": relative,
                    "media_type": media_type,
                }
            )
        return result

    def _make_safe_parent_directories(self, root, relative_path):
        current = os.path.abspath(os.fspath(root))
        _require_directory(current)
        for segment in relative_path.split("/")[:-1]:
            current = os.path.join(current, segment)
            if os.path.lexists(current):
                _require_directory(current)
            else:
                os.mkdir(current)
                _require_directory(current)

    def _copy_verified_file(self, source, target):
        _require_regular_file(source)
        if os.path.lexists(target):
            raise UnsafePublicationEntry(
                "publication_target_exists",
                "A publication artifact target already exists.",
                recoverable=False,
            )
        source_flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
        source_flags |= int(getattr(os, "O_NOFOLLOW", 0))
        target_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        target_flags |= int(getattr(os, "O_BINARY", 0))
        digest = hashlib.sha256()
        size_bytes = 0
        source_descriptor = os.open(source, source_flags)
        try:
            opened = os.fstat(source_descriptor)
            if not stat.S_ISREG(opened.st_mode) or _is_reparse_point(opened):
                raise UnsafePublicationEntry(
                    "safe_regular_file_required",
                    "A publication artifact must be a normal file.",
                    recoverable=False,
                )
            target_descriptor = os.open(target, target_flags, 0o600)
            try:
                with os.fdopen(target_descriptor, "wb", closefd=True) as target_handle:
                    while True:
                        chunk = os.read(source_descriptor, 4 * 1024 * 1024)
                        if not chunk:
                            break
                        target_handle.write(chunk)
                        digest.update(chunk)
                        size_bytes += len(chunk)
                    target_handle.flush()
                    os.fsync(target_handle.fileno())
            except Exception:
                if os.path.lexists(target):
                    try:
                        _require_regular_file(target)
                        os.unlink(target)
                    except (OSError, TrainingWeightPublicationError):
                        pass
                raise
        finally:
            os.close(source_descriptor)

        copied = compute_fingerprint(target, algorithm=FULL_FILE_ALGORITHM)
        source_after = compute_fingerprint(source, algorithm=FULL_FILE_ALGORITHM)
        expected = {"size_bytes": size_bytes, "digest": digest.hexdigest()}
        if any(
            observed.get(field) != value
            for observed in (copied, source_after)
            for field, value in expected.items()
        ):
            raise PublicationIntegrityError(
                "copied_weight_verification_failed",
                "A staged weight changed or did not copy completely.",
            )
        return {
            "size_bytes": size_bytes,
            "digest": digest.hexdigest(),
            "hash_algorithm": FULL_FILE_ALGORITHM,
        }

    def _rename_pending_bundle(self, temp_path, final_path):
        _require_directory(temp_path)
        if os.path.lexists(final_path):
            raise PublicationAlreadyExists(
                "publication_already_exists",
                "This training run already has a publication.",
                recoverable=False,
            )
        os.rename(temp_path, final_path)
        _fsync_directory(self.training_runs_root)

    def _run_id_from_temp_name(self, name):
        if not name.startswith(_TEMP_DIRECTORY_PREFIX):
            return None
        remainder = name[len(_TEMP_DIRECTORY_PREFIX) :]
        run_id, separator, token = remainder.rpartition(".")
        if not separator or not re.fullmatch(r"[0-9a-f]{16}", token):
            return None
        try:
            return _validate_id(run_id, "run_id")
        except UnsafePublicationEntry:
            return None

    def _load_manifest(self, bundle_path, *, expected_run_id):
        _require_directory(bundle_path)
        manifest_path = os.path.join(bundle_path, PUBLICATION_FILENAME)
        _require_regular_file(manifest_path)
        payload = _safe_read_json(manifest_path)
        self._validate_manifest(payload, expected_run_id=expected_run_id)
        return payload

    def _validate_manifest(self, payload, *, expected_run_id):
        if not isinstance(payload, dict) or set(payload) != _MANIFEST_FIELDS:
            raise PublicationIntegrityError(
                "publication_manifest_fields_invalid",
                "The publication manifest fields are invalid.",
                recoverable=False,
            )
        run_id = _validate_id(payload.get("run_id"), "run_id")
        if run_id != expected_run_id:
            raise PublicationIntegrityError(
                "publication_run_id_mismatch",
                "The publication does not belong to the expected training run.",
                recoverable=False,
            )
        if payload.get("schema_version") != PUBLICATION_SCHEMA_VERSION:
            raise PublicationIntegrityError(
                "publication_schema_invalid",
                "The publication manifest schema is unsupported.",
                recoverable=False,
            )
        status_value = payload.get("status")
        if status_value not in {PUBLICATION_STATUS_PENDING, PUBLICATION_STATUS_ACTIVE}:
            raise PublicationIntegrityError(
                "publication_status_invalid",
                "The publication status is invalid.",
                recoverable=False,
            )
        if not isinstance(payload.get("created_at"), str) or not payload["created_at"]:
            raise PublicationIntegrityError(
                "publication_timestamp_invalid",
                "The publication creation time is invalid.",
                recoverable=False,
            )
        if status_value == PUBLICATION_STATUS_PENDING and payload.get("activated_at") is not None:
            raise PublicationIntegrityError(
                "publication_activation_time_invalid",
                "A pending publication cannot have an activation time.",
                recoverable=False,
            )
        if status_value == PUBLICATION_STATUS_ACTIVE and not isinstance(
            payload.get("activated_at"), str
        ):
            raise PublicationIntegrityError(
                "publication_activation_time_invalid",
                "An active publication must have an activation time.",
                recoverable=False,
            )
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise PublicationIntegrityError(
                "publication_artifacts_missing",
                "The publication does not list any weight files.",
                recoverable=False,
            )
        ids = set()
        relative_paths = set()
        prefix = f"{TRAINING_BUNDLE_DIRECTORY}/{run_id}/"
        for artifact in artifacts:
            if not isinstance(artifact, dict) or set(artifact) != _ARTIFACT_FIELDS:
                raise PublicationIntegrityError(
                    "publication_artifact_fields_invalid",
                    "A publication artifact record is invalid.",
                    recoverable=False,
                )
            artifact_id = _validate_id(artifact.get("artifact_id"), "artifact_id")
            role = _validate_id(artifact.get("role"), "artifact_role")
            if role not in {"output_weights", "model_manifest"}:
                raise PublicationIntegrityError(
                    "publication_artifact_role_invalid",
                    "A model publication contains an unsupported artifact role.",
                    recoverable=False,
                )
            if artifact_id in ids:
                raise PublicationIntegrityError(
                    "publication_artifact_duplicate",
                    "Publication artifact identifiers must be unique.",
                    recoverable=False,
                )
            ids.add(artifact_id)
            if artifact.get("path_base") != "managed_model_root" or artifact.get(
                "entry_kind"
            ) != "file":
                raise PublicationIntegrityError(
                    "publication_artifact_location_invalid",
                    "A publication artifact location is invalid.",
                    recoverable=False,
                )
            relative = _validate_relative(artifact.get("relative_path"))
            if not relative.startswith(prefix):
                raise PublicationIntegrityError(
                    "publication_artifact_location_invalid",
                    "A publication artifact is outside its run bundle.",
                    recoverable=False,
                )
            internal = _validate_relative(relative[len(prefix) :])
            if internal.casefold() in relative_paths:
                raise PublicationIntegrityError(
                    "publication_artifact_duplicate",
                    "Publication artifact paths must be unique.",
                    recoverable=False,
                )
            relative_paths.add(internal.casefold())
            if artifact.get("hash_algorithm") != FULL_FILE_ALGORITHM or not _HEX_DIGEST_PATTERN.fullmatch(
                str(artifact.get("digest") or "")
            ):
                raise PublicationIntegrityError(
                    "publication_artifact_fingerprint_invalid",
                    "A publication artifact fingerprint is invalid.",
                    recoverable=False,
                )
            size_bytes = artifact.get("size_bytes")
            if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
                raise PublicationIntegrityError(
                    "publication_artifact_size_invalid",
                    "A publication artifact size is invalid.",
                    recoverable=False,
                )
            if not _MEDIA_TYPE_PATTERN.fullmatch(str(artifact.get("media_type") or "")):
                raise PublicationIntegrityError(
                    "artifact_media_type_invalid",
                    "A publication artifact media type is invalid.",
                    recoverable=False,
                )
        return payload

    def _verify_bundle(self, bundle_path, payload, *, allow_stale_tmp):
        files, directories = _scan_safe_tree(bundle_path)
        stale_tmp = f"{PUBLICATION_FILENAME}.tmp"
        if stale_tmp in files:
            if allow_stale_tmp and payload["status"] == PUBLICATION_STATUS_PENDING:
                stale_path = os.path.join(bundle_path, stale_tmp)
                _require_regular_file(stale_path)
                os.unlink(stale_path)
                files.remove(stale_tmp)
            else:
                raise PublicationIntegrityError(
                    "unexpected_publication_entry",
                    "The publication contains an unexpected file.",
                    recoverable=False,
                )
        expected_files = {PUBLICATION_FILENAME}
        expected_directories = set()
        prefix = f"{TRAINING_BUNDLE_DIRECTORY}/{payload['run_id']}/"
        for artifact in payload["artifacts"]:
            internal = artifact["relative_path"][len(prefix) :]
            expected_files.add(internal)
            parts = internal.split("/")[:-1]
            for index in range(1, len(parts) + 1):
                expected_directories.add("/".join(parts[:index]))
            target, _clean = _join_under(bundle_path, internal)
            _require_regular_file(target)
            observed = compute_fingerprint(target, algorithm=FULL_FILE_ALGORITHM)
            for field in ("size_bytes", "hash_algorithm", "digest"):
                if observed.get(field) != artifact.get(field):
                    raise PublicationIntegrityError(
                        "published_weight_fingerprint_mismatch",
                        "A published weight no longer matches its recorded fingerprint.",
                        recoverable=False,
                    )
        if files != expected_files or directories != expected_directories:
            raise PublicationIntegrityError(
                "unexpected_publication_entry",
                "The publication contains an unexpected or missing entry.",
                recoverable=False,
            )

    def _resolved_run_status(self, run_id, run_record):
        if run_record is None:
            return None
        if not isinstance(run_record, dict):
            raise PublicationIntegrityError(
                "run_record_invalid",
                "The publication run record is invalid.",
                recoverable=False,
            )
        if run_record.get("schema_version") != "taxamask_training_run_v1":
            raise PublicationIntegrityError(
                "run_record_schema_invalid",
                "The publication run record schema is invalid.",
                recoverable=False,
            )
        if run_record.get("run_id") != run_id:
            raise PublicationIntegrityError(
                "run_record_id_mismatch",
                "The publication does not match its training run record.",
                recoverable=False,
            )
        return run_record.get("status")

    def _require_success_record(self, run_id, run_record, artifacts):
        status = self._resolved_run_status(run_id, run_record)
        if status != "succeeded":
            raise PublicationIntegrityError(
                "successful_run_record_required",
                "Only a matching successful training run can activate weights.",
            )
        recorded = {
            item.get("artifact_id"): item
            for item in run_record.get("artifacts", [])
            if isinstance(item, dict) and item.get("artifact_id")
        }
        compared_fields = (
            "artifact_id",
            "role",
            "path_base",
            "relative_path",
            "entry_kind",
            "size_bytes",
            "hash_algorithm",
            "digest",
            "media_type",
        )
        for expected in artifacts:
            observed = recorded.get(expected["artifact_id"])
            if not isinstance(observed, dict) or any(
                observed.get(field) != expected.get(field) for field in compared_fields
            ):
                raise PublicationIntegrityError(
                    "run_artifact_not_registered",
                    "The successful run did not register every published weight file.",
                )

    def _activate_locked(self, run_id, run_record):
        bundle_path = self._bundle_path(run_id)
        if not os.path.lexists(bundle_path):
            raise PublicationIntegrityError(
                "publication_missing",
                "The pending weight publication does not exist.",
            )
        payload = self._load_manifest(bundle_path, expected_run_id=run_id)
        if payload["status"] == PUBLICATION_STATUS_ACTIVE:
            raise ActivePublicationImmutable(
                "active_publication_immutable",
                "An active weight publication cannot be rewritten.",
                recoverable=False,
            )
        self._verify_bundle(bundle_path, payload, allow_stale_tmp=True)
        self._require_success_record(run_id, run_record, payload["artifacts"])
        activated = dict(payload)
        activated["artifacts"] = [dict(item) for item in payload["artifacts"]]
        activated["status"] = PUBLICATION_STATUS_ACTIVE
        activated["activated_at"] = _utc_now()
        self._validate_manifest(activated, expected_run_id=run_id)
        atomic_write_json(
            os.path.join(bundle_path, PUBLICATION_FILENAME), activated, indent=2
        )
        return _runtime_result(activated, bundle_path)


__all__ = [
    "PUBLICATION_SCHEMA_VERSION",
    "PUBLICATION_FILENAME",
    "PUBLICATION_STATUS_PENDING",
    "PUBLICATION_STATUS_ACTIVE",
    "TRAINING_BUNDLE_DIRECTORY",
    "PUBLICATION_LOCK_FILENAME",
    "TrainingWeightPublicationError",
    "UnsafePublicationEntry",
    "PublicationAlreadyExists",
    "PublicationIntegrityError",
    "ActivePublicationImmutable",
    "PublicationLockBusy",
    "TrainingWeightPublisher",
]
