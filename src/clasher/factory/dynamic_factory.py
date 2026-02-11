"""Helpers for creating card compatibility stats from dynamic data."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..card_types import (
    CardStatsCompat,
    TroopStats,
    BuildingStats,
)


def _units_to_tiles(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value / 1000.0


def _tiles_to_units(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    return int(value * 1000)


def troop_from_character_data(
    name: str,
    char_data: Dict[str, Any],
    *,
    elixir: int = 0,
    rarity: str = "Common",
    raw_overrides: Optional[Dict[str, Any]] = None,
) -> CardStatsCompat:
    """Create CardStatsCompat for a troop using raw character data."""
    data = dict(char_data or {})
    projectile_data = data.get("projectileData") or {}
    damage = data.get("damage")
    if damage is None:
        damage = projectile_data.get("damage")

    troop_stats = TroopStats(
        hitpoints=data.get("hitpoints"),
        damage=damage,
        range_tiles=_units_to_tiles(data.get("range")),
        hit_speed_ms=data.get("hitSpeed"),
        sight_range_tiles=_units_to_tiles(data.get("sightRange")),
        collision_radius_tiles=_units_to_tiles(data.get("collisionRadius")),
        speed_tiles_per_min=float(data["speed"]) if data.get("speed") is not None else None,
        deploy_time_ms=data.get("deployTime"),
        load_time_ms=data.get("loadTime"),
        summon_count=data.get("count") or data.get("summonNumber"),
    )

    raw_entry: Dict[str, Any] = {
        "id": data.get("id", 0),
        "name": name,
        "manaCost": elixir,
        "rarity": rarity,
        "tidType": "TID_CARD_TYPE_CHARACTER",
        "summonCharacterData": data,
    }
    if raw_overrides:
        raw_entry.update(raw_overrides)

    from .card_factory import create_card_definition

    card_def = create_card_definition(
        name=name,
        kind="troop",
        rarity=rarity,
        elixir=elixir,
        troop_stats=troop_stats,
        raw=raw_entry,
    )
    return CardStatsCompat.from_card_definition(card_def)


def troop_from_values(
    name: str,
    *,
    hitpoints: int,
    damage: int,
    speed_tiles_per_min: float,
    range_tiles: float = 1.0,
    sight_range_tiles: float = 5.0,
    hit_speed_ms: int = 1000,
    collision_radius_tiles: float = 0.5,
    deploy_time_ms: int = 1000,
    load_time_ms: int = 1000,
    target_type: str = "TID_TARGETS_GROUND",
    attacks_ground: bool = True,
    attacks_air: bool = False,
    elixir: int = 0,
    rarity: str = "Common",
) -> CardStatsCompat:
    """Create CardStatsCompat for simple troop definitions."""
    char_data = {
        "hitpoints": hitpoints,
        "damage": damage,
        "speed": speed_tiles_per_min,
        "range": _tiles_to_units(range_tiles),
        "sightRange": _tiles_to_units(sight_range_tiles),
        "hitSpeed": hit_speed_ms,
        "collisionRadius": _tiles_to_units(collision_radius_tiles),
        "deployTime": deploy_time_ms,
        "loadTime": load_time_ms,
        "tidTarget": target_type,
        "attacksGround": attacks_ground,
        "attacksAir": attacks_air,
    }
    return troop_from_character_data(name, char_data, elixir=elixir, rarity=rarity)


def building_from_values(
    name: str,
    *,
    hitpoints: int,
    damage: int,
    range_tiles: float,
    sight_range_tiles: Optional[float],
    hit_speed_ms: int,
    deploy_time_ms: int,
    collision_radius_tiles: Optional[float],
    lifetime_ms: Optional[int] = None,
    elixir: int = 0,
    rarity: str = "Common",
    projectile_speed: Optional[int] = None,
    projectile_damage: Optional[int] = None,
    target_type: str = "TID_TARGETS_AIR_AND_GROUND",
    raw_overrides: Optional[Dict[str, Any]] = None,
) -> CardStatsCompat:
    """Create CardStatsCompat for building-like entities such as towers."""
    building_stats = BuildingStats(
        hitpoints=hitpoints,
        damage=damage,
        range_tiles=range_tiles,
        hit_speed_ms=hit_speed_ms,
        sight_range_tiles=sight_range_tiles,
        collision_radius_tiles=collision_radius_tiles,
        lifetime_ms=lifetime_ms,
        deploy_time_ms=deploy_time_ms,
    )

    summon_character_data = {
        "hitpoints": hitpoints,
        "damage": damage,
        "range": _tiles_to_units(range_tiles),
        "sightRange": _tiles_to_units(sight_range_tiles) if sight_range_tiles is not None else None,
        "hitSpeed": hit_speed_ms,
        "collisionRadius": _tiles_to_units(collision_radius_tiles) if collision_radius_tiles is not None else None,
        "deployTime": deploy_time_ms,
        "tidTarget": target_type,
        "projectileData": {
            "speed": projectile_speed,
            "damage": projectile_damage or damage,
        } if projectile_speed is not None else None,
    }

    raw_entry = {
        "id": 0,
        "name": name,
        "manaCost": elixir,
        "rarity": rarity,
        "tidType": "TID_CARD_TYPE_BUILDING",
        "summonCharacterData": summon_character_data,
        "projectileSpeed": projectile_speed,
        "projectileData": summon_character_data.get("projectileData"),
        "tidTarget": target_type,
    }
    if raw_overrides:
        raw_entry.update(raw_overrides)

    from .card_factory import create_card_definition

    card_def = create_card_definition(
        name=name,
        kind="building",
        rarity=rarity,
        elixir=elixir,
        building_stats=building_stats,
        raw=raw_entry,
    )
    return CardStatsCompat.from_card_definition(card_def)
