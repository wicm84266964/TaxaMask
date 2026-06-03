from .cascade_routes import (
    ROUTE_BACKEND_EXTERNAL_BLINK,
    ROUTE_BACKEND_HEATMAP_BLINK,
    ROUTE_BACKEND_VIT_B_BLINK,
)
from .blink_expert_manifest import load_blink_expert_manifest
from .projection import CoordinateMapper

import cv2
import numpy as np
import torch

try:
    from AntSleap.core.blink_heatmap_trainer import HeatmapBlinkNet, normalize_heatmap_input_size
except ImportError:
    from .blink_heatmap_trainer import HeatmapBlinkNet, normalize_heatmap_input_size
try:
    from AntSleap.core.external_blink_backend import ExternalBlinkBackendRunner, sanitize_external_blink_config
except ImportError:
    from .external_blink_backend import ExternalBlinkBackendRunner, sanitize_external_blink_config


class BlinkBackendError(RuntimeError):
    pass


class BlinkExpertBackendRegistry:
    def __init__(self):
        self._backends = {}

    def register(self, backend_id, backend):
        key = str(backend_id or "").strip()
        if not key:
            raise ValueError("blink_backend_id_missing")
        self._backends[key] = backend

    def list_backends(self):
        return sorted(self._backends.keys())

    def get(self, backend_id):
        key = str(backend_id or ROUTE_BACKEND_VIT_B_BLINK).strip() or ROUTE_BACKEND_VIT_B_BLINK
        backend = self._backends.get(key)
        if backend is None:
            raise BlinkBackendError(f"unknown_blink_backend:{key}")
        return backend

    def predict_child_box(self, backend_id, *, manager, image_path, parent_box, child_part_name, parent_part, route_record, context=None):
        backend = self.get(backend_id)
        predict = getattr(backend, "predict_child_box", None)
        if not callable(predict):
            raise BlinkBackendError(f"blink_backend_predict_missing:{backend_id}")
        return predict(
            manager=manager,
            image_path=image_path,
            parent_box=parent_box,
            child_part_name=child_part_name,
            parent_part=parent_part,
            route_record=route_record,
            context=context or {},
        )


class VitBBlinkBackend:
    backend_id = ROUTE_BACKEND_VIT_B_BLINK

    def predict_child_box(self, *, manager, image_path, parent_box, child_part_name, parent_part, route_record, context=None):
        expert_part = str(route_record.get("expert_part") or route_record.get("child") or child_part_name).strip()
        expert_path = manager.resolve_route_expert_path(route_record)
        expert_model = manager._load_expert(expert_part, model_path=expert_path)
        if expert_model is None:
            return None
        return manager._infer_with_loaded_expert(image_path, parent_box, child_part_name, expert_model)


