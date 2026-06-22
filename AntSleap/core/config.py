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
    "blink_training_strategy": "triview_random",
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
        "backend_id": "custom_tif_backend",
        "display_name": "TIF Volume Backend",
        "python_executable": "python",
        "prepare_dataset_command": "",
        "train_command": "",
        "predict_command": "",
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

class ConfigManager:
    def __init__(self, config_path=None, legacy_config_path=None):
        self.config_path = os.path.abspath(config_path or CONFIG_FILE)
        self.legacy_config_path = os.path.abspath(legacy_config_path or LEGACY_CONFIG_FILE)
        self.config = deepcopy(DEFAULT_CONFIG)
        self.load()

    def _drop_obsolete_keys(self):
        for key in OBSOLETE_CONFIG_KEYS:
            self.config.pop(key, None)

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

    def save(self):
        self._drop_obsolete_keys()
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
