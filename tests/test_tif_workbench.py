import os
import sys
import tempfile
import unittest
import json
import ast
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np
import tifffile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

has_pyside6 = False

try:
    from PySide6.QtCore import QEvent, QPointF, Qt, QThread
    from PySide6.QtGui import QColor, QPixmap
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QSizePolicy, QTextEdit, QTreeWidgetItem, QWidget
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
        QDialog = None
        QMessageBox = None
        QPointF = None
        Qt = None
        QWidget = None
    else:
        raise
else:
    from PySide6.QtWidgets import QTreeWidget

    from AntSleap.core.tif_part_extraction import add_polygon_keyframe, crop_volume_to_part, read_contours_json, write_contours_json
    from AntSleap.core.tif_materials import upsert_material
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.core.tif_volume_io import load_volume_sidecar, write_volume_sidecar
    from AntSleap.core.tif_local_axis_reslice import compute_local_frame, export_part_reslice
    from AntSleap.core.tif_local_axis_ai import LOCAL_AXIS_MODEL_MANIFEST_SCHEMA_VERSION, export_local_axis_training_manifest
    from tests.test_tif_backend import make_predict_ready_project, make_train_ready_project
    from AntSleap.ui.tif_gpu_volume_canvas import gpu_volume_canvas_available, gpu_volume_offscreen_available, gpu_volume_unavailable_reason
    from AntSleap.ui.tif_local_axis_model_panel import TifLocalAxisModelPanel
    from AntSleap.ui.tif_local_axis_review_queue import TifLocalAxisReviewQueueWidget
    from AntSleap.ui.tif_workbench import (
        TifBatchImportWorker,
        TifConfirmPartRoiWorker,
        TifLabelAutoSaveWorker,
        TifMaterializeWorker,
        TifTrainingResultDialog,
        TifVolumeCanvas,
        TifWorkbenchWidget,
        _tif_write_label_slice_snapshots,
        _tif_canvas_background,
        create_tif_volume_canvas,
        summarize_tif_training_result,
    )
    from AntSleap.ui.tif_workbench_translations import TIF_TRANSLATIONS

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
    def __init__(self, button, buttons, x, y, modifiers=None):
        self._button = button
        self._buttons = buttons
        self._modifiers = modifiers if modifiers is not None else (Qt.NoModifier if Qt is not None else 0)
        self._position = QPointF(float(x), float(y)) if QPointF is not None else (float(x), float(y))
        self.accepted = False

    def button(self):
        return self._button

    def buttons(self):
        return self._buttons

    def position(self):
        return self._position

    def modifiers(self):
        return self._modifiers

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


