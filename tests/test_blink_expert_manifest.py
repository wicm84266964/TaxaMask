# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

import json
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.blink_expert_manifest import (
    BLINK_EXPERT_BACKEND_VIT_B,
    BLINK_EXPERT_MANIFEST_SCHEMA_VERSION,
    default_manifest_path_for_weights,
    load_blink_expert_manifest,
    write_blink_expert_manifest,
)
from AntSleap.core.blink_trainer import BlinkExpertTrainer


class BlinkExpertManifestTests(unittest.TestCase):
    def test_manifest_path_sits_next_to_weights(self):
        self.assertEqual(
            default_manifest_path_for_weights("C:/models/Mandible/expert_v1.pth").replace("\\", "/"),
            "C:/models/Mandible/expert_v1.manifest.json",
        )

    def test_write_and_load_vit_b_manifest(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_path = Path(tmp_dir) / "experts" / "Mandible" / "expert_v20260602_120000.pth"
            weights_path.parent.mkdir(parents=True, exist_ok=True)
            weights_path.write_bytes(b"weights")

            manifest_path, manifest = write_blink_expert_manifest(
                str(weights_path),
                expert_backend=BLINK_EXPERT_BACKEND_VIT_B,
                parent_part="Head",
                child_part="Mandible",
                input_size=(384, 384),
                project_json="C:/project/demo.json",
                trajectory_count=12,
                train_params={"learning_rate": 0.002},
            )

            loaded = load_blink_expert_manifest(manifest_path)
            self.assertEqual(manifest["schema_version"], BLINK_EXPERT_MANIFEST_SCHEMA_VERSION)
            self.assertEqual(loaded["expert_backend"], BLINK_EXPERT_BACKEND_VIT_B)
            self.assertEqual(loaded["parent_part"], "Head")
            self.assertEqual(loaded["child_part"], "Mandible")
            self.assertEqual(loaded["input_size"], [384, 384])
            self.assertEqual(loaded["weights"]["main"], weights_path.name)
            self.assertEqual(loaded["train_data"]["trajectory_count"], 12)

    def test_blink_trainer_write_manifest_uses_training_context(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_path = Path(tmp_dir) / "experts" / "Eye" / "expert_v20260602_120000.pth"
            weights_path.parent.mkdir(parents=True, exist_ok=True)
            weights_path.write_bytes(b"weights")

            trainer = BlinkExpertTrainer.__new__(BlinkExpertTrainer)
            trainer.part_name = "Eye"
            trainer.parent_part = "Head"
            trainer.project_path = str(Path(tmp_dir) / "project.json")
            trainer.learning_rate = 0.001
            trainer.weight_decay = 0.0001

            class Dataset:
                def __len__(self):
                    return 7

            manifest_path, manifest = trainer.write_manifest(str(weights_path), (224, 224), Dataset())

            self.assertTrue(Path(manifest_path).exists())
            on_disk = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(on_disk, manifest)
            self.assertEqual(on_disk["expert_backend"], BLINK_EXPERT_BACKEND_VIT_B)
            self.assertEqual(on_disk["parent_part"], "Head")
            self.assertEqual(on_disk["child_part"], "Eye")
            self.assertEqual(on_disk["train_data"]["trajectory_count"], 7)


if __name__ == "__main__":
    unittest.main()
