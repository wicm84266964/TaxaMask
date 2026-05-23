import unittest

from AntSleap.core.agent_context_routes import enrich_agent_context


class AgentContextRoutesTests(unittest.TestCase):
    def test_general_settings_route_adds_short_navigation_hints(self):
        context = enrich_agent_context(
            {
                "source_workbench": "general_settings",
                "project_type": "settings",
                "runtime_device": "cpu",
                "validation_errors": "none",
            }
        )

        self.assertEqual(context["diagnostic_route"], "general_settings_runtime")
        self.assertIn("LLM_CONTEXT_DETAILED.md", context["llm_context_refs"])
        self.assertIn("GeneralSettingsDialog.get_agent_context", context["source_code_refs"])
        self.assertIn("validation_errors=none", context["health_check_summary"])
        self.assertEqual(context["agent_route_source"], "AntSleap/core/agent_context_routes.py")

    def test_contract_missing_updates_diagnostic_route_without_raw_commands(self):
        context = enrich_agent_context(
            {
                "source_workbench": "stl_model_settings",
                "project_type": "settings",
                "prepare_command_present": "yes",
                "prepare_command_has_contract": "yes",
                "train_command_present": "yes",
                "train_command_has_contract": "no",
                "validation_errors": "train command must include contract",
            }
        )

        self.assertIn("contract_placeholder_missing", context["diagnostic_route"])
        self.assertIn("{contract}", context["diagnostic_focus"])
        self.assertIn("contract_placeholder=missing", context["health_check_summary"])
        self.assertIn("external_backend_contract_v1.md", context["source_code_refs"])
        self.assertNotIn("train.py", str(context))

    def test_tif_route_keeps_manual_truth_safety_visible(self):
        context = enrich_agent_context(
            {
                "source_workbench": "tif_model_settings",
                "project_type": "settings",
                "prepare_command_present": "no",
                "train_command_present": "no",
                "predict_command_present": "yes",
                "predict_command_has_contract": "yes",
                "validation_errors": "none",
            }
        )

        self.assertEqual(context["diagnostic_route"], "tif_volume_backend_settings")
        self.assertIn("model_draft", context["diagnostic_focus"])
        self.assertIn("manual_truth", context["safety_notes"])
        self.assertIn("contract_placeholder=ok_or_not_applicable", context["health_check_summary"])

    def test_unknown_route_passes_through(self):
        original = {"source_workbench": "unknown", "project_type": "settings"}
        self.assertEqual(enrich_agent_context(original), original)


if __name__ == "__main__":
    unittest.main()
