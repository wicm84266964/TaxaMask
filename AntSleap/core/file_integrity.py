"""Streaming, platform-stable fingerprints for TaxaMask artifacts."""

from __future__ import annotations

import hashlib
import os
import stat
import struct
import unicodedata
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple


DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024
FULL_FILE_ALGORITHM = "sha256"
TREE_ALGORITHM = "sha256-tree-v1"
QUICK_FILE_ALGORITHM = "taxamask-sampled-sha256-v1"

_TREE_HEADER = b"taxamask-sha256-tree-v1\0"
_QUICK_HEADER = b"taxamask-sampled-sha256-v1\0"
_QUICK_SAMPLE_SIZE = 1024 * 1024
_QUICK_ALIASES = {QUICK_FILE_ALGORITHM, "quick_fingerprint"}


class FingerprintError(RuntimeError):
    """A fingerprint could not be safely published."""

    def __init__(
        self,
        code: str,
        summary: str,
        *,
        recoverable: bool = True,
        stage: str = "integrity_hash",
    ) -> None:
        super().__init__(summary)
        self.code = str(code)
        self.summary = str(summary)
        self.stage = str(stage)
        self.recoverable = bool(recoverable)

    def as_error(self) -> Dict[str, object]:
        return {
            "code": self.code,
            "summary": self.summary,
            "stage": self.stage,
            "recoverable": self.recoverable,
            "diagnostic_artifact_id": None,
        }


class FingerprintCancelled(FingerprintError):
    def __init__(self) -> None:
        super().__init__("user_cancelled", "The integrity check was cancelled.")


class FingerprintIncomplete(FingerprintError):
    pass


class UnsupportedFingerprintAlgorithm(FingerprintError):
    def __init__(self) -> None:
        super().__init__(
            "unsupported_hash_algorithm",
            "The requested integrity algorithm is not supported for this entry.",
            recoverable=False,
        )


@dataclass(frozen=True)
class _Metadata:
    kind: str
    size: int
    mtime_ns: int
    stable_id: Optional[Tuple[int, int]]
    reliable: bool

    def signature(self) -> Tuple[object, ...]:
        return (self.kind, self.size, self.mtime_ns, self.stable_id)


@dataclass(frozen=True)
class _TreeEntry:
    relative_path: str
    path_bytes: bytes
    physical_path: str
    metadata: _Metadata


@dataclass(frozen=True)
class _PassResult:
    digest: str
    size_bytes: int
    mtime_ns: int
    metadata_signature: Tuple[object, ...]
    reliable: bool


def _check_cancel(cancel_check: Optional[Callable[[], bool]]) -> None:
    if cancel_check is not None and bool(cancel_check()):
        raise FingerprintCancelled()


def _report_progress(
    callback: Optional[Callable[[int, int], None]], done: int, total: int
) -> None:
    if callback is not None:
        callback(int(done), int(total))


def _is_reparse_point(stat_result: os.stat_result) -> bool:
    attributes = int(getattr(stat_result, "st_file_attributes", 0) or 0)
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400) or 0x400)
    return bool(attributes & reparse_flag)


def _metadata(stat_result: os.stat_result) -> _Metadata:
    mode = stat_result.st_mode
    if stat.S_ISREG(mode):
        kind = "file"
    elif stat.S_ISDIR(mode):
        kind = "directory"
    else:
        raise FingerprintIncomplete(
            "unsupported_entry_type",
            "The integrity source contains a link or special filesystem entry.",
            recoverable=False,
        )
    if _is_reparse_point(stat_result):
        raise FingerprintIncomplete(
            "unsupported_entry_type",
            "The integrity source contains a link or special filesystem entry.",
            recoverable=False,
        )

    precise_mtime = getattr(stat_result, "st_mtime_ns", None)
    # Python can expose an integer st_mtime_ns even when the underlying volume
    # only records whole seconds or milliseconds. Treat an observed
    # sub-millisecond component as the conservative signal that high precision
    # is actually available; otherwise the caller performs a full second pass.
    has_precise_mtime = isinstance(precise_mtime, int) and bool(
        int(precise_mtime) % 1_000_000
    )
    mtime_ns = (
        int(precise_mtime)
        if has_precise_mtime
        else int(float(stat_result.st_mtime) * 1_000_000_000)
    )
    device = getattr(stat_result, "st_dev", None)
    inode = getattr(stat_result, "st_ino", None)
    has_stable_id = device is not None and inode not in (None, 0)
    stable_id = (int(device), int(inode)) if has_stable_id else None
    return _Metadata(
        kind=kind,
        size=max(0, int(stat_result.st_size)),
        mtime_ns=mtime_ns,
        stable_id=stable_id,
        reliable=bool(has_precise_mtime and has_stable_id),
    )


