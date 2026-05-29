import json
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

sys.modules.setdefault("fitz", types.SimpleNamespace(Rect=object, Document=object, Page=object))

from core.pdf_processor.part_description_extractor import TextPartDescriptionExtractor  # noqa: E402
from core.pdf_processor.part_description_profile import (  # noqa: E402
    load_part_description_profile,
    normalize_part_description_profile,
    profile_display_name,
)
from core.pdf_processor.pdf_extractor import EnhancedPDFExtractionSystem  # noqa: E402


PROFILE_DIR = REPO_ROOT / "part_description_configs"


class PartDescriptionProfileTests(unittest.TestCase):
    def test_example_profiles_load(self):
        ant = load_part_description_profile(PROFILE_DIR / "蚂蚁分类学部位描述抽取_示例.json")
        generic = load_part_description_profile(PROFILE_DIR / "通用分类学部位描述抽取_模板.json")
        plant = load_part_description_profile(PROFILE_DIR / "植物分类学部位描述抽取_模板.json")

        self.assertEqual(profile_display_name(ant), "蚂蚁分类学部位描述抽取_示例")
        self.assertIn("mandible", {item["key"] for item in ant["part_schema"]})
        self.assertIn("overall_morphology", {item["key"] for item in generic["part_schema"]})
        self.assertIn("leaf", {item["key"] for item in plant["part_schema"]})
        self.assertEqual(ant["extraction_settings"]["max_input_chars"], 600000)

    def test_normalized_profile_is_json_serializable(self):
        profile = normalize_part_description_profile({"profile_name": "Minimal Part Profile"})
        dumped = json.dumps(profile, ensure_ascii=False)
        self.assertIn("Minimal Part Profile", dumped)
        self.assertTrue(profile["part_schema"])

    def test_text_extractor_uses_custom_part_schema(self):
        profile = normalize_part_description_profile(
            {
                "profile_name": "Wing Profile",
                "target_taxon": {"display_name": "test insects", "scientific_scope": "Insecta"},
                "part_schema": [
                    {"key": "wing", "label": "翅", "aliases": ["wing", "wings"]},
                    {"key": "other_diagnostic_structure", "label": "其他", "aliases": ["diagnostic"]},
                ],
            }
        )
        extractor = TextPartDescriptionExtractor({"default_provider": "mock"}, part_profile=profile)
        result = extractor.extract(
            pdf_file_id=1,
            file_name="insect.pdf",
            file_path="C:/papers/insect.pdf",
            file_hash="hash",
            document_blocks=[
                {
                    "page_number": 1,
                    "block_index": 2,
                    "text_content": "Aus testus. Description. Wing broad and hyaline; diagnostic margin dark.",
                    "section_hint": "description",
                    "text_type": "taxonomic",
                    "species_mentions": ["Aus testus"],
                }
            ],
        )

        self.assertEqual(result.profile_name, "Wing Profile")
        self.assertIn("wing", {record["part_key"] for record in result.records})

    def test_pdf_extractor_persists_part_profile_metadata(self):
        db_path = REPO_ROOT / ".tmp_validation" / "test_part_profile_metadata.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.exists():
            db_path.unlink()

        profile = load_part_description_profile(PROFILE_DIR / "蚂蚁分类学部位描述抽取_示例.json")
        extractor = EnhancedPDFExtractionSystem(
            output_db_path=str(db_path),
            save_images_to_files=False,
            enable_multimodal_validation=False,
            text_part_config={"default_provider": "mock"},
            part_description_profile=profile,
        )
        try:
            cursor = extractor.db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO pdf_files (file_path, file_name, file_hash, total_pages, file_size)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("C:/papers/paper.pdf", "paper.pdf", "abc123", 1, 100),
            )
            pdf_file_id = int(cursor.lastrowid)
            result = extractor._extract_text_part_descriptions(
                pdf_file_id=pdf_file_id,
                file_name="paper.pdf",
                file_path="C:/papers/paper.pdf",
                file_hash="abc123",
                document_blocks=[
                    {
                        "page_number": 1,
                        "block_index": 0,
                        "text_content": "Formica clara. Description. Head longer than broad.",
                        "section_hint": "description",
                        "text_type": "taxonomic",
                        "species_mentions": ["Formica clara"],
                    }
                ],
            )
            extractor._persist_pdf_results(pdf_file_id, [], result)
            extractor.db_conn.commit()

            cursor.execute("SELECT profile_name, profile_schema_version FROM part_extraction_runs")
            row = cursor.fetchone()
            self.assertEqual(row[0], "蚂蚁分类学部位描述抽取_示例")
            self.assertEqual(row[1], "taxamask-part-description-profile-v1")
        finally:
            extractor.close()
            if db_path.exists():
                db_path.unlink()


if __name__ == "__main__":
    unittest.main()
