import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from AntSleap.core.cascade_routes import (
        ROUTE_BACKEND_VIT_B_BLINK,
        format_expert_label,
        get_route_persisted_expert_candidates,
        merge_expert_candidates,
    )
    from AntSleap.core.expert_notes import format_expert_display_name, load_expert_notes, set_expert_note
    from AntSleap.core.model_profiles import CHILD_BACKEND_VIT_B
    from AntSleap.ui.main_window_dialog_support import (
        _route_backend_from_child_backend,
        _route_backend_from_entry,
        _route_backend_label,
        _route_manifest_from_entry,
        _runtime_child_backend_defaults,
        _translate_route_registration_source,
        _yes_no_text,
    )
    from AntSleap.ui.main_window_i18n import tr, ui_text
    from AntSleap.ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_NEUTRAL,
        apply_semantic_button_style,
        apply_theme_button_style,
        themed_yes_no_question,
    )
except ImportError:
    from core.cascade_routes import (
        ROUTE_BACKEND_VIT_B_BLINK,
        format_expert_label,
        get_route_persisted_expert_candidates,
        merge_expert_candidates,
    )
    from core.expert_notes import format_expert_display_name, load_expert_notes, set_expert_note
    from core.model_profiles import CHILD_BACKEND_VIT_B
    from ui.main_window_dialog_support import (
        _route_backend_from_child_backend,
        _route_backend_from_entry,
        _route_backend_label,
        _route_manifest_from_entry,
        _runtime_child_backend_defaults,
        _translate_route_registration_source,
        _yes_no_text,
    )
    from ui.main_window_i18n import tr, ui_text
    from ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_NEUTRAL,
        apply_semantic_button_style,
        apply_theme_button_style,
        themed_yes_no_question,
    )


