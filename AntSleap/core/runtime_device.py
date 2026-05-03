import torch


VALID_DEVICE_PREFERENCES = {"auto", "cpu", "cuda"}


def normalize_device_preference(preference=None):
    value = str(preference or "auto").strip().lower()
    return value if value in VALID_DEVICE_PREFERENCES else "auto"


def resolve_torch_device(preference=None):
    preference = normalize_device_preference(preference)
    if preference == "cpu":
        return torch.device("cpu")
    if preference == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    if preference == "cuda":
        return torch.device("cpu")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def resolve_easyocr_gpu(preference=None):
    return resolve_torch_device(preference).type == "cuda"
