import os
import csv
import json
import numpy as np
import torch
import cv2
from datetime import datetime

plt = None
pd = None

# Try imports
try:
    import matplotlib.pyplot as plt
    has_plot = True
except ImportError:
    has_plot = False

try:
    import pandas as pd
    has_pandas = True
except ImportError:
    has_pandas = False

class ExperimentReporter:
    def __init__(self, base_dir):
        """
        base_dir: Project root or weights dir
        """
        self.exp_dir = os.path.join(base_dir, "experiments", f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        if not os.path.exists(self.exp_dir):
            os.makedirs(self.exp_dir)
            
    def get_experiment_dir(self):
        return self.exp_dir

    def save_validation_index(self, validation_rows):
        csv_path = os.path.join(self.exp_dir, "validation_index.csv")
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
        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in validation_rows or []:
                writer.writerow({key: row.get(key, "") for key in fieldnames})
        return csv_path

    def save_report_summary(self, summary_payload):
        summary_path = os.path.join(self.exp_dir, "report_summary.json")
        with open(summary_path, "w", encoding="utf-8") as handle:
            json.dump(summary_payload, handle, indent=2, ensure_ascii=False)
        return summary_path

    def save_csv(self, history):
        csv_path = os.path.join(self.exp_dir, "training_log.csv")
        
        # Determine max length
        max_len = 0
        keys = list(history.keys())
        for k in keys:
            max_len = max(max_len, len(history[k]))
            
        # Pad lists
        data = {}
        for k in keys:
            vals = history[k]
            if len(vals) < max_len:
                vals += [""] * (max_len - len(vals))
            data[k] = vals
            
        if has_pandas and pd is not None:
            df = pd.DataFrame(data)
            df.to_csv(csv_path, index_label="epoch")
        else:
            with open(csv_path, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(["epoch"] + keys)
                for i in range(max_len):
                    row = [i+1] + [data[k][i] for k in keys]
                    w.writerow(row)
        return csv_path

    def plot_metrics(self, history):
        if not has_plot or plt is None:
            return None
        
        img_path = os.path.join(self.exp_dir, "metrics_plot.png")
        
        # Setup Figure: 2x2 Grid
        fig, axs = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle('Training Dynamics', fontsize=16)
        
        # 1. Locator Loss
        ax = axs[0, 0]
        if 'locator_train' in history: ax.plot(history['locator_train'], label='Train Loss', color='blue')
        if 'locator_val' in history: ax.plot(history['locator_val'], label='Val Loss', color='orange', linestyle='--')
        ax.set_title('Locator Loss (Heatmap + WH)')
        ax.set_xlabel('Epochs')
        ax.set_ylabel('Loss')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # 2. Locator Error
        ax = axs[0, 1]
        if 'pixel_error' in history: 
            ax.plot(history['pixel_error'], label='Val Pixel Error', color='red')
            ax.set_ylabel('Error (px)')
        ax.set_title('Locator Precision')
        ax.set_xlabel('Epochs')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # 3. SAM Loss
        ax = axs[1, 0]
        if 'parts_train' in history: ax.plot(history['parts_train'], label='Train Loss', color='blue')
        if 'parts_val' in history: ax.plot(history['parts_val'], label='Val Loss', color='orange', linestyle='--')
        ax.set_title('SAM Segmentation Loss (Dice)')
        ax.set_xlabel('Epochs')
        ax.set_ylabel('Loss')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # 4. SAM IoU
        ax = axs[1, 1]
        if 'iou' in history: 
            ax.plot(history['iou'], label='Val IoU', color='green')
            ax.set_ylabel('IoU')
        ax.set_title('SAM Segmentation Quality (IoU)')
        ax.set_xlabel('Epochs')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout(rect=(0, 0.03, 1, 0.95))
        plt.savefig(img_path, dpi=150)
        plt.close(fig)
        return img_path

    def _draw_overlay_lines(self, image_rgb, lines, start=(14, 24), line_gap=22):
        canvas = image_rgb.copy()
        x0, y0 = start
        for idx, text in enumerate(lines or []):
            if not text:
                continue
            y = y0 + idx * line_gap
            cv2.putText(canvas, str(text), (x0 + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(canvas, str(text), (x0, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        return canvas

    def plot_validation_samples(self, engine, val_loader, num_samples=6):
        """
        Runs inference on validation set.
        1. Saves ALL validation results to 'val_details' folder.
        2. Plots a grid of 'num_samples' for the report.
        """
        if not has_plot or plt is None:
            return {
                "summary_image": None,
                "details_dir": None,
                "rows": [],
                "summary": {"validation_count": 0, "provenance_counts": {}, "preview_count": 0},
            }
        if not val_loader:
            return {
                "summary_image": None,
                "details_dir": None,
                "rows": [],
                "summary": {"validation_count": 0, "provenance_counts": {}, "preview_count": 0},
            }
        
        # Directory for all validation details
        details_dir = os.path.join(self.exp_dir, "val_details")
        if not os.path.exists(details_dir):
            os.makedirs(details_dir)
            
        img_path = os.path.join(self.exp_dir, "validation_samples.png")
        
        engine.locator.eval()
        device = engine.device
        locator_size = getattr(engine, "locator_resolution", (512, 512)) or (512, 512)
        try:
            locator_width = max(1, int(locator_size[0]))
            locator_height = max(1, int(locator_size[1]))
        except Exception:
            locator_width, locator_height = 512, 512
        
        images_to_plot = [] # (img_np) for the grid
        global_idx = 0
        validation_rows = []
        provenance_counts = {}
        dataset = getattr(val_loader, "dataset", None)
        ordered_parts = list(getattr(dataset, "taxonomy", []) or [])
        dataset_rows = list(getattr(dataset, "data", []) or [])
        
        with torch.no_grad():
            for batch_idx, batch_data in enumerate(val_loader):
                # Locator Mode: [img, hm_target, wh_target, valid_parts_mask]
                imgs = batch_data[0]
                valid_parts_mask = batch_data[3] if isinstance(batch_data, (list, tuple)) and len(batch_data) > 3 else None
                imgs = imgs.to(device)
                if valid_parts_mask is not None:
                    valid_parts_mask = valid_parts_mask.to(device)
                
                # Predict
                hm_pred, wh_pred = engine.locator(imgs)
                
                # Process each image in batch
                for i in range(imgs.shape[0]):
                    # Convert Image to Numpy (CHW -> HWC)
                    img_np = imgs[i].cpu().permute(1, 2, 0).numpy()
                    img_np = (img_np * 255).astype(np.uint8).copy()
                    
                    # Get Heatmap (Show max activation across all parts for visualization)
                    if valid_parts_mask is not None:
                        valid_indices = torch.nonzero(valid_parts_mask[i] > 0.5, as_tuple=False).flatten()
                    else:
                        valid_indices = None

                    if valid_indices is not None and valid_indices.numel() > 0:
                        hm_max = torch.max(hm_pred[i, valid_indices], dim=0).values
                    elif valid_indices is not None:
                        hm_max = torch.zeros_like(hm_pred[i, 0])
                    else:
                        hm_max = torch.max(hm_pred[i], dim=0).values # [H, W]
                    hm = hm_max.cpu().numpy()
                    
                    hm_norm = (hm - hm.min()) / (hm.max() - hm.min() + 1e-6)
                    hm_color = cv2.applyColorMap((hm_norm * 255).astype(np.uint8), cv2.COLORMAP_JET)
                    
                    # Overlay
                    hm_rgb = cv2.cvtColor(hm_color, cv2.COLOR_BGR2RGB)
                    overlay = cv2.addWeighted(img_np, 0.6, hm_rgb, 0.4, 0)
                    
                    # Draw All Predicted Boxes
                    num_parts = hm_pred.shape[1]
                    part_peak_bits = []
                    part_error_bits = []
                    valid_part_names = []
                    predicted_part_names = []
                    max_error_px = None
                    for part_idx in range(num_parts):
                        if valid_parts_mask is not None and float(valid_parts_mask[i, part_idx].item()) <= 0.0:
                            continue
                        part_name = ordered_parts[part_idx] if part_idx < len(ordered_parts) else f"part_{part_idx}"
                        valid_part_names.append(part_name)
                        hm_part = hm_pred[i, part_idx].cpu().numpy()
                        peak_value = float(hm_part.max())
                        if peak_value >= 0.1:
                            predicted_part_names.append(part_name)
                        part_peak_bits.append(f"{part_name}={peak_value:.2f}")
                        if hm_part.max() < 0.1:
                            continue # Skip weak predictions
                        
                        y, x = np.unravel_index(hm_part.argmax(), hm_part.shape)
                        wh = wh_pred[i, part_idx].cpu().numpy()
                        w_px, h_px = wh[0] * locator_width, wh[1] * locator_height
                        
                        x1, y1 = int(x - w_px/2), int(y - h_px/2)
                        x2, y2 = int(x + w_px/2), int(y + h_px/2)
                        
                        # Draw Box (Cycle colors?)
                        color = (255, 0, 0) if part_idx == 0 else (0, 255, 0)
                        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(overlay, part_name, (max(0, x1), max(18, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

                        hm_target_batch = batch_data[1] if isinstance(batch_data, (list, tuple)) and len(batch_data) > 1 else None
                        if hm_target_batch is None:
                            continue
                        hm_true = hm_target_batch[i][part_idx].cpu().numpy()
                        yt, xt = np.unravel_index(hm_true.argmax(), hm_true.shape)
                        pixel_error = float(np.sqrt((x - xt) ** 2 + (y - yt) ** 2))
                        part_error_bits.append(f"{part_name}={pixel_error:.1f}px")
                        max_error_px = pixel_error if max_error_px is None else max(max_error_px, pixel_error)

                    provenance = "macro_locator"
                    provenance_counts[provenance] = provenance_counts.get(provenance, 0) + 1
                    sample_entry = dataset_rows[global_idx] if global_idx < len(dataset_rows) else None
                    sample_path = sample_entry[0] if isinstance(sample_entry, (list, tuple)) and len(sample_entry) > 0 else ""
                    image_name = os.path.basename(sample_path) if sample_path else f"sample_{global_idx:04d}"
                    peak_summary = ", ".join(part_peak_bits) if part_peak_bits else "none"
                    error_summary = ", ".join(part_error_bits) if part_error_bits else "none"
                    overlay = self._draw_overlay_lines(
                        overlay,
                        [
                            f"ID: {global_idx:04d} | {image_name}",
                            "Source: macro_locator validation",
                            f"Valid: {', '.join(valid_part_names) if valid_part_names else 'none'}",
                            f"Peaks: {peak_summary}",
                            f"Err(px): {error_summary}",
                        ],
                    )
                    
                    # Save to details folder
                    save_name = os.path.join(details_dir, f"val_{global_idx:04d}.jpg")
                    # Convert RGB to BGR for OpenCV saving
                    cv2.imwrite(save_name, cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
                    validation_rows.append(
                        {
                            "sample_id": f"val_{global_idx:04d}",
                            "image_name": image_name,
                            "image_path": str(sample_path or ""),
                            "detail_image": os.path.basename(save_name),
                            "provenance": provenance,
                            "valid_parts": ", ".join(valid_part_names),
                            "predicted_parts": ", ".join(predicted_part_names),
                            "peak_summary": peak_summary,
                            "error_summary": error_summary,
                            "max_error_px": "" if max_error_px is None else f"{max_error_px:.3f}",
                        }
                    )
                    
                    # Add to plot list if within limit
                    if len(images_to_plot) < num_samples:
                        images_to_plot.append(overlay)
                        
                    global_idx += 1

        # Plot Grid
        if not images_to_plot:
            return {
                "summary_image": None,
                "details_dir": details_dir,
                "rows": validation_rows,
                "summary": {
                    "validation_count": len(validation_rows),
                    "provenance_counts": provenance_counts,
                    "preview_count": 0,
                },
            }
        
        rows = int(np.ceil(len(images_to_plot) / 2))
        fig, axs = plt.subplots(rows, 2, figsize=(10, 5 * rows))
        fig.suptitle(f'Validation Snapshot (Top {len(images_to_plot)})', fontsize=16)
        
        # Handle case where rows=1 (axs is not 2D array)
        if rows == 1: axs = np.array(axs)
        axs = axs.flatten()
        
        for idx, img in enumerate(images_to_plot):
            axs[idx].imshow(img)
            axs[idx].axis('off')
            axs[idx].set_title(f"Sample {idx+1}")
            
        # Hide empty subplots
        for idx in range(len(images_to_plot), len(axs)):
            axs[idx].axis('off')
            
        plt.tight_layout(rect=(0, 0.03, 1, 0.95))
        plt.savefig(img_path, dpi=150)
        plt.close(fig)
        return {
            "summary_image": img_path,
            "details_dir": details_dir,
            "rows": validation_rows,
            "summary": {
                "validation_count": len(validation_rows),
                "provenance_counts": provenance_counts,
                "preview_count": len(images_to_plot),
            },
        }
