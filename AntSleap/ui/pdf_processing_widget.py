from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton, 
                               QFileDialog, QTextEdit, QProgressBar, QGroupBox, QCheckBox, QMessageBox, 
                               QTabWidget, QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, 
                               QScrollArea, QComboBox, QApplication)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QPixmap, QImage, QIntValidator, QDoubleValidator
import importlib
import importlib.util
from copy import deepcopy
import os
import sys
import csv
import sqlite3
import json

from .style import (
    BUTTON_ROLE_COMMIT,
    BUTTON_ROLE_DESTRUCTIVE,
    BUTTON_ROLE_NEUTRAL,
    BUTTON_ROLE_RUN,
    BUTTON_ROLE_STOP,
    DIALOG_ACTION_BUTTON_EXTRAS,
    apply_theme_button_style,
    apply_semantic_button_style,
    apply_surface_role,
    SURFACE_ROLE_PANEL,
    SURFACE_ROLE_RAISED,
    SURFACE_ROLE_SUBTLE,
    get_theme_stylesheet,
    get_theme_config,
    normalize_theme,
    themed_ok_cancel_message,
    themed_yes_no_question,
)

def _load_pdf_processor_dependencies():
    try:
        module = importlib.import_module("core.pdf_processor")
        return getattr(module, "LLMScreenPDFClassifier"), getattr(
            module,
            "EnhancedPDFExtractionSystem",
        )
    except ModuleNotFoundError as exc:
        if exc.name != "core.pdf_processor":
            raise

    repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    package_dir = os.path.join(repo_root, "core", "pdf_processor")
    init_file = os.path.join(package_dir, "__init__.py")

    spec = importlib.util.spec_from_file_location(
        "formica_flow_pdf_processor",
        init_file,
        submodule_search_locations=[package_dir],
    )
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Unable to load pdf_processor package from: {init_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return getattr(module, "LLMScreenPDFClassifier"), getattr(
        module,
        "EnhancedPDFExtractionSystem",
    )


def _load_figure_profile_dependencies():
    try:
        module = importlib.import_module("core.pdf_processor.figure_profile")
    except ModuleNotFoundError as exc:
        if exc.name not in {"core", "core.pdf_processor", "core.pdf_processor.figure_profile"}:
            raise
        repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
        profile_file = os.path.join(repo_root, "core", "pdf_processor", "figure_profile.py")
        spec = importlib.util.spec_from_file_location("formica_flow_figure_profile", profile_file)
        if spec is None or spec.loader is None:
            raise ModuleNotFoundError(f"Unable to load figure_profile module from: {profile_file}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return (
        getattr(module, "load_figure_profile"),
        getattr(module, "normalize_figure_profile"),
        getattr(module, "profile_display_name"),
    )


LLMScreenPDFClassifier, EnhancedPDFExtractionSystem = _load_pdf_processor_dependencies()
load_figure_profile, normalize_figure_profile, profile_display_name = _load_figure_profile_dependencies()


def _resolve_active_theme(parent=None) -> str:
    current = parent
    while current is not None:
        theme = getattr(current, "current_theme", None)
        if isinstance(theme, str) and theme.strip():
            return normalize_theme(theme.strip())
        parent_widget = getattr(current, "parentWidget", None)
        current = parent_widget() if callable(parent_widget) else None
    app = QApplication.instance()
    if app is not None:
        app_theme = app.property("activeTheme")
        if isinstance(app_theme, str) and app_theme.strip():
            return normalize_theme(app_theme.strip())
    return normalize_theme("dark")

# --- Localization ---
TRANSLATIONS = {
    "zh": {
        "Global Settings (LLM / API)": "全局设置 (LLM / API)",
        "Text LLM API": "文本模型 API",
        "Multimodal LLM API": "多模态模型 API",
        "API Key:": "API 密钥:",
        "Base URL:": "Base URL (接口地址):",
        "Model:": "模型名称:",
        "API Protocol:": "API协议:",
        "Image Detail:": "图像细节:",
        "Use same provider as Text LLM": "复用文本模型 API",
        "Vision Model Name": "视觉模型名称",
        "Auto (Recommended)": "自动（推荐）",
        "Auto": "自动",
        "Low": "低",
        "High": "高",
        "Chat Completions": "Chat Completions",
        "Responses API": "Responses API",
        "Save API Settings": "保存API设置",
        "Remember API Key": "记住API密钥",
        "Remember Multimodal API Key": "记住多模态API密钥",
        "API settings saved.": "API设置已保存。",
        "Failed to save API settings: {}": "保存API设置失败: {}",
        "Failed to load API settings: {}": "加载API设置失败: {}",
        "Screening Mode:": "筛选模式:",
        "V2 (CSV Full LLM)": "V2（CSV全量LLM）",
        "Default V2 Profile": "默认V2方案",
        "Lines/PDF:": "每篇提取行数:",
        "Batch Size:": "每批条数:",
        "Fallback Batch:": "降档批次:",
        "Include Threshold:": "通过阈值:",
        "1. PDF Screener (Classify)": "1. 文献筛选 (分类)",
        "Input PDFs:": "输入 PDF 文件夹:",
        "Browse": "浏览",
        "Output Dir:": "输出文件夹:",
        "Start Classification Batch": "开始批量分类",
        "Stop Classification": "停止分类",
        "2. Data Extractor (Images & Text)": "2. 数据提取 (图文提取)",
        "Input Folder:": "输入筛选后的文件夹:",
        "Output DB:": "输出数据库:",
        "Select DB File": "选择数据库文件",
        "Enable Multimodal Validation (Uses API - Slower but more accurate)": "启用多模态验证 (使用 API - 较慢但更准确)",
        "Start Extraction Pipeline": "开始提取流程",
        "Stop Extraction": "停止提取",
        "3. Data Utilities": "3. 数据工具",
        "Browse Database": "浏览数据库",
        "Export PDF Extract Dataset (JSONL)": "导出 PDF 提取数据集（JSONL）",
        "This JSONL contains raw records extracted from PDFs and has not been manually curated.\nUse it for quick model checks, not as a trusted training set.\n\nFor researcher-verified training data, export from the Labeling Workbench.": "该 JSONL 包含从 PDF 自动提取的原始记录，尚未经过人工校核。\n可用于快速检查模型能力，但不应直接视为可信训练集。\n\n如需研究者确认后的训练数据，请改用“标注工作台”导出。",
        "Processing Logs:": "处理日志:",
        "Error": "错误",
        "Mock/Default Review Confirmation": "Mock/默认复核确认",
        "Continue with extraction anyway?": "仍要继续开始提取吗？",
        "Continue": "继续",
        "Cancel": "取消",
        "Please select source and output directories.": "请选择输入和输出目录。",
        "Please select input folder.": "请选择输入文件夹。",
        "Task Finished.": "任务已完成。",
        "Process stopped by user.": "用户已停止任务。",
        "Classification Finished.": "分类已完成。",
        "Extraction Pipeline Completed.": "提取流程已完成。",
        "Advanced Logic Settings": "高级逻辑设置",
        "Advanced Figure Settings": "高级图文方案设置",
        "Figure Extraction / Review Profile:": "图文提取/复核方案:",
        "Built-in Ant Triptych Figure Profile": "内置蚂蚁三视图图文方案",
        "Failed to load figure profile: {0}": "加载图文方案失败: {0}",
        "Failed to save figure profile: {0}": "保存图文方案失败: {0}",
        "Invalid figure profile JSON: {0}": "图文方案 JSON 无效: {0}",
        "Figure extraction/review profile updated.": "图文提取/复核方案已更新。",
        "Edit the figure extraction and multimodal review profile JSON. API keys are not stored here.": "编辑图文提取与多模态复核方案 JSON。API 密钥不会保存在这里。",
        "Keyword Configuration": "关键词配置",
        "Keyword lists are editable helper lexicons for V2 screening. The LLM prompt defines the final biological decision criteria.": "关键词是 V2 筛选的可编辑辅助词库；最终生物学判定标准由 LLM 提示词决定。",
        "Show Keyword Lexicons": "显示关键词词库",
        "Keyword Assist Lexicon": "关键词辅助词库",
        "Required Keywords (e.g. 'sp. nov.'):": "核心关键词 (如 'sp. nov.'):",
        "Supportive Keywords (e.g. 'morphology'):": "支持性关键词 (如 'morphology'):",
        "Taxonomic Group Keywords (e.g. 'ant'):": "目标类群识别词 (如 'ant'):",
        "Strong Exclude (e.g. 'ecology'):": "强排除关键词 (如 'ecology'):",
        "Weak Exclude (e.g. 'note'):": "弱排除关键词 (如 'note'):",
        "Biological Exclude (e.g. 'virus'):": "生物干扰排除词 (如 'virus'):",
        "LLM Review Prompt Template:": "LLM 复查提示词模板:",
        "LLM Prompt (V2 Core):": "LLM 提示词（V2核心）:",
        "System Prompt:": "系统提示词：",
        "Placeholders: {records_json}, {expected_record_count}, {expected_record_ids_json}, {batch_id}.": "占位符：{records_json}, {expected_record_count}, {expected_record_ids_json}, {batch_id}。",
        "Save & Apply": "保存并应用",
        "Reset to Default": "恢复默认",
        "Settings Saved": "设置已保存",
        "Screener logic configuration updated.": "筛选逻辑配置已更新。",
        "Select Logic Profile:": "选择逻辑方案:",
        "Profile Name:": "方案名称:",
        "Save as New Profile": "另存为新方案",
        "Overwrite Current": "覆盖当前方案",
        "Delete Profile": "删除方案",
        "Confirm Delete": "确认删除",
        "Are you sure you want to delete profile '{}'?": "确定要删除方案 '{}' 吗？",
        "Default_Ant_Logic": "默认蚂蚁逻辑",
        "Folder containing raw PDFs...": "包含原始 PDF 的文件夹...",
        "Folder to sort PDFs into...": "分类结果存放文件夹...",
        "Folder with 'New Species' PDFs...": "包含'新种' PDF 的文件夹...",
        "Model Name": "模型名称 (如 gpt-4)",
        "Progress:": "进度:",
        "Processing Results": "处理结果",
        "Summary": "统计摘要",
        "View Detailed CSV": "查看详细 CSV",
        "Close": "关闭",
        "Loading CSV...": "正在加载 CSV...",
        "CSV Viewer": "CSV 查看器",
        "Database Viewer": "数据库浏览器",
        "Image Preview": "图片预览",
        "Text Context": "文本内容",
        "Prompt Char Budget:": "提示词字符预算:",
        "Text Chars/File:": "每文件文本字符数:",
        "LLM Max Tokens:": "LLM 最大 Tokens:",
        "LLM Timeout(s):": "LLM 超时（秒）:",
        "Auto Split Failed Batches": "自动拆分失败批次",
        "Resume Interrupted Runs": "恢复中断运行",
        "V2: separate folder per run": "V2：每次运行独立文件夹",
        "Each V2 run saves into its own subfolder under Output Dir to avoid mixed results.": "勾选后：每次 V2 运行都会在输出目录下使用独立子文件夹，避免不同运行结果混在一起。",
        "Export Success": "导出成功",
        "Exported {} records to {}": "已导出 {} 条记录到 {}",
        "No DB selected": "未选择数据库文件",
        "Select Directory": "选择目录",
        "Select Database File": "选择数据库文件",
        "Profile mode mismatch. Please select a profile matching current screening mode.": "方案模式不匹配，请选择与当前筛选模式一致的方案。",
        "Restore Interrupted Run Params": "恢复中断运行参数",
        "Please select an output directory first.": "请先选择输出目录。",
        "Current output directory does not contain interrupted-run metadata.": "当前输出目录中未找到中断运行元数据。",
        "Interrupted run metadata is missing run_index_path.": "中断运行元数据缺少 run_index_path。",
        "Current output directory does not contain an interrupted V2 run (status: {}).": "当前输出目录中没有可恢复的 V2 中断运行（状态：{}）。",
        "Interrupted run metadata is missing a runtime config snapshot.": "中断运行元数据缺少运行参数快照。",
        "Required file not found: {}": "未找到所需文件: {}",
        "Failed to read JSON file {}: {}": "读取 JSON 文件失败 {}: {}",
        "JSON file does not contain an object: {}": "JSON 文件不是对象格式: {}",
        "Settings Restored": "设置已恢复",
        "Interrupted-run parameters restored from run {}. API key was left unchanged.": "已从运行 {} 恢复中断运行参数。API 密钥未被改动。",
        "Restored interrupted-run parameters from {} (run {}, status {}).": "已从 {} 恢复中断运行参数（运行 {}，状态 {}）。",
        "Failed to restore interrupted-run parameters: {}": "恢复中断运行参数失败: {}",
        "ID": "编号",
        "Filename": "文件名",
        "Path": "路径",
        "Score": "分数",
        "Accepted": "已接受",
        "Page": "页码",
        "Species": "物种",
        "Taxonomic": "分类学相关",
        "DB Error: {0}": "数据库错误：{0}",
        "Invalid Image File": "无效图片文件",
        "Image not found on disk": "磁盘上未找到图片",
        "File: {0}\n": "文件：{0}\n",
        "Page: {0}\nSpecies: {1}\nCategory: {2}\nStatus: {3}\nMultimodal: {4}\n": "页码：{0}\n物种：{1}\n类别：{2}\n状态：{3}\n多模态：{4}\n",
        "Model: {0}\n": "模型：{0}\n",
        "Reject Reason: {0}\n": "拒绝原因：{0}\n",
        "\n--- Caption ---\n{0}\n": "\n--- 图注 ---\n{0}\n",
        "\n--- Evidence ---\n": "\n--- 证据 ---\n",
        "\n(No related evidence found in DB)": "\n（数据库中未找到相关证据）",
        "\n\n--- Related Text ---\n": "\n\n--- 相关文本 ---\n",
        "[{0} | {1}]: {2}\n\n": "[{0} | {1}]：{2}\n\n",
        "\n\n(No related text found in DB)": "\n\n（数据库中未找到相关文本）",
        "Error querying text: {0}": "查询文本时出错：{0}",
        "Failed to load CSV: {0}": "加载 CSV 失败：{0}",
        "Comma separated keywords...": "请输入以逗号分隔的关键词...",
        "Profile name cannot be empty.": "方案名称不能为空。",
        "Error loading summary: {0}": "加载摘要失败：{0}",
        "No summary file generated.": "未生成摘要文件。",
        "sk-...": "sk-...",
        "https://api.siliconflow.cn/v1": "https://api.siliconflow.cn/v1",
        "No DB selected or file not found.": "未选择数据库文件或文件不存在。",
        "Export JSONL": "导出 JSONL",
        "Failed to load profile: {0}": "加载方案失败：{0}",
        "Failed to save profile: {0}": "保存方案失败：{0}",
        "Failed to delete profile: {0}": "删除方案失败：{0}",
        "--- Starting Task with Profile: {0} ---": "--- 开始任务，当前方案：{0} ---",
        "--- Runtime Mode: {0} | lines={1} | batch={2}/{3} | chars={4} | text_chars={5} | max_tokens={6} | timeout={7}s | threshold={8:.2f} | split={9} | resume={10} | isolate={11} | api_protocol={12} ---": "--- 运行模式：{0} | lines={1} | batch={2}/{3} | chars={4} | text_chars={5} | max_tokens={6} | timeout={7}s | threshold={8:.2f} | split={9} | resume={10} | isolate={11} | api_protocol={12} ---",
        "Stopping... (Waiting for current PDF to finish or hit timeout)": "正在停止...（等待当前 PDF 处理完成或超时）",
        "Error: {0}": "错误：{0}",
        "=== Starting Task with Profile: {0} ===": "=== 开始任务，当前方案：{0} ===",
        "Initializing Classifier...": "正在初始化分类器...",
        "  > Processing Mode: {0}": "  > 处理模式：{0}",
        "  > Lines per PDF: {0}": "  > 每篇 PDF 提取行数：{0}",
        "  > Batch Size/Fallback: {0}/{1}": "  > 批次大小/回退批次：{0}/{1}",
        "  > Prompt Char Budget: {0}": "  > 提示词字符预算：{0}",
        "  > Text Chars Per File: {0}": "  > 每文件文本字符数：{0}",
        "  > LLM Max Tokens: {0}": "  > LLM 最大 Tokens：{0}",
        "  > LLM Timeout(s): {0}": "  > LLM 超时（秒）：{0}",
        "  > Per-PDF Extract Timeout(s): {0}": "  > 单篇 PDF 提取超时（秒）：{0}",
        "  > Auto Split Failed Batches: {0}": "  > 自动拆分失败批次：{0}",
        "  > Resume Interrupted Runs: {0}": "  > 恢复中断运行：{0}",
        "  > V2 separate folder per run: {0}": "  > V2 每次运行独立文件夹：{0}",
        "  > Include Threshold: {0:.2f}": "  > 通过阈值：{0:.2f}",
        "  > Loaded Required Keywords: {0}...": "  > 已加载核心关键词：{0}...",
        "  > Target Taxonomic Group: {0}": "  > 目标分类群：{0}",
        "Starting Batch Classification...": "开始批量分类...",
        "  > Resumed interrupted V2 run.": "  > 已恢复中断的 V2 运行。",
        "  > Run Output Directory: {0}": "  > 运行输出目录：{0}",
        "  > Run Status: {0}": "  > 运行状态：{0}",
        "  > Partial results were saved to disk.": "  > 部分结果已保存到磁盘。",
        "Initializing Extractor...": "正在初始化提取器...",
        "No PDF files found in input directory.": "输入目录中未找到 PDF 文件。",
        "Processing {0}/{1}: {2}": "正在处理 {0}/{1}：{2}",
        "  > Figures: {0}, Accepted: {1}, Review: {2}": "  > 图像：{0}，接受：{1}，复核：{2}",
        "  > Failed: {0}": "  > 失败：{0}",
        "  > WARNING: {0} figure(s) in this PDF used mock/default review because real multimodal review was turned OFF at startup. They were placed into Review instead of true acceptance.": "  > 警告：该 PDF 中有 {0} 张图片因启动时关闭了真实多模态复核而使用了 mock/default 复核，因此被放入 Review，而不是真正接受。",
        "  > WARNING: {0} figure(s) in this PDF used mock/default review because real multimodal review could not start at startup{1}. They were placed into Review instead of true acceptance.": "  > 警告：该 PDF 中有 {0} 张图片因真实多模态复核在启动时无法开始{1}，而使用了 mock/default 复核，因此被放入 Review，而不是真正接受。",
        "  > WARNING: {0} figure(s) in this PDF used mock/default review because real multimodal review was not actually configured at startup{1}. They were placed into Review instead of true acceptance.": "  > 警告：该 PDF 中有 {0} 张图片因启动时并未真正配置真实多模态复核{1}，而使用了 mock/default 复核，因此被放入 Review，而不是真正接受。",
        "  > WARNING: Real multimodal review did not fully run for this PDF. {0} figure(s) fell back to mock/default review after runtime failures, so they were placed into Review instead of true acceptance.": "  > 警告：该 PDF 的真实多模态复核未完整运行。{0} 张图片在运行时失败后回退到 mock/default 复核，因此被放入 Review，而不是真正接受。",
        "  > WARNING: {0} figure(s) in this PDF did not receive real multimodal review. They were placed into Review instead of true acceptance.": "  > 警告：该 PDF 中有 {0} 张图片未获得真实多模态复核，因此被放入 Review，而不是真正接受。"
    }
}


def translate_pdf_text(text, lang="en"):
    if lang == "zh":
        return TRANSLATIONS["zh"].get(text, text)
    return text

class DatabaseViewerDialog(QDialog):
    def __init__(self, db_path, parent=None, lang="en"):
        super().__init__(parent)
        self.db_path = db_path
        self.lang = lang
        self.setWindowTitle(self.tr("Database Viewer"))
        self.resize(1200, 800)
        self.init_ui()
        self.load_data()

    def tr(self, text):
        if self.lang == "zh":
            return TRANSLATIONS["zh"].get(text, text)
        return text

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: Table
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        splitter.addWidget(self.table)
        
        # Right: Details (Image + Text)
        right_panel = QWidget()
        r_layout = QVBoxLayout(right_panel)
        
        self.lbl_img = QLabel(self.tr("Image Preview"))
        self.lbl_img.setAlignment(Qt.AlignCenter)
        self.lbl_img.setMinimumSize(400, 400)
        self.lbl_img.setStyleSheet("border: 1px dashed #666; background-color: #333;")
        r_layout.addWidget(self.lbl_img)
        
        r_layout.addWidget(QLabel(self.tr("Text Context")))
        self.txt_context = QTextEdit()
        self.txt_context.setReadOnly(True)
        r_layout.addWidget(self.txt_context)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([600, 600])
        
        layout.addWidget(splitter)
        
        btn_close = QPushButton(self.tr("Close"))
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def load_data(self):
        if not os.path.exists(self.db_path):
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='figure_records'")
            has_v2_table = cursor.fetchone() is not None

            if has_v2_table:
                query = """
                    SELECT id, image_file_name, image_file_path, final_confidence, accepted, page_number, species_candidate
                    FROM figure_records
                    ORDER BY id DESC
                    LIMIT 500
                """
                cursor.execute(query)
                rows = cursor.fetchall()
                self.table.setColumnCount(7)
                self.table.setHorizontalHeaderLabels([
                    self.tr("ID"),
                    self.tr("Filename"),
                    self.tr("Path"),
                    self.tr("Score"),
                    self.tr("Accepted"),
                    self.tr("Page"),
                    self.tr("Species"),
                ])
            else:
                query = """
                    SELECT i.id, i.image_file_name, i.image_file_path, i.confidence_score, i.is_taxonomic
                    FROM images i
                    ORDER BY i.id DESC
                    LIMIT 500
                """
                cursor.execute(query)
                rows = cursor.fetchall()
                self.table.setColumnCount(5)
                self.table.setHorizontalHeaderLabels([
                    self.tr("ID"),
                    self.tr("Filename"),
                    self.tr("Path"),
                    self.tr("Score"),
                    self.tr("Taxonomic"),
                ])
            self.table.setRowCount(len(rows))
            
            for i, row in enumerate(rows):
                for j, val in enumerate(row):
                    self.table.setItem(i, j, QTableWidgetItem(str(val)))
            
            conn.close()
        except Exception as e:
            QMessageBox.warning(self, self.tr("Error"), self.tr("DB Error: {0}").format(e))

    def on_row_selected(self):
        items = self.table.selectedItems()
        if not items: return
        
        row = items[0].row()
        image_id = self.table.item(row, 0).text() # ID is column 0
        img_path = self.table.item(row, 2).text()
        
        # Load Image
        if os.path.exists(img_path):
            pix = QPixmap(img_path)
            if not pix.isNull():
                self.lbl_img.setPixmap(pix.scaled(self.lbl_img.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.lbl_img.setText(self.tr("Invalid Image File"))
        else:
            self.lbl_img.setText(self.tr("Image not found on disk"))
            
        # Query related text
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='figure_records'")
            has_v2_table = cursor.fetchone() is not None

            if has_v2_table:
                cursor.execute(
                    """
                    SELECT page_number, species_candidate, category, review_status, rejection_reason, caption_text,
                           multimodal_validated, multimodal_review_mode, multimodal_model_used
                    FROM figure_records
                    WHERE id = ?
                    """,
                    (image_id,),
                )
                figure_row = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT evidence_level, evidence_type, text_content, match_score, section_title
                    FROM figure_evidence
                    WHERE figure_id = ?
                    ORDER BY CASE evidence_level
                        WHEN 'figure_local' THEN 1
                        WHEN 'species_core' THEN 2
                        ELSE 3
                    END, match_score DESC, id ASC
                    """,
                    (image_id,),
                )
                rows = cursor.fetchall()

                display_text = self.tr("File: {0}\n").format(img_path)
                if figure_row:
                    page_number, species_candidate, category, review_status, rejection_reason, caption_text, multimodal_validated, review_mode, model_used = figure_row
                    multimodal_text = 'real' if multimodal_validated else review_mode or 'none'
                    display_text += self.tr("Page: {0}\nSpecies: {1}\nCategory: {2}\nStatus: {3}\nMultimodal: {4}\n").format(
                        page_number,
                        species_candidate or 'Unknown',
                        category,
                        review_status,
                        multimodal_text,
                    )
                    if model_used:
                        display_text += self.tr("Model: {0}\n").format(model_used)
                    if rejection_reason:
                        display_text += self.tr("Reject Reason: {0}\n").format(rejection_reason)
                    if caption_text:
                        display_text += self.tr("\n--- Caption ---\n{0}\n").format(caption_text)
                if rows:
                    display_text += self.tr("\n--- Evidence ---\n")
                    for level, evidence_type, content, score, section_title in rows:
                        title_part = f" | {section_title}" if section_title else ""
                        display_text += f"[{level} | {evidence_type}{title_part} | score={score:.3f}]\n{content}\n\n"
                else:
                    display_text += self.tr("\n(No related evidence found in DB)")
                self.txt_context.setText(display_text)
            else:
                query = """
                    SELECT t.text_type, t.text_content, r.confidence_level
                    FROM image_text_relations r
                    JOIN text_blocks t ON r.text_block_id = t.id
                    WHERE r.image_id = ?
                    ORDER BY r.correlation_score DESC
                """
                cursor.execute(query, (image_id,))
                rows = cursor.fetchall()
                
                if rows:
                    display_text = self.tr("File: {0}\n").format(img_path) + self.tr("\n\n--- Related Text ---\n")
                    for t_type, content, conf in rows:
                        display_text += self.tr("[{0} | {1}]: {2}\n\n").format(t_type.upper(), conf, content)
                    self.txt_context.setText(display_text)
                else:
                    self.txt_context.setText(self.tr("File: {0}\n").format(img_path) + self.tr("\n\n(No related text found in DB)"))
            
            conn.close()
        except Exception as e:
            self.txt_context.setText(self.tr("Error querying text: {0}").format(e))

class CSVViewerDialog(QDialog):
    def __init__(self, csv_path, parent=None, lang="en"):
        super().__init__(parent)
        self.csv_path = csv_path
        self.lang = lang
        self.setWindowTitle(self.tr("CSV Viewer"))
        self.resize(1000, 600)
        self.init_ui()
        self.load_csv()

    def tr(self, text):
        if self.lang == "zh":
            return TRANSLATIONS["zh"].get(text, text)
        return text

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        layout.addWidget(self.table)
        
        btn_close = QPushButton(self.tr("Close"))
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def load_csv(self):
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if not headers: return
                
                self.table.setColumnCount(len(headers))
                self.table.setHorizontalHeaderLabels(headers)
                
                rows = list(reader)
                self.table.setRowCount(len(rows))
                
                for i, row in enumerate(rows):
                    for j, val in enumerate(row):
                        item = QTableWidgetItem(val)
                        self.table.setItem(i, j, item)
                
                self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
                self.table.horizontalHeader().setStretchLastSection(True)
        except Exception as e:
            QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to load CSV: {0}").format(e))

class ScreenerConfigDialog(QDialog):
    def __init__(self, current_config, profile_name="New_Profile", is_default=False, parent=None, lang="en", current_mode="v2"):
        super().__init__(parent)
        self.config = current_config.copy()
        self.profile_name = profile_name
        self.is_default = is_default # If true, prevent overwrite
        self.lang = lang
        self.current_mode = current_mode
        self.current_theme = _resolve_active_theme(parent)
        self.save_action = None # 'new' or 'overwrite'
        self.setWindowTitle(self.tr("Advanced Logic Settings"))
        self.resize(800, 750)
        self.setStyleSheet(get_theme_stylesheet(self.current_theme))
        self.init_ui()

    def _theme_config(self):
        return get_theme_config(self.current_theme)

    def _apply_text_edit_theme(self, edit: QTextEdit) -> None:
        c = self._theme_config()
        edit.setStyleSheet(
            f"QTextEdit {{ background-color: {c['bg_input']}; color: {c['text_main']}; "
            f"border: 1px solid {c['border']}; border-radius: 8px; padding: 6px 10px; "
            f"selection-background-color: {c['accent_soft']}; }}"
            f"QTextEdit:focus {{ border: 1px solid {c['accent']}; }}"
        )

    def tr(self, text):
        if self.lang == "zh":
            return TRANSLATIONS["zh"].get(text, text)
        return text

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Profile Name Info
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel(self.tr("Profile Name:")))
        self.edit_profile_name = QLineEdit(self.profile_name)
        if self.is_default:
            self.edit_profile_name.setReadOnly(True)
            c = get_theme_config(self.current_theme)
            self.edit_profile_name.setStyleSheet(
                f"background-color: {c['bg_panel']}; color: {c['text_dim']}; "
                f"border: 1px solid {c['border']}; border-radius: 8px; padding: 6px 8px;"
            )
        top_layout.addWidget(self.edit_profile_name)
        layout.addLayout(top_layout)

        mode_note = QLabel(self.tr("Keyword lists are editable helper lexicons for V2 screening. The LLM prompt defines the final biological decision criteria."))
        mode_note.setWordWrap(True)
        mode_note.setStyleSheet(f"color: {get_theme_config(self.current_theme)['text_dim']};")
        layout.addWidget(mode_note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        c_layout = QVBoxLayout(container)
        
        # Keywords
        kw_group = QGroupBox(self.tr("Keyword Assist Lexicon"))
        apply_surface_role(kw_group, SURFACE_ROLE_SUBTLE, "screenerKeywordLexiconGroup")
        kw_layout = QVBoxLayout(kw_group)
        
        self.edits = {}
        fields = [
            ("required_keywords", "Required Keywords (e.g. 'sp. nov.'):"),
            ("supportive_keywords", "Supportive Keywords (e.g. 'morphology'):"),
            ("taxonomic_group_keywords", "Taxonomic Group Keywords (e.g. 'ant'):"),
            ("strong_exclude_keywords", "Strong Exclude (e.g. 'ecology'):"),
            ("weak_exclude_keywords", "Weak Exclude (e.g. 'note'):"),
            ("biological_exclude_keywords", "Biological Exclude (e.g. 'virus'):")
        ]
        
        for key, label in fields:
            kw_layout.addWidget(QLabel(self.tr(label)))
            edit = QTextEdit()
            edit.setAcceptRichText(False)
            edit.setPlaceholderText(self.tr("Comma separated keywords..."))
            edit.setMaximumHeight(80)
            self._apply_text_edit_theme(edit)
            val = self.config.get(key, [])
            edit.setPlainText(", ".join(val))
            kw_layout.addWidget(edit)
            self.edits[key] = edit
            
        self.chk_show_legacy_kw = QCheckBox(self.tr("Show Keyword Lexicons"))
        self.chk_show_legacy_kw.setChecked(True)
        self.chk_show_legacy_kw.toggled.connect(kw_group.setVisible)
        c_layout.addWidget(self.chk_show_legacy_kw)
        kw_group.setVisible(True)
        c_layout.addWidget(kw_group)
        
        # LLM Prompt
        prompt_group = QGroupBox(self.tr("LLM Prompt (V2 Core):"))
        apply_surface_role(prompt_group, SURFACE_ROLE_SUBTLE, "screenerPromptGroup")
        p_layout = QVBoxLayout(prompt_group)
        p_layout.addWidget(QLabel(self.tr("System Prompt:")))
        self.edit_system_prompt = QTextEdit()
        self.edit_system_prompt.setAcceptRichText(False)
        self.edit_system_prompt.setMaximumHeight(70)
        self._apply_text_edit_theme(self.edit_system_prompt)
        self.edit_system_prompt.setPlainText(
            self.config.get("llm_system_prompt", LLMScreenPDFClassifier.DEFAULT_CONFIG.get("llm_system_prompt", ""))
        )
        p_layout.addWidget(self.edit_system_prompt)
        p_layout.addWidget(QLabel(self.tr("Placeholders: {records_json}, {expected_record_count}, {expected_record_ids_json}, {batch_id}.")))
        self.edit_prompt = QTextEdit()
        self.edit_prompt.setMinimumHeight(350)
        self._apply_text_edit_theme(self.edit_prompt)
        self.edit_prompt.setPlainText(
            self.config.get("llm_batch_prompt_template", self.config.get("llm_prompt_template", ""))
        )
        p_layout.addWidget(self.edit_prompt)
        c_layout.addWidget(prompt_group)
        
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_reset = QPushButton(self.tr("Reset to Default"))
        btn_reset.clicked.connect(self.reset_to_default)
        apply_theme_button_style(btn_reset, BUTTON_ROLE_NEUTRAL, theme=self.current_theme)
        
        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()

        if not self.is_default:
            self.btn_overwrite = QPushButton(self.tr("Overwrite Current"))
            self.btn_overwrite.clicked.connect(lambda: self.save_config('overwrite'))
            apply_theme_button_style(self.btn_overwrite, BUTTON_ROLE_COMMIT, "font-weight: bold; padding: 8px;", self.current_theme)
            btn_layout.addWidget(self.btn_overwrite)
        
        self.btn_save_new = QPushButton(self.tr("Save as New Profile"))
        self.btn_save_new.clicked.connect(lambda: self.save_config('new'))
        apply_theme_button_style(self.btn_save_new, BUTTON_ROLE_COMMIT, "font-weight: bold; padding: 8px;", self.current_theme)
        btn_layout.addWidget(self.btn_save_new)
        
        btn_close = QPushButton(self.tr("Close"))
        btn_close.clicked.connect(self.reject)
        apply_theme_button_style(btn_close, BUTTON_ROLE_NEUTRAL, theme=self.current_theme)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)

    def reset_to_default(self):
        default = LLMScreenPDFClassifier.DEFAULT_CONFIG
        for key, edit in self.edits.items():
            edit.setPlainText(", ".join(default.get(key, [])))
        self.edit_prompt.setPlainText(
            default.get("llm_batch_prompt_template", default.get("llm_prompt_template", ""))
        )
        self.edit_system_prompt.setPlainText(default.get("llm_system_prompt", ""))

    def save_config(self, action):
        self.save_action = action
        self.profile_name = self.edit_profile_name.text().strip()
        if not self.profile_name:
            QMessageBox.warning(self, self.tr("Error"), self.tr("Profile name cannot be empty."))
            return

        for key, edit in self.edits.items():
            text = edit.toPlainText()
            keywords = [k.strip() for k in text.split(",") if k.strip()]
            self.config[key] = keywords
        
        prompt_text = self.edit_prompt.toPlainText()
        self.config["llm_system_prompt"] = self.edit_system_prompt.toPlainText()
        self.config["llm_batch_prompt_template"] = prompt_text
        self.config["llm_prompt_template"] = prompt_text
        self.accept()

    def get_result(self):
        return self.config, self.profile_name, self.save_action

class FigureProfileDialog(QDialog):
    def __init__(self, current_profile, profile_name="New_Figure_Profile", is_default=False, parent=None, lang="en"):
        super().__init__(parent)
        self.profile = deepcopy(current_profile)
        self.profile_name = profile_name
        self.is_default = is_default
        self.lang = lang
        self.current_theme = _resolve_active_theme(parent)
        self.save_action = None
        self.setWindowTitle(self.tr("Advanced Figure Settings"))
        self.resize(850, 760)
        self.setStyleSheet(get_theme_stylesheet(self.current_theme))
        self.init_ui()

    def tr(self, text):
        if self.lang == "zh":
            return TRANSLATIONS["zh"].get(text, text)
        return text

    def init_ui(self):
        layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel(self.tr("Profile Name:")))
        self.edit_profile_name = QLineEdit(self.profile_name)
        if self.is_default:
            self.edit_profile_name.setReadOnly(True)
        top_layout.addWidget(self.edit_profile_name)
        layout.addLayout(top_layout)

        note = QLabel(self.tr("Edit the figure extraction and multimodal review profile JSON. API keys are not stored here."))
        note.setWordWrap(True)
        layout.addWidget(note)

        self.edit_json = QTextEdit()
        self.edit_json.setAcceptRichText(False)
        self.edit_json.setPlainText(json.dumps(self.profile, ensure_ascii=False, indent=2))
        layout.addWidget(self.edit_json)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        if not self.is_default:
            btn_overwrite = QPushButton(self.tr("Overwrite Current"))
            btn_overwrite.clicked.connect(lambda: self.save_config("overwrite"))
            apply_theme_button_style(btn_overwrite, BUTTON_ROLE_COMMIT, "font-weight: bold; padding: 8px;", self.current_theme)
            btn_layout.addWidget(btn_overwrite)
        btn_save_new = QPushButton(self.tr("Save as New Profile"))
        btn_save_new.clicked.connect(lambda: self.save_config("new"))
        apply_theme_button_style(btn_save_new, BUTTON_ROLE_COMMIT, "font-weight: bold; padding: 8px;", self.current_theme)
        btn_layout.addWidget(btn_save_new)
        btn_close = QPushButton(self.tr("Close"))
        btn_close.clicked.connect(self.reject)
        apply_theme_button_style(btn_close, BUTTON_ROLE_NEUTRAL, theme=self.current_theme)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def save_config(self, action):
        name = self.edit_profile_name.text().strip()
        if not name:
            QMessageBox.warning(self, self.tr("Error"), self.tr("Profile name cannot be empty."))
            return
        try:
            payload = json.loads(self.edit_json.toPlainText())
            if not isinstance(payload, dict):
                raise ValueError("profile_root_not_object")
            payload["profile_name"] = name
            payload = normalize_figure_profile(payload)
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Error"), self.tr("Invalid figure profile JSON: {0}").format(exc))
            return
        self.profile = payload
        self.profile_name = name
        self.save_action = action
        self.accept()

    def get_result(self):
        return self.profile, self.profile_name, self.save_action

class ProcessingResultDialog(QDialog):
    def __init__(self, txt_path, csv_path, parent=None, lang="en"):
        super().__init__(parent)
        self.txt_path = txt_path
        self.csv_path = csv_path
        self.lang = lang
        self.setWindowTitle(self.tr("Processing Results"))
        self.resize(500, 400)
        self.init_ui()
        self.load_txt()

    def tr(self, text):
        if self.lang == "zh":
            return TRANSLATIONS["zh"].get(text, text)
        return text

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel(self.tr("Summary")))
        self.txt_view = QTextEdit()
        self.txt_view.setReadOnly(True)
        layout.addWidget(self.txt_view)
        
        btn_layout = QHBoxLayout()
        if self.csv_path and os.path.exists(self.csv_path):
            self.btn_csv = QPushButton(self.tr("View Detailed CSV"))
            self.btn_csv.clicked.connect(self.open_csv)
            apply_semantic_button_style(self.btn_csv, BUTTON_ROLE_NEUTRAL, "font-weight: bold; padding: 8px;")
            btn_layout.addWidget(self.btn_csv)
            
        self.btn_close = QPushButton(self.tr("Close"))
        self.btn_close.clicked.connect(self.accept)
        apply_semantic_button_style(self.btn_close, BUTTON_ROLE_NEUTRAL)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)

    def load_txt(self):
        if self.txt_path and os.path.exists(self.txt_path):
            try:
                with open(self.txt_path, 'r', encoding='utf-8') as f:
                    self.txt_view.setText(f.read())
            except Exception as e:
                self.txt_view.setText(self.tr("Error loading summary: {0}").format(e))
        else:
            self.txt_view.setText(self.tr("No summary file generated."))

    def open_csv(self):
        viewer = CSVViewerDialog(self.csv_path, self, self.lang)
        viewer.exec()

class PDFWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int, int) # current, total
    result_signal = Signal(dict) # result paths
    finished_signal = Signal()
    
    def __init__(self, task_type, lang="en", **kwargs):
        super().__init__()
        self.task_type = task_type
        self.lang = lang
        self.kwargs = kwargs
        self._is_running = True

    def tr(self, text):
        return translate_pdf_text(text, self.lang)

    def run(self):
        result_paths = {}
        try:
            if self.task_type == "classify":
                result_paths = self.run_classify()
            elif self.task_type == "extract":
                self.run_extract()
                # Extractor mainly populates DB, we could return DB path
                result_paths = {"db": self.kwargs['db_path']}
        except Exception as e:
            self.log_signal.emit(self.tr("Error: {0}").format(str(e)))
            import traceback
            self.log_signal.emit(traceback.format_exc())
        finally:
            self.result_signal.emit(result_paths)
            self.finished_signal.emit()

    def check_stop(self):
        return not self._is_running

    def report_progress(self, current, total):
        self.progress_signal.emit(current, total)

    def _log_extract_startup_warning(self, extractor):
        startup_state = {}
        if hasattr(extractor, "get_multimodal_startup_state"):
            try:
                startup_state = extractor.get_multimodal_startup_state()
            except Exception:
                startup_state = {}
        if bool(startup_state.get("real_multimodal_configured", False)):
            return
        message = str(startup_state.get("warning_message", "") or "").strip()
        if message:
            self.log_signal.emit(message)

    def _log_extract_pdf_warnings(self, stats):
        startup_mock_count = int(stats.get("startup_mock_review_figures", 0) or 0)
        runtime_fallback_count = int(stats.get("runtime_fallback_review_figures", 0) or 0)
        non_real_count = int(stats.get("non_real_multimodal_figures", 0) or 0)
        startup_status = str(stats.get("multimodal_startup_status", "") or "").strip().lower()
        startup_reason = str(stats.get("multimodal_startup_reason", "") or "").strip()
        startup_detail = f" ({startup_reason})" if startup_reason and startup_status != "disabled" else ""

        if startup_mock_count > 0:
            if startup_status == "disabled":
                self.log_signal.emit(
                    self.tr("  > WARNING: {0} figure(s) in this PDF used mock/default review because real multimodal review was turned OFF at startup. They were placed into Review instead of true acceptance.").format(startup_mock_count)
                )
            elif startup_status == "init_failed":
                self.log_signal.emit(
                    self.tr("  > WARNING: {0} figure(s) in this PDF used mock/default review because real multimodal review could not start at startup{1}. They were placed into Review instead of true acceptance.").format(startup_mock_count, startup_detail)
                )
            else:
                self.log_signal.emit(
                    self.tr("  > WARNING: {0} figure(s) in this PDF used mock/default review because real multimodal review was not actually configured at startup{1}. They were placed into Review instead of true acceptance.").format(startup_mock_count, startup_detail)
                )

        if runtime_fallback_count > 0:
            self.log_signal.emit(
                self.tr("  > WARNING: Real multimodal review did not fully run for this PDF. {0} figure(s) fell back to mock/default review after runtime failures, so they were placed into Review instead of true acceptance.").format(runtime_fallback_count)
            )

        if startup_mock_count == 0 and runtime_fallback_count == 0 and non_real_count > 0:
            self.log_signal.emit(
                self.tr("  > WARNING: {0} figure(s) in this PDF did not receive real multimodal review. They were placed into Review instead of true acceptance.").format(non_real_count)
            )

    def run_classify(self):
        profile_name = self.kwargs.get('profile_name', 'Unknown')
        self.log_signal.emit(self.tr("=== Starting Task with Profile: {0} ===").format(profile_name))
        self.log_signal.emit(self.tr("Initializing Classifier..."))
        
        classifier = LLMScreenPDFClassifier(
            source_folder=self.kwargs['source'],
            output_folder=self.kwargs['output'],
            api_key=self.kwargs.get('api_key'),
            base_url=self.kwargs.get('base_url'),
            model=self.kwargs.get('model', 'gpt-5.4'),
            config=self.kwargs.get('screener_config')
        )
        
        # Log key config details to UI for confirmation
        req_kw = ", ".join(classifier.required_keywords[:3])
        tax_kw = ", ".join(classifier.taxonomic_group_keywords)
        self.log_signal.emit(self.tr("  > Processing Mode: {0}").format(classifier.processing_mode))
        self.log_signal.emit(self.tr("  > Lines per PDF: {0}").format(classifier.lines_per_pdf))
        self.log_signal.emit(self.tr("  > Batch Size/Fallback: {0}/{1}").format(classifier.csv_batch_size, classifier.csv_batch_fallback_size))
        self.log_signal.emit(self.tr("  > Prompt Char Budget: {0}").format(classifier.batch_char_budget))
        self.log_signal.emit(self.tr("  > Text Chars Per File: {0}").format(classifier.max_text_chars_per_file))
        self.log_signal.emit(self.tr("  > LLM Max Tokens: {0}").format(classifier.llm_batch_max_tokens))
        self.log_signal.emit(self.tr("  > LLM Timeout(s): {0}").format(classifier.llm_request_timeout_seconds))
        self.log_signal.emit(self.tr("  > Per-PDF Extract Timeout(s): {0}").format(classifier.pdf_extract_timeout_seconds))
        self.log_signal.emit(self.tr("  > Auto Split Failed Batches: {0}").format(classifier.split_failed_batches))
        self.log_signal.emit(self.tr("  > Resume Interrupted Runs: {0}").format(classifier.resume_interrupted_runs))
        self.log_signal.emit(self.tr("  > V2 separate folder per run: {0}").format(classifier.isolate_v2_runs))
        self.log_signal.emit(self.tr("  > Include Threshold: {0:.2f}").format(classifier.include_confidence_threshold))
        self.log_signal.emit(self.tr("  > Loaded Required Keywords: {0}...").format(req_kw))
        self.log_signal.emit(self.tr("  > Target Taxonomic Group: {0}").format(tax_kw))
        
        self.log_signal.emit(self.tr("Starting Batch Classification..."))
        
        # Pass callbacks
        results = classifier.batch_classify(
            check_stop_callback=self.check_stop,
            progress_callback=self.report_progress
        )

        if isinstance(results, dict):
            run_output_dir = str(results.get('_run_output_dir') or '').strip()
            run_status = str(results.get('_run_status') or '').strip()
            resumed = bool(results.get('_resumed'))
            resume_skip_messages = list(results.get('_resume_skip_messages') or [])
            if resumed:
                self.log_signal.emit(self.tr("  > Resumed interrupted V2 run."))
            elif resume_skip_messages:
                for message in resume_skip_messages:
                    self.log_signal.emit(f"  > {message}")
            if run_output_dir:
                self.log_signal.emit(self.tr("  > Run Output Directory: {0}").format(run_output_dir))
            if run_status:
                self.log_signal.emit(self.tr("  > Run Status: {0}").format(run_status))
        
        paths = {}
        if isinstance(results, dict) and results.get("_stats_path"):
            paths['txt'] = results.get("_stats_path")
        elif isinstance(results, dict):
            paths['txt'] = os.path.join(self.kwargs['output'], "classification_statistics.txt")

        if isinstance(results, dict) and results.get("_csv_path"):
            paths['csv'] = results.get("_csv_path")
        elif classifier.processing_mode == "v2":
            paths['csv'] = os.path.join(self.kwargs['output'], "master_results.csv")
        else:
            paths['csv'] = os.path.join(self.kwargs['output'], "llm_enhanced_classification_details.csv")

        if not self._is_running:
            self.log_signal.emit(self.tr("Process stopped by user."))
            if isinstance(results, dict) and str(results.get('_run_status') or '').strip() in {'stopped', 'partial'}:
                self.log_signal.emit(self.tr("  > Partial results were saved to disk."))
        else:
            self.log_signal.emit(self.tr("Classification Finished."))
            
        return paths

    def run_extract(self):
        figure_profile_name = self.kwargs.get('figure_profile_name', 'Unknown')
        self.log_signal.emit(self.tr("Initializing Extractor..."))
        self.log_signal.emit(self.tr("  > Figure Profile: {0}").format(figure_profile_name))
        extractor = EnhancedPDFExtractionSystem(
            output_db_path=self.kwargs['db_path'],
            save_images_to_files=True, 
            enable_multimodal_validation=self.kwargs.get('use_mllm', False),
            multimodal_config=self.kwargs.get('mllm_config'),
            figure_profile=self.kwargs.get('figure_profile'),
            figure_profile_path=self.kwargs.get('figure_profile_path')
        )
        self._log_extract_startup_warning(extractor)
        
        pdf_dir = self.kwargs['pdf_dir']
        pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
        
        total = len(pdf_files)
        if total == 0:
            self.log_signal.emit(self.tr("No PDF files found in input directory."))
            return

        for i, pdf_file in enumerate(pdf_files):
            if not self._is_running: 
                self.log_signal.emit(self.tr("Process stopped by user."))
                break
            
            self.report_progress(i + 1, total)
                
            self.log_signal.emit(self.tr("Processing {0}/{1}: {2}").format(i + 1, total, pdf_file))
            pdf_path = os.path.join(pdf_dir, pdf_file)
            try:
                res = extractor.extract_from_pdf(pdf_path)
                stats = res.get('stats', {})
                self.log_signal.emit(
                    self.tr("  > Figures: {0}, Accepted: {1}, Review: {2}").format(
                        stats.get('total_figures', stats.get('total_images', 0)),
                        stats.get('accepted_figures', stats.get('taxonomic_images', 0)),
                        stats.get('review_queue_figures', 0),
                    )
                )
                self._log_extract_pdf_warnings(stats)
            except Exception as e:
                self.log_signal.emit(self.tr("  > Failed: {0}").format(e))
        
        extractor.close()
        self.log_signal.emit(self.tr("Extraction Pipeline Completed."))

    def stop(self):
        self._is_running = False

class PdfProcessingWidget(QWidget):
    def __init__(self, current_lang="en", parent=None):
        super().__init__(parent)
        self.current_lang = current_lang
        self.current_theme = "dark"
        # Directory for multiple profiles
        self.configs_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'screener_configs')
        if not os.path.exists(self.configs_dir):
            os.makedirs(self.configs_dir)
        self.api_settings_file = os.path.join(self.configs_dir, "api_runtime_settings.json")
        self.figure_configs_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'multimodal_configs')
        if not os.path.exists(self.figure_configs_dir):
            os.makedirs(self.figure_configs_dir)
             
        self.screener_config = LLMScreenPDFClassifier.DEFAULT_CONFIG.copy()
        self.current_profile_name = "Default_Ant_Logic"
        self.figure_profile = normalize_figure_profile(None)
        self.current_figure_profile_name = profile_display_name(self.figure_profile)
        self.current_figure_profile_path = ""
        
        self.init_ui()
        self.load_api_settings()
        self.worker = None
        self.refresh_profile_list()
        self.refresh_figure_profile_list()
        self.sync_runtime_controls_from_config()
        self.retranslate_ui()

    def _normalize_mode(self, mode_value, default_mode="v2"):
        return "v2"

    def _default_config_for_mode(self, mode):
        config = deepcopy(LLMScreenPDFClassifier.DEFAULT_CONFIG)
        config["processing_mode"] = self._normalize_mode(mode)
        return config

    def _profile_mode_from_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                raw_mode = str(payload.get("processing_mode", "v2") or "v2").strip().lower()
                return "legacy" if raw_mode == "legacy" else "v2"
        except Exception:
            pass
        return "v2"

    def load_api_settings(self):
        if not os.path.exists(self.api_settings_file):
            self.update_mllm_api_controls_enabled()
            return

        try:
            with open(self.api_settings_file, 'r', encoding='utf-8') as handle:
                payload = json.load(handle)

            if not isinstance(payload, dict):
                return

            text_payload = payload.get("text_llm") if isinstance(payload.get("text_llm"), dict) else payload
            multimodal_payload = payload.get("multimodal_llm") if isinstance(payload.get("multimodal_llm"), dict) else {}

            base_url = str(text_payload.get("base_url", "")).strip()
            model = str(text_payload.get("model", "")).strip()
            api_protocol = str(text_payload.get("api_protocol", "auto")).strip().lower()
            remember_key = bool(text_payload.get("remember_api_key", False))
            api_key = str(text_payload.get("api_key", "")) if remember_key else ""

            if base_url:
                self.edit_base_url.setText(base_url)
            if model:
                self.edit_model.setText(model)

            protocol_index = self.combo_api_protocol.findData(api_protocol)
            if protocol_index >= 0:
                self.combo_api_protocol.setCurrentIndex(protocol_index)

            self.chk_remember_api_key.setChecked(remember_key)
            self.edit_api_key.setText(api_key)

            use_same = bool(multimodal_payload.get("use_same_as_text", True))
            self.check_mllm_same_as_text.setChecked(use_same)
            mllm_base_url = str(multimodal_payload.get("base_url", "")).strip()
            mllm_model = str(multimodal_payload.get("model", "")).strip()
            mllm_protocol = str(multimodal_payload.get("api_protocol", "auto")).strip().lower()
            mllm_image_detail = str(multimodal_payload.get("image_detail", "auto")).strip().lower()
            remember_mllm_key = bool(multimodal_payload.get("remember_api_key", False))
            mllm_api_key = str(multimodal_payload.get("api_key", "")) if remember_mllm_key else ""
            if mllm_base_url:
                self.edit_mllm_base_url.setText(mllm_base_url)
            if mllm_model:
                self.edit_mllm_model.setText(mllm_model)
            mllm_protocol_index = self.combo_mllm_api_protocol.findData(mllm_protocol)
            if mllm_protocol_index >= 0:
                self.combo_mllm_api_protocol.setCurrentIndex(mllm_protocol_index)
            image_detail_index = self.combo_mllm_image_detail.findData(mllm_image_detail)
            if image_detail_index >= 0:
                self.combo_mllm_image_detail.setCurrentIndex(image_detail_index)
            self.chk_remember_mllm_api_key.setChecked(remember_mllm_key)
            self.edit_mllm_api_key.setText(mllm_api_key)
            self.update_mllm_api_controls_enabled()
        except Exception as exc:
            self.log(self.tr("Failed to load API settings: {}").format(exc))

    def save_api_settings(self):
        remember_key = self.chk_remember_api_key.isChecked()
        remember_mllm_key = self.chk_remember_mllm_api_key.isChecked()
        payload = {
            "schema_version": "taxamask-api-runtime-settings-v2",
            "text_llm": {
                "base_url": self.edit_base_url.text().strip(),
                "model": self.edit_model.text().strip(),
                "api_protocol": self.combo_api_protocol.currentData() or "auto",
                "remember_api_key": remember_key,
                "api_key": self.edit_api_key.text().strip() if remember_key else "",
            },
            "multimodal_llm": {
                "use_same_as_text": self.check_mllm_same_as_text.isChecked(),
                "base_url": self.edit_mllm_base_url.text().strip(),
                "model": self.edit_mllm_model.text().strip(),
                "api_protocol": self.combo_mllm_api_protocol.currentData() or "auto",
                "image_detail": self.combo_mllm_image_detail.currentData() or "auto",
                "remember_api_key": remember_mllm_key,
                "api_key": self.edit_mllm_api_key.text().strip() if remember_mllm_key else "",
            },
            "base_url": self.edit_base_url.text().strip(),
            "model": self.edit_model.text().strip(),
            "api_protocol": self.combo_api_protocol.currentData() or "auto",
            "remember_api_key": remember_key,
            "api_key": self.edit_api_key.text().strip() if remember_key else "",
        }

        try:
            settings_dir = os.path.dirname(self.api_settings_file)
            if settings_dir:
                os.makedirs(settings_dir, exist_ok=True)
            with open(self.api_settings_file, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            QMessageBox.information(self, self.tr("Settings Saved"), self.tr("API settings saved."))
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to save API settings: {}").format(exc))

    def update_mllm_api_controls_enabled(self):
        use_same = self.check_mllm_same_as_text.isChecked()
        for widget in [
            self.edit_mllm_api_key,
            self.edit_mllm_base_url,
            self.edit_mllm_model,
            self.combo_mllm_api_protocol,
            self.chk_remember_mllm_api_key,
        ]:
            widget.setEnabled(not use_same)
        self.combo_mllm_image_detail.setEnabled(True)

    def _current_multimodal_api_settings(self):
        if self.check_mllm_same_as_text.isChecked():
            return {
                "api_key": self.edit_api_key.text().strip(),
                "base_url": self.edit_base_url.text().strip(),
                "model": self.edit_model.text().strip(),
                "api_protocol": self.combo_api_protocol.currentData() or "auto",
                "image_detail": self.combo_mllm_image_detail.currentData() or "auto",
            }
        return {
            "api_key": self.edit_mllm_api_key.text().strip(),
            "base_url": self.edit_mllm_base_url.text().strip(),
            "model": self.edit_mllm_model.text().strip(),
            "api_protocol": self.combo_mllm_api_protocol.currentData() or "auto",
            "image_detail": self.combo_mllm_image_detail.currentData() or "auto",
        }

    def _load_json_dict_file(self, path):
        if not os.path.exists(path):
            return None, self._translated_text("Required file not found: {}").format(path)

        try:
            with open(path, 'r', encoding='utf-8') as handle:
                payload = json.load(handle)
        except Exception as exc:
            return None, self._translated_text("Failed to read JSON file {}: {}").format(path, exc)

        if not isinstance(payload, dict):
            return None, self._translated_text("JSON file does not contain an object: {}").format(path)

        return payload, ""

    def _apply_runtime_snapshot_to_form(self, snapshot):
        restored_mode = self._normalize_mode(snapshot.get("processing_mode"), "v2")
        snapshot_config = snapshot.get("screener_config")
        restored_config = deepcopy(snapshot_config) if isinstance(snapshot_config, dict) else dict(self.screener_config)

        for key in [
            "processing_mode",
            "lines_per_pdf",
            "csv_batch_size",
            "csv_batch_fallback_size",
            "include_confidence_threshold",
            "batch_char_budget",
            "max_text_chars_per_file",
            "llm_batch_max_tokens",
            "llm_request_timeout_seconds",
            "pdf_extract_timeout_seconds",
            "split_failed_batches",
            "resume_interrupted_runs",
            "isolate_v2_runs",
            "api_protocol",
        ]:
            if key in snapshot:
                restored_config[key] = snapshot.get(key)

        restored_config["processing_mode"] = restored_mode

        mode_index = self.combo_mode.findData(restored_mode)
        if mode_index >= 0:
            was_blocked = self.combo_mode.blockSignals(True)
            self.combo_mode.setCurrentIndex(mode_index)
            self.combo_mode.blockSignals(was_blocked)

        self.current_profile_name = self._translated_text("Default V2 Profile")
        self.refresh_profile_list()

        self.screener_config = restored_config
        self.sync_runtime_controls_from_config()

        source_folder = str(snapshot.get("source_folder", "") or "").strip()
        output_root = str(snapshot.get("output_root", "") or "").strip()
        if source_folder:
            self.edit_src_folder.setText(source_folder)
        if output_root:
            self.edit_out_folder.setText(output_root)

        self.edit_base_url.setText(str(snapshot.get("base_url", "") or ""))
        self.edit_model.setText(str(snapshot.get("model", "") or ""))

        api_protocol = str(snapshot.get("api_protocol", "auto") or "auto").strip().lower()
        protocol_index = self.combo_api_protocol.findData(api_protocol)
        if protocol_index < 0:
            protocol_index = self.combo_api_protocol.findData("auto")
        if protocol_index >= 0:
            self.combo_api_protocol.setCurrentIndex(protocol_index)

    def restore_interrupted_run_parameters(self):
        output_dir = self.edit_out_folder.text().strip()
        if not output_dir:
            reason = self._translated_text("Please select an output directory first.")
            self.log(self._translated_text("Failed to restore interrupted-run parameters: {}").format(reason))
            QMessageBox.warning(self, self._translated_text("Error"), reason)
            return

        active_run_path = os.path.join(output_dir, "v2_active_run.json")
        if not os.path.exists(active_run_path):
            reason = self._translated_text("Current output directory does not contain interrupted-run metadata.")
            self.log(self._translated_text("Failed to restore interrupted-run parameters: {}").format(reason))
            QMessageBox.warning(self, self._translated_text("Error"), reason)
            return

        active_run, error = self._load_json_dict_file(active_run_path)
        if not active_run:
            self.log(self._translated_text("Failed to restore interrupted-run parameters: {}").format(error))
            QMessageBox.warning(self, self._translated_text("Error"), str(error))
            return

        run_index_path = str(active_run.get("run_index_path", "") or "").strip()
        run_dir = str(active_run.get("run_dir", "") or "").strip()
        fallback_run_index_path = os.path.join(run_dir, "resume_state", "run_index.json") if run_dir else ""
        if not run_index_path and fallback_run_index_path:
            run_index_path = fallback_run_index_path

        if not run_index_path:
            reason = self._translated_text("Interrupted run metadata is missing run_index_path.")
            self.log(self._translated_text("Failed to restore interrupted-run parameters: {}").format(reason))
            QMessageBox.warning(self, self._translated_text("Error"), reason)
            return

        run_index, error = self._load_json_dict_file(run_index_path)
        if (not run_index) and fallback_run_index_path and os.path.normpath(fallback_run_index_path) != os.path.normpath(run_index_path):
            run_index_path = fallback_run_index_path
            run_index, error = self._load_json_dict_file(run_index_path)
        if not run_index:
            self.log(self._translated_text("Failed to restore interrupted-run parameters: {}").format(error))
            QMessageBox.warning(self, self._translated_text("Error"), str(error))
            return

        status = str(run_index.get("status", active_run.get("status", "unknown")) or "unknown").strip()
        if status.lower() in {"completed", "completed_with_warnings"}:
            reason = self._translated_text("Current output directory does not contain an interrupted V2 run (status: {}).").format(status)
            self.log(self._translated_text("Failed to restore interrupted-run parameters: {}").format(reason))
            QMessageBox.warning(self, self._translated_text("Error"), reason)
            return

        snapshot = run_index.get("runtime_config_snapshot")
        if not isinstance(snapshot, dict):
            runtime_signature = run_index.get("runtime_signature")
            if isinstance(runtime_signature, dict):
                snapshot = dict(runtime_signature)
                snapshot["processing_mode"] = self._normalize_mode(run_index.get("mode", "v2"), "v2")
                snapshot["source_folder"] = str(run_index.get("source_folder", "") or "")
                snapshot["output_root"] = str(run_index.get("output_root", output_dir) or output_dir)
            else:
                reason = self._translated_text("Interrupted run metadata is missing a runtime config snapshot.")
                self.log(self._translated_text("Failed to restore interrupted-run parameters: {}").format(reason))
                QMessageBox.warning(self, self._translated_text("Error"), reason)
                return

        self._apply_runtime_snapshot_to_form(snapshot)

        run_id = str(run_index.get("run_id", active_run.get("run_id", "unknown")) or "unknown")
        self.log(
            self._translated_text("Restored interrupted-run parameters from {} (run {}, status {}).").format(
                run_index_path,
                run_id,
                status,
            )
        )
        QMessageBox.information(
            self,
            self._translated_text("Settings Restored"),
            self._translated_text("Interrupted-run parameters restored from run {}. API key was left unchanged.").format(run_id),
        )

    def refresh_profile_list(self):
        """Update the combo box with available JSON files in configs_dir"""
        self.combo_profiles.blockSignals(True)
        self.combo_profiles.clear()

        selected_mode = self._normalize_mode(self.combo_mode.currentData() if hasattr(self, "combo_mode") else "v2")
        default_data = "DEFAULT_V2"
        default_label = self.tr("Default V2 Profile")
        self.combo_profiles.addItem(default_label, default_data)
        
        if os.path.exists(self.configs_dir):
            for f in sorted(os.listdir(self.configs_dir)):
                if f.endswith(".json"):
                    if f == "api_runtime_settings.json":
                        continue
                    path = os.path.join(self.configs_dir, f)
                    profile_mode = self._profile_mode_from_file(path)
                    if profile_mode != selected_mode:
                        continue
                    name = f[:-5]
                    self.combo_profiles.addItem(name, f)
        
        # Try to re-select current
        index = self.combo_profiles.findText(self.current_profile_name)
        if index >= 0:
            self.combo_profiles.setCurrentIndex(index)
        else:
            self.combo_profiles.setCurrentIndex(0)
            self.current_profile_name = self.combo_profiles.currentText()
            self.screener_config = self._default_config_for_mode(selected_mode)
            
        self.combo_profiles.blockSignals(False)

    def on_profile_changed(self, index):
        if index < 0: return
        name = self.combo_profiles.currentText()
        file_data = self.combo_profiles.currentData()
        
        selected_mode = self._normalize_mode(self.combo_mode.currentData())

        if file_data in ["DEFAULT", "DEFAULT_V2"]:
            self.screener_config = self._default_config_for_mode(selected_mode)
            self.current_profile_name = self.combo_profiles.currentText()
        else:
            path = os.path.join(self.configs_dir, file_data)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                profile_mode = self._normalize_mode(loaded_config.get("processing_mode"), "v2")
                if profile_mode != selected_mode:
                    QMessageBox.warning(
                        self,
                        self.tr("Error"),
                        self.tr("Profile mode mismatch. Please select a profile matching current screening mode."),
                    )
                    self.combo_profiles.setCurrentIndex(0)
                    self.screener_config = self._default_config_for_mode(selected_mode)
                    self.current_profile_name = self.combo_profiles.currentText()
                    self.sync_runtime_controls_from_config()
                    return
                self.screener_config = loaded_config
                self.current_profile_name = name
            except Exception as e:
                QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to load profile: {0}").format(e))

        self.sync_runtime_controls_from_config()

    def on_mode_changed(self, index):
        if index < 0:
            return
        selected_mode = self._normalize_mode(self.combo_mode.currentData())
        self.screener_config["processing_mode"] = selected_mode
        self.refresh_profile_list()

    def sync_runtime_controls_from_config(self):
        mode = str(self.screener_config.get("processing_mode", "v2")).strip().lower()
        mode = "v2"
        mode_index = self.combo_mode.findData(mode)
        if mode_index >= 0:
            was_blocked = self.combo_mode.blockSignals(True)
            self.combo_mode.setCurrentIndex(mode_index)
            self.combo_mode.blockSignals(was_blocked)

        try:
            lines_per_pdf = max(1, int(self.screener_config.get("lines_per_pdf", 30)))
        except (TypeError, ValueError):
            lines_per_pdf = 30
        try:
            batch_size = max(1, int(self.screener_config.get("csv_batch_size", 80)))
        except (TypeError, ValueError):
            batch_size = 80
        try:
            fallback_batch = max(1, int(self.screener_config.get("csv_batch_fallback_size", 40)))
        except (TypeError, ValueError):
            fallback_batch = 40
        if fallback_batch > batch_size:
            fallback_batch = batch_size
        try:
            include_threshold = float(self.screener_config.get("include_confidence_threshold", 0.75))
        except (TypeError, ValueError):
            include_threshold = 0.75
        try:
            batch_char_budget = max(5000, int(self.screener_config.get("batch_char_budget", 100000)))
        except (TypeError, ValueError):
            batch_char_budget = 100000
        try:
            max_text_chars = max(200, int(self.screener_config.get("max_text_chars_per_file", 1600)))
        except (TypeError, ValueError):
            max_text_chars = 1600
        try:
            llm_batch_max_tokens = max(500, int(self.screener_config.get("llm_batch_max_tokens", 12000)))
        except (TypeError, ValueError):
            llm_batch_max_tokens = 12000
        try:
            llm_timeout = max(30, int(self.screener_config.get("llm_request_timeout_seconds", 240)))
        except (TypeError, ValueError):
            llm_timeout = 240
        split_failed_batches = bool(self.screener_config.get("split_failed_batches", True))
        resume_runs = bool(self.screener_config.get("resume_interrupted_runs", True))
        isolate_runs = bool(self.screener_config.get("isolate_v2_runs", True))

        self.edit_lines_per_pdf.setText(str(lines_per_pdf))
        self.edit_batch_size.setText(str(batch_size))
        self.edit_fallback_batch.setText(str(fallback_batch))
        self.edit_include_threshold.setText(f"{include_threshold:.2f}")
        self.edit_batch_char_budget.setText(str(batch_char_budget))
        self.edit_max_text_chars.setText(str(max_text_chars))
        self.edit_llm_batch_tokens.setText(str(llm_batch_max_tokens))
        self.edit_llm_timeout.setText(str(llm_timeout))
        self.check_split_failed_batches.setChecked(split_failed_batches)
        self.check_resume_runs.setChecked(resume_runs)
        self.check_isolate_runs.setChecked(isolate_runs)

    def save_profile(self, name, config):
        filename = f"{name}.json"
        path = os.path.join(self.configs_dir, filename)
        selected_mode = self._normalize_mode(self.combo_mode.currentData() if hasattr(self, "combo_mode") else "v2")
        config_to_save = deepcopy(config)
        config_to_save["processing_mode"] = selected_mode
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=4)
            self.current_profile_name = name
            self.screener_config = config_to_save
            self.refresh_profile_list()
        except Exception as e:
            QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to save profile: {0}").format(e))

    def delete_current_profile(self):
        if self.combo_profiles.currentData() in ["DEFAULT", "DEFAULT_V2"]:
            return
            
        name = self.combo_profiles.currentText()
        reply = themed_yes_no_question(
            self,
            self.tr("Confirm Delete"),
            self.tr("Are you sure you want to delete profile '{}'?").format(name),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        
        if reply == QMessageBox.Yes:
            path = os.path.join(self.configs_dir, f"{name}.json")
            try:
                if os.path.exists(path):
                    os.remove(path)
                self.current_profile_name = self.combo_profiles.itemText(0) if self.combo_profiles.count() > 0 else ""
                self.refresh_profile_list()
            except Exception as e:
                QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to delete profile: {0}").format(e))

    def refresh_figure_profile_list(self):
        self.combo_figure_profiles.blockSignals(True)
        self.combo_figure_profiles.clear()
        default_label = self.tr("Built-in Ant Triptych Figure Profile")
        self.combo_figure_profiles.addItem(default_label, "DEFAULT_FIGURE")

        if os.path.exists(self.figure_configs_dir):
            for filename in sorted(os.listdir(self.figure_configs_dir)):
                if not filename.endswith(".json"):
                    continue
                path = os.path.join(self.figure_configs_dir, filename)
                try:
                    profile = load_figure_profile(path)
                    name = profile_display_name(profile) or filename[:-5]
                except Exception:
                    name = filename[:-5]
                self.combo_figure_profiles.addItem(name, filename)

        index = self.combo_figure_profiles.findText(self.current_figure_profile_name)
        if index >= 0:
            self.combo_figure_profiles.setCurrentIndex(index)
        else:
            self.combo_figure_profiles.setCurrentIndex(0)
            self.figure_profile = normalize_figure_profile(None)
            self.current_figure_profile_name = self.combo_figure_profiles.currentText()
            self.current_figure_profile_path = ""
        self.combo_figure_profiles.blockSignals(False)

    def on_figure_profile_changed(self, index):
        if index < 0:
            return
        name = self.combo_figure_profiles.currentText()
        data = self.combo_figure_profiles.currentData()
        if data == "DEFAULT_FIGURE":
            self.figure_profile = normalize_figure_profile(None)
            self.current_figure_profile_name = name
            self.current_figure_profile_path = ""
            return
        path = os.path.join(self.figure_configs_dir, str(data))
        try:
            self.figure_profile = load_figure_profile(path)
            self.current_figure_profile_name = profile_display_name(self.figure_profile) or name
            self.current_figure_profile_path = path
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to load figure profile: {0}").format(exc))
            self.combo_figure_profiles.setCurrentIndex(0)

    def save_figure_profile(self, name, profile):
        filename = f"{name}.json"
        path = os.path.join(self.figure_configs_dir, filename)
        profile_to_save = normalize_figure_profile(profile)
        profile_to_save["profile_name"] = name
        try:
            with open(path, 'w', encoding='utf-8') as handle:
                json.dump(profile_to_save, handle, ensure_ascii=False, indent=2)
            self.figure_profile = profile_to_save
            self.current_figure_profile_name = name
            self.current_figure_profile_path = path
            self.refresh_figure_profile_list()
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to save figure profile: {0}").format(exc))

    def delete_current_figure_profile(self):
        if self.combo_figure_profiles.currentData() == "DEFAULT_FIGURE":
            return
        name = self.combo_figure_profiles.currentText()
        reply = themed_yes_no_question(
            self,
            self.tr("Confirm Delete"),
            self.tr("Are you sure you want to delete profile '{}'?").format(name),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply == QMessageBox.Yes:
            path = os.path.join(self.figure_configs_dir, f"{name}.json")
            data = self.combo_figure_profiles.currentData()
            if data:
                path = os.path.join(self.figure_configs_dir, str(data))
            try:
                if os.path.exists(path):
                    os.remove(path)
                self.figure_profile = normalize_figure_profile(None)
                self.current_figure_profile_name = ""
                self.current_figure_profile_path = ""
                self.refresh_figure_profile_list()
            except Exception as exc:
                QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to delete profile: {0}").format(exc))

    def tr(self, text):
        if self.current_lang == "zh":
            return TRANSLATIONS["zh"].get(text, text)
        return text

    def _translated_text(self, text) -> str:
        translated = self.tr(text)
        if isinstance(translated, str) and translated:
            return translated
        return str(text)

    def _confirm_extract_preflight(self, use_mllm, mllm_config):
        confirmation = None
        if hasattr(EnhancedPDFExtractionSystem, "get_prestart_mock_review_confirmation"):
            try:
                confirmation = EnhancedPDFExtractionSystem.get_prestart_mock_review_confirmation(
                    enable_multimodal_validation=use_mllm,
                    multimodal_config=mllm_config,
                )
            except Exception:
                confirmation = None

        if not confirmation:
            return True

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(self._translated_text("Mock/Default Review Confirmation"))
        dialog.setText(str(confirmation.get("message", "") or "").strip())
        dialog.setInformativeText(self._translated_text("Continue with extraction anyway?"))
        continue_button = dialog.addButton(self._translated_text("Continue"), QMessageBox.ButtonRole.AcceptRole)
        cancel_button = dialog.addButton(self._translated_text("Cancel"), QMessageBox.ButtonRole.RejectRole)
        dialog.setStyleSheet(get_theme_stylesheet(getattr(self, "current_theme", "dark")))
        apply_theme_button_style(
            continue_button,
            BUTTON_ROLE_RUN,
            DIALOG_ACTION_BUTTON_EXTRAS,
            getattr(self, "current_theme", "dark"),
        )
        apply_theme_button_style(
            cancel_button,
            BUTTON_ROLE_STOP,
            DIALOG_ACTION_BUTTON_EXTRAS,
            getattr(self, "current_theme", "dark"),
        )
        dialog.setDefaultButton(continue_button)
        dialog.setEscapeButton(cancel_button)
        dialog.exec()
        return dialog.clickedButton() == continue_button

    def init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        self.main_scroll = QScrollArea()
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setObjectName("pdfProcessingScrollArea")
        scroll_content = QWidget()
        scroll_content.setObjectName("pdfProcessingScrollContent")
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # --- Config Section ---
        self.config_group = QGroupBox()
        apply_surface_role(self.config_group, SURFACE_ROLE_PANEL, "pdfSettingsPanel")
        form_layout = QVBoxLayout(self.config_group)
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(10)
        
        # API Keys
        self.api_panel = QWidget()
        apply_surface_role(self.api_panel, SURFACE_ROLE_SUBTLE, "pdfApiPanel")
        api_panel_layout = QVBoxLayout(self.api_panel)
        api_panel_layout.setContentsMargins(10, 10, 10, 10)
        api_panel_layout.setSpacing(8)

        self.text_llm_group = QGroupBox()
        apply_surface_role(self.text_llm_group, SURFACE_ROLE_SUBTLE, "pdfTextLlmApiGroup")
        api_grid = QGridLayout(self.text_llm_group)
        api_grid.setContentsMargins(10, 10, 10, 10)
        api_grid.setHorizontalSpacing(8)
        api_grid.setVerticalSpacing(6)
        self.edit_api_key = QLineEdit()
        self.edit_api_key.setEchoMode(QLineEdit.Password)
        self.edit_api_key.setPlaceholderText(self.tr("sk-..."))
        
        self.edit_base_url = QLineEdit()
        self.edit_base_url.setPlaceholderText(self.tr("https://api.siliconflow.cn/v1"))
        
        self.edit_model = QLineEdit("gpt-5.4")
        self.combo_api_protocol = QComboBox()
        self.combo_api_protocol.addItem(self.tr("Auto (Recommended)"), "auto")
        self.combo_api_protocol.addItem(self.tr("Chat Completions"), "chat_completions")
        self.combo_api_protocol.addItem(self.tr("Responses API"), "responses")
        for control in (self.edit_api_key, self.edit_base_url, self.edit_model, self.combo_api_protocol):
            control.setMinimumHeight(30)
        
        self.lbl_api_key = QLabel()
        self.lbl_base_url = QLabel()
        self.lbl_model = QLabel()
        self.lbl_api_protocol = QLabel()

        api_grid.addWidget(self.lbl_api_key, 0, 0)
        api_grid.addWidget(self.edit_api_key, 0, 1)
        api_grid.addWidget(self.lbl_base_url, 0, 2)
        api_grid.addWidget(self.edit_base_url, 0, 3)
        api_grid.addWidget(self.lbl_model, 1, 0)
        api_grid.addWidget(self.edit_model, 1, 1)
        api_grid.addWidget(self.lbl_api_protocol, 1, 2)
        api_grid.addWidget(self.combo_api_protocol, 1, 3)
        api_grid.setColumnStretch(1, 1)
        api_grid.setColumnStretch(3, 1)
        api_panel_layout.addWidget(self.text_llm_group)

        self.mllm_group = QGroupBox()
        apply_surface_role(self.mllm_group, SURFACE_ROLE_SUBTLE, "pdfMultimodalLlmApiGroup")
        mllm_grid = QGridLayout(self.mllm_group)
        mllm_grid.setContentsMargins(10, 10, 10, 10)
        mllm_grid.setHorizontalSpacing(8)
        mllm_grid.setVerticalSpacing(6)
        self.check_mllm_same_as_text = QCheckBox()
        self.check_mllm_same_as_text.setChecked(True)
        self.check_mllm_same_as_text.toggled.connect(self.update_mllm_api_controls_enabled)

        self.edit_mllm_api_key = QLineEdit()
        self.edit_mllm_api_key.setEchoMode(QLineEdit.Password)
        self.edit_mllm_api_key.setPlaceholderText(self.tr("sk-..."))
        self.edit_mllm_base_url = QLineEdit()
        self.edit_mllm_base_url.setPlaceholderText(self.tr("https://api.siliconflow.cn/v1"))
        self.edit_mllm_model = QLineEdit("Qwen/Qwen3-VL-32B-Instruct")
        self.combo_mllm_api_protocol = QComboBox()
        self.combo_mllm_api_protocol.addItem(self.tr("Auto (Recommended)"), "auto")
        self.combo_mllm_api_protocol.addItem(self.tr("Chat Completions"), "chat_completions")
        self.combo_mllm_api_protocol.addItem(self.tr("Responses API"), "responses")
        self.combo_mllm_image_detail = QComboBox()
        self.combo_mllm_image_detail.addItem("Auto", "auto")
        self.combo_mllm_image_detail.addItem("Low", "low")
        self.combo_mllm_image_detail.addItem("High", "high")
        for control in (
            self.edit_mllm_api_key,
            self.edit_mllm_base_url,
            self.edit_mllm_model,
            self.combo_mllm_api_protocol,
            self.combo_mllm_image_detail,
        ):
            control.setMinimumHeight(30)

        self.lbl_mllm_api_key = QLabel()
        self.lbl_mllm_base_url = QLabel()
        self.lbl_mllm_model = QLabel()
        self.lbl_mllm_api_protocol = QLabel()
        self.lbl_mllm_image_detail = QLabel()

        mllm_grid.addWidget(self.check_mllm_same_as_text, 0, 0, 1, 4)
        mllm_grid.addWidget(self.lbl_mllm_api_key, 1, 0)
        mllm_grid.addWidget(self.edit_mllm_api_key, 1, 1)
        mllm_grid.addWidget(self.lbl_mllm_base_url, 1, 2)
        mllm_grid.addWidget(self.edit_mllm_base_url, 1, 3)
        mllm_grid.addWidget(self.lbl_mllm_model, 2, 0)
        mllm_grid.addWidget(self.edit_mllm_model, 2, 1)
        mllm_grid.addWidget(self.lbl_mllm_api_protocol, 2, 2)
        mllm_grid.addWidget(self.combo_mllm_api_protocol, 2, 3)
        mllm_grid.addWidget(self.lbl_mllm_image_detail, 3, 0)
        mllm_grid.addWidget(self.combo_mllm_image_detail, 3, 1)
        mllm_grid.setColumnStretch(1, 1)
        mllm_grid.setColumnStretch(3, 1)
        api_panel_layout.addWidget(self.mllm_group)

        api_action_layout = QHBoxLayout()
        self.chk_remember_api_key = QCheckBox()
        self.chk_remember_api_key.setChecked(False)
        self.chk_remember_mllm_api_key = QCheckBox()
        self.chk_remember_mllm_api_key.setChecked(False)
        self.btn_save_api_settings = QPushButton()
        self.btn_save_api_settings.clicked.connect(self.save_api_settings)
        apply_semantic_button_style(self.btn_save_api_settings, BUTTON_ROLE_COMMIT, "padding: 5px;")
        api_action_layout.addWidget(self.chk_remember_api_key)
        api_action_layout.addWidget(self.chk_remember_mllm_api_key)
        api_action_layout.addStretch()
        api_action_layout.addWidget(self.btn_save_api_settings)
        api_panel_layout.addLayout(api_action_layout)
        form_layout.addWidget(self.api_panel, 0)

        # Profile Selector & Advanced Logic Button
        self.profile_panel = QWidget()
        apply_surface_role(self.profile_panel, SURFACE_ROLE_SUBTLE, "pdfProfilePanel")
        profile_panel_layout = QVBoxLayout(self.profile_panel)
        profile_panel_layout.setContentsMargins(10, 10, 10, 10)
        profile_panel_layout.setSpacing(6)

        adv_layout = QHBoxLayout()
        
        self.lbl_select_profile = QLabel()
        adv_layout.addWidget(self.lbl_select_profile)
        
        self.combo_profiles = QComboBox()
        self.combo_profiles.setMinimumWidth(200)
        self.combo_profiles.currentIndexChanged.connect(self.on_profile_changed)
        adv_layout.addWidget(self.combo_profiles)
        
        self.btn_delete_profile = QPushButton()
        self.btn_delete_profile.clicked.connect(self.delete_current_profile)
        apply_semantic_button_style(self.btn_delete_profile, BUTTON_ROLE_DESTRUCTIVE)
        adv_layout.addWidget(self.btn_delete_profile)
        
        adv_layout.addStretch()
        
        self.btn_adv_config = QPushButton()
        self.btn_adv_config.clicked.connect(self.open_adv_config)
        apply_semantic_button_style(self.btn_adv_config, BUTTON_ROLE_NEUTRAL, "padding: 5px;")
        adv_layout.addWidget(self.btn_adv_config)
        
        profile_panel_layout.addLayout(adv_layout)

        figure_profile_layout = QHBoxLayout()
        self.lbl_select_figure_profile = QLabel()
        figure_profile_layout.addWidget(self.lbl_select_figure_profile)

        self.combo_figure_profiles = QComboBox()
        self.combo_figure_profiles.setMinimumWidth(240)
        self.combo_figure_profiles.currentIndexChanged.connect(self.on_figure_profile_changed)
        figure_profile_layout.addWidget(self.combo_figure_profiles)

        self.btn_delete_figure_profile = QPushButton()
        self.btn_delete_figure_profile.clicked.connect(self.delete_current_figure_profile)
        apply_semantic_button_style(self.btn_delete_figure_profile, BUTTON_ROLE_DESTRUCTIVE)
        figure_profile_layout.addWidget(self.btn_delete_figure_profile)

        figure_profile_layout.addStretch()

        self.btn_adv_figure_config = QPushButton()
        self.btn_adv_figure_config.clicked.connect(self.open_adv_figure_config)
        apply_semantic_button_style(self.btn_adv_figure_config, BUTTON_ROLE_NEUTRAL, "padding: 5px;")
        figure_profile_layout.addWidget(self.btn_adv_figure_config)

        profile_panel_layout.addLayout(figure_profile_layout)
        form_layout.addWidget(self.profile_panel, 0)
        
        layout.addWidget(self.config_group, 0)
        
        # --- Task Tabs ---
        self.tabs = QTabWidget()
        
        # Tab 1: Classifier
        tab_classify = QWidget()
        l_class = QVBoxLayout(tab_classify)
        l_class.setContentsMargins(0, 0, 0, 0)
        l_class.setSpacing(12)

        self.classify_input_panel = QWidget()
        apply_surface_role(self.classify_input_panel, SURFACE_ROLE_PANEL, "pdfClassifyInputPanel")
        classify_input_layout = QVBoxLayout(self.classify_input_panel)
        classify_input_layout.setContentsMargins(12, 12, 12, 12)
        classify_input_layout.setSpacing(10)
        
        h1 = QHBoxLayout()
        self.edit_src_folder = QLineEdit()
        self.btn_src = QPushButton()
        self.btn_src.clicked.connect(lambda: self.browse_dir(self.edit_src_folder))
        apply_semantic_button_style(self.btn_src, BUTTON_ROLE_NEUTRAL)
        self.lbl_src_pdf = QLabel()
        h1.addWidget(self.lbl_src_pdf)
        h1.addWidget(self.edit_src_folder)
        h1.addWidget(self.btn_src)
        classify_input_layout.addLayout(h1)
        
        h2 = QHBoxLayout()
        self.edit_out_folder = QLineEdit()
        self.btn_out = QPushButton()
        self.btn_out.clicked.connect(lambda: self.browse_dir(self.edit_out_folder))
        self.btn_restore_interrupted_run = QPushButton()
        self.btn_restore_interrupted_run.clicked.connect(self.restore_interrupted_run_parameters)
        apply_semantic_button_style(self.btn_out, BUTTON_ROLE_NEUTRAL)
        apply_semantic_button_style(self.btn_restore_interrupted_run, BUTTON_ROLE_NEUTRAL)
        self.lbl_out_dir = QLabel()
        h2.addWidget(self.lbl_out_dir)
        h2.addWidget(self.edit_out_folder)
        h2.addWidget(self.btn_out)
        h2.addWidget(self.btn_restore_interrupted_run)
        classify_input_layout.addLayout(h2)
        l_class.addWidget(self.classify_input_panel)

        self.classify_runtime_panel = QWidget()
        apply_surface_role(self.classify_runtime_panel, SURFACE_ROLE_SUBTLE, "pdfClassifyRuntimePanel")
        classify_runtime_layout = QVBoxLayout(self.classify_runtime_panel)
        classify_runtime_layout.setContentsMargins(12, 12, 12, 12)
        classify_runtime_layout.setSpacing(10)

        mode_layout = QHBoxLayout()
        self.lbl_screening_mode = QLabel()
        self.combo_mode = QComboBox()
        self.combo_mode.addItem(self.tr("V2 (CSV Full LLM)"), "v2")
        self.combo_mode.setMinimumWidth(180)
        self.combo_mode.currentIndexChanged.connect(self.on_mode_changed)

        self.lbl_lines_per_pdf = QLabel()
        self.edit_lines_per_pdf = QLineEdit("30")
        self.edit_lines_per_pdf.setValidator(QIntValidator(1, 500, self))
        self.edit_lines_per_pdf.setMaximumWidth(70)

        self.lbl_batch_size = QLabel()
        self.edit_batch_size = QLineEdit("80")
        self.edit_batch_size.setValidator(QIntValidator(1, 500, self))
        self.edit_batch_size.setMaximumWidth(70)

        self.lbl_fallback_batch = QLabel()
        self.edit_fallback_batch = QLineEdit("40")
        self.edit_fallback_batch.setValidator(QIntValidator(1, 500, self))
        self.edit_fallback_batch.setMaximumWidth(70)

        self.lbl_include_threshold = QLabel()
        self.edit_include_threshold = QLineEdit("0.75")
        threshold_validator = QDoubleValidator(0.0, 1.0, 3, self)
        threshold_validator.setNotation(QDoubleValidator.StandardNotation)
        self.edit_include_threshold.setValidator(threshold_validator)
        self.edit_include_threshold.setMaximumWidth(80)

        self.lbl_batch_char_budget = QLabel()
        self.edit_batch_char_budget = QLineEdit("100000")
        self.edit_batch_char_budget.setValidator(QIntValidator(5000, 5000000, self))
        self.edit_batch_char_budget.setMaximumWidth(90)

        self.lbl_max_text_chars = QLabel()
        self.edit_max_text_chars = QLineEdit("1600")
        self.edit_max_text_chars.setValidator(QIntValidator(200, 50000, self))
        self.edit_max_text_chars.setMaximumWidth(80)

        self.lbl_llm_batch_tokens = QLabel()
        self.edit_llm_batch_tokens = QLineEdit("12000")
        self.edit_llm_batch_tokens.setValidator(QIntValidator(500, 50000, self))
        self.edit_llm_batch_tokens.setMaximumWidth(80)

        self.lbl_llm_timeout = QLabel()
        self.edit_llm_timeout = QLineEdit("240")
        self.edit_llm_timeout.setValidator(QIntValidator(30, 7200, self))
        self.edit_llm_timeout.setMaximumWidth(80)

        self.check_split_failed_batches = QCheckBox()
        self.check_split_failed_batches.setChecked(True)
        self.check_resume_runs = QCheckBox()
        self.check_resume_runs.setChecked(True)
        self.check_isolate_runs = QCheckBox()
        self.check_isolate_runs.setChecked(True)

        mode_layout.addWidget(self.lbl_screening_mode)
        mode_layout.addWidget(self.combo_mode)
        mode_layout.addSpacing(10)
        mode_layout.addWidget(self.lbl_lines_per_pdf)
        mode_layout.addWidget(self.edit_lines_per_pdf)
        mode_layout.addSpacing(10)
        mode_layout.addWidget(self.lbl_batch_size)
        mode_layout.addWidget(self.edit_batch_size)
        mode_layout.addSpacing(10)
        mode_layout.addWidget(self.lbl_fallback_batch)
        mode_layout.addWidget(self.edit_fallback_batch)
        mode_layout.addSpacing(10)
        mode_layout.addWidget(self.lbl_include_threshold)
        mode_layout.addWidget(self.edit_include_threshold)
        mode_layout.addStretch()
        classify_runtime_layout.addLayout(mode_layout)

        safety_layout = QHBoxLayout()
        safety_layout.addWidget(self.lbl_batch_char_budget)
        safety_layout.addWidget(self.edit_batch_char_budget)
        safety_layout.addSpacing(10)
        safety_layout.addWidget(self.lbl_max_text_chars)
        safety_layout.addWidget(self.edit_max_text_chars)
        safety_layout.addSpacing(10)
        safety_layout.addWidget(self.lbl_llm_batch_tokens)
        safety_layout.addWidget(self.edit_llm_batch_tokens)
        safety_layout.addSpacing(10)
        safety_layout.addWidget(self.lbl_llm_timeout)
        safety_layout.addWidget(self.edit_llm_timeout)
        safety_layout.addStretch()
        classify_runtime_layout.addLayout(safety_layout)

        safety_toggle_layout = QHBoxLayout()
        safety_toggle_layout.addWidget(self.check_split_failed_batches)
        safety_toggle_layout.addSpacing(12)
        safety_toggle_layout.addWidget(self.check_resume_runs)
        safety_toggle_layout.addSpacing(12)
        safety_toggle_layout.addWidget(self.check_isolate_runs)
        safety_toggle_layout.addStretch()
        classify_runtime_layout.addLayout(safety_toggle_layout)
        l_class.addWidget(self.classify_runtime_panel)
        
        # Buttons Layout
        self.classify_action_panel = QWidget()
        apply_surface_role(self.classify_action_panel, SURFACE_ROLE_RAISED, "pdfClassifyActionPanel")
        classify_action_layout = QVBoxLayout(self.classify_action_panel)
        classify_action_layout.setContentsMargins(12, 12, 12, 12)

        btn_layout_cls = QHBoxLayout()
        self.btn_run_classify = QPushButton()
        self.btn_run_classify.clicked.connect(self.start_classify)
        apply_semantic_button_style(self.btn_run_classify, BUTTON_ROLE_RUN, "font-weight: bold; padding: 12px; font-size: 14px;")
        
        self.btn_stop_classify = QPushButton()
        self.btn_stop_classify.clicked.connect(self.stop_worker)
        apply_semantic_button_style(self.btn_stop_classify, BUTTON_ROLE_STOP, "font-weight: bold; padding: 12px; font-size: 14px;")
        self.btn_stop_classify.setEnabled(False)

        btn_layout_cls.addWidget(self.btn_run_classify)
        btn_layout_cls.addWidget(self.btn_stop_classify)
        classify_action_layout.addLayout(btn_layout_cls)
        l_class.addWidget(self.classify_action_panel)
        l_class.addStretch()
        
        self.tabs.addTab(tab_classify, "")
        
        # Tab 2: Extractor
        tab_extract = QWidget()
        l_ext = QVBoxLayout(tab_extract)
        l_ext.setContentsMargins(0, 0, 0, 0)
        l_ext.setSpacing(12)

        self.extract_input_panel = QWidget()
        apply_surface_role(self.extract_input_panel, SURFACE_ROLE_PANEL, "pdfExtractInputPanel")
        extract_input_layout = QVBoxLayout(self.extract_input_panel)
        extract_input_layout.setContentsMargins(12, 12, 12, 12)
        extract_input_layout.setSpacing(10)
        
        h3 = QHBoxLayout()
        self.edit_ext_src = QLineEdit()
        self.btn_ext_src = QPushButton()
        self.btn_ext_src.clicked.connect(lambda: self.browse_dir(self.edit_ext_src))
        apply_semantic_button_style(self.btn_ext_src, BUTTON_ROLE_NEUTRAL)
        self.lbl_ext_src = QLabel()
        h3.addWidget(self.lbl_ext_src)
        h3.addWidget(self.edit_ext_src)
        h3.addWidget(self.btn_ext_src)
        extract_input_layout.addLayout(h3)
        
        h4 = QHBoxLayout()
        self.edit_db_path = QLineEdit("ant_literature.db")
        self.btn_db = QPushButton()
        self.btn_db.clicked.connect(self.browse_save_db)
        apply_semantic_button_style(self.btn_db, BUTTON_ROLE_NEUTRAL)
        self.lbl_ext_db = QLabel()
        h4.addWidget(self.lbl_ext_db)
        h4.addWidget(self.edit_db_path)
        h4.addWidget(self.btn_db)
        extract_input_layout.addLayout(h4)
        
        self.check_mllm = QCheckBox()
        extract_input_layout.addWidget(self.check_mllm)
        l_ext.addWidget(self.extract_input_panel)
        
        # Buttons Layout
        self.extract_action_panel = QWidget()
        apply_surface_role(self.extract_action_panel, SURFACE_ROLE_RAISED, "pdfExtractActionPanel")
        extract_action_layout = QVBoxLayout(self.extract_action_panel)
        extract_action_layout.setContentsMargins(12, 12, 12, 12)

        btn_layout_ext = QHBoxLayout()
        self.btn_run_extract = QPushButton()
        self.btn_run_extract.clicked.connect(self.start_extract)
        apply_semantic_button_style(self.btn_run_extract, BUTTON_ROLE_RUN, "font-weight: bold; padding: 12px; font-size: 14px;")
        
        self.btn_stop_extract = QPushButton()
        self.btn_stop_extract.clicked.connect(self.stop_worker)
        apply_semantic_button_style(self.btn_stop_extract, BUTTON_ROLE_STOP, "font-weight: bold; padding: 12px; font-size: 14px;")
        self.btn_stop_extract.setEnabled(False)

        btn_layout_ext.addWidget(self.btn_run_extract)
        btn_layout_ext.addWidget(self.btn_stop_extract)
        extract_action_layout.addLayout(btn_layout_ext)
        l_ext.addWidget(self.extract_action_panel)
        
        # New Utilities Section
        util_group = QGroupBox()
        apply_surface_role(util_group, SURFACE_ROLE_SUBTLE, "pdfUtilityPanel")
        self.util_group = util_group # For translation
        u_layout = QHBoxLayout(util_group)
        u_layout.setContentsMargins(12, 12, 12, 12)
        u_layout.setSpacing(10)
        
        self.btn_browse_db = QPushButton()
        self.btn_browse_db.clicked.connect(self.browse_database)
        apply_semantic_button_style(self.btn_browse_db, BUTTON_ROLE_NEUTRAL)
        u_layout.addWidget(self.btn_browse_db)
        
        self.btn_export_jsonl = QPushButton()
        self.btn_export_jsonl.clicked.connect(self.export_jsonl)
        apply_semantic_button_style(self.btn_export_jsonl, BUTTON_ROLE_COMMIT)
        u_layout.addWidget(self.btn_export_jsonl)
        
        l_ext.addWidget(util_group)
        l_ext.addStretch()
        
        self.tabs.addTab(tab_extract, "")
        
        layout.addWidget(self.tabs, 1)
        
        # --- Progress Bar & Logs ---
        self.feedback_panel = QWidget()
        apply_surface_role(self.feedback_panel, SURFACE_ROLE_SUBTLE, "pdfFeedbackPanel")
        feedback_layout = QVBoxLayout(self.feedback_panel)
        feedback_layout.setContentsMargins(12, 12, 12, 12)
        feedback_layout.setSpacing(8)

        self.lbl_progress = QLabel()
        feedback_layout.addWidget(self.lbl_progress)
        self.progress_bar = QProgressBar()
        feedback_layout.addWidget(self.progress_bar)
        
        self.lbl_logs = QLabel()
        feedback_layout.addWidget(self.lbl_logs)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setObjectName("MutedLogConsole")
        self.log_area.setMinimumHeight(96)
        feedback_layout.addWidget(self.log_area, 1)
        layout.addWidget(self.feedback_panel, 1)
        self.main_scroll.setWidget(scroll_content)
        outer_layout.addWidget(self.main_scroll)

    def retranslate_ui(self):
        """Update all text labels based on current language"""
        self.config_group.setTitle(self.tr("Global Settings (LLM / API)"))
        self.text_llm_group.setTitle(self.tr("Text LLM API"))
        self.lbl_api_key.setText(self.tr("API Key:"))
        self.lbl_base_url.setText(self.tr("Base URL:"))
        self.lbl_model.setText(self.tr("Model:"))
        self.lbl_api_protocol.setText(self.tr("API Protocol:"))
        self.combo_api_protocol.setItemText(0, self.tr("Auto (Recommended)"))
        self.combo_api_protocol.setItemText(1, self.tr("Chat Completions"))
        self.combo_api_protocol.setItemText(2, self.tr("Responses API"))
        self.edit_api_key.setPlaceholderText(self.tr("sk-..."))
        self.edit_base_url.setPlaceholderText(self.tr("https://api.siliconflow.cn/v1"))
        self.edit_model.setPlaceholderText(self.tr("Model Name"))
        self.mllm_group.setTitle(self.tr("Multimodal LLM API"))
        self.check_mllm_same_as_text.setText(self.tr("Use same provider as Text LLM"))
        self.lbl_mllm_api_key.setText(self.tr("API Key:"))
        self.lbl_mllm_base_url.setText(self.tr("Base URL:"))
        self.lbl_mllm_model.setText(self.tr("Model:"))
        self.lbl_mllm_api_protocol.setText(self.tr("API Protocol:"))
        self.lbl_mllm_image_detail.setText(self.tr("Image Detail:"))
        self.combo_mllm_api_protocol.setItemText(0, self.tr("Auto (Recommended)"))
        self.combo_mllm_api_protocol.setItemText(1, self.tr("Chat Completions"))
        self.combo_mllm_api_protocol.setItemText(2, self.tr("Responses API"))
        self.combo_mllm_image_detail.setItemText(0, self.tr("Auto"))
        self.combo_mllm_image_detail.setItemText(1, self.tr("Low"))
        self.combo_mllm_image_detail.setItemText(2, self.tr("High"))
        self.edit_mllm_api_key.setPlaceholderText(self.tr("sk-..."))
        self.edit_mllm_base_url.setPlaceholderText(self.tr("https://api.siliconflow.cn/v1"))
        self.edit_mllm_model.setPlaceholderText(self.tr("Vision Model Name"))
        self.chk_remember_api_key.setText(self.tr("Remember API Key"))
        self.chk_remember_mllm_api_key.setText(self.tr("Remember Multimodal API Key"))
        self.btn_save_api_settings.setText(self.tr("Save API Settings"))
        self.lbl_screening_mode.setText(self.tr("Screening Mode:"))
        self.combo_mode.setItemText(0, self.tr("V2 (CSV Full LLM)"))
        self.lbl_lines_per_pdf.setText(self.tr("Lines/PDF:"))
        self.lbl_batch_size.setText(self.tr("Batch Size:"))
        self.lbl_fallback_batch.setText(self.tr("Fallback Batch:"))
        self.lbl_include_threshold.setText(self.tr("Include Threshold:"))
        self.lbl_batch_char_budget.setText(self.tr("Prompt Char Budget:"))
        self.lbl_max_text_chars.setText(self.tr("Text Chars/File:"))
        self.lbl_llm_batch_tokens.setText(self.tr("LLM Max Tokens:"))
        self.lbl_llm_timeout.setText(self.tr("LLM Timeout(s):"))
        self.check_split_failed_batches.setText(self.tr("Auto Split Failed Batches"))
        self.check_resume_runs.setText(self.tr("Resume Interrupted Runs"))
        self.check_isolate_runs.setText(self.tr("V2: separate folder per run"))
        self.check_isolate_runs.setToolTip(
            self.tr("Each V2 run saves into its own subfolder under Output Dir to avoid mixed results.")
        )
        
        self.lbl_select_profile.setText(self.tr("Select Logic Profile:"))
        self.btn_delete_profile.setText(self.tr("Delete Profile"))
        self.btn_adv_config.setText(self.tr("Advanced Logic Settings"))
        self.lbl_select_figure_profile.setText(self.tr("Figure Extraction / Review Profile:"))
        self.btn_delete_figure_profile.setText(self.tr("Delete Profile"))
        self.btn_adv_figure_config.setText(self.tr("Advanced Figure Settings"))
        
        self.tabs.setTabText(0, self.tr("1. PDF Screener (Classify)"))
        self.lbl_src_pdf.setText(self.tr("Input PDFs:"))
        self.edit_src_folder.setPlaceholderText(self.tr("Folder containing raw PDFs..."))
        self.btn_src.setText(self.tr("Browse"))
        self.lbl_out_dir.setText(self.tr("Output Dir:"))
        self.btn_restore_interrupted_run.setText(self._translated_text("Restore Interrupted Run Params"))
        self.edit_out_folder.setPlaceholderText(self.tr("Folder to sort PDFs into..."))
        self.btn_out.setText(self.tr("Browse"))
        self.btn_run_classify.setText(self.tr("Start Classification Batch"))
        self.btn_stop_classify.setText(self.tr("Stop Classification"))
        
        self.tabs.setTabText(1, self.tr("2. Data Extractor (Images & Text)"))
        self.lbl_ext_src.setText(self.tr("Input Folder:"))
        self.edit_ext_src.setPlaceholderText(self.tr("Folder with 'New Species' PDFs..."))
        self.btn_ext_src.setText(self.tr("Browse"))
        self.lbl_ext_db.setText(self.tr("Output DB:"))
        self.btn_db.setText(self.tr("Select DB File"))
        self.check_mllm.setText(self.tr("Enable Multimodal Validation (Uses API - Slower but more accurate)"))
        self.btn_run_extract.setText(self.tr("Start Extraction Pipeline"))
        self.btn_stop_extract.setText(self.tr("Stop Extraction"))
        
        self.util_group.setTitle(self.tr("3. Data Utilities"))
        self.btn_browse_db.setText(self.tr("Browse Database"))
        self.btn_export_jsonl.setText(self.tr("Export PDF Extract Dataset (JSONL)"))
        
        self.lbl_logs.setText(self.tr("Processing Logs:"))
        self.lbl_progress.setText(self.tr("Progress:"))

    def open_adv_config(self):
        is_def = self.combo_profiles.currentData() in ["DEFAULT", "DEFAULT_V2"]
        mode = self.combo_mode.currentData() if hasattr(self, "combo_mode") else "v2"
        dlg = ScreenerConfigDialog(self.screener_config, self.current_profile_name, is_def, self, self.current_lang, mode)
        if dlg.exec():
            new_config, new_name, action = dlg.get_result()
            
            if action == 'new':
                self.save_profile(new_name, new_config)
            elif action == 'overwrite':
                self.save_profile(self.current_profile_name, new_config)
            
            QMessageBox.information(self, self.tr("Settings Saved"), self.tr("Screener logic configuration updated."))

    def open_adv_figure_config(self):
        is_default = self.combo_figure_profiles.currentData() == "DEFAULT_FIGURE"
        dlg = FigureProfileDialog(self.figure_profile, self.current_figure_profile_name, is_default, self, self.current_lang)
        if dlg.exec():
            new_profile, new_name, action = dlg.get_result()
            if action == "new":
                self.save_figure_profile(new_name, new_profile)
            elif action == "overwrite":
                self.save_figure_profile(self.current_figure_profile_name, new_profile)
            QMessageBox.information(self, self.tr("Settings Saved"), self.tr("Figure extraction/review profile updated."))

    def change_language(self, lang):
        self.current_lang = lang
        self.refresh_profile_list()
        self.refresh_figure_profile_list()
        self.retranslate_ui()

    def set_theme(self, theme):
        theme = normalize_theme(theme)
        from .style import (
            BUTTON_ROLE_COMMIT,
            BUTTON_ROLE_DESTRUCTIVE,
            BUTTON_ROLE_NEUTRAL,
            BUTTON_ROLE_RUN,
            BUTTON_ROLE_STOP,
            apply_theme_button_style,
            get_theme_config,
        )

        self.current_theme = theme
        c = get_theme_config(theme)
        self.log_area.setStyleSheet(
            f"QTextEdit {{ background: {c['bg_input']}; color: {c['text_main']}; "
            f"border: 1px solid {c['border']}; border-radius: 10px; padding: 8px; "
            f"selection-background-color: {c['accent_soft']}; }}"
        )
        apply_theme_button_style(self.btn_save_api_settings, BUTTON_ROLE_COMMIT, "padding: 5px;", theme)
        apply_theme_button_style(self.btn_delete_profile, BUTTON_ROLE_DESTRUCTIVE, "", theme)
        apply_theme_button_style(self.btn_adv_config, BUTTON_ROLE_NEUTRAL, "padding: 5px;", theme)
        apply_theme_button_style(self.btn_delete_figure_profile, BUTTON_ROLE_DESTRUCTIVE, "", theme)
        apply_theme_button_style(self.btn_adv_figure_config, BUTTON_ROLE_NEUTRAL, "padding: 5px;", theme)
        apply_theme_button_style(self.btn_src, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_out, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_restore_interrupted_run, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(
            self.btn_run_classify,
            BUTTON_ROLE_RUN,
            "font-weight: bold; padding: 12px; font-size: 14px;",
            theme,
        )
        apply_theme_button_style(
            self.btn_stop_classify,
            BUTTON_ROLE_STOP,
            "font-weight: bold; padding: 12px; font-size: 14px;",
            theme,
        )
        apply_theme_button_style(self.btn_ext_src, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_db, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(
            self.btn_run_extract,
            BUTTON_ROLE_RUN,
            "font-weight: bold; padding: 12px; font-size: 14px;",
            theme,
        )
        apply_theme_button_style(
            self.btn_stop_extract,
            BUTTON_ROLE_STOP,
            "font-weight: bold; padding: 12px; font-size: 14px;",
            theme,
        )
        apply_theme_button_style(self.btn_browse_db, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_export_jsonl, BUTTON_ROLE_COMMIT, "", theme)

    def browse_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, self.tr("Select Directory"))
        if d: line_edit.setText(d)

    def browse_save_db(self):
        f, _ = QFileDialog.getSaveFileName(self, self.tr("Select Database File"), "", "SQLite DB (*.db)")
        if f: self.edit_db_path.setText(f)

    def log(self, msg):
        self.log_area.append(msg)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def update_progress(self, current, total):
        if total <= 0:
            total = 1
        if current < 0:
            current = 0
        if current > total:
            current = total
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"%v / %m ({int(current/total*100)}%)")

    def start_classify(self):
        src = self.edit_src_folder.text()
        out = self.edit_out_folder.text()
        if not src or not out:
             QMessageBox.warning(self, self.tr("Error"), self.tr("Please select source and output directories."))
             return
             
        self.toggle_buttons(True)
        self.progress_bar.setValue(0)

        mode = self.combo_mode.currentData() or "v2"
        selected_profile_mode = self._normalize_mode(self.screener_config.get("processing_mode"), "v2")
        if selected_profile_mode != mode and self.combo_profiles.currentData() not in ["DEFAULT", "DEFAULT_V2"]:
            QMessageBox.warning(
                self,
                self.tr("Error"),
                self.tr("Profile mode mismatch. Please select a profile matching current screening mode."),
            )
            self.toggle_buttons(False)
            return

        try:
            lines_per_pdf = int(self.edit_lines_per_pdf.text() or "30")
        except ValueError:
            lines_per_pdf = 30
        try:
            batch_size = int(self.edit_batch_size.text() or "80")
        except ValueError:
            batch_size = 80
        try:
            fallback_batch = int(self.edit_fallback_batch.text() or "40")
        except ValueError:
            fallback_batch = 40
        try:
            include_threshold = float(self.edit_include_threshold.text() or "0.75")
        except ValueError:
            include_threshold = 0.75
        try:
            batch_char_budget = int(self.edit_batch_char_budget.text() or "100000")
        except ValueError:
            batch_char_budget = 100000
        try:
            max_text_chars = int(self.edit_max_text_chars.text() or "1600")
        except ValueError:
            max_text_chars = 1600
        try:
            llm_batch_tokens = int(self.edit_llm_batch_tokens.text() or "12000")
        except ValueError:
            llm_batch_tokens = 12000
        try:
            llm_timeout = int(self.edit_llm_timeout.text() or "240")
        except ValueError:
            llm_timeout = 240

        lines_per_pdf = max(1, lines_per_pdf)
        batch_size = max(1, batch_size)
        fallback_batch = max(1, fallback_batch)
        batch_char_budget = max(5000, batch_char_budget)
        max_text_chars = max(200, max_text_chars)
        llm_batch_tokens = max(500, llm_batch_tokens)
        llm_timeout = max(30, llm_timeout)
        if include_threshold < 0:
            include_threshold = 0.0
        if include_threshold > 1:
            include_threshold = 1.0
        if fallback_batch > batch_size:
            fallback_batch = batch_size

        split_failed_batches = self.check_split_failed_batches.isChecked()
        resume_runs = self.check_resume_runs.isChecked()
        isolate_runs = self.check_isolate_runs.isChecked()

        runtime_config = dict(self.screener_config)
        api_protocol = self.combo_api_protocol.currentData() or "auto"
        runtime_config.update(
            {
                "processing_mode": mode,
                "lines_per_pdf": lines_per_pdf,
                "csv_batch_size": batch_size,
                "csv_batch_fallback_size": fallback_batch,
                "batch_char_budget": batch_char_budget,
                "max_text_chars_per_file": max_text_chars,
                "llm_batch_max_tokens": llm_batch_tokens,
                "llm_request_timeout_seconds": llm_timeout,
                "include_confidence_threshold": include_threshold,
                "api_protocol": api_protocol,
                "split_failed_batches": split_failed_batches,
                "resume_interrupted_runs": resume_runs,
                "isolate_v2_runs": isolate_runs,
            }
        )
        self.screener_config.update(runtime_config)
        runtime_config.setdefault(
            "llm_batch_prompt_template",
            runtime_config.get("llm_prompt_template", LLMScreenPDFClassifier.DEFAULT_CONFIG.get("llm_batch_prompt_template", "")),
        )

        self.log(self.tr("--- Starting Task with Profile: {0} ---").format(self.current_profile_name))
        self.log(
            self.tr("--- Runtime Mode: {0} | lines={1} | batch={2}/{3} | chars={4} | text_chars={5} | max_tokens={6} | timeout={7}s | threshold={8:.2f} | split={9} | resume={10} | isolate={11} | api_protocol={12} ---").format(
                mode.upper(),
                lines_per_pdf,
                batch_size,
                fallback_batch,
                batch_char_budget,
                max_text_chars,
                llm_batch_tokens,
                llm_timeout,
                include_threshold,
                split_failed_batches,
                resume_runs,
                isolate_runs,
                api_protocol,
            )
        )

        self.worker = PDFWorker("classify", lang=self.current_lang, source=src, output=out, 
                                api_key=self.edit_api_key.text(), 
                                base_url=self.edit_base_url.text(),
                                model=self.edit_model.text(),
                                screener_config=runtime_config,
                                profile_name=self.current_profile_name) # Pass name
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.result_signal.connect(self.on_worker_result)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def start_extract(self):
        src = self.edit_ext_src.text()
        db = self.edit_db_path.text()
        if not src:
             QMessageBox.warning(self, self.tr("Error"), self.tr("Please select input folder."))
             return
             
        # Config for MLLM
        mllm_config = {}
        mllm_api = self._current_multimodal_api_settings()
        if mllm_api.get("api_key"):
             try:
                 batch_size = max(1, int(self.edit_batch_size.text() or "80"))
             except ValueError:
                 batch_size = 80
             try:
                 fallback_batch = max(1, int(self.edit_fallback_batch.text() or "40"))
             except ValueError:
                 fallback_batch = 40
             try:
                 batch_char_budget = max(3000, int(self.edit_batch_char_budget.text() or "24000"))
             except ValueError:
                 batch_char_budget = 24000
             try:
                 llm_batch_tokens = max(500, int(self.edit_llm_batch_tokens.text() or "4000"))
             except ValueError:
                 llm_batch_tokens = 4000
             try:
                 llm_timeout = max(30, int(self.edit_llm_timeout.text() or "180"))
             except ValueError:
                 llm_timeout = 180
             mllm_config = {
                  "default_provider": "silicon_flow",
                  "api_protocol": mllm_api.get("api_protocol") or "auto",
                  "image_detail": mllm_api.get("image_detail") or "auto",
                  "review_batch_size": batch_size,
                  "review_batch_fallback_size": min(batch_size, fallback_batch),
                  "batch_char_budget": batch_char_budget,
                  "batch_max_tokens": llm_batch_tokens,
                  "timeout": llm_timeout,
                  "providers": {
                      "silicon_flow": {
                          "api_key": mllm_api.get("api_key", ""),
                          "base_url": mllm_api.get("base_url", ""),
                          "model": mllm_api.get("model", "")
                     }
                 }
             }

        use_mllm = self.check_mllm.isChecked()
        if not self._confirm_extract_preflight(use_mllm, mllm_config):
            return

        self.toggle_buttons(True)
        self.progress_bar.setValue(0)
        
        self.worker = PDFWorker("extract", lang=self.current_lang, pdf_dir=src, db_path=db, 
                                use_mllm=use_mllm,
                                mllm_config=mllm_config,
                                figure_profile=deepcopy(self.figure_profile),
                                figure_profile_path=self.current_figure_profile_path,
                                figure_profile_name=self.current_figure_profile_name)
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def stop_worker(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.log(self.tr("Stopping... (Waiting for current PDF to finish or hit timeout)"))
            self.btn_stop_classify.setEnabled(False)
            self.btn_stop_extract.setEnabled(False)

    def on_worker_result(self, results):
        if 'txt' in results and 'csv' in results and os.path.exists(results['txt']) and os.path.exists(results['csv']):
            dlg = ProcessingResultDialog(results['txt'], results['csv'], self, self.current_lang)
            dlg.exec()

    def on_finished(self):
        self.worker = None
        self.toggle_buttons(False)
        self.log(self.tr("Task Finished."))

    def toggle_buttons(self, running):
        # running = True means task started, so Start disabled, Stop enabled
        self.btn_run_classify.setEnabled(not running)
        self.btn_run_extract.setEnabled(not running)
        self.btn_restore_interrupted_run.setEnabled(not running)
        self.btn_stop_classify.setEnabled(running)
        self.btn_stop_extract.setEnabled(running)

    def browse_database(self):
        db_path = self.edit_db_path.text()
        if not os.path.exists(db_path):
            QMessageBox.warning(self, self.tr("Error"), self.tr("No DB selected or file not found."))
            return
        dlg = DatabaseViewerDialog(db_path, self, self.current_lang)
        dlg.exec()

    def export_jsonl(self):
        db_path = self.edit_db_path.text()
        if not os.path.exists(db_path):
            QMessageBox.warning(self, self.tr("Error"), self.tr("No DB selected or file not found."))
            return

        # Show warning
        reply = themed_ok_cancel_message(
            self,
            self.tr("Export PDF Extract Dataset (JSONL)"),
            self.tr("This JSONL contains raw records extracted from PDFs and has not been manually curated.\nUse it for quick model checks, not as a trusted training set.\n\nFor researcher-verified training data, export from the Labeling Workbench."),
            ok_role=BUTTON_ROLE_COMMIT,
            cancel_role=BUTTON_ROLE_STOP,
        )
        if reply == QMessageBox.Cancel:
            return

        save_path, _ = QFileDialog.getSaveFileName(self, self.tr("Export PDF Extract Dataset (JSONL)"), "", "JSONL (*.jsonl)")
        if not save_path: return

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='figure_records'")
            has_v2_table = cursor.fetchone() is not None
            if has_v2_table:
                cursor.execute(
                    """
                    SELECT
                        f.id,
                        f.image_file_path,
                        f.image_file_name,
                        f.caption_text,
                        f.species_candidate,
                        f.page_number,
                        f.final_confidence
                    FROM figure_records f
                    WHERE f.accepted = 1
                    ORDER BY f.id ASC
                    """
                )
                figure_rows = cursor.fetchall()
                rows = []
                for figure_id, img_path, img_name, caption_text, species_candidate, page_number, final_confidence in figure_rows:
                    cursor.execute(
                        """
                        SELECT evidence_level, text_content
                        FROM figure_evidence
                        WHERE figure_id = ?
                        ORDER BY CASE evidence_level
                            WHEN 'figure_local' THEN 1
                            WHEN 'species_core' THEN 2
                            ELSE 3
                        END, match_score DESC, id ASC
                        """,
                        (figure_id,),
                    )
                    evidence_rows = cursor.fetchall()
                    evidence_text = []
                    for level, text_content in evidence_rows:
                        evidence_text.append(f"[{level}] {text_content}")
                    rows.append((img_path, img_name, "\n".join(filter(None, [caption_text or "", *evidence_text])), species_candidate, page_number, final_confidence))
            else:
                cursor.execute("""
                    SELECT i.image_file_path, i.image_file_name, t.text_content, '', 0, i.confidence_score
                    FROM image_text_relations r
                    JOIN images i ON r.image_id = i.id
                    JOIN text_blocks t ON r.text_block_id = t.id
                    WHERE i.is_taxonomic = 1 AND r.confidence_level = 'high'
                """)
                rows = cursor.fetchall()
            count = 0
            
            with open(save_path, 'w', encoding='utf-8') as f:
                for img_path, img_name, text, species_candidate, page_number, final_confidence in rows:
                    entry = {
                        "image": img_name,
                        "text": text,
                        "source": "pdf_raw_extract",
                        "species_candidate": species_candidate,
                        "page_number": page_number,
                        "confidence": final_confidence,
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    count += 1
                    
            QMessageBox.information(self, self.tr("Export Success"), 
                                    self.tr("Exported {} records to {}").format(count, save_path))
            conn.close()
            
        except Exception as e:
            QMessageBox.critical(self, self.tr("Error"), str(e))
