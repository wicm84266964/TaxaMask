import unittest

from AntSleap.core.tif_status_display import (
    format_train_ready_reasons,
    part_has_model_source,
    review_status_label,
    system_status_label,
)


class TifStatusDisplayTests(unittest.TestCase):
    def test_predicted_pending_review_is_not_called_prediction_without_model_source(self):
        self.assertEqual(
            system_status_label("predicted_pending_review", has_model_source=False),
            "editable result pending review",
        )
        self.assertEqual(
            system_status_label("predicted_pending_review", has_model_source=True),
            "prediction pending review",
        )

    def test_unknown_status_is_not_completed(self):
        self.assertEqual(review_status_label("mystery"), "unrecognized status")
        self.assertEqual(system_status_label("mystery"), "unrecognized status")

    def test_reason_keys_are_readable(self):
        reasons = format_train_ready_reasons(["manual_truth_missing", "part_not_marked_train_ready"])
        self.assertTrue(any("Training truth is missing" in item for item in reasons))

    def test_part_model_source_uses_backup_path(self):
        part = {"labels": {"raw_ai_prediction_backup": {"path": "pred.tif"}}}
        self.assertTrue(part_has_model_source(part))
        self.assertFalse(part_has_model_source({"labels": {"working_edit": {"path": "edit.tif"}}}))
