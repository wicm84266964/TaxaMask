# pyright: reportMissingImports=false

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from AntSleap.core.training_preflight import (
    build_training_preflight,
    describe_training_preflight,
    format_size_pair,
    lower_locator_size_options,
)


class TrainingPreflightTests(unittest.TestCase):
    def _make_image(self, root, name, size):
        image_path = Path(root) / name
        Image.new("RGB", size, color=(180, 180, 180)).save(image_path)
        return str(image_path)

    def test_preflight_uses_saved_annotations_not_manifest_or_view(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            img_head = self._make_image(tmp_dir, "head.png", (960, 640))
            img_mandible = self._make_image(tmp_dir, "mandible.png", (640, 640))
            img_empty = self._make_image(tmp_dir, "empty.png", (800, 800))

            labels = {
                img_head: {
                    "parts": {
                        "Head": [[10, 10], [120, 10], [60, 90]],
                    },
                    "boxes": {"Head": [8, 8, 124, 92]},
                },
                img_mandible: {
                    "parts": {
                        "Mandible": [[20, 20], [80, 25], [48, 70]],
                    },
                    "boxes": {},
                },
                img_empty: {"parts": {}, "boxes": {}},
            }

            preflight = build_training_preflight(
                [img_head, img_mandible, img_empty],
                labels,
                taxonomy=["Head", "Mandible"],
                locator_scope=["Head"],
            )

            self.assertEqual(preflight["locator_image_count"], 1)
            self.assertEqual(preflight["parts_image_count"], 2)
            self.assertEqual(preflight["locator_part_counts"]["Head"], 1)
            self.assertEqual(preflight["parts_part_counts"]["Mandible"], 1)
            self.assertIn("Excluded 1 zero-annotation image(s) from training.", preflight["warnings"])
            self.assertEqual(preflight["selected_locator_size"], (960, 640))

    def test_preflight_detects_mixed_native_resolutions_and_uses_smallest_exact_tier(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            img_a = self._make_image(tmp_dir, "a.png", (1200, 900))
            img_b = self._make_image(tmp_dir, "b.png", (640, 640))
            labels = {
                img_a: {"parts": {"Head": [[10, 10], [100, 10], [60, 80]]}, "boxes": {}},
                img_b: {"parts": {"Head": [[20, 20], [90, 20], [55, 75]]}, "boxes": {}},
            }

            preflight = build_training_preflight(
                [img_a, img_b],
                labels,
                taxonomy=["Head"],
                locator_scope=["Head"],
            )

            self.assertTrue(preflight["mixed_native_resolutions"])
            self.assertEqual(preflight["selected_locator_size"], (640, 640))
            self.assertEqual(preflight["locator_exact_size_counts"], {"1200x900": 1, "640x640": 1})
            self.assertEqual(preflight["lower_locator_size_options"], [(544, 544), (448, 448), (352, 352), (256, 256)])

    def test_lower_locator_size_options_preserve_aspect_ratio(self):
        self.assertEqual(lower_locator_size_options((64, 64)), [])
        self.assertEqual(lower_locator_size_options((1000, 500)), [(850, 425), (700, 350), (550, 275), (400, 200)])

    def test_format_size_pair_returns_readable_exact_size(self):
        self.assertEqual(format_size_pair((960, 640)), "960x640")

    def test_preflight_skips_unreviewed_auto_annotated_drafts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            img_draft = self._make_image(tmp_dir, "draft.png", (960, 640))
            img_reviewed = self._make_image(tmp_dir, "reviewed.png", (960, 640))
            labels = {
                img_draft: {
                    "parts": {
                        "Head": [[10, 10], [120, 10], [60, 90]],
                    },
                    "boxes": {"Head": [8, 8, 124, 92]},
                    "descriptions": {"Head": "Auto-Annotated"},
                },
                img_reviewed: {
                    "parts": {
                        "Head": [[15, 15], [110, 15], [62, 92]],
                    },
                    "boxes": {"Head": [12, 12, 112, 94]},
                    "descriptions": {},
                },
            }

            preflight = build_training_preflight(
                [img_draft, img_reviewed],
                labels,
                taxonomy=["Head"],
                locator_scope=["Head"],
            )

            self.assertEqual(preflight["locator_image_count"], 1)
            self.assertEqual(preflight["parts_image_count"], 1)
            self.assertEqual(preflight["excluded_auto_draft_images"], [img_draft])
            self.assertIn(
                "Excluded 1 image(s) with only unreviewed Auto-Annotated drafts from training.",
                preflight["warnings"],
            )

    def test_preflight_reports_train_val_coverage_separately_for_locator_and_parts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            img_a = self._make_image(tmp_dir, "a.png", (960, 640))
            img_b = self._make_image(tmp_dir, "b.png", (960, 640))
            img_c = self._make_image(tmp_dir, "c.png", (960, 640))

            labels = {
                img_a: {
                    "parts": {
                        "Head": [[10, 10], [120, 10], [60, 90]],
                        "Mandible": [[20, 20], [80, 25], [48, 70]],
                    },
                    "boxes": {},
                },
                img_b: {
                    "parts": {
                        "Head": [[15, 15], [110, 15], [62, 92]],
                    },
                    "boxes": {},
                },
                img_c: {
                    "parts": {
                        "Mandible": [[18, 18], [78, 24], [46, 72]],
                    },
                    "boxes": {},
                },
            }

            preflight = build_training_preflight(
                [img_a, img_b, img_c],
                labels,
                taxonomy=["Head", "Mandible"],
                locator_scope=["Head"],
            )

            self.assertEqual(preflight["locator_part_counts"], {"Head": 2})
            self.assertEqual(sum(preflight["locator_train_part_counts"].values()), len(preflight["locator_train_data"]))
            self.assertEqual(sum(preflight["locator_val_part_counts"].values()), len(preflight["locator_val_data"]))
            self.assertEqual(
                preflight["parts_part_counts"],
                {"Head": 2, "Mandible": 2},
            )

            summary = describe_training_preflight(preflight)
            self.assertIn("Locator eligible images: total 2 | train 1 | val 1", summary)
            self.assertIn("SAM/parts eligible images: total 3 | train 2 | val 1", summary)
            self.assertIn("Locator coverage total: Head=2", summary)
            self.assertIn("Locator coverage train: Head=1", summary)
            self.assertIn("Locator coverage val: Head=1", summary)
            self.assertIn("SAM coverage total: Head=2, Mandible=2", summary)
            self.assertIn("SAM coverage train:", summary)
            self.assertIn("SAM coverage val:", summary)


if __name__ == "__main__":
    unittest.main()
