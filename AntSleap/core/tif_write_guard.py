import os
from dataclasses import dataclass, field

from .tif_label_guard import GuardResult, allow, deny


@dataclass(frozen=True)
class WriteIntent:
    target_path: str
    project_root: str = ""
    source_path: str = ""
    source_role: str = ""
    target_role: str = ""
    operation: str = ""
    audit_metadata: dict = field(default_factory=dict)
    allow_overwrite: bool = False
    allowed_roots: tuple = field(default_factory=tuple)
    protected_paths: tuple = field(default_factory=tuple)

    def to_dict(self):
        return {
            "target_path": self.target_path,
            "project_root": self.project_root,
            "source_path": self.source_path,
            "source_role": self.source_role,
            "target_role": self.target_role,
            "operation": self.operation,
            "audit_metadata": dict(self.audit_metadata or {}),
            "allow_overwrite": bool(self.allow_overwrite),
            "allowed_roots": list(self.allowed_roots or ()),
            "protected_paths": list(self.protected_paths or ()),
        }


def _abs(path):
    text = str(path or "").strip()
    if not text:
        return ""
    return os.path.normcase(os.path.abspath(text))


def _is_within(path, root):
    clean_path = _abs(path)
    clean_root = _abs(root)
    if not clean_path or not clean_root:
        return False
    try:
        return os.path.commonpath([clean_path, clean_root]) == clean_root
    except ValueError:
        return False


def _path_matches_or_is_inside(path, protected):
    clean_path = _abs(path)
    clean_protected = _abs(protected)
    if not clean_path or not clean_protected:
        return False
    if clean_path == clean_protected:
        return True
    return _is_within(clean_path, clean_protected)


def can_write_path(intent, *, allowed_roots=None, protected_paths=None):
    if not isinstance(intent, WriteIntent):
        raise TypeError("intent_must_be_write_intent")
    target = _abs(intent.target_path)
    details = intent.to_dict()
    details["target_abs"] = target
    if not target:
        return deny("write_target_path_required", details=details)

    roots = list(allowed_roots or intent.allowed_roots or ())
    if intent.project_root:
        roots.append(intent.project_root)
    roots = [item for item in roots if str(item or "").strip()]
    if roots and not any(_is_within(target, root) for root in roots):
        return deny("write_target_outside_allowed_roots", details={**details, "allowed_roots": roots})

    protected = list(protected_paths or intent.protected_paths or ())
    if intent.source_path:
        protected.append(intent.source_path)
    for item in protected:
        if _path_matches_or_is_inside(target, item):
            return deny("write_target_matches_protected_source", details={**details, "protected_path": str(item)})

    if os.path.exists(target) and not intent.allow_overwrite:
        return deny("write_target_exists_without_overwrite_intent", details=details)

    return allow("write_path_allowed", details=details)


def ensure_write_allowed(intent, *, allowed_roots=None, protected_paths=None):
    result = can_write_path(intent, allowed_roots=allowed_roots, protected_paths=protected_paths)
    if result:
        return result
    if isinstance(result, GuardResult):
        raise ValueError(f"tif_write_guard_denied:{result.reason}:{result.details}")
    raise ValueError("tif_write_guard_denied")
