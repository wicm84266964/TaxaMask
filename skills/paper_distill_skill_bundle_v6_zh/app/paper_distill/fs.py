from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path


def absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _is_windows_reparse_point(path: Path) -> bool:
    try:
        stat_result = os.lstat(path)
    except OSError:
        return False
    file_attributes = getattr(stat_result, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if isinstance(file_attributes, int) and reparse_flag and file_attributes & reparse_flag:
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction):
        try:
            return bool(is_junction())
        except OSError:
            return False
    return False


def _is_linklike_path(path: Path) -> bool:
    return path.is_symlink() or _is_windows_reparse_point(path)


def ensure_safe_file_target(path: Path) -> None:
    inspected_path = absolute_path(path)
    current = inspected_path
    while True:
        if _is_linklike_path(current):
            raise ValueError(
                f"Refusing to access symlinked or reparse-point path '{current}'."
            )
        parent = current.parent
        if parent == current:
            break
        current = parent


def write_text_atomically(path: Path, content: str) -> None:
    target_path = absolute_path(path)
    ensure_safe_file_target(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(target_path.parent),
            prefix=f"{target_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            _ = handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if temporary_path is None:
            raise RuntimeError("Atomic write did not create a temporary file.")
        _ = temporary_path.replace(target_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            _ = temporary_path.unlink()
