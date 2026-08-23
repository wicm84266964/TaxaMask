import json
import os
import secrets
import shutil
import stat
import tempfile
import time


def _fsync_directory(path):
    try:
        dir_fd = os.open(path or ".", os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


class UnsafeFilesystemPath(ValueError):
    """Raised when a project-local file path crosses an unsafe filesystem entry."""


def _is_link_or_reparse(result):
    attributes = int(getattr(result, "st_file_attributes", 0) or 0)
    reparse_flag = int(
        getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400) or 0x400
    )
    return stat.S_ISLNK(result.st_mode) or bool(attributes & reparse_flag)


def _same_file_stat(left, right):
    left_inode = int(getattr(left, "st_ino", 0) or 0)
    right_inode = int(getattr(right, "st_ino", 0) or 0)
    left_device = int(getattr(left, "st_dev", 0) or 0)
    right_device = int(getattr(right, "st_dev", 0) or 0)
    if left_inode and right_inode:
        return (left_device, left_inode) == (right_device, right_inode)
    return True


def _same_file_content_stat(left, right):
    if not _same_file_stat(left, right):
        return False
    return (
        int(getattr(left, "st_size", -1)) == int(getattr(right, "st_size", -2))
        and int(getattr(left, "st_mtime_ns", 0) or 0)
        == int(getattr(right, "st_mtime_ns", 0) or 0)
    )


def _safe_path_plan(path, trusted_root):
    root = os.path.normpath(os.path.realpath(os.path.abspath(os.fspath(trusted_root))))
    target = os.path.normpath(os.path.abspath(os.fspath(path)))
    parent = os.path.dirname(target) or "."
    try:
        common = os.path.commonpath([root, target])
    except ValueError as exc:
        raise UnsafeFilesystemPath("path_outside_trusted_root") from exc
    if os.path.normcase(common) != os.path.normcase(root) or target == root:
        raise UnsafeFilesystemPath("path_outside_trusted_root")
    if not os.path.isdir(root):
        raise UnsafeFilesystemPath("trusted_root_not_directory")
    relative_parent = os.path.relpath(parent, root)
    if relative_parent == os.curdir:
        parts = []
    elif relative_parent == os.pardir or relative_parent.startswith(os.pardir + os.sep):
        raise UnsafeFilesystemPath("path_outside_trusted_root")
    else:
        parts = relative_parent.split(os.sep)
    return root, target, parent, parts


def _require_safe_parent(path, trusted_root, *, create=False):
    root, target, parent, parts = _safe_path_plan(path, trusted_root)

    current = root
    for part in parts:
        current = os.path.join(current, part)
        if not os.path.lexists(current):
            if not create:
                raise FileNotFoundError(current)
            try:
                os.mkdir(current, 0o700)
            except FileExistsError:
                pass
        result = os.lstat(current)
        if _is_link_or_reparse(result) or not stat.S_ISDIR(result.st_mode):
            raise UnsafeFilesystemPath("unsafe_parent_entry")

    resolved_parent = os.path.normpath(os.path.realpath(parent))
    try:
        resolved_common = os.path.commonpath([root, resolved_parent])
    except ValueError as exc:
        raise UnsafeFilesystemPath("path_outside_trusted_root") from exc
    if os.path.normcase(resolved_common) != os.path.normcase(root):
        raise UnsafeFilesystemPath("path_outside_trusted_root")
    return root, target, parent


def _directory_fd_guards_available():
    return (
        os.name != "nt"
        and os.open in getattr(os, "supports_dir_fd", set())
        and os.stat in getattr(os, "supports_dir_fd", set())
        and os.mkdir in getattr(os, "supports_dir_fd", set())
        and os.rename in getattr(os, "supports_dir_fd", set())
        and os.unlink in getattr(os, "supports_dir_fd", set())
        and bool(getattr(os, "O_DIRECTORY", 0))
        and bool(getattr(os, "O_NOFOLLOW", 0))
    )


