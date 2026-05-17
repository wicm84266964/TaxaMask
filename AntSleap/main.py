import sys
import os
import csv
import json
import re
import threading

# pyright: reportMissingImports=false, reportGeneralTypeIssues=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false, reportOptionalMemberAccess=false, reportOptionalCall=false, reportUninitializedInstanceVariable=false, reportOperatorIssue=false

# Disable Ultralytics checks BEFORE importing it
os.environ["YOLO_VERBOSE"] = "False"
os.environ["ULTRALYTICS_QUIET"] = "True" 

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(PACKAGE_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QListWidget, QPushButton, QLabel, QFileDialog, QTextEdit, 
    QComboBox, QMessageBox, QSplitter, QProgressBar, QDialog, 
    QLineEdit, QScrollArea, QRadioButton, QButtonGroup, QSlider,
    QCheckBox, QInputDialog, QGroupBox, QListWidgetItem, QMenu,
    QDialogButtonBox, QGridLayout, QSizePolicy, QFrame, QFormLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QTreeWidget, QTreeWidgetItem)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PySide6.QtGui import QIcon, QAction, QColor
import numpy as np
import torch

try:
    from AntSleap.core.project import ProjectManager
    from AntSleap.core.database import MultiModalDB
    from AntSleap.core.engine import AntEngine
    from AntSleap.core.sam_helper import SAMWorker
    from AntSleap.core.config import ConfigManager
    from AntSleap.core.window_geometry import compute_centered_window_geometry
    from AntSleap.ui.canvas import AnnotationCanvas
    from AntSleap.ui.style import (
        SCI_THEME,
        LIGHT_THEME,
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_RUN,
        BUTTON_ROLE_STOP,
        SURFACE_ROLE_CANVAS,
        SURFACE_ROLE_PANEL,
        SURFACE_ROLE_RAISED,
        SURFACE_ROLE_SUBTLE,
        SURFACE_ROLE_TOOLBAR,
        apply_theme_dialog_button_box_style,
        apply_theme_button_style,
        apply_semantic_button_style,
        apply_surface_role,
        get_theme_config,
        get_theme_stylesheet,
        normalize_theme,
        register_windows_scholarly_ui_fonts,
        themed_yes_no_question,
    )
    from AntSleap.ui.cropper import ImageCropper
    from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget
    from AntSleap.ui.blink_lab import BlinkLabWidget
    from AntSleap.ui.tif_workbench import TifWorkbenchWidget
    from AntSleap.ui.taxamask_agent_panel import TaxaMaskAgentPanel
    from AntSleap.core.dataset import TwoStageDataset
    from AntSleap.core.training_preflight import build_training_preflight, describe_training_preflight, describe_part_coverage, format_size_pair
    from AntSleap.core.cascade_routes import format_expert_label, get_route_persisted_expert_candidates, merge_expert_candidates
    from AntSleap.core.expert_notes import format_expert_display_name, load_expert_notes
    from AntSleap.core.project_templates import DEFAULT_PROJECT_TEMPLATE_ID, iter_project_templates
    from AntSleap.core.external_backend import BUILTIN_BACKEND_ID, EXTERNAL_BACKEND_ID, ExternalBackendRunner, sanitize_external_backend_config
    from AntSleap.core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG, sanitize_tif_backend_config
    from AntSleap.core.tif_export import SUPPORTED_TIF_EXPORT_FORMATS
    from AntSleap.core.tif_project import TIF_PROJECT_SCHEMA_VERSION, TIF_PROJECT_TYPE, TifProjectManager
    from AntSleap.core.stl_project import STL_PROJECT_SCHEMA_VERSION, STL_PROJECT_TYPE, StlRenderedProjectManager
    from AntSleap.core.stl_review_bridge import import_stl_rendered_views_into_2d_project, register_stl_rendered_views_for_2d_review
    from AntSleap.core.tif_stack_import import import_tif_stack
    from AntSleap.core.amira_import import import_amira_directory
    from AntSleap.core.part_tree import build_part_tree_groups
    from AntSleap.core.platform_open import open_path
    from AntSleap.core.runtime_device import normalize_device_preference, resolve_torch_device
except ImportError:
    from core.project import ProjectManager
    from core.database import MultiModalDB
    from core.engine import AntEngine
    from core.sam_helper import SAMWorker
    from core.config import ConfigManager
    from core.window_geometry import compute_centered_window_geometry
    from ui.canvas import AnnotationCanvas
    from ui.style import (
        SCI_THEME,
        LIGHT_THEME,
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_RUN,
        BUTTON_ROLE_STOP,
        SURFACE_ROLE_CANVAS,
        SURFACE_ROLE_PANEL,
        SURFACE_ROLE_RAISED,
        SURFACE_ROLE_SUBTLE,
        SURFACE_ROLE_TOOLBAR,
        apply_theme_dialog_button_box_style,
        apply_theme_button_style,
        apply_semantic_button_style,
        apply_surface_role,
        get_theme_config,
        get_theme_stylesheet,
        normalize_theme,
        register_windows_scholarly_ui_fonts,
        themed_yes_no_question,
    )
    from ui.cropper import ImageCropper
    from ui.pdf_processing_widget import PdfProcessingWidget
    from ui.blink_lab import BlinkLabWidget
    from ui.tif_workbench import TifWorkbenchWidget
    from ui.taxamask_agent_panel import TaxaMaskAgentPanel
    from core.dataset import TwoStageDataset
    from core.training_preflight import build_training_preflight, describe_training_preflight, describe_part_coverage, format_size_pair
    from core.cascade_routes import format_expert_label, get_route_persisted_expert_candidates, merge_expert_candidates
    from core.expert_notes import format_expert_display_name, load_expert_notes
    from core.project_templates import DEFAULT_PROJECT_TEMPLATE_ID, iter_project_templates
    from core.external_backend import BUILTIN_BACKEND_ID, EXTERNAL_BACKEND_ID, ExternalBackendRunner, sanitize_external_backend_config
    from core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG, sanitize_tif_backend_config
    from core.tif_export import SUPPORTED_TIF_EXPORT_FORMATS
    from core.tif_project import TIF_PROJECT_SCHEMA_VERSION, TIF_PROJECT_TYPE, TifProjectManager
    from core.stl_project import STL_PROJECT_SCHEMA_VERSION, STL_PROJECT_TYPE, StlRenderedProjectManager
    from core.stl_review_bridge import import_stl_rendered_views_into_2d_project, register_stl_rendered_views_for_2d_review
    from core.tif_stack_import import import_tif_stack
    from core.amira_import import import_amira_directory
    from core.part_tree import build_part_tree_groups
    from core.platform_open import open_path
    from core.runtime_device import normalize_device_preference, resolve_torch_device

from torch.utils.data import DataLoader

class InferenceThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    result_signal = Signal(str, dict)
    finished_signal = Signal()
    
    def __init__(self, engine, img_paths, taxonomy, locator_scope, inf_params, project_route_manifest=None, lang="en"):
        super().__init__()
        self.engine = engine
        self.img_paths = img_paths
        self.taxonomy = taxonomy
        self.locator_scope = locator_scope
        self.inf_params = inf_params
        self.project_route_manifest = dict(project_route_manifest or {})
        self.lang = lang
        
    def run(self):
        self.log_signal.emit(tr("Starting batch inference on {0} images...", self.lang).format(len(self.img_paths)))
        count = 0
        for img_path in self.img_paths:
            preds = self.engine.predict_full_pipeline(
                img_path, 
                current_taxonomy=self.taxonomy,
                locator_scope=self.locator_scope,
                conf_thresh=self.inf_params['conf'],
                adapt_thresh=self.inf_params['adapt'],
                box_pad=self.inf_params['pad'],
                noise_floor=self.inf_params['noise_floor'],
                poly_epsilon=self.inf_params['poly_epsilon'],
                project_route_manifest=self.project_route_manifest,
            )
            if preds:
                self.result_signal.emit(img_path, preds)
                self.log_signal.emit(tr("Processed {0}", self.lang).format(os.path.basename(img_path)))
            
            count += 1
            self.progress_signal.emit(int(count / len(self.img_paths) * 100))
            
        self.finished_signal.emit()

# --- Localization ---
TRANSLATIONS = {
    "zh": {
        "PROJECT IMAGES": "项目图片",
        "+ Add Images": "+ 添加图片",
        "Import & Crop": "导入并裁剪",
        "Manual Draw": "手动绘制",
        "Magic Wand (SAM)": "魔棒 (SAM)",
        "Box Prompt (SAM)": "框选 (SAM)",
        "Tool: Magic Wand (SAM) - Click to auto-segment.": "工具: 魔棒 - 点击自动分割",
        "Tool: Box Prompt (SAM) - Drag to segment area.": "工具: 框选 - 拖拽选择区域",
        "Tool: Manual Draw - Click points to outline.": "工具: 手动 - 点击绘制轮廓",
        "Taxon": "分类单元",
        "Structures": "结构标签",
        "DESCRIPTION (Linked)": "描述 (关联)",
        "AI WORKFLOW": "AI 工作流",
        "Auto (Current)": "自动标注 (当前)",
        "Batch (All)": "批量标注 (全部)",
        "Train Models": "训练模型",
        "LOGS": "日志",
        "Export Dataset": "导出数据集",
        "Export Multimodal Dataset": "导出多模态数据",
        "Model Settings": "模型设置",
        "2D/STL Model Settings": "2D/STL 模型设置",
        "TIF Volume Model Settings": "TIF 体数据模型设置",
        "General Settings": "通用设置",
        "General Application Settings": "软件通用设置",
        "Application Preferences": "软件使用偏好",
        "General settings control the whole application: language, theme, startup behavior, autosave, and the default compute device. Workflow-specific training parameters stay in their own model settings.": "通用设置只控制整个软件的使用习惯：语言、主题、启动方式、自动保存和默认计算设备。具体工作流的训练参数放在各自的模型设置里。",
        "Language:": "语言：",
        "Theme:": "主题：",
        "Startup Behavior:": "启动方式：",
        "Show Start Center": "显示启动中心",
        "Continue last project automatically": "自动继续上次项目",
        "Project Autosave Interval (seconds):": "项目自动保存间隔（秒）：",
        "Default Runtime Device:": "默认计算设备：",
        "Runtime device here is the default for built-in 2D/STL models and other internal Torch tasks. TIF external backends use the Python executable and commands configured in TIF settings.": "这里的计算设备是内置 2D/STL 模型和其他内部 Torch 任务的默认值。TIF 外部后端使用 TIF 设置中的 Python 解释器和命令。",
        "Only the audited dark theme is currently enabled.": "当前只启用已经检查过的深色主题。",
        "Autosave interval must be a positive number.": "自动保存间隔必须是正数。",
        "General settings updated.": "通用设置已更新。",
        "2D/STL Morphology Model Settings": "2D/STL 形态学模型设置",
        "2D/STL morphology settings control rendered STL views and ordinary morphology images. TIF volume training is configured separately.": "2D/STL 形态学设置控制 STL 渲染视角图和普通形态图片。TIF 体数据训练在单独的 TIF 设置中配置。",
        "TIF Volume Training Settings": "TIF 体数据训练设置",
        "TIF Backend Defaults": "TIF 后端默认配置",
        "Controls the default external backend used by TIF Volume Workbench. The workbench can still edit the same defaults while you are inside a project.": "这里控制 TIF 体数据工作台默认使用的外部后端。在进入具体项目后，工作台内也可以编辑同一套默认配置。",
        "TIF training uses manual_truth label volumes only. Prediction results are imported as model_draft, so they must be reviewed before becoming manual truth.": "TIF 训练只使用 manual_truth 人工真值标注体。模型预测结果导入为 model_draft 草稿层，必须人工复核后才可成为人工真值。",
        "Training Data Safety": "训练数据安全规则",
        "Training source: manual_truth only.": "训练来源：仅 manual_truth 人工真值。",
        "Prediction import: model_draft layer.": "预测导入：进入 model_draft 草稿层。",
        "Manual truth is never overwritten automatically.": "人工真值不会被自动覆盖。",
        "Export Formats:": "导出格式：",
        "Supported export formats: {0}": "支持的导出格式：{0}",
        "Validate TIF Backend": "校验 TIF 后端",
        "TIF backend configuration looks valid.": "TIF 后端配置看起来可用。",
        "TIF backend ID is required.": "TIF 后端 ID 不能为空。",
        "TIF backend export formats are required.": "TIF 后端导出格式不能为空。",
        "Unsupported TIF export formats: {0}": "不支持的 TIF 导出格式：{0}",
        "TIF backend command '{0}' must include {contract} or {contract_json}.": "TIF 后端命令“{0}”必须包含 {contract} 或 {contract_json}。",
        "TIF backend settings updated.": "TIF 后端设置已更新。",
        "Invalid Settings": "设置无效",
        "Workflow": "工作流",
        "Start Center": "启动中心",
        "TaxaMask Workflow Selection": "TaxaMask 工作流选择",
        "TaxaMask Agent Center": "TaxaMask Agent 中心",
        "Choose the data type you want to work with today.": "选择今天要处理的数据类型。",
        "Ask Ant-Code to configure workflows, inspect errors, prepare PDF evidence, or plan training. Use the right rail when you want to enter a workbench directly.": "让 Ant-Code 帮你配置工作流、检查报错、准备 PDF 证据或规划训练。需要直接进入工作台时，使用右侧入口。",
        "Project Console": "项目控制台",
        "Current workflow": "当前工作流",
        "Current project": "当前项目",
        "2D/STL images": "2D/STL 图片",
        "TIF specimens": "TIF specimen",
        "PDF evidence": "PDF 证据",
        "Ant-Code ready": "Ant-Code 已就绪",
        "Ant-Code stopped": "Ant-Code 未启动",
        "Repository only; no research project selected": "仅仓库上下文；尚未选择研究项目",
        "Recent project: {0}": "最近项目：{0}",
        "2D project: {0}": "2D 项目：{0}",
        "STL rendered-view project: {0}": "STL 渲染视角图项目：{0}",
        "TIF project: {0}": "TIF 项目：{0}",
        "{0} image(s), {1} labeled, {2} STL rendered 2D view(s)": "{0} 张图片，{1} 张已有人工标注，{2} 张 STL 渲染 2D 视角图",
        "{0} specimen(s), {1} train-ready, {2} with manual_truth": "{0} 个 specimen，{1} 个可训练，{2} 个已有 manual_truth",
        "PDF evidence skill ready; {0} review candidate(s)": "PDF evidence skill 已配置；{0} 个候选图待复核",
        "PDF evidence skill missing": "PDF evidence skill 未找到",
        "STL source stays as exported high-resolution 2D views; TaxaMask does not label 3D meshes.": "STL 来源保持为外部导出的高分辨率 2D 视角图；TaxaMask 不做 3D mesh 标注。",
        "2D / STL morphology annotation": "2D / STL 形态学标注",
        "Annotate high-resolution 2D views rendered from STL, or ordinary 2D morphology images, then train Locator/SAM/Blink models.": "标注从 STL 导出的高分辨率 2D 视角图，或普通 2D 形态图像，并训练 Locator/SAM/Blink 模型。",
        "TIF volume annotation": "TIF 体数据标注",
        "Annotate continuous slice volumes with material IDs, export train-ready volumes, and call TIF segmentation backends.": "用 material ID 标注连续切片体数据，导出可训练体数据，并调用 TIF 分割后端。",
        "Continue last project": "继续上次项目",
        "No recent project": "暂无最近项目",
        "Enter 2D/STL workflow": "进入 2D/STL 工作流",
        "Enter TIF workflow": "进入 TIF 工作流",
        "Open any project": "打开任意项目",
        "Create 2D/STL project": "新建 2D/STL 项目",
        "Create TIF project": "新建 TIF 项目",
        "Open 2D/STL Project": "打开 2D/STL 项目",
        "Open TIF Project": "打开 TIF 项目",
        "2D/STL Morphology Workflow": "2D/STL 形态学工作流",
        "TIF Volume Workflow": "TIF 体数据工作流",
        "Opened 2D/STL workflow.": "已进入 2D/STL 工作流。",
        "Opened TIF volume workflow.": "已进入 TIF 体数据工作流。",
        "Ask Agent": "询问 Agent",
        "Local task cards": "本地任务卡",
        "No active project": "未打开项目",
        "Model Backend:": "模型后端：",
        "Built-in Locator + SAM": "内置 Locator + SAM",
        "External Script Backend": "外部脚本后端",
        "Runtime Device:": "运行设备：",
        "Auto (CUDA if available)": "自动（有 CUDA 则使用）",
        "CPU only": "仅 CPU",
        "CUDA GPU": "CUDA 显卡",
        "Controls built-in Locator/SAM/Blink training and inference. External backends use their own command environment. CPU can run small tests, but CUDA is recommended for real training.": "控制内置 Locator/SAM/Blink 的训练和推理。外部后端使用自己的命令环境。CPU 可用于小规模测试，正式训练建议使用 CUDA。",
        "Runtime device resolved to: {0}": "运行设备已解析为：{0}",
    "External Backend": "外部后端",
    "Backend ID:": "后端 ID：",
    "Display Name:": "显示名称：",
    "Python Executable:": "Python 解释器：",
    "Prepare Dataset Command:": "数据准备命令：",
    "Train Command:": "训练命令：",
    "Predict Command:": "推理命令：",
    "Model Manifest Path:": "模型 manifest 路径：",
    "Validate External Backend": "校验外部后端",
    "External backend note:": "外部后端说明：",
    "Use this advanced entry when you want TaxaMask to call your own training or prediction scripts. Commands run in an isolated external_runs directory and receive a contract JSON path through {contract} or {contract_json}. When this backend is selected, built-in Locator/SAM training and prediction do not run for that task.": "当你希望 TaxaMask 调用自己的训练或推理脚本时使用这个高级入口。命令会在独立的 external_runs 目录中运行，并通过 {contract} 或 {contract_json} 接收契约 JSON 路径。选择该后端后，本次任务不会运行内置 Locator/SAM 训练或推理。",
    "External backend configuration looks valid.": "外部后端配置看起来可用。",
    "External backend needs at least a train command or a predict command.": "外部后端至少需要填写训练命令或推理命令。",
    "External backend command '{0}' must include {contract} or {contract_json}.": "外部后端命令“{0}”必须包含 {contract} 或 {contract_json}。",
    "External backend ID is required.": "外部后端 ID 不能为空。",
        "Training": "训练",
        "Inference": "推理",
        "Language": "语言",
        "Theme": "主题",
        "Dark Mode": "深色模式",
        "File": "文件",
        "Settings": "设置",
        "Epochs:": "训练轮数 (Epochs):",
        "Batch Size:": "批次大小 (Batch Size):",
        "Blink Expert Training Defaults:": "Blink 专家训练默认值：",
        "Default Blink Epochs:": "默认 Blink 训练轮数：",
        "Default Blink Batch Size:": "默认 Blink 批次大小：",
        "Default Blink Learning Rate:": "默认 Blink 学习率：",
        "Default Blink Weight Decay:": "默认 Blink 权重衰减：",
        "Default Blink Input Size:": "默认 Blink 输入尺寸：",
        "These defaults are shown in Blink Workbench when the app starts or settings are saved. You can still adjust them for a single expert before training.": "这些默认值会在应用启动或保存设置后显示到 Blink 工作台。训练单个专家前仍可在 Blink 工作台临时调整。",
        "Learning Rate:": "学习率 (LR):",
        "Weight Decay (L2 Reg):": "权重衰减 (L2正则):",
        "Main Locator Parts:": "主定位结构：",
        "Choose which structures the built-in Locator should learn as large, stable targets. Small structures can stay in Structures and be refined with SAM, Blink, or an external backend.": "选择哪些结构交给内置 Locator 作为大而稳定的目标来学习。小结构仍可保留在结构标签中，再通过 SAM、Blink 或外部后端精修。",
        "At least one main locator part must be selected.": "至少需要选择一个主定位结构。",
        "Train from Scratch (Reset Weights)": "从头训练 (重置权重)",
        "Validation Report %:": "测试集展示比例 (%):",
        "Confidence Threshold:": "置信度阈值:",
        "Adaptive Thresh Ratio:": "自适应阈值比例:",
        "Box Padding Ratio:": "框扩展比例:",
        "Noise Floor:": "底噪阈值:",
        "Polygon Simplification (px):": "多边形简化度 (px):",
        "Cancel": "取消",
        "Close": "关闭",
        "Save": "保存",
        "Export": "导出",
        "Browse": "浏览",
        "Select Directory": "选择目录",
        "Export Format:": "导出格式:",
        "Export Path:": "导出路径:",
        "No Labels": "无标签",
        "Annotate images first!": "请先标注图片！",
        "Starting training on active compute device...": "开始在当前计算设备上训练...",
        "Training Locator...": "正在训练定位器...",
        "Training Segmentation...": "正在训练分割器...",
        "Training Finished! Weights saved.": "训练完成！权重已保存。",
        "Batch Inference": "批量推理",
        "Clear AI Labels": "清除 AI 标签",
        "Run auto-annotation on {0} images?\nThis may take a while.": "对 {0} 张图片进行自动标注？\n这可能需要一段时间。",
        "Batch Complete": "批量完成",
        "Batch inference finished.": "批量推理已结束。",
        "System Initialized. Starting SAM loader in 1s...": "系统初始化。1秒后加载 SAM...",
        "Initializing SAM (Segment Anything) on active compute device...": "正在当前计算设备上初始化 SAM...",
        "SAM Model Loaded and Ready!": "SAM 模型加载完毕！",
        "Warning: SAM weights not found at {model_path}": "警告：未在 {model_path} 找到 SAM 权重",
        "Enable Morphometrics": "启用形态测量",
        "Scale Tool": "标尺工具",
        "Tool: Scale - Drag to define 1mm.": "工具: 标尺 - 拖动定义1mm长度。",
        "Enter length in mm:": "输入长度 (mm):",
        "Measurements": "测量数据",
        "Area:": "面积:",
        "Perimeter:": "周长:",
        "Scale set to {:.2f} px/mm": "标尺已设定: {:.2f} px/mm",
        "Open Project": "打开项目",
        "New Project": "新建项目",
        "New TIF Volume Project": "新建 TIF 体数据项目",
        "New TIF Project Directory": "新建 TIF 项目目录",
        "Open STL Rendered-View Project": "打开 STL 渲染视图项目",
        "Project Template:": "项目模板：",
        "Generic taxonomy mask project": "通用分类掩码项目",
        "Ant morphology (validated example)": "蚂蚁形态学（已验证示例）",
        "Save Project": "保存项目",
        "Import TIF Stack": "导入 TIF stack",
        "Import AMIRA Directory": "导入 AMIRA 目录",
        "Import STL Rendered Views to Labeling Workbench": "导入 STL 渲染视角图到标注工作台",
        "Specimen ID:": "Specimen 编号：",
        "Please create or open a TIF volume project first.": "请先新建或打开一个 TIF 体数据项目。",
        "Created TIF volume project: {0}": "已创建 TIF 体数据项目：{0}",
        "Imported TIF stack for specimen {0}. Report: {1}": "已为 specimen {0} 导入 TIF stack。报告：{1}",
        "Imported AMIRA directory for specimen {0}. Report: {1}": "已为 specimen {0} 导入 AMIRA 目录。报告：{1}",
        "Imported STL rendered views into the Labeling Workbench from {0}. Registered views: {1}, specimens: {2}, unparsed files: {3}.": "已从 {0} 将 STL 渲染视角图导入标注工作台。登记视角图：{1}，Specimen 数：{2}，未解析文件：{3}。",
        "Registered STL rendered-view project into the Labeling Workbench. Views: {0}, missing files: {1}.": "已将 STL 渲染视图项目登记进标注工作台。视角图：{0}，缺失文件：{1}。",
        "Check / Relocate Project Images": "检查/重定位项目图片",
        "Project Image Health": "项目图片健康检查",
        "Project has {0}/{1} image paths available. Missing: {2}.": "项目共有 {1} 条图片路径，当前可访问 {0} 条，缺失 {2} 条。",
        "All project image paths are available.": "当前项目图片路径全部可访问。",
        "Select New Image Root": "选择新的图片根目录",
        "Relocation Preview": "重定位预览",
        "Matched {0} missing image path(s). Still unresolved: {1}.\n\nPreview:\n{2}\n\nApply this remap and save the project?": "已匹配 {0} 条缺失图片路径，仍未解决 {1} 条。\n\n预览：\n{2}\n\n是否应用这次重定位并保存项目？",
        "No missing image paths could be matched under the selected folder.": "在所选文件夹下没有匹配到缺失图片路径。",
        "Remapped {0} project image path(s).": "已重定位 {0} 条项目图片路径。",
        "Head": "头部 (Head)",
        "Mesosoma": "胸部 (Mesosoma)",
        "Thorax": "胸部 (Thorax)", 
        "Gaster": "腹部 (Gaster)",
        "Mandible": "上颚 (Mandible)",
        "Eye": "复眼 (Eye)",
        "Unknown": "未知 (Unknown)",
        "Labeling Workbench": "标注工作台",
        "PDF Processing": "文献处理",
        "PDF Evidence Tools": "PDF 文献证据工具",
        "Open PDF Evidence Tools": "打开 PDF 文献证据工具",
        "TIF Volume Workbench": "TIF 体数据工作台",
        "Opened TIF volume project: {0}": "已打开 TIF 体数据项目：{0}",
        "Opened STL rendered-view project and registered it into the Labeling Workbench: {0}": "已打开 STL 渲染视图项目，并登记进标注工作台：{0}",
        "Add Structure": "添加结构标签",
        "Remove Structure": "删除结构标签",
        "Crop this Image": "裁剪此图片",
        "Remove Image": "移除图片",
        "Error": "错误",
        "Success": "成功",
        "Open in Blink Workbench": "在 Blink 工作台中打开",
        "Blink Workbench": "Blink 工作台",
        "Training Report & Validation": "训练报告与验证",
        "Summary": "摘要",
        "No Metrics Generated": "未生成指标图",
        "Training Metrics": "训练指标",
        "Show Validation Set %:": "显示验证集比例：",
        "Load Samples": "加载样本",
        "All validation": "全部验证",
        "Macro locator": "宏定位器",
        "No Validation Summary": "无验证摘要",
        "--- Initial Summary (Top 6) ---": "--- 初始摘要（前 6 张）---",
        "--- Detailed Inspection ---": "--- 详细检查 ---",
        "Validation Inspection": "验证检查",
        "Open Report Folder": "打开报告文件夹",
        "No validation details found at {0}": "未在 {0} 找到验证详情",
        "No images found.": "未找到图片。",
        "{0}% ({1} images)": "{0}%（{1} 张图片）",
        "Cascade Routes": "级联路由",
        "Appoint Expert": "指定专家",
        "Enable Route": "启用路由",
        "Disable Route": "停用路由",
        "Awaiting expert": "待指定专家",
        "Expert file missing": "专家文件缺失",
        "Delete route {0} -> {1}?": "删除路由 {0} -> {1}？",
        "No trained experts were found under weights/experts.": "未在 weights/experts 下找到已训练专家。",
        "Refresh": "刷新",
        "Info": "提示",
        "Select export directory...": "选择导出目录...",
        "Multimodal (Crops + JSONL)": "多模态（裁剪图 + JSONL）",
        "COCO (Standard)": "COCO（标准）",
        "YOLO (Segmentation)": "YOLO（分割）",
        "Enter Blink Workbench": "进入 Blink 工作台",
        "Image: {0}": "图片：{0}",
        "Target Part:": "目标部位：",
        "Entry ROI:": "进入 ROI：",
        "Manual Box": "手工框",
        "Auto Box": "自动框",
        "Target Part is the child part you want to refine. Entry ROI is the parent/context region Blink will zoom into. This project remembers the parent/context ROI you chose for each target part, and later Blink entries reuse that remembered context.": "目标部位是你要精修的子部位；进入 ROI 是 Blink 将放大的父级/上下文区域。这个项目会记住你为每个目标部位选择过的父级/上下文 ROI，之后再次进入 Blink 时会复用这份项目内记忆。",
        "B:": "亮：",
        "C:": "对：",
        "Locator:": "定位器：",
        "Segmenter:": "分割器：",
        "Del": "删除",
        "Delete": "删除",
        "No Locators Found": "未找到定位器",
        "Base SAM (Original)": "基础 SAM（原始）",
        "Delete the selected locator model file from disk.": "从磁盘删除当前选中的定位器模型文件。",
        "Delete the selected segmenter model file from disk.": "从磁盘删除当前选中的分割器模型文件。",
        "Delete Model": "删除模型",
        "Delete locator model {0}?": "删除定位器模型 {0}？",
        "Locator reset to base (untrained).": "定位器已重置为基础（未训练）状态。",
        "Segmenter switched to: Base SAM (Original)": "分割器已切换为：基础 SAM（原始）",
        "Segmenter switched to: Fine-tuned {0}": "分割器已切换为：微调版 {0}",
        "Delete segmenter LoRA {0}?": "删除分割器 LoRA {0}？",
        "New Project Directory": "新建项目目录",
        "Project Name:": "项目名称：",
        "Structure Name:": "结构标签名称：",
        "Exists.": "已存在。",
        "Delete '{0}'?": "删除“{0}”？",
        "Clear AI": "清除 AI",
        "Are you sure?": "确定吗？",
        "Clear all AI labels from the current project?": "清除当前项目中的全部 AI 标签？",
        "Select Images": "选择图片",
        "Remove": "移除",
        "Remove {0} images?": "移除 {0} 张图片？",
        "Blink Workbench Entry": "Blink 工作台入口",
        "Please select an image first.": "请先选择一张图片。",
        "Please select a target part first.": "请先选择目标部位。",
        "No entry ROI is available yet. Draw a manual box or generate an auto box in the workbench first.": "当前还没有可用的进入 ROI，请先在工作台中绘制手工框或生成自动框。",
        "Failed to build a Blink session from the selected options.": "无法根据当前选择建立 Blink 会话。",
        "Opened Blink session for {0} via {1} ({2}).": "已通过 {1}（{2}）为 {0} 打开 Blink 会话。",
        "mm:": "毫米：",
        "No Scale.": "未设置比例尺。",
        "Area: {0:.4f} mm2\nPeri: {1:.4f} mm": "面积：{0:.4f} mm²\n周长：{1:.4f} mm",
        "No Polygon.": "无多边形。",
        "Annotate first!": "请先完成标注！",
        "Training Split Error": "训练划分错误",
        "Training aborted: {0}": "训练已中止：{0}",
        "Settings updated.": "设置已更新。",
        "Language: {0}": "语言：{0}",
        "Running inference on: {0}...": "正在对 {0} 进行推理...",
        "Inference complete. Detected {0} parts, saved {1} new labels.": "推理完成。检测到 {0} 个部位，保存了 {1} 个新标签。",
        "Batch": "批量",
        "Annotate {0} images?": "对 {0} 张图片进行标注？",
        "Starting Batch Inference with Taxonomy ({0}): {1}": "开始批量推理，分类体系（{0}）：{1}",
        "Batch saved {0}/{1} for {2}": "已为 {2} 保存 {0}/{1}",
        "Exported {0} samples.": "已导出 {0} 个样本。",
        "Global labels updated from Blink Workbench.": "全局标签已从 Blink 工作台同步更新。",
        "Restored session: {0}": "已恢复会话：{0}",
        "System Initialized.": "系统已初始化。",
        "Syncing Engine Taxonomy ({0} -> {1})...": "正在同步引擎分类体系（{0} -> {1}）...",
        "Taxonomy changed. Please retrain or select a matching model.": "分类体系已变化，请重新训练或选择匹配的模型。",
        "Training with Taxonomy ({0}): {1}": "使用分类体系进行训练（{0}）：{1}",
        "Training with Locator Scope ({0}): {1}": "使用定位器范围进行训练（{0}）：{1}",
        "Starting Batch Inference with Locator Scope ({0}): {1}": "开始批量推理，定位器范围（{0}）：{1}",
        "Syncing Locator Scope ({0} -> {1})...": "正在同步定位器范围（{0} -> {1}）...",
        "Locator scope changed. Please retrain or select a matching model.": "定位器范围已变化，请重新训练或选择匹配的模型。",
        "Starting batch inference on {0} images...": "开始对 {0} 张图片进行批量推理...",
        "Processed {0}": "已处理 {0}",
        "Training SAM... (BS=1)": "正在训练 SAM...（批次=1）",
        "Generating Report...": "正在生成报告...",
        "Loc Ep {0}: Train {1:.4f} | Val {2:.4f} | Err {3:.1f}px": "定位器轮次 {0}：训练 {1:.4f} | 验证 {2:.4f} | 误差 {3:.1f}px",
        "SAM Ep {0}: Train {1:.4f} | Val {2:.4f} | IoU {3:.2%}": "SAM 轮次 {0}：训练 {1:.4f} | 验证 {2:.4f} | IoU {3:.2%}",
        "Training Finished! All validation results saved to {0}/val_details": "训练完成！所有验证结果已保存到 {0}/val_details",
        "Locator training size set to {0}": "定位器训练尺寸设为 {0}",
        "Locator stage skipped: no eligible locator samples.": "定位器阶段已跳过：没有可用的定位器样本。",
        "SAM stage skipped: no eligible SAM/parts samples.": "SAM 阶段已跳过：没有可用的 SAM/部位样本。",
        "SAM stage skipped: locator-only training is enabled.": "SAM 阶段已跳过：已启用仅训练定位器。",
        "Training cancelled.": "训练已取消。",
        "Training already running...": "训练已在进行中...",
        "Stop Training": "停止训练",
        "Stopping training after the current epoch/batch...": "将在当前轮次/批次结束后停止训练...",
        "Train Locator only (skip SAM)": "仅训练定位器（跳过 SAM）",
        "Skip SAM/parts training for this run. Useful when the base SAM result is already good enough.": "本次训练跳过 SAM/部位分割训练。适合基础 SAM 效果已经足够好的情况。",
        "Training Preflight": "训练预检",
        "Training Readiness Warning": "训练准备警告",
        "Training Confirmation Required": "需要训练确认",
        "Training Retry": "训练重试",
        "Train anyway": "仍然训练",
        "Retry with lower resolution": "用更低分辨率重试",
        "Legacy Locator Confirmation": "旧版定位器确认",
        "The selected locator checkpoint does not store its training resolution. It will be treated as a legacy 512px locator only if you confirm.": "当前选中的定位器检查点没有保存训练分辨率。只有在你确认后，程序才会把它当作旧版 512px 定位器使用。",
        "Training will use only saved annotations and image files. View/manifest gating is no longer used in the main Train Models path.": "主训练路径现在只依据已保存标注和图像文件，不再依赖视图/manifest 门控。",
        "Mixed native image resolutions detected among locator-eligible images. Training will unify them to the smallest native resolution tier among eligible images: {0}. Continue?": "检测到可用于 locator 训练的图片存在混合原生分辨率。训练会统一到这些合格图片中最小的原生分辨率层级：{0}。是否继续？",
        "Locator stage ran out of memory at {0}. You can retry with a lower locator size: {1}": "定位器阶段在 {0} 时发生显存不足。你可以改用更低的定位器尺寸重试：{1}",
        "No lower locator resolutions are available for retry.": "已经没有更低的 locator 分辨率可供重试。",
        "Training preflight summary:\n{0}": "训练预检摘要：\n{0}",
        "Proceed with training?": "是否继续训练？",
        "Locator switched to: {0}": "定位器已切换为：{0}"
    }
}

