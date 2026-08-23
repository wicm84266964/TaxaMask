import copy
import os

from .project import ProjectManager
from .path_identity import canonical_path
from .stl_project import StlRenderedProjectManager
from .stl_rendered_views import DEFAULT_STL_VIEW_NAMES, build_stl_rendered_view_registry, normalize_view_name


STL_REVIEW_PROVENANCE_SCHEMA_VERSION = "ant3d_stl_review_provenance_v1"
_MISSING = object()


class StlReviewRegistrationRollback:
    """Touched-record rollback for a staged, not-yet-persisted STL import."""

    _SAVE_MUTATED_PROJECT_FIELDS = (
        "project_data_version_id",
        "vlm_preannotation",
        "blink_context_roi_parents",
        "parent_box_aspect_ratios",
        "model_profiles",
        "cascade_routes",
    )

    def __init__(self, project_manager, image_paths):
        self._project_manager = project_manager
        self._active = True
        project_data = project_manager.project_data
        images = project_data.get("images", [])
        self._original_image_count = len(images) if isinstance(images, list) else 0
        self._added_images = []
        self._touched_keys = []
        existing_by_identity = {
            os.path.normcase(os.path.normpath(str(candidate))): candidate
            for candidate in images
        }
        for path in image_paths:
            canonical = canonical_path(path)
            identity = os.path.normcase(os.path.normpath(canonical))
            key = existing_by_identity.get(identity, canonical)
            if key not in self._touched_keys:
                self._touched_keys.append(key)

        uid_keys = list(self._touched_keys)
        for key in getattr(project_manager, "_sqlite_dirty_images", set()):
            if key not in uid_keys:
                uid_keys.append(key)
        self._mapping_entries = {
            "labels": self._capture_mapping_entries("labels", self._touched_keys),
            "image_provenance": self._capture_mapping_entries(
                "image_provenance", self._touched_keys
            ),
            "image_uids": self._capture_mapping_entries("image_uids", uid_keys),
        }
        self._mapping_existed = {
            name: name in project_data for name in self._mapping_entries
        }
        self._project_fields = {}
        for name in self._SAVE_MUTATED_PROJECT_FIELDS:
            value = project_data.get(name, _MISSING)
            self._project_fields[name] = (
                _MISSING if value is _MISSING else copy.deepcopy(value)
            )
        self._dirty_membership = {
            name: {
                key: key in getattr(project_manager, name, set())
                for key in self._touched_keys
            }
            for name in (
                "_sqlite_dirty_images",
                "_sqlite_deleted_images",
                "_sqlite_label_dirty_images",
            )
        }
        self._sqlite_project_dirty = project_manager._sqlite_project_dirty
        self._pending_project_data_version_id = (
            project_manager._pending_project_data_version_id
        )
        self._cache = project_manager._image_path_identity_cache
        self._cache_signature = project_manager._image_path_identity_cache_signature
        self._cache_membership = {
            os.path.normcase(os.path.normpath(key)): (
                os.path.normcase(os.path.normpath(key)) in self._cache
            )
            for key in self._touched_keys
        }

    def _capture_mapping_entries(self, mapping_name, keys):
        mapping = self._project_manager.project_data.get(mapping_name, {})
        if not isinstance(mapping, dict):
            return {"__whole_mapping__": copy.deepcopy(mapping)}
        return {
            key: copy.deepcopy(mapping[key]) if key in mapping else _MISSING
            for key in keys
        }

    def record_added_images(self):
        images = self._project_manager.project_data.get("images", [])
        if isinstance(images, list):
            self._added_images = list(images[self._original_image_count :])

    @property
    def active(self):
        return self._active

    def rollback(self):
        """Undo staged memory changes before a successful persistent commit."""
        if not self._active:
            return False
        project_manager = self._project_manager
        project_data = project_manager.project_data
        images = project_data.get("images", [])
        if isinstance(images, list) and self._added_images:
            start = self._original_image_count
            stop = start + len(self._added_images)
            if images[start:stop] == self._added_images:
                del images[start:stop]
            else:
                for added in reversed(self._added_images):
                    for index in range(len(images) - 1, -1, -1):
                        if images[index] == added:
                            del images[index]
                            break

        for mapping_name, entries in self._mapping_entries.items():
            if "__whole_mapping__" in entries:
                project_data[mapping_name] = entries["__whole_mapping__"]
                continue
            mapping = project_data.setdefault(mapping_name, {})
            for key, old_value in entries.items():
                if old_value is _MISSING:
                    mapping.pop(key, None)
                else:
                    mapping[key] = old_value
            if not self._mapping_existed[mapping_name]:
                project_data.pop(mapping_name, None)

        for name, old_value in self._project_fields.items():
            if old_value is _MISSING:
                project_data.pop(name, None)
            else:
                project_data[name] = old_value
        for name, memberships in self._dirty_membership.items():
            values = getattr(project_manager, name)
            for key, was_present in memberships.items():
                if was_present:
                    values.add(key)
                else:
                    values.discard(key)
        project_manager._sqlite_project_dirty = self._sqlite_project_dirty
        project_manager._pending_project_data_version_id = (
            self._pending_project_data_version_id
        )
        for identity, was_present in self._cache_membership.items():
            if was_present:
                self._cache.add(identity)
            else:
                self._cache.discard(identity)
        project_manager._image_path_identity_cache = self._cache
        project_manager._image_path_identity_cache_signature = self._cache_signature
        self.finalize()
        return True

    def finalize(self):
        """Release rollback state after the caller's final save succeeds."""
        if not self._active:
            return False
        self._active = False
        self._project_manager = None
        self._mapping_entries = {}
        self._project_fields = {}
        self._dirty_membership = {}
        self._cache = set()
        return True


