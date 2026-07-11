import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QTreeWidget
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from AntSleap.services.tif_selection_controller import TifSelectionController
    from AntSleap.ui.tif_selection_workflow_controller import TifSelectionWorkflowController
    from AntSleap.ui.tif_workbench_signal_router import TifWorkbenchSignalRouter
    from AntSleap.ui.tif_workbench_view import TifWorkbenchView


@unittest.skipUnless(QApplication is not None, "PySide6 is required for selection workflow tests")
class TifSelectionWorkflowControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_workbench(self):
        workbench = SimpleNamespace()
        workbench.specimen_list = QTreeWidget()
        workbench.selection_controller = TifSelectionController()
        workbench.signal_router = TifWorkbenchSignalRouter()
        workbench.workbench_view = TifWorkbenchView(workbench)
        workbench.current_specimen_id = ""
        workbench.current_volume_scope = "full"
        workbench.current_part_id = ""
        workbench.current_reslice_id = ""
        workbench.display_mode = "slice"
        workbench.label_role_combo = SimpleNamespace(currentData=lambda: "working_edit")
        workbench.load_specimen = Mock()

        def load_part(specimen_id, part_id, selected_reslice_id=""):
            workbench.current_specimen_id = specimen_id
            workbench.current_volume_scope = "part"
            workbench.current_part_id = part_id
            workbench.current_reslice_id = selected_reslice_id

        workbench.load_part = Mock(side_effect=load_part)
        workbench._on_specimen_tree_context_menu = Mock()
        return workbench

    def test_select_payload_routes_part_and_updates_selection_state(self):
        workbench = self.make_workbench()
        controller = TifSelectionWorkflowController(workbench)

        controller.select_payload({"scope": "part_reslice", "specimen_id": "s1", "part_id": "head", "reslice_id": "r1"})

        workbench.load_part.assert_called_once_with("s1", "head", selected_reslice_id="r1")
        self.assertEqual(workbench.selection_controller.state.context_key()[:4], ("s1", "part", "head", "r1"))

    def test_bind_signals_is_idempotent_and_targets_controller(self):
        workbench = self.make_workbench()
        controller = TifSelectionWorkflowController(workbench)

        controller.bind_signals()
        controller.bind_signals()

        self.assertEqual(workbench.signal_router.connection_count("selection"), 2)

    def test_clear_state_resets_widget_mirror_and_service_state(self):
        workbench = self.make_workbench()
        workbench.current_specimen_id = "s1"
        workbench.current_volume_scope = "part"
        workbench.current_part_id = "head"
        workbench.current_reslice_id = "r1"
        controller = TifSelectionWorkflowController(workbench)

        controller.clear_state()

        self.assertEqual(workbench.current_specimen_id, "")
        self.assertEqual(workbench.current_volume_scope, "full")
        self.assertEqual(workbench.selection_controller.state.context_key()[:4], ("", "full", "", ""))


    def test_selection_events_share_one_context_snapshot(self):
        workbench = self.make_workbench()
        events = []
        workbench.workbench_shell = SimpleNamespace(
            notify_controllers=lambda hook, payload: events.append((hook, dict(payload)))
        )
        controller = TifSelectionWorkflowController(workbench)

        controller.select_payload({"scope": "part_reslice", "specimen_id": "s1", "part_id": "head", "reslice_id": "r1"})

        self.assertEqual(events[0], ("on_selection_changing", {"specimen_id": "s1", "volume_scope": "part", "part_id": "head", "reslice_id": "r1"}))
        self.assertEqual(events[1][0], "on_selection_changed")
        self.assertEqual(events[1][1]["specimen_id"], "s1")
        self.assertEqual(events[1][1]["part_id"], "head")
        self.assertEqual(events[1][1]["reslice_id"], "r1")

    def test_selection_uses_annotation_public_unsaved_query(self):
        source = (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "AntSleap"
            / "ui"
            / "tif_selection_workflow_controller.py"
        ).read_text(encoding="utf-8")

        self.assertIn("annotation_workflow_controller.has_unsaved_changes()", source)
        self.assertNotIn("annotation_workflow_controller.state", source)

    def test_widget_context_properties_share_selection_state(self):
        from AntSleap.core.tif_project import TifProjectManager
        from AntSleap.ui.tif_workbench import TifWorkbenchWidget

        widget = TifWorkbenchWidget(TifProjectManager(), "en")
        try:
            widget.current_specimen_id = "s2"
            widget.current_volume_scope = "part"
            widget.current_part_id = "thorax"
            widget.current_reslice_id = "r2"

            state = widget.selection_controller.state
            self.assertEqual(state.context_key()[:4], ("s2", "part", "thorax", "r2"))
            self.assertNotIn("current_specimen_id", widget.__dict__)
            self.assertNotIn("current_volume_scope", widget.__dict__)
            self.assertNotIn("current_part_id", widget.__dict__)
            self.assertNotIn("current_reslice_id", widget.__dict__)
        finally:
            widget.close_project(prompt_unsaved=False)
            widget.deleteLater()

if __name__ == "__main__":
    unittest.main()
