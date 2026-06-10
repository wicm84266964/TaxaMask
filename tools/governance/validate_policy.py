import argparse
import importlib.util
import json
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_policy_loader_module():
    module_path = os.path.join(
        REPO_ROOT, "AntSleap", "core", "governance", "policy_loader.py"
    )
    spec = importlib.util.spec_from_file_location("policy_loader_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load policy loader module from: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


POLICY_LOADER = _load_policy_loader_module()
load_and_validate_policy = getattr(POLICY_LOADER, "load_and_validate_policy")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Core-2 governance policy JSON.")
    parser.add_argument("--policy", required=True, help="Path to policy JSON file.")
    parser.add_argument(
        "--print-effective",
        action="store_true",
        help="Print normalized policy JSON when validation succeeds.",
    )
    args = parser.parse_args()

    result = load_and_validate_policy(args.policy)

    print(f"valid={str(bool(result.get('valid', False))).lower()}")
    print(f"error_count={result.get('error_count', 0)}")

    for index, error in enumerate(result.get("errors", [])):
        print(f"error_{index}_code={error.get('code', '')}")
        print(f"error_{index}_field={error.get('field', '')}")
        print(f"error_{index}_message={error.get('message', '')}")

    if bool(result.get("valid", False)) and args.print_effective:
        print("effective_policy=")
        print(json.dumps(result.get("policy", {}), ensure_ascii=False, indent=2))

    return 0 if bool(result.get("valid", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
