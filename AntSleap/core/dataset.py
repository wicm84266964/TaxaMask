import torch
from torch.utils.data import Dataset
from PIL import Image, ImageDraw
import numpy as np
import random
import torchvision.transforms.functional as TF


RESAMPLE_BILINEAR = Image.Resampling.BILINEAR if hasattr(Image, "Resampling") else getattr(Image, "BILINEAR", 2)

class TwoStageDataset(
    Dataset[
        tuple[torch.Tensor, torch.Tensor, torch.Tensor]
        | tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]
    ]
):
    """
    Segmentation Dataset.
    mode: 
        - 'locator': Returns downsampled FULL image + Center Heatmap + WH Targets.
        - 'parts': Returns High-Res ROI (1024x1024) + Box Prompt + Binary Mask (256x256 for SAM Loss).
    """
    def __init__(self, data_list, taxonomy, mode='locator', input_size=(1024, 1024), crop_size=1500):
        self.data = data_list 
        self.taxonomy = taxonomy
        self.mode = mode
        if mode == 'locator':
            if isinstance(input_size, int):
                locator_size = int(input_size)
                self.input_size = (locator_size, locator_size)
            elif isinstance(input_size, (list, tuple)) and len(input_size) >= 2:
                self.input_size = (int(input_size[0]), int(input_size[1]))
            else:
                self.input_size = (512, 512)
        else:
            self.input_size = input_size
        self.crop_size = crop_size
        
        # SAM Mask Output Size is usually 256x256 (1/4 of input)
        self.mask_size = (256, 256) if mode == 'parts' else self.input_size

    def __len__(self):
        return len(self.data)

    def _empty_locator_sample(self):
        num_parts = len(self.taxonomy)
        target_w, target_h = self.input_size
        return (
            torch.zeros((3, target_h, target_w), dtype=torch.float32),
            torch.zeros((num_parts, target_h, target_w), dtype=torch.float32),
            torch.zeros((num_parts, 2), dtype=torch.float32),
            torch.zeros((num_parts,), dtype=torch.float32),
        )

    def __getitem__(self, idx) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor] | tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        img_path, label_data = self.data[idx]
        
        # Backward compatibility: if label_data is just the parts dict (old code/tests)
        if "parts" in label_data:
            parts = label_data["parts"]
            boxes = label_data.get("boxes", {})
        else:
            # Fallback for old style if any
            parts = label_data
            boxes = {}
        
        try:
            img = Image.open(img_path).convert('RGB')
        except:
            if self.mode == 'locator':
                 return self._empty_locator_sample()
            else:
                 return torch.zeros((3, 1024, 1024)), torch.zeros(4), torch.zeros((1, 256, 256))

        w_orig, h_orig = img.size

        if self.mode == 'locator':
            # --- STAGE 1: LOCATOR (Fixed: Letterbox Resize) ---
            target_w, target_h = self.input_size # (512, 512)
            scale = min(target_w / w_orig, target_h / h_orig)
            new_w = int(w_orig * scale)
            new_h = int(h_orig * scale)
            
            img_resized = img.resize((new_w, new_h), RESAMPLE_BILINEAR)
            
            # Create square canvas (black background)
            canvas = Image.new('RGB', self.input_size, (0, 0, 0))
            # Paste in center
            pad_w = (target_w - new_w) // 2
            pad_h = (target_h - new_h) // 2
            canvas.paste(img_resized, (pad_w, pad_h))
            
            img_tensor = TF.to_tensor(canvas)
            
            # Create Multi-channel Heatmap + WH Targets
            num_parts = len(self.taxonomy)
            heatmap = np.zeros((num_parts, target_h, target_w), dtype=np.float32)
            wh_targets = np.zeros((num_parts, 2), dtype=np.float32) # (N, 2)
            valid_parts_mask = np.zeros((num_parts,), dtype=np.float32)
            
            for i, part_name in enumerate(self.taxonomy):
                if part_name in parts and parts[part_name]:
                    valid_parts_mask[i] = 1.0
                    points = parts[part_name]
                    xs = [p[0] for p in points]
                    ys = [p[1] for p in points]
                    cx = sum(xs) / len(xs)
                    cy = sum(ys) / len(ys)
                    
                    # Map center to resize coords
                    cx_r = int(cx * scale + pad_w)
                    cy_r = int(cy * scale + pad_h)
                    
                    # Calculate WH
                    # PRIORITY: Use explicit manual box if available (Better Ground Truth)
                    if part_name in boxes and boxes[part_name]:
                        bx1, by1, bx2, by2 = boxes[part_name]
                        # Map box to resized coords
                        bx1_r = bx1 * scale + pad_w
                        bx2_r = bx2 * scale + pad_w
                        by1_r = by1 * scale + pad_h
                        by2_r = by2 * scale + pad_h
                        
                        w_part = abs(bx2_r - bx1_r)
                        h_part = abs(by2_r - by1_r)
                    else:
                        # Fallback: Bounding box of mask
                        xs_r = [x * scale + pad_w for x in xs]
                        ys_r = [y * scale + pad_h for y in ys]
                        w_part = max(xs_r) - min(xs_r)
                        h_part = max(ys_r) - min(ys_r)
                        
                    # Store Normalized WH (relative to 512x512)
                    wh_targets[i, 0] = w_part / target_w
                    wh_targets[i, 1] = h_part / target_h

                    # --- Dynamic Sigma for Heatmap ---
                    max_dim = max(w_part, h_part)
                    sigma_dynamic = max(5, min(max_dim / 4.0, 60))

                    # Draw Gaussian
                    if 0 <= cx_r < target_w and 0 <= cy_r < target_h:
                        self.generate_gaussian(heatmap[i], cx_r, cy_r, sigma=sigma_dynamic)
            
            return (
                img_tensor,
                torch.from_numpy(heatmap),
                torch.from_numpy(wh_targets),
                torch.from_numpy(valid_parts_mask),
            )

        elif self.mode == 'parts':
            # --- STAGE 2: SAM FINE-TUNING ---
            
            # 1. Find Center for Cropping
            target_part = None 
            available_parts = [p for p in self.taxonomy if p in parts and parts[p]]
            
            if not available_parts:
                return torch.zeros((3, 1024, 1024)), torch.zeros(4), torch.zeros((1, 256, 256))

            target_part_name = random.choice(available_parts)
            target_points = parts[target_part_name]
            
            xs = [p[0] for p in target_points]
            ys = [p[1] for p in target_points]
            center_x = sum(xs) / len(xs)
            center_y = sum(ys) / len(ys)
            
            # Add random jitter to crop center
            jitter = int(self.crop_size * 0.1)
            crop_cx = center_x + random.randint(-jitter, jitter)
            crop_cy = center_y + random.randint(-jitter, jitter)

            # 2. Crop Image
            left = max(0, int(crop_cx - self.crop_size / 2))
            top = max(0, int(crop_cy - self.crop_size / 2))
            right = min(w_orig, int(crop_cx + self.crop_size / 2))
            bottom = min(h_orig, int(crop_cy + self.crop_size / 2))
            
            crop_img = img.crop((left, top, right, bottom))
            img_final = crop_img.resize(self.input_size, RESAMPLE_BILINEAR)

            # 3. Generate Target Mask (Low Res 256x256) & Box
            scale_x = self.mask_size[0] / crop_img.width
            scale_y = self.mask_size[1] / crop_img.height
            
            local_points = []
            for (x, y) in target_points:
                lx = (x - left) * scale_x
                ly = (y - top) * scale_y
                local_points.append((lx, ly))
            
            mask_img = Image.new('L', self.mask_size, 0)
            if len(local_points) > 2:
                ImageDraw.Draw(mask_img).polygon(local_points, outline=1, fill=1)
            
            mask_tensor = torch.from_numpy(np.array(mask_img, dtype=np.uint8)).unsqueeze(0).float()

            # 4. Generate Box Prompt
            rescale_factor = self.input_size[0] / self.mask_size[0] 
            
            pxs = [p[0] * rescale_factor for p in local_points]
            pys = [p[1] * rescale_factor for p in local_points]
            
            if not pxs:
                 return torch.zeros((3, 1024, 1024)), torch.zeros(4), torch.zeros((1, 256, 256))

            min_x, max_x = min(pxs), max(pxs)
            min_y, max_y = min(pys), max(pys)
            
            # Robust Box Generation for Training
            # Inference often uses a padded box (e.g. 1.4x). 
            # We must simulate this during training so SAM learns to handle loose boxes.
            w_box = max_x - min_x
            h_box = max_y - min_y
            
            # Random Padding: 0% to 50% expansion
            pad_w = w_box * random.uniform(0.0, 0.5)
            pad_h = h_box * random.uniform(0.0, 0.5)
            
            # Random Shift: -10% to +10% shift
            shift_x = w_box * random.uniform(-0.1, 0.1)
            shift_y = h_box * random.uniform(-0.1, 0.1)
            
            b_x1 = max(0, min_x - pad_w/2 + shift_x)
            b_y1 = max(0, min_y - pad_h/2 + shift_y)
            b_x2 = min(self.input_size[0], max_x + pad_w/2 + shift_x)
            b_y2 = min(self.input_size[1], max_y + pad_h/2 + shift_y)
            
            # Fallback for empty/invalid boxes
            if b_x2 <= b_x1 or b_y2 <= b_y1:
                b_x1, b_y1 = max(0, min_x - 10), max(0, min_y - 10)
                b_x2, b_y2 = min(self.input_size[0], max_x + 10), min(self.input_size[1], max_y + 10)
            
            box_tensor = torch.tensor([b_x1, b_y1, b_x2, b_y2], dtype=torch.float32)

            img_tensor = TF.to_tensor(img_final) 
            img_tensor = TF.normalize(img_tensor, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            
            return img_tensor, box_tensor, mask_tensor

        raise ValueError(f"Unsupported dataset mode: {self.mode}")


    def generate_gaussian(self, heatmap, cx, cy, sigma=3):
        h, w = heatmap.shape
        size = int(6 * sigma)
        x_min, x_max = max(0, cx - size), min(w, cx + size)
        y_min, y_max = max(0, cy - size), min(h, cy + size)
        y_grid, x_grid = np.ogrid[y_min:y_max, x_min:x_max]
        g = np.exp(-((x_grid - cx)**2 + (y_grid - cy)**2) / (2 * sigma**2))
        heatmap[y_min:y_max, x_min:x_max] = np.maximum(heatmap[y_min:y_max, x_min:x_max], g)
