from __future__ import annotations

from dataclasses import dataclass, field


RESOURCE_KIND_COMMIT_MEMORY = "commit_memory"
RESOURCE_KIND_SYSTEM_MEMORY = "system_memory"
RESOURCE_KIND_GPU_PREVIEW = "gpu_preview"
RESOURCE_KIND_VOLUME_IO = "volume_io"
RESOURCE_KIND_UNKNOWN = "unknown_resource"


@dataclass(frozen=True)
class TifResourceIssue:
    kind: str
    operation: str = ""
    path: str = ""
    message: str = ""
    original_error: str = ""
    winerror: int | None = None
    errno: int | None = None
    recoverable: bool = True
    edit_limited: bool = False
    details: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "kind": str(self.kind or ""),
            "operation": str(self.operation or ""),
            "path": str(self.path or ""),
            "message": str(self.message or ""),
            "original_error": str(self.original_error or ""),
            "winerror": self.winerror,
            "errno": self.errno,
            "recoverable": bool(self.recoverable),
            "edit_limited": bool(self.edit_limited),
            "details": dict(self.details or {}),
        }


def _clean_int(value):
    try:
        return int(value)
    except Exception:
        return None


def _error_text(exc):
    try:
        return str(exc or "")
    except Exception:
        return ""


def classify_resource_exception(exc, *, operation="", path=""):
    text = _error_text(exc)
    lower = text.lower()
    winerror = _clean_int(getattr(exc, "winerror", None))
    errno = _clean_int(getattr(exc, "errno", None))
    details = {"exception_type": type(exc).__name__}

    if isinstance(exc, MemoryError):
        return TifResourceIssue(
            kind=RESOURCE_KIND_SYSTEM_MEMORY,
            operation=operation,
            path=path,
            message="system_memory_exhausted",
            original_error=text,
            winerror=winerror,
            errno=errno,
            edit_limited=True,
            details=details,
        )

    commit_markers = (
        "页面文件太小",
        "paging file is too small",
        "page file",
        "commit limit",
        "not enough memory resources",
        "winerror 1455",
    )
    if winerror == 1455 or errno == 1455 or any(marker in lower for marker in commit_markers):
        return TifResourceIssue(
            kind=RESOURCE_KIND_COMMIT_MEMORY,
            operation=operation,
            path=path,
            message="windows_commit_memory_exhausted",
            original_error=text,
            winerror=1455 if winerror is None else winerror,
            errno=errno,
            edit_limited=True,
            details=details,
        )

    gpu_markers = (
        "opengl",
        "qopengl",
        "gpu",
        "gl_context",
        "gl context",
        "texture",
        "shader",
        "framebuffer",
    )
    if any(marker in lower for marker in gpu_markers):
        return TifResourceIssue(
            kind=RESOURCE_KIND_GPU_PREVIEW,
            operation=operation,
            path=path,
            message="gpu_preview_resource_failed",
            original_error=text,
            winerror=winerror,
            errno=errno,
            edit_limited=False,
            details=details,
        )

    if isinstance(exc, OSError):
        return TifResourceIssue(
            kind=RESOURCE_KIND_VOLUME_IO,
            operation=operation,
            path=path,
            message="volume_io_failed",
            original_error=text,
            winerror=winerror,
            errno=errno,
            edit_limited=True,
            details=details,
        )

    return TifResourceIssue(
        kind=RESOURCE_KIND_UNKNOWN,
        operation=operation,
        path=path,
        message="resource_operation_failed",
        original_error=text,
        winerror=winerror,
        errno=errno,
        edit_limited=True,
        details=details,
    )


def is_commit_memory_issue(issue):
    return isinstance(issue, TifResourceIssue) and issue.kind == RESOURCE_KIND_COMMIT_MEMORY


def is_resource_limited_issue(issue):
    return isinstance(issue, TifResourceIssue) and issue.kind in {
        RESOURCE_KIND_COMMIT_MEMORY,
        RESOURCE_KIND_SYSTEM_MEMORY,
        RESOURCE_KIND_GPU_PREVIEW,
        RESOURCE_KIND_VOLUME_IO,
    }

