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
    from PIL import Image

    import AntSleap.main as main_module
    from AntSleap.core.project_templates import PROJECT_TEMPLATE_GENERIC
    from AntSleap.core.stl_project import StlRenderedProjectManager
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget

    has_pyside6 = True


class SmokeConfigManager:
    def __init__(self):
        self.values = {
            "language": "en",
            "runtime_device": "cpu",
            "theme": "dark",
            "last_project_path": "",
            "tif_backend": {
                "backend_id": "custom_tif_backend",
                "display_name": "TIF Volume Backend",
                "python_executable": "python",
                "prepare_dataset_command": "",
                "train_command": "",
                "predict_command": "",
                "model_manifest": "",
                "export_formats": "ome_tiff,nrrd,mha,nifti",
            },
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
            self.assertEqual((window.startup_size.width(), window.startup_size.height()), (1480, 920))
            self.assertEqual(window.active_project_kind, "start")
            self.assertEqual(window.tabs.count(), 1)
            self.assertEqual(window.tabs.currentWidget(), window.start_center_widget)
            self.assertEqual(window.tabs.tabText(0), "Start Center")
            self.assertEqual(window.start_title.text(), "TaxaMask Workflow Selection")
            self.assertIsNotNone(window.findChild(main_module.QWidget, "start2DWorkflowCard"))
            self.assertIsNotNone(window.findChild(main_module.QWidget, "startTifWorkflowCard"))
            menu_texts = [
                action.text()
                for menu_action in window.menuBar().actions()
                if menu_action.menu() is not None
                for action in menu_action.menu().actions()
            ]
            self.assertIn("Workflow", [action.text() for action in window.menuBar().actions()])
            self.assertIn("Start Center", menu_texts)
            self.assertIn("2D/STL Morphology Workflow", menu_texts)
            self.assertIn("TIF Volume Workflow", menu_texts)
            self.assertIn("2D/STL Model Settings", menu_texts)
            self.assertIn("TIF Volume Model Settings", menu_texts)
            self.assertNotIn("Language", menu_texts)
            self.assertNotIn("Theme", menu_texts)
            self.assertNotIn("Dark Mode", menu_texts)
            self.assertIn("Check / Relocate Project Images", menu_texts)
            self.assertIn("New TIF Volume Project", menu_texts)
            self.assertNotIn("Import TIF Stack", menu_texts)
            self.assertNotIn("Import AMIRA Directory", menu_texts)
            self.assertIn("Import STL Rendered Views to Labeling Workbench", menu_texts)
            self.assertIn("Open PDF Evidence Tools", menu_texts)
            self.assertNotIn("New STL Rendered-View Project", menu_texts)
        finally:
            window.deleteLater()

    def test_start_center_workflow_buttons_switch_visible_tabs(self):
        window = self._make_window()
        try:
            window.enter_image_workflow()
            self.assertEqual(window.active_project_kind, "image")
            self.assertEqual(window.tabs.count(), 2)
            self.assertEqual(window.tabs.tabText(0), "Labeling Workbench")
            self.assertEqual(window.tabs.tabText(1), "Blink Workbench")
            self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchCanvasShell"))

            window._show_start_center()
            self.assertEqual(window.tabs.count(), 1)
            self.assertEqual(window.tabs.currentWidget(), window.start_center_widget)

            window.enter_tif_workflow()
            self.assertEqual(window.active_project_kind, "tif")
            self.assertEqual(window.tabs.count(), 1)
            self.assertEqual(window.tabs.currentWidget(), window.tif_workbench)
            self.assertEqual(window.tabs.tabText(0), "TIF Volume Workbench")
        finally:
            window.deleteLater()

    def test_language_switch_and_model_settings_are_lightweight(self):
        window = self._make_window()
        try:
            window.change_language("zh")
            self.assertEqual(window.current_lang, "zh")
            self.assertIn("TaxaMask Workbench", window.windowTitle())
            self.assertEqual(window.tif_workbench.btn_import_tif.text(), "导入 TIF stack")
            self.assertEqual(window.start_title.text(), "TaxaMask 工作流选择")

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
                self.assertEqual(dialog.windowTitle(), "2D/STL 形态学模型设置")
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

    def test_general_settings_are_not_2d_stl_model_settings(self):
        dialog = main_module.GeneralSettingsDialog(
            {
                "language": "zh",
                "theme": "dark",
                "startup_behavior": "continue_last",
                "project_autosave_interval_sec": 5,
                "runtime_device": "cpu",
            },
            lang="zh",
        )
        try:
            self.assertEqual(dialog.windowTitle(), "软件通用设置")
            values = dialog.get_values()
            self.assertEqual(values["language"], "zh")
            self.assertEqual(values["startup_behavior"], "continue_last")
            self.assertEqual(values["project_autosave_interval_sec"], 5)
            self.assertEqual(values["runtime_device"], "cpu")
            self.assertIsNone(dialog.findChild(main_module.QWidget, "modelSettingsLocatorScopePanel"))
        finally:
            dialog.deleteLater()

    def test_tif_model_settings_match_volume_backend_contract(self):
        dialog = main_module.TifModelSettingsDialog(
            {
                "backend_id": "tif_unet",
                "display_name": "TIF U-Net",
                "python_executable": "C:/Users/admin/anaconda3/envs/antsleap/python.exe",
                "export_formats": "nrrd,mha",
                "prepare_dataset_command": "{python} prepare.py --contract {contract_json}",
                "train_command": "{python} train.py --contract {contract_json}",
                "predict_command": "",
                "model_manifest": "{run_dir}/outputs/model_manifest.json",
            },
            lang="zh",
        )
        try:
            self.assertEqual(dialog.windowTitle(), "TIF 体数据训练设置")
            safety_panel = dialog.findChild(main_module.QWidget, "tifModelSettingsSafetyPanel")
            self.assertIsNotNone(safety_panel)
            self.assertEqual(dialog._validation_errors(), [])
            values = dialog.get_values()
            self.assertEqual(values["backend_id"], "tif_unet")
            self.assertEqual(values["export_formats"], "nrrd,mha")
            self.assertIn("{contract_json}", values["train_command"])

            dialog.export_formats_edit.setText("nrrd,bad_format")
            self.assertIn("不支持的 TIF 导出格式", "\n".join(dialog._validation_errors()))
        finally:
            dialog.deleteLater()

    def test_tif_model_settings_save_syncs_workbench_defaults(self):
        window = self._make_window()
        try:
            dialog = main_module.TifModelSettingsDialog(window.config.get("tif_backend", {}), lang="en", parent=window)
            try:
                dialog.backend_id_edit.setText("volume_backend")
                dialog.display_name_edit.setText("Volume Backend")
                dialog.python_edit.setText("C:/Python/python.exe")
                dialog.export_formats_edit.setText("nrrd,mha")
                dialog.prepare_command_edit.setPlainText("{python} prepare.py --contract {contract}")
                dialog.train_command_edit.setPlainText("")
                dialog.predict_command_edit.setPlainText("")
                backend_config = dialog.get_values()
            finally:
                dialog.deleteLater()

            window.config.set("tif_backend", dict(backend_config))
            window.tif_workbench.set_config_manager(window.config)

            self.assertEqual(window.config.values["tif_backend"]["backend_id"], "volume_backend")
            self.assertEqual(window.tif_workbench.backend_id_edit.text(), "volume_backend")
            self.assertEqual(window.tif_workbench.backend_formats_edit.text(), "nrrd,mha")
        finally:
            window.deleteLater()

    def test_project_create_and_open_lightweight_path(self):
        window = self._make_window()
        try:
            window.project.create_project("smoke_project", str(self.project_dir), template_id=PROJECT_TEMPLATE_GENERIC)
            created_path = self.project_dir / "smoke_project.json"
            self.assertTrue(created_path.exists())

            window.open_project_path(str(created_path))
            self.assertEqual(window.project.project_data["name"], "smoke_project")
            self.assertEqual(window.project.get_locator_scope(), ["Object"])
            self.assertEqual(window.active_project_kind, "image")
            self.assertEqual(window.tabs.currentWidget(), window.workbench_widget)
        finally:
            window.deleteLater()

    def test_tif_project_open_path_switches_to_tif_workbench(self):
        window = self._make_window()
        try:
            tif_project = TifProjectManager()
            tif_path = tif_project.create_project("tif_smoke", self.project_dir / "tif_smoke")

            self.assertTrue(window._is_tif_project_file(tif_path))
            window.tif_project.load_project(tif_path)
            window.active_project_kind = "tif"
            window._refresh_project_bound_views()

            self.assertEqual(window.tabs.count(), 1)
            self.assertEqual(window.tabs.currentWidget(), window.tif_workbench)
            self.assertEqual(window.tabs.tabText(0), "TIF Volume Workbench")
            self.assertEqual(window.tif_project.project_data["project_type"], "tif_volume")
        finally:
            window.deleteLater()

    def test_pdf_evidence_tools_open_on_demand(self):
        window = self._make_window()
        try:
            window.enter_image_workflow()
            self.assertEqual(window.tabs.count(), 2)
            window.open_pdf_evidence_tools()
            self.assertEqual(window.tabs.currentWidget(), window.pdf_widget)
            self.assertEqual(window.tabs.tabText(window.tabs.currentIndex()), "PDF Evidence Tools")
            self.assertEqual(window.tabs.count(), 3)
        finally:
            window.deleteLater()

    def test_stl_project_open_path_registers_views_into_labeling_workbench(self):
        window = self._make_window()
        try:
            source = self.project_dir / "stl_source"
            source.mkdir()
            Image.new("RGB", (32, 24), "red").save(source / "01_0101_02_dorsal.png")

            stl_project = StlRenderedProjectManager()
            stl_path = stl_project.create_project("stl_smoke", self.project_dir / "stl_smoke")
            stl_project.import_rendered_view_directory(source, copy_files=True, known_views=["dorsal"])
            (self.project_dir / "review").mkdir()
            window.project.create_project("review", str(self.project_dir / "review"), template_id=PROJECT_TEMPLATE_GENERIC)

            self.assertTrue(window._is_stl_project_file(stl_path))
            with patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(stl_path, "JSON (*.json)")):
                window.open_project()

            self.assertEqual(window.active_project_kind, "image")
            self.assertEqual(window.tabs.currentWidget(), window.workbench_widget)
            self.assertEqual(window.tabs.count(), 2)
            self.assertEqual(len(window.project.project_data["images"]), 1)
            image_path = window.project.project_data["images"][0]
            provenance = window.project.get_image_provenance(image_path)
            self.assertEqual(provenance["source_type"], "stl_rendered_view")
            self.assertEqual(window.project.project_data["labels"][image_path]["review_mode"], "stl_rendered_view")
        finally:
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
