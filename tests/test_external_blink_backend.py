import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANTSLEAP_ROOT = PROJECT_ROOT / "AntSleap"
if str(ANTSLEAP_ROOT) not in sys.path:
    sys.path.insert(0, str(ANTSLEAP_ROOT))

from core.cascade_manager import CascadingManager
from core.blink_expert_backends import create_default_blink_backend_registry
from core.cascade_routes import ROUTE_BACKEND_EXTERNAL_BLINK
from core.external_blink_backend import (
    EXTERNAL_BLINK_CONTRACT_SCHEMA,
    EXTERNAL_BLINK_PREDICTION_SCHEMA,
    ExternalBlinkBackendRunner,
)
from core.project import ProjectManager


class ExternalBlinkBackendTests(unittest.TestCase):
    def _script(self, work_dir):
        script_path = Path(work_dir) / "external_blink_dummy.py"
        script_path.write_text(
            "\n".join(
                [
                    "import argparse, json, os",
                    "parser = argparse.ArgumentParser()",
                    "parser.add_argument('--contract', required=True)",
                    "args = parser.parse_args()",
                    "contract = json.load(open(args.contract, encoding='utf-8'))",
                    "assert contract['schema_version'] == 'taxamask_external_blink_contract_v1'",
                    "assert contract['action'] == 'predict_child'",
                    "os.makedirs(os.path.dirname(contract['prediction_json']), exist_ok=True)",
                    "json.dump({",
                    f"  'schema_version': '{EXTERNAL_BLINK_PREDICTION_SCHEMA}',",
                    "  'child_part': contract['child_part'],",
                    "  'box': [12.0, 14.0, 32.0, 36.0],",
                    "  'score': 0.88,",
                    "  'model_id': 'dummy/external_blink',",
                    "}, open(contract['prediction_json'], 'w', encoding='utf-8'))",
                ]
            ),
            encoding="utf-8",
        )
        return script_path

    def test_runner_writes_predict_child_contract_and_reads_box(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir)
            image_path = work_dir / "specimen.png"
            Image.new("RGB", (64, 64), color=(180, 180, 180)).save(image_path)
            script_path = self._script(work_dir)

            manager = ProjectManager()
            manager.create_project("external_blink_demo", tmp_dir)
            manager.add_taxonomy_part("Eye")
            manager.current_project_path = str(work_dir / "project.json")
            manager.save_project()

            runner = ExternalBlinkBackendRunner(
                manager,
                {
                    "backend_id": "dummy_external_blink",
                    "predict_command": f"python {script_path} --contract {{contract_json}}",
                },
                runs_root=str(work_dir / "runs"),
            )
            summary = runner.run_predict_child(
                image_path=str(image_path),
                parent_part="Head",
                child_part="Eye",
                parent_box=[5.0, 5.0, 50.0, 50.0],
            )

            contract = json.loads(Path(summary["contract_json"]).read_text(encoding="utf-8"))
            self.assertEqual(contract["schema_version"], EXTERNAL_BLINK_CONTRACT_SCHEMA)
            self.assertEqual(contract["action"], "predict_child")
            self.assertEqual(contract["parent_part"], "Head")
            self.assertEqual(contract["child_part"], "Eye")
            self.assertEqual(summary["result"]["box"], [12.0, 14.0, 32.0, 36.0])
            self.assertEqual(summary["result"]["confidence"], 0.88)

    def test_external_blink_route_backend_calls_contract_runner(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir)
            image_path = work_dir / "specimen.png"
            Image.new("RGB", (64, 64), color=(180, 180, 180)).save(image_path)
            script_path = self._script(work_dir)

            project = ProjectManager()
            project.create_project("external_blink_route", tmp_dir)
            project.add_taxonomy_part("Eye")
            project.current_project_path = str(work_dir / "project.json")
            project.save_project()

            weights_dir = work_dir / "weights"
            manager = CascadingManager.__new__(CascadingManager)
            manager.engine = types.SimpleNamespace(device="cpu", weights_dir=str(weights_dir))
            manager.device = "cpu"
            manager.project_manager = project
            manager.loaded_experts = {}
            manager.expert_dir = str(weights_dir / "experts")
            manager.route_manifest_path = str(weights_dir / "experts" / "cascade_routes.json")
            manager.legacy_route_manifest = {"version": "", "approved": False, "routes": []}
            manager.blink_backend_registry = create_default_blink_backend_registry()

            route = {
                "parent": "Head",
                "child": "Eye",
                "enabled": True,
                "expert_backend": ROUTE_BACKEND_EXTERNAL_BLINK,
                "backend_params": {
                    "backend_id": "dummy_external_blink",
                    "predict_command": f"python {script_path} --contract {{contract_json}}",
                },
            }
            self.assertIsNone(manager.get_route_block_reason(route))
            result = manager.infer_child_part(
                str(image_path),
                [5.0, 5.0, 50.0, 50.0],
                "Eye",
                parent_part="Head",
                route_manifest={"version": "project-v2", "routes": [route]},
            )

            self.assertEqual(result["backend"], ROUTE_BACKEND_EXTERNAL_BLINK)
            self.assertEqual(result["box"], [12.0, 14.0, 32.0, 36.0])
            self.assertTrue(Path(result["contract_json"]).exists())


if __name__ == "__main__":
    unittest.main()
