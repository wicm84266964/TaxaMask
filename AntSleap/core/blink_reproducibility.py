"""Shared random initialization controls for Blink expert training."""

from __future__ import annotations

import random

import numpy as np
import torch


DEFAULT_BLINK_RANDOM_SEED = 1337
_MAX_NUMPY_SEED = (2**32) - 1


def normalize_blink_random_seed(value, fallback=DEFAULT_BLINK_RANDOM_SEED):
    if isinstance(value, bool):
        return int(fallback)
    try:
        seed = int(value)
    except (TypeError, ValueError):
        seed = int(fallback)
    if seed < 0 or seed > _MAX_NUMPY_SEED:
        seed = int(fallback)
    return seed


def build_blink_seed_record(value=DEFAULT_BLINK_RANDOM_SEED):
    seed = normalize_blink_random_seed(value)
    return {
        "python": seed,
        "numpy": seed,
        "pytorch": seed,
        "cuda": seed,
    }


def build_random_blink_initialization():
    return {
        "method": "random",
        "registered_checkpoint": None,
        "torchvision_pretrained": False,
    }


def apply_blink_training_seed(value=DEFAULT_BLINK_RANDOM_SEED):
    seeds = build_blink_seed_record(value)
    random.seed(seeds["python"])
    np.random.seed(seeds["numpy"])
    torch.manual_seed(seeds["pytorch"])
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seeds["cuda"])
    return seeds


__all__ = [
    "DEFAULT_BLINK_RANDOM_SEED",
    "apply_blink_training_seed",
    "build_blink_seed_record",
    "build_random_blink_initialization",
    "normalize_blink_random_seed",
]
