from ultralytics import SAM
import torch
import numpy as np
import cv2
import os
from PySide6.QtCore import QObject, Signal, QThread, Slot

from .runtime_device import resolve_torch_device

class SAMWorker(QObject):
    """
    Background worker to load SAM model and run inference to avoid freezing UI.
    """
    model_loaded = Signal()
    mask_generated = Signal(list, list) # Returns list of polygon points, AND optional box [x1, y1, x2, y2]
    model_load_error = Signal(str) # New Signal
    prompt_failed = Signal(str)
    
    def __init__(self, model_type="sam_b.pt", poly_epsilon=2.0, device="auto"):
        super().__init__()
        self.model_type = model_type
        self.poly_epsilon = poly_epsilon
        self.device_preference = device
        self.model = None
        self.current_results = None
        
    def set_epsilon(self, epsilon):
        self.poly_epsilon = epsilon
        
    def load_model(self):
        print(f"Loading SAM Model: {self.model_type}...")
        try:
            device = resolve_torch_device(self.device_preference)
            print(f"SAM Worker: Using device: {device}")
            if device.type == 'cuda':
                print(f"  GPU Name: {torch.cuda.get_device_name(0)}")
                
            self.model = SAM(self.model_type)
            # Explicitly move to device (if API supports it, otherwise pass to predict)
            # Ultralytics models usually support .to(device)
            # self.model.to(device) 
            self.device = device
            self._warmup_model(device)
            
            print("SAM Model Loaded.")
            self.model_loaded.emit()
        except Exception as e:
            error_msg = f"Error loading SAM: {e}"
            print(error_msg)
            self.model_load_error.emit(error_msg)

    def _warmup_model(self, device):
        """
        Runs one tiny prompt in the worker thread so the first user-drawn SAM
        box does not pay predictor/device initialization cost on demand.
        """
        if not self.model:
            return
        try:
            dummy = np.zeros((64, 64, 3), dtype=np.uint8)
            self.model.predict(
                dummy,
                bboxes=[[8, 8, 56, 56]],
                verbose=False,
                device=device,
                imgsz=1024,
            )
            if device.type == "cuda":
                torch.cuda.synchronize()
                predictor = getattr(self.model, "predictor", None)
                reset_image = getattr(predictor, "reset_image", None)
                if callable(reset_image):
                    reset_image()
                elif predictor is not None and hasattr(predictor, "features"):
                    predictor.features = None
                torch.cuda.empty_cache()
            print("SAM Worker: Warmup complete.")
        except Exception as exc:
            print(f"SAM Worker: Warmup skipped: {exc}")

    def load_decoder_weights(self, weights_path):
        """
        Loads fine-tuned mask decoder weights.
        """
        if not self.model: return
        try:
            # Access underlying PyTorch model (handle Ultralytics wrapper variations)
            if hasattr(self.model.model, 'model'):
                pt_model = self.model.model.model
            else:
                pt_model = self.model.model
            
            state_dict = torch.load(weights_path, map_location=self.device)
            pt_model.mask_decoder.load_state_dict(state_dict)
            print(f"SAMWorker: Loaded fine-tuned weights from {os.path.basename(weights_path)}")
        except Exception as e:
            print(f"SAMWorker Error loading weights: {e}")

    def reload_base_model(self):
        """
        Reloads the base model to clear any fine-tuning.
        """
        self.load_model() # Re-runs the init load sequence

    @Slot(str, float, float)
    def predict_point(self, image_path, x, y):
        """
        Run SAM inference with a single point prompt.
        """
        if not self.model:
            self.prompt_failed.emit("SAM model is not loaded.")
            return
        try:
            # Ultralytics SAM API
            # points=[[x, y]], labels=[1] (1 for foreground)
            results = self.model.predict(image_path, points=[[x, y]], labels=[1], verbose=False, device=self.device)
            if not self._process_results(results, click_point=(x, y)):
                self.prompt_failed.emit("SAM returned no usable mask.")
        except Exception as e:
            self.prompt_failed.emit(f"SAM point prompt failed: {e}")

    @Slot(str, float, float, float, float)
    def predict_box(self, image_path, x1, y1, x2, y2):
        """
        Run SAM inference with a bounding box prompt.
        """
        if not self.model:
            self.prompt_failed.emit("SAM model is not loaded.")
            return
        try:
            # Ultralytics SAM API uses bboxes=[[x1, y1, x2, y2]]
            results = self.model.predict(image_path, bboxes=[[x1, y1, x2, y2]], verbose=False, device=self.device)
            if not self._process_results(results, prompt_box=[x1, y1, x2, y2]):
                self.prompt_failed.emit("SAM returned no usable mask.")
        except Exception as e:
            self.prompt_failed.emit(f"SAM box prompt failed: {e}")

    def _process_results(self, results, prompt_box=None, click_point=None):
        if results and results[0].masks:
            contours = results[0].masks.xy
            if len(contours) > 0:
                selected_contour = None
                
                if prompt_box:
                    # Filter based on overlap with the prompt box to avoid "flying points"
                    # prompt_box is [x1, y1, x2, y2]
                    bx1, by1, bx2, by2 = prompt_box
                    box_area = (bx2 - bx1) * (by2 - by1)
                    
                    best_score = -1
                    
                    for cnt in contours:
                        if len(cnt) < 3: continue
                        
                        # Calculate bounding rect of the contour
                        cx_min, cy_min = cnt.min(axis=0)
                        cx_max, cy_max = cnt.max(axis=0)
                        
                        # Calculate intersection with prompt box
                        ix1 = max(bx1, cx_min)
                        iy1 = max(by1, cy_min)
                        ix2 = min(bx2, cx_max)
                        iy2 = min(by2, cy_max)
                        
                        inter_w = max(0, ix2 - ix1)
                        inter_h = max(0, iy2 - iy1)
                        intersection_area = inter_w * inter_h
                        
                        # We want the contour that is mostly INSIDE the box, or matches the box best.
                        # Simple metric: Intersection Area. 
                        # (Larger contour inside box = better)
                        if intersection_area > best_score:
                            best_score = intersection_area
                            selected_contour = cnt
                
                elif click_point:
                    # Magic Wand Mode: Find contour containing the point
                    px, py = click_point
                    
                    # 1. Try to find a contour that strictly contains the point
                    containing_contours = []
                    for cnt in contours:
                        # pointPolygonTest returns > 0 if inside, 0 if on edge, < 0 if outside
                        # cnt needs to be float32 for this function usually, but xy output is usually float32 ndarray
                        dist = cv2.pointPolygonTest(cnt.astype(np.float32), (px, py), False)
                        if dist >= 0:
                            containing_contours.append(cnt)
                    
                    if containing_contours:
                        # If multiple contain it (nested?), pick the smallest one usually? 
                        # Or largest? For SAM, usually largest is safer as main object.
                        selected_contour = max(containing_contours, key=lambda x: len(x))
                    else:
                        # 2. If none contain it (maybe clicked just outside), find closest one
                        best_dist = float('inf')
                        for cnt in contours:
                            # Measure distance to contour
                            dist = abs(cv2.pointPolygonTest(cnt.astype(np.float32), (px, py), True))
                            if dist < best_dist:
                                best_dist = dist
                                selected_contour = cnt
                                
                else:
                    # Fallback: Just take the largest contour
                    selected_contour = max(contours, key=lambda x: len(x))

                if selected_contour is not None and len(selected_contour) > 2:
                    # STRICT FILTER: Even the best contour might have a tail that flies out.
                    # If we have a prompt box, we can forcefully clip or filter points that are too far.
                    if prompt_box:
                         bx1, by1, bx2, by2 = prompt_box
                         # Allow a small margin (e.g., 20% expansion) because segmentation is usually better than the box
                         w_b, h_b = bx2 - bx1, by2 - by1
                         margin_x, margin_y = w_b * 0.2, h_b * 0.2
                         limit_x1, limit_y1 = bx1 - margin_x, by1 - margin_y
                         limit_x2, limit_y2 = bx2 + margin_x, by2 + margin_y
                         
                         # Vectorized filtering
                         # Keep points within the expanded box limits
                         mask = (selected_contour[:, 0] >= limit_x1) & (selected_contour[:, 0] <= limit_x2) & \
                                (selected_contour[:, 1] >= limit_y1) & (selected_contour[:, 1] <= limit_y2)
                         
                         filtered_contour = selected_contour[mask]
                         
                         # If filtering broke the contour too much (e.g. split it), we might just fallback 
                         # or if enough points remain, use them. 
                         # Re-calculating convex hull might be too aggressive (loses concavity).
                         # Let's just use the filtered points if they still form a valid shape.
                         if len(filtered_contour) > 2:
                             selected_contour = filtered_contour
                    
                    # Convert to integer numpy array for approxPolyDP
                    poly_np = np.array(selected_contour, dtype=np.int32)
                    
                    # Use the same simplification as the main engine
                    approx = cv2.approxPolyDP(poly_np, self.poly_epsilon, True)
                    
                    # Convert back to list of [x, y] float/int
                    poly_list = [[float(p[0][0]), float(p[0][1])] for p in approx]
                        
                    self.mask_generated.emit(poly_list, prompt_box if prompt_box else [])
                    return True
        return False
