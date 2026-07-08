from dataclasses import dataclass, field
from datetime import datetime

from .tif_task_context import TifTaskContext


TASK_PENDING = "pending"
TASK_RUNNING = "running"
TASK_SUCCEEDED = "succeeded"
TASK_FAILED = "failed"
TASK_CANCELLED = "cancelled"
TASK_TERMINAL_STATUSES = {TASK_SUCCEEDED, TASK_FAILED, TASK_CANCELLED}


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class TifTaskState:
    task_id: str
    task_type: str
    status: str = TASK_PENDING
    context: TifTaskContext = field(default_factory=TifTaskContext)
    action: str = ""
    payload: dict = field(default_factory=dict)
    error: str = ""
    started_at: str = ""
    finished_at: str = ""
    progress_current: int = 0
    progress_total: int = 0
    message: str = ""

    @property
    def running(self):
        return self.status == TASK_RUNNING

    @property
    def terminal(self):
        return self.status in TASK_TERMINAL_STATUSES

    def start(self, message=""):
        self.status = TASK_RUNNING
        self.started_at = self.started_at or _now_iso()
        self.finished_at = ""
        if message:
            self.message = str(message)
        return self

    def progress(self, current=0, total=0, message=""):
        self.progress_current = int(current or 0)
        self.progress_total = int(total or 0)
        if message:
            self.message = str(message)
        return self

    def finish(self, *, payload=None, message=""):
        self.status = TASK_SUCCEEDED
        self.payload = dict(payload or {})
        self.finished_at = _now_iso()
        if message:
            self.message = str(message)
        return self

    def fail(self, error="", *, payload=None, message=""):
        self.status = TASK_FAILED
        self.error = str(error or "")
        self.payload = dict(payload or {})
        self.finished_at = _now_iso()
        if message:
            self.message = str(message)
        return self

    def cancel(self, reason=""):
        self.status = TASK_CANCELLED
        self.error = str(reason or "")
        self.finished_at = _now_iso()
        if reason:
            self.message = str(reason)
        return self

    def to_dict(self):
        return {
            "task_id": str(self.task_id or ""),
            "task_type": str(self.task_type or ""),
            "status": str(self.status or ""),
            "context": self.context.to_dict() if isinstance(self.context, TifTaskContext) else {},
            "action": str(self.action or ""),
            "payload": dict(self.payload or {}),
            "error": str(self.error or ""),
            "started_at": str(self.started_at or ""),
            "finished_at": str(self.finished_at or ""),
            "progress_current": int(self.progress_current or 0),
            "progress_total": int(self.progress_total or 0),
            "message": str(self.message or ""),
        }
