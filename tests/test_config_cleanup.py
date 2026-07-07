# pyright: reportMissingImports=false

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from AntSleap.core.config import ConfigManager, DEFAULT_CONFIG
from AntSleap.core.platform_paths import user_config_path


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

    def test_config_manager_migrates_legacy_root_config_without_deleting_it(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            legacy_path = tmp_path / "repo" / "user_config.json"
            config_path = tmp_path / "config" / "TaxaMask" / "user_config.json"
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_text(
                json.dumps({"language": "zh", "runtime_device": "cpu"}),
                encoding="utf-8",
            )

            manager = ConfigManager(config_path=config_path, legacy_config_path=legacy_path)

            self.assertEqual(manager.get("language"), "zh")
            self.assertEqual(manager.get("runtime_device"), "cpu")
            self.assertTrue(config_path.exists())
            self.assertTrue(legacy_path.exists())

            manager.set("language", "en")
            manager.save()

            migrated_payload = json.loads(config_path.read_text(encoding="utf-8"))
            legacy_payload = json.loads(legacy_path.read_text(encoding="utf-8"))
            self.assertEqual(migrated_payload["language"], "en")
            self.assertEqual(legacy_payload["language"], "zh")

    def test_legacy_empty_tif_backend_migrates_to_nnunet_v2_commands(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "user_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "tif_backend": {
                            "backend_id": "custom_tif_backend",
                            "display_name": "TIF Volume Backend",
                            "python_executable": "C:/taxamask/python.exe",
                            "prepare_dataset_command": "",
                            "train_command": "",
                            "predict_command": "",
                            "model_manifest": "",
                        }
                    }
                ),
                encoding="utf-8",
            )

            manager = ConfigManager(config_path=config_path, legacy_config_path=Path(tmp_dir) / "missing.json")
            backend = manager.get("tif_backend")

            self.assertEqual(backend["backend_id"], "taxamask_tif_nnunet_v2_backend")
            self.assertEqual(backend["python_executable"], "C:/taxamask/python.exe")
            self.assertIn("AntSleap.tools.tif_nnunet_v2_backend", backend["train_command"])

    def test_named_custom_tif_backend_is_not_overwritten_by_migration(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "user_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "tif_backend": {
                            "backend_id": "monai_volume_backend",
                            "display_name": "MONAI volume backend",
                            "python_executable": "python",
                            "prepare_dataset_command": "",
                            "train_command": "",
                            "predict_command": "",
                        }
                    }
                ),
                encoding="utf-8",
            )

            manager = ConfigManager(config_path=config_path, legacy_config_path=Path(tmp_dir) / "missing.json")
            backend = manager.get("tif_backend")

            self.assertEqual(backend["backend_id"], "monai_volume_backend")
            self.assertEqual(backend["display_name"], "MONAI volume backend")
            self.assertEqual(backend["train_command"], "")

    def test_platform_config_path_rules_are_stable(self):
        win_path = user_config_path(
            platform="win32",
            env={"APPDATA": r"C:\Users\alice\AppData\Roaming"},
            home=r"C:\Users\alice",
        )
        self.assertTrue(str(win_path).replace("\\", "/").endswith("AppData/Roaming/TaxaMask/user_config.json"))

        linux_path = user_config_path(
            platform="linux",
            env={},
            home="/home/alice",
        )
        self.assertEqual(str(linux_path).replace("\\", "/"), "/home/alice/.config/taxamask/user_config.json")

        xdg_path = user_config_path(
            platform="linux",
            env={"XDG_CONFIG_HOME": "/tmp/xdg"},
            home="/home/alice",
        )
        self.assertEqual(str(xdg_path).replace("\\", "/"), "/tmp/xdg/taxamask/user_config.json")

        mac_path = user_config_path(
            platform="darwin",
            env={},
            home="/Users/alice",
        )
        self.assertEqual(
            str(mac_path).replace("\\", "/"),
            "/Users/alice/Library/Application Support/TaxaMask/user_config.json",
        )


if __name__ == "__main__":
    unittest.main()
