try:
    from AntSleap.ui.main_window_coordinator import MainWindowCoordinator
    from AntSleap.ui.main_window_shell_dependencies import *
    from AntSleap.ui.main_window_signal_router import MainWindowSignalRouter
    from AntSleap.ui.main_window_view import MainWindowViewAdapter
except ImportError:
    from ui.main_window_coordinator import MainWindowCoordinator
    from ui.main_window_shell_dependencies import *
    from ui.main_window_signal_router import MainWindowSignalRouter
    from ui.main_window_view import MainWindowViewAdapter


class MainWindowShellMixin:
    def _initialize_main_window_state(
        self,
        *,
        config_factory,
        project_factory,
        tif_project_factory,
        stl_project_factory,
        database_factory,
        engine_factory,
    ):
        self._apply_window_icon()
        self.startup_size = QSize(1480, 920)
        self.resize(self.startup_size)
        self.config = config_factory()
        self.current_lang = self.config.get("language", "en")
        self.current_theme = normalize_theme(self.config.get("theme", "dark"))
        if self.config.get("theme", "dark") != self.current_theme:
            self.config.set("theme", self.current_theme)
        self.tif_workflow_enabled = _env_flag_enabled(EXPERIMENTAL_TIF_WORKFLOW_ENV)
        self.project = project_factory()
        self.project.set_known_relocated_roots(self.config.get("known_relocated_roots", []))
        self.tif_project = tif_project_factory()
        self.stl_project = stl_project_factory()
        self.active_project_kind = "image"
        self.active_project_source_kind = "image"
        self.active_project_entry_path = ""
        self.last_workbench_kind = "image"
        self.db = database_factory()
        
        self.train_epochs = self.config.get("train_epochs", 5)
        self.train_batch = self.config.get("train_batch", 4)
        self.blink_train_epochs = self.config.get("blink_train_epochs", 5)
        self.blink_train_batch = self.config.get("blink_train_batch", 2)
        self.blink_train_lr = self.config.get("blink_train_lr", 1e-3)
        self.blink_train_weight_decay = self.config.get("blink_train_weight_decay", 1e-4)
        self.blink_train_input_size = self.config.get("blink_train_input_size", 224)
        self.blink_auto_shrink_steps = int(self.config.get("blink_auto_shrink_steps", DEFAULT_CHILD_AUTO_SHRINK_STEPS) or DEFAULT_CHILD_AUTO_SHRINK_STEPS)
        self.blink_training_strategy = sanitize_blink_training_strategy(
            self.config.get("blink_training_strategy", DEFAULT_BLINK_TRAINING_STRATEGY)
        )
        self.train_lr = self.config.get("train_lr", 1e-4)
        self.train_wd = self.config.get("train_weight_decay", 1e-4)
        self.runtime_device = normalize_device_preference(self.config.get("runtime_device", "auto"))
        self.model_backend = self.config.get("model_backend", BUILTIN_BACKEND_ID)
        self.external_backend_config = sanitize_external_backend_config(self.config.get("external_backend", {}))
        self.inf_conf = self.config.get("inf_conf_thresh", 0.1)
        self.inf_adapt = self.config.get("inf_adapt_thresh", 0.4)
        self.inf_pad = self.config.get("inf_box_pad", 0.4)
        self.inf_noise_floor = self.config.get("inf_noise_floor", 0.15)
        self.inf_poly_epsilon = self.config.get("inf_poly_epsilon", 2.0)
        self.engine = engine_factory(
            learning_rate=self.train_lr,
            weight_decay=self.train_wd,
            num_classes=len(self.project.get_locator_scope()),
            device=self.runtime_device,
        )
        self.current_image = None
        self.inf_thread = None
        self.sam_thread = None
        self.sam_worker = None
        self.sam_busy = False
        self.pending_sam_part = None
        self.pending_sam_image = None
        self.pending_sam_description = ""
        self.pending_sam_project_context = {}
        self.image_import_thread = None
        self.image_import_progress_dialog = None
        self.external_batch_inference_thread = None
        self.external_batch_inference_progress_dialog = None
        self.external_batch_inference_failed = False
        self.external_batch_inference_saved_any = False
        self.external_training_thread = None
        self.external_training_failed = False
        self.trainer = None
        self.locator_preload_thread = None
        self.parts_model_preload_thread = None
        try:
            autosave_seconds = int(float(self.config.get("project_autosave_interval_sec", 3)))
        except Exception:
            autosave_seconds = 3
        self.project_autosave_delay_ms = max(1, autosave_seconds) * 1000
        self.project_save_navigation_idle_ms = max(1200, min(5000, self.project_autosave_delay_ms))
        self.project_last_image_switch_at = 0.0
        self.project_save_pending = False
        self.project_save_context = {}
        self.project_save_timer = QTimer(self)
        self.project_save_timer.setSingleShot(True)
        self.project_save_timer.timeout.connect(self._flush_pending_project_save)
        self.last_confirmed_locator_timestamp = None
        self.pending_training_preflight = None
        self.training_retry_requested = False
        self.parent_training_failed = False
        self.parent_training_cancel_requested = False
        self.child_training_failed = False
        self.child_training_cancel_requested = False
        self.active_training_kind = None
        self.active_training_label = ""
        self.current_blink_context = {}
        self.vlm_preannotation_thread = None
        self.vlm_preannotation_threads = []
        self.vlm_preannotation_progress_dialog = None
        self.vlm_preannotation_cancel_requested = False
        self.vlm_preannotation_cancelled_queued_images = 0
        self.image_list_group_collapsed = {
            "original": False,
            "split": False,
            "manual": False,
        }
        self._image_list_state_cache = None
        self.parent_box_aspect_ratios = (
            self.project.get_parent_box_aspect_ratios()
            if hasattr(self.project, "get_parent_box_aspect_ratios")
            else {}
        )

        self.shell_signal_router = MainWindowSignalRouter()
        self.shell_coordinator = MainWindowCoordinator(
            enter_image=self.enter_image_workflow,
            enter_tif=self.enter_tif_workflow,
            open_agent=self.open_agent_from_context,
            return_to_start=self.return_to_start_center_with_context,
        )

    def _build_main_window_views(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.start_center_widget = self._build_start_center()

        self.workbench_widget = QWidget()
        main_layout = QVBoxLayout(self.workbench_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        self.create_menus()

        self.btn_export = QPushButton()
        self.btn_export.clicked.connect(self.export_dataset)
        apply_semantic_button_style(self.btn_export, BUTTON_ROLE_COMMIT)
        self.btn_crop = QPushButton()
        self.btn_crop.clicked.connect(self.open_cropper)
        apply_semantic_button_style(self.btn_crop, BUTTON_ROLE_NEUTRAL)
        self.btn_batch_split_panels = QPushButton()
        self.btn_batch_split_panels.clicked.connect(self.batch_split_panel_images)
        apply_semantic_button_style(self.btn_batch_split_panels, BUTTON_ROLE_NEUTRAL)
        self.btn_blink_entry = QPushButton()
        self.btn_blink_entry.clicked.connect(self.launch_blink_from_workbench)
        apply_semantic_button_style(self.btn_blink_entry, BUTTON_ROLE_NEUTRAL)
        self.btn_start_center_from_workbench = QPushButton()
        self.btn_start_center_from_workbench.setObjectName("workbenchStartCenterButton")
        self.btn_start_center_from_workbench.clicked.connect(self.shell_coordinator.return_to_start)
        apply_semantic_button_style(self.btn_start_center_from_workbench, BUTTON_ROLE_NEUTRAL)
        self.btn_agent_from_workbench = QPushButton()
        self.btn_agent_from_workbench.setObjectName("workbenchAskAgentButton")
        self.btn_agent_from_workbench.clicked.connect(
            lambda: self.shell_coordinator.open_agent(self._collect_image_workbench_agent_context())
        )
        apply_semantic_button_style(self.btn_agent_from_workbench, BUTTON_ROLE_NEUTRAL)
        self.btn_vlm_preannotate_current = QPushButton()
        self.btn_vlm_preannotate_current.setObjectName("workbenchVlmPreannotateCurrentButton")
        self.btn_vlm_preannotate_current.clicked.connect(self.run_vlm_preannotation_current)
        apply_semantic_button_style(self.btn_vlm_preannotate_current, BUTTON_ROLE_RUN)
        self.btn_vlm_preannotate_batch = QPushButton()
        self.btn_vlm_preannotate_batch.setObjectName("workbenchVlmPreannotateBatchButton")
        self.btn_vlm_preannotate_batch.clicked.connect(self.run_vlm_preannotation_batch)
        apply_semantic_button_style(self.btn_vlm_preannotate_batch, BUTTON_ROLE_RUN)

        self.workbench_top_bar = QWidget()
        apply_surface_role(self.workbench_top_bar, SURFACE_ROLE_TOOLBAR, "workbenchTopBar")
        top_bar_layout = QHBoxLayout(self.workbench_top_bar)
        top_bar_layout.setContentsMargins(12, 10, 12, 10)
        top_bar_layout.setSpacing(10)

        self.toolbar_project_panel = QWidget()
        apply_surface_role(self.toolbar_project_panel, SURFACE_ROLE_SUBTLE, "workbenchToolbarProjectPanel")
        toolbar_project_layout = QHBoxLayout(self.toolbar_project_panel)
        toolbar_project_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_project_layout.setSpacing(8)
        toolbar_project_layout.addWidget(self.btn_export)
        toolbar_project_layout.addWidget(self.btn_crop)
        toolbar_project_layout.addWidget(self.btn_batch_split_panels)

        self.toolbar_flow_panel = QWidget()
        apply_surface_role(self.toolbar_flow_panel, SURFACE_ROLE_SUBTLE, "workbenchToolbarFlowPanel")
        toolbar_flow_layout = QHBoxLayout(self.toolbar_flow_panel)
        toolbar_flow_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_flow_layout.setSpacing(8)
        toolbar_flow_layout.addWidget(self.btn_blink_entry)
        toolbar_flow_layout.addWidget(self.btn_start_center_from_workbench)
        toolbar_flow_layout.addWidget(self.btn_vlm_preannotate_current)
        toolbar_flow_layout.addWidget(self.btn_vlm_preannotate_batch)
        toolbar_flow_layout.addWidget(self.btn_agent_from_workbench)

        top_bar_layout.addWidget(self.toolbar_project_panel, 0)
        top_bar_layout.addStretch(1)
        top_bar_layout.addWidget(self.toolbar_flow_panel, 0)
        main_layout.addWidget(self.workbench_top_bar)

        self.workbench_splitter = QSplitter(Qt.Horizontal)
        self.workbench_splitter.setChildrenCollapsible(False)
        self.workbench_splitter.setHandleWidth(8)
        main_layout.addWidget(self.workbench_splitter, 1)

        left_panel = QWidget()
        apply_surface_role(left_panel, SURFACE_ROLE_SUBTLE, "workbenchLibraryPanel")
        left_panel.setMinimumWidth(220)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)
        self.label_project_images = QLabel()
        self.label_project_images.setObjectName("HeaderLabel")
        left_layout.addWidget(self.label_project_images)
        self.file_list = ImageGroupListWidget()
        self.file_list.setObjectName("imageList")
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_list_context_menu)
        self.file_list.itemClicked.connect(self._handle_image_list_item_clicked)
        self.file_list.currentItemChanged.connect(self.on_file_selected)
        self.file_list.imagesDroppedToGroup.connect(self.move_images_to_group)
        left_layout.addWidget(self.file_list)
        self.btn_add = QPushButton()
        self.btn_add.clicked.connect(self.add_images)
        apply_semantic_button_style(self.btn_add, BUTTON_ROLE_NEUTRAL)
        left_layout.addWidget(self.btn_add)
        self.workbench_splitter.addWidget(left_panel)

        center_panel = QWidget()
        center_panel.setObjectName("workbenchCenterPanel")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(12)

        self.tool_strip = QWidget()
        apply_surface_role(self.tool_strip, SURFACE_ROLE_SUBTLE, "workbenchToolStrip")
        tool_layout = QHBoxLayout(self.tool_strip)
        tool_layout.setContentsMargins(12, 8, 12, 8)
        tool_layout.setSpacing(12)
        self.tool_group = QButtonGroup(self)
        self.radio_draw = QRadioButton()
        self.radio_draw.setObjectName("toolChip")
        self.radio_draw.setChecked(True)
        self.radio_draw.toggled.connect(self.on_tool_changed)
        self.tool_group.addButton(self.radio_draw)
        tool_layout.addWidget(self.radio_draw)
        self.radio_magic = QRadioButton()
        self.radio_magic.setObjectName("toolChip")
        self.radio_magic.toggled.connect(self.on_tool_changed)
        self.tool_group.addButton(self.radio_magic)
        tool_layout.addWidget(self.radio_magic)
        self.radio_box = QRadioButton()
        self.radio_box.setObjectName("toolChip")
        self.radio_box.toggled.connect(self.on_tool_changed)
        self.tool_group.addButton(self.radio_box)
        tool_layout.addWidget(self.radio_box)
        self.radio_annotation_box = QRadioButton()
        self.radio_annotation_box.setObjectName("toolChip")
        self.radio_annotation_box.toggled.connect(self.on_tool_changed)
        self.tool_group.addButton(self.radio_annotation_box)
        tool_layout.addWidget(self.radio_annotation_box)
        self.radio_loose_shrink_box = QRadioButton()
        self.radio_loose_shrink_box.setObjectName("toolChip")
        self.radio_loose_shrink_box.toggled.connect(self.on_tool_changed)
        self.tool_group.addButton(self.radio_loose_shrink_box)
        tool_layout.addWidget(self.radio_loose_shrink_box)
        self.radio_scale = QRadioButton()
        self.radio_scale.setObjectName("scaleToolRadio")
        self.radio_scale.toggled.connect(self.on_tool_changed)
        self.tool_group.addButton(self.radio_scale)
        self.radio_scale.setVisible(False) 
        tool_layout.addWidget(self.radio_scale)
        tool_layout.addStretch(1)
        center_layout.addWidget(self.tool_strip)

        self.canvas = AnnotationCanvas()
        self.canvas.setObjectName("annotationCanvas")
        self.canvas.polygon_completed.connect(self.on_polygon_completed)
        self.canvas.magic_wand_clicked.connect(self.on_magic_wand_clicked)
        self.canvas.magic_box_completed.connect(self.on_magic_box_completed)
        self.canvas.annotation_box_completed.connect(self.on_annotation_box_completed)
        self.canvas.scale_defined.connect(self.on_scale_defined)
        self.canvas_shell = QWidget()
        apply_surface_role(self.canvas_shell, SURFACE_ROLE_CANVAS, "workbenchCanvasShell")
        canvas_layout = QVBoxLayout(self.canvas_shell)
        canvas_layout.setContentsMargins(12, 12, 12, 12)
        canvas_layout.addWidget(self.canvas)
        center_layout.addWidget(self.canvas_shell, 1)
        self.workbench_splitter.addWidget(center_panel)

        from PySide6.QtGui import QKeySequence, QShortcut
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.canvas.undo)
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.shortcut_redo.activated.connect(self.canvas.redo)
        self.shortcut_save = QShortcut(QKeySequence(Qt.Key_S), self)
        self.shortcut_save.activated.connect(lambda: self._flush_pending_project_save(force=True))
        self.shortcut_verify = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.shortcut_verify.activated.connect(self.verify_current_image)

        self.workbench_inspector_scroll = QScrollArea()
        self.workbench_inspector_scroll.setObjectName("workbenchInspectorScroll")
        self.workbench_inspector_scroll.setWidgetResizable(True)
        self.workbench_inspector_scroll.setFrameShape(QFrame.NoFrame)
        self.workbench_inspector_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.workbench_inspector_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
        right_panel = QWidget()
        right_panel.setMinimumWidth(320)
        right_panel.setObjectName("workbenchInspectorPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        self.metadata_panel = QWidget()
        apply_surface_role(self.metadata_panel, SURFACE_ROLE_PANEL, "workbenchMetadataPanel")
        metadata_layout = QVBoxLayout(self.metadata_panel)
        metadata_layout.setContentsMargins(12, 12, 12, 12)
        metadata_layout.setSpacing(10)
        self.label_taxonomy = QLabel()
        self.label_taxonomy.setObjectName("HeaderLabel")
        self.genus_combo = NoWheelComboBox()
        self.genus_combo.setEditable(True)
        self.genus_combo.setInsertPolicy(QComboBox.InsertAlphabetically)
        self.genus_combo.currentTextChanged.connect(self.on_genus_changed)
        self.label_structures = QLabel()
        self.label_structures.setObjectName("HeaderLabel")
        metadata_layout.addWidget(self.label_structures)
        self.part_list = QTreeWidget()
        self.part_list.setObjectName("workbenchPartTree")
        self.part_list.setHeaderHidden(True)
        self.part_list.setRootIsDecorated(True)
        self.part_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.part_list.currentItemChanged.connect(self.on_part_selected)
        self.part_list.setFixedHeight(190) 
        metadata_layout.addWidget(self.part_list)
        self.blink_context_status_label = QLabel()
        self.blink_context_status_label.setObjectName("mutedLabel")
        self.blink_context_status_label.setWordWrap(True)
        metadata_layout.addWidget(self.blink_context_status_label)
        
        tax_btn_layout = QHBoxLayout()
        self.btn_add_part = QPushButton("+")
        self.btn_add_part.clicked.connect(self.add_taxonomy_part)
        apply_semantic_button_style(self.btn_add_part, BUTTON_ROLE_NEUTRAL, "font-weight: bold;")
        self.btn_rename_part = QPushButton(tr("Rename Structure", self.current_lang))
        self.btn_rename_part.clicked.connect(self.rename_taxonomy_part)
        apply_semantic_button_style(self.btn_rename_part, BUTTON_ROLE_NEUTRAL, "padding: 4px 8px;")
        self.btn_del_part = QPushButton("-")
        self.btn_del_part.clicked.connect(self.remove_taxonomy_part)
        apply_semantic_button_style(self.btn_del_part, BUTTON_ROLE_DESTRUCTIVE, "font-weight: bold;")
        tax_btn_layout.addWidget(self.btn_add_part)
        tax_btn_layout.addWidget(self.btn_rename_part)
        tax_btn_layout.addWidget(self.btn_del_part)
        metadata_layout.addLayout(tax_btn_layout)
        
        self.check_morpho = QCheckBox() 
        self.check_morpho.stateChanged.connect(self.toggle_morphometrics)
        metadata_layout.addWidget(self.check_morpho)
        self.group_morpho = QGroupBox()
        apply_surface_role(self.group_morpho, SURFACE_ROLE_SUBTLE, "workbenchMorphometricsPanel")
        self.group_morpho.setVisible(False)
        morpho_layout = QVBoxLayout(self.group_morpho)
        self.label_measurements = QLabel("N/A")
        self.label_measurements.setObjectName("mutedLabel")
        morpho_layout.addWidget(self.label_measurements)
        metadata_layout.addWidget(self.group_morpho)
        self.image_taxon_panel = QWidget()
        self.image_taxon_panel.setObjectName("workbenchImageTaxonPanel")
        image_taxon_layout = QVBoxLayout(self.image_taxon_panel)
        image_taxon_layout.setContentsMargins(0, 0, 0, 0)
        image_taxon_layout.setSpacing(6)
        image_taxon_layout.addWidget(self.label_taxonomy)
        image_taxon_layout.addWidget(self.genus_combo)
        metadata_layout.addWidget(self.image_taxon_panel)
        self.description_header_panel = QWidget()
        self.description_header_panel.setObjectName("workbenchDescriptionHeader")
        description_header = QHBoxLayout(self.description_header_panel)
        description_header.setContentsMargins(0, 0, 0, 0)
        description_header.setSpacing(8)
        self.btn_literature_descriptions = QPushButton()
        self.btn_literature_descriptions.setObjectName("workbenchLiteratureDescriptionButton")
        self.btn_literature_descriptions.clicked.connect(self.open_literature_description_dialog)
        apply_semantic_button_style(self.btn_literature_descriptions, BUTTON_ROLE_NEUTRAL, "padding: 4px 8px;")
        description_header.addWidget(self.btn_literature_descriptions)
        self.label_description = QLabel()
        self.label_description.setObjectName("HeaderLabel")
        description_header.addWidget(self.label_description)
        description_header.addStretch()
        metadata_layout.addWidget(self.description_header_panel)
        self.desc_box = QTextEdit()
        self.desc_box.setMaximumHeight(100)
        self.desc_box.setObjectName("LinkedDescriptionBox")
        metadata_layout.addWidget(self.desc_box)
        right_layout.addWidget(self.metadata_panel)

        self.ai_panel = QWidget()
        apply_surface_role(self.ai_panel, SURFACE_ROLE_PANEL, "workbenchAIPanel")
        ai_layout = QVBoxLayout(self.ai_panel)
        ai_layout.setContentsMargins(12, 12, 12, 12)
        ai_layout.setSpacing(10)
        self.label_ai_workflow = QLabel()
        self.label_ai_workflow.setObjectName("HeaderLabel")
        ai_layout.addWidget(self.label_ai_workflow)

        self.label_model_backend = QLabel()
        self.label_model_backend.setObjectName("mutedLabel")
        ai_layout.addWidget(self.label_model_backend)

        self.parent_annotation_panel = QWidget()
        apply_surface_role(self.parent_annotation_panel, SURFACE_ROLE_RAISED, "workbenchParentAnnotationPanel")
        parent_annotation_layout = QVBoxLayout(self.parent_annotation_panel)
        parent_annotation_layout.setContentsMargins(10, 10, 10, 10)
        parent_annotation_layout.setSpacing(8)
        self.label_parent_annotation = QLabel()
        self.label_parent_annotation.setObjectName("HeaderLabel")
        parent_annotation_layout.addWidget(self.label_parent_annotation)

        # --- Model Selection Area (Decoupled) ---
        self.ai_model_panel = QWidget()
        self.ai_model_panel.setObjectName("workbenchAIModelPanel")
        models_form = QGridLayout(self.ai_model_panel)
        models_form.setContentsMargins(0, 0, 0, 0)
        models_form.setHorizontalSpacing(8)
        models_form.setVerticalSpacing(5)
        models_form.setColumnStretch(1, 1)
        
        # Locator Selection
        self.lbl_locator = QLabel("Locator:")
        models_form.addWidget(self.lbl_locator, 0, 0)
        self.combo_locator = NoWheelComboBox()
        self.combo_locator.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_locator.activated.connect(self.on_locator_changed)
        self.combo_locator.currentIndexChanged.connect(self.update_model_delete_button_states)
        models_form.addWidget(self.combo_locator, 0, 1)
        
        self.btn_del_locator = QPushButton("Del")
        self.btn_del_locator.setEnabled(False)
        self.btn_del_locator.clicked.connect(self.delete_locator_model)
        apply_semantic_button_style(self.btn_del_locator, BUTTON_ROLE_DESTRUCTIVE)
        self.btn_note_locator = QPushButton("Note")
        self.btn_note_locator.setEnabled(False)
        self.btn_note_locator.clicked.connect(self.edit_locator_model_note)
        apply_semantic_button_style(self.btn_note_locator, BUTTON_ROLE_NEUTRAL)
        models_form.addWidget(self.btn_note_locator, 0, 2)
        models_form.addWidget(self.btn_del_locator, 0, 3)
        
        # Segmenter Selection
        self.lbl_segmenter = QLabel("Segmenter:")
        models_form.addWidget(self.lbl_segmenter, 1, 0)
        self.combo_segmenter = NoWheelComboBox()
        self.combo_segmenter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_segmenter.activated.connect(self.on_segmenter_changed)
        self.combo_segmenter.currentIndexChanged.connect(self.update_model_delete_button_states)
        models_form.addWidget(self.combo_segmenter, 1, 1)
        
        self.btn_del_segmenter = QPushButton("Del")
        self.btn_del_segmenter.setEnabled(False)
        self.btn_del_segmenter.clicked.connect(self.delete_segmenter_model)
        apply_semantic_button_style(self.btn_del_segmenter, BUTTON_ROLE_DESTRUCTIVE)
        self.btn_note_segmenter = QPushButton("Note")
        self.btn_note_segmenter.setEnabled(False)
        self.btn_note_segmenter.clicked.connect(self.edit_segmenter_model_note)
        apply_semantic_button_style(self.btn_note_segmenter, BUTTON_ROLE_NEUTRAL)
        models_form.addWidget(self.btn_note_segmenter, 1, 2)
        models_form.addWidget(self.btn_del_segmenter, 1, 3)
        
        parent_annotation_layout.addWidget(self.ai_model_panel)

        self.ai_action_panel = QWidget()
        self.ai_action_panel.setObjectName("workbenchAIActionPanel")
        ai_action_layout = QVBoxLayout(self.ai_action_panel)
        ai_action_layout.setContentsMargins(0, 0, 0, 0)
        ai_action_layout.setSpacing(8)

        btns_layout = QHBoxLayout()
        self.btn_predict = QPushButton()
        self.btn_predict.clicked.connect(self.run_prediction)
        apply_semantic_button_style(self.btn_predict, BUTTON_ROLE_RUN, "padding: 5px;")
        btns_layout.addWidget(self.btn_predict)
        self.btn_batch = QPushButton()
        self.btn_batch.clicked.connect(self.run_batch_inference)
        apply_semantic_button_style(self.btn_batch, BUTTON_ROLE_RUN, "padding: 5px;")
        btns_layout.addWidget(self.btn_batch)
        ai_action_layout.addLayout(btns_layout)
        self.btn_accept_current_ai_drafts = QPushButton()
        self.btn_accept_current_ai_drafts.clicked.connect(self.accept_current_image_ai_drafts)
        apply_semantic_button_style(self.btn_accept_current_ai_drafts, BUTTON_ROLE_COMMIT, "padding: 6px;")
        ai_action_layout.addWidget(self.btn_accept_current_ai_drafts)
        self.btn_accept_batch_ai_drafts = QPushButton()
        self.btn_accept_batch_ai_drafts.clicked.connect(self.accept_batch_ai_drafts)
        apply_semantic_button_style(self.btn_accept_batch_ai_drafts, BUTTON_ROLE_COMMIT, "padding: 6px;")
        ai_action_layout.addWidget(self.btn_accept_batch_ai_drafts)
        self.chk_train_locator_only = QCheckBox()
        self.chk_train_locator_only.setToolTip(
            tr(
                "Skip SAM/parts training for this run. Useful when the base SAM result is already good enough.",
                self.current_lang,
            )
        )
        ai_action_layout.addWidget(self.chk_train_locator_only)
        train_scope_row = QHBoxLayout()
        train_scope_row.setContentsMargins(0, 0, 0, 0)
        train_scope_row.setSpacing(8)
        self.lbl_training_scope = QLabel()
        self.lbl_training_scope.setObjectName("mutedLabel")
        train_scope_row.addWidget(self.lbl_training_scope)
        self.combo_training_scope = NoWheelComboBox()
        self.combo_training_scope.setObjectName("workbenchTrainingScopeCombo")
        self.combo_training_scope.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        train_scope_row.addWidget(self.combo_training_scope, 1)
        ai_action_layout.addLayout(train_scope_row)

        train_buttons_layout = QHBoxLayout()
        self.btn_train = QPushButton()
        self.btn_train.clicked.connect(self.run_training)
        apply_semantic_button_style(self.btn_train, BUTTON_ROLE_RUN, "padding: 8px; margin-top: 5px;")
        train_buttons_layout.addWidget(self.btn_train, 3)
        self.btn_stop_training = QPushButton()
        self.btn_stop_training.setEnabled(False)
        self.btn_stop_training.clicked.connect(self.stop_training)
        apply_semantic_button_style(self.btn_stop_training, BUTTON_ROLE_STOP, "padding: 8px; margin-top: 5px;")
        train_buttons_layout.addWidget(self.btn_stop_training, 2)
        ai_action_layout.addLayout(train_buttons_layout)
        self.btn_clear_ai = QPushButton()
        self.btn_clear_ai.clicked.connect(self.clear_ai_labels)
        apply_semantic_button_style(self.btn_clear_ai, BUTTON_ROLE_DESTRUCTIVE, "font-weight: bold; margin-top: 5px;")
        ai_action_layout.addWidget(self.btn_clear_ai)
        parent_annotation_layout.addWidget(self.ai_action_panel)
        ai_layout.addWidget(self.parent_annotation_panel)

        self.blink_refine_panel = QWidget()
        apply_surface_role(self.blink_refine_panel, SURFACE_ROLE_RAISED, "workbenchBlinkRefinePanel")
        blink_refine_layout = QVBoxLayout(self.blink_refine_panel)
        blink_refine_layout.setContentsMargins(10, 10, 10, 10)
        blink_refine_layout.setSpacing(8)
        self.label_blink_refine = QLabel()
        self.label_blink_refine.setObjectName("HeaderLabel")
        blink_refine_layout.addWidget(self.label_blink_refine)
        self.label_blink_route = QLabel()
        self.label_blink_route.setObjectName("mutedLabel")
        self.label_blink_route.setWordWrap(True)
        blink_refine_layout.addWidget(self.label_blink_route)
        self.label_blink_parent_context = QLabel()
        self.label_blink_parent_context.setObjectName("mutedLabel")
        blink_refine_layout.addWidget(self.label_blink_parent_context)
        self.combo_blink_parent_context = NoWheelComboBox()
        self.combo_blink_parent_context.activated.connect(self.on_blink_parent_context_changed)
        blink_refine_layout.addWidget(self.combo_blink_parent_context)
        self.label_blink_parent_box = QLabel()
        self.label_blink_parent_box.setObjectName("mutedLabel")
        self.label_blink_parent_box.setWordWrap(True)
        blink_refine_layout.addWidget(self.label_blink_parent_box)
        self.label_blink_expert = QLabel()
        self.label_blink_expert.setObjectName("mutedLabel")
        self.label_blink_expert.setWordWrap(True)
        blink_refine_layout.addWidget(self.label_blink_expert)
        self.check_lock_parent_box_ratio = QCheckBox()
        self.check_lock_parent_box_ratio.setChecked(False)
        self.check_lock_parent_box_ratio.stateChanged.connect(self._refresh_annotation_box_constraints)
        blink_refine_layout.addWidget(self.check_lock_parent_box_ratio)
        self.btn_configure_route_expert = QPushButton()
        self.btn_configure_route_expert.clicked.connect(self.open_current_route_expert_settings)
        apply_semantic_button_style(self.btn_configure_route_expert, BUTTON_ROLE_NEUTRAL)
        blink_refine_layout.addWidget(self.btn_configure_route_expert)
        self.btn_blink_auto_annotate = QPushButton()
        self.btn_blink_auto_annotate.clicked.connect(self.run_blink_child_auto_annotate)
        apply_semantic_button_style(self.btn_blink_auto_annotate, BUTTON_ROLE_RUN, "padding: 6px;")
        blink_refine_layout.addWidget(self.btn_blink_auto_annotate)
        blink_shrink_buttons = QHBoxLayout()
        blink_shrink_buttons.setContentsMargins(0, 0, 0, 0)
        blink_shrink_buttons.setSpacing(8)
        self.btn_blink_auto_shrink = QPushButton()
        self.btn_blink_auto_shrink.clicked.connect(self.run_blink_auto_shrink)
        apply_semantic_button_style(self.btn_blink_auto_shrink, BUTTON_ROLE_RUN, "padding: 6px;")
        blink_shrink_buttons.addWidget(self.btn_blink_auto_shrink)
        self.btn_blink_batch_auto_shrink = QPushButton()
        self.btn_blink_batch_auto_shrink.clicked.connect(self.run_blink_batch_auto_shrink)
        apply_semantic_button_style(self.btn_blink_batch_auto_shrink, BUTTON_ROLE_RUN, "padding: 6px;")
        blink_shrink_buttons.addWidget(self.btn_blink_batch_auto_shrink)
        blink_refine_layout.addLayout(blink_shrink_buttons)
        blink_train_buttons = QHBoxLayout()
        blink_train_buttons.setContentsMargins(0, 0, 0, 0)
        blink_train_buttons.setSpacing(8)
        self.btn_blink_train_expert = QPushButton()
        self.btn_blink_train_expert.clicked.connect(self.train_current_blink_expert)
        apply_semantic_button_style(self.btn_blink_train_expert, BUTTON_ROLE_RUN, "padding: 6px;")
        blink_train_buttons.addWidget(self.btn_blink_train_expert, 3)
        self.btn_blink_stop_training = QPushButton()
        self.btn_blink_stop_training.setEnabled(False)
        self.btn_blink_stop_training.clicked.connect(self.stop_current_blink_expert_training)
        apply_semantic_button_style(self.btn_blink_stop_training, BUTTON_ROLE_STOP, "padding: 6px;")
        blink_train_buttons.addWidget(self.btn_blink_stop_training, 2)
        blink_refine_layout.addLayout(blink_train_buttons)
        ai_layout.addWidget(self.blink_refine_panel)

        self.training_progress_panel = QWidget()
        apply_surface_role(self.training_progress_panel, SURFACE_ROLE_SUBTLE, "workbenchTrainingProgressPanel")
        training_progress_layout = QVBoxLayout(self.training_progress_panel)
        training_progress_layout.setContentsMargins(10, 10, 10, 10)
        training_progress_layout.setSpacing(6)
        training_progress_header = QHBoxLayout()
        training_progress_header.setContentsMargins(0, 0, 0, 0)
        training_progress_header.setSpacing(8)
        self.label_training_progress = QLabel()
        self.label_training_progress.setObjectName("HeaderLabel")
        self.label_training_progress.setText(tr("Training progress", self.current_lang))
        training_progress_header.addWidget(self.label_training_progress)
        training_progress_header.addStretch()
        self.btn_training_results = QPushButton()
        self.btn_training_results.setObjectName("workbenchTrainingResultsButton")
        self.btn_training_results.clicked.connect(self.open_training_results_browser)
        apply_semantic_button_style(self.btn_training_results, BUTTON_ROLE_NEUTRAL, "padding: 4px 8px;")
        training_progress_header.addWidget(self.btn_training_results)
        training_progress_layout.addLayout(training_progress_header)
        self.label_training_progress_status = QLabel()
        self.label_training_progress_status.setObjectName("mutedLabel")
        self.label_training_progress_status.setWordWrap(True)
        self.label_training_progress_status.setText(tr("No training running.", self.current_lang))
        training_progress_layout.addWidget(self.label_training_progress_status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        training_progress_layout.addWidget(self.progress)
        ai_layout.addWidget(self.training_progress_panel)
        right_layout.addWidget(self.ai_panel)

        self.logs_panel = QWidget()
        apply_surface_role(self.logs_panel, SURFACE_ROLE_SUBTLE, "workbenchLogsPanel")
        logs_layout = QVBoxLayout(self.logs_panel)
        logs_layout.setContentsMargins(12, 12, 12, 12)
        logs_layout.setSpacing(8)
        self.label_logs = QLabel()
        self.label_logs.setObjectName("HeaderLabel")
        logs_layout.addWidget(self.label_logs)
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMinimumHeight(260)
        self.log_console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log_console.setObjectName("MutedLogConsole")
        logs_layout.addWidget(self.log_console, 1)
        right_layout.addWidget(self.logs_panel, 1)
        right_layout.addStretch(0)
        self.workbench_inspector_scroll.setWidget(right_panel)
        self.workbench_splitter.addWidget(self.workbench_inspector_scroll)
        self.workbench_splitter.setStretchFactor(0, 1)
        self.workbench_splitter.setStretchFactor(1, 5)
        self.workbench_splitter.setStretchFactor(2, 2)
        self.workbench_splitter.setSizes([240, 1080, 320])
        self.shell_view = MainWindowViewAdapter(
            show_start_center=self._show_start_center,
            show_tab=self.tabs.setCurrentIndex,
            refresh_project_console=self._refresh_project_console,
            update_agent_status=self._update_start_agent_status,
        )

    def _connect_main_window_integrations(self):
        self.pdf_widget = None
        self.tif_workbench = None
        self.blink_lab = BlinkLabWidget(
            self.engine,
            self.project,
            self.current_lang,
            blink_epochs=self.blink_train_epochs,
            blink_batch=self.blink_train_batch,
            blink_lr=self.blink_train_lr,
            blink_weight_decay=self.blink_train_weight_decay,
            blink_input_size=self.blink_train_input_size,
            blink_auto_shrink_steps=self.blink_auto_shrink_steps,
            blink_training_strategy=self.blink_training_strategy,
            runtime_device=self.runtime_device,
        )
        self.shell_signal_router.connect_once(
            "blink.start_center",
            self.blink_lab.start_center_requested,
            self.shell_coordinator.return_to_start,
        )
        self.shell_signal_router.connect_once(
            "blink.agent",
            self.blink_lab.agent_requested,
            self.shell_coordinator.open_agent,
        )
        self.shell_signal_router.connect_once(
            "blink.labels_updated",
            self.blink_lab.global_labels_updated,
            self.on_global_labels_updated,
        )
        self.shell_signal_router.connect_once(
            "blink.route_refresh",
            self.blink_lab.route_registry_refresh_requested,
            self.refresh_route_table,
        )
        self.route_settings_panel = RouteManagementPanel(self, self.current_lang)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _ensure_pdf_widget(self):
        if self.pdf_widget is not None:
            return self.pdf_widget
        widget_factory = getattr(self, "_pdf_widget_factory", None)
        if widget_factory is None:
            try:
                from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget
            except ImportError:
                from ui.pdf_processing_widget import PdfProcessingWidget
            widget_factory = PdfProcessingWidget
        self.pdf_widget = widget_factory(self.current_lang)
        self.shell_signal_router.connect_once(
            "pdf.start_center",
            self.pdf_widget.start_center_requested,
            self.shell_coordinator.return_to_start,
        )
        self.shell_signal_router.connect_once(
            "pdf.agent",
            self.pdf_widget.agent_requested,
            self.shell_coordinator.open_agent,
        )
        if hasattr(self.pdf_widget, "set_theme"):
            self.pdf_widget.set_theme(self.current_theme)
        return self.pdf_widget

    def _ensure_tif_workbench(self):
        if self.tif_workbench is not None:
            return self.tif_workbench
        widget_factory = getattr(self, "_tif_workbench_factory", None)
        if widget_factory is None:
            try:
                from AntSleap.ui.tif_workbench import TifWorkbenchWidget
            except ImportError:
                from ui.tif_workbench import TifWorkbenchWidget
            widget_factory = TifWorkbenchWidget
        self.tif_workbench = widget_factory(self.tif_project, self.current_lang, config_manager=self.config)
        self.shell_signal_router.connect_once(
            "tif.start_center",
            self.tif_workbench.start_center_requested,
            self.shell_coordinator.return_to_start,
        )
        self.shell_signal_router.connect_once(
            "tif.agent",
            self.tif_workbench.agent_requested,
            self.shell_coordinator.open_agent,
        )
        if hasattr(self.tif_workbench, "set_theme"):
            self.tif_workbench.set_theme(self.current_theme)
        return self.tif_workbench

    def _finish_main_window_startup(self):
        self._open_or_create_startup_project()
        self.active_project_entry_path = self.project.current_project_path or ""
        self.active_project_kind = "start"
        if self.config.get("startup_behavior", "start_center") == "continue_last" and self.config.get("last_project_path", ""):
            self.open_last_project()
            if self.active_project_kind == "start":
                self._show_start_center()
        else:
            self._show_start_center()
        self.log(tr("System Initialized.", self.current_lang))
        self.refresh_model_list()
        self.refresh_ui()
        self.refresh_route_table()
        self.change_theme(self.current_theme)
        self.apply_startup_window_geometry()