def tr(text, lang="en"):
    if lang == "zh":
        return TRANSLATIONS["zh"].get(text, text)
    return text


SECTION_TRANSLATIONS = {
    "zh": {
        "Overview": "概览",
        "Coverage": "覆盖情况",
        "Warnings": "警告",
        "Ready": "就绪",
        "Skipped": "跳过",
        "Locator stage: {0} | SAM stage: {1}": "Locator 阶段：{0} | SAM 阶段：{1}",
        "Locator size: {0}": "Locator 尺寸：{0}",
        "Mixed-resolution decision: locator training will use {0}.": "混合分辨率处理：Locator 训练将统一使用 {0}。",
        "total images: {0}": "总图片数：{0}",
        "train images: {0}": "训练集图片数：{0}",
        "val images: {0}": "验证集图片数：{0}",
        "total coverage: {0}": "总覆盖：{0}",
        "train coverage: {0}": "训练覆盖：{0}",
        "val coverage: {0}": "验证覆盖：{0}",
        "Locator eligible images: {0}": "可用于 Locator 训练的图片：{0}",
        "SAM/parts eligible images: {0}": "可用于 SAM/部位训练的图片：{0}",
        "Selected locator size: {0}": "选定的 Locator 尺寸：{0}",
        "Eligible locator native sizes: {0}": "符合条件的 Locator 原始尺寸：{0}",
        "Mixed native resolutions: {0}": "存在混合原生分辨率：{0}",
        "Locator coverage": "Locator 标注覆盖情况",
        "SAM / parts coverage": "SAM / 部位标注覆盖情况",
        "Missing images": "缺失图片",
        "Unreadable images": "无法读取的图片",
        "Zero-annotation images": "零标注图片",
        "Invalid-annotation images": "无效标注图片",
        "Warnings:": "警告：",
        "No warnings. The current saved annotations satisfy the training gate.": "当前没有警告，现有已保存标注已满足训练条件。",
        "ID": "编号",
        "Image": "图片",
        "Source": "来源",
        "Valid Parts": "有效部位",
        "Max Error(px)": "最大误差（px）",
        "Validation count: {0}": "验证样本数：{0}",
        "Preview count: {0}": "预览样本数：{0}",
        "Provenance counts:": "来源统计：",
        "Metrics plot: {0}": "指标图：{0}",
        "Validation index: {0}": "验证索引：{0}",
        "No structured report summary found.": "未找到结构化报告摘要。",
        "Validation samples:": "验证样本：",
        "Project Routes": "项目路由",
        "Project Route Management": "项目路由管理",
        "Manage Blink-discovered or manually appointed project routes here. Deleting a route removes only this project record; reopening Blink later with the same parent/child context can register a candidate again.": "可在这里管理由 Blink 发现或手动指定的项目 route。删除 route 只会移除当前项目中的这条记录；如果之后在相同父/子部位上下文下再次打开 Blink，仍可重新登记为候选 route。",
        "Project routes below control which parent -> child expert links are available.": "下方项目中的 route 决定哪些 parent -> child expert 链路可以实际使用。",
        "Parent": "父部位",
        "Child": "子部位",
        "Cross-region structures": "跨区域结构",
        "Ungrouped structures": "未分组结构",
        "Main locator parts": "主定位部位",
        "Blink child parts": "Blink 子部位",
        "Structure group": "结构分组",
        "Enabled": "已启用",
        "Disabled": "已停用",
        "Expert": "专家",
        "Status": "状态",
        "Yes": "是",
        "No": "否",
        "Not appointed": "未指定",
        "Expert not appointed yet": "尚未指定专家",
        "Project": "项目",
        "Blink candidate": "Blink 候选",
        "Blink training": "Blink 训练",
        "Legacy global manifest": "Legacy 全局清单",
        "Appointed": "已指定",
        "Available": "可指定",
        "History": "历史候选",
        "Missing file history": "缺文件历史",
        "Discoverable": "可发现",
        "Select the expert to appoint for {0} -> {1}": "为 {0} -> {1} 选择要指定的专家",
        "This route has no appointed expert yet. Appoint an expert first, then enable the route.": "这条路由还没有指定专家。请先指定专家，再启用该路由。",
        "The appointed expert file for this route is missing. Reappoint an available expert before enabling the route.": "这条路由指定的专家文件缺失。请先重新指定一个可用专家，再启用该路由。",
        "Route {0} -> {1} now uses expert {2}.": "路由 {0} -> {1} 现已指定专家 {2}。",
        "Route {0} -> {1} enabled.": "路由 {0} -> {1} 已启用。",
        "Route {0} -> {1} disabled.": "路由 {0} -> {1} 已停用。",
        "Delete project route {0} -> {1}?\n\nThis removes the current project route record only. If you reopen Blink later with the same parent/child context, Blink can register this route again as a candidate.": "删除项目路由 {0} -> {1}？\n\n这只会移除当前项目里的这条路由记录。如果你之后在相同父/子部位上下文下再次打开 Blink，Blink 仍可把这条路由重新登记为候选。",
        "Deleted route {0} -> {1}.": "已删除路由 {0} -> {1}。",
        "Remove missing expert history {0} from route {1} -> {2}?\n\nThis only cleans the current project route history. It does not delete any model file.": "从路由 {1} -> {2} 中移除缺文件专家历史 {0}？\n\n这只会清理当前项目里的路由历史，不会删除任何模型文件。",
        "Removed missing expert history {0} from route {1} -> {2}.": "已从路由 {1} -> {2} 移除缺文件专家历史 {0}。",
        "Current Image": "当前图片",
        "Route usage for {0}": "路由使用情况：{0}",
        "Route usage for batch image {0}": "批量图片的路由使用情况：{0}",
        "source={0}; attempted={1}; applied={2}": "来源={0}；尝试={1}；应用={2}",
        "Route blocks: {0}": "路由阻断：{0}",
        "Unknown": "未知",
    }
}


def ui_text(text, lang="en"):
    if lang == "zh":
        return SECTION_TRANSLATIONS["zh"].get(text, text)
    return text


def _yes_no_text(value, lang="en"):
    return ui_text("Yes", lang) if value else ui_text("No", lang)


def _translate_validation_provenance(value, lang="en"):
    mapping = {
        "macro_locator": tr("Macro locator", lang),
        "all": tr("All validation", lang),
    }
    return mapping.get(str(value or ""), str(value or ""))


def _translate_route_registration_source(value, lang="en"):
    mapping = {
        "project": ui_text("Project", lang),
        "blink_candidate": ui_text("Blink candidate", lang),
        "blink_training": ui_text("Blink training", lang),
        "legacy_global_manifest": ui_text("Legacy global manifest", lang),
    }
    text = str(value or "project")
    return mapping.get(text, text)


def _translate_training_warning_text(text, lang="en"):
    warning_text = str(text or "")
    if lang != "zh":
        return warning_text

    patterns = [
        (
            r"^Excluded (\d+) image\(s\) missing on disk from training\.$",
            "训练中排除了 {0} 张磁盘缺失图片。",
        ),
        (
            r"^Excluded (\d+) unreadable image\(s\) from training\.$",
            "训练中排除了 {0} 张无法读取的图片。",
        ),
        (
            r"^Excluded (\d+) image\(s\) whose saved annotations were invalid\.$",
            "训练中排除了 {0} 张已保存标注无效的图片。",
        ),
        (
            r"^Excluded (\d+) zero-annotation image\(s\) from training\.$",
            "训练中排除了 {0} 张零标注图片。",
        ),
        (
            r"^No locator-eligible images were found\. The locator stage will be skipped\.$",
            "没有找到可用于 Locator 训练的图片，Locator 阶段将被跳过。",
        ),
        (
            r"^Only 1 locator-eligible image was found; training and validation will reuse the same image\.$",
            "只找到 1 张可用于 Locator 训练的图片，训练与验证将复用同一张图片。",
        ),
        (
            r"^No SAM/parts-eligible images were found\. The SAM stage will be skipped\.$",
            "没有找到可用于 SAM/部位训练的图片，SAM 阶段将被跳过。",
        ),
        (
            r"^Only 1 SAM/parts-eligible image was found; training and validation will reuse the same image\.$",
            "只找到 1 张可用于 SAM/部位训练的图片，训练与验证将复用同一张图片。",
        ),
        (
            r"^Locator coverage is 0 for '(.+)', so that locator part will not be trained\.$",
            "'{0}' 的 Locator 标注覆盖为 0，因此该部位不会进入 Locator 训练。",
        ),
        (
            r"^SAM/parts coverage is 0 for '(.+)', so that part will not enter SAM training\.$",
            "'{0}' 的 SAM/部位标注覆盖为 0，因此该部位不会进入 SAM 训练。",
        ),
    ]

    for pattern, template in patterns:
        match = re.match(pattern, warning_text)
        if match:
            return template.format(*match.groups())
    return warning_text


WORKBENCH_WINDOW_TITLE = "TaxaMask Workbench"
DEFAULT_PROJECT_NAME = "TaxaMask_Project"


class NoWheelComboBox(QComboBox):
    """Combo box that ignores mouse-wheel changes to avoid accidental selection changes."""

    def wheelEvent(self, event):
        event.ignore()


def _blink_preferred_roi_parts(target_part, remembered_parent_part=None):
    target = str(target_part or "").strip()
    remembered_parent = str(remembered_parent_part or "").strip()
    preferred_parts = []
    if remembered_parent and remembered_parent != target:
        preferred_parts.append(remembered_parent)
    return preferred_parts

class TrainingThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    report_signal = Signal(dict)
    success_signal = Signal()
    error_signal = Signal(dict)
    finished_signal = Signal()
    
    def __init__(
        self,
        engine,
        preflight,
        taxonomy,
        locator_scope,
        epochs=5,
        batch_size=4,
        lang="en",
        train_segmenter=True,
    ):
        super().__init__()
        self.engine = engine
        self.preflight = dict(preflight or {})
        self.taxonomy = taxonomy
        self.locator_scope = locator_scope
        self.epochs = epochs
        self.batch_size = batch_size
        self.lang = lang
        self.train_segmenter = bool(train_segmenter)
        self.locator_train_data = list(self.preflight.get("locator_train_data", []))
        self.locator_val_data = list(self.preflight.get("locator_val_data", []))
        self.parts_train_data = list(self.preflight.get("parts_train_data", []))
        self.parts_val_data = list(self.preflight.get("parts_val_data", []))
        self.locator_resolution = tuple(self.preflight.get("selected_locator_size") or (512, 512))
        self.has_locator_stage = bool(self.locator_train_data and self.locator_val_data)
        self.has_parts_stage = bool(self.train_segmenter and self.parts_train_data and self.parts_val_data)
         
    def run(self):
        try:
            self.log_signal.emit("Starting training on active compute device...")

            self.engine.locator_resolution = tuple(self.locator_resolution)
            self.log_signal.emit(
                tr("Locator training size set to {0}", self.lang).format(format_size_pair(self.engine.locator_resolution))
            )

            self.engine.history["locator_train"] = []
            self.engine.history["locator_val"] = []
            self.engine.history["pixel_error"] = []
            self.engine.history["parts_train"] = []
            self.engine.history["parts_val"] = []
            self.engine.history["iou"] = []

            dl_loc_val = None

            if self.has_locator_stage:
                locator = self.engine.ensure_locator_loaded()
                opt_loc = self.engine.opt_loc
                ds_loc_train = TwoStageDataset(
                    self.locator_train_data,
                    self.locator_scope,
                    mode='locator',
                    input_size=tuple(self.engine.locator_resolution),
                )
                ds_loc_val = TwoStageDataset(
                    self.locator_val_data,
                    self.locator_scope,
                    mode='locator',
                    input_size=tuple(self.engine.locator_resolution),
                )
                dl_loc_train = DataLoader(ds_loc_train, batch_size=max(1, self.batch_size*2), shuffle=True)
                dl_loc_val = DataLoader(ds_loc_val, batch_size=max(1, self.batch_size*2), shuffle=False)

                self.log_signal.emit("Training Locator...")
                try:
                    for epoch in range(self.epochs): 
                        if self.isInterruptionRequested():
                            self.log_signal.emit(tr("Training cancelled.", self.lang))
                            return
                        loss_t = self.engine.train_epoch(
                            dl_loc_train,
                            locator,
                            opt_loc,
                            None,
                            stop_callback=self.isInterruptionRequested,
                        )
                        if loss_t is None:
                            self.log_signal.emit(tr("Training cancelled.", self.lang))
                            return
                        if self.isInterruptionRequested():
                            self.log_signal.emit(tr("Training cancelled.", self.lang))
                            return
                        metrics_v = self.engine.validate_epoch(
                            dl_loc_val,
                            locator,
                            stop_callback=self.isInterruptionRequested,
                        )
                        if metrics_v is None:
                            self.log_signal.emit(tr("Training cancelled.", self.lang))
                            return
                        self.engine.history["locator_train"].append(loss_t)
                        self.engine.history["locator_val"].append(metrics_v['loss'])
                        self.engine.history["pixel_error"].append(metrics_v['pixel_error'])
                        self.log_signal.emit(
                            tr("Loc Ep {0}: Train {1:.4f} | Val {2:.4f} | Err {3:.1f}px", self.lang).format(
                                epoch, loss_t, metrics_v['loss'], metrics_v['pixel_error']
                            )
                        )
                        self.progress_signal.emit(int((epoch+1)/(self.epochs*2) * 100))
                except RuntimeError as exc:
                    if "out of memory" in str(exc).lower():
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                        self.error_signal.emit(
                            {
                                "type": "oom",
                                "stage": "locator",
                                "current_resolution": tuple(self.engine.locator_resolution),
                                "lower_options": list(self.preflight.get("lower_locator_size_options", [])),
                                "message": str(exc),
                            }
                        )
                        return
                    raise
            else:
                self.log_signal.emit(tr("Locator stage skipped: no eligible locator samples.", self.lang))
                self.progress_signal.emit(50)

            if self.has_parts_stage:
                ds_parts_train = TwoStageDataset(self.parts_train_data, self.taxonomy, mode='parts')
                ds_parts_val = TwoStageDataset(self.parts_val_data, self.taxonomy, mode='parts')
                dl_parts_train = DataLoader(ds_parts_train, batch_size=1, shuffle=True)
                dl_parts_val = DataLoader(ds_parts_val, batch_size=1, shuffle=False)
                parts_model = self.engine.ensure_parts_model_loaded()
                opt_parts = self.engine.opt_parts

                self.log_signal.emit(tr("Training SAM... (BS=1)", self.lang))
                for epoch in range(self.epochs):
                    if self.isInterruptionRequested():
                        self.log_signal.emit(tr("Training cancelled.", self.lang))
                        return
                    loss_t = self.engine.train_epoch(
                        dl_parts_train,
                        parts_model,
                        opt_parts,
                        self.engine.crit_parts,
                        stop_callback=self.isInterruptionRequested,
                    )
                    if loss_t is None:
                        self.log_signal.emit(tr("Training cancelled.", self.lang))
                        return
                    if self.isInterruptionRequested():
                        self.log_signal.emit(tr("Training cancelled.", self.lang))
                        return
                    metrics_v = self.engine.validate_epoch(
                        dl_parts_val,
                        parts_model,
                        stop_callback=self.isInterruptionRequested,
                    )
                    if metrics_v is None:
                        self.log_signal.emit(tr("Training cancelled.", self.lang))
                        return
                    self.engine.history["parts_train"].append(loss_t)
                    self.engine.history["parts_val"].append(metrics_v['loss'])
                    self.engine.history["iou"].append(metrics_v['iou'])
                    self.log_signal.emit(
                        tr("SAM Ep {0}: Train {1:.4f} | Val {2:.4f} | IoU {3:.2%}", self.lang).format(
                            epoch, loss_t, metrics_v['loss'], metrics_v['iou']
                        )
                    )
                    self.progress_signal.emit(50 + int((epoch+1)/(self.epochs*2) * 100))
            else:
                if self.train_segmenter:
                    self.log_signal.emit(tr("SAM stage skipped: no eligible SAM/parts samples.", self.lang))
                else:
                    self.log_signal.emit(tr("SAM stage skipped: locator-only training is enabled.", self.lang))
                self.progress_signal.emit(100)

            if self.isInterruptionRequested():
                self.log_signal.emit(tr("Training cancelled.", self.lang))
                return
                
            self.engine.save_weights(save_locator=self.has_locator_stage, save_segmenter=self.has_parts_stage)
            self.log_signal.emit(tr("Generating Report...", self.lang))
            
            # Initial report shows only a small summary (e.g., 6 images)
            # Detailed inspection is handled by the UI post-training.
            report = self.engine.generate_report(dl_loc_val, num_samples=6)
            
            self.report_signal.emit(report)
            self.log_signal.emit(
                tr("Training Finished! All validation results saved to {0}/val_details", self.lang).format(report['dir'])
            )
            self.success_signal.emit()
        except Exception as exc:
            self.error_signal.emit({"type": "error", "message": str(exc)})
        finally:
            self.finished_signal.emit()


