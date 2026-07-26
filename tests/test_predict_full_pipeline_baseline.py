# pyright: reportMissingImports=false

import contextlib
import inspect
import io
import json
import math
import os
import statistics
import sys
import tempfile
import time
import tracemalloc
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AntSleap.core.engine import AntEngine


BASELINE_PATH = Path(__file__).parent / "baselines" / "predict_full_pipeline_v1.json"


class _FixedLocator:
    def __init__(self, channels):
        self.channels = list(channels)

    def eval(self):
        return self

    def __call__(self, tensor):
        height, width = int(tensor.shape[-2]), int(tensor.shape[-1])
        heatmaps = torch.zeros((1, len(self.channels), height, width), dtype=torch.float32)
        box_sizes = torch.zeros((1, len(self.channels), 2), dtype=torch.float32)
        for index, channel in enumerate(self.channels):
            x, y = channel["peak_xy"]
            heatmaps[0, index, min(height - 1, int(y)), min(width - 1, int(x))] = float(channel["peak"])
            box_sizes[0, index] = torch.tensor(channel["wh"], dtype=torch.float32)
        return heatmaps, box_sizes


class _FakeSAMModel:
    def eval(self):
        return self


class _TracingSAMPredictor:
    RAW_POLYGON = np.array(
        [[2.0, 3.0], [12.0, 3.0], [12.0, 13.0], [2.0, 13.0]],
        dtype=np.float32,
    )

    def __init__(self, succeeds=True):
        self.succeeds = bool(succeeds)
        self.calls = []

    def predict(self, image_input, bboxes, **_kwargs):
        self.calls.append(
            {
                "crop_size": [int(image_input.size[0]), int(image_input.size[1])],
                "prompt_box": [float(value) for value in bboxes[0]],
                "raw_mask": self.RAW_POLYGON.tolist() if self.succeeds else None,
            }
        )
        if not self.succeeds:
            return []
        masks = types.SimpleNamespace(xy=[self.RAW_POLYGON.copy()])
        return [types.SimpleNamespace(masks=masks)]


class _FakePartsModel:
    def __init__(self, sam_succeeds=True):
        self.sam_model = _FakeSAMModel()
        self.ultralytics_sam = _TracingSAMPredictor(succeeds=sam_succeeds)


class _FixedCascadeManager:
    def __init__(self, expert_confidence=0.82, route_min_confidence=0.75):
        self.expert_box = [40.0, 25.0, 58.0, 45.0]
        self.expert_confidence = float(expert_confidence)
        self.route_min_confidence = float(route_min_confidence)
        self.calls = []
        self.empty_manifest = {"version": "", "routes": []}

    def get_runtime_route_manifest(self, project_route_manifest=None):
        return project_route_manifest if isinstance(project_route_manifest, dict) else self.empty_manifest

    def routes_ready(self, route_manifest=None):
        manifest = route_manifest if isinstance(route_manifest, dict) else self.empty_manifest
        return any(bool(route.get("enabled")) for route in manifest.get("routes", []))

    def _find_route(self, parent_part, child_part_name, route_manifest=None):
        manifest = route_manifest if isinstance(route_manifest, dict) else self.empty_manifest
        for route in manifest.get("routes", []):
            if (
                route.get("parent") == parent_part
                and route.get("child") == child_part_name
                and route.get("enabled")
            ):
                return route
        return None

    def resolve_route_for_child(self, child_part_name, available_parents, route_manifest=None):
        for parent_part in available_parents:
            route = self._find_route(parent_part, child_part_name, route_manifest=route_manifest)
            if route is not None:
                return route
        return None

    def get_route_block_reason(self, route):
        return None if route and route.get("expert_id") else "expert_unappointed"

    def get_route_min_conf(self, _parent_part, _child_part_name, route_manifest=None):
        return self.route_min_confidence

    def describe_route(self, route):
        return f"{route.get('parent')}->{route.get('child')} [{route.get('expert_id')}]"

    def infer_child_part(
        self,
        image_path,
        parent_box,
        child_part_name,
        parent_part="macro_locator",
        route_manifest=None,
    ):
        self.calls.append(
            {
                "image_name": Path(image_path).name,
                "parent_box": [float(value) for value in parent_box],
                "parent_part": str(parent_part),
                "child_part": str(child_part_name),
            }
        )
        return {"box": list(self.expert_box), "confidence": self.expert_confidence}


