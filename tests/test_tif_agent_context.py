import os
import sys
import tempfile
import unittest
from pathlib import Path


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

    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.core.tif_volume_io import write_volume_sidecar
    from AntSleap.ui.tif_workbench import TifWorkbenchWidget


@unittest.skipUnless(QApplication is not None, "PySide6 is required for TIF Agent context tests")
class TifAgentContextBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_volume_widget(self, root):
        manager = TifProjectManager()
        manager.create_project("agent_context", root / "agent_context")
        manager.create_specimen_scaffold("01-0101-21", modality="confocal")
        image = np.arange(5 * 8 * 8, dtype=np.uint8).reshape((5, 8, 8))
        edit = np.zeros((5, 8, 8), dtype=np.uint16)
        image_rel = "specimens/01-0101-21/working/image.ome.zarr"
        edit_rel = "specimens/01-0101-21/labels/working_edit.ome.zarr"
        image_meta = write_volume_sidecar(root / "agent_context" / image_rel, image, role="working_image")
        edit_meta = write_volume_sidecar(root / "agent_context" / edit_rel, edit, role="working_edit")
        manager.register_working_volume("01-0101-21", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
        manager.register_label_volume("01-0101-21", "working_edit", edit_rel, edit_meta["shape_zyx"], edit_meta["dtype"], save=True)
        widget = TifWorkbenchWidget(manager, "en")
        widget.render_current_slice()
        return widget

    def test_public_agent_context_entry_delegates_to_builder_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = self._make_volume_widget(Path(tmp))
            try:
                context = widget.get_agent_context()

                self.assertIs(widget.agent_context_builder.workbench, widget)
                self.assertEqual(context["source_workbench"], "tif_volume")
                self.assertEqual(context["project_type"], "tif_volume")
                self.assertEqual(context["active_specimen_id"], "01-0101-21")
                self.assertEqual(context["active_volume_shape_zyx"], "5/8/8")
                self.assertIn("annotation_training_loop", context["tif_next_requirement"])
                self.assertIn("tif_state_summary", context)
                self.assertIn("training_sample_rule", context)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
