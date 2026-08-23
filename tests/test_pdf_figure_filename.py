import re
import unittest

from core.pdf_processor.pdf_extractor import EnhancedPDFExtractionSystem


class FigureFilenameTests(unittest.TestCase):
    def test_caption_whitespace_is_safe_for_windows_filename(self):
        extractor = object.__new__(EnhancedPDFExtractionSystem)
        extractor.db_conn = None

        filename = extractor._generate_figure_filename(
            "sample.pdf",
            34,
            1,
            {"text_content": "29 24\t Propodeal\nspines long"},
            "1e3fbbbb00000000",
        )

        self.assertEqual(
            filename,
            "sample_p034_f001_29_24_Propodeal_spines_long_1e3fbbbb.png",
        )
        self.assertIsNone(re.search(r"\s", filename))


if __name__ == "__main__":
    unittest.main()
