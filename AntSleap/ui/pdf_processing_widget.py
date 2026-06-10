from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton, 
                               QFileDialog, QTextEdit, QProgressBar, QGroupBox, QCheckBox, QMessageBox, 
                               QTabWidget, QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, 
                               QScrollArea, QComboBox, QApplication, QStackedWidget, QListWidget, QListWidgetItem,
                               QListView, QButtonGroup, QRadioButton, QAbstractItemView)
from PySide6.QtCore import QThread, Signal, Qt, QSize
from PySide6.QtGui import QPixmap, QImage, QIntValidator, QDoubleValidator, QIcon
import importlib
import importlib.util
from copy import deepcopy
import base64
import os
import struct
import sys
import csv
import sqlite3
import json
import zlib
import requests
import shutil
import time

try:
    from AntSleap.core.platform_open import open_path
except ModuleNotFoundError:
    from core.platform_open import open_path

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


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


def _load_pdf_processor_dependencies():
    try:
        module = importlib.import_module("core.pdf_processor")
        return getattr(module, "LLMScreenPDFClassifier"), getattr(
            module,
            "EnhancedPDFExtractionSystem",
        ), getattr(module, "discover_poppler", None)
    except ModuleNotFoundError as exc:
        if exc.name != "core.pdf_processor":
            raise

    repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    package_dir = os.path.join(repo_root, "core", "pdf_processor")
    init_file = os.path.join(package_dir, "__init__.py")

    spec = importlib.util.spec_from_file_location(
        "taxamask_pdf_processor",
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
    ), getattr(module, "discover_poppler", None)


def _load_figure_profile_dependencies():
    try:
        module = importlib.import_module("core.pdf_processor.figure_profile")
    except ModuleNotFoundError as exc:
        if exc.name not in {"core", "core.pdf_processor", "core.pdf_processor.figure_profile"}:
            raise
        repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
        profile_file = os.path.join(repo_root, "core", "pdf_processor", "figure_profile.py")
        spec = importlib.util.spec_from_file_location("taxamask_figure_profile", profile_file)
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


def _load_part_description_profile_dependencies():
    try:
        module = importlib.import_module("core.pdf_processor.part_description_profile")
    except ModuleNotFoundError as exc:
        if exc.name not in {"core", "core.pdf_processor", "core.pdf_processor.part_description_profile"}:
            raise
        repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
        profile_file = os.path.join(repo_root, "core", "pdf_processor", "part_description_profile.py")
        spec = importlib.util.spec_from_file_location("taxamask_part_description_profile", profile_file)
        if spec is None or spec.loader is None:
            raise ModuleNotFoundError(f"Unable to load part_description_profile module from: {profile_file}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return (
        getattr(module, "load_part_description_profile"),
        getattr(module, "normalize_part_description_profile"),
        getattr(module, "profile_display_name"),
    )


LLMScreenPDFClassifier, EnhancedPDFExtractionSystem, discover_poppler = _load_pdf_processor_dependencies()
load_figure_profile, normalize_figure_profile, profile_display_name = _load_figure_profile_dependencies()
(
    load_part_description_profile,
    normalize_part_description_profile,
    part_description_profile_display_name,
) = _load_part_description_profile_dependencies()


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
        "Test Text LLM": "测试文本模型",
        "Test Multimodal LLM": "测试多模态模型",
        "Remember API Key": "记住API密钥",
        "Remember Multimodal API Key": "记住多模态API密钥",
        "API settings saved.": "API设置已保存。",
        "Failed to save API settings: {}": "保存API设置失败: {}",
        "Failed to load API settings: {}": "加载API设置失败: {}",
        "Connection Test": "连接测试",
        "Please fill API key, Base URL, and model first.": "请先填写 API 密钥、Base URL 和模型名称。",
        "Another LLM connection test is already running.": "已有一个 LLM 连接测试正在运行。",
        "Testing Text LLM connection...": "正在测试文本模型连接...",
        "Testing Multimodal LLM connection...": "正在测试多模态模型连接...",
        "Text LLM test passed: {0}": "文本模型测试通过：{0}",
        "Multimodal LLM test passed: {0}": "多模态模型测试通过：{0}",
        "Text LLM test failed: {0}": "文本模型测试失败：{0}",
        "Multimodal LLM test failed: {0}": "多模态模型测试失败：{0}",
        "Send a tiny text-only request to verify the text model settings before screening PDFs.": "发送一个极小的纯文本请求，在筛选 PDF 前验证文本模型配置。",
        "Send a tiny generated PNG plus text to verify the vision model settings before extracting figures.": "发送一张极小的程序生成 PNG 和文本，在提取图版前验证视觉模型配置。",
        "PDF Evidence Tools": "PDF 文献处理工具",
        "Agent first: configure keys/models, then adapt PDF screening and figure-review rules to the target taxon.": "先让 Agent 引导配置 key/模型，再按目标类群适配 PDF 筛选和图文复核规则。",
        "Start Center": "启动中心",
        "Ask Agent": "询问 Agent",
        "Ask Agent to check key/model readiness, then adapt target taxon, screening profile, figure-review profile, provenance, and safe candidate review before running.": "运行前让 Agent 先检查 key/模型是否就绪，再适配目标类群、筛选方案、图文复核方案、证据来源和候选复核边界。",
        "Show Advanced Config": "显示高级配置",
        "Hide Advanced Config": "隐藏高级配置",
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
        "Result Folder:": "结果文件夹:",
        "Database File:": "数据库文件:",
        "Choose Result Folder": "选择结果文件夹",
        "Select Result Folder": "选择结果文件夹",
        "Choose a result folder for this extraction run. The database index and the '<database>_v2_artifacts' folder for images, review batches, and raw LLM responses will be saved there.": "选择本次提取的结果文件夹。数据库索引和用于保存图像、复核批次、LLM 原始响应的“<数据库名>_v2_artifacts”文件夹都会保存在这里。",
        "Database filename for this extraction run. If you omit .db, it will be added automatically.": "本次提取使用的数据库文件名。如果省略 .db，程序会自动补上。",
        "Enable Multimodal Validation (Uses API - Slower but more accurate)": "启用多模态验证 (使用 API - 较慢但更准确)",
        "Poppler: checking...": "Poppler：正在检测...",
        "Poppler: found ({0}) - PDF OCR/image fallback is available.": "Poppler：已找到（{0}）- PDF OCR/图像回退可用。",
        "Poppler: not found - PyMuPDF extraction can still run, but pdf2image/OCR fallback may be unavailable.": "Poppler：未找到 - PyMuPDF 提取仍可运行，但 pdf2image/OCR 回退可能不可用。",
        "Poppler status: {0}": "Poppler 状态：{0}",
        "Start Extraction Pipeline": "开始提取流程",
        "Stop Extraction": "停止提取",
        "3. Data Utilities": "3. 数据工具",
        "Open Database File": "打开数据库文件",
        "Choose an existing .db file to browse.": "选择一个已有 .db 文件进行浏览。",
        "First": "首页",
        "Previous": "上一页",
        "Next": "下一页",
        "Last": "末页",
        "Go": "跳转",
        "Page:": "页码:",
        "Rows/page:": "每页行数:",
        "Showing {0}-{1} of {2} | Page {3}/{4}": "第 {0}-{1} 行，共 {2} 行 | 第 {3}/{4} 页",
        "No rows": "无记录",
        "Search:": "搜索:",
        "Status:": "状态:",
        "Human:": "人工:",
        "VLM:": "多模态:",
        "Sort:": "排序:",
        "Accepted only": "仅 accepted",
        "Needs review": "待复核",
        "Rejected": "已拒绝",
        "All": "全部",
        "Any": "任意",
        "Unreviewed": "未人工复核",
        "Human accepted": "人工通过",
        "Human rejected": "人工拒绝",
        "Import ready": "可导入",
        "Needs crop": "需裁剪",
        "Real": "真实",
        "Mock/none": "Mock/无",
        "Newest first": "最新在前",
        "Oldest first": "最旧在前",
        "Score high-low": "分数高到低",
        "Score low-high": "分数低到高",
        "PDF name": "PDF 名称",
        "Species": "物种",
        "Apply Filters": "应用筛选",
        "Clear Filters": "清空筛选",
        "Clear current filters?": "确认清空当前筛选？",
        "This will reset search, filters, sorting, and page position. It will not delete database records or human review notes.": "这会重置搜索、筛选、排序和当前页位置。不会删除数据库记录，也不会删除人工复核备注。",
        "Table": "表格",
        "Gallery": "图库",
        "Open Image": "打开图片",
        "Open Folder": "打开文件夹",
        "Open PDF": "打开 PDF",
        "Save Review": "保存复核",
        "Mark Filtered Import Ready": "当前筛选全部设为可导入/通过",
        "Mark {0} passable rows as import_ready? {1} rows already marked rejected/needs_crop will be kept.": "确认将当前筛选中 {0} 条可通过记录设为“可导入/通过”？已有 {1} 条人工拒绝/需裁剪记录会被保留。",
        "Marked {0} filtered rows as import_ready.": "已将 {0} 条筛选记录设为“可导入/通过”。",
        "No passable rows match the current filters.": "当前筛选条件下没有可批量通过的记录。",
        "Human Status:": "人工状态:",
        "Review Note:": "复核备注:",
        "Export Filtered CSV": "导出筛选 CSV",
        "Copy Filtered Images": "复制筛选图片",
        "No image path selected.": "未选中图片路径。",
        "Path does not exist: {0}": "路径不存在：{0}",
        "No source PDF found for this row.": "未找到当前记录的来源 PDF。",
        "Human review saved.": "人工复核已保存。",
        "Export finished: {0} rows -> {1}": "导出完成：{0} 行 -> {1}",
        "Copied {0} images -> {1}": "已复制 {0} 张图片 -> {1}",
        "No rows match the current filters.": "当前筛选条件下没有记录。",
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
        "  > Import-ready accepted figures: {0} -> {1}": "  > 可直接导入的通过图: {0} -> {1}",
        "  > Needs-review figure copies: {0} -> {1}": "  > 待人工复核图片副本: {0} -> {1}",
        "Advanced Logic Settings": "高级逻辑设置",
        "Advanced Figure Settings": "高级图文方案设置",
        "Advanced Part Description Settings": "高级文献性状描述方案设置",
        "Figure Extraction / Review Profile:": "图文提取/复核方案:",
        "Part Description Profile:": "文献性状描述抽取方案:",
        "Built-in Ant Taxonomy Figure Profile": "内置蚂蚁分类学图版宽松复核方案",
        "Built-in Ant Part Description Profile": "内置蚂蚁分类学文献性状描述抽取方案",
        "Failed to load figure profile: {0}": "加载图文方案失败: {0}",
        "Failed to save figure profile: {0}": "保存图文方案失败: {0}",
        "Failed to load part description profile: {0}": "加载文献性状描述方案失败: {0}",
        "Failed to save part description profile: {0}": "保存文献性状描述方案失败: {0}",
        "Invalid figure profile JSON: {0}": "图文方案 JSON 无效: {0}",
        "Invalid part description profile JSON: {0}": "文献性状描述方案 JSON 无效: {0}",
        "Figure extraction/review profile updated.": "图文提取/复核方案已更新。",
        "Part description profile updated.": "文献性状描述抽取方案已更新。",
        "Edit the figure extraction and multimodal review profile JSON. API keys are not stored here.": "编辑图文提取与多模态复核方案 JSON。API 密钥不会保存在这里。",
        "Edit the pure-text part-description extraction profile JSON. API keys are not stored here.": "编辑纯文本 PDF 文献性状描述抽取方案 JSON。API 密钥不会保存在这里。",
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
        "\n--- Taxon Part Descriptions ---\n": "\n--- 物种部位描述 ---\n",
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
        "https://api.example.com/v1": "https://api.example.com/v1",
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
        "  > Existing completed PDF result found; skipped re-extraction.": "  > 检测到该 PDF 已有完整提取结果，已跳过重复提取。",
        "  > Run Output Directory: {0}": "  > 运行输出目录：{0}",
        "  > Run Status: {0}": "  > 运行状态：{0}",
        "  > Partial results were saved to disk.": "  > 部分结果已保存到磁盘。",
        "Initializing Extractor...": "正在初始化提取器...",
        "  > Figure Profile: {0}": "  > 图文方案：{0}",
        "  > Part Description Profile: {0}": "  > 部位描述方案：{0}",
        "No PDF files found in input directory.": "输入目录中未找到 PDF 文件。",
        "Processing {0}/{1}: {2}": "正在处理 {0}/{1}：{2}",
        "  > Figures: {0}, Accepted: {1}, Review: {2}": "  > 图像：{0}，接受：{1}，复核：{2}",
        "  > Part descriptions: {0}, Text blocks: {1}, Status: {2}": "  > 部位描述：{0}，文本块：{1}，状态：{2}",
        "  > Part descriptions: {0}, Text blocks: {1}, Status: {2}, Profile: {3}": "  > 部位描述：{0}，文本块：{1}，状态：{2}，方案：{3}",
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

