import ast
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class FakeThread:
    def __init__(self, running):
        self.running = running

    def isRunning(self):
        return self.running


class MainWindowStage8ArchitectureTests(unittest.TestCase):
    def test_main_window_class_only_owns_constructor(self):
        source = (ROOT / "AntSleap" / "main.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        main_window = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MainWindow")
        methods = [node.name for node in main_window.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

        self.assertEqual(methods, ["__init__"])

    def test_presentation_methods_resolve_from_presentation_mixin(self):
        import AntSleap.main as main_module
        from AntSleap.ui.main_window_presentation import MainWindowPresentationMixin

        self.assertIs(main_module.MainWindow.refresh_ui, MainWindowPresentationMixin.refresh_ui)
        self.assertIs(main_module.MainWindow.open_stl_model_settings, MainWindowPresentationMixin.open_stl_model_settings)
        self.assertIs(main_module.MainWindow.change_theme, MainWindowPresentationMixin.change_theme)
        self.assertIs(main_module.MainWindow.log, MainWindowPresentationMixin.log)

    def test_presentation_module_does_not_import_main_window(self):
        source = (ROOT / "AntSleap" / "ui" / "main_window_presentation.py").read_text(encoding="utf-8")

        self.assertNotIn("AntSleap.main", source)
        self.assertNotIn("from main import", source)

    def test_workflow_modules_stay_within_reviewable_size(self):
        filenames = (
            "main_window_image_navigation.py",
            "main_window_image_grouping.py",
            "main_window_project_lifecycle.py",
            "main_window_vlm.py",
            "main_window_training.py",
            "main_window_presentation.py",
        )
        for filename in filenames:
            line_count = len((ROOT / "AntSleap" / "ui" / filename).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(line_count, 1500, filename)

    def test_idle_project_switch_guard_does_not_translate_task_labels(self):
        import AntSleap.ui.main_window_model_management as model_module

        owner = type("IdleOwner", (model_module.MainWindowModelManagementMixin,), {})()
        owner.current_lang = "en"
        translation_calls = []
        with patch.object(model_module, "tr", side_effect=lambda text, lang: translation_calls.append(text) or text):
            self.assertEqual(owner._active_project_bound_background_task(), "")

        self.assertEqual(translation_calls, [])

    def test_active_project_switch_guard_translates_only_detected_task(self):
        import AntSleap.ui.main_window_model_management as model_module

        owner = type("BusyOwner", (model_module.MainWindowModelManagementMixin,), {})()
        owner.current_lang = "en"
        owner.dataset_export_thread = FakeThread(True)
        translation_calls = []
        with patch.object(model_module, "tr", side_effect=lambda text, lang: translation_calls.append(text) or text):
            self.assertEqual(owner._active_project_bound_background_task(), "Export")

        self.assertEqual(translation_calls, ["Export"])


if __name__ == "__main__":
    unittest.main()
