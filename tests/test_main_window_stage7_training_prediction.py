import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FakeProject:
    def __init__(self, path):
        self.current_project_path = path
        self.profile_updates = []

    def update_active_model_profile_parent_weights(self, **kwargs):
        self.profile_updates.append(kwargs)


class FakeRunningThread:
    def isRunning(self):
        return True


class MainWindowStage7TrainingPredictionTests(unittest.TestCase):
    def test_main_window_inherits_stage7_workflow_contracts(self):
        import AntSleap.main as main_module
        from AntSleap.ui.main_window_export import MainWindowExportMixin
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin
        from AntSleap.ui.main_window_prediction import MainWindowPredictionMixin
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin
        from AntSleap.ui.main_window_vlm import MainWindowVlmMixin

        self.assertIs(main_module.MainWindow.refresh_model_list, MainWindowModelManagementMixin.refresh_model_list)
        self.assertIs(main_module.MainWindow.run_training, MainWindowTrainingMixin.run_training)
        self.assertIs(main_module.MainWindow.run_prediction, MainWindowPredictionMixin.run_prediction)
        self.assertIs(
            main_module.MainWindow.run_vlm_preannotation_from_settings,
            MainWindowVlmMixin.run_vlm_preannotation_from_settings,
        )
        self.assertIs(main_module.MainWindow.export_dataset, MainWindowExportMixin.export_dataset)

    def test_stage7_modules_do_not_import_main_window(self):
        for filename in (
            "main_window_model_management.py",
            "main_window_training.py",
            "main_window_prediction.py",
            "main_window_vlm.py",
            "main_window_export.py",
        ):
            source = (ROOT / "AntSleap" / "ui" / filename).read_text(encoding="utf-8")
            self.assertNotIn("AntSleap.main", source)
            self.assertNotIn("from main import", source)

    def test_project_task_context_requires_same_manager_and_path(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin

        owner = type("ContextOwner", (MainWindowModelManagementMixin,), {})()
        first_project = FakeProject(str(ROOT / "first.sqlite_manifest.json"))
        owner.project = first_project
        context = owner._capture_project_task_context()

        self.assertTrue(owner._project_task_context_matches(context))
        first_project.current_project_path = str(ROOT / "second.sqlite_manifest.json")
        self.assertFalse(owner._project_task_context_matches(context))
        owner.project = FakeProject(str(ROOT / "first.sqlite_manifest.json"))
        self.assertFalse(owner._project_task_context_matches(context))

    def test_stale_training_success_does_not_update_new_project_profile(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        owner = type("TrainingOwner", (MainWindowModelManagementMixin, MainWindowTrainingMixin), {})()
        old_project = FakeProject(str(ROOT / "old.sqlite_manifest.json"))
        owner.project = old_project
        owner.parent_training_project_context = owner._capture_project_task_context()
        new_project = FakeProject(str(ROOT / "new.sqlite_manifest.json"))
        owner.project = new_project
        owner.stale_events = []
        owner._log_stale_project_task_result = lambda workflow, context: owner.stale_events.append(workflow)
        owner.trainer = type(
            "Trainer",
            (),
            {"training_context": {"locator_weights": "locator.pth", "segmenter_weights": "segmenter.pth"}},
        )()

        owner._on_training_success()

        self.assertEqual(new_project.profile_updates, [])
        self.assertEqual(owner.stale_events, ["parent_training_success"])

    def test_stale_vlm_worker_run_is_ignored(self):
        from AntSleap.ui.main_window_vlm import MainWindowVlmMixin

        owner = type("VlmOwner", (MainWindowVlmMixin,), {})()
        owner.vlm_preannotation_run_id = "current-run"
        owner.vlm_preannotation_records = []
        worker = type("Worker", (), {"run_id": "old-run"})()

        owner._on_vlm_preannotation_image_result({"image_path": "specimen.png"}, worker=worker)

        self.assertEqual(owner.vlm_preannotation_records, [])

    def test_stale_project_vlm_result_is_cancelled_without_project_write(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin
        from AntSleap.ui.main_window_vlm import MainWindowVlmMixin

        owner = type("VlmContextOwner", (MainWindowModelManagementMixin, MainWindowVlmMixin), {})()
        old_project = FakeProject(str(ROOT / "old.sqlite_manifest.json"))
        owner.project = old_project
        owner.vlm_preannotation_project_context = owner._capture_project_task_context()
        owner.project = FakeProject(str(ROOT / "new.sqlite_manifest.json"))
        owner.vlm_preannotation_run_id = "run-1"
        owner.vlm_preannotation_records = []
        owner.vlm_preannotation_queue = ["queued.png"]
        owner.completed = []
        owner._log_stale_project_task_result = lambda workflow, context: owner.completed.append(workflow)
        owner._complete_current_vlm_image_steps = lambda step, image_path=None: owner.completed.append(step)
        owner._mark_current_vlm_image_done = lambda step, image_path=None: owner.completed.append(step)
        worker = type("Worker", (), {"run_id": "run-1"})()

        owner._on_vlm_preannotation_image_result({"image_path": "old.png"}, worker=worker)

        self.assertTrue(owner.vlm_preannotation_cancel_requested)
        self.assertEqual(owner.vlm_preannotation_queue, [])
        self.assertEqual(owner.vlm_preannotation_records[0]["status"], "stale_project")
        self.assertIn("vlm_image_result", owner.completed)

    def test_dataset_export_blocks_project_switch(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin

        owner = type("BusyOwner", (MainWindowModelManagementMixin,), {})()
        owner.current_lang = "en"
        owner.dataset_export_thread = FakeRunningThread()

        self.assertEqual(owner._active_project_bound_background_task(), "Export")

    def test_child_training_and_sam_block_project_switch(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin

        owner = type("BusyOwner", (MainWindowModelManagementMixin,), {})()
        owner.current_lang = "en"
        owner.blink_lab = type("BlinkLab", (), {"training_thread": FakeRunningThread()})()
        owner.sam_busy = False

        self.assertEqual(owner._active_project_bound_background_task(), "Training")

        owner.blink_lab.training_thread = None
        owner.sam_busy = True

        self.assertEqual(owner._active_project_bound_background_task(), "SAM Auto-Annotation")

    def test_stale_training_error_is_ignored(self):
        from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin
        from AntSleap.ui.main_window_training import MainWindowTrainingMixin

        owner = type("TrainingOwner", (MainWindowModelManagementMixin, MainWindowTrainingMixin), {})()
        owner.project = FakeProject(str(ROOT / "old.sqlite_manifest.json"))
        owner.parent_training_project_context = owner._capture_project_task_context()
        owner.project.current_project_path = str(ROOT / "new.sqlite_manifest.json")
        stale_events = []
        owner._log_stale_project_task_result = lambda workflow, _context: stale_events.append(workflow)

        owner._on_training_error({"type": "runtime", "message": "old failure"})

        self.assertEqual(stale_events, ["parent_training_error"])


if __name__ == "__main__":
    unittest.main()