class HumanReviewSaveWorker(QThread):
    saved = Signal(str, int, str, str)
    failed = Signal(str)

    def __init__(self, db_path, source_table, record_id, status, note, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.source_table = source_table
        self.record_id = int(record_id)
        self.status = status
        self.note = note

    def run(self):
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS figure_human_reviews (
                        source_table TEXT NOT NULL,
                        record_id INTEGER NOT NULL,
                        human_status TEXT NOT NULL DEFAULT 'unreviewed',
                        review_note TEXT DEFAULT '',
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (source_table, record_id)
                    )
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO figure_human_reviews (source_table, record_id, human_status, review_note, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(source_table, record_id) DO UPDATE SET
                        human_status = excluded.human_status,
                        review_note = excluded.review_note,
                        updated_at = excluded.updated_at
                    """,
                    (
                        self.source_table,
                        self.record_id,
                        self.status,
                        self.note,
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
            self.saved.emit(self.source_table, self.record_id, self.status, self.note)
        except Exception as exc:
            self.failed.emit(str(exc))


class DatabaseViewerDialog(QDialog):
    DEFAULT_PAGE_SIZE = 500
    MAX_PAGE_SIZE = 5000

    def __init__(self, db_path, parent=None, lang="en"):
        super().__init__(parent)
        self.db_path = db_path
        self.lang = lang
        self.current_page = 1
        self.page_size = self.DEFAULT_PAGE_SIZE
        self.total_rows = 0
        self.total_pages = 1
        self._active_table = ""
        self._current_rows = []
        self._selected_record = None
        self._sort_options = []
        self._table_widths_initialized = set()
        self._review_save_workers = []
        self.setWindowTitle(self.tr("Database Viewer"))
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        self.setSizeGripEnabled(True)
        self.setMinimumSize(1200, 760)
        self.resize(1600, 960)
        self.init_ui()
        self.load_data()

    def tr(self, text):
        if self.lang == "zh":
            return TRANSLATIONS["zh"].get(text, text)
        return text

    def _clamped_int(self, value, default, minimum, maximum):
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            number = int(default)
        return max(int(minimum), min(int(maximum), number))

    def _ensure_human_review_table(self, cursor):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS figure_human_reviews (
                source_table TEXT NOT NULL,
                record_id INTEGER NOT NULL,
                human_status TEXT NOT NULL DEFAULT 'unreviewed',
                review_note TEXT DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (source_table, record_id)
            )
            """
        )

    def _refresh_schema(self, cursor):
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        self._db_tables = {str(row[0]) for row in cursor.fetchall()}
        self._table_columns = {}
        for table in self._db_tables:
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                self._table_columns[table] = {str(row[1]) for row in cursor.fetchall()}
            except sqlite3.Error:
                self._table_columns[table] = set()

    def _has_col(self, table, column):
        return column in self._table_columns.get(table, set())

    def _has_table(self, table):
        return table in getattr(self, "_db_tables", set())

    def _sql_col(self, table, alias, column, default="''"):
        return f"{alias}.{column}" if self._has_col(table, column) else str(default)

    def _maybe_join_pdf_files(self, source_table, alias):
        if self._has_table("pdf_files") and self._has_col(source_table, "pdf_file_id"):
            return f"LEFT JOIN pdf_files p ON p.id = {alias}.pdf_file_id"
        return ""

    def _pdf_name_expr(self):
        return "COALESCE(p.file_name, '')" if self._has_table("pdf_files") else "''"

    def _pdf_path_expr(self):
        return "COALESCE(p.file_path, '')" if self._has_table("pdf_files") else "''"

    def _filter_state(self):
        return {
            "search": self.search_edit.text().strip(),
            "status": self.status_combo.currentData() or "",
            "human": self.human_filter_combo.currentData() or "",
            "vlm": self.vlm_filter_combo.currentData() or "",
            "sort": self.sort_combo.currentData() or "newest",
        }

    def _has_active_filters(self):
        return (
            bool(self.search_edit.text().strip())
            or self.status_combo.currentIndex() > 0
            or self.human_filter_combo.currentIndex() > 0
            or self.vlm_filter_combo.currentIndex() > 0
            or self.sort_combo.currentIndex() > 0
            or self.current_page > 1
        )

    def _selected_human_status(self):
        button = self.human_status_group.checkedButton()
        if button is None:
            return "unreviewed"
        return str(button.property("value") or "unreviewed")

    def _set_human_status_choice(self, status):
        normalized = str(status or "unreviewed")
        button = self.human_status_buttons.get(normalized) or self.human_status_buttons.get("unreviewed")
        if button is not None:
            button.setChecked(True)

    def _apply_table_default_widths(self):
        table_key = self._active_table or "unknown"
        if table_key in self._table_widths_initialized:
            return
        if self._active_table == "figure_records":
            widths = [70, 180, 420, 90, 90, 80, 180, 180, 130, 260]
        else:
            widths = [70, 180, 420, 90, 110, 180, 130, 260]
        for column, width in enumerate(widths):
            if column < self.table.columnCount():
                self.table.setColumnWidth(column, width)
        self._table_widths_initialized.add(table_key)

    def _build_v2_query_parts(self, *, count_only=False, include_limit=True):
        filters = self._filter_state()
        score_expr = self._sql_col("figure_records", "f", "final_confidence", "0")
        accepted_expr = self._sql_col("figure_records", "f", "accepted", "0")
        page_expr = self._sql_col("figure_records", "f", "page_number", "0")
        species_expr = self._sql_col("figure_records", "f", "species_candidate", "''")
        review_expr = self._sql_col("figure_records", "f", "review_status", "''")
        mode_expr = self._sql_col("figure_records", "f", "multimodal_review_mode", "''")
        validated_expr = self._sql_col("figure_records", "f", "multimodal_validated", "0")
        caption_expr = self._sql_col("figure_records", "f", "caption_text", "''")
        rejection_expr = self._sql_col("figure_records", "f", "rejection_reason", "''")
        pdf_name_expr = self._pdf_name_expr()
        pdf_path_expr = self._pdf_path_expr()
        select = "COUNT(*)" if count_only else (
            f"f.id, f.image_file_name, f.image_file_path, {score_expr}, {accepted_expr}, "
            f"{page_expr}, {species_expr}, COALESCE({review_expr}, ''), "
            f"COALESCE({mode_expr}, ''), COALESCE({validated_expr}, 0), "
            f"{pdf_name_expr}, {pdf_path_expr}, "
            "COALESCE(h.human_status, 'unreviewed'), COALESCE(h.review_note, '')"
        )
        sql = [
            f"SELECT {select}",
            "FROM figure_records f",
            "LEFT JOIN figure_human_reviews h ON h.source_table = 'figure_records' AND h.record_id = f.id",
        ]
        pdf_join = self._maybe_join_pdf_files("figure_records", "f")
        if pdf_join:
            sql.append(pdf_join)
        where = []
        params = []
        status = filters["status"]
        if status == "accepted":
            where.append(f"({accepted_expr} = 1 OR {review_expr} = 'accepted')")
        elif status == "needs_review":
            where.append(f"{review_expr} = 'needs_review'")
        elif status == "rejected":
            where.append(f"({accepted_expr} = 0 AND {review_expr} = 'rejected')")
        human = filters["human"]
        if human == "__unreviewed__":
            where.append("(h.human_status IS NULL OR h.human_status = 'unreviewed')")
        elif human:
            where.append("h.human_status = ?")
            params.append(human)
        vlm = filters["vlm"]
        if vlm == "real":
            where.append(f"(COALESCE({validated_expr}, 0) = 1 OR {mode_expr} = 'real')")
        elif vlm == "mock_none":
            where.append(f"(COALESCE({validated_expr}, 0) = 0 AND COALESCE({mode_expr}, '') != 'real')")
        search = filters["search"]
        if search:
            like = f"%{search}%"
            search_parts = [
                "f.image_file_name LIKE ?",
                "f.image_file_path LIKE ?",
                f"COALESCE({species_expr}, '') LIKE ?",
                f"COALESCE({caption_expr}, '') LIKE ?",
                f"COALESCE({rejection_expr}, '') LIKE ?",
                f"{pdf_name_expr} LIKE ?",
                "COALESCE(h.review_note, '') LIKE ?",
            ]
            params.extend([like] * len(search_parts))
            if self._has_table("figure_evidence"):
                search_parts.append(
                    """
                    EXISTS (
                        SELECT 1 FROM figure_evidence e
                        WHERE e.figure_id = f.id AND (
                            COALESCE(e.text_content, '') LIKE ? OR COALESCE(e.section_title, '') LIKE ?
                        )
                    )
                    """
                )
                params.extend([like, like])
            if (
                self._has_table("taxon_part_descriptions")
                and self._has_col("figure_records", "pdf_file_id")
                and self._has_col("taxon_part_descriptions", "pdf_file_id")
            ):
                desc_search_cols = []
                for col in ("taxon_name", "part_label", "description_text"):
                    if self._has_col("taxon_part_descriptions", col):
                        desc_search_cols.append(f"COALESCE(d.{col}, '') LIKE ?")
                if desc_search_cols:
                    search_parts.append(
                        f"""
                        EXISTS (
                            SELECT 1 FROM taxon_part_descriptions d
                            WHERE d.pdf_file_id = f.pdf_file_id AND (
                                {" OR ".join(desc_search_cols)}
                            )
                        )
                        """
                    )
                    params.extend([like] * len(desc_search_cols))
            where.append("(" + " OR ".join(search_parts) + ")")
        if where:
            sql.append("WHERE " + " AND ".join(where))
        if not count_only:
            sort = filters["sort"]
            order_by = {
                "oldest": "f.id ASC",
                "score_desc": f"COALESCE({score_expr}, 0) DESC, f.id DESC",
                "score_asc": f"COALESCE({score_expr}, 0) ASC, f.id DESC",
                "pdf_name": f"{pdf_name_expr} ASC, {page_expr} ASC, f.id ASC",
                "species": f"{species_expr} ASC, {pdf_name_expr} ASC, f.id ASC",
            }.get(sort, "f.id DESC")
            sql.append(f"ORDER BY {order_by}")
            if include_limit:
                sql.append("LIMIT ? OFFSET ?")
        return "\n".join(sql), params

    def _build_legacy_query_parts(self, *, count_only=False, include_limit=True):
        filters = self._filter_state()
        score_expr = self._sql_col("images", "i", "confidence_score", "0")
        taxonomic_expr = self._sql_col("images", "i", "is_taxonomic", "0")
        pdf_name_expr = self._pdf_name_expr()
        pdf_path_expr = self._pdf_path_expr()
        select = "COUNT(*)" if count_only else (
            f"i.id, i.image_file_name, i.image_file_path, {score_expr}, {taxonomic_expr}, "
            f"{pdf_name_expr}, {pdf_path_expr}, "
            "COALESCE(h.human_status, 'unreviewed'), COALESCE(h.review_note, '')"
        )
        sql = [
            f"SELECT {select}",
            "FROM images i",
            "LEFT JOIN figure_human_reviews h ON h.source_table = 'images' AND h.record_id = i.id",
        ]
        pdf_join = self._maybe_join_pdf_files("images", "i")
        if pdf_join:
            sql.append(pdf_join)
        where = []
        params = []
        status = filters["status"]
        if status == "accepted":
            where.append(f"{taxonomic_expr} = 1")
        elif status in {"needs_review", "rejected"}:
            where.append(f"{taxonomic_expr} = 0")
        human = filters["human"]
        if human == "__unreviewed__":
            where.append("(h.human_status IS NULL OR h.human_status = 'unreviewed')")
        elif human:
            where.append("h.human_status = ?")
            params.append(human)
        search = filters["search"]
        if search:
            like = f"%{search}%"
            search_parts = [
                "i.image_file_name LIKE ?",
                "i.image_file_path LIKE ?",
                f"{pdf_name_expr} LIKE ?",
                "COALESCE(h.review_note, '') LIKE ?",
            ]
            params.extend([like] * len(search_parts))
            if self._has_table("image_text_relations") and self._has_table("text_blocks"):
                search_parts.append(
                    """
                    EXISTS (
                        SELECT 1 FROM image_text_relations r
                        JOIN text_blocks t ON r.text_block_id = t.id
                        WHERE r.image_id = i.id AND COALESCE(t.text_content, '') LIKE ?
                    )
                    """
                )
                params.append(like)
            where.append("(" + " OR ".join(search_parts) + ")")
        if where:
            sql.append("WHERE " + " AND ".join(where))
        if not count_only:
            sort = filters["sort"]
            order_by = {
                "oldest": "i.id ASC",
                "score_desc": f"COALESCE({score_expr}, 0) DESC, i.id DESC",
                "score_asc": f"COALESCE({score_expr}, 0) ASC, i.id DESC",
                "pdf_name": f"{pdf_name_expr} ASC, i.id ASC",
            }.get(sort, "i.id DESC")
            sql.append(f"ORDER BY {order_by}")
            if include_limit:
                sql.append("LIMIT ? OFFSET ?")
        return "\n".join(sql), params

    def init_ui(self):
        layout = QVBoxLayout(self)

        filters = QGridLayout()
        self.search_label = QLabel(self.tr("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.returnPressed.connect(self.apply_filters)
        self.status_label = QLabel(self.tr("Status:"))
        self.status_combo = NoWheelComboBox()
        self.status_combo.addItem(self.tr("All"), "")
        self.status_combo.addItem(self.tr("Accepted only"), "accepted")
        self.status_combo.addItem(self.tr("Needs review"), "needs_review")
        self.status_combo.addItem(self.tr("Rejected"), "rejected")
        self.human_filter_label = QLabel(self.tr("Human:"))
        self.human_filter_combo = NoWheelComboBox()
        for label, value in [
            (self.tr("Any"), ""),
            (self.tr("Unreviewed"), "__unreviewed__"),
            (self.tr("Human accepted"), "human_accepted"),
            (self.tr("Human rejected"), "human_rejected"),
            (self.tr("Import ready"), "import_ready"),
            (self.tr("Needs crop"), "needs_crop"),
        ]:
            self.human_filter_combo.addItem(label, value)
        self.vlm_filter_label = QLabel(self.tr("VLM:"))
        self.vlm_filter_combo = NoWheelComboBox()
        self.vlm_filter_combo.addItem(self.tr("Any"), "")
        self.vlm_filter_combo.addItem(self.tr("Real"), "real")
        self.vlm_filter_combo.addItem(self.tr("Mock/none"), "mock_none")
        self.sort_label = QLabel(self.tr("Sort:"))
        self.sort_combo = NoWheelComboBox()
        self.sort_combo.addItem(self.tr("Newest first"), "newest")
        self.sort_combo.addItem(self.tr("Oldest first"), "oldest")
        self.sort_combo.addItem(self.tr("Score high-low"), "score_desc")
        self.sort_combo.addItem(self.tr("Score low-high"), "score_asc")
        self.sort_combo.addItem(self.tr("PDF name"), "pdf_name")
        self.sort_combo.addItem(self.tr("Species"), "species")
        self.btn_apply_filters = QPushButton(self.tr("Apply Filters"))
        self.btn_clear_filters = QPushButton(self.tr("Clear Filters"))
        self.btn_apply_filters.clicked.connect(self.apply_filters)
        self.btn_clear_filters.clicked.connect(self.clear_filters)
        apply_semantic_button_style(self.btn_apply_filters, BUTTON_ROLE_RUN)
        apply_semantic_button_style(self.btn_clear_filters, BUTTON_ROLE_DESTRUCTIVE)
        filters.addWidget(self.search_label, 0, 0)
        filters.addWidget(self.search_edit, 0, 1, 1, 3)
        filters.addWidget(self.status_label, 0, 4)
        filters.addWidget(self.status_combo, 0, 5)
        filters.addWidget(self.human_filter_label, 0, 6)
        filters.addWidget(self.human_filter_combo, 0, 7)
        filters.addWidget(self.vlm_filter_label, 1, 0)
        filters.addWidget(self.vlm_filter_combo, 1, 1)
        filters.addWidget(self.sort_label, 1, 2)
        filters.addWidget(self.sort_combo, 1, 3)
        filters.addWidget(self.btn_apply_filters, 1, 4, 1, 2)
        filters.addWidget(self.btn_clear_filters, 1, 6, 1, 2)
        layout.addLayout(filters)

        pager = QHBoxLayout()
        self.btn_first = QPushButton(self.tr("First"))
        self.btn_prev = QPushButton(self.tr("Previous"))
        self.page_label = QLabel(self.tr("Page:"))
        self.page_edit = QLineEdit("1")
        self.page_edit.setFixedWidth(70)
        self.page_edit.setValidator(QIntValidator(1, 9999999, self))
        self.btn_go = QPushButton(self.tr("Go"))
        self.btn_next = QPushButton(self.tr("Next"))
        self.btn_last = QPushButton(self.tr("Last"))
        self.page_size_label = QLabel(self.tr("Rows/page:"))
        self.page_size_edit = QLineEdit(str(self.page_size))
        self.page_size_edit.setFixedWidth(80)
        self.page_size_edit.setValidator(QIntValidator(1, self.MAX_PAGE_SIZE, self))
        self.page_status = QLabel("")
        self.page_status.setMinimumWidth(260)
        self.btn_first.clicked.connect(lambda: self.goto_page(1))
        self.btn_prev.clicked.connect(lambda: self.goto_page(self.current_page - 1))
        self.btn_next.clicked.connect(lambda: self.goto_page(self.current_page + 1))
        self.btn_last.clicked.connect(lambda: self.goto_page(self.total_pages))
        self.btn_go.clicked.connect(self.apply_page_controls)
        self.page_edit.returnPressed.connect(self.apply_page_controls)
        self.page_size_edit.returnPressed.connect(self.apply_page_controls)
        for button in (self.btn_first, self.btn_prev, self.btn_go, self.btn_next, self.btn_last):
            apply_semantic_button_style(button, BUTTON_ROLE_NEUTRAL)
        pager.addWidget(self.btn_first)
        pager.addWidget(self.btn_prev)
        pager.addWidget(self.page_label)
        pager.addWidget(self.page_edit)
        pager.addWidget(self.btn_go)
        pager.addWidget(self.btn_next)
        pager.addWidget(self.btn_last)
        pager.addSpacing(12)
        pager.addWidget(self.page_size_label)
        pager.addWidget(self.page_size_edit)
        pager.addSpacing(12)
        pager.addWidget(self.page_status, 1)
        layout.addLayout(pager)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # Left: Table/Gallery
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        view_bar = QHBoxLayout()
        self.btn_table_view = QPushButton(self.tr("Table"))
        self.btn_gallery_view = QPushButton(self.tr("Gallery"))
        self.btn_table_view.clicked.connect(lambda: self.view_stack.setCurrentWidget(self.table))
        self.btn_gallery_view.clicked.connect(lambda: self.view_stack.setCurrentWidget(self.gallery))
        apply_semantic_button_style(self.btn_table_view, BUTTON_ROLE_NEUTRAL)
        apply_semantic_button_style(self.btn_gallery_view, BUTTON_ROLE_NEUTRAL)
        view_bar.addWidget(self.btn_table_view)
        view_bar.addWidget(self.btn_gallery_view)
        view_bar.addStretch(1)
        left_layout.addLayout(view_bar)
        self.view_stack = QStackedWidget()
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setWordWrap(False)
        table_header = self.table.horizontalHeader()
        table_header.setSectionResizeMode(QHeaderView.Interactive)
        table_header.setStretchLastSection(False)
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        table_header.sectionClicked.connect(self.on_header_clicked)
        self.gallery = QListWidget()
        self.gallery.itemSelectionChanged.connect(self.on_gallery_selected)
        self.gallery.setSelectionMode(QListWidget.SingleSelection)
        self.gallery.setViewMode(QListView.IconMode)
        self.gallery.setIconSize(QSize(160, 120))
        self.gallery.setGridSize(QSize(220, 180))
        self.gallery.setResizeMode(QListView.Adjust)
        self.gallery.setMovement(QListView.Static)
        self.gallery.setWordWrap(True)
        self.view_stack.addWidget(self.table)
        self.view_stack.addWidget(self.gallery)
        left_layout.addWidget(self.view_stack)
        splitter.addWidget(left_panel)
        
        # Right: Details (Image + Text)
        right_panel = QWidget()
        r_layout = QVBoxLayout(right_panel)

        detail_splitter = QSplitter(Qt.Vertical)
        detail_splitter.setChildrenCollapsible(False)

        self.lbl_img = QLabel(self.tr("Image Preview"))
        self.lbl_img.setAlignment(Qt.AlignCenter)
        self.lbl_img.setMinimumSize(360, 220)
        self.lbl_img.setStyleSheet("border: 1px dashed #666; background-color: #333;")

        text_panel = QWidget()
        text_layout = QVBoxLayout(text_panel)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.addWidget(QLabel(self.tr("Text Context")))
        self.txt_context = QTextEdit()
        self.txt_context.setReadOnly(True)
        text_layout.addWidget(self.txt_context, 1)

        detail_splitter.addWidget(self.lbl_img)
        detail_splitter.addWidget(text_panel)
        detail_splitter.setSizes([260, 620])
        detail_splitter.setStretchFactor(0, 1)
        detail_splitter.setStretchFactor(1, 4)
        r_layout.addWidget(detail_splitter, 1)

        review_layout = QGridLayout()
        self.human_status_label = QLabel(self.tr("Human Status:"))
        self.human_status_group = QButtonGroup(self)
        self.human_status_buttons = {}
        human_status_box = QWidget()
        human_status_layout = QHBoxLayout(human_status_box)
        human_status_layout.setContentsMargins(0, 0, 0, 0)
        human_status_layout.setSpacing(8)
        for label, value in [
            (self.tr("Unreviewed"), "unreviewed"),
            (self.tr("Human accepted"), "human_accepted"),
            (self.tr("Human rejected"), "human_rejected"),
            (self.tr("Import ready"), "import_ready"),
            (self.tr("Needs crop"), "needs_crop"),
        ]:
            button = QRadioButton(label)
            button.setProperty("value", value)
            self.human_status_group.addButton(button)
            self.human_status_buttons[value] = button
            human_status_layout.addWidget(button)
        human_status_layout.addStretch(1)
        self.human_status_buttons["unreviewed"].setChecked(True)
        self.review_note_label = QLabel(self.tr("Review Note:"))
        self.review_note_edit = QLineEdit()
        self.btn_save_review = QPushButton(self.tr("Save Review"))
        self.btn_save_review.clicked.connect(self.save_current_review)
        apply_semantic_button_style(self.btn_save_review, BUTTON_ROLE_COMMIT)
        review_layout.addWidget(self.human_status_label, 0, 0)
        review_layout.addWidget(human_status_box, 0, 1)
        review_layout.addWidget(self.review_note_label, 1, 0)
        review_layout.addWidget(self.review_note_edit, 1, 1)
        review_layout.addWidget(self.btn_save_review, 2, 1)
        r_layout.addLayout(review_layout)

        action_layout = QGridLayout()
        self.btn_open_image = QPushButton(self.tr("Open Image"))
        self.btn_open_folder = QPushButton(self.tr("Open Folder"))
        self.btn_open_pdf = QPushButton(self.tr("Open PDF"))
        self.btn_export_filtered = QPushButton(self.tr("Export Filtered CSV"))
        self.btn_copy_filtered = QPushButton(self.tr("Copy Filtered Images"))
        self.btn_mark_filtered_ready = QPushButton(self.tr("Mark Filtered Import Ready"))
        self.btn_open_image.clicked.connect(self.open_selected_image)
        self.btn_open_folder.clicked.connect(self.open_selected_folder)
        self.btn_open_pdf.clicked.connect(self.open_selected_pdf)
        self.btn_export_filtered.clicked.connect(self.export_filtered_csv)
        self.btn_copy_filtered.clicked.connect(self.copy_filtered_images)
        self.btn_mark_filtered_ready.clicked.connect(self.mark_filtered_import_ready)
        for button in (self.btn_open_image, self.btn_open_folder, self.btn_open_pdf, self.btn_export_filtered, self.btn_copy_filtered):
            apply_semantic_button_style(button, BUTTON_ROLE_NEUTRAL)
        apply_semantic_button_style(self.btn_mark_filtered_ready, BUTTON_ROLE_COMMIT)
        action_layout.addWidget(self.btn_open_image, 0, 0)
        action_layout.addWidget(self.btn_open_folder, 0, 1)
        action_layout.addWidget(self.btn_open_pdf, 0, 2)
        action_layout.addWidget(self.btn_export_filtered, 1, 0, 1, 2)
        action_layout.addWidget(self.btn_copy_filtered, 1, 2)
        action_layout.addWidget(self.btn_mark_filtered_ready, 2, 0, 1, 3)
        r_layout.addLayout(action_layout)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([520, 1080])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        
        layout.addWidget(splitter)
        
        btn_close = QPushButton(self.tr("Close"))
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def apply_page_controls(self):
        new_page_size = self._clamped_int(self.page_size_edit.text(), self.page_size, 1, self.MAX_PAGE_SIZE)
        new_page = self._clamped_int(self.page_edit.text(), self.current_page, 1, 9999999)
        self.page_size = new_page_size
        self.current_page = new_page
        self.load_data()

    def goto_page(self, page):
        self.current_page = self._clamped_int(page, self.current_page, 1, max(1, self.total_pages))
        self.load_data()

    def _update_pager_state(self):
        if self.total_rows <= 0:
            status = self.tr("No rows")
            start_row = end_row = 0
        else:
            start_row = (self.current_page - 1) * self.page_size + 1
            end_row = min(self.total_rows, self.current_page * self.page_size)
            status = self.tr("Showing {0}-{1} of {2} | Page {3}/{4}").format(
                start_row,
                end_row,
                self.total_rows,
                self.current_page,
                self.total_pages,
            )
        self.page_edit.setText(str(self.current_page))
        self.page_size_edit.setText(str(self.page_size))
        self.page_status.setText(status)
        has_prev = self.current_page > 1
        has_next = self.current_page < self.total_pages
        self.btn_first.setEnabled(has_prev)
        self.btn_prev.setEnabled(has_prev)
        self.btn_next.setEnabled(has_next)
        self.btn_last.setEnabled(has_next)
        self.btn_go.setEnabled(self.total_rows > 0)

    def apply_filters(self):
        self.current_page = 1
        self.load_data()

    def clear_filters(self):
        if self._has_active_filters():
            reply = themed_yes_no_question(
                self,
                self.tr("Clear current filters?"),
                self.tr("This will reset search, filters, sorting, and page position. It will not delete database records or human review notes."),
                confirm_role=BUTTON_ROLE_DESTRUCTIVE,
                default_button=QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        self.search_edit.clear()
        self.status_combo.setCurrentIndex(0)
        self.human_filter_combo.setCurrentIndex(0)
        self.vlm_filter_combo.setCurrentIndex(0)
        self.sort_combo.setCurrentIndex(0)
        self.current_page = 1
        self.load_data()

    def on_header_clicked(self, section):
        if self._active_table == "figure_records":
            mapping = {0: "newest", 3: "score_desc", 5: "oldest", 6: "species", 7: "pdf_name"}
        else:
            mapping = {0: "newest", 3: "score_desc", 5: "pdf_name"}
        sort_value = mapping.get(int(section))
        if not sort_value:
            return
        index = self.sort_combo.findData(sort_value)
        if index >= 0:
            self.sort_combo.setCurrentIndex(index)
            self.apply_filters()

    def _row_to_record(self, row):
        values = list(row)
        if self._active_table == "figure_records":
            return {
                "source_table": "figure_records",
                "id": values[0],
                "image_file_name": values[1] or "",
                "image_file_path": values[2] or "",
                "score": values[3],
                "accepted": values[4],
                "page_number": values[5],
                "species": values[6] or "",
                "review_status": values[7] or "",
                "multimodal_review_mode": values[8] or "",
                "multimodal_validated": values[9],
                "pdf_file_name": values[10] or "",
                "pdf_file_path": values[11] or "",
                "human_status": values[12] or "unreviewed",
                "review_note": values[13] or "",
            }
        return {
            "source_table": "images",
            "id": values[0],
            "image_file_name": values[1] or "",
            "image_file_path": values[2] or "",
            "score": values[3],
            "accepted": values[4],
            "page_number": "",
            "species": "",
            "review_status": "legacy",
            "multimodal_review_mode": "",
            "multimodal_validated": 0,
            "pdf_file_name": values[5] or "",
            "pdf_file_path": values[6] or "",
            "human_status": values[7] or "unreviewed",
            "review_note": values[8] or "",
        }

    def _record_display_values(self, record):
        if self._active_table == "figure_records":
            return [
                record["id"],
                record["image_file_name"],
                record["image_file_path"],
                record["score"],
                record["accepted"],
                record["page_number"],
                record["species"],
                record["pdf_file_name"],
                record["human_status"],
                record["review_note"],
            ]
        return [
            record["id"],
            record["image_file_name"],
            record["image_file_path"],
            record["score"],
            record["accepted"],
            record["pdf_file_name"],
            record["human_status"],
            record["review_note"],
        ]

    def _gallery_label(self, record):
        score = record.get("score")
        try:
            score_text = f"{float(score):.3f}"
        except (TypeError, ValueError):
            score_text = str(score or "")
        bits = [
            f"#{record.get('id')}",
            record.get("image_file_name") or "",
            record.get("species") or record.get("pdf_file_name") or "",
            f"score={score_text}",
            f"human={record.get('human_status') or 'unreviewed'}",
        ]
        return " | ".join(str(bit) for bit in bits if str(bit).strip())

    def _set_selected_record(self, record):
        self._selected_record = dict(record) if record else None
        self.review_note_edit.blockSignals(True)
        self.human_status_group.blockSignals(True)
        if record:
            status = record.get("human_status") or "unreviewed"
            self._set_human_status_choice(status)
            self.review_note_edit.setText(record.get("review_note") or "")
        else:
            self._set_human_status_choice("unreviewed")
            self.review_note_edit.clear()
        self.human_status_group.blockSignals(False)
        self.review_note_edit.blockSignals(False)

    def _update_current_row_review_state(self, status, note):
        if not self._selected_record:
            return
        source_table = self._selected_record.get("source_table") or self._active_table
        record_id = int(self._selected_record.get("id"))
        self._selected_record["human_status"] = status
        self._selected_record["review_note"] = note

        for index, record in enumerate(self._current_rows):
            if (record.get("source_table") or self._active_table) == source_table and int(record.get("id")) == record_id:
                record["human_status"] = status
                record["review_note"] = note
                display_values = self._record_display_values(record)
                for column, value in enumerate(display_values):
                    item = self.table.item(index, column)
                    if item is None:
                        item = QTableWidgetItem()
                        self.table.setItem(index, column, item)
                    item.setText(str(value))
                    item.setData(Qt.UserRole, record)
                break

        for index in range(self.gallery.count()):
            item = self.gallery.item(index)
            record = item.data(Qt.UserRole)
            if not isinstance(record, dict):
                continue
            if (record.get("source_table") or self._active_table) == source_table and int(record.get("id")) == record_id:
                record["human_status"] = status
                record["review_note"] = note
                item.setData(Qt.UserRole, record)
                item.setText(self._gallery_label(record))
                break

    def _on_review_save_done(self, source_table, record_id, status, note):
        worker = self.sender()
        if worker in self._review_save_workers:
            self._review_save_workers.remove(worker)
        if worker is not None:
            worker.deleteLater()

    def _on_review_save_failed(self, detail):
        worker = self.sender()
        if worker in self._review_save_workers:
            self._review_save_workers.remove(worker)
        if worker is not None:
            worker.deleteLater()
        QMessageBox.warning(self, self.tr("Error"), self.tr("DB Error: {0}").format(detail))

    def _wait_for_pending_review_saves(self):
        for worker in list(self._review_save_workers):
            if worker.isRunning():
                worker.wait(1500)

    def closeEvent(self, event):
        self._wait_for_pending_review_saves()
        super().closeEvent(event)

    def accept(self):
        self._wait_for_pending_review_saves()
        super().accept()

    def reject(self):
        self._wait_for_pending_review_saves()
        super().reject()

    def load_data(self):
        if not os.path.exists(self.db_path):
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            self._ensure_human_review_table(cursor)
            self._refresh_schema(cursor)

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='figure_records'")
            has_v2_table = cursor.fetchone() is not None

            if has_v2_table:
                self._active_table = "figure_records"
                count_query, count_params = self._build_v2_query_parts(count_only=True)
                cursor.execute(count_query, count_params)
                self.total_rows = int(cursor.fetchone()[0] or 0)
                self.total_pages = max(1, (self.total_rows + self.page_size - 1) // self.page_size)
                self.current_page = max(1, min(self.current_page, self.total_pages))
                offset = (self.current_page - 1) * self.page_size
                query, params = self._build_v2_query_parts(count_only=False)
                cursor.execute(query, params + [self.page_size, offset])
                rows = cursor.fetchall()
                self.table.setColumnCount(10)
                self.table.setHorizontalHeaderLabels([
                    self.tr("ID"),
                    self.tr("Filename"),
                    self.tr("Path"),
                    self.tr("Score"),
                    self.tr("Accepted"),
                    self.tr("Page"),
                    self.tr("Species"),
                    "PDF",
                    self.tr("Human"),
                    self.tr("Review Note:"),
                ])
            else:
                self._active_table = "images"
                count_query, count_params = self._build_legacy_query_parts(count_only=True)
                cursor.execute(count_query, count_params)
                self.total_rows = int(cursor.fetchone()[0] or 0)
                self.total_pages = max(1, (self.total_rows + self.page_size - 1) // self.page_size)
                self.current_page = max(1, min(self.current_page, self.total_pages))
                offset = (self.current_page - 1) * self.page_size
                query, params = self._build_legacy_query_parts(count_only=False)
                cursor.execute(query, params + [self.page_size, offset])
                rows = cursor.fetchall()
                self.table.setColumnCount(8)
                self.table.setHorizontalHeaderLabels([
                    self.tr("ID"),
                    self.tr("Filename"),
                    self.tr("Path"),
                    self.tr("Score"),
                    self.tr("Taxonomic"),
                    "PDF",
                    self.tr("Human"),
                    self.tr("Review Note:"),
                ])
            self.table.setRowCount(len(rows))
            self.gallery.clear()
            self._current_rows = []
            
            for i, row in enumerate(rows):
                record = self._row_to_record(row)
                self._current_rows.append(record)
                display_values = self._record_display_values(record)
                for j, val in enumerate(display_values):
                    item = QTableWidgetItem(str(val))
                    item.setData(Qt.UserRole, record)
                    self.table.setItem(i, j, item)
                gallery_item = QListWidgetItem(self._gallery_label(record))
                gallery_item.setData(Qt.UserRole, record)
                thumb_path = str(record.get("image_file_path") or "")
                if os.path.exists(thumb_path):
                    thumb = QPixmap(thumb_path)
                    if not thumb.isNull():
                        gallery_item.setIcon(QIcon(thumb.scaled(160, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                self.gallery.addItem(gallery_item)
            self._apply_table_default_widths()
            self._update_pager_state()
            self._set_selected_record(None)
            
            conn.close()
        except Exception as e:
            QMessageBox.warning(self, self.tr("Error"), self.tr("DB Error: {0}").format(e))

    def on_row_selected(self):
        items = self.table.selectedItems()
        if not items: return
        
        row = items[0].row()
        record = self.table.item(row, 0).data(Qt.UserRole)
        self._load_record_details(record)

    def on_gallery_selected(self):
        items = self.gallery.selectedItems()
        if not items:
            return
        self._load_record_details(items[0].data(Qt.UserRole))

    def _load_record_details(self, record):
        if not record:
            return
        self._set_selected_record(record)
        image_id = str(record.get("id"))
        img_path = str(record.get("image_file_path") or "")

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
                display_text = self.tr("File: {0}\n").format(img_path)
                page_number = record.get("page_number", "")
                species_candidate = record.get("species", "")
                review_status = record.get("review_status", "")
                review_mode = record.get("multimodal_review_mode", "")
                multimodal_validated = record.get("multimodal_validated", 0)
                category = ""
                rejection_reason = ""
                caption_text = ""
                model_used = ""
                if self._has_col("figure_records", "category") or self._has_col("figure_records", "caption_text"):
                    cursor.execute(
                        f"""
                        SELECT
                            {self._sql_col('figure_records', 'f', 'category', "''")},
                            {self._sql_col('figure_records', 'f', 'rejection_reason', "''")},
                            {self._sql_col('figure_records', 'f', 'caption_text', "''")},
                            {self._sql_col('figure_records', 'f', 'multimodal_model_used', "''")}
                        FROM figure_records f
                        WHERE f.id = ?
                        """,
                        (image_id,),
                    )
                    extra_row = cursor.fetchone()
                    if extra_row:
                        category, rejection_reason, caption_text, model_used = extra_row
                multimodal_text = 'real' if multimodal_validated else review_mode or 'none'
                display_text += self.tr("Page: {0}\nSpecies: {1}\nCategory: {2}\nStatus: {3}\nMultimodal: {4}\n").format(
                    page_number,
                    species_candidate or 'Unknown',
                    category,
                    review_status,
                    multimodal_text,
                )
                display_text += f"{self.tr('Human:')} {record.get('human_status') or 'unreviewed'}\n"
                if record.get("review_note"):
                    display_text += f"{self.tr('Review Note:')} {record.get('review_note')}\n"
                if model_used:
                    display_text += self.tr("Model: {0}\n").format(model_used)
                if rejection_reason:
                    display_text += self.tr("Reject Reason: {0}\n").format(rejection_reason)
                if caption_text:
                    display_text += self.tr("\n--- Caption ---\n{0}\n").format(caption_text)
                rows = []
                if self._has_table("figure_evidence"):
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
                if rows:
                    display_text += self.tr("\n--- Evidence ---\n")
                    for level, evidence_type, content, score, section_title in rows:
                        title_part = f" | {section_title}" if section_title else ""
                        display_text += f"[{level} | {evidence_type}{title_part} | score={score:.3f}]\n{content}\n\n"
                else:
                    display_text += self.tr("\n(No related evidence found in DB)")
                required_part_cols = {
                    "pdf_file_id", "taxon_name", "caste_or_stage", "part_label", "description_text",
                    "source_pages", "source_block_refs", "confidence", "review_status",
                    "file_name", "file_path", "file_hash",
                }
                if (
                    self._has_table("taxon_part_descriptions")
                    and self._has_col("figure_records", "pdf_file_id")
                    and required_part_cols.issubset(self._table_columns.get("taxon_part_descriptions", set()))
                ):
                    cursor.execute(
                        """
                        SELECT taxon_name, caste_or_stage, part_label, description_text,
                               source_pages, source_block_refs, confidence, review_status,
                               file_name, file_path, file_hash
                        FROM taxon_part_descriptions
                        WHERE pdf_file_id = (
                            SELECT pdf_file_id FROM figure_records WHERE id = ?
                        )
                          AND (
                            taxon_name = ?
                            OR ? = ''
                            OR taxon_name = ''
                        )
                        ORDER BY taxon_name ASC, part_key ASC, id ASC
                        LIMIT 80
                        """,
                        (image_id, species_candidate or "", species_candidate or ""),
                    )
                    part_rows = cursor.fetchall()
                    if part_rows:
                        display_text += self.tr("\n--- Taxon Part Descriptions ---\n")
                        for taxon_name, caste, part_label, description, source_pages, source_refs, confidence, status, part_file_name, part_file_path, part_file_hash in part_rows:
                            display_text += (
                                f"[{taxon_name or 'Unknown'} | {caste or 'unknown'} | {part_label} | "
                                f"file={part_file_name or ''} | hash={part_file_hash or ''} | "
                                f"conf={float(confidence or 0.0):.3f} | {status} | pages={source_pages} | refs={source_refs}]\n"
                                f"{part_file_path or ''}\n"
                                f"{description}\n\n"
                            )
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

    def _selected_path(self):
        if not self._selected_record:
            return ""
        return str(self._selected_record.get("image_file_path") or "")

    def _open_existing_path(self, path):
        if not path:
            QMessageBox.information(self, self.tr("Database Viewer"), self.tr("No image path selected."))
            return
        if not os.path.exists(path):
            QMessageBox.warning(self, self.tr("Error"), self.tr("Path does not exist: {0}").format(path))
            return
        open_path(path)

    def open_selected_image(self):
        self._open_existing_path(self._selected_path())

    def open_selected_folder(self):
        path = self._selected_path()
        folder = os.path.dirname(path) if path else ""
        self._open_existing_path(folder)

    def open_selected_pdf(self):
        if not self._selected_record:
            QMessageBox.information(self, self.tr("Database Viewer"), self.tr("No source PDF found for this row."))
            return
        pdf_path = str(self._selected_record.get("pdf_file_path") or "")
        if not pdf_path:
            QMessageBox.information(self, self.tr("Database Viewer"), self.tr("No source PDF found for this row."))
            return
        self._open_existing_path(pdf_path)

    def save_current_review(self):
        if not self._selected_record:
            return
        status = self._selected_human_status()
        note = self.review_note_edit.text().strip()
        source_table = self._selected_record.get("source_table") or self._active_table
        record_id = int(self._selected_record.get("id"))
        self._update_current_row_review_state(status, note)
        worker = HumanReviewSaveWorker(self.db_path, source_table, record_id, status, note, self)
        worker.saved.connect(self._on_review_save_done)
        worker.failed.connect(self._on_review_save_failed)
        self._review_save_workers.append(worker)
        worker.start()

    def mark_filtered_import_ready(self):
        records = self._all_filtered_records()
        if not records:
            QMessageBox.information(self, self.tr("Database Viewer"), self.tr("No rows match the current filters."))
            return
        protected_statuses = {"human_rejected", "needs_crop"}
        passable_records = [
            record
            for record in records
            if str(record.get("human_status") or "unreviewed") not in protected_statuses
        ]
        if not passable_records:
            QMessageBox.information(self, self.tr("Database Viewer"), self.tr("No passable rows match the current filters."))
            return
        reply = themed_yes_no_question(
            self,
            self.tr("Mark Filtered Import Ready"),
            self.tr("Mark {0} passable rows as import_ready? {1} rows already marked rejected/needs_crop will be kept.").format(
                len(passable_records),
                len(records) - len(passable_records),
            ),
            confirm_role=BUTTON_ROLE_COMMIT,
            default_button=QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            self._ensure_human_review_table(cursor)
            cursor.executemany(
                """
                INSERT INTO figure_human_reviews (source_table, record_id, human_status, review_note, updated_at)
                VALUES (?, ?, 'import_ready', '', ?)
                ON CONFLICT(source_table, record_id) DO UPDATE SET
                    human_status = excluded.human_status,
                    review_note = figure_human_reviews.review_note,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        record.get("source_table") or self._active_table,
                        int(record.get("id")),
                        now,
                    )
                    for record in passable_records
                ],
            )
            conn.commit()
            conn.close()
            QMessageBox.information(
                self,
                self.tr("Database Viewer"),
                self.tr("Marked {0} filtered rows as import_ready.").format(len(passable_records)),
            )
            self.load_data()
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Error"), self.tr("DB Error: {0}").format(exc))

    def _all_filtered_records(self):
        if not os.path.exists(self.db_path):
            return []
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            self._ensure_human_review_table(cursor)
            self._refresh_schema(cursor)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='figure_records'")
            has_v2_table = cursor.fetchone() is not None
            self._active_table = "figure_records" if has_v2_table else "images"
            if has_v2_table:
                query, params = self._build_v2_query_parts(count_only=False, include_limit=False)
            else:
                query, params = self._build_legacy_query_parts(count_only=False, include_limit=False)
            cursor.execute(query, params)
            return [self._row_to_record(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def export_filtered_csv(self):
        records = self._all_filtered_records()
        if not records:
            QMessageBox.information(self, self.tr("Database Viewer"), self.tr("No rows match the current filters."))
            return
        start_dir = os.path.dirname(os.path.abspath(self.db_path))
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Filtered CSV"),
            os.path.join(start_dir, "pdf_database_filtered_review.csv"),
            "CSV (*.csv);;All Files (*)",
        )
        if not out_path:
            return
        fields = [
            "source_table", "id", "image_file_name", "image_file_path", "score", "accepted",
            "page_number", "species", "review_status", "multimodal_review_mode",
            "pdf_file_name", "pdf_file_path", "human_status", "review_note",
        ]
        with open(out_path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for record in records:
                writer.writerow({field: record.get(field, "") for field in fields})
        QMessageBox.information(
            self,
            self.tr("Database Viewer"),
            self.tr("Export finished: {0} rows -> {1}").format(len(records), out_path),
        )

    def copy_filtered_images(self):
        records = self._all_filtered_records()
        if not records:
            QMessageBox.information(self, self.tr("Database Viewer"), self.tr("No rows match the current filters."))
            return
        start_dir = os.path.dirname(os.path.abspath(self.db_path))
        target_dir = QFileDialog.getExistingDirectory(self, self.tr("Copy Filtered Images"), start_dir)
        if not target_dir:
            return
        copied = 0
        used_names = set()
        for record in records:
            src = str(record.get("image_file_path") or "")
            if not src or not os.path.exists(src):
                continue
            base = os.path.basename(src)
            stem, ext = os.path.splitext(base)
            target_name = base
            suffix = 1
            while target_name.lower() in used_names or os.path.exists(os.path.join(target_dir, target_name)):
                target_name = f"{stem}_{suffix:03d}{ext}"
                suffix += 1
            shutil.copy2(src, os.path.join(target_dir, target_name))
            used_names.add(target_name.lower())
            copied += 1
        QMessageBox.information(
            self,
            self.tr("Database Viewer"),
            self.tr("Copied {0} images -> {1}").format(copied, target_dir),
        )

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


class PartDescriptionProfileDialog(QDialog):
    def __init__(self, current_profile, profile_name="New_Part_Description_Profile", is_default=False, parent=None, lang="en"):
        super().__init__(parent)
        self.profile = deepcopy(current_profile)
        self.profile_name = profile_name
        self.is_default = is_default
        self.lang = lang
        self.current_theme = _resolve_active_theme(parent)
        self.save_action = None
        self.setWindowTitle(self.tr("Advanced Part Description Settings"))
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

        note = QLabel(self.tr("Edit the pure-text part-description extraction profile JSON. API keys are not stored here."))
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
            payload = normalize_part_description_profile(payload)
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Error"), self.tr("Invalid part description profile JSON: {0}").format(exc))
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
        part_description_profile_name = self.kwargs.get('part_description_profile_name', 'Unknown')
        self.log_signal.emit(self.tr("Initializing Extractor..."))
        self.log_signal.emit(self.tr("  > Figure Profile: {0}").format(figure_profile_name))
        self.log_signal.emit(self.tr("  > Part Description Profile: {0}").format(part_description_profile_name))
        extractor = EnhancedPDFExtractionSystem(
            output_db_path=self.kwargs['db_path'],
            save_images_to_files=True, 
            enable_multimodal_validation=self.kwargs.get('use_mllm', False),
            multimodal_config=self.kwargs.get('mllm_config'),
            text_part_config=self.kwargs.get('text_part_config'),
            figure_profile=self.kwargs.get('figure_profile'),
            figure_profile_path=self.kwargs.get('figure_profile_path'),
            part_description_profile=self.kwargs.get('part_description_profile'),
            part_description_profile_path=self.kwargs.get('part_description_profile_path'),
            resume_completed_pdfs=self.kwargs.get('resume_completed_pdfs', True),
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
                if stats.get("resumed_skip"):
                    self.log_signal.emit(self.tr("  > Existing completed PDF result found; skipped re-extraction."))
                self.log_signal.emit(
                    self.tr("  > Figures: {0}, Accepted: {1}, Review: {2}").format(
                        stats.get('total_figures', stats.get('total_images', 0)),
                        stats.get('accepted_figures', stats.get('taxonomic_images', 0)),
                        stats.get('review_queue_figures', 0),
                    )
                )
                part_status = str(stats.get('part_extraction_status', '') or '')
                if part_status:
                    self.log_signal.emit(
                        self.tr("  > Part descriptions: {0}, Text blocks: {1}, Status: {2}, Profile: {3}").format(
                            stats.get('part_description_records', 0),
                            stats.get('part_text_blocks', 0),
                            part_status,
                            stats.get('part_description_profile_name', part_description_profile_name),
                        )
                    )
                accepted_dir = str(stats.get("accepted_figures_dir", "") or "")
                accepted_exported = int(stats.get("accepted_exported_figures", 0) or 0)
                review_exported = int(stats.get("review_exported_figures", 0) or 0)
                if accepted_dir:
                    self.log_signal.emit(
                        self.tr("  > Import-ready accepted figures: {0} -> {1}").format(
                            accepted_exported,
                            accepted_dir,
                        )
                    )
                if review_exported:
                    self.log_signal.emit(
                        self.tr("  > Needs-review figure copies: {0} -> {1}").format(
                            review_exported,
                            stats.get("needs_review_figures_dir", ""),
                        )
                    )
                self._log_extract_pdf_warnings(stats)
            except Exception as e:
                self.log_signal.emit(self.tr("  > Failed: {0}").format(e))
        
        extractor.close()
        self.log_signal.emit(self.tr("Extraction Pipeline Completed."))

    def stop(self):
        self._is_running = False


class LLMConnectionTestWorker(QThread):
    result_signal = Signal(str, bool, str)

    TEST_TIMEOUT_SECONDS = 180
    TEST_MAX_OUTPUT_TOKENS = 1024
    TEST_IMAGE_WIDTH = 128
    TEST_IMAGE_HEIGHT = 96

    def __init__(self, role, config, parent=None):
        super().__init__(parent)
        self.role = str(role or "text")
        self.config = dict(config or {})
        self.test_image_data_url = self._build_test_image_data_url()

    def run(self):
        try:
            protocol = self._call_with_protocol_fallback()
            self.result_signal.emit(self.role, True, f"protocol={protocol}, model={self.config.get('model', '')}")
        except Exception as exc:
            self.result_signal.emit(self.role, False, str(exc))

    def _call_with_protocol_fallback(self):
        preferred = self._resolve_api_protocol()
        protocols = [preferred]
        if str(self.config.get("api_protocol", "auto") or "auto").strip().lower() == "auto":
            fallback = "responses" if preferred == "chat_completions" else "chat_completions"
            protocols.append(fallback)

        last_exc = None
        for index, protocol in enumerate(protocols):
            try:
                if protocol == "responses":
                    self._call_responses()
                else:
                    self._call_chat_completions()
                return protocol
            except Exception as exc:
                last_exc = exc
                detail = str(exc).lower()
                can_fallback = index < len(protocols) - 1 and any(
                    token in detail
                    for token in [
                        "404",
                        "400",
                        "422",
                        "unsupported",
                        "not found",
                        "responses",
                        "chat/completions",
                        "empty_chat_completions_test_output",
                        "empty_responses_test_output",
                        "truncated_before_final_answer",
                    ]
                )
                if can_fallback:
                    continue
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("llm_connection_test_failed")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.config.get('api_key', '')}",
            "Content-Type": "application/json",
        }

    def _base_url(self):
        base_text = str(self.config.get("base_url", "") or "").strip()
        for suffix in ["/chat/completions", "/responses"]:
            if base_text.lower().endswith(suffix):
                base_text = base_text[: -len(suffix)]
        return base_text.rstrip("/")

    def _resolve_api_protocol(self):
        protocol = str(self.config.get("api_protocol", "auto") or "auto").strip().lower()
        if protocol in {"chat_completions", "responses"}:
            return protocol
        model_text = str(self.config.get("model", "") or "").strip().lower()
        model_id = model_text.rsplit("/", 1)[-1]
        if model_id.startswith("gpt-5"):
            return "responses"
        return "chat_completions"

    def _text_prompt(self):
        return "Connection test. Reply exactly: OK"

    @classmethod
    def _build_test_image_data_url(cls):
        width = cls.TEST_IMAGE_WIDTH
        height = cls.TEST_IMAGE_HEIGHT
        rows = []
        for y in range(height):
            row = bytearray()
            for x in range(width):
                red, green, blue = 246, 246, 240
                if 12 <= x <= width - 13 and 12 <= y <= height - 13:
                    red, green, blue = 236, 239, 232
                if 22 <= x <= 72 and 24 <= y <= 72:
                    red, green, blue = 218, 64, 48
                if (x - 84) * (x - 84) + (y - 46) * (y - 46) <= 20 * 20:
                    red, green, blue = 42, 112, 204
                if 0 <= x - y // 2 <= 7 and 18 <= y <= 82:
                    red, green, blue = 36, 36, 36
                if x in {10, width - 11} or y in {10, height - 11}:
                    red, green, blue = 26, 31, 35
                row.extend((red, green, blue))
            rows.append(b"\x00" + bytes(row))
        raw = b"".join(rows)

        def chunk(tag, data):
            return (
                struct.pack(">I", len(data))
                + tag
                + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            )

        png = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b"")
        )
        return "data:image/png;base64," + base64.b64encode(png).decode("ascii")

    def _vision_content_chat(self):
        return [
            {"type": "text", "text": "Connection test image. If you can read this image input, reply exactly: OK"},
            {
                "type": "image_url",
                "image_url": {
                    "url": self.test_image_data_url,
                    "detail": str(self.config.get("image_detail", "auto") or "auto"),
                },
            },
        ]

    def _vision_content_responses(self):
        return [
            {"type": "input_text", "text": "Connection test image. If you can read this image input, reply exactly: OK"},
            {"type": "input_image", "image_url": self.test_image_data_url},
        ]

    def _call_chat_completions(self):
        if self.role == "multimodal":
            user_content = self._vision_content_chat()
        else:
            user_content = self._text_prompt()
        payload = {
            "model": self.config.get("model", ""),
            "messages": [
                {"role": "system", "content": "You are a connection test. Reply with the exact text OK and nothing else."},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": self.TEST_MAX_OUTPUT_TOKENS,
            "temperature": 0.0,
        }
        response = requests.post(
            f"{self._base_url()}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=self.TEST_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code} - chat_completions_error - {response.text[:300]}")
        body = response.json()
        text, finish_reason = self._extract_chat_completions_text(body)
        if not text:
            if finish_reason == "length":
                raise ValueError(
                    "chat_completions_test_output_truncated_before_final_answer "
                    f"(max_tokens={self.TEST_MAX_OUTPUT_TOKENS}, response={self._json_preview(body)})"
                )
            raise ValueError(
                f"empty_chat_completions_test_output "
                f"(finish_reason={finish_reason or 'unknown'}, response={self._json_preview(body)})"
            )
        return text

    def _call_responses(self):
        if self.role == "multimodal":
            user_content = self._vision_content_responses()
        else:
            user_content = [{"type": "input_text", "text": self._text_prompt()}]
        payload = {
            "model": self.config.get("model", ""),
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": "You are a connection test. Reply with the exact text OK and nothing else."}]},
                {"role": "user", "content": user_content},
            ],
            "max_output_tokens": self.TEST_MAX_OUTPUT_TOKENS,
            "temperature": 0.0,
        }
        response = requests.post(
            f"{self._base_url()}/responses",
            headers=self._headers(),
            json=payload,
            timeout=self.TEST_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code} - responses_error - {response.text[:300]}")
        body = response.json()
        text = self._extract_responses_text(body)
        if not text:
            raise ValueError(f"empty_responses_test_output (response={self._json_preview(body)})")
        return text

    def _extract_chat_completions_text(self, payload):
        if not isinstance(payload, dict):
            return "", ""
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return "", ""
        choice = choices[0] if isinstance(choices[0], dict) else {}
        finish_reason = str(choice.get("finish_reason", "") or "").strip()
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content = message.get("content", "")
        if isinstance(content, str):
            text = content.strip()
            if text:
                return text, finish_reason
        chunks = []
        if isinstance(content, list):
            for item in content:
                if isinstance(item, str):
                    chunks.append(item)
                elif isinstance(item, dict):
                    text = str(item.get("text", "") or "")
                    if text:
                        chunks.append(text)
        text = "\n".join(chunks).strip()
        if text:
            return text, finish_reason
        reasoning_content = str(message.get("reasoning_content", "") or "").strip()
        if reasoning_content:
            return reasoning_content, finish_reason
        return "", finish_reason

    def _json_preview(self, payload):
        try:
            return json.dumps(payload, ensure_ascii=False)[:300]
        except Exception:
            return str(payload)[:300]

    def _extract_responses_text(self, payload):
        if isinstance(payload, dict):
            output_text = str(payload.get("output_text", "") or "").strip()
            if output_text:
                return output_text
            output_items = payload.get("output")
        else:
            return ""
        chunks = []
        if isinstance(output_items, list):
            for item in output_items:
                content_items = item.get("content") if isinstance(item, dict) else None
                if not isinstance(content_items, list):
                    continue
                for content_item in content_items:
                    if not isinstance(content_item, dict):
                        continue
                    text = str(content_item.get("text", "") or "")
                    if text:
                        chunks.append(text)
        return "\n".join(chunks).strip()


class PdfProcessingWidget(QWidget):
    DEFAULT_EXTRACT_DB_NAME = "taxamask_literature.db"

    start_center_requested = Signal()
    agent_requested = Signal(dict)

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
        self.part_description_configs_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'part_description_configs')
        if not os.path.exists(self.part_description_configs_dir):
            os.makedirs(self.part_description_configs_dir)
             
        self.screener_config = LLMScreenPDFClassifier.DEFAULT_CONFIG.copy()
        self.current_profile_name = "Default_Ant_Logic"
        self.figure_profile = normalize_figure_profile(None)
        self.current_figure_profile_name = profile_display_name(self.figure_profile)
        self.current_figure_profile_path = ""
        self.part_description_profile = normalize_part_description_profile(None)
        self.current_part_description_profile_name = part_description_profile_display_name(self.part_description_profile)
        self.current_part_description_profile_path = ""
        self.advanced_config_visible = False
        self.worker = None
        self.llm_test_worker = None
        
        self.init_ui()
        self.load_api_settings()
        self.refresh_profile_list()
        self.refresh_figure_profile_list()
        self.refresh_part_description_profile_list()
        self.sync_runtime_controls_from_config()
        self.retranslate_ui()
        self.refresh_poppler_status()

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
        if self.check_mllm_same_as_text.isChecked():
            self._sync_mllm_controls_from_text()
        remember_key = self.chk_remember_api_key.isChecked()
        remember_mllm_key = self.chk_remember_mllm_api_key.isChecked()
        use_same_mllm = self.check_mllm_same_as_text.isChecked()
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
                "use_same_as_text": use_same_mllm,
                "base_url": "" if use_same_mllm else self.edit_mllm_base_url.text().strip(),
                "model": "" if use_same_mllm else self.edit_mllm_model.text().strip(),
                "api_protocol": "auto" if use_same_mllm else self.combo_mllm_api_protocol.currentData() or "auto",
                "image_detail": self.combo_mllm_image_detail.currentData() or "auto",
                "remember_api_key": False if use_same_mllm else remember_mllm_key,
                "api_key": "" if use_same_mllm or not remember_mllm_key else self.edit_mllm_api_key.text().strip(),
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

    def _current_text_api_settings(self):
        return {
            "api_key": self.edit_api_key.text().strip(),
            "base_url": self.edit_base_url.text().strip(),
            "model": self.edit_model.text().strip(),
            "api_protocol": self.combo_api_protocol.currentData() or "auto",
        }

    def _sync_mllm_controls_from_text_if_needed(self):
        if self.check_mllm_same_as_text.isChecked():
            self._sync_mllm_controls_from_text()

    def update_mllm_api_controls_enabled(self):
        use_same = self.check_mllm_same_as_text.isChecked()
        if use_same:
            self._sync_mllm_controls_from_text()
        for widget in [
            self.edit_mllm_api_key,
            self.edit_mllm_base_url,
            self.edit_mllm_model,
            self.combo_mllm_api_protocol,
            self.chk_remember_mllm_api_key,
        ]:
            widget.setEnabled(not use_same)
        self.combo_mllm_image_detail.setEnabled(True)
        self._refresh_llm_test_buttons()

    def _sync_mllm_controls_from_text(self):
        if not hasattr(self, "edit_mllm_base_url"):
            return
        self.edit_mllm_api_key.setText(self.edit_api_key.text())
        self.edit_mllm_base_url.setText(self.edit_base_url.text())
        self.edit_mllm_model.setText(self.edit_model.text())
        protocol = self.combo_api_protocol.currentData() or "auto"
        protocol_index = self.combo_mllm_api_protocol.findData(protocol)
        if protocol_index >= 0:
            self.combo_mllm_api_protocol.setCurrentIndex(protocol_index)
        self.chk_remember_mllm_api_key.setChecked(self.chk_remember_api_key.isChecked())

    def _current_multimodal_api_settings(self):
        if self.check_mllm_same_as_text.isChecked():
            self._sync_mllm_controls_from_text()
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

    def _api_test_config_error(self, config):
        if not config.get("api_key") or not config.get("base_url") or not config.get("model"):
            return self.tr("Please fill API key, Base URL, and model first.")
        return ""

    def _refresh_llm_test_buttons(self):
        llm_worker = getattr(self, "llm_test_worker", None)
        task_worker = getattr(self, "worker", None)
        test_running = bool(llm_worker and llm_worker.isRunning())
        task_running = bool(task_worker and task_worker.isRunning())
        enabled = not test_running and not task_running
        if hasattr(self, "btn_test_text_llm"):
            self.btn_test_text_llm.setEnabled(enabled)
        if hasattr(self, "btn_test_mllm"):
            self.btn_test_mllm.setEnabled(enabled)
        if hasattr(self, "btn_run_classify") and not task_running:
            self.btn_run_classify.setEnabled(not test_running)
        if hasattr(self, "btn_run_extract") and not task_running:
            self.btn_run_extract.setEnabled(not test_running)
        if hasattr(self, "btn_restore_interrupted_run") and not task_running:
            self.btn_restore_interrupted_run.setEnabled(not test_running)

    def test_text_llm_connection(self):
        config = self._current_text_api_settings()
        error = self._api_test_config_error(config)
        if error:
            QMessageBox.warning(self, self.tr("Connection Test"), error)
            return
        self._start_llm_connection_test("text", config)

    def test_multimodal_llm_connection(self):
        config = self._current_multimodal_api_settings()
        error = self._api_test_config_error(config)
        if error:
            QMessageBox.warning(self, self.tr("Connection Test"), error)
            return
        self._start_llm_connection_test("multimodal", config)

    def _start_llm_connection_test(self, role, config):
        if self.llm_test_worker and self.llm_test_worker.isRunning():
            QMessageBox.information(self, self.tr("Connection Test"), self.tr("Another LLM connection test is already running."))
            return
        if role == "multimodal":
            self.log(self.tr("Testing Multimodal LLM connection..."))
        else:
            self.log(self.tr("Testing Text LLM connection..."))
        self.llm_test_worker = LLMConnectionTestWorker(role, config, self)
        self.llm_test_worker.result_signal.connect(self._on_llm_connection_test_result)
        self.llm_test_worker.finished.connect(self._refresh_llm_test_buttons)
        self.btn_test_text_llm.setEnabled(False)
        self.btn_test_mllm.setEnabled(False)
        self.btn_run_classify.setEnabled(False)
        self.btn_run_extract.setEnabled(False)
        self.btn_restore_interrupted_run.setEnabled(False)
        self.llm_test_worker.start()

    def _on_llm_connection_test_result(self, role, ok, detail):
        if role == "multimodal":
            message = (
                self.tr("Multimodal LLM test passed: {0}").format(detail)
                if ok
                else self.tr("Multimodal LLM test failed: {0}").format(detail)
            )
        else:
            message = (
                self.tr("Text LLM test passed: {0}").format(detail)
                if ok
                else self.tr("Text LLM test failed: {0}").format(detail)
            )
        self.log(message)
        if ok:
            QMessageBox.information(self, self.tr("Connection Test"), message)
        else:
            QMessageBox.warning(self, self.tr("Connection Test"), message)

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
            lines_per_pdf = max(1, int(self.screener_config.get("lines_per_pdf", 50)))
        except (TypeError, ValueError):
            lines_per_pdf = 50
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
            llm_timeout = max(30, int(self.screener_config.get("llm_request_timeout_seconds", 180)))
        except (TypeError, ValueError):
            llm_timeout = 180
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
        default_label = self.tr("Built-in Ant Taxonomy Figure Profile")
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

    def refresh_part_description_profile_list(self):
        self.combo_part_description_profiles.blockSignals(True)
        self.combo_part_description_profiles.clear()
        default_label = self.tr("Built-in Ant Part Description Profile")
        self.combo_part_description_profiles.addItem(default_label, "DEFAULT_PART_DESCRIPTION")

        if os.path.exists(self.part_description_configs_dir):
            for filename in sorted(os.listdir(self.part_description_configs_dir)):
                if not filename.endswith(".json"):
                    continue
                path = os.path.join(self.part_description_configs_dir, filename)
                try:
                    profile = load_part_description_profile(path)
                    name = part_description_profile_display_name(profile) or filename[:-5]
                except Exception:
                    name = filename[:-5]
                self.combo_part_description_profiles.addItem(name, filename)

        index = self.combo_part_description_profiles.findText(self.current_part_description_profile_name)
        if index >= 0:
            self.combo_part_description_profiles.setCurrentIndex(index)
        else:
            self.combo_part_description_profiles.setCurrentIndex(0)
            self.part_description_profile = normalize_part_description_profile(None)
            self.current_part_description_profile_name = self.combo_part_description_profiles.currentText()
            self.current_part_description_profile_path = ""
        self.combo_part_description_profiles.blockSignals(False)

    def on_part_description_profile_changed(self, index):
        if index < 0:
            return
        name = self.combo_part_description_profiles.currentText()
        data = self.combo_part_description_profiles.currentData()
        if data == "DEFAULT_PART_DESCRIPTION":
            self.part_description_profile = normalize_part_description_profile(None)
            self.current_part_description_profile_name = name
            self.current_part_description_profile_path = ""
            return
        path = os.path.join(self.part_description_configs_dir, str(data))
        try:
            self.part_description_profile = load_part_description_profile(path)
            self.current_part_description_profile_name = part_description_profile_display_name(self.part_description_profile) or name
            self.current_part_description_profile_path = path
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to load part description profile: {0}").format(exc))
            self.combo_part_description_profiles.setCurrentIndex(0)

    def save_part_description_profile(self, name, profile):
        filename = f"{name}.json"
        path = os.path.join(self.part_description_configs_dir, filename)
        profile_to_save = normalize_part_description_profile(profile)
        profile_to_save["profile_name"] = name
        try:
            with open(path, 'w', encoding='utf-8') as handle:
                json.dump(profile_to_save, handle, ensure_ascii=False, indent=2)
            self.part_description_profile = profile_to_save
            self.current_part_description_profile_name = name
            self.current_part_description_profile_path = path
            self.refresh_part_description_profile_list()
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to save part description profile: {0}").format(exc))

    def delete_current_part_description_profile(self):
        if self.combo_part_description_profiles.currentData() == "DEFAULT_PART_DESCRIPTION":
            return
        name = self.combo_part_description_profiles.currentText()
        reply = themed_yes_no_question(
            self,
            self.tr("Confirm Delete"),
            self.tr("Are you sure you want to delete profile '{}'?").format(name),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply == QMessageBox.Yes:
            path = os.path.join(self.part_description_configs_dir, f"{name}.json")
            data = self.combo_part_description_profiles.currentData()
            if data:
                path = os.path.join(self.part_description_configs_dir, str(data))
            try:
                if os.path.exists(path):
                    os.remove(path)
                self.part_description_profile = normalize_part_description_profile(None)
                self.current_part_description_profile_name = ""
                self.current_part_description_profile_path = ""
                self.refresh_part_description_profile_list()
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

        self.workbench_header = QWidget()
        apply_surface_role(self.workbench_header, SURFACE_ROLE_SUBTLE, "pdfWorkbenchHeader")
        header_layout = QHBoxLayout(self.workbench_header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(10)
        header_text_layout = QVBoxLayout()
        header_text_layout.setContentsMargins(0, 0, 0, 0)
        header_text_layout.setSpacing(2)
        self.lbl_workbench_title = QLabel()
        self.lbl_workbench_title.setObjectName("pdfWorkbenchTitle")
        self.lbl_workbench_hint = QLabel()
        self.lbl_workbench_hint.setObjectName("pdfWorkbenchHint")
        self.lbl_workbench_hint.setWordWrap(True)
        header_text_layout.addWidget(self.lbl_workbench_title)
        header_text_layout.addWidget(self.lbl_workbench_hint)
        header_layout.addLayout(header_text_layout, 1)
        self.btn_start_center = QPushButton()
        self.btn_start_center.setObjectName("pdfStartCenterButton")
        self.btn_start_center.clicked.connect(self.start_center_requested.emit)
        self.btn_ask_agent = QPushButton()
        self.btn_ask_agent.setObjectName("pdfAskAgentButton")
        self.btn_ask_agent.clicked.connect(lambda: self.agent_requested.emit(self.get_agent_context()))
        self.btn_toggle_advanced = QPushButton()
        self.btn_toggle_advanced.setObjectName("pdfToggleAdvancedButton")
        self.btn_toggle_advanced.setCheckable(True)
        self.btn_toggle_advanced.setChecked(self.advanced_config_visible)
        self.btn_toggle_advanced.clicked.connect(self.toggle_advanced_config)
        apply_semantic_button_style(self.btn_start_center, BUTTON_ROLE_NEUTRAL)
        apply_semantic_button_style(self.btn_ask_agent, BUTTON_ROLE_COMMIT)
        apply_semantic_button_style(self.btn_toggle_advanced, BUTTON_ROLE_NEUTRAL)
        header_layout.addWidget(self.btn_start_center)
        header_layout.addWidget(self.btn_ask_agent)
        header_layout.addWidget(self.btn_toggle_advanced)
        outer_layout.addWidget(self.workbench_header, 0)

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
        self.config_group.setVisible(self.advanced_config_visible)
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
        self.edit_base_url.setPlaceholderText(self.tr("https://api.example.com/v1"))
        
        self.edit_model = QLineEdit("gpt-5.4")
        self.combo_api_protocol = NoWheelComboBox()
        self.combo_api_protocol.addItem(self.tr("Auto (Recommended)"), "auto")
        self.combo_api_protocol.addItem(self.tr("Chat Completions"), "chat_completions")
        self.combo_api_protocol.addItem(self.tr("Responses API"), "responses")
        self.edit_api_key.textChanged.connect(lambda _text: self._sync_mllm_controls_from_text_if_needed())
        self.edit_base_url.textChanged.connect(lambda _text: self._sync_mllm_controls_from_text_if_needed())
        self.edit_model.textChanged.connect(lambda _text: self._sync_mllm_controls_from_text_if_needed())
        self.combo_api_protocol.currentIndexChanged.connect(lambda _index: self._sync_mllm_controls_from_text_if_needed())
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
        self.btn_test_text_llm = QPushButton()
        self.btn_test_text_llm.clicked.connect(self.test_text_llm_connection)
        apply_semantic_button_style(self.btn_test_text_llm, BUTTON_ROLE_NEUTRAL, "padding: 5px;")
        api_grid.addWidget(self.btn_test_text_llm, 2, 3)
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
        self.edit_mllm_base_url.setPlaceholderText(self.tr("https://api.example.com/v1"))
        self.edit_mllm_model = QLineEdit("Qwen/Qwen3-VL-32B-Instruct")
        self.combo_mllm_api_protocol = NoWheelComboBox()
        self.combo_mllm_api_protocol.addItem(self.tr("Auto (Recommended)"), "auto")
        self.combo_mllm_api_protocol.addItem(self.tr("Chat Completions"), "chat_completions")
        self.combo_mllm_api_protocol.addItem(self.tr("Responses API"), "responses")
        self.combo_mllm_image_detail = NoWheelComboBox()
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
        self.btn_test_mllm = QPushButton()
        self.btn_test_mllm.clicked.connect(self.test_multimodal_llm_connection)
        apply_semantic_button_style(self.btn_test_mllm, BUTTON_ROLE_NEUTRAL, "padding: 5px;")
        mllm_grid.addWidget(self.btn_test_mllm, 3, 3)
        mllm_grid.setColumnStretch(1, 1)
        mllm_grid.setColumnStretch(3, 1)
        api_panel_layout.addWidget(self.mllm_group)

        api_action_layout = QHBoxLayout()
        self.chk_remember_api_key = QCheckBox()
        self.chk_remember_api_key.setChecked(False)
        self.chk_remember_api_key.toggled.connect(lambda _checked: self._sync_mllm_controls_from_text_if_needed())
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
        layout.addWidget(self.api_panel, 0)

        # Profile Selector & Advanced Logic Button
        self.profile_panel = QWidget()
        apply_surface_role(self.profile_panel, SURFACE_ROLE_SUBTLE, "pdfProfilePanel")
        profile_panel_layout = QVBoxLayout(self.profile_panel)
        profile_panel_layout.setContentsMargins(10, 10, 10, 10)
        profile_panel_layout.setSpacing(6)

        adv_layout = QHBoxLayout()
        
        self.lbl_select_profile = QLabel()
        adv_layout.addWidget(self.lbl_select_profile)
        
        self.combo_profiles = NoWheelComboBox()
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

        self.combo_figure_profiles = NoWheelComboBox()
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

        part_description_profile_layout = QHBoxLayout()
        self.lbl_select_part_description_profile = QLabel()
        part_description_profile_layout.addWidget(self.lbl_select_part_description_profile)

        self.combo_part_description_profiles = NoWheelComboBox()
        self.combo_part_description_profiles.setMinimumWidth(240)
        self.combo_part_description_profiles.currentIndexChanged.connect(self.on_part_description_profile_changed)
        part_description_profile_layout.addWidget(self.combo_part_description_profiles)

        self.btn_delete_part_description_profile = QPushButton()
        self.btn_delete_part_description_profile.clicked.connect(self.delete_current_part_description_profile)
        apply_semantic_button_style(self.btn_delete_part_description_profile, BUTTON_ROLE_DESTRUCTIVE)
        part_description_profile_layout.addWidget(self.btn_delete_part_description_profile)

        part_description_profile_layout.addStretch()

        self.btn_adv_part_description_config = QPushButton()
        self.btn_adv_part_description_config.clicked.connect(self.open_adv_part_description_config)
        apply_semantic_button_style(self.btn_adv_part_description_config, BUTTON_ROLE_NEUTRAL, "padding: 5px;")
        part_description_profile_layout.addWidget(self.btn_adv_part_description_config)

        profile_panel_layout.addLayout(part_description_profile_layout)
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
        self.combo_mode = NoWheelComboBox()
        self.combo_mode.addItem(self.tr("V2 (CSV Full LLM)"), "v2")
        self.combo_mode.setMinimumWidth(180)
        self.combo_mode.currentIndexChanged.connect(self.on_mode_changed)

        self.lbl_lines_per_pdf = QLabel()
        self.edit_lines_per_pdf = QLineEdit("50")
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
        self.edit_llm_timeout = QLineEdit("180")
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
        self.edit_db_path = QLineEdit("")
        self.btn_db = QPushButton()
        self.btn_db.clicked.connect(self.browse_result_folder)
        apply_semantic_button_style(self.btn_db, BUTTON_ROLE_NEUTRAL)
        self.lbl_ext_db = QLabel()
        h4.addWidget(self.lbl_ext_db)
        h4.addWidget(self.edit_db_path)
        h4.addWidget(self.btn_db)
        extract_input_layout.addLayout(h4)

        h4_db_name = QHBoxLayout()
        self.edit_db_name = QLineEdit(self.DEFAULT_EXTRACT_DB_NAME)
        self.lbl_ext_db_name = QLabel()
        h4_db_name.addWidget(self.lbl_ext_db_name)
        h4_db_name.addWidget(self.edit_db_name)
        extract_input_layout.addLayout(h4_db_name)
        
        self.check_mllm = QCheckBox()
        extract_input_layout.addWidget(self.check_mllm)

        self.lbl_poppler_status = QLabel()
        self.lbl_poppler_status.setObjectName("pdfPopplerStatus")
        self.lbl_poppler_status.setWordWrap(True)
        extract_input_layout.addWidget(self.lbl_poppler_status)
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
        outer_layout.addWidget(self.main_scroll, 1)

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
        self.edit_base_url.setPlaceholderText(self.tr("https://api.example.com/v1"))
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
        self.edit_mllm_base_url.setPlaceholderText(self.tr("https://api.example.com/v1"))
        self.edit_mllm_model.setPlaceholderText(self.tr("Vision Model Name"))
        self.chk_remember_api_key.setText(self.tr("Remember API Key"))
        self.chk_remember_mllm_api_key.setText(self.tr("Remember Multimodal API Key"))
        self.btn_test_text_llm.setText(self.tr("Test Text LLM"))
        self.btn_test_text_llm.setToolTip(
            self.tr("Send a tiny text-only request to verify the text model settings before screening PDFs.")
        )
        self.btn_test_mllm.setText(self.tr("Test Multimodal LLM"))
        self.btn_test_mllm.setToolTip(
            self.tr("Send a tiny generated PNG plus text to verify the vision model settings before extracting figures.")
        )
        self.btn_save_api_settings.setText(self.tr("Save API Settings"))
        self.lbl_workbench_title.setText(self.tr("PDF Evidence Tools"))
        self.lbl_workbench_hint.setText(
            self.tr("Agent first: configure keys/models, then adapt PDF screening and figure-review rules to the target taxon.")
        )
        self.btn_start_center.setText(self.tr("Start Center"))
        self.btn_ask_agent.setText(self.tr("Ask Agent"))
        self.btn_ask_agent.setToolTip(
            self.tr("Ask Agent to check key/model readiness, then adapt target taxon, screening profile, figure-review profile, provenance, and safe candidate review before running.")
        )
        self.btn_toggle_advanced.setText(
            self.tr("Hide Advanced Config") if self.advanced_config_visible else self.tr("Show Advanced Config")
        )
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
        self.lbl_select_part_description_profile.setText(self.tr("Part Description Profile:"))
        self.btn_delete_part_description_profile.setText(self.tr("Delete Profile"))
        self.btn_adv_part_description_config.setText(self.tr("Advanced Part Description Settings"))
        
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
        self.lbl_ext_db.setText(self.tr("Result Folder:"))
        self.edit_db_path.setPlaceholderText(self.tr("Choose a result folder for this extraction run. The database index and the '<database>_v2_artifacts' folder for images, review batches, and raw LLM responses will be saved there."))
        self.edit_db_path.setToolTip(self.tr("Choose a result folder for this extraction run. The database index and the '<database>_v2_artifacts' folder for images, review batches, and raw LLM responses will be saved there."))
        self.btn_db.setText(self.tr("Choose Result Folder"))
        self.btn_db.setToolTip(self.tr("Choose a result folder for this extraction run. The database index and the '<database>_v2_artifacts' folder for images, review batches, and raw LLM responses will be saved there."))
        self.lbl_ext_db_name.setText(self.tr("Database File:"))
        self.edit_db_name.setPlaceholderText(self.DEFAULT_EXTRACT_DB_NAME)
        self.edit_db_name.setToolTip(self.tr("Database filename for this extraction run. If you omit .db, it will be added automatically."))
        self.check_mllm.setText(self.tr("Enable Multimodal Validation (Uses API - Slower but more accurate)"))
        self.refresh_poppler_status()
        self.btn_run_extract.setText(self.tr("Start Extraction Pipeline"))
        self.btn_stop_extract.setText(self.tr("Stop Extraction"))
        
        self.util_group.setTitle(self.tr("3. Data Utilities"))
        self.btn_browse_db.setText(self.tr("Open Database File"))
        self.btn_browse_db.setToolTip(self.tr("Choose an existing .db file to browse."))
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

    def open_adv_part_description_config(self):
        is_default = self.combo_part_description_profiles.currentData() == "DEFAULT_PART_DESCRIPTION"
        dlg = PartDescriptionProfileDialog(
            self.part_description_profile,
            self.current_part_description_profile_name,
            is_default,
            self,
            self.current_lang,
        )
        if dlg.exec():
            new_profile, new_name, action = dlg.get_result()
            if action == "new":
                self.save_part_description_profile(new_name, new_profile)
            elif action == "overwrite":
                self.save_part_description_profile(self.current_part_description_profile_name, new_profile)
            QMessageBox.information(self, self.tr("Settings Saved"), self.tr("Part description profile updated."))

    def change_language(self, lang):
        self.current_lang = lang
        self.refresh_profile_list()
        self.refresh_figure_profile_list()
        self.refresh_part_description_profile_list()
        self.retranslate_ui()

    def toggle_advanced_config(self, checked=None):
        self.advanced_config_visible = bool(checked) if checked is not None else not self.advanced_config_visible
        if hasattr(self, "config_group"):
            self.config_group.setVisible(self.advanced_config_visible)
        if hasattr(self, "btn_toggle_advanced"):
            self.btn_toggle_advanced.setChecked(self.advanced_config_visible)
        self.retranslate_ui()

    def _safe_current_data(self, combo):
        if combo is None:
            return ""
        try:
            return combo.currentData() or ""
        except Exception:
            return ""

    def _safe_text(self, widget):
        if widget is None or not hasattr(widget, "text"):
            return ""
        try:
            return widget.text().strip()
        except Exception:
            return ""

    def get_agent_context(self):
        multimodal_settings = self._current_multimodal_api_settings()
        recent_log = ""
        if hasattr(self, "log_area"):
            recent_log = "\n".join(self.log_area.toPlainText().splitlines()[-6:])
        current_tab = ""
        if hasattr(self, "tabs"):
            index = self.tabs.currentIndex()
            if index >= 0:
                current_tab = self.tabs.tabText(index)
        return {
            "source_workbench": "pdf_evidence",
            "project_type": "pdf_evidence",
            "settings_question_focus": "stage_1_confirm_pdf_keys_models_with_short_requirement_questions_only",
            "active_label_role": current_tab,
            "screener_profile": self.current_profile_name,
            "figure_profile": self.current_figure_profile_name,
            "part_description_profile": self.current_part_description_profile_name,
            "screening_mode": self._safe_current_data(getattr(self, "combo_mode", None)),
            "text_llm_key_configured": "yes" if self._safe_text(getattr(self, "edit_api_key", None)) else "no",
            "text_llm_base_url_configured": "yes" if self._safe_text(getattr(self, "edit_base_url", None)) else "no",
            "text_llm_model": self._safe_text(getattr(self, "edit_model", None)),
            "text_llm_api_protocol": self._safe_current_data(getattr(self, "combo_api_protocol", None)),
            "multimodal_llm_uses_text_provider": "yes" if getattr(self, "check_mllm_same_as_text", None) is not None and self.check_mllm_same_as_text.isChecked() else "no",
            "multimodal_llm_key_configured": "yes" if multimodal_settings.get("api_key") else "no",
            "multimodal_llm_base_url_configured": "yes" if multimodal_settings.get("base_url") else "no",
            "multimodal_llm_model": multimodal_settings.get("model", ""),
            "multimodal_llm_api_protocol": multimodal_settings.get("api_protocol", "auto"),
            "pdf_source_dir": self._safe_text(getattr(self, "edit_src_folder", None)),
            "screening_output_dir": self._safe_text(getattr(self, "edit_out_folder", None)),
            "extract_input_dir": self._safe_text(getattr(self, "edit_ext_src", None)),
            "extract_result_folder": self._safe_text(getattr(self, "edit_db_path", None)),
            "extract_db_name": self._extract_db_name(),
            "extract_db_path": self._resolve_extract_db_path(self._safe_text(getattr(self, "edit_db_path", None))),
            "multimodal_enabled": "yes" if getattr(self, "check_mllm", None) is not None and self.check_mllm.isChecked() else "no",
            "recent_log_excerpt": recent_log,
        }

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
        self.lbl_workbench_title.setStyleSheet(f"color: {c['text_main']}; font-weight: 700; font-size: 12pt;")
        self.lbl_workbench_hint.setStyleSheet(f"color: {c['text_soft']};")
        apply_theme_button_style(self.btn_save_api_settings, BUTTON_ROLE_COMMIT, "padding: 5px;", theme)
        apply_theme_button_style(self.btn_test_text_llm, BUTTON_ROLE_NEUTRAL, "padding: 5px;", theme)
        apply_theme_button_style(self.btn_test_mllm, BUTTON_ROLE_NEUTRAL, "padding: 5px;", theme)
        apply_theme_button_style(self.btn_start_center, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_ask_agent, BUTTON_ROLE_COMMIT, "", theme)
        apply_theme_button_style(self.btn_toggle_advanced, BUTTON_ROLE_NEUTRAL, "", theme)
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

    def _default_outputs_root(self) -> str:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        return os.path.join(repo_root, "TaxaMask_outputs")

    def _default_extract_result_dir(self) -> str:
        for widget_name in ("edit_out_folder", "edit_ext_src"):
            widget = getattr(self, widget_name, None)
            path_text = self._safe_text(widget)
            if path_text:
                path_text = os.path.abspath(os.path.expanduser(path_text))
                if os.path.isdir(path_text) and not self._path_is_inside_program_package(path_text):
                    return path_text
                parent = os.path.dirname(path_text)
                if parent and os.path.isdir(parent) and not self._path_is_inside_program_package(parent):
                    return parent
        return os.path.join(self._default_outputs_root(), "pdf_extraction")

    def _path_is_inside_program_package(self, path_text: str) -> bool:
        try:
            package_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            return os.path.commonpath([package_dir, os.path.abspath(path_text)]) == package_dir
        except ValueError:
            return False

    def _extract_db_name(self) -> str:
        db_name = self._safe_text(getattr(self, "edit_db_name", None))
        if not db_name:
            db_name = self.DEFAULT_EXTRACT_DB_NAME
        db_name = os.path.basename(os.path.expanduser(db_name.strip()))
        if not db_name:
            db_name = self.DEFAULT_EXTRACT_DB_NAME
        if not db_name.lower().endswith(".db"):
            db_name = f"{db_name}.db"
        return db_name

    def _resolve_extract_db_path(self, value: str = "") -> str:
        raw_text = str(value or "").strip()
        if not raw_text:
            base_dir = self._default_extract_result_dir()
            return os.path.abspath(os.path.join(base_dir, self._extract_db_name()))
        expanded = os.path.abspath(os.path.expanduser(raw_text))
        if raw_text.lower().endswith(".db"):
            return expanded
        if os.path.isdir(expanded) or not os.path.splitext(expanded)[1]:
            return os.path.abspath(os.path.join(expanded, self._extract_db_name()))
        return expanded

    def _set_extract_db_path(self, db_path: str):
        resolved = os.path.abspath(os.path.expanduser(str(db_path or "").strip()))
        if not resolved:
            return
        folder = os.path.dirname(resolved)
        filename = os.path.basename(resolved)
        if folder:
            self.edit_db_path.setText(folder)
        if filename:
            self.edit_db_name.setText(filename)

    def browse_result_folder(self):
        current_db = self._resolve_extract_db_path(self.edit_db_path.text())
        if self._safe_text(self.edit_db_path).lower().endswith(".db"):
            self._set_extract_db_path(current_db)
        start_dir = os.path.dirname(current_db) or self._default_extract_result_dir()
        if not os.path.isdir(start_dir):
            start_dir = self._default_extract_result_dir()
        folder = QFileDialog.getExistingDirectory(self, self.tr("Select Result Folder"), start_dir)
        if folder:
            self.edit_db_path.setText(folder)

    def log(self, msg):
        self.log_area.append(msg)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def _current_poppler_status(self):
        if discover_poppler is None:
            return None
        try:
            return discover_poppler()
        except Exception:
            return None

    def refresh_poppler_status(self):
        status = self._current_poppler_status()
        if status is not None and getattr(status, "found", False):
            source = getattr(status, "source", "") or getattr(status, "bin_path", "") or "detected"
            text = self.tr("Poppler: found ({0}) - PDF OCR/image fallback is available.").format(source)
        elif status is not None:
            text = self.tr("Poppler: not found - PyMuPDF extraction can still run, but pdf2image/OCR fallback may be unavailable.")
        else:
            text = self.tr("Poppler: checking...")
        if hasattr(self, "lbl_poppler_status"):
            self.lbl_poppler_status.setText(text)
        return status

    def log_poppler_status(self):
        status = self.refresh_poppler_status()
        if status is not None and getattr(status, "message", ""):
            detail = status.message
        elif status is not None:
            detail = getattr(status, "source", "unknown")
        else:
            detail = self.tr("Poppler: checking...")
        self.log(self.tr("Poppler status: {0}").format(detail))

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
        if self.llm_test_worker and self.llm_test_worker.isRunning():
            QMessageBox.information(self, self.tr("Connection Test"), self.tr("Another LLM connection test is already running."))
            return
        src = self.edit_src_folder.text()
        out = self.edit_out_folder.text()
        if not src or not out:
             QMessageBox.warning(self, self.tr("Error"), self.tr("Please select source and output directories."))
             return
             
        self.toggle_buttons(True)
        self.progress_bar.setValue(0)
        self.log_poppler_status()

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
            lines_per_pdf = int(self.edit_lines_per_pdf.text() or "50")
        except ValueError:
            lines_per_pdf = 50
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
            llm_timeout = int(self.edit_llm_timeout.text() or "180")
        except ValueError:
            llm_timeout = 180

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
        if self.llm_test_worker and self.llm_test_worker.isRunning():
            QMessageBox.information(self, self.tr("Connection Test"), self.tr("Another LLM connection test is already running."))
            return
        src = self.edit_ext_src.text()
        db = self._resolve_extract_db_path(self.edit_db_path.text())
        if not src:
             QMessageBox.warning(self, self.tr("Error"), self.tr("Please select input folder."))
             return
        self._set_extract_db_path(db)
             
        # Config for MLLM
        mllm_config = {}
        mllm_api = self._current_multimodal_api_settings()
        if mllm_api.get("api_key"):
             batch_size = 2
             fallback_batch = 1
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
                  "review_batch_size": min(2, batch_size),
                  "review_batch_fallback_size": min(1, fallback_batch),
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

        text_part_config = {
            "enabled": True,
            "default_provider": "text_llm",
            "api_protocol": self.combo_api_protocol.currentData() or "auto",
            "timeout": 180,
            "max_output_tokens": 12000,
            "max_input_chars": 600000,
            "providers": {
                "text_llm": {
                    "api_key": self.edit_api_key.text().strip(),
                    "base_url": self.edit_base_url.text().strip(),
                    "model": self.edit_model.text().strip(),
                }
            },
        }

        self.toggle_buttons(True)
        self.progress_bar.setValue(0)
        self.log_poppler_status()
        
        self.worker = PDFWorker("extract", lang=self.current_lang, pdf_dir=src, db_path=db, 
                                use_mllm=use_mllm,
                                mllm_config=mllm_config,
                                text_part_config=text_part_config,
                                figure_profile=deepcopy(self.figure_profile),
                                figure_profile_path=self.current_figure_profile_path,
                                figure_profile_name=self.current_figure_profile_name,
                                part_description_profile=deepcopy(self.part_description_profile),
                                part_description_profile_path=self.current_part_description_profile_path,
                                part_description_profile_name=self.current_part_description_profile_name,
                                resume_completed_pdfs=self.check_resume_runs.isChecked())
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
        self._refresh_llm_test_buttons()
        if running:
            self.btn_run_classify.setEnabled(False)
            self.btn_run_extract.setEnabled(False)
            self.btn_restore_interrupted_run.setEnabled(False)
            self.btn_test_text_llm.setEnabled(False)
            self.btn_test_mllm.setEnabled(False)

    def browse_database(self):
        current_db = self._resolve_extract_db_path(self.edit_db_path.text())
        start_dir = os.path.dirname(current_db) or self._default_extract_result_dir()
        if not os.path.isdir(start_dir):
            start_dir = self._default_extract_result_dir()
        db_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Database File"),
            start_dir,
            "SQLite DB (*.db);;All Files (*)",
        )
        if not db_path:
            return
        self._set_extract_db_path(db_path)
        if not os.path.exists(db_path):
            QMessageBox.warning(self, self.tr("Error"), self.tr("No DB selected or file not found."))
            return
        dlg = DatabaseViewerDialog(db_path, self, self.current_lang)
        dlg.exec()

    def export_jsonl(self):
        db_path = self._resolve_extract_db_path(self.edit_db_path.text())
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
                    cursor.execute(
                        """
                        SELECT taxon_name, caste_or_stage, part_key, part_label,
                               description_text, source_pages, source_block_refs,
                               confidence, review_status, file_name, file_path, file_hash
                        FROM taxon_part_descriptions
                        WHERE pdf_file_id = (
                            SELECT pdf_file_id FROM figure_records WHERE id = ?
                        )
                          AND (
                            taxon_name = ?
                            OR ? = ''
                            OR taxon_name = ''
                        )
                        ORDER BY taxon_name ASC, part_key ASC, id ASC
                        """,
                        (figure_id, species_candidate or "", species_candidate or ""),
                    )
                    part_descriptions = []
                    for taxon_name, caste, part_key, part_label, description, source_pages, source_refs, part_confidence, review_status, file_name, file_path, file_hash in cursor.fetchall():
                        try:
                            pages_payload = json.loads(source_pages or "[]")
                        except Exception:
                            pages_payload = []
                        try:
                            refs_payload = json.loads(source_refs or "[]")
                        except Exception:
                            refs_payload = []
                        part_descriptions.append(
                            {
                                "taxon_name": taxon_name,
                                "caste_or_stage": caste,
                                "part_key": part_key,
                                "part_label": part_label,
                                "description_text": description,
                                "source_pages": pages_payload,
                                "source_block_refs": refs_payload,
                                "confidence": part_confidence,
                                "review_status": review_status,
                                "file_name": file_name,
                                "file_path": file_path,
                                "file_hash": file_hash,
                            }
                        )
                    rows.append((img_path, img_name, "\n".join(filter(None, [caption_text or "", *evidence_text])), species_candidate, page_number, final_confidence, part_descriptions))
            else:
                cursor.execute("""
                    SELECT i.image_file_path, i.image_file_name, t.text_content, '', 0, i.confidence_score
                    FROM image_text_relations r
                    JOIN images i ON r.image_id = i.id
                    JOIN text_blocks t ON r.text_block_id = t.id
                    WHERE i.is_taxonomic = 1 AND r.confidence_level = 'high'
                """)
                rows = [(*row, []) for row in cursor.fetchall()]
            count = 0
            
            with open(save_path, 'w', encoding='utf-8') as f:
                for img_path, img_name, text, species_candidate, page_number, final_confidence, part_descriptions in rows:
                    entry = {
                        "image": img_name,
                        "text": text,
                        "source": "pdf_raw_extract",
                        "species_candidate": species_candidate,
                        "page_number": page_number,
                        "confidence": final_confidence,
                        "part_descriptions": part_descriptions,
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    count += 1
                    
            QMessageBox.information(self, self.tr("Export Success"), 
                                    self.tr("Exported {} records to {}").format(count, save_path))
            conn.close()
            
        except Exception as e:
            QMessageBox.critical(self, self.tr("Error"), str(e))
