import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import ensure_agent_node


class EnsureAgentNodeTest(unittest.TestCase):
    def test_distribution_archive_names_follow_platform(self):
        self.assertEqual(ensure_agent_node.dist_archive_name("Windows", "AMD64"), "node-v22.22.2-win-x64.zip")
        self.assertEqual(ensure_agent_node.dist_archive_name("Linux", "x86_64"), "node-v22.22.2-linux-x64.tar.xz")
        self.assertEqual(ensure_agent_node.dist_archive_name("Darwin", "arm64"), "node-v22.22.2-darwin-arm64.tar.gz")

    def _qualified_source(self):
        for candidate in ensure_agent_node.candidate_nodes():
            if ensure_agent_node.node_is_qualified(candidate):
                return candidate
        self.skipTest("no qualified Node.js is available to copy")

    def test_copies_qualified_node_into_a_new_environment_prefix(self):
        source = self._qualified_source()
        with tempfile.TemporaryDirectory() as temp_dir:
            prefix = Path(temp_dir)
            installed = ensure_agent_node.install_node_from_path(source, prefix)
            self.assertEqual(installed, prefix / "node.exe")
            self.assertTrue(ensure_agent_node.node_is_qualified(installed))
            completed = subprocess.run(
                [str(installed), "-p", "process.version"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertTrue(completed.stdout.strip().startswith("v22."))

    def test_existing_environment_node_is_reused_without_download(self):
        source = self._qualified_source()
        with tempfile.TemporaryDirectory() as temp_dir:
            prefix = Path(temp_dir)
            shutil.copy2(source, prefix / "node.exe")
            installed = ensure_agent_node.ensure_agent_node(prefix, download=False)
            self.assertEqual(installed, prefix / "node.exe")


if __name__ == "__main__":
    unittest.main()
