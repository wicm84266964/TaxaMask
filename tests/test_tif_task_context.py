import unittest

from AntSleap.core.tif_task_context import TifTaskContext


class TifTaskContextTests(unittest.TestCase):
    def test_context_key_and_mapping_are_stable(self):
        context = TifTaskContext(
            specimen_id="s1",
            volume_scope="part",
            part_id="head",
            reslice_id="axis-1",
            label_role="editable_ai_result",
            display_mode="volume",
            request_key="preview-1",
        )

        self.assertEqual(context.key()[0], "s1")
        self.assertEqual(TifTaskContext.from_mapping(context.to_dict()), context)

    def test_context_match_can_ignore_empty_fields(self):
        task_context = TifTaskContext(specimen_id="s1", part_id="head", display_mode="volume")

        self.assertTrue(task_context.matches({"specimen_id": "s1", "part_id": "head"}))
        self.assertFalse(task_context.matches({"specimen_id": "s1", "part_id": "thorax"}))
        self.assertTrue(task_context.matches({"specimen_id": "s1"}, fields=("specimen_id",)))


if __name__ == "__main__":
    unittest.main()
