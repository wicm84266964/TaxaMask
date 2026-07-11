from __future__ import annotations

from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication

try:
    from AntSleap.ui.tif_workbench_translations import tt
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from ui.tif_workbench_translations import tt


class TifSelectionWorkflowController:
    VIEW_SCOPE = "selection"

    def __init__(self, workbench):
        self.workbench = workbench
        self.selection = workbench.selection_controller

    def bind_signals(self):
        view = self.workbench.workbench_view
        view.register_scope(self.VIEW_SCOPE, "specimen_list")
        tree = view.require(self.VIEW_SCOPE, "specimen_list")
        router = self.workbench.signal_router
        router.bind(self.VIEW_SCOPE, "current_item_changed", tree.currentItemChanged, self.on_tree_selection_changed)
        router.bind(self.VIEW_SCOPE, "context_menu", tree.customContextMenuRequested, self.workbench._on_specimen_tree_context_menu)

    def sync_state_from_workbench(self):
        return self.selection.update(
            specimen_id=self.workbench.current_specimen_id,
            volume_scope=self.workbench.current_volume_scope,
            part_id=self.workbench.current_part_id,
            reslice_id=self.workbench.current_reslice_id,
            label_role=self.workbench.label_role_combo.currentData() if hasattr(self.workbench, "label_role_combo") else "",
            display_mode=self.workbench.display_mode,
        )

    def clear_state(self):
        result = self.selection.update(
            specimen_id="",
            volume_scope="full",
            part_id="",
            reslice_id="",
            label_role="",
            display_mode=self.workbench.display_mode or "slice",
        )
        self._apply_state_to_workbench()
        return result

    def on_tree_selection_changed(self, current, previous=None):
        workbench = self.workbench
        if current is None or workbench._loading_specimen:
            return
        if previous is not None and workbench.annotation_workflow_controller.has_unsaved_changes():
            if not workbench.annotation_workflow_controller.confirm_discard_or_save():
                workbench._loading_specimen = True
                try:
                    workbench.specimen_list.setCurrentItem(previous)
                finally:
                    workbench._loading_specimen = False
                return

        payload = workbench._tree_item_payload(current)
        previous_payload = workbench._tree_item_payload(previous) if previous is not None else {}
        target_key = self._payload_key(payload)
        previous_key = self._payload_key(previous_payload)
        preview_status_flushed = False
        if previous is not None and target_key != previous_key and not bool(getattr(workbench, "_programmatic_volume_tree_select", False)):
            workbench._defer_volume_preview_render_once = True
            if workbench.display_mode == "volume":
                message = tt("Preparing full-volume 3D preview...", workbench.lang)
                show_canvas_status = workbench.volume_render_controller._set_volume_canvas_status_text(message, replace_existing=True)
                workbench.volume_render_controller._update_volume_render_status_label(message)
                if show_canvas_status:
                    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
                    preview_status_flushed = True

        cursor_overridden = False
        if previous is not None and target_key != previous_key:
            cursor_overridden = workbench._show_volume_selection_loading_feedback(payload, flush_events=not preview_status_flushed)
        selection_completed = False
        try:
            self.select_payload(payload)
            selection_completed = True
        finally:
            if cursor_overridden:
                try:
                    QApplication.restoreOverrideCursor()
                except Exception:
                    pass
            if selection_completed and target_key != previous_key:
                workbench._finish_volume_selection_loading_feedback(payload)

    def select_payload(self, payload):
        payload = dict(payload or {})
        specimen_id = str(payload.get("specimen_id", "") or "")
        scope = str(payload.get("scope", "full") or "full")
        part_id = str(payload.get("part_id", "") or "")
        reslice_id = str(payload.get("reslice_id", "") or "")
        target_scope = "part" if scope in {"part", "part_reslices", "part_reslice"} else "full"
        target = {
            "specimen_id": specimen_id,
            "volume_scope": target_scope,
            "part_id": part_id if target_scope == "part" else "",
            "reslice_id": reslice_id if target_scope == "part" else "",
        }
        self._notify("on_selection_changing", dict(target))
        if target_scope == "part":
            result = self.selection.select_part(specimen_id, part_id, reslice_id=reslice_id)
            self.workbench.load_part(specimen_id, part_id, selected_reslice_id=reslice_id)
        else:
            result = self.selection.select_specimen(specimen_id, volume_scope="full")
            self.workbench.load_specimen(specimen_id)
        self.sync_state_from_workbench()
        snapshot = self.selection.state.to_dict()
        self._notify("on_selection_changed", snapshot)
        return result

    def _notify(self, hook, payload):
        shell = getattr(self.workbench, "workbench_shell", None)
        notify = getattr(shell, "notify_controllers", None)
        if callable(notify):
            return notify(hook, payload)
        return []

    def _apply_state_to_workbench(self):
        state = self.selection.state
        self.workbench.current_specimen_id = state.specimen_id
        self.workbench.current_volume_scope = state.volume_scope
        self.workbench.current_part_id = state.part_id
        self.workbench.current_reslice_id = state.reslice_id

    @staticmethod
    def _payload_key(payload):
        payload = payload or {}
        return (
            payload.get("scope", "full"),
            payload.get("specimen_id", ""),
            payload.get("part_id", ""),
            payload.get("reslice_id", ""),
        )
