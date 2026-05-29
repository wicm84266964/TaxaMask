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
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QTextEdit, QWidget
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from AntSleap.core.tif_materials import upsert_material
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.core.tif_volume_io import write_volume_sidecar
    from AntSleap.ui.tif_gpu_volume_canvas import gpu_volume_canvas_available, gpu_volume_unavailable_reason
    from AntSleap.ui.tif_workbench import TifVolumeCanvas, TifWorkbenchWidget, create_tif_volume_canvas

    has_pyside6 = True


class FakeWheelEvent:
    def __init__(self, delta_y=120):
        self._delta_y = int(delta_y)
        self.accepted = False
        self.ignored = False

    def angleDelta(self):
        class Delta:
            def __init__(self, value):
                self._value = value

            def y(self):
                return self._value

        return Delta(self._delta_y)

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


class FakeKeyEvent:
    def __init__(self, key):
        self._key = key
        self.accepted = False

    def key(self):
        return self._key

    def accept(self):
        self.accepted = True


class FakeMouseEvent:
    def __init__(self, button, buttons, x, y):
        self._button = button
        self._buttons = buttons
        self._position = QPointF(float(x), float(y))
        self.accepted = False

    def button(self):
        return self._button

    def buttons(self):
        return self._buttons

    def position(self):
        return self._position

    def modifiers(self):
        return Qt.NoModifier

    def accept(self):
        self.accepted = True


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

    def _make_volume_widget(self, root, z_count=4):
        manager = TifProjectManager()
        manager.create_project("viewer", root / "viewer")
        manager.create_specimen_scaffold(
            "01-0101-21",
            modality="confocal",
            material_map={
                "materials": [
                    {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                    {"id": 2, "name": "LO_L", "display_name": "LO_L", "color": "#ff0000", "trainable": True},
                ]
            },
        )
        image = np.arange(z_count * 8 * 8, dtype=np.uint8).reshape((z_count, 8, 8))
        edit = np.zeros((z_count, 8, 8), dtype=np.uint16)
        image_rel = "specimens/01-0101-21/working/image.ome.zarr"
        edit_rel = "specimens/01-0101-21/labels/working_edit.ome.zarr"
        image_meta = write_volume_sidecar(root / "viewer" / image_rel, image, role="working_image")
        edit_meta = write_volume_sidecar(root / "viewer" / edit_rel, edit, role="working_edit")
        manager.register_working_volume("01-0101-21", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
        manager.register_label_volume("01-0101-21", "working_edit", edit_rel, edit_meta["shape_zyx"], edit_meta["dtype"], save=False)
        manager.save_project()
        widget = TifWorkbenchWidget(manager, "en")
        widget.resize(900, 620)
        widget.canvas.resize(480, 360)
        widget.render_current_slice()
        return widget

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
                self.assertIsInstance(widget.edit_volume, np.memmap)
                widget.slice_slider.setValue(0)
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget.current_material_id = 5
                widget.brush_size_slider.setValue(2)
                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)
                self.assertEqual(widget._dirty_edit_slices, {0})
                widget.save_working_edit()

                saved_edit = np.load(root / "brush" / edit_rel / "array.npy")
                saved_manual = np.load(root / "brush" / manual_rel / "array.npy")
                self.assertGreater(int(saved_edit.sum()), 0)
                self.assertEqual(int(saved_manual.sum()), 0)
                self.assertFalse(manager.evaluate_train_ready("01-0101-10")["train_ready"])
                widget.undo()
                widget.redo()
                widget.save_working_edit()
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_working_edit_is_created_lazily_when_painting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("lazy_edit", root / "lazy_edit")
            manager.create_specimen_scaffold(
                "01-0101-lazy",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 7, "name": "brain", "display_name": "Brain", "color": "#00ff00", "trainable": True},
                    ]
                },
            )
            image = np.zeros((2, 12, 12), dtype=np.uint8)
            image_rel = "specimens/01-0101-lazy/working/image.ome.zarr"
            image_meta = write_volume_sidecar(root / "lazy_edit" / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-lazy", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()

            widget = TifWorkbenchWidget(manager)
            try:
                self.assertIsNone(widget.edit_volume)
                self.assertEqual(widget.project.get_specimen("01-0101-lazy")["labels"]["working_edit"]["path"], "")

                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget.current_material_id = 7
                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)

                specimen = widget.project.get_specimen("01-0101-lazy")
                self.assertIsInstance(widget.edit_volume, np.memmap)
                self.assertNotEqual(specimen["labels"]["working_edit"]["path"], "")
                self.assertTrue(widget.working_edit_dirty)
                widget.save_working_edit()

                edit_path = root / "lazy_edit" / specimen["labels"]["working_edit"]["path"] / "array.npy"
                saved = np.load(edit_path)
                self.assertGreater(int(saved.sum()), 0)
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
            self.assertEqual(widget.btn_import_external_prediction_tif.text(), "Import external label TIF to draft")
            self.assertEqual(widget.auto_save_check.text(), "Auto-save edit")
            self.assertTrue(widget.auto_save_check.isChecked())
            self.assertEqual(widget.btn_start_center.text(), "Start Center")
            self.assertEqual(widget.btn_ask_agent.text(), "Ask Agent")
            self.assertEqual(widget.display_mode_combo.currentData(), "slice")
            self.assertEqual(widget.btn_reset_volume_view.text(), "Reset 3D view")
            self.assertIsNotNone(widget.findChild(type(widget.btn_export_training), "tifExportTrainingButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_start_center), "tifStartCenterButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_ask_agent), "tifAskAgentButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_import_tif), "tifImportStackButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_import_amira), "tifImportAmiraButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_prepare_dataset), "tifPrepareDatasetButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_train_backend), "tifTrainBackendButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_import_prediction), "tifImportPredictionButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_import_external_prediction_tif), "tifImportExternalPredictionTifButton"))
            self.assertIsNotNone(widget.findChild(type(widget.auto_save_check), "tifAutoSaveEditCheck"))
            self.assertIsNotNone(widget.findChild(type(widget.display_mode_combo), "tifDisplayModeCombo"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_cutoff_slider), "tifVolumeCutoffSlider"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_quality_slider), "tifVolumeQualitySlider"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_sample_slider), "tifVolumeSampleSlider"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_inside_slider), "tifVolumeInsideSlider"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_clip_slider), "tifVolumeClipSlider"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_reset_volume_view), "tifResetVolumeViewButton"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_clarity_check), "tifVolumeClarityCheck"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifVolumeCanvas"))
            self.assertEqual(widget.volume_quality_slider.maximum(), 4096)
            self.assertEqual(widget.volume_sample_slider.maximum(), 4096)
            self.assertEqual(widget.volume_inside_slider.maximum(), 160)
            self.assertEqual(widget.backend_id_edit.objectName(), "tifBackendIdEdit")
            self.assertEqual(widget.backend_formats_edit.text(), "ome_tiff,nrrd,mha,nifti")
            self.assertEqual(widget.training_status_label.objectName(), "tifTrainingStatusText")
            self.assertEqual(widget.log_console.objectName(), "tifLogConsole")
            inspector_body = widget.findChild(QWidget, "tifInspectorBody")
            self.assertIsNotNone(inspector_body)
            self.assertIs(inspector_body, widget.log_console.parentWidget().parentWidget())
            self.assertIsNone(widget.findChild(QWidget, "tifStatusSection"))
            self.assertEqual(widget.btn_import_tif.property("tifRole"), "primary")
            self.assertEqual(widget.btn_train_backend.property("tifRole"), "primary")
            self.assertEqual(widget.btn_save_backend.property("tifRole"), "secondary")
            self.assertEqual(widget.btn_delete_material.property("tifRole"), "danger")
            self.assertGreaterEqual(widget.btn_import_tif.minimumHeight(), 34)
            self.assertEqual(widget.specimen_list.objectName(), "tifSpecimenList")
            self.assertEqual(widget.material_table.objectName(), "tifMaterialTable")
            self.assertIsNotNone(widget.findChild(QTextEdit, "tifLogConsole"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_ask_agent), "tifAskAgentButton"))
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_ask_agent_context_includes_tif_view_and_brain_reslice_focus(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                specimen = widget.project.get_specimen(widget.current_specimen_id)
                specimen["working_volume"]["spacing_zyx"] = [2.0, 0.5, 0.5]
                widget.display_mode = "volume"
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                y_index = widget.slice_axis_combo.findData("y")
                widget.slice_axis_combo.setCurrentIndex(y_index)
                widget.slice_slider.setValue(2)
                widget.volume_quality_slider.setValue(2048)
                widget.volume_sample_slider.setValue(2048)
                widget.volume_cutoff_slider.setValue(22)
                widget.volume_clarity_check.setChecked(True)
                widget.volume_inside_slider.setValue(65)
                widget.volume_clip_slider.setValue(30)

                context = widget.get_agent_context()

                self.assertEqual(context["source_workbench"], "tif_volume")
                self.assertEqual(context["display_mode"], "volume")
                self.assertEqual(context["active_slice_axis"], "y")
                self.assertIn("/", context["active_slice_position"])
                self.assertEqual(context["active_volume_shape_zyx"], "5/8/8")
                self.assertEqual(context["active_volume_spacing_zyx"], "2.0/0.5/0.5")
                self.assertEqual(context["active_label_shape_zyx"], "5/8/8")
                self.assertEqual(context["volume_density_cutoff"], "22%")
                self.assertEqual(context["volume_texture_target_dim"], "2048")
                self.assertEqual(context["volume_ray_samples"], "2048")
                self.assertEqual(context["volume_clarity_mode"], "on")
                self.assertEqual(context["volume_inside_depth"], "65%")
                self.assertEqual(context["volume_front_cut"], "30%")
                self.assertIn("yaw=", context["volume_yaw_pitch"])
                self.assertIn("brain_orientation_reslice", context["tif_next_requirement"])
                self.assertIn("TIF脑部统一朝向重切片需求_zh.md", context["tif_requirement_doc"])
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_right_panel_controls_ignore_mouse_wheel_changes(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            controls = [
                widget.display_mode_combo,
                widget.slice_axis_combo,
                widget.label_role_combo,
                widget.opacity_slider,
                widget.brightness_slider,
                widget.contrast_slider,
                widget.volume_cutoff_slider,
                widget.volume_quality_slider,
                widget.volume_sample_slider,
                widget.volume_inside_slider,
                widget.volume_clip_slider,
                widget.brush_size_slider,
                widget.slice_slider,
            ]
            before = [
                control.currentIndex() if hasattr(control, "currentIndex") else control.value()
                for control in controls
            ]
            for control in controls:
                event = FakeWheelEvent(120)
                control.wheelEvent(event)
                self.assertTrue(event.ignored)
            after = [
                control.currentIndex() if hasattr(control, "currentIndex") else control.value()
                for control in controls
            ]
            self.assertEqual(before, after)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_canvas_wheel_and_arrow_keys_page_slices(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                self.assertEqual(widget.slice_slider.value(), 0)

                wheel_down = FakeWheelEvent(-120)
                widget.canvas.wheelEvent(wheel_down)
                self.assertTrue(wheel_down.accepted)
                self.assertEqual(widget.slice_slider.value(), 1)

                right = FakeKeyEvent(Qt.Key_Right)
                widget.canvas.keyPressEvent(right)
                self.assertTrue(right.accepted)
                self.assertEqual(widget.slice_slider.value(), 2)

                left = FakeKeyEvent(Qt.Key_Left)
                widget.canvas.keyPressEvent(left)
                self.assertTrue(left.accepted)
                self.assertEqual(widget.slice_slider.value(), 1)

                wheel_up = FakeWheelEvent(120)
                widget.canvas.wheelEvent(wheel_up)
                self.assertEqual(widget.slice_slider.value(), 0)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_canvas_zoom_pan_and_slice_change_reset_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=3)
            try:
                up = FakeKeyEvent(Qt.Key_Up)
                widget.canvas.keyPressEvent(up)
                self.assertTrue(up.accepted)
                self.assertGreater(widget.canvas.zoom_factor(), 1.0)

                press = FakeMouseEvent(Qt.RightButton, Qt.RightButton, 220, 170)
                move = FakeMouseEvent(Qt.RightButton, Qt.RightButton, 260, 190)
                release = FakeMouseEvent(Qt.RightButton, Qt.NoButton, 260, 190)
                widget.canvas.mousePressEvent(press)
                widget.canvas.mouseMoveEvent(move)
                widget.canvas.mouseReleaseEvent(release)
                self.assertTrue(press.accepted)
                self.assertTrue(move.accepted)
                self.assertTrue(release.accepted)
                self.assertNotEqual((widget.canvas._pan_x, widget.canvas._pan_y), (0.0, 0.0))

                widget.move_slice(1)
                self.assertEqual(widget.slice_slider.value(), 1)
                self.assertEqual(widget.canvas.zoom_factor(), 1.0)
                self.assertEqual((widget.canvas._pan_x, widget.canvas._pan_y), (0.0, 0.0))
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_tif_workbench_can_view_z_y_x_orthogonal_slices(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                self.assertEqual(widget.slice_axis_combo.currentData(), "z")
                self.assertEqual(widget.slice_slider.maximum(), 3)

                y_index = widget.slice_axis_combo.findData("y")
                widget.slice_axis_combo.setCurrentIndex(y_index)
                self.assertEqual(widget.slice_slider.maximum(), 7)
                self.assertIn("Y ", widget.canvas_status_text(1.0))
                widget.slice_slider.setValue(4)
                widget.render_current_slice()
                self.assertEqual(widget.canvas._pixmap.width(), 8)
                self.assertEqual(widget.canvas._pixmap.height(), 4)

                x_index = widget.slice_axis_combo.findData("x")
                widget.slice_axis_combo.setCurrentIndex(x_index)
                self.assertEqual(widget.slice_slider.maximum(), 7)
                widget.slice_slider.setValue(5)
                widget.render_current_slice()
                self.assertEqual(widget.canvas._pixmap.width(), 8)
                self.assertEqual(widget.canvas._pixmap.height(), 4)

                z_index = widget.slice_axis_combo.findData("z")
                widget.slice_axis_combo.setCurrentIndex(z_index)
                self.assertEqual(widget.slice_slider.maximum(), 3)
                self.assertEqual(widget.canvas._pixmap.width(), 8)
                self.assertEqual(widget.canvas._pixmap.height(), 8)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_side_angle_slices_are_read_only_for_label_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=3)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget.current_material_id = 2
                before = widget.edit_volume.copy()

                y_index = widget.slice_axis_combo.findData("y")
                widget.slice_axis_combo.setCurrentIndex(y_index)
                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)

                np.testing.assert_array_equal(widget.edit_volume, before)
                self.assertIn("Painting is available on Z slices only", widget.training_status_label.text())
                self.assertFalse(widget.working_edit_dirty)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_tif_workbench_can_render_drag_rotate_volume_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                mode_index = widget.display_mode_combo.findData("volume")
                widget.display_mode_combo.setCurrentIndex(mode_index)

                self.assertEqual(widget.display_mode, "volume")
                self.assertEqual(widget.view_stack.currentWidget(), widget.volume_canvas)
                self.assertFalse(widget.slice_slider.isVisible())
                self.assertIn("3D preview uses a downsampled", widget.training_status_label.text())
                self.assertIsNotNone(widget._volume_preview)
                if isinstance(widget.volume_canvas, TifVolumeCanvas):
                    self.assertIsNotNone(widget.volume_canvas.pixmap())
                self.assertIn("3D volume", widget.volume_status_text())
                self.assertIn(
                    "GPU ray march" if widget._volume_canvas_renderer == "gpu" else "CPU fallback",
                    widget.volume_status_text(),
                )
                widget._volume_canvas_renderer = "gpu"
                widget._volume_gl_renderer_info = "NVIDIA GeForce RTX 3090/PCIe/SSE2"
                widget.volume_quality_slider.setValue(4096)
                widget.volume_sample_slider.setValue(4096)
                widget.volume_clarity_check.setChecked(True)
                widget.volume_inside_slider.setValue(65)
                widget.volume_clip_slider.setValue(30)
                self.assertIn("RTX 3090", widget.volume_status_text())
                self.assertIn("Volume view | GPU ray march [", widget.volume_canvas_overlay_text())
                self.assertIn("Still high quality", widget.volume_canvas_overlay_text())
                self.assertIn("Texture 4096", widget.volume_canvas_overlay_text())
                self.assertIn("Samples 4096", widget.volume_canvas_overlay_text())
                self.assertIn("Inside 65%", widget.volume_canvas_overlay_text())
                self.assertIn("Cut 30%", widget.volume_canvas_overlay_text())
                self.assertIn("drag rotate / wheel zoom", widget.volume_status_text())
                self.assertIn("Pan X 0%", widget.volume_canvas_overlay_text())
                self.assertNotIn("render_quality", widget.volume_canvas_overlay_text())
                widget.change_language("zh")
                self.assertIn("体预览 | GPU 光线步进 [", widget.volume_canvas_overlay_text())
                self.assertIn("静止高清", widget.volume_canvas_overlay_text())
                self.assertEqual(widget.volume_clarity_check.text(), "清晰模式")
                self.assertIn("纹理 4096", widget.volume_canvas_overlay_text())
                self.assertIn("采样 4096", widget.volume_canvas_overlay_text())
                self.assertIn("视点 65%", widget.volume_canvas_overlay_text())
                self.assertIn("近端切 30%", widget.volume_canvas_overlay_text())
                self.assertIn("左键旋转", widget.volume_status_text())
                self.assertIn("右键平移", widget.volume_status_text())
                self.assertIn("横移 0%", widget.volume_canvas_overlay_text())
                self.assertIn("纵移 0%", widget.volume_canvas_overlay_text())
                self.assertIn("静止高清", widget.volume_quality_slider.toolTip())
                widget._update_volume_render_status_label()
                self.assertIn("RTX 3090", widget.volume_render_status_label.text())

                old_yaw = widget._volume_yaw
                widget.rotate_volume_preview(25, -10)
                self.assertNotEqual(widget._volume_yaw, old_yaw)
                self.assertEqual(widget._volume_render_mode, "drag")
                self.assertIn("拖动预览", widget.volume_canvas_overlay_text())
                self.assertIn("纹理 640", widget.volume_canvas_overlay_text())
                self.assertIn("采样 768", widget.volume_canvas_overlay_text())
                widget._finish_volume_interaction()
                self.assertEqual(widget._volume_render_mode, "still")

                old_pan = (widget._volume_pan_x, widget._volume_pan_y)
                widget.pan_volume_preview(80, -40)
                self.assertNotEqual((widget._volume_pan_x, widget._volume_pan_y), old_pan)
                self.assertGreater(widget._volume_pan_x, old_pan[0])
                self.assertGreater(widget._volume_pan_y, old_pan[1])
                self.assertEqual(widget._volume_render_mode, "drag")
                self.assertIn("横移", widget.volume_canvas_overlay_text())
                self.assertIn("纵移", widget.volume_canvas_overlay_text())
                widget.volume_canvas.resize(480, 360)
                press = FakeMouseEvent(Qt.RightButton, Qt.RightButton, 220, 170)
                move = FakeMouseEvent(Qt.RightButton, Qt.RightButton, 260, 140)
                release = FakeMouseEvent(Qt.RightButton, Qt.NoButton, 260, 140)
                widget.volume_canvas.mousePressEvent(press)
                widget.volume_canvas.mouseMoveEvent(move)
                widget.volume_canvas.mouseReleaseEvent(release)
                self.assertTrue(press.accepted)
                self.assertTrue(move.accepted)
                self.assertTrue(release.accepted)

                old_zoom = widget._volume_zoom
                widget.zoom_volume_preview(1)
                self.assertGreater(widget._volume_zoom, old_zoom)
                for _ in range(20):
                    widget.zoom_volume_preview(1)
                self.assertEqual(widget._volume_zoom, 8.0)
                widget._finish_volume_interaction()

                widget.reset_volume_view()
                self.assertEqual(widget._volume_yaw, -35.0)
                self.assertEqual(widget._volume_pitch, 20.0)
                self.assertEqual(widget._volume_zoom, 1.0)
                self.assertEqual(widget._volume_pan_x, 0.0)
                self.assertEqual(widget._volume_pan_y, 0.0)
                self.assertEqual(widget.volume_inside_slider.value(), 0)
                self.assertEqual(widget.volume_clip_slider.value(), 0)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_volume_preview_cache_keeps_drag_and_still_textures_separate(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget.image_volume = np.zeros((12, 900, 900), dtype=np.uint8)
            widget.image_volume[:, 250:650, 250:650] = 180
            widget.volume_quality_slider.setValue(1024)
            still = widget._ensure_volume_preview("still")
            drag = widget._ensure_volume_preview("drag")
            self.assertIsNotNone(still)
            self.assertIsNotNone(drag)
            self.assertLessEqual(max(drag.shape), 640)
            self.assertLessEqual(max(still.shape), 1024)
            self.assertGreaterEqual(max(still.shape), max(drag.shape))
            self.assertEqual(len(widget._volume_preview_cache), 2)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_volume_source_geometry_stays_fixed_across_preview_sizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("geometry", root / "geometry")
            manager.create_specimen_scaffold("01-0101-geo")
            image = np.zeros((12, 900, 900), dtype=np.uint8)
            image_rel = "specimens/01-0101-geo/working/image.ome.zarr"
            image_meta = write_volume_sidecar(root / "geometry" / image_rel, image, role="working_image")
            manager.register_working_volume(
                "01-0101-geo",
                image_rel,
                image_meta["shape_zyx"],
                image_meta["dtype"],
                spacing_zyx=[2.0, 1.0, 1.0],
                save=False,
            )
            manager.save_project()
            widget = TifWorkbenchWidget(manager, "zh")
            try:
                widget.load_specimen("01-0101-geo")
                widget._volume_canvas_renderer = "gpu"
                widget.volume_quality_slider.setValue(1024)
                still = widget._ensure_volume_preview("still")
                drag = widget._ensure_volume_preview("drag")
                self.assertNotEqual(still.shape, drag.shape)
                shape, spacing = widget._volume_source_geometry()
                self.assertEqual(shape, (12, 900, 900))
                self.assertEqual(spacing, (2.0, 1.0, 1.0))
            finally:
                still = None
                drag = None
                widget.close_project()
                widget.deleteLater()

    def test_volume_preview_keeps_uint8_source_without_float_copy(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        try:
            source = np.arange(2 * 4 * 4, dtype=np.uint8).reshape((2, 4, 4))
            preview = widget._normalize_volume_preview_to_uint8(source)
            self.assertEqual(preview.dtype, np.uint8)
            np.testing.assert_array_equal(preview, source)
            self.assertTrue(preview.flags["C_CONTIGUOUS"])
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_volume_preview_normalizes_uint16_source_for_gpu_upload(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        try:
            source = np.array([[[0, 32768], [49152, 65535]]], dtype=np.uint16)
            preview = widget._normalize_volume_preview_to_uint8(source)
            self.assertEqual(preview.dtype, np.uint8)
            self.assertEqual(int(preview.min()), 0)
            self.assertEqual(int(preview.max()), 255)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_clarity_mode_preserves_uint16_preview_for_gpu_upload(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget.image_volume = np.array([[[0, 32768], [49152, 65535]]], dtype=np.uint16)
            widget.volume_clarity_check.setChecked(True)
            preview = widget._ensure_volume_preview("still")
            self.assertEqual(preview.dtype, np.uint16)
            np.testing.assert_array_equal(preview, widget.image_volume)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_volume_preview_is_read_only_for_label_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=3)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget.current_material_id = 2
                before = widget.edit_volume.copy()

                mode_index = widget.display_mode_combo.findData("volume")
                widget.display_mode_combo.setCurrentIndex(mode_index)
                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)

                np.testing.assert_array_equal(widget.edit_volume, before)
                self.assertIn("3D volume preview is read-only", widget.training_status_label.text())
                self.assertFalse(widget.working_edit_dirty)
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
            self.assertEqual(widget.btn_import_external_prediction_tif.text(), "导入外部标签 TIF 到草稿")
            self.assertEqual(widget.auto_save_check.text(), "自动保存编辑层")
            self.assertEqual(widget.btn_start_center.text(), "启动中心")
            self.assertEqual(widget.btn_ask_agent.text(), "询问 Agent")
            self.assertEqual(widget.display_mode_label.text(), "显示模式")
            self.assertEqual(widget.display_mode_combo.itemText(widget.display_mode_combo.findData("volume")), "三维体预览")
            self.assertEqual(widget.slice_axis_label.text(), "切片方向")
            self.assertEqual(widget.slice_axis_combo.itemText(widget.slice_axis_combo.findData("y")), "Y 方向切片")
            section_titles = {
                label.text()
                for label in widget.findChildren(QLabel)
                if label.objectName() == "tifSectionTitle"
            }
            self.assertIn("模型训练", section_titles)
            self.assertIn("模型配置", section_titles)
            self.assertIn("工作台日志", section_titles)
            self.assertEqual(widget.label_role_combo.itemText(widget.label_role_combo.findData("manual_truth")), "人工真值")
            self.assertIn("只读基准层", widget.label_role_help_label.text())
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_tif_volume_canvas_factory_reports_gpu_or_cpu_renderer(self):
        canvas, renderer, warning = create_tif_volume_canvas()
        try:
            self.assertIn(renderer, {"gpu", "cpu"})
            self.assertEqual(canvas.objectName(), "tifVolumeCanvas")
            if renderer == "gpu":
                self.assertTrue(gpu_volume_canvas_available())
                self.assertEqual(warning, "")
            else:
                self.assertIsInstance(canvas, TifVolumeCanvas)
                self.assertIsInstance(warning, str)
        finally:
            canvas.deleteLater()

    def test_gpu_volume_unavailable_reason_is_safe_to_call(self):
        reason = gpu_volume_unavailable_reason()
        self.assertIsInstance(reason, str)

    def test_tif_workbench_releases_optional_gpu_renderer_on_close(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuCanvas(TifVolumeCanvas):
            def __init__(self):
                super().__init__()
                self.release_calls = 0

            def release_gl_resources(self):
                self.release_calls += 1

        fake_canvas = FakeGpuCanvas()
        try:
            widget.volume_canvas = fake_canvas
            self.assertTrue(widget.close_project(prompt_unsaved=False))
            self.assertEqual(fake_canvas.release_calls, 1)
        finally:
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_label_role_help_explains_editable_and_read_only_layers(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        try:
            manual_index = widget.label_role_combo.findData("manual_truth")
            edit_index = widget.label_role_combo.findData("working_edit")
            draft_index = widget.label_role_combo.findData("model_draft")

            widget.label_role_combo.setCurrentIndex(manual_index)
            self.assertIn("只读基准层", widget.label_role_help_label.text())

            widget.label_role_combo.setCurrentIndex(edit_index)
            self.assertIn("可写的工作副本", widget.label_role_help_label.text())

            widget.label_role_combo.setCurrentIndex(draft_index)
            self.assertIn("只读的预测候选", widget.label_role_help_label.text())
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_painting_is_blocked_on_read_only_label_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=2)
            try:
                edit_before = widget.edit_volume.copy()
                draft_index = widget.label_role_combo.findData("model_draft")
                widget.label_role_combo.setCurrentIndex(draft_index)
                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)

                np.testing.assert_array_equal(widget.edit_volume, edit_before)
                self.assertIn("Cannot paint on model draft", widget.training_status_label.text())

                manual_index = widget.label_role_combo.findData("manual_truth")
                widget.label_role_combo.setCurrentIndex(manual_index)
                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)

                np.testing.assert_array_equal(widget.edit_volume, edit_before)
                self.assertIn("Cannot paint on this label layer", widget.training_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_auto_save_writes_working_edit_after_brush_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=2)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget.current_material_id = 2
                widget.brush_size_slider.setValue(1)
                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)

                self.assertTrue(widget.working_edit_dirty)
                self.assertTrue(widget.auto_save_timer.isActive())
                widget.auto_save_timer.stop()
                self.assertTrue(widget.save_working_edit(show_message=True, reason="auto_save"))

                specimen = widget.project.get_specimen("01-0101-21")
                edit_path = root / "viewer" / specimen["labels"]["working_edit"]["path"] / "array.npy"
                saved = np.load(edit_path)
                self.assertGreater(int(saved.sum()), 0)
                self.assertFalse(widget.working_edit_dirty)
                self.assertIn("Auto-saved working edit.", widget.training_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_unsaved_working_edit_prompt_can_cancel_close_and_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=2)
            try:
                widget.auto_save_check.setChecked(False)
                widget.working_edit_dirty = True
                module_path = "AntSleap.ui.tif_workbench.QMessageBox"
                with patch(f"{module_path}.question", return_value=QMessageBox.Cancel):
                    self.assertFalse(widget.close_project(prompt_unsaved=True))
                    self.assertTrue(widget.working_edit_dirty)
                    self.assertEqual(widget.current_specimen_id, "01-0101-21")

                with patch(f"{module_path}.question", return_value=QMessageBox.Save):
                    with patch.object(widget, "save_working_edit", return_value=True) as save_mock:
                        self.assertTrue(widget._confirm_discard_or_save_working_edit())
                        save_mock.assert_called_once()
            finally:
                widget.working_edit_dirty = False
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
