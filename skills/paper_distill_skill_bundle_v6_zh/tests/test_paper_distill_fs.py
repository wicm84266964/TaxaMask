from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.paper_distill.fs import ensure_safe_file_target


class PaperDistillFsTests(unittest.TestCase):
    def test_rejects_reparse_point_when_detector_flags_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root_path = Path(temporary_directory)
            file_path = root_path / "artifact.json"

            with patch(
                "app.paper_distill.fs._is_windows_reparse_point",
                side_effect=lambda path: path == root_path,
            ):
                with self.assertRaisesRegex(ValueError, "reparse-point"):
                    ensure_safe_file_target(file_path)


if __name__ == "__main__":
    _ = unittest.main()
