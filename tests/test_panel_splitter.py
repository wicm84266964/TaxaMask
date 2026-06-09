import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from AntSleap.core.panel_splitter import PanelSplitSettings, detect_panel_crops


class PanelSplitterTests(unittest.TestCase):
    def assertBoxAlmostEqual(self, actual, expected, tolerance=1):
        self.assertEqual(len(actual), len(expected))
        for actual_value, expected_value in zip(actual, expected):
            self.assertLessEqual(abs(actual_value - expected_value), tolerance)

    def test_detects_mixed_pdf_figure_panels_from_white_gutters(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "figure_plate.jpg"
            image = Image.new("RGB", (640, 900), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((10, 10, 630, 350), fill=(120, 128, 112))
            draw.rectangle((10, 360, 630, 590), fill=(126, 134, 118))
            draw.rectangle((10, 600, 230, 890), fill=(135, 118, 95))
            draw.rectangle((240, 600, 630, 890), fill=(132, 122, 100))
            image.save(path)

            crops = detect_panel_crops(str(path))

        boxes = [item["box"] for item in crops]
        self.assertEqual(len(boxes), 4)
        self.assertEqual(boxes[0], [10, 10, 631, 351])
        self.assertEqual(boxes[1], [10, 360, 631, 591])
        self.assertEqual(boxes[2], [10, 600, 231, 891])
        self.assertEqual(boxes[3], [240, 600, 631, 891])
        self.assertTrue(all(item["source"] == "white_separator_panel_split" for item in crops))

    def test_returns_no_crops_for_single_unseparated_image(self):
        image = Image.new("RGB", (300, 220), (130, 125, 112))

        self.assertEqual(detect_panel_crops(image), [])

    def test_detects_off_white_noisy_gutters_from_scanned_pdf_plate(self):
        image = Image.new("RGB", (520, 260), (221, 219, 205))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 239, 260), fill=(118, 92, 70))
        draw.rectangle((281, 0, 520, 260), fill=(188, 194, 184))
        for y in range(0, 260, 17):
            draw.point((260, y), fill=(198, 196, 184))
            draw.point((265, min(259, y + 4)), fill=(205, 203, 190))

        crops = detect_panel_crops(image)

        boxes = [item["box"] for item in crops]
        self.assertEqual(len(boxes), 2)
        self.assertBoxAlmostEqual(boxes[0], [0, 0, 240, 260])
        self.assertBoxAlmostEqual(boxes[1], [281, 0, 520, 260])
        self.assertTrue(all(item["source"] == "white_separator_panel_split" for item in crops))

    def test_detects_butt_joined_plate_panels_without_white_gutters(self):
        image = Image.new("RGB", (600, 460), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 279, 279), fill=(125, 95, 70))
        draw.rectangle((280, 0, 599, 219), fill=(202, 205, 198))
        draw.rectangle((280, 220, 599, 459), fill=(132, 138, 128))
        draw.rectangle((0, 280, 279, 459), fill=(248, 248, 248))
        draw.line((0, 280, 279, 280), fill=(40, 40, 40), width=1)
        draw.line((280, 0, 280, 459), fill=(235, 235, 235), width=1)
        draw.line((280, 220, 599, 220), fill=(226, 226, 226), width=1)

        crops = detect_panel_crops(image)

        boxes = [item["box"] for item in crops]
        self.assertEqual(len(boxes), 4)
        self.assertBoxAlmostEqual(boxes[0], [0, 0, 280, 280])
        self.assertBoxAlmostEqual(boxes[1], [280, 0, 600, 220])
        self.assertBoxAlmostEqual(boxes[2], [280, 220, 600, 460])
        self.assertBoxAlmostEqual(boxes[3], [0, 280, 280, 460])

    def test_detects_hard_scene_change_without_light_separator_line(self):
        image = Image.new("RGB", (420, 260), (118, 92, 70))
        draw = ImageDraw.Draw(image)
        draw.rectangle((210, 0, 419, 259), fill=(188, 194, 184))

        crops = detect_panel_crops(image)

        boxes = [item["box"] for item in crops]
        self.assertEqual(len(boxes), 2)
        self.assertBoxAlmostEqual(boxes[0], [0, 0, 210, 260])
        self.assertBoxAlmostEqual(boxes[1], [210, 0, 420, 260])
        self.assertTrue(all(item["source"] == "hard_seam_panel_split" for item in crops))

    def test_hard_seam_settings_can_be_made_more_conservative_for_noisy_plates(self):
        image = Image.new("RGB", (420, 260), (118, 92, 70))
        draw = ImageDraw.Draw(image)
        draw.rectangle((210, 0, 419, 259), fill=(188, 194, 184))

        strict = detect_panel_crops(image, PanelSplitSettings(seam_strength=120.0))

        self.assertEqual(strict, [])

    def test_default_does_not_force_equal_grid_from_panel_labels(self):
        image = Image.new("RGB", (660, 520), (236, 238, 229))
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", 42)
        except Exception:
            font = ImageFont.load_default(size=42)
        draw.rectangle((0, 0, 659, 299), fill=(150, 176, 150))
        draw.rectangle((0, 310, 324, 519), fill=(140, 168, 145))
        draw.rectangle((336, 310, 659, 519), fill=(170, 196, 162))
        draw.rectangle((0, 300, 659, 309), fill=(248, 248, 241))
        draw.rectangle((325, 310, 335, 519), fill=(248, 248, 241))
        draw.text((18, 16), "133", fill=(20, 20, 20), font=font)
        draw.text((18, 322), "134", fill=(20, 20, 20), font=font)
        draw.text((354, 322), "135", fill=(20, 20, 20), font=font)

        crops = detect_panel_crops(image)

        boxes = [item["box"] for item in crops]
        self.assertEqual(len(boxes), 3)
        self.assertTrue(all(item["source"] == "white_separator_panel_split" for item in crops))
        self.assertBoxAlmostEqual(boxes[0], [0, 0, 660, 300], tolerance=2)
        self.assertBoxAlmostEqual(boxes[1], [0, 310, 325, 520], tolerance=2)
        self.assertBoxAlmostEqual(boxes[2], [336, 310, 660, 520], tolerance=2)

    def test_default_ignores_labels_when_no_real_panel_boundaries_exist(self):
        image = Image.new("RGB", (520, 420), (152, 168, 145))
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", 34)
        except Exception:
            font = ImageFont.load_default(size=34)
        for text, pos in zip(("A", "B", "C", "D"), [(12, 10), (272, 10), (12, 220), (272, 220)]):
            draw.text(pos, text, fill=(255, 255, 255), font=font)

        self.assertEqual(detect_panel_crops(image, PanelSplitSettings(seam_strength=160.0)), [])


if __name__ == "__main__":
    unittest.main()
