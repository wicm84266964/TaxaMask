# pyright: reportMissingImports=false

import unittest
from unittest.mock import patch

from AntSleap.core.blink_expert_manifest import BLINK_EXPERT_BACKEND_VIT_B
from AntSleap.ui.blink_lab import BlinkTrainingThread


class BlinkTrainingBackendGuardTests(unittest.TestCase):
    def _thread(self, backend):
        return BlinkTrainingThread(
            project_path="project.taxamask.json",
            part_name="Mandible",
            parent_part="Head",
            epochs=1,
            batch_size=1,
            trainer_backend=backend,
            device="cpu",
        )

    def test_external_backend_is_rejected_before_trainer_construction(self):
        thread = self._thread("external_blink")
        errors = []
        results = []
        thread.error_signal.connect(errors.append)
        thread.result_signal.connect(results.append)

        with patch(
            "AntSleap.core.blink_trainer.BlinkExpertTrainer",
            side_effect=AssertionError("vit_b_trainer_must_not_be_constructed"),
        ):
            thread.run()

        self.assertEqual(results, [])
        self.assertEqual(errors, ["blink_training_backend_unsupported:external_blink"])

    def test_cancelled_run_never_emits_success_even_with_partial_path(self):
        thread = self._thread(BLINK_EXPERT_BACKEND_VIT_B)
        cancelled = []
        results = []
        thread.cancelled_signal.connect(lambda: cancelled.append(True))
        thread.result_signal.connect(results.append)

        with patch("AntSleap.core.blink_trainer.BlinkExpertTrainer") as trainer_class:
            trainer_class.return_value.train.return_value = "partial_checkpoint.pt"
            with patch.object(thread, "isInterruptionRequested", return_value=True):
                thread.run()

        self.assertEqual(cancelled, [True])
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
