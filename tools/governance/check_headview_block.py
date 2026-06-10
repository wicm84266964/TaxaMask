import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify head-view and unknown are blocked from Core-2 train stream.")
    parser.add_argument("--manifest", required=True, help="Train manifest JSON path.")
    args = parser.parse_args()

    with open(args.manifest, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    core2_train = payload.get("core2_train", [])
    if not isinstance(core2_train, list):
        print("invalid_core2_train")
        return 1

    blocked = []
    for item in core2_train:
        if not isinstance(item, dict):
            continue
        view = str(item.get("view", ""))
        if view in {"head_frontal", "unknown"}:
            blocked.append(str(item.get("sample_id", "")))

    print(f"core2_train_count={len(core2_train)}")
    print(f"blocked_violations={len(blocked)}")

    if blocked:
        print("headview_in_core2_train")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
