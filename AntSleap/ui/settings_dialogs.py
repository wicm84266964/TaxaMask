from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
)

try:
    from AntSleap.core.runtime_device import normalize_device_preference
    from AntSleap.core.tif_backend import nnunet_v2_tif_backend_preset, sanitize_tif_backend_config
    from AntSleap.core.tif_export import SUPPORTED_TIF_EXPORT_FORMATS
    from AntSleap.ui.main_window_dialog_support import (
        _agent_command_has_contract,
        _agent_error_summary,
        _agent_yes_no,
        _format_backend_contract_error,
    )
    from AntSleap.ui.main_window_i18n import tr
    from AntSleap.ui.main_window_widgets import NoWheelComboBox
    from AntSleap.ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_STOP,
        SURFACE_ROLE_SUBTLE,
        apply_semantic_button_style,
        apply_surface_role,
        apply_theme_button_style,
        get_theme_stylesheet,
        normalize_theme,
    )
except ImportError:
    from core.runtime_device import normalize_device_preference
    from core.tif_backend import nnunet_v2_tif_backend_preset, sanitize_tif_backend_config
    from core.tif_export import SUPPORTED_TIF_EXPORT_FORMATS
    from ui.main_window_dialog_support import (
        _agent_command_has_contract,
        _agent_error_summary,
        _agent_yes_no,
        _format_backend_contract_error,
    )
    from ui.main_window_i18n import tr
    from ui.main_window_widgets import NoWheelComboBox
    from ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_STOP,
        SURFACE_ROLE_SUBTLE,
        apply_semantic_button_style,
        apply_surface_role,
        apply_theme_button_style,
        get_theme_stylesheet,
        normalize_theme,
    )


class GeneralSettingsDialog(QDialog):
    agent_requested = Signal(dict)

    def __init__(self, params, lang="en", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.current_theme = normalize_theme(params.get("theme", "dark"))
        self.setWindowTitle(tr("General Application Settings", lang))
        self.resize(620, 460)
        self.setStyleSheet(get_theme_stylesheet(self.current_theme))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        note = QLabel(
            tr(
                "General settings control the whole application: language, theme, startup behavior, autosave, and the default compute device. Workflow-specific training parameters stay in their own model settings.",
                lang,
            )
        )
        note.setWordWrap(True)
        note.setObjectName("mutedLabel")
        layout.addWidget(note)

        group = QGroupBox(tr("Application Preferences", lang))
        apply_surface_role(group, SURFACE_ROLE_SUBTLE, "generalSettingsPreferencesPanel")
        form = QFormLayout(group)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)

        self.language_combo = NoWheelComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("中文", "zh")
        language_index = self.language_combo.findData(params.get("language", "en"))
        self.language_combo.setCurrentIndex(language_index if language_index >= 0 else 0)
        form.addRow(QLabel(tr("Language:", lang)), self.language_combo)

        self.theme_combo = NoWheelComboBox()
        self.theme_combo.addItem(tr("Dark Mode (Deep Space Neon)", lang), "dark")
        self.theme_combo.addItem(tr("Light Mode", lang), "light")
        theme_index = self.theme_combo.findData(self.current_theme)
        self.theme_combo.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        form.addRow(QLabel(tr("Theme:", lang)), self.theme_combo)

        theme_note = QLabel(tr("Dark Mode now uses the Deep Space Neon palette; Light Mode is available for bright workspaces.", lang))
        theme_note.setWordWrap(True)
        theme_note.setObjectName("mutedLabel")
        form.addRow(QLabel(""), theme_note)

        self.startup_combo = NoWheelComboBox()
        self.startup_combo.addItem(tr("Show Start Center", lang), "start_center")
        self.startup_combo.addItem(tr("Continue last project automatically", lang), "continue_last")
        startup_index = self.startup_combo.findData(params.get("startup_behavior", "start_center"))
        self.startup_combo.setCurrentIndex(startup_index if startup_index >= 0 else 0)
        form.addRow(QLabel(tr("Startup Behavior:", lang)), self.startup_combo)

        self.autosave_seconds = QLineEdit(str(params.get("project_autosave_interval_sec", 3)))
        form.addRow(QLabel(tr("Project Autosave Interval (seconds):", lang)), self.autosave_seconds)

        self.runtime_combo = NoWheelComboBox()
        self.runtime_combo.addItem(tr("Auto (CUDA if available)", lang), "auto")
        self.runtime_combo.addItem(tr("CPU only", lang), "cpu")
        self.runtime_combo.addItem(tr("CUDA GPU", lang), "cuda")
        runtime_index = self.runtime_combo.findData(normalize_device_preference(params.get("runtime_device", "auto")))
        self.runtime_combo.setCurrentIndex(runtime_index if runtime_index >= 0 else 0)
        form.addRow(QLabel(tr("Default Runtime Device:", lang)), self.runtime_combo)

        runtime_note = QLabel(
            tr(
                "Runtime device here is the default for built-in 2D/STL models and other internal Torch tasks.",
                lang,
            )
        )
        runtime_note.setWordWrap(True)
        runtime_note.setObjectName("mutedLabel")
        form.addRow(QLabel(""), runtime_note)

        layout.addWidget(group)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        btn_ask_agent = QPushButton(tr("Ask Agent", lang))
        btn_ask_agent.setObjectName("generalSettingsAskAgentButton")
        btn_ask_agent.setToolTip(tr("Ask Agent about these settings. Current values are summarized without sending full command text.", lang))
        apply_theme_button_style(btn_ask_agent, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        btn_ask_agent.clicked.connect(self.request_agent_help)
        btn_save = QPushButton(tr("Save", lang))
        apply_theme_button_style(btn_save, BUTTON_ROLE_COMMIT, "", self.current_theme)
        btn_save.clicked.connect(self.accept_with_validation)
        btn_cancel = QPushButton(tr("Cancel", lang))
        apply_theme_button_style(btn_cancel, BUTTON_ROLE_STOP, "", self.current_theme)
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_ask_agent)
        buttons.addStretch(1)
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

    def accept_with_validation(self):
        try:
            autosave = int(float(self.autosave_seconds.text()))
        except Exception:
            autosave = 0
        if autosave <= 0:
            QMessageBox.warning(self, tr("Invalid Settings", self.lang), tr("Autosave interval must be a positive number.", self.lang))
            return
        self.accept()

    def get_values(self):
        try:
            return {
                "language": self.language_combo.currentData() or "en",
                "theme": normalize_theme(self.theme_combo.currentData() or "dark"),
                "startup_behavior": self.startup_combo.currentData() or "start_center",
                "project_autosave_interval_sec": int(float(self.autosave_seconds.text())),
                "runtime_device": normalize_device_preference(self.runtime_combo.currentData() or "auto"),
            }
        except Exception:
            return None

    def request_agent_help(self):
        self.agent_requested.emit(self.get_agent_context())
        self.reject()

    def get_agent_context(self):
        return {
            "source_workbench": "general_settings",
            "project_type": "settings",
            "settings_scope": "general",
            "settings_question_focus": "Application language, startup behavior, autosave timing, and default runtime device.",
            "language": self.language_combo.currentData() or "en",
            "theme": normalize_theme(self.theme_combo.currentData() or "dark"),
            "startup_behavior": self.startup_combo.currentData() or "start_center",
            "project_autosave_interval_sec": self.autosave_seconds.text().strip(),
            "runtime_device": normalize_device_preference(self.runtime_combo.currentData() or "auto"),
            "validation_errors": _agent_error_summary([]),
        }


