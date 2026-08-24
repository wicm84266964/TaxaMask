import hashlib
import io
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch
from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from AntSleap.core import sam_helper
from AntSleap.core.sam_decoder_checkpoint import build_sam_decoder_checkpoint

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _FakeDevice:
    type = "cpu"


class _FakeSAM:
    instances = []

    def __init__(self, model_type):
        self.model_type = model_type
        self.predict_calls = []
        type(self).instances.append(self)

    def predict(self, source, **kwargs):
        self.predict_calls.append((source, kwargs))
        return []


class _FailingWarmupSAM(_FakeSAM):
    def predict(self, source, **kwargs):
        self.predict_calls.append((source, kwargs))
        raise RuntimeError("warmup failed")


class _RuntimeSAM(_FakeSAM):
    def __init__(self, model_type):
        super().__init__(model_type)
        self.model = SimpleNamespace(
            model=SimpleNamespace(
                mask_decoder=torch.nn.Linear(1, 1, bias=False)
            )
        )


class _RuntimeRequester(QObject):
    requested = Signal(object)


class SamWorkerTests(unittest.TestCase):
    @staticmethod
    def _serialize(payload):
        buffer = io.BytesIO()
        torch.save(payload, buffer)
        return buffer.getvalue()

    def test_verified_base_checkpoint_bytes_load_without_reopening_path(self):
        checkpoint_bytes = b"verified-base-sam-bytes"
        fingerprint = {
            "entry_kind": "file",
            "size_bytes": len(checkpoint_bytes),
            "hash_algorithm": "sha256",
            "digest": hashlib.sha256(checkpoint_bytes).hexdigest(),
        }
        worker = sam_helper.SAMWorker(
            model_type="missing/sam_b.pt",
            device="cpu",
            base_checkpoint_bytes=checkpoint_bytes,
            base_reference="registered/sam_b.pt",
            base_fingerprint=fingerprint,
        )
        loaded = []
        worker.model_loaded.connect(lambda: loaded.append(True))

        with patch.object(
            sam_helper,
            "load_sam_from_checkpoint_bytes",
            side_effect=lambda model_path, payload: _FakeSAM(
                f"{model_path}:{payload.decode('ascii')}"
            ),
        ) as memory_loader, patch.object(
            sam_helper,
            "resolve_torch_device",
            lambda _preference: _FakeDevice(),
        ), patch.object(
            sam_helper,
            "SAM",
            side_effect=AssertionError("base path must not be reopened"),
        ):
            worker.load_model()

        self.assertEqual(loaded, [True])
        memory_loader.assert_called_once_with(
            "missing/sam_b.pt",
            checkpoint_bytes,
        )
        self.assertEqual(
            worker.loaded_base_identity,
            {
                **fingerprint,
                "source": "memory",
                "reference": "registered/sam_b.pt",
            },
        )

    def test_verified_base_fingerprint_mismatch_preserves_current_runtime(self):
        worker = sam_helper.SAMWorker(model_type="sam_b.pt", device="cpu")
        current_model = object()
        worker.model = current_model

        with self.assertRaisesRegex(
            ValueError,
            "sam_worker_base_fingerprint_mismatch",
        ):
            worker.configure_verified_base_sam(
                b"new-base",
                fingerprint={
                    "entry_kind": "file",
                    "size_bytes": 8,
                    "hash_algorithm": "sha256",
                    "digest": "0" * 64,
                },
            )

        self.assertIs(worker.model, current_model)
        self.assertIsNone(worker._verified_base_checkpoint_bytes)
        self.assertEqual(worker.verified_base_sam_identity, {})

    def test_decoder_checkpoint_bytes_use_memory_without_reopening_path(self):
        original_decoder = torch.nn.Linear(1, 1, bias=False)
        with torch.no_grad():
            original_decoder.weight.fill_(1.0)
        worker = sam_helper.SAMWorker(model_type="fake_sam.pt", device="cpu")
        worker.model = SimpleNamespace(
            model=SimpleNamespace(
                model=SimpleNamespace(mask_decoder=original_decoder)
            )
        )
        worker.device = torch.device("cpu")
        payload_buffer = io.BytesIO()
        torch.save(
            {"state_dict": {"weight": torch.tensor([[7.0]])}},
            payload_buffer,
        )
        checkpoint_bytes = payload_buffer.getvalue()
        missing_path = "definitely-missing/replaced-decoder.pth"
        reference = ".training_runs/run/active/sam_decoder_lora_run.pth"
        real_torch_load = torch.load

        with patch.object(
            sam_helper.torch,
            "load",
            wraps=real_torch_load,
        ) as load_mock:
            loaded = worker.load_decoder_weights(
                missing_path,
                checkpoint_payload=checkpoint_bytes,
                reference=reference,
                raise_on_error=True,
            )

        self.assertTrue(loaded)
        checkpoint_source = load_mock.call_args.args[0]
        self.assertIsInstance(checkpoint_source, io.BytesIO)
        self.assertEqual(checkpoint_source.getvalue(), checkpoint_bytes)
        self.assertTrue(load_mock.call_args.kwargs["weights_only"])
        loaded_decoder = worker.model.model.model.mask_decoder
        self.assertIsNot(loaded_decoder, original_decoder)
        self.assertEqual(loaded_decoder.weight.item(), 7.0)
        self.assertEqual(original_decoder.weight.item(), 1.0)
        self.assertEqual(worker.loaded_decoder_reference, reference)
        self.assertEqual(
            worker.loaded_decoder_identity,
            {
                "source": "memory",
                "reference": reference,
                "size_bytes": len(checkpoint_bytes),
                "hash_algorithm": "sha256",
                "digest": hashlib.sha256(checkpoint_bytes).hexdigest(),
            },
        )

    def test_bound_decoder_requires_same_loaded_base_sam(self):
        base_payload = b"worker-bound-base"
        base_fingerprint = {
            "entry_kind": "file",
            "size_bytes": len(base_payload),
            "hash_algorithm": "sha256",
            "digest": hashlib.sha256(base_payload).hexdigest(),
        }
        original_decoder = torch.nn.Linear(1, 1, bias=False)
        worker = sam_helper.SAMWorker(model_type="sam_b.pt", device="cpu")
        worker.model = SimpleNamespace(
            model=SimpleNamespace(
                model=SimpleNamespace(mask_decoder=original_decoder)
            )
        )
        worker.device = torch.device("cpu")
        worker.loaded_base_identity = {
            **base_fingerprint,
            "source": "memory",
            "reference": "registered/sam_b.pt",
        }
        state = {"weight": torch.tensor([[9.0]])}
        bound = self._serialize(
            build_sam_decoder_checkpoint(state, base_fingerprint)
        )
        self.assertTrue(
            worker.load_decoder_weights(
                "missing/bound.pth",
                checkpoint_payload=bound,
                reference="managed/bound.pth",
                raise_on_error=True,
                expected_base_sam_fingerprint=base_fingerprint,
                require_base_sam_match=True,
            )
        )
        self.assertEqual(
            worker.model.model.model.mask_decoder.weight.item(),
            9.0,
        )

        wrong_base = {**base_fingerprint, "digest": "0" * 64}
        with self.assertRaisesRegex(
            ValueError,
            "sam_decoder_runtime_base_sam_mismatch",
        ):
            worker.load_decoder_weights(
                "missing/bound.pth",
                checkpoint_payload=bound,
                reference="managed/bound.pth",
                raise_on_error=True,
                expected_base_sam_fingerprint=wrong_base,
                require_base_sam_match=True,
            )
        with self.assertRaisesRegex(
            ValueError,
            "sam_decoder_checkpoint_base_binding_missing",
        ):
            worker.load_decoder_weights(
                "missing/legacy.pth",
                checkpoint_payload=self._serialize(state),
                reference="managed/legacy.pth",
                raise_on_error=True,
                expected_base_sam_fingerprint=base_fingerprint,
                require_base_sam_match=True,
            )

    def test_runtime_bundle_executes_in_worker_qthread(self):
        app = QApplication.instance() or QApplication([])
        worker = sam_helper.SAMWorker(model_type="fake_sam.pt", device="cpu")
        worker_thread = QThread()
        worker.moveToThread(worker_thread)
        requester = _RuntimeRequester()
        requester.requested.connect(
            worker.apply_runtime_bundle,
            Qt.ConnectionType.QueuedConnection,
        )
        success_spy = QSignalSpy(worker.runtime_apply_succeeded)
        failure_spy = QSignalSpy(worker.runtime_apply_failed)
        checkpoint = self._serialize(
            {"weight": torch.tensor([[5.0]])}
        )
        request = {
            "request_id": "thread-check",
            "reference": "legacy/thread-check.pth",
            "checkpoint_path": "missing/thread-check.pth",
            "checkpoint_payload": checkpoint,
            "model_type": "fake_sam.pt",
            "device_preference": "cpu",
            "poly_epsilon": 2.0,
        }
        try:
            with patch.object(sam_helper, "SAM", _RuntimeSAM), patch.object(
                sam_helper,
                "resolve_torch_device",
                lambda _preference: torch.device("cpu"),
            ):
                worker_thread.start()
                requester.requested.emit(request)
                for _attempt in range(100):
                    app.processEvents()
                    if success_spy.count() or failure_spy.count():
                        break
                    success_spy.wait(20)
            self.assertEqual(failure_spy.count(), 0)
            self.assertEqual(success_spy.count(), 1)
            result = success_spy.at(0)[0]
            self.assertTrue(result["worker_thread_confirmed"])
            self.assertEqual(result["request_id"], "thread-check")
            self.assertEqual(result["loaded_decoder_reference"], "legacy/thread-check.pth")
            self.assertEqual(
                worker.model.model.model.mask_decoder.weight.item(),
                5.0,
            )
        finally:
            worker_thread.quit()
            worker_thread.wait(5000)

    def test_load_model_warms_predictor_with_dummy_box_prompt(self):
        _FakeSAM.instances = []
        worker = sam_helper.SAMWorker(model_type="fake_sam.pt", device="cpu")
        loaded = []
        worker.model_loaded.connect(lambda: loaded.append(True))

        with patch.object(sam_helper, "SAM", _FakeSAM), \
             patch.object(sam_helper, "resolve_torch_device", lambda _preference: _FakeDevice()):
            worker.load_model()

        self.assertTrue(loaded)
        self.assertIs(worker.model, _FakeSAM.instances[0])
        self.assertEqual(len(worker.model.predict_calls), 1)
        source, kwargs = worker.model.predict_calls[0]
        self.assertIsInstance(source, np.ndarray)
        self.assertEqual(source.shape, (64, 64, 3))
        self.assertEqual(kwargs["bboxes"], [[8, 8, 56, 56]])
        self.assertEqual(kwargs["device"].type, "cpu")
        self.assertEqual(kwargs["imgsz"], 1024)
        self.assertFalse(kwargs["verbose"])

    def test_warmup_failure_does_not_block_model_loaded_signal(self):
        _FailingWarmupSAM.instances = []
        worker = sam_helper.SAMWorker(model_type="fake_sam.pt", device="cpu")
        loaded = []
        errors = []
        worker.model_loaded.connect(lambda: loaded.append(True))
        worker.model_load_error.connect(errors.append)

        with patch.object(sam_helper, "SAM", _FailingWarmupSAM), \
             patch.object(sam_helper, "resolve_torch_device", lambda _preference: _FakeDevice()):
            worker.load_model()

        self.assertTrue(loaded)
        self.assertEqual(errors, [])
        self.assertIs(worker.model, _FailingWarmupSAM.instances[0])
        self.assertEqual(len(worker.model.predict_calls), 1)

    def test_reload_base_model_clears_decoder_state_and_results(self):
        _FakeSAM.instances = []
        worker = sam_helper.SAMWorker(model_type="fake_sam.pt", device="cpu")
        worker.model = object()
        worker.current_results = object()
        worker.loaded_decoder_reference = "managed/decoder.pth"
        worker.loaded_decoder_identity = {"digest": "old"}

        with patch.object(sam_helper, "SAM", _FakeSAM), patch.object(
            sam_helper,
            "resolve_torch_device",
            lambda _preference: _FakeDevice(),
        ):
            worker.reload_base_model()

        self.assertIs(worker.model, _FakeSAM.instances[0])
        self.assertIsNone(worker.current_results)
        self.assertEqual(worker.loaded_decoder_reference, "")
        self.assertEqual(worker.loaded_decoder_identity, {})

    def test_reload_base_model_failure_does_not_retain_fine_tuned_runtime(self):
        worker = sam_helper.SAMWorker(model_type="fake_sam.pt", device="cpu")
        worker.model = object()
        worker.current_results = object()
        worker.loaded_decoder_reference = "managed/decoder.pth"
        worker.loaded_decoder_identity = {"digest": "old"}
        errors = []
        worker.model_load_error.connect(errors.append)

        with patch.object(
            sam_helper,
            "resolve_torch_device",
            side_effect=RuntimeError("device unavailable"),
        ):
            worker.reload_base_model()

        self.assertIsNone(worker.model)
        self.assertIsNone(worker.current_results)
        self.assertEqual(worker.loaded_decoder_reference, "")
        self.assertEqual(worker.loaded_decoder_identity, {})
        self.assertEqual(len(errors), 1)
        self.assertIn("device unavailable", errors[0])

if __name__ == "__main__":
    unittest.main()
