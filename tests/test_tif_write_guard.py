import tempfile
import unittest
from pathlib import Path

from AntSleap.core.tif_write_guard import WriteIntent, can_write_path


class TifWriteGuardTests(unittest.TestCase):
    def test_write_intent_blocks_source_and_outside_project_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            project_root.mkdir()
            source = project_root / "source" / "original.tif"
            source.parent.mkdir()
            source.write_bytes(b"raw")
            target = project_root / "labels" / "working_edit.ome.zarr"

            allowed = can_write_path(
                WriteIntent(
                    target_path=str(target),
                    project_root=str(project_root),
                    source_path=str(source),
                    source_role="source_tif",
                    target_role="working_edit",
                    operation="label_save",
                    audit_metadata={"specimen_id": "01"},
                    allowed_roots=(str(project_root),),
                )
            )
            self.assertTrue(allowed.allowed)

            source_overwrite = can_write_path(
                WriteIntent(
                    target_path=str(source),
                    project_root=str(project_root),
                    source_path=str(source),
                    source_role="source_tif",
                    target_role="working_edit",
                    operation="label_save",
                    allow_overwrite=True,
                    allowed_roots=(str(project_root),),
                )
            )
            self.assertFalse(source_overwrite.allowed)
            self.assertEqual(source_overwrite.reason, "write_target_matches_protected_source")

            outside = can_write_path(
                WriteIntent(
                    target_path=str(root / "outside.ome.zarr"),
                    project_root=str(project_root),
                    target_role="working_edit",
                    operation="label_save",
                    allowed_roots=(str(project_root),),
                )
            )
            self.assertFalse(outside.allowed)
            self.assertEqual(outside.reason, "write_target_outside_allowed_roots")

    def test_existing_target_requires_overwrite_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "existing.ome.zarr"
            target.mkdir()

            blocked = can_write_path(
                WriteIntent(
                    target_path=str(target),
                    project_root=str(root),
                    target_role="raw_ai_prediction_backup",
                    operation="prediction_import",
                    allowed_roots=(str(root),),
                    allow_overwrite=False,
                )
            )
            self.assertFalse(blocked.allowed)
            self.assertEqual(blocked.reason, "write_target_exists_without_overwrite_intent")

            allowed = can_write_path(
                WriteIntent(
                    target_path=str(target),
                    project_root=str(root),
                    target_role="raw_ai_prediction_backup",
                    operation="prediction_import",
                    allowed_roots=(str(root),),
                    allow_overwrite=True,
                )
            )
            self.assertTrue(allowed.allowed)


if __name__ == "__main__":
    unittest.main()
