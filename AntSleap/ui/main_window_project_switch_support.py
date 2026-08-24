import hashlib
import stat

try:
    from AntSleap.ui.main_window_project_dependencies import *
    from AntSleap.core.path_identity import canonical_path, path_identity
    from AntSleap.core.safe_io import atomic_write_json_in_root, read_json_bounded_in_root
except ImportError:
    from ui.main_window_project_dependencies import *
    from core.path_identity import canonical_path, path_identity
    from core.safe_io import atomic_write_json_in_root, read_json_bounded_in_root


NEW_PROJECT_RECOVERY_SCHEMA = "taxamask-new-project-recovery-v2"
NEW_PROJECT_RECOVERY_MAX_BYTES = 64 * 1024
NEW_PROJECT_RECOVERY_TTL_SECONDS = 24 * 60 * 60
NEW_PROJECT_RECOVERY_CLOCK_SKEW_SECONDS = 5 * 60


class MainWindowProjectSwitchSupportMixin:
    def _close_active_tif_workbench_for_project_switch(self):
        active_kind = getattr(self, "active_project_kind", "start")
        if active_kind == "start":
            active_kind = getattr(self, "last_workbench_kind", "image")
        if active_kind != "tif":
            return True
        workbench = getattr(self, "tif_workbench", None)
        close_project = getattr(workbench, "close_project", None) if workbench is not None else None
        if not callable(close_project):
            return True
        tif_workbench_selection = self._active_tif_workbench_selection_state()
        try:
            return bool(close_project(prompt_unsaved=True))
        except Exception as exc:
            runtime_log_event("active_tif_close_failed", error=str(exc))
            refresh_project = getattr(workbench, "refresh_project", None)
            if callable(refresh_project):
                try:
                    self._restore_tif_workbench_selection_state(tif_workbench_selection)
                    refresh_project()
                except Exception as restore_exc:
                    runtime_log_event(
                        "active_tif_close_recovery_failed",
                        error=str(restore_exc),
                    )
            return False

    def _snapshot_project_switch_manager(self, manager, *, deep=False):
        if manager is None:
            return None
        snapshot_runtime = getattr(manager, "_snapshot_runtime_state", None)
        if callable(snapshot_runtime):
            if deep:
                try:
                    return ("native", snapshot_runtime(deep=True))
                except TypeError:
                    pass
            return ("native", snapshot_runtime())
        fields = {}
        for name in (
            "project_data",
            "current_project_path",
            "current_storage_backend",
            "current_database_path",
            "current_asset_root",
        ):
            if hasattr(manager, name):
                fields[name] = getattr(manager, name)
        return ("fields", fields)

    def _restore_project_switch_manager(self, manager, snapshot):
        if manager is None or snapshot is None:
            return
        snapshot_kind, state = snapshot
        if snapshot_kind == "native":
            restore_runtime = getattr(manager, "_restore_runtime_state", None)
            if not callable(restore_runtime):
                raise RuntimeError("project_manager_runtime_restore_unavailable")
            restore_runtime(state)
            return
        for name, value in state.items():
            setattr(manager, name, value)

    def _active_tif_workbench_selection_state(self):
        active_kind = getattr(self, "active_project_kind", "start")
        if active_kind == "start":
            active_kind = getattr(self, "last_workbench_kind", "image")
        if active_kind != "tif":
            return None
        workbench = getattr(self, "tif_workbench", None)
        if workbench is None:
            return None
        selection = {}
        for name in (
            "current_specimen_id",
            "current_volume_scope",
            "current_part_id",
            "current_reslice_id",
        ):
            if hasattr(workbench, name):
                selection[name] = getattr(workbench, name)
        return selection or None

    def _restore_tif_workbench_selection_state(self, state):
        if not isinstance(state, dict):
            return
        workbench = getattr(self, "tif_workbench", None)
        if workbench is None:
            return
        for name in (
            "current_specimen_id",
            "current_volume_scope",
            "current_part_id",
            "current_reslice_id",
        ):
            if name in state:
                setattr(workbench, name, state[name])

    def _active_project_switch_recovery_state(
        self,
        *,
        deep_project=False,
        tif_workbench_selection=None,
    ):
        active_kind = getattr(self, "active_project_kind", "start")
        effective_kind = getattr(self, "last_workbench_kind", "image") if active_kind == "start" else active_kind
        if tif_workbench_selection is None and effective_kind == "tif":
            tif_workbench_selection = self._active_tif_workbench_selection_state()
        config = getattr(self, "config", None)
        config_get = getattr(config, "get", None) if config is not None else None
        configured_last_project_path = None
        configured_last_project_path_captured = False
        if callable(config_get):
            try:
                configured_last_project_path = config_get("last_project_path", "")
                configured_last_project_path_captured = True
            except Exception:
                pass
        tabs = getattr(self, "tabs", None)
        current_widget = getattr(tabs, "currentWidget", None) if tabs is not None else None
        current_tab = current_widget() if callable(current_widget) else None
        image_list_group_collapsed = getattr(self, "image_list_group_collapsed", None)
        return {
            "active_project_kind": active_kind,
            "effective_project_kind": effective_kind,
            "last_workbench_kind": getattr(self, "last_workbench_kind", effective_kind),
            "active_project_source_kind": getattr(self, "active_project_source_kind", effective_kind),
            "active_project_entry_path": getattr(self, "active_project_entry_path", ""),
            "configured_last_project_path": configured_last_project_path,
            "configured_last_project_path_captured": configured_last_project_path_captured,
            "manager_runtime": {
                "project": self._snapshot_project_switch_manager(
                    getattr(self, "project", None),
                    deep=deep_project,
                ),
                "tif_project": self._snapshot_project_switch_manager(getattr(self, "tif_project", None)),
                "stl_project": self._snapshot_project_switch_manager(getattr(self, "stl_project", None)),
            },
            "current_image": getattr(self, "current_image", None),
            "image_list_state_cache": getattr(self, "_image_list_state_cache", None),
            "image_list_group_collapsed": (
                dict(image_list_group_collapsed) if isinstance(image_list_group_collapsed, dict) else image_list_group_collapsed
            ),
            "current_tab": current_tab,
            "current_tab_captured": callable(current_widget),
            "tif_workbench_selection": (
                dict(tif_workbench_selection)
                if isinstance(tif_workbench_selection, dict)
                else None
            ),
        }

    def _restore_active_project_after_failed_switch(self, state):
        if not state:
            return False
        recovery_ok = True

        def recovery_failed(stage, exc):
            nonlocal recovery_ok
            recovery_ok = False
            runtime_log_event(
                "active_project_switch_recovery_failed",
                stage=stage,
                project=state.get("active_project_entry_path", ""),
                error=str(exc),
            )

        manager_runtime = state.get("manager_runtime", {})
        for name in ("project", "tif_project", "stl_project"):
            try:
                self._restore_project_switch_manager(
                    getattr(self, name, None),
                    manager_runtime.get(name),
                )
            except Exception as exc:
                recovery_failed(f"restore_{name}", exc)

        # Compatibility for recovery snapshots created before the generic switch transaction.
        if not manager_runtime and state.get("project_path"):
            tif_project = getattr(self, "tif_project", None)
            project_path = str(state.get("project_path") or "")
            if tif_project is not None and canonical_path(getattr(tif_project, "current_project_path", "") or "") != canonical_path(project_path):
                try:
                    tif_project.load_project(project_path)
                except Exception as exc:
                    recovery_failed("restore_tif_project", exc)

        for name in (
            "active_project_kind",
            "last_workbench_kind",
            "active_project_source_kind",
            "active_project_entry_path",
        ):
            if name in state:
                setattr(self, name, state[name])
        config = getattr(self, "config", None)
        config_set = getattr(config, "set", None) if config is not None else None
        config_captured = state.get(
            "configured_last_project_path_captured",
            "configured_last_project_path" in state,
        )
        if config_captured and callable(config_set):
            try:
                config_set("last_project_path", state.get("configured_last_project_path"))
            except Exception as exc:
                recovery_failed("restore_config", exc)

        self.current_image = state.get("current_image")
        self._image_list_state_cache = state.get("image_list_state_cache")
        if "image_list_group_collapsed" in state:
            self.image_list_group_collapsed = state.get("image_list_group_collapsed")

        tif_workbench_selection = state.get("tif_workbench_selection")
        try:
            self._restore_tif_workbench_selection_state(tif_workbench_selection)
        except Exception as exc:
            recovery_failed("restore_tif_workbench_selection", exc)

        refresh_views = getattr(self, "_refresh_project_bound_views", None)
        if callable(refresh_views):
            try:
                refresh_views()
            except Exception as exc:
                recovery_failed("refresh_project_bound_views", exc)
                try:
                    self._restore_tif_workbench_selection_state(tif_workbench_selection)
                except Exception as restore_exc:
                    recovery_failed(
                        "restore_tif_workbench_selection_after_refresh",
                        restore_exc,
                    )

        self.current_image = state.get("current_image")
        self._image_list_state_cache = state.get("image_list_state_cache")
        if "image_list_group_collapsed" in state:
            self.image_list_group_collapsed = state.get("image_list_group_collapsed")

        canvas = getattr(self, "canvas", None)
        load_image = getattr(canvas, "load_image", None) if canvas is not None else None
        if callable(load_image):
            try:
                current_image = state.get("current_image") or ""
                load_image(current_image)
                if current_image:
                    on_enhancement_changed = getattr(self, "on_enhancement_changed", None)
                    if callable(on_enhancement_changed):
                        on_enhancement_changed()
                    get_labels = getattr(getattr(self, "project", None), "get_labels", None)
                    set_polygons = getattr(canvas, "set_polygons", None)
                    if callable(get_labels) and callable(set_polygons):
                        set_polygons(get_labels(current_image))
                    refresh_boxes = getattr(self, "_refresh_current_canvas_boxes", None)
                    if callable(refresh_boxes):
                        refresh_boxes()
            except Exception as exc:
                recovery_failed("restore_canvas", exc)

        if state.get("current_tab_captured"):
            tabs = getattr(self, "tabs", None)
            set_current_widget = getattr(tabs, "setCurrentWidget", None) if tabs is not None else None
            if callable(set_current_widget) and state.get("current_tab") is not None:
                try:
                    set_current_widget(state.get("current_tab"))
                except Exception as exc:
                    recovery_failed("restore_current_tab", exc)
        return recovery_ok

    def _log_new_project_artifact_event(self, event, **fields):
        try:
            runtime_log_event(event, **fields)
        except Exception:
            pass

    def _new_project_artifact_signature(self, path):
        if not path or os.path.islink(path) or not os.path.isfile(path):
            return None
        try:
            before = os.stat(path, follow_symlinks=False)
            if not stat.S_ISREG(before.st_mode):
                return None
            digest = hashlib.sha256()
            with open(path, "rb") as handle:
                opened_before = os.fstat(handle.fileno())
                if not stat.S_ISREG(opened_before.st_mode):
                    return None
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                opened_after = os.fstat(handle.fileno())
            after = os.stat(path, follow_symlinks=False)
        except (OSError, TypeError, ValueError):
            return None
        def stat_state(result):
            return (
                int(result.st_dev),
                int(result.st_ino),
                int(result.st_size),
                int(getattr(result, "st_mtime_ns", int(result.st_mtime * 1_000_000_000))),
                int(result.st_mode),
            )

        before_state = stat_state(before)
        if not all(
            state == before_state
            for state in (stat_state(opened_before), stat_state(opened_after), stat_state(after))
        ):
            return None
        return {
            "identity": [before_state[0], before_state[1]],
            "size": before_state[2],
            "sha256": digest.hexdigest(),
        }

    def _new_project_artifact_signature_matches(self, path, expected):
        if not isinstance(expected, dict):
            return False
        current = self._new_project_artifact_signature(path)
        if current is None:
            return False
        try:
            expected_identity = [int(value) for value in expected.get("identity", [])]
            expected_size = int(expected.get("size", -1))
        except (TypeError, ValueError):
            return False
        return (
            current["identity"] == expected_identity
            and current["size"] == expected_size
            and current["sha256"] == str(expected.get("sha256", ""))
        )

    def _new_project_recovery_marker_path(self, manifest_path):
        manifest_identity = path_identity(manifest_path)
        digest = hashlib.sha256(manifest_identity.encode("utf-8")).hexdigest()[:20]
        return os.path.join(
            os.path.dirname(canonical_path(manifest_path)),
            f".taxamask-new-project-recovery-{digest}.json",
        )

    def _new_project_marker_payload(self, transaction, state, reason=""):
        project_dir = canonical_path(transaction["project_dir"])
        created_at = transaction.get("recovery_marker_created_at")
        expires_at = transaction.get("recovery_marker_expires_at")
        if not isinstance(created_at, int) or isinstance(created_at, bool) or created_at <= 0:
            created_at = int(time.time())
            transaction["recovery_marker_created_at"] = created_at
        if (
            not isinstance(expires_at, int)
            or isinstance(expires_at, bool)
            or expires_at <= created_at
            or expires_at - created_at > NEW_PROJECT_RECOVERY_TTL_SECONDS
        ):
            expires_at = created_at + NEW_PROJECT_RECOVERY_TTL_SECONDS
            transaction["recovery_marker_expires_at"] = expires_at
        records = transaction.get("published_artifacts", {})
        artifacts = []
        for original in transaction.get("artifacts", []):
            record = records.get(original)
            if not isinstance(record, dict):
                continue
            quarantine = str(record.get("quarantine_path") or "")
            artifacts.append(
                {
                    "path": os.path.basename(original),
                    "quarantine_path": os.path.basename(quarantine) if quarantine else "",
                    "identity": list(record.get("identity", [])),
                    "size": int(record.get("size", -1)),
                    "sha256": str(record.get("sha256", "")),
                }
            )
        return {
            "schema_version": NEW_PROJECT_RECOVERY_SCHEMA,
            "state": str(state or "preserved"),
            "created_at": created_at,
            "expires_at": expires_at,
            "project_kind": str(transaction.get("project_kind", "")),
            "project_name": str(transaction.get("project_name", "")),
            "project_directory": project_dir,
            "manifest": os.path.basename(transaction["manifest_path"]),
            "database": os.path.basename(transaction["database_path"]),
            "preexisting_artifacts": [],
            "artifacts": artifacts,
            "reason": str(reason or "")[:1000],
        }

    def _write_new_project_recovery_marker(self, transaction, state, reason=""):
        marker_path = transaction.get("recovery_marker_path", "")
        if not marker_path:
            return False
        expected_marker_path = self._new_project_recovery_marker_path(
            transaction.get("manifest_path", "")
        )
        if (
            path_identity(marker_path) != path_identity(expected_marker_path)
            or path_identity(os.path.dirname(marker_path))
            != path_identity(transaction.get("project_dir", ""))
        ):
            self._log_new_project_artifact_event(
                "new_project_recovery_marker_write_refused",
                marker=marker_path,
                reason="marker_path_outside_project_or_unexpected",
            )
            return False
        known_signature = transaction.get("recovery_marker_signature")
        if os.path.lexists(marker_path):
            if not known_signature or not self._new_project_artifact_signature_matches(marker_path, known_signature):
                return False
        elif known_signature:
            return False
        else:
            try:
                descriptor = os.open(marker_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            except OSError:
                return False
            known_signature = self._new_project_artifact_signature(marker_path)
            if known_signature is None:
                return False
            transaction["recovery_marker_signature"] = known_signature
        try:
            atomic_write_json_in_root(
                marker_path,
                self._new_project_marker_payload(transaction, state, reason),
                trusted_root=transaction["project_dir"],
                max_bytes=NEW_PROJECT_RECOVERY_MAX_BYTES,
                indent=2,
                ensure_ascii=False,
            )
        except Exception as exc:
            self._log_new_project_artifact_event(
                "new_project_recovery_marker_write_failed",
                marker=marker_path,
                error=str(exc),
            )
            return False
        marker_signature = self._new_project_artifact_signature(marker_path)
        if marker_signature is None:
            return False
        transaction["recovery_marker_signature"] = marker_signature
        transaction["recovery_marker_state"] = str(state or "preserved")
        return True

    def _remove_new_project_recovery_marker(self, transaction):
        marker_path = transaction.get("recovery_marker_path", "")
        if not marker_path or not os.path.lexists(marker_path):
            transaction.pop("recovery_marker_signature", None)
            return True
        known_signature = transaction.get("recovery_marker_signature")
        if not known_signature or not self._new_project_artifact_signature_matches(marker_path, known_signature):
            self._log_new_project_artifact_event(
                "new_project_recovery_marker_remove_refused",
                marker=marker_path,
                reason="marker_identity_or_content_changed",
            )
            return False
        try:
            os.remove(marker_path)
        except OSError as exc:
            self._log_new_project_artifact_event(
                "new_project_recovery_marker_remove_failed",
                marker=marker_path,
                error=str(exc),
            )
            return False
        transaction.pop("recovery_marker_signature", None)
        return True

    def _read_new_project_recovery_marker(self, transaction):
        marker_path = transaction.get("recovery_marker_path", "")
        if not marker_path or not os.path.lexists(marker_path):
            return None, ""
        try:
            before = self._new_project_artifact_signature(marker_path)
            payload = read_json_bounded_in_root(
                marker_path,
                trusted_root=transaction["project_dir"],
                max_bytes=NEW_PROJECT_RECOVERY_MAX_BYTES,
            )
            after = self._new_project_artifact_signature(marker_path)
            if before is None or before != after:
                return None, "recovery_marker_changed_while_reading"
        except json.JSONDecodeError:
            return None, "recovery_marker_json_invalid"
        except ValueError as exc:
            if "too_large" in str(exc):
                return None, "recovery_marker_size_invalid"
            return None, "recovery_marker_json_invalid"
        except Exception:
            return None, "recovery_marker_not_safe_regular_file"
        allowed_keys = {
            "schema_version",
            "state",
            "created_at",
            "expires_at",
            "project_kind",
            "project_name",
            "project_directory",
            "manifest",
            "database",
            "preexisting_artifacts",
            "artifacts",
            "reason",
        }
        if not isinstance(payload, dict) or set(payload) != allowed_keys:
            return None, "recovery_marker_shape_invalid"
        if payload.get("schema_version") != NEW_PROJECT_RECOVERY_SCHEMA:
            return None, "recovery_marker_schema_invalid"
        if payload.get("state") not in {
            "published",
            "preserved",
            "rollback_in_progress",
            "delete_incomplete",
            "committed",
        }:
            return None, "recovery_marker_state_invalid"
        created_at = payload.get("created_at")
        expires_at = payload.get("expires_at")
        now = int(time.time())
        if (
            not isinstance(created_at, int)
            or isinstance(created_at, bool)
            or not isinstance(expires_at, int)
            or isinstance(expires_at, bool)
            or created_at <= 0
            or expires_at <= created_at
            or expires_at - created_at > NEW_PROJECT_RECOVERY_TTL_SECONDS
            or created_at > now + NEW_PROJECT_RECOVERY_CLOCK_SKEW_SECONDS
        ):
            return None, "recovery_marker_time_invalid"
        if now >= expires_at:
            return None, "recovery_marker_expired_manual_open_required"
        if payload.get("project_kind") != transaction.get("project_kind"):
            return None, "recovery_marker_project_kind_mismatch"
        if payload.get("project_name") != transaction.get("project_name"):
            return None, "recovery_marker_project_name_mismatch"
        if path_identity(payload.get("project_directory", "")) != path_identity(transaction.get("project_dir", "")):
            return None, "recovery_marker_project_directory_mismatch"
        if payload.get("manifest") != os.path.basename(transaction.get("manifest_path", "")):
            return None, "recovery_marker_manifest_mismatch"
        if payload.get("database") != os.path.basename(transaction.get("database_path", "")):
            return None, "recovery_marker_database_mismatch"
        if payload.get("preexisting_artifacts") != []:
            return None, "recovery_marker_preexisting_artifacts_invalid"

        expected_by_name = {os.path.basename(path): path for path in transaction.get("artifacts", [])}
        raw_artifacts = payload.get("artifacts")
        if not isinstance(raw_artifacts, list) or not (2 <= len(raw_artifacts) <= len(expected_by_name)):
            return None, "recovery_marker_artifact_count_invalid"
        records = {}
        quarantine_names = set()
        for item in raw_artifacts:
            if not isinstance(item, dict) or set(item) != {
                "path",
                "quarantine_path",
                "identity",
                "size",
                "sha256",
            }:
                return None, "recovery_marker_artifact_shape_invalid"
            original = expected_by_name.get(item.get("path"))
            if not original or original in records:
                return None, "recovery_marker_artifact_path_invalid"
            identity = item.get("identity")
            digest = item.get("sha256")
            if (
                not isinstance(identity, list)
                or len(identity) != 2
                or any(not isinstance(value, int) or value < 0 for value in identity)
                or not isinstance(item.get("size"), int)
                or item["size"] < 0
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                return None, "recovery_marker_artifact_signature_invalid"
            quarantine_name = item.get("quarantine_path")
            quarantine_path = ""
            if quarantine_name:
                if (
                    not isinstance(quarantine_name, str)
                    or os.path.basename(quarantine_name) != quarantine_name
                    or not quarantine_name.startswith(".taxamask-new-project-quarantine-")
                    or quarantine_name in quarantine_names
                    or quarantine_name in expected_by_name
                ):
                    return None, "recovery_marker_quarantine_path_invalid"
                quarantine_names.add(quarantine_name)
                quarantine_path = canonical_path(os.path.join(transaction["project_dir"], quarantine_name))
            records[original] = {
                "identity": list(identity),
                "size": item["size"],
                "sha256": digest,
                "quarantine_path": quarantine_path,
            }
        if transaction.get("manifest_path") not in records or transaction.get("database_path") not in records:
            return None, "recovery_marker_primary_artifacts_missing"
        transaction["recovery_marker_signature"] = after
        transaction["recovery_marker_created_at"] = created_at
        transaction["recovery_marker_expires_at"] = expires_at
        return {
            "state": payload["state"],
            "reason": payload.get("reason", ""),
            "records": records,
        }, ""

    def _new_project_record_location(self, original, record, *, allow_missing=False):
        quarantine = str(record.get("quarantine_path") or "")
        original_exists = os.path.lexists(original)
        quarantine_exists = bool(quarantine and os.path.lexists(quarantine))
        if original_exists and quarantine_exists:
            return "", "artifact_exists_at_original_and_quarantine"
        if original_exists:
            if self._new_project_artifact_signature_matches(original, record):
                return "original", ""
            return "", "artifact_signature_changed_at_original"
        if quarantine_exists:
            if self._new_project_artifact_signature_matches(quarantine, record):
                return "quarantine", ""
            return "", "artifact_signature_changed_at_quarantine"
        if allow_missing:
            return "missing", ""
        return "", "artifact_missing_from_original_and_quarantine"

    def _finish_new_project_delete_recovery(self, transaction, records):
        for expected in transaction.get("artifacts", []):
            if expected not in records and os.path.lexists(expected):
                return False, f"delete_recovery_unowned_artifact_present:{os.path.basename(expected)}"
        remaining = []
        for original, record in records.items():
            location, reason = self._new_project_record_location(original, record, allow_missing=True)
            if reason:
                return False, reason
            if location == "original":
                return False, "delete_recovery_found_original_artifact"
            if location == "quarantine":
                remaining.append((original, record["quarantine_path"], record))
        for _original, quarantine, record in remaining:
            if not self._new_project_artifact_signature_matches(quarantine, record):
                return False, "delete_recovery_quarantine_changed_before_remove"
            try:
                os.remove(quarantine)
            except OSError as exc:
                return False, f"delete_recovery_remove_failed:{exc}"
        if not self._remove_new_project_recovery_marker(transaction):
            return False, "delete_recovery_marker_remove_failed"
        return True, ""

    def _clone_pending_new_project_transaction(self, transaction, action):
        stored = dict(transaction)
        stored["recovery_action"] = str(action)
        stored["artifacts"] = list(transaction.get("artifacts", []))
        stored["existed_before"] = dict(transaction.get("existed_before", {}))
        stored["published_artifacts"] = {
            path: {
                "identity": list(record.get("identity", [])),
                "size": record.get("size", -1),
                "sha256": str(record.get("sha256", "")),
                "quarantine_path": str(record.get("quarantine_path") or ""),
            }
            for path, record in transaction.get("published_artifacts", {}).items()
            if isinstance(record, dict)
        }
        return stored

    def _store_pending_new_project_recovery(self, transaction, action):
        recoveries = getattr(self, "_pending_new_project_recoveries", None)
        if not isinstance(recoveries, dict):
            recoveries = {}
            self._pending_new_project_recoveries = recoveries
        recoveries[transaction["key"]] = self._clone_pending_new_project_transaction(
            transaction,
            action,
        )

    def _pending_new_project_recovery_reason(self, transaction, stored):
        if not isinstance(stored, dict):
            return "pending_recovery_record_invalid"
        if stored.get("key") != transaction.get("key"):
            return "pending_recovery_key_mismatch"
        if stored.get("project_kind") != transaction.get("project_kind"):
            return "pending_recovery_project_kind_mismatch"
        if stored.get("project_name") != transaction.get("project_name"):
            return "pending_recovery_project_name_mismatch"
        for field in ("project_dir", "manifest_path", "database_path", "recovery_marker_path"):
            if path_identity(stored.get(field, "")) != path_identity(transaction.get(field, "")):
                return f"pending_recovery_{field}_mismatch"
        stored_artifacts = stored.get("artifacts")
        if not isinstance(stored_artifacts, list) or [
            path_identity(path) for path in stored_artifacts
        ] != [path_identity(path) for path in transaction.get("artifacts", [])]:
            return "pending_recovery_artifacts_mismatch"
        existed_before = stored.get("existed_before")
        if not isinstance(existed_before, dict) or any(existed_before.values()):
            return "pending_recovery_preexisting_artifact_recorded"
        created_at = stored.get("recovery_marker_created_at")
        expires_at = stored.get("recovery_marker_expires_at")
        now = int(time.time())
        if (
            not isinstance(created_at, int)
            or isinstance(created_at, bool)
            or not isinstance(expires_at, int)
            or isinstance(expires_at, bool)
            or created_at <= 0
            or expires_at <= created_at
            or expires_at - created_at > NEW_PROJECT_RECOVERY_TTL_SECONDS
            or created_at > now + NEW_PROJECT_RECOVERY_CLOCK_SKEW_SECONDS
            or now >= expires_at
        ):
            return "pending_recovery_time_invalid_or_expired"
        records = stored.get("published_artifacts")
        if (
            not isinstance(records, dict)
            or stored.get("manifest_path") not in records
            or stored.get("database_path") not in records
            or any(path not in stored_artifacts for path in records)
        ):
            return "pending_recovery_artifact_records_invalid"
        project_dir_identity = path_identity(transaction.get("project_dir", ""))
        for record in records.values():
            quarantine = str(record.get("quarantine_path") or "")
            if not quarantine:
                continue
            quarantine_identity = path_identity(quarantine)
            try:
                inside_project = (
                    project_dir_identity
                    and os.path.commonpath([project_dir_identity, quarantine_identity])
                    == project_dir_identity
                )
            except (OSError, ValueError):
                inside_project = False
            if (
                not inside_project
                or not os.path.basename(quarantine).startswith(
                    ".taxamask-new-project-quarantine-"
                )
            ):
                return "pending_recovery_quarantine_path_invalid"
        return ""

    def _restore_trusted_new_project_artifacts(self, transaction, records):
        locations = []
        for expected in transaction.get("artifacts", []):
            if expected not in records and os.path.lexists(expected):
                return f"unowned_artifact_present:{os.path.basename(expected)}"
        for original, record in records.items():
            location, reason = self._new_project_record_location(original, record)
            if reason:
                return reason
            locations.append((original, record, location))
        for original, record, location in locations:
            if location != "quarantine":
                continue
            quarantine = record["quarantine_path"]
            if os.path.lexists(original) or not self._new_project_artifact_signature_matches(
                quarantine,
                record,
            ):
                return "quarantine_restore_precondition_changed"
            try:
                os.replace(quarantine, original)
            except OSError as exc:
                return f"quarantine_restore_failed:{exc}"
            if not self._new_project_artifact_signature_matches(original, record):
                return "quarantine_restore_verification_failed"
        if not self._new_project_manifest_matches_transaction(transaction):
            return "recovered_manifest_validation_failed"
        for original, record in records.items():
            if not self._new_project_artifact_signature_matches(original, record):
                return "recovered_artifact_changed_after_restore"
        return ""

    def _recover_new_project_from_memory(self, transaction):
        recoveries = getattr(self, "_pending_new_project_recoveries", None)
        if not isinstance(recoveries, dict):
            return None, "", False
        stored = recoveries.get(transaction.get("key"))
        if stored is None:
            return None, "", False
        reason = self._pending_new_project_recovery_reason(transaction, stored)
        if reason:
            return None, reason, False
        candidate = self._clone_pending_new_project_transaction(
            stored,
            stored.get("recovery_action", "open_preserved"),
        )
        action = candidate.get("recovery_action")
        if action == "finish_delete":
            deleted, delete_reason = self._finish_new_project_delete_recovery(
                candidate,
                candidate["published_artifacts"],
            )
            if not deleted:
                return None, delete_reason, False
            self._clear_preserved_new_project(candidate)
            return None, "", True
        if action != "open_preserved":
            return None, "pending_recovery_action_invalid", False
        restore_reason = self._restore_trusted_new_project_artifacts(
            candidate,
            candidate["published_artifacts"],
        )
        if restore_reason:
            return None, restore_reason, False
        candidate.update(
            {
                "published": False,
                "cleanup_safe": True,
                "recover_existing": True,
                "unsafe_reason": "",
            }
        )
        return candidate, "", False

    def _recover_new_project_from_marker(self, transaction):
        marker, reason = self._read_new_project_recovery_marker(transaction)
        if marker is None:
            return None, reason
        state = marker["state"]
        if state == "committed":
            if self._remove_new_project_recovery_marker(transaction):
                return None, ""
            return None, "committed_marker_cleanup_failed"
        return None, f"recovery_marker_{state}_requires_manual_review"

    def _new_project_manifest_matches_transaction(self, transaction):
        manifest_path = transaction.get("manifest_path", "")
        database_path = transaction.get("database_path", "")
        if (
            not manifest_path
            or not database_path
            or os.path.islink(manifest_path)
            or os.path.islink(database_path)
            or not os.path.isfile(manifest_path)
            or not os.path.isfile(database_path)
        ):
            return False
        try:
            payload = read_project_manifest(manifest_path)
            resolved_database = resolve_manifest_database_path(manifest_path, payload)
        except Exception:
            return False
        expected_type = TIF_PROJECT_TYPE if transaction.get("project_kind") == "tif" else "2d_image_annotation"
        return (
            payload.get("project_type") == expected_type
            and str(payload.get("name") or "") == transaction.get("project_name", "")
            and path_identity(resolved_database) == path_identity(database_path)
        )

    def _new_project_artifact_transaction(self, manager, project_kind, project_name, project_dir):
        transaction = {
            "project_kind": str(project_kind or ""),
            "project_name": str(project_name or ""),
            "project_dir": canonical_path(project_dir),
            "published": False,
            "cleanup_safe": False,
            "recover_existing": False,
            "unsafe_reason": "artifact_path_resolver_unavailable",
        }
        resolver = getattr(manager, "_default_sqlite_paths_for_new_project", None)
        if not callable(resolver):
            return transaction
        try:
            if transaction["project_kind"] == "tif":
                manifest_path, database_path = resolver(project_dir)
            else:
                manifest_path, database_path = resolver(project_name, project_dir)
            manifest_path = canonical_path(manifest_path)
            database_path = canonical_path(database_path)
            project_dir_identity = path_identity(project_dir)
            if not project_dir_identity:
                raise ValueError("new_project_directory_identity_unavailable")
            for candidate in (manifest_path, database_path):
                candidate_identity = path_identity(candidate)
                if os.path.commonpath([project_dir_identity, candidate_identity]) != project_dir_identity:
                    raise ValueError("new_project_artifact_outside_selected_directory")
        except Exception as exc:
            transaction["unsafe_reason"] = str(exc)
            return transaction

        artifacts = [
            f"{database_path}-wal",
            f"{database_path}-shm",
            f"{database_path}-journal",
            database_path,
            manifest_path,
        ]
        transaction.update(
            {
                "manifest_path": manifest_path,
                "database_path": database_path,
                "artifacts": artifacts,
                "existed_before": {path: os.path.lexists(path) for path in artifacts},
                "key": (transaction["project_kind"], path_identity(manifest_path)),
                "recovery_marker_path": self._new_project_recovery_marker_path(manifest_path),
                "unsafe_reason": "not_published",
            }
        )
        candidate, blocked_reason, cleanup_completed = self._recover_new_project_from_memory(
            transaction
        )
        if candidate is not None:
            return candidate
        if blocked_reason:
            transaction["recovery_blocked_reason"] = blocked_reason
            self._log_new_project_artifact_event(
                "new_project_pending_recovery_invalid",
                project_kind=transaction["project_kind"],
                manifest=manifest_path,
                reason=blocked_reason,
            )
            return transaction
        if cleanup_completed:
            transaction["existed_before"] = {
                path: os.path.lexists(path) for path in artifacts
            }
        candidate, blocked_reason = self._recover_new_project_from_marker(transaction)
        if candidate is not None:
            return candidate
        if blocked_reason:
            transaction["recovery_blocked_reason"] = blocked_reason
            self._log_new_project_artifact_event(
                "new_project_preserved_recovery_invalid",
                project_kind=transaction["project_kind"],
                manifest=manifest_path,
                reason=blocked_reason,
            )
            return transaction
        preexisting = [
            path
            for path in transaction.get("artifacts", [])
            if transaction.get("existed_before", {}).get(path)
        ]
        if preexisting:
            transaction["creation_blocked_reason"] = (
                f"preexisting_new_project_artifact:{os.path.basename(preexisting[0])}"
            )
            self._log_new_project_artifact_event(
                "new_project_creation_refused_preexisting_artifact",
                project_kind=transaction["project_kind"],
                manifest=manifest_path,
                artifact=preexisting[0],
            )
            return transaction
        recoveries = getattr(self, "_pending_new_project_recoveries", None)
        if isinstance(recoveries, dict):
            recoveries.pop(transaction["key"], None)
        return transaction

    def _capture_new_project_publication(self, transaction, manager):
        transaction["published"] = True
        transaction["actual_manifest_path"] = canonical_path(getattr(manager, "current_project_path", "") or "")
        transaction["actual_database_path"] = canonical_path(getattr(manager, "current_database_path", "") or "")
        if not transaction.get("manifest_path") or not transaction.get("database_path"):
            transaction["unsafe_reason"] = "artifact_paths_not_resolved_before_create"
            return False
        preexisting = [path for path in transaction.get("artifacts", []) if transaction.get("existed_before", {}).get(path)]
        if preexisting:
            transaction["unsafe_reason"] = f"artifact_existed_before_create:{os.path.basename(preexisting[0])}"
            return False
        if path_identity(transaction["actual_manifest_path"]) != path_identity(transaction["manifest_path"]):
            transaction["unsafe_reason"] = "published_manifest_path_mismatch"
            return False
        if path_identity(transaction["actual_database_path"]) != path_identity(transaction["database_path"]):
            transaction["unsafe_reason"] = "published_database_path_mismatch"
            return False
        if not self._new_project_manifest_matches_transaction(transaction):
            transaction["unsafe_reason"] = "published_manifest_validation_failed"
            return False
        records = {}
        for path in transaction.get("artifacts", []):
            if not os.path.lexists(path):
                continue
            signature = self._new_project_artifact_signature(path)
            if signature is None:
                transaction["unsafe_reason"] = f"published_artifact_signature_unavailable:{os.path.basename(path)}"
                return False
            records[path] = {**signature, "quarantine_path": ""}
        if transaction["manifest_path"] not in records or transaction["database_path"] not in records:
            transaction["unsafe_reason"] = "published_primary_artifact_signature_unavailable"
            return False
        transaction["published_artifacts"] = records
        transaction["cleanup_safe"] = self._write_new_project_recovery_marker(
            transaction,
            "published",
            "new_project_storage_published_before_ui_finalize",
        )
        transaction["unsafe_reason"] = "" if transaction["cleanup_safe"] else "recovery_marker_write_failed"
        return transaction["cleanup_safe"]

    def _remember_preserved_new_project(self, transaction, reason):
        records = transaction.get("published_artifacts")
        if (
            not transaction.get("key")
            or not isinstance(records, dict)
            or transaction.get("manifest_path") not in records
            or transaction.get("database_path") not in records
            or any(transaction.get("existed_before", {}).values())
        ):
            self._log_new_project_artifact_event(
                "new_project_finalize_artifacts_preserved_without_retry",
                project_kind=transaction.get("project_kind", ""),
                manifest=transaction.get("manifest_path", transaction.get("actual_manifest_path", "")),
                reason=str(reason or transaction.get("unsafe_reason", "")),
            )
            return False
        marker_written = self._write_new_project_recovery_marker(transaction, "preserved", reason)
        self._store_pending_new_project_recovery(transaction, "open_preserved")
        self._log_new_project_artifact_event(
            "new_project_finalize_artifacts_preserved_for_retry",
            project_kind=transaction.get("project_kind", ""),
            manifest=transaction.get("manifest_path", ""),
            database=transaction.get("database_path", ""),
            reason=str(reason or transaction.get("unsafe_reason", "")),
            marker_written=marker_written,
        )
        return marker_written

    def _clear_preserved_new_project(self, transaction):
        recoveries = getattr(self, "_pending_new_project_recoveries", None)
        if isinstance(recoveries, dict) and transaction.get("key") in recoveries:
            recoveries.pop(transaction["key"], None)

    def _new_project_publication_preflight(self, transaction):
        if not self._new_project_manifest_matches_transaction(transaction):
            return "artifact_validation_changed_before_cleanup"
        records = transaction.get("published_artifacts", {})
        for expected in transaction.get("artifacts", []):
            record = records.get(expected)
            if record is None:
                if os.path.lexists(expected):
                    return f"artifact_appeared_after_publication:{os.path.basename(expected)}"
                continue
            if not self._new_project_artifact_signature_matches(expected, record):
                return f"artifact_identity_or_content_changed:{os.path.basename(expected)}"
        return ""

    def _restore_new_project_quarantine(self, moved):
        errors = []
        for original, quarantine, record in reversed(moved):
            try:
                if os.path.lexists(original):
                    raise FileExistsError(original)
                if not self._new_project_artifact_signature_matches(quarantine, record):
                    raise RuntimeError("quarantine_signature_changed")
                os.replace(quarantine, original)
                if not self._new_project_artifact_signature_matches(original, record):
                    raise RuntimeError("restored_signature_changed")
            except Exception as exc:
                errors.append(f"{original}: {exc}")
        return errors

    def _rollback_new_project_publication(self, transaction, error):
        if not transaction.get("published"):
            return False
        if not transaction.get("cleanup_safe"):
            self._remember_preserved_new_project(transaction, transaction.get("unsafe_reason", "cleanup_not_safe"))
            return False
        unsafe_reason = self._new_project_publication_preflight(transaction)
        if unsafe_reason:
            self._remember_preserved_new_project(transaction, unsafe_reason)
            return False

        moved = []
        token = f"{os.getpid()}_{time.time_ns()}"
        records = transaction.get("published_artifacts", {})
        for index, original in enumerate(transaction.get("artifacts", [])):
            record = records.get(original)
            if record is not None:
                record["quarantine_path"] = canonical_path(
                    os.path.join(
                        transaction["project_dir"],
                        f".taxamask-new-project-quarantine-{token}-{index}.data",
                    )
                )
        if not self._write_new_project_recovery_marker(
            transaction,
            "rollback_in_progress",
            "ui_finalize_failed_and_artifacts_are_being_quarantined",
        ):
            self._remember_preserved_new_project(transaction, "rollback_marker_update_failed")
            return False
        try:
            for original in transaction.get("artifacts", []):
                record = records.get(original)
                if record is None:
                    if os.path.lexists(original):
                        raise RuntimeError(f"unowned_artifact_appeared:{original}")
                    continue
                if not self._new_project_artifact_signature_matches(original, record):
                    raise RuntimeError(f"new_project_artifact_changed_before_move:{original}")
                for unowned in transaction.get("artifacts", []):
                    if unowned not in records and os.path.lexists(unowned):
                        raise RuntimeError(f"unowned_artifact_appeared:{unowned}")
                quarantine = record["quarantine_path"]
                if os.path.lexists(quarantine):
                    raise FileExistsError(quarantine)
                os.replace(original, quarantine)
                if not self._new_project_artifact_signature_matches(quarantine, record):
                    raise RuntimeError(f"new_project_quarantine_verification_failed:{original}")
                moved.append((original, quarantine, record))
            for unowned in transaction.get("artifacts", []):
                if unowned not in records and os.path.lexists(unowned):
                    raise RuntimeError(f"unowned_artifact_appeared:{unowned}")
        except Exception as move_exc:
            rollback_errors = self._restore_new_project_quarantine(moved)
            self._remember_preserved_new_project(transaction, f"artifact_quarantine_failed:{move_exc}")
            self._log_new_project_artifact_event(
                "new_project_finalize_artifact_cleanup_failed",
                project_kind=transaction.get("project_kind", ""),
                manifest=transaction.get("manifest_path", ""),
                error=str(error),
                cleanup_error=str(move_exc),
                rollback_errors=rollback_errors,
            )
            return False

        for _original, quarantine, record in moved:
            if not self._new_project_artifact_signature_matches(quarantine, record):
                self._remember_preserved_new_project(transaction, "quarantine_changed_before_delete")
                return False
        if not self._write_new_project_recovery_marker(
            transaction,
            "delete_incomplete",
            "all_owned_artifacts_quarantined_before_delete",
        ):
            self._remember_preserved_new_project(
                transaction,
                "delete_incomplete_marker_update_failed_before_delete",
            )
            self._log_new_project_artifact_event(
                "new_project_finalize_artifact_delete_not_started",
                project_kind=transaction.get("project_kind", ""),
                manifest=transaction.get("manifest_path", ""),
                reason="delete_incomplete_marker_update_failed_before_delete",
            )
            return False
        self._store_pending_new_project_recovery(transaction, "finish_delete")
        deleted, delete_reason = self._finish_new_project_delete_recovery(
            transaction,
            records,
        )
        if not deleted:
            self._log_new_project_artifact_event(
                "new_project_finalize_artifact_delete_incomplete",
                project_kind=transaction.get("project_kind", ""),
                manifest=transaction.get("manifest_path", ""),
                cleanup_errors=[delete_reason],
            )
            return False
        self._clear_preserved_new_project(transaction)
        self._log_new_project_artifact_event(
            "new_project_finalize_artifacts_rolled_back",
            project_kind=transaction.get("project_kind", ""),
            manifest=transaction.get("manifest_path", ""),
            database=transaction.get("database_path", ""),
            error=str(error),
            quarantined_cleanup_errors=[],
            marker_removed=True,
        )
        return True

    def _complete_new_project_publication(self, transaction):
        recovered_existing = bool(transaction.get("recover_existing"))
        committed_written = self._write_new_project_recovery_marker(
            transaction,
            "committed",
            "new_project_ui_finalize_completed",
        )
        marker_removed = (
            self._remove_new_project_recovery_marker(transaction)
            if committed_written
            else False
        )
        self._clear_preserved_new_project(transaction)
        if not committed_written or not marker_removed:
            self._log_new_project_artifact_event(
                "new_project_commit_marker_cleanup_incomplete",
                project_kind=transaction.get("project_kind", ""),
                manifest=transaction.get("manifest_path", ""),
                committed_written=committed_written,
                marker_removed=marker_removed,
            )
        if recovered_existing:
            self._log_new_project_artifact_event(
                "new_project_preserved_recovery_completed",
                project_kind=transaction.get("project_kind", ""),
                manifest=transaction.get("manifest_path", ""),
            )
        return committed_written and marker_removed

    def _active_tif_switch_recovery_state(self):
        state = self._active_project_switch_recovery_state()
        if state.get("effective_project_kind") != "tif":
            return None
        state["project_path"] = str(getattr(getattr(self, "tif_project", None), "current_project_path", "") or "")
        return state

    def _restore_active_tif_after_failed_switch(self, state):
        return self._restore_active_project_after_failed_switch(state)

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
        if agent_panel is not None and hasattr(agent_panel, "shutdown"):
            try:
                agent_panel.shutdown()
            except Exception:
                pass
        elif agent_panel is not None and hasattr(agent_panel, "stop_dashboard"):
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
        thread = getattr(self, "batch_panel_split_thread", None)
        if thread is not None and thread.isRunning():
            if hasattr(thread, "cancel"):
                thread.cancel()
            thread.wait(30000)
        thread = getattr(self, "parts_model_preload_thread", None)
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
