try:
    from AntSleap.core.tif_task_context import TifTaskContext
    from AntSleap.services.tif_task_manager import TifTaskManager
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_task_context import TifTaskContext
    from services.tif_task_manager import TifTaskManager


class TifQtTaskAdapter:
    def __init__(self, manager=None):
        self.manager = manager or TifTaskManager()

    def context_from_widget(self, widget, *, request_key="", label_role=""):
        role = label_role
        combo = getattr(widget, "label_role_combo", None)
        if not role and combo is not None and hasattr(combo, "currentData"):
            role = combo.currentData() or ""
        return TifTaskContext(
            specimen_id=str(getattr(widget, "current_specimen_id", "") or ""),
            volume_scope=str(getattr(widget, "current_volume_scope", "") or ""),
            part_id=str(getattr(widget, "current_part_id", "") or ""),
            reslice_id=str(getattr(widget, "current_reslice_id", "") or ""),
            label_role=str(role or ""),
            display_mode=str(getattr(widget, "display_mode", "") or ""),
            request_key=str(request_key or ""),
        )

    def start_from_widget(self, widget, task_type, *, action="", payload=None, request_key="", label_role="", message=""):
        return self.manager.start_task(
            task_type,
            context=self.context_from_widget(widget, request_key=request_key, label_role=label_role),
            action=action,
            payload=payload,
            message=message,
        )

    def current_context_matches(self, widget, task_id, *, fields=None, request_key="", label_role="", ignore_empty=False):
        context = self.context_from_widget(widget, request_key=request_key, label_role=label_role)
        return self.manager.context_matches(task_id, context, fields=fields, ignore_empty=ignore_empty)