class HeatmapBlinkBackend:
    backend_id = ROUTE_BACKEND_HEATMAP_BLINK

    def predict_child_box(self, *, manager, image_path, parent_box, child_part_name, parent_part, route_record, context=None):
        expert_path = manager.resolve_route_expert_path(route_record)
        model = self._load_model(manager, expert_path, route_record)
        if model is None:
            return None

        img_np = cv2.imread(image_path)
        if img_np is None:
            return None
        img_np = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        src_h, src_w = img_np.shape[:2]

        meta = getattr(model, "_taxamask_meta", {}) if model is not None else {}
        target_size = normalize_heatmap_input_size(meta.get("input_size") or route_record.get("input_size") or 512)
        mapper = CoordinateMapper((src_w, src_h), parent_box, target_size=target_size)
        crop_np = mapper.crop_and_resize(img_np)

        image_tensor = torch.from_numpy(np.ascontiguousarray(crop_np)).permute(2, 0, 1).float() / 255.0
        image_tensor = image_tensor.unsqueeze(0).to(manager.device)

        with torch.no_grad():
            heatmap_logits, wh_pred = model(image_tensor)
            heatmap = torch.sigmoid(heatmap_logits)[0, 0].detach().cpu().numpy()
            wh = wh_pred[0, 0].detach().cpu().numpy()

        flat_idx = int(np.argmax(heatmap))
        peak_y, peak_x = np.unravel_index(flat_idx, heatmap.shape)
        confidence = float(heatmap[peak_y, peak_x])

        target_w, target_h = target_size
        box_w = max(1.0, float(wh[0]) * float(target_w))
        box_h = max(1.0, float(wh[1]) * float(target_h))
        local_box = [
            float(peak_x) - box_w * 0.5,
            float(peak_y) - box_h * 0.5,
            float(peak_x) + box_w * 0.5,
            float(peak_y) + box_h * 0.5,
        ]
        local_box = CoordinateMapper.clamp_bbox_to_size(local_box, target_w, target_h)
        box_w_abs = max(1e-6, float(local_box[2] - local_box[0]))
        box_h_abs = max(1e-6, float(local_box[3] - local_box[1]))
        area_ratio = (box_w_abs * box_h_abs) / float(target_w * target_h)
        if area_ratio < 0.0005:
            return None

        global_box = mapper.bbox_local_to_global(local_box)
        return {
            "box": global_box,
            "confidence": confidence,
            "area_ratio": float(area_ratio),
            "backend": self.backend_id,
        }

    def _load_model(self, manager, expert_path, route_record):
        if not expert_path:
            return None
        cache_key = f"{self.backend_id}:{expert_path}"
        if cache_key in manager.loaded_experts:
            return manager.loaded_experts[cache_key]
        if not expert_path or not torch or not cv2:
            return None
        try:
            loaded = torch.load(expert_path, map_location=manager.device)
        except Exception as exc:
            raise BlinkBackendError(f"heatmap_blink_load_failed:{exc}") from exc

        checkpoint_state = loaded
        checkpoint_meta = {}
        if isinstance(loaded, dict) and isinstance(loaded.get("state_dict"), dict):
            checkpoint_state = loaded.get("state_dict", {})
            checkpoint_meta = loaded.get("meta", {}) if isinstance(loaded.get("meta"), dict) else {}

        manifest_path = str(route_record.get("expert_manifest") or "").strip()
        manifest = load_blink_expert_manifest(manifest_path)
        manifest_input = manifest.get("input_size") if isinstance(manifest, dict) else None
        input_size = normalize_heatmap_input_size(
            manifest_input or checkpoint_meta.get("input_size") or route_record.get("input_size") or 512
        )

        try:
            base_channels = int(checkpoint_meta.get("base_channels", 24))
        except Exception:
            base_channels = 24
        model = HeatmapBlinkNet(base_channels=base_channels).to(manager.device)
        model.load_state_dict(checkpoint_state)
        checkpoint_meta.update(
            {
                "kind": checkpoint_meta.get("kind") or "blink_heatmap_expert",
                "input_size": [int(input_size[0]), int(input_size[1])],
            }
        )
        model._taxamask_meta = checkpoint_meta
        model.eval()
        manager.loaded_experts[cache_key] = model
        return model


class ExternalBlinkBackend:
    backend_id = ROUTE_BACKEND_EXTERNAL_BLINK

    def predict_child_box(self, *, manager, image_path, parent_box, child_part_name, parent_part, route_record, context=None):
        project_manager = getattr(manager, "project_manager", None)
        if project_manager is None:
            raise BlinkBackendError("external_blink_project_manager_missing")

        backend_config = self._resolve_backend_config(project_manager, route_record)
        runner = ExternalBlinkBackendRunner(project_manager, backend_config)
        model_manifest = str(route_record.get("expert_manifest") or backend_config.get("model_manifest") or "").strip()
        summary = runner.run_predict_child(
            image_path=image_path,
            parent_part=parent_part,
            child_part=child_part_name,
            parent_box=parent_box,
            model_manifest=model_manifest,
        )
        result = summary.get("result")
        if isinstance(result, dict):
            result = dict(result)
            result.setdefault("backend", self.backend_id)
            result["contract_json"] = summary.get("contract_json", "")
            result["prediction_json"] = summary.get("prediction_json", "")
            return result
        return None

    def _resolve_backend_config(self, project_manager, route_record):
        route_params = route_record.get("backend_params") if isinstance(route_record, dict) else {}
        if isinstance(route_params, dict) and route_params.get("predict_command"):
            return sanitize_external_blink_config(route_params)

        get_profile = getattr(project_manager, "get_active_model_profile", None)
        profile = get_profile() if callable(get_profile) else {}
        child_defaults = profile.get("child_backend_defaults", {}) if isinstance(profile, dict) and isinstance(profile.get("child_backend_defaults"), dict) else {}
        external_blink = child_defaults.get("external_blink_backend", {}) if isinstance(child_defaults.get("external_blink_backend"), dict) else {}
        return sanitize_external_blink_config(external_blink)


def create_default_blink_backend_registry():
    registry = BlinkExpertBackendRegistry()
    registry.register(ROUTE_BACKEND_VIT_B_BLINK, VitBBlinkBackend())
    registry.register(ROUTE_BACKEND_HEATMAP_BLINK, HeatmapBlinkBackend())
    registry.register(ROUTE_BACKEND_EXTERNAL_BLINK, ExternalBlinkBackend())
    return registry
