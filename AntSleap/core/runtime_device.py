try:
    import torch
except ModuleNotFoundError:
    torch = None


VALID_DEVICE_PREFERENCES = {"auto", "cpu", "cuda"}


class FallbackDevice:
    def __init__(self, device_type="cpu"):
        self.type = device_type

    def __str__(self):
        return self.type

    def __repr__(self):
        return self.type


def _device(device_type):
    if torch is not None:
        return torch.device(device_type)
    return FallbackDevice("cpu")


def normalize_device_preference(preference=None):
    value = str(preference or "auto").strip().lower()
    return value if value in VALID_DEVICE_PREFERENCES else "auto"


def resolve_torch_device(preference=None):
    preference = normalize_device_preference(preference)
    if preference == "cpu":
        return _device("cpu")
    if torch is not None and preference == "cuda" and torch.cuda.is_available():
        return _device("cuda")
    if preference == "cuda":
        return _device("cpu")
    if torch is not None and torch.cuda.is_available():
        return _device("cuda")
    return _device("cpu")


def resolve_easyocr_gpu(preference=None):
    return resolve_torch_device(preference).type == "cuda"
