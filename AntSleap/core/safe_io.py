import json
import os
import shutil
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
