import unittest

import numpy as np

from AntSleap.core.tif_transfer_function import (
    DEFAULT_TRANSFER_LUT_SIZE,
    TIF_TRANSFER_FUNCTION_SCHEMA_VERSION,
    builtin_transfer_function,
    build_transfer_lut,
    normalize_transfer_function,
)


class TifTransferFunctionTests(unittest.TestCase):
    def test_builtin_transfer_function_has_schema_and_points(self):
        payload = builtin_transfer_function("morphology")

        self.assertEqual(payload["schema_version"], TIF_TRANSFER_FUNCTION_SCHEMA_VERSION)
        self.assertEqual(payload["preset_id"], "morphology")
        self.assertGreaterEqual(len(payload["opacity_points"]), 4)
        self.assertGreaterEqual(len(payload["color_points"]), 4)
        self.assertTrue(payload["gradient_opacity"]["enabled"])

    def test_unknown_preset_normalizes_to_amber(self):
        payload = normalize_transfer_function({"preset_id": "unknown", "window": {"low": -1, "high": 3}})

        self.assertEqual(payload["preset_id"], "amber")
        self.assertEqual(payload["window"]["low"], 0.0)
        self.assertEqual(payload["window"]["high"], 1.0)

    def test_transfer_lut_shape_dtype_and_alpha_ramp(self):
        lut = build_transfer_lut(preset="morphology", opacity=1.0)

        self.assertEqual(lut.shape, (1, DEFAULT_TRANSFER_LUT_SIZE, 4))
        self.assertEqual(lut.dtype, np.uint8)
        self.assertGreater(int(lut[0, -1, 3]), int(lut[0, 4, 3]))

    def test_presets_are_visually_distinct(self):
        amber = build_transfer_lut(preset="amber")
        morphology = build_transfer_lut(preset="morphology")
        publication = build_transfer_lut(preset="publication")

        self.assertFalse((amber[0, 180, :3] == morphology[0, 180, :3]).all())
        self.assertFalse((publication[0, 180, :3] == morphology[0, 180, :3]).all())

    def test_opacity_scales_alpha(self):
        low = build_transfer_lut(preset="publication", opacity=0.5)
        high = build_transfer_lut(preset="publication", opacity=1.0)

        self.assertLess(int(low[0, -1, 3]), int(high[0, -1, 3]))

    def test_custom_payload_roundtrip_keeps_control_points(self):
        payload = {
            "schema_version": TIF_TRANSFER_FUNCTION_SCHEMA_VERSION,
            "preset_id": "custom",
            "window": {"low": 0.1, "high": 0.8},
            "opacity_points": [(0.0, 0.0), (0.5, 0.25), (1.0, 1.0)],
            "color_points": [(0.0, "#000000"), (1.0, "#FFFFFF")],
            "gradient_opacity": {"enabled": True, "low": 0.2, "high": 0.6, "strength": 0.4},
        }

        normalized = normalize_transfer_function(payload)
        lut = build_transfer_lut(normalized)

        self.assertEqual(normalized["preset_id"], "custom")
        self.assertEqual(normalized["opacity_points"], payload["opacity_points"])
        self.assertEqual(normalized["color_points"], payload["color_points"])
        self.assertEqual(normalized["window"], {"low": 0.1, "high": 0.8})
        self.assertEqual(lut.shape, (1, DEFAULT_TRANSFER_LUT_SIZE, 4))


if __name__ == "__main__":
    unittest.main()
