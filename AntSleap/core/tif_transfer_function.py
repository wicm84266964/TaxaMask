"""Transfer-function presets for TIF/CT volume rendering."""

from __future__ import annotations

import copy

import numpy as np


TIF_TRANSFER_FUNCTION_SCHEMA_VERSION = "taxamask_tif_transfer_function_v1"
DEFAULT_TRANSFER_LUT_SIZE = 256
TRANSFER_PRESET_IDS = ("amber", "cyan", "white", "custom", "morphology", "publication")


def _rgb01(value, fallback=(1.0, 0.83, 0.30)):
    try:
        rgb = tuple(float(channel) for channel in value)
    except (TypeError, ValueError):
        rgb = tuple(float(channel) for channel in fallback)
    if len(rgb) != 3:
        rgb = tuple(float(channel) for channel in fallback)
    return tuple(max(0.0, min(1.0, channel)) for channel in rgb)


def _hex_to_rgb01(value, fallback=(1.0, 0.83, 0.30)):
    text = str(value or "").strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        return _rgb01(fallback)
    try:
        return tuple(int(text[index : index + 2], 16) / 255.0 for index in (0, 2, 4))
    except ValueError:
        return _rgb01(fallback)


def _rgb01_to_hex(rgb):
    clean = _rgb01(rgb)
    return "#" + "".join(f"{int(round(channel * 255.0)):02X}" for channel in clean)


def _smoothstep(values):
    values = np.clip(values, 0.0, 1.0)
    return values * values * (3.0 - 2.0 * values)


def _interp_points(density, points):
    clean = sorted((float(x), float(y)) for x, y in points)
    xs = np.asarray([x for x, _ in clean], dtype=np.float32)
    ys = np.asarray([y for _, y in clean], dtype=np.float32)
    return np.interp(density, xs, ys).astype(np.float32)


def _interp_color_points(density, points):
    clean = sorted((float(x), _hex_to_rgb01(color)) for x, color in points)
    xs = np.asarray([x for x, _ in clean], dtype=np.float32)
    colors = np.asarray([rgb for _, rgb in clean], dtype=np.float32)
    channels = [np.interp(density, xs, colors[:, index]) for index in range(3)]
    return np.stack(channels, axis=1).astype(np.float32)


def builtin_transfer_function(preset="amber", tint_rgb=(1.0, 0.83, 0.30)):
    preset_id = str(preset or "amber").lower()
    tint = _rgb01(tint_rgb)
    if preset_id == "cyan":
        color_points = [(0.0, "#0D4775"), (0.42, "#4DE0F5"), (1.0, "#D6FFFA")]
        opacity_points = [(0.0, 0.0), (0.08, 0.0), (0.42, 0.34), (1.0, 0.86)]
    elif preset_id == "white":
        color_points = [(0.0, "#1A1F21"), (0.42, "#A3ADAA"), (1.0, "#FFFBE0")]
        opacity_points = [(0.0, 0.0), (0.08, 0.0), (0.42, 0.34), (1.0, 0.86)]
    elif preset_id == "custom":
        low = _rgb01_to_hex(tuple(channel * 0.18 for channel in tint))
        mid = _rgb01_to_hex(tuple(min(1.0, channel * 0.72 + extra) for channel, extra in zip(tint, (0.08, 0.10, 0.12))))
        high = _rgb01_to_hex(tuple(min(1.0, channel * 1.08 + extra) for channel, extra in zip(tint, (0.12, 0.10, 0.04))))
        color_points = [(0.0, low), (0.42, mid), (1.0, high)]
        opacity_points = [(0.0, 0.0), (0.08, 0.0), (0.42, 0.34), (1.0, 0.86)]
    elif preset_id == "morphology":
        color_points = [(0.0, "#030506"), (0.18, "#293D42"), (0.48, "#9CB8A6"), (0.78, "#DDB968"), (1.0, "#FFF1B8")]
        opacity_points = [(0.0, 0.0), (0.05, 0.0), (0.18, 0.10), (0.42, 0.42), (0.78, 0.76), (1.0, 0.94)]
    elif preset_id == "publication":
        color_points = [(0.0, "#050403"), (0.20, "#45382A"), (0.55, "#C78B38"), (0.82, "#FFE1A1"), (1.0, "#FFFFFF")]
        opacity_points = [(0.0, 0.0), (0.08, 0.0), (0.25, 0.16), (0.55, 0.58), (0.82, 0.88), (1.0, 1.0)]
    else:
        preset_id = "amber"
        color_points = [(0.0, "#21170A"), (0.42, "#DB8A24"), (1.0, "#FFE06B")]
        opacity_points = [(0.0, 0.0), (0.08, 0.0), (0.42, 0.34), (1.0, 0.86)]

    return {
        "schema_version": TIF_TRANSFER_FUNCTION_SCHEMA_VERSION,
        "preset_id": preset_id,
        "name": preset_id,
        "intensity_domain": "normalized",
        "window": {"low": 0.0, "high": 1.0},
        "opacity_points": opacity_points,
        "color_points": color_points,
        "gradient_opacity": {
            "enabled": preset_id in {"morphology", "publication"},
            "low": 0.04 if preset_id == "morphology" else 0.08,
            "high": 0.34 if preset_id == "morphology" else 0.42,
            "strength": 0.65 if preset_id == "morphology" else 0.45,
        },
        "tint_rgb": list(tint),
    }


