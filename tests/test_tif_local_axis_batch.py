import tempfile
import unittest
from pathlib import Path

import numpy as np

from AntSleap.core.tif_local_axis_baseline import (
    add_baseline_local_frame_proposal,
    add_baseline_local_frame_proposals,
)
from AntSleap.core.tif_local_axis_batch import (
    accept_local_frame_proposal,
    batch_export_accepted_reslices,
    list_local_axis_queue,
    proposal_to_reslice_payload,
)
from AntSleap.core.tif_local_axis_reslice import compute_local_frame
from AntSleap.core.tif_part_extraction import crop_volume_to_part
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import load_volume_sidecar, write_volume_sidecar


def make_project_with_frame_proposal(root, spacing_zyx=None, include_local_frame=True):
    project_root = root / "batch_project"
    manager = TifProjectManager()
    manager.create_project("batch_project", project_root)
    manager.create_specimen_scaffold("01-0101-batch")
    image = np.arange(5 * 6 * 7, dtype=np.uint16).reshape((5, 6, 7))
    image_rel = "specimens/01-0101-batch/working/image.ome.zarr"
    image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image", spacing_zyx=spacing_zyx)
    manager.register_working_volume("01-0101-batch", image_rel, image_meta["shape_zyx"], image_meta["dtype"], spacing_zyx=image_meta.get("spacing_zyx"), save=False)
    manager.save_project()
    crop_volume_to_part(manager, "01-0101-batch", "head", [[1, 5], [1, 5], [1, 6]], display_name="Head")
    proposal = {
        "frame_proposal_id": "frame_001",
        "template_id": "head",
        "origin_zyx": [1.5, 1.5, 2.0],
        "output_axis_start_zyx": [0.0, 1.5, 2.0],
        "output_axis_end_zyx": [3.0, 1.5, 2.0],
        "roll_reference": {
            "point_a": {"role": "left_eye", "zyx": [1.5, 1.0, 1.0]},
            "point_b": {"role": "right_eye", "zyx": [1.5, 3.0, 1.0]},
        },
        "confidence": 0.9,
    }
    if include_local_frame:
        proposal["local_frame"] = compute_local_frame(
            proposal["origin_zyx"],
            proposal["output_axis_start_zyx"],
            proposal["output_axis_end_zyx"],
            roll_reference=proposal["roll_reference"],
            spacing_zyx=spacing_zyx,
        )
    manager.add_local_frame_proposal("01-0101-batch", "head", proposal)
    return manager


