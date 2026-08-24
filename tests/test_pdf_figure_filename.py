import csv
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from core.pdf_processor.pdf_extractor import (
    EnhancedPDFExtractionSystem,
    ImportReadyProjectionRecoveryRequired,
)
from core.pdf_processor.part_description_extractor import PartExtractionResult


class _FailingCommitConnection:
    def __init__(self, connection):
        self._connection = connection

    def commit(self):
        raise RuntimeError("injected commit failure")

    def __getattr__(self, name):
        return getattr(self._connection, name)


class FigureFilenameTests(unittest.TestCase):
    def test_caption_whitespace_is_safe_for_windows_filename(self):
        extractor = object.__new__(EnhancedPDFExtractionSystem)
        extractor.db_conn = None
        scope = extractor._pdf_artifact_scope(file_name="sample.pdf")

        filename = extractor._generate_figure_filename(
            "sample.pdf",
            34,
            1,
            {"text_content": "29 24\t Propodeal\nspines long"},
            "1e3fbbbb00000000",
        )

        self.assertEqual(
            filename,
            f"{scope}_p034_f001_29_24_Propodeal_spines_long_1e3fbbbb.png",
        )
        self.assertIsNone(re.search(r"\s", filename))

    def test_pdf_identity_prevents_sanitized_and_truncated_name_collisions(self):
        extractor = object.__new__(EnhancedPDFExtractionSystem)
        extractor.db_conn = None

        spaced = extractor._generate_figure_filename(
            "A B.pdf", 1, 1, {"text_content": "Figure 1"}, "samehash00000000"
        )
        underscored = extractor._generate_figure_filename(
            "A_B.pdf", 1, 1, {"text_content": "Figure 1"}, "samehash00000000"
        )
        long_a = extractor._generate_figure_filename(
            f"{'x' * 80}A.pdf", 1, 1, None, "samehash00000000"
        )
        long_b = extractor._generate_figure_filename(
            f"{'x' * 80}B.pdf", 1, 1, None, "samehash00000000"
        )

        self.assertNotEqual(spaced, underscored)
        self.assertNotEqual(long_a, long_b)
        self.assertRegex(spaced, r"^A_B--[0-9a-f]{16}_p001_f001_")
        self.assertRegex(underscored, r"^A_B--[0-9a-f]{16}_p001_f001_")

    def test_pdf_scope_is_stable_for_content_updates_at_the_same_source_path(self):
        extractor = object.__new__(EnhancedPDFExtractionSystem)
        extractor.db_conn = None
        source_path = str(Path("papers") / "sample.pdf")

        old_scope = extractor._pdf_artifact_scope(
            file_name="sample.pdf", file_hash="old-hash", file_path=source_path
        )
        new_scope = extractor._pdf_artifact_scope(
            file_name="sample.pdf", file_hash="new-hash", file_path=source_path
        )
        other_scope = extractor._pdf_artifact_scope(
            file_name="sample.pdf",
            file_hash="new-hash",
            file_path=str(Path("other") / "sample.pdf"),
        )

        self.assertEqual(old_scope, new_scope)
        self.assertNotEqual(old_scope, other_scope)

    def test_relative_pdf_scope_does_not_change_with_current_working_directory(self):
        extractor = object.__new__(EnhancedPDFExtractionSystem)
        extractor.db_conn = None
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            try:
                os.chdir(first)
                first_scope = extractor._pdf_artifact_scope(
                    file_name="sample.pdf",
                    file_path=str(Path("papers") / "sample.pdf"),
                )
                os.chdir(second)
                second_scope = extractor._pdf_artifact_scope(
                    file_name="sample.pdf",
                    file_path=str(Path("papers") / "sample.pdf"),
                )
            finally:
                os.chdir(original_cwd)

        self.assertEqual(first_scope, second_scope)

    def test_distinct_sqlite_file_path_strings_never_share_a_pdf_scope(self):
        extractor = object.__new__(EnhancedPDFExtractionSystem)
        extractor.db_conn = None

        with patch(
            "core.pdf_processor.pdf_extractor.os.path.realpath",
            return_value=str(Path("physical") / "sample.pdf"),
        ):
            first_scope = extractor._pdf_artifact_scope(
                file_name="sample.pdf",
                file_path=str(Path("link-a") / "sample.pdf"),
            )
            second_scope = extractor._pdf_artifact_scope(
                file_name="sample.pdf",
                file_path=str(Path("link-b") / "sample.pdf"),
            )

        self.assertNotEqual(first_scope, second_scope)

    def test_unicode_only_caption_falls_back_to_figure(self):
        extractor = object.__new__(EnhancedPDFExtractionSystem)
        extractor.db_conn = None

        filename = extractor._generate_figure_filename(
            "蚂蚁形态.pdf",
            2,
            3,
            {"text_content": "图二：头部形态"},
            "abcdef1200000000",
        )

        self.assertRegex(filename, r"^pdf--[0-9a-f]{16}_p002_f003_figure_abcdef12\.png$")
        self.assertIsNone(re.search(r"\s", filename))

    def _insert_accepted_figure(self, extractor, root: Path, payload: bytes = b"new"):
        file_name = "paper.pdf"
        file_path = str(root / file_name)
        file_hash = "fixture-hash"
        scope = extractor._pdf_artifact_scope(
            file_name=file_name,
            file_hash=file_hash,
            file_path=file_path,
        )
        source_name = extractor._generate_figure_filename(
            file_name,
            1,
            1,
            {"text_content": "Figure 1"},
            "1234567800000000",
            pdf_artifact_scope=scope,
        )
        source_path = extractor.figures_dir / source_name
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(payload)

        cursor = extractor.db_conn.cursor()
        cursor.execute(
            """
            INSERT INTO pdf_files (file_path, file_name, file_hash, total_pages, file_size)
            VALUES (?, ?, ?, 1, ?)
            """,
            (file_path, file_name, file_hash, len(payload)),
        )
        pdf_file_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO figure_records (
                pdf_file_id, page_number, figure_index, candidate_id, figure_hash,
                figure_bbox, image_file_path, image_file_name, accepted, review_status
            ) VALUES (?, 1, 1, 'candidate-1', '12345678', '{}', ?, ?, 1, 'accepted')
            """,
            (pdf_file_id, str(source_path), source_name),
        )
        extractor.db_conn.commit()
        return pdf_file_id, scope, source_path

    def _run_artifact_writers(self, extractor):
        written = {}

        def build_candidate(**kwargs):
            run_scope = kwargs["pdf_artifact_scope"]
            figure_path = extractor.figures_dir / f"{run_scope}_p001_f001_new_22222222.png"
            extractor._touched_figure_artifacts.add(figure_path.name)
            figure_path.write_bytes(b"new-figure")
            written["figure"] = figure_path
            return {
                "candidate_id": "fig_p001_001",
                "page_number": 1,
                "figure_index": 1,
                "image_path": str(figure_path),
                "image_file_name": figure_path.name,
            }

        def review_candidates(candidates, run_scope):
            written["batch"] = Path(
                extractor._save_batch_manifest(f"{run_scope}_batch_0001", candidates)
            )
            written["raw"] = Path(
                extractor._save_batch_raw_response(f"{run_scope}_batch_0001", "new-raw")
            )
            return candidates

        return written, build_candidate, review_candidates

    def test_real_import_ready_files_and_manifests_are_isolated_per_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                records = []
                for index, (file_name, file_hash, payload) in enumerate(
                    (("A B.pdf", "same-content-hash", b"spaced"), ("A_B.pdf", "same-content-hash", b"underscored")),
                    start=1,
                ):
                    file_path = str(root / f"source-{index}" / file_name)
                    scope = extractor._pdf_artifact_scope(
                        file_name=file_name,
                        file_hash=file_hash,
                        file_path=file_path,
                    )
                    source_name = extractor._generate_figure_filename(
                        file_name,
                        1,
                        1,
                        {"text_content": "Figure 1"},
                        "1234567800000000",
                        pdf_artifact_scope=scope,
                    )
                    source_path = extractor.figures_dir / source_name
                    source_path.parent.mkdir(parents=True, exist_ok=True)
                    source_path.write_bytes(payload)

                    cursor = extractor.db_conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO pdf_files (file_path, file_name, file_hash, total_pages, file_size)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (file_path, file_name, file_hash, 1, len(payload)),
                    )
                    pdf_file_id = int(cursor.lastrowid)
                    cursor.execute(
                        """
                        INSERT INTO figure_records (
                            pdf_file_id, page_number, figure_index, candidate_id, figure_hash,
                            figure_bbox, image_file_path, image_file_name, accepted, review_status
                        ) VALUES (?, 1, 1, ?, ?, '{}', ?, ?, 1, 'accepted')
                        """,
                        (pdf_file_id, f"candidate-{index}", "12345678", str(source_path), source_name),
                    )
                    extractor.db_conn.commit()
                    stats = extractor._sync_import_ready_figure_exports(pdf_file_id)
                    records.append((pdf_file_id, payload, stats))

                first_manifest = Path(str(records[0][2]["import_ready_manifest"]))
                second_manifest = Path(str(records[1][2]["import_ready_manifest"]))
                self.assertNotEqual(first_manifest, second_manifest)
                self.assertTrue(first_manifest.exists())
                self.assertTrue(second_manifest.exists())

                exported_paths = []
                for pdf_file_id, payload, stats in records:
                    with open(stats["import_ready_manifest"], "r", encoding="utf-8-sig", newline="") as handle:
                        rows = list(csv.DictReader(handle))
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(int(rows[0]["pdf_file_id"]), pdf_file_id)
                    exported_path = Path(rows[0]["exported_image_path"])
                    self.assertEqual(exported_path.read_bytes(), payload)
                    exported_paths.append(exported_path)

                self.assertNotEqual(exported_paths[0].name, exported_paths[1].name)
                legacy_export = extractor.accepted_figures_dir / "A_B__accepted_999999__legacy.png"
                legacy_manifest = extractor.stats_dir / "A_B_import_ready_figures.csv"
                legacy_export.write_bytes(b"ambiguous-legacy")
                legacy_manifest.write_text("legacy", encoding="utf-8")
                extractor._sync_import_ready_figure_exports(records[0][0])
                self.assertEqual(exported_paths[1].read_bytes(), b"underscored")
                self.assertTrue(legacy_export.exists())
                self.assertTrue(legacy_manifest.exists())
            finally:
                extractor.close()

    def test_import_ready_copy_failure_preserves_previous_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                pdf_file_id, scope, _ = self._insert_accepted_figure(extractor, root)
                old_export = extractor.accepted_figures_dir / f"{scope}__accepted_000001__old.png"
                old_manifest = extractor.stats_dir / f"{scope}_import_ready_figures.csv"
                old_export.parent.mkdir(parents=True, exist_ok=True)
                old_export.write_bytes(b"old-export")
                old_manifest.write_bytes(b"old-manifest")

                with patch(
                    "core.pdf_processor.pdf_extractor.shutil.copy2",
                    side_effect=OSError("injected copy failure"),
                ):
                    with self.assertRaisesRegex(OSError, "injected copy failure"):
                        extractor._sync_import_ready_figure_exports(pdf_file_id)

                self.assertEqual(old_export.read_bytes(), b"old-export")
                self.assertEqual(old_manifest.read_bytes(), b"old-manifest")
                self.assertFalse(
                    any(path.name.startswith(f".{scope}_import_ready_") for path in extractor.artifacts_dir.iterdir())
                )
            finally:
                extractor.close()

    def test_import_ready_missing_source_preserves_previous_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                pdf_file_id, scope, source_path = self._insert_accepted_figure(extractor, root)
                old_export = extractor.accepted_figures_dir / f"{scope}__accepted_000001__old.png"
                old_manifest = extractor.stats_dir / f"{scope}_import_ready_figures.csv"
                old_export.parent.mkdir(parents=True, exist_ok=True)
                old_export.write_bytes(b"old-export")
                old_manifest.write_bytes(b"old-manifest")
                source_path.unlink()

                with self.assertRaisesRegex(FileNotFoundError, "import_ready_source_images_missing"):
                    extractor._sync_import_ready_figure_exports(pdf_file_id)

                self.assertEqual(old_export.read_bytes(), b"old-export")
                self.assertEqual(old_manifest.read_bytes(), b"old-manifest")
                self.assertFalse(
                    any(path.name.startswith(f".{scope}_import_ready_") for path in extractor.artifacts_dir.iterdir())
                )
            finally:
                extractor.close()

    def test_import_ready_publish_reports_temporary_backup_cleanup_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                pdf_file_id, scope, _ = self._insert_accepted_figure(extractor, root)
                old_export = extractor.accepted_figures_dir / f"{scope}__accepted_000001__old.png"
                old_manifest = extractor.stats_dir / f"{scope}_import_ready_figures.csv"
                old_export.parent.mkdir(parents=True, exist_ok=True)
                old_export.write_bytes(b"old-export")
                old_manifest.write_bytes(b"old-manifest")

                with self.assertLogs("core.pdf_processor.pdf_extractor", level="WARNING") as logs, patch(
                    "core.pdf_processor.pdf_extractor.shutil.rmtree",
                    side_effect=PermissionError("injected stage cleanup failure"),
                ):
                    stats = extractor._sync_import_ready_figure_exports(pdf_file_id)

                self.assertEqual(stats["import_ready_export_status"], "success")
                self.assertIn("injected stage cleanup failure", stats["import_ready_cleanup_warning"])
                cleanup_directory = Path(stats["import_ready_cleanup_directory"])
                self.assertTrue(cleanup_directory.is_dir())
                self.assertTrue((cleanup_directory / "previous" / "accepted" / old_export.name).is_file())
                self.assertTrue((cleanup_directory / "previous" / "stats" / old_manifest.name).is_file())
                self.assertIn("temporary backup cleanup was incomplete", logs.output[0])
            finally:
                extractor.close()

    def test_import_ready_manifest_write_failure_preserves_previous_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                pdf_file_id, scope, _ = self._insert_accepted_figure(extractor, root)
                old_export = extractor.accepted_figures_dir / f"{scope}__accepted_000001__old.png"
                old_manifest = extractor.stats_dir / f"{scope}_import_ready_figures.csv"
                old_export.parent.mkdir(parents=True, exist_ok=True)
                old_export.write_bytes(b"old-export")
                old_manifest.write_bytes(b"old-manifest")

                with patch.object(
                    extractor,
                    "_write_import_ready_manifest",
                    side_effect=OSError("injected manifest failure"),
                ):
                    with self.assertRaisesRegex(OSError, "injected manifest failure"):
                        extractor._sync_import_ready_figure_exports(pdf_file_id)

                self.assertEqual(old_export.read_bytes(), b"old-export")
                self.assertEqual(old_manifest.read_bytes(), b"old-manifest")
            finally:
                extractor.close()

    def test_import_ready_publish_failure_restores_previous_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                pdf_file_id, scope, _ = self._insert_accepted_figure(extractor, root)
                old_export = extractor.accepted_figures_dir / f"{scope}__accepted_000001__old.png"
                old_manifest = extractor.stats_dir / f"{scope}_import_ready_figures.csv"
                old_export.parent.mkdir(parents=True, exist_ok=True)
                old_export.write_bytes(b"old-export")
                old_manifest.write_bytes(b"old-manifest")
                real_replace = os.replace

                def fail_staged_manifest(source, target):
                    if Path(source).name == "manifest.csv":
                        raise OSError("injected publish failure")
                    return real_replace(source, target)

                with patch(
                    "core.pdf_processor.pdf_extractor.os.replace",
                    side_effect=fail_staged_manifest,
                ):
                    with self.assertRaisesRegex(OSError, "injected publish failure"):
                        extractor._sync_import_ready_figure_exports(pdf_file_id)

                self.assertEqual(old_export.read_bytes(), b"old-export")
                self.assertEqual(old_manifest.read_bytes(), b"old-manifest")
                current_exports = list(extractor.accepted_figures_dir.glob(f"{scope}__*"))
                self.assertEqual(current_exports, [old_export])
            finally:
                extractor.close()

    def test_projection_failure_preserves_source_used_by_restored_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "paper.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\nfixture\n%%EOF\n")
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
                resume_completed_pdfs=False,
            )
            try:
                old_pdf_id, scope, old_source = self._insert_accepted_figure(
                    extractor, root, payload=b"old-source"
                )
                old_stats = extractor._sync_import_ready_figure_exports(old_pdf_id)
                manifest_path = Path(str(old_stats["import_ready_manifest"]))
                with open(
                    manifest_path, "r", encoding="utf-8-sig", newline=""
                ) as handle:
                    old_row = next(csv.DictReader(handle))
                old_export = Path(old_row["exported_image_path"])

                new_run_scope = f"{scope}_run_new000000000"
                new_source = (
                    extractor.figures_dir
                    / f"{new_run_scope}_p001_f001_new_22222222.png"
                )

                def build_candidate(**_kwargs):
                    new_source.write_bytes(b"new-source")
                    extractor._touched_figure_artifacts.add(new_source.name)
                    return {
                        "candidate_id": "new",
                        "page_number": 1,
                        "figure_index": 1,
                        "figure_hash": "newhash",
                        "image_path": str(new_source),
                        "image_file_name": new_source.name,
                        "accepted": True,
                        "review_status": "accepted",
                    }

                document = MagicMock()
                document.__len__.return_value = 1
                real_replace = os.replace

                def fail_staged_manifest(source, target):
                    if Path(source).name == "manifest.csv":
                        raise OSError("injected manifest publish failure")
                    return real_replace(source, target)

                with patch(
                    "core.pdf_processor.pdf_extractor.fitz.open",
                    return_value=document,
                ), patch.object(
                    extractor,
                    "_pdf_artifact_run_scope",
                    return_value=new_run_scope,
                ), patch.object(
                    extractor,
                    "_extract_document_text_blocks",
                    return_value=[],
                ), patch.object(
                    extractor,
                    "_extract_text_part_descriptions",
                    return_value=PartExtractionResult(
                        status="skipped", reason="fixture"
                    ),
                ), patch.object(
                    extractor,
                    "_collect_page_visual_rects",
                    return_value=[{}],
                ), patch.object(
                    extractor,
                    "_cluster_image_rects",
                    return_value=[[{}]],
                ), patch.object(
                    extractor,
                    "_build_figure_candidate",
                    side_effect=build_candidate,
                ), patch.object(
                    extractor,
                    "_review_all_candidates",
                    side_effect=lambda candidates, _scope: candidates,
                ), patch(
                    "core.pdf_processor.pdf_extractor.os.replace",
                    side_effect=fail_staged_manifest,
                ):
                    result = extractor.extract_from_pdf(str(pdf_path))

                with open(
                    manifest_path, "r", encoding="utf-8-sig", newline=""
                ) as handle:
                    restored_row = next(csv.DictReader(handle))

                self.assertEqual(result["status"], "partial_success")
                self.assertEqual(restored_row, old_row)
                self.assertTrue(old_export.is_file())
                self.assertTrue(old_source.is_file())
                self.assertTrue(Path(restored_row["source_image_path"]).is_file())
                self.assertTrue(new_source.is_file())
                document.close.assert_called_once_with()
            finally:
                extractor.close()

    def test_import_ready_incomplete_rollback_preserves_manual_recovery_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                pdf_file_id, scope, _ = self._insert_accepted_figure(extractor, root)
                old_export = extractor.accepted_figures_dir / f"{scope}__accepted_000001__old.png"
                old_manifest = extractor.stats_dir / f"{scope}_import_ready_figures.csv"
                old_export.parent.mkdir(parents=True, exist_ok=True)
                old_export.write_bytes(b"old-export")
                old_manifest.write_bytes(b"old-manifest")
                real_replace = os.replace

                def fail_publish_and_restore(source, target):
                    source_path = Path(source)
                    if source_path.name == "manifest.csv":
                        raise OSError("injected publish failure")
                    if "previous" in source_path.parts:
                        raise OSError("injected restore failure")
                    return real_replace(source, target)

                with patch(
                    "core.pdf_processor.pdf_extractor.os.replace",
                    side_effect=fail_publish_and_restore,
                ):
                    with self.assertRaises(ImportReadyProjectionRecoveryRequired) as raised:
                        extractor._sync_import_ready_figure_exports(pdf_file_id)

                recovery_dir = Path(raised.exception.recovery_directory)
                self.assertTrue(recovery_dir.is_absolute())
                self.assertTrue(recovery_dir.is_dir())
                self.assertIn(str(recovery_dir), str(raised.exception))
                self.assertEqual(
                    (recovery_dir / "previous" / "accepted" / old_export.name).read_bytes(),
                    b"old-export",
                )
                self.assertEqual(
                    (recovery_dir / "previous" / "stats" / old_manifest.name).read_bytes(),
                    b"old-manifest",
                )
            finally:
                extractor.close()

    def test_unambiguous_legacy_import_ready_artifacts_are_removed_after_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                cursor = extractor.db_conn.cursor()
                source_path = str(root / "paper.pdf")
                cursor.execute(
                    """
                    INSERT INTO pdf_files (file_path, file_name, file_hash, total_pages, file_size)
                    VALUES (?, ?, ?, 1, 1)
                    """,
                    (source_path, "paper.pdf", "hash"),
                )
                pdf_file_id = int(cursor.lastrowid)
                extractor.db_conn.commit()
                legacy_accepted = extractor.accepted_figures_dir / "paper__accepted_000001__old.png"
                legacy_review = extractor.review_figures_dir / "paper__review_000001__old.png"
                legacy_manifest = extractor.stats_dir / "paper_import_ready_figures.csv"
                legacy_accepted.parent.mkdir(parents=True, exist_ok=True)
                legacy_review.parent.mkdir(parents=True, exist_ok=True)
                legacy_accepted.write_bytes(b"old")
                legacy_review.write_bytes(b"old")
                legacy_manifest.write_text("old", encoding="utf-8")

                current_scope = extractor._pdf_artifact_scope(
                    file_name="paper.pdf", file_hash="hash", file_path=source_path
                )
                extractor._remove_unambiguous_legacy_import_ready_artifacts(
                    pdf_file_id=pdf_file_id,
                    current_scope=current_scope,
                )

                self.assertFalse(legacy_accepted.exists())
                self.assertFalse(legacy_review.exists())
                self.assertFalse(legacy_manifest.exists())
            finally:
                extractor.close()

    def test_case_only_legacy_scopes_are_ambiguous_on_case_insensitive_filesystems(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                cursor = extractor.db_conn.cursor()
                for index, file_name in enumerate(("Paper.pdf", "paper.pdf"), start=1):
                    cursor.execute(
                        """
                        INSERT INTO pdf_files (file_path, file_name, file_hash, total_pages, file_size)
                        VALUES (?, ?, ?, 1, 1)
                        """,
                        (str(root / f"source-{index}" / file_name), file_name, f"hash-{index}"),
                    )
                extractor.db_conn.commit()
                first_id = int(
                    extractor.db_conn.execute(
                        "SELECT id FROM pdf_files WHERE file_name = 'Paper.pdf'"
                    ).fetchone()[0]
                )
                legacy_export = extractor.accepted_figures_dir / "Paper__accepted_000001__old.png"
                legacy_manifest = extractor.stats_dir / "Paper_import_ready_figures.csv"
                legacy_export.parent.mkdir(parents=True, exist_ok=True)
                legacy_export.write_bytes(b"case-ambiguous")
                legacy_manifest.write_text("case-ambiguous", encoding="utf-8")
                current_scope = extractor._pdf_artifact_scope(
                    file_name="Paper.pdf",
                    file_hash="hash-1",
                    file_path=str(root / "source-1" / "Paper.pdf"),
                )

                with patch(
                    "core.pdf_processor.pdf_extractor.os.path.normcase",
                    side_effect=lambda value: str(value).lower(),
                ):
                    extractor._remove_unambiguous_legacy_import_ready_artifacts(
                        pdf_file_id=first_id,
                        current_scope=current_scope,
                    )

                self.assertTrue(legacy_export.exists())
                self.assertTrue(legacy_manifest.exists())
            finally:
                extractor.close()

    def test_locked_legacy_artifacts_do_not_fail_import_ready_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                cursor = extractor.db_conn.cursor()
                source_path = str(root / "paper.pdf")
                cursor.execute(
                    """
                    INSERT INTO pdf_files (file_path, file_name, file_hash, total_pages, file_size)
                    VALUES (?, 'paper.pdf', 'hash', 1, 1)
                    """,
                    (source_path,),
                )
                pdf_file_id = int(cursor.lastrowid)
                extractor.db_conn.commit()
                legacy_accepted = extractor.accepted_figures_dir / "paper__accepted_000001__old.png"
                legacy_review = extractor.review_figures_dir / "paper__review_000001__old.png"
                legacy_manifest = extractor.stats_dir / "paper_import_ready_figures.csv"
                legacy_accepted.parent.mkdir(parents=True, exist_ok=True)
                legacy_review.parent.mkdir(parents=True, exist_ok=True)
                legacy_accepted.write_bytes(b"locked")
                legacy_review.write_bytes(b"locked")
                legacy_manifest.write_text("locked", encoding="utf-8")
                extractor.logger = Mock()

                with patch.object(Path, "unlink", side_effect=PermissionError("locked by another process")):
                    stats = extractor._sync_import_ready_figure_exports(pdf_file_id)

                self.assertTrue(Path(str(stats["import_ready_manifest"])).exists())
                self.assertEqual(
                    extractor.db_conn.execute("SELECT COUNT(*) FROM pdf_files").fetchone()[0],
                    1,
                )
                self.assertTrue(legacy_accepted.exists())
                self.assertTrue(legacy_review.exists())
                self.assertTrue(legacy_manifest.exists())
                self.assertEqual(extractor.logger.warning.call_count, 3)
            finally:
                extractor.close()

    def test_second_run_removes_only_untouched_audit_artifacts_in_the_same_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                scope = extractor._pdf_artifact_scope(
                    file_name="paper.pdf",
                    file_hash="new-hash",
                    file_path=str(root / "paper.pdf"),
                )
                extractor._reset_pdf_artifact_tracking()
                current_figure = extractor.figures_dir / f"{scope}_p001_f001_current_11111111.png"
                stale_figure = extractor.figures_dir / f"{scope}_p002_f001_old_22222222.png"
                current_run_scope = f"{scope}_run_current00000"
                stale_run_scope = f"{scope}_run_previous0000"
                current_run_figure = extractor.figures_dir / f"{current_run_scope}_p001_f001_current.png"
                stale_run_figure = extractor.figures_dir / f"{stale_run_scope}_p001_f001_old.png"
                other_figure = extractor.figures_dir / "other--0000000000000000_p001_f001_keep_33333333.png"
                for path in (
                    current_figure,
                    stale_figure,
                    current_run_figure,
                    stale_run_figure,
                    other_figure,
                ):
                    path.write_bytes(path.name.encode("ascii"))
                extractor._touched_figure_artifacts.update({current_figure.name, current_run_figure.name})

                current_batch = Path(
                    extractor._save_batch_manifest(f"{scope}_batch_0001", [{"candidate_id": "current"}])
                )
                current_raw = Path(extractor._save_batch_raw_response(f"{scope}_batch_0001", "current"))
                stale_batch = extractor.batch_dir / f"{scope}_batch_0002.json"
                stale_raw = extractor.batch_raw_dir / f"{scope}_batch_0002_attempt_1_failed.txt"
                current_run_batch = Path(
                    extractor._save_batch_manifest(f"{current_run_scope}_batch_0001", [{"candidate_id": "current"}])
                )
                current_run_raw = Path(
                    extractor._save_batch_raw_response(f"{current_run_scope}_batch_0001", "current")
                )
                stale_run_batch = extractor.batch_dir / f"{stale_run_scope}_batch_0001.json"
                stale_run_raw = extractor.batch_raw_dir / f"{stale_run_scope}_batch_0001.txt"
                stale_batch.write_text("{}", encoding="utf-8")
                stale_raw.write_text("old", encoding="utf-8")
                stale_run_batch.write_text("{}", encoding="utf-8")
                stale_run_raw.write_text("old", encoding="utf-8")

                extractor._cleanup_stale_scoped_audit_artifacts(
                    scope=scope,
                    figure_names=extractor._touched_figure_artifacts,
                    batch_manifest_names=extractor._touched_batch_manifests,
                    raw_response_names=extractor._touched_batch_raw_responses,
                )

                for path in (
                    current_figure,
                    current_run_figure,
                    other_figure,
                    current_batch,
                    current_raw,
                    current_run_batch,
                    current_run_raw,
                ):
                    self.assertTrue(path.exists(), path)
                for path in (
                    stale_figure,
                    stale_run_figure,
                    stale_batch,
                    stale_raw,
                    stale_run_batch,
                    stale_run_raw,
                ):
                    self.assertFalse(path.exists(), path)
            finally:
                extractor.close()

    def test_failed_main_extraction_does_not_cleanup_previous_audit_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "paper.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\nfailed extraction\n%%EOF\n")
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                scope = extractor._pdf_artifact_scope(
                    file_name=pdf_path.name,
                    file_hash=extractor._calculate_file_hash(pdf_path),
                    file_path=str(pdf_path),
                )
                old_figure = extractor.figures_dir / f"{scope}_p001_f001_old_11111111.png"
                old_batch = extractor.batch_dir / f"{scope}_batch_0002.json"
                old_raw = extractor.batch_raw_dir / f"{scope}_batch_0002_fallback.txt"
                old_figure.write_bytes(b"old")
                old_batch.write_text("{}", encoding="utf-8")
                old_raw.write_text("old", encoding="utf-8")
                document = MagicMock()
                document.__len__.return_value = 1

                with patch("core.pdf_processor.pdf_extractor.fitz.open", return_value=document), patch.object(
                    extractor,
                    "_extract_document_text_blocks",
                    side_effect=RuntimeError("injected extraction failure"),
                ), patch.object(
                    extractor,
                    "_cleanup_stale_scoped_audit_artifacts",
                    wraps=extractor._cleanup_stale_scoped_audit_artifacts,
                ) as cleanup:
                    with self.assertRaisesRegex(RuntimeError, "injected extraction failure"):
                        extractor.extract_from_pdf(str(pdf_path))

                cleanup.assert_not_called()
                document.close.assert_called_once_with()
                for path in (old_figure, old_batch, old_raw):
                    self.assertTrue(path.exists(), path)
                self.assertEqual(
                    extractor.db_conn.execute("SELECT COUNT(*) FROM pdf_files").fetchone()[0],
                    0,
                )
            finally:
                extractor.close()

    def test_persist_failure_preserves_old_run_artifacts_and_removes_current_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "paper.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\npersist failure\n%%EOF\n")
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
                resume_completed_pdfs=False,
            )
            try:
                scope = extractor._pdf_artifact_scope(
                    file_name=pdf_path.name,
                    file_hash=extractor._calculate_file_hash(pdf_path),
                    file_path=str(pdf_path),
                )
                old_run_scope = f"{scope}_run_old000000000"
                old_paths = (
                    extractor.figures_dir / f"{old_run_scope}_p001_f001_old_11111111.png",
                    extractor.batch_dir / f"{old_run_scope}_batch_0001.json",
                    extractor.batch_raw_dir / f"{old_run_scope}_batch_0001.txt",
                )
                old_payloads = (b"old-figure", b"old-batch", b"old-raw")
                for path, payload in zip(old_paths, old_payloads):
                    path.write_bytes(payload)

                new_run_scope = f"{scope}_run_new000000000"
                written, build_candidate, review_candidates = self._run_artifact_writers(extractor)
                document = MagicMock()
                document.__len__.return_value = 1

                with patch("core.pdf_processor.pdf_extractor.fitz.open", return_value=document), patch.object(
                    extractor,
                    "_pdf_artifact_run_scope",
                    return_value=new_run_scope,
                ), patch.object(
                    extractor,
                    "_extract_document_text_blocks",
                    return_value=[],
                ), patch.object(
                    extractor,
                    "_extract_text_part_descriptions",
                    return_value=PartExtractionResult(status="skipped", reason="fixture"),
                ), patch.object(
                    extractor,
                    "_collect_page_visual_rects",
                    return_value=[{}],
                ), patch.object(
                    extractor,
                    "_cluster_image_rects",
                    return_value=[[{}]],
                ), patch.object(
                    extractor,
                    "_build_figure_candidate",
                    side_effect=build_candidate,
                ), patch.object(
                    extractor,
                    "_review_all_candidates",
                    side_effect=review_candidates,
                ), patch.object(
                    extractor,
                    "_persist_pdf_results",
                    side_effect=RuntimeError("injected persist failure"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "injected persist failure"):
                        extractor.extract_from_pdf(str(pdf_path))

                for path, payload in zip(old_paths, old_payloads):
                    self.assertEqual(path.read_bytes(), payload)
                self.assertEqual(set(written), {"figure", "batch", "raw"})
                for path in written.values():
                    self.assertFalse(path.exists(), path)
                self.assertEqual(extractor.db_conn.execute("SELECT COUNT(*) FROM pdf_files").fetchone()[0], 0)
                document.close.assert_called_once_with()
            finally:
                extractor.close()

    def test_commit_failure_does_not_publish_exports_and_closes_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "paper.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\ncommit failure\n%%EOF\n")
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
                resume_completed_pdfs=False,
            )
            try:
                scope = extractor._pdf_artifact_scope(
                    file_name=pdf_path.name,
                    file_hash=extractor._calculate_file_hash(pdf_path),
                    file_path=str(pdf_path),
                )
                old_export = extractor.accepted_figures_dir / f"{scope}__accepted_000001__old.png"
                old_manifest = extractor.stats_dir / f"{scope}_import_ready_figures.csv"
                old_export.parent.mkdir(parents=True, exist_ok=True)
                old_export.write_bytes(b"old-export")
                old_manifest.write_bytes(b"old-manifest")
                old_run_scope = f"{scope}_run_old000000000"
                old_run_paths = (
                    extractor.figures_dir / f"{old_run_scope}_p001_f001_old_11111111.png",
                    extractor.batch_dir / f"{old_run_scope}_batch_0001.json",
                    extractor.batch_raw_dir / f"{old_run_scope}_batch_0001.txt",
                )
                old_run_payloads = (b"old-figure", b"old-batch", b"old-raw")
                for path, payload in zip(old_run_paths, old_run_payloads):
                    path.write_bytes(payload)
                new_run_scope = f"{scope}_run_new000000000"
                written, build_candidate, review_candidates = self._run_artifact_writers(extractor)
                document = MagicMock()
                document.__len__.return_value = 1
                part_result = PartExtractionResult(
                    status="skipped",
                    reason="fixture",
                    block_labels=[
                        {
                            "file_name": pdf_path.name,
                            "file_path": str(pdf_path),
                            "file_hash": extractor._calculate_file_hash(pdf_path),
                            "block_ref": "p001_b0000",
                            "page_number": 1,
                            "block_index": 0,
                            "text_content": "fixture",
                        }
                    ],
                )
                extractor.db_conn = _FailingCommitConnection(extractor.db_conn)

                with patch("core.pdf_processor.pdf_extractor.fitz.open", return_value=document), patch.object(
                    extractor,
                    "_pdf_artifact_run_scope",
                    return_value=new_run_scope,
                ), patch.object(
                    extractor,
                    "_extract_document_text_blocks",
                    return_value=[],
                ), patch.object(
                    extractor,
                    "_extract_text_part_descriptions",
                    return_value=part_result,
                ), patch.object(
                    extractor,
                    "_collect_page_visual_rects",
                    return_value=[{}],
                ), patch.object(
                    extractor,
                    "_cluster_image_rects",
                    return_value=[[{}]],
                ), patch.object(
                    extractor,
                    "_build_figure_candidate",
                    side_effect=build_candidate,
                ), patch.object(
                    extractor,
                    "_review_all_candidates",
                    side_effect=review_candidates,
                ), patch.object(
                    extractor,
                    "_persist_pdf_results",
                    return_value={},
                ), patch.object(
                    extractor,
                    "_sync_import_ready_figure_exports",
                ) as export_sync:
                    with self.assertRaisesRegex(RuntimeError, "injected commit failure"):
                        extractor.extract_from_pdf(str(pdf_path))

                export_sync.assert_not_called()
                document.close.assert_called_once_with()
                self.assertEqual(old_export.read_bytes(), b"old-export")
                self.assertEqual(old_manifest.read_bytes(), b"old-manifest")
                for path, payload in zip(old_run_paths, old_run_payloads):
                    self.assertEqual(path.read_bytes(), payload)
                self.assertEqual(set(written), {"figure", "batch", "raw"})
                for path in written.values():
                    self.assertFalse(path.exists(), path)
                self.assertEqual(extractor.db_conn.execute("SELECT COUNT(*) FROM pdf_files").fetchone()[0], 0)
            finally:
                extractor.close()

    def test_export_failure_is_partial_success_and_resume_retries_projection_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "paper.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\nprojection retry\n%%EOF\n")
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
                resume_completed_pdfs=True,
            )
            try:
                file_hash = extractor._calculate_file_hash(pdf_path)
                document = MagicMock()
                document.__len__.return_value = 0
                part_result = PartExtractionResult(
                    status="skipped",
                    reason="fixture",
                    block_labels=[
                        {
                            "file_name": pdf_path.name,
                            "file_path": str(pdf_path),
                            "file_hash": file_hash,
                            "block_ref": "p001_b0000",
                            "page_number": 1,
                            "block_index": 0,
                            "text_content": "fixture",
                        }
                    ],
                )

                recovery_dir = root / "projection-recovery"
                recovery_dir.mkdir()
                projection_failure = ImportReadyProjectionRecoveryRequired(
                    "injected export failure",
                    recovery_dir,
                )
                with patch("core.pdf_processor.pdf_extractor.fitz.open", return_value=document), patch.object(
                    extractor,
                    "_extract_document_text_blocks",
                    return_value=[],
                ), patch.object(
                    extractor,
                    "_extract_text_part_descriptions",
                    return_value=part_result,
                ), patch.object(
                    extractor,
                    "_sync_import_ready_figure_exports",
                    side_effect=projection_failure,
                ):
                    first_result = extractor.extract_from_pdf(str(pdf_path))

                self.assertEqual(first_result["status"], "partial_success")
                self.assertEqual(first_result["stats"]["import_ready_export_status"], "error")
                self.assertIn("injected export failure", first_result["stats"]["import_ready_export_error"])
                self.assertEqual(
                    first_result["stats"]["import_ready_recovery_directory"],
                    str(recovery_dir.resolve()),
                )
                self.assertEqual(
                    extractor.db_conn.execute("SELECT COUNT(*) FROM pdf_files").fetchone()[0],
                    1,
                )
                document.close.assert_called_once_with()

                successful_export = {
                    "accepted_exported_figures": 0,
                    "review_exported_figures": 0,
                    "import_ready_export_status": "success",
                    "import_ready_export_error": "",
                }
                with patch("core.pdf_processor.pdf_extractor.fitz.open") as fitz_open, patch.object(
                    extractor,
                    "_sync_import_ready_figure_exports",
                    return_value=successful_export,
                ) as export_sync:
                    resumed_result = extractor.extract_from_pdf(str(pdf_path))

                fitz_open.assert_not_called()
                export_sync.assert_called_once_with(first_result["file_id"])
                self.assertEqual(resumed_result["status"], "skipped_existing")
                self.assertTrue(resumed_result["stats"]["resumed_skip"])
                self.assertEqual(resumed_result["stats"]["import_ready_export_status"], "success")
            finally:
                extractor.close()

    def test_resume_with_missing_source_image_runs_full_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "paper.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\nmissing source retry\n%%EOF\n")
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
                resume_completed_pdfs=True,
            )
            try:
                file_hash = extractor._calculate_file_hash(pdf_path)
                cursor = extractor.db_conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO pdf_files (file_path, file_name, file_hash, total_pages, file_size)
                    VALUES (?, ?, ?, 1, ?)
                    """,
                    (str(pdf_path), pdf_path.name, file_hash, pdf_path.stat().st_size),
                )
                old_file_id = int(cursor.lastrowid)
                cursor.execute(
                    """
                    INSERT INTO figure_records (
                        pdf_file_id, page_number, figure_index, candidate_id, figure_hash,
                        figure_bbox, image_file_path, image_file_name, accepted, review_status
                    ) VALUES (?, 1, 1, 'candidate-1', 'missing', '{}', ?, 'missing.png', 1, 'accepted')
                    """,
                    (old_file_id, str(root / "missing.png")),
                )
                cursor.execute(
                    """
                    INSERT INTO extraction_stats (
                        pdf_file_id, total_candidates, accepted_figures, rejected_figures,
                        review_queue_figures, multimodal_validated_figures
                    ) VALUES (?, 1, 1, 0, 0, 0)
                    """,
                    (old_file_id,),
                )
                extractor.db_conn.commit()

                document = MagicMock()
                document.__len__.return_value = 0
                part_result = PartExtractionResult(status="skipped", reason="fixture")
                persisted_stats = {
                    "total_figures": 0,
                    "accepted_figures": 0,
                    "rejected_figures": 0,
                    "review_queue_figures": 0,
                    "part_description_records": 0,
                }
                projection_stats = {
                    "accepted_exported_figures": 0,
                    "review_exported_figures": 0,
                    "import_ready_export_status": "success",
                    "import_ready_export_error": "",
                }
                with patch("core.pdf_processor.pdf_extractor.fitz.open", return_value=document) as fitz_open, patch.object(
                    extractor, "_extract_document_text_blocks", return_value=[]
                ), patch.object(
                    extractor, "_extract_text_part_descriptions", return_value=part_result
                ), patch.object(
                    extractor, "_persist_pdf_results", return_value=persisted_stats
                ), patch.object(
                    extractor, "_sync_import_ready_figure_exports", return_value=projection_stats
                ):
                    result = extractor.extract_from_pdf(str(pdf_path))

                self.assertEqual(result["status"], "success")
                self.assertNotEqual(result["file_id"], old_file_id)
                fitz_open.assert_called_once_with(str(pdf_path))
                document.close.assert_called_once_with()
                self.assertEqual(
                    extractor.db_conn.execute("SELECT COUNT(*) FROM pdf_files").fetchone()[0],
                    1,
                )
            finally:
                extractor.close()

    def test_agentic_extract_figures_marks_projection_failure_partial(self):
        from tools.agentic import extract_figures

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "pdfs"
            source_dir.mkdir()
            (source_dir / "paper.pdf").write_bytes(b"fixture")
            run_index_path = root / "run-index.json"
            recovery_dir = str((root / "projection-recovery").resolve())

            class FakeExtractor:
                def __init__(self, **_kwargs):
                    pass

                def extract_from_pdf(self, _pdf_path):
                    return {
                        "status": "partial_success",
                        "file_id": 7,
                        "stats": {
                            "import_ready_export_status": "error",
                            "import_ready_export_error": "PermissionError: locked export",
                            "import_ready_recovery_directory": recovery_dir,
                        },
                    }

                def close(self):
                    pass

            argv = [
                "extract_figures.py",
                "--pdf-source-dir",
                str(source_dir),
                "--db",
                str(root / "literature.db"),
                "--run-index",
                str(run_index_path),
            ]
            with patch.object(sys, "argv", argv), patch(
                "core.pdf_processor.pdf_extractor.EnhancedPDFExtractionSystem",
                FakeExtractor,
            ):
                return_code = extract_figures.main()

            payload = json.loads(run_index_path.read_text(encoding="utf-8"))
            self.assertEqual(return_code, 2)
            self.assertEqual(payload["status"], "partial")
            self.assertEqual(payload["summary"]["successful_pdfs"], 0)
            self.assertEqual(payload["summary"]["partial_pdfs"], 1)
            self.assertEqual(payload["summary"]["failed_pdfs"], 0)
            self.assertEqual(payload["summary"]["database_committed_pdfs"], 1)
            item = payload["results"][0]
            self.assertFalse(item["ok"])
            self.assertEqual(item["status"], "failed_projection")
            self.assertTrue(item["database_committed"])
            self.assertEqual(item["error"], "PermissionError: locked export")
            self.assertEqual(item["import_ready_recovery_directory"], recovery_dir)
            self.assertEqual(item["result"]["file_id"], 7)

    def test_agentic_extract_figures_keeps_success_and_resume_statuses_passed(self):
        from tools.agentic import extract_figures

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "pdfs"
            source_dir.mkdir()
            (source_dir / "a.pdf").write_bytes(b"a")
            (source_dir / "b.pdf").write_bytes(b"b")
            run_index_path = root / "run-index.json"

            captured_kwargs = {}

            class FakeExtractor:
                def __init__(self, **kwargs):
                    captured_kwargs.update(kwargs)
                    self.calls = 0

                def extract_from_pdf(self, _pdf_path):
                    statuses = ("success", "skipped_existing")
                    status = statuses[self.calls]
                    self.calls += 1
                    return {"status": status, "file_id": self.calls, "stats": {}}

                def close(self):
                    pass

            argv = [
                "extract_figures.py",
                "--pdf-source-dir",
                str(source_dir),
                "--db",
                str(root / "literature.db"),
                "--run-index",
                str(run_index_path),
            ]
            with patch.object(sys, "argv", argv), patch(
                "core.pdf_processor.pdf_extractor.EnhancedPDFExtractionSystem",
                FakeExtractor,
            ):
                return_code = extract_figures.main()

            payload = json.loads(run_index_path.read_text(encoding="utf-8"))
            self.assertEqual(return_code, 0)
            self.assertEqual(payload["status"], "passed")
            self.assertEqual(payload["summary"]["successful_pdfs"], 2)
            self.assertEqual(payload["summary"]["partial_pdfs"], 0)
            self.assertEqual(payload["summary"]["failed_pdfs"], 0)
            self.assertEqual(
                [item["status"] for item in payload["results"]],
                ["success", "skipped_existing"],
            )
            self.assertTrue(all(item["ok"] for item in payload["results"]))
            self.assertTrue(captured_kwargs["save_images_to_files"])
            self.assertTrue(captured_kwargs["resume_completed_pdfs"])

    def test_stale_audit_cleanup_permission_error_is_warning_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                scope = extractor._pdf_artifact_scope(
                    file_name="paper.pdf",
                    file_path=str(root / "paper.pdf"),
                )
                stale_paths = (
                    extractor.figures_dir / f"{scope}_p001_f001_old_11111111.png",
                    extractor.batch_dir / f"{scope}_batch_0002.json",
                    extractor.batch_raw_dir / f"{scope}_batch_0002_fallback.txt",
                )
                for path in stale_paths:
                    if path.suffix == ".png":
                        path.write_bytes(b"old")
                    else:
                        path.write_text("old", encoding="utf-8")
                extractor.logger = Mock()

                with patch.object(Path, "unlink", side_effect=PermissionError("locked")):
                    extractor._cleanup_stale_scoped_audit_artifacts(
                        scope=scope,
                        figure_names=set(),
                        batch_manifest_names=set(),
                        raw_response_names=set(),
                    )

                for path in stale_paths:
                    self.assertTrue(path.exists(), path)
                self.assertEqual(extractor.logger.warning.call_count, 3)
            finally:
                extractor.close()

    def test_failed_run_cleanup_permission_error_is_warning_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extractor = EnhancedPDFExtractionSystem(
                output_db_path=str(root / "literature.db"),
                save_images_to_files=True,
                enable_multimodal_validation=False,
            )
            try:
                base_scope = extractor._pdf_artifact_scope(
                    file_name="paper.pdf",
                    file_path=str(root / "paper.pdf"),
                )
                run_scope = f"{base_scope}_run_failed00000"
                paths = (
                    extractor.figures_dir / f"{run_scope}_p001_f001_failed.png",
                    extractor.batch_dir / f"{run_scope}_batch_0001.json",
                    extractor.batch_raw_dir / f"{run_scope}_batch_0001.txt",
                )
                for path in paths:
                    path.write_bytes(b"failed-run")
                extractor.logger = Mock()

                with patch.object(Path, "unlink", side_effect=PermissionError("locked")):
                    extractor._cleanup_failed_pdf_run_artifacts(
                        run_scope=run_scope,
                        figure_names={paths[0].name},
                        batch_manifest_names={paths[1].name},
                        raw_response_names={paths[2].name},
                    )

                for path in paths:
                    self.assertTrue(path.exists(), path)
                self.assertEqual(extractor.logger.warning.call_count, 3)
            finally:
                extractor.close()


if __name__ == "__main__":
    unittest.main()
