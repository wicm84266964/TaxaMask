# pyright: reportMissingImports=false

import os
import sys
import sqlite3
import tempfile
from pathlib import Path
from typing import TypedDict, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
ANTSLEAP_ROOT = ROOT / "AntSleap"
if str(ANTSLEAP_ROOT) not in sys.path:
    sys.path.insert(0, str(ANTSLEAP_ROOT))

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import main as main_module
from main import MainWindow, ModelSettingsDialog, ExportDialog, BlinkEntryDialog
from ui.pdf_processing_widget import PdfProcessingWidget, DatabaseViewerDialog
from ui.cropper import ImageCropper
from ui.blink_lab import BlinkLabWidget


MANUAL_IMAGE_DIR = ROOT / "docs" / "manual_images"
ENABLE_IMAGE_CALLOUTS = False
REAL_SAMPLE_IMAGE = Path(
    r"C:\savedata\Formica-Flow_output\20251204图文对应数据库\images\00034_1_Epimyrma_foreli_Menozzi_1921_29_fig_2_wq_view_2.jpg"
)
REAL_SAMPLE_STAGED_NAME = "Epimyrma_foreli_view_2.jpg"
SAMPLE_GENUS = "Epimyrma"
SAMPLE_SPECIES = "Epimyrma foreli"

ANNOTATION_RED = (176, 60, 48, 190)
ANNOTATION_RED_SOFT = (176, 60, 48, 88)
ANNOTATION_LABEL_FILL = (255, 255, 255, 224)
ANNOTATION_TEXT = (104, 36, 30, 255)

SAMPLE_LAYOUT = {
    "head_box": (0.02, 0.03, 0.30, 0.61),
    "head_polygon": [
        (0.03, 0.11),
        (0.18, 0.02),
        (0.27, 0.13),
        (0.28, 0.34),
        (0.23, 0.54),
        (0.08, 0.61),
        (0.02, 0.34),
    ],
    "eye_box": (0.08, 0.14, 0.17, 0.31),
    "eye_polygon": [
        (0.10, 0.19),
        (0.12, 0.14),
        (0.15, 0.15),
        (0.17, 0.21),
        (0.17, 0.29),
        (0.14, 0.33),
        (0.10, 0.31),
        (0.08, 0.24),
    ],
    "gaster_box": (0.71, 0.04, 0.98, 0.59),
    "gaster_polygon": [
        (0.74, 0.06),
        (0.90, 0.07),
        (0.98, 0.20),
        (0.96, 0.47),
        (0.84, 0.59),
        (0.72, 0.49),
        (0.71, 0.22),
    ],
    "crop_head": (0.02, 0.02, 0.34, 0.63),
    "crop_gaster": (0.68, 0.03, 0.30, 0.59),
}


NormalizedRect = tuple[float, float, float, float]
NormalizedPoint = tuple[float, float]


class ScreenshotCallout(TypedDict, total=False):
    label: str
    target_rect: NormalizedRect
    anchor: NormalizedPoint
    label_pos: NormalizedPoint
    show_leader: bool

SCREENSHOT_CALLOUTS: dict[str, list[ScreenshotCallout]] = {
    "fig_7_1_labeling_workbench_overview.png": [
        {
            "label": "当前部位",
            "target_rect": (0.81, 0.17, 0.98, 0.23),
            "anchor": (0.84, 0.20),
            "label_pos": (0.67, 0.18),
            "show_leader": False,
        },
        {
            "label": "进入 Blink",
            "target_rect": (0.67, 0.01, 0.99, 0.05),
            "anchor": (0.83, 0.03),
            "label_pos": (0.72, 0.06),
            "show_leader": False,
        },
    ],
    "fig_8_1_cropper_dialog.png": [
        {
            "label": "裁剪列表",
            "target_rect": (0.02, 0.14, 0.21, 0.49),
            "anchor": (0.12, 0.18),
            "label_pos": (0.03, 0.52),
            "show_leader": False,
        },
        {
            "label": "保存到项目",
            "target_rect": (0.02, 0.92, 0.21, 0.98),
            "anchor": (0.11, 0.95),
            "label_pos": (0.23, 0.84),
            "show_leader": False,
        },
    ],
    "fig_9_1_blink_entry_dialog.png": [
        {
            "label": "目标部位",
            "target_rect": (0.49, 0.31, 0.96, 0.43),
            "anchor": (0.74, 0.37),
            "label_pos": (0.07, 0.28),
            "show_leader": False,
        },
        {
            "label": "进入 ROI",
            "target_rect": (0.49, 0.50, 0.96, 0.62),
            "anchor": (0.74, 0.56),
            "label_pos": (0.07, 0.48),
            "show_leader": False,
        },
    ],
    "fig_9_2_blink_workbench_focused_session.png": [
        {
            "label": "焦点 ROI",
            "target_rect": (0.35, 0.03, 0.64, 0.53),
            "anchor": (0.43, 0.11),
            "label_pos": (0.15, 0.07),
            "show_leader": True,
        },
        {
            "label": "当前精修",
            "target_rect": (0.40, 0.12, 0.49, 0.28),
            "anchor": (0.43, 0.19),
            "label_pos": (0.66, 0.12),
            "show_leader": True,
        },
        {
            "label": "回写全局",
            "target_rect": (0.84, 0.27, 0.99, 0.35),
            "anchor": (0.91, 0.31),
            "label_pos": (0.69, 0.37),
            "show_leader": False,
        },
    ],
}


