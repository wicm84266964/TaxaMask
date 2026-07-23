import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from AntSleap.core.training_run_notes import (
    TrainingRunNoteError,
    TrainingRunNoteStore,
)
from AntSleap.core.training_run_recorder import TrainingRunRecorder


class TrainingRunNoteStoreTests(unittest.TestCase):
    def test_note_is_bound_to_run_and_edit_does_not_modify_run_record(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending("notes_test")
            run.cancel()
            run_path = Path(run.record_path)
            before_bytes = run_path.read_bytes()
            before_mtime = run_path.stat().st_mtime_ns

            store = TrainingRunNoteStore(tmp_dir)
            first = store.save(
                run.run_id,
                purpose="Check whether a new preprocessing setting helps.",
                importance="important",
                conclusion="Keep for comparison.",
            )
            second = store.update(
                run.run_id,
                conclusion="Useful baseline.",
                follow_up="Compare with the next run.",
                expected_updated_at=first["updated_at"],
            )

            self.assertEqual(first["note_ref"], run.note_ref)
            self.assertEqual(second["run_id"], run.run_id)
            self.assertEqual(second["purpose"], first["purpose"])
            self.assertEqual(second["conclusion"], "Useful baseline.")
            self.assertTrue(store.has_note(run.run_id))
            self.assertEqual(run_path.read_bytes(), before_bytes)
            self.assertEqual(run_path.stat().st_mtime_ns, before_mtime)

    def test_note_store_rejects_orphan_and_private_material(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = TrainingRunNoteStore(tmp_dir)
            with self.assertRaisesRegex(TrainingRunNoteError, "note_orphan"):
                store.save("train_20260718T000000000000Z_deadbeef", note="orphan")

            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending("notes_test")
            run.cancel()
            with self.assertRaisesRegex(ValueError, "absolute_path"):
                store.save(run.run_id, note="See C:/Users/researcher/private.txt")
            with self.assertRaisesRegex(ValueError, "secret"):
                store.save(run.run_id, note="api_key=do-not-store")
            with self.assertRaisesRegex(ValueError, "secret"):
                store.save(run.run_id, note="Bearer abcdefghijklmnop")
            private_paths = (
                "See(C:/Users/researcher/private.txt)",
                "复核记录（路径：C:/Users/researcher/private.txt）",
                "复核记录：/home/researcher/private.txt",
                "复核记录【\\\\server\\private\\notes.txt】",
                "路径…/home/researcher/private.txt",
                "路径·\\\\server\\private\\notes.txt",
                "路径…C:\\Users\\researcher\\private.txt",
                "路径_/home/researcher/private.txt",
            )
            for private_path in private_paths:
                with self.subTest(private_path=private_path), self.assertRaisesRegex(
                    ValueError, "absolute_path"
                ):
                    store.save(run.run_id, note=private_path)
            saved = store.save(
                run.run_id,
                note=(
                    "比较 Head/Thorax 比例（C: dorsal；样本 01-02）；"
                    "参考 https://doi.org/10.1234/example"
                ),
            )
            self.assertIn("Head/Thorax", saved["note"])
            self.assertIn("https://doi.org", saved["note"])

    def test_clearing_note_keeps_binding_but_reports_no_content(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending("notes_test")
            run.cancel()
            store = TrainingRunNoteStore(tmp_dir)
            store.save(run.run_id, note="temporary")
            current = store.load(run.run_id)
            cleared = store.save(
                run.run_id, note="", expected_updated_at=current["updated_at"]
            )
            self.assertFalse(cleared["has_content"])
            self.assertFalse(store.has_note(run.run_id))
            self.assertEqual(cleared["note_ref"], run.note_ref)

    def test_note_compare_and_swap_rejects_stale_edit_and_lock_contention(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending("notes_test")
            run.cancel()
            first_store = TrainingRunNoteStore(tmp_dir)
            second_store = TrainingRunNoteStore(tmp_dir)
            first = first_store.save(run.run_id, note="first")
            with self.assertRaisesRegex(TrainingRunNoteError, "note_conflict"):
                second_store.save(run.run_id, note="stale")
            updated = second_store.save(
                run.run_id,
                note="second",
                expected_updated_at=first["updated_at"],
            )
            self.assertEqual(updated["note"], "second")
            with first_store._activity_guard(run.run_id):
                with self.assertRaisesRegex(TrainingRunNoteError, "note_busy"):
                    second_store.save(
                        run.run_id,
                        note="busy",
                        expected_updated_at=updated["updated_at"],
                    )

    def test_note_load_ignores_corrupted_json_projection(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending("notes_test")
            run.cancel()
            store = TrainingRunNoteStore(tmp_dir)
            saved = store.save(run.run_id, note="safe")
            path = store.path_for_run(run.run_id)
            saved["api_key"] = "must-not-load"
            path.write_text(json.dumps(saved), encoding="utf-8")
            loaded = store.load(run.run_id)
            self.assertEqual(loaded["note"], "safe")
            self.assertNotIn("api_key", loaded)

    def test_note_projection_symlink_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending("notes_test")
            run.cancel()
            store = TrainingRunNoteStore(tmp_dir)
            store.save(run.run_id, note="safe")
            note_path = store.path_for_run(run.run_id)
            outside = Path(tmp_dir) / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            note_path.unlink()
            try:
                note_path.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("This workstation cannot create symlinks")
            loaded = store.load(run.run_id)
            self.assertEqual(loaded["note"], "safe")

    def test_note_load_rejects_invalid_sqlite_record(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending("notes_test")
            run.cancel()
            store = TrainingRunNoteStore(tmp_dir)
            saved = store.save(run.run_id, note="safe")
            saved["api_key"] = "must-not-load"
            connection = sqlite3.connect(store.database_path)
            try:
                with connection:
                    connection.execute(
                        "UPDATE training_run_notes SET note_json = ? WHERE run_id = ?",
                        (json.dumps(saved), run.run_id),
                    )
            finally:
                connection.close()
            with self.assertRaisesRegex(ValueError, "training_run_note_invalid"):
                store.load(run.run_id)


if __name__ == "__main__":
    unittest.main()
