import unittest

from AntSleap.services.tif_workbench_states import (
    TifBackendState,
    TifEditState,
    TifLocalAxisState,
    TifPreviewState,
    TifRoiState,
)


class TifWorkbenchStateTests(unittest.TestCase):
    def test_state_objects_are_serializable_summaries(self):
        states = [
            TifEditState(dirty_slice_count=2, auto_save_running=True, role="working_edit", scope="full"),
            TifPreviewState(display_mode="volume", render_mode="still", preview_pending=True, preview_token=7),
            TifBackendState(running=True, action="train", run_dir="runs/train"),
            TifRoiState(active_roi_id="roi-1", roi_keyframe_count=2, confirm_running=True),
            TifLocalAxisState(draft_active=True, export_running=True, pick_target="roll_a", roll_reference_keys=("point_a",)),
        ]

        for state in states:
            payload = state.to_dict()
            self.assertIsInstance(payload, dict)
            self.assertTrue(payload)


if __name__ == "__main__":
    unittest.main()
