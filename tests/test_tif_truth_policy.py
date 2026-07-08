import unittest

from AntSleap.core.tif_truth_policy import can_promote_to_manual_truth, can_use_role_for_training


class TifTruthPolicyTests(unittest.TestCase):
    def test_manual_truth_requires_explicit_reviewed_source(self):
        self.assertTrue(
            can_promote_to_manual_truth(
                "working_edit",
                explicit_review=True,
                review_ready=True,
            )
        )
        self.assertTrue(
            can_promote_to_manual_truth(
                "editable_ai_result",
                explicit_review=True,
                review_ready=True,
                opened_for_review=True,
                require_opened_for_review=True,
            )
        )

        no_review = can_promote_to_manual_truth("working_edit", explicit_review=False, review_ready=True)
        self.assertFalse(no_review.allowed)
        self.assertEqual(no_review.reason, "manual_truth_requires_explicit_review")

        backup = can_promote_to_manual_truth(
            "raw_ai_prediction_backup",
            explicit_review=True,
            review_ready=True,
        )
        self.assertFalse(backup.allowed)
        self.assertEqual(backup.reason, "raw_ai_prediction_backup_cannot_be_promoted_to_manual_truth")

        not_opened = can_promote_to_manual_truth(
            "editable_ai_result",
            explicit_review=True,
            review_ready=True,
            opened_for_review=False,
            require_opened_for_review=True,
        )
        self.assertFalse(not_opened.allowed)
        self.assertEqual(not_opened.reason, "manual_truth_source_not_opened_for_review")

    def test_training_uses_manual_truth_only(self):
        self.assertTrue(can_use_role_for_training("manual_truth", record_exists=True))

        editable = can_use_role_for_training("editable_ai_result", record_exists=True)
        self.assertFalse(editable.allowed)
        self.assertEqual(editable.reason, "training_requires_manual_truth")

        missing = can_use_role_for_training("manual_truth", record_exists=False)
        self.assertFalse(missing.allowed)
        self.assertEqual(missing.reason, "manual_truth_missing")


if __name__ == "__main__":
    unittest.main()
