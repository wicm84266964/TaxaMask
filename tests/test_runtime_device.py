import unittest
from unittest.mock import patch

from AntSleap.core import runtime_device


class FakeCuda:
    def __init__(self, available):
        self._available = available

    def is_available(self):
        return self._available


class FakeTorch:
    def __init__(self, cuda_available):
        self.cuda = FakeCuda(cuda_available)

    def device(self, device_type):
        return runtime_device.FallbackDevice(device_type)


class RuntimeDeviceTests(unittest.TestCase):
    def test_supported_preferences_do_not_include_mps(self):
        self.assertEqual(runtime_device.VALID_DEVICE_PREFERENCES, {"auto", "cpu", "cuda"})
        self.assertEqual(runtime_device.normalize_device_preference("mps"), "auto")
        self.assertEqual(runtime_device.normalize_device_preference("CUDA"), "cuda")
        self.assertEqual(runtime_device.normalize_device_preference(None), "auto")

    def test_auto_prefers_cuda_when_available(self):
        with patch.object(runtime_device, "torch", FakeTorch(cuda_available=True)):
            self.assertEqual(runtime_device.resolve_torch_device("auto").type, "cuda")
            self.assertEqual(runtime_device.resolve_torch_device("cuda").type, "cuda")
            self.assertEqual(runtime_device.resolve_torch_device("cpu").type, "cpu")
            self.assertTrue(runtime_device.resolve_easyocr_gpu("auto"))

    def test_auto_and_cuda_fall_back_to_cpu_without_cuda(self):
        with patch.object(runtime_device, "torch", FakeTorch(cuda_available=False)):
            self.assertEqual(runtime_device.resolve_torch_device("auto").type, "cpu")
            self.assertEqual(runtime_device.resolve_torch_device("cuda").type, "cpu")
            self.assertEqual(runtime_device.resolve_torch_device("mps").type, "cpu")
            self.assertFalse(runtime_device.resolve_easyocr_gpu("auto"))

    def test_missing_torch_still_resolves_to_cpu_for_lightweight_checks(self):
        with patch.object(runtime_device, "torch", None):
            self.assertEqual(runtime_device.resolve_torch_device("auto").type, "cpu")
            self.assertFalse(runtime_device.resolve_easyocr_gpu("auto"))


if __name__ == "__main__":
    unittest.main()
