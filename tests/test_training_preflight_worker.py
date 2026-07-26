import threading
import unittest
from types import SimpleNamespace


try:
    from PySide6.QtCore import QCoreApplication

    from AntSleap.ui.training_preflight_worker import (
        TrainingPreflightWorker,
        format_byte_rate,
        format_eta,
    )
except ImportError:
    QCoreApplication = None


@unittest.skipUnless(QCoreApplication is not None, "PySide6 is required")
class TrainingPreflightWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_formats_rate_and_eta(self):
        self.assertEqual(format_byte_rate(1536), "1.5 KB/s")
        self.assertEqual(format_eta(65), "01:05")
        self.assertEqual(format_eta(3661), "1:01:01")

    def test_worker_reports_progress_and_result(self):
        progress = []
        prepared = []

        def operation(detail_callback, cancel_check):
            self.assertFalse(cancel_check())
            detail_callback(
                {
                    "file_index": 2,
                    "file_count": 4,
                    "display_name": "ant_002.png",
                    "total_bytes_done": 50,
                    "total_bytes": 100,
                }
            )
            return {"status": "ready"}

        worker = TrainingPreflightWorker(operation)
        worker.progress_signal.connect(progress.append)
        worker.prepared_signal.connect(prepared.append)
        worker.start()
        self.assertTrue(worker.wait(5000))
        self.app.processEvents()

        self.assertEqual(prepared, [{"status": "ready"}])
        self.assertEqual(progress[0]["percent"], 50)
        self.assertEqual(progress[0]["display_name"], "ant_002.png")
        self.assertGreaterEqual(progress[0]["bytes_per_second"], 0.0)

    def test_user_cancelled_error_uses_cancel_signal(self):
        cancelled = []
        errors = []

        class CancelledError(RuntimeError):
            code = "user_cancelled"

        def operation(_detail_callback, _cancel_check):
            raise CancelledError("cancelled")

        worker = TrainingPreflightWorker(operation)
        worker.cancelled_signal.connect(lambda: cancelled.append(True))
        worker.error_signal.connect(errors.append)
        worker.start()
        self.assertTrue(worker.wait(5000))
        self.app.processEvents()

        self.assertEqual(cancelled, [True])
        self.assertEqual(errors, [])

    def test_cancel_at_completion_closes_run_instead_of_starting_training(self):
        started = threading.Event()
        release = threading.Event()
        prepared = []
        cancelled = []

        class FakeRun:
            status = "running"

            def __init__(self):
                self.cancel_stage = ""

            def cancel(self, *, stage):
                self.cancel_stage = stage
                self.status = "cancelled"

        run = FakeRun()

        def operation(_detail_callback, _cancel_check):
            started.set()
            release.wait(5)
            return SimpleNamespace(run=run)

        worker = TrainingPreflightWorker(operation)
        worker.prepared_signal.connect(prepared.append)
        worker.cancelled_signal.connect(lambda: cancelled.append(True))
        worker.start()
        self.assertTrue(started.wait(5))
        worker.cancel()
        release.set()
        self.assertTrue(worker.wait(5000))
        self.app.processEvents()

        self.assertEqual(prepared, [])
        self.assertEqual(cancelled, [True])
        self.assertEqual(run.status, "cancelled")
        self.assertEqual(run.cancel_stage, "integrity_preflight")


if __name__ == "__main__":
    unittest.main()
