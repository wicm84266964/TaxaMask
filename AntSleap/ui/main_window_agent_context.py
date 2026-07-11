try:
    from AntSleap.ui.main_window_shell_dependencies import *
except ImportError:
    from ui.main_window_shell_dependencies import *


class MainWindowAgentContextMixin:
    AGENT_CONTEXT_TEXT_LIMIT = 320
    AGENT_CONTEXT_REFERENCE_TEXT_LIMIT = 960
    AGENT_CONTEXT_LOG_LINES = 6
    AGENT_CONTEXT_LOG_LINE_LIMIT = 160
    AGENT_CONTEXT_TOTAL_LIMIT = 5200

    def _recent_text_excerpt(self, widget, line_limit=AGENT_CONTEXT_LOG_LINES):
        if widget is None or not hasattr(widget, "toPlainText"):
            return ""
        lines = []
        for line in widget.toPlainText().splitlines()[-line_limit:]:
            lines.append(self._agent_context_text(line, self.AGENT_CONTEXT_LOG_LINE_LIMIT))
        return "\n".join(lines)

    def _agent_context_text(self, value, limit=AGENT_CONTEXT_TEXT_LIMIT):
        text = str(value or "").replace("\r", " ").strip()
        if len(text) <= limit:
            return text
        return f"{text[:limit]}... [truncated]"

    def _compact_agent_context(self, context):
        context = enrich_agent_context(context)
        allowed_keys = (
            "source_workbench",
            "project_type",
            "project_source_kind",
            "project_path",
            "review_project_path",
            "diagnostic_route",
            "diagnostic_focus",
            "health_check_summary",
            "validation_errors",
            "llm_context_refs",
            "source_code_refs",
            "artifact_hints",
            "safety_notes",
            "suggested_agent_action",
            "agent_route_source",
            "active_specimen_id",
            "active_volume_scope",
            "active_part_id",
            "active_reslice_id",
            "active_part_parent_bbox_zyx",
            "active_part_group_tags",
            "active_image_path",
            "active_label_role",
            "active_slice_axis",
            "active_slice_position",
            "active_volume_shape_zyx",
            "active_volume_spacing_zyx",
            "active_label_shape_zyx",
            "active_label_schema_id",
            "selected_part",
            "selected_material_id",
            "display_mode",
            "train_ready_status",
            "train_ready_reasons",
            "train_ready_part_sample_count",
            "train_ready_top_level_sample_count",
            "training_selection_scope",
            "training_sample_rule",
            "registered_tif_model_count",
            "selected_tif_model_id",
            "selected_model_manifest",
            "tif_backend_id",
            "tif_backend_python",
            "tif_backend_command_presence",
            "backend_run_active",
            "backend_action",
            "backend_run_dir",
            "backend_result_json",
            "predict_group_filter",
            "predict_group_filter_label",
            "predict_target_summary",
            "predict_selected_target_count",
            "predict_selected_targets",
            "tif_task_summary",
            "tif_state_summary",
            "preview_resource_summary",
            "local_axis_state_summary",
            "volume_lifecycle_summary",
            "volume_renderer",
            "volume_renderer_label",
            "volume_render_mode",
            "volume_projection_mode",
            "volume_mask_mode",
            "volume_density_cutoff",
            "volume_density_opacity",
            "volume_texture_target_dim",
            "volume_ray_samples",
            "volume_clarity_mode",
            "volume_detail_enhancement",
            "volume_tone_curve",
            "volume_shader_quality",
            "volume_surface_refine",
            "volume_clip_plane",
            "volume_clip_plane_depth",
            "volume_roi_high_detail",
            "volume_roi_inspect",
            "volume_roi_scale",
            "volume_roi_budget",
            "volume_inside_depth",
            "volume_front_cut",
            "volume_zoom",
            "volume_pan",
            "volume_yaw_pitch",
            "volume_gpu_warning",
            "volume_status_overlay",
            "volume_performance_diagnosis",
            "volume_uploaded_gb",
            "volume_upload_ms",
            "volume_draw_ms",
            "volume_uploaded_shape_zyx",
            "volume_texture_sampling",
            "volume_display_scaling",
            "tif_next_requirement",
            "tif_requirement_doc",
            "pdf_acquisition_stage",
            "harvest_skill",
            "harvest_skill_path",
            "harvest_outputs",
            "harvest_safety_boundary",
            "screener_profile",
            "figure_profile",
            "part_description_profile",
            "screening_mode",
            "text_llm_key_configured",
            "text_llm_base_url_configured",
            "text_llm_model",
            "text_llm_api_protocol",
            "multimodal_llm_uses_text_provider",
            "multimodal_llm_key_configured",
            "multimodal_llm_base_url_configured",
            "multimodal_llm_model",
            "multimodal_llm_api_protocol",
            "pdf_source_dir",
            "screening_output_dir",
            "extract_input_dir",
            "extract_result_folder",
            "extract_db_name",
            "extract_db_path",
            "multimodal_enabled",
            "settings_scope",
            "settings_question_focus",
            "advanced_extension_scope",
            "language",
            "theme",
            "startup_behavior",
            "project_autosave_interval_sec",
            "runtime_device",
            "model_backend",
            "active_model_profile_id",
            "active_model_profile_name",
            "parent_backend",
            "child_backend",
            "route_backend_summary",
            "parent_model_source",
            "parent_model_source_label",
            "default_child_expert",
            "default_child_expert_label",
            "default_child_route_backend",
            "route_specific_backend_count",
            "route_specific_backend_summary",
            "backend_id",
            "display_name",
            "python_executable",
            "export_formats",
            "external_backend_id",
            "external_display_name",
            "external_python",
            "parent_prepare_command_present",
            "parent_train_command_present",
            "parent_predict_command_present",
            "parent_prepare_command_has_contract",
            "parent_train_command_has_contract",
            "parent_predict_command_has_contract",
            "parent_model_manifest_present",
            "child_extension_id",
            "child_extension_display_name",
            "child_extension_python",
            "child_predict_command_present",
            "child_train_command_present",
            "child_predict_command_has_contract",
            "child_train_command_has_contract",
            "child_model_manifest_present",
            "prepare_command_present",
            "train_command_present",
            "predict_command_present",
            "prepare_command_has_contract",
            "train_command_has_contract",
            "predict_command_has_contract",
            "model_manifest_present",
            "locator_scope_count",
            "parent_box_ratio_count",
            "recent_log_excerpt",
        )
        compact = {}
        for key in allowed_keys:
            value = (context or {}).get(key)
            if not value:
                continue
            limit = self.AGENT_CONTEXT_TEXT_LIMIT
            if key in ("llm_context_refs", "source_code_refs", "artifact_hints", "safety_notes"):
                limit = self.AGENT_CONTEXT_REFERENCE_TEXT_LIMIT
            if key == "recent_log_excerpt":
                limit = self.AGENT_CONTEXT_LOG_LINES * self.AGENT_CONTEXT_LOG_LINE_LIMIT
            compact[key] = self._agent_context_text(value, limit)
        context_policy = (
            "Only compact field indexes, route hints, and short log excerpts are provided. "
            "Do not assume full project data is loaded; read the referenced docs/source/artifacts only when needed."
        )
        text_budget = len("context_policy") + len(context_policy)
        limited = {"context_policy": context_policy}
        for key, value in compact.items():
            text = str(value)
            next_budget = text_budget + len(key) + len(text)
            if next_budget > self.AGENT_CONTEXT_TOTAL_LIMIT:
                limited[key] = self._agent_context_text(text, max(80, self.AGENT_CONTEXT_TOTAL_LIMIT - text_budget - len(key)))
                break
            limited[key] = value
            text_budget = next_budget
        return limited

    def _collect_image_workbench_agent_context(self):
        model_context = self._active_model_profile_context()
        route_backends = []
        for route in self._active_project_route_manifest().get("routes", []):
            if not isinstance(route, dict):
                continue
            parent = str(route.get("parent") or "")
            child = str(route.get("child") or "")
            backend = str(route.get("expert_backend") or "")
            if parent and child:
                route_backends.append(f"{parent}->{child}:{backend or 'unknown'}")
        active_profile = _active_profile_from_manager(self.project)
        return {
            "source_workbench": "labeling",
            "project_type": "2d_stl",
            "project_source_kind": getattr(self, "active_project_source_kind", "image"),
            "project_path": self._active_recent_project_path() or getattr(self.project, "current_project_path", "") or "",
            "review_project_path": getattr(self.project, "current_project_path", "") or "",
            "active_image_path": self.current_image or "",
            "selected_part": self._current_part_name() or "",
            "active_model_profile_id": model_context.get("active_profile_id", ""),
            "active_model_profile_name": active_profile.get("display_name", ""),
            "parent_backend": model_context.get("parent_backend", ""),
            "child_backend": model_context.get("child_backend", ""),
            "route_backend_summary": "; ".join(route_backends[:12]),
            "recent_log_excerpt": self._recent_text_excerpt(getattr(self, "log_console", None)),
        }

    def _collect_blink_agent_context(self):
        active_session = getattr(self.blink_lab, "active_session", None) or {}
        return {
            "source_workbench": "blink",
            "project_type": "2d_stl",
            "project_source_kind": getattr(self, "active_project_source_kind", "image"),
            "project_path": self._active_recent_project_path() or getattr(self.project, "current_project_path", "") or "",
            "review_project_path": getattr(self.project, "current_project_path", "") or "",
            "active_image_path": getattr(self.blink_lab, "current_image_path", None) or self.current_image or "",
            "selected_part": getattr(self.blink_lab, "session_target_part", None) or "",
            "active_label_role": "blink_session" if active_session else "",
            "recent_log_excerpt": self._recent_text_excerpt(getattr(self.blink_lab, "training_log_console", None)),
        }

    def _pdf_agent_prompt(self):
        project_hint = self._agent_current_project_label()
        pdf_summary, _pdf_detail = self._start_console_pdf_summary()
        return (
            "请按 TaxaMask 的 PDF evidence workflow 作为分阶段向导接管一次 PDF 文献处理任务。"
            "这个流程面向各种分类学研究者，不要默认用户研究蚂蚁，也不要默认当前筛选配置或图文提取配置已经合适。\n\n"
            "请先读取并遵守这些本地规则/skill：\n"
            "- ANTCODE.md\n"
            "- .lab-agent/memory.md\n"
            "- vendor/ant-code/config/skills/taxonomy-pdf-harvest/SKILL.md\n"
            "- .lab-agent/skills/taxamask-pdf-evidence/SKILL.md\n\n"
            "当前现场：\n"
            f"- 当前项目：{project_hint}\n"
            f"- PDF 状态：{pdf_summary}\n"
            "- PDF 筛选依赖文本 LLM key/model；启用多模态图文复核时还需要可用的视觉模型配置。\n\n"
            "请不要一次性输出全流程长说明。请按五个阶段推进，每轮只处理当前阶段，最多问 3 个问题：\n"
            "0. 文献/PDF 来源判断：用户已经有 PDF 文件夹，还是需要先用 taxonomy-pdf-harvest 合法采集开放 PDF。\n"
            "1. key/model 就绪检查。\n"
            "2. 目标类群与 PDF 筛选条件适配。\n"
            "3. figure/caption 数据处理与图文复核条件适配。\n"
            "4. 跑通流程、说明产物位置和复核/导入边界。\n\n"
            "如果用户还没有 PDF，请先停在第 0 阶段，按 taxonomy-pdf-harvest 的边界规划检索/下载："
            "只使用开放元数据和合法暴露的 PDF 链接，不使用 Sci-Hub、LibGen、付费墙绕过、验证码绕过或登录态抓取。"
            "第 0 阶段的关键产物是 records.csv、doi_list.txt、summary.json、download_manifest.csv 和 pdfs/，"
            "这些是文献来源和下载审计材料，不是训练真值。\n\n"
            "请优先使用需求确认式交互：给我简短选项或短问题让我确认，不要用长段说明替代确认。"
            "现在先停在第 0 阶段：只确认我是否已经有待筛选 PDF 文件夹，还是需要先按目标类群合法采集开放 PDF；"
            "若已有 PDF，再进入第 1 阶段确认文本 LLM key、base URL、model、API 协议和必要的视觉模型配置。"
            "不要要求我在聊天里粘贴真实 key，不要提前展开后面复杂配置。"
        )

    def open_agent_for_pdf_workflow(self):
        prompt = self._pdf_agent_prompt()
        active_kind = getattr(self, "active_project_kind", "start")
        if active_kind in {"image", "tif"}:
            self.last_workbench_kind = active_kind
        self.active_project_kind = "start"
        self._apply_project_mode_tabs()
        self._update_start_center_texts()
        if hasattr(self, "agent_panel"):
            self.agent_panel.update_runtime_status(
                model_status=tr("Local task cards", self.current_lang),
                workflow=tr("PDF evidence workflow", self.current_lang),
                project=self._agent_current_project_label(),
                state=tr("Idle", self.current_lang),
            )
            self.agent_panel.set_prompt_text(prompt)
            if not self.agent_panel.is_running():
                self.agent_panel.start_dashboard()

    def open_agent_from_context(self, context=None):
        payload = dict(context or {})
        source_widget = self.tabs.currentWidget() if hasattr(self, "tabs") else None
        if not payload and hasattr(self, "tabs") and self.tabs.currentWidget() is self.pdf_widget:
            payload = self.pdf_widget.get_agent_context()
        if not payload and hasattr(self, "tabs") and self.tabs.currentWidget() is self.blink_lab:
            payload = self._collect_blink_agent_context()
        if not payload and hasattr(self, "tabs") and self.tabs.currentWidget() is self.tif_workbench:
            payload = self.tif_workbench.get_agent_context()
        if not payload:
            payload = self._collect_image_workbench_agent_context()
        payload = self._compact_agent_context(payload)
        if source_widget is getattr(self, "tif_workbench", None) and hasattr(self.tif_workbench, "prepare_for_agent_panel"):
            self.tif_workbench.prepare_for_agent_panel()
        active_kind = getattr(self, "active_project_kind", "start")
        if active_kind in {"image", "tif"}:
            self.last_workbench_kind = active_kind
        self.active_project_kind = "start"
        self._apply_project_mode_tabs()
        self._update_start_center_texts()
        if hasattr(self, "agent_panel"):
            self.agent_panel.set_context(payload, announce=True)
            self.agent_panel.update_runtime_status(
                model_status=tr("Local task cards", self.current_lang),
                workflow=str(payload.get("source_workbench") or self._agent_current_workflow_label()),
                project=str(payload.get("project_path") or self._agent_current_project_label()),
                state=tr("Idle", self.current_lang),
            )
            if not self.agent_panel.is_running():
                self.agent_panel.start_dashboard()

    def return_to_start_center_with_context(self):
        self._show_start_center()

    def _open_workflow_from_agent(self, workflow):
        if workflow == "tif":
            if not self._is_tif_workflow_enabled():
                self._show_tif_workflow_unavailable()
                return
            self.shell_coordinator.enter_tif()
            return
        self.shell_coordinator.enter_image()

    def _open_model_settings_from_agent(self, workflow):
        if workflow == "tif":
            if not self._is_tif_workflow_enabled():
                self._show_tif_workflow_unavailable()
                return
            self.open_tif_model_settings()
            return
        self.open_stl_model_settings()

    def enter_image_workflow(self):
        self.active_project_kind = "image"
        self.last_workbench_kind = "image"
        self._refresh_project_bound_views()
        self.tabs.setCurrentWidget(self.workbench_widget)
        self.ensure_2d_stl_models_preloaded()
        self.log(tr("Opened 2D/STL workflow.", self.current_lang))

    def enter_tif_workflow(self):
        if not self._is_tif_workflow_enabled():
            self._show_tif_workflow_unavailable()
            return
        self._ensure_tif_workbench()
        self.active_project_kind = "tif"
        self.last_workbench_kind = "tif"
        self._refresh_project_bound_views()
        self.tabs.setCurrentWidget(self.tif_workbench)
        self.log(tr("Opened TIF volume workflow.", self.current_lang))
