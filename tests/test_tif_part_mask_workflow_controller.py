import ast
import os
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from AntSleap.ui.tif_part_mask_workflow_controller import TifPartMaskWorkflowController
    from AntSleap.ui.tif_workbench_signal_router import TifWorkbenchSignalRouter
    from AntSleap.ui.tif_workbench_view import TifWorkbenchView


@unittest.skipUnless(QApplication is not None, "PySide6 is required for part mask workflow tests")
class TifPartMaskWorkflowControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_workbench(self):
        workbench = SimpleNamespace()
        for name in (
            "btn_copy_material_prev",
            "btn_copy_material_next",
            "btn_clear_current_material",
            "btn_draw_part_contour",
            "btn_add_rect_keyframe",
            "btn_delete_part_contour",
            "btn_clear_part_keyframes",
            "btn_prev_key_slice",
            "btn_next_key_slice",
            "btn_preview_part_mask",
            "btn_accept_part_mask",
            "btn_clear_part_preview",
            "btn_add_material",
            "btn_edit_material",
            "btn_delete_material",
        ):
            setattr(workbench, name, QPushButton(name))
        workbench.btn_draw_part_contour.setCheckable(True)
        workbench.material_table = QTableWidget()
        workbench.signal_router = TifWorkbenchSignalRouter()
        workbench.workbench_view = TifWorkbenchView(workbench)
        return workbench

    def test_bind_signals_is_idempotent_and_targets_controller(self):
        workbench = self.make_workbench()
        controller = TifPartMaskWorkflowController(workbench)
        controller.preview_part_mask_from_keyframes = Mock()
        controller.accept_part_mask_preview = Mock()
        controller.clear_part_mask_preview = Mock()
        controller.add_material = Mock()

        controller.bind_signals()
        controller.bind_signals()
        workbench.btn_preview_part_mask.click()
        workbench.btn_accept_part_mask.click()
        workbench.btn_clear_part_preview.click()
        workbench.btn_add_material.click()

        self.assertEqual(workbench.signal_router.connection_count("part_mask_material"), 16)
        controller.preview_part_mask_from_keyframes.assert_called_once_with()
        controller.accept_part_mask_preview.assert_called_once_with()
        controller.clear_part_mask_preview.assert_called_once_with()
        controller.add_material.assert_called_once_with()

    def test_preview_state_is_distinct_from_accepted_and_editable_mask(self):
        controller = TifPartMaskWorkflowController(self.make_workbench())
        preview = object()
        editable = object()
        controller.state.preview_mask = preview
        controller.state.preview_accepted = False
        controller.state.part_mask_volume = editable

        self.assertIs(controller.state.preview_mask, preview)
        self.assertFalse(controller.state.preview_accepted)
        self.assertIs(controller.state.part_mask_volume, editable)

    def test_stale_preview_token_does_not_replace_newer_state(self):
        workbench = self.make_workbench()
        workbench._cancel_tif_task = Mock()
        workbench._task_context_matches_current = Mock(return_value=True)
        workbench._set_scope_controls_enabled = Mock()
        controller = TifPartMaskWorkflowController(workbench)
        controller.state.preview_token = 2
        controller.state.preview_mask = "newer"

        controller._on_part_mask_preview_finished({"token": 1, "mask": "stale", "context": {}})

        self.assertEqual(controller.state.preview_mask, "newer")

    def test_cancel_and_wait_preview_cancels_worker_and_releases_thread(self):
        workbench = self.make_workbench()
        workbench._set_scope_controls_enabled = Mock()
        workbench._cancel_tif_task = Mock()
        controller = TifPartMaskWorkflowController(workbench)
        worker = SimpleNamespace(cancel=Mock())
        thread = SimpleNamespace(quit=Mock(), wait=Mock(), isRunning=Mock(return_value=False))
        controller.preview_worker = worker
        controller.preview_thread = thread
        controller.state.preview_task_id = "mask-preview-1"

        self.assertTrue(controller.cancel_and_wait_preview(timeout_ms=321))

        worker.cancel.assert_called_once_with()
        thread.quit.assert_called_once_with()
        thread.wait.assert_called_once_with(321)
        workbench._cancel_tif_task.assert_called_once_with("mask-preview-1", "part_mask_preview_cancelled")
        self.assertIsNone(controller.preview_worker)
        self.assertIsNone(controller.preview_thread)
        workbench._set_scope_controls_enabled.assert_called_once_with()

    def test_cancel_and_wait_preview_keeps_running_thread_tracked(self):
        workbench = self.make_workbench()
        workbench._set_scope_controls_enabled = Mock()
        workbench._cancel_tif_task = Mock()
        controller = TifPartMaskWorkflowController(workbench)
        worker = SimpleNamespace(cancel=Mock())
        thread = SimpleNamespace(quit=Mock(), wait=Mock(return_value=False), isRunning=Mock(return_value=True))
        controller.preview_worker = worker
        controller.preview_thread = thread
        controller.state.preview_task_id = "mask-preview-2"

        self.assertFalse(controller.cancel_and_wait_preview(timeout_ms=25))

        self.assertIs(controller.preview_worker, worker)
        self.assertIs(controller.preview_thread, thread)
        workbench._cancel_tif_task.assert_called_once_with("mask-preview-2", "part_mask_preview_cancelled")
        workbench._set_scope_controls_enabled.assert_not_called()

    def test_stale_materialize_completion_does_not_reload_or_overwrite_current_view(self):
        workbench = self.make_workbench()
        workbench.lang = "en"
        workbench._task_context_matches_current = Mock(return_value=False)
        workbench._finish_tif_task = Mock()
        workbench.refresh_project = Mock()
        workbench.selection_workflow_controller = SimpleNamespace(select_payload=Mock())
        workbench.training_status_label = SimpleNamespace(setText=Mock())
        workbench.log = Mock()
        controller = TifPartMaskWorkflowController(workbench)
        controller.materialize_specimen_id = "s1"
        controller.materialize_task_id = "materialize-1"
        controller.materialize_thread = SimpleNamespace(quit=Mock())

        controller._on_tif_materialize_finished({"report_path": "report.json"})

        workbench.refresh_project.assert_called_once_with(reload_current=False)
        workbench.selection_workflow_controller.select_payload.assert_not_called()
        workbench.training_status_label.setText.assert_not_called()
        workbench.log.assert_called_once()

    def test_stale_materialize_failure_is_logged_without_unrelated_dialog(self):
        workbench = self.make_workbench()
        workbench.lang = "en"
        workbench._task_context_matches_current = Mock(return_value=False)
        workbench._fail_tif_task = Mock()
        workbench.refresh_project = Mock()
        workbench.selection_workflow_controller = SimpleNamespace(select_payload=Mock())
        workbench.log = Mock()
        controller = TifPartMaskWorkflowController(workbench)
        controller.materialize_specimen_id = "s1"
        controller.materialize_task_id = "materialize-1"
        controller.materialize_thread = SimpleNamespace(quit=Mock())

        with patch("AntSleap.ui.tif_part_mask_workflow_controller.QMessageBox.critical") as critical_mock:
            controller._on_tif_materialize_failed("disk full")

        workbench.refresh_project.assert_called_once_with(reload_current=False)
        workbench.selection_workflow_controller.select_payload.assert_not_called()
        workbench.log.assert_called_once()
        critical_mock.assert_not_called()

    def test_roi_draft_commands_clear_preview_without_touching_accepted_mask(self):
        workbench = self.make_workbench()
        workbench.image_volume = SimpleNamespace(shape=(4, 8, 8))
        workbench._safe_contour_slice_index = lambda item, _default: item.get("slice_index")
        controller = TifPartMaskWorkflowController(workbench)
        accepted_mask = object()
        controller.state.part_mask_volume = accepted_mask
        controller.state.preview_mask = object()
        controller.state.preview_bbox = [0, 0, 0, 1, 1, 1]
        controller.state.preview_accepted = True
        keyframe = {
            "axis": "z",
            "slice_index": 1,
            "polygon": [[1, 1], [5, 1], [5, 5], [1, 5]],
            "source": "roi_shell",
        }

        loaded = controller.load_roi_draft_keyframes([keyframe])

        self.assertEqual(len(loaded), 1)
        self.assertIsNone(controller.state.preview_mask)
        self.assertEqual(controller.state.preview_bbox, [])
        self.assertFalse(controller.state.preview_accepted)
        self.assertIs(controller.state.part_mask_volume, accepted_mask)

        controller.clear_roi_draft_keyframes()

        self.assertEqual(controller.state.keyframes, [])
        self.assertIs(controller.state.part_mask_volume, accepted_mask)

    def test_part_mask_voxel_check_uses_controller_owned_mask(self):
        controller = TifPartMaskWorkflowController(self.make_workbench())
        controller.state.part_mask_volume = np.zeros((3, 4, 5), dtype=np.uint16)
        self.assertFalse(controller._part_mask_has_voxels())

        controller.state.part_mask_volume[2, 3, 4] = 7
        self.assertTrue(controller._part_mask_has_voxels())

    def test_background_and_used_materials_are_guarded_from_deletion(self):
        workbench = self.make_workbench()
        workbench.current_volume_scope = "full"
        workbench.lang = "en"
        controller = TifPartMaskWorkflowController(workbench)
        controller._save_material_map = Mock()

        controller._selected_material = Mock(return_value={"id": 0, "name": "background"})
        with patch("AntSleap.ui.tif_part_mask_workflow_controller.QMessageBox.warning") as warning:
            controller.delete_selected_material()
        warning.assert_called_once()
        controller._save_material_map.assert_not_called()

        controller._selected_material = Mock(return_value={"id": 3, "name": "setae"})
        controller._material_id_is_used = Mock(return_value=True)
        with patch("AntSleap.ui.tif_part_mask_workflow_controller.QMessageBox.warning") as warning:
            controller.delete_selected_material()
        warning.assert_called_once()
        controller._save_material_map.assert_not_called()

    def test_controller_has_no_duplicate_method_definitions(self):
        source_path = Path(__file__).resolve().parents[1] / "AntSleap" / "ui" / "tif_part_mask_workflow_controller.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        controller_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TifPartMaskWorkflowController")
        names = [node.name for node in controller_class.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

        self.assertEqual(len(names), len(set(names)))
        self.assertIsNone(re.search(r"workbench\.workbench\b", source_path.read_text(encoding="utf-8")))

    def test_widget_does_not_assign_part_mask_state_or_worker_fields(self):
        source_path = Path(__file__).resolve().parents[1] / "AntSleap" / "ui" / "tif_workbench.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        widget_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TifWorkbenchWidget")
        forbidden_fields = {
            "part_preview_mask",
            "part_mask_preview_bbox",
            "part_mask_preview_accepted",
            "part_mask_keyframes",
            "part_contour_draw_mode",
            "part_mask_volume",
            "material_map",
            "material_colors",
            "current_material_id",
            "_part_mask_preview_thread",
            "_part_mask_preview_worker",
            "_part_mask_preview_progress",
            "_tif_materialize_thread",
            "_tif_materialize_worker",
            "_tif_materialize_progress",
        }
        assigned_fields = {
            target.attr
            for node in ast.walk(widget_class)
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign))
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self"
        }

        self.assertFalse(assigned_fields & forbidden_fields)


if __name__ == "__main__":
    unittest.main()
