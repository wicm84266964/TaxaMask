# pyright: reportMissingImports=false

import os
import time
import csv
import json
from datetime import datetime
from typing import Callable, Optional

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import DataLoader
import numpy as np
import cv2
try:
    from AntSleap.models.expert_networks import MicroExpertLocator
except ImportError:
    from models.expert_networks import MicroExpertLocator
from .blink_dataset import BlinkTrajectoryDataset
from .taxonomy_defaults import is_safe_part_name
from torchvision.ops import generalized_box_iou_loss, box_convert
try:
    from AntSleap.core.blink_training_strategy import (
        BLINK_STRATEGY_FULL_INSIDE_RANDOM,
        BLINK_STRATEGY_TRIVIEW_RANDOM,
        BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
        blink_training_strategy_label,
        sanitize_blink_training_strategy,
    )
except ImportError:
    from .blink_training_strategy import (
        BLINK_STRATEGY_FULL_INSIDE_RANDOM,
        BLINK_STRATEGY_TRIVIEW_RANDOM,
        BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
        blink_training_strategy_label,
        sanitize_blink_training_strategy,
    )
try:
    from AntSleap.core.runtime_device import resolve_torch_device
except ImportError:
    from .runtime_device import resolve_torch_device
try:
    from AntSleap.core.blink_expert_manifest import (
        BLINK_EXPERT_BACKEND_VIT_B,
        default_manifest_path_for_weights,
        write_blink_expert_manifest,
    )
except ImportError:
    from .blink_expert_manifest import (
        BLINK_EXPERT_BACKEND_VIT_B,
        default_manifest_path_for_weights,
        write_blink_expert_manifest,
    )

try:
    import matplotlib.pyplot as plt
    HAS_PLOT = True
except Exception:
    plt = None
    HAS_PLOT = False

