import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from AntSleap.core.project import ProjectManager
from AntSleap.core.project_templates import PROJECT_TEMPLATE_GENERIC
from AntSleap.core.training_preflight import build_training_preflight


class GenericTaxonomyWorkflowTests(unittest.TestCase):
    def test_generic_project_saves_reopens_and_preflights_without_ant_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            image_path = work_dir / "leaf.png"
            Image.new("RGB", (96, 64), color=(80, 130, 80)).save(image_path)

            manager = ProjectManager()
            manager.create_project("plant_project", tmp, template_id=PROJECT_TEMPLATE_GENERIC)
            manager.project_data["taxonomy"] = ["Leaf", "Flower", "Fruit"]
            manager.set_locator_scope(["Leaf"], save=False)
            manager.project_data["images"] = [str(image_path)]
            manager.project_data["labels"][str(image_path)] = {
                "parts": {"Leaf": [[10, 10], [50, 12], [48, 40], [12, 38]]},
                "boxes": {"Leaf": [10, 10, 50, 40]},
                "descriptions": {"Leaf": "manual verified leaf mask"},
                "status": "labeled",
                "taxon": "Quercus",
                "taxon_rank": "genus",
            }
            manager.save_project(force=True)

            reloaded = ProjectManager()
            reloaded.load_project(manager.current_project_path)
            loaded_image = reloaded.project_data["images"][0]

            self.assertEqual(reloaded.project_data["taxonomy"], ["Leaf", "Flower", "Fruit"])
            self.assertEqual(reloaded.get_locator_scope(), ["Leaf"])
            self.assertEqual(reloaded.get_taxon(loaded_image), "Quercus")

            preflight = build_training_preflight(
                reloaded.project_data["images"],
                reloaded.project_data["labels"],
                reloaded.project_data["taxonomy"],
                reloaded.get_locator_scope(),
            )
            self.assertEqual(preflight["locator_image_count"], 1)
            self.assertEqual(preflight["parts_image_count"], 1)
            self.assertEqual(preflight["locator_part_counts"]["Leaf"], 1)
            self.assertNotIn("Head", preflight["taxonomy"])

    def test_generic_multimodal_export_contains_taxamask_schema_and_taxon(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            image_path = work_dir / "flower.png"
            Image.new("RGB", (80, 80), color=(160, 90, 120)).save(image_path)

            manager = ProjectManager()
            manager.create_project("flower_project", tmp, template_id=PROJECT_TEMPLATE_GENERIC)
            manager.project_data["taxonomy"] = ["Flower"]
            manager.set_locator_scope(["Flower"], save=False)
            manager.project_data["images"] = [str(image_path)]
            manager.project_data["labels"][str(image_path)] = {
                "parts": {"Flower": [[15, 15], [60, 18], [55, 58], [18, 56]]},
                "boxes": {"Flower": [15, 15, 60, 58]},
                "descriptions": {"Flower": "manual verified flower mask"},
                "status": "labeled",
                "taxon": "Rosa",
                "taxon_rank": "genus",
            }

            out_dir = work_dir / "multimodal"
            exported = manager.export_multimodal_dataset(str(out_dir))

            self.assertEqual(exported, 1)
            record = json.loads((out_dir / "multimodal_dataset.jsonl").read_text(encoding="utf-8").strip())
            self.assertEqual(record["schema_version"], "taxamask-multimodal-sample-v1")
            self.assertEqual(record["taxon"], "Rosa")
            self.assertEqual(record["label"], "Flower")
            self.assertNotIn("formica", json.dumps(record).lower())

    def test_add_images_reports_progress_and_skips_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            first_image = work_dir / "first.png"
            second_image = work_dir / "second.png"
            Image.new("RGB", (24, 24), color=(90, 100, 110)).save(first_image)
            Image.new("RGB", (24, 24), color=(120, 130, 140)).save(second_image)

            manager = ProjectManager()
            manager.create_project("progress_project", tmp, template_id=PROJECT_TEMPLATE_GENERIC)
            progress = []

            added = manager.add_images(
                [str(first_image), str(second_image), str(first_image)],
                progress_callback=lambda done, total, label: progress.append((done, total, Path(label).name if label else "")),
            )

            self.assertEqual(added, 2)
            self.assertEqual(len(manager.project_data["images"]), 2)
            self.assertEqual(progress[0], (0, 3, ""))
            self.assertEqual(progress[-1], (3, 3, "first.png"))
            self.assertEqual([item[0] for item in progress], [0, 1, 2, 3])

    def test_remove_images_saves_once_and_clears_related_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            image_paths = []
            for index in range(4):
                image_path = work_dir / f"candidate_{index}.png"
                Image.new("RGB", (24, 24), color=(90 + index, 100, 110)).save(image_path)
                image_paths.append(str(image_path))

            manager = ProjectManager()
            manager.create_project("remove_project", tmp, template_id=PROJECT_TEMPLATE_GENERIC)
            manager.add_images(image_paths, save=False)
            for image_path in image_paths:
                manager.project_data["labels"][image_path]["parts"]["Head"] = [[1, 1], [8, 1], [8, 8]]
                manager.project_data["scales"][image_path] = 100.0
                manager.set_image_provenance(image_path, {"source": "pdf_candidate"}, save=False)

            save_calls = []
            original_save = manager.save_project

            def counted_save():
                save_calls.append("save")
                return original_save()

            manager.save_project = counted_save
            progress = []
            removed = manager.remove_images(
                image_paths[:3],
                progress_callback=lambda done, total, label: progress.append((done, total, Path(label).name if label else "")),
            )

            self.assertEqual(removed, 3)
            self.assertEqual(save_calls, ["save"])
            self.assertEqual(manager.project_data["images"], [image_paths[3]])
            for removed_path in image_paths[:3]:
                self.assertNotIn(removed_path, manager.project_data["labels"])
                self.assertNotIn(removed_path, manager.project_data["scales"])
                self.assertNotIn(removed_path, manager.project_data["image_provenance"])
            self.assertEqual(progress[0], (0, 3, ""))
            self.assertEqual(progress[-1], (3, 3, "candidate_2.png"))

    def test_remove_taxonomy_part_saves_once_for_large_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            manager = ProjectManager()
            manager.create_project("taxonomy_remove_project", tmp, template_id=PROJECT_TEMPLATE_GENERIC)
            manager.project_data["taxonomy"] = ["Head", "Mandible"]
            image_paths = []
            for index in range(25):
                image_path = work_dir / f"specimen_{index:03d}.png"
                Image.new("RGB", (12, 12), color=(index, 100, 110)).save(image_path)
                image_paths.append(str(image_path))
                manager.project_data["images"].append(str(image_path))
                manager.project_data["labels"][str(image_path)] = {
                    "parts": {"Mandible": [[1, 1], [8, 1], [8, 8]]},
                    "boxes": {"Mandible": [1, 1, 8, 8]},
                    "descriptions": {"Mandible": "manual"},
                    "status": "labeled",
                    "genus": "Unknown",
                    "taxon": "Unknown",
                }

            save_calls = []
            original_save = manager.save_project

            def counted_save():
                save_calls.append("save")
                return original_save()

            manager.save_project = counted_save
            removed = manager.remove_taxonomy_part("Mandible")

            self.assertTrue(removed)
            self.assertEqual(save_calls, ["save"])
            self.assertNotIn("Mandible", manager.project_data["taxonomy"])
            self.assertTrue(all("Mandible" not in entry.get("parts", {}) for entry in manager.project_data["labels"].values()))


if __name__ == "__main__":
    unittest.main()
