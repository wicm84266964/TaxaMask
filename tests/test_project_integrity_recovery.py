import json
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
