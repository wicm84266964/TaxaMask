import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import tifffile

from AntSleap.core.amira_import import (
    decode_hxbyterle,
    import_amira_directory,
    parse_materials_from_labels_header,
    read_amira_volume,
    resolve_amira_files,
)
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import load_volume_sidecar


def encode_hxbyterle_repeat_only(values):
    encoded = bytearray()
    index = 0
    flat = list(values)
    while index < len(flat):
        value = flat[index]
        run = 1
        while index + run < len(flat) and flat[index + run] == value and run < 127:
            run += 1
        encoded.append(run)
        encoded.append(value)
        index += run
    return bytes(encoded)


def write_amira_file(path, array_zyx, *, materials_header="", encoding="", dtype_name="byte"):
    z, y, x = array_zyx.shape
    data = np.asarray(array_zyx).reshape(-1)
    if encoding == "HxByteRLE":
        data_bytes = encode_hxbyterle_repeat_only(data)
        data_decl = f"Lattice {{ {dtype_name} Data }} @1(HxByteRLE,{len(data_bytes)})"
    elif encoding:
        data_bytes = data.astype(np.uint8).tobytes()
        data_decl = f"Lattice {{ {dtype_name} Data }} @1({encoding},{len(data_bytes)})"
    else:
        data_bytes = data.astype(np.uint8).tobytes()
        data_decl = f"Lattice {{ {dtype_name} Data }} @1"
    header = f"""# AmiraMesh BINARY-LITTLE-ENDIAN 3.0


define Lattice {x} {y} {z}

Parameters {{
    {materials_header}
    Units {{
        Coordinates "um"
    }}
    Content "{x}x{y}x{z} byte, uniform coordinates",
    BoundingBox 0 {x - 1} 0 {y - 1} 0 {z - 1},
    CoordType "uniform"
}}

{data_decl}

# Data section follows
@1
"""
    with open(path, "wb") as handle:
        handle.write(header.encode("latin1"))
        handle.write(data_bytes)


def write_material_statistics(path):
    text = """# AmiraMesh 3D ASCII 3.0

@1
Table0000Column0001 { byte Table0000Column0001 } @2
Table0000Column0002 { int Table0000Column0002 } @3
Table0000Column0003 { uint64 Table0000Column0003 } @4

# Data section follows
@1
1
2
3

@2
69
120
116
101
114
105
111
114
0
76
79
95
76
0
77
69
95
76
0

@3
0
3
4

@4
12
5
6
"""
    path.write_text(text, encoding="latin1")


