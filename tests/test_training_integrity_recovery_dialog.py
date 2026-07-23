import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtWidgets import QApplication, QFileDialog

from AntSleap.core.project import ProjectManager
from AntSleap.ui.training_integrity_recovery_dialog import (
    TrainingIntegrityRecoveryDialog,
)


class TrainingIntegrityRecoveryDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_lists_mismatch_with_expected_and_observed_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            source = root / "source.png"
            Image.new("RGB", (8, 8), color=(1, 2, 3)).save(source)
            manager = ProjectManager()
            manager.location_registry_database_path = root / "locations.sqlite"
            manager.create_project("recovery_ui", project_root)
            manager.add_images([str(source)], save=True)
            manager.update_label(
                str(source), "Head", [[1, 1], [6, 1], [3, 6]], save=True
            )
            manager.initialize_integrity_baseline()
            Image.new("RGB", (8, 8), color=(9, 8, 7)).save(source)

            dialog = TrainingIntegrityRecoveryDialog(manager)
            try:
                mismatch_rows = [
                    row
                    for row in range(dialog.table.rowCount())
                    if "mismatch" in dialog.table.item(row, 6).text()
                ]
                self.assertEqual(len(mismatch_rows), 1)
                row = mismatch_rows[0]
                self.assertEqual(dialog.table.item(row, 0).text(), "source_image")
                self.assertNotEqual(
                    dialog.table.item(row, 4).text(),
                    dialog.table.item(row, 5).text(),
                )
            finally:
                dialog.close()

    def test_zarr_relocation_uses_directory_picker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            source = root / "source.png"
            zarr_dir = root / "manual_truth.ome.zarr"
            zarr_dir.mkdir()
            Image.new("RGB", (8, 8), color=(1, 2, 3)).save(source)
            manager = ProjectManager()
            manager.location_registry_database_path = root / "locations.sqlite"
            manager.create_project("recovery_ui_zarr", project_root)
            manager.add_images([str(source)], save=True)
            manager.initialize_integrity_baseline()

            dialog = TrainingIntegrityRecoveryDialog(manager)
            try:
                with patch.object(
                    QFileDialog,
                    "getExistingDirectory",
                    return_value=str(zarr_dir),
                ) as directory_picker, patch.object(
                    QFileDialog, "getOpenFileName"
                ) as file_picker:
                    selected = dialog._choose_relocation_candidate(
                        {"runtime_path": str(zarr_dir)}
                    )
                self.assertEqual(selected, str(zarr_dir))
                directory_picker.assert_called_once()
                file_picker.assert_not_called()
            finally:
                dialog.close()


if __name__ == "__main__":
    unittest.main()
