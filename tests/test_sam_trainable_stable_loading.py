import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import torch

from AntSleap.models.sam_trainable import (
    TrainableSAM,
    _MemoryLoadedSAM,
    _build_sam_model_from_bytes,
    _checkpoint_payload_from_bytes,
)


class _FakeSAMCore(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.image_encoder = torch.nn.Linear(1, 1)
        self.prompt_encoder = torch.nn.Linear(1, 1)
        self.mask_decoder = torch.nn.Linear(1, 1)
        self.loaded_state = None
        self.loaded_strict = None
        self.eval_called = False

    def load_state_dict(self, state_dict, strict=True):
        self.loaded_state = dict(state_dict)
        self.loaded_strict = strict
        return SimpleNamespace(missing_keys=[], unexpected_keys=[])

    def eval(self):
        self.eval_called = True
        return self


class SAMTrainableStableLoadingTests(unittest.TestCase):
    @staticmethod
    def _checkpoint_bytes():
        buffer = io.BytesIO()
        torch.save({"model": {"weight": torch.tensor([3.0])}}, buffer)
        return buffer.getvalue()

    @staticmethod
    def _wrapper(core=None):
        return SimpleNamespace(model=core or _FakeSAMCore())

    def test_memory_builder_deserializes_bytesio_and_loads_strictly(self):
        from ultralytics.models.sam import build as sam_build

        checkpoint_bytes = self._checkpoint_bytes()
        core = _FakeSAMCore()
        real_torch_load = torch.load

        with patch.dict(
            sam_build.sam_model_map,
            {"sam_b.pt": lambda checkpoint: core},
            clear=True,
        ), patch(
            "AntSleap.models.sam_trainable.torch.load",
            wraps=real_torch_load,
        ) as load_mock:
            loaded = _build_sam_model_from_bytes(
                "C:/replaced/sam_b.pt",
                checkpoint_bytes,
            )

        self.assertIs(loaded, core)
        self.assertIsInstance(load_mock.call_args.args[0], io.BytesIO)
        self.assertTrue(load_mock.call_args.kwargs["weights_only"])
        self.assertEqual(core.loaded_state["weight"].item(), 3.0)
        self.assertTrue(core.loaded_strict)
        self.assertTrue(core.eval_called)

    def test_ultralytics_wrapper_override_does_not_require_path_to_exist(self):
        checkpoint_bytes = self._checkpoint_bytes()
        core = _FakeSAMCore()
        missing_path = "definitely-missing/sam_b.pt"

        with patch(
            "AntSleap.models.sam_trainable._build_sam_model_from_bytes",
            return_value=core,
        ) as build_mock:
            wrapper = _MemoryLoadedSAM(missing_path, checkpoint_bytes)

        self.assertIs(wrapper.model, core)
        build_mock.assert_called_once_with(missing_path, checkpoint_bytes)

    def test_weights_only_fallback_is_limited_to_unsupported_old_torch(self):
        payload = {"weight": torch.tensor([1.0])}
        with patch(
            "AntSleap.models.sam_trainable.torch.load",
            side_effect=[
                TypeError("load() got an unexpected keyword argument 'weights_only'"),
                payload,
            ],
        ) as load_mock:
            loaded = _checkpoint_payload_from_bytes(b"legacy-torch-fixture")

        self.assertIs(loaded, payload)
        self.assertEqual(load_mock.call_count, 2)
        self.assertTrue(load_mock.call_args_list[0].kwargs["weights_only"])
        self.assertNotIn("weights_only", load_mock.call_args_list[1].kwargs)
        self.assertEqual(load_mock.call_args_list[1].args[0].tell(), 0)

        with patch(
            "AntSleap.models.sam_trainable.torch.load",
            side_effect=TypeError("checkpoint reducer raised TypeError"),
        ) as load_mock:
            with self.assertRaisesRegex(TypeError, "checkpoint reducer"):
                _checkpoint_payload_from_bytes(b"unsafe-fixture")
        self.assertEqual(load_mock.call_count, 1)

    def test_trainable_sam_uses_memory_route_and_records_loaded_digest(self):
        checkpoint_bytes = self._checkpoint_bytes()
        wrapper = self._wrapper()

        with patch(
            "AntSleap.models.sam_trainable._MemoryLoadedSAM",
            return_value=wrapper,
        ) as memory_sam, patch(
            "AntSleap.models.sam_trainable.SAM"
        ) as path_sam:
            model = TrainableSAM(
                model_path="C:/weights/sam_b.pt",
                checkpoint_bytes=bytearray(checkpoint_bytes),
                device="cpu",
            )

        path_sam.assert_not_called()
        memory_sam.assert_called_once()
        self.assertIsInstance(memory_sam.call_args.args[1], bytes)
        self.assertEqual(
            model.loaded_checkpoint_identity["digest"],
            hashlib.sha256(checkpoint_bytes).hexdigest(),
        )
        self.assertEqual(
            model.loaded_checkpoint_identity["size_bytes"],
            len(checkpoint_bytes),
        )
        self.assertFalse(
            any(param.requires_grad for param in model.sam_model.image_encoder.parameters())
        )
        self.assertFalse(
            any(param.requires_grad for param in model.sam_model.prompt_encoder.parameters())
        )
        self.assertTrue(
            all(param.requires_grad for param in model.sam_model.mask_decoder.parameters())
        )

    def test_legacy_path_constructor_remains_compatible(self):
        wrapper = self._wrapper()
        path = Path(tempfile.gettempdir()) / "sam_b.pt"

        with patch(
            "AntSleap.models.sam_trainable.SAM",
            return_value=wrapper,
        ) as path_sam, patch(
            "AntSleap.models.sam_trainable._MemoryLoadedSAM"
        ) as memory_sam:
            model = TrainableSAM(model_path=path, device="cpu")

        path_sam.assert_called_once_with(path)
        memory_sam.assert_not_called()
        self.assertEqual(model.loaded_checkpoint_identity["source"], "path")

    def test_empty_or_non_bytes_checkpoint_is_rejected_before_loading(self):
        with patch("AntSleap.models.sam_trainable._MemoryLoadedSAM") as memory_sam:
            with self.assertRaisesRegex(ValueError, "sam_checkpoint_bytes_empty"):
                TrainableSAM(checkpoint_bytes=b"", device="cpu")
            with self.assertRaisesRegex(TypeError, "sam_checkpoint_bytes_invalid"):
                TrainableSAM(checkpoint_bytes="not-bytes", device="cpu")

        memory_sam.assert_not_called()


if __name__ == "__main__":
    unittest.main()
