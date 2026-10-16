from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BOARD_WIDTH = 18
BOARD_HEIGHT = 32
NUM_TILES = BOARD_WIDTH * BOARD_HEIGHT
NUM_HAND_SLOTS = 4


@dataclass(frozen=True)
class CvObservation:
    """CV-equivalent observation bundle.

    `board` is channel-first (C, H, W).
    `hud` is a flat vector of visible HUD features.
    """

    board: np.ndarray
    hud: np.ndarray
