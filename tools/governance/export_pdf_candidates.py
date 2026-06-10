import argparse
import importlib.util
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_bridge_module():
    module_path = os.path.join(
        REPO_ROOT,
        "AntSleap",
        "core",
        "governance",
        "candidate_bridge.py",
    )
    spec = importlib.util.spec_from_file_location("candidate_bridge_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load candidate bridge module from: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BRIDGE_MODULE = _load_bridge_module()
export_pdf_candidates = getattr(BRIDGE_MODULE, "export_pdf_candidates")
save_candidate_artifact = getattr(BRIDGE_MODULE, "save_candidate_artifact")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export PDF image-level candidates (artifact only).")
    parser.add_argument("--db", required=True, help="SQLite DB path.")
    parser.add_argument("--out", required=True, help="Output candidate artifact JSON path.")
    parser.add_argument(
        "--mode",
        required=False,
        default="candidate_only",
        help="Bridge mode (must be candidate_only).",
    )
    args = parser.parse_args()

    try:
        artifact = export_pdf_candidates(args.db, mode=args.mode)
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc))
        return 1

    save_candidate_artifact(artifact, args.out)

    print("status=ok")
    print(f"mode={artifact.get('mode', '')}")
    print(f"total_candidates={artifact.get('total_candidates', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
