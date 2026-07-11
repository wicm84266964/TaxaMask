import ast
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from AntSleap.ui.tif_roi_workflow_controller import TifRoiWorkflowController
    from AntSleap.ui.tif_workbench_signal_router import TifWorkbenchSignalRouter
    from AntSleap.ui.tif_workbench_view import TifWorkbenchView


@unittest.skipUnless(QApplication is not None, "PySide6 is required for ROI workflow tests")
class TifRoiWorkflowControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_workbench(self):
        workbench = SimpleNamespace(
            part_bbox_edit=QLineEdit(),
            btn_part_draw_roi=QPushButton(),
            btn_save_part_roi=QPushButton(),
            btn_confirm_part_roi=QPushButton(),
            btn_cancel_part_roi=QPushButton(),
            render_current_slice=Mock(),
        )
        workbench.btn_part_draw_roi.setCheckable(True)
        workbench.signal_router = TifWorkbenchSignalRouter()
        workbench.workbench_view = TifWorkbenchView(workbench)
        return workbench

    def test_bind_signals_is_idempotent_and_targets_roi_controller(self):
        workbench = self.make_workbench()
        controller = TifRoiWorkflowController(workbench)
        controller.initialize_compatibility_state()
        controller.save_draft = Mock(return_value=True)
        controller.confirm_to_part = Mock(return_value=True)
        controller.cancel_draft = Mock(return_value=True)

        controller.bind_signals()
        controller.bind_signals()
        workbench.btn_save_part_roi.click()
        workbench.btn_confirm_part_roi.click()
        workbench.btn_cancel_part_roi.click()

        self.assertEqual(workbench.signal_router.connection_count("roi_to_part"), 5)
        controller.save_draft.assert_called_once_with()
        controller.confirm_to_part.assert_called_once_with()
        controller.cancel_draft.assert_called_once_with()

    def test_controller_has_no_duplicate_method_definitions(self):
        source_path = Path(__file__).resolve().parents[1] / "AntSleap" / "ui" / "tif_roi_workflow_controller.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        controller_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TifRoiWorkflowController")
        names = [node.name for node in controller_class.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

        self.assertEqual(len(names), len(set(names)))

    def test_widget_does_not_own_roi_state_or_confirm_worker_fields(self):
        source_path = Path(__file__).resolve().parents[1] / "AntSleap" / "ui" / "tif_workbench.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        widget_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TifWorkbenchWidget")
        retired_methods = {
            "_cleanup_confirm_part_roi_thread",
            "_start_confirm_part_roi_worker",
            "_finish_confirm_part_roi_result",
            "confirm_part_roi_to_part",
            "save_part_roi_draft",
            "cancel_part_roi_draft",
            "_load_roi_draft_for_editing",
            "open_roi_at_widget_position",
            "_ensure_roi_for_created_part",
        }
        method_names = {node.name for node in widget_class.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        forbidden_fields = {
            "active_part_roi_id",
            "part_roi_keyframes",
            "part_roi_draw_mode",
            "_confirm_part_roi_thread",
            "_confirm_part_roi_worker",
            "_confirm_part_roi_progress",
            "_confirm_part_roi_task_id",
            "_confirm_part_roi_request",
        }
        assigned_fields = {
            target.attr
            for node in ast.walk(widget_class)
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign))
            for target in ((node.targets if isinstance(node, ast.Assign) else [node.target]))
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self"
        }

        self.assertFalse(method_names & retired_methods)
        self.assertFalse(assigned_fields & forbidden_fields)


    def test_roi_controller_uses_part_mask_commands_not_internal_state(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "AntSleap" / "ui" / "tif_roi_workflow_controller.py").read_text(encoding="utf-8")

        self.assertNotIn("part_mask_workflow_controller.state", source)
        self.assertIn("part_mask_workflow_controller.load_roi_draft_keyframes", source)
        self.assertIn("part_mask_workflow_controller.clear_roi_draft_keyframes", source)

    def test_load_draft_routes_mask_keyframes_through_part_mask_command(self):
        workbench = self.make_workbench()
        workbench.image_volume = None
        workbench._bbox_text = Mock(return_value="0:1,0:2,0:3")
        workbench.part_mask_workflow_controller = SimpleNamespace(load_roi_draft_keyframes=Mock())
        controller = TifRoiWorkflowController(workbench)
        roi = {
            "roi_id": "head-roi",
            "bbox_zyx": [[0, 1], [0, 2], [0, 3]],
            "metadata": {"roi_keyframes": [], "part_mask_keyframes": [{"axis": "z", "slice_index": 0}]},
        }

        controller.load_draft(roi)

        workbench.part_mask_workflow_controller.load_roi_draft_keyframes.assert_called_once_with(
            [{"axis": "z", "slice_index": 0}]
        )
        self.assertEqual(controller.state.active_roi_id, "head-roi")

    def test_stale_confirm_completion_refreshes_tree_without_reloading_current_view(self):
        workbench = self.make_workbench()
        workbench.lang = "en"
        workbench._task_context_matches_current = Mock(return_value=False)
        workbench._progress_tif_task = Mock()
        workbench._finish_tif_task = Mock()
        workbench._set_scope_controls_enabled = Mock()
        workbench.refresh_project = Mock()
        workbench.log = Mock()
        workbench.training_status_label = SimpleNamespace(setText=Mock())
        controller = TifRoiWorkflowController(workbench)
        controller.state.confirm_task_id = "roi-task"
        controller.confirm_thread = SimpleNamespace(quit=Mock())
        controller.confirm_progress = Mock()
        controller.finish_confirm_result = Mock()

        controller.on_confirm_progress(1, 2, "old ROI progress")
        controller.on_confirm_finished({"specimen_id": "s1", "part_id": "head"})

        workbench.refresh_project.assert_called_once_with(reload_current=False)
        controller.finish_confirm_result.assert_not_called()
        workbench.training_status_label.setText.assert_not_called()
        workbench.log.assert_called_once()

if __name__ == "__main__":
    unittest.main()
