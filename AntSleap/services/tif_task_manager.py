from collections import OrderedDict

from AntSleap.core.tif_task_context import TifTaskContext
from AntSleap.core.tif_task_state import TASK_RUNNING, TifTaskState


DEFAULT_BUSY_LOCK_TASK_TYPES = {
    "tif_import",
    "amira_import",
    "tif_materialize",
    "label_auto_save",
    "label_manual_save",
    "truth_promotion",
    "confirm_part_roi",
    "mask_preview",
    "volume_preview",
    "backend_action",
    "local_axis_export",
}


class TifTaskManager:
    def __init__(self, busy_lock_task_types=None):
        self.busy_lock_task_types = set(busy_lock_task_types or DEFAULT_BUSY_LOCK_TASK_TYPES)
        self._tasks = OrderedDict()
        self._counter = 0

    def _next_task_id(self, task_type):
        self._counter += 1
        return f"{task_type}:{self._counter}"

    def start_task(self, task_type, *, context=None, action="", payload=None, task_id="", message=""):
        clean_type = str(task_type or "task")
        clean_id = str(task_id or self._next_task_id(clean_type))
        task = TifTaskState(
            task_id=clean_id,
            task_type=clean_type,
            context=context if isinstance(context, TifTaskContext) else TifTaskContext.from_mapping(context),
            action=str(action or ""),
            payload=dict(payload or {}),
        ).start(message=message)
        self._tasks[clean_id] = task
        return task

    def task(self, task_id):
        return self._tasks.get(str(task_id or ""))

    def running_tasks(self, task_type=None):
        clean_type = str(task_type or "")
        return [
            task
            for task in self._tasks.values()
            if task.status == TASK_RUNNING and (not clean_type or task.task_type == clean_type)
        ]

    def is_running(self, task_type=None):
        return bool(self.running_tasks(task_type=task_type))

    def finish_task(self, task_id, *, payload=None, message=""):
        task = self.task(task_id)
        if task is None:
            return None
        if task.terminal:
            return task
        return task.finish(payload=payload, message=message)

    def fail_task(self, task_id, error="", *, payload=None, message=""):
        task = self.task(task_id)
        if task is None:
            return None
        if task.terminal:
            return task
        return task.fail(error, payload=payload, message=message)

    def progress_task(self, task_id, current=0, total=0, message=""):
        task = self.task(task_id)
        if task is None:
            return None
        if task.terminal:
            return task
        return task.progress(current=current, total=total, message=message)

    def cancel_task(self, task_id, reason=""):
        task = self.task(task_id)
        if task is None:
            return None
        if task.terminal:
            return task
        return task.cancel(reason)

    def cancel_running(self, task_type=None, reason="cancelled"):
        cancelled = []
        for task in self.running_tasks(task_type=task_type):
            cancelled.append(task.cancel(reason))
        return cancelled

    def active_busy_locks(self):
        return [
            task
            for task in self.running_tasks()
            if task.task_type in self.busy_lock_task_types
        ]

    def busy_locked(self):
        return bool(self.active_busy_locks())

    def busy_lock_reason(self):
        locks = self.active_busy_locks()
        if not locks:
            return ""
        task = locks[0]
        return task.message or task.action or task.task_type

    def context_matches(self, task_id, current_context, *, fields=None, ignore_empty=True):
        task = self.task(task_id)
        if task is None:
            return False
        return task.context.matches(current_context, fields=fields, ignore_empty=ignore_empty)

    def summary(self):
        running = self.running_tasks()
        return {
            "running_count": len(running),
            "busy_locked": self.busy_locked(),
            "busy_lock_types": [task.task_type for task in self.active_busy_locks()],
            "running": [task.to_dict() for task in running],
            "latest": [task.to_dict() for task in list(self._tasks.values())[-10:]],
        }
