# pyright: reportMissingImports=false, reportGeneralTypeIssues=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false, reportIndexIssue=false

import json
import os
import shutil
import time
from PIL import Image, ImageDraw

from .taxonomy_defaults import (
    DEFAULT_LOCATOR_SCOPE,
    DEFAULT_PROJECT_TAXONOMY,
    is_safe_part_name,
    legacy_locator_scope_for_loaded_taxonomy,
    sanitize_locator_scope,
    sanitize_taxonomy,
)
from .project_templates import DEFAULT_PROJECT_TEMPLATE_ID, PROJECT_TEMPLATE_ANT, get_project_template
from .cascade_routes import (
    PROJECT_ROUTE_MANIFEST_VERSION,
    get_route_appointed_expert,
    get_route_persisted_expert_candidates,
    merge_expert_candidates,
    sanitize_route_backend_fields,
    sanitize_expert_reference,
    sanitize_project_route_manifest,
)
from .model_profiles import (
    DEFAULT_VLM_IMAGE_GROUP,
    DEFAULT_MODEL_PROFILE_ID,
    VLM_IMAGE_GROUPS,
    VLM_PROCESSING_SCOPES,
    clone_model_profiles,
    sanitize_model_profiles,
    set_active_model_profile as set_active_model_profile_id,
)
from .vlm_preannotation import DEFAULT_VLM_PROMPT_PROFILE_ID, sanitize_vlm_prompt_profile
from .sqlite_storage import LEGACY_JSON_BACKEND, PROJECT_MANIFEST_SCHEMA_VERSION, SQLITE_BACKEND, write_project_manifest
from .path_identity import canonical_path, path_identity

DEFAULT_CATEGORY_SUPERCATEGORY = "biological_structure"
MULTIMODAL_SAMPLE_SCHEMA_VERSION = "taxamask-multimodal-sample-v1"
MODEL_PROFILE_EXPORT_SUMMARY_SCHEMA_VERSION = "taxamask-model-profile-export-summary-v1"
DEFAULT_PARENT_BOX_ASPECT_RATIOS = {
    "Head": 1.0,
    "Mesosoma": 4.0 / 3.0,
    "Gaster": 4.0 / 3.0,
    "Whole body": 16.0 / 9.0,
}

AUTO_BOX_SOURCE_VLM = "vlm_first_mile"
AUTO_BOX_SOURCE_MODEL = "model_prediction"
AUTO_BOX_SOURCE_EXTERNAL_MODEL = "external_model_prediction"
AUTO_BOX_REVIEW_DRAFT = "draft"
AUTO_BOX_REVIEW_CONFIRMED = "confirmed"
PROJECT_BACKUP_LIMIT = 30
PROJECT_BACKUP_MIN_INTERVAL_SECONDS = 300
LABEL_JOURNAL_SCHEMA_VERSION = "taxamask-label-journal-v1"


