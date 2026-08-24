# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false, reportIndexIssue=false, reportOptionalMemberAccess=false, reportUninitializedInstanceVariable=false

import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANTSLEAP_ROOT = PROJECT_ROOT / "AntSleap"
if str(ANTSLEAP_ROOT) not in sys.path:
    sys.path.insert(0, str(ANTSLEAP_ROOT))

from PIL import Image
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog, QDialogButtonBox
import torch

import main as main_module
import AntSleap.ui.main_window_blink_context as blink_context_module
from main import BlinkEntryDialog, MainWindow
from ui.blink_lab import BlinkLabWidget, BlinkTrainingThread, BucketDeletePreviewDialog, BucketDeleteTypeConfirmDialog
from AntSleap.core.blink_training_strategy import DEFAULT_BLINK_TRAINING_STRATEGY
from AntSleap.core.blink_expert_manifest import (
    BLINK_EXPERT_BACKEND_HEATMAP,
    build_blink_expert_manifest,
)
from AntSleap.core.cascade_manager import CascadingManager
from AntSleap.core.model_profiles import DEFAULT_BLINK_OUTER_LOSS_WEIGHTS
from AntSleap.core.blink_trainer import BlinkExpertTrainer
from AntSleap.core.blink_heatmap_trainer import BlinkHeatmapTrainer
from AntSleap.core.expert_notes import load_expert_notes, set_expert_note
from AntSleap.core.training_weight_publisher import (
    TRAINING_BUNDLE_DIRECTORY,
    TrainingWeightPublisher,
)


class DummyPartsModel:
    ultralytics_sam = None


class DummyCascadeManager:
    def __init__(self):
        self.calls = []
        self.result = {"box": [22.0, 24.0, 40.0, 42.0], "confidence": 1.0, "area_ratio": 0.08}

    def infer_child_part(self, image_path, parent_box, child_part_name, parent_part="macro_locator", route_manifest=None):
        self.calls.append(
            {
                "image_path": image_path,
                "parent_box": list(parent_box),
                "child_part_name": child_part_name,
                "parent_part": parent_part,
                "route_manifest": route_manifest,
            }
        )
        return self.result

class DummyEngine:
    def __init__(self, weights_dir):
        self.weights_dir = weights_dir
        self.device = "cpu"
        self.parts_model = DummyPartsModel()
        self.cascade_manager = DummyCascadeManager()
        self.locator_resolution = (512, 512)
        self.loaded_locator_requires_legacy_confirmation = False
        self.loaded_locator_is_legacy_512 = False
        self.loaded_locator_timestamp = None
        self.predicted_polygons = []
        self.polygon_result = [[24.0, 26.0], [42.0, 26.0], [38.0, 44.0]]

    def predict_base_sam_polygon(self, image_input, prompt_box, poly_epsilon=2.0):
        self.predicted_polygons.append({"shape": tuple(image_input.shape[:2]), "prompt_box": list(prompt_box), "epsilon": poly_epsilon})
        return self.polygon_result


