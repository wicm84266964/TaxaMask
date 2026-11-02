"""Serialize GUI and agent model jobs for the same instance project."""
from pathlib import Path

from .safe_io import AdvisoryFileLock


def run_model_job(project_root, callback):
    root = Path(project_root).resolve()
    lock = AdvisoryFileLock(root / ".instance-model.lock", trusted_root=root, timeout=0.1)
    try:
        if not lock.acquire():
            raise TimeoutError("instance_model_busy")
    except TimeoutError as exc:
        raise RuntimeError("当前项目已有模型任务运行，请等待结束或取消后再试") from exc
    try:
        return callback()
    finally:
        lock.release()
