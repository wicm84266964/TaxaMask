import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import torch

from AntSleap.core.engine import AntEngine
from AntSleap.core.sam_decoder_checkpoint import (
    SAM_DECODER_CHECKPOINT_SCHEMA_VERSION,
    build_sam_decoder_checkpoint,
)


class _FakeSAMCore(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.image_encoder = torch.nn.Linear(2, 2)
        self.prompt_encoder = torch.nn.Linear(2, 2)
        self.mask_decoder = torch.nn.Linear(2, 2)
        for parameter in self.image_encoder.parameters():
            parameter.requires_grad = False
        for parameter in self.prompt_encoder.parameters():
            parameter.requires_grad = False


class _FakeTrainableSAM(torch.nn.Module):
    calls = []
    failure = None

    def __init__(self, model_path, device="cpu", checkpoint_bytes=None):
        super().__init__()
        type(self).calls.append(
            {
                "model_path": str(model_path),
                "device": torch.device(device),
                "checkpoint_bytes": checkpoint_bytes,
            }
        )
        if type(self).failure is not None:
            raise type(self).failure
        self.device = torch.device(device)
        self.sam_model = _FakeSAMCore().to(self.device)
        self.ultralytics_sam = SimpleNamespace(model=self.sam_model)


class EngineSAMStrictLoadingTests(unittest.TestCase):
    def setUp(self):
        _FakeTrainableSAM.calls = []
        _FakeTrainableSAM.failure = None

    @staticmethod
    def _engine(root):
        return AntEngine(
            num_classes=1,
            locator_scope=["Head"],
            device="cpu",
            weights_dir=Path(root) / "weights",
        )

    @staticmethod
    def _serialize(payload):
        buffer = io.BytesIO()
        torch.save(payload, buffer)
        return buffer.getvalue()

    @staticmethod
    def _fingerprint(payload):
        return {
            "entry_kind": "file",
            "size_bytes": len(payload),
            "hash_algorithm": "sha256",
            "digest": hashlib.sha256(payload).hexdigest(),
        }

    def _configure(self, engine, payload=b"verified-base-sam"):
        return engine.configure_verified_base_sam(
            payload,
            reference="registered/sam_b.pt",
            fingerprint=self._fingerprint(payload),
        )

    def _load_fake_parts(self, engine):
        with patch("AntSleap.core.engine.TrainableSAM", _FakeTrainableSAM):
            return engine.ensure_parts_model_loaded()

    def test_verified_base_bytes_feed_parts_and_predictor_without_path_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine(tmp)
            original = b"verified-base-sam"
            identity = self._configure(engine, original)
            Path(engine.base_sam_path).write_bytes(b"replaced-after-verification")
            predictor = object()

            with patch(
                "AntSleap.core.engine.TrainableSAM",
                _FakeTrainableSAM,
            ), patch(
                "AntSleap.core.engine.load_sam_from_checkpoint_bytes",
                return_value=predictor,
            ) as memory_predictor, patch(
                "AntSleap.core.engine.SAM",
                side_effect=AssertionError("verified base SAM path was reopened"),
            ) as path_predictor:
                parts_model = engine.ensure_parts_model_loaded()
                loaded_predictor = engine._get_base_sam_predictor()

            self.assertIsInstance(parts_model, _FakeTrainableSAM)
            self.assertEqual(_FakeTrainableSAM.calls[0]["checkpoint_bytes"], original)
            self.assertIs(loaded_predictor, predictor)
            memory_predictor.assert_called_once_with(engine.base_sam_path, original)
            path_predictor.assert_not_called()
            self.assertEqual(identity["digest"], hashlib.sha256(original).hexdigest())
            self.assertEqual(engine.verified_base_sam_identity, identity)

    def test_invalid_base_fingerprint_does_not_replace_existing_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine(tmp)
            self._configure(engine, b"first-base")
            existing_model = object()
            existing_optimizer = object()
            existing_predictor = object()
            engine.parts_model = existing_model
            engine.opt_parts = existing_optimizer
            engine.base_sam_predictor = existing_predictor
            previous_identity = dict(engine.verified_base_sam_identity)

            with self.assertRaisesRegex(ValueError, "base_sam_fingerprint_mismatch"):
                engine.configure_verified_base_sam(
                    b"second-base",
                    reference="registered/sam_b.pt",
                    fingerprint={
                        "entry_kind": "file",
                        "size_bytes": len(b"second-base"),
                        "hash_algorithm": "sha256",
                        "digest": "0" * 64,
                    },
                )

            self.assertIs(engine.parts_model, existing_model)
            self.assertIs(engine.opt_parts, existing_optimizer)
            self.assertIs(engine.base_sam_predictor, existing_predictor)
            self.assertEqual(engine.verified_base_sam_identity, previous_identity)

    def test_parts_construction_failure_clears_runtime_and_is_not_swallowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine(tmp)
            self._configure(engine)
            engine.loaded_sam_decoder_reference = "old-decoder.pth"
            engine.loaded_sam_decoder_identity = {"digest": "old"}
            _FakeTrainableSAM.failure = RuntimeError("corrupt-base-sam")

            with patch("AntSleap.core.engine.TrainableSAM", _FakeTrainableSAM):
                with self.assertRaisesRegex(RuntimeError, "corrupt-base-sam"):
                    engine.ensure_parts_model_loaded()

            self.assertIsNone(engine.parts_model)
            self.assertIsNone(engine.opt_parts)
            self.assertIsNone(engine.base_sam_predictor)
            self.assertEqual(engine.loaded_sam_decoder_reference, "")
            self.assertEqual(engine.loaded_sam_decoder_identity, {})

    def test_verified_predictor_failure_clears_existing_segmenter_and_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine(tmp)
            self._configure(engine)
            self._load_fake_parts(engine)
            engine.loaded_sam_decoder_reference = "old-decoder.pth"
            engine.loaded_sam_decoder_identity = {"digest": "old"}

            with patch(
                "AntSleap.core.engine.load_sam_from_checkpoint_bytes",
                side_effect=RuntimeError("base-predictor-failed"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "base-predictor-failed",
                ):
                    engine._get_base_sam_predictor()

            self.assertIsNone(engine.parts_model)
            self.assertIsNone(engine.opt_parts)
            self.assertIsNone(engine.base_sam_predictor)
            self.assertEqual(engine.loaded_sam_decoder_reference, "")
            self.assertEqual(engine.loaded_sam_decoder_identity, {})

    def test_legacy_parts_and_predictor_path_calls_remain_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine(tmp)
            predictor = object()

            with patch(
                "AntSleap.core.engine.TrainableSAM",
                _FakeTrainableSAM,
            ), patch(
                "AntSleap.core.engine.SAM",
                return_value=predictor,
            ) as path_predictor, patch(
                "AntSleap.core.engine.load_sam_from_checkpoint_bytes"
            ) as memory_predictor:
                engine.ensure_parts_model_loaded()
                self.assertIs(engine._get_base_sam_predictor(), predictor)

            self.assertIsNone(_FakeTrainableSAM.calls[0]["checkpoint_bytes"])
            path_predictor.assert_called_once_with(engine.base_sam_path)
            memory_predictor.assert_not_called()

    def test_decoder_bytes_load_from_memory_and_atomically_replace_decoder(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine(tmp)
            self._configure(engine)
            parts_model = self._load_fake_parts(engine)
            old_decoder = parts_model.sam_model.mask_decoder
            checkpoint_state = {
                key: torch.full_like(value, 7.0)
                for key, value in old_decoder.state_dict().items()
            }
            checkpoint_bytes = self._serialize(checkpoint_state)
            reference_path = Path(engine.weights_dir) / "sam_decoder_lora_run1.pth"
            reference_path.write_bytes(b"replaced-after-verification")
            real_torch_load = torch.load

            with patch(
                "AntSleap.core.engine.torch.load",
                wraps=real_torch_load,
            ) as load_mock:
                loaded = engine.load_sam_decoder(
                    "run1",
                    checkpoint_path=reference_path,
                    checkpoint_bytes=checkpoint_bytes,
                )

            self.assertIs(loaded, parts_model)
            self.assertIsInstance(load_mock.call_args.args[0], io.BytesIO)
            self.assertIsNot(parts_model.sam_model.mask_decoder, old_decoder)
            for value in parts_model.sam_model.mask_decoder.state_dict().values():
                self.assertTrue(torch.equal(value, torch.full_like(value, 7.0)))
            optimizer_params = {
                id(parameter)
                for group in engine.opt_parts.param_groups
                for parameter in group["params"]
            }
            decoder_params = {
                id(parameter)
                for parameter in parts_model.sam_model.mask_decoder.parameters()
                if parameter.requires_grad
            }
            self.assertEqual(optimizer_params, decoder_params)
            self.assertEqual(
                engine.loaded_sam_decoder_identity["digest"],
                hashlib.sha256(checkpoint_bytes).hexdigest(),
            )
            self.assertEqual(
                engine.loaded_sam_decoder_reference,
                "sam_decoder_lora_run1.pth",
            )

    def test_decoder_missing_key_clears_runtime_without_mutating_old_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine(tmp)
            self._configure(engine)
            parts_model = self._load_fake_parts(engine)
            old_decoder = parts_model.sam_model.mask_decoder
            old_state = {
                key: value.detach().clone()
                for key, value in old_decoder.state_dict().items()
            }
            incomplete = dict(old_state)
            incomplete.pop(next(iter(incomplete)))

            with self.assertRaisesRegex(
                RuntimeError,
                "sam_decoder_checkpoint_state_mismatch",
            ):
                engine.load_sam_decoder(
                    "missing-key",
                    checkpoint_bytes=self._serialize(incomplete),
                )

            self.assertIsNone(engine.parts_model)
            self.assertIsNone(engine.opt_parts)
            self.assertEqual(engine.loaded_sam_decoder_reference, "")
            for key, value in old_decoder.state_dict().items():
                self.assertTrue(torch.equal(value, old_state[key]))

    def test_decoder_wrong_shape_and_corrupt_bytes_clear_runtime_and_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine(tmp)
            self._configure(engine)
            parts_model = self._load_fake_parts(engine)
            wrong_shape = {
                key: value.detach().clone()
                for key, value in parts_model.sam_model.mask_decoder.state_dict().items()
            }
            first_key = next(iter(wrong_shape))
            wrong_shape[first_key] = torch.zeros(1)

            with self.assertRaisesRegex(
                ValueError,
                "sam_decoder_checkpoint_shape_mismatch",
            ):
                engine.load_sam_decoder(
                    "wrong-shape",
                    checkpoint_bytes=self._serialize(wrong_shape),
                )
            self.assertIsNone(engine.parts_model)
            self.assertIsNone(engine.opt_parts)

            engine.loaded_sam_decoder_reference = "stale.pth"
            with self.assertRaises(Exception):
                engine.load_sam_decoder(
                    "corrupt",
                    checkpoint_bytes=b"not-a-torch-checkpoint",
                )
            self.assertIsNone(engine.parts_model)
            self.assertIsNone(engine.opt_parts)
            self.assertEqual(engine.loaded_sam_decoder_reference, "")

    def test_missing_legacy_decoder_and_reset_failure_raise_and_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine(tmp)
            missing = Path(engine.weights_dir) / "sam_decoder_lora_missing.pth"
            engine.parts_model = object()
            engine.opt_parts = object()
            engine.loaded_sam_decoder_reference = "stale.pth"

            with self.assertRaisesRegex(
                FileNotFoundError,
                "sam_decoder_checkpoint_missing",
            ):
                engine.load_sam_decoder("missing", checkpoint_path=missing)
            self.assertIsNone(engine.parts_model)
            self.assertIsNone(engine.opt_parts)
            self.assertEqual(engine.loaded_sam_decoder_reference, "")

            self._configure(engine)
            _FakeTrainableSAM.failure = RuntimeError("reset-base-failed")
            with patch("AntSleap.core.engine.TrainableSAM", _FakeTrainableSAM):
                with self.assertRaisesRegex(RuntimeError, "reset-base-failed"):
                    engine.reset_sam_to_base()
            self.assertIsNone(engine.parts_model)
            self.assertIsNone(engine.opt_parts)

    def test_valid_legacy_decoder_path_still_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine(tmp)
            self._configure(engine)
            parts_model = self._load_fake_parts(engine)
            checkpoint_state = {
                key: torch.full_like(value, 2.0)
                for key, value in parts_model.sam_model.mask_decoder.state_dict().items()
            }
            checkpoint_path = Path(engine.weights_dir) / "sam_decoder_lora_legacy.pth"
            torch.save(checkpoint_state, checkpoint_path)

            loaded = engine.load_sam_decoder(
                "legacy",
                checkpoint_path=checkpoint_path,
            )

            self.assertIs(loaded, parts_model)
            self.assertEqual(
                engine.loaded_sam_decoder_identity,
                {
                    "source": "path",
                    "reference": "sam_decoder_lora_legacy.pth",
                },
            )

    def test_bound_decoder_rejects_legacy_and_wrong_base_sam(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine(tmp)
            base_a = b"verified-base-a"
            identity_a = self._configure(engine, base_a)
            parts_model = self._load_fake_parts(engine)
            state = {
                key: torch.full_like(value, 3.0)
                for key, value in parts_model.sam_model.mask_decoder.state_dict().items()
            }
            legacy_bytes = self._serialize(state)
            with patch("AntSleap.core.engine.TrainableSAM", _FakeTrainableSAM):
                with self.assertRaisesRegex(
                    ValueError,
                    "sam_decoder_checkpoint_base_binding_missing",
                ):
                    engine.load_sam_decoder(
                        "legacy-managed",
                        checkpoint_bytes=legacy_bytes,
                        expected_base_sam_fingerprint=identity_a,
                        require_base_sam_match=True,
                    )

                self._configure(engine, base_a)
                bound_bytes = self._serialize(
                    build_sam_decoder_checkpoint(state, identity_a)
                )
                loaded = engine.load_sam_decoder(
                    "bound-a",
                    checkpoint_bytes=bound_bytes,
                    expected_base_sam_fingerprint=identity_a,
                    require_base_sam_match=True,
                )
                self.assertIsNotNone(loaded)

                identity_b = self._configure(engine, b"verified-base-b")
                with self.assertRaisesRegex(
                    ValueError,
                    "sam_decoder_runtime_base_sam_mismatch",
                ):
                    engine.load_sam_decoder(
                        "bound-a-on-b",
                        checkpoint_bytes=bound_bytes,
                        expected_base_sam_fingerprint=identity_b,
                        require_base_sam_match=True,
                    )
            self.assertIsNone(engine.parts_model)

    def test_segmenter_save_writes_bound_checkpoint_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine(tmp)
            identity = self._configure(engine, b"verified-save-base")
            self._load_fake_parts(engine)
            output_dir = Path(tmp) / "output"
            artifact_key = engine.save_weights(
                save_locator=False,
                save_segmenter=True,
                output_dir=output_dir,
                artifact_key="bound-save",
            )
            self.assertEqual(artifact_key, "bound-save")
            payload = torch.load(
                output_dir / "sam_decoder_lora_bound-save.pth",
                map_location="cpu",
                weights_only=True,
            )
            self.assertEqual(
                payload["schema_version"],
                SAM_DECODER_CHECKPOINT_SCHEMA_VERSION,
            )
            self.assertEqual(payload["meta"]["base_sam"], {
                key: identity[key]
                for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
            })

            unverified = self._engine(Path(tmp) / "unverified")
            self._load_fake_parts(unverified)
            with self.assertRaisesRegex(
                ValueError,
                "sam_decoder_checkpoint_base_sam_fingerprint_invalid",
            ):
                unverified.save_weights(
                    save_locator=False,
                    save_segmenter=True,
                    output_dir=Path(tmp) / "unverified-output",
                    artifact_key="unverified-save",
                )


if __name__ == "__main__":
    unittest.main()
