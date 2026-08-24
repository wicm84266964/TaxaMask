import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from AntSleap.core.path_identity import (
    canonical_path,
    canonicalize_posix_root_alias,
    path_identity,
    paths_overlap,
    paths_refer_to_same_file,
)
from AntSleap.core.project import ProjectManager


class PathIdentityTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "POSIX root alias test")
    def test_platform_root_alias_is_canonicalized_without_rewriting_children(self):
        root_alias = next(
            (
                candidate
                for candidate in ("/var", "/tmp", "/bin", "/sbin", "/lib")
                if os.path.lexists(candidate)
                and stat.S_ISLNK(os.lstat(candidate).st_mode)
            ),
            None,
        )
        if root_alias is None:
            self.skipTest("no platform root alias is available")

        supplied = os.path.join(root_alias, "folders", "taxamask")
        self.assertEqual(
            canonicalize_posix_root_alias(supplied),
            os.path.join(os.path.realpath(root_alias), "folders", "taxamask"),
        )

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
            self.assertEqual(manager.add_images([str(target_image)], save=False), 0)
            manager.set_image_provenance(str(alias_image), {"source_type": "test"}, save=False)
            manager.update_label(str(alias_image), "Head", [[1, 1], [2, 1], [2, 2]], save=False)

            self.assertEqual(len(manager.project_data["images"]), 1)
            self.assertEqual(len(manager.project_data["labels"]), 1)
            self.assertEqual(len(manager.project_data["image_provenance"]), 1)
            self.assertEqual(manager.get_image_provenance(str(target_image))["source_type"], "test")
            self.assertIn("Head", manager.get_labels(str(target_image)))
            self.assertIn("specimen.png", manager.legacy_json_payload(alias_dir / "project.json")["labels"])

    def test_project_image_identity_cache_rebuilds_after_list_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.png"
            second = root / "second.png"
            first.write_bytes(b"first")
            second.write_bytes(b"second")

            manager = ProjectManager()
            manager.add_images([str(first)], save=False)
            second_path = canonical_path(second)
            manager.project_data["images"] = [second_path]
            manager.project_data["labels"] = {second_path: manager._default_label_entry()}

            self.assertEqual(manager.add_images([str(first)], save=False), 1)
            self.assertEqual(
                {path_identity(path) for path in manager.project_data["images"]},
                {path_identity(first), path_identity(second)},
            )

    def test_paths_overlap_uses_physical_ancestor_for_case_insensitive_nonexistent_child(self):
        root = os.path.abspath(os.path.join("virtual", "case_volume"))
        source = os.path.join(root, "Labels")
        target_parent = os.path.join(root, "labels")
        target = os.path.join(target_parent, "nested.ome.zarr")
        existing_identities = {root.casefold(), source.casefold()}

        def exists(path):
            return os.path.abspath(str(path)).casefold() in existing_identities

        def samefile(left, right):
            return os.path.abspath(str(left)).casefold() == os.path.abspath(str(right)).casefold()

        with patch(
            "AntSleap.core.path_identity.canonical_path",
            side_effect=lambda value: os.path.abspath(str(value)),
        ), patch(
            "AntSleap.core.path_identity.path_identity",
            side_effect=lambda value: os.path.abspath(str(value)),
        ), patch(
            "AntSleap.core.path_identity.os.path.normcase",
            side_effect=lambda value: str(value),
        ), patch(
            "AntSleap.core.path_identity.os.path.commonpath",
            return_value=root,
        ), patch(
            "AntSleap.core.path_identity.os.path.exists",
            side_effect=exists,
        ), patch(
            "AntSleap.core.path_identity.os.path.samefile",
            side_effect=samefile,
        ):
            self.assertTrue(paths_overlap(source, target))

    def test_paths_overlap_keeps_case_sensitive_sibling_directories_distinct(self):
        root = os.path.abspath(os.path.join("virtual", "case_volume"))
        source = os.path.join(root, "Labels")
        sibling = os.path.join(root, "labels")
        target = os.path.join(sibling, "nested.ome.zarr")
        existing_paths = {root, source, sibling}

        def normalized(path):
            return os.path.abspath(str(path))

        with patch(
            "AntSleap.core.path_identity.canonical_path",
            side_effect=normalized,
        ), patch(
            "AntSleap.core.path_identity.path_identity",
            side_effect=normalized,
        ), patch(
            "AntSleap.core.path_identity.os.path.normcase",
            side_effect=lambda value: str(value),
        ), patch(
            "AntSleap.core.path_identity.os.path.commonpath",
            return_value=root,
        ), patch(
            "AntSleap.core.path_identity.os.path.exists",
            side_effect=lambda path: normalized(path) in existing_paths,
        ), patch(
            "AntSleap.core.path_identity.os.path.samefile",
            side_effect=lambda left, right: normalized(left) == normalized(right),
        ):
            self.assertFalse(paths_overlap(source, target))


if __name__ == "__main__":
    unittest.main()
