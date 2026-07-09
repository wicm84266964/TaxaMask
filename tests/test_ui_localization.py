# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportUninitializedInstanceVariable=false, reportArgumentType=false, reportCallIssue=false, reportIndexIssue=false

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

import AntSleap.main as main_module
from AntSleap.main import ExportDialog, BlinkEntryDialog, ModelSettingsDialog, RouteManagementPanel, TrainingPreflightDialog, TrainingReportDialog
from AntSleap.ui.blink_lab import BlinkLabWidget
from AntSleap.ui.cropper import ImageCropper
from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget
from AntSleap.core.cascade_routes import ROUTE_BACKEND_HEATMAP_BLINK
from AntSleap.core.expert_notes import set_expert_note
from AntSleap.core.model_profiles import DEFAULT_MODEL_PROFILE_ID, PARENT_BACKEND_EXTERNAL


class DummyPartsModel:
    ultralytics_sam = None


class DummyEngine:
    def __init__(self, weights_dir, available_experts=None):
        self.weights_dir = weights_dir
        self.parts_model = DummyPartsModel()
        self.available_experts = [dict(expert) for expert in (available_experts or [])]
        self.locator_resolution = (512, 512)
        self.loaded_locator_requires_legacy_confirmation = False
        self.loaded_locator_is_legacy_512 = False
        self.loaded_locator_timestamp = None
        self.cascade_manager = self._build_cascade_manager()

    def _build_cascade_manager(self):
        engine = self

        class CascadeManager:
            def get_route_block_reason(self, route):
                return "expert_unappointed" if not route.get("expert_id") else None

            def list_available_experts(self):
                return [dict(expert) for expert in engine.available_experts]

            def resolve_route_expert_path(self, route):
                return None

        return CascadeManager()


