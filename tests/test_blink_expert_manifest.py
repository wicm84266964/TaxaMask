# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

import json
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.blink_expert_manifest import (
    BLINK_EXPERT_BACKEND_HEATMAP,
    BLINK_EXPERT_BACKEND_VIT_B,
    BLINK_EXPERT_MANIFEST_LEGACY_SCHEMA_VERSION,
    BLINK_EXPERT_MANIFEST_SCHEMA_VERSION,
    BLINK_EXPERT_OUTPUT_SCHEMA_HEATMAP,
    BLINK_EXPERT_OUTPUT_SCHEMA_VIT_B,
    build_blink_preprocessing_contract,
    default_manifest_path_for_weights,
    load_blink_expert_manifest,
    validate_blink_expert_contract,
    write_blink_expert_manifest,
)
from AntSleap.core.blink_trainer import BlinkExpertTrainer


class BlinkExpertManifestTests(unittest.TestCase):
    @staticmethod
    def _v2_contract(backend=BLINK_EXPERT_BACKEND_VIT_B):
        if backend == BLINK_EXPERT_BACKEND_HEATMAP:
            checkpoint_kind = "blink_heatmap_expert"
            output_schema = BLINK_EXPERT_OUTPUT_SCHEMA_HEATMAP
        else:
            checkpoint_kind = "blink_expert_locator"
            output_schema = BLINK_EXPERT_OUTPUT_SCHEMA_VIT_B
        preprocessing = build_blink_preprocessing_contract()
        manifest = {
            "schema_version": BLINK_EXPERT_MANIFEST_SCHEMA_VERSION,
            "expert_backend": backend,
            "parent_part": "Head",
            "child_part": "Mandible",
            "input_size": [224, 224],
            "output_schema": output_schema,
            "preprocessing": preprocessing,
        }
        checkpoint_meta = {
            "kind": checkpoint_kind,
            "parent_part": "Head",
            "child_part": "Mandible",
            "part_name": "Mandible",
            "input_size": [224, 224],
            "preprocessing": preprocessing,
        }
        return manifest, checkpoint_meta

    @staticmethod
    def _validate_contract(manifest, checkpoint_meta, **overrides):
        return validate_blink_expert_contract(
            manifest,
            checkpoint_meta,
            expected_backend=overrides.get(
                "expected_backend",
                manifest.get("expert_backend"),
            ),
            route_input_size=overrides.get("route_input_size", [224, 224]),
            route_parent_part=overrides.get("route_parent_part", "Head"),
            route_child_part=overrides.get("route_child_part", "Mandible"),
        )

    def test_manifest_path_sits_next_to_weights(self):
        self.assertEqual(
            default_manifest_path_for_weights("C:/models/Mandible/expert_v1.pth").replace("\\", "/"),
            "C:/models/Mandible/expert_v1.manifest.json",
        )

    def test_write_and_load_vit_b_manifest(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_path = Path(tmp_dir) / "experts" / "Mandible" / "expert_v20260602_120000.pth"
            weights_path.parent.mkdir(parents=True, exist_ok=True)
            weights_path.write_bytes(b"weights")

            manifest_path, manifest = write_blink_expert_manifest(
                str(weights_path),
                expert_backend=BLINK_EXPERT_BACKEND_VIT_B,
                parent_part="Head",
                child_part="Mandible",
                input_size=(384, 384),
                project_json="C:/project/demo.json",
                trajectory_count=12,
                train_params={"learning_rate": 0.002},
            )

            loaded = load_blink_expert_manifest(manifest_path)
            self.assertEqual(manifest["schema_version"], BLINK_EXPERT_MANIFEST_SCHEMA_VERSION)
            self.assertEqual(loaded["expert_backend"], BLINK_EXPERT_BACKEND_VIT_B)
            self.assertEqual(loaded["parent_part"], "Head")
            self.assertEqual(loaded["child_part"], "Mandible")
            self.assertEqual(loaded["input_size"], [384, 384])
            self.assertEqual(
                loaded["preprocessing"],
                build_blink_preprocessing_contract(),
            )
            self.assertEqual(loaded["weights"]["main"], weights_path.name)
            self.assertEqual(loaded["train_data"]["trajectory_count"], 12)

    def test_blink_trainer_write_manifest_uses_training_context(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_path = Path(tmp_dir) / "experts" / "Eye" / "expert_v20260602_120000.pth"
            weights_path.parent.mkdir(parents=True, exist_ok=True)
            weights_path.write_bytes(b"weights")

            trainer = BlinkExpertTrainer.__new__(BlinkExpertTrainer)
            trainer.part_name = "Eye"
            trainer.parent_part = "Head"
            trainer.project_path = str(Path(tmp_dir) / "project.json")
            trainer.learning_rate = 0.001
            trainer.weight_decay = 0.0001

            class Dataset:
                def __len__(self):
                    return 7

            manifest_path, manifest = trainer.write_manifest(str(weights_path), (224, 224), Dataset())

            self.assertTrue(Path(manifest_path).exists())
            on_disk = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(on_disk, manifest)
            self.assertEqual(on_disk["expert_backend"], BLINK_EXPERT_BACKEND_VIT_B)
            self.assertEqual(on_disk["parent_part"], "Head")
            self.assertEqual(on_disk["child_part"], "Eye")
            self.assertEqual(on_disk["train_data"]["trajectory_count"], 7)

    def test_v2_contract_binds_manifest_checkpoint_and_route_identity(self):
        for backend in (
            BLINK_EXPERT_BACKEND_VIT_B,
            BLINK_EXPERT_BACKEND_HEATMAP,
        ):
            with self.subTest(backend=backend):
                manifest, checkpoint_meta = self._v2_contract(backend)
                contract = self._validate_contract(manifest, checkpoint_meta)

                self.assertEqual(contract["parent_part"], "Head")
                self.assertEqual(contract["child_part"], "Mandible")
                self.assertEqual(contract["input_size"], [224, 224])

    def test_v2_contract_rejects_missing_identity_evidence(self):
        cases = (
            ("manifest_parent", "manifest", "parent_part", "blink_manifest_parent_part_missing"),
            ("manifest_child", "manifest", "child_part", "blink_manifest_child_part_missing"),
            ("checkpoint_parent", "checkpoint", "parent_part", "blink_checkpoint_parent_part_missing"),
            ("checkpoint_child", "checkpoint", "child_part", "blink_checkpoint_child_part_missing"),
        )
        for name, owner, field, error_code in cases:
            with self.subTest(case=name):
                manifest, checkpoint_meta = self._v2_contract()
                target = manifest if owner == "manifest" else checkpoint_meta
                target.pop(field)
                if owner == "checkpoint" and field == "child_part":
                    checkpoint_meta.pop("part_name")

                with self.assertRaisesRegex(ValueError, f"^{error_code}$"):
                    self._validate_contract(manifest, checkpoint_meta)

        manifest, checkpoint_meta = self._v2_contract()
        with self.assertRaisesRegex(ValueError, "^blink_route_parent_part_missing$"):
            self._validate_contract(
                manifest,
                checkpoint_meta,
                route_parent_part=None,
            )
        with self.assertRaisesRegex(ValueError, "^blink_route_child_part_missing$"):
            self._validate_contract(
                manifest,
                checkpoint_meta,
                route_child_part=None,
            )

    def test_v2_contract_rejects_identity_conflicts(self):
        cases = (
            ("route_parent", "route_parent_part", "Thorax", "blink_route_parent_part_mismatch"),
            ("route_child", "route_child_part", "Eye", "blink_route_child_part_mismatch"),
            ("checkpoint_parent", "parent_part", "Thorax", "blink_checkpoint_parent_part_mismatch"),
            ("checkpoint_child", "child_part", "Eye", "blink_checkpoint_child_part_mismatch"),
        )
        for name, field, value, error_code in cases:
            with self.subTest(case=name):
                manifest, checkpoint_meta = self._v2_contract()
                overrides = {}
                if name.startswith("route_"):
                    overrides[field] = value
                else:
                    checkpoint_meta[field] = value
                    if field == "child_part":
                        checkpoint_meta["part_name"] = value

                with self.assertRaisesRegex(ValueError, f"^{error_code}$"):
                    self._validate_contract(
                        manifest,
                        checkpoint_meta,
                        **overrides,
                    )

    def test_v2_contract_rejects_checkpoint_child_alias_conflict(self):
        manifest, checkpoint_meta = self._v2_contract()
        checkpoint_meta["part_name"] = "Eye"

        with self.assertRaisesRegex(
            ValueError,
            "^blink_checkpoint_child_part_alias_mismatch$",
        ):
            self._validate_contract(manifest, checkpoint_meta)

    def test_v2_contract_rejects_missing_checkpoint_kind(self):
        manifest, checkpoint_meta = self._v2_contract()
        checkpoint_meta.pop("kind")

        with self.assertRaisesRegex(ValueError, "^blink_checkpoint_kind_missing$"):
            self._validate_contract(manifest, checkpoint_meta)

    def test_v1_contract_keeps_missing_identity_evidence_compatible(self):
        manifest, checkpoint_meta = self._v2_contract()
        manifest["schema_version"] = BLINK_EXPERT_MANIFEST_LEGACY_SCHEMA_VERSION
        manifest.pop("parent_part")
        manifest.pop("child_part")
        manifest.pop("preprocessing")
        checkpoint_meta.pop("kind")
        checkpoint_meta.pop("parent_part")
        checkpoint_meta.pop("child_part")
        checkpoint_meta.pop("part_name")
        checkpoint_meta.pop("preprocessing")

        contract = self._validate_contract(manifest, checkpoint_meta)

        self.assertEqual(contract["parent_part"], "Head")
        self.assertEqual(contract["child_part"], "Mandible")

    def test_v1_contract_rejects_present_identity_evidence_conflicts(self):
        cases = (
            ("manifest_parent", "manifest", "parent_part", "Thorax", "blink_route_parent_part_mismatch"),
            ("manifest_child", "manifest", "child_part", "Eye", "blink_route_child_part_mismatch"),
            ("checkpoint_parent", "checkpoint", "parent_part", "Thorax", "blink_checkpoint_parent_part_mismatch"),
            ("checkpoint_child", "checkpoint", "part_name", "Eye", "blink_checkpoint_child_part_mismatch"),
        )
        for name, owner, field, value, error_code in cases:
            with self.subTest(case=name):
                manifest, checkpoint_meta = self._v2_contract()
                manifest["schema_version"] = (
                    BLINK_EXPERT_MANIFEST_LEGACY_SCHEMA_VERSION
                )
                target = manifest if owner == "manifest" else checkpoint_meta
                target[field] = value
                if owner == "checkpoint" and field == "part_name":
                    checkpoint_meta.pop("child_part")

                with self.assertRaisesRegex(ValueError, f"^{error_code}$"):
                    self._validate_contract(manifest, checkpoint_meta)


if __name__ == "__main__":
    unittest.main()
