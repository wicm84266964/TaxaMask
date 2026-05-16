import tempfile
import unittest
from pathlib import Path

from AntSleap.core.pdf_evidence import add_pdf_evidence_record, read_pdf_evidence_index
from AntSleap.core.specimen_linkage import build_specimen_linkage
from AntSleap.core.stl_project import StlRenderedProjectManager
from AntSleap.core.tif_project import TifProjectManager


class SpecimenLinkageAndPdfEvidenceTests(unittest.TestCase):
    def test_cross_project_specimen_linkage_uses_metadata_ref_or_specimen_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tif = TifProjectManager()
            tif_path = tif.create_project("tif", root / "tif")
            tif.create_specimen_scaffold("01-0101-02", metadata_ref="master:01-0101-02")
            stl = StlRenderedProjectManager()
            stl_path = stl.create_project("stl", root / "stl")
            stl.project_data["specimens"].append(
                {
                    "specimen_id": "01_0101_02",
                    "display_name": "01_0101_02",
                    "metadata_ref": "master:01-0101-02",
                    "views": {},
                }
            )
            stl.save_project()

            report = build_specimen_linkage([tif_path, stl_path])
            self.assertEqual(report["schema_version"], "ant3d_specimen_linkage_v1")
            self.assertEqual(len(report["groups"]), 1)
            self.assertTrue(report["groups"][0]["cross_project"])
            self.assertEqual(len(report["groups"][0]["entries"]), 2)

    def test_pdf_evidence_index_is_lightweight_and_specimen_linkable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence" / "pdf_evidence_index.json"
            payload = add_pdf_evidence_record(
                path,
                {
                    "source_pdf": "paper.pdf",
                    "page": 12,
                    "caption": "Figure evidence",
                    "specimen_id": "01-0101-02",
                    "metadata_ref": "master:01-0101-02",
                },
            )
            self.assertEqual(payload["schema_version"], "ant3d_pdf_evidence_index_v1")
            reloaded = read_pdf_evidence_index(path)
            self.assertEqual(len(reloaded["records"]), 1)
            self.assertEqual(reloaded["records"][0]["specimen_id"], "01-0101-02")


if __name__ == "__main__":
    unittest.main()
