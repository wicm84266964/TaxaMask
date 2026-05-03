import json
from typing import cast

SCHEMA_VERSION = "v2"

REQUIRED_FIELDS = [
    "sample_id",
    "view",
    "source_type",
    "source_ref",
    "ingestion_run_id",
    "label_timestamp",
    "qa_status",
    "routing_tier",
]

VIEW_ENUM = ["lateral", "dorsal", "head_frontal", "unknown"]

ErrorEntry = dict[str, str]
Record = dict[str, object]
Summary = dict[str, object]


def _error(code: str, field: str, message: str) -> ErrorEntry:
    return {
        "code": code,
        "field": field,
        "message": message,
    }


def validate_contract_record(record: dict[str, object]) -> tuple[bool, list[ErrorEntry]]:
    errors: list[ErrorEntry] = []

    for field in REQUIRED_FIELDS:
        if field not in record:
            errors.append(
                _error(
                    f"missing_field:{field}",
                    field,
                    f"Missing required field '{field}'.",
                )
            )

    if "view" in record:
        view_value = record["view"]
        if not isinstance(view_value, str):
            errors.append(
                _error(
                    "invalid_type:view",
                    "view",
                    "Field 'view' must be a string.",
                )
            )
        elif view_value not in VIEW_ENUM:
            allowed = ", ".join(VIEW_ENUM)
            errors.append(
                _error(
                    "invalid_enum:view",
                    "view",
                    f"Field 'view' must be one of: {allowed}.",
                )
            )

    return len(errors) == 0, errors


def _load_records(payload: object) -> tuple[list[object], list[ErrorEntry]]:
    errors: list[ErrorEntry] = []

    if not isinstance(payload, dict):
        return [], [_error("invalid_type:root", "root", "Root JSON must be an object.")]

    payload_map = cast(dict[str, object], payload)

    schema_version = payload_map.get("schema_version")
    if schema_version is None:
        errors.append(
            _error(
                "missing_field:schema_version",
                "schema_version",
                "Missing required field 'schema_version'.",
            )
        )
    elif not isinstance(schema_version, str):
        errors.append(
            _error(
                "invalid_type:schema_version",
                "schema_version",
                "Field 'schema_version' must be a string.",
            )
        )
    elif schema_version != SCHEMA_VERSION:
        errors.append(
            _error(
                "invalid_value:schema_version",
                "schema_version",
                f"Expected schema_version '{SCHEMA_VERSION}', got '{schema_version}'.",
            )
        )

    records_obj = payload_map.get("records")
    if records_obj is None:
        errors.append(
            _error(
                "missing_field:records",
                "records",
                "Missing required field 'records'.",
            )
        )
        return [], errors

    if not isinstance(records_obj, list):
        errors.append(
            _error(
                "invalid_type:records",
                "records",
                "Field 'records' must be a list.",
            )
        )
        return [], errors

    records = cast(list[object], records_obj)
    return records, errors


def validate_contract_file(path: str) -> Summary:
    errors: list[ErrorEntry] = []
    summary: Summary = {
        "schema_version": SCHEMA_VERSION,
        "input_path": path,
        "valid": False,
        "record_count": 0,
        "error_count": 0,
        "errors": errors,
    }

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = cast(object, json.load(handle))
    except FileNotFoundError:
        errors.append(_error("file_not_found", "path", f"File not found: {path}"))
        summary["error_count"] = len(errors)
        return summary
    except json.JSONDecodeError as exc:
        errors.append(
            _error(
                "invalid_json",
                "root",
                f"Invalid JSON: {exc.msg}",
            )
        )
        summary["error_count"] = len(errors)
        return summary

    records, file_errors = _load_records(payload)
    errors.extend(file_errors)
    summary["record_count"] = len(records)

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(
                _error(
                    "invalid_type:record",
                    "record",
                    f"record[{index}] must be a JSON object.",
                )
            )
            continue

        typed_record = cast(Record, record)
        is_valid, record_errors = validate_contract_record(typed_record)
        if not is_valid:
            for error in record_errors:
                errors.append(
                    _error(
                        error["code"],
                        error["field"],
                        f"record[{index}] {error['message']}",
                    )
                )

    summary["error_count"] = len(errors)
    summary["valid"] = len(errors) == 0
    return summary