class DummyConfigManager:
    def __init__(self):
        self.store = {
            "language": "zh",
            "train_epochs": 5,
            "train_batch": 4,
            "train_lr": 1e-4,
            "train_weight_decay": 1e-4,
            "train_split_manifest_path": "artifacts/core2/split_manifest_run1.json",
            "train_core2_manifest_path": "artifacts/core2/train_manifest.json",
            "train_allow_random_fallback": False,
            "inf_conf_thresh": 0.1,
            "inf_adapt_thresh": 0.4,
            "inf_box_pad": 0.4,
            "inf_noise_floor": 0.15,
            "inf_poly_epsilon": 2.0,
            "last_project_path": "",
        }

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value):
        self.store[key] = value

    def save(self):
        return None


class DummyMultiModalDB:
    def query_trait_description(self, genus, part):
        return f"{genus} 的 {part} 描述占位文本。"


class DummyPartsModel:
    ultralytics_sam = None


class DummyEngine:
    def __init__(self, weights_dir):
        self.weights_dir = str(weights_dir)
        self.current_num_classes = 3
        self.parts_model = DummyPartsModel()
        self.history = {}

    def load_locator(self, timestamp):
        return None

    def reset_sam_to_base(self):
        return None

    def load_sam_decoder(self, timestamp):
        return None

    def rebuild_locator(self, num_classes, learning_rate, weight_decay):
        self.current_num_classes = num_classes

    def update_hyperparameters(self, learning_rate, weight_decay):
        return None

    def predict_full_pipeline(self, *args, **kwargs):
        return {}


def make_sample_image(path: Path):
    image = Image.new("RGB", (1400, 950), color=(245, 244, 240))
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 1320, 870), outline=(120, 110, 90), width=6)
    draw.ellipse((350, 170, 1040, 760), fill=(210, 180, 140), outline=(80, 60, 40), width=8)
    draw.ellipse((420, 260, 720, 520), fill=(160, 100, 60), outline=(60, 40, 20), width=6)
    draw.polygon([(500, 520), (740, 490), (680, 650), (470, 640)], fill=(190, 90, 70), outline=(70, 30, 20))
    draw.ellipse((605, 320, 675, 390), fill=(35, 35, 35))
    image.save(path)


def stage_sample_image(temp_dir: Path) -> Path:
    staged_path = temp_dir / REAL_SAMPLE_STAGED_NAME
    if REAL_SAMPLE_IMAGE.exists():
        with Image.open(REAL_SAMPLE_IMAGE) as image:
            image.convert("RGB").save(staged_path, quality=95)
        return staged_path

    fallback_path = temp_dir / "specimen_demo.png"
    make_sample_image(fallback_path)
    return fallback_path


def _scale_box(box: NormalizedRect, width: int, height: int):
    x1, y1, x2, y2 = box
    return [width * x1, height * y1, width * x2, height * y2]


def _scale_polygon(points: list[NormalizedPoint], width: int, height: int):
    return [[width * x, height * y] for x, y in points]


