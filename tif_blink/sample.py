from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TifBlinkSample:
    image: np.ndarray
    label: np.ndarray
    specimen_id: str = ""

