import unittest

from AntSleap.services.tif_roi_part_service import TifRoiPartService


class TifRoiPartServiceTests(unittest.TestCase):
    def test_confirm_part_roi_request_is_structured_and_sized(self):
        service = TifRoiPartService()

        result = service.build_confirm_part_roi_request(
            specimen_id="s1",
            part_id="brain",
            display_name="Brain",
            bbox_zyx=[[0, 2], [1, 4], [2, 6]],
            source_shape_zyx=[5, 6, 7],
            roi_id="brain_roi",
            roi_keyframes=[{"z": 1}],
        )

        self.assertTrue(result.ok)
        request = result.payload["request"]
        self.assertEqual(request["part_id"], "brain")
        self.assertEqual(service.request_voxel_count(request), 24)
        self.assertTrue(service.should_run_in_background(request, threshold=10))


if __name__ == "__main__":
    unittest.main()
