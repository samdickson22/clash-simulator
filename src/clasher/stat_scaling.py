"""Shared Clash Royale level-scaling helpers."""

from __future__ import annotations

import json
from functools import cache
from operator import index
from typing import SupportsFloat

from .paths import gamedata_path


@cache
def _level_percentages() -> tuple[int, ...]:
    """Load the normalized stat table once for this process's pinned feed."""
    with gamedata_path().open() as source:
        rarities = json.load(source)["items"]["rarities"]
    rows = [row for row in rarities if row.get("name") == "Common"]
    if len(rows) != 1:
        raise ValueError("game data must define one canonical Common stat table")
    percentages = rows[0].get("powerLevelMultiplier")
    if (
        not isinstance(percentages, list)
        or not percentages
        or any(type(value) is not int or value <= 0 for value in percentages)
    ):
        raise ValueError("invalid serialized level multipliers")
    # Character stats in the normalized feed use a level-one base. Rarity
    # unlock offsets are card-collection metadata, not another stat scale.
    return (100, *percentages)


def _level_percentage(level: int) -> int:
    if isinstance(level, bool):
        raise TypeError("level must be an integer in the serialized table")
    try:
        position = index(level) - 1
    except TypeError as error:
        raise TypeError("level must be an integer in the serialized table") from error
    percentages = _level_percentages()
    if not 0 <= position < len(percentages):
        raise ValueError(f"level must be between 1 and {len(percentages)}")
    return percentages[position]


def level_multiplier(level: int) -> float:
    """Return the serialized multiplier rather than extrapolating growth."""
    return _level_percentage(level) / 100.0


def scale_stat(value: SupportsFloat | None, level: int = 11) -> int | None:
    """Scale a serialized base stat to ``level`` using game truncation."""
    if value is None:
        return None
    percentage = _level_percentage(level)
    numeric = float(value)
    if numeric.is_integer():
        product = int(numeric) * percentage
        # Native integer division truncates toward zero, including sentinels.
        return product // 100 if product >= 0 else -((-product) // 100)
    return int(numeric * percentage / 100.0)
