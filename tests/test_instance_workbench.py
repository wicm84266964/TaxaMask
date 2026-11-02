import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from AntSleap.core.instance_project import InstanceProject, encode_mask, decode_mask
from AntSleap.core.instance_dataset import export_dataset, import_coco, partition_images, mask_polygon


class InstanceProjectTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / ".tmp_validation"
        root.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = InstanceProject.create(self.root / "project")
        self.addCleanup(lambda: self.project.close())
        self.category = self.project.category("Formica sp. A")
        self.images = []
        for n in range(12):
            path = self.root / f"image_{n}.png"
            Image.new("RGB", (64, 48), (n * 15, 80, 90)).save(path)
            ids, errors = self.project.import_images([path])
            self.images.extend(ids)
            self.assertEqual(errors, [])

    def tearDown(self):
        self.project.close()
        self.tmp.cleanup()

    def instance(self, image=None, box=None, mask=None):
        return self.project.put_instance(image or self.images[0], self.category, box or [1, 2, 12, 20], mask=mask)

    def test_same_species_multiple_instances_roundtrip(self):
        keys = [self.instance() for _ in range(3)]
        self.project.batch(keys, "confirm")
        self.project.review_image(self.images[0], "complete")
        path = self.project.path
        self.project.close()
        self.project = InstanceProject(path)
        self.assertEqual({r["id"] for r in self.project.records("instances")}, set(keys))
        self.project.category("Formica sp. renamed", self.category)
        self.assertTrue(all(self.project.trusted(r) for r in self.project.records("instances")))
        self.project.batch([keys[1]], "delete")
        self.assertEqual(len(self.project.records("instances")), 2)
        self.project.undo()
        self.assertEqual(len(self.project.records("instances")), 3)
        self.project.redo()
        self.assertEqual(len(self.project.records("instances")), 2)

    def test_edit_invalidates_image_and_truth(self):
        key = self.instance()
        self.project.batch([key], "confirm")
        self.project.review_image(self.images[0], "complete")
        self.project.put_instance(self.images[0], self.category, [2, 3, 15, 21], key=key)
        self.assertFalse(self.project.trusted(self.project.get("instances", key)))
        self.assertEqual(self.project.get("images", self.images[0])["review"], "in_progress")
        with self.assertRaises(ValueError):
            self.project.review_image(self.images[0], "complete")
        with self.assertRaises(ValueError):
            self.project.review_image(self.images[0], "confirmed_empty")

    def test_masks_preserve_holes_and_components(self):
        mask = np.zeros((48, 64), np.uint8)
        mask[3:20, 4:20] = 1
        mask[7:11, 8:12] = 0
        mask[30:35, 40:50] = 1
        rle = encode_mask(mask)
        np.testing.assert_array_equal(decode_mask(rle), mask)
        key = self.instance(mask=rle)
        self.assertEqual(self.project.get("instances", key)["box"], [4., 3., 50., 35.])
        with self.assertRaises(ValueError):
            mask_polygon(rle)

    def test_transaction_rolls_back_all_on_failure(self):
        revision = self.project.revision
        key = self.instance()
        count = len(self.project.records("instances"))
        with self.assertRaises(Exception):
            self.project.change("invalid", [("instances", key, None), ("instances", "bad", {"image_id": "missing", "category_id": self.category})])
        self.assertEqual(len(self.project.records("instances")), count)
        self.assertEqual(self.project.revision, revision + 1)

    def test_group_partition_links_specimen_and_source(self):
        self.instance(self.images[0])
        self.instance(self.images[1])
        snapshot = self.project.snapshot()
        for r in snapshot["instances"]:
            r["specimen_id"] = "specimen_1"
        snapshot["images"][1]["source_group"] = "plate_1"
        snapshot["images"][2]["source_group"] = "plate_1"
        partitions = partition_images(snapshot)
        self.assertEqual(len({partitions[k] for k in self.images[:3]}), 1)

    def test_export_excludes_draft_and_unchecked_empty(self):
        keys = [self.instance(box=[1 + n * 15, 2, 12 + n * 15, 20]) for n in range(3)]
        self.project.batch(keys, "confirm")
        self.project.review_image(self.images[0], "complete")
        self.project.review_image(self.images[1], "confirmed_empty")
        self.instance(self.images[2])
        output, report = export_dataset(self.project, self.root / "exports", format="yolo")
        self.assertEqual(report["images"], 2)
        self.assertEqual(report["instances"], 3)
        self.assertEqual(report["negative_images"], 1)
        labels = list((output / "dataset" / "labels").rglob("*.txt"))
        self.assertEqual(sorted(len(p.read_text().splitlines()) for p in labels), [0, 3])
        self.assertTrue((output / "COMPLETE.json").is_file())

    def test_segmentation_excludes_mixed_box_only_image(self):
        mask = np.zeros((48, 64), np.uint8)
        mask[2:12, 3:15] = 1
        keys = [self.instance(mask=encode_mask(mask)), self.instance(box=[30, 20, 50, 40])]
        self.project.batch(keys, "confirm")
        self.project.review_image(self.images[0], "complete")
        _, report = export_dataset(self.project, self.root / "exports", task="segment")
        self.assertEqual(report["instances"], 0)

    def test_coco_roundtrip_same_class_and_draft_import(self):
        keys = [self.instance(box=[1 + n * 15, 2, 12 + n * 15, 20]) for n in range(3)]
        self.project.batch(keys, "confirm")
        self.project.review_image(self.images[0], "complete")
        output, _ = export_dataset(self.project, self.root / "exports", ratios=(1, 0, 0))
        destination = InstanceProject.create(self.root / "import")
        try:
            count = import_coco(destination, output / "dataset/train.json", output / "dataset")
            self.assertEqual(count, 3)
            self.assertEqual(len(destination.records("categories")), 1)
            self.assertTrue(all(r["review"] == "draft" for r in destination.records("instances")))
            with self.assertRaises(ValueError):
                import_coco(destination, output / "dataset/train.json", output / "dataset")
        finally:
            destination.close()

    def test_changed_image_cannot_be_exported(self):
        key = self.instance()
        self.project.batch([key], "confirm")
        self.project.review_image(self.images[0], "complete")
        path = self.project.image_path(self.project.get("images", self.images[0]))
        Image.new("RGB", (64, 48)).save(path)
        _, report = export_dataset(self.project, self.root / "exports")
        self.assertEqual(report["instances"], 0)

    def test_training_ledger_and_changed_input_guard(self):
        from AntSleap.core.instance_training_record import prepare_record
        from AntSleap.core.instance_training import verify_export
        for image in self.images:
            key = self.instance(image)
            self.project.batch([key], "confirm")
            self.project.review_image(image, "complete")
        output, _ = export_dataset(self.project, self.root / "exports", format="yolo")
        weights = self.root / "weights.yaml"
        weights.write_text("nc: 1\n", encoding="utf-8")
        config = {"dataset": str(output), "run_dir": str(self.root / "run"), "task": "detect", "epochs": 1,
                  "batch": 2, "imgsz": 64, "weights": str(weights)}
        verify_export(output, "detect")
        recorder, run, initial = prepare_record(config)
        try:
            self.assertEqual(run.status, "running")
            self.assertTrue(initial.is_file())
            run.cancel()
        finally:
            run.close()
        label = next((output / "dataset/labels").rglob("*.txt"))
        label.write_text("", encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_export(output, "detect")

    def test_yolo_and_class_directory_import(self):
        from AntSleap.core.instance_dataset import import_directory
        for image in self.images:
            key = self.instance(image)
            self.project.batch([key], "confirm")
            self.project.review_image(image, "complete")
        for task, fmt in [("detect", "yolo"), ("classify", "classification")]:
            output, _ = export_dataset(self.project, self.root / "exports", task=task, format=fmt)
            target = InstanceProject.create(self.root / task)
            try:
                count = import_directory(target, output / "dataset", task=task)
                self.assertEqual(count, 12)
            finally:
                target.close()

    def test_merge_undo_and_backup_restore(self):
        key = self.instance()
        self.project.batch([key], "confirm")
        backup = self.project.backup()
        second = self.project.category("Second species")
        self.project.merge_categories(self.category, second)
        self.assertEqual(self.project.get("instances", key)["category_id"], second)
        self.project.undo()
        self.assertEqual(self.project.get("instances", key)["category_id"], self.category)
        self.project.restore_backup(backup)
        self.assertFalse(self.project.trusted(self.project.get("instances", key)))

    def test_instance_project_rejected_by_part_loader(self):
        from AntSleap.core.project import ProjectManager
        manager = ProjectManager()
        with self.assertRaisesRegex(ValueError, "独立工作台"):
            manager.load_project(self.project.path)

    def test_multiple_prediction_boxes_preserved(self):
        from types import SimpleNamespace
        from AntSleap.core.instance_training import predict
        from AntSleap.core.instance_project import digest
        import torch
        weight = self.root / "test.pt"
        weight.write_bytes(b"test-only")
        manifest = self.root / "model_manifest.json"
        manifest.write_text(json.dumps({"schema_version": "taxamask-instance-model-v1", "task": "detect",
                                       "weights": str(weight), "weights_hash": digest(weight), "names": {"0": self.category}}), encoding="utf-8")
        boxes = [SimpleNamespace(xyxy=torch.tensor([[n, 2, n+8, 20]]), cls=torch.tensor([0]), conf=torch.tensor([.9])) for n in (1, 20)]
        class FakeModel:
            task = "detect"
            names = {0: self.category}
            def predict(self, *args, **kwargs):
                return [SimpleNamespace(boxes=boxes)]
        proposals = predict(manifest, self.root / "image_0.png", [self.category], model_factory=lambda *a, **k: FakeModel())
        self.assertEqual(len(proposals), 2)
        self.assertEqual(proposals[0]["category_id"], proposals[1]["category_id"])


class InstanceUITests(unittest.TestCase):
    setUp = InstanceProjectTests.setUp
    tearDown = InstanceProjectTests.tearDown
    def test_workspace_edit_and_reopen(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from AntSleap.ui.instance_workbench import InstanceWorkbench
        app = QApplication.instance() or QApplication([])
        widget = InstanceWorkbench()
        try:
            path = self.project.path
            self.project.close()
            widget.open_path(path)
            widget.categories.setCurrentIndex(widget.categories.findData(self.category))
            widget.geometry({"box": [1, 2, 10, 20]})
            widget.geometry({"box": [20, 2, 35, 20]})
            self.assertEqual(widget.instances.count(), 2)
            widget.resize(1200, 700)
            widget.show()
            app.processEvents()
            self.assertFalse(widget.grab().isNull())
            screenshot = os.environ.get("INSTANCE_WORKBENCH_SCREENSHOT")
            if screenshot:
                widget.grab().save(screenshot)
            widget.history(False)
            self.assertEqual(widget.instances.count(), 1)
            widget.history(True)
            self.assertEqual(widget.instances.count(), 2)
            from AntSleap.core.instance_agent import REQUEST_SCHEMA, submit_request
            from PySide6.QtTest import QTest
            request = {"schema_version": REQUEST_SCHEMA, "request_id": "ui_timer_test",
                       "project_id": widget.project.project_id, "expected_revision": widget.project.revision,
                       "action": "propose_instances", "instances": [{"image_id": widget.image_id,
                       "category_id": self.category, "bbox_xyxy": [2, 3, 12, 22]}]}
            submit_request(widget.project, request)
            QTest.qWait(1700)
            self.assertEqual(widget.instances.count(), 3)
            self.assertFalse(widget.project.trusted(widget.project.records("instances")[-1]))
        finally:
            widget.shutdown()
            widget.close()
            self.project = InstanceProject(path)

    def test_stale_candidate_after_undo_and_failed_batch(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from AntSleap.ui.instance_workbench import InstanceWorkbench
        app = QApplication.instance() or QApplication([])
        widget = InstanceWorkbench()
        path = self.project.path
        self.project.close()
        try:
            widget.open_path(path)
            project = widget.project
            image = project.get("images", widget.image_id)
            context = (project.project_id, image["id"], image["revision"], None, None, self.category, project.revision)
            widget.candidate = (context, [{"category_id": self.category, "box": [1, 2, 10, 20]}, {"category_id": self.category, "box": [1, 2, 999, 20]}])
            with self.assertRaises(ValueError):
                widget.accept_candidate()
            self.assertEqual(len(project.records("instances")), 0)
            project.category("Other")
            project.undo()
            self.assertFalse(widget.context_matches(context))
        finally:
            widget.shutdown()
            widget.close()
            self.project = InstanceProject(path)

    def test_shell_instance_entry_and_return_preserve_project(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget
        from AntSleap.ui.main_window_start_center import MainWindowStartCenterMixin
        from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin
        from AntSleap.ui.main_window_presentation import MainWindowPresentationMixin
        from unittest.mock import Mock
        app = QApplication.instance() or QApplication([])
        class Owner(MainWindowStartCenterMixin, MainWindowProjectLifecycleMixin, QMainWindow):
            def create_menus(self):
                pass
        owner = Owner()
        owner.tabs = QTabWidget()
        owner.setCentralWidget(owner.tabs)
        owner.start_center_widget, owner.workbench_widget, owner.blink_lab = QWidget(), QWidget(), QWidget()
        owner.tif_workbench = owner.pdf_widget = None
        owner.current_lang = "zh"
        owner.config = Mock()
        owner._flush_pending_project_save = Mock()
        owner._ensure_project_switch_available = Mock(return_value=True)
        owner.open_agent_from_context = Mock()
        owner._update_start_center_texts = Mock()
        try:
            owner.enter_instance_workflow()
            self.assertEqual(owner.active_project_kind, "instances")
            self.assertIs(owner.tabs.currentWidget(), owner.instance_workbench)
            owner._show_start_center()
            self.assertIs(owner.tabs.currentWidget(), owner.start_center_widget)
            self.assertEqual(owner.last_workbench_kind, "instances")
            self.assertEqual(owner.tabs.indexOf(owner.instance_workbench), -1)
            owner.enter_instance_workflow()
            self.assertIs(owner.tabs.currentWidget(), owner.instance_workbench)
        finally:
            owner.instance_workbench.shutdown()
            owner.deleteLater()
            app.processEvents()


if __name__ == "__main__":
    unittest.main()
