import os

from .project import ProjectManager
from .stl_project import StlRenderedProjectManager
from .stl_rendered_views import DEFAULT_STL_VIEW_NAMES, build_stl_rendered_view_registry, normalize_view_name


STL_REVIEW_PROVENANCE_SCHEMA_VERSION = "ant3d_stl_review_provenance_v1"


def _image_files_in_dir(source_dir):
    allowed = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
    paths = []
    for dirpath, _, filenames in os.walk(source_dir):
        for filename in filenames:
            if os.path.splitext(filename)[1].lower() in allowed:
                paths.append(os.path.join(dirpath, filename))
    return sorted(paths)


def _register_rendered_view_records_for_2d_review(records, project_manager):
    if not isinstance(project_manager, ProjectManager):
        raise TypeError("project_manager_required")
    existing_records = [record for record in records if os.path.exists(record["path"])]
    missing = [record for record in records if not os.path.exists(record["path"])]
    image_paths = [record["path"] for record in existing_records]
    if image_paths:
        project_manager.add_images(image_paths)
    for record in existing_records:
        provenance = {
            "schema_version": STL_REVIEW_PROVENANCE_SCHEMA_VERSION,
            "source_type": "stl_rendered_view",
            "stl_project_path": record.get("stl_project_path", ""),
            "specimen_id": record.get("specimen_id", ""),
            "metadata_ref": record.get("metadata_ref", ""),
            "view_name": record.get("view_name", ""),
            "source_path": record.get("source_path", ""),
            "workflow_note": "Surface morphology review uses the 2D Labeling Workbench and Blink; labels remain separate from TIF material IDs.",
        }
        project_manager.set_image_provenance(record["path"], provenance, save=False)
        label_entry = project_manager.project_data.setdefault("labels", {}).setdefault(record["path"], project_manager._default_label_entry())
        label_entry["view"] = record.get("view_name", "")
        label_entry["specimen_id"] = record.get("specimen_id", "")
        label_entry["metadata_ref"] = record.get("metadata_ref", "")
        label_entry["review_mode"] = "stl_rendered_view"
    if image_paths:
        project_manager.save_project()
    return {
        "registered_count": len(existing_records),
        "missing_count": len(missing),
        "registered": existing_records,
        "missing": missing,
    }


def import_stl_rendered_views_into_2d_project(project_manager, source_dir, known_views=None):
    source_dir = os.path.abspath(str(source_dir))
    if not os.path.isdir(source_dir):
        raise NotADirectoryError(source_dir)
    views = [normalize_view_name(item) for item in (known_views or DEFAULT_STL_VIEW_NAMES)]
    registry = build_stl_rendered_view_registry(_image_files_in_dir(source_dir), known_views=views)
    records = []
    for specimen in registry.get("specimens", []):
        specimen_id = specimen.get("specimen_id", "")
        metadata_ref = specimen.get("metadata_ref", "")
        for view_name, view in sorted((specimen.get("views") or {}).items()):
            records.append(
                {
                    "path": os.path.abspath(view.get("path", "")),
                    "specimen_id": specimen_id,
                    "metadata_ref": metadata_ref,
                    "view_name": str(view_name),
                    "source_path": os.path.abspath(view.get("path", "")),
                    "stl_project_path": "",
                }
            )
    result = _register_rendered_view_records_for_2d_review(records, project_manager)
    result["registry"] = registry
    result["source_dir"] = source_dir
    result["specimen_count"] = len(registry.get("specimens", []))
    result["unparsed_count"] = len(registry.get("unparsed", []))
    result["duplicate_view_count"] = len(registry.get("duplicate_views", []))
    return result


def collect_stl_rendered_review_images(stl_project_manager, view_names=None):
    if not isinstance(stl_project_manager, StlRenderedProjectManager):
        raise TypeError("stl_project_manager_required")
    view_filter = {str(item).strip().lower() for item in (view_names or []) if str(item).strip()}
    records = []
    for specimen in stl_project_manager.project_data.get("specimens", []):
        specimen_id = specimen.get("specimen_id", "")
        metadata_ref = specimen.get("metadata_ref", "")
        for view_name, view in sorted((specimen.get("views") or {}).items()):
            if view_filter and str(view_name).lower() not in view_filter:
                continue
            path = stl_project_manager.to_absolute(view.get("path", ""))
            records.append(
                {
                    "path": path,
                    "specimen_id": specimen_id,
                    "metadata_ref": metadata_ref,
                    "view_name": str(view_name),
                    "source_path": view.get("source_path", ""),
                    "stl_project_path": stl_project_manager.current_project_path or "",
                }
            )
    return records


def register_stl_rendered_views_for_2d_review(stl_project_manager, project_manager, view_names=None):
    records = collect_stl_rendered_review_images(stl_project_manager, view_names=view_names)
    return _register_rendered_view_records_for_2d_review(records, project_manager)
