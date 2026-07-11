from __future__ import annotations

import gc
import threading
import time

from PySide6.QtWidgets import QMessageBox

try:
    from AntSleap.ui.tif_workbench_translations import tt
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from ui.tif_workbench_translations import tt


class TifProjectLifecycleController:
    def __init__(self, workbench):
        self.workbench = workbench
        self._array_release_threads = set()
        self._array_release_lock = threading.Lock()

    @staticmethod
    def _close_volume_array(array):
        mmap = getattr(array, "_mmap", None)
        if mmap is not None:
            try:
                mmap.close()
            except Exception:
                pass

    def release_volume_arrays(self, arrays, preview_thread=None, defer=False):
        unique_arrays = []
        seen = set()
        for array in arrays or ():
            if array is None or id(array) in seen:
                continue
            seen.add(id(array))
            unique_arrays.append(array)

        def release():
            if preview_thread is not None:
                try:
                    if preview_thread.isRunning():
                        preview_thread.wait()
                except RuntimeError:
                    pass
            for array in unique_arrays:
                self._close_volume_array(array)

        if not defer or not unique_arrays:
            release()
            gc.collect()
            return None

        def run():
            try:
                release()
            finally:
                with self._array_release_lock:
                    self._array_release_threads.discard(threading.current_thread())

        thread = threading.Thread(target=run, name="TifVolumeArrayRelease", daemon=True)
        with self._array_release_lock:
            self._array_release_threads.add(thread)
        thread.start()
        return thread

    def wait_for_volume_array_releases(self, timeout_ms=5000):
        deadline = time.monotonic() + max(0.0, float(timeout_ms) / 1000.0)
        with self._array_release_lock:
            threads = list(self._array_release_threads)
        for thread in threads:
            remaining = max(0.0, deadline - time.monotonic())
            thread.join(remaining)
        with self._array_release_lock:
            return not any(thread.is_alive() for thread in self._array_release_threads)

    def close_project(self, prompt_unsaved=True):
        workbench = self.workbench
        if self.background_write_running():
            if prompt_unsaved:
                self._show_background_task_message()
            return False
        if not workbench.volume_render_controller._cancel_and_wait_volume_preview_build():
            if prompt_unsaved:
                QMessageBox.information(
                    workbench,
                    tt("Volume render", workbench.lang),
                    tt("The 3D preview is still stopping. Wait a moment, then close the project again.", workbench.lang),
                )
            return False
        if not workbench.part_mask_workflow_controller.cancel_and_wait_preview():
            if prompt_unsaved:
                QMessageBox.information(
                    workbench,
                    tt("Part extraction", workbench.lang),
                    tt("The part mask preview is still stopping. Wait a moment, then close the project again.", workbench.lang),
                )
            return False
        if not self.wait_for_volume_array_releases():
            if prompt_unsaved:
                QMessageBox.information(
                    workbench,
                    tt("Volume render", workbench.lang),
                    tt("Previous volume data is still being released. Wait a moment, then close the project again.", workbench.lang),
                )
            return False
        workbench.annotation_workflow_controller.wait_for_auto_save()
        if prompt_unsaved and not workbench.annotation_workflow_controller.confirm_discard_or_save():
            return False
        self._clear_loaded_project_state()
        return True

    def background_write_running(self):
        workbench = self.workbench
        return any(
            getattr(workbench, name, None) is not None
            for name in (
                "_tif_import_thread",
                "_local_axis_reslice_export_thread",
                "_tif_backend_thread",
                "_label_auto_save_thread",
                "_label_manual_save_thread",
                "_promote_thread",
            )
        ) or workbench.roi_workflow_controller.is_confirm_running() or workbench.part_mask_workflow_controller.materialize_thread is not None

    def _show_background_task_message(self):
        workbench = self.workbench
        label_write_running = any(
            getattr(workbench, name, None) is not None
            for name in ("_label_auto_save_thread", "_label_manual_save_thread", "_promote_thread")
        )
        if label_write_running:
            message = workbench.coordinator.backend_write_lock_message() if workbench.coordinator.backend_write_lock_active() else tt("Auto-save is still finishing. Wait a moment, then try again.", workbench.lang)
            title = workbench.coordinator.backend_write_lock_title() if workbench.coordinator.backend_write_lock_active() else tt("TIF backend", workbench.lang)
            QMessageBox.information(workbench, title, message)
            return
        QMessageBox.information(
            workbench,
            tt("TIF data import", workbench.lang),
            tt("Wait for the current backend task to finish before closing the project.", workbench.lang)
            if workbench._tif_backend_thread is not None
            else tt("Wait for the current background TIF task to finish before closing the project.", workbench.lang),
        )

    def _clear_loaded_project_state(self):
        workbench = self.workbench
        workbench.volume_render_controller._clear_volume_preview_cache()
        workbench.volume_render_controller.release_volume_renderer()
        workbench.result_review_controller.invalidate_result_region_mask_cache(clear_active_mask_preview=False)
        workbench.release_loaded_volume_arrays()
        self.wait_for_volume_array_releases()
        workbench.part_mask_workflow_controller.reset_state()
        workbench.annotation_workflow_controller.reset_dirty_tracking()
        workbench.auto_save_timer.stop()
        if hasattr(workbench, "volume_still_timer"):
            workbench.volume_still_timer.stop()
        dialog = getattr(workbench, "_tif_training_result_dialog", None)
        if dialog is not None:
            try:
                dialog.close()
            except Exception:
                pass
            workbench._tif_training_result_dialog = None
        if hasattr(workbench, "training_result_summary_label"):
            workbench.backend_panel_controller._set_training_result_summary(None)
        workbench.current_part = None
        workbench.local_axis_draft = None
        workbench.roi_workflow_controller.reset_state()
        workbench.part_mask_workflow_controller.reset_state()
        workbench.annotation_workflow_controller.reset_history()
        workbench.selection_workflow_controller.clear_state()
        workbench._sync_undo_redo_buttons()
        workbench._update_save_status()
        workbench.canvas.clear()
        workbench.volume_canvas.clear()
        workbench.canvas.setText(tt("No TIF volume loaded", workbench.lang))
        workbench.volume_canvas.setText(tt("No TIF volume loaded", workbench.lang))
        workbench.volume_render_controller._update_volume_render_status_label(tt("No TIF volume loaded", workbench.lang))
