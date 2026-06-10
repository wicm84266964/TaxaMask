import argparse
import importlib.util
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_manifest_builder_module():
    module_path = os.path.join(
        REPO_ROOT, "AntSleap", "core", "governance", "manifest_builder.py"
    )
    spec = importlib.util.spec_from_file_location("manifest_builder_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load manifest builder module from: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MANIFEST_BUILDER = _load_manifest_builder_module()
build_train_manifest = getattr(MANIFEST_BUILDER, "build_train_manifest")
save_manifest = getattr(MANIFEST_BUILDER, "save_manifest")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Core-2 train manifest with route reasons.")
    parser.add_argument("--project", required=True, help="Input project JSON path.")
    parser.add_argument("--policy", required=True, help="Policy JSON path.")
    parser.add_argument("--out", required=True, help="Output train manifest path.")
    args = parser.parse_args()

    manifest = build_train_manifest(args.project, args.policy)
    save_manifest(manifest, args.out)

    summary = manifest.get("summary", {})
    print("status=ok")
    print(f"total_records={summary.get('total_records', 0)}")
    print(f"core2_train_count={summary.get('core2_train_count', 0)}")
    print(f"excluded_count={summary.get('excluded_count', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
