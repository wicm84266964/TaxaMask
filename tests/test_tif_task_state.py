import unittest

from AntSleap.core.tif_task_context import TifTaskContext
from AntSleap.core.tif_task_state import TASK_CANCELLED, TASK_FAILED, TASK_RUNNING, TASK_SUCCEEDED, TifTaskState


class TifTaskStateTests(unittest.TestCase):
    def test_task_lifecycle_records_timestamps_and_payload(self):
        task = TifTaskState("label_manual_save:1", "label_manual_save", context=TifTaskContext(specimen_id="s1"))

        task.start("Saving labels")
        self.assertEqual(task.status, TASK_RUNNING)
        self.assertTrue(task.started_at)

        task.progress(2, 5, "slice 2")
        self.assertEqual(task.progress_current, 2)
        self.assertEqual(task.message, "slice 2")

        task.finish(payload={"saved": True})
        self.assertEqual(task.status, TASK_SUCCEEDED)
        self.assertTrue(task.finished_at)
        self.assertTrue(task.to_dict()["payload"]["saved"])

    def test_task_failure_and_cancel_are_terminal(self):
        failed = TifTaskState("backend_action:1", "backend_action").start().fail("boom")
        cancelled = TifTaskState("preview:1", "volume_preview").start().cancel("user switched specimen")

        self.assertEqual(failed.status, TASK_FAILED)
        self.assertEqual(cancelled.status, TASK_CANCELLED)
        self.assertTrue(failed.terminal)
        self.assertTrue(cancelled.terminal)


if __name__ == "__main__":
    unittest.main()
