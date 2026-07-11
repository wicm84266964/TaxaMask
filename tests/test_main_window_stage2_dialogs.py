import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MainWindowStage2DialogTests(unittest.TestCase):
    def test_main_reexports_stage2_dialogs(self):
        import AntSleap.main as main_module
        from AntSleap.ui.main_window_dialogs import BlinkEntryDialog, ExportDialog, LiteratureDescriptionDialog
        from AntSleap.ui.model_settings_dialog import ModelSettingsDialog
        from AntSleap.ui.route_management_panel import RouteManagementPanel
        from AntSleap.ui.settings_dialogs import GeneralSettingsDialog, TifModelSettingsDialog
        from AntSleap.ui.training_report_dialogs import (
            TrainingPreflightDialog,
            TrainingReportDialog,
            TrainingResultBrowserDialog,
        )

        expected = {
            "BlinkEntryDialog": BlinkEntryDialog,
            "ExportDialog": ExportDialog,
            "GeneralSettingsDialog": GeneralSettingsDialog,
            "LiteratureDescriptionDialog": LiteratureDescriptionDialog,
            "ModelSettingsDialog": ModelSettingsDialog,
            "RouteManagementPanel": RouteManagementPanel,
            "TifModelSettingsDialog": TifModelSettingsDialog,
            "TrainingPreflightDialog": TrainingPreflightDialog,
            "TrainingReportDialog": TrainingReportDialog,
            "TrainingResultBrowserDialog": TrainingResultBrowserDialog,
        }
        for name, dialog_class in expected.items():
            self.assertIs(getattr(main_module, name), dialog_class)

    def test_dialog_modules_do_not_import_main_window(self):
        module_names = [
            "main_window_dialogs.py",
            "model_settings_agent.py",
            "model_settings_dataset.py",
            "model_settings_dialog.py",
            "model_settings_profile.py",
            "model_settings_view.py",
            "route_management_panel.py",
            "settings_dialogs.py",
            "training_report_dialogs.py",
        ]
        for module_name in module_names:
            source = (ROOT / "AntSleap" / "ui" / module_name).read_text(encoding="utf-8")
            self.assertNotIn("AntSleap.main", source)
            self.assertNotIn("from main import", source)

    def test_model_settings_initialization_is_split_by_responsibility(self):
        dialog_source = (ROOT / "AntSleap" / "ui" / "model_settings_dialog.py").read_text(encoding="utf-8")
        tree = ast.parse(dialog_source)
        dialog_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ModelSettingsDialog")
        init_method = next(node for node in dialog_class.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")

        self.assertLessEqual(init_method.end_lineno - init_method.lineno + 1, 65)
        for method_name in [
            "_build_profile_and_parent_extension",
            "_build_parent_tab",
            "_build_child_tab",
            "_build_inference_tab",
            "_build_dialog_actions",
        ]:
            self.assertIn(f"self.{method_name}", dialog_source)

        self.assertLess((ROOT / "AntSleap" / "ui" / "model_settings_view.py").read_text(encoding="utf-8").count("\n"), 850)
        self.assertLess((ROOT / "AntSleap" / "ui" / "model_settings_profile.py").read_text(encoding="utf-8").count("\n"), 850)

    def test_localization_and_dialog_support_are_centralized(self):
        import AntSleap.main as main_module
        from AntSleap.ui.main_window_i18n import SECTION_TRANSLATIONS, TRANSLATIONS, tr, ui_text

        self.assertIs(main_module.TRANSLATIONS, TRANSLATIONS)
        self.assertIs(main_module.SECTION_TRANSLATIONS, SECTION_TRANSLATIONS)
        self.assertIs(main_module.tr, tr)
        self.assertIs(main_module.ui_text, ui_text)
        self.assertEqual(tr("Save", "zh"), "保存")
        self.assertEqual(ui_text("Project Routes", "zh"), "项目路由")


if __name__ == "__main__":
    unittest.main()
