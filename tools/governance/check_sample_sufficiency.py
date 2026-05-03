import argparse
import importlib.util
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_sample_guard_module():
    module_path = os.path.join(
        REPO_ROOT,
        "AntSleap",
        "core",
        "governance",
        "sample_guard.py",
    )
    spec = importlib.util.spec_from_file_location("sample_guard_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load sample guard module from: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAMPLE_GUARD_MODULE = _load_sample_guard_module()
apply_sample_sufficiency_guard = getattr(
    SAMPLE_GUARD_MODULE,
    "apply_sample_sufficiency_guard",
)
save_guarded_report = getattr(SAMPLE_GUARD_MODULE, "save_guarded_report")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply low-sample insufficient-evidence guard to redline report."
    )
    parser.add_argument("--report", required=True, help="Input redline report JSON path.")
    parser.add_argument("--policy", required=True, help="Policy JSON path.")
    parser.add_argument(
        "--out",
        required=False,
        default="",
        help="Output path for guarded report (default: overwrite input report).",
    )
    args = parser.parse_args()

    try:
        guarded = apply_sample_sufficiency_guard(args.report, args.policy)
    except ValueError as exc:
        print(str(exc))
        return 1

    output_path = args.out.strip() if isinstance(args.out, str) else ""
    if not output_path:
        output_path = args.report

    save_guarded_report(guarded, output_path)

    print("status=ok")
    print(f"insufficient_evidence={str(guarded.get('insufficient_evidence', False)).lower()}")
    print(f"global_pass={str(guarded.get('global_pass', False)).lower()}")
    print(f"insufficient_view_count={len(guarded.get('insufficient_evidence_views', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
