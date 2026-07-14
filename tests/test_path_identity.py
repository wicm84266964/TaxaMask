import os
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.path_identity import canonical_path, path_identity, paths_refer_to_same_file


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


if __name__ == "__main__":
    unittest.main()
