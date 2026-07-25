"""Background worker shared by the built-in 2D and Blink training gates."""

from __future__ import annotations

import time

from PySide6.QtCore import QThread, Signal


def format_byte_rate(bytes_per_second):
    try:
        value = max(0.0, float(bytes_per_second or 0.0))
    except (TypeError, ValueError):
        value = 0.0
    units = ("B/s", "KB/s", "MB/s", "GB/s", "TB/s")
    index = 0
    while value >= 1024.0 and index < len(units) - 1:
        value /= 1024.0
        index += 1
    precision = 0 if index == 0 else 1
    return f"{value:.{precision}f} {units[index]}"


def format_eta(seconds):
    try:
        remaining = max(0, int(round(float(seconds or 0.0))))
    except (TypeError, ValueError):
        remaining = 0
    hours, remainder = divmod(remaining, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class TrainingPreflightWorker(QThread):
    """Run a training preparation callable without blocking the GUI thread."""

    progress_signal = Signal(dict)
    prepared_signal = Signal(object)
    error_signal = Signal(object)
    cancelled_signal = Signal()

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        if not callable(operation):
            raise TypeError("training_preflight_operation_not_callable")
        self._operation = operation
        self._started_at = 0.0

    def cancel(self):
        self.requestInterruption()

    def _cancel_requested(self):
        return bool(self.isInterruptionRequested())

    def _report_detail(self, detail):
        payload = dict(detail or {})
        now = time.monotonic()
        elapsed = max(0.0, now - self._started_at)
        completed = max(0, int(payload.get("total_bytes_done") or 0))
        total = max(0, int(payload.get("total_bytes") or 0))
        rate = completed / elapsed if elapsed > 0.0 else 0.0
        if total > 0:
            percent = int(min(99.0, (completed * 100.0) / total))
            eta = (total - completed) / rate if rate > 0.0 else None
        else:
            file_index = max(0, int(payload.get("file_index") or 0) - 1)
            file_count = max(0, int(payload.get("file_count") or 0))
            percent = int(min(99.0, (file_index * 100.0) / file_count)) if file_count else 0
            eta = None
        payload.update(
            {
                "elapsed_seconds": elapsed,
                "bytes_per_second": rate,
                "eta_seconds": eta,
                "percent": max(0, percent),
            }
        )
        self.progress_signal.emit(payload)

    def run(self):
        self._started_at = time.monotonic()
        try:
            prepared = self._operation(
                self._report_detail,
                self._cancel_requested,
            )
        except Exception as exc:
            code = str(getattr(exc, "code", "") or "")
            if code == "user_cancelled" or "integrity_check_cancelled" in str(exc):
                self.cancelled_signal.emit()
            else:
                self.error_signal.emit(exc)
            return
        if self._cancel_requested():
            run = getattr(prepared, "run", None)
            try:
                if run is not None and getattr(run, "status", None) in {
                    "pending",
                    "running",
                }:
                    run.cancel(stage="integrity_preflight")
            except Exception as exc:
                self.error_signal.emit(exc)
                return
            self.cancelled_signal.emit()
            return
        self.prepared_signal.emit(prepared)


__all__ = [
    "TrainingPreflightWorker",
    "format_byte_rate",
    "format_eta",
]