PROJECT_ROUTE_MANIFEST = {
    "version": "pipeline-baseline-v1",
    "routes": [
        {
            "parent": "Head",
            "child": "Mandible",
            "enabled": True,
            "expert_id": "Mandible/baseline-v1.pth",
            "expert_part": "Mandible",
            "expert_filename": "baseline-v1.pth",
            "expert_backend": "vit_b_blink",
            "expert_manifest": "experts/mandible_v1.json",
        }
    ],
}


SCENARIOS = {
    "normal_locator_weak_peak_expert_accepted_sam_success": {
        "image_size": (100, 80),
        "channels": [
            {"peak_xy": (32, 28), "peak": 0.875, "wh": (0.2, 0.25)},
            {"peak_xy": (40, 30), "peak": 0.05, "wh": (0.3, 0.3)},
        ],
        "taxonomy": ["Head", "Mesosoma", "Mandible"],
        "locator_scope": ["Head", "Mesosoma"],
        "route_manifest": PROJECT_ROUTE_MANIFEST,
        "expert_confidence": 0.82,
        "sam_succeeds": True,
    },
    "expert_rejected": {
        "image_size": (100, 80),
        "channels": [{"peak_xy": (32, 28), "peak": 0.875, "wh": (0.2, 0.25)}],
        "taxonomy": ["Head", "Mandible"],
        "locator_scope": ["Head"],
        "route_manifest": PROJECT_ROUTE_MANIFEST,
        "expert_confidence": 0.2,
        "sam_succeeds": True,
    },
    "sam_failure": {
        "image_size": (100, 80),
        "channels": [{"peak_xy": (32, 28), "peak": 0.875, "wh": (0.2, 0.25)}],
        "taxonomy": ["Head"],
        "locator_scope": ["Head"],
        "route_manifest": None,
        "sam_succeeds": False,
    },
    "invalid_locator_box_size_is_sanitized": {
        "image_size": (100, 80),
        "channels": [{"peak_xy": (32, 28), "peak": 0.75, "wh": (-1.0, 0.0)}],
        "taxonomy": ["Head"],
        "locator_scope": ["Head"],
        "route_manifest": None,
        "sam_succeeds": True,
    },
    "crop_too_small": {
        "image_size": (1, 1),
        "channels": [{"peak_xy": (32, 28), "peak": 0.875, "wh": (0.2, 0.25)}],
        "taxonomy": ["Head"],
        "locator_scope": ["Head"],
        "route_manifest": None,
        "sam_succeeds": True,
    },
}


def _polygon_summary(polygon):
    if not polygon:
        return None
    points = np.asarray(polygon, dtype=np.float64)
    shifted = np.roll(points, -1, axis=0)
    area = 0.5 * abs(float(np.sum(points[:, 0] * shifted[:, 1] - points[:, 1] * shifted[:, 0])))
    return {
        "vertex_count": int(len(points)),
        "bounds": [
            float(points[:, 0].min()),
            float(points[:, 1].min()),
            float(points[:, 0].max()),
            float(points[:, 1].max()),
        ],
        "area": area,
    }