def normalize_transfer_function(payload=None, preset="amber", tint_rgb=(1.0, 0.83, 0.30)):
    source = copy.deepcopy(payload) if isinstance(payload, dict) else builtin_transfer_function(preset, tint_rgb)
    source.setdefault("schema_version", TIF_TRANSFER_FUNCTION_SCHEMA_VERSION)
    preset_id = str(source.get("preset_id") or preset or "amber").lower()
    if preset_id not in TRANSFER_PRESET_IDS:
        preset_id = "amber"
    source["preset_id"] = preset_id
    source.setdefault("name", preset_id)
    source.setdefault("intensity_domain", "normalized")
    window = source.get("window") if isinstance(source.get("window"), dict) else {}
    low = max(0.0, min(0.98, float(window.get("low", 0.0))))
    high = max(low + 0.001, min(1.0, float(window.get("high", 1.0))))
    source["window"] = {"low": low, "high": high}
    source.setdefault("opacity_points", builtin_transfer_function(preset_id, tint_rgb)["opacity_points"])
    source.setdefault("color_points", builtin_transfer_function(preset_id, tint_rgb)["color_points"])
    gradient = source.get("gradient_opacity") if isinstance(source.get("gradient_opacity"), dict) else {}
    source["gradient_opacity"] = {
        "enabled": bool(gradient.get("enabled", False)),
        "low": max(0.0, min(1.0, float(gradient.get("low", 0.04)))),
        "high": max(0.0, min(1.0, float(gradient.get("high", 0.34)))),
        "strength": max(0.0, min(1.0, float(gradient.get("strength", 0.0)))),
    }
    source["tint_rgb"] = list(_rgb01(source.get("tint_rgb", tint_rgb), fallback=tint_rgb))
    return source


def build_transfer_lut(
    transfer_function=None,
    preset="amber",
    tint_rgb=(1.0, 0.83, 0.30),
    cutoff=0.0,
    opacity=1.0,
    clarity=False,
    size=DEFAULT_TRANSFER_LUT_SIZE,
):
    tf = normalize_transfer_function(transfer_function, preset=preset, tint_rgb=tint_rgb)
    size = max(16, int(size))
    density = np.linspace(0.0, 1.0, size, dtype=np.float32)
    window = tf["window"]
    low = max(0.0, min(0.98, float(window["low"]) + float(cutoff)))
    high = max(low + 0.001, min(1.0, float(window["high"])))
    mapped = np.clip((density - low) / max(high - low, 0.001), 0.0, 1.0)
    rgb = _interp_color_points(mapped, tf["color_points"])
    alpha = _interp_points(mapped, tf["opacity_points"])
    alpha = _smoothstep(alpha)
    if bool(clarity):
        alpha = np.clip(np.power(alpha, 0.76) * 0.88, 0.0, 1.0)
        rgb = np.clip(rgb * (0.94 + 0.20 * density[:, None]), 0.0, 1.0)
    alpha *= max(0.0, min(1.4, float(opacity)))
    alpha = np.clip(alpha, 0.0, 1.0)
    alpha[density <= low] = 0.0

    lut = np.empty((1, size, 4), dtype=np.uint8)
    lut[0, :, :3] = np.clip(rgb * 255.0, 0.0, 255.0).astype(np.uint8)
    lut[0, :, 3] = np.clip(alpha * 255.0, 0.0, 255.0).astype(np.uint8)
    return np.ascontiguousarray(lut)


__all__ = [
    "DEFAULT_TRANSFER_LUT_SIZE",
    "TIF_TRANSFER_FUNCTION_SCHEMA_VERSION",
    "TRANSFER_PRESET_IDS",
    "builtin_transfer_function",
    "build_transfer_lut",
    "normalize_transfer_function",
]
