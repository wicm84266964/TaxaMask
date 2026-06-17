from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


class PaperDistillPackagingTests(unittest.TestCase):
    def test_pyproject_exposes_paper_distill_console_script(self) -> None:
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

        scripts = pyproject_data["project"]["scripts"]
        self.assertEqual(scripts["paper-distill"], "app.paper_distill.cli:main")

        package_find_include = pyproject_data["tool"]["setuptools"]["packages"]["find"]["include"]
        package_data = pyproject_data["tool"]["setuptools"]["package-data"]
        self.assertIn("skills*", package_find_include)
        self.assertEqual(package_data["skills.paper_distill"], ["SKILL.md"])

    def test_env_example_documents_paper_distill_environment_variables(self) -> None:
        env_example_path = Path(__file__).resolve().parents[1] / ".env.example"
        env_example = env_example_path.read_text(encoding="utf-8")

        self.assertIn("PAPER_DISTILL_BACKEND", env_example)
        self.assertIn("PAPER_DISTILL_MODEL", env_example)
        self.assertIn("PAPER_DISTILL_BASE_URL", env_example)
        self.assertIn("PAPER_DISTILL_API_KEY", env_example)

    def test_skill_bundle_exists_with_stable_contract_markers(self) -> None:
        skill_path = Path(__file__).resolve().parents[1] / "skills" / "paper_distill" / "SKILL.md"
        skill_content = skill_path.read_text(encoding="utf-8")

        self.assertTrue(skill_path.exists())
        self.assertTrue(skill_content.startswith("---\n"))
        self.assertIn("name: paper-distill", skill_content)
        self.assertIn("paper-distill run", skill_content)
        self.assertIn("paper-distill export", skill_content)
        self.assertIn("data/paper_distill/papers", skill_content)
        self.assertIn("qa_entries.jsonl", skill_content)
        self.assertIn("checkpoint.json", skill_content)

    def test_readme_references_skill_bundle(self) -> None:
        readme_path = Path(__file__).resolve().parents[1] / "README.md"
        readme_content = readme_path.read_text(encoding="utf-8")

        self.assertIn("skills/paper_distill/SKILL.md", readme_content)

    def test_skill_bundle_is_packaged_as_python_package_data(self) -> None:
        package_root = Path(__file__).resolve().parents[1] / "skills"
        skill_package_root = package_root / "paper_distill"

        self.assertTrue((package_root / "__init__.py").exists())
        self.assertTrue((skill_package_root / "__init__.py").exists())
        self.assertTrue((skill_package_root / "SKILL.md").exists())


if __name__ == "__main__":
    _ = unittest.main()
