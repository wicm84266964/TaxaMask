# pyright: reportMissingImports=false, reportGeneralTypeIssues=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false, reportIndexIssue=false

import json
import os
import shutil
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
    DEFAULT_MODEL_PROFILE_ID,
    clone_model_profiles,
    sanitize_model_profiles,
    set_active_model_profile as set_active_model_profile_id,
)

DEFAULT_CATEGORY_SUPERCATEGORY = "biological_structure"
MULTIMODAL_SAMPLE_SCHEMA_VERSION = "taxamask-multimodal-sample-v1"
MODEL_PROFILE_EXPORT_SUMMARY_SCHEMA_VERSION = "taxamask-model-profile-export-summary-v1"
DEFAULT_PARENT_BOX_ASPECT_RATIOS = {
    "Head": 1.0,
    "Mesosoma": 4.0 / 3.0,
    "Gaster": 4.0 / 3.0,
    "Whole body": 16.0 / 9.0,
}


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
            "vlm_preannotation": {
                "target_parts": [],
                "processing_scope": "current_image",
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
        self.known_relocated_roots = []

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
        processing_scope = str(settings.get("processing_scope", "current_image") or "current_image").strip()
        if processing_scope not in {"current_image", "all_images"}:
            processing_scope = "current_image"
        return {
            "target_parts": target_parts,
            "processing_scope": processing_scope,
        }

    def get_vlm_preannotation_settings(self):
        settings = self._sanitize_vlm_preannotation_settings(self.project_data.get("vlm_preannotation", {}))
        self.project_data["vlm_preannotation"] = settings
        return settings

    def set_vlm_preannotation_settings(self, settings, save=True):
        clean_settings = self._sanitize_vlm_preannotation_settings(settings)
        self.project_data["vlm_preannotation"] = clean_settings
        self._sync_active_model_profile_from_project_fields()
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

        if changed and save:
            self.save_project()
        return changed

    def create_project(self, name, save_dir, template_id=None):
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
        self.current_project_path = os.path.join(save_dir, f"{name}.json")
        self.save_project()

    def _to_relative(self, abs_path):
        """Convert absolute path to relative path based on project file location."""
        if not self.current_project_path:
            return abs_path
        try:
            project_dir = os.path.dirname(os.path.abspath(self.current_project_path))
            normalized_path = str(abs_path)
            if normalized_path and not os.path.isabs(normalized_path):
                normalized_path = self._to_absolute(normalized_path)
            return os.path.relpath(normalized_path, project_dir)
        except (ValueError, TypeError):
            return abs_path

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
        return os.path.normcase(os.path.normpath(os.path.abspath(str(absolute))))

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
            "vlm_preannotation": {
                "target_parts": [],
                "processing_scope": "current_image",
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
        self.known_relocated_roots = list(getattr(self, "known_relocated_roots", []))

    def load_project(self, path):
        self.clear() # Ensure clean state
        
        with open(path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        
        self.current_project_path = os.path.abspath(path)
        
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

        # Handle Images
        for img_rel in loaded_data.get("images", []):
            img_abs = self._to_absolute(img_rel)
            identity = self._path_identity(img_abs)
            if not identity or identity in image_keys_seen:
                continue
            image_keys_seen.add(identity)
            self.project_data["images"].append(img_abs)
            
        # Handle Labels
        for img_rel, label_data in loaded_data.get("labels", {}).items():
            img_abs = self._to_absolute(img_rel)
            project_key = self._registered_image_key_for_path(img_abs) or img_abs
            existing = self.project_data["labels"].get(project_key)
            if existing:
                self.project_data["labels"][project_key] = self._merge_loaded_label_entry(existing, label_data)
            else:
                self.project_data["labels"][project_key] = self._normalize_label_taxon_fields(label_data)
            
        # Handle Scales
        for img_rel, scale_val in loaded_data.get("scales", {}).items():
            img_abs = self._to_absolute(img_rel)
            project_key = self._registered_image_key_for_path(img_abs) or img_abs
            self.project_data["scales"][project_key] = scale_val

        # Handle per-image provenance for agent-imported PDF candidates.
        self.project_data["image_provenance"] = {}
        for img_rel, provenance in loaded_data.get("image_provenance", {}).items():
            img_abs = self._to_absolute(img_rel)
            if isinstance(provenance, dict):
                project_key = self._registered_image_key_for_path(img_abs) or img_abs
                existing = self.project_data["image_provenance"].get(project_key, {})
                if isinstance(existing, dict):
                    merged = dict(existing)
                    merged.update(provenance)
                    self.project_data["image_provenance"][project_key] = merged
                else:
                    self.project_data["image_provenance"][project_key] = dict(provenance)

    def save_project(self):
        if self.current_project_path:
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
            }
            
            for img_abs in self.project_data["images"]:
                data_to_save["images"].append(self._to_relative(img_abs))
                
            for img_abs, label_data in self.project_data["labels"].items():
                rel_path = self._to_relative(img_abs)
                data_to_save["labels"][rel_path] = label_data
                
            for img_abs, scale_val in self.project_data.get("scales", {}).items():
                rel_path = self._to_relative(img_abs)
                data_to_save["scales"][rel_path] = scale_val

            for img_abs, provenance in self.project_data.get("image_provenance", {}).items():
                rel_path = self._to_relative(img_abs)
                data_to_save["image_provenance"][rel_path] = provenance

            with open(self.current_project_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)

    def add_images(self, image_paths):
        for img in image_paths:
            abs_img = os.path.abspath(img)
            if abs_img not in self.project_data["images"]:
                self.project_data["images"].append(abs_img)
                self.project_data["labels"][abs_img] = self._default_label_entry()
        self.save_project()

    def remove_image(self, image_path):
        """Removes an image and its labels from the project."""
        abs_path = self._to_absolute(image_path)
        if abs_path in self.project_data["images"]:
            self.project_data["images"].remove(abs_path)
        
        if abs_path in self.project_data["labels"]:
            del self.project_data["labels"][abs_path]
            
        if abs_path in self.project_data["scales"]:
            del self.project_data["scales"][abs_path]

        if abs_path in self.project_data.get("image_provenance", {}):
            del self.project_data["image_provenance"][abs_path]
            
        self.save_project()

    def set_image_provenance(self, image_path, provenance, save=True):
        abs_path = self._to_absolute(image_path)
        if "image_provenance" not in self.project_data:
            self.project_data["image_provenance"] = {}
        self.project_data["image_provenance"][abs_path] = dict(provenance or {})
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

    def set_scale(self, image_path, pixels_per_mm):
        self.project_data["scales"][image_path] = pixels_per_mm
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
            entry.setdefault("auto_box_meta", {})[clean_part] = dict(source_meta)
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
        if save:
            self.save_project()
        return True

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
        if save and removed:
            self.save_project()
        return removed
    
    def get_boxes(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("boxes", {})

    def get_auto_boxes(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("auto_boxes", {})

    def get_auto_box_meta(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("auto_box_meta", {})

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
        if save:
            self.save_project()
        return clean_scope

    def update_trajectory(self, image_path, part_name, trajectory, parent_context=None):
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
        self.save_project()
        
    def get_trajectories(self, image_path):
        return self.project_data["labels"].get(image_path, {}).get("trajectories", {})

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
            
            if save:
                self.save_project()

    def set_genus(self, image_path, genus):
        self.set_taxon(image_path, genus)

    def set_taxon(self, image_path, taxon, taxon_rank=None, taxon_metadata=None):
        if image_path in self.project_data["labels"]:
            entry = self._normalize_label_taxon_fields(self.project_data["labels"][image_path])
            clean_taxon = str(taxon or "Unknown").strip() or "Unknown"
            entry["taxon"] = clean_taxon
            entry["genus"] = clean_taxon
            if taxon_rank is not None:
                entry["taxon_rank"] = str(taxon_rank or "").strip()
            if isinstance(taxon_metadata, dict):
                entry["taxon_metadata"] = dict(taxon_metadata)
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
            self.save_project() # FIX: Save immediately
            return True
        return False

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
                self.delete_label(img_path, part_name)

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
            
            self.save_project() # FIX: Save immediately
            return True
        return False

    def remove_auto_labels(self):
        """Removes all labels marked as 'Auto-Annotated'."""
        removed_count = 0
        for img_path in self.project_data["labels"]:
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
                
        self.save_project()
        return removed_count

    def verify_image_labels(self, image_path):
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
            self.save_project()
        return count

    def export_coco(self, output_dir):
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
        
        for img_path in self.project_data["images"]:
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
            
        with open(os.path.join(output_dir, "annotations.json"), 'w', encoding='utf-8') as f:
            json.dump(coco_data, f, indent=4, ensure_ascii=False)
        return count

    def export_yolo(self, output_dir):
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
        
        for img_path in self.project_data["images"]:
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

    def export_multimodal_dataset(self, output_dir, crop_size=512, global_size=1024):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        crops_dir = os.path.join(output_dir, "crops")
        global_dir = os.path.join(output_dir, "images_global")
        os.makedirs(crops_dir, exist_ok=True)
        os.makedirs(global_dir, exist_ok=True)
        
        jsonl_path = os.path.join(output_dir, "multimodal_dataset.jsonl")
        
        count = 0
        processed_globals = set() # Avoid re-processing same global image multiple times
        
        with open(jsonl_path, 'w', encoding='utf-8') as f:
            for img_path, data in self.project_data["labels"].items():
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
        return count
