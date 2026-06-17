import csv
import json
import os
import time
from datetime import datetime
from typing import Callable, Optional

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader

try:
    import matplotlib.pyplot as plt
    HAS_PLOT = True
except Exception:
    plt = None
    HAS_PLOT = False

from .blink_expert_manifest import BLINK_EXPERT_BACKEND_HEATMAP, write_blink_expert_manifest
from .blink_heatmap_dataset import BlinkHeatmapDataset
from .blink_training_strategy import (
    BLINK_STRATEGY_FULL_INSIDE_RANDOM,
    BLINK_STRATEGY_TRIVIEW_RANDOM,
    BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
    blink_training_strategy_label,
    sanitize_blink_training_strategy,
)
from .projection import CoordinateMapper
from .runtime_device import resolve_torch_device
from .taxonomy_defaults import is_safe_part_name


HEATMAP_BLINK_OUTPUT_SCHEMA = "heatmap_wh_box_v1"


def normalize_heatmap_input_size(value, fallback=512):
    if isinstance(value, (list, tuple)) and value:
        value = value[0]
    try:
        side = int(value)
    except Exception:
        side = int(fallback)
    side = max(64, side)
    return (side, side)


class HeatmapBlinkNet(nn.Module):
    def __init__(self, in_channels=3, base_channels=24):
        super().__init__()
        channels = int(base_channels or 24)
        self.base_channels = channels
        self.encoder = nn.Sequential(
            nn.Conv2d(in_channels, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels * 2, 3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(channels * 2),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels * 2, channels * 4, 3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(channels * 4),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels * 4, channels * 4, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels * 4),
            nn.ReLU(inplace=True),
        )
        self.heatmap_head = nn.Sequential(
            nn.Conv2d(channels * 4, channels * 2, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels * 2, 1, 1),
        )
        self.wh_head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(channels * 4, channels * 2),
            nn.ReLU(inplace=True),
            nn.Linear(channels * 2, 2),
            nn.Sigmoid(),
        )

    def forward(self, x):
        features = self.encoder(x)
        heatmap_logits = self.heatmap_head(features)
        heatmap_logits = F.interpolate(
            heatmap_logits,
            size=x.shape[-2:],
            mode="bilinear",
            align_corners=False,
        )
        wh = self.wh_head(features).view(-1, 1, 2)
        return heatmap_logits, wh


