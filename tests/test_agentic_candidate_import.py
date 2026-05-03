import json
import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AgenticCandidateImportTests(unittest.TestCase):
    def test_import_candidates_preserves_image_provenance(self):
        tmp = PROJECT_ROOT / "artifacts" / "test_cases" / "candidate_import"
        tmp.mkdir(parents=True, exist_ok=True)
        image_path = tmp / "lateral.png"
        Image.new("RGB", (64, 48), color=(120, 130, 140)).save(image_path)

        project_path = tmp / "project.json"
        project_path.write_text(
            json.dumps(
                {
                    "name": "demo",
                    "taxonomy": ["Head", "Mesosoma", "Gaster"],
                    "locator_scope": ["Head", "Mesosoma", "Gaster"],
                    "images": [],
                    "labels": {},
                    "scales": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        candidates_path = tmp / "candidates.json"
        candidates_path.write_text(
            json.dumps(
                {
                    "schema_version": "core2-candidate-bridge-v1",
                    "mode": "candidate_only",
                    "candidates": [
                        {
                            "candidate_id": "cand_1",
                            "candidate_stable_id": "stable_1",
                            "image_id": 7,
                            "pdf_id": 3,
                            "pdf_file": "paper.pdf",
                            "pdf_file_path": str(tmp / "paper.pdf"),
                            "page_number": 2,
                            "image_path": str(image_path),
                            "image_file_name": image_path.name,
                            "source_ref": {"db_path": str(tmp / "extract.db"), "table": "figure_records", "row_id": 7},
                            "confidence": {"final_confidence": 0.99},
                            "is_taxonomic": True,
                            "review_status": "accepted",
                            "multimodal_review_mode": "real",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        routing_path = tmp / "routing.json"
        routing_path.write_text(
            json.dumps(
                {
                    "schema_version": "core2-routing-v1",
                    "decisions": [
                        {
                            "candidate_id": "cand_1",
                            "bucket": "Core-2",
                            "view": "lateral",
                            "confidence": 0.99,
                            "risk_tier": "low",
                            "route_reasons": ["core2_target_confident"],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        out_project = tmp / "project_imported.json"
        manifest = tmp / "import_manifest.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "agentic" / "import_candidates_to_project.py"),
                "--project",
                str(project_path),
                "--out",
                str(out_project),
                "--routing",
                str(routing_path),
                "--candidates",
                str(candidates_path),
                "--manifest",
                str(manifest),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(out_project.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["images"]), 1)
        provenance = next(iter(payload["image_provenance"].values()))
        self.assertEqual(provenance["candidate_id"], "cand_1")
        self.assertEqual(provenance["routing"]["bucket"], "Core-2")


if __name__ == "__main__":
    unittest.main()
