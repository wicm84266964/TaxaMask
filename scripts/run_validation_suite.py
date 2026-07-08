from __future__ import annotations

import argparse
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SUITES: dict[str, list[str]] = {
    "tif_core": [
        "tests.test_tif_architecture_test_groups",
        "tests.test_tif_label_guard",
        "tests.test_tif_write_guard",
        "tests.test_tif_truth_policy",
        "tests.test_tif_prediction_policy",
        "tests.test_tif_project",
        "tests.test_tif_backend",
        "tests.test_tif_stack_import",
        "tests.test_amira_import",
        "tests.test_tif_prediction_import",
    ],
    "tif_storage_safety": [
        "tests.test_safe_io",
        "tests.test_tif_json_to_sqlite_migration",
        "tests.test_tif_sqlite_loader",
        "tests.test_tif_sqlite_schema",
    ],
    "tif_services": [
        "tests.test_tif_selection_controller",
        "tests.test_tif_label_edit_service",
        "tests.test_tif_truth_promotion_service",
        "tests.test_tif_roi_part_service",
        "tests.test_tif_backend_workflow_service",
        "tests.test_tif_volume_preview_service",
        "tests.test_tif_local_axis_service",
        "tests.test_tif_task_context",
        "tests.test_tif_task_state",
        "tests.test_tif_task_manager",
        "tests.test_tif_workbench_states",
    ],
    "tif_preview_export": [
        "tests.test_tif_roi_preview",
        "tests.test_tif_volume_preview",
        "tests.test_tif_gpu_volume_canvas",
        "tests.test_tif_transfer_function",
        "tests.test_tif_export",
        "tests.test_tif_local_axis_reslice",
        "tests.test_tif_local_axis_ai",
        "tests.test_tif_local_axis_batch",
        "tests.test_tif_resource_policy",
        "tests.test_tif_preview_controller",
    ],
    "tif_model_backends": [
        "tests.test_tif_nnunet_v2_backend",
        "tests.test_tif_blink_core",
        "tests.test_tif_blink_nnunet_core",
    ],
    "tif_workbench": ["tests.test_tif_workbench", "tests.test_tif_backend_panel_controller"],
    "gui_smoke": ["tests.test_gui_smoke"],
    "ui_polish": ["tests.test_ui_polish_scope"],
    "tif_layout": ["tests.test_tif_workbench_layout"],
    "pdf_safety": ["tests.test_pdf_profile_deletion_safety"],
    "validation_tooling": ["tests.test_validation_suite_script"],
    "validation_chunk_sample": ["tests.test_safe_io.SafeIoTests.test_atomic_write_json_failure_keeps_existing_file_and_removes_tmp"],
    "sqlite_2d": [
        "tests.test_2d_json_to_sqlite_migration",
        "tests.test_2d_sqlite_project_load",
        "tests.test_2d_sqlite_project_save",
        "tests.test_2d_sqlite_schema",
        "tests.test_sqlite_large_scale_rehearsal",
        "tests.test_sqlite_project_maintenance",
        "tests.test_sqlite_storage",
    ],
    "agentic_misc": [
        "tests.test_agent_context_routes",
        "tests.test_agentic_auto_annotate",
        "tests.test_agentic_candidate_import",
        "tests.test_agentic_contract",
        "tests.test_agentic_multimodal_export",
        "tests.test_api_runtime_settings_schema",
        "tests.test_config_cleanup",
        "tests.test_platform_open",
        "tests.test_poppler_discovery",
        "tests.test_reporting_routes",
        "tests.test_runtime_device",
        "tests.test_sam_worker",
        "tests.test_ui_localization",
        "tests.test_window_geometry",
    ],
    "blink_locator": [
        "tests.test_blink_bridge",
        "tests.test_blink_expert_manifest",
        "tests.test_blink_heatmap_dataset",
        "tests.test_blink_route_backends",
        "tests.test_blink_training_strategy",
        "tests.test_external_blink_backend",
        "tests.test_locator_resolution_metadata",
        "tests.test_locator_scope",
        "tests.test_model_profiles",
        "tests.test_part_tree",
        "tests.test_training_preflight",
    ],
    "pdf_literature": [
        "tests.test_panel_splitter",
        "tests.test_figure_profile",
        "tests.test_literature_description_bridge",
        "tests.test_part_description_profile",
        "tests.test_pdf_classifier_llm_review",
        "tests.test_pdf_part_description_extraction",
        "tests.test_specimen_linkage_pdf_evidence",
    ],
    "generic_vlm_stl": [
        "tests.test_generic_export_schema",
        "tests.test_generic_taxonomy_workflow",
        "tests.test_macro_micro_pipeline",
        "tests.test_stl_project",
        "tests.test_stl_rendered_views",
        "tests.test_stl_review_bridge",
        "tests.test_vlm_preannotation",
    ],
}

