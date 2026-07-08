import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_tif_backend import make_predict_ready_project, make_top_level_only_project, make_train_ready_project

from AntSleap.services.tif_backend_workflow_service import TifBackendWorkflowService


class TifBackendWorkflowServiceTests(unittest.TestCase):
    def test_training_prefers_train_ready_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_train_ready_project(Path(tmp))
            service = TifBackendWorkflowService(manager)

            result = service.selected_backend_samples_for_action("train")

            self.assertTrue(result.ok)
            self.assertEqual(result.payload["input_scope"], "part_reslice")
            self.assertEqual(result.payload["part_refs"][0]["part_id"], "brain")

    def test_training_selection_defers_expensive_part_label_id_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_train_ready_project(Path(tmp))
            service = TifBackendWorkflowService(manager)

            with patch.object(manager, "validate_part_label_ids", side_effect=AssertionError("label scan should be deferred")):
                result = service.selected_backend_samples_for_action(
                    "prepare_dataset",
                    current_volume_scope="part",
                    current_specimen_id="01-0101-11",
                    current_part_id="brain",
                    current_reslice_id="brain_axis_001",
                )

            self.assertTrue(result.ok)
            self.assertEqual(result.payload["input_scope"], "part_reslice")
            self.assertEqual(result.payload["part_refs"], [{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}])

    def test_predict_can_fall_back_to_top_level_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_top_level_only_project(Path(tmp))
            service = TifBackendWorkflowService(manager)

            result = service.selected_backend_samples_for_action("predict", current_specimen_id="top-001")

            self.assertTrue(result.ok)
            self.assertEqual(result.payload["input_scope"], "top_level_volume")
            self.assertEqual(result.payload["specimen_ids"], ["top-001"])

    def test_predict_part_refs_are_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_predict_ready_project(Path(tmp))
            service = TifBackendWorkflowService(manager)

            result = service.selected_backend_samples_for_action(
                "predict",
                selected_predict_refs=[{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}],
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.payload["input_scope"], "part_reslice")


if __name__ == "__main__":
    unittest.main()
