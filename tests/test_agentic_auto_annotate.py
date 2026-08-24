import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image
import torch

from AntSleap.core.blink_expert_manifest import (
    build_blink_expert_manifest,
    build_blink_preprocessing_contract,
)
from AntSleap.core.blink_heatmap_trainer import HeatmapBlinkNet
from AntSleap.core.cascade_routes import ROUTE_BACKEND_HEATMAP_BLINK
from AntSleap.core.engine import (
    LOCATOR_ARCHITECTURE_ID,
    LOCATOR_CHECKPOINT_SCHEMA_VERSION,
    AntEngine,
)
from AntSleap.core.project import ProjectManager
from AntSleap.core.training_truth import get_part_training_truth
from AntSleap.core.training_initial_weights import register_initial_weight_version
from AntSleap.core.training_run_2d import prepare_2d_training_run
from AntSleap.models.networks import TraitRegressor
from tools.agentic import auto_annotate_project


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _FaultingBinaryFile:
    def __init__(self, handle, operation):
        self._handle = handle
        self._operation = operation
        self._write_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._handle.close()
        return False

    def __getattr__(self, name):
        return getattr(self._handle, name)

    def write(self, payload):
        self._write_count += 1
        if self._operation == "write":
            raise OSError("synthetic journal write failure")
        if self._operation == "short_write" and self._write_count >= 2:
            return self._handle.write(payload[:-1])
        if self._operation == "prefix_short_write" and self._write_count == 1:
            return self._handle.write(payload[:-1])
        return self._handle.write(payload)

    def flush(self):
        if self._operation == "flush":
            raise OSError("synthetic journal flush failure")
        return self._handle.flush()


