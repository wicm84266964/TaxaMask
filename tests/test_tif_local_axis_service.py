import tempfile
import unittest
from pathlib import Path

from AntSleap.services.tif_local_axis_service import TifLocalAxisService


class TifLocalAxisServiceTests(unittest.TestCase):
    def test_manifest_export_request_adds_template_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = TifLocalAxisService()

            result = service.build_manifest_export_request(None, Path(tmp) / "exports", template_id="brain")

            self.assertTrue(result.ok)
            self.assertEqual(
                result.payload["filters"],
                {"include_unconfirmed": False, "template_id": "brain"},
            )
            self.assertTrue(result.payload["output_dir"].endswith("exports"))

    def test_initial_draft_frame_and_reslice_payload_are_gui_free(self):
        service = TifLocalAxisService()

        draft_result = service.build_initial_draft(
            specimen_id="s1",
            part_id="head",
            source_shape_zyx=(5, 7, 9),
            source_proposal_id="proposal-1",
            source_model_id="axis-model",
            source_model_version="v1",
        )

        self.assertTrue(draft_result.ok)
        draft = draft_result.payload["draft"]
        self.assertEqual(draft["specimen_id"], "s1")
        self.assertEqual(draft["part_id"], "head")
        self.assertEqual(draft["roll_reference"]["pair_id"], "roll_reference_point_pair")
        self.assertEqual(draft["editable_axis"]["source_proposal_id"], "proposal-1")

        draft["roll_reference"]["point_a"] = {"role": "roll_reference_a", "zyx": [2.0, 1.0, 2.0]}
        draft["roll_reference"]["point_b"] = {"role": "roll_reference_b", "zyx": [2.0, 5.0, 6.0]}
        frame_result = service.build_local_frame(draft, spacing_zyx=[1.0, 1.0, 1.0])

        self.assertTrue(frame_result.ok)
        frame = frame_result.payload["frame"]
        self.assertEqual(frame["coordinate_space"], "part_volume_voxel_zyx")

        payload_result = service.build_reslice_payload(
            specimen_id="s1",
            part_id="head",
            draft=draft,
            local_frame=frame,
            source_shape_zyx=(5, 7, 9),
            spacing_zyx=[1.0, 1.0, 1.0],
            reslice_id="head_local_axis_test",
            trainable=True,
        )

        self.assertTrue(payload_result.ok)
        payload = payload_result.payload["payload"]
        self.assertEqual(payload["reslice_id"], "head_local_axis_test")
        self.assertEqual(payload["training"]["source"], "AI proposed + human confirmed")
        self.assertEqual(payload["provenance"]["source_model_id"], "axis-model")
        self.assertEqual(payload["reslice_params"]["coverage"], "full_source_part_bbox")
        self.assertEqual(len(payload["reslice_params"]["output_shape_zyx"]), 3)

    def test_clear_roll_reference_keeps_draft_context(self):
        service = TifLocalAxisService()
        draft = {
            "specimen_id": "s1",
            "part_id": "head",
            "roll_reference": {
                "pair_id": "roll_reference_point_pair",
                "point_a": {"zyx": [1, 2, 3]},
                "point_b": {"zyx": [2, 3, 4]},
                "point_c": {"zyx": [3, 4, 5]},
                "reference_plane": {"normal_axis_zyx": [1, 0, 0]},
            },
            "local_frame": {"ready": True},
        }

        result = service.clear_roll_reference_points(draft)

        self.assertTrue(result.ok)
        clean = result.payload["draft"]
        self.assertEqual(clean["specimen_id"], "s1")
        self.assertEqual(clean["roll_reference"], {"pair_id": "roll_reference_point_pair"})
        self.assertIsNone(clean["local_frame"])
        self.assertTrue(clean["dirty"])


if __name__ == "__main__":
    unittest.main()
