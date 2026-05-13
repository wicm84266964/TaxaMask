# pyright: reportMissingImports=false

import torch
import torch.optim as optim
import torch.nn as nn
from torch.utils.data import DataLoader
import os
import numpy as np
import cv2 
from PIL import Image
import torch.nn.functional as F
from ultralytics import SAM

try:
    from AntSleap.models.networks import TraitRegressor
    from AntSleap.models.sam_trainable import TrainableSAM
except ImportError:
    from models.networks import TraitRegressor
    from models.sam_trainable import TrainableSAM
from .dataset import TwoStageDataset
from .reporter import ExperimentReporter
from .cascade_manager import CascadingManager
from .projection import CoordinateMapper
from .taxonomy_defaults import DEFAULT_LOCATOR_SCOPE, DEFAULT_PROJECT_TAXONOMY, sanitize_locator_scope, sanitize_taxonomy
from .training_preflight import format_size_pair
from .cascade_routes import route_manifest_has_routes
from .runtime_device import normalize_device_preference, resolve_torch_device

class DiceLoss(nn.Module):
    def __init__(self, smooth=1):
        super(DiceLoss, self).__init__()
        self.smooth = smooth

    def forward(self, inputs, targets):
        inputs = torch.sigmoid(inputs)
        inputs = inputs.view(-1)
        targets = targets.view(-1)
        intersection = (inputs * targets).sum()                            
        dice = (2.*intersection + self.smooth)/(inputs.sum() + targets.sum() + self.smooth)  
        return 1 - dice

class FocalMSELoss(nn.Module):
    """
    Modified Focal Loss for Heatmap Regression.
    Penalizes deviations from 1.0 more heavily if the target is 1.0.
    """
    def __init__(self, alpha=2, beta=4):
        super(FocalMSELoss, self).__init__()
        self.alpha = alpha
        self.beta = beta

    def forward(self, pred, gt, reduction='mean'):
        # pred: (B, C, H, W)
        # gt: (B, C, H, W)
        pos_inds = gt.eq(1)
        neg_inds = gt.lt(1)

        neg_weights = torch.pow(1 - gt, self.beta)
        
        loss = 0
        pred = torch.clamp(pred, 1e-6, 1 - 1e-6)

        # "Easy" Focal Loss variant for Heatmaps: Weighted MSE
        # Standard CornerNet Focal Loss is complicated. 
        # Here we use a simpler Weighted MSE approach which is stable and effective.
        # Loss = (1 - p)^alpha * (p - y)^2
        
        # We can simply weight the MSE by the heatmap intensity itself?
        # Let's stick to standard MSE for now but weighted by positive pixels
        # Actually, let's use the USER's approved plan: Focal Loss.
        
        # Implementation of CornerNet Focal Loss
        # pos_loss = log(pred) * (1-pred)^alpha
        # neg_loss = log(1-pred) * pred^alpha * (1-gt)^beta
        
        # But our TraitRegressor outputs linear logits, not sigmoid. 
        # So we apply sigmoid first (conceptually), or use MSE.
        
        # Given "Scheme D" in chat, we agreed on:
        # Loss = Weighted MSE or Focal-like penalty.
        # Let's use Weighted MSE where positive pixels have much higher weight.
        
        # Weights: 100 for peak, 1 for background
        weights = torch.ones_like(gt)
        weights[gt > 0.8] = 20 # Focus on the peak
        weights[gt < 0.1] = 0.5 # Downweight background

        loss = weights * (pred - gt)**2
        if reduction == 'none':
            return loss
        if reduction == 'sum':
            return loss.sum()
        return loss.mean()

