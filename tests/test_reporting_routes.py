# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false

import csv
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ANTSLEAP_ROOT = PROJECT_ROOT / "AntSleap"
if str(ANTSLEAP_ROOT) not in sys.path:
    sys.path.insert(0, str(ANTSLEAP_ROOT))

if "ultralytics" not in sys.modules:
    ultralytics_stub = types.ModuleType("ultralytics")
    ultralytics_models_stub = types.ModuleType("ultralytics.models")
    ultralytics_models_sam_stub = types.ModuleType("ultralytics.models.sam")

    class _FakeSAM:
        def __init__(self, *args, **kwargs):
            pass

        def predict(self, *args, **kwargs):
            return []

    ultralytics_stub.SAM = _FakeSAM
    ultralytics_models_sam_stub.Predictor = object
    sys.modules["ultralytics"] = ultralytics_stub
    sys.modules["ultralytics.models"] = ultralytics_models_stub
    sys.modules["ultralytics.models.sam"] = ultralytics_models_sam_stub

from PIL import Image
from PySide6.QtWidgets import QApplication
from torch.utils.data import DataLoader, TensorDataset
import torch

from AntSleap.core.engine import AntEngine
from AntSleap.main import TrainingReportDialog


class _TinyLocator:
    def eval(self):
        return self

    def __call__(self, imgs):
        batch = imgs.shape[0]
        hm = torch.zeros((batch, 1, 8, 8), dtype=torch.float32)
        hm[:, 0, 3, 4] = 1.0
        wh = torch.zeros((batch, 1, 2), dtype=torch.float32)
        wh[:, 0, 0] = 0.25
        wh[:, 0, 1] = 0.3
        return hm, wh


class _FakeSamModel:
    def eval(self):
        return None

    class mask_decoder:
        @staticmethod
        def state_dict():
            return {"decoder": torch.tensor([1.0])}


class _FakePartsModel:
    def __init__(self):
        self.sam_model = _FakeSamModel()


class ReportingRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_generate_report_writes_summary_and_validation_index(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "sample.png"
            Image.new("RGB", (64, 64), color=(180, 180, 180)).save(image_path)

            imgs = torch.zeros((1, 3, 8, 8), dtype=torch.float32)
            hm_target = torch.zeros((1, 1, 8, 8), dtype=torch.float32)
            hm_target[0, 0, 3, 4] = 1.0
            wh_target = torch.zeros((1, 1, 2), dtype=torch.float32)
            valid_mask = torch.ones((1, 1), dtype=torch.float32)
            dataloader = DataLoader(TensorDataset(imgs, hm_target, wh_target, valid_mask), batch_size=1)
            dataloader.dataset.taxonomy = ["Head"]
            dataloader.dataset.data = [(str(image_path), {"parts": {"Head": [[1, 1], [2, 1], [1, 2]]}, "boxes": {}})]

            engine = AntEngine.__new__(AntEngine)
            engine.weights_dir = os.path.join(tmp_dir, "weights")
            os.makedirs(engine.weights_dir, exist_ok=True)
            engine.locator = _TinyLocator()
            engine.parts_model = _FakePartsModel()
            engine.device = "cpu"
            engine.locator_resolution = (8, 8)
            engine.history = {
                "locator_train": [0.1],
                "locator_val": [0.2],
                "pixel_error": [2.0],
                "parts_train": [],
                "parts_val": [],
                "iou": [],
            }

            report = engine.generate_report(dataloader, num_samples=1)

            self.assertTrue(os.path.exists(report["report_summary"]))
            self.assertTrue(os.path.exists(report["validation_index"]))
            self.assertTrue(os.path.isdir(report["details_dir"]))

            with open(report["validation_index"], "r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["provenance"], "macro_locator")

    def test_training_report_dialog_uses_structured_validation_index_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            report_dir = Path(tmp_dir) / "exp_test"
            details_dir = report_dir / "val_details"
            details_dir.mkdir(parents=True, exist_ok=True)
            sample_image = details_dir / "val_0000.jpg"
            Image.new("RGB", (120, 80), color=(180, 180, 180)).save(sample_image)

            summary_path = report_dir / "report_summary.json"
            summary_path.write_text(
                '{"validation_count": 1, "validation_preview_count": 1, "validation_provenance_counts": {"macro_locator": 1}}',
                encoding="utf-8",
            )
            index_path = report_dir / "validation_index.csv"
            index_path.write_text(
                "sample_id,image_name,image_path,detail_image,provenance,valid_parts,predicted_parts,peak_summary,error_summary,max_error_px\n"
                "val_0000,sample.png,sample.png,val_0000.jpg,macro_locator,Head,Head,Head=1.00,Head=0.0px,0.000\n",
                encoding="utf-8",
            )

            dialog = TrainingReportDialog(
                {
                    "dir": str(report_dir),
                    "report_summary": str(summary_path),
                    "validation_index": str(index_path),
                    "details_dir": str(details_dir),
                    "val": None,
                    "metrics": None,
                },
                lang="en",
            )

            self.assertEqual(dialog.validation_index_table.rowCount(), 1)
            self.assertIn("Validation count: 1", dialog.summary_box.toPlainText())
            self.assertEqual(dialog.validation_filter.currentData(), "all")


if __name__ == "__main__":
    unittest.main()
