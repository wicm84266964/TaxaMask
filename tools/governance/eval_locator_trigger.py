import argparse
import importlib.util
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_trigger_module():
    module_path = os.path.join(
        REPO_ROOT,
        "AntSleap",
        "core",
        "governance",
        "locator_trigger.py",
    )
    spec = importlib.util.spec_from_file_location("locator_trigger_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load locator trigger module from: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TRIGGER_MODULE = _load_trigger_module()
evaluate_locator_upgrade_trigger = getattr(TRIGGER_MODULE, "evaluate_locator_upgrade_trigger")
save_locator_trigger = getattr(TRIGGER_MODULE, "save_locator_trigger")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate locator-upgrade trigger from redline history.")
    parser.add_argument("--history", required=True, help="Redline history JSON path.")
    parser.add_argument("--out", required=True, help="Output trigger report path.")
    args = parser.parse_args()

    try:
        report = evaluate_locator_upgrade_trigger(args.history)
    except ValueError as exc:
        print(str(exc))
        return 1

    save_locator_trigger(report, args.out)

    print("status=ok")
    print(f"triggered={str(report.get('triggered', False)).lower()}")
    print(f"reason_count={len(report.get('reason_codes', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
