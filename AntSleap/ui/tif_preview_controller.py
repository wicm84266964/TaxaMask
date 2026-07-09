from __future__ import annotations

try:
    from AntSleap.core.tif_resource_policy import (
        RESOURCE_KIND_COMMIT_MEMORY,
        RESOURCE_KIND_GPU_PREVIEW,
        RESOURCE_KIND_SYSTEM_MEMORY,
        RESOURCE_KIND_VOLUME_IO,
        TifResourceIssue,
        classify_resource_exception,
    )
    from AntSleap.core.tif_volume_io import load_volume_sidecar
    from AntSleap.ui.tif_workbench_translations import tt
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_resource_policy import (
        RESOURCE_KIND_COMMIT_MEMORY,
        RESOURCE_KIND_GPU_PREVIEW,
        RESOURCE_KIND_SYSTEM_MEMORY,
        RESOURCE_KIND_VOLUME_IO,
        TifResourceIssue,
        classify_resource_exception,
    )
    from core.tif_volume_io import load_volume_sidecar
    from ui.tif_workbench_translations import tt


class TifPreviewController:
    def __init__(self, workbench):
        self.workbench = workbench
        self.last_resource_issue = None

    @property
    def lang(self):
        return self.workbench.lang

    def clear_resource_issue(self):
        self.last_resource_issue = None

    def classify_exception(self, exc, *, operation="", path=""):
        return classify_resource_exception(exc, operation=operation, path=path)

    def resource_issue_message(self, issue=None):
        issue = issue if isinstance(issue, TifResourceIssue) else self.last_resource_issue
        if not isinstance(issue, TifResourceIssue):
            return ""
        path = str(issue.path or "").strip()
        if issue.kind == RESOURCE_KIND_COMMIT_MEMORY:
            base = tt(
                "System commit memory/page file is too small to open this TIF volume right now. Close training jobs or increase the Windows page file, then reload the specimen. Project data was not modified.",
                self.lang,
            )
        elif issue.kind == RESOURCE_KIND_SYSTEM_MEMORY:
            base = tt(
                "System memory is not enough to open this TIF volume right now. Close other heavy tasks, then reload the specimen. Project data was not modified.",
                self.lang,
            )
        elif issue.kind == RESOURCE_KIND_GPU_PREVIEW:
            base = tt(
                "3D preview resources are unavailable right now. Slice review and saved project data are not changed.",
                self.lang,
            )
        elif issue.kind == RESOURCE_KIND_VOLUME_IO:
            base = tt(
                "TIF volume could not be opened. Check whether the file still exists and is accessible. Project data was not modified.",
                self.lang,
            )
        else:
            base = tt(
                "A TIF preview resource operation failed. Project data was not modified.",
                self.lang,
            )
        if path:
            return f"{base}\n{tt('Path', self.lang)}: {path}"
        return base

    def record_resource_issue(self, issue):
        if not isinstance(issue, TifResourceIssue):
            return ""
        self.last_resource_issue = issue
        message = self.resource_issue_message(issue)
        wb = self.workbench
        wb._slice_unavailable_override = message
        if hasattr(wb, "canvas"):
            wb.canvas.setText(message)
        if hasattr(wb, "volume_canvas"):
            wb.volume_canvas.setText(message)
        if hasattr(wb, "volume_render_status_label"):
            wb._update_volume_render_status_label(message)
        if hasattr(wb, "training_status_label"):
            wb.training_status_label.setText(message)
            wb.training_status_label.setToolTip(str(issue.original_error or ""))
        if hasattr(wb, "_set_operation_feedback"):
            wb._set_operation_feedback(message)
        else:
            try:
                wb.log(message)
            except Exception:
                pass
        return message

    def safe_load_volume_sidecar(self, path, *, mmap_mode="r", operation="load_volume"):
        try:
            return load_volume_sidecar(path, mmap_mode=mmap_mode), None
        except Exception as exc:
            issue = self.classify_exception(exc, operation=operation, path=str(path or ""))
            self.record_resource_issue(issue)
            return None, issue

    def state_summary(self):
        issue = self.last_resource_issue
        if not isinstance(issue, TifResourceIssue):
            return {"resource_limited": False}
        data = issue.to_dict()
        data["resource_limited"] = True
        data["user_message"] = self.resource_issue_message(issue)
        return data
