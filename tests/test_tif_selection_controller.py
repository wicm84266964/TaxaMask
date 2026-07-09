import unittest

from AntSleap.services.tif_selection_controller import TifSelectionController


class TifSelectionControllerTests(unittest.TestCase):
    def test_label_roles_and_preferred_role_follow_scope(self):
        controller = TifSelectionController()

        self.assertEqual(controller.label_roles_for_scope("full"), ("working_edit", "manual_truth", "raw_ai_prediction_backup"))
        self.assertEqual(controller.preferred_label_role("missing", "full"), "working_edit")

        result = controller.select_part("specimen-1", "brain", reslice_id="axis-1")
        self.assertTrue(result.ok)
        self.assertEqual(controller.state.context_key()[0], "specimen-1")
        self.assertEqual(controller.label_roles_for_scope(), ("manual_truth", "editable_ai_result", "raw_ai_prediction_backup"))
        self.assertEqual(controller.preferred_label_role("manual_truth"), "editable_ai_result")


if __name__ == "__main__":
    unittest.main()
