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
                self.assertIn("测量网格", dialog.scale_label.text())
                self.assertIn("毫米", dialog.scale_label.text())
                self.assertIn("测量", dialog.export_button.text())
                self.assertEqual(dialog.history_table.columnCount(), 7)
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

    def test_dialog_bootstrap_recovers_then_marks_unknown_scale_as_unitless_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = _project(Path(tmp), spacing_unit="unknown")
            recovery = {
                "checked_count": 1,
                "complete_count": 0,
                "incomplete_count": 1,
                "records": [{"status": "incomplete"}],
            }
            with patch(
                "AntSleap.ui.tif_mesh_export_dialog.recover_interrupted_mesh_exports",
                return_value=recovery,
            ) as recover:
                dialog = TifMeshExportDialog(manager, "ant_001", lang="zh")
                try:
                    self._wait_for_worker(dialog)
                    recover.assert_called_once()
                    self.assertIs(recover.call_args.args[0], manager)
                    self.assertEqual(recover.call_args.kwargs["specimen_id"], "ant_001")
                    self.assertEqual(recover.call_args.kwargs["part_id"], "")
                    self.assertEqual(recover.call_args.kwargs["reslice_id"], "")
                    self.assertTrue(callable(recover.call_args.kwargs["cancel_check"]))
                    self.assertTrue(callable(recover.call_args.kwargs["progress_callback"]))
                    self.assertEqual(dialog.mesh_purpose, "observation")
                    self.assertEqual(dialog.output_unit, "unitless")
                    self.assertIn("观察网格", dialog.scale_label.text())
                    self.assertIn("无单位", dialog.scale_label.text())
                    self.assertIn("不可用于物理测量", dialog.scale_label.text())
                    self.assertIn("观察", dialog.export_button.text())
                    self.assertIn("1 个未完成", dialog.status_label.text())
                finally:
                    dialog.deleteLater()

    def test_registry_mismatch_error_explains_recovery_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = _project(Path(tmp))
            dialog = TifMeshExportDialog(manager, "ant_001", lang="zh")
            try:
                self._wait_for_worker(dialog)
                with patch(
                    "AntSleap.ui.tif_mesh_export_dialog.QMessageBox.critical"
                ) as critical:
                    dialog._on_error("mesh_manual_truth_registry_mismatch")
                message = critical.call_args.args[2]
                self.assertIn("TaxaMask 外发生了变化", message)
                self.assertIn("恢复登记文件", message)
                self.assertIn("登记为新版本", message)
                self.assertIn("重新审核", message)
            finally:
                dialog.deleteLater()

    def test_unsafe_truth_path_error_explains_safe_relocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = _project(Path(tmp))
            dialog = TifMeshExportDialog(manager, "ant_001", lang="zh")
            try:
                self._wait_for_worker(dialog)
                with patch(
                    "AntSleap.ui.tif_mesh_export_dialog.QMessageBox.critical"
                ) as critical:
                    dialog._on_error("mesh_manual_truth_path_unsafe")
                message = critical.call_args.args[2]
                self.assertIn("符号链接", message)
                self.assertIn("junction", message)
                self.assertIn("重新定位或登记", message)
            finally:
                dialog.deleteLater()

    def test_workbench_routes_full_and_reslice_scope_to_mesh_dialog(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = _project(Path(tmp))
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.show()
                self.app.processEvents()
                widget.current_specimen_id = "ant_001"
                widget.current_volume_scope = "full"
                widget.current_part_id = ""
                widget.current_reslice_id = ""
                widget.image_volume = np.zeros((2, 2, 2), dtype=np.uint8)
                widget._set_scope_controls_enabled()
                self.assertTrue(widget.btn_export_reviewed_mesh.isEnabled())
                for display_mode in ("slice", "volume"):
                    widget.display_mode = display_mode
                    widget._sync_mode_sections()
                    self.app.processEvents()
                    self.assertTrue(
                        widget.btn_export_reviewed_mesh.isVisibleTo(widget),
                        f"full/{display_mode} mesh export entry is hidden",
                    )
                manager.get_specimen("ant_001")["labels"]["manual_truth"]["status"] = "draft"
                widget._set_scope_controls_enabled()
                self.assertFalse(widget.btn_export_reviewed_mesh.isEnabled())
                manual = manager.get_specimen("ant_001")["labels"]["manual_truth"]
                manual["status"] = ""
                manual.pop("review_audit", None)
                manual.pop("training", None)
                widget._set_scope_controls_enabled()
                self.assertFalse(widget.btn_export_reviewed_mesh.isEnabled())
                manual.pop("role", None)
                manager.get_specimen("ant_001")["labels"]["manual_truth"]["status"] = "reviewed"
                widget._set_scope_controls_enabled()
                self.assertTrue(widget.btn_export_reviewed_mesh.isEnabled())
                with patch("AntSleap.ui.tif_workbench.TifMeshExportDialog") as dialog_type:
                    widget.open_reviewed_mesh_export_dialog()
                self.assertEqual(dialog_type.call_args.args[1], "ant_001")
                self.assertEqual(dialog_type.call_args.kwargs["part_id"], "")
                self.assertEqual(dialog_type.call_args.kwargs["reslice_id"], "")
                dialog_type.return_value.exec.assert_called_once_with()

                widget.current_volume_scope = "part"
                widget.current_part_id = "head"
                widget.current_reslice_id = "head_axis_001"
                with patch.object(widget.local_axis_controller, "update_summary"):
                    for display_mode in ("slice", "volume"):
                        widget.display_mode = display_mode
                        widget._sync_mode_sections()
                        self.app.processEvents()
                        self.assertTrue(
                            widget.btn_export_reviewed_mesh.isVisibleTo(widget),
                            f"part/{display_mode} mesh export entry is hidden",
                        )
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