def _run_scenario(name, device="cpu"):
    scenario = SCENARIOS[name]
    with tempfile.TemporaryDirectory() as tmp_dir:
        image_path = Path(tmp_dir) / "synthetic_specimen.png"
        Image.new("RGB", scenario["image_size"], color=(173, 181, 189)).save(image_path)

        engine = AntEngine.__new__(AntEngine)
        engine.device = device
        engine.locator_resolution = (64, 64)
        engine.locator = _FixedLocator(scenario["channels"])
        engine.parts_model = _FakePartsModel(sam_succeeds=scenario["sam_succeeds"])
        engine.cascade_manager = _FixedCascadeManager(
            expert_confidence=scenario.get("expert_confidence", 0.82),
        )

        stdout = io.StringIO()
        runtime_events = []

        def capture_event(event, **fields):
            runtime_events.append({"event": str(event), **fields})

        if str(device).startswith("cuda"):
            torch.cuda.synchronize()
        started = time.perf_counter()
        with patch(
            "AntSleap.core.prediction_pipeline.runtime_log_event",
            side_effect=capture_event,
        ), contextlib.redirect_stdout(stdout):
            result = engine.predict_full_pipeline(
                str(image_path),
                current_taxonomy=scenario["taxonomy"],
                locator_scope=scenario["locator_scope"],
                conf_thresh=0.1,
                adapt_thresh=0.4,
                box_pad=0.4,
                noise_floor=0.15,
                poly_epsilon=0.0,
                project_route_manifest=scenario["route_manifest"],
                model_profile_context={
                    "active_profile_id": "pipeline-baseline-profile",
                    "parent_backend": "builtin_locator_sam",
                    "prediction_run_id": "predict_baseline_001",
                    "image_uid": "image_baseline_001",
                    "specimen_id": "specimen_baseline_001",
                },
            )
        if str(device).startswith("cuda"):
            torch.cuda.synchronize()
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        stdout_text = stdout.getvalue()
        log_lines = [
            json.dumps(event, ensure_ascii=True, sort_keys=True)
            for event in runtime_events
        ]
        raw_log = "\n".join(log_lines)
        if raw_log:
            raw_log += "\n"
        polygons = {part: _polygon_summary(polygon) for part, polygon in sorted(result["polygons"].items())}
        sam_calls = [
            {
                "crop_size": call["crop_size"],
                "prompt_box": call["prompt_box"],
                "raw_mask_summary": _polygon_summary(call["raw_mask"]),
            }
            for call in engine.parts_model.ultralytics_sam.calls
        ]
        return (
            {
                "result": result,
                "polygon_summary": polygons,
                "sam_calls": sam_calls,
                "expert_calls": engine.cascade_manager.calls,
                "log": {
                    "line_count": len(log_lines),
                    "utf8_bytes": len(raw_log.encode("utf-8")),
                    "lines": log_lines,
                    "event_names": [event["event"] for event in runtime_events],
                    "stdout": stdout_text,
                },
            },
            elapsed_ms,
        )


def _nested_close(
    test_case,
    actual,
    expected,
    path,
    float_abs_tol,
    geometry_abs_tol,
    relative_tol,
):
    if isinstance(expected, dict):
        test_case.assertIsInstance(actual, dict, path)
        actual_keys = set(actual)
        expected_keys = set(expected)
        if path.endswith(".result.meta"):
            test_case.assertTrue(
                expected_keys.issubset(actual_keys),
                f"{path}: missing baseline keys {sorted(expected_keys - actual_keys)}",
            )
        else:
            test_case.assertEqual(actual_keys, expected_keys, path)
        for key in expected:
            _nested_close(
                test_case,
                actual[key],
                expected[key],
                f"{path}.{key}",
                float_abs_tol,
                geometry_abs_tol,
                relative_tol,
            )
        return
    if isinstance(expected, list):
        test_case.assertIsInstance(actual, list, path)
        test_case.assertEqual(len(actual), len(expected), path)
        for index, expected_item in enumerate(expected):
            _nested_close(
                test_case,
                actual[index],
                expected_item,
                f"{path}[{index}]",
                float_abs_tol,
                geometry_abs_tol,
                relative_tol,
            )
        return
    if isinstance(expected, bool):
        test_case.assertIsInstance(actual, bool, path)
        test_case.assertEqual(actual, expected, path)
        return
    if isinstance(expected, int):
        test_case.assertIsInstance(actual, int, path)
        test_case.assertNotIsInstance(actual, bool, path)
        test_case.assertEqual(actual, expected, path)
        return
    if isinstance(expected, float):
        test_case.assertIsInstance(actual, (int, float), path)
        test_case.assertNotIsInstance(actual, bool, path)
        tolerance = geometry_abs_tol if any(
            marker in path for marker in ("auto_boxes", "polygons", "bounds", "prompt_box", "parent_box")
        ) else float_abs_tol
        test_case.assertTrue(
            math.isclose(float(actual), float(expected), rel_tol=relative_tol, abs_tol=tolerance),
            f"{path}: {actual!r} differs from {expected!r} by more than {tolerance}",
        )
        return
    test_case.assertEqual(actual, expected, path)


