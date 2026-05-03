# pyright: reportMissingImports=false

import os
import time
from typing import Callable, Optional

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import DataLoader
try:
    from AntSleap.models.expert_networks import MicroExpertLocator
except ImportError:
    from models.expert_networks import MicroExpertLocator
from .blink_dataset import BlinkTrajectoryDataset
from .taxonomy_defaults import is_safe_part_name
from torchvision.ops import generalized_box_iou_loss, box_convert

class BlinkExpertTrainer:
    """
    BLINK 微观专家模型训练器
    
    采用 Generalized IoU (GIoU) Loss 来惩罚预测框和黄金掩码框之间的偏差。
    通过学习你在 Blink Lab 里留下的那几百条“收缩轨迹”，它能学会一步到位的极限预测。
    """
    def __init__(self, project_path, part_name, parent_part=None, device='cuda', save_dir=None, protect_active=False):
        self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        self.part_name = str(part_name).strip()
        if not is_safe_part_name(self.part_name):
            raise ValueError(f"Unsafe Blink expert part name: {self.part_name}")
        self.parent_part = str(parent_part).strip() if isinstance(parent_part, str) and parent_part.strip() else None
        self.project_path = project_path
        self.protect_active = bool(protect_active)

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
        self.model = MicroExpertLocator(pretrained=True).to(self.device)
        self.optimizer = optim.AdamW(self.model.parameters(), lr=1e-3, weight_decay=1e-4)
        
        # 动态学习率调度器
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(self.optimizer, mode='min', factor=0.5, patience=5)

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

    def train(self, epochs=50, batch_size=8, target_size=(224, 224), log_callback: Optional[Callable[[str], None]] = None):
        parent_suffix = f" within {self.parent_part}" if self.parent_part else ""
        self._emit_training_log(
            f"=== Starting Blink Training for {self.part_name} Expert{parent_suffix} ===",
            log_callback=log_callback,
        )
        
        # 加载刚才写的数据集生成器 (它会自动执行 Inside/Outside 的盲盒遮罩)
        dataset = BlinkTrajectoryDataset(
            self.project_path,
            self.part_name,
            parent_part=self.parent_part,
            target_size=target_size,
        )
        
        if len(dataset) == 0:
            self._emit_training_log(
                "Error: Not enough trajectory data. Please go to Blink Lab and run 'Auto-Shrink' on a few images first!",
                log_callback=log_callback,
            )
            return None
            
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0)
        
        best_loss = float('inf')
        active_path = os.path.join(self.save_dir, "best_expert.pth")
        save_path = active_path
        
        # 版本保护：在开始新的训练前，如果发现已经存在旧的 best_expert，
        # 则将其重命名为一个带有时间戳的归档文件，防止被直接覆盖。
        if self.protect_active and os.path.exists(active_path):
            save_path = self._next_versioned_save_path()
            self._emit_training_log(
                f"Active expert is protected by an appointed route. New training will be saved as: {save_path}",
                log_callback=log_callback,
            )
        elif os.path.exists(active_path):
            import shutil
            archive_path = self._next_versioned_save_path()
            shutil.copy2(active_path, archive_path)
            self._emit_training_log(
                f"Archived previous expert model to: {archive_path}",
                log_callback=log_callback,
            )
        
        self.model.train()
        
        for epoch in range(epochs):
            epoch_loss = 0.0
            epoch_loss_final = 0.0
            epoch_loss_step = 0.0
            epoch_loss_view = 0.0
            epoch_loss_consistency = 0.0
            start_time = time.time()
            
            for batch_data in dataloader:
                imgs_inside = None
                imgs_outside = None
                if isinstance(batch_data, dict):
                    imgs = batch_data["image"].to(self.device)
                    imgs_inside = batch_data["inside_image"].to(self.device)
                    imgs_outside = batch_data["outside_image"].to(self.device)
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

                if use_pairwise_losses and imgs_inside is not None and imgs_outside is not None:
                    preds_inside = self._predict_xyxy_rel(imgs_inside)
                    preds_outside = self._predict_xyxy_rel(imgs_outside)

                    loss_inside = generalized_box_iou_loss(preds_inside, targets_final, reduction="mean")
                    loss_outside = generalized_box_iou_loss(preds_outside, targets_final, reduction="mean")
                    loss_view = 0.5 * (loss_inside + loss_outside)
                    loss_consistency = F.smooth_l1_loss(preds_inside, preds_outside)
                else:
                    loss_view = torch.tensor(0.0, device=self.device)
                    loss_consistency = torch.tensor(0.0, device=self.device)

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
                
            avg_loss = epoch_loss / len(dataloader)
            avg_final = epoch_loss_final / len(dataloader)
            avg_step = epoch_loss_step / len(dataloader)
            avg_view = epoch_loss_view / len(dataloader)
            avg_consistency = epoch_loss_consistency / len(dataloader)
            self.scheduler.step(avg_loss)
            
            elapsed = time.time() - start_time
            self._emit_training_log(
                f"Epoch [{epoch+1}/{epochs}] Loss: {avg_loss:.4f} "
                f"(final={avg_final:.4f}, step={avg_step:.4f}, view={avg_view:.4f}, cons={avg_consistency:.4f}) "
                f"- {elapsed:.1f}s",
                log_callback=log_callback,
            )
            
            # 保存表现最好的专家
            if avg_loss < best_loss:
                best_loss = avg_loss
                torch.save(self.model.state_dict(), save_path)
                self._emit_training_log(
                    f"  -> Saved new best expert model for {self.part_name}.",
                    log_callback=log_callback,
                )
                
        self._emit_training_log(
            f"=== Training Complete! Expert saved to {save_path} ===",
            log_callback=log_callback,
        )
        return save_path
