import torch
import torch.nn as nn
import torchvision.models as models

class MicroExpertLocator(nn.Module):
    """
    基于 Vision Transformer 的微观专家网络 (Transformer Micro-Expert)
    
    设计理念：
    1. 全局视野 (Global Context)：使用 ViT-B/16 作为骨干。与 CNN 不同，ViT 的自注意力机制
       允许网络在处理第一层时就建立图像各个 Patch 之间的全局拓扑关系。
    2. 眨眼算法绝配：在 Outside-View（部位被涂黑）训练时，ViT 能通过周围的解剖结构（如触角、头壳边缘）
       的注意力权重，推断出被遮挡部位的精确物理边界。
    3. 极限回归：抛弃分类头，换上专为极限界框设计的回归头。
    """
    def __init__(self, pretrained=True):
        super().__init__()
        
        # 1. 骨干网络 (Backbone)：加载预训练的 Vision Transformer (Base 架构, 16x16 Patch)
        # ViT-B_16 has 86M parameters and is intended for CUDA-capable GPU runs.
        weights = models.ViT_B_16_Weights.DEFAULT if pretrained else None
        self.vit = models.vit_b_16(weights=weights)
        
        # 2. 定制回归头 (Regression Head)：替换原本的 1000 类分类头
        # ViT-B_16 输出的隐层维度是 768
        self.vit.heads = nn.Sequential(
            nn.Linear(768, 256),
            nn.GELU(),
            nn.Dropout(p=0.1),
            nn.Linear(256, 4),
            nn.Sigmoid() # 强制输出 [cx, cy, w, h] 在 0~1 的相对比例
        )

    def forward(self, x):
        # x: [B, 3, 512, 512] (输入通常会被 resize 到 224 或 512 等 ViT 兼容尺寸)
        # 内部 ViT 会自动将图像切分为 Patch，并加上 Position Embedding
        
        # 输出 bbox: [B, 4] -> [cx, cy, w, h] 比例
        bbox = self.vit(x)
        return bbox

    def _xyxy_to_cxcywh(self, box, img_w, img_h):
        """将绝对坐标 [x1, y1, x2, y2] 转换为相对比例 [cx, cy, w, h]"""
        x1, y1, x2, y2 = box
        w = x2 - x1
        h = y2 - y1
        cx = x1 + w / 2
        cy = y1 + h / 2
        return [cx / img_w, cy / img_h, w / img_w, h / img_h]

    def _cxcywh_to_xyxy(self, cxcywh, img_w, img_h):
        """将模型输出的相对比例转换为绝对坐标"""
        cx, cy, rel_w, rel_h = cxcywh
        abs_cx = cx * img_w
        abs_cy = cy * img_h
        abs_w = rel_w * img_w
        abs_h = rel_h * img_h
        
        x1 = abs_cx - abs_w / 2
        y1 = abs_cy - abs_h / 2
        x2 = abs_cx + abs_w / 2
        y2 = abs_cy + abs_h / 2
        return [x1, y1, x2, y2]
