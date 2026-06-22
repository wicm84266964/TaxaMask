import os
import sys
import tempfile
import unittest
import json
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
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QTextEdit, QWidget
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from PySide6.QtWidgets import QTreeWidget

    from AntSleap.core.tif_part_extraction import add_polygon_keyframe, crop_volume_to_part, read_contours_json, write_contours_json
    from AntSleap.core.tif_materials import upsert_material
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.core.tif_volume_io import write_volume_sidecar
    from AntSleap.core.tif_local_axis_reslice import compute_local_frame, export_part_reslice
    from AntSleap.core.tif_local_axis_ai import LOCAL_AXIS_MODEL_MANIFEST_SCHEMA_VERSION
    from AntSleap.ui.tif_gpu_volume_canvas import gpu_volume_canvas_available, gpu_volume_offscreen_available, gpu_volume_unavailable_reason
    from AntSleap.ui.tif_local_axis_model_panel import TifLocalAxisModelPanel
    from AntSleap.ui.tif_local_axis_reslice_page import TifLocalAxisResliceDialog, TifLocalAxisSlicePickerDialog
    from AntSleap.ui.tif_local_axis_review_queue import TifLocalAxisReviewQueueWidget
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

    def ignore(self):
        self.ignored = True


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


class FakePartNameDialog:
    queue = []

    def __init__(self, *args, **kwargs):
        if not self.queue:
            raise AssertionError("FakePartNameDialog.queue is empty")
        self._part_id, self._display_name, self._accepted = self.queue.pop(0)

    def exec(self):
        return 1 if self._accepted else 0

    def values(self):
        return self._part_id, self._display_name


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

    def _make_local_axis_panel_project(self, root, project_name="local_axis_panel"):
        manager = TifProjectManager()
        project_root = root / project_name
        manager.create_project(project_name, project_root)
        manager.create_specimen_scaffold("01-0101-local-axis")
        image = np.arange(4 * 6 * 8, dtype=np.uint8).reshape((4, 6, 8))
        image_rel = "specimens/01-0101-local-axis/working/image.ome.zarr"
        image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image")
        manager.register_working_volume("01-0101-local-axis", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
        manager.save_project()
        crop_volume_to_part(manager, "01-0101-local-axis", "head", [[1, 3], [2, 6], [1, 5]], display_name="Head")
        frame = compute_local_frame(
            [0.5, 1.5, 1.5],
            [0.0, 1.5, 1.5],
            [1.0, 1.5, 1.5],
            roll_reference={
                "point_a": {"role": "left_eye", "zyx": [0.5, 1.0, 1.0]},
                "point_b": {"role": "right_eye", "zyx": [0.5, 2.0, 1.0]},
            },
        )
        export_part_reslice(
            manager,
            "01-0101-local-axis",
            "head",
            {
                "reslice_id": "head_axis_training",
                "template_id": "head",
                "local_frame": frame,
                "training": {"human_confirmed": True, "usable_for_training": True},
            },
        )
        return manager

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

    def test_specimen_tree_loads_full_and_part_volumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("part_viewer", root / "part_viewer")
            manager.create_specimen_scaffold(
                "01-0101-part",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 2, "name": "brain", "display_name": "Brain", "color": "#ff0000", "trainable": True},
                    ]
                },
            )
            image = np.arange(4 * 6 * 8, dtype=np.uint8).reshape((4, 6, 8))
            image_rel = "specimens/01-0101-part/working/image.ome.zarr"
            image_meta = write_volume_sidecar(root / "part_viewer" / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-part", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-part", "head", [[1, 3], [2, 6], [1, 5]], display_name="Head")

            widget = TifWorkbenchWidget(manager, "en")
            try:
                self.assertIsInstance(widget.specimen_list, QTreeWidget)
                self.assertEqual(widget.specimen_list.count(), 1)
                root_item = widget.specimen_list.topLevelItem(0)
                self.assertEqual(root_item.childCount(), 2)

                widget._select_volume_tree_item("01-0101-part", "part", "head")

                self.assertEqual(widget.current_volume_scope, "part")
                self.assertEqual(widget.current_part_id, "head")
                self.assertEqual(tuple(widget.image_volume.shape), (2, 4, 4))
                self.assertIn("Part volume", widget.status_label.text())
                self.assertIn("Parent bbox", widget.metadata_label.text())

                widget._select_volume_tree_item("01-0101-part", "full", "")
                self.assertEqual(widget.current_volume_scope, "full")
                self.assertEqual(tuple(widget.image_volume.shape), (4, 6, 8))
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_specimen_tree_groups_part_reslices_under_part(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("reslice_tree", root / "reslice_tree")
            manager.create_specimen_scaffold(
                "01-0101-reslice",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 2, "name": "brain", "display_name": "Brain", "color": "#ff0000", "trainable": True},
                    ]
                },
            )
            image = np.arange(4 * 6 * 8, dtype=np.uint8).reshape((4, 6, 8))
            image_rel = "specimens/01-0101-reslice/working/image.ome.zarr"
            image_meta = write_volume_sidecar(root / "reslice_tree" / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-reslice", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-reslice", "head", [[1, 3], [2, 6], [1, 5]], display_name="Head")
            frame = compute_local_frame(
                [0.5, 1.5, 1.5],
                [0.0, 1.5, 1.5],
                [1.0, 1.5, 1.5],
                roll_reference={
                    "point_a": {"role": "left_eye", "zyx": [0.5, 1.0, 1.0]},
                    "point_b": {"role": "right_eye", "zyx": [0.5, 2.0, 1.0]},
                },
            )
            export_part_reslice(
                manager,
                "01-0101-reslice",
                "head",
                {"reslice_id": "head_axis_001", "template_id": "head", "local_frame": frame},
            )

            widget = TifWorkbenchWidget(manager, "en")
            try:
                root_item = widget.specimen_list.topLevelItem(0)
                part_item = root_item.child(1)
                self.assertEqual(part_item.childCount(), 1)
                reslices_item = part_item.child(0)
                self.assertEqual(reslices_item.text(0), "Reslices")
                self.assertEqual(reslices_item.childCount(), 1)
                self.assertIn("head_axis_001", reslices_item.child(0).text(0))

                widget.specimen_list.setCurrentItem(reslices_item.child(0))

                self.assertEqual(widget.current_volume_scope, "part")
                self.assertEqual(widget.current_part_id, "head")
                self.assertEqual(widget.current_reslice_id, "head_axis_001")
                self.assertEqual(tuple(widget.image_volume.shape), (2, 4, 4))
                self.assertIn("Reslice ID: head_axis_001", widget.metadata_label.text())
                self.assertIn("Metadata:", widget.metadata_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_local_axis_reslice_dialog_exports_and_refreshes_tree_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("local_axis_dialog", root / "local_axis_dialog")
            manager.create_specimen_scaffold(
                "01-0101-dialog",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 2, "name": "brain", "display_name": "Brain", "color": "#ff0000", "trainable": True},
                    ]
                },
            )
            image = np.arange(4 * 6 * 8, dtype=np.uint8).reshape((4, 6, 8))
            image_rel = "specimens/01-0101-dialog/working/image.ome.zarr"
            image_meta = write_volume_sidecar(root / "local_axis_dialog" / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-dialog", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-dialog", "head", [[1, 3], [2, 6], [1, 5]], display_name="Head")

            dialog = TifLocalAxisResliceDialog(manager, "01-0101-dialog", "head", lang="en")
            try:
                dialog.reslice_id_edit.setText("head_axis_dialog")
                dialog.roll_a_point_edit.setText("0.5,1,1")
                dialog.roll_b_point_edit.setText("0.5,2,1")
                payload = dialog.build_reslice_payload()

                self.assertEqual(payload["reslice_id"], "head_axis_dialog")
                self.assertEqual(payload["template_id"], "head")
                self.assertEqual(payload["editable_axis"]["role"], "editable_output_axis")
                self.assertEqual(payload["editable_axis"]["source_axis_id"], "source_z_axis")
                self.assertEqual(dialog.roll_a_role_edit.text(), "roll_point_a")
                self.assertEqual(dialog.roll_b_role_edit.text(), "roll_point_b")
                self.assertTrue(payload["training"]["human_confirmed"])
                dialog.picker_axis_combo.setCurrentIndex(dialog.picker_axis_combo.findData("z"))
                dialog.picker_slice_slider.setValue(0)
                dialog.picker_target_combo.setCurrentIndex(dialog.picker_target_combo.findData("origin"))
                dialog._set_picker_point(2.0, 1.0)
                self.assertEqual(dialog.origin_edit.text(), "0,1,2")
                signal_result = dialog.compute_source_signal()
                self.assertIsNotNone(signal_result)
                self.assertIn("Auxiliary navigation only", dialog.source_signal_summary.text())
                result = dialog.export_reslice()

                self.assertIsNotNone(result)
                self.assertEqual(manager.list_part_reslices("01-0101-dialog", "head")[0]["reslice_id"], "head_axis_dialog")
            finally:
                dialog.deleteLater()

    @unittest.skipUnless(has_pyside6, "PySide6 not available")
    def test_local_axis_reslice_dialog_has_large_mpr_picker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("local_axis_large_mpr", root / "local_axis_large_mpr")
            manager.create_specimen_scaffold("01-0101-large-mpr")
            image = np.arange(4 * 6 * 8, dtype=np.uint8).reshape((4, 6, 8))
            image_rel = "specimens/01-0101-large-mpr/working/image.ome.zarr"
            image_meta = write_volume_sidecar(root / "local_axis_large_mpr" / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-large-mpr", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-large-mpr", "head", [[1, 3], [2, 6], [1, 5]], display_name="Head")

            dialog = TifLocalAxisResliceDialog(manager, "01-0101-large-mpr", "head", lang="en")
            picker = TifLocalAxisSlicePickerDialog(dialog)
            try:
                self.assertEqual(dialog.btn_large_mpr.text(), "Open large MPR view")
                self.assertEqual(picker.windowTitle(), "Large MPR point picking")
                self.assertEqual(picker.btn_fullscreen.text(), "Full screen")

                picker.axis_combo.setCurrentIndex(picker.axis_combo.findData("z"))
                picker.slice_slider.setValue(0)
                picker.target_combo.setCurrentIndex(picker.target_combo.findData("origin"))
                picker._set_point(2.0, 1.0)

                self.assertEqual(dialog.origin_edit.text(), "0,1,2")
                self.assertEqual(dialog.picker_target_combo.currentData(), "origin")
            finally:
                picker.deleteLater()
                dialog.deleteLater()

    def test_local_axis_reslice_dialog_requires_accepted_proposal_before_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("local_axis_dialog_proposal", root / "local_axis_dialog_proposal")
            manager.create_specimen_scaffold("01-0101-proposal")
            image = np.arange(4 * 6 * 8, dtype=np.uint8).reshape((4, 6, 8))
            image_rel = "specimens/01-0101-proposal/working/image.ome.zarr"
            image_meta = write_volume_sidecar(root / "local_axis_dialog_proposal" / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-proposal", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-proposal", "head", [[1, 3], [2, 6], [1, 5]], display_name="Head")
            manager.add_local_frame_proposal(
                "01-0101-proposal",
                "head",
                {
                    "frame_proposal_id": "frame_001",
                    "template_id": "head",
                    "origin_zyx": [0.5, 1.5, 1.5],
                    "output_axis_start_zyx": [0.0, 1.5, 1.5],
                    "output_axis_end_zyx": [1.0, 1.5, 1.5],
                    "roll_reference": {
                        "point_a": {"role": "left_eye", "zyx": [0.5, 1.0, 1.0]},
                        "point_b": {"role": "right_eye", "zyx": [0.5, 2.0, 1.0]},
                    },
                    "confidence": 0.8,
                    "status": "proposed",
                },
            )

            dialog = TifLocalAxisResliceDialog(manager, "01-0101-proposal", "head", proposal_id="frame_001", lang="en")
            try:
                dialog.reslice_id_edit.setText("proposal_axis")
                with patch.object(QMessageBox, "warning") as warning:
                    self.assertIsNone(dialog.export_reslice())
                    self.assertTrue(warning.called)
                self.assertEqual(manager.list_part_reslices("01-0101-proposal", "head"), [])

                dialog.update_selected_proposal_status("accepted")
                result = dialog.export_reslice()

                self.assertIsNotNone(result)
                self.assertEqual(manager.list_part_reslices("01-0101-proposal", "head")[0]["reslice_id"], "proposal_axis")
                self.assertEqual(
                    manager.get_local_frame_proposal("01-0101-proposal", "head", "frame_001")["status"],
                    "exported",
                )
                self.assertEqual(result["record"]["provenance"]["source_proposal_id"], "frame_001")
            finally:
                dialog.deleteLater()

    def test_local_axis_reslice_button_is_enabled_for_part_volume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("local_axis_button", root / "local_axis_button")
            manager.create_specimen_scaffold(
                "01-0101-button",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 2, "name": "brain", "display_name": "Brain", "color": "#ff0000", "trainable": True},
                    ]
                },
            )
            image = np.arange(4 * 6 * 8, dtype=np.uint8).reshape((4, 6, 8))
            image_rel = "specimens/01-0101-button/working/image.ome.zarr"
            image_meta = write_volume_sidecar(root / "local_axis_button" / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-button", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-button", "head", [[1, 3], [2, 6], [1, 5]], display_name="Head")

            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget._select_volume_tree_item("01-0101-button", "part", "head")

                self.assertTrue(widget.btn_local_axis_reslice.isEnabled())
                self.assertEqual(widget.btn_local_axis_reslice.text(), "Local Axis Reslice")
                self.assertTrue(widget.btn_local_axis_queue.isEnabled())
                self.assertEqual(widget.btn_local_axis_queue.text(), "Review Local Axis Queue")
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_local_axis_review_queue_updates_status_and_batch_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("local_axis_queue", root / "local_axis_queue")
            manager.create_specimen_scaffold("01-0101-queue")
            image = np.arange(4 * 6 * 8, dtype=np.uint8).reshape((4, 6, 8))
            image_rel = "specimens/01-0101-queue/working/image.ome.zarr"
            image_meta = write_volume_sidecar(root / "local_axis_queue" / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-queue", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-queue", "head", [[1, 3], [2, 6], [1, 5]], display_name="Head")
            manager.add_local_frame_proposal(
                "01-0101-queue",
                "head",
                {
                    "frame_proposal_id": "frame_001",
                    "template_id": "head",
                    "origin_zyx": [0.5, 1.5, 1.5],
                    "output_axis_start_zyx": [0.0, 1.5, 1.5],
                    "output_axis_end_zyx": [1.0, 1.5, 1.5],
                    "roll_reference": {
                        "point_a": {"role": "left_eye", "zyx": [0.5, 1.0, 1.0]},
                        "point_b": {"role": "right_eye", "zyx": [0.5, 2.0, 1.0]},
                    },
                    "confidence": 0.8,
                    "status": "proposed",
                },
            )

            queue = TifLocalAxisReviewQueueWidget(manager, lang="en")
            try:
                self.assertEqual(len(queue.rows), 1)
                queue.table.selectRow(0)
                queue.update_selected_status("accepted")

                self.assertEqual(manager.get_local_frame_proposal("01-0101-queue", "head", "frame_001")["status"], "accepted")
                result = queue.batch_export_accepted()

                self.assertEqual(len(result["exported"]), 1)
                self.assertEqual(manager.list_part_reslices("01-0101-queue", "head")[0]["reslice_id"], "frame_001_reslice")
            finally:
                queue.deleteLater()

    def test_local_axis_review_queue_filters_sorts_and_emits_open_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("local_axis_queue_filters", root / "local_axis_queue_filters")
            manager.create_specimen_scaffold("01-0101-queue-filter")
            image = np.arange(4 * 6 * 8, dtype=np.uint8).reshape((4, 6, 8))
            image_rel = "specimens/01-0101-queue-filter/working/image.ome.zarr"
            image_meta = write_volume_sidecar(root / "local_axis_queue_filters" / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-queue-filter", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-queue-filter", "head", [[1, 3], [2, 6], [1, 5]], display_name="Head")
            for proposal_id, confidence, version, flags in (
                ("frame_high", 0.8, "v1", []),
                ("frame_low", 0.2, "v2", ["twisted_pose"]),
            ):
                manager.add_local_frame_proposal(
                    "01-0101-queue-filter",
                    "head",
                    {
                        "frame_proposal_id": proposal_id,
                        "template_id": "head",
                        "origin_zyx": [0.5, 1.5, 1.5],
                        "output_axis_start_zyx": [0.0, 1.5, 1.5],
                        "output_axis_end_zyx": [1.0, 1.5, 1.5],
                        "confidence": confidence,
                        "model_version": version,
                        "hard_case_flags": flags,
                    },
                )

            queue = TifLocalAxisReviewQueueWidget(manager, lang="en")
            opened = []
            try:
                queue.sort_combo.setCurrentIndex(queue.sort_combo.findData("confidence_asc"))
                queue.refresh()
                self.assertEqual(queue.rows[0]["proposal_id"], "frame_low")

                queue.model_version_filter_edit.setCurrentText("v2")
                queue.hard_flag_filter_edit.setCurrentText("twisted_pose")
                queue.refresh()
                self.assertEqual([row["proposal_id"] for row in queue.rows], ["frame_low"])

                queue.open_proposal_requested.connect(lambda specimen_id, part_id, proposal_id: opened.append((specimen_id, part_id, proposal_id)))
                queue.table.selectRow(0)
                row = queue.open_selected_proposal()

                self.assertEqual(row["proposal_id"], "frame_low")
                self.assertEqual(opened, [("01-0101-queue-filter", "head", "frame_low")])
            finally:
                queue.deleteLater()

    def test_local_axis_model_panel_exports_imports_and_registers_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._make_local_axis_panel_project(root)
            panel = TifLocalAxisModelPanel(manager, lang="en", specimen_id="01-0101-local-axis", part_id="head")
            try:
                export = panel.export_training_manifest_to_dir(root / "training_export")

                self.assertEqual(export["sample_count"], 1)
                self.assertEqual(export["manifest"]["samples"][0]["reslice_id"], "head_axis_training")

                proposal_path = root / "local_frame_proposals.json"
                proposal_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "taxamask_tif_local_axis_frame_proposals_v1",
                            "proposals": [
                                {
                                    "frame_proposal_id": "frame_from_panel",
                                    "specimen_id": "01-0101-local-axis",
                                    "part_id": "head",
                                    "template_id": "head",
                                    "origin_zyx": [0.5, 1.5, 1.5],
                                    "output_axis_start_zyx": [0.0, 1.5, 1.5],
                                    "output_axis_end_zyx": [1.0, 1.5, 1.5],
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                imported = panel.import_local_frame_proposals_file(proposal_path)

                self.assertEqual(len(imported["local_frame_proposals"]), 1)
                self.assertEqual(
                    manager.list_local_frame_proposals("01-0101-local-axis", "head")[0]["frame_proposal_id"],
                    "frame_from_panel",
                )

                manifest_path = root / "local_axis_model_manifest.json"
                manifest_path.write_text(
                    json.dumps(
                        {
                            "schema_version": LOCAL_AXIS_MODEL_MANIFEST_SCHEMA_VERSION,
                            "model_id": "external_local_axis/head_frame_panel_v1",
                            "model_version": "v1",
                            "backend_id": "external_local_axis",
                            "template_id": "head",
                            "model_type": "local_frame",
                        }
                    ),
                    encoding="utf-8",
                )
                model = panel.register_model_manifest_file(manifest_path)

                self.assertEqual(model["model_id"], "external_local_axis/head_frame_panel_v1")
                self.assertEqual(
                    manager.project_data["view_settings"]["local_axis_active_model_id"],
                    "external_local_axis/head_frame_panel_v1",
                )
                self.assertEqual(panel.models_table.rowCount(), 1)
                self.assertIn("Registered model", panel.status_label.text())
                self.assertEqual(panel.save_active_model_profile(), "external_local_axis/head_frame_panel_v1")
            finally:
                panel.deleteLater()

    def test_local_axis_model_panel_generates_baseline_proposals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._make_local_axis_panel_project(root, "local_axis_panel_baseline")
            panel = TifLocalAxisModelPanel(manager, lang="en", specimen_id="01-0101-local-axis", part_id="head")
            try:
                result = panel.generate_baseline_proposals()

                self.assertEqual(len(result["proposals"]), 1)
                proposal = manager.list_local_frame_proposals("01-0101-local-axis", "head")[0]
                self.assertEqual(proposal["status"], "needs_review")
                self.assertEqual(proposal["model_version"], "baseline_v1")
                self.assertIn("Baseline proposals generated", panel.status_label.text())
            finally:
                panel.deleteLater()

    def test_local_axis_model_panel_saves_dedicated_backend_config(self):
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

        with tempfile.TemporaryDirectory() as tmp:
            manager = self._make_local_axis_panel_project(Path(tmp), "local_axis_panel_config")
            config = Config()
            panel = TifLocalAxisModelPanel(manager, lang="en", config_manager=config)
            try:
                panel.backend_id_edit.setText("local_axis_backend")
                panel.backend_prepare_edit.setText("python prepare.py --contract {contract_json}")
                saved = panel.save_backend_settings()

                self.assertEqual(saved["backend_id"], "local_axis_backend")
                self.assertEqual(config.values["tif_local_axis_backend"]["backend_id"], "local_axis_backend")
                self.assertEqual(config.save_calls, 1)

                panel.backend_train_edit.setText("python train.py")
                with self.assertRaisesRegex(ValueError, "contract"):
                    panel.save_backend_settings()
            finally:
                panel.deleteLater()

    def test_part_bbox_input_draws_roi_overlay_on_current_slice(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                widget.part_bbox_edit.setText("1,3,2,6,1,5")
                widget.slice_slider.setValue(1)
                rects = widget.current_roi_overlay_rects()

                self.assertEqual(rects[0]["rect"], [1, 2, 5, 6])
                self.assertEqual(rects[0]["kind"], "current")

                widget.slice_slider.setValue(0)
                self.assertEqual(widget.current_roi_overlay_rects(), [])
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_dragging_roi_updates_bbox_for_current_axis(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                widget.part_bbox_edit.setText("1,3,1,7,1,7")
                widget.slice_slider.setValue(2)
                widget.btn_part_draw_roi.setChecked(True)
                widget.canvas.resize(480, 360)
                widget.render_current_slice()
                start = widget.canvas._image_rect_to_widget_rect([2, 2, 3, 3]).center()
                end = widget.canvas._image_rect_to_widget_rect([5, 5, 6, 6]).center()

                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, start.x(), start.y()))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end.x(), end.y()))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, end.x(), end.y()))

                self.assertEqual(widget.part_bbox_edit.text(), "1,3,2,6,2,6")
                self.assertIn("ROI bbox updated", widget.training_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_dragging_loaded_roi_draft_updates_original_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                widget.project.add_part_roi(
                    widget.current_specimen_id,
                    "head_roi",
                    display_name="Head ROI",
                    bbox_zyx=[[1, 3], [1, 7], [1, 7]],
                )
                widget.active_part_roi_id = "head_roi"
                widget.part_bbox_edit.setText("1,3,1,7,1,7")
                widget.slice_slider.setValue(2)
                widget.btn_part_draw_roi.setChecked(True)
                widget.canvas.resize(480, 360)
                widget.render_current_slice()
                start = widget.canvas._image_rect_to_widget_rect([2, 2, 3, 3]).center()
                end = widget.canvas._image_rect_to_widget_rect([5, 5, 6, 6]).center()

                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, start.x(), start.y()))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end.x(), end.y()))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, end.x(), end.y()))
                roi = widget.save_part_roi_draft()

                self.assertEqual(widget.active_part_roi_id, "head_roi")
                self.assertEqual(roi["bbox_zyx"], [[1, 3], [2, 6], [2, 6]])
                self.assertEqual(len(widget.project.list_part_rois(widget.current_specimen_id)), 1)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_roi_draft_saves_without_writing_part_until_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                widget.part_bbox_edit.setText("1,3,2,6,1,5")
                module_path = "AntSleap.ui.tif_workbench.TifPartNameDialog"
                FakePartNameDialog.queue = [("head_roi", "Head ROI", True)]
                with patch(module_path, FakePartNameDialog):
                    roi = widget.save_part_roi_draft()

                self.assertIsNotNone(roi)
                self.assertEqual(roi["status"], "draft")
                self.assertEqual(widget.project.list_parts(widget.current_specimen_id), [])
                self.assertEqual(widget.active_part_roi_id, "head_roi")
                widget.slice_slider.setValue(1)
                self.assertTrue(widget.current_roi_overlay_rects())

                FakePartNameDialog.queue = [("head", "Head", True)]
                with patch(module_path, FakePartNameDialog):
                    widget.confirm_part_roi_to_part()

                part = widget.project.get_part("01-0101-21", "head")
                roi = widget.project.get_part_roi("01-0101-21", "head_roi")
                self.assertIsNotNone(part)
                self.assertEqual(roi["status"], "part_created")
                self.assertEqual(roi["linked_part_id"], "head")
                self.assertEqual(widget.current_volume_scope, "part")
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_double_click_created_part_roi_opens_part_volume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=4)
            try:
                part = crop_volume_to_part(widget.project, "01-0101-21", "head", [[1, 3], [2, 6], [1, 5]], display_name="Head")
                widget.project.add_part_roi(
                    "01-0101-21",
                    "head_roi",
                    display_name="Head ROI",
                    bbox_zyx=part["parent_bbox_zyx"],
                    status="part_created",
                    linked_part_id="head",
                )
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "full", "")
                widget.slice_slider.setValue(1)
                widget.render_current_slice()
                point = widget.canvas._image_rect_to_widget_rect([1, 2, 5, 6]).center()

                self.assertTrue(widget.open_roi_at_widget_position(point.x(), point.y()))

                self.assertEqual(widget.current_volume_scope, "part")
                self.assertEqual(widget.current_part_id, "head")
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_delete_current_part_volume_removes_part_storage_and_returns_to_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=4)
            try:
                part = crop_volume_to_part(widget.project, "01-0101-21", "head", [[1, 3], [2, 6], [1, 5]], display_name="Head")
                widget.project.add_part_roi(
                    "01-0101-21",
                    "head_roi",
                    display_name="Head ROI",
                    bbox_zyx=part["parent_bbox_zyx"],
                    status="part_created",
                    linked_part_id="head",
                )
                part_dir = root / "viewer" / widget.project.part_dir("01-0101-21", "head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                self.assertTrue(part_dir.exists())
                self.assertTrue(widget.btn_delete_part_volume.isEnabled())

                with patch("AntSleap.ui.tif_workbench.QMessageBox.question", return_value=QMessageBox.Yes):
                    widget.delete_current_part_volume()

                self.assertFalse(part_dir.exists())
                self.assertIsNone(widget.project.get_part("01-0101-21", "head", default=None))
                self.assertEqual(widget.current_volume_scope, "full")
                self.assertEqual(widget.current_part_id, "")
                roi = widget.project.get_part_roi("01-0101-21", "head_roi", default=None)
                self.assertEqual(roi["status"], "cancelled")
                self.assertEqual(roi["linked_part_id"], "")
                self.assertIn("Deleted part volume Head", widget.training_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_part_freehand_contour_saves_overlay_and_deletes_key_slice(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[1, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.slice_slider.setValue(1)
                widget.btn_draw_part_contour.setChecked(True)
                widget.canvas.resize(480, 360)
                widget.render_current_slice()

                pixels = ([2, 2], [5, 2], [5, 5], [2, 5], [2, 3])
                points = [widget.canvas._image_point_to_widget_point(pixel) for pixel in pixels]
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, points[0][0], points[0][1]))
                for point in points[1:]:
                    widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, point[0], point[1]))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, points[-1][0], points[-1][1]))

                contours_path = widget.project.to_absolute(widget.project.get_part("01-0101-21", "head")["contours_path"])
                contours = read_contours_json(contours_path)
                self.assertEqual(len(contours["keyframes"]), 1)
                self.assertEqual(contours["keyframes"][0]["slice_index"], 1)
                self.assertEqual(contours["keyframes"][0]["source"], "manual_freehand")
                self.assertGreaterEqual(len(contours["keyframes"][0]["polygon"]), 3)
                self.assertTrue(widget.current_contour_overlay_polygons())

                widget.delete_current_part_keyframe()
                contours = read_contours_json(contours_path)
                self.assertEqual(contours["keyframes"], [])
                self.assertFalse(widget.current_contour_overlay_polygons())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_part_key_slice_navigation_jumps_between_saved_contours(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=6)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 5], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                part = widget.project.get_part("01-0101-21", "head")
                contours_path = widget.project.to_absolute(part["contours_path"])
                contours = read_contours_json(contours_path)
                polygon = [[1, 1], [4, 1], [4, 4], [1, 4]]
                contours = add_polygon_keyframe(contours, 0, polygon, axis="z", source="manual_freehand")
                contours = add_polygon_keyframe(contours, 3, polygon, axis="z", source="manual_freehand")
                write_contours_json(contours_path, contours)

                widget.slice_slider.setValue(1)
                widget.jump_part_keyframe("next")
                self.assertEqual(widget.slice_slider.value(), 3)
                self.assertTrue(widget.current_contour_overlay_polygons())

                widget.jump_part_keyframe("previous")
                self.assertEqual(widget.slice_slider.value(), 0)
                widget.jump_part_keyframe("previous")
                self.assertIn("No previous key slice", widget.training_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_dirty_contours_do_not_break_slice_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 5], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                part = widget.project.get_part("01-0101-21", "head")
                contours_path = Path(widget.project.to_absolute(part["contours_path"]))
                contours_path.write_text(
                    '{"axis":"z","keyframes":["bad",{"slice_index":"bad","polygon":[[1,1],[2,1],[2,2]]},{"slice_index":1,"polygon":[[1,1],[4,1],[4,4],[1,4]]}]}',
                    encoding="utf-8",
                )
                widget.slice_slider.setValue(1)

                overlays = widget.current_contour_overlay_polygons()

                self.assertEqual(len(overlays), 1)
                self.assertEqual(overlays[0]["polygon"], [[1, 1], [4, 1], [4, 4], [1, 4]])
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_part_mask_preview_reports_quality_and_3d_mask_modes_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=6)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 5], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                part = widget.project.get_part("01-0101-21", "head")
                contours_path = widget.project.to_absolute(part["contours_path"])
                polygon_a = [[1, 1], [4, 1], [4, 4], [1, 4]]
                polygon_b = [[2, 2], [5, 2], [5, 5], [2, 5]]
                contours = read_contours_json(contours_path)
                contours = add_polygon_keyframe(contours, 0, polygon_a, axis="z", source="manual_freehand")
                contours = add_polygon_keyframe(contours, 4, polygon_b, axis="z", source="manual_freehand")
                write_contours_json(contours_path, contours)

                widget.preview_part_mask_from_keyframes()

                self.assertIsNotNone(widget.part_preview_mask)
                self.assertIn("Part mask preview quality", widget.training_status_label.text())
                self.assertGreater(int(widget.part_preview_mask.sum()), 0)

                mode_index = widget.display_mode_combo.findData("volume")
                widget.display_mode_combo.setCurrentIndex(mode_index)
                boundary_index = widget.volume_mask_combo.findData("mask_boundary")
                widget.volume_mask_combo.setCurrentIndex(boundary_index)
                widget.render_volume_preview()
                self.assertIn("Mask display Mask boundary", widget.volume_canvas_overlay_text())
                if isinstance(widget.volume_canvas, TifVolumeCanvas):
                    self.assertIsNotNone(widget.volume_canvas.pixmap())

                masked_index = widget.volume_mask_combo.findData("masked_image")
                widget.volume_mask_combo.setCurrentIndex(masked_index)
                widget.render_volume_preview()
                self.assertIn("Masked image", widget.volume_canvas_overlay_text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_part_volume_3d_defaults_to_masked_image_after_mask_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                self.assertEqual(widget.volume_mask_combo.currentData(), "image_only")

                part = widget.project.get_part("01-0101-21", "head")
                contours_path = widget.project.to_absolute(part["contours_path"])
                contours = read_contours_json(contours_path)
                contours = add_polygon_keyframe(contours, 0, [[1, 1], [4, 1], [4, 4], [1, 4]], axis="z", source="manual_freehand")
                contours = add_polygon_keyframe(contours, 3, [[2, 2], [5, 2], [5, 5], [2, 5]], axis="z", source="manual_freehand")
                write_contours_json(contours_path, contours)
                widget.preview_part_mask_from_keyframes()
                widget.accept_part_mask_preview()

                mode_index = widget.display_mode_combo.findData("volume")
                widget.display_mode_combo.setCurrentIndex(mode_index)

                self.assertEqual(widget.volume_mask_combo.currentData(), "masked_image")
                self.assertIn("Masked image", widget.volume_canvas_overlay_text())

                image_index = widget.volume_mask_combo.findData("image_only")
                widget.volume_mask_combo.setCurrentIndex(image_index)
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("slice"))
                widget.display_mode_combo.setCurrentIndex(mode_index)

                self.assertEqual(widget.volume_mask_combo.currentData(), "image_only")
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_task_tabs_follow_tif_workflow_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                self.assertIs(widget.task_tabs.currentWidget(), widget.part_task_page)
                self.assertFalse(widget.part_locate_section.isHidden())
                self.assertTrue(widget.part_mask_section.isHidden())
                self.assertTrue(widget.part_output_section.isHidden())

                mode_index = widget.display_mode_combo.findData("volume")
                widget.display_mode_combo.setCurrentIndex(mode_index)
                self.assertIs(widget.task_tabs.currentWidget(), widget.display_task_page)
                self.assertTrue(widget.part_locate_section.isHidden())

                slice_index = widget.display_mode_combo.findData("slice")
                widget.display_mode_combo.setCurrentIndex(slice_index)
                self.assertIs(widget.task_tabs.currentWidget(), widget.part_task_page)
                self.assertFalse(widget.part_locate_section.isHidden())

                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                self.assertIs(widget.task_tabs.currentWidget(), widget.part_task_page)
                self.assertTrue(widget.annotation_section.isHidden())
                self.assertTrue(widget.part_locate_section.isHidden())
                self.assertFalse(widget.part_mask_section.isHidden())
                self.assertFalse(widget.part_output_section.isHidden())

                widget.display_mode_combo.setCurrentIndex(mode_index)
                self.assertIs(widget.task_tabs.currentWidget(), widget.display_task_page)
                self.assertTrue(widget.part_mask_section.isHidden())
                self.assertFalse(widget.part_output_section.isHidden())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_part_mask_buttons_refresh_when_returning_to_slice_z_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 5], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                self.assertTrue(widget.btn_draw_part_contour.isEnabled())
                self.assertTrue(widget.btn_preview_part_mask.isEnabled())

                mode_index = widget.display_mode_combo.findData("volume")
                widget.display_mode_combo.setCurrentIndex(mode_index)
                self.assertFalse(widget.btn_draw_part_contour.isEnabled())

                slice_index = widget.display_mode_combo.findData("slice")
                widget.display_mode_combo.setCurrentIndex(slice_index)
                y_index = widget.slice_axis_combo.findData("y")
                widget.slice_axis_combo.setCurrentIndex(y_index)
                self.assertFalse(widget.btn_draw_part_contour.isEnabled())

                z_index = widget.slice_axis_combo.findData("z")
                widget.slice_axis_combo.setCurrentIndex(z_index)
                self.assertTrue(widget.btn_draw_part_contour.isEnabled())
                self.assertTrue(widget.btn_preview_part_mask.isEnabled())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_rectangular_keyframe_clears_stale_preview_mask(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 5], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.part_preview_mask = np.ones(tuple(widget.image_volume.shape), dtype=np.uint16)

                widget.add_current_rect_keyframe()

                self.assertIsNone(widget.part_preview_mask)
                self.assertEqual(widget.project.get_part("01-0101-21", "head")["status"], "draft")
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_part_volume_color_can_override_parent_render_color(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                cyan_index = widget.volume_tint_combo.findData("cyan")
                widget.volume_tint_combo.setCurrentIndex(cyan_index)
                self.assertEqual(widget.project.project_data["view_settings"]["volume_tint"], "cyan")

                crop_volume_to_part(widget.project, "01-0101-21", "head", [[1, 3], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                self.assertEqual(widget.volume_tint_combo.currentData(), "cyan")

                white_index = widget.volume_tint_combo.findData("white")
                widget.volume_tint_combo.setCurrentIndex(white_index)

                part = widget.project.get_part("01-0101-21", "head")
                self.assertEqual(part["view_settings"]["volume_tint"], "white")
                self.assertEqual(widget.project.project_data["view_settings"]["volume_tint"], "cyan")
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_part_volume_color_override_survives_project_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=4)
            project_json = widget.project.current_project_path
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[1, 3], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                white_index = widget.volume_tint_combo.findData("white")
                widget.volume_tint_combo.setCurrentIndex(white_index)
            finally:
                widget.close_project()
                widget.deleteLater()

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)
            self.assertEqual(reloaded.get_part("01-0101-21", "head")["view_settings"]["volume_tint"], "white")

    def test_part_extraction_flow_reopens_with_mask_contours_and_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=5)
            project_json = widget.project.current_project_path
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                part = widget.project.get_part("01-0101-21", "head")
                contours_path = widget.project.to_absolute(part["contours_path"])
                polygon_a = [[1, 1], [4, 1], [4, 4], [1, 4]]
                polygon_b = [[2, 2], [5, 2], [5, 5], [2, 5]]
                contours = read_contours_json(contours_path)
                contours = add_polygon_keyframe(contours, 0, polygon_a, axis="z", source="manual_freehand")
                contours = add_polygon_keyframe(contours, 3, polygon_b, axis="z", source="manual_freehand")
                write_contours_json(contours_path, contours)

                widget.preview_part_mask_from_keyframes()
                self.assertIsNotNone(widget.part_preview_mask)
                widget.accept_part_mask_preview()
                self.assertIn("Accepted part mask", widget.training_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)
            reloaded_widget = TifWorkbenchWidget(reloaded, "en")
            try:
                reloaded_widget._select_volume_tree_item("01-0101-21", "part", "head")
                self.assertEqual(reloaded_widget.current_volume_scope, "part")
                self.assertIsNotNone(reloaded_widget.image_volume)
                self.assertIsNotNone(reloaded_widget.label_volume)
                self.assertEqual(tuple(reloaded_widget.image_volume.shape), tuple(reloaded_widget.label_volume.shape))
                part = reloaded_widget.project.get_part("01-0101-21", "head")
                self.assertTrue(Path(reloaded_widget.project.to_absolute(part["contours_path"])).exists())
                self.assertTrue(Path(reloaded_widget.project.to_absolute(part["extraction_path"])).exists())
                self.assertTrue(reloaded_widget.current_contour_overlay_polygons())
            finally:
                reloaded_widget.close_project()
                reloaded_widget.deleteLater()

    def test_part_package_export_status_does_not_expand_sidebar_with_full_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=4)
            export_dir = root / "very" / "deep" / "external" / "part" / "archive" / "folder"
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 3], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                with patch("AntSleap.ui.tif_workbench.QFileDialog.getExistingDirectory", return_value=str(export_dir)):
                    with patch_message_boxes():
                        widget.export_current_part_package()
                text = widget.training_status_label.text()
                self.assertIn("part_manifest.json", text)
                self.assertNotIn(str(export_dir), text)
                self.assertIn(str(export_dir), widget.training_status_label.toolTip())
                self.assertTrue((export_dir / "01-0101-21_head" / "part_manifest.json").exists())
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
            self.assertEqual(widget.btn_local_axis_models.text(), "Local Axis Models")
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
            self.assertIsNotNone(widget.findChild(type(widget.btn_local_axis_models), "tifLocalAxisModelsButton"))
            self.assertIsNotNone(widget.findChild(type(widget.auto_save_check), "tifAutoSaveEditCheck"))
            self.assertIsNotNone(widget.findChild(type(widget.display_mode_combo), "tifDisplayModeCombo"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_cutoff_slider), "tifVolumeCutoffSlider"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_projection_combo), "tifVolumeProjectionCombo"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_quality_slider), "tifVolumeQualitySlider"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_sample_slider), "tifVolumeSampleSlider"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_inside_slider), "tifVolumeInsideSlider"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_clip_slider), "tifVolumeClipSlider"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_reset_volume_view), "tifResetVolumeViewButton"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_clarity_check), "tifVolumeClarityCheck"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_roi_detail_check), "tifVolumeRoiDetailCheck"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_roi_scale_slider), "tifVolumeRoiScaleSlider"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifSliceDisplaySection"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifVolumeRenderSection"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifVolumeCanvas"))
            self.assertEqual(widget.volume_quality_slider.maximum(), 4096)
            self.assertEqual(widget.volume_sample_slider.maximum(), 4096)
            self.assertEqual(widget.volume_inside_slider.maximum(), 160)
            self.assertEqual(widget.volume_projection_combo.currentData(), "composite")
            self.assertEqual(widget.volume_roi_scale_slider.value(), 200)
            self.assertFalse(widget.slice_display_section.isHidden())
            self.assertFalse(widget.annotation_section.isHidden())
            self.assertTrue(widget.volume_render_section.isHidden())
            self.assertEqual(widget.backend_id_edit.objectName(), "tifBackendIdEdit")
            self.assertEqual(widget.backend_formats_edit.text(), "ome_tiff,nrrd,mha,nifti")
            self.assertEqual(widget.training_status_label.objectName(), "tifTrainingStatusText")
            self.assertEqual(widget.log_console.objectName(), "tifLogConsole")
            task_tabs = widget.findChild(QWidget, "tifTaskTabs")
            self.assertIsNotNone(task_tabs)
            self.assertEqual(widget.task_tabs.count(), 4)
            self.assertEqual(widget.task_tabs.tabText(0), "Part")
            self.assertEqual(widget.task_tabs.tabText(1), "Display")
            self.assertEqual(widget.task_tabs.tabText(2), "Annotation")
            self.assertEqual(widget.task_tabs.tabText(3), "Train/export")
            self.assertIs(widget.log_console.parentWidget().parentWidget(), widget.training_task_page.widget())
            self.assertIsNotNone(widget.findChild(QWidget, "tifStatusSection"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifPartLocateSection"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifPartMaskSection"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifPartOutputSection"))
            self.assertEqual(widget.btn_import_tif.property("tifRole"), "primary")
            self.assertEqual(widget.btn_train_backend.property("tifRole"), "primary")
            self.assertEqual(widget.btn_local_axis_models.property("tifRole"), "primary")
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

    def test_volume_canvas_is_created_lazily_and_released_before_agent(self):
        manager = TifProjectManager()
        created = []

        class FakeGpuCanvas(TifVolumeCanvas):
            def __init__(self):
                super().__init__()
                self.release_calls = 0

            def set_volume_data(self, *args, **kwargs):
                return None

            def release_gl_resources(self):
                self.release_calls += 1

        fake_canvas = FakeGpuCanvas()

        def fake_factory(parent=None):
            created.append(parent)
            return fake_canvas, "gpu", ""

        with patch("AntSleap.ui.tif_workbench.create_tif_volume_canvas", fake_factory):
            widget = TifWorkbenchWidget(manager, "en")
            try:
                self.assertFalse(widget._volume_canvas_created)
                self.assertIsInstance(widget.volume_canvas, TifVolumeCanvas)
                self.assertIsNot(widget.volume_canvas, fake_canvas)
                self.assertEqual(created, [])

                mode_index = widget.display_mode_combo.findData("volume")
                widget.display_mode_combo.setCurrentIndex(mode_index)

                self.assertTrue(widget._volume_canvas_created)
                self.assertIs(widget.volume_canvas, fake_canvas)
                self.assertEqual(widget._volume_canvas_renderer, "gpu")

                widget.prepare_for_agent_panel()

                self.assertEqual(widget.display_mode, "slice")
                self.assertFalse(widget._volume_canvas_created)
                self.assertIsInstance(widget.volume_canvas, TifVolumeCanvas)
                self.assertIsNot(widget.volume_canvas, fake_canvas)
                self.assertEqual(fake_canvas.release_calls, 1)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_3d_mask_mode_falls_back_from_gpu_canvas_to_cpu_pixmap_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)

            class FakeGpuLabel(QLabel):
                def __init__(self):
                    super().__init__()
                    self.release_calls = 0

                def set_volume_data(self, *args, **kwargs):
                    return None

                def release_gl_resources(self):
                    self.release_calls += 1

            fake_canvas = FakeGpuLabel()
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 5], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.part_preview_mask = np.ones(tuple(widget.image_volume.shape), dtype=np.uint16)
                widget.display_mode = "volume"
                widget.view_stack.addWidget(fake_canvas)
                widget.volume_canvas = fake_canvas
                widget._volume_canvas_renderer = "gpu"
                widget._volume_canvas_created = True
                boundary_index = widget.volume_mask_combo.findData("mask_boundary")
                widget.volume_mask_combo.setCurrentIndex(boundary_index)

                widget.render_volume_preview()

                self.assertEqual(fake_canvas.release_calls, 1)
                self.assertEqual(widget._volume_canvas_renderer, "cpu")
                self.assertIsInstance(widget.volume_canvas, TifVolumeCanvas)
                self.assertIsNotNone(widget.volume_canvas.pixmap())
            finally:
                widget.close_project()
                widget.deleteLater()
                fake_canvas.deleteLater()

    def test_masked_image_mode_uses_gpu_canvas_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)

            class FakeGpuLabel(QLabel):
                def __init__(self):
                    super().__init__()
                    self.release_calls = 0
                    self.uploads = []
                    self.mask_upload = None
                    self.render_state_args = None
                    self.render_state_kwargs = None

                def set_volume_data(self, volume, *args, **kwargs):
                    self.uploads.append(np.asarray(volume).copy())

                def set_mask_data(self, mask):
                    self.mask_upload = None if mask is None else np.asarray(mask).copy()

                def set_render_state(self, *args, **kwargs):
                    self.render_state_args = args
                    self.render_state_kwargs = kwargs
                    return None

                def release_gl_resources(self):
                    self.release_calls += 1

            fake_canvas = FakeGpuLabel()
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 5], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                mask = np.zeros(tuple(widget.image_volume.shape), dtype=np.uint16)
                mask[:, 1:4, 1:4] = 1
                widget.part_preview_mask = mask
                widget.display_mode = "volume"
                widget.view_stack.addWidget(fake_canvas)
                widget.volume_canvas = fake_canvas
                widget._volume_canvas_renderer = "gpu"
                widget._volume_canvas_created = True
                masked_index = widget.volume_mask_combo.findData("masked_image")
                widget.volume_mask_combo.setCurrentIndex(masked_index)

                widget.render_volume_preview()

                self.assertEqual(fake_canvas.release_calls, 0)
                self.assertEqual(widget._volume_canvas_renderer, "gpu")
                self.assertGreaterEqual(len(fake_canvas.uploads), 1)
                uploaded = fake_canvas.uploads[-1]
                self.assertEqual(tuple(uploaded.shape), tuple(widget._ensure_volume_preview("still").shape))
                self.assertGreater(int(uploaded[:, 1:4, 1:4].sum()), 0)
                outside = uploaded.copy()
                outside[:, 1:4, 1:4] = 0
                self.assertGreater(int(outside.sum()), 0)
                self.assertIsNotNone(fake_canvas.mask_upload)
                self.assertGreater(int(fake_canvas.mask_upload[:, 1:4, 1:4].sum()), 0)
                mask_outside = fake_canvas.mask_upload.copy()
                mask_outside[:, 1:4, 1:4] = 0
                self.assertEqual(int(mask_outside.sum()), 0)
                self.assertIsNotNone(fake_canvas.render_state_kwargs)
                self.assertEqual(fake_canvas.render_state_kwargs["transfer_preset"], widget._volume_transfer_preset())
                self.assertEqual(fake_canvas.render_state_kwargs["mask_mode"], "masked_image")
                self.assertEqual(fake_canvas.render_state_kwargs["render_mode"], "still")
            finally:
                widget.close_project()
                widget.deleteLater()
                fake_canvas.deleteLater()

    def test_mask_boundary_mode_uses_gpu_canvas_when_mask_texture_is_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)

            class FakeGpuLabel(QLabel):
                def __init__(self):
                    super().__init__()
                    self.release_calls = 0
                    self.uploads = []
                    self.mask_upload = None
                    self.render_state_kwargs = None

                def set_volume_data(self, volume, *args, **kwargs):
                    self.uploads.append(np.asarray(volume).copy())

                def set_mask_data(self, mask):
                    self.mask_upload = None if mask is None else np.asarray(mask).copy()

                def set_render_state(self, *args, **kwargs):
                    self.render_state_kwargs = dict(kwargs)

                def release_gl_resources(self):
                    self.release_calls += 1

            fake_canvas = FakeGpuLabel()
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 5], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                mask = np.zeros(tuple(widget.image_volume.shape), dtype=np.uint16)
                mask[:, 1:4, 1:4] = 1
                widget.part_preview_mask = mask
                widget.display_mode = "volume"
                widget.view_stack.addWidget(fake_canvas)
                widget.volume_canvas = fake_canvas
                widget._volume_canvas_renderer = "gpu"
                widget._volume_canvas_created = True
                boundary_index = widget.volume_mask_combo.findData("mask_boundary")
                widget.volume_mask_combo.setCurrentIndex(boundary_index)

                widget.render_volume_preview()

                self.assertEqual(fake_canvas.release_calls, 0)
                self.assertEqual(widget._volume_canvas_renderer, "gpu")
                self.assertGreaterEqual(len(fake_canvas.uploads), 1)
                self.assertIsNotNone(fake_canvas.mask_upload)
                self.assertEqual(fake_canvas.render_state_kwargs["mask_mode"], "mask_boundary")
            finally:
                widget.close_project()
                widget.deleteLater()
                fake_canvas.deleteLater()

    def test_image_only_mode_restores_gpu_after_temporary_mask_cpu_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 5], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.part_preview_mask = np.ones(tuple(widget.image_volume.shape), dtype=np.uint16)
                widget.display_mode = "volume"
                widget._volume_canvas_created = True
                widget._volume_canvas_renderer = "cpu"
                widget.volume_canvas.setProperty("tifVolumeRenderer", "cpu-mask-fallback")
                class FakeRestoredGpuCanvas(TifVolumeCanvas):
                    def set_volume_data(self, *args, **kwargs):
                        return None

                gpu_canvas = FakeRestoredGpuCanvas()
                gpu_canvas.setProperty("tifVolumeRenderer", "gpu-offscreen")
                calls = []

                def fake_factory(parent=None):
                    calls.append(parent)
                    return gpu_canvas, "gpu", ""

                image_index = widget.volume_mask_combo.findData("image_only")
                widget.volume_mask_combo.setCurrentIndex(image_index)
                with patch("AntSleap.ui.tif_workbench.create_tif_volume_canvas", fake_factory):
                    widget.render_volume_preview()

                self.assertEqual(widget._volume_canvas_renderer, "gpu")
                self.assertIs(widget.volume_canvas, gpu_canvas)
                self.assertEqual(len(calls), 1)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_ask_agent_context_includes_tif_view_and_local_axis_reslice_focus(self):
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
                widget.volume_projection_combo.setCurrentIndex(widget.volume_projection_combo.findData("mip"))
                widget.volume_clarity_check.setChecked(True)
                widget.volume_roi_scale_slider.setValue(250)
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
                expected_target_dim = "2048" if widget._volume_canvas_renderer == "gpu" else "128"
                self.assertEqual(context["volume_texture_target_dim"], expected_target_dim)
                self.assertEqual(context["volume_projection_mode"], "mip")
                self.assertEqual(context["volume_ray_samples"], "2048")
                self.assertEqual(context["volume_clarity_mode"], "on")
                self.assertEqual(context["volume_roi_high_detail"], "on")
                self.assertEqual(context["volume_inside_depth"], "65%")
                self.assertEqual(context["volume_front_cut"], "30%")
                self.assertIn("yaw=", context["volume_yaw_pitch"])
                self.assertIn("local_axis_reslice", context["tif_next_requirement"])
                self.assertIn("AntScan局部轴重切片合并设计稿", context["tif_requirement_doc"])
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

    def test_slice_slider_arrow_keys_follow_review_shortcuts(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                self.assertEqual(widget.slice_slider.value(), 0)
                self.assertEqual(widget.canvas.zoom_factor(), 1.0)

                up = FakeKeyEvent(Qt.Key_Up)
                widget.slice_slider.keyPressEvent(up)
                self.assertTrue(up.accepted)
                self.assertEqual(widget.slice_slider.value(), 0)
                self.assertGreater(widget.canvas.zoom_factor(), 1.0)

                down = FakeKeyEvent(Qt.Key_Down)
                widget.slice_slider.keyPressEvent(down)
                self.assertTrue(down.accepted)
                self.assertEqual(widget.slice_slider.value(), 0)
                self.assertEqual(widget.canvas.zoom_factor(), 1.0)

                right = FakeKeyEvent(Qt.Key_Right)
                widget.slice_slider.keyPressEvent(right)
                self.assertTrue(right.accepted)
                self.assertEqual(widget.slice_slider.value(), 1)
                self.assertEqual(widget.canvas.zoom_factor(), 1.0)

                left = FakeKeyEvent(Qt.Key_Left)
                widget.slice_slider.keyPressEvent(left)
                self.assertTrue(left.accepted)
                self.assertEqual(widget.slice_slider.value(), 0)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_control_slider_arrow_keys_follow_review_shortcuts(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                widget.brightness_slider.setValue(10)
                self.assertEqual(widget.slice_slider.value(), 0)
                self.assertEqual(widget.canvas.zoom_factor(), 1.0)

                up = FakeKeyEvent(Qt.Key_Up)
                widget.brightness_slider.keyPressEvent(up)
                self.assertTrue(up.accepted)
                self.assertEqual(widget.brightness_slider.value(), 10)
                self.assertEqual(widget.slice_slider.value(), 0)
                self.assertGreater(widget.canvas.zoom_factor(), 1.0)

                right = FakeKeyEvent(Qt.Key_Right)
                widget.brightness_slider.keyPressEvent(right)
                self.assertTrue(right.accepted)
                self.assertEqual(widget.brightness_slider.value(), 10)
                self.assertEqual(widget.slice_slider.value(), 1)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_canvas_zoom_pan_and_slice_change_preserve_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=3)
            try:
                up = FakeKeyEvent(Qt.Key_Up)
                widget.canvas.keyPressEvent(up)
                self.assertTrue(up.accepted)
                self.assertGreater(widget.canvas.zoom_factor(), 1.0)
                for _ in range(20):
                    widget.canvas.keyPressEvent(FakeKeyEvent(Qt.Key_Up))
                self.assertEqual(widget.canvas.zoom_factor(), 16.0)
                self.assertIn("1600%", widget.canvas_status_text(widget.canvas.zoom_factor()))

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
                self.assertEqual(widget.canvas.zoom_factor(), 16.0)
                self.assertNotEqual((widget.canvas._pan_x, widget.canvas._pan_y), (0.0, 0.0))
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
                widget.volume_projection_combo.setCurrentIndex(widget.volume_projection_combo.findData("surface"))
                widget.volume_clarity_check.setChecked(True)
                widget.volume_roi_scale_slider.setValue(250)
                widget.volume_inside_slider.setValue(65)
                widget.volume_clip_slider.setValue(30)
                widget.zoom_volume_preview(1)
                widget._finish_volume_interaction()
                self.assertIn("RTX 3090", widget.volume_status_text())
                self.assertIn("Volume view | GPU ray march [", widget.volume_canvas_overlay_text())
                self.assertIn("Still high quality", widget.volume_canvas_overlay_text())
                self.assertIn("Mode Surface", widget.volume_canvas_overlay_text())
                self.assertIn("Texture 4096", widget.volume_canvas_overlay_text())
                self.assertIn("Samples 4096", widget.volume_canvas_overlay_text())
                if widget._volume_canvas_renderer == "gpu":
                    self.assertIn("ROI 2.5x", widget.volume_canvas_overlay_text())
                self.assertIn("Inside 65%", widget.volume_canvas_overlay_text())
                self.assertIn("Cut 30%", widget.volume_canvas_overlay_text())
                self.assertIn("drag rotate / wheel zoom", widget.volume_status_text())
                self.assertIn("Pan X 0%", widget.volume_canvas_overlay_text())
                self.assertNotIn("render_quality", widget.volume_canvas_overlay_text())
                widget.change_language("zh")
                self.assertIn("体预览 | GPU 光线步进 [", widget.volume_canvas_overlay_text())
                self.assertIn("静止高清", widget.volume_canvas_overlay_text())
                self.assertIn("模式 表面边界", widget.volume_canvas_overlay_text())
                self.assertEqual(widget.volume_clarity_check.text(), "清晰模式")
                self.assertEqual(widget.volume_roi_detail_check.text(), "ROI 高清")
                self.assertIn("纹理 4096", widget.volume_canvas_overlay_text())
                self.assertIn("采样 4096", widget.volume_canvas_overlay_text())
                if widget._volume_canvas_renderer == "gpu":
                    self.assertIn("ROI 2.5x", widget.volume_canvas_overlay_text())
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
                for _ in range(40):
                    widget.zoom_volume_preview(1)
                self.assertEqual(widget._volume_zoom, 16.0)
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

    def test_part_volume_still_preview_preserves_uint16_detail_by_default(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget.current_volume_scope = "part"
            widget.image_volume = np.array([[[0, 32768], [49152, 65535]]], dtype=np.uint16)
            preview = widget._ensure_volume_preview("still")
            self.assertEqual(preview.dtype, np.uint16)
            np.testing.assert_array_equal(preview, widget.image_volume)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_transfer_function_change_keeps_volume_texture_cache(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuLabel(QLabel):
            def __init__(self):
                super().__init__()
                self.upload_ids = []
                self.render_state_kwargs = []

            def set_volume_data(self, volume, *args, **kwargs):
                self.upload_ids.append(id(volume))

            def set_render_state(self, *args, **kwargs):
                self.render_state_kwargs.append(dict(kwargs))

        fake_canvas = FakeGpuLabel()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget.display_mode = "volume"
            widget.image_volume = np.zeros((8, 96, 96), dtype=np.uint8)
            widget.image_volume[:, 24:72, 24:72] = 180

            widget.render_volume_preview()
            before_cache_items = [(key, id(value)) for key, value in widget._volume_preview_cache.items()]
            before_upload = fake_canvas.upload_ids[-1]
            cyan_index = widget.volume_tint_combo.findData("cyan")
            widget.volume_tint_combo.setCurrentIndex(cyan_index)

            after_cache_items = [(key, id(value)) for key, value in widget._volume_preview_cache.items()]
            self.assertEqual(before_cache_items, after_cache_items)
            self.assertEqual(fake_canvas.upload_ids[-1], before_upload)
            self.assertEqual(fake_canvas.render_state_kwargs[-1]["transfer_preset"], "cyan")
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_volume_drag_updates_gpu_camera_without_reuploading_texture(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuLabel(QLabel):
            def __init__(self):
                super().__init__()
                self.upload_ids = []
                self.mask_uploads = []
                self.render_state_kwargs = []
                self.interaction_state_kwargs = []
                self._has_volume = False

            def has_volume(self):
                return self._has_volume

            def set_volume_data(self, volume, *args, **kwargs):
                self.upload_ids.append(id(volume))
                self._has_volume = True

            def set_mask_data(self, mask):
                self.mask_uploads.append(None if mask is None else id(mask))

            def set_render_state(self, *args, **kwargs):
                self.render_state_kwargs.append(dict(kwargs))

            def set_interaction_render_state(self, *args, **kwargs):
                self.interaction_state_kwargs.append(dict(kwargs))

        fake_canvas = FakeGpuLabel()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget.display_mode = "volume"
            widget.image_volume = np.zeros((8, 96, 96), dtype=np.uint8)
            widget.image_volume[:, 24:72, 24:72] = 180

            widget.render_volume_preview()
            self.assertEqual(len(fake_canvas.upload_ids), 1)
            first_upload = fake_canvas.upload_ids[-1]

            widget.rotate_volume_preview(20, -5)
            widget._render_volume_interaction_preview()

            self.assertEqual(fake_canvas.upload_ids, [first_upload])
            self.assertTrue(fake_canvas.interaction_state_kwargs)
            self.assertEqual(fake_canvas.interaction_state_kwargs[-1]["render_mode"], "drag")
            self.assertLessEqual(fake_canvas.interaction_state_kwargs[-1]["sample_steps"], 768)
            self.assertEqual(widget._volume_render_mode, "drag")
            widget._finish_volume_interaction()
            self.assertEqual(widget._volume_render_mode, "still")
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_transfer_opacity_change_keeps_volume_texture_cache(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuLabel(QLabel):
            def __init__(self):
                super().__init__()
                self.upload_ids = []
                self.render_state_kwargs = []

            def set_volume_data(self, volume, *args, **kwargs):
                self.upload_ids.append(id(volume))

            def set_mask_data(self, mask):
                return None

            def set_render_state(self, *args, **kwargs):
                self.render_state_kwargs.append(dict(kwargs))

        fake_canvas = FakeGpuLabel()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget.display_mode = "volume"
            widget.image_volume = np.zeros((8, 96, 96), dtype=np.uint8)
            widget.image_volume[:, 24:72, 24:72] = 180

            widget.render_volume_preview()
            before_cache_items = [(key, id(value)) for key, value in widget._volume_preview_cache.items()]
            before_upload = fake_canvas.upload_ids[-1]
            widget.volume_transfer_opacity_slider.setValue(65)

            after_cache_items = [(key, id(value)) for key, value in widget._volume_preview_cache.items()]
            self.assertEqual(before_cache_items, after_cache_items)
            self.assertEqual(fake_canvas.upload_ids[-1], before_upload)
            self.assertAlmostEqual(fake_canvas.render_state_kwargs[-1]["transfer_opacity"], 0.65)
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_volume_enhancement_and_clip_plane_are_passed_to_gpu_state(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuLabel(QLabel):
            def __init__(self):
                super().__init__()
                self.render_state_kwargs = []

            def set_volume_data(self, *args, **kwargs):
                return None

            def set_mask_data(self, mask):
                return None

            def set_render_state(self, *args, **kwargs):
                self.render_state_kwargs.append(dict(kwargs))

        fake_canvas = FakeGpuLabel()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget.display_mode = "volume"
            widget.image_volume = np.zeros((8, 96, 96), dtype=np.uint8)
            widget.image_volume[:, 24:72, 24:72] = 180
            widget._volume_yaw = 35.0
            widget._volume_pitch = -15.0

            widget.volume_enhancement_slider.setValue(80)
            widget.volume_tone_slider.setValue(90)
            widget.volume_surface_refine_check.setChecked(True)
            widget.volume_clip_plane_check.setChecked(True)
            widget.volume_clip_plane_depth_slider.setValue(62)
            widget.render_volume_preview()

            state = fake_canvas.render_state_kwargs[-1]
            self.assertAlmostEqual(state["enhancement"], 0.8)
            self.assertAlmostEqual(state["tone_gamma"], 0.9)
            self.assertTrue(state["surface_refine"])
            self.assertTrue(state["clip_plane_enabled"])
            self.assertAlmostEqual(state["clip_plane_depth"], 0.62)
            self.assertEqual(len(state["clip_plane_normal"]), 3)
            self.assertIn("Clip plane 62%", widget.volume_canvas_overlay_text())
            self.assertIn("Detail enhancement 80%", widget.volume_canvas_overlay_text())

            widget._volume_render_mode = "drag"
            widget.render_volume_preview()
            self.assertEqual(fake_canvas.render_state_kwargs[-1]["enhancement"], 0.0)
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_masked_volume_preview_is_cached_for_interaction_reuse(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        try:
            preview = np.arange(2 * 5 * 5, dtype=np.uint8).reshape((2, 5, 5))
            mask = np.zeros_like(preview, dtype=np.uint8)
            mask[:, 1:4, 1:4] = 1

            first = widget._masked_volume_preview(preview, mask)
            second = widget._masked_volume_preview(preview, mask)

            self.assertIs(first, second)
            self.assertEqual(len(widget._volume_masked_preview_cache), 1)
            outside = first.copy()
            outside[:, 1:4, 1:4] = 0
            self.assertEqual(int(outside.sum()), 0)
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
            self.assertIn("1. 定位部位", section_titles)
            self.assertIn("2. 生成部位 mask", section_titles)
            self.assertIn("3. 输出与管理", section_titles)
            self.assertEqual(widget.label_role_combo.itemText(widget.label_role_combo.findData("manual_truth")), "人工真值")
            self.assertIn("只读基准层", widget.label_role_help_label.text())
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_tif_volume_canvas_factory_reports_gpu_or_cpu_renderer(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TAXAMASK_TIF_GPU_VOLUME_PREVIEW", None)
            os.environ.pop("TAXAMASK_TIF_EMBEDDED_QOPENGLWIDGET", None)
            canvas, renderer, warning = create_tif_volume_canvas()
        try:
            self.assertIn(renderer, {"gpu", "cpu"})
            self.assertEqual(canvas.objectName(), "tifVolumeCanvas")
            self.assertNotIsInstance(canvas, QOpenGLWidget)
            if renderer == "gpu":
                self.assertEqual(canvas.property("tifVolumeRenderer"), "gpu-offscreen")
                self.assertEqual(warning, "")
            else:
                self.assertIsInstance(canvas, TifVolumeCanvas)
                self.assertIsInstance(warning, str)
        finally:
            canvas.deleteLater()

    def test_tif_volume_canvas_factory_can_disable_gpu_preview(self):
        with patch.dict(os.environ, {"TAXAMASK_TIF_GPU_VOLUME_PREVIEW": "0"}, clear=False):
            canvas, renderer, warning = create_tif_volume_canvas()
        try:
            self.assertEqual(renderer, "cpu")
            self.assertEqual(canvas.objectName(), "tifVolumeCanvas")
            self.assertIsInstance(canvas, TifVolumeCanvas)
            self.assertIn("disabled", warning)
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
