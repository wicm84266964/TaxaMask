import argparse
import importlib.util
import json
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_resolver_callable():
    module_path = os.path.join(
        REPO_ROOT, "AntSleap", "core", "governance", "view_resolver.py"
    )
    spec = importlib.util.spec_from_file_location("view_resolver_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load resolver module from: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "resolve_view")


resolve_view = _load_resolver_callable()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run canonical view resolver fixture tests.")
    parser.add_argument("--fixture", required=True, help="Fixture JSON path.")
    args = parser.parse_args()

    with open(args.fixture, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        print("status=error")
        print("message=fixture_cases_must_be_list")
        return 1

    failures: list[str] = []

    for case in cases:
        case_id = str(case.get("id", "unknown_case"))
        text = str(case.get("filename_or_text", ""))
        context = str(case.get("context_text", ""))
        expect_view = str(case.get("expect_view", ""))
        reason_contains = str(case.get("reason_contains", ""))

        resolved = resolve_view(text, context)
        actual_view = str(resolved.get("view", ""))
        actual_reason = str(resolved.get("resolution_reason", ""))

        if actual_view != expect_view:
            failures.append(
                f"{case_id}:view_mismatch expected={expect_view} actual={actual_view}"
            )

        if reason_contains and reason_contains not in actual_reason:
            failures.append(
                f"{case_id}:reason_mismatch expected_contains={reason_contains} actual={actual_reason}"
            )

    if failures:
        print("status=failed")
        print(f"total_cases={len(cases)}")
        print(f"failed_cases={len(failures)}")
        for index, failure in enumerate(failures):
            print(f"failure_{index}={failure}")
        return 1

    print("status=ok")
    print(f"total_cases={len(cases)}")
    print(f"passed_cases={len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
