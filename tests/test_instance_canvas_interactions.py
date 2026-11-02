"""Mouse-driven annotation checks; INSTANCE_TEST_IMAGE optionally supplies a real photo."""
import os
import tempfile
import unittest
import time
from unittest.mock import patch
from pathlib import Path
import numpy as np
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from AntSleap.core.instance_project import InstanceProject, decode_mask
from AntSleap.core.instance_dataset import export_dataset, import_coco
from AntSleap.ui.instance_workbench import InstanceWorkbench
from AntSleap.ui.style import apply_theme_to_app, register_windows_scholarly_ui_fonts


class InstanceMouseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("INSTANCE_TEST_SAM"):
            # Match desktop startup: native ML libraries load before Qt workers.
            from AntSleap.core.sam_helper import SAMWorker
        cls.app = QApplication.instance() or QApplication([])
        register_windows_scholarly_ui_fonts()
        apply_theme_to_app("classic_dark")

    def setUp(self):
        root = Path(__file__).resolve().parents[1] / ".tmp_validation"
        root.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.tmp.name)
        source = os.environ.get("INSTANCE_TEST_IMAGE")
        if not source:
            source = self.root / "fixture.png"
            Image.new("RGB", (474, 293), "#8c9d75").save(source)
        self.project = InstanceProject.create(self.root / "project")
        self.cid = self.project.category("Test category A")
        self.project.import_images([source])
        self.widget = InstanceWorkbench()
        warning = patch("AntSleap.ui.instance_workbench.QMessageBox.warning", return_value=None)
        warning.start()
        self.addCleanup(warning.stop)
        self.widget.set_project(self.project)
        self.widget.categories.setCurrentIndex(self.widget.categories.findData(self.cid))
        self.widget.resize(1400, 900)
        self.widget.show()
        self.app.processEvents()
        self.widget.canvas.fit_to_view()
        self.errors = []
        def guard(callback):
            try:
                return callback()
            except Exception as exc:
                self.errors.append(str(exc))
        self.widget.guard = guard

    def tearDown(self):
        self.widget.shutdown()
        self.widget.close()
        self.tmp.cleanup()

    def point(self, x, y):
        im = self.project.get("images", self.widget.image_id)
        return self.widget.canvas.image_to_screen(x * im["width"], y * im["height"]).toPoint()

    def tool(self, key):
        self.widget.tool.setCurrentIndex(self.widget.tool.findData(key))

    def click(self, x, y, modifier=Qt.NoModifier):
        QTest.mouseClick(self.widget.canvas, Qt.LeftButton, modifier, self.point(x, y))

    def drag(self, start, end):
        canvas = self.widget.canvas
        QTest.mousePress(canvas, Qt.LeftButton, Qt.NoModifier, self.point(*start))
        QTest.mouseMove(canvas, self.point(*end), 20)
        QTest.mouseRelease(canvas, Qt.LeftButton, Qt.NoModifier, self.point(*end))
        self.app.processEvents()

    def polygon(self):
        self.tool("polygon")
        for p in ((.25, .3), (.65, .3), (.65, .65), (.25, .65)):
            self.click(*p)
        QTest.keyClick(self.widget.canvas, Qt.Key_Return)
        self.assertEqual(self.errors, [])

    def test_boxes_overlap_select_review_undo_reopen(self):
        self.tool("box")
        self.drag((.25, .25), (.7, .7))
        self.drag((.3, .3), (.6, .6))
        records = self.project.records("instances")
        self.assertEqual(len(records), 2)
        self.tool("select")
        self.click(.4, .4)
        first = self.widget.canvas.active_id
        self.click(.4, .4)
        self.assertNotEqual(first, self.widget.canvas.active_id)
        keys = [r["id"] for r in records]
        self.project.batch(keys, "confirm")
        self.project.review_image(self.widget.image_id, "complete")
        self.project.batch([keys[0]], "delete")
        self.widget.history(False)
        self.assertEqual(len(self.project.records("instances")), 2)
        self.widget.history(True)
        self.assertEqual(len(self.project.records("instances")), 1)
        reader = InstanceProject(self.project.path, readonly=True)
        try:
            self.assertEqual(reader.records("instances"), self.project.records("instances"))
        finally:
            reader.close()
        self.assertEqual(self.errors, [])

    def test_polygon_vertices_brush_erase_and_truth_invalidation(self):
        self.polygon()
        key = self.widget.canvas.active_id
        self.project.batch([key], "confirm")
        self.tool("vertices")
        self.drag((.25, .3), (.2, .25))
        self.assertFalse(self.project.trusted(self.project.get("instances", key)))
        revision = self.project.revision
        self.click(.4, .2, Qt.ControlModifier)
        self.assertGreater(self.project.revision, revision)
        revision = self.project.revision
        self.click(.4, .2, Qt.ShiftModifier)
        self.assertGreater(self.project.revision, revision)
        before = decode_mask(self.project.get("instances", key)["mask"])
        self.tool("erase")
        self.drag((.4, .45), (.45, .45))
        erased = decode_mask(self.project.get("instances", key)["mask"])
        self.assertLess(erased.sum(), before.sum())
        self.tool("brush")
        self.drag((.4, .45), (.45, .45))
        painted = decode_mask(self.project.get("instances", key)["mask"])
        self.assertGreater(painted.sum(), erased.sum())
        self.assertEqual(len(self.project.records("instances")), 1)
        self.assertEqual(self.errors, [])

    def test_sam_prompts_and_cancel_are_not_annotations(self):
        canvas = self.widget.canvas
        canvas.prompt_ready.disconnect()
        prompts = []
        canvas.prompt_ready.connect(prompts.append)
        self.tool("sam_point"); self.click(.4, .4)
        self.tool("sam_negative"); self.click(.9, .9)
        self.tool("sam_box"); self.drag((.2, .2), (.7, .7))
        self.assertEqual(prompts[0]["labels"], [1])
        self.assertEqual(prompts[1]["labels"], [0])
        self.assertEqual(len(prompts[2]["box"]), 4)
        self.tool("polygon"); self.click(.2, .2); self.click(.5, .2)
        QTest.keyClick(canvas, Qt.Key_Escape)
        QTest.keyClick(canvas, Qt.Key_Return)
        self.assertEqual(self.project.records("instances"), [])

    def test_real_pixels_mask_export_import_roundtrip(self):
        self.polygon()
        key = self.widget.canvas.active_id
        self.project.batch([key], "confirm")
        self.project.review_image(self.widget.image_id, "complete")
        folder, report = export_dataset(self.project, self.root / "exports", task="segment", format="coco", ratios=(1, 0, 0))
        self.assertEqual(report["instances"], 1)
        destination = InstanceProject.create(self.root / "imported")
        try:
            import_coco(destination, folder / "dataset/train.json", folder / "dataset")
            np.testing.assert_array_equal(decode_mask(destination.records("instances")[0]["mask"]),
                                          decode_mask(self.project.get("instances", key)["mask"]))
            self.assertFalse(destination.trusted(destination.records("instances")[0]))
        finally:
            destination.close()

    @unittest.skipUnless(os.environ.get("INSTANCE_TEST_SAM"), "Opt-in real SAM weights required")
    def test_real_sam_box_point_background_and_draft_acceptance(self):
        self.widget.sam_options = {"model": os.environ["INSTANCE_TEST_SAM"], "device": "cpu"}
        im = self.project.get("images", self.widget.image_id)
        w, h = im["width"], im["height"]
        prompts = [{"box": [.23*w, .2*h, .75*w, .65*h]},
                   {"points": [[.42*w, .42*h]], "labels": [1]},
                   {"points": [[.03*w, .9*h]], "labels": [0]}]
        with patch("AntSleap.ui.instance_workbench.QInputDialog.getInt", return_value=(1, True)):
            for prompt in prompts:
                self.widget.sam_prompt(prompt)
                deadline = time.monotonic() + 180
                while self.widget.busy and time.monotonic() < deadline:
                    self.app.processEvents()
                    # Release the GIL while the Python worker imports/runs torch.
                    time.sleep(.02)
                self.assertFalse(self.widget.busy, "SAM timed out")
                self.assertIsNotNone(self.widget.candidate, self.widget.log.toPlainText())
                self.assertEqual(self.project.records("instances"), [])
            self.widget.accept_candidate()
        record = self.project.records("instances")[0]
        self.assertEqual(record["mask"]["size"], [h, w])
        self.assertEqual(record["source"], "sam")
        self.assertFalse(self.project.trusted(record))
        self.project.batch([record["id"]], "confirm")
        self.assertTrue(self.project.trusted(self.project.get("instances", record["id"])))
        self.widget.refresh()
        screenshot = os.environ.get("INSTANCE_TEST_SCREENSHOT")
        if screenshot:
            self.widget.grab().save(screenshot)

    def test_sam_background_points_are_grouped_for_one_instance(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        import torch
        from AntSleap.core.sam_helper import SAMWorker
        worker = SAMWorker(device="cpu")
        worker.device = "cpu"
        image = self.project.get("images", self.widget.image_id)
        tensor = torch.ones((1, image["height"], image["width"]))
        worker.model = Mock()
        worker.model.predict.return_value = [SimpleNamespace(masks=SimpleNamespace(data=tensor))]
        worker.predict_instance_masks(self.project.image_path(image), points=[[20, 20], [30, 30]], labels=[1, 0])
        kwargs = worker.model.predict.call_args.kwargs
        self.assertEqual(kwargs["points"], [[[20, 20], [30, 30]]])
        self.assertEqual(kwargs["labels"], [[1, 0]])


if __name__ == "__main__":
    unittest.main()
