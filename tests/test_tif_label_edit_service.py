import unittest

import numpy as np

from AntSleap.services.tif_label_edit_service import TifLabelEditService


class TifLabelEditServiceTests(unittest.TestCase):
    def test_build_save_request_copies_dirty_slices_and_checks_role(self):
        service = TifLabelEditService()
        edit = np.arange(3 * 4 * 5, dtype=np.uint16).reshape((3, 4, 5))

        result = service.build_save_request(
            edit_volume=edit,
            dirty_slices={0, 2},
            edit_slice_revisions={0: 3, 2: 4},
            edit_path="labels/working_edit.ome.zarr",
            scope="top_level",
            specimen_id="s1",
            role="working_edit",
            reason="manual",
        )

        self.assertTrue(result.ok)
        request = result.payload["request"]
        self.assertEqual(sorted(request["slices"].keys()), [0, 2])
        self.assertEqual(request["slice_revisions"], {0: 3, 2: 4})
        edit[0, 0, 0] = 999
        self.assertNotEqual(int(request["slices"][0][0, 0]), 999)

    def test_raw_backup_save_is_blocked(self):
        service = TifLabelEditService()

        result = service.build_save_request(
            edit_volume=np.zeros((2, 3, 4), dtype=np.uint16),
            dirty_slices={0},
            edit_path="labels/raw_ai_prediction_backup.ome.zarr",
            scope="part",
            role="raw_ai_prediction_backup",
            reason="manual",
        )

        self.assertFalse(result.ok)
        self.assertIn("raw_ai_prediction_backup_is_read_only", result.reasons)


if __name__ == "__main__":
    unittest.main()