def get_sample_geometry(sample_image: Path):
    with Image.open(sample_image) as image:
        width, height = image.size

    head_box = cast(NormalizedRect, SAMPLE_LAYOUT["head_box"])
    head_polygon = cast(list[NormalizedPoint], SAMPLE_LAYOUT["head_polygon"])
    eye_box = cast(NormalizedRect, SAMPLE_LAYOUT["eye_box"])
    eye_polygon = cast(list[NormalizedPoint], SAMPLE_LAYOUT["eye_polygon"])
    gaster_box = cast(NormalizedRect, SAMPLE_LAYOUT["gaster_box"])
    gaster_polygon = cast(list[NormalizedPoint], SAMPLE_LAYOUT["gaster_polygon"])
    crop_head = cast(NormalizedRect, SAMPLE_LAYOUT["crop_head"])
    crop_gaster = cast(NormalizedRect, SAMPLE_LAYOUT["crop_gaster"])
    return {
        "head_box": _scale_box(head_box, width, height),
        "head_polygon": _scale_polygon(head_polygon, width, height),
        "eye_box": _scale_box(eye_box, width, height),
        "eye_polygon": _scale_polygon(eye_polygon, width, height),
        "gaster_box": _scale_box(gaster_box, width, height),
        "gaster_polygon": _scale_polygon(gaster_polygon, width, height),
        "crop_head": QRectF(width * crop_head[0], height * crop_head[1], width * crop_head[2], height * crop_head[3]),
        "crop_gaster": QRectF(width * crop_gaster[0], height * crop_gaster[1], width * crop_gaster[2], height * crop_gaster[3]),
    }


