# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportOptionalCall=false, reportPossiblyUnboundVariable=false, reportUninitializedInstanceVariable=false, reportConstantRedefinition=false, reportArgumentType=false, reportCallIssue=false, reportIndexIssue=false

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

has_pyside6 = False

try:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication, QWidget, QGridLayout, QDialogButtonBox, QTreeWidget
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
        QPointF = None
        QImage = None
        QTreeWidget = None
        QWidget = object
        main_module = None
        BlinkLabWidget = None
        ImageCropper = None
        PdfProcessingWidget = None
    else:
        raise
else:
    import AntSleap.main as main_module
    from AntSleap.ui.blink_lab import BlinkLabWidget
    from AntSleap.ui.cropper import ImageCropper
    from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget
    from AntSleap.ui.style import SCI_THEME

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


class DummySamWorker:
    def __init__(self, *args, **kwargs):
        self.model = None
        self.mask_generated = DummySignal()
        self.model_loaded = DummySignal()
        self.model_load_error = DummySignal()

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


class DummyCascadeManager:
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
        return None

    def list_available_experts(self):
        return []


class DummyEngine:
    def __init__(self, weights_dir):
        self.weights_dir = weights_dir
        self.locator = None
        self.parts_model = DummyPartsModel()
        self.cascade_manager = DummyCascadeManager()
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

    def load_locator(self, timestamp):
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

    def load_sam_decoder(self, timestamp):
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


class DummyProjectManager:
    def __init__(self, project_root):
        self.current_project_path = str(Path(project_root) / "dummy_project.json")
        self.save_calls = 0
        self.project_data = {
            "taxonomy": ["Head", "Mesosoma", "Gaster"],
            "images": [],
            "labels": {},
            "cascade_routes": {"version": "project-v2", "routes": []},
        }

    def create_project(self, name, directory, **kwargs):
        self.current_project_path = str(Path(directory) / f"{name}.json")
        self.project_data["images"] = []
        self.project_data["labels"] = {}

    def load_project(self, path):
        self.current_project_path = str(path)

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
                "descriptions": {},
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

    def get_genus(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("genus", "Unknown")

    def set_genus(self, image_path, genus_name):
        entry = self._ensure_label_entry(image_path)
        entry["genus"] = genus_name
        self.save_project()
        return None

    def update_label(self, image_path, part_name, points, description_text=None, box=None, auto_box=None, save=True):
        entry = self._ensure_label_entry(image_path)
        entry["parts"][part_name] = [[float(pt[0]), float(pt[1])] for pt in points]
        entry["status"] = "labeled"
        if box:
            entry["boxes"][part_name] = [float(v) for v in box]
            entry["auto_boxes"].pop(part_name, None)
        if auto_box:
            entry["auto_boxes"][part_name] = [float(v) for v in auto_box]
        if description_text:
            entry["descriptions"][part_name] = description_text
        if save:
            self.save_project()
        return None

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

    def update_trajectory(self, *args, **kwargs):
        return None

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
        ):
            self.assertIn(selector, SCI_THEME)

    def test_scientific_theme_strengthens_generic_checked_indicators_without_touching_chip_radios(self):
        self.assertIn("QRadioButton::indicator:checked", SCI_THEME)
        self.assertIn("border: 2px solid #38BDF8", SCI_THEME)
        self.assertIn("QCheckBox::indicator:checked", SCI_THEME)
        self.assertIn("background-color: #38BDF8", SCI_THEME)
        self.assertIn("QRadioButton#toolChip::indicator", SCI_THEME)
        self.assertIn("QRadioButton#scaleToolRadio::indicator", SCI_THEME)

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
            self.assertIn("background-color: #5B7486", ok_button.styleSheet())
            self.assertIn("background-color: #1E2126", cancel_button.styleSheet())

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
            patch.object(main_module, "SAMWorker", DummySamWorker),
            patch.object(main_module, "QThread", DummyThread),
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
             patch.object(main_module, "SAMWorker", DummySamWorker), \
             patch.object(main_module, "QThread", DummyThread), \
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

    def test_pdf_processing_api_inputs_keep_usable_height_when_resized(self):
        with patch.object(PdfProcessingWidget, "load_api_settings", lambda self: None), \
             patch.object(PdfProcessingWidget, "refresh_profile_list", lambda self: None), \
             patch.object(PdfProcessingWidget, "sync_runtime_controls_from_config", lambda self: None):
            widget = PdfProcessingWidget("zh")

        try:
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
            self.assertIsNotNone(window.findChild(QWidget, "workbenchAIPanel"))
            self.assertIsNotNone(window.findChild(QWidget, "workbenchAIActionPanel"))
            self.assertIsNotNone(window.findChild(QWidget, "workbenchLogsPanel"))
            self.assertEqual(window.btn_export.parentWidget().objectName(), "workbenchToolbarProjectPanel")
            self.assertEqual(window.btn_blink_entry.parentWidget().objectName(), "workbenchToolbarFlowPanel")
            self.assertEqual(window.btn_agent_from_workbench.parentWidget().objectName(), "workbenchToolbarFlowPanel")
            self.assertEqual(window.canvas.parentWidget().objectName(), "workbenchCanvasShell")
            self.assertEqual(window.btn_predict.parentWidget().objectName(), "workbenchAIActionPanel")
            self.assertEqual(window.log_console.parentWidget().objectName(), "workbenchLogsPanel")
            self.assertEqual(window.desc_box.parentWidget().objectName(), "workbenchMetadataPanel")
            self.assertIsInstance(window.part_list, QTreeWidget)
            self.assertEqual(window.part_list.objectName(), "workbenchPartTree")
            self.assertIsNone(window.findChild(QWidget, "workbenchRoutePanel"))
            self.assertEqual(window.workbench_splitter.handleWidth(), 8)
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
                main_module,
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
            self.assertIn("Deleting a route removes only this project record", route_panel.note_label.text())
            self.assertEqual(route_panel.route_tree.objectName(), "projectRouteTree")
            self.assertGreaterEqual(route_panel.route_tree.minimumHeight(), 360)
            parent_item = route_panel._find_parent_item("Head")
            self.assertIsNotNone(parent_item)
            route_item = route_panel._find_route_item("Head", "Mandible")
            self.assertIsNotNone(route_item)
            self.assertEqual(route_item.text(4), "Expert not appointed yet")
            self.assertEqual(route_item.text(5), "Blink candidate")
            self.assertIn("Project routes below control which parent -> child expert links are available", dialog.lbl_cascade_note.text())
        finally:
            try:
                dialog.hide()
                dialog.deleteLater()
            except Exception:
                pass
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
            self.assertEqual(len(args), 9)
            self.assertEqual(args[-1]["routes"][0]["child"], "Mandible")
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
                main_module,
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
                main_module,
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

    def test_main_window_image_switch_flushes_pending_polygon_edit(self):
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

            self.assertEqual(self.project_manager.save_calls, baseline_save_calls + 1)
            self.assertFalse(window.project_save_pending)
            self.assertEqual(window.current_image, second_key)
        finally:
            window.hide()
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
