from __future__ import annotations

from collections import OrderedDict

from PySide6.QtWidgets import QApplication

try:
    from AntSleap.core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG, sanitize_tif_backend_config
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.services.tif_backend_workflow_service import TifBackendWorkflowService
    from AntSleap.services.tif_label_edit_service import TifLabelEditService
    from AntSleap.services.tif_local_axis_service import TifLocalAxisService
    from AntSleap.services.tif_roi_part_service import TifRoiPartService
    from AntSleap.services.tif_selection_controller import TifSelectionController
    from AntSleap.services.tif_task_manager import TifTaskManager
    from AntSleap.services.tif_truth_promotion_service import TifTruthPromotionService
    from AntSleap.services.tif_volume_preview_service import TifVolumePreviewService
    from AntSleap.ui.style import normalize_theme
    from AntSleap.ui.tif_agent_context import TifAgentContextBuilder
    from AntSleap.ui.tif_annotation_workflow_controller import TifAnnotationWorkflowController
    from AntSleap.ui.tif_backend_panel_controller import TifBackendPanelController
    from AntSleap.ui.tif_local_axis_controller import TifLocalAxisController
    from AntSleap.ui.tif_project_lifecycle_controller import TifProjectLifecycleController
    from AntSleap.ui.tif_part_mask_workflow_controller import TifPartMaskWorkflowController
    from AntSleap.ui.tif_roi_workflow_controller import TifRoiWorkflowController
    from AntSleap.ui.tif_result_review_controller import TifResultReviewController
    from AntSleap.ui.tif_preview_controller import TifPreviewController
    from AntSleap.ui.tif_selection_workflow_controller import TifSelectionWorkflowController
    from AntSleap.ui.tif_tasks import TifQtTaskAdapter
    from AntSleap.ui.tif_workbench_signal_router import TifWorkbenchSignalRouter
    from AntSleap.ui.tif_workbench_coordinator import TifWorkbenchCoordinator
    from AntSleap.ui.tif_workbench_view import TifWorkbenchView
    from AntSleap.ui.tif_volume_render_controller import TifVolumeRenderController
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG, sanitize_tif_backend_config
    from core.tif_project import TifProjectManager
    from services.tif_backend_workflow_service import TifBackendWorkflowService
    from services.tif_label_edit_service import TifLabelEditService
    from services.tif_local_axis_service import TifLocalAxisService
    from services.tif_roi_part_service import TifRoiPartService
    from services.tif_selection_controller import TifSelectionController
    from services.tif_task_manager import TifTaskManager
    from services.tif_truth_promotion_service import TifTruthPromotionService
    from services.tif_volume_preview_service import TifVolumePreviewService
    from ui.style import normalize_theme
    from ui.tif_agent_context import TifAgentContextBuilder
    from ui.tif_annotation_workflow_controller import TifAnnotationWorkflowController
    from ui.tif_backend_panel_controller import TifBackendPanelController
    from ui.tif_local_axis_controller import TifLocalAxisController
    from ui.tif_project_lifecycle_controller import TifProjectLifecycleController
    from ui.tif_part_mask_workflow_controller import TifPartMaskWorkflowController
    from ui.tif_roi_workflow_controller import TifRoiWorkflowController
    from ui.tif_result_review_controller import TifResultReviewController
    from ui.tif_preview_controller import TifPreviewController
    from ui.tif_selection_workflow_controller import TifSelectionWorkflowController
    from ui.tif_tasks import TifQtTaskAdapter
    from ui.tif_workbench_signal_router import TifWorkbenchSignalRouter
    from ui.tif_workbench_coordinator import TifWorkbenchCoordinator
    from ui.tif_workbench_view import TifWorkbenchView
    from ui.tif_volume_render_controller import TifVolumeRenderController


