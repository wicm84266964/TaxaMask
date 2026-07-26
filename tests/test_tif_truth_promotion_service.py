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

    def test_promote_selected_ref_persists_whitelisted_review_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            manager = TifProjectManager()
            manager.create_project("truth_service_audit", project_root)
            manager.create_specimen_scaffold("s1")
            manager.add_or_update_label_schema(
                "regions",
                labels=[{"id": 1, "name": "region"}],
                save=False,
            )
            for part_id in ("selected", "unselected"):
                image_rel = f"specimens/s1/parts/{part_id}/image.ome.zarr"
                edit_rel = f"specimens/s1/parts/{part_id}/labels/editable_ai_result.ome.zarr"
                image_meta = write_volume_sidecar(
                    project_root / image_rel,
                    np.zeros((2, 3, 4), dtype=np.uint8),
                    role="part_image",
                )
                edit_meta = write_volume_sidecar(
                    project_root / edit_rel,
                    np.ones((2, 3, 4), dtype=np.uint16),
                    role="editable_ai_result",
                )
                manager.add_part(
                    "s1",
                    part_id,
                    image={"path": image_rel, **image_meta},
                    save=False,
                )
                source = manager.register_part_label_volume(
                    "s1",
                    part_id,
                    "editable_ai_result",
                    edit_rel,
                    edit_meta["shape_zyx"],
                    edit_meta["dtype"],
                    prediction_id=f"prediction-{part_id}",
                    save=False,
                )
                source.update(
                    {
                        "model_id": "tif-model-7",
                        "model_version": "7.2",
                        "reviewer_notes": "notes must not become audit facts",
                    }
                )
                manager.set_part_training_metadata(
                    "s1",
                    part_id,
                    label_schema_id="regions",
                    opened_for_review=True,
                    save=False,
                )

            old_manual_rel = "specimens/s1/parts/selected/labels/manual_truth.ome.zarr"
            old_manual_meta = write_volume_sidecar(
                project_root / old_manual_rel,
                np.zeros((2, 3, 4), dtype=np.uint16),
                role="manual_truth",
            )
            manager.register_part_label_volume(
                "s1",
                "selected",
                "manual_truth",
                old_manual_rel,
                old_manual_meta["shape_zyx"],
                old_manual_meta["dtype"],
                status="reviewed",
                save=True,
            )

            result = TifTruthPromotionService(manager).promote_reviewed_refs(
                [{"specimen_id": "s1", "part_id": "selected"}],
                save=True,
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.payload["count"], 1)
            reloaded = TifProjectManager()
            reloaded.load_project(manager.current_project_path)
            selected_manual = reloaded.get_part("s1", "selected")["labels"]["manual_truth"]
            unselected_manual = reloaded.get_part("s1", "unselected")["labels"]["manual_truth"]
            audit = selected_manual["review_audit"]
            self.assertEqual(
                set(audit),
                {
                    "action",
                    "explicit_review",
                    "reviewed_at",
                    "source_role",
                    "specimen_id",
                    "part_id",
                    "reslice_id",
                    "model_id",
                    "model_version",
                    "prediction_id",
                },
            )
            self.assertEqual(audit["action"], "accept_selected_ai_results")
            self.assertIs(audit["explicit_review"], True)
            self.assertTrue(audit["reviewed_at"])
            self.assertEqual(audit["source_role"], "editable_ai_result")
            self.assertEqual(audit["specimen_id"], "s1")
            self.assertEqual(audit["part_id"], "selected")
            self.assertEqual(audit["reslice_id"], "")
            self.assertEqual(audit["model_id"], "tif-model-7")
            self.assertEqual(audit["model_version"], "7.2")
            self.assertEqual(audit["prediction_id"], "prediction-selected")
            self.assertNotIn("reviewer_notes", audit)
            self.assertFalse(unselected_manual.get("path"))


if __name__ == "__main__":
    unittest.main()
