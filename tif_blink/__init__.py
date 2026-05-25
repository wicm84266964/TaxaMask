"""TIF-Blink experimental brain-region segmentation framework."""

from .boundary import BoundaryBandConfig, make_boundary_band
from .labels import LabelMapping, build_label_mapping, decode_label, encode_label
from .preprocess import input_channel_count
from .sample import TifBlinkSample
from .sampler import BalancedSliceSamplerConfig
from .views import BlinkViewConfig, make_blink_view

__all__ = [
    "BoundaryBandConfig",
    "BlinkViewConfig",
    "BalancedSliceSamplerConfig",
    "LabelMapping",
    "TifBlinkSample",
    "build_label_mapping",
    "decode_label",
    "encode_label",
    "input_channel_count",
    "make_boundary_band",
    "make_blink_view",
]
