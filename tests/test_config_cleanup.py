# pyright: reportMissingImports=false

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from AntSleap.core.config import ConfigManager, DEFAULT_CONFIG


class ConfigCleanupTests(unittest.TestCase):
    def test_default_config_no_longer_contains_manifest_training_defaults(self):
        self.assertNotIn("train_split_manifest_path", DEFAULT_CONFIG)
        self.assertNotIn("train_core2_manifest_path", DEFAULT_CONFIG)
        self.assertNotIn("train_allow_random_fallback", DEFAULT_CONFIG)
        self.assertNotIn("inf_enable_cascade_experts", DEFAULT_CONFIG)

    def test_config_manager_drops_obsolete_manifest_keys_on_load_and_save(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "user_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "language": "zh",
                        "train_split_manifest_path": "artifacts/core2/split_manifest_run1.json",
                        "train_core2_manifest_path": "artifacts/core2/train_manifest.json",
                        "train_allow_random_fallback": False,
                        "inf_enable_cascade_experts": True,
                    }
                ),
                encoding="utf-8",
            )

            with patch("AntSleap.core.config.CONFIG_FILE", str(config_path)):
                manager = ConfigManager()
                self.assertEqual(manager.get("language"), "zh")
                self.assertNotIn("train_split_manifest_path", manager.config)
                self.assertNotIn("train_core2_manifest_path", manager.config)
                self.assertNotIn("train_allow_random_fallback", manager.config)
                self.assertNotIn("inf_enable_cascade_experts", manager.config)

                manager.save()
                saved_payload = json.loads(config_path.read_text(encoding="utf-8"))
                self.assertNotIn("train_split_manifest_path", saved_payload)
                self.assertNotIn("train_core2_manifest_path", saved_payload)
                self.assertNotIn("train_allow_random_fallback", saved_payload)
                self.assertNotIn("inf_enable_cascade_experts", saved_payload)


if __name__ == "__main__":
    unittest.main()