class AmiraImportTests(unittest.TestCase):
    def test_hxbyterle_decode_matches_expected_size(self):
        values = [0, 0, 0, 3, 3, 4, 4, 4, 4]
        decoded = decode_hxbyterle(encode_hxbyterle_repeat_only(values), len(values), dtype=np.uint8)
        self.assertEqual(decoded.tolist(), values)

    def test_materials_parse_from_labels_header(self):
        materials = parse_materials_from_labels_header(
            """
Parameters {
    Materials {
        Exterior {
            Color 0.7 0.8 0.8,
        }
        LO_L {
            Id 3,
            Color 1 0.426 0,
            Lock "true"
        }
    }
}
"""
        )
        self.assertEqual(materials[0]["name"], "Exterior")
        self.assertEqual(materials[1]["id"], 3)
        self.assertEqual(materials[1]["color"], "#ff6d00")

    def test_amira_directory_import_uses_resampled_and_creates_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "amira"
            source.mkdir()
            resampled = np.arange(2 * 3 * 4, dtype=np.uint8).reshape((2, 3, 4))
            labels = np.zeros((2, 3, 4), dtype=np.uint8)
            labels[:, 1:, 1:] = 3

            materials_header = """
Materials {
    Exterior {
        Color 0.7 0.8 0.8,
    }
    LO_L {
        Id 3,
        Color 1 0.426 0,
        Lock "true"
    }
    ME_L {
        Id 4,
        Color 1 0.426 0,
        Lock "true"
    }
}
"""
            write_amira_file(source / "sample.resampled", resampled, materials_header="", encoding="")
            write_amira_file(source / "sample(1).labels", labels, materials_header=materials_header, encoding="HxByteRLE")
            tifffile.imwrite(source / "raw.tif", np.zeros((3, 5, 6), dtype=np.uint8), photometric="minisblack")
            write_material_statistics(source / "sample(1).MaterialStatistics")
            (source / "sample.surf").write_bytes(b"surf")
            (source / "sample.hx").write_text(
                """
[ load "${SCRIPTDIR}/sample.resampled" ] setLabel "sample.resampled"
[ load "${SCRIPTDIR}/sample.labels" ] setLabel "sample.labels"
"sample.labels" ImageData connect "sample.resampled"
""",
                encoding="latin1",
            )

            manager = TifProjectManager()
            manager.create_project("amira_project", root / "project")
            result = import_amira_directory(manager, source, "01-0101-07", copy_source=True)
            specimen = manager.get_specimen("01-0101-07")
            readiness = manager.evaluate_train_ready("01-0101-07")

            self.assertTrue(readiness["train_ready"])
            self.assertEqual(specimen["working_volume"]["shape_zyx"], [2, 3, 4])
            self.assertEqual(specimen["labels"]["manual_truth"]["shape_zyx"], [2, 3, 4])
            self.assertEqual(result["report"]["alignment"]["labels_aligned_to"], "resampled")
            self.assertIn("raw_tif_shape_differs_from_labels_shape", result["report"]["warnings"])
            np.testing.assert_array_equal(load_volume_sidecar(manager.to_absolute(specimen["working_volume"]["path"])), resampled)
            np.testing.assert_array_equal(load_volume_sidecar(manager.to_absolute(specimen["labels"]["manual_truth"]["path"])), labels)
            self.assertTrue((Path(manager.project_dir) / specimen["source"]["amira_labels"]).exists())

    def test_resolve_amira_files_matches_hx_reference_with_numbered_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            (source / "sample.hx").write_text('"sample.labels" ImageData connect "sample.resampled"', encoding="latin1")
            (source / "sample(1).labels").write_bytes(b"")
            (source / "sample.resampled").write_bytes(b"")

            resolved = resolve_amira_files(source)

            self.assertTrue(resolved["labels"].endswith("sample(1).labels"))
            self.assertTrue(resolved["resampled"].endswith("sample.resampled"))

    def test_read_amira_volume_plain_file_uses_zyx_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plain.resampled"
            array = np.arange(2 * 3 * 4, dtype=np.uint8).reshape((2, 3, 4))
            write_amira_file(path, array, encoding="")

            loaded, header = read_amira_volume(path)

            self.assertEqual(header["lattice_xyz"], [4, 3, 2])
            self.assertEqual(header["shape_zyx"], [2, 3, 4])
            np.testing.assert_array_equal(loaded, array)

    def test_failed_amira_decode_does_not_leave_half_registered_specimen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "amira_broken"
            source.mkdir()
            resampled = np.zeros((2, 3, 4), dtype=np.uint8)
            labels = np.zeros((2, 3, 4), dtype=np.uint8)
            write_amira_file(source / "sample.resampled", resampled, encoding="")
            write_amira_file(source / "sample.labels", labels, encoding="UnsupportedEncoding")
            (source / "sample.hx").write_text(
                '"sample.labels" ImageData connect "sample.resampled"',
                encoding="latin1",
            )

            manager = TifProjectManager()
            manager.create_project("amira_broken_project", root / "project")

            with self.assertRaisesRegex(ValueError, "unsupported_amira_encoding"):
                import_amira_directory(manager, source, "01-0101-broken")

            self.assertIsNone(manager.get_specimen("01-0101-broken", default=None))
            self.assertEqual(manager.project_data["specimens"], [])

    def test_failed_amira_sidecar_write_rolls_back_registered_specimen_and_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "amira_write_fail"
            source.mkdir()
            resampled = np.zeros((2, 3, 4), dtype=np.uint8)
            labels = np.zeros((2, 3, 4), dtype=np.uint8)
            write_amira_file(source / "sample.resampled", resampled, encoding="")
            write_amira_file(source / "sample.labels", labels, encoding="")
            (source / "sample.hx").write_text(
                '"sample.labels" ImageData connect "sample.resampled"',
                encoding="latin1",
            )

            manager = TifProjectManager()
            manager.create_project("amira_write_fail_project", root / "project")

            with patch("AntSleap.core.amira_import.write_volume_sidecar", side_effect=RuntimeError("disk write failed")):
                with self.assertRaisesRegex(RuntimeError, "disk write failed"):
                    import_amira_directory(manager, source, "01-0101-writefail")

            self.assertIsNone(manager.get_specimen("01-0101-writefail", default=None))
            self.assertFalse((Path(manager.project_dir) / "specimens" / "01-0101-writefail").exists())


if __name__ == "__main__":
    unittest.main()
