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

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    import numpy as np

    from AntSleap.core.tif_part_extraction import crop_volume_to_part
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.core.tif_volume_io import write_volume_sidecar
    from AntSleap.ui.tif_workbench import TifWorkbenchWidget


@unittest.skipUnless(QApplication is not None, "PySide6 is required for TIF Local Axis controller tests")
class TifLocalAxisControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_part_widget(self, root):
        manager = TifProjectManager()
        project_root = root / "local_axis_controller"
        manager.create_project("local_axis_controller", project_root)
        manager.create_specimen_scaffold("01-0101-21", modality="confocal")
        image = np.arange(5 * 8 * 8, dtype=np.uint8).reshape((5, 8, 8))
        edit = np.zeros((5, 8, 8), dtype=np.uint16)
        image_rel = "specimens/01-0101-21/working/image.ome.zarr"
        edit_rel = "specimens/01-0101-21/labels/working_edit.ome.zarr"
        image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image")
        edit_meta = write_volume_sidecar(project_root / edit_rel, edit, role="working_edit")
        manager.register_working_volume("01-0101-21", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
        manager.register_label_volume("01-0101-21", "working_edit", edit_rel, edit_meta["shape_zyx"], edit_meta["dtype"], save=True)
        crop_volume_to_part(manager, "01-0101-21", "head", [[0, 4], [1, 7], [1, 7]], display_name="Head")
        crop_volume_to_part(manager, "01-0101-21", "thorax", [[1, 5], [1, 7], [1, 7]], display_name="Thorax")
        widget = TifWorkbenchWidget(manager, "en")
        widget.resize(900, 620)
        widget.refresh_project()
        widget._select_volume_tree_item("01-0101-21", "part", "head")
        return widget

    def test_controller_keeps_draft_scoped_to_current_part(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_part_widget(Path(tmp))
            try:
                draft = widget.local_axis_controller.copy_source_z_axis_to_draft()

                self.assertIsNotNone(draft)
                self.assertEqual(widget.local_axis_controller.current_draft()["part_id"], "head")

                widget.current_part_id = "thorax"
                widget.local_axis_controller.clear_draft_if_part_changed("01-0101-21", "thorax")

                self.assertIsNone(widget.local_axis_draft)
                self.assertIsNone(widget.local_axis_controller.current_draft())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_controller_allows_roll_pick_target_during_preview_busy_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_part_widget(Path(tmp))
            task = None
            try:
                task = widget._start_tif_task("volume_preview", action="build_preview", message="Preparing preview")

                with patch.object(widget, "render_volume_preview", return_value=None):
                    self.assertTrue(widget.local_axis_controller.set_pick_target("roll_a"))

                self.assertTrue(widget._backend_write_lock_active())
                self.assertEqual(widget._local_axis_pick_target, "roll_a")
                self.assertEqual(widget._local_axis_roll_pick_target, "roll_a")
                self.assertIsNotNone(widget.local_axis_controller.current_draft())
                self.assertTrue(widget.volume_clip_plane_check.isChecked())
                self.assertTrue(widget.btn_pick_roll_ref_a.isChecked())
                self.assertEqual(widget.task_manager.task(task.task_id).status, "running")
            finally:
                if task is not None:
                    widget._finish_tif_task(task.task_id, message="done")
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_controller_builds_reslice_payload_with_three_point_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_part_widget(Path(tmp))
            try:
                draft = widget.local_axis_controller.copy_source_z_axis_to_draft()
                self.assertIsNotNone(draft)
                widget.local_axis_draft["roll_reference"] = {
                    "pair_id": "roll_reference_point_pair",
                    "point_a": {"role": "roll_reference_a", "zyx": [1.0, 1.0, 1.0]},
                    "point_b": {"role": "roll_reference_b", "zyx": [1.0, 5.0, 1.0]},
                    "point_c": {"role": "reference_plane_c", "zyx": [3.0, 1.0, 5.0]},
                }

                self.assertTrue(widget.local_axis_controller.align_to_reference_plane())
                payload = widget.local_axis_controller.current_reslice_payload()

                self.assertEqual(payload["template_id"], "head")
                self.assertEqual(payload["roll_reference"]["point_c"]["role"], "reference_plane_c")
                self.assertEqual(payload["reference_plane"]["plane_id"], "three_point_reference_plane")
                self.assertEqual(payload["training"]["source"], "manual_confirmed")
                self.assertEqual(payload["provenance"]["reference_plane_source"], "manual_three_point_plane")
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
