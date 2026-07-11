import importlib
import unittest

from tests.tif_architecture_test_groups import (
    TIF_ARCHITECTURE_REGRESSION_GROUPS,
    TIF_RESEARCH_SAFETY_COVERAGE,
    TIF_RESEARCH_SMOKE_TESTS,
    unittest_command_for,
)


def _module_name(target):
    if ".Tif" in target:
        return target.split(".Tif", 1)[0]
    return target


class TifArchitectureTestGroupTests(unittest.TestCase):
    def test_regression_groups_reference_importable_modules(self):
        self.assertIn("core_safety", TIF_ARCHITECTURE_REGRESSION_GROUPS)
        self.assertIn("service_task", TIF_ARCHITECTURE_REGRESSION_GROUPS)
        self.assertIn("round3_architecture", TIF_ARCHITECTURE_REGRESSION_GROUPS)
        self.assertIn("research_smoke", TIF_ARCHITECTURE_REGRESSION_GROUPS)

        for group_name, targets in TIF_ARCHITECTURE_REGRESSION_GROUPS.items():
            self.assertTrue(targets, group_name)
            command = unittest_command_for(group_name)
            self.assertIn("python -m unittest", command)
            for target in targets:
                importlib.import_module(_module_name(target))

    def test_research_safety_checklist_has_named_test_coverage(self):
        expected = {
            "prediction_import_never_overwrites_manual_truth",
            "raw_ai_prediction_backup_is_audit_only",
            "unreviewed_results_do_not_enter_training",
            "save_failure_keeps_dirty_state",
            "stale_task_result_does_not_write_current_part",
            "roi_output_shape_matches_bbox",
            "training_selection_uses_train_ready_samples",
            "local_axis_export_respects_backend_write_lock",
        }

        self.assertEqual(set(TIF_RESEARCH_SAFETY_COVERAGE), expected)
        for requirement, targets in TIF_RESEARCH_SAFETY_COVERAGE.items():
            self.assertGreaterEqual(len(targets), 2, requirement)
            for target in targets:
                importlib.import_module(_module_name(target))

    def test_research_smoke_group_covers_main_tif_workflows(self):
        smoke = "\n".join(TIF_RESEARCH_SMOKE_TESTS)

        for keyword in (
            "batch_import",
            "confirm_roi",
            "auto_save",
            "promotes_batch_to_manual_truth",
            "train_finished",
            "stale_background",
            "falls_back",
            "review_retrain_loop",
        ):
            self.assertIn(keyword, smoke)


if __name__ == "__main__":
    unittest.main()
