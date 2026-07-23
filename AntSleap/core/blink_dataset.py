import os
import json
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset
import random
from .projection import CoordinateMapper
from .training_truth import resolve_part_training_trust
try:
    from .blink_training_strategy import (
        BLINK_STRATEGY_FULL_INSIDE_RANDOM,
        BLINK_STRATEGY_TRIVIEW_RANDOM,
        BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
        sanitize_blink_training_strategy,
    )
except ImportError:
    from blink_training_strategy import (
        BLINK_STRATEGY_FULL_INSIDE_RANDOM,
        BLINK_STRATEGY_TRIVIEW_RANDOM,
        BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
        sanitize_blink_training_strategy,
    )

class BlinkTrajectoryDataset(Dataset):
    """
    眨眼轨迹数据集 (The Blink DataLoader)
    
    专门为训练“通用微观专家模型”设计。
    核心能力：
    1. 加载 ProjectManager 保存的收缩轨迹 (Trajectories)。
    2. 动态应用 Blink 遮罩增强 (Inside-View / Outside-View)。
    3. 生成回归目标 (Regression Targets)。
    """
    def __init__(
        self,
        project_json_path,
        part_name="Mandible",
        parent_part=None,
        target_size=(512, 512),
        blink_prob=0.5,
        training_strategy=BLINK_STRATEGY_TRIVIEW_RANDOM,
        stage_view_mode=None,
        allowed_image_paths=None,
        training_records=None,
    ):
        """
        :param project_json_path: project.json 的路径
        :param part_name: 专注训练的解剖学部位 (如 Mandible)
        :param target_size: 网络输入的固定分辨率
        :param blink_prob: 触发 Blink 遮罩的概率
        """
        self.project_path = project_json_path
        self.part_name = part_name
        self.parent_part = str(parent_part).strip() if isinstance(parent_part, str) and parent_part.strip() else None
        self.target_size = target_size
        self.blink_prob = blink_prob
        self.training_strategy = sanitize_blink_training_strategy(training_strategy)
        self.stage_view_mode = str(stage_view_mode or "").strip().lower()
        self.allowed_image_paths = self._normalize_allowed_image_paths(allowed_image_paths)
        self.training_records = list(training_records or [])
        self.samples = []
        
        self._load_data()

    def _normalize_allowed_image_paths(self, image_paths):
        if not image_paths:
            return None
        allowed = set()
        for image_path in image_paths:
            text = str(image_path or "").strip()
            if not text:
                continue
            allowed.add(os.path.normcase(os.path.normpath(text)))
            allowed.add(os.path.normcase(os.path.abspath(os.path.normpath(text))))
        return allowed or None

    def _is_allowed_image_path(self, rel_img_path, abs_img_path):
        if not self.allowed_image_paths:
            return True
        rel_key = os.path.normcase(os.path.normpath(str(rel_img_path or "")))
        abs_key = os.path.normcase(os.path.abspath(os.path.normpath(str(abs_img_path or ""))))
        return rel_key in self.allowed_image_paths or abs_key in self.allowed_image_paths

    def _safe_box(self, box, width, height):
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            return [0.0, 0.0, max(1.0, width * 0.05), max(1.0, height * 0.05)]
        return CoordinateMapper.clamp_bbox_to_size(box, width, height)

    def _img_to_tensor(self, img_np):
        img_resized = cv2.resize(img_np, self.target_size)
        return torch.from_numpy(img_resized.copy()).permute(2, 0, 1).float() / 255.0
        
    def _load_data(self):
        if not self.training_records and not os.path.exists(self.project_path):
            print(f"Dataset Error: {self.project_path} not found.")
            return
        proj_dir = os.path.dirname(self.project_path)
        if self.training_records:
            label_items = list(self.training_records)
        else:
            with open(self.project_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            label_items = list(data.get("labels", {}).items())
        
        # 遍历所有图片，寻找包含目标部位轨迹的数据
        for rel_img_path, label_data in label_items:
            if not isinstance(label_data, dict):
                continue
            if not resolve_part_training_trust(label_data, self.part_name).get("eligible"):
                continue
            trajectories = label_data.get("trajectories", {})
            if self.part_name in trajectories:
                traj_payload = trajectories[self.part_name]
                parent_context = {}
                if isinstance(traj_payload, dict):
                    traj_list = traj_payload.get("frames", [])
                    parent_context = traj_payload.get("parent_context", {}) if isinstance(traj_payload.get("parent_context", {}), dict) else {}
                else:
                    traj_list = traj_payload

                if not isinstance(traj_list, list) or len(traj_list) < 1:
                    continue

                sample_parent_part = str(parent_context.get("parent_part") or "").strip() or None
                if self.parent_part and sample_parent_part != self.parent_part:
                    continue
                # 原始大图的绝对路径
                abs_img_path = (
                    os.path.normpath(rel_img_path)
                    if os.path.isabs(str(rel_img_path))
                    else os.path.normpath(os.path.join(proj_dir, rel_img_path))
                )
                if not self._is_allowed_image_path(rel_img_path, abs_img_path):
                    continue
                
                # 记录这整个轨迹序列作为一组样本
                # 我们可以在 __getitem__ 中随机抽取轨迹中的某一帧
                self.samples.append({
                    "image_path": abs_img_path,
                    "trajectory": traj_list,
                    "parent_context": parent_context,
                })
                
        parent_suffix = f" within {self.parent_part}" if self.parent_part else ""
        print(f"Blink Dataset initialized: Found {len(self.samples)} valid image sequences for {self.part_name}{parent_suffix}.")

    def __len__(self):
        # 放大样本量：每个序列由于包含数十个中间帧，我们在每个 epoch 随机采一次
        # 这里定义长度为序列数 * 10 (保证每个 epoch 能多看几帧不同的松紧度)
        return len(self.samples) * 10
        
    def apply_blink_mask(self, img_np, box, blink_type):
        """
        应用眨眼遮罩的核心逻辑
        :param img_np: 图像张量
        :param box: [x1, y1, x2, y2]
        :param blink_type: "INSIDE" 或 "OUTSIDE"
        """
        x1, y1, x2, y2 = map(int, box)
        h, w = img_np.shape[:2]
        
        # 边界保护
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        masked_img = np.zeros_like(img_np)
        
        if blink_type == "INSIDE":
            # 只保留框内，框外涂黑
            masked_img[y1:y2, x1:x2] = img_np[y1:y2, x1:x2]
        elif blink_type == "OUTSIDE":
            # 保留框外，抠掉框内
            masked_img = img_np.copy()
            masked_img[y1:y2, x1:x2] = 0
            
        return masked_img

    def __getitem__(self, idx):
        # 1. 抽取样本
        sample_idx = idx % len(self.samples)
        sample_data = self.samples[sample_idx]
        
        # 2. 随机选择轨迹中的一帧
        trajectory = sample_data["trajectory"]
        if len(trajectory) > 1:
            # 偏向于选择靠近黄金目标的帧 (同时预留 frame+1 作为过程监督目标)
            lower = max(0, len(trajectory) // 2 - 1)
            upper = max(lower, len(trajectory) - 2)
            frame_idx = random.randint(lower, upper)
        else:
            frame_idx = 0
        frame = trajectory[frame_idx]
        next_frame = trajectory[min(frame_idx + 1, len(trajectory) - 1)]
        parent_context = sample_data.get("parent_context", {}) if isinstance(sample_data.get("parent_context", {}), dict) else {}
        
        # 输入框（用于眨眼遮罩）和监督框
        global_box = frame.get("box", [0, 0, 10, 10])
        step_target_box = next_frame.get("box", global_box)
        golden_box = trajectory[-1].get("box", step_target_box)
        
        # 3. 加载图片并优先按父级视野裁剪，保证训练输入和级联推理视野一致。
        img_np = cv2.imread(sample_data["image_path"])
        if img_np is not None:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
            src_h, src_w = img_np.shape[:2]
        else:
            # Fallback
            img_np = np.zeros((self.target_size[1], self.target_size[0], 3), dtype=np.uint8)
            src_h, src_w = self.target_size[1], self.target_size[0]
            global_box = [0, 0, 10, 10]
            step_target_box = [0, 0, 10, 10]
            golden_box = [0, 0, 10, 10]

        # 坐标安全化（原图坐标系）
        global_box = self._safe_box(global_box, src_w, src_h)
        step_target_box = self._safe_box(step_target_box, src_w, src_h)
        golden_box = self._safe_box(golden_box, src_w, src_h)

        parent_box = parent_context.get("parent_box") if isinstance(parent_context, dict) else None
        has_parent_crop = isinstance(parent_box, (list, tuple)) and len(parent_box) == 4
        if has_parent_crop:
            parent_box = self._safe_box(parent_box, src_w, src_h)
            mapper = CoordinateMapper((src_w, src_h), parent_box, target_size=self.target_size)
            crop_img_np = mapper.crop_and_resize(img_np)
            source_img_np = crop_img_np
            global_box = mapper.bbox_global_to_local(global_box)
            step_target_box = mapper.bbox_global_to_local(step_target_box)
            golden_box = mapper.bbox_global_to_local(golden_box)
            src_h, src_w = self.target_size[1], self.target_size[0]
        else:
            source_img_np = img_np

        # 4. 生成视角：主视角用于本轮输入，Inside/Outside 仅在方案一中参与额外对照 loss。
        inside_img_np = self.apply_blink_mask(source_img_np, global_box, "INSIDE")
        outside_img_np = self.apply_blink_mask(source_img_np, global_box, "OUTSIDE")

        primary_img_np = source_img_np
        primary_view = "full"
        if self.training_strategy == BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE:
            if self.stage_view_mode == "inside":
                primary_img_np = inside_img_np
                primary_view = "inside"
            else:
                primary_img_np = source_img_np
                primary_view = "full"
        elif self.training_strategy == BLINK_STRATEGY_FULL_INSIDE_RANDOM:
            if random.random() < self.blink_prob:
                primary_img_np = inside_img_np
                primary_view = "inside"
        elif random.random() < self.blink_prob:
            if random.random() < 0.5:
                primary_img_np = inside_img_np
                primary_view = "inside"
            else:
                primary_img_np = outside_img_np
                primary_view = "outside"

        # 5. 目标框映射到网络输入尺寸，再转归一化坐标
        if has_parent_crop:
            step_box_scaled = CoordinateMapper.clamp_bbox_to_size(step_target_box, self.target_size[0], self.target_size[1])
            final_box_scaled = CoordinateMapper.clamp_bbox_to_size(golden_box, self.target_size[0], self.target_size[1])
        else:
            step_box_scaled = CoordinateMapper.scale_bbox(step_target_box, (src_w, src_h), self.target_size)
            final_box_scaled = CoordinateMapper.scale_bbox(golden_box, (src_w, src_h), self.target_size)

        target_step = torch.tensor(
            CoordinateMapper.bbox_to_normalized(step_box_scaled, self.target_size),
            dtype=torch.float32,
        )
        target_final = torch.tensor(
            CoordinateMapper.bbox_to_normalized(final_box_scaled, self.target_size),
            dtype=torch.float32,
        )

        return {
            "image": self._img_to_tensor(primary_img_np),
            "inside_image": self._img_to_tensor(inside_img_np),
            "outside_image": self._img_to_tensor(outside_img_np),
            "target_step": target_step,
            "target_final": target_final,
            "view_mode": primary_view,
        }
