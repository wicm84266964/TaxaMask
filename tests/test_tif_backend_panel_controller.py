import json
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
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from tests.test_tif_backend import make_predict_ready_project, make_train_ready_project

    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.ui.tif_workbench import TifWorkbenchWidget


@unittest.skipUnless(QApplication is not None, "PySide6 is required for TIF backend panel controller tests")
class TifBackendPanelControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_predict_target_table_uses_service_readiness_and_preserves_tuple_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_predict_ready_project(Path(tmp))
            manager.upsert_part_user_tag("round_1", "Round 1", order_index=0, save=False)
            manager.set_part_user_tags("01-0101-11", "brain", ["round_1"], save=True)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                controller = widget.backend_panel_controller
                widget.refresh_predict_targets()

                self.assertGreaterEqual(widget.predict_targets_table.rowCount(), 1)
                self.assertEqual(widget.predict_targets_table.item(0, 6).text(), "Ready")
                self.assertIn("Round 1", widget.predict_targets_table.item(0, 4).text())

                widget.select_all_ready_predict_targets()

                expected_key = ("01-0101-11", "brain", "brain_axis_001")
                self.assertIn(expected_key, widget._tif_predict_selected_refs)
                self.assertEqual(
                    controller.selected_backend_samples_for_action("predict"),
                    {
                        "input_scope": "part_reslice",
                        "part_refs": [{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}],
                        "specimen_ids": [],
                        "fallback_reason": "",
                    },
                )
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_training_selection_still_uses_backend_workflow_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_train_ready_project(Path(tmp))
            widget = TifWorkbenchWidget(manager, "en")
            try:
                selection = widget.backend_panel_controller.selected_backend_samples_for_action("train")

                self.assertEqual(selection["input_scope"], "part_reslice")
                self.assertEqual(selection["part_refs"][0]["part_id"], "brain")
                self.assertEqual(selection["specimen_ids"], [])
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_model_library_controls_require_existing_manifest_and_not_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            manager = TifProjectManager()
            manager.create_project("model_library", project_root)
            outputs = project_root / "runs" / "train" / "outputs"
            outputs.mkdir(parents=True)
            manifest = outputs / "model_manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "ant3d_tif_model_manifest_v1",
                        "model_id": "taxamask_tif_nnunet_v2_backend/train_model_library",
                        "backend_id": "taxamask_tif_nnunet_v2_backend",
                        "model_family": "nnunet_v2_tif_region",
                        "created_at": "2026-07-07T12:00:00+08:00",
                        "trained_specimens": ["s1", "s2"],
                        "trained_parts": [{"specimen_id": "s1", "part_id": "head"}],
                        "input_scope": "part_reslice",
                        "label_schema_ids": ["head_regions"],
                        "nnunet": {"model_output_dir": str(outputs)},
                        "usable_for_research_prediction": True,
                    }
                ),
                encoding="utf-8",
            )
            manager.register_tif_segmentation_model_from_manifest(manifest, {"training_samples": 2}, save=True)
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget._populate_tif_model_library_combo("taxamask_tif_nnunet_v2_backend/train_model_library")

                self.assertTrue(widget.btn_use_selected_tif_model.isEnabled())
                self.assertTrue(widget.btn_save_tif_model_notes.isEnabled())
                self.assertTrue(widget.btn_delete_tif_model_record.isEnabled())
                self.assertIn("Samples: 2", widget.model_library_summary_label.text())

                widget._tif_backend_thread = object()
                widget._set_backend_controls_running(True)
                self.assertFalse(widget.btn_use_selected_tif_model.isEnabled())
                self.assertFalse(widget.btn_save_tif_model_notes.isEnabled())
                self.assertFalse(widget.btn_delete_tif_model_record.isEnabled())
            finally:
                widget._tif_backend_thread = None
                widget._tif_backend_worker = None
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

    def test_training_result_controls_lock_during_backend_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_output = root / "model_output"
            model_output.mkdir()
            manifest = model_output / "model_manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            manager = TifProjectManager()
            widget = TifWorkbenchWidget(manager, "en")
            try:
                widget._set_training_result_summary(
                    {
                        "model_output": str(model_output),
                        "model_manifest": str(manifest),
                        "metrics": [("dice", "0.8")],
                        "curves": [],
                        "previews": [],
                    }
                )

                self.assertTrue(widget.btn_show_training_result_summary.isEnabled())
                self.assertTrue(widget.btn_open_training_model_output.isEnabled())
                self.assertTrue(widget.btn_open_training_model_manifest.isEnabled())
                self.assertTrue(widget.btn_batch_predict_entry.isEnabled())

                widget._tif_backend_thread = object()
                widget._set_backend_controls_running(True)

                self.assertFalse(widget.btn_show_training_result_summary.isEnabled())
                self.assertFalse(widget.btn_open_training_model_output.isEnabled())
                self.assertFalse(widget.btn_open_training_model_manifest.isEnabled())
                self.assertFalse(widget.btn_batch_predict_entry.isEnabled())
                self.assertIn("Training result is ready", widget.training_result_summary_label.text())
            finally:
                widget._tif_backend_thread = None
                widget._tif_backend_worker = None
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
