import unittest

from AntSleap.ui.material_intake_registry import (
    register_material_intake_page,
    resolve_material_intake_page,
    workbench_import_allowed,
)


class MaterialIntakeRegistryTest(unittest.TestCase):
    def test_existing_pdf_pages_remain_connected_to_the_workbench(self):
        screening = resolve_material_intake_page("literature_screening", {"has_source_folder": True})
        extraction = resolve_material_intake_page("data_extraction", {})
        self.assertEqual(screening["source_workbench"], "pdf_evidence")
        self.assertEqual(screening["settings_focus"], "stage_2_screening_criteria_and_run_diagnosis")
        self.assertTrue(screening["connected_to_workbench"])
        self.assertTrue(screening["include_pdf_fields"])
        self.assertEqual(extraction["source_workbench"], "pdf_evidence")
        self.assertEqual(extraction["settings_focus"], "stage_3_figure_extraction_review_and_import_ready_export")
        self.assertTrue(workbench_import_allowed("data_extraction"))

    def test_unregistered_page_does_not_reuse_pdf_evidence(self):
        page = resolve_material_intake_page("future_volume_intake", {})
        self.assertEqual(page["source_workbench"], "material_intake")
        self.assertEqual(page["project_type"], "material_intake")
        self.assertFalse(page["connected_to_workbench"])
        self.assertFalse(page["include_pdf_fields"])
        self.assertFalse(workbench_import_allowed("future_volume_intake"))
        self.assertNotIn("pdf_evidence", page["source_workbench"])

    def test_a_new_module_can_register_its_own_page(self):
        register_material_intake_page({
            "page_id": "test_only_mesh_intake",
            "source_workbench": "mesh_intake",
            "project_type": "mesh_intake",
            "connected_to_workbench": False,
            "include_pdf_fields": False,
            "pathway_label_key": "Mesh intake",
            "resolve_stage": lambda _facts: {
                "settings_focus": "mesh_intake_confirm_files",
                "acquisition_stage": "mesh_intake_waiting_for_files",
                "page_instruction": "Confirm the mesh files only.",
            },
        })
        page = resolve_material_intake_page("test_only_mesh_intake", {})
        self.assertEqual(page["source_workbench"], "mesh_intake")
        self.assertEqual(page["settings_focus"], "mesh_intake_confirm_files")
        self.assertFalse(page["include_pdf_fields"])


if __name__ == "__main__":
    unittest.main()