class RouteManagementPanel(QWidget):
    NODE_TYPE_ROLE = Qt.UserRole
    NODE_PAYLOAD_ROLE = Qt.UserRole + 1

    def __init__(self, owner, lang="en", parent=None):
        super().__init__(parent)
        self.owner = owner
        self.lang = lang
        self.init_ui()
        self.retranslate_ui()

    def _ui(self, text):
        return ui_text(text, self.lang)

    def _tr(self, text):
        return tr(text, self.lang)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.header_label = QLabel()
        self.header_label.setObjectName("HeaderLabel")
        layout.addWidget(self.header_label)

        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        self.note_label.setObjectName("mutedLabel")
        layout.addWidget(self.note_label)

        self.route_tree = QTreeWidget()
        self.route_tree.setObjectName("projectRouteTree")
        self.route_tree.setAlternatingRowColors(True)
        self.route_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.route_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.route_tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.route_tree.setRootIsDecorated(True)
        self.route_tree.setItemsExpandable(True)
        self.route_tree.setUniformRowHeights(True)
        self.route_tree.header().setStretchLastSection(True)
        self.route_tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.route_tree.itemSelectionChanged.connect(self.update_action_buttons)
        self.route_tree.setMinimumHeight(380)
        self.route_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.route_tree, 1)

        button_row = QHBoxLayout()
        self.btn_refresh_routes = QPushButton()
        self.btn_refresh_routes.clicked.connect(self.refresh_route_table)
        apply_semantic_button_style(self.btn_refresh_routes, BUTTON_ROLE_NEUTRAL)
        button_row.addWidget(self.btn_refresh_routes)

        self.btn_appoint_route_expert = QPushButton()
        self.btn_appoint_route_expert.clicked.connect(self.appoint_selected_route_expert)
        apply_semantic_button_style(self.btn_appoint_route_expert, BUTTON_ROLE_COMMIT)
        button_row.addWidget(self.btn_appoint_route_expert)

        self.btn_toggle_route = QPushButton()
        self.btn_toggle_route.clicked.connect(self.toggle_selected_route_enabled)
        apply_semantic_button_style(self.btn_toggle_route, BUTTON_ROLE_NEUTRAL)
        button_row.addWidget(self.btn_toggle_route)

        self.btn_delete_route = QPushButton()
        self.btn_delete_route.clicked.connect(self.delete_selected_route)
        apply_semantic_button_style(self.btn_delete_route, BUTTON_ROLE_DESTRUCTIVE)
        button_row.addWidget(self.btn_delete_route)

        self.btn_edit_expert_note = QPushButton()
        self.btn_edit_expert_note.clicked.connect(self.edit_selected_expert_note)
        apply_semantic_button_style(self.btn_edit_expert_note, BUTTON_ROLE_NEUTRAL)
        button_row.addWidget(self.btn_edit_expert_note)

        self.btn_delete_expert_file = QPushButton()
        self.btn_delete_expert_file.clicked.connect(self.delete_selected_expert_file)
        apply_semantic_button_style(self.btn_delete_expert_file, BUTTON_ROLE_DESTRUCTIVE)
        button_row.addWidget(self.btn_delete_expert_file)

        layout.addLayout(button_row)
    def set_language(self, lang):
        self.lang = lang
        self.retranslate_ui()
        self.refresh_route_table()

    def set_theme(self, theme):
        apply_theme_button_style(self.btn_refresh_routes, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_appoint_route_expert, BUTTON_ROLE_COMMIT, "", theme)
        apply_theme_button_style(self.btn_toggle_route, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_delete_route, BUTTON_ROLE_DESTRUCTIVE, "", theme)
        apply_theme_button_style(self.btn_edit_expert_note, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_delete_expert_file, BUTTON_ROLE_DESTRUCTIVE, "", theme)

    def retranslate_ui(self):
        self.header_label.setText(self._ui("Project Routes"))
        self.note_label.setText(
            self._ui(
                "Manage parent-child expert routes in the current 2D workflow here. Deleting a route removes only this project record; training or appointing an expert later can register a candidate again."
            )
        )
        self.btn_refresh_routes.setText(self._tr("Refresh"))
        self.btn_appoint_route_expert.setText(self._tr("Appoint Expert"))
        self.btn_delete_route.setText(self._ui("Delete Route"))
        self.btn_delete_route.setToolTip(self._ui("Delete the selected project route only."))
        self.btn_edit_expert_note.setText(self._ui("Edit Expert Note"))
        self.btn_edit_expert_note.setToolTip(self._ui("Select an expert row to edit its display note."))
        self.btn_delete_expert_file.setText(self._ui("Delete Expert File"))
        self.btn_delete_expert_file.setToolTip(self._ui("Select an available expert file to delete the model file from disk."))
        self.route_tree.setHeaderLabels([
            self._ui("Parent"),
            self._ui("Child"),
            self._ui("Enabled"),
            self._ui("Backend"),
            self._ui("Expert"),
            self._ui("Status"),
            self._ui("Profile Fit"),
            self._ui("Source"),
        ])
        self.update_action_buttons()
    def _selected_node_payload(self):
        item = self.route_tree.currentItem()
        if item is None:
            return None
        payload = item.data(0, self.NODE_PAYLOAD_ROLE)
        return dict(payload) if isinstance(payload, dict) else None

    def _selected_route_entry(self):
        payload = self._selected_node_payload() or {}
        route = payload.get("route")
        return dict(route) if isinstance(route, dict) else None

    def _selected_expert_entry(self):
        payload = self._selected_node_payload() or {}
        expert = payload.get("expert")
        return dict(expert) if isinstance(expert, dict) else None

    def _make_node_payload(self, kind, *, route=None, expert=None, parent_part=None):
        payload = {"kind": str(kind or "")}
        if isinstance(route, dict):
            payload["route"] = dict(route)
        if isinstance(expert, dict):
            payload["expert"] = dict(expert)
        if parent_part:
            payload["parent_part"] = str(parent_part)
        return payload

    def _available_experts_by_part(self):
        cascade_manager = getattr(getattr(self.owner, "engine", None), "cascade_manager", None)
        if cascade_manager is None:
            return {}

        experts_by_part = {}
        for expert in cascade_manager.list_available_experts() or []:
            if not isinstance(expert, dict):
                continue
            expert_part = str(expert.get("expert_part") or "").strip()
            if not expert_part:
                continue
            experts_by_part.setdefault(expert_part, []).append(dict(expert))
        return experts_by_part

    def _expert_notes(self):
        weights_dir = getattr(getattr(self.owner, "engine", None), "weights_dir", "")
        return load_expert_notes(weights_dir)

    def _expert_root_dir(self):
        weights_dir = getattr(getattr(self.owner, "engine", None), "weights_dir", "")
        return os.path.abspath(os.path.join(str(weights_dir or ""), "experts"))

    def _is_safe_expert_file_path(self, file_path):
        if not isinstance(file_path, str) or not file_path:
            return False
        try:
            expert_root = self._expert_root_dir()
            file_abs = os.path.abspath(file_path)
            return (
                os.path.commonpath([expert_root, file_abs]) == expert_root
                and os.path.isfile(file_abs)
                and file_abs.lower().endswith(".pth")
            )
        except Exception:
            return False

    def _selected_existing_expert_file(self):
        expert = self._selected_expert_entry()
        if not expert:
            return None
        file_path = expert.get("path")
        if not self._is_safe_expert_file_path(file_path):
            return None
        expert_id = str(expert.get("expert_id") or "").strip()
        return {"path": os.path.abspath(file_path), "expert_id": expert_id}

    def _route_expert_candidates(self, route_entry, available_experts_by_part):
        route = dict(route_entry or {})
        cascade_manager = getattr(getattr(self.owner, "engine", None), "cascade_manager", None)
        resolve_route_expert_path = getattr(cascade_manager, "resolve_route_expert_path", None)
        child_part = str(route.get("child") or "").strip()
        appointed_label = format_expert_label(route)
        appointed_candidate = None
        if appointed_label != "Unappointed":
            appointed_candidate = {
                "expert_id": appointed_label,
                "expert_part": route.get("expert_part") or route.get("child"),
                "expert_filename": route.get("expert_filename"),
                "expert_backend": _route_backend_from_entry(route),
                "expert_manifest": _route_manifest_from_entry(route),
                "input_size": route.get("input_size"),
                "backend_params": route.get("backend_params") if isinstance(route.get("backend_params"), dict) else {},
                "note": route.get("note"),
                "path": resolve_route_expert_path(route) if callable(resolve_route_expert_path) else None,
            }

        candidates = []
        persisted_candidates = get_route_persisted_expert_candidates(route)
        runtime_candidates = available_experts_by_part.get(child_part, [])
        merged_candidates = merge_expert_candidates(
            persisted_candidates,
            runtime_candidates,
            appointed_expert=appointed_candidate,
        )

        available_by_id = {}
        for expert in runtime_candidates:
            expert_id = str(expert.get("expert_id") or "").strip()
            if not expert_id:
                continue
            available_by_id[expert_id] = dict(expert)

        persisted_ids = {
            str(candidate.get("expert_id") or "").strip()
            for candidate in persisted_candidates
            if isinstance(candidate, dict)
        }

        for candidate in merged_candidates:
            expert_id = str(candidate.get("expert_id") or "").strip()
            if not expert_id:
                continue

            runtime_match = available_by_id.get(expert_id)
            is_appointed = expert_id == appointed_label
            is_persisted = expert_id in persisted_ids or is_appointed
            merged_candidate = dict(candidate)
            if isinstance(runtime_match, dict):
                merged_candidate.update(runtime_match)

            merged_candidate["appointed"] = is_appointed
            merged_candidate["is_persisted"] = is_persisted
            merged_candidate["is_discoverable"] = isinstance(runtime_match, dict)
            path_value = merged_candidate.get("path")
            merged_candidate["file_exists"] = bool(path_value) and os.path.exists(path_value)
            candidates.append(merged_candidate)
        return candidates

    def _set_item_payload(self, item, payload):
        item.setData(0, self.NODE_TYPE_ROLE, payload.get("kind"))
        item.setData(0, self.NODE_PAYLOAD_ROLE, payload)

    def _active_child_route_backend(self):
        defaults = _runtime_child_backend_defaults(getattr(self.owner, "project", None))
        return _route_backend_from_child_backend(defaults.get("backend_type", CHILD_BACKEND_VIT_B))

    def _route_profile_fit_text(self, route_entry):
        route = dict(route_entry or {})
        route_label = format_expert_label(route)
        if route_label == "Unappointed":
            return self._ui("No appointed expert")
        default_backend = self._active_child_route_backend()
        route_backend = _route_backend_from_entry(route)
        if route_backend == default_backend:
            return self._ui("Matches active profile")
        return self._ui("Route-specific backend")

    def _route_profile_fit_tooltip(self, route_entry):
        route = dict(route_entry or {})
        default_backend = self._active_child_route_backend()
        route_backend = _route_backend_from_entry(route)
        return self._ui("Active profile default: {0}\nRoute expert backend: {1}").format(
            _route_backend_label(default_backend, self.lang),
            _route_backend_label(route_backend, self.lang),
        )

    def _build_route_tree_item(self, parent_item, route_entry, expert_candidates):
        route = dict(route_entry or {})
        expert_notes = self._expert_notes()
        route_item = QTreeWidgetItem(parent_item)
        self._set_item_payload(route_item, self._make_node_payload("route", route=route))
        route_item.setText(1, str(route.get("child") or ""))
        route_item.setText(2, _yes_no_text(route.get("enabled"), self.lang))
        backend_value = _route_backend_from_entry(route)
        route_item.setText(3, _route_backend_label(backend_value, self.lang))
        route_item.setToolTip(3, f"{_route_backend_label(backend_value, self.lang)}\n{backend_value}")
        route_label = format_expert_label(route)
        if route_label != "Unappointed":
            route_note = expert_notes.get(route_label, "")
            route_display = format_expert_display_name(route_label, route_note)
            route_item.setText(4, route_display)
            manifest_value = _route_manifest_from_entry(route)
            tooltip = f"{route_display}\n{route_label}"
            if manifest_value:
                tooltip += f"\n{manifest_value}"
            route_item.setToolTip(4, tooltip)
        else:
            route_item.setText(4, self._ui("Not appointed"))
        route_item.setText(5, self._route_runtime_status(route))
        route_item.setText(6, self._route_profile_fit_text(route))
        route_item.setToolTip(6, self._route_profile_fit_tooltip(route))
        route_item.setText(7, _translate_route_registration_source(route.get("registration_source"), self.lang))

        if not expert_candidates:
            placeholder_item = QTreeWidgetItem(route_item)
            self._set_item_payload(placeholder_item, self._make_node_payload("expert_placeholder", route=route))
            placeholder_item.setText(3, _route_backend_label(backend_value, self.lang))
            placeholder_item.setText(4, self._ui("Not appointed"))
            placeholder_item.setText(5, self._ui("Expert not appointed yet"))
            placeholder_item.setText(6, self._ui("No appointed expert"))
            placeholder_item.setFlags(placeholder_item.flags() & ~Qt.ItemIsSelectable)
            return route_item

        for expert in expert_candidates:
            expert_item = QTreeWidgetItem(route_item)
            self._set_item_payload(expert_item, self._make_node_payload("expert", route=route, expert=expert))
            expert_id = str(expert.get("expert_id") or "").strip()
            is_appointed = bool(expert.get("appointed"))
            is_discoverable = bool(expert.get("is_discoverable"))
            is_persisted = bool(expert.get("is_persisted"))
            file_exists = bool(expert.get("file_exists"))
            expert_note = expert_notes.get(expert_id, "")
            expert_label = format_expert_display_name(expert_id, expert_note, appointed=is_appointed)
            backend_value = expert.get("expert_backend") or route.get("expert_backend") or ROUTE_BACKEND_VIT_B_BLINK
            manifest_value = expert.get("expert_manifest") or route.get("expert_manifest") or ""
            expert_item.setText(3, _route_backend_label(backend_value, self.lang))
            expert_item.setText(4, expert_label)
            expert_item.setToolTip(
                3,
                f"{_route_backend_label(backend_value, self.lang)}\n{backend_value}",
            )
            expert_item.setToolTip(
                4,
                f"{expert_label}\n{expert_id}\n{manifest_value}".strip(),
            )
            if is_appointed:
                status_text = self._ui("Appointed")
            elif is_persisted and not file_exists:
                status_text = self._ui("Missing file history")
            elif is_persisted:
                status_text = self._ui("History")
            elif is_discoverable:
                status_text = self._ui("Discoverable")
            else:
                status_text = self._ui("Available")
            expert_item.setText(5, status_text)
            expert_item.setText(
                6,
                self._ui("Matches active profile")
                if backend_value == self._active_child_route_backend()
                else self._ui("Route-specific backend"),
            )
            expert_item.setToolTip(
                6,
                self._ui("Active profile default: {0}\nRoute expert backend: {1}").format(
                    _route_backend_label(self._active_child_route_backend(), self.lang),
                    _route_backend_label(backend_value, self.lang),
                ),
            )
            if is_appointed:
                expert_font = expert_item.font(4)
                expert_font.setBold(True)
                expert_item.setFont(4, expert_font)
                status_font = expert_item.font(5)
                status_font.setBold(True)
                expert_item.setFont(5, status_font)
        return route_item

    def _find_parent_item(self, parent_part):
        clean_parent = str(parent_part or "").strip()
        for index in range(self.route_tree.topLevelItemCount()):
            item = self.route_tree.topLevelItem(index)
            if item is None:
                continue
            payload = item.data(0, self.NODE_PAYLOAD_ROLE)
            if isinstance(payload, dict) and payload.get("kind") == "parent" and payload.get("parent_part") == clean_parent:
                return item
        return None

    def _find_route_item(self, parent_part, child_part):
        parent_item = self._find_parent_item(parent_part)
        clean_child = str(child_part or "").strip()
        if parent_item is None or not clean_child:
            return None
        for index in range(parent_item.childCount()):
            item = parent_item.child(index)
            if item is None:
                continue
            payload = item.data(0, self.NODE_PAYLOAD_ROLE)
            route = payload.get("route") if isinstance(payload, dict) else None
            if isinstance(route, dict) and route.get("parent") == str(parent_part or "").strip() and route.get("child") == clean_child:
                return item
        return None

    def _find_expert_item(self, parent_part, child_part, expert_id):
        route_item = self._find_route_item(parent_part, child_part)
        clean_expert_id = str(expert_id or "").strip()
        if route_item is None or not clean_expert_id:
            return None
        for index in range(route_item.childCount()):
            item = route_item.child(index)
            if item is None:
                continue
            payload = item.data(0, self.NODE_PAYLOAD_ROLE)
            expert = payload.get("expert") if isinstance(payload, dict) else None
            if isinstance(expert, dict) and str(expert.get("expert_id") or "").strip() == clean_expert_id:
                return item
        return None

    def _route_runtime_status(self, route_entry):
        if not route_entry:
            return self._ui("Unknown")
        block_reason = self.owner.engine.cascade_manager.get_route_block_reason(route_entry)
        if block_reason == "expert_unappointed":
            return self._ui("Expert not appointed yet")
        if block_reason == "expert_model_missing":
            return self._tr("Expert file missing")
        return self._ui("Enabled") if bool(route_entry.get("enabled", False)) else self._ui("Disabled")

    def refresh_route_table(self):
        routes = self.owner.project.iter_cascade_routes()
        experts_by_part = self._available_experts_by_part()
        self.route_tree.clear()
        parent_items = {}

        for route in routes:
            parent_part = str(route.get("parent") or "")
            parent_item = parent_items.get(parent_part)
            if parent_item is None:
                parent_item = QTreeWidgetItem(self.route_tree)
                self._set_item_payload(parent_item, self._make_node_payload("parent", parent_part=parent_part))
                parent_item.setText(0, parent_part)
                parent_item.setExpanded(True)
                parent_items[parent_part] = parent_item

            expert_candidates = self._route_expert_candidates(route, experts_by_part)
            route_item = self._build_route_tree_item(parent_item, route, expert_candidates)
            route_item.setExpanded(True)

        self.route_tree.expandAll()
        self.update_action_buttons()

    def update_action_buttons(self):
        payload = self._selected_node_payload() or {}
        route = self._selected_route_entry()
        expert = self._selected_expert_entry()
        selected_kind = str(payload.get("kind") or "")
        can_delete_missing_history = (
            selected_kind == "expert"
            and bool(route)
            and bool(expert)
            and bool(expert.get("is_persisted"))
            and not bool(expert.get("file_exists"))
            and not bool(expert.get("appointed"))
            and hasattr(self.owner.project, "remove_cascade_route_expert_candidate")
        )
        self.btn_appoint_route_expert.setEnabled(selected_kind == "expert" and bool(self._selected_expert_entry()))
        self.btn_delete_route.setEnabled((selected_kind == "route" and bool(route)) or can_delete_missing_history)
        can_edit_expert_note = selected_kind == "expert" and bool(expert) and bool(str(expert.get("expert_id") or "").strip())
        self.btn_edit_expert_note.setEnabled(can_edit_expert_note)
        can_delete_expert_file = selected_kind == "expert" and bool(self._selected_existing_expert_file())
        self.btn_delete_expert_file.setEnabled(can_delete_expert_file)
        if can_delete_expert_file:
            self.btn_delete_expert_file.setToolTip(self._ui("Delete the selected expert model file from disk."))
        else:
            self.btn_delete_expert_file.setToolTip(self._ui("Select an available expert file to delete the model file from disk."))
        self.btn_toggle_route.setEnabled(selected_kind == "route" and bool(route))
        self.btn_toggle_route.setText(
            self._tr("Disable Route") if route and route.get("enabled") else self._tr("Enable Route")
        )
    def edit_selected_expert_note(self):
        payload = self._selected_node_payload() or {}
        if str(payload.get("kind") or "") != "expert":
            return
        route = self._selected_route_entry()
        expert = self._selected_expert_entry()
        if not route or not expert:
            return
        expert_id = str(expert.get("expert_id") or "").strip()
        if not expert_id:
            return
        weights_dir = getattr(getattr(self.owner, "engine", None), "weights_dir", "")
        current_note = self._expert_notes().get(expert_id, "")
        note, ok = QInputDialog.getText(
            self,
            self._ui("Edit Expert Note"),
            self._ui("Expert display note:"),
            QLineEdit.Normal,
            current_note,
        )
        if not ok:
            return
        clean_note = set_expert_note(weights_dir, expert_id, note)
        parent_part = route.get("parent")
        child_part = route.get("child")
        self.refresh_route_table()
        refreshed_item = self._find_expert_item(parent_part, child_part, expert_id)
        if refreshed_item is not None:
            self.route_tree.setCurrentItem(refreshed_item)
        if clean_note:
            self.owner.log(self._ui("Updated expert note for {0}: {1}").format(expert_id, clean_note))
        else:
            self.owner.log(self._ui("Cleared expert note for {0}.").format(expert_id))

    def appoint_selected_route_expert(self):
        payload = self._selected_node_payload() or {}
        if str(payload.get("kind") or "") != "expert":
            return
        route = self._selected_route_entry()
        expert = self._selected_expert_entry()
        if not route or not expert:
            return
        selected_label = str(expert.get("expert_id") or "").strip()
        if not selected_label:
            return

        updated = self.owner.project.appoint_cascade_route_expert(
            route.get("parent"),
            route.get("child"),
            expert_id=selected_label,
            expert_backend=expert.get("expert_backend") or route.get("expert_backend") or ROUTE_BACKEND_VIT_B_BLINK,
            expert_manifest=expert.get("expert_manifest") or route.get("expert_manifest"),
            input_size=expert.get("input_size") or route.get("input_size"),
            backend_params=expert.get("backend_params") if isinstance(expert.get("backend_params"), dict) else route.get("backend_params"),
            note=expert.get("note") or route.get("note"),
        )
        if updated:
            self.refresh_route_table()
            self.owner.log(
                self._ui("Route {0} -> {1} now uses expert {2}.").format(
                    route.get("parent"),
                    route.get("child"),
                    selected_label,
                )
            )

    def toggle_selected_route_enabled(self):
        payload = self._selected_node_payload() or {}
        if str(payload.get("kind") or "") != "route":
            return
        route = self._selected_route_entry()
        if not route:
            return
        block_reason = self.owner.engine.cascade_manager.get_route_block_reason(route)
        if not route.get("enabled") and block_reason == "expert_unappointed":
            QMessageBox.information(self, self._tr("Appoint Expert"), self._ui("This route has no appointed expert yet. Appoint an expert first, then enable the route."))
            return
        if not route.get("enabled") and block_reason == "expert_model_missing":
            QMessageBox.information(self, self._tr("Appoint Expert"), self._ui("The appointed expert file for this route is missing. Reappoint an available expert before enabling the route."))
            return

        updated = self.owner.project.set_cascade_route_enabled(
            route.get("parent"),
            route.get("child"),
            not bool(route.get("enabled")),
        )
        if updated:
            self.refresh_route_table()
            if updated.get("enabled"):
                self.owner.log(self._ui("Route {0} -> {1} enabled.").format(updated.get("parent"), updated.get("child")))
            else:
                self.owner.log(self._ui("Route {0} -> {1} disabled.").format(updated.get("parent"), updated.get("child")))

    def delete_selected_route(self):
        payload = self._selected_node_payload() or {}
        if str(payload.get("kind") or "") == "expert":
            self.remove_selected_missing_expert_history()
            return
        if str(payload.get("kind") or "") != "route":
            return
        route = self._selected_route_entry()
        if not route:
            return
        reply = themed_yes_no_question(
            self,
            self._tr("Delete"),
            self._ui(
                "Delete project route {0} -> {1}?\n\nThis removes the current project route record only. If you reopen Blink later with the same parent/child context, Blink can register this route again as a candidate."
            ).format(route.get("parent"), route.get("child")),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply != QMessageBox.Yes:
            return
        if self.owner.project.delete_cascade_route(route.get("parent"), route.get("child")):
            self.refresh_route_table()
            self.owner.log(self._ui("Deleted route {0} -> {1}.").format(route.get("parent"), route.get("child")))

    def delete_selected_expert_file(self):
        file_info = self._selected_existing_expert_file()
        if not file_info:
            return
        file_path = file_info["path"]
        expert_id = file_info.get("expert_id") or os.path.basename(file_path)
        reply = themed_yes_no_question(
            self,
            self._ui("Delete Expert File"),
            self._ui(
                "Delete expert file {0}?\n\nThis removes the model file from disk and clears current-project expert references to it. Parent -> child route records are kept, but they will return to an unappointed state if this was the appointed expert."
            ).format(expert_id),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            os.remove(file_path)
            if expert_id:
                weights_dir = getattr(getattr(self.owner, "engine", None), "weights_dir", "")
                set_expert_note(weights_dir, expert_id, "")
            cascade_manager = getattr(getattr(self.owner, "engine", None), "cascade_manager", None)
            loaded_experts = getattr(cascade_manager, "loaded_experts", None)
            if isinstance(loaded_experts, dict):
                loaded_experts.clear()
            cleanup_refs = getattr(getattr(self.owner, "project", None), "remove_cascade_route_expert_references", None)
            cleanup_count = 0
            if callable(cleanup_refs):
                cleanup_count = int(cleanup_refs(expert_id, save=True) or 0)
            self.refresh_route_table()
            self.owner.log(self._ui("Deleted expert file {0}. Cleared {1} current-project route reference(s).").format(expert_id, cleanup_count))
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._tr("Delete Model"),
                self._ui("Failed to delete expert file: {0}").format(exc),
            )

    def remove_selected_missing_expert_history(self):
        route = self._selected_route_entry()
        expert = self._selected_expert_entry()
        if not route or not expert:
            return
        if not bool(expert.get("is_persisted")) or bool(expert.get("file_exists")) or bool(expert.get("appointed")):
            return
        remove_candidate = getattr(self.owner.project, "remove_cascade_route_expert_candidate", None)
        if not callable(remove_candidate):
            return
        expert_id = str(expert.get("expert_id") or "").strip()
        if not expert_id:
            return
        reply = themed_yes_no_question(
            self,
            self._tr("Delete"),
            self._ui(
                "Remove missing expert history {0} from route {1} -> {2}?\n\nThis only cleans the current project route history. It does not delete any model file."
            ).format(expert_id, route.get("parent"), route.get("child")),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply != QMessageBox.Yes:
            return
        if remove_candidate(route.get("parent"), route.get("child"), expert_id):
            self.refresh_route_table()
            self.owner.log(
                self._ui("Removed missing expert history {0} from route {1} -> {2}.").format(
                    expert_id,
                    route.get("parent"),
                    route.get("child"),
                )
            )