class ProjectManager:
    def __init__(self):
        self.project_data = {
            "name": "Untitled",
            "images": [], 
            "labels": {}, # Map: image_path -> { "parts": { "Head": [[x,y], [x,y]...] }, ... } 
            "taxonomy": list(DEFAULT_PROJECT_TAXONOMY),
            "locator_scope": list(DEFAULT_LOCATOR_SCOPE),
            "project_template": PROJECT_TEMPLATE_ANT,
            "category_supercategory": DEFAULT_CATEGORY_SUPERCATEGORY,
            "taxon_label": "Genus",
            "scales": {}, # Map: image_path -> float (pixels_per_mm)
            "image_provenance": {},
            "image_groups": {
                "custom_groups": [],
            },
            "vlm_preannotation": {
                "target_parts": [],
                "processing_scope": "image_group",
                "image_group": DEFAULT_VLM_IMAGE_GROUP,
                "concurrency": 1,
                "prompt_profile_id": DEFAULT_VLM_PROMPT_PROFILE_ID,
                "prompt_profile": sanitize_vlm_prompt_profile({}),
            },
            "blink_context_roi_parents": {},
            "parent_box_aspect_ratios": dict(DEFAULT_PARENT_BOX_ASPECT_RATIOS),
            "model_profiles": {},
            "cascade_routes": {
                "version": PROJECT_ROUTE_MANIFEST_VERSION,
                "routes": [],
            },
        }
        self.current_project_path = None
        self.current_storage_backend = LEGACY_JSON_BACKEND
        self.current_database_path = ""
        self._sqlite_dirty_images = set()
        self._sqlite_deleted_images = set()
        self._sqlite_project_dirty = False
        self._legacy_json_write_enabled = False
        self.known_relocated_roots = []
        self._last_label_journal_fsync = 0.0

    def set_known_relocated_roots(self, root_mappings):
        clean_mappings = []
        for item in root_mappings or []:
            if not isinstance(item, dict):
                continue
            marker = str(item.get("marker", "") or "").strip()
            relocated_root = str(item.get("relocated_root", "") or "").strip()
            if not marker or not relocated_root:
                continue
            clean_mappings.append(
                {
                    "marker": os.path.normpath(marker),
                    "relocated_root": os.path.normpath(relocated_root),
                }
            )
        self.known_relocated_roots = clean_mappings

    def _sanitize_cascade_routes(self, route_manifest):
        clean_manifest = sanitize_project_route_manifest(
            route_manifest,
            taxonomy=self.project_data.get("taxonomy", []),
        )
        self.project_data["cascade_routes"] = clean_manifest
        return clean_manifest

    def _model_profile_context(self):
        return {
            "taxonomy": list(self.project_data.get("taxonomy", [])),
            "locator_scope": list(self.project_data.get("locator_scope", [])),
            "parent_box_aspect_ratios": dict(self.project_data.get("parent_box_aspect_ratios", {})),
            "vlm_preannotation": dict(self.project_data.get("vlm_preannotation", {})),
        }

    def _sanitize_model_profiles(self, profiles):
        clean_profiles = sanitize_model_profiles(profiles, **self._model_profile_context())
        self.project_data["model_profiles"] = clean_profiles
        return clean_profiles

    def _sync_active_model_profile_from_project_fields(self):
        profiles = self._sanitize_model_profiles(self.project_data.get("model_profiles", {}))
        active_id = profiles.get("active_profile_id", DEFAULT_MODEL_PROFILE_ID)
        for profile in profiles.get("profiles", []):
            if profile.get("profile_id") != active_id:
                continue
            parent_backend = profile.setdefault("parent_backend", {})
            parent_backend["locator_scope"] = list(self.project_data.get("locator_scope", []))
            parent_backend["parent_box_aspect_ratios"] = dict(self.project_data.get("parent_box_aspect_ratios", {}))
            inference_params = profile.setdefault("inference_params", {})
            inference_params["vlm_preannotation"] = dict(self.project_data.get("vlm_preannotation", {}))
            break
        self.project_data["model_profiles"] = self._sanitize_model_profiles(profiles)
        return self.project_data["model_profiles"]

    def _sanitize_blink_context_roi_parents(self, parent_map):
        taxonomy = set(self.project_data.get("taxonomy", []))
        clean_map = {}
        if not isinstance(parent_map, dict):
            return clean_map

        for target_part, parent_part in parent_map.items():
            clean_target = str(target_part).strip()
            clean_parent = str(parent_part).strip()
            if not clean_target or not clean_parent:
                continue
            if clean_target == clean_parent:
                continue
            if clean_target not in taxonomy or clean_parent not in taxonomy:
                continue
            clean_map[clean_target] = clean_parent

        return clean_map

    def _sanitize_parent_box_aspect_ratios(self, ratio_map):
        taxonomy = set(self.project_data.get("taxonomy", []))
        clean_map = {}
        if isinstance(ratio_map, dict):
            for part_name, ratio in ratio_map.items():
                clean_part = str(part_name or "").strip()
                if not clean_part:
                    continue
                if taxonomy and clean_part not in taxonomy and clean_part not in DEFAULT_PARENT_BOX_ASPECT_RATIOS:
                    continue
                try:
                    clean_ratio = float(ratio)
                except Exception:
                    continue
                if clean_ratio > 0:
                    clean_map[clean_part] = clean_ratio

        for part_name, ratio in DEFAULT_PARENT_BOX_ASPECT_RATIOS.items():
            if not taxonomy or part_name in taxonomy:
                clean_map.setdefault(part_name, float(ratio))
        return clean_map

    def _safe_image_group_id(self, value, fallback):
        text = str(value or "").strip()
        clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)
        clean = clean.strip("_")
        return clean or fallback

    def _sanitize_image_groups(self, image_groups):
        if not isinstance(image_groups, dict):
            image_groups = {}
        builtin_ids = {"original", "split", "hard_candidates", "manual_done", "manual"}
        seen = set()
        custom_groups = []
        raw_groups = image_groups.get("custom_groups", [])
        if isinstance(raw_groups, dict):
            raw_groups = [
                {"id": group_id, "name": group_name}
                for group_id, group_name in raw_groups.items()
            ]
        if not isinstance(raw_groups, list):
            raw_groups = []

        for index, group in enumerate(raw_groups, start=1):
            if not isinstance(group, dict):
                continue
            name = str(group.get("name", "") or "").strip()
            if not name:
                continue
            group_id = self._safe_image_group_id(group.get("id", ""), f"custom_{index}")
            if group_id in builtin_ids:
                group_id = f"custom_{group_id}"
            base_id = group_id
            suffix = 2
            while group_id in seen or group_id in builtin_ids:
                group_id = f"{base_id}_{suffix}"
                suffix += 1
            seen.add(group_id)
            custom_groups.append({"id": group_id, "name": name[:80]})
        return {"custom_groups": custom_groups}

    def _sanitize_vlm_preannotation_settings(self, settings):
        taxonomy = list(self.project_data.get("taxonomy", []))
        taxonomy_set = set(taxonomy)
        if not isinstance(settings, dict):
            settings = {}
        target_parts = []
        for part_name in settings.get("target_parts", []):
            clean_part = str(part_name or "").strip()
            if clean_part and clean_part in taxonomy_set and clean_part not in target_parts:
                target_parts.append(clean_part)
        processing_scope = str(settings.get("processing_scope", "image_group") or "image_group").strip()
        if processing_scope not in VLM_PROCESSING_SCOPES:
            processing_scope = "image_group"
        image_group = str(settings.get("image_group", DEFAULT_VLM_IMAGE_GROUP) or DEFAULT_VLM_IMAGE_GROUP).strip()
        custom_group_ids = {
            str(group.get("id", "")).strip()
            for group in self._sanitize_image_groups(self.project_data.get("image_groups", {})).get("custom_groups", [])
            if str(group.get("id", "")).strip()
        }
        if image_group not in VLM_IMAGE_GROUPS and image_group not in custom_group_ids:
            image_group = DEFAULT_VLM_IMAGE_GROUP
        try:
            concurrency = int(settings.get("concurrency", 1))
        except Exception:
            concurrency = 1
        concurrency = max(1, min(8, concurrency))
        return {
            "target_parts": target_parts,
            "processing_scope": processing_scope,
            "image_group": image_group,
            "concurrency": concurrency,
            "prompt_profile_id": str(
                settings.get("prompt_profile_id")
                or (settings.get("prompt_profile") if isinstance(settings.get("prompt_profile"), dict) else {}).get("profile_id")
                or DEFAULT_VLM_PROMPT_PROFILE_ID
            ).strip() or DEFAULT_VLM_PROMPT_PROFILE_ID,
            "prompt_profile": sanitize_vlm_prompt_profile(settings.get("prompt_profile", {})),
        }

    def get_vlm_preannotation_settings(self):
        settings = self._sanitize_vlm_preannotation_settings(self.project_data.get("vlm_preannotation", {}))
        self.project_data["vlm_preannotation"] = settings
        return settings

    def set_vlm_preannotation_settings(self, settings, save=True):
        clean_settings = self._sanitize_vlm_preannotation_settings(settings)
        self.project_data["vlm_preannotation"] = clean_settings
        self._sync_active_model_profile_from_project_fields()
        self._mark_sqlite_project_dirty()
        if save:
            self.save_project()
        return clean_settings

    def get_vlm_preannotation_target_parts(self):
        return list(self.get_vlm_preannotation_settings().get("target_parts", []))

    def _category_supercategory(self):
        value = self.project_data.get("category_supercategory", DEFAULT_CATEGORY_SUPERCATEGORY)
        if not isinstance(value, str) or not value.strip():
            return DEFAULT_CATEGORY_SUPERCATEGORY
        return value.strip()

    def _label_taxon_payload(self, label_data):
        if not isinstance(label_data, dict):
            return {
                "taxon": "Unknown",
                "taxon_rank": "",
                "taxon_metadata": {},
                "genus": "Unknown",
            }

        genus = str(label_data.get("genus", "Unknown") or "Unknown")
        taxon = str(label_data.get("taxon", genus) or genus or "Unknown")
        taxon_rank = str(label_data.get("taxon_rank", "") or "")
        taxon_metadata = label_data.get("taxon_metadata", {})
        if not isinstance(taxon_metadata, dict):
            taxon_metadata = {}
        return {
            "taxon": taxon,
            "taxon_rank": taxon_rank,
            "taxon_metadata": taxon_metadata,
            "genus": genus,
        }

    def _default_label_entry(self):
        return {
            "parts": {},
            "status": "unlabeled",
            "genus": "Unknown",
            "taxon": "Unknown",
            "taxon_rank": "",
            "taxon_metadata": {},
            "descriptions": {},
            "description_sources": {},
        }

    def _label_entry_has_saved_content(self, label_data):
        if not isinstance(label_data, dict):
            return False

        for key in (
            "parts",
            "boxes",
            "auto_boxes",
            "auto_box_meta",
            "descriptions",
            "description_sources",
            "shrink_loose_boxes",
            "trajectories",
        ):
            value = label_data.get(key)
            if value:
                return True

        if str(label_data.get("status", "unlabeled") or "unlabeled") != "unlabeled":
            return True
        if str(label_data.get("genus", "Unknown") or "Unknown") not in ("", "Unknown"):
            return True
        if str(label_data.get("taxon", "Unknown") or "Unknown") not in ("", "Unknown"):
            return True
        if str(label_data.get("taxon_rank", "") or ""):
            return True
        taxon_metadata = label_data.get("taxon_metadata", {})
        if isinstance(taxon_metadata, dict) and taxon_metadata:
            return True

        known_default_keys = {
            "parts",
            "status",
            "genus",
            "taxon",
            "taxon_rank",
            "taxon_metadata",
            "descriptions",
            "description_sources",
            "boxes",
            "auto_boxes",
            "auto_box_meta",
            "shrink_loose_boxes",
            "trajectories",
        }
        for key, value in label_data.items():
            if key not in known_default_keys and value not in ({}, [], "", None):
                return True
        return False

    def _project_sidecar_stem(self, project_path=None):
        path = os.path.abspath(project_path or self.current_project_path or "")
        name = os.path.basename(path)
        stem, _ext = os.path.splitext(name)
        return stem or "project"

    def _project_backup_dir(self, project_path=None):
        path = os.path.abspath(project_path or self.current_project_path or "")
        if not path:
            return ""
        return os.path.join(os.path.dirname(path), f"{self._project_sidecar_stem(path)}.project_backups")

    def _label_journal_path(self, project_path=None):
        path = os.path.abspath(project_path or self.current_project_path or "")
        if not path:
            return ""
        return os.path.join(os.path.dirname(path), f"{self._project_sidecar_stem(path)}.label_journal.jsonl")

    def _json_timestamp(self):
        return time.strftime("%Y-%m-%dT%H:%M:%S%z")

    def _backup_current_project_file(self, project_path):
        if not project_path or not os.path.exists(project_path):
            return ""
        try:
            if os.path.getsize(project_path) <= 0:
                return ""
        except OSError:
            return ""

        backup_dir = self._project_backup_dir(project_path)
        stem = self._project_sidecar_stem(project_path)
        try:
            os.makedirs(backup_dir, exist_ok=True)
            existing = [
                os.path.join(backup_dir, name)
                for name in os.listdir(backup_dir)
                if name.startswith(f"{stem}.") and name.endswith(".json.bak")
            ]
            if existing:
                latest_mtime = max(os.path.getmtime(path) for path in existing if os.path.exists(path))
                if time.time() - latest_mtime < PROJECT_BACKUP_MIN_INTERVAL_SECONDS:
                    return ""

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"{stem}.{timestamp}.json.bak")
            tmp_backup_path = f"{backup_path}.tmp"
            shutil.copy2(project_path, tmp_backup_path)
            os.replace(tmp_backup_path, backup_path)

            backups = sorted(
                [
                    os.path.join(backup_dir, name)
                    for name in os.listdir(backup_dir)
                    if name.startswith(f"{stem}.") and name.endswith(".json.bak")
                ],
                key=lambda item: os.path.getmtime(item),
                reverse=True,
            )
            for old_backup in backups[PROJECT_BACKUP_LIMIT:]:
                try:
                    os.remove(old_backup)
                except OSError:
                    pass
            return backup_path
        except Exception as exc:
            print(f"Project backup skipped: {exc}")
            return ""

    def _append_label_journal_entry(self, image_path, action):
        if self.is_sqlite_project() or not getattr(self, "_legacy_json_write_enabled", False):
            return False
        journal_path = self._label_journal_path()
        if not journal_path or not image_path:
            return False
        labels = self.project_data.get("labels", {})
        label_entry = labels.get(image_path, self._default_label_entry())
        try:
            os.makedirs(os.path.dirname(journal_path), exist_ok=True)
            record = {
                "schema_version": LABEL_JOURNAL_SCHEMA_VERSION,
                "timestamp": self._json_timestamp(),
                "action": str(action or "label_update"),
                "project": os.path.abspath(self.current_project_path) if self.current_project_path else "",
                "image_path": self._to_relative(image_path),
                "label": label_entry if isinstance(label_entry, dict) else self._default_label_entry(),
            }
            with open(journal_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._last_label_journal_fsync = time.time()
            return True
        except Exception as exc:
            print(f"Label journal write skipped: {exc}")
            return False

    def recover_labels_from_journal(self, journal_path=None, save=True):
        path = journal_path or self._label_journal_path()
        if not path or not os.path.exists(path):
            return {
                "recovered_images": 0,
                "records_read": 0,
                "records_skipped": 0,
            }

        latest_by_image = {}
        records_read = 0
        records_skipped = 0
        try:
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        records_skipped += 1
                        continue
                    if record.get("schema_version") != LABEL_JOURNAL_SCHEMA_VERSION:
                        records_skipped += 1
                        continue
                    image_path = str(record.get("image_path") or "")
                    label_entry = record.get("label")
                    if not image_path or not isinstance(label_entry, dict):
                        records_skipped += 1
                        continue
                    abs_path = self._to_absolute(image_path)
                    latest_by_image[abs_path] = label_entry
                    records_read += 1
        except OSError:
            return {
                "recovered_images": 0,
                "records_read": records_read,
                "records_skipped": records_skipped,
            }

        labels = self.project_data.setdefault("labels", {})
        for image_path, label_entry in latest_by_image.items():
            labels[image_path] = self._normalize_label_taxon_fields(label_entry)
            if image_path not in self.project_data.get("images", []):
                self.project_data.setdefault("images", []).append(image_path)

        if latest_by_image and save:
            self._mark_sqlite_images_dirty(latest_by_image.keys())
            self._mark_sqlite_project_dirty()
            self.save_project()

        return {
            "recovered_images": len(latest_by_image),
            "records_read": records_read,
            "records_skipped": records_skipped,
        }

    def _normalize_label_taxon_fields(self, label_data):
        if not isinstance(label_data, dict):
            label_data = self._default_label_entry()

        label_data.setdefault("parts", {})
        label_data.setdefault("status", "unlabeled")
        label_data.setdefault("descriptions", {})
        label_data.setdefault("description_sources", {})
        if not isinstance(label_data.get("description_sources"), dict):
            label_data["description_sources"] = {}

        payload = self._label_taxon_payload(label_data)
        label_data["taxon"] = payload["taxon"]
        label_data["taxon_rank"] = payload["taxon_rank"]
        label_data["taxon_metadata"] = payload["taxon_metadata"]
        label_data["genus"] = payload["genus"]
        return label_data

    def _resolve_known_relocated_output(self, path):
        """Resolve user-configured relocated dataset roots after manual disk reorganization."""
        if not isinstance(path, str) or not path:
            return None

        normalized = os.path.normpath(path)
        normalized_lower = normalized.lower()

        for mapping in self.known_relocated_roots:
            marker = os.path.normpath(mapping.get("marker", ""))
            relocated_root = os.path.normpath(mapping.get("relocated_root", ""))
            if not marker or not relocated_root:
                continue

            marker_lower = marker.lower()
            marker_index = normalized_lower.find(marker_lower)
            if marker_index == -1:
                continue

            suffix_start = marker_index + len(marker)
            suffix = normalized[suffix_start:].lstrip("\\/")
            relocated_path = os.path.normpath(os.path.join(relocated_root, suffix))
            if os.path.exists(relocated_path):
                return relocated_path
        return None

    def get_image_path_health(self):
        images = list(self.project_data.get("images", []))
        existing = []
        missing = []
        for image_path in images:
            normalized = os.path.normpath(str(image_path))
            if os.path.exists(normalized):
                existing.append(normalized)
            else:
                missing.append(normalized)
        return {
            "total": len(images),
            "existing": existing,
            "missing": missing,
            "existing_count": len(existing),
            "missing_count": len(missing),
        }

    def preview_image_path_remap(self, new_root):
        root = os.path.normpath(str(new_root or "").strip())
        health = self.get_image_path_health()
        matches = []
        unresolved = []
        if not root or not os.path.isdir(root):
            return {
                "new_root": root,
                "missing": health["missing"],
                "matches": matches,
                "unresolved": list(health["missing"]),
            }

        by_name = {}
        duplicate_names = set()
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                key = filename.lower()
                candidate = os.path.normpath(os.path.join(dirpath, filename))
                if key in by_name:
                    duplicate_names.add(key)
                    continue
                by_name[key] = candidate

        for old_path in health["missing"]:
            filename = os.path.basename(old_path).lower()
            new_path = by_name.get(filename)
            if new_path and filename not in duplicate_names:
                matches.append({"old_path": old_path, "new_path": new_path})
            else:
                unresolved.append(old_path)

        return {
            "new_root": root,
            "missing": health["missing"],
            "matches": matches,
            "unresolved": unresolved,
        }

    def apply_image_path_remap(self, remap_matches, save=True):
        path_map = {}
        for item in remap_matches or []:
            if not isinstance(item, dict):
                continue
            old_path = os.path.normpath(str(item.get("old_path", "") or ""))
            new_path = os.path.normpath(str(item.get("new_path", "") or ""))
            if old_path and new_path and os.path.exists(new_path):
                path_map[old_path] = new_path

        if not path_map:
            return 0

        remapped_images = []
        changed = 0
        for image_path in self.project_data.get("images", []):
            normalized = os.path.normpath(str(image_path))
            replacement = path_map.get(normalized)
            if replacement:
                remapped_images.append(replacement)
                changed += 1
            else:
                remapped_images.append(image_path)
        self.project_data["images"] = remapped_images

        for key in ("labels", "scales", "image_provenance"):
            source = self.project_data.get(key, {})
            if not isinstance(source, dict):
                continue
            remapped = {}
            for image_path, value in source.items():
                normalized = os.path.normpath(str(image_path))
                remapped[path_map.get(normalized, image_path)] = value
            self.project_data[key] = remapped

        if changed:
            if self.is_sqlite_project():
                for old_path in path_map.keys():
                    self._mark_sqlite_image_deleted(old_path)
                self._mark_sqlite_images_dirty(path_map.values())
                self._mark_sqlite_project_dirty()
            if save:
                self.save_project()
        return changed

    def _remove_sqlite_artifacts(self, database_path):
        base = os.path.abspath(str(database_path or ""))
        for candidate in (base, f"{base}-wal", f"{base}-shm"):
            try:
                if os.path.exists(candidate):
                    os.remove(candidate)
            except OSError:
                pass

    def _default_sqlite_paths_for_new_project(self, name, save_dir):
        stem = str(name or "project").strip() or "project"
        directory = canonical_path(save_dir)
        return (
            os.path.join(directory, f"{stem}.sqlite_manifest.json"),
            os.path.join(directory, f"{stem}.taxamask.sqlite"),
        )

    def _create_sqlite_project_storage(self, name, save_dir):
        from .project_sqlite_schema import create_2d_project_database

        manifest_path, database_path = self._default_sqlite_paths_for_new_project(name, save_dir)
        if os.path.exists(manifest_path):
            raise FileExistsError(manifest_path)
        if any(os.path.exists(candidate) for candidate in (database_path, f"{database_path}-wal", f"{database_path}-shm")):
            raise FileExistsError(database_path)

        conn = None
        manifest_created = False
        try:
            conn = create_2d_project_database(database_path)
            conn.close()
            conn = None
            write_project_manifest(
                manifest_path,
                "2d_image_annotation",
                self.project_data.get("name", name or "Untitled"),
                database_path,
                extra={
                    "project_asset_root": ".",
                    "created_as": "sqlite_default",
                },
            )
            manifest_created = True
            self.current_project_path = canonical_path(manifest_path)
            self.current_database_path = canonical_path(database_path)
            self.current_storage_backend = SQLITE_BACKEND
            self._sqlite_project_dirty = True
            self.flush_sqlite_changes(project_dirty=True, integrity_check=True)
            return self.current_project_path
        except Exception:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            if manifest_created:
                try:
                    os.remove(manifest_path)
                except OSError:
                    pass
            self._remove_sqlite_artifacts(database_path)
            self.current_storage_backend = LEGACY_JSON_BACKEND
            self.current_database_path = ""
            self._legacy_json_write_enabled = False
            raise

    def create_project(self, name, save_dir, template_id=None, storage_backend=SQLITE_BACKEND):
        self.clear()
        os.makedirs(save_dir, exist_ok=True)
        template = get_project_template(template_id or PROJECT_TEMPLATE_ANT)
        self.project_data["name"] = name
        self.project_data["project_template"] = template["template_id"]
        self.project_data["taxonomy"] = sanitize_taxonomy(template["taxonomy"], fallback=template["taxonomy"])
        self.project_data["locator_scope"] = sanitize_locator_scope(
            template["locator_scope"],
            self.project_data["taxonomy"],
            fallback=template["locator_scope"],
        )
        self.project_data["category_supercategory"] = template["category_supercategory"]
        self.project_data["taxon_label"] = template["taxon_label"]
        self.ensure_default_model_profile()
        if storage_backend == SQLITE_BACKEND:
            return self._create_sqlite_project_storage(name, save_dir)
        if storage_backend not in (LEGACY_JSON_BACKEND, "json"):
            raise ValueError(f"unsupported_project_storage_backend:{storage_backend}")
        self.current_storage_backend = LEGACY_JSON_BACKEND
        self.current_database_path = ""
        self._legacy_json_write_enabled = True
        self.current_project_path = canonical_path(os.path.join(save_dir, f"{name}.json"))
        self.save_project()
        return self.current_project_path

    def _to_relative_for_project_path(self, abs_path, project_path):
        if not abs_path:
            return abs_path
        try:
            project_dir = os.path.dirname(os.path.abspath(project_path or self.current_project_path or ""))
            normalized_path = str(abs_path)
            if normalized_path and not os.path.isabs(normalized_path):
                normalized_path = self._to_absolute(normalized_path)
            return os.path.relpath(normalized_path, project_dir).replace("\\", "/")
        except (ValueError, TypeError):
            return abs_path

    def _to_relative(self, abs_path):
        """Convert absolute path to relative path based on project file location."""
        if not self.current_project_path:
            return abs_path
        return self._to_relative_for_project_path(abs_path, self.current_project_path)

    def _to_absolute(self, path):
        """Convert relative path to absolute path."""
        if path is None:
            return ""

        path = str(path).replace("\\", "/")
        if not path:
            return ""

        if os.path.isabs(path):
            abs_path = os.path.abspath(os.path.normpath(path))
            if os.path.exists(abs_path):
                return abs_path
            relocated = self._resolve_known_relocated_output(abs_path)
            if relocated:
                return os.path.abspath(os.path.normpath(relocated))
            return abs_path

        project_abs_path = ""
        if self.current_project_path:
            project_dir = os.path.dirname(os.path.abspath(self.current_project_path))
            project_abs_path = os.path.abspath(os.path.normpath(os.path.join(project_dir, path)))
            if os.path.exists(project_abs_path):
                return project_abs_path
            relocated = self._resolve_known_relocated_output(project_abs_path)
            if relocated:
                return os.path.abspath(os.path.normpath(relocated))

        cwd_abs_path = os.path.abspath(os.path.normpath(path))
        if os.path.exists(cwd_abs_path):
            return cwd_abs_path

        relocated = self._resolve_known_relocated_output(cwd_abs_path)
        if relocated:
            return os.path.abspath(os.path.normpath(relocated))

        relocated = self._resolve_known_relocated_output(path)
        if relocated:
            return os.path.abspath(os.path.normpath(relocated))

        return project_abs_path or cwd_abs_path

    def _path_identity(self, path):
        if not path:
            return ""
        try:
            absolute = self._to_absolute(path)
        except Exception:
            absolute = path
        return self._absolute_path_identity(absolute)

    def _absolute_path_identity(self, path):
        if not path:
            return ""
        return path_identity(path)

    def _registered_image_key_for_path(self, path):
        target = self._path_identity(path)
        if not target:
            return ""
        for image_path in self.project_data.get("images", []):
            if self._path_identity(image_path) == target:
                return image_path
        return ""

    def _merge_loaded_label_entry(self, existing, incoming):
        merged = self._normalize_label_taxon_fields(dict(existing or {}))
        incoming = self._normalize_label_taxon_fields(dict(incoming or {}))

        for key, value in incoming.items():
            if isinstance(value, dict):
                target = merged.setdefault(key, {})
                if not isinstance(target, dict):
                    target = {}
                for child_key, child_value in value.items():
                    if child_key not in target or target.get(child_key) in ({}, [], "", None):
                        target[child_key] = child_value
                merged[key] = target
                continue

            if key == "status":
                if value == "labeled" or not merged.get("status") or merged.get("status") == "unlabeled":
                    merged[key] = value
                continue

            if value not in ("", None, "Unknown") and merged.get(key) in ("", None, "Unknown"):
                merged[key] = value

        if merged.get("parts"):
            merged["status"] = "labeled"
        return self._normalize_label_taxon_fields(merged)

    def clear(self):
        """Resets the project data to a clean state."""
        self.project_data = {
            "name": "Untitled",
            "images": [],
            "labels": {},
            "taxonomy": list(DEFAULT_PROJECT_TAXONOMY),
            "locator_scope": list(DEFAULT_LOCATOR_SCOPE),
            "project_template": PROJECT_TEMPLATE_ANT,
            "category_supercategory": DEFAULT_CATEGORY_SUPERCATEGORY,
            "taxon_label": "Genus",
            "scales": {},
            "image_provenance": {},
            "image_groups": {
                "custom_groups": [],
            },
            "vlm_preannotation": {
                "target_parts": [],
                "processing_scope": "image_group",
                "image_group": DEFAULT_VLM_IMAGE_GROUP,
                "concurrency": 1,
                "prompt_profile_id": DEFAULT_VLM_PROMPT_PROFILE_ID,
                "prompt_profile": sanitize_vlm_prompt_profile({}),
            },
            "blink_context_roi_parents": {},
            "parent_box_aspect_ratios": dict(DEFAULT_PARENT_BOX_ASPECT_RATIOS),
            "model_profiles": {},
            "cascade_routes": {
                "version": PROJECT_ROUTE_MANIFEST_VERSION,
                "routes": [],
            },
        }
        self.current_project_path = None
        self.current_storage_backend = LEGACY_JSON_BACKEND
        self.current_database_path = ""
        self._sqlite_dirty_images = set()
        self._sqlite_deleted_images = set()
        self._sqlite_project_dirty = False
        self._legacy_json_write_enabled = False
        self.known_relocated_roots = list(getattr(self, "known_relocated_roots", []))

    def _is_sqlite_manifest_payload(self, payload):
        return (
            isinstance(payload, dict)
            and payload.get("schema_version") == PROJECT_MANIFEST_SCHEMA_VERSION
            and payload.get("storage_backend") == SQLITE_BACKEND
        )

    def is_sqlite_project(self):
        return getattr(self, "current_storage_backend", "json") == SQLITE_BACKEND

    def _mark_sqlite_image_dirty(self, image_path):
        if not self.is_sqlite_project() or not image_path:
            return
        self._sqlite_dirty_images.add(self._registered_image_key_for_path(image_path) or image_path)

    def _mark_sqlite_images_dirty(self, image_paths):
        for image_path in image_paths or []:
            self._mark_sqlite_image_dirty(image_path)

    def _mark_sqlite_image_deleted(self, image_path):
        if not self.is_sqlite_project() or not image_path:
            return
        self._sqlite_deleted_images.add(image_path)

    def _mark_sqlite_project_dirty(self):
        if self.is_sqlite_project():
            self._sqlite_project_dirty = True

    def mark_sqlite_project_dirty(self):
        self._mark_sqlite_project_dirty()

    def mark_sqlite_images_dirty(self, image_paths):
        self._mark_sqlite_images_dirty(image_paths)

    def mark_sqlite_image_dirty(self, image_path):
        self._mark_sqlite_image_dirty(image_path)

    def flush_sqlite_changes(self, *, image_paths=None, deleted_image_paths=None, project_dirty=None, integrity_check=False):
        if not self.is_sqlite_project():
            return False
        from .project_sqlite_writer import flush_project_changes

        if image_paths is None:
            image_paths = sorted(self._sqlite_dirty_images)
        else:
            image_paths = list(image_paths or [])
        if deleted_image_paths is None:
            deleted_image_paths = sorted(self._sqlite_deleted_images)
        else:
            deleted_image_paths = list(deleted_image_paths or [])
        if project_dirty is None:
            project_dirty = self._sqlite_project_dirty

        if not image_paths and not deleted_image_paths and not project_dirty:
            return False

        flush_project_changes(
            self,
            image_paths=image_paths,
            deleted_image_paths=deleted_image_paths,
            integrity_check=integrity_check,
        )
        flushed_images = set(image_paths)
        deleted_images = set(deleted_image_paths)
        self._sqlite_dirty_images.difference_update(flushed_images)
        self._sqlite_deleted_images.difference_update(deleted_images)
        if project_dirty:
            self._sqlite_project_dirty = False
        return True

    def _sqlite_force_deleted_image_paths(self):
        if not self.is_sqlite_project() or not self.current_database_path:
            return []
        try:
            import sqlite3

            conn = sqlite3.connect(self.current_database_path)
            try:
                rows = conn.execute("SELECT path FROM images WHERE status != 'deleted'").fetchall()
            finally:
                conn.close()
        except Exception:
            return []
        current_identities = {
            self._path_identity(image_path)
            for image_path in self.project_data.get("images", []) or []
            if image_path
        }
        current_identities.discard("")
        deleted = []
        for row in rows:
            stored_path = str(row[0] or "")
            if stored_path and self._path_identity(stored_path) not in current_identities:
                deleted.append(stored_path)
        return deleted

    def _apply_loaded_project_data(self, loaded_data, project_path):
        self.clear() # Ensure clean state

        self.current_project_path = canonical_path(project_path)

        # FIX: Strictly use loaded taxonomy if present.
        # This prevents the system from overriding custom empty taxonomies with defaults.
        if "taxonomy" in loaded_data:
            loaded_taxonomy = loaded_data["taxonomy"]
        else:
            # Fallback only if key is completely missing
            loaded_taxonomy = list(DEFAULT_PROJECT_TAXONOMY)

        self.project_data["taxonomy"] = sanitize_taxonomy(loaded_taxonomy, fallback=DEFAULT_PROJECT_TAXONOMY)

        if "locator_scope" in loaded_data:
            self.project_data["locator_scope"] = sanitize_locator_scope(
                loaded_data.get("locator_scope"),
                self.project_data["taxonomy"],
                fallback=DEFAULT_LOCATOR_SCOPE,
            )
        else:
            # Legacy compatibility: old projects keep using their saved taxonomy as locator scope.
            self.project_data["locator_scope"] = legacy_locator_scope_for_loaded_taxonomy(
                self.project_data["taxonomy"]
            )

        self.project_data["blink_context_roi_parents"] = self._sanitize_blink_context_roi_parents(
            loaded_data.get("blink_context_roi_parents", {})
        )
        self.project_data["parent_box_aspect_ratios"] = self._sanitize_parent_box_aspect_ratios(
            loaded_data.get("parent_box_aspect_ratios", DEFAULT_PARENT_BOX_ASPECT_RATIOS)
        )
        self.project_data["image_groups"] = self._sanitize_image_groups(
            loaded_data.get("image_groups", {})
        )
        self.project_data["vlm_preannotation"] = self._sanitize_vlm_preannotation_settings(
            loaded_data.get("vlm_preannotation", {})
        )
        self.project_data["cascade_routes"] = self._sanitize_cascade_routes(
            loaded_data.get("cascade_routes", {})
        )
        self.project_data["model_profiles"] = self._sanitize_model_profiles(
            loaded_data.get("model_profiles", {})
        )

        self.project_data["name"] = loaded_data.get("name", "Untitled")
        self.project_data["project_template"] = str(loaded_data.get("project_template", "") or "")
        self.project_data["category_supercategory"] = (
            str(loaded_data.get("category_supercategory", DEFAULT_CATEGORY_SUPERCATEGORY)).strip()
            or DEFAULT_CATEGORY_SUPERCATEGORY
        )
        self.project_data["taxon_label"] = str(loaded_data.get("taxon_label", "Taxon") or "Taxon").strip() or "Taxon"

        image_keys_seen = set()
        image_key_by_identity = {}

        # Handle Images
        for img_rel in loaded_data.get("images", []):
            img_abs = self._to_absolute(img_rel)
            identity = self._absolute_path_identity(img_abs)
            if not identity or identity in image_keys_seen:
                continue
            image_keys_seen.add(identity)
            self.project_data["images"].append(img_abs)
            image_key_by_identity[identity] = img_abs

        # Handle Labels
        for img_rel, label_data in loaded_data.get("labels", {}).items():
            img_abs = self._to_absolute(img_rel)
            project_key = image_key_by_identity.get(self._absolute_path_identity(img_abs), img_abs)
            existing = self.project_data["labels"].get(project_key)
            if existing:
                self.project_data["labels"][project_key] = self._merge_loaded_label_entry(existing, label_data)
            else:
                self.project_data["labels"][project_key] = self._normalize_label_taxon_fields(label_data)

        for img_abs in self.project_data.get("images", []):
            self.project_data["labels"].setdefault(img_abs, self._default_label_entry())

        # Handle Scales
        for img_rel, scale_val in loaded_data.get("scales", {}).items():
            img_abs = self._to_absolute(img_rel)
            project_key = image_key_by_identity.get(self._absolute_path_identity(img_abs), img_abs)
            self.project_data["scales"][project_key] = scale_val

        # Handle per-image provenance for agent-imported PDF candidates.
        self.project_data["image_provenance"] = {}
        for img_rel, provenance in loaded_data.get("image_provenance", {}).items():
            img_abs = self._to_absolute(img_rel)
            if isinstance(provenance, dict):
                project_key = image_key_by_identity.get(self._absolute_path_identity(img_abs), img_abs)
                existing = self.project_data["image_provenance"].get(project_key, {})
                if isinstance(existing, dict):
                    merged = dict(existing)
                    merged.update(provenance)
                    self.project_data["image_provenance"][project_key] = merged
                else:
                    self.project_data["image_provenance"][project_key] = dict(provenance)

    def load_project(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)

        if self._is_sqlite_manifest_payload(loaded_data):
            from .project_sqlite_loader import load_2d_sqlite_project_manifest

            loaded_sqlite = load_2d_sqlite_project_manifest(path)
            self._apply_loaded_project_data(loaded_sqlite["project_data"], path)
            self.current_storage_backend = SQLITE_BACKEND
            self.current_database_path = canonical_path(loaded_sqlite.get("database_path", ""))
            self._sqlite_dirty_images = set()
            self._sqlite_deleted_images = set()
            self._sqlite_project_dirty = False
            self._legacy_json_write_enabled = False
            return

        self._apply_loaded_project_data(loaded_data, path)
        self.current_storage_backend = LEGACY_JSON_BACKEND
        self.current_database_path = ""
        self._legacy_json_write_enabled = False

    def enable_legacy_json_writes_for_compatibility(self, enabled=True):
        self._legacy_json_write_enabled = bool(enabled)

    def _save_legacy_json_project(self):
        project_path = os.path.abspath(self.current_project_path)
        project_dir = os.path.dirname(project_path) or "."
        data_to_save = self.legacy_json_payload(project_path)
        tmp_path = f"{project_path}.tmp"
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            with open(tmp_path, 'r', encoding='utf-8') as f:
                json.load(f)
            self._backup_current_project_file(project_path)
            os.replace(tmp_path, project_path)
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            raise
        try:
            dir_fd = os.open(project_dir, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass

    def legacy_json_payload(self, project_path=None):
        target_project_path = os.path.abspath(str(project_path or self.current_project_path or "project.json"))
        self._sync_active_model_profile_from_project_fields()
        data_to_save = {
            "name": self.project_data["name"],
            "taxonomy": self.project_data["taxonomy"],
            "locator_scope": self.get_locator_scope(),
            "project_template": self.project_data.get("project_template", ""),
            "category_supercategory": self._category_supercategory(),
            "taxon_label": self.project_data.get("taxon_label", "Taxon"),
            "vlm_preannotation": self.get_vlm_preannotation_settings(),
            "blink_context_roi_parents": self.get_blink_context_roi_parents(),
            "parent_box_aspect_ratios": self.get_parent_box_aspect_ratios(),
            "model_profiles": self.get_model_profiles(),
            "cascade_routes": self.get_cascade_routes(),
            "images": [],
            "labels": {},
            "scales": {},
            "image_provenance": {},
            "image_groups": self._sanitize_image_groups(self.project_data.get("image_groups", {})),
        }

        for img_abs in self.project_data["images"]:
            data_to_save["images"].append(self._to_relative_for_project_path(img_abs, target_project_path))

        for img_abs, label_data in self.project_data["labels"].items():
            if not self._label_entry_has_saved_content(label_data):
                continue
            rel_path = self._to_relative_for_project_path(img_abs, target_project_path)
            data_to_save["labels"][rel_path] = label_data

        for img_abs, scale_val in self.project_data.get("scales", {}).items():
            rel_path = self._to_relative_for_project_path(img_abs, target_project_path)
            data_to_save["scales"][rel_path] = scale_val

        for img_abs, provenance in self.project_data.get("image_provenance", {}).items():
            rel_path = self._to_relative_for_project_path(img_abs, target_project_path)
            data_to_save["image_provenance"][rel_path] = provenance

        return data_to_save

    def save_project(self, force=False):
        if getattr(self, "current_storage_backend", "json") == SQLITE_BACKEND:
            if force:
                return self.flush_sqlite_changes(
                    image_paths=list(self.project_data.get("images", []) or []),
                    deleted_image_paths=self._sqlite_force_deleted_image_paths(),
                    project_dirty=True,
                )
            return self.flush_sqlite_changes()
        if self.current_project_path:
            if not getattr(self, "_legacy_json_write_enabled", False):
                raise RuntimeError("legacy_json_project_is_read_only; migrate to SQLite or export a legacy JSON copy")
            return self._save_legacy_json_project()

    def add_images(self, image_paths, progress_callback=None, save=True):
        paths = list(image_paths or [])
        total = len(paths)
        if progress_callback:
            progress_callback(0, total, "")

        images = self.project_data.setdefault("images", [])
        labels = self.project_data.setdefault("labels", {})
        existing = {
            path_identity(path)
            for path in images
            if path
        }
        added = 0
        for index, img in enumerate(paths, start=1):
            abs_img = canonical_path(img)
            identity = path_identity(abs_img)
            if identity not in existing:
                images.append(abs_img)
                labels.setdefault(abs_img, self._default_label_entry())
                self._mark_sqlite_image_dirty(abs_img)
                existing.add(identity)
                added += 1
            if progress_callback:
                progress_callback(index, total, abs_img)

        if save:
            self.save_project()
        return added

    def remove_image(self, image_path, save=True):
        """Removes an image and its labels from the project."""
        removed = self.remove_images([image_path], save=save)
        return bool(removed)

    def remove_images(self, image_paths, progress_callback=None, save=True):
        """Removes images and related project metadata, saving only once for batches."""
        paths = [path for path in (image_paths or []) if path]
        total = len(paths)
        if progress_callback:
            progress_callback(0, total, "")
        if not paths:
            if save:
                self.save_project()
            return 0

        remove_identities = {self._path_identity(path) for path in paths}
        remove_identities.discard("")

        def should_remove(path):
            return self._path_identity(path) in remove_identities

        old_images = list(self.project_data.get("images", []))
        kept_images = [path for path in old_images if not should_remove(path)]
        removed_count = len(old_images) - len(kept_images)
        self.project_data["images"] = kept_images
        for stored_path in old_images:
            if should_remove(stored_path):
                self._mark_sqlite_image_deleted(stored_path)

        for key in ("labels", "scales", "image_provenance"):
            mapping = self.project_data.get(key)
            if not isinstance(mapping, dict):
                continue
            for stored_path in list(mapping.keys()):
                if should_remove(stored_path):
                    self._mark_sqlite_image_deleted(stored_path)
                    del mapping[stored_path]

        for group in self.project_data.get("image_groups", {}).get("custom_groups", []):
            if not isinstance(group, dict) or not isinstance(group.get("images"), list):
                continue
            group["images"] = [path for path in group.get("images", []) if not should_remove(path)]

        if progress_callback:
            for index, path in enumerate(paths, start=1):
                progress_callback(index, total, str(path))

        if removed_count:
            self._mark_sqlite_project_dirty()
        if save:
            self.save_project()
        return removed_count

    def set_image_provenance(self, image_path, provenance, save=True):
        abs_path = self._to_absolute(image_path)
        if "image_provenance" not in self.project_data:
            self.project_data["image_provenance"] = {}
        self.project_data["image_provenance"][abs_path] = dict(provenance or {})
        self._mark_sqlite_image_dirty(abs_path)
        if save:
            self.save_project()

    def get_image_provenance(self, image_path):
        abs_path = self._to_absolute(image_path)
        provenance = self.project_data.get("image_provenance", {}).get(abs_path, {})
        return dict(provenance) if isinstance(provenance, dict) else {}

    def set_description_source(self, image_path, part_name, source_meta, save=True):
        abs_path = self._to_absolute(image_path)
        clean_part = str(part_name or "").strip()
        if not abs_path or not clean_part:
            return
        if abs_path not in self.project_data["labels"]:
            self.project_data["labels"][abs_path] = self._default_label_entry()
        entry = self._normalize_label_taxon_fields(self.project_data["labels"][abs_path])
        entry.setdefault("description_sources", {})[clean_part] = dict(source_meta or {})
        self._append_label_journal_entry(abs_path, "set_description_source")
        self._mark_sqlite_image_dirty(abs_path)
        if save:
            self.save_project()

    def get_description_source(self, image_path, part_name):
        abs_path = self._to_absolute(image_path)
        clean_part = str(part_name or "").strip()
        entry = self.project_data.get("labels", {}).get(abs_path, {})
        sources = entry.get("description_sources", {}) if isinstance(entry, dict) else {}
        if not isinstance(sources, dict):
            return {}
        source = sources.get(clean_part, {})
        return dict(source) if isinstance(source, dict) else {}

    def set_part_description(self, image_path, part_name, description_text, source_meta=None, save=True):
        abs_path = self._to_absolute(image_path)
        clean_part = str(part_name or "").strip()
        if not abs_path or not clean_part:
            return
        if abs_path not in self.project_data["labels"]:
            self.project_data["labels"][abs_path] = self._default_label_entry()
        entry = self._normalize_label_taxon_fields(self.project_data["labels"][abs_path])
        text = str(description_text or "").strip()
        if text:
            entry.setdefault("descriptions", {})[clean_part] = text
        elif clean_part in entry.get("descriptions", {}):
            del entry["descriptions"][clean_part]
        if source_meta is not None:
            if source_meta:
                entry.setdefault("description_sources", {})[clean_part] = dict(source_meta)
            elif clean_part in entry.get("description_sources", {}):
                del entry["description_sources"][clean_part]
        self._append_label_journal_entry(abs_path, "set_part_description")
        self._mark_sqlite_image_dirty(abs_path)
        if save:
            self.save_project()

    def get_part_description(self, image_path, part_name):
        abs_path = self._to_absolute(image_path)
        clean_part = str(part_name or "").strip()
        entry = self.project_data.get("labels", {}).get(abs_path, {})
        descriptions = entry.get("descriptions", {}) if isinstance(entry, dict) else {}
        if not isinstance(descriptions, dict):
            return ""
        return str(descriptions.get(clean_part, "") or "")

    def set_scale(self, image_path, pixels_per_mm, save=True):
        self.project_data["scales"][image_path] = pixels_per_mm
        self._mark_sqlite_image_dirty(image_path)
        if save:
            self.save_project()

    def get_scale(self, image_path):
        return self.project_data.get("scales", {}).get(image_path)

    def get_blink_context_roi_parents(self):
        clean_map = self._sanitize_blink_context_roi_parents(
            self.project_data.get("blink_context_roi_parents", {})
        )
        self.project_data["blink_context_roi_parents"] = clean_map
        return dict(clean_map)

    def ensure_default_model_profile(self):
        return self._sanitize_model_profiles(self.project_data.get("model_profiles", {}))

    def get_model_profiles(self):
        self._sync_active_model_profile_from_project_fields()
        return clone_model_profiles(self.project_data.get("model_profiles", {}))

    def set_model_profiles(self, model_profiles, save=True):
        clean_profiles = self._sanitize_model_profiles(model_profiles)
        self._mark_sqlite_project_dirty()
        if save:
            self.save_project()
        return clone_model_profiles(clean_profiles)

    def get_active_model_profile(self):
        profiles = self.get_model_profiles()
        active_id = profiles.get("active_profile_id")
        for profile in profiles.get("profiles", []):
            if profile.get("profile_id") == active_id:
                return clone_model_profiles(profile)
        profiles = self.ensure_default_model_profile()
        return clone_model_profiles(profiles.get("profiles", [{}])[0])

    def set_active_model_profile(self, profile_id, save=True):
        clean_profiles = set_active_model_profile_id(
            self.project_data.get("model_profiles", {}),
            profile_id,
        )
        self.project_data["model_profiles"] = self._sanitize_model_profiles(clean_profiles)
        active_profile = None
        active_id = self.project_data["model_profiles"].get("active_profile_id")
        for profile in self.project_data["model_profiles"].get("profiles", []):
            if profile.get("profile_id") == active_id:
                active_profile = clone_model_profiles(profile)
                break
        if not active_profile:
            active_profile = clone_model_profiles(self.project_data["model_profiles"].get("profiles", [{}])[0])
        parent_backend = active_profile.get("parent_backend", {})
        inference_params = active_profile.get("inference_params", {})
        self.project_data["locator_scope"] = sanitize_locator_scope(
            parent_backend.get("locator_scope", []),
            self.project_data.get("taxonomy", []),
            fallback=DEFAULT_LOCATOR_SCOPE,
        )
        self.project_data["parent_box_aspect_ratios"] = self._sanitize_parent_box_aspect_ratios(
            parent_backend.get("parent_box_aspect_ratios", {})
        )
        self.project_data["vlm_preannotation"] = self._sanitize_vlm_preannotation_settings(
            inference_params.get("vlm_preannotation", {})
        )
        self._mark_sqlite_project_dirty()
        if save:
            self.save_project()
        return active_profile

    def update_active_model_profile_parent_weights(self, locator_weights=None, segmenter_weights=None, save=True):
        profiles = self._sanitize_model_profiles(self.project_data.get("model_profiles", {}))
        active_id = profiles.get("active_profile_id", DEFAULT_MODEL_PROFILE_ID)
        updated_profile = None
        for profile in profiles.get("profiles", []):
            if profile.get("profile_id") != active_id:
                continue
            parent_backend = profile.setdefault("parent_backend", {})
            if locator_weights is not None:
                parent_backend["locator_weights"] = str(locator_weights or "")
            if segmenter_weights is not None:
                parent_backend["segmenter_weights"] = str(segmenter_weights or "BASE_SAM") or "BASE_SAM"
            updated_profile = clone_model_profiles(profile)
            break
        self.project_data["model_profiles"] = self._sanitize_model_profiles(profiles)
        self._mark_sqlite_project_dirty()
        if save:
            self.save_project()
        return updated_profile or self.get_active_model_profile()

    def _summarize_external_backend_for_audit(self, config):
        payload = config if isinstance(config, dict) else {}
        return {
            "backend_id": str(payload.get("backend_id") or ""),
            "display_name": str(payload.get("display_name") or ""),
            "python_executable": os.path.basename(str(payload.get("python_executable") or "")),
            "prepare_command_present": bool(str(payload.get("prepare_dataset_command") or "").strip()),
            "train_command_present": bool(str(payload.get("train_command") or "").strip()),
            "predict_command_present": bool(str(payload.get("predict_command") or "").strip()),
            "model_manifest": str(payload.get("model_manifest") or ""),
        }

    def _summarize_external_blink_for_audit(self, config):
        payload = config if isinstance(config, dict) else {}
        return {
            "backend_id": str(payload.get("backend_id") or ""),
            "display_name": str(payload.get("display_name") or ""),
            "python_executable": os.path.basename(str(payload.get("python_executable") or "")),
            "train_command_present": bool(str(payload.get("train_command") or "").strip()),
            "predict_command_present": bool(str(payload.get("predict_command") or "").strip()),
            "model_manifest": str(payload.get("model_manifest") or ""),
        }

    def build_model_profile_export_summary(self, export_format=None):
        profiles = self.get_model_profiles()
        active_profile = self.get_active_model_profile()
        parent_backend = active_profile.get("parent_backend", {}) if isinstance(active_profile.get("parent_backend"), dict) else {}
        child_defaults = active_profile.get("child_backend_defaults", {}) if isinstance(active_profile.get("child_backend_defaults"), dict) else {}
        inference_params = active_profile.get("inference_params", {}) if isinstance(active_profile.get("inference_params"), dict) else {}

        route_summaries = []
        for route in self.iter_cascade_routes():
            appointed = route.get("appointed_expert", {}) if isinstance(route.get("appointed_expert"), dict) else {}
            route_summaries.append(
                {
                    "parent": str(route.get("parent") or ""),
                    "child": str(route.get("child") or ""),
                    "enabled": bool(route.get("enabled", False)),
                    "expert_backend": str(appointed.get("expert_backend") or route.get("expert_backend") or ""),
                    "expert_id": str(appointed.get("expert_id") or route.get("expert_id") or ""),
                    "expert_manifest": str(appointed.get("expert_manifest") or route.get("expert_manifest") or ""),
                    "input_size": appointed.get("input_size") or route.get("input_size"),
                    "min_conf": route.get("min_conf"),
                }
            )

        return {
            "schema_version": MODEL_PROFILE_EXPORT_SUMMARY_SCHEMA_VERSION,
            "project_name": str(self.project_data.get("name") or ""),
            "project_path": os.path.abspath(self.current_project_path) if self.current_project_path else "",
            "export_format": str(export_format or ""),
            "active_profile_id": str(profiles.get("active_profile_id") or active_profile.get("profile_id") or ""),
            "active_profile": {
                "profile_id": str(active_profile.get("profile_id") or ""),
                "display_name": str(active_profile.get("display_name") or ""),
                "description": str(active_profile.get("description") or ""),
                "profile_scope": str(active_profile.get("profile_scope") or "2d_stl"),
            },
            "parent_backend": {
                "backend_type": str(parent_backend.get("backend_type") or ""),
                "locator_scope": list(parent_backend.get("locator_scope") or []),
                "locator_weights": str(parent_backend.get("locator_weights") or ""),
                "segmenter_weights": str(parent_backend.get("segmenter_weights") or ""),
                "train_params": dict(parent_backend.get("train_params") or {}),
                "parent_box_aspect_ratios": dict(parent_backend.get("parent_box_aspect_ratios") or {}),
                "external_backend": self._summarize_external_backend_for_audit(parent_backend.get("external_backend")),
            },
            "child_backend_defaults": {
                "backend_type": str(child_defaults.get("backend_type") or ""),
                "input_size": child_defaults.get("input_size"),
                "train_params": dict(child_defaults.get("train_params") or {}),
                "heatmap_params": dict(child_defaults.get("heatmap_params") or {}),
                "external_blink_backend": self._summarize_external_blink_for_audit(child_defaults.get("external_blink_backend")),
            },
            "inference_params": {
                "conf": inference_params.get("conf"),
                "adapt": inference_params.get("adapt"),
                "pad": inference_params.get("pad"),
                "noise_floor": inference_params.get("noise_floor"),
                "poly_epsilon": inference_params.get("poly_epsilon"),
                "vlm_preannotation": dict(inference_params.get("vlm_preannotation") or {}),
            },
            "route_count": len(route_summaries),
            "route_experts": route_summaries,
        }

    def write_model_profile_export_summary(self, output_dir, export_format=None):
        if not output_dir:
            return ""
        os.makedirs(output_dir, exist_ok=True)
        summary_path = os.path.join(output_dir, "model_profile_summary.json")
        with open(summary_path, "w", encoding="utf-8") as handle:
            json.dump(
                self.build_model_profile_export_summary(export_format=export_format),
                handle,
                indent=2,
                ensure_ascii=False,
            )
        return summary_path

    def _clone_cascade_route(self, route_entry):
        route = dict(route_entry or {})
        appointed_expert = route.get("appointed_expert")
        if isinstance(appointed_expert, dict):
            route["appointed_expert"] = dict(appointed_expert)
        else:
            route["appointed_expert"] = {}

        expert_candidates = route.get("expert_candidates")
        if isinstance(expert_candidates, list):
            route["expert_candidates"] = [
                dict(candidate)
                for candidate in expert_candidates
                if isinstance(candidate, dict)
            ]
        else:
            route["expert_candidates"] = []
        return route

    def get_cascade_routes(self):
        clean_manifest = self._sanitize_cascade_routes(self.project_data.get("cascade_routes", {}))
        return {
            "version": clean_manifest.get("version", PROJECT_ROUTE_MANIFEST_VERSION),
            "routes": [self._clone_cascade_route(route) for route in clean_manifest.get("routes", [])],
        }

    def merge_cascade_route_expert_candidates(self, route_entry, supplemental_candidates=None, prioritize_supplemental=False):
        route = dict(route_entry or {})
        appointed_expert = get_route_appointed_expert(route)
        if prioritize_supplemental:
            persisted_candidates = route.get("expert_candidates", [])
            merged_candidates = merge_expert_candidates(
                supplemental_candidates or [],
                persisted_candidates,
                appointed_expert,
                appointed_expert=None,
            )
        else:
            persisted_candidates = get_route_persisted_expert_candidates(route)
            merged_candidates = merge_expert_candidates(
                persisted_candidates,
                supplemental_candidates or [],
                appointed_expert=appointed_expert,
            )
        route["appointed_expert"] = dict(appointed_expert)
        route["expert_candidates"] = [dict(candidate) for candidate in merged_candidates]
        route.update(appointed_expert)
        return route

    def iter_cascade_routes(self):
        return [self._clone_cascade_route(route) for route in self.get_cascade_routes().get("routes", [])]

    def get_cascade_route(self, parent_part, child_part):
        clean_parent = str(parent_part or "").strip()
        clean_child = str(child_part or "").strip()
        if not clean_parent or not clean_child:
            return None

        for route in self.iter_cascade_routes():
            if route.get("parent") == clean_parent and route.get("child") == clean_child:
                return self._clone_cascade_route(route)
        return None

    def set_cascade_route(self, route_entry, save=True):
        clean_entry = sanitize_project_route_manifest(
            {"routes": [route_entry]},
            taxonomy=self.project_data.get("taxonomy", []),
        ).get("routes", [])
        if not clean_entry:
            return None
        clean_entry = dict(clean_entry[0])

        manifest = self.get_cascade_routes()
        routes = []
        replaced = False
        for route in manifest.get("routes", []):
            if route.get("parent") == clean_entry.get("parent") and route.get("child") == clean_entry.get("child"):
                routes.append(clean_entry)
                replaced = True
            else:
                routes.append(dict(route))
        if not replaced:
            routes.append(clean_entry)

        self.project_data["cascade_routes"] = self._sanitize_cascade_routes(
            {
                "version": PROJECT_ROUTE_MANIFEST_VERSION,
                "routes": routes,
            }
        )
        self._mark_sqlite_project_dirty()
        if save:
            self.save_project()
        return clean_entry

    def register_cascade_route_candidate(
        self,
        parent_part,
        child_part,
        *,
        expert_id=None,
        expert_part=None,
        expert_filename=None,
        expert_backend=None,
        expert_manifest=None,
        input_size=None,
        backend_params=None,
        note=None,
        focus_source=None,
        registration_source="blink_candidate",
        save=True,
    ):
        existing = self.get_cascade_route(parent_part, child_part) or {}
        supplemental_candidate = sanitize_expert_reference(
            expert_part=expert_part,
            expert_filename=expert_filename,
            expert_id=expert_id,
        )
        supplemental_candidates = [supplemental_candidate] if supplemental_candidate.get("expert_id") else []
        route_payload = {
            "parent": parent_part,
            "child": child_part,
            "enabled": bool(existing.get("enabled", False)),
            "min_conf": existing.get("min_conf"),
            "registration_source": registration_source,
            "focus_source": focus_source,
            "appointed_expert": dict(existing.get("appointed_expert") or {}),
            "expert_candidates": [dict(candidate) for candidate in existing.get("expert_candidates", [])],
            "expert_id": existing.get("expert_id"),
            "expert_part": existing.get("expert_part"),
            "expert_filename": existing.get("expert_filename"),
            "expert_backend": expert_backend if expert_backend is not None else existing.get("expert_backend"),
            "expert_manifest": expert_manifest if expert_manifest is not None else existing.get("expert_manifest"),
            "input_size": input_size if input_size is not None else existing.get("input_size"),
            "backend_params": backend_params if backend_params is not None else existing.get("backend_params"),
            "note": note if note is not None else existing.get("note"),
        }
        route_payload.update(sanitize_route_backend_fields(route_payload))
        if supplemental_candidate.get("expert_id"):
            supplemental_candidate.update(sanitize_route_backend_fields(route_payload))
            supplemental_candidates = [supplemental_candidate]
        route_payload = self.merge_cascade_route_expert_candidates(
            route_payload,
            supplemental_candidates,
            prioritize_supplemental=bool(supplemental_candidates),
        )
        return self.set_cascade_route(route_payload, save=save)

    def appoint_cascade_route_expert(
        self,
        parent_part,
        child_part,
        *,
        expert_part=None,
        expert_filename=None,
        expert_id=None,
        expert_backend=None,
        expert_manifest=None,
        input_size=None,
        backend_params=None,
        note=None,
        save=True,
    ):
        route = self.get_cascade_route(parent_part, child_part)
        if not route:
            route = self.register_cascade_route_candidate(parent_part, child_part, save=False)
        if not route:
            return None

        clean_expert = sanitize_expert_reference(
            expert_part=expert_part,
            expert_filename=expert_filename,
            expert_id=expert_id,
        )
        route_payload = dict(route)
        route_payload["appointed_expert"] = dict(clean_expert)
        route_payload["appointed_expert"].update(
            sanitize_route_backend_fields(
                {
                    "expert_backend": expert_backend if expert_backend is not None else route.get("expert_backend"),
                    "expert_manifest": expert_manifest if expert_manifest is not None else route.get("expert_manifest"),
                    "input_size": input_size if input_size is not None else route.get("input_size"),
                    "backend_params": backend_params if backend_params is not None else route.get("backend_params"),
                    "note": note if note is not None else route.get("note"),
                }
            )
        )
        route_payload["expert_candidates"] = [
            dict(candidate)
            for candidate in merge_expert_candidates(
                route.get("expert_candidates", []),
                route_payload["appointed_expert"],
                appointed_expert=route_payload["appointed_expert"],
            )
        ]
        route_payload.update(clean_expert)
        route_payload.update(sanitize_route_backend_fields(route_payload["appointed_expert"]))
        return self.set_cascade_route(route_payload, save=save)

    def set_cascade_route_enabled(self, parent_part, child_part, enabled, save=True):
        route = self.get_cascade_route(parent_part, child_part)
        if not route:
            route = self.register_cascade_route_candidate(parent_part, child_part, save=False)
        if not route:
            return None

        route_payload = dict(route)
        route_payload["enabled"] = bool(enabled)
        return self.set_cascade_route(route_payload, save=save)

    def delete_cascade_route(self, parent_part, child_part, save=True):
        clean_parent = str(parent_part or "").strip()
        clean_child = str(child_part or "").strip()
        if not clean_parent or not clean_child:
            return False

        manifest = self.get_cascade_routes()
        routes = [
            dict(route)
            for route in manifest.get("routes", [])
            if not (route.get("parent") == clean_parent and route.get("child") == clean_child)
        ]
        if len(routes) == len(manifest.get("routes", [])):
            return False

        self.project_data["cascade_routes"] = self._sanitize_cascade_routes(
            {"version": PROJECT_ROUTE_MANIFEST_VERSION, "routes": routes}
        )
        self._mark_sqlite_project_dirty()
        if save:
            self.save_project()
        return True

    def remove_cascade_route_expert_candidate(self, parent_part, child_part, expert_id, save=True):
        clean_parent = str(parent_part or "").strip()
        clean_child = str(child_part or "").strip()
        clean_expert_id = str(expert_id or "").strip()
        if not clean_parent or not clean_child or not clean_expert_id:
            return False

        route = self.get_cascade_route(clean_parent, clean_child)
        if not route:
            return False

        appointed_id = str(get_route_appointed_expert(route).get("expert_id") or "").strip()
        if appointed_id == clean_expert_id:
            return False

        candidates = [
            dict(candidate)
            for candidate in route.get("expert_candidates", [])
            if isinstance(candidate, dict)
        ]
        kept_candidates = [
            candidate
            for candidate in candidates
            if str(candidate.get("expert_id") or "").strip() != clean_expert_id
        ]
        if len(kept_candidates) == len(candidates):
            return False

        route_payload = dict(route)
        route_payload["expert_candidates"] = kept_candidates
        return bool(self.set_cascade_route(route_payload, save=save))

    def remove_cascade_route_expert_references(self, expert_id, save=True):
        clean_expert_id = str(expert_id or "").strip()
        if not clean_expert_id:
            return 0

        manifest = self.get_cascade_routes()
        updated_routes = []
        changed_count = 0
        empty_expert = sanitize_expert_reference()

        for route in manifest.get("routes", []):
            route_payload = dict(route)
            changed = False
            appointed_id = str(get_route_appointed_expert(route_payload).get("expert_id") or "").strip()

            candidates = [
                dict(candidate)
                for candidate in route_payload.get("expert_candidates", [])
                if isinstance(candidate, dict)
            ]
            kept_candidates = [
                candidate
                for candidate in candidates
                if str(candidate.get("expert_id") or "").strip() != clean_expert_id
            ]
            if len(kept_candidates) != len(candidates):
                changed = True
            route_payload["expert_candidates"] = kept_candidates

            if appointed_id == clean_expert_id:
                route_payload["appointed_expert"] = dict(empty_expert)
                route_payload["expert_id"] = None
                route_payload["expert_part"] = None
                route_payload["expert_filename"] = None
                changed = True

            if changed:
                changed_count += 1
            updated_routes.append(route_payload)

        if changed_count <= 0:
            return 0

        self.project_data["cascade_routes"] = self._sanitize_cascade_routes(
            {"version": PROJECT_ROUTE_MANIFEST_VERSION, "routes": updated_routes}
        )
        self._mark_sqlite_project_dirty()
        if save:
            self.save_project()
        return changed_count

    def get_current_project_expert_bucket_impacts(self, child_part):
        clean_child = str(child_part or "").strip()
        impacts = {
            "child_part": clean_child,
            "routes": [],
        }
        if not clean_child:
            return impacts

        for route in self.iter_cascade_routes():
            if route.get("child") != clean_child:
                continue
            impacts["routes"].append(
                {
                    "parent": route.get("parent"),
                    "child": route.get("child"),
                    "enabled": bool(route.get("enabled", False)),
                    "registration_source": route.get("registration_source"),
                    "appointed_expert_id": route.get("appointed_expert", {}).get("expert_id"),
                    "expert_id": route.get("expert_id"),
                }
            )

        impacts["routes"].sort(key=lambda entry: (str(entry.get("parent") or ""), str(entry.get("child") or "")))
        return impacts

    def remove_current_project_expert_bucket_routes(self, child_part, save=True):
        clean_child = str(child_part or "").strip()
        if not clean_child:
            return 0

        manifest = self.get_cascade_routes()
        original_routes = list(manifest.get("routes", []))
        kept_routes = [
            dict(route)
            for route in original_routes
            if route.get("child") != clean_child
        ]
        removed_count = len(original_routes) - len(kept_routes)
        if removed_count <= 0:
            return 0

        self.project_data["cascade_routes"] = self._sanitize_cascade_routes(
            {
                "version": PROJECT_ROUTE_MANIFEST_VERSION,
                "routes": kept_routes,
            }
        )
        self._mark_sqlite_project_dirty()
        if save:
            self.save_project()
        return removed_count

    def get_blink_context_parent(self, target_part):
        clean_target = str(target_part).strip()
        if not clean_target:
            return None
        return self.get_blink_context_roi_parents().get(clean_target)

    def remember_blink_context_parent(self, target_part, parent_part, save=True):
        clean_target = str(target_part).strip()
        clean_parent = str(parent_part).strip()
        if not clean_target or not clean_parent or clean_target == clean_parent:
            return False

        taxonomy = self.project_data.get("taxonomy", [])
        if clean_target not in taxonomy or clean_parent not in taxonomy:
            return False

        parent_map = self.get_blink_context_roi_parents()
        if parent_map.get(clean_target) == clean_parent:
            return False

        parent_map[clean_target] = clean_parent
        self.project_data["blink_context_roi_parents"] = parent_map
        self._mark_sqlite_project_dirty()
        if save:
            self.save_project()
        return True

    def clear_blink_context_parent(self, target_part, save=True):
        clean_target = str(target_part).strip()
        if not clean_target:
            return False

        parent_map = self.get_blink_context_roi_parents()
        if clean_target not in parent_map:
            return False

        del parent_map[clean_target]
        self.project_data["blink_context_roi_parents"] = parent_map
        self._mark_sqlite_project_dirty()
        if save:
            self.save_project()
        return True

    def get_parent_box_aspect_ratios(self):
        clean_map = self._sanitize_parent_box_aspect_ratios(
            self.project_data.get("parent_box_aspect_ratios", DEFAULT_PARENT_BOX_ASPECT_RATIOS)
        )
        self.project_data["parent_box_aspect_ratios"] = clean_map
        return dict(clean_map)

    def set_parent_box_aspect_ratio(self, part_name, aspect_ratio, save=True):
        clean_part = str(part_name or "").strip()
        if not clean_part or clean_part not in self.project_data.get("taxonomy", []):
            return False
        try:
            clean_ratio = float(aspect_ratio)
        except Exception:
            return False
        if clean_ratio <= 0:
            return False

        ratios = self.get_parent_box_aspect_ratios()
        ratios[clean_part] = clean_ratio
        self.project_data["parent_box_aspect_ratios"] = self._sanitize_parent_box_aspect_ratios(ratios)
        self._sync_active_model_profile_from_project_fields()
        self._mark_sqlite_project_dirty()
        if save:
            self.save_project()
        return True

    def get_shrink_loose_boxes(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("shrink_loose_boxes", {})

    def update_shrink_loose_box(self, image_path, part_name, box, save=True):
        clean_part = str(part_name or "").strip()
        clean_box = None
        if isinstance(box, (list, tuple)) and len(box) == 4:
            try:
                clean_box = [float(value) for value in box]
            except Exception:
                clean_box = None
        if not clean_part or not clean_box or clean_box[2] <= clean_box[0] or clean_box[3] <= clean_box[1]:
            return False
        if image_path not in self.project_data["labels"]:
            self.project_data["labels"][image_path] = self._default_label_entry()
        entry = self.project_data["labels"][image_path]
        entry.setdefault("shrink_loose_boxes", {})[clean_part] = clean_box
        self._append_label_journal_entry(image_path, "update_shrink_loose_box")
        self._mark_sqlite_image_dirty(image_path)
        if save:
            self.save_project()
        return True

    def update_label(self, image_path, part_name, points, description_text=None, box=None, auto_box=None, save=True):
        """
        Updates polygon points AND potentially the associated text description.
        Optionally stores the source bounding box [x1,y1,x2,y2].
        """
        # Auto-Repair: Ensure entry exists
        if image_path not in self.project_data["labels"]:
             self.project_data["labels"][image_path] = self._default_label_entry()
        
        # Sanitize Points: Ensure all are list of floats, no NaNs
        clean_points = []
        if points:
            try:
                for pt in points:
                    if len(pt) >= 2:
                        clean_points.append([float(pt[0]), float(pt[1])])
            except Exception as e:
                print(f"Error sanitizing points for {part_name}: {e}")
                return

        self.project_data["labels"][image_path]["parts"][part_name] = clean_points
        self.project_data["labels"][image_path]["status"] = "labeled"
        
        if box:
            try:
                if len(box) == 4:
                    clean_box = [float(v) for v in box]
                    if "boxes" not in self.project_data["labels"][image_path]:
                            self.project_data["labels"][image_path]["boxes"] = {}
                    self.project_data["labels"][image_path]["boxes"][part_name] = clean_box
                    
                    # LOGIC FIX: Manual override should clear old Auto Box
                    # If user manually draws a box, the old auto prediction is obsolete.
                    if "auto_boxes" in self.project_data["labels"][image_path]:
                        if part_name in self.project_data["labels"][image_path]["auto_boxes"]:
                            del self.project_data["labels"][image_path]["auto_boxes"][part_name]
                    if "auto_box_meta" in self.project_data["labels"][image_path]:
                        self.project_data["labels"][image_path]["auto_box_meta"].pop(part_name, None)
            except Exception as e:
                print(f"Error sanitizing box: {e}")
        
        if auto_box:
            try:
                if len(auto_box) == 4:
                    clean_auto_box = [float(v) for v in auto_box]
                    if "auto_boxes" not in self.project_data["labels"][image_path]:
                            self.project_data["labels"][image_path]["auto_boxes"] = {}
                    self.project_data["labels"][image_path]["auto_boxes"][part_name] = clean_auto_box
            except Exception as e:
                print(f"Error sanitizing auto_box: {e}")

        entry = self.project_data["labels"][image_path]
        if description_text:
            entry["descriptions"][part_name] = description_text
        elif not auto_box and entry.get("descriptions", {}).get(part_name) == "Auto-Annotated":
            del entry["descriptions"][part_name]
            
        self._append_label_journal_entry(image_path, "update_label")
        self._mark_sqlite_image_dirty(image_path)
        if save:
            self.save_project()

    def update_auto_box(self, image_path, part_name, box, description_text=None, source_meta=None, save=True):
        clean_part = str(part_name or "").strip()
        clean_box = None
        if isinstance(box, (list, tuple)) and len(box) == 4:
            try:
                clean_box = [float(value) for value in box]
            except Exception:
                clean_box = None
        if not clean_part or not clean_box or clean_box[2] <= clean_box[0] or clean_box[3] <= clean_box[1]:
            return False
        if image_path not in self.project_data["labels"]:
            self.project_data["labels"][image_path] = self._default_label_entry()
        entry = self.project_data["labels"][image_path]
        entry.setdefault("auto_boxes", {})[clean_part] = clean_box
        if description_text:
            entry.setdefault("descriptions", {})[clean_part] = str(description_text)
        if source_meta:
            clean_meta = dict(source_meta)
            clean_meta.setdefault("source", AUTO_BOX_SOURCE_MODEL)
            clean_meta.setdefault("review_status", AUTO_BOX_REVIEW_DRAFT)
            entry.setdefault("auto_box_meta", {})[clean_part] = clean_meta
        self._append_label_journal_entry(image_path, "update_auto_box")
        self._mark_sqlite_image_dirty(image_path)
        if save:
            self.save_project()
        return True

    def set_auto_box_review_status(self, image_path, part_name, review_status, save=True):
        clean_part = str(part_name or "").strip()
        clean_status = str(review_status or "").strip() or "draft"
        if not clean_part or image_path not in self.project_data["labels"]:
            return False
        entry = self.project_data["labels"][image_path]
        if clean_part not in entry.get("auto_boxes", {}):
            return False
        meta = entry.setdefault("auto_box_meta", {}).setdefault(clean_part, {})
        meta["review_status"] = clean_status
        self._append_label_journal_entry(image_path, "set_auto_box_review_status")
        self._mark_sqlite_image_dirty(image_path)
        if save:
            self.save_project()
        return True

    def summarize_image_ai_drafts(self, image_path):
        if image_path not in self.project_data["labels"]:
            return {
                "reviewable_polygon_parts": [],
                "box_only_parts": [],
            }
        entry = self.project_data["labels"][image_path]
        parts = entry.get("parts", {}) if isinstance(entry.get("parts", {}), dict) else {}
        auto_boxes = entry.get("auto_boxes", {}) if isinstance(entry.get("auto_boxes", {}), dict) else {}
        descriptions = entry.get("descriptions", {}) if isinstance(entry.get("descriptions", {}), dict) else {}
        reviewable = []
        box_only = []
        for part_name, desc in descriptions.items():
            if desc != "Auto-Annotated":
                continue
            has_polygon = bool(parts.get(part_name))
            has_auto_box = part_name in auto_boxes
            if has_polygon:
                reviewable.append(part_name)
            elif has_auto_box:
                box_only.append(part_name)
        return {
            "reviewable_polygon_parts": reviewable,
            "box_only_parts": box_only,
        }

    def summarize_ai_drafts_for_images(self, image_paths):
        summaries = []
        total_reviewable = 0
        total_box_only = 0
        for image_path in image_paths or []:
            if not image_path:
                continue
            summary = self.summarize_image_ai_drafts(image_path)
            reviewable_count = len(summary.get("reviewable_polygon_parts", []) or [])
            box_only_count = len(summary.get("box_only_parts", []) or [])
            if reviewable_count or box_only_count:
                item = dict(summary)
                item["image_path"] = image_path
                item["reviewable_count"] = reviewable_count
                item["box_only_count"] = box_only_count
                summaries.append(item)
                total_reviewable += reviewable_count
                total_box_only += box_only_count
        return {
            "images_with_drafts": summaries,
            "image_count": len(summaries),
            "reviewable_polygon_count": total_reviewable,
            "box_only_count": total_box_only,
        }

    def verify_ai_drafts_for_images(self, image_paths):
        accepted_count = 0
        accepted_images = 0
        for image_path in image_paths or []:
            if not image_path:
                continue
            count = self.verify_image_labels(image_path, save=False)
            if count:
                accepted_count += count
                accepted_images += 1
        if accepted_count:
            self._mark_sqlite_images_dirty(image_paths)
            self.save_project()
        return {
            "accepted_count": accepted_count,
            "accepted_images": accepted_images,
        }

    def remove_auto_box(self, image_path, part_name, save=True):
        clean_part = str(part_name or "").strip()
        if not clean_part or image_path not in self.project_data["labels"]:
            return False
        entry = self.project_data["labels"][image_path]
        removed = False
        if clean_part in entry.get("auto_boxes", {}):
            del entry["auto_boxes"][clean_part]
            removed = True
        if clean_part in entry.get("auto_box_meta", {}):
            del entry["auto_box_meta"][clean_part]
            removed = True
        if removed:
            self._append_label_journal_entry(image_path, "remove_auto_box")
            self._mark_sqlite_image_dirty(image_path)
        if save and removed:
            self.save_project()
        return removed
    
    def get_boxes(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("boxes", {})

    def get_auto_boxes(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("auto_boxes", {})

    def get_auto_box_meta(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("auto_box_meta", {})

    def split_auto_boxes_by_source(self, image_path):
        entry = self.project_data["labels"].get(image_path, {})
        auto_boxes = entry.get("auto_boxes", {}) if isinstance(entry.get("auto_boxes", {}), dict) else {}
        meta = entry.get("auto_box_meta", {}) if isinstance(entry.get("auto_box_meta", {}), dict) else {}
        model_boxes = {}
        vlm_boxes = {}
        for part_name, box in auto_boxes.items():
            part_meta = meta.get(part_name, {}) if isinstance(meta.get(part_name), dict) else {}
            if part_meta.get("source") == AUTO_BOX_SOURCE_VLM:
                vlm_boxes[part_name] = box
            else:
                model_boxes[part_name] = box
        return model_boxes, vlm_boxes

    def get_locator_scope(self):
        locator_scope = self.project_data.get("locator_scope", [])
        taxonomy = self.project_data.get("taxonomy", [])
        clean_scope = sanitize_locator_scope(locator_scope, taxonomy, fallback=DEFAULT_LOCATOR_SCOPE)
        self.project_data["locator_scope"] = clean_scope
        return clean_scope

    def set_locator_scope(self, locator_scope, save=True):
        clean_scope = sanitize_locator_scope(locator_scope, self.project_data.get("taxonomy", []), fallback=DEFAULT_LOCATOR_SCOPE)
        self.project_data["locator_scope"] = clean_scope
        self._sync_active_model_profile_from_project_fields()
        self._mark_sqlite_project_dirty()
        if save:
            self.save_project()
        return clean_scope

    def update_trajectory(self, image_path, part_name, trajectory, parent_context=None, save=True):
        """
        Stores the blink shrink trajectory data for a specific part.
        This is the core training material for the Stage 3 Expert Models.
        """
        if image_path not in self.project_data["labels"]:
             self.project_data["labels"][image_path] = self._default_label_entry()
        
        if "trajectories" not in self.project_data["labels"][image_path]:
            self.project_data["labels"][image_path]["trajectories"] = {}

        clean_trajectory = []
        total_steps = len(trajectory) if trajectory else 0
        for idx, frame in enumerate(trajectory or []):
            if not isinstance(frame, dict):
                continue

            box = frame.get("box")
            if not box or len(box) != 4:
                continue

            try:
                clean_box = [float(v) for v in box]
            except Exception:
                continue

            x1, y1, x2, y2 = clean_box
            if x2 <= x1 or y2 <= y1:
                continue

            clean_frame = {
                "step": int(frame.get("step", idx)),
                "alpha": float(frame.get("alpha", idx / max(1, total_steps - 1))),
                "box": clean_box,
                "is_golden": bool(frame.get("is_golden", idx == total_steps - 1)),
                "coord_frame": str(frame.get("coord_frame", "global")),
            }

            target_box = frame.get("target_box")
            if target_box and isinstance(target_box, (list, tuple)) and len(target_box) == 4:
                try:
                    clean_frame["target_box"] = [float(v) for v in target_box]
                except Exception:
                    pass

            clean_trajectory.append(clean_frame)

        clean_parent_context = None
        if isinstance(parent_context, dict):
            raw_parent_box = parent_context.get("parent_box")
            raw_parent_part = parent_context.get("parent_part")
            raw_source = parent_context.get("source")
            if isinstance(raw_parent_box, (list, tuple)) and len(raw_parent_box) == 4:
                try:
                    clean_parent_box = [float(v) for v in raw_parent_box]
                    px1, py1, px2, py2 = clean_parent_box
                    if px2 > px1 and py2 > py1:
                        clean_parent_context = {"parent_box": clean_parent_box}
                        if isinstance(raw_parent_part, str) and raw_parent_part.strip():
                            clean_parent_context["parent_part"] = raw_parent_part.strip()
                        if isinstance(raw_source, str) and raw_source.strip():
                            clean_parent_context["source"] = raw_source.strip()
                except Exception:
                    clean_parent_context = None

        trajectory_payload = {"frames": clean_trajectory}
        if clean_parent_context:
            trajectory_payload["parent_context"] = clean_parent_context

        self.project_data["labels"][image_path]["trajectories"][part_name] = trajectory_payload
        self._append_label_journal_entry(image_path, "update_trajectory")
        self._mark_sqlite_image_dirty(image_path)
        if save:
            self.save_project()
        
    def get_trajectories(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("trajectories", {})

    def summarize_blink_trajectory_datasets(self):
        summaries = {}
        for image_path, entry in self.project_data.get("labels", {}).items():
            if not isinstance(entry, dict):
                continue
            trajectories = entry.get("trajectories", {})
            if not isinstance(trajectories, dict):
                continue
            for child_part, payload in trajectories.items():
                if not isinstance(payload, dict):
                    continue
                frames = payload.get("frames", [])
                if not isinstance(frames, list) or not frames:
                    continue
                parent_context = payload.get("parent_context", {})
                if not isinstance(parent_context, dict):
                    parent_context = {}
                parent_part = str(parent_context.get("parent_part") or "").strip() or "Unknown parent"
                child_part = str(child_part or "").strip() or "Unknown child"
                key = (parent_part, child_part)
                item = summaries.setdefault(
                    key,
                    {
                        "parent_part": parent_part,
                        "child_part": child_part,
                        "image_count": 0,
                        "frame_count": 0,
                        "sources": set(),
                        "images": [],
                    },
                )
                item["image_count"] += 1
                item["frame_count"] += len(frames)
                source = str(parent_context.get("source") or "").strip() or "unknown"
                item["sources"].add(source)
                item["images"].append(
                    {
                        "image_path": image_path,
                        "frame_count": len(frames),
                        "source": source,
                        "parent_box": parent_context.get("parent_box"),
                    }
                )
        result = []
        for item in summaries.values():
            clean = dict(item)
            clean["sources"] = sorted(clean.get("sources", []))
            clean["images"] = sorted(clean.get("images", []), key=lambda value: str(value.get("image_path", "")))
            result.append(clean)
        return sorted(result, key=lambda value: (value.get("parent_part", ""), value.get("child_part", "")))

    def delete_blink_trajectory_dataset(self, parent_part, child_part, save=True):
        clean_parent = str(parent_part or "").strip()
        clean_child = str(child_part or "").strip()
        if not clean_child:
            return 0
        removed = 0
        changed_images = []
        for image_path, entry in self.project_data.get("labels", {}).items():
            if not isinstance(entry, dict):
                continue
            trajectories = entry.get("trajectories", {})
            if not isinstance(trajectories, dict) or clean_child not in trajectories:
                continue
            payload = trajectories.get(clean_child)
            parent_context = payload.get("parent_context", {}) if isinstance(payload, dict) else {}
            if not isinstance(parent_context, dict):
                parent_context = {}
            stored_parent = str(parent_context.get("parent_part") or "").strip() or "Unknown parent"
            if clean_parent and stored_parent != clean_parent:
                continue
            del trajectories[clean_child]
            removed += 1
            changed_images.append(image_path)
            if not trajectories:
                entry.pop("trajectories", None)
        if removed:
            for image_path in changed_images:
                self._append_label_journal_entry(image_path, "delete_blink_trajectory_dataset")
            self._mark_sqlite_images_dirty(changed_images)
        if removed and save:
            self.save_project()
        return removed

    def delete_label(self, image_path, part_name, save=True):
        """
        Completely removes a label and all its associated data (boxes, descriptions, etc.)
        """
        if image_path in self.project_data["labels"]:
            entry = self.project_data["labels"][image_path]
            
            # Remove Polygon
            if "parts" in entry and part_name in entry["parts"]:
                del entry["parts"][part_name]
            
            # Remove Description
            if "descriptions" in entry and part_name in entry["descriptions"]:
                del entry["descriptions"][part_name]
            if "description_sources" in entry and part_name in entry["description_sources"]:
                del entry["description_sources"][part_name]
                
            # Remove Manual Box
            if "boxes" in entry and part_name in entry["boxes"]:
                del entry["boxes"][part_name]
                
            # Remove Auto Box
            if "auto_boxes" in entry and part_name in entry["auto_boxes"]:
                del entry["auto_boxes"][part_name]

            if "auto_box_meta" in entry and part_name in entry["auto_box_meta"]:
                del entry["auto_box_meta"][part_name]

            # Remove Blink Trajectory
            if "trajectories" in entry and part_name in entry["trajectories"]:
                del entry["trajectories"][part_name]

            # Remove Blink loose shrink box
            if "shrink_loose_boxes" in entry and part_name in entry["shrink_loose_boxes"]:
                del entry["shrink_loose_boxes"][part_name]
            
            self._append_label_journal_entry(image_path, "delete_label")
            self._mark_sqlite_image_dirty(image_path)
            if save:
                self.save_project()

    def set_genus(self, image_path, genus, save=True):
        self.set_taxon(image_path, genus, save=save)

    def set_taxon(self, image_path, taxon, taxon_rank=None, taxon_metadata=None, save=True):
        if image_path in self.project_data["labels"]:
            entry = self._normalize_label_taxon_fields(self.project_data["labels"][image_path])
            clean_taxon = str(taxon or "Unknown").strip() or "Unknown"
            entry["taxon"] = clean_taxon
            entry["genus"] = clean_taxon
            if taxon_rank is not None:
                entry["taxon_rank"] = str(taxon_rank or "").strip()
            if isinstance(taxon_metadata, dict):
                entry["taxon_metadata"] = dict(taxon_metadata)
            self._append_label_journal_entry(image_path, "set_taxon")
            self._mark_sqlite_image_dirty(image_path)
            if save:
                self.save_project()

    def get_labels(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("parts", {})

    def get_genus(self, image_path):
        return self.get_taxon(image_path)

    def get_taxon(self, image_path):
        return self._label_taxon_payload(self.project_data["labels"].get(image_path, {})).get("taxon", "Unknown")

    def list_taxa(self):
        taxa = {"Unknown"}
        for label_data in self.project_data.get("labels", {}).values():
            taxa.add(self._label_taxon_payload(label_data).get("taxon", "Unknown"))
        return sorted(taxa)

    def add_taxonomy_part(self, part_name):
        """Adds a new part to the taxonomy if it doesn't exist."""
        clean_name = str(part_name).strip()
        if is_safe_part_name(clean_name) and clean_name not in self.project_data["taxonomy"]:
            self.project_data["taxonomy"].append(clean_name)
            self._sync_active_model_profile_from_project_fields()
            self._mark_sqlite_project_dirty()
            self.save_project() # FIX: Save immediately
            return True
        return False

    def _rename_label_part_key(self, entry, old_part, new_part):
        if not isinstance(entry, dict):
            return
        for key in (
            "parts",
            "boxes",
            "auto_boxes",
            "auto_box_meta",
            "descriptions",
            "description_sources",
            "shrink_loose_boxes",
            "trajectories",
        ):
            bucket = entry.get(key)
            if isinstance(bucket, dict) and old_part in bucket:
                bucket[new_part] = bucket.pop(old_part)
        trajectories = entry.get("trajectories", {})
        if isinstance(trajectories, dict):
            for payload in trajectories.values():
                if not isinstance(payload, dict):
                    continue
                parent_context = payload.get("parent_context", {})
                if isinstance(parent_context, dict) and parent_context.get("parent_part") == old_part:
                    parent_context["parent_part"] = new_part

    def _rename_part_in_routes(self, old_part, new_part):
        raw_manifest = self.project_data.get("cascade_routes", {})
        manifest = raw_manifest if isinstance(raw_manifest, dict) else {}
        updated_routes = []
        raw_routes = manifest.get("routes", [])
        if not isinstance(raw_routes, list):
            raw_routes = []
        for route in raw_routes:
            if not isinstance(route, dict):
                continue
            route_payload = dict(route)
            if route_payload.get("parent") == old_part:
                route_payload["parent"] = new_part
            if route_payload.get("child") == old_part:
                route_payload["child"] = new_part
            if route_payload.get("expert_part") == old_part:
                route_payload["expert_part"] = new_part
                filename = route_payload.get("expert_filename")
                if filename:
                    route_payload["expert_id"] = f"{new_part}/{filename}"
            appointed = route_payload.get("appointed_expert")
            if isinstance(appointed, dict) and appointed.get("expert_part") == old_part:
                appointed = dict(appointed)
                appointed["expert_part"] = new_part
                filename = appointed.get("expert_filename")
                if filename:
                    appointed["expert_id"] = f"{new_part}/{filename}"
                route_payload["appointed_expert"] = appointed
            candidates = []
            for candidate in route_payload.get("expert_candidates", []) or []:
                if not isinstance(candidate, dict):
                    continue
                candidate_payload = dict(candidate)
                if candidate_payload.get("expert_part") == old_part:
                    candidate_payload["expert_part"] = new_part
                    filename = candidate_payload.get("expert_filename")
                    if filename:
                        candidate_payload["expert_id"] = f"{new_part}/{filename}"
                candidates.append(candidate_payload)
            route_payload["expert_candidates"] = candidates
            updated_routes.append(route_payload)
        self.project_data["cascade_routes"] = self._sanitize_cascade_routes(
            {
                "version": manifest.get("version", PROJECT_ROUTE_MANIFEST_VERSION),
                "routes": updated_routes,
            }
        )

    def rename_taxonomy_part(self, old_part_name, new_part_name, save=True):
        """Renames a taxonomy part and migrates labels, drafts, boxes, and routes."""
        old_part = str(old_part_name or "").strip()
        new_part = str(new_part_name or "").strip()
        taxonomy = list(self.project_data.get("taxonomy", []))
        if (
            not old_part
            or not new_part
            or old_part == new_part
            or old_part not in taxonomy
            or new_part in taxonomy
            or not is_safe_part_name(new_part)
        ):
            return False

        raw_parent_map = self.project_data.get("blink_context_roi_parents", {})
        raw_parent_map = dict(raw_parent_map) if isinstance(raw_parent_map, dict) else {}

        self.project_data["taxonomy"] = [new_part if part == old_part else part for part in taxonomy]
        self.project_data["locator_scope"] = [
            new_part if part == old_part else part
            for part in self.project_data.get("locator_scope", [])
        ]

        ratios = dict(self.project_data.get("parent_box_aspect_ratios", {}))
        if old_part in ratios and new_part not in ratios:
            ratios[new_part] = ratios.pop(old_part)
        else:
            ratios.pop(old_part, None)
        self.project_data["parent_box_aspect_ratios"] = self._sanitize_parent_box_aspect_ratios(ratios)

        settings = dict(self.project_data.get("vlm_preannotation", {}))
        settings["target_parts"] = [
            new_part if part == old_part else part
            for part in settings.get("target_parts", [])
        ]
        self.project_data["vlm_preannotation"] = self._sanitize_vlm_preannotation_settings(settings)

        renamed_parent_map = {}
        for target_part, parent_part in raw_parent_map.items():
            target = new_part if target_part == old_part else target_part
            parent = new_part if parent_part == old_part else parent_part
            if target != parent:
                renamed_parent_map[target] = parent
        self.project_data["blink_context_roi_parents"] = self._sanitize_blink_context_roi_parents(renamed_parent_map)

        for entry in self.project_data.get("labels", {}).values():
            self._rename_label_part_key(entry, old_part, new_part)

        self._rename_part_in_routes(old_part, new_part)
        self._sync_active_model_profile_from_project_fields()
        self._mark_sqlite_project_dirty()
        self._mark_sqlite_images_dirty(self.project_data.get("labels", {}).keys())

        if save:
            self.save_project()
        return True

    def remove_taxonomy_part(self, part_name):
        """Removes a part from taxonomy and deletes all associated labels."""
        if part_name in self.project_data["taxonomy"]:
            self.project_data["taxonomy"].remove(part_name)
            self.project_data["locator_scope"] = sanitize_locator_scope(
                self.project_data.get("locator_scope", []),
                self.project_data["taxonomy"],
                fallback=DEFAULT_LOCATOR_SCOPE,
            )
            
            # Remove labels for this part in all images
            for img_path in self.project_data["labels"]:
                self.delete_label(img_path, part_name, save=False)

            parent_map = self.get_blink_context_roi_parents()
            self.project_data["blink_context_roi_parents"] = {
                target_part: parent_part
                for target_part, parent_part in parent_map.items()
                if target_part != part_name and parent_part != part_name
            }
            self.project_data["cascade_routes"] = self._sanitize_cascade_routes(
                {
                    "version": self.project_data.get("cascade_routes", {}).get("version", PROJECT_ROUTE_MANIFEST_VERSION),
                    "routes": [
                        route
                        for route in self.project_data.get("cascade_routes", {}).get("routes", [])
                        if route.get("parent") != part_name
                        and route.get("child") != part_name
                        and route.get("expert_part") != part_name
                    ],
                }
            )
            self._sync_active_model_profile_from_project_fields()
            self._mark_sqlite_project_dirty()
            self._mark_sqlite_images_dirty(self.project_data.get("labels", {}).keys())
            
            self.save_project() # FIX: Save immediately
            return True
        return False

    def remove_auto_labels_for_images(self, image_paths, save=True):
        """Removes labels marked as 'Auto-Annotated' for the selected images."""
        removed_count = 0
        candidate_paths = list(image_paths or [])
        if not candidate_paths:
            return 0
        path_identities = {self._path_identity(path) for path in candidate_paths if path}
        path_identities.discard("")
        label_keys = [
            img_path
            for img_path in list(self.project_data.get("labels", {}).keys())
            if self._path_identity(img_path) in path_identities
        ]
        for img_path in label_keys:
            parts_to_remove = []
            labels = self.project_data["labels"][img_path]
            
            if "descriptions" in labels:
                for part, desc in labels["descriptions"].items():
                    if desc == "Auto-Annotated":
                        parts_to_remove.append(part)
            
            for part in parts_to_remove:
                if part in labels["parts"]:
                    del labels["parts"][part]
                del labels["descriptions"][part]
                if "description_sources" in labels and part in labels["description_sources"]:
                    del labels["description_sources"][part]
                if "auto_boxes" in labels and part in labels["auto_boxes"]:
                    del labels["auto_boxes"][part]
                if "auto_box_meta" in labels and part in labels["auto_box_meta"]:
                    del labels["auto_box_meta"][part]
                removed_count += 1
                
            if not labels["parts"]:
                labels["status"] = "unlabeled"
            if parts_to_remove:
                self._append_label_journal_entry(img_path, "remove_auto_labels_for_images")
                self._mark_sqlite_image_dirty(img_path)
                
        if save:
            self.save_project()
        return removed_count

    def remove_auto_labels(self, save=True):
        """Removes all labels marked as 'Auto-Annotated'."""
        return self.remove_auto_labels_for_images(self.project_data.get("labels", {}).keys(), save=save)

    def verify_image_labels(self, image_path, save=True):
        """Removes 'Auto-Annotated' only from labels with a saved polygon."""
        if image_path not in self.project_data["labels"]: return 0
        
        labels = self.project_data["labels"][image_path]
        parts = labels.get("parts", {}) if isinstance(labels.get("parts", {}), dict) else {}
        count = 0
        if "descriptions" in labels:
            for part in list(labels["descriptions"].keys()):
                if labels["descriptions"][part] == "Auto-Annotated" and parts.get(part):
                    del labels["descriptions"][part]
                    self.set_auto_box_review_status(image_path, part, "confirmed", save=False)
                    count += 1
        
        if count > 0:
            self._append_label_journal_entry(image_path, "verify_image_labels")
            self._mark_sqlite_image_dirty(image_path)
        if count > 0 and save:
            self.save_project()
        return count

    def export_coco(self, output_dir, progress_callback=None):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        images_dir = os.path.join(output_dir, "images")
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
            
        coco_data = {
            "info": {"description": self.project_data["name"], "year": 2024, "version": "1.0"},
            "licenses": [],
            "images": [],
            "annotations": [],
            "categories": []
        }
        
        cat_map = {}
        supercategory = self._category_supercategory()
        for idx, part in enumerate(self.project_data["taxonomy"], 1):
            coco_data["categories"].append({"id": idx, "name": part, "supercategory": supercategory})
            cat_map[part] = idx
            
        ann_id = 1
        img_id = 1
        count = 0
        
        image_paths = list(self.project_data["images"])
        total = len(image_paths)

        for index, img_path in enumerate(image_paths, start=1):
            if progress_callback:
                progress_callback(index - 1, total, os.path.basename(img_path))
            if not os.path.exists(img_path): continue
            fname = os.path.basename(img_path)
            shutil.copy(img_path, os.path.join(images_dir, fname))
            
            try:
                with Image.open(img_path) as pim:
                    w, h = pim.size
            except:
                w, h = 0, 0
                
            coco_data["images"].append({"id": img_id, "file_name": fname, "width": w, "height": h})
            
            parts = self.get_labels(img_path)
            manual_boxes = self.get_boxes(img_path)

            for part_name, points in parts.items():
                if part_name not in cat_map: continue
                flat_points = [coord for pt in points for coord in pt]
                
                # Priority: Use manual box if available, else derive from points
                if part_name in manual_boxes:
                    bx1, by1, bx2, by2 = manual_boxes[part_name]
                    bbox = [bx1, by1, bx2 - bx1, by2 - by1] # [x, y, w, h]
                else:
                    xs, ys = [p[0] for p in points], [p[1] for p in points]
                    if not xs or not ys: continue
                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)
                    bbox = [min_x, min_y, max_x - min_x, max_y - min_y] 
                
                coco_data["annotations"].append({
                    "id": ann_id,
                    "image_id": img_id,
                    "category_id": cat_map[part_name],
                    "segmentation": [flat_points],
                    "area": bbox[2] * bbox[3], 
                    "bbox": bbox,
                    "iscrowd": 0
                })
                ann_id += 1
            img_id += 1
            count += 1

        if progress_callback:
            progress_callback(total, total, "annotations.json")
            
        with open(os.path.join(output_dir, "annotations.json"), 'w', encoding='utf-8') as f:
            json.dump(coco_data, f, indent=4, ensure_ascii=False)
        return count

    def export_yolo(self, output_dir, progress_callback=None):
        """
        Export in YOLOv8-segmentation format.
        Structure: <class_id> <x1_norm> <y1_norm> ... <xn_norm> <yn_norm>
        Note: YOLO-seg uses the polygon points directly, but we'll ensure 
        the data reflects the latest manual/auto labels.
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        images_dir = os.path.join(output_dir, "images")
        labels_dir = os.path.join(output_dir, "labels")
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(labels_dir, exist_ok=True)
        
        cat_map = {name: i for i, name in enumerate(self.project_data["taxonomy"])}
        count = 0
        
        image_paths = list(self.project_data["images"])
        total = len(image_paths)

        for index, img_path in enumerate(image_paths, start=1):
            if progress_callback:
                progress_callback(index - 1, total, os.path.basename(img_path))
            if not os.path.exists(img_path): continue
            
            # Copy Image
            fname = os.path.basename(img_path)
            shutil.copy(img_path, os.path.join(images_dir, fname))
            
            # Create Label File
            label_fname = os.path.splitext(fname)[0] + ".txt"
            
            try:
                with Image.open(img_path) as pim:
                    w, h = pim.size
            except: continue
            
            parts = self.get_labels(img_path)
            if not parts: continue
            
            with open(os.path.join(labels_dir, label_fname), 'w') as f:
                for part_name, points in parts.items():
                    if part_name not in cat_map: continue
                    class_id = cat_map[part_name]
                    
                    # YOLO-seg needs normalized coordinates [0, 1]
                    norm_points = []
                    for pt in points:
                        nx = pt[0] / w
                        ny = pt[1] / h
                        norm_points.append(f"{nx:.6f} {ny:.6f}")
                    
                    line = f"{class_id} " + " ".join(norm_points) + "\n"
                    f.write(line)
            count += 1

        if progress_callback:
            progress_callback(total, total, "dataset.yaml")
            
        # Create dataset.yaml
        yaml_content = (
            f"path: {json.dumps(os.path.abspath(output_dir), ensure_ascii=False)}\n"
            "train: images\n"
            "val: images\n\n"
            "names:\n"
        )
        for i, name in enumerate(self.project_data["taxonomy"]):
            yaml_content += f"  {i}: {json.dumps(str(name), ensure_ascii=False)}\n"
            
        with open(os.path.join(output_dir, "dataset.yaml"), 'w', encoding='utf-8') as f:
            f.write(yaml_content)
            
        return count

    def export_multimodal_dataset(self, output_dir, crop_size=512, global_size=1024, progress_callback=None):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        crops_dir = os.path.join(output_dir, "crops")
        global_dir = os.path.join(output_dir, "images_global")
        os.makedirs(crops_dir, exist_ok=True)
        os.makedirs(global_dir, exist_ok=True)
        
        jsonl_path = os.path.join(output_dir, "multimodal_dataset.jsonl")
        
        count = 0
        processed_globals = set() # Avoid re-processing same global image multiple times
        label_items = [
            (img_path, data)
            for img_path, data in self.project_data["labels"].items()
            if isinstance(data, dict)
        ]
        total = len(label_items)
        
        with open(jsonl_path, 'w', encoding='utf-8') as f:
            for index, (img_path, data) in enumerate(label_items, start=1):
                if progress_callback:
                    progress_callback(index - 1, total, os.path.basename(img_path))
                if not os.path.exists(img_path): continue
                try:
                    img = Image.open(img_path).convert('RGB')
                except: continue
                
                # 1. Process Global Image (Once per image file)
                # Resize keeping aspect ratio so max dim is global_size
                w_orig, h_orig = img.size
                scale_global = min(global_size / w_orig, global_size / h_orig)
                # If original is smaller than global_size, keep original? Or upscale? 
                # Usually keep original if smaller, but let's stick to max-size constraint.
                if scale_global < 1.0:
                    new_w, new_h = int(w_orig * scale_global), int(h_orig * scale_global)
                    img_global = img.resize((new_w, new_h), Image.BILINEAR)
                else:
                    scale_global = 1.0
                    img_global = img
                
                global_filename = os.path.basename(img_path)
                global_rel_path = f"images_global/{global_filename}"
                
                # Only save global image if not already saved (optimization)
                # But need to check if file actually exists in target
                global_abs_path = os.path.join(global_dir, global_filename)
                if img_path not in processed_globals:
                    img_global.save(global_abs_path)
                    processed_globals.add(img_path)
                
                manual_boxes = data.get("boxes", {})

                for part, points in data["parts"].items():
                    if not points or not isinstance(points, list): continue
                    desc = data.get("descriptions", {}).get(part, "")
                    if not desc: continue 
                    
                    # 2. Determine Crop Center
                    # Priority: Use manual box for centering, else points
                    bx1, by1, bx2, by2 = 0, 0, 0, 0
                    has_manual_box = False
                    
                    if part in manual_boxes:
                        bx1, by1, bx2, by2 = manual_boxes[part]
                        center_x, center_y = (bx1 + bx2) / 2, (by1 + by2) / 2
                        has_manual_box = True
                    else:
                        xs, ys = [p[0] for p in points], [p[1] for p in points]
                        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
                        center_x, center_y = (min_x + max_x) / 2, (min_y + max_y) / 2
                        bx1, by1, bx2, by2 = min_x, min_y, max_x, max_y
                    
                    # 3. Create Local Crop
                    left = max(0, int(center_x - crop_size/2))
                    top = max(0, int(center_y - crop_size/2))
                    right = min(img.width, int(center_x + crop_size/2))
                    bottom = min(img.height, int(center_y + crop_size/2))
                    
                    crop = img.crop((left, top, right, bottom))
                    base_name = os.path.splitext(os.path.basename(img_path))[0]
                    crop_filename = f"{base_name}_{part}.jpg"
                    crop.save(os.path.join(crops_dir, crop_filename))
                    
                    # 4. Calculate Relative Segmentation & BBox
                    rel_points = [[p[0] - left, p[1] - top] for p in points]
                    
                    # Calculate BBox in GLOBAL coordinates (scaled)
                    bbox_global = [
                        bx1 * scale_global, 
                        by1 * scale_global, 
                        bx2 * scale_global, 
                        by2 * scale_global
                    ]

                    taxon_payload = self._label_taxon_payload(data)
                    entry = {
                        "schema_version": MULTIMODAL_SAMPLE_SCHEMA_VERSION,
                        "id": f"{base_name}_{part}",
                        "image_global": global_rel_path,
                        "image_local": f"crops/{crop_filename}",
                        "text": desc,
                        "label": part,
                        "taxon": taxon_payload["taxon"],
                        "taxon_rank": taxon_payload["taxon_rank"],
                        "taxon_metadata": taxon_payload["taxon_metadata"],
                        "genus": taxon_payload["genus"],
                        "annotation_status": "workbench_export",
                        "review_status": data.get("review_status", data.get("status", "unknown")),
                        "segmentation_local": rel_points, # Points relative to crop
                        "bbox_global": bbox_global,       # Box relative to global image
                        "bbox_original": [bx1, by1, bx2, by2], # Box in original resolution
                        "is_manual_box": has_manual_box,
                        "source_provenance": self.get_image_provenance(img_path),
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    count += 1

        if progress_callback:
            progress_callback(total, total, "multimodal_dataset.jsonl")
        return count
