import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ApiRuntimeSettingsSchemaTests(unittest.TestCase):
    def test_example_settings_have_separate_text_and_multimodal_roles(self):
        path = REPO_ROOT / "screener_configs" / "api_runtime_settings.example.json"
        payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], "taxamask-api-runtime-settings-v2")
        self.assertIn("text_llm", payload)
        self.assertIn("multimodal_llm", payload)
        self.assertIn("model", payload["text_llm"])
        self.assertIn("image_detail", payload["multimodal_llm"])
        self.assertFalse(payload["text_llm"]["api_key"])
        self.assertFalse(payload["multimodal_llm"]["api_key"])


if __name__ == "__main__":
    unittest.main()

