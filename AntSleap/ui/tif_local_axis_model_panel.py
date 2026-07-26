import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from AntSleap.ui.training_integrity_recovery_dialog import (
        TrainingIntegrityRecoveryDialog,
        is_training_integrity_error,
    )
    from AntSleap.core.tif_local_axis_baseline import add_baseline_local_frame_proposals
    from AntSleap.core.tif_local_axis_ai import (
        DEFAULT_LOCAL_AXIS_BACKEND_CONFIG,
        TifLocalAxisBackendRunner,
        export_local_axis_training_manifest,
        import_local_axis_proposals,
        load_global_roi_proposals,
        load_local_frame_proposals,
        register_local_axis_model_manifest,
        local_axis_initial_weight_entries,
        sanitize_local_axis_backend_config,
        validate_local_axis_backend_command,
    )
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from ui.training_integrity_recovery_dialog import (
        TrainingIntegrityRecoveryDialog,
        is_training_integrity_error,
    )
    from core.tif_local_axis_baseline import add_baseline_local_frame_proposals
    from core.tif_local_axis_ai import (
        DEFAULT_LOCAL_AXIS_BACKEND_CONFIG,
        TifLocalAxisBackendRunner,
        export_local_axis_training_manifest,
        import_local_axis_proposals,
        load_global_roi_proposals,
        load_local_frame_proposals,
        register_local_axis_model_manifest,
        local_axis_initial_weight_entries,
        sanitize_local_axis_backend_config,
        validate_local_axis_backend_command,
    )


MODEL_PANEL_TRANSLATIONS = {
    "zh": {
        "Local Axis Models": "局部轴模型",
        "Training dataset": "训练数据",
        "Backend configuration": "后端配置",
        "Actions": "动作",
        "Registered models": "已登记模型",
        "Active model profile": "当前模型方案",
        "Run history": "运行记录",
        "Template": "模板",
        "Export confirmed training manifest": "导出已确认训练清单",
        "Import global ROI proposals": "导入全局 ROI 建议项",
        "Import local frame proposals": "导入局部坐标系建议项",
        "Register model manifest": "登记模型清单",
        "Register training start model": "登记训练起始模型",
        "Initial-weight registration note": "初始权重登记备注",
        "Registered training start model: {0}": "已登记训练起始模型：{0}",
        "Backend ID": "后端 ID",
        "Display name": "显示名称",
        "Python": "Python",
        "Prepare command": "准备命令",
        "Train command": "训练命令",
        "Predict command": "预测命令",
        "Predict global ROI command": "预测全局 ROI 命令",
        "Predict local frame command": "预测局部坐标系命令",
        "Model manifest": "模型清单",
        "Save backend settings": "保存后端设置",
        "Prepare dataset": "准备数据集",
        "Train": "训练",
        "Predict global ROI": "预测全局 ROI",
        "Predict local frame": "预测局部坐标系",
        "Predict combined": "组合预测",
        "Generate baseline proposals": "生成基线建议项",
        "Refresh": "刷新",
        "Active model": "当前模型",
        "Save active model": "保存当前模型",
        "Model ID": "模型 ID",
        "Version": "版本",
        "Type": "类型",
        "Backend": "后端",
        "Manifest": "清单",
        "Run ID": "运行 ID",
        "Action": "动作",
        "Status": "状态",
        "Specimens": "标本",
        "Run dir": "运行目录",
        "No active model": "无当前模型",
        "None": "无",
        "Saved backend settings.": "已保存后端设置。",
        "Saved active Local Axis model: {0}": "已保存当前局部轴模型：{0}",
        "Command must include {contract} or {contract_json}: {0}": "命令必须包含 {contract} 或 {contract_json}：{0}",
        "Exported training manifest: {0} samples\n{1}": "已导出训练清单：{0} 条样本\n{1}",
        "Imported proposals: {0} global, {1} local frame.": "已导入建议项：{0} 条全局 ROI，{1} 条局部坐标系。",
        "Registered model: {0}": "已登记模型：{0}",
        "Running {0}...": "正在运行：{0}...",
        "Cancel": "取消",
        "Action finished: {0}\nRun: {1}": "动作完成：{0}\n运行目录：{1}",
        "Baseline proposals generated: {0} proposals, {1} skipped.": "已生成基线建议项：{0} 条，跳过 {1} 条。",
        "No command configured for this action.": "这个动作还没有配置命令。",
        "No TIF project is open.": "当前没有打开 TIF 项目。",
        "prepare_dataset": "准备数据集",
        "train": "训练",
        "predict": "组合预测",
        "predict_global_roi": "预测全局 ROI",
        "predict_local_frame": "预测局部坐标系",
    }
}


