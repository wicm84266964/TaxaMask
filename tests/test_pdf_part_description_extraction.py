import sqlite3
import sys
import types
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
