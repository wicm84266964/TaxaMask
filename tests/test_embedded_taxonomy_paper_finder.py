from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PROJECT_ROOT / "vendor" / "ant-code" / "config" / "skills"
SKILL_ROOT = SKILLS_ROOT / "taxonomy-paper-finder"


def load_bridge_module():
    path = SKILL_ROOT / "scripts" / "bridge_to_harvest.py"
    spec = importlib.util.spec_from_file_location("embedded_taxonomy_paper_finder_bridge", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_script_module(name: str):
    path = SKILL_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"embedded_taxonomy_paper_finder_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class EmbeddedTaxonomyPaperFinderTests(unittest.TestCase):
    def test_current_skill_name_and_complete_runtime_are_bundled(self):
        self.assertTrue(SKILL_ROOT.is_dir())
        self.assertFalse((SKILLS_ROOT / "taxonomy-pdf-harvest" / "SKILL.md").exists())
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: taxonomy-paper-finder", skill_text)
        for relative_path in (
            "scripts/fetch_candidates.py",
            "scripts/validate_report.py",
            "scripts/export_digest.py",
            "scripts/bridge_to_harvest.py",
            "scripts/oa_pdf_harvester.py",
            "references/schemas/screening-report.schema.json",
        ):
            self.assertTrue((SKILL_ROOT / relative_path).is_file(), relative_path)

    def test_selected_paper_bridge_defaults_to_deep_reads(self):
        bridge = load_bridge_module()
        report = {
            "recommendations": {
                "primary": ["paper-1", "paper-2"],
                "shortlist_order": ["paper-1", "paper-2"],
                "deep_reads": [{"candidate_id": "paper-2"}],
            },
            "inspected_candidates": [
                {
                    "candidate_id": "paper-1",
                    "paper": {"title": "Primary paper", "landing_url": "https://example.org/1"},
                },
                {
                    "candidate_id": "paper-2",
                    "paper": {
                        "title": "Deep-read paper",
                        "landing_url": "https://example.org/2",
                        "doi": "https://doi.org/10.1234/deep-read",
                    },
                },
            ],
        }

        rows = bridge.bridge_report(report)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Deep-read paper")
        self.assertEqual(rows[0]["doi"], "10.1234/deep-read")

    def test_default_runtime_is_outside_vendored_source(self):
        fetch_candidates = load_script_module("fetch_candidates")
        runtime_config = SKILL_ROOT / "config" / "runtime-paths.json"

        paths = fetch_candidates.resolve_runtime_paths(runtime_config)

        expected_root = PROJECT_ROOT / "TaxaMask_outputs" / "taxonomy-paper-finder"
        self.assertEqual(paths["runtime_root"], expected_root)
        self.assertFalse(str(paths["runtime_root"]).startswith(str(SKILL_ROOT)))


if __name__ == "__main__":
    unittest.main()
