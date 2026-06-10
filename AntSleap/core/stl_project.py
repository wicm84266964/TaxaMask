import json
import os
import shutil
from datetime import datetime

from .stl_rendered_views import DEFAULT_STL_VIEW_NAMES, build_stl_rendered_view_registry, normalize_view_name


STL_PROJECT_SCHEMA_VERSION = "taxamask_stl_rendered_project_v1"
STL_PROJECT_TYPE = "stl_rendered_views"
DEFAULT_STL_PROJECT_FILENAME = "stl_project.json"


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_path_fragment(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    return clean.strip("_") or "specimen"


def _image_files_in_dir(source_dir):
    allowed = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
    paths = []
    for dirpath, _, filenames in os.walk(source_dir):
        for filename in filenames:
            if os.path.splitext(filename)[1].lower() in allowed:
                paths.append(os.path.join(dirpath, filename))
    return sorted(paths)


def _default_project_data(name, known_views=None):
    now = _now_iso()
    views = [normalize_view_name(item) for item in (known_views or DEFAULT_STL_VIEW_NAMES)]
    return {
        "schema_version": STL_PROJECT_SCHEMA_VERSION,
        "project_type": STL_PROJECT_TYPE,
        "project_id": f"stl_project_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "name": str(name or "Untitled STL Rendered View Project"),
        "created_at": now,
        "updated_at": now,
        "known_views": [item for item in views if item],
        "specimens": [],
        "imports": [],
        "metadata_links": [],
    }


class StlRenderedProjectManager:
    def __init__(self):
        self.project_data = _default_project_data("Untitled STL Rendered View Project")
        self.current_project_path = None

    @property
    def project_dir(self):
        if not self.current_project_path:
            return os.getcwd()
        return os.path.dirname(os.path.abspath(self.current_project_path))

    def create_project(self, name, project_dir, known_views=None):
        os.makedirs(project_dir, exist_ok=True)
        self.project_data = _default_project_data(name, known_views=known_views)
        self.current_project_path = os.path.join(os.path.abspath(project_dir), DEFAULT_STL_PROJECT_FILENAME)
        self.save_project()
        return self.current_project_path

    def load_project(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("stl_project_json_not_object")
        if payload.get("schema_version") != STL_PROJECT_SCHEMA_VERSION:
            raise ValueError(f"unsupported_stl_project_schema:{payload.get('schema_version')}")
        if payload.get("project_type") != STL_PROJECT_TYPE:
            raise ValueError(f"not_stl_rendered_project:{payload.get('project_type')}")
        payload.setdefault("known_views", list(DEFAULT_STL_VIEW_NAMES))
        payload.setdefault("specimens", [])
        payload.setdefault("imports", [])
        payload.setdefault("metadata_links", [])
        self.project_data = payload
        self.current_project_path = os.path.abspath(path)
        return self.project_data

    def save_project(self):
        if not self.current_project_path:
            raise ValueError("stl_project_path_not_set")
        self.project_data["updated_at"] = _now_iso()
        os.makedirs(os.path.dirname(os.path.abspath(self.current_project_path)), exist_ok=True)
        with open(self.current_project_path, "w", encoding="utf-8") as handle:
            json.dump(self.project_data, handle, ensure_ascii=False, indent=2)

    def to_relative(self, path):
        if not path:
            return ""
        text = str(path)
        if not os.path.isabs(text):
            return text.replace("\\", "/")
        try:
            return os.path.relpath(text, self.project_dir).replace("\\", "/")
        except ValueError:
            return text

    def to_absolute(self, path):
        if not path:
            return ""
        text = str(path)
        if os.path.isabs(text):
            return os.path.normpath(text)
        return os.path.normpath(os.path.join(self.project_dir, text))

    def import_rendered_view_directory(self, source_dir, copy_files=True, known_views=None):
        source_dir = os.path.abspath(str(source_dir))
        if not os.path.isdir(source_dir):
            raise NotADirectoryError(source_dir)
        views = [normalize_view_name(item) for item in (known_views or self.project_data.get("known_views") or DEFAULT_STL_VIEW_NAMES)]
        registry = build_stl_rendered_view_registry(_image_files_in_dir(source_dir), known_views=views)
        imported_specimens = []
        for specimen in registry.get("specimens", []):
            clean_id = str(specimen.get("specimen_id"))
            record = self._get_or_create_specimen(clean_id)
            for view_name, view_record in sorted((specimen.get("views") or {}).items()):
                source_path = view_record.get("path", "")
                target_rel = source_path
                if copy_files:
                    ext = os.path.splitext(source_path)[1].lower()
                    target_rel = os.path.join(
                        "specimens",
                        _safe_path_fragment(clean_id),
                        "rendered_views",
                        f"{normalize_view_name(view_name)}{ext}",
                    ).replace("\\", "/")
                    target_abs = self.to_absolute(target_rel)
                    os.makedirs(os.path.dirname(target_abs), exist_ok=True)
                    if os.path.abspath(source_path) != os.path.abspath(target_abs):
                        shutil.copy2(source_path, target_abs)
                record.setdefault("views", {})[view_name] = {
                    "view_name": view_name,
                    "path": self.to_relative(target_rel),
                    "source_path": source_path,
                    "filename": os.path.basename(source_path),
                    "role": "rendered_stl_view",
                    "label_status": "unlabeled",
                    "max_resolution_note": "Supports very high resolution rendered views; keep source images as primary assets.",
                }
            imported_specimens.append(record)

        report = {
            "imported_at": _now_iso(),
            "source_dir": source_dir,
            "copy_files": bool(copy_files),
            "known_views": views,
            "specimen_count": len(imported_specimens),
            "unparsed": registry.get("unparsed", []),
            "duplicate_views": registry.get("duplicate_views", []),
        }
        self.project_data.setdefault("imports", []).append(report)
        self.save_project()
        return {"registry": registry, "report": report, "specimens": imported_specimens}

    def _get_or_create_specimen(self, specimen_id):
        for specimen in self.project_data.get("specimens", []):
            if specimen.get("specimen_id") == specimen_id:
                return specimen
        specimen = {
            "specimen_id": specimen_id,
            "display_name": specimen_id,
            "metadata_ref": "",
            "views": {},
            "review_status": "not_started",
            "train_ready": False,
            "surface_label_taxonomy_ref": "",
        }
        self.project_data.setdefault("specimens", []).append(specimen)
        return specimen
