from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from .tif_workbench_translations import tt


class TifWorkbenchCoordinator:
    PREVIEW_INTERACTION_TASK_TYPES = frozenset({"volume_preview", "mask_preview"})

    def __init__(self, workbench):
        self.workbench = workbench

    def preview_interaction_task_types(self):
        return set(self.PREVIEW_INTERACTION_TASK_TYPES)

    def active_busy_locks(self, ignored_task_types=None):
        ignored = {str(task_type or "") for task_type in (ignored_task_types or set())}
        return [
            task
            for task in self.workbench.task_manager.active_busy_locks()
            if str(getattr(task, "task_type", "") or "") not in ignored
        ]

    def backend_write_lock_active(self, ignored_task_types=None):
        wb = self.workbench
        return bool(
            self.active_busy_locks(ignored_task_types)
            or wb.backend_panel_controller.action_running()
            or wb.roi_workflow_controller.is_confirm_running()
            or wb.local_axis_controller.export_running()
            or wb.annotation_workflow_controller.manual_save_thread is not None
            or wb.annotation_workflow_controller.promote_thread is not None
        )

    def backend_write_lock_message(self, ignored_task_types=None):
        wb = self.workbench
        active_locks = self.active_busy_locks(ignored_task_types)
        if active_locks:
            messages = {
                "truth_promotion": "Training truth acceptance is running. Wait until it finishes before editing project data.",
                "label_auto_save": "Label auto-save is running. Wait until it finishes before editing project data.",
                "label_manual_save": "Label save is running. Wait until it finishes before editing project data.",
                "confirm_part_roi": "Part volume creation is running. Wait until it finishes before editing project data.",
                "local_axis_export": "Local Axis Reslice export is running. Wait until it finishes before editing project data.",
                "backend_action": "Backend run is active. Stop it or wait until it finishes before editing project data.",
                "tif_import": "TIF import is running. Wait until it finishes before editing project data.",
                "amira_import": "AMIRA import is running. Wait until it finishes before editing project data.",
                "tif_materialize": "Working volume build is running. Wait until it finishes before editing project data.",
                "volume_preview": "Volume preview is being rebuilt. Wait until it finishes before editing project data.",
                "mask_preview": "Mask preview is being rebuilt. Wait until it finishes before editing project data.",
            }
            message = messages.get(str(active_locks[0].task_type or ""))
            if message:
                return tt(message, wb.lang)
        if wb.annotation_workflow_controller.promote_thread is not None:
            return tt("Training truth acceptance is running. Wait until it finishes before editing project data.", wb.lang)
        if wb.annotation_workflow_controller.manual_save_thread is not None:
            return tt("Label save is running. Wait until it finishes before editing project data.", wb.lang)
        if wb.roi_workflow_controller.is_confirm_running():
            return tt("Part volume creation is running. Wait until it finishes before editing project data.", wb.lang)
        if wb.local_axis_controller.export_running():
            return tt("Local Axis Reslice export is running. Wait until it finishes before editing project data.", wb.lang)
        return tt("Backend run is active. Stop it or wait until it finishes before editing project data.", wb.lang)

    def backend_write_lock_title(self):
        if self.workbench.roi_workflow_controller.is_confirm_running():
            return tt("Part extraction", self.workbench.lang)
        return tt("TIF backend", self.workbench.lang)

    def guard_backend_write_lock(self, show_message=True, ignored_task_types=None):
        if not self.backend_write_lock_active(ignored_task_types=ignored_task_types):
            return True
        message = self.backend_write_lock_message(ignored_task_types=ignored_task_types)
        if show_message:
            self.workbench._set_operation_feedback(message)
            QMessageBox.information(self.workbench, self.backend_write_lock_title(), message)
        return False
