import json
import os
import random

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset

from .projection import CoordinateMapper
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


def _safe_positive_int(value, fallback):
    try:
        number = int(value)
    except Exception:
        number = int(fallback)
    return max(1, number)


def _gaussian_heatmap(width, height, center_x, center_y, sigma):
    xs = np.arange(width, dtype=np.float32)[None, :]
    ys = np.arange(height, dtype=np.float32)[:, None]
    sigma = max(float(sigma), 0.1)
    heatmap = np.exp(-((xs - float(center_x)) ** 2 + (ys - float(center_y)) ** 2) / (2.0 * sigma * sigma))
    return heatmap.astype(np.float32)


class BlinkHeatmapDataset(Dataset):
    def __init__(
        self,
        project_json_path,
        child_part,
        parent_part=None,
        input_size=512,
        heatmap_sigma=2.0,
        blink_prob=0.5,
        training_strategy=BLINK_STRATEGY_TRIVIEW_RANDOM,
        stage_view_mode=None,
    ):
        self.project_json_path = str(project_json_path or "")
        self.child_part = str(child_part or "").strip()
        self.parent_part = str(parent_part or "").strip() or None
        self.input_size = _safe_positive_int(input_size, 512)
        self.heatmap_sigma = float(heatmap_sigma or 2.0)
        self.blink_prob = max(0.0, min(1.0, float(blink_prob)))
        self.training_strategy = sanitize_blink_training_strategy(training_strategy)
        self.stage_view_mode = str(stage_view_mode or "").strip().lower()
        self.samples = []
        self._load_samples()
        self.sequence_count = len(self.samples)

    def _load_samples(self):
        if not self.project_json_path or not os.path.exists(self.project_json_path):
            return
        with open(self.project_json_path, "r", encoding="utf-8") as handle:
            project_data = json.load(handle)
        if not isinstance(project_data, dict):
            return
        project_dir = os.path.dirname(os.path.abspath(self.project_json_path))
        labels = project_data.get("labels", {})
        if not isinstance(labels, dict):
            return

        for image_path, label_data in labels.items():
            if not isinstance(label_data, dict):
                continue
            trajectories = label_data.get("trajectories", {})
            if not isinstance(trajectories, dict) or self.child_part not in trajectories:
                continue
            trajectory_payload = trajectories.get(self.child_part)
            if isinstance(trajectory_payload, dict):
                frames = trajectory_payload.get("frames", [])
                parent_context = trajectory_payload.get("parent_context", {})
            else:
                frames = trajectory_payload
                parent_context = {}
            if not isinstance(frames, list) or not frames:
                continue
            if not isinstance(parent_context, dict):
                parent_context = {}
            sample_parent = str(parent_context.get("parent_part") or "").strip()
            if self.parent_part and sample_parent != self.parent_part:
                continue
            parent_box = parent_context.get("parent_box")
            if not isinstance(parent_box, (list, tuple)) or len(parent_box) != 4:
                continue
            final_frame = frames[-1] if isinstance(frames[-1], dict) else {}
            child_box = final_frame.get("box")
            if not isinstance(child_box, (list, tuple)) or len(child_box) != 4:
                continue
            absolute_image = image_path
            if not os.path.isabs(str(absolute_image)):
                absolute_image = os.path.join(project_dir, str(absolute_image))
            self.samples.append(
                {
                    "image_path": os.path.normpath(absolute_image),
                    "parent_box": list(parent_box),
                    "trajectory": [frame for frame in frames if isinstance(frame, dict)],
                    "child_box": list(child_box),
                }
            )

    def __len__(self):
        return len(self.samples) * 10

    def _image_to_tensor(self, image_np):
        image_np = np.ascontiguousarray(image_np)
        return torch.from_numpy(image_np).permute(2, 0, 1).float() / 255.0

    def _safe_box(self, box, width, height):
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            return [0.0, 0.0, max(1.0, width * 0.05), max(1.0, height * 0.05)]
        return CoordinateMapper.clamp_bbox_to_size(box, width, height)

    def _apply_blink_mask(self, image_np, box, mode):
        x1, y1, x2, y2 = [int(round(float(value))) for value in box]
        height, width = image_np.shape[:2]
        x1 = max(0, min(width, x1))
        x2 = max(0, min(width, x2))
        y1 = max(0, min(height, y1))
        y2 = max(0, min(height, y2))
        if x2 <= x1 or y2 <= y1:
            return image_np.copy()
        if mode == "inside":
            masked = np.zeros_like(image_np)
            masked[y1:y2, x1:x2] = image_np[y1:y2, x1:x2]
            return masked
        masked = image_np.copy()
        masked[y1:y2, x1:x2] = 0
        return masked

    def _target_from_box(self, local_box):
        x1, y1, x2, y2 = local_box
        center_x = (x1 + x2) * 0.5
        center_y = (y1 + y2) * 0.5
        box_w = max(1.0, x2 - x1) / float(self.input_size)
        box_h = max(1.0, y2 - y1) / float(self.input_size)
        heatmap = _gaussian_heatmap(
            self.input_size,
            self.input_size,
            center_x,
            center_y,
            self.heatmap_sigma,
        )
        return {
            "heatmap": torch.from_numpy(heatmap).unsqueeze(0),
            "wh": torch.tensor([box_w, box_h], dtype=torch.float32),
            "local_box": torch.tensor(local_box, dtype=torch.float32),
        }

    def __getitem__(self, index):
        sample = self.samples[index % len(self.samples)]
        trajectory = sample.get("trajectory", [])
        if len(trajectory) > 1:
            lower = max(0, len(trajectory) // 2 - 1)
            upper = max(lower, len(trajectory) - 2)
            frame_index = random.randint(lower, upper)
        else:
            frame_index = 0
        frame = trajectory[frame_index] if frame_index < len(trajectory) else {}
        next_frame = trajectory[min(frame_index + 1, len(trajectory) - 1)] if trajectory else {}

        image_np = cv2.imread(sample["image_path"])
        if image_np is None:
            image_np = np.zeros((self.input_size, self.input_size, 3), dtype=np.uint8)
        else:
            image_np = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
        src_h, src_w = image_np.shape[:2]
        parent_box = self._safe_box(sample["parent_box"], src_w, src_h)
        current_box = self._safe_box(frame.get("box", sample["child_box"]), src_w, src_h)
        step_box = self._safe_box(next_frame.get("box", sample["child_box"]), src_w, src_h)
        final_box = self._safe_box(sample["child_box"], src_w, src_h)

        mapper = CoordinateMapper((src_w, src_h), parent_box, target_size=(self.input_size, self.input_size))
        crop_np = mapper.crop_and_resize(image_np)
        current_local_box = CoordinateMapper.clamp_bbox_to_size(
            mapper.bbox_global_to_local(current_box),
            self.input_size,
            self.input_size,
        )
        step_local_box = CoordinateMapper.clamp_bbox_to_size(
            mapper.bbox_global_to_local(step_box),
            self.input_size,
            self.input_size,
        )
        final_local_box = CoordinateMapper.clamp_bbox_to_size(
            mapper.bbox_global_to_local(final_box),
            self.input_size,
            self.input_size,
        )

        inside_np = self._apply_blink_mask(crop_np, current_local_box, "inside")
        outside_np = self._apply_blink_mask(crop_np, current_local_box, "outside")
        primary_np = crop_np
        primary_view = "full"
        if self.training_strategy == BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE:
            if self.stage_view_mode == "inside":
                primary_np = inside_np
                primary_view = "inside"
            else:
                primary_np = crop_np
                primary_view = "full"
        elif self.training_strategy == BLINK_STRATEGY_FULL_INSIDE_RANDOM:
            if random.random() < self.blink_prob:
                primary_np = inside_np
                primary_view = "inside"
        elif random.random() < self.blink_prob:
            if random.random() < 0.5:
                primary_np = inside_np
                primary_view = "inside"
            else:
                primary_np = outside_np
                primary_view = "outside"

        final_target = self._target_from_box(final_local_box)
        step_target = self._target_from_box(step_local_box)
        return {
            "image": self._image_to_tensor(primary_np),
            "inside_image": self._image_to_tensor(inside_np),
            "outside_image": self._image_to_tensor(outside_np),
            "heatmap": final_target["heatmap"],
            "wh": final_target["wh"],
            "local_box": final_target["local_box"],
            "step_heatmap": step_target["heatmap"],
            "step_wh": step_target["wh"],
            "step_local_box": step_target["local_box"],
            "view_mode": primary_view,
        }
