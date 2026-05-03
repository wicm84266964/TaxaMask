import argparse
import importlib.util
import json
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_grouping_module():
    module_path = os.path.join(REPO_ROOT, "AntSleap", "core", "governance", "grouping.py")
    spec = importlib.util.spec_from_file_location("grouping_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load grouping module from: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GROUPING = _load_grouping_module()
detect_group_leakage = getattr(GROUPING, "detect_group_leakage")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check train/val grouping leakage in split manifest.")
    parser.add_argument("--manifest", required=True, help="Split manifest JSON path.")
    args = parser.parse_args()

    with open(args.manifest, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    train = manifest.get("train", [])
    val = manifest.get("val", [])
    collisions = detect_group_leakage(train, val)

    print(f"collision_count={len(collisions)}")
    if collisions:
        print("status=failed")
        for index, item in enumerate(collisions):
            print(f"collision_{index}_group={item.get('group_key', '')}")
        return 1

    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
