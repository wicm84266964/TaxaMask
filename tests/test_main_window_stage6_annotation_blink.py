import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox


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

    def isRunning(self):
        return True


class FakePreflightWorker:
    def __init__(self):
        self.prepared_signal = FakeSignal()
        self.error_signal = FakeSignal()
        self.cancelled_signal = FakeSignal()

    def isRunning(self):
        return True


class FakeButton:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, value):
        self.enabled = bool(value)


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
        owner._apply_sam_generated_polygon = lambda *args, **kwargs: calls.append((args, kwargs))

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
        owner._apply_sam_generated_polygon = lambda *args, **kwargs: writes.append((args, kwargs))

        owner._begin_sam_prompt()
        owner.on_sam_mask_generated([[1, 1], [2, 1], [2, 2]], [1, 1, 2, 2])

        self.assertEqual(writes, [])
        self.assertEqual(stale_events, ["sam_mask_result"])
        self.assertFalse(owner.sam_busy)
        self.assertEqual(owner.pending_sam_project_context, {})

    def _make_sam_owner(self, image_path="first.png", part="Head"):
        from AntSleap.core.project import ProjectManager
        from AntSleap.ui.main_window_annotation import MainWindowAnnotationMixin

        owner = type("AnnotationOwner", (MainWindowAnnotationMixin,), {})()
        owner.project = ProjectManager()
        stored = owner.project._image_data_key(image_path)
        owner.project.project_data["images"] = [stored]
        owner.project.project_data["labels"] = {stored: owner.project._default_label_entry()}
        owner.current_image = stored
        owner.current_lang = "en"
        owner.sam_worker = type("Worker", (), {"model": object()})()
        owner.sam_busy = False
        owner.pending_sam_part = None
        owner.pending_sam_image = None
        owner.pending_sam_description = ""
        owner.pending_sam_project_context = {}
        owner._capture_project_task_context = lambda: {"project_path": "sam-project"}
        owner._project_task_context_matches = lambda _context: True
        owner._log_stale_project_task_result = lambda *_args: None
        owner._current_part_name = lambda: part
        owner.desc_box = type("Description", (), {"toPlainText": lambda self: ""})()
        owner.canvas = type(
            "Canvas",
            (),
            {"set_polygons": lambda self, *_args, **_kwargs: None, "save_state": lambda self: None},
        )()
        owner.check_morpho = type("Check", (), {"isChecked": lambda self: False})()
        owner.logs = []
        owner.log = lambda message: owner.logs.append(str(message))
        owner._schedule_project_save = lambda: None
        owner._refresh_current_canvas_boxes = lambda: None
        owner._refresh_current_image_list_status = lambda *_args, **_kwargs: None
        owner._refresh_blink_refine_state = lambda: None
        owner._same_project_image_path = lambda left, right: left == right
        return owner, stored

    def test_sam_result_saves_model_prediction_draft_not_manual_confirmed(self):
        from AntSleap.core.training_truth import (
            TRAINING_REVIEW_DRAFT,
            TRAINING_SOURCE_MODEL,
            get_part_training_truth,
            resolve_part_training_trust,
        )

        owner, image_path = self._make_sam_owner()
        owner._begin_sam_prompt()
        owner.on_sam_mask_generated([[5, 5], [25, 5], [15, 20]], [4, 4, 26, 21])

        entry = owner.project.project_data["labels"][image_path]
        truth = get_part_training_truth(entry, "Head")
        decision = resolve_part_training_trust(entry, "Head")
        self.assertEqual(truth["source"], TRAINING_SOURCE_MODEL)
        self.assertEqual(truth["review_status"], TRAINING_REVIEW_DRAFT)
        self.assertFalse(decision["eligible"])
        self.assertEqual(decision["state"], "draft")
        self.assertEqual(entry["auto_boxes"]["Head"], [4.0, 4.0, 26.0, 21.0])
        self.assertNotIn("Head", entry.get("boxes", {}))
        self.assertTrue(any("review-pending SAM outline" in item for item in owner.logs))

    def test_empty_sam_result_keeps_existing_confirmed_outline(self):
        owner, image_path = self._make_sam_owner()
        original = [[5.0, 5.0], [30.0, 5.0], [15.0, 25.0]]
        owner.project.update_label(image_path, "Head", original, save=False)
        owner._begin_sam_prompt()
        owner.on_sam_mask_generated([], [4, 4, 26, 21])

        self.assertEqual(owner.project.project_data["labels"][image_path]["parts"]["Head"], original)
        self.assertTrue(any("Existing labels were kept" in item for item in owner.logs))

    def test_sam_overwrite_of_confirmed_outline_can_be_cancelled(self):
        owner, image_path = self._make_sam_owner()
        original = [[5.0, 5.0], [30.0, 5.0], [15.0, 25.0]]
        owner.project.update_label(image_path, "Head", original, save=False)
        owner._begin_sam_prompt()
        with patch(
            "AntSleap.ui.main_window_annotation.themed_yes_no_question",
            return_value=QMessageBox.No,
        ):
            owner.on_sam_mask_generated([[1, 1], [8, 1], [4, 7]], [1, 1, 8, 7])

        self.assertEqual(owner.project.project_data["labels"][image_path]["parts"]["Head"], original)
        truth = owner.project.project_data["labels"][image_path]
        from AntSleap.core.training_truth import get_part_training_truth

        self.assertEqual(get_part_training_truth(truth, "Head")["review_status"], "confirmed")

    def test_sam_overwrite_of_confirmed_outline_saves_draft_when_accepted(self):
        from AntSleap.core.training_truth import (
            TRAINING_REVIEW_DRAFT,
            TRAINING_SOURCE_MODEL,
            get_part_training_truth,
        )

        owner, image_path = self._make_sam_owner()
        original = [[5.0, 5.0], [30.0, 5.0], [15.0, 25.0]]
        owner.project.update_label(image_path, "Head", original, save=False)
        owner._begin_sam_prompt()
        new_poly = [[1.0, 1.0], [8.0, 1.0], [4.0, 7.0]]
        with patch(
            "AntSleap.ui.main_window_annotation.themed_yes_no_question",
            return_value=QMessageBox.Yes,
        ):
            owner.on_sam_mask_generated(new_poly, [1, 1, 8, 7])

        entry = owner.project.project_data["labels"][image_path]
        self.assertEqual(entry["parts"]["Head"], new_poly)
        truth = get_part_training_truth(entry, "Head")
        self.assertEqual(truth["source"], TRAINING_SOURCE_MODEL)
        self.assertEqual(truth["review_status"], TRAINING_REVIEW_DRAFT)

    def test_undo_restores_trust_and_does_not_confirm_neighbor_draft(self):
        from AntSleap.core.training_truth import (
            TRAINING_REVIEW_CONFIRMED,
            TRAINING_REVIEW_DRAFT,
            TRAINING_SOURCE_MODEL,
            get_part_training_truth,
        )

        owner, image_path = self._make_sam_owner()
        head = [[5.0, 5.0], [30.0, 5.0], [15.0, 25.0]]
        eye = [[2.0, 2.0], [9.0, 2.0], [5.0, 8.0]]
        owner.project.update_label(image_path, "Head", head, save=False)
        owner.project.update_label(
            image_path,
            "Eye",
            eye,
            save=False,
            training_source=TRAINING_SOURCE_MODEL,
            training_review_status=TRAINING_REVIEW_DRAFT,
            training_accepted_via="",
        )
        owner.canvas.polygons = {"Head": head, "Eye": eye}
        owner._on_annotation_history_checkpoint()
        owner.project.update_label(
            image_path,
            "Head",
            [[1.0, 1.0], [6.0, 1.0], [3.0, 5.0]],
            save=False,
        )
        owner.canvas.polygons = {"Head": [[1.0, 1.0], [6.0, 1.0], [3.0, 5.0]], "Eye": eye}
        owner._on_annotation_polygons_restored({"Head": head, "Eye": eye}, dict(owner.canvas.polygons), "undo")
        entry = owner.project.project_data["labels"][image_path]
        self.assertEqual(entry["parts"]["Head"], head)
        self.assertEqual(get_part_training_truth(entry, "Head")["review_status"], TRAINING_REVIEW_CONFIRMED)
        self.assertEqual(get_part_training_truth(entry, "Eye")["source"], TRAINING_SOURCE_MODEL)
        self.assertEqual(get_part_training_truth(entry, "Eye")["review_status"], TRAINING_REVIEW_DRAFT)

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

    def test_child_progress_does_not_duplicate_shell_training_state_connection(self):
        from AntSleap.ui.main_window_blink_workflow import MainWindowBlinkWorkflowMixin

        state_signal = FakeSignal()
        preflight = FakePreflightWorker()
        owner = type("BlinkOwner", (MainWindowBlinkWorkflowMixin,), {})()
        owner.blink_lab = type(
            "BlinkLab",
            (),
            {
                "training_thread": None,
                "training_preflight_thread": preflight,
                "training_state_changed": state_signal,
            },
        )()
        state_events = []
        owner._on_child_training_state_changed = state_events.append
        state_signal.connect(owner._on_child_training_state_changed)

        owner._connect_child_training_progress(prefer_preflight=True)

        self.assertEqual(len(state_signal.callbacks), 1)
        state_signal.callbacks[0]("preflight_started")
        self.assertEqual(state_events, ["preflight_started"])

    def test_child_preflight_counts_as_busy_and_handoffs_to_training_thread(self):
        from AntSleap.ui.main_window_blink_workflow import MainWindowBlinkWorkflowMixin

        preflight = FakePreflightWorker()
        formal_thread = FakeTrainingThread()
        owner = type("BlinkOwner", (MainWindowBlinkWorkflowMixin,), {})()
        owner.blink_lab = type(
            "BlinkLab",
            (),
            {"training_thread": None, "training_preflight_thread": preflight},
        )()
        owner.btn_blink_stop_training = FakeButton()
        owner._set_training_progress = lambda *args: None
        owner._refresh_blink_refine_state = lambda: None
        owner._on_child_training_result = lambda *args: None
        owner._on_child_training_error = lambda *args: None
        owner._on_child_training_cancelled = lambda *args: None
        owner._on_child_training_finished = lambda *args: None

        self.assertTrue(owner._is_child_training_running())
        owner._connect_child_training_progress()
        self.assertEqual(len(preflight.prepared_signal.callbacks), 1)

        owner.blink_lab.training_thread = formal_thread
        preflight.prepared_signal.callbacks[0](object())

        self.assertEqual(len(formal_thread.progress_signal.callbacks), 1)
        self.assertEqual(len(formal_thread.finished.callbacks), 1)
        self.assertTrue(owner.btn_blink_stop_training.enabled)

    def test_child_preflight_error_restores_outer_controls(self):
        from AntSleap.ui.main_window_blink_workflow import MainWindowBlinkWorkflowMixin

        preflight = FakePreflightWorker()
        owner = type("BlinkOwner", (MainWindowBlinkWorkflowMixin,), {})()
        owner.blink_lab = type(
            "BlinkLab",
            (),
            {"training_thread": None, "training_preflight_thread": preflight},
        )()
        owner.btn_train = FakeButton()
        owner.btn_blink_stop_training = FakeButton()
        owner.current_lang = "en"
        owner.child_training_failed = False
        owner.child_training_cancel_requested = False
        owner.progress = type("Progress", (), {"value": lambda self: 20})()
        owner._set_training_progress = lambda *args: None
        owner._refresh_blink_refine_state = lambda: None

        owner._connect_child_training_progress()
        preflight.error_signal.callbacks[0](RuntimeError("failed"))

        self.assertTrue(owner.btn_train.enabled)
        self.assertFalse(owner.btn_blink_stop_training.enabled)
        self.assertTrue(owner.child_training_failed)

    def test_child_retry_state_keeps_outer_controls_busy(self):
        from AntSleap.ui.main_window_blink_workflow import MainWindowBlinkWorkflowMixin

        owner = type("BlinkOwner", (MainWindowBlinkWorkflowMixin,), {})()
        owner.blink_lab = type(
            "BlinkLab",
            (),
            {"training_thread": None, "training_preflight_thread": None},
        )()
        owner.btn_train = FakeButton()
        owner.btn_blink_stop_training = FakeButton()
        owner._refresh_blink_refine_state = lambda: None

        owner._on_child_training_state_changed("retry_queued")

        self.assertFalse(owner.btn_train.enabled)
        self.assertTrue(owner.btn_blink_stop_training.enabled)


if __name__ == "__main__":
    unittest.main()
