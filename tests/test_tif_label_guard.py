import unittest

from AntSleap.core.tif_label_guard import (
    can_write_label_role,
    require_editable_label_role,
)


class TifLabelGuardTests(unittest.TestCase):
    def test_label_role_write_matrix_protects_truth_and_raw_backup(self):
        self.assertTrue(can_write_label_role("working_edit", operation="manual_save"))
        self.assertTrue(can_write_label_role("editable_ai_result", operation="prediction_review_import"))

        raw_edit = can_write_label_role("raw_ai_prediction_backup", operation="manual_save")
        self.assertFalse(raw_edit.allowed)
        self.assertEqual(raw_edit.reason, "raw_ai_prediction_backup_is_read_only")

        raw_import = can_write_label_role(
            "raw_ai_prediction_backup",
            operation="prediction_raw_backup_import",
            audit_metadata={"prediction_id": "run_001"},
        )
        self.assertTrue(raw_import.allowed)

        truth_without_review = can_write_label_role("manual_truth", operation="truth_promotion", explicit_review=False)
        self.assertFalse(truth_without_review.allowed)
        self.assertEqual(truth_without_review.reason, "manual_truth_requires_explicit_review")

        truth_with_review = can_write_label_role("manual_truth", operation="truth_promotion", explicit_review=True)
        self.assertTrue(truth_with_review.allowed)

    def test_editable_role_guard_matches_top_level_and_part_scopes(self):
        self.assertTrue(require_editable_label_role("working_edit", scope="top_level"))
        self.assertTrue(require_editable_label_role("editable_ai_result", scope="part"))

        top_level_manual = require_editable_label_role("manual_truth", scope="top_level")
        self.assertFalse(top_level_manual.allowed)
        self.assertEqual(top_level_manual.reason, "manual_truth_is_not_directly_editable")

        part_backup = require_editable_label_role("raw_ai_prediction_backup", scope="part")
        self.assertFalse(part_backup.allowed)
        self.assertEqual(part_backup.reason, "raw_ai_prediction_backup_is_read_only")


if __name__ == "__main__":
    unittest.main()