class BlinkHeatmapTrainer:
    def __init__(
        self,
        project_path,
        part_name,
        parent_part=None,
        device="auto",
        save_dir=None,
        learning_rate=1e-3,
        weight_decay=1e-4,
        input_size=512,
        heatmap_sigma=2.0,
        wh_loss_weight=1.0,
        center_loss_weight=1.0,
        training_strategy=BLINK_STRATEGY_TRIVIEW_RANDOM,
        allowed_image_paths=None,
        training_scope=None,
    ):
        self.device = resolve_torch_device(device)
        self.part_name = str(part_name or "").strip()
        if not is_safe_part_name(self.part_name):
            raise ValueError(f"Unsafe heatmap Blink expert part name: {self.part_name}")
        self.parent_part = str(parent_part).strip() if isinstance(parent_part, str) and parent_part.strip() else None
        self.project_path = project_path
        self.learning_rate = float(learning_rate)
        self.weight_decay = float(weight_decay)
        self.input_size = normalize_heatmap_input_size(input_size)
        self.heatmap_sigma = max(0.1, float(heatmap_sigma or 2.0))
        self.wh_loss_weight = max(0.0, float(wh_loss_weight))
        self.center_loss_weight = max(0.0, float(center_loss_weight))
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
            raise ValueError(f"Unsafe heatmap Blink expert save path for part: {self.part_name}")

        self.save_dir = target_dir
        os.makedirs(self.save_dir, exist_ok=True)

        self.model = HeatmapBlinkNet().to(self.device)
        self.optimizer = optim.AdamW(self.model.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(self.optimizer, mode="min", factor=0.5, patience=5)

    def _emit_training_log(self, message: str, log_callback: Optional[Callable[[str], None]] = None):
        print(message)
        if callable(log_callback):
            log_callback(str(message))

    def _next_versioned_save_path(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate_path = os.path.join(self.save_dir, f"heatmap_expert_v{timestamp}.pth")
        suffix = 2
        while os.path.exists(candidate_path):
            candidate_path = os.path.join(self.save_dir, f"heatmap_expert_v{timestamp}_{suffix}.pth")
            suffix += 1
        return candidate_path

    def train(
        self,
        epochs=50,
        batch_size=4,
        target_size=None,
        log_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        stop_callback: Optional[Callable[[], bool]] = None,
    ):
        target_size = normalize_heatmap_input_size(target_size or self.input_size)
        parent_suffix = f" within {self.parent_part}" if self.parent_part else ""
        self._emit_training_log(
            f"=== Starting Heatmap Blink Training for {self.part_name} Expert{parent_suffix} ===",
            log_callback=log_callback,
        )
        self._emit_training_log(
            f"Heatmap Blink params: epochs={epochs}, batch={batch_size}, lr={self.learning_rate:g}, "
            f"weight_decay={self.weight_decay:g}, input_size={target_size[0]}, sigma={self.heatmap_sigma:g}",
            log_callback=log_callback,
        )
        self._emit_training_log(
            f"Heatmap Blink training strategy: {self.training_strategy} ({blink_training_strategy_label(self.training_strategy)})",
            log_callback=log_callback,
        )

        dataset = self._make_dataset(target_size)
        if len(dataset) == 0:
            self._emit_training_log(
                "Error: Not enough parent ROI trajectory data for heatmap Blink training.",
                log_callback=log_callback,
            )
            return None

        best_loss = float("inf")
        save_path = self._next_versioned_save_path()
        self._emit_training_log(
            f"New heatmap Blink training will be saved as a candidate: {save_path}",
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
            dataloader = DataLoader(stage_dataset, batch_size=int(batch_size), shuffle=True, num_workers=0)
            self._emit_training_log(
                f"--- Heatmap Blink stage: {stage_name} | view_mode={stage.get('view_mode') or 'random'} | epochs={stage_epochs} ---",
                log_callback=log_callback,
            )
            for _stage_epoch in range(stage_epochs):
                global_epoch += 1
                if callable(stop_callback) and stop_callback():
                    self._emit_training_log("Training cancelled before starting the next epoch.", log_callback=log_callback)
                    return None

                avg_loss, avg_final, avg_step, avg_view, avg_consistency, elapsed = self._run_epoch(
                    dataloader,
                    stage_name,
                    stop_callback=stop_callback,
                    log_callback=log_callback,
                )
                if avg_loss is None:
                    return None
                self.scheduler.step(avg_loss)
                self.history["loss"].append(avg_loss)
                self.history["loss_final"].append(avg_final)
                self.history["loss_step"].append(avg_step)
                self.history["loss_view"].append(avg_view)
                self.history["loss_consistency"].append(avg_consistency)
                self.history["stage"].append(stage_name)
                self._emit_training_log(
                    f"Epoch [{global_epoch}/{epochs}] Stage={stage_name} Loss: {avg_loss:.4f} "
                    f"(final={avg_final:.4f}, step={avg_step:.4f}, view={avg_view:.4f}, consistency={avg_consistency:.4f}) - {elapsed:.1f}s",
                    log_callback=log_callback,
                )
                if callable(progress_callback):
                    progress_callback(int((global_epoch / max(1, int(epochs))) * 100))

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
                        f"  -> Saved improved heatmap checkpoint candidate for {self.part_name}.",
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
            f"=== Heatmap Blink Training Complete! Expert saved to {save_path} ===",
            log_callback=log_callback,
        )
        return save_path

    def _make_dataset(self, target_size, stage_view_mode=None):
        return BlinkHeatmapDataset(
            self.project_path,
            self.part_name,
            parent_part=self.parent_part,
            input_size=target_size[0],
            heatmap_sigma=self.heatmap_sigma,
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

    def _run_epoch(self, dataloader, stage_name, stop_callback=None, log_callback=None):
        epoch_loss = 0.0
        epoch_final = 0.0
        epoch_step = 0.0
        epoch_view = 0.0
        epoch_consistency = 0.0
        start_time = time.time()

        for batch_data in dataloader:
            if callable(stop_callback) and stop_callback():
                self._emit_training_log("Training cancellation requested. Stopping after the current batch.", log_callback=log_callback)
                return None, None, None, None, None, None

            imgs = batch_data["image"].to(self.device)
            heatmap_target = batch_data["heatmap"].to(self.device)
            wh_target = batch_data["wh"].to(self.device).float().view(-1, 1, 2)
            step_heatmap_target = batch_data.get("step_heatmap", batch_data["heatmap"]).to(self.device)
            step_wh_target = batch_data.get("step_wh", batch_data["wh"]).to(self.device).float().view(-1, 1, 2)

            self.optimizer.zero_grad()
            heatmap_logits, wh_pred = self.model(imgs)
            heatmap_pred = torch.sigmoid(heatmap_logits)
            final_center_loss = F.mse_loss(heatmap_pred, heatmap_target)
            final_wh_loss = F.smooth_l1_loss(wh_pred, wh_target)
            step_center_loss = F.mse_loss(heatmap_pred, step_heatmap_target)
            step_wh_loss = F.smooth_l1_loss(wh_pred, step_wh_target)

            view_loss = torch.tensor(0.0, device=self.device)
            consistency_loss = torch.tensor(0.0, device=self.device)
            if "inside_image" in batch_data:
                inside_imgs = batch_data["inside_image"].to(self.device)
                inside_logits, inside_wh = self.model(inside_imgs)
                inside_heatmap = torch.sigmoid(inside_logits)
                inside_center_loss = F.mse_loss(inside_heatmap, heatmap_target)
                inside_wh_loss = F.smooth_l1_loss(inside_wh, wh_target)
                inside_loss = self.center_loss_weight * inside_center_loss + self.wh_loss_weight * inside_wh_loss
                if self.training_strategy == BLINK_STRATEGY_TRIVIEW_RANDOM and "outside_image" in batch_data:
                    outside_imgs = batch_data["outside_image"].to(self.device)
                    outside_logits, outside_wh = self.model(outside_imgs)
                    outside_heatmap = torch.sigmoid(outside_logits)
                    outside_center_loss = F.mse_loss(outside_heatmap, heatmap_target)
                    outside_wh_loss = F.smooth_l1_loss(outside_wh, wh_target)
                    outside_loss = self.center_loss_weight * outside_center_loss + self.wh_loss_weight * outside_wh_loss
                    view_loss = 0.5 * (inside_loss + outside_loss)
                    consistency_loss = F.smooth_l1_loss(inside_heatmap, outside_heatmap) + F.smooth_l1_loss(inside_wh, outside_wh)
                elif self.training_strategy == BLINK_STRATEGY_FULL_INSIDE_RANDOM:
                    view_loss = inside_loss
                elif self.training_strategy == BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE and stage_name == "stage2_inside":
                    view_loss = inside_loss

            final_loss = self.center_loss_weight * final_center_loss + self.wh_loss_weight * final_wh_loss
            step_loss = self.center_loss_weight * step_center_loss + self.wh_loss_weight * step_wh_loss
            loss = final_loss + 0.35 * step_loss + 0.20 * view_loss + 0.10 * consistency_loss
            loss.backward()
            self.optimizer.step()

            epoch_loss += float(loss.item())
            epoch_final += float(final_loss.item())
            epoch_step += float(step_loss.item())
            epoch_view += float(view_loss.item())
            epoch_consistency += float(consistency_loss.item())

        denom = max(1, len(dataloader))
        return (
            epoch_loss / denom,
            epoch_final / denom,
            epoch_step / denom,
            epoch_view / denom,
            epoch_consistency / denom,
            time.time() - start_time,
        )

    def _build_checkpoint_meta(self, target_size, epochs, batch_size, best_loss):
        return {
            "kind": "blink_heatmap_expert",
            "part_name": self.part_name,
            "parent_part": self.parent_part,
            "input_size": [int(target_size[0]), int(target_size[1])],
            "base_channels": int(getattr(self.model, "base_channels", 24) or 24),
            "heatmap_sigma": float(self.heatmap_sigma),
            "learning_rate": float(self.learning_rate),
            "weight_decay": float(self.weight_decay),
            "wh_loss_weight": float(self.wh_loss_weight),
            "center_loss_weight": float(self.center_loss_weight),
            "epochs": int(epochs),
            "batch_size": int(batch_size),
            "best_loss": float(best_loss),
            "training_strategy": self.training_strategy,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    def write_manifest(self, save_path, target_size, dataset):
        train_params = {
            "learning_rate": float(self.learning_rate),
            "weight_decay": float(self.weight_decay),
            "heatmap_sigma": float(self.heatmap_sigma),
            "wh_loss_weight": float(self.wh_loss_weight),
            "center_loss_weight": float(self.center_loss_weight),
            "training_strategy": self.training_strategy,
        }
        if self.training_scope:
            train_params["training_scope"] = dict(self.training_scope)
        manifest_path, manifest = write_blink_expert_manifest(
            save_path,
            expert_backend=BLINK_EXPERT_BACKEND_HEATMAP,
            parent_part=self.parent_part,
            child_part=self.part_name,
            input_size=target_size,
            project_json=self.project_path,
            trajectory_count=int(getattr(dataset, "sequence_count", len(dataset) if dataset is not None else 0) or 0),
            output_schema=HEATMAP_BLINK_OUTPUT_SCHEMA,
            train_params=train_params,
        )
        return manifest_path, manifest

    def _experiment_dir(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(self.project_path)))
        if not base_dir or not os.path.isdir(base_dir):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        exp_dir = os.path.join(base_dir, "experiments", f"heatmap_blink_{self.part_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
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
        fig, ax = plt.subplots(figsize=(10, 6))
        for key, values in self.history.items():
            if key == "stage":
                continue
            if values:
                ax.plot(values, label=key)
        ax.set_title(f"Heatmap Blink Expert Training: {self.part_name}")
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Loss")
        ax.grid(True, alpha=0.3)
        ax.legend()
        plt.tight_layout()
        plt.savefig(metrics_path, dpi=150)
        plt.close(fig)
        return metrics_path

    def _tensor_to_uint8(self, image_tensor):
        arr = image_tensor.detach().cpu().permute(1, 2, 0).numpy()
        return np.clip(arr * 255.0, 0, 255).astype(np.uint8)

    def _predict_local_box(self, image_tensor, target_size):
        self.model.eval()
        with torch.no_grad():
            heatmap_logits, wh_pred = self.model(image_tensor.unsqueeze(0).to(self.device))
            heatmap = torch.sigmoid(heatmap_logits)[0, 0].detach().cpu().numpy()
            wh = wh_pred[0, 0].detach().cpu().numpy()
        flat_idx = int(np.argmax(heatmap))
        peak_y, peak_x = np.unravel_index(flat_idx, heatmap.shape)
        box_w = max(1.0, float(wh[0]) * float(target_size[0]))
        box_h = max(1.0, float(wh[1]) * float(target_size[1]))
        local_box = [
            float(peak_x) - box_w * 0.5,
            float(peak_y) - box_h * 0.5,
            float(peak_x) + box_w * 0.5,
            float(peak_y) + box_h * 0.5,
        ]
        return CoordinateMapper.clamp_bbox_to_size(local_box, target_size[0], target_size[1]), float(heatmap[peak_y, peak_x])

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

    def _draw_validation_detail(self, image_rgb, pred_box, target_box, score):
        canvas = image_rgb.copy()
        pred = [int(round(v)) for v in pred_box]
        target = [int(round(v)) for v in target_box]
        cv2.rectangle(canvas, (target[0], target[1]), (target[2], target[3]), (40, 220, 80), 2)
        cv2.rectangle(canvas, (pred[0], pred[1]), (pred[2], pred[3]), (40, 210, 255), 2)
        cv2.putText(canvas, f"{self.part_name} | score {score:.2f}", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(canvas, f"{self.part_name} | score {score:.2f}", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        return canvas

    def _plot_validation_samples(self, dataset, exp_dir, target_size, max_samples=24):
        details_dir = os.path.join(exp_dir, "val_details")
        os.makedirs(details_dir, exist_ok=True)
        rows = []
        preview_images = []
        sample_count = min(max_samples, len(dataset))
        for idx in range(sample_count):
            sample = dataset[idx]
            image_rgb = self._tensor_to_uint8(sample["image"])
            target_box = [float(v) for v in sample["local_box"].detach().cpu().numpy().tolist()]
            pred_box, score = self._predict_local_box(sample["image"], target_size)
            iou = self._box_iou(pred_box, target_box)
            detail_name = f"heatmap_blink_val_{idx:04d}.png"
            detail_path = os.path.join(details_dir, detail_name)
            detail_img = self._draw_validation_detail(image_rgb, pred_box, target_box, score)
            cv2.imwrite(detail_path, cv2.cvtColor(detail_img, cv2.COLOR_RGB2BGR))
            if len(preview_images) < 8:
                preview_images.append(detail_img)
            rows.append(
                {
                    "sample_id": f"heatmap_blink_{idx:04d}",
                    "image_name": os.path.basename(detail_name),
                    "image_path": "",
                    "detail_image": detail_name,
                    "provenance": "heatmap_blink_expert",
                    "valid_parts": self.part_name,
                    "predicted_parts": self.part_name,
                    "peak_summary": f"score {score:.3f}",
                    "error_summary": f"IoU {iou:.3f}",
                    "max_error_px": "",
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
            "kind": "heatmap_blink_expert_report",
            "part_name": self.part_name,
            "parent_part": self.parent_part,
            "model_path": save_path,
            "input_size": [int(target_size[0]), int(target_size[1])],
            "heatmap_sigma": float(self.heatmap_sigma),
            "learning_rate": float(self.learning_rate),
            "weight_decay": float(self.weight_decay),
            "training_strategy": self.training_strategy,
            "training_scope": dict(self.training_scope),
            "trajectory_sequence_count": int(getattr(dataset, "sequence_count", 0) or 0),
            "expanded_training_sample_count": int(len(dataset) if dataset is not None else 0),
            "validation_count": len(validation_rows),
            "validation_preview_count": min(8, len(validation_rows)),
            "validation_provenance_counts": {"heatmap_blink_expert": len(validation_rows)},
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
