"""Card naming normalization helpers.

These aliases bridge canonical deck-list names to the internal gamedata keys.
"""

from __future__ import annotations

from typing import Mapping, Optional, TypeVar

T = TypeVar("T")


CARD_NAME_ALIASES: dict[str, str] = {
    # Common community names -> gamedata keys used by this project
    "Archers": "Archer",
    "Bandit": "Assassin",
    "BarbarianBarrel": "BarbLog",
    "DartGoblin": "BlowdartGoblin",
    "GiantSnowball": "Snowball",
    "Guards": "SkeletonWarriors",
    "IceGolem": "IceGolemite",
    "IceSpirit": "IceSpirits",
    "Lumberjack": "AxeMan",
    "MagicArcher": "EliteArcher",
    "NightWitch": "DarkWitch",
    "RoyalGhost": "Ghost",
    "SkeletonBarrel": "SkeletonBalloon",
    # Spaced/punctuation variants occasionally found in deck exports
    "Hog Rider": "HogRider",
    "Mini P.E.K.K.A": "MiniPekka",
    "Mini P.E.K.K.A.": "MiniPekka",
    "P.E.K.K.A": "Pekka",
    "P.E.K.K.A.": "Pekka",
    "Royal Delivery": "RoyalDelivery",
    "Night Witch": "DarkWitch",
    "Skeleton Barrel": "SkeletonBalloon",
    "The Log": "Log",
    "Wall Breakers": "Wallbreakers",
    "X-Bow": "Xbow",
}


def resolve_card_name(name: str, available: Optional[Mapping[str, T]] = None) -> str:
    """Resolve a card/deck name to an internal gamedata key."""
    if not name:
        return name

    if available is not None and name in available:
        return name

    resolved = CARD_NAME_ALIASES.get(name, name)
    if available is None:
        return resolved
    return resolved if resolved in available else name


def alias_card_map(values: Mapping[str, T]) -> dict[str, T]:
    """Return a shallow copy of `values` with alias keys added when resolvable."""
    aliased = dict(values)
    for alias, target in CARD_NAME_ALIASES.items():
        if alias in aliased:
            continue
        target_value = values.get(target)
        if target_value is not None:
            aliased[alias] = target_value
    return aliased