class TifWorkbenchShell:
    SHELL_SCOPE = "shell"

    def __init__(self, workbench):
        self.workbench = workbench
        self.view = TifWorkbenchView(workbench)
        self.signal_router = TifWorkbenchSignalRouter()

    def configure_foundation(self, project_manager, lang, parent, config_manager):
        workbench = self.workbench
        workbench.project = project_manager or TifProjectManager()
        workbench.lang = lang
        workbench.config_manager = config_manager
        parent_theme = getattr(parent, "current_theme", None) if parent is not None else None
        application = QApplication.instance()
        app_theme = application.property("activeTheme") if isinstance(application, QApplication) else None
        workbench.current_theme = normalize_theme(parent_theme or app_theme or "dark")
        config = config_manager.get("tif_backend", DEFAULT_TIF_BACKEND_CONFIG) if config_manager is not None else DEFAULT_TIF_BACKEND_CONFIG
        workbench.backend_config = sanitize_tif_backend_config(config)
        workbench.selection_controller = TifSelectionController()
        workbench.label_edit_service = TifLabelEditService()
        workbench.truth_promotion_service = TifTruthPromotionService(workbench.project)
        workbench.backend_workflow_service = TifBackendWorkflowService(workbench.project)
        workbench.roi_part_service = TifRoiPartService()
        workbench.volume_preview_service = TifVolumePreviewService()
        workbench.local_axis_service = TifLocalAxisService()
        workbench.task_manager = TifTaskManager()
        workbench.task_adapter = TifQtTaskAdapter(workbench.task_manager)
        workbench.agent_context_builder = TifAgentContextBuilder(workbench)
        workbench.coordinator = TifWorkbenchCoordinator(workbench)
        workbench.backend_panel_controller = TifBackendPanelController(workbench)
        workbench.result_review_controller = TifResultReviewController(workbench)
        workbench.local_axis_controller = TifLocalAxisController(workbench)
        workbench.preview_controller = TifPreviewController(workbench)
        workbench.volume_render_controller = TifVolumeRenderController(workbench)
        workbench.annotation_workflow_controller = TifAnnotationWorkflowController(workbench)
        workbench.roi_workflow_controller = TifRoiWorkflowController(workbench)
        workbench.part_mask_workflow_controller = TifPartMaskWorkflowController(workbench)
        workbench.selection_workflow_controller = TifSelectionWorkflowController(workbench)
        workbench.project_lifecycle_controller = TifProjectLifecycleController(workbench)
        self.controllers = OrderedDict(
            (
                ("selection", workbench.selection_workflow_controller),
                ("project_lifecycle", workbench.project_lifecycle_controller),
                ("annotation", workbench.annotation_workflow_controller),
                ("roi", workbench.roi_workflow_controller),
                ("part_mask", workbench.part_mask_workflow_controller),
                ("preview", workbench.preview_controller),
                ("volume_render", workbench.volume_render_controller),
                ("local_axis", workbench.local_axis_controller),
                ("backend_panel", workbench.backend_panel_controller),
                ("result_review", workbench.result_review_controller),
            )
        )

    def initialize_runtime_state(self):
        workbench = self.workbench
        defaults = {
            "current_part": None,
            "image_volume": None,
            "label_volume": None,
            "_slice_unavailable_override": "",
            "edit_volume": None,
            "_loading_specimen": False,
            "_tif_import_thread": None,
            "_tif_import_worker": None,
            "_tif_import_progress": None,
            "_tif_import_specimen_id": "",
            "_tif_import_jobs": [],
            "_tif_import_task_id": "",
            "slice_axis": "z",
            "_slice_positions": {"z": 0, "y": 0, "x": 0},
            "display_mode": "slice",
        }
        for name, value in defaults.items():
            setattr(workbench, name, value)
        workbench.advanced_annotation_tool_specs = workbench._advanced_annotation_tool_specs()
        workbench.annotation_workflow_controller.initialize_compatibility_state()
        workbench.roi_workflow_controller.initialize_compatibility_state()

    def bind_shell_signals(self):
        view = self.view
        view.register_scope(
            self.SHELL_SCOPE,
            "btn_start_center",
            "btn_ask_agent",
            "btn_show_workbench_log",
        )
        self.signal_router.bind(
            self.SHELL_SCOPE,
            "start_center",
            view.require(self.SHELL_SCOPE, "btn_start_center").clicked,
            self._request_start_center,
        )
        self.signal_router.bind(
            self.SHELL_SCOPE,
            "ask_agent",
            view.require(self.SHELL_SCOPE, "btn_ask_agent").clicked,
            self._request_agent,
        )
        self.signal_router.bind(
            self.SHELL_SCOPE,
            "show_log",
            view.require(self.SHELL_SCOPE, "btn_show_workbench_log").clicked,
            self.workbench.show_workbench_log,
        )

    def finalize_startup(self):
        workbench = self.workbench
        workbench._apply_button_roles()
        workbench.view_builder.build_layout()
        workbench._apply_soft_style()
        workbench._load_backend_config_into_ui()
        workbench._sync_annotation_tool_buttons()
        workbench.part_mask_workflow_controller._update_current_material_summary()
        workbench._sync_undo_redo_buttons()
        workbench._update_save_status()
        workbench._update_texts()
        workbench._sync_mode_sections()
        self.bind_shell_signals()
        workbench.selection_workflow_controller.bind_signals()
        workbench.annotation_workflow_controller.bind_signals()
        workbench.roi_workflow_controller.bind_signals()
        workbench.part_mask_workflow_controller.bind_signals()
        workbench.volume_render_controller.bind_signals()
        workbench.local_axis_controller.bind_signals()
        workbench.backend_panel_controller.bind_signals()
        workbench.result_review_controller.bind_signals()
        workbench.refresh_project()

    def notify_controllers(self, hook, *args, **kwargs):
        results = []
        for name, controller in getattr(self, "controllers", {}).items():
            callback = getattr(controller, str(hook), None)
            if callable(callback):
                results.append((name, callback(*args, **kwargs)))
        return results

    def shutdown(self):
        self.notify_controllers("on_workbench_closing")
        self.signal_router.unbind_all()
        self.notify_controllers("on_workbench_destroyed")

    def _request_start_center(self):
        self.workbench.start_center_requested.emit()

    def _request_agent(self):
        self.workbench.agent_requested.emit(self.workbench.get_agent_context())
