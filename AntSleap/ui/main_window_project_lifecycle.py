try:
    from AntSleap.ui.main_window_project_dependencies import *
except ImportError:
    from ui.main_window_project_dependencies import *


class MainWindowProjectLifecycleMixin:
    def _default_outputs_root(self):
        return os.path.abspath(os.path.join(REPO_ROOT, DEFAULT_OUTPUTS_DIR_NAME))

    def _ensure_default_output_subdir(self, *parts):
        path = os.path.join(self._default_outputs_root(), *parts)
        os.makedirs(path, exist_ok=True)
        return path

    def _default_2d_stl_projects_root(self):
        return self._ensure_default_output_subdir(DEFAULT_2D_STL_PROJECTS_DIR_NAME)

    def _default_tif_projects_root(self):
        return self._ensure_default_output_subdir(DEFAULT_TIF_PROJECTS_DIR_NAME)

    def _default_startup_project_dir(self):
        return self._ensure_default_output_subdir(DEFAULT_2D_STL_PROJECTS_DIR_NAME, DEFAULT_STARTUP_PROJECT_DIR_NAME)

    def _startup_project_manifest_path(self):
        return os.path.join(self._default_startup_project_dir(), f"{DEFAULT_PROJECT_NAME}.sqlite_manifest.json")

    def _startup_legacy_json_project_path(self):
        return os.path.join(self._default_startup_project_dir(), f"{DEFAULT_PROJECT_NAME}.json")

    def _open_or_create_startup_project(self):
        manifest_path = self._startup_project_manifest_path()
        legacy_json_path = self._startup_legacy_json_project_path()
        if os.path.exists(manifest_path):
            self.project.load_project(manifest_path)
            return
        if os.path.exists(legacy_json_path):
            self.open_project_path(legacy_json_path)
            return
        self.project.create_project(
            DEFAULT_PROJECT_NAME,
            self._default_startup_project_dir(),
            template_id=DEFAULT_PROJECT_TEMPLATE_ID,
        )

    def _default_project_dialog_dir(self, project_kind):
        if str(project_kind or "").lower() == "tif":
            return self._default_tif_projects_root()
        return self._default_2d_stl_projects_root()

    def _current_2d_project_dir(self):
        project_path = getattr(self.project, "current_project_path", "") or ""
        if project_path:
            return os.path.dirname(os.path.abspath(project_path))
        return self._default_2d_stl_projects_root()

    def _default_2d_export_dir(self):
        path = os.path.join(self._current_2d_project_dir(), "exports")
        os.makedirs(path, exist_ok=True)
        return path

    def _default_vlm_preannotation_dir(self):
        path = os.path.join(self._current_2d_project_dir(), "vlm_preannotation")
        os.makedirs(path, exist_ok=True)
        return path

    def _default_open_project_dir(self):
        candidates = [
            self.config.get("last_project_path", ""),
            getattr(self, "active_project_entry_path", ""),
            getattr(self.project, "current_project_path", ""),
        ]
        if self._is_tif_workflow_enabled():
            candidates.append(getattr(self.tif_project, "current_project_path", ""))
        for candidate in candidates:
            if not candidate:
                continue
            path = os.path.abspath(str(candidate))
            if self._path_is_startup_project(path):
                continue
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            if folder and os.path.isdir(folder) and not self._path_is_inside_program_package(folder):
                return folder
        return self._ensure_default_output_subdir()

    def _path_is_startup_project(self, path_text):
        try:
            startup_dir = self._default_startup_project_dir()
            path = os.path.abspath(str(path_text))
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            return os.path.commonpath([startup_dir, folder]) == startup_dir
        except (TypeError, ValueError):
            return False

    def _path_is_inside_program_package(self, path_text):
        try:
            return os.path.commonpath([PACKAGE_DIR, os.path.abspath(str(path_text))]) == PACKAGE_DIR
        except (TypeError, ValueError):
            return False

    def open_last_project(self):
        last_project = self.config.get("last_project_path", "")
        if not last_project or not os.path.exists(last_project):
            return
        if self._is_tif_project_file(last_project) and not self._is_tif_workflow_enabled():
            self._show_tif_workflow_unavailable()
            return
        self.open_project_path(last_project)

    def closeEvent(self, event):
        if getattr(self, "image_import_thread", None) is not None and self.image_import_thread.isRunning():
            QMessageBox.information(
                self,
                tr("Image Import", self.current_lang),
                tr("Image import is running. Please wait for it to finish before closing TaxaMask.", self.current_lang),
            )
            event.ignore()
            return
        if getattr(self, "external_batch_inference_thread", None) is not None and self.external_batch_inference_thread.isRunning():
            QMessageBox.information(
                self,
                tr("Batch Inference", self.current_lang),
                tr("Batch inference is running. Please wait for it to finish before closing TaxaMask.", self.current_lang),
            )
            event.ignore()
            return
        if getattr(self, "vlm_preannotation_run_active", False):
            QMessageBox.information(
                self,
                tr("VLM Pre-Annotate", self.current_lang),
                tr(
                    "VLM stop requested. Remaining queued images were cancelled; waiting for active request(s) to finish.",
                    self.current_lang,
                ),
            )
            self.request_stop_vlm_preannotation(confirm=False)
            event.ignore()
            return
        if getattr(self, "external_training_thread", None) is not None and self.external_training_thread.isRunning():
            QMessageBox.information(
                self,
                tr("Training", self.current_lang),
                tr("External backend training is running. Please wait for it to finish before closing TaxaMask.", self.current_lang),
            )
            event.ignore()
            return
        task_label = self._active_project_bound_background_task()
        if task_label:
            QMessageBox.information(
                self,
                tr("Project is busy", self.current_lang),
                tr("{0} is still running. Wait for it to finish before closing TaxaMask.", self.current_lang).format(task_label),
            )
            event.ignore()
            return
        self._shutdown_background_workers()
        self._flush_pending_project_save(defer_for_navigation=False)
        recent_project_path = self._active_recent_project_path()
        if recent_project_path:
            self.config.set("last_project_path", recent_project_path)
        self.config.save()
        event.accept()
        os._exit(0)

    def _active_recent_project_path(self):
        active_kind = getattr(self, "active_project_kind", "start")
        if active_kind == "start":
            active_kind = getattr(self, "last_workbench_kind", "image")
        source_kind = getattr(self, "active_project_source_kind", active_kind)
        if active_kind == "tif":
            return getattr(self.tif_project, "current_project_path", None) or ""
        if active_kind == "image":
            if source_kind == "stl":
                return getattr(self.stl_project, "current_project_path", None) or getattr(self, "active_project_entry_path", "")
            return getattr(self.project, "current_project_path", None) or getattr(self, "active_project_entry_path", "")
        return ""

    def _shutdown_background_workers(self):
        tif_workbench = getattr(self, "tif_workbench", None)
        if tif_workbench is not None and hasattr(tif_workbench, "release_volume_renderer"):
            try:
                tif_workbench.release_volume_renderer()
            except Exception:
                pass
        agent_panel = getattr(self, "agent_panel", None)
        if agent_panel is not None and hasattr(agent_panel, "stop_dashboard"):
            try:
                agent_panel.stop_dashboard()
            except Exception:
                pass
        if self.sam_thread and self.sam_thread.isRunning():
            self.sam_thread.quit()
            self.sam_thread.wait(1000)
        thread = getattr(self, "image_import_thread", None)
        if thread is not None and thread.isRunning():
            thread.wait(30000)
        thread = getattr(self, "parts_model_preload_thread", None)
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def destroy(self, destroyWindow=True, destroySubWindows=True):
        self._shutdown_background_workers()
        return super().destroy(destroyWindow, destroySubWindows)

    def _schedule_project_save(self, reason="pending_change", **context):
        self.project_save_pending = True
        self.project_save_context = {
            "reason": reason,
            "_scheduled_project_path": str(getattr(self.project, "current_project_path", "") or ""),
            **context,
        }
        self.project_save_timer.start(self.project_autosave_delay_ms)

    def _defer_project_save_for_active_navigation(self):
        if not self.project_save_pending:
            return
        self.project_last_image_switch_at = time.monotonic()
        self.project_save_timer.start(self.project_autosave_delay_ms)

    def _flush_pending_project_save(self, force=False, defer_for_navigation=True):
        if self.project_save_timer.isActive():
            self.project_save_timer.stop()

        if not self.project.current_project_path:
            self.project_save_pending = False
            self.project_save_context = {}
            return False

        if not force and not self.project_save_pending:
            return False

        if defer_for_navigation and not force and self.project_last_image_switch_at:
            elapsed_ms = (time.monotonic() - self.project_last_image_switch_at) * 1000.0
            if elapsed_ms < self.project_save_navigation_idle_ms:
                remaining_ms = max(
                    250,
                    int(self.project_save_navigation_idle_ms - elapsed_ms),
                )
                self.project_save_timer.start(remaining_ms)
                return False

        context = getattr(self, "project_save_context", {}) or {}
        scheduled_path = os.path.normcase(os.path.abspath(str(context.get("_scheduled_project_path") or "")))
        current_path = os.path.normcase(os.path.abspath(str(self.project.current_project_path or "")))
        if scheduled_path and scheduled_path != current_path:
            runtime_log_event(
                "stale_project_save_skipped",
                scheduled_project=scheduled_path,
                current_project=current_path,
            )
            self.project_save_pending = False
            self.project_save_context = {}
            return False
        log_context = {key: value for key, value in context.items() if not str(key).startswith("_")}
        try:
            try:
                self.project.save_project(force=force)
            except TypeError as exc:
                if "force" not in str(exc):
                    raise
                self.project.save_project()
        except Exception:
            runtime_log_exception(
                "project_save_failed",
                *sys.exc_info(),
            )
            runtime_log_event(
                "project_save_failed_context",
                project=getattr(self.project, "current_project_path", ""),
                image_count=len(self.project.project_data.get("images", []) or []),
                label_count=len(self.project.project_data.get("labels", {}) or {}),
                **log_context,
            )
            raise
        if context:
            runtime_log_event(
                "project_save_ok",
                project=getattr(self.project, "current_project_path", ""),
                image_count=len(self.project.project_data.get("images", []) or []),
                label_count=len(self.project.project_data.get("labels", {}) or {}),
                **log_context,
            )
        self.project_save_pending = False
        self.project_save_context = {}
        return True

    def _refresh_project_bound_views(self):
        self._apply_project_mode_tabs()
        if getattr(self, "active_project_kind", "image") == "start":
            self._update_start_center_texts()
            if hasattr(self, "tabs"):
                self.tabs.setCurrentWidget(self.start_center_widget)
            return
        if getattr(self, "active_project_kind", "image") == "tif":
            self._ensure_tif_workbench().refresh_project()
            if hasattr(self, "tabs"):
                self.tabs.setCurrentWidget(self.tif_workbench)
            return
        self.refresh_file_list()
        self.refresh_ui()
        self.refresh_route_table()

    def _project_image_count(self):
        try:
            return len([img for img in self.project.project_data.get("images", []) if img])
        except Exception:
            return 0

    def _prepare_image_list_for_project_open(self):
        image_count = self._project_image_count()
        self._image_list_state_cache = None
        should_collapse = image_count >= LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD

        for group_key, _label in self._all_image_group_definitions():
            self.image_list_group_collapsed[str(group_key)] = should_collapse
        if not should_collapse:
            return False
        self.current_image = None
        self.log(
            tr(
                "Large project detected ({0} images). The image groups are collapsed for faster opening; expand a group when you are ready to review images.",
                self.current_lang,
            ).format(image_count)
        )
        return True

    def _preload_2d_stl_models_after_open(self):
        if getattr(self, "active_project_kind", "image") != "image":
            return
        if self._project_image_count() >= LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD:
            self.log(
                tr(
                    "Large project opened without startup model preloading. Models will load when auto annotation or training starts.",
                    self.current_lang,
                )
            )
            return
        QTimer.singleShot(0, self.ensure_2d_stl_models_preloaded)

    def _ensure_tab_visible(self, widget, title):
        if not hasattr(self, "tabs") or widget is None:
            return
        if self.tabs.indexOf(widget) < 0:
            self.tabs.addTab(widget, title)

    def _remove_tab_if_present(self, widget):
        if not hasattr(self, "tabs") or widget is None:
            return
        index = self.tabs.indexOf(widget)
        if index >= 0:
            self.tabs.removeTab(index)

    def _apply_project_mode_tabs(self):
        if not hasattr(self, "tabs"):
            return
        if getattr(self, "active_project_kind", "image") == "start":
            for widget in (
                self.workbench_widget,
                self.blink_lab,
                getattr(self, "tif_workbench", None),
                getattr(self, "pdf_widget", None),
            ):
                self._remove_tab_if_present(widget)
            self._ensure_tab_visible(self.start_center_widget, tr("Start Center", self.current_lang))
            self.tabs.setCurrentWidget(self.start_center_widget)
            return
        if getattr(self, "active_project_kind", "image") == "tif":
            self._ensure_tif_workbench()
            self._remove_tab_if_present(self.start_center_widget)
            self._remove_tab_if_present(self.workbench_widget)
            self._remove_tab_if_present(self.blink_lab)
            self._remove_tab_if_present(getattr(self, "pdf_widget", None))
            self._ensure_tab_visible(self.tif_workbench, tr("TIF Volume Workbench", self.current_lang))
            self.tabs.setCurrentWidget(self.tif_workbench)
            return
        self._remove_tab_if_present(self.start_center_widget)
        self._remove_tab_if_present(getattr(self, "tif_workbench", None))
        self._remove_tab_if_present(self.blink_lab)
        self._ensure_tab_visible(self.workbench_widget, tr("Labeling Workbench", self.current_lang))
        if self.tabs.currentWidget() is None or self.tabs.currentWidget() is getattr(self, "tif_workbench", None):
            self.tabs.setCurrentWidget(self.workbench_widget)

    def _is_tif_project_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return False
        if self._is_tif_sqlite_project_manifest_payload(payload):
            return True
        return (
            isinstance(payload, dict)
            and payload.get("schema_version") == TIF_PROJECT_SCHEMA_VERSION
            and payload.get("project_type") == TIF_PROJECT_TYPE
        )

    def _is_stl_project_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return False
        return (
            isinstance(payload, dict)
            and payload.get("schema_version") == STL_PROJECT_SCHEMA_VERSION
            and payload.get("project_type") == STL_PROJECT_TYPE
        )

    def _read_project_probe_payload(self, path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _is_sqlite_project_manifest_payload(self, payload):
        return (
            isinstance(payload, dict)
            and payload.get("schema_version") == PROJECT_MANIFEST_SCHEMA_VERSION
            and payload.get("storage_backend") == SQLITE_BACKEND
        )

    def _is_tif_sqlite_project_manifest_payload(self, payload):
        return self._is_sqlite_project_manifest_payload(payload) and payload.get("project_type") == TIF_PROJECT_TYPE

    def _is_2d_sqlite_project_manifest_payload(self, payload):
        return self._is_sqlite_project_manifest_payload(payload) and payload.get("project_type") != TIF_PROJECT_TYPE

    def _is_legacy_2d_json_project_payload(self, payload):
        if not isinstance(payload, dict):
            return False
        if self._is_sqlite_project_manifest_payload(payload):
            return False
        if (
            payload.get("schema_version") in {TIF_PROJECT_SCHEMA_VERSION, STL_PROJECT_SCHEMA_VERSION}
            or payload.get("project_type") in {TIF_PROJECT_TYPE, STL_PROJECT_TYPE}
        ):
            return False
        project_keys = {"images", "labels", "taxonomy", "locator_scope", "project_template"}
        return bool(project_keys.intersection(payload.keys())) and (
            isinstance(payload.get("images", []), list)
            or isinstance(payload.get("labels", {}), dict)
        )

    def _is_legacy_2d_json_project_file(self, path):
        return self._is_legacy_2d_json_project_payload(self._read_project_probe_payload(path))

    def _candidate_manifest_paths_for_sqlite_database(self, path):
        database_path = os.path.abspath(str(path))
        directory = os.path.dirname(database_path) or "."
        filename = os.path.basename(database_path)
        candidates = []
        suffixes = [
            (".taxamask.sqlite", ".sqlite_manifest.json"),
            (".taxamask_tif.sqlite", ".tif_sqlite_manifest.json"),
        ]
        for db_suffix, manifest_suffix in suffixes:
            if filename.endswith(db_suffix):
                candidates.append(os.path.join(directory, f"{filename[:-len(db_suffix)]}{manifest_suffix}"))
        for name in os.listdir(directory) if os.path.isdir(directory) else []:
            if name.endswith(".sqlite_manifest.json") or name.endswith(".tif_sqlite_manifest.json"):
                candidates.append(os.path.join(directory, name))
        seen = set()
        unique = []
        for candidate in candidates:
            norm = os.path.normcase(os.path.normpath(os.path.abspath(str(candidate))))
            if norm not in seen:
                seen.add(norm)
                unique.append(os.path.abspath(str(candidate)))
        return unique

    def _manifest_for_sqlite_database_file(self, path):
        database_path = os.path.abspath(str(path))
        database_norm = os.path.normcase(os.path.normpath(database_path))
        for manifest_path in self._candidate_manifest_paths_for_sqlite_database(database_path):
            if not os.path.exists(manifest_path):
                continue
            try:
                payload = read_project_manifest(manifest_path)
                resolved_db = resolve_manifest_database_path(manifest_path, payload)
            except Exception:
                continue
            resolved_norm = os.path.normcase(os.path.normpath(os.path.abspath(resolved_db)))
            if resolved_norm == database_norm:
                return os.path.abspath(manifest_path)
        return ""

    def _is_project_sqlite_database_file(self, path):
        filename = os.path.basename(str(path or ""))
        return filename.endswith(".taxamask.sqlite") or filename.endswith(".taxamask_tif.sqlite")

    def _active_sqlite_project_manager(self):
        if getattr(self, "active_project_kind", "image") == "tif":
            manager = getattr(self, "tif_project", None)
        else:
            manager = getattr(self, "project", None)
        if manager is None:
            return None
        is_sqlite = getattr(manager, "is_sqlite_project", None)
        if not callable(is_sqlite) or not is_sqlite():
            return None
        return manager

    def _flush_active_sqlite_project_before_maintenance(self):
        manager = self._active_sqlite_project_manager()
        if manager is None:
            return None
        if manager is getattr(self, "project", None):
            flushed = self._flush_pending_project_save(force=True, defer_for_navigation=False)
            if not flushed:
                try:
                    manager.save_project(force=True)
                except TypeError:
                    manager.save_project()
        else:
            manager.save_project()
        return manager

    def _sqlite_maintenance_default_dir(self, manager):
        database_path = str(getattr(manager, "current_database_path", "") or "")
        if database_path:
            return os.path.dirname(os.path.abspath(database_path)) or "."
        project_path = str(getattr(manager, "current_project_path", "") or "")
        return os.path.dirname(os.path.abspath(project_path)) if project_path else self._default_outputs_root()

    def backup_current_sqlite_project(self):
        manager = self._flush_active_sqlite_project_before_maintenance()
        if manager is None:
            QMessageBox.information(
                self,
                tr("Backup SQLite Project", self.current_lang),
                tr("The current project is not a SQLite-backed project.", self.current_lang),
            )
            return
        try:
            result = backup_sqlite_project_manifest(
                manager.current_project_path,
                min_interval_seconds=0,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                tr("Backup SQLite Project", self.current_lang),
                tr("SQLite project backup failed.\n\n{0}", self.current_lang).format(str(exc)),
            )
            return
        if not result.backup_manifest_path:
            QMessageBox.information(
                self,
                tr("Backup SQLite Project", self.current_lang),
                tr("SQLite project backup was skipped because a recent backup already exists.", self.current_lang),
            )
            return
        self.log(
            tr(
                "SQLite project backup created. Manifest: {0}; database: {1}",
                self.current_lang,
            ).format(result.backup_manifest_path, result.backup_database_path)
        )
        QMessageBox.information(
            self,
            tr("Backup SQLite Project", self.current_lang),
            tr(
                "SQLite backup created.\n\nOpen this manifest to inspect the backup:\n{0}",
                self.current_lang,
            ).format(result.backup_manifest_path),
        )

    def export_current_project_legacy_json(self):
        manager = self._flush_active_sqlite_project_before_maintenance()
        if manager is None:
            QMessageBox.information(
                self,
                tr("Export Legacy JSON", self.current_lang),
                tr("The current project is not a SQLite-backed project.", self.current_lang),
            )
            return
        default_dir = os.path.join(self._sqlite_maintenance_default_dir(manager), "legacy_json_exports")
        os.makedirs(default_dir, exist_ok=True)
        project_name = str(getattr(manager, "project_data", {}).get("name") or "project").strip() or "project"
        safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in project_name).strip("_") or "project"
        default_path = os.path.join(default_dir, f"{safe_name}.legacy_export_{time.strftime('%Y%m%d_%H%M%S')}.json")
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Export Legacy JSON", self.current_lang),
            default_path,
            tr("TaxaMask Projects (*.json);;All Files (*)", self.current_lang),
        )
        if not output_path:
            return
        try:
            result = export_sqlite_project_to_legacy_json(manager.current_project_path, output_path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                tr("Export Legacy JSON", self.current_lang),
                tr("Legacy JSON export failed.\n\n{0}", self.current_lang).format(str(exc)),
            )
            return
        self.log(
            tr(
                "Exported SQLite project to legacy JSON for audit. Path: {0}; stats: {1}",
                self.current_lang,
            ).format(result.output_path, result.stats)
        )
        QMessageBox.information(
            self,
            tr("Export Legacy JSON", self.current_lang),
            tr("Legacy JSON export created:\n{0}", self.current_lang).format(result.output_path),
        )

    def open_current_sqlite_migration_report(self):
        manager = self._active_sqlite_project_manager()
        if manager is None:
            QMessageBox.information(
                self,
                tr("Open Migration Report", self.current_lang),
                tr("The current project is not a SQLite-backed project.", self.current_lang),
            )
            return
        report_path = sqlite_project_migration_report_path(manager.current_project_path)
        if not report_path:
            QMessageBox.information(
                self,
                tr("Open Migration Report", self.current_lang),
                tr("No migration report is recorded for this project.", self.current_lang),
            )
            return
        if not open_path(report_path):
            QMessageBox.information(
                self,
                tr("Open Migration Report", self.current_lang),
                tr("Migration report path:\n{0}", self.current_lang).format(report_path),
            )

    def new_project(self):
        if not self._ensure_project_switch_available():
            return
        d = QFileDialog.getExistingDirectory(
            self,
            tr("New Project Directory", self.current_lang),
            self._default_project_dialog_dir("image"),
        )
        if d:
            name, ok = QInputDialog.getText(self, tr("New Project", self.current_lang), tr("Project Name:", self.current_lang))
            if ok and name:
                template = self._choose_project_template()
                if template is None:
                    return
                self._flush_pending_project_save(defer_for_navigation=False)
                self.project.create_project(name, d, template_id=template["template_id"])
                self.active_project_kind = "image"
                self.last_workbench_kind = "image"
                self.active_project_source_kind = "image"
                self.active_project_entry_path = self.project.current_project_path or ""
                self.config.set("last_project_path", self.active_project_entry_path)
                self._refresh_project_bound_views()
                self.ensure_2d_stl_models_preloaded()
                self.canvas.load_image("") 

    def new_tif_project(self):
        if not self._ensure_project_switch_available():
            return
        if not self._is_tif_workflow_enabled():
            self._show_tif_workflow_unavailable()
            return
        d = QFileDialog.getExistingDirectory(
            self,
            tr("New TIF Project Directory", self.current_lang),
            self._default_project_dialog_dir("tif"),
        )
        if not d:
            return
        name, ok = QInputDialog.getText(self, tr("New TIF Volume Project", self.current_lang), tr("Project Name:", self.current_lang))
        if not ok or not name:
            return
        self._flush_pending_project_save(defer_for_navigation=False)
        self.tif_project.create_project(name, d)
        self.active_project_kind = "tif"
        self.last_workbench_kind = "tif"
        self.active_project_source_kind = "tif"
        self.active_project_entry_path = self.tif_project.current_project_path or ""
        self.config.set("last_project_path", self.tif_project.current_project_path)
        self._refresh_project_bound_views()
        self.log(tr("Created TIF volume project: {0}", self.current_lang).format(self.tif_project.current_project_path))

    def _ensure_tif_project_open(self):
        if getattr(self, "active_project_kind", "image") != "tif" or not self.tif_project.current_project_path:
            QMessageBox.warning(
                self,
                tr("TIF Volume Workbench", self.current_lang),
                tr("Please create or open a TIF volume project first.", self.current_lang),
            )
            return False
        return True

    def import_tif_stack_action(self):
        if not self._ensure_tif_project_open():
            return
        self._ensure_tif_workbench()
        tif_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Import TIF Stack", self.current_lang),
            "",
            "TIF/TIFF (*.tif *.tiff)",
        )
        if not tif_path:
            return
        default_id = os.path.splitext(os.path.basename(tif_path))[0]
        specimen_id, ok = QInputDialog.getText(
            self,
            tr("Import TIF Stack", self.current_lang),
            tr("Specimen ID:", self.current_lang),
            text=default_id,
        )
        if not ok or not specimen_id:
            return
        try:
            result = import_tif_stack(self.tif_project, tif_path, specimen_id)
        except Exception as exc:
            QMessageBox.critical(self, tr("Import TIF Stack", self.current_lang), str(exc))
            return
        self.tif_workbench.refresh_project()
        self.tabs.setCurrentWidget(self.tif_workbench)
        report_path = result.get("report_path", "")
        self.log(tr("Imported TIF stack for specimen {0}. Report: {1}", self.current_lang).format(specimen_id, report_path))

    def import_amira_directory_action(self):
        if not self._ensure_tif_project_open():
            return
        self._ensure_tif_workbench()
        source_dir = QFileDialog.getExistingDirectory(
            self,
            tr("Import AMIRA Directory", self.current_lang),
            self.tif_project.project_dir,
        )
        if not source_dir:
            return
        default_id = os.path.basename(os.path.normpath(source_dir))
        specimen_id, ok = QInputDialog.getText(
            self,
            tr("Import AMIRA Directory", self.current_lang),
            tr("Specimen ID:", self.current_lang),
            text=default_id,
        )
        if not ok or not specimen_id:
            return
        try:
            result = import_amira_directory(self.tif_project, source_dir, specimen_id)
        except Exception as exc:
            QMessageBox.critical(self, tr("Import AMIRA Directory", self.current_lang), str(exc))
            return
        self.tif_workbench.refresh_project()
        self.tabs.setCurrentWidget(self.tif_workbench)
        report_path = result.get("report_path", "")
        self.log(tr("Imported AMIRA directory for specimen {0}. Report: {1}", self.current_lang).format(specimen_id, report_path))

    def import_stl_rendered_views_action(self):
        source_dir = QFileDialog.getExistingDirectory(
            self,
            tr("Import STL Rendered Views to Labeling Workbench", self.current_lang),
            self._current_2d_project_dir(),
        )
        if not source_dir:
            return
        try:
            result = import_stl_rendered_views_into_2d_project(self.project, source_dir)
        except Exception as exc:
            QMessageBox.critical(self, tr("Import STL Rendered Views to Labeling Workbench", self.current_lang), str(exc))
            return
        self.active_project_kind = "image"
        self.last_workbench_kind = "image"
        self.active_project_source_kind = "image"
        self.active_project_entry_path = self.project.current_project_path or ""
        self.config.set("last_project_path", self.active_project_entry_path)
        self._refresh_project_bound_views()
        self.tabs.setCurrentWidget(self.workbench_widget)
        self.ensure_2d_stl_models_preloaded()
        self.log(
            tr("Imported STL rendered views into the Labeling Workbench from {0}. Registered views: {1}, specimens: {2}, unparsed files: {3}.", self.current_lang).format(
                source_dir,
                result.get("registered_count", 0),
                result.get("specimen_count", 0),
                result.get("unparsed_count", 0),
            )
        )

    def open_pdf_evidence_tools(self):
        self._ensure_pdf_widget()
        index = self.tabs.indexOf(self.pdf_widget)
        if index < 0:
            index = self.tabs.addTab(self.pdf_widget, tr("PDF Evidence Tools", self.current_lang))
        self.tabs.setCurrentIndex(index)

    def open_pdf_multimodal_api_settings(self):
        self.open_pdf_evidence_tools()
        pdf_widget = getattr(self, "pdf_widget", None)
        if pdf_widget is None:
            return
        if hasattr(pdf_widget, "tabs"):
            try:
                pdf_widget.tabs.setCurrentIndex(0)
            except Exception:
                pass
        if hasattr(pdf_widget, "api_panel"):
            try:
                pdf_widget.api_panel.setVisible(True)
            except Exception:
                pass
        target = getattr(pdf_widget, "mllm_group", None) or getattr(pdf_widget, "api_panel", None)
        scroll = getattr(pdf_widget, "main_scroll", None)
        if target is not None and scroll is not None:
            try:
                scroll.ensureWidgetVisible(target)
            except Exception:
                pass
        use_same = True
        same_widget = getattr(pdf_widget, "check_mllm_same_as_text", None)
        if same_widget is not None and hasattr(same_widget, "isChecked"):
            try:
                use_same = bool(same_widget.isChecked())
            except Exception:
                use_same = True
        editor = (
            getattr(pdf_widget, "edit_api_key", None)
            if use_same
            else getattr(pdf_widget, "edit_mllm_api_key", None)
        )
        if editor is None:
            editor = getattr(pdf_widget, "edit_mllm_model", None) or getattr(pdf_widget, "edit_model", None)
        if editor is not None and hasattr(editor, "setFocus"):
            try:
                editor.setFocus()
            except Exception:
                pass

    def _choose_project_template(self):
        templates = iter_project_templates()
        if not templates:
            return {"template_id": DEFAULT_PROJECT_TEMPLATE_ID}
        labels = [tr(template["display_name"], self.current_lang) for template in templates]
        selected, ok = QInputDialog.getItem(
            self,
            tr("New Project", self.current_lang),
            tr("Project Template:", self.current_lang),
            labels,
            0,
            False,
        )
        if not ok:
            return None
        try:
            return templates[labels.index(selected)]
        except ValueError:
            return templates[0]

    def open_project(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            tr("Open Project", self.current_lang),
            self._default_open_project_dir(),
            tr(
                "TaxaMask Project Entry (*.sqlite_manifest.json *.tif_sqlite_manifest.json *.json);;SQLite Database (*.taxamask.sqlite *.taxamask_tif.sqlite);;All Files (*)",
                self.current_lang,
            ),
        )
        if f:
            self.open_project_path(f)

    def _confirm_legacy_2d_json_migration(self, path):
        message = tr(
            "This is an older 2D JSON project. TaxaMask now stores 2D projects in SQLite so large annotation projects are saved incrementally instead of rewriting one large JSON file.\n\nThe old JSON will not be overwritten. A SQLite database, a manifest file, a migration report, and a legacy JSON backup will be created next to the project.\n\nMigrate and open the SQLite project now?",
            self.current_lang,
        )
        reply = themed_yes_no_question(
            self,
            tr("Migrate 2D Project to SQLite", self.current_lang),
            f"{message}\n\n{path}",
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        return reply == QMessageBox.Yes

    def _existing_sqlite_manifest_for_legacy_json(self, path):
        manifest_path = default_sqlite_manifest_path(path)
        if not os.path.exists(manifest_path):
            return ""
        try:
            read_project_manifest(manifest_path)
        except Exception:
            return ""
        return os.path.abspath(manifest_path)

    def _confirm_open_existing_sqlite_migration(self, manifest_path):
        reply = themed_yes_no_question(
            self,
            tr("Migrate 2D Project to SQLite", self.current_lang),
            tr(
                "A migrated SQLite version already exists for this old JSON project.\n\nOpen the existing SQLite manifest instead?\n\n{0}",
                self.current_lang,
            ).format(manifest_path),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        return reply == QMessageBox.Yes

    def _confirm_legacy_tif_json_migration(self, path):
        message = tr(
            "This is an older TIF JSON project. TaxaMask can now store the TIF project index in SQLite while keeping the large volume and label sidecar files on disk.\n\nThe old JSON will not be overwritten. The TIF volume sidecar files will not be moved. A SQLite database, a manifest file, a migration report, and a legacy JSON backup will be created next to the project.\n\nMigrate and open the SQLite project now?",
            self.current_lang,
        )
        reply = themed_yes_no_question(
            self,
            tr("Migrate TIF Project to SQLite", self.current_lang),
            f"{message}\n\n{path}",
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        return reply == QMessageBox.Yes

    def _existing_tif_sqlite_manifest_for_legacy_json(self, path):
        manifest_path = default_tif_sqlite_manifest_path(path)
        if not os.path.exists(manifest_path):
            return ""
        try:
            payload = read_project_manifest(manifest_path)
        except Exception:
            return ""
        if payload.get("project_type") != TIF_PROJECT_TYPE:
            return ""
        return os.path.abspath(manifest_path)

    def _confirm_open_existing_tif_sqlite_migration(self, manifest_path):
        reply = themed_yes_no_question(
            self,
            tr("Migrate TIF Project to SQLite", self.current_lang),
            tr(
                "A migrated SQLite version already exists for this old TIF JSON project.\n\nOpen the existing SQLite manifest instead?\n\n{0}",
                self.current_lang,
            ).format(manifest_path),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        return reply == QMessageBox.Yes

    def _migrate_legacy_2d_project_with_progress(self, path):
        progress = QProgressDialog(
            tr("Migrating 2D project to SQLite...", self.current_lang),
            "",
            0,
            100,
            self,
        )
        progress.setWindowTitle(tr("Migrate 2D Project to SQLite", self.current_lang))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)
        self._prepare_progress_dialog(progress, width=560)
        progress.show()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

        def on_progress(done, total, message):
            total = max(0, int(total or 0))
            done = max(0, int(done or 0))
            if total > 0:
                if progress.maximum() != total:
                    progress.setRange(0, total)
                progress.setValue(min(done, total))
            else:
                progress.setRange(0, 0)
            progress.setLabelText(str(message or ""))
            if app is not None:
                app.processEvents()

        try:
            result = migrate_legacy_2d_json_to_sqlite(path, progress_callback=on_progress)
        finally:
            progress.close()
            progress.deleteLater()
            if app is not None:
                app.processEvents()
        return result

    def _migrate_legacy_tif_project_with_progress(self, path):
        progress = QProgressDialog(
            tr("Migrating TIF project to SQLite...", self.current_lang),
            "",
            0,
            100,
            self,
        )
        progress.setWindowTitle(tr("Migrate TIF Project to SQLite", self.current_lang))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)
        self._prepare_progress_dialog(progress, width=560)
        progress.show()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

        def on_progress(done, total, message):
            total = max(0, int(total or 0))
            done = max(0, int(done or 0))
            if total > 0:
                if progress.maximum() != total:
                    progress.setRange(0, total)
                progress.setValue(min(done, total))
            else:
                progress.setRange(0, 0)
            progress.setLabelText(str(message or ""))
            if app is not None:
                app.processEvents()

        try:
            result = migrate_legacy_tif_json_to_sqlite(path, progress_callback=on_progress)
        finally:
            progress.close()
            progress.deleteLater()
            if app is not None:
                app.processEvents()
        return result

    def open_project_path(self, path):
        if not self._ensure_project_switch_available():
            return
        f = os.path.abspath(str(path))
        runtime_log_event("open_project_begin", path=f)
        self._flush_pending_project_save(defer_for_navigation=False)
        if self._is_project_sqlite_database_file(f):
            manifest_path = self._manifest_for_sqlite_database_file(f)
            if not manifest_path:
                QMessageBox.warning(
                    self,
                    tr("Project entry file not found", self.current_lang),
                    tr(
                        "This is a SQLite database file, but TaxaMask could not find the matching project entry file. Please open the project entry file next to it instead:\n\n2D: *.sqlite_manifest.json\nTIF: *.tif_sqlite_manifest.json\n\nSelected database:\n{0}",
                        self.current_lang,
                    ).format(f),
                )
                runtime_log_event("open_project_sqlite_database_without_manifest", path=f)
                return
            self.log(
                tr(
                    "Selected a SQLite database file. Opening its project entry instead: {0}",
                    self.current_lang,
                ).format(manifest_path)
            )
            runtime_log_event("open_project_sqlite_database_redirected", path=f, manifest=manifest_path)
            f = manifest_path
        payload = self._read_project_probe_payload(f)
        if self._is_legacy_2d_json_project_payload(payload):
            existing_manifest = self._existing_sqlite_manifest_for_legacy_json(f)
            if existing_manifest:
                if not self._confirm_open_existing_sqlite_migration(existing_manifest):
                    runtime_log_event("open_project_existing_sqlite_manifest_cancelled", path=f, manifest=existing_manifest)
                    return
                f = existing_manifest
                payload = self._read_project_probe_payload(f)
            else:
                if not self._confirm_legacy_2d_json_migration(f):
                    runtime_log_event("open_project_legacy_json_migration_cancelled", path=f)
                    return
                try:
                    migration_result = self._migrate_legacy_2d_project_with_progress(f)
                except Exception as exc:
                    runtime_log_exception("open_project_legacy_json_migration_failed", *sys.exc_info())
                    QMessageBox.critical(
                        self,
                        tr("Migrate 2D Project to SQLite", self.current_lang),
                        tr("2D project migration failed. The old JSON was not modified.\n\n{0}", self.current_lang).format(str(exc)),
                    )
                    return
                f = os.path.abspath(str(migration_result.manifest_path))
                runtime_log_event(
                    "open_project_legacy_json_migrated",
                    source=migration_result.source_json_path,
                    manifest=f,
                    database=migration_result.database_path,
                    image_count=migration_result.stats.get("image_count", 0),
                    label_count=migration_result.stats.get("label_count", 0),
                )
                self.log(
                    tr(
                        "Migrated legacy 2D JSON project to SQLite. Manifest: {0}; database: {1}; report: {2}",
                        self.current_lang,
                    ).format(f, migration_result.database_path, migration_result.report_path)
                )
        if self._is_tif_project_file(f):
            if not self._is_tif_workflow_enabled():
                self._show_tif_workflow_unavailable()
                return
            if (
                isinstance(payload, dict)
                and payload.get("schema_version") == TIF_PROJECT_SCHEMA_VERSION
                and payload.get("project_type") == TIF_PROJECT_TYPE
            ):
                existing_manifest = self._existing_tif_sqlite_manifest_for_legacy_json(f)
                if existing_manifest:
                    if not self._confirm_open_existing_tif_sqlite_migration(existing_manifest):
                        runtime_log_event("open_tif_existing_sqlite_manifest_cancelled", path=f, manifest=existing_manifest)
                        return
                    f = existing_manifest
                else:
                    if not self._confirm_legacy_tif_json_migration(f):
                        runtime_log_event("open_tif_legacy_json_migration_cancelled", path=f)
                        return
                    try:
                        migration_result = self._migrate_legacy_tif_project_with_progress(f)
                    except Exception as exc:
                        runtime_log_exception("open_tif_legacy_json_migration_failed", *sys.exc_info())
                        QMessageBox.critical(
                            self,
                            tr("Migrate TIF Project to SQLite", self.current_lang),
                            tr("TIF project migration failed. The old JSON was not modified.\n\n{0}", self.current_lang).format(str(exc)),
                        )
                        return
                    f = os.path.abspath(str(migration_result.manifest_path))
                    runtime_log_event(
                        "open_tif_legacy_json_migrated",
                        source=migration_result.source_json_path,
                        manifest=f,
                        database=migration_result.database_path,
                        specimen_count=migration_result.stats.get("specimen_count", 0),
                        part_count=migration_result.stats.get("part_count", 0),
                    )
                    self.log(
                        tr(
                            "Migrated legacy TIF JSON project to SQLite. Manifest: {0}; database: {1}; report: {2}",
                            self.current_lang,
                        ).format(f, migration_result.database_path, migration_result.report_path)
                    )
            self.tif_project.load_project(f)
            self.active_project_kind = "tif"
            self.last_workbench_kind = "tif"
            self.active_project_source_kind = "tif"
            self.active_project_entry_path = f
            self.config.set("last_project_path", f)
            self.log(tr("Opened TIF volume project: {0}", self.current_lang).format(f))
        elif self._is_stl_project_file(f):
            self.stl_project.load_project(f)
            result = register_stl_rendered_views_for_2d_review(self.stl_project, self.project)
            self.active_project_kind = "image"
            self.last_workbench_kind = "image"
            self.active_project_source_kind = "stl"
            self.active_project_entry_path = f
            self.config.set("last_project_path", f)
            self._prepare_image_list_for_project_open()
            self.log(tr("Opened STL rendered-view project and registered it into the Labeling Workbench: {0}", self.current_lang).format(f))
            self.log(
                tr("Registered STL rendered-view project into the Labeling Workbench. Views: {0}, missing files: {1}.", self.current_lang).format(
                    result.get("registered_count", 0),
                    result.get("missing_count", 0),
                )
            )
        else:
            self.project.load_project(f)
            self.active_project_kind = "image"
            self.last_workbench_kind = "image"
            self.active_project_source_kind = "image"
            self.active_project_entry_path = f
            self.config.set("last_project_path", f)
            self._prepare_image_list_for_project_open()
        self._refresh_project_bound_views()
        if hasattr(self.engine, "cascade_manager"):
            self.engine.cascade_manager.project_manager = self.project
        self._sync_blink_lab_model_profile_defaults()
        if getattr(self, "active_project_kind", "image") == "image":
            self._preload_2d_stl_models_after_open()
        runtime_log_event(
            "open_project_ok",
            path=f,
            active_kind=getattr(self, "active_project_kind", ""),
            source_kind=getattr(self, "active_project_source_kind", ""),
            image_count=len(self.project.project_data.get("images", []) or []),
            label_count=len(self.project.project_data.get("labels", {}) or {}),
        )
        self.canvas.load_image("")

    def _format_relocation_preview(self, matches, limit=8):
        lines = []
        for item in list(matches or [])[:limit]:
            old_name = os.path.basename(str(item.get("old_path", "")))
            new_path = str(item.get("new_path", ""))
            lines.append(f"{old_name} -> {new_path}")
        remaining = max(0, len(matches or []) - limit)
        if remaining:
            lines.append(f"... +{remaining}")
        return "\n".join(lines) if lines else "-"

    def check_relocate_project_images(self):
        health = self.project.get_image_path_health()
        message = tr("Project has {0}/{1} image paths available. Missing: {2}.", self.current_lang).format(
            health["existing_count"],
            health["total"],
            health["missing_count"],
        )
        if health["missing_count"] <= 0:
            QMessageBox.information(
                self,
                tr("Project Image Health", self.current_lang),
                tr("All project image paths are available.", self.current_lang),
            )
            self.log(message)
            return

        self.log(message)
        new_root = QFileDialog.getExistingDirectory(self, tr("Select New Image Root", self.current_lang))
        if not new_root:
            return

        preview = self.project.preview_image_path_remap(new_root)
        matches = preview.get("matches", [])
        if not matches:
            QMessageBox.information(
                self,
                tr("Relocation Preview", self.current_lang),
                tr("No missing image paths could be matched under the selected folder.", self.current_lang),
            )
            return

        preview_text = self._format_relocation_preview(matches)
        reply = themed_yes_no_question(
            self,
            tr("Relocation Preview", self.current_lang),
            tr("Matched {0} missing image path(s). Still unresolved: {1}.\n\nPreview:\n{2}\n\nApply this remap and save the project?", self.current_lang).format(
                len(matches),
                len(preview.get("unresolved", [])),
                preview_text,
            ),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        if reply != QMessageBox.Yes:
            return

        self._flush_pending_project_save(defer_for_navigation=False)
        changed = self.project.apply_image_path_remap(matches, save=True)
        self.refresh_file_list()
        if self.current_image and not os.path.exists(self.current_image):
            self.current_image = None
            self.canvas.load_image("")
        result = tr("Remapped {0} project image path(s).", self.current_lang).format(changed)
        self.log(result)
        QMessageBox.information(self, tr("Project Image Health", self.current_lang), result)
