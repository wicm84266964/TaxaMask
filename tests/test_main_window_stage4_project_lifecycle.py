import tempfile
import unittest
from pathlib import Path


class FakeTimer:
    def __init__(self):
        self.active = False
        self.delay = 0

    def start(self, delay):
        self.active = True
        self.delay = delay

    def stop(self):
        self.active = False

    def isActive(self):
        return self.active


class FakeProject:
    def __init__(self, path):
        self.current_project_path = path
        self.project_data = {"images": [], "labels": {}}
        self.save_count = 0

    def save_project(self, force=False):
        self.save_count += 1


class MainWindowStage4ProjectLifecycleTests(unittest.TestCase):
    def test_main_window_inherits_project_lifecycle_contract(self):
        import AntSleap.main as main_module
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin

        self.assertIs(main_module.MainWindow.open_project_path, MainWindowProjectLifecycleMixin.open_project_path)
        self.assertIs(main_module.MainWindow.closeEvent, MainWindowProjectLifecycleMixin.closeEvent)
        self.assertIs(
            main_module.MainWindow._flush_pending_project_save,
            MainWindowProjectLifecycleMixin._flush_pending_project_save,
        )

    def test_stale_save_callback_never_writes_new_project(self):
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin

        with tempfile.TemporaryDirectory() as temp_dir:
            old_path = str(Path(temp_dir) / "old.sqlite_manifest.json")
            new_path = str(Path(temp_dir) / "new.sqlite_manifest.json")
            owner = type("LifecycleOwner", (MainWindowProjectLifecycleMixin,), {})()
            owner.project = FakeProject(old_path)
            owner.project_save_timer = FakeTimer()
            owner.project_autosave_delay_ms = 100
            owner.project_save_navigation_idle_ms = 100
            owner.project_last_image_switch_at = 0.0
            owner.project_save_pending = False
            owner.project_save_context = {}

            owner._schedule_project_save("annotation_changed")
            owner.project.current_project_path = new_path

            self.assertFalse(owner._flush_pending_project_save(force=True))
            self.assertEqual(owner.project.save_count, 0)
            self.assertFalse(owner.project_save_pending)
            self.assertEqual(owner.project_save_context, {})

    def test_project_lifecycle_module_does_not_import_main_window(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "AntSleap"
            / "ui"
            / "main_window_project_lifecycle.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("AntSleap.main", source)
        self.assertNotIn("from main import", source)


if __name__ == "__main__":
    unittest.main()
