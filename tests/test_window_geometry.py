import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AntSleap.core.window_geometry import compute_centered_window_geometry


class WindowGeometryTests(unittest.TestCase):
    def test_geometry_centers_when_screen_is_large_enough(self):
        x, y, width, height = compute_centered_window_geometry((0, 0, 2560, 1440), (1600, 1000))
        self.assertEqual((width, height), (1600, 1000))
        self.assertEqual((x, y), (480, 220))

    def test_geometry_clamps_when_screen_is_smaller_than_default(self):
        x, y, width, height = compute_centered_window_geometry((0, 0, 1366, 768), (1600, 1000))
        self.assertEqual((width, height), (1334, 736))
        self.assertEqual((x, y), (16, 16))


if __name__ == "__main__":
    unittest.main()
