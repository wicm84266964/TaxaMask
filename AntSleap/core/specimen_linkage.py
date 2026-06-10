import csv
import json
import os


SPECIMEN_LINKAGE_SCHEMA_VERSION = "taxamask_specimen_linkage_v1"


def normalize_specimen_key(value):
    text = str(value or "").strip().lower()
    return "".join(ch for ch in text if ch.isalnum())


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_not_object:{path}")
    return payload


def build_specimen_linkage(project_paths):
    entries = []
    by_key = {}
    for path in project_paths:
        project_path = os.path.abspath(str(path))
        payload = _load_json(project_path)
        project_type = str(payload.get("project_type", "image_2d"))
        for specimen in payload.get("specimens", []):
            if not isinstance(specimen, dict):
                continue
            specimen_id = str(specimen.get("specimen_id", "")).strip()
            if not specimen_id:
                continue
            key = normalize_specimen_key(specimen.get("metadata_ref") or specimen_id)
            entry = {
                "project_path": project_path,
                "project_type": project_type,
                "project_name": payload.get("name", ""),
                "specimen_id": specimen_id,
                "metadata_ref": specimen.get("metadata_ref", ""),
                "review_status": specimen.get("review_status", ""),
                "train_ready": bool(specimen.get("train_ready", False)),
                "link_key": key,
            }
            entries.append(entry)
            by_key.setdefault(key, []).append(entry)

    groups = []
    unlinked = []
    for key, group_entries in sorted(by_key.items()):
        project_types = sorted({item["project_type"] for item in group_entries})
        group = {
            "link_key": key,
            "project_types": project_types,
            "entries": group_entries,
            "cross_project": len({item["project_path"] for item in group_entries}) > 1,
        }
        if group["cross_project"]:
            groups.append(group)
        else:
            unlinked.extend(group_entries)
    return {
        "schema_version": SPECIMEN_LINKAGE_SCHEMA_VERSION,
        "project_paths": [os.path.abspath(str(path)) for path in project_paths],
        "groups": groups,
        "unlinked": unlinked,
    }


def write_specimen_linkage_report(project_paths, output_path):
    report = build_specimen_linkage(project_paths)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    return report


def write_specimen_linkage_csv(report, output_path):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "link_key",
                "cross_project",
                "project_type",
                "project_name",
                "project_path",
                "specimen_id",
                "metadata_ref",
                "review_status",
                "train_ready",
            ],
        )
        writer.writeheader()
        for group in report.get("groups", []):
            for entry in group.get("entries", []):
                row = dict(entry)
                row["cross_project"] = True
                writer.writerow(row)
        for entry in report.get("unlinked", []):
            row = dict(entry)
            row["cross_project"] = False
            writer.writerow(row)
