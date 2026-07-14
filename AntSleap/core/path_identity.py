import os


def canonical_path(path):
    """Return a stable absolute spelling for an existing path or its existing parents."""
    if path is None:
        return ""
    text = str(path)
    if not text.strip():
        return ""
    absolute = os.path.abspath(os.path.normpath(os.path.expanduser(text)))
    return os.path.normpath(os.path.realpath(absolute))


def path_identity(path):
    canonical = canonical_path(path)
    return os.path.normcase(canonical) if canonical else ""


def paths_refer_to_same_file(left, right):
    if not left or not right:
        return False
    try:
        if os.path.exists(left) and os.path.exists(right):
            return os.path.samefile(left, right)
    except (OSError, TypeError, ValueError):
        pass
    left_identity = path_identity(left)
    return bool(left_identity) and left_identity == path_identity(right)
