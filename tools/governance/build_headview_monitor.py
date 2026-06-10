import argparse
import importlib.util
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_head_monitor_module():
    module_path = os.path.join(
        REPO_ROOT,
        "AntSleap",
        "core",
        "governance",
        "headview_monitor.py",
    )
    spec = importlib.util.spec_from_file_location("headview_monitor_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load headview monitor module from: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HEAD_MONITOR_MODULE = _load_head_monitor_module()
build_head_view_monitor = getattr(HEAD_MONITOR_MODULE, "build_head_view_monitor")
save_head_view_monitor = getattr(HEAD_MONITOR_MODULE, "save_head_view_monitor")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build non-blocking head-view QA monitor artifact.")
    parser.add_argument("--metrics", required=True, help="Per-view metrics JSON path.")
    parser.add_argument("--out", required=True, help="Output head-view monitor JSON path.")
    args = parser.parse_args()

    try:
        monitor = build_head_view_monitor(args.metrics)
    except ValueError as exc:
        print(str(exc))
        return 1

    save_head_view_monitor(monitor, args.out)

    print("status=ok")
    print(f"monitor_status={monitor.get('status', '')}")
    print(f"blocking={str(monitor.get('blocking', False)).lower()}")
    print(f"sample_count={monitor.get('sample_count', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
