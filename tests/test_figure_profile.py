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
    def test_review_batch_size_is_capped_for_stable_vision_calls(self):
        validator = MultimodalValidator(
            {
                "default_provider": "mock",
                "review_batch_size": 9,
                "review_batch_fallback_size": 6,
            }
        )

        self.assertEqual(validator.review_batch_size, 2)
        self.assertEqual(validator.review_batch_fallback_size, 1)

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

    def test_multimodal_parser_tolerates_extra_text_after_json(self):
        validator = MultimodalValidator({"default_provider": "mock"})
        raw = (
            '[{"candidate_id":"c1","accept":true,"confidence_score":0.91,'
            '"category":"target_taxon_figure","reasoning":"ok","species_candidate":"Formica clara",'
            '"species_confidence":0.8,"detected_views":["head_frontal"],'
            '"has_auxiliary_inset":false,"comparison_figure":false,"multiple_species":false}]'
            '\n说明：以上为结构化复核结果。'
        )

        results = validator._parse_triptych_results(raw, [{"candidate_id": "c1"}], "mimo-v2.5")

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].accept)
        self.assertEqual(results[0].candidate_id, "c1")

    def test_multimodal_parser_selects_results_object_from_multiple_json_values(self):
        validator = MultimodalValidator({"default_provider": "mock"})
        raw = (
            '{"note":"not the result"}\n'
            '{"results":[{"candidate_id":"c2","accept":false,"confidence_score":0.2,'
            '"category":"uncertain","reasoning":"missing views","species_candidate":"",'
            '"species_confidence":0,"detected_views":[],"has_auxiliary_inset":false,'
            '"comparison_figure":false,"multiple_species":false}]}'
        )

        results = validator._parse_triptych_results(raw, [{"candidate_id": "c2"}], "mimo-v2.5")

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].accept)
        self.assertEqual(results[0].candidate_id, "c2")


