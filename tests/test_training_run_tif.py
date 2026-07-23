import tempfile
import unittest
from pathlib import Path

import numpy as np

from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import write_volume_sidecar
from AntSleap.core.training_run_recorder import TrainingRunRecorder
from AntSleap.core.training_run_tif import attach_tif_training_evidence


class TrainingRunTifTests(unittest.TestCase):
    def test_two_specimens_prepare_verified_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            manager = TifProjectManager()
            manager.create_project("ants", project_root)
            for index in range(2):
                specimen_id = f"specimen_{index}"
                manager.create_specimen_scaffold(specimen_id)
                source_rel = f"specimens/{specimen_id}/working/source.tif"
                source = project_root / source_rel
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(f"source-{index}".encode())
                manager.register_working_volume(
                    specimen_id, source_rel, [2, 3, 4], "uint16", save=False
                )
                truth_rel = (
                    f"specimens/{specimen_id}/labels/manual_truth.ome.zarr"
                )
                metadata = write_volume_sidecar(
                    project_root / truth_rel,
                    np.ones((2, 3, 4), dtype=np.uint16),
                    role="manual_truth",
                )
                manager.register_label_volume(
                    specimen_id,
                    "manual_truth",
                    truth_rel,
                    metadata["shape_zyx"],
                    metadata["dtype"],
                    status="reviewed",
                    explicit_review=True,
                    operation="truth_promotion",
                    save=False,
                )
                manager.set_review_status(
                    specimen_id, "train_ready", train_ready=True, save=False
                )
            manager.save_project()
            manager.initialize_integrity_baseline()
            recorder = TrainingRunRecorder(
                root / "runs", database_path=manager.current_database_path
            )
            run = recorder.create_pending("tif_external")
            result = attach_tif_training_evidence(
                run,
                manager,
                sample_specs=[
                    {
                        "sample_id": f"sample_{index}",
                        "group_id": f"specimen_{index}",
                        "owner_keys": [
                            f"specimen.specimen_{index}.working",
                            f"specimen.specimen_{index}.manual_truth",
                        ],
                    }
                    for index in range(2)
                ],
                effective_config={
                    "epochs": 1,
                    "batch_size": 1,
                    "learning_rate": 0.001,
                    "weight_decay": 0.0001,
                    "random_seed": 0,
                    "input_resolution": [2, 3, 4],
                    "preprocessing": {"dataset_adapter": "tif_contract"},
                    "model": {
                        "family": "external",
                        "version": "1",
                        "locator": "disabled",
                        "parts": "volume",
                    },
                    "loss_weights": {},
                },
                backend={
                    "backend_id": "tif_external",
                    "backend_version": "1.0",
                    "adapter_id": "tif_backend_runner",
                    "adapter_version": "1.0",
                },
            )
            self.assertEqual(run.status, "running")
            self.assertEqual(
                {item["partition"] for item in result["assignments"]},
                {"train", "validation"},
            )
            run.fail(RuntimeError("test cleanup"), stage="test")


if __name__ == "__main__":
    unittest.main()