def _lstat_metadata(path: str) -> _Metadata:
    result = os.lstat(path)
    if stat.S_ISLNK(result.st_mode) or _is_reparse_point(result):
        raise FingerprintIncomplete(
            "unsupported_entry_type",
            "The integrity source contains a link or special filesystem entry.",
            recoverable=False,
        )
    return _metadata(result)


def _ensure_unchanged(expected: _Metadata, observed: _Metadata) -> None:
    if expected.signature() != observed.signature():
        raise FingerprintIncomplete(
            "source_changed_during_hash",
            "The source changed while its integrity fingerprint was being calculated.",
        )


def _open_binary_nofollow(path: str):
    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    descriptor = os.open(path, flags)
    return os.fdopen(descriptor, "rb", closefd=True)


def _read_full_file_pass(
    path: str,
    chunk_size: int,
    progress_callback: Optional[Callable[[int, int], None]],
    cancel_check: Optional[Callable[[], bool]],
) -> _PassResult:
    before = _lstat_metadata(path)
    if before.kind != "file":
        raise UnsupportedFingerprintAlgorithm()
    _check_cancel(cancel_check)
    _report_progress(progress_callback, 0, before.size)
    digest = hashlib.sha256()
    read_bytes = 0
    try:
        with _open_binary_nofollow(path) as handle:
            opened = _metadata(os.fstat(handle.fileno()))
            _ensure_unchanged(before, opened)
            while True:
                _check_cancel(cancel_check)
                block = handle.read(chunk_size)
                if not block:
                    break
                digest.update(block)
                read_bytes += len(block)
                _report_progress(progress_callback, read_bytes, before.size)
            closed = _metadata(os.fstat(handle.fileno()))
            _ensure_unchanged(before, closed)
    except FingerprintError:
        raise
    except OSError as exc:
        raise FingerprintIncomplete(
            "source_read_failed", "The source could not be read for integrity checking."
        ) from exc
    try:
        after = _lstat_metadata(path)
    except FileNotFoundError as exc:
        raise FingerprintIncomplete(
            "source_changed_during_hash",
            "The source changed while its integrity fingerprint was being calculated.",
        ) from exc
    _ensure_unchanged(before, after)
    if read_bytes != before.size:
        raise FingerprintIncomplete(
            "source_changed_during_hash",
            "The source changed while its integrity fingerprint was being calculated.",
        )
    _check_cancel(cancel_check)
    _report_progress(progress_callback, before.size, before.size)
    return _PassResult(
        digest=digest.hexdigest(),
        size_bytes=before.size,
        mtime_ns=before.mtime_ns,
        metadata_signature=before.signature(),
        reliable=before.reliable,
    )


