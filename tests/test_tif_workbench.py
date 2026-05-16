import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

has_pyside6 = False

try:
    from PySide6.QtWidgets import QApplication, QLabel, QTextEdit
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from AntSleap.core.tif_materials import upsert_material
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.core.tif_volume_io import write_volume_sidecar
    from AntSleap.ui.tif_workbench import TifWorkbenchWidget

    has_pyside6 = True


class patch_message_boxes:
    def __enter__(self):
        if not has_pyside6:
            return self
        module_path = "AntSleap.ui.tif_workbench.QMessageBox"
        self._patchers = [
            patch(f"{module_path}.information", return_value=None),
            patch(f"{module_path}.warning", return_value=None),
            patch(f"{module_path}.critical", return_value=None),
        ]
        for patcher in self._patchers:
            patcher.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        for patcher in reversed(getattr(self, "_patchers", [])):
            patcher.stop()
        return False


@unittest.skipUnless(has_pyside6, "PySide6 is required for TIF workbench tests")
class TifWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_tif_workbench_loads_specimen_and_renders_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("viewer", root / "viewer")
            manager.create_specimen_scaffold(
                "01-0101-08",
                modality="confocal",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 2, "name": "LO_L", "display_name": "LO_L", "color": "#ff0000", "trainable": True},
                    ]
                },
            )
            image = np.arange(3 * 6 * 7, dtype=np.uint8).reshape((3, 6, 7))
            labels = np.zeros((3, 6, 7), dtype=np.uint16)
            labels[1, 2:5, 3:6] = 2
            image_rel = "specimens/01-0101-08/working/image.ome.zarr"
            label_rel = "specimens/01-0101-08/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(root / "viewer" / image_rel, image, role="working_image")
            label_meta = write_volume_sidecar(root / "viewer" / label_rel, labels, role="manual_truth")
            manager.register_working_volume("01-0101-08", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            edit_rel = "specimens/01-0101-08/labels/working_edit.ome.zarr"
            edit_meta = write_volume_sidecar(root / "viewer" / edit_rel, np.zeros_like(labels), role="working_edit")
            manager.register_label_volume("01-0101-08", "manual_truth", label_rel, label_meta["shape_zyx"], label_meta["dtype"], save=False)
            manager.register_label_volume("01-0101-08", "working_edit", edit_rel, edit_meta["shape_zyx"], edit_meta["dtype"], save=False)
            manager.set_review_status("01-0101-08", "train_ready", train_ready=True)

            widget = TifWorkbenchWidget(manager, "en")
            try:
                self.assertEqual(widget.specimen_list.count(), 1)
                self.assertEqual(widget.current_specimen_id, "01-0101-08")
                self.assertEqual(widget.slice_slider.maximum(), 2)
                self.assertEqual(widget.material_table.rowCount(), 2)
                widget.slice_slider.setValue(1)
                widget.render_current_slice()
                self.assertIsNotNone(widget.canvas.pixmap())
                self.assertIn("Train-ready: yes", widget.status_label.text())
                self.assertIn("Shape Z/Y/X", widget.metadata_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_brush_edit_saves_working_edit_without_touching_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("brush", root / "brush")
            manager.create_specimen_scaffold(
                "01-0101-10",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 5, "name": "AL_L", "display_name": "AL_L", "color": "#00ff00", "trainable": True},
                    ]
                },
            )
            image = np.zeros((2, 12, 12), dtype=np.uint8)
            manual = np.zeros((2, 12, 12), dtype=np.uint16)
            edit = np.zeros((2, 12, 12), dtype=np.uint16)
            image_rel = "specimens/01-0101-10/working/image.ome.zarr"
            manual_rel = "specimens/01-0101-10/labels/manual_truth.ome.zarr"
            edit_rel = "specimens/01-0101-10/labels/working_edit.ome.zarr"
            image_meta = write_volume_sidecar(root / "brush" / image_rel, image, role="working_image")
            manual_meta = write_volume_sidecar(root / "brush" / manual_rel, manual, role="manual_truth")
            edit_meta = write_volume_sidecar(root / "brush" / edit_rel, edit, role="working_edit")
            manager.register_working_volume("01-0101-10", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.register_label_volume("01-0101-10", "manual_truth", manual_rel, manual_meta["shape_zyx"], manual_meta["dtype"], save=False)
            manager.register_label_volume("01-0101-10", "working_edit", edit_rel, edit_meta["shape_zyx"], edit_meta["dtype"], save=False)
            manager.set_review_status("01-0101-10", "train_ready", train_ready=True)

            widget = TifWorkbenchWidget(manager)
            try:
                widget.slice_slider.setValue(0)
                widget.current_material_id = 5
                widget.brush_size_slider.setValue(2)
                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)
                widget.save_working_edit()

                saved_edit = np.load(root / "brush" / edit_rel / "array.npy")
                saved_manual = np.load(root / "brush" / manual_rel / "array.npy")
                self.assertGreater(int(saved_edit.sum()), 0)
                self.assertEqual(int(saved_manual.sum()), 0)
                self.assertFalse(manager.evaluate_train_ready("01-0101-10")["train_ready"])
                widget.undo()
                widget.redo()
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_material_map_can_be_edited_and_refuses_used_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("materials_ui", root / "materials_ui")
            manager.create_specimen_scaffold(
                "01-0101-13",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "trainable": False},
                        {"id": 5, "name": "brain", "display_name": "Brain", "color": "#ff0000", "trainable": True},
                    ]
                },
            )
            image = np.zeros((2, 8, 8), dtype=np.uint8)
            labels = np.zeros((2, 8, 8), dtype=np.uint16)
            labels[0, 2:4, 2:4] = 5
            image_rel = "specimens/01-0101-13/working/image.ome.zarr"
            edit_rel = "specimens/01-0101-13/labels/working_edit.ome.zarr"
            image_meta = write_volume_sidecar(root / "materials_ui" / image_rel, image, role="working_image")
            edit_meta = write_volume_sidecar(root / "materials_ui" / edit_rel, labels, role="working_edit")
            manager.register_working_volume("01-0101-13", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.register_label_volume("01-0101-13", "working_edit", edit_rel, edit_meta["shape_zyx"], edit_meta["dtype"], save=False)
            manager.save_project()

            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.load_specimen("01-0101-13")
                widget.material_map = upsert_material(
                    widget.material_map,
                    {"id": 6, "name": "optic_lobe", "display_name": "Optic lobe", "color": "#00ff00", "trainable": True},
                )
                widget._save_material_map()
                self.assertEqual(widget.material_table.rowCount(), 3)
                self.assertTrue(widget._material_id_is_used(5))
                self.assertFalse(widget._material_id_is_used(6))
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_training_handoff_controls_are_visible(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            self.assertEqual(widget.btn_import_tif.text(), "Import TIF stack")
            self.assertEqual(widget.btn_import_amira.text(), "Import AMIRA directory")
            self.assertEqual(widget.btn_export_training.text(), "Export train-ready volumes")
            self.assertEqual(widget.btn_prepare_dataset.text(), "Prepare dataset")
            self.assertEqual(widget.btn_train_backend.text(), "Train backend")
            self.assertEqual(widget.btn_import_prediction.text(), "Import prediction")
            self.assertIsNotNone(widget.findChild(type(widget.btn_export_training), "tifExportTrainingButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_import_tif), "tifImportStackButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_import_amira), "tifImportAmiraButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_prepare_dataset), "tifPrepareDatasetButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_train_backend), "tifTrainBackendButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_import_prediction), "tifImportPredictionButton"))
            self.assertEqual(widget.backend_id_edit.objectName(), "tifBackendIdEdit")
            self.assertEqual(widget.backend_formats_edit.text(), "ome_tiff,nrrd,mha,nifti")
            self.assertEqual(widget.training_status_label.objectName(), "tifTrainingStatusText")
            self.assertEqual(widget.log_console.objectName(), "tifLogConsole")
            self.assertEqual(widget.btn_import_tif.property("tifRole"), "primary")
            self.assertEqual(widget.btn_train_backend.property("tifRole"), "primary")
            self.assertEqual(widget.btn_save_backend.property("tifRole"), "secondary")
            self.assertEqual(widget.btn_delete_material.property("tifRole"), "danger")
            self.assertGreaterEqual(widget.btn_import_tif.minimumHeight(), 34)
            self.assertEqual(widget.specimen_list.objectName(), "tifSpecimenList")
            self.assertEqual(widget.material_table.objectName(), "tifMaterialTable")
            self.assertIsNotNone(widget.findChild(QTextEdit, "tifLogConsole"))
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_tif_workbench_chinese_labels_cover_import_and_backend_controls(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget.change_language("zh")
            self.assertEqual(widget.btn_import_tif.text(), "导入 TIF stack")
            self.assertEqual(widget.btn_import_amira.text(), "导入 AMIRA 目录")
            self.assertEqual(widget.btn_export_training.text(), "导出可训练体数据")
            self.assertEqual(widget.btn_prepare_dataset.text(), "准备训练数据")
            self.assertEqual(widget.btn_train_backend.text(), "训练后端")
            self.assertEqual(widget.btn_import_prediction.text(), "运行预测并导入草稿")
            section_titles = {
                label.text()
                for label in widget.findChildren(QLabel)
                if label.objectName() == "tifSectionTitle"
            }
            self.assertIn("模型训练", section_titles)
            self.assertIn("模型配置", section_titles)
            self.assertIn("工作台日志", section_titles)
            self.assertEqual(widget.label_role_combo.itemText(widget.label_role_combo.findData("manual_truth")), "人工真值")
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_backend_settings_save_into_config_manager(self):
        class Config:
            def __init__(self):
                self.values = {}
                self.save_calls = 0

            def get(self, key, default=None):
                return self.values.get(key, default)

            def set(self, key, value):
                self.values[key] = value

            def save(self):
                self.save_calls += 1

        manager = TifProjectManager()
        config = Config()
        widget = TifWorkbenchWidget(manager, "en", config_manager=config)
        try:
            widget.backend_id_edit.setText("volume_backend")
            widget.backend_python_edit.setText("C:/Python/python.exe")
            widget.backend_formats_edit.setText("nrrd,mha")
            widget.backend_prepare_edit.setText("{python} prepare.py {contract}")
            with patch_message_boxes():
                widget.save_backend_settings()
            self.assertEqual(config.values["tif_backend"]["backend_id"], "volume_backend")
            self.assertEqual(config.values["tif_backend"]["export_formats"], "nrrd,mha")
            self.assertEqual(config.save_calls, 1)
            self.assertIn("Backend settings saved.", widget.log_console.toPlainText())
        finally:
            widget.close_project()
            widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
