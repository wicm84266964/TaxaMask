import unittest

import numpy as np

from AntSleap.core.tif_prediction_policy import (
    can_import_prediction_target,
    prediction_import_plan,
    validate_external_prediction_import,
    validate_prediction_volume,
)


class TifPredictionPolicyTests(unittest.TestCase):
    def test_prediction_import_plan_never_targets_manual_truth(self):
        top = prediction_import_plan("top_level_volume")
        self.assertEqual(top.review_role, "working_edit")
        self.assertEqual(top.raw_backup_role, "raw_ai_prediction_backup")

        part = prediction_import_plan("part_reslice")
        self.assertEqual(part.review_role, "editable_ai_result")
        self.assertEqual(part.raw_backup_role, "raw_ai_prediction_backup")

        manual = can_import_prediction_target("manual_truth", audit_metadata={"prediction_id": "p1"})
        self.assertFalse(manual.allowed)
        self.assertEqual(manual.reason, "prediction_import_must_not_target_manual_truth")

        backup = can_import_prediction_target(
            "raw_ai_prediction_backup",
            source_role="backend_prediction_result",
            overwrite_existing=True,
            audit_metadata={"prediction_id": "p1"},
        )
        self.assertTrue(backup.allowed)

        review = can_import_prediction_target(
            "editable_ai_result",
            source_role="backend_prediction_result",
            overwrite_existing=True,
            audit_metadata={"prediction_id": "p1"},
        )
        self.assertTrue(review.allowed)

    def test_prediction_shape_dtype_and_context_validation(self):
        valid = validate_prediction_volume(
            prediction_shape_zyx=[2, 3, 4],
            expected_shape_zyx=[2, 3, 4],
            dtype=np.uint16,
            context={"specimen_id": "01"},
        )
        self.assertTrue(valid.allowed)

        mismatch = validate_external_prediction_import(
            specimen_id="01",
            prediction_shape_zyx=[2, 3, 5],
            expected_shape_zyx=[2, 3, 4],
            dtype=np.uint16,
        )
        self.assertFalse(mismatch.allowed)
        self.assertEqual(mismatch.reason, "external_prediction_shape_mismatch")

        float_dtype = validate_prediction_volume(
            prediction_shape_zyx=[2, 3, 4],
            expected_shape_zyx=[2, 3, 4],
            dtype=np.float32,
        )
        self.assertFalse(float_dtype.allowed)
        self.assertEqual(float_dtype.reason, "prediction_label_tif_must_be_integer_dtype")


if __name__ == "__main__":
    unittest.main()
