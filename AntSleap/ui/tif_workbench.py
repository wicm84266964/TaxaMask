import math
import os

import numpy as np
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QPen, QPixmap, QPolygonF, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from AntSleap.core.amira_import import import_amira_directory
    from AntSleap.core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG, TifBackendRunner, sanitize_tif_backend_config
    from AntSleap.core.tif_export import export_tif_training_dataset
    from AntSleap.core.tif_materials import next_material_id, read_material_map, remove_material, upsert_material, write_material_map
    from AntSleap.core.tif_part_extraction import (
        add_rectangular_keyframe,
        add_polygon_keyframe,
        build_preview_mask_from_contours,
        crop_volume_to_part,
        delete_keyframe,
        export_part_package,
        neighboring_keyframe_indices,
        read_contours_json,
        validate_contours_for_interpolation,
        write_contours_json,
        write_part_mask,
    )
    from AntSleap.core.tif_prediction_import import default_prediction_id_for_tif, import_external_prediction_tif
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.core.tif_stack_import import import_tif_stack
    from AntSleap.core.tif_volume_io import create_empty_label_sidecar_like, flush_volume_array, load_volume_sidecar, volume_sidecar_exists
    from AntSleap.core.tif_local_axis_reslice import create_editable_axis_from_source, source_z_axis_for_part
    from AntSleap.ui.tif_local_axis_model_panel import TifLocalAxisModelDialog
    from AntSleap.ui.tif_local_axis_reslice_page import TifLocalAxisResliceDialog
    from AntSleap.ui.tif_local_axis_review_queue import TifLocalAxisReviewQueueWidget
    from AntSleap.ui.tif_gpu_volume_canvas import (
        GPU_VOLUME_MAX_RAY_STEPS,
        GPU_VOLUME_MAX_TEXTURE_DIM,
        TifGpuVolumeCanvas,
        TifGpuVolumeOffscreenWidget,
        build_volume_transfer_lut,
        gpu_volume_canvas_available,
        gpu_volume_offscreen_available,
        gpu_volume_unavailable_reason,
        volume_shape_scale,
    )
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.amira_import import import_amira_directory
    from core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG, TifBackendRunner, sanitize_tif_backend_config
    from core.tif_export import export_tif_training_dataset
    from core.tif_materials import next_material_id, read_material_map, remove_material, upsert_material, write_material_map
    from core.tif_part_extraction import (
        add_rectangular_keyframe,
        add_polygon_keyframe,
        build_preview_mask_from_contours,
        crop_volume_to_part,
        delete_keyframe,
        export_part_package,
        neighboring_keyframe_indices,
        read_contours_json,
        validate_contours_for_interpolation,
        write_contours_json,
        write_part_mask,
    )
    from core.tif_prediction_import import default_prediction_id_for_tif, import_external_prediction_tif
    from core.tif_project import TifProjectManager
    from core.tif_stack_import import import_tif_stack
    from core.tif_volume_io import create_empty_label_sidecar_like, flush_volume_array, load_volume_sidecar, volume_sidecar_exists
    from core.tif_local_axis_reslice import create_editable_axis_from_source, source_z_axis_for_part
    from ui.tif_local_axis_model_panel import TifLocalAxisModelDialog
    from ui.tif_local_axis_reslice_page import TifLocalAxisResliceDialog
    from ui.tif_local_axis_review_queue import TifLocalAxisReviewQueueWidget
    from ui.tif_gpu_volume_canvas import (
        GPU_VOLUME_MAX_RAY_STEPS,
        GPU_VOLUME_MAX_TEXTURE_DIM,
        TifGpuVolumeCanvas,
        TifGpuVolumeOffscreenWidget,
        build_volume_transfer_lut,
        gpu_volume_canvas_available,
        gpu_volume_offscreen_available,
        gpu_volume_unavailable_reason,
        volume_shape_scale,
    )


TIF_TRANSLATIONS = {
    "zh": {
        "Material": "Material",
        "ID": "ID",
        "Name": "名称",
        "Display name": "显示名称",
        "Color": "颜色",
        "Trainable": "可训练",
        "Choose color": "选择颜色",
        "No TIF volume loaded": "未加载 TIF 体数据",
        "Specimens": "Specimen",
        "Volume slices": "体数据切片",
        "Volume controls": "体数据控制",
        "Current object": "当前对象",
        "Display": "显示",
        "Annotation": "标注",
        "Train/export": "训练/导出",
        "Slice display": "切片显示",
        "3D rendering": "三维体渲染",
        "Annotation tools": "标注工具",
        "Model training": "模型训练",
        "Model configuration": "模型配置",
        "Workbench log": "工作台日志",
        "Display mode": "显示模式",
        "Slice review": "切片复核",
        "3D volume": "三维体预览",
        "Volume render": "体渲染",
        "Render mode": "渲染模式",
        "Composite": "透明累积",
        "MIP": "最大强度",
        "MinIP": "最小强度",
        "Average": "平均强度",
        "Surface": "表面边界",
        "Density cutoff": "密度阈值",
        "Render quality": "渲染质量",
        "Ray samples": "光线采样",
        "ROI high detail": "ROI 高清",
        "ROI scale": "ROI 倍率",
        "Inside depth": "视点深度",
        "Front cut": "近端剖切",
        "Mask display": "Mask 显示",
        "Image only": "仅图像",
        "Mask boundary": "Mask 边界",
        "Masked image": "只看 Mask 内图像",
        "Mask opacity": "Mask 透明度",
        "Transfer function": "密度映射",
        "Density opacity": "密度透明度",
        "Detail enhancement": "细节增强",
        "Tone curve": "明暗曲线",
        "Surface refine": "表面精修",
        "Clip plane": "任意剖切面",
        "Show local axes": "显示局部轴",
        "source Z": "原始 Z",
        "output Z": "输出 Z",
        "Clip depth": "剖切深度",
        "View aligned": "按当前视角",
        "Drag preview": "拖动预览",
        "Still high quality": "静止高清",
        "VRAM": "显存",
        "Upload": "上传",
        "Draw": "绘制",
        "actual": "实际",
        "GPU stats pending": "等待 GPU 统计",
        "Renderer": "渲染器",
        "GPU ray march": "GPU 光线步进",
        "CPU fallback": "CPU 回退",
        "GPU renderer unavailable. Using CPU fallback.": "GPU 渲染器不可用，正在使用 CPU 回退。",
        "GPU renderer failed. Using CPU fallback: {0}": "GPU 渲染器失败，正在使用 CPU 回退：{0}",
        "GPU fallback active": "GPU 回退中",
        "bottleneck: texture upload": "瓶颈：纹理上传",
        "bottleneck: ray rendering": "瓶颈：光线渲染",
        "large GPU texture": "大体积 GPU 纹理",
        "GPU failed": "GPU 失败",
        "Reset 3D view": "重置 3D 视角",
        "drag rotate / wheel zoom": "左键旋转 / 右键平移 / 滚轮缩放",
        "Volume view": "体预览",
        "Texture": "纹理",
        "Samples": "采样",
        "Inside": "视点",
        "Cut": "近端切",
        "Zoom": "缩放",
        "Pan X": "横移",
        "Pan Y": "纵移",
        "Clarity mode": "清晰模式",
        "Sharp": "清晰",
        "Smooth": "平滑",
        "Data": "数据",
        "Mode": "模式",
        "ROI": "ROI",
        "Filters low-gray background and noise. Raise it for outer shape review; lower it when weak internal structures disappear.": "密度映射的起点。调高会过滤背景和噪声，适合看外轮廓；调低会保留弱信号，适合找内部淡结构。",
        "Switches how values along the viewing ray are projected. MIP highlights bright structures, MinIP highlights dark gaps, Average shows density trend, and Surface emphasizes boundaries.": "切换视线方向上的体数据投影方式。最大强度适合看亮结构，最小强度适合看暗间隙，平均强度适合看整体密度，表面边界适合看轮廓。",
        "Controls the maximum edge length of the still GPU volume. Dragging uses a smaller temporary texture, then rebuilds this sharper texture when the view settles.": "控制静止高清时上传到 GPU 的体数据最大边长。拖动时会临时用较小纹理，停下后自动重建这个高清纹理；3090 可尝试 1024 到 2048。",
        "Controls the number of samples per screen pixel along the viewing ray. Higher values stabilize internal layers and fine lines, mainly increasing GPU compute load.": "控制每个屏幕像素沿视线取样次数。数值越高，内部层次和细线更稳定，但主要增加 GPU 计算负载；如果转动不卡，可继续调高。",
        "When zoomed in and still, renders the 3D view at a higher offscreen pixel density before scaling it back, improving small-part inspection at the cost of more GPU readback work.": "静止且放大观察时，先用更高离屏像素密度渲染三维体，再缩回当前显示区域。它能改善小部位观察，但会增加 GPU 读回和显示成本。",
        "Controls the offscreen supersampling factor used by ROI high detail. Higher values make still zoomed views smoother but heavier.": "控制 ROI 高清的离屏超采样倍数。数值越高，静止放大视图越平滑，但负载也更重。",
        "Sharp still rendering keeps more source intensity detail and uses crisper sampling. It may upload more data and can look grainier while revealing fine internal structures.": "静止高清时尽量保留原始灰度层次，并使用更锐利的采样。它会上传更多数据，画面可能更有颗粒感，但更容易看清细小内部结构。",
        "Controls how strongly dense voxels accumulate in 3D. Lower values make internal layers less blocked; higher values make weak structures more visible.": "控制三维渲染中密度累积的强弱。调低会减少遮挡，更容易看内部层次；调高会让弱信号更明显，但画面可能更厚。",
        "Enhances fine boundaries while the view is still. It is a display-only aid for checking internal layers and part edges.": "静止观察时增强细小边界。它只是显示辅助，用于检查内部层次和部位边缘，不修改原始数据。",
        "Adjusts display gamma for 3D rendering. Lower values brighten faint structures; higher values keep dense regions calmer.": "调整三维渲染的显示曲线。调低会提亮弱结构，调高会让高密度区域更克制。",
        "Refines first surface hits in Surface mode while still. It improves contour stability without affecting Composite rendering.": "静止且使用表面边界模式时精修首次命中位置，让轮廓更稳定；不影响透明累积模式。",
        "Enables a view-aligned GPU clipping plane. It only cuts the display, not the saved TIF, mask, or training data.": "启用按当前视角对齐的 GPU 剖切面。它只切开屏幕显示，不会修改已保存的 TIF、Mask 或训练数据。",
        "Shows the locked source Z axis and the selected local output axis on the 3D part preview. This is display-only and does not edit data.": "在三维部位预览中显示锁定的原始 Z 轴和当前选中局部输出轴。这个开关只影响显示，不修改数据。",
        "Moves the clipping plane through the current 3D view. Use it to peel away outer tissue and inspect inside structures.": "沿当前三维视角移动剖切面。可用于剥开外层组织观察内部结构。",
        "Shows accepted or preview part masks in the 3D view. Boundary is best for checking extraction edges; masked image hides voxels outside the mask.": "在三维视图中显示已接受或预览中的部位 Mask。边界模式适合检查切除轮廓，只看 Mask 内图像会隐藏 Mask 外体素。",
        "Controls how strongly mask boundaries are blended into the 3D inspection view.": "控制 Mask 边界叠加到三维观察视图中的强度。",
        "Moves the camera into the volume. Use it to enter the specimen and inspect internal structures; keep it at 0 for outer shape review.": "移动观察点。0 在样本外看整体，100 接近样本中心，100 以上继续进入更深内部；它不切掉体数据，只改变你站在哪里看。",
        "Cuts away the front part of the current view. Use it to remove blocking outer tissue and inspect deeper structures; keep it at 0 for the full outline.": "从当前视角靠近屏幕的一侧切掉一段体数据。它不移动观察点，只移除挡在眼前的近端外层；看完整外轮廓时保持为 0。",
        "Restores the external default view and clears inside depth and front cut.": "恢复外部默认视角，并清空视点深度和近端剖切。",
        "3D preview uses a downsampled read-only volume. Use Slice review for precise label editing.": "3D 预览使用降采样只读体数据。精确标签修改请使用切片复核。",
        "3D volume preview is read-only. Switch to Slice review for label editing.": "3D 体预览为只读观察。需要修改标签时请切回切片复核。",
        "Slice": "切片",
        "View plane": "切片方向",
        "Z axial": "Z 轴切片",
        "Y coronal": "Y 方向切片",
        "X sagittal": "X 方向切片",
        "Side-angle slices are read-only in this version. Use Z axial view for label editing.": "当前版本中侧向切片为只读观察。需要修改标签时请切回 Z 轴切片。",
        "Painting is available on Z slices only. Switch back to Z axial view before editing labels.": "画笔编辑目前只开放在 Z 轴切片上。修改标签前请切回 Z 轴切片。",
        "Label layer": "标签层",
        "Manual truth is a read-only reference. Switch to Current edit before changing labels.": "人工真值是只读基准层。要修改标注，请先切换到“当前编辑”。",
        "Current edit is the editable working copy. Brush changes are saved here first.": "当前编辑是可写的工作副本。画笔修改会先保存到这一层。",
        "Model draft is a read-only prediction candidate. Copy it to Current edit before manual correction.": "模型草稿是只读的预测候选。需要人工修正时，请先复制到“当前编辑”。",
        "Cannot paint on this label layer. Switch to Current edit first.": "当前标签层不能直接绘制。请先切换到“当前编辑”。",
        "Cannot paint on model draft. Copy model draft to Current edit first.": "不能直接在模型草稿上绘制。请先复制模型草稿到“当前编辑”。",
        "manual_truth": "人工真值",
        "working_edit": "当前编辑",
        "model_draft": "模型草稿",
        "Overlay": "叠加透明度",
        "Brightness": "亮度",
        "Contrast": "对比度",
        "Brush size": "画笔大小",
        "Undo": "撤销",
        "Redo": "重做",
        "Save working edit": "保存当前编辑层",
        "Auto-save edit": "自动保存编辑层",
        "Working edit saved.": "当前编辑层已保存。",
        "Auto-saved working edit.": "已自动保存当前编辑层。",
        "Unsaved working edit": "未保存的当前编辑层",
        "Save changes to the current working_edit before continuing?": "继续前是否保存当前 working_edit 的修改？",
        "Auto-save is on. Brush changes are saved shortly after editing.": "自动保存已开启。修改后会短延迟保存。",
        "Auto-save is off. Remember to save the current edit layer.": "自动保存已关闭。请记得手动保存当前编辑层。",
        "Accept as manual truth": "确认为人工真值",
        "Copy model draft to working edit": "复制模型草稿到当前编辑层",
        "Material map": "材料表",
        "Add material": "新增 material",
        "Edit material": "编辑 material",
        "Delete material": "删除 material",
        "Data import": "数据导入",
        "Part extraction": "部位提取",
        "1. Locate part": "1. 定位部位",
        "2. Build part mask": "2. 生成部位 mask",
        "3. Output and manage": "3. 输出与管理",
        "Full volume": "整只体数据",
        "Part volume": "部位体数据",
        "Part": "部位",
        "Reslices": "重切片",
        "Parent specimen": "父标本",
        "Current view": "当前视图",
        "Parent bbox Z/Y/X": "父体 bbox Z/Y/X",
        "Part image": "部位图像",
        "Part mask": "部位 mask",
        "Contours": "轮廓文件",
        "Extraction": "提取记录",
        "Parent working volume": "父工作体数据",
        "Use center ROI": "使用中心 ROI",
        "Draw ROI": "手动框选 ROI",
        "Save ROI draft": "保存 ROI 草稿",
        "Confirm ROI": "确认 ROI",
        "Cancel ROI": "取消 ROI",
        "ROI ID:": "ROI 编号：",
        "Create part": "新建部位",
        "Part ID:": "部位编号：",
        "Display name:": "显示名称：",
        "z0,z1,y0,y1,x0,x1": "z0,z1,y0,y1,x0,x1",
        "Add rectangular key slice": "添加矩形关键切片",
        "Draw contour": "手绘轮廓",
        "Delete key slice": "删除当前关键切片",
        "Previous key slice": "上一关键切片",
        "Next key slice": "下一关键切片",
        "Preview auto fill": "预览自动填充",
        "Accept part mask": "接受部位 mask",
        "Clear preview": "清除预览",
        "Local Axis Reslice": "局部轴重切片",
        "Local Axis Reslice / part volume": "局部轴重切片 / 部位体数据",
        "Review Local Axis Queue": "复核局部轴队列",
        "Local Axis Models": "局部轴模型",
        "Export part package": "导出部位包",
        "Delete part volume": "删除部位体数据",
        "Delete part volume?": "删除部位体数据？",
        "Delete part volume {0}? This removes the cropped image, mask, contours, and extraction files, but keeps the parent TIF volume.": "确认删除部位体数据 {0} 吗？这会删除裁剪图像、mask、轮廓和提取记录，但不会删除父级 TIF 体数据。",
        "Deleted part volume {0}.": "已删除部位体数据 {0}。",
        "Switch to Full volume before creating a part.": "请先切回整只体数据，再新建部位。",
        "Switch to Full volume before saving ROI draft.": "请先切回整只体数据，再保存 ROI 草稿。",
        "Switch to Full volume before confirming ROI.": "请先切回整只体数据，再确认 ROI。",
        "Switch to Full volume before drawing ROI.": "请先切回整只体数据，再手动框选 ROI。",
        "Drag on the current slice to update the ROI bbox.": "请在当前切片上拖拽矩形，用来更新 ROI bbox。",
        "ROI bbox updated: {0}": "ROI bbox 已更新：{0}",
        "Saved ROI draft {0}.": "已保存 ROI 草稿 {0}。",
        "Loaded ROI draft {0} for editing.": "已载入 ROI 草稿 {0}，可继续编辑。",
        "Confirmed ROI and created part {0}.": "已确认 ROI 并创建部位 {0}。",
        "Cancelled ROI draft {0}.": "已取消 ROI 草稿 {0}。",
        "This ROI is linked to a created part and cannot be cancelled here.": "这个 ROI 已关联到已创建部位，不能在这里取消。",
        "Select a part volume before editing part masks.": "请先选择一个部位体数据，再编辑部位 mask。",
        "Select a part volume before previewing masks.": "请先选择一个部位体数据，再预览 mask。",
        "Key-slice mask preview currently uses Z slices.": "当前关键切片 mask 预览先使用 Z 轴切片。",
        "Switch to part volume before drawing contours.": "请先选择部位体数据，再手绘轮廓。",
        "Contour drawing currently uses Z slices.": "当前手绘轮廓先使用 Z 轴切片。",
        "Drag on the current part slice to draw a closed contour.": "请在当前部位切片上拖拽，画出一个闭合轮廓。",
        "Contour saved at Z {0}.": "已在 Z={0} 保存轮廓。",
        "Contour needs at least 3 points.": "轮廓至少需要 3 个点。",
        "Deleted contour at Z {0}.": "已删除 Z={0} 的轮廓。",
        "No contour exists at Z {0}.": "Z={0} 没有可删除的轮廓。",
        "No previous key slice.": "没有上一张关键切片。",
        "No next key slice.": "没有下一张关键切片。",
        "Part mask preview quality: {0}": "部位 mask 预览质量：{0}",
        "Quality check passed": "质量检查通过",
        "Review warnings": "有提示，请复核",
        "Exported part package.\nManifest: {0}": "已导出部位包。\nManifest：{0}",
        "Exported part package.\nFolder: {0}\nManifest: {1}": "已导出部位包。\n文件夹：{0}\nManifest：{1}",
        "Define a part-local output axis and roll reference, then export a reviewable local reslice.": "定义部位内输出轴和 roll 参照点，然后导出可复核的局部重切片。",
        "Work in the 3D part preview first. Source Z is locked; copy it to create an editable output Z draft, then use the detail dialog only for precise MPR picking, roll reference, preview, and export.": "优先在三维部位预览中工作。原始 Z 轴是锁定参考；先复制它生成可编辑输出 Z 草稿，再把详情弹窗作为精确 MPR 点选、roll 参照、预览和导出的辅助工具。",
        "Local axis unavailable. Select a part volume.": "局部轴不可用。请先选择部位体数据。",
        "Source Z axis: locked reference": "原始 Z 轴：锁定参考",
        "3D overlay: on": "三维叠加显示：开启",
        "3D overlay: off": "三维叠加显示：关闭",
        "Draft output Z: none": "草稿输出 Z：无",
        "Draft output Z: {0}": "草稿输出 Z：{0}",
        "Saved reslice: none selected": "已保存重切片：未选中",
        "Saved reslice: {0}": "已保存重切片：{0}",
        "Open detail / MPR / export": "打开详情 / MPR / 导出",
        "Review proposals": "复核建议项",
        "Copied source Z axis as editable output axis.": "已从原始 Z 轴复制可编辑输出轴。",
        "Select a part volume before opening Local Axis Reslice.": "请先选择一个部位体数据，再打开局部轴重切片。",
        "Local Axis model and proposal tools": "局部轴模型与建议项工具",
        "Copy source Z axis": "复制原始 Z 轴",
        "Export reslice": "导出重切片",
        "Reslice ID": "重切片编号",
        "Template": "模板",
        "Origin z,y,x": "中心点 z,y,x",
        "Output axis start z,y,x": "输出轴起点 z,y,x",
        "Output axis end z,y,x": "输出轴终点 z,y,x",
        "Local axis draft": "局部轴草稿",
        "Roll point A role": "Roll 点 A 角色",
        "Roll point A z,y,x": "Roll 点 A z,y,x",
        "Roll point B role": "Roll 点 B 角色",
        "Roll point B z,y,x": "Roll 点 B z,y,x",
        "Output shape z,y,x": "输出尺寸 z,y,x",
        "Image": "图像",
        "Metadata": "元数据",
        "Output shape Z/Y/X": "输出尺寸 Z/Y/X",
        "Human confirmed": "人工已确认",
        "Usable for training": "可用于训练",
        "Hard case flags": "困难样本标记",
        "Source proposal": "来源建议项",
        "Model version": "模型版本",
        "Exported local axis reslice {0}.": "已导出局部轴重切片 {0}。",
        "Select a part volume before exporting a part package.": "请先选择一个部位体数据，再导出部位包。",
        "Created part {0} from bbox {1}.": "已按 bbox {1} 新建部位 {0}。",
        "Added rectangular key slice at Z {0}.": "已在 Z={0} 添加矩形关键切片。",
        "Preview mask generated from {0} key slice(s).": "已根据 {0} 个关键切片生成预览 mask。",
        "Accepted part mask.": "已接受部位 mask。",
        "Part volume is read-only here. Use part mask preview controls for extraction masks.": "当前部位体数据在这里按只读观察处理。请用部位 mask 预览控件生成提取 mask。",
        "Part volumes are not promoted to full-volume manual truth in this version.": "当前版本不会把部位体数据提升为整只体数据的人工真值。",
        "Part volumes do not use model draft handoff in this version.": "当前版本部位体数据不走模型草稿交接。",
        "Part volumes inherit the parent specimen material map. Switch to Full volume to edit materials.": "部位体数据继承父标本 material 表。需要编辑 material 时请切回整只体数据。",
        "Render color": "渲染颜色",
        "Amber": "琥珀黄",
        "Cyan": "青蓝",
        "White": "灰白",
        "Custom": "自定义",
        "Import TIF stack": "导入 TIF stack",
        "Import AMIRA directory": "导入 AMIRA 目录",
        "Start Center": "启动中心",
        "Ask Agent": "询问 Agent",
        "Training handoff": "训练交接",
        "Export train-ready volumes": "导出可训练体数据",
        "Backend parameters": "后端参数",
        "Dataset exchange": "训练数据交换",
        "Backend ID": "后端 ID",
        "Display name": "显示名称",
        "Python": "Python",
        "Export formats": "导出格式",
        "Prepare command": "Prepare 命令",
        "Train command": "训练命令",
        "Predict command": "预测命令",
        "Model manifest": "模型 manifest",
        "Save backend settings": "保存后端设置",
        "Prepare dataset": "准备训练数据",
        "Train backend": "训练后端",
        "Import prediction": "运行预测并导入草稿",
        "Import external label TIF to draft": "导入外部标签 TIF 到草稿",
        "Import External Label TIF": "导入外部标签 TIF",
        "Prediction ID:": "预测编号：",
        "Source model:": "来源模型：",
        "Imported external label TIF as model draft for specimen {0}. Report: {1}": "已为 specimen {0} 将外部标签 TIF 导入模型草稿。报告：{1}",
        "Please select a specimen with a working volume first.": "请先选择一个已有 working volume 的 specimen。",
        "Specimen status": "Specimen 状态",
        "Volume metadata": "体数据元数据",
        "No specimens in this TIF project": "当前 TIF 项目还没有 specimen",
        "Working volume missing": "缺少 working volume",
        "yes": "是",
        "no": "否",
        "Train": "训练",
        "train-ready": "可训练",
        "not train-ready": "不可训练",
        "Status": "状态",
        "Train-ready": "可训练",
        "Reasons": "原因",
        "Shape Z/Y/X": "Shape Z/Y/X",
        "dtype": "dtype",
        "spacing Z/Y/X": "spacing Z/Y/X",
        "modality": "成像类型",
        "Source TIF": "原始 TIF",
        "Working volume": "工作体数据",
        "Working edit": "当前编辑层",
        "Manual truth": "人工真值层",
        "Latest model draft": "最新模型草稿",
        "Show debug paths": "显示调试路径",
        "Import report": "导入报告",
        "TIF data import": "TIF 数据导入",
        "Please create or open a TIF project first.": "请先新建或打开一个 TIF 项目。",
        "Please create or open a TIF volume project first.": "请先新建或打开一个 TIF 体数据项目。",
        "Import TIF Stack": "导入 TIF stack",
        "Import AMIRA Directory": "导入 AMIRA 目录",
        "Specimen ID:": "Specimen 编号：",
        "Imported TIF stack for specimen {0}. Report: {1}": "已为 specimen {0} 导入 TIF stack。报告：{1}",
        "Importing TIF stack...": "正在导入 TIF stack...",
        "Reading TIF slices": "正在读取 TIF 切片",
        "Reading TIF volume": "正在读取 TIF 体数据",
        "Writing TIF sidecar": "正在写入 TIF sidecar",
        "Creating editable label layer": "正在创建可编辑标签层",
        "Saving TIF project": "正在保存 TIF 项目",
        "TIF import is already running.": "已有 TIF 导入正在运行。",
        "Imported AMIRA directory for specimen {0}. Report: {1}": "已为 specimen {0} 导入 AMIRA 目录。报告：{1}",
        "TIF training handoff": "TIF 训练交接",
        "Export train-ready TIF volumes": "导出可训练 TIF 体数据",
        "Exported {0} train-ready specimen(s).\nManifest: {1}": "已导出 {0} 个可训练 specimen。\nManifest：{1}",
        "Export failed: {0}": "导出失败：{0}",
        "TIF backend": "TIF 后端",
        "Backend settings saved.": "后端设置已保存。",
        "Running {0}...": "正在运行：{0}...",
        "Action finished: {0}\nRun: {1}": "动作完成：{0}\n运行目录：{1}",
        "Action failed: {0}": "动作失败：{0}",
        "No command configured for this backend action.": "这个后端动作还没有配置命令。",
        "No train-ready specimens are available.": "当前没有可训练 specimen。",
        "No specimen is available for prediction.": "当前没有可用于预测的 specimen。",
        "Copied latest model draft into working_edit.": "已将最新模型草稿复制到当前编辑层。",
        "No model draft is available for this specimen.": "当前 specimen 还没有模型草稿。",
        "Background material cannot be deleted.": "不能删除 background material。",
        "Material {0} is still used by a label volume.": "Material {0} 仍被 label volume 使用，不能删除。",
        "Delete material {0} ({1})?": "删除 material {0}（{1}）？",
        "Accept working edit": "确认当前编辑层",
        "Promote the current working_edit layer to manual_truth for training?": "将当前 working_edit 提升为可训练的 manual_truth？",
    }
}


def tt(text, lang):
    return TIF_TRANSLATIONS.get(lang, {}).get(text, text)


def _now_log_time():
    from datetime import datetime

    return datetime.now().strftime("%H:%M:%S")


class MaterialEditorDialog(QDialog):
    def __init__(self, material=None, next_id=1, parent=None, lang="en"):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tt("Material", self.lang))
        material = dict(material or {})
        self.id_spin = WheelSafeSpinBox()
        self.id_spin.setRange(0, 65535)
        self.id_spin.setValue(int(material.get("id", next_id)))
        self.id_spin.setEnabled(not material)
        self.name_edit = QLineEdit(str(material.get("name", "")))
        self.display_edit = QLineEdit(str(material.get("display_name", material.get("name", ""))))
        self.color_edit = QLineEdit(str(material.get("color", "#f94144")))
        self.trainable_check = QCheckBox(tt("Trainable", self.lang))
        self.trainable_check.setChecked(bool(material.get("trainable", self.id_spin.value() != 0)))
        self.color_button = QPushButton(tt("Choose color", self.lang))
        self.color_button.clicked.connect(self.choose_color)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow(tt("ID", self.lang), self.id_spin)
        form.addRow(tt("Name", self.lang), self.name_edit)
        form.addRow(tt("Display name", self.lang), self.display_edit)
        color_row = QHBoxLayout()
        color_row.addWidget(self.color_edit, 1)
        color_row.addWidget(self.color_button)
        form.addRow(tt("Color", self.lang), color_row)
        form.addRow("", self.trainable_check)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.color_edit.text()), self, "Material color")
        if color.isValid():
            self.color_edit.setText(color.name())

    def get_material(self):
        material_id = int(self.id_spin.value())
        name = self.name_edit.text().strip() or f"material_{material_id}"
        display_name = self.display_edit.text().strip() or name
        return {
            "id": material_id,
            "name": name,
            "display_name": display_name,
            "color": self.color_edit.text().strip(),
            "trainable": bool(self.trainable_check.isChecked() and material_id != 0),
            "source_name": display_name,
        }


class TifPartNameDialog(QDialog):
    def __init__(self, title, part_id="", display_name="", parent=None, lang="en", id_label="Part ID:"):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tt(title, self.lang))
        layout = QFormLayout(self)
        self.part_id_edit = QLineEdit(str(part_id or ""))
        self.display_name_edit = QLineEdit(str(display_name or part_id or ""))
        layout.addRow(tt(id_label, self.lang), self.part_id_edit)
        layout.addRow(tt("Display name:", self.lang), self.display_name_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self):
        part_id = self.part_id_edit.text().strip()
        display_name = self.display_name_edit.text().strip() or part_id
        return part_id, display_name


class WheelSafeComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class WheelSafeSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()

    def _tif_shortcut_parent(self):
        parent = self.parent()
        while parent is not None:
            if callable(getattr(parent, "_handle_slice_shortcut_key", None)):
                return parent
            parent = parent.parent()
        return None

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            parent = self._tif_shortcut_parent()
            handler = getattr(parent, "_handle_slice_shortcut_key", None)
            if callable(handler) and handler(event.key()):
                event.accept()
                return
        super().keyPressEvent(event)


class WheelSafeSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class TifSpecimenTree(QTreeWidget):
    """Tree widget with a tiny QListWidget-like surface for older tests/helpers."""

    def count(self):
        return self.topLevelItemCount()

    def item(self, row):
        return self.topLevelItem(row)

    def addItem(self, item):
        self.addTopLevelItem(item)

    def setCurrentRow(self, row):
        item = self.topLevelItem(row)
        if item is not None:
            child = item.child(0)
            self.setCurrentItem(child or item)


