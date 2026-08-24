import hashlib

try:
    from AntSleap.ui.main_window_stage7_dependencies import *
    from AntSleap.core.safe_io import read_bytes_bounded_in_root
except ImportError:
    from ui.main_window_stage7_dependencies import *
    from core.safe_io import read_bytes_bounded_in_root


class MainWindowModelManagementMixin:
    def _capture_project_task_context(self):
        project = getattr(self, "project", None)
        path = str(getattr(project, "current_project_path", "") or "")
        normalized_path = os.path.normcase(os.path.abspath(path)) if path else ""
        return {"project": project, "project_path": normalized_path}

    def _project_task_context_matches(self, context):
        context = context if isinstance(context, dict) else {}
        project = getattr(self, "project", None)
        path = str(getattr(project, "current_project_path", "") or "")
        normalized_path = os.path.normcase(os.path.abspath(path)) if path else ""
        return project is context.get("project") and normalized_path == str(context.get("project_path", "") or "")

    def _log_stale_project_task_result(self, workflow, context):
        runtime_log_event(
            "stale_project_task_result_skipped",
            workflow=str(workflow or "background"),
            expected_project=str((context or {}).get("project_path", "") or ""),
            current_project=str(getattr(getattr(self, "project", None), "current_project_path", "") or ""),
        )

    def _active_tif_project_bound_task(self):
        workbench = getattr(self, "tif_workbench", None)
        if workbench is None:
            return ""

        annotation = getattr(workbench, "annotation_workflow_controller", None)
        if annotation is not None and bool(getattr(annotation, "saving_working_edit", False)):
            return tr("TIF Volume Workbench", self.current_lang)
        reference_checks = (
            (annotation, "auto_save_thread", "TIF Volume Workbench"),
            (annotation, "manual_save_thread", "TIF Volume Workbench"),
            (annotation, "promote_thread", "TIF Volume Workbench"),
            (workbench, "_label_auto_save_thread", "TIF Volume Workbench"),
            (workbench, "_label_manual_save_thread", "TIF Volume Workbench"),
            (workbench, "_promote_thread", "TIF Volume Workbench"),
            (workbench, "_tif_import_thread", "Import Complete TIF Volume"),
            (workbench, "_tif_backend_thread", "TIF Volume Workbench"),
        )
        for owner, attribute, label_key in reference_checks:
            if owner is None:
                continue
            try:
                thread = getattr(owner, attribute, None)
                if thread is None:
                    continue
                is_running = getattr(thread, "isRunning", None)
                if not callable(is_running) or is_running():
                    return tr(label_key, self.current_lang)
            except RuntimeError:
                continue

        backend_controller = getattr(workbench, "backend_panel_controller", None)
        action_running = getattr(backend_controller, "action_running", None)
        if callable(action_running):
            try:
                if action_running():
                    return tr("TIF Volume Workbench", self.current_lang)
            except RuntimeError:
                pass

        task_manager = getattr(workbench, "task_manager", None)
        if task_manager is not None:
            try:
                if task_manager.is_running():
                    return tr("TIF Volume Workbench", self.current_lang)
            except (AttributeError, RuntimeError):
                pass
        return ""

    def _active_project_bound_background_task(self):
        tif_task_label = self._active_tif_project_bound_task()
        if tif_task_label:
            return tif_task_label
        checks = (
            ("image_import_thread", "Image import"),
            ("batch_panel_split_thread", "Batch Split Plates"),
            ("external_batch_inference_thread", "Batch Inference"),
            ("inf_thread", "Batch Inference"),
            ("trainer", "Training"),
            ("external_training_thread", "Training"),
            # Input verification reads the active project's files and creates
            # a run record, so it must be treated as project-bound work too.
            ("training_preflight_thread", "Training"),
            ("dataset_export_thread", "Export"),
        )
        for attribute, label_key in checks:
            thread = getattr(self, attribute, None)
            if attribute == "batch_panel_split_thread" and thread is not None:
                return tr(label_key, self.current_lang)
            try:
                if thread is not None and thread.isRunning():
                    return tr(label_key, self.current_lang)
            except RuntimeError:
                continue
        blink_lab = getattr(self, "blink_lab", None)
        child_training_thread = getattr(blink_lab, "training_thread", None) if blink_lab is not None else None
        try:
            if child_training_thread is not None and child_training_thread.isRunning():
                return tr("Training", self.current_lang)
        except RuntimeError:
            pass
        child_preflight_thread = (
            getattr(blink_lab, "training_preflight_thread", None)
            if blink_lab is not None
            else None
        )
        try:
            if child_preflight_thread is not None and child_preflight_thread.isRunning():
                return tr("Training", self.current_lang)
        except RuntimeError:
            pass
        if (
            getattr(self, "sam_decoder_apply_pending", None)
            or getattr(self, "sam_base_reload_pending", False)
        ):
            return tr("SAM Auto-Annotation", self.current_lang)
        if getattr(self, "sam_busy", False):
            return tr("SAM Auto-Annotation", self.current_lang)
        if getattr(self, "vlm_preannotation_run_active", False):
            return tr("VLM Pre-Annotate", self.current_lang)
        return ""

    def _ensure_sam_runtime_settled(self, operation):
        if not (
            getattr(self, "sam_decoder_apply_pending", None)
            or getattr(self, "sam_base_reload_pending", False)
        ):
            return True
        message = tr(
            "SAM is still loading. Wait for the ready message before starting {0}.",
            self.current_lang,
        ).format(str(operation or "this operation"))
        self.log(message)
        runtime_log_event(
            "operation_blocked_by_sam_runtime_transition",
            operation=str(operation or "unknown"),
        )
        QMessageBox.information(
            self,
            tr("SAM is loading", self.current_lang),
            message,
        )
        return False

    def _ensure_project_switch_available(self):
        task_label = self._active_project_bound_background_task()
        if not task_label:
            return True
        QMessageBox.information(
            self,
            tr("Project is busy", self.current_lang),
            tr("{0} is still running. Wait for it to finish before switching projects.", self.current_lang).format(task_label),
        )
        runtime_log_event("project_switch_blocked_by_background_task", task=task_label)
        return False

    def refresh_model_list(self, *, allow_while_training=False):
        current_locator = self.combo_locator.currentData() if self.combo_locator.count() else None
        current_segmenter = self.combo_segmenter.currentData() if self.combo_segmenter.count() else None
        locator_signals_blocked = self.combo_locator.blockSignals(True)
        segmenter_signals_blocked = self.combo_segmenter.blockSignals(True)
        self.combo_locator.clear()
        self.combo_segmenter.clear()

        if not self.engine:
            self.combo_locator.blockSignals(locator_signals_blocked)
            self.combo_segmenter.blockSignals(segmenter_signals_blocked)
            return

        import glob
        parent_model_notes = load_parent_model_notes(self.engine.weights_dir)
        managed = self._verified_managed_parent_weights()
        active_profile = _active_profile_from_manager(self.project)
        parent_backend = active_profile.get("parent_backend", {}) if isinstance(active_profile, dict) else {}
        preferred_locator = str(parent_backend.get("locator_weights") or "")
        preferred_segmenter = str(parent_backend.get("segmenter_weights") or "")
        # 1. Populate Locators
        loc_files = glob.glob(os.path.join(self.engine.weights_dir, "locator_*.pth"))
        # Format: "20260105_1105"
        loc_timestamps = sorted([os.path.basename(f).replace("locator_", "").replace(".pth", "") for f in loc_files], reverse=True)

        if loc_timestamps:
            for ts in loc_timestamps:
                self.combo_locator.addItem(self._build_locator_combo_label(ts, parent_model_notes), ts)
        for item in managed["locator"]:
            self.combo_locator.addItem(
                f"{item['run_id']} [verified]", item["relative_path"]
            )
        if self.combo_locator.count():
            locator_choice = current_locator
            if preferred_locator and self.combo_locator.findData(preferred_locator) >= 0:
                locator_choice = preferred_locator
            locator_index = self.combo_locator.findData(locator_choice)
            self.combo_locator.setCurrentIndex(max(0, locator_index))
        else:
            self.combo_locator.addItem(tr("No Locators Found", self.current_lang), "__no_locator__")

        # 2. Populate Segmenters
        self.combo_segmenter.addItem(tr("Base SAM (Original)", self.current_lang), "BASE_SAM")

        seg_files = glob.glob(os.path.join(self.engine.weights_dir, "sam_decoder_lora_*.pth"))
        seg_timestamps = sorted([os.path.basename(f).replace("sam_decoder_lora_", "").replace(".pth", "") for f in seg_files], reverse=True)

        if seg_timestamps:
            for ts in seg_timestamps:
                self.combo_segmenter.addItem(self._build_segmenter_combo_label(ts, parent_model_notes), ts)
        for item in managed["segmenter"]:
            self.combo_segmenter.addItem(
                f"{item['run_id']} [verified]", item["relative_path"]
            )

        # Default to Base SAM (Index 0) for safety/compatibility, or latest if user prefers?
        # User strategy: "配合原始的sam模型，先达到一个很好的效果". So default to Base SAM.
        segmenter_choice = current_segmenter
        if preferred_segmenter and self.combo_segmenter.findData(preferred_segmenter) >= 0:
            segmenter_choice = preferred_segmenter
        segmenter_index = self.combo_segmenter.findData(segmenter_choice)
        if segmenter_index < 0:
            segmenter_index = 0
        self.combo_segmenter.setCurrentIndex(segmenter_index)

        self.combo_locator.blockSignals(locator_signals_blocked)
        self.combo_segmenter.blockSignals(segmenter_signals_blocked)
        if getattr(self, "active_project_kind", "start") == "image":
            self._apply_locator_selection_to_runtime(
                allow_while_training=allow_while_training
            )
            self._apply_segmenter_selection_to_runtime(
                allow_while_training=allow_while_training
            )
        self.update_model_delete_button_states()

    def _verified_managed_parent_weights(self):
        result = {"locator": [], "segmenter": []}
        is_sqlite_project = getattr(self.project, "is_sqlite_project", None)
        if (
            not self.engine
            or not self.project
            or not callable(is_sqlite_project)
            or not is_sqlite_project()
        ):
            return result
        project_path = str(self.project.current_project_path or "")
        if not project_path:
            return result
        runs_root = os.path.join(
            os.path.dirname(os.path.abspath(project_path)), "runs", "train"
        )
        try:
            recorder = TrainingRunRecorder(
                runs_root,
                database_path=self.project.current_database_path,
                recover_on_startup=False,
            )
            discovery = TrainingWeightPublisher(
                self.engine.weights_dir
            ).list_active(recorder.load)
        except Exception:
            runtime_log_exception("managed_model_discovery_failed", *sys.exc_info())
            return result
        for publication in discovery.get("publications", []):
            run_id = str(publication.get("run_id") or "")
            for artifact in publication.get("artifacts", []):
                if artifact.get("role") != "output_weights":
                    continue
                relative = str(artifact.get("relative_path") or "")
                filename = os.path.basename(relative)
                item = {
                    "run_id": run_id,
                    "artifact_id": str(artifact.get("artifact_id") or ""),
                    "relative_path": relative,
                    "expected": {
                        key: artifact.get(key)
                        for key in (
                            "entry_kind",
                            "size_bytes",
                            "hash_algorithm",
                            "digest",
                        )
                    },
                }
                if (
                    item["artifact_id"] == "locator_checkpoint"
                    and filename.startswith("locator_")
                    and filename.endswith(".pth")
                ):
                    result["locator"].append(item)
                elif (
                    item["artifact_id"] == "sam_decoder_checkpoint"
                    and filename.startswith("sam_decoder_lora_")
                    and filename.endswith(".pth")
                ):
                    result["segmenter"].append(item)
        for values in result.values():
            values.sort(key=lambda item: item["run_id"], reverse=True)
        return result

    def _verified_managed_model_path(self, reference, model_kind):
        clean_reference = str(reference or "").replace("\\", "/")
        if "/" not in clean_reference:
            return None
        group = "locator" if model_kind == "locator" else "segmenter"
        verified = self._verified_managed_parent_weights().get(group, [])
        if not any(
            item.get("relative_path") == clean_reference for item in verified
        ):
            return None
        resolver = (
            self._locator_model_path
            if model_kind == "locator"
            else self._segmenter_model_path
        )
        return resolver(clean_reference)

    def _verified_managed_model_checkpoint(self, reference, model_kind):
        clean_reference = str(reference or "").replace("\\", "/")
        if "/" not in clean_reference:
            return None
        group = "locator" if model_kind == "locator" else "segmenter"
        verified = self._verified_managed_parent_weights().get(group, [])
        matches = [
            item
            for item in verified
            if item.get("relative_path") == clean_reference
        ]
        if len(matches) != 1:
            return None
        resolver = (
            self._locator_model_path
            if model_kind == "locator"
            else self._segmenter_model_path
        )
        checkpoint_path = resolver(clean_reference)
        if not checkpoint_path:
            return None

        expected = matches[0].get("expected", {})
        expected_size = expected.get("size_bytes")
        expected_digest = str(expected.get("digest") or "").lower()
        if (
            expected.get("entry_kind") != "file"
            or not isinstance(expected_size, int)
            or isinstance(expected_size, bool)
            or expected_size <= 0
            or str(expected.get("hash_algorithm") or "").lower() != "sha256"
            or len(expected_digest) != 64
        ):
            return None
        checkpoint_payload = read_bytes_bounded_in_root(
            checkpoint_path,
            trusted_root=self.engine.weights_dir,
            max_bytes=expected_size,
        )
        observed_digest = hashlib.sha256(checkpoint_payload).hexdigest()
        if (
            len(checkpoint_payload) != expected_size
            or observed_digest != expected_digest
        ):
            return None
        result = {
            "path": checkpoint_path,
            "payload": checkpoint_payload,
            "expected": dict(expected),
        }
        if model_kind == "segmenter":
            result["base_sam"] = self._verified_managed_training_base_sam(
                matches[0].get("run_id")
            )
        return result

    def _verified_managed_training_base_sam(self, run_id):
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            raise ValueError("managed_segmenter_training_run_missing")
        project_path = os.path.abspath(
            os.fspath(getattr(self.project, "current_project_path", "") or "")
        )
        if not project_path:
            raise ValueError("managed_segmenter_project_path_missing")
        runs_root = os.path.abspath(
            os.path.join(os.path.dirname(project_path), "runs", "train")
        )
        recorder = TrainingRunRecorder(
            runs_root,
            database_path=self.project.current_database_path,
            recover_on_startup=False,
        )
        record = recorder.load(clean_run_id)
        if record.get("status") != "succeeded":
            raise ValueError("managed_segmenter_training_run_not_succeeded")

        project_ref = record.get("project_ref") or {}
        run_project_id = str(project_ref.get("project_id") or "")
        project_id = str(self.project.project_data.get("project_id") or "")
        if not run_project_id or not project_id:
            raise ValueError("managed_segmenter_project_identity_missing")
        if run_project_id != project_id:
            raise ValueError("managed_segmenter_project_identity_mismatch")

        run_dir = os.path.abspath(os.path.join(runs_root, clean_run_id))
        try:
            inside_runs = os.path.normcase(
                os.path.commonpath([runs_root, run_dir])
            ) == os.path.normcase(runs_root)
        except ValueError:
            inside_runs = False
        if not inside_runs or not os.path.isdir(run_dir):
            raise ValueError("managed_segmenter_training_run_directory_missing")
        training_evidence = training_run_initial_weight_evidence(
            self.project,
            record,
            run_dir=run_dir,
            slot="parent.sam_base",
        )

        base_sam_path = os.path.abspath(
            os.fspath(getattr(self.engine, "base_sam_path", "") or "")
        )
        if not base_sam_path:
            raise ValueError("managed_segmenter_base_sam_path_missing")
        try:
            runtime_weight = read_verified_initial_weight(
                self.project,
                {"slot": "parent.sam_base", "path": base_sam_path},
            )
        except Exception as exc:
            raise ValueError(
                "managed_segmenter_base_sam_registry_verification_failed"
            ) from exc
        expected = training_evidence["fingerprint"]
        observed = runtime_weight["observed"]
        if any(
            observed.get(field) != expected.get(field)
            for field in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
        ):
            raise ValueError("managed_segmenter_base_sam_training_run_mismatch")
        return {
            "path": runtime_weight["path"],
            "payload": runtime_weight["payload"],
            "expected": dict(observed),
            "training_evidence": training_evidence,
        }

    def _stable_runtime_base_sam(self):
        base_sam_path = os.path.abspath(
            os.fspath(getattr(self.engine, "base_sam_path", "") or "")
        )
        if not base_sam_path or not os.path.isfile(base_sam_path):
            raise ValueError("base_sam_checkpoint_missing")
        expected_size = int(os.lstat(base_sam_path).st_size)
        if expected_size <= 0:
            raise ValueError("base_sam_checkpoint_empty")
        payload = read_bytes_bounded_in_root(
            base_sam_path,
            trusted_root=self.engine.weights_dir,
            max_bytes=expected_size,
        )
        expected = {
            "entry_kind": "file",
            "size_bytes": len(payload),
            "hash_algorithm": "sha256",
            "digest": hashlib.sha256(payload).hexdigest(),
        }
        return {
            "path": base_sam_path,
            "payload": payload,
            "expected": expected,
            "training_evidence": None,
        }

    def _stable_runtime_segmenter_checkpoint(self, checkpoint_path):
        resolved_path = os.path.abspath(os.fspath(checkpoint_path or ""))
        if not resolved_path or not os.path.isfile(resolved_path):
            raise ValueError("segmenter_checkpoint_missing")
        expected_size = int(os.lstat(resolved_path).st_size)
        if expected_size <= 0:
            raise ValueError("segmenter_checkpoint_empty")
        payload = read_bytes_bounded_in_root(
            resolved_path,
            trusted_root=self.engine.weights_dir,
            max_bytes=expected_size,
        )
        return {
            "path": resolved_path,
            "payload": payload,
            "expected": {
                "entry_kind": "file",
                "size_bytes": len(payload),
                "hash_algorithm": "sha256",
                "digest": hashlib.sha256(payload).hexdigest(),
            },
        }

    def _configure_engine_runtime_base_sam(self, base_sam):
        configure_base = getattr(
            self.engine,
            "configure_verified_base_sam",
            None,
        )
        if not callable(configure_base):
            raise ValueError("segmenter_engine_base_configuration_missing")
        configured_identity = configure_base(
            base_sam["payload"],
            reference=base_sam["path"],
            fingerprint=base_sam["expected"],
        )
        if any(
            configured_identity.get(field) != base_sam["expected"].get(field)
            for field in (
                "entry_kind",
                "size_bytes",
                "hash_algorithm",
                "digest",
            )
        ):
            raise ValueError("segmenter_engine_base_identity_mismatch")
        return dict(configured_identity)

    def _selected_locator_timestamp(self):
        item_data = self.combo_locator.currentData() if self.combo_locator.count() else None
        if item_data in (None, "", "__no_locator__"):
            return None
        return str(item_data)

    def _selected_locator_display_text(self):
        if not self.combo_locator.count():
            return ""
        return str(self.combo_locator.currentText() or "").strip()

    def _parent_model_filename(self, model_kind, timestamp):
        ts = str(timestamp or "").strip()
        if not ts:
            return ""
        if "/" in ts or "\\" in ts:
            return os.path.basename(ts.replace("\\", "/"))
        if model_kind == "locator":
            return f"locator_{ts}.pth"
        if model_kind == "segmenter":
            return f"sam_decoder_lora_{ts}.pth"
        return ""

    def _build_locator_combo_label(self, timestamp, parent_model_notes=None):
        ts = str(timestamp or "").strip()
        if not ts:
            return ts
        filename = self._parent_model_filename("locator", ts)
        notes = parent_model_notes if isinstance(parent_model_notes, dict) else load_parent_model_notes(getattr(self.engine, "weights_dir", ""))
        note = notes.get(filename, "")

        path = self._locator_model_path(ts)
        if not path or not os.path.exists(path):
            return format_parent_model_display_name(filename or ts, note)

        state_label = ""
        try:
            saved_state = torch.load(path, map_location="cpu", weights_only=True)
        except Exception:
            pass
        else:
            checkpoint_meta = {}
            if isinstance(saved_state, dict) and isinstance(saved_state.get("meta"), dict):
                checkpoint_meta = saved_state.get("meta") or {}

            saved_resolution = checkpoint_meta.get("locator_size")
            legacy_resolution = checkpoint_meta.get("locator_resolution")
            if saved_resolution is None and legacy_resolution is not None:
                try:
                    legacy_side = max(1, int(legacy_resolution))
                except Exception:
                    legacy_side = 512
                saved_resolution = [legacy_side, legacy_side]

            size_pair = None
            if saved_resolution is not None:
                try:
                    size_pair = (max(1, int(saved_resolution[0])), max(1, int(saved_resolution[1])))
                except Exception:
                    size_pair = None

            checkpoint_schema = str(saved_state.get("schema_version") or "") if isinstance(saved_state, dict) else ""
            saved_scope = checkpoint_meta.get("locator_scope")
            scope_is_verifiable = (
                checkpoint_schema == "taxamask_locator_checkpoint_v2"
                and isinstance(saved_scope, (list, tuple))
                and bool(saved_scope)
                and all(isinstance(part, str) and part.strip() for part in saved_scope)
                and len({part.strip() for part in saved_scope}) == len(saved_scope)
            )
            if scope_is_verifiable and size_pair is not None:
                state_label = f"exact {format_size_pair(size_pair)}"
            elif scope_is_verifiable:
                state_label = "exact scope; assumed 512x512"
            elif size_pair is not None:
                state_label = f"legacy scope; resolution {format_size_pair(size_pair)}"
            else:
                state_label = "legacy scope; assumed 512x512"
        return format_parent_model_display_name(filename, note, details=state_label)

    def _build_segmenter_combo_label(self, timestamp, parent_model_notes=None):
        ts = str(timestamp or "").strip()
        if not ts:
            return ts
        filename = self._parent_model_filename("segmenter", ts)
        notes = parent_model_notes if isinstance(parent_model_notes, dict) else load_parent_model_notes(getattr(self.engine, "weights_dir", ""))
        return format_parent_model_display_name(filename, notes.get(filename, ""))

    def _selected_segmenter_timestamp(self):
        item_data = self.combo_segmenter.currentData() if self.combo_segmenter.count() else None
        if item_data in (None, "", "BASE_SAM", "No Segmenters Found"):
            return None
        return str(item_data)

    def _restore_confirmed_model_selection(self, model_kind):
        if model_kind == "locator":
            combo = self.combo_locator
            reference = self.last_confirmed_locator_timestamp
            combo_reference = reference if reference else "__no_locator__"
        elif model_kind == "segmenter":
            combo = self.combo_segmenter
            reference = self.last_confirmed_segmenter_timestamp
            combo_reference = reference if reference else "BASE_SAM"
        else:
            raise ValueError(f"unsupported_model_kind:{model_kind}")

        index = combo.findData(combo_reference)
        if index < 0:
            return False
        signals_were_blocked = combo.blockSignals(True)
        try:
            combo.setCurrentIndex(index)
        finally:
            combo.blockSignals(signals_were_blocked)
        return True

    def _parent_model_runtime_is_locked(self):
        checker = getattr(self, "_is_any_training_running", None)
        return bool(callable(checker) and checker())

    def _block_model_selection_while_training(self, model_kind, *, notify=True):
        if not self._parent_model_runtime_is_locked():
            return False

        requested = (
            self._selected_locator_timestamp()
            if model_kind == "locator"
            else self._selected_segmenter_timestamp()
        )
        restored = self._restore_confirmed_model_selection(model_kind)
        message = tr(
            "Locator and Segmenter selection is locked while training or training input verification is running.",
            self.current_lang,
        )
        self.log(message)
        runtime_log_event(
            "model_selection_blocked_training",
            model_kind=model_kind,
            requested_reference=str(requested or "base"),
            restored=bool(restored),
        )
        if notify:
            QMessageBox.information(
                self,
                tr("Model selection locked", self.current_lang),
                message,
            )
        return True

    def _ensure_parent_model_settings_available(self):
        if not self._parent_model_runtime_is_locked():
            return True
        message = tr(
            "Model settings are locked while training or training input verification is running.",
            self.current_lang,
        )
        self.log(message)
        runtime_log_event("model_settings_blocked_training")
        QMessageBox.information(
            self,
            tr("Model selection locked", self.current_lang),
            message,
        )
        return False

    def _active_project_route_manifest(self):
        return self.project.get_cascade_routes()

    def _active_model_profile_context(self):
        active_profile = _active_profile_from_manager(self.project)
        parent_backend = active_profile.get("parent_backend", {}) if isinstance(active_profile.get("parent_backend"), dict) else {}
        child_defaults = active_profile.get("child_backend_defaults", {}) if isinstance(active_profile.get("child_backend_defaults"), dict) else {}
        return {
            "active_profile_id": str(active_profile.get("profile_id") or ""),
            "parent_backend": str(parent_backend.get("backend_type") or ""),
            "child_backend": str(child_defaults.get("backend_type") or ""),
        }

    def _active_external_backend_config(self):
        active_profile = _active_profile_from_manager(self.project)
        parent_backend = active_profile.get("parent_backend", {}) if isinstance(active_profile.get("parent_backend"), dict) else {}
        if parent_backend.get("backend_type") == PARENT_BACKEND_EXTERNAL:
            return sanitize_external_backend_config(parent_backend.get("external_backend", {}))
        return sanitize_external_backend_config(self.external_backend_config)

    def _selected_route_entry(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is None:
            return None
        return panel._selected_route_entry()

    def _route_runtime_status(self, route_entry):
        panel = getattr(self, "route_settings_panel", None)
        if panel is None:
            return ui_text("Unknown", self.current_lang)
        return panel._route_runtime_status(route_entry)

    def refresh_route_table(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is not None:
            panel.refresh_route_table()
        if hasattr(self, "part_list"):
            self._refresh_part_tree(self._current_part_name())
        if hasattr(self, "blink_refine_panel"):
            self._refresh_blink_refine_state()

    def update_route_action_buttons(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is not None:
            panel.update_action_buttons()

    def toggle_selected_route_enabled(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is not None:
            panel.toggle_selected_route_enabled()

    def delete_selected_route(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is not None:
            panel.delete_selected_route()

    def _log_route_usage_summary(self, payload, image_path=None, prefix=None):
        if not isinstance(payload, dict):
            return
        meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
        attempted = list(meta.get("cascade_attempted_routes", []) or [])
        applied = list(meta.get("cascade_applied_routes", []) or [])
        block_reasons = dict(meta.get("cascade_block_reasons", {}) or {})
        route_source = str(meta.get("cascade_route_source", "none") or "none")
        image_name = os.path.basename(image_path) if image_path else tr("Current Image", self.current_lang)
        title = prefix or ui_text("Route usage for {0}", self.current_lang).format(image_name)
        attempted_text = attempted or [ui_text("None", self.current_lang)]
        applied_text = applied or [ui_text("None", self.current_lang)]
        self.log(
            f"{title}: "
            f"{ui_text('source={0}; attempted={1}; applied={2}', self.current_lang).format(route_source, attempted_text, applied_text)}"
        )
        profile_id = str(meta.get("model_profile_id") or "")
        parent_backend = str(meta.get("parent_backend") or "")
        route_backends = list(meta.get("cascade_route_backends", []) or [])
        if profile_id or parent_backend or route_backends:
            self.log(
                ui_text("Model audit: profile={0}; parent_backend={1}; route_backends={2}", self.current_lang).format(
                    profile_id or "unknown",
                    parent_backend or "unknown",
                    route_backends or [ui_text("None", self.current_lang)],
                )
            )
        if block_reasons:
            block_text = ", ".join(f"{part}={reason}" for part, reason in sorted(block_reasons.items()))
            self.log(ui_text("Route blocks: {0}", self.current_lang).format(block_text))

    def _locator_model_path(self, timestamp):
        if not self.engine or not timestamp:
            return None
        if "/" in str(timestamp) or "\\" in str(timestamp):
            path = os.path.abspath(
                os.path.join(self.engine.weights_dir, *str(timestamp).replace("\\", "/").split("/"))
            )
            if os.path.normcase(os.path.commonpath([self.engine.weights_dir, path])) != os.path.normcase(os.path.abspath(self.engine.weights_dir)):
                return None
            return path
        return os.path.join(self.engine.weights_dir, f"locator_{timestamp}.pth")

    def _segmenter_model_path(self, timestamp):
        if not self.engine or not timestamp:
            return None
        if "/" in str(timestamp) or "\\" in str(timestamp):
            path = os.path.abspath(
                os.path.join(self.engine.weights_dir, *str(timestamp).replace("\\", "/").split("/"))
            )
            if os.path.normcase(os.path.commonpath([self.engine.weights_dir, path])) != os.path.normcase(os.path.abspath(self.engine.weights_dir)):
                return None
            return path
        return os.path.join(self.engine.weights_dir, f"sam_decoder_lora_{timestamp}.pth")

    def _apply_locator_selection_to_runtime(
        self,
        *,
        log_change=False,
        allow_while_training=False,
    ):
        if not self.engine:
            return False
        if (
            not allow_while_training
            and self._block_model_selection_while_training(
                "locator",
                notify=False,
            )
        ):
            return False

        ts = self._selected_locator_timestamp()
        if not ts:
            try:
                if self.engine.locator is None:
                    self.engine.ensure_locator_loaded()
                else:
                    self.engine.reset_locator_to_base()
            except Exception as exc:
                return self._report_locator_load_failure("base", exc)
            self.locator_load_failure = None
            self.last_confirmed_locator_timestamp = None
            if log_change:
                self.log(tr("Locator reset to base (untrained).", self.current_lang))
            return True

        checkpoint_path = self._locator_model_path(ts)
        managed_selection = "/" in ts or "\\" in ts
        try:
            checkpoint_payload = None
            if managed_selection:
                checkpoint = self._verified_managed_model_checkpoint(ts, "locator")
                if not checkpoint:
                    return self._report_locator_load_failure(
                        ts,
                        ValueError("managed_locator_verification_failed"),
                        log_exception=False,
                    )
                checkpoint_path = checkpoint["path"]
                checkpoint_payload = checkpoint["payload"]
            load_kwargs = {
                "checkpoint_path": checkpoint_path,
                "require_complete": managed_selection,
                "expected_locator_scope": self.project.get_locator_scope(),
            }
            if checkpoint_payload is not None:
                load_kwargs["checkpoint_payload"] = checkpoint_payload
            self.engine.load_locator(ts, **load_kwargs)
            if getattr(self.engine, "locator", None) is None:
                raise RuntimeError("locator_checkpoint_load_left_runtime_unloaded")
            loaded_timestamp = str(
                getattr(self.engine, "loaded_locator_timestamp", "") or ""
            )
            if loaded_timestamp and loaded_timestamp != str(ts):
                raise RuntimeError("locator_checkpoint_selection_mismatch")
        except Exception as exc:
            return self._report_locator_load_failure(ts, exc)

        self.locator_load_failure = None
        if not self._locator_selection_needs_legacy_confirmation():
            self.last_confirmed_locator_timestamp = ts
        if log_change:
            locator_label = self._selected_locator_display_text() or ts
            self.log(tr("Locator switched to: {0}", self.current_lang).format(locator_label))
        return True

    def _clear_locator_runtime_after_failure(self):
        clear_failed_load = getattr(
            self.engine,
            "_clear_failed_locator_load",
            None,
        )
        if callable(clear_failed_load):
            clear_failed_load()
            return
        self.engine.locator = None
        if hasattr(self.engine, "opt_loc"):
            self.engine.opt_loc = None
        self.engine.loaded_locator_timestamp = None
        if hasattr(self.engine, "loaded_locator_schema_version"):
            self.engine.loaded_locator_schema_version = ""
        if hasattr(self.engine, "loaded_locator_scope"):
            self.engine.loaded_locator_scope = []
        self.engine.loaded_locator_requires_legacy_confirmation = False
        self.engine.loaded_locator_is_legacy_512 = False

    def _report_locator_load_failure(self, selection, exc, *, log_exception=True):
        self._clear_locator_runtime_after_failure()
        selection_text = str(selection or "base")
        reason = str(exc or "locator_checkpoint_load_failed")
        self.locator_load_failure = {
            "selection": selection_text,
            "reason": reason,
        }
        if log_exception:
            runtime_log_exception("locator_checkpoint_load_failed", *sys.exc_info())
        else:
            runtime_log_event(
                "locator_checkpoint_load_failed",
                selection=selection_text,
                reason=reason,
            )
        message = tr(
            "Locator checkpoint could not be loaded: {0}. Prediction and training were stopped.",
            self.current_lang,
        ).format(reason)
        self.log(message)
        QMessageBox.critical(
            self,
            tr("Model verification failed", self.current_lang),
            message,
        )
        return False

    def _ensure_locator_ready_for_operation(self):
        self.ensure_locator_preloaded()
        failure = getattr(self, "locator_load_failure", None)
        if isinstance(failure, dict):
            return False
        if not self.engine or getattr(self.engine, "locator", None) is None:
            return self._report_locator_load_failure(
                self._selected_locator_timestamp() or "base",
                RuntimeError("locator_runtime_unloaded"),
                log_exception=False,
            )

        selected = self._selected_locator_timestamp()
        loaded = str(getattr(self.engine, "loaded_locator_timestamp", "") or "")
        if selected and loaded and loaded != selected:
            return self._report_locator_load_failure(
                selected,
                RuntimeError("locator_checkpoint_selection_mismatch"),
                log_exception=False,
            )
        return True

    def _locator_selection_needs_legacy_confirmation(self):
        return bool(getattr(self.engine, "loaded_locator_requires_legacy_confirmation", False))

    def _confirm_legacy_locator_selection_if_needed(self):
        if not self.engine or not self._locator_selection_needs_legacy_confirmation():
            return True

        current_scope = ", ".join(self.project.get_locator_scope()) or "(empty)"
        scope_is_unverified = not bool(
            getattr(self.engine, "loaded_locator_scope", []) or []
        )
        resolution_is_assumed = bool(
            getattr(self.engine, "loaded_locator_is_legacy_512", False)
        )
        if scope_is_unverified and resolution_is_assumed:
            message = tr(
                "The selected locator checkpoint has no verifiable ordered locator scope or training resolution. Continuing assumes its output channels follow the current project order ({0}) and uses 512px inference. Continue only after verifying both assumptions.",
                self.current_lang,
            ).format(current_scope)
        elif scope_is_unverified:
            message = tr(
                "The selected locator checkpoint has no verifiable ordered locator scope. Continuing assumes its output channels follow the current project order ({0}). Continue only after verifying this assumption.",
                self.current_lang,
            ).format(current_scope)
        else:
            message = tr(
                "The selected locator checkpoint has no verifiable training resolution. Continuing uses 512px inference. Continue only after verifying this assumption.",
                self.current_lang,
            )
        reply = themed_yes_no_question(
            self,
            tr("Legacy Locator Confirmation", self.current_lang),
            message,
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        if reply == QMessageBox.Yes:
            self.engine.loaded_locator_requires_legacy_confirmation = False
            self.last_confirmed_locator_timestamp = self._selected_locator_timestamp()
            return True

        self.log("Legacy locator selection was cancelled.")
        return False

    def _apply_segmenter_selection_to_runtime(
        self,
        *,
        log_change=False,
        allow_while_training=False,
    ):
        if not self.engine:
            return False
        if (
            not allow_while_training
            and self._block_model_selection_while_training(
                "segmenter",
                notify=False,
            )
        ):
            return False

        self._discard_pending_sam_decoder("segmenter_selection_changed")
        ts = self._selected_segmenter_timestamp()
        if not ts:
            try:
                base_sam = self._stable_runtime_base_sam()
                self._configure_engine_runtime_base_sam(base_sam)
                self.engine.reset_sam_to_base()
                if self.sam_worker:
                    self._request_sam_base_reload()
                self.last_confirmed_segmenter_timestamp = None
                if log_change:
                    self.log(tr("Segmenter switched to: Base SAM (Original)", self.current_lang))
                return True
            except Exception as exc:
                runtime_log_exception("base_segmenter_load_failed", *sys.exc_info())
                QMessageBox.critical(
                    self,
                    tr("Model loading failed", self.current_lang),
                    str(exc),
                )
                return False

        checkpoint_path = self._segmenter_model_path(ts)
        managed_selection = "/" in ts or "\\" in ts
        checkpoint_payload = None
        expected = {}
        base_sam = None
        try:
            if managed_selection:
                checkpoint = self._verified_managed_model_checkpoint(
                    ts,
                    "segmenter",
                )
                if not checkpoint:
                    raise ValueError("managed_segmenter_verification_failed")
                checkpoint_path = checkpoint["path"]
                checkpoint_payload = checkpoint["payload"]
                expected = checkpoint["expected"]
                base_sam = checkpoint["base_sam"]
            else:
                base_sam = self._stable_runtime_base_sam()
                checkpoint = self._stable_runtime_segmenter_checkpoint(
                    checkpoint_path
                )
                checkpoint_path = checkpoint["path"]
                checkpoint_payload = checkpoint["payload"]
                expected = checkpoint["expected"]
            self._configure_engine_runtime_base_sam(base_sam)

            engine_kwargs = {"checkpoint_path": checkpoint_path}
            if checkpoint_payload is not None:
                engine_kwargs["checkpoint_payload"] = checkpoint_payload
            if managed_selection:
                engine_kwargs["expected_base_sam_fingerprint"] = base_sam[
                    "expected"
                ]
                engine_kwargs["require_base_sam_match"] = True
            self.engine.load_sam_decoder(ts, **engine_kwargs)

            engine_identity = dict(
                getattr(self.engine, "loaded_sam_decoder_identity", {}) or {}
            )
            if not self._segmenter_memory_identity_matches(
                engine_identity,
                expected,
            ):
                raise ValueError("segmenter_engine_identity_mismatch")
            if managed_selection and (
                getattr(self.engine, "loaded_sam_decoder_reference", "") != ts
            ):
                raise ValueError("managed_segmenter_engine_reference_mismatch")

            pending_record = {
                "project_context": self._capture_project_task_context(),
                "reference": ts,
                "checkpoint_path": checkpoint_path,
                "checkpoint_payload": checkpoint_payload,
                "expected": dict(expected),
                "base_checkpoint_payload": base_sam.get("payload"),
                "base_reference": str(base_sam.get("path") or ""),
                "base_expected": dict(base_sam.get("expected") or {}),
                "managed": bool(managed_selection),
                "engine_reference": str(
                    getattr(self.engine, "loaded_sam_decoder_reference", "") or ""
                ),
                "engine_identity": dict(
                    getattr(self.engine, "loaded_sam_decoder_identity", {}) or {}
                ),
                "log_change": bool(log_change),
            }
            self.sam_decoder_apply_pending = pending_record

            worker_ready = bool(
                self.sam_worker
                and getattr(self.sam_worker, "model", None) is not None
                and not getattr(self, "sam_base_reload_pending", False)
            )
            if worker_ready:
                return self._queue_pending_sam_decoder_to_worker()

            if not getattr(self, "sam_base_reload_pending", False):
                self._request_sam_base_reload()
            if self.sam_decoder_apply_pending is None:
                return self.last_confirmed_segmenter_timestamp == ts
            runtime_log_event(
                "segmenter_worker_apply_pending",
                reference=ts,
                managed=bool(managed_selection),
                project=str(
                    pending_record["project_context"].get(
                        "project_path", ""
                    )
                ),
            )
            return True
        except Exception as exc:
            event = (
                "managed_segmenter_load_failed"
                if managed_selection
                else "legacy_segmenter_load_failed"
            )
            runtime_log_exception(event, *sys.exc_info())
            return self._fail_pending_sam_decoder(
                event,
                message=str(exc),
                managed=managed_selection,
            )

    def _discard_pending_sam_decoder(self, reason=""):
        pending = getattr(self, "sam_decoder_apply_pending", None)
        self.sam_decoder_apply_pending = None
        if pending:
            runtime_log_event(
                "segmenter_worker_pending_discarded",
                reference=str(pending.get("reference") or ""),
                reason=str(reason or "unspecified"),
            )
        return pending

    @staticmethod
    def _segmenter_memory_identity_matches(identity, expected):
        identity = identity if isinstance(identity, dict) else {}
        expected = expected if isinstance(expected, dict) else {}
        return bool(
            identity.get("source") == "memory"
            and identity.get("size_bytes") == expected.get("size_bytes")
            and identity.get("hash_algorithm") == expected.get("hash_algorithm")
            and identity.get("digest") == expected.get("digest")
        )

    @staticmethod
    def _segmenter_base_identity_matches(identity, expected):
        identity = identity if isinstance(identity, dict) else {}
        expected = expected if isinstance(expected, dict) else {}
        return bool(
            identity.get("source") == "memory"
            and identity.get("entry_kind") == expected.get("entry_kind")
            and identity.get("size_bytes") == expected.get("size_bytes")
            and identity.get("hash_algorithm") == expected.get("hash_algorithm")
            and identity.get("digest") == expected.get("digest")
        )

    def _queue_pending_sam_decoder_to_worker(self):
        pending = getattr(self, "sam_decoder_apply_pending", None)
        if not isinstance(pending, dict):
            return False
        if pending.get("worker_request_queued"):
            return True

        context = pending.get("project_context")
        if not self._project_task_context_matches(context):
            self._discard_pending_sam_decoder("project_context_changed")
            self._clear_segmenter_runtimes_after_failure()
            self.last_confirmed_segmenter_timestamp = None
            runtime_log_event(
                "stale_segmenter_worker_apply_skipped",
                expected_project=str((context or {}).get("project_path", "")),
                current_project=str(
                    getattr(getattr(self, "project", None), "current_project_path", "")
                    or ""
                ),
            )
            self.sam_base_reload_pending = False
            self._request_sam_base_reload()
            return False

        reference = str(pending.get("reference") or "")
        if self._selected_segmenter_timestamp() != reference:
            self._discard_pending_sam_decoder("selected_reference_changed")
            return False

        worker = self.sam_worker
        if worker is None or getattr(worker, "model", None) is None:
            return False
        if getattr(self, "sam_base_reload_pending", False):
            return False

        current_engine_reference = str(
            getattr(self.engine, "loaded_sam_decoder_reference", "") or ""
        )
        current_engine_identity = dict(
            getattr(self.engine, "loaded_sam_decoder_identity", {}) or {}
        )
        if (
            current_engine_reference != pending.get("engine_reference")
            or current_engine_identity != pending.get("engine_identity")
        ):
            return self._fail_pending_sam_decoder(
                "segmenter_engine_changed_while_worker_pending",
                managed=bool(pending.get("managed")),
            )
        connect_protocol = getattr(
            self,
            "_connect_sam_worker_runtime_protocol",
            None,
        )
        if callable(connect_protocol):
            connect_protocol(worker)
        if not hasattr(worker, "apply_runtime_bundle") or not hasattr(
            self,
            "sam_runtime_apply_requested",
        ):
            return self._fail_pending_sam_decoder(
                "segmenter_worker_runtime_protocol_missing",
                managed=bool(pending.get("managed")),
            )

        self.sam_decoder_request_serial = int(
            getattr(self, "sam_decoder_request_serial", 0)
        ) + 1
        request_id = f"sam-runtime-{self.sam_decoder_request_serial}"
        pending["request_id"] = request_id
        pending["worker_request_queued"] = True
        request = {
            "request_id": request_id,
            "reference": reference,
            "checkpoint_path": pending.get("checkpoint_path"),
            "checkpoint_payload": pending.get("checkpoint_payload"),
            "model_type": str(
                getattr(self.engine, "base_sam_path", "") or "sam_b.pt"
            ),
            "device_preference": self.runtime_device,
            "poly_epsilon": self.inf_poly_epsilon,
            "base_checkpoint_payload": pending.get("base_checkpoint_payload"),
            "base_reference": pending.get("base_reference"),
            "base_expected": pending.get("base_expected") or None,
            "require_base_sam_match": bool(pending.get("managed")),
        }
        self.sam_runtime_apply_requested.emit(request)
        if self.sam_decoder_apply_pending is None:
            return self.last_confirmed_segmenter_timestamp == reference
        runtime_log_event(
            "segmenter_worker_apply_queued",
            request_id=request_id,
            reference=reference,
            managed=bool(pending.get("managed")),
        )
        return True

    def _on_sam_runtime_apply_succeeded(self, result):
        payload = result if isinstance(result, dict) else {}
        pending = getattr(self, "sam_decoder_apply_pending", None)
        if (
            not isinstance(pending, dict)
            or payload.get("request_id") != pending.get("request_id")
        ):
            runtime_log_event(
                "stale_segmenter_worker_result_skipped",
                request_id=str(payload.get("request_id") or ""),
                status="succeeded",
            )
            return False
        try:
            context = pending.get("project_context")
            reference = str(pending.get("reference") or "")
            if not self._project_task_context_matches(context):
                raise ValueError("segmenter_project_changed_while_worker_pending")
            if self._selected_segmenter_timestamp() != reference:
                raise ValueError("segmenter_selection_changed_while_worker_pending")
            if payload.get("loaded_decoder_reference") != reference:
                raise ValueError("segmenter_worker_reference_mismatch")
            if not payload.get("worker_thread_confirmed"):
                raise ValueError("segmenter_worker_thread_mismatch")
            if not self._segmenter_base_identity_matches(
                payload.get("base_identity"),
                pending.get("base_expected"),
            ):
                raise ValueError("segmenter_worker_base_identity_mismatch")
            if not self._segmenter_memory_identity_matches(
                payload.get("decoder_identity"),
                pending.get("expected"),
            ):
                raise ValueError("segmenter_worker_identity_mismatch")
            current_engine_reference = str(
                getattr(self.engine, "loaded_sam_decoder_reference", "") or ""
            )
            current_engine_identity = dict(
                getattr(self.engine, "loaded_sam_decoder_identity", {}) or {}
            )
            if (
                current_engine_reference != pending.get("engine_reference")
                or current_engine_identity != pending.get("engine_identity")
            ):
                raise ValueError("segmenter_engine_changed_while_worker_pending")
        except Exception as exc:
            runtime_log_exception(
                "segmenter_worker_result_verification_failed",
                *sys.exc_info(),
            )
            return self._fail_pending_sam_decoder(
                "segmenter_worker_result_verification_failed",
                message=str(exc),
                managed=bool(pending.get("managed")),
            )

        log_change = bool(pending.get("log_change"))
        reference = str(pending.get("reference") or "")
        self.sam_decoder_apply_pending = None
        self.last_confirmed_segmenter_timestamp = reference
        runtime_log_event(
            "segmenter_worker_apply_ok",
            request_id=str(payload.get("request_id") or ""),
            reference=reference,
            managed=bool(pending.get("managed")),
        )
        if log_change:
            self.log(
                tr(
                    "Segmenter switched to: Fine-tuned {0}",
                    self.current_lang,
                ).format(reference)
            )
        return True

    def _on_sam_runtime_apply_failed(self, result):
        payload = result if isinstance(result, dict) else {}
        pending = getattr(self, "sam_decoder_apply_pending", None)
        if (
            not isinstance(pending, dict)
            or payload.get("request_id") != pending.get("request_id")
        ):
            runtime_log_event(
                "stale_segmenter_worker_result_skipped",
                request_id=str(payload.get("request_id") or ""),
                status="failed",
            )
            return False
        event = (
            "managed_segmenter_worker_apply_failed"
            if pending.get("managed")
            else "legacy_segmenter_worker_apply_failed"
        )
        return self._fail_pending_sam_decoder(
            event,
            message=str(payload.get("error") or ""),
            managed=bool(pending.get("managed")),
        )

    def _fail_pending_sam_decoder(
        self,
        event,
        *,
        message="",
        managed=None,
        reload_worker=True,
    ):
        pending = self._discard_pending_sam_decoder(event)
        if managed is None:
            managed = bool((pending or {}).get("managed"))
        self._clear_segmenter_runtimes_after_failure()
        self.last_confirmed_segmenter_timestamp = None
        self._restore_confirmed_model_selection("segmenter")
        self.sam_base_reload_pending = False
        if reload_worker:
            try:
                self._request_sam_base_reload()
            except Exception:
                runtime_log_exception(
                    "segmenter_base_restore_failed",
                    *sys.exc_info(),
                )
        title = (
            tr("Model verification failed", self.current_lang)
            if managed
            else tr("Model loading failed", self.current_lang)
        )
        detail = (
            tr(
                "This managed SAM decoder no longer matches its successful training record and was not loaded.",
                self.current_lang,
            )
            if managed
            else tr(
                "The selected legacy SAM decoder could not be loaded consistently and Base SAM was restored.",
                self.current_lang,
            )
        )
        if message:
            self.log(f"{event}: {message}")
        QMessageBox.critical(self, title, detail)
        return False

    def _clear_segmenter_runtimes_after_failure(self):
        clear_engine = getattr(self.engine, "_clear_failed_parts_load", None)
        if callable(clear_engine):
            try:
                clear_engine()
            except Exception:
                runtime_log_exception(
                    "managed_segmenter_engine_cleanup_failed",
                    *sys.exc_info(),
                )
        self.engine.parts_model = None
        if hasattr(self.engine, "opt_parts"):
            self.engine.opt_parts = None
        if hasattr(self.engine, "base_sam_predictor"):
            self.engine.base_sam_predictor = None
        self.engine.loaded_sam_decoder_reference = ""
        self.engine.loaded_sam_decoder_identity = {}

    def update_model_delete_button_states(self, *_):
        locator_ts = self._selected_locator_timestamp()
        locator_path = self._locator_model_path(locator_ts)
        can_edit_locator = bool(locator_path and os.path.exists(locator_path) and "/" not in str(locator_ts) and "\\" not in str(locator_ts))
        self.btn_del_locator.setEnabled(can_edit_locator)
        self.btn_note_locator.setEnabled(can_edit_locator)

        segmenter_ts = self._selected_segmenter_timestamp()
        segmenter_path = self._segmenter_model_path(segmenter_ts)
        can_edit_segmenter = bool(segmenter_path and os.path.exists(segmenter_path) and "/" not in str(segmenter_ts) and "\\" not in str(segmenter_ts))
        self.btn_del_segmenter.setEnabled(can_edit_segmenter)
        self.btn_note_segmenter.setEnabled(can_edit_segmenter)

    def _edit_parent_model_note(self, model_kind):
        if model_kind == "locator":
            ts = self._selected_locator_timestamp()
            path = self._locator_model_path(ts)
            title = tr("Edit Locator Note", self.current_lang)
        elif model_kind == "segmenter":
            ts = self._selected_segmenter_timestamp()
            path = self._segmenter_model_path(ts)
            title = tr("Edit Segmenter Note", self.current_lang)
        else:
            return
        filename = self._parent_model_filename(model_kind, ts)
        if not ts or not filename or not path or not os.path.exists(path):
            self.update_model_delete_button_states()
            return

        notes = load_parent_model_notes(self.engine.weights_dir)
        current_note = notes.get(filename, "")
        note, ok = QInputDialog.getText(
            self,
            title,
            tr("Model display note:", self.current_lang),
            QLineEdit.Normal,
            current_note,
        )
        if not ok:
            return
        clean_note = set_parent_model_note(self.engine.weights_dir, filename, note)
        self.refresh_model_list()
        if clean_note:
            self.log(tr("Updated model note for {0}: {1}", self.current_lang).format(filename, clean_note))
        else:
            self.log(tr("Cleared model note for {0}.", self.current_lang).format(filename))

    def edit_locator_model_note(self):
        self._edit_parent_model_note("locator")

    def edit_segmenter_model_note(self):
        self._edit_parent_model_note("segmenter")

    def on_locator_changed(self, index):
        if getattr(self, "active_project_kind", "start") != "image" or not self.engine:
            self.update_model_delete_button_states()
            return
        if self._block_model_selection_while_training("locator"):
            self.update_model_delete_button_states()
            return
        selected_ts = self._selected_locator_timestamp()
        if not self._apply_locator_selection_to_runtime(log_change=False):
            fallback_ts = self.last_confirmed_locator_timestamp
            fallback_index = self.combo_locator.findData(fallback_ts) if fallback_ts else -1
            if fallback_index >= 0 and fallback_ts != selected_ts:
                self.combo_locator.blockSignals(True)
                self.combo_locator.setCurrentIndex(fallback_index)
                self.combo_locator.blockSignals(False)
                if self._apply_locator_selection_to_runtime(log_change=False):
                    fallback_label = self._selected_locator_display_text() or fallback_ts
                    self.log(
                        tr("Locator switched to: {0}", self.current_lang).format(
                            fallback_label
                        )
                    )
            self.update_model_delete_button_states()
            return
        if self._locator_selection_needs_legacy_confirmation():
            if not self._confirm_legacy_locator_selection_if_needed():
                fallback_ts = self.last_confirmed_locator_timestamp
                fallback_index = self.combo_locator.findData(fallback_ts) if fallback_ts else -1
                if fallback_index < 0:
                    fallback_index = 0 if self.combo_locator.count() else -1
                if fallback_index >= 0:
                    self.combo_locator.blockSignals(True)
                    self.combo_locator.setCurrentIndex(fallback_index)
                    self.combo_locator.blockSignals(False)
                    if self._apply_locator_selection_to_runtime(log_change=False):
                        fallback_label = self._selected_locator_display_text()
                        if fallback_label:
                            self.log(tr("Locator switched to: {0}", self.current_lang).format(fallback_label))
                        else:
                            self.log(tr("Locator reset to base (untrained).", self.current_lang))
            else:
                self.last_confirmed_locator_timestamp = self._selected_locator_timestamp()
                self.log(
                    tr("Locator switched to: {0}", self.current_lang).format(
                        self._selected_locator_display_text() or self.last_confirmed_locator_timestamp
                    )
                )
        else:
            self.last_confirmed_locator_timestamp = self._selected_locator_timestamp()
            current_label = self._selected_locator_display_text()
            if current_label:
                self.log(tr("Locator switched to: {0}", self.current_lang).format(current_label))
            else:
                self.log(tr("Locator reset to base (untrained).", self.current_lang))
        self.update_model_delete_button_states()

    def delete_locator_model(self):
        ts = self._selected_locator_timestamp()
        if not ts:
            self.update_model_delete_button_states()
            return

        reply = themed_yes_no_question(
            self,
            tr("Delete Model", self.current_lang),
            tr("Delete locator model {0}?", self.current_lang).format(ts),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply == QMessageBox.Yes:
            try:
                p = self._locator_model_path(ts)
                if os.path.exists(p):
                    os.remove(p)
                    set_parent_model_note(self.engine.weights_dir, self._parent_model_filename("locator", ts), "")
                    self.log(f"Deleted locator: {ts}")
                    self.refresh_model_list()
                else:
                    self.log(f"File not found: {p}")
                    self.update_model_delete_button_states()
            except Exception as e:
                self.log(f"Error deleting model: {e}")
                self.update_model_delete_button_states()

    def on_segmenter_changed(self, index):
        if self._block_model_selection_while_training("segmenter"):
            self.update_model_delete_button_states()
            return
        if not self._apply_segmenter_selection_to_runtime(log_change=True):
            self._restore_confirmed_model_selection("segmenter")
        self.update_model_delete_button_states()

    def delete_segmenter_model(self):
        ts = self._selected_segmenter_timestamp()
        if not ts:
            self.update_model_delete_button_states()
            return

        reply = themed_yes_no_question(
            self,
            tr("Delete Model", self.current_lang),
            tr("Delete segmenter LoRA {0}?", self.current_lang).format(ts),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply == QMessageBox.Yes:
            try:
                p = self._segmenter_model_path(ts)
                if os.path.exists(p):
                    os.remove(p)
                    set_parent_model_note(self.engine.weights_dir, self._parent_model_filename("segmenter", ts), "")
                    self.log(f"Deleted segmenter: {ts}")
                    self.refresh_model_list()
                else:
                    self.log(f"File not found: {p}")
                    self.update_model_delete_button_states()
            except Exception as e:
                self.log(f"Error deleting model: {e}")
                self.update_model_delete_button_states()

    def on_model_changed(self, index):
        # Deprecated
        pass

    def _external_backend_runner(self):
        return ExternalBackendRunner(self.project, self._active_external_backend_config())

    def ensure_2d_stl_models_preloaded(self):
        locator_started = self.ensure_locator_preloaded()
        sam_started = self.ensure_sam_preloaded()
        return bool(locator_started or sam_started)

    def ensure_locator_preloaded(self):
        if not self.engine or not hasattr(self.engine, "ensure_locator_loaded"):
            return False
        locator_scope = list(self.project.get_locator_scope())
        locator_scope_len = len(locator_scope)
        current_scope = list(
            getattr(self.engine, "current_locator_scope", []) or []
        )
        scope_changed = bool(current_scope) and current_scope != locator_scope
        if locator_scope_len != self.engine.current_num_classes or scope_changed:
            if scope_changed:
                self._clear_locator_runtime_after_failure()
            self.engine.current_num_classes = locator_scope_len
            self.engine.loaded_locator_timestamp = None
            self.engine.loaded_locator_requires_legacy_confirmation = False
            self.engine.loaded_locator_is_legacy_512 = False
        if hasattr(self.engine, "current_locator_scope"):
            self.engine.current_locator_scope = locator_scope
        ts = self._selected_locator_timestamp()
        locator_loaded = getattr(self.engine, "locator", None) is not None
        loaded_ts = str(getattr(self.engine, "loaded_locator_timestamp", "") or "")
        failed_selection = str(
            (getattr(self, "locator_load_failure", None) or {}).get("selection", "")
        )
        selection_matches = not ts or not loaded_ts or loaded_ts == ts
        if locator_loaded and selection_matches and failed_selection != str(ts or "base"):
            return False

        loaded = self._apply_locator_selection_to_runtime(log_change=False)
        return bool(loaded)

    def _preload_engine_parts_model_async(self):
        if not self.engine or not hasattr(self.engine, "ensure_parts_model_loaded"):
            return False
        if getattr(self.engine, "parts_model", None) is not None:
            return False
        existing_thread = getattr(self, "parts_model_preload_thread", None)
        if existing_thread is not None and existing_thread.is_alive():
            return False

        def worker():
            try:
                self.engine.ensure_parts_model_loaded()
            except Exception as exc:
                print(f"Error preloading Trainable SAM: {exc}")

        self.parts_model_preload_thread = threading.Thread(
            target=worker,
            name="TaxaMaskTrainableSAMPreload",
            daemon=True,
        )
        self.parts_model_preload_thread.start()
        return True
