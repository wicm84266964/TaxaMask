# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

import os
import json
import torch
import cv2

from .projection import CoordinateMapper
from .cascade_routes import (
    LEGACY_EXPERT_FILENAME,
    build_expert_id,
    format_expert_label,
    parse_expert_id,
    route_manifest_has_routes,
    sanitize_legacy_route_manifest,
    sanitize_project_route_manifest,
)
from .expert_notes import load_expert_notes
try:
    from AntSleap.models.expert_networks import MicroExpertLocator
except ImportError:
    from models.expert_networks import MicroExpertLocator

class CascadingManager:
    """
    级联推理骨架 (Cascade Inference Scaffold)
    
    用于前期验证阶段：展示大模型与微观专家 (Transformer) 的接力工作流。
    未来将对接真实的 anatomy_tree.json 进行动态路由。
    """
    def __init__(self, main_engine):
        self.engine = main_engine
        self.device = main_engine.device
        
        # 缓存已加载的专家模型，避免重复加载
        self.loaded_experts = {}
        self.expert_dir = os.path.join(main_engine.weights_dir, "experts")
        self.route_manifest_path = os.path.join(self.expert_dir, "cascade_routes.json")
        self.legacy_route_manifest = {
            "version": "",
            "approved": False,
            "routes": [],
        }
        self.load_routes()

    def load_routes(self, route_manifest_path=None):
        """加载专家路由合同。未配置或未批准时返回默认关闭态。"""
        path = route_manifest_path or self.route_manifest_path
        self.route_manifest_path = path

        if not os.path.exists(path):
            self.legacy_route_manifest = {"version": "", "approved": False, "routes": []}
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            self.legacy_route_manifest = {"version": "", "approved": False, "routes": []}
            return False

        self.legacy_route_manifest = sanitize_legacy_route_manifest(raw)
        return self.routes_ready()

    def routes_ready(self, route_manifest=None):
        manifest = route_manifest if isinstance(route_manifest, dict) else self.legacy_route_manifest
        routes = manifest.get("routes", []) if isinstance(manifest, dict) else []
        if not isinstance(routes, list):
            return False
        return any(bool(route.get("enabled", False)) for route in routes if isinstance(route, dict))

    def get_runtime_route_manifest(self, project_route_manifest=None):
        project_manifest = sanitize_project_route_manifest(project_route_manifest or {})
        if route_manifest_has_routes(project_manifest):
            return project_manifest
        return {
            "version": self.legacy_route_manifest.get("version", ""),
            "routes": [dict(route) for route in self.legacy_route_manifest.get("routes", [])],
        }

    def _find_route(self, parent_part, child_part_name, route_manifest=None):
        manifest = self.get_runtime_route_manifest(route_manifest)
        if not self.routes_ready(manifest):
            return None

        parent_part = str(parent_part or "").strip()
        child_part_name = str(child_part_name or "").strip()
        if not parent_part or not child_part_name:
            return None

        route_list = manifest.get("routes", [])
        if not isinstance(route_list, list):
            return None

        for route in route_list:
            if not isinstance(route, dict):
                continue
            if not bool(route.get("enabled", False)):
                continue
            route_parent = route.get("parent", "")
            route_child = route.get("child", "")
            if route_parent == parent_part and route_child == child_part_name:
                return route
        return None

    def resolve_route_for_child(self, child_part_name, available_parents, route_manifest=None):
        manifest = self.get_runtime_route_manifest(route_manifest)
        if not self.routes_ready(manifest):
            return None

        child_part_name = str(child_part_name or "").strip()
        if not child_part_name:
            return None

        available = [str(part).strip() for part in available_parents or [] if str(part).strip()]
        if not available:
            return None

        route_list = manifest.get("routes", [])
        for route in route_list:
            if not isinstance(route, dict):
                continue
            if not bool(route.get("enabled", False)):
                continue
            route_child = str(route.get("child", "")).strip()
            if route_child != child_part_name:
                continue
            route_parent = str(route.get("parent", "")).strip()
            if route_parent in available:
                return route
        return None

    def can_override(self, parent_part, child_part_name, route_manifest=None):
        return self._find_route(parent_part, child_part_name, route_manifest=route_manifest) is not None

    def get_route_min_conf(self, parent_part, child_part_name, route_manifest=None):
        route = self._find_route(parent_part, child_part_name, route_manifest=route_manifest)
        if not route:
            return None
        min_conf = route.get("min_conf", None)
        if isinstance(min_conf, (int, float)):
            return float(min_conf)
        return None

    def describe_route(self, route):
        if not isinstance(route, dict):
            return "unknown-route"
        parent = str(route.get("parent") or "?").strip() or "?"
        child = str(route.get("child") or "?").strip() or "?"
        expert_label = format_expert_label(route)
        return f"{parent}->{child} [{expert_label}]"

    def route_has_explicit_expert(self, route):
        if not isinstance(route, dict):
            return False
        return bool(route.get("expert_id") or route.get("expert_part") or route.get("expert_filename"))

    def resolve_route_expert_path(self, route):
        if not isinstance(route, dict):
            return None

        expert_id = route.get("expert_id")
        expert_part, expert_filename = parse_expert_id(expert_id)
        if not expert_part:
            raw_part = route.get("expert_part") or route.get("expert_name")
            if isinstance(raw_part, str) and raw_part.strip():
                expert_part = raw_part.strip()
        if not expert_filename:
            raw_filename = route.get("expert_filename")
            if isinstance(raw_filename, str) and raw_filename.strip():
                expert_filename = os.path.basename(raw_filename.strip())

        is_legacy_route = str(route.get("registration_source") or "") == "legacy_global_manifest"
        if is_legacy_route:
            if not expert_part:
                expert_part = str(route.get("child") or "").strip()
            if not expert_filename:
                expert_filename = LEGACY_EXPERT_FILENAME

        if not expert_part or not expert_filename:
            return None
        return os.path.join(self.expert_dir, expert_part, expert_filename)

    def get_route_block_reason(self, route):
        if not isinstance(route, dict):
            return "route_missing"
        is_legacy_route = str(route.get("registration_source") or "") == "legacy_global_manifest"
        if not is_legacy_route and not self.route_has_explicit_expert(route):
            return "expert_unappointed"
        route_path = self.resolve_route_expert_path(route)
        if not route_path:
            return "expert_unappointed" if not is_legacy_route else "expert_model_missing"
        if not os.path.exists(route_path):
            return "expert_model_missing"
        return None

    def route_is_usable(self, route):
        return self.get_route_block_reason(route) is None

    def list_available_experts(self):
        experts = []
        if not os.path.exists(self.expert_dir):
            return experts
        expert_notes = load_expert_notes(self.engine.weights_dir)

        for part_folder in sorted(os.listdir(self.expert_dir)):
            part_path = os.path.join(self.expert_dir, part_folder)
            if not os.path.isdir(part_path):
                continue
            for filename in sorted(os.listdir(part_path)):
                if not filename.lower().endswith(".pth"):
                    continue
                expert_id = build_expert_id(part_folder, filename)
                if not expert_id:
                    continue
                experts.append(
                    {
                        "expert_part": part_folder,
                        "expert_filename": filename,
                        "expert_id": expert_id,
                        "path": os.path.join(part_path, filename),
                        "note": expert_notes.get(expert_id, ""),
                    }
                )
        return experts
         
    def _load_expert(self, part_name, model_path=None):
        """懒加载：需要时才把对应的 Transformer 专家拉进显存"""
        cache_key = str(model_path or part_name or "").strip()
        if cache_key in self.loaded_experts:
            return self.loaded_experts[cache_key]
             
        if model_path is None:
            return None
        if not os.path.exists(model_path):
            return None
             
        print(f"Loading Micro-Expert for [{part_name}] from {model_path}...")
        loaded = torch.load(model_path, map_location=self.device)
        checkpoint_state = loaded
        checkpoint_meta = {}
        if isinstance(loaded, dict) and isinstance(loaded.get("state_dict"), dict):
            checkpoint_state = loaded.get("state_dict", {})
            checkpoint_meta = loaded.get("meta", {}) if isinstance(loaded.get("meta"), dict) else {}
        input_size = checkpoint_meta.get("input_size") or [224, 224]
        try:
            input_side = int(input_size[0] if isinstance(input_size, (list, tuple)) else input_size)
        except Exception:
            input_side = 224
        expert_model = MicroExpertLocator(pretrained=False, image_size=input_side).to(self.device)
        expert_model.load_state_dict(checkpoint_state)
        expert_model._taxamask_meta = checkpoint_meta
        expert_model.eval()
         
        self.loaded_experts[cache_key] = expert_model
        return expert_model

    def _infer_with_loaded_expert(self, image_path, parent_box, child_part_name, expert_model):
        if expert_model is None:
            return None

        img_np = cv2.imread(image_path)
        if img_np is None:
            return None
        img_np = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        h, w, _ = img_np.shape

        meta = getattr(expert_model, "_taxamask_meta", {}) if expert_model is not None else {}
        input_size = meta.get("input_size") if isinstance(meta, dict) else None
        try:
            input_side = int(input_size[0] if isinstance(input_size, (list, tuple)) else input_size)
        except Exception:
            input_side = int(getattr(expert_model, "image_size", 224) or 224)
        target_size = (input_side, input_side)
        mapper = CoordinateMapper((w, h), parent_box, target_size=target_size)
        zoomed_img_np = mapper.crop_and_resize(img_np)

        img_tensor = torch.from_numpy(zoomed_img_np).permute(2, 0, 1).float() / 255.0
        img_tensor = img_tensor.unsqueeze(0).to(self.device)

        with torch.no_grad():
            preds_cxcywh_rel = expert_model(img_tensor)[0]
            preds_rel = preds_cxcywh_rel.cpu().numpy()

        local_box = expert_model._cxcywh_to_xyxy(preds_rel, target_size[0], target_size[1])
        local_box = CoordinateMapper.clamp_bbox_to_size(local_box, target_size[0], target_size[1])

        box_w = max(1e-6, float(local_box[2] - local_box[0]))
        box_h = max(1e-6, float(local_box[3] - local_box[1]))
        area_ratio = (box_w * box_h) / float(target_size[0] * target_size[1])
        if area_ratio < 0.002:
            return None

        confidence = 1.0
        global_box = mapper.bbox_local_to_global(local_box)

        print(
            f"Cascading Success: Found {child_part_name} at global coords {global_box} "
            f"(conf={confidence:.3f}, area_ratio={area_ratio:.3f})"
        )
        return {
            "box": global_box,
            "confidence": confidence,
            "area_ratio": float(area_ratio),
        }

    def infer_legacy_expert_in_parent_box(self, image_path, parent_box, child_part_name):
        legacy_path = os.path.join(self.expert_dir, child_part_name, LEGACY_EXPERT_FILENAME)
        expert_model = self._load_expert(child_part_name, model_path=legacy_path)
        if expert_model is None:
            print(f"Legacy expert model for {child_part_name} not found. Skipping.")
            return None
        return self._infer_with_loaded_expert(image_path, parent_box, child_part_name, expert_model)

    def run_cascading_inference(self, image_path, parent_part="Head", child_part="Mandible", parent_box=None, route_manifest=None):
        """
        验证逻辑：
        1. 获取父节点的框 (模拟大模型输出)
        2. 裁剪放大
        3. 专家推理
        4. 坐标回传
        """
        # 注意：这里我们为了简化测试，假设父节点已经被识别，
        # 在真实应用中，这一步应该调用 self.engine.locator.predict() 获取。
        # 这里我们假定 project 已经有了 Head 的手动框或者机器框作为父节点。
        
        # 为了避免循环依赖，这里默认由调用方直接提供 parent_box
        if parent_box is None:
            print(
                f"Cascade Scaffold: missing parent_box for parent={parent_part}, child={child_part}. "
                "Call infer_child_part() directly with a valid parent_box."
            )
            return None

        return self.infer_child_part(
            image_path=image_path,
            parent_box=parent_box,
            child_part_name=child_part,
            parent_part=parent_part,
            route_manifest=route_manifest,
        )
         
    def infer_child_part(self, image_path, parent_box, child_part_name, parent_part="macro_locator", route_manifest=None):
        """
        核心接力函数：在大图的 parent_box 中，寻找 child_part。
        返回：全局坐标下的 [x1, y1, x2, y2]
        """
        route = self._find_route(parent_part, child_part_name, route_manifest=route_manifest)
        if route is None:
            return None

        expert_part = str(route.get("expert_part") or route.get("child") or child_part_name).strip()
        expert_path = self.resolve_route_expert_path(route)
        expert_model = self._load_expert(expert_part, model_path=expert_path)
        if expert_model is None:
            print(f"Expert model for {child_part_name} not found. Skipping.")
            return None

        return self._infer_with_loaded_expert(image_path, parent_box, child_part_name, expert_model)