class BlinkExpertTrainer:
    """
    BLINK 微观专家模型训练器
    
    采用 Generalized IoU (GIoU) Loss 来惩罚预测框和黄金掩码框之间的偏差。
    通过学习你在 Blink Lab 里留下的那几百条“收缩轨迹”，它能学会一步到位的极限预测。
    """
    def __init__(
        self,
        project_path,
        part_name,
        parent_part=None,
        device='auto',
        save_dir=None,
        learning_rate=1e-3,
        weight_decay=1e-4,
        input_size=224,
        training_strategy=BLINK_STRATEGY_TRIVIEW_RANDOM,
        allowed_image_paths=None,
        training_scope=None,
    ):
        self.device = resolve_torch_device(device)
        self.part_name = str(part_name).strip()
        if not is_safe_part_name(self.part_name):
            raise ValueError(f"Unsafe Blink expert part name: {self.part_name}")
        self.parent_part = str(parent_part).strip() if isinstance(parent_part, str) and parent_part.strip() else None
        self.project_path = project_path
        self.learning_rate = float(learning_rate)
        self.weight_decay = float(weight_decay)
        self.input_size = self._normalize_input_size(input_size)
        self.training_strategy = sanitize_blink_training_strategy(training_strategy)
        self.allowed_image_paths = [str(path) for path in (allowed_image_paths or []) if str(path or "").strip()]
        self.training_scope = dict(training_scope or {})
        self.history = {
            "loss": [],
            "loss_final": [],
            "loss_step": [],
            "loss_view": [],
            "loss_consistency": [],
            "stage": [],
        }
        self.last_report = {}

        if save_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            save_dir = os.path.join(base_dir, "weights", "experts")

        expert_root = os.path.abspath(save_dir)
        target_dir = os.path.abspath(os.path.join(expert_root, self.part_name))
        if os.path.commonpath([expert_root, target_dir]) != expert_root:
            raise ValueError(f"Unsafe Blink expert save path for part: {self.part_name}")

        # 确保保存目录存在
        self.save_dir = target_dir
        os.makedirs(self.save_dir, exist_ok=True)
        
        # 实例化我们刚才写的轻量级小网络
        self.model = MicroExpertLocator(pretrained=True, image_size=self.input_size[0]).to(self.device)
        self.optimizer = optim.AdamW(self.model.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
        
        # 动态学习率调度器
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(self.optimizer, mode='min', factor=0.5, patience=5)

    def _normalize_input_size(self, value):
        if isinstance(value, (list, tuple)) and value:
            raw_value = value[0]
        else:
            raw_value = value
        try:
            side = int(raw_value)
        except Exception:
            side = 224
        allowed = [224, 384, 512]
        if side not in allowed:
            side = min(allowed, key=lambda candidate: abs(candidate - side))
        return (side, side)

    def _sanitize_xyxy_rel(self, boxes_rel):
        """将归一化框约束到合法区间，并保证 x2>x1, y2>y1。"""
        boxes_rel = boxes_rel.clamp(0.0, 1.0)
        x1 = torch.minimum(boxes_rel[:, 0], boxes_rel[:, 2])
        y1 = torch.minimum(boxes_rel[:, 1], boxes_rel[:, 3])
        x2 = torch.maximum(boxes_rel[:, 0], boxes_rel[:, 2])
        y2 = torch.maximum(boxes_rel[:, 1], boxes_rel[:, 3])

        eps = 1e-4
        x2 = torch.maximum(x2, x1 + eps)
        y2 = torch.maximum(y2, y1 + eps)

        x2 = x2.clamp(0.0, 1.0)
        y2 = y2.clamp(0.0, 1.0)
        x1 = torch.minimum(x1, x2 - eps)
        y1 = torch.minimum(y1, y2 - eps)

        return torch.stack([x1, y1, x2, y2], dim=1)

    def _predict_xyxy_rel(self, imgs):
        preds_cxcywh_rel = self.model(imgs)
        preds_xyxy_rel = box_convert(preds_cxcywh_rel, in_fmt="cxcywh", out_fmt="xyxy")
        return self._sanitize_xyxy_rel(preds_xyxy_rel)

    def _emit_training_log(self, message: str, log_callback: Optional[Callable[[str], None]] = None):
        print(message)
        if callable(log_callback):
            log_callback(str(message))

    def _next_versioned_save_path(self):
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate_path = os.path.join(self.save_dir, f"expert_v{timestamp}.pth")
        suffix = 2
        while os.path.exists(candidate_path):
            candidate_path = os.path.join(self.save_dir, f"expert_v{timestamp}_{suffix}.pth")
            suffix += 1
        return candidate_path

    def train(
        self,
        epochs=50,
        batch_size=8,
        target_size=None,
        log_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        stop_callback: Optional[Callable[[], bool]] = None,
    ):
        target_size = self._normalize_input_size(target_size or self.input_size)
        parent_suffix = f" within {self.parent_part}" if self.parent_part else ""
        self._emit_training_log(
            f"=== Starting Blink Training for {self.part_name} Expert{parent_suffix} ===",
            log_callback=log_callback,
        )
        self._emit_training_log(
            f"Blink params: epochs={epochs}, batch={batch_size}, lr={self.learning_rate:g}, "
            f"weight_decay={self.weight_decay:g}, input_size={target_size[0]}",
            log_callback=log_callback,
        )
        self._emit_training_log(
            f"Blink training strategy: {self.training_strategy} ({blink_training_strategy_label(self.training_strategy)})",
            log_callback=log_callback,
        )

        dataset = self._make_dataset(target_size)

        if len(dataset) == 0:
            self._emit_training_log(
                "Error: Not enough trajectory data. Please go to Blink Lab and run 'Auto-Shrink' on a few images first!",
                log_callback=log_callback,
            )
            return None

        best_loss = float('inf')
        save_path = self._next_versioned_save_path()
        self._emit_training_log(
            f"New Blink training will be saved as a candidate: {save_path}",
            log_callback=log_callback,
        )

        self.model.train()

        if callable(progress_callback):
            progress_callback(0)

        stages = self._training_stages(int(epochs))
        global_epoch = 0
        for stage in stages:
            stage_name = stage["name"]
            stage_epochs = int(stage["epochs"])
            stage_dataset = self._make_dataset(target_size, stage_view_mode=stage.get("view_mode"))
            dataloader = DataLoader(stage_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
            self._emit_training_log(
                f"--- Blink stage: {stage_name} | view_mode={stage.get('view_mode') or 'random'} | epochs={stage_epochs} ---",
                log_callback=log_callback,
            )
            for _stage_epoch in range(stage_epochs):
                global_epoch += 1
                if callable(stop_callback) and stop_callback():
                    self._emit_training_log(
                        "Training cancelled before starting the next epoch.",
                        log_callback=log_callback,
                    )
                    return None

                avg_loss, avg_final, avg_step, avg_view, avg_consistency, elapsed = self._run_epoch(
                    dataloader,
                    target_size,
                    stage_name,
                    stop_callback=stop_callback,
                    log_callback=log_callback,
                )
                if avg_loss is None:
                    return None
                self.scheduler.step(avg_loss)
                self.history["loss"].append(float(avg_loss))
                self.history["loss_final"].append(float(avg_final))
                self.history["loss_step"].append(float(avg_step))
                self.history["loss_view"].append(float(avg_view))
                self.history["loss_consistency"].append(float(avg_consistency))
                self.history["stage"].append(stage_name)

                self._emit_training_log(
                    f"Epoch [{global_epoch}/{epochs}] Stage={stage_name} Loss: {avg_loss:.4f} "
                    f"(final={avg_final:.4f}, step={avg_step:.4f}, view={avg_view:.4f}, cons={avg_consistency:.4f}) "
                    f"- {elapsed:.1f}s",
                    log_callback=log_callback,
                )
                if callable(progress_callback):
                    progress_callback(int((global_epoch / max(1, int(epochs))) * 100))

                # Save the best checkpoint within this training run; route appointment is handled separately.
                if avg_loss < best_loss:
                    best_loss = avg_loss
                    torch.save(
                        {
                            "state_dict": self.model.state_dict(),
                            "meta": self._build_checkpoint_meta(target_size, epochs, batch_size, best_loss),
                        },
                        save_path,
                    )
                    self._emit_training_log(
                        f"  -> Saved improved checkpoint candidate for {self.part_name}.",
                        log_callback=log_callback,
                    )

        if os.path.exists(save_path):
            saved_payload = torch.load(save_path, map_location=self.device)
            saved_state = saved_payload.get("state_dict", saved_payload) if isinstance(saved_payload, dict) else saved_payload
            self.model.load_state_dict(saved_state)
        manifest_path, manifest = self.write_manifest(save_path, target_size, dataset)
        self.last_report = self.generate_report(dataset, save_path, target_size=target_size, max_samples=24)
        self.last_report["manifest_path"] = manifest_path
        self.last_report["manifest"] = manifest
        self._emit_training_log(
            f"=== Training Complete! Expert saved to {save_path} ===",
            log_callback=log_callback,
        )
        return save_path

    def _make_dataset(self, target_size, stage_view_mode=None):
        return BlinkTrajectoryDataset(
            self.project_path,
            self.part_name,
            parent_part=self.parent_part,
            target_size=target_size,
            training_strategy=self.training_strategy,
            stage_view_mode=stage_view_mode,
            allowed_image_paths=self.allowed_image_paths,
        )

    def _training_stages(self, epochs):
        total = max(1, int(epochs))
        if self.training_strategy != BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE:
            return [{"name": self.training_strategy, "view_mode": None, "epochs": total}]
        full_epochs = max(1, total // 2)
        inside_epochs = max(1, total - full_epochs)
        if total == 1:
            return [{"name": "stage1_full", "view_mode": "full", "epochs": 1}]
        return [
            {"name": "stage1_full", "view_mode": "full", "epochs": full_epochs},
            {"name": "stage2_inside", "view_mode": "inside", "epochs": inside_epochs},
        ]

    def _run_epoch(self, dataloader, target_size, stage_name, stop_callback=None, log_callback=None):
        epoch_loss = 0.0
        epoch_loss_final = 0.0
        epoch_loss_step = 0.0
        epoch_loss_view = 0.0
        epoch_loss_consistency = 0.0
        start_time = time.time()

        for batch_data in dataloader:
            if callable(stop_callback) and stop_callback():
                self._emit_training_log(
                    "Training cancellation requested. Stopping after the current batch.",
                    log_callback=log_callback,
                )
                return None, None, None, None, None, None

            imgs_inside = None
            imgs_outside = None
            if isinstance(batch_data, dict):
                imgs = batch_data["image"].to(self.device)
                imgs_inside = batch_data.get("inside_image")
                imgs_outside = batch_data.get("outside_image")
                imgs_inside = imgs_inside.to(self.device) if imgs_inside is not None else None
                imgs_outside = imgs_outside.to(self.device) if imgs_outside is not None else None
                targets_step = self._sanitize_xyxy_rel(batch_data["target_step"].to(self.device).float())
                targets_final = self._sanitize_xyxy_rel(batch_data["target_final"].to(self.device).float())
                use_pairwise_losses = True
            else:
                imgs, targets = batch_data
                imgs = imgs.to(self.device)
                targets = targets.to(self.device).float()
                if targets.max().item() > 1.5:
                    norm = torch.tensor(
                        [target_size[0], target_size[1], target_size[0], target_size[1]],
                        dtype=targets.dtype,
                        device=self.device,
                    )
                    targets = targets / norm
                targets_final = self._sanitize_xyxy_rel(targets)
                targets_step = targets_final
                use_pairwise_losses = False

            self.optimizer.zero_grad()

            preds_main = self._predict_xyxy_rel(imgs)
            loss_final = generalized_box_iou_loss(preds_main, targets_final, reduction="mean")
            loss_step = F.smooth_l1_loss(preds_main, targets_step)

            loss_view = torch.tensor(0.0, device=self.device)
            loss_consistency = torch.tensor(0.0, device=self.device)
            if use_pairwise_losses and imgs_inside is not None:
                preds_inside = self._predict_xyxy_rel(imgs_inside)
                loss_inside = generalized_box_iou_loss(preds_inside, targets_final, reduction="mean")
                if self.training_strategy == BLINK_STRATEGY_TRIVIEW_RANDOM and imgs_outside is not None:
                    preds_outside = self._predict_xyxy_rel(imgs_outside)
                    loss_outside = generalized_box_iou_loss(preds_outside, targets_final, reduction="mean")
                    loss_view = 0.5 * (loss_inside + loss_outside)
                    loss_consistency = F.smooth_l1_loss(preds_inside, preds_outside)
                elif self.training_strategy == BLINK_STRATEGY_FULL_INSIDE_RANDOM:
                    loss_view = loss_inside
                elif self.training_strategy == BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE and stage_name == "stage2_inside":
                    loss_view = loss_inside

            loss = (
                loss_final
                + 0.35 * loss_step
                + 0.20 * loss_view
                + 0.10 * loss_consistency
            )

            loss.backward()
            self.optimizer.step()

            epoch_loss += loss.item()
            epoch_loss_final += loss_final.item()
            epoch_loss_step += loss_step.item()
            epoch_loss_view += loss_view.item()
            epoch_loss_consistency += loss_consistency.item()

        denom = max(1, len(dataloader))
        return (
            epoch_loss / denom,
            epoch_loss_final / denom,
            epoch_loss_step / denom,
            epoch_loss_view / denom,
            epoch_loss_consistency / denom,
            time.time() - start_time,
        )

    def _build_checkpoint_meta(self, target_size, epochs, batch_size, best_loss):
        training_strategy = sanitize_blink_training_strategy(
            getattr(self, "training_strategy", BLINK_STRATEGY_TRIVIEW_RANDOM)
        )
        return {
            "kind": "blink_expert_locator",
            "part_name": self.part_name,
            "parent_part": self.parent_part,
            "input_size": [int(target_size[0]), int(target_size[1])],
            "learning_rate": float(self.learning_rate),
            "weight_decay": float(self.weight_decay),
            "epochs": int(epochs),
            "batch_size": int(batch_size),
            "best_loss": float(best_loss),
            "training_strategy": training_strategy,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    def write_manifest(self, save_path, target_size, dataset):
        training_strategy = sanitize_blink_training_strategy(
            getattr(self, "training_strategy", BLINK_STRATEGY_TRIVIEW_RANDOM)
        )
        train_params = {
            "learning_rate": float(self.learning_rate),
            "weight_decay": float(self.weight_decay),
            "training_strategy": training_strategy,
        }
        training_scope = getattr(self, "training_scope", {})
        if training_scope:
            train_params["training_scope"] = dict(training_scope)
        manifest_path, manifest = write_blink_expert_manifest(
            save_path,
            expert_backend=BLINK_EXPERT_BACKEND_VIT_B,
            parent_part=self.parent_part,
            child_part=self.part_name,
            input_size=target_size,
            project_json=self.project_path,
            trajectory_count=len(dataset) if dataset is not None else 0,
            output_schema="vit_b_box_regression_v1",
            train_params=train_params,
        )
        return manifest_path, manifest

    def _experiment_dir(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(self.project_path)))
        if not base_dir or not os.path.isdir(base_dir):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        exp_dir = os.path.join(base_dir, "experiments", f"blink_{self.part_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(exp_dir, exist_ok=True)
        return exp_dir

    def _save_history_csv(self, exp_dir):
        csv_path = os.path.join(exp_dir, "training_log.csv")
        keys = list(self.history.keys())
        max_len = max([len(self.history.get(key, [])) for key in keys] or [0])
        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["epoch"] + keys)
            for idx in range(max_len):
                writer.writerow([idx + 1] + [
                    self.history.get(key, [""] * max_len)[idx] if idx < len(self.history.get(key, [])) else ""
                    for key in keys
                ])
        return csv_path

    def _plot_metrics(self, exp_dir):
        if not HAS_PLOT or plt is None:
            return None
        metrics_path = os.path.join(exp_dir, "metrics_plot.png")
        fig, axs = plt.subplots(2, 2, figsize=(12, 9))
        fig.suptitle(f"Blink Expert Training: {self.part_name}", fontsize=15)
        panels = [
            ("loss", "Total Loss", axs[0, 0]),
            ("loss_final", "Final Box Loss", axs[0, 1]),
            ("loss_step", "Step Loss", axs[1, 0]),
            ("loss_view", "Inside/Outside View Loss", axs[1, 1]),
        ]
        for key, title, ax in panels:
            values = self.history.get(key, [])
            if values:
                ax.plot(values, label=key)
            ax.set_title(title)
            ax.set_xlabel("Epoch")
            ax.set_ylabel("Loss")
            ax.grid(True, alpha=0.3)
            ax.legend()
        plt.tight_layout(rect=(0, 0.03, 1, 0.94))
        plt.savefig(metrics_path, dpi=150)
        plt.close(fig)
        return metrics_path

    def _tensor_to_uint8(self, image_tensor):
        arr = image_tensor.detach().cpu().permute(1, 2, 0).numpy()
        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
        return arr

    def _rel_xyxy_to_abs(self, box_rel, target_size):
        box = np.asarray(box_rel, dtype=np.float32)
        return [
            float(box[0] * target_size[0]),
            float(box[1] * target_size[1]),
            float(box[2] * target_size[0]),
            float(box[3] * target_size[1]),
        ]

    def _box_iou(self, box_a, box_b):
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
        inter = iw * ih
        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    def _draw_validation_detail(self, image_rgb, pred_box, target_box, title_lines=None):
        canvas = image_rgb.copy()
        pred = [int(round(v)) for v in pred_box]
        target = [int(round(v)) for v in target_box]
        cv2.rectangle(canvas, (target[0], target[1]), (target[2], target[3]), (40, 220, 80), 2)
        cv2.rectangle(canvas, (pred[0], pred[1]), (pred[2], pred[3]), (40, 210, 255), 2)
        for idx, text in enumerate(title_lines or []):
            y = 24 + idx * 22
            cv2.putText(canvas, str(text), (11, y + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(canvas, str(text), (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        return canvas

    def _plot_validation_samples(self, dataset, exp_dir, target_size, max_samples=24):
        details_dir = os.path.join(exp_dir, "val_details")
        os.makedirs(details_dir, exist_ok=True)
        rows = []
        preview_images = []
        sample_count = min(max_samples, len(dataset))
        self.model.eval()
        for idx in range(sample_count):
            sample = dataset[idx]
            image_tensor = sample["image"].to(self.device)
            target_rel = sample["target_final"].detach().cpu().numpy()
            with torch.no_grad():
                pred_rel = self._predict_xyxy_rel(image_tensor.unsqueeze(0))[0].detach().cpu().numpy()

            image_rgb = self._tensor_to_uint8(sample["image"])
            pred_box = self._rel_xyxy_to_abs(pred_rel, target_size)
            target_box = self._rel_xyxy_to_abs(target_rel, target_size)
            iou = self._box_iou(pred_box, target_box)
            pred_center = np.array([(pred_box[0] + pred_box[2]) / 2.0, (pred_box[1] + pred_box[3]) / 2.0])
            target_center = np.array([(target_box[0] + target_box[2]) / 2.0, (target_box[1] + target_box[3]) / 2.0])
            center_error = float(np.linalg.norm(pred_center - target_center))
            detail_name = f"blink_val_{idx:04d}.png"
            detail_path = os.path.join(details_dir, detail_name)
            detail_img = self._draw_validation_detail(
                image_rgb,
                pred_box,
                target_box,
                [
                    f"{self.part_name} | IoU {iou:.2f}",
                    f"center error {center_error:.1f}px",
                    "green=target cyan=prediction",
                ],
            )
            cv2.imwrite(detail_path, cv2.cvtColor(detail_img, cv2.COLOR_RGB2BGR))
            if len(preview_images) < 8:
                preview_images.append(detail_img)
            rows.append(
                {
                    "sample_id": f"blink_{idx:04d}",
                    "image_name": os.path.basename(detail_name),
                    "image_path": "",
                    "detail_image": detail_name,
                    "provenance": "blink_expert",
                    "valid_parts": self.part_name,
                    "predicted_parts": self.part_name,
                    "peak_summary": f"IoU {iou:.3f}",
                    "error_summary": f"center {center_error:.1f}px",
                    "max_error_px": f"{center_error:.3f}",
                }
            )

        summary_image = None
        if HAS_PLOT and plt is not None and preview_images:
            summary_image = os.path.join(exp_dir, "validation_samples.png")
            cols = 2
            rows_count = int(np.ceil(len(preview_images) / cols))
            fig, axs = plt.subplots(rows_count, cols, figsize=(10, max(4, rows_count * 4)))
            axs = np.asarray(axs).reshape(-1)
            for ax_idx, ax in enumerate(axs):
                ax.axis("off")
                if ax_idx < len(preview_images):
                    ax.imshow(preview_images[ax_idx])
                    ax.set_title(f"Sample {ax_idx}")
            plt.tight_layout()
            plt.savefig(summary_image, dpi=150)
            plt.close(fig)

        return summary_image, details_dir, rows

    def generate_report(self, dataset, save_path, target_size, max_samples=24):
        exp_dir = self._experiment_dir()
        csv_path = self._save_history_csv(exp_dir)
        metrics_path = self._plot_metrics(exp_dir)
        val_path, details_dir, validation_rows = self._plot_validation_samples(dataset, exp_dir, target_size, max_samples=max_samples)
        validation_index_path = os.path.join(exp_dir, "validation_index.csv")
        fieldnames = [
            "sample_id",
            "image_name",
            "image_path",
            "detail_image",
            "provenance",
            "valid_parts",
            "predicted_parts",
            "peak_summary",
            "error_summary",
            "max_error_px",
        ]
        with open(validation_index_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in validation_rows:
                writer.writerow({key: row.get(key, "") for key in fieldnames})
        summary = {
            "kind": "blink_expert_report",
            "part_name": self.part_name,
            "parent_part": self.parent_part,
            "model_path": save_path,
            "input_size": [int(target_size[0]), int(target_size[1])],
            "learning_rate": float(self.learning_rate),
            "weight_decay": float(self.weight_decay),
            "training_strategy": self.training_strategy,
            "training_scope": dict(self.training_scope),
            "trajectory_sequence_count": int(getattr(dataset, "sequence_count", len(getattr(dataset, "samples", []) or [])) or 0),
            "expanded_training_sample_count": int(len(dataset) if dataset is not None else 0),
            "validation_count": len(validation_rows),
            "validation_preview_count": min(8, len(validation_rows)),
            "validation_provenance_counts": {"blink_expert": len(validation_rows)},
        }
        summary_path = os.path.join(exp_dir, "report_summary.json")
        with open(summary_path, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, ensure_ascii=False)
        return {
            "dir": exp_dir,
            "csv": csv_path,
            "metrics": metrics_path,
            "val": val_path,
            "validation_index": validation_index_path,
            "report_summary": summary_path,
            "validation_rows": validation_rows,
            "validation_summary": summary,
            "details_dir": details_dir,
            "model_path": save_path,
        }
