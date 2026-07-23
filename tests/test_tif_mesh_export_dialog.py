import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from AntSleap.ui.tif_mesh_export_dialog import TifMeshExportDialog
    from AntSleap.ui.tif_workbench import TifWorkbenchWidget
    from tests.test_mesh_export import _project


@unittest.skipUnless(QApplication is not None, "PySide6 is required for mesh export UI tests")
class TifMeshExportDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _wait_for_worker(self, dialog, timeout=5.0):
        deadline = time.monotonic() + timeout
        while dialog.worker is not None and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertIsNone(dialog.worker)

    def test_dialog_scans_reviewed_source_then_click_starts_export_without_signal_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = _project(Path(tmp))
            dialog = TifMeshExportDialog(manager, "ant_001", lang="zh")
            try:
                self.assertIsNotNone(dialog.worker)
                self.assertFalse(dialog.export_button.isEnabled())
                self._wait_for_worker(dialog)
                self.assertTrue(dialog.source_ready)
                self.assertEqual(dialog.label_table.rowCount(), 2)
                with patch.object(dialog, "_start_worker") as start_worker:
                    dialog.export_button.click()
                    self.app.processEvents()
                self.assertEqual(start_worker.call_args.args[0], "export")
                self.assertEqual(
                    start_worker.call_args.args[1]["label_ids"],
                    [1, 2],
                )
            finally:
                dialog.deleteLater()

    def test_workbench_routes_full_and_reslice_scope_to_mesh_dialog(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = _project(Path(tmp))
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.current_specimen_id = "ant_001"
                widget.current_volume_scope = "full"
                widget.current_part_id = ""
                widget.current_reslice_id = ""
                widget.image_volume = np.zeros((2, 2, 2), dtype=np.uint8)
                widget._set_scope_controls_enabled()
                self.assertTrue(widget.btn_export_reviewed_mesh.isEnabled())
                manager.get_specimen("ant_001")["labels"]["manual_truth"]["status"] = "draft"
                widget._set_scope_controls_enabled()
                self.assertFalse(widget.btn_export_reviewed_mesh.isEnabled())
                manager.get_specimen("ant_001")["labels"]["manual_truth"]["status"] = "reviewed"
                with patch("AntSleap.ui.tif_workbench.TifMeshExportDialog") as dialog_type:
                    widget.open_reviewed_mesh_export_dialog()
                self.assertEqual(dialog_type.call_args.args[1], "ant_001")
                self.assertEqual(dialog_type.call_args.kwargs["part_id"], "")
                self.assertEqual(dialog_type.call_args.kwargs["reslice_id"], "")
                dialog_type.return_value.exec.assert_called_once_with()

                widget.current_volume_scope = "part"
                widget.current_part_id = "head"
                widget.current_reslice_id = "head_axis_001"
                manual = manager.get_specimen("ant_001")["labels"]["manual_truth"]
                with patch.object(manager, "part_label_record", return_value=manual), patch(
                    "AntSleap.ui.tif_workbench.TifMeshExportDialog"
                ) as part_dialog_type:
                    widget.open_reviewed_mesh_export_dialog()
                self.assertEqual(part_dialog_type.call_args.kwargs["part_id"], "head")
                self.assertEqual(
                    part_dialog_type.call_args.kwargs["reslice_id"],
                    "head_axis_001",
                )
            finally:
                widget.current_volume_scope = "full"
                widget.current_part_id = ""
                widget.current_reslice_id = ""
                widget.close_project()
                widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
