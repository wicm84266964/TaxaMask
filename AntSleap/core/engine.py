# pyright: reportMissingImports=false

import copy
import hashlib
import io
import torch
import torch.optim as optim
import torch.nn as nn
from torch.utils.data import DataLoader
import os
import re
import secrets
import threading
import numpy as np
import cv2 
from PIL import Image
import torch.nn.functional as F
from ultralytics import SAM

try:
    from AntSleap.models.networks import TraitRegressor
    from AntSleap.models.sam_trainable import (
        TrainableSAM,
        load_sam_from_checkpoint_bytes,
    )
except ImportError:
    from models.networks import TraitRegressor
    from models.sam_trainable import TrainableSAM, load_sam_from_checkpoint_bytes
from .dataset import TwoStageDataset
from .reporter import ExperimentReporter
from .cascade_manager import CascadingManager
from .projection import CoordinateMapper
from .taxonomy_defaults import DEFAULT_LOCATOR_SCOPE, DEFAULT_PROJECT_TAXONOMY, sanitize_locator_scope, sanitize_taxonomy
from .training_preflight import format_size_pair
from .cascade_routes import route_manifest_has_routes
from .runtime_device import normalize_device_preference, resolve_torch_device
from .model_profiles import DEFAULT_LOCATOR_LOSS_WEIGHTS, sanitize_loss_weights
from .sam_decoder_checkpoint import (
    build_sam_decoder_checkpoint,
    parse_sam_decoder_checkpoint,
    require_matching_base_sam,
)


_WEIGHT_ARTIFACT_KEY_RE = re.compile(r"^[A-Za-z0-9._-]{1,240}$")
LOCATOR_CHECKPOINT_SCHEMA_VERSION = "taxamask_locator_checkpoint_v2"
LOCATOR_ARCHITECTURE_ID = "trait_regressor_unet_wh_v1"


def _checkpoint_locator_scope(value, expected_count):
    if not isinstance(value, (list, tuple)):
        raise ValueError("locator_checkpoint_scope_invalid")
    scope = []
    seen = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("locator_checkpoint_scope_invalid")
        part_name = item.strip()
        if part_name in seen:
            raise ValueError("locator_checkpoint_scope_duplicate")
        seen.add(part_name)
        scope.append(part_name)
    if len(scope) != int(expected_count):
        raise ValueError(
            "locator_checkpoint_scope_count_mismatch:"
            f"expected={int(expected_count)}:observed={len(scope)}"
        )
    return scope


