from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RESULT_PREFIX = "ROUND4_BENCHMARK_JSON="


class BenchmarkConfigManager:
    def __init__(self):
        self.values = {
            "language": "en",
            "runtime_device": "cpu",
            "theme": "dark",
            "last_project_path": "",
            "startup_behavior": "start_center",
        }

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def save(self):
        return None


class BenchmarkSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback, *_args, **_kwargs):
        self.callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self.callbacks):
            callback(*args, **kwargs)


class BenchmarkThread:
    def __init__(self):
        self.started = BenchmarkSignal()
        self._running = False

    def start(self):
        self._running = True
        self.started.emit()

    def isRunning(self):
        return self._running

    def quit(self):
        self._running = False

    def wait(self, _timeout=None):
        return True


class BenchmarkSamWorker:
    def __init__(self, *args, **kwargs):
        self.model = None
        self.device_preference = kwargs.get("device", "cpu")
        self.mask_generated = BenchmarkSignal()
        self.model_loaded = BenchmarkSignal()
        self.model_load_error = BenchmarkSignal()
        self.prompt_failed = BenchmarkSignal()

    def moveToThread(self, thread):
        self.thread = thread

    def load_model(self):
        self.model = object()
        self.model_loaded.emit()

    def set_epsilon(self, _value):
        return None

    def reload_base_model(self):
        return None

    def load_decoder_weights(self, _path):
        return None


class BenchmarkCascadeManager:
    def list_available_experts(self):
        return []

    def get_route_block_reason(self, _route):
        return "expert_unappointed"


class BenchmarkEngine:
    def __init__(self, *args, **kwargs):
        self.weights_dir = tempfile.mkdtemp(prefix="taxamask_round4_weights_")
        self.locator = None
        self.parts_model = None
        self.cascade_manager = BenchmarkCascadeManager()
        self.current_num_classes = int(kwargs.get("num_classes", 3) or 3)
        self.locator_resolution = (512, 512)
        self.loaded_locator_requires_legacy_confirmation = False
        self.loaded_locator_is_legacy_512 = False
        self.loaded_locator_timestamp = None
        self.device_preference = kwargs.get("device", "cpu")
        self.device = "cpu"

    def set_device_preference(self, preference):
        self.device_preference = preference
        return False

    def rebuild_locator(self, num_classes, _learning_rate, _weight_decay):
        self.current_num_classes = int(num_classes)

    def update_hyperparameters(self, _learning_rate, _weight_decay):
        return None

    def ensure_locator_loaded(self):
        if self.locator is None:
            self.locator = object()
        return self.locator

    def ensure_parts_model_loaded(self):
        if self.parts_model is None:
            self.parts_model = type("BenchmarkPartsModel", (), {"ultralytics_sam": None})()
        return self.parts_model

    def load_locator(self, timestamp):
        self.ensure_locator_loaded()
        self.loaded_locator_timestamp = timestamp

    def load_sam_decoder(self, _timestamp):
        return None

    def reset_locator_to_base(self):
        self.ensure_locator_loaded()

    def reset_sam_to_base(self):
        return None


class BenchmarkDatabase:
    def query_trait_description(self, _genus_name, _part_name):
        return ""


def _rss_mb() -> float:
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def _measure(callback, app) -> float:
    started = time.perf_counter()
    callback()
    app.processEvents()
    return (time.perf_counter() - started) * 1000.0


def _part_items(tree, role):
    items = []
    for top_index in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(top_index)
        if top.data(0, role):
            items.append(top)
        for child_index in range(top.childCount()):
            child = top.child(child_index)
            if child.data(0, role):
                items.append(child)
    return items


