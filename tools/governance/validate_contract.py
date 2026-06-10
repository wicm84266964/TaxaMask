import importlib.util
import os
import sys
from collections.abc import Callable
from typing import cast


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

ErrorEntry = dict[str, str]
Summary = dict[str, object]
ValidateFileFn = Callable[[str], Summary]


def _load_contract_bindings() -> tuple[str, ValidateFileFn]:
    module_path = os.path.join(
        REPO_ROOT,
        "AntSleap",
        "core",
        "governance",
        "view_contract.py",
    )
    spec = importlib.util.spec_from_file_location("view_contract_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed_to_load_contract_module:{module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    schema_version_obj = getattr(module, "SCHEMA_VERSION", None)
    validate_fn_obj = getattr(module, "validate_contract_file", None)

    if not isinstance(schema_version_obj, str):
        raise RuntimeError("invalid_contract_binding:schema_version")
    if not callable(validate_fn_obj):
        raise RuntimeError("invalid_contract_binding:validate_contract_file")

    return schema_version_obj, cast(ValidateFileFn, validate_fn_obj)


SCHEMA_VERSION, validate_contract_file = _load_contract_bindings()


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _as_int(value: object) -> int:
    if isinstance(value, int):
        return value
    return 0


def _as_error_list(value: object) -> list[ErrorEntry]:
    if not isinstance(value, list):
        return []

    items = cast(list[object], value)
    normalized: list[ErrorEntry] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        typed_item = cast(dict[str, object], item)
        code = typed_item.get("code")
        field = typed_item.get("field")
        message = typed_item.get("message")

        if isinstance(code, str) and isinstance(field, str) and isinstance(message, str):
            normalized.append(
                {
                    "code": code,
                    "field": field,
                    "message": message,
                }
            )

    return normalized


def _parse_cli_args(argv: list[str]) -> tuple[bool, str | None, str | None, str | None]:
    self_test = False
    fixture: str | None = None
    input_path: str | None = None
    index = 0

    while index < len(argv):
        token = argv[index]

        if token == "--self-test":
            self_test = True
            index += 1
            continue

        if token == "--fixture" or token == "--input":
            if index + 1 >= len(argv):
                return False, None, None, f"missing_value:{token}"

            value = argv[index + 1]
            if token == "--fixture":
                fixture = value
            else:
                input_path = value

            index += 2
            continue

        return False, None, None, f"unknown_argument:{token}"

    return self_test, fixture, input_path, None


def _print_summary(summary: Summary) -> None:
    schema_version = summary.get("schema_version")
    input_path = summary.get("input_path")
    record_count = summary.get("record_count")
    error_count = summary.get("error_count")
    valid = summary.get("valid")

    print(f"schema_version={schema_version if isinstance(schema_version, str) else SCHEMA_VERSION}")
    print(f"input={input_path if isinstance(input_path, str) else ''}")
    print(f"record_count={_as_int(record_count)}")
    print(f"error_count={_as_int(error_count)}")
    print(f"valid={_bool_text(valid is True)}")

    errors = _as_error_list(summary.get("errors"))
    for index, error in enumerate(errors):
        print(f"error[{index}].code={error['code']}")
        print(f"error[{index}].field={error['field']}")
        print(f"error[{index}].message={error['message']}")


def main(argv: list[str]) -> int:
    self_test, fixture, input_path, parse_error = _parse_cli_args(argv)

    if parse_error is not None:
        print(f"error={parse_error}")
        return 2

    if self_test:
        print("contract_v2_ok")
        return 0

    if fixture is not None and input_path is not None:
        print("error=conflicting_arguments")
        print("message=use_only_one_of_fixture_or_input")
        return 2

    target = fixture if fixture is not None else input_path
    if target is None:
        print("error=missing_argument")
        print("message=provide_fixture_or_input_or_self_test")
        return 2

    summary = validate_contract_file(target)
    _print_summary(summary)

    valid = summary.get("valid")
    return 0 if valid is True else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as exc:
        print("valid=false")
        print("error_count=1")
        print("error[0].code=runtime_exception")
        print("error[0].field=runtime")
        print(f"error[0].message={exc}")
        raise SystemExit(2)
