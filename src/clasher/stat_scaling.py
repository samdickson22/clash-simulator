"""Shared Clash Royale level-scaling helpers."""

from __future__ import annotations

from typing import SupportsFloat


def level_multiplier(level: int) -> float:
    """Return the game's cumulative, two-decimal level multiplier."""
    multiplier = 1.0
    for _ in range(max(0, int(level) - 1)):
        multiplier = int((multiplier * 1.1 + 1e-9) * 100) / 100.0
    return multiplier


def scale_stat(value: SupportsFloat | None, level: int = 11) -> int | None:
    """Scale a serialized base stat to ``level`` using game truncation."""
    if value is None:
        return None
    return int(float(value) * level_multiplier(level))
