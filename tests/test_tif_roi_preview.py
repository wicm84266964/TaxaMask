import unittest

import numpy as np

from AntSleap.core.tif_roi_preview import (
    build_roi_volume_preview,
    normalize_roi_bbox_zyx,
    roi_crop_view,
    roi_shape_zyx,
    texture_budgeted_max_dim,
)


class TifRoiPreviewTests(unittest.TestCase):
    def test_roi_bbox_crop_and_shape_are_zyx(self):
        volume = np.arange(4 * 6 * 8, dtype=np.uint16).reshape((4, 6, 8))
        bbox = normalize_roi_bbox_zyx([[1, 3], [2, 6], [1, 5]], volume.shape)
        crop = roi_crop_view(volume, bbox)

        self.assertEqual(bbox, [[1, 3], [2, 6], [1, 5]])
        self.assertEqual(roi_shape_zyx(bbox), (2, 4, 4))
        np.testing.assert_array_equal(crop, volume[1:3, 2:6, 1:5])

    def test_roi_bbox_is_clipped_without_going_empty(self):
        bbox = normalize_roi_bbox_zyx([[3, 99], [-4, 2], [4, 4]], (4, 6, 8))

        self.assertEqual(bbox, [[3, 4], [0, 2], [4, 5]])

    def test_texture_budget_reduces_large_roi_target_dim(self):
        full_dim = texture_budgeted_max_dim((64, 256, 256), np.dtype("uint16"), budget_bytes=64 * 256 * 256 * 2)
        reduced_dim = texture_budgeted_max_dim((128, 512, 512), np.dtype("uint16"), budget_bytes=64 * 256 * 256 * 2)

        self.assertEqual(full_dim, 256)
        self.assertLess(reduced_dim, 512)
        self.assertGreaterEqual(reduced_dim, 1)

    def test_build_roi_volume_preview_reads_only_bbox(self):
        volume = np.zeros((4, 8, 8), dtype=np.uint16)
        volume[1:3, 2:6, 1:5] = 5000
        volume[:, 6:, 6:] = 65000

        preview = build_roi_volume_preview(volume, [[1, 3], [2, 6], [1, 5]], 16, preserve_source=True)

        self.assertEqual(tuple(preview.shape), (2, 4, 4))
        self.assertEqual(preview.dtype, np.uint16)
        self.assertEqual(int(preview.max()), 5000)


if __name__ == "__main__":
    unittest.main()
