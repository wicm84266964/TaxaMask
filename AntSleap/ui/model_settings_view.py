try:
    from AntSleap.ui.model_settings_dependencies import *
except ImportError:
    from ui.model_settings_dependencies import *


class ModelSettingsViewMixin:
    def _build_workflow_note(self, layout):
        lang = self.lang
        workflow_note = QLabel(
            tr(
                "2D/STL morphology settings control rendered STL views and ordinary morphology images.",
                lang,
            )
        )
        workflow_note.setWordWrap(True)
        workflow_note.setObjectName("mutedLabel")
        layout.addWidget(workflow_note)

    def _build_profile_and_parent_extension(self, params, active_profile, parent_backend, child_defaults):
        lang = self.lang
        profile_group = QGroupBox(tr("Model Profiles", lang))
        apply_surface_role(profile_group, SURFACE_ROLE_SUBTLE, "modelSettingsProfilePanel")
        profile_form = QGridLayout(profile_group)
        profile_form.setContentsMargins(12, 12, 12, 12)
        profile_form.setHorizontalSpacing(10)
        profile_form.setVerticalSpacing(8)
        profile_note = QLabel(tr("Project profile changes are saved into the current project JSON. Save the current controls as a profile after choosing the model sources and validating any advanced extensions you want to reuse.", lang))
        profile_note.setWordWrap(True)
        profile_note.setObjectName("mutedLabel")
        profile_form.addWidget(profile_note, 0, 0, 1, 3)
        profile_form.addWidget(QLabel(tr("Current Model Profile:", lang)), 1, 0)
        self.combo_model_profile = NoWheelComboBox()
        self.combo_model_profile.setObjectName("modelSettingsProfileCombo")
        profile_form.addWidget(self.combo_model_profile, 1, 1, 1, 2)
        profile_form.addWidget(QLabel(tr("Profile ID:", lang)), 2, 0)
        self.profile_id_edit = QLineEdit()
        self.profile_id_edit.setReadOnly(True)
        profile_form.addWidget(self.profile_id_edit, 2, 1, 1, 2)
        profile_form.addWidget(QLabel(tr("Profile Display Name:", lang)), 3, 0)
        self.profile_name_edit = QLineEdit()
        profile_form.addWidget(self.profile_name_edit, 3, 1, 1, 2)
        profile_form.addWidget(QLabel(tr("Profile Description:", lang)), 4, 0)
        self.profile_description_edit = QTextEdit()
        self.profile_description_edit.setAcceptRichText(False)
        self.profile_description_edit.setMinimumHeight(82)
        profile_form.addWidget(self.profile_description_edit, 4, 1, 1, 2)
        profile_form.addWidget(QLabel(tr("Profile Summary:", lang)), 5, 0)
        self.profile_summary_box = QTextEdit()
        self.profile_summary_box.setObjectName("modelSettingsProfileSummary")
        self.profile_summary_box.setReadOnly(True)
        self.profile_summary_box.setAcceptRichText(False)
        self.profile_summary_box.setMinimumHeight(128)
        profile_form.addWidget(self.profile_summary_box, 5, 1, 1, 2)
        profile_buttons = QHBoxLayout()
        self.btn_new_profile = QPushButton(tr("Save Current Settings as New Profile", lang))
        self.btn_copy_profile = QPushButton(tr("Copy Profile", lang))
        self.btn_delete_profile = QPushButton(tr("Delete Profile", lang))
        self.btn_set_active_profile = QPushButton(tr("Set as Active Profile", lang))
        for button, role in [
            (self.btn_new_profile, BUTTON_ROLE_NEUTRAL),
            (self.btn_copy_profile, BUTTON_ROLE_NEUTRAL),
            (self.btn_delete_profile, BUTTON_ROLE_DESTRUCTIVE),
            (self.btn_set_active_profile, BUTTON_ROLE_COMMIT),
        ]:
            apply_semantic_button_style(button, role)
            profile_buttons.addWidget(button)
        profile_form.addLayout(profile_buttons, 6, 0, 1, 3)
        self._refresh_profile_combo()
        self.combo_model_profile.currentIndexChanged.connect(self._load_selected_profile_fields)
        self.profile_name_edit.textChanged.connect(self._update_current_profile_metadata)
        self.profile_description_edit.textChanged.connect(self._update_current_profile_metadata)
        self.btn_new_profile.clicked.connect(self.new_model_profile)
        self.btn_copy_profile.clicked.connect(self.copy_model_profile)
        self.btn_delete_profile.clicked.connect(self.delete_model_profile)
        self.btn_set_active_profile.clicked.connect(self.set_selected_profile_active)
        self.profile_tab_index = None

        tab_backend = QWidget()
        tab_backend.setObjectName("modelSettingsAdvancedExtensionsTab")
        form_backend = QVBoxLayout(tab_backend)
        advanced_note = QLabel(
            tr(
                "Advanced extensions collect high-impact model source switches plus custom script and manifest settings for the current model profile. Parent-part and child-part pages show the active sources as read-only summaries.",
                lang,
            )
        )
        advanced_note.setWordWrap(True)
        advanced_note.setObjectName("mutedLabel")
        form_backend.addWidget(advanced_note)
        advanced_order_note = QLabel(
            tr(
                "Advanced extension order: 1) choose or save the model profile, 2) choose parent/default child model sources, 3) fill the parent or child custom extension blocks only when those sources are selected.",
                lang,
            )
        )
        advanced_order_note.setWordWrap(True)
        advanced_order_note.setObjectName("mutedLabel")
        form_backend.addWidget(advanced_order_note)
        profile_group.setTitle(tr("1. Model Profiles", lang))
        form_backend.addWidget(profile_group)
        self.backend_combo = NoWheelComboBox()
        self.backend_combo.addItem(tr("Built-in Locator + SAM", lang), BUILTIN_BACKEND_ID)
        self.backend_combo.addItem(tr("Custom Script Extension", lang), EXTERNAL_BACKEND_ID)
        initial_backend = params.get("model_backend", BUILTIN_BACKEND_ID)
        active_parent = active_profile.get("parent_backend", {}) if isinstance(active_profile.get("parent_backend"), dict) else {}
        if active_parent.get("backend_type") == PARENT_BACKEND_EXTERNAL:
            initial_backend = EXTERNAL_BACKEND_ID
        elif active_parent.get("backend_type") == PARENT_BACKEND_BUILTIN:
            initial_backend = BUILTIN_BACKEND_ID
        backend_index = self.backend_combo.findData(initial_backend)
        self.backend_combo.setCurrentIndex(backend_index if backend_index >= 0 else 0)
        self.backend_combo.setEnabled(False)
        self.backend_combo.setToolTip(
            tr(
                "Compatibility display only. Choose Parent Model Source in Advanced Extensions to switch the active parent model source.",
                lang,
            )
        )
        self.backend_combo.setVisible(False)

        model_source_group = QGroupBox(tr("2. Model Source Switches", lang))
        model_source_group.setObjectName("modelSettingsModelSourceSwitchPanel")
        apply_surface_role(model_source_group, SURFACE_ROLE_SUBTLE, "modelSettingsModelSourceSwitchPanel")
        model_source_layout = QVBoxLayout(model_source_group)
        model_source_layout.setContentsMargins(12, 12, 12, 12)
        model_source_layout.setSpacing(8)
        model_source_note = QLabel(
            tr(
                "Choose the high-impact model sources for the current profile here. Existing child route experts stay route-specific; this default mainly affects new/default child expert training and unresolved route defaults.",
                lang,
            )
        )
        model_source_note.setWordWrap(True)
        model_source_note.setObjectName("mutedLabel")
        model_source_layout.addWidget(model_source_note)
        model_source_layout.addWidget(QLabel(tr("Parent Model Source:", lang)))
        self.parent_backend_combo = NoWheelComboBox()
        self.parent_backend_combo.addItem(tr("Built-in Locator + SAM", lang), PARENT_BACKEND_BUILTIN)
        self.parent_backend_combo.addItem(tr("Custom Parent Extension", lang), PARENT_BACKEND_EXTERNAL)
        parent_backend_index = self.parent_backend_combo.findData(parent_backend.get("backend_type", PARENT_BACKEND_BUILTIN))
        self.parent_backend_combo.setCurrentIndex(parent_backend_index if parent_backend_index >= 0 else 0)
        self.parent_backend_combo.currentIndexChanged.connect(self._sync_legacy_backend_combo_from_parent_backend)
        self.parent_backend_combo.currentIndexChanged.connect(lambda _index: self._refresh_model_source_summaries())
        model_source_layout.addWidget(self.parent_backend_combo)
        parent_source_note = QLabel(
            tr(
                "Parent source changes parent-part training and Auto annotation. Custom Parent Extension calls the configured script below instead of built-in Locator/SAM.",
                lang,
            )
        )
        parent_source_note.setWordWrap(True)
        parent_source_note.setObjectName("mutedLabel")
        model_source_layout.addWidget(parent_source_note)
        model_source_layout.addWidget(QLabel(tr("Default Child Expert:", lang)))
        self.child_backend_combo = NoWheelComboBox()
        self.child_backend_combo.addItem(tr("ViT-B Blink Expert", lang), CHILD_BACKEND_VIT_B)
        self.child_backend_combo.addItem(tr("Heatmap Blink Expert", lang), CHILD_BACKEND_HEATMAP)
        self.child_backend_combo.addItem(tr("Custom Child Extension", lang), CHILD_BACKEND_EXTERNAL)
        child_backend_index = self.child_backend_combo.findData(child_defaults.get("backend_type", CHILD_BACKEND_VIT_B))
        self.child_backend_combo.setCurrentIndex(child_backend_index if child_backend_index >= 0 else 0)
        self.child_backend_combo.currentIndexChanged.connect(lambda _index: self._refresh_model_source_summaries())
        model_source_layout.addWidget(self.child_backend_combo)
        child_source_note = QLabel(
            tr(
                "Default child expert affects new/default child expert training. During inference, each appointed parent -> child route calls the backend recorded on that route.",
                lang,
            )
        )
        child_source_note.setWordWrap(True)
        child_source_note.setObjectName("mutedLabel")
        model_source_layout.addWidget(child_source_note)
        form_backend.addWidget(model_source_group)

        parent_extension_group = QGroupBox(tr("3. Parent-part Custom Extension", lang))
        parent_extension_group.setObjectName("modelSettingsParentExtensionPanel")
        apply_surface_role(parent_extension_group, SURFACE_ROLE_SUBTLE, "modelSettingsParentExtensionPanel")
        parent_extension_layout = QVBoxLayout(parent_extension_group)
        parent_extension_layout.setContentsMargins(12, 12, 12, 12)
        parent_extension_layout.setSpacing(8)
        self.parent_extension_status_label = QLabel()
        self.parent_extension_status_label.setObjectName("modelSettingsParentExtensionStatus")
        self.parent_extension_status_label.setWordWrap(True)
        parent_extension_layout.addWidget(self.parent_extension_status_label)
        external_note = QLabel(
            tr("Use this advanced entry when you want TaxaMask to call your own parent-part training or prediction scripts. Commands run in an isolated external_runs directory and receive a contract JSON path through {contract} or {contract_json}. When Parent Model Source is set to Custom Parent Extension for the active model profile, built-in Locator/SAM training and prediction do not run for that task.", lang)
        )
        external_note.setWordWrap(True)
        external_note.setObjectName("mutedLabel")
        parent_extension_layout.addWidget(external_note)
        external_profile_note = QLabel(
            tr(
                "Parent extension settings are saved inside the current model profile when Parent Model Source is set to Custom Parent Extension.",
                lang,
            )
        )
        external_profile_note.setWordWrap(True)
        external_profile_note.setObjectName("mutedLabel")
        parent_extension_layout.addWidget(external_profile_note)

        external_config = sanitize_external_backend_config(params.get("external_backend", {}))
        parent_extension_layout.addWidget(QLabel(tr("Extension ID:", lang)))
        self.external_backend_id = QLineEdit(external_config.get("backend_id", ""))
        parent_extension_layout.addWidget(self.external_backend_id)
        parent_extension_layout.addWidget(QLabel(tr("Display Name:", lang)))
        self.external_display_name = QLineEdit(external_config.get("display_name", ""))
        parent_extension_layout.addWidget(self.external_display_name)
        parent_extension_layout.addWidget(QLabel(tr("Python Executable:", lang)))
        self.external_python = QLineEdit(external_config.get("python_executable", "python"))
        parent_extension_layout.addWidget(self.external_python)
        parent_extension_layout.addWidget(QLabel(tr("Prepare Dataset Command:", lang)))
        self.external_prepare_command = self._make_command_editor(
            external_config.get("prepare_dataset_command", ""),
            "{python} scripts/prepare_dataset.py --contract {contract_json}",
        )
        parent_extension_layout.addWidget(self.external_prepare_command)
        parent_extension_layout.addWidget(QLabel(tr("Train Command:", lang)))
        self.external_train_command = self._make_command_editor(
            external_config.get("train_command", ""),
            "{python} scripts/train_model.py --contract {contract_json}",
        )
        parent_extension_layout.addWidget(self.external_train_command)
        parent_extension_layout.addWidget(QLabel(tr("Predict Command:", lang)))
        self.external_predict_command = self._make_command_editor(
            external_config.get("predict_command", ""),
            "{python} scripts/predict_image.py --contract {contract_json}",
        )
        parent_extension_layout.addWidget(self.external_predict_command)
        parent_extension_layout.addWidget(QLabel(tr("Model Manifest Path:", lang)))
        self.external_model_manifest = QLineEdit(external_config.get("model_manifest", ""))
        self.external_model_manifest.setPlaceholderText("{run_dir}/model/taxamask_model_manifest.json")
        parent_extension_layout.addWidget(self.external_model_manifest)
        self.external_validation_label = QLabel()
        self.external_validation_label.setObjectName("mutedLabel")
        self.external_validation_label.setWordWrap(True)
        parent_extension_layout.addWidget(self.external_validation_label)
        btn_validate_external = QPushButton(tr("Validate Parent Extension", lang))
        apply_semantic_button_style(btn_validate_external, BUTTON_ROLE_NEUTRAL)
        btn_validate_external.clicked.connect(self.validate_external_backend)
        parent_extension_layout.addWidget(btn_validate_external)
        form_backend.addWidget(parent_extension_group)

        return tab_backend, form_backend

    def _build_parent_tab(self, params):
        lang = self.lang
        tab_parent = QWidget()
        tab_parent.setObjectName("modelSettingsParentTab")
        form_parent = QVBoxLayout(tab_parent)
        self.parent_backend_status_label = QLabel()
        self.parent_backend_status_label.setObjectName("modelSettingsParentSourceSummary")
        self.parent_backend_status_label.setWordWrap(True)
        form_parent.addWidget(self.parent_backend_status_label)
        parent_backend_status_note = QLabel(tr("Read-only summary. Change this source in Advanced Extensions.", lang))
        parent_backend_status_note.setWordWrap(True)
        parent_backend_status_note.setObjectName("mutedLabel")
        form_parent.addWidget(parent_backend_status_note)
        form_parent.addWidget(QLabel(tr("Epochs:", lang)))
        self.spin_epochs = QLineEdit(str(params['epochs']))
        form_parent.addWidget(self.spin_epochs)
        form_parent.addWidget(QLabel(tr("Batch Size:", lang)))
        self.spin_batch = QLineEdit(str(params['batch']))
        form_parent.addWidget(self.spin_batch)
        form_parent.addWidget(QLabel(tr("Learning Rate:", lang)))
        self.spin_lr = QLineEdit(str(params['lr']))
        form_parent.addWidget(self.spin_lr)
        form_parent.addWidget(QLabel(tr("Weight Decay (L2 Reg):", lang)))
        self.spin_wd = QLineEdit(str(params['wd']))
        form_parent.addWidget(self.spin_wd)

        device_group = QGroupBox(tr("Runtime Device:", lang))
        apply_surface_role(device_group, SURFACE_ROLE_SUBTLE, "modelSettingsRuntimeDevicePanel")
        device_layout = QVBoxLayout(device_group)
        device_layout.setContentsMargins(12, 12, 12, 12)
        device_layout.setSpacing(8)
        device_note = QLabel(
            tr(
                "Controls built-in Locator/SAM/Blink training and inference. Custom extensions use their own command environment. CPU can run small tests, but CUDA is recommended for real training.",
                lang,
            )
        )
        device_note.setWordWrap(True)
        device_note.setObjectName("mutedLabel")
        device_layout.addWidget(device_note)
        self.combo_runtime_device = NoWheelComboBox()
        self.combo_runtime_device.addItem(tr("Auto (CUDA if available)", lang), "auto")
        self.combo_runtime_device.addItem(tr("CPU only", lang), "cpu")
        self.combo_runtime_device.addItem(tr("CUDA GPU", lang), "cuda")
        runtime_device = normalize_device_preference(params.get("runtime_device", "auto"))
        runtime_index = self.combo_runtime_device.findData(runtime_device)
        self.combo_runtime_device.setCurrentIndex(runtime_index if runtime_index >= 0 else 0)
        device_layout.addWidget(self.combo_runtime_device)
        form_parent.addWidget(device_group)

        parent_ratio_group = QGroupBox(tr("Parent Box Aspect Ratios:", lang))
        apply_surface_role(parent_ratio_group, SURFACE_ROLE_SUBTLE, "modelSettingsParentBoxRatioPanel")
        ratio_layout = QGridLayout(parent_ratio_group)
        ratio_layout.setContentsMargins(12, 12, 12, 12)
        ratio_layout.setHorizontalSpacing(10)
        ratio_layout.setVerticalSpacing(8)
        ratio_note = QLabel(
            tr(
                "Used when the main labeling workbench draws parent context boxes. Enter each as width : height, for example 4 : 3. Child boxes and Blink shrink start boxes stay free-ratio.",
                lang,
            )
        )
        ratio_note.setWordWrap(True)
        ratio_note.setObjectName("mutedLabel")
        ratio_layout.addWidget(ratio_note, 0, 0, 1, 4)
        self.parent_box_ratio_inputs = {}
        ratio_map = params.get("parent_box_aspect_ratios", {}) if isinstance(params.get("parent_box_aspect_ratios", {}), dict) else {}
        default_ratio_parts = ["Head", "Mesosoma", "Gaster", "Whole body"]
        ratio_parts = []
        for part_name in list(self.initial_locator_scope) + default_ratio_parts:
            clean_part = str(part_name or "").strip()
            if clean_part and clean_part not in ratio_parts:
                ratio_parts.append(clean_part)
        ratio_layout.addWidget(QLabel(tr("Width", lang)), 1, 1)
        ratio_layout.addWidget(QLabel(tr("Height", lang)), 1, 3)
        for index, part_name in enumerate(ratio_parts, start=2):
            ratio_layout.addWidget(QLabel(part_name), index, 0)
            width_edit = QLineEdit()
            width_edit.setPlaceholderText("4")
            width_edit.setMaximumWidth(90)
            height_edit = QLineEdit()
            height_edit.setPlaceholderText("3")
            height_edit.setMaximumWidth(90)
            self.parent_box_ratio_inputs[part_name] = (width_edit, height_edit)
            self._set_parent_box_ratio_input(part_name, ratio_map.get(part_name, ""))
            ratio_layout.addWidget(width_edit, index, 1)
            ratio_layout.addWidget(QLabel(":"), index, 2)
            ratio_layout.addWidget(height_edit, index, 3)
        form_parent.addWidget(parent_ratio_group)

        locator_group = QGroupBox(tr("Main Locator Parts:", lang))
        apply_surface_role(locator_group, SURFACE_ROLE_SUBTLE, "modelSettingsLocatorScopePanel")
        locator_layout = QVBoxLayout(locator_group)
        locator_layout.setContentsMargins(12, 12, 12, 12)
        locator_layout.setSpacing(8)
        locator_note = QLabel(
            tr(
                "Choose which structures the built-in Locator should learn as large, stable targets. Small structures can stay in Structures and be refined with SAM, Blink, or a custom extension.",
                lang,
            )
        )
        locator_note.setWordWrap(True)
        locator_note.setObjectName("mutedLabel")
        locator_layout.addWidget(locator_note)

        locator_grid = QGridLayout()
        locator_grid.setContentsMargins(0, 4, 0, 0)
        locator_grid.setHorizontalSpacing(16)
        locator_grid.setVerticalSpacing(6)
        for index, part_name in enumerate(self.taxonomy):
            check = QCheckBox(part_name)
            check.setChecked(part_name in self.initial_locator_scope)
            check.setProperty("part_name", part_name)
            self.locator_scope_checks.append(check)
            locator_grid.addWidget(check, index // 2, index % 2)
        locator_layout.addLayout(locator_grid)
        self.locator_scope_validation_label = QLabel("")
        self.locator_scope_validation_label.setObjectName("mutedLabel")
        locator_layout.addWidget(self.locator_scope_validation_label)
        form_parent.addWidget(locator_group)
        form_parent.addStretch()
        self.parent_tab_index = self.tabs.addTab(self._make_scroll_tab(tab_parent), tr("Parent-part annotation", lang))

    def _build_child_tab(self, params, child_defaults, form_backend):
        lang = self.lang
        tab_child = QWidget()
        tab_child.setObjectName("modelSettingsChildTab")
        form_child = QVBoxLayout(tab_child)
        self.child_backend_status_label = QLabel()
        self.child_backend_status_label.setObjectName("modelSettingsChildSourceSummary")
        self.child_backend_status_label.setWordWrap(True)
        form_child.addWidget(self.child_backend_status_label)
        child_backend_status_note = QLabel(tr("Read-only summary. Change this source in Advanced Extensions.", lang))
        child_backend_status_note.setWordWrap(True)
        child_backend_status_note.setObjectName("mutedLabel")
        form_child.addWidget(child_backend_status_note)

        blink_group = QGroupBox(tr("Blink Expert Training Defaults:", lang))
        apply_surface_role(blink_group, SURFACE_ROLE_SUBTLE, "modelSettingsBlinkTrainingPanel")
        blink_layout = QVBoxLayout(blink_group)
        blink_layout.setContentsMargins(12, 12, 12, 12)
        blink_layout.setSpacing(8)
        blink_note = QLabel(
            tr(
                "These defaults are shown in Child Expert Session when the app starts or settings are saved. You can still adjust them for a single expert before training.",
                lang,
            )
        )
        blink_note.setWordWrap(True)
        blink_note.setObjectName("mutedLabel")
        blink_layout.addWidget(blink_note)
        blink_layout.addWidget(QLabel(tr("Blink Training Strategy:", lang)))
        self.combo_blink_training_strategy = NoWheelComboBox()
        for strategy in (
            BLINK_STRATEGY_TRIVIEW_RANDOM,
            BLINK_STRATEGY_FULL_INSIDE_RANDOM,
            BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
        ):
            self.combo_blink_training_strategy.addItem(blink_training_strategy_label(strategy, lang), strategy)
        selected_strategy = sanitize_blink_training_strategy(
            child_defaults.get("training_strategy"),
            params.get("blink_training_strategy", DEFAULT_BLINK_TRAINING_STRATEGY),
        )
        strategy_index = self.combo_blink_training_strategy.findData(selected_strategy)
        self.combo_blink_training_strategy.setCurrentIndex(strategy_index if strategy_index >= 0 else 0)
        self.combo_blink_training_strategy.currentIndexChanged.connect(self._update_blink_training_strategy_note)
        blink_layout.addWidget(self.combo_blink_training_strategy)
        self.blink_training_strategy_note = QLabel("")
        self.blink_training_strategy_note.setWordWrap(True)
        self.blink_training_strategy_note.setObjectName("mutedLabel")
        blink_layout.addWidget(self.blink_training_strategy_note)
        self._update_blink_training_strategy_note()
        blink_layout.addWidget(QLabel(tr("Default Blink Epochs:", lang)))
        self.spin_blink_epochs = QLineEdit(str(params.get("blink_epochs", 5)))
        blink_layout.addWidget(self.spin_blink_epochs)
        blink_layout.addWidget(QLabel(tr("Default Blink Batch Size:", lang)))
        self.spin_blink_batch = QLineEdit(str(params.get("blink_batch", 2)))
        blink_layout.addWidget(self.spin_blink_batch)
        blink_layout.addWidget(QLabel(tr("Default Blink Learning Rate:", lang)))
        self.spin_blink_lr = QLineEdit(str(params.get("blink_lr", 1e-3)))
        blink_layout.addWidget(self.spin_blink_lr)
        blink_layout.addWidget(QLabel(tr("Default Blink Weight Decay:", lang)))
        self.spin_blink_wd = QLineEdit(str(params.get("blink_weight_decay", 1e-4)))
        blink_layout.addWidget(self.spin_blink_wd)
        blink_layout.addWidget(QLabel(tr("Default Blink Input Size:", lang)))
        self.combo_blink_input_size = NoWheelComboBox()
        for side in [224, 384, 512]:
            self.combo_blink_input_size.addItem(f"{side} x {side}", side)
        try:
            input_side = int(params.get("blink_input_size", 224))
        except Exception:
            input_side = 224
        input_index = self.combo_blink_input_size.findData(input_side)
        self.combo_blink_input_size.setCurrentIndex(input_index if input_index >= 0 else 0)
        blink_layout.addWidget(self.combo_blink_input_size)
        blink_layout.addWidget(QLabel(tr("Auto-shrink Steps:", lang)))
        self.spin_blink_auto_shrink_steps = NoWheelSpinBox()
        self.spin_blink_auto_shrink_steps.setRange(1, 200)
        try:
            shrink_steps = int(child_defaults.get("auto_shrink_steps", params.get("blink_auto_shrink_steps", DEFAULT_CHILD_AUTO_SHRINK_STEPS)))
        except Exception:
            shrink_steps = DEFAULT_CHILD_AUTO_SHRINK_STEPS
        self.spin_blink_auto_shrink_steps.setValue(max(1, min(200, shrink_steps)))
        self.spin_blink_auto_shrink_steps.setToolTip(
            tr(
                "Number of interpolation steps from the loose shrink start box to the final target box. 20 steps saves 21 trajectory frames including the starting frame.",
                lang,
            )
        )
        blink_layout.addWidget(self.spin_blink_auto_shrink_steps)
        form_child.addWidget(blink_group)

        blink_dataset_group = QGroupBox(tr("Blink Shrink Training Datasets", lang))
        blink_dataset_group.setObjectName("modelSettingsBlinkDatasetPanel")
        apply_surface_role(blink_dataset_group, SURFACE_ROLE_SUBTLE, "modelSettingsBlinkDatasetPanel")
        blink_dataset_layout = QVBoxLayout(blink_dataset_group)
        blink_dataset_layout.setContentsMargins(12, 12, 12, 12)
        blink_dataset_layout.setSpacing(8)
        self.blink_dataset_note = QLabel(
            tr(
                "Shows saved auto-shrink trajectories used to train child-part experts. Each row is grouped by parent -> child route.",
                lang,
            )
        )
        self.blink_dataset_note.setWordWrap(True)
        self.blink_dataset_note.setObjectName("mutedLabel")
        blink_dataset_layout.addWidget(self.blink_dataset_note)
        self.blink_dataset_tree = QTreeWidget()
        self.blink_dataset_tree.setObjectName("modelSettingsBlinkDatasetTree")
        self.blink_dataset_tree.setRootIsDecorated(False)
        self.blink_dataset_tree.setAlternatingRowColors(True)
        self.blink_dataset_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.blink_dataset_tree.setHeaderLabels(
            [
                tr("Route", lang),
                tr("Images", lang),
                tr("Frames", lang),
                tr("Sources", lang),
            ]
        )
        self.blink_dataset_tree.setMinimumHeight(160)
        self.blink_dataset_tree.itemSelectionChanged.connect(self._refresh_blink_dataset_actions)
        header = self.blink_dataset_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        blink_dataset_layout.addWidget(self.blink_dataset_tree)
        dataset_buttons = QHBoxLayout()
        self.btn_blink_dataset_details = QPushButton(tr("View Details", lang))
        self.btn_blink_dataset_details.setObjectName("modelSettingsBlinkDatasetDetailsButton")
        self.btn_blink_dataset_details.clicked.connect(self._show_blink_dataset_details)
        apply_semantic_button_style(self.btn_blink_dataset_details, BUTTON_ROLE_NEUTRAL)
        self.btn_blink_dataset_delete = QPushButton(tr("Delete Dataset", lang))
        self.btn_blink_dataset_delete.setObjectName("modelSettingsBlinkDatasetDeleteButton")
        self.btn_blink_dataset_delete.clicked.connect(self._delete_selected_blink_dataset)
        apply_semantic_button_style(self.btn_blink_dataset_delete, BUTTON_ROLE_DESTRUCTIVE)
        dataset_buttons.addWidget(self.btn_blink_dataset_details)
        dataset_buttons.addWidget(self.btn_blink_dataset_delete)
        dataset_buttons.addStretch(1)
        blink_dataset_layout.addLayout(dataset_buttons)
        form_child.addWidget(blink_dataset_group)

        heatmap_group = QGroupBox(tr("Heatmap Blink Parameters:", lang))
        apply_surface_role(heatmap_group, SURFACE_ROLE_SUBTLE, "modelSettingsHeatmapBlinkPanel")
        heatmap_layout = QVBoxLayout(heatmap_group)
        heatmap_params = child_defaults.get("heatmap_params", {}) if isinstance(child_defaults.get("heatmap_params"), dict) else {}
        self.spin_heatmap_input_size = QLineEdit(str(heatmap_params.get("input_size", DEFAULT_HEATMAP_BLINK_PARAMS["input_size"])))
        self.spin_heatmap_sigma = QLineEdit(str(heatmap_params.get("heatmap_sigma", DEFAULT_HEATMAP_BLINK_PARAMS["heatmap_sigma"])))
        self.spin_heatmap_wh_loss = QLineEdit(str(heatmap_params.get("wh_loss_weight", DEFAULT_HEATMAP_BLINK_PARAMS["wh_loss_weight"])))
        self.spin_heatmap_center_loss = QLineEdit(str(heatmap_params.get("center_loss_weight", DEFAULT_HEATMAP_BLINK_PARAMS["center_loss_weight"])))
        for label_text, editor in [
            (tr("Heatmap Input Size:", lang), self.spin_heatmap_input_size),
            (tr("Heatmap Sigma:", lang), self.spin_heatmap_sigma),
            (tr("WH Loss Weight:", lang), self.spin_heatmap_wh_loss),
            (tr("Center Loss Weight:", lang), self.spin_heatmap_center_loss),
        ]:
            heatmap_layout.addWidget(QLabel(label_text))
            heatmap_layout.addWidget(editor)
        form_child.addWidget(heatmap_group)

        external_blink_group = QGroupBox(tr("4. Child-part Custom Extension", lang))
        apply_surface_role(external_blink_group, SURFACE_ROLE_SUBTLE, "modelSettingsExternalBlinkPanel")
        external_blink_layout = QVBoxLayout(external_blink_group)
        external_blink_layout.setContentsMargins(12, 12, 12, 12)
        external_blink_layout.setSpacing(8)
        self.child_extension_status_label = QLabel()
        self.child_extension_status_label.setObjectName("modelSettingsChildExtensionStatus")
        self.child_extension_status_label.setWordWrap(True)
        external_blink_layout.addWidget(self.child_extension_status_label)
        external_blink_note = QLabel(
            tr(
                "Child extension settings are saved inside the current model profile when Default Child Backend is set to Custom Child Extension.",
                lang,
            )
        )
        external_blink_note.setWordWrap(True)
        external_blink_note.setObjectName("mutedLabel")
        external_blink_layout.addWidget(external_blink_note)
        external_blink = dict(DEFAULT_EXTERNAL_BLINK_BACKEND)
        if isinstance(child_defaults.get("external_blink_backend"), dict):
            external_blink.update(child_defaults.get("external_blink_backend"))
        self.external_blink_backend_id = QLineEdit(external_blink.get("backend_id", ""))
        self.external_blink_display_name = QLineEdit(external_blink.get("display_name", ""))
        self.external_blink_python = QLineEdit(external_blink.get("python_executable", "python"))
        self.external_blink_predict_command = self._make_command_editor(
            external_blink.get("predict_command", ""),
            "{python} scripts/predict_child.py --contract {contract_json}",
        )
        self.external_blink_train_command = self._make_command_editor(
            external_blink.get("train_command", ""),
            "{python} scripts/train_child.py --contract {contract_json}",
        )
        self.external_blink_model_manifest = QLineEdit(external_blink.get("model_manifest", ""))
        for label_text, widget in [
            (tr("Child Extension ID:", lang), self.external_blink_backend_id),
            (tr("Child Extension Display Name:", lang), self.external_blink_display_name),
            (tr("Child Extension Python Executable:", lang), self.external_blink_python),
            (tr("Child Extension Predict Command:", lang), self.external_blink_predict_command),
            (tr("Child Extension Train Command:", lang), self.external_blink_train_command),
            (tr("Child Extension Model Manifest:", lang), self.external_blink_model_manifest),
        ]:
            external_blink_layout.addWidget(QLabel(label_text))
            external_blink_layout.addWidget(widget)
        self.external_blink_validation_label = QLabel()
        self.external_blink_validation_label.setObjectName("mutedLabel")
        self.external_blink_validation_label.setWordWrap(True)
        external_blink_layout.addWidget(self.external_blink_validation_label)
        btn_validate_external_blink = QPushButton(tr("Validate Child Extension", lang))
        apply_semantic_button_style(btn_validate_external_blink, BUTTON_ROLE_NEUTRAL)
        btn_validate_external_blink.clicked.connect(self.validate_external_blink_backend)
        external_blink_layout.addWidget(btn_validate_external_blink)
        form_backend.addWidget(external_blink_group)
        form_backend.addStretch()
        form_child.addStretch()
        self.child_tab_index = self.tabs.addTab(self._make_scroll_tab(tab_child), tr("Child-part annotation", lang))

    def _build_inference_tab(self, params, tab_backend):
        lang = self.lang
        tab_inf = QWidget()
        form_inf = QVBoxLayout(tab_inf)
        form_inf.addWidget(QLabel(tr("Confidence Threshold:", lang)))
        self.spin_conf = QLineEdit(str(params['conf']))
        form_inf.addWidget(self.spin_conf)
        form_inf.addWidget(QLabel(tr("Adaptive Thresh Ratio:", lang)))
        self.spin_adapt = QLineEdit(str(params['adapt']))
        form_inf.addWidget(self.spin_adapt)
        form_inf.addWidget(QLabel(tr("Noise Floor:", lang)))
        self.spin_noise = QLineEdit(str(params['noise_floor']))
        form_inf.addWidget(self.spin_noise)
        form_inf.addWidget(QLabel(tr("Polygon Simplification (px):", lang)))
        self.spin_poly = QLineEdit(str(params.get('poly_epsilon', 2.0)))
        form_inf.addWidget(self.spin_poly)
        form_inf.addWidget(QLabel(tr("Box Padding Ratio:", lang)))
        self.spin_pad = QLineEdit(str(params['pad']))
        form_inf.addWidget(self.spin_pad)

        vlm_settings = params.get("vlm_preannotation", {}) if isinstance(params.get("vlm_preannotation", {}), dict) else {}
        vlm_group = QGroupBox(tr("AI Multimodal Pre-Annotation:", lang))
        apply_surface_role(vlm_group, SURFACE_ROLE_SUBTLE, "modelSettingsVlmPreannotationPanel")
        vlm_layout = QVBoxLayout(vlm_group)
        vlm_layout.setContentsMargins(12, 12, 12, 12)
        vlm_layout.setSpacing(8)
        vlm_note = QLabel(
            tr(
                "Choose which existing project structures will be sent to the multimodal model. This list is separate from main locator parts.",
                lang,
            )
        )
        vlm_note.setWordWrap(True)
        vlm_note.setObjectName("mutedLabel")
        vlm_layout.addWidget(vlm_note)
        vlm_layout.addWidget(QLabel(tr("VLM Target Parts:", lang)))
        vlm_grid = QGridLayout()
        vlm_grid.setContentsMargins(0, 4, 0, 0)
        vlm_grid.setHorizontalSpacing(16)
        vlm_grid.setVerticalSpacing(6)
        selected_vlm_parts = {
            str(part).strip()
            for part in vlm_settings.get("target_parts", [])
            if str(part).strip()
        }
        for index, part_name in enumerate(self.taxonomy):
            check = QCheckBox(part_name)
            check.setChecked(part_name in selected_vlm_parts)
            check.setProperty("part_name", part_name)
            self.vlm_target_part_checks.append(check)
            vlm_grid.addWidget(check, index // 2, index % 2)
        vlm_layout.addLayout(vlm_grid)

        self.btn_vlm_detail_toggle = QToolButton()
        self.btn_vlm_detail_toggle.setObjectName("modelSettingsVlmDetailToggle")
        self.btn_vlm_detail_toggle.setText(tr("VLM Detailed Settings", lang))
        self.btn_vlm_detail_toggle.setCheckable(True)
        self.btn_vlm_detail_toggle.setChecked(False)
        self.btn_vlm_detail_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_vlm_detail_toggle.setArrowType(Qt.RightArrow)
        vlm_layout.addWidget(self.btn_vlm_detail_toggle)

        self.vlm_details_widget = QWidget()
        self.vlm_details_widget.setObjectName("modelSettingsVlmDetailsPanel")
        vlm_details_layout = QVBoxLayout(self.vlm_details_widget)
        vlm_details_layout.setContentsMargins(0, 4, 0, 0)
        vlm_details_layout.setSpacing(8)
        self.vlm_details_widget.setVisible(False)
        self.btn_vlm_detail_toggle.toggled.connect(self._toggle_vlm_details)

        vlm_details_layout.addWidget(QLabel(tr("VLM Batch Scope:", lang)))
        self.combo_vlm_processing_scope = NoWheelComboBox()
        self.combo_vlm_processing_scope.setObjectName("modelSettingsVlmBatchScopeCombo")
        self.combo_vlm_processing_scope.addItem(tr("All imported images", lang), "all_images")
        self.combo_vlm_processing_scope.addItem(tr("Images in selected list group", lang), "image_group")
        scope_value = str(vlm_settings.get("processing_scope", "image_group") or "image_group")
        if scope_value == "current_image":
            scope_value = "image_group"
        scope_index = self.combo_vlm_processing_scope.findData(scope_value)
        self.combo_vlm_processing_scope.setCurrentIndex(scope_index if scope_index >= 0 else 0)
        vlm_details_layout.addWidget(self.combo_vlm_processing_scope)
        vlm_details_layout.addWidget(QLabel(tr("VLM Image Group:", lang)))
        self.combo_vlm_image_group = NoWheelComboBox()
        self.combo_vlm_image_group.setObjectName("modelSettingsVlmImageGroupCombo")
        self._populate_vlm_image_group_combo(str(vlm_settings.get("image_group", "split") or "split"))
        vlm_details_layout.addWidget(self.combo_vlm_image_group)
        vlm_details_layout.addWidget(QLabel(tr("VLM API Concurrency:", lang)))
        self.spin_vlm_concurrency = NoWheelSpinBox()
        self.spin_vlm_concurrency.setObjectName("modelSettingsVlmConcurrencySpin")
        self.spin_vlm_concurrency.setRange(1, 8)
        self.spin_vlm_concurrency.setValue(max(1, min(8, int(vlm_settings.get("concurrency", 1) or 1))))
        self.spin_vlm_concurrency.setToolTip(
            tr(
                "Default is 1 to protect rate-limited API keys. Increase only if your provider explicitly allows parallel requests; high concurrency can trigger throttling, extra charges, or account blocking.",
                lang,
            )
        )
        vlm_details_layout.addWidget(self.spin_vlm_concurrency)
        vlm_concurrency_note = QLabel(
            tr(
                "Default is 1 to protect rate-limited API keys. Increase only if your provider explicitly allows parallel requests; high concurrency can trigger throttling, extra charges, or account blocking.",
                lang,
            )
        )
        vlm_concurrency_note.setWordWrap(True)
        vlm_concurrency_note.setObjectName("mutedLabel")
        vlm_details_layout.addWidget(vlm_concurrency_note)
        vlm_details_layout.addWidget(QLabel(tr("VLM Prompt Profile:", lang)))
        vlm_profile_note = QLabel(
            tr(
                "Prompt profile only changes the instructions sent to the multimodal model. The grid input, JSON schema, coordinate mapping, and SAM draft generation stay locked.",
                lang,
            )
        )
        vlm_profile_note.setWordWrap(True)
        vlm_profile_note.setObjectName("mutedLabel")
        vlm_details_layout.addWidget(vlm_profile_note)
        self.combo_vlm_prompt_profile = NoWheelComboBox()
        self.combo_vlm_prompt_profile.setObjectName("modelSettingsVlmPromptProfileCombo")
        self.combo_vlm_prompt_profile.addItem(tr("Built-in Ant Taxonomy Default", lang), DEFAULT_VLM_PROMPT_PROFILE_ID)
        self.combo_vlm_prompt_profile.addItem(tr("Project Custom Prompt", lang), "project_custom")
        self.combo_vlm_prompt_profile.currentIndexChanged.connect(lambda _index: self._refresh_vlm_prompt_profile_editors())
        vlm_details_layout.addWidget(self.combo_vlm_prompt_profile)
        vlm_prompt_help = QLabel(
            tr(
                "Use the built-in ant prompt profile as a stable baseline. Choose Project Custom Prompt when adapting VLM pre-annotation to another taxon or a special image style.",
                lang,
            )
        )
        vlm_prompt_help.setWordWrap(True)
        vlm_prompt_help.setObjectName("mutedLabel")
        vlm_details_layout.addWidget(vlm_prompt_help)
        vlm_details_layout.addWidget(QLabel(tr("Profile Name:", lang)))
        self.vlm_prompt_profile_name = QLineEdit()
        self.vlm_prompt_profile_name.setObjectName("modelSettingsVlmPromptProfileName")
        vlm_details_layout.addWidget(self.vlm_prompt_profile_name)
        self.vlm_prompt_taxon_context = self._make_prompt_profile_editor()
        self.vlm_prompt_body_rules = self._make_prompt_profile_editor()
        self.vlm_prompt_anchor_rules = self._make_prompt_profile_editor()
        self.vlm_prompt_extra_instructions = self._make_prompt_profile_editor()
        for label_text, editor in [
            (tr("Research Taxon / Image Context:", lang), self.vlm_prompt_taxon_context),
            (tr("Main Body / Attachment Rules:", lang), self.vlm_prompt_body_rules),
            (tr("Part Anchor Rules:", lang), self.vlm_prompt_anchor_rules),
            (tr("Extra VLM Instructions:", lang), self.vlm_prompt_extra_instructions),
        ]:
            vlm_details_layout.addWidget(QLabel(label_text))
            vlm_details_layout.addWidget(editor)
        vlm_layout.addWidget(self.vlm_details_widget)
        self._set_vlm_prompt_profile_controls(vlm_settings)
        form_inf.addWidget(vlm_group)

        self.lbl_cascade_note = QLabel(
            ui_text(
                "Project routes below control which parent -> child expert links are available.",
                lang,
            )
        )
        self.lbl_cascade_note.setWordWrap(True)
        self.lbl_cascade_note.setObjectName("mutedLabel")
        form_inf.addWidget(self.lbl_cascade_note)
        if self.route_panel is not None:
            route_group = QGroupBox(ui_text("Project Route Management", lang))
            apply_surface_role(route_group, SURFACE_ROLE_SUBTLE, "modelSettingsRoutePanel")
            route_layout = QVBoxLayout(route_group)
            route_layout.setContentsMargins(12, 12, 12, 12)
            route_layout.setSpacing(10)
            route_layout.addWidget(self.route_panel)
            form_inf.addWidget(route_group, 1)

        form_inf.addStretch()
        self.inference_tab_index = self.tabs.addTab(self._make_scroll_tab(tab_inf), tr("Inference", lang))
        self.advanced_extensions_tab_index = self.tabs.addTab(self._make_scroll_tab(tab_backend), tr("Advanced Extensions", lang))
        self.external_backend_tab_index = self.advanced_extensions_tab_index

    def _build_dialog_actions(self, layout):
        lang = self.lang
        layout.addWidget(self.tabs, 1)
        btn_layout = QHBoxLayout()
        btn_ask_agent = QPushButton(tr("Ask Agent", lang))
        btn_ask_agent.setObjectName("modelSettingsAskAgentButton")
        btn_ask_agent.setToolTip(tr("Ask Agent about these settings. Current values are summarized without sending full command text.", lang))
        apply_semantic_button_style(btn_ask_agent, BUTTON_ROLE_NEUTRAL)
        btn_ask_agent.clicked.connect(self.request_agent_help)
        btn_save = QPushButton(tr("Save", lang))
        apply_semantic_button_style(btn_save, BUTTON_ROLE_COMMIT)
        btn_save.clicked.connect(self.accept_with_validation)
        btn_cancel = QPushButton(tr("Cancel", lang))
        apply_semantic_button_style(btn_cancel, BUTTON_ROLE_STOP)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ask_agent)
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        self._refresh_blink_dataset_table()
        self._load_selected_profile_fields()