class TrainingPreflightDialog(QDialog):
    def __init__(self, preflight, parent=None, lang="en"):
        super().__init__(parent)
        self.lang = lang
        self.preflight = dict(preflight or {})
        self.current_theme = getattr(parent, "current_theme", "dark")
        self._accepted = False
        self._accepted_mixed_resolution = False
        self.setWindowTitle(tr("Training Preflight", self.lang))
        self.resize(920, 760)

        layout = QVBoxLayout(self)

        intro = QLabel(
            tr(
                "Training will use only saved annotations and image files. View/manifest gating is no longer used in the main Train Models path.",
                self.lang,
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.summary_label = QLabel(self._build_overall_summary())
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("mutedLabel")
        layout.addWidget(self.summary_label)

        tabs = QTabWidget()
        tabs.addTab(self._build_overview_tab(), ui_text("Overview", self.lang))
        tabs.addTab(self._build_coverage_tab(), ui_text("Coverage", self.lang))
        tabs.addTab(self._build_warnings_tab(), ui_text("Warnings", self.lang))
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons = buttons
        self.btn_train = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.btn_cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.btn_train.setText(tr("Train anyway", self.lang))
        self.btn_cancel.setText(tr("Cancel", self.lang))
        self.set_theme(self.current_theme)
        buttons.accepted.connect(self._accept_training)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_theme(self, theme):
        self.current_theme = theme
        apply_theme_dialog_button_box_style(
            getattr(self, "buttons", None),
            ok_role=BUTTON_ROLE_RUN,
            cancel_role=BUTTON_ROLE_STOP,
            theme=theme,
        )

    def _ui(self, text):
        return ui_text(text, self.lang)

    def _translate_warning(self, text):
        return _translate_training_warning_text(text, self.lang)

    def _warnings_text(self):
        warnings = list(self.preflight.get("warnings", []))
        excluded_sections = [
            ("Missing images", self.preflight.get("excluded_missing_images", [])),
            ("Unreadable images", self.preflight.get("excluded_invalid_images", [])),
            ("Zero-annotation images", self.preflight.get("excluded_zero_annotation_images", [])),
            ("Invalid-annotation images", self.preflight.get("excluded_invalid_annotation_images", [])),
        ]
        lines = []
        if warnings:
            lines.append(self._ui("Warnings:"))
            lines.extend(f"- {self._translate_warning(warning)}" for warning in warnings)
        else:
            lines.append(self._ui("No warnings. The current saved annotations satisfy the training gate."))
        for title, values in excluded_sections:
            if values:
                lines.append("")
                lines.append(f"{self._ui(title)}:")
                lines.extend(f"- {os.path.basename(str(value))}" for value in values)
        return "\n".join(lines)

    def _build_overall_summary(self):
        locator_count = int(self.preflight.get("locator_image_count", 0))
        parts_count = int(self.preflight.get("parts_image_count", 0))
        locator_ready = self._ui("Ready") if locator_count > 0 else self._ui("Skipped")
        sam_ready = self._ui("Ready") if parts_count > 0 else self._ui("Skipped")
        selected_locator_size = format_size_pair(self.preflight.get("selected_locator_size"))
        if self.preflight.get("mixed_native_resolutions"):
            mixed_note = tr("Mixed native image resolutions detected among locator-eligible images. Training will unify them to the smallest native resolution tier among eligible images: {0}. Continue?", self.lang).format(selected_locator_size)
        else:
            mixed_note = self._ui("Mixed-resolution decision: locator training will use {0}.").format(selected_locator_size)
        return (
            f"{self._ui('Locator stage: {0} | SAM stage: {1}').format(locator_ready, sam_ready)}\n"
            f"{self._ui('Locator size: {0}').format(selected_locator_size)}\n"
            f"{mixed_note}"
        )

    def _make_readonly_text(self, text):
        box = QTextEdit()
        box.setReadOnly(True)
        box.setPlainText(text)
        box.setMinimumHeight(160)
        return box

    def _coverage_lines(self, title, total_count, train_count, val_count, total_text, train_text, val_text):
        lines = [
            self._ui(title),
            f"  {self._ui('total images: {0}').format(total_count)}",
            f"  {self._ui('train images: {0}').format(train_count)}",
            f"  {self._ui('val images: {0}').format(val_count)}",
            f"  {self._ui('total coverage: {0}').format(total_text)}",
            f"  {self._ui('train coverage: {0}').format(train_text)}",
            f"  {self._ui('val coverage: {0}').format(val_text)}",
        ]
        return "\n".join(lines)

    def _build_overview_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        selected_locator_size = format_size_pair(self.preflight.get("selected_locator_size"))
        locator_size_summary = str(self.preflight.get("locator_size_summary", "none") or "none")
        overview_lines = [
            self._ui("Locator eligible images: {0}").format(int(self.preflight.get('locator_image_count', 0))),
            self._ui("SAM/parts eligible images: {0}").format(int(self.preflight.get('parts_image_count', 0))),
            self._ui("Selected locator size: {0}").format(selected_locator_size),
            self._ui("Eligible locator native sizes: {0}").format(locator_size_summary),
            self._ui("Mixed native resolutions: {0}").format(_yes_no_text(self.preflight.get('mixed_native_resolutions'), self.lang)),
        ]
        layout.addWidget(self._make_readonly_text("\n".join(overview_lines)))
        return tab

    def _build_coverage_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        locator_text = self._coverage_lines(
            "Locator coverage",
            int(self.preflight.get("locator_image_count", 0)),
            len(self.preflight.get("locator_train_data", []) or []),
            len(self.preflight.get("locator_val_data", []) or []),
            describe_part_coverage(self.preflight.get("locator_part_counts", {}), self.preflight.get("locator_scope", [])),
            describe_part_coverage(self.preflight.get("locator_train_part_counts", {}), self.preflight.get("locator_scope", [])),
            describe_part_coverage(self.preflight.get("locator_val_part_counts", {}), self.preflight.get("locator_scope", [])),
        )
        parts_text = self._coverage_lines(
            "SAM / parts coverage",
            int(self.preflight.get("parts_image_count", 0)),
            len(self.preflight.get("parts_train_data", []) or []),
            len(self.preflight.get("parts_val_data", []) or []),
            describe_part_coverage(self.preflight.get("parts_part_counts", {}), self.preflight.get("taxonomy", [])),
            describe_part_coverage(self.preflight.get("parts_train_part_counts", {}), self.preflight.get("taxonomy", [])),
            describe_part_coverage(self.preflight.get("parts_val_part_counts", {}), self.preflight.get("taxonomy", [])),
        )
        layout.addWidget(self._make_readonly_text(locator_text + "\n\n" + parts_text))
        return tab

    def _build_warnings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._make_readonly_text(self._warnings_text()))
        return tab

    def _accept_training(self):
        self._accepted = True
        self._accepted_mixed_resolution = not bool(self.preflight.get("mixed_native_resolutions"))
        self.accept()

    def accepted_training(self):
        return self._accepted

    def accepted_mixed_resolution(self):
        return self._accepted_mixed_resolution

class TrainingReportDialog(QDialog):
    def __init__(self, report_data, parent=None, lang="en"):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tr("Training Report & Validation", self.lang))
        self.resize(1200, 800)
        self.report_data = dict(report_data or {})
        self.validation_rows = self._load_validation_rows()
        self.filtered_validation_rows = list(self.validation_rows)
        self.report_summary = self._load_report_summary()
        
        layout = QVBoxLayout(self)
        
        tabs = QTabWidget()

        tab_summary = QWidget()
        summary_layout = QVBoxLayout(tab_summary)
        self.summary_box = QTextEdit()
        self.summary_box.setReadOnly(True)
        self.summary_box.setPlainText(self._build_summary_text())
        summary_layout.addWidget(self.summary_box)
        tabs.addTab(tab_summary, tr("Summary", self.lang))
        
        # Tab 1: Metrics Plot
        tab_metrics = QWidget()
        layout_m = QVBoxLayout(tab_metrics)
        self.lbl_metrics = QLabel(tr("No Metrics Generated", self.lang))
        self.lbl_metrics.setAlignment(Qt.AlignCenter)
        if report_data.get('metrics') and os.path.exists(report_data['metrics']):
            from PySide6.QtGui import QPixmap
            pix = QPixmap(report_data['metrics'])
            self.lbl_metrics.setPixmap(pix.scaled(1000, 700, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout_m.addWidget(self.lbl_metrics)
        tabs.addTab(tab_metrics, tr("Training Metrics", self.lang))
        
        # Tab 2: Validation Samples
        tab_val = QWidget()
        layout_v = QVBoxLayout(tab_val)
        
        # Controls for deterministic browsing
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel(tr("Show Validation Set %:", self.lang)))
        
        self.slider_pct = QSlider(Qt.Horizontal)
        self.slider_pct.setRange(5, 100)
        self.slider_pct.setValue(20)
        self.slider_pct.setTickPosition(QSlider.TicksBelow)
        self.slider_pct.setTickInterval(10)
        
        self.lbl_pct = QLabel("20%")
        self.slider_pct.valueChanged.connect(lambda v: self.lbl_pct.setText(f"{v}%"))
        
        ctrl_layout.addWidget(self.slider_pct)
        ctrl_layout.addWidget(self.lbl_pct)

        self.validation_filter = NoWheelComboBox()
        self.validation_filter.addItem(tr("All validation", self.lang), "all")
        self.validation_filter.addItem(tr("Macro locator", self.lang), "macro_locator")
        self.validation_filter.currentIndexChanged.connect(self.load_gallery)
        ctrl_layout.addWidget(self.validation_filter)
        
        btn_load = QPushButton(tr("Load Samples", self.lang))
        btn_load.clicked.connect(self.load_gallery)
        ctrl_layout.addWidget(btn_load)
        ctrl_layout.addStretch()
        
        layout_v.addLayout(ctrl_layout)
        
        # Scroll Area
        scroll_v = QScrollArea()
        scroll_v.setWidgetResizable(True)
        self.content_v = QWidget()
        self.layout_gallery = QVBoxLayout(self.content_v) # Main layout for scroll content
        
        # 1. Initial Summary Image
        self.lbl_val = QLabel(tr("No Validation Summary", self.lang))
        self.lbl_val.setAlignment(Qt.AlignCenter)
        if report_data.get('val') and os.path.exists(report_data['val']):
            from PySide6.QtGui import QPixmap
            pix = QPixmap(report_data['val'])
            self.lbl_val.setPixmap(pix)
            self.layout_gallery.addWidget(QLabel(tr("--- Initial Summary (Top 6) ---", self.lang)))
            self.layout_gallery.addWidget(self.lbl_val)
        
        self.validation_index_table = QTableWidget(0, 5)
        self.validation_index_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.validation_index_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.validation_index_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.validation_index_table.setAlternatingRowColors(True)
        self.validation_index_table.verticalHeader().setVisible(False)
        self.validation_index_table.horizontalHeader().setStretchLastSection(True)
        self.validation_index_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.validation_index_table.setHorizontalHeaderLabels([
            ui_text("ID", self.lang),
            ui_text("Image", self.lang),
            ui_text("Source", self.lang),
            ui_text("Valid Parts", self.lang),
            ui_text("Max Error(px)", self.lang),
        ])
        self.validation_index_table.itemSelectionChanged.connect(self._load_selected_detail_preview)
        layout_v.addWidget(self.validation_index_table)

        # 2. Dynamic Grid Placeholder
        self.grid_widget = QWidget()
        self.grid_layout = None # Will be created on load
        self.layout_gallery.addWidget(QLabel(tr("--- Detailed Inspection ---", self.lang)))
        self.layout_gallery.addWidget(self.grid_widget)
        self.layout_gallery.addStretch()
        
        scroll_v.setWidget(self.content_v)
        layout_v.addWidget(scroll_v)
        tabs.addTab(tab_val, tr("Validation Inspection", self.lang))
        
        layout.addWidget(tabs)
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_open = QPushButton(tr("Open Report Folder", self.lang))
        btn_open.clicked.connect(self.open_folder)
        btn_close = QPushButton(tr("Close", self.lang))
        btn_close.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_open)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.load_gallery()

    def _ui(self, text):
        return ui_text(text, self.lang)

    def _load_report_summary(self):
        summary_path = self.report_data.get("report_summary")
        if summary_path and os.path.exists(summary_path):
            try:
                with open(summary_path, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                    if isinstance(loaded, dict):
                        return loaded
            except Exception:
                pass
        summary = self.report_data.get("validation_summary")
        return dict(summary or {})

    def _load_validation_rows(self):
        if isinstance(self.report_data.get("validation_rows"), list):
            return [dict(row) for row in self.report_data.get("validation_rows", []) if isinstance(row, dict)]
        index_path = self.report_data.get("validation_index")
        rows = []
        if index_path and os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8", newline="") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        rows.append(dict(row))
            except Exception:
                pass
        return rows

    def _build_summary_text(self):
        lines = []
        if self.report_summary:
            lines.append(self._ui("Validation count: {0}").format(self.report_summary.get('validation_count', 0)))
            lines.append(self._ui("Preview count: {0}").format(self.report_summary.get('validation_preview_count', 0)))
            provenance_counts = self.report_summary.get("validation_provenance_counts", {}) or {}
            if provenance_counts:
                lines.append(self._ui("Provenance counts:"))
                for key, value in sorted(provenance_counts.items()):
                    lines.append(f"- {_translate_validation_provenance(key, self.lang)}: {value}")
            metrics_name = self.report_summary.get("metrics_plot")
            if metrics_name:
                lines.append(self._ui("Metrics plot: {0}").format(metrics_name))
            validation_index = self.report_summary.get("validation_index_csv")
            if validation_index:
                lines.append(self._ui("Validation index: {0}").format(validation_index))
        else:
            lines.append(self._ui("No structured report summary found."))

        if self.validation_rows:
            lines.append("")
            lines.append(self._ui("Validation samples:"))
            for row in self.validation_rows[:10]:
                lines.append(
                    f"- {row.get('sample_id', '')}: {row.get('image_name', '')} | {_translate_validation_provenance(row.get('provenance', ''), self.lang)} | {row.get('error_summary', '')}"
                )
        return "\n".join(lines)

    def _current_filtered_rows(self):
        filter_value = self.validation_filter.currentData() if hasattr(self, "validation_filter") else "all"
        if filter_value in (None, "all"):
            return list(self.validation_rows)
        return [row for row in self.validation_rows if row.get("provenance") == filter_value]

    def _detail_image_path(self, row):
        details_dir = self.report_data.get("details_dir") or os.path.join(self.report_data.get("dir", ""), "val_details")
        detail_name = row.get("detail_image") if isinstance(row, dict) else None
        if not detail_name:
            return None
        path = os.path.join(details_dir, detail_name)
        return path if os.path.exists(path) else None

    def _rebuild_gallery_grid(self, selected_rows):
        if self.grid_layout:
            while self.grid_layout.count():
                item = self.grid_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            QWidget().setLayout(self.grid_layout)

        from PySide6.QtWidgets import QGridLayout
        from PySide6.QtGui import QPixmap

        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(10)

        row_idx = 0
        col_idx = 0
        max_cols = 3
        for row in selected_rows:
            detail_path = self._detail_image_path(row)
            if not detail_path:
                continue
            label = QLabel()
            pix = QPixmap(detail_path)
            if pix.width() > 400:
                pix = pix.scaledToWidth(400, Qt.SmoothTransformation)
            label.setPixmap(pix)
            label.setToolTip(f"{row.get('sample_id', '')} | {row.get('image_name', '')}")
            self.grid_layout.addWidget(label, row_idx, col_idx)
            col_idx += 1
            if col_idx >= max_cols:
                col_idx = 0
                row_idx += 1

    def _populate_validation_index_table(self, selected_rows):
        self.validation_index_table.setRowCount(len(selected_rows))
        for row_idx, row in enumerate(selected_rows):
            values = [
                row.get("sample_id", ""),
                row.get("image_name", ""),
                _translate_validation_provenance(row.get("provenance", ""), self.lang),
                row.get("valid_parts", ""),
                row.get("max_error_px", ""),
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, dict(row))
                self.validation_index_table.setItem(row_idx, col_idx, item)

    def _load_selected_detail_preview(self):
        current_row = self.validation_index_table.currentRow()
        if current_row < 0:
            return
        item = self.validation_index_table.item(current_row, 0)
        if not item:
            return
        row = item.data(Qt.UserRole)
        if not isinstance(row, dict):
            return
        self._rebuild_gallery_grid([row])

    def load_gallery(self):
        val_dir = self.report_data.get("details_dir") or os.path.join(self.report_data.get('dir', ''), "val_details")
        if not os.path.exists(val_dir):
            QMessageBox.warning(self, tr("Error", self.lang), tr("No validation details found at {0}", self.lang).format(val_dir))
            return

        if not self.validation_rows:
            QMessageBox.warning(self, tr("Error", self.lang), tr("No images found.", self.lang))
            return

        filtered_rows = self._current_filtered_rows()
        if not filtered_rows:
            self.filtered_validation_rows = []
            self.validation_index_table.setRowCount(0)
            self._rebuild_gallery_grid([])
            self.lbl_pct.setText(tr("{0}% ({1} images)", self.lang).format(self.slider_pct.value(), 0))
            return

        pct = self.slider_pct.value()
        count = max(1, int(len(filtered_rows) * (pct / 100.0)))
        selected_rows = filtered_rows[:count]
        self.filtered_validation_rows = list(selected_rows)
        self._populate_validation_index_table(selected_rows)
        self._rebuild_gallery_grid(selected_rows[: min(6, len(selected_rows))])
        if selected_rows:
            self.validation_index_table.setCurrentCell(0, 0)
        self.lbl_pct.setText(tr("{0}% ({1} images)", self.lang).format(pct, count))
        
    def open_folder(self):
        d = self.report_data.get('dir')
        if d:
            open_path(d)


class RouteManagementPanel(QWidget):
    NODE_TYPE_ROLE = Qt.UserRole
    NODE_PAYLOAD_ROLE = Qt.UserRole + 1

    def __init__(self, owner, lang="en", parent=None):
        super().__init__(parent)
        self.owner = owner
        self.lang = lang
        self.init_ui()
        self.retranslate_ui()

    def _ui(self, text):
        return ui_text(text, self.lang)

    def _tr(self, text):
        return tr(text, self.lang)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.header_label = QLabel()
        self.header_label.setObjectName("HeaderLabel")
        layout.addWidget(self.header_label)

        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        self.note_label.setObjectName("mutedLabel")
        layout.addWidget(self.note_label)

        self.route_tree = QTreeWidget()
        self.route_tree.setObjectName("projectRouteTree")
        self.route_tree.setAlternatingRowColors(True)
        self.route_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.route_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.route_tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.route_tree.setRootIsDecorated(True)
        self.route_tree.setItemsExpandable(True)
        self.route_tree.setUniformRowHeights(True)
        self.route_tree.header().setStretchLastSection(True)
        self.route_tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.route_tree.itemSelectionChanged.connect(self.update_action_buttons)
        self.route_tree.setMinimumHeight(380)
        self.route_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.route_tree, 1)

        button_row = QHBoxLayout()
        self.btn_refresh_routes = QPushButton()
        self.btn_refresh_routes.clicked.connect(self.refresh_route_table)
        apply_semantic_button_style(self.btn_refresh_routes, BUTTON_ROLE_NEUTRAL)
        button_row.addWidget(self.btn_refresh_routes)

        self.btn_appoint_route_expert = QPushButton()
        self.btn_appoint_route_expert.clicked.connect(self.appoint_selected_route_expert)
        apply_semantic_button_style(self.btn_appoint_route_expert, BUTTON_ROLE_COMMIT)
        button_row.addWidget(self.btn_appoint_route_expert)

        self.btn_toggle_route = QPushButton()
        self.btn_toggle_route.clicked.connect(self.toggle_selected_route_enabled)
        apply_semantic_button_style(self.btn_toggle_route, BUTTON_ROLE_NEUTRAL)
        button_row.addWidget(self.btn_toggle_route)

        self.btn_delete_route = QPushButton()
        self.btn_delete_route.clicked.connect(self.delete_selected_route)
        apply_semantic_button_style(self.btn_delete_route, BUTTON_ROLE_DESTRUCTIVE)
        button_row.addWidget(self.btn_delete_route)

        layout.addLayout(button_row)

    def set_language(self, lang):
        self.lang = lang
        self.retranslate_ui()
        self.refresh_route_table()

    def set_theme(self, theme):
        apply_theme_button_style(self.btn_refresh_routes, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_appoint_route_expert, BUTTON_ROLE_COMMIT, "", theme)
        apply_theme_button_style(self.btn_toggle_route, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_delete_route, BUTTON_ROLE_DESTRUCTIVE, "", theme)

    def retranslate_ui(self):
        self.header_label.setText(self._ui("Project Routes"))
        self.note_label.setText(
            self._ui(
                "Manage Blink-discovered or manually appointed project routes here. Deleting a route removes only this project record; reopening Blink later with the same parent/child context can register a candidate again."
            )
        )
        self.btn_refresh_routes.setText(self._tr("Refresh"))
        self.btn_appoint_route_expert.setText(self._tr("Appoint Expert"))
        self.btn_delete_route.setText(self._tr("Delete"))
        self.route_tree.setHeaderLabels([
            self._ui("Parent"),
            self._ui("Child"),
            self._ui("Enabled"),
            self._ui("Expert"),
            self._ui("Status"),
            self._ui("Source"),
        ])
        self.update_action_buttons()

    def _selected_node_payload(self):
        item = self.route_tree.currentItem()
        if item is None:
            return None
        payload = item.data(0, self.NODE_PAYLOAD_ROLE)
        return dict(payload) if isinstance(payload, dict) else None

    def _selected_route_entry(self):
        payload = self._selected_node_payload() or {}
        route = payload.get("route")
        return dict(route) if isinstance(route, dict) else None

    def _selected_expert_entry(self):
        payload = self._selected_node_payload() or {}
        expert = payload.get("expert")
        return dict(expert) if isinstance(expert, dict) else None

    def _make_node_payload(self, kind, *, route=None, expert=None, parent_part=None):
        payload = {"kind": str(kind or "")}
        if isinstance(route, dict):
            payload["route"] = dict(route)
        if isinstance(expert, dict):
            payload["expert"] = dict(expert)
        if parent_part:
            payload["parent_part"] = str(parent_part)
        return payload

    def _available_experts_by_part(self):
        cascade_manager = getattr(getattr(self.owner, "engine", None), "cascade_manager", None)
        if cascade_manager is None:
            return {}

        experts_by_part = {}
        for expert in cascade_manager.list_available_experts() or []:
            if not isinstance(expert, dict):
                continue
            expert_part = str(expert.get("expert_part") or "").strip()
            if not expert_part:
                continue
            experts_by_part.setdefault(expert_part, []).append(dict(expert))
        return experts_by_part

    def _expert_notes(self):
        weights_dir = getattr(getattr(self.owner, "engine", None), "weights_dir", "")
        return load_expert_notes(weights_dir)

    def _route_expert_candidates(self, route_entry, available_experts_by_part):
        route = dict(route_entry or {})
        cascade_manager = getattr(getattr(self.owner, "engine", None), "cascade_manager", None)
        resolve_route_expert_path = getattr(cascade_manager, "resolve_route_expert_path", None)
        child_part = str(route.get("child") or "").strip()

        appointed_label = format_expert_label(route)
        appointed_candidate = None
        if appointed_label != "Unappointed":
            appointed_candidate = {
                "expert_id": appointed_label,
                "expert_part": route.get("expert_part") or route.get("child"),
                "expert_filename": route.get("expert_filename"),
                "path": resolve_route_expert_path(route) if callable(resolve_route_expert_path) else None,
            }

        candidates = []
        persisted_candidates = get_route_persisted_expert_candidates(route)
        runtime_candidates = available_experts_by_part.get(child_part, [])
        merged_candidates = merge_expert_candidates(
            persisted_candidates,
            runtime_candidates,
            appointed_expert=appointed_candidate,
        )

        available_by_id = {}
        for expert in runtime_candidates:
            expert_id = str(expert.get("expert_id") or "").strip()
            if not expert_id:
                continue
            available_by_id[expert_id] = dict(expert)

        persisted_ids = {
            str(candidate.get("expert_id") or "").strip()
            for candidate in persisted_candidates
            if isinstance(candidate, dict)
        }

        for candidate in merged_candidates:
            expert_id = str(candidate.get("expert_id") or "").strip()
            if not expert_id:
                continue

            runtime_match = available_by_id.get(expert_id)
            is_appointed = expert_id == appointed_label
            is_persisted = expert_id in persisted_ids or is_appointed
            merged_candidate = dict(candidate)
            if isinstance(runtime_match, dict):
                merged_candidate.update(runtime_match)

            merged_candidate["appointed"] = is_appointed
            merged_candidate["is_persisted"] = is_persisted
            merged_candidate["is_discoverable"] = isinstance(runtime_match, dict)
            path_value = merged_candidate.get("path")
            merged_candidate["file_exists"] = bool(path_value) and os.path.exists(path_value)
            candidates.append(merged_candidate)
        return candidates

    def _set_item_payload(self, item, payload):
        item.setData(0, self.NODE_TYPE_ROLE, payload.get("kind"))
        item.setData(0, self.NODE_PAYLOAD_ROLE, payload)

    def _build_route_tree_item(self, parent_item, route_entry, expert_candidates):
        route = dict(route_entry or {})
        expert_notes = self._expert_notes()
        route_item = QTreeWidgetItem(parent_item)
        self._set_item_payload(route_item, self._make_node_payload("route", route=route))
        route_item.setText(1, str(route.get("child") or ""))
        route_item.setText(2, _yes_no_text(route.get("enabled"), self.lang))
        route_label = format_expert_label(route)
        if route_label != "Unappointed":
            route_note = expert_notes.get(route_label, "")
            route_display = format_expert_display_name(route_label, route_note)
            route_item.setText(3, route_display)
            route_item.setToolTip(3, f"{route_display}\n{route_label}")
        else:
            route_item.setText(3, self._ui("Not appointed"))
        route_item.setText(4, self._route_runtime_status(route))
        route_item.setText(5, _translate_route_registration_source(route.get("registration_source"), self.lang))

        if not expert_candidates:
            placeholder_item = QTreeWidgetItem(route_item)
            self._set_item_payload(placeholder_item, self._make_node_payload("expert_placeholder", route=route))
            placeholder_item.setText(3, self._ui("Not appointed"))
            placeholder_item.setText(4, self._ui("Expert not appointed yet"))
            placeholder_item.setFlags(placeholder_item.flags() & ~Qt.ItemIsSelectable)
            return route_item

        for expert in expert_candidates:
            expert_item = QTreeWidgetItem(route_item)
            self._set_item_payload(expert_item, self._make_node_payload("expert", route=route, expert=expert))
            expert_id = str(expert.get("expert_id") or "").strip()
            is_appointed = bool(expert.get("appointed"))
            is_discoverable = bool(expert.get("is_discoverable"))
            is_persisted = bool(expert.get("is_persisted"))
            file_exists = bool(expert.get("file_exists"))
            expert_note = expert_notes.get(expert_id, "")
            expert_label = format_expert_display_name(expert_id, expert_note, appointed=is_appointed)
            expert_item.setText(3, expert_label)
            expert_item.setToolTip(3, f"{expert_label}\n{expert_id}")
            if is_appointed:
                status_text = self._ui("Appointed")
            elif is_persisted and not file_exists:
                status_text = self._ui("Missing file history")
            elif is_persisted:
                status_text = self._ui("History")
            elif is_discoverable:
                status_text = self._ui("Discoverable")
            else:
                status_text = self._ui("Available")
            expert_item.setText(4, status_text)
            if is_appointed:
                expert_font = expert_item.font(3)
                expert_font.setBold(True)
                expert_item.setFont(3, expert_font)
                status_font = expert_item.font(4)
                status_font.setBold(True)
                expert_item.setFont(4, status_font)
        return route_item

    def _find_parent_item(self, parent_part):
        clean_parent = str(parent_part or "").strip()
        for index in range(self.route_tree.topLevelItemCount()):
            item = self.route_tree.topLevelItem(index)
            if item is None:
                continue
            payload = item.data(0, self.NODE_PAYLOAD_ROLE)
            if isinstance(payload, dict) and payload.get("kind") == "parent" and payload.get("parent_part") == clean_parent:
                return item
        return None

    def _find_route_item(self, parent_part, child_part):
        parent_item = self._find_parent_item(parent_part)
        clean_child = str(child_part or "").strip()
        if parent_item is None or not clean_child:
            return None
        for index in range(parent_item.childCount()):
            item = parent_item.child(index)
            if item is None:
                continue
            payload = item.data(0, self.NODE_PAYLOAD_ROLE)
            route = payload.get("route") if isinstance(payload, dict) else None
            if isinstance(route, dict) and route.get("parent") == str(parent_part or "").strip() and route.get("child") == clean_child:
                return item
        return None

    def _find_expert_item(self, parent_part, child_part, expert_id):
        route_item = self._find_route_item(parent_part, child_part)
        clean_expert_id = str(expert_id or "").strip()
        if route_item is None or not clean_expert_id:
            return None
        for index in range(route_item.childCount()):
            item = route_item.child(index)
            if item is None:
                continue
            payload = item.data(0, self.NODE_PAYLOAD_ROLE)
            expert = payload.get("expert") if isinstance(payload, dict) else None
            if isinstance(expert, dict) and str(expert.get("expert_id") or "").strip() == clean_expert_id:
                return item
        return None

    def _route_runtime_status(self, route_entry):
        if not route_entry:
            return self._ui("Unknown")
        block_reason = self.owner.engine.cascade_manager.get_route_block_reason(route_entry)
        if block_reason == "expert_unappointed":
            return self._ui("Expert not appointed yet")
        if block_reason == "expert_model_missing":
            return self._tr("Expert file missing")
        return self._ui("Enabled") if bool(route_entry.get("enabled", False)) else self._ui("Disabled")

    def refresh_route_table(self):
        routes = self.owner.project.iter_cascade_routes()
        experts_by_part = self._available_experts_by_part()
        self.route_tree.clear()
        parent_items = {}

        for route in routes:
            parent_part = str(route.get("parent") or "")
            parent_item = parent_items.get(parent_part)
            if parent_item is None:
                parent_item = QTreeWidgetItem(self.route_tree)
                self._set_item_payload(parent_item, self._make_node_payload("parent", parent_part=parent_part))
                parent_item.setText(0, parent_part)
                parent_item.setExpanded(True)
                parent_items[parent_part] = parent_item

            expert_candidates = self._route_expert_candidates(route, experts_by_part)
            route_item = self._build_route_tree_item(parent_item, route, expert_candidates)
            route_item.setExpanded(True)

        self.route_tree.expandAll()
        self.update_action_buttons()

    def update_action_buttons(self):
        payload = self._selected_node_payload() or {}
        route = self._selected_route_entry()
        expert = self._selected_expert_entry()
        selected_kind = str(payload.get("kind") or "")
        can_delete_missing_history = (
            selected_kind == "expert"
            and bool(route)
            and bool(expert)
            and bool(expert.get("is_persisted"))
            and not bool(expert.get("file_exists"))
            and not bool(expert.get("appointed"))
            and hasattr(self.owner.project, "remove_cascade_route_expert_candidate")
        )
        self.btn_appoint_route_expert.setEnabled(selected_kind == "expert" and bool(self._selected_expert_entry()))
        self.btn_delete_route.setEnabled((selected_kind == "route" and bool(route)) or can_delete_missing_history)
        self.btn_toggle_route.setEnabled(selected_kind == "route" and bool(route))
        self.btn_toggle_route.setText(
            self._tr("Disable Route") if route and route.get("enabled") else self._tr("Enable Route")
        )

    def appoint_selected_route_expert(self):
        payload = self._selected_node_payload() or {}
        if str(payload.get("kind") or "") != "expert":
            return
        route = self._selected_route_entry()
        expert = self._selected_expert_entry()
        if not route or not expert:
            return
        selected_label = str(expert.get("expert_id") or "").strip()
        if not selected_label:
            return

        updated = self.owner.project.appoint_cascade_route_expert(
            route.get("parent"),
            route.get("child"),
            expert_id=selected_label,
        )
        if updated:
            self.refresh_route_table()
            self.owner.log(
                self._ui("Route {0} -> {1} now uses expert {2}.").format(
                    route.get("parent"),
                    route.get("child"),
                    selected_label,
                )
            )

    def toggle_selected_route_enabled(self):
        payload = self._selected_node_payload() or {}
        if str(payload.get("kind") or "") != "route":
            return
        route = self._selected_route_entry()
        if not route:
            return
        block_reason = self.owner.engine.cascade_manager.get_route_block_reason(route)
        if not route.get("enabled") and block_reason == "expert_unappointed":
            QMessageBox.information(self, self._tr("Appoint Expert"), self._ui("This route has no appointed expert yet. Appoint an expert first, then enable the route."))
            return
        if not route.get("enabled") and block_reason == "expert_model_missing":
            QMessageBox.information(self, self._tr("Appoint Expert"), self._ui("The appointed expert file for this route is missing. Reappoint an available expert before enabling the route."))
            return

        updated = self.owner.project.set_cascade_route_enabled(
            route.get("parent"),
            route.get("child"),
            not bool(route.get("enabled")),
        )
        if updated:
            self.refresh_route_table()
            if updated.get("enabled"):
                self.owner.log(self._ui("Route {0} -> {1} enabled.").format(updated.get("parent"), updated.get("child")))
            else:
                self.owner.log(self._ui("Route {0} -> {1} disabled.").format(updated.get("parent"), updated.get("child")))

    def delete_selected_route(self):
        payload = self._selected_node_payload() or {}
        if str(payload.get("kind") or "") == "expert":
            self.remove_selected_missing_expert_history()
            return
        if str(payload.get("kind") or "") != "route":
            return
        route = self._selected_route_entry()
        if not route:
            return
        reply = themed_yes_no_question(
            self,
            self._tr("Delete"),
            self._ui(
                "Delete project route {0} -> {1}?\n\nThis removes the current project route record only. If you reopen Blink later with the same parent/child context, Blink can register this route again as a candidate."
            ).format(route.get("parent"), route.get("child")),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply != QMessageBox.Yes:
            return
        if self.owner.project.delete_cascade_route(route.get("parent"), route.get("child")):
            self.refresh_route_table()
            self.owner.log(self._ui("Deleted route {0} -> {1}.").format(route.get("parent"), route.get("child")))

    def remove_selected_missing_expert_history(self):
        route = self._selected_route_entry()
        expert = self._selected_expert_entry()
        if not route or not expert:
            return
        if not bool(expert.get("is_persisted")) or bool(expert.get("file_exists")) or bool(expert.get("appointed")):
            return
        remove_candidate = getattr(self.owner.project, "remove_cascade_route_expert_candidate", None)
        if not callable(remove_candidate):
            return
        expert_id = str(expert.get("expert_id") or "").strip()
        if not expert_id:
            return
        reply = themed_yes_no_question(
            self,
            self._tr("Delete"),
            self._ui(
                "Remove missing expert history {0} from route {1} -> {2}?\n\nThis only cleans the current project route history. It does not delete any model file."
            ).format(expert_id, route.get("parent"), route.get("child")),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply != QMessageBox.Yes:
            return
        if remove_candidate(route.get("parent"), route.get("child"), expert_id):
            self.refresh_route_table()
            self.owner.log(
                self._ui("Removed missing expert history {0} from route {1} -> {2}.").format(
                    expert_id,
                    route.get("parent"),
                    route.get("child"),
                )
            )

class ModelSettingsDialog(QDialog):
    def __init__(self, params, lang="en", parent=None, route_panel=None):
        super().__init__(parent)
        self.lang = lang
        self.route_panel = route_panel
        self.setWindowTitle(tr("2D/STL Morphology Model Settings", lang))
        self.resize(880, 680)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.locator_scope_checks = []

        workflow_note = QLabel(
            tr(
                "2D/STL morphology settings control rendered STL views and ordinary morphology images. TIF volume training is configured separately.",
                lang,
            )
        )
        workflow_note.setWordWrap(True)
        workflow_note.setObjectName("mutedLabel")
        layout.addWidget(workflow_note)

        tab_backend = QWidget()
        form_backend = QVBoxLayout(tab_backend)
        form_backend.addWidget(QLabel(tr("Model Backend:", lang)))
        self.backend_combo = NoWheelComboBox()
        self.backend_combo.addItem(tr("Built-in Locator + SAM", lang), BUILTIN_BACKEND_ID)
        self.backend_combo.addItem(tr("External Script Backend", lang), EXTERNAL_BACKEND_ID)
        backend_index = self.backend_combo.findData(params.get("model_backend", BUILTIN_BACKEND_ID))
        self.backend_combo.setCurrentIndex(backend_index if backend_index >= 0 else 0)
        form_backend.addWidget(self.backend_combo)
        external_note = QLabel(
            tr("Use this advanced entry when you want TaxaMask to call your own training or prediction scripts. Commands run in an isolated external_runs directory and receive a contract JSON path through {contract} or {contract_json}. When this backend is selected, built-in Locator/SAM training and prediction do not run for that task.", lang)
        )
        external_note.setWordWrap(True)
        external_note.setObjectName("mutedLabel")
        form_backend.addWidget(external_note)

        external_config = sanitize_external_backend_config(params.get("external_backend", {}))
        form_backend.addWidget(QLabel(tr("Backend ID:", lang)))
        self.external_backend_id = QLineEdit(external_config.get("backend_id", ""))
        form_backend.addWidget(self.external_backend_id)
        form_backend.addWidget(QLabel(tr("Display Name:", lang)))
        self.external_display_name = QLineEdit(external_config.get("display_name", ""))
        form_backend.addWidget(self.external_display_name)
        form_backend.addWidget(QLabel(tr("Python Executable:", lang)))
        self.external_python = QLineEdit(external_config.get("python_executable", "python"))
        form_backend.addWidget(self.external_python)
        form_backend.addWidget(QLabel(tr("Prepare Dataset Command:", lang)))
        self.external_prepare_command = self._make_command_editor(
            external_config.get("prepare_dataset_command", ""),
            "{python} scripts/prepare_dataset.py --contract {contract_json}",
        )
        form_backend.addWidget(self.external_prepare_command)
        form_backend.addWidget(QLabel(tr("Train Command:", lang)))
        self.external_train_command = self._make_command_editor(
            external_config.get("train_command", ""),
            "{python} scripts/train_model.py --contract {contract_json}",
        )
        form_backend.addWidget(self.external_train_command)
        form_backend.addWidget(QLabel(tr("Predict Command:", lang)))
        self.external_predict_command = self._make_command_editor(
            external_config.get("predict_command", ""),
            "{python} scripts/predict_image.py --contract {contract_json}",
        )
        form_backend.addWidget(self.external_predict_command)
        form_backend.addWidget(QLabel(tr("Model Manifest Path:", lang)))
        self.external_model_manifest = QLineEdit(external_config.get("model_manifest", ""))
        self.external_model_manifest.setPlaceholderText("{run_dir}/model/taxamask_model_manifest.json")
        form_backend.addWidget(self.external_model_manifest)
        self.external_validation_label = QLabel()
        self.external_validation_label.setObjectName("mutedLabel")
        self.external_validation_label.setWordWrap(True)
        form_backend.addWidget(self.external_validation_label)
        btn_validate_external = QPushButton(tr("Validate External Backend", lang))
        apply_semantic_button_style(btn_validate_external, BUTTON_ROLE_NEUTRAL)
        btn_validate_external.clicked.connect(self.validate_external_backend)
        form_backend.addWidget(btn_validate_external)
        form_backend.addStretch()
        
        tab_train = QWidget()
        form_train = QVBoxLayout(tab_train)
        form_train.addWidget(QLabel(tr("Epochs:", lang)))
        self.spin_epochs = QLineEdit(str(params['epochs']))
        form_train.addWidget(self.spin_epochs)
        form_train.addWidget(QLabel(tr("Batch Size:", lang)))
        self.spin_batch = QLineEdit(str(params['batch']))
        form_train.addWidget(self.spin_batch)
        form_train.addWidget(QLabel(tr("Learning Rate:", lang)))
        self.spin_lr = QLineEdit(str(params['lr']))
        form_train.addWidget(self.spin_lr)
        form_train.addWidget(QLabel(tr("Weight Decay (L2 Reg):", lang)))
        self.spin_wd = QLineEdit(str(params['wd']))
        form_train.addWidget(self.spin_wd)

        device_group = QGroupBox(tr("Runtime Device:", lang))
        apply_surface_role(device_group, SURFACE_ROLE_SUBTLE, "modelSettingsRuntimeDevicePanel")
        device_layout = QVBoxLayout(device_group)
        device_layout.setContentsMargins(12, 12, 12, 12)
        device_layout.setSpacing(8)
        device_note = QLabel(
            tr(
                "Controls built-in Locator/SAM/Blink training and inference. External backends use their own command environment. CPU can run small tests, but CUDA is recommended for real training.",
                lang,
            )
        )
        device_note.setWordWrap(True)
        device_note.setObjectName("mutedLabel")
        device_layout.addWidget(device_note)
        self.combo_runtime_device = NoWheelComboBox()
        self.combo_runtime_device.addItem(tr("Auto (CUDA if available)", lang), "auto")
        self.combo_runtime_device.addItem(tr("CPU only", lang), "cpu")
        self.combo_runtime_device.addItem(tr("CUDA GPU", lang), "cuda")
        runtime_device = normalize_device_preference(params.get("runtime_device", "auto"))
        runtime_index = self.combo_runtime_device.findData(runtime_device)
        self.combo_runtime_device.setCurrentIndex(runtime_index if runtime_index >= 0 else 0)
        device_layout.addWidget(self.combo_runtime_device)
        form_train.addWidget(device_group)

        blink_group = QGroupBox(tr("Blink Expert Training Defaults:", lang))
        apply_surface_role(blink_group, SURFACE_ROLE_SUBTLE, "modelSettingsBlinkTrainingPanel")
        blink_layout = QVBoxLayout(blink_group)
        blink_layout.setContentsMargins(12, 12, 12, 12)
        blink_layout.setSpacing(8)
        blink_note = QLabel(
            tr(
                "These defaults are shown in Blink Workbench when the app starts or settings are saved. You can still adjust them for a single expert before training.",
                lang,
            )
        )
        blink_note.setWordWrap(True)
        blink_note.setObjectName("mutedLabel")
        blink_layout.addWidget(blink_note)
        blink_layout.addWidget(QLabel(tr("Default Blink Epochs:", lang)))
        self.spin_blink_epochs = QLineEdit(str(params.get("blink_epochs", 5)))
        blink_layout.addWidget(self.spin_blink_epochs)
        blink_layout.addWidget(QLabel(tr("Default Blink Batch Size:", lang)))
        self.spin_blink_batch = QLineEdit(str(params.get("blink_batch", 2)))
        blink_layout.addWidget(self.spin_blink_batch)
        blink_layout.addWidget(QLabel(tr("Default Blink Learning Rate:", lang)))
        self.spin_blink_lr = QLineEdit(str(params.get("blink_lr", 1e-3)))
        blink_layout.addWidget(self.spin_blink_lr)
        blink_layout.addWidget(QLabel(tr("Default Blink Weight Decay:", lang)))
        self.spin_blink_wd = QLineEdit(str(params.get("blink_weight_decay", 1e-4)))
        blink_layout.addWidget(self.spin_blink_wd)
        blink_layout.addWidget(QLabel(tr("Default Blink Input Size:", lang)))
        self.combo_blink_input_size = NoWheelComboBox()
        for side in [224, 384, 512]:
            self.combo_blink_input_size.addItem(f"{side} x {side}", side)
        try:
            input_side = int(params.get("blink_input_size", 224))
        except Exception:
            input_side = 224
        input_index = self.combo_blink_input_size.findData(input_side)
        self.combo_blink_input_size.setCurrentIndex(input_index if input_index >= 0 else 0)
        blink_layout.addWidget(self.combo_blink_input_size)
        form_train.addWidget(blink_group)

        locator_group = QGroupBox(tr("Main Locator Parts:", lang))
        apply_surface_role(locator_group, SURFACE_ROLE_SUBTLE, "modelSettingsLocatorScopePanel")
        locator_layout = QVBoxLayout(locator_group)
        locator_layout.setContentsMargins(12, 12, 12, 12)
        locator_layout.setSpacing(8)
        locator_note = QLabel(
            tr(
                "Choose which structures the built-in Locator should learn as large, stable targets. Small structures can stay in Structures and be refined with SAM, Blink, or an external backend.",
                lang,
            )
        )
        locator_note.setWordWrap(True)
        locator_note.setObjectName("mutedLabel")
        locator_layout.addWidget(locator_note)

        taxonomy = [str(part) for part in params.get("taxonomy", []) if str(part).strip()]
        locator_scope = [str(part) for part in params.get("locator_scope", []) if str(part).strip()]
        if not taxonomy:
            taxonomy = list(locator_scope)
        if not locator_scope:
            locator_scope = list(taxonomy)
        locator_grid = QGridLayout()
        locator_grid.setContentsMargins(0, 4, 0, 0)
        locator_grid.setHorizontalSpacing(16)
        locator_grid.setVerticalSpacing(6)
        for index, part_name in enumerate(taxonomy):
            check = QCheckBox(part_name)
            check.setChecked(part_name in locator_scope)
            check.setProperty("part_name", part_name)
            self.locator_scope_checks.append(check)
            locator_grid.addWidget(check, index // 2, index % 2)
        locator_layout.addLayout(locator_grid)
        self.locator_scope_validation_label = QLabel("")
        self.locator_scope_validation_label.setObjectName("mutedLabel")
        locator_layout.addWidget(self.locator_scope_validation_label)
        form_train.addWidget(locator_group)
        
        form_train.addStretch()
        tabs.addTab(self._make_scroll_tab(tab_train), tr("Training", lang))
        
        tab_inf = QWidget()
        form_inf = QVBoxLayout(tab_inf)
        form_inf.addWidget(QLabel(tr("Confidence Threshold:", lang)))
        self.spin_conf = QLineEdit(str(params['conf']))
        form_inf.addWidget(self.spin_conf)
        form_inf.addWidget(QLabel(tr("Adaptive Thresh Ratio:", lang)))
        self.spin_adapt = QLineEdit(str(params['adapt']))
        form_inf.addWidget(self.spin_adapt)
        form_inf.addWidget(QLabel(tr("Noise Floor:", lang)))
        self.spin_noise = QLineEdit(str(params['noise_floor']))
        form_inf.addWidget(self.spin_noise)
        form_inf.addWidget(QLabel(tr("Polygon Simplification (px):", lang)))
        self.spin_poly = QLineEdit(str(params.get('poly_epsilon', 2.0)))
        form_inf.addWidget(self.spin_poly)
        form_inf.addWidget(QLabel(tr("Box Padding Ratio:", lang)))
        self.spin_pad = QLineEdit(str(params['pad']))
        form_inf.addWidget(self.spin_pad)
        self.lbl_cascade_note = QLabel(
            ui_text(
                "Project routes below control which parent -> child expert links are available.",
                lang,
            )
        )
        self.lbl_cascade_note.setWordWrap(True)
        self.lbl_cascade_note.setObjectName("mutedLabel")
        form_inf.addWidget(self.lbl_cascade_note)

        if self.route_panel is not None:
            route_group = QGroupBox(ui_text("Project Route Management", lang))
            apply_surface_role(route_group, SURFACE_ROLE_SUBTLE, "modelSettingsRoutePanel")
            route_layout = QVBoxLayout(route_group)
            route_layout.setContentsMargins(12, 12, 12, 12)
            route_layout.setSpacing(10)
            route_layout.addWidget(self.route_panel)
            form_inf.addWidget(route_group, 1)

        form_inf.addStretch()
        tabs.addTab(self._make_scroll_tab(tab_inf), tr("Inference", lang))
        tabs.addTab(self._make_scroll_tab(tab_backend), tr("External Backend", lang))
        
        layout.addWidget(tabs, 1)
        btn_layout = QHBoxLayout()
        btn_save = QPushButton(tr("Save", lang))
        apply_semantic_button_style(btn_save, BUTTON_ROLE_COMMIT)
        btn_save.clicked.connect(self.accept_with_validation)
        btn_cancel = QPushButton(tr("Cancel", lang))
        apply_semantic_button_style(btn_cancel, BUTTON_ROLE_STOP)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _make_scroll_tab(self, content_widget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        scroll.setWidget(content_widget)
        return scroll

    def _make_command_editor(self, text, placeholder):
        editor = QTextEdit()
        editor.setAcceptRichText(False)
        editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        editor.setMinimumHeight(72)
        editor.setPlainText(str(text or ""))
        editor.setPlaceholderText(placeholder)
        return editor

    def _command_text(self, editor):
        return editor.toPlainText().strip()

    def _external_backend_validation_errors(self):
        if self.backend_combo.currentData() != EXTERNAL_BACKEND_ID:
            return []
        errors = []
        if not self.external_backend_id.text().strip():
            errors.append(tr("External backend ID is required.", self.lang))

        commands = {
            "prepare_dataset": self._command_text(self.external_prepare_command),
            "train": self._command_text(self.external_train_command),
            "predict": self._command_text(self.external_predict_command),
        }
        if not commands["train"] and not commands["predict"]:
            errors.append(tr("External backend needs at least a train command or a predict command.", self.lang))

        for command_name, command_text in commands.items():
            if command_text and "{contract}" not in command_text and "{contract_json}" not in command_text:
                errors.append(
                    tr(
                        "External backend command '{0}' must include {contract} or {contract_json}.",
                        self.lang,
                    ).format(command_name)
                )
        return errors

    def validate_external_backend(self):
        errors = self._external_backend_validation_errors()
        if errors:
            self.external_validation_label.setText("\n".join(errors))
            QMessageBox.warning(self, tr("External Backend", self.lang), "\n".join(errors))
            return False
        self.external_validation_label.setText(tr("External backend configuration looks valid.", self.lang))
        QMessageBox.information(self, tr("External Backend", self.lang), tr("External backend configuration looks valid.", self.lang))
        return True

    def accept_with_validation(self):
        errors = self._external_backend_validation_errors()
        if not self._selected_locator_scope():
            errors.append(tr("At least one main locator part must be selected.", self.lang))
        if errors:
            message = "\n".join(errors)
            self.external_validation_label.setText(message)
            self.locator_scope_validation_label.setText(message)
            QMessageBox.warning(self, tr("Model Settings", self.lang), message)
            return
        self.accept()

    def _selected_locator_scope(self):
        selected = []
        for check in self.locator_scope_checks:
            if check.isChecked():
                part_name = str(check.property("part_name") or check.text()).strip()
                if part_name:
                    selected.append(part_name)
        return selected

    def get_values(self):
        try:
            return {
                'epochs': int(self.spin_epochs.text()),
                'batch': int(self.spin_batch.text()),
                'blink_epochs': int(self.spin_blink_epochs.text()),
                'blink_batch': int(self.spin_blink_batch.text()),
                'blink_lr': float(self.spin_blink_lr.text()),
                'blink_weight_decay': float(self.spin_blink_wd.text()),
                'blink_input_size': int(self.combo_blink_input_size.currentData() or 224),
                'lr': float(self.spin_lr.text()),
                'wd': float(self.spin_wd.text()),
                'conf': float(self.spin_conf.text()),
                'adapt': float(self.spin_adapt.text()),
                'pad': float(self.spin_pad.text()),
                'noise_floor': float(self.spin_noise.text()),
                'poly_epsilon': float(self.spin_poly.text()),
                'locator_scope': self._selected_locator_scope(),
                'runtime_device': self.combo_runtime_device.currentData() or "auto",
                'model_backend': self.backend_combo.currentData() or BUILTIN_BACKEND_ID,
                'external_backend': sanitize_external_backend_config(
                    {
                        "backend_id": self.external_backend_id.text(),
                        "display_name": self.external_display_name.text(),
                        "python_executable": self.external_python.text(),
                        "prepare_dataset_command": self._command_text(self.external_prepare_command),
                        "train_command": self._command_text(self.external_train_command),
                        "predict_command": self._command_text(self.external_predict_command),
                        "model_manifest": self.external_model_manifest.text(),
                    }
                ),
            }
        except: return None


class GeneralSettingsDialog(QDialog):
    def __init__(self, params, lang="en", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tr("General Application Settings", lang))
        self.resize(620, 460)

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
        self.theme_combo.addItem(tr("Dark Mode", lang), "dark")
        theme_index = self.theme_combo.findData(normalize_theme(params.get("theme", "dark")))
        self.theme_combo.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        form.addRow(QLabel(tr("Theme:", lang)), self.theme_combo)

        theme_note = QLabel(tr("Only the audited dark theme is currently enabled.", lang))
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
                "Runtime device here is the default for built-in 2D/STL models and other internal Torch tasks. TIF external backends use the Python executable and commands configured in TIF settings.",
                lang,
            )
        )
        runtime_note.setWordWrap(True)
        runtime_note.setObjectName("mutedLabel")
        form.addRow(QLabel(""), runtime_note)

        layout.addWidget(group)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        btn_save = QPushButton(tr("Save", lang))
        apply_semantic_button_style(btn_save, BUTTON_ROLE_COMMIT)
        btn_save.clicked.connect(self.accept_with_validation)
        btn_cancel = QPushButton(tr("Cancel", lang))
        apply_semantic_button_style(btn_cancel, BUTTON_ROLE_STOP)
        btn_cancel.clicked.connect(self.reject)
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


class TifModelSettingsDialog(QDialog):
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
            "TIF training uses manual_truth label volumes only. Prediction results are imported as model_draft, so they must be reviewed before becoming manual truth.",
            "Training source: manual_truth only.",
            "Prediction import: model_draft layer.",
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
        form.addRow(QLabel(""), btn_validate)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(group)
        layout.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        btn_save = QPushButton(tr("Save", lang))
        apply_semantic_button_style(btn_save, BUTTON_ROLE_COMMIT)
        btn_save.clicked.connect(self.accept_with_validation)
        btn_cancel = QPushButton(tr("Cancel", lang))
        apply_semantic_button_style(btn_cancel, BUTTON_ROLE_STOP)
        btn_cancel.clicked.connect(self.reject)
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
                    tr("TIF backend command '{0}' must include {contract} or {contract_json}.", self.lang).format(command_name)
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


class ExportDialog(QDialog):
    def __init__(self, parent=None, lang="en"):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tr("Export Dataset", self.lang))
        self.resize(400, 150)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("Export Format:", self.lang)))
        self.format_combo = NoWheelComboBox()
        self.format_combo.addItem(tr("Multimodal (Crops + JSONL)", self.lang), "multimodal")
        self.format_combo.addItem(tr("COCO (Standard)", self.lang), "coco")
        self.format_combo.addItem(tr("YOLO (Segmentation)", self.lang), "yolo")
        layout.addWidget(self.format_combo)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(tr("Select export directory...", self.lang))
        layout.addWidget(QLabel(tr("Export Path:", self.lang)))
        browse_layout = QHBoxLayout()
        browse_layout.addWidget(self.path_edit)
        btn_browse = QPushButton(tr("Browse", self.lang))
        apply_semantic_button_style(btn_browse, BUTTON_ROLE_NEUTRAL)
        btn_browse.clicked.connect(self.browse)
        browse_layout.addWidget(btn_browse)
        layout.addLayout(browse_layout)
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton(tr("Export", self.lang))
        apply_semantic_button_style(btn_ok, BUTTON_ROLE_COMMIT)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton(tr("Cancel", self.lang))
        apply_semantic_button_style(btn_cancel, BUTTON_ROLE_STOP)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
    def browse(self):
        d = QFileDialog.getExistingDirectory(self, tr("Select Directory", self.lang))
        if d:
            self.path_edit.setText(d)
    def get_path(self): 
        return self.path_edit.text()
    def get_format(self): 
        return self.format_combo.currentData() or self.format_combo.currentText()


