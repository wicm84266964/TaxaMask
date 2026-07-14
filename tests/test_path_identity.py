import os
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.path_identity import canonical_path, path_identity, paths_refer_to_same_file
from AntSleap.core.project import ProjectManager


class PathIdentityTests(unittest.TestCase):
    def test_relative_and_absolute_paths_share_an_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "specimen.png"
            target.write_bytes(b"image")
            previous = os.getcwd()
            try:
                os.chdir(root)
                self.assertEqual(path_identity("specimen.png"), path_identity(target))
                self.assertTrue(paths_refer_to_same_file("specimen.png", target))
            finally:
                os.chdir(previous)

    def test_realpath_resolves_directory_aliases_when_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target_dir = root / "physical"
            target_dir.mkdir()
            target = target_dir / "specimen.png"
            target.write_bytes(b"image")
            alias_dir = root / "alias"
            try:
                os.symlink(target_dir, alias_dir, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"directory symlinks are unavailable: {exc}")

            alias = alias_dir / target.name
            self.assertEqual(canonical_path(alias), canonical_path(target))
            self.assertTrue(paths_refer_to_same_file(alias, target))

    def test_project_image_state_uses_one_key_across_directory_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target_dir = root / "physical"
            target_dir.mkdir()
            alias_dir = root / "alias"
            try:
                os.symlink(target_dir, alias_dir, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"directory symlinks are unavailable: {exc}")

            target_image = target_dir / "specimen.png"
            target_image.write_bytes(b"image")
            alias_image = alias_dir / target_image.name

            manager = ProjectManager()
            manager.current_project_path = canonical_path(target_dir / "project.json")
            manager.add_images([str(alias_image)], save=False)
            manager.set_image_provenance(str(alias_image), {"source_type": "test"}, save=False)
            manager.update_label(str(alias_image), "Head", [[1, 1], [2, 1], [2, 2]], save=False)

            self.assertEqual(len(manager.project_data["images"]), 1)
            self.assertEqual(len(manager.project_data["labels"]), 1)
            self.assertEqual(len(manager.project_data["image_provenance"]), 1)
            self.assertEqual(manager.get_image_provenance(str(target_image))["source_type"], "test")
            self.assertIn("Head", manager.get_labels(str(target_image)))
            self.assertIn("specimen.png", manager.legacy_json_payload(alias_dir / "project.json")["labels"])


if __name__ == "__main__":
    unittest.main()
