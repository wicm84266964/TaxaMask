import unittest

from AntSleap.services.tif_volume_preview_service import TifVolumePreviewService


class TifVolumePreviewServiceTests(unittest.TestCase):
    def test_preview_request_has_stable_cache_key(self):
        service = TifVolumePreviewService()

        result = service.build_preview_request(
            volume_path="specimens/s1/working/image.ome.zarr",
            label_path="specimens/s1/labels/working_edit.ome.zarr",
            mode="still",
            roi_bbox=[[0, 2], [0, 3], [0, 4]],
            mask_mode="mask_overlay",
            specimen_id="s1",
            budget_bytes=123,
        )

        self.assertTrue(result.ok)
        request = result.payload["request"]
        self.assertEqual(request["budget_bytes"], 123)
        self.assertEqual(request["owner"], ("s1", "", ""))
        self.assertIn("mask_overlay", request["cache_key"])

    def test_workbench_preview_request_preserves_cache_contract(self):
        service = TifVolumePreviewService()

        result = service.build_workbench_preview_request(
            owner=("s1", "full", "", ""),
            shape=(12, 24, 36),
            source_dtype="uint16",
            max_dim=512,
            preserve_source=True,
            algorithm="mean",
            roi_bbox=[[1, 5], [2, 8], [3, 9]],
            texture_budget_bytes=1024,
            mode="still",
            message="Preparing ROI crop preview...",
        )

        self.assertTrue(result.ok)
        request = result.payload["request"]
        self.assertEqual(request["owner"], ("s1", "full", "", ""))
        self.assertEqual(request["shape"], (12, 24, 36))
        self.assertEqual(request["roi_key"], ((1, 5), (2, 8), (3, 9)))
        self.assertEqual(
            request["cache_key"],
            (
                ("s1", "full", "", ""),
                (12, 24, 36),
                "uint16",
                512,
                True,
                "mean",
                ((1, 5), (2, 8), (3, 9)),
                1024,
            ),
        )

    def test_mask_preview_request_preserves_mask_identity(self):
        service = TifVolumePreviewService()

        result = service.build_mask_preview_request(
            owner=("s1", "part", "head", ""),
            shape=(5, 6, 7),
            source_dtype="uint16",
            max_dim=256,
            mask_identity=12345,
            algorithm="occupancy",
            mode="drag",
            message="Preparing mask preview...",
        )

        self.assertTrue(result.ok)
        request = result.payload["request"]
        self.assertEqual(request["mode"], "drag")
        self.assertEqual(request["cache_key"], (("s1", "part", "head", ""), (5, 6, 7), "uint16", 256, 12345, "occupancy", None))


if __name__ == "__main__":
    unittest.main()
