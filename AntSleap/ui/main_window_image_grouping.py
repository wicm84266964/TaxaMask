try:
    from AntSleap.ui.main_window_navigation_dependencies import *
except ImportError:
    from ui.main_window_navigation_dependencies import *


class MainWindowImageGroupingMixin:
    def _panel_crop_identity_index(self, images, provenance_by_image=None):
        provenance_by_image = provenance_by_image or {}
        image_identities = {}
        stem_dir_index = set()
        stem_identity_index = {}
        split_crop_identities = set()
        source_with_crops = set()
        for img in images or []:
            if not img:
                continue
            try:
                identity = os.path.normcase(os.path.normpath(os.path.abspath(str(img))))
            except Exception:
                identity = str(img)
            image_identities[img] = identity
            try:
                directory = os.path.normcase(os.path.abspath(os.path.dirname(str(img))))
                stem = os.path.normcase(os.path.splitext(os.path.basename(str(img)))[0])
                stem_dir_index.add((directory, stem))
                stem_identity_index.setdefault((directory, stem), identity)
            except Exception:
                pass

        for img in images or []:
            if not img:
                continue
            identity = image_identities.get(img, "")
            provenance = provenance_by_image.get(img, {})
            derived_from = provenance.get("derived_from") if isinstance(provenance, dict) else {}
            if isinstance(derived_from, dict) and bool(derived_from.get("image_path")):
                split_crop_identities.add(identity)
                try:
                    source_identity = os.path.normcase(
                        os.path.normpath(os.path.abspath(str(derived_from.get("image_path"))))
                    )
                    source_with_crops.add(source_identity)
                except Exception:
                    pass
                continue

            base_name = os.path.basename(str(img))
            if not re.search(r"__(?:panel|crop)_\d{3}(?:_\d+)?\.(?:png|jpe?g|tif|tiff)$", base_name, re.IGNORECASE):
                continue
            try:
                crop_dir = os.path.normcase(os.path.abspath(os.path.dirname(str(img))))
                crop_stem = os.path.splitext(base_name)[0]
                source_stem = re.sub(r"__(?:panel|crop)_\d{3}(?:_\d+)?$", "", crop_stem, flags=re.IGNORECASE)
                source_key = (crop_dir, os.path.normcase(source_stem))
                if source_key in stem_dir_index:
                    split_crop_identities.add(identity)
                    source_identity = stem_identity_index.get(source_key)
                    if source_identity and source_identity != identity:
                        source_with_crops.add(source_identity)
            except Exception:
                continue

        return image_identities, split_crop_identities, source_with_crops

    def _project_image_groups(self, images=None, labeled_images=None):
        groups = {group_id: [] for group_id, _label in self._all_image_group_definitions()}
        images = [img for img in (images if images is not None else self.project.project_data.get("images", [])) if img]
        image_order = {img: index for index, img in enumerate(images)}
        provenance_by_image = {
            img: self.project.get_image_provenance(img)
            for img in images
            if hasattr(self.project, "get_image_provenance")
        }
        image_identities, split_crop_identities, source_with_crops = self._panel_crop_identity_index(
            images,
            provenance_by_image=provenance_by_image,
        )
        if labeled_images is None:
            labeled_images = {
                img
                for img in images
                if bool(self.project.get_labels(img) or self.project.get_auto_boxes(img))
            }
        else:
            labeled_images = set(labeled_images or [])

        def sort_group_items(items):
            return sorted(
                list(items or []),
                key=lambda path: (0 if path in labeled_images else 1, image_order.get(path, len(image_order))),
            )

        for img in images:
            if not img:
                continue
            provenance = provenance_by_image.get(img, {})
            manual_group = str(provenance.get("manual_image_group", "") or "").strip() if isinstance(provenance, dict) else ""
            if manual_group and manual_group in groups:
                groups[manual_group].append(img)
                continue
            identity = image_identities.get(img, "")
            is_labeled = img in labeled_images
            is_split_crop = identity in split_crop_identities
            is_hard_candidate_crop = is_split_crop and self._is_hard_joined_candidate_crop(img, provenance=provenance)
            review = provenance.get("panel_split_review") if isinstance(provenance, dict) else {}
            review_status = review.get("status") if isinstance(review, dict) else ""
            needs_manual_split = (not is_split_crop) and identity not in source_with_crops and review_status == "manual_required"
            manual_split_done = (not is_split_crop) and review_status == "manual_done"
            if needs_manual_split:
                groups.setdefault("manual", []).append(img)
            elif is_hard_candidate_crop:
                groups.setdefault("hard_candidates", []).append(img)
            elif is_split_crop:
                groups.setdefault("split", []).append(img)
            elif manual_split_done:
                groups.setdefault("manual_done", []).append(img)
            else:
                groups.setdefault("original", []).append(img)
        for group_id in list(groups.keys()):
            groups[group_id] = sort_group_items(groups.get(group_id, []))
        return groups

    def _same_project_image_path(self, left, right):
        if not left or not right:
            return False
        to_absolute = getattr(self.project, "_to_absolute", None)
        try:
            left_path = to_absolute(left) if callable(to_absolute) else os.path.abspath(str(left))
            right_path = to_absolute(right) if callable(to_absolute) else os.path.abspath(str(right))
        except Exception:
            left_path = str(left)
            right_path = str(right)
        return os.path.normcase(os.path.normpath(left_path)) == os.path.normcase(os.path.normpath(right_path))

    def _project_image_key_for_path(self, image_path):
        for candidate in self.project.project_data.get("images", []):
            if self._same_project_image_path(candidate, image_path):
                return candidate
        return ""