class TifModelSettingsDialog(QDialog):
    agent_requested = Signal(dict)

    def __init__(self, config, lang="en", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tr("TIF Volume Training Settings", lang))
        self.resize(820, 680)

        self.backend_config = sanitize_tif_backend_config(config or {})

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        note = QLabel(
            tr(
                "Controls the default external backend used by TIF Volume Workbench. The workbench can still edit the same defaults while you are inside a project.",
                lang,
            )
        )
        note.setWordWrap(True)
        note.setObjectName("mutedLabel")
        layout.addWidget(note)

        safety = QGroupBox(tr("Training Data Safety", lang))
        apply_surface_role(safety, SURFACE_ROLE_SUBTLE, "tifModelSettingsSafetyPanel")
        safety_layout = QVBoxLayout(safety)
        safety_layout.setContentsMargins(12, 12, 12, 12)
        safety_layout.setSpacing(6)
        for text in (
            "TIF training uses manual_truth label volumes only. Part prediction results are imported as editable_ai_result plus a raw backup, so they must be reviewed before becoming manual truth.",
            "Training source: manual_truth only.",
            "Prediction import: editable_ai_result layer.",
            "Manual truth is never overwritten automatically.",
        ):
            label = QLabel(tr(text, lang))
            label.setWordWrap(True)
            label.setObjectName("mutedLabel")
            safety_layout.addWidget(label)
        layout.addWidget(safety)

        group = QGroupBox(tr("TIF Backend Defaults", lang))
        apply_surface_role(group, SURFACE_ROLE_SUBTLE, "tifModelSettingsBackendPanel")
        form = QFormLayout(group)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)

        self.backend_id_edit = QLineEdit(self.backend_config.get("backend_id", ""))
        form.addRow(QLabel(tr("Backend ID:", lang)), self.backend_id_edit)

        self.display_name_edit = QLineEdit(self.backend_config.get("display_name", ""))
        form.addRow(QLabel(tr("Display Name:", lang)), self.display_name_edit)

        self.python_edit = QLineEdit(self.backend_config.get("python_executable", "python"))
        form.addRow(QLabel(tr("Python Executable:", lang)), self.python_edit)

        self.export_formats_edit = QLineEdit(self.backend_config.get("export_formats", "ome_tiff,nrrd,mha,nifti"))
        form.addRow(QLabel(tr("Export Formats:", lang)), self.export_formats_edit)
        supported = QLabel(tr("Supported export formats: {0}", lang).format(", ".join(sorted(SUPPORTED_TIF_EXPORT_FORMATS))))
        supported.setWordWrap(True)
        supported.setObjectName("mutedLabel")
        form.addRow(QLabel(""), supported)

        self.prepare_command_edit = self._make_command_editor(
            self.backend_config.get("prepare_dataset_command", ""),
            "{python} prepare_tif_dataset.py --contract {contract_json}",
        )
        form.addRow(QLabel(tr("Prepare Dataset Command:", lang)), self.prepare_command_edit)

        self.train_command_edit = self._make_command_editor(
            self.backend_config.get("train_command", ""),
            "{python} train_tif_model.py --contract {contract_json}",
        )
        form.addRow(QLabel(tr("Train Command:", lang)), self.train_command_edit)

        self.predict_command_edit = self._make_command_editor(
            self.backend_config.get("predict_command", ""),
            "{python} predict_tif_volume.py --contract {contract_json}",
        )
        form.addRow(QLabel(tr("Predict Command:", lang)), self.predict_command_edit)

        self.model_manifest_edit = QLineEdit(self.backend_config.get("model_manifest", ""))
        self.model_manifest_edit.setPlaceholderText("{run_dir}/outputs/model_manifest.json")
        form.addRow(QLabel(tr("Model Manifest Path:", lang)), self.model_manifest_edit)

        self.validation_label = QLabel("")
        self.validation_label.setObjectName("mutedLabel")
        self.validation_label.setWordWrap(True)
        form.addRow(QLabel(""), self.validation_label)

        btn_validate = QPushButton(tr("Validate TIF Backend", lang))
        apply_semantic_button_style(btn_validate, BUTTON_ROLE_NEUTRAL)
        btn_validate.clicked.connect(self.validate_backend)
        btn_nnunet_preset = QPushButton(tr("Use nnU-Net v2 Preset", lang))
        btn_nnunet_preset.setObjectName("tifUseNnunetV2PresetButton")
        btn_nnunet_preset.setToolTip(
            tr("Fill the editable command fields with the bundled TaxaMask nnU-Net v2 contract adapter.", lang)
        )
        apply_semantic_button_style(btn_nnunet_preset, BUTTON_ROLE_NEUTRAL)
        btn_nnunet_preset.clicked.connect(self.apply_nnunet_v2_preset)
        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        preset_row.addWidget(btn_nnunet_preset)
        preset_row.addWidget(btn_validate)
        preset_row.addStretch(1)
        form.addRow(QLabel(""), preset_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(group)
        layout.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        btn_ask_agent = QPushButton(tr("Ask Agent", lang))
        btn_ask_agent.setObjectName("tifModelSettingsAskAgentButton")
        btn_ask_agent.setToolTip(tr("Ask Agent about these settings. Current values are summarized without sending full command text.", lang))
        apply_semantic_button_style(btn_ask_agent, BUTTON_ROLE_NEUTRAL)
        btn_ask_agent.clicked.connect(self.request_agent_help)
        btn_save = QPushButton(tr("Save", lang))
        apply_semantic_button_style(btn_save, BUTTON_ROLE_COMMIT)
        btn_save.clicked.connect(self.accept_with_validation)
        btn_cancel = QPushButton(tr("Cancel", lang))
        apply_semantic_button_style(btn_cancel, BUTTON_ROLE_STOP)
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_ask_agent)
        buttons.addStretch(1)
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

    def _make_command_editor(self, text, placeholder):
        editor = QTextEdit()
        editor.setAcceptRichText(False)
        editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        editor.setMinimumHeight(70)
        editor.setPlainText(str(text or ""))
        editor.setPlaceholderText(placeholder)
        return editor

    def _command_text(self, editor):
        return editor.toPlainText().strip()

    def _set_backend_fields(self, config):
        config = sanitize_tif_backend_config(config or {})
        self.backend_id_edit.setText(config.get("backend_id", ""))
        self.display_name_edit.setText(config.get("display_name", ""))
        self.python_edit.setText(config.get("python_executable", "python"))
        self.export_formats_edit.setText(config.get("export_formats", "ome_tiff,nrrd,mha,nifti"))
        self.prepare_command_edit.setPlainText(config.get("prepare_dataset_command", ""))
        self.train_command_edit.setPlainText(config.get("train_command", ""))
        self.predict_command_edit.setPlainText(config.get("predict_command", ""))
        self.model_manifest_edit.setText(config.get("model_manifest", ""))

    def apply_nnunet_v2_preset(self):
        self._set_backend_fields(nnunet_v2_tif_backend_preset(self.python_edit.text().strip() or "python"))
        self.validation_label.setText(tr("nnU-Net v2 preset filled. Commands remain editable for other 3D backends.", self.lang))

    def _export_formats(self):
        return [
            item.strip()
            for item in self.export_formats_edit.text().split(",")
            if item.strip()
        ]

    def _validation_errors(self):
        errors = []
        if not self.backend_id_edit.text().strip():
            errors.append(tr("TIF backend ID is required.", self.lang))
        export_formats = self._export_formats()
        if not export_formats:
            errors.append(tr("TIF backend export formats are required.", self.lang))
        unknown_formats = sorted(set(export_formats) - SUPPORTED_TIF_EXPORT_FORMATS)
        if unknown_formats:
            errors.append(tr("Unsupported TIF export formats: {0}", self.lang).format(", ".join(unknown_formats)))

        commands = {
            "prepare_dataset": self._command_text(self.prepare_command_edit),
            "train": self._command_text(self.train_command_edit),
            "predict": self._command_text(self.predict_command_edit),
        }
        for command_name, command_text in commands.items():
            if command_text and "{contract}" not in command_text and "{contract_json}" not in command_text:
                errors.append(
                    _format_backend_contract_error(
                        tr("TIF backend command '{0}' must include {contract} or {contract_json}.", self.lang),
                        command_name,
                    )
                )
        return errors

    def validate_backend(self):
        errors = self._validation_errors()
        if errors:
            message = "\n".join(errors)
            self.validation_label.setText(message)
            QMessageBox.warning(self, tr("TIF Volume Model Settings", self.lang), message)
            return False
        self.validation_label.setText(tr("TIF backend configuration looks valid.", self.lang))
        QMessageBox.information(
            self,
            tr("TIF Volume Model Settings", self.lang),
            tr("TIF backend configuration looks valid.", self.lang),
        )
        return True

    def accept_with_validation(self):
        errors = self._validation_errors()
        if errors:
            message = "\n".join(errors)
            self.validation_label.setText(message)
            QMessageBox.warning(self, tr("Invalid Settings", self.lang), message)
            return
        self.accept()

    def get_values(self):
        return sanitize_tif_backend_config(
            {
                "backend_id": self.backend_id_edit.text(),
                "display_name": self.display_name_edit.text(),
                "python_executable": self.python_edit.text(),
                "export_formats": ",".join(self._export_formats()),
                "prepare_dataset_command": self._command_text(self.prepare_command_edit),
                "train_command": self._command_text(self.train_command_edit),
                "predict_command": self._command_text(self.predict_command_edit),
                "model_manifest": self.model_manifest_edit.text(),
            }
        )

    def request_agent_help(self):
        self.agent_requested.emit(self.get_agent_context())
        self.reject()

    def get_agent_context(self):
        prepare_command = self._command_text(self.prepare_command_edit)
        train_command = self._command_text(self.train_command_edit)
        predict_command = self._command_text(self.predict_command_edit)
        return {
            "source_workbench": "tif_model_settings",
            "project_type": "settings",
            "settings_scope": "tif_volume_backend",
            "settings_question_focus": "TIF volume external backend defaults for dataset export, nnU-Net style training, and prediction import.",
            "backend_id": self.backend_id_edit.text().strip(),
            "display_name": self.display_name_edit.text().strip(),
            "python_executable": self.python_edit.text().strip(),
            "export_formats": ",".join(self._export_formats()),
            "prepare_command_present": _agent_yes_no(bool(prepare_command)),
            "train_command_present": _agent_yes_no(bool(train_command)),
            "predict_command_present": _agent_yes_no(bool(predict_command)),
            "prepare_command_has_contract": _agent_yes_no(_agent_command_has_contract(prepare_command)),
            "train_command_has_contract": _agent_yes_no(_agent_command_has_contract(train_command)),
            "predict_command_has_contract": _agent_yes_no(_agent_command_has_contract(predict_command)),
            "model_manifest_present": _agent_yes_no(bool(self.model_manifest_edit.text().strip())),
            "validation_errors": _agent_error_summary(self._validation_errors()),
        }

