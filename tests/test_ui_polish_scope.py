# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportOptionalCall=false, reportPossiblyUnboundVariable=false, reportUninitializedInstanceVariable=false, reportConstantRedefinition=false, reportArgumentType=false, reportCallIssue=false, reportIndexIssue=false

import os
import sys
import tempfile
import unittest
import copy
import json
from pathlib import Path
from unittest.mock import patch

import torch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

has_pyside6 = False

try:
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QApplication, QWidget, QGridLayout, QDialogButtonBox, QTreeWidget, QTableWidget, QLabel, QPushButton
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
        QColor = None
        QPointF = None
        QRectF = None
        QImage = None
        QPainter = None
        QTreeWidget = None
        QPushButton = None
        QWidget = object
        main_module = None
        BlinkLabWidget = None
        ImageCropper = None
        PdfProcessingWidget = None
    else:
        raise
else:
    import AntSleap.main as main_module
    import AntSleap.ui.main_window_annotation as annotation_module
    import AntSleap.ui.main_window_blink_workflow as blink_workflow_module
    import AntSleap.ui.main_window_image_navigation as image_navigation_module
    import AntSleap.ui.main_window_model_management as model_management_module
    import AntSleap.ui.main_window_part_tree as part_tree_module
    import AntSleap.ui.main_window_prediction as prediction_module
    import AntSleap.ui.main_window_vlm as vlm_module
    import AntSleap.ui.model_settings_dataset as model_settings_dataset_module
    import AntSleap.ui.route_management_panel as route_management_module
    from AntSleap.core.blink_dataset import BlinkTrajectoryDataset
    from AntSleap.core.blink_heatmap_dataset import BlinkHeatmapDataset
    from AntSleap.ui.blink_lab import BlinkExpertTrainingReportDialog, BlinkLabWidget
    from AntSleap.ui.cropper import ImageCropper
    from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget
    from AntSleap.ui.style import BUTTON_ROLE_COMMIT, BUTTON_ROLE_NEUTRAL, SCI_THEME, apply_semantic_button_style, build_theme_palette, get_theme_config, refresh_themed_buttons

    has_pyside6 = True


class DummyPartsModel:
    ultralytics_sam = None


class DummySignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)
        return None

    def emit(self, *args, **kwargs):
        for callback in list(self.callbacks):
            callback(*args, **kwargs)


class DummyThread:
    def __init__(self):
        self.started = DummySignal()
        self._running = False

    def start(self):
        self._running = True
        self.started.emit()

    def isRunning(self):
        return self._running

    def quit(self):
        self._running = False

    def wait(self, _timeout=None):
        return True


class DummyVlmPreannotationThread(DummyThread):
    instances = []

    def __init__(self, *args, **kwargs):
        super().__init__()
        type(self).instances.append(self)
        self.args = args
        self.kwargs = kwargs
        self.log_signal = DummySignal()
        self.image_result_signal = DummySignal()
        self.progress_signal = DummySignal()
        self.error_signal = DummySignal()
        self.finished_signal = DummySignal()


class DummySamWorker:
    last_instance = None

    def __init__(self, *args, **kwargs):
        type(self).last_instance = self
        self.model = None
        self.predict_point_calls = []
        self.predict_box_calls = []
        self.mask_generated = DummySignal()
        self.model_loaded = DummySignal()
        self.model_load_error = DummySignal()
        self.prompt_failed = DummySignal()

    def moveToThread(self, thread):
        self.thread = thread

    def load_model(self):
        self.model = object()
        self.model_loaded.emit()

    def reload_base_model(self):
        self.load_model()

    def load_decoder_weights(self, weights_path):
        self.decoder_weights = weights_path

    def set_epsilon(self, epsilon):
        self.poly_epsilon = epsilon

    def predict_point(self, image_path, x, y):
        self.predict_point_calls.append((image_path, x, y))

    def predict_box(self, image_path, x1, y1, x2, y2):
        self.predict_box_calls.append((image_path, x1, y1, x2, y2))


class DummyCascadeManager:
    def __init__(self, weights_dir=None):
        self.infer_calls = []
        self.infer_result = {"box": [18.0, 18.0, 42.0, 42.0], "confidence": 0.9}
        self.weights_dir = str(weights_dir or "")
        self.loaded_experts = {}

    def get_route_block_reason(self, route):
        if not isinstance(route, dict):
            return "route_missing"
        appointed = route.get("appointed_expert") if isinstance(route.get("appointed_expert"), dict) else route
        if not appointed.get("expert_id"):
            return "expert_unappointed"
        expert_part = appointed.get("expert_part") or route.get("expert_part") or route.get("child")
        expert_filename = appointed.get("expert_filename") or route.get("expert_filename")
        if not expert_part or not expert_filename:
            return "expert_unappointed"
        if not (Path(self.weights_dir) / "experts" / str(expert_part) / str(expert_filename)).exists():
            return "expert_model_missing"
        return None

    def list_available_experts(self):
        expert_root = Path(self.weights_dir) / "experts"
        if not expert_root.exists():
            return []
        experts = []
        for part_dir in sorted(path for path in expert_root.iterdir() if path.is_dir()):
            for model_path in sorted(part_dir.glob("*.pth")):
                expert_id = f"{part_dir.name}/{model_path.name}"
                experts.append(
                    {
                        "expert_part": part_dir.name,
                        "expert_filename": model_path.name,
                        "expert_id": expert_id,
                        "path": str(model_path),
                        "expert_backend": "vit_b_blink",
                    }
                )
        return experts

    def resolve_route_expert_path(self, route):
        expert_part = route.get("expert_part") or route.get("child")
        expert_filename = route.get("expert_filename")
        if not expert_part or not expert_filename:
            return None
        return str(Path(self.weights_dir) / "experts" / str(expert_part) / str(expert_filename))

    def infer_child_part(self, image_path, parent_box, child_part_name, parent_part="macro_locator", route_manifest=None):
        self.infer_calls.append(
            {
                "image_path": image_path,
                "parent_box": list(parent_box),
                "child_part_name": child_part_name,
                "parent_part": parent_part,
                "route_manifest": route_manifest,
            }
        )
        return dict(self.infer_result)


class DummyEngine:
    def __init__(self, weights_dir):
        self.weights_dir = weights_dir
        self.locator = None
        self.parts_model = DummyPartsModel()
        self.cascade_manager = DummyCascadeManager(weights_dir)
        self.current_num_classes = 3
        self.locator_resolution = (512, 512)
        self.loaded_locator_requires_legacy_confirmation = False
        self.loaded_locator_is_legacy_512 = False
        self.loaded_locator_timestamp = None
        self.load_locator_calls = []
        self.load_sam_decoder_calls = []
        self.reset_sam_calls = 0
        self.reset_locator_calls = 0
        self.predict_calls = []

    def ensure_locator_loaded(self):
        if self.locator is None:
            self.locator = object()
        return self.locator

    def load_locator(self, timestamp, checkpoint_path=None):
        self.ensure_locator_loaded()
        self.load_locator_calls.append(timestamp)
        return None

    def reset_locator_to_base(self):
        self.ensure_locator_loaded()
        self.reset_locator_calls += 1
        return None

    def reset_sam_to_base(self):
        self.reset_sam_calls += 1
        return None

    def load_sam_decoder(self, timestamp, checkpoint_path=None):
        self.load_sam_decoder_calls.append(timestamp)
        return None

    def rebuild_locator(self, num_classes, learning_rate, weight_decay):
        self.current_num_classes = num_classes

    def update_hyperparameters(self, learning_rate, weight_decay):
        return None

    def predict_full_pipeline(self, *args, **kwargs):
        self.predict_calls.append({"args": args, "kwargs": kwargs})
        return {
            "polygons": {},
            "auto_boxes": {},
            "scores": {},
            "meta": {
                "cascade_route_source": "project",
                "cascade_attempted_routes": [],
                "cascade_applied_routes": [],
                "cascade_block_reasons": {},
            },
        }

    def predict_base_sam_polygon(self, image_input, prompt_box, poly_epsilon=2.0):
        x1, y1, x2, y2 = [float(value) for value in prompt_box]
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

    def ensure_parts_model_loaded(self):
        return self.parts_model

    def set_device_preference(self, preference):
        self.device_preference = preference
        return False


