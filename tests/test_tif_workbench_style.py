import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AntSleap.ui.tif_workbench_style import build_tif_workbench_stylesheet, tif_canvas_background


class TifWorkbenchStyleTests(unittest.TestCase):
    def test_stylesheet_keeps_key_object_names_and_canvas_backgrounds(self):
        dark = build_tif_workbench_stylesheet("dark")
        light = build_tif_workbench_stylesheet("light")

        self.assertIn("QWidget#tifWorkbenchRoot", dark)
        self.assertIn("QScrollArea#tifInspectorScroll", dark)
        self.assertIn("QLabel#tifSaveStatusText", dark)
        self.assertIn("QFrame#tifLocalAxisVolumeSection", dark)
        self.assertIn(tif_canvas_background("dark"), dark)
        self.assertIn(tif_canvas_background("light"), light)


if __name__ == "__main__":
    unittest.main()