class AgenticAutoAnnotateTests(unittest.TestCase):
    def _managed_locator_fixture(
        self,
        root: Path,
        *,
        activate: bool = True,
        checkpoint_bytes: bytes = b"managed-locator-checkpoint",
        decoder_bytes: bytes | None = None,
        registered_base_sam_bytes: bytes | None = None,
        image_count: int = 3,
    ):
        project_dir = root / "project"
        manager = ProjectManager()
        project_path = Path(manager.create_project("managed", project_dir))
        manager.location_registry_database_path = root / "locations.sqlite"

        images_dir = project_dir / "images"
        images_dir.mkdir()
        image_paths = []
        for index in range(image_count):
            image_path = images_dir / f"specimen_{index}.png"
            Image.new("RGB", (32, 24), color=(100 + index, 90, 80)).save(image_path)
            image_paths.append(str(image_path))
        manager.add_images(image_paths, save=True)
        for image_path in image_paths:
            manager.update_label(
                image_path,
                "Head",
                [[2, 2], [20, 2], [10, 18]],
                box=[2, 2, 20, 18],
                save=True,
            )
        manager.initialize_integrity_baseline()
        base_sam_path = None
        if registered_base_sam_bytes is not None:
            base_sam_path = root / "registered" / "sam_b.pt"
            base_sam_path.parent.mkdir()
            base_sam_path.write_bytes(registered_base_sam_bytes)
            register_initial_weight_version(
                manager,
                [{"slot": "parent.sam_base", "path": base_sam_path}],
                note="Agentic full-pipeline fixture base SAM registration.",
            )

        runs_root = root / "runs"
        include_parts = registered_base_sam_bytes is not None
        prepared = prepare_2d_training_run(
            manager,
            runs_root=runs_root,
            entrypoint="agentic_auto_annotate_test",
            effective_config={
                "epochs": 1,
                "batch_size": 1,
                "learning_rate": 0.001,
                "weight_decay": 0.0001,
                "random_seed": 0,
                "input_resolution": [32, 24],
                "preprocessing": {"dataset_adapter": "TwoStageDataset"},
                "model": {
                    "family": "AntEngine",
                    "version": "1",
                    "locator": "TraitRegressor",
                    "parts": "TrainableSAM" if include_parts else "disabled",
                },
                "loss_weights": {"locator": {"heatmap": 1.0, "wh": 1.0}},
                "persist_weights": True,
            },
            backend={
                "backend_id": "builtin_locator_sam",
                "backend_version": "1.0",
                "adapter_id": "agentic_auto_annotate_test",
                "adapter_version": "1.0",
            },
            include_parts=include_parts,
            initial_weight_slots=("parent.sam_base",) if include_parts else (),
        )

        managed_model_root = root / "managed_models"
        staging = root / "staging"
        staging.mkdir()
        checkpoint_name = f"locator_{prepared.run.run_id}.pth"
        (staging / checkpoint_name).write_bytes(checkpoint_bytes)
        artifact_specs = [
            {
                "artifact_id": "locator_checkpoint",
                "role": "output_weights",
                "relative_path": checkpoint_name,
                "media_type": "application/octet-stream",
            }
        ]
        if decoder_bytes is not None:
            decoder_name = f"sam_decoder_lora_{prepared.run.run_id}.pth"
            (staging / decoder_name).write_bytes(decoder_bytes)
            artifact_specs.append(
                {
                    "artifact_id": "sam_decoder_checkpoint",
                    "role": "output_weights",
                    "relative_path": decoder_name,
                    "media_type": "application/octet-stream",
                }
            )
        publisher = auto_annotate_project.TrainingWeightPublisher(managed_model_root)
        publication = publisher.publish_pending(
            prepared.run.run_id,
            staging,
            artifact_specs,
        )
        prepared.run.register_path_base("managed_model_root", managed_model_root)
        artifacts_by_id = {
            item["artifact_id"]: item for item in publication["artifacts"]
        }
        for artifact in publication["artifacts"]:
            prepared.run.add_artifact(
                artifact_id=artifact["artifact_id"],
                role="output_weights",
                path=managed_model_root / Path(artifact["relative_path"]),
                path_base="managed_model_root",
                media_type=artifact["media_type"],
            )
        successful = prepared.run.succeed()
        if activate:
            publisher.activate(prepared.run.run_id, successful)
        return {
            "manager": manager,
            "project_path": project_path,
            "runs_root": runs_root,
            "managed_model_root": managed_model_root,
            "run_id": prepared.run.run_id,
            "checkpoint_path": managed_model_root
            / Path(artifacts_by_id["locator_checkpoint"]["relative_path"]),
            "artifact": artifacts_by_id["locator_checkpoint"],
            "decoder_path": (
                managed_model_root
                / Path(artifacts_by_id["sam_decoder_checkpoint"]["relative_path"])
                if "sam_decoder_checkpoint" in artifacts_by_id
                else None
            ),
            "decoder_artifact": artifacts_by_id.get("sam_decoder_checkpoint"),
            "base_sam_path": base_sam_path,
        }

    def test_auto_annotate_cli_applies_prediction_json(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "auto_annotate"
        tmp.mkdir(parents=True, exist_ok=True)
        image_path = tmp / "specimen.png"
        Image.new("RGB", (100, 80), color=(110, 120, 130)).save(image_path)

        project_path = tmp / "project.json"
        project_path.write_text(
            json.dumps(
                {
                    "name": "demo",
                    "taxonomy": ["Head"],
                    "locator_scope": ["Head"],
                    "images": ["specimen.png"],
                    "labels": {
                        "specimen.png": {
                            "parts": {},
                            "status": "unlabeled",
                            "genus": "Formica",
                            "descriptions": {},
                        }
                    },
                    "scales": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        predictions_path = tmp / "predictions.json"
        predictions_path.write_text(
            json.dumps(
                {
                    "images": {
                        str(image_path): {
                            "polygons": {
                                "Head": [[10, 10], [40, 10], [40, 35], [10, 35]],
                            },
                            "auto_boxes": {
                                "Head": [10, 10, 40, 35],
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_project = tmp / "project_auto.json"
        report = tmp / "auto_report.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "agentic" / "auto_annotate_project.py"),
                "--project",
                str(project_path),
                "--out",
                str(out_project),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(out_project.read_text(encoding="utf-8"))
        labels = next(iter(payload["labels"].values()))
        self.assertIn("Head", labels["parts"])
        self.assertEqual(labels["descriptions"]["Head"], "Auto-Annotated")
        self.assertEqual(labels["auto_box_meta"]["Head"]["source"], "model_prediction")
        summary = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(summary["saved_label_count"], 1)
        self.assertIsNone(summary["checkpoint_evidence"])

    def test_auto_annotate_cli_can_write_draft_boxes_only(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "auto_annotate_draft"
        tmp.mkdir(parents=True, exist_ok=True)
        image_path = tmp / "specimen.png"
        Image.new("RGB", (100, 80), color=(110, 120, 130)).save(image_path)

        project_path = tmp / "project.json"
        project_path.write_text(
            json.dumps(
                {
                    "name": "demo",
                    "taxonomy": ["Head"],
                    "locator_scope": ["Head"],
                    "images": ["specimen.png"],
                    "labels": {
                        "specimen.png": {
                            "parts": {},
                            "status": "unlabeled",
                            "genus": "Formica",
                            "descriptions": {},
                        }
                    },
                    "scales": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        predictions_path = tmp / "predictions.json"
        predictions_path.write_text(
            json.dumps(
                {
                    "images": {
                        str(image_path): {
                            "polygons": {
                                "Head": [[10, 10], [40, 10], [40, 35], [10, 35]],
                            },
                            "auto_boxes": {
                                "Head": [10, 10, 40, 35],
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_project = tmp / "project_auto_draft.json"
        report = tmp / "auto_report_draft.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "agentic" / "auto_annotate_project.py"),
                "--project",
                str(project_path),
                "--out",
                str(out_project),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report),
                "--draft-boxes-only",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(out_project.read_text(encoding="utf-8"))
        labels = next(iter(payload["labels"].values()))
        self.assertEqual(labels.get("parts", {}), {})
        self.assertEqual(labels["auto_boxes"]["Head"], [10.0, 10.0, 40.0, 35.0])
        self.assertEqual(labels["auto_box_meta"]["Head"]["source"], "model_prediction")
        summary = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(summary["draft_boxes_only"])
        self.assertEqual(summary["results"][0]["detected_count"], 1)

    def test_auto_annotate_cli_can_write_box_only_model_drafts(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "auto_annotate_box_only_draft"
        tmp.mkdir(parents=True, exist_ok=True)
        image_path = tmp / "specimen.png"
        Image.new("RGB", (100, 80), color=(110, 120, 130)).save(image_path)

        project_path = tmp / "project.json"
        project_path.write_text(
            json.dumps(
                {
                    "name": "demo",
                    "taxonomy": ["Head"],
                    "locator_scope": ["Head"],
                    "images": ["specimen.png"],
                    "labels": {
                        "specimen.png": {
                            "parts": {},
                            "status": "unlabeled",
                            "genus": "Formica",
                            "descriptions": {},
                        }
                    },
                    "scales": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        predictions_path = tmp / "predictions.json"
        predictions_path.write_text(
            json.dumps(
                {
                    "images": {
                        str(image_path): {
                            "polygons": {},
                            "auto_boxes": {
                                "Head": [12, 14, 48, 45],
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_project = tmp / "project_auto_box_only_draft.json"
        report = tmp / "auto_box_only_draft_report.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "agentic" / "auto_annotate_project.py"),
                "--project",
                str(project_path),
                "--out",
                str(out_project),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report),
                "--draft-boxes-only",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(out_project.read_text(encoding="utf-8"))
        labels = next(iter(payload["labels"].values()))
        self.assertEqual(labels.get("parts", {}), {})
        self.assertEqual(labels["auto_boxes"]["Head"], [12.0, 14.0, 48.0, 45.0])
        self.assertEqual(labels["auto_box_meta"]["Head"]["source"], "model_prediction")
        summary = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(summary["saved_label_count"], 1)

    def test_auto_annotate_cli_only_new_replaces_unconfirmed_vlm_draft(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "auto_annotate_priority"
        tmp.mkdir(parents=True, exist_ok=True)
        image_path = tmp / "specimen.png"
        Image.new("RGB", (100, 80), color=(110, 120, 130)).save(image_path)

        project_path = tmp / "project.json"
        project_path.write_text(
            json.dumps(
                {
                    "name": "demo",
                    "taxonomy": ["Head"],
                    "locator_scope": ["Head"],
                    "images": ["specimen.png"],
                    "labels": {
                        "specimen.png": {
                            "parts": {"Head": [[10, 10], [40, 10], [40, 35], [10, 35]]},
                            "auto_boxes": {"Head": [10, 10, 40, 35]},
                            "auto_box_meta": {"Head": {"source": "vlm_first_mile", "review_status": "draft"}},
                            "descriptions": {"Head": "Auto-Annotated"},
                            "status": "labeled",
                            "genus": "Formica",
                        }
                    },
                    "scales": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        predictions_path = tmp / "predictions.json"
        predictions_path.write_text(
            json.dumps(
                {
                    "images": {
                        str(image_path): {
                            "polygons": {
                                "Head": [[20, 20], [70, 20], [70, 55], [20, 55]],
                            },
                            "auto_boxes": {
                                "Head": [20, 20, 70, 55],
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_project = tmp / "project_auto_priority.json"
        report = tmp / "auto_priority_report.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "agentic" / "auto_annotate_project.py"),
                "--project",
                str(project_path),
                "--out",
                str(out_project),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report),
                "--only-new",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(out_project.read_text(encoding="utf-8"))
        labels = next(iter(payload["labels"].values()))
        self.assertEqual(labels["parts"]["Head"], [[20.0, 20.0], [70.0, 20.0], [70.0, 55.0], [20.0, 55.0]])
        self.assertEqual(labels["auto_boxes"]["Head"], [20.0, 20.0, 70.0, 55.0])
        self.assertEqual(labels["auto_box_meta"]["Head"]["source"], "model_prediction")
        summary = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(summary["saved_label_count"], 1)

    def test_auto_annotate_cli_keeps_confirmed_label_even_without_only_new(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "auto_annotate_confirmed_priority"
        tmp.mkdir(parents=True, exist_ok=True)
        image_path = tmp / "specimen.png"
        Image.new("RGB", (100, 80), color=(110, 120, 130)).save(image_path)

        project_path = tmp / "project.json"
        project_path.write_text(
            json.dumps(
                {
                    "name": "demo",
                    "taxonomy": ["Head"],
                    "locator_scope": ["Head"],
                    "images": ["specimen.png"],
                    "labels": {
                        "specimen.png": {
                            "parts": {"Head": [[10, 10], [40, 10], [40, 35], [10, 35]]},
                            "auto_boxes": {"Head": [10, 10, 40, 35]},
                            "auto_box_meta": {"Head": {"source": "model_prediction", "review_status": "confirmed"}},
                            "descriptions": {},
                            "status": "labeled",
                            "genus": "Formica",
                        }
                    },
                    "scales": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        predictions_path = tmp / "predictions.json"
        predictions_path.write_text(
            json.dumps(
                {
                    "images": {
                        str(image_path): {
                            "polygons": {
                                "Head": [[20, 20], [70, 20], [70, 55], [20, 55]],
                            },
                            "auto_boxes": {
                                "Head": [20, 20, 70, 55],
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_project = tmp / "project_auto_confirmed_priority.json"
        report = tmp / "auto_confirmed_priority_report.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "agentic" / "auto_annotate_project.py"),
                "--project",
                str(project_path),
                "--out",
                str(out_project),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(out_project.read_text(encoding="utf-8"))
        labels = next(iter(payload["labels"].values()))
        self.assertEqual(labels["parts"]["Head"], [[10, 10], [40, 10], [40, 35], [10, 35]])
        self.assertEqual(labels["auto_boxes"]["Head"], [10, 10, 40, 35])
        summary = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(summary["saved_label_count"], 0)

    def test_apply_failure_writes_traceable_failure_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self._managed_locator_fixture(root, image_count=2)
            image_path = fixture["manager"].project_data["images"][0]
            image_key = fixture["manager"]._image_data_key(image_path)
            fixture["manager"].project_data["labels"][image_key] = (
                fixture["manager"]._default_label_entry()
            )
            fixture["manager"]._mark_sqlite_image_dirty(image_key)
            fixture["manager"].save_project()
            predictions_path = root / "predictions.json"
            predictions_path.write_text(
                json.dumps(
                    {
                        "images": {
                            image_path: {
                                "polygons": {
                                    "Head": [[2, 2], [20, 2], [10, 18]],
                                },
                                "auto_boxes": {"Head": [2, 2, 20, 18]},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            report_path = root / "apply-failure-report.json"
            argv = [
                "auto_annotate_project.py",
                "--project",
                str(fixture["project_path"]),
                "--out",
                str(fixture["project_path"]),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report_path),
            ]

            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                auto_annotate_project,
                "_apply_payload",
                side_effect=RuntimeError("synthetic apply failure"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "synthetic apply failure"
                ):
                    auto_annotate_project.main()

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["failure_stage"], "apply_predictions")
            self.assertEqual(report["error_type"], "RuntimeError")
            self.assertEqual(report["image_count"], 0)
            self.assertEqual(report["applied_label_count"], 0)
            self.assertEqual(report["saved_label_count"], 0)
            self.assertFalse(report["save_completed"])
            self.assertEqual(report["results"], [])

    def test_project_save_failure_writes_traceable_failure_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self._managed_locator_fixture(root, image_count=2)
            image_path = fixture["manager"].project_data["images"][0]
            image_key = fixture["manager"]._image_data_key(image_path)
            fixture["manager"].project_data["labels"][image_key] = (
                fixture["manager"]._default_label_entry()
            )
            fixture["manager"]._mark_sqlite_image_dirty(image_key)
            fixture["manager"].save_project()
            predictions_path = root / "predictions.json"
            predictions_path.write_text(
                json.dumps(
                    {
                        "images": {
                            image_path: {
                                "polygons": {
                                    "Head": [[2, 2], [20, 2], [10, 18]],
                                },
                                "auto_boxes": {"Head": [2, 2, 20, 18]},
                                "scores": {"Head": 0.91},
                                "meta": {"cascade_applied_count": 0},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            report_path = root / "save-failure-report.json"
            argv = [
                "auto_annotate_project.py",
                "--project",
                str(fixture["project_path"]),
                "--out",
                str(fixture["project_path"]),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report_path),
            ]

            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                auto_annotate_project.ProjectManager,
                "save_project",
                side_effect=OSError("synthetic project save failure"),
            ):
                with self.assertRaisesRegex(
                    OSError, "synthetic project save failure"
                ):
                    auto_annotate_project.main()

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["failure_stage"], "project_save")
            self.assertEqual(report["error_type"], "OSError")
            self.assertEqual(report["image_count"], 1)
            self.assertEqual(report["applied_label_count"], 1)
            self.assertEqual(report["saved_label_count"], 0)
            self.assertFalse(report["save_completed"])
            self.assertEqual(report["results"][0]["prediction_scores"], {"Head": 0.91})
            self.assertEqual(
                report["results"][0]["prediction_meta"],
                {"cascade_applied_count": 0},
            )

    def test_external_image_apply_failure_rolls_back_memory_and_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self._managed_locator_fixture(root, image_count=2)
            external_image = root / "external-apply-failure.png"
            Image.new("RGB", (32, 24), color=(140, 120, 100)).save(external_image)
            predictions_path = root / "external-apply-failure-predictions.json"
            predictions_path.write_text(
                json.dumps(
                    {
                        "images": {
                            str(external_image): {
                                "polygons": {
                                    "Head": [[2, 2], [20, 2], [10, 18]],
                                },
                                "auto_boxes": {"Head": [2, 2, 20, 18]},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            report_path = root / "external-apply-failure-report.json"
            observed_manager = ProjectManager()
            observed_manager.load_project(str(fixture["project_path"]))
            before_state = observed_manager._snapshot_runtime_state(deep=True)
            argv = [
                "auto_annotate_project.py",
                "--project",
                str(fixture["project_path"]),
                "--out",
                str(fixture["project_path"]),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report_path),
            ]

            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                auto_annotate_project,
                "ProjectManager",
                return_value=observed_manager,
            ), mock.patch.object(
                observed_manager,
                "add_images",
                wraps=observed_manager.add_images,
            ) as add_images, mock.patch.object(
                observed_manager,
                "save_project",
                wraps=observed_manager.save_project,
            ) as save_project, mock.patch.object(
                auto_annotate_project,
                "_apply_payload",
                side_effect=RuntimeError("synthetic external apply failure"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "synthetic external apply failure"
                ):
                    auto_annotate_project.main()

            add_images.assert_called_once()
            self.assertFalse(add_images.call_args.kwargs.get("save", True))
            save_project.assert_not_called()
            self.assertEqual(
                observed_manager._snapshot_runtime_state(deep=True),
                before_state,
            )
            reloaded = ProjectManager()
            reloaded.load_project(str(fixture["project_path"]))
            self.assertEqual(
                reloaded.project_data["images"],
                before_state["project_data"]["images"],
            )
            self.assertNotIn(str(external_image.resolve()), reloaded.project_data["images"])
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["failure_stage"], "apply_predictions")
            self.assertFalse(report["save_completed"])

    def test_external_image_final_save_failure_rolls_back_memory_and_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self._managed_locator_fixture(root, image_count=2)
            external_image = root / "external-save-failure.png"
            Image.new("RGB", (32, 24), color=(150, 130, 110)).save(external_image)
            predictions_path = root / "external-save-failure-predictions.json"
            predictions_path.write_text(
                json.dumps(
                    {
                        "images": {
                            str(external_image): {
                                "polygons": {
                                    "Head": [[2, 2], [20, 2], [10, 18]],
                                },
                                "auto_boxes": {"Head": [2, 2, 20, 18]},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            report_path = root / "external-save-failure-report.json"
            observed_manager = ProjectManager()
            observed_manager.load_project(str(fixture["project_path"]))
            before_state = observed_manager._snapshot_runtime_state(deep=True)
            argv = [
                "auto_annotate_project.py",
                "--project",
                str(fixture["project_path"]),
                "--out",
                str(fixture["project_path"]),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report_path),
            ]

            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                auto_annotate_project,
                "ProjectManager",
                return_value=observed_manager,
            ), mock.patch.object(
                observed_manager,
                "add_images",
                wraps=observed_manager.add_images,
            ) as add_images, mock.patch.object(
                observed_manager,
                "save_project",
                side_effect=OSError("synthetic external save failure"),
            ) as save_project:
                with self.assertRaisesRegex(
                    OSError, "synthetic external save failure"
                ):
                    auto_annotate_project.main()

            add_images.assert_called_once()
            self.assertFalse(add_images.call_args.kwargs.get("save", True))
            save_project.assert_called_once_with()
            self.assertEqual(
                observed_manager._snapshot_runtime_state(deep=True),
                before_state,
            )
            reloaded = ProjectManager()
            reloaded.load_project(str(fixture["project_path"]))
            self.assertEqual(
                reloaded.project_data["images"],
                before_state["project_data"]["images"],
            )
            self.assertNotIn(str(external_image.resolve()), reloaded.project_data["images"])
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["failure_stage"], "project_save")
            self.assertEqual(report["applied_label_count"], 1)
            self.assertEqual(report["saved_label_count"], 0)
            self.assertFalse(report["save_completed"])

    def test_legacy_apply_failure_discards_buffered_journal_and_project_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = []
            for index in range(2):
                image_path = root / f"legacy-{index}.png"
                Image.new(
                    "RGB",
                    (32, 24),
                    color=(120 + index, 100, 80),
                ).save(image_path)
                images.append(image_path)

            project_path = root / "legacy.json"
            project_path.write_text(
                json.dumps(
                    {
                        "name": "legacy-transaction",
                        "taxonomy": ["Head"],
                        "locator_scope": ["Head"],
                        "images": [path.name for path in images],
                        "labels": {},
                        "scales": {},
                    }
                ),
                encoding="utf-8",
            )
            project_bytes_before = project_path.read_bytes()
            journal_path = root / "legacy.label_journal.jsonl"
            journal_path.write_bytes(b'{"existing": true}\n')
            journal_bytes_before = journal_path.read_bytes()
            predictions_path = root / "legacy-predictions.json"
            predictions_path.write_text(
                json.dumps(
                    {
                        "images": {
                            str(image_path): {
                                "polygons": {
                                    "Head": [[2, 2], [20, 2], [10, 18]],
                                },
                                "auto_boxes": {"Head": [2, 2, 20, 18]},
                            }
                            for image_path in images
                        }
                    }
                ),
                encoding="utf-8",
            )
            report_path = root / "legacy-failure-report.json"
            observed_manager = ProjectManager()
            captured_transaction_state = {}
            real_snapshot = observed_manager._snapshot_runtime_state

            def capture_transaction_state(*args, **kwargs):
                state = real_snapshot(*args, **kwargs)
                captured_transaction_state["state"] = state
                return state

            real_apply = auto_annotate_project._apply_payload
            apply_count = 0

            def fail_second_record(*args, **kwargs):
                nonlocal apply_count
                apply_count += 1
                if apply_count == 2:
                    raise RuntimeError("synthetic second-record failure")
                return real_apply(*args, **kwargs)

            argv = [
                "auto_annotate_project.py",
                "--project",
                str(project_path),
                "--out",
                str(project_path),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report_path),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                auto_annotate_project,
                "ProjectManager",
                return_value=observed_manager,
            ), mock.patch.object(
                observed_manager,
                "_snapshot_runtime_state",
                side_effect=capture_transaction_state,
            ), mock.patch.object(
                auto_annotate_project,
                "_apply_payload",
                side_effect=fail_second_record,
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "synthetic second-record failure"
                ):
                    auto_annotate_project.main()

            self.assertEqual(apply_count, 2)
            self.assertEqual(
                observed_manager.project_data,
                captured_transaction_state["state"]["project_data"],
            )
            self.assertEqual(observed_manager._label_journal_transaction_stack, [])
            self.assertEqual(observed_manager._label_journal_transaction_entries, [])
            self.assertEqual(project_path.read_bytes(), project_bytes_before)
            self.assertEqual(journal_path.read_bytes(), journal_bytes_before)
            reloaded = ProjectManager()
            reloaded.load_project(str(project_path))
            for image_path in images:
                self.assertEqual(reloaded.get_labels(str(image_path)), {})
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["failure_stage"], "apply_predictions")
            self.assertEqual(report["image_count"], 1)
            self.assertEqual(report["applied_label_count"], 1)
            self.assertEqual(report["saved_label_count"], 0)
            self.assertFalse(report["save_completed"])

    def test_legacy_journal_failure_reports_saved_project_as_partial_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "legacy.png"
            Image.new("RGB", (32, 24), color=(120, 100, 80)).save(image_path)
            project_path = root / "legacy.json"
            project_path.write_text(
                json.dumps(
                    {
                        "name": "legacy-journal-partial",
                        "taxonomy": ["Head"],
                        "locator_scope": ["Head"],
                        "images": [image_path.name],
                        "labels": {},
                        "scales": {},
                    }
                ),
                encoding="utf-8",
            )
            predictions_path = root / "predictions.json"
            predictions_path.write_text(
                json.dumps(
                    {
                        "images": {
                            str(image_path): {
                                "polygons": {
                                    "Head": [[2, 2], [20, 2], [10, 18]],
                                },
                                "auto_boxes": {"Head": [2, 2, 20, 18]},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            report_path = root / "partial-report.json"
            observed_manager = ProjectManager()
            argv = [
                "auto_annotate_project.py",
                "--project",
                str(project_path),
                "--out",
                str(project_path),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report_path),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                auto_annotate_project,
                "ProjectManager",
                return_value=observed_manager,
            ), mock.patch.object(
                observed_manager,
                "_write_label_journal_lines",
                return_value=False,
            ):
                self.assertEqual(auto_annotate_project.main(), 3)

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "partial_success")
            self.assertEqual(report["warning_stage"], "label_journal_commit")
            self.assertTrue(report["save_completed"])
            self.assertEqual(report["saved_label_count"], 1)
            self.assertEqual(report["journal_status"], "failed")
            self.assertGreater(report["journal_entry_count"], 0)
            self.assertGreater(report["journal_byte_count"], 0)
            self.assertFalse(
                report["journal_commit"]["retryable_after_exit"]
            )
            self.assertEqual(
                report["warnings"][0]["code"],
                "legacy_label_journal_commit_failed",
            )

            reloaded = ProjectManager()
            reloaded.load_project(str(project_path))
            image_key = str(image_path.resolve())
            self.assertEqual(
                reloaded.get_labels(image_key)["Head"],
                [[2.0, 2.0], [20.0, 2.0], [10.0, 18.0]],
            )
            self.assertEqual(
                len(observed_manager._label_journal_transaction_stack),
                1,
            )
            retry_token = observed_manager._label_journal_transaction_stack[-1][
                "token"
            ]
            self.assertTrue(
                observed_manager.commit_label_journal_transaction(retry_token)
            )

    def test_external_image_success_persists_image_label_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_manager = ProjectManager()
            project_path = Path(
                project_manager.create_project("external-success", root / "project")
            )
            external_image = root / "external-success.png"
            Image.new("RGB", (32, 24), color=(150, 120, 90)).save(external_image)
            predictions_path = root / "external-success-predictions.json"
            predictions_path.write_text(
                json.dumps(
                    {
                        "images": {
                            str(external_image): {
                                "polygons": {
                                    "Head": [[2, 2], [20, 2], [10, 18]],
                                },
                                "auto_boxes": {"Head": [2, 2, 20, 18]},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            report_path = root / "external-success-report.json"
            observed_manager = ProjectManager()
            argv = [
                "auto_annotate_project.py",
                "--project",
                str(project_path),
                "--out",
                str(project_path),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report_path),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                auto_annotate_project,
                "ProjectManager",
                return_value=observed_manager,
            ), mock.patch.object(
                observed_manager,
                "add_images",
                wraps=observed_manager.add_images,
            ) as add_images, mock.patch.object(
                observed_manager,
                "save_project",
                wraps=observed_manager.save_project,
            ) as save_project:
                self.assertEqual(auto_annotate_project.main(), 0)

            add_images.assert_called_once_with([str(external_image.resolve())], save=False)
            save_project.assert_called_once_with()
            reloaded = ProjectManager()
            reloaded.load_project(str(project_path))
            external_path = str(external_image.resolve())
            self.assertIn(external_path, reloaded.project_data["images"])
            self.assertEqual(
                reloaded.get_labels(external_path)["Head"],
                [[2.0, 2.0], [20.0, 2.0], [10.0, 18.0]],
            )
            self.assertEqual(
                reloaded.get_auto_boxes(external_path)["Head"],
                [2.0, 2.0, 20.0, 18.0],
            )
            external_entry = reloaded.project_data["labels"][external_path]
            self.assertEqual(
                get_part_training_truth(external_entry, "Head"),
                {"source": "model_prediction", "review_status": "draft"},
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["storage_write_mode"], "sqlite_in_place")
            self.assertEqual(report["image_count"], 1)
            self.assertEqual(report["applied_label_count"], 1)
            self.assertEqual(report["saved_label_count"], 1)
            self.assertTrue(report["save_completed"])

    def test_external_image_only_new_preserves_manual_truth_and_adds_external(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_manager = ProjectManager()
            project_path = Path(
                project_manager.create_project("external-only-new", root / "project")
            )
            existing_image = root / "existing.png"
            external_image = root / "external.png"
            Image.new("RGB", (32, 24), color=(100, 90, 80)).save(existing_image)
            Image.new("RGB", (32, 24), color=(130, 120, 110)).save(external_image)
            existing_path = str(existing_image.resolve())
            external_path = str(external_image.resolve())
            original_points = [[1, 1], [12, 1], [6, 10]]
            project_manager.add_images([existing_path], save=True)
            project_manager.update_label(
                existing_path,
                "Head",
                original_points,
                box=[1, 1, 12, 10],
                save=True,
            )
            predictions_path = root / "external-only-new-predictions.json"
            predicted_points = [[2, 2], [20, 2], [10, 18]]
            predictions_path.write_text(
                json.dumps(
                    {
                        "images": {
                            existing_path: {
                                "polygons": {"Head": predicted_points},
                                "auto_boxes": {"Head": [2, 2, 20, 18]},
                            },
                            external_path: {
                                "polygons": {"Head": predicted_points},
                                "auto_boxes": {"Head": [2, 2, 20, 18]},
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            report_path = root / "external-only-new-report.json"
            observed_manager = ProjectManager()
            argv = [
                "auto_annotate_project.py",
                "--project",
                str(project_path),
                "--out",
                str(project_path),
                "--predictions",
                str(predictions_path),
                "--only-new",
                "--report",
                str(report_path),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                auto_annotate_project,
                "ProjectManager",
                return_value=observed_manager,
            ), mock.patch.object(
                observed_manager,
                "save_project",
                wraps=observed_manager.save_project,
            ) as save_project:
                self.assertEqual(auto_annotate_project.main(), 0)

            save_project.assert_called_once_with()
            reloaded = ProjectManager()
            reloaded.load_project(str(project_path))
            self.assertEqual(reloaded.get_labels(existing_path)["Head"], original_points)
            existing_entry = reloaded.project_data["labels"][existing_path]
            self.assertEqual(
                get_part_training_truth(existing_entry, "Head"),
                {
                    "source": "manual",
                    "review_status": "confirmed",
                    "accepted_via": "manual_edit",
                },
            )
            self.assertIn(external_path, reloaded.project_data["images"])
            self.assertEqual(
                reloaded.get_labels(external_path)["Head"], predicted_points
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["image_count"], 2)
            self.assertEqual(report["applied_label_count"], 1)
            self.assertEqual(report["saved_label_count"], 1)
            self.assertEqual(report["rejected_count"], 1)
            self.assertEqual(
                report["results"][0]["rejected"],
                [{"part": "Head", "reason": "already_labeled"}],
            )
            self.assertTrue(report["save_completed"])

    def test_legacy_label_journal_transactions_are_nested_and_ordered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = ProjectManager()
            manager.current_project_path = str(root / "nested.json")
            manager.enable_legacy_json_writes_for_compatibility(True)
            image_path = str(root / "image.png")
            outer = manager.begin_label_journal_transaction()
            self.assertTrue(manager._append_label_journal_entry(image_path, "outer-1"))
            inner = manager.begin_label_journal_transaction()
            self.assertTrue(manager._append_label_journal_entry(image_path, "inner"))
            manager.rollback_label_journal_transaction(inner)
            self.assertTrue(manager._append_label_journal_entry(image_path, "outer-2"))
            self.assertTrue(manager.commit_label_journal_transaction(outer))

            records = [
                json.loads(line)
                for line in (root / "nested.label_journal.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(
                [record["action"] for record in records],
                ["outer-1", "outer-2"],
            )

    def test_inner_journal_commit_is_discarded_by_outer_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = ProjectManager()
            manager.current_project_path = str(root / "nested-rollback.json")
            manager.enable_legacy_json_writes_for_compatibility(True)
            image_path = str(root / "image.png")

            outer = manager.begin_label_journal_transaction()
            self.assertTrue(manager._append_label_journal_entry(image_path, "outer"))
            inner = manager.begin_label_journal_transaction()
            self.assertTrue(manager._append_label_journal_entry(image_path, "inner"))
            self.assertTrue(manager.commit_label_journal_transaction(inner))
            manager.rollback_label_journal_transaction(outer)

            self.assertEqual(manager._label_journal_transaction_stack, [])
            self.assertEqual(manager._label_journal_transaction_entries, [])
            self.assertFalse(
                (root / "nested-rollback.label_journal.jsonl").exists()
            )

    def test_journal_commit_failures_keep_original_and_allow_single_retry(self):
        for operation in ("write", "short_write", "flush", "fsync"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manager = ProjectManager()
                manager.current_project_path = str(root / "retry.json")
                manager.enable_legacy_json_writes_for_compatibility(True)
                image_path = str(root / "image.png")
                journal_path = root / "retry.label_journal.jsonl"
                original = b'{"existing": true}\n'
                journal_path.write_bytes(original)
                Path(f"{journal_path}.lock").write_bytes(b"0")
                token = manager.begin_label_journal_transaction()
                self.assertTrue(
                    manager._append_label_journal_entry(image_path, "retry-once")
                )
                entries_before = list(manager._label_journal_transaction_entries)
                bytes_before = manager._label_journal_transaction_bytes

                if operation == "fsync":
                    fault = mock.patch(
                        "AntSleap.core.project.os.fsync",
                        side_effect=OSError("synthetic journal fsync failure"),
                    )
                else:
                    real_open = open

                    def faulting_open(path, mode="r", *args, **kwargs):
                        handle = real_open(path, mode, *args, **kwargs)
                        if str(path).endswith(".tmp") and mode == "w+b":
                            return _FaultingBinaryFile(handle, operation)
                        return handle

                    fault = mock.patch(
                        "AntSleap.core.project.open",
                        side_effect=faulting_open,
                        create=True,
                    )

                with fault:
                    self.assertFalse(
                        manager.commit_label_journal_transaction(token)
                    )

                self.assertEqual(journal_path.read_bytes(), original)
                self.assertEqual(
                    manager._label_journal_transaction_entries,
                    entries_before,
                )
                self.assertEqual(
                    manager._label_journal_transaction_bytes,
                    bytes_before,
                )
                self.assertIs(
                    manager._label_journal_transaction_stack[-1]["token"],
                    token,
                )
                self.assertTrue(manager.commit_label_journal_transaction(token))
                records = journal_path.read_text(encoding="utf-8").splitlines()
                actions = [json.loads(line).get("action") for line in records]
                self.assertEqual(actions.count("retry-once"), 1)
                self.assertEqual(manager._label_journal_transaction_stack, [])

    def test_journal_replace_that_commits_then_raises_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = ProjectManager()
            manager.current_project_path = str(root / "replace.json")
            manager.enable_legacy_json_writes_for_compatibility(True)
            token = manager.begin_label_journal_transaction()
            self.assertTrue(
                manager._append_label_journal_entry(
                    str(root / "image.png"),
                    "replace-once",
                )
            )
            real_replace = __import__("os").replace

            def replace_then_raise(source, target):
                real_replace(source, target)
                raise OSError("synthetic post-replace failure")

            with mock.patch(
                "AntSleap.core.project.os.replace",
                side_effect=replace_then_raise,
            ):
                self.assertTrue(manager.commit_label_journal_transaction(token))

            journal_path = root / "replace.label_journal.jsonl"
            records = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                [record.get("action") for record in records],
                ["replace-once"],
            )
            self.assertEqual(manager._label_journal_transaction_stack, [])

    def test_journal_post_replace_fallback_rejects_same_size_prefix_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = ProjectManager()
            manager.current_project_path = str(root / "tampered-replace.json")
            manager.enable_legacy_json_writes_for_compatibility(True)
            journal_path = root / "tampered-replace.label_journal.jsonl"
            original = b'{"action":"seed"}\n'
            journal_path.write_bytes(original)
            token = manager.begin_label_journal_transaction()
            self.assertTrue(
                manager._append_label_journal_entry(
                    str(root / "image.png"),
                    "replace-after-tamper",
                )
            )
            appended = manager._label_journal_transaction_entries[0][1].encode(
                "utf-8"
            )
            real_replace = __import__("os").replace

            def replace_tamper_then_raise(source, target):
                real_replace(source, target)
                published = Path(target).read_bytes()
                Path(target).write_bytes(b"[" + published[1:])
                raise OSError("synthetic post-replace tampering")

            with mock.patch(
                "AntSleap.core.project.os.replace",
                side_effect=replace_tamper_then_raise,
            ):
                self.assertFalse(manager.commit_label_journal_transaction(token))

            self.assertIs(
                manager._label_journal_transaction_stack[-1]["token"],
                token,
            )
            published = journal_path.read_bytes()
            self.assertEqual(len(published), len(original) + len(appended))
            self.assertTrue(published.endswith(appended))
            manager.rollback_label_journal_transaction(token)

    def test_large_journal_prefix_short_write_preserves_original_and_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = ProjectManager()
            manager.current_project_path = str(root / "large-prefix.json")
            manager.enable_legacy_json_writes_for_compatibility(True)
            journal_path = root / "large-prefix.label_journal.jsonl"
            original = (
                b'{"padding":"'
                + (b"x" * (1024 * 1024 + 64))
                + b'"}\n'
            )
            journal_path.write_bytes(original)
            token = manager.begin_label_journal_transaction()
            self.assertTrue(
                manager._append_label_journal_entry(
                    str(root / "image.png"),
                    "after-large-prefix",
                )
            )
            real_open = open

            def faulting_open(path, mode="r", *args, **kwargs):
                handle = real_open(path, mode, *args, **kwargs)
                if str(path).endswith(".tmp") and mode == "w+b":
                    return _FaultingBinaryFile(handle, "prefix_short_write")
                return handle

            with mock.patch(
                "AntSleap.core.project.open",
                side_effect=faulting_open,
                create=True,
            ):
                self.assertFalse(manager.commit_label_journal_transaction(token))

            self.assertEqual(journal_path.read_bytes(), original)
            self.assertIs(
                manager._label_journal_transaction_stack[-1]["token"],
                token,
            )
            self.assertTrue(manager.commit_label_journal_transaction(token))
            published = journal_path.read_bytes()
            self.assertTrue(published.startswith(original))
            self.assertEqual(
                published[len(original) :].count(b'"action": "after-large-prefix"'),
                1,
            )

    def test_legacy_label_journal_transaction_buffer_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = ProjectManager()
            manager.current_project_path = str(root / "bounded.json")
            manager.enable_legacy_json_writes_for_compatibility(True)
            token = manager.begin_label_journal_transaction()
            with mock.patch(
                "AntSleap.core.project.LABEL_JOURNAL_TRANSACTION_MAX_RECORDS",
                1,
            ):
                self.assertTrue(
                    manager._append_label_journal_entry(
                        str(root / "image.png"), "first"
                    )
                )
                with self.assertRaisesRegex(
                    RuntimeError,
                    "label_journal_transaction_buffer_limit_exceeded",
                ):
                    manager._append_label_journal_entry(
                        str(root / "image.png"), "second"
                    )
            manager.rollback_label_journal_transaction(token)
            self.assertEqual(manager._label_journal_transaction_entries, [])
            self.assertFalse((root / "bounded.label_journal.jsonl").exists())

    def test_legacy_label_journal_byte_limit_accepts_exact_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = ProjectManager()
            manager.current_project_path = str(root / "byte-bounded.json")
            manager.enable_legacy_json_writes_for_compatibility(True)
            image_path = str(root / "image.png")
            with mock.patch.object(
                manager,
                "_json_timestamp",
                return_value="2026-08-24T00:00:00Z",
            ):
                probe = manager.begin_label_journal_transaction()
                manager._append_label_journal_entry(image_path, "exact")
                exact_bytes = manager._label_journal_transaction_bytes
                manager.rollback_label_journal_transaction(probe)

                token = manager.begin_label_journal_transaction()
                with mock.patch(
                    "AntSleap.core.project.LABEL_JOURNAL_TRANSACTION_MAX_BYTES",
                    exact_bytes,
                ):
                    self.assertTrue(
                        manager._append_label_journal_entry(image_path, "exact")
                    )
                    entries_before = list(
                        manager._label_journal_transaction_entries
                    )
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "label_journal_transaction_buffer_limit_exceeded",
                    ):
                        manager._append_label_journal_entry(image_path, "x")
                    self.assertEqual(
                        manager._label_journal_transaction_entries,
                        entries_before,
                    )
                    self.assertEqual(
                        manager._label_journal_transaction_bytes,
                        exact_bytes,
                    )
                manager.rollback_label_journal_transaction(token)

    def test_active_journal_transaction_blocks_project_reset_and_load(self):
        manager = ProjectManager()
        token = manager.begin_label_journal_transaction()
        with self.assertRaisesRegex(
            RuntimeError,
            "label_journal_transaction_active:clear",
        ):
            manager.clear()
        with self.assertRaisesRegex(
            RuntimeError,
            "label_journal_transaction_active:load_project",
        ):
            manager.load_project("unused.json")
        manager.rollback_label_journal_transaction(token)

    def test_run_engine_loads_active_managed_locator_and_reports_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._managed_locator_fixture(Path(tmp))

            class FakeEngine:
                loaded_paths = []
                loaded_payloads = []
                route_manifests = []
                instances = []
                full_pipeline_calls = 0
                box_pipeline_calls = 0

                def __init__(
                    self,
                    num_classes,
                    device,
                    weights_dir=None,
                    locator_scope=None,
                ):
                    self.num_classes = num_classes
                    self.device = device
                    self.weights_dir = str(Path(weights_dir).resolve())
                    self.locator_scope = list(locator_scope or [])
                    self.locator = None
                    self.loaded_locator_timestamp = None
                    self.loaded_locator_schema_version = ""
                    self.loaded_locator_scope = []
                    self.cascade_manager = mock.Mock()
                    self.cascade_manager.expert_dir = str(
                        Path(self.weights_dir) / "experts"
                    )
                    self.cascade_manager.route_manifest_path = str(
                        Path(self.cascade_manager.expert_dir)
                        / "cascade_routes.json"
                    )
                    type(self).instances.append(self)

                def load_locator(
                    self,
                    timestamp,
                    *,
                    checkpoint_path=None,
                    checkpoint_payload=None,
                    require_complete=False,
                    expected_locator_scope=None,
                ):
                    self.locator = object()
                    self.loaded_locator_timestamp = timestamp
                    self.loaded_locator_schema_version = (
                        "taxamask_locator_checkpoint_v2"
                    )
                    self.loaded_locator_scope = list(expected_locator_scope or [])
                    self.loaded_paths.append(
                        (Path(self.weights_dir), Path(checkpoint_path))
                    )
                    self.loaded_payloads.append(
                        (
                            bytes(checkpoint_payload),
                            bool(require_complete),
                            list(expected_locator_scope or []),
                        )
                    )

                def predict_full_pipeline(
                    self,
                    image_path,
                    taxonomy,
                    locator_scope,
                    conf_thresh,
                    project_route_manifest=None,
                ):
                    type(self).full_pipeline_calls += 1
                    type(self).route_manifests.append(project_route_manifest)
                    return {"polygons": {}, "auto_boxes": {}}

                def predict_box_pipeline(
                    self,
                    image_path,
                    taxonomy,
                    locator_scope,
                    conf_thresh,
                    project_route_manifest=None,
                ):
                    type(self).box_pipeline_calls += 1
                    type(self).route_manifests.append(project_route_manifest)
                    return {"polygons": {}, "auto_boxes": {}}

            report_path = Path(tmp) / "report.json"
            output_path = Path(fixture["project_path"])
            argv = [
                "auto_annotate_project.py",
                "--project",
                str(fixture["project_path"]),
                "--out",
                str(output_path),
                "--run-engine",
                "--training-run-id",
                fixture["run_id"],
                "--runs-root",
                str(fixture["runs_root"]),
                "--managed-model-root",
                str(fixture["managed_model_root"]),
                "--draft-boxes-only",
                "--report",
                str(report_path),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch(
                "AntSleap.core.engine.AntEngine", FakeEngine
            ):
                self.assertEqual(auto_annotate_project.main(), 0)

            report = json.loads(report_path.read_text(encoding="utf-8"))
            evidence = report["checkpoint_evidence"]
            self.assertEqual(evidence["run_id"], fixture["run_id"])
            self.assertEqual(evidence["path_base"], "managed_model_root")
            self.assertEqual(
                evidence["relative_path"], fixture["artifact"]["relative_path"]
            )
            self.assertEqual(evidence["digest"], fixture["artifact"]["digest"])
            self.assertEqual(evidence["hash_algorithm"], "sha256")
            self.assertTrue(evidence["loaded"])
            self.assertEqual(
                evidence["checkpoint_schema_version"],
                "taxamask_locator_checkpoint_v2",
            )
            expected_scope = fixture["manager"].get_locator_scope()
            self.assertEqual(evidence["locator_scope"], expected_scope)
            self.assertEqual(report["engine_prediction_mode"], "locator_boxes")
            self.assertEqual(report["storage_write_mode"], "sqlite_in_place")
            self.assertEqual(
                Path(report["sqlite_database"]),
                Path(fixture["manager"].current_database_path).resolve(),
            )
            self.assertEqual(FakeEngine.full_pipeline_calls, 0)
            self.assertEqual(FakeEngine.box_pipeline_calls, 3)
            self.assertEqual(
                FakeEngine.route_manifests,
                [fixture["manager"].get_cascade_routes()] * 3,
            )
            self.assertEqual(
                [
                    (root.resolve(), checkpoint.resolve())
                    for root, checkpoint in FakeEngine.loaded_paths
                ],
                [
                    (
                        fixture["managed_model_root"].resolve(),
                        fixture["checkpoint_path"].resolve(),
                    )
                ],
            )
            self.assertEqual(
                FakeEngine.loaded_payloads,
                [
                    (
                        b"managed-locator-checkpoint",
                        True,
                        expected_scope,
                    )
                ],
            )
            engine_instance = FakeEngine.instances[0]
            self.assertEqual(
                engine_instance.locator_scope,
                expected_scope,
            )
            self.assertEqual(
                Path(engine_instance.cascade_manager.expert_dir),
                fixture["managed_model_root"].resolve() / "experts",
            )
            self.assertEqual(
                engine_instance.cascade_manager.project_manager.project_data[
                    "project_id"
                ],
                fixture["manager"].project_data["project_id"],
            )
            self.assertEqual(
                Path(
                    engine_instance.cascade_manager.project_manager.current_database_path
                ).resolve(),
                Path(fixture["manager"].current_database_path).resolve(),
            )
            engine_instance.cascade_manager.load_routes.assert_not_called()

    def test_real_engine_box_only_runs_parent_child_route_without_sam(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            locator = TraitRegressor(in_channels=3, out_channels=1)
            for parameter in locator.parameters():
                torch.nn.init.constant_(parameter, 0.0)
            with torch.no_grad():
                locator.outc.conv.bias.fill_(1.0)
            checkpoint_buffer = io.BytesIO()
            torch.save(
                {
                    "schema_version": LOCATOR_CHECKPOINT_SCHEMA_VERSION,
                    "state_dict": locator.state_dict(),
                    "meta": {
                        "architecture_id": LOCATOR_ARCHITECTURE_ID,
                        "locator_size": [64, 64],
                        "locator_resolution": 64,
                        "num_classes": 1,
                        "locator_scope": ["Head"],
                        "loss_config": {
                            "locator": {"heatmap": 1.0, "wh": 0.5}
                        },
                    },
                },
                checkpoint_buffer,
            )
            fixture = self._managed_locator_fixture(
                root,
                checkpoint_bytes=checkpoint_buffer.getvalue(),
                image_count=2,
            )
            del locator

            manager = fixture["manager"]
            manager.project_data["taxonomy"] = ["Head", "Eye"]
            manager.set_locator_scope(["Head"], save=False)
            manager._mark_sqlite_project_dirty()
            for image_path in manager.project_data["images"]:
                image_key = manager._image_data_key(image_path)
                manager.project_data["labels"][image_key] = (
                    manager._default_label_entry()
                )
                manager._mark_sqlite_image_dirty(image_key)
            manager.save_project()

            blink_model = HeatmapBlinkNet(base_channels=4)
            for parameter in blink_model.parameters():
                torch.nn.init.constant_(parameter, 0.0)
            blink_run_id = "blink-box-only-integration-001"
            blink_staging = root / "blink-staging"
            staged_child_dir = blink_staging / "Eye"
            staged_child_dir.mkdir(parents=True)
            staged_checkpoint = staged_child_dir / "eye_heatmap.pth"
            torch.save(
                {
                    "state_dict": blink_model.state_dict(),
                    "meta": {
                        "kind": "blink_heatmap_expert",
                        "parent_part": "Head",
                        "child_part": "Eye",
                        "part_name": "Eye",
                        "input_size": [64, 64],
                        "preprocessing": build_blink_preprocessing_contract(),
                        "base_channels": 4,
                    },
                },
                staged_checkpoint,
            )
            staged_manifest = staged_child_dir / "eye_heatmap.manifest.json"
            staged_manifest.write_text(
                json.dumps(
                    build_blink_expert_manifest(
                        str(staged_checkpoint),
                        expert_backend=ROUTE_BACKEND_HEATMAP_BLINK,
                        parent_part="Head",
                        child_part="Eye",
                        input_size=(64, 64),
                    )
                ),
                encoding="utf-8",
            )
            blink_publisher = auto_annotate_project.TrainingWeightPublisher(
                fixture["managed_model_root"] / "experts"
            )
            blink_publication = blink_publisher.publish_pending(
                blink_run_id,
                blink_staging,
                [
                    {
                        "artifact_id": "blink_checkpoint",
                        "role": "output_weights",
                        "relative_path": "Eye/eye_heatmap.pth",
                        "media_type": "application/octet-stream",
                    },
                    {
                        "artifact_id": "blink_model_manifest",
                        "role": "model_manifest",
                        "relative_path": "Eye/eye_heatmap.manifest.json",
                        "media_type": "application/json",
                    },
                ],
            )
            active_blink = blink_publisher.activate(
                blink_run_id,
                {
                    "schema_version": "taxamask_training_run_v1",
                    "run_id": blink_run_id,
                    "status": "succeeded",
                    "artifacts": blink_publication["artifacts"],
                },
            )
            active_artifacts = {
                item["artifact_id"]: item
                for item in active_blink["artifacts"]
            }
            active_manifest = (
                fixture["managed_model_root"]
                / "experts"
                / Path(
                    active_artifacts["blink_model_manifest"]["relative_path"]
                )
            )
            manager.set_cascade_route(
                {
                    "parent": "Head",
                    "child": "Eye",
                    "enabled": True,
                    "min_conf": 0.35,
                    "expert_id": "Eye/eye_heatmap.pth",
                    "expert_part": "Eye",
                    "expert_filename": "eye_heatmap.pth",
                    "expert_backend": ROUTE_BACKEND_HEATMAP_BLINK,
                    "expert_manifest": str(active_manifest),
                    "input_size": [64, 64],
                },
                save=True,
            )

            report_path = root / "real-box-only-report.json"
            argv = [
                "auto_annotate_project.py",
                "--project",
                str(fixture["project_path"]),
                "--out",
                str(fixture["project_path"]),
                "--run-engine",
                "--training-run-id",
                fixture["run_id"],
                "--runs-root",
                str(fixture["runs_root"]),
                "--managed-model-root",
                str(fixture["managed_model_root"]),
                "--draft-boxes-only",
                "--confidence",
                "0.35",
                "--device",
                "cpu",
                "--report",
                str(report_path),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch(
                "tools.agentic.auto_annotate_project.read_verified_initial_weight",
                side_effect=AssertionError(
                    "box-only must not inspect base SAM registration"
                ),
            ), mock.patch(
                "AntSleap.core.engine.TrainableSAM",
                side_effect=AssertionError("box-only must not construct SAM"),
            ), mock.patch.object(
                AntEngine,
                "ensure_parts_model_loaded",
                side_effect=AssertionError("box-only must not load SAM parts"),
            ), mock.patch.object(
                AntEngine,
                "load_sam_decoder",
                side_effect=AssertionError("box-only must not load SAM decoder"),
            ), mock.patch.object(
                AntEngine,
                "_run_sam_polygon",
                side_effect=AssertionError("box-only must not invoke SAM"),
            ):
                self.assertEqual(auto_annotate_project.main(), 0)

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["engine_prediction_mode"], "locator_boxes")
            self.assertEqual(report["saved_label_count"], 4)
            self.assertEqual(report["rejected_count"], 0)
            self.assertEqual(
                report["checkpoint_evidence"]["checkpoint_schema_version"],
                LOCATOR_CHECKPOINT_SCHEMA_VERSION,
            )
            self.assertEqual(
                report["checkpoint_evidence"]["locator_scope"],
                ["Head"],
            )
            self.assertEqual(len(report["results"]), 2)
            for result in report["results"]:
                self.assertEqual(result["predicted_parts"], ["Eye", "Head"])
                self.assertEqual(set(result["prediction_scores"]), {"Head", "Eye"})
                route_meta = result["prediction_meta"]
                self.assertTrue(route_meta["cascade_requested"])
                self.assertTrue(route_meta["cascade_routes_ready"])
                self.assertEqual(route_meta["cascade_applied_count"], 1)
                self.assertEqual(len(route_meta["cascade_attempted_routes"]), 1)
                self.assertEqual(len(route_meta["cascade_applied_routes"]), 1)
                self.assertIn(
                    "Head->Eye",
                    route_meta["cascade_applied_routes"][0],
                )
                self.assertEqual(
                    route_meta["cascade_route_backends"],
                    [f"Head->Eye:{ROUTE_BACKEND_HEATMAP_BLINK}"],
                )
                self.assertEqual(
                    route_meta["cascade_route_manifests"],
                    [str(active_manifest)],
                )

            reloaded = ProjectManager()
            reloaded.load_project(str(fixture["project_path"]))
            for image_path in reloaded.project_data["images"]:
                image_key = reloaded._image_data_key(image_path)
                entry = reloaded.project_data["labels"][image_key]
                self.assertEqual(entry.get("parts", {}), {})
                self.assertEqual(set(entry["auto_boxes"]), {"Head", "Eye"})
                head_box = entry["auto_boxes"]["Head"]
                eye_box = entry["auto_boxes"]["Eye"]
                self.assertLessEqual(head_box[0], eye_box[0])
                self.assertLessEqual(head_box[1], eye_box[1])
                self.assertGreaterEqual(head_box[2], eye_box[2])
                self.assertGreaterEqual(head_box[3], eye_box[3])
                self.assertEqual(
                    entry["auto_box_meta"]["Head"]["review_status"],
                    "draft",
                )
                self.assertEqual(
                    entry["auto_box_meta"]["Eye"]["review_status"],
                    "draft",
                )

    def test_sqlite_project_rejects_nonexistent_output_manifest_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._managed_locator_fixture(Path(tmp))
            report_path = Path(tmp) / "report.json"
            output_path = Path(tmp) / "not-created.sqlite_manifest.json"
            argv = [
                "auto_annotate_project.py",
                "--project",
                str(fixture["project_path"]),
                "--out",
                str(output_path),
                "--predictions",
                str(Path(tmp) / "unused-predictions.json"),
                "--report",
                str(report_path),
            ]
            with mock.patch.object(sys, "argv", argv):
                with self.assertRaisesRegex(
                    ValueError, "sqlite_output_must_match_input_manifest"
                ):
                    auto_annotate_project.main()
            self.assertFalse(output_path.exists())
            self.assertFalse(report_path.exists())

    def test_run_engine_only_new_predicts_images_with_partially_existing_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._managed_locator_fixture(Path(tmp))

            class FakeEngine:
                predicted_paths = []

                def __init__(
                    self,
                    num_classes,
                    device,
                    weights_dir=None,
                    locator_scope=None,
                ):
                    del num_classes, device, weights_dir
                    self.locator_scope = list(locator_scope or [])
                    self.locator = None
                    self.loaded_locator_timestamp = None
                    self.loaded_locator_schema_version = ""
                    self.loaded_locator_scope = []
                    self.cascade_manager = mock.Mock()

                def load_locator(
                    self,
                    timestamp,
                    *,
                    checkpoint_path=None,
                    checkpoint_payload=None,
                    require_complete=False,
                    expected_locator_scope=None,
                ):
                    del checkpoint_path, checkpoint_payload, require_complete
                    self.locator = object()
                    self.loaded_locator_timestamp = timestamp
                    self.loaded_locator_schema_version = (
                        LOCATOR_CHECKPOINT_SCHEMA_VERSION
                    )
                    self.loaded_locator_scope = list(expected_locator_scope or [])

                def predict_box_pipeline(self, image_path, *_args, **_kwargs):
                    type(self).predicted_paths.append(image_path)
                    return {"polygons": {}, "auto_boxes": {}}

            with mock.patch("AntSleap.core.engine.AntEngine", FakeEngine):
                records, _evidence = auto_annotate_project._run_engine_predictions(
                    fixture["manager"],
                    0.35,
                    training_run_id=fixture["run_id"],
                    runs_root=str(fixture["runs_root"]),
                    managed_model_root=str(fixture["managed_model_root"]),
                    only_new=True,
                    draft_boxes_only=True,
                    device="cpu",
                )

            expected = list(fixture["manager"].project_data["images"])
            self.assertEqual([item["image_path"] for item in records], expected)
            self.assertEqual(FakeEngine.predicted_paths, expected)

    def test_full_pipeline_uses_registry_verified_base_sam(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self._managed_locator_fixture(
                root,
                decoder_bytes=b"managed decoder fixture",
                registered_base_sam_bytes=b"registered base SAM fixture",
            )
            base_sam = fixture["base_sam_path"]

            class FakeEngine:
                observed_base_sam = []

                def __init__(
                    self,
                    num_classes,
                    device,
                    weights_dir=None,
                    locator_scope=None,
                ):
                    self.weights_dir = str(Path(weights_dir).resolve())
                    self.base_sam_path = str(Path(self.weights_dir) / "sam_b.pt")
                    self.locator_scope = list(locator_scope or [])
                    self.locator = None
                    self.loaded_locator_timestamp = None
                    self.loaded_locator_schema_version = ""
                    self.loaded_locator_scope = []
                    self.parts_model = None
                    self.loaded_sam_decoder_reference = ""
                    self.cascade_manager = mock.Mock()

                def configure_verified_base_sam(
                    self,
                    checkpoint_bytes,
                    *,
                    reference="",
                    fingerprint=None,
                ):
                    self.base_sam_path = reference
                    self.base_sam_checkpoint_bytes = bytes(checkpoint_bytes)
                    self.base_sam_fingerprint = dict(fingerprint or {})

                def load_sam_decoder(
                    self,
                    timestamp,
                    *,
                    checkpoint_path=None,
                    checkpoint_bytes=None,
                    checkpoint_payload=None,
                    expected_base_sam_fingerprint=None,
                    require_base_sam_match=False,
                ):
                    del timestamp, checkpoint_bytes, checkpoint_payload
                    self.expected_base_sam_fingerprint = dict(
                        expected_base_sam_fingerprint or {}
                    )
                    self.require_base_sam_match = bool(require_base_sam_match)
                    self.parts_model = object()
                    self.loaded_sam_decoder_reference = str(
                        Path(checkpoint_path).resolve().relative_to(
                            Path(self.weights_dir).resolve()
                        )
                    ).replace("\\", "/")

                def load_locator(
                    self,
                    timestamp,
                    *,
                    checkpoint_path=None,
                    checkpoint_payload=None,
                    require_complete=False,
                    expected_locator_scope=None,
                ):
                    self.locator = object()
                    self.loaded_locator_timestamp = timestamp
                    self.loaded_locator_schema_version = (
                        "taxamask_locator_checkpoint_v2"
                    )
                    self.loaded_locator_scope = list(expected_locator_scope or [])

                def predict_full_pipeline(
                    self,
                    image_path,
                    taxonomy,
                    locator_scope,
                    conf_thresh,
                    project_route_manifest=None,
                ):
                    type(self).observed_base_sam.append(self.base_sam_path)
                    return {"polygons": {}, "auto_boxes": {}}

            with mock.patch("AntSleap.core.engine.AntEngine", FakeEngine):
                records, evidence = auto_annotate_project._run_engine_predictions(
                    fixture["manager"],
                    0.35,
                    training_run_id=fixture["run_id"],
                    runs_root=str(fixture["runs_root"]),
                    managed_model_root=str(fixture["managed_model_root"]),
                    base_sam_path=str(base_sam),
                    draft_boxes_only=False,
                    device="cpu",
                )

            self.assertEqual(len(records), 3)
            self.assertEqual(
                [
                    Path(path).resolve()
                    for path in FakeEngine.observed_base_sam
                ],
                [base_sam.resolve()] * 3,
            )
            self.assertEqual(
                evidence["base_sam_evidence"]["status"],
                "verified",
            )
            self.assertEqual(
                evidence["base_sam_evidence"]["fingerprint"]["digest"],
                hashlib.sha256(base_sam.read_bytes()).hexdigest(),
            )
            self.assertTrue(
                evidence["base_sam_evidence"]["loaded_from_verified_bytes"]
            )
            self.assertTrue(evidence["sam_decoder_evidence"]["loaded"])
            self.assertEqual(
                evidence["publication"]["run_id"], fixture["run_id"]
            )
            self.assertEqual(
                evidence["training_run"]["run_id"], fixture["run_id"]
            )
            self.assertEqual(
                evidence["training_base_sam"]["fingerprint"]["digest"],
                evidence["base_sam_evidence"]["fingerprint"]["digest"],
            )

    def test_full_pipeline_rejects_base_sam_from_different_project_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self._managed_locator_fixture(
                root,
                decoder_bytes=b"managed decoder fixture",
                registered_base_sam_bytes=b"training base SAM fixture",
            )
            replacement = root / "replacement" / "sam_b.pt"
            replacement.parent.mkdir()
            replacement.write_bytes(b"different registered base SAM")
            register_initial_weight_version(
                fixture["manager"],
                [{"slot": "parent.sam_base", "path": replacement}],
                note="Register a different base after the historical training run.",
            )

            class FakeEngine:
                configure_calls = 0
                locator_load_calls = 0

                def __init__(self, **_kwargs):
                    self.cascade_manager = mock.Mock()

                def configure_verified_base_sam(self, *_args, **_kwargs):
                    type(self).configure_calls += 1

                def load_locator(self, *_args, **_kwargs):
                    type(self).locator_load_calls += 1

            with mock.patch("AntSleap.core.engine.AntEngine", FakeEngine):
                with self.assertRaisesRegex(
                    ValueError,
                    "base_sam_training_run_mismatch",
                ):
                    auto_annotate_project._run_engine_predictions(
                        fixture["manager"],
                        0.35,
                        training_run_id=fixture["run_id"],
                        runs_root=str(fixture["runs_root"]),
                        managed_model_root=str(fixture["managed_model_root"]),
                        base_sam_path=str(replacement),
                        draft_boxes_only=False,
                        device="cpu",
                    )

            self.assertEqual(FakeEngine.configure_calls, 0)
            self.assertEqual(FakeEngine.locator_load_calls, 0)

    def test_full_pipeline_rejects_unregistered_base_sam_before_locator_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self._managed_locator_fixture(
                root,
                decoder_bytes=b"managed decoder fixture",
                registered_base_sam_bytes=b"training base SAM fixture",
            )
            unregistered_sam = root / "unregistered" / "sam_b.pt"
            unregistered_sam.parent.mkdir()
            unregistered_sam.write_bytes(b"unregistered base SAM fixture")

            class FakeEngine:
                load_calls = 0

                def __init__(
                    self,
                    num_classes,
                    device,
                    weights_dir=None,
                    locator_scope=None,
                ):
                    self.weights_dir = str(Path(weights_dir).resolve())
                    self.locator_scope = list(locator_scope or [])
                    self.cascade_manager = mock.Mock()

                def load_locator(self, *args, **kwargs):
                    type(self).load_calls += 1

            with mock.patch("AntSleap.core.engine.AntEngine", FakeEngine):
                with self.assertRaisesRegex(
                    ValueError, "base_sam_registry_verification_failed"
                ):
                    auto_annotate_project._run_engine_predictions(
                        fixture["manager"],
                        0.35,
                        training_run_id=fixture["run_id"],
                        runs_root=str(fixture["runs_root"]),
                        managed_model_root=str(fixture["managed_model_root"]),
                        base_sam_path=str(unregistered_sam),
                        draft_boxes_only=False,
                        device="cpu",
                    )
            self.assertEqual(FakeEngine.load_calls, 0)

    def test_full_pipeline_missing_decoder_writes_traceable_failure_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self._managed_locator_fixture(
                root,
                registered_base_sam_bytes=b"training base SAM fixture",
            )
            report_path = root / "failed-full-pipeline-report.json"
            argv = [
                "auto_annotate_project.py",
                "--project",
                str(fixture["project_path"]),
                "--out",
                str(fixture["project_path"]),
                "--run-engine",
                "--training-run-id",
                fixture["run_id"],
                "--runs-root",
                str(fixture["runs_root"]),
                "--managed-model-root",
                str(fixture["managed_model_root"]),
                "--base-sam-path",
                str(root / "not-reached-sam_b.pt"),
                "--report",
                str(report_path),
            ]

            with mock.patch.object(sys, "argv", argv):
                with self.assertRaisesRegex(
                    ValueError,
                    "sam_decoder_checkpoint_artifact_invalid",
                ):
                    auto_annotate_project.main()

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["failure_stage"], "engine_prediction")
            self.assertEqual(
                report["checkpoint_evidence"]["run_id"],
                fixture["run_id"],
            )
            self.assertEqual(
                report["checkpoint_evidence"]["project_ref"]["project_id"],
                fixture["manager"].project_data["project_id"],
            )
            self.assertEqual(report["saved_label_count"], 0)

    def test_run_engine_fails_if_checkpoint_disappears_after_publication_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._managed_locator_fixture(Path(tmp))
            original_list_active = (
                auto_annotate_project.TrainingWeightPublisher.list_active
            )

            def remove_after_list(publisher, resolver):
                result = original_list_active(publisher, resolver)
                fixture["checkpoint_path"].unlink()
                return result

            with mock.patch.object(
                auto_annotate_project.TrainingWeightPublisher,
                "list_active",
                new=remove_after_list,
            ):
                with self.assertRaisesRegex(ValueError, "locator_checkpoint_missing"):
                    auto_annotate_project._managed_locator_checkpoint(
                        fixture["manager"],
                        training_run_id=fixture["run_id"],
                        runs_root=str(fixture["runs_root"]),
                        managed_model_root=str(fixture["managed_model_root"]),
                    )

    def test_run_engine_fails_if_checkpoint_changes_after_publication_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._managed_locator_fixture(Path(tmp))
            original_list_active = (
                auto_annotate_project.TrainingWeightPublisher.list_active
            )

            def tamper_after_list(publisher, resolver):
                result = original_list_active(publisher, resolver)
                fixture["checkpoint_path"].write_bytes(b"tampered-checkpoint")
                return result

            with mock.patch.object(
                auto_annotate_project.TrainingWeightPublisher,
                "list_active",
                new=tamper_after_list,
            ):
                with self.assertRaisesRegex(
                    ValueError, "locator_checkpoint_fingerprint_mismatch"
                ):
                    auto_annotate_project._managed_locator_checkpoint(
                        fixture["manager"],
                        training_run_id=fixture["run_id"],
                        runs_root=str(fixture["runs_root"]),
                        managed_model_root=str(fixture["managed_model_root"]),
                    )

    def test_run_engine_rejects_training_run_from_another_project_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._managed_locator_fixture(Path(tmp))
            fixture["manager"].project_data["project_id"] = "another-project"
            with self.assertRaisesRegex(
                ValueError, "training_run_project_identity_mismatch"
            ):
                auto_annotate_project._managed_locator_checkpoint(
                    fixture["manager"],
                    training_run_id=fixture["run_id"],
                    runs_root=str(fixture["runs_root"]),
                    managed_model_root=str(fixture["managed_model_root"]),
                )

    def test_run_engine_rejects_succeeded_but_inactive_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._managed_locator_fixture(Path(tmp), activate=False)
            with self.assertRaisesRegex(ValueError, "locator_publication_not_active"):
                auto_annotate_project._managed_locator_checkpoint(
                    fixture["manager"],
                    training_run_id=fixture["run_id"],
                    runs_root=str(fixture["runs_root"]),
                    managed_model_root=str(fixture["managed_model_root"]),
                )

    def test_run_engine_rejects_wrong_runs_root_even_with_shared_project_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._managed_locator_fixture(Path(tmp))
            with self.assertRaisesRegex(ValueError, "training_run_directory_missing"):
                auto_annotate_project._managed_locator_checkpoint(
                    fixture["manager"],
                    training_run_id=fixture["run_id"],
                    runs_root=str(Path(tmp) / "wrong-runs-root"),
                    managed_model_root=str(fixture["managed_model_root"]),
                )

    def test_run_engine_rejects_forged_same_name_directory_in_wrong_runs_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._managed_locator_fixture(Path(tmp))
            wrong_root = Path(tmp) / "wrong-runs-root"
            forged_run = wrong_root / fixture["run_id"]
            forged_run.mkdir(parents=True)
            (forged_run / "training_run.json").write_text(
                json.dumps(
                    {
                        "schema_version": "taxamask_training_run_v1",
                        "run_id": fixture["run_id"],
                        "status": "succeeded",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError, "training_run_projection_mismatch"
            ):
                auto_annotate_project._managed_locator_checkpoint(
                    fixture["manager"],
                    training_run_id=fixture["run_id"],
                    runs_root=str(wrong_root),
                    managed_model_root=str(fixture["managed_model_root"]),
                )

    def test_run_engine_requires_all_managed_checkpoint_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(
                        PROJECT_ROOT
                        / "tools"
                        / "agentic"
                        / "auto_annotate_project.py"
                    ),
                    "--project",
                    str(Path(tmp) / "missing-project.json"),
                    "--out",
                    str(Path(tmp) / "output.json"),
                    "--run-engine",
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("--training-run-id", result.stderr)
            self.assertIn("--runs-root", result.stderr)
            self.assertIn("--managed-model-root", result.stderr)


if __name__ == "__main__":
    unittest.main()
