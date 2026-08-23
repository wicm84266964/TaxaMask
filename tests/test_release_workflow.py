import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
CROSS_PLATFORM_WORKFLOW = ROOT / ".github" / "workflows" / "cross-platform-smoke.yml"
CITATION = ROOT / "CITATION.cff"


def _load_workflow(path):
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), dict):
        raise AssertionError(f"invalid workflow: {path}")
    return payload


def _step_run(workflow, job_id, step_name):
    for step in workflow["jobs"][job_id].get("steps", []):
        if step.get("name") == step_name:
            return str(step.get("run") or "")
    raise AssertionError(f"missing step: {job_id}/{step_name}")


class ReleaseWorkflowTests(unittest.TestCase):
    def test_release_requires_every_expected_ci_check(self):
        release_workflow = _load_workflow(WORKFLOW)
        ci_workflow = _load_workflow(CROSS_PLATFORM_WORKFLOW)
        ci_jobs = ci_workflow["jobs"]
        smoke = ci_jobs["smoke"]
        matrix = smoke["strategy"]["matrix"]
        smoke_names = {
            str(smoke["name"])
            .replace("${{ matrix.os }}", str(os_name))
            .replace("${{ matrix.python-version }}", str(python_version))
            for os_name in matrix["os"]
            for python_version in matrix["python-version"]
        }
        expected_checks = smoke_names | {
            str(ci_jobs["embedded-agent"]["name"]),
            str(ci_jobs["paper-distill-skill"]["name"]),
        }

        gate = _step_run(release_workflow, "release", "Require successful checks on this commit")
        block = re.search(r"required_checks=\(\s*(.*?)\s*\)", gate, flags=re.DOTALL)
        self.assertIsNotNone(block)
        required_checks = set(re.findall(r'^\s*"([^"]+)"\s*$', block.group(1), flags=re.MULTILINE))

        self.assertEqual(required_checks, expected_checks)
        self.assertIn('[[ "$state" != "completed:success" ]]', gate)
        self.assertIn('[[ "$failed" -eq 0 ]] || exit 1', gate)

    def test_release_validates_version_metadata_and_uses_descriptive_title(self):
        workflow = _load_workflow(WORKFLOW)
        citation = yaml.safe_load(CITATION.read_text(encoding="utf-8"))
        version = str(citation["version"])
        release_notes = list((ROOT / "docs" / "releases").glob(f"{version}-*.md"))
        self.assertEqual(len(release_notes), 1)
        release_note_lines = release_notes[0].read_text(encoding="utf-8").splitlines()
        heading = release_note_lines[0]
        self.assertTrue(heading.startswith(f"# TaxaMask v{version}"))
        release_date = str(citation["date-released"])
        release_note_header = "\n".join(release_note_lines[:5])
        self.assertRegex(
            release_note_header,
            rf"(?<!\d){re.escape(release_date)}(?!\d)",
        )

        validation = _step_run(workflow, "release", "Validate release request")
        creation = _step_run(workflow, "release", "Create immutable tag and GitHub release")
        self.assertIn('if [[ "v$citation_version" != "$VERSION" ]]', validation)
        self.assertIn('if [[ "$heading" != "# TaxaMask $VERSION"* ]]', validation)
        self.assertIn('release_title="${heading#\\# }"', creation)
        self.assertIn('--title "$release_title"', creation)


if __name__ == "__main__":
    unittest.main()
