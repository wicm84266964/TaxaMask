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


def _existing_path_is_ancestor(ancestor, descendant):
    """Use filesystem identity to detect an existing ancestor of a path."""
    ancestor_path = canonical_path(ancestor)
    probe = canonical_path(descendant)
    if not ancestor_path or not probe:
        return False
    try:
        if not os.path.exists(ancestor_path):
            return False
    except (OSError, TypeError, ValueError):
        return False

    while probe:
        try:
            if os.path.exists(probe) and os.path.samefile(ancestor_path, probe):
                return True
        except (OSError, TypeError, ValueError):
            pass
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    return False


def paths_overlap(left, right):
    """Return whether two physical paths are equal or contain one another."""
    left_identity = path_identity(left)
    right_identity = path_identity(right)
    if not left_identity or not right_identity:
        return False
    if paths_refer_to_same_file(left, right):
        return True
    try:
        common = os.path.normcase(os.path.commonpath([left_identity, right_identity]))
    except ValueError:
        common = ""
    if common in {left_identity, right_identity}:
        return True
    # ``normcase`` is intentionally a no-op on POSIX, including the default
    # case-insensitive macOS filesystem. Compare existing ancestors by file
    # identity so a not-yet-created child cannot bypass the overlap guard via
    # case-only spelling or a directory alias.
    return _existing_path_is_ancestor(left, right) or _existing_path_is_ancestor(right, left)
