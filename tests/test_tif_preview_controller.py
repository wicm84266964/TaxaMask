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

    from tests.test_tif_backend import make_train_ready_project

    from AntSleap.core.tif_volume_io import write_volume_sidecar
    from AntSleap.ui.tif_workbench import TifWorkbenchWidget


def _winerror_1455():
    exc = OSError(1455, "页面文件太小，无法完成操作。")
    exc.winerror = 1455
    return exc


@unittest.skipUnless(QApplication is not None, "PySide6 is required for TIF preview controller tests")
class TifPreviewControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_safe_load_volume_sidecar_records_commit_memory_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_train_ready_project(Path(tmp))
            widget = TifWorkbenchWidget(manager, "en")
            try:
                with patch("AntSleap.ui.tif_preview_controller.load_volume_sidecar", side_effect=_winerror_1455()):
                    volume, issue = widget.preview_controller.safe_load_volume_sidecar(
                        manager.to_absolute("specimens/01-0101-11/labels/working_edit.ome.zarr"),
                        mmap_mode="c",
                        operation="load_working_edit_volume",
                    )

                self.assertIsNone(volume)
                self.assertEqual(issue.kind, "commit_memory")
                summary = widget.preview_controller.state_summary()
                self.assertTrue(summary["resource_limited"])
                self.assertEqual(summary["kind"], "commit_memory")
                self.assertIn("page file", summary["user_message"])
                self.assertIn("Project data was not modified", widget.training_status_label.text())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_load_specimen_survives_edit_volume_commit_memory_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            edit_rel = "specimens/01-0101-11/labels/working_edit.ome.zarr"
            edit_meta = write_volume_sidecar(root / "backend" / edit_rel, np.zeros((2, 3, 4), dtype=np.uint16), role="working_edit")
            manager.register_label_volume(
                "01-0101-11",
                "working_edit",
                edit_rel,
                edit_meta["shape_zyx"],
                edit_meta["dtype"],
                status="empty_edit",
                save=True,
            )
            real_loader = __import__("AntSleap.ui.tif_preview_controller", fromlist=["load_volume_sidecar"]).load_volume_sidecar

            def fail_only_edit(path, mmap_mode="r"):
                if str(path).replace("\\", "/").endswith("labels/working_edit.ome.zarr"):
                    raise _winerror_1455()
                return real_loader(path, mmap_mode=mmap_mode)

            widget = TifWorkbenchWidget(manager, "en")
            try:
                with patch("AntSleap.ui.tif_preview_controller.load_volume_sidecar", side_effect=fail_only_edit):
                    widget.load_specimen("01-0101-11")

                self.assertIsNotNone(widget.image_volume)
                self.assertIsNone(widget.edit_volume)
                summary = widget.preview_controller.state_summary()
                self.assertTrue(summary["resource_limited"])
                self.assertEqual(summary["kind"], "commit_memory")
                self.assertIn("page file", widget.volume_status_text())
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
