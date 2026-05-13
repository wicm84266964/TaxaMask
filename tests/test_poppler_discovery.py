import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.pdf_processor.poppler_discovery import discover_poppler


class PopplerDiscoveryTests(unittest.TestCase):
    def _touch_tools(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        suffix = ".exe" if __import__("os").name == "nt" else ""
        (directory / f"pdfinfo{suffix}").write_text("", encoding="utf-8")
        (directory / f"pdftoppm{suffix}").write_text("", encoding="utf-8")

    def test_discovers_configured_poppler_bin(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            poppler_bin = Path(tmp_dir) / "custom_poppler" / "bin"
            self._touch_tools(poppler_bin)
            status = discover_poppler(user_path=poppler_bin, repo_root=Path(tmp_dir) / "repo")

            self.assertTrue(status.found)
            self.assertEqual(status.source, "configured")
            self.assertEqual(Path(status.bin_path), poppler_bin)

    def test_discovers_bundled_poppler(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "repo"
            poppler_bin = root / "external_tools" / "poppler" / "Library" / "bin"
            self._touch_tools(poppler_bin)
            status = discover_poppler(repo_root=root)

            self.assertTrue(status.found)
            self.assertEqual(status.source, "bundled")

    def test_reports_missing_when_no_tools_exist(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("shutil.which", return_value=None):
                status = discover_poppler(repo_root=Path(tmp_dir) / "repo")

            self.assertFalse(status.found)
            self.assertEqual(status.source, "missing")
            self.assertIn("pdf2image", status.message)


if __name__ == "__main__":
    unittest.main()
