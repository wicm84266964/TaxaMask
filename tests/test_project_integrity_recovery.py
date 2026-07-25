import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from AntSleap.core.project import ProjectManager
from AntSleap.core.project_integrity_recovery import (
    inspect_project_integrity,
    register_current_asset_version,
    write_redacted_integrity_diagnostic,
)


class ProjectIntegrityRecoveryTests(unittest.TestCase):
    def test_inspection_reports_progress_and_can_be_cancelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "ant.png"
            Image.new("RGB", (8, 8), color=(1, 2, 3)).save(source)
            manager = ProjectManager()
            manager.location_registry_database_path = root / "locations.sqlite"
            manager.create_project("cancel_recovery", root / "project")
            manager.add_images([str(source)], save=True)
            manager.initialize_integrity_baseline()
            progress = []

            with self.assertRaisesRegex(RuntimeError, "integrity_check_cancelled"):
                inspect_project_integrity(
                    manager,
                    progress_callback=lambda current, total, role: progress.append(
                        (current, total, role)
                    ),
                    cancel_check=lambda: bool(progress),
                )
            self.assertTrue(progress)

    def test_inspection_and_registration_reject_linked_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            manager = ProjectManager()
            manager.location_registry_database_path = root / "locations.sqlite"
            manager.create_project("linked_recovery", project_root)
            source_dir = project_root / "source"
            source_dir.mkdir()
            image = source_dir / "ant.png"
            Image.new("RGB", (8, 8), color=(1, 2, 3)).save(image)
            manager.add_images([str(image)], save=True)
            manager.initialize_integrity_baseline()

            relocated = root / "relocated_source"
            source_dir.rename(relocated)
            try:
                source_dir.symlink_to(relocated, target_is_directory=True)
            except (OSError, NotImplementedError):
                relocated.rename(source_dir)
                self.skipTest("This workstation cannot create directory symlinks")

            report = inspect_project_integrity(manager)
            source = next(
                item for item in report["items"] if item["role"] == "source_image"
            )

            self.assertEqual(source["status"], "incomplete")
            self.assertEqual(source["error_code"], "source_path_unsafe")
            with self.assertRaisesRegex(ValueError, "source_path_unsafe"):
                register_current_asset_version(
                    manager,
                    source,
                    note="This linked path must never become a trusted revision.",
                )

    def test_managed_relative_escape_is_rejected_even_when_content_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            manager = ProjectManager()
            manager.location_registry_database_path = root / "locations.sqlite"
            manager.create_project("escape_recovery", project_root)
            source_dir = project_root / "source"
            source_dir.mkdir()
            image = source_dir / "ant.png"
            Image.new("RGB", (8, 8), color=(1, 2, 3)).save(image)
            manager.add_images([str(image)], save=True)
            manager.initialize_integrity_baseline()

            outside = root / "outside" / "ant.png"
            outside.parent.mkdir()
            outside.write_bytes(image.read_bytes())
            image_uid = manager.get_image_uid(str(image))
            connection = sqlite3.connect(manager.current_database_path)
            try:
                connection.execute(
                    """
                    UPDATE integrity_locations
                    SET relative_path = ?
                    WHERE is_active = 1
                      AND location_kind = 'managed_relative'
                      AND asset_id = (
                          SELECT asset_id
                          FROM integrity_assets
                          WHERE owner_kind = 'image'
                            AND owner_key = ?
                            AND role = 'source_image'
                      )
                    """,
                    ("../outside/ant.png", image_uid),
                )
                connection.commit()
            finally:
                connection.close()

            report = inspect_project_integrity(manager)
            source = next(
                item for item in report["items"] if item["role"] == "source_image"
            )
            self.assertEqual(source["status"], "incomplete")
            self.assertEqual(source["error_code"], "source_path_unsafe")
            with self.assertRaisesRegex(ValueError, "source_path_unsafe"):
                register_current_asset_version(
                    manager,
                    source,
                    note="An escaped managed path must not become trusted.",
                )

    def test_missing_external_file_still_has_a_per_file_recovery_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            external = root / "external" / "ant.png"
            external.parent.mkdir()
            Image.new("RGB", (8, 8), color=(4, 5, 6)).save(external)
            manager = ProjectManager()
            manager.location_registry_database_path = root / "locations.sqlite"
            manager.create_project("missing_external", root / "project")
            manager.add_images([str(external)], save=True)
            manager.initialize_integrity_baseline()
            external.unlink()

            report = inspect_project_integrity(manager)
            source = next(
                item for item in report["items"] if item["role"] == "source_image"
            )
            self.assertEqual(report["status"], "needs_attention")
            self.assertEqual(source["status"], "missing")
            self.assertEqual(source["error_code"], "source_missing")

    def test_inspection_exposes_mismatch_but_diagnostic_redacts_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            source_root = root / "private_source"
            source_root.mkdir()
            image = source_root / "ant.png"
            Image.new("RGB", (8, 8), color=(1, 2, 3)).save(image)
            manager = ProjectManager()
            manager.location_registry_database_path = root / "locations.sqlite"
            manager.create_project("recovery", project_root)
            manager.add_images([str(image)], save=True)
            manager.update_label(
                str(image), "Head", [[1, 1], [6, 1], [3, 6]], save=True
            )
            manager.initialize_integrity_baseline()
            Image.new("RGB", (8, 8), color=(9, 8, 7)).save(image)

            report = inspect_project_integrity(manager)

            source = next(item for item in report["items"] if item["role"] == "source_image")
            self.assertEqual(source["status"], "mismatch")
            self.assertEqual(source["error_code"], "source_digest_mismatch")
            self.assertEqual(source["runtime_path"], str(image.resolve()))
            diagnostic = root / "diagnostic.json"
            write_redacted_integrity_diagnostic(report, diagnostic)
            text = diagnostic.read_text(encoding="utf-8")
            payload = json.loads(text)
            self.assertEqual(payload["schema_version"], "taxamask_integrity_diagnostic_v1")
            self.assertNotIn(str(root.resolve()), text)
            self.assertEqual(
                next(item for item in payload["items"] if item["role"] == "source_image")["file_name"],
                "ant.png",
            )

            previous_version = manager.project_data["project_data_version_id"]
            register_current_asset_version(
                manager,
                source,
                note="Researcher intentionally replaced the source scan.",
            )
            self.assertNotEqual(
                manager.project_data["project_data_version_id"], previous_version
            )
            self.assertTrue(inspect_project_integrity(manager)["status"] == "verified")


if __name__ == "__main__":
    unittest.main()
