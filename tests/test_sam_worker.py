import unittest
from unittest.mock import patch

import numpy as np

from AntSleap.core import sam_helper


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


class SamWorkerTests(unittest.TestCase):
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

if __name__ == "__main__":
    unittest.main()