def tt(text, lang="en"):
    return MODEL_PANEL_TRANSLATIONS.get(lang, {}).get(text, text)


class TifLocalAxisModelPanel(QWidget):
    def __init__(self, project_manager, parent=None, lang="en", config_manager=None, specimen_id="", part_id=""):
        super().__init__(parent)
        self.project = project_manager
        self.lang = lang
        self.config_manager = config_manager
        self.specimen_id = str(specimen_id or "")
        self.part_id = str(part_id or "")
        self.backend_config = sanitize_local_axis_backend_config(self._load_backend_config())
        self.last_result = None
        self.setObjectName("tifLocalAxisModelPanel")

        root = QVBoxLayout(self)
        root.addWidget(self._build_dataset_group())
        root.addWidget(self._build_backend_group())
        root.addWidget(self._build_action_group())
        root.addWidget(self._build_active_model_group())
        root.addWidget(self._build_model_table_group())
        root.addWidget(self._build_run_table_group())
        self.status_label = QLabel("")
        self.status_label.setObjectName("tifLocalAxisModelStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self._load_backend_config_into_ui()
        self.refresh_tables()

    def _load_backend_config(self):
        if self.config_manager is None:
            return DEFAULT_LOCAL_AXIS_BACKEND_CONFIG
        return self.config_manager.get("tif_local_axis_backend", DEFAULT_LOCAL_AXIS_BACKEND_CONFIG)

    def _build_dataset_group(self):
        group = QGroupBox(tt("Training dataset", self.lang))
        layout = QFormLayout(group)
        self.template_edit = QLineEdit(self.part_id)
        self.btn_export_training = QPushButton(tt("Export confirmed training manifest", self.lang))
        self.btn_export_training.clicked.connect(self.export_training_manifest_dialog)
        self.btn_import_global = QPushButton(tt("Import global ROI proposals", self.lang))
        self.btn_import_global.clicked.connect(self.import_global_proposals_dialog)
        self.btn_import_local = QPushButton(tt("Import local frame proposals", self.lang))
        self.btn_import_local.clicked.connect(self.import_local_frame_proposals_dialog)
        self.btn_register_model = QPushButton(tt("Register model manifest", self.lang))
        self.btn_register_model.clicked.connect(self.register_model_manifest_dialog)
        self.btn_register_training_model = QPushButton(
            tt("Register training start model", self.lang)
        )
        self.btn_register_training_model.clicked.connect(
            self.register_training_model_manifest_dialog
        )
        layout.addRow(tt("Template", self.lang), self.template_edit)
        layout.addRow("", self.btn_export_training)
        layout.addRow("", self.btn_import_global)
        layout.addRow("", self.btn_import_local)
        layout.addRow("", self.btn_register_model)
        layout.addRow("", self.btn_register_training_model)
        return group

    def _build_active_model_group(self):
        group = QGroupBox(tt("Active model profile", self.lang))
        layout = QFormLayout(group)
        self.active_model_combo = QComboBox()
        self.active_model_combo.setObjectName("tifLocalAxisActiveModelCombo")
        self.btn_save_active_model = QPushButton(tt("Save active model", self.lang))
        self.btn_save_active_model.clicked.connect(self.save_active_model_profile)
        layout.addRow(tt("Active model", self.lang), self.active_model_combo)
        layout.addRow("", self.btn_save_active_model)
        return group

    def _build_backend_group(self):
        group = QGroupBox(tt("Backend configuration", self.lang))
        layout = QFormLayout(group)
        self.backend_id_edit = QLineEdit()
        self.backend_display_edit = QLineEdit()
        self.backend_python_edit = QLineEdit()
        self.backend_prepare_edit = QLineEdit()
        self.backend_train_edit = QLineEdit()
        self.backend_predict_edit = QLineEdit()
        self.backend_predict_global_edit = QLineEdit()
        self.backend_predict_local_edit = QLineEdit()
        self.backend_manifest_edit = QLineEdit()
        self.btn_save_backend = QPushButton(tt("Save backend settings", self.lang))
        self.btn_save_backend.clicked.connect(self.save_backend_settings)
        layout.addRow(tt("Backend ID", self.lang), self.backend_id_edit)
        layout.addRow(tt("Display name", self.lang), self.backend_display_edit)
        layout.addRow(tt("Python", self.lang), self.backend_python_edit)
        layout.addRow(tt("Prepare command", self.lang), self.backend_prepare_edit)
        layout.addRow(tt("Train command", self.lang), self.backend_train_edit)
        layout.addRow(tt("Predict command", self.lang), self.backend_predict_edit)
        layout.addRow(tt("Predict global ROI command", self.lang), self.backend_predict_global_edit)
        layout.addRow(tt("Predict local frame command", self.lang), self.backend_predict_local_edit)
        layout.addRow(tt("Model manifest", self.lang), self.backend_manifest_edit)
        layout.addRow("", self.btn_save_backend)
        return group

    def _build_action_group(self):
        group = QGroupBox(tt("Actions", self.lang))
        layout = QHBoxLayout(group)
        self.btn_prepare = QPushButton(tt("Prepare dataset", self.lang))
        self.btn_train = QPushButton(tt("Train", self.lang))
        self.btn_predict_global = QPushButton(tt("Predict global ROI", self.lang))
        self.btn_predict_local = QPushButton(tt("Predict local frame", self.lang))
        self.btn_predict = QPushButton(tt("Predict combined", self.lang))
        self.btn_baseline = QPushButton(tt("Generate baseline proposals", self.lang))
        self.btn_refresh = QPushButton(tt("Refresh", self.lang))
        self.btn_prepare.clicked.connect(lambda: self.run_backend_action("prepare_dataset"))
        self.btn_train.clicked.connect(lambda: self.run_backend_action("train"))
        self.btn_predict_global.clicked.connect(lambda: self.run_backend_action("predict_global_roi"))
        self.btn_predict_local.clicked.connect(lambda: self.run_backend_action("predict_local_frame"))
        self.btn_predict.clicked.connect(lambda: self.run_backend_action("predict"))
        self.btn_baseline.clicked.connect(self.generate_baseline_proposals)
        self.btn_refresh.clicked.connect(self.refresh_tables)
        for button in (
            self.btn_prepare,
            self.btn_train,
            self.btn_predict_global,
            self.btn_predict_local,
            self.btn_predict,
            self.btn_baseline,
            self.btn_refresh,
        ):
            layout.addWidget(button)
        return group

    def _build_model_table_group(self):
        group = QGroupBox(tt("Registered models", self.lang))
        root = QVBoxLayout(group)
        self.models_table = QTableWidget(0, 6)
        self.models_table.setObjectName("tifLocalAxisModelsTable")
        self.models_table.setHorizontalHeaderLabels(
            [tt(text, self.lang) for text in ["Model ID", "Version", "Template", "Type", "Backend", "Manifest"]]
        )
        root.addWidget(self.models_table)
        return group

    def _build_run_table_group(self):
        group = QGroupBox(tt("Run history", self.lang))
        root = QVBoxLayout(group)
        self.runs_table = QTableWidget(0, 7)
        self.runs_table.setObjectName("tifLocalAxisRunsTable")
        self.runs_table.setHorizontalHeaderLabels(
            [tt(text, self.lang) for text in ["Run ID", "Action", "Status", "Backend", "Template", "Specimens", "Run dir"]]
        )
        root.addWidget(self.runs_table)
        return group

    def _backend_config_from_ui(self):
        return sanitize_local_axis_backend_config(
            {
                "backend_id": self.backend_id_edit.text(),
                "display_name": self.backend_display_edit.text(),
                "python_executable": self.backend_python_edit.text(),
                "prepare_dataset_command": self.backend_prepare_edit.text(),
                "train_command": self.backend_train_edit.text(),
                "predict_command": self.backend_predict_edit.text(),
                "predict_global_roi_command": self.backend_predict_global_edit.text(),
                "predict_local_frame_command": self.backend_predict_local_edit.text(),
                "model_manifest": self.backend_manifest_edit.text(),
            }
        )

    def _load_backend_config_into_ui(self):
        config = sanitize_local_axis_backend_config(self.backend_config)
        self.backend_id_edit.setText(config.get("backend_id", ""))
        self.backend_display_edit.setText(config.get("display_name", ""))
        self.backend_python_edit.setText(config.get("python_executable", "python"))
        self.backend_prepare_edit.setText(config.get("prepare_dataset_command", ""))
        self.backend_train_edit.setText(config.get("train_command", ""))
        self.backend_predict_edit.setText(config.get("predict_command", ""))
        self.backend_predict_global_edit.setText(config.get("predict_global_roi_command", ""))
        self.backend_predict_local_edit.setText(config.get("predict_local_frame_command", ""))
        self.backend_manifest_edit.setText(config.get("model_manifest", ""))

    def _validate_backend_config(self, config):
        command_fields = (
            ("prepare_dataset_command", config.get("prepare_dataset_command", "")),
            ("train_command", config.get("train_command", "")),
            ("predict_command", config.get("predict_command", "")),
            ("predict_global_roi_command", config.get("predict_global_roi_command", "")),
            ("predict_local_frame_command", config.get("predict_local_frame_command", "")),
        )
        for field, command in command_fields:
            if not validate_local_axis_backend_command(command):
                message = tt("Command must include {contract} or {contract_json}: {0}", self.lang)
                raise ValueError(message.replace("{0}", field))

    def save_backend_settings(self):
        config = self._backend_config_from_ui()
        self._validate_backend_config(config)
        self.backend_config = config
        if self.config_manager is not None:
            self.config_manager.set("tif_local_axis_backend", dict(config))
            self.config_manager.save()
        self.status_label.setText(tt("Saved backend settings.", self.lang))
        return config

    def _training_filters(self):
        filters = {"include_unconfirmed": False}
        template_id = self.template_edit.text().strip()
        if template_id:
            filters["template_id"] = template_id
        return filters

    def export_training_manifest_to_dir(self, output_dir):
        result = export_local_axis_training_manifest(self.project, output_dir, self._training_filters())
        self.status_label.setText(
            tt("Exported training manifest: {0} samples\n{1}", self.lang).format(
                result.get("sample_count", 0),
                result.get("manifest_path", ""),
            )
        )
        return result

    def export_training_manifest_dialog(self):
        default_dir = os.path.join(self.project.project_dir, "exports", "local_axis_training")
        os.makedirs(default_dir, exist_ok=True)
        output_dir = QFileDialog.getExistingDirectory(self, tt("Export training manifest", self.lang), default_dir)
        if not output_dir:
            return None
        try:
            return self.export_training_manifest_to_dir(output_dir)
        except Exception as exc:
            QMessageBox.warning(self, tt("Local Axis Models", self.lang), str(exc))
            return None

    def import_global_proposals_file(self, path):
        proposals = load_global_roi_proposals(path)
        return self._import_proposals(global_proposals=proposals)

    def import_local_frame_proposals_file(self, path):
        proposals = load_local_frame_proposals(path)
        return self._import_proposals(local_frame_proposals=proposals)

    def _import_proposals(self, global_proposals=None, local_frame_proposals=None):
        result = import_local_axis_proposals(self.project, global_proposals or [], local_frame_proposals or [])
        self.refresh_tables()
        self.status_label.setText(
            tt("Imported proposals: {0} global, {1} local frame.", self.lang).format(
                len(result.get("global_roi_proposals", [])),
                len(result.get("local_frame_proposals", [])),
            )
        )
        return result

    def import_global_proposals_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, tt("Import global ROI proposals", self.lang), "", "JSON (*.json)")
        if not path:
            return None
        try:
            return self.import_global_proposals_file(path)
        except Exception as exc:
            QMessageBox.warning(self, tt("Local Axis Models", self.lang), str(exc))
            return None

    def import_local_frame_proposals_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, tt("Import local frame proposals", self.lang), "", "JSON (*.json)")
        if not path:
            return None
        try:
            return self.import_local_frame_proposals_file(path)
        except Exception as exc:
            QMessageBox.warning(self, tt("Local Axis Models", self.lang), str(exc))
            return None

    def register_model_manifest_file(self, path):
        record = register_local_axis_model_manifest(self.project, path)
        self.refresh_tables()
        self._set_active_model_id(record.get("model_id", ""), save=True)
        self.status_label.setText(tt("Registered model: {0}", self.lang).format(record.get("model_id", "")))
        return record

    def register_model_manifest_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, tt("Register model manifest", self.lang), "", "JSON (*.json)")
        if not path:
            return None
        try:
            return self.register_model_manifest_file(path)
        except Exception as exc:
            QMessageBox.warning(self, tt("Local Axis Models", self.lang), str(exc))
            return None

    def _command_key_for_action(self, action):
        return {
            "prepare_dataset": "prepare_dataset_command",
            "train": "train_command",
            "predict": "predict_command",
            "predict_global_roi": "predict_global_roi_command",
            "predict_local_frame": "predict_local_frame_command",
        }.get(action, "")

    def _selected_specimen_ids(self):
        if self.specimen_id:
            return [self.specimen_id]
        return [item.get("specimen_id", "") for item in self.project.project_data.get("specimens", []) if item.get("specimen_id")]

    def _selected_part_map(self, action):
        if self.specimen_id and self.part_id and action in {
            "prepare_dataset",
            "train",
            "predict_local_frame",
            "predict",
            "baseline",
        }:
            return {self.specimen_id: [self.part_id]}
        return None

    def generate_baseline_proposals(self):
        try:
            result = add_baseline_local_frame_proposals(
                self.project,
                specimen_ids=self._selected_specimen_ids() or None,
                part_ids_by_specimen=self._selected_part_map("baseline"),
                template_id=self.template_edit.text().strip(),
            )
        except Exception as exc:
            QMessageBox.warning(self, tt("Local Axis Models", self.lang), str(exc))
            self.status_label.setText(str(exc))
            return None
        self.refresh_tables()
        self.status_label.setText(
            tt("Baseline proposals generated: {0} proposals, {1} skipped.", self.lang).format(
                len(result.get("proposals", [])),
                len(result.get("skipped", [])),
            )
        )
        return result

    def run_backend_action(self, action):
        progress = None
        try:
            config = self.save_backend_settings()
            command_key = self._command_key_for_action(action)
            if command_key and not str(config.get(command_key, "")).strip():
                if action == "predict_global_roi" and config.get("predict_command", "").strip():
                    pass
                elif action == "predict_local_frame" and config.get("predict_command", "").strip():
                    pass
                else:
                    QMessageBox.warning(self, tt("Local Axis Models", self.lang), tt("No command configured for this action.", self.lang))
                    return None
            action_label = tt(action, self.lang)
            self.status_label.setText(tt("Running {0}...", self.lang).format(action_label))
            if action == "train":
                progress = QProgressDialog(
                    tt("Running {0}...", self.lang).format(action_label),
                    tt("Cancel", self.lang),
                    0,
                    100,
                    self,
                )
                progress.setWindowTitle(tt("Local Axis Models", self.lang))
                progress.setWindowModality(Qt.WindowModal)
                progress.setAutoClose(False)
                progress.setAutoReset(False)
                progress.setMinimumDuration(0)
                progress.show()

            def on_progress(current, total, message):
                if progress is None:
                    return
                if int(total or 0) <= 0:
                    progress.setRange(0, 0)
                else:
                    progress.setRange(0, max(1, int(total)))
                    progress.setValue(max(0, min(int(current or 0), int(total))))
                if message:
                    progress.setLabelText(str(message))
                QApplication.processEvents()

            def cancel_requested():
                if progress is None:
                    return False
                QApplication.processEvents()
                return progress.wasCanceled()

            runner = TifLocalAxisBackendRunner(self.project, config)
            result = runner.run_action(
                action,
                specimen_ids=self._selected_specimen_ids() or None,
                part_ids_by_specimen=self._selected_part_map(action),
                template_id=self.template_edit.text().strip(),
                model_manifest=config.get("model_manifest", ""),
                progress_callback=on_progress if action == "train" else None,
                cancel_check=cancel_requested if action == "train" else None,
            )
        except Exception as exc:
            if action == "train" and is_training_integrity_error(exc):
                self._training_integrity_recovery_dialog = (
                    TrainingIntegrityRecoveryDialog(self.project, self)
                )
                self._training_integrity_recovery_dialog.open()
            else:
                QMessageBox.warning(self, tt("Local Axis Models", self.lang), str(exc))
            self.status_label.setText(str(exc))
            return None
        finally:
            if progress is not None:
                progress.close()
                progress.deleteLater()
        self.last_result = result
        self.refresh_tables()
        self.status_label.setText(tt("Action finished: {0}\nRun: {1}", self.lang).format(tt(action, self.lang), result.get("run_dir", "")))
        return result

    def register_training_model_manifest_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tt("Register training start model", self.lang),
            "",
            "JSON (*.json)",
        )
        if not path:
            return None
        note, accepted = QInputDialog.getText(
            self,
            tt("Register training start model", self.lang),
            tt("Initial-weight registration note", self.lang),
        )
        if not accepted:
            return None
        try:
            from AntSleap.core.training_initial_weights import (
                register_initial_weight_version,
            )

            entries = local_axis_initial_weight_entries(path)
            register_initial_weight_version(self.project, entries, note=note)
            record = self.register_model_manifest_file(path)
        except Exception as exc:
            QMessageBox.warning(self, tt("Local Axis Models", self.lang), str(exc))
            return None
        self.status_label.setText(
            tt("Registered training start model: {0}", self.lang).format(
                record.get("model_id", "")
            )
        )
        return record

    def refresh_tables(self):
        self._refresh_active_model_combo()
        self._refresh_models_table()
        self._refresh_runs_table()

    def _project_view_settings(self):
        return self.project.project_data.setdefault("view_settings", {})

    def _active_model_id(self):
        settings = self._project_view_settings()
        return str(settings.get("local_axis_active_model_id", "") or "")

    def _set_active_model_id(self, model_id, save=False):
        settings = self._project_view_settings()
        settings["local_axis_active_model_id"] = str(model_id or "")
        if save:
            self.project.save_project()
        self._refresh_active_model_combo()
        return settings["local_axis_active_model_id"]

    def _refresh_active_model_combo(self):
        if not hasattr(self, "active_model_combo"):
            return
        models = self.project.list_local_axis_models() if hasattr(self.project, "list_local_axis_models") else []
        active_id = self._active_model_id()
        self.active_model_combo.blockSignals(True)
        self.active_model_combo.clear()
        self.active_model_combo.addItem(tt("No active model", self.lang), "")
        for model in models:
            model_id = str(model.get("model_id", "") or "")
            label = "{0} ({1}, {2})".format(
                model_id,
                model.get("model_version", "") or "-",
                model.get("template_id", "") or "-",
            )
            self.active_model_combo.addItem(label, model_id)
        index = self.active_model_combo.findData(active_id)
        self.active_model_combo.setCurrentIndex(index if index >= 0 else 0)
        self.active_model_combo.blockSignals(False)

    def save_active_model_profile(self):
        model_id = str(self.active_model_combo.currentData() or "")
        saved = self._set_active_model_id(model_id, save=True)
        self.status_label.setText(tt("Saved active Local Axis model: {0}", self.lang).format(saved or tt("None", self.lang)))
        return saved

    def _set_readonly_item(self, table, row, col, value):
        item = QTableWidgetItem(str(value))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, col, item)

    def _refresh_models_table(self):
        models = self.project.list_local_axis_models() if hasattr(self.project, "list_local_axis_models") else []
        self.models_table.setRowCount(len(models))
        for row, model in enumerate(models):
            values = [
                model.get("model_id", ""),
                model.get("model_version", ""),
                model.get("template_id", ""),
                model.get("model_type", ""),
                model.get("backend_id", ""),
                model.get("model_manifest", ""),
            ]
            for col, value in enumerate(values):
                self._set_readonly_item(self.models_table, row, col, value)

    def _refresh_runs_table(self):
        legacy_runs = self.project.list_local_axis_runs() if hasattr(self.project, "list_local_axis_runs") else []
        merged = {
            str(item.get("run_id") or ""): dict(item)
            for item in legacy_runs
            if str(item.get("run_id") or "")
        }
        try:
            from AntSleap.core.training_run_recorder import TrainingRunRecorder

            runs_root = os.path.join(self.project.project_dir, "runs", "local_axis")
            recorder = TrainingRunRecorder(
                runs_root,
                database_path=self.project.current_database_path,
            )
            for record in recorder.list_records():
                if record.get("entrypoint") != "local_axis_external":
                    continue
                invocation = (record.get("effective_config") or {}).get(
                    "adapter_invocation"
                ) or {}
                backend = record.get("backend") or {}
                merged[record["run_id"]] = {
                    "run_id": record["run_id"],
                    "action": "train",
                    "result_status": record.get("status", ""),
                    "backend_id": backend.get("adapter_id") or backend.get("backend_id", ""),
                    "template_id": invocation.get("template_id", ""),
                    "specimen_ids": [],
                    "run_dir": os.path.join(runs_root, record["run_id"]),
                    "created_at": record.get("created_at", ""),
                }
        except Exception:
            pass
        runs = sorted(
            merged.values(),
            key=lambda item: (
                str(item.get("created_at") or ""),
                str(item.get("run_id") or ""),
            ),
            reverse=True,
        )
        self.runs_table.setRowCount(len(runs))
        for row, run in enumerate(runs):
            values = [
                run.get("run_id", ""),
                run.get("action", ""),
                run.get("result_status", ""),
                run.get("backend_id", ""),
                run.get("template_id", ""),
                ",".join(run.get("specimen_ids", []) or []),
                run.get("run_dir", ""),
            ]
            for col, value in enumerate(values):
                self._set_readonly_item(self.runs_table, row, col, value)


class TifLocalAxisModelDialog(QDialog):
    def __init__(self, project_manager, parent=None, lang="en", config_manager=None, specimen_id="", part_id=""):
        super().__init__(parent)
        self.setWindowTitle(tt("Local Axis Models", lang))
        self.resize(980, 760)
        root = QVBoxLayout(self)
        self.panel = TifLocalAxisModelPanel(
            project_manager,
            parent=self,
            lang=lang,
            config_manager=config_manager,
            specimen_id=specimen_id,
            part_id=part_id,
        )
        root.addWidget(self.panel)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
