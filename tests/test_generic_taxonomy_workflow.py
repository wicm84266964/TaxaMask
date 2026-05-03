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
            manager.save_project()

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


if __name__ == "__main__":
    unittest.main()
