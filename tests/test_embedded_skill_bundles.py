from __future__ import annotations

import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "skills" / "EMBEDDED_SKILLS.json"
PAPER_ROOT = PROJECT_ROOT / "skills" / "paper_distill_skill_bundle_v6_zh"
UNSLOTH_ROOT = PROJECT_ROOT / "skills" / "unsloth-studio-finetune-portable"


def walk_strings(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_strings(child)
    elif isinstance(value, str):
        yield value


class EmbeddedSkillBundleTests(unittest.TestCase):
    def test_manifest_records_sources_licenses_and_tests(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        components = {item["name"]: item for item in manifest["components"]}
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(
            set(components),
            {
                "ant-code-generic-skills",
                "taxamask-pdf-evidence",
                "taxonomy-paper-finder",
                "paper-distill",
                "unsloth-studio-finetune",
            },
        )
        for component in components.values():
            self.assertTrue(component["default_enabled"])
            self.assertTrue(component["sync_policy"])
            self.assertTrue(component["test_command"])
            self.assertTrue((PROJECT_ROOT / component["license_file"]).is_file())

    def test_paper_distill_uses_distinct_taxamask_version_and_attribution(self):
        metadata_text = (PAPER_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        skill_text = (PAPER_ROOT / "skills" / "paper_distill" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('version = "0.2.0+taxamask.zh1"', metadata_text)
        self.assertIn('authors = [{ name = "Paper Distill contributors" }]', metadata_text)
        self.assertIn("version: 0.2.0-taxamask.zh1", skill_text)
        self.assertNotIn('authors = [{ name = "OpenAI" }]', metadata_text)

    def test_unsloth_templates_and_openapi_are_sanitized(self):
        full = json.loads((UNSLOTH_ROOT / "templates" / "qwen35_dual_gpu_windows_api.template.json").read_text(encoding="utf-8"))
        smoke = json.loads((UNSLOTH_ROOT / "templates" / "qwen35_dual_gpu_windows_api.smoke.template.json").read_text(encoding="utf-8"))
        openapi = json.loads((UNSLOTH_ROOT / "references" / "unsloth-openapi.json").read_text(encoding="utf-8"))
        self.assertEqual(full["gpu_ids"], [0, 1])
        self.assertFalse(full["load_in_4bit"])
        self.assertEqual(smoke["max_steps"], 1)
        self.assertIn("/api/train/start", openapi["paths"])
        for value in walk_strings(openapi):
            lowered = value.lower().replace("/", "\\")
            self.assertNotIn("c:\\users\\", lowered)
            self.assertNotIn("lbj-workspace", lowered)
            self.assertNotIn("saveproject", lowered)


if __name__ == "__main__":
    unittest.main()
