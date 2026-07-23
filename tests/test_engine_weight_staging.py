import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

from AntSleap.core.engine import AntEngine, _atomic_torch_save


class EngineWeightStagingTests(unittest.TestCase):
    def test_atomic_torch_save_removes_partial_checkpoint_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "locator_train_test.pth"

            def fail_after_partial(_payload, handle):
                handle.write(b"partial")
                raise OSError("disk_full")

            with patch("AntSleap.core.engine.torch.save", side_effect=fail_after_partial):
                with self.assertRaises(OSError):
                    _atomic_torch_save({"state_dict": {}}, target)

            self.assertFalse(target.exists())
            self.assertFalse(list(Path(tmp).glob("*.tmp_*")))

    def test_custom_run_key_saves_locator_only_without_constructing_sam(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = AntEngine.__new__(AntEngine)
            engine.weights_dir = str(Path(tmp) / "legacy")
            engine.locator_resolution = (512, 512)
            engine.current_num_classes = 1
            engine._locator_loss_weights = {"heatmap": 1.0, "wh": 1.0}
            engine.locator = torch.nn.Linear(2, 1)
            engine.ensure_locator_loaded = lambda: engine.locator
            engine.ensure_parts_model_loaded = lambda: (_ for _ in ()).throw(
                AssertionError("SAM must not be constructed")
            )
            engine.loaded_locator_timestamp = None
            engine.loaded_locator_requires_legacy_confirmation = True
            engine.loaded_locator_is_legacy_512 = True
            staging = Path(tmp) / "staging"

            artifact_key = engine.save_weights(
                save_locator=True,
                save_segmenter=False,
                output_dir=staging,
                artifact_key="train_fixture_001",
            )

            self.assertEqual(artifact_key, "train_fixture_001")
            self.assertTrue((staging / "locator_train_fixture_001.pth").is_file())
            self.assertFalse(list(staging.glob("sam_decoder_lora_*.pth")))
            self.assertEqual(engine.loaded_locator_timestamp, "train_fixture_001")

    def test_existing_run_key_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = AntEngine.__new__(AntEngine)
            engine.weights_dir = str(tmp)
            engine.locator_resolution = (512, 512)
            engine.current_num_classes = 1
            engine._locator_loss_weights = {"heatmap": 1.0, "wh": 1.0}
            engine.locator = torch.nn.Linear(2, 1)
            engine.ensure_locator_loaded = lambda: engine.locator
            engine.loaded_locator_timestamp = None
            engine.loaded_locator_requires_legacy_confirmation = False
            engine.loaded_locator_is_legacy_512 = False

            engine.save_weights(
                save_locator=True,
                save_segmenter=False,
                output_dir=tmp,
                artifact_key="train_fixture_002",
            )
            original = (Path(tmp) / "locator_train_fixture_002.pth").read_bytes()

            with self.assertRaises(FileExistsError):
                engine.save_weights(
                    save_locator=True,
                    save_segmenter=False,
                    output_dir=tmp,
                    artifact_key="train_fixture_002",
                )

            self.assertEqual(
                (Path(tmp) / "locator_train_fixture_002.pth").read_bytes(), original
            )


if __name__ == "__main__":
    unittest.main()
