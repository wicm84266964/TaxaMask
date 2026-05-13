import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from AntSleap.core.project import ProjectManager
from AntSleap.core.external_backend import EXTERNAL_PREDICTION_SCHEMA, ExternalBackendRunner, external_prediction_to_internal_payload
from AntSleap.core.project_templates import PROJECT_TEMPLATE_ANT, PROJECT_TEMPLATE_GENERIC


class GenericExportSchemaTests(unittest.TestCase):
    def _build_project(self, work_dir: Path) -> ProjectManager:
        image_path = work_dir / "plant specimen.png"
        Image.new("RGB", (100, 80), color=(90, 140, 90)).save(image_path)

        manager = ProjectManager()
        manager.current_project_path = str(work_dir / "project.json")
        manager.project_data.update(
            {
                "name": "generic_export_demo",
                "taxonomy": ["Leaf blade", "Flower:petal"],
                "locator_scope": ["Leaf blade"],
                "images": [str(image_path)],
                "labels": {
                    str(image_path): {
                        "parts": {"Leaf blade": [[10, 10], [50, 10], [50, 40], [10, 40]]},
                        "boxes": {"Leaf blade": [10, 10, 50, 40]},
                        "descriptions": {"Leaf blade": "manual plant annotation"},
                        "status": "labeled",
                        "taxon": "Quercus",
                        "taxon_rank": "genus",
                    }
                },
            }
        )
        return manager

    def test_coco_uses_generic_supercategory_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            manager = self._build_project(work_dir)
            out_dir = work_dir / "coco"

            exported = manager.export_coco(str(out_dir))

            self.assertEqual(exported, 1)
            payload = json.loads((out_dir / "annotations.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["categories"][0]["supercategory"], "biological_structure")

    def test_yolo_dataset_yaml_quotes_custom_taxonomy_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            manager = self._build_project(work_dir)
            out_dir = work_dir / "yolo"

            exported = manager.export_yolo(str(out_dir))

            self.assertEqual(exported, 1)
            yaml_text = (out_dir / "dataset.yaml").read_text(encoding="utf-8")
            self.assertIn('0: "Leaf blade"', yaml_text)
            self.assertIn('1: "Flower:petal"', yaml_text)

    def test_project_supercategory_survives_save_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            manager = self._build_project(work_dir)
            manager.project_data["category_supercategory"] = "plant_structure"
            manager.save_project()

            reloaded = ProjectManager()
            reloaded.load_project(str(work_dir / "project.json"))

            self.assertEqual(reloaded.project_data["category_supercategory"], "plant_structure")

    def test_legacy_genus_loads_as_taxon_and_new_taxon_is_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            image_path = work_dir / "specimen.png"
            Image.new("RGB", (20, 20), color=(120, 120, 120)).save(image_path)
            project_path = work_dir / "project.json"
            project_path.write_text(
                json.dumps(
                    {
                        "name": "legacy",
                        "taxonomy": ["Leaf"],
                        "locator_scope": ["Leaf"],
                        "images": ["specimen.png"],
                        "labels": {
                            "specimen.png": {
                                "parts": {},
                                "descriptions": {},
                                "status": "unlabeled",
                                "genus": "Formica",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            manager = ProjectManager()
            manager.load_project(str(project_path))
            loaded_image = manager.project_data["images"][0]
            self.assertEqual(manager.get_taxon(loaded_image), "Formica")

            manager.set_taxon(loaded_image, "Quercus", taxon_rank="genus")
            saved = json.loads(project_path.read_text(encoding="utf-8"))
            saved_label = saved["labels"]["specimen.png"]
            self.assertEqual(saved_label["taxon"], "Quercus")
            self.assertEqual(saved_label["genus"], "Quercus")
            self.assertEqual(saved_label["taxon_rank"], "genus")

    def test_new_project_can_use_generic_or_ant_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            generic = ProjectManager()
            generic.create_project("generic", tmp, template_id=PROJECT_TEMPLATE_GENERIC)
            self.assertEqual(generic.project_data["taxonomy"], ["Object", "Region", "Structure"])
            self.assertEqual(generic.project_data["locator_scope"], ["Object"])
            self.assertEqual(generic.project_data["category_supercategory"], "biological_structure")

            ant = ProjectManager()
            ant.create_project("ant", tmp, template_id=PROJECT_TEMPLATE_ANT)
            self.assertEqual(ant.project_data["taxonomy"], ["Head", "Mesosoma", "Gaster"])
            self.assertEqual(ant.project_data["locator_scope"], ["Head", "Mesosoma", "Gaster"])
            self.assertEqual(ant.project_data["category_supercategory"], "ant_part")

    def test_relocated_roots_are_configured_not_hardcoded(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            old_marker = "old_dataset_root"
            relocated_root = work_dir / "new_dataset_root"
            relocated_image = relocated_root / "images" / "specimen.png"
            relocated_image.parent.mkdir(parents=True)
            Image.new("RGB", (12, 12), color=(100, 100, 100)).save(relocated_image)

            manager = ProjectManager()
            unresolved = manager._resolve_known_relocated_output(str(Path(old_marker) / "images" / "specimen.png"))
            self.assertIsNone(unresolved)

            manager.set_known_relocated_roots(
                [{"marker": old_marker, "relocated_root": str(relocated_root)}]
            )
            resolved = manager._resolve_known_relocated_output(str(Path(old_marker) / "images" / "specimen.png"))
            self.assertEqual(Path(resolved), relocated_image)

    def test_project_image_health_and_remap_preview_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            old_root = work_dir / "old_root"
            new_root = work_dir / "new_root"
            old_image = old_root / "images" / "specimen.png"
            new_image = new_root / "images" / "specimen.png"
            new_image.parent.mkdir(parents=True)
            Image.new("RGB", (12, 12), color=(120, 80, 80)).save(new_image)

            manager = ProjectManager()
            manager.current_project_path = str(work_dir / "project.json")
            manager.project_data["images"] = [str(old_image)]
            manager.project_data["labels"] = {
                str(old_image): {
                    "parts": {"Head": [[1, 1], [5, 1], [5, 5]]},
                    "status": "labeled",
                    "genus": "Unknown",
                }
            }
            manager.project_data["scales"] = {str(old_image): 12.5}
            manager.project_data["image_provenance"] = {str(old_image): {"source": "manual"}}

            health = manager.get_image_path_health()
            self.assertEqual(health["missing_count"], 1)
            self.assertEqual(health["existing_count"], 0)

            preview = manager.preview_image_path_remap(str(new_root))
            self.assertEqual(len(preview["matches"]), 1)
            self.assertEqual(Path(preview["matches"][0]["new_path"]), new_image)
            self.assertEqual(preview["unresolved"], [])

            changed = manager.apply_image_path_remap(preview["matches"], save=False)
            self.assertEqual(changed, 1)
            self.assertEqual(manager.project_data["images"], [str(new_image)])
            self.assertIn(str(new_image), manager.project_data["labels"])
            self.assertIn(str(new_image), manager.project_data["scales"])
            self.assertIn(str(new_image), manager.project_data["image_provenance"])

    def test_project_image_remap_leaves_duplicate_names_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            new_root = work_dir / "new_root"
            for folder in ("a", "b"):
                image_path = new_root / folder / "specimen.png"
                image_path.parent.mkdir(parents=True)
                Image.new("RGB", (12, 12), color=(100, 100, 100)).save(image_path)

            manager = ProjectManager()
            missing = work_dir / "old_root" / "specimen.png"
            manager.project_data["images"] = [str(missing)]

            preview = manager.preview_image_path_remap(str(new_root))
            self.assertEqual(preview["matches"], [])
            self.assertEqual(preview["unresolved"], [str(missing)])

    def test_external_backend_runner_contract_and_prediction_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            image_path = work_dir / "leaf.png"
            Image.new("RGB", (24, 24), color=(80, 120, 80)).save(image_path)
            script_path = work_dir / "external_backend_dummy.py"
            script_path.write_text(
                "\n".join(
                    [
                        "import argparse, json, os",
                        "parser = argparse.ArgumentParser()",
                        "parser.add_argument('--contract', required=True)",
                        "args = parser.parse_args()",
                        "contract = json.load(open(args.contract, encoding='utf-8'))",
                        "os.makedirs(os.path.dirname(contract['prediction_json']), exist_ok=True)",
                        "json.dump({",
                        f"  'schema_version': '{EXTERNAL_PREDICTION_SCHEMA}',",
                        "  'image_path': contract['image_path'],",
                        "  'polygons': {'Leaf': [[1, 1], [10, 1], [10, 10]], 'NotInTaxonomy': [[0, 0], [1, 0], [1, 1]]},",
                        "  'boxes': {'Leaf': [1, 1, 10, 10]},",
                        "  'scores': {'Leaf': 0.9},",
                        "}, open(contract['prediction_json'], 'w', encoding='utf-8'))",
                    ]
                ),
                encoding="utf-8",
            )

            manager = ProjectManager()
            manager.create_project("external_demo", tmp, template_id=PROJECT_TEMPLATE_GENERIC)
            manager.project_data["taxonomy"] = ["Leaf"]
            manager.set_locator_scope(["Leaf"], save=False)
            manager.current_project_path = str(work_dir / "external_demo.json")
            manager.save_project()

            runner = ExternalBackendRunner(
                manager,
                {
                    "backend_id": "dummy_backend",
                    "predict_command": f"python {script_path} --contract {{contract_json}}",
                },
                runs_root=str(work_dir / "external_runs"),
            )
            result = runner.run_predict(str(image_path))

            self.assertTrue(Path(result["contract_json"]).exists())
            self.assertTrue(Path(result["prediction_json"]).exists())
            self.assertIn("Leaf", result["payload"]["polygons"])
            self.assertNotIn("NotInTaxonomy", result["payload"]["polygons"])

    def test_external_prediction_conversion_filters_unknown_labels(self):
        payload = external_prediction_to_internal_payload(
            {
                "polygons": {"Leaf": [[1, 1], [2, 1], [2, 2]], "Head": [[0, 0], [1, 0], [1, 1]]},
                "boxes": {"Leaf": [1, 1, 2, 2], "Head": [0, 0, 1, 1]},
            },
            ["Leaf"],
        )
        self.assertEqual(set(payload["polygons"].keys()), {"Leaf"})
        self.assertEqual(set(payload["auto_boxes"].keys()), {"Leaf"})

    def test_external_backend_runner_train_writes_manifest_without_builtin_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            script_path = work_dir / "external_train_dummy.py"
            script_path.write_text(
                "\n".join(
                    [
                        "import argparse, json, os",
                        "parser = argparse.ArgumentParser()",
                        "parser.add_argument('--contract', required=True)",
                        "args = parser.parse_args()",
                        "contract = json.load(open(args.contract, encoding='utf-8'))",
                        "if contract['action'] == 'prepare_dataset':",
                        "    os.makedirs(contract['dataset_dir'], exist_ok=True)",
                        "    json.dump({'prepared': True}, open(os.path.join(contract['dataset_dir'], 'dataset_manifest.json'), 'w', encoding='utf-8'))",
                        "elif contract['action'] == 'train':",
                        "    os.makedirs(os.path.dirname(contract['model_manifest']), exist_ok=True)",
                        "    json.dump({",
                        "      'schema_version': 'taxamask_model_manifest_v1',",
                        "      'model_id': 'dummy/train',",
                        "      'backend_id': contract['backend_id'],",
                        "      'taxonomy': contract['taxonomy'],",
                        "      'locator_scope': contract['locator_scope'],",
                        "      'weights': {'main': 'dummy.pt'},",
                        "    }, open(contract['model_manifest'], 'w', encoding='utf-8'))",
                    ]
                ),
                encoding="utf-8",
            )

            manager = ProjectManager()
            manager.create_project("external_train_demo", tmp, template_id=PROJECT_TEMPLATE_GENERIC)
            runner = ExternalBackendRunner(
                manager,
                {
                    "backend_id": "dummy_train_backend",
                    "prepare_dataset_command": f"python {script_path} --contract {{contract}}",
                    "train_command": f"python {script_path} --contract {{contract_json}}",
                },
                runs_root=str(work_dir / "external_runs"),
            )
            summary = runner.run_prepare_and_train()

            self.assertTrue(Path(summary["contract_json"]).exists())
            self.assertTrue(Path(summary["model_manifest"]).exists())
            self.assertEqual(summary["manifest"]["schema_version"], "taxamask_model_manifest_v1")
            run_dir = Path(summary["run_dir"])
            self.assertFalse(list(run_dir.rglob("locator_*.pth")))
            self.assertFalse(list(run_dir.rglob("sam_decoder_lora_*.pth")))


if __name__ == "__main__":
    unittest.main()