class DummyProjectManager:
    def __init__(self, project_root):
        self.current_project_path = str(Path(project_root) / "dummy_project.json")
        self.current_database_path = str(Path(project_root) / "dummy_project.sqlite")
        self._is_sqlite_project = False
        self.save_calls = 0
        self.project_data = {
            "taxonomy": ["Head", "Mesosoma", "Gaster"],
            "images": [],
            "labels": {},
            "image_provenance": {},
            "blink_context_roi_parents": {},
            "parent_box_aspect_ratios": {"Head": 1.0, "Mesosoma": 4 / 3, "Gaster": 4 / 3},
            "cascade_routes": {"version": "project-v2", "routes": []},
        }

    def create_project(self, name, directory, **kwargs):
        self.current_project_path = str(Path(directory) / f"{name}.json")
        self.project_data["images"] = []
        self.project_data["labels"] = {}

    def load_project(self, path):
        self.current_project_path = str(path)

    def is_sqlite_project(self):
        return bool(self._is_sqlite_project)

    def integrity_registry_state(self):
        return {"status": "ready"}

    def set_known_relocated_roots(self, roots):
        self.known_relocated_roots = list(roots or [])

    def save_project(self):
        self.save_calls += 1
        return None

    def _ensure_label_entry(self, image_path):
        return self.project_data["labels"].setdefault(
            image_path,
            {
                "parts": {},
                "boxes": {},
                "auto_boxes": {},
                "auto_box_meta": {},
                "descriptions": {},
                "description_sources": {},
                "status": "unlabeled",
                "genus": "Unknown",
            },
        )

    def get_locator_scope(self):
        taxonomy = list(self.project_data.get("taxonomy", []))
        return list(self.project_data.get("locator_scope", taxonomy))

    def set_locator_scope(self, locator_scope, save=True):
        taxonomy = list(self.project_data.get("taxonomy", []))
        clean_scope = [part for part in locator_scope if part in taxonomy]
        if not clean_scope and taxonomy:
            clean_scope = [taxonomy[0]]
        self.project_data["locator_scope"] = clean_scope
        if save:
            self.save_project()
        return clean_scope

    def get_labels(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("parts", {})

    def get_boxes(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("boxes", {})

    def get_auto_boxes(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("auto_boxes", {})

    def set_image_provenance(self, image_path, provenance, save=True):
        self.project_data.setdefault("image_provenance", {})[str(image_path)] = dict(provenance or {})
        if save:
            self.save_project()
        return None

    def get_image_provenance(self, image_path):
        return dict(self.project_data.get("image_provenance", {}).get(str(image_path), {}))

    def summarize_image_ai_drafts(self, image_path):
        entry = self.project_data["labels"].get(image_path, {})
        parts = entry.get("parts", {}) if isinstance(entry.get("parts", {}), dict) else {}
        auto_boxes = entry.get("auto_boxes", {}) if isinstance(entry.get("auto_boxes", {}), dict) else {}
        descriptions = entry.get("descriptions", {}) if isinstance(entry.get("descriptions", {}), dict) else {}
        reviewable = []
        box_only = []
        for part_name, desc in descriptions.items():
            if desc != "Auto-Annotated":
                continue
            if parts.get(part_name):
                reviewable.append(part_name)
            elif part_name in auto_boxes:
                box_only.append(part_name)
        return {"reviewable_polygon_parts": reviewable, "box_only_parts": box_only}

    def summarize_ai_drafts_for_images(self, image_paths):
        image_summaries = []
        reviewable_count = 0
        box_only_count = 0
        for image_path in image_paths or []:
            summary = self.summarize_image_ai_drafts(image_path)
            image_reviewable = len(summary["reviewable_polygon_parts"])
            image_box_only = len(summary["box_only_parts"])
            if image_reviewable or image_box_only:
                item = dict(summary)
                item["image_path"] = image_path
                item["reviewable_count"] = image_reviewable
                item["box_only_count"] = image_box_only
                image_summaries.append(item)
                reviewable_count += image_reviewable
                box_only_count += image_box_only
        return {
            "images_with_drafts": image_summaries,
            "image_count": len(image_summaries),
            "reviewable_polygon_count": reviewable_count,
            "box_only_count": box_only_count,
        }

    def set_auto_box_review_status(self, image_path, part_name, review_status, save=True):
        entry = self.project_data["labels"].get(image_path)
        if not entry or part_name not in entry.get("auto_boxes", {}):
            return False
        entry.setdefault("auto_box_meta", {}).setdefault(part_name, {})["review_status"] = review_status
        if save:
            self.save_project()
        return True

    def verify_image_labels(self, image_path, save=True):
        labels = self.project_data["labels"].get(image_path)
        if not labels:
            return 0
        parts = labels.get("parts", {}) if isinstance(labels.get("parts", {}), dict) else {}
        descriptions = labels.get("descriptions", {}) if isinstance(labels.get("descriptions", {}), dict) else {}
        count = 0
        for part_name in list(descriptions.keys()):
            if descriptions.get(part_name) == "Auto-Annotated" and parts.get(part_name):
                descriptions.pop(part_name, None)
                self.set_auto_box_review_status(image_path, part_name, "confirmed", save=False)
                count += 1
        if count and save:
            self.save_project()
        return count

    def verify_ai_drafts_for_images(self, image_paths):
        accepted_count = 0
        accepted_images = 0
        for image_path in image_paths or []:
            count = self.verify_image_labels(image_path, save=False)
            if count:
                accepted_count += count
                accepted_images += 1
        if accepted_count:
            self.save_project()
        return {"accepted_count": accepted_count, "accepted_images": accepted_images}

    def get_blink_context_parent(self, target_part):
        return self.project_data.get("blink_context_roi_parents", {}).get(target_part)

    def get_blink_context_roi_parents(self):
        return dict(self.project_data.get("blink_context_roi_parents", {}))

    def remember_blink_context_parent(self, target_part, parent_part, save=True):
        self.project_data.setdefault("blink_context_roi_parents", {})[target_part] = parent_part
        if save:
            self.save_project()
        return True

    def clear_blink_context_parent(self, target_part, save=True):
        removed = target_part in self.project_data.get("blink_context_roi_parents", {})
        self.project_data.get("blink_context_roi_parents", {}).pop(target_part, None)
        if removed and save:
            self.save_project()
        return removed

    def get_parent_box_aspect_ratios(self):
        return dict(self.project_data.get("parent_box_aspect_ratios", {}))

    def get_active_model_profile(self):
        return dict(self.project_data.get("active_model_profile", {}))

    def get_cascade_route(self, parent_part, child_part):
        for route in self.project_data.get("cascade_routes", {}).get("routes", []):
            if route.get("parent") == parent_part and route.get("child") == child_part:
                return dict(route)
        return None

    def register_cascade_route_candidate(self, parent_part, child_part, **kwargs):
        existing = self.get_cascade_route(parent_part, child_part) or {}
        route = {
            "parent": parent_part,
            "child": child_part,
            "enabled": bool(existing.get("enabled", False)),
            "appointed_expert": dict(existing.get("appointed_expert") or {}),
            "expert_candidates": [dict(candidate) for candidate in existing.get("expert_candidates", []) if isinstance(candidate, dict)],
            "expert_id": existing.get("expert_id"),
            "expert_part": existing.get("expert_part"),
            "expert_filename": existing.get("expert_filename"),
            "registration_source": kwargs.get("registration_source", existing.get("registration_source", "blink_candidate")),
            "focus_source": kwargs.get("focus_source", existing.get("focus_source")),
        }
        routes = [
            dict(item)
            for item in self.project_data.setdefault("cascade_routes", {"version": "project-v2", "routes": []}).get("routes", [])
            if not (item.get("parent") == parent_part and item.get("child") == child_part)
        ]
        routes.append(route)
        self.project_data["cascade_routes"]["routes"] = routes
        if kwargs.get("save", True):
            self.save_project()
        return route

    def get_shrink_loose_boxes(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("shrink_loose_boxes", {})

    def update_shrink_loose_box(self, image_path, part_name, box, save=True):
        entry = self._ensure_label_entry(image_path)
        entry.setdefault("shrink_loose_boxes", {})[part_name] = [float(value) for value in box]
        if save:
            self.save_project()
        return True

    def get_genus(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("genus", "Unknown")

    def get_taxon(self, image_path):
        entry = self.project_data["labels"].get(image_path, {})
        return entry.get("taxon") or entry.get("genus", "Unknown")

    def set_part_description(self, image_path, part_name, description_text, source_meta=None, save=True):
        entry = self._ensure_label_entry(image_path)
        text = str(description_text or "").strip()
        if text:
            entry.setdefault("descriptions", {})[part_name] = text
        else:
            entry.setdefault("descriptions", {}).pop(part_name, None)
        if source_meta is not None:
            if source_meta:
                entry.setdefault("description_sources", {})[part_name] = dict(source_meta)
            else:
                entry.setdefault("description_sources", {}).pop(part_name, None)
        if save:
            self.save_project()
        return None

    def get_part_description(self, image_path, part_name):
        return self.project_data["labels"].get(image_path, {}).get("descriptions", {}).get(part_name, "")

    def get_description_source(self, image_path, part_name):
        return dict(self.project_data["labels"].get(image_path, {}).get("description_sources", {}).get(part_name, {}))

    def set_genus(self, image_path, genus_name, save=True):
        self.set_taxon(image_path, genus_name, save=save)
        return None

    def set_taxon(self, image_path, taxon_name, save=True):
        entry = self._ensure_label_entry(image_path)
        clean_taxon = str(taxon_name or "Unknown").strip() or "Unknown"
        entry["taxon"] = clean_taxon
        entry["genus"] = clean_taxon
        if save:
            self.save_project()
        return None

    def update_label(
        self,
        image_path,
        part_name,
        points,
        description_text=None,
        box=None,
        auto_box=None,
        save=True,
        *,
        training_source=None,
        training_review_status=None,
        training_accepted_via=None,
        preserve_training_truth=False,
    ):
        entry = self._ensure_label_entry(image_path)
        entry["parts"][part_name] = [[float(pt[0]), float(pt[1])] for pt in points]
        entry["status"] = "labeled"
        if box:
            entry["boxes"][part_name] = [float(v) for v in box]
            entry["auto_boxes"].pop(part_name, None)
            entry.get("auto_box_meta", {}).pop(part_name, None)
        if auto_box:
            entry["auto_boxes"][part_name] = [float(v) for v in auto_box]
        if description_text:
            entry["descriptions"][part_name] = description_text
        elif not auto_box and entry.get("descriptions", {}).get(part_name) == "Auto-Annotated":
            entry["descriptions"].pop(part_name, None)
        if save:
            self.save_project()
        return None

    def update_auto_box(self, image_path, part_name, box, description_text=None, source_meta=None, save=True):
        entry = self._ensure_label_entry(image_path)
        entry.setdefault("auto_boxes", {})[part_name] = [float(v) for v in box]
        if description_text:
            entry.setdefault("descriptions", {})[part_name] = description_text
        if source_meta:
            entry.setdefault("auto_box_meta", {})[part_name] = dict(source_meta)
        if save:
            self.save_project()
        return True

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

    def remove_auto_labels_for_images(self, image_paths, save=True):
        removed = 0
        for image_path in image_paths or []:
            entry = self.project_data.get("labels", {}).get(image_path)
            if not isinstance(entry, dict):
                continue
            descriptions = entry.get("descriptions", {}) if isinstance(entry.get("descriptions", {}), dict) else {}
            parts_to_remove = [part for part, desc in list(descriptions.items()) if desc == "Auto-Annotated"]
            for part in parts_to_remove:
                entry.get("parts", {}).pop(part, None)
                entry.get("descriptions", {}).pop(part, None)
                entry.get("description_sources", {}).pop(part, None)
                entry.get("auto_boxes", {}).pop(part, None)
                entry.get("auto_box_meta", {}).pop(part, None)
                removed += 1
            if not entry.get("parts"):
                entry["status"] = "unlabeled"
        if save:
            self.save_project()
        return removed

    def remove_auto_labels(self, save=True):
        return self.remove_auto_labels_for_images(self.project_data.get("labels", {}).keys(), save=save)

    def delete_label(self, image_path, part_name, save=True):
        entry = self.project_data["labels"].get(image_path)
        if entry is None:
            return None

        entry.get("parts", {}).pop(part_name, None)
        entry.get("descriptions", {}).pop(part_name, None)
        entry.get("boxes", {}).pop(part_name, None)
        entry.get("auto_boxes", {}).pop(part_name, None)
        if not entry.get("parts"):
            entry["status"] = "unlabeled"
        if save:
            self.save_project()
        return None

    def remove_image(self, image_path, save=True):
        return bool(self.remove_images([image_path], save=save))

    def remove_images(self, image_paths, progress_callback=None, save=True):
        paths = [str(path) for path in (image_paths or []) if path]
        total = len(paths)
        if progress_callback:
            progress_callback(0, total, "")
        remove_set = set(paths)
        old_images = list(self.project_data.get("images", []))
        self.project_data["images"] = [path for path in old_images if path not in remove_set]
        removed = len(old_images) - len(self.project_data["images"])
        for path in paths:
            self.project_data.get("labels", {}).pop(path, None)
            self.project_data.get("image_provenance", {}).pop(path, None)
        if progress_callback:
            for index, path in enumerate(paths, start=1):
                progress_callback(index, total, path)
        if save:
            self.save_project()
        return removed

    def update_trajectory(self, image_path, part_name, trajectory, parent_context=None, save=True):
        entry = self._ensure_label_entry(image_path)
        entry.setdefault("trajectories", {})[part_name] = {"frames": list(trajectory or [])}
        if parent_context:
            entry["trajectories"][part_name]["parent_context"] = dict(parent_context)
        if save:
            self.save_project()
        return None

    def summarize_blink_trajectory_datasets(self):
        summaries = {}
        for image_path, entry in self.project_data.get("labels", {}).items():
            trajectories = entry.get("trajectories", {}) if isinstance(entry.get("trajectories", {}), dict) else {}
            for child_part, payload in trajectories.items():
                frames = payload.get("frames", []) if isinstance(payload, dict) else []
                parent_context = payload.get("parent_context", {}) if isinstance(payload, dict) else {}
                parent_part = str(parent_context.get("parent_part") or "Unknown parent")
                key = (parent_part, child_part)
                item = summaries.setdefault(
                    key,
                    {"parent_part": parent_part, "child_part": child_part, "image_count": 0, "frame_count": 0, "sources": set(), "images": []},
                )
                item["image_count"] += 1
                item["frame_count"] += len(frames)
                source = str(parent_context.get("source") or "unknown")
                item["sources"].add(source)
                item["images"].append(
                    {
                        "image_path": image_path,
                        "frame_count": len(frames),
                        "source": source,
                        "parent_box": parent_context.get("parent_box"),
                    }
                )
        result = []
        for item in summaries.values():
            clean = dict(item)
            clean["sources"] = sorted(clean["sources"])
            result.append(clean)
        return sorted(result, key=lambda item: (item["parent_part"], item["child_part"]))

    def delete_blink_trajectory_dataset(self, parent_part, child_part, save=True):
        removed = 0
        for entry in self.project_data.get("labels", {}).values():
            trajectories = entry.get("trajectories", {}) if isinstance(entry.get("trajectories", {}), dict) else {}
            payload = trajectories.get(child_part)
            parent_context = payload.get("parent_context", {}) if isinstance(payload, dict) else {}
            stored_parent = str(parent_context.get("parent_part") or "Unknown parent")
            if payload is not None and stored_parent == parent_part:
                del trajectories[child_part]
                removed += 1
        if save and removed:
            self.save_project()
        return removed

    def iter_cascade_routes(self):
        return [dict(route) for route in self.project_data.get("cascade_routes", {}).get("routes", [])]

    def get_cascade_routes(self):
        manifest = self.project_data.get("cascade_routes", {"version": "project-v2", "routes": []})
        return {
            "version": manifest.get("version", "project-v2"),
            "routes": [dict(route) for route in manifest.get("routes", [])],
        }

    def appoint_cascade_route_expert(self, parent_part, child_part, expert_id=None, save=True, **kwargs):
        routes = []
        updated = None
        for route in self.project_data.setdefault("cascade_routes", {"version": "project-v2", "routes": []}).get("routes", []):
            candidate = dict(route)
            if candidate.get("parent") == parent_part and candidate.get("child") == child_part:
                appointed = {
                    "expert_id": expert_id,
                    "expert_part": None,
                    "expert_filename": None,
                }
                if isinstance(expert_id, str) and "/" in expert_id:
                    expert_part, expert_filename = expert_id.split("/", 1)
                    appointed = {
                        "expert_id": expert_id,
                        "expert_part": expert_part,
                        "expert_filename": expert_filename,
                    }
                    candidate["expert_part"] = expert_part
                    candidate["expert_filename"] = expert_filename
                candidate["appointed_expert"] = appointed
                candidate["expert_id"] = expert_id
                existing_candidates = [
                    dict(item)
                    for item in candidate.get("expert_candidates", [])
                    if isinstance(item, dict)
                ]
                candidate["expert_candidates"] = ([dict(appointed)] if expert_id else []) + [
                    item for item in existing_candidates if item.get("expert_id") != expert_id
                ]
                updated = dict(candidate)
            routes.append(candidate)
        self.project_data["cascade_routes"]["routes"] = routes
        if save:
            self.save_project()
        return updated

    def set_cascade_route_enabled(self, parent_part, child_part, enabled, save=True):
        routes = []
        updated = None
        for route in self.project_data.setdefault("cascade_routes", {"version": "project-v2", "routes": []}).get("routes", []):
            candidate = dict(route)
            if candidate.get("parent") == parent_part and candidate.get("child") == child_part:
                candidate["enabled"] = bool(enabled)
                updated = dict(candidate)
            routes.append(candidate)
        self.project_data["cascade_routes"]["routes"] = routes
        if save:
            self.save_project()
        return updated

    def update_active_model_profile_parent_weights(self, locator_weights=None, segmenter_weights=None, save=True):
        self.last_profile_parent_weights = {
            "locator_weights": locator_weights,
            "segmenter_weights": segmenter_weights,
            "save": save,
        }
        if save:
            self.save_project()
        return self.last_profile_parent_weights

    def delete_cascade_route(self, parent_part, child_part, save=True):
        original = self.project_data.setdefault("cascade_routes", {"version": "project-v2", "routes": []}).get("routes", [])
        routes = [
            dict(route)
            for route in original
            if not (route.get("parent") == parent_part and route.get("child") == child_part)
        ]
        removed = len(routes) != len(original)
        self.project_data["cascade_routes"]["routes"] = routes
        if removed and save:
            self.save_project()
        return removed

    def remove_cascade_route_expert_references(self, expert_id, save=True):
        clean_expert_id = str(expert_id or "").strip()
        if not clean_expert_id:
            return 0
        changed_count = 0
        routes = []
        for route in self.project_data.setdefault("cascade_routes", {"version": "project-v2", "routes": []}).get("routes", []):
            candidate = dict(route)
            changed = False
            appointed = candidate.get("appointed_expert") if isinstance(candidate.get("appointed_expert"), dict) else {}
            if appointed.get("expert_id") == clean_expert_id or candidate.get("expert_id") == clean_expert_id:
                candidate["appointed_expert"] = {"expert_id": None, "expert_part": None, "expert_filename": None}
                candidate["expert_id"] = None
                candidate["expert_part"] = None
                candidate["expert_filename"] = None
                changed = True
            candidates = [
                dict(item)
                for item in candidate.get("expert_candidates", [])
                if isinstance(item, dict)
            ]
            kept = [item for item in candidates if item.get("expert_id") != clean_expert_id]
            if len(kept) != len(candidates):
                changed = True
            candidate["expert_candidates"] = kept
            if changed:
                changed_count += 1
            routes.append(candidate)
        self.project_data["cascade_routes"]["routes"] = routes
        if changed_count and save:
            self.save_project()
        return changed_count

    def remove_taxonomy_part(self, part_name, save=True):
        if part_name not in self.project_data.get("taxonomy", []):
            return False
        self.project_data["taxonomy"].remove(part_name)
        self.project_data["locator_scope"] = [
            part for part in self.project_data.get("locator_scope", []) if part != part_name
        ]
        self.project_data["cascade_routes"]["routes"] = [
            dict(route)
            for route in self.project_data.get("cascade_routes", {}).get("routes", [])
            if route.get("parent") != part_name and route.get("child") != part_name
        ]
        if save:
            self.save_project()
        return True

    def rename_taxonomy_part(self, old_part_name, new_part_name, save=True):
        old_part = str(old_part_name or "").strip()
        new_part = str(new_part_name or "").strip()
        taxonomy = self.project_data.get("taxonomy", [])
        if not old_part or not new_part or old_part not in taxonomy or new_part in taxonomy:
            return False
        self.project_data["taxonomy"] = [new_part if part == old_part else part for part in taxonomy]
        self.project_data["locator_scope"] = [
            new_part if part == old_part else part
            for part in self.project_data.get("locator_scope", [])
        ]
        parent_map = self.project_data.get("blink_context_roi_parents", {})
        self.project_data["blink_context_roi_parents"] = {
            (new_part if target == old_part else target): (new_part if parent == old_part else parent)
            for target, parent in parent_map.items()
        }
        for entry in self.project_data.get("labels", {}).values():
            for key in ("parts", "boxes", "auto_boxes", "auto_box_meta", "descriptions", "shrink_loose_boxes", "trajectories"):
                bucket = entry.get(key)
                if isinstance(bucket, dict) and old_part in bucket:
                    bucket[new_part] = bucket.pop(old_part)
        if save:
            self.save_project()
        return True


class DummyConfigManager:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def save(self):
        return None


class DummyDatabase:
    def query_trait_description(self, genus_name, part_name):
        return ""


@unittest.skipUnless(has_pyside6, "PySide6 is required for UI polish scope tests")
class UiPolishScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_scientific_theme_exposes_comfort_selectors(self):
        for selector in (
            "QRadioButton::indicator",
            "QCheckBox::indicator",
            "QTreeWidget, QTreeView",
            "QScrollArea#workbenchInspectorScroll",
            "QWidget#workbenchInspectorPanel",
            "QAbstractScrollArea, QAbstractItemView",
            "QStatusBar",
        ):
            self.assertIn(selector, SCI_THEME)
        self.assertIn("qlineargradient", SCI_THEME)
        self.assertNotIn("%BG_GRADIENT%", SCI_THEME)

    def test_dark_theme_palette_covers_linux_native_backgrounds(self):
        palette = build_theme_palette("dark")
        self.assertEqual(palette.window().color().name().upper(), "#070D1A")
        self.assertEqual(palette.base().color().name().upper(), "#101A2B")
        self.assertEqual(palette.button().color().name().upper(), "#101A2B")

    def test_light_theme_palette_covers_linux_native_backgrounds(self):
        palette = build_theme_palette("light")
        self.assertEqual(palette.window().color().name().upper(), "#F5F8FC")
        self.assertEqual(palette.base().color().name().upper(), "#FFFFFF")
        self.assertEqual(palette.button().color().name().upper(), "#FFFFFF")

    def test_scientific_theme_strengthens_generic_checked_indicators_without_touching_chip_radios(self):
        self.assertIn("QRadioButton::indicator:checked", SCI_THEME)
        self.assertIn("border: 2px solid #6F8FB8", SCI_THEME)
        self.assertIn("QCheckBox::indicator:checked", SCI_THEME)
        self.assertIn("background-color: #6F8FB8", SCI_THEME)
        self.assertIn("QRadioButton#toolChip::indicator", SCI_THEME)
        self.assertIn("QRadioButton#scaleToolRadio::indicator", SCI_THEME)

    def test_themed_buttons_refresh_when_switching_to_light_mode(self):
        owner = QWidget()
        owner.current_theme = "dark"
        neutral = QPushButton("Neutral", owner)
        commit = QPushButton("Commit", owner)
        apply_semantic_button_style(neutral, BUTTON_ROLE_NEUTRAL)
        apply_semantic_button_style(commit, BUTTON_ROLE_COMMIT)
        self.assertIn("qlineargradient", neutral.styleSheet())
        self.assertIn("qlineargradient", commit.styleSheet())

        owner.current_theme = "light"
        refresh_themed_buttons(owner, "light")

        self.assertIn("background-color: #FDFEFF", neutral.styleSheet())
        self.assertIn("background-color: #0EA5E9", commit.styleSheet())
        self.assertNotIn("qlineargradient", neutral.styleSheet())
        owner.close()

    def test_dialog_button_box_theme_helper_produces_button_like_controls(self):
        preflight = {
            "locator_image_count": 1,
            "parts_image_count": 1,
            "selected_locator_size": (960, 640),
            "mixed_native_resolutions": False,
            "locator_size_summary": "960x640 (1)",
            "locator_train_data": [1],
            "locator_val_data": [1],
            "parts_train_data": [1],
            "parts_val_data": [1],
            "locator_part_counts": {"Head": 1},
            "locator_train_part_counts": {"Head": 1},
            "locator_val_part_counts": {"Head": 1},
            "parts_part_counts": {"Head": 1},
            "parts_train_part_counts": {"Head": 1},
            "parts_val_part_counts": {"Head": 1},
            "locator_scope": ["Head"],
            "taxonomy": ["Head"],
            "warnings": [],
        }

        owner = QWidget()
        owner.current_theme = "light"
        preflight_dialog = main_module.TrainingPreflightDialog(preflight, parent=owner, lang="en")
        entry_dialog = main_module.BlinkEntryDialog(
            "sample.png",
            ["Head", "Mandible"],
            "Mandible",
            [{"part": "Head", "source": "manual", "box": [1, 2, 3, 4]}],
            parent=owner,
            lang="en",
        )

        for dialog in (preflight_dialog, entry_dialog):
            buttons = dialog.findChild(QDialogButtonBox)
            self.assertIsNotNone(buttons)
            ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
            cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
            self.assertIn("min-width: 104px", ok_button.styleSheet())
            self.assertIn("min-height: 36px", ok_button.styleSheet())
            self.assertIn("font-weight: 700", ok_button.styleSheet())
            self.assertIn("background-color: #0EA5E9", ok_button.styleSheet())
            self.assertIn("background-color: #F8FBFE", cancel_button.styleSheet())

        preflight_dialog.close()
        entry_dialog.close()
        owner.close()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.weights_dir = Path(self.temp_dir.name) / "weights"
        (self.weights_dir / "experts").mkdir(parents=True, exist_ok=True)
        self.engine = DummyEngine(str(self.weights_dir))
        self.project_manager = DummyProjectManager(self.temp_dir.name)
        self._runtime_patchers = [
            patch.object(annotation_module, "SAMWorker", DummySamWorker),
            patch.object(annotation_module, "QThread", DummyThread),
        ]
        for patcher in self._runtime_patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(getattr(self, "_runtime_patchers", [])):
            patcher.stop()
        self.temp_dir.cleanup()

    def make_main_window(self):
        def project_factory():
            return self.project_manager

        def engine_factory(*args, **kwargs):
            return self.engine

        with patch.object(main_module, "ConfigManager", DummyConfigManager), \
             patch.object(main_module, "ProjectManager", project_factory), \
             patch.object(main_module, "MultiModalDB", DummyDatabase), \
             patch.object(main_module, "AntEngine", engine_factory), \
             patch.object(annotation_module, "SAMWorker", DummySamWorker), \
             patch.object(annotation_module, "QThread", DummyThread), \
             patch.object(PdfProcessingWidget, "load_api_settings", lambda self: None), \
             patch.object(PdfProcessingWidget, "refresh_profile_list", lambda self: None), \
             patch.object(PdfProcessingWidget, "sync_runtime_controls_from_config", lambda self: None), \
             patch.object(main_module.QTimer, "singleShot", lambda *args, **kwargs: None):
            return main_module.MainWindow()

    def test_pdf_processing_widget_exposes_polish_panels(self):
        with patch.object(PdfProcessingWidget, "load_api_settings", lambda self: None), \
             patch.object(PdfProcessingWidget, "refresh_profile_list", lambda self: None), \
             patch.object(PdfProcessingWidget, "sync_runtime_controls_from_config", lambda self: None):
            widget = PdfProcessingWidget("en")

        self.assertIsNotNone(widget.findChild(QWidget, "pdfSettingsPanel"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfWorkbenchHeader"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfStartCenterButton"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfAskAgentButton"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfToggleAdvancedButton"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfApiPanel"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfProfilePanel"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfClassifyInputPanel"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfClassifyRuntimePanel"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfClassifyActionPanel"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfExtractInputPanel"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfExtractActionPanel"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfUtilityPanel"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfFeedbackPanel"))
        self.assertIsNotNone(widget.findChild(QWidget, "pdfPopplerStatus"))
        self.assertEqual(widget.btn_run_classify.parentWidget().objectName(), "pdfClassifyActionPanel")
        self.assertEqual(widget.btn_run_extract.parentWidget().objectName(), "pdfExtractActionPanel")
        self.assertEqual(widget.log_area.parentWidget().objectName(), "pdfFeedbackPanel")
        self.assertEqual(widget.workbench_header.parentWidget(), widget)
        outer_layout = widget.layout()
        self.assertLess(outer_layout.indexOf(widget.workbench_header), outer_layout.indexOf(widget.main_scroll))
        self.assertTrue(widget.config_group.isHidden())
        widget.toggle_advanced_config(True)
        self.assertFalse(widget.config_group.isHidden())

    def test_pdf_processing_api_inputs_keep_usable_height_when_resized(self):
        with patch.object(PdfProcessingWidget, "load_api_settings", lambda self: None), \
             patch.object(PdfProcessingWidget, "refresh_profile_list", lambda self: None), \
             patch.object(PdfProcessingWidget, "sync_runtime_controls_from_config", lambda self: None):
            widget = PdfProcessingWidget("zh")

        try:
            widget.toggle_advanced_config(True)
            for width, height in [(1180, 760), (1920, 1080), (900, 560)]:
                widget.resize(width, height)
                widget.show()
                self.app.processEvents()
                for control in (
                    widget.edit_api_key,
                    widget.edit_base_url,
                    widget.edit_model,
                    widget.edit_mllm_api_key,
                    widget.edit_mllm_base_url,
                    widget.edit_mllm_model,
                    widget.combo_api_protocol,
                    widget.combo_mllm_api_protocol,
                    widget.combo_mllm_image_detail,
                ):
                    self.assertGreaterEqual(control.height(), 24)
                    self.assertTrue(control.isVisible())
            self.assertLessEqual(widget.minimumHeight(), 120)
        finally:
            widget.close()
            widget.deleteLater()

    def test_blink_lab_exposes_session_action_and_training_panels(self):
        widget = BlinkLabWidget(self.engine, self.project_manager, lang="en")

        self.assertIsNotNone(widget.findChild(QWidget, "blinkSidebarPanel"))
        self.assertIsNotNone(widget.findChild(QWidget, "blinkCanvasShell"))
        self.assertIsNotNone(widget.findChild(QWidget, "blinkSessionPanel"))
        self.assertIsNotNone(widget.findChild(QWidget, "blinkActionPanel"))
        self.assertIsNotNone(widget.findChild(QWidget, "blinkTrainingPanel"))
        self.assertEqual(widget.lbl_status.parentWidget().objectName(), "blinkSessionPanel")
        self.assertEqual(widget.btn_apply_global.parentWidget().objectName(), "blinkActionPanel")
        self.assertEqual(widget.btn_train_expert.parentWidget().objectName(), "blinkTrainingPanel")
        self.assertEqual(widget.blink_splitter.handleWidth(), 8)
        self.assertGreaterEqual(widget.btn_auto_annotate.minimumHeight(), 44)
        self.assertGreaterEqual(widget.btn_apply_global.minimumHeight(), 54)
        self.assertGreaterEqual(widget.btn_train_expert.minimumHeight(), 54)
        self.assertLess(widget.canvas.blink_alpha, 245)
        self.assertGreaterEqual(widget.canvas.blink_alpha, 160)
        self.assertLessEqual(widget.canvas.blink_alpha, 220)
        widget.close()

    def test_blink_training_report_matches_parent_dataset_browsing(self):
        report_dir = Path(self.temp_dir.name) / "blink_report"
        details_dir = report_dir / "val_details"
        details_dir.mkdir(parents=True, exist_ok=True)
        image = QImage(120, 80, QImage.Format_RGB32)
        image.fill(QColor("#223344"))
        detail_path = details_dir / "blink_val_0000.png"
        self.assertTrue(image.save(str(detail_path)))
        report = {
            "dir": str(report_dir),
            "details_dir": str(details_dir),
            "validation_rows": [
                {
                    "sample_id": "blink_0000",
                    "image_name": "blink_val_0000.png",
                    "detail_image": "blink_val_0000.png",
                    "provenance": "blink_expert",
                    "valid_parts": "Mandible",
                    "peak_summary": "IoU 0.800",
                    "error_summary": "center 2.0px",
                }
            ],
            "validation_summary": {
                "kind": "blink_expert_report",
                "part_name": "Mandible",
                "parent_part": "Head",
                "validation_count": 1,
            },
        }

        dialog = BlinkExpertTrainingReportDialog(report, lang="en")
        try:
            table = dialog.findChild(QTableWidget, "blinkTrainingValidationTable")
            preview = dialog.findChild(QLabel, "blinkTrainingValidationPreview")
            self.assertIsNotNone(table)
            self.assertIsNotNone(preview)
            self.assertEqual(table.rowCount(), 1)
            self.assertEqual(table.item(0, 0).text(), "blink_0000")
            self.assertEqual(table.item(0, 3).text(), "Mandible")
            table.setCurrentCell(0, 0)
            self.app.processEvents()
            self.assertIsNotNone(preview.pixmap())
            self.assertFalse(preview.pixmap().isNull())
        finally:
            dialog.close()

    def test_cropper_exposes_load_draw_export_flow_panels(self):
        dialog = ImageCropper(lang="en")

        self.assertIsNotNone(dialog.findChild(QWidget, "cropperFlowPanel"))
        self.assertIsNotNone(dialog.findChild(QWidget, "cropperLoadPanel"))
        self.assertIsNotNone(dialog.findChild(QWidget, "cropperDrawPanel"))
        self.assertIsNotNone(dialog.findChild(QWidget, "cropperExportPanel"))
        self.assertIsNotNone(dialog.findChild(QWidget, "cropperCanvasShell"))
        self.assertEqual(dialog.btn_load.parentWidget().objectName(), "cropperLoadPanel")
        self.assertEqual(dialog.btn_save.parentWidget().objectName(), "cropperExportPanel")
        self.assertEqual(dialog.crop_list.parentWidget().objectName(), "cropperDrawPanel")
        self.assertEqual(dialog.btn_auto_split.parentWidget().objectName(), "cropperDrawPanel")
        self.assertEqual(dialog.btn_delete_selected.parentWidget().objectName(), "cropperDrawPanel")
        self.assertEqual(dialog.btn_clear_crops.parentWidget().objectName(), "cropperDrawPanel")

    def test_cropper_exports_traceable_crop_records(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "paper__accepted_000007__figure.jpg"
            image = QImage(160, 120, QImage.Format_RGB32)
            image.fill(0xEDEAE4)
            self.assertTrue(image.save(str(source)))

            dialog = ImageCropper(initial_image=str(source), lang="en")
            try:
                dialog.canvas.crops = [QRectF(10, 20, 70, 80)]
                with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):
                    dialog.save_crops()

                files = dialog.get_files()
                records = dialog.get_crop_records()
                self.assertEqual(len(files), 1)
                self.assertEqual(Path(files[0]).name, "paper__accepted_000007__figure__crop_001.jpg")
                self.assertTrue(Path(files[0]).exists())
                self.assertEqual(records[0]["path"], files[0])
                self.assertEqual(os.path.normcase(records[0]["source_image"]), os.path.normcase(str(source.resolve())))
                self.assertEqual(records[0]["crop_index"], 1)
                self.assertEqual(records[0]["crop_box"], [10, 20, 80, 100])
                self.assertEqual(records[0]["source_size"], [160, 120])
                self.assertEqual(records[0]["crop_source"], "manual")
            finally:
                dialog.deleteLater()

    def test_cropper_auto_splits_white_gutter_figure_plate(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "paper__accepted_000008__figure.jpg"
            image = QImage(320, 300, QImage.Format_RGB32)
            image.fill(0xFFFFFF)
            painter = QPainter(image)
            try:
                painter.fillRect(5, 5, 310, 95, QColor(120, 130, 112))
                painter.fillRect(5, 105, 310, 90, QColor(124, 134, 116))
                painter.fillRect(5, 205, 110, 90, QColor(140, 120, 96))
                painter.fillRect(125, 205, 190, 90, QColor(136, 124, 100))
            finally:
                painter.end()
            self.assertTrue(image.save(str(source)))

            dialog = ImageCropper(initial_image=str(source), lang="en")
            try:
                with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):
                    dialog.auto_split_panels()

                self.assertEqual(len(dialog.canvas.crops), 4)
                self.assertEqual(dialog.crop_list.count(), 4)
                self.assertTrue(all(source == "white_separator_panel_split" for source in dialog.crop_sources))

                with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):
                    dialog.save_crops()

                records = dialog.get_crop_records()
                self.assertEqual(len(records), 4)
                self.assertTrue(all(item["crop_source"] == "white_separator_panel_split" for item in records))
            finally:
                dialog.deleteLater()

    def test_cropper_can_delete_and_clear_auto_split_candidates_before_saving(self):
        dialog = ImageCropper(lang="en")
        try:
            dialog.canvas.crops = [QRectF(1, 2, 30, 40), QRectF(50, 60, 70, 80)]
            dialog.crop_sources = ["white_separator_panel_split", "hard_seam_panel_split"]
            dialog._refresh_crop_list()

            dialog.crop_list.setCurrentRow(1)
            dialog.delete_selected_crop()
            self.assertEqual(len(dialog.canvas.crops), 1)
            self.assertEqual(dialog.crop_sources, ["white_separator_panel_split"])
            self.assertEqual(dialog.crop_list.count(), 1)

            dialog.clear_crops()
            self.assertEqual(dialog.canvas.crops, [])
            self.assertEqual(dialog.crop_sources, [])
            self.assertEqual(dialog.crop_list.count(), 0)
        finally:
            dialog.deleteLater()

    def test_main_window_exposes_workbench_polish_hierarchy(self):
        window = self.make_main_window()

        try:
            window.enter_image_workflow()
            self.assertEqual(window.windowTitle(), "TaxaMask Workbench (EN)")
            self.assertEqual(window.tabs.styleSheet().strip(), "")
            self.assertIsNotNone(window.findChild(QWidget, "workbenchTopBar"))
            self.assertIsNotNone(window.findChild(QWidget, "workbenchToolbarProjectPanel"))
            self.assertIsNotNone(window.findChild(QWidget, "workbenchToolbarFlowPanel"))
            self.assertIsNotNone(window.findChild(QWidget, "workbenchAskAgentButton"))
            self.assertIsNotNone(window.findChild(QWidget, "taxamaskAgentPanel"))
            self.assertIsNotNone(window.findChild(QWidget, "workbenchLibraryPanel"))
            self.assertIsNotNone(window.findChild(QWidget, "workbenchCanvasShell"))
            self.assertIsNotNone(window.findChild(QWidget, "workbenchMetadataPanel"))
            self.assertIsNotNone(window.findChild(QWidget, "workbenchImageTaxonPanel"))
            self.assertIsNotNone(window.findChild(QWidget, "workbenchAIPanel"))
            self.assertIsNotNone(window.findChild(QWidget, "workbenchParentAnnotationPanel"))
            self.assertIsNotNone(window.findChild(QWidget, "workbenchAIActionPanel"))
            self.assertIsNotNone(window.findChild(QWidget, "workbenchLogsPanel"))
            self.assertEqual(window.btn_export.parentWidget().objectName(), "workbenchToolbarProjectPanel")
            self.assertEqual(window.btn_blink_entry.parentWidget().objectName(), "workbenchToolbarFlowPanel")
            self.assertFalse(window.btn_blink_entry.isVisible())
            self.assertEqual(window.btn_agent_from_workbench.parentWidget().objectName(), "workbenchToolbarFlowPanel")
            self.assertEqual(window.btn_literature_descriptions.parentWidget().objectName(), "workbenchDescriptionHeader")
            self.assertEqual(window.label_taxonomy.parentWidget().objectName(), "workbenchImageTaxonPanel")
            self.assertEqual(window.genus_combo.parentWidget().objectName(), "workbenchImageTaxonPanel")
            self.assertLess(
                window.metadata_panel.layout().indexOf(window.part_list),
                window.metadata_panel.layout().indexOf(window.image_taxon_panel),
            )
            self.assertLess(
                window.description_header_panel.layout().indexOf(window.btn_literature_descriptions),
                window.description_header_panel.layout().indexOf(window.label_description),
            )
            self.assertEqual(window.canvas.parentWidget().objectName(), "workbenchCanvasShell")
            self.assertEqual(window.label_ai_workflow.text(), "Auto Annotation")
            self.assertEqual(window.label_parent_annotation.text(), "Parent-part annotation")
            self.assertEqual(window.label_taxonomy.text(), "Current image taxon")
            self.assertFalse(hasattr(window, "slider_bright"))
            self.assertFalse(hasattr(window, "slider_contrast"))
            self.assertEqual(window.ai_model_panel.parentWidget().objectName(), "workbenchParentAnnotationPanel")
            self.assertEqual(window.ai_action_panel.parentWidget().objectName(), "workbenchParentAnnotationPanel")
            self.assertEqual(window.btn_predict.parentWidget().objectName(), "workbenchAIActionPanel")
            self.assertEqual(window.btn_blink_auto_annotate.parentWidget().objectName(), "workbenchBlinkRefinePanel")
            self.assertEqual(window.label_blink_refine.text(), "Child-part annotation")
            self.assertEqual(window.btn_blink_auto_annotate.text(), "Annotate child from existing parent box")
            self.assertEqual(window.combo_blink_parent_context.parentWidget().objectName(), "workbenchBlinkRefinePanel")
            self.assertEqual(window.radio_loose_shrink_box.parentWidget().objectName(), "workbenchToolStrip")
            self.assertEqual(window.radio_box.text(), "SAM Box Segmentation")
            self.assertIn("run SAM", window.radio_box.toolTip())
            self.assertEqual(window.radio_annotation_box.text(), "Manual ROI Box")
            self.assertIn("does not run SAM", window.radio_annotation_box.toolTip())
            self.assertEqual(window.radio_loose_shrink_box.text(), "Blink Shrink Start Box")
            self.assertIn("auto-shrink trajectory", window.radio_loose_shrink_box.toolTip())
            self.assertFalse(hasattr(window, "radio_blink_box_shrink"))
            self.assertEqual(window.log_console.parentWidget().objectName(), "workbenchLogsPanel")
            self.assertEqual(window.desc_box.parentWidget().objectName(), "workbenchMetadataPanel")
            window.change_language("zh")
            self.assertEqual(window.label_ai_workflow.text(), "自动标注")
            self.assertEqual(window.label_parent_annotation.text(), "父部位标注")
            self.assertEqual(window.label_blink_refine.text(), "子部位标注")
            self.assertEqual(window.label_taxonomy.text(), "当前图片物种")
            self.assertEqual(window.btn_blink_auto_annotate.text(), "用已有父框标注子部位")
            self.assertEqual(window.radio_box.text(), "SAM框选分割")
            self.assertIn("立即调用 SAM", window.radio_box.toolTip())
            self.assertEqual(window.radio_annotation_box.text(), "人工ROI框")
            self.assertIn("只保存框", window.radio_annotation_box.toolTip())
            self.assertEqual(window.radio_loose_shrink_box.text(), "Blink收缩起始框")
            self.assertIn("不是最终标注框", window.radio_loose_shrink_box.toolTip())
            self.assertFalse(window.desc_box.isReadOnly())
            self.assertIsInstance(window.part_list, QTreeWidget)
            self.assertEqual(window.part_list.objectName(), "workbenchPartTree")
            self.assertIsNone(window.findChild(QWidget, "workbenchRoutePanel"))
            self.assertEqual(window.workbench_splitter.handleWidth(), 8)
        finally:
            window.deleteLater()

    def test_image_group_header_collapse_does_not_load_image_during_startup(self):
        window = self.make_main_window()
        try:
            original_image = Path(self.temp_dir.name) / "original.png"
            crop_image = Path(self.temp_dir.name) / "original__panel_001.jpg"
            for path in (original_image, crop_image):
                image = QImage(120, 80, QImage.Format_RGB32)
                image.fill(0xFFB0B0B0)
                self.assertTrue(image.save(str(path)))

            original_key = str(original_image)
            crop_key = str(crop_image)
            self.project_manager.project_data["images"] = [original_key, crop_key]
            self.project_manager.project_data["labels"] = {
                original_key: {"parts": {}, "boxes": {}, "auto_boxes": {}, "descriptions": {}, "status": "unlabeled", "genus": "Unknown"},
                crop_key: {"parts": {}, "boxes": {}, "auto_boxes": {}, "descriptions": {}, "status": "unlabeled", "genus": "Unknown"},
            }
            self.project_manager.set_image_provenance(
                crop_key,
                {"source_type": "image_crop", "derived_from": {"image_path": original_key, "crop_index": 1}},
                save=False,
            )
            window.current_image = original_key
            window.refresh_file_list()
            window.canvas.load_image("")

            original_header = None
            for index in range(window.file_list.count()):
                item = window.file_list.item(index)
                if item.data(main_module.Qt.UserRole + 1) == "original":
                    original_header = item
                    break
            self.assertIsNotNone(original_header)
            self.assertTrue(window.canvas.original_pixmap is None or window.canvas.original_pixmap.isNull())

            window._handle_image_list_item_clicked(original_header)

            self.assertTrue(window.image_list_group_collapsed.get("original"))
            self.assertIsNone(window.file_list.currentItem())
            self.assertTrue(window.canvas.original_pixmap is None or window.canvas.original_pixmap.isNull())
            self.assertEqual(window.current_image, original_key)
        finally:
            window.deleteLater()

    def test_image_group_header_collapse_reuses_large_project_group_cache(self):
        window = self.make_main_window()
        try:
            image_paths = []
            labels = {}
            for index in range(1200):
                image_path = str(Path(self.temp_dir.name) / f"plate_{index:04d}.png")
                image_paths.append(image_path)
                labels[image_path] = {"parts": {}, "boxes": {}, "auto_boxes": {}, "descriptions": {}, "status": "unlabeled", "genus": "Unknown"}
            crop_path = str(Path(self.temp_dir.name) / "plate_0000__panel_001.jpg")
            image_paths.append(crop_path)
            labels[crop_path] = {"parts": {}, "boxes": {}, "auto_boxes": {}, "descriptions": {}, "status": "unlabeled", "genus": "Unknown"}
            self.project_manager.project_data["images"] = image_paths
            self.project_manager.project_data["labels"] = labels
            self.project_manager.set_image_provenance(
                crop_path,
                {"source_type": "image_crop", "derived_from": {"image_path": image_paths[0], "crop_index": 1}},
                save=False,
            )

            window.refresh_file_list()
            cached_state = window._image_list_state_cache
            self.assertIsInstance(cached_state, dict)
            self.assertEqual(cached_state["total_count"], len(image_paths))

            original_header = None
            for index in range(window.file_list.count()):
                item = window.file_list.item(index)
                if item.data(main_module.Qt.UserRole + 1) == "original":
                    original_header = item
                    break
            self.assertIsNotNone(original_header)

            with patch.object(window, "_build_image_list_state", side_effect=AssertionError("collapse should reuse cache")):
                window._handle_image_list_item_clicked(original_header)

            self.assertTrue(window.image_list_group_collapsed.get("original"))
            self.assertIs(window._image_list_state_cache, cached_state)
        finally:
            window.deleteLater()

    def test_literature_description_append_reveals_editable_target_box(self):
        window = self.make_main_window()
        try:
            window.enter_image_workflow()
            window.show()
            self.app.processEvents()
            image_path = str(Path(self.temp_dir.name) / "paper__accepted_000001.jpg")
            self.project_manager.project_data["images"] = [image_path]
            self.project_manager.project_data["labels"] = {image_path: {"parts": {}, "descriptions": {}}}
            window.current_image = image_path
            window.desc_box.setText("Existing manual note.")
            window.workbench_splitter.setSizes([240, 1200, 20])
            self.app.processEvents()

            source_meta = {
                "source": "literature",
                "pdf_filename": "paper.pdf",
                "taxon_name": "Aphaenogaster gamagumayaa",
            }
            window._apply_literature_description(
                "Mandible",
                "Mandible elongate, inner margin with small teeth.",
                source_meta,
                append=True,
            )
            self.app.processEvents()

            text = window.desc_box.toPlainText()
            self.assertIn("Existing manual note.", text)
            self.assertIn("Mandible elongate", text)
            self.assertFalse(window.desc_box.isReadOnly())
            self.assertGreaterEqual(window.workbench_splitter.sizes()[2], 180)
            self.assertEqual(
                self.project_manager.get_part_description(image_path, "Mandible"),
                text,
            )
            self.assertEqual(
                self.project_manager.get_description_source(image_path, "Mandible"),
                source_meta,
            )
            self.assertEqual(
                self.project_manager.get_taxon(image_path),
                "Aphaenogaster gamagumayaa",
            )
            self.assertEqual(window.genus_combo.currentText(), "Aphaenogaster gamagumayaa")
        finally:
            window.deleteLater()

    def test_blink_workbench_uses_lightweight_agent_entry_only(self):
        widget = BlinkLabWidget(self.engine, self.project_manager, lang="en")
        try:
            self.assertIsNotNone(widget.findChild(QWidget, "blinkStartCenterButton"))
            self.assertIsNotNone(widget.findChild(QWidget, "blinkAskAgentButton"))
            self.assertIsNone(widget.findChild(QWidget, "taxamaskAgentPanel"))
            context = widget.get_agent_context()
            self.assertEqual(context["source_workbench"], "blink")
            self.assertEqual(context["project_type"], "2d_stl")
        finally:
            widget.deleteLater()

    def test_part_tree_nests_blink_children_and_preserves_child_selection(self):
        window = self.make_main_window()
        try:
            self.project_manager.project_data["taxonomy"] = ["Head", "Mesosoma", "Gaster", "Mandible", "Seta"]
            self.project_manager.project_data["locator_scope"] = ["Head", "Mesosoma", "Gaster"]
            self.project_manager.project_data["cascade_routes"] = {
                "version": "project-v2",
                "routes": [
                    {"parent": "Head", "child": "Mandible", "enabled": False},
                    {"parent": "Head", "child": "Seta", "enabled": False},
                    {"parent": "Mesosoma", "child": "Seta", "enabled": False},
                ],
            }

            window.refresh_route_table()

            head_item = window.part_list.topLevelItem(0)
            self.assertEqual(head_item.data(0, main_module.Qt.UserRole), "Head")
            self.assertEqual(head_item.childCount(), 1)
            self.assertEqual(head_item.child(0).data(0, main_module.Qt.UserRole), "Mandible")

            cross_region_item = window.part_list.topLevelItem(3)
            self.assertIsNone(cross_region_item.data(0, main_module.Qt.UserRole))
            self.assertEqual(cross_region_item.child(0).data(0, main_module.Qt.UserRole), "Seta")

            window.part_list.setCurrentItem(head_item.child(0))
            self.app.processEvents()
            self.assertEqual(window._current_part_name(), "Mandible")
            self.assertEqual(window.canvas.current_tool_part, "Mandible")

            window.part_list.setCurrentItem(cross_region_item)
            self.app.processEvents()
            self.assertIsNone(window._current_part_name())
            self.assertIsNone(window.canvas.current_tool_part)
        finally:
            window.deleteLater()

    def test_workbench_blink_context_resolves_parent_route_and_status(self):
        window = self.make_main_window()
        try:
            self.project_manager.project_data["taxonomy"] = ["Head", "Mesosoma", "Gaster", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head", "Mesosoma", "Gaster"]
            image_path = str(Path(self.temp_dir.name) / "specimen.png")
            self.project_manager.project_data["images"] = [image_path]
            self.project_manager.project_data["labels"] = {
                image_path: {
                    "parts": {},
                    "boxes": {"Head": [10, 10, 80, 70]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }
            self.project_manager.project_data["blink_context_roi_parents"] = {"Mandible": "Head"}
            self.project_manager.project_data["cascade_routes"] = {
                "version": "project-v2",
                "routes": [
                    {
                        "parent": "Head",
                        "child": "Mandible",
                        "enabled": True,
                        "appointed_expert": {
                            "expert_id": "Mandible/expert_v20260501_090000.pth",
                            "expert_part": "Mandible",
                            "expert_filename": "expert_v20260501_090000.pth",
                        },
                        "expert_id": "Mandible/expert_v20260501_090000.pth",
                        "expert_part": "Mandible",
                        "expert_filename": "expert_v20260501_090000.pth",
                    }
                ],
            }

            window.refresh_route_table()
            window.current_image = image_path
            window._select_part_in_tree("Mandible")
            context = window._refresh_blink_refine_state()

            self.assertEqual(context["role"], "child")
            self.assertEqual(context["parent_part"], "Head")
            self.assertEqual(context["parent_source"], "remembered")
            self.assertEqual(context["parent_box_source"], "manual")
            self.assertEqual(context["route_label"], "Head -> Mandible")
            self.assertTrue(context["can_refine"])
            self.assertIn("Head -> Mandible", window.label_blink_route.text())
            self.assertTrue(window.btn_blink_auto_annotate.isEnabled())
        finally:
            window.deleteLater()

    def test_workbench_parent_context_combo_can_remember_manual_parent(self):
        window = self.make_main_window()
        try:
            image_path = str(Path(self.temp_dir.name) / "specimen.png")
            self.project_manager.project_data["taxonomy"] = ["Head", "Mesosoma", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head", "Mesosoma"]
            self.project_manager.project_data["images"] = [image_path]
            self.project_manager.project_data["labels"] = {
                image_path: {
                    "parts": {},
                    "boxes": {"Mesosoma": [10, 10, 90, 60]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }

            window.refresh_route_table()
            window.current_image = image_path
            window._select_part_in_tree("Mandible")
            index = window.combo_blink_parent_context.findData("Mesosoma")
            self.assertGreaterEqual(index, 0)
            window.combo_blink_parent_context.setCurrentIndex(index)
            window.on_blink_parent_context_changed()

            self.assertEqual(self.project_manager.get_blink_context_parent("Mandible"), "Mesosoma")
            route = self.project_manager.get_cascade_route("Mesosoma", "Mandible")
            self.assertIsNotNone(route)
            self.assertEqual(route.get("registration_source"), "workbench_blink_refine")
            context = window._refresh_blink_refine_state()
            self.assertEqual(context["parent_part"], "Mesosoma")
            self.assertEqual(context["parent_source"], "remembered")
        finally:
            window.deleteLater()

    def test_single_locator_parent_does_not_auto_bind_new_child_part(self):
        window = self.make_main_window()
        try:
            image_path = str(Path(self.temp_dir.name) / "specimen.png")
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["images"] = [image_path]
            self.project_manager.project_data["labels"] = {
                image_path: {
                    "parts": {},
                    "boxes": {"Head": [10, 10, 80, 70]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }

            window.refresh_route_table()
            window.current_image = image_path
            self.assertEqual(window.part_list.topLevelItem(0).data(0, main_module.Qt.UserRole), "Head")
            self.assertEqual(window.part_list.topLevelItem(0).childCount(), 0)

            window._select_part_in_tree("Mandible")
            context = window._refresh_blink_refine_state()

            self.assertEqual(context["role"], "child")
            self.assertIsNone(context["parent_part"])
            self.assertEqual(context["parent_source"], "none")
            self.assertEqual(window.combo_blink_parent_context.findData("Head"), 0)
            self.assertEqual(window.combo_blink_parent_context.currentIndex(), -1)
            self.assertIsNone(self.project_manager.get_blink_context_parent("Mandible"))
            self.assertIsNone(self.project_manager.get_cascade_route("Head", "Mandible"))

            window.combo_blink_parent_context.setCurrentIndex(0)
            window.on_blink_parent_context_changed()

            self.assertEqual(self.project_manager.get_blink_context_parent("Mandible"), "Head")
            self.assertIsNotNone(self.project_manager.get_cascade_route("Head", "Mandible"))
            self.assertEqual(window.part_list.topLevelItem(0).child(0).data(0, main_module.Qt.UserRole), "Mandible")
        finally:
            window.deleteLater()

    def test_workbench_parent_context_combo_lists_only_real_parent_options(self):
        window = self.make_main_window()
        try:
            image_path = str(Path(self.temp_dir.name) / "specimen.png")
            self.project_manager.project_data["taxonomy"] = ["Head", "Mesosoma", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head", "Mesosoma"]
            self.project_manager.project_data["images"] = [image_path]
            self.project_manager.project_data["labels"] = {
                image_path: {
                    "parts": {},
                    "boxes": {"Head": [10, 10, 80, 70], "Mesosoma": [90, 10, 150, 70]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }

            window.refresh_route_table()
            window.current_image = image_path
            window._select_part_in_tree("Mandible")
            context = window._refresh_blink_refine_state()

            combo_items = [window.combo_blink_parent_context.itemText(index) for index in range(window.combo_blink_parent_context.count())]
            combo_data = [window.combo_blink_parent_context.itemData(index) for index in range(window.combo_blink_parent_context.count())]
            self.assertIn("Head", combo_data)
            self.assertIn("Mesosoma", combo_data)
            self.assertNotIn("Choose parent context", combo_items)
            self.assertIsNone(context["parent_part"])
            self.assertEqual(window.combo_blink_parent_context.currentIndex(), -1)
        finally:
            window.deleteLater()

    def test_workbench_parent_context_combo_uses_disabled_unavailable_message_without_options(self):
        window = self.make_main_window()
        try:
            self.project_manager.project_data["taxonomy"] = ["Mandible"]
            self.project_manager.project_data["locator_scope"] = []
            window.refresh_route_table()
            window._select_part_in_tree("Mandible")

            self.assertFalse(window.combo_blink_parent_context.isEnabled())
            self.assertEqual(window.combo_blink_parent_context.count(), 1)
            self.assertEqual(window.combo_blink_parent_context.itemData(0), "")
            self.assertIn("unavailable", window.combo_blink_parent_context.itemText(0).lower())
        finally:
            window.deleteLater()

    def test_annotation_box_roles_keep_child_box_and_shrink_loose_box_separate(self):
        window = self.make_main_window()
        try:
            image_path = str(Path(self.temp_dir.name) / "specimen.png")
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["images"] = [image_path]
            self.project_manager.project_data["labels"] = {
                image_path: {
                    "parts": {},
                    "boxes": {"Head": [10, 10, 80, 70]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }
            self.project_manager.project_data["blink_context_roi_parents"] = {"Mandible": "Head"}
            window.refresh_route_table()
            window.current_image = image_path
            window._select_part_in_tree("Mandible")

            window.radio_annotation_box.setChecked(True)
            window.on_tool_changed()
            window.on_annotation_box_completed(20, 20, 40, 40)
            self.assertEqual(self.project_manager.get_boxes(image_path)["Mandible"], [20.0, 20.0, 40.0, 40.0])

            window.radio_loose_shrink_box.setChecked(True)
            window.on_tool_changed()
            window.on_annotation_box_completed(15, 15, 45, 45)
            self.assertEqual(self.project_manager.get_boxes(image_path)["Mandible"], [20.0, 20.0, 40.0, 40.0])
            self.assertEqual(self.project_manager.get_shrink_loose_boxes(image_path)["Mandible"], [15.0, 15.0, 45.0, 45.0])
            self.assertEqual(window.canvas.shrink_loose_boxes["Mandible"], [15.0, 15.0, 45.0, 45.0])
        finally:
            window.deleteLater()

    def test_parent_box_ratio_lock_defaults_off_and_can_affect_sam_and_roi_boxes(self):
        window = self.make_main_window()
        try:
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["parent_box_aspect_ratios"] = {"Head": 1.0}
            window.refresh_route_table()
            window._select_part_in_tree("Head")
            window.radio_box.setChecked(True)
            window.on_tool_changed()

            self.assertEqual(window.canvas.mode, "BOX_PROMPT")
            self.assertFalse(window.check_lock_parent_box_ratio.isChecked())
            self.assertIsNone(window.canvas.annotation_box_aspect_ratio)
            window.check_lock_parent_box_ratio.setChecked(True)
            self.assertEqual(window.canvas.annotation_box_aspect_ratio, 1.0)

            window.radio_annotation_box.setChecked(True)
            window.on_tool_changed()

            self.assertEqual(window.canvas.mode, "ANNOTATION_BOX")
            self.assertEqual(window.canvas.annotation_box_aspect_ratio, 1.0)
            window.check_lock_parent_box_ratio.setChecked(False)
            self.assertIsNone(window.canvas.annotation_box_aspect_ratio)
        finally:
            window.deleteLater()

    def test_locked_annotation_box_ratio_keeps_drag_point_inside_box(self):
        canvas = main_module.AnnotationCanvas()
        canvas.set_mode("BOX_PROMPT")
        canvas.set_annotation_box_aspect_ratio(2.0)

        rect = canvas._box_rect_for_current_mode(QPointF(10, 10), QPointF(20, 40))

        self.assertLessEqual(rect.left(), 20)
        self.assertGreaterEqual(rect.right(), 20)
        self.assertLessEqual(rect.top(), 40)
        self.assertGreaterEqual(rect.bottom(), 40)
        self.assertAlmostEqual(rect.width() / rect.height(), 2.0)

    def test_loose_shrink_box_tool_is_child_only(self):
        window = self.make_main_window()
        try:
            image_path = str(Path(self.temp_dir.name) / "specimen.png")
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["images"] = [image_path]
            self.project_manager.project_data["labels"] = {
                image_path: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }
            window.refresh_route_table()
            window.current_image = image_path
            window._select_part_in_tree("Head")

            window.radio_loose_shrink_box.setChecked(True)
            window.on_tool_changed()
            with patch.object(main_module.QMessageBox, "information") as info:
                window.on_annotation_box_completed(10, 10, 40, 40)

            self.assertIn("child structures", info.call_args.args[2])
            self.assertNotIn("Head", self.project_manager.get_boxes(image_path))
            self.assertEqual(self.project_manager.get_shrink_loose_boxes(image_path), {})
        finally:
            window.deleteLater()

    def test_workbench_child_auto_annotate_uses_route_expert_and_sam_polygon(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(96, 72, QImage.Format_RGB32)
        image.fill(0xFFCCCCCC)
        self.assertTrue(image.save(str(image_path)))

        window = self.make_main_window()
        try:
            image_key = str(image_path)
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {},
                    "boxes": {"Head": [5, 5, 80, 60]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }
            self.project_manager.project_data["blink_context_roi_parents"] = {"Mandible": "Head"}
            self.project_manager.project_data["cascade_routes"] = {
                "version": "project-v2",
                "routes": [
                    {
                        "parent": "Head",
                        "child": "Mandible",
                        "enabled": True,
                        "appointed_expert": {
                            "expert_id": "Mandible/expert_v20260501_090000.pth",
                            "expert_part": "Mandible",
                            "expert_filename": "expert_v20260501_090000.pth",
                        },
                        "expert_id": "Mandible/expert_v20260501_090000.pth",
                        "expert_part": "Mandible",
                        "expert_filename": "expert_v20260501_090000.pth",
                    }
                ],
            }
            window.refresh_route_table()
            window.current_image = image_key
            window._select_part_in_tree("Mandible")

            window.run_blink_child_auto_annotate()

            self.assertEqual(self.engine.predict_calls, [])
            self.assertEqual(len(self.engine.cascade_manager.infer_calls), 1)
            call = self.engine.cascade_manager.infer_calls[0]
            self.assertEqual(call["parent_part"], "Head")
            self.assertEqual(call["child_part_name"], "Mandible")
            self.assertEqual(call["parent_box"], [5.0, 5.0, 80.0, 60.0])
            self.assertEqual(call["route_manifest"]["routes"][0]["child"], "Mandible")
            self.assertEqual(
                self.project_manager.get_boxes(image_key)["Mandible"],
                [18.0, 18.0, 42.0, 42.0],
            )
            self.assertEqual(len(self.project_manager.get_labels(image_key)["Mandible"]), 4)
            self.assertEqual(self.project_manager.get_blink_context_parent("Mandible"), "Head")
        finally:
            window.deleteLater()

    def test_workbench_child_auto_annotate_accepts_parent_auto_box_after_prediction_refresh(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(96, 72, QImage.Format_RGB32)
        image.fill(0xFFCCCCCC)
        self.assertTrue(image.save(str(image_path)))

        window = self.make_main_window()
        try:
            image_key = str(image_path)
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }
            self.project_manager.project_data["blink_context_roi_parents"] = {"Mandible": "Head"}
            self.project_manager.project_data["cascade_routes"] = {
                "version": "project-v2",
                "routes": [
                    {
                        "parent": "Head",
                        "child": "Mandible",
                        "enabled": True,
                        "appointed_expert": {
                            "expert_id": "Mandible/expert_v20260501_090000.pth",
                            "expert_part": "Mandible",
                            "expert_filename": "expert_v20260501_090000.pth",
                        },
                        "expert_id": "Mandible/expert_v20260501_090000.pth",
                        "expert_part": "Mandible",
                        "expert_filename": "expert_v20260501_090000.pth",
                    }
                ],
            }
            self.engine.predict_calls.clear()
            self.engine.predict_full_pipeline = lambda **_kwargs: {
                "polygons": {"Head": [[12.0, 14.0], [74.0, 14.0], [74.0, 58.0], [12.0, 58.0]]},
                "auto_boxes": {"Head": [12.0, 14.0, 74.0, 58.0]},
                "meta": {},
            }
            window.refresh_route_table()
            window.current_image = image_key
            window._select_part_in_tree("Mandible")
            before_context = window._refresh_blink_refine_state()
            self.assertFalse(before_context["has_parent_box"])
            self.assertFalse(window.btn_blink_auto_annotate.isEnabled())

            window.run_prediction()

            after_context = window._refresh_blink_refine_state()
            self.assertTrue(after_context["has_parent_box"])
            self.assertEqual(after_context["parent_box_source"], "auto")
            self.assertTrue(after_context["can_refine"])
            self.assertTrue(window.btn_blink_auto_annotate.isEnabled())

            window.run_blink_child_auto_annotate()

            self.assertEqual(len(self.engine.cascade_manager.infer_calls), 1)
            self.assertEqual(self.engine.cascade_manager.infer_calls[0]["parent_box"], [12.0, 14.0, 74.0, 58.0])
        finally:
            window.deleteLater()

    def test_workbench_child_auto_annotate_requires_ready_route_and_parent_box(self):
        window = self.make_main_window()
        try:
            image_path = str(Path(self.temp_dir.name) / "specimen.png")
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["images"] = [image_path]
            self.project_manager.project_data["labels"] = {
                image_path: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }
            self.project_manager.project_data["blink_context_roi_parents"] = {"Mandible": "Head"}
            window.refresh_route_table()
            window.current_image = image_path
            window._select_part_in_tree("Mandible")
            context = window._refresh_blink_refine_state()
            self.assertFalse(context["can_refine"])
            self.assertIn("Draw a parent box", context["disabled_reason"])
            self.assertFalse(window.btn_blink_auto_annotate.isEnabled())

            with patch.object(main_module.QMessageBox, "information") as info:
                window.run_blink_child_auto_annotate()
            info.assert_called()
            self.assertEqual(self.engine.cascade_manager.infer_calls, [])

            self.project_manager.project_data["labels"][image_path]["boxes"]["Head"] = [5, 5, 80, 60]
            window._refresh_blink_refine_state()
            self.assertFalse(window.btn_blink_auto_annotate.isEnabled())
            self.assertIn("Configure a route expert", window.btn_blink_auto_annotate.toolTip())
        finally:
            window.deleteLater()

    def test_child_auto_annotate_does_not_run_with_unappointed_route_expert(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(96, 72, QImage.Format_RGB32)
        image.fill(0xFFCCCCCC)
        self.assertTrue(image.save(str(image_path)))

        window = self.make_main_window()
        try:
            image_key = str(image_path)
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {},
                    "boxes": {"Head": [5, 5, 80, 60]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }
            self.project_manager.project_data["blink_context_roi_parents"] = {"Mandible": "Head"}
            self.project_manager.project_data["cascade_routes"] = {
                "version": "project-v2",
                "routes": [
                    {
                        "parent": "Head",
                        "child": "Mandible",
                        "enabled": True,
                        "appointed_expert": {},
                        "expert_candidates": [],
                        "expert_id": None,
                        "expert_part": None,
                        "expert_filename": None,
                    }
                ],
            }
            window.refresh_route_table()
            window.current_image = image_key
            window._select_part_in_tree("Mandible")
            context = window._refresh_blink_refine_state()

            self.assertFalse(context["can_refine"])
            self.assertIn("Configure a route expert", context["disabled_reason"])
            self.assertFalse(window.btn_blink_auto_annotate.isEnabled())

            with patch.object(main_module.QMessageBox, "information") as info:
                window.run_blink_child_auto_annotate()

            info.assert_called()
            self.assertEqual(self.engine.predict_calls, [])
            self.assertEqual(self.engine.cascade_manager.infer_calls, [])
            self.assertNotIn("Mandible", self.project_manager.get_boxes(image_key))
        finally:
            window.deleteLater()

    def test_workbench_auto_shrink_saves_parent_context_trajectory(self):
        module = type(sys)("core.blink_refiner")

        class FakeRefiner:
            steps = None

            def __init__(self, sam_model=None, device="auto"):
                self.sam_model = sam_model
                self.device = device

            def generate_shrink_trajectory(self, image_input, initial_box, golden_poly, steps=20):
                FakeRefiner.steps = steps
                return [
                    {"step": 0, "alpha": 0.0, "box": list(initial_box), "is_golden": False},
                    {"step": 1, "alpha": 1.0, "box": [22.0, 22.0, 38.0, 38.0], "is_golden": True},
                ]

        module.BlinkRefiner = FakeRefiner
        previous_module = sys.modules.get("core.blink_refiner")
        sys.modules["core.blink_refiner"] = module

        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(96, 72, QImage.Format_RGB32)
        image.fill(0xFFCCCCCC)
        self.assertTrue(image.save(str(image_path)))
        window = self.make_main_window()
        try:
            image_key = str(image_path)
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {"Mandible": [[24, 24], [38, 24], [38, 38], [24, 38]]},
                    "boxes": {"Head": [5, 5, 80, 60], "Mandible": [24, 24, 38, 38]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "shrink_loose_boxes": {"Mandible": [18, 18, 44, 44]},
                    "status": "labeled",
                    "genus": "Unknown",
                }
            }
            self.project_manager.project_data["active_model_profile"] = {
                "child_backend_defaults": {"auto_shrink_steps": 12}
            }
            self.project_manager.project_data["blink_context_roi_parents"] = {"Mandible": "Head"}
            window.refresh_route_table()
            window.current_image = image_key
            window._select_part_in_tree("Mandible")

            window.run_blink_auto_shrink()

            trajectory = self.project_manager.project_data["labels"][image_key]["trajectories"]["Mandible"]
            self.assertEqual(len(trajectory["frames"]), 2)
            self.assertEqual(trajectory["parent_context"]["parent_part"], "Head")
            self.assertEqual(trajectory["parent_context"]["parent_box"], [5.0, 5.0, 80.0, 60.0])
            self.assertEqual(self.project_manager.get_boxes(image_key)["Mandible"], [22.0, 22.0, 38.0, 38.0])
            self.assertEqual(FakeRefiner.steps, 12)
        finally:
            window.deleteLater()
            if previous_module is not None:
                sys.modules["core.blink_refiner"] = previous_module
            else:
                sys.modules.pop("core.blink_refiner", None)

    def test_workbench_batch_auto_shrink_skips_existing_trajectories(self):
        module = type(sys)("core.blink_refiner")

        class FakeRefiner:
            calls = []

            def __init__(self, sam_model=None, device="auto"):
                self.sam_model = sam_model
                self.device = device

            def generate_shrink_trajectory(self, image_input, initial_box, golden_poly, steps=20):
                FakeRefiner.calls.append((tuple(initial_box), len(golden_poly), steps))
                return [
                    {"step": 0, "alpha": 0.0, "box": list(initial_box), "is_golden": False},
                    {"step": 1, "alpha": 1.0, "box": [22.0, 22.0, 38.0, 38.0], "is_golden": True},
                ]

        module.BlinkRefiner = FakeRefiner
        previous_module = sys.modules.get("core.blink_refiner")
        sys.modules["core.blink_refiner"] = module

        first_path = Path(self.temp_dir.name) / "specimen_a.png"
        second_path = Path(self.temp_dir.name) / "specimen_b.png"
        for path in (first_path, second_path):
            image = QImage(96, 72, QImage.Format_RGB32)
            image.fill(0xFFCCCCCC)
            self.assertTrue(image.save(str(path)))
        window = self.make_main_window()
        try:
            first_key = str(first_path)
            second_key = str(second_path)
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["images"] = [first_key, second_key]
            base_label = {
                "parts": {"Mandible": [[24, 24], [38, 24], [38, 38], [24, 38]]},
                "boxes": {"Head": [5, 5, 80, 60], "Mandible": [24, 24, 38, 38]},
                "auto_boxes": {},
                "descriptions": {},
                "shrink_loose_boxes": {"Mandible": [18, 18, 44, 44]},
                "status": "labeled",
                "genus": "Unknown",
            }
            self.project_manager.project_data["labels"] = {
                first_key: copy.deepcopy(base_label),
                second_key: {
                    **copy.deepcopy(base_label),
                    "trajectories": {"Mandible": {"frames": [{"box": [1, 1, 2, 2]}]}},
                },
            }
            self.project_manager.project_data["active_model_profile"] = {
                "child_backend_defaults": {"auto_shrink_steps": 9}
            }
            self.project_manager.project_data["blink_context_roi_parents"] = {"Mandible": "Head"}
            window.refresh_route_table()
            window.current_image = first_key
            window._select_part_in_tree("Mandible")

            with patch.object(blink_workflow_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):
                window.run_blink_batch_auto_shrink()

            self.assertEqual(len(FakeRefiner.calls), 1)
            self.assertEqual(FakeRefiner.calls[0][2], 9)
            first_trajectory = self.project_manager.project_data["labels"][first_key]["trajectories"]["Mandible"]
            second_trajectory = self.project_manager.project_data["labels"][second_key]["trajectories"]["Mandible"]
            self.assertEqual(len(first_trajectory["frames"]), 2)
            self.assertEqual(first_trajectory["parent_context"]["parent_part"], "Head")
            self.assertEqual(second_trajectory["frames"], [{"box": [1, 1, 2, 2]}])
            self.assertEqual(self.project_manager.get_boxes(first_key)["Mandible"], [22.0, 22.0, 38.0, 38.0])
        finally:
            window.deleteLater()
            if previous_module is not None:
                sys.modules["core.blink_refiner"] = previous_module
            else:
                sys.modules.pop("core.blink_refiner", None)

    def test_workbench_auto_shrink_requires_polygon_and_loose_box(self):
        window = self.make_main_window()
        try:
            image_path = str(Path(self.temp_dir.name) / "specimen.png")
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["images"] = [image_path]
            self.project_manager.project_data["labels"] = {
                image_path: {
                    "parts": {},
                    "boxes": {"Head": [5, 5, 80, 60]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }
            self.project_manager.project_data["blink_context_roi_parents"] = {"Mandible": "Head"}
            window.refresh_route_table()
            window.current_image = image_path
            window._select_part_in_tree("Mandible")
            with patch.object(main_module.QMessageBox, "information") as info:
                window.run_blink_auto_shrink()
            self.assertIn("Draw or confirm the child polygon", info.call_args.args[2])

            self.project_manager.project_data["labels"][image_path]["parts"]["Mandible"] = [[20, 20], [40, 20], [40, 40]]
            with patch.object(main_module.QMessageBox, "information") as info:
                window.run_blink_auto_shrink()
            self.assertIn("Blink Shrink Start Box", info.call_args.args[2])
            self.assertIn("canvas toolbar", info.call_args.args[2])
        finally:
            window.deleteLater()

    def test_workbench_train_current_blink_expert_uses_current_parent_child_context(self):
        window = self.make_main_window()
        try:
            image_path = str(Path(self.temp_dir.name) / "specimen.png")
            other_image_path = str(Path(self.temp_dir.name) / "other_specimen.png")
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["images"] = [image_path, other_image_path]
            self.project_manager.project_data["image_groups"] = {
                "custom_groups": [{"id": "pilot_group", "name": "Pilot group"}]
            }
            self.project_manager.project_data["labels"] = {
                image_path: {
                    "parts": {"Mandible": [[24, 24], [38, 24], [38, 38], [24, 38]]},
                    "boxes": {"Head": [5, 5, 80, 60]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "labeled",
                    "genus": "Unknown",
                }
            }
            self.project_manager.set_image_provenance(image_path, {"manual_image_group": "pilot_group"}, save=False)
            self.project_manager.project_data["blink_context_roi_parents"] = {"Mandible": "Head"}
            window.refresh_file_list()
            group_index = window.combo_training_scope.findData("pilot_group")
            self.assertGreaterEqual(group_index, 0)
            window.combo_training_scope.setCurrentIndex(group_index)
            window.refresh_route_table()
            window.current_image = image_path
            window._select_part_in_tree("Mandible")

            with patch.object(window.blink_lab, "train_expert_model") as train:
                window.train_current_blink_expert()

            train.assert_called_once()
            _, train_kwargs = train.call_args
            self.assertEqual(train_kwargs["allowed_image_paths"], [image_path])
            self.assertEqual(train_kwargs["training_scope"]["scope_id"], "pilot_group")
            self.assertEqual(train_kwargs["training_scope"]["label"], "Pilot group")
            self.assertEqual(train_kwargs["training_scope"]["image_count"], 1)
            self.assertEqual(window.blink_lab.session_target_part, "Mandible")
            self.assertEqual(window.blink_lab.current_image_path, image_path)
            self.assertEqual(window.blink_lab.active_session["focus_roi"]["part"], "Head")
            self.assertEqual(window.blink_lab.training_route_context["parent_part"], "Head")
            self.assertEqual(window.blink_lab.training_route_context["child_part"], "Mandible")
        finally:
            window.deleteLater()

    def test_child_expert_datasets_filter_trajectories_by_training_scope_images(self):
        image_paths = []
        for index in range(2):
            image_path = Path(self.temp_dir.name) / f"child_scope_{index}.png"
            image = QImage(96, 72, QImage.Format_RGB32)
            image.fill(0xFFB0B0B0)
            self.assertTrue(image.save(str(image_path)))
            image_paths.append(str(image_path))

        self.project_manager.project_data["labels"] = {
            path: {
                "trajectories": {
                    "Mandible": {
                        "frames": [
                            {"box": [10.0, 10.0, 40.0, 36.0]},
                            {"box": [12.0, 12.0, 34.0, 30.0]},
                        ],
                        "parent_context": {
                            "parent_part": "Head",
                            "parent_box": [4.0, 4.0, 80.0, 62.0],
                        },
                    }
                }
            }
            for path in image_paths
        }
        project_path = Path(self.project_manager.current_project_path)
        project_path.write_text(json.dumps(self.project_manager.project_data), encoding="utf-8")

        vit_dataset = BlinkTrajectoryDataset(
            str(project_path),
            part_name="Mandible",
            parent_part="Head",
            target_size=(224, 224),
            allowed_image_paths=[image_paths[0]],
        )
        heatmap_dataset = BlinkHeatmapDataset(
            str(project_path),
            child_part="Mandible",
            parent_part="Head",
            input_size=224,
            allowed_image_paths=[image_paths[0]],
        )

        self.assertEqual(len(vit_dataset.samples), 1)
        self.assertEqual(vit_dataset.samples[0]["image_path"], os.path.normpath(image_paths[0]))
        self.assertEqual(heatmap_dataset.sequence_count, 1)
        self.assertEqual(heatmap_dataset.samples[0]["image_path"], os.path.normpath(image_paths[0]))

    def test_workbench_shared_training_progress_tracks_child_expert_thread(self):
        class FakeBlinkTrainingThread:
            def __init__(self):
                self.progress_signal = DummySignal()
                self.result_signal = DummySignal()
                self.error_signal = DummySignal()
                self.cancelled_signal = DummySignal()
                self.finished = DummySignal()
                self._running = True

            def isRunning(self):
                return self._running

        window = self.make_main_window()
        try:
            image_path = str(Path(self.temp_dir.name) / "specimen.png")
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["images"] = [image_path]
            self.project_manager.project_data["labels"] = {
                image_path: {
                    "parts": {"Mandible": [[24, 24], [38, 24], [38, 38], [24, 38]]},
                    "boxes": {"Head": [5, 5, 80, 60]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "labeled",
                    "genus": "Unknown",
                }
            }
            self.project_manager.project_data["blink_context_roi_parents"] = {"Mandible": "Head"}
            window.refresh_route_table()
            window.current_image = image_path
            window._select_part_in_tree("Mandible")
            fake_thread = FakeBlinkTrainingThread()

            def start_fake_training(*_args, **_kwargs):
                window.blink_lab.training_thread = fake_thread

            with patch.object(window.blink_lab, "train_expert_model", side_effect=start_fake_training):
                window.train_current_blink_expert()

            self.assertTrue(window.btn_blink_stop_training.isEnabled())
            fake_thread.progress_signal.emit(37)
            self.assertEqual(window.progress.value(), 37)
            self.assertIn("Child-part expert training", window.label_training_progress_status.text())
            self.assertIn("Head -> Mandible", window.label_training_progress_status.text())

            fake_thread.result_signal.emit(str(Path(self.temp_dir.name) / "mandible_expert.pt"))
            fake_thread._running = False
            fake_thread.finished.emit()
            self.assertEqual(window.progress.value(), 100)
            self.assertTrue(window.btn_train.isEnabled())
            self.assertFalse(window.btn_blink_stop_training.isEnabled())
        finally:
            window.deleteLater()

    def test_workbench_child_training_stop_button_delegates_to_blink_lab(self):
        class FakeBlinkTrainingThread:
            def __init__(self):
                self.progress_signal = DummySignal()
                self.result_signal = DummySignal()
                self.error_signal = DummySignal()
                self.cancelled_signal = DummySignal()
                self.finished = DummySignal()
                self._running = True

            def isRunning(self):
                return self._running

        window = self.make_main_window()
        try:
            fake_thread = FakeBlinkTrainingThread()
            window.blink_lab.training_thread = fake_thread
            window._connect_child_training_progress()
            window.btn_blink_stop_training.setEnabled(True)
            with patch.object(window.blink_lab, "stop_expert_training") as stop:
                window.stop_current_blink_expert_training()

            stop.assert_called_once()
            self.assertTrue(window.child_training_cancel_requested)
            self.assertFalse(window.btn_blink_stop_training.isEnabled())
            self.assertIn("Stopping child-part expert training", window.label_training_progress_status.text())
        finally:
            window.deleteLater()

    def test_workbench_training_results_browser_discovers_parent_and_child_reports(self):
        experiments_dir = Path(self.temp_dir.name) / "experiments"
        parent_dir = experiments_dir / "exp_20260606_010101"
        child_dir = experiments_dir / "heatmap_blink_Mandible_20260606_010102"
        for report_dir in [parent_dir, child_dir]:
            (report_dir / "val_details").mkdir(parents=True, exist_ok=True)
            (report_dir / "validation_index.csv").write_text(
                "sample_id,image_name,image_path,detail_image,provenance,valid_parts,predicted_parts,peak_summary,error_summary,max_error_px\n",
                encoding="utf-8",
            )

        (parent_dir / "report_summary.json").write_text(
            main_module.json.dumps(
                {
                    "validation_count": 6,
                    "metrics_plot": "metrics_plot.png",
                    "validation_summary_image": "validation_samples.png",
                    "validation_details_dir": "val_details",
                    "validation_index_csv": "validation_index.csv",
                    "training_context": {
                        "parent_backend": main_module.PARENT_BACKEND_BUILTIN,
                        "locator_scope": ["Head", "Mesosoma", "Gaster"],
                        "train_segmenter": True,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (child_dir / "report_summary.json").write_text(
            main_module.json.dumps(
                {
                    "kind": "heatmap_blink_expert_report",
                    "part_name": "Mandible",
                    "parent_part": "Head",
                    "model_path": str(self.weights_dir / "experts" / "Mandible" / "model.pth"),
                    "training_strategy": main_module.BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
                    "validation_count": 4,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        window = self.make_main_window()
        try:
            self.assertIsNotNone(getattr(window, "btn_training_results", None))
            self.assertEqual(window.btn_training_results.objectName(), "workbenchTrainingResultsButton")
            self.assertEqual(window.btn_training_results.text(), "Training Results")
            reports = [
                report
                for report in window.discover_training_reports()
                if str(report.get("dir", "")).startswith(str(experiments_dir))
            ]
            self.assertEqual(len(reports), 2)
            report_types = {report["report_type"] for report in reports}
            self.assertEqual(report_types, {"parent", "child"})
            child_report = next(report for report in reports if report["report_type"] == "child")
            self.assertEqual(child_report["target_label"], "Head -> Mandible")
            self.assertIn("Plan 3", child_report["strategy_label"])

            dialog = main_module.TrainingResultBrowserDialog(reports, lang="en")
            try:
                self.assertEqual(dialog.table.rowCount(), 2)
                self.assertEqual(
                    [dialog.table.horizontalHeaderItem(i).text() for i in range(dialog.table.columnCount())],
                    ["Type", "Target", "Backend", "Strategy", "Samples", "Time", "Status", "Note", "Report Folder"],
                )
            finally:
                dialog.close()
        finally:
            window.deleteLater()

    def test_workbench_training_buttons_are_mutually_exclusive(self):
        class FakeRunningTraining:
            def isRunning(self):
                return True

        window = self.make_main_window()
        try:
            image_path = str(Path(self.temp_dir.name) / "specimen.png")
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.project_manager.project_data["images"] = [image_path]
            self.project_manager.project_data["labels"] = {
                image_path: {
                    "parts": {"Mandible": [[24, 24], [38, 24], [38, 38], [24, 38]]},
                    "boxes": {"Head": [5, 5, 80, 60]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "labeled",
                    "genus": "Unknown",
                }
            }
            self.project_manager.project_data["blink_context_roi_parents"] = {"Mandible": "Head"}
            window.refresh_route_table()
            window.current_image = image_path
            window._select_part_in_tree("Mandible")

            window.trainer = FakeRunningTraining()
            with patch.object(window.blink_lab, "train_expert_model") as train, \
                 patch.object(main_module.QMessageBox, "information") as info:
                window.train_current_blink_expert()

            train.assert_not_called()
            info.assert_called()

            window.trainer = None
            window.blink_lab.training_thread = FakeRunningTraining()
            with patch.object(main_module.QMessageBox, "information") as info:
                window.run_training()
            info.assert_called()
        finally:
            window.deleteLater()

    def test_remove_selected_tree_part_delegates_to_project_cleanup(self):
        window = self.make_main_window()
        try:
            self.project_manager.project_data["taxonomy"] = ["Head", "Mesosoma", "Gaster", "Mandible"]
            self.project_manager.project_data["locator_scope"] = ["Head", "Mesosoma", "Gaster"]
            self.project_manager.project_data["cascade_routes"] = {
                "version": "project-v2",
                "routes": [{"parent": "Head", "child": "Mandible", "enabled": False}],
            }
            window.refresh_route_table()
            mandible_item = window.part_list.topLevelItem(0).child(0)
            window.part_list.setCurrentItem(mandible_item)

            with patch.object(
                part_tree_module,
                "themed_yes_no_question",
                return_value=main_module.QMessageBox.Yes,
            ), patch.object(self.project_manager, "remove_taxonomy_part", wraps=self.project_manager.remove_taxonomy_part) as remover:
                window.remove_taxonomy_part()

            remover.assert_called_once_with("Mandible")
            self.assertNotIn("Mandible", self.project_manager.project_data["taxonomy"])
            self.assertEqual(self.project_manager.project_data["cascade_routes"]["routes"], [])
        finally:
            window.deleteLater()

    def test_model_settings_hosts_project_route_management_panel(self):
        window = self.make_main_window()
        try:
            window.project_manager = self.project_manager
            self.project_manager.project_data["taxonomy"] = ["Head", "Mesosoma", "Gaster", "Mandible"]
            self.project_manager.project_data["cascade_routes"] = {
                "version": "project-v2",
                "routes": [
                    {
                        "parent": "Head",
                        "child": "Mandible",
                        "enabled": False,
                        "appointed_expert": {
                            "expert_id": None,
                            "expert_part": None,
                            "expert_filename": None,
                        },
                        "expert_candidates": [],
                        "expert_id": None,
                        "expert_part": None,
                        "expert_filename": None,
                        "registration_source": "blink_candidate",
                    }
                ],
            }
            image_a = str(Path(self.temp_dir.name) / "specimen_a.png")
            image_b = str(Path(self.temp_dir.name) / "specimen_b.png")
            self.project_manager.project_data["labels"] = {
                image_a: {
                    "trajectories": {
                        "Mandible": {
                            "frames": [{"box": [1, 1, 10, 10]}, {"box": [2, 2, 9, 9]}],
                            "parent_context": {
                                "parent_part": "Head",
                                "parent_box": [5, 5, 80, 60],
                                "source": "manual",
                            },
                        }
                    }
                },
                image_b: {
                    "trajectories": {
                        "Mandible": {
                            "frames": [{"box": [3, 3, 8, 8]}],
                            "parent_context": {
                                "parent_part": "Head",
                                "parent_box": [6, 6, 81, 61],
                                "source": "auto",
                            },
                        }
                    }
                },
            }

            route_panel = window.route_settings_panel
            route_panel.refresh_route_table()
            dialog = main_module.ModelSettingsDialog(
                {
                    "epochs": 5,
                    "batch": 2,
                    "lr": 1e-4,
                    "wd": 1e-4,
                    "conf": 0.1,
                    "adapt": 0.4,
                    "pad": 0.4,
                    "noise_floor": 0.15,
                    "poly_epsilon": 2.0,
                    "taxonomy": ["Head", "Mesosoma", "Gaster", "Mandible"],
                    "locator_scope": ["Head", "Mesosoma", "Gaster"],
                },
                lang="en",
                parent=window,
                route_panel=route_panel,
            )
            dialog.show()
            self.app.processEvents()

            route_group = dialog.findChild(QWidget, "modelSettingsRoutePanel")
            self.assertIsNotNone(route_group)
            self.assertEqual(route_panel.parentWidget().objectName(), "modelSettingsRoutePanel")
            self.assertEqual(dialog.tabs.tabText(dialog.advanced_extensions_tab_index), "Advanced Extensions")
            self.assertGreater(dialog.advanced_extensions_tab_index, dialog.inference_tab_index)
            advanced_tab = dialog.tabs.widget(dialog.advanced_extensions_tab_index).widget()
            parent_tab = dialog.tabs.widget(dialog.parent_tab_index).widget()
            child_tab = dialog.tabs.widget(dialog.child_tab_index).widget()
            self.assertIsNotNone(advanced_tab.findChild(QWidget, "modelSettingsModelSourceSwitchPanel"))
            self.assertIsNotNone(parent_tab.findChild(QWidget, "modelSettingsParentSourceSummary"))
            self.assertIsNotNone(child_tab.findChild(QWidget, "modelSettingsChildSourceSummary"))
            self.assertIsNotNone(advanced_tab.findChild(QWidget, "modelSettingsParentExtensionPanel"))
            self.assertIsNotNone(advanced_tab.findChild(QWidget, "modelSettingsExternalBlinkPanel"))
            vlm_panel = dialog.findChild(QWidget, "modelSettingsVlmPreannotationPanel")
            self.assertIsNotNone(vlm_panel)
            vlm_details = dialog.findChild(QWidget, "modelSettingsVlmDetailsPanel")
            self.assertIsNotNone(vlm_details)
            self.assertFalse(vlm_details.isVisible())
            self.assertIsNotNone(dialog.findChild(main_module.QToolButton, "modelSettingsVlmDetailToggle"))
            self.assertGreaterEqual(len(dialog.vlm_target_part_checks), 4)
            dataset_panel = child_tab.findChild(QWidget, "modelSettingsBlinkDatasetPanel")
            self.assertIsNotNone(dataset_panel)
            dataset_tree = child_tab.findChild(QTreeWidget, "modelSettingsBlinkDatasetTree")
            self.assertIsNotNone(dataset_tree)
            self.assertEqual(dataset_tree.topLevelItemCount(), 1)
            dataset_item = dataset_tree.topLevelItem(0)
            self.assertEqual(dataset_item.text(0), "Head -> Mandible")
            self.assertEqual(dataset_item.text(1), "2")
            self.assertEqual(dataset_item.text(2), "3")
            self.assertIn("manual", dataset_item.text(3))
            self.assertIn("auto", dataset_item.text(3))
            dataset_tree.setCurrentItem(dataset_item)
            details = dialog._format_blink_dataset_details(dialog._selected_blink_dataset_summary())
            self.assertIn(image_a, details)
            self.assertIn("Parent box", details)
            with patch.object(main_module.QDialog, "exec", return_value=main_module.QDialog.DialogCode.Accepted) as exec_dialog:
                dialog._show_blink_dataset_details()
            exec_dialog.assert_called_once()
            with patch.object(model_settings_dataset_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):
                dialog._delete_selected_blink_dataset()
            self.assertEqual(self.project_manager.project_data["labels"][image_a].get("trajectories", {}), {})
            self.assertEqual(self.project_manager.project_data["labels"][image_b].get("trajectories", {}), {})
            self.assertIn("No Blink shrink trajectory datasets", dataset_tree.topLevelItem(0).text(0))
            self.assertIsNotNone(dialog.spin_blink_auto_shrink_steps)
            self.assertIsInstance(dialog.spin_blink_auto_shrink_steps, main_module.NoWheelSpinBox)
            self.assertEqual(dialog.spin_blink_auto_shrink_steps.value(), 20)
            self.assertIsInstance(dialog.spin_vlm_concurrency, main_module.NoWheelSpinBox)
            self.assertIsNotNone(dialog.combo_blink_training_strategy)
            strategy_index = dialog.combo_blink_training_strategy.findData("two_stage_full_then_inside")
            self.assertGreaterEqual(strategy_index, 0)
            dialog.combo_blink_training_strategy.setCurrentIndex(strategy_index)
            dialog.spin_blink_auto_shrink_steps.setValue(35)
            values = dialog.get_values()
            self.assertEqual(values["blink_auto_shrink_steps"], 35)
            self.assertEqual(values["blink_training_strategy"], "two_stage_full_then_inside")
            active_profile = values["model_profiles"]["profiles"][0]
            self.assertEqual(active_profile["child_backend_defaults"]["auto_shrink_steps"], 35)
            self.assertEqual(active_profile["child_backend_defaults"]["training_strategy"], "two_stage_full_then_inside")
            self.assertIn("Deleting a route removes only this project record", route_panel.note_label.text())
            self.assertEqual(route_panel.route_tree.objectName(), "projectRouteTree")
            self.assertGreaterEqual(route_panel.route_tree.minimumHeight(), 360)
            parent_item = route_panel._find_parent_item("Head")
            self.assertIsNotNone(parent_item)
            route_item = route_panel._find_route_item("Head", "Mandible")
            self.assertIsNotNone(route_item)
            self.assertEqual(route_item.text(3), "ViT-B Blink Expert")
            self.assertEqual(route_item.text(5), "Expert not appointed yet")
            self.assertEqual(route_item.text(6), "No appointed expert")
            self.assertEqual(route_item.text(7), "Blink candidate")
            self.assertIn("Project routes below control which parent -> child expert links are available", dialog.lbl_cascade_note.text())
        finally:
            try:
                dialog.hide()
                dialog.deleteLater()
            except Exception:
                pass
            window.deleteLater()

    def test_settings_numeric_controls_ignore_mouse_wheel(self):
        class DummyWheelEvent:
            def __init__(self):
                self.ignored = False

            def ignore(self):
                self.ignored = True

        spin = main_module.NoWheelSpinBox()
        spin.setRange(1, 100)
        spin.setValue(12)
        spin_event = DummyWheelEvent()
        spin.wheelEvent(spin_event)
        self.assertTrue(spin_event.ignored)
        self.assertEqual(spin.value(), 12)

        slider = main_module.NoWheelSlider(main_module.Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(42)
        slider_event = DummyWheelEvent()
        slider.wheelEvent(slider_event)
        self.assertTrue(slider_event.ignored)
        self.assertEqual(slider.value(), 42)

    def test_route_panel_can_delete_selected_child_expert_file(self):
        expert_dir = self.weights_dir / "experts" / "Mandible"
        expert_dir.mkdir(parents=True, exist_ok=True)
        expert_path = expert_dir / "expert_v20260501_090000.pth"
        expert_path.write_bytes(b"expert")

        window = self.make_main_window()
        try:
            self.project_manager.project_data["taxonomy"] = ["Head", "Mesosoma", "Gaster", "Mandible"]
            self.project_manager.project_data["cascade_routes"] = {
                "version": "project-v2",
                "routes": [
                    {
                        "parent": "Head",
                        "child": "Mandible",
                        "enabled": True,
                        "appointed_expert": {
                            "expert_id": "Mandible/expert_v20260501_090000.pth",
                            "expert_part": "Mandible",
                            "expert_filename": "expert_v20260501_090000.pth",
                        },
                        "expert_id": "Mandible/expert_v20260501_090000.pth",
                        "expert_part": "Mandible",
                        "expert_filename": "expert_v20260501_090000.pth",
                        "expert_candidates": [],
                    }
                ],
            }
            window.engine.cascade_manager.loaded_experts["cached-model"] = object()

            route_panel = window.route_settings_panel
            route_panel.refresh_route_table()
            route_item = route_panel._find_route_item("Head", "Mandible")
            self.assertIsNotNone(route_item)
            self.assertEqual(route_item.childCount(), 1)
            expert_item = route_item.child(0)
            route_panel.route_tree.setCurrentItem(expert_item)
            route_panel.update_action_buttons()

            self.assertTrue(route_panel.btn_delete_expert_file.isEnabled())
            self.assertEqual(route_panel.btn_delete_route.text(), "Delete Route")
            self.assertEqual(route_panel.btn_delete_expert_file.text(), "Delete Expert File")

            with patch.object(
                route_management_module,
                "themed_yes_no_question",
                return_value=main_module.QMessageBox.Yes,
            ):
                route_panel.delete_selected_expert_file()

            self.assertFalse(expert_path.exists())
            self.assertEqual(len(self.project_manager.project_data["cascade_routes"]["routes"]), 1)
            refreshed_route_item = route_panel._find_route_item("Head", "Mandible")
            self.assertEqual(refreshed_route_item.text(5), "Expert not appointed yet")
            self.assertEqual(refreshed_route_item.text(4), "Not appointed")
            self.assertEqual(refreshed_route_item.childCount(), 1)
            self.assertEqual(refreshed_route_item.child(0).text(5), "Expert not appointed yet")
            route_record = self.project_manager.project_data["cascade_routes"]["routes"][0]
            self.assertIsNone(route_record.get("expert_id"))
            self.assertEqual(route_record.get("expert_candidates"), [])
            self.assertEqual(window.engine.cascade_manager.loaded_experts, {})
        finally:
            window.deleteLater()

    def test_route_panel_can_edit_selected_child_expert_note(self):
        expert_dir = self.weights_dir / "experts" / "Mandible"
        expert_dir.mkdir(parents=True, exist_ok=True)
        expert_path = expert_dir / "expert_v20260501_090000.pth"
        expert_path.write_bytes(b"expert")

        window = self.make_main_window()
        try:
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager.project_data["cascade_routes"] = {
                "version": "project-v2",
                "routes": [
                    {
                        "parent": "Head",
                        "child": "Mandible",
                        "enabled": True,
                        "appointed_expert": {},
                        "expert_candidates": [
                            {
                                "expert_id": "Mandible/expert_v20260501_090000.pth",
                                "expert_part": "Mandible",
                                "expert_filename": "expert_v20260501_090000.pth",
                            }
                        ],
                    }
                ],
            }

            route_panel = window.route_settings_panel
            route_panel.refresh_route_table()
            route_item = route_panel._find_route_item("Head", "Mandible")
            self.assertIsNotNone(route_item)
            expert_item = route_item.child(0)
            route_panel.route_tree.setCurrentItem(expert_item)
            route_panel.update_action_buttons()

            self.assertTrue(route_panel.btn_edit_expert_note.isEnabled())
            with patch.object(
                main_module.QInputDialog,
                "getText",
                return_value=("small-head validation run", True),
            ):
                route_panel.edit_selected_expert_note()

            notes_path = self.weights_dir / "experts" / "expert_notes.json"
            self.assertTrue(notes_path.exists())
            with notes_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(
                payload["notes"]["Mandible/expert_v20260501_090000.pth"],
                "small-head validation run",
            )
            refreshed_expert = route_panel._find_expert_item(
                "Head",
                "Mandible",
                "Mandible/expert_v20260501_090000.pth",
            )
            self.assertIsNotNone(refreshed_expert)
            self.assertIn("small-head validation run", refreshed_expert.text(4))
        finally:
            window.deleteLater()

    def test_model_settings_exposes_locator_scope_selection(self):
        dialog = main_module.ModelSettingsDialog(
            {
                "epochs": 5,
                "batch": 2,
                "lr": 1e-4,
                "wd": 1e-4,
                "conf": 0.1,
                "adapt": 0.4,
                "pad": 0.4,
                "noise_floor": 0.15,
                "poly_epsilon": 2.0,
                "runtime_device": "cpu",
                "taxonomy": ["Leaf", "Flower", "Fruit", "Stamen"],
                "locator_scope": ["Leaf", "Flower"],
                "parent_box_aspect_ratios": {"Leaf": 1.2, "Flower": 1.5},
            },
            lang="en",
        )
        try:
            runtime_group = dialog.findChild(QWidget, "modelSettingsRuntimeDevicePanel")
            self.assertIsNotNone(runtime_group)
            device_combo = runtime_group.findChild(main_module.QComboBox)
            self.assertIsNotNone(device_combo)
            self.assertEqual(device_combo.currentData(), "cpu")
            device_combo.setCurrentIndex(device_combo.findData("cuda"))
            self.assertEqual(dialog.get_values()["runtime_device"], "cuda")

            locator_group = dialog.findChild(QWidget, "modelSettingsLocatorScopePanel")
            self.assertIsNotNone(locator_group)
            checks = {check.text(): check for check in locator_group.findChildren(main_module.QCheckBox)}
            self.assertEqual(set(checks), {"Leaf", "Flower", "Fruit", "Stamen"})
            self.assertTrue(checks["Leaf"].isChecked())
            self.assertTrue(checks["Flower"].isChecked())
            self.assertFalse(checks["Fruit"].isChecked())
            checks["Flower"].setChecked(False)
            checks["Fruit"].setChecked(True)
            self.assertEqual(dialog.get_values()["locator_scope"], ["Leaf", "Fruit"])
            ratio_group = dialog.findChild(QWidget, "modelSettingsParentBoxRatioPanel")
            self.assertIsNotNone(ratio_group)
            ratio_width, ratio_height = dialog.parent_box_ratio_inputs["Leaf"]
            self.assertEqual(ratio_width.text(), "6")
            self.assertEqual(ratio_height.text(), "5")
            flower_width, flower_height = dialog.parent_box_ratio_inputs["Flower"]
            self.assertEqual(flower_width.text(), "3")
            self.assertEqual(flower_height.text(), "2")
            ratio_width.setText("7")
            ratio_height.setText("5")
            self.assertEqual(dialog.get_values()["parent_box_aspect_ratios"]["Leaf"], 1.4)
        finally:
            dialog.deleteLater()

    def test_model_settings_parent_box_ratio_rejects_partial_width_height(self):
        dialog = main_module.ModelSettingsDialog(
            {
                "epochs": 5,
                "batch": 2,
                "lr": 1e-4,
                "wd": 1e-4,
                "conf": 0.1,
                "adapt": 0.4,
                "pad": 0.4,
                "noise_floor": 0.15,
                "poly_epsilon": 2.0,
                "taxonomy": ["Leaf"],
                "locator_scope": ["Leaf"],
                "parent_box_aspect_ratios": {},
            },
            lang="en",
        )
        try:
            ratio_width, ratio_height = dialog.parent_box_ratio_inputs["Leaf"]
            ratio_width.setText("4")
            ratio_height.setText("")
            self.assertIn("Leaf", "\n".join(dialog._parent_box_aspect_ratio_errors()))
            ratio_height.setText("3")
            self.assertEqual(dialog._parent_box_aspect_ratio_errors(), [])
            self.assertAlmostEqual(dialog.get_values()["parent_box_aspect_ratios"]["Leaf"], 4 / 3)
        finally:
            dialog.deleteLater()

    def test_main_window_run_prediction_omits_retired_cascade_toggle_argument(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        window = self.make_main_window()
        try:
            image_key = str(image_path)
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }
            self.project_manager.project_data["cascade_routes"] = {
                "version": "project-v2",
                "routes": [
                    {
                        "parent": "Head",
                        "child": "Mandible",
                        "enabled": True,
                        "appointed_expert": {
                            "expert_id": "Mandible/expert_v20260501_090000.pth",
                            "expert_part": "Mandible",
                            "expert_filename": "expert_v20260501_090000.pth",
                        },
                        "expert_candidates": [
                            {
                                "expert_id": "Mandible/expert_v20260501_090000.pth",
                                "expert_part": "Mandible",
                                "expert_filename": "expert_v20260501_090000.pth",
                            }
                        ],
                        "expert_id": "Mandible/expert_v20260501_090000.pth",
                        "expert_part": "Mandible",
                        "expert_filename": "expert_v20260501_090000.pth",
                        "registration_source": "blink_candidate",
                    }
                ],
            }

            window.file_list.clear()
            window.file_list.addItem(Path(image_key).name)
            window.current_image = image_key
            window.run_prediction()

            self.assertEqual(len(self.engine.predict_calls), 1)
            call = self.engine.predict_calls[0]
            args = call["args"]
            kwargs = call["kwargs"]
            self.assertEqual(args, ())
            self.assertEqual(kwargs["project_route_manifest"]["routes"][0]["child"], "Mandible")
            self.assertIn("model_profile_context", kwargs)
        finally:
            window.deleteLater()

    def test_parent_prediction_can_replace_unconfirmed_vlm_draft_but_keeps_confirmed_label(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["taxonomy"] = ["Head"]
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {"Head": [[10.0, 10.0], [20.0, 10.0], [20.0, 20.0]]},
                    "boxes": {},
                    "auto_boxes": {"Head": [10.0, 10.0, 20.0, 20.0]},
                    "auto_box_meta": {"Head": {"source": "vlm_first_mile", "review_status": "draft"}},
                    "descriptions": {"Head": "Auto-Annotated"},
                    "status": "labeled",
                    "genus": "Unknown",
                }
            }
            prediction = {
                "polygons": {"Head": [[30.0, 30.0], [60.0, 30.0], [60.0, 60.0]]},
                "auto_boxes": {"Head": [30.0, 30.0, 60.0, 60.0]},
            }

            saved, total = window._apply_prediction_to_project(image_key, prediction, only_new=True, save=False)

            labels = self.project_manager.project_data["labels"][image_key]
            self.assertEqual((saved, total), (1, 1))
            self.assertEqual(labels["parts"]["Head"], prediction["polygons"]["Head"])
            self.assertEqual(labels["auto_boxes"]["Head"], prediction["auto_boxes"]["Head"])
            self.assertEqual(labels["auto_box_meta"]["Head"]["source"], "model_prediction")

            labels["descriptions"].pop("Head", None)
            labels["auto_box_meta"]["Head"]["review_status"] = "confirmed"
            confirmed_points = [[40.0, 40.0], [50.0, 40.0], [50.0, 50.0]]
            labels["parts"]["Head"] = confirmed_points
            saved, total = window._apply_prediction_to_project(
                image_key,
                {
                    "polygons": {"Head": [[70.0, 70.0], [80.0, 70.0], [80.0, 80.0]]},
                    "auto_boxes": {"Head": [70.0, 70.0, 80.0, 80.0]},
                },
                only_new=True,
                save=False,
            )

            self.assertEqual((saved, total), (0, 1))
            self.assertEqual(labels["parts"]["Head"], confirmed_points)
        finally:
            window.deleteLater()

    def test_vlm_does_not_replace_model_prediction_draft(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["taxonomy"] = ["Head"]
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {"Head": [[30.0, 30.0], [60.0, 30.0], [60.0, 60.0]]},
                    "boxes": {},
                    "auto_boxes": {"Head": [30.0, 30.0, 60.0, 60.0]},
                    "auto_box_meta": {"Head": {"source": "model_prediction", "review_status": "draft"}},
                    "descriptions": {"Head": "Auto-Annotated"},
                    "status": "labeled",
                    "genus": "Unknown",
                }
            }

            ok, mode = window._apply_vlm_candidate(
                image_key,
                image,
                {"part": "Head", "box_xyxy": [70.0, 70.0, 90.0, 90.0], "confidence": 0.95},
                {"report_path": "vlm_after_model.json"},
            )

            labels = self.project_manager.project_data["labels"][image_key]
            self.assertFalse(ok)
            self.assertEqual(mode, "already_labeled")
            self.assertEqual(labels["auto_boxes"]["Head"], [30.0, 30.0, 60.0, 60.0])
            self.assertEqual(labels["auto_box_meta"]["Head"]["source"], "model_prediction")
        finally:
            window.deleteLater()

    def test_parent_prediction_can_replace_box_only_vlm_draft(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["taxonomy"] = ["Head"]
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {"Head": [10.0, 10.0, 40.0, 35.0]},
                    "auto_box_meta": {"Head": {"source": "vlm_first_mile", "review_status": "draft"}},
                    "descriptions": {"Head": "Auto-Annotated"},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }
            prediction = {
                "polygons": {"Head": [[20.0, 20.0], [70.0, 20.0], [70.0, 55.0], [20.0, 55.0]]},
                "auto_boxes": {"Head": [20.0, 20.0, 70.0, 55.0]},
            }

            saved, total = window._apply_prediction_to_project(image_key, prediction, only_new=True, save=False)

            labels = self.project_manager.project_data["labels"][image_key]
            self.assertEqual((saved, total), (1, 1))
            self.assertEqual(labels["parts"]["Head"], prediction["polygons"]["Head"])
            self.assertEqual(labels["auto_boxes"]["Head"], prediction["auto_boxes"]["Head"])
            self.assertEqual(labels["auto_box_meta"]["Head"]["source"], "model_prediction")
        finally:
            window.deleteLater()

    def test_canvas_splits_vlm_and_model_auto_boxes(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["taxonomy"] = ["Head", "Mesosoma"]
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {
                        "Head": [10.0, 10.0, 50.0, 50.0],
                        "Mesosoma": [60.0, 60.0, 110.0, 110.0],
                    },
                    "auto_box_meta": {
                        "Head": {"source": "vlm_first_mile", "review_status": "draft"},
                        "Mesosoma": {"source": "model_prediction", "review_status": "draft"},
                    },
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }

            window.current_image = image_key
            window._refresh_current_canvas_boxes()

            self.assertEqual(window.canvas.vlm_boxes, {"Head": [10.0, 10.0, 50.0, 50.0]})
            self.assertEqual(window.canvas.auto_boxes, {"Mesosoma": [60.0, 60.0, 110.0, 110.0]})
        finally:
            window.deleteLater()

    def test_vlm_preannotation_can_replace_unconfirmed_draft_but_keeps_confirmed_label(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["taxonomy"] = ["Head"]
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {"Head": [[10.0, 10.0], [20.0, 10.0], [20.0, 20.0]]},
                    "boxes": {},
                    "auto_boxes": {"Head": [10.0, 10.0, 20.0, 20.0]},
                    "auto_box_meta": {"Head": {"source": "vlm_first_mile", "review_status": "draft"}},
                    "descriptions": {"Head": "Auto-Annotated"},
                    "status": "labeled",
                    "genus": "Unknown",
                }
            }

            ok, mode = window._apply_vlm_candidate(
                image_key,
                image,
                {"part": "Head", "box_xyxy": [30.0, 30.0, 60.0, 60.0], "confidence": 0.9},
                {"report_path": "rerun.json"},
            )

            labels = self.project_manager.project_data["labels"][image_key]
            self.assertTrue(ok)
            self.assertEqual(mode, "polygon")
            self.assertEqual(labels["parts"]["Head"], [[30.0, 30.0], [60.0, 30.0], [60.0, 60.0], [30.0, 60.0]])
            self.assertEqual(labels["auto_boxes"]["Head"], [30.0, 30.0, 60.0, 60.0])
            self.assertEqual(labels["auto_box_meta"]["Head"]["review_status"], "draft")

            labels["descriptions"].pop("Head", None)
            labels["auto_box_meta"]["Head"]["review_status"] = "confirmed"
            confirmed_points = [[40.0, 40.0], [50.0, 40.0], [50.0, 50.0]]
            labels["parts"]["Head"] = confirmed_points
            ok, mode = window._apply_vlm_candidate(
                image_key,
                image,
                {"part": "Head", "box_xyxy": [70.0, 70.0, 90.0, 90.0], "confidence": 0.95},
                {"report_path": "rerun_confirmed.json"},
            )

            self.assertFalse(ok)
            self.assertEqual(mode, "already_labeled")
            self.assertEqual(labels["parts"]["Head"], confirmed_points)
        finally:
            window.deleteLater()

    def test_workbench_agent_context_includes_model_profile_and_route_backend(self):
        window = self.make_main_window()
        try:
            window.project.project_data["taxonomy"].append("Mandible")
            window.project.project_data["cascade_routes"] = {
                "version": "project-v2",
                "routes": [
                    {
                        "parent": "Head",
                        "child": "Mandible",
                        "enabled": True,
                        "expert_backend": "heatmap_blink",
                        "expert_id": "Mandible/expert_v20260602_120000.pth",
                        "expert_part": "Mandible",
                        "expert_filename": "expert_v20260602_120000.pth",
                        "appointed_expert": {
                            "expert_backend": "heatmap_blink",
                            "expert_id": "Mandible/expert_v20260602_120000.pth",
                        },
                        "expert_candidates": [],
                    }
                ],
            }

            context = window._collect_image_workbench_agent_context()
            self.assertEqual(context["active_model_profile_id"], "builtin_heatmap_default")
            self.assertEqual(context["parent_backend"], "builtin_locator_sam")
            self.assertEqual(context["child_backend"], "vit_b_blink")
            self.assertIn("Head->Mandible:heatmap_blink", context["route_backend_summary"])

            compact = window._compact_agent_context(context)
            self.assertEqual(compact["active_model_profile_id"], "builtin_heatmap_default")
            self.assertIn("Head->Mandible:heatmap_blink", compact["route_backend_summary"])
        finally:
            window.deleteLater()

    def test_training_success_updates_active_model_profile_parent_weights(self):
        window = self.make_main_window()
        try:
            class TrainerStub:
                training_context = {
                    "locator_weights": "locator_20260602_1200.pth",
                    "segmenter_weights": "sam_decoder_lora_20260602_1200.pth",
                }

            window.trainer = TrainerStub()
            window._on_training_success()

            self.assertEqual(
                window.project.last_profile_parent_weights["locator_weights"],
                "locator_20260602_1200.pth",
            )
            self.assertEqual(
                window.project.last_profile_parent_weights["segmenter_weights"],
                "sam_decoder_lora_20260602_1200.pth",
            )
            self.assertFalse(window.project.last_profile_parent_weights["save"])
            self.assertGreaterEqual(window.project.save_calls, 1)
        finally:
            window.deleteLater()

    def test_main_window_model_delete_buttons_are_clear_and_stateful(self):
        locator_timestamp = "20260105_1105"
        segmenter_timestamp = "20260105_1115"
        torch.save(
            {"state_dict": {}, "meta": {"locator_size": [640, 384]}},
            self.weights_dir / f"locator_{locator_timestamp}.pth",
        )
        (self.weights_dir / f"sam_decoder_lora_{segmenter_timestamp}.pth").write_bytes(b"segmenter")

        window = self.make_main_window()
        try:
            self.assertEqual(window.btn_del_locator.text(), "Del")
            self.assertEqual(window.btn_del_segmenter.text(), "Del")
            self.assertEqual(window.btn_note_locator.text(), "Note")
            self.assertEqual(window.btn_note_segmenter.text(), "Note")
            self.assertEqual(
                window.btn_del_locator.toolTip(),
                "Delete the selected locator model file from disk.",
            )
            self.assertEqual(
                window.btn_del_segmenter.toolTip(),
                "Delete the selected segmenter model file from disk.",
            )
            self.assertEqual(window.combo_locator.currentData(), locator_timestamp)
            self.assertEqual(window.combo_locator.currentText(), f"{locator_timestamp} [exact 640x384]")
            self.assertTrue(window.btn_del_locator.isEnabled())
            self.assertEqual(self.engine.load_locator_calls, [])
            self.assertEqual(window.combo_segmenter.currentData(), "BASE_SAM")
            self.assertFalse(window.btn_del_segmenter.isEnabled())
            self.assertEqual(self.engine.reset_sam_calls, 0)

            window.enter_image_workflow()
            self.assertEqual(self.engine.load_locator_calls[-1], locator_timestamp)

            segmenter_index = window.combo_segmenter.findData(segmenter_timestamp)
            self.assertGreaterEqual(segmenter_index, 0)
            window.combo_segmenter.setCurrentIndex(segmenter_index)
            self.assertTrue(window.btn_del_segmenter.isEnabled())

            base_index = window.combo_segmenter.findData("BASE_SAM")
            self.assertGreaterEqual(base_index, 0)
            window.combo_segmenter.setCurrentIndex(base_index)
            self.assertFalse(window.btn_del_segmenter.isEnabled())
        finally:
            window.deleteLater()

        (self.weights_dir / f"locator_{locator_timestamp}.pth").unlink()
        window = self.make_main_window()
        try:
            self.assertEqual(window.combo_locator.currentData(), "__no_locator__")
            self.assertFalse(window.btn_del_locator.isEnabled())
        finally:
            window.deleteLater()

    def test_main_window_parent_model_notes_are_editable_and_cleanup_on_delete(self):
        locator_timestamp = "20260105_1105"
        segmenter_timestamp = "20260105_1115"
        torch.save(
            {"state_dict": {}, "meta": {"locator_size": [640, 384]}},
            self.weights_dir / f"locator_{locator_timestamp}.pth",
        )
        (self.weights_dir / f"sam_decoder_lora_{segmenter_timestamp}.pth").write_bytes(b"segmenter")

        window = self.make_main_window()
        try:
            self.assertTrue(window.btn_note_locator.isEnabled())
            with patch.object(
                main_module.QInputDialog,
                "getText",
                return_value=("quick Head pilot", True),
            ):
                window.edit_locator_model_note()

            locator_index = window.combo_locator.findData(locator_timestamp)
            self.assertGreaterEqual(locator_index, 0)
            self.assertEqual(
                window.combo_locator.itemText(locator_index),
                f"quick Head pilot ({locator_timestamp} [exact 640x384])",
            )

            segmenter_index = window.combo_segmenter.findData(segmenter_timestamp)
            self.assertGreaterEqual(segmenter_index, 0)
            window.combo_segmenter.setCurrentIndex(segmenter_index)
            self.assertTrue(window.btn_note_segmenter.isEnabled())
            with patch.object(
                main_module.QInputDialog,
                "getText",
                return_value=("SAM LoRA trial", True),
            ):
                window.edit_segmenter_model_note()

            segmenter_index = window.combo_segmenter.findData(segmenter_timestamp)
            self.assertGreaterEqual(segmenter_index, 0)
            self.assertEqual(
                window.combo_segmenter.itemText(segmenter_index),
                f"SAM LoRA trial ({segmenter_timestamp})",
            )

            notes_path = self.weights_dir / "parent_model_notes.json"
            self.assertTrue(notes_path.exists())
            with notes_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload["notes"][f"locator_{locator_timestamp}.pth"], "quick Head pilot")
            self.assertEqual(payload["notes"][f"sam_decoder_lora_{segmenter_timestamp}.pth"], "SAM LoRA trial")

            window.combo_locator.setCurrentIndex(locator_index)
            with patch.object(
                model_management_module,
                "themed_yes_no_question",
                return_value=main_module.QMessageBox.Yes,
            ):
                window.delete_locator_model()
            with notes_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertNotIn(f"locator_{locator_timestamp}.pth", payload["notes"])
            self.assertIn(f"sam_decoder_lora_{segmenter_timestamp}.pth", payload["notes"])
        finally:
            window.deleteLater()

    def test_main_window_locator_combo_marks_legacy_and_logs_display_state(self):
        exact_timestamp = "20260105_1105"
        legacy_timestamp = "20260105_1115"
        torch.save(
            {"state_dict": {}, "meta": {"locator_size": [768, 512]}},
            self.weights_dir / f"locator_{exact_timestamp}.pth",
        )
        torch.save({"state_dict": {}}, self.weights_dir / f"locator_{legacy_timestamp}.pth")

        window = self.make_main_window()
        try:
            exact_index = window.combo_locator.findData(exact_timestamp)
            legacy_index = window.combo_locator.findData(legacy_timestamp)
            self.assertGreaterEqual(exact_index, 0)
            self.assertGreaterEqual(legacy_index, 0)
            self.assertEqual(window.combo_locator.itemText(exact_index), f"{exact_timestamp} [exact 768x512]")
            self.assertEqual(window.combo_locator.itemText(legacy_index), f"{legacy_timestamp} [legacy-512]")

            window.enter_image_workflow()
            window.combo_locator.setCurrentIndex(legacy_index)
            window.on_locator_changed(legacy_index)

            self.assertIn(f"Locator switched to: {legacy_timestamp} [legacy-512]", window.log_console.toPlainText())
        finally:
            window.deleteLater()

    def test_main_window_model_selector_rows_use_shared_grid_alignment(self):
        locator_timestamp = "20260105_1105"
        segmenter_timestamp = "20260105_1115"
        (self.weights_dir / f"locator_{locator_timestamp}.pth").write_bytes(b"locator")
        (self.weights_dir / f"sam_decoder_lora_{segmenter_timestamp}.pth").write_bytes(b"segmenter")

        window = self.make_main_window()
        try:
            window.resize(1680, 980)
            window.tabs.setCurrentIndex(1)
            window.show()
            self.app.processEvents()

            layout = window.ai_model_panel.layout()
            self.assertIsInstance(layout, QGridLayout)
            self.assertEqual(layout.columnStretch(1), 1)
            self.assertEqual(window.lbl_locator.x(), window.lbl_segmenter.x())
            self.assertEqual(window.combo_locator.x(), window.combo_segmenter.x())
            self.assertEqual(window.btn_note_locator.x(), window.btn_note_segmenter.x())
            self.assertEqual(window.btn_del_locator.x(), window.btn_del_segmenter.x())
            self.assertEqual(window.combo_locator.width(), window.combo_segmenter.width())
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_locator_delete_removes_prefixed_weight_file(self):
        locator_timestamp = "20260105_1105"
        locator_path = self.weights_dir / f"locator_{locator_timestamp}.pth"
        wrong_legacy_path = self.weights_dir / f"{locator_timestamp}.pth"
        locator_path.write_bytes(b"locator")
        wrong_legacy_path.write_bytes(b"legacy")

        window = self.make_main_window()
        try:
            self.assertEqual(window.combo_locator.currentData(), locator_timestamp)
            self.assertTrue(window.btn_del_locator.isEnabled())

            with patch.object(
                model_management_module,
                "themed_yes_no_question",
                return_value=main_module.QMessageBox.Yes,
            ):
                window.delete_locator_model()

            self.assertFalse(locator_path.exists())
            self.assertTrue(wrong_legacy_path.exists())
            self.assertEqual(window.combo_locator.currentData(), "__no_locator__")
            self.assertFalse(window.btn_del_locator.isEnabled())
            self.assertEqual(self.engine.reset_locator_calls, 0)
        finally:
            window.deleteLater()

    def test_main_window_segmenter_delete_resets_runtime_to_base(self):
        segmenter_timestamp = "20260105_1115"
        segmenter_path = self.weights_dir / f"sam_decoder_lora_{segmenter_timestamp}.pth"
        segmenter_path.write_bytes(b"segmenter")

        window = self.make_main_window()
        try:
            window.enter_image_workflow()
            baseline_reset_calls = self.engine.reset_sam_calls
            segmenter_index = window.combo_segmenter.findData(segmenter_timestamp)
            self.assertGreaterEqual(segmenter_index, 0)
            window.combo_segmenter.setCurrentIndex(segmenter_index)

            with patch.object(
                model_management_module,
                "themed_yes_no_question",
                return_value=main_module.QMessageBox.Yes,
            ):
                window.delete_segmenter_model()

            self.assertFalse(segmenter_path.exists())
            self.assertEqual(window.combo_segmenter.currentData(), "BASE_SAM")
            self.assertFalse(window.btn_del_segmenter.isEnabled())
            self.assertGreater(self.engine.reset_sam_calls, baseline_reset_calls)
        finally:
            window.deleteLater()

    def test_main_window_same_image_refresh_preserves_viewport(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {"Head": [[20.0, 20.0], [60.0, 20.0], [40.0, 55.0]]},
                    "boxes": {"Head": [18.0, 18.0, 62.0, 58.0]},
                    "auto_boxes": {},
                }
            }

            window.resize(1680, 980)
            window.show()
            self.app.processEvents()

            window.refresh_file_list()
            window.file_list.setCurrentItem(window.file_list.item(0))
            self.app.processEvents()

            window.canvas.scale = 3.25
            window.canvas.offset = QPointF(41.0, 63.0)

            updated_points = [[24.0, 24.0], [80.0, 24.0], [52.0, 70.0]]
            self.project_manager.project_data["labels"][image_key]["parts"]["Head"] = updated_points

            window.refresh_file_list()
            self.app.processEvents()

            self.assertAlmostEqual(window.canvas.scale, 3.25)
            self.assertAlmostEqual(window.canvas.offset.x(), 41.0)
            self.assertAlmostEqual(window.canvas.offset.y(), 63.0)
            self.assertEqual(window.canvas.polygons["Head"], updated_points)
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_polygon_edit_defers_save_and_skips_blink_auto_sync(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {"Head": [[20.0, 20.0], [60.0, 20.0], [40.0, 55.0]]},
                    "boxes": {"Head": [18.0, 18.0, 62.0, 58.0]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "labeled",
                    "genus": "Unknown",
                }
            }

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            window.file_list.setCurrentItem(window.file_list.item(0))
            self.app.processEvents()

            baseline_save_calls = self.project_manager.save_calls
            updated_points = [[24.0, 24.0], [80.0, 24.0], [52.0, 70.0]]

            with patch.object(window.blink_lab, "refresh_from_workbench") as blink_refresh:
                window.on_polygon_completed("Head", updated_points)
                self.app.processEvents()

                self.assertEqual(self.project_manager.save_calls, baseline_save_calls)
                self.assertTrue(window.project_save_pending)
                self.assertTrue(window.project_save_timer.isActive())
                self.assertEqual(window.canvas.polygons["Head"], updated_points)
                blink_refresh.assert_not_called()

            window._flush_pending_project_save()

            self.assertEqual(self.project_manager.save_calls, baseline_save_calls + 1)
            self.assertFalse(window.project_save_pending)
            self.assertFalse(window.project_save_timer.isActive())
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_sam_box_request_is_queued_without_direct_worker_call(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }
            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            window.file_list.setCurrentItem(window.file_list.item(0))
            self.app.processEvents()
            window.part_list.setCurrentItem(window.part_list.topLevelItem(0))
            window.init_sam()
            self.app.processEvents()

            worker = DummySamWorker.last_instance
            self.assertIsNotNone(worker)
            self.assertEqual(worker.predict_box_calls, [])

            with patch.object(worker, "predict_box", wraps=worker.predict_box) as direct_predict:
                window.on_magic_box_completed(10.0, 12.0, 80.0, 90.0)
                self.assertTrue(window.sam_busy)
                direct_predict.assert_not_called()
                self.assertEqual(worker.predict_box_calls, [])
                self.app.processEvents()
                self.assertEqual(
                    worker.predict_box_calls,
                    [(image_key, 10.0, 12.0, 80.0, 90.0)],
                )
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_polygon_edit_updates_image_list_without_full_rebuild(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }
            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            window.file_list.setCurrentItem(window.file_list.item(0))
            self.app.processEvents()

            with patch.object(window, "refresh_file_list", wraps=window.refresh_file_list) as full_refresh:
                window.on_polygon_completed("Head", [[24.0, 24.0], [80.0, 24.0], [52.0, 70.0]])
                self.app.processEvents()
                full_refresh.assert_not_called()

            self.assertEqual(window.label_project_images.text(), "PROJECT IMAGES (1/1)")
            color = window.file_list.item(0).foreground().color()
            self.assertEqual(color, QColor(get_theme_config(window.current_theme)["success"]))
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_remove_selected_images_defers_save_and_removes_visible_rows(self):
        image_paths = []
        for index in range(3):
            image_path = Path(self.temp_dir.name) / f"specimen_{index}.png"
            image = QImage(120, 90, QImage.Format_RGB32)
            image.fill(0xFFB0B0B0)
            self.assertTrue(image.save(str(image_path)))
            image_paths.append(str(image_path))

        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = list(image_paths)
            self.project_manager.project_data["labels"] = {
                image_paths[0]: {
                    "parts": {"Head": [[10.0, 10.0], [40.0, 10.0], [24.0, 30.0]]},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "labeled",
                    "genus": "Unknown",
                },
                image_paths[1]: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                },
                image_paths[2]: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                },
            }

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            for row in range(window.file_list.count()):
                item = window.file_list.item(row)
                if item.data(main_module.Qt.UserRole) == image_paths[0]:
                    item.setSelected(True)
                    window.file_list.setCurrentItem(item)
                    break
            self.app.processEvents()

            baseline_save_calls = self.project_manager.save_calls
            with patch.object(image_navigation_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes), \
                 patch.object(window, "refresh_file_list", wraps=window.refresh_file_list) as full_refresh:
                window.remove_selected_images()
                self.app.processEvents()

            self.assertEqual(self.project_manager.save_calls, baseline_save_calls)
            self.assertTrue(window.project_save_pending)
            full_refresh.assert_not_called()
            self.assertEqual(self.project_manager.project_data["images"], image_paths[1:])
            self.assertNotIn(image_paths[0], self.project_manager.project_data["labels"])
            self.assertEqual(window.current_image, image_paths[1])
            self.assertEqual(window.label_project_images.text(), "PROJECT IMAGES (0/2)")
            visible_paths = [
                window.file_list.item(row).data(main_module.Qt.UserRole)
                for row in range(window.file_list.count())
                if window.file_list.item(row).data(main_module.Qt.UserRole)
            ]
            self.assertEqual(visible_paths, image_paths[1:])
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_remove_current_middle_image_selects_next_visible_image(self):
        image_paths = []
        for index in range(4):
            image_path = Path(self.temp_dir.name) / f"specimen_{index}.png"
            image = QImage(120, 90, QImage.Format_RGB32)
            image.fill(0xFFB0B0B0)
            self.assertTrue(image.save(str(image_path)))
            image_paths.append(str(image_path))

        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = list(image_paths)
            self.project_manager.project_data["labels"] = {
                path: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
                for path in image_paths
            }

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            window.file_list.clearSelection()
            for row in range(window.file_list.count()):
                item = window.file_list.item(row)
                if item.data(main_module.Qt.UserRole) == image_paths[1]:
                    item.setSelected(True)
                    window.file_list.setCurrentItem(item)
                    break
            self.app.processEvents()

            with patch.object(image_navigation_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):
                window.remove_selected_images()
                self.app.processEvents()

            self.assertEqual(window.current_image, image_paths[2])
            self.assertEqual(window.file_list.currentItem().data(main_module.Qt.UserRole), image_paths[2])
            visible_paths = [
                window.file_list.item(row).data(main_module.Qt.UserRole)
                for row in range(window.file_list.count())
                if window.file_list.item(row).data(main_module.Qt.UserRole)
            ]
            self.assertEqual(visible_paths, [image_paths[0], image_paths[2], image_paths[3]])
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_remove_current_last_image_selects_previous_visible_image(self):
        image_paths = []
        for index in range(3):
            image_path = Path(self.temp_dir.name) / f"specimen_tail_{index}.png"
            image = QImage(120, 90, QImage.Format_RGB32)
            image.fill(0xFFB0B0B0)
            self.assertTrue(image.save(str(image_path)))
            image_paths.append(str(image_path))

        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = list(image_paths)
            self.project_manager.project_data["labels"] = {
                path: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
                for path in image_paths
            }

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            window.file_list.clearSelection()
            for row in range(window.file_list.count()):
                item = window.file_list.item(row)
                if item.data(main_module.Qt.UserRole) == image_paths[2]:
                    item.setSelected(True)
                    window.file_list.setCurrentItem(item)
                    break
            self.app.processEvents()

            with patch.object(image_navigation_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):
                window.remove_selected_images()
                self.app.processEvents()

            self.assertEqual(window.current_image, image_paths[1])
            self.assertEqual(window.file_list.currentItem().data(main_module.Qt.UserRole), image_paths[1])
            visible_paths = [
                window.file_list.item(row).data(main_module.Qt.UserRole)
                for row in range(window.file_list.count())
                if window.file_list.item(row).data(main_module.Qt.UserRole)
            ]
            self.assertEqual(visible_paths, image_paths[:2])
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_move_images_to_group_defers_save(self):
        image_paths = []
        for index in range(2):
            image_path = Path(self.temp_dir.name) / f"specimen_{index}.png"
            image = QImage(120, 90, QImage.Format_RGB32)
            image.fill(0xFFB0B0B0)
            self.assertTrue(image.save(str(image_path)))
            image_paths.append(str(image_path))

        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = list(image_paths)
            self.project_manager.project_data["labels"] = {
                path: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
                for path in image_paths
            }
            self.project_manager.project_data["image_groups"] = {
                "custom_groups": [{"id": "review_batch", "name": "Review batch"}]
            }

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            self.app.processEvents()

            baseline_save_calls = self.project_manager.save_calls
            window.move_images_to_group([image_paths[0]], "review_batch")
            self.app.processEvents()

            self.assertEqual(self.project_manager.save_calls, baseline_save_calls)
            self.assertTrue(window.project_save_pending)
            provenance = self.project_manager.project_data["image_provenance"][image_paths[0]]
            self.assertEqual(provenance["manual_image_group"], "review_batch")
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_training_scope_limits_parent_training_preflight_to_selected_group(self):
        image_paths = []
        for index in range(3):
            image_path = Path(self.temp_dir.name) / f"train_scope_{index}.png"
            image = QImage(120, 90, QImage.Format_RGB32)
            image.fill(0xFFB0B0B0)
            self.assertTrue(image.save(str(image_path)))
            image_paths.append(str(image_path))

        window = self.make_main_window()
        try:
            self.project_manager.project_data["taxonomy"] = ["Head", "Mandible"]
            self.project_manager._is_sqlite_project = True
            self.project_manager.project_data["locator_scope"] = ["Head"]
            self.engine.current_num_classes = 1
            self.project_manager.project_data["images"] = list(image_paths)
            self.project_manager.project_data["image_groups"] = {
                "custom_groups": [{"id": "quick_check", "name": "Quick check"}]
            }
            self.project_manager.project_data["labels"] = {
                path: {
                    "parts": {"Head": [[10.0, 10.0], [45.0, 10.0], [24.0, 45.0]]},
                    "boxes": {"Head": [8.0, 8.0, 48.0, 48.0]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "labeled",
                    "genus": "Unknown",
                }
                for path in image_paths
            }
            self.project_manager.set_image_provenance(
                image_paths[0],
                {"manual_image_group": "quick_check"},
                save=False,
            )
            self.project_manager.set_image_provenance(
                image_paths[1],
                {"manual_image_group": "quick_check"},
                save=False,
            )

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            self.app.processEvents()

            group_index = window.combo_training_scope.findData("quick_check")
            self.assertGreaterEqual(group_index, 0)
            window.combo_training_scope.setCurrentIndex(group_index)

            launched = {}

            def fake_launch(preflight, tax, locator_scope, train_segmenter=True, training_scope=None):
                launched["preflight"] = dict(preflight)
                launched["tax"] = list(tax)
                launched["locator_scope"] = list(locator_scope)
                launched["training_scope"] = dict(training_scope or {})

            with patch.object(window, "_show_structured_training_preflight", return_value=True), \
                 patch.object(window, "_confirm_legacy_locator_selection_if_needed", return_value=True), \
                 patch.object(window, "ensure_locator_preloaded"), \
                 patch.object(window, "ensure_sam_preloaded"), \
                 patch.object(window, "_launch_training_with_preflight", side_effect=fake_launch):
                window.run_training()

            self.assertEqual(launched["training_scope"]["scope_id"], "quick_check")
            self.assertEqual(launched["training_scope"]["images"], image_paths[:2])
            self.assertEqual(launched["preflight"]["training_scope_id"], "quick_check")
            self.assertEqual(launched["preflight"]["training_scope_label"], "Quick check")
            self.assertEqual(launched["preflight"]["training_scope_image_count"], 2)
            preflight_paths = {sample[0] for sample in launched["preflight"]["locator_samples"]}
            self.assertEqual(preflight_paths, set(image_paths[:2]))
            self.assertNotIn(image_paths[2], preflight_paths)
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_manual_polygon_edit_clears_auto_annotated_blocker(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {"Head": [[20.0, 20.0], [60.0, 20.0], [40.0, 55.0]]},
                    "boxes": {},
                    "auto_boxes": {"Head": [20.0, 20.0, 80.0, 68.0]},
                    "auto_box_meta": {"Head": {"source": "vlm_first_mile", "review_status": "draft"}},
                    "descriptions": {"Head": "Auto-Annotated"},
                    "status": "labeled",
                    "genus": "Unknown",
                }
            }

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            window.file_list.setCurrentItem(window.file_list.item(0))
            self.app.processEvents()
            window.desc_box.setPlainText("Auto-Annotated")

            updated_points = [[24.0, 24.0], [80.0, 24.0], [52.0, 70.0]]
            window.on_polygon_completed("Head", updated_points)
            self.app.processEvents()

            labels = self.project_manager.project_data["labels"][image_key]
            self.assertNotIn("Head", labels.get("descriptions", {}))
            self.assertEqual(labels["parts"]["Head"], updated_points)
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_accept_current_ai_drafts_requires_confirmation(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {"Head": [[20.0, 20.0], [60.0, 20.0], [40.0, 55.0]]},
                    "boxes": {},
                    "auto_boxes": {"Head": [20.0, 20.0, 80.0, 68.0]},
                    "auto_box_meta": {"Head": {"source": "vlm_first_mile", "review_status": "draft"}},
                    "descriptions": {"Head": "Auto-Annotated"},
                    "status": "labeled",
                    "genus": "Unknown",
                }
            }

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            window.file_list.setCurrentItem(window.file_list.item(0))
            self.app.processEvents()

            with patch.object(
                vlm_module,
                "themed_yes_no_question",
                return_value=main_module.QMessageBox.No,
            ) as confirm:
                window.accept_current_image_ai_drafts()
            confirm.assert_called_once()
            self.assertEqual(self.project_manager.project_data["labels"][image_key]["descriptions"]["Head"], "Auto-Annotated")

            with patch.object(
                vlm_module,
                "themed_yes_no_question",
                return_value=main_module.QMessageBox.Yes,
            ) as confirm:
                window.accept_current_image_ai_drafts()
            confirm.assert_called_once()
            labels = self.project_manager.project_data["labels"][image_key]
            self.assertNotIn("Head", labels.get("descriptions", {}))
            self.assertEqual(labels["auto_box_meta"]["Head"]["review_status"], "confirmed")
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_accept_current_ai_drafts_updates_list_without_full_rebuild(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {"Head": [[20.0, 20.0], [60.0, 20.0], [40.0, 55.0]]},
                    "boxes": {},
                    "auto_boxes": {"Head": [20.0, 20.0, 80.0, 68.0]},
                    "auto_box_meta": {"Head": {"source": "vlm_first_mile", "review_status": "draft"}},
                    "descriptions": {"Head": "Auto-Annotated"},
                    "status": "labeled",
                    "genus": "Unknown",
                }
            }

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            window.file_list.setCurrentItem(window.file_list.item(0))
            self.app.processEvents()

            baseline_save_calls = self.project_manager.save_calls
            with patch.object(
                vlm_module,
                "themed_yes_no_question",
                return_value=main_module.QMessageBox.Yes,
            ), patch.object(window, "refresh_file_list", wraps=window.refresh_file_list) as full_refresh:
                window.accept_current_image_ai_drafts()
                self.app.processEvents()

            full_refresh.assert_not_called()
            self.assertEqual(self.project_manager.save_calls, baseline_save_calls)
            self.assertTrue(window.project_save_pending)
            self.assertEqual(window.label_project_images.text(), "PROJECT IMAGES (1/1)")
            self.assertEqual(window.file_list.item(0).foreground().color(), QColor(get_theme_config(window.current_theme)["success"]))
        finally:
            window.hide()
            window.deleteLater()

    def test_vlm_stop_clears_remaining_queue_and_finishes_cancelled_run(self):
        image_paths = []
        for index in range(3):
            image_path = Path(self.temp_dir.name) / f"vlm_stop_{index}.png"
            image = QImage(120, 90, QImage.Format_RGB32)
            image.fill(0xFFB0B0B0)
            self.assertTrue(image.save(str(image_path)))
            image_paths.append(str(image_path))

        window = self.make_main_window()
        try:
            window.vlm_preannotation_run_active = True
            window.vlm_preannotation_queue = image_paths[1:]
            window.vlm_preannotation_records = [
                {
                    "status": "passed",
                    "image_path": image_paths[0],
                    "candidates": [{"part": "Head"}],
                    "rejected": [],
                }
            ]
            window.vlm_preannotation_saved_total = 1
            window.vlm_preannotation_run_id = "stop_test"
            window.vlm_preannotation_artifacts_dir = str(Path(self.temp_dir.name) / "vlm_preannotation")
            window.vlm_preannotation_target_parts = ["Head"]
            window.vlm_preannotation_total_steps = 18
            window.vlm_preannotation_completed_steps = 6
            window.vlm_preannotation_total_images = 3
            window.vlm_preannotation_completed_images = 1
            window.vlm_preannotation_prompt_profile = main_module.default_vlm_prompt_profile()
            window.vlm_preannotation_concurrency = 1

            with patch.object(
                vlm_module,
                "themed_yes_no_question",
                return_value=main_module.QMessageBox.Yes,
            ) as confirm:
                stopped = window.request_stop_vlm_preannotation(confirm=True)

            self.assertTrue(stopped)
            confirm.assert_called_once()
            self.assertEqual(window.vlm_preannotation_queue, [])
            self.assertTrue(window.vlm_preannotation_cancel_requested)
            self.assertEqual(window.vlm_preannotation_cancelled_queued_images, 2)

            with patch.object(window, "_start_next_vlm_preannotation_image") as start_next:
                window._on_vlm_preannotation_finished()

            start_next.assert_not_called()
            self.assertFalse(window.vlm_preannotation_run_active)
            report_path = Path(window.vlm_preannotation_artifacts_dir) / "vlm_preannotation_summary_stop_test.json"
            self.assertTrue(report_path.exists())
            with report_path.open("r", encoding="utf-8") as handle:
                summary = json.load(handle)
            self.assertEqual(summary["status"], "cancelled")
            self.assertEqual(summary["cancelled_queued_image_count"], 2)
            self.assertEqual(summary["saved_box_count"], 1)
            self.assertEqual(summary["concurrency"], 1)
        finally:
            window.hide()
            window.deleteLater()

    def test_vlm_preannotation_starts_workers_up_to_configured_concurrency(self):
        image_paths = []
        for index in range(4):
            image_path = Path(self.temp_dir.name) / f"vlm_parallel_{index}.png"
            image = QImage(120, 90, QImage.Format_RGB32)
            image.fill(0xFFB0B0B0)
            self.assertTrue(image.save(str(image_path)))
            image_paths.append(str(image_path))

        window = self.make_main_window()
        try:
            window.vlm_preannotation_run_active = True
            window.vlm_preannotation_cancel_requested = False
            window.vlm_preannotation_queue = list(image_paths)
            window.vlm_preannotation_threads = []
            window.vlm_preannotation_concurrency = 2
            window.vlm_preannotation_records = []
            window.vlm_preannotation_saved_total = 0
            window.vlm_preannotation_run_id = "parallel_test"
            window.vlm_preannotation_artifacts_dir = str(Path(self.temp_dir.name) / "vlm_preannotation")
            window.vlm_preannotation_target_parts = ["Head"]
            window.vlm_preannotation_total_steps = 24
            window.vlm_preannotation_completed_steps = 0
            window.vlm_preannotation_total_images = 4
            window.vlm_preannotation_completed_images = 0
            window.vlm_preannotation_prompt_profile = main_module.default_vlm_prompt_profile()

            DummyVlmPreannotationThread.instances = []
            with patch.object(vlm_module, "VlmPreannotationThread", DummyVlmPreannotationThread):
                window._start_vlm_preannotation_workers()

            self.assertEqual(len(window.vlm_preannotation_threads), 2)
            self.assertEqual(len(DummyVlmPreannotationThread.instances), 2)
            self.assertEqual(len(window.vlm_preannotation_queue), 2)
            self.assertTrue(all(thread.isRunning() for thread in window.vlm_preannotation_threads))
        finally:
            for thread in getattr(window, "vlm_preannotation_threads", []) or []:
                thread.quit()
            window.vlm_preannotation_threads = []
            window.vlm_preannotation_thread = None
            window.hide()
            window.deleteLater()

    def test_main_window_verify_current_image_defers_save_and_updates_list(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {"Head": [[20.0, 20.0], [60.0, 20.0], [40.0, 55.0]]},
                    "boxes": {},
                    "auto_boxes": {"Head": [20.0, 20.0, 80.0, 68.0]},
                    "auto_box_meta": {"Head": {"source": "vlm_first_mile", "review_status": "draft"}},
                    "descriptions": {"Head": "Auto-Annotated"},
                    "status": "labeled",
                    "genus": "Unknown",
                }
            }

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            window.file_list.setCurrentItem(window.file_list.item(0))
            self.app.processEvents()

            baseline_save_calls = self.project_manager.save_calls
            with patch.object(window, "refresh_file_list", wraps=window.refresh_file_list) as full_refresh:
                window.verify_current_image()
                self.app.processEvents()

            full_refresh.assert_not_called()
            self.assertEqual(self.project_manager.save_calls, baseline_save_calls)
            self.assertTrue(window.project_save_pending)
            self.assertNotIn("Head", self.project_manager.project_data["labels"][image_key]["descriptions"])
            self.assertEqual(window.file_list.item(0).foreground().color(), QColor(get_theme_config(window.current_theme)["success"]))
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_accept_batch_ai_drafts_confirms_project_auto_drafts(self):
        first_image = Path(self.temp_dir.name) / "split_a.png"
        second_image = Path(self.temp_dir.name) / "split_b.png"
        for path in (first_image, second_image):
            image = QImage(240, 180, QImage.Format_RGB32)
            image.fill(0xFFB0B0B0)
            self.assertTrue(image.save(str(path)))

        first_key = str(first_image)
        second_key = str(second_image)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = [first_key, second_key]
            self.project_manager.project_data["labels"] = {
                first_key: {
                    "parts": {"Head": [[20.0, 20.0], [60.0, 20.0], [40.0, 55.0]]},
                    "boxes": {},
                    "auto_boxes": {
                        "Head": [20.0, 20.0, 80.0, 68.0],
                        "Eye": [40.0, 30.0, 52.0, 42.0],
                    },
                    "auto_box_meta": {
                        "Head": {"source": "vlm_first_mile", "review_status": "draft"},
                        "Eye": {"source": "vlm_first_mile", "review_status": "draft"},
                    },
                    "descriptions": {"Head": "Auto-Annotated", "Eye": "Auto-Annotated"},
                    "status": "labeled",
                    "genus": "Unknown",
                },
                second_key: {
                    "parts": {"Mesosoma": [[40.0, 20.0], [100.0, 20.0], [100.0, 70.0], [40.0, 70.0]]},
                    "boxes": {},
                    "auto_boxes": {"Mesosoma": [40.0, 20.0, 100.0, 70.0]},
                    "auto_box_meta": {"Mesosoma": {"source": "vlm_first_mile", "review_status": "draft"}},
                    "descriptions": {"Mesosoma": "Auto-Annotated"},
                    "status": "labeled",
                    "genus": "Unknown",
                },
            }

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            window.file_list.setCurrentItem(window.file_list.item(0))
            self.app.processEvents()

            with patch.object(
                vlm_module,
                "themed_yes_no_question",
                return_value=main_module.QMessageBox.Yes,
            ) as confirm:
                window.accept_batch_ai_drafts()
            confirm.assert_called_once()

            first_labels = self.project_manager.project_data["labels"][first_key]
            second_labels = self.project_manager.project_data["labels"][second_key]
            self.assertNotIn("Head", first_labels.get("descriptions", {}))
            self.assertEqual(first_labels["descriptions"]["Eye"], "Auto-Annotated")
            self.assertNotIn("Mesosoma", second_labels.get("descriptions", {}))
            self.assertEqual(first_labels["auto_box_meta"]["Head"]["review_status"], "confirmed")
            self.assertEqual(second_labels["auto_box_meta"]["Mesosoma"]["review_status"], "confirmed")
        finally:
            window.hide()
            window.deleteLater()

    def test_clear_ai_labels_can_target_selected_image_group(self):
        original_image = Path(self.temp_dir.name) / "original.png"
        split_image = Path(self.temp_dir.name) / "source__panel_001.png"
        for path in (original_image, split_image):
            image = QImage(160, 120, QImage.Format_RGB32)
            image.fill(0xFFB0B0B0)
            self.assertTrue(image.save(str(path)))

        original_key = str(original_image)
        split_key = str(split_image)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = [original_key, split_key]
            self.project_manager.project_data["labels"] = {
                original_key: {
                    "parts": {"Head": [[10.0, 10.0], [30.0, 10.0], [30.0, 30.0]]},
                    "boxes": {},
                    "auto_boxes": {"Head": [10.0, 10.0, 30.0, 30.0]},
                    "auto_box_meta": {"Head": {"source": "vlm_first_mile", "review_status": "draft"}},
                    "descriptions": {"Head": "Auto-Annotated"},
                    "status": "labeled",
                    "genus": "Unknown",
                },
                split_key: {
                    "parts": {"Head": [[40.0, 40.0], [80.0, 40.0], [80.0, 80.0]]},
                    "boxes": {},
                    "auto_boxes": {"Head": [40.0, 40.0, 80.0, 80.0]},
                    "auto_box_meta": {"Head": {"source": "vlm_first_mile", "review_status": "draft"}},
                    "descriptions": {"Head": "Auto-Annotated"},
                    "status": "labeled",
                    "genus": "Unknown",
                },
            }

            window.show()
            self.app.processEvents()
            window.refresh_file_list()

            with patch.object(
                window,
                "_choose_clear_ai_scope",
                return_value={"paths": [split_key], "label": "Split Crops", "count": 1},
            ), patch.object(
                prediction_module,
                "themed_yes_no_question",
                return_value=main_module.QMessageBox.Yes,
            ):
                window.clear_ai_labels()

            self.assertIn("Head", self.project_manager.project_data["labels"][original_key]["parts"])
            self.assertEqual(self.project_manager.project_data["labels"][original_key]["descriptions"]["Head"], "Auto-Annotated")
            self.assertNotIn("Head", self.project_manager.project_data["labels"][split_key]["parts"])
            self.assertNotIn("Head", self.project_manager.project_data["labels"][split_key]["descriptions"])
            self.assertTrue(window.project_save_pending)
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_image_switch_keeps_pending_polygon_edit_async(self):
        first_image = Path(self.temp_dir.name) / "specimen_a.png"
        second_image = Path(self.temp_dir.name) / "specimen_b.png"
        for path, color in ((first_image, 0xFFB0B0B0), (second_image, 0xFF90A0D0)):
            image = QImage(240, 180, QImage.Format_RGB32)
            image.fill(color)
            self.assertTrue(image.save(str(path)))

        first_key = str(first_image)
        second_key = str(second_image)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = [first_key, second_key]
            self.project_manager.project_data["labels"] = {
                first_key: {
                    "parts": {"Head": [[20.0, 20.0], [60.0, 20.0], [40.0, 55.0]]},
                    "boxes": {"Head": [18.0, 18.0, 62.0, 58.0]},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "labeled",
                    "genus": "Unknown",
                },
                second_key: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                },
            }

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            window.file_list.setCurrentItem(window.file_list.item(0))
            self.app.processEvents()

            baseline_save_calls = self.project_manager.save_calls
            window.on_polygon_completed("Head", [[24.0, 24.0], [80.0, 24.0], [52.0, 70.0]])
            self.app.processEvents()

            self.assertEqual(self.project_manager.save_calls, baseline_save_calls)
            self.assertTrue(window.project_save_pending)

            window.file_list.setCurrentItem(window.file_list.item(1))
            self.app.processEvents()

            self.assertEqual(self.project_manager.save_calls, baseline_save_calls)
            self.assertTrue(window.project_save_pending)
            self.assertEqual(window.current_image, second_key)

            self.assertFalse(window._flush_pending_project_save())
            self.assertEqual(self.project_manager.save_calls, baseline_save_calls)
            self.assertTrue(window.project_save_pending)
            self.assertTrue(window.project_save_timer.isActive())

            window._flush_pending_project_save(force=True)
            self.assertEqual(self.project_manager.save_calls, baseline_save_calls + 1)
            self.assertFalse(window.project_save_pending)
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_image_switch_does_not_save_taxon_combo_update(self):
        first_image = Path(self.temp_dir.name) / "specimen_a.png"
        second_image = Path(self.temp_dir.name) / "specimen_b.png"
        for path, color in ((first_image, 0xFFB0B0B0), (second_image, 0xFF90A0D0)):
            image = QImage(240, 180, QImage.Format_RGB32)
            image.fill(color)
            self.assertTrue(image.save(str(path)))

        first_key = str(first_image)
        second_key = str(second_image)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = [first_key, second_key]
            self.project_manager.project_data["labels"] = {
                first_key: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Formica",
                    "taxon": "Formica",
                },
                second_key: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Camponotus",
                    "taxon": "Camponotus",
                },
            }

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            window.file_list.setCurrentItem(window.file_list.item(0))
            self.app.processEvents()

            baseline_save_calls = self.project_manager.save_calls
            window.file_list.setCurrentItem(window.file_list.item(1))
            self.app.processEvents()

            self.assertEqual(window.current_image, second_key)
            self.assertEqual(window.genus_combo.currentText(), "Camponotus")
            self.assertEqual(self.project_manager.save_calls, baseline_save_calls)
            self.assertFalse(window.project_save_pending)
        finally:
            window.hide()
            window.deleteLater()

    def test_main_window_vlm_image_result_updates_list_without_full_rebuild(self):
        image_path = Path(self.temp_dir.name) / "specimen.png"
        image = QImage(240, 180, QImage.Format_RGB32)
        image.fill(0xFFB0B0B0)
        self.assertTrue(image.save(str(image_path)))

        image_key = str(image_path)
        window = self.make_main_window()
        try:
            self.project_manager.project_data["images"] = [image_key]
            self.project_manager.project_data["labels"] = {
                image_key: {
                    "parts": {},
                    "boxes": {},
                    "auto_boxes": {},
                    "descriptions": {},
                    "status": "unlabeled",
                    "genus": "Unknown",
                }
            }
            window.vlm_preannotation_records = []
            window.vlm_preannotation_saved_total = 0
            window.vlm_preannotation_run_id = "test_run"
            window.vlm_preannotation_target_parts = ["Head"]
            window.vlm_preannotation_total_images = 1
            window.vlm_preannotation_completed_images = 0
            window.vlm_preannotation_total_steps = 6
            window.vlm_preannotation_completed_steps = 0

            window.show()
            self.app.processEvents()
            window.refresh_file_list()
            window.file_list.setCurrentItem(window.file_list.item(0))
            self.app.processEvents()

            result = {
                "status": "passed",
                "image_path": image_key,
                "target_parts": ["Head"],
                "candidates": [
                    {
                        "part": "Head",
                        "box_xyxy": [10.0, 12.0, 80.0, 90.0],
                        "confidence": 0.95,
                        "reason": "test",
                    }
                ],
                "report_path": "report.json",
            }

            baseline_save_calls = self.project_manager.save_calls
            with patch.object(
                window, "refresh_file_list", wraps=window.refresh_file_list
            ) as full_refresh, patch.object(
                window, "_on_vlm_preannotation_error"
            ) as vlm_error:
                window._on_vlm_preannotation_image_result(result)
                self.app.processEvents()

            full_refresh.assert_not_called()
            vlm_error.assert_not_called()
            self.assertEqual(self.project_manager.save_calls, baseline_save_calls)
            self.assertTrue(window.project_save_pending)
            self.assertEqual(window.vlm_preannotation_saved_total, 1)
            self.assertIn("Head", self.project_manager.project_data["labels"][image_key]["parts"])
            self.assertEqual(window.label_project_images.text(), "PROJECT IMAGES (1/1)")
            self.assertEqual(window.file_list.item(0).foreground().color(), QColor(get_theme_config(window.current_theme)["success"]))
        finally:
            window.hide()
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
