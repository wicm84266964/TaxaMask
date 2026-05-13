# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

has_pyside6 = False

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
        main_module = None
        PROJECT_TEMPLATE_GENERIC = "generic_taxonomy"
        PdfProcessingWidget = None
    else:
        raise
else:
    import AntSleap.main as main_module
    from AntSleap.core.project_templates import PROJECT_TEMPLATE_GENERIC
    from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget

    has_pyside6 = True


class SmokeConfigManager:
    def __init__(self):
        self.values = {
            "language": "en",
            "runtime_device": "cpu",
            "theme": "dark",
            "last_project_path": "",
        }

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def save(self):
        return None


class SmokePartsModel:
    ultralytics_sam = None


class SmokeCascadeManager:
    def list_available_experts(self):
        return []

    def get_route_block_reason(self, route):
        return "expert_unappointed"


class SmokeEngine:
    def __init__(self, *args, **kwargs):
        self.weights_dir = tempfile.mkdtemp()
        self.parts_model = SmokePartsModel()
        self.cascade_manager = SmokeCascadeManager()
        self.current_num_classes = int(kwargs.get("num_classes", 3) or 3)
        self.locator_resolution = (512, 512)
        self.loaded_locator_requires_legacy_confirmation = False
        self.loaded_locator_is_legacy_512 = False
        self.loaded_locator_timestamp = None
        self.device_preference = kwargs.get("device", "cpu")

    def set_device_preference(self, preference):
        self.device_preference = preference
        return False

    def rebuild_locator(self, num_classes, learning_rate, weight_decay):
        self.current_num_classes = int(num_classes)

    def update_hyperparameters(self, learning_rate, weight_decay):
        return None

    def load_locator(self, timestamp):
        return None

    def load_sam_decoder(self, timestamp):
        return None

    def reset_locator_to_base(self):
        return None

    def reset_sam_to_base(self):
        return None


class SmokeDatabase:
    def query_trait_description(self, genus_name, part_name):
        return ""


@unittest.skipUnless(has_pyside6, "PySide6 is required for GUI smoke tests")
class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_window(self):
        with patch.object(main_module, "ConfigManager", SmokeConfigManager), \
             patch.object(main_module, "AntEngine", SmokeEngine), \
             patch.object(main_module, "MultiModalDB", SmokeDatabase), \
             patch.object(PdfProcessingWidget, "load_api_settings", lambda self: None), \
             patch.object(PdfProcessingWidget, "refresh_profile_list", lambda self: None), \
             patch.object(PdfProcessingWidget, "sync_runtime_controls_from_config", lambda self: None), \
             patch.object(main_module.QTimer, "singleShot", lambda *args, **kwargs: None):
            return main_module.MainWindow()

    def test_main_window_constructs_offscreen_without_loading_sam(self):
        window = self._make_window()
        try:
            self.assertEqual(window.windowTitle(), "TaxaMask Workbench (EN)")
            self.assertEqual(window.runtime_device, "cpu")
            self.assertEqual(window.tabs.count(), 3)
            self.assertEqual(window.tabs.tabText(0), "PDF Processing")
            self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchCanvasShell"))
            menu_texts = [
                action.text()
                for menu_action in window.menuBar().actions()
                if menu_action.menu() is not None
                for action in menu_action.menu().actions()
            ]
            self.assertIn("Check / Relocate Project Images", menu_texts)
        finally:
            window.deleteLater()

    def test_language_switch_and_model_settings_are_lightweight(self):
        window = self._make_window()
        try:
            window.change_language("zh")
            self.assertEqual(window.current_lang, "zh")
            self.assertIn("TaxaMask Workbench", window.windowTitle())

            dialog = main_module.ModelSettingsDialog(
                {
                    "epochs": 1,
                    "batch": 1,
                    "lr": 1e-4,
                    "wd": 1e-4,
                    "conf": 0.1,
                    "adapt": 0.4,
                    "pad": 0.4,
                    "noise_floor": 0.15,
                    "poly_epsilon": 2.0,
                    "runtime_device": "cpu",
                    "taxonomy": ["Head", "Mesosoma"],
                    "locator_scope": ["Head"],
                },
                lang=window.current_lang,
                parent=window,
            )
            try:
                self.assertEqual(dialog.get_values()["runtime_device"], "cpu")
                runtime_group = dialog.findChild(main_module.QWidget, "modelSettingsRuntimeDevicePanel")
                self.assertIsNotNone(runtime_group)
                device_combo = runtime_group.findChild(main_module.QComboBox)
                self.assertIsNotNone(device_combo)
                device_values = {
                    device_combo.itemData(index)
                    for index in range(device_combo.count())
                }
                self.assertEqual(device_values, {"auto", "cpu", "cuda"})
                self.assertNotIn("mps", device_values)
            finally:
                dialog.deleteLater()
        finally:
            window.deleteLater()

    def test_project_create_and_open_lightweight_path(self):
        window = self._make_window()
        try:
            window.project.create_project("smoke_project", str(self.project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            created_path = self.project_dir / "smoke_project.json"
            self.assertTrue(created_path.exists())

            window.project.load_project(str(created_path))
            window._refresh_project_bound_views()
            self.assertEqual(window.project.project_data["name"], "smoke_project")
            self.assertEqual(window.project.get_locator_scope(), ["Object"])
        finally:
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
