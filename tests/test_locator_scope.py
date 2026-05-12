# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false, reportIndexIssue=false

import json
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.project import ProjectManager


class LocatorScopeTests(unittest.TestCase):
    def test_new_project_defaults_to_three_part_taxonomy_and_scope(self):
        pm = ProjectManager()
        self.assertEqual(pm.project_data["taxonomy"], ["Head", "Mesosoma", "Gaster"])
        self.assertEqual(pm.get_locator_scope(), ["Head", "Mesosoma", "Gaster"])

    def test_legacy_project_without_locator_scope_keeps_taxonomy_as_scope(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir) / "legacy.json"
            project_path.write_text(
                json.dumps(
                    {
                        "name": "legacy",
                        "taxonomy": ["Head", "Mesosoma", "Gaster", "Mandible", "Eye"],
                        "images": [],
                        "labels": {},
                        "scales": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            pm = ProjectManager()
            pm.load_project(str(project_path))

            self.assertEqual(pm.project_data["taxonomy"], ["Head", "Mesosoma", "Gaster", "Mandible", "Eye"])
            self.assertEqual(pm.get_locator_scope(), ["Head", "Mesosoma", "Gaster", "Mandible", "Eye"])

    def test_adding_small_parts_does_not_expand_locator_scope(self):
        pm = ProjectManager()
        pm.add_taxonomy_part("Mandible")
        pm.add_taxonomy_part("Eye")

        self.assertEqual(pm.project_data["taxonomy"], ["Head", "Mesosoma", "Gaster", "Mandible", "Eye"])
        self.assertEqual(pm.get_locator_scope(), ["Head", "Mesosoma", "Gaster"])

    def test_add_taxonomy_part_rejects_path_like_names(self):
        pm = ProjectManager()

        self.assertFalse(pm.add_taxonomy_part("../Mandible"))
        self.assertFalse(pm.add_taxonomy_part("..\\Mandible"))
        self.assertFalse(pm.add_taxonomy_part("Mandible/Eye"))
        self.assertFalse(pm.add_taxonomy_part("Mandible\\Eye"))
        self.assertFalse(pm.add_taxonomy_part("C:Mandible"))
        self.assertEqual(pm.project_data["taxonomy"], ["Head", "Mesosoma", "Gaster"])

    def test_blink_context_parent_round_trips_per_project(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pm = ProjectManager()
            pm.create_project("blink_memory", tmp_dir)
            pm.add_taxonomy_part("Mandible")

            remembered = pm.remember_blink_context_parent("Mandible", "Head")

            self.assertTrue(remembered)
            self.assertEqual(pm.get_blink_context_parent("Mandible"), "Head")

            reloaded = ProjectManager()
            reloaded.load_project(pm.current_project_path)

            self.assertEqual(
                reloaded.get_blink_context_roi_parents(),
                {"Mandible": "Head"},
            )

    def test_project_cascade_routes_round_trip_with_portable_expert_reference(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pm = ProjectManager()
            pm.create_project("route_memory", tmp_dir)
            pm.add_taxonomy_part("Mandible")

            pm.register_cascade_route_candidate("Head", "Mandible", save=False)
            pm.appoint_cascade_route_expert(
                "Head",
                "Mandible",
                expert_id="Mandible/expert_v20260501_090000.pth",
                save=False,
            )
            pm.set_cascade_route_enabled("Head", "Mandible", True, save=False)
            pm.save_project()

            reloaded = ProjectManager()
            reloaded.load_project(pm.current_project_path)
            route = reloaded.get_cascade_route("Head", "Mandible")

            self.assertIsNotNone(route)
            self.assertTrue(route.get("enabled"))
            self.assertEqual(reloaded.get_cascade_routes().get("version"), "project-v2")
            self.assertEqual(route.get("expert_id"), "Mandible/expert_v20260501_090000.pth")
            self.assertEqual(route.get("expert_part"), "Mandible")
            self.assertEqual(route.get("expert_filename"), "expert_v20260501_090000.pth")
            self.assertEqual(route.get("appointed_expert", {}).get("expert_id"), "Mandible/expert_v20260501_090000.pth")
            self.assertEqual(
                [candidate.get("expert_id") for candidate in route.get("expert_candidates", [])],
                ["Mandible/expert_v20260501_090000.pth"],
            )

    def test_legacy_flat_route_migrates_to_project_v2_on_load_and_save(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir) / "legacy_routes.json"
            project_path.write_text(
                json.dumps(
                    {
                        "name": "legacy_routes",
                        "taxonomy": ["Head", "Mesosoma", "Gaster", "Mandible"],
                        "locator_scope": ["Head", "Mesosoma", "Gaster"],
                        "images": [],
                        "labels": {},
                        "scales": {},
                        "cascade_routes": {
                            "version": "project-v1",
                            "routes": [
                                {
                                    "parent": "Head",
                                    "child": "Mandible",
                                    "enabled": True,
                                    "expert_id": "Mandible/expert_v20260501_090000.pth",
                                    "expert_part": "Mandible",
                                    "expert_filename": "expert_v20260501_090000.pth",
                                    "registration_source": "blink_candidate",
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            pm = ProjectManager()
            pm.load_project(str(project_path))
            route = pm.get_cascade_route("Head", "Mandible")

            self.assertIsNotNone(route)
            self.assertEqual(pm.get_cascade_routes().get("version"), "project-v2")
            self.assertEqual(route.get("appointed_expert", {}).get("expert_id"), "Mandible/expert_v20260501_090000.pth")
            self.assertEqual(
                [candidate.get("expert_id") for candidate in route.get("expert_candidates", [])],
                ["Mandible/expert_v20260501_090000.pth"],
            )

            pm.save_project()
            saved = json.loads(project_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["cascade_routes"]["version"], "project-v2")
            saved_route = saved["cascade_routes"]["routes"][0]
            self.assertEqual(saved_route["appointed_expert"]["expert_id"], "Mandible/expert_v20260501_090000.pth")
            self.assertEqual(saved_route["expert_candidates"][0]["expert_id"], "Mandible/expert_v20260501_090000.pth")

    def test_appointing_new_expert_preserves_previous_expert_as_history_candidate(self):
        pm = ProjectManager()
        pm.add_taxonomy_part("Mandible")
        pm.register_cascade_route_candidate("Head", "Mandible", save=False)
        pm.appoint_cascade_route_expert("Head", "Mandible", expert_id="Mandible/expert_v20260501_090000.pth", save=False)

        updated = pm.appoint_cascade_route_expert(
            "Head",
            "Mandible",
            expert_id="Mandible/mandible_v2.pth",
            save=False,
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.get("appointed_expert", {}).get("expert_id"), "Mandible/mandible_v2.pth")
        self.assertEqual(updated.get("expert_id"), "Mandible/mandible_v2.pth")
        self.assertEqual(
            [candidate.get("expert_id") for candidate in updated.get("expert_candidates", [])],
            ["Mandible/mandible_v2.pth", "Mandible/expert_v20260501_090000.pth"],
        )

    def test_new_training_candidate_is_first_without_overwriting_appointed_expert(self):
        pm = ProjectManager()
        pm.add_taxonomy_part("Mandible")
        pm.register_cascade_route_candidate(
            "Head",
            "Mandible",
            expert_id="Mandible/expert_v20260501_090000.pth",
            save=False,
        )
        pm.appoint_cascade_route_expert("Head", "Mandible", expert_id="Mandible/expert_v20260501_090000.pth", save=False)

        updated = pm.register_cascade_route_candidate(
            "Head",
            "Mandible",
            expert_id="Mandible/expert_v20260512_120000.pth",
            registration_source="blink_training",
            save=False,
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.get("appointed_expert", {}).get("expert_id"), "Mandible/expert_v20260501_090000.pth")
        self.assertEqual(updated.get("expert_id"), "Mandible/expert_v20260501_090000.pth")
        self.assertEqual(
            [candidate.get("expert_id") for candidate in updated.get("expert_candidates", [])],
            ["Mandible/expert_v20260512_120000.pth", "Mandible/expert_v20260501_090000.pth"],
        )

    def test_route_accessors_do_not_leak_mutable_nested_state(self):
        pm = ProjectManager()
        pm.add_taxonomy_part("Mandible")
        pm.register_cascade_route_candidate("Head", "Mandible", save=False)
        pm.appoint_cascade_route_expert("Head", "Mandible", expert_id="Mandible/expert_v20260501_090000.pth", save=False)

        route_copy = pm.get_cascade_route("Head", "Mandible")
        self.assertIsNotNone(route_copy)

        route_copy["appointed_expert"]["expert_id"] = "Mandible/hacked.pth"
        route_copy["expert_candidates"][0]["expert_id"] = "Mandible/hacked.pth"

        stored_route = pm.get_cascade_route("Head", "Mandible")
        self.assertEqual(stored_route.get("appointed_expert", {}).get("expert_id"), "Mandible/expert_v20260501_090000.pth")
        self.assertEqual(
            [candidate.get("expert_id") for candidate in stored_route.get("expert_candidates", [])],
            ["Mandible/expert_v20260501_090000.pth"],
        )

    def test_project_cascade_route_candidate_stays_disabled_until_manual_enable(self):
        pm = ProjectManager()
        pm.add_taxonomy_part("Mandible")
        route = pm.register_cascade_route_candidate("Head", "Mandible", save=False)

        self.assertIsNotNone(route)
        self.assertFalse(route.get("enabled"))

    def test_remove_taxonomy_part_clears_related_cascade_routes(self):
        pm = ProjectManager()
        pm.add_taxonomy_part("Mandible")
        pm.register_cascade_route_candidate("Head", "Mandible", save=False)
        pm.appoint_cascade_route_expert("Head", "Mandible", expert_id="Mandible/expert_v20260501_090000.pth", save=False)

        removed = pm.remove_taxonomy_part("Mandible")

        self.assertTrue(removed)
        self.assertIsNone(pm.get_cascade_route("Head", "Mandible"))

    def test_blink_context_parent_does_not_leak_between_projects(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pm_one = ProjectManager()
            pm_one.create_project("project_one", tmp_dir)
            pm_one.add_taxonomy_part("Mandible")
            pm_one.remember_blink_context_parent("Mandible", "Head")

            pm_two = ProjectManager()
            pm_two.create_project("project_two", tmp_dir)
            pm_two.add_taxonomy_part("Mandible")

            self.assertIsNone(pm_two.get_blink_context_parent("Mandible"))
            self.assertEqual(pm_two.get_blink_context_roi_parents(), {})

    def test_remove_taxonomy_part_clears_blink_context_parent_preferences(self):
        pm = ProjectManager()
        pm.add_taxonomy_part("Mandible")
        pm.add_taxonomy_part("Eye")
        pm.remember_blink_context_parent("Mandible", "Head", save=False)
        pm.remember_blink_context_parent("Eye", "Head", save=False)

        removed = pm.remove_taxonomy_part("Head")

        self.assertTrue(removed)
        self.assertEqual(pm.get_blink_context_roi_parents(), {})

    def test_update_label_can_defer_disk_save(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pm = ProjectManager()
            pm.create_project("deferred_update", tmp_dir)

            image_path = str(Path(tmp_dir) / "specimen.png")
            rel_image_path = Path(image_path).name
            pm.project_data["images"] = [image_path]
            pm.project_data["labels"][image_path] = {
                "parts": {},
                "status": "unlabeled",
                "genus": "Unknown",
                "descriptions": {},
                "boxes": {},
                "auto_boxes": {},
            }
            pm.save_project()

            pm.update_label(
                image_path,
                "Head",
                [[10.0, 10.0], [24.0, 10.0], [18.0, 24.0]],
                save=False,
            )

            self.assertIn("Head", pm.project_data["labels"][image_path]["parts"])

            on_disk_before_flush = json.loads(Path(pm.current_project_path).read_text(encoding="utf-8"))
            self.assertEqual(on_disk_before_flush["labels"][rel_image_path]["parts"], {})

            pm.save_project()
            on_disk_after_flush = json.loads(Path(pm.current_project_path).read_text(encoding="utf-8"))
            self.assertIn("Head", on_disk_after_flush["labels"][rel_image_path]["parts"])

    def test_delete_label_can_defer_disk_save(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pm = ProjectManager()
            pm.create_project("deferred_delete", tmp_dir)

            image_path = str(Path(tmp_dir) / "specimen.png")
            rel_image_path = Path(image_path).name
            pm.project_data["images"] = [image_path]
            pm.project_data["labels"][image_path] = {
                "parts": {"Head": [[10.0, 10.0], [24.0, 10.0], [18.0, 24.0]]},
                "status": "labeled",
                "genus": "Unknown",
                "descriptions": {"Head": "probe"},
                "boxes": {"Head": [8.0, 8.0, 26.0, 26.0]},
                "auto_boxes": {},
            }
            pm.save_project()

            pm.delete_label(image_path, "Head", save=False)

            self.assertNotIn("Head", pm.project_data["labels"][image_path]["parts"])

            on_disk_before_flush = json.loads(Path(pm.current_project_path).read_text(encoding="utf-8"))
            self.assertIn("Head", on_disk_before_flush["labels"][rel_image_path]["parts"])

            pm.save_project()
            on_disk_after_flush = json.loads(Path(pm.current_project_path).read_text(encoding="utf-8"))
            self.assertNotIn("Head", on_disk_after_flush["labels"][rel_image_path]["parts"])

    def test_current_project_expert_bucket_impacts_only_report_matching_current_project_routes(self):
        pm = ProjectManager()
        pm.add_taxonomy_part("Mandible")
        pm.add_taxonomy_part("Eye")
        pm.register_cascade_route_candidate("Head", "Mandible", save=False)
        pm.register_cascade_route_candidate("Eye", "Mandible", save=False)
        pm.register_cascade_route_candidate("Head", "Eye", save=False)
        pm.appoint_cascade_route_expert("Head", "Mandible", expert_id="Mandible/expert_v20260501_090000.pth", save=False)
        pm.appoint_cascade_route_expert("Eye", "Mandible", expert_id="Mandible/mandible_v2.pth", save=False)
        pm.appoint_cascade_route_expert("Head", "Eye", expert_id="Eye/expert_v20260501_091500.pth", save=False)

        impact = pm.get_current_project_expert_bucket_impacts("Mandible")

        self.assertEqual(impact.get("child_part"), "Mandible")
        self.assertEqual(
            [(route.get("parent"), route.get("child")) for route in impact.get("routes", [])],
            [("Eye", "Mandible"), ("Head", "Mandible")],
        )
        self.assertEqual(
            [route.get("appointed_expert_id") for route in impact.get("routes", [])],
            ["Mandible/mandible_v2.pth", "Mandible/expert_v20260501_090000.pth"],
        )

    def test_remove_current_project_expert_bucket_routes_only_cleans_matching_child_routes(self):
        pm = ProjectManager()
        pm.add_taxonomy_part("Mandible")
        pm.add_taxonomy_part("Eye")
        pm.register_cascade_route_candidate("Head", "Mandible", save=False)
        pm.register_cascade_route_candidate("Eye", "Mandible", save=False)
        pm.register_cascade_route_candidate("Head", "Eye", save=False)

        removed_count = pm.remove_current_project_expert_bucket_routes("Mandible", save=False)

        self.assertEqual(removed_count, 2)
        self.assertIsNone(pm.get_cascade_route("Head", "Mandible"))
        self.assertIsNone(pm.get_cascade_route("Eye", "Mandible"))
        self.assertIsNotNone(pm.get_cascade_route("Head", "Eye"))


if __name__ == "__main__":
    unittest.main()
