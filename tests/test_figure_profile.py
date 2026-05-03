import json
import sys
import types
import unittest
from pathlib import Path

from core.pdf_processor.figure_profile import load_figure_profile, normalize_figure_profile, profile_display_name
from core.pdf_processor.multimodal_validator import MultimodalValidator


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = REPO_ROOT / "multimodal_configs"


class FigureProfileTests(unittest.TestCase):
    def test_example_profiles_load_and_keep_expected_scope(self):
        ant = load_figure_profile(PROFILE_DIR / "蚂蚁三视图提取复核_示例.json")
        generic = load_figure_profile(PROFILE_DIR / "通用分类学图版提取复核_模板.json")
        plant = load_figure_profile(PROFILE_DIR / "植物分类学图版提取复核_模板.json")

        self.assertEqual(profile_display_name(ant), "蚂蚁三视图提取复核_示例")
        self.assertEqual(
            set(ant["review_rules"]["view_schema"]["required_or_expected_views"]),
            {"lateral", "dorsal", "head_frontal"},
        )
        self.assertNotIn("lateral", generic["review_rules"]["view_schema"]["view_terms"])
        self.assertNotIn("formicidae", plant["taxonomy_terms"])
        self.assertEqual(plant["review_rules"]["view_schema"]["acceptance_mode"], "model_accept_with_parts_recorded")

    def test_normalized_profile_is_json_serializable(self):
        profile = normalize_figure_profile({"profile_name": "Minimal Test Profile"})
        dumped = json.dumps(profile, ensure_ascii=False)
        self.assertIn("Minimal Test Profile", dumped)
        self.assertIsInstance(profile["extraction_rules"]["core_section_hints"], list)


class MultimodalValidatorProfileTests(unittest.TestCase):
    def test_schema_uses_profile_defined_detected_parts(self):
        plant = load_figure_profile(PROFILE_DIR / "植物分类学图版提取复核_模板.json")
        validator = MultimodalValidator({"default_provider": "mock", "figure_profile": plant})

        schema = validator._build_triptych_json_schema()
        detected_items = schema["properties"]["results"]["items"]["properties"]["detected_views"]["items"]

        self.assertEqual(
            set(detected_items["enum"]),
            {"habit", "leaf", "flower", "fruit_or_seed", "diagnostic_detail"},
        )

    def test_mock_review_uses_profile_terms(self):
        plant = load_figure_profile(PROFILE_DIR / "植物分类学图版提取复核_模板.json")
        validator = MultimodalValidator({"default_provider": "mock", "figure_profile": plant})

        results, _raw, protocol = validator.review_triptych_batch_mock(
            [
                {
                    "candidate_id": "c1",
                    "caption_text": "Figure 1. Rosa alba flower leaf fruit diagnosis description type specimen.",
                    "figure_local_text": "flower leaf fruit",
                    "species_core_text": "Diagnosis Rosa alba new species.",
                    "species_extended_text": "",
                }
            ]
        )

        self.assertEqual(protocol, "mock")
        self.assertEqual(results[0].category, "plant_taxonomic_plate")
        self.assertEqual(set(results[0].detected_views), {"leaf", "flower", "fruit_or_seed"})
        self.assertEqual(results[0].species_candidate, "Rosa alba")


class PDFExtractorProfileTests(unittest.TestCase):
    def test_extractor_acceptance_mode_follows_profile(self):
        sys.modules.setdefault("fitz", types.SimpleNamespace(Rect=object, Document=object, Page=object))
        from core.pdf_processor.pdf_extractor import EnhancedPDFExtractionSystem

        plant = load_figure_profile(PROFILE_DIR / "植物分类学图版提取复核_模板.json")
        extractor = EnhancedPDFExtractionSystem(
            output_db_path=str(REPO_ROOT / ".tmp_validation" / "test_figure_profile.db"),
            save_images_to_files=False,
            enable_multimodal_validation=False,
            figure_profile=plant,
        )
        try:
            self.assertEqual(extractor.figure_profile_name, "植物分类学图版提取复核_模板")
            self.assertEqual(extractor.figure_acceptance_mode, "model_accept_with_parts_recorded")
            self.assertTrue(extractor._has_required_profile_parts([]))
            self.assertIn("plantae", extractor.taxonomic_keywords)
            self.assertNotIn("formicidae", extractor.taxonomic_keywords)
        finally:
            extractor.close()
            db_path = REPO_ROOT / ".tmp_validation" / "test_figure_profile.db"
            if db_path.exists():
                db_path.unlink()


if __name__ == "__main__":
    unittest.main()

