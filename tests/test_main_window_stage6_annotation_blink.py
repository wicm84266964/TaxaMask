import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class FakeTrainingThread:
    def __init__(self):
        self.progress_signal = FakeSignal()
        self.result_signal = FakeSignal()
        self.error_signal = FakeSignal()
        self.cancelled_signal = FakeSignal()
        self.finished = FakeSignal()


class MainWindowStage6AnnotationBlinkTests(unittest.TestCase):
    def test_main_window_inherits_stage6_workflow_contracts(self):
        import AntSleap.main as main_module
        from AntSleap.ui.main_window_annotation import MainWindowAnnotationMixin
        from AntSleap.ui.main_window_blink_context import MainWindowBlinkContextMixin
        from AntSleap.ui.main_window_blink_workflow import MainWindowBlinkWorkflowMixin

        self.assertIs(main_module.MainWindow.on_polygon_completed, MainWindowAnnotationMixin.on_polygon_completed)
        self.assertIs(
            main_module.MainWindow.launch_blink_from_workbench,
            MainWindowBlinkContextMixin.launch_blink_from_workbench,
        )
        self.assertIs(
            main_module.MainWindow.run_blink_batch_auto_shrink,
            MainWindowBlinkWorkflowMixin.run_blink_batch_auto_shrink,
        )

    def test_stage6_modules_do_not_import_main_window(self):
        for filename in (
            "main_window_annotation.py",
            "main_window_blink_context.py",
            "main_window_blink_workflow.py",
        ):
            source = (ROOT / "AntSleap" / "ui" / filename).read_text(encoding="utf-8")
            self.assertNotIn("AntSleap.main", source)
            self.assertNotIn("from main import", source)

    def test_sam_result_keeps_prompt_image_part_and_description_context(self):
        from AntSleap.ui.main_window_annotation import MainWindowAnnotationMixin

        owner = type("AnnotationOwner", (MainWindowAnnotationMixin,), {})()
        owner.current_image = "first.png"
        owner.current_lang = "en"
        owner.sam_worker = type("Worker", (), {"model": object()})()
        owner.sam_busy = False
        owner.pending_sam_part = None
        owner.pending_sam_image = None
        owner.pending_sam_description = ""
        owner.pending_sam_project_context = {}
        owner._capture_project_task_context = lambda: {"project_path": "first-project"}
        owner._project_task_context_matches = lambda _context: True
        owner._log_stale_project_task_result = lambda *_args: None
        owner._current_part_name = lambda: "Mandible"
        owner.desc_box = type("Description", (), {"toPlainText": lambda self: "manual description"})()
        calls = []
        owner.on_polygon_completed = lambda *args, **kwargs: calls.append((args, kwargs))

        self.assertEqual(owner._begin_sam_prompt(), ("first.png", "Mandible"))
        owner.current_image = "second.png"
        owner.on_sam_mask_generated([[1, 1], [2, 1], [2, 2]], [1, 1, 2, 2])

        self.assertEqual(calls[0][0][0], "Mandible")
        self.assertEqual(calls[0][1]["image_path"], "first.png")
        self.assertEqual(calls[0][1]["description_text"], "manual description")
        self.assertFalse(owner.sam_busy)
        self.assertIsNone(owner.pending_sam_image)

    def test_stale_sam_result_does_not_write_into_new_project(self):
        from AntSleap.ui.main_window_annotation import MainWindowAnnotationMixin

        owner = type("AnnotationOwner", (MainWindowAnnotationMixin,), {})()
        owner.current_image = "first.png"
        owner.current_lang = "en"
        owner.sam_worker = type("Worker", (), {"model": object()})()
        owner.sam_busy = False
        owner.pending_sam_part = None
        owner.pending_sam_image = None
        owner.pending_sam_description = ""
        owner.pending_sam_project_context = {}
        owner._current_part_name = lambda: "Mandible"
        owner.desc_box = type("Description", (), {"toPlainText": lambda self: "manual description"})()
        owner._capture_project_task_context = lambda: {"project_path": "old-project"}
        owner._project_task_context_matches = lambda _context: False
        stale_events = []
        owner._log_stale_project_task_result = lambda workflow, _context: stale_events.append(workflow)
        writes = []
        owner.on_polygon_completed = lambda *args, **kwargs: writes.append((args, kwargs))

        owner._begin_sam_prompt()
        owner.on_sam_mask_generated([[1, 1], [2, 1], [2, 2]], [1, 1, 2, 2])

        self.assertEqual(writes, [])
        self.assertEqual(stale_events, ["sam_mask_result"])
        self.assertFalse(owner.sam_busy)
        self.assertEqual(owner.pending_sam_project_context, {})

    def test_child_training_signals_connect_once(self):
        from AntSleap.ui.main_window_blink_workflow import MainWindowBlinkWorkflowMixin

        thread = FakeTrainingThread()
        owner = type("BlinkOwner", (MainWindowBlinkWorkflowMixin,), {})()
        owner.blink_lab = type("BlinkLab", (), {"training_thread": thread})()
        owner._set_training_progress = lambda *args: None
        owner._on_child_training_result = lambda *args: None
        owner._on_child_training_error = lambda *args: None
        owner._on_child_training_cancelled = lambda *args: None
        owner._on_child_training_finished = lambda *args: None

        owner._connect_child_training_progress()
        owner._connect_child_training_progress()

        self.assertEqual(len(thread.progress_signal.callbacks), 1)
        self.assertEqual(len(thread.result_signal.callbacks), 1)
        self.assertEqual(len(thread.error_signal.callbacks), 1)
        self.assertEqual(len(thread.cancelled_signal.callbacks), 1)
        self.assertEqual(len(thread.finished.callbacks), 1)


if __name__ == "__main__":
    unittest.main()
