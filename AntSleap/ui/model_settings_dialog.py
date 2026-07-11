try:
    from AntSleap.ui.model_settings_agent import ModelSettingsAgentMixin
    from AntSleap.ui.model_settings_dataset import ModelSettingsDatasetMixin
    from AntSleap.ui.model_settings_dependencies import *
    from AntSleap.ui.model_settings_profile import ModelSettingsProfileMixin
    from AntSleap.ui.model_settings_view import ModelSettingsViewMixin
except ImportError:
    from ui.model_settings_agent import ModelSettingsAgentMixin
    from ui.model_settings_dataset import ModelSettingsDatasetMixin
    from ui.model_settings_dependencies import *
    from ui.model_settings_profile import ModelSettingsProfileMixin
    from ui.model_settings_view import ModelSettingsViewMixin


class ModelSettingsDialog(
    ModelSettingsViewMixin,
    ModelSettingsDatasetMixin,
    ModelSettingsProfileMixin,
    ModelSettingsAgentMixin,
    QDialog,
):
    agent_requested = Signal(dict)

    def __init__(self, params, lang="en", parent=None, route_panel=None):
        super().__init__(parent)
        self.lang = lang
        self.route_panel = route_panel
        self.setWindowTitle(tr("2D/STL Morphology Model Settings", lang))
        self.resize(880, 680)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.locator_scope_checks = []
        self.vlm_target_part_checks = []
        self.taxonomy = [str(part) for part in params.get("taxonomy", []) if str(part).strip()]
        self.initial_locator_scope = [str(part) for part in params.get("locator_scope", []) if str(part).strip()]
        self.vlm_image_group_definitions = self._normalize_vlm_image_group_definitions(
            params.get("vlm_image_group_definitions", [])
        )
        if not self.taxonomy:
            self.taxonomy = list(self.initial_locator_scope)
        if not self.initial_locator_scope:
            self.initial_locator_scope = list(self.taxonomy)
        model_profile_context = {
            "taxonomy": self.taxonomy,
            "locator_scope": self.initial_locator_scope,
            "parent_box_aspect_ratios": params.get("parent_box_aspect_ratios", {}),
            "vlm_preannotation": params.get("vlm_preannotation", {}),
            "child_auto_shrink_steps": params.get("blink_auto_shrink_steps", DEFAULT_CHILD_AUTO_SHRINK_STEPS),
        }
        raw_model_profiles = params.get("model_profiles", {})
        if (
            (not isinstance(raw_model_profiles, dict) or not raw_model_profiles.get("profiles"))
            and params.get("model_backend") == EXTERNAL_BACKEND_ID
        ):
            model_profile_context["parent_backend_type"] = PARENT_BACKEND_EXTERNAL
            model_profile_context["external_parent_backend"] = params.get("external_backend", {})
        self.model_profiles = sanitize_model_profiles(
            params.get("model_profiles", {}),
            **model_profile_context,
        )
        active_profile = self._active_profile()
        parent_backend = active_profile.get("parent_backend", {}) if isinstance(active_profile, dict) else {}
        child_defaults = active_profile.get("child_backend_defaults", {}) if isinstance(active_profile, dict) else {}
        self.owner_window = parent if hasattr(parent, "project") else None
        self._build_workflow_note(layout)
        tab_backend, form_backend = self._build_profile_and_parent_extension(
            params,
            active_profile,
            parent_backend,
            child_defaults,
        )
        self._build_parent_tab(params)
        self._build_child_tab(params, child_defaults, form_backend)
        self._build_inference_tab(params, tab_backend)
        self._build_dialog_actions(layout)