def _image_files_in_dir(source_dir):
    allowed = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
    paths = []
    for dirpath, _, filenames in os.walk(source_dir):
        for filename in filenames:
            if os.path.splitext(filename)[1].lower() in allowed:
                paths.append(os.path.join(dirpath, filename))
    return sorted(paths)


def _register_rendered_view_records_for_2d_review(records, project_manager, *, save=True):
    if not isinstance(project_manager, ProjectManager):
        raise TypeError("project_manager_required")
    existing_records = [record for record in records if os.path.exists(record["path"])]
    missing = [record for record in records if not os.path.exists(record["path"])]
    image_paths = [record["path"] for record in existing_records]
    result = {
        "registered_count": len(existing_records),
        "missing_count": len(missing),
        "registered": existing_records,
        "missing": missing,
    }
    rollback_token = StlReviewRegistrationRollback(project_manager, image_paths)
    if not image_paths:
        if save:
            rollback_token.finalize()
        else:
            result["rollback_token"] = rollback_token
        return result

    try:
        project_manager.add_images(image_paths, save=False)
        rollback_token.record_added_images()
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
            image_key = project_manager._image_data_key(record["path"])
            label_entry = project_manager.project_data.setdefault("labels", {}).setdefault(
                image_key, project_manager._default_label_entry()
            )
            label_entry["view"] = record.get("view_name", "")
            label_entry["specimen_id"] = record.get("specimen_id", "")
            label_entry["metadata_ref"] = record.get("metadata_ref", "")
            label_entry["review_mode"] = "stl_rendered_view"
            project_manager._mark_sqlite_label_dirty(image_key)
        if save:
            project_manager.save_project()
    except Exception:
        rollback_token.record_added_images()
        rollback_token.rollback()
        raise
    if save:
        rollback_token.finalize()
    else:
        result["rollback_token"] = rollback_token
    return result


def import_stl_rendered_views_into_2d_project(
    project_manager, source_dir, known_views=None, *, save=True
):
    """Register views, optionally returning a rollback token without saving."""
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
    result = _register_rendered_view_records_for_2d_review(
        records, project_manager, save=save
    )
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


def register_stl_rendered_views_for_2d_review(
    stl_project_manager, project_manager, view_names=None, *, save=True
):
    """Register project views, optionally staging them for a caller-owned save."""
    records = collect_stl_rendered_review_images(stl_project_manager, view_names=view_names)
    return _register_rendered_view_records_for_2d_review(
        records, project_manager, save=save
    )
