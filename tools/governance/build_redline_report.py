import argparse
import importlib.util
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_redline_module():
    module_path = os.path.join(
        REPO_ROOT,
        "AntSleap",
        "core",
        "governance",
        "redline_gate.py",
    )
    spec = importlib.util.spec_from_file_location("redline_gate_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load redline gate module from: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REDLINE_MODULE = _load_redline_module()
build_redline_report = getattr(REDLINE_MODULE, "build_redline_report")
save_redline_report = getattr(REDLINE_MODULE, "save_redline_report")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build policy-gated per-view redline report.")
    parser.add_argument("--metrics", required=True, help="Per-view metrics JSON path.")
    parser.add_argument("--policy", required=True, help="Policy JSON path.")
    parser.add_argument("--out", required=True, help="Output redline report path.")
    args = parser.parse_args()

    try:
        report = build_redline_report(args.metrics, args.policy)
    except ValueError as exc:
        print(str(exc))
        return 1

    save_redline_report(report, args.out)

    print("status=ok")
    print(f"global_pass={str(report.get('global_pass', False)).lower()}")
    print(f"target_views={','.join(report.get('target_views', []))}")
    print(f"reason_count={len(report.get('reason_codes', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