class TifSliceCanvas(QLabel):
    ZOOM_STEPS = (1.0, 1.25, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tifSliceCanvas")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(360, 280)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFrameShape(QFrame.NoFrame)
        self.setText("No TIF volume loaded")
        self._pixmap = None
        self._draw_rect = QRectF()
        self._zoom_index = 0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._panning = False
        self._last_pan_pos = None
        self._roi_drag_start = None
        self._roi_drag_current = None
        self._contour_drag_points = []
        self.workbench = None

    def set_slice_pixmap(self, pixmap, reset_view=False):
        self._pixmap = pixmap
        if reset_view:
            self.reset_view(refresh=False)
        self._refresh_scaled_pixmap()

    def reset_view(self, refresh=True):
        self._zoom_index = 0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._panning = False
        self._last_pan_pos = None
        if refresh:
            self._refresh_scaled_pixmap()

    def zoom_factor(self):
        return float(self.ZOOM_STEPS[max(0, min(self._zoom_index, len(self.ZOOM_STEPS) - 1))])

    def zoom_in(self):
        if self._pixmap is None or self._pixmap.isNull():
            return
        if self._zoom_index < len(self.ZOOM_STEPS) - 1:
            self._zoom_index += 1
            self._refresh_scaled_pixmap()

    def zoom_out(self):
        if self._pixmap is None or self._pixmap.isNull():
            return
        if self._zoom_index > 0:
            self._zoom_index -= 1
            if self._zoom_index == 0:
                self._pan_x = 0.0
                self._pan_y = 0.0
            self._refresh_scaled_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_scaled_pixmap()

    def _refresh_scaled_pixmap(self):
        if self._pixmap is None or self._pixmap.isNull():
            return
        view_w = max(1, int(self.width()))
        view_h = max(1, int(self.height()))
        base = self._pixmap.scaled(view_w, view_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        zoom = self.zoom_factor()
        target_w = max(1, int(round(base.width() * zoom)))
        target_h = max(1, int(round(base.height() * zoom)))
        zoomed = self._pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        target_w = max(1, int(zoomed.width()))
        target_h = max(1, int(zoomed.height()))
        max_pan_x = max(0.0, (target_w - view_w) / 2.0)
        max_pan_y = max(0.0, (target_h - view_h) / 2.0)
        self._pan_x = max(-max_pan_x, min(max_pan_x, self._pan_x)) if max_pan_x else 0.0
        self._pan_y = max(-max_pan_y, min(max_pan_y, self._pan_y)) if max_pan_y else 0.0
        x = (view_w - target_w) / 2.0 + self._pan_x
        y = (view_h - target_h) / 2.0 + self._pan_y
        self._draw_rect = QRectF(x, y, target_w, target_h)

        composed = QPixmap(view_w, view_h)
        composed.fill(QColor("#07090A"))
        painter = QPainter(composed)
        painter.drawPixmap(int(round(x)), int(round(y)), zoomed)
        self._draw_roi_overlays(painter)
        self._draw_contour_overlays(painter)
        self._draw_status_overlay(painter)
        painter.end()
        self.setPixmap(composed)

    def _image_rect_to_widget_rect(self, image_rect):
        if self._pixmap is None or self._pixmap.isNull() or self._draw_rect.isNull():
            return QRectF()
        x0, y0, x1, y1 = [float(value) for value in image_rect]
        width = max(1.0, float(self._pixmap.width()))
        height = max(1.0, float(self._pixmap.height()))
        left = self._draw_rect.x() + (x0 / width) * self._draw_rect.width()
        right = self._draw_rect.x() + (x1 / width) * self._draw_rect.width()
        top = self._draw_rect.y() + (y0 / height) * self._draw_rect.height()
        bottom = self._draw_rect.y() + (y1 / height) * self._draw_rect.height()
        return QRectF(min(left, right), min(top, bottom), abs(right - left), abs(bottom - top))

    def _draw_roi_overlays(self, painter):
        if self.workbench is None:
            return
        rects = []
        if callable(getattr(self.workbench, "current_roi_overlay_rects", None)):
            rects = self.workbench.current_roi_overlay_rects()
        painter.save()
        for entry in rects:
            if isinstance(entry, dict):
                image_rect = entry.get("rect", [])
                color = QColor(str(entry.get("color", "#FFD34D")))
                fill = QColor(color)
                fill.setAlpha(34)
            else:
                image_rect = entry
                color = QColor("#FFD34D")
                fill = QColor(255, 211, 77, 34)
            rect = self._image_rect_to_widget_rect(image_rect)
            if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
                continue
            painter.fillRect(rect, fill)
            pen = QPen(color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(rect)
        if self._roi_drag_start is not None and self._roi_drag_current is not None:
            start = self._roi_drag_start
            current = self._roi_drag_current
            rect = QRectF(
                min(start.x(), current.x()),
                min(start.y(), current.y()),
                abs(current.x() - start.x()),
                abs(current.y() - start.y()),
            )
            if rect.width() > 1 and rect.height() > 1:
                painter.fillRect(rect, QColor(103, 168, 184, 36))
                pen = QPen(QColor("#67A8B8"))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawRect(rect)
        painter.restore()

    def _image_point_to_widget_point(self, point):
        if self._pixmap is None or self._pixmap.isNull() or self._draw_rect.isNull():
            return None
        px, py = [float(value) for value in point]
        width = max(1.0, float(self._pixmap.width()))
        height = max(1.0, float(self._pixmap.height()))
        return (
            self._draw_rect.x() + (px / width) * self._draw_rect.width(),
            self._draw_rect.y() + (py / height) * self._draw_rect.height(),
        )

    def _draw_polyline(self, painter, points, color, closed=False, fill_alpha=0):
        if len(points) < 2:
            return
        widget_points = [self._image_point_to_widget_point(point) for point in points]
        widget_points = [point for point in widget_points if point is not None]
        if len(widget_points) < 2:
            return
        painter.save()
        polygon = None
        if closed and fill_alpha > 0 and len(widget_points) >= 3:
            polygon = QPolygonF([QPointF(float(x), float(y)) for x, y in widget_points])
            fill = QColor(color)
            fill.setAlpha(fill_alpha)
            painter.setBrush(fill)
        else:
            painter.setBrush(Qt.NoBrush)
        pen = QPen(QColor(color))
        pen.setWidth(2)
        painter.setPen(pen)
        if polygon is not None:
            painter.drawPolygon(polygon)
        for first, second in zip(widget_points, widget_points[1:]):
            painter.drawLine(int(round(first[0])), int(round(first[1])), int(round(second[0])), int(round(second[1])))
        if closed and len(widget_points) >= 3:
            painter.drawLine(
                int(round(widget_points[-1][0])),
                int(round(widget_points[-1][1])),
                int(round(widget_points[0][0])),
                int(round(widget_points[0][1])),
            )
        painter.restore()

    def _draw_contour_overlays(self, painter):
        if self.workbench is None:
            return
        contours = []
        if callable(getattr(self.workbench, "current_contour_overlay_polygons", None)):
            contours = self.workbench.current_contour_overlay_polygons()
        for contour in contours:
            if isinstance(contour, dict):
                self._draw_polyline(
                    painter,
                    contour.get("polygon", []),
                    str(contour.get("color", "#FF8C42")),
                    closed=True,
                    fill_alpha=int(contour.get("fill_alpha", 24)),
                )
        if self._contour_drag_points:
            self._draw_polyline(painter, self._contour_drag_points, "#FF8C42", closed=False, fill_alpha=0)

    def _draw_status_overlay(self, painter):
        if self.workbench is None:
            return
        text = self.workbench.canvas_status_text(self.zoom_factor())
        if not text:
            return
        painter.save()
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(text)
        rect = QRectF(10, 10, text_w + 16, metrics.height() + 8)
        painter.fillRect(rect, QColor(7, 9, 10, 190))
        painter.setPen(QColor("#DCE4E8"))
        painter.drawText(rect.adjusted(8, 4, -8, -4), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()

    def widget_to_image_pixel(self, x, y):
        if self._pixmap is None or self._pixmap.isNull() or self._draw_rect.isNull():
            return None
        if not self._draw_rect.contains(float(x), float(y)):
            return None
        rel_x = (float(x) - self._draw_rect.x()) / max(1.0, self._draw_rect.width())
        rel_y = (float(y) - self._draw_rect.y()) / max(1.0, self._draw_rect.height())
        px = int(rel_x * self._pixmap.width())
        py = int(rel_y * self._pixmap.height())
        return (
            max(0, min(int(self._pixmap.width()) - 1, px)),
            max(0, min(int(self._pixmap.height()) - 1, py)),
        )

    def wheelEvent(self, event):
        if self.workbench is None:
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        self.setFocus(Qt.MouseFocusReason)
        self.workbench.move_slice(-1 if delta > 0 else 1)
        event.accept()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Left:
            if self.workbench is not None:
                self.workbench.move_slice(-1)
            event.accept()
            return
        if key == Qt.Key_Right:
            if self.workbench is not None:
                self.workbench.move_slice(1)
            event.accept()
            return
        if key == Qt.Key_Up:
            self.zoom_in()
            event.accept()
            return
        if key == Qt.Key_Down:
            self.zoom_out()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        self.setFocus(Qt.MouseFocusReason)
        if (
            self.workbench is not None
            and event.button() == Qt.LeftButton
            and callable(getattr(self.workbench, "is_part_roi_draw_mode", None))
            and self.workbench.is_part_roi_draw_mode()
        ):
            self._roi_drag_start = event.position()
            self._roi_drag_current = event.position()
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if (
            self.workbench is not None
            and event.button() == Qt.LeftButton
            and callable(getattr(self.workbench, "is_part_contour_draw_mode", None))
            and self.workbench.is_part_contour_draw_mode()
        ):
            pixel = self.widget_to_image_pixel(event.position().x(), event.position().y())
            self._contour_drag_points = [list(pixel)] if pixel is not None else []
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if event.button() == Qt.RightButton and self.zoom_factor() > 1.0:
            self._panning = True
            self._last_pan_pos = event.position()
            event.accept()
            return
        if self.workbench is not None and event.button() == Qt.LeftButton:
            self.workbench.paint_at_widget_position(event.position().x(), event.position().y(), erase=bool(event.modifiers() & Qt.ControlModifier))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._roi_drag_start is not None and event.buttons() & Qt.LeftButton:
            self._roi_drag_current = event.position()
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if self._contour_drag_points and event.buttons() & Qt.LeftButton:
            pixel = self.widget_to_image_pixel(event.position().x(), event.position().y())
            if pixel is not None:
                if not self._contour_drag_points or self._contour_drag_points[-1] != list(pixel):
                    self._contour_drag_points.append(list(pixel))
                    self._refresh_scaled_pixmap()
            event.accept()
            return
        if self._panning and event.buttons() & Qt.RightButton and self._last_pan_pos is not None:
            current = event.position()
            self._pan_x += current.x() - self._last_pan_pos.x()
            self._pan_y += current.y() - self._last_pan_pos.y()
            self._last_pan_pos = current
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if self.workbench is not None and event.buttons() & Qt.LeftButton:
            self.workbench.paint_at_widget_position(event.position().x(), event.position().y(), erase=bool(event.modifiers() & Qt.ControlModifier))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._roi_drag_start is not None:
            start = self._roi_drag_start
            end = event.position()
            self._roi_drag_start = None
            self._roi_drag_current = None
            if self.workbench is not None:
                self.workbench.finish_part_roi_drag(start.x(), start.y(), end.x(), end.y())
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if event.button() == Qt.LeftButton and self._contour_drag_points:
            points = list(self._contour_drag_points)
            self._contour_drag_points = []
            if self.workbench is not None:
                self.workbench.finish_part_contour_drag(points)
            self._refresh_scaled_pixmap()
            event.accept()
            return
        if event.button() == Qt.RightButton and self._panning:
            self._panning = False
            self._last_pan_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.workbench is not None and event.button() == Qt.LeftButton:
            if callable(getattr(self.workbench, "open_roi_at_widget_position", None)):
                if self.workbench.open_roi_at_widget_position(event.position().x(), event.position().y()):
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)


class TifVolumeCanvas(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tifVolumeCanvas")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(360, 280)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFrameShape(QFrame.NoFrame)
        self.setText("No TIF volume loaded")
        self.workbench = None
        self._mouse_mode = ""
        self._last_drag_pos = None
        self._axis_overlays = []

    def set_axis_overlays(self, overlays):
        self._axis_overlays = list(overlays or [])
        self.update()

    def set_volume_pixmap(self, pixmap):
        if pixmap is None or pixmap.isNull():
            self.clear()
            return
        scaled = pixmap.scaled(
            max(1, int(self.width())),
            max(1, int(self.height())),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        composed = QPixmap(max(1, int(self.width())), max(1, int(self.height())))
        composed.fill(QColor("#07090A"))
        painter = QPainter(composed)
        x = int(round((composed.width() - scaled.width()) / 2.0))
        y = int(round((composed.height() - scaled.height()) / 2.0))
        painter.drawPixmap(x, y, scaled)
        self._draw_status_overlay(painter)
        self._draw_axis_overlays(painter)
        painter.end()
        self.setPixmap(composed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.workbench is not None:
            self.workbench.schedule_volume_preview_render()

    def _draw_status_overlay(self, painter):
        if self.workbench is None:
            return
        text = self.workbench.volume_status_text()
        if not text:
            return
        painter.save()
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(text)
        rect = QRectF(10, 10, text_w + 16, metrics.height() + 8)
        painter.fillRect(rect, QColor(7, 9, 10, 190))
        painter.setPen(QColor("#DCE4E8"))
        painter.drawText(rect.adjusted(8, 4, -8, -4), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()

    def _draw_axis_overlays(self, painter):
        if not self._axis_overlays:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        for overlay in self._axis_overlays:
            start = overlay.get("start_xy")
            end = overlay.get("end_xy")
            if not start or not end:
                continue
            color = QColor(str(overlay.get("color") or "#FFB84D"))
            painter.setPen(QPen(color, int(overlay.get("width", 2))))
            x0, y0 = float(start[0]), float(start[1])
            x1, y1 = float(end[0]), float(end[1])
            painter.drawLine(int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1)))
            painter.drawEllipse(int(round(x0 - 4)), int(round(y0 - 4)), 8, 8)
            painter.drawEllipse(int(round(x1 - 4)), int(round(y1 - 4)), 8, 8)
            label = str(overlay.get("label") or "")
            if label:
                painter.drawText(int(round(x1 + 6)), int(round(y1 - 6)), label)
        painter.restore()

    def mousePressEvent(self, event):
        self.setFocus(Qt.MouseFocusReason)
        if self.workbench is not None and event.button() in (Qt.LeftButton, Qt.RightButton):
            self._mouse_mode = "rotate" if event.button() == Qt.LeftButton else "pan"
            self._last_drag_pos = event.position()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        buttons = event.buttons()
        active = (
            (self._mouse_mode == "rotate" and buttons & Qt.LeftButton)
            or (self._mouse_mode == "pan" and buttons & Qt.RightButton)
        )
        if self.workbench is not None and active and self._last_drag_pos is not None:
            current = event.position()
            dx = current.x() - self._last_drag_pos.x()
            dy = current.y() - self._last_drag_pos.y()
            self._last_drag_pos = current
            if self._mouse_mode == "pan":
                self.workbench.pan_volume_preview(dx, dy)
            else:
                self.workbench.rotate_volume_preview(dx, dy)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.LeftButton, Qt.RightButton) and self._mouse_mode:
            self._mouse_mode = ""
            self._last_drag_pos = None
            if self.workbench is not None:
                self.workbench.finish_volume_interaction_debounced()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if self.workbench is None:
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        self.workbench.zoom_volume_preview(1 if delta > 0 else -1)
        event.accept()


def create_tif_volume_canvas(parent=None):
    gpu_flag = os.environ.get("TAXAMASK_TIF_GPU_VOLUME_PREVIEW", "").strip().lower()
    if gpu_flag in {"0", "false", "no", "off"}:
        return TifVolumeCanvas(parent), "cpu", "GPU volume preview disabled by TAXAMASK_TIF_GPU_VOLUME_PREVIEW."
    if gpu_volume_offscreen_available() and TifGpuVolumeOffscreenWidget is not None:
        try:
            canvas = TifGpuVolumeOffscreenWidget(parent)
            if hasattr(canvas, "initialize_renderer"):
                canvas.initialize_renderer(emit_info=False)
            canvas.setProperty("tifVolumeRenderer", "gpu-offscreen")
            return canvas, "gpu", ""
        except Exception as exc:
            return TifVolumeCanvas(parent), "cpu", str(exc)
    legacy_flag = os.environ.get("TAXAMASK_TIF_EMBEDDED_QOPENGLWIDGET", "").strip().lower()
    if legacy_flag in {"1", "true", "yes", "on"} and gpu_volume_canvas_available() and TifGpuVolumeCanvas is not None:
        try:
            canvas = TifGpuVolumeCanvas(parent)
            canvas.setProperty("tifVolumeRenderer", "gpu-embedded")
            return canvas, "gpu", ""
        except Exception as exc:
            return TifVolumeCanvas(parent), "cpu", str(exc)
    return TifVolumeCanvas(parent), "cpu", gpu_volume_unavailable_reason()


class TifImportWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, project_manager, tif_path, specimen_id):
        super().__init__()
        self.project_manager = project_manager
        self.tif_path = tif_path
        self.specimen_id = specimen_id

    def run(self):
        try:
            result = import_tif_stack(
                self.project_manager,
                self.tif_path,
                self.specimen_id,
                copy_source=False,
                create_working_edit=False,
                progress_callback=self.progress.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class TifWorkbenchWidget(QWidget):
    start_center_requested = Signal()
    agent_requested = Signal(dict)

    def __init__(self, project_manager=None, lang="zh", parent=None, config_manager=None):
        super().__init__(parent)
        self.setObjectName("tifWorkbenchRoot")
        self.project = project_manager or TifProjectManager()
        self.lang = lang
        self.config_manager = config_manager
        config = self.config_manager.get("tif_backend", DEFAULT_TIF_BACKEND_CONFIG) if self.config_manager is not None else DEFAULT_TIF_BACKEND_CONFIG
        self.backend_config = sanitize_tif_backend_config(config)
        self.current_specimen_id = ""
        self.current_volume_scope = "full"
        self.current_part_id = ""
        self.current_part = None
        self.current_reslice_id = ""
        self.local_axis_draft = None
        self.part_preview_mask = None
        self.part_roi_draw_mode = False
        self.part_contour_draw_mode = False
        self.active_part_roi_id = ""
        self.image_volume = None
        self.label_volume = None
        self.material_map = {}
        self.material_colors = {}
        self.current_material_id = 0
        self.edit_volume = None
        self.working_edit_dirty = False
        self._dirty_edit_slices = set()
        self._loading_specimen = False
        self._saving_working_edit = False
        self._tif_import_thread = None
        self._tif_import_worker = None
        self._tif_import_progress = None
        self._tif_import_specimen_id = ""
        self.undo_stack = []
        self.redo_stack = []
        self.slice_axis = "z"
        self._slice_positions = {"z": 0, "y": 0, "x": 0}
        self.display_mode = "slice"
        self._volume_preview_cache = {}
        self._volume_preview = None
        self._volume_preview_source_shape = ()
        self._volume_render_mode = "still"
        self._volume_last_stats = {}
        self._volume_canvas_renderer = "cpu"
        self._volume_renderer_warning = ""
        self._volume_gl_renderer_info = ""
        self._volume_render_scheduled = False
        self._volume_interaction_render_scheduled = False
        self._volume_interaction_render_pending = False
        self._volume_interaction_render_interval_ms = 16
        self._handling_gpu_volume_failure = False
        self._volume_yaw = -35.0
        self._volume_pitch = 20.0
        self._volume_zoom = 1.0
        self._volume_pan_x = 0.0
        self._volume_pan_y = 0.0
        self._volume_mask_preview_cache = {}
        self._volume_masked_preview_cache = {}
        self._volume_clarity_mode = False

        self.specimen_list = TifSpecimenTree()
        self.specimen_list.setObjectName("tifSpecimenList")
        self.specimen_list.setHeaderHidden(True)
        self.specimen_list.currentItemChanged.connect(self._on_specimen_tree_selected)

        self.canvas = TifSliceCanvas()
        self.canvas.workbench = self
        self.volume_canvas = TifVolumeCanvas()
        self.volume_canvas.workbench = self
        self.volume_canvas.setProperty("tifVolumeRenderer", "placeholder")
        self._volume_canvas_created = False
        if hasattr(self, "volume_render_status_label"):
            self.volume_render_status_label.setVisible(False)
        self._reset_canvas_view_on_next_render = False
        self.display_mode_combo = WheelSafeComboBox()
        self.display_mode_combo.setObjectName("tifDisplayModeCombo")
        self._populate_display_mode_combo()
        self.display_mode_combo.currentIndexChanged.connect(self.on_display_mode_changed)
        self.slice_slider = WheelSafeSlider(Qt.Horizontal)
        self.slice_slider.setRange(0, 0)
        self.slice_slider.valueChanged.connect(self.on_slice_slider_changed)
        self.slice_prefix_label = QLabel("Slice")
        self.slice_label = QLabel("0 / 0")
        self.slice_axis_combo = WheelSafeComboBox()
        self.slice_axis_combo.setObjectName("tifSliceAxisCombo")
        self._populate_slice_axis_combo()
        self.slice_axis_combo.currentIndexChanged.connect(self.on_slice_axis_changed)

        self.label_role_combo = WheelSafeComboBox()
        self._populate_label_role_combo()
        self.label_role_combo.currentIndexChanged.connect(self._reload_label_volume)
        self.label_role_help_label = QLabel("")
        self.label_role_help_label.setObjectName("tifLayerHelpText")
        self.label_role_help_label.setWordWrap(True)

        self.opacity_slider = WheelSafeSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(45)
        self.opacity_slider.valueChanged.connect(self.render_current_slice)
        self.brightness_slider = WheelSafeSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self.render_current_slice)
        self.contrast_slider = WheelSafeSlider(Qt.Horizontal)
        self.contrast_slider.setRange(1, 30)
        self.contrast_slider.setValue(10)
        self.contrast_slider.valueChanged.connect(self.render_current_slice)
        self.volume_cutoff_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_cutoff_slider.setObjectName("tifVolumeCutoffSlider")
        self.volume_cutoff_slider.setRange(0, 95)
        self.volume_cutoff_slider.setValue(35)
        self.volume_cutoff_slider.valueChanged.connect(self.render_volume_preview)
        self.volume_projection_combo = WheelSafeComboBox()
        self.volume_projection_combo.setObjectName("tifVolumeProjectionCombo")
        self.volume_projection_combo.currentIndexChanged.connect(self._on_volume_projection_changed)
        self.volume_quality_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_quality_slider.setObjectName("tifVolumeQualitySlider")
        self.volume_quality_slider.setRange(128, GPU_VOLUME_MAX_TEXTURE_DIM)
        self.volume_quality_slider.setValue(1024)
        self.volume_quality_slider.valueChanged.connect(self._refresh_volume_preview)
        self.volume_sample_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_sample_slider.setObjectName("tifVolumeSampleSlider")
        self.volume_sample_slider.setRange(256, GPU_VOLUME_MAX_RAY_STEPS)
        self.volume_sample_slider.setValue(1536)
        self.volume_sample_slider.valueChanged.connect(self.render_volume_preview)
        self.volume_clarity_check = QCheckBox("Clarity mode")
        self.volume_clarity_check.setObjectName("tifVolumeClarityCheck")
        self.volume_clarity_check.toggled.connect(self._on_volume_clarity_toggled)
        self.volume_roi_detail_check = QCheckBox("ROI high detail")
        self.volume_roi_detail_check.setObjectName("tifVolumeRoiDetailCheck")
        self.volume_roi_detail_check.setChecked(True)
        self.volume_roi_detail_check.toggled.connect(self.render_volume_preview)
        self.volume_roi_scale_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_roi_scale_slider.setObjectName("tifVolumeRoiScaleSlider")
        self.volume_roi_scale_slider.setRange(100, 300)
        self.volume_roi_scale_slider.setValue(200)
        self.volume_roi_scale_slider.valueChanged.connect(self.render_volume_preview)
        self.volume_inside_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_inside_slider.setObjectName("tifVolumeInsideSlider")
        self.volume_inside_slider.setRange(0, 160)
        self.volume_inside_slider.setValue(0)
        self.volume_inside_slider.valueChanged.connect(self.render_volume_preview)
        self.volume_clip_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_clip_slider.setObjectName("tifVolumeClipSlider")
        self.volume_clip_slider.setRange(0, 92)
        self.volume_clip_slider.setValue(0)
        self.volume_clip_slider.valueChanged.connect(self.render_volume_preview)
        self.volume_tint_combo = WheelSafeComboBox()
        self.volume_tint_combo.setObjectName("tifVolumeTintCombo")
        self._populate_volume_tint_combo()
        self.volume_tint_combo.currentIndexChanged.connect(self._on_volume_tint_changed)
        self.btn_volume_custom_color = QPushButton("Choose color")
        self.btn_volume_custom_color.setObjectName("tifVolumeCustomColorButton")
        self.btn_volume_custom_color.clicked.connect(self.choose_volume_custom_color)
        self.volume_transfer_opacity_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_transfer_opacity_slider.setObjectName("tifVolumeTransferOpacitySlider")
        self.volume_transfer_opacity_slider.setRange(25, 140)
        self.volume_transfer_opacity_slider.setValue(100)
        self.volume_transfer_opacity_slider.valueChanged.connect(self._on_volume_transfer_opacity_changed)
        self.volume_enhancement_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_enhancement_slider.setObjectName("tifVolumeEnhancementSlider")
        self.volume_enhancement_slider.setRange(0, 100)
        self.volume_enhancement_slider.setValue(35)
        self.volume_enhancement_slider.valueChanged.connect(self._on_volume_display_enhancement_changed)
        self.volume_tone_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_tone_slider.setObjectName("tifVolumeToneSlider")
        self.volume_tone_slider.setRange(70, 130)
        self.volume_tone_slider.setValue(100)
        self.volume_tone_slider.valueChanged.connect(self._on_volume_display_enhancement_changed)
        self.volume_surface_refine_check = QCheckBox("Surface refine")
        self.volume_surface_refine_check.setObjectName("tifVolumeSurfaceRefineCheck")
        self.volume_surface_refine_check.setChecked(True)
        self.volume_surface_refine_check.toggled.connect(self._on_volume_display_enhancement_changed)
        self.volume_clip_plane_check = QCheckBox("Clip plane")
        self.volume_clip_plane_check.setObjectName("tifVolumeClipPlaneCheck")
        self.volume_clip_plane_check.setChecked(False)
        self.volume_clip_plane_check.toggled.connect(self._on_volume_clip_plane_changed)
        self.volume_local_axes_check = QCheckBox("Show local axes")
        self.volume_local_axes_check.setObjectName("tifVolumeLocalAxesCheck")
        self.volume_local_axes_check.setChecked(False)
        self.volume_local_axes_check.toggled.connect(self.render_volume_preview)
        self.volume_local_axes_check.toggled.connect(self._update_local_axis_summary)
        self.volume_clip_plane_depth_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_clip_plane_depth_slider.setObjectName("tifVolumeClipPlaneDepthSlider")
        self.volume_clip_plane_depth_slider.setRange(0, 100)
        self.volume_clip_plane_depth_slider.setValue(50)
        self.volume_clip_plane_depth_slider.valueChanged.connect(self.render_volume_preview)
        self.volume_mask_combo = WheelSafeComboBox()
        self.volume_mask_combo.setObjectName("tifVolumeMaskCombo")
        self._populate_volume_mask_combo()
        self.volume_mask_combo.currentIndexChanged.connect(self._on_volume_mask_changed)
        self.volume_mask_opacity_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_mask_opacity_slider.setObjectName("tifVolumeMaskOpacitySlider")
        self.volume_mask_opacity_slider.setRange(0, 100)
        self.volume_mask_opacity_slider.setValue(45)
        self.volume_mask_opacity_slider.valueChanged.connect(self.render_volume_preview)
        self.btn_reset_volume_view = QPushButton("Reset 3D view")
        self.btn_reset_volume_view.setObjectName("tifResetVolumeViewButton")
        self.btn_reset_volume_view.clicked.connect(self.reset_volume_view)
        self.volume_render_status_label = QLabel("")
        self.volume_render_status_label.setObjectName("tifVolumeRenderStatus")
        self.volume_render_status_label.setWordWrap(True)
        self.volume_render_status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.volume_render_status_label.setVisible(False)
        self.local_axis_summary_label = QLabel("")
        self.local_axis_summary_label.setObjectName("tifLocalAxisSummaryText")
        self.local_axis_summary_label.setWordWrap(True)
        self.local_axis_summary_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        self.status_label = QLabel("")
        self.status_label.setObjectName("tifStatusText")
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.metadata_label = QLabel("")
        self.metadata_label.setObjectName("tifMetadataText")
        self.metadata_label.setWordWrap(True)
        self.metadata_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.metadata_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.show_debug_paths_check = QCheckBox("Show debug paths")
        self.show_debug_paths_check.setObjectName("tifShowDebugPathsCheck")
        self.show_debug_paths_check.setChecked(False)
        self.show_debug_paths_check.toggled.connect(self._on_show_debug_paths_toggled)
        self.material_table = QTableWidget(0, 4)
        self.material_table.setObjectName("tifMaterialTable")
        self.material_table.setMinimumHeight(150)
        self.material_table.setMaximumHeight(240)
        self.material_table.setHorizontalHeaderLabels(["ID", "Name", "Train", "Color"])
        self.material_table.verticalHeader().setVisible(False)
        self.material_table.setShowGrid(False)
        self.material_table.setAlternatingRowColors(True)
        self.material_table.horizontalHeader().setStretchLastSection(True)
        self.material_table.itemSelectionChanged.connect(self._on_material_selected)
        self.btn_add_material = QPushButton("Add material")
        self.btn_add_material.clicked.connect(self.add_material)
        self.btn_edit_material = QPushButton("Edit material")
        self.btn_edit_material.clicked.connect(self.edit_selected_material)
        self.btn_delete_material = QPushButton("Delete material")
        self.btn_delete_material.clicked.connect(self.delete_selected_material)

        self.brush_size_slider = WheelSafeSlider(Qt.Horizontal)
        self.brush_size_slider.setRange(1, 80)
        self.brush_size_slider.setValue(8)
        self.btn_undo = QPushButton("Undo")
        self.btn_undo.clicked.connect(self.undo)
        self.btn_redo = QPushButton("Redo")
        self.btn_redo.clicked.connect(self.redo)
        self.btn_save_edit = QPushButton("Save working edit")
        self.btn_save_edit.clicked.connect(lambda: self.save_working_edit())
        self.auto_save_check = QCheckBox("Auto-save edit")
        self.auto_save_check.setObjectName("tifAutoSaveEditCheck")
        self.auto_save_check.setChecked(True)
        self.auto_save_check.toggled.connect(self._on_auto_save_toggled)
        self.btn_promote = QPushButton("Accept as manual truth")
        self.btn_promote.clicked.connect(self.promote_working_edit)
        self.btn_copy_draft = QPushButton("Copy model draft to working edit")
        self.btn_copy_draft.clicked.connect(self.copy_latest_model_draft_to_working_edit)
        self.btn_import_tif = QPushButton("Import TIF stack")
        self.btn_import_tif.setObjectName("tifImportStackButton")
        self.btn_import_tif.clicked.connect(self.import_tif_stack_dialog)
        self.btn_import_amira = QPushButton("Import AMIRA directory")
        self.btn_import_amira.setObjectName("tifImportAmiraButton")
        self.btn_import_amira.clicked.connect(self.import_amira_directory_dialog)
        self.part_bbox_edit = QLineEdit()
        self.part_bbox_edit.setObjectName("tifPartBboxEdit")
        self.part_bbox_edit.setPlaceholderText("z0,z1,y0,y1,x0,x1")
        self.part_bbox_edit.textChanged.connect(self.render_current_slice)
        self.btn_part_default_bbox = QPushButton("Use center ROI")
        self.btn_part_default_bbox.setObjectName("tifPartDefaultBboxButton")
        self.btn_part_default_bbox.clicked.connect(self.fill_default_part_bbox)
        self.btn_part_draw_roi = QPushButton("Draw ROI")
        self.btn_part_draw_roi.setObjectName("tifPartDrawRoiButton")
        self.btn_part_draw_roi.setCheckable(True)
        self.btn_part_draw_roi.toggled.connect(self.set_part_roi_draw_mode)
        self.btn_save_part_roi = QPushButton("Save ROI draft")
        self.btn_save_part_roi.setObjectName("tifSavePartRoiButton")
        self.btn_save_part_roi.clicked.connect(self.save_part_roi_draft)
        self.btn_confirm_part_roi = QPushButton("Confirm ROI")
        self.btn_confirm_part_roi.setObjectName("tifConfirmPartRoiButton")
        self.btn_confirm_part_roi.clicked.connect(self.confirm_part_roi_to_part)
        self.btn_cancel_part_roi = QPushButton("Cancel ROI")
        self.btn_cancel_part_roi.setObjectName("tifCancelPartRoiButton")
        self.btn_cancel_part_roi.clicked.connect(self.cancel_part_roi_draft)
        self.btn_create_part = QPushButton("Create part")
        self.btn_create_part.setObjectName("tifCreatePartButton")
        self.btn_create_part.clicked.connect(self.create_part_from_bbox_dialog)
        self.btn_add_rect_keyframe = QPushButton("Add rectangular key slice")
        self.btn_add_rect_keyframe.setObjectName("tifAddRectKeyframeButton")
        self.btn_add_rect_keyframe.clicked.connect(self.add_current_rect_keyframe)
        self.btn_draw_part_contour = QPushButton("Draw contour")
        self.btn_draw_part_contour.setObjectName("tifDrawPartContourButton")
        self.btn_draw_part_contour.setCheckable(True)
        self.btn_draw_part_contour.toggled.connect(self.set_part_contour_draw_mode)
        self.btn_delete_part_contour = QPushButton("Delete key slice")
        self.btn_delete_part_contour.setObjectName("tifDeletePartContourButton")
        self.btn_delete_part_contour.clicked.connect(self.delete_current_part_keyframe)
        self.btn_prev_key_slice = QPushButton("Previous key slice")
        self.btn_prev_key_slice.setObjectName("tifPrevPartKeySliceButton")
        self.btn_prev_key_slice.clicked.connect(lambda: self.jump_part_keyframe("previous"))
        self.btn_next_key_slice = QPushButton("Next key slice")
        self.btn_next_key_slice.setObjectName("tifNextPartKeySliceButton")
        self.btn_next_key_slice.clicked.connect(lambda: self.jump_part_keyframe("next"))
        self.btn_preview_part_mask = QPushButton("Preview auto fill")
        self.btn_preview_part_mask.setObjectName("tifPreviewPartMaskButton")
        self.btn_preview_part_mask.clicked.connect(self.preview_part_mask_from_keyframes)
        self.btn_accept_part_mask = QPushButton("Accept part mask")
        self.btn_accept_part_mask.setObjectName("tifAcceptPartMaskButton")
        self.btn_accept_part_mask.clicked.connect(self.accept_part_mask_preview)
        self.btn_clear_part_preview = QPushButton("Clear preview")
        self.btn_clear_part_preview.setObjectName("tifClearPartPreviewButton")
        self.btn_clear_part_preview.clicked.connect(self.clear_part_mask_preview)
        self.btn_local_axis_reslice = QPushButton("Open detail / MPR / export")
        self.btn_local_axis_reslice.setObjectName("tifLocalAxisResliceButton")
        self.btn_local_axis_reslice.clicked.connect(self.open_local_axis_reslice_dialog)
        self.btn_copy_source_z_axis = QPushButton("Copy source Z axis")
        self.btn_copy_source_z_axis.setObjectName("tifCopySourceZAxisButton")
        self.btn_copy_source_z_axis.clicked.connect(self.copy_source_z_axis_to_local_axis_draft)
        self.btn_local_axis_queue = QPushButton("Review Local Axis Queue")
        self.btn_local_axis_queue.setObjectName("tifLocalAxisQueueButton")
        self.btn_local_axis_queue.clicked.connect(self.open_local_axis_review_queue)
        self.btn_local_axis_models = QPushButton("Local Axis Models")
        self.btn_local_axis_models.setObjectName("tifLocalAxisModelsButton")
        self.btn_local_axis_models.clicked.connect(self.open_local_axis_model_dialog)
        self.btn_export_part_package = QPushButton("Export part package")
        self.btn_export_part_package.setObjectName("tifExportPartPackageButton")
        self.btn_export_part_package.clicked.connect(self.export_current_part_package)
        self.btn_delete_part_volume = QPushButton("Delete part volume")
        self.btn_delete_part_volume.setObjectName("tifDeletePartVolumeButton")
        self.btn_delete_part_volume.clicked.connect(self.delete_current_part_volume)
        self.btn_export_training = QPushButton("Export train-ready volumes")
        self.btn_export_training.setObjectName("tifExportTrainingButton")
        self.btn_export_training.clicked.connect(self.export_training_dataset)
        self.backend_id_edit = QLineEdit()
        self.backend_id_edit.setObjectName("tifBackendIdEdit")
        self.backend_display_edit = QLineEdit()
        self.backend_python_edit = QLineEdit()
        self.backend_formats_edit = QLineEdit()
        self.backend_prepare_edit = QLineEdit()
        self.backend_train_edit = QLineEdit()
        self.backend_predict_edit = QLineEdit()
        self.backend_manifest_edit = QLineEdit()
        self.btn_save_backend = QPushButton("Save backend settings")
        self.btn_save_backend.setObjectName("tifSaveBackendButton")
        self.btn_save_backend.clicked.connect(self.save_backend_settings)
        self.btn_prepare_dataset = QPushButton("Prepare dataset")
        self.btn_prepare_dataset.setObjectName("tifPrepareDatasetButton")
        self.btn_prepare_dataset.clicked.connect(lambda: self.run_backend_action("prepare_dataset"))
        self.btn_train_backend = QPushButton("Train backend")
        self.btn_train_backend.setObjectName("tifTrainBackendButton")
        self.btn_train_backend.clicked.connect(lambda: self.run_backend_action("train"))
        self.btn_import_prediction = QPushButton("Import prediction")
        self.btn_import_prediction.setObjectName("tifImportPredictionButton")
        self.btn_import_prediction.clicked.connect(lambda: self.run_backend_action("predict"))
        self.btn_import_external_prediction_tif = QPushButton("Import external label TIF to draft")
        self.btn_import_external_prediction_tif.setObjectName("tifImportExternalPredictionTifButton")
        self.btn_import_external_prediction_tif.clicked.connect(self.import_external_prediction_tif_dialog)
        self.btn_start_center = QPushButton("Start Center")
        self.btn_start_center.setObjectName("tifStartCenterButton")
        self.btn_start_center.clicked.connect(self.start_center_requested.emit)
        self.btn_ask_agent = QPushButton("Ask Agent")
        self.btn_ask_agent.setObjectName("tifAskAgentButton")
        self.btn_ask_agent.clicked.connect(lambda: self.agent_requested.emit(self.get_agent_context()))
        self.training_status_label = QLabel("")
        self.training_status_label.setObjectName("tifTrainingStatusText")
        self.training_status_label.setWordWrap(True)
        self.training_status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.log_console = QTextEdit()
        self.log_console.setObjectName("tifLogConsole")
        self.log_console.setReadOnly(True)
        self.log_console.setMinimumHeight(90)
        self.log_console.setMaximumHeight(140)
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.undo)
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.shortcut_redo.activated.connect(self.redo)
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.setSingleShot(True)
        self.auto_save_timer.setInterval(1200)
        self.auto_save_timer.timeout.connect(lambda: self.save_working_edit(show_message=True, reason="auto_save"))
        self.volume_still_timer = QTimer(self)
        self.volume_still_timer.setSingleShot(True)
        self.volume_still_timer.setInterval(220)
        self.volume_still_timer.timeout.connect(self._finish_volume_interaction)

        self._apply_button_roles()
        self._build_layout()
        self._apply_soft_style()
        self._load_backend_config_into_ui()
        self._update_texts()
        self._sync_mode_sections()
        self.refresh_project()

    def _style_button(self, button, role="secondary", full_width=False):
        button.setProperty("tifRole", role)
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumHeight(34)
        if full_width:
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _apply_button_roles(self):
        primary_buttons = [
            self.btn_import_tif,
            self.btn_import_amira,
            self.btn_export_training,
            self.btn_prepare_dataset,
            self.btn_train_backend,
            self.btn_import_prediction,
            self.btn_import_external_prediction_tif,
            self.btn_local_axis_models,
            self.btn_promote,
            self.btn_create_part,
            self.btn_preview_part_mask,
            self.btn_accept_part_mask,
            self.btn_local_axis_reslice,
            self.btn_local_axis_queue,
            self.btn_export_part_package,
        ]
        secondary_buttons = [
            self.btn_start_center,
            self.btn_ask_agent,
            self.btn_undo,
            self.btn_redo,
            self.btn_save_edit,
            self.btn_reset_volume_view,
            self.btn_volume_custom_color,
            self.btn_copy_draft,
            self.btn_copy_source_z_axis,
            self.btn_add_material,
            self.btn_edit_material,
            self.btn_save_backend,
            self.btn_part_default_bbox,
            self.btn_part_draw_roi,
            self.btn_save_part_roi,
            self.btn_add_rect_keyframe,
            self.btn_draw_part_contour,
            self.btn_prev_key_slice,
            self.btn_next_key_slice,
            self.btn_clear_part_preview,
        ]
        for button in primary_buttons:
            self._style_button(button, "primary", full_width=True)
        for button in secondary_buttons:
            self._style_button(button, "secondary", full_width=True)
        self._style_button(self.btn_delete_material, "danger", full_width=True)
        self._style_button(self.btn_confirm_part_roi, "primary", full_width=True)
        self._style_button(self.btn_cancel_part_roi, "danger", full_width=True)
        self._style_button(self.btn_delete_part_contour, "danger", full_width=True)
        self._style_button(self.btn_delete_part_volume, "danger", full_width=True)

    def _populate_label_role_combo(self):
        current = self.label_role_combo.currentData() if self.label_role_combo.count() else "manual_truth"
        self.label_role_combo.blockSignals(True)
        self.label_role_combo.clear()
        for role in ("manual_truth", "working_edit", "model_draft"):
            self.label_role_combo.addItem(tt(role, self.lang), role)
        index = self.label_role_combo.findData(current)
        self.label_role_combo.setCurrentIndex(index if index >= 0 else 0)
        self.label_role_combo.blockSignals(False)

    def _populate_slice_axis_combo(self):
        current = self.slice_axis_combo.currentData() if self.slice_axis_combo.count() else self.slice_axis
        self.slice_axis_combo.blockSignals(True)
        self.slice_axis_combo.clear()
        for axis, label in (("z", "Z axial"), ("y", "Y coronal"), ("x", "X sagittal")):
            self.slice_axis_combo.addItem(tt(label, self.lang), axis)
        index = self.slice_axis_combo.findData(current)
        self.slice_axis_combo.setCurrentIndex(index if index >= 0 else 0)
        self.slice_axis_combo.blockSignals(False)

    def _populate_display_mode_combo(self):
        current = self.display_mode_combo.currentData() if self.display_mode_combo.count() else self.display_mode
        self.display_mode_combo.blockSignals(True)
        self.display_mode_combo.clear()
        for mode, label in (("slice", "Slice review"), ("volume", "3D volume")):
            self.display_mode_combo.addItem(tt(label, self.lang), mode)
        index = self.display_mode_combo.findData(current)
        self.display_mode_combo.setCurrentIndex(index if index >= 0 else 0)
        self.display_mode_combo.blockSignals(False)

    def _populate_volume_projection_combo(self):
        current = self.volume_projection_combo.currentData() if self.volume_projection_combo.count() else "composite"
        self.volume_projection_combo.blockSignals(True)
        self.volume_projection_combo.clear()
        for mode, label in (
            ("composite", "Composite"),
            ("mip", "MIP"),
            ("minip", "MinIP"),
            ("average", "Average"),
            ("surface", "Surface"),
        ):
            self.volume_projection_combo.addItem(tt(label, self.lang), mode)
        index = self.volume_projection_combo.findData(current)
        self.volume_projection_combo.setCurrentIndex(index if index >= 0 else 0)
        self.volume_projection_combo.blockSignals(False)

    def _populate_volume_tint_combo(self):
        current = self._active_volume_view_settings().get("volume_tint", "amber")
        self.volume_tint_combo.blockSignals(True)
        self.volume_tint_combo.clear()
        for mode, label in (
            ("amber", "Amber"),
            ("cyan", "Cyan"),
            ("white", "White"),
            ("custom", "Custom"),
        ):
            self.volume_tint_combo.addItem(tt(label, self.lang), mode)
        index = self.volume_tint_combo.findData(current)
        self.volume_tint_combo.setCurrentIndex(index if index >= 0 else 0)
        self.volume_tint_combo.blockSignals(False)

    def _apply_volume_transfer_opacity_setting(self):
        if not hasattr(self, "volume_transfer_opacity_slider"):
            return
        settings = self._active_volume_view_settings()
        value = settings.get("volume_transfer_opacity", 100)
        try:
            value = int(round(float(value)))
        except (TypeError, ValueError):
            value = 100
        value = max(self.volume_transfer_opacity_slider.minimum(), min(self.volume_transfer_opacity_slider.maximum(), value))
        self.volume_transfer_opacity_slider.blockSignals(True)
        self.volume_transfer_opacity_slider.setValue(value)
        self.volume_transfer_opacity_slider.blockSignals(False)

    def _populate_volume_mask_combo(self):
        current = self.volume_mask_combo.currentData() if self.volume_mask_combo.count() else self._default_volume_mask_mode()
        self.volume_mask_combo.blockSignals(True)
        self.volume_mask_combo.clear()
        for mode, label in (
            ("image_only", "Image only"),
            ("mask_boundary", "Mask boundary"),
            ("masked_image", "Masked image"),
        ):
            self.volume_mask_combo.addItem(tt(label, self.lang), mode)
        index = self.volume_mask_combo.findData(current)
        self.volume_mask_combo.setCurrentIndex(index if index >= 0 else 0)
        self.volume_mask_combo.blockSignals(False)

    def _set_volume_mask_mode(self, mode):
        if not hasattr(self, "volume_mask_combo"):
            return False
        mode = mode if mode in {"image_only", "mask_boundary", "masked_image"} else "image_only"
        index = self.volume_mask_combo.findData(mode)
        if index < 0 or index == self.volume_mask_combo.currentIndex():
            return False
        self.volume_mask_combo.blockSignals(True)
        self.volume_mask_combo.setCurrentIndex(index)
        self.volume_mask_combo.blockSignals(False)
        return True

    def _default_volume_mask_mode(self):
        configured = (self._active_volume_view_settings() or {}).get("volume_mask_mode", "")
        if configured in {"image_only", "mask_boundary", "masked_image"}:
            if configured == "image_only" or self._active_part_mask_has_voxels():
                return configured
        if self.current_volume_scope == "part" and self._active_part_mask_has_voxels():
            return "masked_image"
        return "image_only"

    def _apply_default_volume_mask_mode(self):
        if self._set_volume_mask_mode(self._default_volume_mask_mode()):
            self._clear_volume_preview_cache()

    def _project_view_settings(self):
        return self.project.project_data.setdefault("view_settings", {})

    def _active_volume_view_settings(self):
        if self.current_volume_scope == "part" and isinstance(self.current_part, dict):
            part_settings = self.current_part.setdefault("view_settings", {})
            parent_settings = self._project_view_settings()
            for key in ("volume_tint", "volume_tint_custom", "volume_transfer_opacity"):
                if key not in part_settings and key in parent_settings:
                    part_settings[key] = parent_settings[key]
            return part_settings
        return self._project_view_settings()

    def _save_active_volume_view_settings(self):
        if self.current_volume_scope == "part" and self.current_specimen_id and self.current_part_id:
            settings = dict((self.current_part or {}).get("view_settings") or {})
            try:
                self.current_part = self.project.update_part_view_settings(self.current_specimen_id, self.current_part_id, settings)
            except Exception:
                if self.project.current_project_path:
                    self.project.save_project()
            return
        if self.project.current_project_path:
            self.project.save_project()

    def change_language(self, lang):
        self.lang = lang
        self._update_texts()
        self.refresh_project()
        self.render_current_slice()

    def _update_texts(self):
        for title, label in getattr(self, "_panel_title_labels", {}).values():
            label.setText(tt(title, self.lang))
        for title, label in getattr(self, "_section_title_labels", {}).values():
            label.setText(tt(title, self.lang))
        self._populate_label_role_combo()
        self._populate_display_mode_combo()
        self._populate_volume_projection_combo()
        self._populate_volume_tint_combo()
        self._apply_volume_transfer_opacity_setting()
        self._populate_volume_mask_combo()
        if hasattr(self, "task_tabs"):
            for index, label in enumerate(("Part", "Display", "Annotation", "Train/export")):
                self.task_tabs.setTabText(index, tt(label, self.lang))
        if self.image_volume is None:
            if self.specimen_list.count():
                self.canvas.setText(tt("Working volume missing", self.lang))
            else:
                self.canvas.setText(tt("No specimens in this TIF project", self.lang))
        self.slice_prefix_label.setText(tt("Slice", self.lang))
        self.display_mode_label.setText(tt("Display mode", self.lang))
        self.slice_axis_label.setText(tt("View plane", self.lang))
        self._populate_slice_axis_combo()
        self.label_layer_label.setText(tt("Label layer", self.lang))
        self._update_label_role_help()
        self.overlay_label.setText(tt("Overlay", self.lang))
        self.brightness_label.setText(tt("Brightness", self.lang))
        self.contrast_label.setText(tt("Contrast", self.lang))
        self.volume_projection_label.setText(tt("Render mode", self.lang))
        self.volume_tint_label.setText(tt("Transfer function", self.lang))
        self.volume_transfer_opacity_label.setText(tt("Density opacity", self.lang))
        self.volume_enhancement_label.setText(tt("Detail enhancement", self.lang))
        self.volume_tone_label.setText(tt("Tone curve", self.lang))
        self.volume_surface_refine_check.setText(tt("Surface refine", self.lang))
        self.volume_clip_plane_check.setText(tt("Clip plane", self.lang))
        self.volume_local_axes_check.setText(tt("Show local axes", self.lang))
        self.volume_clip_plane_depth_label.setText(tt("Clip depth", self.lang))
        self.volume_mask_label.setText(tt("Mask display", self.lang))
        self.volume_mask_opacity_label.setText(tt("Mask opacity", self.lang))
        self.volume_cutoff_label.setText(tt("Density cutoff", self.lang))
        self.volume_quality_label.setText(tt("Render quality", self.lang))
        self.volume_sample_label.setText(tt("Ray samples", self.lang))
        self.volume_clarity_check.setText(tt("Clarity mode", self.lang))
        self.volume_roi_detail_check.setText(tt("ROI high detail", self.lang))
        self.volume_roi_scale_label.setText(tt("ROI scale", self.lang))
        self.volume_inside_label.setText(tt("Inside depth", self.lang))
        self.volume_clip_label.setText(tt("Front cut", self.lang))
        self.btn_volume_custom_color.setText(tt("Choose color", self.lang))
        self.btn_reset_volume_view.setText(tt("Reset 3D view", self.lang))
        self._update_volume_control_tooltips()
        if self.display_mode == "volume":
            self.training_status_label.setText(self._volume_renderer_status_message())
        self.brush_size_label.setText(tt("Brush size", self.lang))
        self.btn_import_tif.setText(tt("Import TIF stack", self.lang))
        self.btn_import_amira.setText(tt("Import AMIRA directory", self.lang))
        self.part_bbox_edit.setPlaceholderText(tt("z0,z1,y0,y1,x0,x1", self.lang))
        self.btn_part_default_bbox.setText(tt("Use center ROI", self.lang))
        self.btn_part_draw_roi.setText(tt("Draw ROI", self.lang))
        self.btn_save_part_roi.setText(tt("Save ROI draft", self.lang))
        self.btn_confirm_part_roi.setText(tt("Confirm ROI", self.lang))
        self.btn_cancel_part_roi.setText(tt("Cancel ROI", self.lang))
        self.btn_create_part.setText(tt("Create part", self.lang))
        self.btn_add_rect_keyframe.setText(tt("Add rectangular key slice", self.lang))
        self.btn_draw_part_contour.setText(tt("Draw contour", self.lang))
        self.btn_delete_part_contour.setText(tt("Delete key slice", self.lang))
        self.btn_prev_key_slice.setText(tt("Previous key slice", self.lang))
        self.btn_next_key_slice.setText(tt("Next key slice", self.lang))
        self.btn_preview_part_mask.setText(tt("Preview auto fill", self.lang))
        self.btn_accept_part_mask.setText(tt("Accept part mask", self.lang))
        self.btn_clear_part_preview.setText(tt("Clear preview", self.lang))
        self.btn_export_part_package.setText(tt("Export part package", self.lang))
        if hasattr(self, "local_axis_volume_help_label"):
            self.local_axis_volume_help_label.setText(
                tt(
                    "Work in the 3D part preview first. Source Z is locked; copy it to create an editable output Z draft, then use the detail dialog only for precise MPR picking, roll reference, preview, and export.",
                    self.lang,
                )
            )
        self.btn_local_axis_reslice.setText(tt("Open detail / MPR / export", self.lang))
        self.btn_copy_source_z_axis.setText(tt("Copy source Z axis", self.lang))
        self.btn_local_axis_queue.setText(tt("Review proposals", self.lang))
        self.btn_local_axis_models.setText(tt("Local Axis Models", self.lang))
        self.btn_delete_part_volume.setText(tt("Delete part volume", self.lang))
        self.btn_undo.setText(tt("Undo", self.lang))
        self.btn_redo.setText(tt("Redo", self.lang))
        self.btn_save_edit.setText(tt("Save working edit", self.lang))
        self.auto_save_check.setText(tt("Auto-save edit", self.lang))
        self.show_debug_paths_check.setText(tt("Show debug paths", self.lang))
        self.btn_promote.setText(tt("Accept as manual truth", self.lang))
        self.btn_copy_draft.setText(tt("Copy model draft to working edit", self.lang))
        self.btn_add_material.setText(tt("Add material", self.lang))
        self.btn_edit_material.setText(tt("Edit material", self.lang))
        self.btn_delete_material.setText(tt("Delete material", self.lang))
        self.btn_export_training.setText(tt("Export train-ready volumes", self.lang))
        self.backend_id_label.setText(tt("Backend ID", self.lang))
        self.backend_display_label.setText(tt("Display name", self.lang))
        self.backend_python_label.setText(tt("Python", self.lang))
        self.backend_formats_label.setText(tt("Export formats", self.lang))
        self.backend_prepare_label.setText(tt("Prepare command", self.lang))
        self.backend_train_label.setText(tt("Train command", self.lang))
        self.backend_predict_label.setText(tt("Predict command", self.lang))
        self.backend_manifest_label.setText(tt("Model manifest", self.lang))
        self.btn_save_backend.setText(tt("Save backend settings", self.lang))
        self.btn_prepare_dataset.setText(tt("Prepare dataset", self.lang))
        self.btn_train_backend.setText(tt("Train backend", self.lang))
        self.btn_import_prediction.setText(tt("Import prediction", self.lang))
        self.btn_import_external_prediction_tif.setText(tt("Import external label TIF to draft", self.lang))
        self.btn_start_center.setText(tt("Start Center", self.lang))
        self.btn_ask_agent.setText(tt("Ask Agent", self.lang))
        self.material_table.setHorizontalHeaderLabels(
            [tt("ID", self.lang), tt("Name", self.lang), tt("Train", self.lang), tt("Color", self.lang)]
        )
        self._update_local_axis_summary()

    def _update_volume_control_tooltips(self):
        pairs = (
            (
                self.volume_projection_label,
                self.volume_projection_combo,
                "Switches how values along the viewing ray are projected. MIP highlights bright structures, MinIP highlights dark gaps, Average shows density trend, and Surface emphasizes boundaries.",
            ),
            (
                self.volume_cutoff_label,
                self.volume_cutoff_slider,
                "Filters low-gray background and noise. Raise it for outer shape review; lower it when weak internal structures disappear.",
            ),
            (
                self.volume_quality_label,
                self.volume_quality_slider,
                "Controls the maximum edge length of the still GPU volume. Dragging uses a smaller temporary texture, then rebuilds this sharper texture when the view settles.",
            ),
            (
                self.volume_sample_label,
                self.volume_sample_slider,
                "Controls the number of samples per screen pixel along the viewing ray. Higher values stabilize internal layers and fine lines, mainly increasing GPU compute load.",
            ),
            (
                self.volume_clarity_check,
                self.volume_clarity_check,
                "Sharp still rendering keeps more source intensity detail and uses crisper sampling. It may upload more data and can look grainier while revealing fine internal structures.",
            ),
            (
                self.volume_transfer_opacity_label,
                self.volume_transfer_opacity_slider,
                "Controls how strongly dense voxels accumulate in 3D. Lower values make internal layers less blocked; higher values make weak structures more visible.",
            ),
            (
                self.volume_enhancement_label,
                self.volume_enhancement_slider,
                "Enhances fine boundaries while the view is still. It is a display-only aid for checking internal layers and part edges.",
            ),
            (
                self.volume_tone_label,
                self.volume_tone_slider,
                "Adjusts display gamma for 3D rendering. Lower values brighten faint structures; higher values keep dense regions calmer.",
            ),
            (
                self.volume_surface_refine_check,
                self.volume_surface_refine_check,
                "Refines first surface hits in Surface mode while still. It improves contour stability without affecting Composite rendering.",
            ),
            (
                self.volume_clip_plane_check,
                self.volume_clip_plane_check,
                "Enables a view-aligned GPU clipping plane. It only cuts the display, not the saved TIF, mask, or training data.",
            ),
            (
                self.volume_local_axes_check,
                self.volume_local_axes_check,
                "Shows the locked source Z axis and the selected local output axis on the 3D part preview. This is display-only and does not edit data.",
            ),
            (
                self.volume_clip_plane_depth_label,
                self.volume_clip_plane_depth_slider,
                "Moves the clipping plane through the current 3D view. Use it to peel away outer tissue and inspect inside structures.",
            ),
            (
                self.volume_roi_detail_check,
                self.volume_roi_detail_check,
                "When zoomed in and still, renders the 3D view at a higher offscreen pixel density before scaling it back, improving small-part inspection at the cost of more GPU readback work.",
            ),
            (
                self.volume_roi_scale_label,
                self.volume_roi_scale_slider,
                "Controls the offscreen supersampling factor used by ROI high detail. Higher values make still zoomed views smoother but heavier.",
            ),
            (
                self.volume_inside_label,
                self.volume_inside_slider,
                "Moves the camera into the volume. Use it to enter the specimen and inspect internal structures; keep it at 0 for outer shape review.",
            ),
            (
                self.volume_clip_label,
                self.volume_clip_slider,
                "Cuts away the front part of the current view. Use it to remove blocking outer tissue and inspect deeper structures; keep it at 0 for the full outline.",
            ),
            (
                self.volume_mask_label,
                self.volume_mask_combo,
                "Shows accepted or preview part masks in the 3D view. Boundary is best for checking extraction edges; masked image hides voxels outside the mask.",
            ),
            (
                self.volume_mask_opacity_label,
                self.volume_mask_opacity_slider,
                "Controls how strongly mask boundaries are blended into the 3D inspection view.",
            ),
        )
        for label, slider, text in pairs:
            help_text = tt(text, self.lang)
            label.setToolTip(help_text)
            slider.setToolTip(help_text)
        self.btn_reset_volume_view.setToolTip(tt("Restores the external default view and clears inside depth and front cut.", self.lang))

    def get_agent_context(self):
        selected_material = self._selected_material()
        material_id = ""
        if isinstance(selected_material, dict):
            material_id = selected_material.get("id", "")
        recent_log = ""
        if hasattr(self, "log_console"):
            recent_log = "\n".join(self.log_console.toPlainText().splitlines()[-6:])

        source_shape, spacing_zyx = self._volume_source_geometry()
        active_label_role = self.label_role_combo.currentData() or ""
        active_label_volume = self.label_volume
        if active_label_role == "working_edit" and self.edit_volume is not None:
            active_label_volume = self.edit_volume
        label_shape = tuple(int(value) for value in getattr(active_label_volume, "shape", ()) or ())
        axis = self._current_slice_axis()
        slice_position = ""
        if self.image_volume is not None:
            slice_position = f"{int(self.slice_slider.value()) + 1}/{self._slice_count_for_axis(axis)}"

        readiness_text = ""
        readiness_reasons = ""
        if self.current_specimen_id and self.current_volume_scope != "part":
            try:
                readiness = self.project.evaluate_train_ready(self.current_specimen_id)
            except Exception:
                readiness = {}
            if readiness:
                readiness_text = "yes" if readiness.get("train_ready") else "no"
                readiness_reasons = ",".join(str(item) for item in readiness.get("reasons", []) if str(item))

        def triplet_text(values):
            values = tuple(values or ())
            if len(values) != 3:
                return ""
            return f"{values[0]}/{values[1]}/{values[2]}"

        clarity = "on" if bool(getattr(self, "_volume_clarity_mode", False)) else "off"
        volume_status = ""
        if self.image_volume is not None:
            volume_status = self.volume_canvas_overlay_text()
        volume_perf = self.volume_performance_report() if self.image_volume is not None else {}

        return {
            "source_workbench": "tif_volume",
            "project_type": "tif_volume",
            "project_path": getattr(self.project, "current_project_path", "") or "",
            "active_specimen_id": self.current_specimen_id,
            "active_volume_scope": self.current_volume_scope,
            "active_part_id": self.current_part_id,
            "active_part_parent_bbox_zyx": str((self.current_part or {}).get("parent_bbox_zyx", "")),
            "active_label_role": active_label_role,
            "selected_material_id": material_id,
            "display_mode": self.display_mode,
            "active_slice_axis": axis,
            "active_slice_position": slice_position,
            "active_volume_shape_zyx": triplet_text(source_shape),
            "active_volume_spacing_zyx": triplet_text(spacing_zyx),
            "active_label_shape_zyx": triplet_text(label_shape),
            "train_ready_status": readiness_text,
            "train_ready_reasons": readiness_reasons,
            "volume_renderer": self._volume_canvas_renderer,
            "volume_renderer_label": self._volume_renderer_label(),
            "volume_render_mode": self._volume_render_mode,
            "volume_projection_mode": self._volume_projection_mode(),
            "volume_mask_mode": self._volume_mask_mode(),
            "volume_density_cutoff": f"{int(self.volume_cutoff_slider.value())}%",
            "volume_density_opacity": f"{int(self.volume_transfer_opacity_slider.value())}%",
            "volume_texture_target_dim": str(self._active_volume_target_dim()),
            "volume_ray_samples": str(self._active_volume_sample_count()),
            "volume_clarity_mode": clarity,
            "volume_detail_enhancement": f"{int(self.volume_enhancement_slider.value())}%",
            "volume_tone_curve": f"{int(self.volume_tone_slider.value())}%",
            "volume_surface_refine": "on" if self.volume_surface_refine_check.isChecked() else "off",
            "volume_clip_plane": "on" if self.volume_clip_plane_check.isChecked() else "off",
            "volume_clip_plane_depth": f"{int(self.volume_clip_plane_depth_slider.value())}%",
            "volume_roi_high_detail": "on" if self.volume_roi_detail_check.isChecked() else "off",
            "volume_roi_scale": f"{self._active_volume_roi_scale():.1f}x",
            "volume_inside_depth": f"{int(self.volume_inside_slider.value())}%",
            "volume_front_cut": f"{int(self.volume_clip_slider.value())}%",
            "volume_zoom": f"{int(round(float(self._volume_zoom) * 100))}%",
            "volume_pan": f"x={int(round(float(self._volume_pan_x) * 100))}%, y={int(round(float(self._volume_pan_y) * 100))}%",
            "volume_yaw_pitch": f"yaw={float(self._volume_yaw):.1f}, pitch={float(self._volume_pitch):.1f}",
            "volume_gpu_warning": self._volume_renderer_warning,
            "volume_status_overlay": volume_status,
            "volume_performance_diagnosis": str(volume_perf.get("diagnosis", "")),
            "volume_uploaded_gb": f"{float(volume_perf.get('uploaded_gb', 0.0)):.2f}",
            "volume_upload_ms": f"{float(volume_perf.get('upload_ms', 0.0)):.0f}",
            "volume_draw_ms": f"{float(volume_perf.get('draw_ms', 0.0)):.1f}",
            "tif_next_requirement": "local_axis_reslice: define a part-local output axis plus roll reference, preview/export local resliced image and optional mask, and keep accepted records usable as training data.",
            "tif_requirement_doc": "docs/designs/2026-06-20_AntScan局部轴重切片合并设计稿.md",
            "recent_log_excerpt": recent_log,
        }

    def _backend_config_from_ui(self):
        return sanitize_tif_backend_config(
            {
                "backend_id": self.backend_id_edit.text(),
                "display_name": self.backend_display_edit.text(),
                "python_executable": self.backend_python_edit.text(),
                "export_formats": self.backend_formats_edit.text(),
                "prepare_dataset_command": self.backend_prepare_edit.text(),
                "train_command": self.backend_train_edit.text(),
                "predict_command": self.backend_predict_edit.text(),
                "model_manifest": self.backend_manifest_edit.text(),
            }
        )

    def _load_backend_config_into_ui(self):
        config = sanitize_tif_backend_config(self.backend_config)
        self.backend_id_edit.setText(config.get("backend_id", ""))
        self.backend_display_edit.setText(config.get("display_name", ""))
        self.backend_python_edit.setText(config.get("python_executable", "python"))
        self.backend_formats_edit.setText(config.get("export_formats", "ome_tiff,nrrd,mha,nifti"))
        self.backend_prepare_edit.setText(config.get("prepare_dataset_command", ""))
        self.backend_train_edit.setText(config.get("train_command", ""))
        self.backend_predict_edit.setText(config.get("predict_command", ""))
        self.backend_manifest_edit.setText(config.get("model_manifest", ""))

    def log(self, message):
        if not hasattr(self, "log_console"):
            return
        self.log_console.append(f"[{_now_log_time()}] {message}")

    def canvas_status_text(self, zoom_factor):
        if self.image_volume is None:
            return ""
        axis = self._current_slice_axis()
        index = int(self.slice_slider.value()) + 1
        total = self._slice_count_for_axis(axis)
        return f"{axis.upper()} {index}/{total} · {int(round(float(zoom_factor) * 100))}%"

    def move_slice(self, delta):
        if self.image_volume is None:
            return
        current = int(self.slice_slider.value())
        target = max(self.slice_slider.minimum(), min(self.slice_slider.maximum(), current + int(delta)))
        if target == current:
            return
        self.slice_slider.setValue(target)

    def on_slice_slider_changed(self):
        self._slice_positions[self._current_slice_axis()] = int(self.slice_slider.value())
        self.render_current_slice()

    def on_slice_axis_changed(self):
        axis = self.slice_axis_combo.currentData() or "z"
        self.slice_axis = axis if axis in {"z", "y", "x"} else "z"
        self._configure_slice_slider_for_axis(self.slice_axis, preserve_position=True)
        self._reset_canvas_view_on_next_render = True
        if self.slice_axis != "z":
            self.part_contour_draw_mode = False
            self.btn_draw_part_contour.blockSignals(True)
            self.btn_draw_part_contour.setChecked(False)
            self.btn_draw_part_contour.blockSignals(False)
            message = tt("Side-angle slices are read-only in this version. Use Z axial view for label editing.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
        self._set_scope_controls_enabled()
        self.render_current_slice()

    def on_display_mode_changed(self):
        mode = self.display_mode_combo.currentData() or "slice"
        self.display_mode = mode if mode in {"slice", "volume"} else "slice"
        if self.display_mode == "volume":
            self._ensure_volume_canvas()
        if hasattr(self, "view_stack"):
            self.view_stack.setCurrentWidget(self.volume_canvas if self.display_mode == "volume" else self.canvas)
        if hasattr(self, "volume_render_status_label"):
            self.volume_render_status_label.setVisible(self.display_mode == "volume")
        self._sync_mode_sections()
        is_volume = self.display_mode == "volume"
        if is_volume:
            self.part_roi_draw_mode = False
            self.part_contour_draw_mode = False
            self.btn_part_draw_roi.blockSignals(True)
            self.btn_part_draw_roi.setChecked(False)
            self.btn_part_draw_roi.blockSignals(False)
            self.btn_draw_part_contour.blockSignals(True)
            self.btn_draw_part_contour.setChecked(False)
            self.btn_draw_part_contour.blockSignals(False)
        volume_mode_controls = (
            self.volume_sample_label,
            self.volume_sample_slider,
            self.volume_clarity_check,
            self.volume_enhancement_label,
            self.volume_enhancement_slider,
            self.volume_tone_label,
            self.volume_tone_slider,
            self.volume_surface_refine_check,
            self.volume_roi_detail_check,
            self.volume_roi_scale_label,
            self.volume_roi_scale_slider,
            self.volume_clip_plane_check,
            self.volume_clip_plane_depth_label,
            self.volume_clip_plane_depth_slider,
            self.volume_inside_label,
            self.volume_inside_slider,
            self.volume_clip_label,
            self.volume_clip_slider,
        )
        for widget in (
            self.slice_axis_label,
            self.slice_axis_combo,
            self.slice_prefix_label,
            self.slice_slider,
            self.slice_label,
            self.volume_sample_label,
            self.volume_sample_slider,
            self.volume_clarity_check,
            self.volume_enhancement_label,
            self.volume_enhancement_slider,
            self.volume_tone_label,
            self.volume_tone_slider,
            self.volume_surface_refine_check,
            self.volume_roi_detail_check,
            self.volume_roi_scale_label,
            self.volume_roi_scale_slider,
            self.volume_clip_plane_check,
            self.volume_clip_plane_depth_label,
            self.volume_clip_plane_depth_slider,
            self.volume_inside_label,
            self.volume_inside_slider,
            self.volume_clip_label,
            self.volume_clip_slider,
        ):
            is_volume_control = any(widget is control for control in volume_mode_controls)
            widget.setVisible(is_volume if is_volume_control else not is_volume)
        if is_volume:
            message = self._volume_renderer_status_message()
            self.training_status_label.setText(message)
            self.log(message)
            self._apply_default_volume_mask_mode()
            self._set_scope_controls_enabled()
            self.render_volume_preview()
        else:
            self._set_scope_controls_enabled()
            self.render_current_slice()

    def _sync_mode_sections(self):
        is_volume = self.display_mode == "volume"
        is_part = self.current_volume_scope == "part"
        is_full = not is_part
        self._place_local_axis_volume_section(is_volume=is_volume, is_part=is_part)
        if hasattr(self, "slice_display_section"):
            self.slice_display_section.setVisible(not is_volume)
        if hasattr(self, "annotation_section"):
            self.annotation_section.setVisible(not is_volume and is_full)
        if hasattr(self, "volume_render_section"):
            self.volume_render_section.setVisible(is_volume)
        if hasattr(self, "local_axis_volume_section"):
            self.local_axis_volume_section.setVisible(is_part)
        if hasattr(self, "part_locate_section"):
            self.part_locate_section.setVisible(is_full and not is_volume)
        if hasattr(self, "part_mask_section"):
            self.part_mask_section.setVisible(is_part and not is_volume)
        if hasattr(self, "part_output_section"):
            self.part_output_section.setVisible(is_part)
        if hasattr(self, "task_tabs"):
            target = self.display_task_page if is_volume else self.part_task_page
            if self.task_tabs.currentWidget() is not target:
                self.task_tabs.setCurrentWidget(target)
        self._update_local_axis_summary()

    def _place_local_axis_volume_section(self, is_volume=None, is_part=None):
        section = getattr(self, "local_axis_volume_section", None)
        if section is None:
            return
        is_volume = self.display_mode == "volume" if is_volume is None else bool(is_volume)
        is_part = self.current_volume_scope == "part" if is_part is None else bool(is_part)
        if is_volume and is_part and hasattr(self, "display_task_layout"):
            if self.display_task_layout.indexOf(section) != 0:
                self.display_task_layout.insertWidget(0, section)
            return
        if hasattr(self, "part_task_layout") and hasattr(self, "part_output_section"):
            output_index = self.part_task_layout.indexOf(self.part_output_section)
            target_index = output_index if output_index >= 0 else self.part_task_layout.count()
            current_index = self.part_task_layout.indexOf(section)
            if current_index != target_index - (1 if 0 <= current_index < target_index else 0):
                self.part_task_layout.insertWidget(target_index, section)

    def _safe_contour_slice_index(self, keyframe, default=None):
        try:
            return int((keyframe or {}).get("slice_index", default))
        except (TypeError, ValueError, OverflowError):
            return default

    def _connect_volume_canvas_signals(self, canvas):
        if hasattr(canvas, "render_failed"):
            canvas.render_failed.connect(self._on_gpu_volume_failed)
        if hasattr(canvas, "render_info_changed"):
            canvas.render_info_changed.connect(self._on_gpu_volume_info_changed)
        if hasattr(canvas, "render_stats_changed"):
            canvas.render_stats_changed.connect(self._on_gpu_volume_stats_changed)

    def _ensure_volume_canvas(self, force_gpu=False):
        if self._volume_canvas_created and not force_gpu:
            return
        old_canvas = getattr(self, "volume_canvas", None)
        if force_gpu and old_canvas is not None and hasattr(old_canvas, "release_gl_resources"):
            try:
                old_canvas.release_gl_resources()
            except Exception:
                pass
        canvas, renderer, warning = create_tif_volume_canvas()
        canvas.workbench = self
        if not hasattr(canvas, "set_volume_data"):
            canvas.setProperty("tifVolumeRenderer", "cpu")
            renderer = "cpu"
        self._connect_volume_canvas_signals(canvas)
        self.volume_canvas = canvas
        self._volume_canvas_renderer = renderer
        self._volume_renderer_warning = warning
        self._volume_canvas_created = True
        if hasattr(self, "view_stack"):
            self.view_stack.addWidget(self.volume_canvas)
            if self.display_mode == "volume":
                self.view_stack.setCurrentWidget(self.volume_canvas)
            if old_canvas is not None:
                index = self.view_stack.indexOf(old_canvas)
                if index >= 0:
                    self.view_stack.removeWidget(old_canvas)
        if old_canvas is not None:
            old_canvas.hide()
            old_canvas.setParent(None)
            old_canvas.deleteLater()
        if warning:
            self.log(tt("GPU renderer unavailable. Using CPU fallback.", self.lang) + f" {warning}")

    def _reset_volume_canvas_placeholder_for_agent(self):
        canvas = getattr(self, "volume_canvas", None)
        if canvas is None or not getattr(self, "_volume_canvas_created", False):
            return
        renderer_kind = str(canvas.property("tifVolumeRenderer") or "")
        if renderer_kind == "gpu-offscreen":
            return
        if hasattr(canvas, "release_gl_resources"):
            try:
                canvas.release_gl_resources()
            except Exception:
                pass
        placeholder = TifVolumeCanvas()
        placeholder.workbench = self
        placeholder.setProperty("tifVolumeRenderer", "placeholder")
        self.volume_canvas = placeholder
        self._volume_canvas_renderer = "cpu"
        self._volume_renderer_warning = ""
        self._volume_gl_renderer_info = ""
        self._volume_canvas_created = False
        if hasattr(self, "view_stack"):
            self.view_stack.addWidget(self.volume_canvas)
            if self.display_mode == "volume":
                self.view_stack.setCurrentWidget(self.volume_canvas)
            index = self.view_stack.indexOf(canvas)
            if index >= 0:
                self.view_stack.removeWidget(canvas)
        canvas.hide()
        canvas.setParent(None)
        canvas.deleteLater()

    def _label_role_help_text(self, role=None):
        role = role or self.label_role_combo.currentData()
        if role == "working_edit":
            return tt("Current edit is the editable working copy. Brush changes are saved here first.", self.lang)
        if role == "model_draft":
            return tt("Model draft is a read-only prediction candidate. Copy it to Current edit before manual correction.", self.lang)
        return tt("Manual truth is a read-only reference. Switch to Current edit before changing labels.", self.lang)

    def _update_label_role_help(self):
        if hasattr(self, "label_role_help_label"):
            self.label_role_help_label.setText(self._label_role_help_text())

    def _on_auto_save_toggled(self, checked):
        message = tt("Auto-save is on. Brush changes are saved shortly after editing.", self.lang) if checked else tt("Auto-save is off. Remember to save the current edit layer.", self.lang)
        self.training_status_label.setText(message)
        self.log(message)
        if checked and self.working_edit_dirty:
            self.auto_save_timer.start()
        elif not checked:
            self.auto_save_timer.stop()

    def _mark_working_edit_dirty(self):
        self.working_edit_dirty = True
        if self.auto_save_check.isChecked():
            self.auto_save_timer.start()

    def _confirm_discard_or_save_working_edit(self):
        self.auto_save_timer.stop()
        if not self.working_edit_dirty:
            return True
        reply = QMessageBox.question(
            self,
            tt("Unsaved working edit", self.lang),
            tt("Save changes to the current working_edit before continuing?", self.lang),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Save:
            return self.save_working_edit(show_message=True)
        self.working_edit_dirty = False
        self._dirty_edit_slices = set()
        if self.current_specimen_id:
            self._load_edit_volume()
        return True

    def save_backend_settings(self):
        self.backend_config = self._backend_config_from_ui()
        if self.config_manager is not None:
            self.config_manager.set("tif_backend", dict(self.backend_config))
            self.config_manager.save()
        self.training_status_label.setText(tt("Backend settings saved.", self.lang))
        self.log(tt("Backend settings saved.", self.lang))
        QMessageBox.information(self, tt("TIF backend", self.lang), tt("Backend settings saved.", self.lang))

    def _ensure_tif_project_open(self):
        if not self.project.current_project_path:
            QMessageBox.warning(
                self,
                tt("TIF data import", self.lang),
                tt("Please create or open a TIF project first.", self.lang),
            )
            return False
        return True

    def _select_specimen_after_import(self, specimen_id):
        self._select_volume_tree_item(specimen_id, "full")

    def _set_tif_import_controls_enabled(self, enabled):
        for button in (self.btn_import_tif, self.btn_import_amira):
            button.setEnabled(bool(enabled))

    def _cleanup_tif_import_thread(self):
        self._set_tif_import_controls_enabled(True)
        if self._tif_import_progress is not None:
            self._tif_import_progress.close()
            self._tif_import_progress.deleteLater()
        self._tif_import_progress = None
        self._tif_import_worker = None
        self._tif_import_thread = None
        self._tif_import_specimen_id = ""

    def _on_tif_import_progress(self, current, total, message):
        if self._tif_import_progress is None:
            return
        maximum = max(1, int(total or 100))
        value = max(0, min(maximum, int(current or 0)))
        self._tif_import_progress.setMaximum(maximum)
        self._tif_import_progress.setValue(value)
        self._tif_import_progress.setLabelText(tt(message, self.lang))

    def _on_tif_import_finished(self, result):
        specimen_id = self._tif_import_specimen_id
        self.refresh_project()
        self._select_specimen_after_import(specimen_id)
        report_path = result.get("report_path", "") if isinstance(result, dict) else ""
        message = tt("Imported TIF stack for specimen {0}. Report: {1}", self.lang).format(specimen_id, report_path)
        self.training_status_label.setText(message)
        self.log(message)
        thread = self._tif_import_thread
        self._cleanup_tif_import_thread()
        if thread is not None:
            thread.quit()

    def _on_tif_import_failed(self, message):
        thread = self._tif_import_thread
        self._cleanup_tif_import_thread()
        if thread is not None:
            thread.quit()
        QMessageBox.critical(self, tt("Import TIF Stack", self.lang), message)

    def import_tif_stack_dialog(self):
        if not self._ensure_tif_project_open():
            return
        if self._tif_import_thread is not None:
            QMessageBox.information(
                self,
                tt("Import TIF Stack", self.lang),
                tt("TIF import is already running.", self.lang),
            )
            return
        tif_path, _ = QFileDialog.getOpenFileName(
            self,
            tt("Import TIF Stack", self.lang),
            "",
            "TIF/TIFF (*.tif *.tiff)",
        )
        if not tif_path:
            return
        default_id = os.path.splitext(os.path.basename(tif_path))[0]
        specimen_id, ok = QInputDialog.getText(
            self,
            tt("Import TIF Stack", self.lang),
            tt("Specimen ID:", self.lang),
            text=default_id,
        )
        if not ok or not specimen_id:
            return
        self._set_tif_import_controls_enabled(False)
        self._tif_import_specimen_id = specimen_id
        self._tif_import_progress = QProgressDialog(
            tt("Importing TIF stack...", self.lang),
            "",
            0,
            100,
            self,
        )
        self._tif_import_progress.setWindowTitle(tt("Import TIF Stack", self.lang))
        self._tif_import_progress.setCancelButton(None)
        self._tif_import_progress.setAutoClose(False)
        self._tif_import_progress.setAutoReset(False)
        self._tif_import_progress.setWindowModality(Qt.WindowModal)
        self._tif_import_progress.show()

        self._tif_import_thread = QThread(self)
        self._tif_import_worker = TifImportWorker(self.project, tif_path, specimen_id)
        self._tif_import_worker.moveToThread(self._tif_import_thread)
        self._tif_import_thread.started.connect(self._tif_import_worker.run)
        self._tif_import_worker.progress.connect(self._on_tif_import_progress)
        self._tif_import_worker.finished.connect(self._on_tif_import_finished)
        self._tif_import_worker.failed.connect(self._on_tif_import_failed)
        self._tif_import_worker.finished.connect(self._tif_import_thread.quit)
        self._tif_import_worker.failed.connect(self._tif_import_thread.quit)
        self._tif_import_thread.finished.connect(self._tif_import_worker.deleteLater)
        self._tif_import_thread.finished.connect(self._tif_import_thread.deleteLater)
        self._tif_import_thread.start()

    def import_amira_directory_dialog(self):
        if not self._ensure_tif_project_open():
            return
        source_dir = QFileDialog.getExistingDirectory(self, tt("Import AMIRA Directory", self.lang), self.project.project_dir)
        if not source_dir:
            return
        default_id = os.path.basename(os.path.normpath(source_dir))
        specimen_id, ok = QInputDialog.getText(
            self,
            tt("Import AMIRA Directory", self.lang),
            tt("Specimen ID:", self.lang),
            text=default_id,
        )
        if not ok or not specimen_id:
            return
        try:
            result = import_amira_directory(self.project, source_dir, specimen_id)
        except Exception as exc:
            QMessageBox.critical(self, tt("Import AMIRA Directory", self.lang), str(exc))
            return
        self.refresh_project()
        self._select_specimen_after_import(specimen_id)
        report_path = result.get("report_path", "")
        message = tt("Imported AMIRA directory for specimen {0}. Report: {1}", self.lang).format(specimen_id, report_path)
        self.training_status_label.setText(message)
        self.log(message)

    def _default_part_bbox(self):
        if self.image_volume is None:
            return []
        shape = [int(value) for value in self.image_volume.shape]
        bbox = []
        for size in shape:
            span = max(1, int(round(size * 0.45)))
            start = max(0, int((size - span) // 2))
            end = min(size, start + span)
            bbox.append([start, end])
        return bbox

    def _bbox_text(self, bbox):
        if not bbox or len(bbox) != 3:
            return ""
        return ",".join(str(int(value)) for pair in bbox for value in pair)

    def fill_default_part_bbox(self):
        bbox = self._default_part_bbox()
        if bbox:
            self.part_bbox_edit.setText(self._bbox_text(bbox))
            self.active_part_roi_id = ""
            self.render_current_slice()

    def _parse_part_bbox_text(self):
        text = self.part_bbox_edit.text().strip()
        if not text:
            bbox = self._default_part_bbox()
            if bbox:
                self.part_bbox_edit.setText(self._bbox_text(bbox))
            return bbox
        chunks = [chunk.strip() for chunk in text.replace(";", ",").split(",") if chunk.strip()]
        if len(chunks) != 6:
            raise ValueError("bbox_must_be_z0_z1_y0_y1_x0_x1")
        values = [int(chunk) for chunk in chunks]
        return [[values[0], values[1]], [values[2], values[3]], [values[4], values[5]]]

    def is_part_roi_draw_mode(self):
        return bool(
            self.part_roi_draw_mode
            and self.current_volume_scope == "full"
            and self.display_mode == "slice"
            and self.image_volume is not None
        )

    def set_part_roi_draw_mode(self, checked):
        self.part_roi_draw_mode = bool(checked)
        if self.part_roi_draw_mode:
            self.part_contour_draw_mode = False
            self.btn_draw_part_contour.blockSignals(True)
            self.btn_draw_part_contour.setChecked(False)
            self.btn_draw_part_contour.blockSignals(False)
            if self.current_volume_scope != "full" or self.image_volume is None:
                self.part_roi_draw_mode = False
                self.btn_part_draw_roi.blockSignals(True)
                self.btn_part_draw_roi.setChecked(False)
                self.btn_part_draw_roi.blockSignals(False)
                QMessageBox.information(self, tt("Part extraction", self.lang), tt("Switch to Full volume before drawing ROI.", self.lang))
                return
            message = tt("Drag on the current slice to update the ROI bbox.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
        self.render_current_slice()

    def is_part_contour_draw_mode(self):
        return bool(
            self.part_contour_draw_mode
            and self.current_volume_scope == "part"
            and self.display_mode == "slice"
            and self.image_volume is not None
            and self._current_slice_axis() == "z"
        )

    def set_part_contour_draw_mode(self, checked):
        self.part_contour_draw_mode = bool(checked)
        if self.part_contour_draw_mode:
            self.part_roi_draw_mode = False
            self.btn_part_draw_roi.blockSignals(True)
            self.btn_part_draw_roi.setChecked(False)
            self.btn_part_draw_roi.blockSignals(False)
            if self.current_volume_scope != "part" or self.image_volume is None:
                self.part_contour_draw_mode = False
                self.btn_draw_part_contour.blockSignals(True)
                self.btn_draw_part_contour.setChecked(False)
                self.btn_draw_part_contour.blockSignals(False)
                QMessageBox.information(self, tt("Part extraction", self.lang), tt("Switch to part volume before drawing contours.", self.lang))
                return
            if self.display_mode != "slice" or self._current_slice_axis() != "z":
                self.part_contour_draw_mode = False
                self.btn_draw_part_contour.blockSignals(True)
                self.btn_draw_part_contour.setChecked(False)
                self.btn_draw_part_contour.blockSignals(False)
                QMessageBox.information(self, tt("Part extraction", self.lang), tt("Contour drawing currently uses Z slices.", self.lang))
                return
            message = tt("Drag on the current part slice to draw a closed contour.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
        self.render_current_slice()

    def current_roi_overlay_rects(self):
        if self.current_volume_scope != "full" or self.image_volume is None:
            return []
        overlays = []
        try:
            bbox = self._parse_part_bbox_text()
        except Exception:
            bbox = []
        if bbox and len(bbox) == 3:
            current_rect = self._bbox_projection_for_current_slice(bbox)
            if current_rect:
                overlays.append({"rect": current_rect, "color": "#FFD34D", "kind": "current"})
        specimen = self.project.get_specimen(self.current_specimen_id, default=None) if self.current_specimen_id else None
        for roi in (specimen or {}).get("part_rois", []) or []:
            if (roi or {}).get("status") == "cancelled":
                continue
            rect = self._bbox_projection_for_current_slice((roi or {}).get("bbox_zyx", []))
            if rect:
                color = "#42D9C8" if (roi or {}).get("status") in {"draft", "confirmed"} else "#7EE787"
                overlays.append({"rect": rect, "color": color, "kind": "roi", "roi_id": (roi or {}).get("roi_id", "")})
        for part in (specimen or {}).get("parts", []) or []:
            rect = self._bbox_projection_for_current_slice((part or {}).get("parent_bbox_zyx", []))
            if rect:
                overlays.append({"rect": rect, "color": "#7EE787", "kind": "part", "part_id": (part or {}).get("part_id", "")})
        return overlays

    def _bbox_projection_for_current_slice(self, bbox):
        if not bbox or len(bbox) != 3:
            return None
        axis, index = self._active_slice_position()
        z_range, y_range, x_range = bbox
        if axis == "z":
            if not (int(z_range[0]) <= int(index) < int(z_range[1])):
                return None
            return [x_range[0], y_range[0], x_range[1], y_range[1]]
        if axis == "y":
            if not (int(y_range[0]) <= int(index) < int(y_range[1])):
                return None
            return [x_range[0], z_range[0], x_range[1], z_range[1]]
        if axis == "x":
            if not (int(x_range[0]) <= int(index) < int(x_range[1])):
                return None
            return [y_range[0], z_range[0], y_range[1], z_range[1]]
        return None

    def finish_part_roi_drag(self, start_x, start_y, end_x, end_y):
        if not self.is_part_roi_draw_mode() or self.image_volume is None:
            return
        axis = self._current_slice_axis()
        start_pixel = self.canvas.widget_to_image_pixel(start_x, start_y)
        end_pixel = self.canvas.widget_to_image_pixel(end_x, end_y)
        if start_pixel is None or end_pixel is None:
            return
        x0 = min(int(start_pixel[0]), int(end_pixel[0]))
        x1 = max(int(start_pixel[0]), int(end_pixel[0])) + 1
        y0 = min(int(start_pixel[1]), int(end_pixel[1]))
        y1 = max(int(start_pixel[1]), int(end_pixel[1])) + 1
        if x1 - x0 < 2 or y1 - y0 < 2:
            return
        try:
            bbox = self._parse_part_bbox_text()
        except Exception:
            bbox = self._default_part_bbox()
        if not bbox:
            return
        slice_index = int(self.slice_slider.value())
        if axis == "z":
            bbox[0] = self._expanded_axis_range(bbox[0], slice_index, int(self.image_volume.shape[0]))
            bbox[1] = [y0, y1]
            bbox[2] = [x0, x1]
        elif axis == "y":
            bbox[0] = [y0, y1]
            bbox[1] = self._expanded_axis_range(bbox[1], slice_index, int(self.image_volume.shape[1]))
            bbox[2] = [x0, x1]
        elif axis == "x":
            bbox[0] = [y0, y1]
            bbox[1] = [x0, x1]
            bbox[2] = self._expanded_axis_range(bbox[2], slice_index, int(self.image_volume.shape[2]))
        bbox = self._clip_bbox_to_shape(bbox, self.image_volume.shape)
        self.part_bbox_edit.setText(self._bbox_text(bbox))
        message = tt("ROI bbox updated: {0}", self.lang).format(self.part_bbox_edit.text())
        self.training_status_label.setText(message)
        self.log(message)
        self.render_current_slice()

    def open_roi_at_widget_position(self, x, y):
        if self.current_volume_scope != "full" or self.image_volume is None:
            return False
        pixel = self.canvas.widget_to_image_pixel(x, y)
        if pixel is None:
            return False
        px, py = pixel
        overlays = list(reversed(self.current_roi_overlay_rects()))
        for overlay in overlays:
            if not isinstance(overlay, dict):
                continue
            rect = overlay.get("rect", [])
            if len(rect) != 4:
                continue
            x0, y0, x1, y1 = [int(value) for value in rect]
            if not (min(x0, x1) <= px <= max(x0, x1) and min(y0, y1) <= py <= max(y0, y1)):
                continue
            if overlay.get("kind") == "part" and overlay.get("part_id"):
                self._select_volume_tree_item(self.current_specimen_id, "part", overlay.get("part_id", ""))
                return True
            if overlay.get("kind") == "roi" and overlay.get("roi_id"):
                roi = self.project.get_part_roi(self.current_specimen_id, overlay.get("roi_id", ""), default=None)
                if roi is not None:
                    self.active_part_roi_id = roi.get("roi_id", "")
                    self.part_bbox_edit.setText(self._bbox_text(roi.get("bbox_zyx", [])))
                    message = tt("Loaded ROI draft {0} for editing.", self.lang).format(roi.get("display_name") or roi.get("roi_id"))
                    self.training_status_label.setText(message)
                    self.log(message)
                    self.render_current_slice()
                    return True
        return False

    def _expanded_axis_range(self, existing_range, index, size):
        try:
            start, end = int(existing_range[0]), int(existing_range[1])
        except Exception:
            start, end = index, index + 1
        if end <= start:
            start, end = index, index + 1
        return [max(0, min(start, index)), min(int(size), max(end, index + 1))]

    def _default_roi_id(self):
        existing = len(self.project.list_part_rois(self.current_specimen_id, include_cancelled=True)) if self.current_specimen_id else 0
        return f"roi_{existing + 1}"

    def save_part_roi_draft(self):
        if self.current_volume_scope != "full" or not self.current_specimen_id or self.image_volume is None:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Switch to Full volume before saving ROI draft.", self.lang))
            return None
        try:
            bbox = self._clip_bbox_to_shape(self._parse_part_bbox_text(), self.image_volume.shape)
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return None
        if self.active_part_roi_id:
            roi = self.project.update_part_roi(self.current_specimen_id, self.active_part_roi_id, bbox_zyx=bbox, status="draft")
        else:
            dialog = TifPartNameDialog(
                "Save ROI draft",
                part_id=self._default_roi_id(),
                display_name=self._default_roi_id(),
                parent=self,
                lang=self.lang,
                id_label="ROI ID:",
            )
            if dialog.exec() != QDialog.Accepted:
                return None
            roi_id, display_name = dialog.values()
            if not str(roi_id).strip():
                return None
            try:
                roi = self.project.add_part_roi(
                    self.current_specimen_id,
                    roi_id,
                    display_name=display_name or roi_id,
                    bbox_zyx=bbox,
                    status="draft",
                )
            except Exception as exc:
                QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
                return None
        self.active_part_roi_id = roi.get("roi_id", "")
        self.part_bbox_edit.setText(self._bbox_text(roi.get("bbox_zyx", [])))
        message = tt("Saved ROI draft {0}.", self.lang).format(roi.get("display_name") or roi.get("roi_id"))
        self.training_status_label.setText(message)
        self.log(message)
        self.render_current_slice()
        return roi

    def confirm_part_roi_to_part(self):
        if self.current_volume_scope != "full" or not self.current_specimen_id or self.image_volume is None:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Switch to Full volume before confirming ROI.", self.lang))
            return
        roi = self.project.get_part_roi(self.current_specimen_id, self.active_part_roi_id, default=None) if self.active_part_roi_id else None
        if roi is not None:
            bbox = roi.get("bbox_zyx", [])
            default_part_id = str(roi.get("roi_id", "")).replace("_roi", "") or f"part_{len(self.project.list_parts(self.current_specimen_id)) + 1}"
            default_display_name = str(roi.get("display_name") or default_part_id)
        else:
            try:
                bbox = self._clip_bbox_to_shape(self._parse_part_bbox_text(), self.image_volume.shape)
            except Exception as exc:
                QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
                return
            default_part_id = f"part_{len(self.project.list_parts(self.current_specimen_id)) + 1}"
            default_display_name = default_part_id
        if not bbox:
            return
        dialog = TifPartNameDialog(
            "Confirm ROI",
            part_id=default_part_id,
            display_name=default_display_name,
            parent=self,
            lang=self.lang,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        part_id, display_name = dialog.values()
        if not part_id:
            return
        try:
            part = crop_volume_to_part(self.project, self.current_specimen_id, part_id, bbox, display_name=display_name or part_id)
            if roi is not None:
                self.project.update_part_roi(
                    self.current_specimen_id,
                    roi.get("roi_id", ""),
                    status="part_created",
                    linked_part_id=part.get("part_id", ""),
                    save=True,
                )
            else:
                self._ensure_roi_for_created_part(part, bbox, display_name=display_name or part_id)
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        self.active_part_roi_id = ""
        self.refresh_project()
        self._select_volume_tree_item(self.current_specimen_id, "part", part.get("part_id", ""))
        message = tt("Confirmed ROI and created part {0}.", self.lang).format(part.get("display_name") or part.get("part_id"))
        self.training_status_label.setText(message)
        self.log(message)

    def _ensure_roi_for_created_part(self, part, bbox, display_name=""):
        if not isinstance(part, dict):
            return None
        part_id = part.get("part_id", "")
        if self.active_part_roi_id:
            try:
                return self.project.update_part_roi(
                    self.current_specimen_id,
                    self.active_part_roi_id,
                    bbox_zyx=bbox,
                    status="part_created",
                    linked_part_id=part_id,
                    display_name=display_name or part.get("display_name") or part_id,
                    save=True,
                )
            except Exception:
                pass
        roi_id = f"{part_id}_roi"
        try:
            return self.project.add_part_roi(
                self.current_specimen_id,
                roi_id,
                display_name=display_name or part.get("display_name") or roi_id,
                bbox_zyx=bbox,
                status="part_created",
                linked_part_id=part_id,
                save=True,
            )
        except ValueError:
            return None

    def cancel_part_roi_draft(self):
        if not self.active_part_roi_id:
            self.part_bbox_edit.clear()
            self.render_current_slice()
            return
        roi = self.project.get_part_roi(self.current_specimen_id, self.active_part_roi_id, default=None)
        if roi is not None and roi.get("linked_part_id"):
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("This ROI is linked to a created part and cannot be cancelled here.", self.lang))
            return
        self.project.discard_part_roi(self.current_specimen_id, self.active_part_roi_id)
        message = tt("Cancelled ROI draft {0}.", self.lang).format(self.active_part_roi_id)
        self.active_part_roi_id = ""
        self.part_bbox_edit.clear()
        self.training_status_label.setText(message)
        self.log(message)
        self.render_current_slice()

    def delete_current_part_volume(self):
        if self.current_volume_scope != "part" or not self.current_specimen_id or not self.current_part_id:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Select a part volume before exporting a part package.", self.lang))
            return
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        if part is None:
            return
        display_name = part.get("display_name") or part.get("part_id") or self.current_part_id
        response = QMessageBox.question(
            self,
            tt("Delete part volume?", self.lang),
            tt(
                "Delete part volume {0}? This removes the cropped image, mask, contours, and extraction files, but keeps the parent TIF volume.",
                self.lang,
            ).format(display_name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response != QMessageBox.Yes:
            return
        try:
            self.image_volume = None
            self.label_volume = None
            self.edit_volume = None
            self.part_preview_mask = None
            self._clear_volume_preview_cache()
            import gc

            gc.collect()
            result = self.project.discard_part(self.current_specimen_id, self.current_part_id, remove_storage=True, save=False)
            specimen = self.project.get_specimen(self.current_specimen_id, default=None)
            if specimen is not None:
                for roi in specimen.get("part_rois", []) or []:
                    if str(roi.get("linked_part_id", "")) == str(self.current_part_id):
                        self.project.update_part_roi(
                            self.current_specimen_id,
                            roi.get("roi_id", ""),
                            status="cancelled",
                            linked_part_id="",
                            save=False,
                        )
            self.project.save_project()
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        self.part_preview_mask = None
        self.current_part = None
        deleted_part_id = self.current_part_id
        self.current_part_id = ""
        self.current_volume_scope = "full"
        self._clear_volume_preview_cache()
        self.refresh_project()
        self._select_volume_tree_item(self.current_specimen_id, "full", "")
        message = tt("Deleted part volume {0}.", self.lang).format(display_name)
        if not result.get("removed_storage"):
            message = f"{message} Storage was already missing."
        self.training_status_label.setText(message)
        self.log(f"{message} part_id={deleted_part_id}")

    def _clip_bbox_to_shape(self, bbox, shape):
        clean = []
        for axis, pair in enumerate(bbox):
            size = int(shape[axis])
            start = max(0, min(size, int(pair[0])))
            end = max(0, min(size, int(pair[1])))
            if end < start:
                start, end = end, start
            if end == start:
                end = min(size, start + 1)
                start = max(0, end - 1)
            clean.append([start, end])
        return clean

    def create_part_from_bbox_dialog(self):
        if self.current_volume_scope != "full" or not self.current_specimen_id or self.image_volume is None:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Switch to Full volume before creating a part.", self.lang))
            return
        default_part_id = f"part_{len(self.project.list_parts(self.current_specimen_id)) + 1}"
        dialog = TifPartNameDialog(
            "Create part",
            part_id=default_part_id,
            display_name=default_part_id,
            parent=self,
            lang=self.lang,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        part_id, display_name = dialog.values()
        if not part_id:
            return
        try:
            bbox = self._clip_bbox_to_shape(self._parse_part_bbox_text(), self.image_volume.shape)
            part = crop_volume_to_part(self.project, self.current_specimen_id, part_id, bbox, display_name=display_name or part_id)
            self._ensure_roi_for_created_part(part, bbox, display_name=display_name or part_id)
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        self.active_part_roi_id = ""
        self.refresh_project()
        self._select_volume_tree_item(self.current_specimen_id, "part", part.get("part_id", ""))
        message = tt("Created part {0} from bbox {1}.", self.lang).format(part.get("display_name") or part.get("part_id"), part.get("parent_bbox_zyx"))
        self.training_status_label.setText(message)
        self.log(message)

    def _current_part_contours_path(self):
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        if part is None:
            return ""
        return self.project.to_absolute(part.get("contours_path", ""))

    def _current_part_contours(self):
        contours_path = self._current_part_contours_path()
        if not contours_path:
            return {}, ""
        return read_contours_json(contours_path), contours_path

    def _format_contour_quality_report(self, report):
        if not isinstance(report, dict):
            return ""
        problems = []
        for item in report.get("errors", []) or []:
            problems.append(str(item.get("message") or item.get("code") or "error"))
        for item in report.get("warnings", []) or []:
            problems.append(str(item.get("message") or item.get("code") or "warning"))
        if not problems:
            return tt("Quality check passed", self.lang)
        return f"{tt('Review warnings', self.lang)}: " + " | ".join(problems[:4])

    def _dedupe_contour_points(self, points):
        clean = []
        width = int(self.image_volume.shape[2]) if self.image_volume is not None else 0
        height = int(self.image_volume.shape[1]) if self.image_volume is not None else 0
        for point in points or []:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            px = int(round(float(point[0])))
            py = int(round(float(point[1])))
            if width > 0:
                px = max(0, min(width - 1, px))
            if height > 0:
                py = max(0, min(height - 1, py))
            next_point = [px, py]
            if not clean or clean[-1] != next_point:
                clean.append(next_point)
        if len(clean) > 2 and clean[0] == clean[-1]:
            clean.pop()
        return clean

    def current_contour_overlay_polygons(self):
        if self.current_volume_scope != "part" or self.image_volume is None:
            return []
        axis, slice_index = self._active_slice_position()
        contours_path = self._current_part_contours_path()
        if not contours_path:
            return []
        contours = read_contours_json(contours_path)
        overlays = []
        for keyframe in contours.get("keyframes", []) or []:
            if not isinstance(keyframe, dict):
                continue
            if str(keyframe.get("axis", "z")) != axis:
                continue
            if self._safe_contour_slice_index(keyframe, None) != int(slice_index):
                continue
            polygon = keyframe.get("polygon") or []
            clean_polygon = self._dedupe_contour_points(polygon)
            if len(clean_polygon) >= 3:
                overlays.append({"polygon": clean_polygon, "color": "#FF8C42", "fill_alpha": 30})
        return overlays

    def finish_part_contour_drag(self, points):
        if not self.is_part_contour_draw_mode() or self.image_volume is None:
            return
        polygon = self._dedupe_contour_points(points)
        if len(polygon) < 3:
            message = tt("Contour needs at least 3 points.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
            return
        contours, contours_path = self._current_part_contours()
        if not contours_path:
            return
        slice_index = int(self.slice_slider.value())
        try:
            contours = add_polygon_keyframe(
                contours,
                slice_index,
                polygon,
                axis="z",
                author="taxamask_ui_freehand",
                source="manual_freehand",
            )
            write_contours_json(contours_path, contours)
            part = self.project.update_part_status(self.current_specimen_id, self.current_part_id, "draft")
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        self.current_part = part
        self.part_preview_mask = None
        self._update_status_labels(self.project.get_specimen(self.current_specimen_id), part=part)
        self.render_current_slice()
        message = tt("Contour saved at Z {0}.", self.lang).format(slice_index)
        self.training_status_label.setText(message)
        self.log(message)

    def delete_current_part_keyframe(self):
        if self.current_volume_scope != "part" or self.image_volume is None:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Select a part volume before editing part masks.", self.lang))
            return
        if self._current_slice_axis() != "z":
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Contour drawing currently uses Z slices.", self.lang))
            return
        contours, contours_path = self._current_part_contours()
        if not contours_path:
            return
        slice_index = int(self.slice_slider.value())
        contours, deleted = delete_keyframe(contours, slice_index, axis="z")
        if not deleted:
            message = tt("No contour exists at Z {0}.", self.lang).format(slice_index)
            self.training_status_label.setText(message)
            self.log(message)
            return
        write_contours_json(contours_path, contours)
        part = self.project.update_part_status(self.current_specimen_id, self.current_part_id, "draft")
        self.current_part = part
        self.part_preview_mask = None
        self._update_status_labels(self.project.get_specimen(self.current_specimen_id), part=part)
        self.render_current_slice()
        message = tt("Deleted contour at Z {0}.", self.lang).format(slice_index)
        self.training_status_label.setText(message)
        self.log(message)

    def jump_part_keyframe(self, direction):
        if self.current_volume_scope != "part" or self.image_volume is None:
            return
        if self._current_slice_axis() != "z":
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Contour drawing currently uses Z slices.", self.lang))
            return
        contours, _contours_path = self._current_part_contours()
        neighbors = neighboring_keyframe_indices(contours, int(self.slice_slider.value()), axis="z")
        target = neighbors.get("previous" if direction == "previous" else "next")
        if target is None:
            message = tt("No previous key slice." if direction == "previous" else "No next key slice.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
            return
        self.slice_slider.setValue(int(target))
        self.render_current_slice()

    def _part_keyframe_bbox_yx(self):
        if self.image_volume is None:
            return []
        height = int(self.image_volume.shape[1])
        width = int(self.image_volume.shape[2])
        y_margin = max(0, int(round(height * 0.18)))
        x_margin = max(0, int(round(width * 0.18)))
        return [[y_margin, max(y_margin + 1, height - y_margin)], [x_margin, max(x_margin + 1, width - x_margin)]]

    def add_current_rect_keyframe(self):
        if self.current_volume_scope != "part" or self.image_volume is None:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Select a part volume before editing part masks.", self.lang))
            return
        if self._current_slice_axis() != "z":
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Key-slice mask preview currently uses Z slices.", self.lang))
            return
        contours_path = self._current_part_contours_path()
        if not contours_path:
            return
        contours = read_contours_json(contours_path)
        contours = add_rectangular_keyframe(
            contours,
            int(self.slice_slider.value()),
            self._part_keyframe_bbox_yx(),
            author="taxamask_ui_rect",
        )
        write_contours_json(contours_path, contours)
        part = self.project.update_part_status(self.current_specimen_id, self.current_part_id, "draft")
        self.current_part = part
        self.part_preview_mask = None
        self._clear_volume_preview_cache()
        self._update_status_labels(self.project.get_specimen(self.current_specimen_id), part=part)
        self.render_current_slice()
        message = tt("Added rectangular key slice at Z {0}.", self.lang).format(int(self.slice_slider.value()))
        self.training_status_label.setText(message)
        self.log(message)

    def preview_part_mask_from_keyframes(self):
        if self.current_volume_scope != "part" or self.image_volume is None:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Select a part volume before previewing masks.", self.lang))
            return
        contours_path = self._current_part_contours_path()
        contours = read_contours_json(contours_path)
        report = validate_contours_for_interpolation(contours, self.image_volume.shape, axis="z")
        if not report.get("ok"):
            QMessageBox.warning(self, tt("Part extraction", self.lang), self._format_contour_quality_report(report))
            return
        try:
            self.part_preview_mask = build_preview_mask_from_contours(contours, self.image_volume.shape)
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        part = self.project.update_part_status(self.current_specimen_id, self.current_part_id, "mask_preview")
        self.current_part = part
        self._update_status_labels(self.project.get_specimen(self.current_specimen_id), part=part)
        self.render_current_slice()
        quality = self._format_contour_quality_report(report)
        message = (
            tt("Preview mask generated from {0} key slice(s).", self.lang).format(len(contours.get("keyframes", [])))
            + "\n"
            + tt("Part mask preview quality: {0}", self.lang).format(quality)
        )
        self.training_status_label.setText(message)
        self.log(message)

    def accept_part_mask_preview(self):
        if self.current_volume_scope != "part" or self.part_preview_mask is None:
            return
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        if part is None:
            return
        try:
            metadata = write_part_mask(self.project, part, self.part_preview_mask)
            part["mask"].update(
                {
                    "shape_zyx": metadata.get("shape_zyx", []),
                    "dtype": metadata.get("dtype", ""),
                    "spacing_zyx": metadata.get("spacing_zyx", []),
                    "spacing_unit": metadata.get("spacing_unit", "micrometer"),
                    "orientation": metadata.get("orientation", "unknown"),
                }
            )
            part = self.project.update_part_status(self.current_specimen_id, self.current_part_id, "reviewed")
            self.project.save_project()
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        self.part_preview_mask = None
        self._clear_volume_preview_cache()
        self.current_part = part
        self._reload_label_volume()
        self._update_status_labels(self.project.get_specimen(self.current_specimen_id), part=part)
        self.render_current_slice()
        message = tt("Accepted part mask.", self.lang)
        self.training_status_label.setText(message)
        self.log(message)

    def clear_part_mask_preview(self):
        self.part_preview_mask = None
        self._clear_volume_preview_cache()
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        if part is not None:
            self.current_part = part
            self._update_status_labels(self.project.get_specimen(self.current_specimen_id), part=part)
        self.render_current_slice()

    def import_external_prediction_tif_dialog(self):
        if not self._ensure_tif_project_open():
            return
        if not self.current_specimen_id:
            QMessageBox.warning(
                self,
                tt("Import External Label TIF", self.lang),
                tt("Please select a specimen with a working volume first.", self.lang),
            )
            return
        specimen_id = self.current_specimen_id
        specimen = self.project.get_specimen(specimen_id, default=None)
        working = (specimen or {}).get("working_volume") or {}
        if not working.get("path") or not volume_sidecar_exists(self.project.to_absolute(working.get("path", ""))):
            QMessageBox.warning(
                self,
                tt("Import External Label TIF", self.lang),
                tt("Please select a specimen with a working volume first.", self.lang),
            )
            return
        tif_path, _ = QFileDialog.getOpenFileName(
            self,
            tt("Import External Label TIF", self.lang),
            "",
            "TIF/TIFF (*.tif *.tiff)",
        )
        if not tif_path:
            return
        prediction_id, ok = QInputDialog.getText(
            self,
            tt("Import External Label TIF", self.lang),
            tt("Prediction ID:", self.lang),
            text=default_prediction_id_for_tif(tif_path),
        )
        if not ok or not prediction_id:
            return
        source_model, ok = QInputDialog.getText(
            self,
            tt("Import External Label TIF", self.lang),
            tt("Source model:", self.lang),
            text="nnUNet",
        )
        if not ok:
            return
        try:
            result = import_external_prediction_tif(
                self.project,
                specimen_id,
                tif_path,
                prediction_id=prediction_id,
                source_model=source_model or "external_tif",
            )
        except Exception as exc:
            QMessageBox.critical(self, tt("Import External Label TIF", self.lang), str(exc))
            return
        self.refresh_project()
        self._select_specimen_after_import(specimen_id)
        index = self.label_role_combo.findData("model_draft")
        if index >= 0:
            self.label_role_combo.setCurrentIndex(index)
        self.load_specimen(specimen_id)
        report_path = result.get("report_path", "")
        message = tt("Imported external label TIF as model draft for specimen {0}. Report: {1}", self.lang).format(specimen_id, report_path)
        self.training_status_label.setText(message)
        self.log(message)

    def _selected_specimen_ids_for_action(self, action):
        if action in {"prepare_dataset", "train"}:
            ready = [item.get("specimen_id") for item in self.project.list_train_ready_specimens()]
            if not ready:
                raise ValueError("No train-ready specimens are available.")
            return ready
        ids = [self.current_specimen_id] if self.current_specimen_id else []
        if not ids:
            ids = [item.get("specimen_id") for item in self.project.project_data.get("specimens", [])]
        if not ids:
            raise ValueError("No specimen is available for prediction.")
        return ids

    def run_backend_action(self, action):
        if not self._ensure_tif_project_open():
            return
        self.backend_config = self._backend_config_from_ui()
        if self.config_manager is not None:
            self.config_manager.set("tif_backend", dict(self.backend_config))
            self.config_manager.save()
        command_key = {
            "prepare_dataset": "prepare_dataset_command",
            "train": "train_command",
            "predict": "predict_command",
        }.get(action, "")
        if command_key and not self.backend_config.get(command_key, "").strip():
            QMessageBox.warning(self, tt("TIF backend", self.lang), tt("No command configured for this backend action.", self.lang))
            return
        try:
            specimen_ids = self._selected_specimen_ids_for_action(action)
            running_message = tt("Running {0}...", self.lang).format(action)
            self.training_status_label.setText(running_message)
            self.log(running_message)
            runner = TifBackendRunner(self.project, self.backend_config)
            result = runner.run_action(
                action,
                specimen_ids=specimen_ids,
                model_manifest=self.backend_config.get("model_manifest", ""),
            )
        except Exception as exc:
            message = tt("Action failed: {0}", self.lang).format(str(exc))
            self.training_status_label.setText(message)
            self.log(message)
            QMessageBox.warning(self, tt("TIF backend", self.lang), str(exc))
            return
        imported_id = self.current_specimen_id
        self.refresh_project()
        if action == "predict" and imported_id:
            self._select_specimen_after_import(imported_id)
            index = self.label_role_combo.findData("model_draft")
            if index >= 0:
                self.label_role_combo.setCurrentIndex(index)
        message = tt("Action finished: {0}\nRun: {1}", self.lang).format(action, result.get("run_dir", ""))
        self.training_status_label.setText(message)
        self.log(message)
        QMessageBox.information(
            self,
            tt("TIF backend", self.lang),
            message,
        )

    def _make_panel(self, title, object_name):
        panel = QFrame()
        panel.setObjectName(object_name)
        panel.setFrameShape(QFrame.NoFrame)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("tifPanelTitle")
        layout.addWidget(title_label)
        if not hasattr(self, "_panel_title_labels"):
            self._panel_title_labels = {}
        self._panel_title_labels[object_name] = (title, title_label)
        return panel, layout

    def _make_section(self, title, object_name):
        section = QFrame()
        section.setObjectName(object_name)
        section.setFrameShape(QFrame.NoFrame)
        section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("tifSectionTitle")
        layout.addWidget(title_label)
        if not hasattr(self, "_section_title_labels"):
            self._section_title_labels = {}
        self._section_title_labels[object_name] = (title, title_label)
        return section, layout

    def _make_task_page(self, object_name):
        scroll = QScrollArea()
        scroll.setObjectName("tifInspectorScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName(object_name)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        scroll.setWidget(body)
        return scroll, layout

    def _build_layout(self):
        self._field_labels = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        top_bar = QFrame()
        top_bar.setObjectName("tifWorkbenchTopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 8, 12, 8)
        top_layout.setSpacing(8)
        self.tif_top_context_label = QLabel("TIF Volume Workbench")
        self.tif_top_context_label.setObjectName("tifTopContextLabel")
        top_layout.addWidget(self.tif_top_context_label, 1)
        top_layout.addWidget(self.btn_start_center)
        top_layout.addWidget(self.btn_ask_agent)
        root.addWidget(top_bar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("tifWorkbenchSplitter")
        root.addWidget(splitter, 1)

        left, left_layout = self._make_panel("Specimens", "tifSpecimenPanel")
        left_layout.addWidget(self.specimen_list, 1)
        splitter.addWidget(left)

        center, center_layout = self._make_panel("Volume slices", "tifVolumePanel")
        canvas_shell = QFrame()
        canvas_shell.setObjectName("tifCanvasShell")
        canvas_layout = QVBoxLayout(canvas_shell)
        canvas_layout.setContentsMargins(6, 6, 6, 6)
        self.view_stack = QStackedWidget()
        self.view_stack.setObjectName("tifViewStack")
        self.view_stack.addWidget(self.canvas)
        self.view_stack.addWidget(self.volume_canvas)
        canvas_layout.addWidget(self.view_stack, 1)
        canvas_layout.addWidget(self.volume_render_status_label)
        center_layout.addWidget(canvas_shell, 1)
        slice_bar = QFrame()
        slice_bar.setObjectName("tifSliceBar")
        slice_row = QHBoxLayout()
        slice_row.setContentsMargins(10, 6, 10, 6)
        self.display_mode_label = QLabel("Display mode")
        slice_row.addWidget(self.display_mode_label)
        slice_row.addWidget(self.display_mode_combo)
        self.slice_axis_label = QLabel("View plane")
        slice_row.addWidget(self.slice_axis_label)
        slice_row.addWidget(self.slice_axis_combo)
        slice_row.addWidget(self.slice_prefix_label)
        slice_row.addWidget(self.slice_slider, 1)
        slice_row.addWidget(self.slice_label)
        slice_bar.setLayout(slice_row)
        center_layout.addWidget(slice_bar)
        splitter.addWidget(center)

        right, right_layout = self._make_panel("Volume controls", "tifControlPanel")
        right.setMinimumWidth(360)
        right.setMaximumWidth(520)

        self.task_tabs = QTabWidget()
        self.task_tabs.setObjectName("tifTaskTabs")
        right_layout.addWidget(self.task_tabs, 1)

        self.part_task_page, self.part_task_layout = self._make_task_page("tifPartTaskPage")
        self.display_task_page, self.display_task_layout = self._make_task_page("tifDisplayTaskPage")
        self.annotation_task_page, self.annotation_task_layout = self._make_task_page("tifAnnotationTaskPage")
        self.training_task_page, self.training_task_layout = self._make_task_page("tifTrainingTaskPage")
        self.task_tabs.addTab(self.part_task_page, tt("Part", self.lang))
        self.task_tabs.addTab(self.display_task_page, tt("Display", self.lang))
        self.task_tabs.addTab(self.annotation_task_page, tt("Annotation", self.lang))
        self.task_tabs.addTab(self.training_task_page, tt("Train/export", self.lang))

        import_section, import_layout = self._make_section("Data import", "tifImportSection")
        import_button_row = QHBoxLayout()
        import_button_row.addWidget(self.btn_import_tif)
        import_button_row.addWidget(self.btn_import_amira)
        import_layout.addLayout(import_button_row)
        self.part_task_layout.addWidget(import_section)

        status_section, status_layout = self._make_section("Current object", "tifStatusSection")
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.show_debug_paths_check)
        status_layout.addWidget(self.metadata_label)
        self.part_task_layout.addWidget(status_section)

        self.part_locate_section, part_locate_layout = self._make_section("1. Locate part", "tifPartLocateSection")
        part_locate_layout.addWidget(self.part_bbox_edit)
        part_bbox_row = QHBoxLayout()
        part_bbox_row.addWidget(self.btn_part_default_bbox)
        part_bbox_row.addWidget(self.btn_part_draw_roi)
        part_locate_layout.addLayout(part_bbox_row)
        part_draft_row = QHBoxLayout()
        part_draft_row.addWidget(self.btn_save_part_roi)
        part_draft_row.addWidget(self.btn_confirm_part_roi)
        part_locate_layout.addLayout(part_draft_row)
        part_action_row = QHBoxLayout()
        part_action_row.addWidget(self.btn_create_part)
        part_action_row.addWidget(self.btn_cancel_part_roi)
        part_locate_layout.addLayout(part_action_row)
        self.part_task_layout.addWidget(self.part_locate_section)

        self.part_mask_section, part_mask_layout = self._make_section("2. Build part mask", "tifPartMaskSection")
        part_key_row = QHBoxLayout()
        part_key_row.addWidget(self.btn_add_rect_keyframe)
        part_key_row.addWidget(self.btn_draw_part_contour)
        part_mask_layout.addLayout(part_key_row)
        part_key_nav_row = QHBoxLayout()
        part_key_nav_row.addWidget(self.btn_prev_key_slice)
        part_key_nav_row.addWidget(self.btn_next_key_slice)
        part_mask_layout.addLayout(part_key_nav_row)
        part_key_action_row = QHBoxLayout()
        part_key_action_row.addWidget(self.btn_delete_part_contour)
        part_key_action_row.addWidget(self.btn_preview_part_mask)
        part_mask_layout.addLayout(part_key_action_row)
        part_mask_row = QHBoxLayout()
        part_mask_row.addWidget(self.btn_accept_part_mask)
        part_mask_row.addWidget(self.btn_clear_part_preview)
        part_mask_layout.addLayout(part_mask_row)
        self.part_task_layout.addWidget(self.part_mask_section)

        self.local_axis_volume_section, local_axis_volume_layout = self._make_section(
            "Local Axis Reslice / part volume",
            "tifLocalAxisVolumeSection",
        )
        self.local_axis_volume_help_label = QLabel(
            tt(
                "Work in the 3D part preview first. Source Z is locked; copy it to create an editable output Z draft, then use the detail dialog only for precise MPR picking, roll reference, preview, and export.",
                self.lang,
            )
        )
        self.local_axis_volume_help_label.setObjectName("tifLayerHelpText")
        self.local_axis_volume_help_label.setWordWrap(True)
        local_axis_volume_layout.addWidget(self.local_axis_volume_help_label)
        local_axis_volume_layout.addWidget(self.local_axis_summary_label)
        local_axis_volume_row = QHBoxLayout()
        local_axis_volume_row.addWidget(self.btn_copy_source_z_axis)
        local_axis_volume_row.addWidget(self.btn_local_axis_reslice)
        local_axis_volume_layout.addLayout(local_axis_volume_row)
        local_axis_volume_layout.addWidget(self.btn_local_axis_queue)
        self.part_task_layout.addWidget(self.local_axis_volume_section)

        self.part_output_section, part_output_layout = self._make_section("3. Output and manage", "tifPartOutputSection")
        part_output_layout.addWidget(self.btn_export_part_package)
        part_output_layout.addWidget(self.btn_delete_part_volume)
        self.part_task_layout.addWidget(self.part_output_section)

        self.slice_display_section, slice_display_layout = self._make_section("Slice display", "tifSliceDisplaySection")
        slice_controls = QGridLayout()
        slice_controls.setHorizontalSpacing(10)
        slice_controls.setVerticalSpacing(8)
        self.label_layer_label = QLabel("Label layer")
        self.overlay_label = QLabel("Overlay")
        self.brightness_label = QLabel("Brightness")
        self.contrast_label = QLabel("Contrast")
        slice_controls.addWidget(self.overlay_label, 0, 0)
        slice_controls.addWidget(self.opacity_slider, 0, 1)
        slice_controls.addWidget(self.brightness_label, 1, 0)
        slice_controls.addWidget(self.brightness_slider, 1, 1)
        slice_controls.addWidget(self.contrast_label, 2, 0)
        slice_controls.addWidget(self.contrast_slider, 2, 1)
        slice_display_layout.addLayout(slice_controls)
        self.display_task_layout.addWidget(self.slice_display_section)

        self.volume_render_section, volume_render_layout = self._make_section("3D rendering", "tifVolumeRenderSection")
        volume_controls = QGridLayout()
        volume_controls.setHorizontalSpacing(10)
        volume_controls.setVerticalSpacing(8)
        self.volume_projection_label = QLabel("Render mode")
        self.volume_tint_label = QLabel("Transfer function")
        self.volume_enhancement_label = QLabel("Detail enhancement")
        self.volume_tone_label = QLabel("Tone curve")
        self.volume_mask_label = QLabel("Mask display")
        self.volume_mask_opacity_label = QLabel("Mask opacity")
        self.volume_cutoff_label = QLabel("Density cutoff")
        self.volume_quality_label = QLabel("Render quality")
        self.volume_sample_label = QLabel("Ray samples")
        self.volume_roi_scale_label = QLabel("ROI scale")
        self.volume_clip_plane_depth_label = QLabel("Clip depth")
        self.volume_inside_label = QLabel("Inside depth")
        self.volume_clip_label = QLabel("Front cut")
        volume_controls.addWidget(self.volume_projection_label, 0, 0)
        volume_controls.addWidget(self.volume_projection_combo, 0, 1)
        volume_controls.addWidget(self.volume_tint_label, 1, 0)
        color_row = QHBoxLayout()
        color_row.addWidget(self.volume_tint_combo, 1)
        color_row.addWidget(self.btn_volume_custom_color)
        volume_controls.addLayout(color_row, 1, 1)
        self.volume_transfer_opacity_label = QLabel("Density opacity")
        volume_controls.addWidget(self.volume_transfer_opacity_label, 2, 0)
        volume_controls.addWidget(self.volume_transfer_opacity_slider, 2, 1)
        volume_controls.addWidget(self.volume_enhancement_label, 3, 0)
        volume_controls.addWidget(self.volume_enhancement_slider, 3, 1)
        volume_controls.addWidget(self.volume_tone_label, 4, 0)
        volume_controls.addWidget(self.volume_tone_slider, 4, 1)
        volume_controls.addWidget(self.volume_mask_label, 5, 0)
        volume_controls.addWidget(self.volume_mask_combo, 5, 1)
        volume_controls.addWidget(self.volume_mask_opacity_label, 6, 0)
        volume_controls.addWidget(self.volume_mask_opacity_slider, 6, 1)
        volume_controls.addWidget(self.volume_local_axes_check, 7, 0, 1, 2)
        volume_controls.addWidget(self.volume_cutoff_label, 8, 0)
        volume_controls.addWidget(self.volume_cutoff_slider, 8, 1)
        volume_controls.addWidget(self.volume_quality_label, 9, 0)
        volume_controls.addWidget(self.volume_quality_slider, 9, 1)
        volume_controls.addWidget(self.volume_sample_label, 10, 0)
        volume_controls.addWidget(self.volume_sample_slider, 10, 1)
        volume_controls.addWidget(self.volume_clarity_check, 11, 0, 1, 2)
        volume_controls.addWidget(self.volume_surface_refine_check, 12, 0, 1, 2)
        volume_controls.addWidget(self.volume_roi_detail_check, 13, 0, 1, 2)
        volume_controls.addWidget(self.volume_roi_scale_label, 14, 0)
        volume_controls.addWidget(self.volume_roi_scale_slider, 14, 1)
        volume_controls.addWidget(self.volume_clip_plane_check, 15, 0, 1, 2)
        volume_controls.addWidget(self.volume_clip_plane_depth_label, 16, 0)
        volume_controls.addWidget(self.volume_clip_plane_depth_slider, 16, 1)
        volume_controls.addWidget(self.volume_inside_label, 17, 0)
        volume_controls.addWidget(self.volume_inside_slider, 17, 1)
        volume_controls.addWidget(self.volume_clip_label, 18, 0)
        volume_controls.addWidget(self.volume_clip_slider, 18, 1)
        volume_render_layout.addLayout(volume_controls)
        volume_render_layout.addWidget(self.btn_reset_volume_view)
        self.display_task_layout.addWidget(self.volume_render_section)

        self.annotation_section, annotation_layout = self._make_section("Annotation tools", "tifAnnotationSection")
        controls = QGridLayout()
        controls.setHorizontalSpacing(10)
        controls.setVerticalSpacing(8)
        self.brush_size_label = QLabel("Brush size")
        controls.addWidget(self.label_layer_label, 0, 0)
        controls.addWidget(self.label_role_combo, 0, 1)
        controls.addWidget(self.brush_size_label, 1, 0)
        controls.addWidget(self.brush_size_slider, 1, 1)
        annotation_layout.addLayout(controls)
        annotation_layout.addWidget(self.label_role_help_label)
        button_row = QHBoxLayout()
        button_row.addWidget(self.btn_undo)
        button_row.addWidget(self.btn_redo)
        annotation_layout.addLayout(button_row)
        annotation_layout.addWidget(self.auto_save_check)
        annotation_layout.addWidget(self.btn_save_edit)
        annotation_layout.addWidget(self.btn_promote)
        annotation_layout.addWidget(self.btn_copy_draft)
        self.annotation_task_layout.addWidget(self.annotation_section)

        material_section, material_layout = self._make_section("Material map", "tifMaterialSection")
        material_button_row = QHBoxLayout()
        material_button_row.addWidget(self.btn_add_material)
        material_button_row.addWidget(self.btn_edit_material)
        material_button_row.addWidget(self.btn_delete_material)
        material_layout.addLayout(material_button_row)
        material_layout.addWidget(self.material_table)
        self.annotation_task_layout.addWidget(material_section)

        training_section, training_layout = self._make_section("Model training", "tifTrainingSection")
        training_layout.addWidget(self.btn_export_training)
        backend_button_row = QHBoxLayout()
        backend_button_row.addWidget(self.btn_prepare_dataset)
        backend_button_row.addWidget(self.btn_train_backend)
        backend_button_row.addWidget(self.btn_import_prediction)
        training_layout.addLayout(backend_button_row)
        training_layout.addWidget(self.btn_import_external_prediction_tif)
        training_layout.addWidget(self.btn_local_axis_models)
        training_layout.addWidget(self.training_status_label)
        self.training_task_layout.addWidget(training_section)

        backend_section, backend_layout = self._make_section("Model configuration", "tifBackendSection")
        backend_form = QFormLayout()
        backend_form.setHorizontalSpacing(8)
        backend_form.setVerticalSpacing(6)
        self.backend_id_label = QLabel("Backend ID")
        self.backend_display_label = QLabel("Display name")
        self.backend_python_label = QLabel("Python")
        self.backend_formats_label = QLabel("Export formats")
        self.backend_prepare_label = QLabel("Prepare command")
        self.backend_train_label = QLabel("Train command")
        self.backend_predict_label = QLabel("Predict command")
        self.backend_manifest_label = QLabel("Model manifest")
        backend_form.addRow(self.backend_id_label, self.backend_id_edit)
        backend_form.addRow(self.backend_display_label, self.backend_display_edit)
        backend_form.addRow(self.backend_python_label, self.backend_python_edit)
        backend_form.addRow(self.backend_formats_label, self.backend_formats_edit)
        backend_form.addRow(self.backend_prepare_label, self.backend_prepare_edit)
        backend_form.addRow(self.backend_train_label, self.backend_train_edit)
        backend_form.addRow(self.backend_predict_label, self.backend_predict_edit)
        backend_form.addRow(self.backend_manifest_label, self.backend_manifest_edit)
        backend_layout.addLayout(backend_form)
        backend_layout.addWidget(self.btn_save_backend)
        self.training_task_layout.addWidget(backend_section)

        log_section, log_layout = self._make_section("Workbench log", "tifLogSection")
        log_layout.addWidget(self.log_console)
        self.training_task_layout.addWidget(log_section)
        self.part_task_layout.addStretch(1)
        self.display_task_layout.addStretch(1)
        self.annotation_task_layout.addStretch(1)
        self.training_task_layout.addStretch(1)
        splitter.addWidget(right)

        splitter.setSizes([230, 900, 420])

    def _apply_soft_style(self):
        self.setStyleSheet(
            """
            QWidget#tifWorkbenchRoot {
                background: #15191D;
            }
            QFrame#tifSpecimenPanel,
            QFrame#tifVolumePanel,
            QFrame#tifControlPanel,
            QFrame#tifWorkbenchTopBar {
                background: #1B2024;
                border: 1px solid #2F3A40;
                border-radius: 12px;
            }
            QLabel#tifTopContextLabel {
                color: #DCE4E8;
                font-weight: 700;
                border: none;
            }
            QFrame#tifImportSection,
            QFrame#tifPartExtractionSection,
            QFrame#tifSliceDisplaySection,
            QFrame#tifVolumeRenderSection,
            QFrame#tifLocalAxisVolumeSection,
            QFrame#tifAnnotationSection,
            QFrame#tifMaterialSection,
            QFrame#tifTrainingSection,
            QFrame#tifBackendSection,
            QFrame#tifStatusSection,
            QFrame#tifLogSection {
                background: #20262B;
                border: 1px solid #334047;
                border-radius: 12px;
            }
            QWidget#tifInspectorBody {
                background: transparent;
            }
            QScrollArea#tifInspectorScroll {
                background: transparent;
                border: none;
            }
            QLabel#tifPanelTitle {
                color: #DCE4E8;
                font-weight: 700;
                padding-bottom: 4px;
                border: none;
            }
            QLabel#tifSectionTitle {
                color: #B9C5CA;
                font-weight: 700;
                margin-top: 8px;
                border: none;
            }
            QFrame#tifCanvasShell {
                background: #0A0D0F;
                border: 1px solid #2F3A40;
                border-radius: 12px;
            }
            QLabel#tifSliceCanvas {
                background: #07090A;
                color: #859098;
                border: none;
                border-radius: 10px;
            }
            #tifVolumeCanvas {
                background: #07090A;
                color: #859098;
                border: none;
                border-radius: 10px;
            }
            QLabel#tifVolumeRenderStatus {
                background: #111619;
                color: #B9C5CA;
                border: 1px solid #2B363B;
                border-radius: 8px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QFrame#tifSliceBar {
                background: #182023;
                border: 1px solid #2B363B;
                border-radius: 12px;
            }
            QTreeWidget#tifSpecimenList,
            QTableWidget#tifMaterialTable {
                background: #111619;
                alternate-background-color: #171D20;
                border: 1px solid #2D373D;
                border-radius: 10px;
                padding: 2px;
                selection-background-color: #31525D;
                selection-color: #F4FAFC;
            }
            QTableWidget#tifMaterialTable::item,
            QTreeWidget#tifSpecimenList::item {
                min-height: 24px;
                padding: 4px;
                border: none;
            }
            QTableWidget#tifMaterialTable QHeaderView::section {
                background: #222A2F;
                color: #D7E0E4;
                border: none;
                border-right: 1px solid #303B42;
                padding: 5px 6px;
                font-weight: 700;
            }
            QLineEdit {
                background: #111619;
                color: #DCE4E8;
                border: 1px solid #2D373D;
                border-radius: 8px;
                padding: 4px 6px;
                selection-background-color: #31525D;
            }
            QPushButton {
                background: #26323A;
                color: #EEF6F8;
                border: 1px solid #4A5A63;
                border-radius: 10px;
                padding: 8px 12px;
                font-weight: 700;
                min-height: 18px;
            }
            QPushButton:hover {
                background: #31414B;
                border-color: #6C828E;
            }
            QPushButton:pressed {
                background: #1C252B;
                border-color: #8CA4AF;
                padding-top: 9px;
                padding-bottom: 7px;
            }
            QPushButton:disabled {
                background: #1A2024;
                color: #6C777D;
                border-color: #2B3338;
            }
            QPushButton[tifRole="primary"] {
                background: #2D6472;
                border: 1px solid #67A8B8;
                color: #F5FCFF;
            }
            QPushButton[tifRole="primary"]:hover {
                background: #37788A;
                border-color: #91C7D3;
            }
            QPushButton[tifRole="primary"]:pressed {
                background: #245563;
                border-color: #B2DCE4;
            }
            QPushButton[tifRole="secondary"] {
                background: #253038;
                border: 1px solid #4C5B64;
                color: #DCE7EB;
            }
            QPushButton[tifRole="secondary"]:hover {
                background: #303D46;
                border-color: #71848F;
            }
            QPushButton[tifRole="danger"] {
                background: #3B2528;
                border: 1px solid #8D4B55;
                color: #FFE9EC;
            }
            QPushButton[tifRole="danger"]:hover {
                background: #512D33;
                border-color: #B66974;
            }
            QPushButton[tifRole="danger"]:pressed {
                background: #2D1C20;
                border-color: #D98A94;
            }
            QTextEdit#tifLogConsole {
                background: #101518;
                color: #B8C4CA;
                border: 1px solid #2A353B;
                border-radius: 10px;
                padding: 6px;
            }
            QLabel#tifLayerHelpText {
                color: #B8C4CA;
                background: #12191D;
                border: 1px solid #2C3840;
                border-radius: 8px;
                padding: 6px 8px;
            }
            QLabel#tifStatusText,
            QLabel#tifMetadataText,
            QLabel#tifLocalAxisSummaryText,
            QLabel#tifTrainingStatusText {
                color: #AEBAC0;
                border: none;
            }
            QPushButton#tifExportTrainingButton,
            QPushButton#tifPrepareDatasetButton,
            QPushButton#tifTrainBackendButton,
            QPushButton#tifImportPredictionButton,
            QPushButton#tifImportStackButton,
            QPushButton#tifImportAmiraButton {
                font-weight: 700;
            }
            """
        )

    def set_project_manager(self, project_manager):
        if not self._confirm_discard_or_save_working_edit():
            return
        self.close_project(prompt_unsaved=False)
        self.project = project_manager
        self.refresh_project()

    def set_config_manager(self, config_manager):
        self.config_manager = config_manager
        config = self.config_manager.get("tif_backend", DEFAULT_TIF_BACKEND_CONFIG) if self.config_manager is not None else DEFAULT_TIF_BACKEND_CONFIG
        self.backend_config = sanitize_tif_backend_config(config)
        self._load_backend_config_into_ui()

    def _handle_slice_shortcut_key(self, key):
        if self.display_mode == "slice":
            if key == Qt.Key_Left:
                self.move_slice(-1)
                return True
            if key == Qt.Key_Right:
                self.move_slice(1)
                return True
            if key == Qt.Key_Up:
                self.canvas.zoom_in()
                return True
            if key == Qt.Key_Down:
                self.canvas.zoom_out()
                return True
        return False

    def keyPressEvent(self, event):
        if self._handle_slice_shortcut_key(event.key()):
            event.accept()
            return
        super().keyPressEvent(event)

    def close_project(self, prompt_unsaved=True):
        if prompt_unsaved and not self._confirm_discard_or_save_working_edit():
            return False
        self.release_volume_renderer()
        self.image_volume = None
        self.label_volume = None
        self.material_map = {}
        self.material_colors = {}
        self.current_specimen_id = ""
        self.edit_volume = None
        self._clear_volume_preview_cache()
        self._dirty_edit_slices = set()
        self.auto_save_timer.stop()
        if hasattr(self, "volume_still_timer"):
            self.volume_still_timer.stop()
        self.working_edit_dirty = False
        self.current_volume_scope = "full"
        self.current_part_id = ""
        self.current_part = None
        self.local_axis_draft = None
        self.part_preview_mask = None
        self.undo_stack = []
        self.redo_stack = []
        self.canvas.clear()
        self.volume_canvas.clear()
        self.canvas.setText(tt("No TIF volume loaded", self.lang))
        self.volume_canvas.setText(tt("No TIF volume loaded", self.lang))
        self._update_volume_render_status_label(tt("No TIF volume loaded", self.lang))
        return True

    def prepare_for_agent_panel(self):
        if hasattr(self, "volume_still_timer"):
            self.volume_still_timer.stop()
        if self.display_mode != "volume":
            self._reset_volume_canvas_placeholder_for_agent()
            return
        self.display_mode = "slice"
        index = self.display_mode_combo.findData("slice") if hasattr(self, "display_mode_combo") else -1
        if index >= 0:
            self.display_mode_combo.blockSignals(True)
            self.display_mode_combo.setCurrentIndex(index)
            self.display_mode_combo.blockSignals(False)
        self.on_display_mode_changed()
        self._reset_volume_canvas_placeholder_for_agent()

    def release_volume_renderer(self):
        canvas = getattr(self, "volume_canvas", None)
        if canvas is not None and hasattr(canvas, "release_gl_resources"):
            try:
                canvas.release_gl_resources()
            except Exception:
                pass

    def _current_slice_axis(self):
        axis = self.slice_axis_combo.currentData() if hasattr(self, "slice_axis_combo") else self.slice_axis
        return axis if axis in {"z", "y", "x"} else "z"

    def _slice_axis_dim(self, axis):
        return {"z": 0, "y": 1, "x": 2}.get(axis, 0)

    def _slice_count_for_axis(self, axis=None):
        if self.image_volume is None:
            return 1
        axis = axis or self._current_slice_axis()
        dim = self._slice_axis_dim(axis)
        return max(1, int(self.image_volume.shape[dim]))

    def _configure_slice_slider_for_axis(self, axis=None, preserve_position=True):
        axis = axis or self._current_slice_axis()
        count = self._slice_count_for_axis(axis)
        position = int(self._slice_positions.get(axis, 0)) if preserve_position else 0
        position = max(0, min(count - 1, position))
        self.slice_slider.blockSignals(True)
        self.slice_slider.setRange(0, count - 1)
        self.slice_slider.setValue(position)
        self.slice_slider.blockSignals(False)
        self._slice_positions[axis] = position
        self.slice_label.setText(f"{position + 1} / {count}")

    def _active_slice_position(self):
        axis = self._current_slice_axis()
        count = self._slice_count_for_axis(axis)
        index = max(0, min(int(self.slice_slider.value()), count - 1))
        self._slice_positions[axis] = index
        return axis, index

    def closeEvent(self, event):
        if not self.close_project(prompt_unsaved=True):
            event.ignore()
            return
        self.release_volume_renderer()
        super().closeEvent(event)

    def refresh_project(self):
        previous_id = self.current_specimen_id
        previous_scope = self.current_volume_scope
        previous_part_id = self.current_part_id
        self.specimen_list.blockSignals(True)
        self.specimen_list.clear()
        for specimen in self.project.project_data.get("specimens", []):
            specimen_id = specimen.get("specimen_id", "")
            parent = QTreeWidgetItem([self._format_specimen_label(specimen)])
            parent.setData(0, Qt.UserRole, {"scope": "full", "specimen_id": specimen_id, "part_id": ""})
            parent.setExpanded(True)

            full_item = QTreeWidgetItem([tt("Full volume", self.lang)])
            full_item.setData(0, Qt.UserRole, {"scope": "full", "specimen_id": specimen_id, "part_id": ""})
            parent.addChild(full_item)

            for part in specimen.get("parts", []) or []:
                label = self._format_part_label(part)
                part_item = QTreeWidgetItem([label])
                part_item.setData(
                    0,
                    Qt.UserRole,
                    {"scope": "part", "specimen_id": specimen_id, "part_id": part.get("part_id", "")},
                )
                reslices = ((part.get("metadata") or {}).get("local_axis_reslices", []) or [])
                if reslices:
                    reslices_item = QTreeWidgetItem([tt("Reslices", self.lang)])
                    reslices_item.setData(
                        0,
                        Qt.UserRole,
                        {"scope": "part_reslices", "specimen_id": specimen_id, "part_id": part.get("part_id", "")},
                    )
                    part_item.addChild(reslices_item)
                    for reslice in reslices:
                        reslice_item = QTreeWidgetItem([self._format_reslice_label(reslice)])
                        reslice_item.setData(
                            0,
                            Qt.UserRole,
                            {
                                "scope": "part_reslice",
                                "specimen_id": specimen_id,
                                "part_id": part.get("part_id", ""),
                                "reslice_id": reslice.get("reslice_id", ""),
                            },
                        )
                        reslices_item.addChild(reslice_item)
                    part_item.setExpanded(True)
                parent.addChild(part_item)
            self.specimen_list.addTopLevelItem(parent)
        self.specimen_list.blockSignals(False)
        if self.specimen_list.count():
            if not self._select_volume_tree_item(previous_id, previous_scope, previous_part_id):
                self._select_volume_tree_item("", "full", "")
        else:
            self.current_specimen_id = ""
            self.current_volume_scope = "full"
            self.current_part_id = ""
            self.current_part = None
            self.current_reslice_id = ""
            self.canvas.setText(tt("No specimens in this TIF project", self.lang))
            self.status_label.setText("")
            self.metadata_label.setText("")

    def _format_specimen_label(self, specimen):
        status = specimen.get("review_status", "not_started")
        train = tt("train-ready", self.lang) if specimen.get("train_ready") else tt("not train-ready", self.lang)
        return f"{specimen.get('display_name') or specimen.get('specimen_id')} ({status}, {train})"

    def _format_part_label(self, part):
        status = str((part or {}).get("status", "draft") or "draft")
        name = str((part or {}).get("display_name") or (part or {}).get("part_id") or tt("Part volume", self.lang))
        return f"{name} ({status})"

    def _format_reslice_label(self, reslice):
        name = str((reslice or {}).get("display_name") or (reslice or {}).get("reslice_id") or "reslice")
        status = str((reslice or {}).get("status") or "exported")
        return f"{name} ({status})"

    def _tree_item_payload(self, item):
        payload = item.data(0, Qt.UserRole) if item is not None else {}
        if isinstance(payload, dict):
            return {
                "scope": payload.get("scope", "full"),
                "specimen_id": payload.get("specimen_id", ""),
                "part_id": payload.get("part_id", ""),
                "reslice_id": payload.get("reslice_id", ""),
            }
        return {"scope": "full", "specimen_id": str(payload or ""), "part_id": "", "reslice_id": ""}

    def _select_volume_tree_item(self, specimen_id="", scope="full", part_id="", reslice_id=""):
        target_specimen = str(specimen_id or "").strip()
        target_scope = "part_reslice" if scope == "part_reslice" else ("part" if scope in {"part", "part_reslices"} else "full")
        target_part = str(part_id or "").strip()
        target_reslice = str(reslice_id or "").strip()
        fallback = None
        for row in range(self.specimen_list.topLevelItemCount()):
            parent = self.specimen_list.topLevelItem(row)
            if parent is None:
                continue
            parent_payload = self._tree_item_payload(parent)
            if fallback is None:
                fallback = parent.child(0) or parent
            if target_specimen and parent_payload.get("specimen_id") != target_specimen:
                continue
            if target_scope == "full":
                self.specimen_list.setCurrentItem(parent.child(0) or parent)
                return True
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                payload = self._tree_item_payload(child)
                if payload.get("scope") == "part" and payload.get("part_id") == target_part:
                    if target_scope == "part_reslice":
                        for group_index in range(child.childCount()):
                            group = child.child(group_index)
                            group_payload = self._tree_item_payload(group)
                            if group_payload.get("scope") == "part_reslices" and group.childCount():
                                if target_reslice:
                                    for reslice_index in range(group.childCount()):
                                        reslice_item = group.child(reslice_index)
                                        reslice_payload = self._tree_item_payload(reslice_item)
                                        if reslice_payload.get("reslice_id") == target_reslice:
                                            self.specimen_list.setCurrentItem(reslice_item)
                                            return True
                                    return False
                                self.specimen_list.setCurrentItem(group.child(0))
                                return True
                        if target_reslice:
                            return False
                    self.specimen_list.setCurrentItem(child)
                    return True
        if fallback is not None and not target_specimen:
            self.specimen_list.setCurrentItem(fallback)
            return True
        return False

    def _on_specimen_tree_selected(self, current, previous=None):
        if current is None:
            return
        if self._loading_specimen:
            return
        if previous is not None and self.working_edit_dirty:
            if not self._confirm_discard_or_save_working_edit():
                self._loading_specimen = True
                try:
                    self.specimen_list.setCurrentItem(previous)
                finally:
                    self._loading_specimen = False
                return
        payload = self._tree_item_payload(current)
        specimen_id = payload.get("specimen_id", "")
        if payload.get("scope") in {"part", "part_reslices", "part_reslice"}:
            self.load_part(specimen_id, payload.get("part_id", ""), selected_reslice_id=payload.get("reslice_id", ""))
        else:
            self.load_specimen(specimen_id)

    def load_specimen(self, specimen_id):
        if specimen_id != self.current_specimen_id and self.working_edit_dirty:
            if not self._confirm_discard_or_save_working_edit():
                return
        specimen = self.project.get_specimen(specimen_id, default=None)
        if specimen is None:
            return
        self._loading_specimen = True
        try:
            self.auto_save_timer.stop()
            self.current_specimen_id = specimen_id
            self.current_volume_scope = "full"
            self.current_part_id = ""
            self.current_part = None
            self.current_reslice_id = ""
            self.local_axis_draft = None
            self.part_preview_mask = None
            self.active_part_roi_id = ""
            self.part_roi_draw_mode = False
            self.part_contour_draw_mode = False
            self.btn_part_draw_roi.blockSignals(True)
            self.btn_part_draw_roi.setChecked(False)
            self.btn_part_draw_roi.blockSignals(False)
            self.btn_draw_part_contour.blockSignals(True)
            self.btn_draw_part_contour.setChecked(False)
            self.btn_draw_part_contour.blockSignals(False)
            self.image_volume = None
            self.label_volume = None
            self.edit_volume = None
            self.working_edit_dirty = False
            self._dirty_edit_slices = set()
            self.material_map = {}
            self.material_colors = {}
            self._clear_volume_preview_cache()
            self.undo_stack = []
            self.redo_stack = []

            image_path = self.project.to_absolute((specimen.get("working_volume") or {}).get("path", ""))
            if image_path and volume_sidecar_exists(image_path):
                self.image_volume = load_volume_sidecar(image_path, mmap_mode="r")
                self._slice_positions = {
                    "z": max(0, min(int(self.slice_slider.value()), int(self.image_volume.shape[0]) - 1)),
                    "y": max(0, int(self.image_volume.shape[1]) // 2),
                    "x": max(0, int(self.image_volume.shape[2]) // 2),
                }
                self._configure_slice_slider_for_axis(self._current_slice_axis(), preserve_position=True)
                self._reset_canvas_view_on_next_render = True
            else:
                self.slice_slider.setRange(0, 0)
                self.canvas.reset_view()

            material_path = self.project.to_absolute(specimen.get("material_map", ""))
            if material_path and os.path.exists(material_path):
                self.material_map = read_material_map(material_path)
                self.material_colors = {
                    int(item["id"]): QColor(str(item.get("color", "#000000")))
                    for item in self.material_map.get("materials", [])
                }
            self._populate_material_table()
            self._populate_volume_tint_combo()
            self._apply_volume_transfer_opacity_setting()
            self._populate_volume_mask_combo()
            self._reload_label_volume()
            self._load_edit_volume()
            self._update_status_labels(specimen)
            self._apply_default_volume_mask_mode()
            self._sync_mode_sections()
            self.render_current_slice()
            if self.display_mode == "volume":
                self.render_volume_preview()
        finally:
            self._loading_specimen = False

    def load_part(self, specimen_id, part_id, selected_reslice_id=""):
        if self.working_edit_dirty:
            if not self._confirm_discard_or_save_working_edit():
                return
        specimen = self.project.get_specimen(specimen_id, default=None)
        part = self.project.get_part(specimen_id, part_id, default=None)
        if specimen is None or part is None:
            return
        self._loading_specimen = True
        try:
            self.auto_save_timer.stop()
            self.current_specimen_id = specimen_id
            self.current_volume_scope = "part"
            self.current_part_id = part.get("part_id", "")
            self.current_part = part
            self.current_reslice_id = str(selected_reslice_id or "")
            self._clear_local_axis_draft_if_part_changed(specimen_id, self.current_part_id)
            self.active_part_roi_id = ""
            self.part_roi_draw_mode = False
            self.part_contour_draw_mode = False
            self.btn_part_draw_roi.blockSignals(True)
            self.btn_part_draw_roi.setChecked(False)
            self.btn_part_draw_roi.blockSignals(False)
            self.btn_draw_part_contour.blockSignals(True)
            self.btn_draw_part_contour.setChecked(False)
            self.btn_draw_part_contour.blockSignals(False)
            self.image_volume = None
            self.label_volume = None
            self.edit_volume = None
            self.working_edit_dirty = False
            self._dirty_edit_slices = set()
            self.material_map = {}
            self.material_colors = {}
            self.part_preview_mask = None
            self._clear_volume_preview_cache()
            self.undo_stack = []
            self.redo_stack = []

            image_path = self.project.to_absolute((part.get("image") or {}).get("path", ""))
            if image_path and volume_sidecar_exists(image_path):
                self.image_volume = load_volume_sidecar(image_path, mmap_mode="r")
                self._slice_positions = {
                    "z": max(0, min(int(self.slice_slider.value()), int(self.image_volume.shape[0]) - 1)),
                    "y": max(0, int(self.image_volume.shape[1]) // 2),
                    "x": max(0, int(self.image_volume.shape[2]) // 2),
                }
                self._configure_slice_slider_for_axis(self._current_slice_axis(), preserve_position=True)
                self._reset_canvas_view_on_next_render = True
            else:
                self.slice_slider.setRange(0, 0)
                self.canvas.reset_view()

            material_path = self.project.to_absolute(specimen.get("material_map", ""))
            if material_path and os.path.exists(material_path):
                self.material_map = read_material_map(material_path)
                self.material_colors = {
                    int(item["id"]): QColor(str(item.get("color", "#000000")))
                    for item in self.material_map.get("materials", [])
                }
            self._populate_material_table()
            self._populate_volume_tint_combo()
            self._apply_volume_transfer_opacity_setting()
            self._reload_label_volume()
            self._load_edit_volume()
            self._update_status_labels(specimen, part=part)
            self._apply_default_volume_mask_mode()
            self._sync_mode_sections()
            self.render_current_slice()
            if self.display_mode == "volume":
                self.render_volume_preview()
        finally:
            self._loading_specimen = False

    def _populate_material_table(self):
        materials = self.material_map.get("materials", []) if isinstance(self.material_map, dict) else []
        self.material_table.setRowCount(len(materials))
        for row, material in enumerate(materials):
            self.material_table.setItem(row, 0, QTableWidgetItem(str(material.get("id", ""))))
            self.material_table.setItem(row, 1, QTableWidgetItem(str(material.get("display_name") or material.get("name") or "")))
            self.material_table.setItem(row, 2, QTableWidgetItem(tt("yes", self.lang) if material.get("trainable") else tt("no", self.lang)))
            color_item = QTableWidgetItem(str(material.get("color", "")))
            try:
                color_item.setBackground(QColor(str(material.get("color", "#000000"))))
            except Exception:
                pass
            self.material_table.setItem(row, 3, color_item)
        self.material_table.resizeColumnsToContents()
        if self.material_table.rowCount() > 1:
            self.material_table.selectRow(1)
        elif self.material_table.rowCount() == 1:
            self.material_table.selectRow(0)

    def _selected_material(self):
        items = self.material_table.selectedItems()
        if not items:
            return None
        row = items[0].row()
        try:
            material_id = int(self.material_table.item(row, 0).text())
        except Exception:
            return None
        for material in self.material_map.get("materials", []):
            if int(material.get("id", -1)) == material_id:
                return dict(material)
        return None

    def _material_map_path(self):
        if self.current_volume_scope == "part":
            return ""
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None:
            return ""
        return self.project.to_absolute(specimen.get("material_map", ""))

    def _save_material_map(self):
        path = self._material_map_path()
        if not path:
            return
        self.material_map = write_material_map(path, self.material_map, source=self.material_map.get("source", "manual"))
        self.material_colors = {
            int(item["id"]): QColor(str(item.get("color", "#000000")))
            for item in self.material_map.get("materials", [])
        }
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is not None:
            self._update_status_labels(specimen)
            self._populate_material_table()
            self._populate_volume_tint_combo()
        self.render_current_slice()

    def add_material(self):
        if not self.current_specimen_id:
            return
        if self.current_volume_scope == "part":
            QMessageBox.information(self, tt("Material map", self.lang), tt("Part volumes inherit the parent specimen material map. Switch to Full volume to edit materials.", self.lang))
            return
        dialog = MaterialEditorDialog(next_id=next_material_id(self.material_map), parent=self, lang=self.lang)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.material_map = upsert_material(self.material_map, dialog.get_material())
            self._save_material_map()
        except Exception as exc:
            QMessageBox.warning(self, tt("Material map", self.lang), str(exc))

    def edit_selected_material(self):
        if self.current_volume_scope == "part":
            QMessageBox.information(self, tt("Material map", self.lang), tt("Part volumes inherit the parent specimen material map. Switch to Full volume to edit materials.", self.lang))
            return
        material = self._selected_material()
        if material is None:
            return
        dialog = MaterialEditorDialog(material=material, parent=self, lang=self.lang)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.material_map = upsert_material(self.material_map, dialog.get_material())
            self._save_material_map()
        except Exception as exc:
            QMessageBox.warning(self, tt("Material map", self.lang), str(exc))

    def delete_selected_material(self):
        if self.current_volume_scope == "part":
            QMessageBox.information(self, tt("Material map", self.lang), tt("Part volumes inherit the parent specimen material map. Switch to Full volume to edit materials.", self.lang))
            return
        material = self._selected_material()
        if material is None:
            return
        material_id = int(material.get("id", -1))
        if material_id == 0:
            QMessageBox.warning(self, tt("Material map", self.lang), tt("Background material cannot be deleted.", self.lang))
            return
        if self._material_id_is_used(material_id):
            QMessageBox.warning(self, tt("Material map", self.lang), tt("Material {0} is still used by a label volume.", self.lang).format(material_id))
            return
        reply = QMessageBox.question(
            self,
            tt("Material map", self.lang),
            tt("Delete material {0} ({1})?", self.lang).format(material_id, material.get("display_name", material.get("name", ""))),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self.material_map = remove_material(self.material_map, material_id)
            self._save_material_map()
        except Exception as exc:
            QMessageBox.warning(self, tt("Material map", self.lang), str(exc))

    def _material_id_is_used(self, material_id):
        arrays = []
        if self.edit_volume is not None:
            arrays.append(self.edit_volume)
        if self.label_volume is not None:
            arrays.append(self.label_volume)
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is not None:
            label_records = []
            labels = specimen.get("labels") or {}
            label_records.extend([labels.get("manual_truth") or {}, labels.get("working_edit") or {}])
            label_records.extend(labels.get("model_drafts") or [])
            for record in label_records:
                path = self.project.to_absolute((record or {}).get("path", ""))
                if path and volume_sidecar_exists(path):
                    try:
                        arrays.append(load_volume_sidecar(path, mmap_mode="r"))
                    except Exception:
                        pass
        for array in arrays:
            try:
                z_count = int(array.shape[0]) if getattr(array, "ndim", 0) == 3 else 0
                for z_index in range(z_count):
                    if np.any(np.asarray(array[z_index]) == int(material_id)):
                        return True
            except Exception:
                continue
        return False

    def _on_material_selected(self):
        items = self.material_table.selectedItems()
        if not items:
            return
        row = items[0].row()
        try:
            self.current_material_id = int(self.material_table.item(row, 0).text())
        except Exception:
            self.current_material_id = 0

    def _reload_label_volume(self):
        self.label_volume = None
        self._update_label_role_help()
        if self.current_volume_scope == "part":
            part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
            mask_path = self.project.to_absolute(((part or {}).get("mask") or {}).get("path", ""))
            if mask_path and volume_sidecar_exists(mask_path):
                self.label_volume = load_volume_sidecar(mask_path, mmap_mode="r")
            self.render_current_slice()
            return
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None:
            return
        role = self.label_role_combo.currentData()
        label_record = None
        labels = specimen.get("labels") or {}
        if role in {"manual_truth", "working_edit"}:
            label_record = labels.get(role) or {}
        elif role == "model_draft":
            drafts = labels.get("model_drafts") or []
            label_record = drafts[-1] if drafts else {}
        label_path = self.project.to_absolute((label_record or {}).get("path", ""))
        if label_path and volume_sidecar_exists(label_path):
            self.label_volume = load_volume_sidecar(label_path, mmap_mode="r")
        self.render_current_slice()

    def _load_edit_volume(self):
        if self.current_volume_scope == "part":
            self.edit_volume = None
            return
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        self.edit_volume = None
        if specimen is None:
            return
        edit_path = self.project.to_absolute(((specimen.get("labels") or {}).get("working_edit") or {}).get("path", ""))
        if edit_path and volume_sidecar_exists(edit_path):
            self.edit_volume = load_volume_sidecar(edit_path, mmap_mode="c")

    def _ensure_working_edit_volume(self):
        if self.current_volume_scope == "part":
            return False
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None:
            return False
        labels = specimen.setdefault("labels", {})
        edit_record = labels.get("working_edit") or {}
        edit_path = self.project.to_absolute(edit_record.get("path", ""))
        if edit_path and volume_sidecar_exists(edit_path):
            if self.edit_volume is None:
                self.edit_volume = load_volume_sidecar(edit_path, mmap_mode="c")
            return self.edit_volume is not None
        image_path = self.project.to_absolute((specimen.get("working_volume") or {}).get("path", ""))
        if not image_path or not volume_sidecar_exists(image_path):
            return False
        edit_rel = os.path.join(self.project.specimen_dir(self.current_specimen_id), "labels", "working_edit.ome.zarr").replace("\\", "/")
        edit_abs = self.project.to_absolute(edit_rel)
        metadata = create_empty_label_sidecar_like(image_path, edit_abs, role="working_edit", write_ome_zarr=False)
        self.project.register_label_volume(
            self.current_specimen_id,
            "working_edit",
            edit_rel,
            metadata["shape_zyx"],
            metadata["dtype"],
            status="empty_edit",
            spacing_zyx=metadata.get("spacing_zyx"),
            spacing_unit=metadata.get("spacing_unit", "micrometer"),
            orientation=metadata.get("orientation", "unknown"),
            fmt=metadata.get("format", ""),
            save=False,
        )
        self.project.save_project()
        self.edit_volume = load_volume_sidecar(edit_abs, mmap_mode="c")
        return self.edit_volume is not None

    def _format_tif_path_line(self, label, path_value):
        path_text = str(path_value or "").strip()
        if not path_text:
            return f"{tt(label, self.lang)}: -"
        try:
            absolute = self.project.to_absolute(path_text)
        except Exception:
            absolute = path_text
        if absolute and os.path.normpath(absolute) != os.path.normpath(path_text):
            return f"{tt(label, self.lang)}: {path_text}\n  {absolute}"
        return f"{tt(label, self.lang)}: {path_text}"

    def _on_show_debug_paths_toggled(self, checked=False):
        specimen = self.project.get_specimen(self.current_specimen_id, default=None) if self.current_specimen_id else None
        if specimen is not None:
            self._update_status_labels(specimen, part=self.current_part if self.current_volume_scope == "part" else None)

    def _set_scope_controls_enabled(self):
        is_part = self.current_volume_scope == "part"
        has_image = self.image_volume is not None
        for widget in (
            self.label_role_combo,
            self.brush_size_slider,
            self.btn_undo,
            self.btn_redo,
            self.btn_save_edit,
            self.btn_promote,
            self.btn_copy_draft,
            self.btn_export_training,
            self.btn_prepare_dataset,
            self.btn_train_backend,
            self.btn_import_prediction,
            self.btn_import_external_prediction_tif,
        ):
            widget.setEnabled(not is_part)
        self.auto_save_check.setEnabled(not is_part)
        self.btn_add_material.setEnabled(not is_part)
        self.btn_edit_material.setEnabled(not is_part)
        self.btn_delete_material.setEnabled(not is_part)
        self.part_bbox_edit.setEnabled(not is_part and has_image)
        self.btn_part_default_bbox.setEnabled(not is_part and has_image)
        self.btn_part_draw_roi.setEnabled(not is_part and has_image and self.display_mode == "slice")
        self.btn_save_part_roi.setEnabled(not is_part and has_image)
        self.btn_confirm_part_roi.setEnabled(not is_part and has_image)
        self.btn_cancel_part_roi.setEnabled(not is_part)
        self.btn_create_part.setEnabled(not is_part and has_image)
        self.btn_add_rect_keyframe.setEnabled(is_part and has_image)
        contour_enabled = is_part and has_image and self.display_mode == "slice" and self._current_slice_axis() == "z"
        self.btn_draw_part_contour.setEnabled(contour_enabled)
        self.btn_delete_part_contour.setEnabled(contour_enabled)
        self.btn_prev_key_slice.setEnabled(contour_enabled)
        self.btn_next_key_slice.setEnabled(contour_enabled)
        self.btn_preview_part_mask.setEnabled(is_part and has_image)
        self.btn_accept_part_mask.setEnabled(is_part and self.part_preview_mask is not None)
        self.btn_clear_part_preview.setEnabled(is_part and self.part_preview_mask is not None)
        self.btn_copy_source_z_axis.setEnabled(is_part and has_image)
        self.btn_local_axis_reslice.setEnabled(is_part and has_image)
        self.btn_local_axis_queue.setEnabled(bool(self.project.project_data.get("specimens", [])))
        self.btn_local_axis_models.setEnabled(bool(self.project.project_data.get("specimens", [])))
        self.btn_export_part_package.setEnabled(is_part and has_image)
        self.btn_delete_part_volume.setEnabled(is_part and self.current_part is not None)
        self._update_local_axis_summary()

    def _update_status_labels(self, specimen, part=None):
        self._set_scope_controls_enabled()
        readiness = self.project.evaluate_train_ready(specimen.get("specimen_id"))
        if part is not None:
            self.status_label.setText(
                f"{tt('Current view', self.lang)}: {tt('Part volume', self.lang)}\n"
                f"{tt('Part', self.lang)}: {part.get('display_name') or part.get('part_id')}\n"
                f"{tt('Status', self.lang)}: {part.get('status', 'draft')}\n"
                f"{tt('Parent specimen', self.lang)}: {specimen.get('display_name') or specimen.get('specimen_id')}"
            )
        else:
            self.status_label.setText(
                f"{tt('Current view', self.lang)}: {tt('Full volume', self.lang)}\n"
                f"{tt('Status', self.lang)}: {specimen.get('review_status', 'not_started')}\n"
                f"{tt('Train-ready', self.lang)}: {tt('yes', self.lang) if readiness['train_ready'] else tt('no', self.lang)}\n"
                f"{tt('Reasons', self.lang)}: {', '.join(readiness['reasons']) if readiness['reasons'] else '-'}"
            )
        working = specimen.get("working_volume") or {}
        labels = specimen.get("labels") or {}
        model_drafts = labels.get("model_drafts") or []
        latest_draft = model_drafts[-1] if model_drafts else {}
        source = specimen.get("source") or {}
        path_lines = [
            self._format_tif_path_line("Source TIF", source.get("raw_tif") or (specimen.get("provenance") or {}).get("source_file", "")),
            self._format_tif_path_line("Working volume", working.get("path", "")),
            self._format_tif_path_line("Working edit", (labels.get("working_edit") or {}).get("path", "")),
            self._format_tif_path_line("Manual truth", (labels.get("manual_truth") or {}).get("path", "")),
            self._format_tif_path_line("Latest model draft", latest_draft.get("path", "")),
            self._format_tif_path_line("Material map", specimen.get("material_map", "")),
            self._format_tif_path_line("Import report", working.get("import_report", "")),
        ]
        if part is not None:
            part_image = part.get("image") or {}
            part_mask = part.get("mask") or {}
            path_lines = [
                self._format_tif_path_line("Part image", part_image.get("path", "")),
                self._format_tif_path_line("Part mask", part_mask.get("path", "")),
                self._format_tif_path_line("Contours", part.get("contours_path", "")),
                self._format_tif_path_line("Extraction", part.get("extraction_path", "")),
                self._format_tif_path_line("Parent working volume", working.get("path", "")),
            ]
            metadata_lines = [
                f"{tt('Shape Z/Y/X', self.lang)}: {part_image.get('shape_zyx', [])}",
                f"{tt('dtype', self.lang)}: {part_image.get('dtype', '')}",
                f"{tt('spacing Z/Y/X', self.lang)}: {part_image.get('spacing_zyx', [])} {part_image.get('spacing_unit', '')}",
                f"{tt('Parent bbox Z/Y/X', self.lang)}: {part.get('parent_bbox_zyx', [])}",
                f"{tt('modality', self.lang)}: {specimen.get('modality', 'unknown')}",
            ]
            draft = self._current_local_axis_draft()
            if draft is not None:
                metadata_lines.extend(
                    [
                        "",
                        f"{tt('Local axis draft', self.lang)}: {draft.get('template_id', '')}",
                        f"{tt('Output axis start z,y,x', self.lang)}: {(draft.get('editable_axis') or {}).get('start_zyx', [])}",
                        f"{tt('Output axis end z,y,x', self.lang)}: {(draft.get('editable_axis') or {}).get('end_zyx', [])}",
                    ]
                )
            if self.current_reslice_id:
                reslice = self.project.get_part_reslice(
                    specimen.get("specimen_id", ""),
                    part.get("part_id", ""),
                    self.current_reslice_id,
                    default=None,
                )
                if reslice is not None:
                    training = reslice.get("training") or {}
                    provenance = reslice.get("provenance") or {}
                    metadata_lines.extend(
                        [
                            "",
                            f"{tt('Reslice ID', self.lang)}: {reslice.get('reslice_id', '')}",
                            f"{tt('Template', self.lang)}: {reslice.get('template_id', '')}",
                            f"{tt('Status', self.lang)}: {reslice.get('status', '')}",
                            f"{tt('Image', self.lang)}: {reslice.get('image_path', '')}",
                            f"{tt('Mask', self.lang)}: {reslice.get('mask_path', '') or '-'}",
                            f"{tt('Metadata', self.lang)}: {reslice.get('metadata_path', '')}",
                            f"{tt('Output shape Z/Y/X', self.lang)}: {(reslice.get('reslice_params') or {}).get('output_shape_zyx', [])}",
                            f"{tt('Human confirmed', self.lang)}: {bool(training.get('human_confirmed'))}",
                            f"{tt('Usable for training', self.lang)}: {bool(training.get('usable_for_training', True))}",
                            f"{tt('Hard case flags', self.lang)}: {', '.join(training.get('hard_case_flags', []) or []) or '-'}",
                            f"{tt('Source proposal', self.lang)}: {provenance.get('source_proposal_id', '') or '-'}",
                            f"{tt('Model version', self.lang)}: {provenance.get('source_model_version', '') or '-'}",
                        ]
                    )
        else:
            metadata_lines = [
                f"{tt('Shape Z/Y/X', self.lang)}: {working.get('shape_zyx', [])}",
                f"{tt('dtype', self.lang)}: {working.get('dtype', '')}",
                f"{tt('spacing Z/Y/X', self.lang)}: {working.get('spacing_zyx', [])} {working.get('spacing_unit', '')}",
                f"{tt('modality', self.lang)}: {specimen.get('modality', 'unknown')}",
            ]
        if self.show_debug_paths_check.isChecked():
            metadata_lines.extend(["", *path_lines])
        self.metadata_label.setText("\n".join(metadata_lines))

    def render_current_slice(self):
        if self.image_volume is None:
            if not self.current_specimen_id and not self.specimen_list.count():
                self.canvas.setText(tt("No specimens in this TIF project", self.lang))
            else:
                self.canvas.setText(tt("Working volume missing", self.lang))
            return
        axis, slice_index = self._active_slice_position()
        total = self._slice_count_for_axis(axis)
        self.slice_label.setText(f"{slice_index + 1} / {total}")
        image_slice = self._extract_axis_slice(self.image_volume, axis, slice_index)
        label_slice = None
        if self.label_volume is not None and self.label_volume.shape == self.image_volume.shape:
            label_slice = self._extract_axis_slice(self.label_volume, axis, slice_index)
        if self.label_role_combo.currentData() == "working_edit" and self.edit_volume is not None and self.edit_volume.shape == self.image_volume.shape:
            label_slice = self._extract_axis_slice(self.edit_volume, axis, slice_index)
        if self.current_volume_scope == "part" and self.part_preview_mask is not None and self.part_preview_mask.shape == self.image_volume.shape:
            label_slice = self._extract_axis_slice(self.part_preview_mask, axis, slice_index)
        pixmap = self._render_slice_pixmap(image_slice, label_slice)
        reset_view = bool(getattr(self, "_reset_canvas_view_on_next_render", False))
        self._reset_canvas_view_on_next_render = False
        self.canvas.set_slice_pixmap(pixmap, reset_view=reset_view)

    def _extract_axis_slice(self, volume, axis, index):
        if volume is None:
            return None
        axis = axis if axis in {"z", "y", "x"} else "z"
        if axis == "y":
            index = max(0, min(int(index), int(volume.shape[1]) - 1))
            return np.asarray(volume[:, index, :])
        if axis == "x":
            index = max(0, min(int(index), int(volume.shape[2]) - 1))
            return np.asarray(volume[:, :, index])
        index = max(0, min(int(index), int(volume.shape[0]) - 1))
        return np.asarray(volume[index])

    def volume_status_text(self):
        if self.image_volume is None:
            return ""
        return (
            f"{tt('3D volume', self.lang)} | "
            f"{self._volume_renderer_label()} | "
            f"{self._volume_mode_label()} | "
            f"{tt('drag rotate / wheel zoom', self.lang)} | "
            f"{int(round(self._volume_zoom * 100))}%"
        )

    def _local_axis_overlay_enabled(self):
        return bool(
            getattr(self, "volume_local_axes_check", None)
            and self.volume_local_axes_check.isChecked()
            and self.current_volume_scope == "part"
            and self.image_volume is not None
        )

    def _clear_local_axis_draft_if_part_changed(self, specimen_id="", part_id=""):
        draft = self.local_axis_draft if isinstance(self.local_axis_draft, dict) else None
        if draft is None:
            return
        if str(draft.get("specimen_id", "")) != str(specimen_id or "") or str(draft.get("part_id", "")) != str(part_id or ""):
            self.local_axis_draft = None

    def _source_z_axis_for_current_part(self):
        shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
        if len(shape) != 3 or min(shape) <= 0:
            return {}
        return source_z_axis_for_part(shape)

    def copy_source_z_axis_to_local_axis_draft(self):
        if self.current_volume_scope != "part" or not self.current_specimen_id or not self.current_part_id or self.image_volume is None:
            QMessageBox.information(self, tt("Local Axis Reslice", self.lang), tt("Select a part volume before opening Local Axis Reslice.", self.lang))
            return None
        source_axis = self._source_z_axis_for_current_part()
        if not source_axis:
            return None
        editable_axis = create_editable_axis_from_source(source_axis)
        shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
        origin = [(float(value) - 1.0) / 2.0 for value in shape]
        draft = {
            "specimen_id": self.current_specimen_id,
            "part_id": self.current_part_id,
            "template_id": str(self.current_part_id or "generic"),
            "source_axis": source_axis,
            "editable_axis": editable_axis,
            "origin_zyx": origin,
            "roll_reference": {},
            "local_frame": None,
            "dirty": True,
        }
        self.local_axis_draft = draft
        if hasattr(self, "volume_local_axes_check"):
            self.volume_local_axes_check.setChecked(True)
        self.training_status_label.setText(tt("Copied source Z axis as editable output axis.", self.lang))
        self.log(tt("Copied source Z axis as editable output axis.", self.lang))
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is not None:
            self._update_status_labels(specimen, part=self.current_part)
        if self.display_mode == "volume":
            self.render_volume_preview()
        return draft

    def _current_part_reslice_record(self):
        if not self.current_specimen_id or not self.current_part_id or not self.current_reslice_id:
            return None
        return self.project.get_part_reslice(self.current_specimen_id, self.current_part_id, self.current_reslice_id, default=None)

    def _current_local_axis_draft(self):
        draft = self.local_axis_draft if isinstance(self.local_axis_draft, dict) else None
        if draft is None:
            return None
        if str(draft.get("specimen_id", "")) != str(self.current_specimen_id or ""):
            return None
        if str(draft.get("part_id", "")) != str(self.current_part_id or ""):
            return None
        return draft

    def _format_local_axis_point_pair(self, axis):
        if not isinstance(axis, dict):
            return "-"
        start = axis.get("start_zyx") or []
        end = axis.get("end_zyx") or []
        if not start or not end:
            return "-"
        return "{0} -> {1}".format(start, end)

    def _update_local_axis_summary(self):
        label = getattr(self, "local_axis_summary_label", None)
        if label is None:
            return
        if self.current_volume_scope != "part" or not self.current_part_id or self.image_volume is None:
            label.setText(tt("Local axis unavailable. Select a part volume.", self.lang))
            return
        lines = [
            f"{tt('Part', self.lang)}: {self.current_part_id}",
            tt("Source Z axis: locked reference", self.lang),
            tt(
                "3D overlay: on" if self.display_mode == "volume" and self._local_axis_overlay_enabled() else "3D overlay: off",
                self.lang,
            ),
        ]
        draft = self._current_local_axis_draft()
        if draft is not None:
            lines.append(
                tt("Draft output Z: {0}", self.lang).format(
                    self._format_local_axis_point_pair((draft.get("editable_axis") or {}))
                )
            )
        else:
            lines.append(tt("Draft output Z: none", self.lang))
        reslice = self._current_part_reslice_record()
        if isinstance(reslice, dict):
            lines.append(tt("Saved reslice: {0}", self.lang).format(reslice.get("reslice_id", "")))
        else:
            lines.append(tt("Saved reslice: none selected", self.lang))
        label.setText("\n".join(lines))

    def _project_zyx_to_volume_xy(self, point_zyx, shape_zyx, source_shape=None, spacing_zyx=None):
        if not point_zyx or len(point_zyx) != 3:
            return None
        shape = tuple(max(1, int(value)) for value in (shape_zyx or (1, 1, 1)))
        if len(shape) != 3:
            return None
        z, y, x = [float(value) for value in point_zyx]
        dims = np.array([max(1, shape[0] - 1), max(1, shape[1] - 1), max(1, shape[2] - 1)], dtype=np.float32)
        coord = np.array([x / dims[2], y / dims[1], z / dims[0]], dtype=np.float32) - 0.5
        x_scale, y_scale, z_scale = volume_shape_scale(source_shape or shape, spacing_zyx)
        coord[0] *= x_scale
        coord[1] *= y_scale
        coord[2] *= z_scale

        yaw = math.radians(float(self._volume_yaw))
        pitch = math.radians(float(self._volume_pitch))
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        rot_yaw = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float32)
        rot_pitch = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=np.float32)
        rotated = coord @ (rot_yaw @ rot_pitch).T

        width = max(1.0, float(self.volume_canvas.width()) if hasattr(self, "volume_canvas") else 1.0)
        height = max(1.0, float(self.volume_canvas.height()) if hasattr(self, "volume_canvas") else 1.0)
        scale = (min(width, height) * 0.78) * float(self._volume_zoom)
        center_x = width / 2.0 + float(self._volume_pan_x) * scale * 0.5
        center_y = height / 2.0 - float(self._volume_pan_y) * scale * 0.5
        return [float(rotated[0] * scale + center_x), float(-rotated[1] * scale + center_y)]

    def _local_axis_volume_overlays(self):
        if not self._local_axis_overlay_enabled():
            return []
        shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
        if len(shape) != 3:
            return []
        source_shape, spacing_zyx = self._volume_source_geometry()
        overlays = []

        def add_axis(start, end, label, color, width=2):
            start_xy = self._project_zyx_to_volume_xy(start, shape, source_shape=source_shape, spacing_zyx=spacing_zyx)
            end_xy = self._project_zyx_to_volume_xy(end, shape, source_shape=source_shape, spacing_zyx=spacing_zyx)
            if start_xy and end_xy:
                overlays.append({"start_xy": start_xy, "end_xy": end_xy, "label": label, "color": color, "width": width})

        source_z = self._source_z_axis_for_current_part()
        add_axis(source_z.get("start_zyx"), source_z.get("end_zyx"), tt("source Z", self.lang), "#6AA6FF", width=2)

        editable = {}
        draft = self._current_local_axis_draft()
        if isinstance(draft, dict):
            editable = draft.get("editable_axis") or {}
        else:
            reslice = self._current_part_reslice_record()
            if isinstance(reslice, dict):
                editable = ((reslice.get("source") or {}).get("editable_axis") or {})
        if editable.get("start_zyx") and editable.get("end_zyx"):
            add_axis(editable.get("start_zyx"), editable.get("end_zyx"), tt("output Z", self.lang), "#FFB84D", width=3)
        return overlays

    def volume_canvas_overlay_text(self):
        if self.image_volume is None:
            return ""
        stats_text = self._volume_stats_text()
        parts = [
            tt("Volume view", self.lang),
            self._volume_renderer_label(),
            self._volume_mode_label(),
            f"{tt('Mode', self.lang)} {self._volume_projection_label()}",
            f"{tt('Transfer function', self.lang)} {self._volume_transfer_label()}",
            f"{tt('Mask display', self.lang)} {self._volume_mask_label_text()}",
            f"{tt('Detail enhancement', self.lang)} {int(self.volume_enhancement_slider.value())}%",
            f"{tt('Texture', self.lang)} {self._active_volume_target_dim()}",
            f"{tt('Samples', self.lang)} {self._active_volume_sample_count()}",
            f"{tt('ROI', self.lang)} {self._active_volume_roi_scale():.1f}x",
        ]
        if self.volume_clip_plane_check.isChecked():
            parts.append(f"{tt('Clip plane', self.lang)} {int(self.volume_clip_plane_depth_slider.value())}%")
        parts.extend(
            [
                f"{tt('Inside', self.lang)} {int(self.volume_inside_slider.value())}%",
                f"{tt('Cut', self.lang)} {int(self.volume_clip_slider.value())}%",
                f"{tt('Zoom', self.lang)} {int(round(self._volume_zoom * 100))}%",
                f"{tt('Pan X', self.lang)} {int(round(self._volume_pan_x * 100))}%",
                f"{tt('Pan Y', self.lang)} {int(round(self._volume_pan_y * 100))}%",
            ]
        )
        if stats_text:
            parts.append(stats_text)
        return " | ".join(parts)

    def _volume_mode_label(self):
        return tt("Drag preview", self.lang) if self._volume_render_mode == "drag" else tt("Still high quality", self.lang)

    def _volume_projection_mode(self):
        if hasattr(self, "volume_projection_combo"):
            mode = self.volume_projection_combo.currentData()
            if mode in {"composite", "mip", "minip", "average", "surface"}:
                return mode
        return "composite"

    def _volume_projection_label(self):
        labels = {
            "composite": "Composite",
            "mip": "MIP",
            "minip": "MinIP",
            "average": "Average",
            "surface": "Surface",
        }
        return tt(labels.get(self._volume_projection_mode(), "Composite"), self.lang)

    def _volume_mask_mode(self):
        if hasattr(self, "volume_mask_combo"):
            mode = self.volume_mask_combo.currentData()
            if mode in {"image_only", "mask_boundary", "masked_image"}:
                return mode
        return "image_only"

    def _volume_mask_label_text(self):
        labels = {
            "image_only": "Image only",
            "mask_boundary": "Mask boundary",
            "masked_image": "Masked image",
        }
        return tt(labels.get(self._volume_mask_mode(), "Image only"), self.lang)

    def _volume_transfer_label(self):
        labels = {
            "amber": "Amber",
            "cyan": "Cyan",
            "white": "White",
            "custom": "Custom",
        }
        return tt(labels.get(self._volume_transfer_preset(), "Amber"), self.lang)

    def _volume_transfer_opacity(self, mode=None):
        value = 100
        if hasattr(self, "volume_transfer_opacity_slider"):
            value = int(self.volume_transfer_opacity_slider.value())
        render_mode = "drag" if mode == "drag" else self._volume_render_mode
        base = 0.72 if self._volume_clarity_mode and render_mode == "still" else (1.0 if render_mode == "still" else 0.82)
        return max(0.05, min(1.4, base * (float(value) / 100.0)))

    def _volume_detail_enhancement(self, mode=None):
        if mode == "drag":
            return 0.0
        value = int(self.volume_enhancement_slider.value()) if hasattr(self, "volume_enhancement_slider") else 0
        return max(0.0, min(1.0, float(value) / 100.0))

    def _volume_tone_gamma(self):
        value = int(self.volume_tone_slider.value()) if hasattr(self, "volume_tone_slider") else 100
        return max(0.65, min(1.35, float(value) / 100.0))

    def _volume_clip_plane_normal(self):
        try:
            yaw = math.radians(float(self._volume_yaw))
            pitch = math.radians(float(self._volume_pitch))
            cy, sy = math.cos(yaw), math.sin(yaw)
            cp, sp = math.cos(pitch), math.sin(pitch)
            rot_yaw = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float32)
            rot_pitch = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=np.float32)
            direction = (rot_yaw @ rot_pitch).T @ np.asarray((0.0, 0.0, 1.0), dtype=np.float32)
            length = float(np.linalg.norm(direction))
            if not np.isfinite(length) or length <= 1e-6:
                return (0.0, 0.0, 1.0)
            direction = direction / length
            return tuple(float(value) for value in direction)
        except Exception:
            return (0.0, 0.0, 1.0)

    def _active_volume_roi_scale(self):
        if self._volume_canvas_renderer != "gpu" or self._volume_render_mode != "still":
            return 1.0
        if not getattr(self, "volume_roi_detail_check", None) or not self.volume_roi_detail_check.isChecked():
            return 1.0
        if float(self._volume_zoom) <= 1.01:
            return 1.0
        return max(1.0, min(3.0, float(self.volume_roi_scale_slider.value()) / 100.0))

    def _active_volume_sample_count(self):
        samples = int(self.volume_sample_slider.value())
        if self._volume_render_mode == "drag" and self._volume_canvas_renderer == "gpu":
            return max(256, min(samples, 768))
        roi_scale = self._active_volume_roi_scale()
        if roi_scale > 1.0 and self._volume_canvas_renderer == "gpu":
            return max(256, min(GPU_VOLUME_MAX_RAY_STEPS, int(round(samples * min(1.5, roi_scale)))))
        return samples

    def _volume_stats_text(self):
        stats = dict(getattr(self, "_volume_last_stats", {}) or {})
        if not stats:
            return tt("GPU stats pending", self.lang) if self._volume_canvas_renderer == "gpu" else ""
        shape = tuple(stats.get("shape_zyx") or ())
        parts = []
        if len(shape) == 3 and all(int(value) > 0 for value in shape):
            parts.append(f"{tt('actual', self.lang)} {int(shape[2])}x{int(shape[1])}x{int(shape[0])}")
        dtype = str(stats.get("dtype") or "")
        if dtype:
            parts.append(f"{tt('Data', self.lang)} {dtype}")
        projection = str(stats.get("projection_mode") or "")
        if projection:
            parts.append(f"{tt('Mode', self.lang)} {self._volume_projection_label()}")
        transfer = str(stats.get("transfer_preset") or "")
        if transfer:
            parts.append(f"{tt('Transfer function', self.lang)} {tt(transfer.capitalize(), self.lang)}")
        transfer_opacity = stats.get("transfer_opacity")
        if transfer_opacity is not None:
            try:
                parts.append(f"{tt('Density opacity', self.lang)} {int(round(float(transfer_opacity) * 100))}%")
            except (TypeError, ValueError):
                pass
        mask_mode = str(stats.get("mask_mode") or "")
        if mask_mode and mask_mode != "image_only":
            parts.append(f"{tt('Mask display', self.lang)} {self._volume_mask_label_text()}")
        enhancement = stats.get("enhancement")
        if enhancement is not None:
            try:
                value = int(round(float(enhancement) * 100))
                if value > 0:
                    parts.append(f"{tt('Detail enhancement', self.lang)} {value}%")
            except (TypeError, ValueError):
                pass
        if stats.get("clip_plane_enabled"):
            try:
                parts.append(f"{tt('Clip plane', self.lang)} {int(round(float(stats.get('clip_plane_depth') or 0.0) * 100))}%")
            except (TypeError, ValueError):
                parts.append(tt("Clip plane", self.lang))
        supersample = float(stats.get("supersample_scale") or 1.0)
        if supersample > 1.01:
            parts.append(f"{tt('ROI', self.lang)} {supersample:.1f}x")
        byte_count = int(stats.get("bytes") or 0)
        if byte_count > 0:
            parts.append(f"{tt('VRAM', self.lang)} {byte_count / (1024.0 ** 3):.2f} GB")
        upload_ms = float(stats.get("upload_ms") or 0.0)
        draw_ms = float(stats.get("draw_ms") or 0.0)
        if upload_ms > 0:
            parts.append(f"{tt('Upload', self.lang)} {upload_ms:.0f} ms")
        if draw_ms > 0:
            parts.append(f"{tt('Draw', self.lang)} {draw_ms:.1f} ms")
        diagnosis = self._volume_performance_diagnosis(stats)
        if diagnosis:
            parts.append(diagnosis)
        return " | ".join(parts)

    def _volume_performance_diagnosis(self, stats=None):
        stats = dict(stats or getattr(self, "_volume_last_stats", {}) or {})
        if self._volume_canvas_renderer != "gpu":
            if self._volume_renderer_warning:
                return tt("GPU fallback active", self.lang)
            return ""
        byte_count = int(stats.get("bytes") or 0)
        upload_ms = float(stats.get("upload_ms") or 0.0)
        draw_ms = float(stats.get("draw_ms") or 0.0)
        if upload_ms >= 1200.0:
            return tt("bottleneck: texture upload", self.lang)
        if draw_ms >= 90.0:
            return tt("bottleneck: ray rendering", self.lang)
        if byte_count >= int(1.5 * 1024 * 1024 * 1024):
            return tt("large GPU texture", self.lang)
        return ""

    def volume_performance_report(self):
        stats = dict(getattr(self, "_volume_last_stats", {}) or {})
        source_shape, spacing_zyx = self._volume_source_geometry()
        report = {
            "renderer": self._volume_canvas_renderer,
            "renderer_label": self._volume_renderer_label(),
            "source_shape_zyx": tuple(int(value) for value in source_shape) if len(source_shape) == 3 else (),
            "spacing_zyx": tuple(float(value) for value in spacing_zyx) if len(spacing_zyx) == 3 else (),
            "preview_shape_zyx": tuple(int(value) for value in stats.get("shape_zyx") or ()),
            "dtype": str(stats.get("dtype") or ""),
            "uploaded_bytes": int(stats.get("bytes") or 0),
            "upload_ms": float(stats.get("upload_ms") or 0.0),
            "draw_ms": float(stats.get("draw_ms") or 0.0),
            "samples": int(stats.get("steps") or self._active_volume_sample_count()),
            "render_mode": self._volume_render_mode,
            "projection_mode": self._volume_projection_mode(),
            "roi_scale": float(self._active_volume_roi_scale()),
            "clip_plane_enabled": bool(self.volume_clip_plane_check.isChecked()),
            "diagnosis": self._volume_performance_diagnosis(stats),
        }
        if report["uploaded_bytes"] > 0:
            report["uploaded_gb"] = report["uploaded_bytes"] / (1024.0 ** 3)
        else:
            report["uploaded_gb"] = 0.0
        return report

    def _update_volume_render_status_label(self, text=None):
        if not hasattr(self, "volume_render_status_label"):
            return
        if text is None:
            text = self.volume_canvas_overlay_text() if self.image_volume is not None else tt("No TIF volume loaded", self.lang)
        self.volume_render_status_label.setText(str(text or ""))

    def _volume_renderer_label(self):
        renderer = tt("GPU ray march", self.lang) if self._volume_canvas_renderer == "gpu" else tt("CPU fallback", self.lang)
        gpu_label = ""
        if self._volume_canvas_renderer == "gpu":
            if hasattr(self.volume_canvas, "renderer_label"):
                gpu_label = self.volume_canvas.renderer_label()
            if not gpu_label:
                gpu_label = self._compact_gpu_renderer_info(self._volume_gl_renderer_info)
        if gpu_label:
            renderer = f"{renderer} [{gpu_label}]"
        return renderer

    def _compact_gpu_renderer_info(self, info):
        text = " ".join(str(info or "").split())
        if "RTX 3090" in text:
            return "RTX 3090"
        if "NVIDIA GeForce" in text:
            return text.replace("NVIDIA GeForce ", "NVIDIA ").split("|")[0].strip()
        return text.split("|")[0].strip()[:42]

    def _volume_renderer_status_message(self):
        if self._volume_canvas_renderer == "gpu":
            return tt("3D preview uses a downsampled read-only volume. Use Slice review for precise label editing.", self.lang)
        if self._volume_renderer_warning:
            return (
                tt("3D preview uses a downsampled read-only volume. Use Slice review for precise label editing.", self.lang)
                + "\n"
                + tt("GPU renderer unavailable. Using CPU fallback.", self.lang)
            )
        return tt("3D preview uses a downsampled read-only volume. Use Slice review for precise label editing.", self.lang)

    def _on_gpu_volume_info_changed(self, details):
        info = str(details or "")
        if info == self._volume_gl_renderer_info:
            return
        self._volume_gl_renderer_info = info
        if self._volume_gl_renderer_info:
            self.log(f"GPU volume OpenGL renderer: {self._volume_gl_renderer_info}")
        self._update_volume_render_status_label()
        if self.display_mode == "volume":
            self.render_volume_preview()

    def _on_gpu_volume_failed(self, reason):
        if self._volume_canvas_renderer != "gpu":
            return
        if getattr(self, "_handling_gpu_volume_failure", False):
            return
        self._handling_gpu_volume_failure = True
        warning = str(reason or "unknown")
        try:
            self._switch_volume_canvas_to_cpu(warning)
            message = tt("GPU renderer failed. Using CPU fallback: {0}", self.lang).format(warning)
            self.training_status_label.setText(message)
            self._update_volume_render_status_label(
                f"{tt('Volume view', self.lang)} | {tt('CPU fallback', self.lang)} | {tt('GPU failed', self.lang)}: {warning}"
            )
            self.log(message)
        finally:
            self._handling_gpu_volume_failure = False
        self.schedule_volume_preview_render()

    def _switch_volume_canvas_to_cpu(self, warning=""):
        old_canvas = getattr(self, "volume_canvas", None)
        if old_canvas is not None and not hasattr(old_canvas, "set_volume_pixmap"):
            if hasattr(old_canvas, "release_gl_resources"):
                try:
                    old_canvas.release_gl_resources()
                except Exception:
                    pass
            self.volume_canvas = TifVolumeCanvas()
            self.volume_canvas.workbench = self
            renderer_property = "cpu-mask-fallback" if str(warning or "").startswith("Mask inspection") else "cpu"
            self.volume_canvas.setProperty("tifVolumeRenderer", renderer_property)
            if hasattr(self, "view_stack"):
                self.view_stack.addWidget(self.volume_canvas)
                index = self.view_stack.indexOf(old_canvas)
                if self.display_mode == "volume":
                    self.view_stack.setCurrentWidget(self.volume_canvas)
                if index >= 0:
                    self.view_stack.removeWidget(old_canvas)
            old_canvas.hide()
            old_canvas.setParent(None)
            old_canvas.deleteLater()
        self._volume_canvas_renderer = "cpu"
        if warning and not str(warning).startswith("Mask inspection"):
            self._volume_renderer_warning = str(warning)
        self._volume_last_stats = {}

    def _try_restore_gpu_volume_canvas(self):
        if self._volume_canvas_renderer == "gpu" or self._volume_renderer_warning:
            return False
        if not getattr(self, "_volume_canvas_created", False):
            return False
        if str(getattr(self.volume_canvas, "property", lambda _key: "")("tifVolumeRenderer") or "") != "cpu-mask-fallback":
            return False
        self._ensure_volume_canvas(force_gpu=True)
        return self._volume_canvas_renderer == "gpu"

    def _on_gpu_volume_stats_changed(self):
        if hasattr(self.volume_canvas, "render_stats"):
            self._volume_last_stats = dict(self.volume_canvas.render_stats() or {})
        self._update_volume_render_status_label()

    def _start_volume_interaction(self):
        if self._volume_render_mode != "drag":
            self._volume_render_mode = "drag"
        if hasattr(self, "volume_still_timer"):
            self.volume_still_timer.start()

    def finish_volume_interaction_debounced(self):
        if hasattr(self, "volume_still_timer"):
            self.volume_still_timer.start()

    def _finish_volume_interaction(self):
        self._volume_interaction_render_pending = False
        if self._volume_render_mode != "still":
            self._volume_render_mode = "still"
            self.render_volume_preview()

    def _on_volume_clarity_toggled(self, checked):
        self._volume_clarity_mode = bool(checked)
        self._clear_volume_preview_cache()
        self.render_volume_preview()

    def _on_volume_display_enhancement_changed(self, *_args):
        self.render_volume_preview()

    def _on_volume_clip_plane_changed(self, *_args):
        self.render_volume_preview()

    def _on_volume_projection_changed(self):
        self.render_volume_preview()

    def _volume_tint_rgb(self):
        settings = self._active_volume_view_settings()
        mode = self.volume_tint_combo.currentData() if hasattr(self, "volume_tint_combo") else settings.get("volume_tint", "amber")
        if mode == "cyan":
            color = QColor("#61D9FF")
        elif mode == "white":
            color = QColor("#F0F4F2")
        elif mode == "custom":
            color = QColor(str(settings.get("volume_tint_custom", "#FFD34D")))
            if not color.isValid():
                color = QColor("#FFD34D")
        else:
            color = QColor("#FFD34D")
        return np.asarray([color.redF(), color.greenF(), color.blueF()], dtype=np.float32)

    def _volume_transfer_preset(self):
        settings = self._active_volume_view_settings()
        mode = self.volume_tint_combo.currentData() if hasattr(self, "volume_tint_combo") else settings.get("volume_tint", "amber")
        mode = str(mode or "amber").lower()
        return mode if mode in {"amber", "cyan", "white", "custom"} else "amber"

    def _volume_transfer_lut(self):
        return build_volume_transfer_lut(
            self._volume_transfer_preset(),
            tuple(float(value) for value in self._volume_tint_rgb()),
            cutoff=0.0,
            opacity=self._volume_transfer_opacity(),
            clarity=self._volume_clarity_mode and self._volume_render_mode == "still",
        )

    def _on_volume_tint_changed(self):
        settings = self._active_volume_view_settings()
        settings["volume_tint"] = self.volume_tint_combo.currentData() or "amber"
        self._save_active_volume_view_settings()
        self.render_volume_preview()

    def _on_volume_transfer_opacity_changed(self):
        settings = self._active_volume_view_settings()
        settings["volume_transfer_opacity"] = int(self.volume_transfer_opacity_slider.value())
        self._save_active_volume_view_settings()
        self.render_volume_preview()

    def _on_volume_mask_changed(self):
        settings = self._active_volume_view_settings()
        settings["volume_mask_mode"] = self._volume_mask_mode()
        self._save_active_volume_view_settings()
        self._clear_volume_mask_caches()
        self.render_volume_preview()

    def choose_volume_custom_color(self):
        settings = self._active_volume_view_settings()
        color = QColorDialog.getColor(QColor(str(settings.get("volume_tint_custom", "#FFD34D"))), self, tt("Choose color", self.lang))
        if not color.isValid():
            return
        settings["volume_tint"] = "custom"
        settings["volume_tint_custom"] = color.name()
        index = self.volume_tint_combo.findData("custom")
        if index >= 0:
            self.volume_tint_combo.setCurrentIndex(index)
        self._save_active_volume_view_settings()
        self.render_volume_preview()

    def rotate_volume_preview(self, dx, dy):
        self._start_volume_interaction()
        self._volume_yaw = (self._volume_yaw + float(dx) * 0.6) % 360.0
        self._volume_pitch = max(-85.0, min(85.0, self._volume_pitch + float(dy) * 0.45))
        self._request_volume_interaction_render()

    def pan_volume_preview(self, dx, dy):
        self._start_volume_interaction()
        width = max(1.0, float(self.volume_canvas.width()) if hasattr(self, "volume_canvas") else 1.0)
        height = max(1.0, float(self.volume_canvas.height()) if hasattr(self, "volume_canvas") else 1.0)
        zoom = max(0.35, float(self._volume_zoom))
        self._volume_pan_x = max(-2.0, min(2.0, self._volume_pan_x + (float(dx) / width) * 2.0 / zoom))
        self._volume_pan_y = max(-2.0, min(2.0, self._volume_pan_y - (float(dy) / height) * 2.0 / zoom))
        self._request_volume_interaction_render()

    def zoom_volume_preview(self, direction):
        self._start_volume_interaction()
        factor = 1.18 if int(direction) > 0 else 1.0 / 1.18
        self._volume_zoom = max(0.35, min(16.0, self._volume_zoom * factor))
        self._request_volume_interaction_render()

    def reset_volume_view(self):
        if hasattr(self, "volume_still_timer"):
            self.volume_still_timer.stop()
        self._volume_render_mode = "still"
        self._volume_yaw = -35.0
        self._volume_pitch = 20.0
        self._volume_zoom = 1.0
        self._volume_pan_x = 0.0
        self._volume_pan_y = 0.0
        if hasattr(self, "volume_inside_slider"):
            self.volume_inside_slider.blockSignals(True)
            self.volume_inside_slider.setValue(0)
            self.volume_inside_slider.blockSignals(False)
        if hasattr(self, "volume_clip_slider"):
            self.volume_clip_slider.blockSignals(True)
            self.volume_clip_slider.setValue(0)
            self.volume_clip_slider.blockSignals(False)
        if hasattr(self, "volume_clip_plane_check"):
            self.volume_clip_plane_check.blockSignals(True)
            self.volume_clip_plane_check.setChecked(False)
            self.volume_clip_plane_check.blockSignals(False)
        if hasattr(self, "volume_clip_plane_depth_slider"):
            self.volume_clip_plane_depth_slider.blockSignals(True)
            self.volume_clip_plane_depth_slider.setValue(50)
            self.volume_clip_plane_depth_slider.blockSignals(False)
        self.render_volume_preview()

    def _refresh_volume_preview(self):
        self._clear_volume_preview_cache()
        self.render_volume_preview()

    def _clear_volume_preview_cache(self):
        self._volume_preview_cache = {}
        self._clear_volume_mask_caches()
        self._volume_preview = None
        self._volume_preview_source_shape = ()
        self._volume_last_stats = {}
        self._volume_render_mode = "still"
        self._volume_interaction_render_pending = False

    def _clear_volume_mask_caches(self):
        self._volume_mask_preview_cache = {}
        self._volume_masked_preview_cache = {}

    def _volume_drag_target_dim(self):
        requested = self._volume_texture_target_dim()
        if self._volume_canvas_renderer != "gpu":
            return requested
        return max(256, min(requested, 640))

    def _active_volume_target_dim(self, mode=None):
        mode = mode or self._volume_render_mode
        if mode == "drag":
            return self._volume_drag_target_dim()
        requested = self._volume_texture_target_dim()
        if self.current_volume_scope == "part" and self.image_volume is not None:
            shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
            voxel_count = int(np.prod(shape)) if len(shape) == 3 else 0
            if voxel_count > 0 and voxel_count <= 64_000_000:
                requested = max(requested, min(max(shape), 1536))
        return requested

    def _ensure_volume_preview(self, mode=None):
        if self.image_volume is None:
            return None
        shape = tuple(int(value) for value in self.image_volume.shape)
        mode = "drag" if mode == "drag" else "still"
        max_dim = self._active_volume_target_dim(mode)
        source_dtype = str(np.dtype(getattr(self.image_volume, "dtype", np.uint8)))
        cache_key = (shape, source_dtype, max_dim, bool(self._volume_clarity_mode and mode == "still"))
        cached = self._volume_preview_cache.get(cache_key)
        if cached is not None:
            self._volume_preview = cached
            self._volume_preview_source_shape = cache_key
            return cached

        factors = [max(1, int(math.ceil(size / float(max_dim)))) for size in shape]
        source = self.image_volume[:: factors[0], :: factors[1], :: factors[2]]
        preserve_source = mode == "still" and (self._volume_clarity_mode or self.current_volume_scope == "part")
        preview = self._normalize_volume_preview(source, preserve_source=preserve_source)
        if preview is None:
            return None
        self._volume_preview_cache[cache_key] = preview
        self._volume_preview = preview
        self._volume_preview_source_shape = cache_key
        return preview

    def _active_part_mask_volume(self):
        if self.current_volume_scope != "part" or self.image_volume is None:
            return None
        if self.part_preview_mask is not None and self.part_preview_mask.shape == self.image_volume.shape:
            return self.part_preview_mask
        if self.label_volume is not None and self.label_volume.shape == self.image_volume.shape:
            return self.label_volume
        return None

    def _active_part_mask_has_voxels(self):
        mask = self._active_part_mask_volume()
        if mask is None:
            return False
        try:
            shape = tuple(int(value) for value in getattr(mask, "shape", ()) or ())
            if len(shape) < 3:
                return bool(np.any(np.asarray(mask) > 0))
            plane_values = max(1, int(np.prod(shape[1:])))
            z_chunk = max(1, min(int(shape[0]), int((16 * 1024 * 1024) / plane_values)))
            for z0 in range(0, int(shape[0]), z_chunk):
                z1 = min(int(shape[0]), z0 + z_chunk)
                if np.any(np.asarray(mask[z0:z1]) > 0):
                    return True
            return False
        except Exception:
            return False

    def _ensure_volume_mask_preview(self, mode=None):
        mask = self._active_part_mask_volume()
        if mask is None:
            return None
        shape = tuple(int(value) for value in getattr(mask, "shape", ()) or ())
        mode = "drag" if mode == "drag" else "still"
        max_dim = self._active_volume_target_dim(mode)
        cache_key = (shape, str(np.dtype(getattr(mask, "dtype", np.uint16))), max_dim, id(mask))
        cached = self._volume_mask_preview_cache.get(cache_key)
        if cached is not None:
            return cached
        factors = [max(1, int(math.ceil(size / float(max_dim)))) for size in shape]
        preview = (np.asarray(mask[:: factors[0], :: factors[1], :: factors[2]]) > 0).astype(np.uint8)
        preview = np.ascontiguousarray(preview)
        self._volume_mask_preview_cache[cache_key] = preview
        return preview

    def _masked_volume_preview(self, preview, mask_preview):
        if mask_preview is None or tuple(mask_preview.shape) != tuple(preview.shape):
            return preview
        cache_key = (
            id(preview),
            id(mask_preview),
            tuple(int(value) for value in preview.shape),
            str(np.dtype(getattr(preview, "dtype", np.uint8))),
        )
        cached = self._volume_masked_preview_cache.get(cache_key)
        if cached is not None:
            return cached
        mask_values = np.asarray(mask_preview) > 0
        masked = np.ascontiguousarray(np.where(mask_values, preview, np.zeros_like(preview)))
        self._volume_masked_preview_cache[cache_key] = masked
        return masked

    def _mask_boundary_preview(self, mask_preview):
        mask = np.asarray(mask_preview, dtype=bool)
        if mask.size == 0:
            return np.zeros_like(mask, dtype=bool)
        eroded = mask.copy()
        for axis in range(3):
            before = np.roll(mask, 1, axis=axis)
            after = np.roll(mask, -1, axis=axis)
            index_first = [slice(None)] * 3
            index_last = [slice(None)] * 3
            index_first[axis] = 0
            index_last[axis] = -1
            before[tuple(index_first)] = False
            after[tuple(index_last)] = False
            eroded &= before & after
        return mask & ~eroded

    def _normalize_volume_preview(self, source, preserve_source=False):
        if source is None:
            return None
        source_dtype = np.dtype(getattr(source, "dtype", np.uint8))
        if preserve_source and source_dtype == np.uint16:
            preview = np.ascontiguousarray(source)
            return preview if preview.size else None
        if source_dtype == np.uint8:
            preview = np.ascontiguousarray(source)
            return preview if preview.size else None
        preview = np.asarray(source)
        if preview.size == 0:
            return None
        sample = self._sample_volume_preview_values(preview)
        if np.issubdtype(preview.dtype, np.integer):
            sample_values = np.asarray(sample, dtype=np.float32).reshape(-1)
        else:
            sample_values = np.asarray(sample, dtype=np.float32).reshape(-1)
        finite = sample_values[np.isfinite(sample_values)]
        if finite.size == 0:
            return np.zeros(preview.shape, dtype=np.uint8)
        low = float(np.percentile(finite, 1))
        high = float(np.percentile(finite, 99.5))
        if high <= low:
            low = float(np.min(finite))
            high = float(np.max(finite))
        if high <= low:
            return np.zeros(preview.shape, dtype=np.uint8)
        return self._scale_volume_preview_to_uint8(preview, low, high)

    def _normalize_volume_preview_to_uint8(self, source):
        return self._normalize_volume_preview(source, preserve_source=False)

    def _sample_volume_preview_values(self, preview, max_samples=1_000_000):
        if preview.size <= max_samples:
            return preview
        step = max(1, int(math.ceil((float(preview.size) / float(max_samples)) ** (1.0 / 3.0))))
        return preview[::step, ::step, ::step]

    def _scale_volume_preview_to_uint8(self, preview, low, high):
        scale = 255.0 / max(float(high) - float(low), 1e-6)
        result = np.empty(preview.shape, dtype=np.uint8)
        if preview.ndim < 3:
            chunk = np.asarray(preview, dtype=np.float32)
            chunk = np.clip((chunk - float(low)) * scale, 0.0, 255.0)
            return np.ascontiguousarray(chunk.astype(np.uint8))
        plane_values = max(1, int(np.prod(preview.shape[1:])))
        z_chunk = max(1, min(int(preview.shape[0]), int((64 * 1024 * 1024) / (plane_values * 4))))
        for z0 in range(0, int(preview.shape[0]), z_chunk):
            z1 = min(int(preview.shape[0]), z0 + z_chunk)
            chunk = np.asarray(preview[z0:z1], dtype=np.float32)
            chunk = np.clip((chunk - float(low)) * scale, 0.0, 255.0)
            result[z0:z1] = chunk.astype(np.uint8)
        return np.ascontiguousarray(result)

    def _volume_texture_target_dim(self):
        requested = max(8, int(self.volume_quality_slider.value()))
        if self._volume_canvas_renderer == "gpu":
            return max(256, min(GPU_VOLUME_MAX_TEXTURE_DIM, requested))
        return max(32, min(128, requested))

    def _volume_render_state(self, mode=None):
        mode = "drag" if mode == "drag" else "still"
        samples = int(self.volume_sample_slider.value())
        if mode == "drag":
            samples = max(256, min(samples, 768))
        return {
            "cutoff_percent": self.volume_cutoff_slider.value(),
            "yaw": self._volume_yaw,
            "pitch": self._volume_pitch,
            "zoom": self._volume_zoom,
            "render_quality": self._active_volume_target_dim(mode),
            "sample_steps": samples,
            "inside_depth": float(self.volume_inside_slider.value()) / 100.0,
            "front_clip": float(self.volume_clip_slider.value()) / 100.0,
            "render_mode": mode,
            "pan_x": self._volume_pan_x,
            "pan_y": self._volume_pan_y,
            "clarity_mode": self._volume_clarity_mode,
            "projection_mode": self._volume_projection_mode(),
            "supersample_scale": self._active_volume_roi_scale(),
            "tint_rgb": tuple(float(value) for value in self._volume_tint_rgb()),
            "transfer_preset": self._volume_transfer_preset(),
            "transfer_opacity": self._volume_transfer_opacity(mode),
            "mask_mode": self._volume_mask_mode(),
            "mask_opacity": max(0.0, min(1.0, float(self.volume_mask_opacity_slider.value()) / 100.0)),
            "enhancement": self._volume_detail_enhancement(mode),
            "tone_gamma": self._volume_tone_gamma(),
            "surface_refine": bool(self.volume_surface_refine_check.isChecked()),
            "clip_plane_enabled": bool(self.volume_clip_plane_check.isChecked()),
            "clip_plane_depth": float(self.volume_clip_plane_depth_slider.value()) / 100.0,
            "clip_plane_normal": self._volume_clip_plane_normal(),
        }

    def _sync_gpu_volume_canvas(self, preview, mask_preview=None, mask_mode=None):
        if self._volume_canvas_renderer != "gpu" or not hasattr(self.volume_canvas, "set_volume_data"):
            return False
        mask_mode = mask_mode if mask_mode in {"mask_boundary", "masked_image"} else "image_only"
        if mask_mode != "image_only" and not hasattr(self.volume_canvas, "set_mask_data"):
            return False
        source_shape, spacing_zyx = self._volume_source_geometry()
        mode = "drag" if self._volume_render_mode == "drag" else "still"
        state = self._volume_render_state(mode)
        state["mask_mode"] = mask_mode
        if hasattr(self.volume_canvas, "set_axis_overlays"):
            self.volume_canvas.set_axis_overlays(self._local_axis_volume_overlays())
        if hasattr(self.volume_canvas, "set_volume_render_inputs"):
            self.volume_canvas.set_volume_render_inputs(
                preview,
                mask=mask_preview if mask_mode != "image_only" else None,
                render_state=state,
                source_shape=source_shape,
                spacing_zyx=spacing_zyx,
            )
            return True
        self.volume_canvas.set_volume_data(preview, source_shape=source_shape, spacing_zyx=spacing_zyx)
        if hasattr(self.volume_canvas, "set_mask_data"):
            self.volume_canvas.set_mask_data(mask_preview if mask_mode != "image_only" else None)
        if hasattr(self.volume_canvas, "set_render_state"):
            self.volume_canvas.set_render_state(**state)
        return True

    def _request_volume_interaction_render(self):
        if self.display_mode != "volume":
            return
        self._volume_interaction_render_pending = True
        if self._volume_interaction_render_scheduled:
            return
        self._volume_interaction_render_scheduled = True

        def run():
            self._volume_interaction_render_scheduled = False
            if not self._volume_interaction_render_pending:
                return
            self._volume_interaction_render_pending = False
            self._render_volume_interaction_preview()

        delay_ms = int(self._volume_interaction_render_interval_ms)
        if self._volume_canvas_renderer != "gpu":
            delay_ms = max(delay_ms, 80)
        QTimer.singleShot(delay_ms, run)

    def _render_volume_interaction_preview(self):
        if self.display_mode != "volume" or self.image_volume is None:
            return
        if self._sync_gpu_volume_camera_only():
            self._update_volume_render_status_label()
            return
        self.render_volume_preview()

    def _sync_gpu_volume_camera_only(self):
        if self._volume_canvas_renderer != "gpu" or not hasattr(self.volume_canvas, "set_render_state"):
            return False
        if not callable(getattr(self.volume_canvas, "has_volume", None)) or not self.volume_canvas.has_volume():
            return False
        mode = "drag" if self._volume_render_mode == "drag" else "still"
        state = self._volume_render_state(mode)
        state["mask_mode"] = self._volume_mask_mode()
        if hasattr(self.volume_canvas, "set_axis_overlays"):
            self.volume_canvas.set_axis_overlays(self._local_axis_volume_overlays())
        if callable(getattr(self.volume_canvas, "set_interaction_render_state", None)):
            self.volume_canvas.set_interaction_render_state(**state)
        else:
            self.volume_canvas.set_render_state(**state)
        return True

    def _volume_source_geometry(self):
        shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
        spacing = ()
        if self.current_volume_scope == "part":
            record = ((self.current_part or {}).get("image") or {})
        else:
            specimen = self.project.get_specimen(self.current_specimen_id, default=None) if self.current_specimen_id else None
            record = (specimen or {}).get("working_volume") or {}
        record_shape = record.get("shape_zyx") or []
        try:
            record_shape = tuple(int(value) for value in record_shape)
        except (TypeError, ValueError):
            record_shape = ()
        if len(record_shape) == 3 and min(record_shape) > 0:
            shape = record_shape
        record_spacing = record.get("spacing_zyx") or []
        try:
            record_spacing = tuple(float(value) for value in record_spacing)
        except (TypeError, ValueError):
            record_spacing = ()
        if len(record_spacing) == 3 and min(record_spacing) > 0:
            spacing = record_spacing
        return shape, spacing

    def schedule_volume_preview_render(self):
        if getattr(self, "_volume_render_scheduled", False):
            return
        self._volume_render_scheduled = True

        def run():
            self._volume_render_scheduled = False
            if self.display_mode == "volume" and not getattr(self, "_handling_gpu_volume_failure", False):
                self.render_volume_preview()

        QTimer.singleShot(0, run)

    def render_volume_preview(self):
        if not hasattr(self, "volume_canvas"):
            return
        if getattr(self, "_handling_gpu_volume_failure", False):
            return
        if self.display_mode == "volume":
            self._ensure_volume_canvas()
        if self.image_volume is None:
            if hasattr(self.volume_canvas, "set_axis_overlays"):
                self.volume_canvas.set_axis_overlays([])
            self.volume_canvas.clear()
            self.volume_canvas.setText(tt("No TIF volume loaded", self.lang))
            self._update_volume_render_status_label(tt("No TIF volume loaded", self.lang))
            return
        preview = self._ensure_volume_preview(self._volume_render_mode)
        if preview is None:
            if hasattr(self.volume_canvas, "set_axis_overlays"):
                self.volume_canvas.set_axis_overlays([])
            self.volume_canvas.clear()
            self.volume_canvas.setText(tt("No TIF volume loaded", self.lang))
            self._update_volume_render_status_label(tt("No TIF volume loaded", self.lang))
            return
        mask_mode = self._volume_mask_mode()
        mask_preview = self._ensure_volume_mask_preview(self._volume_render_mode) if mask_mode != "image_only" else None
        if mask_preview is None and mask_mode != "image_only":
            mask_mode = "image_only"
        self._try_restore_gpu_volume_canvas()
        if self._sync_gpu_volume_canvas(preview, mask_preview=mask_preview, mask_mode=mask_mode):
            self._update_volume_render_status_label()
            return
        if mask_mode != "image_only" and not hasattr(self.volume_canvas, "set_volume_pixmap"):
            self._switch_volume_canvas_to_cpu("Mask inspection uses CPU fallback.")
        pixmap = self._render_volume_preview_pixmap(preview, mask_preview=mask_preview, mask_mode=mask_mode)
        if hasattr(self.volume_canvas, "set_axis_overlays"):
            self.volume_canvas.set_axis_overlays(self._local_axis_volume_overlays())
        self.volume_canvas.set_volume_pixmap(pixmap)
        self._update_volume_render_status_label()

    def _render_volume_preview_pixmap(self, preview, mask_preview=None, mask_mode="image_only"):
        max_value = float(np.iinfo(preview.dtype).max) if np.issubdtype(preview.dtype, np.integer) else 1.0
        projection_mode = self._volume_projection_mode()
        cutoff = float(self.volume_cutoff_slider.value()) / 100.0
        mask_mode = mask_mode if mask_mode in {"mask_boundary", "masked_image"} else "image_only"
        mask_values = None
        if mask_preview is not None and tuple(mask_preview.shape) == tuple(preview.shape):
            mask_values = np.asarray(mask_preview) > 0
        render_source = preview
        if mask_mode == "masked_image" and mask_values is not None:
            render_source = np.where(mask_values, preview, np.zeros_like(preview))
        if projection_mode == "minip":
            threshold = int(round(cutoff * max_value))
            points = np.argwhere((render_source > 0) & (render_source <= max(1, threshold)))
        elif projection_mode == "average":
            threshold = int(round(max(0.0, cutoff * 0.65) * max_value))
            points = np.argwhere(render_source > threshold)
        else:
            threshold = int(round(cutoff * max_value / (1.25 if projection_mode == "surface" else 1.0)))
            points = np.argwhere(render_source > threshold)
        if points.size == 0:
            points = np.argwhere(render_source > 0)
        if points.size == 0:
            center_slice = np.asarray(render_source[int(render_source.shape[0] // 2)], dtype=np.uint8)
            return self._render_slice_pixmap(center_slice)

        point_indices = points.copy()
        values = render_source[points[:, 0], points[:, 1], points[:, 2]].astype(np.float32)
        if projection_mode == "minip":
            values = max_value - values
        if max_value > 255.0:
            values = values * (255.0 / max_value)
        source_shape, spacing_zyx = self._volume_source_geometry()
        x_scale, y_scale, z_scale = volume_shape_scale(source_shape or preview.shape, spacing_zyx)
        dims = np.array([max(1, preview.shape[0] - 1), max(1, preview.shape[1] - 1), max(1, preview.shape[2] - 1)], dtype=np.float32)
        coords = points.astype(np.float32) / dims
        coords = coords[:, [2, 1, 0]] - 0.5
        coords[:, 0] *= x_scale
        coords[:, 1] *= y_scale
        coords[:, 2] *= z_scale

        yaw = math.radians(self._volume_yaw)
        pitch = math.radians(self._volume_pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        rot_yaw = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float32)
        rot_pitch = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=np.float32)
        rotated = coords @ (rot_yaw @ rot_pitch).T
        front_clip = max(0.0, min(0.92, float(self.volume_clip_slider.value()) / 100.0))
        if front_clip > 0.0:
            near_depth = float(np.min(rotated[:, 2]))
            far_depth = float(np.max(rotated[:, 2]))
            keep_depth = near_depth + (far_depth - near_depth) * front_clip
            keep = rotated[:, 2] >= keep_depth
            if np.any(keep):
                rotated = rotated[keep]
                values = values[keep]
                point_indices = point_indices[keep]
            else:
                pixmap = QPixmap(360, 360)
                pixmap.fill(QColor("#07090A"))
                return pixmap

        out_size = 360
        scale = (out_size * 0.78) * float(self._volume_zoom)
        center_x = out_size / 2.0 + self._volume_pan_x * scale * 0.5
        center_y = out_size / 2.0 - self._volume_pan_y * scale * 0.5
        px = np.round(rotated[:, 0] * scale + center_x).astype(np.int32)
        py = np.round(-rotated[:, 1] * scale + center_y).astype(np.int32)
        inside = (px >= 0) & (px < out_size) & (py >= 0) & (py < out_size)
        if not np.any(inside):
            pixmap = QPixmap(out_size, out_size)
            pixmap.fill(QColor("#07090A"))
            return pixmap

        px = px[inside]
        py = py[inside]
        depth = rotated[:, 2][inside]
        values = values[inside]
        point_indices = point_indices[inside]

        image = np.zeros((out_size, out_size, 3), dtype=np.uint8)
        shade = 0.65 + 0.35 * np.clip((depth - depth.min()) / max(1e-6, depth.max() - depth.min()), 0.0, 1.0)
        lut = self._volume_transfer_lut()[0]
        lut_index = np.clip(np.round(values), 0, lut.shape[0] - 1).astype(np.int32)
        opacity = lut[lut_index, 3].astype(np.float32) / 255.0
        color_float = lut[lut_index, :3].astype(np.float32) * shade[:, None] * (0.38 + 0.62 * opacity[:, None])
        color = np.clip(color_float, 0, 255).astype(np.uint8)
        if mask_mode == "mask_boundary" and mask_values is not None:
            boundary = self._mask_boundary_preview(mask_values)
            boundary_values = boundary[point_indices[:, 0], point_indices[:, 1], point_indices[:, 2]]
            if np.any(boundary_values):
                opacity = max(0.0, min(1.0, float(self.volume_mask_opacity_slider.value()) / 100.0))
                mask_color = np.asarray([255, 142, 66], dtype=np.float32)
                color_float = color.astype(np.float32)
                color_float[boundary_values] = (1.0 - opacity) * color_float[boundary_values] + opacity * mask_color
                color = np.clip(color_float, 0, 255).astype(np.uint8)
        flat_index = py * out_size + px
        flat = image.reshape((-1, 3))
        for channel in range(3):
            np.maximum.at(flat[:, channel], flat_index, color[:, channel])
        for off_x, off_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx = px + off_x
            ny = py + off_y
            neighbor = (nx >= 0) & (nx < out_size) & (ny >= 0) & (ny < out_size)
            if np.any(neighbor):
                nidx = ny[neighbor] * out_size + nx[neighbor]
                ncolor = (color[neighbor].astype(np.float32) * 0.42).astype(np.uint8)
                for channel in range(3):
                    np.maximum.at(flat[:, channel], nidx, ncolor[:, channel])
        qimage = QImage(np.ascontiguousarray(image).data, out_size, out_size, out_size * 3, QImage.Format_RGB888).copy()
        return QPixmap.fromImage(qimage)

    def paint_at_widget_position(self, x, y, erase=False):
        if self.image_volume is None:
            return
        if self.current_volume_scope == "part":
            message = tt("Part volume is read-only here. Use part mask preview controls for extraction masks.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
            return
        if self.display_mode == "volume":
            message = tt("3D volume preview is read-only. Switch to Slice review for label editing.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
            return
        if self._current_slice_axis() != "z":
            message = tt("Painting is available on Z slices only. Switch back to Z axial view before editing labels.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
            return
        if self.edit_volume is None and not self._ensure_working_edit_volume():
            return
        role = self.label_role_combo.currentData()
        if role != "working_edit":
            if role == "model_draft":
                message = tt("Cannot paint on model draft. Copy model draft to Current edit first.", self.lang)
            else:
                message = tt("Cannot paint on this label layer. Switch to Current edit first.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
            return
        z_index = int(self.slice_slider.value())
        height, width = self.image_volume.shape[1], self.image_volume.shape[2]
        pixel = self._widget_to_image_pixel(x, y, width, height)
        if pixel is None:
            return
        px, py = pixel
        radius = max(1, int(self.brush_size_slider.value()))
        self._push_undo()
        yy, xx = np.ogrid[:height, :width]
        mask = (xx - px) ** 2 + (yy - py) ** 2 <= radius ** 2
        self.edit_volume[z_index][mask] = 0 if erase else int(self.current_material_id)
        self._dirty_edit_slices.add(z_index)
        self._mark_working_edit_dirty()
        self.render_current_slice()

    def _widget_to_image_pixel(self, x, y, image_width, image_height):
        pixel = self.canvas.widget_to_image_pixel(x, y)
        if pixel is None:
            return None
        px, py = pixel
        return max(0, min(image_width - 1, px)), max(0, min(image_height - 1, py))

    def _push_undo(self):
        if self.edit_volume is None:
            return
        if self._current_slice_axis() != "z":
            return
        z_index = int(self.slice_slider.value())
        self.undo_stack.append((z_index, self.edit_volume[z_index].copy()))
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack or self.edit_volume is None:
            return
        z_index, old_slice = self.undo_stack.pop()
        self.redo_stack.append((z_index, self.edit_volume[z_index].copy()))
        self.edit_volume[z_index] = old_slice
        self._dirty_edit_slices.add(z_index)
        if self._current_slice_axis() == "z":
            self.slice_slider.setValue(z_index)
        self._mark_working_edit_dirty()
        self.render_current_slice()

    def redo(self):
        if not self.redo_stack or self.edit_volume is None:
            return
        z_index, redo_slice = self.redo_stack.pop()
        self.undo_stack.append((z_index, self.edit_volume[z_index].copy()))
        self.edit_volume[z_index] = redo_slice
        self._dirty_edit_slices.add(z_index)
        if self._current_slice_axis() == "z":
            self.slice_slider.setValue(z_index)
        self._mark_working_edit_dirty()
        self.render_current_slice()

    def save_working_edit(self, show_message=True, reason="manual"):
        if self._saving_working_edit:
            return True
        if self.current_volume_scope == "part":
            return False
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None or self.edit_volume is None:
            return False
        edit_path = self.project.to_absolute(((specimen.get("labels") or {}).get("working_edit") or {}).get("path", ""))
        if not edit_path:
            return False
        self._saving_working_edit = True
        self.auto_save_timer.stop()
        try:
            self.label_volume = None
            target = load_volume_sidecar(edit_path, mmap_mode="r+")
            if self._dirty_edit_slices:
                for z_index in sorted(self._dirty_edit_slices):
                    if 0 <= int(z_index) < int(target.shape[0]):
                        target[int(z_index)] = self.edit_volume[int(z_index)]
            metadata = flush_volume_array(edit_path, target)
            specimen["labels"]["working_edit"]["dtype"] = metadata["dtype"]
            specimen["labels"]["working_edit"]["status"] = "in_progress"
            specimen["review_status"] = "in_progress"
            specimen["train_ready"] = False
            self.project.save_project()
            self.working_edit_dirty = False
            self._dirty_edit_slices = set()
            self.edit_volume = load_volume_sidecar(edit_path, mmap_mode="c")
            if self.label_role_combo.currentData() == "working_edit":
                self.label_volume = load_volume_sidecar(edit_path, mmap_mode="r")
            else:
                self._reload_label_volume()
            self._update_status_labels(specimen)
        except Exception as exc:
            self.working_edit_dirty = True
            QMessageBox.warning(self, tt("Unsaved working edit", self.lang), str(exc))
            return False
        finally:
            self._saving_working_edit = False
        if show_message:
            message = tt("Auto-saved working edit.", self.lang) if reason == "auto_save" else tt("Working edit saved.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
        return True

    def promote_working_edit(self):
        if not self.current_specimen_id:
            return
        if self.current_volume_scope == "part":
            QMessageBox.information(self, tt("Accept working edit", self.lang), tt("Part volumes are not promoted to full-volume manual truth in this version.", self.lang))
            return
        if not self.save_working_edit(show_message=False):
            return
        reply = QMessageBox.question(
            self,
            tt("Accept working edit", self.lang),
            tt("Promote the current working_edit layer to manual_truth for training?", self.lang),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.project.promote_working_edit_to_manual_truth(self.current_specimen_id)
        self._reload_label_volume()
        specimen = self.project.get_specimen(self.current_specimen_id)
        self._update_status_labels(specimen)
        self.refresh_project()

    def copy_latest_model_draft_to_working_edit(self):
        if not self.current_specimen_id:
            return
        if self.current_volume_scope == "part":
            QMessageBox.information(self, tt("TIF backend", self.lang), tt("Part volumes do not use model draft handoff in this version.", self.lang))
            return
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        drafts = ((specimen or {}).get("labels") or {}).get("model_drafts") or []
        if not drafts:
            QMessageBox.warning(
                self,
                tt("TIF backend", self.lang),
                tt("No model draft is available for this specimen.", self.lang),
            )
            return
        try:
            self.project.copy_label_layer_to_working_edit(self.current_specimen_id, source_role="model_draft")
        except Exception as exc:
            QMessageBox.warning(self, tt("TIF backend", self.lang), str(exc))
            return
        index = self.label_role_combo.findData("working_edit")
        if index >= 0:
            self.label_role_combo.setCurrentIndex(index)
        self.load_specimen(self.current_specimen_id)
        message = tt("Copied latest model draft into working_edit.", self.lang)
        self.training_status_label.setText(message)
        self.log(message)

    def export_training_dataset(self):
        if not self.project.current_project_path:
            QMessageBox.warning(self, tt("TIF training handoff", self.lang), tt("Please create or open a TIF project first.", self.lang))
            return
        default_dir = os.path.join(self.project.project_dir, "exports", "train_ready")
        os.makedirs(default_dir, exist_ok=True)
        output_dir = QFileDialog.getExistingDirectory(self, tt("Export train-ready TIF volumes", self.lang), default_dir)
        if not output_dir:
            return
        formats = [
            item.strip()
            for item in self.backend_formats_edit.text().split(",")
            if item.strip()
        ]
        try:
            result = export_tif_training_dataset(
                self.project,
                output_dir,
                formats=formats or ["ome_tiff", "nrrd", "mha", "nifti"],
                require_train_ready=True,
            )
        except Exception as exc:
            QMessageBox.warning(self, tt("TIF training handoff", self.lang), str(exc))
            message = tt("Export failed: {0}", self.lang).format(str(exc))
            self.training_status_label.setText(message)
            self.log(message)
            return
        manifest_path = result.get("manifest_path", "")
        exported_count = result.get("exported_count", 0)
        message = tt("Exported {0} train-ready specimen(s).\nManifest: {1}", self.lang).format(exported_count, manifest_path)
        self.training_status_label.setText(message)
        self.log(message)
        QMessageBox.information(
            self,
            tt("TIF training handoff", self.lang),
            message,
        )

    def export_current_part_package(self):
        if self.current_volume_scope != "part" or not self.current_specimen_id or not self.current_part_id:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Select a part volume before exporting a part package.", self.lang))
            return
        default_dir = os.path.join(self.project.project_dir, "exports", "parts")
        os.makedirs(default_dir, exist_ok=True)
        output_dir = QFileDialog.getExistingDirectory(self, tt("Export part package", self.lang), default_dir)
        if not output_dir:
            return
        try:
            result = export_part_package(self.project, self.current_specimen_id, self.current_part_id, output_dir)
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        manifest_path = result.get("manifest_path", "")
        package_dir = result.get("package_dir", "") or os.path.dirname(manifest_path)
        package_name = os.path.basename(os.path.normpath(package_dir)) if package_dir else "-"
        manifest_name = os.path.basename(manifest_path) if manifest_path else "-"
        message = tt("Exported part package.\nFolder: {0}\nManifest: {1}", self.lang).format(package_name, manifest_name)
        full_message = tt("Exported part package.\nFolder: {0}\nManifest: {1}", self.lang).format(package_dir or "-", manifest_path or "-")
        self.training_status_label.setText(message)
        self.training_status_label.setToolTip(full_message)
        self.log(full_message)
        QMessageBox.information(self, tt("Part extraction", self.lang), message)

    def open_local_axis_reslice_dialog(self, specimen_id=None, part_id=None, proposal_id=""):
        target_specimen_id = str(specimen_id or self.current_specimen_id or "")
        target_part_id = str(part_id or self.current_part_id or "")
        if not target_specimen_id or not target_part_id:
            QMessageBox.information(self, tt("Local Axis Reslice", self.lang), tt("Select a part volume before opening Local Axis Reslice.", self.lang))
            return None
        try:
            initial_draft = (
                self._current_local_axis_draft()
                if not proposal_id and target_specimen_id == self.current_specimen_id and target_part_id == self.current_part_id
                else None
            )
            dialog = TifLocalAxisResliceDialog(
                self.project,
                target_specimen_id,
                target_part_id,
                proposal_id=proposal_id,
                parent=self,
                lang=self.lang,
                initial_draft=initial_draft,
            )
        except Exception as exc:
            QMessageBox.warning(self, tt("Local Axis Reslice", self.lang), str(exc))
            return None
        result = None
        if dialog.exec() == QDialog.Accepted:
            result = dialog.export_result
            record = (result or {}).get("record", {}) if isinstance(result, dict) else {}
            reslice_id = record.get("reslice_id", "")
            message = tt("Exported local axis reslice {0}.", self.lang).format(reslice_id)
            self.training_status_label.setText(message)
            self.log(message)
            draft = self._current_local_axis_draft()
            if draft is not None and target_specimen_id == self.current_specimen_id and target_part_id == self.current_part_id:
                self.local_axis_draft = None
            self.refresh_project()
            self._select_volume_tree_item(target_specimen_id, "part_reslice", target_part_id, reslice_id)
        dialog.deleteLater()
        return result

    def open_local_axis_review_queue(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tt("Review Local Axis Queue", self.lang))
        dialog.resize(980, 620)
        layout = QVBoxLayout(dialog)
        queue = TifLocalAxisReviewQueueWidget(self.project, parent=dialog, lang=self.lang)
        queue.open_proposal_requested.connect(lambda specimen_id, part_id, proposal_id: self.open_local_axis_reslice_dialog(specimen_id, part_id, proposal_id))
        layout.addWidget(queue)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
        self.refresh_project()
        dialog.deleteLater()
        return queue

    def open_local_axis_model_dialog(self):
        if not self._ensure_tif_project_open():
            return None
        dialog = TifLocalAxisModelDialog(
            self.project,
            parent=self,
            lang=self.lang,
            config_manager=self.config_manager,
            specimen_id=self.current_specimen_id,
            part_id=self.current_part_id if self.current_volume_scope == "part" else "",
        )
        dialog.exec()
        self.refresh_project()
        dialog.deleteLater()
        return dialog

    def _render_slice_pixmap(self, image_slice, label_slice=None):
        gray = self._normalize_image(image_slice)
        rgb = np.stack([gray, gray, gray], axis=-1)
        if label_slice is not None and self.opacity_slider.value() > 0:
            alpha = self.opacity_slider.value() / 100.0
            mask = label_slice > 0
            if np.any(mask):
                overlay = np.zeros_like(rgb)
                for material_id in np.unique(label_slice[mask]):
                    color = self.material_colors.get(int(material_id), QColor("#ff4b4b"))
                    overlay[label_slice == material_id] = [color.red(), color.green(), color.blue()]
                rgb[mask] = ((1.0 - alpha) * rgb[mask].astype(np.float32) + alpha * overlay[mask].astype(np.float32)).astype(np.uint8)
        height, width = rgb.shape[:2]
        rgb = np.ascontiguousarray(rgb)
        image = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format_RGB888).copy()
        return QPixmap.fromImage(image)

    def _normalize_image(self, image_slice):
        data = np.asarray(image_slice, dtype=np.float32)
        finite = data[np.isfinite(data)]
        if finite.size == 0:
            return np.zeros(data.shape, dtype=np.uint8)
        low = float(np.percentile(finite, 1))
        high = float(np.percentile(finite, 99))
        if high <= low:
            low = float(np.min(finite))
            high = float(np.max(finite))
        if high <= low:
            return np.zeros(data.shape, dtype=np.uint8)
        normalized = (data - low) / (high - low)
        contrast = self.contrast_slider.value() / 10.0
        brightness = self.brightness_slider.value() / 100.0
        normalized = (normalized - 0.5) * contrast + 0.5 + brightness
        return np.clip(normalized * 255.0, 0, 255).astype(np.uint8)