def _child_benchmark(workspace: Path) -> dict[str, object]:
    child_started = time.perf_counter()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-gpu-compositing")
    os.environ["TAXAMASK_ENABLE_TIF_WORKFLOW"] = "1"

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    import AntSleap.main as main_module
    from PIL import Image
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget

    import_ms = (time.perf_counter() - child_started) * 1000.0
    app = QApplication.instance() or QApplication([])
    output_root = workspace / "TaxaMask_outputs"

    with ExitStack() as stack:
        stack.enter_context(patch.object(main_module, "ConfigManager", BenchmarkConfigManager))
        stack.enter_context(patch.object(main_module, "AntEngine", BenchmarkEngine))
        stack.enter_context(patch.object(main_module, "MultiModalDB", BenchmarkDatabase))
        stack.enter_context(patch.object(main_module, "SAMWorker", BenchmarkSamWorker))
        stack.enter_context(patch.object(main_module, "QThread", BenchmarkThread))
        stack.enter_context(patch.object(main_module.MainWindow, "_default_outputs_root", lambda _window: str(output_root)))
        stack.enter_context(patch.object(PdfProcessingWidget, "load_api_settings", lambda self: None))
        stack.enter_context(patch.object(PdfProcessingWidget, "refresh_profile_list", lambda self: None))
        stack.enter_context(patch.object(PdfProcessingWidget, "sync_runtime_controls_from_config", lambda self: None))
        stack.enter_context(patch.object(main_module.QTimer, "singleShot", lambda *args, **kwargs: None))

        construct_started = time.perf_counter()
        window = main_module.MainWindow()
        app.processEvents()
        construct_ms = (time.perf_counter() - construct_started) * 1000.0
        start_center_ready_ms = (time.perf_counter() - child_started) * 1000.0
        rss_start_center_mb = _rss_mb()

        enter_image_ms = _measure(window.enter_image_workflow, app)
        rss_image_mb = _rss_mb()
        enter_tif_ms = _measure(window.enter_tif_workflow, app)
        rss_tif_mb = _rss_mb()
        window.enter_image_workflow()
        app.processEvents()

        image_dir = workspace / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        image_paths = []
        for index, value in enumerate((48, 192), 1):
            image_path = image_dir / f"benchmark_{index}.png"
            Image.new("RGB", (8, 8), (value, value, value)).save(image_path)
            image_paths.append(str(image_path))

        project_dir = workspace / "project"
        manager = main_module.ProjectManager()
        project_path = manager.create_project("round4_benchmark", str(project_dir))
        manager.add_images(image_paths, save=True)
        open_project_ms = _measure(lambda: window.open_project_path(project_path), app)

        window.refresh_file_list()
        app.processEvents()
        image_switch_samples = []
        if window.file_list.count() >= 2:
            for index in range(10):
                image_switch_samples.append(_measure(lambda row=index % 2: window.file_list.setCurrentRow(row), app))

        part_switch_samples = []
        parts = _part_items(window.part_list, Qt.UserRole)
        if len(parts) >= 2:
            for index in range(10):
                part_switch_samples.append(_measure(lambda item=parts[index % 2]: window.part_list.setCurrentItem(item), app))

        with patch.object(main_module.ModelSettingsDialog, "exec", lambda self: 0):
            model_settings_ms = _measure(window.open_stl_model_settings, app)

        window.agent_panel.is_running = lambda: True
        agent_context_ms = _measure(
            lambda: window.open_agent_from_context(
                {
                    "source_workbench": "round4_benchmark",
                    "project_path": str(project_path),
                    "active_image": image_paths[0],
                }
            ),
            app,
        )

        operation_samples = [
            enter_image_ms,
            enter_tif_ms,
            open_project_ms,
            model_settings_ms,
            agent_context_ms,
            *image_switch_samples,
            *part_switch_samples,
        ]
        result = {
            "import_ms": import_ms,
            "construct_main_window_ms": construct_ms,
            "start_center_ready_ms": start_center_ready_ms,
            "enter_image_workflow_ms": enter_image_ms,
            "enter_tif_workflow_ms": enter_tif_ms,
            "open_small_2d_project_ms": open_project_ms,
            "image_switch_median_ms": statistics.median(image_switch_samples) if image_switch_samples else 0.0,
            "part_switch_median_ms": statistics.median(part_switch_samples) if part_switch_samples else 0.0,
            "model_settings_open_close_ms": model_settings_ms,
            "agent_context_accept_ms": agent_context_ms,
            "rss_start_center_mb": rss_start_center_mb,
            "rss_image_workflow_mb": rss_image_mb,
            "rss_tif_empty_workbench_mb": rss_tif_mb,
            "sync_operations_over_100ms": sum(value > 100.0 for value in operation_samples),
            "sync_operations_over_250ms": sum(value > 250.0 for value in operation_samples),
            "sync_operation_count": len(operation_samples),
        }

        try:
            window._shutdown_background_workers()
        except Exception:
            pass
        window.hide()
        window.deleteLater()
        app.processEvents()
        return result


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return float(ordered[index])


