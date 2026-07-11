import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.ui.tif_workbench import TifWorkbenchWidget


@unittest.skipUnless(QApplication is not None, "PySide6 is required for coordinator tests")
class TifWorkbenchCoordinatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_busy_task_message_and_preview_ignore_are_ordered(self):
        widget = TifWorkbenchWidget(TifProjectManager(), "en")
        try:
            task = widget._start_tif_task("volume_preview", action="build")
            self.assertTrue(widget.coordinator.backend_write_lock_active())
            self.assertIn("Volume preview", widget.coordinator.backend_write_lock_message())
            ignored = widget.coordinator.preview_interaction_task_types()
            self.assertFalse(widget.coordinator.backend_write_lock_active(ignored_task_types=ignored))
            self.assertTrue(widget.coordinator.guard_backend_write_lock(show_message=False, ignored_task_types=ignored))
            widget._finish_tif_task(task.task_id)
        finally:
            widget.deleteLater()

    def test_roi_lock_uses_part_extraction_title(self):
        widget = TifWorkbenchWidget(TifProjectManager(), "en")
        try:
            widget.roi_workflow_controller.is_confirm_running = Mock(return_value=True)
            self.assertTrue(widget.coordinator.backend_write_lock_active())
            self.assertEqual(widget.coordinator.backend_write_lock_title(), "Part extraction")
            with patch("AntSleap.ui.tif_workbench_coordinator.QMessageBox.information") as info:
                self.assertFalse(widget.coordinator.guard_backend_write_lock())
            info.assert_called_once()
        finally:
            widget.deleteLater()

    def test_coordinator_does_not_own_workflow_internal_state(self):
        source = (PROJECT_ROOT / "AntSleap" / "ui" / "tif_workbench_coordinator.py").read_text(encoding="utf-8")
        for forbidden in ("brush", "roi_keyframes", "mask_volume", "render_cache", "local_axis_draft", "result_compare"):
            self.assertNotIn(forbidden, source)
        self.assertLess(len(source.splitlines()), 300)


if __name__ == "__main__":
    unittest.main()
