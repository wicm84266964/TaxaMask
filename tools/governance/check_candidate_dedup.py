import argparse
import importlib.util
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_idempotency_module():
    module_path = os.path.join(
        REPO_ROOT,
        "AntSleap",
        "core",
        "governance",
        "idempotency.py",
    )
    spec = importlib.util.spec_from_file_location("idempotency_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load idempotency module from: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


IDEMPOTENCY_MODULE = _load_idempotency_module()
check_candidate_dedup = getattr(IDEMPOTENCY_MODULE, "check_candidate_dedup")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check candidate ID dedup status.")
    parser.add_argument("--input", required=True, help="Input candidates/routing JSON path.")
    args = parser.parse_args()

    try:
        report = check_candidate_dedup(args.input)
    except ValueError as exc:
        print(str(exc))
        return 1

    print("status=ok")
    print(f"total_records={report.get('total_records', 0)}")
    print(f"id_count={report.get('id_count', 0)}")
    print(f"duplicate_count={report.get('duplicate_count', 0)}")

    if int(report.get("duplicate_count", 0)) > 0:
        print("duplicate_candidates_detected")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
