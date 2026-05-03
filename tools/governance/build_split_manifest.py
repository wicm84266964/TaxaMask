import argparse
import importlib.util
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_splitter_module():
    module_path = os.path.join(REPO_ROOT, "AntSleap", "core", "governance", "splitter.py")
    spec = importlib.util.spec_from_file_location("splitter_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load splitter module from: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SPLITTER = _load_splitter_module()
build_split_manifest = getattr(SPLITTER, "build_split_manifest")
save_split_manifest = getattr(SPLITTER, "save_split_manifest")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic view-stratified train/val split manifest."
    )
    parser.add_argument("--project", required=True, help="Project JSON path.")
    parser.add_argument("--seed", required=True, type=int, help="Deterministic split seed.")
    parser.add_argument("--out", required=True, help="Output split manifest path.")
    parser.add_argument(
        "--val-ratio", type=float, default=0.2, help="Validation split ratio (default: 0.2)."
    )
    args = parser.parse_args()

    manifest = build_split_manifest(
        project_path=args.project,
        seed=args.seed,
        val_ratio=args.val_ratio,
    )
    save_split_manifest(manifest, args.out)

    print("status=ok")
    print(f"total_samples={manifest.get('total_samples', 0)}")
    print(f"train_count={manifest.get('train_count', 0)}")
    print(f"val_count={manifest.get('val_count', 0)}")
    print(f"dataset_fingerprint={manifest.get('dataset_fingerprint', '')}")
    print(f"membership_fingerprint={manifest.get('membership_fingerprint', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
