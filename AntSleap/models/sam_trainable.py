import torch
import torch.nn as nn
from ultralytics import SAM
from ultralytics.models.sam import Predictor as SAMPredictor

try:
    from AntSleap.core.runtime_device import resolve_torch_device
except ImportError:
    from core.runtime_device import resolve_torch_device

class TrainableSAM(nn.Module):
    def __init__(self, model_path="weights/sam_b.pt", device='auto'):
        super().__init__()
        self.device = resolve_torch_device(device)
        print(f"Loading Trainable SAM from {model_path}...")
        
        # Load Ultralytics SAM
        # Ultralytics wraps the model in a wrapper. We need to access the underlying torch model.
        # Structure: SAM -> model -> model (MobileSAM/SAM)
        self.ultralytics_sam = SAM(model_path)
        
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
