import argparse
import importlib.util
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_evaluator_module():
    module_path = os.path.join(REPO_ROOT, "AntSleap", "core", "governance", "evaluator.py")
    spec = importlib.util.spec_from_file_location("evaluator_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load evaluator module from: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR_MODULE = _load_evaluator_module()
calculate_per_view_metrics = getattr(EVALUATOR_MODULE, "calculate_per_view_metrics")
save_per_view_metrics = getattr(EVALUATOR_MODULE, "save_per_view_metrics")


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate per-view governance metrics.")
    parser.add_argument("--pred", required=True, help="Predictions JSON path.")
    parser.add_argument("--gt", required=True, help="Ground-truth JSON path.")
    parser.add_argument("--out", required=True, help="Output per-view metrics JSON path.")
    args = parser.parse_args()

    try:
        report = calculate_per_view_metrics(args.pred, args.gt)
    except ValueError as exc:
        print(str(exc))
        return 1

    save_per_view_metrics(report, args.out)

    print("status=ok")
    print(f"total_samples={report.get('total_samples', 0)}")
    print("views=" + ",".join(report.get("views_present", [])))
    for view, metrics in report.get("metrics_by_view", {}).items():
        print(
            f"view={view} pass_rate={metrics.get('pass_rate', 0.0)} "
            f"boundary_overlap={metrics.get('boundary_overlap', 0.0)} "
            f"localization_error_px={metrics.get('localization_error_px', 0.0)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
