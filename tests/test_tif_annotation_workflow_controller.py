import os
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton, QSlider
    from PySide6.QtGui import QShortcut
    from PySide6.QtCore import Qt
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from AntSleap.ui.tif_annotation_workflow_controller import TifAnnotationWorkflowController
    from AntSleap.ui.tif_workbench_signal_router import TifWorkbenchSignalRouter
    from AntSleap.ui.tif_workbench_view import TifWorkbenchView


@unittest.skipUnless(QApplication is not None, "PySide6 is required for annotation workflow tests")
class TifAnnotationWorkflowControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_workbench(self):
        workbench = SimpleNamespace()
        for name in (
            "btn_tool_brush", "btn_tool_eraser", "btn_tool_lasso", "btn_tool_rectangle",
            "btn_tool_ellipse", "btn_tool_picker", "btn_tool_pan", "btn_undo", "btn_redo",
            "btn_save_edit", "btn_promote", "btn_interpolate_current_label",
        ):
            setattr(workbench, name, QPushButton(name))
        workbench.brush_size_slider = QSlider(Qt.Horizontal)
        workbench.brush_size_slider.setRange(1, 100)
        workbench.brush_size_slider.setValue(10)
        workbench.auto_save_check = QCheckBox()
        for name in (
            "shortcut_undo", "shortcut_redo", "shortcut_redo_alt", "shortcut_save_edit",
            "shortcut_tool_brush", "shortcut_tool_eraser", "shortcut_tool_lasso",
            "shortcut_tool_rectangle", "shortcut_tool_ellipse", "shortcut_tool_picker",
            "shortcut_brush_smaller", "shortcut_brush_larger",
        ):
            setattr(workbench, name, QShortcut(workbench.btn_tool_brush))
        workbench.signal_router = TifWorkbenchSignalRouter()
        workbench.workbench_view = TifWorkbenchView(workbench)
        workbench.undo = Mock()
        workbench.redo = Mock()
        workbench.save_working_edit_async = Mock()
        workbench.promote_working_edit = Mock()
        workbench._annotation_tool_modes = Mock(return_value=("brush", "eraser", "lasso", "rectangle", "ellipse", "picker", "pan"))
        workbench._sync_annotation_tool_buttons = Mock()
        workbench._set_operation_feedback = Mock()
        workbench.coordinator = SimpleNamespace(
            backend_write_lock_active=Mock(return_value=False),
            backend_write_lock_message=Mock(return_value="locked"),
            guard_backend_write_lock=Mock(return_value=True),
        )
        workbench._invalidate_result_region_mask_cache = Mock()
        workbench._update_save_status = Mock()
        workbench.auto_save_timer = Mock()
        workbench.canvas = SimpleNamespace(_refresh_scaled_pixmap=Mock())
        workbench.lang = "en"
        workbench.current_volume_scope = "top_level"
        return workbench

    def test_revision_match_preserves_later_same_slice_edit(self):
        workbench = self.make_workbench()
        controller = TifAnnotationWorkflowController(workbench)
        controller.initialize_compatibility_state()
        controller.mark_slice_dirty(4)
        saved_revision = controller.state.slice_revisions[4]
        controller.mark_slice_dirty(4)

        controller.clear_saved_slices({4: saved_revision})

        self.assertTrue(controller.state.dirty)
        self.assertIn(4, controller.state.dirty_slices)
        self.assertTrue(controller.state.dirty)

    def test_bind_signals_is_idempotent_and_tool_button_targets_controller(self):
        workbench = self.make_workbench()
        controller = TifAnnotationWorkflowController(workbench)
        controller.initialize_compatibility_state()
        controller.save_async = Mock(return_value=True)

        controller.bind_signals()
        controller.bind_signals()
        workbench.btn_tool_eraser.click()

        self.assertEqual(workbench.signal_router.connection_count("annotation"), 26)
        self.assertEqual(controller.state.tool_mode, "eraser")

        workbench.btn_save_edit.click()
        controller.save_async.assert_called_once_with()

    def test_write_lock_blocks_dirty_transition(self):
        workbench = self.make_workbench()
        workbench.coordinator.backend_write_lock_active.return_value = True
        controller = TifAnnotationWorkflowController(workbench)
        controller.initialize_compatibility_state()

        controller.mark_working_edit_dirty()

        self.assertFalse(controller.state.dirty)
        workbench._invalidate_result_region_mask_cache.assert_not_called()

    def test_selection_is_blocked_while_manual_save_is_running(self):
        workbench = self.make_workbench()
        controller = TifAnnotationWorkflowController(workbench)
        controller.initialize_compatibility_state()
        controller.manual_save_thread = object()

        self.assertFalse(controller.confirm_discard_or_save())

        workbench._set_operation_feedback.assert_called_once()
        workbench._update_save_status.assert_called_once_with(state="saving")
        workbench.auto_save_timer.stop.assert_not_called()

    def test_stale_manual_save_failure_does_not_mark_new_view_dirty(self):
        workbench = self.make_workbench()
        workbench._fail_tif_task = Mock()
        workbench._cancel_tif_task = Mock()
        workbench._set_scope_controls_enabled = Mock()
        workbench._pending_backend_action_after_save = {"action": "train"}
        workbench.log = Mock()
        controller = TifAnnotationWorkflowController(workbench)
        controller.initialize_compatibility_state()
        controller.manual_save_token = 7
        controller.manual_save_task_id = "save-7"
        controller.manual_save_thread = object()
        controller.result_matches_current_view = Mock(return_value=False)

        with patch("AntSleap.ui.tif_annotation_workflow_controller.QMessageBox.warning") as warning_mock:
            controller.on_manual_save_failed(
                {
                    "token": 7,
                    "error": "disk full",
                    "context": {"specimen_id": "s1", "part_id": "head", "reslice_id": "axis-1"},
                }
            )

        self.assertFalse(controller.state.dirty)
        workbench._fail_tif_task.assert_called_once_with("save-7", "disk full", payload=ANY)
        workbench._update_save_status.assert_not_called()
        workbench.log.assert_called_once()
        warning_mock.assert_called_once()
        self.assertIsNone(workbench._pending_backend_action_after_save)

    def test_stale_truth_promotion_refreshes_tree_without_reloading_current_view(self):
        workbench = self.make_workbench()
        workbench._task_context_matches_current = Mock(return_value=False)
        workbench._finish_tif_task = Mock()
        workbench._set_scope_controls_enabled = Mock()
        workbench.refresh_project = Mock()
        workbench.selection_workflow_controller = SimpleNamespace(select_payload=Mock())
        controller = TifAnnotationWorkflowController(workbench)
        controller.initialize_compatibility_state()
        controller.promote_task_id = "promote-1"
        controller.promote_thread = object()

        controller.on_promote_finished(
            {"specimen_id": "s1", "part_id": "head", "reslice_id": "axis-1"}
        )

        workbench.refresh_project.assert_called_once_with(reload_current=False)
        workbench.selection_workflow_controller.select_payload.assert_not_called()
        self.assertIn("left unchanged", workbench._set_operation_feedback.call_args.args[0])

    def test_controller_has_no_duplicate_method_definitions(self):
        source_path = Path(__file__).resolve().parents[1] / "AntSleap" / "ui" / "tif_annotation_workflow_controller.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        controller_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TifAnnotationWorkflowController")
        names = [node.name for node in controller_class.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

        self.assertEqual(len(names), len(set(names)))


    def test_widget_and_shell_do_not_store_annotation_state_copies(self):
        root = Path(__file__).resolve().parents[1]
        widget_source = (root / "AntSleap" / "ui" / "tif_workbench.py").read_text(encoding="utf-8")
        shell_source = (root / "AntSleap" / "ui" / "tif_workbench_shell.py").read_text(encoding="utf-8")
        controller_source = (root / "AntSleap" / "ui" / "tif_annotation_workflow_controller.py").read_text(encoding="utf-8")

        for name in (
            "working_edit_dirty",
            "_dirty_edit_slices",
            "_edit_slice_revisions",
            "undo_stack",
            "redo_stack",
            "_label_auto_save_thread",
            "_label_manual_save_thread",
            "_promote_thread",
        ):
            self.assertNotIn(f'"{name}":', shell_source)
        self.assertNotIn("workbench.working_edit_dirty =", controller_source)
        self.assertNotIn("workbench._dirty_edit_slices =", controller_source)
        self.assertNotIn("workbench.undo_stack =", controller_source)
        self.assertNotIn("workbench._label_auto_save_thread =", controller_source)
        self.assertIn("working_edit_dirty = _controller_state_property(\"annotation_workflow_controller\", \"dirty\", bool)", widget_source)
        self.assertIn("_label_auto_save_thread = _controller_attribute_property(\"annotation_workflow_controller\", \"auto_save_thread\")", widget_source)

if __name__ == "__main__":
    unittest.main()
