import unittest

from AntSleap.core.annotation_display import (
    CAT_CONFIRMED_ONLY,
    CAT_DRAFT_ONLY,
    CAT_MIXED,
    CAT_UNLABELED,
    SCREEN_CONFIRMED,
    SCREEN_EMPTY,
    SCREEN_PENDING,
    classify_image_entry,
    classify_part,
)
from AntSleap.core.training_truth import (
    TRAINING_REVIEW_CONFIRMED,
    TRAINING_REVIEW_DRAFT,
    TRAINING_SOURCE_MANUAL,
    TRAINING_SOURCE_MODEL,
    set_part_training_truth,
)


class AnnotationDisplayTests(unittest.TestCase):
    def _polygon(self):
        return [[1.0, 1.0], [8.0, 1.0], [4.0, 7.0]]

    def test_draft_and_confirmed_parts_make_pending_screen_and_mixed_category(self):
        entry = {"parts": {"Head": self._polygon(), "Eye": self._polygon()}, "descriptions": {}}
        set_part_training_truth(
            entry,
            "Head",
            source=TRAINING_SOURCE_MANUAL,
            review_status=TRAINING_REVIEW_CONFIRMED,
            accepted_via="manual_edit",
        )
        set_part_training_truth(
            entry,
            "Eye",
            source=TRAINING_SOURCE_MODEL,
            review_status=TRAINING_REVIEW_DRAFT,
            accepted_via="",
        )
        image = classify_image_entry(entry)
        self.assertEqual(image["category"], CAT_MIXED)
        self.assertEqual(image["screen"], SCREEN_PENDING)
        self.assertEqual(classify_part(entry, "Eye")["kind"], "draft")
        self.assertEqual(classify_part(entry, "Head")["kind"], "confirmed")

    def test_empty_image_is_unlabeled(self):
        image = classify_image_entry({})
        self.assertEqual(image["category"], CAT_UNLABELED)
        self.assertEqual(image["screen"], SCREEN_EMPTY)

    def test_confirmed_only_image(self):
        entry = {"parts": {"Head": self._polygon()}}
        image = classify_image_entry(entry)
        self.assertEqual(image["category"], CAT_CONFIRMED_ONLY)
        self.assertEqual(image["screen"], SCREEN_CONFIRMED)

    def test_box_only_is_pending_draft_category(self):
        entry = {"auto_boxes": {"Mandible": [1, 1, 8, 8]}}
        image = classify_image_entry(entry)
        self.assertEqual(image["category"], CAT_DRAFT_ONLY)
        self.assertEqual(image["screen"], SCREEN_PENDING)
