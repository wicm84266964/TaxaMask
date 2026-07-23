import datetime as _datetime
import re
import uuid


PROJECT_KIND_2D = "taxamask_2d"
PROJECT_KIND_TIF = "taxamask_tif"

_PROJECT_ID_PREFIXES = {
    PROJECT_KIND_2D: "project_2d",
    PROJECT_KIND_TIF: "project_tif",
}

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
MAX_TRACEABILITY_ID_LENGTH = 240


def validate_traceability_id(value, field_name="traceability_id"):
    text = str(value or "").strip()
    if (
        not text
        or len(text) > MAX_TRACEABILITY_ID_LENGTH
        or not _SAFE_ID_RE.fullmatch(text)
    ):
        raise ValueError(f"invalid_{field_name}")
    return text


def _new_stable_id(prefix):
    timestamp = _datetime.datetime.now(_datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    return f"{prefix}_{timestamp}_{uuid.uuid4().hex}"


def new_project_id(project_kind):
    try:
        prefix = _PROJECT_ID_PREFIXES[str(project_kind)]
    except KeyError as exc:
        raise ValueError(f"unsupported_project_traceability_kind:{project_kind}") from exc
    return _new_stable_id(prefix)


def new_project_data_version_id():
    return _new_stable_id("project_data")


def new_project_traceability(project_kind, project_id=None):
    clean_project_id = (
        validate_traceability_id(project_id, "project_id")
        if project_id is not None and str(project_id).strip()
        else new_project_id(project_kind)
    )
    return {
        "project_id": clean_project_id,
        "project_data_version_id": new_project_data_version_id(),
    }


def ensure_project_traceability(payload, project_kind):
    if not isinstance(payload, dict):
        raise TypeError("project_traceability_payload_not_dict")
    changed = False
    try:
        validate_traceability_id(payload.get("project_id"), "project_id")
    except ValueError:
        payload["project_id"] = new_project_id(project_kind)
        changed = True
    try:
        validate_traceability_id(
            payload.get("project_data_version_id"), "project_data_version_id"
        )
    except ValueError:
        payload["project_data_version_id"] = new_project_data_version_id()
        changed = True
    return changed
