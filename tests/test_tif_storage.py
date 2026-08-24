import json
import os
import sqlite3
import tempfile
import unittest
import zlib
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

import numpy as np

from AntSleap.core.tif_materialization_cache import TifMaterializationCache
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_export import write_nifti_volume
from AntSleap.core.tif_storage import (
    enforce_storage_preflight,
    ensure_label_value_fits_dtype,
    estimate_storage_preflight,
    label_dtype_for_max_id,
    materialization_cache_key,
)
from AntSleap.core.tif_storage_inventory import scan_tif_project_storage
from AntSleap.core.tif_storage_migration import (
    migrate_label_dtypes,
    quarantine_legacy_run_caches,
)
from AntSleap.core.tif_storage_lifecycle import TifStorageLifecycleManager
from AntSleap.core.tif_storage_lifecycle import _verify_plan_item
from AntSleap.core.tif_volume_io import (
    create_empty_label_sidecar_like,
    write_volume_sidecar,
)


class TifStoragePolicyTests(unittest.TestCase):
    def test_label_dtype_boundaries_and_overflow_guard(self):
        self.assertEqual(label_dtype_for_max_id(0), np.dtype("uint8"))
        self.assertEqual(label_dtype_for_max_id(255), np.dtype("uint8"))
        self.assertEqual(label_dtype_for_max_id(256), np.dtype("uint16"))
        self.assertEqual(label_dtype_for_max_id(65535), np.dtype("uint16"))
        self.assertEqual(label_dtype_for_max_id(65536), np.dtype("uint32"))
        self.assertEqual(ensure_label_value_fits_dtype(255, "uint8"), 255)
        with self.assertRaisesRegex(OverflowError, "label_id_not_representable"):
            ensure_label_value_fits_dtype(256, "uint8")

    def test_cache_key_is_path_independent_and_parameter_sensitive(self):
        source = [
            {
                "asset_id": "asset-1",
                "content_hash": "sha256:abc",
                "role": "manual_truth",
                "path": "old/location",
            }
        ]
        moved = [{**source[0], "path": "new/location"}]
        first, _ = materialization_cache_key(
            source_assets=source,
            format_id="nnunet_nifti_label",
            compression={"id": "gzip"},
        )
        second, _ = materialization_cache_key(
            source_assets=moved,
            format_id="nnunet_nifti_label",
            compression={"id": "gzip"},
        )
        changed, _ = materialization_cache_key(
            source_assets=moved,
            format_id="nnunet_nifti_label",
            compression={"id": "gzip", "level": 1},
        )
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)

    def test_disk_preflight_fails_before_backend_launch(self):
        usage = namedtuple("usage", "total used free")
        contract = {
            "action": "prepare_dataset",
            "input_scope": "top_level_volume",
            "specimens": [
                {
                    "input_volume": {"shape_zyx": [10, 10, 10], "dtype": "uint8"},
                    "label_volume": {"shape_zyx": [10, 10, 10], "dtype": "uint8"},
                }
            ],
        }
        with patch(
            "AntSleap.core.tif_storage.shutil.disk_usage",
            return_value=usage(1000, 999, 1),
        ):
            report = estimate_storage_preflight(
                contract,
                ".",
                backend_id="taxamask_tif_nnunet_v2_backend",
                required_formats=["nnunet_nifti"],
            )
        self.assertFalse(report["sufficient"])
        with self.assertRaisesRegex(OSError, "tif_storage_preflight_insufficient"):
            enforce_storage_preflight(report)

    def test_ome_zarr_chunk_is_lossless_and_zero_chunk_is_sparse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            values = np.arange(24, dtype=np.uint16).reshape((2, 3, 4))
            sidecar = root / "values.ome.zarr"
            write_volume_sidecar(sidecar, values, role="manual_truth")
            zarray = json.loads((sidecar / "0" / ".zarray").read_text("utf-8"))
            payload = zlib.decompress((sidecar / "0" / "0.0.0").read_bytes())
            decoded = np.frombuffer(payload, dtype=np.dtype(zarray["dtype"])).reshape(
                values.shape
            )
            np.testing.assert_array_equal(decoded, values)

            empty = root / "empty.ome.zarr"
            write_volume_sidecar(
                empty,
                np.zeros((2, 3, 4), dtype=np.uint8),
                role="working_edit",
            )
            self.assertFalse((empty / "0" / "0.0.0").exists())

    def test_new_label_sidecar_uses_schema_maximum_dtype(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "image.ome.zarr"
            write_volume_sidecar(
                image,
                np.zeros((2, 3, 4), dtype=np.uint8),
                role="working_image",
                write_ome_zarr=False,
            )
            small = create_empty_label_sidecar_like(
                image,
                root / "small.ome.zarr",
                max_label_id=12,
                write_ome_zarr=False,
            )
            wide = create_empty_label_sidecar_like(
                image,
                root / "wide.ome.zarr",
                max_label_id=256,
                write_ome_zarr=False,
            )
            self.assertEqual(small["dtype"], "uint8")
            self.assertEqual(wide["dtype"], "uint16")
            with self.assertRaisesRegex(OverflowError, "label_id_not_representable"):
                create_empty_label_sidecar_like(
                    image,
                    root / "unsafe.ome.zarr",
                    dtype="uint8",
                    max_label_id=256,
                    write_ome_zarr=False,
                )

    def test_nifti_gzip_output_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            volume = np.arange(24, dtype=np.uint16).reshape((2, 3, 4))
            first = root / "first.nii.gz"
            second = root / "second.nii.gz"
            write_nifti_volume(first, volume)
            write_nifti_volume(second, volume)
            self.assertEqual(first.read_bytes(), second.read_bytes())


class TifMaterializationCacheTests(unittest.TestCase):
    def test_cache_reuses_verified_content_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = TifMaterializationCache(root)
            source_assets = [
                {
                    "asset_id": "asset-1",
                    "content_hash": "sha256:source",
                    "role": "manual_truth",
                }
            ]
            writes = []

            def writer(path):
                writes.append(str(path))
                Path(path).write_bytes(b"verified materialization")

            first = cache.materialize(
                destination=root / "runs" / "one" / "label.nii.gz",
                suffix=".nii.gz",
                source_assets=source_assets,
                format_id="nnunet_nifti_label",
                writer=writer,
            )
            second = cache.materialize(
                destination=root / "runs" / "two" / "label.nii.gz",
                suffix=".nii.gz",
                source_assets=[{**source_assets[0], "path": "moved"}],
                format_id="nnunet_nifti_label",
                writer=writer,
            )
            self.assertFalse(first["cache_hit"])
            self.assertTrue(second["cache_hit"])
            self.assertEqual(len(writes), 1)
            self.assertEqual(first["cache_key"], second["cache_key"])
            self.assertFalse(os.path.isabs(first["run_path"]))

            entry = root / first["cache_path"]
            manifest = json.loads((entry / "materialization.json").read_text("utf-8"))
            artifact = entry / manifest["artifact_name"]
            original_stat = artifact.stat()
            artifact.write_bytes(b"x" * original_stat.st_size)
            os.utime(artifact, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            with self.assertRaisesRegex(RuntimeError, "materialization_cache_entry_invalid"):
                cache.materialize(
                    destination=root / "runs" / "three" / "label.nii.gz",
                    suffix=".nii.gz",
                    source_assets=source_assets,
                    format_id="nnunet_nifti_label",
                    writer=writer,
                )


class TifStorageLifecycleTests(unittest.TestCase):
    def test_legacy_reproducible_tree_verification_detects_changes(self):
        from AntSleap.core.file_integrity import compute_fingerprint

        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "legacy-cache"
            tree.mkdir()
            payload = tree / "payload.bin"
            payload.write_bytes(b"rebuildable")
            fingerprint = compute_fingerprint(tree)
            item = {
                "path_kind": "legacy_reproducible_tree",
                "content_hash": (
                    f"{fingerprint['hash_algorithm']}:{fingerprint['digest']}"
                ),
            }
            self.assertEqual(
                _verify_plan_item(tree, item),
                item["content_hash"],
            )
            payload.write_bytes(b"changed")
            with self.assertRaisesRegex(
                ValueError, "cleanup_materialization_hash_mismatch"
            ):
                _verify_plan_item(tree, item)

    def test_label_dtype_migration_is_lossless_and_updates_project_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            manager = TifProjectManager()
            manager.create_project("migration", project_root)
            manager.add_specimen("s1")
            relative = "specimens/s1/labels/working_edit.ome.zarr"
            values = np.zeros((8, 32, 32), dtype=np.uint16)
            values[0, 0, :4] = [0, 1, 4, 2]
            write_volume_sidecar(
                project_root / relative,
                values,
                role="working_edit",
            )
            manager.register_label_volume(
                "s1",
                "working_edit",
                relative,
                values.shape,
                values.dtype,
            )

            report = migrate_label_dtypes(manager)

            migrated = np.load(project_root / relative / "array.npy")
            self.assertEqual(migrated.dtype, np.dtype("uint8"))
            np.testing.assert_array_equal(migrated, values)
            self.assertEqual(report["state"], "completed")
            self.assertGreater(report["released_bytes"], 0)
            reloaded = TifProjectManager()
            reloaded.load_project(manager.current_project_path)
            self.assertEqual(
                reloaded.get_specimen("s1")["labels"]["working_edit"]["dtype"],
                "uint8",
            )

    def test_legacy_run_cache_enters_existing_quarantine_and_restore_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            manager = TifProjectManager()
            manager.create_project("legacy", project_root)
            source_image = project_root / "specimens" / "s1" / "image.tif"
            source_label = project_root / "specimens" / "s1" / "truth.npy"
            source_image.parent.mkdir(parents=True)
            source_image.write_bytes(b"image")
            np.save(source_label, np.array([1], dtype=np.uint8))
            run_root = (
                project_root
                / "runs"
                / "prepare_dataset"
                / "prepare_dataset_test"
            )
            dataset = run_root / "dataset"
            dataset.mkdir(parents=True)
            (dataset / "derived.bin").write_bytes(b"derived")
            (run_root / "contract.json").write_text(
                json.dumps(
                    {
                        "action": "prepare_dataset",
                        "part_samples": [
                            {
                                "input_volume": {"path": str(source_image)},
                                "label_volume": {"path": str(source_label)},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            quarantined = quarantine_legacy_run_caches(manager, grace_days=1)

            self.assertEqual(quarantined["state"], "quarantined")
            self.assertFalse(dataset.exists())
            item = quarantined["items"][0]
            self.assertEqual(item["path_kind"], "legacy_reproducible_tree")
            self.assertTrue((project_root / item["quarantine_path"]).is_dir())
            restored = TifStorageLifecycleManager(manager).restore(
                quarantined["plan_id"]
            )
            self.assertEqual(restored["state"], "restored")
            self.assertTrue(dataset.is_dir())

    def _project_with_cached_run(self, root):
        project_root = Path(root) / "project"
        manager = TifProjectManager()
        manager.create_project("storage", project_root)
        cache = TifMaterializationCache(project_root)
        materialization = cache.materialize(
            destination=project_root / "runs" / "prepare" / "run-1" / "imagesTr" / "case.nii",
            suffix=".nii",
            source_assets=[
                {
                    "asset_id": "asset-source",
                    "content_hash": "sha256:source",
                    "role": "source_volume",
                }
            ],
            format_id="nnunet_nifti_image",
            writer=lambda path: Path(path).write_bytes(b"small cached nifti"),
        )
        manager.project_data.setdefault("runs", []).append(
            {
                "run_id": "run-1",
                "action": "prepare_dataset",
                "backend_id": "taxamask_tif_nnunet_v2_backend",
                "run_dir": "runs/prepare/run-1",
                "result_status": "success",
                "input_assets": [
                    {
                        "asset_id": "asset-source",
                        "owner_key": "specimen.s1.working",
                        "role": "source_volume",
                        "content_hash": "sha256:source",
                    }
                ],
                "materializations": [materialization],
            }
        )
        manager.save_project()
        return manager, materialization

    def test_inventory_protects_unknown_files_and_deduplicates_hardlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, materialization = self._project_with_cached_run(tmp)
            unknown = Path(manager.project_dir) / "research_notes.bin"
            unknown.write_bytes(b"unknown")
            unknown_cache = Path(manager.project_dir) / "cache" / "research_notes.bin"
            unknown_cache.write_bytes(b"unknown cache content")
            report = scan_tif_project_storage(manager)
            item = next(
                value
                for value in report["items"]
                if value["relative_path"] == "research_notes.bin"
            )
            self.assertEqual(item["authority_level"], "L0")
            self.assertFalse(item["reclaimable"])
            cache_item = next(
                value
                for value in report["items"]
                if value["relative_path"] == "cache/research_notes.bin"
            )
            self.assertEqual(cache_item["authority_level"], "L0")
            self.assertFalse(cache_item["reclaimable"])
            registered_cache_items = [
                value
                for value in report["items"]
                if value["classification_reason"].startswith("registered_cache_")
            ]
            self.assertEqual(len(registered_cache_items), 2)
            self.assertTrue(
                all(value["authority_level"] == "L2" for value in registered_cache_items)
            )
            self.assertGreater(report["summary"]["hardlink_shared_bytes"], 0)
            self.assertTrue(materialization["run_path"])

    def test_cleanup_blocks_cache_entry_with_unregistered_extra_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, materialization = self._project_with_cached_run(tmp)
            cache_dir = Path(manager.project_dir) / materialization["cache_path"]
            (cache_dir / "research_notes.txt").write_text(
                "must remain protected",
                encoding="utf-8",
            )
            lifecycle = TifStorageLifecycleManager(manager)
            plan = lifecycle.create_cleanup_plan()
            matching = [
                item
                for item in plan["items"]
                if item["cache_key"] == materialization["cache_key"]
            ]
            self.assertTrue(matching)
            self.assertTrue(all(item["eligibility"] == "blocked" for item in matching))
            self.assertTrue(
                all(
                    "cleanup_cache_entry_members_invalid" in item["blocked_reason"]
                    for item in matching
                )
            )

    def test_cleanup_quarantines_cache_and_run_link_then_restores_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, materialization = self._project_with_cached_run(tmp)
            lifecycle = TifStorageLifecycleManager(manager)
            original_cache_path = materialization["cache_path"]
            original_run_path = materialization["run_path"]
            plan = lifecycle.create_cleanup_plan()
            eligible = [
                item for item in plan["items"] if item["eligibility"] == "eligible"
            ]
            self.assertEqual(
                {item["path_kind"] for item in eligible},
                {"cache_entry", "run_materialization"},
            )
            self.assertGreater(plan["expected_release_bytes"], 0)
            interrupted_item = eligible[0]
            interrupted_source = (
                Path(manager.project_dir) / interrupted_item["original_path"]
            )
            interrupted_target = (
                Path(manager.project_dir)
                / ".quarantine"
                / plan["plan_id"]
                / interrupted_item["original_path"]
            )
            interrupted_target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(interrupted_source, interrupted_target)
            quarantined = lifecycle.quarantine(plan["plan_id"], grace_days=1)
            self.assertEqual(quarantined["state"], "quarantined")
            self.assertFalse((Path(manager.project_dir) / original_cache_path).exists())
            self.assertFalse((Path(manager.project_dir) / original_run_path).exists())
            inventory = scan_tif_project_storage(manager)
            quarantine_items = [
                item
                for item in inventory["items"]
                if item["relative_path"].startswith(".quarantine/")
            ]
            self.assertTrue(quarantine_items)
            self.assertTrue(
                all(item["authority_level"] == "L2" for item in quarantine_items)
            )
            self.assertEqual(
                inventory["summary"]["quarantined_allocated_bytes"],
                sum(item["allocated_bytes"] for item in quarantine_items),
            )
            interrupted_restore_item = next(
                item
                for item in quarantined["items"]
                if item["state"] == "quarantined"
            )
            interrupted_restore_source = (
                Path(manager.project_dir)
                / interrupted_restore_item["quarantine_path"]
            )
            interrupted_restore_target = (
                Path(manager.project_dir) / interrupted_restore_item["original_path"]
            )
            interrupted_restore_target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(interrupted_restore_source, interrupted_restore_target)
            restored = lifecycle.restore(plan["plan_id"])
            self.assertEqual(restored["state"], "restored")
            self.assertTrue((Path(manager.project_dir) / original_cache_path).exists())
            self.assertTrue((Path(manager.project_dir) / original_run_path).exists())

    def test_pin_blocks_cleanup_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, materialization = self._project_with_cached_run(tmp)
            lifecycle = TifStorageLifecycleManager(manager)
            lifecycle.pin(
                "cache_key",
                materialization["cache_key"],
                "paper experiment",
                pinned_by="unit-test",
            )
            plan = lifecycle.create_cleanup_plan()
            matching = [
                item
                for item in plan["items"]
                if item["cache_key"] == materialization["cache_key"]
            ]
            self.assertTrue(matching)
            self.assertTrue(all(item["eligibility"] == "blocked" for item in matching))
            self.assertTrue(
                all(item["blocked_reason"] == "retention_pin_active" for item in matching)
            )

    def test_selected_cleanup_plan_only_quarantines_chosen_cache_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, first = self._project_with_cached_run(tmp)
            project_root = Path(manager.project_dir)
            cache = TifMaterializationCache(project_root)
            second = cache.materialize(
                destination=project_root
                / "runs"
                / "prepare"
                / "run-2"
                / "imagesTr"
                / "case.nii",
                suffix=".nii",
                source_assets=[
                    {
                        "asset_id": "asset-source-2",
                        "content_hash": "sha256:source-2",
                        "role": "source_volume",
                    }
                ],
                format_id="nnunet_nifti_image",
                writer=lambda path: Path(path).write_bytes(b"second cached nifti"),
            )
            manager.project_data.setdefault("runs", []).append(
                {
                    "run_id": "run-2",
                    "action": "prepare_dataset",
                    "backend_id": "taxamask_tif_nnunet_v2_backend",
                    "run_dir": "runs/prepare/run-2",
                    "result_status": "success",
                    "input_assets": [
                        {
                            "asset_id": "asset-source-2",
                            "owner_key": "specimen.s2.working",
                            "role": "source_volume",
                            "content_hash": "sha256:source-2",
                        }
                    ],
                    "materializations": [second],
                }
            )
            manager.save_project()

            lifecycle = TifStorageLifecycleManager(manager)
            first_cache_path = first["cache_path"]
            first_run_path = first["run_path"]
            second_cache_path = second["cache_path"]
            second_run_path = second["run_path"]
            plan = lifecycle.create_cleanup_plan(cache_keys=[first["cache_key"]])
            self.assertEqual(
                {item["cache_key"] for item in plan["items"]},
                {first["cache_key"]},
            )
            quarantined = lifecycle.quarantine(plan["plan_id"])

            self.assertFalse((project_root / first_cache_path).exists())
            self.assertFalse((project_root / first_run_path).exists())
            self.assertTrue((project_root / second_cache_path).exists())
            self.assertTrue((project_root / second_run_path).exists())
            self.assertTrue(
                (project_root / quarantined["report_paths"]["json_path"]).is_file()
            )
            self.assertEqual(
                lifecycle.list_cleanup_plans(states=["quarantined"])[0]["plan_id"],
                plan["plan_id"],
            )

            reloaded = TifProjectManager()
            reloaded.load_project(manager.current_project_path)
            reopened_lifecycle = TifStorageLifecycleManager(reloaded)
            self.assertEqual(
                reopened_lifecycle.list_cleanup_plans(states=["quarantined"])[0][
                    "plan_id"
                ],
                plan["plan_id"],
            )

    def test_restore_refuses_to_overwrite_path_created_during_grace_period(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, _materialization = self._project_with_cached_run(tmp)
            lifecycle = TifStorageLifecycleManager(manager)
            plan = lifecycle.create_cleanup_plan()
            quarantined = lifecycle.quarantine(plan["plan_id"])
            run_item = next(
                item
                for item in quarantined["items"]
                if item["path_kind"] == "run_materialization"
            )
            occupied = Path(manager.project_dir) / run_item["original_path"]
            occupied.parent.mkdir(parents=True, exist_ok=True)
            occupied.write_bytes(b"new file created during grace period")

            with self.assertRaisesRegex(
                FileExistsError, "cleanup_restore_source_and_target_exist"
            ):
                lifecycle.restore(plan["plan_id"])

            self.assertEqual(
                occupied.read_bytes(), b"new file created during grace period"
            )
            self.assertTrue(
                (Path(manager.project_dir) / run_item["quarantine_path"]).exists()
            )
            self.assertEqual(lifecycle.report(plan["plan_id"])["state"], "quarantined")

    def test_purge_requires_exact_plan_id_and_expired_grace_period(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, materialization = self._project_with_cached_run(tmp)
            lifecycle = TifStorageLifecycleManager(manager)
            plan = lifecycle.create_cleanup_plan()
            lifecycle.quarantine(plan["plan_id"], grace_days=1)
            with self.assertRaisesRegex(ValueError, "cleanup_purge_confirmation_mismatch"):
                lifecycle.purge(plan["plan_id"], confirmation="wrong")
            with self.assertRaisesRegex(ValueError, "cleanup_grace_period_active"):
                lifecycle.purge(plan["plan_id"], confirmation=plan["plan_id"])
            connection = sqlite3.connect(manager.current_database_path)
            try:
                connection.execute(
                    "UPDATE cleanup_plans SET grace_until = ? WHERE plan_id = ?",
                    ("2000-01-01T00:00:00Z", plan["plan_id"]),
                )
                connection.commit()
            finally:
                connection.close()
            purged = lifecycle.purge(plan["plan_id"], confirmation=plan["plan_id"])
            self.assertEqual(purged["state"], "deleted")
            self.assertGreater(purged["deleted_bytes"], 0)
            self.assertTrue(
                all(item["state"] == "deleted" for item in purged["items"])
            )
            run_record = manager.project_data["runs"][0]
            self.assertEqual(run_record["materializations"][0]["status"], "deleted")

    def test_purge_can_audit_an_explicit_grace_period_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, _materialization = self._project_with_cached_run(tmp)
            lifecycle = TifStorageLifecycleManager(manager)
            plan = lifecycle.create_cleanup_plan()
            lifecycle.quarantine(plan["plan_id"], grace_days=1)

            purged = lifecycle.purge(
                plan["plan_id"],
                confirmation=plan["plan_id"],
                override_grace_period=True,
            )

            self.assertEqual(purged["state"], "deleted")
            connection = sqlite3.connect(manager.current_database_path)
            try:
                event = connection.execute(
                    """
                    SELECT payload_json FROM cleanup_events
                    WHERE plan_id = ? AND event_type = 'grace_period_overridden'
                    """,
                    (plan["plan_id"],),
                ).fetchone()
            finally:
                connection.close()
            self.assertIsNotNone(event)
            payload = json.loads(event[0])
            self.assertEqual(payload["reason"], "user_confirmed_project_validation")
            self.assertTrue(payload["original_grace_until"])

    def test_quarantine_save_failure_rolls_files_and_memory_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, materialization = self._project_with_cached_run(tmp)
            lifecycle = TifStorageLifecycleManager(manager)
            original_project_data = json.loads(json.dumps(manager.project_data))
            cache_path = Path(manager.project_dir) / materialization["cache_path"]
            run_path = Path(manager.project_dir) / materialization["run_path"]
            plan = lifecycle.create_cleanup_plan()
            with patch.object(
                manager,
                "save_project",
                side_effect=RuntimeError("injected_save_failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "injected_save_failure"):
                    lifecycle.quarantine(plan["plan_id"])
            self.assertTrue(cache_path.exists())
            self.assertTrue(run_path.exists())
            self.assertEqual(manager.project_data, original_project_data)
            self.assertEqual(lifecycle.report(plan["plan_id"])["state"], "planned")

    def test_quarantine_database_failure_restores_files_and_saved_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, materialization = self._project_with_cached_run(tmp)
            lifecycle = TifStorageLifecycleManager(manager)
            cache_path = Path(manager.project_dir) / materialization["cache_path"]
            run_path = Path(manager.project_dir) / materialization["run_path"]
            original_cache_path = materialization["cache_path"]
            plan = lifecycle.create_cleanup_plan()
            original_insert_event = lifecycle._insert_event

            def fail_quarantine_event(
                connection,
                plan_id,
                item_id,
                event_type,
                payload=None,
            ):
                if event_type == "item_quarantined":
                    raise sqlite3.OperationalError("injected_database_failure")
                return original_insert_event(
                    connection,
                    plan_id,
                    item_id,
                    event_type,
                    payload,
                )

            with patch.object(
                lifecycle,
                "_insert_event",
                side_effect=fail_quarantine_event,
            ):
                with self.assertRaisesRegex(
                    sqlite3.OperationalError,
                    "injected_database_failure",
                ):
                    lifecycle.quarantine(plan["plan_id"])

            self.assertTrue(cache_path.exists())
            self.assertTrue(run_path.exists())
            self.assertEqual(lifecycle.report(plan["plan_id"])["state"], "planned")
            reloaded = TifProjectManager()
            reloaded.load_project(manager.current_project_path)
            reloaded_materialization = reloaded.project_data["runs"][0][
                "materializations"
            ][0]
            self.assertEqual(reloaded_materialization["status"], "verified")
            self.assertEqual(
                reloaded_materialization["cache_path"],
                original_cache_path,
            )

    def test_purge_resumes_after_delete_failure_and_repairs_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, materialization = self._project_with_cached_run(tmp)
            lifecycle = TifStorageLifecycleManager(manager)
            plan = lifecycle.create_cleanup_plan()
            lifecycle.quarantine(plan["plan_id"], grace_days=1)
            connection = sqlite3.connect(manager.current_database_path)
            try:
                connection.execute(
                    "UPDATE cleanup_plans SET grace_until = ? WHERE plan_id = ?",
                    ("2000-01-01T00:00:00Z", plan["plan_id"]),
                )
                connection.commit()
            finally:
                connection.close()

            from AntSleap.core import tif_storage_lifecycle as lifecycle_module

            original_remove = lifecycle_module._remove_path
            remove_count = 0

            def fail_second_remove(path):
                nonlocal remove_count
                remove_count += 1
                if remove_count == 2:
                    raise OSError("injected_delete_failure")
                original_remove(path)

            with patch.object(
                lifecycle_module,
                "_remove_path",
                side_effect=fail_second_remove,
            ):
                with self.assertRaisesRegex(OSError, "injected_delete_failure"):
                    lifecycle.purge(plan["plan_id"], confirmation=plan["plan_id"])

            interrupted = lifecycle.report(plan["plan_id"])
            self.assertEqual(interrupted["state"], "quarantined")
            self.assertEqual(
                {item["state"] for item in interrupted["items"]},
                {"deleted", "deleting"},
            )
            self.assertEqual(
                manager.project_data["runs"][0]["materializations"][0]["status"],
                "quarantined",
            )

            resumed = lifecycle.purge(
                plan["plan_id"], confirmation=plan["plan_id"]
            )
            self.assertEqual(resumed["state"], "deleted")
            self.assertTrue(
                all(item["state"] == "deleted" for item in resumed["items"])
            )
            materialization_record = manager.project_data["runs"][0][
                "materializations"
            ][0]
            self.assertEqual(materialization_record["status"], "deleted")
            self.assertEqual(materialization_record["cache_path"], "")


if __name__ == "__main__":
    unittest.main()
