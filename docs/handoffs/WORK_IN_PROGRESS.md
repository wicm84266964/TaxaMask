# Work In Progress & Next Steps (As of 2026-01-05)

This document outlines a critical but unimplemented task discussed today. This is for the next AI assistant to quickly understand the context and continue the work.

---

## 1. The Problem: "Magic Wand" Fails After Fine-tuning

### Symptoms:
- When using the **Base SAM** model, both Box Prompt (框选) and Point Prompt (魔棒) work perfectly.
- After fine-tuning the model (training the SAM Mask Decoder), the **Box Prompt** works as expected, but the **Point Prompt (Magic Wand)** completely fails, producing full-screen noise or chaotic artifacts.

### Root Cause:
- **Catastrophic Forgetting due to Single-Prompt Training.**
- Our current training pipeline (`dataset.py` + `engine.py`) **only feeds Box Prompts** to the `TrainableSAM` model.
- The SAM Mask Decoder is being optimized exclusively for "Box Embedding -> Mask" pairs.
- As a result, the decoder's weights drift and it "forgets" how to correctly interpret the feature distribution from "Point Embeddings". When a Point Prompt is used in inference, the fine-tuned decoder no longer understands the input, leading to catastrophic failure.

---

## 2. The Solution: Mixed Prompt Training

To fix this, the model must be trained to handle both prompt types simultaneously. This involves modifying the training loop to randomly present either a Box or a Point as the prompt for a given training sample.

---

## 3. Actionable Steps for Tomorrow (Implementation Plan)

The goal is to implement **Mixed Prompt Training**. This requires changes in three key files:

### Step 1: Modify `dataset.py` (`TwoStageDataset`)
- The `__getitem__` method (for `mode='parts'`) needs to be updated.
- **Current return**: `img_tensor, box_tensor, mask_tensor`
- **New return**: It should also return a point prompt. The easiest way is to calculate the center of the bounding box.
- **Example modification**:
  ```python
  # In TwoStageDataset.__getitem__ for 'parts' mode
  
  # ... (after box_tensor is created)
  
  # Generate a point prompt from the box center
  x1, y1, x2, y2 = box_tensor.tolist()
  center_x = (x1 + x2) / 2
  center_y = (y1 + y2) / 2
  point_prompt = torch.tensor([[center_x, center_y]], dtype=torch.float32) # Shape: [1, 2]
  point_label = torch.tensor([1], dtype=torch.float32) # 1 = Foreground
  
  # The method should now return both, or alternate.
  # A simple way is to always return both, and let the engine decide which to use.
  return img_tensor, box_tensor, point_prompt, point_label, mask_tensor
  ```
  *(Note: This might require updating the DataLoader logic in `engine.py` to handle the new format.)*

### Step 2: Modify `models/sam_trainable.py` (`TrainableSAM`)
- The `forward` method signature must be updated to accept either `bboxes` or `points` (and `labels`).
- **Current `forward`**: `forward(self, images, bboxes)`
- **New `forward`**: `forward(self, images, bboxes=None, points=None, labels=None)`
- **Internal Logic**:
  ```python
  # In TrainableSAM.forward
  
  # ... (after image_embeddings are generated)
  
  if bboxes is not None:
      # Use box prompt as before
      sparse_embeddings, dense_embeddings = self.sam_model.prompt_encoder(
          points=None,
          boxes=bboxes.unsqueeze(1),
          #...
      )
  elif points is not None:
      # Use point prompt
      sparse_embeddings, dense_embeddings = self.sam_model.prompt_encoder(
          points=(points, labels), # Points are passed as a tuple (coords, labels)
          boxes=None,
          #...
      )
  else:
      raise ValueError("Must provide either bboxes or points")
      
  # ... (rest of the forward pass)
  ```

### Step 3: Modify `core/engine.py` (`AntEngine.train_epoch`)
- This is where the random switching happens.
- In the `train_epoch` loop for the SAM model:
  ```python
  # In AntEngine.train_epoch, where is_sam is True:
  
  # The dataloader now yields: imgs, boxes, points, labels, masks
  for i, batch_data in enumerate(dataloader):
      imgs, boxes, points, labels, masks = batch_data # Adjust to new dataset output
      imgs, boxes, points, labels, masks = imgs.to(self.device), ...
      
      optimizer.zero_grad()
      
      # Randomly choose prompt type for this batch
      if torch.rand(1).item() > 0.5:
          # Use Box Prompt
          pred_masks, _ = model(imgs, bboxes=boxes)
      else:
          # Use Point Prompt
          pred_masks, _ = model(imgs, points=points, labels=labels)
          
      loss = criterion(pred_masks, masks)
      loss.backward()
      optimizer.step()
      # ...
  ```

By implementing these three steps, the fine-tuned model will retain its ability to respond to both box and point prompts, making it universally useful for both automatic and manual annotation tasks.
