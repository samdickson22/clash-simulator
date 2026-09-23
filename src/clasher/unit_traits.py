"""Runtime traits that are absent from the exported card data."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

# Reference/benchmark switch for production collision-plane calls, whose
# inputs are exact Entity instances with required air/hover fields.
_USE_DIRECT_ENTITY_COLLISION_PLANE = True


@lru_cache(maxsize=512)
def _normalize(name: str) -> str:
    return "".join(ch for ch in name.casefold() if ch.isalnum())


# The bundled game-data export contains attack target planes but no movement
# plane.  Keep the missing source datum centralized instead of duplicating
# partial name lists in each spawn path.
AIR_UNIT_NAMES = frozenset(
    _normalize(name)
    for name in {
        "BabyDragon",
        "Balloon",
        "Bat",
        "Bats",
        "ElectroDragon",
        "FlyingMachine",
        "InfernoDragon",
        "LavaHound",
        "LavaPup",
        "LavaPups",
        "MegaMinion",
        "Minion",
        "Minions",
        "MinionHorde",
        "Phoenix",
        "SkeletonBalloon",
        "SkeletonDragon",
        "SkeletonDragons",
    }
)


# Hovering troops remain on the ground target/effect plane but ignore river
# terrain while moving. Keep this separate from ``AIR_UNIT_NAMES`` so cards
# such as Royal Ghost are still hittable by ground-only attacks and spells.
HOVER_UNIT_NAMES = frozenset(
    _normalize(name)
    for name in {
        "BattleHealer",
        "Ghost",
        "RoyalGhost",
    }
)


# Ordinary pushback cannot move heavyweight troops. The Log explicitly
# bypasses this class. The exported data omits mass, so keep the missing
# runtime trait beside the likewise omitted movement plane.
KNOCKBACK_IMMUNE_NAMES = frozenset(
    _normalize(name)
    for name in {
        "Bowler",
        "DarkPrince",
        "Giant",
        "Golem",
        "LavaHound",
        "MegaKnight",
        "Pekka",
        "Prince",
        "Sparky",
    }
)


# The public card export used by this project omits the character ``mass``
# column. Mass governs native troop collision pressure; these values are the
# runtime character values (spawned descendants included).
UNIT_MASS_BY_NAME = {
    _normalize(name): mass
    for mass, names in {
        1.0: {
            "Bat", "Bats", "ElectroSpirit", "FireSpirit", "Guard",
            "IceSpirit", "IceSpirits", "Skeleton", "Skeletons",
            "SkeletonWarrior", "SkeletonWarriors", "SpearGoblin", "SpearGoblins",
        },
        2.0: {
            "Goblin",
            "Goblins",
            "Goblin_Stab",
            "Minion",
            "Minions",
            "RoyalHog",
            "RoyalHogs",
        },
        3.0: {
            "Archer", "Archers", "Assassin", "Bandit", "BlowdartGoblin",
            "DartGoblin", "EliteArcher", "Ghost", "MagicArcher",
            "Princess", "RoyalGhost",
        },
        4.0: {
            "Barbarian", "Barbarians", "Bomber", "HogRider", "MiniPekka",
            "RageBarbarian", "Lumberjack", "DarkWitch", "NightWitch",
            "Wallbreaker", "Wallbreakers",
        },
        5.0: {
            "BabyDragon", "IceWizard", "InfernoDragon", "LavaHound", "LavaPup",
            "LavaPups", "Musketeer", "Valkyrie", "ElectroWizard",
            "DeliveryRecruit", "RoyalRecruit", "RoyalRecruits",
        },
        6.0: {
            "ArcherQueen", "Balloon", "BattleRam", "DarkPrince", "Firecracker",
            "Golemite", "IceGolem", "IceGolemite", "Knight", "MegaMinion", "Miner",
            "Prince",
        },
        7.0: {"ElectroDragon", "SkeletonBalloon", "SkeletonBarrel"},
        8.0: {"Witch"},
        18.0: {"Bowler", "Giant", "MegaKnight", "Pekka"},
        20.0: {"Golem"},
    }.items()
    for name in names
}


def is_air_unit_card(card_stats: Any) -> bool:
    """Return the movement plane for a card or spawned character."""
    raw = getattr(card_stats, "_raw_entry", {}) or {}
    character_data = raw.get("summonCharacterData", {}) or {}
    flying_height = character_data.get("flyingHeight")
    if flying_height is not None:
        return float(flying_height) > 0.0
    names = [getattr(card_stats, "name", "")]
    names.append(character_data.get("name", ""))
    return any(_normalize(name) in AIR_UNIT_NAMES for name in names if name)


def is_hover_unit_card(card_stats: Any) -> bool:
    """Return whether a ground-targeted card ignores river terrain."""
    raw = getattr(card_stats, "_raw_entry", {}) or {}
    character_data = raw.get("summonCharacterData", {}) or {}
    hovering = character_data.get("hovering")
    if hovering is not None:
        return bool(hovering)
    names = [getattr(card_stats, "name", "")]
    names.append(character_data.get("name", ""))
    return any(_normalize(name) in HOVER_UNIT_NAMES for name in names if name)


def is_airborne_target(entity: Any) -> bool:
    """Return the target plane currently occupied by an entity.

    River-jumping troops temporarily occupy the air target plane: ground-only
    attacks lose them, while attacks capable of hitting air continue normally.
    This is combat state rather than a card trait, so it must not overwrite the
    unit's permanent movement plane.
    """
    return bool(
        getattr(entity, "is_air_unit", False)
        or getattr(entity, "_river_jump_active", False)
    )


def is_native_building_target(entity: Any) -> bool:
    """Return whether building-only attackers may acquire this entity.

    Native targeting accepts physical buildings plus CharacterData rows whose
    ``BuildingTarget`` bit is set. Keeping the predicate data-driven preserves
    support for moving objective characters without classifying their
    collision or sight geometry as a stationary building.
    """
    if getattr(entity, "entity_kind", 4) == 1:
        return True
    card_stats = getattr(entity, "card_stats", None)
    if bool(getattr(card_stats, "building_target", False)):
        return True
    character_data = getattr(card_stats, "summon_character_data", None) or {}
    return bool(character_data.get("buildingTarget", False))


def is_above_ground_surface(entity: Any) -> bool:
    """Return whether ground-hugging effects pass underneath the entity.

    Mega Knight's leap rises above rolling/ground-area payloads without
    changing target plane: X-Bow remains locked while Log passes underneath.
    River jumps change both predicates and are therefore a distinct state.
    """
    return bool(
        getattr(entity, "is_air_unit", False)
        or getattr(entity, "_river_jump_active", False)
        or getattr(entity, "_mk_leap_phase", None) == "airborne"
    )


def uses_air_collision_plane(entity: Any) -> bool:
    """Return the body-pressure plane used by native movement.

    Hovering characters remain ground targets and can still receive rolling
    and ground-area payloads, but their physical body shares the air collision
    plane. This lets them pass through ground characters and buildings while
    still spacing flying characters.
    """
    if _USE_DIRECT_ENTITY_COLLISION_PLANE:
        return bool(
            entity.is_air_unit
            or entity._is_hover_unit
            or getattr(entity, "_river_jump_active", False)
            or getattr(entity, "_mk_leap_phase", None) == "airborne"
        )

    hover = getattr(entity, "_is_hover_unit", None)
    if hover is None:
        hover = is_hover_unit_card(getattr(entity, "card_stats", None))
    return bool(is_above_ground_surface(entity) or hover)


def is_in_transit(entity: Any) -> bool:
    """Return whether an entity is moving outside ordinary ground collision."""
    if getattr(entity, "_river_jump_active", False):
        return True
    for mechanic in getattr(entity, "mechanics", []):
        predicate = getattr(mechanic, "blocks_ground_collision", None)
        if callable(predicate) and predicate(entity):
            return True
    return False


def is_knockback_immune(card_stats: Any) -> bool:
    """Return whether ordinary pushback is blocked by unit mass."""
    raw = getattr(card_stats, "_raw_entry", {}) or {}
    character_data = raw.get("summonCharacterData", {}) or {}
    ignore_pushback = character_data.get("ignorePushback")
    if ignore_pushback is not None:
        return bool(ignore_pushback)
    names = [getattr(card_stats, "name", "")]
    names.append(character_data.get("name", ""))
    return any(_normalize(name) in KNOCKBACK_IMMUNE_NAMES for name in names if name)


def unit_mass(card_stats: Any) -> float:
    """Return the runtime collision mass for a troop or spawned character."""
    raw = getattr(card_stats, "_raw_entry", {}) or {}
    character_data = raw.get("summonCharacterData", {}) or {}
    explicit = character_data.get("mass")
    if explicit is None:
        explicit = getattr(card_stats, "mass", None)
    if explicit is not None:
        return max(0.1, float(explicit))

    names = [getattr(card_stats, "name", "")]
    nested = getattr(card_stats, "summon_character_data", None) or {}
    names.append(nested.get("name", ""))
    for name in names:
        value = UNIT_MASS_BY_NAME.get(_normalize(name))
        if value is not None:
            return value
    # Five is the game's ordinary medium-unit class. Enabled deck cards and
    # all of their descendants are enumerated above; this remains a safe
    # forward-compatible default for unknown custom data.
    return 5.0
