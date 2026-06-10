import argparse
import importlib.util
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_router_module():
    module_path = os.path.join(
        REPO_ROOT,
        "AntSleap",
        "core",
        "governance",
        "router.py",
    )
    spec = importlib.util.spec_from_file_location("router_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load router module from: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROUTER_MODULE = _load_router_module()
route_candidates = getattr(ROUTER_MODULE, "route_candidates")
save_routing_report = getattr(ROUTER_MODULE, "save_routing_report")


def main() -> int:
    parser = argparse.ArgumentParser(description="Route candidates into Core-2 / Frontier / Ambiguous.")
    parser.add_argument("--candidates", required=True, help="Candidate artifact JSON path.")
    parser.add_argument("--policy", required=True, help="Policy JSON path.")
    parser.add_argument("--out", required=True, help="Output routing decisions JSON path.")
    args = parser.parse_args()

    try:
        report = route_candidates(args.candidates, args.policy)
    except ValueError as exc:
        print(str(exc))
        return 1

    save_routing_report(report, args.out)

    summary = report.get("summary", {})
    print("status=ok")
    print(f"total_candidates={summary.get('total_candidates', 0)}")
    print(
        f"bucket_counts=Core-2:{summary.get('core2_count', 0)},"
        f"Frontier:{summary.get('frontier_count', 0)},"
        f"Ambiguous:{summary.get('ambiguous_count', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
