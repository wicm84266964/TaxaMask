import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from tests.test_tif_backend import make_predict_ready_project, make_train_ready_project
    from AntSleap.core.tif_volume_io import write_volume_sidecar
    from AntSleap.ui.tif_workbench import TifWorkbenchWidget


@unittest.skipUnless(QApplication is not None, "PySide6 is required for result review controller tests")
class TifResultReviewControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_signals_are_bound_once_and_state_is_controller_owned(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = TifWorkbenchWidget(make_predict_ready_project(Path(tmp)), "en")
            try:
                controller = widget.result_review_controller
                self.assertEqual(widget.signal_router.connection_count("result_review"), 9)
                controller.bind_signals()
                self.assertEqual(widget.signal_router.connection_count("result_review"), 9)
                self.assertIs(widget._result_region_mask_cache, controller.state.region_mask_cache)
                controller.state.stale = False
                self.assertFalse(widget._result_comparison_stale)
                self.assertNotIn("_result_comparison_stale", widget.__dict__)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_open_selected_target_uses_selection_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = TifWorkbenchWidget(make_train_ready_project(Path(tmp)), "en")
            try:
                controller = widget.result_review_controller
                controller.selected_result_comparison_row = Mock(
                    return_value={"ref": {"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}, "ok": False}
                )
                selected = Mock(return_value=True)
                widget.selection_workflow_controller.select_payload = selected
                with patch.object(widget.volume_render_controller, "render_volume_preview"):
                    self.assertTrue(controller.open_selected_target())
                selected.assert_called_once_with(
                    {"specimen_id": "01-0101-11", "scope": "part_reslice", "part_id": "brain", "reslice_id": "brain_axis_001"}
                )
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_accept_selected_results_uses_truth_promotion_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = TifWorkbenchWidget(make_predict_ready_project(Path(tmp)), "en")
            try:
                controller = widget.result_review_controller
                ref = {"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}
                controller.selected_part_refs_for_review_acceptance = Mock(return_value=[ref])
                controller.split_review_acceptance_refs = Mock(return_value=([ref], [], []))
                result = Mock()
                result.__bool__ = Mock(return_value=True)
                result.payload = {"result": {"count": 1}}
                promote = Mock(return_value=result)
                widget.truth_promotion_service.promote_reviewed_refs = promote
                widget.refresh_project = Mock()
                widget.selection_workflow_controller.select_payload = Mock(return_value=True)
                with patch("AntSleap.ui.tif_result_review_controller.QMessageBox.question", return_value=QMessageBox.Yes):
                    self.assertTrue(controller.accept_selected_results())
                promote.assert_called_once_with([ref], require_opened_for_review=False, save=True)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_accept_selected_results_reports_atomic_batch_failure_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = TifWorkbenchWidget(make_predict_ready_project(Path(tmp)), "en")
            try:
                controller = widget.result_review_controller
                ref = {
                    "specimen_id": "01-0101-11",
                    "part_id": "brain",
                    "reslice_id": "brain_axis_001",
                }
                controller.selected_part_refs_for_review_acceptance = Mock(
                    return_value=[ref]
                )
                controller.split_review_acceptance_refs = Mock(
                    return_value=([ref], [], [])
                )
                widget.truth_promotion_service.promote_reviewed_refs = Mock(
                    side_effect=RuntimeError("synthetic_atomic_rollback")
                )
                with patch(
                    "AntSleap.ui.tif_result_review_controller.QMessageBox.question",
                    return_value=QMessageBox.Yes,
                ), patch(
                    "AntSleap.ui.tif_result_review_controller.QMessageBox.warning"
                ) as warning:
                    self.assertFalse(controller.accept_selected_results())

                message = warning.call_args.args[2]
                self.assertIn("01-0101-11:brain:brain_axis_001", message)
                self.assertIn("synthetic_atomic_rollback", message)
                self.assertIn("No selected AI results were accepted", message)
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_accept_selected_results_empty_selection_never_calls_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            widget = TifWorkbenchWidget(make_predict_ready_project(Path(tmp)), "en")
            try:
                controller = widget.result_review_controller
                controller.selected_part_refs_for_review_acceptance = Mock(
                    return_value=[]
                )
                promote = Mock(
                    side_effect=AssertionError("empty selection must not promote")
                )
                widget.truth_promotion_service.promote_reviewed_refs = promote
                with patch(
                    "AntSleap.ui.tif_result_review_controller.QMessageBox.warning"
                ) as warning:
                    self.assertFalse(controller.accept_selected_results())

                promote.assert_not_called()
                self.assertIn(
                    "No selected editable AI result",
                    warning.call_args.args[2],
                )
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_external_prediction_import_preserves_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget.selection_workflow_controller.select_payload(
                    {"specimen_id": "01-0101-11", "scope": "full", "part_id": "", "reslice_id": ""}
                )
                specimen = manager.get_specimen("01-0101-11")
                manual_before = dict((specimen.get("labels") or {}).get("manual_truth") or {})
                working = specimen.get("working_volume") or {}
                shape = tuple(working.get("shape_zyx") or ())
                tif_path = root / "external_prediction.tif"
                import tifffile
                tifffile.imwrite(tif_path, np.ones(shape, dtype=np.uint16))
                with patch("AntSleap.ui.tif_result_review_controller.QFileDialog.getOpenFileName", return_value=(str(tif_path), "")), \
                     patch("AntSleap.ui.tif_result_review_controller.QInputDialog.getText", side_effect=[("external_001", True), ("external_model", True)]):
                    widget.result_review_controller.import_external_prediction_dialog()
                specimen_after = manager.get_specimen("01-0101-11")
                self.assertEqual((specimen_after.get("labels") or {}).get("manual_truth") or {}, manual_before)
                self.assertTrue(((specimen_after.get("labels") or {}).get("working_edit") or {}).get("path"))
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_controller_has_no_cross_workflow_state_access(self):
        source = (PROJECT_ROOT / "AntSleap" / "ui" / "tif_result_review_controller.py").read_text(encoding="utf-8")
        self.assertNotIn("annotation_workflow_controller.state", source)
        self.assertNotIn("volume_render_controller.state", source)
        self.assertNotIn("backend_panel_controller.state", source)
        self.assertLess(len(source.splitlines()), 3000)


if __name__ == "__main__":
    unittest.main()
