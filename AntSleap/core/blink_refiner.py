import numpy as np
import cv2
from .projection import CoordinateMapper
from .runtime_device import normalize_device_preference, resolve_torch_device

class BlinkRefiner:
    """
    BLINK 核心算法引擎 (遵循概念白皮书重构版)：
    倒果为因。以人类专家的“黄金多边形(Golden Polygon)”为靶心，
    从初始松散框生成向物理极限逼近的渐进式收缩轨迹。
    这是生成 Blink 算法训练数据集的核心。
    """
    def __init__(self, sam_model, device='auto'):
        self.sam = sam_model
        self.device_preference = normalize_device_preference(device)
        self.device = resolve_torch_device(self.device_preference)

    def _resolve_image_size(self, image_input):
        """统一解析输入图像尺寸，返回 (width, height)。"""
        if isinstance(image_input, np.ndarray) and image_input.ndim >= 2:
            h, w = image_input.shape[:2]
            return float(w), float(h)
        if isinstance(image_input, str):
            img_np = cv2.imread(image_input)
            if img_np is not None:
                h, w = img_np.shape[:2]
                return float(w), float(h)
        return None
        
    def generate_shrink_trajectory(self, image_input, initial_box, golden_poly, steps=20, pad_ratio=0.03):
        """
        生成从松散框逼近黄金目标的轨迹。
        
        :param image_input: 局部高清特写图 (numpy 数组或图像路径)
        :param initial_box: [x1, y1, x2, y2] 用户画的初始松散大框
        :param golden_poly: [[x,y], ...] 专家精修确认过的黄金真值掩码
        :param steps: 轨迹的总帧数
        :param pad_ratio: (新增) 目标框比极限界框大多少比例。SAM 需要边缘外的一点点上下文(Context)才能准确分割。
        :return: trajectory_history (包含每一步的框和 SAM 反馈)
        """
        if not golden_poly or len(golden_poly) < 3:
            print("Shrink Refiner Error: Missing golden polygon. Human expert must provide a baseline.")
            return []

        # 1. 确定绝对真理目标 (Target Box)
        poly_np = np.array(golden_poly)
        mask_x_min, mask_y_min = np.min(poly_np, axis=0)
        mask_x_max, mask_y_max = np.max(poly_np, axis=0)
        
        # 计算宽度和高度
        w = mask_x_max - mask_x_min
        h = mask_y_max - mask_y_min
        
        # 目标框：给完美贴合的外接矩形加上 1% ~ 5% 的 Padding，防止贴死边缘导致 SAM 瞎掉
        target_box = [
            mask_x_min - w * pad_ratio, 
            mask_y_min - h * pad_ratio, 
            mask_x_max + w * pad_ratio, 
            mask_y_max + h * pad_ratio
        ]

        image_size = self._resolve_image_size(image_input)
        img_w, img_h = None, None
        if image_size is not None:
            img_w, img_h = image_size
            target_box = CoordinateMapper.clamp_bbox_to_size(target_box, img_w, img_h)
            initial_box = CoordinateMapper.clamp_bbox_to_size(initial_box, img_w, img_h)
        else:
            target_box = CoordinateMapper.sanitize_bbox_xyxy(target_box)
            initial_box = CoordinateMapper.sanitize_bbox_xyxy(initial_box)
        
        trajectory = []
        
        # 2. 线性插值生成轨迹
        for i in range(steps + 1):
            # 进度比例 (0.0 到 1.0)
            alpha = i / float(steps)
            
            # 当前帧的框坐标 (在 initial_box 和 target_box 之间滑动)
            current_box = [
                initial_box[0] + (target_box[0] - initial_box[0]) * alpha,
                initial_box[1] + (target_box[1] - initial_box[1]) * alpha,
                initial_box[2] + (target_box[2] - initial_box[2]) * alpha,
                initial_box[3] + (target_box[3] - initial_box[3]) * alpha
            ]

            if image_size is not None and img_w is not None and img_h is not None:
                current_box = CoordinateMapper.clamp_bbox_to_size(current_box, img_w, img_h)
            else:
                current_box = CoordinateMapper.sanitize_bbox_xyxy(current_box)
            
            # 3. 记录环境特征 (可选：在这里调用 SAM 获取当前非完美框下的特征浓度反馈，供以后强化学习使用)
            # 为了速度，当前仅记录轨迹坐标
            
            trajectory.append({
                "step": i,
                "alpha": alpha,
                "box": current_box,
                "is_golden": (i == steps),
                "coord_frame": "local_zoom",
                "target_box": target_box,
            })
            
        print(f"Trajectory generated successfully. {len(trajectory)} frames targeting the golden baseline.")
        return trajectory

