try:
    from AntSleap.ui.main_window_shell_dependencies import *
except ImportError:
    from ui.main_window_shell_dependencies import *


class MainWindowStartCenterMixin:
    def _is_tif_workflow_enabled(self):
        return bool(getattr(self, "tif_workflow_enabled", False))

    def _show_tif_workflow_unavailable(self):
        QMessageBox.information(
            self,
            tr("TIF Volume Workbench", self.current_lang),
            (
                "The experimental TIF workflow is hidden in the public build. "
                f"Set {EXPERIMENTAL_TIF_WORKFLOW_ENV}=1 before starting TaxaMask to enable it for local development."
            ),
        )

    def _apply_window_icon(self):
        for icon_path in (APP_ICON_PATH, APP_ICON_FALLBACK_PATH):
            if icon_path and os.path.exists(icon_path):
                icon = QIcon(icon_path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    app = QApplication.instance()
                    if app is not None:
                        app.setWindowIcon(icon)
                    return

    def apply_startup_window_geometry(self):
        if QApplication.platformName() == "offscreen":
            return

        app = QApplication.instance()
        if app is None:
            return

        screen = app.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        x, y, width, height = compute_centered_window_geometry(
            (available.left(), available.top(), available.width(), available.height()),
            (self.startup_size.width(), self.startup_size.height()),
        )
        self.setGeometry(x, y, width, height)

    def _build_start_center(self):
        page = QWidget()
        page.setObjectName("startCenterPage")
        outer_layout = QHBoxLayout(page)
        outer_layout.setContentsMargins(24, 22, 24, 22)
        outer_layout.setSpacing(18)

        agent_area = QWidget()
        agent_area.setObjectName("startCenterAgentMain")
        agent_layout = QVBoxLayout(agent_area)
        agent_layout.setContentsMargins(0, 0, 0, 0)
        agent_layout.setSpacing(14)

        self.agent_panel = TaxaMaskAgentPanel(self.current_lang)
        self.agent_panel.status_changed.connect(self._handle_agent_dashboard_status_changed)

        header = QWidget()
        apply_surface_role(header, SURFACE_ROLE_PANEL, "startCenterHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 14)
        header_layout.setSpacing(14)

        header_text = QWidget()
        header_text_layout = QVBoxLayout(header_text)
        header_text_layout.setContentsMargins(0, 0, 0, 0)
        header_text_layout.setSpacing(6)
        self.start_title = QLabel()
        self.start_title.setObjectName("startCenterTitle")
        self.start_subtitle = QLabel()
        self.start_subtitle.setObjectName("mutedLabel")
        self.start_subtitle.setWordWrap(True)
        header_text_layout.addWidget(self.start_title)
        header_text_layout.addWidget(self.start_subtitle)
        header_layout.addWidget(header_text, 1)

        header_controls = QWidget()
        header_controls.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        header_controls_layout = QVBoxLayout(header_controls)
        header_controls_layout.setContentsMargins(0, 0, 0, 0)
        header_controls_layout.setSpacing(6)
        self.start_agent_status_label = QLabel()
        self.start_agent_status_label.setObjectName("mutedLabel")
        self.start_agent_status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.start_agent_status_label.setWordWrap(False)
        header_controls_layout.addWidget(self.start_agent_status_label)
        header_button_layout = QHBoxLayout()
        header_button_layout.setContentsMargins(0, 0, 0, 0)
        header_button_layout.setSpacing(8)
        self.btn_start_ant_code = QPushButton()
        self.btn_start_ant_code.setObjectName("startCenterStartAntCodeButton")
        self.btn_start_ant_code.clicked.connect(self.agent_panel.start_dashboard)
        self.btn_stop_ant_code = QPushButton()
        self.btn_stop_ant_code.setObjectName("startCenterStopAntCodeButton")
        self.btn_stop_ant_code.clicked.connect(self.agent_panel.stop_dashboard)
        button_extras = "padding: 5px 10px;"
        apply_semantic_button_style(self.btn_start_ant_code, BUTTON_ROLE_RUN, button_extras)
        apply_semantic_button_style(self.btn_stop_ant_code, BUTTON_ROLE_STOP, button_extras)
        header_button_layout.addWidget(self.btn_start_ant_code)
        header_button_layout.addWidget(self.btn_stop_ant_code)
        header_controls_layout.addLayout(header_button_layout)
        header_layout.addWidget(header_controls, 0, Qt.AlignTop | Qt.AlignRight)
        agent_layout.addWidget(header)

        agent_layout.addWidget(self.agent_panel, 1)
        outer_layout.addWidget(agent_area, 1)

        workflow_rail_scroll = QScrollArea()
        workflow_rail_scroll.setObjectName("startWorkflowRailScroll")
        workflow_rail_scroll.setWidgetResizable(True)
        workflow_rail_scroll.setFrameShape(QFrame.NoFrame)
        workflow_rail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        workflow_rail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        workflow_rail_scroll.setMinimumWidth(360)
        workflow_rail_scroll.setMaximumWidth(410)
        workflow_rail_scroll.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        workflow_rail = QWidget()
        workflow_rail.setObjectName("startWorkflowRail")
        workflow_rail.setMinimumWidth(340)
        workflow_rail.setMaximumWidth(390)
        rail_layout = QVBoxLayout(workflow_rail)
        rail_layout.setContentsMargins(0, 0, 0, 0)
        rail_layout.setSpacing(14)
        self.start_console_panel = self._build_project_console()
        rail_layout.addWidget(self.start_console_panel)
        self.start_quick_panel = self._build_start_quick_panel()
        rail_layout.addWidget(self.start_quick_panel)
        self.start_image_card = self._build_workflow_card(
            "start2DWorkflowCard",
            "2D / STL morphology annotation",
            "Annotate high-resolution 2D views rendered from STL, or ordinary 2D morphology images, then train Locator/SAM/Blink models.",
            "Enter 2D/STL workflow",
            self.shell_coordinator.enter_image,
            "Create 2D/STL project",
            self.new_project,
        )
        self.start_tif_card = None
        if self._is_tif_workflow_enabled():
            self.start_tif_card = self._build_workflow_card(
                "startTifWorkflowCard",
                "TIF volume annotation",
                "Annotate continuous slice volumes with material IDs, export train-ready volumes, and call TIF segmentation backends.",
                "Enter TIF workflow",
                self.shell_coordinator.enter_tif,
                "Create TIF project",
                self.new_tif_project,
            )
        self.start_pdf_card = self._build_workflow_card(
            "startPdfEvidenceCard",
            "PDF evidence workflow",
            "Use Agent first to confirm the target taxon, screening rules, figure extraction scope, evidence indexes, candidate review, and safe import.",
            "Plan PDF workflow with Agent",
            self.open_agent_for_pdf_workflow,
            "Open PDF tools",
            self.open_pdf_evidence_tools,
        )
        rail_layout.addWidget(self.start_pdf_card)
        rail_layout.addWidget(self.start_image_card)
        if self.start_tif_card is not None:
            rail_layout.addWidget(self.start_tif_card)
        rail_layout.addStretch(1)
        workflow_rail_scroll.setWidget(workflow_rail)
        outer_layout.addWidget(workflow_rail_scroll, 0)
        return page

    def _build_start_quick_panel(self):
        panel = QWidget()
        apply_surface_role(panel, SURFACE_ROLE_SUBTLE, "startCenterQuickPanel")
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        self.start_recent_label = QLabel()
        self.start_recent_label.setObjectName("mutedLabel")
        self.start_recent_label.setWordWrap(True)
        self.start_recent_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.btn_continue_last = QPushButton()
        self.btn_continue_last.clicked.connect(self.open_last_project)
        apply_semantic_button_style(self.btn_continue_last, BUTTON_ROLE_COMMIT)
        self.btn_open_any = QPushButton()
        self.btn_open_any.clicked.connect(self.open_project)
        apply_semantic_button_style(self.btn_open_any, BUTTON_ROLE_NEUTRAL)
        self.btn_general_settings = QPushButton()
        self.btn_general_settings.clicked.connect(self.open_general_settings)
        apply_semantic_button_style(self.btn_general_settings, BUTTON_ROLE_NEUTRAL)
        layout.addWidget(self.start_recent_label)
        layout.addWidget(self.btn_continue_last)
        layout.addWidget(self.btn_open_any)
        layout.addWidget(self.btn_general_settings)
        return panel

    def _build_project_console(self):
        panel = QWidget()
        apply_surface_role(panel, SURFACE_ROLE_SUBTLE, "startProjectConsole")
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        self.start_console_title = QLabel()
        self.start_console_title.setObjectName("startProjectConsoleTitle")
        self.start_console_summary = QLabel()
        self.start_console_summary.setObjectName("mutedLabel")
        self.start_console_summary.setWordWrap(False)
        self.start_console_summary.setMinimumWidth(0)
        self.start_console_summary.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        title_layout.addWidget(self.start_console_title)
        title_layout.addWidget(self.start_console_summary)
        header_layout.addLayout(title_layout, 1)
        self.btn_start_console_toggle = QPushButton()
        self.btn_start_console_toggle.setObjectName("startProjectConsoleToggleButton")
        self.btn_start_console_toggle.clicked.connect(self._toggle_start_project_console)
        apply_semantic_button_style(self.btn_start_console_toggle, BUTTON_ROLE_NEUTRAL, "padding: 3px 8px; min-width: 34px;")
        header_layout.addWidget(self.btn_start_console_toggle, 0, Qt.AlignTop | Qt.AlignRight)
        layout.addWidget(header)

        self.start_console_body = QWidget()
        self.start_console_body.setObjectName("startProjectConsoleBody")
        body_layout = QVBoxLayout(self.start_console_body)
        body_layout.setContentsMargins(0, 2, 0, 0)
        body_layout.setSpacing(5)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        self.start_console_workflow_label, self.start_console_workflow_value = self._build_project_console_row(
            grid, 0, "startConsoleWorkflowValue"
        )
        self.start_console_project_label, self.start_console_project_value = self._build_project_console_row(
            grid, 1, "startConsoleProjectValue"
        )
        self.start_console_images_label, self.start_console_images_value = self._build_project_console_row(
            grid, 2, "startConsoleImagesValue"
        )
        if self._is_tif_workflow_enabled():
            self.start_console_tif_label, self.start_console_tif_value = self._build_project_console_row(
                grid, 3, "startConsoleTifValue"
            )
        else:
            self.start_console_tif_label = None
            self.start_console_tif_value = None
        self.start_console_pdf_label, self.start_console_pdf_value = self._build_project_console_row(
            grid, 4 if self._is_tif_workflow_enabled() else 3, "startConsolePdfValue"
        )
        self.start_console_agent_label, self.start_console_agent_value = self._build_project_console_row(
            grid, 5 if self._is_tif_workflow_enabled() else 4, "startConsoleAgentValue"
        )
        grid.setColumnStretch(1, 1)
        body_layout.addLayout(grid)

        self.start_console_stl_note = QLabel()
        self.start_console_stl_note.setObjectName("mutedLabel")
        self.start_console_stl_note.setWordWrap(True)
        body_layout.addWidget(self.start_console_stl_note)
        layout.addWidget(self.start_console_body)
        self.start_console_expanded = False
        self.start_console_body.setVisible(False)
        return panel

    def _toggle_start_project_console(self):
        self.start_console_expanded = not bool(getattr(self, "start_console_expanded", False))
        self._update_start_project_console_collapsed_state()

    def _update_start_project_console_collapsed_state(self):
        if not hasattr(self, "start_console_body"):
            return
        expanded = bool(getattr(self, "start_console_expanded", False))
        self.start_console_body.setVisible(expanded)
        if hasattr(self, "btn_start_console_toggle"):
            self.btn_start_console_toggle.setText("−" if expanded else "+")
            self.btn_start_console_toggle.setToolTip(
                tr("Collapse Project Console", self.current_lang)
                if expanded
                else tr("Expand Project Console", self.current_lang)
            )

    def _build_project_console_row(self, grid, row, value_object_name):
        label = QLabel()
        label.setObjectName("mutedLabel")
        label.setMinimumWidth(92)
        value = QLabel()
        value.setObjectName(value_object_name)
        value.setProperty("consoleValue", True)
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        grid.addWidget(label, row, 0)
        grid.addWidget(value, row, 1)
        return label, value

    def _build_workflow_card(self, object_name, title_key, description_key, enter_key, enter_callback, create_key, create_callback):
        card = QFrame()
        card.setObjectName(object_name)
        card.setFrameShape(QFrame.NoFrame)
        card.setProperty("surfaceRole", SURFACE_ROLE_PANEL)
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setMinimumHeight(230)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        title = QLabel()
        title.setObjectName("startWorkflowTitle")
        title.setProperty("textKey", title_key)
        title.setWordWrap(True)
        description = QLabel()
        description.setObjectName("mutedLabel")
        description.setWordWrap(True)
        description.setProperty("textKey", description_key)
        enter_button = QPushButton()
        enter_button.setProperty("textKey", enter_key)
        enter_button.clicked.connect(enter_callback)
        apply_semantic_button_style(enter_button, BUTTON_ROLE_RUN, "padding: 10px; font-weight: bold;")
        create_button = QPushButton()
        create_button.setProperty("textKey", create_key)
        create_button.clicked.connect(create_callback)
        apply_semantic_button_style(create_button, BUTTON_ROLE_NEUTRAL)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addStretch(1)
        layout.addWidget(enter_button)
        layout.addWidget(create_button)
        return card

    def _show_start_center(self):
        active_kind = getattr(self, "active_project_kind", "start")
        if active_kind in {"image", "tif"}:
            self.last_workbench_kind = active_kind
        self.active_project_kind = "start"
        self._apply_project_mode_tabs()
        self._update_start_center_texts()

    def _update_start_center_texts(self):
        if not hasattr(self, "start_center_widget"):
            return
        self.start_title.setText(tr("TaxaMask Agent Center", self.current_lang))
        self.start_subtitle.setText(
            tr(
                "Ask Ant-Code to configure workflows, inspect errors, prepare PDF evidence, or plan training. Use the right rail when you want to enter a workbench directly.",
                self.current_lang,
            )
        )
        last_project = self.config.get("last_project_path", "")
        if last_project and os.path.exists(last_project):
            self.start_recent_label.setText(
                f"{tr('Continue last project', self.current_lang)}\n{self._compact_project_path(last_project)}"
            )
            self.start_recent_label.setToolTip(os.path.abspath(last_project))
            self.btn_continue_last.setEnabled(True)
        else:
            self.start_recent_label.setText(tr("No recent project", self.current_lang))
            self.start_recent_label.setToolTip("")
            self.btn_continue_last.setEnabled(False)
        self.btn_continue_last.setText(tr("Continue last project", self.current_lang))
        self.btn_open_any.setText(tr("Open any project", self.current_lang))
        self.btn_general_settings.setText(tr("General Settings", self.current_lang))
        if hasattr(self, "btn_start_ant_code"):
            self.btn_start_ant_code.setText(tr("Start Ant-Code", self.current_lang))
            self.btn_stop_ant_code.setText(tr("Stop Ant-Code", self.current_lang))
        self._refresh_project_console()
        if hasattr(self, "create_menus"):
            self.create_menus()
        for label in self.start_center_widget.findChildren(QLabel):
            key = label.property("textKey")
            if key:
                label.setText(tr(str(key), self.current_lang))
        for button in self.start_center_widget.findChildren(QPushButton):
            key = button.property("textKey")
            if key:
                button.setText(tr(str(key), self.current_lang))
        if hasattr(self, "agent_panel"):
            self.agent_panel.set_language(self.current_lang)
            self.agent_panel.update_runtime_status(
                model_status=tr("Local task cards", self.current_lang),
                workflow=self._agent_current_workflow_label(),
                project=self._agent_current_project_label(),
                state=tr("Idle", self.current_lang),
            )
            self._update_start_agent_status(self.agent_panel.status_text())
            self._refresh_project_console()

    def _handle_agent_dashboard_status_changed(self, status):
        self._update_start_agent_status(status)
        self._refresh_project_console()

    def _update_start_agent_status(self, status=None):
        if not hasattr(self, "start_agent_status_label"):
            return
        panel = getattr(self, "agent_panel", None)
        text = str(status or (panel.status_text() if panel is not None else "") or "").strip()
        if not text:
            text = self._start_console_agent_status()
        max_len = 72
        display = text if len(text) <= max_len else f"{text[: max_len - 1]}..."
        self.start_agent_status_label.setText(tr("Agent status: {0}", self.current_lang).format(display))
        self.start_agent_status_label.setToolTip(text)

    def _refresh_project_console(self):
        if not hasattr(self, "start_console_title"):
            return
        self.start_console_title.setText(tr("Project Console", self.current_lang))
        self.start_console_workflow_label.setText(tr("Current workflow", self.current_lang))
        self.start_console_project_label.setText(tr("Current project", self.current_lang))
        self.start_console_images_label.setText(tr("2D/STL images", self.current_lang))
        if self._is_tif_workflow_enabled() and self.start_console_tif_label is not None:
            self.start_console_tif_label.setText(tr("TIF specimens", self.current_lang))
        self.start_console_pdf_label.setText(tr("PDF evidence", self.current_lang))
        self.start_console_agent_label.setText("Ant-Code")

        self.start_console_workflow_value.setText(self._agent_current_workflow_label())
        project_summary, project_detail = self._start_console_project_summary()
        image_summary, image_detail = self._start_console_image_summary()
        tif_summary, tif_detail = (
            self._start_console_tif_summary()
            if self._is_tif_workflow_enabled()
            else ("", "")
        )
        pdf_summary, pdf_detail = self._start_console_pdf_summary()
        agent_summary = self._start_console_agent_status()
        summary = self._start_console_collapsed_summary(project_summary, agent_summary)
        self.start_console_summary.setText(summary)
        self.start_console_summary.setToolTip(f"{project_summary}\n{agent_summary}".strip())
        self.start_console_project_value.setText(project_summary)
        self.start_console_images_value.setText(image_summary)
        if self._is_tif_workflow_enabled() and self.start_console_tif_value is not None:
            self.start_console_tif_value.setText(tif_summary)
        self.start_console_pdf_value.setText(pdf_summary)
        self.start_console_agent_value.setText(agent_summary)
        self.start_console_workflow_value.setToolTip(self._agent_current_workflow_label())
        self.start_console_project_value.setToolTip(project_detail)
        self.start_console_images_value.setToolTip(image_detail)
        if self._is_tif_workflow_enabled() and self.start_console_tif_value is not None:
            self.start_console_tif_value.setToolTip(tif_detail)
        self.start_console_pdf_value.setToolTip(pdf_detail)
        self.start_console_agent_value.setToolTip(agent_summary)
        self.start_console_stl_note.setText(
            tr(
                "STL source stays as exported high-resolution 2D views; TaxaMask does not label 3D meshes.",
                self.current_lang,
            )
        )
        self._update_start_project_console_collapsed_state()

    def _start_console_collapsed_summary(self, project_summary, agent_summary):
        project_text = str(project_summary or "").replace("\n", " ").strip()
        agent_text = str(agent_summary or "").replace("\n", " ").strip()
        if len(project_text) > 34:
            project_text = f"{project_text[:33]}..."
        if len(agent_text) > 26:
            agent_text = f"{agent_text[:25]}..."
        return " · ".join([item for item in (project_text, agent_text) if item])

    def _start_console_project_summary(self):
        kind = getattr(self, "active_project_kind", "start")
        source_kind = getattr(self, "active_project_source_kind", kind)
        if kind == "tif":
            path = getattr(self.tif_project, "current_project_path", "") or ""
            if path:
                return tr("TIF project: {0}", self.current_lang).format(self._compact_project_path(path)), os.path.abspath(path)
            return tr("No active project", self.current_lang), ""
        if kind == "image":
            path = self._active_recent_project_path() or getattr(self.project, "current_project_path", "") or ""
            if source_kind == "stl":
                if path:
                    return tr("STL rendered-view project: {0}", self.current_lang).format(self._compact_project_path(path)), os.path.abspath(path)
                return tr("No active project", self.current_lang), ""
            if path:
                return tr("2D project: {0}", self.current_lang).format(self._compact_project_path(path)), os.path.abspath(path)
            return tr("No active project", self.current_lang), ""

        last_project = self.config.get("last_project_path", "") or ""
        if last_project:
            return tr("Recent project: {0}", self.current_lang).format(self._compact_project_path(last_project)), os.path.abspath(last_project)
        return tr("Repository only; no research project selected", self.current_lang), REPO_ROOT

    def _compact_project_path(self, path):
        text = str(path or "").strip()
        if not text:
            return ""
        name = os.path.basename(os.path.normpath(text))
        parent = os.path.basename(os.path.dirname(os.path.normpath(text)))
        display = f"{parent}/{name}" if parent else name
        max_chars = 48
        if len(display) <= max_chars:
            return display
        keep_left = 18
        keep_right = max(12, max_chars - keep_left - 3)
        return f"{display[:keep_left]}...{display[-keep_right:]}"

    def _start_console_image_summary(self):
        images = list((self.project.project_data or {}).get("images", []))
        labels = (self.project.project_data or {}).get("labels", {})
        labeled_count = 0
        stl_count = 0
        for image_path in images:
            entry = labels.get(image_path, {}) if isinstance(labels, dict) else {}
            if isinstance(entry, dict) and entry.get("parts"):
                labeled_count += 1
            provenance = self.project.get_image_provenance(image_path)
            if provenance.get("source_type") == "stl_rendered_view":
                stl_count += 1
        summary = tr("{0} image(s), {1} labeled, {2} STL rendered 2D view(s)", self.current_lang).format(
            len(images),
            labeled_count,
            stl_count,
        )
        detail = tr("2D/STL images", self.current_lang) + f": {len(images)}; labeled: {labeled_count}; STL rendered 2D views: {stl_count}"
        return summary, detail

    def _start_console_tif_summary(self):
        specimens = list((self.tif_project.project_data or {}).get("specimens", []))
        manual_truth_count = 0
        for specimen in specimens:
            manual = ((specimen.get("labels") or {}) if isinstance(specimen, dict) else {}).get("manual_truth") or {}
            if manual.get("path"):
                manual_truth_count += 1
        try:
            train_ready_count = len(self.tif_project.list_train_ready_specimens())
        except Exception:
            train_ready_count = sum(
                1
                for specimen in specimens
                if isinstance(specimen, dict) and (specimen.get("train_ready") or specimen.get("review_status") == "train_ready")
            )
        summary = tr("{0} specimen(s), {1} train-ready, {2} with manual_truth", self.current_lang).format(
            len(specimens),
            train_ready_count,
            manual_truth_count,
        )
        detail = tr("TIF specimens", self.current_lang) + f": {len(specimens)}; train-ready: {train_ready_count}; manual_truth: {manual_truth_count}"
        return summary, detail

    def _start_console_pdf_summary(self):
        skill_path = os.path.join(REPO_ROOT, ".lab-agent", "skills", "taxamask-pdf-evidence", "SKILL.md")
        if not os.path.exists(skill_path):
            return tr("PDF evidence skill missing", self.current_lang), skill_path
        candidates = 0
        for image_path in (self.project.project_data or {}).get("images", []):
            provenance = self.project.get_image_provenance(image_path)
            if self._is_pdf_candidate_provenance(provenance):
                entry = (self.project.project_data or {}).get("labels", {}).get(image_path, {})
                if not isinstance(entry, dict) or entry.get("status") != "labeled":
                    candidates += 1
        summary = tr("PDF evidence skill ready; {0} review candidate(s)", self.current_lang).format(candidates)
        detail = f"{summary}\n{skill_path}"
        return summary, detail

    def _is_pdf_candidate_provenance(self, provenance):
        if not isinstance(provenance, dict):
            return False
        source_type = str(provenance.get("source_type", "") or "").strip()
        return source_type in {"pdf_candidate", "pdf_candidate_crop"}

    def _start_console_agent_status(self):
        panel = getattr(self, "agent_panel", None)
        if panel is None or not panel.is_running():
            return tr("Ant-Code stopped", self.current_lang)
        return tr("Ant-Code ready", self.current_lang)

    def _agent_current_workflow_label(self):
        kind = getattr(self, "active_project_kind", "start")
        if kind == "tif":
            return tr("TIF Volume Workflow", self.current_lang)
        if kind == "image":
            return tr("2D/STL Morphology Workflow", self.current_lang)
        return tr("Start Center", self.current_lang)

    def _agent_current_project_label(self):
        if getattr(self, "active_project_kind", "start") == "tif":
            path = getattr(self.tif_project, "current_project_path", "") or ""
        elif getattr(self, "active_project_kind", "start") == "image":
            path = self._active_recent_project_path() or getattr(self.project, "current_project_path", "") or ""
        else:
            path = self.config.get("last_project_path", "") or ""
        return path if path else tr("No active project", self.current_lang)
