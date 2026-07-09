import tempfile
import unittest
from pathlib import Path

import numpy as np

from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import write_volume_sidecar
from AntSleap.services.tif_truth_promotion_service import TifTruthPromotionService


class TifTruthPromotionServiceTests(unittest.TestCase):
    def test_split_blocks_unreviewed_or_unknown_label_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            manager = TifProjectManager()
            manager.create_project("truth_service", project_root)
            manager.create_specimen_scaffold("s1")
            part_image_rel = "specimens/s1/parts/brain/image.ome.zarr"
            edit_rel = "specimens/s1/parts/brain/labels/editable_ai_result.ome.zarr"
            part_meta = write_volume_sidecar(project_root / part_image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="part_image")
            edit_meta = write_volume_sidecar(project_root / edit_rel, np.full((2, 3, 4), 9, dtype=np.uint16), role="editable_ai_result")
            manager.add_part("s1", "brain", image={"path": part_image_rel, **part_meta}, save=False)
            manager.add_or_update_label_schema("brain_regions", labels=[{"id": 1, "name": "region"}], save=False)
            manager.register_part_label_volume("s1", "brain", "editable_ai_result", edit_rel, edit_meta["shape_zyx"], edit_meta["dtype"], save=False)
            manager.set_part_training_metadata("s1", "brain", label_schema_id="brain_regions", opened_for_review=True, save=True)

            service = TifTruthPromotionService(manager)
            result = service.split_review_acceptance_refs([{"specimen_id": "s1", "part_id": "brain"}])

            self.assertTrue(result.ok)
            self.assertEqual(result.payload["ready"], [])
            self.assertEqual(len(result.payload["blocked"]), 1)
            self.assertIn("unknown_label_ids", result.payload["blocked"][0]["reasons"])


if __name__ == "__main__":
    unittest.main()