def summarize_runs(runs: list[dict[str, object]]) -> dict[str, dict[str, float]]:
    numeric_keys = sorted(
        {
            key
            for run in runs
            for key, value in run.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
    )
    summary = {}
    for key in numeric_keys:
        values = [float(run[key]) for run in runs if key in run]
        summary[key] = {
            "median": statistics.median(values) if values else 0.0,
            "p95": _percentile(values, 0.95),
            "min": min(values) if values else 0.0,
            "max": max(values) if values else 0.0,
        }
    return summary


def _run_parent(runs: int, output: Path, max_attempts: int) -> int:
    raw_runs = []
    failed_attempts = []
    with tempfile.TemporaryDirectory(prefix="taxamask_round4_benchmark_") as temp_root:
        for index in range(runs):
            result = None
            for attempt in range(1, max_attempts + 1):
                workspace = Path(temp_root) / f"run_{index + 1:02d}_attempt_{attempt:02d}"
                workspace.mkdir(parents=True, exist_ok=True)
                command = [sys.executable, str(Path(__file__).resolve()), "--child", "--workspace", str(workspace)]
                started = time.perf_counter()
                try:
                    completed = subprocess.run(
                        command,
                        cwd=ROOT,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=180,
                        check=False,
                    )
                    process_total_ms = (time.perf_counter() - started) * 1000.0
                except subprocess.TimeoutExpired as exc:
                    failed_attempts.append({"run": index + 1, "attempt": attempt, "reason": "timeout", "detail": str(exc)})
                    print(f"run {index + 1}/{runs} attempt {attempt}/{max_attempts} timed out", flush=True)
                    continue
                result_line = next((line for line in reversed(completed.stdout.splitlines()) if line.startswith(RESULT_PREFIX)), "")
                if completed.returncode != 0 or not result_line:
                    failed_attempts.append(
                        {
                            "run": index + 1,
                            "attempt": attempt,
                            "reason": "child_failed",
                            "returncode": completed.returncode,
                            "stdout_tail": completed.stdout[-1000:],
                            "stderr_tail": completed.stderr[-1000:],
                        }
                    )
                    print(
                        f"run {index + 1}/{runs} attempt {attempt}/{max_attempts} failed with {completed.returncode}",
                        flush=True,
                    )
                    continue
                result = json.loads(result_line[len(RESULT_PREFIX) :])
                result["process_total_ms"] = process_total_ms
                result["attempt"] = attempt
                raw_runs.append(result)
                print(
                    f"run {index + 1}/{runs}: start_center={result['start_center_ready_ms']:.1f}ms process={process_total_ms:.1f}ms attempt={attempt}",
                    flush=True,
                )
                break
            if result is None:
                raise RuntimeError(f"benchmark run {index + 1} failed after {max_attempts} attempts")

    payload = {
        "schema_version": 1,
        "python": sys.executable,
        "runs": runs,
        "environment": {
            "qt_platform": "offscreen",
            "qt_opengl": "software",
            "private_data": False,
        },
        "summary": summarize_runs(raw_runs),
        "raw_runs": raw_runs,
        "failed_attempts": failed_attempts,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark TaxaMask MainWindow with isolated, non-private fixtures.")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--output", type=Path, default=ROOT / ".tmp_validation" / "round4_stage0" / "performance_baseline.json")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--workspace", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.child:
        if args.workspace is None:
            raise SystemExit("--workspace is required with --child")
        result = _child_benchmark(args.workspace)
        print(RESULT_PREFIX + json.dumps(result, ensure_ascii=False), flush=True)
        os._exit(0)
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.max_attempts < 1:
        raise SystemExit("--max-attempts must be at least 1")
    return _run_parent(args.runs, args.output, args.max_attempts)


if __name__ == "__main__":
    raise SystemExit(main())