class BlinkEntryDialog(QDialog):
    def __init__(self, image_path, taxonomy, selected_part, roi_candidates, parent=None, lang="en", remembered_parent_map=None):
        super().__init__(parent)
        self.lang = lang
        self.current_theme = getattr(parent, "current_theme", "dark")
        self.remembered_parent_map = dict(remembered_parent_map or {})
        self.setWindowTitle(tr("Enter Blink Workbench", self.lang))
        self.setModal(True)
        self.resize(520, 220)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("Image: {0}", self.lang).format(os.path.basename(image_path))))

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel(tr("Target Part:", self.lang)))
        self.target_combo = NoWheelComboBox()
        for part in taxonomy:
            self.target_combo.addItem(tr(part, self.lang), part)
        selected_idx = self.target_combo.findData(selected_part)
        if selected_idx >= 0:
            self.target_combo.setCurrentIndex(selected_idx)
        target_row.addWidget(self.target_combo)
        layout.addLayout(target_row)

        roi_row = QHBoxLayout()
        roi_row.addWidget(QLabel(tr("Entry ROI:", self.lang)))
        self.roi_combo = NoWheelComboBox()
        for candidate in roi_candidates:
            source_text = tr("Manual Box", self.lang) if candidate.get("source") == "manual" else tr("Auto Box", self.lang)
            label = f"{tr(candidate.get('part', 'ROI'), self.lang)} ({source_text})"
            self.roi_combo.addItem(label, candidate)
        roi_row.addWidget(self.roi_combo)
        layout.addLayout(roi_row)

        self.tip_label = QLabel(
            tr("Target Part is the child part you want to refine. Entry ROI is the parent/context region Blink will zoom into. This project remembers the parent/context ROI you chose for each target part, and later Blink entries reuse that remembered context.", self.lang)
        )
        self.tip_label.setWordWrap(True)
        layout.addWidget(self.tip_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons = buttons
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.set_theme(self.current_theme)
        layout.addWidget(buttons)

        self.target_combo.currentIndexChanged.connect(self._sync_preferred_roi)
        self._sync_preferred_roi(self.target_combo.currentIndex())

    def set_theme(self, theme):
        self.current_theme = theme
        apply_theme_dialog_button_box_style(
            getattr(self, "buttons", None),
            ok_role=BUTTON_ROLE_RUN,
            cancel_role=BUTTON_ROLE_STOP,
            theme=theme,
        )

    def _sync_preferred_roi(self, _index):
        target_part = self.target_combo.currentData() or self.target_combo.currentText()
        remembered_parent = self.remembered_parent_map.get(str(target_part or "").strip())
        for preferred_part in _blink_preferred_roi_parts(target_part, remembered_parent):
            for idx in range(self.roi_combo.count()):
                candidate = self.roi_combo.itemData(idx)
                if isinstance(candidate, dict) and candidate.get("part") == preferred_part:
                    self.roi_combo.setCurrentIndex(idx)
                    return

        self.roi_combo.setCurrentIndex(-1)

    def get_session_spec(self, image_path):
        focus_roi = self.roi_combo.currentData()
        if not isinstance(focus_roi, dict):
            return None

        target_part = self.target_combo.currentData() or self.target_combo.currentText().strip()
        if not target_part:
            return None

        return {
            "image_path": image_path,
            "target_part": target_part,
            "focus_roi": focus_roi,
        }

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.startup_size = QSize(1480, 920)
        self.resize(self.startup_size)
        self.config = ConfigManager()
        self.current_lang = self.config.get("language", "en")
        self.current_theme = normalize_theme(self.config.get("theme", "dark"))
        if self.config.get("theme", "dark") != self.current_theme:
            self.config.set("theme", self.current_theme)
        self.project = ProjectManager()
        self.project.set_known_relocated_roots(self.config.get("known_relocated_roots", []))
        self.tif_project = TifProjectManager()
        self.stl_project = StlRenderedProjectManager()
        self.active_project_kind = "image"
        self.active_project_source_kind = "image"
        self.active_project_entry_path = ""
        self.db = MultiModalDB()
        
        self.train_epochs = self.config.get("train_epochs", 5)
        self.train_batch = self.config.get("train_batch", 4)
        self.blink_train_epochs = self.config.get("blink_train_epochs", 5)
        self.blink_train_batch = self.config.get("blink_train_batch", 2)
        self.blink_train_lr = self.config.get("blink_train_lr", 1e-3)
        self.blink_train_weight_decay = self.config.get("blink_train_weight_decay", 1e-4)
        self.blink_train_input_size = self.config.get("blink_train_input_size", 224)
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
        self.engine = AntEngine(
            learning_rate=self.train_lr,
            weight_decay=self.train_wd,
            num_classes=len(self.project.get_locator_scope()),
            device=self.runtime_device,
        )
        self.current_image = None
        self.inf_thread = None
        self.sam_thread = None
        self.sam_worker = None
        self.trainer = None
        self.locator_preload_thread = None
        self.parts_model_preload_thread = None
        try:
            autosave_seconds = int(float(self.config.get("project_autosave_interval_sec", 3)))
        except Exception:
            autosave_seconds = 3
        self.project_autosave_delay_ms = max(1, autosave_seconds) * 1000
        self.project_save_pending = False
        self.project_save_timer = QTimer(self)
        self.project_save_timer.setSingleShot(True)
        self.project_save_timer.timeout.connect(self._flush_pending_project_save)
        self.last_confirmed_locator_timestamp = None
        self.pending_training_preflight = None
        self.training_retry_requested = False

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
        self.btn_blink_entry = QPushButton()
        self.btn_blink_entry.clicked.connect(self.launch_blink_from_workbench)
        apply_semantic_button_style(self.btn_blink_entry, BUTTON_ROLE_NEUTRAL)
        self.btn_start_center_from_workbench = QPushButton()
        self.btn_start_center_from_workbench.setObjectName("workbenchStartCenterButton")
        self.btn_start_center_from_workbench.clicked.connect(self.return_to_start_center_with_context)
        apply_semantic_button_style(self.btn_start_center_from_workbench, BUTTON_ROLE_NEUTRAL)
        self.btn_agent_from_workbench = QPushButton()
        self.btn_agent_from_workbench.setObjectName("workbenchAskAgentButton")
        self.btn_agent_from_workbench.clicked.connect(lambda: self.open_agent_from_context(self._collect_image_workbench_agent_context()))
        apply_semantic_button_style(self.btn_agent_from_workbench, BUTTON_ROLE_NEUTRAL)

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

        self.toolbar_flow_panel = QWidget()
        apply_surface_role(self.toolbar_flow_panel, SURFACE_ROLE_SUBTLE, "workbenchToolbarFlowPanel")
        toolbar_flow_layout = QHBoxLayout(self.toolbar_flow_panel)
        toolbar_flow_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_flow_layout.setSpacing(8)
        toolbar_flow_layout.addWidget(self.btn_blink_entry)
        toolbar_flow_layout.addWidget(self.btn_start_center_from_workbench)
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
        self.file_list = QListWidget()
        self.file_list.setObjectName("imageList")
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_list_context_menu)
        self.file_list.currentItemChanged.connect(self.on_file_selected)
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
        self.radio_scale = QRadioButton()
        self.radio_scale.setObjectName("scaleToolRadio")
        self.radio_scale.toggled.connect(self.on_tool_changed)
        self.tool_group.addButton(self.radio_scale)
        self.radio_scale.setVisible(False) 
        tool_layout.addWidget(self.radio_scale)
        tool_layout.addStretch(1)
        enh_layout = QHBoxLayout()
        self.lbl_bright = QLabel("B:")
        self.lbl_bright.setObjectName("mutedLabel")
        enh_layout.addWidget(self.lbl_bright)
        self.slider_bright = QSlider(Qt.Horizontal)
        self.slider_bright.setRange(-100, 100)
        self.slider_bright.setValue(0)
        self.slider_bright.setFixedWidth(120)
        self.slider_bright.valueChanged.connect(self.on_enhancement_changed)
        enh_layout.addWidget(self.slider_bright)
        self.lbl_contrast = QLabel("C:")
        self.lbl_contrast.setObjectName("mutedLabel")
        enh_layout.addWidget(self.lbl_contrast)
        self.slider_contrast = QSlider(Qt.Horizontal)
        self.slider_contrast.setRange(1, 30)
        self.slider_contrast.setValue(10)
        self.slider_contrast.setFixedWidth(120)
        self.slider_contrast.valueChanged.connect(self.on_enhancement_changed)
        enh_layout.addWidget(self.slider_contrast)
        tool_layout.addLayout(enh_layout)
        center_layout.addWidget(self.tool_strip)

        self.canvas = AnnotationCanvas()
        self.canvas.setObjectName("annotationCanvas")
        self.canvas.polygon_completed.connect(self.on_polygon_completed)
        self.canvas.magic_wand_clicked.connect(self.on_magic_wand_clicked)
        self.canvas.magic_box_completed.connect(self.on_magic_box_completed)
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

        right_scroll = QScrollArea()
        right_scroll.setObjectName("workbenchInspectorScroll")
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        right_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
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
        metadata_layout.addWidget(self.label_taxonomy)
        self.genus_combo = NoWheelComboBox()
        self.genus_combo.setEditable(True)
        self.genus_combo.setInsertPolicy(QComboBox.InsertAlphabetically)
        self.genus_combo.currentTextChanged.connect(self.on_genus_changed)
        metadata_layout.addWidget(self.genus_combo)
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
        
        tax_btn_layout = QHBoxLayout()
        self.btn_add_part = QPushButton("+")
        self.btn_add_part.clicked.connect(self.add_taxonomy_part)
        apply_semantic_button_style(self.btn_add_part, BUTTON_ROLE_NEUTRAL, "font-weight: bold;")
        self.btn_del_part = QPushButton("-")
        self.btn_del_part.clicked.connect(self.remove_taxonomy_part)
        apply_semantic_button_style(self.btn_del_part, BUTTON_ROLE_DESTRUCTIVE, "font-weight: bold;")
        tax_btn_layout.addWidget(self.btn_add_part)
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
        self.label_description = QLabel()
        self.label_description.setObjectName("HeaderLabel")
        metadata_layout.addWidget(self.label_description)
        self.desc_box = QTextEdit()
        self.desc_box.setReadOnly(True)
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
        
        # --- Model Selection Area (Decoupled) ---
        self.ai_model_panel = QWidget()
        apply_surface_role(self.ai_model_panel, SURFACE_ROLE_SUBTLE, "workbenchAIModelPanel")
        models_form = QGridLayout(self.ai_model_panel)
        models_form.setContentsMargins(10, 10, 10, 10)
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
        models_form.addWidget(self.btn_del_locator, 0, 2)
        
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
        models_form.addWidget(self.btn_del_segmenter, 1, 2)
        
        ai_layout.addWidget(self.ai_model_panel)

        self.ai_action_panel = QWidget()
        apply_surface_role(self.ai_action_panel, SURFACE_ROLE_RAISED, "workbenchAIActionPanel")
        ai_action_layout = QVBoxLayout(self.ai_action_panel)
        ai_action_layout.setContentsMargins(10, 10, 10, 10)
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
        self.chk_train_locator_only = QCheckBox()
        self.chk_train_locator_only.setToolTip(
            tr(
                "Skip SAM/parts training for this run. Useful when the base SAM result is already good enough.",
                self.current_lang,
            )
        )
        ai_action_layout.addWidget(self.chk_train_locator_only)

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
        self.progress = QProgressBar()
        ai_action_layout.addWidget(self.progress)
        ai_layout.addWidget(self.ai_action_panel)
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
        right_scroll.setWidget(right_panel)
        self.workbench_splitter.addWidget(right_scroll)
        self.workbench_splitter.setStretchFactor(0, 1)
        self.workbench_splitter.setStretchFactor(1, 5)
        self.workbench_splitter.setStretchFactor(2, 2)
        self.workbench_splitter.setSizes([240, 1080, 320])

        self.pdf_widget = PdfProcessingWidget(self.current_lang)
        self.tif_workbench = TifWorkbenchWidget(self.tif_project, self.current_lang, config_manager=self.config)
        self.tif_workbench.start_center_requested.connect(self.return_to_start_center_with_context)
        self.tif_workbench.agent_requested.connect(self.open_agent_from_context)
        self.blink_lab = BlinkLabWidget(
            self.engine,
            self.project,
            self.current_lang,
            blink_epochs=self.blink_train_epochs,
            blink_batch=self.blink_train_batch,
            blink_lr=self.blink_train_lr,
            blink_weight_decay=self.blink_train_weight_decay,
            blink_input_size=self.blink_train_input_size,
            runtime_device=self.runtime_device,
        )
        self.blink_lab.start_center_requested.connect(self.return_to_start_center_with_context)
        self.blink_lab.agent_requested.connect(self.open_agent_from_context)
        self.blink_lab.global_labels_updated.connect(self.on_global_labels_updated)
        self.blink_lab.route_registry_refresh_requested.connect(self.refresh_route_table)
        self.route_settings_panel = RouteManagementPanel(self, self.current_lang)

        self.project.create_project(DEFAULT_PROJECT_NAME, ".", template_id=DEFAULT_PROJECT_TEMPLATE_ID)
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

        header = QWidget()
        apply_surface_role(header, SURFACE_ROLE_PANEL, "startCenterHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 14)
        header_layout.setSpacing(6)
        self.start_title = QLabel()
        self.start_title.setObjectName("startCenterTitle")
        self.start_subtitle = QLabel()
        self.start_subtitle.setObjectName("mutedLabel")
        self.start_subtitle.setWordWrap(True)
        header_layout.addWidget(self.start_title)
        header_layout.addWidget(self.start_subtitle)
        agent_layout.addWidget(header)

        self.agent_panel = TaxaMaskAgentPanel(self.current_lang)
        self.agent_panel.status_changed.connect(lambda _status: self._refresh_project_console())
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
        self.start_image_card = self._build_workflow_card(
            "start2DWorkflowCard",
            "2D / STL morphology annotation",
            "Annotate high-resolution 2D views rendered from STL, or ordinary 2D morphology images, then train Locator/SAM/Blink models.",
            "Enter 2D/STL workflow",
            self.enter_image_workflow,
            "Create 2D/STL project",
            self.new_project,
        )
        self.start_tif_card = self._build_workflow_card(
            "startTifWorkflowCard",
            "TIF volume annotation",
            "Annotate continuous slice volumes with material IDs, export train-ready volumes, and call TIF segmentation backends.",
            "Enter TIF workflow",
            self.enter_tif_workflow,
            "Create TIF project",
            self.new_tif_project,
        )
        rail_layout.addWidget(self.start_image_card)
        rail_layout.addWidget(self.start_tif_card)

        footer = QWidget()
        apply_surface_role(footer, SURFACE_ROLE_SUBTLE, "startCenterFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.setSpacing(8)
        self.start_recent_label = QLabel()
        self.start_recent_label.setObjectName("mutedLabel")
        self.start_recent_label.setWordWrap(True)
        self.btn_continue_last = QPushButton()
        self.btn_continue_last.clicked.connect(self.open_last_project)
        apply_semantic_button_style(self.btn_continue_last, BUTTON_ROLE_COMMIT)
        self.btn_open_any = QPushButton()
        self.btn_open_any.clicked.connect(self.open_project)
        apply_semantic_button_style(self.btn_open_any, BUTTON_ROLE_NEUTRAL)
        self.btn_general_settings = QPushButton()
        self.btn_general_settings.clicked.connect(self.open_general_settings)
        apply_semantic_button_style(self.btn_general_settings, BUTTON_ROLE_NEUTRAL)
        footer_layout.addWidget(self.start_recent_label)
        footer_layout.addWidget(self.btn_continue_last)
        footer_layout.addWidget(self.btn_open_any)
        footer_layout.addWidget(self.btn_general_settings)
        rail_layout.addWidget(footer)
        rail_layout.addStretch(1)
        workflow_rail_scroll.setWidget(workflow_rail)
        outer_layout.addWidget(workflow_rail_scroll, 0)
        return page

    def _build_project_console(self):
        panel = QWidget()
        apply_surface_role(panel, SURFACE_ROLE_SUBTLE, "startProjectConsole")
        panel.setMaximumHeight(230)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(5)

        self.start_console_title = QLabel()
        self.start_console_title.setObjectName("HeaderLabel")
        layout.addWidget(self.start_console_title)

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
        self.start_console_tif_label, self.start_console_tif_value = self._build_project_console_row(
            grid, 3, "startConsoleTifValue"
        )
        self.start_console_pdf_label, self.start_console_pdf_value = self._build_project_console_row(
            grid, 4, "startConsolePdfValue"
        )
        self.start_console_agent_label, self.start_console_agent_value = self._build_project_console_row(
            grid, 5, "startConsoleAgentValue"
        )
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self.start_console_stl_note = QLabel()
        self.start_console_stl_note.setObjectName("mutedLabel")
        self.start_console_stl_note.setWordWrap(True)
        layout.addWidget(self.start_console_stl_note)
        return panel

    def _build_project_console_row(self, grid, row, value_object_name):
        label = QLabel()
        label.setObjectName("mutedLabel")
        label.setMinimumWidth(92)
        value = QLabel()
        value.setObjectName(value_object_name)
        value.setProperty("consoleValue", True)
        value.setWordWrap(True)
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
            self.start_recent_label.setText(f"{tr('Continue last project', self.current_lang)}: {last_project}")
            self.btn_continue_last.setEnabled(True)
        else:
            self.start_recent_label.setText(tr("No recent project", self.current_lang))
            self.btn_continue_last.setEnabled(False)
        self.btn_continue_last.setText(tr("Continue last project", self.current_lang))
        self.btn_open_any.setText(tr("Open any project", self.current_lang))
        self.btn_general_settings.setText(tr("General Settings", self.current_lang))
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
            self._refresh_project_console()

    def _refresh_project_console(self):
        if not hasattr(self, "start_console_title"):
            return
        self.start_console_title.setText(tr("Project Console", self.current_lang))
        self.start_console_workflow_label.setText(tr("Current workflow", self.current_lang))
        self.start_console_project_label.setText(tr("Current project", self.current_lang))
        self.start_console_images_label.setText(tr("2D/STL images", self.current_lang))
        self.start_console_tif_label.setText(tr("TIF specimens", self.current_lang))
        self.start_console_pdf_label.setText(tr("PDF evidence", self.current_lang))
        self.start_console_agent_label.setText("Ant-Code")

        self.start_console_workflow_value.setText(self._agent_current_workflow_label())
        self.start_console_project_value.setText(self._start_console_project_summary())
        self.start_console_images_value.setText(self._start_console_image_summary())
        self.start_console_tif_value.setText(self._start_console_tif_summary())
        self.start_console_pdf_value.setText(self._start_console_pdf_summary())
        self.start_console_agent_value.setText(self._start_console_agent_status())
        self.start_console_project_value.setToolTip(self._agent_current_project_label())
        self.start_console_stl_note.setText(
            tr(
                "STL source stays as exported high-resolution 2D views; TaxaMask does not label 3D meshes.",
                self.current_lang,
            )
        )

    def _start_console_project_summary(self):
        kind = getattr(self, "active_project_kind", "start")
        source_kind = getattr(self, "active_project_source_kind", kind)
        if kind == "tif":
            path = getattr(self.tif_project, "current_project_path", "") or ""
            return tr("TIF project: {0}", self.current_lang).format(self._compact_project_path(path)) if path else tr("No active project", self.current_lang)
        if kind == "image":
            path = self._active_recent_project_path() or getattr(self.project, "current_project_path", "") or ""
            if source_kind == "stl":
                return tr("STL rendered-view project: {0}", self.current_lang).format(self._compact_project_path(path)) if path else tr("No active project", self.current_lang)
            return tr("2D project: {0}", self.current_lang).format(self._compact_project_path(path)) if path else tr("No active project", self.current_lang)

        last_project = self.config.get("last_project_path", "") or ""
        if last_project:
            return tr("Recent project: {0}", self.current_lang).format(self._compact_project_path(last_project))
        return tr("Repository only; no research project selected", self.current_lang)

    def _compact_project_path(self, path):
        text = str(path or "").strip()
        if not text:
            return ""
        name = os.path.basename(os.path.normpath(text))
        parent = os.path.basename(os.path.dirname(os.path.normpath(text)))
        return f"{parent}/{name}" if parent else name

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
        return tr("{0} image(s), {1} labeled, {2} STL rendered 2D view(s)", self.current_lang).format(
            len(images),
            labeled_count,
            stl_count,
        )

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
        return tr("{0} specimen(s), {1} train-ready, {2} with manual_truth", self.current_lang).format(
            len(specimens),
            train_ready_count,
            manual_truth_count,
        )

    def _start_console_pdf_summary(self):
        skill_path = os.path.join(REPO_ROOT, ".lab-agent", "skills", "taxamask-pdf-evidence", "SKILL.md")
        if not os.path.exists(skill_path):
            return tr("PDF evidence skill missing", self.current_lang)
        candidates = 0
        for image_path in (self.project.project_data or {}).get("images", []):
            provenance = self.project.get_image_provenance(image_path)
            if provenance.get("source_type") == "pdf_candidate":
                entry = (self.project.project_data or {}).get("labels", {}).get(image_path, {})
                if not isinstance(entry, dict) or entry.get("status") != "labeled":
                    candidates += 1
        return tr("PDF evidence skill ready; {0} review candidate(s)", self.current_lang).format(candidates)

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

    AGENT_CONTEXT_TEXT_LIMIT = 320
    AGENT_CONTEXT_LOG_LINES = 6
    AGENT_CONTEXT_LOG_LINE_LIMIT = 160
    AGENT_CONTEXT_TOTAL_LIMIT = 1800

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
        allowed_keys = (
            "source_workbench",
            "project_type",
            "project_source_kind",
            "project_path",
            "review_project_path",
            "active_specimen_id",
            "active_image_path",
            "active_label_role",
            "selected_part",
            "selected_material_id",
            "recent_log_excerpt",
        )
        compact = {}
        for key in allowed_keys:
            value = (context or {}).get(key)
            if not value:
                continue
            limit = self.AGENT_CONTEXT_TEXT_LIMIT
            if key == "recent_log_excerpt":
                limit = self.AGENT_CONTEXT_LOG_LINES * self.AGENT_CONTEXT_LOG_LINE_LIMIT
            compact[key] = self._agent_context_text(value, limit)
        compact["context_policy"] = (
            "Only compact field indexes are provided. Do not assume full project data is loaded; "
            "read specific files only when needed."
        )
        text_budget = 0
        limited = {}
        for key, value in compact.items():
            text = str(value)
            next_budget = text_budget + len(key) + len(text)
            if next_budget > self.AGENT_CONTEXT_TOTAL_LIMIT and key != "context_policy":
                limited[key] = self._agent_context_text(text, max(80, self.AGENT_CONTEXT_TOTAL_LIMIT - text_budget - len(key)))
                break
            limited[key] = value
            text_budget = next_budget
        return limited

    def _collect_image_workbench_agent_context(self):
        return {
            "source_workbench": "labeling",
            "project_type": "2d_stl",
            "project_source_kind": getattr(self, "active_project_source_kind", "image"),
            "project_path": self._active_recent_project_path() or getattr(self.project, "current_project_path", "") or "",
            "review_project_path": getattr(self.project, "current_project_path", "") or "",
            "active_image_path": self.current_image or "",
            "selected_part": self._current_part_name() or "",
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

    def open_agent_from_context(self, context=None):
        payload = dict(context or {})
        if not payload and hasattr(self, "tabs") and self.tabs.currentWidget() is self.blink_lab:
            payload = self._collect_blink_agent_context()
        if not payload and hasattr(self, "tabs") and self.tabs.currentWidget() is self.tif_workbench:
            payload = self.tif_workbench.get_agent_context()
        if not payload:
            payload = self._collect_image_workbench_agent_context()
        payload = self._compact_agent_context(payload)
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

    def return_to_start_center_with_context(self):
        self._show_start_center()

    def _open_workflow_from_agent(self, workflow):
        if workflow == "tif":
            self.enter_tif_workflow()
            return
        self.enter_image_workflow()

    def _open_model_settings_from_agent(self, workflow):
        if workflow == "tif":
            self.open_tif_model_settings()
            return
        self.open_stl_model_settings()

    def enter_image_workflow(self):
        self.active_project_kind = "image"
        self._refresh_project_bound_views()
        self.tabs.setCurrentWidget(self.workbench_widget)
        self.ensure_2d_stl_models_preloaded()
        self.log(tr("Opened 2D/STL workflow.", self.current_lang))

    def enter_tif_workflow(self):
        self.active_project_kind = "tif"
        self._refresh_project_bound_views()
        self.tabs.setCurrentWidget(self.tif_workbench)
        self.log(tr("Opened TIF volume workflow.", self.current_lang))

    def open_last_project(self):
        last_project = self.config.get("last_project_path", "")
        if not last_project or not os.path.exists(last_project):
            return
        self.open_project_path(last_project)

    def closeEvent(self, event):
        self._shutdown_background_workers()
        self._flush_pending_project_save()
        recent_project_path = self._active_recent_project_path()
        if recent_project_path:
            self.config.set("last_project_path", recent_project_path)
        self.config.save()
        event.accept()
        os._exit(0)

    def _active_recent_project_path(self):
        active_kind = getattr(self, "active_project_kind", "start")
        source_kind = getattr(self, "active_project_source_kind", active_kind)
        if active_kind == "tif":
            return getattr(self.tif_project, "current_project_path", None) or ""
        if active_kind == "image":
            if source_kind == "stl":
                return getattr(self.stl_project, "current_project_path", None) or getattr(self, "active_project_entry_path", "")
            return getattr(self.project, "current_project_path", None) or getattr(self, "active_project_entry_path", "")
        return ""

    def _shutdown_background_workers(self):
        agent_panel = getattr(self, "agent_panel", None)
        if agent_panel is not None and hasattr(agent_panel, "stop_dashboard"):
            try:
                agent_panel.stop_dashboard()
            except Exception:
                pass
        if self.sam_thread and self.sam_thread.isRunning():
            self.sam_thread.quit()
            self.sam_thread.wait(1000)
        thread = getattr(self, "parts_model_preload_thread", None)
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def destroy(self, destroyWindow=True, destroySubWindows=True):
        self._shutdown_background_workers()
        return super().destroy(destroyWindow, destroySubWindows)

    def _schedule_project_save(self):
        self.project_save_pending = True
        self.project_save_timer.start(self.project_autosave_delay_ms)

    def _flush_pending_project_save(self, force=False):
        if self.project_save_timer.isActive():
            self.project_save_timer.stop()

        if not self.project.current_project_path:
            self.project_save_pending = False
            return False

        if not force and not self.project_save_pending:
            return False

        self.project.save_project()
        self.project_save_pending = False
        return True

    def refresh_model_list(self):
        current_locator = self.combo_locator.currentData() if self.combo_locator.count() else None
        current_segmenter = self.combo_segmenter.currentData() if self.combo_segmenter.count() else None
        self.combo_locator.blockSignals(True)
        self.combo_segmenter.blockSignals(True)
        self.combo_locator.clear()
        self.combo_segmenter.clear()
        
        if not self.engine:
            return
            
        import glob
        # 1. Populate Locators
        loc_files = glob.glob(os.path.join(self.engine.weights_dir, "locator_*.pth"))
        # Format: "20260105_1105"
        loc_timestamps = sorted([os.path.basename(f).replace("locator_", "").replace(".pth", "") for f in loc_files], reverse=True)
        
        if loc_timestamps:
            for ts in loc_timestamps:
                self.combo_locator.addItem(self._build_locator_combo_label(ts), ts)
            locator_index = self.combo_locator.findData(current_locator)
            if locator_index < 0:
                locator_index = 0
            self.combo_locator.setCurrentIndex(locator_index)
        else:
            self.combo_locator.addItem(tr("No Locators Found", self.current_lang), "__no_locator__")
            
        # 2. Populate Segmenters
        self.combo_segmenter.addItem(tr("Base SAM (Original)", self.current_lang), "BASE_SAM")
        
        seg_files = glob.glob(os.path.join(self.engine.weights_dir, "sam_decoder_lora_*.pth"))
        seg_timestamps = sorted([os.path.basename(f).replace("sam_decoder_lora_", "").replace(".pth", "") for f in seg_files], reverse=True)
        
        if seg_timestamps:
            for ts in seg_timestamps:
                self.combo_segmenter.addItem(ts, ts)
            
        # Default to Base SAM (Index 0) for safety/compatibility, or latest if user prefers?
        # User strategy: "配合原始的sam模型，先达到一个很好的效果". So default to Base SAM.
        segmenter_index = self.combo_segmenter.findData(current_segmenter)
        if segmenter_index < 0:
            segmenter_index = 0
        self.combo_segmenter.setCurrentIndex(segmenter_index)
        
        self.combo_locator.blockSignals(False)
        self.combo_segmenter.blockSignals(False)
        if getattr(self, "active_project_kind", "start") == "image":
            self._apply_locator_selection_to_runtime()
            self._apply_segmenter_selection_to_runtime()
        self.update_model_delete_button_states()

    def _selected_locator_timestamp(self):
        item_data = self.combo_locator.currentData() if self.combo_locator.count() else None
        if item_data in (None, "", "__no_locator__"):
            return None
        return str(item_data)

    def _selected_locator_display_text(self):
        if not self.combo_locator.count():
            return ""
        return str(self.combo_locator.currentText() or "").strip()

    def _build_locator_combo_label(self, timestamp):
        ts = str(timestamp or "").strip()
        if not ts:
            return ts

        path = self._locator_model_path(ts)
        if not path or not os.path.exists(path):
            return ts

        try:
            saved_state = torch.load(path, map_location="cpu")
        except Exception:
            return ts

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

        if saved_resolution is None:
            state_label = "legacy-512"
        else:
            try:
                size_pair = (max(1, int(saved_resolution[0])), max(1, int(saved_resolution[1])))
            except Exception:
                size_pair = (512, 512)
            state_label = f"exact {format_size_pair(size_pair)}"
        return f"{ts} [{state_label}]"

    def _selected_segmenter_timestamp(self):
        item_data = self.combo_segmenter.currentData() if self.combo_segmenter.count() else None
        if item_data in (None, "", "BASE_SAM", "No Segmenters Found"):
            return None
        return str(item_data)

    def _active_project_route_manifest(self):
        return self.project.get_cascade_routes()

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

    def update_route_action_buttons(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is not None:
            panel.update_action_buttons()

    def _refresh_project_bound_views(self):
        self._apply_project_mode_tabs()
        if getattr(self, "active_project_kind", "image") == "start":
            self._update_start_center_texts()
            if hasattr(self, "tabs"):
                self.tabs.setCurrentWidget(self.start_center_widget)
            return
        if getattr(self, "active_project_kind", "image") == "tif":
            if hasattr(self, "tif_workbench"):
                self.tif_workbench.refresh_project()
            if hasattr(self, "tabs"):
                self.tabs.setCurrentWidget(self.tif_workbench)
            return
        self.refresh_file_list()
        self.refresh_ui()
        self.refresh_route_table()

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
            for widget in (self.workbench_widget, self.blink_lab, self.tif_workbench, self.pdf_widget):
                self._remove_tab_if_present(widget)
            self._ensure_tab_visible(self.start_center_widget, tr("Start Center", self.current_lang))
            self.tabs.setCurrentWidget(self.start_center_widget)
            return
        if getattr(self, "active_project_kind", "image") == "tif":
            self._remove_tab_if_present(self.start_center_widget)
            self._remove_tab_if_present(self.workbench_widget)
            self._remove_tab_if_present(self.blink_lab)
            self._remove_tab_if_present(self.pdf_widget)
            self._ensure_tab_visible(self.tif_workbench, tr("TIF Volume Workbench", self.current_lang))
            self.tabs.setCurrentWidget(self.tif_workbench)
            return
        self._remove_tab_if_present(self.start_center_widget)
        self._remove_tab_if_present(self.tif_workbench)
        self._ensure_tab_visible(self.workbench_widget, tr("Labeling Workbench", self.current_lang))
        self._ensure_tab_visible(self.blink_lab, tr("Blink Workbench", self.current_lang))
        if self.tabs.currentWidget() is None or self.tabs.currentWidget() is self.tif_workbench:
            self.tabs.setCurrentWidget(self.workbench_widget)

    def _is_tif_project_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return False
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

    def appoint_selected_route_expert(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is not None:
            panel.appoint_selected_route_expert()

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
        if block_reasons:
            block_text = ", ".join(f"{part}={reason}" for part, reason in sorted(block_reasons.items()))
            self.log(ui_text("Route blocks: {0}", self.current_lang).format(block_text))

    def _locator_model_path(self, timestamp):
        if not self.engine or not timestamp:
            return None
        return os.path.join(self.engine.weights_dir, f"locator_{timestamp}.pth")

    def _segmenter_model_path(self, timestamp):
        if not self.engine or not timestamp:
            return None
        return os.path.join(self.engine.weights_dir, f"sam_decoder_lora_{timestamp}.pth")

    def _apply_locator_selection_to_runtime(self, *, log_change=False):
        if not self.engine:
            return

        ts = self._selected_locator_timestamp()
        if not ts:
            if self.engine.locator is None:
                self.engine.ensure_locator_loaded()
            else:
                self.engine.reset_locator_to_base()
            if log_change:
                self.log(tr("Locator reset to base (untrained).", self.current_lang))
            return

        self.engine.load_locator(ts)
        if log_change:
            locator_label = self._selected_locator_display_text() or ts
            self.log(tr("Locator switched to: {0}", self.current_lang).format(locator_label))

    def _locator_selection_needs_legacy_confirmation(self):
        return bool(getattr(self.engine, "loaded_locator_requires_legacy_confirmation", False))

    def _confirm_legacy_locator_selection_if_needed(self):
        if not self.engine or not self._locator_selection_needs_legacy_confirmation():
            return True

        reply = themed_yes_no_question(
            self,
            tr("Legacy Locator Confirmation", self.current_lang),
            tr(
                "The selected locator checkpoint does not store its training resolution. It will be treated as a legacy 512px locator only if you confirm.",
                self.current_lang,
            ),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        if reply == QMessageBox.Yes:
            self.engine.loaded_locator_requires_legacy_confirmation = False
            self.last_confirmed_locator_timestamp = self._selected_locator_timestamp()
            return True

        self.log("Legacy locator selection was cancelled.")
        return False

    def _show_structured_training_preflight(self, preflight):
        dialog = TrainingPreflightDialog(preflight, self, self.current_lang)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        return bool(dialog.accepted_training())

    def _is_locator_oom_error(self, exc):
        message = str(exc or "").lower()
        return "out of memory" in message or "cuda out of memory" in message

    def _ask_locator_oom_retry_resolution(self, current_resolution, lower_options):
        if not lower_options:
            QMessageBox.warning(
                self,
                tr("Training Retry", self.current_lang),
                tr("No lower locator resolutions are available for retry.", self.current_lang),
            )
            return None

        options_text = ", ".join(format_size_pair(value) for value in lower_options)
        message = tr(
            "Locator stage ran out of memory at {0}. You can retry with a lower locator size: {1}",
            self.current_lang,
        ).format(format_size_pair(current_resolution), options_text)

        selected_text, ok = QInputDialog.getItem(
            self,
            tr("Training Retry", self.current_lang),
            message,
            [format_size_pair(value) for value in lower_options],
            0,
            False,
        )
        if not ok or not selected_text:
            return None

        for candidate in lower_options:
            if format_size_pair(candidate) == str(selected_text).strip():
                return tuple(candidate)
        return None

    def _launch_training_with_preflight(self, preflight, tax, locator_scope, train_segmenter=True):
        active_preflight = dict(preflight or {})
        self.pending_training_preflight = {
            "preflight": active_preflight,
            "taxonomy": list(tax or []),
            "locator_scope": list(locator_scope or []),
            "train_segmenter": bool(train_segmenter),
        }
        self.training_retry_requested = False

        self.engine.locator_resolution = tuple(active_preflight.get("selected_locator_size") or (512, 512))
        self.trainer = TrainingThread(
            self.engine,
            active_preflight,
            tax,
            locator_scope,
            self.train_epochs,
            self.train_batch,
            lang=self.current_lang,
            train_segmenter=train_segmenter,
        )
        self.trainer.log_signal.connect(self.log)
        self.trainer.progress_signal.connect(self.progress.setValue)
        self.trainer.report_signal.connect(self.show_training_report)
        self.trainer.success_signal.connect(self._on_training_success)
        self.trainer.error_signal.connect(self._on_training_error)
        self.trainer.finished_signal.connect(self._on_training_finished)
        self.btn_train.setEnabled(False)
        self.btn_stop_training.setEnabled(True)
        self.progress.setValue(0)
        self.trainer.start()

    def _on_training_success(self):
        self.refresh_model_list()

    def _on_training_finished(self):
        self.btn_train.setEnabled(False if self.training_retry_requested else True)
        self.btn_stop_training.setEnabled(False)
        if not self.training_retry_requested:
            self.refresh_model_list()

    def _on_training_error(self, payload):
        payload = dict(payload or {})
        error_type = payload.get("type")
        self.training_retry_requested = False

        if error_type == "oom" and payload.get("stage") == "locator":
            retry_resolution = self._ask_locator_oom_retry_resolution(
                payload.get("current_resolution") or 512,
                payload.get("lower_options", []),
            )
            if retry_resolution is not None and self.pending_training_preflight:
                self.training_retry_requested = True
                updated_preflight = dict(self.pending_training_preflight.get("preflight") or {})
                updated_preflight["selected_locator_size"] = tuple(retry_resolution)
                updated_preflight["lower_locator_size_options"] = [
                    tuple(value)
                    for value in updated_preflight.get("lower_locator_size_options", [])
                    if tuple(value) != tuple(retry_resolution)
                ]
                self.pending_training_preflight["preflight"] = updated_preflight
                QTimer.singleShot(
                    0,
                    lambda: self._launch_training_with_preflight(
                        updated_preflight,
                        self.pending_training_preflight.get("taxonomy", []),
                        self.pending_training_preflight.get("locator_scope", []),
                        self.pending_training_preflight.get("train_segmenter", True),
                    ),
                )
                return

        message = str(payload.get("message") or "Training failed.")
        self.log(tr("Training aborted: {0}", self.current_lang).format(message))
        QMessageBox.critical(self, tr("Error", self.current_lang), message)

    def stop_training(self):
        if self.trainer and self.trainer.isRunning():
            self.trainer.requestInterruption()
            self.btn_stop_training.setEnabled(False)
            self.log(tr("Stopping training after the current epoch/batch...", self.current_lang))

    def _apply_segmenter_selection_to_runtime(self, *, log_change=False):
        if not self.engine:
            return

        ts = self._selected_segmenter_timestamp()
        if not ts:
            if self.engine.parts_model is not None:
                self.engine.reset_sam_to_base()
            if self.sam_worker:
                self.sam_worker.reload_base_model()
            if log_change:
                self.log(tr("Segmenter switched to: Base SAM (Original)", self.current_lang))
            return

        self.engine.load_sam_decoder(ts)
        if self.sam_worker:
            weights_path = self._segmenter_model_path(ts)
            if weights_path:
                self.sam_worker.load_decoder_weights(weights_path)
        if log_change:
            self.log(tr("Segmenter switched to: Fine-tuned {0}", self.current_lang).format(ts))

    def update_model_delete_button_states(self, *_):
        locator_ts = self._selected_locator_timestamp()
        locator_path = self._locator_model_path(locator_ts)
        self.btn_del_locator.setEnabled(bool(locator_path and os.path.exists(locator_path)))

        segmenter_ts = self._selected_segmenter_timestamp()
        segmenter_path = self._segmenter_model_path(segmenter_ts)
        self.btn_del_segmenter.setEnabled(bool(segmenter_path and os.path.exists(segmenter_path)))

    def on_locator_changed(self, index):
        if getattr(self, "active_project_kind", "start") != "image" or getattr(self.engine, "locator", None) is None:
            self.update_model_delete_button_states()
            return
        self._apply_locator_selection_to_runtime(log_change=False)
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
                    self._apply_locator_selection_to_runtime(log_change=False)
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
                    self.log(f"Deleted locator: {ts}")
                    self.refresh_model_list()
                else:
                    self.log(f"File not found: {p}")
                    self.update_model_delete_button_states()
            except Exception as e:
                self.log(f"Error deleting model: {e}")
                self.update_model_delete_button_states()

    def on_segmenter_changed(self, index):
        self._apply_segmenter_selection_to_runtime(log_change=True)
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

    def create_menus(self):
        menubar = self.menuBar()
        menubar.clear()
        file_menu = menubar.addMenu(tr("File", self.current_lang))
        file_menu.addAction(tr("Start Center", self.current_lang), self._show_start_center)
        file_menu.addAction(tr("New Project", self.current_lang), self.new_project)
        file_menu.addAction(tr("New TIF Volume Project", self.current_lang), self.new_tif_project)
        file_menu.addAction(tr("Open Project", self.current_lang), self.open_project)
        file_menu.addAction(tr("Save Project", self.current_lang), lambda: self._flush_pending_project_save(force=True))
        file_menu.addAction(tr("Import STL Rendered Views to Labeling Workbench", self.current_lang), self.import_stl_rendered_views_action)
        file_menu.addAction(tr("Open PDF Evidence Tools", self.current_lang), self.open_pdf_evidence_tools)
        file_menu.addAction(tr("Check / Relocate Project Images", self.current_lang), self.check_relocate_project_images)
        file_menu.addAction(tr("Export Dataset", self.current_lang), self.export_dataset)
        workflow_menu = menubar.addMenu(tr("Workflow", self.current_lang))
        workflow_menu.addAction(tr("2D/STL Morphology Workflow", self.current_lang), self.enter_image_workflow)
        workflow_menu.addAction(tr("TIF Volume Workflow", self.current_lang), self.enter_tif_workflow)
        workflow_menu.addAction(tr("Create 2D/STL project", self.current_lang), self.new_project)
        workflow_menu.addAction(tr("Create TIF project", self.current_lang), self.new_tif_project)
        workflow_menu.addAction(tr("Import STL Rendered Views to Labeling Workbench", self.current_lang), self.import_stl_rendered_views_action)
        settings_menu = menubar.addMenu(tr("Settings", self.current_lang))
        settings_menu.addAction(tr("General Settings", self.current_lang), self.open_general_settings)
        settings_menu.addAction(tr("2D/STL Model Settings", self.current_lang), self.open_stl_model_settings)
        settings_menu.addAction(tr("TIF Volume Model Settings", self.current_lang), self.open_tif_model_settings)

    def new_project(self):
        d = QFileDialog.getExistingDirectory(self, tr("New Project Directory", self.current_lang))
        if d:
            name, ok = QInputDialog.getText(self, tr("New Project", self.current_lang), tr("Project Name:", self.current_lang))
            if ok and name:
                template = self._choose_project_template()
                if template is None:
                    return
                self._flush_pending_project_save()
                self.project.create_project(name, d, template_id=template["template_id"])
                self.active_project_kind = "image"
                self.active_project_source_kind = "image"
                self.active_project_entry_path = self.project.current_project_path or ""
                self.config.set("last_project_path", self.active_project_entry_path)
                self._refresh_project_bound_views()
                self.ensure_2d_stl_models_preloaded()
                self.canvas.load_image("") 

    def new_tif_project(self):
        d = QFileDialog.getExistingDirectory(self, tr("New TIF Project Directory", self.current_lang))
        if not d:
            return
        name, ok = QInputDialog.getText(self, tr("New TIF Volume Project", self.current_lang), tr("Project Name:", self.current_lang))
        if not ok or not name:
            return
        self._flush_pending_project_save()
        self.tif_project.create_project(name, d)
        self.active_project_kind = "tif"
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
        source_dir = QFileDialog.getExistingDirectory(self, tr("Import AMIRA Directory", self.current_lang))
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
        source_dir = QFileDialog.getExistingDirectory(self, tr("Import STL Rendered Views to Labeling Workbench", self.current_lang))
        if not source_dir:
            return
        try:
            result = import_stl_rendered_views_into_2d_project(self.project, source_dir)
        except Exception as exc:
            QMessageBox.critical(self, tr("Import STL Rendered Views to Labeling Workbench", self.current_lang), str(exc))
            return
        self.active_project_kind = "image"
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
        index = self.tabs.indexOf(self.pdf_widget)
        if index < 0:
            index = self.tabs.addTab(self.pdf_widget, tr("PDF Evidence Tools", self.current_lang))
        self.tabs.setCurrentIndex(index)

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
        f, _ = QFileDialog.getOpenFileName(self, tr("Open Project", self.current_lang), "", "JSON (*.json)")
        if f:
            self.open_project_path(f)

    def open_project_path(self, path):
        f = os.path.abspath(str(path))
        self._flush_pending_project_save()
        if self._is_tif_project_file(f):
            self.tif_project.load_project(f)
            self.active_project_kind = "tif"
            self.active_project_source_kind = "tif"
            self.active_project_entry_path = f
            self.config.set("last_project_path", f)
            self.log(tr("Opened TIF volume project: {0}", self.current_lang).format(f))
        elif self._is_stl_project_file(f):
            self.stl_project.load_project(f)
            result = register_stl_rendered_views_for_2d_review(self.stl_project, self.project)
            self.active_project_kind = "image"
            self.active_project_source_kind = "stl"
            self.active_project_entry_path = f
            self.config.set("last_project_path", f)
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
            self.active_project_source_kind = "image"
            self.active_project_entry_path = f
            self.config.set("last_project_path", f)
        self._refresh_project_bound_views()
        if getattr(self, "active_project_kind", "image") == "image":
            self.ensure_2d_stl_models_preloaded()
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

        self._flush_pending_project_save()
        changed = self.project.apply_image_path_remap(matches, save=True)
        self.refresh_file_list()
        if self.current_image and not os.path.exists(self.current_image):
            self.current_image = None
            self.canvas.load_image("")
        result = tr("Remapped {0} project image path(s).", self.current_lang).format(changed)
        self.log(result)
        QMessageBox.information(self, tr("Project Image Health", self.current_lang), result)

    def _part_item_name(self, item):
        if item is None:
            return None
        part_name = item.data(0, Qt.UserRole)
        clean_name = str(part_name or "").strip()
        return clean_name or None

    def _current_part_name(self):
        return self._part_item_name(self.part_list.currentItem())

    def _append_part_tree_item(self, parent_item, text, part_name=None, tooltip=None):
        item = QTreeWidgetItem(parent_item) if parent_item is not None else QTreeWidgetItem(self.part_list)
        item.setText(0, text)
        item.setData(0, Qt.UserRole, part_name)
        if tooltip:
            item.setToolTip(0, tooltip)
        return item

    def _select_part_in_tree(self, part_name):
        clean_name = str(part_name or "").strip()
        if not clean_name:
            return False

        def walk(item):
            if item is None:
                return None
            if self._part_item_name(item) == clean_name:
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None

        for index in range(self.part_list.topLevelItemCount()):
            found_item = walk(self.part_list.topLevelItem(index))
            if found_item is not None:
                self.part_list.setCurrentItem(found_item)
                return True
        return False

    def _first_selectable_part_item(self):
        def walk(item):
            if item is None:
                return None
            if self._part_item_name(item):
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None

        for index in range(self.part_list.topLevelItemCount()):
            found_item = walk(self.part_list.topLevelItem(index))
            if found_item is not None:
                return found_item
        return None

    def _refresh_part_tree(self, selected_part=None):
        if getattr(self, "_refreshing_part_tree", False):
            return
        if not hasattr(self, "part_list"):
            return
        self._refreshing_part_tree = True
        previous_selection = selected_part or self._current_part_name()
        try:
            self.part_list.blockSignals(True)
            self.part_list.clear()
            groups = build_part_tree_groups(
                self.project.project_data.get("taxonomy", []),
                self.project.get_locator_scope(),
                self.project.iter_cascade_routes(),
            )

            for parent_group in groups.get("parents", []):
                parent_part = parent_group.get("part")
                if not parent_part:
                    continue
                parent_item = self._append_part_tree_item(
                    None,
                    tr(parent_part, self.current_lang),
                    part_name=parent_part,
                    tooltip=tr("Main locator parts", self.current_lang),
                )
                for child_part in parent_group.get("children", []):
                    self._append_part_tree_item(
                        parent_item,
                        tr(child_part, self.current_lang),
                        part_name=child_part,
                        tooltip=tr("Blink child parts", self.current_lang),
                    )
                parent_item.setExpanded(True)

            cross_region = groups.get("cross_region", [])
            if cross_region:
                group_item = self._append_part_tree_item(
                    None,
                    tr("Cross-region structures", self.current_lang),
                    tooltip=tr("Structure group", self.current_lang),
                )
                for part_name in cross_region:
                    self._append_part_tree_item(group_item, tr(part_name, self.current_lang), part_name=part_name)
                group_item.setExpanded(True)

            ungrouped = groups.get("ungrouped", [])
            if ungrouped:
                group_item = self._append_part_tree_item(
                    None,
                    tr("Ungrouped structures", self.current_lang),
                    tooltip=tr("Structure group", self.current_lang),
                )
                for part_name in ungrouped:
                    self._append_part_tree_item(group_item, tr(part_name, self.current_lang), part_name=part_name)
                group_item.setExpanded(True)

            selected = self._select_part_in_tree(previous_selection)
            if not selected:
                first_part_item = self._first_selectable_part_item()
                if first_part_item is not None:
                    self.part_list.setCurrentItem(first_part_item)
        finally:
            self.part_list.blockSignals(False)
            self._refreshing_part_tree = False

        current_part = self._current_part_name()
        if current_part:
            self.canvas.set_active_part(current_part)
            self.update_db_description(current_part)
        else:
            self.canvas.set_active_part(None)
            self.desc_box.clear()

    def add_taxonomy_part(self):
        name, ok = QInputDialog.getText(self, tr("Add Structure", self.current_lang), tr("Structure Name:", self.current_lang))
        if ok and name:
            if self.project.add_taxonomy_part(name.strip()):
                self.refresh_ui()
                self.project.save_project()
            else:
                QMessageBox.warning(self, tr("Error", self.current_lang), tr("Exists.", self.current_lang))

    def remove_taxonomy_part(self):
        part_name = self._current_part_name()
        if not part_name:
            return
        if themed_yes_no_question(
            self,
            tr("Remove Structure", self.current_lang),
            tr("Delete '{0}'?", self.current_lang).format(part_name),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        ) == QMessageBox.Yes:
            if self.project.remove_taxonomy_part(part_name):
                self.refresh_ui()
                self.project.save_project()

    def clear_ai_labels(self):
        if themed_yes_no_question(
            self,
            tr("Clear AI Labels", self.current_lang),
            tr("Clear all AI labels from the current project?", self.current_lang),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        ) == QMessageBox.Yes:
            c = self.project.remove_auto_labels()
            self.refresh_file_list()
            if self.current_image:
                self.canvas.set_polygons(self.project.get_labels(self.current_image))
            self.log(f"Removed {c} AI labels.")

    def on_global_labels_updated(self):
        """Called when Blink Workbench applies changes back to the global project."""
        if self.current_image:
            self.canvas.set_polygons(self.project.get_labels(self.current_image))
            self.canvas.set_boxes(
                self.project.get_boxes(self.current_image), 
                self.project.get_auto_boxes(self.current_image)
            )
        self.log(tr("Global labels updated from Blink Workbench.", self.current_lang))

    def refresh_ui(self):
        if self.engine:
            current_locator_scope = self.project.get_locator_scope()
            curr_scope_len = len(current_locator_scope)
        if curr_scope_len != self.engine.current_num_classes:
                self.log(
                    tr("Syncing Locator Scope ({0} -> {1})...", self.current_lang).format(
                        self.engine.current_num_classes, curr_scope_len
                    )
                )
                if self.engine.locator is not None:
                    self.engine.rebuild_locator(curr_scope_len, self.train_lr, self.train_wd)
                else:
                    self.engine.current_num_classes = curr_scope_len
                    self.engine.loaded_locator_timestamp = None
                    self.engine.loaded_locator_requires_legacy_confirmation = False
                    self.engine.loaded_locator_is_legacy_512 = False
                # FIX: Do NOT auto-load weights here as they might mismatch dimensions.
                self.log(tr("Locator scope changed. Please retrain or select a matching model.", self.current_lang))
                self.refresh_model_list()
        self.setWindowTitle(f"{WORKBENCH_WINDOW_TITLE} ({self.current_lang.upper()})")
        self.create_menus()
        self.btn_export.setText(tr("Export Dataset", self.current_lang))
        self.btn_crop.setText(tr("Import & Crop", self.current_lang))
        self.btn_add.setText(tr("+ Add Images", self.current_lang))
        self.label_project_images.setText(tr("PROJECT IMAGES", self.current_lang))
        self.label_taxonomy.setText(tr("Taxon", self.current_lang))
        self.label_structures.setText(tr("Structures", self.current_lang))
        self.label_ai_workflow.setText(tr("AI WORKFLOW", self.current_lang))
        backend_label = tr("Built-in Locator + SAM", self.current_lang)
        if self.model_backend == EXTERNAL_BACKEND_ID:
            backend_label = self.external_backend_config.get("display_name") or tr("External Script Backend", self.current_lang)
        self.label_model_backend.setText(f"{tr('Model Backend:', self.current_lang)} {backend_label}")
        self.btn_predict.setText(tr("Auto (Current)", self.current_lang))
        self.btn_batch.setText(tr("Batch (All)", self.current_lang))
        self.chk_train_locator_only.setText(tr("Train Locator only (skip SAM)", self.current_lang))
        self.chk_train_locator_only.setToolTip(
            tr(
                "Skip SAM/parts training for this run. Useful when the base SAM result is already good enough.",
                self.current_lang,
            )
        )
        self.btn_train.setText(tr("Train Models", self.current_lang))
        self.btn_stop_training.setText(tr("Stop Training", self.current_lang))
        self.btn_clear_ai.setText(tr("Clear AI Labels", self.current_lang))
        self.btn_blink_entry.setText(tr("Open in Blink Workbench", self.current_lang))
        self.btn_start_center_from_workbench.setText(tr("Start Center", self.current_lang))
        self.btn_agent_from_workbench.setText(tr("Ask Agent", self.current_lang))
        self.label_logs.setText(tr("LOGS", self.current_lang))
        self.radio_draw.setText(tr("Manual Draw", self.current_lang))
        self.radio_magic.setText(tr("Magic Wand (SAM)", self.current_lang))
        self.radio_box.setText(tr("Box Prompt (SAM)", self.current_lang))
        self.radio_scale.setText(tr("Scale Tool", self.current_lang))
        self.lbl_bright.setText(tr("B:", self.current_lang))
        self.lbl_contrast.setText(tr("C:", self.current_lang))
        self.check_morpho.setText(tr("Enable Morphometrics", self.current_lang))
        self.group_morpho.setTitle(tr("Measurements", self.current_lang))
        self.lbl_locator.setText(tr("Locator:", self.current_lang))
        self.lbl_segmenter.setText(tr("Segmenter:", self.current_lang))
        self.btn_del_locator.setText(tr("Del", self.current_lang))
        self.btn_del_locator.setToolTip(tr("Delete the selected locator model file from disk.", self.current_lang))
        self.btn_del_segmenter.setText(tr("Del", self.current_lang))
        self.btn_del_segmenter.setToolTip(tr("Delete the selected segmenter model file from disk.", self.current_lang))
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if widget is self.workbench_widget:
                self.tabs.setTabText(index, tr("Labeling Workbench", self.current_lang))
            elif widget is self.blink_lab:
                self.tabs.setTabText(index, tr("Blink Workbench", self.current_lang))
            elif widget is self.tif_workbench:
                self.tabs.setTabText(index, tr("TIF Volume Workbench", self.current_lang))
            elif widget is self.pdf_widget:
                self.tabs.setTabText(index, tr("PDF Evidence Tools", self.current_lang))
            elif widget is self.start_center_widget:
                self.tabs.setTabText(index, tr("Start Center", self.current_lang))
        self._update_start_center_texts()
        self.genus_combo.blockSignals(True)
        self.genus_combo.clear()
        if hasattr(self.project, "list_taxa"):
            taxa = self.project.list_taxa()
        else:
            labels_vals = self.project.project_data["labels"].values()
            taxa = sorted(list(set(["Unknown"] + [d.get("genus", "Unknown") for d in labels_vals])))
        self.genus_combo.addItems(taxa)
        get_taxon = getattr(self.project, "get_taxon", self.project.get_genus)
        self.genus_combo.setCurrentText(get_taxon(self.current_image) if self.current_image else "Unknown")
        self.genus_combo.blockSignals(False)
        if self.check_morpho.isChecked() and self._current_part_name():
            self.update_measurements(self._current_part_name())
        self.refresh_route_table()

    def open_general_settings(self):
        params = {
            "language": self.current_lang,
            "theme": self.current_theme,
            "startup_behavior": self.config.get("startup_behavior", "start_center"),
            "project_autosave_interval_sec": max(1, int(self.project_autosave_delay_ms / 1000)),
            "runtime_device": self.runtime_device,
        }
        dlg = GeneralSettingsDialog(params, self.current_lang, self)
        if not dlg.exec():
            return
        values = dlg.get_values()
        if not values:
            return

        old_lang = self.current_lang
        old_theme = self.current_theme
        old_runtime_device = self.runtime_device
        self.project_autosave_delay_ms = max(1, int(values["project_autosave_interval_sec"])) * 1000
        self.config.set("startup_behavior", values["startup_behavior"])
        self.config.set("project_autosave_interval_sec", int(values["project_autosave_interval_sec"]))

        new_runtime_device = normalize_device_preference(values.get("runtime_device", "auto"))
        self.runtime_device = new_runtime_device
        self.config.set("runtime_device", self.runtime_device)
        if old_runtime_device != self.runtime_device:
            if self.engine.set_device_preference(self.runtime_device):
                self.log(tr("Runtime device resolved to: {0}", self.current_lang).format(str(self.engine.device)))
            if self.sam_worker:
                self.sam_worker.device_preference = self.runtime_device
                self.sam_worker.reload_base_model()
                selected_segmenter = self._selected_segmenter_timestamp()
                if selected_segmenter:
                    weights_path = self._segmenter_model_path(selected_segmenter)
                    if weights_path:
                        self.sam_worker.load_decoder_weights(weights_path)
            if hasattr(self, "blink_lab"):
                self.blink_lab.set_training_defaults(
                    self.blink_train_epochs,
                    self.blink_train_batch,
                    self.blink_train_lr,
                    self.blink_train_weight_decay,
                    self.blink_train_input_size,
                    self.runtime_device,
                )

        if values["language"] != old_lang:
            self.change_language(values["language"])
        else:
            self.config.set("language", self.current_lang)
        if values["theme"] != old_theme:
            self.change_theme(values["theme"])
        else:
            self.config.set("theme", self.current_theme)
        self.config.save()
        self.log(tr("General settings updated.", self.current_lang))
        self.refresh_ui()

    def open_stl_model_settings(self):
        params = {
            'epochs': self.train_epochs, 'batch': self.train_batch, 'lr': self.train_lr, 'wd': self.train_wd,
            'blink_epochs': self.blink_train_epochs,
            'blink_batch': self.blink_train_batch,
            'blink_lr': self.blink_train_lr,
            'blink_weight_decay': self.blink_train_weight_decay,
            'blink_input_size': self.blink_train_input_size,
            'conf': self.inf_conf, 'adapt': self.inf_adapt, 'pad': self.inf_pad, 
            'noise_floor': self.inf_noise_floor, 'poly_epsilon': self.inf_poly_epsilon,
            'model_backend': self.model_backend,
            'external_backend': self.external_backend_config,
            'runtime_device': self.runtime_device,
            'taxonomy': self.project.project_data.get("taxonomy", []),
            'locator_scope': self.project.get_locator_scope(),
        }
        route_panel = getattr(self, "route_settings_panel", None)
        if route_panel is not None:
            route_panel.setParent(None)
        dlg = ModelSettingsDialog(params, self.current_lang, self, route_panel=route_panel)
        if dlg.exec():
            v = dlg.get_values()
            if not v:
                if route_panel is not None:
                    route_panel.setParent(self)
                return
            self.train_epochs, self.train_batch = v['epochs'], v['batch']
            self.blink_train_epochs, self.blink_train_batch = v['blink_epochs'], v['blink_batch']
            self.blink_train_lr = v['blink_lr']
            self.blink_train_weight_decay = v['blink_weight_decay']
            self.blink_train_input_size = v['blink_input_size']
            self.train_lr, self.train_wd = v['lr'], v['wd']
            self.inf_conf, self.inf_adapt = v['conf'], v['adapt']
            self.inf_pad, self.inf_noise_floor = v['pad'], v['noise_floor']
            self.inf_poly_epsilon = v['poly_epsilon']
            old_runtime_device = self.runtime_device
            self.runtime_device = normalize_device_preference(v.get("runtime_device", "auto"))
            self.model_backend = v.get("model_backend", BUILTIN_BACKEND_ID)
            self.external_backend_config = sanitize_external_backend_config(v.get("external_backend", {}))
            self.project.set_locator_scope(v.get("locator_scope", []), save=False)
            
            self.config.set("train_epochs", self.train_epochs)
            self.config.set("train_batch", self.train_batch)
            self.config.set("blink_train_epochs", self.blink_train_epochs)
            self.config.set("blink_train_batch", self.blink_train_batch)
            self.config.set("blink_train_lr", self.blink_train_lr)
            self.config.set("blink_train_weight_decay", self.blink_train_weight_decay)
            self.config.set("blink_train_input_size", self.blink_train_input_size)
            self.config.set("train_lr", self.train_lr)
            self.config.set("train_weight_decay", self.train_wd)
            self.config.set("inf_conf_thresh", self.inf_conf)
            self.config.set("inf_adapt_thresh", self.inf_adapt)
            self.config.set("inf_box_pad", self.inf_pad)
            self.config.set("inf_noise_floor", self.inf_noise_floor)
            self.config.set("inf_poly_epsilon", self.inf_poly_epsilon)
            self.config.set("runtime_device", self.runtime_device)
            self.config.set("model_backend", self.model_backend)
            self.config.set("external_backend", self.external_backend_config)
            self.project.save_project()
            
            self.engine.update_hyperparameters(self.train_lr, self.train_wd)
            if self.engine.set_device_preference(self.runtime_device):
                self.log(tr("Runtime device resolved to: {0}", self.current_lang).format(str(self.engine.device)))
            
            # Update SAM Worker epsilon
            if self.sam_worker:
                self.sam_worker.set_epsilon(self.inf_poly_epsilon)
                if old_runtime_device != self.runtime_device:
                    self.sam_worker.device_preference = self.runtime_device
                    self.sam_worker.reload_base_model()
                    selected_segmenter = self._selected_segmenter_timestamp()
                    if selected_segmenter:
                        weights_path = self._segmenter_model_path(selected_segmenter)
                        if weights_path:
                            self.sam_worker.load_decoder_weights(weights_path)

            if hasattr(self, "blink_lab"):
                self.blink_lab.set_training_defaults(
                    self.blink_train_epochs,
                    self.blink_train_batch,
                    self.blink_train_lr,
                    self.blink_train_weight_decay,
                    self.blink_train_input_size,
                    self.runtime_device,
                )

            self.log(tr("Settings updated.", self.current_lang))
            self.refresh_ui()

        if route_panel is not None:
            route_panel.setParent(self)
            route_panel.set_language(self.current_lang)
            route_panel.set_theme(self.current_theme)

    def open_settings(self):
        self.open_stl_model_settings()

    def open_tif_model_settings(self):
        current_config = self.config.get("tif_backend", DEFAULT_TIF_BACKEND_CONFIG)
        dlg = TifModelSettingsDialog(current_config, self.current_lang, self)
        if not dlg.exec():
            return
        backend_config = dlg.get_values()
        self.config.set("tif_backend", dict(backend_config))
        self.config.save()
        if hasattr(self, "tif_workbench"):
            self.tif_workbench.set_config_manager(self.config)
        self.log(tr("TIF backend settings updated.", self.current_lang))

    def change_language(self, lang):
        self.current_lang = lang
        self.config.set("language", lang)
        self.pdf_widget.change_language(lang)
        self.tif_workbench.change_language(lang)
        self.blink_lab.change_language(lang)
        if hasattr(self, "route_settings_panel"):
            self.route_settings_panel.set_language(lang)
        self.refresh_model_list()
        self.refresh_ui()
        self.change_theme(self.current_theme)
        self.log(tr("Language: {0}", self.current_lang).format(lang))

    def change_theme(self, theme):
        theme = normalize_theme(theme)
        self.current_theme = theme
        self.config.set("theme", theme)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setProperty("activeTheme", theme)
        self.setStyleSheet(get_theme_stylesheet(theme))

        for widget in [self.pdf_widget, self.blink_lab, self.canvas]:
            if hasattr(widget, "set_theme"):
                widget.set_theme(theme)

        if hasattr(self, "route_settings_panel"):
            self.route_settings_panel.set_theme(theme)

        self.update_widget_themes()
        self.update_button_themes()
        self.log(f"Theme: {tr('Dark Mode', self.current_lang)}")

    def update_widget_themes(self):
        c = get_theme_config(self.current_theme)

        if hasattr(self, "desc_box"):
            self.desc_box.setStyleSheet(
                f"color: {c['text_soft']}; font-style: italic; background-color: {c['bg_input']};"
                f"border: 1px solid {c['border']}; border-radius: 10px; padding: 8px 10px; font-size: 10pt;"
            )

        if hasattr(self, "log_console"):
            self.log_console.setStyleSheet(
                f"background-color: {c['bg_input']}; color: {c['text_main']};"
                f"font-family: Consolas, 'Courier New', monospace; font-size: 9pt;"
                f"border: 1px solid {c['border']}; border-radius: 10px; padding: 8px;"
            )

    def update_button_themes(self):
        if hasattr(self, "btn_export"):
            apply_theme_button_style(self.btn_export, BUTTON_ROLE_COMMIT, "", self.current_theme)
        if hasattr(self, "btn_crop"):
            apply_theme_button_style(self.btn_crop, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        if hasattr(self, "btn_blink_entry"):
            apply_theme_button_style(self.btn_blink_entry, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        if hasattr(self, "btn_start_center_from_workbench"):
            apply_theme_button_style(self.btn_start_center_from_workbench, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        if hasattr(self, "btn_agent_from_workbench"):
            apply_theme_button_style(self.btn_agent_from_workbench, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        if hasattr(self, "btn_add"):
            apply_theme_button_style(self.btn_add, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        if hasattr(self, "btn_add_part"):
            apply_theme_button_style(self.btn_add_part, BUTTON_ROLE_NEUTRAL, "font-weight: bold;", self.current_theme)
        if hasattr(self, "btn_del_part"):
            apply_theme_button_style(self.btn_del_part, BUTTON_ROLE_DESTRUCTIVE, "font-weight: bold;", self.current_theme)
        if hasattr(self, "btn_del_locator"):
            apply_theme_button_style(self.btn_del_locator, BUTTON_ROLE_DESTRUCTIVE, "", self.current_theme)
        if hasattr(self, "btn_del_segmenter"):
            apply_theme_button_style(self.btn_del_segmenter, BUTTON_ROLE_DESTRUCTIVE, "", self.current_theme)
        if hasattr(self, "btn_predict"):
            apply_theme_button_style(self.btn_predict, BUTTON_ROLE_RUN, "padding: 5px;", self.current_theme)
        if hasattr(self, "btn_batch"):
            apply_theme_button_style(self.btn_batch, BUTTON_ROLE_RUN, "padding: 5px;", self.current_theme)
        if hasattr(self, "btn_train"):
            apply_theme_button_style(self.btn_train, BUTTON_ROLE_RUN, "padding: 8px; margin-top: 5px;", self.current_theme)
        if hasattr(self, "btn_stop_training"):
            apply_theme_button_style(self.btn_stop_training, BUTTON_ROLE_STOP, "padding: 8px; margin-top: 5px;", self.current_theme)
        if hasattr(self, "btn_clear_ai"):
            apply_theme_button_style(self.btn_clear_ai, BUTTON_ROLE_DESTRUCTIVE, "font-weight: bold; margin-top: 5px;", self.current_theme)
    def add_images(self):
        fs, _ = QFileDialog.getOpenFileNames(self, tr("Select Images", self.current_lang), "", "Images (*.png *.jpg *.jpeg *.tif)")
        if fs:
            self._flush_pending_project_save()
            self.project.add_images(fs)
            self.refresh_file_list()

    def open_cropper(self):
        img = None
        if self.file_list.currentItem():
            fn = self.file_list.currentItem().text()
            for p in self.project.project_data["images"]:
                if os.path.basename(p) == fn:
                    img = p
                    break
        dlg = ImageCropper(initial_image=img, parent=self, lang=self.current_lang)
        if dlg.exec():
            nf = dlg.get_files()
            if nf:
                self._flush_pending_project_save()
                self.project.add_images(nf)
                self.refresh_file_list()

    def show_file_list_context_menu(self, pos):
        its = self.file_list.selectedItems()
        if not its:
            return
        m = QMenu(self)
        if len(its) == 1:
            m.addAction(tr("Crop this Image", self.current_lang), self.open_cropper)
        m.addAction(tr("Remove Image", self.current_lang), self.remove_selected_images)
        m.exec(self.file_list.mapToGlobal(pos))

    def remove_selected_images(self):
        its = self.file_list.selectedItems()
        if not its:
            return
        if themed_yes_no_question(
            self,
            tr("Remove", self.current_lang),
            tr("Remove {0} images?", self.current_lang).format(len(its)),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        ) == QMessageBox.Yes:
            self._flush_pending_project_save()
            name_to_path = {os.path.basename(p): p for p in self.project.project_data["images"]}
            for it in its:
                p = name_to_path.get(it.text())
                if p:
                    self.project.remove_image(p)
            self.refresh_file_list()
            if self.current_image not in self.project.project_data["images"]:
                self.current_image = None
                self.canvas.load_image("")

    def refresh_file_list(self):
        # 1. Remember the currently selected image path
        current_selection_path = self.current_image

        self.file_list.blockSignals(True) # Prevent signal spam during rebuild
        self.file_list.clear()
        total_count = len(self.project.project_data["images"])
        labeled_count = 0
        
        # Logic: Labeled images first, then Unlabeled images.
        # Within each group, keep original insertion order.
        labeled_imgs = []
        unlabeled_imgs = []
        
        for img in self.project.project_data["images"]:
            if not img: continue
            if self.project.get_labels(img):
                labeled_imgs.append(img)
                labeled_count += 1
            else:
                unlabeled_imgs.append(img)
                
        # Combine: Labeled -> Unlabeled
        final_list = labeled_imgs + unlabeled_imgs
        
        item_to_select = None

        for img in final_list:
            base_name = os.path.basename(img)
            item = QListWidgetItem(base_name)
            item.setData(Qt.UserRole, img) # Store full path for safer lookup
            
            if img in labeled_imgs:
                item.setForeground(QColor("#8FBC8F")) # DarkSeaGreen
            else:
                item.setForeground(QColor("#CCCCCC")) # Grey
                
            self.file_list.addItem(item)
            
            # Check if this is the one we were looking at
            if current_selection_path and img == current_selection_path:
                item_to_select = item
        
        self.file_list.blockSignals(False)
        
        # 2. Restore Selection
        if item_to_select:
            self.file_list.setCurrentItem(item_to_select)
            self.file_list.scrollToItem(item_to_select) # Ensure visible
        
        # Update the header label on the left side
        header_base = tr("PROJECT IMAGES", self.current_lang)
        self.label_project_images.setText(f"{header_base} ({labeled_count}/{total_count})")

    def _collect_blink_roi_candidates(self, image_path, selected_part=None, preferred_roi_parts=None):
        manual_boxes = self.project.get_boxes(image_path)
        auto_boxes = self.project.get_auto_boxes(image_path)
        candidates = []

        def _append(boxes, source):
            if not isinstance(boxes, dict):
                return

            ordered_parts = list(boxes.keys())
            preferred_parts = [part for part in list(preferred_roi_parts or []) if part in ordered_parts]
            if preferred_parts:
                ordered_parts = preferred_parts + [part for part in ordered_parts if part not in preferred_parts]

            for part in ordered_parts:
                box = boxes.get(part)
                if not isinstance(box, (list, tuple)) or len(box) != 4:
                    continue
                try:
                    clean_box = [float(v) for v in box]
                except Exception:
                    continue
                if clean_box[2] <= clean_box[0] or clean_box[3] <= clean_box[1]:
                    continue
                candidates.append({
                    "part": part,
                    "source": source,
                    "box": clean_box,
                })

        _append(manual_boxes, "manual")
        _append(auto_boxes, "auto")
        return candidates

    def on_file_selected(self, curr, prev):
        if not curr:
            return
        
        # Robust Retrieval: Try getting data from UserRole first
        p = curr.data(Qt.UserRole)
        
        # Fallback for old items (shouldn't happen with new refresh logic)
        if not p:
            fn = curr.text()
            p = next((path for path in self.project.project_data["images"] if os.path.basename(path) == fn), None)
            
        if p:
            previous_image = self.current_image
            same_image = bool(previous_image) and os.path.normpath(previous_image) == os.path.normpath(p)
            has_loaded_pixmap = bool(self.canvas.original_pixmap and not self.canvas.original_pixmap.isNull())

            if not same_image:
                self._flush_pending_project_save()

            self.current_image = p
            labels = self.project.get_labels(p)
            manual_boxes = self.project.get_boxes(p)
            auto_boxes = self.project.get_auto_boxes(p)
            if not (same_image and has_loaded_pixmap):
                self.canvas.load_image(p)
                self.on_enhancement_changed()
            self.canvas.set_polygons(labels)
            self.canvas.set_boxes(manual_boxes, auto_boxes)
            get_taxon = getattr(self.project, "get_taxon", self.project.get_genus)
            self.genus_combo.setCurrentText(get_taxon(p))

    def on_part_selected(self, curr, prev):
        p = self._part_item_name(curr)
        if not p:
            self.canvas.set_active_part(None)
            self.desc_box.clear()
            return
        self.canvas.set_active_part(p)
        self.update_db_description(p)
        if self.check_morpho.isChecked():
            self.update_measurements(p)

    def launch_blink_from_workbench(self):
        if not self.current_image:
            QMessageBox.warning(self, tr("Blink Workbench Entry", self.current_lang), tr("Please select an image first.", self.current_lang))
            return

        selected_part = self._current_part_name()
        if not selected_part:
            QMessageBox.warning(self, tr("Blink Workbench Entry", self.current_lang), tr("Please select a target part first.", self.current_lang))
            return

        taxonomy = list(self.project.project_data.get("taxonomy", []))
        remembered_parent_map = self.project.get_blink_context_roi_parents()
        remembered_parent = remembered_parent_map.get(str(selected_part or "").strip())
        preferred_roi_parts = _blink_preferred_roi_parts(selected_part, remembered_parent)
        roi_candidates = self._collect_blink_roi_candidates(
            self.current_image,
            selected_part,
            preferred_roi_parts=preferred_roi_parts,
        )
        if not roi_candidates:
            QMessageBox.information(
                self,
                tr("Blink Workbench Entry", self.current_lang),
                tr("No entry ROI is available yet. Draw a manual box or generate an auto box in the workbench first.", self.current_lang),
            )
            return

        dialog = BlinkEntryDialog(
            self.current_image,
            taxonomy,
            selected_part,
            roi_candidates,
            self,
            self.current_lang,
            remembered_parent_map=remembered_parent_map,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        session = dialog.get_session_spec(self.current_image)
        if not session:
            QMessageBox.warning(
                self,
                tr("Blink Workbench Entry", self.current_lang),
                tr("Failed to build a Blink session from the selected options.", self.current_lang),
            )
            return

        labels = self.project.get_labels(self.current_image)
        manual_boxes = self.project.get_boxes(self.current_image)
        auto_boxes = self.project.get_auto_boxes(self.current_image)
        started = self.blink_lab.start_session(session, labels, manual_boxes, auto_boxes)
        if not started:
            return
        self.tabs.setCurrentWidget(self.blink_lab)

        focus_roi = session.get("focus_roi", {})
        if not isinstance(focus_roi, dict):
            focus_roi = {}
        remembered_target_part = session.get("target_part")
        remembered_parent_part = str(focus_roi.get("part") or "").strip()
        if remembered_parent_part and remembered_target_part:
            if remembered_parent_part == remembered_target_part:
                self.project.clear_blink_context_parent(remembered_target_part)
            else:
                self.project.remember_blink_context_parent(remembered_target_part, remembered_parent_part)
                if hasattr(self.project, "register_cascade_route_candidate"):
                    self.project.register_cascade_route_candidate(
                        remembered_parent_part,
                        remembered_target_part,
                        focus_source=focus_roi.get("source"),
                        registration_source="blink_candidate",
                    )
                    if hasattr(self, "refresh_route_table"):
                        self.refresh_route_table()
        focus_label = focus_roi.get("part", "ROI")
        focus_source = focus_roi.get("source", "manual")
        self.log(
            tr("Opened Blink session for {0} via {1} ({2}).", self.current_lang).format(
                session.get('target_part'), focus_label, focus_source
            )
        )

    def on_genus_changed(self, txt):
        if self.current_image:
            set_taxon = getattr(self.project, "set_taxon", self.project.set_genus)
            set_taxon(self.current_image, txt)

    def update_db_description(self, p):
        if p:
            self.desc_box.setText(self.db.query_trait_description(self.genus_combo.currentText(), p))

    def on_enhancement_changed(self):
        self.canvas.set_enhancements(self.slider_bright.value(), self.slider_contrast.value() / 10.0)

    def on_tool_changed(self):
        if self.radio_magic.isChecked():
            self.canvas.set_mode("MAGIC_WAND")
        elif self.radio_box.isChecked():
            self.canvas.set_mode("BOX_PROMPT")
        elif self.radio_scale.isChecked():
            self.canvas.set_mode("SCALE")
        else:
            self.canvas.set_mode("DRAW")

    def on_magic_wand_clicked(self, x, y):
        if self.current_image and self.sam_worker and self.sam_worker.model:
            self.sam_worker.predict_point(self.current_image, x, y)

    def on_magic_box_completed(self, x1, y1, x2, y2):
        if self.current_image and self.sam_worker and self.sam_worker.model:
            self.sam_worker.predict_box(self.current_image, x1, y1, x2, y2)

    def on_sam_mask_generated(self, pts, box=None):
        p = self._current_part_name()
        if p:
            self.on_polygon_completed(p, pts, box)
            # Re-fetch from project to ensure consistency (and display updated boxes)
            self.canvas.set_polygons(self.project.get_labels(self.current_image))
            self.canvas.set_boxes(self.project.get_boxes(self.current_image), self.project.get_auto_boxes(self.current_image))

    def on_polygon_completed(self, p, pts, box=None):
        if self.current_image:
            if not pts:
                # Empty points means DELETE
                self.project.delete_label(self.current_image, p, save=False)
            else:
                self.project.update_label(self.current_image, p, pts, self.desc_box.toPlainText(), box=box, save=False)
            self._schedule_project_save()
            
            # Update counts on the left panel
            self.refresh_file_list()
            
            if self.check_morpho.isChecked():
                self.update_measurements(p)

    def toggle_morphometrics(self, state):
        on = self.check_morpho.isChecked()
        self.radio_scale.setVisible(on)
        self.group_morpho.setVisible(on)
        p = self._current_part_name()
        if on and p:
            self.update_measurements(p)

    def on_scale_defined(self, lpx):
        v, ok = QInputDialog.getDouble(self, tr("Scale Tool", self.current_lang), tr("mm:", self.current_lang), 1.0, 0.001, 1000.0, 3)
        if ok and self.current_image:
            self.project.set_scale(self.current_image, lpx/v)
            self.refresh_ui()

    def update_measurements(self, p):
        if not self.current_image or not p:
            return
        sc = self.project.get_scale(self.current_image)
        if not sc:
            self.label_measurements.setText(tr("No Scale.", self.current_lang))
            return
        pts = self.project.get_labels(self.current_image).get(p)
        if pts and len(pts) > 2:
            import cv2
            pts_np = np.array(pts, dtype=np.float32)
            a = cv2.contourArea(pts_np) / (sc*sc)
            peri = cv2.arcLength(pts_np, True) / sc
            self.label_measurements.setText(tr("Area: {0:.4f} mm2\nPeri: {1:.4f} mm", self.current_lang).format(a, peri))
        else:
            self.label_measurements.setText(tr("No Polygon.", self.current_lang))

    def run_training(self):
        self._flush_pending_project_save()
        if self.trainer and self.trainer.isRunning():
            self.log(tr("Training already running...", self.current_lang))
            return
        if self.model_backend == EXTERNAL_BACKEND_ID:
            self.run_external_training()
            return
        images = list(self.project.project_data.get("images", []))
        labels_by_image = dict(self.project.project_data.get("labels", {}))
        if not images:
            QMessageBox.warning(self, tr("No Labels", self.current_lang), tr("Annotate first!", self.current_lang))
            return
        tax = self.project.project_data["taxonomy"]
        locator_scope = self.project.get_locator_scope()
        preflight = build_training_preflight(images, labels_by_image, tax, locator_scope)

        if not preflight.get("locator_samples") and not preflight.get("parts_samples"):
            QMessageBox.warning(self, tr("No Labels", self.current_lang), tr("Annotate first!", self.current_lang))
            return

        self.log(tr("Training with Taxonomy ({0}): {1}", self.current_lang).format(len(tax), tax))
        self.log(tr("Training with Locator Scope ({0}): {1}", self.current_lang).format(len(locator_scope), locator_scope))
        self.log(describe_training_preflight(preflight))
        train_segmenter = not self.chk_train_locator_only.isChecked()
        if not train_segmenter and not preflight.get("locator_samples"):
            QMessageBox.warning(
                self,
                tr("Training", self.current_lang),
                tr("Locator stage skipped: no eligible locator samples.", self.current_lang),
            )
            return
        
        if len(locator_scope) != self.engine.current_num_classes:
            self.engine.rebuild_locator(len(locator_scope), self.train_lr, self.train_wd)

        if not self._show_structured_training_preflight(preflight):
            return

        if preflight.get("locator_samples"):
            self.ensure_locator_preloaded()
        if not self._confirm_legacy_locator_selection_if_needed():
            return
        if train_segmenter and preflight.get("parts_samples"):
            self.ensure_sam_preloaded()

        self._launch_training_with_preflight(preflight, tax, locator_scope, train_segmenter=train_segmenter)

    def _external_backend_runner(self):
        return ExternalBackendRunner(self.project, self.external_backend_config)

    def run_external_training(self):
        self._flush_pending_project_save()
        if not self.project.current_project_path:
            QMessageBox.warning(self, tr("Training", self.current_lang), tr("Save Project", self.current_lang))
            return
        try:
            self.btn_train.setEnabled(False)
            self.btn_stop_training.setEnabled(False)
            self.log("External backend training started.")
            summary = self._external_backend_runner().run_prepare_and_train()
            self.log(f"External training complete. Contract: {summary.get('contract_json')}")
            self.log(f"External model manifest: {summary.get('model_manifest')}")
        except Exception as exc:
            self.log(f"External training failed: {exc}")
            QMessageBox.critical(self, tr("Error", self.current_lang), str(exc))
        finally:
            self.btn_train.setEnabled(True)
            self.btn_stop_training.setEnabled(False)

    def show_training_report(self, report_data):
        dlg = TrainingReportDialog(report_data, self, self.current_lang)
        dlg.exec()

    def _extract_prediction_payload(self, payload):
        """兼容新旧推理输出协议，统一返回 polygons + auto_boxes。"""
        polygons = {}
        auto_boxes = {}
        taxonomy_set = set(self.project.project_data.get("taxonomy", []))

        if not isinstance(payload, dict):
            return polygons, auto_boxes

        # 新协议: {polygons: {...}, auto_boxes: {...}}
        if isinstance(payload.get("polygons"), dict):
            polygons = {
                str(part): points
                for part, points in payload.get("polygons", {}).items()
                if str(part) in taxonomy_set
            }
            raw_auto_boxes = payload.get("auto_boxes", {}) if isinstance(payload.get("auto_boxes"), dict) else {}
            auto_boxes = {
                str(part): box
                for part, box in raw_auto_boxes.items()
                if str(part) in taxonomy_set
            }
            return polygons, auto_boxes

        # 旧协议回退: {part: polygon, part_BOX: box_polygon}
        for key, value in payload.items():
            if key.endswith("_BOX") and isinstance(value, list):
                xs = [p[0] for p in value if isinstance(p, (list, tuple)) and len(p) >= 2]
                ys = [p[1] for p in value if isinstance(p, (list, tuple)) and len(p) >= 2]
                if xs and ys:
                    real_part = key.replace("_BOX", "")
                    auto_boxes[real_part] = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]
            elif isinstance(value, list):
                if key in taxonomy_set:
                    polygons[key] = value

        return polygons, auto_boxes

    def _apply_prediction_to_project(self, image_path, payload, only_new=True):
        polygons, auto_boxes = self._extract_prediction_payload(payload)
        existing_parts = set(self.project.get_labels(image_path).keys())
        saved_count = 0

        for part_name, points in polygons.items():
            if only_new and part_name in existing_parts:
                continue

            auto_box = auto_boxes.get(part_name)
            if (not auto_box) and isinstance(points, list) and points:
                xs = [pt[0] for pt in points if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                ys = [pt[1] for pt in points if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                if xs and ys:
                    auto_box = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]

            self.project.update_label(image_path, part_name, points, "Auto-Annotated", auto_box=auto_box)
            existing_parts.add(part_name)
            saved_count += 1

        return saved_count, len(polygons)

    def run_prediction(self):
        if not self.current_image:
            return
        if self.model_backend == EXTERNAL_BACKEND_ID:
            self.run_external_prediction(self.current_image)
            return
        self.ensure_locator_preloaded()
        if not self._confirm_legacy_locator_selection_if_needed():
            return
        self.ensure_sam_preloaded()
        self.log(tr("Running inference on: {0}...", self.current_lang).format(os.path.basename(self.current_image)))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ps = self.engine.predict_full_pipeline(
                self.current_image, 
                self.project.project_data["taxonomy"], 
                self.project.get_locator_scope(),
                self.inf_conf, 
                self.inf_adapt, 
                self.inf_pad, 
                self.inf_noise_floor,
                self.inf_poly_epsilon,
                self._active_project_route_manifest(),
            )
            count, total_detected = self._apply_prediction_to_project(self.current_image, ps, only_new=True)
            
            labels = self.project.get_labels(self.current_image)
            manual_boxes = self.project.get_boxes(self.current_image)
            auto_boxes = self.project.get_auto_boxes(self.current_image)
            self.canvas.set_polygons(labels)
            self.canvas.set_boxes(manual_boxes, auto_boxes)
            self.refresh_file_list()
            self._log_route_usage_summary(ps, self.current_image)
            self.log(tr("Inference complete. Detected {0} parts, saved {1} new labels.", self.current_lang).format(total_detected, count))
        finally:
            QApplication.restoreOverrideCursor()

    def run_external_prediction(self, image_path):
        self._flush_pending_project_save()
        self.log(tr("Running inference on: {0}...", self.current_lang).format(os.path.basename(image_path)))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = self._external_backend_runner().run_predict(
                image_path,
                model_manifest=self.external_backend_config.get("model_manifest", ""),
            )
            count, total_detected = self._apply_prediction_to_project(image_path, result.get("payload", {}), only_new=True)
            if image_path == self.current_image:
                self.canvas.set_polygons(self.project.get_labels(image_path))
                self.canvas.set_boxes(self.project.get_boxes(image_path), self.project.get_auto_boxes(image_path))
            self.refresh_file_list()
            self.log(f"External inference complete. Contract: {result.get('contract_json')}")
            self.log(tr("Inference complete. Detected {0} parts, saved {1} new labels.", self.current_lang).format(total_detected, count))
        except Exception as exc:
            self.log(f"External inference failed: {exc}")
            QMessageBox.critical(self, tr("Error", self.current_lang), str(exc))
        finally:
            QApplication.restoreOverrideCursor()

    def verify_current_image(self):
        if self.current_image:
            self.project.verify_image_labels(self.current_image)

    def run_batch_inference(self):
        ul = [img for img in self.project.project_data["images"] if not self.project.get_labels(img)]
        if not ul:
            return
        if self.model_backend == EXTERNAL_BACKEND_ID:
            if themed_yes_no_question(
                self,
                tr("Batch", self.current_lang),
                tr("Annotate {0} images?", self.current_lang).format(len(ul)),
                confirm_role=BUTTON_ROLE_RUN,
            ) == QMessageBox.Yes:
                self.btn_batch.setEnabled(False)
                self.btn_predict.setEnabled(False)
                try:
                    for image_path in ul:
                        result = self._external_backend_runner().run_predict(
                            image_path,
                            model_manifest=self.external_backend_config.get("model_manifest", ""),
                        )
                        saved, total = self._apply_prediction_to_project(image_path, result.get("payload", {}), only_new=True)
                        self.log(tr("Batch saved {0}/{1} for {2}", self.current_lang).format(saved, total, os.path.basename(image_path)))
                    self.refresh_file_list()
                except Exception as exc:
                    self.log(f"External batch inference failed: {exc}")
                    QMessageBox.critical(self, tr("Error", self.current_lang), str(exc))
                finally:
                    self.btn_batch.setEnabled(True)
                    self.btn_predict.setEnabled(True)
            return
        self.ensure_locator_preloaded()
        if not self._confirm_legacy_locator_selection_if_needed():
            return
        self.ensure_sam_preloaded()
        if themed_yes_no_question(
            self,
            tr("Batch", self.current_lang),
            tr("Annotate {0} images?", self.current_lang).format(len(ul)),
            confirm_role=BUTTON_ROLE_RUN,
        ) == QMessageBox.Yes:
            self.btn_batch.setEnabled(False)
            self.btn_predict.setEnabled(False)
            
            tax = self.project.project_data["taxonomy"]
            locator_scope = self.project.get_locator_scope()
            self.log(tr("Starting Batch Inference with Taxonomy ({0}): {1}", self.current_lang).format(len(tax), tax))
            self.log(tr("Starting Batch Inference with Locator Scope ({0}): {1}", self.current_lang).format(len(locator_scope), locator_scope))
            
            params = {
                'conf': self.inf_conf, 'adapt': self.inf_adapt, 
                'pad': self.inf_pad, 'noise_floor': self.inf_noise_floor,
                'poly_epsilon': self.inf_poly_epsilon,
            }
            self.inf_thread = InferenceThread(
                self.engine,
                ul,
                tax,
                locator_scope,
                params,
                project_route_manifest=self._active_project_route_manifest(),
                lang=self.current_lang,
            )
            self.inf_thread.log_signal.connect(self.log) # Fix: Connect log signal
            def on_batch_res(p, d):
                saved, total = self._apply_prediction_to_project(p, d, only_new=True)
                self._log_route_usage_summary(
                    d,
                    p,
                    prefix=ui_text("Route usage for batch image {0}", self.current_lang).format(os.path.basename(p)),
                )
                self.log(tr("Batch saved {0}/{1} for {2}", self.current_lang).format(saved, total, os.path.basename(p)))
            self.inf_thread.result_signal.connect(on_batch_res)
            self.inf_thread.finished_signal.connect(lambda: [self.btn_batch.setEnabled(True), self.btn_predict.setEnabled(True)])
            self.inf_thread.start()

    def export_dataset(self):
        dlg = ExportDialog(self, self.current_lang)
        if dlg.exec():
            self._flush_pending_project_save()
            p, f = dlg.get_path(), dlg.get_format()
            if f == "multimodal":
                c = self.project.export_multimodal_dataset(p)
            elif f == "coco":
                c = self.project.export_coco(p)
            else:
                c = self.project.export_yolo(p)
            QMessageBox.information(self, tr("Export", self.current_lang), tr("Exported {0} samples.", self.current_lang).format(c))

    def init_sam(self):
        if self.sam_thread and self.sam_thread.isRunning():
            return
        if self.sam_worker and getattr(self.sam_worker, "model", None) is not None:
            return
        mp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights", "sam_b.pt")
        self.log(tr("Initializing SAM (Segment Anything) on active compute device...", self.current_lang))
        self.sam_thread = QThread()
        # Pass current epsilon to worker
        self.sam_worker = SAMWorker(model_type=mp, poly_epsilon=self.inf_poly_epsilon, device=self.runtime_device)
        self.sam_worker.moveToThread(self.sam_thread)
        self.sam_thread.started.connect(self.sam_worker.load_model)
        self.sam_worker.mask_generated.connect(self.on_sam_mask_generated)
        self.sam_worker.model_loaded.connect(lambda: self.log(tr("SAM Model Loaded and Ready!", self.current_lang)))
        self.sam_worker.model_load_error.connect(lambda message: self.log(str(message)))
        self.sam_thread.start()

    def ensure_sam_preloaded(self):
        started = False
        if self.sam_thread and self.sam_thread.isRunning():
            pass
        elif self.sam_worker and getattr(self.sam_worker, "model", None) is not None:
            pass
        else:
            self.init_sam()
            started = True

        if self._preload_engine_parts_model_async():
            started = True
        return started

    def ensure_2d_stl_models_preloaded(self):
        locator_started = self.ensure_locator_preloaded()
        sam_started = self.ensure_sam_preloaded()
        return bool(locator_started or sam_started)

    def ensure_locator_preloaded(self):
        if not self.engine or not hasattr(self.engine, "ensure_locator_loaded"):
            return False
        if getattr(self.engine, "locator", None) is not None:
            return False
        locator_scope_len = len(self.project.get_locator_scope())
        if locator_scope_len != self.engine.current_num_classes:
            self.engine.current_num_classes = locator_scope_len
            self.engine.loaded_locator_timestamp = None
            self.engine.loaded_locator_requires_legacy_confirmation = False
            self.engine.loaded_locator_is_legacy_512 = False
        ts = self._selected_locator_timestamp()
        if ts:
            self.engine.load_locator(ts)
        else:
            self.engine.ensure_locator_loaded()
        return True

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

    def log(self, msg):
        self.log_console.append(msg)

if __name__ == "__main__":
    def excepthook(t, v, tb):
        import traceback
        err = "".join(traceback.format_exception(t, v, tb))
        print(f"CRITICAL ERROR:\n{err}")
        QMessageBox.critical(None, "Error", f"{v}")
        sys.__excepthook__(t, v, tb)
    sys.excepthook = excepthook
    app = QApplication(sys.argv)
    register_windows_scholarly_ui_fonts()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