class AntEngine:
    def __init__(self, learning_rate=1e-4, weight_decay=1e-4, num_classes=None, device="auto"):
        self.device_preference = normalize_device_preference(device)
        self.device = resolve_torch_device(device)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.weights_dir = os.path.join(base_dir, "weights")
        if not os.path.exists(self.weights_dir): os.makedirs(self.weights_dir)
        
        if num_classes is None:
            num_classes = len(DEFAULT_LOCATOR_SCOPE)
        self.current_num_classes = num_classes
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.locator_resolution = (512, 512)
        self.loaded_locator_timestamp = None
        self.loaded_locator_requires_legacy_confirmation = False
        self.loaded_locator_is_legacy_512 = False

        # 1. Locator (Now with WH Regression)
        self.locator = TraitRegressor(in_channels=3, out_channels=num_classes).to(self.device) 
        self.opt_loc = optim.Adam(self.locator.parameters(), lr=learning_rate, weight_decay=weight_decay)
        
        # Loss Functions
        self.crit_heatmap = FocalMSELoss() # New Focal-like MSE
        self.crit_wh = nn.SmoothL1Loss(reduction='none') # Robust regression for WH
        
        # 2. SAM
        base_sam_path = os.path.join(self.weights_dir, "sam_b.pt")
        self.base_sam_path = base_sam_path
        self.base_sam_predictor = None
        self.parts_model = TrainableSAM(model_path=base_sam_path, device=self.device)
        trainable_params = [p for p in self.parts_model.parameters() if p.requires_grad]
        self.opt_parts = optim.Adam(trainable_params, lr=learning_rate, weight_decay=weight_decay)
        
        self.crit_dice = DiceLoss()
        self.crit_parts = self.crit_dice 
        
        self.cascade_manager = CascadingManager(self)
        
        self.history = {"locator": [], "parts": []}
        self.load_weights()

    def set_device_preference(self, device_preference):
        clean_preference = normalize_device_preference(device_preference)
        new_device = resolve_torch_device(clean_preference)
        if clean_preference == self.device_preference and new_device == self.device:
            return False

        self.device_preference = clean_preference
        self.device = new_device
        self.locator.to(self.device)
        self.parts_model.to(self.device)
        self.parts_model.device = self.device
        self.base_sam_predictor = None

        self.opt_loc = optim.Adam(self.locator.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
        trainable_params = [p for p in self.parts_model.parameters() if p.requires_grad]
        self.opt_parts = optim.Adam(trainable_params, lr=self.learning_rate, weight_decay=self.weight_decay)
        if getattr(self, "cascade_manager", None) is not None:
            self.cascade_manager.device = self.device
            self.cascade_manager.loaded_experts.clear()
        if self.device.type != "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()
        return True

    def rebuild_locator(self, num_classes, learning_rate=1e-4, weight_decay=1e-4):
        if num_classes == self.current_num_classes: return
        print(f"Rebuilding Locator for {num_classes} classes...")
        self.current_num_classes = num_classes
        self.locator = TraitRegressor(in_channels=3, out_channels=num_classes).to(self.device)
        self.opt_loc = optim.Adam(self.locator.parameters(), lr=learning_rate, weight_decay=weight_decay)
        self.loaded_locator_timestamp = None
        self.loaded_locator_requires_legacy_confirmation = False
        self.loaded_locator_is_legacy_512 = False

    def reset_locator_to_base(self):
        print("Resetting Locator to base (untrained) weights...")
        self.locator = TraitRegressor(in_channels=3, out_channels=self.current_num_classes).to(self.device)
        self.opt_loc = optim.Adam(self.locator.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
        self.locator_resolution = (512, 512)
        self.loaded_locator_timestamp = None
        self.loaded_locator_requires_legacy_confirmation = False
        self.loaded_locator_is_legacy_512 = False

    def update_hyperparameters(self, learning_rate, weight_decay):
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        for param_group in self.opt_loc.param_groups:
            param_group['lr'] = learning_rate
            param_group['weight_decay'] = weight_decay
        for param_group in self.opt_parts.param_groups:
            param_group['lr'] = learning_rate
            param_group['weight_decay'] = weight_decay

    def _resolve_taxonomy_scopes(self, current_taxonomy=None, locator_scope=None):
        full_taxonomy = sanitize_taxonomy(current_taxonomy or locator_scope, fallback=DEFAULT_PROJECT_TAXONOMY)
        active_locator_scope = sanitize_locator_scope(locator_scope, full_taxonomy, fallback=full_taxonomy)
        return full_taxonomy, active_locator_scope

    def _resolve_image_size(self, image_input):
        if isinstance(image_input, np.ndarray) and image_input.ndim >= 2:
            h, w = image_input.shape[:2]
            return float(w), float(h)
        if isinstance(image_input, Image.Image):
            try:
                w, h = image_input.size
                return float(w), float(h)
            except Exception:
                return None
        return None

    def _get_base_sam_predictor(self):
        if self.base_sam_predictor is None:
            self.base_sam_predictor = SAM(self.base_sam_path)
        return self.base_sam_predictor

    def _polygon_from_predictor(self, predictor, image_input, prompt_box, left, top, poly_epsilon, image_size=None):
        if predictor is None:
            return None

        if image_size is None:
            image_size = self._resolve_image_size(image_input)
        if image_size is None:
            return None
        w_orig, h_orig = image_size

        results = predictor.predict(
            image_input,
            bboxes=[prompt_box],
            verbose=False,
            device=self.device,
        )

        if not results or not results[0].masks:
            return None

        poly = results[0].masks.xy[0]
        if len(poly) == 0:
            return None

        poly_np = np.array(poly, dtype=np.int32)
        approx = cv2.approxPolyDP(poly_np, poly_epsilon, True)
        approx_points = np.array(approx, dtype=np.float32).reshape(-1, 2)
        final_poly = [[float(x + left), float(y + top)] for x, y in approx_points]

        clamped_poly = []
        for x, y in final_poly:
            cx = max(0.0, min(x, float(w_orig - 0.1)))
            cy = max(0.0, min(y, float(h_orig - 0.1)))
            clamped_poly.append([cx, cy])

        return clamped_poly if len(clamped_poly) > 2 else None

    def _run_sam_polygon(self, img_crop, prompt_box, left, top, poly_epsilon, image_size):
        return self._polygon_from_predictor(
            self.parts_model.ultralytics_sam,
            img_crop,
            prompt_box,
            left,
            top,
            poly_epsilon,
            image_size=image_size,
        )

    def predict_base_sam_polygon(self, image_input, prompt_box, poly_epsilon=2.0):
        predictor = self._get_base_sam_predictor()
        return self._polygon_from_predictor(
            predictor,
            image_input,
            prompt_box,
            0.0,
            0.0,
            poly_epsilon,
            image_size=self._resolve_image_size(image_input),
        )

    def calculate_iou(self, pred_mask, true_mask):
        pred_mask = (torch.sigmoid(pred_mask) > 0.5).float()
        intersection = (pred_mask * true_mask).sum()
        union = pred_mask.sum() + true_mask.sum() - intersection
        if union == 0: return 1.0
        return (intersection / union).item()

    def _unpack_locator_batch(self, batch_data):
        if not isinstance(batch_data, (list, tuple)):
            raise ValueError("Locator batch must be a tuple or list.")
        if len(batch_data) < 3:
            raise ValueError("Locator batch must contain at least img, heatmap target, and WH target.")

        imgs = batch_data[0]
        hm_target = batch_data[1]
        wh_target = batch_data[2]
        valid_parts_mask = batch_data[3] if len(batch_data) > 3 else torch.ones(hm_target.shape[:2], dtype=hm_target.dtype)
        return imgs, hm_target, wh_target, valid_parts_mask

    def _expand_locator_valid_mask(self, valid_parts_mask, target_tensor):
        if valid_parts_mask is None:
            return None
        expanded_mask = valid_parts_mask
        while expanded_mask.dim() < target_tensor.dim():
            expanded_mask = expanded_mask.unsqueeze(-1)
        return expanded_mask.to(device=target_tensor.device, dtype=target_tensor.dtype)

    def _masked_locator_average(self, loss_tensor, valid_parts_mask):
        expanded_mask = self._expand_locator_valid_mask(valid_parts_mask, loss_tensor)
        if expanded_mask is None:
            return loss_tensor.mean()

        masked_loss = loss_tensor * expanded_mask
        denom = expanded_mask.sum()
        if float(denom.item()) <= 0.0:
            return loss_tensor.sum() * 0.0
        return masked_loss.sum() / denom

    def _compute_locator_losses(self, hm_pred, hm_target, wh_pred, wh_target, valid_parts_mask):
        heatmap_loss_tensor = self.crit_heatmap(hm_pred, hm_target, reduction='none')
        wh_loss_tensor = self.crit_wh(wh_pred, wh_target)
        loss_hm = self._masked_locator_average(heatmap_loss_tensor, valid_parts_mask)
        loss_wh = self._masked_locator_average(wh_loss_tensor, valid_parts_mask)
        total_loss = loss_hm + 0.5 * loss_wh
        return loss_hm, loss_wh, total_loss

    def _compute_locator_pixel_error(self, hm_pred, hm_target, valid_parts_mask):
        total_error = 0.0
        valid_count = 0

        hm_pred_np = hm_pred.detach().cpu().numpy()
        hm_target_np = hm_target.detach().cpu().numpy()
        if valid_parts_mask is None:
            valid_parts_mask_np = np.ones(hm_target_np.shape[:2], dtype=np.float32)
        else:
            valid_parts_mask_np = valid_parts_mask.detach().cpu().numpy()

        batch_size, num_parts = hm_target_np.shape[:2]
        for batch_idx in range(batch_size):
            for part_idx in range(num_parts):
                if float(valid_parts_mask_np[batch_idx, part_idx]) <= 0.0:
                    continue
                hm_p = hm_pred_np[batch_idx, part_idx]
                hm_t = hm_target_np[batch_idx, part_idx]
                yp, xp = np.unravel_index(hm_p.argmax(), hm_p.shape)
                yt, xt = np.unravel_index(hm_t.argmax(), hm_t.shape)
                total_error += float(np.sqrt((xp - xt) ** 2 + (yp - yt) ** 2))
                valid_count += 1

        return total_error, valid_count

    def validate_epoch(self, dataloader, model, stop_callback=None):
        is_sam = isinstance(model, TrainableSAM)
        if is_sam: model.sam_model.eval()
        else: model.eval()
        total_loss, total_metric, count = 0, 0, 0
        criterion = self.crit_dice if is_sam else self.crit_heatmap
        
        with torch.no_grad():
            for batch_data in dataloader:
                if callable(stop_callback) and stop_callback():
                    return None
                if is_sam:
                    imgs, boxes, masks = batch_data
                    imgs, boxes, masks = imgs.to(self.device), boxes.to(self.device), masks.to(self.device)
                    pred_masks, _ = model(imgs, boxes)
                    loss = criterion(pred_masks, masks)
                    total_metric += self.calculate_iou(pred_masks, masks)
                    total_loss += loss.item()
                else:
                    # Locator Batch: [img, heatmap_target, wh_target, valid_parts_mask]
                    imgs, hm_target, wh_target, valid_parts_mask = self._unpack_locator_batch(batch_data)
                    imgs = imgs.to(self.device)
                    hm_target = hm_target.to(self.device)
                    wh_target = wh_target.to(self.device)
                    valid_parts_mask = valid_parts_mask.to(self.device)
                    
                    hm_pred, wh_pred = model(imgs)

                    _, _, locator_loss = self._compute_locator_losses(
                        hm_pred,
                        hm_target,
                        wh_pred,
                        wh_target,
                        valid_parts_mask,
                    )

                    total_loss += locator_loss.item()
                    pixel_error_sum, pixel_count = self._compute_locator_pixel_error(
                        hm_pred,
                        hm_target,
                        valid_parts_mask,
                    )
                    total_metric += pixel_error_sum
                    count += pixel_count
                         
        avg_loss = total_loss / len(dataloader)
        if is_sam:
            avg_metric = total_metric / len(dataloader)
        else:
            avg_metric = (total_metric / count) if count > 0 else float('nan')
        return {'loss': avg_loss, 'iou' if is_sam else 'pixel_error': avg_metric}

    def load_weights(self, timestamp=None):
        """Legacy method: Loads both if available."""
        self.load_locator(timestamp)
        self.load_sam_decoder(timestamp)

    def load_locator(self, timestamp):
        suffix = f"_{timestamp}" if timestamp else ""
        loc_path = os.path.join(self.weights_dir, f"locator{suffix}.pth")
        
        # If specific timestamp not found, try to find latest? No, strict loading for specific selection.
        if os.path.exists(loc_path):
            try:
                saved_state = torch.load(loc_path, map_location=self.device)
                checkpoint_state = saved_state
                checkpoint_meta = {}

                if isinstance(saved_state, dict) and isinstance(saved_state.get("state_dict"), dict):
                    checkpoint_state = saved_state.get("state_dict", {})
                    checkpoint_meta = saved_state.get("meta", {}) if isinstance(saved_state.get("meta"), dict) else {}
                elif isinstance(saved_state, dict):
                    checkpoint_meta = saved_state.get("meta", {}) if isinstance(saved_state.get("meta"), dict) else {}
                
                # Architecture check
                if 'outc.conv.weight' in checkpoint_state:
                     if checkpoint_state['outc.conv.weight'].shape[0] != self.current_num_classes:
                          print(f"Locator architecture mismatch for {timestamp}. Skipping.")
                          return

                self.locator.load_state_dict(checkpoint_state, strict=False)
                saved_resolution = checkpoint_meta.get("locator_size")
                legacy_resolution = checkpoint_meta.get("locator_resolution")
                if saved_resolution is None and legacy_resolution is not None:
                    try:
                        legacy_side = max(1, int(legacy_resolution))
                    except Exception:
                        legacy_side = 512
                    saved_resolution = [legacy_side, legacy_side]

                if saved_resolution is None:
                    self.locator_resolution = (512, 512)
                    self.loaded_locator_requires_legacy_confirmation = True
                    self.loaded_locator_is_legacy_512 = True
                else:
                    try:
                        self.locator_resolution = (max(1, int(saved_resolution[0])), max(1, int(saved_resolution[1])))
                    except Exception:
                        self.locator_resolution = (512, 512)
                    self.loaded_locator_requires_legacy_confirmation = False
                    self.loaded_locator_is_legacy_512 = False
                self.loaded_locator_timestamp = timestamp
                print(f"Loaded Locator: {os.path.basename(loc_path)}")
            except Exception as e:
                print(f"ERROR loading Locator {loc_path}: {e}")
        else:
            print(f"Locator weights not found: {loc_path}")

    def load_sam_decoder(self, timestamp):
        suffix = f"_{timestamp}" if timestamp else ""
        sam_path = os.path.join(self.weights_dir, f"sam_decoder_lora{suffix}.pth")
        
        if os.path.exists(sam_path):
            try:
                self.parts_model.sam_model.mask_decoder.load_state_dict(torch.load(sam_path, map_location=self.device))
                print(f"Loaded Segmenter (Fine-tuned): {os.path.basename(sam_path)}")
            except Exception as e:
                print(f"ERROR loading SAM Decoder {sam_path}: {e}")
        else:
            print(f"Segmenter weights not found: {sam_path}")

    def reset_sam_to_base(self):
        print("Resetting Segmenter to Base SAM (Original)...")
        # To reset, we reload the original weights from the base model file
        # Or simpler: re-instantiate the parts_model? No, that's heavy.
        # We can re-load the state dict from the base file if we kept a copy?
        # Actually, since we only trained the mask decoder, we can reload just the mask decoder 
        # from the original "sam_b.pt".
        # But "sam_b.pt" is a full checkpoint.
        
        try:
            # Re-initialize the TrainableSAM class is the safest way to ensure clean slate
            # But we want to avoid reloading the heavy Image Encoder if possible.
            # Ideally, we should have saved the "initial_state" of the decoder.
            # For now, let's just re-create the wrapper. It's fast enough (~1-2s).
            base_sam_path = os.path.join(self.weights_dir, "sam_b.pt")
            self.parts_model = TrainableSAM(model_path=base_sam_path, device=self.device)
            
            # We also need to re-create the optimizer because parameters changed objects
            trainable_params = [p for p in self.parts_model.parameters() if p.requires_grad]
            self.opt_parts = optim.Adam(trainable_params, lr=self.learning_rate, weight_decay=self.weight_decay)
            print("Segmenter reset complete.")
        except Exception as e:
            print(f"Error resetting SAM: {e}")

    def reset_to_base_model(self):
        """Resets everything (Locator + SAM)"""
        print("Resetting EVERYTHING to Base...")
        self.locator = TraitRegressor(in_channels=3, out_channels=self.current_num_classes).to(self.device)
        self.opt_loc = optim.Adam(self.locator.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
        self.reset_sam_to_base()

    def save_weights(self, save_locator=True, save_segmenter=True):
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        if save_locator:
            locator_payload = {
                "state_dict": self.locator.state_dict(),
                    "meta": {
                    "locator_size": [int(self.locator_resolution[0]), int(self.locator_resolution[1])],
                    "locator_resolution": int(self.locator_resolution[0]),
                    "num_classes": int(self.current_num_classes),
                },
            }
            torch.save(locator_payload, os.path.join(self.weights_dir, f"locator_{ts}.pth"))
            self.loaded_locator_timestamp = ts
            self.loaded_locator_requires_legacy_confirmation = False
            self.loaded_locator_is_legacy_512 = False
        if save_segmenter:
            torch.save(self.parts_model.sam_model.mask_decoder.state_dict(), os.path.join(self.weights_dir, f"sam_decoder_lora_{ts}.pth"))
        return ts

    def generate_report(self, val_dataloader=None, num_samples=4):
        """Generates plots and CSVs for the current training session."""
        reporter = ExperimentReporter(os.path.dirname(self.weights_dir))
        
        # 1. Save CSV
        csv_path = reporter.save_csv(self.history)
        
        # 2. Plot Metrics
        metrics_path = reporter.plot_metrics(self.history)
        
        # 3. Validation Samples (if loader provided)
        val_path = None
        validation_rows = []
        details_dir = None
        validation_summary = {"validation_count": 0, "provenance_counts": {}, "preview_count": 0}
        if val_dataloader:
            validation_payload = reporter.plot_validation_samples(self, val_dataloader, num_samples=num_samples)
            if isinstance(validation_payload, dict):
                val_path = validation_payload.get("summary_image")
                validation_rows = list(validation_payload.get("rows", []))
                details_dir = validation_payload.get("details_dir")
                validation_summary = dict(validation_payload.get("summary", validation_summary))
            else:
                val_path = validation_payload

        validation_index_path = reporter.save_validation_index(validation_rows)
        validation_count_value = validation_summary.get("validation_count", 0)
        if not isinstance(validation_count_value, (int, float)):
            validation_count_value = 0
        validation_preview_value = validation_summary.get("preview_count", 0)
        if not isinstance(validation_preview_value, (int, float)):
            validation_preview_value = 0
        provenance_counts = validation_summary.get("provenance_counts", {})
        if not isinstance(provenance_counts, dict):
            provenance_counts = {}
        report_summary_payload = {
            "history_keys": sorted(list(self.history.keys())),
            "metrics_plot": os.path.basename(metrics_path) if metrics_path else None,
            "training_log_csv": os.path.basename(csv_path) if csv_path else None,
            "validation_summary_image": os.path.basename(val_path) if val_path else None,
            "validation_details_dir": os.path.basename(details_dir) if details_dir else "val_details",
            "validation_index_csv": os.path.basename(validation_index_path) if validation_index_path else None,
            "validation_count": int(validation_count_value),
            "validation_preview_count": int(validation_preview_value),
            "validation_provenance_counts": provenance_counts,
        }
        report_summary_path = reporter.save_report_summary(report_summary_payload)
             
        print(f"Report Generated at: {reporter.get_experiment_dir()}")
        return {
            'dir': reporter.get_experiment_dir(),
            'csv': csv_path,
            'metrics': metrics_path,
            'val': val_path,
            'validation_index': validation_index_path,
            'report_summary': report_summary_path,
            'validation_rows': validation_rows,
            'validation_summary': report_summary_payload,
            'details_dir': details_dir or os.path.join(reporter.get_experiment_dir(), "val_details"),
        }

    def train_epoch(self, dataloader, model, optimizer, criterion, log_func=None, stop_callback=None):
        is_sam = isinstance(model, TrainableSAM)
        if is_sam: model.sam_model.train()
        else: model.train()
        total_loss = 0
        
        for i, batch_data in enumerate(dataloader):
            if callable(stop_callback) and stop_callback():
                return None
            optimizer.zero_grad()
            if is_sam:
                imgs, boxes, masks = batch_data
                imgs, boxes, masks = imgs.to(self.device), boxes.to(self.device), masks.to(self.device)
                pred_masks, _ = model(imgs, boxes)
                loss = criterion(pred_masks, masks)
            else:
                # Locator Batch: [img, heatmap_target, wh_target, valid_parts_mask]
                imgs, hm_target, wh_target, valid_parts_mask = self._unpack_locator_batch(batch_data)
                imgs = imgs.to(self.device)
                hm_target = hm_target.to(self.device)
                wh_target = wh_target.to(self.device)
                valid_parts_mask = valid_parts_mask.to(self.device)
                
                hm_pred, wh_pred = model(imgs)

                _, _, loss = self._compute_locator_losses(
                    hm_pred,
                    hm_target,
                    wh_pred,
                    wh_target,
                    valid_parts_mask,
                )
                
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        return total_loss / len(dataloader)

    def predict_full_pipeline(
        self,
        image_path,
        current_taxonomy=None,
        locator_scope=None,
        conf_thresh=0.1,
        adapt_thresh=0.4,
        box_pad=0.4,
        noise_floor=0.15,
        poly_epsilon=2.0,
        project_route_manifest=None,
    ):
        self.locator.eval()
        self.parts_model.sam_model.eval()

        try:
            img_pil = Image.open(image_path).convert('RGB')
        except Exception:
            return {"polygons": {}, "auto_boxes": {}, "scores": {}, "meta": {}}

        w_orig, h_orig = img_pil.size

        locator_size = getattr(self, "locator_resolution", (512, 512)) or (512, 512)
        try:
            locator_width = max(1, int(locator_size[0]))
            locator_height = max(1, int(locator_size[1]))
        except Exception:
            locator_width, locator_height = 512, 512

        # Resize to locator size with Letterbox
        scale = min(float(locator_width) / w_orig, float(locator_height) / h_orig)
        new_w, new_h = int(w_orig * scale), int(h_orig * scale)
        pad_w, pad_h = (locator_width - new_w) // 2, (locator_height - new_h) // 2

        bilinear_mode = Image.Resampling.BILINEAR if hasattr(Image, "Resampling") else getattr(Image, "BILINEAR", 2)
        img_resized = img_pil.resize((new_w, new_h), bilinear_mode)
        img_loc = Image.new('RGB', (locator_width, locator_height), (0, 0, 0))
        img_loc.paste(img_resized, (pad_w, pad_h))
        t_loc = torch.from_numpy(np.array(img_loc)).permute(2, 0, 1).float().unsqueeze(0).to(self.device) / 255.0

        with torch.no_grad():
            hm_all, wh_all = self.locator(t_loc)
            hm_all = hm_all.cpu().numpy()[0]
            wh_all = wh_all.cpu().numpy()[0]

        current_taxonomy, active_locator_scope = self._resolve_taxonomy_scopes(current_taxonomy, locator_scope)
        if len(active_locator_scope) != hm_all.shape[0]:
            print(f"WARNING: Mismatch! Locator scope {len(active_locator_scope)} vs Model {hm_all.shape[0]}")

        cascade_block_reasons = {}
        cascade_attempted_routes = []
        cascade_applied_routes = []
        cascade_applied_count = 0
        cascade_manager = getattr(self, "cascade_manager", None)
        get_runtime_route_manifest = getattr(cascade_manager, "get_runtime_route_manifest", None)
        if callable(get_runtime_route_manifest):
            runtime_route_manifest = get_runtime_route_manifest(project_route_manifest)
        else:
            runtime_route_manifest = project_route_manifest if isinstance(project_route_manifest, dict) else {}
        runtime_route_source = "project" if route_manifest_has_routes(project_route_manifest or {}) else "legacy_global"
        routes_ready = getattr(cascade_manager, "routes_ready", None)
        if callable(routes_ready):
            try:
                cascade_routes_ready = bool(routes_ready(runtime_route_manifest))
            except TypeError:
                cascade_routes_ready = bool(routes_ready())
        else:
            cascade_routes_ready = False
        if not cascade_routes_ready and runtime_route_source != "project":
            runtime_route_source = "none"

        predictions = {
            "polygons": {},
            "auto_boxes": {},
            "scores": {},
            "meta": {
                "image_size": [float(w_orig), float(h_orig)],
                "conf_thresh": float(conf_thresh),
                "adapt_thresh": float(adapt_thresh),
                "noise_floor": float(noise_floor),
                "locator_size": [int(locator_width), int(locator_height)],
                "locator_resolution_label": format_size_pair((locator_width, locator_height)),
                "project_taxonomy": list(current_taxonomy),
                "locator_scope": list(active_locator_scope),
                "cascade_requested": bool(cascade_routes_ready),
                "cascade_enabled": bool(cascade_routes_ready),
                "cascade_routes_ready": bool(cascade_routes_ready),
                "cascade_route_source": runtime_route_source,
                "cascade_route_manifest_version": str(runtime_route_manifest.get("version") or ""),
                "cascade_applied_count": 0,
                "cascade_attempted_routes": cascade_attempted_routes,
                "cascade_applied_routes": cascade_applied_routes,
                "cascade_block_reasons": cascade_block_reasons,
            },
        }

        predictions["meta"]["cascade_routes_ready"] = cascade_routes_ready

        for i, part_name in enumerate(active_locator_scope):
            if i >= hm_all.shape[0]:
                break

            hm = hm_all[i]
            wh = wh_all[i]

            max_val = float(hm.max())
            min_required_peak = max(float(conf_thresh), float(noise_floor))
            if max_val < min_required_peak:
                print(f"DEBUG: Part '{part_name}' skipped. Peak {max_val:.4f} < {min_required_peak:.4f}")
                continue

            # 让 adapt_thresh / noise_floor 真实参与定位点筛选
            effective_thresh = max(float(noise_floor), float(adapt_thresh) * max_val)
            hm_filtered = np.where(hm >= effective_thresh, hm, 0.0)
            if hm_filtered.max() <= 0:
                print(f"DEBUG: Part '{part_name}' skipped. No activation above effective threshold {effective_thresh:.4f}")
                continue

            y_loc, x_loc = np.unravel_index(hm_filtered.argmax(), hm_filtered.shape)
            cx, cy = float(x_loc), float(y_loc)

            pred_w = max(float(wh[0]) * float(locator_width), 10.0)
            pred_h = max(float(wh[1]) * float(locator_height), 10.0)

            w_box = pred_w * (1.0 + float(box_pad))
            h_box = pred_h * (1.0 + float(box_pad))

            center_x = (cx - pad_w) / scale
            center_y = (cy - pad_h) / scale
            half_w, half_h = (w_box / scale) / 2.0, (h_box / scale) / 2.0

            crop_w, crop_h = max(half_w * 2 + 200, 512), max(half_h * 2 + 200, 512)
            left = max(0, int(center_x - crop_w / 2))
            top = max(0, int(center_y - crop_h / 2))
            right = min(w_orig, int(center_x + crop_w / 2))
            bottom = min(h_orig, int(center_y + crop_h / 2))
            img_crop = img_pil.crop((left, top, right, bottom))

            if img_crop.width < 2 or img_crop.height < 2:
                print(f"DEBUG: Part '{part_name}' skipped. Crop too small.")
                continue

            rel_x, rel_y = center_x - left, center_y - top
            p_x1 = max(0.0, rel_x - half_w)
            p_y1 = max(0.0, rel_y - half_h)
            p_x2 = min(float(img_crop.width), rel_x + half_w)
            p_y2 = min(float(img_crop.height), rel_y + half_h)

            p_x1 = max(0.0, min(p_x1, float(img_crop.width - 1)))
            p_y1 = max(0.0, min(p_y1, float(img_crop.height - 1)))
            p_x2 = max(p_x1 + 1.0, min(p_x2, float(img_crop.width)))
            p_y2 = max(p_y1 + 1.0, min(p_y2, float(img_crop.height)))

            prompt_box = [p_x1, p_y1, p_x2, p_y2]
            if p_x2 <= p_x1 or p_y2 <= p_y1:
                print(f"DEBUG: Invalid prompt box for {part_name}: {prompt_box}")
                continue

            # 将 prompt_box 映射回原图坐标，并作为 auto_box 初值
            orig_bx1 = p_x1 + left
            orig_by1 = p_y1 + top
            orig_bx2 = p_x2 + left
            orig_by2 = p_y2 + top

            # --- CASCADE ROUTE INTERCEPTION (manifest-driven) ---
            if cascade_routes_ready:
                parent_part = "macro_locator"
                if not cascade_routes_ready:
                    cascade_block_reasons[part_name] = "routes_not_ready"
                else:
                    route = self.cascade_manager._find_route(parent_part, part_name, route_manifest=runtime_route_manifest)
                    if route is None:
                        cascade_block_reasons[part_name] = "route_missing"
                    else:
                        route_block_reason = self.cascade_manager.get_route_block_reason(route)
                        if route_block_reason:
                            cascade_block_reasons[part_name] = route_block_reason
                        else:
                            cascade_attempted_routes.append(self.cascade_manager.describe_route(route))
                            expert_result = self.cascade_manager.infer_child_part(
                                image_path,
                                parent_box=[orig_bx1, orig_by1, orig_bx2, orig_by2],
                                child_part_name=part_name,
                                parent_part=parent_part,
                                route_manifest=runtime_route_manifest,
                            )

                            expert_box = None
                            expert_conf = 0.0
                            if isinstance(expert_result, dict):
                                raw_box = expert_result.get("box")
                                if isinstance(raw_box, (list, tuple)) and len(raw_box) == 4:
                                    expert_box = list(raw_box)

                                raw_conf = expert_result.get("confidence", 0.0)
                                if isinstance(raw_conf, (int, float)):
                                    expert_conf = float(raw_conf)
                            elif isinstance(expert_result, (list, tuple)) and len(expert_result) == 4:
                                expert_box = list(expert_result)
                                expert_conf = 1.0

                            if expert_box:
                                expert_box = CoordinateMapper.clamp_bbox_to_size(expert_box, w_orig, h_orig)

                                route_min_conf = self.cascade_manager.get_route_min_conf(parent_part, part_name, route_manifest=runtime_route_manifest)
                                conf_gate = float(adapt_thresh)
                                if isinstance(route_min_conf, (int, float)):
                                    conf_gate = max(conf_gate, float(route_min_conf))

                                if expert_conf >= conf_gate:
                                    orig_bx1, orig_by1, orig_bx2, orig_by2 = expert_box
                                    cascade_applied_count += 1
                                    cascade_applied_routes.append(self.cascade_manager.describe_route(route))
                                    print(f"[{part_name}] Macro box overridden by Micro-Expert (conf={expert_conf:.3f}).")

                                    px1 = max(0.0, orig_bx1 - left)
                                    py1 = max(0.0, orig_by1 - top)
                                    px2 = min(float(img_crop.width), orig_bx2 - left)
                                    py2 = min(float(img_crop.height), orig_by2 - top)
                                    if px2 > px1 and py2 > py1:
                                        prompt_box = [px1, py1, px2, py2]
                                else:
                                    cascade_block_reasons[part_name] = "confidence_below_gate"
                                    print(f"[{part_name}] Expert suggestion ignored (conf={expert_conf:.3f} < gate={conf_gate:.3f}).")
                            else:
                                cascade_block_reasons[part_name] = "expert_unavailable"

            final_box = CoordinateMapper.clamp_bbox_to_size(
                [orig_bx1, orig_by1, orig_bx2, orig_by2],
                w_orig,
                h_orig,
            )
            predictions["auto_boxes"][part_name] = [float(v) for v in final_box]
            predictions["scores"][part_name] = max_val

            polygon = self._run_sam_polygon(img_crop, prompt_box, left, top, poly_epsilon, (w_orig, h_orig))
            if polygon:
                predictions["polygons"][part_name] = polygon
            else:
                print(f"DEBUG: Part '{part_name}' SAM returned NO valid polygon.")

        if cascade_routes_ready:
            available_parents = list(predictions["auto_boxes"].keys())
            for child_part in current_taxonomy:
                if child_part in active_locator_scope or child_part in predictions["auto_boxes"]:
                    continue

                route = self.cascade_manager.resolve_route_for_child(
                    child_part,
                    available_parents,
                    route_manifest=runtime_route_manifest,
                )
                if not route:
                    cascade_block_reasons[child_part] = "route_missing"
                    continue

                route_block_reason = self.cascade_manager.get_route_block_reason(route)
                if route_block_reason:
                    cascade_block_reasons[child_part] = route_block_reason
                    continue

                cascade_attempted_routes.append(self.cascade_manager.describe_route(route))

                parent_part = str(route.get("parent", "")).strip()
                parent_box = predictions["auto_boxes"].get(parent_part)
                if not parent_box:
                    cascade_block_reasons[child_part] = "parent_box_missing"
                    continue

                expert_result = self.cascade_manager.infer_child_part(
                    image_path,
                    parent_box=parent_box,
                    child_part_name=child_part,
                    parent_part=parent_part,
                    route_manifest=runtime_route_manifest,
                )

                expert_box = None
                expert_conf = 0.0
                if isinstance(expert_result, dict):
                    raw_box = expert_result.get("box")
                    if isinstance(raw_box, (list, tuple)) and len(raw_box) == 4:
                        expert_box = list(raw_box)

                    raw_conf = expert_result.get("confidence", 0.0)
                    if isinstance(raw_conf, (int, float)):
                        expert_conf = float(raw_conf)
                elif isinstance(expert_result, (list, tuple)) and len(expert_result) == 4:
                    expert_box = list(expert_result)
                    expert_conf = 1.0

                if not expert_box:
                    cascade_block_reasons[child_part] = "expert_unavailable"
                    continue

                expert_box = CoordinateMapper.clamp_bbox_to_size(expert_box, w_orig, h_orig)
                route_min_conf = self.cascade_manager.get_route_min_conf(parent_part, child_part, route_manifest=runtime_route_manifest)
                conf_gate = float(adapt_thresh)
                if isinstance(route_min_conf, (int, float)):
                    conf_gate = max(conf_gate, float(route_min_conf))
                if expert_conf < conf_gate:
                    cascade_block_reasons[child_part] = "confidence_below_gate"
                    continue

                parent_box = CoordinateMapper.clamp_bbox_to_size(parent_box, w_orig, h_orig)
                p_x1, p_y1, p_x2, p_y2 = CoordinateMapper.sanitize_bbox_xyxy(parent_box)
                crop_left = max(0, int(np.floor(p_x1)))
                crop_top = max(0, int(np.floor(p_y1)))
                crop_right = min(w_orig, int(np.ceil(p_x2)))
                crop_bottom = min(h_orig, int(np.ceil(p_y2)))
                if crop_right <= crop_left or crop_bottom <= crop_top:
                    cascade_block_reasons[child_part] = "parent_crop_invalid"
                    continue

                parent_crop = img_pil.crop((crop_left, crop_top, crop_right, crop_bottom))
                local_prompt_box = [
                    expert_box[0] - crop_left,
                    expert_box[1] - crop_top,
                    expert_box[2] - crop_left,
                    expert_box[3] - crop_top,
                ]
                local_prompt_box = CoordinateMapper.clamp_bbox_to_size(
                    local_prompt_box,
                    parent_crop.width,
                    parent_crop.height,
                )

                predictions["auto_boxes"][child_part] = [float(v) for v in expert_box]
                predictions["scores"][child_part] = expert_conf
                cascade_applied_count += 1
                cascade_applied_routes.append(self.cascade_manager.describe_route(route))

                polygon = self._run_sam_polygon(
                    parent_crop,
                    local_prompt_box,
                    crop_left,
                    crop_top,
                    poly_epsilon,
                    (w_orig, h_orig),
                )
                if polygon:
                    predictions["polygons"][child_part] = polygon
                else:
                    cascade_block_reasons[child_part] = "sam_polygon_missing"

        elif runtime_route_source == "project":
            raw_route_list = runtime_route_manifest.get("routes", []) if isinstance(runtime_route_manifest, dict) else []
            route_list = raw_route_list if isinstance(raw_route_list, list) else []
            for route in route_list:
                if not isinstance(route, dict):
                    continue
                child_part = str(route.get("child") or "").strip()
                if not child_part or child_part in active_locator_scope or child_part in predictions["auto_boxes"]:
                    continue
                if child_part in cascade_block_reasons:
                    continue
                route_block_reason = self.cascade_manager.get_route_block_reason(route)
                cascade_block_reasons[child_part] = route_block_reason or "route_disabled"

        unique_attempted = []
        seen_attempted = set()
        for label in cascade_attempted_routes:
            if label in seen_attempted:
                continue
            seen_attempted.add(label)
            unique_attempted.append(label)

        unique_applied = []
        seen_applied = set()
        for label in cascade_applied_routes:
            if label in seen_applied:
                continue
            seen_applied.add(label)
            unique_applied.append(label)

        predictions["meta"]["cascade_attempted_routes"] = unique_attempted
        predictions["meta"]["cascade_applied_routes"] = unique_applied
        predictions["meta"]["cascade_applied_count"] = cascade_applied_count
        return predictions
