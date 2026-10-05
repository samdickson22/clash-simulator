"""Crown Tower curves from the retained Null's 15.535.86 reference tables.

The level-one King base and projectile come from characters/king_tower.toml;
the Princess base comes from gamedata.json. globals.csv sets 7% King HP,
8% other Crown stats, then 10% after TOWER_SCALING_START_EXP_LEVEL=9.
Source hashes and extracted values are recorded in the M0 levels receipt.
"""

from operator import index

from .balance import TOURNAMENT_LEVEL, tournament_tower_stat


def tower_stat(name: str, field: str, level: int = TOURNAMENT_LEVEL) -> int:
    """Scale Crown HP/damage with integer percentage truncation at each level."""
    if isinstance(level, bool):
        raise TypeError("tower level must be an integer")
    level = index(level)
    if not 10 <= level <= 12:
        raise ValueError("Crown Tower level support is limited to 10 through 12")
    bases = {
        "PrincessTower": {"hitpoints": 1400, "damage": 50},
        "KingTower": {"hitpoints": 2400, "damage": 50},
    }
    base = bases[name][field]
    if level == TOURNAMENT_LEVEL:
        # Preserve the pinned tournament baseline, including its balance layer.
        value = tournament_tower_stat(name, field)
        if value is None:
            raise ValueError(f"Missing tournament {name} {field}")
        return value
    growth = 7 if name == "KingTower" and field == "hitpoints" else 8
    percentage = 100
    for next_level in range(2, level + 1):
        step_growth = growth if next_level <= 9 else 10
        percentage = percentage * (100 + step_growth) // 100
    return base * percentage // 100
