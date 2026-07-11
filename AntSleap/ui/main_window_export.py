try:
    from AntSleap.ui.main_window_stage7_dependencies import *
except ImportError:
    from ui.main_window_stage7_dependencies import *


class MainWindowExportMixin:
    def export_dataset(self):
        dlg = ExportDialog(self, self.current_lang, default_dir=self._default_2d_export_dir())
        if dlg.exec():
            self._flush_pending_project_save(defer_for_navigation=False)
            p, f = dlg.get_path(), dlg.get_format()
            if not p:
                return
            self._start_dataset_export(p, f)

    def _start_dataset_export(self, output_dir, export_format):
        if getattr(self, "dataset_export_thread", None) is not None and self.dataset_export_thread.isRunning():
            QMessageBox.information(
                self,
                tr("Export", self.current_lang),
                tr("Dataset export is already running.", self.current_lang),
            )
            return

        progress = QProgressDialog(
            tr("Preparing dataset export...", self.current_lang),
            "",
            0,
            0,
            self,
        )
        progress.setWindowTitle(tr("Export Progress", self.current_lang))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)
        self._prepare_progress_dialog(progress, width=520)
        progress.show()

        self.dataset_export_thread = DatasetExportThread(
            self.project,
            output_dir,
            export_format,
            lang=self.current_lang,
        )
        thread = self.dataset_export_thread
        task_context = self._capture_project_task_context()
        self.dataset_export_project_context = task_context

        def on_progress(done, total, label):
            total = max(0, int(total))
            done = max(0, int(done))
            if total > 0 and progress.maximum() != total:
                progress.setRange(0, total)
            elif total <= 0 and progress.maximum() != 0:
                progress.setRange(0, 0)
            if total > 0:
                progress.setValue(min(done, total))
            message = tr("Exporting dataset...", self.current_lang)
            if label:
                message = tr("Exporting dataset: {0}", self.current_lang).format(label)
            progress.setLabelText(message)

        def on_success(count, folder, _export_format):
            if not self._project_task_context_matches(task_context):
                self._log_stale_project_task_result("dataset_export_success", task_context)
                progress.close()
                return
            progress.setValue(progress.maximum())
            progress.close()
            message = tr("Exported {0} samples.\n\nOutput folder: {1}", self.current_lang).format(count, folder)
            self.log(message)
            try:
                open_path(folder)
            except Exception as exc:
                self.log(f"Could not open export folder: {exc}")
            QMessageBox.information(self, tr("Export", self.current_lang), message)

        def on_error(message):
            if not self._project_task_context_matches(task_context):
                self._log_stale_project_task_result("dataset_export_error", task_context)
                progress.close()
                return
            progress.close()
            QMessageBox.warning(
                self,
                tr("Export", self.current_lang),
                tr("Dataset export failed: {0}", self.current_lang).format(message),
            )

        def on_finished():
            if getattr(self, "dataset_export_thread", None) is thread:
                self.dataset_export_thread = None

        thread.progress_signal.connect(on_progress)
        thread.success_signal.connect(on_success)
        thread.error_signal.connect(on_error)
        thread.finished_signal.connect(on_finished)
        thread.start()
