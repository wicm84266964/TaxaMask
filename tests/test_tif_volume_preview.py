import unittest

import numpy as np

from AntSleap.core.tif_volume_preview import (
    build_mask_preview,
    build_volume_preview,
    downsample_volume,
    preview_factors_for_shape,
    preview_shape_for_factors,
)


class TifVolumePreviewTests(unittest.TestCase):
    def test_preview_factors_keep_dimensions_under_limit(self):
        self.assertEqual(preview_factors_for_shape((12, 900, 901), 384), (1, 3, 3))
        self.assertEqual(preview_shape_for_factors((12, 900, 901), (1, 3, 3)), (12, 300, 301))

    def test_hybrid_downsample_preserves_thin_bright_structure_better_than_stride(self):
        volume = np.zeros((4, 8, 8), dtype=np.uint16)
        volume[:, 1::2, 1::2] = 4000

        stride = downsample_volume(volume, (1, 2, 2), mode="stride")
        hybrid = downsample_volume(volume, (1, 2, 2), mode="hybrid")
        maximum = downsample_volume(volume, (1, 2, 2), mode="max")

        self.assertEqual(int(stride.max()), 0)
        self.assertGreater(int(hybrid.max()), 0)
        self.assertEqual(int(maximum.max()), 4000)

    def test_mean_downsample_keeps_weak_density_layer(self):
        volume = np.zeros((4, 8, 8), dtype=np.uint16)
        volume[:, 2:6, 2:6] = 120

        preview = downsample_volume(volume, (1, 2, 2), mode="mean")

        self.assertGreater(int(preview[:, 1:3, 1:3].sum()), 0)
        self.assertEqual(preview.dtype, volume.dtype)

    def test_mean_downsample_handles_non_divisible_edges(self):
        volume = np.arange(3 * 5 * 7, dtype=np.uint16).reshape((3, 5, 7))

        preview = downsample_volume(volume, (2, 3, 4), mode="mean")

        expected = np.empty((2, 2, 2), dtype=np.uint16)
        for oz, z0 in enumerate((0, 2)):
            for oy, y0 in enumerate((0, 3)):
                for ox, x0 in enumerate((0, 4)):
                    block = volume[z0 : min(z0 + 2, 3), y0 : min(y0 + 3, 5), x0 : min(x0 + 4, 7)]
                    expected[oz, oy, ox] = int(round(float(block.mean())))
        np.testing.assert_array_equal(preview, expected)

    def test_hybrid_downsample_handles_non_divisible_edges(self):
        volume = np.arange(3 * 5 * 7, dtype=np.uint16).reshape((3, 5, 7))

        preview = downsample_volume(volume, (2, 3, 4), mode="hybrid")

        expected = np.empty((2, 2, 2), dtype=np.uint16)
        for oz, z0 in enumerate((0, 2)):
            for oy, y0 in enumerate((0, 3)):
                for ox, x0 in enumerate((0, 4)):
                    block = volume[z0 : min(z0 + 2, 3), y0 : min(y0 + 3, 5), x0 : min(x0 + 4, 7)]
                    expected[oz, oy, ox] = int(round(float(block.mean()) * 0.65 + float(block.max()) * 0.35))
        np.testing.assert_array_equal(preview, expected)

    def test_build_volume_preview_normalizes_uint16_when_not_preserving_source(self):
        volume = np.zeros((2, 8, 8), dtype=np.uint16)
        volume[:, 2:6, 2:6] = 1000

        preview = build_volume_preview(volume, 4, mode="hybrid", preserve_source=False)

        self.assertEqual(preview.dtype, np.uint8)
        self.assertEqual(tuple(preview.shape), (2, 4, 4))
        self.assertGreater(int(preview.max()), 0)

    def test_build_volume_preview_preserves_uint16_when_requested(self):
        volume = np.arange(2 * 4 * 4, dtype=np.uint16).reshape((2, 4, 4))

        preview = build_volume_preview(volume, 8, mode="hybrid", preserve_source=True)

        self.assertEqual(preview.dtype, np.uint16)
        np.testing.assert_array_equal(preview, volume)

    def test_mask_occupancy_keeps_small_labels_that_stride_can_miss(self):
        mask = np.zeros((2, 8, 8), dtype=np.uint16)
        mask[:, 1::2, 1::2] = 7

        nearest = build_mask_preview(mask, 4, mode="nearest")
        occupancy = build_mask_preview(mask, 4, mode="occupancy")

        self.assertEqual(int(nearest.max()), 0)
        self.assertEqual(int(occupancy.max()), 1)
        self.assertEqual(occupancy.dtype, np.uint8)


if __name__ == "__main__":
    unittest.main()