class DummyProjectManager:
    def __init__(self):
        self.current_project_path = "dummy_project.json"
        self.project_data = {
            "taxonomy": ["Head", "Mandible", "Eye"],
            "locator_scope": ["Head"],
            "labels": {},
            "blink_context_roi_parents": {},
            "cascade_routes": {"version": "project-v2", "routes": []},
        }
        self.updated_labels = []
        self.updated_trajectories = []
        self.route_cleanup_calls = []

    def get_labels(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("parts", {})

    def get_boxes(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("boxes", {})

    def get_auto_boxes(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("auto_boxes", {})

    def get_auto_box_meta(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("auto_box_meta", {})

    def split_auto_boxes_by_source(self, image_path):
        entry = self.project_data["labels"].get(image_path, {})
        auto_boxes = entry.get("auto_boxes", {}) if isinstance(entry.get("auto_boxes", {}), dict) else {}
        meta = entry.get("auto_box_meta", {}) if isinstance(entry.get("auto_box_meta", {}), dict) else {}
        model_boxes = {}
        vlm_boxes = {}
        for part_name, box in auto_boxes.items():
            part_meta = meta.get(part_name, {}) if isinstance(meta.get(part_name), dict) else {}
            if part_meta.get("source") == "vlm_first_mile":
                vlm_boxes[part_name] = box
            else:
                model_boxes[part_name] = box
        return model_boxes, vlm_boxes

    def update_label(self, image_path, part_name, points, description_text=None, box=None, auto_box=None):
        label_entry = self.project_data["labels"].setdefault(
            image_path,
            {"parts": {}, "boxes": {}, "auto_boxes": {}, "trajectories": {}},
        )
        label_entry["parts"][part_name] = points
        if box:
            label_entry["boxes"][part_name] = box
        self.updated_labels.append((image_path, part_name, points, box))

    def update_trajectory(self, image_path, part_name, trajectory, parent_context=None):
        label_entry = self.project_data["labels"].setdefault(
            image_path,
            {"parts": {}, "boxes": {}, "auto_boxes": {}, "trajectories": {}},
        )
        payload = {"frames": trajectory}
        if parent_context:
            payload["parent_context"] = parent_context
        label_entry["trajectories"][part_name] = payload
        self.updated_trajectories.append((image_path, part_name, trajectory, parent_context))

    def get_blink_context_roi_parents(self):
        return dict(self.project_data.get("blink_context_roi_parents", {}))

    def get_blink_context_parent(self, target_part):
        return self.project_data.get("blink_context_roi_parents", {}).get(target_part)

    def remember_blink_context_parent(self, target_part, parent_part, save=True):
        self.project_data.setdefault("blink_context_roi_parents", {})[target_part] = parent_part
        return True

    def clear_blink_context_parent(self, target_part, save=True):
        removed = target_part in self.project_data.get("blink_context_roi_parents", {})
        self.project_data.get("blink_context_roi_parents", {}).pop(target_part, None)
        return removed

    def get_cascade_route(self, parent_part, child_part):
        for route in self.project_data.get("cascade_routes", {}).get("routes", []):
            if route.get("parent") == parent_part and route.get("child") == child_part:
                return dict(route)
        return None

    def register_cascade_route_candidate(
        self,
        parent_part,
        child_part,
        *,
        expert_id=None,
        expert_part=None,
        expert_filename=None,
        expert_backend=None,
        expert_manifest=None,
        input_size=None,
        backend_params=None,
        note=None,
        focus_source=None,
        registration_source="blink_candidate",
        save=True,
    ):
        existing = self.get_cascade_route(parent_part, child_part) or {}
        clean_expert_id = expert_id
        clean_expert_part = expert_part
        clean_expert_filename = expert_filename
        if clean_expert_id and "/" in clean_expert_id:
            clean_expert_part, clean_expert_filename = clean_expert_id.split("/", 1)
        elif clean_expert_part and clean_expert_filename:
            clean_expert_id = f"{clean_expert_part}/{clean_expert_filename}"

        existing_candidates = [
            dict(candidate)
            for candidate in existing.get("expert_candidates", [])
            if isinstance(candidate, dict)
        ]
        if clean_expert_id:
            new_candidate = {
                "expert_id": clean_expert_id,
                "expert_part": clean_expert_part,
                "expert_filename": clean_expert_filename,
                "expert_backend": expert_backend or existing.get("expert_backend", "vit_b_blink"),
                "expert_manifest": expert_manifest,
                "input_size": input_size,
                "backend_params": backend_params or {},
            }
            existing_candidates = [
                candidate
                for candidate in existing_candidates
                if candidate.get("expert_id") != clean_expert_id
            ]
            existing_candidates.insert(0, new_candidate)

        route = {
            "parent": parent_part,
            "child": child_part,
            "enabled": bool(existing.get("enabled", False)),
            "expert_id": existing.get("expert_id"),
            "expert_part": existing.get("expert_part"),
            "expert_filename": existing.get("expert_filename"),
            "expert_backend": expert_backend if expert_backend is not None else existing.get("expert_backend", "vit_b_blink"),
            "expert_manifest": expert_manifest if expert_manifest is not None else existing.get("expert_manifest"),
            "input_size": input_size if input_size is not None else existing.get("input_size"),
            "backend_params": backend_params if backend_params is not None else existing.get("backend_params", {}),
            "note": note if note is not None else existing.get("note"),
            "appointed_expert": dict(existing.get("appointed_expert") or {}),
            "expert_candidates": existing_candidates,
            "focus_source": focus_source,
            "registration_source": registration_source,
        }
        routes = [
            r
            for r in self.project_data.setdefault("cascade_routes", {"version": "project-v2", "routes": []}).get("routes", [])
            if not (r.get("parent") == parent_part and r.get("child") == child_part)
        ]
        routes.append(route)
        self.project_data["cascade_routes"]["routes"] = routes
        return route

    def appoint_cascade_route_expert(
        self,
        parent_part,
        child_part,
        expert_id=None,
        expert_part=None,
        expert_filename=None,
        expert_backend=None,
        expert_manifest=None,
        input_size=None,
        backend_params=None,
        note=None,
        save=True,
    ):
        route = self.register_cascade_route_candidate(
            parent_part,
            child_part,
            expert_backend=expert_backend,
            expert_manifest=expert_manifest,
            input_size=input_size,
            backend_params=backend_params,
            note=note,
            save=False,
        )
        if expert_id:
            clean_expert_id = expert_id
            clean_expert_part, clean_expert_filename = expert_id.split("/", 1)
        else:
            clean_expert_part = expert_part
            clean_expert_filename = expert_filename
            clean_expert_id = f"{expert_part}/{expert_filename}"
        route["expert_id"] = clean_expert_id
        route["expert_part"] = clean_expert_part
        route["expert_filename"] = clean_expert_filename
        route["expert_backend"] = expert_backend or route.get("expert_backend", "vit_b_blink")
        route["expert_manifest"] = expert_manifest if expert_manifest is not None else route.get("expert_manifest")
        route["input_size"] = input_size if input_size is not None else route.get("input_size")
        route["backend_params"] = backend_params if backend_params is not None else route.get("backend_params", {})
        route["note"] = note if note is not None else route.get("note")
        route["appointed_expert"] = {
            "expert_id": clean_expert_id,
            "expert_part": clean_expert_part,
            "expert_filename": clean_expert_filename,
            "expert_backend": route.get("expert_backend"),
            "expert_manifest": route.get("expert_manifest"),
            "input_size": route.get("input_size"),
            "backend_params": route.get("backend_params", {}),
        }
        route["expert_candidates"] = [dict(route["appointed_expert"])]
        routes = [
            r
            for r in self.project_data.setdefault("cascade_routes", {"version": "project-v2", "routes": []}).get("routes", [])
            if not (r.get("parent") == parent_part and r.get("child") == child_part)
        ]
        routes.append(route)
        self.project_data["cascade_routes"]["routes"] = routes
        return route

    def set_cascade_route_enabled(self, parent_part, child_part, enabled, save=True):
        route = self.get_cascade_route(parent_part, child_part)
        if not route:
            route = self.register_cascade_route_candidate(parent_part, child_part, save=False)
        route["enabled"] = bool(enabled)
        routes = [
            r
            for r in self.project_data.setdefault("cascade_routes", {"version": "project-v2", "routes": []}).get("routes", [])
            if not (r.get("parent") == parent_part and r.get("child") == child_part)
        ]
        routes.append(route)
        self.project_data["cascade_routes"]["routes"] = routes
        return route

    def get_locator_scope(self):
        return list(self.project_data.get("locator_scope", []))

    def get_current_project_expert_bucket_impacts(self, child_part):
        clean_child = str(child_part or "").strip()
        routes = []
        for route in self.project_data.get("cascade_routes", {}).get("routes", []):
            if route.get("child") != clean_child:
                continue
            routes.append(
                {
                    "parent": route.get("parent"),
                    "child": route.get("child"),
                    "enabled": bool(route.get("enabled", False)),
                    "appointed_expert_id": route.get("appointed_expert", {}).get("expert_id") if isinstance(route.get("appointed_expert"), dict) else None,
                    "expert_id": route.get("expert_id"),
                }
            )
        return {"child_part": clean_child, "routes": routes}

    def remove_current_project_expert_bucket_routes(self, child_part, save=True):
        clean_child = str(child_part or "").strip()
        routes = list(self.project_data.get("cascade_routes", {}).get("routes", []))
        kept = [route for route in routes if route.get("child") != clean_child]
        removed = len(routes) - len(kept)
        self.project_data.setdefault("cascade_routes", {"version": "project-v2", "routes": []})["routes"] = kept
        self.route_cleanup_calls.append((clean_child, removed, save))
        return removed


class BlinkBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        image_path = Path(self.temp_dir.name) / "specimen.png"
        Image.new("RGB", (120, 100), color=(180, 180, 180)).save(image_path)
        self.image_path = str(image_path)

        weights_dir = Path(self.temp_dir.name) / "weights"
        weights_dir.mkdir(parents=True, exist_ok=True)
        (weights_dir / "experts").mkdir(parents=True, exist_ok=True)

        self.engine = DummyEngine(str(weights_dir))
        self.pm = DummyProjectManager()
        self.pm.project_data["labels"][self.image_path] = {
            "parts": {
                "Mandible": [[20.0, 20.0], [40.0, 20.0], [35.0, 40.0]],
                "Eye": [[55.0, 25.0], [65.0, 25.0], [60.0, 35.0]],
            },
            "boxes": {
                "Head": [10.0, 10.0, 80.0, 70.0],
                "Mandible": [18.0, 18.0, 42.0, 42.0],
            },
            "auto_boxes": {
                "Eye": [54.0, 24.0, 66.0, 36.0],
            },
            "trajectories": {},
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_expert_file(self, part_name, filename, content=b"expert"):
        bucket_dir = Path(self.engine.weights_dir) / "experts" / part_name
        bucket_dir.mkdir(parents=True, exist_ok=True)
        file_path = bucket_dir / filename
        file_path.write_bytes(content)
        return file_path

    def _publish_active_expert(
        self,
        run_id="blink-ui-run-001",
        *,
        child_part="Mandible",
    ):
        staging_root = Path(self.temp_dir.name) / f"staging-{run_id}"
        child_dir = staging_root / child_part
        child_dir.mkdir(parents=True)
        staged_weights = child_dir / "expert_published.pth"
        staged_weights.write_bytes(b"published blink weights")
        staged_manifest = staged_weights.with_suffix(".manifest.json")
        staged_manifest.write_text(
            json.dumps(
                build_blink_expert_manifest(
                    str(staged_weights),
                    parent_part="Head",
                    child_part=child_part,
                    input_size=(64, 64),
                )
            ),
            encoding="utf-8",
        )
        model_root = Path(self.engine.weights_dir) / "experts"
        publisher = TrainingWeightPublisher(model_root)
        publication = publisher.publish_pending(
            run_id,
            staging_root,
            [
                {
                    "artifact_id": "blink_checkpoint",
                    "role": "output_weights",
                    "relative_path": f"{child_part}/expert_published.pth",
                    "media_type": "application/octet-stream",
                },
                {
                    "artifact_id": "blink_model_manifest",
                    "role": "model_manifest",
                    "relative_path": f"{child_part}/expert_published.manifest.json",
                    "media_type": "application/json",
                },
            ],
        )
        active = publisher.activate(
            run_id,
            {
                "schema_version": "taxamask_training_run_v1",
                "run_id": run_id,
                "status": "succeeded",
                "artifacts": publication["artifacts"],
            },
        )
        artifacts = {item["artifact_id"]: item for item in active["artifacts"]}
        published_weights = model_root.joinpath(
            *artifacts["blink_checkpoint"]["relative_path"].split("/")
        )
        published_manifest = model_root.joinpath(
            *artifacts["blink_model_manifest"]["relative_path"].split("/")
        )
        return published_weights, published_manifest

    def _select_bucket_item(self, widget, part_name):
        widget.refresh_expert_registry()
        for index in range(widget.expert_tree.topLevelItemCount()):
            item = widget.expert_tree.topLevelItem(index)
            if item is not None and item.text(0) == part_name:
                widget.expert_tree.setCurrentItem(item)
                return item
        self.fail(f"Bucket item for {part_name} was not found")

    def _select_model_item(self, widget, part_name, filename):
        part_item = self._select_bucket_item(widget, part_name)
        for index in range(part_item.childCount()):
            item = part_item.child(index)
            if item is None:
                continue
            if item.text(0) == filename:
                widget.expert_tree.setCurrentItem(item)
                return item
        self.fail(f"Model item for {part_name}/{filename} was not found")

    def _select_model_item_by_expert_id(self, widget, part_name, expert_id):
        part_item = self._select_bucket_item(widget, part_name)
        for index in range(part_item.childCount()):
            item = part_item.child(index)
            if item is None:
                continue
            if item.data(0, Qt.UserRole + 2) == expert_id:
                widget.expert_tree.setCurrentItem(item)
                return item
        self.fail(f"Model item for {expert_id} was not found")

    def test_dialog_requires_explicit_roi_when_no_preference_exists_even_if_context_box_exists(self):
        dialog = BlinkEntryDialog(
            self.image_path,
            ["Head", "Mandible", "Eye"],
            "Mandible",
            [
                {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
                {"part": "Mandible", "source": "manual", "box": [18.0, 18.0, 42.0, 42.0]},
            ],
        )

        self.assertEqual(dialog.target_combo.currentText(), "Mandible")
        self.assertEqual(dialog.roi_combo.currentIndex(), -1)
        self.assertIsNone(dialog.roi_combo.currentData())
        self.assertIsNone(dialog.get_session_spec(self.image_path))

    def test_dialog_prefers_remembered_parent_roi_when_available(self):
        dialog = BlinkEntryDialog(
            self.image_path,
            ["Head", "Mandible", "Eye"],
            "Mandible",
            [
                {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
                {"part": "Mandible", "source": "manual", "box": [18.0, 18.0, 42.0, 42.0]},
            ],
            remembered_parent_map={"Mandible": "Head"},
        )

        current_roi = dialog.roi_combo.currentData()
        self.assertIsInstance(current_roi, dict)
        self.assertEqual(current_roi.get("part"), "Head")

    def test_workbench_candidate_collection_prefers_remembered_head_context_for_eye(self):
        fake_window = types.SimpleNamespace(project=self.pm)
        self.pm.remember_blink_context_parent("Eye", "Head", save=False)
        preferred_roi_parts = main_module._blink_preferred_roi_parts(
            "Eye",
            self.pm.get_blink_context_parent("Eye"),
        )
        roi_candidates = MainWindow._collect_blink_roi_candidates(
            fake_window,
            self.image_path,
            "Eye",
            preferred_roi_parts=preferred_roi_parts,
        )

        self.assertGreaterEqual(len(roi_candidates), 2)
        self.assertEqual(roi_candidates[0].get("part"), "Head")

        dialog = BlinkEntryDialog(
            self.image_path,
            ["Head", "Mandible", "Eye"],
            "Eye",
            roi_candidates,
            remembered_parent_map=self.pm.get_blink_context_roi_parents(),
        )

        current_roi = dialog.roi_combo.currentData()
        self.assertIsInstance(current_roi, dict)
        self.assertEqual(current_roi.get("part"), "Head")

    def test_dialog_requires_explicit_roi_when_only_unrelated_boxes_exist(self):
        dialog = BlinkEntryDialog(
            self.image_path,
            ["Head", "Mandible", "Eye"],
            "Mandible",
            [
                {"part": "Mesosoma", "source": "manual", "box": [5.0, 5.0, 90.0, 80.0]},
            ],
        )

        self.assertEqual(dialog.roi_combo.currentIndex(), -1)
        self.assertIsNone(dialog.roi_combo.currentData())
        self.assertIsNone(dialog.get_session_spec(self.image_path))

    def test_launch_blink_remembers_user_selected_parent_context(self):
        class DummyItem:
            def data(self, _role):
                return "Mandible"

            def text(self):
                return "Mandible"

        class DummyPartList:
            def currentItem(self):
                return DummyItem()

        class DummyBlinkLab:
            def __init__(self):
                self.last_session = None
                self.last_labels = None
                self.last_manual_boxes = None
                self.last_auto_boxes = None

            def start_session(self, session, labels, manual_boxes, auto_boxes):
                self.last_session = session
                self.last_labels = labels
                self.last_manual_boxes = manual_boxes
                self.last_auto_boxes = auto_boxes
                return True

        class FakeDialog:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

            def exec(self):
                return QDialog.DialogCode.Accepted

            def get_session_spec(self, image_path):
                return {
                    "image_path": image_path,
                    "target_part": "Mandible",
                    "focus_roi": {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
                }

        fake_window = types.SimpleNamespace(
            current_image=self.image_path,
            current_lang="en",
            part_list=DummyPartList(),
            project=self.pm,
            blink_lab=DummyBlinkLab(),
            tabs=types.SimpleNamespace(setCurrentWidget=lambda *_args, **_kwargs: None),
            log=lambda *_args, **_kwargs: None,
        )
        fake_window._current_part_name = lambda: "Mandible"
        fake_window._collect_blink_roi_candidates = lambda image_path, selected_part, preferred_roi_parts=None: MainWindow._collect_blink_roi_candidates(
            fake_window,
            image_path,
            selected_part,
            preferred_roi_parts=preferred_roi_parts,
        )

        with patch.object(blink_context_module, "BlinkEntryDialog", FakeDialog):
            MainWindow.launch_blink_from_workbench(fake_window)

        self.assertEqual(self.pm.get_blink_context_parent("Mandible"), "Head")
        route = self.pm.get_cascade_route("Head", "Mandible")
        self.assertIsNotNone(route)
        self.assertFalse(route.get("enabled"))
        self.assertEqual(fake_window.blink_lab.last_labels, self.pm.get_labels(self.image_path))
        self.assertEqual(fake_window.blink_lab.last_manual_boxes, self.pm.get_boxes(self.image_path))
        self.assertEqual(fake_window.blink_lab.last_auto_boxes, self.pm.get_auto_boxes(self.image_path))

    def test_launch_blink_passes_only_model_auto_boxes_to_child_session(self):
        class DummyItem:
            def data(self, _role):
                return "Mandible"

            def text(self):
                return "Mandible"

        class DummyPartList:
            def currentItem(self):
                return DummyItem()

        class DummyBlinkLab:
            def __init__(self):
                self.last_auto_boxes = None

            def start_session(self, session, labels, manual_boxes, auto_boxes):
                self.last_auto_boxes = auto_boxes
                return True

        class FakeDialog:
            def __init__(self, *args, **kwargs):
                pass

            def exec(self):
                return QDialog.DialogCode.Accepted

            def get_session_spec(self, image_path):
                return {
                    "image_path": image_path,
                    "target_part": "Mandible",
                    "focus_roi": {"part": "Head", "source": "auto", "box": [10.0, 10.0, 80.0, 70.0]},
                }

        label_entry = self.pm.project_data["labels"][self.image_path]
        label_entry.setdefault("auto_boxes", {})["Mandible"] = [5.0, 5.0, 15.0, 15.0]
        label_entry.setdefault("auto_box_meta", {})["Eye"] = {"source": "model_prediction", "review_status": "draft"}
        label_entry.setdefault("auto_box_meta", {})["Mandible"] = {"source": "vlm_first_mile", "review_status": "draft"}

        fake_window = types.SimpleNamespace(
            current_image=self.image_path,
            current_lang="en",
            part_list=DummyPartList(),
            project=self.pm,
            blink_lab=DummyBlinkLab(),
            tabs=types.SimpleNamespace(setCurrentWidget=lambda *_args, **_kwargs: None),
            log=lambda *_args, **_kwargs: None,
        )
        fake_window._current_part_name = lambda: "Mandible"
        fake_window._collect_blink_roi_candidates = lambda image_path, selected_part, preferred_roi_parts=None: MainWindow._collect_blink_roi_candidates(
            fake_window,
            image_path,
            selected_part,
            preferred_roi_parts=preferred_roi_parts,
        )
        fake_window._auto_boxes_for_canvas = lambda image_path: self.pm.split_auto_boxes_by_source(image_path)

        with patch.object(blink_context_module, "BlinkEntryDialog", FakeDialog):
            MainWindow.launch_blink_from_workbench(fake_window)

        self.assertEqual(fake_window.blink_lab.last_auto_boxes, {"Eye": [54.0, 24.0, 66.0, 36.0]})
        self.assertNotIn("Mandible", fake_window.blink_lab.last_auto_boxes)

    def test_launch_blink_clears_remembered_parent_when_target_roi_is_chosen(self):
        self.pm.remember_blink_context_parent("Mandible", "Head", save=False)

        class DummyItem:
            def data(self, _role):
                return "Mandible"

            def text(self):
                return "Mandible"

        class DummyPartList:
            def currentItem(self):
                return DummyItem()

        class DummyBlinkLab:
            def __init__(self):
                self.last_session = None

            def start_session(self, session, labels, manual_boxes, auto_boxes):
                self.last_session = session
                return True

        class FakeDialog:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

            def exec(self):
                return QDialog.DialogCode.Accepted

            def get_session_spec(self, image_path):
                return {
                    "image_path": image_path,
                    "target_part": "Mandible",
                    "focus_roi": {"part": "Mandible", "source": "manual", "box": [18.0, 18.0, 42.0, 42.0]},
                }

        fake_window = types.SimpleNamespace(
            current_image=self.image_path,
            current_lang="en",
            part_list=DummyPartList(),
            project=self.pm,
            blink_lab=DummyBlinkLab(),
            tabs=types.SimpleNamespace(setCurrentWidget=lambda *_args, **_kwargs: None),
            log=lambda *_args, **_kwargs: None,
        )
        fake_window._current_part_name = lambda: "Mandible"
        fake_window._collect_blink_roi_candidates = lambda image_path, selected_part, preferred_roi_parts=None: MainWindow._collect_blink_roi_candidates(
            fake_window,
            image_path,
            selected_part,
            preferred_roi_parts=preferred_roi_parts,
        )

        with patch.object(blink_context_module, "BlinkEntryDialog", FakeDialog):
            MainWindow.launch_blink_from_workbench(fake_window)

        self.assertIsNone(self.pm.get_blink_context_parent("Mandible"))

    def test_start_session_focuses_selected_roi_and_hides_non_target_polygons(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        session = {
            "image_path": self.image_path,
            "target_part": "Mandible",
            "focus_roi": {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
        }

        started = widget.start_session(
            session,
            self.pm.get_labels(self.image_path),
            self.pm.get_boxes(self.image_path),
            self.pm.get_auto_boxes(self.image_path),
        )

        self.assertTrue(started)
        self.assertEqual(widget.session_target_part, "Mandible")
        self.assertEqual(widget.canvas.current_tool_part, "Mandible")
        self.assertIn("Mandible", widget.canvas.polygons)
        self.assertNotIn("Eye", widget.canvas.polygons)
        self.assertIn("Head", widget.canvas.manual_boxes)
        self.assertEqual(tuple(widget.zoomed_img_np.shape[:2]), (800, 800))

    def test_blink_integrity_recovery_allows_only_one_retry(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        request = {"project_path": self.pm.current_project_path, "part": "Mandible"}
        self.assertTrue(widget._queue_blink_integrity_retry(request))
        self.assertFalse(widget._queue_blink_integrity_retry(request))
        self.assertTrue(widget.integrity_recovery_retry_used)
        self.assertEqual(widget.pending_blink_retry_request, request)

    def test_blink_training_integrity_error_queues_recovery_retry(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        widget.pending_training_request = {
            "project_path": self.pm.current_project_path,
            "part": "Mandible",
        }
        worker = types.SimpleNamespace(project_path=self.pm.current_project_path)

        class FakeRecovery:
            report = {"status": "verified"}

            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

            def exec(self):
                return 1

        with patch("ui.blink_lab.TrainingIntegrityRecoveryDialog", FakeRecovery):
            widget._on_training_error("registry_verified_file_changed", worker=worker)

        self.assertTrue(widget.integrity_recovery_retry_used)
        self.assertEqual(
            widget.pending_blink_retry_request,
            widget.pending_training_request,
        )

    def test_blink_preflight_recovery_retry_links_failed_run(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        request = {
            "project_path": self.pm.current_project_path,
            "part": "Mandible",
        }
        worker = types.SimpleNamespace(project_path=self.pm.current_project_path)
        error = RuntimeError("registry_verified_file_changed")
        error.training_run_id = "failed_blink_preflight_run"
        widget.training_preflight_thread = worker
        widget.training_preflight_dialog = None

        class FakeRecovery:
            report = {"status": "verified"}

            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

            def exec(self):
                return 1

        with patch("ui.blink_lab.QMessageBox.critical"), patch(
            "ui.blink_lab.TrainingIntegrityRecoveryDialog", FakeRecovery
        ), patch.object(
            widget, "_start_queued_blink_integrity_retry", return_value=True
        ) as start_retry:
            widget._on_blink_preflight_error(error, request, worker)

        self.assertEqual(
            widget.pending_blink_retry_request["retry_of"],
            "failed_blink_preflight_run",
        )
        start_retry.assert_called_once_with()

    def test_blink_session_filters_vlm_drafts_from_internal_auto_boxes(self):
        label_entry = self.pm.project_data["labels"][self.image_path]
        label_entry.setdefault("auto_boxes", {})["Mandible"] = [5.0, 5.0, 15.0, 15.0]
        label_entry.setdefault("auto_box_meta", {})["Eye"] = {"source": "model_prediction", "review_status": "draft"}
        label_entry.setdefault("auto_box_meta", {})["Mandible"] = {"source": "vlm_first_mile", "review_status": "draft"}

        widget = BlinkLabWidget(self.engine, self.pm)
        session = {
            "image_path": self.image_path,
            "target_part": "Mandible",
            "focus_roi": {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
        }

        started = widget.start_session(session)

        self.assertTrue(started)
        self.assertEqual(widget.raw_auto_boxes, {"Eye": [54.0, 24.0, 66.0, 36.0]})
        self.assertNotIn("Mandible", widget.canvas.auto_boxes)

    def test_apply_to_global_only_writes_target_part(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        session = {
            "image_path": self.image_path,
            "target_part": "Mandible",
            "focus_roi": {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
        }
        widget.start_session(
            session,
            self.pm.get_labels(self.image_path),
            self.pm.get_boxes(self.image_path),
            self.pm.get_auto_boxes(self.image_path),
        )

        widget.canvas.polygons["Mandible"] = [[25.0, 25.0], [55.0, 25.0], [45.0, 55.0]]
        widget.canvas.manual_boxes["Mandible"] = [22.0, 22.0, 58.0, 58.0]
        widget.canvas.polygons["Eye"] = [[60.0, 30.0], [70.0, 30.0], [65.0, 40.0]]
        widget.canvas.manual_boxes["Eye"] = [58.0, 28.0, 72.0, 42.0]

        widget.apply_to_global()

        self.assertEqual(len(self.pm.updated_labels), 1)
        _, part_name, _, _ = self.pm.updated_labels[0]
        self.assertEqual(part_name, "Mandible")
        self.assertNotIn("Eye", self.pm.project_data["labels"][self.image_path]["boxes"])

    def test_refresh_from_workbench_skips_dirty_session_reload(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        session = {
            "image_path": self.image_path,
            "target_part": "Mandible",
            "focus_roi": {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
        }
        widget.start_session(
            session,
            self.pm.get_labels(self.image_path),
            self.pm.get_boxes(self.image_path),
            self.pm.get_auto_boxes(self.image_path),
        )

        widget.session_dirty = True
        refreshed = widget.refresh_from_workbench(
            self.image_path,
            {"Mandible": [[1.0, 1.0], [2.0, 1.0], [1.5, 2.0]]},
            {"Head": [0.0, 0.0, 10.0, 10.0]},
            {},
        )

        self.assertFalse(refreshed)
        self.assertIn("Mandible", widget.canvas.polygons)
        self.assertEqual(widget.canvas.current_tool_part, "Mandible")

    def test_refresh_from_workbench_same_image_preserves_viewport(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        widget.resize(1400, 900)
        widget.show()
        self.app.processEvents()

        session = {
            "image_path": self.image_path,
            "target_part": "Mandible",
            "focus_roi": {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
        }
        widget.start_session(
            session,
            self.pm.get_labels(self.image_path),
            self.pm.get_boxes(self.image_path),
            self.pm.get_auto_boxes(self.image_path),
        )

        widget.canvas.scale = 2.4
        widget.canvas.offset = QPointF(28.0, 36.0)

        updated_points = [[22.0, 22.0], [48.0, 22.0], [40.0, 52.0]]
        self.pm.project_data["labels"][self.image_path]["parts"]["Mandible"] = updated_points

        refreshed = widget.refresh_from_workbench(
            self.image_path,
            self.pm.get_labels(self.image_path),
            self.pm.get_boxes(self.image_path),
            self.pm.get_auto_boxes(self.image_path),
        )
        self.app.processEvents()

        expected_local = widget.mapper.poly_global_to_local(updated_points)
        expected_local = [[float(x), float(y)] for x, y in expected_local]

        self.assertTrue(refreshed)
        self.assertAlmostEqual(widget.canvas.scale, 2.4)
        self.assertAlmostEqual(widget.canvas.offset.x(), 28.0)
        self.assertAlmostEqual(widget.canvas.offset.y(), 36.0)
        self.assertEqual(widget.canvas.polygons["Mandible"], expected_local)

        widget.hide()

    def test_auto_shrink_marks_session_dirty(self):
        module = types.ModuleType("core.blink_refiner")

        class FakeBlinkRefiner:
            last_device = None
            last_steps = None

            def __init__(self, sam_model=None, device="auto"):
                self.sam_model = sam_model
                FakeBlinkRefiner.last_device = device

            def generate_shrink_trajectory(self, image_input, initial_box, golden_poly, steps=20):
                FakeBlinkRefiner.last_steps = steps
                return [
                    {"box": [18.0, 18.0, 42.0, 42.0], "step": 0, "alpha": 0.0, "coord_frame": "local"},
                    {"box": [20.0, 20.0, 40.0, 40.0], "step": 1, "alpha": 1.0, "coord_frame": "local"},
                ]

        module.BlinkRefiner = FakeBlinkRefiner
        previous_module = sys.modules.get("core.blink_refiner")
        sys.modules["core.blink_refiner"] = module
        try:
            widget = BlinkLabWidget(self.engine, self.pm, blink_auto_shrink_steps=7)
            session = {
                "image_path": self.image_path,
                "target_part": "Mandible",
                "focus_roi": {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
            }
            widget.start_session(
                session,
                self.pm.get_labels(self.image_path),
                self.pm.get_boxes(self.image_path),
                self.pm.get_auto_boxes(self.image_path),
            )

            widget.session_dirty = False
            widget.run_auto_shrink()

            self.assertTrue(widget.session_dirty)
            self.assertEqual(widget.canvas.manual_boxes["Mandible"], [20.0, 20.0, 40.0, 40.0])
            self.assertEqual(len(self.pm.updated_trajectories), 1)
            _, saved_part, saved_frames, parent_context = self.pm.updated_trajectories[0]
            self.assertEqual(saved_part, "Mandible")
            self.assertEqual(len(saved_frames), 2)
            self.assertIsInstance(parent_context, dict)
            self.assertEqual(parent_context.get("parent_part"), "Head")
            self.assertEqual(FakeBlinkRefiner.last_device, "auto")
            self.assertEqual(FakeBlinkRefiner.last_steps, 7)
        finally:
            if previous_module is not None:
                sys.modules["core.blink_refiner"] = previous_module
            else:
                sys.modules.pop("core.blink_refiner", None)

    def test_auto_annotate_generates_polygon_without_overwriting_manual_box(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        session = {
            "image_path": self.image_path,
            "target_part": "Mandible",
            "focus_roi": {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
        }
        widget.start_session(
            session,
            self.pm.get_labels(self.image_path),
            self.pm.get_boxes(self.image_path),
            self.pm.get_auto_boxes(self.image_path),
        )

        widget.canvas.polygons.pop("Mandible", None)
        original_manual_box = list(widget.canvas.manual_boxes["Mandible"])
        widget.run_auto_annotate()

        self.assertIn("Mandible", widget.canvas.polygons)
        self.assertEqual(widget.canvas.manual_boxes["Mandible"], original_manual_box)
        self.assertTrue(widget.session_dirty)
        self.assertEqual(len(self.engine.cascade_manager.calls), 1)
        self.assertEqual(self.engine.cascade_manager.calls[0]["child_part_name"], "Mandible")
        self.assertEqual(len(self.engine.predicted_polygons), 1)
        self.assertIn("Refine it", widget.lbl_status.text())

    def test_auto_annotate_requires_appointed_route_expert(self):
        self.engine.cascade_manager.result = None
        widget = BlinkLabWidget(self.engine, self.pm)
        session = {
            "image_path": self.image_path,
            "target_part": "Mandible",
            "focus_roi": {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
        }
        widget.start_session(
            session,
            self.pm.get_labels(self.image_path),
            self.pm.get_boxes(self.image_path),
            self.pm.get_auto_boxes(self.image_path),
        )

        widget.canvas.polygons.pop("Mandible", None)
        widget.run_auto_annotate()

        self.assertIn("Train one or appoint a candidate", widget.lbl_status.text())
        self.assertEqual(len(self.engine.predicted_polygons), 0)

    def test_manual_prompt_box_generates_polygon_without_overwriting_shrink_box(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        session = {
            "image_path": self.image_path,
            "target_part": "Mandible",
            "focus_roi": {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
        }
        widget.start_session(
            session,
            self.pm.get_labels(self.image_path),
            self.pm.get_boxes(self.image_path),
            self.pm.get_auto_boxes(self.image_path),
        )

        widget.canvas.polygons.pop("Mandible", None)
        original_manual_box = list(widget.canvas.manual_boxes["Mandible"])
        widget.on_tool_changed(widget.rb_box_prompt)
        widget.on_box_drawn(28.0, 30.0, 46.0, 48.0)

        self.assertIn("Mandible", widget.canvas.polygons)
        self.assertEqual(widget.canvas.manual_boxes["Mandible"], original_manual_box)
        self.assertEqual(len(self.engine.cascade_manager.calls), 0)
        self.assertEqual(len(self.engine.predicted_polygons), 1)
        self.assertEqual(self.engine.predicted_polygons[0]["prompt_box"], [28.0, 30.0, 46.0, 48.0])
        self.assertIn("Refine it", widget.lbl_status.text())
        self.assertEqual(widget.box_tool_role, "shrink")

    def test_manual_prompt_box_failure_resets_back_to_shrink_mode(self):
        self.engine.polygon_result = None
        widget = BlinkLabWidget(self.engine, self.pm)
        session = {
            "image_path": self.image_path,
            "target_part": "Mandible",
            "focus_roi": {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
        }
        widget.start_session(
            session,
            self.pm.get_labels(self.image_path),
            self.pm.get_boxes(self.image_path),
            self.pm.get_auto_boxes(self.image_path),
        )

        widget.canvas.polygons.pop("Mandible", None)
        widget.on_tool_changed(widget.rb_box_prompt)
        widget.on_box_drawn(28.0, 30.0, 46.0, 48.0)

        self.assertNotIn("Mandible", widget.canvas.polygons)
        self.assertIn("Adjust the box", widget.lbl_status.text())
        self.assertEqual(widget.box_tool_role, "shrink")
        self.assertTrue(widget.rb_box.isChecked())

    def test_manual_prompt_cancel_resets_back_to_shrink_mode(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        session = {
            "image_path": self.image_path,
            "target_part": "Mandible",
            "focus_roi": {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
        }
        widget.start_session(
            session,
            self.pm.get_labels(self.image_path),
            self.pm.get_boxes(self.image_path),
            self.pm.get_auto_boxes(self.image_path),
        )

        widget.on_tool_changed(widget.rb_box_prompt)
        with patch("ui.blink_lab.themed_yes_no_question", return_value=QMessageBox.StandardButton.No):
            widget.on_box_drawn(28.0, 30.0, 46.0, 48.0)

        self.assertIn("cancelled", widget.lbl_status.text())
        self.assertEqual(widget.box_tool_role, "shrink")
        self.assertTrue(widget.rb_box.isChecked())

    def test_blink_expert_trainer_log_callback_keeps_stdout_prints(self):
        trainer = BlinkExpertTrainer.__new__(BlinkExpertTrainer)
        received_logs = []

        with patch("builtins.print") as print_mock:
            trainer._emit_training_log("Epoch 1 ready", received_logs.append)

        print_mock.assert_called_once_with("Epoch 1 ready")
        self.assertEqual(received_logs, ["Epoch 1 ready"])

    def test_blink_expert_trainer_rejects_unsafe_part_name(self):
        with self.assertRaises(ValueError):
            BlinkExpertTrainer(
                project_path=self.pm.current_project_path,
                part_name="..\\unsafe",
                save_dir=str(Path(self.engine.weights_dir) / "experts"),
                device="cpu",
            )

    def test_blink_expert_trainer_versioned_candidate_path_preserves_existing_models(self):
        save_dir = Path(self.engine.weights_dir) / "experts"
        appointed_path = save_dir / "Mandible" / "expert_v20260501_090000.pth"
        appointed_path.parent.mkdir(parents=True, exist_ok=True)
        appointed_path.write_bytes(b"appointed")

        trainer = BlinkExpertTrainer.__new__(BlinkExpertTrainer)
        trainer.save_dir = str(appointed_path.parent)

        candidate_path = trainer._next_versioned_save_path()

        self.assertNotEqual(Path(candidate_path).name, "expert_v20260501_090000.pth")
        self.assertTrue(Path(candidate_path).name.startswith("expert_v"))
        self.assertEqual(appointed_path.read_bytes(), b"appointed")

    def test_blink_training_thread_emits_log_signal_and_widget_receives_log_lines(self):
        class FakeTrainer:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def train(
                self,
                epochs=0,
                batch_size=0,
                target_size=(224, 224),
                log_callback=None,
                progress_callback=None,
                stop_callback=None,
            ):
                if log_callback:
                    log_callback("Epoch [1/2] Loss: 0.3210")
                    log_callback("Epoch [2/2] Loss: 0.1230")
                return "saved_expert.pth"

        widget = BlinkLabWidget(self.engine, self.pm)
        thread = BlinkTrainingThread(
            project_path=self.pm.current_project_path,
            part_name="Mandible",
            parent_part="Head",
            epochs=2,
            batch_size=1,
        )
        emitted_logs = []
        emitted_results = []
        thread.log_signal.connect(emitted_logs.append)
        thread.log_signal.connect(widget.append_training_log)
        thread.result_signal.connect(emitted_results.append)

        with patch("AntSleap.core.blink_trainer.BlinkExpertTrainer", FakeTrainer):
            thread.start()
            thread.wait()
            self.app.processEvents()

        console_text = widget.training_log_console.toPlainText()
        self.assertEqual(emitted_results, ["saved_expert.pth"])
        self.assertEqual(
            emitted_logs,
            ["Epoch [1/2] Loss: 0.3210", "Epoch [2/2] Loss: 0.1230"],
        )
        self.assertIn("Epoch [1/2] Loss: 0.3210", console_text)
        self.assertIn("Epoch [2/2] Loss: 0.1230", console_text)

    def test_blink_training_report_waits_until_thread_finished(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        report = {"validation_summary": {"part_name": "Mandible"}, "dir": "report_dir"}
        opened_reports = []

        def fake_show_report():
            opened_reports.append(dict(widget.pending_training_report or {}))
            widget.pending_training_report = None

        widget._show_pending_training_report = fake_show_report
        widget._on_training_report(report)

        self.assertEqual(opened_reports, [])
        self.assertEqual(widget.pending_training_report.get("validation_summary", {}).get("part_name"), "Mandible")

        widget._on_training_finished()
        self.app.processEvents()

        self.assertEqual(opened_reports, [report])
        self.assertIsNone(widget.pending_training_report)

    def test_stale_blink_training_result_does_not_link_route_to_new_project(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        widget.training_route_context = {
            "parent_part": "Head",
            "child_part": "Mandible",
            "had_appointed_expert": False,
        }
        save_path = str(Path(self.engine.weights_dir) / "experts" / "Mandible" / "expert_stale.pth")
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        Path(save_path).write_bytes(b"expert")
        worker = type("Worker", (), {"project_path": str(Path(self.pm.current_project_path).with_name("old_project.json"))})()

        widget._on_training_result(save_path, worker=worker)

        self.assertIsNone(self.pm.get_cascade_route("Head", "Mandible"))
        self.assertIn("previous project", widget.lbl_status.text())

    def test_blink_training_thread_passes_candidate_training_params_to_trainer(self):
        trainer_kwargs = {}

        class FakeTrainer:
            def __init__(self, **kwargs):
                trainer_kwargs.update(kwargs)

            def train(
                self,
                epochs=0,
                batch_size=0,
                target_size=(224, 224),
                log_callback=None,
                progress_callback=None,
                stop_callback=None,
            ):
                return "saved_expert.pth"

        thread = BlinkTrainingThread(
            project_path=self.pm.current_project_path,
            part_name="Mandible",
            parent_part="Head",
            epochs=2,
            batch_size=1,
            learning_rate=0.002,
            weight_decay=0.0003,
            input_size=384,
            outer_loss_weights={"final": 1.2, "step": 0.4, "view": 0.3, "consistency": 0.2},
            device="cpu",
        )
        with patch("AntSleap.core.blink_trainer.BlinkExpertTrainer", FakeTrainer):
            thread.start()
            thread.wait()
            self.app.processEvents()

        self.assertEqual(
            set(trainer_kwargs),
            {
                "project_path",
                "part_name",
                "parent_part",
                "learning_rate",
                "weight_decay",
                "input_size",
                "outer_loss_weights",
                "training_strategy",
                "device",
                "allowed_image_paths",
                "training_scope",
                "save_dir",
                "training_records",
                "validation_records",
            },
        )
        self.assertEqual(trainer_kwargs.get("learning_rate"), 0.002)
        self.assertEqual(trainer_kwargs.get("weight_decay"), 0.0003)
        self.assertEqual(trainer_kwargs.get("input_size"), 384)
        self.assertEqual(
            trainer_kwargs.get("outer_loss_weights"),
            {"final": 1.2, "step": 0.4, "view": 0.3, "consistency": 0.2},
        )
        self.assertEqual(trainer_kwargs.get("training_strategy"), DEFAULT_BLINK_TRAINING_STRATEGY)
        self.assertEqual(trainer_kwargs.get("device"), "cpu")
        self.assertEqual(trainer_kwargs.get("allowed_image_paths"), [])
        self.assertEqual(trainer_kwargs.get("training_scope"), {})

    def test_heatmap_blink_training_thread_passes_outer_loss_weights_to_trainer(self):
        trainer_kwargs = {}

        class FakeTrainer:
            def __init__(self, **kwargs):
                trainer_kwargs.update(kwargs)

            def train(self, **_kwargs):
                return "saved_heatmap_expert.pth"

        custom_weights = {"final": 1.3, "step": 0.45, "view": 0.25, "consistency": 0.15}
        thread = BlinkTrainingThread(
            project_path=self.pm.current_project_path,
            part_name="Mandible",
            parent_part="Head",
            epochs=2,
            batch_size=1,
            trainer_backend=BLINK_EXPERT_BACKEND_HEATMAP,
            outer_loss_weights=custom_weights,
            device="cpu",
        )
        with patch("AntSleap.core.blink_heatmap_trainer.BlinkHeatmapTrainer", FakeTrainer):
            thread.start()
            thread.wait()
            self.app.processEvents()

        self.assertEqual(trainer_kwargs.get("outer_loss_weights"), custom_weights)

    def test_blink_training_thread_without_profile_weights_uses_legacy_defaults(self):
        thread = BlinkTrainingThread(
            project_path=self.pm.current_project_path,
            part_name="Mandible",
            parent_part="Head",
            epochs=1,
            batch_size=1,
        )

        self.assertEqual(thread.outer_loss_weights, DEFAULT_BLINK_OUTER_LOSS_WEIGHTS)

    def test_blink_training_thread_passes_selected_training_strategy(self):
        trainer_kwargs = {}

        class FakeTrainer:
            def __init__(self, **kwargs):
                trainer_kwargs.update(kwargs)

            def train(
                self,
                epochs=0,
                batch_size=0,
                target_size=(224, 224),
                log_callback=None,
                progress_callback=None,
                stop_callback=None,
            ):
                return "saved_expert.pth"

        thread = BlinkTrainingThread(
            project_path=self.pm.current_project_path,
            part_name="Mandible",
            parent_part="Head",
            epochs=2,
            batch_size=1,
            training_strategy="full_inside_random",
            device="cpu",
        )
        with patch("AntSleap.core.blink_trainer.BlinkExpertTrainer", FakeTrainer):
            thread.start()
            thread.wait()
            self.app.processEvents()

        self.assertEqual(trainer_kwargs.get("training_strategy"), "full_inside_random")

    def test_training_success_appoints_and_enables_new_route_expert(self):
        cascade_manager = CascadingManager(self.engine)
        self.engine.cascade_manager = cascade_manager
        widget = BlinkLabWidget(self.engine, self.pm)
        widget.training_route_context = {
            "parent_part": "Head",
            "child_part": "Mandible",
            "had_appointed_expert": False,
        }
        refresh_hits = []
        widget.route_registry_refresh_requested.connect(lambda: refresh_hits.append("refresh"))

        published_path, published_manifest = self._publish_active_expert()
        save_path = str(published_path)

        widget._on_training_result(save_path)

        route = self.pm.get_cascade_route("Head", "Mandible")
        self.assertIsNotNone(route)
        self.assertTrue(route.get("enabled"))
        self.assertEqual(route.get("expert_id"), "Mandible/expert_published.pth")
        self.assertEqual(route.get("appointed_expert", {}).get("expert_id"), "Mandible/expert_published.pth")
        expected_manifest_reference = published_manifest.relative_to(
            Path(self.engine.weights_dir) / "experts"
        ).as_posix()
        self.assertEqual(route.get("expert_manifest"), expected_manifest_reference)
        self.assertEqual(Path(cascade_manager.resolve_route_expert_path(route)), published_path)
        self.assertEqual(
            [candidate.get("expert_id") for candidate in route.get("expert_candidates", [])],
            ["Mandible/expert_published.pth"],
        )
        self.assertEqual(refresh_hits, ["refresh"])
        self.assertIn("enabled", widget.lbl_status.text())
        self.assertIn("Head -> Mandible", widget.lbl_status.text())

        class _CropProbeExpert:
            _taxamask_meta = {"input_size": [64, 64]}

            def __init__(self):
                self.input_shape = None

            def __call__(self, tensor):
                self.input_shape = tuple(tensor.shape)
                return torch.tensor([[0.5, 0.5, 0.5, 0.5]], dtype=torch.float32)

            def _cxcywh_to_xyxy(self, _prediction, width, height):
                return [width * 0.25, height * 0.25, width * 0.75, height * 0.75]

        crop_probe = _CropProbeExpert()
        with patch.object(cascade_manager, "_load_expert", return_value=crop_probe):
            prediction = cascade_manager.infer_child_part(
                self.image_path,
                [10.0, 10.0, 80.0, 70.0],
                "Mandible",
                parent_part="Head",
                route_manifest=self.pm.project_data["cascade_routes"],
            )
        self.assertEqual(crop_probe.input_shape, (1, 3, 64, 64))
        self.assertIsInstance(prediction, dict)
        self.assertGreaterEqual(prediction["box"][0], 10.0)
        self.assertGreaterEqual(prediction["box"][1], 10.0)
        self.assertLessEqual(prediction["box"][2], 80.0)
        self.assertLessEqual(prediction["box"][3], 70.0)

    def test_blink_trainers_reject_reserved_part_names_before_creating_directories(self):
        expert_root = Path(self.engine.weights_dir) / "reserved-constructor-test"
        for trainer_class, reserved_name in (
            (BlinkExpertTrainer, "Training_Runs"),
            (BlinkHeatmapTrainer, "EXPERT_NOTES.JSON"),
        ):
            with self.subTest(trainer=trainer_class.__name__, part=reserved_name):
                with self.assertRaisesRegex(
                    ValueError,
                    "blink_expert_part_name_unsafe_or_reserved",
                ):
                    trainer_class(
                        project_path=self.pm.current_project_path,
                        part_name=reserved_name,
                        save_dir=str(expert_root),
                        device="cpu",
                    )
                self.assertFalse(expert_root.exists())

    def test_blink_trainers_revalidate_mutated_part_before_dataset_access(self):
        for trainer_class in (BlinkExpertTrainer, BlinkHeatmapTrainer):
            with self.subTest(trainer=trainer_class.__name__):
                trainer = trainer_class.__new__(trainer_class)
                trainer.part_name = "cascade_routes.json"
                with patch.object(trainer, "_make_dataset") as make_dataset:
                    with self.assertRaisesRegex(
                        ValueError,
                        "blink_expert_part_name_unsafe_or_reserved",
                    ):
                        trainer.train(epochs=1, batch_size=1)
                make_dataset.assert_not_called()

    def test_blink_training_ui_rejects_reserved_part_before_baseline_or_preflight(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        widget.canvas.current_tool_part = ".training_weight_publication.lock"
        project_before = json.loads(json.dumps(self.pm.project_data))

        with patch.object(widget, "_ensure_blink_training_baseline") as baseline, \
             patch.object(widget, "_start_blink_training_preflight") as preflight, \
             patch("ui.blink_lab.QMessageBox.critical") as critical:
            widget.train_expert_model()

        baseline.assert_not_called()
        preflight.assert_not_called()
        critical.assert_called_once()
        self.assertEqual(self.pm.project_data, project_before)
        self.assertIsNone(widget.training_preflight_thread)

    def test_manual_appointment_rejects_expert_bound_to_another_child_without_project_write(self):
        self.engine.cascade_manager = CascadingManager(self.engine)
        self._publish_active_expert("blink-wrong-child-appointment")
        widget = BlinkLabWidget(self.engine, self.pm)
        widget.start_session(
            {
                "image_path": self.image_path,
                "target_part": "Eye",
                "focus_roi": {
                    "part": "Head",
                    "source": "manual",
                    "box": [10.0, 10.0, 80.0, 70.0],
                },
            },
            self.pm.get_labels(self.image_path),
            self.pm.get_boxes(self.image_path),
            self.pm.get_auto_boxes(self.image_path),
        )
        self._select_model_item_by_expert_id(
            widget,
            "Mandible",
            "Mandible/expert_published.pth",
        )
        project_before = json.loads(json.dumps(self.pm.project_data))

        with patch("ui.blink_lab.QMessageBox.critical") as critical, \
             patch("ui.blink_lab.themed_yes_no_question") as confirm:
            widget.appoint_selected_expert_to_current_route()

        critical.assert_called_once()
        confirm.assert_not_called()
        self.assertEqual(self.pm.project_data, project_before)
        self.assertIsNone(self.pm.get_cascade_route("Head", "Eye"))

    def test_training_result_with_missing_manifest_does_not_register_route(self):
        cascade_manager = CascadingManager(self.engine)
        self.engine.cascade_manager = cascade_manager
        widget = BlinkLabWidget(self.engine, self.pm)
        widget.training_route_context = {
            "parent_part": "Head",
            "child_part": "Mandible",
            "had_appointed_expert": False,
        }
        save_path = str(
            self._create_expert_file(
                "Mandible",
                "expert_without_manifest.pth",
            )
        )

        widget._on_training_result(save_path)

        route = self.pm.get_cascade_route("Head", "Mandible")
        self.assertIsNone(route)
        self.assertIn("route auto-link failed", widget.lbl_status.text())

    def test_training_success_does_not_override_existing_appointed_route_expert(self):
        self.pm.appoint_cascade_route_expert(
            "Head",
            "Mandible",
            expert_id="Mandible/expert_v20260501_090000.pth",
            save=False,
        )
        self.pm.set_cascade_route_enabled("Head", "Mandible", True, save=False)
        widget = BlinkLabWidget(self.engine, self.pm)
        widget.training_route_context = {
            "parent_part": "Head",
            "child_part": "Mandible",
            "had_appointed_expert": True,
        }
        refresh_hits = []
        widget.route_registry_refresh_requested.connect(lambda: refresh_hits.append("refresh"))

        save_path = str(Path(self.engine.weights_dir) / "experts" / "Mandible" / "expert_v20260503_120000.pth")
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        Path(save_path).write_bytes(b"candidate")

        widget._on_training_result(save_path)

        route = self.pm.get_cascade_route("Head", "Mandible")
        self.assertTrue(route.get("enabled"))
        self.assertEqual(route.get("expert_id"), "Mandible/expert_v20260501_090000.pth")
        self.assertEqual(route.get("appointed_expert", {}).get("expert_id"), "Mandible/expert_v20260501_090000.pth")
        self.assertEqual(
            [candidate.get("expert_id") for candidate in route.get("expert_candidates", [])],
            ["Mandible/expert_v20260501_090000.pth"],
        )
        self.assertEqual(refresh_hits, [])
        self.assertIn("route auto-link failed", widget.lbl_status.text())

    def test_bucket_delete_preview_cancel_keeps_files_and_current_project_routes(self):
        self._create_expert_file("Mandible", "expert_v20260501_090000.pth")
        self.pm.project_data["cascade_routes"] = {
            "version": "project-v2",
            "routes": [
                {"parent": "Head", "child": "Mandible", "enabled": True, "expert_id": "Mandible/expert_v20260501_090000.pth", "appointed_expert": {"expert_id": "Mandible/expert_v20260501_090000.pth"}},
            ],
        }
        widget = BlinkLabWidget(self.engine, self.pm)
        self._select_bucket_item(widget, "Mandible")

        with patch.object(widget, "_show_bucket_delete_preview_dialog", return_value=(False, True, None)):
            widget.delete_expert_model()

        self.assertTrue((Path(self.engine.weights_dir) / "experts" / "Mandible" / "expert_v20260501_090000.pth").exists())
        self.assertIsNotNone(self.pm.get_cascade_route("Head", "Mandible"))
        self.assertEqual(self.pm.route_cleanup_calls, [])

    def test_bucket_delete_preview_summary_discloses_path_files_routes_and_default_cleanup(self):
        file_path = self._create_expert_file("Mandible", "expert_v20260501_090000.pth")
        self.pm.project_data["cascade_routes"] = {
            "version": "project-v2",
            "routes": [
                {"parent": "Head", "child": "Mandible", "enabled": True, "expert_id": "Mandible/expert_v20260501_090000.pth", "appointed_expert": {"expert_id": "Mandible/expert_v20260501_090000.pth"}},
            ],
        }
        widget = BlinkLabWidget(self.engine, self.pm)

        summary = widget._summarize_bucket_delete_preview(
            "Mandible",
            str(file_path.parent),
            [str(file_path)],
            self.pm.get_current_project_expert_bucket_impacts("Mandible"),
        )
        dialog = BucketDeletePreviewDialog(
            widget,
            title="preview",
            body_text=summary,
            cleanup_label="cleanup",
            cleanup_checked=True,
        )

        self.assertIn(str(file_path.parent), summary)
        self.assertIn("expert_v20260501_090000.pth", summary)
        self.assertIn("Head -> Mandible", summary)
        self.assertIn("Default cleanup action", summary)
        self.assertIn("currently open project only", summary)
        self.assertTrue(dialog.cleanup_checkbox.isChecked())

    def test_bucket_delete_dialogs_use_strong_destructive_and_cancel_button_styles(self):
        widget = BlinkLabWidget(self.engine, self.pm)
        widget.set_theme("light")

        preview_dialog = BucketDeletePreviewDialog(
            widget,
            title="preview",
            body_text="body",
            cleanup_label="cleanup",
            cleanup_checked=True,
            lang="en",
        )
        type_dialog = BucketDeleteTypeConfirmDialog(
            widget,
            title="confirm",
            prompt_text="prompt",
            expected_text="Mandible",
            placeholder_text="type",
            lang="en",
        )

        for dialog in (preview_dialog, type_dialog):
            ok_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
            cancel_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
            self.assertEqual(ok_button.text(), "Delete Expert Bucket Permanently")
            self.assertEqual(cancel_button.text(), "Cancel")
            self.assertIn("min-width: 168px", ok_button.styleSheet())
            self.assertIn("background-color: #DC2626", ok_button.styleSheet())
            self.assertIn("font-weight: 700", ok_button.styleSheet())
            self.assertIn("border-radius: 8px", cancel_button.styleSheet())
            self.assertIn("font-weight: 700", cancel_button.styleSheet())
            self.assertIn("min-width: 104px", cancel_button.styleSheet())

        self.assertIn("color: #DC2626", type_dialog.error_label.styleSheet())

        preview_dialog.close()
        type_dialog.close()
        widget.close()

    def test_bucket_delete_type_confirmation_guard_keeps_files_and_routes(self):
        self._create_expert_file("Mandible", "expert_v20260501_090000.pth")
        self.pm.project_data["cascade_routes"] = {
            "version": "project-v2",
            "routes": [
                {"parent": "Head", "child": "Mandible", "enabled": True, "expert_id": "Mandible/expert_v20260501_090000.pth", "appointed_expert": {"expert_id": "Mandible/expert_v20260501_090000.pth"}},
            ],
        }
        widget = BlinkLabWidget(self.engine, self.pm)
        self._select_bucket_item(widget, "Mandible")

        with patch.object(widget, "_show_bucket_delete_preview_dialog", return_value=(True, True, None)), \
             patch.object(widget, "_show_bucket_delete_type_confirm_dialog", return_value=(False, None)):
            widget.delete_expert_model()

        self.assertTrue((Path(self.engine.weights_dir) / "experts" / "Mandible" / "expert_v20260501_090000.pth").exists())
        self.assertIsNotNone(self.pm.get_cascade_route("Head", "Mandible"))
        self.assertEqual(self.pm.route_cleanup_calls, [])

    def test_bucket_delete_checked_cleanup_removes_current_project_routes_and_refreshes(self):
        self._create_expert_file("Mandible", "expert_v20260501_090000.pth")
        self._create_expert_file("Mandible", "expert_v20260422_100000.pth")
        set_expert_note(self.engine.weights_dir, "Mandible/expert_v20260501_090000.pth", "old appointed")
        set_expert_note(self.engine.weights_dir, "Mandible/expert_v20260422_100000.pth", "old history")
        set_expert_note(self.engine.weights_dir, "Eye/expert_v20260501_091500.pth", "eye route")
        self.pm.project_data["cascade_routes"] = {
            "version": "project-v2",
            "routes": [
                {"parent": "Head", "child": "Mandible", "enabled": True, "expert_id": "Mandible/expert_v20260501_090000.pth", "appointed_expert": {"expert_id": "Mandible/expert_v20260501_090000.pth"}},
                {"parent": "Eye", "child": "Mandible", "enabled": False, "expert_id": "Mandible/expert_v20260422_100000.pth", "appointed_expert": {"expert_id": "Mandible/expert_v20260422_100000.pth"}},
                {"parent": "Head", "child": "Eye", "enabled": True, "expert_id": "Eye/expert_v20260501_091500.pth", "appointed_expert": {"expert_id": "Eye/expert_v20260501_091500.pth"}},
            ],
        }
        widget = BlinkLabWidget(self.engine, self.pm)
        refresh_hits = []
        widget.route_registry_refresh_requested.connect(lambda: refresh_hits.append("refresh"))
        self._select_bucket_item(widget, "Mandible")

        with patch.object(widget, "_show_bucket_delete_preview_dialog", return_value=(True, True, None)), \
             patch.object(widget, "_show_bucket_delete_type_confirm_dialog", return_value=(True, None)):
            widget.delete_expert_model()

        self.assertFalse((Path(self.engine.weights_dir) / "experts" / "Mandible").exists())
        self.assertIsNone(self.pm.get_cascade_route("Head", "Mandible"))
        self.assertIsNone(self.pm.get_cascade_route("Eye", "Mandible"))
        self.assertIsNotNone(self.pm.get_cascade_route("Head", "Eye"))
        self.assertEqual(self.pm.route_cleanup_calls[-1][:2], ("Mandible", 2))
        self.assertEqual(refresh_hits, ["refresh"])
        notes = load_expert_notes(self.engine.weights_dir)
        self.assertNotIn("Mandible/expert_v20260501_090000.pth", notes)
        self.assertNotIn("Mandible/expert_v20260422_100000.pth", notes)
        self.assertEqual(notes.get("Eye/expert_v20260501_091500.pth"), "eye route")

    def test_bucket_delete_unchecked_cleanup_keeps_current_project_routes(self):
        self._create_expert_file("Mandible", "expert_v20260501_090000.pth")
        self.pm.project_data["cascade_routes"] = {
            "version": "project-v2",
            "routes": [
                {"parent": "Head", "child": "Mandible", "enabled": True, "expert_id": "Mandible/expert_v20260501_090000.pth", "appointed_expert": {"expert_id": "Mandible/expert_v20260501_090000.pth"}},
            ],
        }
        widget = BlinkLabWidget(self.engine, self.pm)
        self._select_bucket_item(widget, "Mandible")

        with patch.object(widget, "_show_bucket_delete_preview_dialog", return_value=(True, False, None)), \
             patch.object(widget, "_show_bucket_delete_type_confirm_dialog", return_value=(True, None)):
            widget.delete_expert_model()

        self.assertFalse((Path(self.engine.weights_dir) / "experts" / "Mandible").exists())
        self.assertIsNotNone(self.pm.get_cascade_route("Head", "Mandible"))
        self.assertEqual(self.pm.route_cleanup_calls, [])

    def test_bucket_delete_failure_does_not_remove_current_project_routes(self):
        self._create_expert_file("Mandible", "expert_v20260501_090000.pth")
        self.pm.project_data["cascade_routes"] = {
            "version": "project-v2",
            "routes": [
                {"parent": "Head", "child": "Mandible", "enabled": True, "expert_id": "Mandible/expert_v20260501_090000.pth", "appointed_expert": {"expert_id": "Mandible/expert_v20260501_090000.pth"}},
            ],
        }
        widget = BlinkLabWidget(self.engine, self.pm)
        self._select_bucket_item(widget, "Mandible")

        with patch.object(widget, "_show_bucket_delete_preview_dialog", return_value=(True, True, None)), \
             patch.object(widget, "_show_bucket_delete_type_confirm_dialog", return_value=(True, None)), \
             patch.object(widget, "_delete_expert_bucket_files", side_effect=OSError("disk busy")), \
             patch("ui.blink_lab.QMessageBox.critical"):
            widget.delete_expert_model()

        self.assertTrue((Path(self.engine.weights_dir) / "experts" / "Mandible" / "expert_v20260501_090000.pth").exists())
        self.assertIsNotNone(self.pm.get_cascade_route("Head", "Mandible"))
        self.assertEqual(self.pm.route_cleanup_calls, [])

    def test_single_file_delete_behavior_is_preserved_for_model_nodes(self):
        self._create_expert_file("Mandible", "expert_v20260501_090000.pth", b"appointed")
        extra_path = self._create_expert_file("Mandible", "expert_v20260422_100000.pth", b"history")
        set_expert_note(self.engine.weights_dir, "Mandible/expert_v20260501_090000.pth", "appointed")
        set_expert_note(self.engine.weights_dir, "Mandible/expert_v20260422_100000.pth", "history")
        self.pm.project_data["cascade_routes"] = {
            "version": "project-v2",
            "routes": [
                {"parent": "Head", "child": "Mandible", "enabled": True, "expert_id": "Mandible/expert_v20260501_090000.pth", "appointed_expert": {"expert_id": "Mandible/expert_v20260501_090000.pth"}},
            ],
        }
        widget = BlinkLabWidget(self.engine, self.pm)
        refresh_hits = []
        widget.route_registry_refresh_requested.connect(lambda: refresh_hits.append("refresh"))
        self._select_model_item_by_expert_id(widget, "Mandible", "Mandible/expert_v20260422_100000.pth")

        with patch("ui.blink_lab.themed_yes_no_question", return_value=QMessageBox.StandardButton.Yes):
            widget.delete_expert_model()

        self.assertFalse(extra_path.exists())
        self.assertTrue((Path(self.engine.weights_dir) / "experts" / "Mandible" / "expert_v20260501_090000.pth").exists())
        self.assertTrue((Path(self.engine.weights_dir) / "experts" / "Mandible").exists())
        self.assertIsNotNone(self.pm.get_cascade_route("Head", "Mandible"))
        self.assertEqual(refresh_hits, ["refresh"])
        notes = load_expert_notes(self.engine.weights_dir)
        self.assertEqual(notes.get("Mandible/expert_v20260501_090000.pth"), "appointed")
        self.assertNotIn("Mandible/expert_v20260422_100000.pth", notes)

    def test_active_managed_publication_cannot_be_deleted_as_single_file(self):
        cascade_manager = CascadingManager(self.engine)
        self.engine.cascade_manager = cascade_manager
        published_path, published_manifest = self._publish_active_expert(
            "blink-ui-delete-guard"
        )
        publication_path = published_path.parents[1] / "publication.json"
        widget = BlinkLabWidget(self.engine, self.pm)
        item = self._select_model_item_by_expert_id(
            widget,
            "Mandible",
            "Mandible/expert_published.pth",
        )

        self.assertEqual(
            item.data(0, Qt.UserRole + 3).get("publication_run_id"),
            "blink-ui-delete-guard",
        )
        self.assertFalse(widget.btn_delete_expert.isEnabled())
        self.assertIn("cannot be deleted", widget.btn_delete_expert.toolTip())
        with patch("ui.blink_lab.QMessageBox.information") as information, \
             patch("ui.blink_lab.os.remove") as remove_file, \
             patch("ui.blink_lab.themed_yes_no_question") as confirm:
            widget.delete_expert_model()

        information.assert_called_once()
        remove_file.assert_not_called()
        confirm.assert_not_called()
        self.assertTrue(published_path.exists())
        self.assertTrue(published_manifest.exists())
        self.assertTrue(publication_path.exists())
        self.assertTrue(cascade_manager.list_available_experts())

    def test_managed_publication_delete_guard_does_not_trust_tree_metadata(self):
        cascade_manager = CascadingManager(self.engine)
        self.engine.cascade_manager = cascade_manager
        published_path, published_manifest = self._publish_active_expert(
            "blink-ui-delete-forged-metadata"
        )
        publication_path = published_path.parents[1] / "publication.json"
        widget = BlinkLabWidget(self.engine, self.pm)
        item = self._select_model_item_by_expert_id(
            widget,
            "Mandible",
            "Mandible/expert_published.pth",
        )
        item.setData(0, Qt.UserRole + 3, None)

        with patch("ui.blink_lab.QMessageBox.information") as information, \
             patch("ui.blink_lab.os.remove") as remove_file, \
             patch("ui.blink_lab.themed_yes_no_question") as confirm:
            widget.delete_expert_model()

        information.assert_called_once()
        confirm.assert_not_called()
        remove_file.assert_not_called()
        self.assertTrue(published_path.exists())
        self.assertTrue(published_manifest.exists())
        self.assertTrue(publication_path.exists())

    def test_single_file_delete_rechecks_ancestor_after_confirmation(self):
        file_path = self._create_expert_file(
            "Mandible",
            "expert_v20260501_090000.pth",
            b"must remain",
        )
        bucket_path = file_path.parent
        widget = BlinkLabWidget(self.engine, self.pm)
        self._select_model_item_by_expert_id(
            widget,
            "Mandible",
            "Mandible/expert_v20260501_090000.pth",
        )
        original_lstat = os.lstat
        state = {"reparse": False}

        def guarded_lstat(path):
            observed = original_lstat(path)
            if state["reparse"] and os.path.normcase(os.path.abspath(path)) == os.path.normcase(str(bucket_path)):
                return types.SimpleNamespace(
                    st_mode=observed.st_mode,
                    st_dev=observed.st_dev,
                    st_ino=observed.st_ino,
                    st_mtime_ns=observed.st_mtime_ns,
                    st_file_attributes=0x400,
                )
            return observed

        def confirm_then_swap(*_args, **_kwargs):
            state["reparse"] = True
            return QMessageBox.StandardButton.Yes

        with patch("ui.blink_lab.os.lstat", side_effect=guarded_lstat), \
             patch("ui.blink_lab.themed_yes_no_question", side_effect=confirm_then_swap), \
             patch("ui.blink_lab.os.remove") as remove_file, \
             patch("ui.blink_lab.QMessageBox.critical") as critical:
            widget.delete_expert_model()

        remove_file.assert_not_called()
        critical.assert_called_once()
        self.assertTrue(file_path.exists())

    def test_single_file_delete_rechecks_fingerprint_after_confirmation(self):
        file_path = self._create_expert_file(
            "Mandible",
            "expert_v20260501_090000.pth",
            b"before confirmation",
        )
        widget = BlinkLabWidget(self.engine, self.pm)
        self._select_model_item_by_expert_id(
            widget,
            "Mandible",
            "Mandible/expert_v20260501_090000.pth",
        )

        def confirm_then_replace(*_args, **_kwargs):
            file_path.write_bytes(b"replacement after confirmation")
            return QMessageBox.StandardButton.Yes

        with patch("ui.blink_lab.themed_yes_no_question", side_effect=confirm_then_replace), \
             patch("ui.blink_lab.os.remove") as remove_file, \
             patch("ui.blink_lab.QMessageBox.critical") as critical:
            widget.delete_expert_model()

        remove_file.assert_not_called()
        critical.assert_called_once()
        self.assertTrue(file_path.exists())
        self.assertEqual(file_path.read_bytes(), b"replacement after confirmation")

    def test_managed_training_root_is_never_exposed_as_deletable_bucket(self):
        cascade_manager = CascadingManager(self.engine)
        self.engine.cascade_manager = cascade_manager
        published_path, published_manifest = self._publish_active_expert(
            "blink-ui-reserved-bucket"
        )
        widget = BlinkLabWidget(self.engine, self.pm)
        bucket_names = [
            widget.expert_tree.topLevelItem(index).text(0)
            for index in range(widget.expert_tree.topLevelItemCount())
        ]

        self.assertNotIn(TRAINING_BUNDLE_DIRECTORY, bucket_names)
        self.assertIsNone(widget._selected_expert_bucket_info())
        self.assertFalse(widget.btn_delete_expert.isEnabled())
        with self.assertRaisesRegex(ValueError, "unsafe_expert_bucket"):
            widget._delete_expert_bucket_files(
                str(Path(self.engine.weights_dir) / "experts" / TRAINING_BUNDLE_DIRECTORY)
            )
        self.assertTrue(published_path.exists())
        self.assertTrue(published_manifest.exists())

    def test_bucket_delete_rejects_windows_reparse_directory_flag(self):
        file_path = self._create_expert_file(
            "Mandible",
            "expert_v20260501_090000.pth",
        )
        bucket_path = file_path.parent
        original_lstat = os.lstat

        def reparse_bucket(path):
            observed = original_lstat(path)
            if os.path.normcase(os.path.abspath(path)) != os.path.normcase(
                str(bucket_path)
            ):
                return observed
            return types.SimpleNamespace(
                st_mode=observed.st_mode,
                st_dev=observed.st_dev,
                st_ino=observed.st_ino,
                st_mtime_ns=observed.st_mtime_ns,
                st_file_attributes=0x400,
            )

        widget = BlinkLabWidget(self.engine, self.pm)
        with patch("ui.blink_lab.os.lstat", side_effect=reparse_bucket):
            self.assertFalse(widget._is_safe_expert_bucket_path(str(bucket_path)))
            with self.assertRaisesRegex(ValueError, "unsafe_expert_bucket"):
                widget._delete_expert_bucket_files(str(bucket_path))
        self.assertTrue(file_path.exists())

    def test_bucket_delete_rejects_unlisted_nested_directory(self):
        file_path = self._create_expert_file(
            "Mandible",
            "expert_v20260501_090000.pth",
        )
        nested_file = file_path.parent / "nested" / "unlisted.bin"
        nested_file.parent.mkdir()
        nested_file.write_bytes(b"must remain")
        widget = BlinkLabWidget(self.engine, self.pm)
        self._select_bucket_item(widget, "Mandible")

        with patch("ui.blink_lab.QMessageBox.critical") as critical, \
             patch.object(widget, "_show_bucket_delete_preview_dialog") as preview:
            widget.delete_expert_model()

        critical.assert_called_once()
        preview.assert_not_called()
        self.assertTrue(file_path.exists())
        self.assertTrue(nested_file.exists())

    def test_bucket_delete_rejects_change_after_preview(self):
        file_path = self._create_expert_file(
            "Mandible",
            "expert_v20260501_090000.pth",
            b"before preview",
        )
        widget = BlinkLabWidget(self.engine, self.pm)
        self._select_bucket_item(widget, "Mandible")

        def mutate_then_confirm(**_kwargs):
            file_path.write_bytes(b"changed after preview")
            return True, True, None

        with patch.object(
            widget,
            "_show_bucket_delete_preview_dialog",
            side_effect=mutate_then_confirm,
        ), patch.object(
            widget,
            "_show_bucket_delete_type_confirm_dialog",
            return_value=(True, None),
        ), patch("ui.blink_lab.QMessageBox.critical") as critical:
            widget.delete_expert_model()

        critical.assert_called_once()
        self.assertTrue(file_path.exists())
        self.assertEqual(file_path.read_bytes(), b"changed after preview")
        self.assertEqual(self.pm.route_cleanup_calls, [])

    def test_refresh_expert_registry_skips_unsafe_bucket_names(self):
        expert_root = Path(self.engine.weights_dir) / "experts"
        safe_bucket = expert_root / "Mandible"
        safe_bucket.mkdir(parents=True, exist_ok=True)
        (safe_bucket / "expert_v20260501_090000.pth").write_bytes(b"safe")
        unsafe_bucket = expert_root / "..bad"
        unsafe_bucket.mkdir(parents=True, exist_ok=True)
        (unsafe_bucket / "expert_v20260501_090000.pth").write_bytes(b"unsafe")

        widget = BlinkLabWidget(self.engine, self.pm)
        widget.refresh_expert_registry()

        names = [widget.expert_tree.topLevelItem(index).text(0) for index in range(widget.expert_tree.topLevelItemCount())]
        self.assertIn("Mandible", names)
        self.assertNotIn("..bad", names)

    def test_expert_registry_displays_editable_notes_without_renaming_files(self):
        file_path = self._create_expert_file("Mandible", "expert_v20260501_090000.pth")
        set_expert_note(self.engine.weights_dir, "Mandible/expert_v20260501_090000.pth", "side view stable")

        widget = BlinkLabWidget(self.engine, self.pm)
        item = self._select_model_item(widget, "Mandible", "side view stable (Mandible/expert_v20260501_090000.pth)")

        self.assertEqual(item.data(0, Qt.UserRole), str(file_path))
        self.assertEqual(item.data(0, Qt.UserRole + 2), "Mandible/expert_v20260501_090000.pth")
        self.assertIn("side view stable", item.text(0))
        self.assertTrue(file_path.exists())

    def test_edit_selected_expert_note_saves_sidecar_metadata(self):
        self._create_expert_file("Mandible", "expert_v20260501_090000.pth")
        widget = BlinkLabWidget(self.engine, self.pm)
        self._select_model_item_by_expert_id(widget, "Mandible", "Mandible/expert_v20260501_090000.pth")

        with patch("ui.blink_lab.QInputDialog.getText", return_value=("keep for dorsal view", True)):
            widget.edit_selected_expert_note()

        notes = load_expert_notes(self.engine.weights_dir)
        self.assertEqual(notes.get("Mandible/expert_v20260501_090000.pth"), "keep for dorsal view")
        self.assertIn("keep for dorsal view", widget.expert_tree.currentItem().text(0))


if __name__ == "__main__":
    unittest.main()
