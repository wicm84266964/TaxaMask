import json
import sys
import types
import unittest
from pathlib import Path
import importlib

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PROFILE_DIR = REPO_ROOT / "multimodal_configs"
PDF_PROCESSOR_DIR = REPO_ROOT / "core" / "pdf_processor"
PDF_PROCESSOR_PACKAGE_DIR = REPO_ROOT / "core"
if str(PDF_PROCESSOR_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PDF_PROCESSOR_PACKAGE_DIR))

figure_profile_module = importlib.import_module("pdf_processor.figure_profile")
validator_module = importlib.import_module("pdf_processor.multimodal_validator")
load_figure_profile = figure_profile_module.load_figure_profile
normalize_figure_profile = figure_profile_module.normalize_figure_profile
profile_display_name = figure_profile_module.profile_display_name
MultimodalValidator = validator_module.MultimodalValidator
FigureReviewResult = validator_module.FigureReviewResult


class FigureProfileTests(unittest.TestCase):
    def test_example_profiles_load_and_keep_expected_scope(self):
        ant = load_figure_profile(PROFILE_DIR / "蚂蚁分类学图版宽松复核_示例.json")
        generic = load_figure_profile(PROFILE_DIR / "通用分类学图版提取复核_模板.json")
        plant = load_figure_profile(PROFILE_DIR / "植物分类学图版提取复核_模板.json")

        self.assertEqual(profile_display_name(ant), "蚂蚁分类学图版宽松复核_示例")
        self.assertEqual(ant["review_rules"]["view_schema"]["acceptance_mode"], "model_accept_with_parts_recorded")
        self.assertIn("mandible", ant["review_rules"]["view_schema"]["required_or_expected_views"])
        self.assertNotIn("head_frontal", ant["review_rules"]["view_schema"]["required_or_expected_views"])
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

    def test_ant_mock_review_allows_same_taxon_castes_but_rejects_multi_species(self):
        ant = load_figure_profile(PROFILE_DIR / "蚂蚁分类学图版宽松复核_示例.json")
        validator = MultimodalValidator({"default_provider": "mock", "figure_profile": ant})

        results, _raw, protocol = validator.review_triptych_batch_mock(
            [
                {
                    "candidate_id": "same_taxon_castes",
                    "caption_text": "Figure 1. Formica clara queen and male mandible antenna diagnosis description.",
                    "figure_local_text": "mandible antenna head",
                    "species_core_text": "Diagnosis Formica clara worker queen male morphology.",
                    "species_extended_text": "",
                },
                {
                    "candidate_id": "multi_species",
                    "caption_text": "Figure 2. Formica clara and Lasius niger comparison of mandible diagnosis.",
                    "figure_local_text": "mandible head comparison",
                    "species_core_text": "",
                    "species_extended_text": "",
                },
            ]
        )

        self.assertEqual(protocol, "mock")
        by_id = {result.candidate_id: result for result in results}
        self.assertTrue(by_id["same_taxon_castes"].accept)
        self.assertFalse(by_id["same_taxon_castes"].comparison_figure)
        self.assertFalse(by_id["multi_species"].accept)
        self.assertTrue(by_id["multi_species"].comparison_figure)


class PDFExtractorProfileTests(unittest.TestCase):
    def test_extractor_acceptance_mode_follows_profile(self):
        sys.modules.setdefault("fitz", types.SimpleNamespace(Rect=object, Document=object, Page=object))
        EnhancedPDFExtractionSystem = importlib.import_module("pdf_processor.pdf_extractor").EnhancedPDFExtractionSystem

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

    def test_extractor_blocks_conflicting_comparison_category(self):
        sys.modules.setdefault("fitz", types.SimpleNamespace(Rect=object, Document=object, Page=object))
        EnhancedPDFExtractionSystem = importlib.import_module("pdf_processor.pdf_extractor").EnhancedPDFExtractionSystem

        ant = load_figure_profile(PROFILE_DIR / "蚂蚁分类学图版宽松复核_示例.json")
        extractor = EnhancedPDFExtractionSystem(
            output_db_path=str(REPO_ROOT / ".tmp_validation" / "test_figure_profile_conflict.db"),
            save_images_to_files=False,
            enable_multimodal_validation=False,
            figure_profile=ant,
        )
        try:
            reviewed = extractor._apply_review_results(
                [{"candidate_id": "c1", "species_confidence": 0.0}],
                [
                    FigureReviewResult(
                        candidate_id="c1",
                        accept=True,
                        confidence_score=0.99,
                        category="comparison_or_multi_species",
                        reasoning="model returned inconsistent accept/category",
                        species_candidate="Formica clara",
                        species_confidence=0.9,
                        detected_views=["mandible"],
                        comparison_figure=False,
                        multiple_species=False,
                        model_used="test_model",
                        review_mode="real",
                    )
                ],
                "test_protocol",
            )

            self.assertFalse(reviewed[0]["accepted"])
            self.assertEqual(reviewed[0]["review_status"], "rejected")
            self.assertEqual(reviewed[0]["rejection_reason"], "comparison_or_multi_species")
        finally:
            extractor.close()
            db_path = REPO_ROOT / ".tmp_validation" / "test_figure_profile_conflict.db"
            if db_path.exists():
                db_path.unlink()


if __name__ == "__main__":
    unittest.main()
