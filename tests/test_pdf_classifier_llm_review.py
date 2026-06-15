import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import shutil


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

sys.modules.setdefault("fitz", types.SimpleNamespace(Rect=object, Document=object, Page=object))

from core.pdf_processor.pdf_classifier import LLMScreenPDFClassifier  # noqa: E402


class PdfClassifierLlmReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = REPO_ROOT / ".tmp_validation" / "pdf_classifier_llm_review"
        self.source_dir = self.tmp_root / "source"
        self.output_dir = self.tmp_root / "output"
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)

    def test_llm_review_uses_model_response_instead_of_test_filename_shortcut(self):
        classifier = LLMScreenPDFClassifier(
            source_folder=str(self.source_dir),
            output_folder=str(self.output_dir),
            api_key="test-key",
        )
        classifier.client = object()

        with patch.object(
            classifier,
            "_call_llm",
            return_value=("判断：否\n理由：不是目标分类群的新种描述。", "stop", "chat_completions"),
        ) as call_llm:
            approved, reason = classifier.llm_review_new_species_report(
                "Taxonomy paper text.",
                "test_new_species.pdf",
            )

        self.assertFalse(approved)
        self.assertIn("判断：否", reason)
        call_llm.assert_called_once()

    def test_llm_review_accepts_positive_mocked_model_response(self):
        classifier = LLMScreenPDFClassifier(
            source_folder=str(self.source_dir),
            output_folder=str(self.output_dir),
            api_key="test-key",
        )
        classifier.client = object()

        with patch.object(
            classifier,
            "_call_llm",
            return_value=("判断：是\n理由：明确包含蚂蚁新种描述。", "stop", "chat_completions"),
        ):
            approved, reason = classifier.llm_review_new_species_report(
                "Formica clara sp. nov. Diagnosis and type material.",
                "ordinary_filename.pdf",
            )

        self.assertTrue(approved)
        self.assertIn("判断：是", reason)


if __name__ == "__main__":
    unittest.main()