DEFAULT_ORDER = [name for name in SUITES if name != "validation_chunk_sample"]
SUITE_CHOICES = list(SUITES)
SUITE_DEFAULT_CHUNK_SIZES = {
    "gui_smoke": 3,
    "ui_polish": 5,
}


def _test_count(modules: list[str]) -> int:
    total = 0
    for module in modules:
        path = ROOT / (module.replace(".", os.sep) + ".py")
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            total += sum(1 for line in handle if line.lstrip().startswith("def test_"))
    return total


def _iter_test_ids(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_test_ids(item)
        else:
            test_id = item.id() if hasattr(item, "id") else ""
            if test_id:
                yield test_id


def _test_ids(modules: list[str]) -> list[str]:
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    return list(_iter_test_ids(suite))


def _chunks(items: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        return [items]
    return [items[index : index + size] for index in range(0, len(items), size)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run TaxaMask validation suites in stable groups.")
    parser.add_argument("--list", action="store_true", help="List available suites and test counts.")
    parser.add_argument("--suite", action="append", choices=SUITE_CHOICES, help="Run only the named suite. Can be repeated.")
    parser.add_argument("--timeout", type=int, default=900, help="Per-suite timeout in seconds.")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Override suite chunking. Use 0 to disable chunking; omit to use stable per-suite defaults.",
    )
    args = parser.parse_args(argv)

    if args.list:
        for name in DEFAULT_ORDER:
            print(f"{name}: {_test_count(SUITES[name])} tests")
        return 0

    selected = args.suite or DEFAULT_ORDER
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QT_OPENGL", "software")
    env.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-gpu-compositing")

    python = sys.executable
    for name in selected:
        modules = SUITES[name]
        print(f"\n=== {name} ({_test_count(modules)} tests) ===", flush=True)
        chunk_size = SUITE_DEFAULT_CHUNK_SIZES.get(name, 0) if args.chunk_size is None else int(args.chunk_size)
        if chunk_size > 0:
            try:
                test_ids = _test_ids(modules)
            except Exception as exc:
                print(f"Failed to collect test ids for {name}: {exc}", file=sys.stderr)
                return 1
            groups = _chunks(test_ids, chunk_size) if test_ids else [modules]
            for index, group in enumerate(groups, 1):
                print(f"--- {name} chunk {index}/{len(groups)} ({len(group)} tests) ---", flush=True)
                command = [python, "-m", "unittest", *group]
                try:
                    subprocess.run(command, cwd=ROOT, env=env, timeout=args.timeout, check=True)
                except subprocess.TimeoutExpired:
                    print(f"Suite chunk timed out after {args.timeout}s: {name} chunk {index}", file=sys.stderr)
                    return 124
                except subprocess.CalledProcessError as exc:
                    print(f"Suite chunk failed: {name} chunk {index}", file=sys.stderr)
                    return int(exc.returncode or 1)
            continue

        command = [python, "-m", "unittest", *modules]
        try:
            subprocess.run(command, cwd=ROOT, env=env, timeout=args.timeout, check=True)
        except subprocess.TimeoutExpired:
            print(f"Suite timed out after {args.timeout}s: {name}", file=sys.stderr)
            return 124
        except subprocess.CalledProcessError as exc:
            print(f"Suite failed: {name}", file=sys.stderr)
            return int(exc.returncode or 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