class TifLocalAxisBatchTests(unittest.TestCase):
    def test_queue_lists_pending_frame_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_project_with_frame_proposal(Path(tmp))

            rows = list_local_axis_queue(manager, {"status": "proposed"})

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["proposal_id"], "frame_001")
            self.assertEqual(rows[0]["kind"], "local_frame_proposal")

    def test_queue_lists_no_part_part_ready_and_failed_rows_without_duplicate_legacy_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_project_with_frame_proposal(root)
            manager.create_specimen_scaffold("01-0101-no-part")
            manager.create_specimen_scaffold("01-0101-ready")
            ready_image = np.zeros((3, 4, 5), dtype=np.uint8)
            ready_rel = "specimens/01-0101-ready/working/image.ome.zarr"
            ready_meta = write_volume_sidecar(root / "batch_project" / ready_rel, ready_image, role="working_image")
            manager.register_working_volume("01-0101-ready", ready_rel, ready_meta["shape_zyx"], ready_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-ready", "head", [[0, 3], [0, 4], [0, 5]], display_name="Head")
            part = manager.get_part("01-0101-ready", "head")
            part.setdefault("metadata", {}).setdefault("local_axis_batch_failures", []).append(
                {
                    "failure_id": "failed_frame_002",
                    "proposal_id": "frame_002",
                    "template_id": "head",
                    "reason": "ValueError",
                    "detail": "bad roll reference",
                }
            )
            manager.save_project()

            all_rows = list_local_axis_queue(manager, {"status": "all"})
            no_part_rows = list_local_axis_queue(manager, {"status": "no_part"})
            part_ready_rows = list_local_axis_queue(manager, {"status": "part_ready"})
            no_proposal_rows = list_local_axis_queue(manager, {"status": "no_proposal"})
            failed_rows = list_local_axis_queue(manager, {"status": "failed"})

            self.assertEqual([row["specimen_id"] for row in no_part_rows], ["01-0101-no-part"])
            self.assertEqual([row["specimen_id"] for row in part_ready_rows], ["01-0101-ready"])
            self.assertEqual([row["status"] for row in no_proposal_rows], ["no_proposal"])
            self.assertEqual([row["status"] for row in all_rows if row["specimen_id"] == "01-0101-ready" and row["kind"] == "part"], ["part_ready"])
            self.assertEqual(failed_rows[0]["status"], "failed")
            self.assertEqual(failed_rows[0]["failure_reason"], "ValueError")

    def test_queue_filters_by_model_version_hard_flag_and_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_project_with_frame_proposal(Path(tmp))
            manager.add_local_frame_proposal(
                "01-0101-batch",
                "head",
                {
                    "frame_proposal_id": "frame_002",
                    "template_id": "head",
                    "origin_zyx": [1.5, 1.5, 2.0],
                    "output_axis_start_zyx": [0.0, 1.5, 2.0],
                    "output_axis_end_zyx": [3.0, 1.5, 2.0],
                    "confidence": 0.1,
                    "model_version": "v2",
                    "hard_case_flags": ["twisted_pose"],
                },
            )

            hard_rows = list_local_axis_queue(manager, {"status": "hard_cases", "model_version": "v2"})
            sorted_rows = list_local_axis_queue(manager, {"status": "all", "sort": "confidence_asc"})
            version_rows = list_local_axis_queue(manager, {"status": "all", "model_version": "v2"})

            self.assertEqual([row["proposal_id"] for row in hard_rows], ["frame_002"])
            self.assertEqual(sorted_rows[0]["proposal_id"], "frame_002")
            self.assertEqual([row["kind"] for row in version_rows], ["local_frame_proposal"])

    def test_unaccepted_proposal_cannot_be_converted_to_reslice_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_project_with_frame_proposal(Path(tmp))
            proposal = manager.get_local_frame_proposal("01-0101-batch", "head", "frame_001")

            with self.assertRaisesRegex(ValueError, "not_accepted"):
                proposal_to_reslice_payload(proposal)

    def test_batch_export_only_exports_accepted_proposals(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_project_with_frame_proposal(Path(tmp))
            first = batch_export_accepted_reslices(manager, ["frame_001"])
            self.assertEqual(len(first["exported"]), 0)
            self.assertEqual(first["skipped"][0]["reason"], "not_accepted")

            accept_local_frame_proposal(manager, "01-0101-batch", "head", "frame_001")
            second = batch_export_accepted_reslices(manager, ["frame_001"], reslice_params={"output_shape_zyx": [4, 4, 5]})

            self.assertEqual(len(second["exported"]), 1)
            self.assertEqual(second["run"]["action"], "batch_reslice_export")
            self.assertEqual(second["run"]["metrics"]["exported_count"], 1)
            self.assertEqual(manager.get_local_frame_proposal("01-0101-batch", "head", "frame_001")["status"], "exported")
            self.assertEqual(manager.list_part_reslices("01-0101-batch", "head")[0]["reslice_id"], "frame_001_reslice")
            self.assertEqual(manager.list_local_axis_runs()[-1]["action"], "batch_reslice_export")

    def test_batch_export_records_failures_and_keeps_exporting_other_accepted_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_project_with_frame_proposal(root)
            manager.create_specimen_scaffold("01-0101-good")
            image = np.arange(5 * 6 * 7, dtype=np.uint16).reshape((5, 6, 7))
            image_rel = "specimens/01-0101-good/working/image.ome.zarr"
            image_meta = write_volume_sidecar(root / "batch_project" / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-good", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-good", "head", [[1, 5], [1, 5], [1, 6]], display_name="Head")
            manager.add_local_frame_proposal(
                "01-0101-good",
                "head",
                {
                    "frame_proposal_id": "frame_good",
                    "template_id": "head",
                    "origin_zyx": [1.5, 1.5, 2.0],
                    "output_axis_start_zyx": [0.0, 1.5, 2.0],
                    "output_axis_end_zyx": [3.0, 1.5, 2.0],
                    "roll_reference": {
                        "point_a": {"role": "left_eye", "zyx": [1.5, 1.0, 1.0]},
                        "point_b": {"role": "right_eye", "zyx": [1.5, 3.0, 1.0]},
                    },
                    "status": "accepted",
                },
                save=False,
            )
            accept_local_frame_proposal(manager, "01-0101-batch", "head", "frame_001")
            bad = manager.get_local_frame_proposal("01-0101-batch", "head", "frame_001")
            bad["roll_reference"] = {
                "point_a": {"role": "left_eye", "zyx": [1.5, 1.0, 1.0]},
                "point_b": {"role": "right_eye", "zyx": [1.5, 1.0, 1.0]},
            }
            manager.save_project()

            result = batch_export_accepted_reslices(manager, reslice_params={"output_shape_zyx": [4, 4, 5]})

            self.assertEqual(len(result["exported"]), 1)
            self.assertEqual(len(result["skipped"]), 1)
            self.assertEqual(result["run"]["result_status"], "partial_success")
            self.assertEqual(manager.get_local_frame_proposal("01-0101-good", "head", "frame_good")["status"], "exported")
            self.assertEqual(manager.get_local_frame_proposal("01-0101-batch", "head", "frame_001")["status"], "accepted")
            failed_rows = list_local_axis_queue(manager, {"status": "failed"})
            self.assertEqual(len(failed_rows), 1)
            self.assertEqual(failed_rows[0]["proposal_id"], "frame_001")
            self.assertIn("roll_reference", failed_rows[0]["failure_detail"])

            reloaded = TifProjectManager()
            reloaded.load_project(manager.current_project_path)
            reloaded_failures = list_local_axis_queue(reloaded, {"status": "failed"})
            self.assertEqual(reloaded_failures[0]["proposal_id"], "frame_001")

    def test_batch_export_recomputes_proposal_frame_with_part_spacing(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_project_with_frame_proposal(Path(tmp), spacing_zyx=[2.0, 1.0, 1.0], include_local_frame=False)
            accept_local_frame_proposal(manager, "01-0101-batch", "head", "frame_001")

            result = batch_export_accepted_reslices(manager, ["frame_001"], reslice_params={"output_shape_zyx": [4, 4, 5]})

            self.assertEqual(len(result["exported"]), 1)
            reslice = manager.list_part_reslices("01-0101-batch", "head")[0]
            self.assertEqual(reslice["local_frame"]["spacing_zyx"], [2.0, 1.0, 1.0])

    def test_baseline_proposal_uses_source_z_fallback_for_empty_mask(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_project_with_frame_proposal(Path(tmp))

            proposal = add_baseline_local_frame_proposal(manager, "01-0101-batch", "head", proposal_id="baseline_empty")

            self.assertEqual(proposal["status"], "needs_review")
            self.assertEqual(proposal["model_version"], "baseline_v1")
            self.assertIn("source_z_fallback", proposal["hard_case_flags"])
            self.assertEqual(proposal["provenance"]["creates_final_reslice"], False)

    def test_baseline_proposal_uses_part_mask_pca_when_mask_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_project_with_frame_proposal(Path(tmp))
            part = manager.get_part("01-0101-batch", "head")
            mask_path = manager.to_absolute(part["mask"]["path"])
            mask = load_volume_sidecar(mask_path)
            mask[:] = 0
            mask[1:4, 1:3, 1:3] = 1
            write_volume_sidecar(mask_path, mask, role="part_mask")

            result = add_baseline_local_frame_proposals(
                manager,
                specimen_ids=["01-0101-batch"],
                part_ids_by_specimen={"01-0101-batch": ["head"]},
                template_id="head",
            )

            self.assertEqual(len(result["proposals"]), 1)
            proposal = result["proposals"][0]
            self.assertEqual(proposal["status"], "needs_review")
            self.assertEqual(proposal["provenance"]["axis_source"], "part_mask_pca")
            self.assertIn("baseline_pca_initial_axis", proposal["hard_case_flags"])
            self.assertEqual(result["run"]["action"], "baseline_local_frame_proposal")


if __name__ == "__main__":
    unittest.main()
