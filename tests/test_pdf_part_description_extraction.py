import sqlite3
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

sys.modules.setdefault("fitz", types.SimpleNamespace(Rect=object, Document=object, Page=object))

from core.pdf_processor.part_description_extractor import TextPartDescriptionExtractor  # noqa: E402
from core.pdf_processor.pdf_extractor import EnhancedPDFExtractionSystem  # noqa: E402


class PdfPartDescriptionExtractionTests(unittest.TestCase):
    def test_mock_text_part_extractor_preserves_file_and_block_provenance(self):
        extractor = TextPartDescriptionExtractor({"default_provider": "mock"})
        blocks = [
            {
                "page_number": 3,
                "block_index": 7,
                "text_content": "Formica clara. Diagnosis. Head subquadrate; mandible with five teeth; mesosoma weakly convex.",
                "section_hint": "diagnosis",
                "text_type": "taxonomic",
                "species_mentions": ["Formica clara"],
            }
        ]

        result = extractor.extract(
            pdf_file_id=12,
            file_name="paper.pdf",
            file_path="C:/papers/paper.pdf",
            file_hash="abc123",
            document_blocks=blocks,
        )

        self.assertEqual(result.status, "mock")
        self.assertGreaterEqual(len(result.records), 2)
        head = next(item for item in result.records if item["part_key"] == "head")
        self.assertEqual(head["source_block_refs"], ["p003_b0007"])
        self.assertEqual(head["source_pages"], [3])
        self.assertEqual(head["source_blocks"][0]["file_name"], "paper.pdf")
        self.assertEqual(head["source_blocks"][0]["file_hash"], "abc123")

    def test_text_part_parser_tolerates_extra_text_after_json(self):
        extractor = TextPartDescriptionExtractor({"default_provider": "mock"})
        raw = (
            '{"taxon_part_descriptions":[],"text_block_labels":[{"block_ref":"p001_b0001",'
            '"role":"diagnosis","taxon_name":"Formica clara","confidence":0.8}]}'
            '\n补充说明：已按要求输出。'
        )

        payload = extractor._parse_json_payload(raw)

        self.assertEqual(payload["text_block_labels"][0]["block_ref"], "p001_b0001")

    def test_text_part_parser_uses_first_json_object_when_model_repeats(self):
        extractor = TextPartDescriptionExtractor({"default_provider": "mock"})
        raw = (
            '{"taxon_part_descriptions":[],"text_block_labels":[]}'
            '{"taxon_part_descriptions":[{"taxon_name":"wrong"}],"text_block_labels":[]}'
        )

        payload = extractor._parse_json_payload(raw)

        self.assertEqual(payload["taxon_part_descriptions"], [])

    def test_pdf_extractor_persists_taxon_part_descriptions_and_text_blocks(self):
        db_path = REPO_ROOT / ".tmp_validation" / "test_pdf_part_descriptions.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.exists():
            db_path.unlink()

        extractor = EnhancedPDFExtractionSystem(
            output_db_path=str(db_path),
            save_images_to_files=False,
            enable_multimodal_validation=False,
            text_part_config={"default_provider": "mock"},
        )
        try:
            cursor = extractor.db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO pdf_files (file_path, file_name, file_hash, total_pages, file_size)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("C:/papers/paper.pdf", "paper.pdf", "abc123", 5, 1000),
            )
            pdf_file_id = int(cursor.lastrowid)
            result = extractor._extract_text_part_descriptions(
                pdf_file_id=pdf_file_id,
                file_name="paper.pdf",
                file_path="C:/papers/paper.pdf",
                file_hash="abc123",
                document_blocks=[
                    {
                        "page_number": 2,
                        "block_index": 4,
                        "text_content": "Formica clara. Description. Head longer than broad; petiole node high.",
                        "section_hint": "description",
                        "text_type": "taxonomic",
                        "species_mentions": ["Formica clara"],
                    }
                ],
            )
            stats = extractor._persist_pdf_results(pdf_file_id, [], result)
            extractor.db_conn.commit()

            self.assertGreaterEqual(stats["part_description_records"], 2)
            conn = sqlite3.connect(str(db_path))
            try:
                db_cursor = conn.cursor()
                db_cursor.execute(
                    """
                    SELECT file_name, file_hash, taxon_name, part_key, source_block_refs, source_pages
                    FROM taxon_part_descriptions
                    WHERE part_key = 'head'
                    """
                )
                row = db_cursor.fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "paper.pdf")
                self.assertEqual(row[1], "abc123")
                self.assertEqual(row[2], "Formica clara")
                self.assertEqual(row[3], "head")
                self.assertEqual(row[4], '["p002_b0004"]')
                self.assertEqual(row[5], "[2]")

                db_cursor.execute(
                    """
                    SELECT file_name, block_ref, page_number, llm_role, llm_taxon_name
                    FROM pdf_text_blocks
                    WHERE block_ref = 'p002_b0004'
                    """
                )
                block_row = db_cursor.fetchone()
                self.assertEqual(block_row, ("paper.pdf", "p002_b0004", 2, "morphological_description", "Formica clara"))
            finally:
                conn.close()
        finally:
            extractor.close()
            if db_path.exists():
                db_path.unlink()

    def test_missing_text_llm_config_still_persists_unprocessed_blocks(self):
        db_path = REPO_ROOT / ".tmp_validation" / "test_pdf_part_descriptions_skipped.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.exists():
            db_path.unlink()

        extractor = EnhancedPDFExtractionSystem(
            output_db_path=str(db_path),
            save_images_to_files=False,
            enable_multimodal_validation=False,
        )
        try:
            cursor = extractor.db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO pdf_files (file_path, file_name, file_hash, total_pages, file_size)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("C:/papers/plain.pdf", "plain.pdf", "hash456", 1, 100),
            )
            pdf_file_id = int(cursor.lastrowid)
            result = extractor._extract_text_part_descriptions(
                pdf_file_id=pdf_file_id,
                file_name="plain.pdf",
                file_path="C:/papers/plain.pdf",
                file_hash="hash456",
                document_blocks=[
                    {
                        "page_number": 1,
                        "block_index": 0,
                        "text_content": "Some PDF text.",
                        "section_hint": "other",
                        "text_type": "other",
                        "species_mentions": [],
                    }
                ],
            )
            stats = extractor._persist_pdf_results(pdf_file_id, [], result)
            extractor.db_conn.commit()

            self.assertEqual(stats["part_extraction_status"], "skipped")
            self.assertEqual(stats["part_text_blocks"], 1)
            conn = sqlite3.connect(str(db_path))
            try:
                db_cursor = conn.cursor()
                db_cursor.execute(
                    """
                    SELECT file_name, file_hash, block_ref, llm_role, model_used
                    FROM pdf_text_blocks
                    WHERE block_ref = 'p001_b0000'
                    """
                )
                self.assertEqual(
                    db_cursor.fetchone(),
                    ("plain.pdf", "hash456", "p001_b0000", "unprocessed", "missing_text_llm_config"),
                )
                db_cursor.execute("SELECT profile_name FROM part_extraction_runs")
                self.assertEqual(db_cursor.fetchone()[0], "内置蚂蚁分类学部位描述抽取")
            finally:
                conn.close()
        finally:
            extractor.close()
            if db_path.exists():
                db_path.unlink()

    def test_extract_from_pdf_skips_completed_same_hash_when_resume_enabled(self):
        db_path = REPO_ROOT / ".tmp_validation" / "test_pdf_extract_resume.db"
        pdf_path = REPO_ROOT / ".tmp_validation" / "resume_source.pdf"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.exists():
            db_path.unlink()
        pdf_path.write_bytes(b"%PDF-1.4\nresume test\n%%EOF\n")

        extractor = EnhancedPDFExtractionSystem(
            output_db_path=str(db_path),
            save_images_to_files=False,
            enable_multimodal_validation=False,
            resume_completed_pdfs=True,
        )
        try:
            file_hash = extractor._calculate_file_hash(pdf_path)
            cursor = extractor.db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO pdf_files (file_path, file_name, file_hash, total_pages, file_size)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(pdf_path), pdf_path.name, file_hash, 1, pdf_path.stat().st_size),
            )
            pdf_file_id = int(cursor.lastrowid)
            cursor.execute(
                """
                INSERT INTO part_extraction_runs
                    (pdf_file_id, file_name, file_path, file_hash, status, reason, extracted_records, labeled_blocks)
                VALUES (?, ?, ?, ?, 'real', '', 1, 3)
                """,
                (pdf_file_id, pdf_path.name, str(pdf_path), file_hash),
            )
            cursor.execute(
                """
                INSERT INTO extraction_stats
                    (pdf_file_id, total_candidates, accepted_figures, rejected_figures, review_queue_figures, multimodal_validated_figures)
                VALUES (?, 0, 0, 0, 0, 0)
                """,
                (pdf_file_id,),
            )
            extractor.db_conn.commit()

            fitz_open = Mock()
            with patch.object(sys.modules["core.pdf_processor.pdf_extractor"].fitz, "open", fitz_open, create=True):
                result = extractor.extract_from_pdf(str(pdf_path))

            fitz_open.assert_not_called()
            self.assertEqual(result["status"], "skipped_existing")
            self.assertTrue(result["stats"]["resumed_skip"])
            self.assertEqual(result["file_id"], pdf_file_id)
        finally:
            extractor.close()
            if db_path.exists():
                db_path.unlink()
            if pdf_path.exists():
                pdf_path.unlink()

    def test_extract_from_pdf_reruns_incomplete_existing_record(self):
        db_path = REPO_ROOT / ".tmp_validation" / "test_pdf_extract_resume_incomplete.db"
        pdf_path = REPO_ROOT / ".tmp_validation" / "resume_incomplete.pdf"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.exists():
            db_path.unlink()
        pdf_path.write_bytes(b"%PDF-1.4\nresume incomplete\n%%EOF\n")

        extractor = EnhancedPDFExtractionSystem(
            output_db_path=str(db_path),
            save_images_to_files=False,
            enable_multimodal_validation=False,
            resume_completed_pdfs=True,
        )
        try:
            file_hash = extractor._calculate_file_hash(pdf_path)
            cursor = extractor.db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO pdf_files (file_path, file_name, file_hash, total_pages, file_size)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(pdf_path), pdf_path.name, file_hash, 1, pdf_path.stat().st_size),
            )
            pdf_file_id = int(cursor.lastrowid)
            cursor.execute(
                """
                INSERT INTO extraction_stats
                    (pdf_file_id, total_candidates, accepted_figures, rejected_figures, review_queue_figures, multimodal_validated_figures)
                VALUES (?, 0, 0, 0, 0, 0)
                """,
                (pdf_file_id,),
            )
            extractor.db_conn.commit()

            self.assertIsNone(extractor._resume_existing_pdf_result(str(pdf_path), file_hash))
        finally:
            extractor.close()
            if db_path.exists():
                db_path.unlink()
            if pdf_path.exists():
                pdf_path.unlink()


if __name__ == "__main__":
    unittest.main()
