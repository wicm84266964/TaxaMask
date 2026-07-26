# pyright: reportMissingImports=false

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "tools" / "agentic" / "train_project.py"
SPEC = importlib.util.spec_from_file_location("taxamask_agentic_train_project", SCRIPT_PATH)
TRAIN_PROJECT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(TRAIN_PROJECT)


class _FakeProjectManager:
    def __init__(self, project_data):
        self.project_data = project_data
        self._image_uids = dict(project_data.get("image_uids", {}))
        for index, image_path in enumerate(project_data.get("images", []), start=1):
            self._image_uids.setdefault(image_path, f"image_fixture_{index:06d}")

    def load_project(self, _path):
        return self.project_data

    def get_locator_scope(self):
        return list(self.project_data.get("locator_scope", []))

    def get_active_model_profile(self):
        return dict(self.project_data.get("active_model_profile", {}))

    def get_image_uid(self, image_path):
        return self._image_uids.get(str(image_path))


class AgenticTrainProjectSafetyTests(unittest.TestCase):
    def _make_image(self, root, name):
        image_path = Path(root) / name
        Image.new("RGB", (64, 64), color=(180, 180, 180)).save(image_path)
        return str(image_path)

    def _make_registered_project(self, root, count, *, loss_weights=None):
        project_dir = Path(root) / "project"
        project_dir.mkdir()
        manager = TRAIN_PROJECT.ProjectManager()
        manager.create_project("ants", project_dir)
        manager.location_registry_database_path = Path(root) / "locations.sqlite"
        manager.project_data["taxonomy"] = ["Head"]
        manager.project_data["locator_scope"] = ["Head"]
        profiles = manager.get_model_profiles()
        active_id = profiles["active_profile_id"]
        for profile in profiles["profiles"]:
            if profile["profile_id"] == active_id:
                profile["parent_backend"]["locator_scope"] = ["Head"]
                if loss_weights is not None:
                    profile["parent_backend"]["loss_weights"] = dict(loss_weights)
        manager.set_model_profiles(profiles)
        images_dir = project_dir / "images"
        images_dir.mkdir()
        image_paths = [
            self._make_image(images_dir, f"reviewed_{index}.png")
            for index in range(count)
        ]
        manager.add_images(image_paths, save=True)
        for image_path in image_paths:
            manager.update_label(
                image_path,
                "Head",
                [[4, 4], [40, 4], [20, 36]],
                box=[4, 4, 40, 36],
                save=True,
            )
        manager.initialize_integrity_baseline()
        return manager, image_paths

    def test_auto_only_sample_is_ineligible_for_locator_and_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = self._make_image(tmp, "auto_only.png")
            manager = _FakeProjectManager(
                {
                    "images": [image_path],
                    "labels": {
                        image_path: {
                            "parts": {"Head": [[4, 4], [40, 4], [20, 36]]},
                            "boxes": {"Head": [4, 4, 40, 36]},
                            "descriptions": {"Head": "Auto-Annotated"},
                        }
                    },
                }
            )

            preflight, locator_records, parts_records = TRAIN_PROJECT._build_reviewed_training_inputs(
                manager,
                ["Head"],
                ["Head"],
                0,
            )

            self.assertEqual(locator_records, [])
            self.assertEqual(parts_records, [])
            self.assertEqual(preflight["excluded_auto_draft_images"], [image_path])
            exclusion_counts = TRAIN_PROJECT._preflight_exclusion_counts(preflight)
            self.assertEqual(exclusion_counts["auto_draft_only_images"], 1)
            self.assertEqual(exclusion_counts["total_excluded_images"], 1)

    def test_mixed_sample_keeps_only_reviewed_parts_for_each_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = self._make_image(tmp, "mixed.png")
            manager = _FakeProjectManager(
                {
                    "images": [image_path],
                    "labels": {
                        image_path: {
                            "parts": {
                                "Head": [[4, 4], [40, 4], [20, 36]],
                                "Mandible": [[8, 8], [32, 8], [20, 28]],
                            },
                            "boxes": {
                                "Head": [4, 4, 40, 36],
                                "Mandible": [8, 8, 32, 28],
                            },
                            "descriptions": {"Mandible": "Auto-Annotated"},
                        }
                    },
                }
            )

            _preflight, locator_records, parts_records = TRAIN_PROJECT._build_reviewed_training_inputs(
                manager,
                ["Head", "Mandible"],
                ["Head", "Mandible"],
                0,
            )

            self.assertEqual(set(locator_records[0][1]["parts"]), {"Head"})
            self.assertEqual(set(parts_records[0][1]["parts"]), {"Head"})
            self.assertEqual(set(locator_records[0][1]["boxes"]), {"Head"})
            self.assertEqual(set(parts_records[0][1]["boxes"]), {"Head"})

    def test_fewer_than_two_reviewed_samples_never_constructs_engine_or_saves_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, _image_paths = self._make_registered_project(root, 1)
            report_path = root / "report.json"
            argv = [
                str(SCRIPT_PATH),
                "--project",
                str(manager.current_project_path),
                "--report",
                str(report_path),
                "--train-parts",
                "--save-weights",
            ]

            with patch.object(
                TRAIN_PROJECT,
                "AntEngine",
                side_effect=AssertionError("training engine must not start"),
            ), patch.object(
                TRAIN_PROJECT, "TRAINING_RUNS_ROOT", str(root / "training_runs")
            ), patch.object(sys, "argv", argv):
                exit_code = TRAIN_PROJECT.main()

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["error"], "not_enough_reviewed_locator_samples")
            self.assertEqual(report["saved_weights_timestamp"], "")
            self.assertEqual(report["locator_selected_sample_count"], 1)
            self.assertEqual(report["parts_selected_sample_count"], 1)

    def test_headless_parts_training_requires_registered_base_sam(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, _image_paths = self._make_registered_project(root, 2)
            report_path = root / "report.json"
            argv = [
                str(SCRIPT_PATH),
                "--project",
                str(manager.current_project_path),
                "--report",
                str(report_path),
                "--train-parts",
            ]

            with patch.object(
                TRAIN_PROJECT,
                "AntEngine",
                side_effect=AssertionError("training engine must not start"),
            ), patch.object(
                TRAIN_PROJECT, "TRAINING_RUNS_ROOT", str(root / "training_runs")
            ), patch.object(sys, "argv", argv):
                exit_code = TRAIN_PROJECT.main()

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(
                report["error"],
                "headless_base_sam_not_registered_use_gui_training_once",
            )

    def test_headless_training_passes_active_profile_loss_weights_and_reports_effective_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_path = root / "report.json"
            custom_weights = {"heatmap": 1.4, "wh": 0.65}
            manager, _image_paths = self._make_registered_project(
                root, 2, loss_weights=custom_weights
            )
            captured_kwargs = {}

            class FakeEngine:
                def __init__(self, **kwargs):
                    captured_kwargs.update(kwargs)
                    self.device = "cpu"
                    self.locator = object()
                    self.opt_loc = object()
                    self.loss_config_snapshot = {"locator": dict(kwargs.get("locator_loss_weights") or {})}

                def ensure_locator_loaded(self):
                    return self.locator

                def train_epoch(self, *_args, **_kwargs):
                    return 0.25

                def validate_epoch(self, *_args, **_kwargs):
                    return {"loss": 0.2, "pixel_error": 1.0}

            argv = [
                str(SCRIPT_PATH),
                "--project",
                str(manager.current_project_path),
                "--report",
                str(report_path),
            ]
            with patch.object(
                TRAIN_PROJECT,
                "AntEngine",
                FakeEngine,
            ), patch.object(
                TRAIN_PROJECT, "TRAINING_RUNS_ROOT", str(root / "training_runs")
            ), patch.object(sys, "argv", argv):
                exit_code = TRAIN_PROJECT.main()

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0, report)
            self.assertEqual(captured_kwargs["locator_loss_weights"], custom_weights)
            self.assertEqual(report["loss_config"], {"locator": custom_weights})
            run_records = list((root / "training_runs").glob("*/training_run.json"))
            self.assertEqual(len(run_records), 1)
            run_record = json.loads(run_records[0].read_text(encoding="utf-8"))
            self.assertEqual(run_record["status"], "succeeded")
            self.assertFalse(run_record["effective_config"]["persist_weights"])
            self.assertNotIn(str(root.resolve()), run_records[0].read_text(encoding="utf-8"))
            with closing(sqlite3.connect(manager.current_database_path)) as connection:
                row = connection.execute(
                    "SELECT status FROM training_runs WHERE run_id = ?",
                    (run_record["run_id"],),
                ).fetchone()
            self.assertEqual(row, ("succeeded",))

    def test_headless_training_uses_registered_truth_not_mutated_live_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, image_paths = self._make_registered_project(root, 2)
            original_polygon = [[4, 4], [40, 4], [20, 36]]
            manager.project_data["labels"][image_paths[0]]["parts"]["Head"] = [
                [1, 1],
                [2, 1],
                [1, 2],
            ]
            report_path = root / "report.json"
            captured_records = []

            class CapturingDataset:
                def __init__(self, records, _taxonomy, **_kwargs):
                    captured_records.extend(records)

                def __len__(self):
                    return 1

                def __getitem__(self, _index):
                    raise AssertionError("fake engine must not consume tensors")

            class FakeEngine:
                def __init__(self, **kwargs):
                    self.device = "cpu"
                    self.locator = object()
                    self.opt_loc = object()
                    self.loss_config_snapshot = {
                        "locator": dict(kwargs.get("locator_loss_weights") or {})
                    }

                def ensure_locator_loaded(self):
                    return self.locator

                def train_epoch(self, *_args, **_kwargs):
                    return 0.1

                def validate_epoch(self, *_args, **_kwargs):
                    return {"loss": 0.1, "pixel_error": 0.0}

            argv = [
                str(SCRIPT_PATH),
                "--project",
                str(manager.current_project_path),
                "--report",
                str(report_path),
            ]
            with patch.object(manager, "load_project", return_value=manager.project_data), patch.object(
                TRAIN_PROJECT, "ProjectManager", return_value=manager
            ), patch.object(TRAIN_PROJECT, "TwoStageDataset", CapturingDataset), patch.object(
                TRAIN_PROJECT, "AntEngine", FakeEngine
            ), patch.object(
                TRAIN_PROJECT, "TRAINING_RUNS_ROOT", str(root / "training_runs")
            ), patch.object(sys, "argv", argv):
                exit_code = TRAIN_PROJECT.main()

            self.assertEqual(exit_code, 0)
            polygons = [
                record[1]["parts"]["Head"]
                for record in captured_records
                if "Head" in record[1].get("parts", {})
            ]
            self.assertTrue(polygons)
            self.assertTrue(all(polygon == original_polygon for polygon in polygons))

    def test_registry_source_mismatch_stops_before_engine_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, image_paths = self._make_registered_project(root, 2)
            Image.new("RGB", (64, 64), color=(1, 2, 3)).save(image_paths[0])
            report_path = root / "report.json"
            argv = [
                str(SCRIPT_PATH),
                "--project",
                str(manager.current_project_path),
                "--report",
                str(report_path),
            ]
            with patch.object(
                TRAIN_PROJECT,
                "AntEngine",
                side_effect=AssertionError("training engine must not start"),
            ), patch.object(
                TRAIN_PROJECT, "TRAINING_RUNS_ROOT", str(root / "training_runs")
            ), patch.object(sys, "argv", argv):
                exit_code = TRAIN_PROJECT.main()

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["error"], "source_digest_mismatch")
            with closing(sqlite3.connect(manager.current_database_path)) as connection:
                row = connection.execute(
                    "SELECT status FROM training_runs WHERE run_id = ?",
                    (report["training_run_id"],),
                ).fetchone()
            self.assertEqual(row, ("failed",))

    def test_uninitialized_registry_stops_before_engine_and_records_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "project"
            project_dir.mkdir()
            manager = TRAIN_PROJECT.ProjectManager()
            manager.create_project("ants", project_dir)
            report_path = root / "report.json"
            argv = [
                str(SCRIPT_PATH),
                "--project",
                str(manager.current_project_path),
                "--report",
                str(report_path),
            ]
            with patch.object(
                TRAIN_PROJECT,
                "AntEngine",
                side_effect=AssertionError("training engine must not start"),
            ), patch.object(
                TRAIN_PROJECT, "TRAINING_RUNS_ROOT", str(root / "training_runs")
            ), patch.object(sys, "argv", argv):
                exit_code = TRAIN_PROJECT.main()

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["error"], "integrity_baseline_missing")
            with closing(sqlite3.connect(manager.current_database_path)) as connection:
                row = connection.execute(
                    "SELECT status FROM training_runs WHERE run_id = ?",
                    (report["training_run_id"],),
                ).fetchone()
            self.assertEqual(row, ("failed",))

    def test_locator_only_weights_publish_as_one_active_run_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_path = root / "report.json"
            managed_model_root = root / "managed_models"
            manager, _image_paths = self._make_registered_project(root, 2)
            save_calls = []

            class FakeEngine:
                def __init__(self, **kwargs):
                    self.device = "cpu"
                    self.locator = object()
                    self.opt_loc = object()
                    self.loss_config_snapshot = {
                        "locator": dict(kwargs.get("locator_loss_weights") or {})
                    }

                def ensure_locator_loaded(self):
                    return self.locator

                def train_epoch(self, *_args, **_kwargs):
                    return 0.25

                def validate_epoch(self, *_args, **_kwargs):
                    return {"loss": 0.2, "pixel_error": 1.0}

                def save_weights(self, **kwargs):
                    save_calls.append(dict(kwargs))
                    output_dir = Path(kwargs["output_dir"])
                    artifact_key = kwargs["artifact_key"]
                    (output_dir / f"locator_{artifact_key}.pth").write_bytes(
                        b"locator checkpoint"
                    )
                    if kwargs["save_segmenter"]:
                        (output_dir / f"sam_decoder_lora_{artifact_key}.pth").write_bytes(
                            b"segmenter checkpoint"
                        )
                    return artifact_key

            argv = [
                str(SCRIPT_PATH),
                "--project",
                str(manager.current_project_path),
                "--report",
                str(report_path),
                "--save-weights",
            ]
            with patch.object(TRAIN_PROJECT, "AntEngine", FakeEngine), patch.object(
                TRAIN_PROJECT, "TRAINING_RUNS_ROOT", str(root / "training_runs")
            ), patch.object(
                TRAIN_PROJECT, "MANAGED_MODEL_ROOT", str(managed_model_root)
            ), patch.object(sys, "argv", argv):
                exit_code = TRAIN_PROJECT.main()

            self.assertEqual(exit_code, 0, json.loads(report_path.read_text(encoding="utf-8")))
            self.assertEqual(len(save_calls), 1)
            self.assertFalse(save_calls[0]["save_segmenter"])
            run_path = next((root / "training_runs").glob("*/training_run.json"))
            run_record = json.loads(run_path.read_text(encoding="utf-8"))
            run_id = run_record["run_id"]
            bundle = managed_model_root / "training_runs" / run_id
            publication = json.loads(
                (bundle / "publication.json").read_text(encoding="utf-8")
            )
            self.assertEqual(publication["status"], "active")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["weight_publication_status"], "active")
            self.assertTrue((bundle / f"locator_{run_id}.pth").is_file())
            self.assertFalse(list(bundle.glob("sam_decoder_lora_*.pth")))
            output_artifacts = [
                item
                for item in run_record["artifacts"]
                if item.get("role") == "output_weights"
            ]
            self.assertEqual(len(output_artifacts), 1)
            self.assertEqual(output_artifacts[0]["path_base"], "managed_model_root")
            self.assertNotIn(str(root.resolve()), run_path.read_text(encoding="utf-8"))

    def test_unreadable_existing_run_is_not_treated_as_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "train_fixture_unreadable"
            (root / run_id).mkdir()

            class BrokenRecorder:
                runs_root = str(root)

                def load(self, _run_id):
                    raise TRAIN_PROJECT.TrainingRunRecordError("record_unreadable")

            with self.assertRaises(TRAIN_PROJECT.TrainingRunRecordError):
                TRAIN_PROJECT._load_run_record_or_none(BrokenRecorder(), run_id)

            self.assertIsNone(
                TRAIN_PROJECT._load_run_record_or_none(
                    BrokenRecorder(), "train_fixture_missing"
                )
            )

    def test_activation_os_error_keeps_training_passed_and_marks_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report = {
                "status": "passed",
                "weight_publication_status": "pending_activation",
                "weight_publication_error_code": "",
            }

            class BrokenPublisher:
                def activate(self, _run_id, _record):
                    raise OSError("disk unavailable")

            exit_code = TRAIN_PROJECT._activate_weight_publication(
                BrokenPublisher(),
                "train_fixture",
                {"status": "succeeded"},
                report,
                str(report_path),
            )

            saved = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 2)
            self.assertEqual(saved["status"], "passed")
            self.assertEqual(saved["weight_publication_status"], "pending_recovery")

    def test_activation_keyboard_interrupt_never_rewrites_training_as_cancelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report = {
                "status": "passed",
                "weight_publication_status": "pending_activation",
                "weight_publication_error_code": "",
            }

            class InterruptedPublisher:
                def activate(self, _run_id, _record):
                    raise KeyboardInterrupt()

            exit_code = TRAIN_PROJECT._activate_weight_publication(
                InterruptedPublisher(),
                "train_fixture",
                {"status": "succeeded"},
                report,
                str(report_path),
            )

            saved = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 2)
            self.assertEqual(saved["status"], "passed")
            self.assertEqual(saved["weight_publication_status"], "pending_recovery")

    def test_report_update_interrupt_after_activation_stays_training_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = {
                "status": "passed",
                "weight_publication_status": "pending_activation",
                "weight_publication_error_code": "",
            }

            class ActivePublisher:
                def activate(self, _run_id, _record):
                    return {"status": "active"}

            with patch.object(
                TRAIN_PROJECT, "_write_json", side_effect=KeyboardInterrupt()
            ):
                exit_code = TRAIN_PROJECT._activate_weight_publication(
                    ActivePublisher(),
                    "train_fixture",
                    {"status": "succeeded"},
                    report,
                    str(Path(tmp) / "report.json"),
                )

            self.assertEqual(exit_code, 2)
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["weight_publication_status"], "active")

    def test_nonrecoverable_activation_error_requires_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report = {
                "status": "passed",
                "weight_publication_status": "pending_activation",
                "weight_publication_error_code": "",
            }

            class InvalidPublisher:
                def activate(self, _run_id, _record):
                    raise TRAIN_PROJECT.TrainingWeightPublicationError(
                        "publication_manifest_invalid",
                        "Publication is invalid.",
                        recoverable=False,
                    )

            exit_code = TRAIN_PROJECT._activate_weight_publication(
                InvalidPublisher(),
                "train_fixture",
                {"status": "succeeded"},
                report,
                str(report_path),
            )

            saved = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 2)
            self.assertEqual(saved["status"], "passed")
            self.assertEqual(saved["weight_publication_status"], "needs_attention")

    def test_group_split_keeps_locator_and_parts_for_one_image_together(self):
        locator = [(f"image_{index}.png", {}) for index in range(4)]
        parts = [(f"image_{index}.png", {}) for index in range(1, 4)]
        image_uids = {
            path: f"image_uid_{index}"
            for index, (path, _entry) in enumerate(locator)
        }
        partitions = TRAIN_PROJECT._build_group_partition_map(
            locator,
            parts,
            42,
            include_parts=True,
            sample_uid_by_path=image_uids,
        )
        locator_partitions = {
            path: partitions[image_uids[path]] for path, _entry in locator
        }
        for path, _entry in parts:
            self.assertEqual(partitions[image_uids[path]], locator_partitions[path])
        self.assertIn("train", {partitions[image_uids[path]] for path, _entry in parts})
        self.assertIn(
            "validation", {partitions[image_uids[path]] for path, _entry in parts}
        )

    def test_group_split_is_stable_when_images_move(self):
        original = [(f"old/location/image_{index}.png", {}) for index in range(6)]
        relocated = [(f"new/location/specimen_{index}.png", {}) for index in range(6)]
        stable_uids = [f"image_uid_{index}" for index in range(6)]

        original_split = TRAIN_PROJECT._build_group_partition_map(
            original,
            [],
            20260718,
            include_parts=False,
            sample_uid_by_path={
                path: stable_uids[index]
                for index, (path, _entry) in enumerate(original)
            },
        )
        relocated_split = TRAIN_PROJECT._build_group_partition_map(
            relocated,
            [],
            20260718,
            include_parts=False,
            sample_uid_by_path={
                path: stable_uids[index]
                for index, (path, _entry) in enumerate(relocated)
            },
        )

        self.assertEqual(original_split, relocated_split)

    def test_seed_facts_cover_python_numpy_pytorch_and_cuda(self):
        expected = {
            "python": 20260718,
            "numpy": 20260718,
            "pytorch": 20260718,
            "cuda": 20260718,
        }
        self.assertEqual(TRAIN_PROJECT._seed_training(20260718), expected)
        python_value = TRAIN_PROJECT.random.random()
        numpy_value = float(TRAIN_PROJECT.np.random.random())
        torch_value = float(TRAIN_PROJECT.torch.rand(1).item())

        TRAIN_PROJECT._seed_training(20260718)

        self.assertEqual(TRAIN_PROJECT.random.random(), python_value)
        self.assertEqual(float(TRAIN_PROJECT.np.random.random()), numpy_value)
        self.assertEqual(float(TRAIN_PROJECT.torch.rand(1).item()), torch_value)

    def test_project_load_failure_is_recorded_before_engine_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_path = root / "report.json"

            class BrokenManager:
                def load_project(self, _path):
                    raise ValueError("broken_project")

            argv = [
                str(SCRIPT_PATH),
                "--project",
                str(root / "project.json"),
                "--report",
                str(report_path),
            ]
            with patch.object(TRAIN_PROJECT, "ProjectManager", BrokenManager), patch.object(
                TRAIN_PROJECT,
                "AntEngine",
                side_effect=AssertionError("training engine must not start"),
            ), patch.object(
                TRAIN_PROJECT, "TRAINING_RUNS_ROOT", str(root / "training_runs")
            ), patch.object(sys, "argv", argv):
                exit_code = TRAIN_PROJECT.main()

            self.assertEqual(exit_code, 1)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["error"], "broken_project")
            run_path = next((root / "training_runs").glob("*/training_run.json"))
            run_record = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(run_record["status"], "failed")
            self.assertEqual(run_record["error"]["stage"], "project_load")

    def test_keyboard_interrupt_is_recorded_as_cancelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_path = root / "report.json"

            class InterruptedManager:
                def load_project(self, _path):
                    raise KeyboardInterrupt()

            argv = [
                str(SCRIPT_PATH),
                "--project",
                str(root / "project.json"),
                "--report",
                str(report_path),
            ]
            with patch.object(
                TRAIN_PROJECT, "ProjectManager", InterruptedManager
            ), patch.object(
                TRAIN_PROJECT, "TRAINING_RUNS_ROOT", str(root / "training_runs")
            ), patch.object(sys, "argv", argv):
                exit_code = TRAIN_PROJECT.main()

            self.assertEqual(exit_code, 130)
            run_path = next((root / "training_runs").glob("*/training_run.json"))
            run_record = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(run_record["status"], "cancelled")
            self.assertEqual(run_record["error"]["code"], "user_cancelled")


if __name__ == "__main__":
    unittest.main()
