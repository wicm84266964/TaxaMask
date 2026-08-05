import unittest

import numpy as np

from scripts.prepare_brain_region_input import resolve_spacing_zyx_um
from AntSleap.core.tif_brain_input_cleaning import (
    DEFAULT_REGION_INPUT_PROFILE,
    centered_crop_bounds,
    largest_component,
    prepare_brain_region_input,
    prepare_locator_candidate,
)


class TifBrainInputCleaningTests(unittest.TestCase):
    def test_cli_rejects_unverified_default_spacing(self):
        with self.assertRaisesRegex(ValueError, "verified_spacing_zyx_um_is_required"):
            resolve_spacing_zyx_um(
                None,
                {
                    "spacing_zyx": [1.0, 1.0, 1.0],
                    "spacing_unit": "unknown",
                    "scale_verified": False,
                },
            )

    def test_cli_converts_verified_nifti_spacing_to_micrometers(self):
        self.assertEqual(
            resolve_spacing_zyx_um(
                None,
                {
                    "spacing_zyx": [0.0054, 0.0054, 0.0054],
                    "spacing_unit": "millimeter",
                    "scale_verified": True,
                },
            ),
            [5.4, 5.4, 5.4],
        )

    def test_cli_accepts_explicit_micrometer_spacing_for_plain_tiff(self):
        self.assertEqual(
            resolve_spacing_zyx_um(
                [5.4, 5.4, 6.0],
                {"scale_verified": False, "spacing_unit": "unknown"},
            ),
            [5.4, 5.4, 6.0],
        )

    def test_default_context_preserves_boundary_texture_without_retaining_full_head(self):
        self.assertEqual(DEFAULT_REGION_INPUT_PROFILE["context_margin_um"], 20.0)

    def test_largest_component_removes_prediction_fragments(self):
        mask = np.zeros((12, 14, 16), dtype=np.uint8)
        mask[3:9, 4:11, 5:13] = 1
        mask[0, 0, 0] = 1

        selected, audit = largest_component(mask)

        self.assertEqual(int(selected.sum()), 6 * 7 * 8)
        self.assertEqual(audit["component_count"], 2)
        self.assertGreater(audit["largest_component_dominance"], 0.99)

    def test_cleaning_uses_only_accepted_largest_component_and_backgrounds_context(self):
        volume = np.arange(40 * 40 * 40, dtype=np.uint16).reshape((40, 40, 40))
        prediction = np.zeros_like(volume, dtype=np.uint8)
        prediction[12:28, 12:28, 12:28] = 2
        prediction[2:5, 2:5, 2:5] = 2
        prediction[30:35, 30:35, 30:35] = 1

        cleaned, mask, audit = prepare_brain_region_input(
            volume,
            prediction,
            [5.4, 5.4, 5.4],
            profile={
                "crop_margin_um": 10.8,
                "context_margin_um": 0.0,
                "training_fov_min_zyx_um": [1, 1, 1],
                "training_fov_max_zyx_um": [1000, 1000, 1000],
                "mask_fraction_range": [0.01, 0.99],
            },
        )

        self.assertEqual(cleaned.shape, (20, 20, 20))
        self.assertEqual(int(mask.sum()), 16**3)
        self.assertEqual(audit["component_count"], 2)
        self.assertEqual(audit["status"], "ready")
        background = audit["background_value"]
        self.assertTrue(np.all(cleaned[mask == 0] == background))

    def test_oversized_prediction_fails_closed_and_proposes_locator_crop(self):
        volume = np.zeros((100, 100, 100), dtype=np.uint8)
        prediction = np.zeros_like(volume)
        prediction[5:95, 5:95, 5:95] = 2

        _cleaned, _mask, audit = prepare_brain_region_input(
            volume,
            prediction,
            [10.0, 10.0, 10.0],
        )

        self.assertEqual(audit["status"], "requires_review")
        self.assertFalse(audit["quality_gate"]["physical_fov_pass"])
        self.assertFalse(audit["quality_gate"]["automatic_prediction_allowed"])
        starts, stops = audit["locator_fallback_bbox_zyx_exclusive"]
        self.assertTrue(all(stop > start for start, stop in zip(starts, stops)))

    def test_centered_crop_clips_without_changing_requested_size(self):
        starts, stops = centered_crop_bounds(
            [20, 30, 40],
            [1, 2, 3],
            [2.0, 2.0, 2.0],
            [20.0, 20.0, 20.0],
        )
        np.testing.assert_array_equal(starts, [0, 0, 0])
        np.testing.assert_array_equal(stops - starts, [10, 10, 10])

    def test_locator_candidate_is_review_crop_resampled_to_target_spacing(self):
        volume = np.arange(20 * 20 * 20, dtype=np.uint16).reshape((20, 20, 20))

        candidate, spacing = prepare_locator_candidate(
            volume,
            [2.0, 2.0, 2.0],
            [[5, 5, 5], [15, 15, 15]],
            [4.0, 4.0, 4.0],
        )

        self.assertEqual(candidate.shape, (5, 5, 5))
        np.testing.assert_allclose(spacing, [4.0, 4.0, 4.0])

    def test_empty_mask_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "mask_is_empty"):
            prepare_brain_region_input(
                np.zeros((5, 5, 5), dtype=np.uint8),
                np.zeros((5, 5, 5), dtype=np.uint8),
                [1.0, 1.0, 1.0],
            )


if __name__ == "__main__":
    unittest.main()