class FakeProgressDialog:
    instances = []

    def __init__(self, label_text="", cancel_text="", minimum=0, maximum=100, parent=None):
        self.label_text = label_text
        self.cancel_text = cancel_text
        self.minimum = minimum
        self.maximum = maximum
        self.value = minimum
        self.parent = parent
        self.window_title = ""
        self.auto_close = None
        self.auto_reset = None
        self.minimum_duration = None
        self.window_modality = None
        self.shown = False
        self.closed = False
        self.deleted = False
        self.cancel_button = object()
        FakeProgressDialog.instances.append(self)

    def setWindowTitle(self, title):
        self.window_title = title

    def setCancelButton(self, button):
        self.cancel_button = button

    def setAutoClose(self, enabled):
        self.auto_close = bool(enabled)

    def setAutoReset(self, enabled):
        self.auto_reset = bool(enabled)

    def setMinimumDuration(self, duration):
        self.minimum_duration = int(duration)

    def setWindowModality(self, modality):
        self.window_modality = modality

    def setRange(self, minimum, maximum):
        self.minimum = int(minimum)
        self.maximum = int(maximum)

    def setValue(self, value):
        self.value = int(value)

    def setLabelText(self, text):
        self.label_text = text

    def show(self):
        self.shown = True

    def close(self):
        self.closed = True

    def deleteLater(self):
        self.deleted = True


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

    def _wait_for_local_axis_export(self, widget, timeout_ms=10000):
        deadline = datetime.now().timestamp() + (float(timeout_ms) / 1000.0)
        while widget._local_axis_reslice_export_running():
            self.app.processEvents()
            if datetime.now().timestamp() > deadline:
                raise AssertionError("Timed out waiting for local axis reslice export")
        self.app.processEvents()

    def _wait_for_label_manual_save(self, widget, timeout_ms=5000):
        deadline = datetime.now().timestamp() + (float(timeout_ms) / 1000.0)
        while widget._label_manual_save_running():
            self.app.processEvents()
            if datetime.now().timestamp() > deadline:
                raise AssertionError("Timed out waiting for label manual save")
        self.app.processEvents()

    def test_tif_workbench_theme_switch_updates_panels_and_canvas_background(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget.set_theme("dark")
            dark_style = widget.styleSheet()
            self.assertIn("#070D1A", dark_style)
            self.assertIn(_tif_canvas_background("dark"), dark_style)
            self.assertEqual(widget.canvas.current_theme, "dark")
            self.assertEqual(widget.volume_canvas.current_theme, "dark")

            widget.set_theme("light")
            light_style = widget.styleSheet()
            self.assertIn("#F5F8FC", light_style)
            self.assertIn("#FFFFFF", light_style)
            self.assertIn(_tif_canvas_background("light"), light_style)
            self.assertIn("QTextEdit#tifLogConsole QScrollBar:vertical", light_style)
            self.assertIn("QScrollArea#tifInspectorScroll QScrollBar:vertical", light_style)
            self.assertIn("#EEF4FA", light_style)
            self.assertIn("#B9CADB", light_style)
            self.assertEqual(widget.canvas.current_theme, "light")
            self.assertEqual(widget.volume_canvas.current_theme, "light")
            self.assertNotIn("#07090A", light_style)
        finally:
            widget.deleteLater()

    def test_cpu_volume_canvas_recomposes_cached_pixmap_when_theme_changes(self):
        canvas = TifVolumeCanvas()
        try:
            canvas.resize(120, 100)
            source = QPixmap(20, 20)
            source.fill(QColor("#DCE4E8"))

            canvas.set_theme("light")
            canvas.set_volume_pixmap(source)
            light_background = canvas.pixmap().toImage().pixelColor(0, 0).name().upper()

            canvas.set_theme("dark")
            dark_background = canvas.pixmap().toImage().pixelColor(0, 0).name().upper()

            self.assertEqual(light_background, _tif_canvas_background("light").upper())
            self.assertEqual(dark_background, _tif_canvas_background("dark").upper())
        finally:
            canvas.deleteLater()

    def _canvas_xy_for_image_pixel(self, widget, x, y):
        point = widget.canvas._image_point_to_widget_point([float(x) + 0.5, float(y) + 0.5])
        self.assertIsNotNone(point)
        return point

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
                [0.5, 1.5, 0.0],
                [0.5, 1.5, 3.0],
                roll_reference={
                    "point_a": {"role": "left_eye", "zyx": [0.0, 1.0, 1.5]},
                    "point_b": {"role": "right_eye", "zyx": [1.0, 1.0, 1.5]},
                },
            )
            export_result = export_part_reslice(
                manager,
                "01-0101-reslice",
                "head",
                {"reslice_id": "head_axis_001", "template_id": "head", "local_frame": frame},
            )
            exported_image = tifffile.imread(export_result["image_path"])
            expected_reslice_shape = tuple(exported_image.shape)
            self.assertEqual(expected_reslice_shape, (4, 4, 2))
            part_image = load_volume_sidecar(root / "reslice_tree" / manager.get_part("01-0101-reslice", "head")["image"]["path"])
            self.assertFalse(np.array_equal(exported_image, np.asarray(part_image)))

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
                self.assertEqual(tuple(widget.image_volume.shape), expected_reslice_shape)
                np.testing.assert_array_equal(np.asarray(widget.image_volume), exported_image)
                self.assertFalse(np.array_equal(np.asarray(widget.image_volume), np.asarray(part_image)))
                self.assertIn("Reslice ID: head_axis_001", widget.metadata_label.text())
                self.assertIn("Image: specimens/01-0101-reslice/parts/head/reslices/head_axis_001/image.tif", widget.metadata_label.text())
                self.assertIn("Metadata:", widget.metadata_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_select_volume_tree_item_targets_specific_reslice(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                frame = compute_local_frame(
                    [1.5, 3.0, 3.0],
                    [0.0, 3.0, 3.0],
                    [3.0, 3.0, 3.0],
                    roll_reference={
                        "point_a": {"role": "left_eye", "zyx": [1.5, 2.0, 2.0]},
                        "point_b": {"role": "right_eye", "zyx": [1.5, 4.0, 2.0]},
                    },
                )
                second_result = export_part_reslice(
                    widget.project,
                    "01-0101-21",
                    "head",
                    {
                        "reslice_id": "head_axis_saved",
                        "template_id": "head",
                        "source_axis": {
                            "axis_id": "source_z_axis",
                            "role": "source_direction_reference",
                            "start_zyx": [0.0, 3.0, 3.0],
                            "end_zyx": [3.0, 3.0, 3.0],
                            "locked": True,
                        },
                        "editable_axis": {
                            "axis_id": "local_output_z_axis",
                            "role": "editable_output_axis",
                            "source_axis_id": "source_z_axis",
                            "start_zyx": [0.0, 3.0, 3.0],
                            "end_zyx": [3.0, 3.0, 3.0],
                        },
                        "local_frame": frame,
                    },
                )
                export_part_reslice(
                    widget.project,
                    "01-0101-21",
                    "head",
                    {
                        "reslice_id": "head_axis_second",
                        "template_id": "head",
                        "local_frame": frame,
                    },
                )

                widget.refresh_project()
                self.assertTrue(widget._select_volume_tree_item("01-0101-21", "part_reslice", "head", "head_axis_second"))

                self.assertEqual(widget.current_reslice_id, "head_axis_second")
                np.testing.assert_array_equal(np.asarray(widget.image_volume), tifffile.imread(second_result["image_path"]))
                overlays = widget._local_axis_volume_overlays()
                labels = [item["label"] for item in overlays]
                self.assertIn("source Z", labels)
                self.assertIn("output Z", labels)
                self.assertIn("Roll reference", labels)
                self.assertIn("Reslice ID: head_axis_second", widget.metadata_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_select_volume_tree_item_does_not_fallback_to_wrong_reslice(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                frame = compute_local_frame(
                    [1.5, 3.0, 3.0],
                    [0.0, 3.0, 3.0],
                    [3.0, 3.0, 3.0],
                    roll_reference={
                        "point_a": {"role": "left_eye", "zyx": [1.5, 2.0, 2.0]},
                        "point_b": {"role": "right_eye", "zyx": [1.5, 4.0, 2.0]},
                    },
                )
                export_part_reslice(
                    widget.project,
                    "01-0101-21",
                    "head",
                    {"reslice_id": "head_axis_saved", "template_id": "head", "local_frame": frame},
                )
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")

                self.assertFalse(widget._select_volume_tree_item("01-0101-21", "part_reslice", "head", "missing_reslice"))
                self.assertEqual(widget.current_volume_scope, "part")
                self.assertEqual(widget.current_reslice_id, "")
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_select_volume_tree_item_reports_missing_reslice_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")

                self.assertFalse(widget._select_volume_tree_item("01-0101-21", "part_reslice", "head", "not_created_yet"))
                self.assertEqual(widget.current_volume_scope, "part")
                self.assertEqual(widget.current_reslice_id, "")
            finally:
                widget.close_project()
                widget.deleteLater()

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
                self.assertEqual(widget.btn_local_axis_reslice.text(), "Export confirmed reslice")
                self.assertTrue(widget.btn_export_local_axis_training_manifest.isEnabled())
                self.assertIsNone(widget.findChild(QWidget, "tifLocalAxisModelsButton"))
                self.assertIsNone(widget.findChild(QWidget, "tifLocalAxisModelsInlineButton"))
                self.assertIsNone(widget.findChild(QWidget, "tifPredictLocalAxisGlobalButton"))
                self.assertIsNone(widget.findChild(QWidget, "tifPredictLocalAxisFrameButton"))
                self.assertFalse(hasattr(widget, "open_local_axis_reslice_dialog"))
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
                self.assertEqual(widget.part_bbox_edit.text(), "")
                self.assertEqual(widget.current_roi_overlay_rects(), [])

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
                widget.slice_slider.setValue(2)
                widget.btn_part_draw_roi.setChecked(True)
                widget.canvas.resize(480, 360)
                widget.render_current_slice()
                start = widget.canvas._image_rect_to_widget_rect([2, 2, 3, 3]).center()
                end = widget.canvas._image_rect_to_widget_rect([5, 5, 6, 6]).center()

                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, start.x(), start.y()))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end.x(), end.y()))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, end.x(), end.y()))

                self.assertEqual(widget.part_bbox_edit.text(), "2,3,2,6,2,6")
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
                widget.slice_slider.setValue(3)
                widget.btn_part_draw_roi.setChecked(True)
                widget.canvas.resize(480, 360)
                widget.render_current_slice()
                start = widget.canvas._image_rect_to_widget_rect([0, 0, 1, 1]).center()
                end = widget.canvas._image_rect_to_widget_rect([7, 7, 8, 8]).center()

                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, start.x(), start.y()))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end.x(), end.y()))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, end.x(), end.y()))
                roi = widget.save_part_roi_draft()

                self.assertEqual(widget.active_part_roi_id, "head_roi")
                self.assertEqual(roi["bbox_zyx"], [[1, 4], [0, 8], [0, 8]])
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

    def test_confirm_saved_roi_uses_latest_bbox_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                widget.part_bbox_edit.setText("1,2,2,5,2,5")
                module_path = "AntSleap.ui.tif_workbench.TifPartNameDialog"
                FakePartNameDialog.queue = [("head_roi", "Head ROI", True)]
                with patch(module_path, FakePartNameDialog):
                    roi = widget.save_part_roi_draft()
                self.assertEqual(roi["bbox_zyx"], [[1, 2], [2, 5], [2, 5]])

                widget.part_bbox_edit.setText("1,4,1,6,1,7")
                FakePartNameDialog.queue = [("head", "Head", True)]
                with patch(module_path, FakePartNameDialog):
                    widget.confirm_part_roi_to_part()

                part = widget.project.get_part("01-0101-21", "head")
                roi = widget.project.get_part_roi("01-0101-21", "head_roi")
                self.assertEqual(part["parent_bbox_zyx"], [[1, 4], [1, 6], [1, 7]])
                self.assertEqual(roi["bbox_zyx"], [[1, 4], [1, 6], [1, 7]])
                self.assertEqual(roi["status"], "part_created")
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_saved_roi_draft_autosaves_later_dragged_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                widget.part_bbox_edit.setText("1,2,2,5,2,5")
                module_path = "AntSleap.ui.tif_workbench.TifPartNameDialog"
                FakePartNameDialog.queue = [("head_roi", "Head ROI", True)]
                with patch(module_path, FakePartNameDialog):
                    widget.save_part_roi_draft()

                widget.slice_slider.setValue(3)
                widget.btn_part_draw_roi.setChecked(True)
                widget.canvas.resize(480, 360)
                widget.render_current_slice()
                start = widget.canvas._image_rect_to_widget_rect([1, 1, 2, 2]).center()
                end = widget.canvas._image_rect_to_widget_rect([6, 6, 7, 7]).center()

                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, start.x(), start.y()))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end.x(), end.y()))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, end.x(), end.y()))

                roi = widget.project.get_part_roi("01-0101-21", "head_roi")
                self.assertEqual(widget.part_bbox_edit.text(), "1,4,1,7,1,7")
                self.assertEqual(roi["bbox_zyx"], [[1, 4], [1, 7], [1, 7]])
                self.assertEqual(roi["status"], "draft")
                self.assertIn("saved to draft", widget.training_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_confirm_roi_initializes_part_mask_from_key_slice_rect_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.btn_part_draw_roi.setChecked(True)
                widget.canvas.resize(480, 360)

                for z_index, rect in ((0, [3, 3, 5, 5]), (2, [1, 1, 7, 7]), (4, [3, 3, 5, 5])):
                    widget.slice_slider.setValue(z_index)
                    widget.render_current_slice()
                    start = widget.canvas._image_rect_to_widget_rect([rect[0], rect[1], rect[0] + 1, rect[1] + 1]).center()
                    end = widget.canvas._image_rect_to_widget_rect([rect[2] - 1, rect[3] - 1, rect[2], rect[3]]).center()
                    widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, start.x(), start.y()))
                    widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end.x(), end.y()))
                    widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, end.x(), end.y()))

                module_path = "AntSleap.ui.tif_workbench.TifPartNameDialog"
                FakePartNameDialog.queue = [("head", "Head", True)]
                with patch(module_path, FakePartNameDialog):
                    widget.confirm_part_roi_to_part()

                part = widget.project.get_part("01-0101-21", "head")
                self.assertEqual(part["parent_bbox_zyx"], [[0, 5], [1, 7], [1, 7]])
                mask = np.asarray(load_volume_sidecar(widget.project.to_absolute(part["mask"]["path"]), mmap_mode="r")).copy()
                self.assertEqual(tuple(mask.shape), (5, 6, 6))
                self.assertEqual(int(np.count_nonzero(mask[0])), 4)
                self.assertEqual(int(np.count_nonzero(mask[2])), 36)
                self.assertEqual(int(np.count_nonzero(mask[4])), 4)
                self.assertLess(int(np.count_nonzero(mask)), int(np.prod(mask.shape)))
                self.assertEqual(part["status"], "mask_preview")
                self.assertEqual(part.get("view_settings", {}).get("volume_mask_mode"), "masked_image")
                contours = read_contours_json(widget.project.to_absolute(part["contours_path"]))
                self.assertEqual(contours["keyframes"], [])
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_confirm_roi_initializes_part_mask_from_full_volume_freehand_contours(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.part_bbox_edit.setText("0,5,0,8,0,8")
                widget.part_mask_keyframes = [
                    {
                        "axis": "z",
                        "slice_index": 1,
                        "polygon": [[2, 2], [5, 2], [5, 5], [2, 5]],
                        "source": "manual_freehand",
                    },
                    {
                        "axis": "z",
                        "slice_index": 3,
                        "polygon": [[1, 1], [6, 1], [6, 6], [1, 6]],
                        "source": "manual_freehand",
                    },
                ]

                module_path = "AntSleap.ui.tif_workbench.TifPartNameDialog"
                FakePartNameDialog.queue = [("head", "Head", True)]
                with patch(module_path, FakePartNameDialog):
                    widget.confirm_part_roi_to_part()

                part = widget.project.get_part("01-0101-21", "head")
                self.assertEqual(part["parent_bbox_zyx"], [[1, 4], [1, 7], [1, 7]])
                self.assertEqual(part["status"], "mask_preview")
                self.assertEqual(part.get("view_settings", {}).get("volume_mask_mode"), "masked_image")
                self.assertEqual(part.get("metadata", {}).get("full_volume_mask_source"), "manual_freehand_key_slices")
                self.assertEqual(part.get("metadata", {}).get("full_volume_mask_keyframe_count"), 2)

                mask = np.asarray(load_volume_sidecar(widget.project.to_absolute(part["mask"]["path"]), mmap_mode="r")).copy()
                self.assertEqual(tuple(mask.shape), (3, 6, 6))
                self.assertGreater(int(np.count_nonzero(mask)), 0)
                self.assertLess(int(np.count_nonzero(mask)), int(np.prod(mask.shape)))

                contours = read_contours_json(widget.project.to_absolute(part["contours_path"]))
                self.assertEqual(len(contours["keyframes"]), 2)
                self.assertEqual([item["slice_index"] for item in contours["keyframes"]], [0, 2])
                self.assertEqual(contours["keyframes"][0]["polygon"], [[1, 1], [4, 1], [4, 4], [1, 4]])
                self.assertEqual(widget.project.list_parts("01-0101-21")[0]["part_id"], "head")
                self.assertNotIn("Full-volume contour mask not initialized", widget.training_status_label.text())
                self.assertIn("Full-volume contour mask initialized from 2 key slice", widget.training_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_full_volume_mask_preview_enables_accept_and_creates_part_mask(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.part_bbox_edit.setText("0,5,0,8,0,8")
                widget.part_mask_keyframes = [
                    {
                        "axis": "z",
                        "slice_index": 1,
                        "polygon": [[2, 2], [5, 2], [5, 5], [2, 5]],
                        "source": "manual_freehand",
                    },
                    {
                        "axis": "z",
                        "slice_index": 3,
                        "polygon": [[1, 1], [6, 1], [6, 6], [1, 6]],
                        "source": "manual_freehand",
                    },
                ]

                widget.preview_part_mask_from_keyframes()

                self.assertIsNotNone(widget.part_preview_mask)
                self.assertTrue(widget.btn_accept_part_mask.isEnabled())
                widget.accept_part_mask_preview()
                self.assertTrue(widget.part_mask_preview_accepted)
                self.assertIn("Confirm ROI", widget.training_status_label.text())

                module_path = "AntSleap.ui.tif_workbench.TifPartNameDialog"
                FakePartNameDialog.queue = [("head", "Head", True)]
                with patch(module_path, FakePartNameDialog), \
                     patch("AntSleap.ui.tif_workbench.build_preview_mask_from_contours") as build_mock:
                    widget.confirm_part_roi_to_part()

                build_mock.assert_not_called()
                part = widget.project.get_part("01-0101-21", "head")
                mask = np.asarray(load_volume_sidecar(widget.project.to_absolute(part["mask"]["path"]), mmap_mode="r")).copy()
                self.assertGreater(int(np.count_nonzero(mask)), 0)
                self.assertEqual(part["status"], "mask_preview")
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_large_part_mask_preview_starts_background_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.part_bbox_edit.setText("0,5,0,8,0,8")
                widget.part_mask_keyframes = [
                    {
                        "axis": "z",
                        "slice_index": 1,
                        "polygon": [[2, 2], [5, 2], [5, 5], [2, 5]],
                        "source": "manual_freehand",
                    },
                    {
                        "axis": "z",
                        "slice_index": 3,
                        "polygon": [[1, 1], [6, 1], [6, 6], [1, 6]],
                        "source": "manual_freehand",
                    },
                ]

                starts = []

                def fake_start(contours, shape, context):
                    starts.append((contours, tuple(shape), context))
                    widget._part_mask_preview_thread = object()
                    widget._set_scope_controls_enabled()

                with patch.object(widget, "_should_build_part_mask_preview_in_background", return_value=True), \
                     patch.object(widget, "_start_part_mask_preview_build", side_effect=fake_start):
                    widget.preview_part_mask_from_keyframes()

                self.assertIsNone(widget.part_preview_mask)
                self.assertEqual(len(starts), 1)
                self.assertEqual(starts[0][2]["scope"], "full")
                self.assertFalse(widget.btn_preview_part_mask.isEnabled())
                self.assertFalse(widget.btn_accept_part_mask.isEnabled())
            finally:
                widget._part_mask_preview_thread = None
                widget.close_project()
                widget.deleteLater()

    def test_large_confirm_roi_starts_background_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.part_bbox_edit.setText("0,5,0,8,0,8")
                starts = []

                def fake_start(request):
                    starts.append(dict(request))
                    widget._confirm_part_roi_thread = object()
                    widget._set_scope_controls_enabled()
                    return True

                module_path = "AntSleap.ui.tif_workbench.TifPartNameDialog"
                FakePartNameDialog.queue = [("head", "Head", True)]
                with patch(module_path, FakePartNameDialog), \
                     patch.object(widget, "_should_confirm_part_roi_in_background", return_value=True), \
                     patch.object(widget, "_start_confirm_part_roi_worker", side_effect=fake_start):
                    widget.confirm_part_roi_to_part()

                self.assertEqual(len(starts), 1)
                self.assertEqual(starts[0]["part_id"], "head")
                self.assertEqual(starts[0]["bbox_zyx"], [[0, 5], [0, 8], [0, 8]])
                self.assertEqual(widget.project.list_parts("01-0101-21"), [])
                self.assertFalse(widget.btn_confirm_part_roi.isEnabled())
                self.assertFalse(widget.btn_preview_part_mask.isEnabled())
            finally:
                widget._confirm_part_roi_thread = None
                widget.close_project()
                widget.deleteLater()

    def test_confirm_roi_background_request_reuses_accepted_preview_mask(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.part_bbox_edit.setText("0,5,0,8,0,8")
                widget.part_mask_keyframes = [
                    {
                        "axis": "z",
                        "slice_index": 1,
                        "polygon": [[2, 2], [5, 2], [5, 5], [2, 5]],
                        "source": "manual_freehand",
                    },
                    {
                        "axis": "z",
                        "slice_index": 3,
                        "polygon": [[1, 1], [6, 1], [6, 6], [1, 6]],
                        "source": "manual_freehand",
                    },
                ]
                widget.preview_part_mask_from_keyframes()
                preview_mask = widget.part_preview_mask
                self.assertIsNotNone(preview_mask)
                widget.accept_part_mask_preview()

                starts = []

                def fake_start(request):
                    starts.append(dict(request))
                    widget._confirm_part_roi_thread = object()
                    widget._set_scope_controls_enabled()
                    return True

                module_path = "AntSleap.ui.tif_workbench.TifPartNameDialog"
                FakePartNameDialog.queue = [("head", "Head", True)]
                with patch(module_path, FakePartNameDialog), \
                     patch.object(widget, "_should_confirm_part_roi_in_background", return_value=True), \
                     patch.object(widget, "_start_confirm_part_roi_worker", side_effect=fake_start):
                    widget.confirm_part_roi_to_part()

                self.assertEqual(len(starts), 1)
                self.assertIs(starts[0]["accepted_preview_mask"], preview_mask)
                self.assertEqual(starts[0]["bbox_zyx"], widget.part_mask_preview_bbox)
                self.assertEqual(starts[0]["mask_bbox_zyx"], widget.part_mask_preview_bbox)
                self.assertEqual(len((starts[0]["mask_contours"] or {}).get("keyframes", [])), 2)
            finally:
                widget._confirm_part_roi_thread = None
                widget.close_project()
                widget.deleteLater()

    def test_confirm_roi_worker_creates_part_and_writes_accepted_mask(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.part_bbox_edit.setText("0,5,0,8,0,8")
                widget.part_mask_keyframes = [
                    {
                        "axis": "z",
                        "slice_index": 1,
                        "polygon": [[2, 2], [5, 2], [5, 5], [2, 5]],
                        "source": "manual_freehand",
                    },
                    {
                        "axis": "z",
                        "slice_index": 3,
                        "polygon": [[1, 1], [6, 1], [6, 6], [1, 6]],
                        "source": "manual_freehand",
                    },
                ]
                widget.preview_part_mask_from_keyframes()
                widget.accept_part_mask_preview()
                request = widget._build_confirm_part_roi_request(
                    None,
                    widget.part_mask_preview_bbox,
                    "head",
                    "Head",
                    [],
                    widget._full_volume_contours_payload(),
                    widget.part_mask_preview_bbox,
                )
                worker = TifConfirmPartRoiWorker(widget.project, request)
                finished = []
                failed = []
                worker.finished.connect(lambda result: finished.append(result))
                worker.failed.connect(lambda result: failed.append(result))

                with patch("AntSleap.ui.tif_workbench.build_preview_mask_from_contours") as build_mock:
                    worker.run()

                self.assertFalse(failed)
                self.assertEqual(len(finished), 1)
                build_mock.assert_not_called()
                part = widget.project.get_part("01-0101-21", "head")
                self.assertIsNotNone(part)
                self.assertEqual(part["status"], "mask_preview")
                self.assertEqual(part.get("view_settings", {}).get("volume_mask_mode"), "masked_image")
                mask = np.asarray(load_volume_sidecar(widget.project.to_absolute(part["mask"]["path"]), mmap_mode="r")).copy()
                self.assertTrue(np.array_equal(mask, request["accepted_preview_mask"]))
                contours = read_contours_json(widget.project.to_absolute(part["contours_path"]))
                self.assertEqual(len(contours["keyframes"]), 2)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_roi_draft_saves_and_restores_full_volume_freehand_contours(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.part_bbox_edit.setText("0,5,0,8,0,8")
                widget.part_mask_keyframes = [
                    {
                        "axis": "z",
                        "slice_index": 2,
                        "polygon": [[2, 2], [5, 2], [5, 5], [2, 5]],
                        "source": "manual_freehand",
                    }
                ]
                module_path = "AntSleap.ui.tif_workbench.TifPartNameDialog"
                FakePartNameDialog.queue = [("head_roi", "Head ROI", True)]
                with patch(module_path, FakePartNameDialog):
                    roi = widget.save_part_roi_draft()

                self.assertEqual(len((roi.get("metadata") or {}).get("part_mask_keyframes", [])), 1)
                self.assertEqual((roi.get("metadata") or {}).get("part_mask_bbox_zyx"), [[2, 3], [2, 6], [2, 6]])

                widget.part_mask_keyframes = []
                widget._load_roi_draft_for_editing(roi)
                widget.slice_slider.setValue(2)

                self.assertEqual(len(widget.part_mask_keyframes), 1)
                self.assertEqual(widget.part_mask_keyframes[0]["slice_index"], 2)
                self.assertTrue(widget.current_contour_overlay_polygons())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_part_mask_preview_ignores_roi_shell_after_adding_new_key_slice(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.btn_part_draw_roi.setChecked(True)
                widget.canvas.resize(480, 360)
                for z_index, rect in ((0, [3, 3, 5, 5]), (2, [1, 1, 7, 7]), (4, [3, 3, 5, 5])):
                    widget.slice_slider.setValue(z_index)
                    widget.render_current_slice()
                    start = widget.canvas._image_rect_to_widget_rect([rect[0], rect[1], rect[0] + 1, rect[1] + 1]).center()
                    end = widget.canvas._image_rect_to_widget_rect([rect[2] - 1, rect[3] - 1, rect[2], rect[3]]).center()
                    widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, start.x(), start.y()))
                    widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end.x(), end.y()))
                    widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, end.x(), end.y()))

                module_path = "AntSleap.ui.tif_workbench.TifPartNameDialog"
                FakePartNameDialog.queue = [("head", "Head", True)]
                with patch(module_path, FakePartNameDialog):
                    widget.confirm_part_roi_to_part()

                part = widget.project.get_part("01-0101-21", "head")
                contours_path = widget.project.to_absolute(part["contours_path"])
                self.assertEqual(read_contours_json(contours_path)["keyframes"], [])

                widget.slice_slider.setValue(2)
                widget.add_current_rect_keyframe()
                widget.preview_part_mask_from_keyframes()

                contours = read_contours_json(contours_path)
                self.assertEqual(len(contours["keyframes"]), 1)
                self.assertEqual(contours["keyframes"][0]["source"], "rectangle")
                self.assertIsNotNone(widget.part_preview_mask)
                self.assertEqual(int(np.count_nonzero(widget.part_preview_mask[0])), 0)
                self.assertGreater(int(np.count_nonzero(widget.part_preview_mask[2])), 0)
                self.assertEqual(int(np.count_nonzero(widget.part_preview_mask[4])), 0)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_part_mask_preview_filters_legacy_roi_shell_keyframes(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 5], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                part = widget.project.get_part("01-0101-21", "head")
                contours_path = widget.project.to_absolute(part["contours_path"])
                contours = read_contours_json(contours_path)
                contours = add_polygon_keyframe(
                    contours,
                    0,
                    [[1, 1], [4, 1], [4, 4], [1, 4]],
                    axis="z",
                    author="taxamask_roi_shell",
                    source="rectangle",
                )
                contours = add_polygon_keyframe(
                    contours,
                    2,
                    [[2, 2], [5, 2], [5, 5], [2, 5]],
                    axis="z",
                    author="taxamask_ui_freehand",
                    source="manual_freehand",
                )
                write_contours_json(contours_path, contours)

                widget.slice_slider.setValue(0)
                self.assertFalse(widget.current_contour_overlay_polygons())

                widget.preview_part_mask_from_keyframes()

                self.assertIsNotNone(widget.part_preview_mask)
                self.assertEqual(int(np.count_nonzero(widget.part_preview_mask[0])), 0)
                self.assertGreater(int(np.count_nonzero(widget.part_preview_mask[2])), 0)
                self.assertIn("Ignored 1 legacy ROI shell", widget.training_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_clear_part_mask_keyframes_resets_legacy_roi_shell_and_mask(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 5], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                part = widget.project.get_part("01-0101-21", "head")
                contours_path = widget.project.to_absolute(part["contours_path"])
                contours = read_contours_json(contours_path)
                contours = add_polygon_keyframe(
                    contours,
                    0,
                    [[1, 1], [4, 1], [4, 4], [1, 4]],
                    axis="z",
                    author="taxamask_roi_shell",
                    source="rectangle",
                )
                contours = add_polygon_keyframe(
                    contours,
                    3,
                    [[2, 2], [5, 2], [5, 5], [2, 5]],
                    axis="z",
                    author="taxamask_roi_shell",
                    source="rectangle",
                )
                write_contours_json(contours_path, contours)
                mask = load_volume_sidecar(widget.project.to_absolute(part["mask"]["path"]), mmap_mode="r+")
                try:
                    mask[:] = 1
                    if hasattr(mask, "flush"):
                        mask.flush()
                finally:
                    mmap_handle = getattr(mask, "_mmap", None)
                    if mmap_handle is not None:
                        mmap_handle.close()
                widget.part_preview_mask = np.ones(tuple(widget.image_volume.shape), dtype=np.uint16)

                with patch("AntSleap.ui.tif_workbench.QMessageBox.question", return_value=QMessageBox.Yes):
                    self.assertTrue(widget.clear_part_mask_keyframes())

                self.assertEqual(read_contours_json(contours_path)["keyframes"], [])
                reset_source = load_volume_sidecar(widget.project.to_absolute(part["mask"]["path"]), mmap_mode="r")
                try:
                    reset_mask = np.asarray(reset_source).copy()
                finally:
                    mmap_handle = getattr(reset_source, "_mmap", None)
                    if mmap_handle is not None:
                        mmap_handle.close()
                self.assertEqual(int(np.count_nonzero(reset_mask)), 0)
                self.assertIsNone(widget.part_preview_mask)
                self.assertEqual(widget.project.get_part("01-0101-21", "head")["status"], "roi_confirmed")
                self.assertIn("Cleared 2 key slice", widget.training_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_create_part_button_is_not_in_locate_part_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                self.assertEqual(widget.part_task_layout.indexOf(widget.btn_create_part), -1)
                self.assertFalse(widget.btn_create_part.isEnabled())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_rectangular_keyframe_button_is_not_in_part_mask_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                self.assertEqual(widget.part_mask_section.layout().indexOf(widget.btn_add_rect_keyframe), -1)
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

    def test_first_roi_drag_does_not_use_default_bbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                widget.slice_slider.setValue(2)
                widget.btn_part_draw_roi.setChecked(True)
                widget.canvas.resize(480, 360)
                widget.render_current_slice()
                start = widget.canvas._image_rect_to_widget_rect([2, 2, 3, 3]).center()
                end = widget.canvas._image_rect_to_widget_rect([5, 5, 6, 6]).center()

                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, start.x(), start.y()))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end.x(), end.y()))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, end.x(), end.y()))

                self.assertEqual(widget.part_bbox_edit.text(), "2,3,2,6,2,6")
                self.assertIn("ROI bbox updated", widget.training_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_roi_drag_accumulates_boxes_in_one_slice_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                widget.btn_part_draw_roi.setChecked(True)
                widget.canvas.resize(480, 360)

                widget.slice_slider.setValue(1)
                widget.render_current_slice()
                first_start = widget.canvas._image_rect_to_widget_rect([1, 2, 2, 3]).center()
                first_end = widget.canvas._image_rect_to_widget_rect([4, 5, 5, 6]).center()
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, first_start.x(), first_start.y()))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, first_end.x(), first_end.y()))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, first_end.x(), first_end.y()))

                widget.slice_slider.setValue(3)
                widget.render_current_slice()
                second_start = widget.canvas._image_rect_to_widget_rect([3, 1, 4, 2]).center()
                second_end = widget.canvas._image_rect_to_widget_rect([6, 4, 7, 5]).center()
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, second_start.x(), second_start.y()))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, second_end.x(), second_end.y()))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, second_end.x(), second_end.y()))

                self.assertEqual(widget.part_bbox_edit.text(), "1,4,1,6,1,7")
                self.assertEqual(
                    [(item["slice_index"], item["rect"]) for item in widget.part_roi_keyframes],
                    [(1, [1, 2, 5, 6]), (3, [3, 1, 7, 5])],
                )
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_roi_drag_replaces_key_slice_rect_instead_of_expanding_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=4)
            try:
                widget.btn_part_draw_roi.setChecked(True)
                widget.canvas.resize(480, 360)
                widget.slice_slider.setValue(2)
                widget.render_current_slice()

                first_start = widget.canvas._image_rect_to_widget_rect([1, 1, 2, 2]).center()
                first_end = widget.canvas._image_rect_to_widget_rect([6, 6, 7, 7]).center()
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, first_start.x(), first_start.y()))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, first_end.x(), first_end.y()))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, first_end.x(), first_end.y()))

                second_start = widget.canvas._image_rect_to_widget_rect([2, 2, 3, 3]).center()
                second_end = widget.canvas._image_rect_to_widget_rect([4, 4, 5, 5]).center()
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, second_start.x(), second_start.y()))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, second_end.x(), second_end.y()))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, second_end.x(), second_end.y()))

                self.assertEqual(widget.part_bbox_edit.text(), "2,3,2,5,2,5")
                self.assertEqual(len(widget.part_roi_keyframes), 1)
                self.assertEqual(widget.part_roi_keyframes[0]["rect"], [2, 2, 5, 5])
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_delete_part_volume_from_tree_without_loading_part(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=4)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "brain", [[1, 3], [2, 6], [1, 5]], display_name="Brain")
                part_dir = root / "viewer" / widget.project.part_dir("01-0101-21", "brain")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "full", "")
                self.assertEqual(widget.current_volume_scope, "full")
                self.assertTrue(part_dir.exists())

                with patch.object(widget, "load_part") as load_part, \
                    patch("AntSleap.ui.tif_workbench.QMessageBox.question", return_value=QMessageBox.Yes):
                    self.assertTrue(widget.delete_part_volume("01-0101-21", "brain"))

                load_part.assert_not_called()
                self.assertFalse(part_dir.exists())
                self.assertIsNone(widget.project.get_part("01-0101-21", "brain", default=None))
                self.assertEqual(widget.current_volume_scope, "full")
                self.assertEqual(widget.current_part_id, "")
                self.assertIn("Deleted part volume Brain", widget.training_status_label.text())
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

    def test_contour_draw_mode_uses_subpixel_points_and_hides_brush_radius_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[1, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.slice_slider.setValue(1)
                widget.brush_size_slider.setValue(31)
                widget.btn_draw_part_contour.setChecked(True)
                widget.canvas.resize(480, 360)
                widget.render_current_slice()

                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.NoButton, Qt.NoButton, widget.canvas.width() / 2, widget.canvas.height() / 2))
                self.assertEqual(widget.canvas._last_annotation_preview, {})

                drawn_points = [[1.25, 1.35], [2.2, 1.05], [4.55, 1.45], [4.85, 3.1], [3.6, 4.65], [1.35, 4.35]]
                points = [widget.canvas._image_point_to_widget_point(point) for point in drawn_points]
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, points[0][0], points[0][1]))
                for point in points[1:]:
                    widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, point[0], point[1]))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, points[-1][0], points[-1][1]))

                contours_path = widget.project.to_absolute(widget.project.get_part("01-0101-21", "head")["contours_path"])
                contour = read_contours_json(contours_path)["keyframes"][0]
                self.assertEqual(len(contour["polygon"]), len(drawn_points))
                for saved, drawn in zip(contour["polygon"], drawn_points):
                    self.assertAlmostEqual(saved[0], drawn[0], places=2)
                    self.assertAlmostEqual(saved[1], drawn[1], places=2)
                self.assertTrue(any(isinstance(value, float) and not float(value).is_integer() for point in contour["polygon"] for value in point))
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

    def test_part_volume_3d_left_drag_uses_full_volume_pitch_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                mode_index = widget.display_mode_combo.findData("volume")
                widget.display_mode_combo.setCurrentIndex(mode_index)
                self.assertEqual(widget.current_volume_scope, "full")

                full_pitch = widget._volume_pitch
                widget.volume_canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, 220, 170))
                widget.volume_canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, 220, 150))
                widget.volume_canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, 220, 150))
                self.assertGreater(widget._volume_pitch, full_pitch)
                expected_delta = widget._volume_pitch - full_pitch

                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.display_mode_combo.setCurrentIndex(mode_index)
                self.assertEqual(widget.current_volume_scope, "part")

                part_pitch = widget._volume_pitch
                widget.volume_canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, 220, 170))
                widget.volume_canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, 220, 150))
                widget.volume_canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, 220, 150))

                self.assertGreater(widget._volume_pitch, part_pitch)
                self.assertAlmostEqual(widget._volume_pitch - part_pitch, expected_delta)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_result_comparison_exports_current_rendering_screenshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.task_tabs.setCurrentWidget(widget.training_mode_tabs)
                widget.training_mode_tabs.setCurrentWidget(widget.result_compare_page)
                widget.result_region_combo.setCurrentIndex(widget.result_region_combo.findData(2))
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))
                output_path = root / "viewer" / "exports" / "render_screenshots" / "manual_output.png"
                with patch("AntSleap.ui.tif_workbench.QFileDialog.getSaveFileName", return_value=(str(output_path), "PNG image (*.png)")):
                    exported = widget.export_current_rendering_screenshot()

                self.assertEqual(exported, str(output_path))
                self.assertTrue(output_path.exists())
                self.assertGreater(output_path.stat().st_size, 0)
                sidecar_path = output_path.with_suffix(".json")
                self.assertTrue(sidecar_path.exists())
                with open(sidecar_path, "r", encoding="utf-8") as handle:
                    metadata = json.load(handle)
                self.assertEqual(metadata["schema_version"], "taxamask_tif_render_screenshot_v1")
                self.assertEqual(metadata["specimen_id"], "01-0101-21")
                self.assertEqual(metadata["part_id"], "head")
                self.assertEqual(metadata["region_id"], 2)
                self.assertTrue(metadata["region_slug"].startswith("region_2"))
                self.assertTrue(metadata["region_name"])
                self.assertEqual(metadata["label_role"], "manual_truth")
                self.assertEqual(metadata["display_mode"], "volume")
                self.assertTrue(metadata["project_relative_image_path"].endswith("manual_output.png"))
                self.assertIn("Exported current rendering screenshot", widget.training_status_label.text())
                self.assertIn("region_2", widget._current_result_region_slug())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_result_comparison_lists_region_counts_and_opens_selected_part_3d(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("result_compare", root / "result_compare")
            manager.add_or_update_label_schema(
                "brain_regions",
                labels=[
                    {"id": 1, "name": "mushroom_body", "display_name": "Mushroom body", "color": "#ff0000"},
                    {"id": 2, "name": "antennal_lobe", "display_name": "Antennal lobe", "color": "#00ff00"},
                ],
                user_defined_part_name="brain",
                save=False,
            )
            for specimen_id, display_name, manual_count, editable_count in (
                ("01-0101-a", "A", 3, 5),
                ("01-0101-b", "B", 7, 9),
            ):
                manager.create_specimen_scaffold(
                    specimen_id,
                    material_map={
                        "materials": [
                            {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                            {"id": 1, "name": "mushroom_body", "display_name": "Mushroom body", "trainable": True},
                            {"id": 2, "name": "antennal_lobe", "display_name": "Antennal lobe", "trainable": True},
                        ]
                    },
                )
                specimen = manager.get_specimen(specimen_id)
                specimen["display_name"] = display_name
                part_dir = manager.part_dir(specimen_id, "brain")
                image_rel = f"{part_dir}/image.ome.zarr"
                mask_rel = f"{part_dir}/mask.ome.zarr"
                image = np.arange(24, dtype=np.uint8).reshape((2, 3, 4))
                mask = np.ones((2, 3, 4), dtype=np.uint16)
                image_meta = write_volume_sidecar(root / "result_compare" / image_rel, image, role="part_image")
                mask_meta = write_volume_sidecar(root / "result_compare" / mask_rel, mask, role="part_mask")
                manager.add_part(
                    specimen_id,
                    "brain",
                    display_name="Brain",
                    image={"path": image_rel, "format": "ant3d_volume_sidecar", "shape_zyx": image_meta["shape_zyx"], "dtype": image_meta["dtype"]},
                    mask={"path": mask_rel, "format": "ant3d_volume_sidecar", "shape_zyx": mask_meta["shape_zyx"], "dtype": mask_meta["dtype"]},
                    save=False,
                )
                manager.set_part_training_metadata(
                    specimen_id,
                    "brain",
                    user_defined_part_name="brain",
                    label_schema_id="brain_regions",
                    system_status="predicted_pending_review",
                    save=False,
                )
                manual = np.zeros((2, 3, 4), dtype=np.uint16)
                manual.reshape(-1)[:manual_count] = 2
                manual.reshape(-1)[manual_count : manual_count + 2] = 1
                editable = np.zeros((2, 3, 4), dtype=np.uint16)
                editable.reshape(-1)[:editable_count] = 2
                editable.reshape(-1)[editable_count : editable_count + 1] = 1
                manual_rel = f"{part_dir}/labels/manual_truth.ome.zarr"
                editable_rel = f"{part_dir}/labels/editable_ai_result.ome.zarr"
                manual_meta = write_volume_sidecar(root / "result_compare" / manual_rel, manual, role="manual_truth")
                editable_meta = write_volume_sidecar(root / "result_compare" / editable_rel, editable, role="editable_ai_result")
                manager.register_part_label_volume(
                    specimen_id,
                    "brain",
                    "manual_truth",
                    manual_rel,
                    manual_meta["shape_zyx"],
                    manual_meta["dtype"],
                    status="reviewed",
                    save=False,
                )
                manager.register_part_label_volume(
                    specimen_id,
                    "brain",
                    "editable_ai_result",
                    editable_rel,
                    editable_meta["shape_zyx"],
                    editable_meta["dtype"],
                    status="pending_review",
                    save=False,
                )
            manager.save_project()

            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget._select_volume_tree_item("01-0101-a", "part", "brain")
                widget.task_tabs.setCurrentWidget(widget.training_mode_tabs)
                widget.training_mode_tabs.setCurrentWidget(widget.result_compare_page)
                widget.result_region_combo.setCurrentIndex(widget.result_region_combo.findData(2))
                rows = widget.refresh_result_comparison()

                self.assertEqual(len(rows), 2)
                self.assertEqual(widget.result_compare_table.rowCount(), 2)
                self.assertEqual(sum(row["region_voxels"] for row in rows), 10)
                self.assertEqual(sum(row["total_labeled_voxels"] for row in rows), 14)
                self.assertIn("10", widget.result_compare_summary_label.text())
                self.assertIn("14", widget.result_compare_summary_label.text())

                editable_index = widget.result_source_editable_radio
                editable_index.setChecked(True)
                editable_rows = widget.refresh_result_comparison()
                self.assertEqual(sum(row["region_voxels"] for row in editable_rows), 14)
                self.assertEqual(sum(row["total_labeled_voxels"] for row in editable_rows), 16)

                target_row = next(index for index, row in enumerate(editable_rows) if row["ref"]["specimen_id"] == "01-0101-b")
                widget.result_compare_table.selectRow(target_row)
                self.assertTrue(widget.show_selected_result_region_in_3d())

                self.assertEqual(widget.current_specimen_id, "01-0101-b")
                self.assertEqual(widget.current_part_id, "brain")
                self.assertEqual(widget.display_mode, "volume")
                self.assertEqual(widget.volume_mask_combo.currentData(), "masked_image")
                mask = widget._active_result_region_mask_volume()
                self.assertIsNotNone(mask)
                self.assertNotIsInstance(mask, np.ndarray)
                self.assertEqual(tuple(mask.shape), (2, 3, 4))
                self.assertEqual(int(np.count_nonzero(mask[0])), min(9, 12))
                self.assertEqual(int(np.count_nonzero(np.asarray(mask))), 9)
                mask = None
                self.assertIn("Region highlight is ready", widget.training_status_label.text())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_result_comparison_can_open_part_even_when_selected_source_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.project.set_part_training_metadata(
                    "01-0101-21",
                    "head",
                    user_defined_part_name="head",
                    label_schema_id="missing_source_schema",
                    save=False,
                )
                widget.refresh_project()
                widget.task_tabs.setCurrentWidget(widget.training_mode_tabs)
                widget.training_mode_tabs.setCurrentWidget(widget.result_compare_page)
                rows = widget.refresh_result_comparison()
                self.assertEqual(len(rows), 1)
                self.assertFalse(rows[0]["ok"])
                self.assertIn("manual_truth", rows[0]["source_status"])

                widget.result_compare_table.selectRow(0)
                self.assertTrue(widget.open_selected_result_comparison_target())

                self.assertEqual(widget.current_specimen_id, "01-0101-21")
                self.assertEqual(widget.current_part_id, "head")
                self.assertEqual(widget.display_mode, "volume")
                self.assertEqual(widget.volume_mask_combo.currentData(), "image_only")
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_part_switch_defers_result_comparison_counts_until_tab_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                crop_volume_to_part(widget.project, "01-0101-21", "thorax", [[1, 5], [1, 7], [1, 7]], display_name="Thorax")
                for part_id in ("head", "thorax"):
                    part = widget.project.get_part("01-0101-21", part_id)
                    label_rel = f"{widget.project.part_dir('01-0101-21', part_id)}/labels/manual_truth.ome.zarr"
                    label = np.ones(tuple(part["image"]["shape_zyx"]), dtype=np.uint16)
                    label_meta = write_volume_sidecar(root / "viewer" / label_rel, label, role="manual_truth")
                    widget.project.register_part_label_volume(
                        "01-0101-21",
                        part_id,
                        "manual_truth",
                        label_rel,
                        label_meta["shape_zyx"],
                        label_meta["dtype"],
                        status="reviewed",
                        save=False,
                    )
                widget.project.save_project()

                with patch.object(widget, "_label_volume_counts_for_result", side_effect=AssertionError("counts should be deferred")):
                    widget.refresh_project()
                    widget._select_volume_tree_item("01-0101-21", "part", "head")
                    widget._select_volume_tree_item("01-0101-21", "part", "thorax")

                self.assertTrue(getattr(widget, "_result_comparison_stale", False))

                calls = {"count": 0}

                def fake_counts(_record, _region_id):
                    calls["count"] += 1
                    return {"ok": False, "status": "deferred-test", "path": ""}

                with patch.object(widget, "_label_volume_counts_for_result", side_effect=fake_counts):
                    widget.task_tabs.setCurrentWidget(widget.training_mode_tabs)
                    widget.training_mode_tabs.setCurrentWidget(widget.result_compare_page)
                    self.assertFalse(getattr(widget, "_result_comparison_stale", True))

                self.assertGreater(calls["count"], 0)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_reslice_switch_does_not_fallback_to_full_tif_read_when_memmap_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("reslice_no_full_read", root / "reslice_no_full_read")
            manager.create_specimen_scaffold(
                "01-0101-reslice",
                material_map={"materials": [{"id": 0, "name": "background", "display_name": "Background", "trainable": False}]},
            )
            image = np.arange(4 * 6 * 8, dtype=np.uint8).reshape((4, 6, 8))
            image_rel = "specimens/01-0101-reslice/working/image.ome.zarr"
            image_meta = write_volume_sidecar(root / "reslice_no_full_read" / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-reslice", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-reslice", "head", [[1, 3], [2, 6], [1, 5]], display_name="Head")
            reslice_rel = "specimens/01-0101-reslice/parts/head/reslices/bad_axis/image.tif"
            reslice_abs = root / "reslice_no_full_read" / reslice_rel
            reslice_abs.parent.mkdir(parents=True, exist_ok=True)
            tifffile.imwrite(reslice_abs, np.zeros((2, 4, 4), dtype=np.uint8), compression="deflate")
            manager.add_part_reslice(
                "01-0101-reslice",
                "head",
                {
                    "reslice_id": "bad_axis",
                    "display_name": "bad_axis",
                    "status": "exported",
                    "image_path": reslice_rel,
                    "reslice_params": {"output_shape_zyx": [2, 4, 4]},
                },
                save=False,
            )
            manager.save_project()

            widget = TifWorkbenchWidget(manager, "en")
            try:
                with patch("AntSleap.ui.tif_workbench.tifffile.imread", side_effect=AssertionError("full TIF read should be avoided")):
                    widget._select_volume_tree_item("01-0101-reslice", "part_reslice", "head", "bad_axis")

                self.assertIsNone(widget.image_volume)
                self.assertIn("cannot be opened quickly", widget.canvas.text())
                self.assertIn("cannot be opened", widget.log_console.toPlainText())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_copy_source_z_axis_creates_visible_local_axis_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")

                draft = widget.copy_source_z_axis_to_local_axis_draft()

                self.assertIsNotNone(draft)
                self.assertEqual(draft["part_id"], "head")
                self.assertEqual(draft["editable_axis"]["role"], "editable_output_axis")
                self.assertTrue(widget.volume_local_axes_check.isChecked())
                overlays = widget._local_axis_volume_overlays()
                self.assertEqual([item["label"] for item in overlays], ["source Z", "output Z"])
                self.assertEqual(overlays[0]["label_anchor_xy"], overlays[0]["start_xy"])
                self.assertEqual(overlays[1]["label_anchor_xy"], overlays[1]["end_xy"])
                self.assertNotEqual(overlays[0]["label_offset_xy"], overlays[1]["label_offset_xy"])
                self.assertIn("Local axis draft", widget.metadata_label.text())
                self.assertIn("Copied source Z axis", widget.local_axis_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_local_axis_output_endpoint_drag_updates_draft_in_3d_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))
                widget.volume_canvas.resize(480, 360)
                draft = widget.copy_source_z_axis_to_local_axis_draft()
                self.assertIsNotNone(draft)

                overlays = widget._local_axis_volume_overlays()
                output_overlay = [item for item in overlays if item["label"] == "output Z"][0]
                end_xy = output_overlay["end_xy"]
                old_yaw = widget._volume_yaw
                old_end = list(draft["editable_axis"]["end_zyx"])

                press = FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end_xy[0], end_xy[1])
                move = FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end_xy[0] + 36, end_xy[1] - 18)
                release = FakeMouseEvent(Qt.LeftButton, Qt.NoButton, end_xy[0] + 36, end_xy[1] - 18)
                widget.volume_canvas.mousePressEvent(press)
                widget.volume_canvas.mouseMoveEvent(move)
                widget.volume_canvas.mouseReleaseEvent(release)

                new_end = widget.local_axis_draft["editable_axis"]["end_zyx"]
                self.assertTrue(press.accepted)
                self.assertTrue(move.accepted)
                self.assertTrue(release.accepted)
                self.assertNotEqual(new_end, old_end)
                self.assertEqual(widget._volume_yaw, old_yaw)
                self.assertIn("Updated output axis", widget.local_axis_status_label.text())
                self.assertIn("Draft output Z:", widget.local_axis_summary_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_local_axis_output_body_drag_moves_whole_axis_in_3d_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))
                widget.volume_canvas.resize(480, 360)
                draft = widget.copy_source_z_axis_to_local_axis_draft()
                self.assertIsNotNone(draft)

                overlays = widget._local_axis_volume_overlays()
                output_overlay = [item for item in overlays if item["label"] == "output Z"][0]
                start_xy = output_overlay["start_xy"]
                end_xy = output_overlay["end_xy"]
                body_xy = [(start_xy[0] + end_xy[0]) * 0.5, (start_xy[1] + end_xy[1]) * 0.5]
                old_start = list(draft["editable_axis"]["start_zyx"])
                old_end = list(draft["editable_axis"]["end_zyx"])
                old_vector = np.asarray(old_end, dtype=np.float64) - np.asarray(old_start, dtype=np.float64)

                press = FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, body_xy[0], body_xy[1])
                move = FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, body_xy[0] + 30, body_xy[1] - 12)
                release = FakeMouseEvent(Qt.LeftButton, Qt.NoButton, body_xy[0] + 30, body_xy[1] - 12)
                widget.volume_canvas.mousePressEvent(press)
                widget.volume_canvas.mouseMoveEvent(move)
                widget.volume_canvas.mouseReleaseEvent(release)

                new_start = widget.local_axis_draft["editable_axis"]["start_zyx"]
                new_end = widget.local_axis_draft["editable_axis"]["end_zyx"]
                new_vector = np.asarray(new_end, dtype=np.float64) - np.asarray(new_start, dtype=np.float64)
                self.assertTrue(press.accepted)
                self.assertTrue(move.accepted)
                self.assertTrue(release.accepted)
                self.assertNotEqual(new_start, old_start)
                self.assertNotEqual(new_end, old_end)
                np.testing.assert_allclose(new_vector, old_vector, atol=1e-6)
                self.assertIn("Moved output axis body", widget.local_axis_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_local_axis_roll_reference_uses_clip_plane_and_updates_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))
                widget.volume_canvas.resize(480, 360)
                draft = widget.copy_source_z_axis_to_local_axis_draft()
                self.assertIsNotNone(draft)

                self.assertFalse(widget.volume_clip_plane_check.isChecked())
                self.assertTrue(widget.set_local_axis_pick_target("roll_a"))
                self.assertTrue(widget.volume_clip_plane_check.isChecked())
                self.assertIn("clip plane", widget.btn_pick_roll_ref_a.toolTip())

                widget.volume_clip_plane_depth_slider.setValue(45)
                self.assertTrue(widget.set_local_axis_pick_target("roll_a"))
                left_click = FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, 205, 180)
                widget.volume_canvas.mousePressEvent(left_click)
                self.assertTrue(left_click.accepted)
                self.assertIn("roll_reference_a", widget.local_axis_status_label.text())

                self.assertTrue(widget.set_local_axis_pick_target("roll_b"))
                right_click = FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, 275, 180)
                widget.volume_canvas.mousePressEvent(right_click)
                self.assertTrue(right_click.accepted)

                roll = widget.local_axis_draft["roll_reference"]
                self.assertEqual(roll["point_a"]["role"], "roll_reference_a")
                self.assertEqual(roll["point_b"]["role"], "roll_reference_b")
                self.assertIsNotNone(widget.local_axis_draft["local_frame"])
                self.assertNotIn("Local frame x_axis", widget.local_axis_summary_label.text())
                self.assertFalse(widget.local_axis_details_label.isVisible())
                widget.local_axis_details_check.setChecked(True)
                self.assertIn("Local frame x_axis", widget.local_axis_details_label.text())
                self.assertIn("Axis/reference relation", widget.local_axis_details_label.text())
                self.assertIn("A/B projected roll width", widget.local_axis_details_label.text())
                overlays = widget._local_axis_volume_overlays()
                self.assertIn("Roll reference A", [item.get("label") for item in overlays])
                self.assertIn("Roll reference B", [item.get("label") for item in overlays])
                self.assertIn("Roll reference", [item.get("label") for item in overlays])

                old_frame_z = list(widget.local_axis_draft["local_frame"]["z_axis"])
                output_overlay = [item for item in overlays if item.get("label") == "output Z"][0]
                end_xy = output_overlay["end_xy"]
                widget.volume_canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end_xy[0], end_xy[1]))
                widget.volume_canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end_xy[0] + 28, end_xy[1] - 14))
                widget.volume_canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, end_xy[0] + 28, end_xy[1] - 14))

                self.assertNotEqual(widget.local_axis_draft["local_frame"]["z_axis"], old_frame_z)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_local_axis_roll_reference_pick_ignores_preview_busy_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            task = None
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))
                widget.volume_canvas.resize(480, 360)
                self.assertIsNotNone(widget.copy_source_z_axis_to_local_axis_draft())

                task = widget._start_tif_task("volume_preview", action="build_preview", message="Preparing preview")
                self.assertTrue(widget._backend_write_lock_active())
                self.assertTrue(widget.set_local_axis_pick_target("roll_a"))
                click = FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, 205, 180)
                widget.volume_canvas.mousePressEvent(click)

                self.assertTrue(click.accepted)
                self.assertEqual(widget.task_manager.task(task.task_id).status, "running")
                self.assertEqual(widget.local_axis_draft["roll_reference"]["point_a"]["role"], "roll_reference_a")
                self.assertIn("roll_reference_a", widget.local_axis_status_label.text())
            finally:
                if task is not None:
                    widget._finish_tif_task(task.task_id, message="done")
                widget.close_project()
                widget.deleteLater()

    def test_local_axis_controls_remain_available_during_preview_busy_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            task = None
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))

                task = widget._start_tif_task("volume_preview", action="build_preview", message="Preparing preview")
                widget._set_scope_controls_enabled()

                self.assertTrue(widget._backend_write_lock_active())
                self.assertTrue(widget.btn_copy_source_z_axis.isEnabled())
                self.assertTrue(widget.btn_pick_roll_ref_a.isEnabled())
                self.assertTrue(widget.btn_pick_roll_ref_b.isEnabled())
                self.assertTrue(widget.btn_pick_roll_ref_c.isEnabled())
                self.assertTrue(widget.btn_align_axis_to_reference_plane.isEnabled())
                self.assertFalse(widget.btn_local_axis_reslice.isEnabled())
                self.assertFalse(widget.btn_import_tif.isEnabled())
            finally:
                if task is not None:
                    widget._finish_tif_task(task.task_id, message="done")
                widget.close_project()
                widget.deleteLater()

    def test_local_axis_pick_target_auto_creates_draft_during_preview_busy_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            task = None
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))
                widget.volume_canvas.resize(480, 360)
                self.assertIsNone(widget.local_axis_draft)

                task = widget._start_tif_task("volume_preview", action="build_preview", message="Preparing preview")
                with patch.object(widget, "render_volume_preview", return_value=None):
                    self.assertTrue(widget.set_local_axis_pick_target("roll_a"))

                self.assertIsNotNone(widget.local_axis_draft)
                self.assertEqual(widget._local_axis_pick_target, "roll_a")
                self.assertTrue(widget.volume_clip_plane_check.isChecked())
                self.assertTrue(widget.btn_pick_roll_ref_a.isChecked())
                self.assertEqual(widget.task_manager.task(task.task_id).status, "running")
            finally:
                if task is not None:
                    widget._finish_tif_task(task.task_id, message="done")
                widget.close_project()
                widget.deleteLater()

    def test_busy_lock_matrix_allows_preview_only_local_axis_draft_interaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            task = None
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                preview_task_types = {"volume_preview", "mask_preview"}
                blocking_task_types = {
                    "tif_import",
                    "amira_import",
                    "tif_materialize",
                    "label_auto_save",
                    "label_manual_save",
                    "truth_promotion",
                    "confirm_part_roi",
                    "backend_action",
                    "local_axis_export",
                }
                for task_type in sorted(preview_task_types | blocking_task_types):
                    task = widget._start_tif_task(task_type, action=f"test_{task_type}", message=f"testing {task_type}")
                    try:
                        self.assertTrue(widget._backend_write_lock_active(), task_type)
                        allowed = widget._guard_local_axis_draft_interaction(show_message=False)
                        self.assertEqual(allowed, task_type in preview_task_types, task_type)
                        self.assertFalse(widget._guard_backend_write_lock(show_message=False), task_type)
                        ignored_preview_allowed = widget._guard_backend_write_lock(
                            show_message=False,
                            ignored_task_types=widget._local_axis_draft_lock_ignored_task_types(),
                        )
                        self.assertEqual(ignored_preview_allowed, task_type in preview_task_types, task_type)
                    finally:
                        widget._finish_tif_task(task.task_id, message="done")
                        task = None
            finally:
                if task is not None:
                    widget._finish_tif_task(task.task_id, message="done")
                widget.close_project()
                widget.deleteLater()

    def test_local_axis_three_point_plane_aligns_output_z_and_exports_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                draft = widget.copy_source_z_axis_to_local_axis_draft()
                self.assertIsNotNone(draft)

                roll = {
                    "pair_id": "roll_reference_point_pair",
                    "point_a": {"role": "roll_reference_a", "zyx": [1.0, 1.0, 1.0]},
                    "point_b": {"role": "roll_reference_b", "zyx": [1.0, 5.0, 1.0]},
                    "point_c": {"role": "reference_plane_c", "zyx": [3.0, 1.0, 5.0]},
                }
                widget.local_axis_draft["roll_reference"] = roll
                old_axis = dict(widget.local_axis_draft["editable_axis"])

                self.assertTrue(widget.align_local_axis_to_reference_plane())

                aligned_axis = widget.local_axis_draft["editable_axis"]
                reference_plane = widget.local_axis_draft["reference_plane"]
                self.assertNotEqual(aligned_axis["end_zyx"], old_axis["end_zyx"])
                self.assertEqual(aligned_axis["derived_from"], "three_point_reference_plane")
                self.assertEqual(reference_plane["point_c_zyx"], [3.0, 1.0, 5.0])
                self.assertEqual(widget.local_axis_draft["roll_reference"]["point_c"]["role"], "reference_plane_c")
                self.assertIn("Plane reference: C set", widget.local_axis_summary_label.text())
                widget.local_axis_details_check.setChecked(True)
                self.assertIn("Reference plane normal", widget.local_axis_details_label.text())

                overlays = widget._local_axis_volume_overlays()
                self.assertIn("Plane reference C", [item.get("label") for item in overlays])
                self.assertIn("A/B/C reference plane", [item.get("label") for item in overlays])

                payload = widget._current_local_axis_reslice_payload()
                self.assertEqual(payload["roll_reference"]["point_c"]["role"], "reference_plane_c")
                self.assertEqual(payload["reference_plane"]["plane_id"], "three_point_reference_plane")

                FakeProgressDialog.instances.clear()
                with patch("AntSleap.ui.tif_workbench.QProgressDialog", FakeProgressDialog):
                    result = widget.export_current_local_axis_reslice()

                self.assertIsNotNone(result)
                self.assertEqual(result["status"], "running")
                self._wait_for_local_axis_export(widget)
                record = widget.project.get_part_reslice("01-0101-21", "head", result["reslice_id"])
                self.assertEqual(record["local_frame"]["roll_reference"]["point_c"]["role"], "reference_plane_c")
                self.assertEqual(record["training_sample"]["roll_reference_point_pair"]["point_c"]["role"], "reference_plane_c")
                self.assertEqual(record["training_sample"]["reference_plane"]["plane_id"], "three_point_reference_plane")
                self.assertEqual(record["provenance"]["reference_plane_source"], "manual_three_point_plane")
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_local_axis_clip_plane_depth_advances_from_viewer_side(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))
                widget.volume_canvas.resize(480, 360)

                widget.volume_clip_plane_depth_slider.setValue(0)
                front_depth = widget._clip_plane_rotated_depth()
                widget.volume_clip_plane_depth_slider.setValue(50)
                middle_depth = widget._clip_plane_rotated_depth()
                widget.volume_clip_plane_depth_slider.setValue(100)
                back_depth = widget._clip_plane_rotated_depth()

                self.assertGreater(front_depth, middle_depth)
                self.assertGreater(middle_depth, back_depth)
                self.assertGreater(front_depth, 0.0)
                self.assertLess(back_depth, 0.0)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_local_axis_sidebar_export_records_training_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))
                widget.volume_canvas.resize(480, 360)
                draft = widget.copy_source_z_axis_to_local_axis_draft()
                self.assertIsNotNone(draft)

                widget.volume_clip_plane_check.setChecked(True)
                widget.volume_clip_plane_depth_slider.setValue(45)
                expected_origin = list(widget.local_axis_draft["origin_zyx"])
                self.assertTrue(widget.set_local_axis_pick_target("roll_a"))
                widget.volume_canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, 205, 180))
                self.assertTrue(widget.set_local_axis_pick_target("roll_b"))
                widget.volume_canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, 275, 180))
                self.assertIsNotNone(widget.local_axis_draft["local_frame"])
                self.assertEqual(widget.local_axis_draft["origin_zyx"], expected_origin)

                original_part = dict(widget.project.get_part("01-0101-21", "head"))
                original_part_image = dict(original_part.get("image") or {})
                original_part_mask = dict(original_part.get("mask") or {})
                original_part_contours = dict(original_part.get("contours") or {})
                original_part_image_path = root / "viewer" / original_part_image["path"]
                FakeProgressDialog.instances.clear()
                with patch("AntSleap.ui.tif_workbench.QProgressDialog", FakeProgressDialog):
                    result = widget.export_current_local_axis_reslice()

                self.assertIsNotNone(result)
                self.assertEqual(result["status"], "running")
                self.assertTrue(widget._local_axis_reslice_export_running())
                self._wait_for_local_axis_export(widget)
                self.assertEqual(len(FakeProgressDialog.instances), 1)
                progress = FakeProgressDialog.instances[0]
                self.assertTrue(progress.shown)
                self.assertTrue(progress.closed)
                self.assertTrue(progress.deleted)
                self.assertEqual(progress.cancel_button, None)
                self.assertEqual(progress.window_title, "Local Axis Reslice")
                self.assertIn("Finalizing Local Axis Reslice export", progress.label_text)
                record = widget.project.get_part_reslice("01-0101-21", "head", result["reslice_id"])
                self.assertEqual(record["status"], "exported")
                self.assertTrue(record["image_path"].endswith("image.tif"))
                self.assertTrue(record["metadata_path"].endswith("metadata.json"))
                self.assertTrue(record["training_sample"]["human_confirmed"])
                self.assertTrue(record["training_sample"]["usable_for_training"])
                self.assertEqual(record["training_sample"]["part_id"], "head")
                self.assertEqual(record["training_sample"]["source_axis"]["role"], "source_direction_reference")
                self.assertEqual(record["training_sample"]["final_editable_axis"]["role"], "editable_output_axis")
                self.assertEqual(record["training_sample"]["roll_reference_point_pair"]["point_a"]["role"], "roll_reference_a")
                self.assertEqual(record["training_sample"]["origin_zyx"], expected_origin)
                output_shape = record["training_sample"]["outputs"]["image_shape_zyx"]
                self.assertEqual(output_shape, record["training_sample"]["reslice_params"]["output_shape_zyx"])
                self.assertGreaterEqual(output_shape[0], 4)
                self.assertGreaterEqual(output_shape[1], 6)
                self.assertGreaterEqual(output_shape[2], 6)
                self.assertIsNotNone(widget.local_axis_draft)
                self.assertIsNone(widget._current_local_axis_draft())
                self.assertEqual(widget.current_reslice_id, record["reslice_id"])
                self.assertTrue((root / "viewer" / record["metadata_path"]).exists())
                self.assertTrue((root / "viewer" / record["image_path"]).exists())
                self.assertTrue(original_part_image_path.exists())
                part_after_export = widget.project.get_part("01-0101-21", "head")
                self.assertEqual(part_after_export["image"], original_part_image)
                self.assertEqual(part_after_export.get("mask") or {}, original_part_mask)
                self.assertEqual(part_after_export.get("contours") or {}, original_part_contours)
                self.assertEqual(len(widget.project.list_part_reslices("01-0101-21", "head")), 1)

                manifest_dir = root / "manifest"
                manifest = export_local_axis_training_manifest(widget.project, manifest_dir, {"template_id": "head"})
                self.assertEqual(manifest["sample_count"], 1)
                sample = manifest["manifest"]["samples"][0]
                self.assertEqual(sample["reslice_id"], record["reslice_id"])
                self.assertTrue(sample["part_image"]["path"])
                self.assertTrue(sample["outputs"]["image_path"].endswith("image.tif"))
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_local_axis_volume_section_follows_part_3d_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                mode_index = widget.display_mode_combo.findData("volume")
                widget.display_mode_combo.setCurrentIndex(mode_index)
                self.assertTrue(widget.local_axis_volume_section.isHidden())

                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.display_mode_combo.setCurrentIndex(mode_index)

                self.assertIs(widget.task_tabs.currentWidget(), widget.display_task_page)
                self.assertFalse(widget.local_axis_volume_section.isHidden())
                self.assertIn("Source Z axis", widget.local_axis_summary_label.text())
                self.assertIn("Draft output Z: none", widget.local_axis_summary_label.text())

                draft = widget.copy_source_z_axis_to_local_axis_draft()

                self.assertIsNotNone(draft)
                self.assertIn("Draft output Z:", widget.local_axis_summary_label.text())
                self.assertIn("3D overlay: on", widget.local_axis_summary_label.text())
                self.assertEqual(widget.btn_local_axis_reslice.text(), "Export confirmed reslice")
                self.assertIs(widget.volume_local_axes_check.parentWidget(), widget.local_axis_volume_section)
                self.assertIs(widget.volume_clip_plane_check.parentWidget(), widget.volume_render_section)
                self.assertIs(widget.volume_clip_plane_depth_slider.parentWidget(), widget.volume_render_section)

                slice_index = widget.display_mode_combo.findData("slice")
                widget.display_mode_combo.setCurrentIndex(slice_index)
                self.assertFalse(widget.local_axis_volume_section.isHidden())
                self.assertIs(widget.task_tabs.currentWidget(), widget.part_task_page)
                self.assertGreater(widget.part_task_layout.indexOf(widget.local_axis_volume_section), widget.part_task_layout.indexOf(widget.part_mask_section))
                self.assertLess(widget.part_task_layout.indexOf(widget.local_axis_volume_section), widget.part_task_layout.indexOf(widget.part_output_section))

                widget._select_volume_tree_item("01-0101-21", "full")
                self.assertTrue(widget.local_axis_volume_section.isHidden())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_local_axis_draft_is_scoped_to_current_part(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                crop_volume_to_part(widget.project, "01-0101-21", "thorax", [[1, 5], [1, 7], [1, 7]], display_name="Thorax")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                self.assertIsNotNone(widget.copy_source_z_axis_to_local_axis_draft())

                widget._select_volume_tree_item("01-0101-21", "part", "thorax")

                self.assertIsNone(widget.local_axis_draft)
                widget.volume_local_axes_check.setChecked(True)
                overlays = widget._local_axis_volume_overlays()
                self.assertEqual([item["label"] for item in overlays], ["source Z"])
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_selected_saved_reslice_is_read_only_and_draws_saved_axis_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                draft = widget.copy_source_z_axis_to_local_axis_draft()
                self.assertIsNotNone(draft)
                saved_axis = dict(draft["editable_axis"])
                saved_axis["start_zyx"] = [0.0, 1.0, 1.0]
                saved_axis["end_zyx"] = [0.0, 6.0, 6.0]
                saved_image_rel = "specimens/01-0101-21/parts/head/reslices/saved_axis/image.tif"
                saved_image_abs = Path(tmp) / "viewer" / saved_image_rel
                saved_image_abs.parent.mkdir(parents=True, exist_ok=True)
                tifffile.imwrite(saved_image_abs, np.zeros((4, 6, 6), dtype=np.uint8), photometric="minisblack")
                widget.project.add_part_reslice(
                    "01-0101-21",
                    "head",
                    {
                        "reslice_id": "saved_axis",
                        "image_path": saved_image_rel,
                        "source": {
                            "source_axis": draft["source_axis"],
                            "editable_axis": saved_axis,
                        },
                        "local_frame": {
                            "origin_zyx": [2.0, 3.0, 3.0],
                            "x_axis": [1.0, 0.0, 0.0],
                            "y_axis": [0.0, 1.0, 0.0],
                            "z_axis": [0.0, 0.0, 1.0],
                            "spacing_zyx": [1.0, 1.0, 1.0],
                            "roll_reference": {
                                "point_a": {"role": "roll_reference_a", "zyx": [1.0, 2.0, 2.0]},
                                "point_b": {"role": "roll_reference_b", "zyx": [1.0, 4.0, 4.0]},
                            },
                        },
                        "reslice_params": {"output_shape_zyx": [4, 6, 6], "output_spacing_zyx": [1.0, 1.0, 1.0]},
                    },
                    save=False,
                )

                widget.load_part("01-0101-21", "head", selected_reslice_id="saved_axis")
                widget.volume_local_axes_check.setChecked(True)
                overlays = widget._local_axis_volume_overlays()

                self.assertIsNotNone(widget.local_axis_draft)
                self.assertIsNone(widget._current_local_axis_draft())
                labels = [item.get("label") for item in overlays]
                self.assertIn("source Z", labels)
                self.assertIn("output Z", labels)
                self.assertIn("Roll reference A", labels)
                self.assertIn("Roll reference B", labels)
                self.assertFalse(widget.btn_copy_source_z_axis.isEnabled())
                self.assertFalse(widget.btn_local_axis_reslice.isEnabled())
                self.assertFalse(widget.local_axis_trainable_check.isEnabled())
                self.assertFalse(widget.btn_add_rect_keyframe.isEnabled())
                self.assertFalse(widget.btn_preview_part_mask.isEnabled())
                self.assertFalse(widget.btn_accept_part_mask.isEnabled())
                self.assertFalse(widget.btn_export_part_package.isEnabled())
                self.assertFalse(widget.btn_delete_part_volume.isEnabled())
                self.assertFalse(widget._is_editable_part_volume())
                with self.assertRaises(ValueError):
                    widget._current_local_axis_reslice_payload()
                self.assertIn("read-only", widget.local_axis_status_label.text())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_copy_source_z_axis_uses_current_part_id_as_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "leg_gland", [[0, 4], [1, 7], [1, 7]], display_name="Leg gland")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "leg_gland")

                draft = widget.copy_source_z_axis_to_local_axis_draft()

                self.assertIsNotNone(draft)
                self.assertEqual(draft["part_id"], "leg_gland")
                self.assertEqual(draft["template_id"], "leg_gland")
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_task_tabs_follow_tif_workflow_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                self.assertIs(widget.task_tabs.currentWidget(), widget.part_task_page)
                self.assertFalse(widget.part_locate_section.isHidden())
                self.assertFalse(widget.part_mask_section.isHidden())
                self.assertTrue(widget.part_output_section.isHidden())
                self.assertTrue(widget.btn_draw_part_contour.isEnabled())
                self.assertTrue(widget.btn_preview_part_mask.isEnabled())

                mode_index = widget.display_mode_combo.findData("volume")
                widget.display_mode_combo.setCurrentIndex(mode_index)
                self.assertIs(widget.task_tabs.currentWidget(), widget.display_task_page)
                self.assertTrue(widget.part_locate_section.isHidden())
                self.assertTrue(widget.part_mask_section.isHidden())

                slice_index = widget.display_mode_combo.findData("slice")
                widget.display_mode_combo.setCurrentIndex(slice_index)
                self.assertIs(widget.task_tabs.currentWidget(), widget.part_task_page)
                self.assertFalse(widget.part_locate_section.isHidden())
                self.assertFalse(widget.part_mask_section.isHidden())

                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                self.assertIs(widget.task_tabs.currentWidget(), widget.part_task_page)
                self.assertFalse(widget.annotation_section.isHidden())
                self.assertTrue(widget.part_locate_section.isHidden())
                self.assertFalse(widget.part_mask_section.isHidden())
                self.assertFalse(widget.part_output_section.isHidden())

                widget.task_tabs.setCurrentWidget(widget.training_mode_tabs)
                widget.training_mode_tabs.setCurrentWidget(widget.annotation_task_page)
                widget._sync_mode_sections()
                self.assertIs(widget.task_tabs.currentWidget(), widget.training_mode_tabs)
                self.assertIs(widget.training_mode_tabs.currentWidget(), widget.annotation_task_page)
                self.assertFalse(widget.annotation_section.isHidden())

                widget.display_mode_combo.setCurrentIndex(mode_index)
                self.assertIs(widget.task_tabs.currentWidget(), widget.training_mode_tabs)
                self.assertTrue(widget.part_mask_section.isHidden())
                self.assertTrue(widget.part_output_section.isHidden())
                self.assertFalse(widget.local_axis_volume_section.isHidden())
                self.assertEqual(widget.display_task_layout.indexOf(widget.local_axis_volume_section), 0)
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
                self.assertIsNone(reloaded_widget.label_volume)
                self.assertIsNotNone(reloaded_widget.part_mask_volume)
                self.assertEqual(tuple(reloaded_widget.image_volume.shape), tuple(reloaded_widget.part_mask_volume.shape))
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

    def test_right_sidebar_visible_pages_do_not_overflow_control_panel(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")
                widget.resize(1400, 900)
                widget.show()
                self.app.processEvents()

                right_panel = widget.findChild(QWidget, "tifControlPanel")
                self.assertIsNotNone(right_panel)
                self.assertLessEqual(right_panel.minimumSizeHint().width(), right_panel.maximumWidth())

                def assert_visible_widgets_inside_right_panel(context):
                    self.app.processEvents()
                    overflow = []
                    right_width = right_panel.width()
                    for child in right_panel.findChildren(QWidget):
                        if not child.isVisible() or child.isWindow():
                            continue
                        top_left = child.mapTo(right_panel, child.rect().topLeft())
                        right_edge = top_left.x() + child.width()
                        if right_edge > right_width + 3:
                            overflow.append((child.objectName(), type(child).__name__, right_edge, right_width))
                    self.assertFalse(overflow[:6], f"{context} right sidebar overflow: {overflow[:6]}")

                slice_index = widget.display_mode_combo.findData("slice")
                volume_index = widget.display_mode_combo.findData("volume")

                widget.display_mode_combo.setCurrentIndex(slice_index)
                widget.task_tabs.setCurrentWidget(widget.part_task_page)
                assert_visible_widgets_inside_right_panel("part extraction")

                widget.display_mode_combo.setCurrentIndex(volume_index)
                widget.task_tabs.setCurrentWidget(widget.display_task_page)
                widget.copy_source_z_axis_to_local_axis_draft()
                assert_visible_widgets_inside_right_panel("3D review with local axis")

                widget.task_tabs.setCurrentWidget(widget.training_mode_tabs)
                widget.training_mode_tabs.setCurrentWidget(widget.annotation_task_page)
                assert_visible_widgets_inside_right_panel("label review")

                widget.training_mode_tabs.setCurrentWidget(widget.training_task_page)
                assert_visible_widgets_inside_right_panel("train predict")

                widget.training_mode_tabs.setCurrentWidget(widget.result_compare_page)
                assert_visible_widgets_inside_right_panel("result comparison")
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
                self.assertEqual(widget.material_table.horizontalHeaderItem(0).text(), "")
                self.assertEqual(widget.material_table.item(1, 0).text(), "")
                self.assertEqual(widget.material_table.item(1, 0).toolTip(), "#ff0000")
                self.assertEqual(widget.material_table.item(1, 1).text(), "5")
                self.assertEqual(widget.material_table.item(2, 2).text(), "Optic lobe")
                widget.material_table.selectRow(2)
                self.assertEqual(widget.current_material_id, 6)
                self.assertIn("Label 6: Optic lobe", widget.current_material_label.text())
                self.assertEqual(widget.current_material_swatch.toolTip(), "#00ff00")
                widget.material_table.selectRow(0)
                self.assertEqual(widget.current_material_id, 0)
                self.assertIn("Background / erase target", widget.current_material_label.text())
                self.assertIn("no", widget.material_table.item(0, 3).text())
                self.assertTrue(widget._material_id_is_used(5))
                self.assertFalse(widget._material_id_is_used(6))
            finally:
                widget.close_project(prompt_unsaved=False)
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
            self.assertEqual(widget.btn_browse_model_manifest.text(), "Browse manifest")
            self.assertEqual(widget.btn_refresh_predict_targets.text(), "Refresh targets")
            self.assertEqual(widget.btn_select_current_predict_target.text(), "Select current part")
            self.assertEqual(widget.btn_select_ready_predict_targets.text(), "Select all ready")
            self.assertEqual(widget.btn_clear_predict_targets.text(), "Clear selection")
            self.assertEqual(widget.btn_accept_selected_ai_results.text(), "Accept selected AI results")
            self.assertEqual(widget.btn_import_external_prediction_tif.text(), "Import external label TIF as review result")
            self.assertEqual(widget.auto_save_check.text(), "Auto-save labels")
            self.assertFalse(widget.btn_copy_draft.isVisible())
            self.assertTrue(widget.auto_save_check.isChecked())
            self.assertEqual(widget.btn_start_center.text(), "Start Center")
            self.assertEqual(widget.btn_ask_agent.text(), "Ask Agent")
            self.assertEqual(widget.btn_show_workbench_log.text(), "Show full log")
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
            self.assertIsNotNone(widget.findChild(type(widget.btn_browse_model_manifest), "tifBrowseModelManifestButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_accept_selected_ai_results), "tifAcceptSelectedAiResultsButton"))
            self.assertIsNotNone(widget.findChild(type(widget.predict_targets_table), "tifPredictTargetsTable"))
            self.assertIsNotNone(widget.findChild(type(widget.predict_filter_combo), "tifPredictFilterCombo"))
            self.assertIsNotNone(widget.findChild(type(widget.ai_review_check_label), "tifAiReviewCheckText"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_import_external_prediction_tif), "tifImportExternalPredictionTifButton"))
            self.assertIsNone(widget.findChild(QWidget, "tifLocalAxisModelsButton"))
            self.assertIsNone(widget.findChild(QWidget, "tifLocalAxisModelsInlineButton"))
            self.assertIsNone(widget.findChild(QWidget, "tifPrepareLocalAxisDatasetButton"))
            self.assertIsNone(widget.findChild(QWidget, "tifTrainLocalAxisModelButton"))
            self.assertIsNone(widget.findChild(QWidget, "tifPredictLocalAxisGlobalButton"))
            self.assertIsNone(widget.findChild(QWidget, "tifPredictLocalAxisFrameButton"))
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
            self.assertIsNotNone(widget.findChild(type(widget.volume_roi_source_combo), "tifVolumeRoiSourceCombo"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_roi_inspect_check), "tifVolumeRoiInspectCheck"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_roi_scale_slider), "tifVolumeRoiScaleSlider"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_roi_budget_combo), "tifVolumeRoiBudgetCombo"))
            self.assertIsNotNone(widget.findChild(type(widget.volume_shader_quality_combo), "tifVolumeShaderQualityCombo"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifSliceDisplaySection"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifVolumeRenderSection"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifVolumeCanvas"))
            self.assertEqual(widget.volume_quality_slider.maximum(), 4096)
            self.assertEqual(widget.volume_sample_slider.maximum(), 4096)
            self.assertEqual(widget.volume_inside_slider.maximum(), 160)
            self.assertEqual(widget.volume_projection_combo.currentData(), "composite")
            self.assertEqual(widget.volume_roi_scale_slider.value(), 200)
            self.assertEqual(widget.volume_roi_budget_combo.currentData(), "balanced")
            self.assertEqual(widget.volume_roi_source_combo.currentData(), "full")
            self.assertEqual(widget.volume_roi_source_combo.itemText(widget.volume_roi_source_combo.findData("current_bbox")), "Current bbox draft")
            self.assertFalse(widget.volume_roi_inspect_check.isChecked())
            self.assertEqual(widget.volume_shader_quality_combo.currentData(), "preset")
            self.assertFalse(widget.slice_display_section.isHidden())
            self.assertFalse(widget.annotation_section.isHidden())
            self.assertTrue(widget.volume_render_section.isHidden())
            self.assertEqual(widget.backend_id_edit.objectName(), "tifBackendIdEdit")
            self.assertEqual(widget.backend_formats_edit.text(), "ome_tiff,nrrd,mha,nifti")
            self.assertEqual(widget.training_status_label.objectName(), "tifTrainingStatusText")
            self.assertEqual(widget.operation_status_label.objectName(), "tifOperationStatusText")
            self.assertIsNotNone(widget.findChild(QWidget, "tifOperationStatusSection"))
            self.assertIn("Annotation feedback", widget.operation_status_label.text())
            self.assertEqual(widget.log_console.objectName(), "tifLogConsole")
            task_tabs = widget.findChild(QWidget, "tifTaskTabs")
            self.assertIsNotNone(task_tabs)
            self.assertEqual(widget.task_tabs.count(), 3)
            self.assertEqual(widget.task_tabs.tabText(0), "Review")
            self.assertEqual(widget.task_tabs.tabText(1), "Part Extraction")
            self.assertEqual(widget.task_tabs.tabText(2), "Annotation / training")
            self.assertEqual(widget.training_mode_tabs.count(), 3)
            self.assertEqual(widget.training_mode_tabs.tabText(0), "Label review")
            self.assertEqual(widget.training_mode_tabs.tabText(1), "Train / predict")
            self.assertEqual(widget.training_mode_tabs.tabText(2), "Result comparison")
            self.assertLess(
                widget.annotation_task_layout.indexOf(widget.label_schema_section),
                widget.annotation_task_layout.indexOf(widget.material_section),
            )
            self.assertLess(
                widget.annotation_task_layout.indexOf(widget.material_section),
                widget.annotation_task_layout.indexOf(widget.annotation_section),
            )
            self.assertIn("select one current label", widget.material_help_label.text())
            self.assertIn("Bind a label schema first", widget.label_schema_help_label.text())
            self.assertFalse(widget.material_editor_buttons.isHidden())
            self.assertIn("Group tags only organize", widget.part_user_tag_help_label.text())
            self.assertIn("not annotation classes", widget.part_user_tag_help_label.text())
            self.assertEqual(widget.btn_new_part_user_tag.text(), "Add group tag")
            self.assertEqual(widget.btn_save_part_user_tag.text(), "Save group tag")
            self.assertIs(widget.log_console.parentWidget().parentWidget(), widget.training_task_page.widget())
            widget.training_status_label.setText("Brush feedback mirror")
            self.assertEqual(widget.operation_status_label.text(), "Brush feedback mirror")
            widget.task_tabs.setCurrentWidget(widget.training_mode_tabs)
            widget.training_mode_tabs.setCurrentWidget(widget.annotation_task_page)
            widget.show_workbench_log()
            self.assertIs(widget.task_tabs.currentWidget(), widget.training_mode_tabs)
            self.assertIs(widget.training_mode_tabs.currentWidget(), widget.training_task_page)
            self.assertIsNotNone(widget.findChild(QWidget, "tifStatusSection"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifPartLocateSection"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifPartMaskSection"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifPartOutputSection"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifResultComparisonSection"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_export_current_rendering), "tifExportCurrentRenderingButton"))
            self.assertIsNotNone(widget.findChild(type(widget.result_compare_table), "tifResultComparisonTable"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_refresh_result_comparison), "tifRefreshResultComparisonButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_open_result_comparison_target), "tifOpenResultComparisonTargetButton"))
            self.assertIsNotNone(widget.findChild(type(widget.btn_show_result_region_in_3d), "tifShowResultRegionIn3DButton"))
            self.assertEqual(widget.btn_import_tif.property("tifRole"), "primary")
            self.assertEqual(widget.btn_train_backend.property("tifRole"), "primary")
            self.assertEqual(widget.btn_save_backend.property("tifRole"), "secondary")
            self.assertEqual(widget.btn_delete_material.property("tifRole"), "danger")
            self.assertGreaterEqual(widget.btn_import_tif.minimumHeight(), 34)
            self.assertEqual(widget.specimen_list.objectName(), "tifSpecimenList")
            self.assertEqual(widget.material_table.objectName(), "tifMaterialTable")
            self.assertEqual(widget.btn_tool_brush.objectName(), "tifToolBrushButton")
            self.assertEqual(widget.btn_tool_eraser.objectName(), "tifToolEraserButton")
            self.assertEqual(widget.btn_tool_picker.objectName(), "tifToolPickerButton")
            self.assertEqual(widget.btn_tool_pan.objectName(), "tifToolPanButton")
            self.assertEqual(widget.annotation_tool_mode, "brush")
            self.assertTrue(widget.btn_tool_brush.isChecked())
            widget.btn_tool_eraser.click()
            self.assertEqual(widget.annotation_tool_mode, "eraser")
            self.assertTrue(widget.btn_tool_eraser.isChecked())
            self.assertIn("write background 0", widget.btn_tool_eraser.toolTip())
            self.assertEqual(widget.current_material_swatch.objectName(), "tifCurrentMaterialSwatch")
            self.assertEqual(widget.current_material_label.objectName(), "tifCurrentMaterialText")
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

    def test_ask_agent_context_includes_tif_view_and_annotation_training_focus(self):
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
                self.assertEqual(context["train_ready_part_sample_count"], "0")
                self.assertEqual(context["train_ready_top_level_sample_count"], "0")
                self.assertEqual(context["registered_tif_model_count"], "0")
                self.assertEqual(context["backend_run_active"], "no")
                self.assertIn("tif_task_summary", context)
                self.assertIn("tif_state_summary", context)
                self.assertIn("running_count", context["tif_task_summary"])
                self.assertIn("selection", context["tif_state_summary"])
                self.assertIn("annotation_training_loop", context["tif_next_requirement"])
                self.assertIn("TIF训练回环", context["tif_requirement_doc"])
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_composite_drag_preview_uses_lighter_interaction_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget._volume_canvas_renderer = "gpu"
                widget.volume_quality_slider.setValue(1024)
                widget.volume_sample_slider.setValue(1536)
                widget.volume_projection_combo.setCurrentIndex(widget.volume_projection_combo.findData("composite"))
                widget._volume_render_mode = "drag"

                self.assertEqual(widget._active_volume_target_dim("drag"), 384)
                self.assertEqual(widget._active_volume_sample_count(), 384)
                composite_state = widget._volume_render_state("drag")
                self.assertEqual(composite_state["render_quality"], 384)
                self.assertEqual(composite_state["sample_steps"], 384)
                self.assertLess(composite_state["transfer_opacity"], 0.7)
                self.assertEqual(composite_state["adaptive_step_strength"], 0.0)

                widget.volume_projection_combo.setCurrentIndex(widget.volume_projection_combo.findData("mip"))
                mip_state = widget._volume_render_state("drag")

                self.assertEqual(widget._active_volume_target_dim("drag"), 640)
                self.assertEqual(mip_state["sample_steps"], 768)
                self.assertEqual(mip_state["adaptive_step_strength"], 0.0)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_roi_high_detail_scale_raises_still_gpu_sample_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget._volume_canvas_renderer = "gpu"
                widget._volume_render_mode = "still"
                widget._volume_zoom = 2.5
                widget.volume_sample_slider.setValue(2048)
                widget.volume_roi_detail_check.setChecked(True)
                widget.volume_roi_scale_slider.setValue(250)

                state = widget._volume_render_state("still")

                self.assertEqual(widget._active_volume_sample_count(), 3072)
                self.assertEqual(state["sample_steps"], 3072)
                self.assertEqual(state["supersample_scale"], 2.5)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_volume_depth_sliders_use_interaction_preview_while_dragging(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))
                calls = []

                def fake_request():
                    calls.append(widget._volume_render_mode)

                widget._request_volume_interaction_render = fake_request
                for slider, value in (
                    (widget.volume_inside_slider, 45),
                    (widget.volume_clip_slider, 28),
                    (widget.volume_clip_plane_depth_slider, 72),
                ):
                    widget._volume_render_mode = "still"
                    slider.sliderPressed.emit()
                    slider.setSliderDown(True)
                    slider.setValue(value)
                    slider.setSliderDown(False)
                    slider.sliderReleased.emit()

                self.assertEqual(calls, ["drag", "drag", "drag"])
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_volume_quality_slider_rebuilds_only_after_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))
                calls = []

                def fake_refresh():
                    calls.append(int(widget.volume_quality_slider.value()))

                widget._refresh_volume_preview = fake_refresh
                widget.volume_quality_slider.setValue(1024)
                calls.clear()

                widget.volume_quality_slider.sliderPressed.emit()
                widget.volume_quality_slider.sliderMoved.emit(2048)
                widget.volume_quality_slider.setSliderDown(True)
                widget.volume_quality_slider.setValue(2048)
                widget._on_volume_quality_changed()
                widget.volume_quality_slider.sliderMoved.emit(3072)
                widget.volume_quality_slider.setValue(3072)
                widget._on_volume_quality_changed()
                widget.volume_quality_slider.sliderMoved.emit(4096)
                widget.volume_quality_slider.setValue(4096)
                widget._on_volume_quality_changed()

                self.assertEqual(calls, [])
                self.assertEqual(widget._volume_quality_committed_value, 1024)
                self.assertIn("Release Render quality", widget.volume_render_status_label.text())

                widget.volume_quality_slider.setSliderDown(False)
                widget.volume_quality_slider.sliderReleased.emit()

                self.assertEqual(calls, [4096])

                widget.volume_quality_slider.sliderPressed.emit()
                widget.volume_quality_slider.setSliderDown(True)
                widget._on_volume_quality_changed()
                widget.volume_quality_slider.setSliderDown(False)
                widget.volume_quality_slider.sliderReleased.emit()

                self.assertEqual(calls, [4096])
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_volume_roi_scale_slider_updates_only_after_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))
                calls = []

                def fake_render():
                    calls.append(int(widget.volume_roi_scale_slider.value()))

                widget.render_volume_preview = fake_render
                widget.volume_roi_scale_slider.setValue(200)
                calls.clear()

                widget.volume_roi_scale_slider.sliderPressed.emit()
                widget.volume_roi_scale_slider.setSliderDown(True)
                widget.volume_roi_scale_slider.setValue(250)
                widget._on_volume_roi_scale_changed()
                widget.volume_roi_scale_slider.setValue(300)
                widget._on_volume_roi_scale_changed()

                self.assertEqual(calls, [])
                self.assertIn("Release ROI scale", widget.volume_render_status_label.text())

                widget.volume_roi_scale_slider.setSliderDown(False)
                widget.volume_roi_scale_slider.sliderReleased.emit()

                self.assertEqual(calls, [300])
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_volume_transfer_opacity_saves_only_after_drag_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))
                saves = []
                renders = []

                def fake_save():
                    saves.append(int(widget.volume_transfer_opacity_slider.value()))

                def fake_render():
                    renders.append(int(widget.volume_transfer_opacity_slider.value()))

                widget._save_active_volume_view_settings = fake_save
                widget.render_volume_preview = fake_render

                widget.volume_transfer_opacity_slider.sliderPressed.emit()
                widget.volume_transfer_opacity_slider.setSliderDown(True)
                widget.volume_transfer_opacity_slider.setValue(80)
                widget.volume_transfer_opacity_slider.setValue(120)

                self.assertEqual(saves, [])
                self.assertEqual(renders[-2:], [80, 120])

                widget.volume_transfer_opacity_slider.setSliderDown(False)
                widget.volume_transfer_opacity_slider.sliderReleased.emit()

                self.assertEqual(saves, [120])
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

    def test_display_mode_switcher_stays_left_of_its_label(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            row = widget.display_mode_combo.parentWidget().layout()
            self.assertLess(row.indexOf(widget.display_mode_combo), row.indexOf(widget.display_mode_label))
            widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("volume"))
            self.assertLess(row.indexOf(widget.display_mode_combo), row.indexOf(widget.display_mode_label))
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
                self.assertIn("Local detail check", widget.volume_canvas_overlay_text())
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
                self.assertIn("局部结构检查", widget.volume_canvas_overlay_text())
                self.assertIn("模式 表面边界", widget.volume_canvas_overlay_text())
                self.assertEqual(widget.volume_clarity_check.text(), "局部结构检查")
                self.assertEqual(widget.volume_roi_detail_check.text(), "ROI 高清")
                self.assertIn("纹理 4096", widget.volume_canvas_overlay_text())
                self.assertIn("采样 4096", widget.volume_canvas_overlay_text())
                if widget._volume_canvas_renderer == "gpu":
                    self.assertIn("ROI 2.5x", widget.volume_canvas_overlay_text())
                self.assertIn("视点 65%", widget.volume_canvas_overlay_text())
                self.assertIn("近端裁剪 30%", widget.volume_canvas_overlay_text())
                self.assertIn("左键旋转", widget.volume_status_text())
                self.assertIn("右键平移", widget.volume_status_text())
                self.assertIn("横移 0%", widget.volume_canvas_overlay_text())
                self.assertIn("纵移 0%", widget.volume_canvas_overlay_text())
                self.assertIn("静止高清", widget.volume_quality_slider.toolTip())
                widget._update_volume_render_status_label()
                self.assertFalse(widget.volume_render_status_label.wordWrap())
                self.assertEqual(widget.volume_render_status_label.minimumHeight(), widget.volume_render_status_label.maximumHeight())
                self.assertNotIn("\n", widget.volume_render_status_label.text())
                self.assertNotIn("RTX 3090", widget.volume_render_status_label.text())
                self.assertIn("RTX 3090", widget.volume_render_status_label.toolTip())
                self.assertIn("4096", widget.volume_render_status_label.text())
                self.assertIn("0%", widget.volume_render_status_label.toolTip())

                old_yaw = widget._volume_yaw
                old_pitch = widget._volume_pitch
                widget.rotate_volume_preview(25, -10)
                self.assertNotEqual(widget._volume_yaw, old_yaw)
                self.assertGreater(widget._volume_pitch, old_pitch)
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
                widget._volume_pan_x = 0.0
                widget._volume_pan_y = 0.0
                widget._volume_zoom = 16.0
                widget.pan_volume_preview(120, -90)
                self.assertAlmostEqual(widget._volume_pan_x, 0.7, places=2)
                self.assertAlmostEqual(widget._volume_pan_y, 0.7, places=2)
                for _ in range(80):
                    widget.pan_volume_preview(120, -90)
                self.assertGreater(widget._volume_pan_x, 4.0)
                self.assertGreater(widget._volume_pan_y, 4.0)
                self.assertLessEqual(widget._volume_pan_x, widget._volume_pan_limit())
                self.assertLessEqual(widget._volume_pan_y, widget._volume_pan_limit())
                widget._volume_zoom = 1.0
                widget._clamp_volume_pan()
                self.assertLessEqual(widget._volume_pan_x, widget._volume_pan_limit())
                self.assertLessEqual(widget._volume_pan_y, widget._volume_pan_limit())
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
            self.assertEqual(widget._volume_preview_algorithm("still"), "hybrid")
            self.assertEqual(widget._volume_preview_algorithm("drag"), "stride")
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_volume_preview_cache_keeps_three_recent_specimen_owners(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget.volume_quality_slider.setValue(128)
            for specimen_id in ("specimen-a", "specimen-b", "specimen-c"):
                widget.current_specimen_id = specimen_id
                widget.current_volume_scope = "full"
                widget.current_part_id = ""
                widget.current_reslice_id = ""
                widget.image_volume = np.full((4, 16, 16), len(specimen_id), dtype=np.uint8)
                self.assertIsNotNone(widget._ensure_volume_preview("still"))

            widget.current_specimen_id = "specimen-a"
            widget.image_volume = np.full((4, 16, 16), 1, dtype=np.uint8)
            cached_a = widget._ensure_volume_preview("still")

            widget.current_specimen_id = "specimen-d"
            widget.image_volume = np.full((4, 16, 16), 4, dtype=np.uint8)
            self.assertIsNotNone(widget._ensure_volume_preview("still"))

            owners = {key[0][0] for key in widget._volume_preview_cache.keys()}
            self.assertEqual(owners, {"specimen-a", "specimen-c", "specimen-d"})
            self.assertNotIn("specimen-b", owners)
            report = widget.volume_performance_report()
            self.assertEqual(report["cache_specimen_count"], 3)
            self.assertEqual(report["cache_max_specimens"], 3)
            self.assertGreater(report["cache_estimated_bytes"], 0)

            widget.current_specimen_id = "specimen-a"
            widget.image_volume = np.full((4, 16, 16), 1, dtype=np.uint8)
            self.assertIs(widget._ensure_volume_preview("still"), cached_a)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_high_quality_volume_preview_cache_reduces_owner_limit(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget.volume_quality_slider.setValue(4096)
            for specimen_id in ("specimen-a", "specimen-b", "specimen-c"):
                widget.current_specimen_id = specimen_id
                widget.current_volume_scope = "full"
                widget.current_part_id = ""
                widget.current_reslice_id = ""
                widget.image_volume = np.full((4, 16, 16), len(specimen_id), dtype=np.uint8)
                self.assertIsNotNone(widget._ensure_volume_preview("still"))

            owners = {key[0][0] for key in widget._volume_preview_cache.keys()}
            self.assertEqual(owners, {"specimen-c"})
            report = widget.volume_performance_report()
            self.assertEqual(report["cache_specimen_count"], 1)
            self.assertEqual(report["cache_max_specimens"], 1)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_volume_quality_change_keeps_gpu_texture_cache_before_budgeted_rebuild(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeCanvas(QLabel):
            def __init__(self):
                super().__init__()
                self.release_texture_cache_calls = 0

            def release_texture_cache(self):
                self.release_texture_cache_calls += 1

            def render_stats(self):
                return {"texture_cache_entries": 0, "texture_cache_bytes": 0}

            def has_volume(self):
                return True

        fake_canvas = FakeCanvas()
        try:
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            calls = []

            def fake_refresh():
                calls.append(int(widget.volume_quality_slider.value()))

            widget._refresh_volume_preview = fake_refresh
            widget.volume_quality_slider.setValue(1024)
            widget._volume_quality_committed_value = 1024

            widget.volume_quality_slider.setValue(4096)
            widget._commit_volume_quality_change()

            self.assertEqual(fake_canvas.release_texture_cache_calls, 0)
            self.assertEqual(calls, [4096])
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_switching_specimen_resets_active_preview_without_flushing_lru_cache(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget.current_specimen_id = "specimen-a"
            widget.image_volume = np.zeros((4, 16, 16), dtype=np.uint8)
            first = widget._ensure_volume_preview("still")

            widget.current_specimen_id = "specimen-b"
            widget._reset_active_volume_preview_state()

            self.assertIsNone(widget._volume_preview)
            self.assertEqual(len(widget._volume_preview_cache), 1)
            self.assertIs(next(iter(widget._volume_preview_cache.values())), first)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_switching_specimen_cancels_pending_preview_without_locking_tree(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget.specimen_list.setEnabled(True)
            widget._set_volume_preview_build_controls_busy(True)
            worker = type("Worker", (), {"cancelled": False, "cancel": lambda self: setattr(self, "cancelled", True)})()
            widget._volume_preview_build_worker = worker
            widget._volume_preview_pending_token = 9
            widget._volume_preview_pending_key = ("old",)
            widget._volume_preview_pending_mask_key = None

            widget._cancel_volume_preview_build()

            self.assertTrue(worker.cancelled)
            self.assertEqual(widget._volume_preview_pending_token, 0)
            self.assertIsNone(widget._volume_preview_pending_key)
            self.assertTrue(widget.specimen_list.isEnabled())
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_deferred_specimen_switch_render_keeps_gpu_stream_path(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget.display_mode = "volume"
            widget._defer_volume_preview_render_once = True
            calls = []

            def fake_timer(_delay, callback):
                calls.append(callback)

            with patch("AntSleap.ui.tif_workbench.QTimer.singleShot", side_effect=fake_timer), \
                patch.object(widget, "_try_build_volume_gpu_texture") as gpu_build:
                widget.render_volume_preview()

            self.assertEqual(calls, [widget.render_volume_preview])
            gpu_build.assert_not_called()
            self.assertFalse(widget._defer_volume_preview_render_once)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_user_tree_switch_shows_volume_pending_status_before_loading(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget.display_mode = "volume"
            widget._loading_specimen = False
            previous = QTreeWidgetItem(["old"])
            previous.setData(0, Qt.UserRole, {"scope": "full", "specimen_id": "old", "part_id": ""})
            current = QTreeWidgetItem(["new"])
            current.setData(0, Qt.UserRole, {"scope": "full", "specimen_id": "new", "part_id": ""})

            with patch.object(widget, "_set_volume_canvas_status_text", return_value=True) as set_status, \
                patch("AntSleap.ui.tif_workbench.QApplication.processEvents") as process_events, \
                patch.object(widget, "load_specimen") as load_specimen:
                widget._on_specimen_tree_selected(current, previous)

            set_status.assert_called_once_with("Preparing full-volume 3D preview...", replace_existing=True)
            process_events.assert_called_once()
            load_specimen.assert_called_once_with("new")
            self.assertTrue(widget._defer_volume_preview_render_once)
            self.assertIn("Preparing full-volume 3D preview", widget.volume_render_status_label.text())
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_volume_preview_wait_state_blocks_clicks_but_allows_wheel_events(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._begin_volume_preview_ui_wait()

            self.assertTrue(widget.eventFilter(widget.specimen_list, QEvent(QEvent.MouseButtonPress)))
            self.assertTrue(widget.eventFilter(widget.specimen_list, QEvent(QEvent.KeyPress)))
            self.assertFalse(widget.eventFilter(widget.specimen_list, QEvent(QEvent.Wheel)))
        finally:
            widget._end_volume_preview_ui_wait()
            widget.close_project()
            widget.deleteLater()

    def test_metadata_only_specimen_shows_deferred_volume_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("metadata_ui", root / "metadata_ui")
            manager.create_specimen_scaffold("specimen-meta")
            specimen = manager.get_specimen("specimen-meta")
            specimen["metadata"]["import_status"] = "metadata_only"
            specimen["working_volume"].update(
                {
                    "path": "",
                    "shape_zyx": [2, 3, 4],
                    "dtype": "uint8",
                    "status": "metadata_only",
                }
            )
            manager.save_project()
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.load_specimen("specimen-meta")
                widget.display_mode = "volume"
                widget.render_volume_preview()

                self.assertIsNone(widget.image_volume)
                self.assertEqual(widget.volume_render_status_label.text(), "TIF metadata registered. Build a working volume before 3D preview.")
                self.assertIn("metadata registered", widget.volume_canvas.text())
                self.assertEqual(widget.canvas.text(), "TIF metadata registered. Build a working volume before slice review.")
                self.assertFalse(widget.slice_slider.isEnabled())
                self.assertFalse(widget.slice_axis_combo.isEnabled())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_metadata_only_slice_review_starts_working_volume_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("metadata_slice", root / "metadata_slice")
            widget = TifWorkbenchWidget(manager, "en")
            materialize_calls = []
            widget.materialize_current_tif_metadata = lambda: materialize_calls.append(True) or True
            manager.create_specimen_scaffold("specimen-meta")
            tif_path = root / "source.tif"
            tifffile.imwrite(tif_path, np.zeros((2, 3, 4), dtype=np.uint8), photometric="minisblack")
            specimen = manager.get_specimen("specimen-meta")
            specimen["source"]["raw_tif"] = str(tif_path)
            specimen["metadata"].update({"import_status": "metadata_only", "source_tif": str(tif_path)})
            specimen["working_volume"].update({"path": "", "shape_zyx": [2, 3, 4], "dtype": "uint8", "status": "metadata_only"})
            manager.save_project()
            try:
                widget.refresh_project()
                widget.load_specimen("specimen-meta")

                self.assertTrue(materialize_calls)
                self.assertIsNone(widget.image_volume)
                self.assertEqual(widget.canvas.text(), "Working volume is being built. Slice review will be available when it finishes.")
                self.assertFalse(widget.slice_slider.isEnabled())
                self.assertFalse(widget.slice_axis_combo.isEnabled())
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_switching_metadata_only_specimen_to_volume_starts_materialize_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("metadata_volume", root / "metadata_volume")
            manager.create_specimen_scaffold("specimen-meta")
            specimen = manager.get_specimen("specimen-meta")
            specimen["metadata"]["import_status"] = "metadata_only"
            specimen["working_volume"].update({"path": "", "shape_zyx": [2, 3, 4], "dtype": "uint8", "status": "metadata_only"})
            manager.save_project()
            widget = TifWorkbenchWidget(manager, "en")
            materialize_calls = []
            widget.materialize_current_tif_metadata = lambda: materialize_calls.append(True) or True
            try:
                widget.load_specimen("specimen-meta")
                materialize_calls.clear()
                mode_index = widget.display_mode_combo.findData("volume")
                widget.display_mode_combo.setCurrentIndex(mode_index)
                widget.on_display_mode_changed()
                self.assertTrue(materialize_calls)
                self.assertEqual(widget.display_mode, "volume")
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_still_volume_preview_uses_detail_preserving_downsample(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget.image_volume = np.zeros((2, 512, 512), dtype=np.uint16)
            widget.image_volume[:, 1:257:2, 1:257:2] = 4000
            widget.volume_quality_slider.setValue(128)

            still = widget._ensure_volume_preview("still")
            drag = widget._ensure_volume_preview("drag")

            self.assertEqual(tuple(still.shape), (2, 256, 256))
            self.assertEqual(tuple(drag.shape), (2, 256, 256))
            self.assertGreater(int(still.max()), int(drag.max()))
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

    def test_full_volume_roi_high_detail_uploads_original_bbox_crop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("roi_detail", root / "roi_detail")
            manager.create_specimen_scaffold("01-0101-roi")
            image = np.zeros((6, 32, 32), dtype=np.uint16)
            image[:, 24:, 24:] = 60000
            image[1:4, 4:20, 6:22] = 4000
            image_rel = "specimens/01-0101-roi/working/image.ome.zarr"
            image_meta = write_volume_sidecar(root / "roi_detail" / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-roi", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            widget = TifWorkbenchWidget(manager, "en")

            class FakeGpuLabel(QLabel):
                def __init__(self):
                    super().__init__()
                    self.uploads = []
                    self.render_state_kwargs = []
                    self.source_shapes = []

                def set_volume_data(self, volume, *args, **kwargs):
                    self.uploads.append(np.asarray(volume).copy())
                    self.source_shapes.append(tuple(kwargs.get("source_shape") or ()))

                def set_render_state(self, *args, **kwargs):
                    self.render_state_kwargs.append(dict(kwargs))

            fake_canvas = FakeGpuLabel()
            try:
                widget.load_specimen("01-0101-roi")
                widget._volume_canvas_renderer = "gpu"
                widget._volume_canvas_created = True
                widget.view_stack.addWidget(fake_canvas)
                widget.volume_canvas = fake_canvas
                widget.display_mode = "volume"
                widget._volume_render_mode = "still"
                widget._volume_zoom = 2.5
                widget.volume_roi_detail_check.setChecked(True)
                widget.volume_roi_source_combo.setCurrentIndex(widget.volume_roi_source_combo.findData("current_bbox"))
                widget.volume_roi_inspect_check.setChecked(True)
                widget.volume_roi_scale_slider.setValue(250)
                widget.volume_quality_slider.setValue(4096)
                widget.part_bbox_edit.setText("1,4,4,20,6,22")
                fake_canvas.uploads.clear()
                fake_canvas.source_shapes.clear()
                fake_canvas.render_state_kwargs.clear()

                widget.render_volume_preview()

                self.assertEqual(len(fake_canvas.uploads), 1)
                uploaded = fake_canvas.uploads[-1]
                self.assertEqual(tuple(uploaded.shape), (3, 16, 16))
                self.assertEqual(uploaded.dtype, np.uint16)
                self.assertEqual(int(uploaded.max()), 4000)
                self.assertEqual(fake_canvas.source_shapes[-1], (3, 16, 16))
                self.assertEqual(widget._volume_roi_preview_bbox, [[1, 4], [4, 20], [6, 22]])
                report = widget.volume_performance_report()
                self.assertTrue(report["roi_inspect_enabled"])
                self.assertTrue(report["roi_inspect_active"])
                self.assertEqual(report["roi_source_shape_zyx"], (3, 16, 16))
                self.assertEqual(report["roi_texture_budget_bytes"], widget._roi_texture_budget_bytes())
                self.assertEqual(manager.list_parts("01-0101-roi"), [])

                widget._volume_render_mode = "drag"
                drag = widget._ensure_volume_preview("drag")
                self.assertEqual(widget._volume_roi_preview_bbox, None)
                self.assertNotEqual(tuple(drag.shape), (3, 16, 16))
            finally:
                widget.close_project()
                widget.deleteLater()
                fake_canvas.deleteLater()

    def test_roi_crop_request_uses_roi_status_text_at_default_zoom(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_render_mode = "still"
            widget.display_mode = "volume"
            widget.current_volume_scope = "full"
            widget.image_volume = np.zeros((6, 32, 32), dtype=np.uint16)
            widget.part_bbox_edit.setText("1,4,4,20,6,22")
            widget.volume_roi_detail_check.setChecked(True)
            widget.volume_roi_source_combo.setCurrentIndex(widget.volume_roi_source_combo.findData("current_bbox"))
            widget.volume_roi_inspect_check.setChecked(True)
            widget._volume_zoom = 1.0

            request = widget._volume_preview_request("still")

            self.assertEqual(request["roi_bbox"], [[1, 4], [4, 20], [6, 22]])
            self.assertEqual(request["message"], "正在准备 ROI 裁剪块预览...")
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_full_volume_bbox_does_not_crop_without_roi_inspect(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_render_mode = "still"
            widget._volume_zoom = 2.5
            widget.current_volume_scope = "full"
            widget.image_volume = np.zeros((6, 32, 32), dtype=np.uint16)
            widget.image_volume[1:4, 4:20, 6:22] = 4000
            widget.part_bbox_edit.setText("1,4,4,20,6,22")
            widget.volume_roi_detail_check.setChecked(True)
            widget.volume_roi_source_combo.setCurrentIndex(widget.volume_roi_source_combo.findData("current_bbox"))
            widget.volume_roi_inspect_check.setChecked(False)
            widget.volume_roi_scale_slider.setValue(250)
            widget.volume_quality_slider.setValue(4096)

            preview = widget._ensure_volume_preview("still")

            self.assertNotEqual(tuple(preview.shape), (3, 16, 16))
            self.assertEqual(widget._volume_roi_preview_bbox, None)
            report = widget.volume_performance_report()
            self.assertFalse(report["roi_inspect_enabled"])
            self.assertFalse(report["roi_inspect_active"])
            self.assertEqual(report["roi_source_shape_zyx"], ())
            self.assertIn("ROI 2.5x", widget.volume_canvas_overlay_text())
            self.assertNotIn("ROI crop source", widget.volume_canvas_overlay_text())
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_full_volume_bbox_does_not_crop_until_bbox_source_selected(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_render_mode = "still"
            widget._volume_zoom = 2.5
            widget.current_volume_scope = "full"
            widget.image_volume = np.zeros((6, 32, 32), dtype=np.uint16)
            widget.image_volume[1:4, 4:20, 6:22] = 4000
            widget.part_bbox_edit.setText("1,4,4,20,6,22")
            widget.volume_roi_detail_check.setChecked(True)
            widget.volume_roi_source_combo.setCurrentIndex(widget.volume_roi_source_combo.findData("full"))
            widget.volume_roi_inspect_check.setChecked(True)
            widget.volume_roi_scale_slider.setValue(250)
            widget.volume_quality_slider.setValue(4096)

            preview = widget._ensure_volume_preview("still")

            self.assertNotEqual(tuple(preview.shape), (3, 16, 16))
            self.assertEqual(widget._volume_roi_preview_bbox, None)
            report = widget.volume_performance_report()
            self.assertEqual(report["roi_source_mode"], "full")
            self.assertTrue(report["roi_inspect_enabled"])
            self.assertFalse(report["roi_inspect_active"])
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_volume_roi_source_can_use_saved_roi_draft(self):
        manager = TifProjectManager()
        manager.project_data["specimens"].append(
            {
                "specimen_id": "specimen-roi",
                "display_name": "specimen-roi",
                "metadata_ref": "",
                "modality": "unknown",
                "source": {},
                "working_volume": {"path": "", "shape_zyx": [6, 32, 32], "dtype": "uint16", "spacing_zyx": [], "format": ""},
                "labels": {"manual_truth": {"path": ""}, "working_edit": {"path": ""}, "model_drafts": []},
                "material_map": "",
                "review_status": "not_started",
                "train_ready": False,
                "provenance": {},
                "metadata": {},
                "parts": [],
                "part_rois": [],
            }
        )
        manager.add_part_roi("specimen-roi", "head_roi", display_name="Head", bbox_zyx=[[1, 4], [4, 20], [6, 22]], save=False)
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget.current_specimen_id = "specimen-roi"
            widget._populate_volume_roi_source_combo()
            widget._volume_canvas_renderer = "gpu"
            widget._volume_render_mode = "still"
            widget._volume_zoom = 2.5
            widget.current_volume_scope = "full"
            widget.image_volume = np.zeros((6, 32, 32), dtype=np.uint16)
            widget.image_volume[1:4, 4:20, 6:22] = 4000
            widget.volume_roi_detail_check.setChecked(True)
            widget.volume_roi_source_combo.setCurrentIndex(widget.volume_roi_source_combo.findData("roi:head_roi"))
            widget.volume_roi_inspect_check.setChecked(True)
            widget.volume_roi_scale_slider.setValue(250)
            widget.volume_quality_slider.setValue(4096)

            preview = widget._ensure_volume_preview("still")

            self.assertEqual(tuple(preview.shape), (3, 16, 16))
            self.assertEqual(widget._volume_roi_preview_bbox, [[1, 4], [4, 20], [6, 22]])
            self.assertEqual(widget.volume_performance_report()["roi_source_mode"], "roi:head_roi")
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_volume_roi_source_can_use_part_parent_bbox(self):
        manager = TifProjectManager()
        manager.project_data["specimens"].append(
            {
                "specimen_id": "specimen-part",
                "display_name": "specimen-part",
                "metadata_ref": "",
                "modality": "unknown",
                "source": {},
                "working_volume": {"path": "", "shape_zyx": [6, 32, 32], "dtype": "uint16", "spacing_zyx": [], "format": ""},
                "labels": {"manual_truth": {"path": ""}, "working_edit": {"path": ""}, "model_drafts": []},
                "material_map": "",
                "review_status": "not_started",
                "train_ready": False,
                "provenance": {},
                "metadata": {},
                "parts": [],
                "part_rois": [],
            }
        )
        manager.add_part(
            "specimen-part",
            "leg",
            display_name="Leg",
            image={"path": "specimens/specimen-part/parts/leg/image.ome.zarr", "shape_zyx": [3, 16, 16], "dtype": "uint16"},
            parent_bbox_zyx=[[2, 5], [8, 24], [10, 26]],
            save=False,
        )
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget.current_specimen_id = "specimen-part"
            widget._populate_volume_roi_source_combo()
            widget._volume_canvas_renderer = "gpu"
            widget._volume_render_mode = "still"
            widget._volume_zoom = 2.5
            widget.current_volume_scope = "full"
            widget.image_volume = np.zeros((6, 32, 32), dtype=np.uint16)
            widget.image_volume[2:5, 8:24, 10:26] = 5000
            widget.volume_roi_detail_check.setChecked(True)
            widget.volume_roi_source_combo.setCurrentIndex(widget.volume_roi_source_combo.findData("part:leg"))
            widget.volume_roi_inspect_check.setChecked(True)
            widget.volume_roi_scale_slider.setValue(250)
            widget.volume_quality_slider.setValue(4096)

            preview = widget._ensure_volume_preview("still")

            self.assertEqual(tuple(preview.shape), (3, 16, 16))
            self.assertEqual(widget._volume_roi_preview_bbox, [[2, 5], [8, 24], [10, 26]])
            self.assertEqual(widget.volume_performance_report()["roi_source_mode"], "part:leg")
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_roi_high_detail_budget_preset_controls_texture_budget_and_cache_key(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_render_mode = "still"
            widget._volume_zoom = 2.5
            widget.image_volume = np.zeros((8, 64, 64), dtype=np.uint16)
            widget.part_bbox_edit.setText("0,8,0,64,0,64")
            widget.volume_roi_detail_check.setChecked(True)
            widget.volume_roi_source_combo.setCurrentIndex(widget.volume_roi_source_combo.findData("current_bbox"))
            widget.volume_roi_inspect_check.setChecked(True)
            widget.volume_quality_slider.setValue(4096)

            balanced = widget._ensure_volume_preview("still")
            balanced_key = widget._volume_preview_source_shape
            balanced_budget = widget._roi_texture_budget_bytes()
            high_index = widget.volume_roi_budget_combo.findData("high")
            self.assertGreaterEqual(high_index, 0)

            widget.volume_roi_budget_combo.setCurrentIndex(high_index)
            high = widget._ensure_volume_preview("still")
            high_key = widget._volume_preview_source_shape

            self.assertGreater(widget._roi_texture_budget_bytes(), balanced_budget)
            self.assertNotEqual(balanced_key, high_key)
            self.assertEqual(high_key[-1], widget._roi_texture_budget_bytes())
            self.assertEqual(tuple(high.shape), tuple(balanced.shape))
            self.assertIn("ROI budget 2.5 GB", widget.volume_canvas_overlay_text())
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_cpu_volume_front_clip_discards_viewer_side_depths(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        try:
            depths = np.asarray([-0.8, -0.2, 0.3, 0.9], dtype=np.float32)
            keep = widget._viewer_side_front_clip_mask(depths, 0.5)

            np.testing.assert_array_equal(keep, np.asarray([True, True, False, False]))
            np.testing.assert_array_equal(widget._viewer_side_front_clip_mask(depths, 0.0), np.ones(depths.shape, dtype=bool))
        finally:
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

    def test_clarity_toggle_keeps_previous_preview_variants_cached(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_render_mode = "still"
            widget.current_volume_scope = "full"
            widget.image_volume = np.arange(8 * 16 * 16, dtype=np.uint16).reshape((8, 16, 16))

            widget._volume_clarity_mode = False
            normal_request = widget._volume_preview_request("still")
            normal_preview = widget._ensure_volume_preview("still")
            self.assertIn(normal_request["cache_key"], widget._volume_preview_cache)

            widget._on_volume_clarity_toggled(True)
            clarity_request = widget._volume_preview_request("still")
            clarity_preview = widget._ensure_volume_preview("still")
            self.assertIn(clarity_request["cache_key"], widget._volume_preview_cache)
            self.assertIn(normal_request["cache_key"], widget._volume_preview_cache)
            self.assertIs(widget._volume_preview_cache[normal_request["cache_key"]], normal_preview)

            widget._on_volume_clarity_toggled(False)
            reused_normal = widget._ensure_volume_preview("still")

            self.assertIs(reused_normal, normal_preview)
            self.assertIn(clarity_request["cache_key"], widget._volume_preview_cache)
            self.assertIs(widget._volume_preview_cache[clarity_request["cache_key"]], clarity_preview)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_volume_preview_cache_limits_variants_per_owner(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            owner = ("specimen", "full", "", "")
            other_owner = ("other", "full", "", "")
            for index in range(10):
                key = (owner, (2, 2, 2), "uint8", 128 + index, False, "hybrid", None, index)
                widget._volume_preview_cache[key] = np.zeros((1, 1, 1), dtype=np.uint8)
            other_key = (other_owner, (2, 2, 2), "uint8", 128, False, "hybrid", None, 0)
            widget._volume_preview_cache[other_key] = np.ones((1, 1, 1), dtype=np.uint8)

            widget._prune_volume_preview_cache()

            owner_keys = [
                key for key in widget._volume_preview_cache.keys()
                if widget._volume_cache_owner_from_key(key) == owner
            ]
            self.assertLessEqual(len(owner_keys), 8)
            self.assertNotIn((owner, (2, 2, 2), "uint8", 128, False, "hybrid", None, 0), widget._volume_preview_cache)
            self.assertIn(other_key, widget._volume_preview_cache)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_default_mask_mode_change_keeps_volume_preview_cache(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget.current_specimen_id = "specimen"
            widget.current_volume_scope = "part"
            widget.current_part_id = "part"
            widget.current_part = {"view_settings": {"volume_mask_mode": "masked_image"}}
            widget.image_volume = np.zeros((2, 4, 4), dtype=np.uint8)
            widget.part_preview_mask = np.ones((2, 4, 4), dtype=np.uint8)
            owner = widget._active_volume_cache_owner()
            volume_key = (owner, (2, 4, 4), "uint8", 128, False, "hybrid", None, 0)
            mask_key = (owner, (2, 4, 4), "uint8", 128, 1, "occupancy", None)
            widget._volume_preview_cache[volume_key] = np.zeros((2, 4, 4), dtype=np.uint8)
            widget._volume_mask_preview_cache[mask_key] = np.ones((2, 4, 4), dtype=np.uint8)

            widget._apply_default_volume_mask_mode()

            self.assertEqual(widget.volume_mask_combo.currentData(), "masked_image")
            self.assertIn(volume_key, widget._volume_preview_cache)
            self.assertNotIn(mask_key, widget._volume_mask_preview_cache)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_volume_performance_report_exposes_gpu_texture_cache(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget.image_volume = np.zeros((2, 4, 4), dtype=np.uint8)
            widget._volume_last_stats = {
                "shape_zyx": (2, 4, 4),
                "dtype": "uint8",
                "bytes": 32,
                "texture_cache_entries": 3,
                "texture_cache_bytes": 256 * 1024 * 1024,
                "texture_cache_budget_bytes": 5 * 1024 * 1024 * 1024,
                "texture_cache_hits": 4,
                "texture_cache_misses": 1,
            }

            report = widget.volume_performance_report()
            overlay = widget.volume_canvas_overlay_text()

            self.assertEqual(report["gpu_texture_cache_entries"], 3)
            self.assertEqual(report["gpu_texture_cache_hits"], 4)
            self.assertEqual(report["gpu_texture_cache_misses"], 1)
            self.assertIn("GPU cache 3 256 MB hit 4/5", overlay)
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

    def test_local_detail_check_keeps_roi_high_detail_supersample(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_render_mode = "still"
            widget.image_volume = np.zeros((4, 32, 32), dtype=np.uint8)
            widget._volume_zoom = 3.0
            widget.volume_roi_detail_check.setChecked(True)
            widget.volume_roi_scale_slider.setValue(250)
            self.assertEqual(widget._active_volume_roi_scale(), 2.5)

            widget.volume_clarity_check.setChecked(True)

            self.assertEqual(widget._active_volume_roi_scale(), 2.5)
            self.assertIn("局部结构检查", widget.volume_canvas_overlay_text())
            self.assertIn("ROI 2.5x", widget.volume_canvas_overlay_text())
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_part_local_detail_check_raises_still_texture_target(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget.current_volume_scope = "part"
            widget.image_volume = np.zeros((10, 2200, 2200), dtype=np.uint8)
            widget.volume_quality_slider.setValue(1024)

            self.assertEqual(widget._active_volume_target_dim("still"), 1536)

            widget.volume_clarity_check.setChecked(True)

            self.assertEqual(widget._active_volume_target_dim("still"), 2200)
            self.assertEqual(widget._active_volume_target_dim("drag"), 384)
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

    def test_morphology_transfer_function_is_available_without_reuploading_texture(self):
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
            before_upload = fake_canvas.upload_ids[-1]
            morphology_index = widget.volume_tint_combo.findData("morphology")
            self.assertGreaterEqual(morphology_index, 0)
            widget.volume_tint_combo.setCurrentIndex(morphology_index)

            self.assertEqual(fake_canvas.upload_ids[-1], before_upload)
            self.assertEqual(fake_canvas.render_state_kwargs[-1]["transfer_preset"], "morphology")
            self.assertAlmostEqual(fake_canvas.render_state_kwargs[-1]["gradient_opacity"], 0.65)
            self.assertEqual(fake_canvas.render_state_kwargs[-1]["gradient_opacity_range"], (0.04, 0.34))
            self.assertGreater(fake_canvas.render_state_kwargs[-1]["jitter_strength"], 0.0)
            self.assertGreater(fake_canvas.render_state_kwargs[-1]["adaptive_step_strength"], 0.0)
            self.assertIn("Morphology Inspect", widget.volume_canvas_overlay_text())
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_shader_quality_mode_controls_experimental_rendering(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuLabel(QLabel):
            def __init__(self):
                super().__init__()
                self.render_state_kwargs = []

            def set_volume_data(self, *args, **kwargs):
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
            state = fake_canvas.render_state_kwargs[-1]
            self.assertEqual(state["shader_quality_mode"], "preset")
            self.assertEqual(state["transfer_preset"], "amber")
            self.assertEqual(state["jitter_strength"], 0.0)
            self.assertEqual(state["adaptive_step_strength"], 0.0)
            self.assertEqual(state["gradient_opacity"], 0.0)

            morphology_index = widget.volume_tint_combo.findData("morphology")
            widget.volume_tint_combo.setCurrentIndex(morphology_index)
            state = fake_canvas.render_state_kwargs[-1]
            self.assertGreater(state["jitter_strength"], 0.0)
            self.assertGreater(state["adaptive_step_strength"], 0.0)
            self.assertGreater(state["gradient_opacity"], 0.0)

            off_index = widget.volume_shader_quality_combo.findData("off")
            widget.volume_shader_quality_combo.setCurrentIndex(off_index)
            state = fake_canvas.render_state_kwargs[-1]
            self.assertEqual(state["shader_quality_mode"], "off")
            self.assertEqual(state["jitter_strength"], 0.0)
            self.assertEqual(state["adaptive_step_strength"], 0.0)
            self.assertEqual(state["gradient_opacity"], 0.0)

            amber_index = widget.volume_tint_combo.findData("amber")
            all_index = widget.volume_shader_quality_combo.findData("all_still")
            widget.volume_tint_combo.setCurrentIndex(amber_index)
            widget.volume_shader_quality_combo.setCurrentIndex(all_index)
            state = fake_canvas.render_state_kwargs[-1]
            self.assertEqual(state["shader_quality_mode"], "all_still")
            self.assertGreater(state["jitter_strength"], 0.0)
            self.assertGreater(state["adaptive_step_strength"], 0.0)
            self.assertEqual(state["gradient_opacity"], 0.0)
            self.assertIn("Shader quality All still composite", widget.volume_canvas_overlay_text())
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_apply_morphology_inspect_preset_updates_display_without_reuploading_texture(self):
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
            first_upload = fake_canvas.upload_ids[-1]
            widget.apply_morphology_inspect_preset()

            self.assertEqual(fake_canvas.upload_ids[-1], first_upload)
            state = fake_canvas.render_state_kwargs[-1]
            self.assertEqual(state["transfer_preset"], "morphology")
            self.assertEqual(state["projection_mode"], "composite")
            self.assertEqual(state["shader_quality_mode"], "preset")
            self.assertAlmostEqual(state["enhancement"], 0.72)
            self.assertAlmostEqual(state["tone_gamma"], 0.92)
            self.assertAlmostEqual(state["gradient_opacity"], 0.65)
            self.assertEqual(state["gradient_opacity_range"], (0.04, 0.34))
            self.assertAlmostEqual(state["jitter_strength"], 0.42)
            self.assertAlmostEqual(state["adaptive_step_strength"], 0.35)
            self.assertTrue(state["surface_refine"])
            self.assertEqual(widget.volume_cutoff_slider.value(), 18)
            self.assertEqual(widget.project.project_data["view_settings"]["volume_tint"], "morphology")
            self.assertEqual(widget.project.project_data["view_settings"]["volume_shader_quality"], "preset")
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
            self.assertEqual(fake_canvas.interaction_state_kwargs[-1]["jitter_strength"], 0.0)
            self.assertEqual(fake_canvas.interaction_state_kwargs[-1]["adaptive_step_strength"], 0.0)
            self.assertEqual(fake_canvas.interaction_state_kwargs[-1]["gradient_opacity"], 0.0)
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

    def test_large_gpu_upload_uses_non_modal_status(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuLabel(QLabel):
            def __init__(self):
                super().__init__()
                self.render_inputs = []
                self.text_updates = []

            def setText(self, text):
                self.text_updates.append(str(text or ""))
                super().setText(text)

            def has_volume(self):
                return True

            def set_volume_data(self, volume, *args, **kwargs):
                return None

            def set_volume_render_inputs(self, volume, *args, **kwargs):
                self.render_inputs.append((volume, kwargs))

        fake_canvas = FakeGpuLabel()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget._volume_render_mode = "still"
            widget.display_mode = "volume"
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            preview = np.zeros((33, 1024, 1024), dtype=np.uint8)

            FakeProgressDialog.instances.clear()
            with patch("AntSleap.ui.tif_workbench.QProgressDialog", FakeProgressDialog):
                self.assertTrue(widget._sync_gpu_volume_canvas(preview))

            self.assertEqual(len(fake_canvas.render_inputs), 1)
            self.assertEqual(len(FakeProgressDialog.instances), 0)
            self.assertIn("Uploading 3D preview to GPU", widget.volume_render_status_label.text())
            self.assertNotIn("Uploading 3D preview to GPU...", fake_canvas.text_updates)
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_large_gpu_upload_keeps_previous_frame_without_forced_process_events(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuLabel(QLabel):
            def __init__(self):
                super().__init__()
                self.render_inputs = []

            def has_volume(self):
                return True

            def set_volume_data(self, volume, *args, **kwargs):
                return None

            def set_volume_render_inputs(self, volume, *args, **kwargs):
                self.render_inputs.append((volume, kwargs))

        fake_canvas = FakeGpuLabel()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget._volume_render_mode = "still"
            widget.display_mode = "volume"
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            preview = np.zeros((33, 1024, 1024), dtype=np.uint8)

            with patch("AntSleap.ui.tif_workbench.QApplication.processEvents") as process_events:
                self.assertTrue(widget._sync_gpu_volume_canvas(preview))

            self.assertEqual(len(fake_canvas.render_inputs), 1)
            process_events.assert_not_called()
            self.assertIn("Uploading 3D preview to GPU", widget.volume_render_status_label.text())
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_full_volume_still_preview_prefers_gpu_stream_build_before_cpu_preview(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuStreamCanvas(QLabel):
            def __init__(self):
                super().__init__()
                self.build_calls = []
                self.render_states = []
                self.mask_uploads = []

            def has_volume(self):
                return bool(self.build_calls)

            def build_volume_texture_from_source(self, volume, max_dim, **kwargs):
                self.build_calls.append((volume, int(max_dim), dict(kwargs)))
                return object()

            def set_mask_data(self, mask, *args, **kwargs):
                self.mask_uploads.append(mask)

            def set_render_state(self, **kwargs):
                self.render_states.append(dict(kwargs))

            def render_stats(self):
                return {"preview_provider": {"kind": "gpu_texture", "build_backend": "gpu_stream"}}

        fake_canvas = FakeGpuStreamCanvas()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget._volume_render_mode = "still"
            widget.display_mode = "volume"
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget.image_volume = np.zeros((4, 16, 16), dtype=np.uint8)
            widget.image_volume[:, 4:12, 4:12] = 180

            with patch("AntSleap.ui.tif_workbench.build_volume_preview") as cpu_builder:
                widget.render_volume_preview()

            cpu_builder.assert_not_called()
            self.assertEqual(len(fake_canvas.build_calls), 1)
            self.assertEqual(fake_canvas.build_calls[0][1], widget._active_volume_target_dim("still"))
            self.assertEqual(fake_canvas.build_calls[0][2]["cache_key"], widget._volume_preview_request("still")["cache_key"])
            self.assertEqual(fake_canvas.mask_uploads[-1], None)
            self.assertEqual(fake_canvas.render_states[-1]["mask_mode"], "image_only")
            self.assertEqual(widget._volume_last_stats["preview_provider"]["build_backend"], "gpu_stream")
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_large_full_volume_prefers_gpu_stream_before_background_cpu_preview(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class ShapeOnlyVolume:
            def __init__(self, shape, dtype):
                self.shape = tuple(int(value) for value in shape)
                self.dtype = np.dtype(dtype)
                self.nbytes = int(np.prod(self.shape, dtype=np.int64)) * int(self.dtype.itemsize)

            def __getitem__(self, _key):
                raise AssertionError("full-volume GPU stream should receive the source without UI-thread CPU slicing")

        class FakeGpuStreamCanvas(QLabel):
            def __init__(self):
                super().__init__()
                self.build_calls = []
                self.mask_uploads = []
                self.render_states = []

            def has_volume(self):
                return bool(self.build_calls)

            def build_volume_texture_from_source(self, volume, max_dim, **kwargs):
                self.build_calls.append((volume, int(max_dim), dict(kwargs)))
                return object()

            def set_mask_data(self, mask, *args, **kwargs):
                self.mask_uploads.append(mask)

            def set_render_state(self, **kwargs):
                self.render_states.append(dict(kwargs))

            def render_stats(self):
                return {"preview_provider": {"kind": "gpu_texture", "build_backend": "gpu_stream"}}

        fake_canvas = FakeGpuStreamCanvas()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget._volume_render_mode = "still"
            widget.current_volume_scope = "full"
            widget.display_mode = "volume"
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget.image_volume = ShapeOnlyVolume((120, 1600, 1600), np.uint8)
            widget.volume_quality_slider.setValue(1024)

            with patch.object(widget, "_start_volume_preview_build") as background_start, \
                patch("AntSleap.ui.tif_workbench.build_volume_preview") as cpu_builder:
                widget.render_volume_preview()

            background_start.assert_not_called()
            cpu_builder.assert_not_called()
            self.assertEqual(len(fake_canvas.build_calls), 1)
            self.assertIs(fake_canvas.build_calls[0][0], widget.image_volume)
            self.assertEqual(fake_canvas.build_calls[0][2]["cache_key"], widget._volume_preview_request("still")["cache_key"])
            self.assertEqual(fake_canvas.mask_uploads[-1], None)
            self.assertEqual(fake_canvas.render_states[-1]["mask_mode"], "image_only")
            self.assertEqual(widget._volume_last_stats["preview_provider"]["build_backend"], "gpu_stream")
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_gpu_stream_rebuild_keeps_existing_frame_without_pending_flash(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuStreamCanvas(QLabel):
            def __init__(self):
                super().__init__()
                self.build_calls = []
                self.text_updates = []

            def has_volume(self):
                return True

            def setText(self, text):
                self.text_updates.append(str(text))
                super().setText(text)

            def build_volume_texture_from_source(self, volume, max_dim, **kwargs):
                self.build_calls.append((volume, int(max_dim), dict(kwargs)))
                return object()

            def set_mask_data(self, mask, *args, **kwargs):
                return None

            def set_render_state(self, **kwargs):
                return None

            def render_stats(self):
                return {"preview_provider": {"kind": "gpu_texture", "build_backend": "gpu_stream"}}

        fake_canvas = FakeGpuStreamCanvas()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget._volume_render_mode = "still"
            widget.display_mode = "volume"
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget.image_volume = np.zeros((4, 16, 16), dtype=np.uint8)

            with patch("AntSleap.ui.tif_workbench.build_volume_preview") as cpu_builder:
                widget.render_volume_preview()

            cpu_builder.assert_not_called()
            self.assertEqual(len(fake_canvas.build_calls), 1)
            self.assertNotIn("Preparing full-volume 3D preview...", fake_canvas.text_updates)
            self.assertEqual(widget._volume_last_stats["preview_provider"]["build_backend"], "gpu_stream")
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_roi_crop_preview_prefers_gpu_stream_build_before_cpu_preview(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuStreamCanvas(QLabel):
            def __init__(self):
                super().__init__()
                self.build_calls = []
                self.render_states = []
                self.mask_uploads = []

            def has_volume(self):
                return bool(self.build_calls)

            def build_volume_texture_from_source(self, volume, max_dim, **kwargs):
                self.build_calls.append((volume, int(max_dim), dict(kwargs)))
                return object()

            def set_mask_data(self, mask, *args, **kwargs):
                self.mask_uploads.append(mask)

            def set_render_state(self, **kwargs):
                self.render_states.append(dict(kwargs))

            def render_stats(self):
                return {"preview_provider": {"kind": "gpu_texture", "build_backend": "gpu_stream"}}

        fake_canvas = FakeGpuStreamCanvas()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget._volume_render_mode = "still"
            widget.display_mode = "volume"
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget.image_volume = np.zeros((6, 32, 32), dtype=np.uint16)
            widget.part_bbox_edit.setText("1,5,8,24,10,26")
            widget.volume_roi_detail_check.setChecked(True)
            widget.volume_roi_source_combo.setCurrentIndex(widget.volume_roi_source_combo.findData("current_bbox"))
            widget.volume_roi_inspect_check.setChecked(True)
            fake_canvas.build_calls.clear()
            fake_canvas.render_states.clear()
            fake_canvas.mask_uploads.clear()

            with patch("AntSleap.ui.tif_workbench.build_roi_volume_preview") as cpu_roi_builder:
                widget.render_volume_preview()

            cpu_roi_builder.assert_not_called()
            self.assertEqual(len(fake_canvas.build_calls), 1)
            self.assertEqual(tuple(fake_canvas.build_calls[0][0].shape), (4, 16, 16))
            self.assertEqual(fake_canvas.build_calls[0][2]["cache_key"], widget._volume_preview_request("still")["cache_key"])
            self.assertEqual(fake_canvas.render_states[-1]["mask_mode"], "image_only")
            self.assertEqual(widget._volume_roi_preview_source_shape, (4, 16, 16))
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_part_local_detail_preview_prefers_gpu_stream_build_before_cpu_preview(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuStreamCanvas(QLabel):
            def __init__(self):
                super().__init__()
                self.build_calls = []
                self.mask_build_calls = []
                self.mask_uploads = []
                self.render_states = []

            def has_volume(self):
                return bool(self.build_calls)

            def build_volume_texture_from_source(self, volume, max_dim, **kwargs):
                self.build_calls.append((volume, int(max_dim), dict(kwargs)))
                return object()

            def build_mask_texture_from_source(self, mask, max_dim, **kwargs):
                self.mask_build_calls.append((mask, int(max_dim), dict(kwargs)))
                return True

            def set_mask_data(self, mask, *args, **kwargs):
                self.mask_uploads.append(mask)

            def set_render_state(self, **kwargs):
                self.render_states.append(dict(kwargs))

            def render_stats(self):
                return {"preview_provider": {"kind": "gpu_texture", "build_backend": "gpu_stream"}}

        fake_canvas = FakeGpuStreamCanvas()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget._volume_render_mode = "still"
            widget.current_volume_scope = "part"
            widget.display_mode = "volume"
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget.image_volume = np.zeros((4, 32, 32), dtype=np.uint8)
            widget.part_preview_mask = np.zeros((4, 32, 32), dtype=np.uint8)
            widget.part_preview_mask[:, 8:24, 8:24] = 1
            widget.volume_clarity_check.setChecked(True)
            widget.volume_mask_combo.setCurrentIndex(widget.volume_mask_combo.findData("masked_image"))
            fake_canvas.build_calls.clear()
            fake_canvas.mask_build_calls.clear()
            fake_canvas.render_states.clear()
            fake_canvas.mask_uploads.clear()

            with patch("AntSleap.ui.tif_workbench.build_volume_preview") as cpu_builder, \
                patch("AntSleap.ui.tif_workbench.build_mask_preview") as cpu_mask_builder:
                widget.render_volume_preview()

            cpu_builder.assert_not_called()
            cpu_mask_builder.assert_not_called()
            self.assertEqual(len(fake_canvas.build_calls), 1)
            self.assertEqual(len(fake_canvas.mask_build_calls), 1)
            self.assertEqual(tuple(fake_canvas.build_calls[0][0].shape), (4, 32, 32))
            self.assertEqual(tuple(fake_canvas.mask_build_calls[0][0].shape), (4, 32, 32))
            self.assertEqual(fake_canvas.mask_build_calls[0][2]["cache_key"], widget._volume_mask_preview_request("still")["cache_key"])
            self.assertEqual(fake_canvas.mask_uploads, [])
            self.assertEqual(fake_canvas.render_states[-1]["mask_mode"], "masked_image")
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_large_part_volume_preview_starts_background_before_gpu_stream_build(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuStreamCanvas(QLabel):
            def __init__(self):
                super().__init__()
                self.build_calls = []

            def has_volume(self):
                return False

            def build_volume_texture_from_source(self, volume, max_dim, **kwargs):
                self.build_calls.append((volume, int(max_dim), dict(kwargs)))
                return object()

            def set_mask_data(self, mask, *args, **kwargs):
                return None

            def set_render_state(self, **kwargs):
                return None

        fake_canvas = FakeGpuStreamCanvas()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget._volume_render_mode = "still"
            widget.current_volume_scope = "part"
            widget.display_mode = "volume"
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget.image_volume = np.zeros((40, 1024, 1024), dtype=np.uint8)
            widget.volume_quality_slider.setValue(512)
            starts = []

            def fake_start(volume_request=None, mask_request=None):
                starts.append((volume_request, mask_request))
                widget._volume_preview_build_thread = object()
                return True

            with patch.object(widget, "_start_volume_preview_build", side_effect=fake_start), \
                patch("AntSleap.ui.tif_workbench.build_volume_preview") as cpu_builder:
                widget.render_volume_preview()

            self.assertEqual(len(starts), 1)
            self.assertIsNotNone(starts[0][0])
            self.assertEqual(starts[0][0]["cache_key"], widget._volume_preview_request("still")["cache_key"])
            self.assertEqual(fake_canvas.build_calls, [])
            cpu_builder.assert_not_called()
        finally:
            widget._volume_preview_build_thread = None
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_full_volume_part_mask_preview_uses_roi_background_for_3d(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class ShapeOnlyVolume:
            def __init__(self, shape, dtype):
                self.shape = tuple(int(value) for value in shape)
                self.dtype = np.dtype(dtype)
                self.nbytes = int(np.prod(self.shape, dtype=np.int64)) * int(self.dtype.itemsize)

            def __getitem__(self, _key):
                raise AssertionError("large preview source should not be sliced on the UI thread")

        class FakeGpuStreamCanvas(QLabel):
            def __init__(self):
                super().__init__()
                self.build_calls = []
                self.mask_build_calls = []
                self.mask_uploads = []
                self.render_states = []

            def has_volume(self):
                return False

            def build_volume_texture_from_source(self, volume, max_dim, **kwargs):
                self.build_calls.append((volume, int(max_dim), dict(kwargs)))
                return object()

            def build_mask_texture_from_source(self, mask, max_dim, **kwargs):
                self.mask_build_calls.append((mask, int(max_dim), dict(kwargs)))
                return True

            def set_mask_data(self, mask, *args, **kwargs):
                self.mask_uploads.append(mask)

            def set_render_state(self, **kwargs):
                self.render_states.append(dict(kwargs))

        fake_canvas = FakeGpuStreamCanvas()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget._volume_render_mode = "still"
            widget.current_volume_scope = "full"
            widget.display_mode = "volume"
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget.image_volume = ShapeOnlyVolume((80, 1200, 1200), np.uint8)
            widget.part_mask_preview_bbox = [[8, 72], [100, 1100], [120, 1120]]
            widget.part_preview_mask = ShapeOnlyVolume((64, 1000, 1000), np.uint16)
            starts = []

            def fake_start(volume_request=None, mask_request=None):
                starts.append((volume_request, mask_request))
                widget._volume_preview_build_thread = object()
                return True

            with patch.object(widget, "_start_volume_preview_build", side_effect=fake_start), \
                patch("AntSleap.ui.tif_workbench.build_roi_volume_preview") as cpu_roi_builder, \
                patch("AntSleap.ui.tif_workbench.build_roi_mask_preview") as cpu_mask_builder:
                widget._apply_default_volume_mask_mode()
                widget.render_volume_preview()

            self.assertEqual(widget.volume_mask_combo.currentData(), "masked_image")
            self.assertEqual(len(starts), 1)
            volume_request, mask_request = starts[0]
            self.assertIsNotNone(volume_request)
            self.assertIsNotNone(mask_request)
            self.assertEqual(volume_request["roi_bbox"], widget.part_mask_preview_bbox)
            self.assertIsNone(mask_request["roi_bbox"])
            self.assertEqual(fake_canvas.build_calls, [])
            self.assertEqual(fake_canvas.mask_build_calls, [])
            cpu_roi_builder.assert_not_called()
            cpu_mask_builder.assert_not_called()
        finally:
            widget._volume_preview_build_thread = None
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_small_part_volume_preview_can_use_gpu_stream_build(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuStreamCanvas(QLabel):
            def __init__(self):
                super().__init__()
                self.build_calls = []
                self.mask_uploads = []
                self.render_states = []

            def has_volume(self):
                return bool(self.build_calls)

            def build_volume_texture_from_source(self, volume, max_dim, **kwargs):
                self.build_calls.append((volume, int(max_dim), dict(kwargs)))
                return object()

            def set_mask_data(self, mask, *args, **kwargs):
                self.mask_uploads.append(mask)

            def set_render_state(self, **kwargs):
                self.render_states.append(dict(kwargs))

            def render_stats(self):
                return {"preview_provider": {"kind": "gpu_texture", "build_backend": "gpu_stream"}}

        fake_canvas = FakeGpuStreamCanvas()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget._volume_render_mode = "still"
            widget.current_volume_scope = "part"
            widget.display_mode = "volume"
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget.image_volume = np.zeros((4, 32, 32), dtype=np.uint8)
            widget.volume_quality_slider.setValue(512)

            with patch.object(widget, "_start_volume_preview_build") as background_start, \
                patch("AntSleap.ui.tif_workbench.build_volume_preview") as cpu_builder:
                widget.render_volume_preview()

            background_start.assert_not_called()
            cpu_builder.assert_not_called()
            self.assertEqual(len(fake_canvas.build_calls), 1)
            self.assertEqual(fake_canvas.render_states[-1]["mask_mode"], "image_only")
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_gpu_mask_source_for_roi_request_uses_roi_crop(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget.current_volume_scope = "part"
            widget.image_volume = np.zeros((6, 32, 32), dtype=np.uint8)
            widget.part_preview_mask = np.arange(6 * 32 * 32, dtype=np.uint16).reshape((6, 32, 32))
            request = {"roi_bbox": ((1, 5), (8, 24), (10, 26))}

            source, source_shape, normalized = widget._gpu_mask_source_for_request(request)

            self.assertEqual(source_shape, (4, 16, 16))
            self.assertEqual(normalized, ((1, 5), (8, 24), (10, 26)))
            self.assertEqual(tuple(source.shape), (4, 16, 16))
            self.assertEqual(int(source[0, 0, 0]), int(widget.part_preview_mask[1, 8, 10]))
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_gpu_stream_degradation_is_reported_without_extra_panel(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget.display_mode = "volume"
            widget.image_volume = np.zeros((4, 16, 16), dtype=np.uint8)
            widget._volume_last_stats = {
                "shape_zyx": (128, 128, 128),
                "dtype": "uint16",
                "bytes": 128 * 128 * 128 * 2,
                "gpu_stream_build": {
                    "degraded": True,
                    "degrade_reason": "texture_budget",
                    "requested_max_dim": 512,
                    "actual_max_dim": 128,
                },
            }

            summary = widget._volume_status_summary_text()
            details = widget._volume_stats_text()
            report = widget.volume_performance_report()

            self.assertIn("GPU budget 128/512", summary)
            self.assertIn("GPU budget auto-scaled preview 128/512", details)
            self.assertTrue(report["gpu_stream_degraded"])
            self.assertEqual(report["gpu_stream_build"]["degrade_reason"], "texture_budget")
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_volume_quality_commit_keeps_gpu_texture_cache_for_budgeted_reuse(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")

        class FakeGpuCanvas(QLabel):
            def __init__(self):
                super().__init__()
                self.release_calls = 0

            def release_texture_cache(self):
                self.release_calls += 1

            def render_stats(self):
                return {"texture_cache_entries": 2}

        fake_canvas = FakeGpuCanvas()
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_canvas_created = True
            widget.display_mode = "slice"
            widget.view_stack.addWidget(fake_canvas)
            widget.volume_canvas = fake_canvas
            widget.image_volume = np.zeros((4, 16, 16), dtype=np.uint8)
            widget._volume_quality_committed_value = 512
            widget.volume_quality_slider.setValue(1024)

            with patch.object(widget, "_refresh_volume_preview") as refresh:
                widget._commit_volume_quality_change()

            self.assertEqual(fake_canvas.release_calls, 0)
            refresh.assert_called_once()
            self.assertEqual(widget._volume_quality_committed_value, 1024)
        finally:
            widget.close_project()
            widget.deleteLater()
            fake_canvas.deleteLater()

    def test_gpu_stream_degradation_reduces_preview_cache_owner_limit(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget.volume_quality_slider.setValue(1024)

            self.assertEqual(widget._volume_cache_owner_limit(), 3)

            widget._volume_last_stats = {"gpu_stream_build": {"degraded": True}}

            self.assertEqual(widget._volume_cache_owner_limit(), 1)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_large_volume_mask_preview_can_run_in_background_with_status(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_render_mode = "still"
            widget.display_mode = "volume"
            widget.current_volume_scope = "part"
            widget.image_volume = np.zeros((4, 32, 32), dtype=np.uint8)
            widget.part_preview_mask = np.zeros((4, 32, 32), dtype=np.uint8)
            widget.part_preview_mask[:, 8:24, 8:24] = 1
            widget.volume_quality_slider.setValue(128)
            widget.volume_mask_combo.setCurrentIndex(widget.volume_mask_combo.findData("masked_image"))
            volume_request = widget._volume_preview_request("still")
            widget._cache_volume_preview_result(volume_request, np.zeros((4, 32, 32), dtype=np.uint8), 0.0)

            FakeProgressDialog.instances.clear()
            with patch("AntSleap.ui.tif_workbench.QProgressDialog", FakeProgressDialog):
                with patch.object(widget, "_should_show_volume_mask_preview_progress", return_value=True):
                    widget.render_volume_preview()

            self.assertEqual(len(FakeProgressDialog.instances), 0)
            mask_request = widget._volume_mask_preview_request("still")
            self.assertTrue(
                widget._volume_preview_build_thread is not None
                or mask_request["cache_key"] in widget._volume_mask_preview_cache
            )
            widget._cancel_and_wait_volume_preview_build()
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_stale_background_volume_preview_result_is_ignored(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._volume_canvas_renderer = "gpu"
            widget._volume_render_mode = "still"
            widget.display_mode = "volume"
            widget.image_volume = np.zeros((4, 16, 16), dtype=np.uint8)
            request = widget._volume_preview_request("still")
            stale_preview = np.ones((4, 16, 16), dtype=np.uint8)

            widget._volume_preview_pending_token = 7
            widget._volume_preview_pending_key = request["cache_key"]
            widget._on_volume_preview_build_finished(
                {
                    "token": 6,
                    "preview": stale_preview,
                    "volume_request": request,
                    "build_ms": 12.0,
                }
            )

            self.assertNotIn(request["cache_key"], widget._volume_preview_cache)
            self.assertEqual(widget._volume_preview_pending_token, 7)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_stale_background_volume_preview_context_is_cancelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                widget.display_mode = "volume"
                request = widget._volume_preview_request("still")
                task = widget._start_tif_task(
                    "volume_preview",
                    action="build_preview",
                    request_key=widget._task_request_key(request["cache_key"]),
                    message="Preparing preview",
                )
                widget._volume_preview_build_task_id = task.task_id
                widget._volume_preview_pending_token = 8
                widget._volume_preview_pending_key = request["cache_key"]
                widget._volume_preview_pending_mask_key = None
                widget.current_specimen_id = "different_specimen"

                widget._on_volume_preview_build_finished(
                    {
                        "token": 8,
                        "volume_request": request,
                        "preview": np.ones((4, 16, 16), dtype=np.uint8),
                    }
                )

                self.assertEqual(widget.task_manager.task(task.task_id).status, "cancelled")
                self.assertNotIn(request["cache_key"], widget._volume_preview_cache)
                self.assertEqual(widget._volume_preview_pending_token, 0)
            finally:
                widget.close_project()
                widget.deleteLater()

    def test_stale_background_volume_preview_cleanup_keeps_current_task(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            old_thread = object()
            old_worker = object()
            current_thread = object()
            current_worker = object()
            widget._volume_preview_build_thread = current_thread
            widget._volume_preview_build_worker = current_worker

            widget._cleanup_volume_preview_build_thread(old_thread, old_worker)

            self.assertIs(widget._volume_preview_build_thread, current_thread)
            self.assertIs(widget._volume_preview_build_worker, current_worker)

            widget._cleanup_volume_preview_build_thread(current_thread, current_worker)

            self.assertIsNone(widget._volume_preview_build_thread)
            self.assertIsNone(widget._volume_preview_build_worker)
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_background_volume_preview_busy_locks_rebuild_controls(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget.volume_quality_slider.setEnabled(True)
            widget.volume_roi_inspect_check.setEnabled(True)
            widget.volume_roi_scale_slider.setEnabled(False)
            widget.specimen_list.setEnabled(True)

            widget._set_volume_preview_build_controls_busy(True)

            self.assertFalse(widget.volume_quality_slider.isEnabled())
            self.assertFalse(widget.volume_roi_inspect_check.isEnabled())
            self.assertFalse(widget.volume_roi_scale_slider.isEnabled())
            self.assertTrue(widget.specimen_list.isEnabled())

            widget._set_volume_preview_build_controls_busy(False)

            self.assertTrue(widget.volume_quality_slider.isEnabled())
            self.assertTrue(widget.volume_roi_inspect_check.isEnabled())
            self.assertFalse(widget.volume_roi_scale_slider.isEnabled())
            self.assertTrue(widget.specimen_list.isEnabled())
        finally:
            widget.close_project()
            widget.deleteLater()

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
            self.assertEqual(widget.volume_clip_plane_depth_slider.value(), 0)
            widget.volume_clip_plane_check.setChecked(True)
            widget.volume_clip_plane_depth_slider.setValue(62)
            widget.render_volume_preview()

            state = fake_canvas.render_state_kwargs[-1]
            self.assertAlmostEqual(state["enhancement"], 0.8)
            self.assertAlmostEqual(state["tone_gamma"], 0.9)
            self.assertEqual(state["shader_quality_mode"], "preset")
            self.assertEqual(state["jitter_strength"], 0.0)
            self.assertEqual(state["adaptive_step_strength"], 0.0)
            self.assertEqual(state["gradient_opacity"], 0.0)
            self.assertTrue(state["surface_refine"])
            self.assertTrue(state["clip_plane_enabled"])
            self.assertAlmostEqual(state["clip_plane_depth"], 0.62)
            self.assertEqual(len(state["clip_plane_normal"]), 3)
            self.assertIn("Clip plane 62%", widget.volume_canvas_overlay_text())
            self.assertIn("Detail enhancement 80%", widget.volume_canvas_overlay_text())

            widget._volume_render_mode = "drag"
            widget.render_volume_preview()
            self.assertEqual(fake_canvas.render_state_kwargs[-1]["enhancement"], 0.0)
            self.assertEqual(fake_canvas.render_state_kwargs[-1]["jitter_strength"], 0.0)
            self.assertEqual(fake_canvas.render_state_kwargs[-1]["adaptive_step_strength"], 0.0)
            self.assertEqual(fake_canvas.render_state_kwargs[-1]["gradient_opacity"], 0.0)
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

    def test_tif_batch_import_worker_registers_multiple_stacks_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("batch_import", root / "batch_import")
            tif_a = root / "a.tif"
            tif_b = root / "b.tif"
            tifffile.imwrite(tif_a, np.arange(2 * 5 * 6, dtype=np.uint16).reshape(2, 5, 6), photometric="minisblack")
            tifffile.imwrite(tif_b, np.ones((3, 4, 5), dtype=np.uint8), photometric="minisblack")
            worker = TifBatchImportWorker(
                manager,
                [
                    {"tif_path": str(tif_a), "specimen_id": "specimen-a"},
                    {"tif_path": str(tif_b), "specimen_id": "specimen-b"},
                ],
            )
            finished = []
            worker.finished.connect(finished.append)

            worker.run()

            self.assertEqual(len(finished), 1)
            results = finished[0]["results"]
            self.assertEqual([item["ok"] for item in results], [True, True])
            for specimen_id in ("specimen-a", "specimen-b"):
                specimen = manager.get_specimen(specimen_id)
                self.assertIsNotNone(specimen)
                self.assertEqual((specimen.get("metadata") or {}).get("import_status"), "metadata_only")
                self.assertEqual((specimen.get("working_volume") or {}).get("path"), "")
                self.assertEqual((specimen.get("working_volume") or {}).get("status"), "metadata_only")
                self.assertFalse((specimen.get("labels") or {}).get("working_edit", {}).get("path"))

    def test_tif_batch_import_worker_keeps_successes_when_one_stack_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("batch_partial", root / "batch_partial")
            good_tif = root / "good.tif"
            bad_tif = root / "bad.tif"
            tifffile.imwrite(good_tif, np.ones((2, 4, 4), dtype=np.uint8), photometric="minisblack")
            bad_tif.write_bytes(b"not a tif")
            worker = TifBatchImportWorker(
                manager,
                [
                    {"tif_path": str(bad_tif), "specimen_id": "bad"},
                    {"tif_path": str(good_tif), "specimen_id": "good"},
                ],
            )
            finished = []
            worker.finished.connect(finished.append)

            worker.run()

            self.assertEqual(len(finished), 1)
            results = finished[0]["results"]
            self.assertEqual([item["ok"] for item in results], [False, True])
            self.assertIsNone(manager.get_specimen("bad"))
            self.assertIsNotNone(manager.get_specimen("good"))

    def test_tif_materialize_worker_builds_working_volume_for_metadata_only_specimen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("materialize", root / "materialize")
            tif_path = root / "source.tif"
            source = np.arange(2 * 4 * 5, dtype=np.uint8).reshape(2, 4, 5)
            tifffile.imwrite(tif_path, source, photometric="minisblack")
            batch = TifBatchImportWorker(manager, [{"tif_path": str(tif_path), "specimen_id": "specimen-meta"}])
            batch_finished = []
            batch.finished.connect(batch_finished.append)
            batch.run()
            self.assertEqual(manager.get_specimen("specimen-meta")["metadata"]["import_status"], "metadata_only")

            worker = TifMaterializeWorker(manager, "specimen-meta")
            finished = []
            failed = []
            progress = []
            worker.finished.connect(finished.append)
            worker.failed.connect(failed.append)
            worker.progress.connect(lambda current, total, message: progress.append((current, total, message)))
            worker.run()

            self.assertEqual(failed, [])
            self.assertEqual(len(finished), 1)
            specimen = manager.get_specimen("specimen-meta")
            self.assertEqual((specimen.get("metadata") or {}).get("import_status"), "materialized")
            self.assertTrue((specimen.get("working_volume") or {}).get("path"))
            self.assertFalse((specimen.get("labels") or {}).get("working_edit", {}).get("path"))
            image_abs = manager.to_absolute(specimen["working_volume"]["path"])
            np.testing.assert_array_equal(load_volume_sidecar(image_abs), source)
            self.assertTrue(any("Reading" in item[2] or "Working volume ready" in item[2] for item in progress))

    def test_tif_materialize_worker_does_not_delete_source_inside_specimen_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("materialize_internal", root / "materialize_internal")
            manager.create_specimen_scaffold("specimen-meta")
            tif_path = Path(manager.project_dir) / "specimens" / "specimen-meta" / "source" / "raw" / "source.tif"
            source = np.arange(2 * 4 * 5, dtype=np.uint8).reshape(2, 4, 5)
            tifffile.imwrite(tif_path, source, photometric="minisblack")
            specimen = manager.get_specimen("specimen-meta")
            specimen["source"]["raw_tif"] = str(tif_path)
            specimen["metadata"].update(
                {
                    "import_status": "metadata_only",
                    "source_tif": str(tif_path),
                    "shape_zyx": [2, 4, 5],
                    "dtype": "uint8",
                }
            )
            specimen["working_volume"].update({"path": "", "shape_zyx": [2, 4, 5], "dtype": "uint8", "status": "metadata_only"})
            manager.save_project()

            worker = TifMaterializeWorker(manager, "specimen-meta")
            finished = []
            failed = []
            worker.finished.connect(finished.append)
            worker.failed.connect(failed.append)
            worker.run()

            self.assertEqual(failed, [])
            self.assertEqual(len(finished), 1)
            self.assertTrue(tif_path.exists())
            specimen = manager.get_specimen("specimen-meta")
            self.assertTrue((specimen.get("working_volume") or {}).get("path"))
            np.testing.assert_array_equal(load_volume_sidecar(manager.to_absolute(specimen["working_volume"]["path"])), source)

    def test_tif_workbench_chinese_labels_cover_import_and_backend_controls(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget.change_language("zh")
            self.assertEqual(widget.task_tabs.tabText(2), "标注与训练")
            self.assertEqual(widget.btn_import_tif.text(), "导入 TIF stack")
            self.assertEqual(widget.btn_import_amira.text(), "导入 AMIRA 目录")
            self.assertEqual(widget.btn_export_training.text(), "导出可训练体数据")
            self.assertEqual(widget.btn_prepare_dataset.text(), "准备训练数据")
            self.assertEqual(widget.btn_train_backend.text(), "训练后端")
            self.assertEqual(widget.btn_import_prediction.text(), "运行预测并导入待核验结果")
            self.assertEqual(widget.btn_import_external_prediction_tif.text(), "导入外部标签 TIF 为待核验结果")
            self.assertEqual(widget.auto_save_check.text(), "自动保存标注")
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
            self.assertIn("结构区域标签表", section_titles)
            self.assertIn("模型配置", section_titles)
            self.assertIn("工作台日志", section_titles)
            self.assertIn("1. 定位部位", section_titles)
            self.assertIn("2. 生成部位 mask", section_titles)
            self.assertIn("3. 输出与管理", section_titles)
            self.assertIn("已训练模型", section_titles)
            self.assertEqual(widget.model_library_label.text(), "已训练模型")
            self.assertEqual(widget.model_library_notes_label.text(), "备注")
            self.assertEqual(widget.model_library_notes_edit.placeholderText(), "模型备注")
            self.assertEqual(widget.btn_use_selected_tif_model.text(), "使用选中模型")
            self.assertEqual(widget.btn_save_tif_model_notes.text(), "保存备注")
            self.assertEqual(widget.btn_delete_tif_model_record.text(), "删除模型登记")
            self.assertEqual(widget.model_library_combo.itemText(0), "未登记模型")
            self.assertIn("当前项目还没有登记已训练模型", widget.model_library_summary_label.text())
            self.assertEqual(widget.label_role_combo.itemText(widget.label_role_combo.findData("manual_truth")), "训练真值")
            self.assertIn("训练真值", widget.label_role_help_label.text())
            self.assertIn("区域标签", widget.result_region_label.text())
            self.assertEqual(widget.btn_import_label_schema.text(), "导入 TaxaMask 标签表 JSON")
            self.assertEqual(widget.btn_new_part_user_tag.text(), "新增分组标签")
            self.assertEqual(widget.btn_save_part_user_tag.text(), "保存分组标签")
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_tif_workbench_literal_translation_keys_are_in_chinese_table(self):
        paths = [
            Path("AntSleap/ui/tif_workbench.py"),
            Path("AntSleap/ui/tif_workbench_dialogs.py"),
            Path("AntSleap/ui/tif_workbench_canvas.py"),
            Path("AntSleap/ui/tif_workbench_workers.py"),
        ]
        literal_keys = set()
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Name) or node.func.id != "tt" or not node.args:
                    continue
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    literal_keys.add(first_arg.value)
        missing = sorted(key for key in literal_keys if key not in TIF_TRANSLATIONS.get("zh", {}))
        self.assertEqual(missing, [])

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
            backup_index = widget.label_role_combo.findData("raw_ai_prediction_backup")

            widget.label_role_combo.setCurrentIndex(manual_index)
            self.assertIn("训练真值", widget.label_role_help_label.text())

            widget.label_role_combo.setCurrentIndex(edit_index)
            self.assertIn("当前标注", widget.label_role_help_label.text())

            widget.label_role_combo.setCurrentIndex(backup_index)
            self.assertIn("AI 原始备份只读", widget.label_role_help_label.text())
        finally:
            widget.close_project()
            widget.deleteLater()

    def test_painting_is_blocked_on_read_only_label_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=2)
            try:
                edit_before = widget.edit_volume.copy()
                backup_index = widget.label_role_combo.findData("raw_ai_prediction_backup")
                widget.label_role_combo.setCurrentIndex(backup_index)
                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)

                np.testing.assert_array_equal(widget.edit_volume, edit_before)
                self.assertIn("Raw AI prediction backup is read-only", widget.training_status_label.text())

                manual_index = widget.label_role_combo.findData("manual_truth")
                widget.label_role_combo.setCurrentIndex(manual_index)
                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)

                np.testing.assert_array_equal(widget.edit_volume, edit_before)
                self.assertIn("Cannot paint on training truth directly", widget.training_status_label.text())
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
                self.assertIn("Painted label 2 on slice", widget.operation_status_label.text())
                self.assertTrue(widget.auto_save_timer.isActive())
                widget.auto_save_timer.stop()
                request = widget._snapshot_label_auto_save_request(reason="auto_save")
                self.assertIsNotNone(request)
                result = _tif_write_label_slice_snapshots(
                    request["token"],
                    request["edit_path"],
                    request["slices"],
                    request["slice_revisions"],
                )
                widget._on_label_auto_save_finished(result)

                specimen = widget.project.get_specimen("01-0101-21")
                edit_path = root / "viewer" / specimen["labels"]["working_edit"]["path"] / "array.npy"
                saved = np.load(edit_path)
                self.assertGreater(int(saved.sum()), 0)
                self.assertFalse(widget.working_edit_dirty)
                self.assertIn("Auto-saved current labels.", widget.training_status_label.text())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_background_auto_save_keeps_later_same_slice_edits_dirty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=2)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget.current_material_id = 2
                widget.brush_size_slider.setValue(1)
                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)

                request = widget._snapshot_label_auto_save_request(reason="auto_save")
                self.assertIsNotNone(request)
                snapshot_revisions = dict(request["slice_revisions"])

                widget.edit_volume[0, 0, 0] = 2
                widget._mark_edit_slice_dirty(0)
                result = _tif_write_label_slice_snapshots(
                    request["token"],
                    request["edit_path"],
                    request["slices"],
                    request["slice_revisions"],
                )
                widget._on_label_auto_save_finished(result)

                self.assertTrue(widget.working_edit_dirty)
                self.assertIn(0, widget._dirty_edit_slices)
                self.assertGreater(widget._edit_slice_revisions[0], snapshot_revisions[0])
                specimen = widget.project.get_specimen("01-0101-21")
                saved = np.load(root / "viewer" / specimen["labels"]["working_edit"]["path"] / "array.npy")
                self.assertEqual(int(saved[0, 0, 0]), 0)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_manual_save_queues_behind_running_auto_save_without_waiting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=2)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget.current_material_id = 2
                widget.brush_size_slider.setValue(1)
                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)

                auto_request = widget._snapshot_label_auto_save_request(reason="auto_save")
                self.assertIsNotNone(auto_request)
                widget._label_auto_save_thread = object()
                self.assertTrue(widget.save_working_edit_async())
                self.assertIsNotNone(widget._pending_manual_save_after_auto)
                self.assertFalse(widget._label_manual_save_running())
                self.assertIn("Finishing auto-save", widget.operation_status_label.text())

                widget._label_auto_save_thread = None
                result = _tif_write_label_slice_snapshots(
                    auto_request["token"],
                    auto_request["edit_path"],
                    auto_request["slices"],
                    auto_request["slice_revisions"],
                )
                widget._on_label_auto_save_finished(result)

                self.assertIsNone(widget._pending_manual_save_after_auto)
                if widget._label_manual_save_running():
                    self._wait_for_label_manual_save(widget)
                self.assertFalse(widget.working_edit_dirty)
                specimen = widget.project.get_specimen("01-0101-21")
                saved = np.load(root / "viewer" / specimen["labels"]["working_edit"]["path"] / "array.npy")
                self.assertGreater(int(saved.sum()), 0)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_label_auto_save_worker_writes_dirty_slice_in_qt_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edit_path = root / "edit.ome.zarr"
            write_volume_sidecar(edit_path, np.zeros((2, 4, 4), dtype=np.uint16), role="working_edit", write_ome_zarr=False)
            thread = QThread()
            worker = TifLabelAutoSaveWorker(
                1,
                edit_path,
                {1: np.full((4, 4), 7, dtype=np.uint16)},
                {1: 3},
            )
            worker.moveToThread(thread)
            finished = []
            failed = []
            try:
                thread.started.connect(worker.run)
                worker.finished.connect(lambda result: finished.append(result))
                worker.failed.connect(lambda result: failed.append(result))
                worker.finished.connect(thread.quit)
                worker.failed.connect(thread.quit)
                thread.start()
                deadline = datetime.now().timestamp() + 5.0
                while not finished and not failed and datetime.now().timestamp() < deadline:
                    self.app.processEvents()
                self.assertEqual(failed, [])
                self.assertTrue(finished)

                saved = np.load(edit_path / "array.npy")
                self.assertEqual(int(saved[1].sum()), 7 * 16)
                result = finished[0]
                self.assertEqual(result["saved_slices"], [1])
                self.assertEqual(result["slice_revisions"], {1: 3})
            finally:
                if thread.isRunning():
                    thread.quit()
                    thread.wait(5000)
                worker.deleteLater()
                thread.deleteLater()

    def test_visible_annotation_tools_paint_erase_lasso_pick_and_pan(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=2)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget.brush_size_slider.setValue(1)
                x = widget.canvas.width() / 2
                y = widget.canvas.height() / 2

                widget.set_annotation_tool_mode("brush", show_message=False)
                widget._set_current_material_id(2)
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, x, y))
                self.assertGreater(int(np.count_nonzero(widget.edit_volume[0] == 2)), 0)
                painted = widget.edit_volume.copy()

                widget.set_annotation_tool_mode("eraser", show_message=False)
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, x, y))
                self.assertLess(int(np.count_nonzero(widget.edit_volume[0] == 2)), int(np.count_nonzero(painted[0] == 2)))
                self.assertIn("Erased labels on slice", widget.operation_status_label.text())

                widget.set_annotation_tool_mode("brush", show_message=False)
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, x, y))
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, x, y, modifiers=Qt.ControlModifier))
                self.assertEqual(int(widget.edit_volume[0, 4, 4]), 0)

                widget.set_annotation_tool_mode("lasso", show_message=False)
                self.assertTrue(widget.findChild(QWidget, "tifToolLassoButton").isChecked())
                widget.finish_lasso_fill([[1, 1], [5, 1], [5, 5], [1, 5]])
                self.assertGreater(int(np.count_nonzero(widget.edit_volume[0] == 2)), 0)
                self.assertIn("Filled label 2 on slice", widget.operation_status_label.text())

                widget.edit_volume[0, 4, 4] = 2
                widget.render_current_slice()
                widget._set_current_material_id(0)
                widget.set_annotation_tool_mode("picker", show_message=False)
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, x, y))
                self.assertEqual(widget.current_material_id, 2)
                self.assertIn("Picked label 2", widget.operation_status_label.text())

                before_pan = widget.edit_volume.copy()
                widget.set_annotation_tool_mode("pan", show_message=False)
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, x, y))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, x + 20, y + 10))
                np.testing.assert_array_equal(widget.edit_volume, before_pan)
                self.assertIn("Labels were not changed", widget.operation_status_label.text())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_brush_drag_interpolates_stroke_and_uses_single_undo_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=2)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget.brush_size_slider.setValue(1)
                widget._set_current_material_id(2)
                widget.set_annotation_tool_mode("brush", show_message=False)
                start = self._canvas_xy_for_image_pixel(widget, 1, 4)
                end = self._canvas_xy_for_image_pixel(widget, 6, 4)

                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, start[0], start[1]))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end[0], end[1]))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, end[0], end[1]))

                self.assertEqual(len(widget.undo_stack), 1)
                for x in range(1, 7):
                    self.assertEqual(int(widget.edit_volume[0, 4, x]), 2)
                painted = widget.edit_volume.copy()

                widget.undo()
                self.assertEqual(int(np.count_nonzero(widget.edit_volume[0])), 0)
                widget.redo()
                np.testing.assert_array_equal(widget.edit_volume, painted)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_lasso_fill_fills_closed_outline_and_undoes_as_single_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=2)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget._set_current_material_id(2)
                widget.set_annotation_tool_mode("lasso", show_message=False)
                raw_points = [(1, 1), (6, 1), (6, 6), (1, 6), (1, 1)]
                canvas_points = [self._canvas_xy_for_image_pixel(widget, x, y) for x, y in raw_points]

                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, canvas_points[0][0], canvas_points[0][1]))
                for point in canvas_points[1:]:
                    widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, point[0], point[1]))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, canvas_points[-1][0], canvas_points[-1][1]))

                self.assertEqual(len(widget.undo_stack), 1)
                self.assertEqual(int(widget.edit_volume[0, 3, 3]), 2)
                self.assertEqual(int(widget.edit_volume[0, 0, 0]), 0)
                self.assertTrue(widget.working_edit_dirty)
                self.assertIn(0, widget._dirty_edit_slices)
                self.assertIn("Filled label 2 on slice", widget.operation_status_label.text())

                filled = widget.edit_volume.copy()
                widget.undo()
                self.assertEqual(int(np.count_nonzero(widget.edit_volume[0])), 0)
                widget.redo()
                np.testing.assert_array_equal(widget.edit_volume, filled)

                widget.auto_save_timer.stop()
                self.assertTrue(widget.save_working_edit(show_message=True))
                specimen = widget.project.get_specimen("01-0101-21")
                edit_path = root / "viewer" / specimen["labels"]["working_edit"]["path"] / "array.npy"
                saved = np.load(edit_path)
                self.assertEqual(int(saved[0, 3, 3]), 2)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_rectangle_and_ellipse_fill_preview_write_dirty_and_warn_on_risky_area(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=2)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget._set_current_material_id(2)

                widget.set_annotation_tool_mode("rectangle", show_message=False)
                start = self._canvas_xy_for_image_pixel(widget, 0, 0)
                end = self._canvas_xy_for_image_pixel(widget, 7, 7)
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, start[0], start[1]))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end[0], end[1]))
                self.assertEqual(int(np.count_nonzero(widget.edit_volume[0])), 0)
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, end[0], end[1]))

                self.assertEqual(len(widget.undo_stack), 1)
                self.assertEqual(int(np.count_nonzero(widget.edit_volume[0] == 2)), 64)
                self.assertIn("Filled rectangle label 2", widget.operation_status_label.text())
                self.assertIn("Large fill area", widget.operation_status_label.text())
                self.assertIn("touches the image edge", widget.operation_status_label.text())
                self.assertTrue(widget.working_edit_dirty)

                widget.undo()
                self.assertEqual(int(np.count_nonzero(widget.edit_volume[0])), 0)
                widget.redo()
                self.assertEqual(int(np.count_nonzero(widget.edit_volume[0] == 2)), 64)

                widget.set_annotation_tool_mode("ellipse", show_message=False)
                small = self._canvas_xy_for_image_pixel(widget, 3, 3)
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, small[0], small[1]))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, small[0], small[1]))
                self.assertIn("too small", widget.operation_status_label.text())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_current_material_copy_to_neighbor_and_clear_are_confirmed_single_undo_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=3)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget._set_current_material_id(2)
                widget.edit_volume[1, 2:5, 2:5] = 2
                widget.slice_slider.setValue(1)
                widget.render_current_slice()
                module_path = "AntSleap.ui.tif_workbench.QMessageBox"

                with patch(f"{module_path}.question", return_value=QMessageBox.Yes):
                    self.assertTrue(widget.copy_current_material_to_adjacent_slice(1))

                self.assertEqual(int(widget.slice_slider.value()), 2)
                self.assertEqual(len(widget.undo_stack), 1)
                self.assertEqual(int(np.count_nonzero(widget.edit_volume[2] == 2)), 9)
                self.assertIn("Copied label 2 from slice 2 to slice 3", widget.operation_status_label.text())
                self.assertIn(2, widget._dirty_edit_slices)

                widget.undo()
                self.assertEqual(int(np.count_nonzero(widget.edit_volume[2] == 2)), 0)
                widget.redo()
                self.assertEqual(int(np.count_nonzero(widget.edit_volume[2] == 2)), 9)

                with patch(f"{module_path}.question", return_value=QMessageBox.Yes):
                    self.assertTrue(widget.clear_current_material_on_slice())

                self.assertEqual(int(np.count_nonzero(widget.edit_volume[2] == 2)), 0)
                self.assertEqual(len(widget.undo_stack), 2)
                self.assertIn("Cleared label 2 on slice 3", widget.operation_status_label.text())
                widget.undo()
                self.assertEqual(int(np.count_nonzero(widget.edit_volume[2] == 2)), 9)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_interpolate_fill_uses_current_label_key_slices(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget._set_current_material_id(2)
                widget.edit_volume[1, 2:4, 2:4] = 2
                widget.edit_volume[3, 4:7, 4:7] = 2

                self.assertTrue(widget.interpolate_current_label_between_key_slices())

                self.assertGreater(int(np.count_nonzero(widget.edit_volume[2] == 2)), 0)
                self.assertIn(2, widget._dirty_edit_slices)
                self.assertIn("Interpolate filled label 2", widget.operation_status_label.text())
                self.assertGreaterEqual(len(widget.undo_stack), 1)
                widget.undo()
                self.assertEqual(int(np.count_nonzero(widget.edit_volume[2] == 2)), 0)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_part_volume_annotation_tools_save_editable_ai_result_not_part_mask(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=4)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[1, 3], [2, 6], [1, 5]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")

                self.assertEqual(widget.current_volume_scope, "part")
                self.assertEqual(widget.current_reslice_id, "")
                self.assertIsNone(widget.edit_volume)
                self.assertIsNone(widget.label_volume)
                self.assertEqual(widget.label_role_combo.currentData(), "editable_ai_result")
                part = widget.project.get_part("01-0101-21", "head")
                mask_path = root / "viewer" / part["mask"]["path"]
                original_mask_volume = load_volume_sidecar(mask_path, mmap_mode="r")
                original_mask = np.asarray(original_mask_volume).copy()
                del original_mask_volume
                self.assertFalse(widget.annotation_section.isHidden())
                self.assertTrue(widget.btn_tool_brush.isEnabled())
                self.assertTrue(widget.btn_tool_eraser.isEnabled())
                self.assertTrue(widget.btn_tool_lasso.isEnabled())
                self.assertTrue(widget.btn_tool_rectangle.isEnabled())
                self.assertTrue(widget.btn_tool_ellipse.isEnabled())
                self.assertTrue(widget.btn_tool_picker.isEnabled())
                self.assertTrue(widget.btn_save_edit.isEnabled())
                self.assertTrue(widget.btn_promote.isEnabled())
                self.assertTrue(widget.label_role_combo.isEnabled())
                self.assertEqual(widget.annotation_tool_mode, "pan")
                self.assertTrue(widget.btn_tool_pan.isChecked())

                widget.brush_size_slider.setValue(42)
                widget.canvas.mouseMoveEvent(
                    FakeMouseEvent(
                        Qt.NoButton,
                        Qt.NoButton,
                        widget.canvas.width() / 2,
                        widget.canvas.height() / 2,
                    )
                )
                self.assertEqual(widget.canvas._last_annotation_preview, {})

                widget._set_current_material_id(2)
                widget.slice_slider.setValue(0)
                widget.set_annotation_tool_mode("rectangle", show_message=False)
                start = self._canvas_xy_for_image_pixel(widget, 1, 1)
                end = self._canvas_xy_for_image_pixel(widget, 2, 2)
                widget.canvas.mousePressEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, start[0], start[1]))
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.LeftButton, Qt.LeftButton, end[0], end[1]))
                widget.canvas.mouseReleaseEvent(FakeMouseEvent(Qt.LeftButton, Qt.NoButton, end[0], end[1]))

                self.assertIsNotNone(widget.edit_volume)
                self.assertEqual(len(widget.undo_stack), 1)
                self.assertGreater(int(np.count_nonzero(widget.edit_volume[0] == 2)), 0)
                self.assertTrue(widget.working_edit_dirty)
                self.assertTrue(widget.btn_undo.isEnabled())

                widget.undo()
                self.assertEqual(int(np.count_nonzero(widget.edit_volume[0] == 2)), 0)
                widget.redo()
                self.assertGreater(int(np.count_nonzero(widget.edit_volume[0] == 2)), 0)
                self.assertTrue(widget.save_working_edit(show_message=True))
                self.assertFalse(widget.working_edit_dirty)
                self.assertIn("Editable AI result saved.", widget.operation_status_label.text())

                part = widget.project.get_part("01-0101-21", "head")
                edit_path = root / "viewer" / part["labels"]["editable_ai_result"]["path"]
                saved_edit_volume = load_volume_sidecar(edit_path, mmap_mode="r")
                saved_edit = np.asarray(saved_edit_volume).copy()
                del saved_edit_volume
                self.assertGreater(int(np.count_nonzero(saved_edit[0] == 2)), 0)
                self.assertEqual(part["labels"]["editable_ai_result"]["status"], "pending_review")
                self.assertEqual((part.get("training") or {}).get("system_status"), "predicted_pending_review")
                saved_mask_volume = load_volume_sidecar(mask_path, mmap_mode="r")
                saved_mask = np.asarray(saved_mask_volume).copy()
                del saved_mask_volume
                np.testing.assert_array_equal(saved_mask, original_mask)
                self.assertIn("editable_ai_result", part.get("labels", {}))
                self.assertNotIn("manual_truth", {role for role, record in (part.get("labels") or {}).items() if (record or {}).get("path")})

                specimen = widget.project.get_specimen("01-0101-21")
                parent_edit = np.load(root / "viewer" / specimen["labels"]["working_edit"]["path"] / "array.npy")
                self.assertEqual(int(np.count_nonzero(parent_edit)), 0)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_saved_part_reslice_edits_reslice_labels_and_hides_part_mask_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                frame = compute_local_frame(
                    [1.5, 3.0, 3.0],
                    [0.0, 3.0, 3.0],
                    [3.0, 3.0, 3.0],
                    roll_reference={
                        "point_a": {"role": "left_eye", "zyx": [1.5, 2.0, 2.0]},
                        "point_b": {"role": "right_eye", "zyx": [1.5, 4.0, 2.0]},
                    },
                )
                export_part_reslice(
                    widget.project,
                    "01-0101-21",
                    "head",
                    {"reslice_id": "head_axis_saved", "template_id": "head", "local_frame": frame},
                )
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part_reslice", "head", "head_axis_saved")

                self.assertEqual(widget.current_reslice_id, "head_axis_saved")
                self.assertIsNone(widget.edit_volume)
                self.assertEqual(widget.label_role_combo.currentData(), "editable_ai_result")
                self.assertIsNone(widget.part_mask_volume)
                self.assertIsNone(widget._active_part_mask_volume())
                self.assertFalse(widget._active_part_mask_likely_available())
                self.assertEqual(widget.volume_mask_combo.currentData(), "image_only")
                self.assertTrue(widget.btn_bind_label_schema_to_part.isEnabled())
                self.assertTrue(widget.material_editor_buttons.isHidden())
                self.assertIn("bound schema", widget.material_help_label.text())
                self.assertTrue(widget.btn_tool_brush.isEnabled())
                self.assertTrue(widget.btn_tool_rectangle.isEnabled())
                self.assertTrue(widget.btn_save_edit.isEnabled())
                self.assertTrue(widget.btn_tool_pan.isEnabled())
                self.assertTrue(widget.btn_tool_picker.isEnabled())
                self.assertFalse(widget.btn_draw_part_contour.isEnabled())
                self.assertFalse(widget.btn_preview_part_mask.isEnabled())
                self.assertFalse(widget.btn_local_axis_reslice.isEnabled())

                widget._set_current_material_id(2)
                start = self._canvas_xy_for_image_pixel(widget, 1, 1)
                end = self._canvas_xy_for_image_pixel(widget, 3, 3)
                self.assertTrue(widget.finish_shape_fill_drag("rectangle", start[0], start[1], end[0], end[1]))
                self.assertIsNotNone(widget.edit_volume)
                self.assertTrue(widget.working_edit_dirty)
                self.assertTrue(widget.save_working_edit(show_message=True))
                self.assertIn("Editable AI result saved.", widget.operation_status_label.text())

                part = widget.project.get_part("01-0101-21", "head")
                self.assertFalse((part["labels"]["editable_ai_result"] or {}).get("path"))
                reslice = widget.project.get_part_reslice("01-0101-21", "head", "head_axis_saved")
                edit_record = reslice["labels"]["editable_ai_result"]
                edit_path = root / "viewer" / edit_record["path"]
                saved_edit_volume = load_volume_sidecar(edit_path, mmap_mode="r")
                saved_edit = np.asarray(saved_edit_volume).copy()
                del saved_edit_volume
                self.assertGreater(int(np.count_nonzero(saved_edit == 2)), 0)
                self.assertEqual(edit_record.get("orientation"), "local_axis_reslice")
                self.assertEqual(edit_record.get("coordinate_space"), "local_axis_reslice_voxel_zyx")
                self.assertEqual(edit_record.get("reslice_id"), "head_axis_saved")
                self.assertEqual((part.get("training") or {}).get("active_reslice_id"), "head_axis_saved")
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_research_smoke_part_annotation_local_axis_save_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=5)
            project_json = widget.project.current_project_path
            try:
                crop_volume_to_part(widget.project, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
                widget.refresh_project()
                widget._select_volume_tree_item("01-0101-21", "part", "head")

                self.assertEqual(widget.current_volume_scope, "part")
                self.assertEqual(widget.current_part_id, "head")
                self.assertEqual(widget.label_role_combo.currentData(), "editable_ai_result")

                widget._set_current_material_id(2)
                start = self._canvas_xy_for_image_pixel(widget, 1, 1)
                end = self._canvas_xy_for_image_pixel(widget, 3, 3)
                self.assertTrue(widget.finish_shape_fill_drag("rectangle", start[0], start[1], end[0], end[1]))
                self.assertTrue(widget.save_working_edit(show_message=True))
                editable = widget.project.part_label_record("01-0101-21", "head", "editable_ai_result")
                self.assertIn("editable_ai_result.ome.zarr", editable["path"])
                saved_edit = load_volume_sidecar(root / "viewer" / editable["path"], mmap_mode="r")
                try:
                    self.assertGreater(int(np.count_nonzero(saved_edit)), 0)
                finally:
                    mmap_handle = getattr(saved_edit, "_mmap", None)
                    if mmap_handle is not None:
                        mmap_handle.close()

                self.assertIsNotNone(widget.copy_source_z_axis_to_local_axis_draft())
                widget.local_axis_draft["roll_reference"] = {
                    "pair_id": "roll_reference_point_pair",
                    "point_a": {"role": "roll_reference_a", "zyx": [1.0, 1.0, 1.0]},
                    "point_b": {"role": "roll_reference_b", "zyx": [1.0, 4.0, 1.0]},
                    "point_c": {"role": "reference_plane_c", "zyx": [3.0, 1.0, 4.0]},
                }
                self.assertTrue(widget.align_local_axis_to_reference_plane())

                with patch_message_boxes():
                    result = widget.export_current_local_axis_reslice()
                self.assertEqual(result["status"], "running")
                reslice_id = result["reslice_id"]
                self._wait_for_local_axis_export(widget)

                reslice = widget.project.get_part_reslice("01-0101-21", "head", reslice_id)
                self.assertIsNotNone(reslice)
                self.assertEqual(reslice["training_sample"]["roll_reference_point_pair"]["point_c"]["role"], "reference_plane_c")
                self.assertTrue(Path(widget.project.to_absolute(reslice["image_path"])).exists())
                self.assertTrue(Path(widget.project.to_absolute(reslice["metadata_path"])).exists())
                widget.project.save_project()
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

            reloaded = TifProjectManager()
            reloaded.enable_legacy_json_writes_for_compatibility(True)
            reloaded.load_project(project_json)
            reloaded_widget = TifWorkbenchWidget(reloaded, "en")
            try:
                reloaded_widget._select_volume_tree_item("01-0101-21", "part", "head")
                self.assertEqual(reloaded_widget.current_part_id, "head")
                reloaded_part = reloaded_widget.project.get_part("01-0101-21", "head")
                self.assertIn("editable_ai_result.ome.zarr", reloaded_part["labels"]["editable_ai_result"]["path"])
                reloaded_reslices = reloaded_widget.project.list_part_reslices("01-0101-21", "head")
                self.assertEqual(len(reloaded_reslices), 1)
                reloaded_widget._select_volume_tree_item("01-0101-21", "part_reslice", "head", reloaded_reslices[0]["reslice_id"])
                self.assertEqual(reloaded_widget.current_reslice_id, reloaded_reslices[0]["reslice_id"])
                self.assertIsNotNone(reloaded_widget.image_volume)
                self.assertIn("Saved reslice", reloaded_widget.local_axis_summary_label.text())
            finally:
                reloaded_widget.close_project(prompt_unsaved=False)
                reloaded_widget.deleteLater()

    def test_shape_and_slice_helpers_respect_read_only_layer_and_axis(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=3)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget._set_current_material_id(2)
                before = widget.edit_volume.copy()
                x_index = widget.slice_axis_combo.findData("x")
                widget.slice_axis_combo.setCurrentIndex(x_index)
                start = self._canvas_xy_for_image_pixel(widget, 1, 1)
                end = self._canvas_xy_for_image_pixel(widget, 6, 6)

                self.assertFalse(widget.finish_shape_fill_drag("rectangle", start[0], start[1], end[0], end[1]))
                np.testing.assert_array_equal(widget.edit_volume, before)
                self.assertIn("Painting is available on Z slices only", widget.operation_status_label.text())

                widget.slice_axis_combo.setCurrentIndex(widget.slice_axis_combo.findData("z"))
                manual_index = widget.label_role_combo.findData("manual_truth")
                widget.label_role_combo.setCurrentIndex(manual_index)
                self.assertFalse(widget.copy_current_material_to_adjacent_slice(1))
                self.assertFalse(widget.clear_current_material_on_slice())
                np.testing.assert_array_equal(widget.edit_volume, before)
                self.assertIn("Cannot paint on training truth directly", widget.operation_status_label.text())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_annotation_cursor_preview_tracks_tool_radius_and_read_only_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=2)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget.brush_size_slider.setValue(5)
                x = widget.canvas.width() / 2
                y = widget.canvas.height() / 2

                widget.set_annotation_tool_mode("brush", show_message=False)
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.NoButton, Qt.NoButton, x, y))
                self.assertEqual(widget.canvas._last_annotation_preview["mode"], "brush")
                self.assertEqual(widget.canvas._last_annotation_preview["radius"], 5.0)
                self.assertFalse(widget.canvas._last_annotation_preview["disabled"])

                widget.set_annotation_tool_mode("eraser", show_message=False)
                widget.brush_size_slider.setValue(9)
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.NoButton, Qt.NoButton, x, y))
                self.assertEqual(widget.canvas._last_annotation_preview["mode"], "eraser")
                self.assertEqual(widget.canvas._last_annotation_preview["radius"], 9.0)

                widget.set_annotation_tool_mode("pan", show_message=False)
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.NoButton, Qt.NoButton, x, y))
                self.assertEqual(widget.canvas._last_annotation_preview, {})

                manual_index = widget.label_role_combo.findData("manual_truth")
                widget.label_role_combo.setCurrentIndex(manual_index)
                widget.set_annotation_tool_mode("brush", show_message=False)
                widget.canvas.mouseMoveEvent(FakeMouseEvent(Qt.NoButton, Qt.NoButton, x, y))
                self.assertTrue(widget.canvas._last_annotation_preview["disabled"])
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_save_status_and_undo_redo_controls_follow_dirty_slices(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            widget = self._make_volume_widget(root, z_count=2)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget.brush_size_slider.setValue(1)
                widget._set_current_material_id(2)

                self.assertFalse(widget.btn_undo.isEnabled())
                self.assertFalse(widget.btn_redo.isEnabled())
                self.assertIn("Saved", widget.save_status_label.text())

                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)
                self.assertTrue(widget.btn_undo.isEnabled())
                self.assertFalse(widget.btn_redo.isEnabled())
                self.assertIn("Auto-save pending", widget.save_status_label.text())
                self.assertIn("1 slice", widget.save_status_label.text())
                widget.auto_save_timer.stop()
                widget._update_save_status()
                self.assertIn("Unsaved changes", widget.save_status_label.text())

                painted = widget.edit_volume.copy()
                widget.undo()
                self.assertTrue(widget.btn_redo.isEnabled())
                self.assertIn("Undo restored slice", widget.operation_status_label.text())
                self.assertFalse(np.array_equal(widget.edit_volume, painted))

                widget.redo()
                self.assertTrue(widget.btn_undo.isEnabled())
                self.assertIn("Redo restored slice", widget.operation_status_label.text())
                np.testing.assert_array_equal(widget.edit_volume, painted)

                self.assertTrue(widget.save_working_edit(show_message=True))
                self.assertFalse(widget.working_edit_dirty)
                self.assertIn("Saved", widget.save_status_label.text())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_annotation_shortcuts_adjust_tools_radius_save_and_redo(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=2)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget.brush_size_slider.setValue(8)
                widget._set_current_material_id(2)

                widget.shortcut_tool_eraser.activated.emit()
                self.assertEqual(widget.annotation_tool_mode, "eraser")
                widget.shortcut_tool_lasso.activated.emit()
                self.assertEqual(widget.annotation_tool_mode, "lasso")
                widget.shortcut_tool_rectangle.activated.emit()
                self.assertEqual(widget.annotation_tool_mode, "rectangle")
                widget.shortcut_tool_ellipse.activated.emit()
                self.assertEqual(widget.annotation_tool_mode, "ellipse")
                widget.shortcut_tool_picker.activated.emit()
                self.assertEqual(widget.annotation_tool_mode, "picker")
                widget.shortcut_tool_brush.activated.emit()
                self.assertEqual(widget.annotation_tool_mode, "brush")

                widget.shortcut_brush_smaller.activated.emit()
                self.assertEqual(widget.brush_size_slider.value(), 7)
                widget.shortcut_brush_larger.activated.emit()
                self.assertEqual(widget.brush_size_slider.value(), 8)

                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)
                widget.auto_save_timer.stop()
                widget.shortcut_undo.activated.emit()
                self.assertTrue(widget.btn_redo.isEnabled())
                widget.shortcut_redo_alt.activated.emit()
                self.assertIn("Redo restored slice", widget.operation_status_label.text())

                widget.shortcut_save_edit.activated.emit()
                self._wait_for_label_manual_save(widget)
                self.assertFalse(widget.working_edit_dirty)
                self.assertIn("Current labels saved.", widget.operation_status_label.text())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_advanced_annotation_tools_are_spec_only_until_designed(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            self.assertIn("bucket_fill", widget.advanced_annotation_tool_specs)
            self.assertNotIn("lasso_polygon", widget.advanced_annotation_tool_specs)
            self.assertNotIn("rectangle", widget.advanced_annotation_tool_specs)
            self.assertNotIn("ellipse", widget.advanced_annotation_tool_specs)
            for spec in widget.advanced_annotation_tool_specs.values():
                self.assertTrue(spec["requires_design"])
                self.assertTrue(spec["requires_undo_plan"])
                self.assertTrue(spec["requires_risk_notice"])
            self.assertIsNone(widget.findChild(QWidget, "tifToolBucketFillButton"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifInterpolateCurrentLabelButton"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifToolLassoButton"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifToolRectangleButton"))
            self.assertIsNotNone(widget.findChild(QWidget, "tifToolEllipseButton"))
        finally:
            widget.close_project(prompt_unsaved=False)
            widget.deleteLater()

    def test_read_only_slice_axis_reports_block_reason_without_editing(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=2)
            try:
                edit_index = widget.label_role_combo.findData("working_edit")
                widget.label_role_combo.setCurrentIndex(edit_index)
                before = widget.edit_volume.copy()
                x_index = widget.slice_axis_combo.findData("x")
                widget.slice_axis_combo.setCurrentIndex(x_index)
                widget.paint_at_widget_position(widget.canvas.width() / 2, widget.canvas.height() / 2)

                np.testing.assert_array_equal(widget.edit_volume, before)
                self.assertIn("Painting is available on Z slices only", widget.operation_status_label.text())
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

    def test_nnunet_preset_fills_editable_tif_backend_fields(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "zh")
        try:
            widget.backend_python_edit.setText("C:/TaxaMask/python.exe")
            with patch("AntSleap.ui.tif_workbench.normalize_tif_backend_runtime_config") as normalize_mock:
                normalize_mock.side_effect = lambda config: {**config, "python_executable": "C:/Users/admin/anaconda3/envs/3d-brain/python.exe"}
                widget.apply_nnunet_v2_backend_preset()

            self.assertEqual(widget.btn_use_nnunet_backend_preset.text(), "使用 nnU-Net v2 预设")
            self.assertEqual(widget.backend_id_edit.text(), "taxamask_tif_nnunet_v2_backend")
            self.assertEqual(widget.backend_python_edit.text(), "C:/Users/admin/anaconda3/envs/3d-brain/python.exe")
            self.assertIn("AntSleap.tools.tif_nnunet_v2_backend", widget.backend_train_edit.text())
            self.assertIn("{contract_json}", widget.backend_predict_edit.text())

            widget.backend_train_edit.setText("{python} custom_3d_backend.py train --contract {contract_json}")
            widget.backend_predict_edit.setText("{python} custom_3d_backend.py predict --contract {contract_json}")
            config = widget._backend_config_from_ui()
            self.assertIn("custom_3d_backend.py train", config["train_command"])
            self.assertIn("custom_3d_backend.py predict", config["predict_command"])
        finally:
            widget.close_project(prompt_unsaved=False)
            widget.deleteLater()

    def test_backend_run_controls_are_present_and_idle_by_default(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            self.assertEqual(widget.btn_stop_backend.objectName(), "tifStopBackendButton")
            self.assertEqual(widget.btn_open_backend_run.objectName(), "tifOpenBackendRunButton")
            self.assertEqual(widget.btn_open_backend_result.objectName(), "tifOpenBackendResultButton")
            self.assertEqual(widget.btn_show_training_result_summary.objectName(), "tifShowTrainingResultSummaryButton")
            self.assertEqual(widget.btn_open_training_model_output.objectName(), "tifOpenTrainingModelOutputButton")
            self.assertEqual(widget.btn_open_training_model_manifest.objectName(), "tifOpenTrainingModelManifestButton")
            self.assertEqual(widget.btn_batch_predict_entry.objectName(), "tifBatchPredictEntryButton")
            self.assertEqual(widget.backend_progress_bar.objectName(), "tifBackendProgressBar")
            self.assertEqual(widget.backend_log_tail.objectName(), "tifBackendLogTail")
            self.assertEqual(widget.backend_run_title_label.text(), "Backend run")
            self.assertEqual(widget.backend_progress_bar.parentWidget().objectName(), "tifTrainingSection")
            self.assertEqual(widget.training_result_summary_label.sizePolicy().horizontalPolicy(), QSizePolicy.Ignored)
            self.assertEqual(widget.backend_run_status_label.sizePolicy().horizontalPolicy(), QSizePolicy.Ignored)
            self.assertEqual(widget.backend_log_tail.sizePolicy().horizontalPolicy(), QSizePolicy.Ignored)
            self.assertFalse(widget.btn_stop_backend.isEnabled())
            self.assertFalse(widget.btn_open_backend_run.isEnabled())
            self.assertFalse(widget.btn_open_backend_result.isEnabled())
            self.assertFalse(widget.btn_show_training_result_summary.isEnabled())
            self.assertFalse(widget.btn_open_training_model_output.isEnabled())
            self.assertFalse(widget.btn_open_training_model_manifest.isEnabled())
            self.assertFalse(widget.btn_batch_predict_entry.isEnabled())
            self.assertIn("Idle", widget.backend_run_status_label.text())
            self.assertIn("No training result", widget.training_result_summary_label.text())
        finally:
            widget.close_project(prompt_unsaved=False)
            widget.deleteLater()

    def test_backend_unknown_total_progress_stays_percent_bar(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._start_backend_status("train", part_refs=[{"specimen_id": "s1", "part_id": "p1"}])
            widget._on_tif_backend_progress(40, 100, "Wrote backend contract: C:/very/long/run/contract.json")
            widget._on_tif_backend_progress(0, 0, "Running train command... 120s")

            self.assertEqual(widget.backend_progress_bar.minimum(), 0)
            self.assertEqual(widget.backend_progress_bar.maximum(), 100)
            self.assertEqual(widget.backend_progress_bar.value(), 40)
            self.assertEqual(widget.backend_progress_bar.format(), "%p%")
            self.assertIn("Running train command", widget.backend_run_status_label.text())
        finally:
            widget._tif_backend_thread = None
            widget._tif_backend_worker = None
            widget.close_project(prompt_unsaved=False)
            widget.deleteLater()

    def test_training_result_side_panel_compacts_long_paths_without_losing_tooltip(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            model_output = "C:/saveproject/LBJ-workspace/Formica-Flow-Latest/TaxaMask_outputs/tif_projects/project/runs/train/train_20260707_taxamask_tif_nnunet_v2_backend/outputs"
            model_manifest = model_output + "/model_manifest.json"
            summary = {
                "status": "success",
                "backend_id": "mock_backend",
                "run_id": "train_20260707_taxamask_tif_nnunet_v2_backend",
                "run_dir": "C:/saveproject/LBJ-workspace/Formica-Flow-Latest/TaxaMask_outputs/tif_projects/project/runs/train/train_20260707_taxamask_tif_nnunet_v2_backend",
                "model_output": model_output,
                "model_manifest": model_manifest,
                "metrics": [("summary.dice", "0.8")],
                "curves": [],
                "previews": [],
                "warnings": [],
                "errors": [],
            }
            widget._set_training_result_summary(summary)

            panel_text = widget.training_result_summary_label.text()
            tooltip = widget.training_result_summary_label.toolTip()
            self.assertIn("Training result is ready", panel_text)
            self.assertIn(".../outputs/model_manifest.json", panel_text)
            self.assertNotIn("C:/saveproject/LBJ-workspace", panel_text)
            self.assertIn(model_output, tooltip)
            self.assertIn(model_manifest, tooltip)
        finally:
            widget.close_project(prompt_unsaved=False)
            widget.deleteLater()

    def test_training_result_summary_resolves_metrics_and_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "runs" / "train" / "run_1"
            outputs = run_dir / "outputs"
            outputs.mkdir(parents=True)
            manifest = outputs / "model_manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "ant3d_tif_model_manifest_v1",
                        "model_id": "taxamask_tif_nnunet_v2_backend/train_1",
                        "backend_id": "mock_backend",
                        "model_family": "nnunet_v2_tif_region",
                        "created_at": "2026-07-07T12:00:00+08:00",
                        "trained_specimens": ["s1", "s2"],
                        "trained_parts": [{"specimen_id": "s1", "part_id": "head"}],
                        "input_scope": "part_reslice",
                        "label_schema_ids": ["head_regions"],
                        "nnunet": {"model_output_dir": str(outputs), "checkpoint_path": str(outputs / "checkpoint_final.pth")},
                        "usable_for_research_prediction": True,
                    }
                ),
                encoding="utf-8",
            )
            curve = outputs / "loss_curve.png"
            curve.write_bytes(b"not-a-real-png")
            preview = outputs / "mask_preview_01.png"
            preview.write_bytes(b"not-a-real-png")
            result_json = run_dir / "result.json"
            result = {
                "status": "success",
                "action": "train",
                "backend_id": "mock_backend",
                "run_id": "run_1",
                "artifacts": [
                    {"type": "model_manifest", "path": "outputs/model_manifest.json", "format": "json"},
                    {"type": "model_output_dir", "path": "outputs", "format": "directory"},
                    {"type": "training_curve", "path": "outputs/loss_curve.png", "format": "png"},
                    {"type": "mask_preview", "path": "outputs/mask_preview_01.png", "format": "png"},
                ],
                "metrics": {"summary": {"dice": 0.87654}, "by_material": {"MB": {"dice": 0.75}}},
                "warnings": ["small validation set"],
                "errors": [],
                "provenance": {"model_manifest": "outputs/model_manifest.json"},
            }
            summary = summarize_tif_training_result(result, result_json=str(result_json), run_dir=str(run_dir))
            self.assertEqual(summary["status"], "success")
            self.assertEqual(summary["model_manifest"], str(manifest.resolve()))
            self.assertEqual(summary["model_output"], str(outputs.resolve()))
            self.assertEqual(len(summary["curves"]), 1)
            self.assertEqual(len(summary["previews"]), 1)
            self.assertIn(("summary.dice", "0.8765"), summary["metrics"])
            self.assertIn(("by_material.MB.dice", "0.75"), summary["metrics"])

    def test_training_result_dialog_renders_tables_and_preview_percentage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outputs = root / "outputs"
            outputs.mkdir()
            curve = outputs / "curve.png"
            preview_paths = [outputs / f"preview_{idx}.png" for idx in range(5)]
            pix = QPixmap(16, 16)
            pix.fill(QColor("#ff0000"))
            self.assertTrue(pix.save(str(curve)))
            for path in preview_paths:
                self.assertTrue(pix.save(str(path)))
            summary = {
                "status": "success",
                "backend_id": "mock_backend",
                "run_id": "run_1",
                "run_dir": str(root),
                "model_output": str(outputs),
                "model_manifest": str(outputs / "model_manifest.json"),
                "metrics": [("summary.dice", "0.91")],
                "artifacts": [
                    {"type": "training_curve", "format": "png", "absolute_path": str(curve)},
                    *[
                        {"type": "mask_preview", "format": "png", "absolute_path": str(path)}
                        for path in preview_paths
                    ],
                ],
                "curves": [{"type": "training_curve", "format": "png", "absolute_path": str(curve)}],
                "previews": [
                    {"type": "mask_preview", "format": "png", "absolute_path": str(path)}
                    for path in preview_paths
                ],
                "warnings": [],
                "errors": [],
            }
            dialog = TifTrainingResultDialog(summary, "en")
            try:
                self.assertEqual(dialog.metrics_table.rowCount(), 1)
                self.assertEqual(dialog.artifact_table.rowCount(), 6)
                self.assertEqual(dialog.preview_percent_slider.value(), 20)
                self.assertIn("20% (1)", dialog.preview_percent_label.text())
                dialog.preview_percent_slider.setValue(100)
                self.assertIn("100% (5)", dialog.preview_percent_label.text())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_train_finished_updates_training_result_panel_and_prediction_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "runs" / "train" / "train_1"
            outputs = run_dir / "outputs"
            outputs.mkdir(parents=True)
            manifest = outputs / "model_manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "ant3d_tif_model_manifest_v1",
                        "model_id": "taxamask_tif_nnunet_v2_backend/train_1",
                        "backend_id": "mock_backend",
                        "model_family": "nnunet_v2_tif_region",
                        "created_at": "2026-07-07T12:00:00+08:00",
                        "trained_specimens": ["s1", "s2"],
                        "trained_parts": [{"specimen_id": "s1", "part_id": "head"}],
                        "input_scope": "part_reslice",
                        "label_schema_ids": ["head_regions"],
                        "nnunet": {"model_output_dir": str(outputs), "checkpoint_path": str(outputs / "checkpoint_final.pth")},
                        "usable_for_research_prediction": True,
                    }
                ),
                encoding="utf-8",
            )
            result_json = run_dir / "result.json"
            result_json.write_text("{}", encoding="utf-8")
            curve = outputs / "training_curve.png"
            curve.write_bytes(b"not-a-real-png")
            backend_result = {
                "_result_json": str(result_json),
                "status": "success",
                "action": "train",
                "backend_id": "mock_backend",
                "run_id": "train_1",
                "artifacts": [
                    {"type": "model_manifest", "path": "outputs/model_manifest.json", "format": "json"},
                    {"type": "training_curve", "path": "outputs/training_curve.png", "format": "png"},
                ],
                "metrics": {"summary": {"dice": 0.8}},
                "provenance": {"model_manifest": "outputs/model_manifest.json", "usable_for_research_prediction": True},
                "warnings": [],
                "errors": [],
            }
            manager = TifProjectManager()
            manager.create_project("training_finish", root / "project")
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget._tif_backend_thread = object()
                payload = {
                    "run_id": "train_1",
                    "run_dir": str(run_dir),
                    "contract": {"action": "train", "result_json": str(result_json)},
                    "result": backend_result,
                }
                with patch.object(widget, "refresh_project"), patch.object(widget, "show_latest_training_result_summary", return_value=True) as show_summary:
                    widget._on_tif_backend_finished(payload)
                show_summary.assert_called_once_with(show_message=False)
                widget._tif_backend_thread = None
                widget._refresh_training_result_controls()
                self.assertIn("Training result is ready", widget.training_result_summary_label.text())
                self.assertEqual(widget.backend_manifest_edit.text(), str(manifest.resolve()))
                self.assertTrue(widget.btn_show_training_result_summary.isEnabled())
                self.assertTrue(widget.btn_open_training_model_output.isEnabled())
                self.assertTrue(widget.btn_open_training_model_manifest.isEnabled())
                self.assertTrue(widget.btn_batch_predict_entry.isEnabled())
                self.assertGreater(widget.model_library_combo.count(), 1)
                self.assertEqual(widget.backend_manifest_edit.text(), str(manifest.resolve()))
                self.assertIsNotNone(manager.get_tif_segmentation_model("taxamask_tif_nnunet_v2_backend/train_1"))
                with patch_message_boxes():
                    self.assertTrue(widget.enter_batch_prediction_from_training_result())
                self.assertIn("Model manifest filled", widget.training_status_label.text())
                widget._set_training_result_summary(None)
                self.assertEqual(widget.backend_manifest_edit.text(), "")
                widget.backend_manifest_edit.setText("C:/models/manual_manifest.json")
                widget.backend_config["model_manifest"] = "C:/models/manual_manifest.json"
                widget._set_training_result_summary(None)
                self.assertEqual(widget.backend_manifest_edit.text(), "C:/models/manual_manifest.json")
            finally:
                widget._tif_backend_thread = None
                widget._tif_backend_worker = None
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_tif_model_library_selects_notes_and_deletes_registration_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            manager = TifProjectManager()
            manager.create_project("model_library", project_root)
            outputs = project_root / "runs" / "train" / "outputs"
            outputs.mkdir(parents=True)
            manifest = outputs / "model_manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "ant3d_tif_model_manifest_v1",
                        "model_id": "taxamask_tif_nnunet_v2_backend/train_model_library",
                        "backend_id": "taxamask_tif_nnunet_v2_backend",
                        "model_family": "nnunet_v2_tif_region",
                        "created_at": "2026-07-07T12:00:00+08:00",
                        "trained_specimens": ["s1", "s2"],
                        "trained_parts": [{"specimen_id": "s1", "part_id": "head"}, {"specimen_id": "s2", "part_id": "head"}],
                        "input_scope": "part_reslice",
                        "label_schema_ids": ["head_regions"],
                        "nnunet": {"model_output_dir": str(outputs), "checkpoint_path": str(outputs / "checkpoint_final.pth")},
                        "usable_for_research_prediction": True,
                    }
                ),
                encoding="utf-8",
            )
            manager.register_tif_segmentation_model_from_manifest(manifest, {"training_samples": 2}, save=True)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget._populate_tif_model_library_combo("taxamask_tif_nnunet_v2_backend/train_model_library")
                self.assertEqual(widget.model_library_combo.currentData(), "taxamask_tif_nnunet_v2_backend/train_model_library")

                self.assertTrue(widget.use_selected_tif_model())
                self.assertEqual(widget.backend_manifest_edit.text(), str(manifest))

                widget.model_library_notes_edit.setPlainText("Use for validated head batch")
                self.assertTrue(widget.save_selected_tif_model_notes())
                self.assertEqual(
                    manager.get_tif_segmentation_model("taxamask_tif_nnunet_v2_backend/train_model_library")["notes"],
                    "Use for validated head batch",
                )

                with patch("AntSleap.ui.tif_workbench.QMessageBox.question", return_value=QMessageBox.Yes), patch_message_boxes():
                    self.assertTrue(widget.delete_selected_tif_model_record())
                self.assertTrue(manifest.exists())
                self.assertEqual(manager.list_tif_segmentation_models(), [])
                self.assertEqual(widget.backend_manifest_edit.text(), "")
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_predict_target_table_lists_predict_ready_part_without_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            manager.upsert_part_user_tag("round_1", "Round 1", order_index=0, save=False)
            manager.set_part_user_tags("01-0101-11", "brain", ["round_1"], save=True)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.refresh_predict_targets()

                self.assertGreaterEqual(widget.predict_targets_table.rowCount(), 1)
                self.assertIn("Prediction targets:", widget.predict_targets_summary_label.text())
                status_item = widget.predict_targets_table.item(0, 6)
                label_item = widget.predict_targets_table.item(0, 5)
                tag_item = widget.predict_targets_table.item(0, 4)
                select_item = widget.predict_targets_table.item(0, 0)

                self.assertEqual(status_item.text(), "Ready")
                self.assertTrue(bool(status_item.data(Qt.UserRole)))
                self.assertEqual(label_item.text(), "brain_regions")
                self.assertIn("Round 1", tag_item.text())
                self.assertEqual(select_item.checkState(), Qt.Unchecked)

                widget.select_all_ready_predict_targets()
                self.assertEqual(widget.predict_targets_table.item(0, 0).checkState(), Qt.Checked)
                refs = widget._selected_part_refs_for_action("predict")
                self.assertEqual(refs, [{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}])
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_label_schema_and_user_tags_ui_bind_current_part(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget._select_volume_tree_item("01-0101-11", "part", "brain")
                self.assertEqual(widget.current_part_id, "brain")

                widget.new_label_schema()
                widget.label_schema_id_edit.setText("brain_regions_v2")
                widget.label_schema_part_name_edit.setText("brain")
                widget.label_schema_table.item(0, 1).setText("3")
                widget.label_schema_table.item(0, 2).setText("central_complex")
                widget.label_schema_table.item(0, 3).setText("#123456")
                self.assertTrue(widget.bind_current_part_label_schema())

                part = manager.get_part("01-0101-11", "brain")
                self.assertEqual(part["training"]["label_schema_id"], "brain_regions_v2")
                self.assertEqual(part["training"]["user_defined_part_name"], "brain")
                schema_labels = manager.get_label_schema("brain_regions_v2")["labels"]
                self.assertTrue(any(item["id"] == 3 and item["name"] == "central_complex" for item in schema_labels))
                central_row = -1
                for row in range(widget.material_table.rowCount()):
                    id_item = widget.material_table.item(row, 1)
                    if id_item is not None and id_item.text() == "3":
                        central_row = row
                        break
                self.assertGreaterEqual(central_row, 0)
                self.assertIn("central_complex", widget.material_table.item(central_row, 2).text())
                self.assertEqual(widget.material_table.item(central_row, 0).background().color().name(), "#123456")

                widget.new_part_user_tag()
                widget.part_user_tag_id_edit.setText("paper_fig")
                widget.part_user_tag_label_edit.setText("Paper figure")
                widget.part_user_tag_color_edit.setText("#abcdef")
                widget.save_part_user_tag()
                self.assertEqual(widget.part_user_tag_table.rowCount(), 1)
                widget.part_user_tag_table.item(0, 4).setCheckState(Qt.Checked)
                self.assertTrue(widget.apply_part_user_tags_to_current_part())

                part = manager.get_part("01-0101-11", "brain")
                self.assertEqual(part["user_tags"], ["paper_fig"])
                self.assertEqual(part["training"]["system_status"], "cut_pending_labeling")
                self.assertIn("Paper figure", widget.specimen_list.topLevelItem(0).child(1).text(0))

                index = widget.predict_filter_combo.findData("tag:paper_fig")
                self.assertGreaterEqual(index, 0)
                widget.predict_filter_combo.setCurrentIndex(index)
                widget.refresh_predict_targets()
                self.assertGreaterEqual(widget.predict_targets_table.rowCount(), 1)
                self.assertIn("Paper figure", widget.predict_targets_table.item(0, 4).text())

                widget.new_part_user_tag()
                widget.part_user_tag_id_edit.setText("round_1")
                widget.part_user_tag_label_edit.setText("Round 1")
                widget.part_user_tag_color_edit.setText("#fedcba")
                widget.save_part_user_tag()
                widget.part_user_tag_table.selectRow(1)
                self.assertTrue(widget.move_selected_part_user_tag(-1))
                self.assertEqual([tag["tag_id"] for tag in manager.project_data["part_user_tags"]], ["round_1", "paper_fig"])
                widget.refresh_predict_targets()
                self.assertLess(
                    widget.predict_filter_combo.findData("tag:round_1"),
                    widget.predict_filter_combo.findData("tag:paper_fig"),
                )
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_label_schema_import_export_dialogs_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget._populate_label_schema_combo("brain_regions")
                export_path = root / "brain_regions_export.json"
                with patch("AntSleap.ui.tif_workbench.QFileDialog.getSaveFileName", return_value=(str(export_path), "TaxaMask label schema (*.json)")):
                    self.assertEqual(widget.export_label_schema_dialog(), str(export_path))
                self.assertTrue(export_path.exists())
                exported = json.loads(export_path.read_text(encoding="utf-8"))
                self.assertEqual(exported["label_schema"]["schema_id"], "brain_regions")
                self.assertIn("Exported label schema brain_regions", widget.training_status_label.text())

                import_path = root / "brain_regions_import.json"
                import_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "taxamask_tif_label_schema_v1",
                            "label_schema": {
                                "schema_id": "brain_regions_imported",
                                "user_defined_part_name": "brain",
                                "labels": [{"id": 7, "name": "optic_lobe", "display_name": "Optic lobe", "color": "#112233"}],
                            },
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                with patch("AntSleap.ui.tif_workbench.QFileDialog.getOpenFileName", return_value=(str(import_path), "TaxaMask label schema (*.json)")):
                    schema = widget.import_label_schema_dialog()

                self.assertEqual(schema["schema_id"], "brain_regions_imported")
                self.assertEqual(manager.get_label_schema("brain_regions_imported")["labels"][0]["id"], 7)
                self.assertGreaterEqual(widget.label_schema_combo.findData("brain_regions_imported"), 0)
                self.assertEqual(widget.label_schema_table.item(0, 2).text(), "Optic lobe")
                self.assertIn("Imported label schema brain_regions_imported", widget.training_status_label.text())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_new_label_schema_uses_current_part_instead_of_brain_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            part = manager.get_part("01-0101-11", "brain")
            part["part_id"] = "antenna"
            part["display_name"] = "Antenna"
            manager.save_project()
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.current_volume_scope = "part"
                widget.current_specimen_id = "01-0101-11"
                widget.current_part_id = "antenna"
                widget.current_part = part

                schema_id = widget.new_label_schema()

                self.assertEqual(schema_id, "antenna_regions")
                self.assertEqual(widget.label_schema_part_name_edit.text(), "antenna")
                self.assertEqual(widget.label_schema_table.item(0, 2).text(), "label_1")
                self.assertNotIn("brain", schema_id)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_label_schema_import_cancel_keeps_existing_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            widget = TifWorkbenchWidget(manager, "en")
            import_path = root / "brain_regions_replace.json"
            import_path.write_text(
                json.dumps(
                    {
                        "schema_version": "taxamask_tif_label_schema_v1",
                        "label_schema": {
                            "schema_id": "brain_regions",
                            "user_defined_part_name": "brain",
                            "labels": [{"id": 9, "name": "wrong_region", "color": "#000000"}],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            try:
                before = list(manager.get_label_schema("brain_regions")["labels"])
                with patch("AntSleap.ui.tif_workbench.QFileDialog.getOpenFileName", return_value=(str(import_path), "TaxaMask label schema (*.json)")), \
                     patch("AntSleap.ui.tif_workbench.QMessageBox.question", return_value=QMessageBox.No):
                    self.assertIsNone(widget.import_label_schema_dialog())

                self.assertEqual(manager.get_label_schema("brain_regions")["labels"], before)
                self.assertFalse(any(item["id"] == 9 for item in manager.get_label_schema("brain_regions")["labels"]))
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_browse_model_manifest_sets_predict_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "model_manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            manager = TifProjectManager()
            manager.create_project("manifest_picker", root / "project")
            widget = TifWorkbenchWidget(manager, "en")
            try:
                with patch("AntSleap.ui.tif_workbench.QFileDialog.getOpenFileName", return_value=(str(manifest), "JSON (*.json)")):
                    self.assertTrue(widget.browse_model_manifest())
                self.assertEqual(widget.backend_manifest_edit.text(), str(manifest))
                self.assertEqual(widget.backend_config["model_manifest"], str(manifest))
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_predict_requires_existing_model_manifest_before_backend_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.backend_predict_edit.setText(f"{os.sys.executable} missing_predict.py")
                widget.select_all_ready_predict_targets()
                with patch_message_boxes():
                    widget.run_backend_action("predict")
                self.assertFalse(widget._backend_action_running())
                self.assertIn("Select a model manifest", widget.training_status_label.text())

                widget.backend_manifest_edit.setText(str(root / "missing_manifest.json"))
                with patch_message_boxes():
                    widget.run_backend_action("predict")
                self.assertFalse(widget._backend_action_running())
                self.assertIn("Model manifest does not exist", widget.training_status_label.text())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_part_training_action_reports_missing_training_truth_without_top_level_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget._select_volume_tree_item("01-0101-11", "part_reslice", "brain", "brain_axis_001")
                widget.backend_train_edit.setText(f"{os.sys.executable} missing_train.py")
                with patch("AntSleap.ui.tif_workbench.QMessageBox.warning", return_value=None) as warning_mock:
                    widget.run_backend_action("train")

                self.assertFalse(widget._backend_action_running())
                self.assertEqual(warning_mock.call_count, 1)
                message = str(warning_mock.call_args[0][2])
                self.assertIn("Current part/reslice is not train-ready yet", message)
                self.assertIn("Training truth is missing", message)
                self.assertIn("Accept as training truth", message)
                self.assertNotEqual(message, "No train-ready top-level volumes are available.")
                self.assertNotIn("No train-ready top-level volumes", widget.training_status_label.text())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_backend_action_waits_for_async_label_save_before_starting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.backend_prepare_edit.setText(f"{os.sys.executable} missing_prepare.py")
                widget.current_specimen_id = "01-0101-11"
                widget.current_part_id = "brain"
                widget.current_reslice_id = "brain_axis_001"
                widget.current_volume_scope = "part"
                widget.working_edit_dirty = True

                with patch("AntSleap.ui.tif_workbench.QMessageBox.question", return_value=QMessageBox.Save), \
                     patch.object(widget, "save_working_edit", side_effect=AssertionError("sync save should not run")), \
                     patch.object(widget, "save_working_edit_async", return_value=True) as async_save:
                    widget.run_backend_action("prepare_dataset")

                async_save.assert_called_once()
                self.assertFalse(widget._backend_action_running())
                self.assertEqual(widget._pending_backend_action_after_save["action"], "prepare_dataset")

                started = []
                captured = {}

                class FakeThread:
                    def __init__(self, parent=None):
                        self.started = type("SignalLike", (), {"connect": lambda self, slot: started.append("started")})()
                        self.finished = type("SignalLike", (), {"connect": lambda self, slot: None})()

                    def start(self):
                        started.append("start_called")

                    def quit(self):
                        started.append("quit")

                    def deleteLater(self):
                        pass

                class FakeWorker:
                    def __init__(self, *args, **kwargs):
                        captured["args"] = args
                        captured["kwargs"] = kwargs
                        self.progress = type("SignalLike", (), {"connect": lambda self, slot: None})()
                        self.finished = type("SignalLike", (), {"connect": lambda self, slot: None})()
                        self.failed = type("SignalLike", (), {"connect": lambda self, slot: None})()

                    def moveToThread(self, thread):
                        started.append("move")

                    def run(self):
                        pass

                    def deleteLater(self):
                        pass

                widget.working_edit_dirty = False
                with patch("AntSleap.ui.tif_workbench.QThread", FakeThread), \
                     patch("AntSleap.ui.tif_workbench.TifBackendActionWorker", FakeWorker):
                    self.assertTrue(widget._resume_pending_backend_action_after_save())

                self.assertTrue(widget._backend_action_running())
                self.assertEqual(captured["args"][2], "prepare_dataset")
                self.assertEqual(captured["kwargs"]["input_scope"], "part_reslice")
                self.assertEqual(
                    captured["kwargs"]["part_refs"],
                    [{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}],
                )
                self.assertIn("start_called", started)
            finally:
                widget._tif_backend_thread = None
                widget._tif_backend_worker = None
                widget.working_edit_dirty = False
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_accept_selected_ai_results_promotes_batch_to_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            edit_rel = "specimens/01-0101-11/parts/brain/reslices/brain_axis_001/labels/editable_ai_result.ome.zarr"
            edit_array = np.full((4, 4, 4), 2, dtype=np.uint16)
            edit_meta = write_volume_sidecar(root / "backend" / edit_rel, edit_array, role="editable_ai_result")
            manager.register_part_reslice_label_volume(
                "01-0101-11",
                "brain",
                "brain_axis_001",
                "editable_ai_result",
                edit_rel,
                edit_meta["shape_zyx"],
                edit_meta["dtype"],
                status="pending_review",
                save=False,
            )
            manager.set_part_training_metadata("01-0101-11", "brain", opened_for_review=True, save=True)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.select_all_ready_predict_targets()
                with patch("AntSleap.ui.tif_workbench.QMessageBox.question", return_value=QMessageBox.Yes):
                    self.assertTrue(widget.accept_selected_ai_results())

                part = widget.project.get_part("01-0101-11", "brain")
                reslice = widget.project.get_part_reslice("01-0101-11", "brain", "brain_axis_001")
                self.assertFalse((part["labels"]["manual_truth"] or {}).get("path"))
                self.assertEqual(reslice["labels"]["manual_truth"]["status"], "reviewed")
                self.assertEqual(part["training"]["system_status"], "verified_train_ready")
                self.assertIn("Accepted 1 editable AI result", widget.training_status_label.text())
                np.testing.assert_array_equal(load_volume_sidecar(root / "backend" / reslice["labels"]["manual_truth"]["path"]), edit_array)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_accept_selected_ai_results_requires_saved_current_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            edit_rel = "specimens/01-0101-11/parts/brain/reslices/brain_axis_001/labels/editable_ai_result.ome.zarr"
            edit_meta = write_volume_sidecar(root / "backend" / edit_rel, np.ones((4, 4, 4), dtype=np.uint16), role="editable_ai_result")
            manager.register_part_reslice_label_volume(
                "01-0101-11",
                "brain",
                "brain_axis_001",
                "editable_ai_result",
                edit_rel,
                edit_meta["shape_zyx"],
                edit_meta["dtype"],
                status="pending_review",
                save=False,
            )
            manager.set_part_training_metadata("01-0101-11", "brain", opened_for_review=True, save=True)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.current_volume_scope = "part"
                widget.working_edit_dirty = True
                widget.select_all_ready_predict_targets()
                with patch_message_boxes(), patch.object(widget, "save_working_edit", side_effect=AssertionError("sync save should not run")):
                    self.assertFalse(widget.accept_selected_ai_results())

                self.assertIn("Save current labels before accepting selected AI results", widget.operation_status_label.text())
                self.assertFalse(widget.project.evaluate_part_train_ready("01-0101-11", "brain")["train_ready"])
            finally:
                widget.working_edit_dirty = False
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_ai_review_check_label_reports_unknown_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            edit_rel = "specimens/01-0101-11/parts/brain/reslices/brain_axis_001/labels/editable_ai_result.ome.zarr"
            edit_meta = write_volume_sidecar(root / "backend" / edit_rel, np.full((4, 4, 4), 9, dtype=np.uint16), role="editable_ai_result")
            manager.register_part_reslice_label_volume(
                "01-0101-11",
                "brain",
                "brain_axis_001",
                "editable_ai_result",
                edit_rel,
                edit_meta["shape_zyx"],
                edit_meta["dtype"],
                status="pending_review",
                save=False,
            )
            manager.set_part_training_metadata("01-0101-11", "brain", opened_for_review=True, save=True)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget._select_volume_tree_item("01-0101-11", "part_reslice", "brain", "brain_axis_001")
                text = widget.ai_review_check_label.text()
                self.assertIn("Review check blocked", text)
                self.assertIn("unknown labels: 9", text)
                self.assertIn("Schema brain_regions", text)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_accept_selected_ai_results_warns_before_unopened_batch_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            edit_rel = "specimens/01-0101-11/parts/brain/reslices/brain_axis_001/labels/editable_ai_result.ome.zarr"
            edit_meta = write_volume_sidecar(root / "backend" / edit_rel, np.ones((4, 4, 4), dtype=np.uint16), role="editable_ai_result")
            manager.register_part_reslice_label_volume(
                "01-0101-11",
                "brain",
                "brain_axis_001",
                "editable_ai_result",
                edit_rel,
                edit_meta["shape_zyx"],
                edit_meta["dtype"],
                status="pending_review",
                save=False,
            )
            manager.set_part_training_metadata("01-0101-11", "brain", opened_for_review=False, save=True)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.select_all_ready_predict_targets()
                replies = [QMessageBox.No]

                def answer(*args, **kwargs):
                    return replies.pop(0)

                with patch("AntSleap.ui.tif_workbench.QMessageBox.question", side_effect=answer) as question_mock:
                    self.assertFalse(widget.accept_selected_ai_results())
                self.assertEqual(question_mock.call_count, 1)
                self.assertFalse(widget.project.evaluate_part_train_ready("01-0101-11", "brain")["train_ready"])
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_accept_selected_ai_results_blocks_unknown_label_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            edit_rel = "specimens/01-0101-11/parts/brain/reslices/brain_axis_001/labels/editable_ai_result.ome.zarr"
            edit_meta = write_volume_sidecar(root / "backend" / edit_rel, np.full((4, 4, 4), 9, dtype=np.uint16), role="editable_ai_result")
            manager.register_part_reslice_label_volume(
                "01-0101-11",
                "brain",
                "brain_axis_001",
                "editable_ai_result",
                edit_rel,
                edit_meta["shape_zyx"],
                edit_meta["dtype"],
                status="pending_review",
                save=False,
            )
            manager.set_part_training_metadata("01-0101-11", "brain", opened_for_review=True, save=True)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.select_all_ready_predict_targets()
                with patch_message_boxes():
                    self.assertFalse(widget.accept_selected_ai_results())
                self.assertIn("label/schema problems", widget.training_status_label.text())
                self.assertIn("unknown labels: 9", widget.training_status_label.text())
                self.assertFalse(widget.project.evaluate_part_train_ready("01-0101-11", "brain")["train_ready"])
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_predict_overwrite_prompt_blocks_or_allows_backend_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            manifest = root / "model_manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            editable_rel = "specimens/01-0101-11/parts/brain/reslices/brain_axis_001/labels/editable_ai_result.ome.zarr"
            editable_meta = write_volume_sidecar(root / "backend" / editable_rel, np.ones((4, 4, 4), dtype=np.uint16), role="editable_ai_result")
            manager.register_part_reslice_label_volume(
                "01-0101-11",
                "brain",
                "brain_axis_001",
                "editable_ai_result",
                editable_rel,
                editable_meta["shape_zyx"],
                editable_meta["dtype"],
                save=True,
            )
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.current_specimen_id = "01-0101-11"
                widget.current_part_id = "brain"
                widget.current_volume_scope = "part"
                widget.backend_predict_edit.setText(f"{os.sys.executable} missing_predict.py")
                widget.backend_manifest_edit.setText(str(manifest))
                widget.select_all_ready_predict_targets()
                with patch("AntSleap.ui.tif_workbench.QMessageBox.question", return_value=QMessageBox.No):
                    widget.run_backend_action("predict")
                self.assertFalse(widget._backend_action_running())
                self.assertNotIn("Running predict", widget.training_status_label.text())

                started = []

                class FakeThread:
                    def __init__(self, parent=None):
                        self.started = type("SignalLike", (), {"connect": lambda self, slot: started.append("started")})()
                        self.finished = type("SignalLike", (), {"connect": lambda self, slot: None})()

                    def start(self):
                        started.append("start_called")

                    def quit(self):
                        started.append("quit")

                    def deleteLater(self):
                        pass

                captured = {}

                class FakeWorker:
                    def __init__(self, *args, **kwargs):
                        captured["args"] = args
                        captured["kwargs"] = kwargs
                        self.progress = type("SignalLike", (), {"connect": lambda self, slot: None})()
                        self.finished = type("SignalLike", (), {"connect": lambda self, slot: None})()
                        self.failed = type("SignalLike", (), {"connect": lambda self, slot: None})()

                    def moveToThread(self, thread):
                        started.append("move")

                    def run(self):
                        pass

                    def deleteLater(self):
                        pass

                with patch("AntSleap.ui.tif_workbench.QMessageBox.question", return_value=QMessageBox.Yes), patch("AntSleap.ui.tif_workbench.QThread", FakeThread), patch("AntSleap.ui.tif_workbench.TifBackendActionWorker", FakeWorker):
                    widget.run_backend_action("predict")
                self.assertTrue(widget._backend_action_running())
                self.assertIn("Running predict", widget.training_status_label.text())
                self.assertIn("start_called", started)
                self.assertEqual(captured["kwargs"]["model_manifest"], str(manifest))
                self.assertEqual(captured["kwargs"]["input_scope"], "part_reslice")
                self.assertEqual(captured["kwargs"]["specimen_ids"], [])
                self.assertEqual(captured["kwargs"]["part_refs"], [{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}])
            finally:
                widget._tif_backend_thread = None
                widget._tif_backend_worker = None
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_training_selection_defers_expensive_part_label_id_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.current_volume_scope = "part"
                widget.current_specimen_id = "01-0101-11"
                widget.current_part_id = "brain"
                widget.current_reslice_id = "brain_axis_001"
                with patch.object(manager, "validate_part_label_ids", side_effect=AssertionError("label scan should be deferred")):
                    selection = widget._selected_backend_samples_for_action("prepare_dataset")

                self.assertEqual(selection["input_scope"], "part_reslice")
                self.assertEqual(
                    selection["part_refs"],
                    [{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}],
                )
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_backend_write_lock_blocks_project_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.current_specimen_id = "01-0101-11"
                widget.current_part_id = "brain"
                widget.current_volume_scope = "part"
                widget.current_reslice_id = ""
                widget.image_volume = np.zeros((2, 3, 4), dtype=np.uint8)
                widget.edit_volume = np.zeros((2, 3, 4), dtype=np.uint16)
                widget._tif_backend_thread = object()
                widget._set_scope_controls_enabled()
                self.assertTrue(widget._backend_write_lock_active())
                self.assertFalse(widget.btn_save_edit.isEnabled())
                self.assertFalse(widget.btn_promote.isEnabled())
                self.assertFalse(widget.btn_export_training.isEnabled())
                self.assertFalse(widget.btn_local_axis_reslice.isEnabled())

                with patch_message_boxes(), patch.object(widget.project, "save_project") as save_mock:
                    self.assertFalse(widget.save_working_edit(show_message=True))
                    self.assertFalse(widget.export_current_part_package())
                    self.assertIsNone(widget.copy_source_z_axis_to_local_axis_draft())
                    with patch("AntSleap.ui.tif_workbench.QFileDialog.getOpenFileNames") as open_files:
                        widget.import_tif_stack_dialog()
                        open_files.assert_not_called()
                    with patch("AntSleap.ui.tif_workbench.QFileDialog.getExistingDirectory") as open_dir:
                        widget.import_amira_directory_dialog()
                        open_dir.assert_not_called()
                    save_mock.assert_not_called()
                self.assertIn("Backend run is active", widget.operation_status_label.text())
            finally:
                widget._tif_backend_thread = None
                widget._tif_backend_worker = None
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_task_manager_preview_lock_blocks_project_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp), z_count=5)
            try:
                task = widget._start_tif_task("volume_preview", action="build_preview", message="Preparing preview")
                self.assertTrue(widget._backend_write_lock_active())
                self.assertIn("Volume preview", widget._backend_write_lock_message())
                with patch_message_boxes(), patch("AntSleap.ui.tif_workbench.QFileDialog.getOpenFileNames") as open_files:
                    widget.import_tif_stack_dialog()
                    open_files.assert_not_called()
                widget._finish_tif_task(task.task_id, message="done")
                self.assertFalse(widget._backend_write_lock_active())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_backend_failure_preserves_run_folder_for_log_review(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            run_dir = os.path.join(tempfile.gettempdir(), "taxamask_failed_backend_run")
            result_json = os.path.join(run_dir, "result.json")
            widget._tif_backend_thread = object()
            widget._tif_backend_action = "train"
            long_error = (
                "tif_backend_train_failed:2:C:/very/long/train_stderr.log\n"
                "taxamask_tif_nnunet_v2_backend failed: nnunet_command_failed:1:C:/very/long/nnunet_v2_commands.log"
            )
            with patch_message_boxes():
                widget._on_tif_backend_failed(
                    long_error,
                    {"run_dir": run_dir, "result_json": result_json, "action": "train"},
                )
            self.assertEqual(widget._tif_backend_run_dir, run_dir)
            self.assertEqual(widget._tif_backend_result_json, result_json)
            self.assertIn("nnU-Net command failed", widget.training_status_label.text())
            self.assertNotIn("C:/very/long", widget.backend_run_status_label.text())
            self.assertIn("nnunet_v2_commands.log", widget.backend_log_tail.toPlainText())
            self.assertIn("C:/very/long", widget.backend_log_tail.toolTip())
            self.assertFalse(widget.btn_open_backend_result.isEnabled())
        finally:
            widget._tif_backend_thread = None
            widget._tif_backend_worker = None
            widget.close_project(prompt_unsaved=False)
            widget.deleteLater()

    def test_backend_failure_summarizes_single_sample_training_requirement(self):
        manager = TifProjectManager()
        widget = TifWorkbenchWidget(manager, "en")
        try:
            widget._tif_backend_thread = object()
            widget._tif_backend_action = "train"
            with patch_message_boxes():
                widget._on_tif_backend_failed(
                    "tif_backend_train_failed:2:stderr.log\n"
                    "taxamask_tif_nnunet_v2_backend failed: nnunet_training_requires_at_least_2_samples:1",
                    {"action": "train"},
                )
            self.assertIn("at least 2", widget.training_status_label.text())
            self.assertIn("1", widget.training_status_label.text())
        finally:
            widget._tif_backend_thread = None
            widget._tif_backend_worker = None
            widget.close_project(prompt_unsaved=False)
            widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
