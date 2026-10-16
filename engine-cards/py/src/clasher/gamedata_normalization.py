"""Normalize compositional game-data into the simulator's runtime schema.

The live export increasingly stores gameplay objects behind action graphs
instead of duplicating fully expanded ``summon*Data`` fields on every card.
The simulator keeps one stable internal representation, so this module
resolves those action edges and named object references at the data boundary.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from typing import Any


def normalized_walking_speed(character_data: Mapping[str, Any]) -> float | None:
    """Convert average serialized speed to the native active-stride speed.

    Native data compensates for StopMovementAfterMS/WaitMS before buffs and
    gait timing. Integer truncation matches Giant52, Golem54, and IceGolem52.
    The original asset values stay unchanged in the raw data.
    """
    raw = character_data.get("speed")
    if raw is None:
        return None
    speed = float(raw)
    stop_ms = int(character_data.get("stopMovementAfterMS", 0) or 0)
    wait_ms = int(character_data.get("waitMS", 0) or 0)
    if stop_ms > 0 and wait_ms > 0:
        return float(int(speed) * (stop_ms + wait_ms) // stop_ms)
    return speed


_ACTION_KEYS = {
    "actionsData",
    "onStartingActionData",
    "subActionsData",
}

_DEPLOYABLE_SOURCES = {
    "buildings",
    "characters",
}


# The public v5 export contains the Skeleton Barrel's EXT reference but omits
# the inherited object itself. This is the resolved gameplay portion of the
# current client definition:
#
#   EXT.SkeletonContainerNew -> BUILDING.SkeletonContainer
#
# The child changes only its death VFX. Keeping the missing native object in
# this declarative registry lets the same reference resolver handle it just
# like an object included directly in the export.
EXTERNAL_OBJECT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "SkeletonContainerNew": {
        "name": "SkeletonContainerNew",
        "source": "buildings",
        "attacksAir": True,
        "attacksGround": True,
        "deathDamage": 57,
        "deathDamageRadius": 2000,
        "deathPushback": 1000,
        "deathSpawnCharacter": "Skeleton",
        "deathSpawnCount": 7,
        "deathSpawnDeployTime": 500,
        "deathSpawnMinRadius": 1480,
        "deathSpawnPushback": True,
        "deathSpawnRadius": 1480,
        "deployTime": 600,
        "spawnConstPriority": True,
        "tidTarget": "TID_TARGETS_AIR_AND_GROUND",
    },
}


def serialized_hit_planes(
    payload: Mapping[str, Any],
    *,
    default_air: bool = True,
    default_ground: bool = True,
) -> tuple[bool, bool]:
    """Decode compact-export hit-plane fields.

    The v5 serializer drops false boolean columns. If either plane column is
    present, an omitted counterpart is therefore false (Earthquake now emits
    only ``hitsGround=true``). Character projectiles commonly serialize the
    same rule through ``tidTarget`` instead. Payloads with neither form retain
    the native mechanic's caller-supplied defaults, allowing a projectile to
    inherit its firing character's attack planes.
    """
    if "hitsAir" in payload or "hitsGround" in payload:
        return bool(payload.get("hitsAir", False)), bool(
            payload.get("hitsGround", False)
        )
    target_type = str(payload.get("tidTarget", "") or "")
    if target_type:
        return (
            "AIR" in target_type,
            "GROUND" in target_type or "BUILDINGS" in target_type,
        )
    return bool(default_air), bool(default_ground)


def _is_deployable_object(value: Any) -> bool:
    if not isinstance(value, dict) or not value.get("name"):
        return False
    source = str(value.get("source", ""))
    return source in _DEPLOYABLE_SOURCES or source.startswith(
        ("buildings_", "characters_")
    )


def _iter_dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def _iter_action_spawns(value: Any) -> Iterator[dict[str, Any]]:
    """Yield deployable objects reached by any nested action graph."""
    if isinstance(value, dict):
        spawn = value.get("spawnDataData")
        if _is_deployable_object(spawn):
            yield spawn
        for child in value.values():
            yield from _iter_action_spawns(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_action_spawns(child)


def _object_richness(value: Mapping[str, Any]) -> tuple[int, int]:
    """Prefer complete base objects over thin EXT/action references."""
    nested_fields = sum(1 for _ in _iter_dicts(value))
    return len(value), nested_fields


def build_object_registry(data: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Index the richest serialized definition for each deployable object."""
    registry = deepcopy(EXTERNAL_OBJECT_DEFINITIONS)
    for value in _iter_dicts(data):
        if not _is_deployable_object(value):
            continue
        name = str(value["name"])
        existing = registry.get(name)
        if existing is None or _object_richness(value) > _object_richness(existing):
            registry[name] = deepcopy(value)
    return registry


def _runtime_area_payload(area: Mapping[str, Any]) -> dict[str, Any]:
    """Strip action routing while retaining the area effect it surrounds."""
    return {
        key: deepcopy(value)
        for key, value in area.items()
        if key not in _ACTION_KEYS
    }


def _attach_action_death_spawn(value: dict[str, Any]) -> None:
    if value.get("deathSpawnCharacterData"):
        return
    death_area = value.get("deathAreaEffectData")
    if not isinstance(death_area, dict):
        return
    spawn = next(_iter_action_spawns(death_area.get("onStartingActionData")), None)
    if spawn is not None:
        value["deathSpawnCharacterData"] = deepcopy(spawn)
        value.setdefault("deathSpawnCharacter", spawn.get("name"))


def _resolve_death_spawn_reference(
    value: dict[str, Any],
    object_registry: Mapping[str, Mapping[str, Any]],
) -> None:
    if value.get("deathSpawnCharacterData"):
        return
    name = value.get("deathSpawnCharacter")
    resolved = object_registry.get(str(name)) if name else None
    if resolved is not None:
        value["deathSpawnCharacterData"] = deepcopy(resolved)


def normalize_entry(
    entry: Mapping[str, Any],
    object_registry: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return one card entry with action spawns and references expanded.

    Expansion is structural: object names decide only reference identity, not
    behavior. This keeps new cards using the same action/reference semantics
    without adding card-name conditionals.
    """
    result = deepcopy(entry)
    registry: dict[str, Mapping[str, Any]] = dict(EXTERNAL_OBJECT_DEFINITIONS)
    if object_registry:
        registry.update(object_registry)

    if not result.get("summonCharacterData") and result.get("spellAsDeploy"):
        area = result.get("areaEffectObjectData")
        if isinstance(area, dict):
            character = next(
                _iter_action_spawns(area.get("onStartingActionData")),
                None,
            )
            if character is not None:
                character = deepcopy(character)
                character.setdefault(
                    "spawnAreaObjectData",
                    _runtime_area_payload(area),
                )
                result["summonCharacterData"] = character

    # Newly attached objects can themselves contain named death spawns. Walk
    # to a fixed point so an arbitrary chain is hydrated without special
    # nesting-depth assumptions.
    processed: set[int] = set()
    while True:
        pending = [
            value
            for value in _iter_dicts(result)
            if id(value) not in processed
        ]
        if not pending:
            break
        for value in pending:
            processed.add(id(value))
            _attach_action_death_spawn(value)
            _resolve_death_spawn_reference(value, registry)

    return result