class PDFExtractorProfileTests(unittest.TestCase):
    def test_review_batches_use_pdf_scope_to_avoid_artifact_overwrite(self):
        sys.modules.setdefault("fitz", types.SimpleNamespace(Rect=object, Document=object, Page=object))
        EnhancedPDFExtractionSystem = importlib.import_module("pdf_processor.pdf_extractor").EnhancedPDFExtractionSystem

        db_path = REPO_ROOT / ".tmp_validation" / "test_figure_batch_scope.db"
        extractor = EnhancedPDFExtractionSystem(
            output_db_path=str(db_path),
            save_images_to_files=False,
            enable_multimodal_validation=False,
        )
        try:
            seen_batch_ids = []

            def fake_review(batch, batch_id):
                seen_batch_ids.append(batch_id)
                return list(batch)

            extractor._review_candidate_batch = fake_review
            candidates = [{"candidate_id": "c1"}, {"candidate_id": "c2"}]

            extractor._review_all_candidates(candidates, "zootaxa.4526.2.3")
            extractor._review_all_candidates(candidates, "zootaxa.4532.3.1")

            self.assertEqual(
                seen_batch_ids,
                [
                    "zootaxa_4526_2_3_batch_0001",
                    "zootaxa_4532_3_1_batch_0001",
                ],
            )
        finally:
            extractor.close()
            if extractor.artifacts_dir.exists():
                for path in sorted(extractor.artifacts_dir.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        path.rmdir()
                extractor.artifacts_dir.rmdir()
            if db_path.exists():
                db_path.unlink()

    def test_failed_real_multimodal_attempt_saves_raw_response_for_audit(self):
        sys.modules.setdefault("fitz", types.SimpleNamespace(Rect=object, Document=object, Page=object))
        EnhancedPDFExtractionSystem = importlib.import_module("pdf_processor.pdf_extractor").EnhancedPDFExtractionSystem

        class FailingValidator:
            review_batch_size = 2
            review_batch_fallback_size = 1
            batch_char_budget = 24000
            last_raw_response = '{"results":[{"candidate_id":"c1"}]} trailing text'

            def review_triptych_batch(self, candidates):
                raise ValueError("Extra data: line 1 column 34 (char 33)")

            def review_triptych_batch_mock(self, candidates, error_context=""):
                return (
                    [
                        FigureReviewResult(
                            candidate_id=str(candidate.get("candidate_id", "")),
                            accept=False,
                            confidence_score=0.0,
                            category="uncertain",
                            reasoning=error_context,
                            model_used="mock",
                            review_mode="mock",
                        )
                        for candidate in candidates
                    ],
                    "mock raw",
                    "mock",
                )

        db_path = REPO_ROOT / ".tmp_validation" / "test_figure_failed_raw.db"
        extractor = EnhancedPDFExtractionSystem(
            output_db_path=str(db_path),
            save_images_to_files=False,
            enable_multimodal_validation=False,
        )
        try:
            extractor.enable_multimodal_validation = True
            extractor.validator = FailingValidator()
            extractor._should_split_failed_batch = lambda candidates, detail: False
            extractor._review_candidate_batch([{"candidate_id": "c1"}], "paper_batch_0001")

            failed_raw = extractor.batch_raw_dir / "paper_batch_0001_attempt_1_failed.txt"
            fallback_raw = extractor.batch_raw_dir / "paper_batch_0001_fallback.txt"
            self.assertTrue(failed_raw.exists())
            self.assertIn("trailing text", failed_raw.read_text(encoding="utf-8"))
            self.assertTrue(fallback_raw.exists())
        finally:
            extractor.close()
            if extractor.artifacts_dir.exists():
                for path in sorted(extractor.artifacts_dir.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        path.rmdir()
                extractor.artifacts_dir.rmdir()
            if db_path.exists():
                db_path.unlink()

    def test_import_ready_export_copies_only_accepted_figures(self):
        sys.modules.setdefault("fitz", types.SimpleNamespace(Rect=object, Document=object, Page=object))
        EnhancedPDFExtractionSystem = importlib.import_module("pdf_processor.pdf_extractor").EnhancedPDFExtractionSystem

        db_path = REPO_ROOT / ".tmp_validation" / "test_figure_import_ready.db"
        extractor = EnhancedPDFExtractionSystem(
            output_db_path=str(db_path),
            save_images_to_files=True,
            enable_multimodal_validation=False,
        )
        try:
            source_dir = db_path.parent / "source_figures"
            source_dir.mkdir(parents=True, exist_ok=True)
            accepted_image = source_dir / "accepted.png"
            rejected_image = source_dir / "rejected.png"
            accepted_image.write_bytes(b"accepted-image")
            rejected_image.write_bytes(b"rejected-image")

            cursor = extractor.db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO pdf_files (file_path, file_name, file_hash, total_pages, file_size)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("C:/papers/paper.pdf", "paper.pdf", "hash", 1, 100),
            )
            pdf_file_id = int(cursor.lastrowid)
            stats = extractor._persist_pdf_results(
                pdf_file_id,
                [
                    {
                        "page_number": 1,
                        "figure_index": 1,
                        "candidate_id": "accepted",
                        "figure_hash": "a",
                        "image_path": str(accepted_image),
                        "image_file_name": accepted_image.name,
                        "accepted": True,
                        "review_status": "accepted",
                        "category": "ant_taxonomic_figure",
                        "final_confidence": 0.95,
                        "multimodal_validated": True,
                        "multimodal_review_mode": "real",
                    },
                    {
                        "page_number": 1,
                        "figure_index": 2,
                        "candidate_id": "rejected",
                        "figure_hash": "r",
                        "image_path": str(rejected_image),
                        "image_file_name": rejected_image.name,
                        "accepted": False,
                        "review_status": "rejected",
                        "category": "non_taxonomic_or_other",
                        "final_confidence": 0.2,
                        "multimodal_validated": True,
                        "multimodal_review_mode": "real",
                    },
                ],
            )
            stats.update(extractor._sync_import_ready_figure_exports(pdf_file_id))

            accepted_exports = list(extractor.accepted_figures_dir.glob("paper__accepted_*.png"))
            review_exports = list(extractor.review_figures_dir.glob("paper__review_*.png"))
            self.assertEqual(stats["accepted_exported_figures"], 1)
            self.assertEqual(stats["review_exported_figures"], 0)
            self.assertEqual(len(accepted_exports), 1)
            self.assertEqual(accepted_exports[0].read_bytes(), b"accepted-image")
            self.assertEqual(review_exports, [])
            manifest = extractor.stats_dir / "paper_import_ready_figures.csv"
            self.assertTrue(manifest.exists())
            manifest_text = manifest.read_text(encoding="utf-8-sig")
            self.assertIn("accepted.png", manifest_text)
            self.assertNotIn("rejected.png", manifest_text)
        finally:
            extractor.close()
            for folder in [
                extractor.artifacts_dir,
                db_path.parent / "source_figures",
            ]:
                if folder.exists():
                    for path in sorted(folder.rglob("*"), reverse=True):
                        if path.is_file():
                            path.unlink()
                        elif path.is_dir():
                            path.rmdir()
                    folder.rmdir()
            if db_path.exists():
                db_path.unlink()

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
