import argparse
import json


REQUIRED_CHECK_KEYS = {"pass_rate", "boundary_overlap", "localization_error_px"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate redline report structure and target-view checks.")
    parser.add_argument("--report", required=True, help="Redline report JSON path.")
    args = parser.parse_args()

    with open(args.report, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    target_views = payload.get("target_views", [])
    target_view_reports = payload.get("target_view_reports", {})
    global_pass = payload.get("global_pass")

    if not isinstance(target_views, list) or not isinstance(target_view_reports, dict):
        print("redline_structure_invalid")
        return 1
    if not isinstance(global_pass, bool):
        print("redline_global_pass_missing")
        return 1

    if global_pass is False:
        insufficient_evidence = payload.get("insufficient_evidence")
        if insufficient_evidence is not True:
            print("redline_global_fail")
            return 1

    for view in target_views:
        report = target_view_reports.get(view)
        if not isinstance(report, dict):
            print(f"missing_target_view_report:{view}")
            return 1

        checks = report.get("checks", {})
        if not isinstance(checks, dict):
            print(f"missing_target_checks:{view}")
            return 1

        if set(checks.keys()) != REQUIRED_CHECK_KEYS:
            print(f"invalid_target_checks:{view}")
            return 1

        for key in REQUIRED_CHECK_KEYS:
            if not isinstance(checks.get(key), bool):
                print(f"invalid_check_type:{view}:{key}")
                return 1

    print("redline_report_ok")
    print(f"target_view_count={len(target_views)}")
    print(f"global_pass={str(global_pass).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
