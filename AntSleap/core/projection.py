import numpy as np
import cv2


class CoordinateMapper:
    """
    负责处理宏观全局图 (Global) 与 微观局部图 (Local) 之间的坐标重投影计算。
    这是级联专家架构（Cascading Architecture）的数学基础。
    """

    def __init__(self, global_size, crop_box, target_size=(512, 512)):
        """
        :param global_size: (Width, Height) 原始大图的尺寸
        :param crop_box: [x1, y1, x2, y2] 在大图中的裁剪区域（比如一级定位器找到的 Head 框）
        :param target_size: (Width, Height) 局部图被放大到的标准尺寸，默认 512x512
        """
        self.global_w, self.global_h = global_size

        # 关键修复：初始化时就确定“唯一有效裁剪框”，避免映射框与实际裁剪框不一致
        raw = self.sanitize_bbox_xyxy(crop_box)
        clamped = self.clamp_bbox_to_size(raw, self.global_w, self.global_h)

        ix1 = int(np.floor(clamped[0]))
        iy1 = int(np.floor(clamped[1]))
        ix2 = int(np.ceil(clamped[2]))
        iy2 = int(np.ceil(clamped[3]))

        ix1 = max(0, min(ix1, int(self.global_w) - 1))
        iy1 = max(0, min(iy1, int(self.global_h) - 1))
        ix2 = max(ix1 + 1, min(ix2, int(self.global_w)))
        iy2 = max(iy1 + 1, min(iy2, int(self.global_h)))

        self.crop_x1, self.crop_y1 = float(ix1), float(iy1)
        self.crop_x2, self.crop_y2 = float(ix2), float(iy2)

        # 保存整数边界，确保 crop_and_resize 与映射严格一致
        self.crop_ix1, self.crop_iy1 = ix1, iy1
        self.crop_ix2, self.crop_iy2 = ix2, iy2

        self.crop_w = max(1.0, self.crop_x2 - self.crop_x1)
        self.crop_h = max(1.0, self.crop_y2 - self.crop_y1)

        self.target_w, self.target_h = target_size

        # 计算缩放比例：局部图尺寸 / 裁剪出的实际尺寸
        self.scale_x = self.target_w / self.crop_w
        self.scale_y = self.target_h / self.crop_h

    @staticmethod
    def sanitize_bbox_xyxy(bbox):
        """统一处理 [x1,y1,x2,y2] 的顺序和类型。"""
        if bbox is None or len(bbox) != 4:
            return [0.0, 0.0, 1.0, 1.0]
        x1, y1, x2, y2 = [float(v) for v in bbox]
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        return [x1, y1, x2, y2]

    @staticmethod
    def clamp_bbox_to_size(bbox, width, height, min_size=1.0):
        """将框限制在指定尺寸内，并确保有最小面积。"""
        width = max(1.0, float(width))
        height = max(1.0, float(height))
        x1, y1, x2, y2 = CoordinateMapper.sanitize_bbox_xyxy(bbox)

        x1 = max(0.0, min(x1, width - 1.0))
        y1 = max(0.0, min(y1, height - 1.0))
        x2 = max(0.0, min(x2, width))
        y2 = max(0.0, min(y2, height))

        if x2 <= x1:
            x2 = min(width, x1 + float(min_size))
        if y2 <= y1:
            y2 = min(height, y1 + float(min_size))

        return [x1, y1, x2, y2]

    @staticmethod
    def scale_bbox(bbox, src_size, dst_size):
        """将框从 src_size 映射到 dst_size。size 约定: (width, height)。"""
        src_w, src_h = src_size
        dst_w, dst_h = dst_size
        src_w = max(1.0, float(src_w))
        src_h = max(1.0, float(src_h))
        sx = float(dst_w) / src_w
        sy = float(dst_h) / src_h
        x1, y1, x2, y2 = CoordinateMapper.sanitize_bbox_xyxy(bbox)
        return [x1 * sx, y1 * sy, x2 * sx, y2 * sy]

    @staticmethod
    def bbox_to_normalized(bbox, size):
        """将绝对坐标框转换为 0~1 归一化坐标。size 约定: (width, height)。"""
        w, h = size
        clamped = CoordinateMapper.clamp_bbox_to_size(bbox, w, h)
        w = max(1.0, float(w))
        h = max(1.0, float(h))
        x1, y1, x2, y2 = clamped
        norm = [x1 / w, y1 / h, x2 / w, y2 / h]
        return [max(0.0, min(v, 1.0)) for v in norm]

    # --- 1. 单点映射 ---
    def global_to_local(self, x, y):
        """将大图上的坐标点映射到放大后的局部图上"""
        local_x = (x - self.crop_x1) * self.scale_x
        local_y = (y - self.crop_y1) * self.scale_y
        return local_x, local_y

    def local_to_global(self, local_x, local_y):
        """将局部图上的坐标点精准还原到原始大图上"""
        global_x = (local_x / self.scale_x) + self.crop_x1
        global_y = (local_y / self.scale_y) + self.crop_y1
        return global_x, global_y

    # --- 2. Bounding Box 映射 ---
    def bbox_global_to_local(self, bbox):
        """bbox: [x1, y1, x2, y2]"""
        x1, y1, x2, y2 = self.sanitize_bbox_xyxy(bbox)
        lx1, ly1 = self.global_to_local(x1, y1)
        lx2, ly2 = self.global_to_local(x2, y2)
        return self.clamp_bbox_to_size([lx1, ly1, lx2, ly2], self.target_w, self.target_h)

    def bbox_local_to_global(self, local_bbox):
        """将专家在局部图中找到的框，还原为大图坐标"""
        x1, y1, x2, y2 = self.sanitize_bbox_xyxy(local_bbox)
        gx1, gy1 = self.local_to_global(x1, y1)
        gx2, gy2 = self.local_to_global(x2, y2)
        return self.clamp_bbox_to_size([gx1, gy1, gx2, gy2], self.global_w, self.global_h)

    # --- 3. 多边形映射 (供 SAM 精修后的掩码使用) ---
    def poly_global_to_local(self, points):
        """points: [[x1,y1], [x2,y2], ...]"""
        return [list(self.global_to_local(p[0], p[1])) for p in points]

    def poly_local_to_global(self, local_points):
        return [list(self.local_to_global(p[0], p[1])) for p in local_points]

    # --- 4. 图像裁剪工具 ---
    def crop_and_resize(self, image_np):
        """
        根据初始化的裁剪框和目标尺寸，生成高保真的局部图。
        使用 cv2.INTER_CUBIC（双三次插值）以最大程度保留微观纹理。
        """
        # 使用 __init__ 中确定的唯一整数裁剪框，保证和映射公式一一对应
        x1, y1, x2, y2 = self.crop_ix1, self.crop_iy1, self.crop_ix2, self.crop_iy2

        if x2 <= x1 or y2 <= y1:
            return np.zeros((self.target_h, self.target_w, 3), dtype=np.uint8)

        cropped = image_np[y1:y2, x1:x2]
        resized = cv2.resize(cropped, (self.target_w, self.target_h), interpolation=cv2.INTER_CUBIC)
        return resized
