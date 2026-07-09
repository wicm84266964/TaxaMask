# pyright: reportMissingImports=false

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-gpu-compositing")

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
        PdfProcessingWidget = None
        pdf_widget_module = None
    else:
        raise
else:
    import AntSleap.ui.pdf_processing_widget as pdf_widget_module
    from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget


@unittest.skipUnless(QApplication is not None, "PySide6 is required for PDF profile safety tests")
class PdfProfileDeletionSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_widget(self):
        with patch.object(PdfProcessingWidget, "load_api_settings", lambda self: None), \
            patch.object(PdfProcessingWidget, "refresh_poppler_status", lambda self: None):
            widget = PdfProcessingWidget("en")
        widget.configs_dir = str(self.root / "screener_configs")
        widget.figure_configs_dir = str(self.root / "multimodal_configs")
        widget.part_description_configs_dir = str(self.root / "part_description_configs")
        widget.api_settings_file = str(Path(widget.configs_dir) / "api_runtime_settings.json")
        for directory in (widget.configs_dir, widget.figure_configs_dir, widget.part_description_configs_dir):
            Path(directory).mkdir(parents=True, exist_ok=True)
        widget.refresh_profile_list()
        widget.refresh_figure_profile_list()
        widget.refresh_part_description_profile_list()
        return widget

    def test_default_profiles_are_not_deleted_or_prompted(self):
        widget = self._make_widget()
        try:
            with patch.object(pdf_widget_module, "themed_yes_no_question", side_effect=AssertionError("default delete should not ask")):
                widget.delete_current_profile()
                widget.delete_current_figure_profile()
                widget.delete_current_part_description_profile()

            self.assertEqual(widget.combo_profiles.currentData(), "DEFAULT_V2")
            self.assertEqual(widget.combo_figure_profiles.currentData(), "DEFAULT_FIGURE")
            self.assertEqual(widget.combo_part_description_profiles.currentData(), "DEFAULT_PART_DESCRIPTION")
        finally:
            widget.deleteLater()

    def test_custom_screener_profile_deletion_removes_only_selected_json(self):
        widget = self._make_widget()
        try:
            selected = Path(widget.configs_dir) / "Keep_Custom_Ant_Filter.json"
            neighbor = Path(widget.configs_dir) / "Other_Filter.json"
            selected.write_text(json.dumps({"processing_mode": "v2"}), encoding="utf-8")
            neighbor.write_text(json.dumps({"processing_mode": "v2"}), encoding="utf-8")
            widget.current_profile_name = "Keep_Custom_Ant_Filter"
            widget.refresh_profile_list()
            widget.combo_profiles.setCurrentIndex(widget.combo_profiles.findText("Keep_Custom_Ant_Filter"))

            with patch.object(pdf_widget_module, "themed_yes_no_question", return_value=pdf_widget_module.QMessageBox.Yes):
                widget.delete_current_profile()

            self.assertFalse(selected.exists())
            self.assertTrue(neighbor.exists())
            self.assertEqual(widget.combo_profiles.currentData(), "DEFAULT_V2")
        finally:
            widget.deleteLater()

    def test_cancelled_custom_profile_deletion_keeps_file(self):
        widget = self._make_widget()
        try:
            selected = Path(widget.figure_configs_dir) / "custom_figure.json"
            selected.write_text(json.dumps({"profile_name": "Custom Figure"}), encoding="utf-8")
            widget.current_figure_profile_name = "Custom Figure"
            widget.refresh_figure_profile_list()
            widget.combo_figure_profiles.setCurrentIndex(widget.combo_figure_profiles.findText("Custom Figure"))

            with patch.object(pdf_widget_module, "themed_yes_no_question", return_value=pdf_widget_module.QMessageBox.No):
                widget.delete_current_figure_profile()

            self.assertTrue(selected.exists())
            self.assertEqual(widget.combo_figure_profiles.currentText(), "Custom Figure")
        finally:
            widget.deleteLater()

    def test_custom_figure_and_part_description_deletion_use_combo_data_path(self):
        widget = self._make_widget()
        try:
            figure_path = Path(widget.figure_configs_dir) / "custom_figure_filename.json"
            part_path = Path(widget.part_description_configs_dir) / "custom_part_filename.json"
            figure_neighbor = Path(widget.figure_configs_dir) / "figure_neighbor.json"
            part_neighbor = Path(widget.part_description_configs_dir) / "part_neighbor.json"
            figure_path.write_text(json.dumps({"profile_name": "Displayed Figure Name"}), encoding="utf-8")
            part_path.write_text(json.dumps({"profile_name": "Displayed Part Name"}), encoding="utf-8")
            figure_neighbor.write_text(json.dumps({"profile_name": "Figure Neighbor"}), encoding="utf-8")
            part_neighbor.write_text(json.dumps({"profile_name": "Part Neighbor"}), encoding="utf-8")

            widget.current_figure_profile_name = "Displayed Figure Name"
            widget.current_part_description_profile_name = "Displayed Part Name"
            widget.refresh_figure_profile_list()
            widget.refresh_part_description_profile_list()
            widget.combo_figure_profiles.setCurrentIndex(widget.combo_figure_profiles.findText("Displayed Figure Name"))
            widget.combo_part_description_profiles.setCurrentIndex(widget.combo_part_description_profiles.findText("Displayed Part Name"))

            with patch.object(pdf_widget_module, "themed_yes_no_question", return_value=pdf_widget_module.QMessageBox.Yes):
                widget.delete_current_figure_profile()
                widget.delete_current_part_description_profile()

            self.assertFalse(figure_path.exists())
            self.assertFalse(part_path.exists())
            self.assertTrue(figure_neighbor.exists())
            self.assertTrue(part_neighbor.exists())
            self.assertEqual(widget.combo_figure_profiles.currentData(), "DEFAULT_FIGURE")
            self.assertEqual(widget.combo_part_description_profiles.currentData(), "DEFAULT_PART_DESCRIPTION")
        finally:
            widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