def _quick_sample_ranges(size: int) -> List[Tuple[int, int]]:
    if size <= 0:
        return []
    length = min(_QUICK_SAMPLE_SIZE, size)
    offsets = {
        0,
        max(0, (size - length) // 2),
        max(0, size - length),
    }
    return [(offset, min(length, size - offset)) for offset in sorted(offsets)]


def _read_quick_file_pass(
    path: str,
    chunk_size: int,
    progress_callback: Optional[Callable[[int, int], None]],
    cancel_check: Optional[Callable[[], bool]],
) -> _PassResult:
    before = _lstat_metadata(path)
    if before.kind != "file":
        raise UnsupportedFingerprintAlgorithm()
    samples = _quick_sample_ranges(before.size)
    total_sampled = sum(length for _, length in samples)
    digest = hashlib.sha256()
    digest.update(_QUICK_HEADER)
    digest.update(struct.pack(">Q", before.size))
    done = 0
    _check_cancel(cancel_check)
    _report_progress(progress_callback, 0, total_sampled)
    try:
        with _open_binary_nofollow(path) as handle:
            opened = _metadata(os.fstat(handle.fileno()))
            _ensure_unchanged(before, opened)
            for offset, length in samples:
                digest.update(struct.pack(">Q", offset))
                digest.update(struct.pack(">Q", length))
                handle.seek(offset)
                remaining = length
                while remaining:
                    _check_cancel(cancel_check)
                    block = handle.read(min(chunk_size, remaining))
                    if not block:
                        raise FingerprintIncomplete(
                            "source_changed_during_hash",
                            "The source changed while its integrity fingerprint was being calculated.",
                        )
                    digest.update(block)
                    done += len(block)
                    remaining -= len(block)
                    _report_progress(progress_callback, done, total_sampled)
            closed = _metadata(os.fstat(handle.fileno()))
            _ensure_unchanged(before, closed)
    except FingerprintError:
        raise
    except OSError as exc:
        raise FingerprintIncomplete(
            "source_read_failed", "The source could not be read for integrity checking."
        ) from exc
    try:
        after = _lstat_metadata(path)
    except FileNotFoundError as exc:
        raise FingerprintIncomplete(
            "source_changed_during_hash",
            "The source changed while its integrity fingerprint was being calculated.",
        ) from exc
    _ensure_unchanged(before, after)
    _check_cancel(cancel_check)
    _report_progress(progress_callback, total_sampled, total_sampled)
    return _PassResult(
        digest=digest.hexdigest(),
        size_bytes=before.size,
        mtime_ns=before.mtime_ns,
        metadata_signature=before.signature(),
        reliable=before.reliable,
    )


def _normalise_component(name: str) -> str:
    normalised = unicodedata.normalize("NFC", str(name))
    if (
        not normalised
        or normalised in {".", ".."}
        or "/" in normalised
        or "\\" in normalised
        or "\0" in normalised
    ):
        raise FingerprintIncomplete(
            "invalid_tree_path",
            "The directory contains a name that cannot be represented safely.",
            recoverable=False,
        )
    return normalised


def _scan_tree(root: str) -> List[_TreeEntry]:
    entries: List[_TreeEntry] = []
    seen = set()
    pending: List[Tuple[str, Tuple[str, ...]]] = [(root, tuple())]
    while pending:
        current, prefix = pending.pop()
        try:
            current_metadata = _lstat_metadata(current)
        except FileNotFoundError as exc:
            raise FingerprintIncomplete(
                "source_changed_during_hash",
                "The source changed while its integrity fingerprint was being calculated.",
            ) from exc
        if current_metadata.kind != "directory":
            raise FingerprintIncomplete(
                "source_changed_during_hash",
                "The source changed while its integrity fingerprint was being calculated.",
            )
        try:
            with os.scandir(current) as iterator:
                children = list(iterator)
        except OSError as exc:
            raise FingerprintIncomplete(
                "source_scan_failed",
                "The directory could not be enumerated for integrity checking.",
            ) from exc
        child_directories = []
        for child in children:
            component = _normalise_component(child.name)
            relative_parts = prefix + (component,)
            relative_path = "/".join(relative_parts)
            path_bytes = relative_path.encode("utf-8")
            if path_bytes in seen:
                raise FingerprintIncomplete(
                    "normalised_path_collision",
                    "Two directory entries have the same normalized relative path.",
                    recoverable=False,
                )
            seen.add(path_bytes)
            physical_path = os.path.join(current, child.name)
            try:
                # On Windows DirEntry.stat may expose st_dev/st_ino as zero even
                # though os.lstat can obtain a stable file ID. Use one metadata
                # source for the snapshot and all subsequent stability checks.
                stat_result = os.lstat(physical_path)
            except OSError as exc:
                raise FingerprintIncomplete(
                    "source_changed_during_hash",
                    "The source changed while its integrity fingerprint was being calculated.",
                ) from exc
            if child.is_symlink() or _is_reparse_point(stat_result):
                raise FingerprintIncomplete(
                    "unsupported_entry_type",
                    "The integrity source contains a link or special filesystem entry.",
                    recoverable=False,
                )
            metadata = _metadata(stat_result)
            entries.append(
                _TreeEntry(relative_path, path_bytes, physical_path, metadata)
            )
            if metadata.kind == "directory":
                child_directories.append((physical_path, relative_parts))
        pending.extend(child_directories)
    return sorted(entries, key=lambda item: item.path_bytes)


def _tree_snapshot(entries: List[_TreeEntry]) -> Tuple[object, ...]:
    return tuple(
        (entry.path_bytes, entry.metadata.signature()) for entry in entries
    )


def _hash_tree_file(
    hasher,
    entry: _TreeEntry,
    chunk_size: int,
    progress_callback: Optional[Callable[[int, int], None]],
    cancel_check: Optional[Callable[[], bool]],
    done: int,
    total: int,
) -> int:
    try:
        before = _lstat_metadata(entry.physical_path)
    except FileNotFoundError as exc:
        raise FingerprintIncomplete(
            "source_changed_during_hash",
            "The source changed while its integrity fingerprint was being calculated.",
        ) from exc
    _ensure_unchanged(entry.metadata, before)
    try:
        with _open_binary_nofollow(entry.physical_path) as handle:
            opened = _metadata(os.fstat(handle.fileno()))
            _ensure_unchanged(entry.metadata, opened)
            read_bytes = 0
            while True:
                _check_cancel(cancel_check)
                block = handle.read(chunk_size)
                if not block:
                    break
                hasher.update(block)
                read_bytes += len(block)
                done += len(block)
                _report_progress(progress_callback, done, total)
            closed = _metadata(os.fstat(handle.fileno()))
            _ensure_unchanged(entry.metadata, closed)
    except FingerprintError:
        raise
    except OSError as exc:
        raise FingerprintIncomplete(
            "source_read_failed", "A directory member could not be read for integrity checking."
        ) from exc
    try:
        after = _lstat_metadata(entry.physical_path)
    except FileNotFoundError as exc:
        raise FingerprintIncomplete(
            "source_changed_during_hash",
            "The source changed while its integrity fingerprint was being calculated.",
        ) from exc
    _ensure_unchanged(entry.metadata, after)
    if read_bytes != entry.metadata.size:
        raise FingerprintIncomplete(
            "source_changed_during_hash",
            "The source changed while its integrity fingerprint was being calculated.",
        )
    return done


def _read_tree_pass(
    root: str,
    chunk_size: int,
    progress_callback: Optional[Callable[[int, int], None]],
    cancel_check: Optional[Callable[[], bool]],
) -> _PassResult:
    root_before = _lstat_metadata(root)
    if root_before.kind != "directory":
        raise UnsupportedFingerprintAlgorithm()
    _check_cancel(cancel_check)
    entries_before = _scan_tree(root)
    total = sum(
        entry.metadata.size
        for entry in entries_before
        if entry.metadata.kind == "file"
    )
    _report_progress(progress_callback, 0, total)
    digest = hashlib.sha256()
    digest.update(_TREE_HEADER)
    done = 0
    for entry in entries_before:
        _check_cancel(cancel_check)
        kind_byte = b"D" if entry.metadata.kind == "directory" else b"F"
        content_length = 0 if entry.metadata.kind == "directory" else entry.metadata.size
        digest.update(kind_byte)
        digest.update(struct.pack(">Q", len(entry.path_bytes)))
        digest.update(entry.path_bytes)
        digest.update(struct.pack(">Q", content_length))
        if entry.metadata.kind == "file":
            done = _hash_tree_file(
                digest,
                entry,
                chunk_size,
                progress_callback,
                cancel_check,
                done,
                total,
            )
    entries_after = _scan_tree(root)
    try:
        root_after = _lstat_metadata(root)
    except FileNotFoundError as exc:
        raise FingerprintIncomplete(
            "source_changed_during_hash",
            "The source changed while its integrity fingerprint was being calculated.",
        ) from exc
    _ensure_unchanged(root_before, root_after)
    if _tree_snapshot(entries_before) != _tree_snapshot(entries_after):
        raise FingerprintIncomplete(
            "source_changed_during_hash",
            "The directory changed while its integrity fingerprint was being calculated.",
        )
    _check_cancel(cancel_check)
    _report_progress(progress_callback, total, total)
    reliable = root_before.reliable and all(
        entry.metadata.reliable for entry in entries_before
    )
    metadata_signature = (root_before.signature(), _tree_snapshot(entries_before))
    return _PassResult(
        digest=digest.hexdigest(),
        size_bytes=total,
        mtime_ns=root_before.mtime_ns,
        metadata_signature=metadata_signature,
        reliable=reliable,
    )


def _require_matching_second_pass(
    first: _PassResult,
    second: _PassResult,
) -> None:
    if (
        first.digest != second.digest
        or first.size_bytes != second.size_bytes
        or first.metadata_signature != second.metadata_signature
    ):
        raise FingerprintIncomplete(
            "source_stability_unconfirmed",
            "The filesystem could not provide a stable integrity reading.",
        )


def compute_fingerprint(
    path,
    algorithm=None,
    *,
    chunk_size=DEFAULT_CHUNK_SIZE,
    progress_callback=None,
    cancel_check=None,
) -> Dict[str, object]:
    """Compute a publishable fingerprint without retaining the source path.

    ``progress_callback`` receives ``(processed_bytes, total_bytes)``.  A truthy
    ``cancel_check()`` raises :class:`FingerprintCancelled`; no partial digest is
    returned.  ``quick_fingerprint`` is accepted as an input alias, but the
    result always carries the versioned ``taxamask-sampled-sha256-v1`` name.
    """

    try:
        chunk_size = int(chunk_size)
    except (TypeError, ValueError) as exc:
        raise ValueError("chunk_size must be a positive integer") from exc
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")

    source = os.fspath(path)
    initial = _lstat_metadata(source)
    if algorithm is None:
        selected = TREE_ALGORITHM if initial.kind == "directory" else FULL_FILE_ALGORITHM
    else:
        selected = str(algorithm).strip().lower()
        if selected in _QUICK_ALIASES:
            selected = QUICK_FILE_ALGORITHM

    if initial.kind == "directory":
        if selected != TREE_ALGORITHM:
            raise UnsupportedFingerprintAlgorithm()
        first = _read_tree_pass(source, chunk_size, progress_callback, cancel_check)
        if not first.reliable:
            second = _read_tree_pass(source, chunk_size, None, cancel_check)
            _require_matching_second_pass(first, second)
        entry_kind = "directory"
    else:
        if selected == FULL_FILE_ALGORITHM:
            reader = _read_full_file_pass
        elif selected == QUICK_FILE_ALGORITHM:
            reader = _read_quick_file_pass
        else:
            raise UnsupportedFingerprintAlgorithm()
        first = reader(source, chunk_size, progress_callback, cancel_check)
        if not first.reliable:
            second = reader(source, chunk_size, None, cancel_check)
            _require_matching_second_pass(first, second)
        entry_kind = "file"

    return {
        "entry_kind": entry_kind,
        "size_bytes": first.size_bytes,
        "hash_algorithm": selected,
        "digest": first.digest,
        "mtime_ns": first.mtime_ns,
    }


__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "FULL_FILE_ALGORITHM",
    "TREE_ALGORITHM",
    "QUICK_FILE_ALGORITHM",
    "FingerprintError",
    "FingerprintCancelled",
    "FingerprintIncomplete",
    "UnsupportedFingerprintAlgorithm",
    "compute_fingerprint",
]