def load_annotation_font(size: int):
    font_files = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    ]
    for font_file in font_files:
        if font_file.exists():
            try:
                return ImageFont.truetype(str(font_file), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _norm_rect_to_px(rect: NormalizedRect, size: tuple[int, int]):
    width, height = size
    x1, y1, x2, y2 = rect
    return [int(width * x1), int(height * y1), int(width * x2), int(height * y2)]


def _norm_point_to_px(point: NormalizedPoint, size: tuple[int, int]):
    width, height = size
    x, y = point
    return int(width * x), int(height * y)


def _closest_point_on_rect(point: tuple[int, int], rect):
    x, y = point
    x1, y1, x2, y2 = rect
    return max(x1, min(x, x2)), max(y1, min(y, y2))


def _clamp(value: float, lower: float, upper: float):
    return max(lower, min(value, upper))


def _rect_center(rect):
    x1, y1, x2, y2 = rect
    return int((x1 + x2) / 2), int((y1 + y2) / 2)


def _annotation_font_size(size: tuple[int, int]):
    width, _ = size
    if width >= 1400:
        return 20
    if width >= 900:
        return 18
    return 16


def _corner_span(length: int):
    return max(14, min(38, int(length * 0.18)))


def _draw_corner_brackets(draw: ImageDraw.ImageDraw, rect, color, width: int):
    x1, y1, x2, y2 = rect
    span_x = _corner_span(x2 - x1)
    span_y = _corner_span(y2 - y1)

    draw.line([(x1, y1 + span_y), (x1, y1), (x1 + span_x, y1)], fill=color, width=width)
    draw.line([(x2 - span_x, y1), (x2, y1), (x2, y1 + span_y)], fill=color, width=width)
    draw.line([(x1, y2 - span_y), (x1, y2), (x1 + span_x, y2)], fill=color, width=width)
    draw.line([(x2 - span_x, y2), (x2, y2), (x2, y2 - span_y)], fill=color, width=width)


def _edge_connection_start(rect, anchor: tuple[int, int], label_rect):
    x1, y1, x2, y2 = rect
    rect_cx, rect_cy = _rect_center(rect)
    label_cx, label_cy = _rect_center(label_rect)
    anchor_x, anchor_y = _closest_point_on_rect(anchor, rect)
    edge_margin = max(8, min(18, int(min(x2 - x1, y2 - y1) * 0.18)))

    dx = label_cx - rect_cx
    dy = label_cy - rect_cy
    horizontal_bias = abs(dx) / max(1, x2 - x1)
    vertical_bias = abs(dy) / max(1, y2 - y1)

    if horizontal_bias >= vertical_bias:
        if dx >= 0:
            return (x2, int(_clamp(anchor_y, y1 + edge_margin, y2 - edge_margin))), "right"
        return (x1, int(_clamp(anchor_y, y1 + edge_margin, y2 - edge_margin))), "left"

    if dy >= 0:
        return (int(_clamp(anchor_x, x1 + edge_margin, x2 - edge_margin)), y2), "bottom"
    return (int(_clamp(anchor_x, x1 + edge_margin, x2 - edge_margin)), y1), "top"


def _offset_point(point: tuple[int, int], side: str, distance: int):
    x, y = point
    if side == "left":
        return x - distance, y
    if side == "right":
        return x + distance, y
    if side == "top":
        return x, y - distance
    return x, y + distance


def annotate_manual_image(image_path: Path):
    if not ENABLE_IMAGE_CALLOUTS:
        return
    callouts = SCREENSHOT_CALLOUTS.get(image_path.name)
    if not callouts:
        return

    with Image.open(image_path) as image:
        annotated = image.convert("RGBA")

    overlay = Image.new("RGBA", annotated.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    font = load_annotation_font(_annotation_font_size(annotated.size))
    stroke_width = 2 if max(annotated.size) >= 1000 else 2
    leader_width = 2
    label_padding_x = 12 if max(annotated.size) >= 1000 else 10
    label_padding_y = 8
    leader_stub = max(10, min(18, int(min(annotated.size) * 0.02)))

    for callout in callouts:
        label = callout["label"]
        target_rect = _norm_rect_to_px(callout["target_rect"], annotated.size)
        anchor = _norm_point_to_px(callout["anchor"], annotated.size)
        label_x, label_y = _norm_point_to_px(callout["label_pos"], annotated.size)

        _draw_corner_brackets(draw, target_rect, ANNOTATION_RED, stroke_width)

        text_bbox = draw.multiline_textbbox((0, 0), label, font=font, spacing=4)
        label_rect = [
            label_x,
            label_y,
            label_x + (text_bbox[2] - text_bbox[0]) + label_padding_x * 2,
            label_y + (text_bbox[3] - text_bbox[1]) + label_padding_y * 2,
        ]

        if callout.get("show_leader", True):
            leader_start, leader_side = _edge_connection_start(target_rect, anchor, label_rect)
            leader_stub_end = _offset_point(leader_start, leader_side, leader_stub)
            label_anchor = _closest_point_on_rect(leader_stub_end, label_rect)
            if leader_side in {"left", "right"}:
                elbow = (leader_stub_end[0], label_anchor[1])
            else:
                elbow = (label_anchor[0], leader_stub_end[1])

            leader_points = [leader_start, leader_stub_end]
            if elbow != leader_stub_end and elbow != label_anchor:
                leader_points.append(elbow)
            if label_anchor != leader_points[-1]:
                leader_points.append(label_anchor)
            draw.line(leader_points, fill=ANNOTATION_RED_SOFT, width=leader_width)

        draw.rounded_rectangle(
            label_rect,
            radius=12,
            fill=ANNOTATION_LABEL_FILL,
            outline=ANNOTATION_RED_SOFT,
            width=2,
        )
        draw.multiline_text(
            (label_x + label_padding_x, label_y + label_padding_y),
            label,
            font=font,
            fill=ANNOTATION_TEXT,
            spacing=4,
        )

    Image.alpha_composite(annotated, overlay).save(image_path)


def make_database(db_path: Path, image_path: Path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE figure_records (
            id INTEGER PRIMARY KEY,
            image_file_name TEXT,
            image_file_path TEXT,
            final_confidence REAL,
            accepted INTEGER,
            page_number INTEGER,
            species_candidate TEXT,
            category TEXT,
            review_status TEXT,
            rejection_reason TEXT,
            caption_text TEXT,
            multimodal_validated INTEGER,
            multimodal_review_mode TEXT,
            multimodal_model_used TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE figure_evidence (
            id INTEGER PRIMARY KEY,
            figure_id INTEGER,
            evidence_level TEXT,
            evidence_type TEXT,
            text_content TEXT,
            match_score REAL,
            section_title TEXT
        )
        """
    )
    cur.execute(
        """
        INSERT INTO figure_records (
            id, image_file_name, image_file_path, final_confidence, accepted, page_number,
            species_candidate, category, review_status, rejection_reason, caption_text,
            multimodal_validated, multimodal_review_mode, multimodal_model_used
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            image_path.name,
            str(image_path),
            0.93,
            1,
            12,
            SAMPLE_SPECIES,
            "new_species_report",
            "accepted",
            "",
            "Figure 12. Worker habitus in lateral view; head, eye, and gaster remain clearly visible for annotation.",
            1,
            "real",
            "gpt-5.4",
        ),
    )
    cur.executemany(
        """
        INSERT INTO figure_evidence (figure_id, evidence_level, evidence_type, text_content, match_score, section_title)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (1, "figure_local", "caption", "Lateral habitus preserves the head capsule, compound eye, and gaster outline for downstream review.", 0.98, "Figure caption"),
            (1, "species_core", "body_text", "Diagnosis text emphasizes cephalic form, eye placement, and waist-to-gaster profile.", 0.91, "Diagnosis"),
        ],
    )
    conn.commit()
    conn.close()


def patch_main_dependencies(weights_dir: Path):
    main_module.ConfigManager = DummyConfigManager
    main_module.MultiModalDB = DummyMultiModalDB
    main_module.AntEngine = lambda learning_rate=None, weight_decay=None, num_classes=None: DummyEngine(weights_dir)
    main_module.QTimer.singleShot = lambda *args, **kwargs: None
    main_module.MainWindow.init_sam = lambda self: None


def save_widget(widget, output_path: Path, app: QApplication, size=None):
    if size is not None:
        widget.resize(*size)
    widget.show()
    widget.repaint()
    app.processEvents()
    QTest.qWait(150)
    app.processEvents()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    widget.grab().save(str(output_path))


def apply_cjk_font(app: QApplication):
    font_files = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    ]
    for font_file in font_files:
        if font_file.exists():
            font_id = QFontDatabase.addApplicationFont(str(font_file))
            if font_id >= 0:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    app.setFont(QFont(families[0], 10))
                    return families[0]

    preferred_fonts = [
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "Noto Sans SC",
        "Microsoft JhengHei UI",
        "Microsoft JhengHei",
        "SimHei",
        "SimSun",
    ]
    families = set(QFontDatabase.families())
    for family in preferred_fonts:
        if family in families:
            app.setFont(QFont(family, 10))
            return family
    return None


def build_main_window(app: QApplication, temp_dir: Path, sample_image: Path):
    geometry = get_sample_geometry(sample_image)
    weights_dir = temp_dir / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    (weights_dir / "locator_20260319_demo.pth").write_bytes(b"demo")
    (weights_dir / "sam_decoder_lora_20260319_demo.pth").write_bytes(b"demo")
    expert_dir = weights_dir / "experts" / "Eye"
    expert_dir.mkdir(parents=True, exist_ok=True)
    (expert_dir / "best_expert.pth").write_bytes(b"demo-best")
    (expert_dir / "expert_v20260319_090000.pth").write_bytes(b"demo-archived")

    patch_main_dependencies(weights_dir)
    previous_cwd = Path.cwd()
    os.chdir(temp_dir)
    try:
        window = MainWindow()
    finally:
        os.chdir(previous_cwd)

    project_path = temp_dir / "manual_demo.json"
    window.project.create_project("manual_demo", str(temp_dir))
    window.project.current_project_path = str(project_path)
    window.project.add_images([str(sample_image)])
    window.project.set_genus(str(sample_image), SAMPLE_GENUS)
    window.project.update_label(
        str(sample_image),
        "Head",
        geometry["head_polygon"],
        "头部轮廓示例",
        box=geometry["head_box"],
    )
    window.project.update_label(
        str(sample_image),
        "Gaster",
        geometry["gaster_polygon"],
        "腹部轮廓示例",
        box=geometry["gaster_box"],
    )
    window.project.update_label(
        str(sample_image),
        "Eye",
        geometry["eye_polygon"],
        "Auto-Annotated",
        auto_box=geometry["eye_box"],
    )
    window.project.set_scale(str(sample_image), 120.0)
    window.refresh_model_list()
    window.refresh_ui()
    window.refresh_file_list()
    window.tabs.setCurrentIndex(1)
    window.file_list.setCurrentRow(0)
    app.processEvents()
    if window.part_list.count() > 0:
        window.part_list.setCurrentRow(0)
    window.check_morpho.setChecked(True)
    window.update_measurements("Head")
    window.log_console.append("系统初始化完成，示例项目已载入。")
    window.log_console.append("当前图片已选择，可直接进入 Blink 工作台。")
    return window, weights_dir


def capture_main_window(app, output_dir: Path, temp_dir: Path, sample_image: Path):
    window, _ = build_main_window(app, temp_dir, sample_image)
    save_widget(window, output_dir / "fig_3_1_main_window_overview.png", app, size=(1600, 1000))
    save_widget(window.workbench_widget, output_dir / "fig_7_1_labeling_workbench_overview.png", app, size=(1500, 900))
    annotate_manual_image(output_dir / "fig_7_1_labeling_workbench_overview.png")
    return window


def capture_pdf_widget(app, output_dir: Path):
    widget = PdfProcessingWidget("zh")
    widget.edit_api_key.clear()
    widget.chk_remember_api_key.setChecked(False)
    widget.edit_base_url.setText("https://api.siliconflow.cn/v1")
    widget.edit_model.setText("gpt-5.4")
    widget.combo_api_protocol.setCurrentIndex(widget.combo_api_protocol.findData("auto"))
    widget.edit_src_folder.setText(r"C:\savedata\pdf_source")
    widget.edit_out_folder.setText(r"C:\savedata\pdf_output")
    widget.log_area.append("--- 开始任务，当前方案：默认 V2 方案 ---")
    widget.log_area.append("--- 运行模式：V2 | lines=30 | batch=80/40 | chars=100000 | text_chars=1600 | max_tokens=12000 | timeout=240s | threshold=0.75 | split=True | resume=True | isolate=True | api_protocol=auto ---")
    widget.tabs.setCurrentIndex(0)
    save_widget(widget, output_dir / "fig_5_1_pdf_screener_overview.png", app, size=(1400, 900))

    widget.tabs.setCurrentIndex(1)
    widget.edit_ext_src.setText(r"C:\savedata\pdf_selected")
    widget.edit_db_path.setText(r"C:\savedata\ant_literature.db")
    widget.check_mllm.setChecked(True)
    save_widget(widget, output_dir / "fig_5_2_pdf_extractor_overview.png", app, size=(1400, 900))
    return widget


def capture_database_viewer(app, output_dir: Path, db_path: Path):
    dialog = DatabaseViewerDialog(str(db_path), lang="zh")
    if dialog.table.rowCount() > 0:
        dialog.table.selectRow(0)
        dialog.on_row_selected()
    save_widget(dialog, output_dir / "fig_6_1_database_viewer.png", app, size=(1200, 800))


def capture_cropper(app, output_dir: Path, sample_image: Path):
    geometry = get_sample_geometry(sample_image)
    dialog = ImageCropper(initial_image=str(sample_image), lang="zh")
    crop_a = geometry["crop_head"]
    crop_b = geometry["crop_gaster"]
    dialog.canvas.crops = [crop_a, crop_b]
    dialog.on_crop_added(crop_a)
    dialog.on_crop_added(crop_b)
    dialog.canvas.update()
    save_widget(dialog, output_dir / "fig_8_1_cropper_dialog.png", app, size=(1200, 800))
    annotate_manual_image(output_dir / "fig_8_1_cropper_dialog.png")


def capture_blink_dialogs(app, output_dir: Path, sample_image: Path, weights_dir: Path):
    geometry = get_sample_geometry(sample_image)
    entry_dialog = BlinkEntryDialog(
        str(sample_image),
        ["Head", "Mesosoma", "Gaster", "Eye"],
        "Eye",
        [
            {"part": "Head", "source": "manual", "box": geometry["head_box"]},
            {"part": "Gaster", "source": "manual", "box": geometry["gaster_box"]},
            {"part": "Eye", "source": "auto", "box": geometry["eye_box"]},
        ],
        lang="zh",
    )
    for index in range(entry_dialog.roi_combo.count()):
        candidate = entry_dialog.roi_combo.itemData(index)
        if isinstance(candidate, dict) and candidate.get("part") == "Head" and candidate.get("source") == "manual":
            entry_dialog.roi_combo.setCurrentIndex(index)
            break
    save_widget(entry_dialog, output_dir / "fig_9_1_blink_entry_dialog.png", app, size=(520, 220))
    annotate_manual_image(output_dir / "fig_9_1_blink_entry_dialog.png")

    engine = DummyEngine(weights_dir)
    expert_dir = Path(engine.weights_dir) / "experts" / "Eye"
    expert_dir.mkdir(parents=True, exist_ok=True)
    (expert_dir / "best_expert.pth").write_bytes(b"demo-best")
    (expert_dir / "expert_v20260319_090000.pth").write_bytes(b"demo-archived")

    class PM:
        def __init__(self, image_path):
            self.project_data = {
                "taxonomy": ["Head", "Gaster", "Eye"],
                "locator_scope": ["Head", "Gaster"],
            }
            self.labels_by_path = {
                image_path: {
                    "parts": {
                        "Head": geometry["head_polygon"],
                        "Gaster": geometry["gaster_polygon"],
                        "Eye": geometry["eye_polygon"],
                    },
                    "boxes": {
                        "Head": geometry["head_box"],
                        "Gaster": geometry["gaster_box"],
                    },
                    "auto_boxes": {
                        "Eye": geometry["eye_box"],
                    },
                    "trajectories": {},
                }
            }

        def get_labels(self, path):
            return self.labels_by_path.get(path, {}).get("parts", {})

        def get_boxes(self, path):
            return self.labels_by_path.get(path, {}).get("boxes", {})

        def get_auto_boxes(self, path):
            return self.labels_by_path.get(path, {}).get("auto_boxes", {})

        def update_label(self, *args, **kwargs):
            return None

        def update_trajectory(self, *args, **kwargs):
            return None

    pm = PM(str(sample_image))
    blink_widget = BlinkLabWidget(engine, pm, lang="zh")
    blink_widget.start_session(
        {
            "image_path": str(sample_image),
            "target_part": "Eye",
            "focus_roi": {"part": "Head", "source": "manual", "box": geometry["head_box"]},
        },
        pm.get_labels(str(sample_image)),
        pm.get_boxes(str(sample_image)),
        pm.get_auto_boxes(str(sample_image)),
    )
    blink_widget.refresh_expert_registry()
    save_widget(blink_widget, output_dir / "fig_9_2_blink_workbench_focused_session.png", app, size=(1500, 900))
    annotate_manual_image(output_dir / "fig_9_2_blink_workbench_focused_session.png")


def capture_model_and_export_dialogs(app, output_dir: Path):
    model_dialog = ModelSettingsDialog(
        {
            "epochs": 8,
            "batch": 4,
            "lr": 1e-4,
            "wd": 1e-4,
            "conf": 0.1,
            "adapt": 0.4,
            "pad": 0.4,
            "noise_floor": 0.15,
            "poly_epsilon": 2.0,
        },
        lang="zh",
    )
    save_widget(model_dialog, output_dir / "fig_10_1_model_settings_dialog.png", app, size=(500, 420))

    export_dialog = ExportDialog(lang="zh")
    export_dialog.path_edit.setText(r"C:\savedata\exports\demo")
    save_widget(export_dialog, output_dir / "fig_11_1_export_dataset_dialog.png", app, size=(460, 220))


def main():
    app = cast(QApplication, QApplication.instance() or QApplication([]))
    font_family = apply_cjk_font(app)
    MANUAL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        sample_image = stage_sample_image(temp_dir)
        db_path = temp_dir / "manual_demo.db"
        make_database(db_path, sample_image)

        window = capture_main_window(app, MANUAL_IMAGE_DIR, temp_dir, sample_image)
        weights_dir = Path(window.engine.weights_dir)
        capture_pdf_widget(app, MANUAL_IMAGE_DIR)
        capture_database_viewer(app, MANUAL_IMAGE_DIR, db_path)
        capture_cropper(app, MANUAL_IMAGE_DIR, sample_image)
        capture_blink_dialogs(app, MANUAL_IMAGE_DIR, sample_image, weights_dir)
        capture_model_and_export_dialogs(app, MANUAL_IMAGE_DIR)

    print("Generated screenshots:")
    if font_family:
        print(f"Using font: {font_family}")
    for path in sorted(MANUAL_IMAGE_DIR.glob("fig_*.png")):
        print(path.name)


if __name__ == "__main__":
    main()
