"""
Mapping from common/deck card names to internal gamedata names.
The gamedata.json uses internal names that differ from the commonly used card names.
"""

# Deck name -> gamedata internal name
DECK_TO_INTERNAL = {
    "Archers": "Archer",
    "Bandit": "Assassin",
    "BarbarianBarrel": "BarbLog",
    "DartGoblin": "BlowdartGoblin",
    "GiantSnowball": "Snowball",
    "Guards": "SkeletonWarriors",
    "IceGolem": "IceGolemite",
    "IceSpirit": "IceSpirits",
    "Lumberjack": "RageBarbarian",
    "MagicArcher": "EliteArcher",
    "RoyalGhost": "Ghost",
    "SkeletonBarrel": "SkeletonBalloon",
}

# Internal name -> deck name (reverse mapping)
INTERNAL_TO_DECK = {v: k for k, v in DECK_TO_INTERNAL.items()}


def resolve_name(name: str) -> str:
    """Resolve a deck card name to its internal gamedata name."""
    return DECK_TO_INTERNAL.get(name, name)


def display_name(internal_name: str) -> str:
    """Get the display/deck name from an internal name."""
    return INTERNAL_TO_DECK.get(internal_name, internal_name)
