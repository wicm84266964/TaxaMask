import gc
import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

from AntSleap.core.engine import (
    LOCATOR_ARCHITECTURE_ID,
    LOCATOR_CHECKPOINT_SCHEMA_VERSION,
    AntEngine,
)
from AntSleap.models.networks import TraitRegressor


class LocatorCheckpointStrictLoadingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.weights_dir = Path(self.temp_dir.name) / "managed-models"

    def tearDown(self):
        gc.collect()
        self.temp_dir.cleanup()

    def _engine(self, num_classes=1, locator_scope=None):
        scope = locator_scope or [f"Part{index + 1}" for index in range(num_classes)]
        return AntEngine(
            num_classes=num_classes,
            device="cpu",
            weights_dir=self.weights_dir,
            locator_scope=scope,
        )

    def _payload(self, num_classes=1, *, metadata=True, locator_scope=None):
        model = TraitRegressor(in_channels=3, out_channels=num_classes)
        scope = locator_scope or [f"Part{index + 1}" for index in range(num_classes)]
        payload = {
            "schema_version": LOCATOR_CHECKPOINT_SCHEMA_VERSION,
            "state_dict": model.state_dict(),
        }
        if metadata:
            payload["meta"] = {
                "architecture_id": LOCATOR_ARCHITECTURE_ID,
                "locator_size": [640, 384],
                "num_classes": num_classes,
                "locator_scope": list(scope),
            }
        return payload

    def _write_payload(self, filename, payload):
        path = self.weights_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(payload, path)
        return path

    def _prime_loaded_state(self, engine):
        engine.ensure_locator_loaded()
        engine.locator_resolution = (768, 512)
        engine.loaded_locator_timestamp = "previous"
        engine.loaded_locator_reference = "locator_previous.pth"
        engine.loaded_locator_identity = {"digest": "previous"}
        engine.loaded_locator_requires_legacy_confirmation = True
        engine.loaded_locator_is_legacy_512 = True

    def _assert_failed_state_cleared(self, engine):
        self.assertIsNone(engine.locator)
        self.assertIsNone(engine.opt_loc)
        self.assertEqual(engine.locator_resolution, (512, 512))
        self.assertIsNone(engine.loaded_locator_timestamp)
        self.assertEqual(engine.loaded_locator_reference, "")
        self.assertEqual(engine.loaded_locator_identity, {})
        self.assertFalse(engine.loaded_locator_requires_legacy_confirmation)
        self.assertFalse(engine.loaded_locator_is_legacy_512)

    def test_explicit_weights_dir_initializes_all_managed_paths_together(self):
        engine = self._engine()
        expected_root = os.path.abspath(self.weights_dir)

        self.assertEqual(engine.weights_dir, expected_root)
        self.assertEqual(engine.base_sam_path, os.path.join(expected_root, "sam_b.pt"))
        self.assertEqual(
            engine.cascade_manager.expert_dir,
            os.path.join(expected_root, "experts"),
        )
        self.assertEqual(
            engine.cascade_manager.route_manifest_path,
            os.path.join(expected_root, "experts", "cascade_routes.json"),
        )

    def test_valid_real_locator_checkpoint_loads_strictly(self):
        engine = self._engine()
        checkpoint = self._write_payload("locator_valid.pth", self._payload())

        engine.load_locator(
            "valid",
            checkpoint_path=checkpoint,
            require_complete=True,
            expected_locator_scope=["Part1"],
        )

        self.assertIsInstance(engine.locator, TraitRegressor)
        self.assertIsNotNone(engine.opt_loc)
        self.assertEqual(engine.locator_resolution, (640, 384))
        self.assertEqual(engine.loaded_locator_timestamp, "valid")
        self.assertEqual(engine.loaded_locator_reference, "locator_valid.pth")
        self.assertEqual(
            engine.loaded_locator_identity,
            {
                "source": "path",
                "reference": "locator_valid.pth",
            },
        )
        self.assertEqual(
            engine.loaded_locator_schema_version,
            LOCATOR_CHECKPOINT_SCHEMA_VERSION,
        )
        self.assertEqual(engine.loaded_locator_scope, ["Part1"])
        self.assertFalse(engine.loaded_locator_requires_legacy_confirmation)
        self.assertFalse(engine.loaded_locator_is_legacy_512)

    def test_empty_checkpoint_raises_and_clears_previous_locator(self):
        engine = self._engine()
        self._prime_loaded_state(engine)
        checkpoint = self._write_payload(
            "locator_empty.pth",
            {"state_dict": {}, "meta": {"num_classes": 1}},
        )

        with self.assertRaisesRegex(ValueError, "locator_checkpoint_state_empty"):
            engine.load_locator("empty", checkpoint_path=checkpoint)

        self._assert_failed_state_cleared(engine)

    def test_partial_checkpoint_raises_and_clears_previous_locator(self):
        engine = self._engine()
        self._prime_loaded_state(engine)
        payload = self._payload()
        removed_key = next(iter(payload["state_dict"]))
        payload["state_dict"].pop(removed_key)
        checkpoint = self._write_payload("locator_partial.pth", payload)

        with self.assertRaisesRegex(RuntimeError, "locator_checkpoint_state_mismatch"):
            engine.load_locator("partial", checkpoint_path=checkpoint)

        self._assert_failed_state_cleared(engine)

    def test_metadata_num_classes_mismatch_clears_previous_locator(self):
        engine = self._engine(num_classes=1)
        self._prime_loaded_state(engine)
        payload = self._payload(num_classes=1)
        payload["meta"]["num_classes"] = 2
        checkpoint = self._write_payload(
            "locator_wrong_metadata.pth",
            payload,
        )

        with self.assertRaisesRegex(
            ValueError,
            "locator_checkpoint_num_classes_mismatch",
        ):
            engine.load_locator("wrong-metadata", checkpoint_path=checkpoint)

        self._assert_failed_state_cleared(engine)

    def test_output_head_num_classes_mismatch_clears_previous_locator(self):
        engine = self._engine(num_classes=1)
        self._prime_loaded_state(engine)
        checkpoint = self._write_payload(
            "locator_two_classes.pth",
            self._payload(num_classes=2, metadata=False)["state_dict"],
        )

        with self.assertRaisesRegex(
            ValueError,
            "locator_checkpoint_num_classes_mismatch",
        ):
            engine.load_locator("two-classes", checkpoint_path=checkpoint)

        self._assert_failed_state_cleared(engine)

    def test_checkpoint_bytes_are_used_without_reading_replaced_path(self):
        engine = self._engine()
        buffer = io.BytesIO()
        torch.save(self._payload(), buffer)
        stable_bytes = buffer.getvalue()
        checkpoint = self.weights_dir / "locator_replaced.pth"
        checkpoint.write_bytes(b"replaced-after-verification")
        original_torch_load = torch.load

        with patch(
            "AntSleap.core.engine.torch.load",
            wraps=original_torch_load,
        ) as load_mock:
            engine.load_locator(
                "stable-bytes",
                checkpoint_path=checkpoint,
                checkpoint_bytes=stable_bytes,
                require_complete=True,
                expected_locator_scope=["Part1"],
            )

        self.assertIsInstance(load_mock.call_args.args[0], io.BytesIO)
        self.assertEqual(checkpoint.read_bytes(), b"replaced-after-verification")
        self.assertIsInstance(engine.locator, TraitRegressor)
        self.assertEqual(engine.loaded_locator_reference, "locator_replaced.pth")
        self.assertEqual(
            engine.loaded_locator_identity,
            {
                "source": "memory",
                "reference": "locator_replaced.pth",
                "size_bytes": len(stable_bytes),
                "hash_algorithm": "sha256",
                "digest": hashlib.sha256(stable_bytes).hexdigest(),
            },
        )

    def test_local_legacy_checkpoint_loads_with_expected_scope_for_confirmation(self):
        engine = self._engine(locator_scope=["Head"])
        checkpoint = self._write_payload(
            "locator_legacy.pth",
            self._payload()["state_dict"],
        )

        engine.load_locator(
            "legacy",
            checkpoint_path=checkpoint,
            require_complete=False,
            expected_locator_scope=["Head"],
        )

        self.assertIsInstance(engine.locator, TraitRegressor)
        self.assertEqual(engine.loaded_locator_schema_version, "")
        self.assertEqual(engine.loaded_locator_scope, [])
        self.assertEqual(engine.current_locator_scope, ["Head"])
        self.assertTrue(engine.loaded_locator_requires_legacy_confirmation)
        self.assertTrue(engine.loaded_locator_is_legacy_512)

    def test_managed_checkpoint_rejects_same_count_reordered_scope(self):
        engine = self._engine(num_classes=2, locator_scope=["Head", "Eye"])
        checkpoint = self._write_payload(
            "locator_reordered.pth",
            self._payload(num_classes=2, locator_scope=["Head", "Eye"]),
        )

        with self.assertRaisesRegex(ValueError, "locator_checkpoint_scope_mismatch"):
            engine.load_locator(
                "reordered",
                checkpoint_path=checkpoint,
                require_complete=True,
                expected_locator_scope=["Eye", "Head"],
            )

        self._assert_failed_state_cleared(engine)

    def test_managed_checkpoint_rejects_same_count_renamed_scope(self):
        engine = self._engine(num_classes=2, locator_scope=["Head", "Eye"])
        checkpoint = self._write_payload(
            "locator_renamed.pth",
            self._payload(num_classes=2, locator_scope=["Head", "Eye"]),
        )

        with self.assertRaisesRegex(ValueError, "locator_checkpoint_scope_mismatch"):
            engine.load_locator(
                "renamed",
                checkpoint_path=checkpoint,
                require_complete=True,
                expected_locator_scope=["Head", "Mandible"],
            )

        self._assert_failed_state_cleared(engine)


if __name__ == "__main__":
    unittest.main()
