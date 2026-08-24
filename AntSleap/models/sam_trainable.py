import hashlib
import io
from pathlib import Path

import torch
import torch.nn as nn
from ultralytics import SAM
from ultralytics.models.sam import Predictor as SAMPredictor

try:
    from AntSleap.core.runtime_device import resolve_torch_device
except ImportError:
    from core.runtime_device import resolve_torch_device


def _checkpoint_payload_from_bytes(checkpoint_bytes):
    buffer = io.BytesIO(checkpoint_bytes)
    try:
        return torch.load(buffer, map_location="cpu", weights_only=True)
    except TypeError as exc:
        message = str(exc).lower()
        if "weights_only" not in message or "unexpected keyword" not in message:
            raise
        buffer.seek(0)
        return torch.load(buffer, map_location="cpu")


def _build_sam_model_from_bytes(model_path, checkpoint_bytes):
    from ultralytics.models.sam.build import sam_model_map

    model_name = Path(str(model_path)).name.lower()
    matches = [
        (str(name), builder)
        for name, builder in sam_model_map.items()
        if model_name.endswith(str(name).lower())
    ]
    if not matches:
        raise FileNotFoundError(
            f"sam_checkpoint_variant_unsupported:{model_name}"
        )
    _name, builder = max(matches, key=lambda item: len(item[0]))
    sam_model = builder(None)
    state_dict = _checkpoint_payload_from_bytes(checkpoint_bytes)
    if (
        isinstance(state_dict, dict)
        and "model" in state_dict
        and isinstance(state_dict["model"], dict)
    ):
        state_dict = state_dict["model"]
    if not isinstance(state_dict, dict) or not state_dict:
        raise ValueError("sam_checkpoint_state_invalid")
    sam_model.load_state_dict(state_dict, strict=True)
    sam_model.eval()
    return sam_model


class _MemoryLoadedSAM(SAM):
    """Ultralytics SAM wrapper whose loader consumes immutable checkpoint bytes."""

    def __init__(self, model_path, checkpoint_bytes):
        self._checkpoint_bytes = checkpoint_bytes
        try:
            super().__init__(str(model_path))
        finally:
            self._checkpoint_bytes = None

    def _load(self, weights, task=None):
        del task
        self.model = _build_sam_model_from_bytes(
            weights,
            self._checkpoint_bytes,
        )


def load_sam_from_checkpoint_bytes(model_path, checkpoint_bytes):
    """Construct an Ultralytics SAM wrapper without reopening a checkpoint path."""

    if not isinstance(checkpoint_bytes, (bytes, bytearray, memoryview)):
        raise TypeError("sam_checkpoint_bytes_invalid")
    stable_bytes = bytes(checkpoint_bytes)
    if not stable_bytes:
        raise ValueError("sam_checkpoint_bytes_empty")
    return _MemoryLoadedSAM(model_path, stable_bytes)


class TrainableSAM(nn.Module):
    def __init__(
        self,
        model_path="weights/sam_b.pt",
        device="auto",
        checkpoint_bytes=None,
    ):
        super().__init__()
        self.device = resolve_torch_device(device)
        print(f"Loading Trainable SAM from {model_path}...")

        if checkpoint_bytes is None:
            self.loaded_checkpoint_identity = {
                "source": "path",
                "path": str(model_path),
            }
            self.ultralytics_sam = SAM(model_path)
        else:
            if not isinstance(checkpoint_bytes, (bytes, bytearray, memoryview)):
                raise TypeError("sam_checkpoint_bytes_invalid")
            stable_bytes = bytes(checkpoint_bytes)
            if not stable_bytes:
                raise ValueError("sam_checkpoint_bytes_empty")
            self.loaded_checkpoint_identity = {
                "source": "memory",
                "path": str(model_path),
                "size_bytes": len(stable_bytes),
                "hash_algorithm": "sha256",
                "digest": hashlib.sha256(stable_bytes).hexdigest(),
            }
            self.ultralytics_sam = load_sam_from_checkpoint_bytes(
                model_path,
                stable_bytes,
            )

        # Load Ultralytics SAM
        # Ultralytics wraps the model in a wrapper. We need to access the underlying torch model.
        # Structure: SAM -> model -> model (MobileSAM/SAM)

        # Access core PyTorch module - Robust handling for different Ultralytics versions
        if hasattr(self.ultralytics_sam.model, 'model'):
            self.sam_model = self.ultralytics_sam.model.model 
        else:
            self.sam_model = self.ultralytics_sam.model
            
        self.sam_model.to(self.device)
        
        # Freeze Image Encoder (ViT) - This is the heavy part
        for param in self.sam_model.image_encoder.parameters():
            param.requires_grad = False
            
        # Freeze Prompt Encoder
        for param in self.sam_model.prompt_encoder.parameters():
            param.requires_grad = False
            
        # Unfreeze Mask Decoder (We train this!)
        for param in self.sam_model.mask_decoder.parameters():
            param.requires_grad = True
            
        print("SAM Image Encoder & Prompt Encoder -> FROZEN.")
        print("SAM Mask Decoder -> TRAINABLE.")

    def forward(self, images, bboxes):
        """
        Custom forward pass for training.
        images: [B, 3, 1024, 1024] - Normalized tensor
        bboxes: [B, 4] - Box prompts corresponding to the object (x1, y1, x2, y2)
        """
        # DEBUG: Print shapes
        # print(f"DEBUG: Input Images: {images.shape}, BBoxes: {bboxes.shape}")
        
        # 1. Image Encoder (Frozen)
        # Returns image embeddings
        with torch.no_grad():
            image_embeddings = self.sam_model.image_encoder(images)
            # print(f"DEBUG: Image Embeddings: {image_embeddings.shape}")

        # 2. Prompt Encoder (Frozen)
        # Process boxes: SAM expects boxes to be un-normalized (pixels)
        # Ultralytics/SAM logic usually expects boxes in [B, N, 4] format.
        
        sparse_embeddings, dense_embeddings = self.sam_model.prompt_encoder(
            points=None,
            boxes=bboxes.unsqueeze(1), # [B, 1, 4]
            masks=None,
        )
        # print(f"DEBUG: Sparse Emb: {sparse_embeddings.shape}, Dense Emb: {dense_embeddings.shape}")

        # 3. Mask Decoder (Trainable)
        # Returns: low_res_masks, iou_predictions
        low_res_masks, iou_preds = self.sam_model.mask_decoder(
            image_embeddings=image_embeddings,
            image_pe=self.sam_model.prompt_encoder.get_dense_pe(),
            sparse_prompt_embeddings=sparse_embeddings,
            dense_prompt_embeddings=dense_embeddings,
            multimask_output=False, # We only want the best mask
        )

        return low_res_masks, iou_preds