def _measure_case(name, warmup_runs, measured_runs, device="cpu"):
    for _ in range(warmup_runs):
        _run_scenario(name, device=device)
    snapshots = []
    elapsed_samples_ms = []
    if str(device).startswith("cuda"):
        torch.cuda.reset_peak_memory_stats()
    tracemalloc.start()
    for _ in range(measured_runs):
        snapshot, elapsed_ms = _run_scenario(name, device=device)
        snapshots.append(snapshot)
        elapsed_samples_ms.append(elapsed_ms)
    _current_bytes, peak_python_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "scenario": name,
        "device": str(device),
        "elapsed_samples_ms": elapsed_samples_ms,
        "median_elapsed_ms": statistics.median(elapsed_samples_ms),
        "peak_python_mib": peak_python_bytes / (1024 * 1024),
        "peak_cuda_mib": (
            torch.cuda.max_memory_allocated() / (1024 * 1024)
            if str(device).startswith("cuda")
            else 0.0
        ),
        "log_observations": [snapshot["log"] for snapshot in snapshots],
    }


class PredictFullPipelineBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    def test_baseline_contract_identity_is_frozen(self):
        self.assertEqual(
            self.baseline["schema_version"],
            "taxamask_predict_full_pipeline_baseline_v1",
        )
        self.assertEqual(self.baseline["status"], "frozen")

    def test_public_signature_is_frozen(self):
        signature = inspect.signature(AntEngine.predict_full_pipeline)
        self.assertEqual(
            list(signature.parameters),
            [
                "self",
                "image_path",
                "current_taxonomy",
                "locator_scope",
                "conf_thresh",
                "adapt_thresh",
                "box_pad",
                "noise_floor",
                "poly_epsilon",
                "project_route_manifest",
                "model_profile_context",
            ],
        )
        self.assertEqual(signature.parameters["conf_thresh"].default, 0.1)
        self.assertEqual(signature.parameters["adapt_thresh"].default, 0.4)
        self.assertEqual(signature.parameters["box_pad"].default, 0.4)
        self.assertEqual(signature.parameters["noise_floor"].default, 0.15)
        self.assertEqual(signature.parameters["poly_epsilon"].default, 2.0)

    def test_frozen_scenarios_match_public_result_and_diagnostic_baseline(self):
        tolerances = self.baseline["tolerances"]
        for scenario_name, expected in self.baseline["scenarios"].items():
            with self.subTest(scenario=scenario_name):
                actual, _elapsed_ms = _run_scenario(scenario_name)
                strict_actual = {key: value for key, value in actual.items() if key != "log"}
                _nested_close(
                    self,
                    strict_actual,
                    expected,
                    scenario_name,
                    float(tolerances["float_abs"]),
                    float(tolerances["geometry_abs"]),
                    float(tolerances["relative"]),
                )

    def test_baseline_covers_required_success_and_failure_routes(self):
        required = {
            "normal_locator_weak_peak_expert_accepted_sam_success",
            "expert_rejected",
            "sam_failure",
            "invalid_locator_box_size_is_sanitized",
            "crop_too_small",
        }
        self.assertEqual(set(self.baseline["scenarios"]), required)

        normal = self.baseline["scenarios"]["normal_locator_weak_peak_expert_accepted_sam_success"]
        self.assertIn("Head", normal["result"]["auto_boxes"])
        self.assertNotIn("Mesosoma", normal["result"]["auto_boxes"])
        self.assertIn("Mandible", normal["result"]["auto_boxes"])
        self.assertEqual(normal["result"]["meta"]["cascade_applied_count"], 1)

        rejected = self.baseline["scenarios"]["expert_rejected"]
        self.assertEqual(
            rejected["result"]["meta"]["cascade_block_reasons"]["Mandible"],
            "confidence_below_gate",
        )
        self.assertNotIn("Mandible", rejected["result"]["auto_boxes"])

        failed = self.baseline["scenarios"]["sam_failure"]
        self.assertEqual(failed["result"]["polygons"], {})
        self.assertIn("Head", failed["result"]["auto_boxes"])

        tiny = self.baseline["scenarios"]["crop_too_small"]
        self.assertEqual(tiny["result"]["auto_boxes"], {})
        self.assertEqual(tiny["sam_calls"], [])

    def test_probe_records_timing_and_stable_log_volume_without_absolute_performance_gate(self):
        protocol = self.baseline["measurement_protocol"]
        self.assertEqual(protocol["performance_gate"], "comparison_only")
        self.assertNotIn("max_elapsed_ms", protocol)
        report = _measure_case(
            protocol["scenario"],
            int(protocol["warmup_runs"]),
            int(protocol["measured_runs"]),
        )
        self.assertEqual(len(report["elapsed_samples_ms"]), int(protocol["measured_runs"]))
        self.assertTrue(all(sample >= 0.0 for sample in report["elapsed_samples_ms"]))
        self.assertTrue(report["log_observations"])
        first_observation = report["log_observations"][0]
        self.assertGreater(first_observation["line_count"], 0)
        self.assertLessEqual(first_observation["line_count"], 16)
        self.assertGreater(first_observation["utf8_bytes"], 0)
        self.assertLess(first_observation["utf8_bytes"], 8192)
        self.assertEqual(first_observation["stdout"], "")
        self.assertIn("prediction_begin", first_observation["event_names"])
        self.assertIn("prediction_locator_candidate_skipped", first_observation["event_names"])
        self.assertIn("prediction_route_decision", first_observation["event_names"])
        self.assertIn("prediction_sam_result", first_observation["event_names"])
        self.assertEqual(first_observation["event_names"][-1], "prediction_complete")
        for observation in report["log_observations"]:
            self.assertEqual(
                set(observation),
                {"line_count", "utf8_bytes", "lines", "event_names", "stdout"},
            )
            self.assertIsInstance(observation["line_count"], int)
            self.assertIsInstance(observation["utf8_bytes"], int)
            self.assertIsInstance(observation["lines"], list)
            self.assertGreaterEqual(observation["utf8_bytes"], 0)
            self.assertEqual(observation["line_count"], len(observation["lines"]))
            self.assertTrue(all(isinstance(line, str) for line in observation["lines"]))
            self.assertEqual(observation["event_names"], first_observation["event_names"])
            self.assertLess(observation["utf8_bytes"], 8192)
            self.assertNotIn(str(PROJECT_ROOT), "\n".join(observation["lines"]))
            self.assertNotIn("raw_mask", "\n".join(observation["lines"]))

    def test_detailed_logging_adds_box_summary_without_arrays(self):
        with patch.dict(os.environ, {"TAXAMASK_PREDICTION_DIAGNOSTICS": "1"}):
            snapshot, _elapsed_ms = _run_scenario(
                "normal_locator_weak_peak_expert_accepted_sam_success"
            )
        joined = "\n".join(snapshot["log"]["lines"])
        self.assertIn('"box":', joined)
        self.assertNotIn("raw_mask", joined)
        self.assertLess(snapshot["log"]["utf8_bytes"], 8192)

    def test_structured_events_explain_rejection_and_missing_polygon(self):
        rejected, _elapsed_ms = _run_scenario("expert_rejected")
        rejected_events = [json.loads(line) for line in rejected["log"]["lines"]]
        self.assertTrue(
            any(
                event["event"] == "prediction_route_decision"
                and event.get("part") == "Mandible"
                and event.get("reason") == "confidence_below_gate"
                for event in rejected_events
            )
        )

        failed, _elapsed_ms = _run_scenario("sam_failure")
        failed_events = [json.loads(line) for line in failed["log"]["lines"]]
        self.assertTrue(
            any(
                event["event"] == "prediction_sam_result"
                and event.get("part") == "Head"
                and event.get("status") == "no_polygon"
                for event in failed_events
            )
        )
        self.assertIn("Head", failed["result"]["auto_boxes"])


def _print_measurement_report():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    protocol = baseline["measurement_protocol"]
    reports = {
        "cpu": _measure_case(
            protocol["scenario"],
            int(protocol["warmup_runs"]),
            int(protocol["measured_runs"]),
            device="cpu",
        )
    }
    if torch.cuda.is_available():
        reports["cuda_orchestration"] = _measure_case(
            protocol["scenario"],
            int(protocol["warmup_runs"]),
            int(protocol["measured_runs"]),
            device="cuda:0",
        )
    print(json.dumps(reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if "--measure" in sys.argv:
        _print_measurement_report()
    else:
        unittest.main()