def _open_safe_parent(path, trusted_root, *, create=False):
    """Return a verified parent fd on POSIX, with a checked path fallback on Windows.

    Python's Windows stdlib has no open-relative equivalent for directory handles.
    The fallback rejects reparse points before and after opening, but cannot make a
    hostile concurrent parent-directory replacement fully atomic.
    """

    if not _directory_fd_guards_available():
        root, target, parent = _require_safe_parent(
            path, trusted_root, create=create
        )
        return root, target, parent, None

    root, target, parent, parts = _safe_path_plan(path, trusted_root)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    before_root = os.lstat(root)
    root_fd = os.open(root, directory_flags)
    current_fd = root_fd
    try:
        opened_root = os.fstat(root_fd)
        after_root = os.lstat(root)
        if (
            _is_link_or_reparse(before_root)
            or not stat.S_ISDIR(before_root.st_mode)
            or not stat.S_ISDIR(opened_root.st_mode)
            or not _same_file_stat(before_root, opened_root)
            or not _same_file_stat(opened_root, after_root)
        ):
            raise UnsafeFilesystemPath("trusted_root_identity_changed")
        for part in parts:
            next_fd = -1
            try:
                try:
                    next_fd = os.open(part, directory_flags, dir_fd=current_fd)
                except FileNotFoundError:
                    if not create:
                        raise
                    try:
                        os.mkdir(part, 0o700, dir_fd=current_fd)
                    except FileExistsError:
                        pass
                    next_fd = os.open(part, directory_flags, dir_fd=current_fd)
                except OSError as exc:
                    try:
                        blocked_entry = os.stat(
                            part,
                            dir_fd=current_fd,
                            follow_symlinks=False,
                        )
                    except OSError:
                        raise exc
                    if _is_link_or_reparse(blocked_entry) or not stat.S_ISDIR(
                        blocked_entry.st_mode
                    ):
                        raise UnsafeFilesystemPath(
                            "unsafe_parent_entry"
                        ) from exc
                    raise
                opened = os.fstat(next_fd)
                if _is_link_or_reparse(opened) or not stat.S_ISDIR(opened.st_mode):
                    raise UnsafeFilesystemPath("unsafe_parent_entry")
            except Exception:
                if next_fd >= 0:
                    os.close(next_fd)
                raise
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd
        if current_fd == root_fd:
            root_fd = -1
        return root, target, parent, current_fd
    except Exception:
        if current_fd >= 0:
            os.close(current_fd)
        raise
    finally:
        if root_fd >= 0 and root_fd != current_fd:
            os.close(root_fd)


def _entry_stat(path, parent_fd=None):
    if parent_fd is None:
        return os.lstat(path)
    return os.stat(
        os.path.basename(path),
        dir_fd=parent_fd,
        follow_symlinks=False,
    )


def _entry_exists(path, parent_fd=None):
    try:
        _entry_stat(path, parent_fd)
        return True
    except FileNotFoundError:
        return False


def _require_safe_regular_entry_at(path, parent_fd=None):
    result = _entry_stat(path, parent_fd)
    if _is_link_or_reparse(result) or not stat.S_ISREG(result.st_mode):
        raise UnsafeFilesystemPath("unsafe_regular_file_entry")
    return result


def _open_entry(path, flags, mode=0o600, *, parent_fd=None):
    if parent_fd is None:
        return os.open(path, flags, mode)
    return os.open(os.path.basename(path), flags, mode, dir_fd=parent_fd)


def _require_safe_regular_entry(path):
    result = os.lstat(path)
    if _is_link_or_reparse(result) or not stat.S_ISREG(result.st_mode):
        raise UnsafeFilesystemPath("unsafe_regular_file_entry")
    return result


def read_json_bounded_in_root(path, *, trusted_root, max_bytes):
    """Read one regular JSON file through a single, size-bounded descriptor."""
    _root, target, _parent, parent_fd = _open_safe_parent(
        path, trusted_root, create=False
    )
    descriptor = -1
    try:
        before = _require_safe_regular_entry_at(target, parent_fd)
        flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
        flags |= int(getattr(os, "O_NOFOLLOW", 0))
        if os.name != "nt":
            flags |= int(getattr(os, "O_NONBLOCK", 0))
        descriptor = _open_entry(target, flags, parent_fd=parent_fd)
        opened_before = os.fstat(descriptor)
        if _is_link_or_reparse(opened_before) or not stat.S_ISREG(opened_before.st_mode):
            raise UnsafeFilesystemPath("opened_entry_not_regular")
        after_open = _require_safe_regular_entry_at(target, parent_fd)
        if not _same_file_stat(before, opened_before) or not _same_file_stat(
            opened_before, after_open
        ):
            raise UnsafeFilesystemPath("file_identity_changed_during_open")
        if parent_fd is None:
            _require_safe_parent(target, trusted_root, create=False)

        limit = int(max_bytes)
        if limit < 0:
            raise ValueError("max_bytes_must_be_nonnegative")
        chunks = []
        remaining = limit + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > limit:
            raise ValueError("json_file_too_large")
        opened_after = os.fstat(descriptor)
        final_entry = _require_safe_regular_entry_at(target, parent_fd)
        if not _same_file_content_stat(opened_before, opened_after):
            raise UnsafeFilesystemPath("file_content_changed_during_read")
        if not _same_file_content_stat(opened_after, final_entry):
            raise UnsafeFilesystemPath("file_identity_changed_during_read")
        if parent_fd is None:
            _require_safe_parent(target, trusted_root, create=False)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if parent_fd is not None:
            os.close(parent_fd)
    return json.loads(raw.decode("utf-8"))


