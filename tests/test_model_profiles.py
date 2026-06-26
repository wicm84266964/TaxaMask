# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportArgumentType=false

import json
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.model_profiles import (
    CHILD_BACKEND_VIT_B,
    DEFAULT_MODEL_PROFILE_ID,
    MODEL_PROFILES_SCHEMA_VERSION,
    PARENT_BACKEND_BUILTIN,
    sanitize_model_profiles,
)
from AntSleap.core.project import MODEL_PROFILE_EXPORT_SUMMARY_SCHEMA_VERSION, ProjectManager
from AntSleap.core.project_sqlite_maintenance import export_sqlite_project_to_legacy_json


class ModelProfileTests(unittest.TestCase):
    def test_default_model_profiles_capture_project_scope_and_blink_defaults(self):
        profiles = sanitize_model_profiles(
            {},
            taxonomy=["Head", "Mesosoma", "Gaster", "Mandible"],
            locator_scope=["Head", "Mesosoma", "Gaster"],
            parent_box_aspect_ratios={"Head": 1.0},
            vlm_preannotation={
                "target_parts": ["Mandible"],
                "processing_scope": "image_group",
                "image_group": "split",
                "prompt_profile_id": "project_custom",
                "prompt_profile": {
                    "profile_id": "project_custom",
                    "display_name": "Bee prompt",
                    "taxon_context": "蜂类图像",
                    "body_focus_rules": "不要把翅纳入胸部主体框。",
                    "part_anchor_rules": "Thorax 在 Head 和 Abdomen 之间。",
                    "extra_instructions": "",
                },
            },
        )

        self.assertEqual(profiles["schema_version"], MODEL_PROFILES_SCHEMA_VERSION)
        self.assertEqual(profiles["active_profile_id"], DEFAULT_MODEL_PROFILE_ID)
        profile = profiles["profiles"][0]
        self.assertEqual(profile["parent_backend"]["backend_type"], PARENT_BACKEND_BUILTIN)
        self.assertEqual(profile["parent_backend"]["locator_scope"], ["Head", "Mesosoma", "Gaster"])
        self.assertEqual(profile["child_backend_defaults"]["backend_type"], CHILD_BACKEND_VIT_B)
        self.assertEqual(profile["child_backend_defaults"]["input_size"], 224)
        self.assertEqual(profile["inference_params"]["vlm_preannotation"]["target_parts"], ["Mandible"])
        self.assertEqual(profile["inference_params"]["vlm_preannotation"]["processing_scope"], "image_group")
        self.assertEqual(profile["inference_params"]["vlm_preannotation"]["image_group"], "split")
        self.assertEqual(profile["inference_params"]["vlm_preannotation"]["prompt_profile_id"], "project_custom")
        self.assertIn("蜂类", profile["inference_params"]["vlm_preannotation"]["prompt_profile"]["taxon_context"])

    def test_new_project_writes_default_model_profiles(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pm = ProjectManager()
            pm.create_project("profile_demo", tmp_dir)

            export_path = Path(tmp_dir) / "profile_demo.legacy.json"
            export_sqlite_project_to_legacy_json(pm.current_project_path, export_path)
            saved = json.loads(export_path.read_text(encoding="utf-8"))

            self.assertIn("model_profiles", saved)
            self.assertEqual(saved["model_profiles"]["active_profile_id"], DEFAULT_MODEL_PROFILE_ID)
            active = pm.get_active_model_profile()
            self.assertEqual(active["parent_backend"]["locator_scope"], ["Head", "Mesosoma", "Gaster"])
            self.assertEqual(active["child_backend_defaults"]["backend_type"], CHILD_BACKEND_VIT_B)

    def test_legacy_project_load_adds_default_model_profiles_without_changing_old_fields(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir) / "legacy.json"
            project_path.write_text(
                json.dumps(
                    {
                        "name": "legacy",
                        "taxonomy": ["Head", "Mesosoma", "Mandible"],
                        "locator_scope": ["Head"],
                        "images": [],
                        "labels": {},
                        "scales": {},
                        "vlm_preannotation": {
                            "target_parts": ["Mandible"],
                            "processing_scope": "image_group",
                            "image_group": "split",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            pm = ProjectManager()
            pm.load_project(str(project_path))

            self.assertEqual(pm.get_locator_scope(), ["Head"])
            self.assertEqual(pm.get_vlm_preannotation_settings()["target_parts"], ["Mandible"])
            profile = pm.get_active_model_profile()
            self.assertEqual(profile["parent_backend"]["locator_scope"], ["Head"])
            self.assertEqual(profile["inference_params"]["vlm_preannotation"]["processing_scope"], "image_group")
            self.assertEqual(profile["inference_params"]["vlm_preannotation"]["image_group"], "split")

    def test_project_preserves_custom_image_groups_and_vlm_group(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir) / "custom_groups.json"
            image_path = Path(tmp_dir) / "specimen.png"
            image_path.write_bytes(b"image")
            project_path.write_text(
                json.dumps(
                    {
                        "name": "custom groups",
                        "taxonomy": ["Head"],
                        "locator_scope": ["Head"],
                        "images": [image_path.name],
                        "labels": {},
                        "scales": {},
                        "image_groups": {
                            "custom_groups": [
                                {"id": "review_ready", "name": "Review Ready"},
                            ]
                        },
                        "image_provenance": {
                            image_path.name: {"manual_image_group": "review_ready"}
                        },
                        "vlm_preannotation": {
                            "target_parts": ["Head"],
                            "processing_scope": "image_group",
                            "image_group": "review_ready",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            pm = ProjectManager()
            pm.load_project(str(project_path))

            self.assertEqual(pm.project_data["image_groups"]["custom_groups"][0]["id"], "review_ready")
            self.assertEqual(pm.get_vlm_preannotation_settings()["image_group"], "review_ready")
            pm.save_project()
            saved = json.loads(project_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["image_groups"]["custom_groups"][0]["name"], "Review Ready")
            self.assertEqual(saved["vlm_preannotation"]["image_group"], "review_ready")

    def test_project_model_profiles_round_trip_active_profile(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pm = ProjectManager()
            pm.create_project("profile_switch", tmp_dir)
            profiles = pm.get_model_profiles()
            copied = dict(profiles["profiles"][0])
            copied["profile_id"] = "head_only"
            copied["display_name"] = "Head only profile"
            copied["parent_backend"] = dict(copied["parent_backend"])
            copied["parent_backend"]["locator_scope"] = ["Head"]
            profiles["profiles"].append(copied)
            profiles["active_profile_id"] = "head_only"

            pm.set_model_profiles(profiles, save=False)
            pm.set_active_model_profile("head_only", save=False)
            pm.save_project()

            reloaded = ProjectManager()
            reloaded.load_project(pm.current_project_path)

            self.assertEqual(reloaded.get_model_profiles()["active_profile_id"], "head_only")
            self.assertEqual(reloaded.get_locator_scope(), ["Head"])
            self.assertEqual(reloaded.get_active_model_profile()["display_name"], "Head only profile")

    def test_legacy_locator_scope_updates_active_profile_snapshot(self):
        pm = ProjectManager()
        pm.add_taxonomy_part("Mandible")
        pm.ensure_default_model_profile()

        pm.set_locator_scope(["Head"], save=False)

        active = pm.get_active_model_profile()
        self.assertEqual(active["parent_backend"]["locator_scope"], ["Head"])

    def test_model_profile_export_summary_includes_active_profile_and_route_backends(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pm = ProjectManager()
            pm.create_project("profile_export", tmp_dir)
            pm.add_taxonomy_part("Mandible")
            pm.register_cascade_route_candidate(
                "Head",
                "Mandible",
                expert_id="Mandible/expert_v20260602_120000.pth",
                expert_backend="heatmap_blink",
                expert_manifest="Mandible/expert_v20260602_120000.manifest.json",
                input_size=[512, 512],
                save=False,
            )
            summary_path = pm.write_model_profile_export_summary(tmp_dir, export_format="multimodal")

            summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
            self.assertEqual(summary["schema_version"], MODEL_PROFILE_EXPORT_SUMMARY_SCHEMA_VERSION)
            self.assertEqual(summary["active_profile_id"], DEFAULT_MODEL_PROFILE_ID)
            self.assertEqual(summary["parent_backend"]["backend_type"], PARENT_BACKEND_BUILTIN)
            self.assertEqual(summary["child_backend_defaults"]["backend_type"], CHILD_BACKEND_VIT_B)
            self.assertEqual(summary["route_count"], 1)
            self.assertEqual(summary["route_experts"][0]["expert_backend"], "heatmap_blink")
            self.assertEqual(summary["route_experts"][0]["parent"], "Head")


if __name__ == "__main__":
    unittest.main()
