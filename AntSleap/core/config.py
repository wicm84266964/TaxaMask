import json
import os
import shutil
from copy import deepcopy

from .platform_paths import legacy_repo_config_path, user_config_path

CONFIG_FILE = str(user_config_path())
LEGACY_CONFIG_FILE = str(legacy_repo_config_path())

OBSOLETE_CONFIG_KEYS = (
    "train_split_manifest_path",
    "train_core2_manifest_path",
    "train_allow_random_fallback",
    "inf_enable_cascade_experts",
)

DEFAULT_CONFIG = {
    "language": "en",
    "last_project_path": "",
    "startup_behavior": "start_center", # start_center | continue_last
    "project_autosave_interval_sec": 3,
    "train_epochs": 5,
    "train_batch": 4,
    "blink_train_epochs": 5,
    "blink_train_batch": 2,
    "blink_train_lr": 1e-3,
    "blink_train_weight_decay": 1e-4,
    "blink_train_input_size": 224,
    "blink_auto_shrink_steps": 20,
    "blink_training_strategy": "two_stage_full_then_inside",
    "train_lr": 1e-4,
    "train_weight_decay": 1e-4, # L2 Regularization (Higher = Less Overfitting)
    "train_from_scratch": False, # If True, resets weights before training
    "runtime_device": "auto", # auto | cpu | cuda
    "theme": "dark",
    "known_relocated_roots": [],
    "model_backend": "builtin_locator_sam",
    "external_backend": {
        "backend_id": "custom_external_backend",
        "display_name": "External Script Backend",
        "python_executable": "python",
        "prepare_dataset_command": "",
        "train_command": "",
        "predict_command": "",
        "model_manifest": "",
    },
    "tif_backend": {
        "backend_id": "taxamask_tif_nnunet_v2_backend",
        "display_name": "nnU-Net v2 TIF Region Segmentation",
        "python_executable": "python",
        "prepare_dataset_command": "{python} -m AntSleap.tools.tif_nnunet_v2_backend --contract {contract_json}",
        "train_command": "{python} -m AntSleap.tools.tif_nnunet_v2_backend --contract {contract_json}",
        "predict_command": "{python} -m AntSleap.tools.tif_nnunet_v2_backend --contract {contract_json}",
        "model_manifest": "",
        "export_formats": "ome_tiff,nrrd,mha,nifti",
    },
    "tif_local_axis_backend": {
        "backend_id": "external_local_axis",
        "display_name": "Local Axis Backend",
        "python_executable": "python",
        "prepare_dataset_command": "",
        "train_command": "",
        "predict_command": "",
        "predict_global_roi_command": "",
        "predict_local_frame_command": "",
        "model_manifest": "",
    },
    
    # Inference Hyperparameters
    "inf_conf_thresh": 0.1,    # Minimum heatmap peak value (0.0 - 1.0)
    "inf_adapt_thresh": 0.4,   # Threshold relative to peak (e.g. 0.4 * peak)
    "inf_noise_floor": 0.15,   # Absolute minimum threshold to filter noise
    "inf_box_pad": 0.4,        # Box expansion padding ratio
    "inf_poly_epsilon": 2.0,   # Polygon simplification tolerance (pixels)
}

_TIF_BACKEND_COMMAND_KEYS = (
    "prepare_dataset_command",
    "train_command",
    "predict_command",
)


def _tif_backend_commands_are_empty(config):
    if not isinstance(config, dict):
        return True
    return not any(str(config.get(key) or "").strip() for key in _TIF_BACKEND_COMMAND_KEYS)


def _is_legacy_empty_tif_backend_config(config):
    if not isinstance(config, dict):
        return True
    backend_id = str(config.get("backend_id") or "").strip()
    display_name = str(config.get("display_name") or "").strip()
    legacy_ids = {"", "custom_tif_backend", "taxamask_tif_nnunet_v2_backend"}
    legacy_names = {"", "TIF Volume Backend", "nnU-Net v2 TIF Brain Regions", "nnU-Net v2 TIF Region Segmentation"}
    return backend_id in legacy_ids and display_name in legacy_names and _tif_backend_commands_are_empty(config)


def _default_nnunet_v2_tif_backend_config(python_executable="python"):
    config = deepcopy(DEFAULT_CONFIG["tif_backend"])
    if python_executable:
        config["python_executable"] = str(python_executable)
    return config

class ConfigManager:
    def __init__(self, config_path=None, legacy_config_path=None):
        self.config_path = os.path.abspath(config_path or CONFIG_FILE)
        self.legacy_config_path = os.path.abspath(legacy_config_path or LEGACY_CONFIG_FILE)
        self.config = deepcopy(DEFAULT_CONFIG)
        self.load()

    def _drop_obsolete_keys(self):
        for key in OBSOLETE_CONFIG_KEYS:
            self.config.pop(key, None)

    def _migrate_tif_backend_defaults(self):
        backend = self.config.get("tif_backend")
        if not isinstance(backend, dict):
            self.config["tif_backend"] = _default_nnunet_v2_tif_backend_config()
            return
        if _is_legacy_empty_tif_backend_config(backend):
            python_executable = str(backend.get("python_executable") or DEFAULT_CONFIG["tif_backend"].get("python_executable") or "python")
            self.config["tif_backend"] = _default_nnunet_v2_tif_backend_config(python_executable)

    def _migrate_legacy_config(self):
        if os.path.exists(self.config_path):
            return
        if not self.legacy_config_path or not os.path.exists(self.legacy_config_path):
            return
        if os.path.abspath(self.config_path) == os.path.abspath(self.legacy_config_path):
            return
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        shutil.copy2(self.legacy_config_path, self.config_path)

    def load(self):
        self._migrate_legacy_config()
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.config.update(data)
            except Exception:
                pass
        self._drop_obsolete_keys()
        self._migrate_tif_backend_defaults()

    def save(self):
        self._drop_obsolete_keys()
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
