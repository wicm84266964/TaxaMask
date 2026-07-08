import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from AntSleap.core.safe_io import atomic_write_json, backup_file, replace_directory_safely


class SafeIoTests(unittest.TestCase):
    def test_atomic_write_json_failure_keeps_existing_file_and_removes_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "project.json"
            path.write_text('{"status": "original"}', encoding="utf-8")

            with patch("AntSleap.core.safe_io.os.replace", side_effect=OSError("simulated replace failure")):
                with self.assertRaises(OSError):
                    atomic_write_json(path, {"status": "new"})

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"status": "original"})
            self.assertFalse(Path(f"{path}.tmp").exists())

    def test_backup_file_throttles_and_prunes_old_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "project.json"
            backup_dir = root / "backups"
            source.write_text("first", encoding="utf-8")

            first = backup_file(source, backup_dir, limit=2, min_interval_seconds=0)
            self.assertTrue(Path(first).exists())

            with patch("AntSleap.core.safe_io.time.time", return_value=os.path.getmtime(first) + 1):
                throttled = backup_file(source, backup_dir, limit=2, min_interval_seconds=300)
            self.assertEqual(throttled, "")

            for index in range(3):
                source.write_text(f"version {index}", encoding="utf-8")
                with patch("AntSleap.core.safe_io.time.strftime", return_value=f"20260101_00000{index}"):
                    backup_file(source, backup_dir, limit=2, min_interval_seconds=0)

            backups = sorted(backup_dir.glob("project.*.bak"))
            self.assertEqual(len(backups), 2)

    def test_replace_directory_safely_restores_existing_target_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "new_dir"
            target = root / "target_dir"
            backup = root / "target_backup"
            source.mkdir()
            target.mkdir()
            (source / "new.txt").write_text("new", encoding="utf-8")
            (target / "old.txt").write_text("old", encoding="utf-8")

            real_replace = os.replace
            calls = {"count": 0}

            def flaky_replace(src, dst):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("simulated target replace failure")
                return real_replace(src, dst)

            with patch("AntSleap.core.safe_io.os.replace", side_effect=flaky_replace):
                with self.assertRaises(OSError):
                    replace_directory_safely(source, target, backup_suffix=str(backup))

            self.assertTrue((target / "old.txt").exists())
            self.assertEqual((target / "old.txt").read_text(encoding="utf-8"), "old")


if __name__ == "__main__":
    unittest.main()
