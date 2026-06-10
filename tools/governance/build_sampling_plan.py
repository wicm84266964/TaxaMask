import argparse
import importlib.util
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_scorer_module():
    module_path = os.path.join(
        REPO_ROOT,
        "AntSleap",
        "core",
        "governance",
        "risk_scorer.py",
    )
    spec = importlib.util.spec_from_file_location("risk_scorer_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load risk scorer module from: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCORER_MODULE = _load_scorer_module()
build_sampling_plan = getattr(SCORER_MODULE, "build_sampling_plan")
save_sampling_plan = getattr(SCORER_MODULE, "save_sampling_plan")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build risk-tier review sampling report.")
    parser.add_argument("--candidates", required=True, help="Candidate artifact JSON path.")
    parser.add_argument("--policy", required=True, help="Policy JSON path.")
    parser.add_argument("--out", required=True, help="Output sampling report JSON path.")
    args = parser.parse_args()

    try:
        report = build_sampling_plan(args.candidates, args.policy)
    except ValueError as exc:
        print(str(exc))
        return 1

    save_sampling_plan(report, args.out)

    tiers = report.get("summary", {}).get("tiers", {})
    print("status=ok")
    print(f"total_candidates={report.get('summary', {}).get('total_candidates', 0)}")
    print(
        "tier_counts="
        f"high:{tiers.get('high', {}).get('count', 0)},"
        f"medium:{tiers.get('medium', {}).get('count', 0)},"
        f"low:{tiers.get('low', {}).get('count', 0)}"
    )
    print(
        "sample_counts="
        f"high:{tiers.get('high', {}).get('sample_count', 0)},"
        f"medium:{tiers.get('medium', {}).get('sample_count', 0)},"
        f"low:{tiers.get('low', {}).get('sample_count', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