def atomic_write_json_in_root(
    path,
    payload,
    *,
    trusted_root,
    max_bytes=None,
    indent=2,
    ensure_ascii=False,
    validate=True,
):
    """Atomically write JSON without following project-local links or fixed temp names."""
    serialized = json.dumps(
        payload,
        ensure_ascii=ensure_ascii,
        indent=indent,
    ).encode("utf-8")
    if max_bytes is not None and len(serialized) > int(max_bytes):
        raise ValueError("json_payload_too_large")
    if validate:
        loaded = json.loads(serialized.decode("utf-8"))
        if not isinstance(loaded, type(payload)):
            raise ValueError("atomic_json_type_changed")

    _root, target, parent, parent_fd = _open_safe_parent(
        path, trusted_root, create=True
    )
    descriptor = -1
    tmp_path = ""
    tmp_name = ""
    opened = None
    try:
        if _entry_exists(target, parent_fd):
            _require_safe_regular_entry_at(target, parent_fd)
        if parent_fd is None:
            descriptor, tmp_path = tempfile.mkstemp(
                prefix=f".{os.path.basename(target)}.tmp-",
                dir=parent,
            )
            tmp_name = os.path.basename(tmp_path)
        else:
            for _attempt in range(100):
                tmp_name = (
                    f".{os.path.basename(target)}.tmp-{secrets.token_hex(12)}"
                )
                try:
                    descriptor = os.open(
                        tmp_name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=parent_fd,
                    )
                    tmp_path = os.path.join(parent, tmp_name)
                    break
                except FileExistsError:
                    continue
            if descriptor < 0:
                raise FileExistsError("atomic_json_temp_name_exhausted")
        opened = os.fstat(descriptor)
        if _is_link_or_reparse(opened) or not stat.S_ISREG(opened.st_mode):
            raise UnsafeFilesystemPath("temporary_entry_not_regular")
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())

        if parent_fd is None:
            _require_safe_parent(target, trusted_root, create=False)
        current_tmp = _require_safe_regular_entry_at(tmp_path, parent_fd)
        if not _same_file_stat(opened, current_tmp):
            raise UnsafeFilesystemPath("temporary_file_identity_changed")
        if _entry_exists(target, parent_fd):
            _require_safe_regular_entry_at(target, parent_fd)
        if parent_fd is None:
            os.replace(tmp_path, target)
        else:
            os.rename(
                tmp_name,
                os.path.basename(target),
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
        tmp_path = ""
        if parent_fd is None:
            _fsync_directory(parent)
        else:
            os.fsync(parent_fd)
    finally:
        if descriptor >= 0:
            if opened is None:
                try:
                    opened = os.fstat(descriptor)
                except OSError:
                    if os.stat in getattr(os, "supports_fd", set()):
                        try:
                            opened = os.stat(descriptor)
                        except OSError:
                            pass
            try:
                os.close(descriptor)
            except OSError:
                pass
        if tmp_path and _entry_exists(tmp_path, parent_fd):
            try:
                current_tmp = _entry_stat(tmp_path, parent_fd)
                if (
                    not _is_link_or_reparse(current_tmp)
                    and stat.S_ISREG(current_tmp.st_mode)
                    and opened is not None
                    and _same_file_stat(opened, current_tmp)
                ):
                    if parent_fd is None:
                        os.remove(tmp_path)
                    else:
                        os.unlink(tmp_name, dir_fd=parent_fd)
            except OSError:
                pass
        if parent_fd is not None:
            os.close(parent_fd)
    return payload


def isolate_regular_file_in_root(path, rejected_path, *, trusted_root):
    """Move a regular project-local file to one bounded rejected-file slot."""
    _rejected_root, rejected, rejected_parent, _parts = _safe_path_plan(
        rejected_path, trusted_root
    )
    _root, source, parent, parent_fd = _open_safe_parent(
        path, trusted_root, create=False
    )
    if os.path.normcase(os.path.normpath(rejected_parent)) != os.path.normcase(
        os.path.normpath(parent)
    ):
        if parent_fd is not None:
            os.close(parent_fd)
        raise UnsafeFilesystemPath("isolation_target_parent_mismatch")
    if os.path.normcase(source) == os.path.normcase(rejected):
        if parent_fd is not None:
            os.close(parent_fd)
        raise UnsafeFilesystemPath("isolation_target_matches_source")

    descriptor = -1
    opened = None
    try:
        before = _require_safe_regular_entry_at(source, parent_fd)
        flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
        flags |= int(getattr(os, "O_NOFOLLOW", 0))
        if os.name != "nt":
            flags |= int(getattr(os, "O_NONBLOCK", 0))
        descriptor = _open_entry(source, flags, parent_fd=parent_fd)
        opened = os.fstat(descriptor)
        after_open = _require_safe_regular_entry_at(source, parent_fd)
        if (
            _is_link_or_reparse(opened)
            or not stat.S_ISREG(opened.st_mode)
            or not _same_file_stat(before, opened)
            or not _same_file_stat(opened, after_open)
        ):
            raise UnsafeFilesystemPath("isolation_source_identity_changed")
        if _entry_exists(rejected, parent_fd):
            existing_rejected = _require_safe_regular_entry_at(rejected, parent_fd)
            if _same_file_stat(opened, existing_rejected):
                raise UnsafeFilesystemPath("isolation_target_matches_source")

        if parent_fd is None:
            os.close(descriptor)
            descriptor = -1
            _require_safe_parent(source, trusted_root, create=False)
            _require_safe_parent(rejected, trusted_root, create=False)
            os.replace(source, rejected)
        else:
            os.rename(
                os.path.basename(source),
                os.path.basename(rejected),
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
        moved = _require_safe_regular_entry_at(rejected, parent_fd)
        if not _same_file_content_stat(opened, moved):
            raise UnsafeFilesystemPath("isolation_source_identity_changed")
        if parent_fd is None:
            _require_safe_parent(rejected, trusted_root, create=False)
            _fsync_directory(parent)
        else:
            os.fsync(parent_fd)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if parent_fd is not None:
            os.close(parent_fd)
    return rejected


class AdvisoryFileLock:
    """Process-scoped advisory lock; the lock file may remain but never stays locked."""

    def __init__(self, path, *, trusted_root, timeout=5.0, poll_interval=0.05):
        self.path = os.path.abspath(os.fspath(path))
        self.trusted_root = os.path.abspath(os.fspath(trusted_root))
        self.timeout = max(0.0, float(timeout))
        self.poll_interval = max(0.001, float(poll_interval))
        self.handle = None

    def acquire(self):
        if self.handle is not None:
            raise RuntimeError("advisory_file_lock_already_acquired")
        _root, target, _parent, parent_fd = _open_safe_parent(
            self.path, self.trusted_root, create=True
        )
        descriptor = -1
        handle = None
        try:
            before = None
            if _entry_exists(target, parent_fd):
                before = _require_safe_regular_entry_at(target, parent_fd)
                if int(getattr(before, "st_nlink", 1) or 1) != 1:
                    raise UnsafeFilesystemPath("unsafe_lock_hardlink")
            flags = os.O_RDWR | os.O_CREAT | int(getattr(os, "O_BINARY", 0))
            flags |= int(getattr(os, "O_NOFOLLOW", 0))
            descriptor = _open_entry(target, flags, 0o600, parent_fd=parent_fd)
            handle = os.fdopen(descriptor, "r+b", closefd=True)
            descriptor = -1
            opened = os.fstat(handle.fileno())
            if _is_link_or_reparse(opened) or not stat.S_ISREG(opened.st_mode):
                raise UnsafeFilesystemPath("lock_entry_not_regular")
            if int(getattr(opened, "st_nlink", 1) or 1) != 1:
                raise UnsafeFilesystemPath("unsafe_lock_hardlink")
            after = _require_safe_regular_entry_at(target, parent_fd)
            if before is not None and not _same_file_stat(before, opened):
                raise UnsafeFilesystemPath("lock_identity_changed_during_open")
            if not _same_file_stat(opened, after):
                raise UnsafeFilesystemPath("lock_identity_changed_during_open")
            if parent_fd is None:
                _require_safe_parent(target, self.trusted_root, create=False)
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
                os.fsync(handle.fileno())

            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(
                            handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                        )
                    break
                except (OSError, IOError):
                    if time.monotonic() >= deadline:
                        handle.close()
                        handle = None
                        return False
                    time.sleep(self.poll_interval)
        except Exception:
            if handle is not None:
                handle.close()
            elif descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            raise
        finally:
            if parent_fd is not None:
                os.close(parent_fd)
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

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError("advisory_file_lock_timeout")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        return False


def atomic_write_json(path, payload, *, indent=2, ensure_ascii=False, validate=True):
    target = os.path.abspath(str(path))
    directory = os.path.dirname(target) or "."
    os.makedirs(directory, exist_ok=True)
    tmp_path = f"{target}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=ensure_ascii, indent=indent)
            handle.flush()
            os.fsync(handle.fileno())
        if validate:
            with open(tmp_path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, type(payload)):
                raise ValueError(f"atomic_json_type_changed:{target}")
        os.replace(tmp_path, target)
        _fsync_directory(directory)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise
    return payload


def atomic_write_text(path, text, *, encoding="utf-8"):
    target = os.path.abspath(str(path))
    directory = os.path.dirname(target) or "."
    os.makedirs(directory, exist_ok=True)
    tmp_path = f"{target}.tmp"
    try:
        with open(tmp_path, "w", encoding=encoding) as handle:
            handle.write(str(text))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
        _fsync_directory(directory)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise
    return path


def backup_file(path, backup_dir, *, stem=None, suffix=".bak", limit=30, min_interval_seconds=300):
    source = os.path.abspath(str(path))
    if not os.path.exists(source):
        return ""
    try:
        if os.path.getsize(source) <= 0:
            return ""
    except OSError:
        return ""

    os.makedirs(backup_dir, exist_ok=True)
    base = stem or os.path.splitext(os.path.basename(source))[0] or "file"
    existing = [
        os.path.join(backup_dir, name)
        for name in os.listdir(backup_dir)
        if name.startswith(f"{base}.") and name.endswith(suffix)
    ]
    if existing:
        latest_mtime = max(os.path.getmtime(item) for item in existing if os.path.exists(item))
        if time.time() - latest_mtime < min_interval_seconds:
            return ""

    backup_path = os.path.join(backup_dir, f"{base}.{time.strftime('%Y%m%d_%H%M%S')}{suffix}")
    tmp_backup_path = f"{backup_path}.tmp"
    shutil.copy2(source, tmp_backup_path)
    os.replace(tmp_backup_path, backup_path)
    _fsync_directory(backup_dir)

    backups = sorted(
        [
            os.path.join(backup_dir, name)
            for name in os.listdir(backup_dir)
            if name.startswith(f"{base}.") and name.endswith(suffix)
        ],
        key=lambda item: os.path.getmtime(item),
        reverse=True,
    )
    for old_backup in backups[limit:]:
        try:
            os.remove(old_backup)
        except OSError:
            pass
    return backup_path


def copytree_replace_safely(source, target, *, backup_suffix=None):
    source_abs = os.path.abspath(str(source))
    target_abs = os.path.abspath(str(target))
    parent = os.path.dirname(target_abs) or "."
    os.makedirs(parent, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    tmp_target = f"{target_abs}.tmp_copy_{stamp}_{os.getpid()}"
    backup_target = backup_suffix or f"{target_abs}.bak_{stamp}_{os.getpid()}"
    moved_old = False
    try:
        shutil.copytree(source_abs, tmp_target)
        if os.path.exists(target_abs):
            os.replace(target_abs, backup_target)
            moved_old = True
        os.replace(tmp_target, target_abs)
        _fsync_directory(parent)
        if moved_old and os.path.exists(backup_target):
            shutil.rmtree(backup_target)
        return target_abs
    except Exception:
        try:
            if os.path.exists(tmp_target):
                shutil.rmtree(tmp_target)
        except OSError:
            pass
        if moved_old and not os.path.exists(target_abs) and os.path.exists(backup_target):
            try:
                os.replace(backup_target, target_abs)
            except OSError:
                pass
        raise


def replace_directory_safely(source_dir, target_dir, *, backup_suffix=None):
    source_abs = os.path.abspath(str(source_dir))
    target_abs = os.path.abspath(str(target_dir))
    parent = os.path.dirname(target_abs) or "."
    os.makedirs(parent, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_target = backup_suffix or f"{target_abs}.bak_{stamp}_{os.getpid()}"
    moved_old = False
    try:
        if os.path.exists(target_abs):
            os.replace(target_abs, backup_target)
            moved_old = True
        os.replace(source_abs, target_abs)
        _fsync_directory(parent)
        if moved_old and os.path.exists(backup_target):
            shutil.rmtree(backup_target)
        return target_abs
    except Exception:
        if moved_old and not os.path.exists(target_abs) and os.path.exists(backup_target):
            try:
                os.replace(backup_target, target_abs)
            except OSError:
                pass
        raise