def _fsync_directory(path):
    try:
        descriptor = os.open(os.fspath(path), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


def _atomic_torch_save(payload, path):
    """Write a PyTorch payload without exposing a partial final checkpoint."""

    target = os.path.abspath(os.fspath(path))
    directory = os.path.dirname(target) or "."
    os.makedirs(directory, exist_ok=True)
    temp_path = f"{target}.tmp_{secrets.token_hex(8)}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    descriptor = None
    try:
        descriptor = os.open(temp_path, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = None
            torch.save(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        if os.path.lexists(target):
            raise FileExistsError(f"weight_checkpoint_exists:{os.path.basename(target)}")
        try:
            os.link(temp_path, target, follow_symlinks=False)
        except (NotImplementedError, TypeError):
            os.rename(temp_path, target)
        else:
            os.unlink(temp_path)
        _fsync_directory(directory)
        return target
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        try:
            if os.path.lexists(temp_path):
                os.unlink(temp_path)
        except OSError:
            pass
        raise

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
    def __init__(
        self,
        learning_rate=1e-4,
        weight_decay=1e-4,
        num_classes=None,
        device="auto",
        locator_loss_weights=None,
        weights_dir=None,
        locator_scope=None,
    ):
        self.device_preference = normalize_device_preference(device)
        self.device = resolve_torch_device(device)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_weights_dir = os.path.join(base_dir, "weights")
        self.weights_dir = os.path.abspath(
            os.fspath(default_weights_dir if weights_dir is None else weights_dir)
        )
        if not os.path.exists(self.weights_dir): os.makedirs(self.weights_dir)
        
        if num_classes is None:
            num_classes = len(DEFAULT_LOCATOR_SCOPE)
        self.current_num_classes = num_classes
        self.current_locator_scope = (
            _checkpoint_locator_scope(locator_scope, num_classes)
            if locator_scope is not None
            else []
        )
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.set_locator_loss_weights(locator_loss_weights)
        self.locator_resolution = (512, 512)
        self.loaded_locator_timestamp = None
        self.loaded_locator_reference = ""
        self.loaded_locator_identity = {}
        self.loaded_locator_schema_version = ""
        self.loaded_locator_scope = []
        self.loaded_sam_decoder_reference = ""
        self.loaded_sam_decoder_identity = {}
        self.loaded_locator_requires_legacy_confirmation = False
        self.loaded_locator_is_legacy_512 = False

        # 1. Locator (Now with WH Regression)
        self.locator = None
        self.opt_loc = None
        self._locator_lock = threading.Lock()
        
        # Loss Functions
        self.crit_heatmap = FocalMSELoss() # New Focal-like MSE
        self.crit_wh = nn.SmoothL1Loss(reduction='none') # Robust regression for WH
        
        # 2. SAM
        base_sam_path = os.path.join(self.weights_dir, "sam_b.pt")
        self.base_sam_path = base_sam_path
        self._verified_base_sam_bytes = None
        self.verified_base_sam_identity = {}
        self.base_sam_predictor = None
        self.parts_model = None
        self.opt_parts = None
        self._parts_model_lock = threading.Lock()
        
        self.crit_dice = DiceLoss()
        self.crit_parts = self.crit_dice 
        
        self.cascade_manager = CascadingManager(self)
        
        self.history = {"locator": [], "parts": []}
        self.load_weights()

    @property
    def loss_config_snapshot(self):
        weights = sanitize_loss_weights(
            getattr(self, "_locator_loss_weights", None),
            DEFAULT_LOCATOR_LOSS_WEIGHTS,
        )
        return {"locator": weights}

    def get_loss_config_snapshot(self):
        return self.loss_config_snapshot

    def set_locator_loss_weights(self, loss_weights=None):
        self._locator_loss_weights = sanitize_loss_weights(
            loss_weights,
            DEFAULT_LOCATOR_LOSS_WEIGHTS,
        )
        return self.loss_config_snapshot

    def ensure_locator_loaded(self):
        if not hasattr(self, "_locator_lock"):
            self._locator_lock = threading.Lock()
        with self._locator_lock:
            if self.locator is None:
                self.locator = TraitRegressor(in_channels=3, out_channels=self.current_num_classes).to(self.device)
                self.opt_loc = optim.Adam(self.locator.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
        if self.locator is None:
            raise RuntimeError("Locator model failed to load.")
        return self.locator

    def ensure_parts_model_loaded(self):
        if not hasattr(self, "_parts_model_lock"):
            self._parts_model_lock = threading.Lock()
        with self._parts_model_lock:
            if getattr(self, "parts_model", None) is None:
                try:
                    candidate, optimizer = self._new_parts_runtime()
                except BaseException:
                    self._clear_failed_parts_load()
                    raise
                self.parts_model = candidate
                self.opt_parts = optimizer
                self.loaded_sam_decoder_reference = ""
                self.loaded_sam_decoder_identity = {}
        if self.parts_model is None:
            raise RuntimeError("SAM parts model failed to load.")
        return self.parts_model

    def _new_parts_runtime(self):
        kwargs = {
            "model_path": self.base_sam_path,
            "device": self.device,
        }
        checkpoint_bytes = getattr(self, "_verified_base_sam_bytes", None)
        if checkpoint_bytes is not None:
            kwargs["checkpoint_bytes"] = checkpoint_bytes
        candidate = TrainableSAM(**kwargs)
        trainable_params = [
            parameter
            for parameter in candidate.parameters()
            if parameter.requires_grad
        ]
        if not trainable_params:
            raise ValueError("sam_parts_trainable_parameters_empty")
        optimizer = optim.Adam(
            trainable_params,
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )
        return candidate, optimizer

    def _clear_failed_parts_load(self):
        self.parts_model = None
        self.opt_parts = None
        self.base_sam_predictor = None
        self.loaded_sam_decoder_reference = ""
        self.loaded_sam_decoder_identity = {}

    def configure_verified_base_sam(
        self,
        checkpoint_bytes,
        *,
        reference="",
        fingerprint=None,
    ):
        if not isinstance(checkpoint_bytes, (bytes, bytearray, memoryview)):
            raise TypeError("base_sam_checkpoint_bytes_invalid")
        stable_bytes = bytes(checkpoint_bytes)
        if not stable_bytes:
            raise ValueError("base_sam_checkpoint_bytes_empty")
        observed = {
            "entry_kind": "file",
            "size_bytes": len(stable_bytes),
            "hash_algorithm": "sha256",
            "digest": hashlib.sha256(stable_bytes).hexdigest(),
        }
        if fingerprint is not None:
            if not isinstance(fingerprint, dict):
                raise TypeError("base_sam_fingerprint_invalid")
            keys = ("size_bytes", "hash_algorithm", "digest")
            if any(fingerprint.get(key) != observed[key] for key in keys):
                raise ValueError("base_sam_fingerprint_mismatch")
            if fingerprint.get("entry_kind", "file") != "file":
                raise ValueError("base_sam_fingerprint_mismatch")
        identity = {
            **observed,
            "reference": str(reference or self.base_sam_path),
        }
        if not hasattr(self, "_parts_model_lock"):
            self._parts_model_lock = threading.Lock()
        with self._parts_model_lock:
            self._verified_base_sam_bytes = stable_bytes
            self.verified_base_sam_identity = identity
            self._clear_failed_parts_load()
        return dict(identity)

    def set_device_preference(self, device_preference):
        clean_preference = normalize_device_preference(device_preference)
        new_device = resolve_torch_device(clean_preference)
        if clean_preference == self.device_preference and new_device == self.device:
            return False

        self.device_preference = clean_preference
        self.device = new_device
        if self.locator is not None:
            self.locator.to(self.device)
        if self.parts_model is not None:
            self.parts_model.to(self.device)
            self.parts_model.device = self.device
        self.base_sam_predictor = None

        if self.locator is not None:
            self.opt_loc = optim.Adam(self.locator.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
        else:
            self.opt_loc = None
        if self.parts_model is not None:
            trainable_params = [p for p in self.parts_model.parameters() if p.requires_grad]
            self.opt_parts = optim.Adam(trainable_params, lr=self.learning_rate, weight_decay=self.weight_decay)
        else:
            self.opt_parts = None
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
        self.current_locator_scope = []
        if self.locator is not None:
            self.locator = TraitRegressor(in_channels=3, out_channels=num_classes).to(self.device)
            self.opt_loc = optim.Adam(self.locator.parameters(), lr=learning_rate, weight_decay=weight_decay)
        else:
            self.opt_loc = None
        self.loaded_locator_timestamp = None
        self.loaded_locator_reference = ""
        self.loaded_locator_identity = {}
        self.loaded_locator_schema_version = ""
        self.loaded_locator_scope = []
        self.loaded_locator_requires_legacy_confirmation = False
        self.loaded_locator_is_legacy_512 = False

    def reset_locator_to_base(self):
        print("Resetting Locator to base (untrained) weights...")
        self.locator = TraitRegressor(in_channels=3, out_channels=self.current_num_classes).to(self.device)
        self.opt_loc = optim.Adam(self.locator.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
        self.locator_resolution = (512, 512)
        self.loaded_locator_timestamp = None
        self.loaded_locator_reference = ""
        self.loaded_locator_identity = {}
        self.loaded_locator_schema_version = ""
        self.loaded_locator_scope = []
        self.loaded_locator_requires_legacy_confirmation = False
        self.loaded_locator_is_legacy_512 = False

    def update_hyperparameters(self, learning_rate, weight_decay):
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        if self.opt_loc is not None:
            for param_group in self.opt_loc.param_groups:
                param_group['lr'] = learning_rate
                param_group['weight_decay'] = weight_decay
        if self.opt_parts is not None:
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
        if not hasattr(self, "_parts_model_lock"):
            self._parts_model_lock = threading.Lock()
        with self._parts_model_lock:
            if self.base_sam_predictor is None:
                try:
                    checkpoint_bytes = getattr(
                        self,
                        "_verified_base_sam_bytes",
                        None,
                    )
                    if checkpoint_bytes is None:
                        candidate = SAM(self.base_sam_path)
                    else:
                        candidate = load_sam_from_checkpoint_bytes(
                            self.base_sam_path,
                            checkpoint_bytes,
                        )
                except BaseException:
                    self._clear_failed_parts_load()
                    raise
                self.base_sam_predictor = candidate
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
        parts_model = self.ensure_parts_model_loaded()
        return self._polygon_from_predictor(
            parts_model.ultralytics_sam,
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
        weights = self.loss_config_snapshot["locator"]
        total_loss = weights["heatmap"] * loss_hm + weights["wh"] * loss_wh
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
        """Legacy method: loads models only when a specific timestamp is requested."""
        if timestamp:
            self.load_locator(timestamp)
        if timestamp:
            self.load_sam_decoder(timestamp)

    def _clear_failed_locator_load(self):
        self.locator = None
        self.opt_loc = None
        self.locator_resolution = (512, 512)
        self.loaded_locator_timestamp = None
        self.loaded_locator_reference = ""
        self.loaded_locator_identity = {}
        self.loaded_locator_schema_version = ""
        self.loaded_locator_scope = []
        self.loaded_locator_requires_legacy_confirmation = False
        self.loaded_locator_is_legacy_512 = False

    def _new_locator_load_candidate(self):
        current_locator = getattr(self, "locator", None)
        if current_locator is None or isinstance(current_locator, TraitRegressor):
            candidate = TraitRegressor(
                in_channels=3,
                out_channels=self.current_num_classes,
            )
        else:
            candidate = copy.deepcopy(current_locator)
        return candidate.to(self.device)

    def load_locator(
        self,
        timestamp,
        *,
        checkpoint_path=None,
        checkpoint_bytes=None,
        checkpoint_payload=None,
        require_complete=False,
        expected_locator_scope=None,
    ):
        loc_path = ""
        try:
            suffix = f"_{timestamp}" if timestamp else ""
            loc_path = os.path.abspath(
                checkpoint_path
                or os.path.join(self.weights_dir, f"locator{suffix}.pth")
            )
            weights_root = os.path.abspath(self.weights_dir)
            try:
                inside = os.path.normcase(
                    os.path.commonpath([weights_root, loc_path])
                ) == os.path.normcase(weights_root)
            except ValueError:
                inside = False
            if not inside:
                raise ValueError("locator_checkpoint_outside_managed_model_root")

            if checkpoint_bytes is not None and checkpoint_payload is not None:
                raise ValueError("locator_checkpoint_bytes_ambiguous")
            stable_bytes = None
            stable_payload = (
                checkpoint_bytes
                if checkpoint_bytes is not None
                else checkpoint_payload
            )
            if stable_payload is None:
                if not os.path.isfile(loc_path):
                    raise FileNotFoundError(
                        f"locator_checkpoint_missing:{os.path.basename(loc_path)}"
                    )
                checkpoint_source = loc_path
            else:
                if not isinstance(stable_payload, (bytes, bytearray, memoryview)):
                    raise TypeError("locator_checkpoint_bytes_invalid")
                stable_bytes = bytes(stable_payload)
                if not stable_bytes:
                    raise ValueError("locator_checkpoint_bytes_empty")
                checkpoint_source = io.BytesIO(stable_bytes)

            saved_state = torch.load(
                checkpoint_source,
                map_location=self.device,
                weights_only=True,
            )
            checkpoint_meta = {}
            checkpoint_schema = ""
            if isinstance(saved_state, dict) and "state_dict" in saved_state:
                checkpoint_state = saved_state.get("state_dict")
                if not isinstance(checkpoint_state, dict):
                    raise ValueError("locator_checkpoint_state_invalid")
                raw_meta = saved_state.get("meta")
                if raw_meta is not None and not isinstance(raw_meta, dict):
                    raise ValueError("locator_checkpoint_meta_invalid")
                checkpoint_meta = dict(raw_meta or {})
                checkpoint_schema = str(saved_state.get("schema_version") or "")
            elif isinstance(saved_state, dict):
                checkpoint_state = saved_state
            else:
                raise ValueError("locator_checkpoint_payload_invalid")

            if not checkpoint_state:
                raise ValueError("locator_checkpoint_state_empty")
            if not all(
                isinstance(key, str)
                and isinstance(value, (torch.Tensor, nn.Parameter))
                for key, value in checkpoint_state.items()
            ):
                raise ValueError("locator_checkpoint_state_invalid")

            if (
                require_complete
                and checkpoint_schema != LOCATOR_CHECKPOINT_SCHEMA_VERSION
            ):
                raise ValueError("locator_checkpoint_schema_required")
            if (
                checkpoint_schema
                and checkpoint_schema != LOCATOR_CHECKPOINT_SCHEMA_VERSION
            ):
                raise ValueError(
                    f"locator_checkpoint_schema_unsupported:{checkpoint_schema}"
                )

            saved_scope = []
            if checkpoint_schema == LOCATOR_CHECKPOINT_SCHEMA_VERSION:
                if checkpoint_meta.get("architecture_id") != LOCATOR_ARCHITECTURE_ID:
                    raise ValueError("locator_checkpoint_architecture_mismatch")
                if "num_classes" not in checkpoint_meta:
                    raise ValueError("locator_checkpoint_num_classes_missing")
                saved_scope = _checkpoint_locator_scope(
                    checkpoint_meta.get("locator_scope"),
                    self.current_num_classes,
                )
            if require_complete and expected_locator_scope is None:
                raise ValueError("locator_checkpoint_expected_scope_required")
            if expected_locator_scope is not None:
                expected_scope = _checkpoint_locator_scope(
                    expected_locator_scope,
                    self.current_num_classes,
                )
                if saved_scope and saved_scope != expected_scope:
                    raise ValueError(
                        "locator_checkpoint_scope_mismatch:"
                        f"expected={expected_scope!r}:observed={saved_scope!r}"
                    )

            saved_num_classes = checkpoint_meta.get("num_classes")
            if saved_num_classes is not None:
                try:
                    saved_num_classes = int(saved_num_classes)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        "locator_checkpoint_num_classes_invalid"
                    ) from exc
                if saved_num_classes != int(self.current_num_classes):
                    raise ValueError(
                        "locator_checkpoint_num_classes_mismatch:"
                        f"expected={self.current_num_classes}:"
                        f"observed={saved_num_classes}"
                    )

            output_weight = checkpoint_state.get("outc.conv.weight")
            if output_weight is not None and (
                output_weight.ndim < 1
                or int(output_weight.shape[0]) != int(self.current_num_classes)
            ):
                observed_classes = (
                    int(output_weight.shape[0]) if output_weight.ndim >= 1 else -1
                )
                raise ValueError(
                    "locator_checkpoint_num_classes_mismatch:"
                    f"expected={self.current_num_classes}:"
                    f"observed={observed_classes}"
                )

            candidate = self._new_locator_load_candidate()
            expected_state = candidate.state_dict()
            expected_keys = set(expected_state)
            observed_keys = set(checkpoint_state)
            missing_keys = sorted(expected_keys - observed_keys)
            unexpected_keys = sorted(observed_keys - expected_keys)
            if missing_keys or unexpected_keys:
                details = []
                if missing_keys:
                    details.append(f"missing={','.join(missing_keys[:5])}")
                if unexpected_keys:
                    details.append(
                        f"unexpected={','.join(unexpected_keys[:5])}"
                    )
                raise RuntimeError(
                    "locator_checkpoint_state_mismatch:" + ":".join(details)
                )
            candidate.load_state_dict(checkpoint_state, strict=True)

            saved_resolution = checkpoint_meta.get("locator_size")
            legacy_resolution = checkpoint_meta.get("locator_resolution")
            if saved_resolution is None and legacy_resolution is not None:
                try:
                    legacy_side = max(1, int(legacy_resolution))
                except Exception:
                    legacy_side = 512
                saved_resolution = [legacy_side, legacy_side]

            if saved_resolution is None:
                locator_resolution = (512, 512)
                resolution_fell_back = True
            else:
                try:
                    locator_resolution = (
                        max(1, int(saved_resolution[0])),
                        max(1, int(saved_resolution[1])),
                    )
                    resolution_fell_back = False
                except Exception:
                    locator_resolution = (512, 512)
                    resolution_fell_back = True
            requires_legacy_confirmation = bool(
                not checkpoint_schema or resolution_fell_back
            )
            is_legacy_512 = resolution_fell_back

            optimizer = optim.Adam(
                candidate.parameters(),
                lr=getattr(self, "learning_rate", 1e-4),
                weight_decay=getattr(self, "weight_decay", 1e-4),
            )
            self.locator = candidate
            self.opt_loc = optimizer
            self.locator_resolution = locator_resolution
            self.loaded_locator_requires_legacy_confirmation = (
                requires_legacy_confirmation
            )
            self.loaded_locator_is_legacy_512 = is_legacy_512
            self.loaded_locator_timestamp = timestamp
            self.loaded_locator_reference = os.path.relpath(
                loc_path,
                weights_root,
            ).replace("\\", "/")
            if stable_bytes is None:
                self.loaded_locator_identity = {
                    "source": "path",
                    "reference": self.loaded_locator_reference,
                }
            else:
                self.loaded_locator_identity = {
                    "source": "memory",
                    "reference": self.loaded_locator_reference,
                    "size_bytes": len(stable_bytes),
                    "hash_algorithm": "sha256",
                    "digest": hashlib.sha256(stable_bytes).hexdigest(),
                }
            self.loaded_locator_schema_version = checkpoint_schema
            self.loaded_locator_scope = list(saved_scope)
            if saved_scope:
                self.current_locator_scope = list(saved_scope)
            print(f"Loaded Locator: {os.path.basename(loc_path)}")
        except Exception as exc:
            self._clear_failed_locator_load()
            display_path = loc_path or str(checkpoint_path or "")
            print(f"ERROR loading Locator {display_path}: {exc}")
            raise

    def load_sam_decoder(
        self,
        timestamp,
        *,
        checkpoint_path=None,
        checkpoint_bytes=None,
        checkpoint_payload=None,
        expected_base_sam_fingerprint=None,
        require_base_sam_match=False,
    ):
        sam_path = ""
        try:
            suffix = f"_{timestamp}" if timestamp else ""
            sam_path = os.path.abspath(
                checkpoint_path
                or os.path.join(
                    self.weights_dir,
                    f"sam_decoder_lora{suffix}.pth",
                )
            )
            weights_root = os.path.abspath(self.weights_dir)
            try:
                inside = os.path.normcase(
                    os.path.commonpath([weights_root, sam_path])
                ) == os.path.normcase(weights_root)
            except ValueError:
                inside = False
            if not inside:
                raise ValueError("segmenter_checkpoint_outside_managed_model_root")

            if checkpoint_bytes is not None and checkpoint_payload is not None:
                raise ValueError("sam_decoder_checkpoint_bytes_ambiguous")
            stable_payload = (
                checkpoint_bytes
                if checkpoint_bytes is not None
                else checkpoint_payload
            )
            stable_bytes = None
            if stable_payload is None:
                if not os.path.isfile(sam_path):
                    raise FileNotFoundError(
                        f"sam_decoder_checkpoint_missing:{os.path.basename(sam_path)}"
                    )
                checkpoint_source = sam_path
            else:
                if not isinstance(stable_payload, (bytes, bytearray, memoryview)):
                    raise TypeError("sam_decoder_checkpoint_bytes_invalid")
                stable_bytes = bytes(stable_payload)
                if not stable_bytes:
                    raise ValueError("sam_decoder_checkpoint_bytes_empty")
                checkpoint_source = io.BytesIO(stable_bytes)

            saved_payload = torch.load(
                checkpoint_source,
                map_location=self.device,
                weights_only=True,
            )
            parsed_checkpoint = parse_sam_decoder_checkpoint(
                saved_payload,
                require_bound_base=bool(require_base_sam_match),
            )
            checkpoint_state = parsed_checkpoint["state_dict"]
            checkpoint_base_sam = parsed_checkpoint["base_sam"]
            if checkpoint_base_sam is not None or require_base_sam_match:
                require_matching_base_sam(
                    checkpoint_base_sam,
                    expected_base_sam_fingerprint,
                    getattr(self, "verified_base_sam_identity", None),
                )
            if not isinstance(checkpoint_state, dict):
                raise ValueError("sam_decoder_checkpoint_state_invalid")
            if not checkpoint_state:
                raise ValueError("sam_decoder_checkpoint_state_empty")
            if not all(
                isinstance(key, str)
                and isinstance(value, (torch.Tensor, nn.Parameter))
                for key, value in checkpoint_state.items()
            ):
                raise ValueError("sam_decoder_checkpoint_state_invalid")

            if not hasattr(self, "_parts_model_lock"):
                self._parts_model_lock = threading.Lock()
            with self._parts_model_lock:
                parts_model = getattr(self, "parts_model", None)
                if parts_model is None or getattr(self, "opt_parts", None) is None:
                    parts_model, _base_optimizer = self._new_parts_runtime()
                decoder = parts_model.sam_model.mask_decoder
                expected_state = decoder.state_dict()
                expected_keys = set(expected_state)
                observed_keys = set(checkpoint_state)
                if observed_keys != expected_keys:
                    missing = sorted(expected_keys - observed_keys)
                    unexpected = sorted(observed_keys - expected_keys)
                    raise RuntimeError(
                        "sam_decoder_checkpoint_state_mismatch:"
                        f"missing={missing}:unexpected={unexpected}"
                    )
                for key, expected_value in expected_state.items():
                    observed_value = checkpoint_state[key]
                    if tuple(observed_value.shape) != tuple(expected_value.shape):
                        raise ValueError(
                            "sam_decoder_checkpoint_shape_mismatch:"
                            f"key={key}:expected={tuple(expected_value.shape)}:"
                            f"observed={tuple(observed_value.shape)}"
                        )

                candidate_decoder = copy.deepcopy(decoder)
                candidate_decoder.load_state_dict(checkpoint_state, strict=True)
                candidate_decoder.to(self.device)
                trainable_params = [
                    parameter
                    for parameter in candidate_decoder.parameters()
                    if parameter.requires_grad
                ]
                if not trainable_params:
                    raise ValueError("sam_decoder_trainable_parameters_empty")
                optimizer = optim.Adam(
                    trainable_params,
                    lr=self.learning_rate,
                    weight_decay=self.weight_decay,
                )
                parts_model.sam_model.mask_decoder = candidate_decoder
                self.parts_model = parts_model
                self.opt_parts = optimizer
                reference = os.path.relpath(sam_path, weights_root).replace(
                    "\\",
                    "/",
                )
                self.loaded_sam_decoder_reference = reference
                if stable_bytes is None:
                    self.loaded_sam_decoder_identity = {
                        "source": "path",
                        "reference": reference,
                    }
                else:
                    self.loaded_sam_decoder_identity = {
                        "source": "memory",
                        "reference": reference,
                        "size_bytes": len(stable_bytes),
                        "hash_algorithm": "sha256",
                        "digest": hashlib.sha256(stable_bytes).hexdigest(),
                    }
            print(f"Loaded Segmenter (Fine-tuned): {os.path.basename(sam_path)}")
            return self.parts_model
        except BaseException as exc:
            if not hasattr(self, "_parts_model_lock"):
                self._parts_model_lock = threading.Lock()
            with self._parts_model_lock:
                self._clear_failed_parts_load()
            display_path = sam_path or str(checkpoint_path or "")
            print(f"ERROR loading SAM Decoder {display_path}: {exc}")
            raise

    def reset_sam_to_base(self):
        print("Resetting Segmenter to Base SAM (Original)...")
        if not hasattr(self, "_parts_model_lock"):
            self._parts_model_lock = threading.Lock()
        try:
            with self._parts_model_lock:
                candidate, optimizer = self._new_parts_runtime()
                self.parts_model = candidate
                self.opt_parts = optimizer
                self.loaded_sam_decoder_reference = ""
                self.loaded_sam_decoder_identity = {}
            print("Segmenter reset complete.")
            return self.parts_model
        except BaseException as exc:
            with self._parts_model_lock:
                self._clear_failed_parts_load()
            print(f"Error resetting SAM: {exc}")
            raise

    def reset_to_base_model(self):
        """Resets everything (Locator + SAM)"""
        print("Resetting EVERYTHING to Base...")
        self.reset_locator_to_base()
        self.reset_sam_to_base()

    def save_weights(
        self,
        save_locator=True,
        save_segmenter=True,
        *,
        output_dir=None,
        artifact_key=None,
        locator_scope=None,
    ):
        import datetime

        if artifact_key is None:
            artifact_key = (
                datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                + f"_{secrets.token_hex(4)}"
            )
        artifact_key = str(artifact_key or "").strip()
        if not _WEIGHT_ARTIFACT_KEY_RE.fullmatch(artifact_key):
            raise ValueError("invalid_weight_artifact_key")
        target_dir = os.path.abspath(os.fspath(output_dir or self.weights_dir))
        os.makedirs(target_dir, exist_ok=True)
        locator_path = os.path.join(target_dir, f"locator_{artifact_key}.pth")
        segmenter_path = os.path.join(
            target_dir, f"sam_decoder_lora_{artifact_key}.pth"
        )
        requested_paths = []
        if save_locator:
            requested_paths.append(locator_path)
        if save_segmenter:
            requested_paths.append(segmenter_path)
        if any(os.path.lexists(path) for path in requested_paths):
            raise FileExistsError("weight_checkpoint_exists")
        if save_locator:
            locator = self.ensure_locator_loaded()
            scope = _checkpoint_locator_scope(
                locator_scope
                if locator_scope is not None
                else getattr(self, "current_locator_scope", None),
                self.current_num_classes,
            )
            locator_payload = {
                "schema_version": LOCATOR_CHECKPOINT_SCHEMA_VERSION,
                "state_dict": locator.state_dict(),
                "meta": {
                    "architecture_id": LOCATOR_ARCHITECTURE_ID,
                    "locator_size": [int(self.locator_resolution[0]), int(self.locator_resolution[1])],
                    "locator_resolution": int(self.locator_resolution[0]),
                    "num_classes": int(self.current_num_classes),
                    "locator_scope": list(scope),
                    "loss_config": self.loss_config_snapshot,
                },
            }
            _atomic_torch_save(locator_payload, locator_path)
            self.current_locator_scope = list(scope)
            self.loaded_locator_timestamp = artifact_key
            self.loaded_locator_schema_version = LOCATOR_CHECKPOINT_SCHEMA_VERSION
            self.loaded_locator_scope = list(scope)
            self.loaded_locator_requires_legacy_confirmation = False
            self.loaded_locator_is_legacy_512 = False
        if save_segmenter:
            parts_model = self.ensure_parts_model_loaded()
            _atomic_torch_save(
                build_sam_decoder_checkpoint(
                    parts_model.sam_model.mask_decoder.state_dict(),
                    getattr(self, "verified_base_sam_identity", None),
                ),
                segmenter_path,
            )
        return artifact_key

    def generate_report(self, val_dataloader=None, num_samples=4, training_context=None):
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
            "loss_config": self.loss_config_snapshot,
        }
        if isinstance(training_context, dict) and training_context:
            report_summary_payload["training_context"] = dict(training_context)
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
        model_profile_context=None,
    ):
        from .prediction_pipeline import predict_full_pipeline

        return predict_full_pipeline(
            self,
            image_path,
            current_taxonomy=current_taxonomy,
            locator_scope=locator_scope,
            conf_thresh=conf_thresh,
            adapt_thresh=adapt_thresh,
            box_pad=box_pad,
            noise_floor=noise_floor,
            poly_epsilon=poly_epsilon,
            project_route_manifest=project_route_manifest,
            model_profile_context=model_profile_context,
        )

    def predict_box_pipeline(
        self,
        image_path,
        current_taxonomy=None,
        locator_scope=None,
        conf_thresh=0.1,
        adapt_thresh=0.4,
        box_pad=0.4,
        noise_floor=0.15,
        project_route_manifest=None,
        model_profile_context=None,
    ):
        from .prediction_pipeline import predict_box_pipeline

        return predict_box_pipeline(
            self,
            image_path,
            current_taxonomy=current_taxonomy,
            locator_scope=locator_scope,
            conf_thresh=conf_thresh,
            adapt_thresh=adapt_thresh,
            box_pad=box_pad,
            noise_floor=noise_floor,
            project_route_manifest=project_route_manifest,
            model_profile_context=model_profile_context,
        )
