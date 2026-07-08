import unittest

from AntSleap.core.tif_task_context import TifTaskContext
from AntSleap.services.tif_task_manager import TifTaskManager


class TifTaskManagerTests(unittest.TestCase):
    def test_busy_lock_tracks_write_tasks(self):
        manager = TifTaskManager()

        preview = manager.start_task("volume_preview", context=TifTaskContext(specimen_id="s1"))
        self.assertTrue(manager.busy_locked())
        self.assertEqual(manager.busy_lock_reason(), "volume_preview")
        manager.finish_task(preview.task_id)
        self.assertFalse(manager.busy_locked())

        save = manager.start_task("label_manual_save", context=TifTaskContext(specimen_id="s1"), message="Saving")
        self.assertTrue(manager.busy_locked())
        self.assertEqual(manager.busy_lock_reason(), "Saving")

        manager.finish_task(save.task_id)
        self.assertFalse(manager.busy_locked())

    def test_context_matching_blocks_stale_results(self):
        manager = TifTaskManager()
        task = manager.start_task("volume_preview", context=TifTaskContext(specimen_id="s1", part_id="head", request_key="preview-a"))

        self.assertTrue(manager.context_matches(task.task_id, {"specimen_id": "s1", "part_id": "head", "request_key": "preview-a"}))
        self.assertFalse(manager.context_matches(task.task_id, {"specimen_id": "s1", "part_id": "thorax", "request_key": "preview-a"}))

    def test_summary_is_agent_readable(self):
        manager = TifTaskManager()
        manager.start_task("backend_action", action="train", context=TifTaskContext(specimen_id="s1"))

        summary = manager.summary()

        self.assertTrue(summary["busy_locked"])
        self.assertEqual(summary["running_count"], 1)
        self.assertEqual(summary["running"][0]["action"], "train")

    def test_terminal_task_status_is_not_overwritten_by_late_signals(self):
        manager = TifTaskManager()
        task = manager.start_task("backend_action", context=TifTaskContext(specimen_id="s1"))

        manager.cancel_task(task.task_id, "user_cancelled")
        manager.fail_task(task.task_id, "late_worker_failure")

        self.assertEqual(manager.task(task.task_id).status, "cancelled")
        self.assertEqual(manager.task(task.task_id).error, "user_cancelled")


if __name__ == "__main__":
    unittest.main()