class DummyProjectManager:
    def __init__(self):
        self.project_data = {
            "taxonomy": ["Head", "Mandible", "Eye"],
            "labels": {},
            "cascade_routes": {
                "version": "project-v1",
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
            },
        }
        self.save_calls = 0

    def get_labels(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("parts", {})

    def get_boxes(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("boxes", {})

    def get_auto_boxes(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("auto_boxes", {})

    def update_label(self, *args, **kwargs):
        return None

    def update_trajectory(self, *args, **kwargs):
        return None

    def iter_cascade_routes(self):
        return [dict(route) for route in self.project_data.get("cascade_routes", {}).get("routes", [])]

    def get_cascade_route(self, parent_part, child_part):
        for route in self.project_data.get("cascade_routes", {}).get("routes", []):
            if route.get("parent") == parent_part and route.get("child") == child_part:
                return dict(route)
        return None

    def get_active_model_profile(self):
        return {
            "profile_id": DEFAULT_MODEL_PROFILE_ID,
            "display_name": "Built-in heatmap parent + default Blink",
            "parent_backend": {"backend_type": "builtin_locator_sam"},
            "child_backend_defaults": {"backend_type": "vit_b_blink"},
        }

    def save_project(self):
        self.save_calls += 1
        return None

    def appoint_cascade_route_expert(self, parent_part, child_part, expert_id=None, save=True, **kwargs):
        updated = None
        routes = []
        for route in self.project_data.get("cascade_routes", {}).get("routes", []):
            candidate = dict(route)
            if candidate.get("parent") == parent_part and candidate.get("child") == child_part:
                candidate["appointed_expert"] = {
                    "expert_id": expert_id,
                    "expert_part": None,
                    "expert_filename": None,
                }
                if isinstance(expert_id, str) and "/" in expert_id:
                    expert_part, expert_filename = expert_id.split("/", 1)
                    candidate["appointed_expert"] = {
                        "expert_id": expert_id,
                        "expert_part": expert_part,
                        "expert_filename": expert_filename,
                    }
                    candidate["expert_part"] = expert_part
                    candidate["expert_filename"] = expert_filename
                candidate["expert_id"] = expert_id
                existing_candidates = [
                    dict(item)
                    for item in candidate.get("expert_candidates", [])
                    if isinstance(item, dict)
                ]
                new_candidates = []
                if expert_id:
                    new_candidates.append(dict(candidate["appointed_expert"]))
                for item in existing_candidates:
                    if item.get("expert_id") != expert_id:
                        new_candidates.append(item)
                candidate["expert_candidates"] = new_candidates
                updated = dict(candidate)
            routes.append(candidate)
        self.project_data["cascade_routes"]["routes"] = routes
        if updated and save:
            self.save_project()
        return updated

    def set_cascade_route_enabled(self, parent_part, child_part, enabled, save=True):
        updated = None
        routes = []
        for route in self.project_data.get("cascade_routes", {}).get("routes", []):
            candidate = dict(route)
            if candidate.get("parent") == parent_part and candidate.get("child") == child_part:
                candidate["enabled"] = bool(enabled)
                updated = dict(candidate)
            routes.append(candidate)
        self.project_data["cascade_routes"]["routes"] = routes
        if updated and save:
            self.save_project()
        return updated

    def delete_cascade_route(self, parent_part, child_part, save=True):
        routes = [
            dict(route)
            for route in self.project_data.get("cascade_routes", {}).get("routes", [])
            if not (route.get("parent") == parent_part and route.get("child") == child_part)
        ]
        removed = len(routes) != len(self.project_data.get("cascade_routes", {}).get("routes", []))
        self.project_data["cascade_routes"]["routes"] = routes
        return removed

    def remove_cascade_route_expert_candidate(self, parent_part, child_part, expert_id, save=True):
        removed = False
        routes = []
        for route in self.project_data.get("cascade_routes", {}).get("routes", []):
            candidate = dict(route)
            if candidate.get("parent") == parent_part and candidate.get("child") == child_part:
                appointed_id = str((candidate.get("appointed_expert") or {}).get("expert_id") or "")
                if appointed_id == expert_id:
                    routes.append(candidate)
                    continue
                before = list(candidate.get("expert_candidates", []))
                candidate["expert_candidates"] = [
                    dict(item)
                    for item in before
                    if isinstance(item, dict) and item.get("expert_id") != expert_id
                ]
                removed = len(candidate["expert_candidates"]) != len(before)
            routes.append(candidate)
        self.project_data["cascade_routes"]["routes"] = routes
        if removed and save:
            self.save_project()
        return removed


class UiLocalizationTests(unittest.TestCase):
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

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_dialog_uses_chinese_strings(self):
        dialog = ExportDialog(lang="zh")
        self.assertEqual(dialog.windowTitle(), "导出数据集")
        self.assertEqual(dialog.format_combo.itemText(0), "多模态（裁剪图 + JSONL）")
        self.assertEqual(dialog.path_edit.placeholderText(), "选择导出目录...")

    def test_blink_entry_dialog_translates_target_and_roi_labels(self):
        dialog = BlinkEntryDialog(
            self.image_path,
            ["Head", "Mandible", "Eye"],
            "Mandible",
            [
                {"part": "Head", "source": "manual", "box": [10.0, 10.0, 80.0, 70.0]},
                {"part": "Mandible", "source": "manual", "box": [18.0, 18.0, 42.0, 42.0]},
            ],
            lang="zh",
            remembered_parent_map={"Mandible": "Head"},
        )
        self.assertEqual(dialog.windowTitle(), "进入子部位专家会话")
        self.assertEqual(dialog.target_combo.currentText(), "上颚 (Mandible)")
        self.assertIn("手工框", dialog.roi_combo.currentText())
        self.assertIn("子部位", dialog.tip_label.text())
        self.assertIn("记住", dialog.tip_label.text())

    def test_blink_lab_supports_runtime_chinese_switch(self):
        widget = BlinkLabWidget(self.engine, self.pm, lang="en")
        widget.change_language("zh")
        self.assertEqual(widget.sidebar.title(), "专家分类")
        self.assertEqual(widget.btn_sync.text(), "从工作台同步")
        self.assertEqual(widget.rb_box_prompt.text(), "绘制框（SAM 草稿）")
        self.assertEqual(widget.btn_auto_annotate.text(), "自动标注草稿")
        self.assertEqual(widget.btn_auto_shrink.text(), "执行自动收缩")
        self.assertEqual(widget.lbl_epochs.text(), "训练轮数 (Epochs):")
        self.assertEqual(widget.lbl_batch_size.text(), "批次大小 (Batch Size):")
        self.assertTrue(widget.lbl_status.wordWrap())

    def test_cropper_uses_chinese_text(self):
        dialog = ImageCropper(lang="zh")
        self.assertEqual(dialog.windowTitle(), "智能图片裁剪器")
        self.assertEqual(dialog.btn_load.text(), "加载图片")
        self.assertEqual(dialog.btn_auto_split.text(), "自动切分拼图")
        self.assertEqual(dialog.btn_delete_selected.text(), "删除选中裁剪框")
        self.assertEqual(dialog.btn_clear_crops.text(), "清空裁剪框")
        self.assertEqual(dialog.btn_save.text(), "保存并加入项目")

    def test_pdf_processing_widget_supports_chinese_switch(self):
        widget = PdfProcessingWidget("en")
        self.assertEqual(widget.check_isolate_runs.text(), "V2: separate folder per run")
        self.assertEqual(
            widget.check_isolate_runs.toolTip(),
            "Each V2 run saves into its own subfolder under Output Dir to avoid mixed results.",
        )
        widget.change_language("zh")
        self.assertEqual(widget.config_group.title(), "全局设置 (LLM / API)")
        self.assertEqual(widget.btn_start_center.text(), "启动中心")
        self.assertEqual(widget.btn_ask_agent.text(), "询问 Agent")
        self.assertEqual(widget.btn_toggle_advanced.text(), "显示高级配置")
        self.assertEqual(widget.btn_restore_interrupted_run.text(), "恢复中断运行参数")
        self.assertEqual(widget.util_group.title(), "3. 数据工具")
        self.assertEqual(widget.btn_export_jsonl.text(), "导出 PDF 提取数据集（JSONL）")
        self.assertEqual(widget.check_isolate_runs.text(), "V2：每次运行独立文件夹")
        self.assertEqual(
            widget.check_isolate_runs.toolTip(),
            "勾选后：每次 V2 运行都会在输出目录下使用独立子文件夹，避免不同运行结果混在一起。",
        )
        widget.set_theme("light")
        part_advanced_style = widget.btn_adv_part_description_config.styleSheet()
        self.assertIn("background-color: #FDFEFF", part_advanced_style)
        self.assertNotIn("qlineargradient", part_advanced_style)
        self.assertIn("background-color: #DC2626", widget.btn_delete_part_description_profile.styleSheet())

    def test_main_translates_added_common_dialog_strings(self):
        self.assertEqual(main_module.tr("Close", "zh"), "关闭")
        self.assertEqual(main_module.tr("Select Directory", "zh"), "选择目录")

    def test_main_translates_model_delete_button_copy(self):
        self.assertEqual(main_module.tr("Del", "zh"), "删除")
        self.assertEqual(main_module.tr("Locator switched to: {0}", "zh"), "定位器已切换为：{0}")
        self.assertEqual(
            main_module.tr("Delete the selected locator model file from disk.", "zh"),
            "从磁盘删除当前选中的定位器模型文件。",
        )
        self.assertEqual(
            main_module.tr("Delete the selected segmenter model file from disk.", "zh"),
            "从磁盘删除当前选中的分割器模型文件。",
        )

    def test_route_panel_and_model_settings_use_chinese_copy(self):
        owner = type(
            "Owner",
            (),
            {
                "project": self.pm,
                "engine": self.engine,
                "log": lambda _self, _message: None,
            },
        )()
        panel = RouteManagementPanel(owner, lang="zh")
        panel.refresh_route_table()

        self.assertEqual(panel.header_label.text(), "项目路由")
        self.assertIn("重新登记", panel.note_label.text())
        parent_item = panel.route_tree.topLevelItem(0)
        self.assertEqual(parent_item.text(0), "Head")
        route_item = parent_item.child(0)
        self.assertEqual(route_item.text(1), "Mandible")
        self.assertEqual(route_item.text(2), "否")
        self.assertEqual(route_item.text(3), "ViT-B Blink 专家")
        self.assertEqual(route_item.text(5), "尚未指定专家")
        self.assertEqual(route_item.text(6), "未指定专家")
        self.assertEqual(route_item.text(7), "Blink 候选")
        expert_placeholder = route_item.child(0)
        self.assertEqual(expert_placeholder.text(3), "ViT-B Blink 专家")
        self.assertEqual(expert_placeholder.text(4), "未指定")
        self.assertEqual(expert_placeholder.text(5), "尚未指定专家")
        self.assertEqual(expert_placeholder.text(6), "未指定专家")

    def test_route_tree_prefers_persisted_candidate_history_over_runtime_discovery(self):
        self.pm.project_data["cascade_routes"]["version"] = "project-v2"
        self.pm.project_data["cascade_routes"]["routes"] = [
            {
                "parent": "Head",
                "child": "Mandible",
                "enabled": False,
                "appointed_expert": {
                    "expert_id": "Mandible/mandible_v2.pth",
                    "expert_part": "Mandible",
                    "expert_filename": "mandible_v2.pth",
                },
                "expert_candidates": [
                    {
                        "expert_id": "Mandible/mandible_v2.pth",
                        "expert_part": "Mandible",
                        "expert_filename": "mandible_v2.pth",
                    },
                    {
                        "expert_id": "Mandible/expert_v20260501_090000.pth",
                        "expert_part": "Mandible",
                        "expert_filename": "expert_v20260501_090000.pth",
                    },
                ],
                "expert_id": "Mandible/mandible_v2.pth",
                "expert_part": "Mandible",
                "expert_filename": "mandible_v2.pth",
                "registration_source": "project",
            }
        ]
        owner = type(
            "Owner",
            (),
            {
                "project": self.pm,
                "engine": self.engine,
                "log": lambda _self, _message: None,
            },
        )()
        panel = RouteManagementPanel(owner, lang="en")
        panel.refresh_route_table()

        route_item = panel._find_route_item("Head", "Mandible")
        appointed_item = panel._find_expert_item("Head", "Mandible", "Mandible/mandible_v2.pth")
        history_item = panel._find_expert_item("Head", "Mandible", "Mandible/expert_v20260501_090000.pth")

        self.assertIsNotNone(route_item)
        self.assertEqual(route_item.childCount(), 2)
        self.assertIsNotNone(appointed_item)
        self.assertIsNotNone(history_item)
        self.assertEqual(appointed_item.text(3), "ViT-B Blink Expert")
        self.assertEqual(appointed_item.text(5), "Appointed")
        self.assertEqual(history_item.text(5), "Missing file history")

        dialog = ModelSettingsDialog(
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
            lang="zh",
            route_panel=panel,
        )
        route_group = dialog.findChild(QWidget, "modelSettingsRoutePanel")
        self.assertIsNotNone(route_group)
        self.assertIn("route 决定哪些 parent -> child expert 链路可以实际使用", dialog.lbl_cascade_note.text())

    def test_route_tree_marks_route_specific_backend_against_active_profile(self):
        self.pm.project_data["cascade_routes"]["version"] = "project-v2"
        self.pm.project_data["cascade_routes"]["routes"] = [
            {
                "parent": "Head",
                "child": "Mandible",
                "enabled": True,
                "appointed_expert": {
                    "expert_id": "Mandible/heatmap_v1.pth",
                    "expert_part": "Mandible",
                    "expert_filename": "heatmap_v1.pth",
                    "expert_backend": ROUTE_BACKEND_HEATMAP_BLINK,
                },
                "expert_candidates": [],
                "expert_id": "Mandible/heatmap_v1.pth",
                "expert_part": "Mandible",
                "expert_filename": "heatmap_v1.pth",
                "expert_backend": ROUTE_BACKEND_HEATMAP_BLINK,
                "registration_source": "project",
            }
        ]
        owner = type(
            "Owner",
            (),
            {
                "project": self.pm,
                "engine": self.engine,
                "log": lambda _self, _message: None,
            },
        )()
        panel = RouteManagementPanel(owner, lang="en")
        panel.refresh_route_table()

        route_item = panel._find_route_item("Head", "Mandible")

        self.assertEqual(route_item.text(3), "Heatmap Blink Expert")
        self.assertEqual(route_item.text(6), "Route-specific backend")
        self.assertIn("Active profile default", route_item.toolTip(6))

    def test_missing_expert_history_can_be_removed_from_route_tree(self):
        self.pm.project_data["cascade_routes"]["version"] = "project-v2"
        self.pm.project_data["cascade_routes"]["routes"] = [
            {
                "parent": "Head",
                "child": "Mandible",
                "enabled": False,
                "appointed_expert": {
                    "expert_id": "Mandible/appointed.pth",
                    "expert_part": "Mandible",
                    "expert_filename": "appointed.pth",
                },
                "expert_candidates": [
                    {
                        "expert_id": "Mandible/appointed.pth",
                        "expert_part": "Mandible",
                        "expert_filename": "appointed.pth",
                    },
                    {
                        "expert_id": "Mandible/deleted_history.pth",
                        "expert_part": "Mandible",
                        "expert_filename": "deleted_history.pth",
                    },
                ],
                "expert_id": "Mandible/appointed.pth",
                "expert_part": "Mandible",
                "expert_filename": "appointed.pth",
                "registration_source": "project",
            }
        ]
        owner = type(
            "Owner",
            (),
            {
                "project": self.pm,
                "engine": self.engine,
                "log": lambda _self, _message: None,
            },
        )()
        panel = RouteManagementPanel(owner, lang="en")
        panel.refresh_route_table()

        history_item = panel._find_expert_item("Head", "Mandible", "Mandible/deleted_history.pth")
        appointed_item = panel._find_expert_item("Head", "Mandible", "Mandible/appointed.pth")
        self.assertIsNotNone(history_item)
        self.assertIsNotNone(appointed_item)

        panel.route_tree.setCurrentItem(history_item)
        panel.update_action_buttons()
        self.assertTrue(panel.btn_delete_route.isEnabled())

        with patch.object(
            main_module,
            "themed_yes_no_question",
            return_value=QMessageBox.StandardButton.Yes,
        ) as question_mock:
            panel.delete_selected_route()

        self.assertIn("only cleans the current project route history", question_mock.call_args.args[2])
        route = self.pm.get_cascade_route("Head", "Mandible")
        self.assertEqual(
            [candidate.get("expert_id") for candidate in route.get("expert_candidates", [])],
            ["Mandible/appointed.pth"],
        )
        self.assertIsNone(panel._find_expert_item("Head", "Mandible", "Mandible/deleted_history.pth"))

        panel.route_tree.setCurrentItem(panel._find_expert_item("Head", "Mandible", "Mandible/appointed.pth"))
        panel.update_action_buttons()
        self.assertFalse(panel.btn_delete_route.isEnabled())

    def test_model_settings_dialog_no_longer_exposes_cascade_master_toggle(self):
        dialog = ModelSettingsDialog(
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
                "taxonomy": ["Head", "Mesosoma", "Gaster"],
                "locator_scope": ["Head", "Mesosoma", "Gaster"],
            },
            lang="zh",
        )

        try:
            locator_group = dialog.findChild(QWidget, "modelSettingsLocatorScopePanel")
            self.assertIsNotNone(locator_group)
            self.assertEqual(len(locator_group.findChildren(main_module.QCheckBox)), 3)
            self.assertNotIn("enable_cascade", dialog.get_values())
        finally:
            dialog.deleteLater()

    def test_model_profile_manager_requires_confirmation_for_delete_and_activation(self):
        dialog = ModelSettingsDialog(
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
                "taxonomy": ["Head", "Mandible", "Eye"],
                "locator_scope": ["Head"],
            },
            lang="en",
        )
        try:
            self.assertEqual(dialog.btn_new_profile.text(), "Save Current Settings as New Profile")
            self.assertEqual(dialog.btn_set_active_profile.text(), "Set as Active Profile")
            self.assertIsNotNone(dialog.findChild(QWidget, "modelSettingsProfileSummary"))
            self.assertIsNone(dialog.profile_tab_index)
            advanced_tab = dialog.tabs.widget(dialog.advanced_extensions_tab_index).widget()
            self.assertIsNotNone(advanced_tab.findChild(QWidget, "modelSettingsProfilePanel"))
            self.assertIsNotNone(advanced_tab.findChild(QWidget, "modelSettingsModelSourceSwitchPanel"))
            self.assertIsNotNone(advanced_tab.findChild(QWidget, "modelSettingsParentExtensionPanel"))
            self.assertIsNotNone(advanced_tab.findChild(QWidget, "modelSettingsExternalBlinkPanel"))
            self.assertEqual(dialog.tabs.tabText(0), "Parent-part annotation")
            self.assertEqual(dialog.tabs.tabText(1), "Child-part annotation")
            self.assertEqual(dialog.tabs.tabText(2), "Inference")
            self.assertEqual(dialog.tabs.tabText(3), "Advanced Extensions")
            panel_order = [
                advanced_tab.findChild(QWidget, "modelSettingsProfilePanel").y(),
                advanced_tab.findChild(QWidget, "modelSettingsModelSourceSwitchPanel").y(),
                advanced_tab.findChild(QWidget, "modelSettingsParentExtensionPanel").y(),
                advanced_tab.findChild(QWidget, "modelSettingsExternalBlinkPanel").y(),
            ]
            self.assertEqual(panel_order, sorted(panel_order))
            self.assertIn("Project active profile", dialog.profile_summary_box.toPlainText())

            dialog.new_model_profile()
            new_id = dialog.combo_model_profile.currentData()
            self.assertNotEqual(new_id, DEFAULT_MODEL_PROFILE_ID)
            self.assertEqual(dialog.model_profiles["active_profile_id"], DEFAULT_MODEL_PROFILE_ID)
            values = dialog.get_values()
            self.assertEqual(values["model_profiles"]["active_profile_id"], DEFAULT_MODEL_PROFILE_ID)

            with patch.object(
                main_module,
                "themed_yes_no_question",
                return_value=QMessageBox.StandardButton.No,
            ) as question_mock:
                dialog.set_selected_profile_active()

            self.assertIn("only changes the project default profile", question_mock.call_args.args[2])
            self.assertEqual(dialog.model_profiles["active_profile_id"], DEFAULT_MODEL_PROFILE_ID)

            dialog.combo_model_profile.setCurrentIndex(dialog.combo_model_profile.findData(new_id))
            with patch.object(
                main_module,
                "themed_yes_no_question",
                return_value=QMessageBox.StandardButton.Yes,
            ) as question_mock:
                dialog.delete_model_profile()

            self.assertIn("Model weights, external scripts, and route expert bindings are not deleted", question_mock.call_args.args[2])
            remaining_ids = [profile["profile_id"] for profile in dialog.model_profiles["profiles"]]
            self.assertNotIn(new_id, remaining_ids)
        finally:
            dialog.deleteLater()

    def test_model_profile_external_parent_only_affects_runtime_after_activation(self):
        dialog = ModelSettingsDialog(
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
                "taxonomy": ["Head", "Mandible", "Eye"],
                "locator_scope": ["Head"],
                "model_backend": main_module.BUILTIN_BACKEND_ID,
            },
            lang="en",
        )
        try:
            dialog.new_model_profile()
            new_id = dialog.combo_model_profile.currentData()
            dialog.parent_backend_combo.setCurrentIndex(dialog.parent_backend_combo.findData(PARENT_BACKEND_EXTERNAL))
            dialog.external_backend_id.setText("external_parent_test")
            dialog.external_display_name.setText("External Parent Test")
            dialog.external_train_command.setPlainText("{python} train.py --contract {contract_json}")
            dialog.external_predict_command.setPlainText("{python} predict.py --contract {contract_json}")

            self.assertFalse(dialog.backend_combo.isEnabled())
            self.assertEqual(dialog.backend_combo.currentData(), main_module.EXTERNAL_BACKEND_ID)
            self.assertIn("Compatibility display only", dialog.backend_combo.toolTip())
            self.assertEqual(dialog.tabs.tabText(dialog.advanced_extensions_tab_index), "Advanced Extensions")
            advanced_tab = dialog.tabs.widget(dialog.advanced_extensions_tab_index).widget()
            parent_tab = dialog.tabs.widget(dialog.parent_tab_index).widget()
            child_tab = dialog.tabs.widget(dialog.child_tab_index).widget()
            self.assertIsNotNone(advanced_tab.findChild(QWidget, "modelSettingsModelSourceSwitchPanel"))
            self.assertIsNotNone(parent_tab.findChild(QWidget, "modelSettingsParentSourceSummary"))
            self.assertIsNotNone(child_tab.findChild(QWidget, "modelSettingsChildSourceSummary"))
            self.assertIsNotNone(advanced_tab.findChild(QWidget, "modelSettingsParentExtensionPanel"))
            self.assertIsNotNone(advanced_tab.findChild(QWidget, "modelSettingsExternalBlinkPanel"))
            parent_status = advanced_tab.findChild(QWidget, "modelSettingsParentExtensionStatus")
            child_status = advanced_tab.findChild(QWidget, "modelSettingsChildExtensionStatus")
            self.assertIsNotNone(parent_status)
            self.assertIsNotNone(child_status)
            self.assertIn("Active now", parent_status.text())
            self.assertIn("Not active now", child_status.text())
            self.assertIsNone(child_tab.findChild(QWidget, "modelSettingsExternalBlinkPanel"))
            self.assertEqual(dialog._external_backend_validation_errors(), [])

            values_before_activation = dialog.get_values()
            self.assertEqual(values_before_activation["model_profiles"]["active_profile_id"], DEFAULT_MODEL_PROFILE_ID)
            self.assertEqual(values_before_activation["model_backend"], main_module.BUILTIN_BACKEND_ID)
            self.assertNotEqual(values_before_activation["external_backend"]["backend_id"], "external_parent_test")

            with patch.object(
                main_module,
                "themed_yes_no_question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                dialog.set_selected_profile_active()

            values_after_activation = dialog.get_values()
            self.assertEqual(values_after_activation["model_profiles"]["active_profile_id"], new_id)
            self.assertEqual(values_after_activation["model_backend"], main_module.EXTERNAL_BACKEND_ID)
            self.assertEqual(values_after_activation["external_backend"]["backend_id"], "external_parent_test")
        finally:
            dialog.deleteLater()

    def test_model_profile_dialog_loads_active_external_parent_config(self):
        dialog = ModelSettingsDialog(
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
                "taxonomy": ["Head", "Mandible", "Eye"],
                "locator_scope": ["Head"],
                "model_backend": main_module.BUILTIN_BACKEND_ID,
                "external_backend": {
                    "backend_id": "old_global_external",
                    "display_name": "Old Global External",
                    "python_executable": "python",
                    "train_command": "{python} old_train.py --contract {contract_json}",
                    "predict_command": "{python} old_predict.py --contract {contract_json}",
                },
                "model_profiles": {
                    "active_profile_id": "saved_external_profile",
                    "profiles": [
                        {
                            "profile_id": "saved_external_profile",
                            "display_name": "Saved External Profile",
                            "parent_backend": {
                                "backend_type": PARENT_BACKEND_EXTERNAL,
                                "locator_scope": ["Head"],
                                "external_backend": {
                                    "backend_id": "saved_profile_external",
                                    "display_name": "Saved Profile External",
                                    "python_executable": "python",
                                    "train_command": "{python} saved_train.py --contract {contract_json}",
                                    "predict_command": "{python} saved_predict.py --contract {contract_json}",
                                    "model_manifest": "saved_manifest.json",
                                },
                            },
                        }
                    ],
                },
            },
            lang="en",
        )
        try:
            self.assertEqual(dialog.combo_model_profile.currentData(), "saved_external_profile")
            self.assertEqual(dialog.parent_backend_combo.currentData(), PARENT_BACKEND_EXTERNAL)
            self.assertEqual(dialog.backend_combo.currentData(), main_module.EXTERNAL_BACKEND_ID)
            self.assertFalse(dialog.backend_combo.isEnabled())
            self.assertEqual(dialog.parent_backend_combo.currentText(), "Custom Parent Extension")
            self.assertEqual(dialog.child_backend_combo.itemText(dialog.child_backend_combo.findData(main_module.CHILD_BACKEND_EXTERNAL)), "Custom Child Extension")
            self.assertEqual(dialog.external_backend_id.text(), "saved_profile_external")
            self.assertEqual(dialog.external_display_name.text(), "Saved Profile External")
            self.assertIn("saved_train.py", dialog.external_train_command.toPlainText())

            values = dialog.get_values()
            self.assertEqual(values["model_backend"], main_module.EXTERNAL_BACKEND_ID)
            self.assertEqual(values["external_backend"]["backend_id"], "saved_profile_external")
            self.assertNotEqual(values["external_backend"]["backend_id"], "old_global_external")
        finally:
            dialog.deleteLater()

    def test_model_settings_legacy_external_backend_initializes_default_profile(self):
        dialog = ModelSettingsDialog(
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
                "taxonomy": ["Head", "Mandible"],
                "locator_scope": ["Head"],
                "model_backend": main_module.EXTERNAL_BACKEND_ID,
                "external_backend": {
                    "backend_id": "legacy_external",
                    "display_name": "Legacy External",
                    "python_executable": "python",
                    "prepare_dataset_command": "{python} prepare.py --contract {contract_json}",
                    "train_command": "{python} train.py --contract {contract_json}",
                    "predict_command": "",
                },
            },
            lang="en",
        )
        try:
            self.assertEqual(dialog.parent_backend_combo.currentData(), PARENT_BACKEND_EXTERNAL)
            self.assertEqual(dialog.backend_combo.currentData(), main_module.EXTERNAL_BACKEND_ID)
            self.assertEqual(dialog.external_backend_id.text(), "legacy_external")
            context = dialog.get_agent_context()
            self.assertEqual(context["prepare_command_present"], "yes")
            self.assertEqual(context["prepare_command_has_contract"], "yes")
        finally:
            dialog.deleteLater()

    def test_route_delete_confirmation_uses_clear_recovery_copy_in_chinese(self):
        logged_messages = []
        owner = type(
            "Owner",
            (),
            {
                "project": self.pm,
                "engine": self.engine,
                "log": lambda _self, message: logged_messages.append(message),
            },
        )()
        panel = RouteManagementPanel(owner, lang="zh")
        panel.refresh_route_table()
        route_item = panel._find_route_item("Head", "Mandible")
        panel.route_tree.setCurrentItem(route_item)

        with patch.object(
            main_module,
            "themed_yes_no_question",
            return_value=QMessageBox.StandardButton.No,
        ) as question_mock:
            panel.delete_selected_route()

        self.assertIn("当前项目里的这条路由记录", question_mock.call_args.args[2])
        self.assertIn("重新登记为候选", question_mock.call_args.args[2])

    def test_route_tree_scopes_actions_by_selected_node_type(self):
        available_experts = [
            {
                "expert_part": "Mandible",
                "expert_filename": "expert_v20260501_090000.pth",
                "expert_id": "Mandible/expert_v20260501_090000.pth",
                "path": str(Path(self.temp_dir.name) / "weights" / "experts" / "Mandible" / "expert_v20260501_090000.pth"),
            },
            {
                "expert_part": "Mandible",
                "expert_filename": "mandible_v2.pth",
                "expert_id": "Mandible/mandible_v2.pth",
                "path": str(Path(self.temp_dir.name) / "weights" / "experts" / "Mandible" / "mandible_v2.pth"),
            },
        ]
        engine = DummyEngine(str(Path(self.temp_dir.name) / "weights"), available_experts=available_experts)
        owner = type(
            "Owner",
            (),
            {
                "project": self.pm,
                "engine": engine,
                "log": lambda _self, _message: None,
            },
        )()
        self.pm.appoint_cascade_route_expert("Head", "Mandible", expert_id="Mandible/expert_v20260501_090000.pth", save=False)
        panel = RouteManagementPanel(owner, lang="en")
        panel.refresh_route_table()

        parent_item = panel._find_parent_item("Head")
        route_item = panel._find_route_item("Head", "Mandible")
        appointed_expert_item = panel._find_expert_item("Head", "Mandible", "Mandible/expert_v20260501_090000.pth")
        available_expert_item = panel._find_expert_item("Head", "Mandible", "Mandible/mandible_v2.pth")

        self.assertIsNotNone(parent_item)
        self.assertIsNotNone(route_item)
        self.assertIsNotNone(appointed_expert_item)
        self.assertIsNotNone(available_expert_item)
        self.assertEqual(route_item.childCount(), 2)
        self.assertEqual(appointed_expert_item.text(3), "ViT-B Blink Expert")
        self.assertEqual(appointed_expert_item.text(4), "★ Mandible/expert_v20260501_090000.pth")
        self.assertEqual(appointed_expert_item.text(5), "Appointed")
        self.assertEqual(available_expert_item.text(5), "Discoverable")

        panel.route_tree.setCurrentItem(parent_item)
        panel.update_action_buttons()
        self.assertFalse(panel.btn_appoint_route_expert.isEnabled())
        self.assertFalse(panel.btn_toggle_route.isEnabled())
        self.assertFalse(panel.btn_delete_route.isEnabled())

        panel.route_tree.setCurrentItem(route_item)
        panel.update_action_buttons()
        self.assertFalse(panel.btn_appoint_route_expert.isEnabled())
        self.assertTrue(panel.btn_toggle_route.isEnabled())
        self.assertTrue(panel.btn_delete_route.isEnabled())

        panel.route_tree.setCurrentItem(available_expert_item)
        panel.update_action_buttons()
        self.assertTrue(panel.btn_appoint_route_expert.isEnabled())
        self.assertFalse(panel.btn_toggle_route.isEnabled())
        self.assertFalse(panel.btn_delete_route.isEnabled())

    def test_route_tree_displays_expert_notes_without_changing_route_payloads(self):
        available_experts = [
            {
                "expert_part": "Mandible",
                "expert_filename": "expert_v20260501_090000.pth",
                "expert_id": "Mandible/expert_v20260501_090000.pth",
                "path": str(Path(self.temp_dir.name) / "weights" / "experts" / "Mandible" / "expert_v20260501_090000.pth"),
            },
            {
                "expert_part": "Mandible",
                "expert_filename": "expert_v20260503_120000.pth",
                "expert_id": "Mandible/expert_v20260503_120000.pth",
                "path": str(Path(self.temp_dir.name) / "weights" / "experts" / "Mandible" / "expert_v20260503_120000.pth"),
            },
        ]
        engine = DummyEngine(str(Path(self.temp_dir.name) / "weights"), available_experts=available_experts)
        set_expert_note(engine.weights_dir, "Mandible/expert_v20260501_090000.pth", "side view stable")
        owner = type(
            "Owner",
            (),
            {
                "project": self.pm,
                "engine": engine,
                "log": lambda _self, _message: None,
            },
        )()
        self.pm.appoint_cascade_route_expert("Head", "Mandible", expert_id="Mandible/expert_v20260501_090000.pth", save=False)
        panel = RouteManagementPanel(owner, lang="en")
        panel.refresh_route_table()

        route_item = panel._find_route_item("Head", "Mandible")
        appointed_expert_item = panel._find_expert_item("Head", "Mandible", "Mandible/expert_v20260501_090000.pth")
        available_expert_item = panel._find_expert_item("Head", "Mandible", "Mandible/expert_v20260503_120000.pth")

        self.assertEqual(route_item.text(3), "ViT-B Blink Expert")
        self.assertEqual(route_item.text(4), "side view stable (Mandible/expert_v20260501_090000.pth)")
        self.assertEqual(appointed_expert_item.text(4), "★ side view stable (Mandible/expert_v20260501_090000.pth)")
        self.assertEqual(available_expert_item.text(4), "Mandible/expert_v20260503_120000.pth")

        panel.route_tree.setCurrentItem(available_expert_item)
        panel.appoint_selected_route_expert()
        route = self.pm.get_cascade_route("Head", "Mandible")
        self.assertEqual(route.get("expert_id"), "Mandible/expert_v20260503_120000.pth")

    def test_training_dialogs_use_chinese_runtime_copy(self):
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
            "parts_part_counts": {"Head": 1, "Mandible": 0},
            "parts_train_part_counts": {"Head": 1, "Mandible": 0},
            "parts_val_part_counts": {"Head": 1, "Mandible": 0},
            "locator_scope": ["Head"],
            "taxonomy": ["Head", "Mandible"],
            "warnings": [
                "Excluded 1 zero-annotation image(s) from training.",
                "SAM/parts coverage is 0 for 'Mandible', so that part will not enter SAM training.",
            ],
            "excluded_missing_images": [],
            "excluded_invalid_images": [],
            "excluded_zero_annotation_images": ["sample.png"],
            "excluded_invalid_annotation_images": [],
        }
        dialog = TrainingPreflightDialog(preflight, lang="zh")
        self.assertIn("Locator 阶段：就绪", dialog.summary_label.text())
        tabs = dialog.findChild(main_module.QTabWidget)
        overview_text = tabs.widget(0).findChild(main_module.QTextEdit).toPlainText()
        self.assertIn("可用于 Locator 训练的图片：1", overview_text)
        coverage_text = tabs.widget(1).findChild(main_module.QTextEdit).toPlainText()
        self.assertIn("Locator 标注覆盖情况", coverage_text)
        warnings_text = dialog._warnings_text()
        self.assertIn("训练中排除了 1 张零标注图片", warnings_text)
        self.assertIn("SAM/部位标注覆盖为 0", warnings_text)
        self.assertIn("不会进入 SAM 训练", warnings_text)

        with tempfile.TemporaryDirectory() as tmp_dir:
            details_dir = Path(tmp_dir) / "val_details"
            details_dir.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (120, 80), color=(180, 180, 180)).save(details_dir / "val_0000.jpg")
            summary_path = Path(tmp_dir) / "report_summary.json"
            summary_path.write_text(
                '{"validation_count": 1, "validation_preview_count": 1, "validation_provenance_counts": {"macro_locator": 1}}',
                encoding="utf-8",
            )
            index_path = Path(tmp_dir) / "validation_index.csv"
            index_path.write_text(
                "sample_id,image_name,image_path,detail_image,provenance,valid_parts,predicted_parts,peak_summary,error_summary,max_error_px\n"
                "val_0000,sample.png,sample.png,val_0000.jpg,macro_locator,Head,Head,Head=1.00,Head=0.0px,0.000\n",
                encoding="utf-8",
            )
            report_dialog = TrainingReportDialog(
                {
                    "dir": tmp_dir,
                    "report_summary": str(summary_path),
                    "validation_index": str(index_path),
                    "details_dir": str(details_dir),
                    "val": None,
                    "metrics": None,
                },
                lang="zh",
            )
            self.assertIn("验证样本数：1", report_dialog.summary_box.toPlainText())
            self.assertEqual(report_dialog.validation_index_table.horizontalHeaderItem(2).text(), "来源")
            self.assertEqual(report_dialog.validation_index_table.item(0, 2).text(), "宏定位器")

    def test_clear_ai_confirmation_uses_clear_ai_labels_wording(self):
        class DummyProject:
            def remove_auto_labels(self):
                return 0

        class DummyCanvas:
            def set_polygons(self, _labels):
                return None

        class DummyWindow:
            def __init__(self):
                self.current_lang = "zh"
                self.project = DummyProject()
                self.current_image = None
                self.canvas = DummyCanvas()

            def refresh_file_list(self):
                return None

            def log(self, _message):
                return None

        window = DummyWindow()
        with patch.object(
            main_module,
            "themed_yes_no_question",
            return_value=QMessageBox.StandardButton.No,
        ) as question_mock:
            main_module.MainWindow.clear_ai_labels(window)

        self.assertEqual(question_mock.call_args.args[1], "清除 AI 标签")
        self.assertEqual(question_mock.call_args.args[2], "清除当前项目中的全部 AI 标签？")


if __name__ == "__main__":
    unittest.main()
