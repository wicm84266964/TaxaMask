import hashlib
import io
import json
import os
import shutil
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANTSLEAP_ROOT = PROJECT_ROOT / "AntSleap"

import sys

if str(ANTSLEAP_ROOT) not in sys.path:
    sys.path.insert(0, str(ANTSLEAP_ROOT))

from core.cascade_manager import CascadingManager
from core.blink_expert_backends import (
    BlinkBackendError,
    create_default_blink_backend_registry,
)
from core.blink_heatmap_trainer import HeatmapBlinkNet
from core.blink_expert_manifest import (
    BLINK_EXPERT_MANIFEST_LEGACY_SCHEMA_VERSION,
    build_blink_expert_manifest,
    build_blink_preprocessing_contract,
)
from core.cascade_routes import (
    ROUTE_BACKEND_HEATMAP_BLINK,
    ROUTE_BACKEND_VIT_B_BLINK,
)
from core.training_weight_publisher import TrainingWeightPublisher


class TinyBlinkExpert(torch.nn.Module):
    def __init__(self, pretrained=False, image_size=224):
        super().__init__()
        self.image_size = int(image_size)
        self.weight = torch.nn.Parameter(torch.ones(1))


class BlinkRouteBackendTests(unittest.TestCase):
    def _manager(self, weights_dir):
        engine = types.SimpleNamespace(device="cpu", weights_dir=str(weights_dir))
        manager = CascadingManager.__new__(CascadingManager)
        manager.engine = engine
        manager.device = "cpu"
        manager.loaded_experts = {}
        manager.expert_dir = str(Path(weights_dir) / "experts")
        manager.route_manifest_path = str(Path(weights_dir) / "experts" / "cascade_routes.json")
        manager.legacy_route_manifest = {"version": "", "approved": False, "routes": []}
        manager.blink_backend_registry = create_default_blink_backend_registry()
        return manager

    def _write_managed_expert(self, weights_dir, child_part="Mandible", filename="expert_v1.pth"):
        expert_path = Path(weights_dir) / "experts" / child_part / filename
        expert_path.parent.mkdir(parents=True, exist_ok=True)
        expert_path.write_bytes(b"placeholder")
        manifest_path = expert_path.with_suffix(".manifest.json")
        manifest_path.write_text(
            json.dumps(
                build_blink_expert_manifest(
                    str(expert_path),
                    parent_part="Head",
                    child_part=child_part,
                )
            ),
            encoding="utf-8",
        )
        return expert_path, manifest_path

    def _publish_active_expert(
        self,
        weights_dir,
        run_id="blink-run-001",
        *,
        checkpoint_bytes=b"published blink weights",
        expert_backend=ROUTE_BACKEND_VIT_B_BLINK,
        manifest_transform=None,
    ):
        staging_root = Path(weights_dir).parent / f"staging-{run_id}"
        child_dir = staging_root / "Mandible"
        child_dir.mkdir(parents=True)
        staged_weights = child_dir / "expert_published.pth"
        staged_weights.write_bytes(checkpoint_bytes)
        staged_manifest = staged_weights.with_suffix(".manifest.json")
        manifest = build_blink_expert_manifest(
            str(staged_weights),
            expert_backend=expert_backend,
            parent_part="Head",
            child_part="Mandible",
            input_size=(64, 64),
        )
        if callable(manifest_transform):
            manifest = manifest_transform(dict(manifest))
        staged_manifest.write_text(json.dumps(manifest), encoding="utf-8")
        publisher = TrainingWeightPublisher(Path(weights_dir) / "experts")
        publication = publisher.publish_pending(
            run_id,
            staging_root,
            [
                {
                    "artifact_id": "blink_checkpoint",
                    "role": "output_weights",
                    "relative_path": "Mandible/expert_published.pth",
                    "media_type": "application/octet-stream",
                },
                {
                    "artifact_id": "blink_model_manifest",
                    "role": "model_manifest",
                    "relative_path": "Mandible/expert_published.manifest.json",
                    "media_type": "application/json",
                },
            ],
        )
        active = publisher.activate(
            run_id,
            {
                "schema_version": "taxamask_training_run_v1",
                "run_id": run_id,
                "status": "succeeded",
                "artifacts": publication["artifacts"],
            },
        )
        artifacts = {item["artifact_id"]: item for item in active["artifacts"]}
        model_root = Path(weights_dir) / "experts"
        weights_path = model_root.joinpath(*artifacts["blink_checkpoint"]["relative_path"].split("/"))
        manifest_path = model_root.joinpath(*artifacts["blink_model_manifest"]["relative_path"].split("/"))
        return weights_path, manifest_path

    def _serialize_contract_checkpoint(
        self,
        expert_backend,
        *,
        parent_part="Head",
        child_part="Mandible",
        include_kind=True,
    ):
        if expert_backend == ROUTE_BACKEND_HEATMAP_BLINK:
            model = HeatmapBlinkNet(base_channels=4)
            checkpoint_kind = "blink_heatmap_expert"
        else:
            model = TinyBlinkExpert(image_size=64)
            checkpoint_kind = "blink_expert_locator"
        metadata = {
            "parent_part": parent_part,
            "child_part": child_part,
            "part_name": child_part,
            "input_size": [64, 64],
            "preprocessing": build_blink_preprocessing_contract(),
        }
        if expert_backend == ROUTE_BACKEND_HEATMAP_BLINK:
            metadata["base_channels"] = 4
        if include_kind:
            metadata["kind"] = checkpoint_kind
        buffer = io.BytesIO()
        torch.save(
            {
                "state_dict": model.state_dict(),
                "meta": metadata,
            },
            buffer,
        )
        return buffer.getvalue()

    def _load_contract_checkpoint(self, manager, expert_backend, checkpoint, route):
        if expert_backend == ROUTE_BACKEND_VIT_B_BLINK:
            with patch("core.cascade_manager.MicroExpertLocator", TinyBlinkExpert):
                return manager._load_expert(
                    "Mandible",
                    model_path=checkpoint["path"],
                    checkpoint_bytes=checkpoint["checkpoint_bytes"],
                    checkpoint_digest=checkpoint["digest"],
                    checkpoint_source=checkpoint["source"],
                    manifest_payload=checkpoint["manifest_payload"],
                    manifest_identity=checkpoint["manifest_identity"],
                    route_record=route,
                )
        backend = manager._blink_backends().get(expert_backend)
        return backend._load_model(manager, checkpoint, route)

    def test_vit_b_backend_keeps_existing_loader_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            expert_path = weights_dir / "experts" / "Mandible" / "expert_v1.pth"
            expert_path.parent.mkdir(parents=True, exist_ok=True)
            expert_path.write_bytes(b"placeholder")
            manager = self._manager(weights_dir)
            loader_calls = []
            infer_calls = []

            def fake_load(part_name, model_path=None, **_kwargs):
                loader_calls.append((part_name, model_path))
                return object()

            def fake_infer(image_path, parent_box, child_part_name, expert_model):
                infer_calls.append((image_path, list(parent_box), child_part_name, expert_model))
                return {"box": [1, 2, 3, 4], "confidence": 1.0}

            manager._load_expert = fake_load
            manager._infer_with_loaded_expert = fake_infer

            result = manager.infer_child_part(
                "specimen.png",
                [10, 20, 80, 70],
                "Mandible",
                parent_part="Head",
                route_manifest={
                    "version": "project-v2",
                    "routes": [
                        {
                            "parent": "Head",
                            "child": "Mandible",
                            "enabled": True,
                            "expert_id": "Mandible/expert_v1.pth",
                            "expert_part": "Mandible",
                            "expert_filename": "expert_v1.pth",
                            "expert_backend": ROUTE_BACKEND_VIT_B_BLINK,
                        }
                    ],
                },
            )

            self.assertEqual(result["box"], [1, 2, 3, 4])
            self.assertEqual(loader_calls, [("Mandible", str(expert_path))])
            self.assertEqual(infer_calls[0][1], [10, 20, 80, 70])

    def test_heatmap_backend_predicts_without_calling_vit_b_loader(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            expert_path = weights_dir / "experts" / "Eye" / "heatmap_v1.pth"
            expert_path.parent.mkdir(parents=True, exist_ok=True)
            model = HeatmapBlinkNet(base_channels=8)
            for param in model.parameters():
                torch.nn.init.constant_(param, 0.0)
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "meta": {
                        "kind": "blink_heatmap_expert",
                        "input_size": [64, 64],
                        "base_channels": 8,
                    },
                },
                expert_path,
            )
            image_path = Path(tmp_dir) / "specimen.png"
            cv2.imwrite(str(image_path), np.full((80, 100, 3), 180, dtype=np.uint8))
            manager = self._manager(weights_dir)
            loader_calls = []

            def fake_load(part_name, model_path=None):
                loader_calls.append((part_name, model_path))
                return object()

            manager._load_expert = fake_load

            route = {
                "parent": "Head",
                "child": "Eye",
                "enabled": True,
                "expert_id": "Eye/heatmap_v1.pth",
                "expert_part": "Eye",
                "expert_filename": "heatmap_v1.pth",
                "expert_backend": ROUTE_BACKEND_HEATMAP_BLINK,
                "input_size": [64, 64],
            }
            self.assertIsNone(manager.get_route_block_reason(route))

            result = manager.infer_child_part(
                str(image_path),
                [10, 20, 80, 70],
                "Eye",
                parent_part="Head",
                route_manifest={"version": "project-v2", "routes": [route]},
            )

            self.assertIsInstance(result, dict)
            self.assertEqual(result.get("backend"), ROUTE_BACKEND_HEATMAP_BLINK)
            self.assertEqual(len(result.get("box", [])), 4)
            self.assertEqual(loader_calls, [])

    def test_active_training_bundle_resolves_and_is_discoverable(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            published_path, manifest_path = self._publish_active_expert(weights_dir)
            manager = self._manager(weights_dir)
            route = {
                "parent": "Head",
                "child": "Mandible",
                "enabled": True,
                "expert_id": f"Mandible/{published_path.name}",
                "expert_part": "Mandible",
                "expert_filename": published_path.name,
                "expert_manifest": str(manifest_path),
            }

            self.assertEqual(Path(manager.resolve_route_expert_path(route)), published_path)
            self.assertTrue(manager.route_is_usable(route))
            route["expert_manifest"] = manifest_path.relative_to(
                weights_dir / "experts"
            ).as_posix()
            self.assertEqual(Path(manager.resolve_route_expert_path(route)), published_path)

            relocated_weights_dir = Path(tmp_dir) / "relocated" / "weights"
            shutil.copytree(
                weights_dir / "experts",
                relocated_weights_dir / "experts",
            )
            relocated_manager = self._manager(relocated_weights_dir)
            relocated_path = (
                relocated_weights_dir
                / "experts"
                / published_path.relative_to(weights_dir / "experts")
            )
            self.assertEqual(
                Path(relocated_manager.resolve_route_expert_path(route)),
                relocated_path,
            )
            experts = manager.list_available_experts()
            self.assertIn(str(published_path), [item.get("path") for item in experts])
            self.assertNotIn(
                "publication.json",
                [os.path.basename(str(item.get("path") or "")) for item in experts],
            )

    def test_managed_vit_b_backend_passes_verified_checkpoint_bytes_to_loader(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            published_path, manifest_path = self._publish_active_expert(weights_dir)
            manager = self._manager(weights_dir)
            loader_calls = []

            def fake_load(part_name, model_path=None, **kwargs):
                loader_calls.append((part_name, model_path, kwargs))
                return object()

            manager._load_expert = fake_load
            manager._infer_with_loaded_expert = lambda *_args, **_kwargs: {
                "box": [1, 2, 3, 4],
                "confidence": 1.0,
            }
            route = {
                "parent": "Head",
                "child": "Mandible",
                "enabled": True,
                "expert_part": "Mandible",
                "expert_backend": ROUTE_BACKEND_VIT_B_BLINK,
                "expert_manifest": str(manifest_path),
            }

            result = manager.infer_child_part(
                "specimen.png",
                [10, 20, 80, 70],
                "Mandible",
                parent_part="Head",
                route_manifest={"version": "project-v2", "routes": [route]},
            )

            self.assertEqual(result["box"], [1, 2, 3, 4])
            self.assertEqual(len(loader_calls), 1)
            part_name, model_path, loader_kwargs = loader_calls[0]
            expected_bytes = published_path.read_bytes()
            self.assertEqual(part_name, "Mandible")
            self.assertEqual(Path(model_path), published_path)
            self.assertEqual(loader_kwargs["checkpoint_bytes"], expected_bytes)
            self.assertEqual(
                loader_kwargs["checkpoint_digest"],
                hashlib.sha256(expected_bytes).hexdigest(),
            )
            self.assertEqual(
                loader_kwargs["checkpoint_source"],
                "active_training_publication",
            )
            self.assertEqual(
                loader_kwargs["manifest_payload"],
                manifest_path.read_bytes(),
            )
            self.assertEqual(
                loader_kwargs["manifest_identity"]["digest"],
                hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            )
            self.assertEqual(
                loader_kwargs["route_record"]["expert_manifest"],
                route["expert_manifest"],
            )
            self.assertEqual(
                loader_kwargs["route_record"]["expert_backend"],
                ROUTE_BACKEND_VIT_B_BLINK,
            )

    def test_managed_heatmap_load_uses_verified_bytes_after_path_swap(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            model = HeatmapBlinkNet(base_channels=4)
            for parameter in model.parameters():
                torch.nn.init.constant_(parameter, 0.0)
            buffer = io.BytesIO()
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "meta": {
                        "kind": "blink_heatmap_expert",
                        "parent_part": "Head",
                        "child_part": "Mandible",
                        "part_name": "Mandible",
                        "input_size": [64, 64],
                        "preprocessing": build_blink_preprocessing_contract(),
                        "base_channels": 4,
                    },
                },
                buffer,
            )
            original_checkpoint = buffer.getvalue()
            published_path, manifest_path = self._publish_active_expert(
                weights_dir,
                run_id="blink-window-swap-001",
                checkpoint_bytes=original_checkpoint,
                expert_backend=ROUTE_BACKEND_HEATMAP_BLINK,
            )
            image_path = Path(tmp_dir) / "specimen.png"
            cv2.imwrite(str(image_path), np.full((80, 100, 3), 180, dtype=np.uint8))
            manager = self._manager(weights_dir)
            route = {
                "parent": "Head",
                "child": "Mandible",
                "enabled": True,
                "expert_backend": ROUTE_BACKEND_HEATMAP_BLINK,
                "expert_manifest": str(manifest_path),
                "input_size": [64, 64],
            }

            original_bundle_loader = manager._load_active_training_bundle
            swapped = []

            def load_bundle_then_swap(run_id, **kwargs):
                bundle = original_bundle_loader(run_id, **kwargs)
                if kwargs.get("checkpoint_path") and not swapped:
                    tampered = bytes([original_checkpoint[0] ^ 0x01]) + original_checkpoint[1:]
                    self.assertEqual(len(tampered), len(original_checkpoint))
                    published_path.write_bytes(tampered)
                    swapped.append(True)
                return bundle

            manager._load_active_training_bundle = load_bundle_then_swap
            original_torch_load = torch.load
            loaded_payloads = []

            def load_verified_bytes(source, *args, **kwargs):
                self.assertIsInstance(source, io.BytesIO)
                loaded_payloads.append(source.getvalue())
                return original_torch_load(source, *args, **kwargs)

            with patch(
                "core.blink_expert_backends.torch.load",
                side_effect=load_verified_bytes,
            ):
                result = manager.infer_child_part(
                    str(image_path),
                    [10, 20, 80, 70],
                    "Mandible",
                    parent_part="Head",
                    route_manifest={"version": "project-v2", "routes": [route]},
                )

            self.assertIsInstance(result, dict)
            self.assertEqual(swapped, [True])
            self.assertNotEqual(published_path.read_bytes(), original_checkpoint)
            self.assertEqual(loaded_payloads, [original_checkpoint])

    def test_managed_heatmap_uses_verified_manifest_payload_after_path_swap(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            model = HeatmapBlinkNet(base_channels=4)
            for parameter in model.parameters():
                torch.nn.init.constant_(parameter, 0.0)
            buffer = io.BytesIO()
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "meta": {
                        "kind": "blink_heatmap_expert",
                        "parent_part": "Head",
                        "child_part": "Mandible",
                        "part_name": "Mandible",
                        "input_size": [64, 64],
                        "preprocessing": build_blink_preprocessing_contract(),
                        "base_channels": 4,
                    },
                },
                buffer,
            )
            checkpoint_bytes = buffer.getvalue()
            published_path, manifest_path = self._publish_active_expert(
                weights_dir,
                run_id="blink-manifest-swap-001",
                checkpoint_bytes=checkpoint_bytes,
                expert_backend=ROUTE_BACKEND_HEATMAP_BLINK,
            )
            original_manifest = manifest_path.read_bytes()
            tampered_manifest = original_manifest.replace(
                b'"input_size": [64, 64]',
                b'"input_size": [96, 96]',
                1,
            )
            self.assertEqual(len(tampered_manifest), len(original_manifest))
            self.assertNotEqual(tampered_manifest, original_manifest)
            manager = self._manager(weights_dir)
            route = {
                "parent": "Head",
                "child": "Mandible",
                "enabled": True,
                "expert_backend": ROUTE_BACKEND_HEATMAP_BLINK,
                "expert_manifest": str(manifest_path),
                "input_size": [64, 64],
            }
            original_bundle_loader = manager._load_active_training_bundle
            swapped = []

            def load_bundle_then_swap(run_id, **kwargs):
                bundle = original_bundle_loader(run_id, **kwargs)
                if (
                    kwargs.get("checkpoint_path")
                    and kwargs.get("manifest_path")
                    and not swapped
                ):
                    manifest_path.write_bytes(tampered_manifest)
                    swapped.append(True)
                return bundle

            manager._load_active_training_bundle = load_bundle_then_swap
            checkpoint = manager.resolve_route_expert_checkpoint(route)

            self.assertIsInstance(checkpoint, dict)
            self.assertEqual(swapped, [True])
            self.assertEqual(checkpoint["checkpoint_bytes"], checkpoint_bytes)
            self.assertEqual(checkpoint["manifest_payload"], original_manifest)
            self.assertEqual(
                checkpoint["manifest_identity"]["digest"],
                hashlib.sha256(original_manifest).hexdigest(),
            )
            self.assertEqual(manifest_path.read_bytes(), tampered_manifest)

            backend = manager._blink_backends().get(
                ROUTE_BACKEND_HEATMAP_BLINK
            )
            with patch(
                "builtins.open",
                side_effect=AssertionError("backend reopened manifest path"),
            ):
                loaded_model = backend._load_model(manager, checkpoint, route)

            self.assertIsNotNone(loaded_model)
            self.assertEqual(
                loaded_model._taxamask_meta["input_size"],
                [64, 64],
            )

    def test_managed_heatmap_rejects_semantic_evidence_mismatches(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            model = HeatmapBlinkNet(base_channels=4)
            preprocessing = build_blink_preprocessing_contract()

            for mismatch, checkpoint_meta, expected_error in (
                (
                    "input_size",
                    {
                        "kind": "blink_heatmap_expert",
                        "parent_part": "Head",
                        "child_part": "Mandible",
                        "part_name": "Mandible",
                        "input_size": [32, 32],
                        "preprocessing": preprocessing,
                        "base_channels": 4,
                    },
                    "blink_input_size_evidence_mismatch",
                ),
                (
                    "preprocessing",
                    {
                        "kind": "blink_heatmap_expert",
                        "parent_part": "Head",
                        "child_part": "Mandible",
                        "part_name": "Mandible",
                        "input_size": [64, 64],
                        "preprocessing": {
                            **preprocessing,
                            "color_conversion": "rgb_passthrough",
                        },
                        "base_channels": 4,
                    },
                    "blink_preprocessing_evidence_mismatch",
                ),
            ):
                with self.subTest(mismatch=mismatch):
                    buffer = io.BytesIO()
                    torch.save(
                        {
                            "state_dict": model.state_dict(),
                            "meta": checkpoint_meta,
                        },
                        buffer,
                    )
                    published_path, manifest_path = self._publish_active_expert(
                        weights_dir,
                        run_id=f"blink-semantic-{mismatch}",
                        checkpoint_bytes=buffer.getvalue(),
                        expert_backend=ROUTE_BACKEND_HEATMAP_BLINK,
                    )
                    manager = self._manager(weights_dir)
                    route = {
                        "parent": "Head",
                        "child": "Mandible",
                        "enabled": True,
                        "expert_backend": ROUTE_BACKEND_HEATMAP_BLINK,
                        "expert_manifest": str(manifest_path),
                        "input_size": [64, 64],
                    }
                    checkpoint = manager.resolve_route_expert_checkpoint(route)
                    self.assertEqual(Path(checkpoint["path"]), published_path)
                    backend = manager._blink_backends().get(
                        ROUTE_BACKEND_HEATMAP_BLINK
                    )
                    with self.assertRaisesRegex(BlinkBackendError, expected_error):
                        backend._load_model(manager, checkpoint, route)
                    self.assertEqual(manager.loaded_experts, {})

    def test_managed_heatmap_rejects_route_size_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            model = HeatmapBlinkNet(base_channels=4)
            buffer = io.BytesIO()
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "meta": {
                        "kind": "blink_heatmap_expert",
                        "parent_part": "Head",
                        "child_part": "Mandible",
                        "part_name": "Mandible",
                        "input_size": [64, 64],
                        "preprocessing": build_blink_preprocessing_contract(),
                        "base_channels": 4,
                    },
                },
                buffer,
            )
            _published_path, manifest_path = self._publish_active_expert(
                weights_dir,
                run_id="blink-route-size-mismatch",
                checkpoint_bytes=buffer.getvalue(),
                expert_backend=ROUTE_BACKEND_HEATMAP_BLINK,
            )
            manager = self._manager(weights_dir)
            route = {
                "parent": "Head",
                "child": "Mandible",
                "enabled": True,
                "expert_backend": ROUTE_BACKEND_HEATMAP_BLINK,
                "expert_manifest": str(manifest_path),
                "input_size": [96, 96],
            }
            checkpoint = manager.resolve_route_expert_checkpoint(route)
            backend = manager._blink_backends().get(ROUTE_BACKEND_HEATMAP_BLINK)
            with self.assertRaisesRegex(
                BlinkBackendError,
                "blink_route_input_size_mismatch",
            ):
                backend._load_model(manager, checkpoint, route)

    def test_managed_resolution_reads_manifest_and_checkpoint_once(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            published_path, manifest_path = self._publish_active_expert(weights_dir)
            manager = self._manager(weights_dir)
            route = {
                "parent": "Head",
                "child": "Mandible",
                "enabled": True,
                "expert_backend": ROUTE_BACKEND_VIT_B_BLINK,
                "expert_manifest": str(manifest_path),
                "input_size": [64, 64],
            }
            from core import cascade_manager as cascade_module

            original_reader = cascade_module.read_bytes_bounded_in_root
            opened_paths = []

            def recording_reader(path, **kwargs):
                opened_paths.append(os.path.normcase(os.path.abspath(path)))
                return original_reader(path, **kwargs)

            with patch(
                "core.cascade_manager.read_bytes_bounded_in_root",
                side_effect=recording_reader,
            ):
                checkpoint = manager.resolve_route_expert_checkpoint(route)

            self.assertIsInstance(checkpoint, dict)
            self.assertEqual(
                opened_paths.count(os.path.normcase(os.path.abspath(manifest_path))),
                1,
            )
            self.assertEqual(
                opened_paths.count(os.path.normcase(os.path.abspath(published_path))),
                1,
            )

    def test_managed_backends_reject_cross_route_checkpoint_identity(self):
        for expert_backend in (
            ROUTE_BACKEND_VIT_B_BLINK,
            ROUTE_BACKEND_HEATMAP_BLINK,
        ):
            for identity_field, mismatched_value, expected_error in (
                (
                    "parent_part",
                    "Thorax",
                    "blink_checkpoint_parent_part_mismatch",
                ),
                (
                    "child_part",
                    "Eye",
                    "blink_checkpoint_child_part_mismatch",
                ),
            ):
                with self.subTest(
                    expert_backend=expert_backend,
                    identity_field=identity_field,
                ), tempfile.TemporaryDirectory() as tmp_dir:
                    weights_dir = Path(tmp_dir) / "weights"
                    identity = {
                        "parent_part": "Head",
                        "child_part": "Mandible",
                    }
                    identity[identity_field] = mismatched_value
                    checkpoint_bytes = self._serialize_contract_checkpoint(
                        expert_backend,
                        **identity,
                    )
                    _published_path, manifest_path = self._publish_active_expert(
                        weights_dir,
                        run_id=f"cross-{identity_field}",
                        checkpoint_bytes=checkpoint_bytes,
                        expert_backend=expert_backend,
                    )
                    manager = self._manager(weights_dir)
                    route = {
                        "parent": "Head",
                        "child": "Mandible",
                        "enabled": True,
                        "expert_backend": expert_backend,
                        "expert_manifest": str(manifest_path),
                        "input_size": [64, 64],
                    }
                    checkpoint = manager.resolve_route_expert_checkpoint(route)

                    self.assertIsInstance(checkpoint, dict)
                    with self.assertRaisesRegex(BlinkBackendError, expected_error):
                        self._load_contract_checkpoint(
                            manager,
                            expert_backend,
                            checkpoint,
                            route,
                        )
                    self.assertEqual(manager.loaded_experts, {})

    def test_managed_backends_revalidate_route_identity_on_cache_hit(self):
        for expert_backend in (
            ROUTE_BACKEND_VIT_B_BLINK,
            ROUTE_BACKEND_HEATMAP_BLINK,
        ):
            for route_field, mismatched_value, expected_error in (
                ("parent", "Thorax", "blink_route_parent_part_mismatch"),
                ("child", "Eye", "blink_route_child_part_mismatch"),
            ):
                with self.subTest(
                    expert_backend=expert_backend,
                    route_field=route_field,
                ), tempfile.TemporaryDirectory() as tmp_dir:
                    weights_dir = Path(tmp_dir) / "weights"
                    checkpoint_bytes = self._serialize_contract_checkpoint(
                        expert_backend
                    )
                    _published_path, manifest_path = self._publish_active_expert(
                        weights_dir,
                        run_id=f"cache-{route_field}",
                        checkpoint_bytes=checkpoint_bytes,
                        expert_backend=expert_backend,
                    )
                    manager = self._manager(weights_dir)
                    route = {
                        "parent": "Head",
                        "child": "Mandible",
                        "enabled": True,
                        "expert_backend": expert_backend,
                        "expert_manifest": str(manifest_path),
                        "input_size": [64, 64],
                    }
                    checkpoint = manager.resolve_route_expert_checkpoint(route)
                    first_model = self._load_contract_checkpoint(
                        manager,
                        expert_backend,
                        checkpoint,
                        route,
                    )

                    self.assertIsNotNone(first_model)
                    self.assertEqual(len(manager.loaded_experts), 1)
                    mismatched_route = dict(route)
                    mismatched_route[route_field] = mismatched_value
                    with self.assertRaisesRegex(BlinkBackendError, expected_error):
                        self._load_contract_checkpoint(
                            manager,
                            expert_backend,
                            checkpoint,
                            mismatched_route,
                        )
                    self.assertEqual(len(manager.loaded_experts), 1)

    def test_managed_backends_require_checkpoint_kind(self):
        for expert_backend in (
            ROUTE_BACKEND_VIT_B_BLINK,
            ROUTE_BACKEND_HEATMAP_BLINK,
        ):
            with self.subTest(
                expert_backend=expert_backend
            ), tempfile.TemporaryDirectory() as tmp_dir:
                weights_dir = Path(tmp_dir) / "weights"
                checkpoint_bytes = self._serialize_contract_checkpoint(
                    expert_backend,
                    include_kind=False,
                )
                _published_path, manifest_path = self._publish_active_expert(
                    weights_dir,
                    run_id="missing-kind",
                    checkpoint_bytes=checkpoint_bytes,
                    expert_backend=expert_backend,
                )
                manager = self._manager(weights_dir)
                route = {
                    "parent": "Head",
                    "child": "Mandible",
                    "enabled": True,
                    "expert_backend": expert_backend,
                    "expert_manifest": str(manifest_path),
                    "input_size": [64, 64],
                }
                checkpoint = manager.resolve_route_expert_checkpoint(route)

                self.assertIsInstance(checkpoint, dict)
                with self.assertRaisesRegex(
                    BlinkBackendError,
                    "blink_checkpoint_kind_missing",
                ):
                    self._load_contract_checkpoint(
                        manager,
                        expert_backend,
                        checkpoint,
                        route,
                    )
                self.assertEqual(manager.loaded_experts, {})

    def test_managed_v1_unbound_manifest_is_rejected(self):
        def unbind_legacy_manifest(manifest):
            manifest["schema_version"] = BLINK_EXPERT_MANIFEST_LEGACY_SCHEMA_VERSION
            manifest.pop("parent_part", None)
            manifest.pop("child_part", None)
            manifest.pop("preprocessing", None)
            return manifest

        for expert_backend in (
            ROUTE_BACKEND_VIT_B_BLINK,
            ROUTE_BACKEND_HEATMAP_BLINK,
        ):
            with self.subTest(
                expert_backend=expert_backend
            ), tempfile.TemporaryDirectory() as tmp_dir:
                weights_dir = Path(tmp_dir) / "weights"
                published_path, manifest_path = self._publish_active_expert(
                    weights_dir,
                    run_id="managed-v1-unbound",
                    checkpoint_bytes=self._serialize_contract_checkpoint(
                        expert_backend
                    ),
                    expert_backend=expert_backend,
                    manifest_transform=unbind_legacy_manifest,
                )
                manager = self._manager(weights_dir)
                route = {
                    "parent": "Head",
                    "child": "Mandible",
                    "enabled": True,
                    "expert_backend": expert_backend,
                    "expert_manifest": str(manifest_path),
                }

                self.assertIsNone(manager.resolve_route_expert_checkpoint(route))
                self.assertIsNone(manager.resolve_route_expert_path(route))
                self.assertEqual(
                    manager.get_route_block_reason(route),
                    "expert_model_missing",
                )
                self.assertNotIn(
                    str(published_path),
                    [item.get("path") for item in manager.list_available_experts()],
                )

    def test_reserved_expert_buckets_are_not_discovered_or_resolved(self):
        reserved_parts = (
            "training_runs",
            "EXPERT_NOTES.JSON",
            "Cascade_Routes.Json",
            ".TRAINING_WEIGHT_PUBLICATION.LOCK",
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            expert_root = weights_dir / "experts"
            reserved_paths = []
            for reserved_part in reserved_parts:
                expert_path = expert_root / reserved_part / "reserved.pth"
                expert_path.parent.mkdir(parents=True, exist_ok=True)
                expert_path.write_bytes(b"must not be routed")
                reserved_paths.append(str(expert_path))

            manager = self._manager(weights_dir)
            discovered_paths = [
                item.get("path") for item in manager.list_available_experts()
            ]
            for reserved_part, reserved_path in zip(
                reserved_parts,
                reserved_paths,
            ):
                with self.subTest(reserved_part=reserved_part):
                    self.assertNotIn(reserved_path, discovered_paths)
                    route = {
                        "parent": "Head",
                        "child": "Mandible",
                        "enabled": True,
                        "expert_id": f"{reserved_part}/reserved.pth",
                        "expert_part": reserved_part,
                        "expert_filename": "reserved.pth",
                        "expert_backend": ROUTE_BACKEND_VIT_B_BLINK,
                    }
                    self.assertIsNone(manager.resolve_route_expert_path(route))
                    self.assertEqual(
                        manager.get_route_block_reason(route),
                        "expert_model_missing",
                    )

                    reserved_child_route = dict(route)
                    reserved_child_route["child"] = reserved_part
                    self.assertEqual(
                        manager.get_route_block_reason(reserved_child_route),
                        "blink_route_child_part_unsafe_or_reserved",
                    )

    def test_vit_loader_validates_semantics_and_caches_by_manifest_digest(self):
        class TinyExpert(torch.nn.Module):
            def __init__(self, pretrained=False, image_size=224):
                super().__init__()
                self.image_size = int(image_size)
                self.weight = torch.nn.Parameter(torch.ones(1))

        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            preprocessing = build_blink_preprocessing_contract()

            def serialized_checkpoint(input_size):
                buffer = io.BytesIO()
                torch.save(
                    {
                        "state_dict": TinyExpert(image_size=input_size).state_dict(),
                        "meta": {
                            "kind": "blink_expert_locator",
                            "parent_part": "Head",
                            "child_part": "Mandible",
                            "part_name": "Mandible",
                            "input_size": [input_size, input_size],
                            "preprocessing": preprocessing,
                        },
                    },
                    buffer,
                )
                return buffer.getvalue()

            valid_bytes = serialized_checkpoint(64)
            _published_path, manifest_path = self._publish_active_expert(
                weights_dir,
                run_id="blink-vit-contract-valid",
                checkpoint_bytes=valid_bytes,
                expert_backend=ROUTE_BACKEND_VIT_B_BLINK,
            )
            manager = self._manager(weights_dir)
            route = {
                "parent": "Head",
                "child": "Mandible",
                "enabled": True,
                "expert_backend": ROUTE_BACKEND_VIT_B_BLINK,
                "expert_manifest": str(manifest_path),
                "input_size": [64, 64],
            }
            checkpoint = manager.resolve_route_expert_checkpoint(route)

            with patch("core.cascade_manager.MicroExpertLocator", TinyExpert):
                first_model = manager._load_expert(
                    "Mandible",
                    model_path=checkpoint["path"],
                    checkpoint_bytes=checkpoint["checkpoint_bytes"],
                    checkpoint_digest=checkpoint["digest"],
                    checkpoint_source=checkpoint["source"],
                    manifest_payload=checkpoint["manifest_payload"],
                    manifest_identity=checkpoint["manifest_identity"],
                    route_record=route,
                )

                second_manifest = json.loads(
                    checkpoint["manifest_payload"].decode("utf-8")
                )
                second_manifest["created_at"] = "2099-01-01T00:00:00"
                second_payload = json.dumps(
                    second_manifest,
                    sort_keys=True,
                ).encode("utf-8")
                second_identity = {
                    "size_bytes": len(second_payload),
                    "hash_algorithm": "sha256",
                    "digest": hashlib.sha256(second_payload).hexdigest(),
                }
                second_model = manager._load_expert(
                    "Mandible",
                    model_path=checkpoint["path"],
                    checkpoint_bytes=checkpoint["checkpoint_bytes"],
                    checkpoint_digest=checkpoint["digest"],
                    checkpoint_source=checkpoint["source"],
                    manifest_payload=second_payload,
                    manifest_identity=second_identity,
                    route_record=route,
                )

            self.assertIsNot(first_model, second_model)
            self.assertEqual(first_model._taxamask_meta["input_size"], [64, 64])
            self.assertEqual(len(manager.loaded_experts), 2)
            self.assertTrue(
                any(
                    checkpoint["manifest_identity"]["digest"] in key
                    for key in manager.loaded_experts
                )
            )
            self.assertTrue(
                any(second_identity["digest"] in key for key in manager.loaded_experts)
            )

            mismatch_bytes = serialized_checkpoint(32)
            mismatch_digest = hashlib.sha256(mismatch_bytes).hexdigest()
            with patch("core.cascade_manager.MicroExpertLocator", TinyExpert):
                with self.assertRaisesRegex(
                    BlinkBackendError,
                    "blink_input_size_evidence_mismatch",
                ):
                    manager._load_expert(
                        "Mandible",
                        model_path=checkpoint["path"],
                        checkpoint_bytes=mismatch_bytes,
                        checkpoint_digest=mismatch_digest,
                        checkpoint_source=checkpoint["source"],
                        manifest_payload=checkpoint["manifest_payload"],
                        manifest_identity=checkpoint["manifest_identity"],
                        route_record=route,
                    )

    def test_vit_loader_accepts_legacy_v1_manifest_without_preprocessing(self):
        class TinyExpert(torch.nn.Module):
            def __init__(self, pretrained=False, image_size=224):
                super().__init__()
                self.image_size = int(image_size)
                self.weight = torch.nn.Parameter(torch.ones(1))

        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            model_path = weights_dir / "experts" / "Eye" / "expert_v1.pth"
            model_path.parent.mkdir(parents=True)
            buffer = io.BytesIO()
            torch.save(
                {
                    "state_dict": TinyExpert(image_size=64).state_dict(),
                    "meta": {
                        "kind": "blink_expert_locator",
                        "input_size": [64, 64],
                    },
                },
                buffer,
            )
            checkpoint_bytes = buffer.getvalue()
            model_path.write_bytes(checkpoint_bytes)
            legacy_manifest = build_blink_expert_manifest(
                str(model_path),
                parent_part="Head",
                child_part="Eye",
                input_size=(64, 64),
            )
            legacy_manifest["schema_version"] = (
                BLINK_EXPERT_MANIFEST_LEGACY_SCHEMA_VERSION
            )
            legacy_manifest.pop("preprocessing")
            manifest_payload = json.dumps(legacy_manifest).encode("utf-8")
            manifest_identity = {
                "size_bytes": len(manifest_payload),
                "hash_algorithm": "sha256",
                "digest": hashlib.sha256(manifest_payload).hexdigest(),
            }
            manager = self._manager(weights_dir)
            with patch("core.cascade_manager.MicroExpertLocator", TinyExpert):
                model = manager._load_expert(
                    "Eye",
                    model_path=str(model_path),
                    checkpoint_bytes=checkpoint_bytes,
                    checkpoint_digest=hashlib.sha256(checkpoint_bytes).hexdigest(),
                    checkpoint_source="legacy_manifest_compatibility",
                    manifest_payload=manifest_payload,
                    manifest_identity=manifest_identity,
                    route_record={"input_size": [64, 64]},
                )
            self.assertIsNotNone(model)
            self.assertEqual(model._taxamask_meta["input_size"], [64, 64])

    def test_legacy_heatmap_cache_identity_includes_checkpoint_digest(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            expert_path = weights_dir / "experts" / "Eye" / "heatmap_v1.pth"
            expert_path.parent.mkdir(parents=True)

            def serialized_model(fill_value):
                model = HeatmapBlinkNet(base_channels=4)
                for parameter in model.parameters():
                    torch.nn.init.constant_(parameter, fill_value)
                buffer = io.BytesIO()
                torch.save(
                    {
                        "state_dict": model.state_dict(),
                        "meta": {
                            "kind": "blink_heatmap_expert",
                            "input_size": [64, 64],
                            "base_channels": 4,
                        },
                    },
                    buffer,
                )
                return buffer.getvalue()

            first_bytes = serialized_model(0.0)
            second_bytes = serialized_model(0.25)
            expert_path.write_bytes(first_bytes)
            manager = self._manager(weights_dir)
            route = {
                "parent": "Head",
                "child": "Eye",
                "enabled": True,
                "expert_id": "Eye/heatmap_v1.pth",
                "expert_part": "Eye",
                "expert_filename": "heatmap_v1.pth",
                "expert_backend": ROUTE_BACKEND_HEATMAP_BLINK,
                "input_size": [64, 64],
            }
            backend = manager._blink_backends().get(ROUTE_BACKEND_HEATMAP_BLINK)

            first_record = manager.resolve_route_expert_checkpoint(route)
            first_model = backend._load_model(manager, first_record, route)
            expert_path.write_bytes(second_bytes)
            second_record = manager.resolve_route_expert_checkpoint(route)
            second_model = backend._load_model(manager, second_record, route)

            self.assertNotEqual(first_record["digest"], second_record["digest"])
            self.assertIsNot(first_model, second_model)
            self.assertEqual(len(manager.loaded_experts), 2)
            self.assertTrue(
                any(key.endswith(first_record["digest"]) for key in manager.loaded_experts)
            )
            self.assertTrue(
                any(key.endswith(second_record["digest"]) for key in manager.loaded_experts)
            )

    def test_external_manifest_is_rejected_without_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            legacy_path = weights_dir / "experts" / "Mandible" / "expert_v1.pth"
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_bytes(b"legacy fallback must not be selected")
            external_path = Path(tmp_dir) / "outside.pth"
            external_path.write_bytes(b"outside")
            external_manifest = Path(tmp_dir) / "outside.manifest.json"
            external_manifest.write_text(
                json.dumps(
                    build_blink_expert_manifest(
                        str(external_path),
                        parent_part="Head",
                        child_part="Mandible",
                    )
                ),
                encoding="utf-8",
            )
            manager = self._manager(weights_dir)
            route = {
                "parent": "Head",
                "child": "Mandible",
                "enabled": True,
                "expert_id": "Mandible/expert_v1.pth",
                "expert_manifest": str(external_manifest),
            }

            self.assertIsNone(manager.resolve_route_expert_path(route))
            self.assertEqual(manager.get_route_block_reason(route), "expert_model_missing")

    def test_active_bundle_rejects_same_size_checkpoint_and_manifest_tampering(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            published_path, manifest_path = self._publish_active_expert(weights_dir)
            manager = self._manager(weights_dir)
            route = {
                "parent": "Head",
                "child": "Mandible",
                "enabled": True,
                "expert_id": f"Mandible/{published_path.name}",
                "expert_manifest": str(manifest_path),
            }
            original_checkpoint = published_path.read_bytes()
            original_manifest = manifest_path.read_bytes()
            tampered_checkpoint = bytes([original_checkpoint[0] ^ 0x01]) + original_checkpoint[1:]
            tampered_manifest = original_manifest.replace(b'"Head"', b'"Hedd"', 1)
            self.assertEqual(len(tampered_checkpoint), len(original_checkpoint))
            self.assertEqual(len(tampered_manifest), len(original_manifest))
            self.assertNotEqual(tampered_manifest, original_manifest)

            for target, original, tampered in (
                (published_path, original_checkpoint, tampered_checkpoint),
                (manifest_path, original_manifest, tampered_manifest),
            ):
                with self.subTest(target=target):
                    target.write_bytes(tampered)
                    self.assertIsNone(manager.resolve_route_expert_path(route))
                    self.assertNotIn(
                        str(published_path),
                        [item.get("path") for item in manager.list_available_experts()],
                    )
                    target.write_bytes(original)
                    self.assertEqual(
                        Path(manager.resolve_route_expert_path(route)),
                        published_path,
                    )

    def test_manifest_weights_main_rejects_traversal_and_external_paths(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            expert_path, manifest_path = self._write_managed_expert(weights_dir)
            manager = self._manager(weights_dir)
            route = {
                "parent": "Head",
                "child": "Mandible",
                "enabled": True,
                "expert_id": f"Mandible/{expert_path.name}",
                "expert_manifest": str(manifest_path),
            }
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))

            for unsafe_main in ("../expert_v1.pth", str(Path(tmp_dir) / "outside.pth")):
                with self.subTest(unsafe_main=unsafe_main):
                    payload["weights"]["main"] = unsafe_main
                    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
                    self.assertIsNone(manager.resolve_route_expert_path(route))

    def test_symlink_manifest_and_checkpoint_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            expert_path, manifest_path = self._write_managed_expert(weights_dir)
            manager = self._manager(weights_dir)
            route = {
                "parent": "Head",
                "child": "Mandible",
                "enabled": True,
                "expert_id": f"Mandible/{expert_path.name}",
            }
            linked_manifest = manifest_path.with_name("linked.manifest.json")
            try:
                os.symlink(manifest_path, linked_manifest)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"filesystem symlinks unavailable: {exc}")
            route["expert_manifest"] = str(linked_manifest)
            self.assertIsNone(manager.resolve_route_expert_path(route))

            linked_weights = expert_path.with_name("linked.pth")
            os.symlink(expert_path, linked_weights)
            linked_weights_manifest = linked_weights.with_suffix(".manifest.json")
            linked_weights_manifest.write_text(
                json.dumps(
                    build_blink_expert_manifest(
                        str(linked_weights),
                        parent_part="Head",
                        child_part="Mandible",
                    )
                ),
                encoding="utf-8",
            )
            route["expert_manifest"] = str(linked_weights_manifest)
            self.assertIsNone(manager.resolve_route_expert_path(route))

    def test_reparse_flag_on_manifest_or_checkpoint_is_rejected(self):
        class _ReparseStat:
            def __init__(self, source):
                self._source = source
                self.st_file_attributes = 0x400

            def __getattr__(self, name):
                return getattr(self._source, name)

        with tempfile.TemporaryDirectory() as tmp_dir:
            weights_dir = Path(tmp_dir) / "weights"
            expert_path, manifest_path = self._write_managed_expert(weights_dir)
            manager = self._manager(weights_dir)
            route = {
                "parent": "Head",
                "child": "Mandible",
                "enabled": True,
                "expert_id": f"Mandible/{expert_path.name}",
                "expert_manifest": str(manifest_path),
            }
            original_lstat = os.lstat

            for flagged_path in (manifest_path, expert_path):
                flagged_key = os.path.normcase(os.path.abspath(flagged_path))

                def guarded_lstat(path, *, _flagged_key=flagged_key):
                    observed = original_lstat(path)
                    if os.path.normcase(os.path.abspath(path)) == _flagged_key:
                        return _ReparseStat(observed)
                    return observed

                with self.subTest(flagged_path=flagged_path), patch(
                    "core.cascade_manager.os.lstat",
                    side_effect=guarded_lstat,
                ):
                    self.assertIsNone(manager.resolve_route_expert_path(route))


if __name__ == "__main__":
    unittest.main()
