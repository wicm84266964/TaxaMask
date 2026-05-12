import json
import os

CONFIG_FILE = "user_config.json"

OBSOLETE_CONFIG_KEYS = (
    "train_split_manifest_path",
    "train_core2_manifest_path",
    "train_allow_random_fallback",
    "inf_enable_cascade_experts",
)

DEFAULT_CONFIG = {
    "language": "en",
    "last_project_path": "",
    "train_epochs": 5,
    "train_batch": 4,
    "blink_train_epochs": 5,
    "blink_train_batch": 2,
    "blink_train_lr": 1e-3,
    "blink_train_weight_decay": 1e-4,
    "blink_train_input_size": 224,
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
    
    # Inference Hyperparameters
    "inf_conf_thresh": 0.1,    # Minimum heatmap peak value (0.0 - 1.0)
    "inf_adapt_thresh": 0.4,   # Threshold relative to peak (e.g. 0.4 * peak)
    "inf_noise_floor": 0.15,   # Absolute minimum threshold to filter noise
    "inf_box_pad": 0.4,        # Box expansion padding ratio
    "inf_poly_epsilon": 2.0,   # Polygon simplification tolerance (pixels)
}

class ConfigManager:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()

    def _drop_obsolete_keys(self):
        for key in OBSOLETE_CONFIG_KEYS:
            self.config.pop(key, None)

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.config.update(data)
            except:
                pass
        self._drop_obsolete_keys()

    def save(self):
        self._drop_obsolete_keys()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
