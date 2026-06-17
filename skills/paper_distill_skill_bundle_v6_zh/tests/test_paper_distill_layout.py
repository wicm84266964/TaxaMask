from __future__ import annotations

import unittest
from pathlib import Path

from app.paper_distill.layout import (
    build_paper_id,
    build_source_hash,
    extract_title,
    normalize_markdown_source,
)


class PaperDistillLayoutTests(unittest.TestCase):
    def test_normalization_hash_and_title_are_stable(self) -> None:
        raw_source = "# Sample Paper\r\n\r\nLine one.  \r\nLine two.\r\n"
        normalized = normalize_markdown_source(raw_source)

        self.assertEqual(normalized, "# Sample Paper\n\nLine one.\nLine two.\n")
        self.assertEqual(extract_title(Path("sample_paper.md"), normalized), "Sample Paper")

        source_hash = build_source_hash(normalized)
        paper_id = build_paper_id("Sample Paper", source_hash)

        self.assertTrue(source_hash.startswith("sha256:"))
        self.assertEqual(paper_id.split("--", 1)[0], "sample-paper")


if __name__ == "__main__":
    _ = unittest.main()
