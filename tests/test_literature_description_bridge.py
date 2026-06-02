import sqlite3
import tempfile
import unittest
import csv
from pathlib import Path

from AntSleap.core.literature_descriptions import (
    build_description_source,
    build_text_block_source,
    candidate_literature_db_paths,
    infer_literature_db_path_from_artifact_image,
    query_literature_part_descriptions,
    query_literature_text_blocks,
    resolve_literature_context,
)
from AntSleap.core.project import ProjectManager


class LiteratureDescriptionBridgeTests(unittest.TestCase):
    def _create_minimal_literature_db(self, db_path, image_path, *, figure_id=7, pdf_id=3, species="Aphaenogaster gamagumayaa"):
        db_path = Path(db_path)
        image_path = Path(image_path)
        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()
            c.execute("CREATE TABLE pdf_files (id INTEGER PRIMARY KEY, file_path TEXT, file_name TEXT)")
            c.execute(
                """
                CREATE TABLE figure_records (
                    id INTEGER PRIMARY KEY,
                    pdf_file_id INTEGER,
                    page_number INTEGER,
                    figure_index INTEGER,
                    image_file_path TEXT,
                    image_file_name TEXT,
                    species_candidate TEXT
                )
                """
            )
            c.execute(
                """
                CREATE TABLE taxon_part_descriptions (
                    id INTEGER PRIMARY KEY,
                    pdf_file_id INTEGER,
                    file_name TEXT,
                    file_path TEXT,
                    file_hash TEXT,
                    taxon_name TEXT,
                    caste_or_stage TEXT,
                    part_key TEXT,
                    part_label TEXT,
                    description_text TEXT,
                    source_pages TEXT,
                    source_block_refs TEXT,
                    source_blocks TEXT,
                    model_used TEXT,
                    confidence REAL,
                    review_status TEXT,
                    created_at TEXT
                )
                """
            )
            c.execute("INSERT INTO pdf_files (id, file_path, file_name) VALUES (?, ?, 'paper.pdf')", (pdf_id, str(db_path.parent / "paper.pdf")))
            c.execute(
                """
                INSERT INTO figure_records
                    (id, pdf_file_id, page_number, figure_index, image_file_path, image_file_name, species_candidate)
                VALUES (?, ?, 2, 1, ?, ?, ?)
                """,
                (figure_id, pdf_id, str(image_path), image_path.name, species),
            )
            c.execute(
                """
                INSERT INTO taxon_part_descriptions
                    (id, pdf_file_id, file_name, file_path, file_hash, taxon_name, caste_or_stage,
                     part_key, part_label, description_text, source_pages, source_block_refs,
                     source_blocks, model_used, confidence, review_status, created_at)
                VALUES
                    (11, ?, 'paper.pdf', ?, 'hash', ?, 'worker',
                     'scape', '触角/柄节', 'Scapes elongate and slim.',
                     '[2]', '["p002_b0003"]', '[]', 'mock', 0.91, 'auto_extracted', 'now')
                """,
                (pdf_id, str(db_path.parent / "paper.pdf"), species),
            )
            conn.commit()
        finally:
            conn.close()

    def test_artifact_image_infers_sibling_db_and_does_not_cross_match_by_number(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            right_db = tmp / "right_run.db"
            wrong_db = tmp / "wrong_run.db"
            image_dir = tmp / "right_run_v2_artifacts" / "accepted_figures"
            image_dir.mkdir(parents=True)
            image_path = image_dir / "paper__accepted_000007__figure.png"
            image_path.write_bytes(b"image")
            source_image = tmp / "right_run_v2_artifacts" / "figure_images" / "paper_source.png"
            source_image.parent.mkdir(parents=True)
            source_image.write_bytes(b"source")

            self._create_minimal_literature_db(right_db, source_image, figure_id=7, pdf_id=3)
            stats_dir = tmp / "right_run_v2_artifacts" / "stats"
            stats_dir.mkdir(parents=True)
            with open(stats_dir / "paper_import_ready_figures.csv", "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "pdf_file_id",
                        "figure_id",
                        "status",
                        "pdf_name",
                        "page_number",
                        "species_candidate",
                        "final_confidence",
                        "category",
                        "review_status",
                        "source_image_path",
                        "exported_image_path",
                        "exported_image_name",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "pdf_file_id": 3,
                        "figure_id": 7,
                        "status": "accepted",
                        "pdf_name": "paper.pdf",
                        "page_number": 2,
                        "species_candidate": "Aphaenogaster gamagumayaa",
                        "final_confidence": 0.91,
                        "category": "taxonomic",
                        "review_status": "accepted",
                        "source_image_path": str(source_image),
                        "exported_image_path": str(image_path),
                        "exported_image_name": image_path.name,
                    }
                )
            other_image = tmp / "wrong_run_v2_artifacts" / "accepted_figures" / image_path.name
            other_image.parent.mkdir(parents=True)
            other_image.write_bytes(b"other")
            self._create_minimal_literature_db(wrong_db, other_image, figure_id=7, pdf_id=9, species="Wrong species")

            self.assertEqual(Path(infer_literature_db_path_from_artifact_image(str(image_path))), right_db)

            wrong_context = resolve_literature_context(
                str(wrong_db),
                image_path=str(image_path),
                provenance={},
                allow_filename_figure_id=False,
            )
            self.assertFalse(wrong_context["available"])

            paths = candidate_literature_db_paths(
                repo_root=str(tmp),
                provenance={},
                extra_paths=[infer_literature_db_path_from_artifact_image(str(image_path)), str(wrong_db)],
            )
            self.assertEqual(Path(paths[0]), right_db)

            right_context = resolve_literature_context(
                str(right_db),
                image_path=str(image_path),
                provenance={},
                allow_filename_figure_id=True,
            )
            self.assertTrue(right_context["available"])
            self.assertEqual(right_context["pdf_file_id"], 3)

    def test_resolves_current_pdf_figure_and_queries_part_description(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            db_path = tmp / "literature.db"
            image_path = tmp / "zootaxa__accepted_000007__figure.png"
            image_path.write_bytes(b"placeholder")

            conn = sqlite3.connect(db_path)
            try:
                c = conn.cursor()
                c.execute(
                    """
                    CREATE TABLE pdf_files (
                        id INTEGER PRIMARY KEY,
                        file_path TEXT,
                        file_name TEXT
                    )
                    """
                )
                c.execute(
                    """
                    CREATE TABLE figure_records (
                        id INTEGER PRIMARY KEY,
                        pdf_file_id INTEGER,
                        page_number INTEGER,
                        figure_index INTEGER,
                        image_file_path TEXT,
                        image_file_name TEXT,
                        species_candidate TEXT
                    )
                    """
                )
                c.execute(
                    """
                    CREATE TABLE taxon_part_descriptions (
                        id INTEGER PRIMARY KEY,
                        pdf_file_id INTEGER,
                        file_name TEXT,
                        file_path TEXT,
                        file_hash TEXT,
                        taxon_name TEXT,
                        caste_or_stage TEXT,
                        part_key TEXT,
                        part_label TEXT,
                        description_text TEXT,
                        source_pages TEXT,
                        source_block_refs TEXT,
                        source_blocks TEXT,
                        model_used TEXT,
                        confidence REAL,
                        review_status TEXT,
                        created_at TEXT
                    )
                    """
                )
                c.execute(
                    "INSERT INTO pdf_files (id, file_path, file_name) VALUES (3, ?, ?)",
                    (str(tmp / "paper.pdf"), "paper.pdf"),
                )
                c.execute(
                    """
                    INSERT INTO figure_records
                        (id, pdf_file_id, page_number, figure_index, image_file_path, image_file_name, species_candidate)
                    VALUES (7, 3, 2, 1, ?, ?, ?)
                    """,
                    (str(image_path), image_path.name, "Aphaenogaster gamagumayaa"),
                )
                c.execute(
                    """
                    INSERT INTO taxon_part_descriptions
                        (id, pdf_file_id, file_name, file_path, file_hash, taxon_name, caste_or_stage,
                         part_key, part_label, description_text, source_pages, source_block_refs,
                         source_blocks, model_used, confidence, review_status, created_at)
                    VALUES
                        (11, 3, 'paper.pdf', ?, 'hash', 'Aphaenogaster gamagumayaa', 'worker',
                         'pronotum', '前胸背板', 'Pronotum elongate and regularly convex.',
                         '[2]', '["p002_b0003"]', '[]', 'mock', 0.91, 'auto_extracted', 'now')
                    """,
                    (str(tmp / "paper.pdf"),),
                )
                conn.commit()
            finally:
                conn.close()

            context = resolve_literature_context(
                str(db_path),
                image_path=str(image_path),
                provenance={"source_ref": {"table": "figure_records", "row_id": 7}},
            )

            self.assertTrue(context["available"])
            self.assertEqual(context["pdf_file_id"], 3)
            self.assertEqual(context["species_candidate"], "Aphaenogaster gamagumayaa")

            rows = query_literature_part_descriptions(
                str(db_path),
                context=context,
                current_part="Pronotum",
                search_text="前胸背板",
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["part_key"], "pronotum")
            self.assertIn("Pronotum elongate", rows[0]["description_text"])

    def test_project_stores_selected_description_and_source(self):
        manager = ProjectManager()
        image_path = str(Path(tempfile.gettempdir()) / "taxamask_selected.png")
        manager.project_data["images"] = [image_path]
        manager.project_data["labels"] = {
            image_path: {
                "parts": {},
                "status": "needs_review",
                "genus": "Aphaenogaster gamagumayaa",
                "taxon": "Aphaenogaster gamagumayaa",
                "descriptions": {},
            }
        }

        source = build_description_source(
            {
                "id": 11,
                "pdf_file_id": 3,
                "file_name": "paper.pdf",
                "file_path": "paper.pdf",
                "taxon_name": "Aphaenogaster gamagumayaa",
                "caste_or_stage": "worker",
                "part_key": "pronotum",
                "part_label": "前胸背板",
                "source_pages": [2],
                "source_block_refs": ["p002_b0003"],
                "confidence": 0.91,
                "review_status": "auto_extracted",
            },
            {"figure_id": 7, "species_candidate": "Aphaenogaster gamagumayaa"},
        )
        manager.set_part_description(
            image_path,
            "Pronotum",
            "Pronotum elongate and regularly convex.",
            source_meta=source,
            save=False,
        )

        self.assertEqual(
            manager.get_part_description(image_path, "Pronotum"),
            "Pronotum elongate and regularly convex.",
        )
        saved_source = manager.get_description_source(image_path, "Pronotum")
        self.assertEqual(saved_source["record_id"], 11)
        self.assertEqual(saved_source["part_key"], "pronotum")

    def test_cropped_pdf_candidate_inherits_context_from_parent_provenance(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            db_path = tmp / "literature.db"
            parent_image = tmp / "paper__accepted_000007__figure.jpg"
            crop_image = tmp / "paper__accepted_000007__figure__crop_001.jpg"
            parent_image.write_bytes(b"parent")
            crop_image.write_bytes(b"crop")

            conn = sqlite3.connect(db_path)
            try:
                c = conn.cursor()
                c.execute("CREATE TABLE pdf_files (id INTEGER PRIMARY KEY, file_path TEXT, file_name TEXT)")
                c.execute(
                    """
                    CREATE TABLE figure_records (
                        id INTEGER PRIMARY KEY,
                        pdf_file_id INTEGER,
                        page_number INTEGER,
                        figure_index INTEGER,
                        image_file_path TEXT,
                        image_file_name TEXT,
                        species_candidate TEXT
                    )
                    """
                )
                c.execute(
                    """
                    CREATE TABLE taxon_part_descriptions (
                        id INTEGER PRIMARY KEY,
                        pdf_file_id INTEGER,
                        file_name TEXT,
                        file_path TEXT,
                        file_hash TEXT,
                        taxon_name TEXT,
                        caste_or_stage TEXT,
                        part_key TEXT,
                        part_label TEXT,
                        description_text TEXT,
                        source_pages TEXT,
                        source_block_refs TEXT,
                        source_blocks TEXT,
                        model_used TEXT,
                        confidence REAL,
                        review_status TEXT,
                        created_at TEXT
                    )
                    """
                )
                c.execute("INSERT INTO pdf_files (id, file_path, file_name) VALUES (3, ?, 'paper.pdf')", (str(tmp / "paper.pdf"),))
                c.execute(
                    """
                    INSERT INTO figure_records
                        (id, pdf_file_id, page_number, figure_index, image_file_path, image_file_name, species_candidate)
                    VALUES (7, 3, 2, 1, ?, ?, 'Aphaenogaster gamagumayaa')
                    """,
                    (str(parent_image), parent_image.name),
                )
                c.execute(
                    """
                    INSERT INTO taxon_part_descriptions
                        (id, pdf_file_id, file_name, file_path, file_hash, taxon_name, caste_or_stage,
                         part_key, part_label, description_text, source_pages, source_block_refs,
                         source_blocks, model_used, confidence, review_status, created_at)
                    VALUES
                        (11, 3, 'paper.pdf', ?, 'hash', 'Aphaenogaster gamagumayaa', 'worker',
                         'scape', '触角/柄节', 'Scapes elongate and slim.',
                         '[2]', '["p002_b0003"]', '[]', 'mock', 0.91, 'auto_extracted', 'now')
                    """,
                    (str(tmp / "paper.pdf"),),
                )
                conn.commit()
            finally:
                conn.close()

            provenance = {
                "source_type": "pdf_candidate_crop",
                "source_db": str(db_path),
                "source_ref": {"table": "figure_records", "row_id": 7},
                "species_candidate": "Aphaenogaster gamagumayaa",
                "derived_from": {
                    "image_path": str(parent_image),
                    "crop_index": 1,
                    "crop_box": [10, 20, 100, 120],
                },
            }
            context = resolve_literature_context(str(db_path), image_path=str(crop_image), provenance=provenance)

            self.assertTrue(context["available"])
            self.assertEqual(context["figure_id"], 7)
            rows = query_literature_part_descriptions(str(db_path), context=context, current_part="scape")
            self.assertEqual(len(rows), 1)
            self.assertIn("Scapes elongate", rows[0]["description_text"])

    def test_raw_pdf_text_block_search_is_available_as_fallback(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            db_path = tmp / "literature.db"
            image_path = tmp / "paper__accepted_000007__figure.jpg"
            image_path.write_bytes(b"image")

            conn = sqlite3.connect(db_path)
            try:
                c = conn.cursor()
                c.execute("CREATE TABLE pdf_files (id INTEGER PRIMARY KEY, file_path TEXT, file_name TEXT)")
                c.execute(
                    """
                    CREATE TABLE figure_records (
                        id INTEGER PRIMARY KEY,
                        pdf_file_id INTEGER,
                        page_number INTEGER,
                        figure_index INTEGER,
                        image_file_path TEXT,
                        image_file_name TEXT,
                        species_candidate TEXT
                    )
                    """
                )
                c.execute(
                    """
                    CREATE TABLE taxon_part_descriptions (
                        id INTEGER PRIMARY KEY,
                        pdf_file_id INTEGER,
                        file_name TEXT,
                        file_path TEXT,
                        file_hash TEXT,
                        taxon_name TEXT,
                        caste_or_stage TEXT,
                        part_key TEXT,
                        part_label TEXT,
                        description_text TEXT,
                        source_pages TEXT,
                        source_block_refs TEXT,
                        source_blocks TEXT,
                        model_used TEXT,
                        confidence REAL,
                        review_status TEXT,
                        created_at TEXT
                    )
                    """
                )
                c.execute(
                    """
                    CREATE TABLE pdf_text_blocks (
                        id INTEGER PRIMARY KEY,
                        pdf_file_id INTEGER,
                        file_name TEXT,
                        file_path TEXT,
                        file_hash TEXT,
                        block_ref TEXT,
                        page_number INTEGER,
                        block_index INTEGER,
                        section_hint TEXT,
                        text_type TEXT,
                        text_content TEXT,
                        llm_role TEXT,
                        llm_taxon_name TEXT,
                        llm_confidence REAL,
                        model_used TEXT,
                        created_at TEXT
                    )
                    """
                )
                c.execute("INSERT INTO pdf_files (id, file_path, file_name) VALUES (3, ?, 'paper.pdf')", (str(tmp / "paper.pdf"),))
                c.execute(
                    """
                    INSERT INTO figure_records
                        (id, pdf_file_id, page_number, figure_index, image_file_path, image_file_name, species_candidate)
                    VALUES (7, 3, 2, 1, ?, ?, 'Aphaenogaster gamagumayaa')
                    """,
                    (str(image_path), image_path.name),
                )
                c.execute(
                    """
                    INSERT INTO pdf_text_blocks
                        (id, pdf_file_id, file_name, file_path, file_hash, block_ref, page_number,
                         block_index, section_hint, text_type, text_content, llm_role,
                         llm_taxon_name, llm_confidence, model_used, created_at)
                    VALUES
                        (21, 3, 'paper.pdf', ?, 'hash', 'p004_b0009', 4,
                         9, 'species_account', 'body', 'Scape is remarkably elongate in workers.',
                         'morphological_description', 'Aphaenogaster gamagumayaa', 0.82, 'mock', 'now')
                    """,
                    (str(tmp / "paper.pdf"),),
                )
                conn.commit()
            finally:
                conn.close()

            context = resolve_literature_context(
                str(db_path),
                image_path=str(image_path),
                provenance={"source_ref": {"table": "figure_records", "row_id": 7}},
            )
            structured_rows = query_literature_part_descriptions(str(db_path), context=context, search_text="scape")
            raw_rows = query_literature_text_blocks(str(db_path), context=context, search_text="scape", scope="taxon")

            self.assertEqual(structured_rows, [])
            self.assertEqual(len(raw_rows), 1)
            self.assertEqual(raw_rows[0]["block_ref"], "p004_b0009")
            self.assertIn("remarkably elongate", raw_rows[0]["text_content"])
            source = build_text_block_source(raw_rows[0], context)
            self.assertEqual(source["source"], "pdf_text_block")
            self.assertEqual(source["block_ref"], "p004_b0009")


if __name__ == "__main__":
    unittest.main()
