import hashlib
import os
import stat
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from AntSleap.core.file_integrity import (
    FingerprintCancelled,
    FingerprintIncomplete,
    QUICK_FILE_ALGORITHM,
    TREE_ALGORITHM,
    UnsupportedFingerprintAlgorithm,
    compute_fingerprint,
)


class FileIntegrityTests(unittest.TestCase):
    def test_full_file_sha256_is_chunked_and_reports_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "volume.bin"
            payload = bytes(range(251)) * 19
            path.write_bytes(payload)
            events = []

            result = compute_fingerprint(
                path,
                chunk_size=97,
                progress_callback=lambda done, total: events.append((done, total)),
            )

            self.assertEqual(result["entry_kind"], "file")
            self.assertEqual(result["size_bytes"], len(payload))
            self.assertEqual(result["hash_algorithm"], "sha256")
            self.assertEqual(result["digest"], hashlib.sha256(payload).hexdigest())
            self.assertIsInstance(result["mtime_ns"], int)
            self.assertEqual(events[0], (0, len(payload)))
            self.assertEqual(events[-1], (len(payload), len(payload)))
            self.assertGreater(len(events), 3)
            self.assertNotIn("path", result)

    def test_empty_file_has_standard_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.bin"
            path.write_bytes(b"")
            result = compute_fingerprint(path)
            self.assertEqual(result["size_bytes"], 0)
            self.assertEqual(result["digest"], hashlib.sha256(b"").hexdigest())

    def test_quick_fingerprint_uses_versioned_algorithm_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large-ct.bin"
            path.write_bytes(b"A" * (3 * 1024 * 1024 + 137))
            by_alias = compute_fingerprint(path, "quick_fingerprint", chunk_size=65536)
            by_name = compute_fingerprint(path, QUICK_FILE_ALGORITHM, chunk_size=131072)

            self.assertEqual(by_alias["hash_algorithm"], QUICK_FILE_ALGORITHM)
            self.assertEqual(by_alias["digest"], by_name["digest"])
            self.assertNotEqual(
                by_alias["digest"], hashlib.sha256(path.read_bytes()).hexdigest()
            )

    def test_cancel_never_returns_a_partial_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cancel.bin"
            path.write_bytes(b"0123456789" * 1000)
            calls = 0

            def cancel_check():
                nonlocal calls
                calls += 1
                return calls >= 3

            with self.assertRaises(FingerprintCancelled) as caught:
                compute_fingerprint(path, chunk_size=64, cancel_check=cancel_check)
            self.assertEqual(caught.exception.code, "user_cancelled")

    def test_missing_source_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                compute_fingerprint(Path(tmp) / "missing.bin")

    def test_same_content_keeps_digest_after_file_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "original.bin"
            moved = Path(tmp) / "moved.bin"
            original.write_bytes(b"stable research volume")
            before = compute_fingerprint(original)
            original.replace(moved)
            after = compute_fingerprint(moved)
            self.assertEqual(before["digest"], after["digest"])
            self.assertEqual(before["size_bytes"], after["size_bytes"])

    def test_read_failure_has_explicit_incomplete_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "denied.bin"
            path.write_bytes(b"private")
            with patch(
                "AntSleap.core.file_integrity._open_binary_nofollow",
                side_effect=PermissionError("denied"),
            ):
                with self.assertRaises(FingerprintIncomplete) as raised:
                    compute_fingerprint(path)
            self.assertEqual(raised.exception.code, "source_read_failed")

    def test_tree_digest_matches_frozen_byte_framing_and_keeps_empty_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tree"
            (root / "empty").mkdir(parents=True)
            (root / "sub").mkdir()
            (root / "a.txt").write_bytes(b"A")
            (root / "sub" / "b.bin").write_bytes(b"BC")

            expected = hashlib.sha256()
            expected.update(b"taxamask-sha256-tree-v1\0")
            records = [
                (b"F", b"a.txt", b"A"),
                (b"D", b"empty", b""),
                (b"D", b"sub", b""),
                (b"F", b"sub/b.bin", b"BC"),
            ]
            for kind, relative_path, content in records:
                expected.update(kind)
                expected.update(struct.pack(">Q", len(relative_path)))
                expected.update(relative_path)
                expected.update(struct.pack(">Q", len(content)))
                expected.update(content)

            result = compute_fingerprint(root)
            self.assertEqual(result["entry_kind"], "directory")
            self.assertEqual(result["hash_algorithm"], TREE_ALGORITHM)
            self.assertEqual(result["size_bytes"], 3)
            self.assertEqual(result["digest"], expected.hexdigest())

    def test_empty_tree_is_hash_of_fixed_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = compute_fingerprint(tmp)
            expected = hashlib.sha256(b"taxamask-sha256-tree-v1\0").hexdigest()
            self.assertEqual(result["digest"], expected)
            self.assertEqual(result["size_bytes"], 0)

    def test_mtime_is_not_part_of_file_or_tree_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tree"
            root.mkdir()
            member = root / "member.bin"
            member.write_bytes(b"same content")
            file_before = compute_fingerprint(member)
            tree_before = compute_fingerprint(root)
            stat_result = member.stat()
            os.utime(
                member,
                ns=(stat_result.st_atime_ns, stat_result.st_mtime_ns + 2_000_000_000),
            )
            file_after = compute_fingerprint(member)
            tree_after = compute_fingerprint(root)
            self.assertEqual(file_before["digest"], file_after["digest"])
            self.assertEqual(tree_before["digest"], tree_after["digest"])

    def test_tree_rejects_symlink_instead_of_following_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tree"
            root.mkdir()
            target = Path(tmp) / "target.bin"
            target.write_bytes(b"private")
            link = root / "linked.bin"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("This workstation cannot create test symlinks")
            with self.assertRaises(FingerprintIncomplete) as caught:
                compute_fingerprint(root)
            self.assertEqual(caught.exception.code, "unsupported_entry_type")

    def test_root_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            link = Path(tmp) / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("This workstation cannot create test symlinks")
            with self.assertRaises(FingerprintIncomplete):
                compute_fingerprint(link)

    def test_algorithm_kind_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tree"
            root.mkdir()
            file_path = Path(tmp) / "file.bin"
            file_path.write_bytes(b"x")
            with self.assertRaises(UnsupportedFingerprintAlgorithm):
                compute_fingerprint(root, "sha256")
            with self.assertRaises(UnsupportedFingerprintAlgorithm):
                compute_fingerprint(file_path, TREE_ALGORITHM)

    def test_invalid_chunk_size_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.bin"
            path.write_bytes(b"x")
            with self.assertRaises(ValueError):
                compute_fingerprint(path, chunk_size=0)

    def test_coarse_integer_mtime_is_not_treated_as_high_precision(self):
        from AntSleap.core.file_integrity import _metadata

        common = {
            "st_mode": stat.S_IFREG | 0o600,
            "st_size": 1,
            "st_mtime": 1784379000.0,
            "st_dev": 3,
            "st_ino": 7,
            "st_file_attributes": 0,
        }
        coarse = _metadata(
            SimpleNamespace(st_mtime_ns=1784379000000000000, **common)
        )
        precise = _metadata(
            SimpleNamespace(st_mtime_ns=1784379000000000123, **common)
        )
        self.assertFalse(coarse.reliable)
        self.assertTrue(precise.reliable)


if __name__ == "__main__":
    unittest.main()
