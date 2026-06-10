import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from AntSleap.core.platform_open import open_path


class PlatformOpenTests(unittest.TestCase):
    def test_open_path_uses_linux_xdg_open(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            calls = []
            self.assertTrue(open_path(tmp_dir, platform="linux", runner=lambda cmd, check=False: calls.append((cmd, check))))
            self.assertEqual(calls, [(["xdg-open", str(Path(tmp_dir))], False)])

    def test_open_path_uses_macos_open(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            calls = []
            self.assertTrue(open_path(tmp_dir, platform="darwin", runner=lambda cmd, check=False: calls.append((cmd, check))))
            self.assertEqual(calls, [(["open", str(Path(tmp_dir))], False)])

    def test_open_path_uses_windows_startfile(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("os.startfile", create=True) as startfile:
                self.assertTrue(open_path(tmp_dir, platform="win32"))
                startfile.assert_called_once_with(str(Path(tmp_dir)))

    def test_open_path_returns_false_for_missing_target(self):
        self.assertFalse(open_path(Path(tempfile.gettempdir()) / "taxamask_missing_open_target"))
        self.assertFalse(open_path(None))


if __name__ == "__main__":
    unittest.main()
