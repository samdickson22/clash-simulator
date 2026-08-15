from __future__ import annotations

import copy
import hashlib
import json
import math
import struct
from collections import deque
from dataclasses import dataclass, field, replace
from enum import Enum
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, cast

from .balance import DEFAULT_BATTLE_TIMELINE_NEXT_CARD_REFILL_COOLDOWN_MS
from .cards.ice_spirit import IceSpiritFreeze
from .differential import (
    SNAPSHOT_SCHEMA_VERSION,
    _entity_snapshot,
    _normalize,
    canonical_battle_snapshot,
    snapshot_bytes,
)
from .entities import Building, Projectile

try:
    from _clasher_rust import (  # type: ignore[import-untyped]
        ResidentBattle as _ResidentBattle,
    )
    from _clasher_rust import (  # type: ignore[import-untyped]
        consume_state_bytes as _consume_state_bytes,
    )
    from _clasher_rust import noop_ticks as _noop_ticks  # type: ignore[import-untyped]
    from _clasher_rust import (  # type: ignore[import-untyped]
        standard_grid_route as _standard_grid_route,
    )
except ImportError:  # pragma: no cover - depends on optional compiled artifact
    _consume_state_bytes = None
    _noop_ticks = None
    _ResidentBattle = None
    _standard_grid_route = None


FNV_OFFSET_BASIS: Final = 0xCBF29CE484222325
FNV_PRIME: Final = 0x100000001B3
U64_MASK: Final = (1 << 64) - 1
RESIDENT_CARD_CATALOG_SCHEMA_VERSION: Final = 13
RESIDENT_PREPARED_SEMANTIC_SCHEMA_VERSION: Final = 13
_RESIDENT_PREVIEW_TICK_FAILURE_PREFIX: Final = (
    "resident joint-action preview failed after actions during complete ticks: "
)


def _catalog_source_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _single_troop_capability_reasons(card_stats: Any, card_def: Any) -> list[str]:
    """Return data-driven reasons a card is outside resident troop actions."""
    from .cards.wallbreakers import WallBreakersDemolition
    from .mechanics.shared.damage_ramp import DamageRamp
    from .mechanics.shared.death_area import DeathAreaEffect
    from .mechanics.shared.death_effects import DeathDamage, DeathSpawn
    from .mechanics.shared.shield import Shield

    reasons: list[str] = []
    if str(getattr(card_def, "kind", "") or "").casefold() != "troop":
        reasons.append("not_troop")
    summon_count = int(getattr(card_stats, "summon_count", None) or 1)
    second_count = int(
        getattr(card_stats, "summon_character_second_count", None) or 0
    )
    second_data = getattr(card_stats, "summon_character_second_data", None)
    if not 1 <= summon_count <= 90 or not 0 <= second_count <= 90:
        reasons.append("unsupported_primary_count")
    if summon_count + second_count > 90:
        reasons.append("unsupported_formation_count")
    if (second_count > 0 and type(second_data) is not dict) or (
        second_count == 0 and second_data is not None
    ):
        reasons.append("malformed_secondary_character")
    primary_data = getattr(card_stats, "summon_character_data", None)
    if type(primary_data) is not dict or not primary_data:
        reasons.append("missing_character_data")
    if float(getattr(card_stats, "summon_width", 0.0) or 0.0) != 0.0:
        reasons.append("wide_formation")
    if getattr(card_stats, "summon_formation", None) is not None:
        reasons.append("explicit_formation")
    if bool(getattr(card_stats, "full_lane_deploy", False)):
        reasons.append("full_lane_deploy")
    mechanics = tuple(getattr(card_def, "mechanics", ()) or ())
    resident_death_mechanic_types = (
        Shield,
        DeathDamage,
        DeathSpawn,
        DeathAreaEffect,
    )
    mechanic_types = tuple(type(mechanic) for mechanic in mechanics)
    supported_mechanic_family = (
        mechanic_types == (IceSpiritFreeze,)
        or mechanic_types == (DamageRamp,)
        or mechanic_types == (WallBreakersDemolition,)
        or all(
            mechanic_type in resident_death_mechanic_types
            for mechanic_type in mechanic_types
        )
    )
    if not supported_mechanic_family:
        reasons.append("executable_mechanics")
    summon_radius = getattr(card_stats, "summon_radius", None)
    formation_radius = (
        float(summon_radius)
        if summon_radius is not None
        else float(getattr(card_stats, "collision_radius", 0.5) or 0.5)
    )
    if not math.isfinite(formation_radius) or formation_radius < 0.0:
        reasons.append("invalid_formation_radius")
    summon_deploy_delay = float(
        getattr(card_stats, "summon_deploy_delay", 0.0) or 0.0
    )
    if not math.isfinite(summon_deploy_delay) or summon_deploy_delay < 0.0:
        reasons.append("invalid_summon_deploy_delay")
    spawn_angle_shift = float(
        getattr(card_stats, "spawn_angle_shift", 0.0) or 0.0
    )
    if not math.isfinite(spawn_angle_shift):
        reasons.append("invalid_spawn_angle_shift")
    return reasons


def _ordinary_building_capability_reasons(
    card_stats: Any,
    card_def: Any,
) -> list[str]:
    """Return data-driven reasons a building is outside resident actions."""
    reasons: list[str] = []
    if str(getattr(card_def, "kind", "") or "").casefold() != "building":
        reasons.append("not_building")
    if str(getattr(card_stats, "card_type", "") or "").casefold() != "building":
        reasons.append("not_building_stats")
    from .cards.tesla import HideWhenIdle
    from .mechanics.shared.damage_ramp import DamageRamp

    mechanic_types = tuple(
        type(mechanic)
        for mechanic in tuple(getattr(card_def, "mechanics", ()) or ())
    )
    if mechanic_types not in ((), (DamageRamp,), (HideWhenIdle,)):
        reasons.append("executable_mechanics")
    if mechanic_types == (HideWhenIdle,):
        mechanic = card_def.mechanics[0]
        if (
            type(mechanic.hide_delay_ms) is not int
            or mechanic.hide_delay_ms <= 0
            or type(mechanic.rise_time_ms) is not int
            or mechanic.rise_time_ms <= 0
        ):
            reasons.append("invalid_hide_when_idle")
    if not getattr(card_stats, "summon_character_data", None):
        reasons.append("missing_character_data")
    if int(getattr(card_stats, "summon_count", None) or 1) != 1:
        reasons.append("unsupported_primary_count")
    if int(getattr(card_stats, "summon_character_second_count", None) or 0) != 0:
        reasons.append("secondary_character")
    if float(getattr(card_stats, "summon_width", 0.0) or 0.0) != 0.0:
        reasons.append("wide_formation")
    if getattr(card_stats, "summon_formation", None) is not None:
        reasons.append("explicit_formation")
    if bool(getattr(card_stats, "full_lane_deploy", False)):
        reasons.append("full_lane_deploy")
    raw_radius = getattr(card_stats, "collision_radius", None)
    collision_radius = float(1.0 if raw_radius is None else raw_radius)
    if not math.isfinite(collision_radius) or collision_radius < 0.0:
        reasons.append("invalid_building_collision_radius")
    deploy_time = float(getattr(card_stats, "deploy_time", 0.0) or 0.0)
    if not math.isfinite(deploy_time) or deploy_time < 0.0:
        reasons.append("invalid_deploy_time")
    return reasons


def _is_canonical_resident_action_arena(arena: Any) -> bool:
    """Return whether Rust's fixed action geometry exactly describes ``arena``."""
    from .arena import TileGrid

    if type(arena) is not TileGrid:
        return False
    expected_blocked = {
        (0, 14),
        (0, 17),
        (17, 14),
        (17, 17),
        *((x, 0) for x in (*range(6), *range(12, 18))),
        *((x, 31) for x in (*range(6), *range(12, 18))),
    }
    tower_positions = (
        (arena.BLUE_LEFT_TOWER.x, arena.BLUE_LEFT_TOWER.y),
        (arena.BLUE_RIGHT_TOWER.x, arena.BLUE_RIGHT_TOWER.y),
        (arena.BLUE_KING_TOWER.x, arena.BLUE_KING_TOWER.y),
        (arena.RED_LEFT_TOWER.x, arena.RED_LEFT_TOWER.y),
        (arena.RED_RIGHT_TOWER.x, arena.RED_RIGHT_TOWER.y),
        (arena.RED_KING_TOWER.x, arena.RED_KING_TOWER.y),
    )
    return (
        int(arena.width) == 18
        and int(arena.height) == 32
        and float(arena.tile_size) == 100.0
        and set(arena.BLOCKED_TILES) == expected_blocked
        and tower_positions
        == (
            (3.5, 6.5),
            (14.5, 6.5),
            (9.0, 2.5),
            (3.5, 25.5),
            (14.5, 25.5),
            (9.0, 29.5),
        )
    )


@dataclass(frozen=True)
class _ResidentCharacterBirthRecipe:
    kind: str
    action_kind: str
    effective_name: str
    template_fingerprint: str
    source_fingerprint: str | None
    member_count: int | None
    prototype: Any
    source_data: Any | None = None
    card_stats_group: int = 0
    uses_live_action_card_stats: bool = True
    formation_variant: int | None = None


@dataclass(frozen=True)
class _ResidentActionCardStatsAttestation:
    card_stats: Any
    fingerprint: str


@dataclass(frozen=True)
class _ResidentRollingProjectileRecipe:
    source_kind: str
    spawn_character: str | None
    spawn_character_data: dict[str, Any]
    spawn_data_fingerprint: str
    spawn_deploy_delay: float | None


@dataclass(frozen=True)
class _ResidentSpawnProjectileRecipe:
    source_kind: str
    damage: float
    radius: float
    travel_speed: float
    activation_delay: float
    spawn_count: int
    spawn_character: str
    spawn_character_data: dict[str, Any]
    spawn_data_fingerprint: str
    spawn_radius: float | None
    spawn_deploy_delay: float | None
    spawn_const_priority: bool
    launch_from_king: bool
    requires_territory: bool
    hits_air: bool
    hits_ground: bool
    ignore_buildings: bool
    crown_tower_damage_multiplier: float
    crown_tower_damage: float | None


@dataclass(frozen=True)
class _ResidentCardCatalogBundle:
    payload: bytes
    action_recipes: dict[str, _ResidentCharacterBirthRecipe]
    death_spawn_recipes: dict[tuple[str, str], _ResidentCharacterBirthRecipe]
    action_member_recipes: dict[
        tuple[str, int, str], _ResidentCharacterBirthRecipe
    ] = field(default_factory=dict)
    rolling_spawn_recipes: dict[
        tuple[str, str], _ResidentCharacterBirthRecipe
    ] = field(default_factory=dict)
    rolling_projectile_recipes: dict[
        str, _ResidentRollingProjectileRecipe
    ] = field(default_factory=dict)
    spawn_projectile_spawn_recipes: dict[
        tuple[str, int, str], _ResidentCharacterBirthRecipe
    ] = field(default_factory=dict)
    spawn_projectile_recipes: dict[
        str, _ResidentSpawnProjectileRecipe
    ] = field(default_factory=dict)
    pending_spell_action_kinds: tuple[tuple[str, str], ...] = ()


def _normalized_sha256(value: Any) -> str:
    return _canonical_json_sha256(_normalize(value))


def _canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()


def _prototype_sha256(prototype: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            _entity_snapshot(prototype),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()


def _copy_attested_birth_recipe(
    recipe: _ResidentCharacterBirthRecipe,
) -> _ResidentCharacterBirthRecipe | None:
    if recipe.formation_variant is not None and (
        type(recipe.formation_variant) is not int
        or not 0 <= recipe.formation_variant < 4
    ):
        return None
    if _prototype_sha256(recipe.prototype) != recipe.template_fingerprint:
        return None
    if (
        not recipe.uses_live_action_card_stats
        and recipe.source_fingerprint
        != _normalized_sha256(recipe.prototype.card_stats)
    ):
        return None
    prototype_battle = getattr(recipe.prototype, "battle_state", None)
    memo = {} if prototype_battle is None else {id(prototype_battle): prototype_battle}
    return _ResidentCharacterBirthRecipe(
        kind=recipe.kind,
        action_kind=recipe.action_kind,
        effective_name=recipe.effective_name,
        template_fingerprint=recipe.template_fingerprint,
        source_fingerprint=recipe.source_fingerprint,
        member_count=recipe.member_count,
        prototype=copy.deepcopy(recipe.prototype, memo),
        source_data=copy.deepcopy(recipe.source_data),
        card_stats_group=recipe.card_stats_group,
        uses_live_action_card_stats=recipe.uses_live_action_card_stats,
        formation_variant=recipe.formation_variant,
    )


@lru_cache(maxsize=4)
def _resident_card_catalog_bundle(
    data_file: str,
    modified_ns: int,
    file_size: int,
) -> _ResidentCardCatalogBundle:
    """Compile one immutable, fingerprinted resident card catalog revision."""
    del modified_ns, file_size
    from .arena import Position
    from .battle import BattleState
    from .card_aliases import CARD_NAME_ALIASES
    from .data import CardDataLoader
    from .factory.dynamic_factory import troop_from_character_data
    from .formations import formation_offset
    from .kinematics import tiles_to_logic_units
    from .spells import (
        SPELL_REGISTRY,
        DirectDamageSpell,
        ProjectileSpell,
        RollingProjectileSpell,
        RoyalDeliverySpell,
        SpawnProjectileSpell,
    )
    from .unit_traits import is_air_unit_card

    path = Path(data_file)
    loader = CardDataLoader(path)
    definitions = loader.load_card_definitions()
    prototype_battle = BattleState(card_loader=loader.clone_lazy())
    lookup_names = set(definitions)
    lookup_names.update(
        alias for alias, target in CARD_NAME_ALIASES.items() if target in definitions
    )
    cards: list[dict[str, Any]] = []
    death_spawn_templates: list[dict[str, Any]] = []
    seen_death_spawn_templates: set[str] = set()
    action_recipes: dict[str, _ResidentCharacterBirthRecipe] = {}
    action_member_recipes: dict[
        tuple[str, int, str], _ResidentCharacterBirthRecipe
    ] = {}
    death_spawn_recipes: dict[tuple[str, str], _ResidentCharacterBirthRecipe] = {}
    rolling_spawn_recipes: dict[
        tuple[str, str], _ResidentCharacterBirthRecipe
    ] = {}
    rolling_projectile_recipes: dict[str, _ResidentRollingProjectileRecipe] = {}
    spawn_projectile_spawn_recipes: dict[
        tuple[str, int, str], _ResidentCharacterBirthRecipe
    ] = {}
    spawn_projectile_recipes: dict[str, _ResidentSpawnProjectileRecipe] = {}
    for lookup_name in sorted(lookup_names):
        card_def = loader.get_card_definition(lookup_name)
        card_stats = loader.get_card(lookup_name)
        if card_def is None or card_stats is None:  # pragma: no cover - loader invariant
            continue
        serialized_kind = str(getattr(card_def, "kind", "") or "").casefold()
        action_kind = (
            "building"
            if serialized_kind == "building"
            else "troop"
            if serialized_kind == "troop"
            else "unsupported"
        )
        reasons = (
            _ordinary_building_capability_reasons(card_stats, card_def)
            if action_kind == "building"
            else _single_troop_capability_reasons(card_stats, card_def)
        )
        projectile_spell: dict[str, Any] | None = None
        rolling_projectile_spell: dict[str, Any] | None = None
        spawn_projectile_spell: dict[str, Any] | None = None
        direct_damage_spell: dict[str, Any] | None = None
        spell = SPELL_REGISTRY.get(str(card_stats.name))
        if type(spell) is DirectDamageSpell:
            action_kind = "direct_damage_spell"
            direct_values = (
                float(spell.radius),
                float(spell.damage),
                float(spell.stun_duration),
                float(spell.slow_duration),
                float(spell.slow_multiplier),
                float(spell.knockback_distance),
                float(spell.crown_tower_damage_multiplier),
            )
            crown_damage = (
                None
                if spell.crown_tower_damage is None
                else float(spell.crown_tower_damage)
            )
            direct_reasons: list[str] = []
            if bool(spell.requires_territory) or bool(spell.requires_walkable_target):
                direct_reasons.append("restricted_direct_damage_spell_placement")
            if int(getattr(card_stats, "deploy_w_tile_margin", 0) or 0) != 0:
                direct_reasons.append("direct_damage_spell_margin")
            if (
                not all(math.isfinite(value) for value in direct_values)
                or crown_damage is not None
                and not math.isfinite(crown_damage)
                or spell.radius <= 0.0
                or spell.damage <= 0.0
                or spell.stun_duration < 0.0
                or spell.slow_duration < 0.0
                or spell.slow_multiplier < 0.0
                or spell.slow_duration > 0.0
                and spell.slow_multiplier >= 1.0
                or spell.knockback_distance != 0.0
                or bool(spell.knockback_ignores_mass)
                or not (bool(spell.hits_air) and bool(spell.hits_ground))
                or spell.crown_tower_damage_multiplier < 0.0
                or crown_damage is not None
                and crown_damage < 0.0
            ):
                direct_reasons.append("invalid_direct_damage_spell")
            reasons = direct_reasons
            if not reasons:
                direct_damage_spell = {
                    "radius": float(spell.radius),
                    "damage": float(spell.damage),
                    "stun_duration": float(spell.stun_duration),
                    "slow_duration": float(spell.slow_duration),
                    "slow_multiplier": float(spell.slow_multiplier),
                    "hits_air": bool(spell.hits_air),
                    "hits_ground": bool(spell.hits_ground),
                    "affects_hidden": bool(spell.affects_hidden),
                    "crown_tower_damage_multiplier": float(
                        spell.crown_tower_damage_multiplier
                    ),
                    "crown_tower_damage": crown_damage,
                }
        elif type(spell) in (SpawnProjectileSpell, RoyalDeliverySpell):
            assert isinstance(spell, (SpawnProjectileSpell, RoyalDeliverySpell))
            action_kind = "spawn_projectile_spell"
            launch_from_king = type(spell) is SpawnProjectileSpell
            activation_delay = (
                0.0
                if launch_from_king
                else float(cast(RoyalDeliverySpell, spell).impact_delay)
            )
            spawn_radius_value = (
                getattr(spell, "spawn_radius", None)
                if launch_from_king
                else 0.0
            )
            spawn_radius = (
                None if spawn_radius_value is None else float(spawn_radius_value)
            )
            spawn_deploy_delay = (
                None
                if spell.spawn_deploy_delay is None
                else float(spell.spawn_deploy_delay)
            )
            spawn_character = str(spell.spawn_character or "")
            spawn_character_data = spell.spawn_character_data
            crown_damage = (
                None
                if spell.crown_tower_damage is None
                else float(spell.crown_tower_damage)
            )
            spawn_values = (
                float(spell.radius),
                float(spell.damage),
                float(spell.travel_speed),
                activation_delay,
                float(spell.crown_tower_damage_multiplier),
            )
            spawn_spell_reasons: list[str] = []
            inherited_projectile_payload = {
                "stun_duration": float(getattr(spell, "stun_duration", 0.0) or 0.0),
                "slow_duration": float(getattr(spell, "slow_duration", 0.0) or 0.0),
                "slow_multiplier": float(getattr(spell, "slow_multiplier", 1.0)),
                "knockback_distance": float(
                    getattr(spell, "knockback_distance", 0.0) or 0.0
                ),
                "knockback_ignores_mass": bool(
                    getattr(spell, "knockback_ignores_mass", False)
                ),
                "damage_waves": int(getattr(spell, "damage_waves", 1) or 1),
                "damage_wave_interval": float(
                    getattr(spell, "damage_wave_interval", 0.0) or 0.0
                ),
                "multiple_projectiles": int(
                    getattr(spell, "multiple_projectiles", 1) or 1
                ),
                "spread_radius": float(getattr(spell, "spread_radius", 0.0) or 0.0),
                "projectile_pattern": str(
                    getattr(spell, "projectile_pattern", "native_radial")
                ),
                "pierces": bool(getattr(spell, "pierces", False)),
                "homing": bool(getattr(spell, "homing", False)),
                "spawn_projectile_data_present": getattr(
                    spell, "spawn_projectile_data", None
                )
                is not None,
            }
            if bool(spell.requires_walkable_target):
                spawn_spell_reasons.append("spawn_projectile_walkable_placement")
            if int(getattr(card_stats, "deploy_w_tile_margin", 0) or 0) != 0:
                spawn_spell_reasons.append("spawn_projectile_margin")
            if (
                not all(math.isfinite(value) for value in spawn_values)
                or crown_damage is not None
                and not math.isfinite(crown_damage)
                or spell.radius < 0.0
                or spell.damage < 0.0
                or spell.travel_speed <= 0.0
                or activation_delay < 0.0
                or not 1 <= int(spell.spawn_count) <= 90
                or spawn_radius is not None
                and (not math.isfinite(spawn_radius) or spawn_radius < 0.0)
                or spawn_deploy_delay is not None
                and (
                    not math.isfinite(spawn_deploy_delay)
                    or spawn_deploy_delay < 0.0
                )
                or spell.crown_tower_damage_multiplier < 0.0
                or crown_damage is not None
                and crown_damage < 0.0
                or inherited_projectile_payload["stun_duration"] != 0.0
                or inherited_projectile_payload["slow_duration"] != 0.0
                or inherited_projectile_payload["slow_multiplier"] != 1.0
                or inherited_projectile_payload["knockback_distance"] != 0.0
                or inherited_projectile_payload["knockback_ignores_mass"]
                or inherited_projectile_payload["damage_waves"] != 1
                or inherited_projectile_payload["damage_wave_interval"] != 0.0
                or inherited_projectile_payload["multiple_projectiles"] != 1
                or inherited_projectile_payload["spread_radius"] != 0.0
                or inherited_projectile_payload["projectile_pattern"]
                != "native_radial"
                or inherited_projectile_payload["pierces"]
                or inherited_projectile_payload["homing"]
                or inherited_projectile_payload["spawn_projectile_data_present"]
            ):
                spawn_spell_reasons.append("invalid_spawn_projectile_spell")
            if (
                type(spawn_character_data) is not dict
                or not spawn_character_data
                or str(spawn_character_data.get("name") or "") != spawn_character
            ):
                spawn_spell_reasons.append("spawn_projectile_child_payload")

            normalized_spawn_data: Any = None
            spawn_data_fingerprint: str | None = None
            carrier_child_template_snapshot: dict[str, Any] | None = None
            carrier_child_template_fingerprint: str | None = None
            if not spawn_spell_reasons:
                try:
                    normalized_spawn_data = _normalize(spawn_character_data)
                    spawn_data_fingerprint = _canonical_json_sha256(
                        normalized_spawn_data
                    )
                    spawn_stats = troop_from_character_data(
                        spawn_character,
                        spawn_character_data,
                        elixir=0,
                        rarity=spawn_character_data.get("rarity", "Common"),
                    )
                    spawned_id = prototype_battle.next_entity_id
                    prototype_battle._spawn_unit_at_position(
                        Position(9.0, 8.0),
                        0,
                        spawn_stats,
                        deploy_delay_override=spawn_deploy_delay,
                        snap_to_valid=False,
                    )
                    prototype = prototype_battle.entities.pop(spawned_id)
                    carrier_child_template_snapshot = dict(_entity_snapshot(prototype))
                    carrier_child_template_fingerprint = _prototype_sha256(prototype)
                    for ordinal in range(int(spell.spawn_count)):
                        spawn_projectile_spawn_recipes[
                            (
                                str(spell.name),
                                ordinal,
                                carrier_child_template_fingerprint,
                            )
                        ] = _ResidentCharacterBirthRecipe(
                            kind="spawn_projectile_spawn",
                            action_kind="troop",
                            effective_name=spawn_character,
                            template_fingerprint=carrier_child_template_fingerprint,
                            source_fingerprint=spawn_data_fingerprint,
                            member_count=int(spell.spawn_count),
                            prototype=prototype,
                            source_data=copy.deepcopy(spawn_character_data),
                            card_stats_group=0,
                            # The provenance fingerprint authenticates the raw
                            # child payload here (as it does for rolling
                            # endpoint births), while publication still clones
                            # the attested prototype stats rather than consulting
                            # the live action-card wrapper.
                            uses_live_action_card_stats=True,
                        )
                except (OverflowError, TypeError, ValueError) as error:
                    spawn_spell_reasons.append(
                        f"spawn_projectile_template_compile:{type(error).__name__}"
                    )
            reasons = spawn_spell_reasons
            if not reasons:
                spawn_projectile_spell = {
                    "radius": float(spell.radius),
                    "damage": float(spell.damage),
                    "travel_speed": float(spell.travel_speed),
                    "activation_delay": activation_delay,
                    "spawn_count": int(spell.spawn_count),
                    "spawn_character": spawn_character,
                    "spawn_character_data": normalized_spawn_data,
                    "spawn_data_fingerprint": spawn_data_fingerprint,
                    "spawn_radius": spawn_radius,
                    "spawn_deploy_delay": spawn_deploy_delay,
                    "spawn_const_priority": (
                        bool(getattr(spell, "spawn_const_priority", False))
                        if launch_from_king
                        else False
                    ),
                    "launch_from_king": launch_from_king,
                    "requires_territory": bool(spell.requires_territory),
                    "hits_air": bool(getattr(spell, "hits_air", True)),
                    "hits_ground": bool(getattr(spell, "hits_ground", True)),
                    "ignore_buildings": (
                        False
                        if launch_from_king
                        else bool(cast(RoyalDeliverySpell, spell).ignore_buildings)
                    ),
                    "crown_tower_damage_multiplier": float(
                        spell.crown_tower_damage_multiplier
                    ),
                    "crown_tower_damage": crown_damage,
                    "spawn_template_snapshot": carrier_child_template_snapshot,
                    "spawn_template_fingerprint": carrier_child_template_fingerprint,
                    **inherited_projectile_payload,
                }
                recipe = _ResidentSpawnProjectileRecipe(
                    source_kind=str(spell.name),
                    damage=float(spell.damage),
                    radius=float(spell.radius),
                    travel_speed=float(spell.travel_speed),
                    activation_delay=activation_delay,
                    spawn_count=int(spell.spawn_count),
                    spawn_character=spawn_character,
                    spawn_character_data=copy.deepcopy(spawn_character_data),
                    spawn_data_fingerprint=cast(str, spawn_data_fingerprint),
                    spawn_radius=spawn_radius,
                    spawn_deploy_delay=spawn_deploy_delay,
                    spawn_const_priority=(
                        bool(getattr(spell, "spawn_const_priority", False))
                        if launch_from_king
                        else False
                    ),
                    launch_from_king=launch_from_king,
                    requires_territory=bool(spell.requires_territory),
                    hits_air=bool(getattr(spell, "hits_air", True)),
                    hits_ground=bool(getattr(spell, "hits_ground", True)),
                    ignore_buildings=(
                        False
                        if launch_from_king
                        else bool(cast(RoyalDeliverySpell, spell).ignore_buildings)
                    ),
                    crown_tower_damage_multiplier=float(
                        spell.crown_tower_damage_multiplier
                    ),
                    crown_tower_damage=crown_damage,
                )
                spawn_projectile_recipes[lookup_name] = recipe
                spawn_projectile_recipes[str(spell.name)] = recipe
        elif type(spell) is ProjectileSpell:
            action_kind = "projectile_spell"
            spell_values = (
                float(spell.radius),
                float(spell.damage),
                float(spell.travel_speed),
                float(spell.stun_duration),
                float(spell.slow_duration),
                float(spell.slow_multiplier),
                float(spell.knockback_distance),
                float(spell.crown_tower_damage_multiplier),
            )
            crown_damage = (
                None
                if spell.crown_tower_damage is None
                else float(spell.crown_tower_damage)
            )
            spell_reasons: list[str] = []
            projectile_count = max(1, int(spell.multiple_projectiles))
            wave_count = max(1, int(spell.damage_waves))
            grouped_ring = (
                projectile_count > 1
                and str(spell.projectile_pattern) == "grouped_ring"
                and wave_count >= 1
                and float(spell.damage_wave_interval) > 0.0
                and float(spell.spread_radius) > 0.0
                and float(spell.knockback_distance) == 0.0
                and float(spell.stun_duration) == 0.0
                and float(spell.slow_duration) == 0.0
            )
            single_projectile = (
                projectile_count == 1
                and wave_count == 1
                and float(spell.damage_wave_interval) == 0.0
                and str(spell.projectile_pattern) == "native_radial"
            )
            if not (single_projectile or grouped_ring):
                spell_reasons.append("unsupported_projectile_spell_pattern")
            if bool(spell.requires_territory) or bool(spell.requires_walkable_target):
                spell_reasons.append("restricted_projectile_spell_placement")
            if int(getattr(card_stats, "deploy_w_tile_margin", 0) or 0) != 0:
                spell_reasons.append("projectile_spell_margin")
            if float(spell.stun_duration) != 0.0 or float(spell.slow_duration) != 0.0:
                spell_reasons.append("projectile_spell_status")
            if (
                not all(math.isfinite(value) for value in spell_values)
                or crown_damage is not None
                and not math.isfinite(crown_damage)
                or spell.radius <= 0.0
                or spell.damage <= 0.0
                or spell.travel_speed <= 0.0
                or spell.knockback_distance < 0.0
            ):
                spell_reasons.append("invalid_projectile_spell")
            reasons = spell_reasons
            if not reasons:
                projectile_spell = {
                    "radius": float(spell.radius),
                    "damage": float(spell.damage),
                    "travel_speed": float(spell.travel_speed),
                    "stun_duration": float(spell.stun_duration),
                    "slow_duration": float(spell.slow_duration),
                    "slow_multiplier": float(spell.slow_multiplier),
                    "knockback_distance": float(spell.knockback_distance),
                    "knockback_ignores_mass": bool(spell.knockback_ignores_mass),
                    "hits_air": bool(spell.hits_air),
                    "hits_ground": bool(spell.hits_ground),
                    "crown_tower_damage_multiplier": float(
                        spell.crown_tower_damage_multiplier
                    ),
                    "crown_tower_damage": crown_damage,
                    "projectile_pattern": str(spell.projectile_pattern),
                    "multiple_projectiles": projectile_count,
                    "damage_waves": wave_count,
                    "damage_wave_interval": float(spell.damage_wave_interval),
                    "spread_radius": float(spell.spread_radius),
                }
        elif type(spell) is RollingProjectileSpell:
            action_kind = "rolling_projectile_spell"
            rolling_values = (
                float(spell.radius),
                float(spell.damage),
                float(spell.casting_speed),
                float(spell.casting_min_distance),
                float(spell.projectile_range),
                float(spell.radius_y),
                float(spell.knockback_distance),
                float(spell.crown_tower_damage_multiplier),
            )
            crown_damage = (
                None
                if spell.crown_tower_damage is None
                else float(spell.crown_tower_damage)
            )
            spawn_character = str(spell.spawn_character or "")
            spawn_character_data = dict(spell.spawn_character_data or {})
            spawn_deploy_delay = (
                None
                if spell.spawn_deploy_delay is None
                else float(spell.spawn_deploy_delay)
            )
            spell_reasons = []
            if not bool(spell.requires_territory) or bool(
                spell.requires_walkable_target
            ):
                spell_reasons.append("rolling_projectile_placement")
            if int(getattr(card_stats, "deploy_w_tile_margin", 0) or 0) != 0:
                spell_reasons.append("rolling_projectile_margin")
            if (
                not all(math.isfinite(value) for value in rolling_values)
                or crown_damage is not None
                and not math.isfinite(crown_damage)
                or spell.radius <= 0.0
                or spell.damage <= 0.0
                or spell.casting_speed <= 0.0
                or spell.casting_min_distance < 0.0
                or type(spell.travel_speed) is not int
                or spell.travel_speed <= 0
                or spell.projectile_range <= 0.0
                or spell.radius_y < 0.0
                or spell.knockback_distance < 0.0
                or spell.crown_tower_damage_multiplier < 0.0
                or crown_damage is not None
                and crown_damage < 0.0
            ):
                spell_reasons.append("invalid_rolling_projectile_spell")
            if bool(spawn_character) != bool(spawn_character_data):
                spell_reasons.append("rolling_projectile_spawn_payload")
            elif spawn_character and str(spawn_character_data.get("name") or "") != (
                spawn_character
            ):
                spell_reasons.append("rolling_projectile_spawn_name")
            if spawn_deploy_delay is not None and (
                not math.isfinite(spawn_deploy_delay) or spawn_deploy_delay < 0.0
            ):
                spell_reasons.append("invalid_rolling_projectile_spawn_delay")

            spawn_template_snapshot: dict[str, Any] | None = None
            spawn_template_fingerprint: str | None = None
            normalized_spawn_data = _normalize(spawn_character_data)
            spawn_data_fingerprint = _canonical_json_sha256(normalized_spawn_data)
            spawn_recipe: _ResidentCharacterBirthRecipe | None = None
            if not spell_reasons and spawn_character:
                try:
                    spawn_stats = troop_from_character_data(
                        spawn_character,
                        spawn_character_data,
                        elixir=0,
                        rarity=spawn_character_data.get("rarity", "Common"),
                    )
                    spawned_id = prototype_battle.next_entity_id
                    prototype_battle._spawn_unit_at_position(
                        Position(9.0, 8.0),
                        0,
                        spawn_stats,
                        deploy_delay_override=spawn_deploy_delay,
                        snap_to_valid=False,
                    )
                    prototype = prototype_battle.entities.pop(spawned_id)
                    spawn_template_snapshot = dict(_entity_snapshot(prototype))
                    spawn_template_fingerprint = _prototype_sha256(prototype)
                    spawn_recipe = _ResidentCharacterBirthRecipe(
                        kind="rolling_spawn",
                        action_kind="troop",
                        effective_name=spawn_character,
                        template_fingerprint=spawn_template_fingerprint,
                        source_fingerprint=spawn_data_fingerprint,
                        member_count=1,
                        prototype=prototype,
                        source_data=copy.deepcopy(spawn_character_data),
                    )
                except (OverflowError, TypeError, ValueError) as error:
                    spell_reasons.append(
                        f"rolling_spawn_template_compile:{type(error).__name__}"
                    )
            reasons = spell_reasons
            if not reasons:
                rolling_projectile_spell = {
                    "radius": float(spell.radius),
                    "damage": float(spell.damage),
                    "casting_speed": float(spell.casting_speed),
                    "casting_min_distance": float(spell.casting_min_distance),
                    "travel_speed": int(spell.travel_speed),
                    "projectile_range": float(spell.projectile_range),
                    "radius_y": float(spell.radius_y),
                    "knockback_distance": float(spell.knockback_distance),
                    "knockback_ignores_mass": bool(spell.knockback_ignores_mass),
                    "crown_tower_damage_multiplier": float(
                        spell.crown_tower_damage_multiplier
                    ),
                    "crown_tower_damage": crown_damage,
                    "spawn_character": spawn_character or None,
                    "spawn_character_data": normalized_spawn_data,
                    "spawn_deploy_delay": spawn_deploy_delay,
                    "spawn_data_fingerprint": spawn_data_fingerprint,
                    "spawn_template_snapshot": spawn_template_snapshot,
                    "spawn_template_fingerprint": spawn_template_fingerprint,
                }
                if spawn_recipe is not None:
                    rolling_spawn_recipes[
                        (
                            str(spell.name),
                            spawn_recipe.template_fingerprint.lower(),
                        )
                    ] = spawn_recipe
                rolling_projectile_recipes[str(spell.name)] = (
                    _ResidentRollingProjectileRecipe(
                        source_kind=str(spell.name),
                        spawn_character=spawn_character or None,
                        spawn_character_data=copy.deepcopy(spawn_character_data),
                        spawn_data_fingerprint=spawn_data_fingerprint,
                        spawn_deploy_delay=spawn_deploy_delay,
                    )
                )
        template_snapshot: dict[str, Any] | None = None
        template_fingerprint: str | None = None
        formation_offsets: list[list[list[int]]] = []
        deploy_delay_offsets: list[float] = []
        mixed_formation_members: list[list[dict[str, Any]]] = []
        catalog_summon_count = int(
            getattr(card_stats, "summon_count", None) or 1
        )
        second_count = int(
            getattr(card_stats, "summon_character_second_count", None) or 0
        )
        if (
            not reasons
            and projectile_spell is None
            and action_kind == "troop"
            and second_count > 0
        ):
            catalog_summon_count += second_count
            compiled_member_keys: list[tuple[str, int, str]] = []
            try:
                for variant_index, (player_id, lane_x) in enumerate(
                    (
                        (0, 4.0),
                        (0, 14.0),
                        (1, 4.0),
                        (1, 14.0),
                    )
                ):
                    formation_battle = BattleState(card_loader=loader.clone_lazy())
                    formation_stats = formation_battle.card_loader.get_card(lookup_name)
                    if formation_stats is None:
                        raise ValueError("mixed formation card disappeared")
                    anchor = Position(lane_x, 8.0 if player_id == 0 else 24.0)
                    before_ids = set(formation_battle.entities)
                    formation_battle._spawn_troop(
                        anchor,
                        player_id,
                        formation_stats,
                    )
                    spawned = [
                        entity
                        for entity_id, entity in formation_battle.entities.items()
                        if entity_id not in before_ids
                    ]
                    if len(spawned) != catalog_summon_count:
                        raise ValueError("mixed formation member count changed")
                    stats_groups: dict[int, int] = {}
                    members: list[dict[str, Any]] = []
                    for ordinal, entity in enumerate(spawned):
                        stats_identity = id(entity.card_stats)
                        stats_group = stats_groups.setdefault(
                            stats_identity,
                            len(stats_groups),
                        )
                        snapshot = dict(_entity_snapshot(entity))
                        fingerprint = _prototype_sha256(entity)
                        effective_name = str(entity.card_stats.name)
                        stats_fingerprint = _normalized_sha256(entity.card_stats)
                        member_row = {
                            "offset": [
                                tiles_to_logic_units(entity.position.x - anchor.x),
                                tiles_to_logic_units(entity.position.y - anchor.y),
                            ],
                            "deploy_delay": float(entity.deploy_delay_remaining),
                            "effective_name": effective_name,
                            "template_snapshot": snapshot,
                            "template_fingerprint": fingerprint,
                            "card_stats_group": stats_group,
                            "card_stats_fingerprint": stats_fingerprint,
                        }
                        recipe_key = (lookup_name, ordinal, fingerprint)
                        action_member_recipes[recipe_key] = (
                            _ResidentCharacterBirthRecipe(
                                kind="catalog_action",
                                action_kind="troop",
                                effective_name=effective_name,
                                template_fingerprint=fingerprint,
                                source_fingerprint=stats_fingerprint,
                                member_count=catalog_summon_count,
                                prototype=entity,
                                card_stats_group=stats_group,
                                uses_live_action_card_stats=False,
                                formation_variant=variant_index,
                            )
                        )
                        compiled_member_keys.append(recipe_key)
                        members.append(member_row)
                    if sorted(set(stats_groups.values())) != list(
                        range(len(stats_groups))
                    ):
                        raise ValueError("mixed formation stats groups changed")
                    mixed_formation_members.append(members)
            except (OverflowError, TypeError, ValueError) as error:
                reasons.append(f"mixed_formation_compile:{type(error).__name__}")
                mixed_formation_members = []
                for recipe_key in compiled_member_keys:
                    action_member_recipes.pop(recipe_key, None)
        elif not reasons and projectile_spell is None and action_kind == "troop":
            summon_count = int(getattr(card_stats, "summon_count", None) or 1)
            summon_radius = getattr(card_stats, "summon_radius", None)
            formation_radius = (
                float(summon_radius)
                if summon_radius is not None
                else float(getattr(card_stats, "collision_radius", 0.5) or 0.5)
            )
            angle_shift = float(
                getattr(card_stats, "spawn_angle_shift", 0.0) or 0.0
            )
            try:
                for player_id in (0, 1):
                    for lane_id in (1, 2):
                        formation_offsets.append(
                            [
                                [
                                    tiles_to_logic_units(offset_x),
                                    tiles_to_logic_units(offset_y),
                                ]
                                for index in range(summon_count)
                                for offset_x, offset_y in (
                                    formation_offset(
                                        index,
                                        summon_count,
                                        formation_radius,
                                        player_id,
                                        angle_shift_degrees=angle_shift,
                                        lane_id=lane_id,
                                    ),
                                )
                            ]
                        )
                summon_deploy_delay = float(
                    getattr(card_stats, "summon_deploy_delay", 0.0) or 0.0
                )
                deploy_delay_offsets = [
                    index * summon_deploy_delay / 1000.0
                    for index in range(summon_count)
                ]
                spawned_id = prototype_battle.next_entity_id
                prototype_battle._spawn_unit_at_position(
                    Position(9.0, 8.0),
                    0,
                    card_stats,
                    snap_to_valid=False,
                )
                prototype = prototype_battle.entities.pop(spawned_id)
                template_snapshot = dict(_entity_snapshot(prototype))
                template_fingerprint = _prototype_sha256(prototype)
                formation_runtime_supported = True
                if summon_count > 1:
                    for variant_index, (player_id, lane_x) in enumerate(
                        ((0, 4.0), (0, 14.0), (1, 4.0), (1, 14.0))
                    ):
                        formation_battle = BattleState(card_loader=loader.clone_lazy())
                        anchor = Position(lane_x, 8.0 if player_id == 0 else 24.0)
                        before_ids = set(formation_battle.entities)
                        formation_battle._spawn_troop(anchor, player_id, card_stats)
                        spawned = [
                            entity
                            for entity_id, entity in formation_battle.entities.items()
                            if entity_id not in before_ids
                        ]
                        expected_offsets = formation_offsets[variant_index]
                        if len(spawned) != summon_count:
                            formation_runtime_supported = False
                            break
                        for index, entity in enumerate(spawned):
                            offset_x, offset_y = expected_offsets[index]
                            expected_x = (
                                tiles_to_logic_units(anchor.x) + offset_x
                            ) / 1000.0
                            expected_y = (
                                tiles_to_logic_units(anchor.y) + offset_y
                            ) / 1000.0
                            expected_delay = (
                                prototype.deploy_delay_remaining
                                + deploy_delay_offsets[index]
                            )
                            if (
                                type(entity) is not type(prototype)
                                or str(entity.card_stats.name)
                                != str(prototype.card_stats.name)
                                or float(entity.position.x).hex()
                                != float(expected_x).hex()
                                or float(entity.position.y).hex()
                                != float(expected_y).hex()
                                or float(entity.deploy_delay_remaining).hex()
                                != float(expected_delay).hex()
                            ):
                                formation_runtime_supported = False
                                break
                        if not formation_runtime_supported:
                            break
                if not formation_runtime_supported:
                    reasons.append("formation_runtime_preflight")
                action_recipes[lookup_name] = _ResidentCharacterBirthRecipe(
                    kind="catalog_action",
                    action_kind="troop",
                    effective_name=str(card_stats.name),
                    template_fingerprint=template_fingerprint,
                    source_fingerprint=None,
                    member_count=summon_count,
                    prototype=prototype,
                )
            except (OverflowError, TypeError, ValueError) as error:
                reasons.append(f"formation_compile:{type(error).__name__}")
                formation_offsets = []
                deploy_delay_offsets = []
        elif not reasons and action_kind == "building":
            try:
                spawned_id = prototype_battle.next_entity_id
                prototype_battle._spawn_entity(
                    Building,
                    Position(9.0, 8.0),
                    0,
                    card_stats,
                )
                prototype = prototype_battle.entities.pop(spawned_id)
                template_snapshot = dict(_entity_snapshot(prototype))
                template_fingerprint = _prototype_sha256(prototype)
                action_recipes[lookup_name] = _ResidentCharacterBirthRecipe(
                    kind="catalog_action",
                    action_kind="building",
                    effective_name=str(card_stats.name),
                    template_fingerprint=template_fingerprint,
                    source_fingerprint=None,
                    member_count=1,
                    prototype=prototype,
                )
            except (OverflowError, TypeError, ValueError) as error:
                reasons.append(f"building_template_compile:{type(error).__name__}")
        building_footprint_size: int | None = None
        if action_kind == "building":
            raw_collision_radius = getattr(card_stats, "collision_radius", None)
            collision_radius = (
                1.0
                if raw_collision_radius is None
                else float(raw_collision_radius)
            )
            building_footprint_size = max(
                1,
                math.ceil(max(0.0, collision_radius) * 2.0) + 1,
            )
        cards.append(
            {
                "lookup_name": lookup_name,
                "effective_name": str(card_stats.name),
                "action_kind": action_kind,
                "building_footprint_size": building_footprint_size,
                "mana_cost": float(card_stats.mana_cost),
                "can_deploy_on_enemy_side": bool(
                    getattr(card_stats, "can_deploy_on_enemy_side", False)
                ),
                "deploy_w_tile_margin": int(
                    getattr(card_stats, "deploy_w_tile_margin", 0) or 0
                ),
                "symmetric_deploy_snap": bool(
                    action_kind == "troop"
                    and not is_air_unit_card(card_stats)
                    and float(getattr(card_stats, "speed", 0) or 0) > 0.0
                    and int(
                        (getattr(card_stats, "summon_character_data", {}) or {}).get(
                            "dashCooldown", 0
                        )
                        or 0
                    )
                    == 0
                ),
                "summon_count": int(
                    catalog_summon_count
                ),
                "formation_offsets": formation_offsets,
                "deploy_delay_offsets": deploy_delay_offsets,
                "mixed_formation_members": mixed_formation_members,
                "capability_reasons": reasons,
                "template_snapshot": template_snapshot,
                "template_fingerprint": template_fingerprint,
                "projectile_spell": projectile_spell,
                "rolling_projectile_spell": rolling_projectile_spell,
                "spawn_projectile_spell": spawn_projectile_spell,
                "direct_damage_spell": direct_damage_spell,
            }
        )
        death_spawn_data = getattr(card_stats, "death_spawn_character_data", None)
        death_spawn_name = str(
            getattr(card_stats, "death_spawn_character", "") or ""
        )
        if (
            death_spawn_name
            and death_spawn_data
            and death_spawn_data.get("hitpoints") is not None
        ):
            normalized_unit_data = _normalize(death_spawn_data)
            template_key = json.dumps(
                [death_spawn_name, normalized_unit_data],
                sort_keys=True,
                separators=(",", ":"),
            )
            if template_key not in seen_death_spawn_templates:
                seen_death_spawn_templates.add(template_key)
                child_stats = troop_from_character_data(
                    death_spawn_name,
                    death_spawn_data,
                    elixir=0,
                    rarity=death_spawn_data.get("rarity", "Common"),
                )
                spawned_id = prototype_battle.next_entity_id
                prototype_battle._spawn_unit_at_position(
                    Position(9.0, 8.0),
                    0,
                    child_stats,
                    snap_to_valid=False,
                )
                child_prototype = prototype_battle.entities.pop(spawned_id)
                child_template_snapshot = dict(_entity_snapshot(child_prototype))
                death_template_fingerprint = _prototype_sha256(child_prototype)
                death_spawn_templates.append(
                    {
                        "unit_name": death_spawn_name,
                        "unit_data": normalized_unit_data,
                        "template_snapshot": child_template_snapshot,
                        "template_fingerprint": death_template_fingerprint,
                    }
                )
                death_spawn_recipes[(death_spawn_name, death_template_fingerprint)] = (
                    _ResidentCharacterBirthRecipe(
                        kind="death_spawn",
                        action_kind="troop",
                        effective_name=death_spawn_name,
                        template_fingerprint=death_template_fingerprint,
                        source_fingerprint=_canonical_json_sha256(
                            normalized_unit_data
                        ),
                        member_count=None,
                        prototype=child_prototype,
                    )
                )
    payload = {
        "schema_version": RESIDENT_CARD_CATALOG_SCHEMA_VERSION,
        "source_fingerprint": _catalog_source_sha256(path),
        "cards": cards,
        "death_spawn_templates": death_spawn_templates,
    }
    return _ResidentCardCatalogBundle(
        payload=json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii"),
        action_recipes=action_recipes,
        death_spawn_recipes=death_spawn_recipes,
        action_member_recipes=action_member_recipes,
        rolling_spawn_recipes=rolling_spawn_recipes,
        rolling_projectile_recipes=rolling_projectile_recipes,
        spawn_projectile_spawn_recipes=spawn_projectile_spawn_recipes,
        spawn_projectile_recipes=spawn_projectile_recipes,
        pending_spell_action_kinds=tuple(
            (str(card["lookup_name"]), str(card["action_kind"]))
            for card in cards
            if not card["capability_reasons"]
            and card["action_kind"]
            in {
                "projectile_spell",
                "rolling_projectile_spell",
                "spawn_projectile_spell",
                "direct_damage_spell",
            }
        ),
    )


def _resident_card_catalog_bytes(
    data_file: str,
    modified_ns: int,
    file_size: int,
) -> bytes:
    return _resident_card_catalog_bundle(
        data_file,
        modified_ns,
        file_size,
    ).payload


def rust_core_available() -> bool:
    return (
        _noop_ticks is not None
        and _consume_state_bytes is not None
        and _ResidentBattle is not None
        and _standard_grid_route is not None
    )


def require_rust_core() -> None:
    if not rust_core_available():
        raise RuntimeError(
            "optional Rust core is not installed; run "
            "`maturin develop --manifest-path rust/clasher-core/Cargo.toml`"
        )


def rust_noop_ticks(ticks: int) -> int:
    require_rust_core()
    if ticks < 0 or ticks > (1 << 32) - 1:
        raise ValueError("ticks must fit in u32")
    assert _noop_ticks is not None
    return int(_noop_ticks(ticks))


def python_consume_state_bytes(payload: bytes) -> tuple[int, int]:
    hash_value = FNV_OFFSET_BASIS
    for byte in payload:
        hash_value = ((hash_value ^ byte) * FNV_PRIME) & U64_MASK
    return len(payload), hash_value


def rust_consume_state_bytes(payload: bytes) -> tuple[int, int]:
    require_rust_core()
    assert _consume_state_bytes is not None
    size, hash_value = _consume_state_bytes(payload)
    return int(size), int(hash_value)


def rust_standard_grid_route(
    start: tuple[int, int],
    goal: tuple[int, int],
    lane_id: int,
    jump_height: bool,
) -> tuple[tuple[int, int], ...] | None:
    require_rust_core()
    assert _standard_grid_route is not None
    route = _standard_grid_route(start, goal, lane_id, jump_height)
    if route is None:
        return None
    return tuple((int(cell[0]), int(cell[1])) for cell in route)


class RustBattleMode(str, Enum):
    OFF = "off"
    SHADOW = "shadow"
    ON = "on"


class ResidentPreviewTickError(RuntimeError):
    """An unpublished resident candidate failed after applying joint actions."""


@dataclass(frozen=True)
class BattleClockState:
    tick: int
    time: float
    dt: float
    double_elixir: bool
    triple_elixir: bool
    overtime: bool
    game_over: bool

    def sha256(self) -> str:
        payload = struct.pack(
            "<qdd????",
            self.tick,
            self.time,
            self.dt,
            self.double_elixir,
            self.triple_elixir,
            self.overtime,
            self.game_over,
        )
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ResidentPlayerState:
    player_id: int
    elixir: float
    max_elixir: float
    next_card_refill_cooldown_ms: int
    hand: tuple[str | None, ...]
    cycle_queue: tuple[str, ...]
    king_tower_hp: float
    left_tower_hp: float
    right_tower_hp: float

    def append_hash_payload(self, payload: bytearray) -> None:
        payload.extend(struct.pack("<qddqQ", self.player_id, self.elixir, self.max_elixir, self.next_card_refill_cooldown_ms, len(self.hand)))
        for card in self.hand:
            if card is None:
                payload.append(0)
            else:
                payload.append(1)
                _append_string(payload, card)
        payload.extend(struct.pack("<Q", len(self.cycle_queue)))
        for card in self.cycle_queue:
            _append_string(payload, card)
        payload.extend(
            struct.pack(
                "<ddd",
                self.king_tower_hp,
                self.left_tower_hp,
                self.right_tower_hp,
            )
        )


@dataclass(frozen=True)
class ResidentTowerState:
    id: int
    player_id: int
    slot: str
    hp: float
    hp_milli: int
    is_alive: bool
    is_active: bool
    last_attack_time: float

    def append_hash_payload(self, payload: bytearray) -> None:
        payload.extend(struct.pack("<qq", self.id, self.player_id))
        _append_string(payload, self.slot)
        payload.extend(
            struct.pack(
                "<dq??d",
                self.hp,
                self.hp_milli,
                self.is_alive,
                self.is_active,
                self.last_attack_time,
            )
        )


@dataclass(frozen=True)
class ResidentOutcomeState:
    sudden_death: bool
    game_over: bool
    winner: int | None
    sudden_death_crowns: tuple[int, int]


def _freeze_prepared_value(value: Any) -> Any:
    """Recursively detach mutable PyO3 containers from a prepared boundary."""
    if isinstance(value, dict):
        return MappingProxyType(
            {str(key): _freeze_prepared_value(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_prepared_value(item) for item in value)
    return value


def _decode_prepared_publication_parts(value: Any) -> MappingProxyType[str, Any]:
    frozen = _freeze_prepared_value(value)
    if not isinstance(frozen, MappingProxyType):
        raise TypeError("resident prepared publication parts are not a mapping")
    if frozen.get("version") != 1:
        raise ValueError("unsupported resident prepared publication version")
    binding = frozen.get("binding")
    if not isinstance(binding, MappingProxyType):
        raise TypeError("resident prepared publication binding is not a mapping")
    if binding.get("semantic_schema_version") != RESIDENT_PREPARED_SEMANTIC_SCHEMA_VERSION:
        raise ValueError("unsupported resident prepared semantic schema")
    return frozen


_PREPARED_PUBLICATION_AUTHORITY: Final = object()
_PREPARED_PUBLICATION_RAW_CONSUMER: Final = object()
_PREPARED_PUBLICATION_DELTA_CONSUMER: Final = object()
_PREPARED_PUBLICATION_BEST_CONSUMER: Final = object()


class ResidentPreparedPublication:
    """Single-use owner for one authenticated native publication projection.

    Stage 1 intentionally does not apply these parts to a Python battle. The
    binding carried by the parts is the future consume-time authority: runtime
    cutover must compare it with the live prior registry/boundary before any
    mutation. Making the crossing single-use prevents accidental replay while
    that final consumer is still deferred.
    """

    __slots__ = (
        "_action_card_stats",
        "_birth_catalog",
        "_consumed",
        "_native",
    )

    def __init__(
        self,
        native: Any,
        birth_catalog: _ResidentCardCatalogBundle | None,
        action_card_stats: dict[str, _ResidentActionCardStatsAttestation] | None,
        *,
        authority: object,
    ) -> None:
        if authority is not _PREPARED_PUBLICATION_AUTHORITY:
            raise TypeError("ResidentPreparedPublication is runtime-owned")
        self._native = native
        self._birth_catalog = birth_catalog
        self._action_card_stats = action_card_stats
        self._consumed = False

    def __setattr__(self, name: str, value: Any) -> None:
        if hasattr(self, name):
            raise AttributeError("ResidentPreparedPublication is immutable")
        object.__setattr__(self, name, value)

    def parts(self) -> MappingProxyType[str, Any]:
        """Cross native state once and return recursively frozen typed parts."""
        if self._consumed:
            raise RuntimeError("resident prepared publication was already consumed")
        object.__setattr__(self, "_consumed", True)
        return _decode_prepared_publication_parts(self._native.parts())

    def _consume_raw_parts(self, authority: object) -> dict[str, Any]:
        """Return the native graph once to the trusted publication consumer."""
        if authority is not _PREPARED_PUBLICATION_RAW_CONSUMER:
            raise TypeError("raw prepared publication consumption is runtime-owned")
        if self._consumed:
            raise RuntimeError("resident prepared publication was already consumed")
        object.__setattr__(self, "_consumed", True)
        value = self._native.parts()
        if type(value) is not dict:
            raise TypeError("resident prepared publication parts are not a mapping")
        if value.get("version") != 1:
            raise ValueError("unsupported resident prepared publication version")
        binding = value.get("binding")
        if type(binding) is not dict:
            raise TypeError("resident prepared publication binding is not a mapping")
        if (
            binding.get("semantic_schema_version")
            != RESIDENT_PREPARED_SEMANTIC_SCHEMA_VERSION
        ):
            raise ValueError("unsupported resident prepared semantic schema")
        return cast(dict[str, Any], value)

    def _consume_delta_parts(self, authority: object) -> dict[str, Any]:
        """Return one native field-group delta to the trusted test decoder."""
        if authority is not _PREPARED_PUBLICATION_DELTA_CONSUMER:
            raise TypeError("delta prepared publication consumption is runtime-owned")
        if self._consumed:
            raise RuntimeError("resident prepared publication was already consumed")
        object.__setattr__(self, "_consumed", True)
        value = self._native.delta_parts()
        if type(value) is not dict:
            raise TypeError("resident prepared publication delta is not a mapping")
        if value.get("version") != 1:
            raise ValueError("unsupported resident prepared delta version")
        binding = value.get("binding")
        if type(binding) is not dict:
            raise TypeError(
                "resident prepared publication delta binding is not a mapping"
            )
        if (
            binding.get("semantic_schema_version")
            != RESIDENT_PREPARED_SEMANTIC_SCHEMA_VERSION
        ):
            raise ValueError("unsupported resident prepared delta semantic schema")
        return cast(dict[str, Any], value)

    def _consume_best_parts(self, authority: object) -> dict[str, Any]:
        """Return one native-selected full-or-delta graph to production."""
        if authority is not _PREPARED_PUBLICATION_BEST_CONSUMER:
            raise TypeError("best prepared publication consumption is runtime-owned")
        if self._consumed:
            raise RuntimeError("resident prepared publication was already consumed")
        object.__setattr__(self, "_consumed", True)
        value = self._native.best_parts()
        if type(value) is not dict or set(value) != {
            "version",
            "kind",
            "full",
            "delta",
        }:
            raise TypeError("resident best publication envelope is malformed")
        if (
            type(value["version"]) is not int
            or value["version"] != 1
            or type(value["kind"]) is not int
        ):
            raise ValueError("unsupported resident best publication version")
        if value["kind"] == 0:
            if type(value["full"]) is not dict or value["delta"] is not None:
                raise ValueError("resident best full publication is malformed")
        elif value["kind"] == 1:
            if type(value["delta"]) is not dict or value["full"] is not None:
                raise ValueError("resident best delta publication is malformed")
        else:
            raise ValueError("resident best publication kind is unsupported")
        return cast(dict[str, Any], value)


def _append_string(payload: bytearray, value: str) -> None:
    encoded = value.encode("utf-8")
    payload.extend(struct.pack("<Q", len(encoded)))
    payload.extend(encoded)


class ResidentRustBattle:
    """Python owner for one long-lived native battle allocation.

    A complete canonical checkpoint crosses the boundary only at construction
    or an explicit checkpoint replacement. Ordinary phase methods operate on
    resident Rust fields. Complete-tick ``on`` mode remains fail-closed until
    every phase has been ported and the extension advertises that capability.
    """

    def __init__(
        self,
        native: Any,
        birth_catalog: _ResidentCardCatalogBundle | None = None,
        action_card_stats: dict[
            str,
            _ResidentActionCardStatsAttestation,
        ]
        | None = None,
    ) -> None:
        self._native = native
        self._birth_catalog = birth_catalog
        self._action_card_stats = action_card_stats

    def fork(self) -> ResidentRustBattle:
        """Clone all resident mutable state without Python-state marshalling."""
        return type(self)(
            self._native.fork(),
            self._birth_catalog,
            self._action_card_stats,
        )

    def prepare_publication(
        self,
        prior: ResidentRustBattle,
    ) -> ResidentPreparedPublication:
        """Authenticate and freeze a direct native child against its prior."""
        if self._birth_catalog is not prior._birth_catalog:
            raise ValueError("prepared publication uses a different Python birth catalog")
        if self._action_card_stats is not prior._action_card_stats:
            raise ValueError(
                "prepared publication uses different Python action-card attestations"
            )
        return ResidentPreparedPublication(
            self._native.prepare_publication(prior._native),
            self._birth_catalog,
            self._action_card_stats,
            authority=_PREPARED_PUBLICATION_AUTHORITY,
        )

    def character_action_birth_recipe(
        self,
        lookup_name: str,
        template_fingerprint: str | None = None,
        ordinal: int | None = None,
    ) -> _ResidentCharacterBirthRecipe | None:
        catalog = self._birth_catalog
        if catalog is None:  # pragma: no cover - legacy direct construction
            return None
        normalized_lookup = str(lookup_name)
        recipe = (
            catalog.action_member_recipes.get(
                (
                    normalized_lookup,
                    int(ordinal),
                    str(template_fingerprint).lower(),
                )
            )
            if ordinal is not None and template_fingerprint is not None
            else None
        )
        if recipe is None:
            recipe = catalog.action_recipes.get(normalized_lookup)
        return None if recipe is None else _copy_attested_birth_recipe(recipe)

    def character_action_card_stats_are_current(
        self,
        battle: Any,
        lookup_name: str,
    ) -> bool:
        attestations = self._action_card_stats
        if attestations is None:  # pragma: no cover - legacy direct construction
            return False
        attestation = attestations.get(str(lookup_name))
        if attestation is None:
            return False
        current = battle.card_loader.get_card(str(lookup_name))
        return (
            current is attestation.card_stats
            and _normalized_sha256(current) == attestation.fingerprint
        )

    def character_death_spawn_birth_recipe(
        self,
        unit_name: str,
        template_fingerprint: str,
    ) -> _ResidentCharacterBirthRecipe | None:
        catalog = self._birth_catalog
        if catalog is None:  # pragma: no cover - legacy direct construction
            return None
        recipe = catalog.death_spawn_recipes.get(
            (str(unit_name), str(template_fingerprint).lower())
        )
        return None if recipe is None else _copy_attested_birth_recipe(recipe)

    def character_rolling_spawn_birth_recipe(
        self,
        spell_name: str,
        template_fingerprint: str,
    ) -> _ResidentCharacterBirthRecipe | None:
        """Return an attested endpoint child recipe for one rolling spell."""
        catalog = self._birth_catalog
        if catalog is None:  # pragma: no cover - legacy direct construction
            return None
        recipe = catalog.rolling_spawn_recipes.get(
            (str(spell_name), str(template_fingerprint).lower())
        )
        return None if recipe is None else _copy_attested_birth_recipe(recipe)

    def rolling_spawn_recipe_for_spell(
        self, spell_name: str
    ) -> _ResidentCharacterBirthRecipe | None:
        """Return the sole attested endpoint recipe for a rolling spell."""
        catalog = self._birth_catalog
        if catalog is None:  # pragma: no cover - legacy direct construction
            return None
        matches = [
            recipe
            for (candidate, _), recipe in catalog.rolling_spawn_recipes.items()
            if candidate == str(spell_name)
        ]
        if len(matches) != 1:
            return None
        return _copy_attested_birth_recipe(matches[0])

    def rolling_projectile_recipe(
        self, spell_name: str
    ) -> _ResidentRollingProjectileRecipe | None:
        """Return exact constructor-only state for one rolling spell object."""
        catalog = self._birth_catalog
        if catalog is None:  # pragma: no cover - legacy direct construction
            return None
        recipe = catalog.rolling_projectile_recipes.get(str(spell_name))
        if recipe is None:
            return None
        return _ResidentRollingProjectileRecipe(
            source_kind=recipe.source_kind,
            spawn_character=recipe.spawn_character,
            spawn_character_data=copy.deepcopy(recipe.spawn_character_data),
            spawn_data_fingerprint=recipe.spawn_data_fingerprint,
            spawn_deploy_delay=recipe.spawn_deploy_delay,
        )

    def character_spawn_projectile_birth_recipe(
        self,
        spell_name: str,
        template_fingerprint: str,
        ordinal: int,
    ) -> _ResidentCharacterBirthRecipe | None:
        catalog = self._birth_catalog
        if catalog is None:  # pragma: no cover - legacy direct construction
            return None
        recipe = catalog.spawn_projectile_spawn_recipes.get(
            (str(spell_name), int(ordinal), str(template_fingerprint).lower())
        )
        return None if recipe is None else _copy_attested_birth_recipe(recipe)

    def spawn_projectile_recipe(
        self, spell_name: str
    ) -> _ResidentSpawnProjectileRecipe | None:
        catalog = self._birth_catalog
        if catalog is None:  # pragma: no cover - legacy direct construction
            return None
        recipe = catalog.spawn_projectile_recipes.get(str(spell_name))
        return None if recipe is None else replace(
            recipe,
            spawn_character_data=copy.deepcopy(recipe.spawn_character_data),
        )

    def pending_spell_action_kind(self, spell_name: str) -> str | None:
        """Return the attested placement family for a supported pending spell."""
        catalog = self._birth_catalog
        if catalog is None:  # pragma: no cover - legacy direct construction
            return None
        expected_name = str(spell_name)
        for lookup_name, action_kind in catalog.pending_spell_action_kinds:
            if lookup_name == expected_name:
                return action_kind
        return None

    @classmethod
    def from_battle(cls, battle: Any) -> ResidentRustBattle:
        require_rust_core()
        checkpoint = snapshot_bytes(canonical_battle_snapshot(battle))
        data_path = Path(battle.card_loader.data_file)
        data_stat = data_path.stat()
        catalog = _resident_card_catalog_bundle(
            str(data_path.resolve()),
            data_stat.st_mtime_ns,
            data_stat.st_size,
        )
        action_card_stats: dict[
            str,
            _ResidentActionCardStatsAttestation,
        ] = {}
        action_lookup_names = set(catalog.action_recipes)
        action_lookup_names.update(
            lookup_name for lookup_name, _, _ in catalog.action_member_recipes
        )
        for lookup_name in action_lookup_names:
            card_stats = battle.card_loader.get_card(lookup_name)
            if card_stats is None:  # pragma: no cover - catalog/loader invariant
                continue
            action_card_stats[lookup_name] = _ResidentActionCardStatsAttestation(
                card_stats=card_stats,
                fingerprint=_normalized_sha256(card_stats),
            )
        damage_groups_by_identity: dict[int, tuple[set[int], list[int]]] = {}
        for entity in battle.entities.values():
            if type(entity) is not Projectile:
                continue
            hit_ids = entity.damage_group_hit_entity_ids
            if hit_ids is None:
                continue
            _, projectile_ids = damage_groups_by_identity.setdefault(
                id(hit_ids),
                (hit_ids, []),
            )
            projectile_ids.append(int(entity.id))
        projectile_damage_groups = [
            (min(projectile_ids), sorted(hit_ids), projectile_ids)
            for hit_ids, projectile_ids in damage_groups_by_identity.values()
        ]
        assert _ResidentBattle is not None
        native = _ResidentBattle(
            checkpoint,
            catalog=catalog.payload,
            tick=int(battle.tick),
            time=float(battle.time),
            dt=float(battle.dt),
            arena_width_tiles=int(battle.arena.width),
            arena_height_tiles=int(battle.arena.height),
            canonical_action_arena=_is_canonical_resident_action_arena(battle.arena),
            double_elixir=bool(battle.double_elixir),
            triple_elixir=bool(battle.triple_elixir),
            overtime=bool(battle.overtime),
            game_over=bool(battle.game_over),
            double_elixir_start_time=float(battle.double_elixir_start_time),
            overtime_start_time=float(battle.overtime_start_time),
            triple_elixir_start_time=float(battle.triple_elixir_start_time),
            player_tick_ms=round(float(battle.dt) * 1000.0),
            refill_schedule=list(
                DEFAULT_BATTLE_TIMELINE_NEXT_CARD_REFILL_COOLDOWN_MS
            ),
            players=[
                (
                    int(player.player_id),
                    float(player.elixir),
                    float(player.max_elixir),
                    int(player.next_card_refill_cooldown_ms),
                    list(player.hand),
                    list(player.cycle_queue),
                    float(player.king_tower_hp),
                    float(player.left_tower_hp),
                    float(player.right_tower_hp),
                )
                for player in battle.players
            ],
            starting_tower_hps=[
                (
                    float(battle._starting_tower_hps[player_id]["left"]),
                    float(battle._starting_tower_hps[player_id]["right"]),
                    float(battle._starting_tower_hps[player_id]["king"]),
                )
                for player_id in (0, 1)
            ],
            towers=[
                (
                    int(entity.id),
                    int(entity.player_id),
                    str(entity._crown_tower_slot),
                    float(entity.hitpoints),
                    round(float(entity.hitpoints) * 1000.0),
                    bool(entity.is_alive),
                    bool(getattr(entity, "_tower_active", True)),
                    float(entity.last_attack_time),
                )
                for entity in battle.entities.values()
                if isinstance(entity, Building)
                and entity._crown_tower_slot in {"left", "right", "king"}
            ],
            idle_eligible=bool(battle.can_fast_forward_idle()),
            sparse_idle_win_checks=True,
            win_conditions_dirty=bool(battle._win_conditions_dirty),
            sudden_death=bool(battle.sudden_death),
            sudden_death_crowns=tuple(battle._sudden_death_crowns),
            tiebreaker_time=float(battle.tiebreaker_time),
            winner=battle.winner,
            pending_spell_casts=[
                (
                    float(cast.execute_at),
                    int(cast.sequence),
                    str(cast.spell_name),
                    int(cast.player_id),
                    float(cast.position.x),
                    float(cast.position.y),
                )
                for cast in battle._pending_spell_casts
            ],
            next_spell_cast_sequence=int(battle._next_spell_cast_sequence),
            projectile_damage_groups=projectile_damage_groups,
        )
        native_supported_actions = frozenset(
            str(name) for name in native.catalog_supported_cards()
        )
        catalog = replace(
            catalog,
            pending_spell_action_kinds=tuple(
                (lookup_name, action_kind)
                for lookup_name, action_kind in catalog.pending_spell_action_kinds
                if lookup_name in native_supported_actions
            ),
        )
        return cls(native, catalog, action_card_stats)

    @property
    def supports_complete_tick(self) -> bool:
        return bool(self._native.supports_complete_tick())

    def require_complete_tick(self, mode: RustBattleMode | str) -> None:
        parsed_mode = RustBattleMode(mode)
        if parsed_mode is not RustBattleMode.OFF and not self.supports_complete_tick:
            raise RuntimeError(
                f"Rust battle mode {parsed_mode.value!r} is unavailable: the "
                "resident core cannot execute the complete tick exactly"
            )

    def advance_complete_tick(self) -> bool:
        return bool(self._native.advance_complete_tick())

    def advance_complete_ticks(self, ticks: int) -> int:
        return int(self._native.advance_complete_ticks(int(ticks)))

    def pending_spell_state_bytes(self) -> bytes:
        return bytes(self._native.pending_spell_state_bytes())

    def projectile_damage_group_state_bytes(self) -> bytes:
        return bytes(self._native.projectile_damage_group_state_bytes())

    def advance_clock_phase(self) -> bool:
        return bool(self._native.advance_clock_phase())

    def clock_state(self) -> BattleClockState:
        values = self._native.clock_state()
        return BattleClockState(*values)

    def clock_sha256(self) -> str:
        return str(self._native.clock_sha256())

    def advance_player_phase(self) -> None:
        self._native.advance_player_phase()

    def player_states(self) -> tuple[ResidentPlayerState, ...]:
        return tuple(
            ResidentPlayerState(
                player_id=int(values[0]),
                elixir=float(values[1]),
                max_elixir=float(values[2]),
                next_card_refill_cooldown_ms=int(values[3]),
                hand=tuple(values[4]),
                cycle_queue=tuple(values[5]),
                king_tower_hp=float(values[6]),
                left_tower_hp=float(values[7]),
                right_tower_hp=float(values[8]),
            )
            for values in self._native.player_states()
        )

    def publication_player_state_bytes(self) -> bytes:
        return bytes(self._native.publication_player_state_bytes())

    def player_sha256(self) -> str:
        return str(self._native.player_sha256())

    @property
    def supports_idle_ticks(self) -> bool:
        return bool(self._native.supports_idle_ticks())

    def advance_idle_ticks(self, ticks: int) -> int:
        return int(self._native.advance_idle_ticks(ticks))

    def tower_states(self) -> tuple[ResidentTowerState, ...]:
        return tuple(
            ResidentTowerState(
                id=int(values[0]),
                player_id=int(values[1]),
                slot=str(values[2]),
                hp=float(values[3]),
                hp_milli=int(values[4]),
                is_alive=bool(values[5]),
                is_active=bool(values[6]),
                last_attack_time=float(values[7]),
            )
            for values in self._native.tower_states()
        )

    def outcome_state(self) -> ResidentOutcomeState:
        sudden_death, game_over, winner, crowns = self._native.outcome_state()
        return ResidentOutcomeState(
            sudden_death=bool(sudden_death),
            game_over=bool(game_over),
            winner=None if winner is None else int(winner),
            sudden_death_crowns=(int(crowns[0]), int(crowns[1])),
        )

    @property
    def win_conditions_dirty(self) -> bool:
        return bool(self._native.win_conditions_dirty())

    def idle_sha256(self) -> str:
        return str(self._native.idle_sha256())

    def entity_state_bytes(self) -> bytes:
        return bytes(self._native.entity_state_bytes())

    def publication_entity_state_bytes(self) -> bytes:
        return bytes(self._native.publication_entity_state_bytes())

    def publication_battle_attribute_presence_bytes(self) -> bytes:
        return bytes(self._native.publication_battle_attribute_presence_bytes())

    def publication_exactness_sha256(self) -> str:
        return str(self._native.publication_exactness_sha256())

    def entity_sha256(self) -> str:
        return str(self._native.entity_sha256())

    @property
    def next_entity_id(self) -> int:
        return int(self._native.next_entity_id())

    @property
    def supports_modifier_phase(self) -> bool:
        return bool(self._native.supports_modifier_phase())

    def advance_modifier_phase(self) -> None:
        self._native.advance_modifier_phase()

    def modifier_state_bytes(self) -> bytes:
        return bytes(self._native.modifier_state_bytes())

    def modifier_sha256(self) -> str:
        return str(self._native.modifier_sha256())

    def shield_state_bytes(self) -> bytes:
        return bytes(self._native.shield_state_bytes())

    def shield_sha256(self) -> str:
        return str(self._native.shield_sha256())

    def death_opcode_state_bytes(self) -> bytes:
        return bytes(self._native.death_opcode_state_bytes())

    def death_opcode_sha256(self) -> str:
        return str(self._native.death_opcode_sha256())

    def area_effect_state_bytes(self) -> bytes:
        return bytes(self._native.area_effect_state_bytes())

    def area_effect_sha256(self) -> str:
        return str(self._native.area_effect_sha256())

    @property
    def supports_character_object_phase(self) -> bool:
        return bool(self._native.supports_character_object_phase())

    def advance_character_object_phase(self) -> None:
        self._native.advance_character_object_phase()

    def character_object_state_bytes(self) -> bytes:
        return bytes(self._native.character_object_state_bytes())

    def character_object_sha256(self) -> str:
        return str(self._native.character_object_sha256())

    @property
    def supports_resident_object_phase(self) -> bool:
        return bool(self._native.supports_resident_object_phase())

    def advance_resident_object_phase(self) -> None:
        self._native.advance_resident_object_phase()

    @property
    def supports_stationary_movement_phase(self) -> bool:
        return bool(self._native.supports_stationary_movement_phase())

    def advance_stationary_movement_phase(self) -> None:
        self._native.advance_stationary_movement_phase()

    def stationary_movement_state_bytes(self) -> bytes:
        return bytes(self._native.stationary_movement_state_bytes())

    def stationary_movement_sha256(self) -> str:
        return str(self._native.stationary_movement_sha256())

    @property
    def supports_flying_movement_phase(self) -> bool:
        return bool(self._native.supports_flying_movement_phase())

    def advance_flying_movement_phase(self) -> None:
        self._native.advance_flying_movement_phase()

    def flying_movement_state_bytes(self) -> bytes:
        return bytes(self._native.flying_movement_state_bytes())

    def flying_movement_sha256(self) -> str:
        return str(self._native.flying_movement_sha256())

    @property
    def supports_ground_movement_phase(self) -> bool:
        return bool(self._native.supports_ground_movement_phase())

    def advance_ground_movement_phase(self) -> None:
        self._native.advance_ground_movement_phase()

    def ground_movement_state_bytes(self) -> bytes:
        return bytes(self._native.ground_movement_state_bytes())

    def ground_movement_sha256(self) -> str:
        return str(self._native.ground_movement_sha256())

    @property
    def supports_direct_combat_phase(self) -> bool:
        return bool(self._native.supports_direct_combat_phase())

    def direct_combat_capability(self) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]],
            json.loads(self._native.direct_combat_capability_bytes()),
        )

    @property
    def supports_locked_direct_combat_phase(self) -> bool:
        return bool(self._native.supports_locked_direct_combat_phase())

    def advance_locked_direct_combat_phase(self) -> None:
        self._native.advance_locked_direct_combat_phase()

    @property
    def supports_direct_troop_combat_phase(self) -> bool:
        return bool(self._native.supports_direct_troop_combat_phase())

    def advance_direct_troop_combat_phase(self) -> None:
        self._native.advance_direct_troop_combat_phase()

    @property
    def supports_building_lifetime_phase(self) -> bool:
        return bool(self._native.supports_building_lifetime_phase())

    def advance_building_lifetime_phase(self) -> None:
        self._native.advance_building_lifetime_phase()

    def building_lifetime_state_bytes(self) -> bytes:
        return bytes(self._native.building_lifetime_state_bytes())

    def building_lifetime_sha256(self) -> str:
        return str(self._native.building_lifetime_sha256())

    @property
    def supports_point_projectile_phase(self) -> bool:
        return bool(self._native.supports_point_projectile_phase())

    def advance_point_projectile_phase(self) -> None:
        self._native.advance_point_projectile_phase()

    def point_projectile_state_bytes(self) -> bytes:
        return bytes(self._native.point_projectile_state_bytes())

    def point_projectile_sha256(self) -> str:
        return str(self._native.point_projectile_sha256())

    def rolling_projectile_state_bytes(self) -> bytes:
        return bytes(self._native.rolling_projectile_state_bytes())

    def rolling_projectile_sha256(self) -> str:
        return str(self._native.rolling_projectile_sha256())

    @property
    def supports_cleanup_phase(self) -> bool:
        return bool(self._native.supports_cleanup_phase())

    def advance_cleanup_phase(self) -> None:
        self._native.advance_cleanup_phase()

    def locked_direct_combat_state_bytes(self) -> bytes:
        return bytes(self._native.locked_direct_combat_state_bytes())

    def locked_direct_combat_sha256(self) -> str:
        return str(self._native.locked_direct_combat_sha256())

    @property
    def resident_catalog_schema_version(self) -> int:
        return int(self._native.catalog_schema_version())

    @property
    def resident_catalog_fingerprint(self) -> str:
        return str(self._native.catalog_fingerprint())

    @property
    def resident_catalog_source_fingerprint(self) -> str:
        return str(self._native.catalog_source_fingerprint())

    @property
    def resident_catalog_strong_count(self) -> int:
        return int(self._native.catalog_strong_count())

    def resident_supported_action_cards(self) -> tuple[str, ...]:
        return tuple(str(name) for name in self._native.catalog_supported_cards())

    def resident_action_card_capability_reasons(self, name: str) -> tuple[str, ...]:
        return tuple(
            str(reason) for reason in self._native.catalog_capability_reasons(str(name))
        )

    def resident_legal_action_ids(self, player_id: int) -> tuple[int, ...]:
        return tuple(
            int(action_id)
            for action_id in self._native.legal_action_ids(int(player_id))
        )

    def resident_oracle_state_key(self) -> tuple[Any, ...]:
        base, entities = self._native.oracle_state_key_parts()
        return (
            *(int(value) for value in base),
            tuple(
                tuple(int(value) for value in entity_key)
                for entity_key in entities
            ),
        )

    def resident_oracle_leaf_projection(self) -> Any:
        from .rl.rust_oracle_leaf import projection_from_native_parts

        return projection_from_native_parts(
            self._native.oracle_leaf_projection_parts()
        )

    def apply_resident_joint_actions(
        self,
        action0: int,
        action1: int,
    ) -> tuple[dict[int, bool], tuple[int, int]]:
        success0, success1, order = self._native.apply_joint_actions(
            int(action0),
            int(action1),
        )
        return (
            {0: bool(success0), 1: bool(success1)},
            (int(order[0]), int(order[1])),
        )

    def preview_resident_joint_action_interval(
        self,
        action0: int,
        action1: int,
        ticks: int,
    ) -> tuple[ResidentRustBattle, dict[int, bool], tuple[int, int], int]:
        """Return one unpublished clone after exact joint actions and ticks."""

        try:
            native, success0, success1, order, advanced = (
                self._native.preview_joint_action_interval(
                    int(action0),
                    int(action1),
                    int(ticks),
                )
            )
        except RuntimeError as error:
            message = str(error)
            if message.startswith(_RESIDENT_PREVIEW_TICK_FAILURE_PREFIX):
                detail = message.removeprefix(_RESIDENT_PREVIEW_TICK_FAILURE_PREFIX)
                raise ResidentPreviewTickError(detail) from error
            raise
        candidate = type(self)(
            native,
            self._birth_catalog,
            self._action_card_stats,
        )
        return (
            candidate,
            {0: bool(success0), 1: bool(success1)},
            (int(order[0]), int(order[1])),
            int(advanced),
        )

    def apply_resident_ordered_interval(
        self,
        action0: int,
        action1: int,
        first_player: int,
        ticks: int,
    ) -> tuple[dict[int, bool], int]:
        success0, success1, advanced = self._native.apply_ordered_interval(
            int(action0),
            int(action1),
            int(first_player),
            int(ticks),
        )
        return {0: bool(success0), 1: bool(success1)}, int(advanced)

    def rng_random(self) -> float:
        return float(self._native.rng_random())

    def rng_randrange(self, stop: int) -> int:
        return int(self._native.rng_randrange(stop))

    def rng_choice_index(self, length: int) -> int:
        return int(self._native.rng_choice_index(length))

    def rng_shuffle_indices(self, length: int) -> list[int]:
        return [int(index) for index in self._native.rng_shuffle_indices(length)]

    def rng_getstate(self) -> tuple[int, tuple[int, ...], float | None]:
        version, words, index, gauss_next = self._native.rng_state_parts()
        return (
            int(version),
            (*[int(word) for word in words], int(index)),
            None if gauss_next is None else float(gauss_next),
        )

    def rng_state_bytes(self) -> bytes:
        return bytes(self._native.rng_state_bytes())

    def rng_sha256(self) -> str:
        return str(self._native.rng_sha256())

    def checkpoint_bytes(self) -> bytes:
        return bytes(self._native.checkpoint_bytes())

    @property
    def checkpoint_sha256(self) -> str:
        return str(self._native.checkpoint_sha256())

    @property
    def checkpoint_size(self) -> int:
        return int(self._native.checkpoint_size())

    @property
    def checkpoint_generation(self) -> int:
        return int(self._native.checkpoint_generation())

    def publication_authority_token(self) -> tuple[Any, ...]:
        """Return the immutable native lineage/node/epoch publication binding."""

        return tuple(self._native.publication_authority_token())

    @property
    def checkpoint_is_current(self) -> bool:
        return bool(self._native.checkpoint_is_current())

    @property
    def schema_version(self) -> int:
        return int(self._native.schema_version())

    def replace_checkpoint(self, payload: bytes) -> None:
        self._native.replace_checkpoint(payload)


def compare_clock_phase(battle: Any, resident: ResidentRustBattle) -> None:
    expected = BattleClockState(
        tick=int(battle.tick),
        time=float(battle.time),
        dt=float(battle.dt),
        double_elixir=bool(battle.double_elixir),
        triple_elixir=bool(battle.triple_elixir),
        overtime=bool(battle.overtime),
        game_over=bool(battle.game_over),
    )
    actual = resident.clock_state()
    if actual == expected and resident.clock_sha256() == expected.sha256():
        return
    for field_name in BattleClockState.__dataclass_fields__:
        expected_value = getattr(expected, field_name)
        actual_value = getattr(actual, field_name)
        if type(expected_value) is not type(actual_value) or expected_value != actual_value:
            raise AssertionError(
                "resident Rust clock parity mismatch "
                f"field={field_name} expected={expected_value!r} "
                f"actual={actual_value!r}"
            )
    raise AssertionError(
        "resident Rust clock hash mismatch "
        f"expected={expected.sha256()} actual={resident.clock_sha256()}"
    )


def python_player_states(battle: Any) -> tuple[ResidentPlayerState, ...]:
    return tuple(
        ResidentPlayerState(
            player_id=int(player.player_id),
            elixir=float(player.elixir),
            max_elixir=float(player.max_elixir),
            next_card_refill_cooldown_ms=int(
                player.next_card_refill_cooldown_ms
            ),
            hand=tuple(player.hand),
            cycle_queue=tuple(player.cycle_queue),
            king_tower_hp=float(player.king_tower_hp),
            left_tower_hp=float(player.left_tower_hp),
            right_tower_hp=float(player.right_tower_hp),
        )
        for player in battle.players
    )


def player_states_sha256(states: tuple[ResidentPlayerState, ...]) -> str:
    payload = bytearray(struct.pack("<Q", len(states)))
    for player in states:
        player.append_hash_payload(payload)
    return hashlib.sha256(payload).hexdigest()


def compare_player_phase(battle: Any, resident: ResidentRustBattle) -> None:
    expected = python_player_states(battle)
    actual = resident.player_states()
    if actual == expected and resident.player_sha256() == player_states_sha256(expected):
        return
    if len(actual) != len(expected):
        raise AssertionError(
            "resident Rust player parity mismatch "
            f"field=count expected={len(expected)} actual={len(actual)}"
        )
    for player_index, (expected_player, actual_player) in enumerate(
        zip(expected, actual, strict=True)
    ):
        for field_name in ResidentPlayerState.__dataclass_fields__:
            expected_value = getattr(expected_player, field_name)
            actual_value = getattr(actual_player, field_name)
            if type(expected_value) is not type(actual_value) or expected_value != actual_value:
                raise AssertionError(
                    "resident Rust player parity mismatch "
                    f"player={player_index} field={field_name} "
                    f"expected={expected_value!r} actual={actual_value!r}"
                )
    raise AssertionError(
        "resident Rust player hash mismatch "
        f"expected={player_states_sha256(expected)} "
        f"actual={resident.player_sha256()}"
    )


def python_tower_states(battle: Any) -> tuple[ResidentTowerState, ...]:
    return tuple(
        ResidentTowerState(
            id=int(entity.id),
            player_id=int(entity.player_id),
            slot=str(entity._crown_tower_slot),
            hp=float(entity.hitpoints),
            hp_milli=round(float(entity.hitpoints) * 1000.0),
            is_alive=bool(entity.is_alive),
            is_active=bool(getattr(entity, "_tower_active", True)),
            last_attack_time=float(entity.last_attack_time),
        )
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity._crown_tower_slot in {"left", "right", "king"}
    )


def python_outcome_state(battle: Any) -> ResidentOutcomeState:
    return ResidentOutcomeState(
        sudden_death=bool(battle.sudden_death),
        game_over=bool(battle.game_over),
        winner=battle.winner,
        sudden_death_crowns=tuple(battle._sudden_death_crowns),
    )


def idle_state_sha256(battle: Any) -> str:
    clock = BattleClockState(
        tick=int(battle.tick),
        time=float(battle.time),
        dt=float(battle.dt),
        double_elixir=bool(battle.double_elixir),
        triple_elixir=bool(battle.triple_elixir),
        overtime=bool(battle.overtime),
        game_over=bool(battle.game_over),
    )
    outcome = python_outcome_state(battle)
    players = python_player_states(battle)
    towers = python_tower_states(battle)
    payload = bytearray(struct.pack("<qd", clock.tick, clock.time))
    payload.extend(
        bytes(
            (
                clock.double_elixir,
                clock.triple_elixir,
                clock.overtime,
                outcome.sudden_death,
                outcome.game_over,
            )
        )
    )
    if outcome.winner is None:
        payload.append(0)
    else:
        payload.append(1)
        payload.extend(struct.pack("<q", outcome.winner))
    payload.extend(struct.pack("<qq", *outcome.sudden_death_crowns))
    payload.extend(struct.pack("<Q", len(players)))
    for player in players:
        player.append_hash_payload(payload)
    payload.extend(struct.pack("<Q", len(towers)))
    for tower in towers:
        tower.append_hash_payload(payload)
    return hashlib.sha256(payload).hexdigest()


def compare_idle_state(battle: Any, resident: ResidentRustBattle) -> None:
    compare_clock_phase(battle, resident)
    compare_player_phase(battle, resident)
    expected_towers = python_tower_states(battle)
    actual_towers = resident.tower_states()
    if expected_towers != actual_towers:
        raise AssertionError(
            "resident Rust idle parity mismatch field=towers "
            f"expected={expected_towers!r} actual={actual_towers!r}"
        )
    expected_outcome = python_outcome_state(battle)
    actual_outcome = resident.outcome_state()
    if expected_outcome != actual_outcome:
        raise AssertionError(
            "resident Rust idle parity mismatch field=outcome "
            f"expected={expected_outcome!r} actual={actual_outcome!r}"
        )
    expected_hash = idle_state_sha256(battle)
    actual_hash = resident.idle_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust idle parity mismatch field=hash "
            f"expected={expected_hash} actual={actual_hash}"
        )


def _exact_scalar(value: Any) -> dict[str, str | int]:
    if type(value) is int:
        return {"kind": "int", "value": int(value)}
    return {"bits": f"{struct.unpack('<Q', struct.pack('<d', float(value)))[0]:016x}", "kind": "float"}


def _entity_id_or_none(value: Any) -> int | None:
    return None if value is None else int(value.id)


def resident_entity_rows(battle: Any) -> list[dict[str, Any]]:
    return [
        {
            "card_name": str(getattr(entity.card_stats, "name", "")),
            "encounter_index": encounter_index,
            "entity_kind": int(entity.entity_kind),
            "freeze_expiry_time": _exact_scalar(
                getattr(entity, "freeze_expiry_time", 0.0)
            ),
            "hitpoints": _exact_scalar(entity.hitpoints),
            "id": int(entity.id),
            "is_alive": bool(entity.is_alive),
            "max_hitpoints": _exact_scalar(entity.max_hitpoints),
            "mechanics": [
                f"{type(mechanic).__module__}.{type(mechanic).__qualname__}"
                for mechanic in entity.mechanics
            ],
            "pending_projectile_max_duration_ms": int(
                entity._pending_projectile_max_duration_ms
            ),
            "placement_delay_total": _exact_scalar(
                entity.placement_delay_total
            ),
            "player_id": int(entity.player_id),
            "position_x": _exact_scalar(entity.position.x),
            "position_y": _exact_scalar(entity.position.y),
            "python_type": (
                f"{type(entity).__module__}.{type(entity).__qualname__}"
            ),
            "spawn_angle_shift": _exact_scalar(
                getattr(entity.card_stats, "spawn_angle_shift", 0.0) or 0.0
            ),
            "target_id": (
                None if entity.target_id is None else int(entity.target_id)
            ),
        }
        for encounter_index, entity in enumerate(battle.entities.values())
    ]


def resident_entity_bytes(battle: Any) -> bytes:
    return json.dumps(
        resident_entity_rows(battle),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def compare_resident_entities(
    battle: Any,
    resident: ResidentRustBattle,
) -> None:
    expected = resident_entity_rows(battle)
    actual = json.loads(resident.entity_state_bytes())
    if expected == actual:
        expected_hash = hashlib.sha256(resident_entity_bytes(battle)).hexdigest()
        actual_hash = resident.entity_sha256()
        if expected_hash == actual_hash:
            return
        raise AssertionError(
            "resident Rust entity hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )
    from .differential import first_snapshot_difference

    difference = first_snapshot_difference(expected, actual)
    if difference is None:  # pragma: no cover - defensive
        raise AssertionError("resident Rust entity state mismatch")
    raise AssertionError(
        "resident Rust entity parity mismatch "
        f"path={difference.path} reason={difference.reason} "
        f"expected={difference.expected!r} actual={difference.actual!r}"
    )


def resident_rng_state(rng: Any) -> dict[str, Any]:
    version, inner, gauss_next = rng.getstate()
    return {
        "gauss_next": None if gauss_next is None else _exact_scalar(gauss_next),
        "index": int(inner[-1]),
        "state": [int(word) for word in inner[:-1]],
        "version": int(version),
    }


def resident_rng_bytes(rng: Any) -> bytes:
    return json.dumps(
        resident_rng_state(rng),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def compare_resident_rng(rng: Any, resident: ResidentRustBattle) -> None:
    expected = resident_rng_state(rng)
    actual = json.loads(resident.rng_state_bytes())
    if expected != actual:
        from .differential import first_snapshot_difference

        difference = first_snapshot_difference(expected, actual)
        if difference is None:  # pragma: no cover - defensive
            raise AssertionError("resident Rust RNG state mismatch")
        raise AssertionError(
            "resident Rust RNG parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )
    expected_hash = hashlib.sha256(resident_rng_bytes(rng)).hexdigest()
    actual_hash = resident.rng_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust RNG hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )


def modifier_state_rows(battle: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for encounter_index, entity in enumerate(battle.entities.values()):
        if not isinstance(entity, Building) and entity.entity_kind != 0:
            continue
        rows.append(
            {
                "attack_speed_buff_multiplier": _exact_scalar(
                    entity.attack_speed_buff_multiplier
                ),
                "attack_speed_debuff_multiplier": _exact_scalar(
                    entity.attack_speed_debuff_multiplier
                ),
                "encounter_index": encounter_index,
                "haste_effects": [
                    [_exact_scalar(value) for value in effect]
                    for effect in entity._haste_effects
                ],
                "haste_timer": _exact_scalar(entity.haste_timer),
                "id": int(entity.id),
                "movement_mode_multiplier": _exact_scalar(
                    entity.movement_mode_multiplier
                ),
                "movement_speed_buff_multiplier": _exact_scalar(
                    entity.movement_speed_buff_multiplier
                ),
                "original_speed": (
                    None
                    if entity.original_speed is None
                    else _exact_scalar(entity.original_speed)
                ),
                "slow_effects": [
                    [_exact_scalar(value) for value in effect]
                    for effect in entity._slow_effects
                ],
                "slow_multiplier": _exact_scalar(entity.slow_multiplier),
                "slow_timer": _exact_scalar(entity.slow_timer),
                "spawn_speed_buff_multiplier": _exact_scalar(
                    entity.spawn_speed_buff_multiplier
                ),
                "spawn_speed_debuff_multiplier": _exact_scalar(
                    entity.spawn_speed_debuff_multiplier
                ),
                "speed": _exact_scalar(entity.speed),
                "stun_timer": _exact_scalar(entity.stun_timer),
            }
        )
    return rows


def modifier_state_bytes(battle: Any) -> bytes:
    return json.dumps(
        modifier_state_rows(battle),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def shield_state_rows(battle: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for encounter_index, entity in enumerate(battle.entities.values()):
        shields = [
            mechanic
            for mechanic in entity.mechanics
            if (
                f"{type(mechanic).__module__}.{type(mechanic).__qualname__}"
                == "clasher.mechanics.shared.shield.Shield"
            )
        ]
        if not shields:
            continue
        rows.append(
            {
                "encounter_index": encounter_index,
                "id": int(entity.id),
                "shield_break_count": int(
                    getattr(entity, "_shield_break_count", 0)
                ),
                "shields": [
                    {
                        "current_shield": _exact_scalar(
                            mechanic.current_shield
                        ),
                        "max_shield": _exact_scalar(mechanic.max_shield),
                    }
                    for mechanic in shields
                ],
            }
        )
    return rows


def shield_state_bytes(battle: Any) -> bytes:
    return json.dumps(
        shield_state_rows(battle),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def death_opcode_state_rows(battle: Any) -> list[dict[str, Any]]:
    import math

    from .gamedata_normalization import serialized_hit_planes
    from .kinematics import tiles_to_logic_units
    from .mechanics.shared.death_area import (
        DeathAreaEffect,
        _serialized_speed_multiplier,
    )
    from .mechanics.shared.death_effects import DeathDamage, DeathSpawn

    rows: list[dict[str, Any]] = []
    for encounter_index, entity in enumerate(battle.entities.values()):
        opcode_index = 0
        for mechanic in entity.mechanics:
            if isinstance(mechanic, DeathAreaEffect):
                area_data = mechanic.area_data
                radius_tiles = float(area_data.get("radius", 0) or 0) / 1000.0
                duration = max(
                    0.001,
                    float(area_data.get("lifeDuration", 0) or 0) / 1000.0,
                )
                effect_tick_interval = max(
                    0.0,
                    float(area_data.get("hitSpeed", 0) or 0) / 1000.0,
                )
                refresh_duration = max(
                    0.0,
                    float(area_data.get("buffTime", 0) or 0) / 1000.0,
                )
                buff_data = area_data.get("buffData") or {}
                movement_multiplier = _serialized_speed_multiplier(
                    buff_data.get("speedMultiplier")
                )
                attack_multiplier = _serialized_speed_multiplier(
                    buff_data.get("hitSpeedMultiplier")
                )
                spawn_multiplier = _serialized_speed_multiplier(
                    buff_data.get("spawnSpeedMultiplier")
                )
                raw_damage = float(area_data.get("damage", 0) or 0)
                if not all(
                    math.isfinite(value)
                    for value in (
                        radius_tiles,
                        duration,
                        effect_tick_interval,
                        refresh_duration,
                        raw_damage,
                        movement_multiplier,
                        attack_multiplier,
                        spawn_multiplier,
                    )
                ):
                    raise ValueError(
                        "DeathAreaEffect contains a non-finite numeric field"
                    )
                if (
                    area_data.get("onStartingActionData") is not None
                    or max(
                        movement_multiplier,
                        attack_multiplier,
                        spawn_multiplier,
                    )
                    > 1.0
                    or (
                        movement_multiplier == 0.0
                        and attack_multiplier == 0.0
                        and spawn_multiplier == 0.0
                    )
                    or radius_tiles < 0.0
                    or raw_damage != 0.0
                    or effect_tick_interval > 0.0
                ):
                    continue
                hits_air, hits_ground = serialized_hit_planes(area_data)
                rows.append(
                    {
                        "affects_hidden": bool(
                            area_data.get("affectsHidden", False)
                        ),
                        "area_name": str(
                            area_data.get("name", "") or "death-area"
                        ),
                        "attack_multiplier": _exact_scalar(
                            attack_multiplier
                        ),
                        "cap_buff_time_to_effect": bool(
                            area_data.get(
                                "capBuffTimeToAreaEffectTime",
                                False,
                            )
                        ),
                        "duration": _exact_scalar(duration),
                        "effect_tick_interval": _exact_scalar(
                            effect_tick_interval
                        ),
                        "encounter_index": encounter_index,
                        "hits_air": hits_air,
                        "hits_ground": hits_ground,
                        "id": int(entity.id),
                        "movement_multiplier": _exact_scalar(
                            movement_multiplier
                        ),
                        "opcode_index": opcode_index,
                        "opcode_type": "area",
                        "radius_tiles": _exact_scalar(radius_tiles),
                        "radius_units": max(
                            0,
                            tiles_to_logic_units(radius_tiles),
                        ),
                        "refresh_duration": _exact_scalar(refresh_duration),
                        "spawn_multiplier": _exact_scalar(spawn_multiplier),
                    }
                )
                opcode_index += 1
                continue
            if isinstance(mechanic, DeathSpawn):
                unit_data = mechanic.unit_data or {}
                if unit_data.get("deathDamage") is not None and not unit_data.get(
                    "hitpoints"
                ):
                    continue
                rows.append(
                    {
                        "count": int(mechanic.count),
                        "deploy_time_ms": int(mechanic.deploy_time_ms),
                        "encounter_index": encounter_index,
                        "id": int(entity.id),
                        "min_radius_tiles": _exact_scalar(
                            mechanic.min_radius_tiles
                        ),
                        "opcode_index": opcode_index,
                        "opcode_type": "spawn",
                        "radial_pushback": bool(mechanic.radial_pushback),
                        "radius_tiles": _exact_scalar(mechanic.radius_tiles),
                        "spawn_const_priority": bool(
                            mechanic.spawn_const_priority
                        ),
                        "unit_name": str(mechanic.unit_name),
                        "unit_data_sha256": hashlib.sha256(
                            json.dumps(
                                _normalize(mechanic.unit_data),
                                sort_keys=True,
                                separators=(",", ":"),
                            ).encode("ascii")
                        ).hexdigest(),
                    }
                )
                opcode_index += 1
                continue
            if not isinstance(mechanic, DeathDamage):
                continue
            rows.append(
                {
                    "base_damage": int(mechanic.damage),
                    "encounter_index": encounter_index,
                    "hits_air": bool(mechanic.hits_air),
                    "hits_ground": bool(mechanic.hits_ground),
                    "id": int(entity.id),
                    "knockback_distance": _exact_scalar(
                        mechanic.knockback_distance
                    ),
                    "knockback_units": min(
                        10_000,
                        max(
                            0,
                            tiles_to_logic_units(mechanic.knockback_distance),
                        ),
                    ),
                    "opcode_index": opcode_index,
                    "opcode_type": "damage",
                    "radius_tiles": _exact_scalar(mechanic.radius_tiles),
                    "radius_units": max(
                        0,
                        tiles_to_logic_units(mechanic.radius_tiles),
                    ),
                    "scaled_damage": _exact_scalar(mechanic.scaled_damage),
                }
            )
            opcode_index += 1
    return rows


def area_effect_state_rows(battle: Any) -> list[dict[str, Any]]:
    from .entities import AreaEffect
    from .kinematics import tiles_to_logic_units

    rows: list[dict[str, Any]] = []
    for encounter_index, entity in enumerate(battle.entities.values()):
        if not isinstance(entity, AreaEffect):
            continue
        attack_multiplier = (
            (
                entity.speed_multiplier
                if entity.slows_attack_speed
                else 1.0
            )
            if entity.attack_speed_multiplier is None
            else entity.attack_speed_multiplier
        )
        spawn_multiplier = (
            (
                entity.speed_multiplier
                if entity.slows_spawn_speed
                else 1.0
            )
            if entity.spawn_speed_multiplier is None
            else entity.spawn_speed_multiplier
        )
        rows.append(
            {
                "affects_hidden": bool(entity.affects_hidden),
                "area_name": str(
                    getattr(entity, "spell_name", "") or "death-area"
                ),
                "attack_multiplier": _exact_scalar(attack_multiplier),
                "cap_buff_time_to_effect": bool(
                    entity.cap_buff_time_to_effect
                ),
                "duration": _exact_scalar(entity.duration),
                "effect_snapshot_applied": bool(
                    entity.effect_snapshot_applied
                ),
                "effect_tick_interval": _exact_scalar(
                    entity.effect_tick_interval
                ),
                "encounter_index": encounter_index,
                "hits_air": bool(entity.hits_air),
                "hits_ground": bool(entity.hits_ground),
                "id": int(entity.id),
                "is_alive": bool(entity.is_alive),
                "movement_multiplier": _exact_scalar(
                    entity.speed_multiplier
                ),
                "player_id": int(entity.player_id),
                "position_x": _exact_scalar(entity.position.x),
                "position_y": _exact_scalar(entity.position.y),
                "radius_tiles": _exact_scalar(entity.radius),
                "radius_units": max(
                    0,
                    tiles_to_logic_units(entity.radius),
                ),
                "refresh_duration": _exact_scalar(
                    entity.slow_refresh_duration
                ),
                "spawn_multiplier": _exact_scalar(spawn_multiplier),
                "time_alive": _exact_scalar(entity.time_alive),
            }
        )
    return rows


def area_effect_state_bytes(battle: Any) -> bytes:
    return json.dumps(
        area_effect_state_rows(battle),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def compare_area_effect_state(
    battle: Any,
    resident: ResidentRustBattle,
) -> None:
    expected = area_effect_state_rows(battle)
    actual = json.loads(resident.area_effect_state_bytes())
    if expected != actual:
        from .differential import first_snapshot_difference

        difference = first_snapshot_difference(expected, actual)
        if difference is None:  # pragma: no cover - defensive
            raise AssertionError("resident Rust area-effect state mismatch")
        raise AssertionError(
            "resident Rust area-effect parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )
    expected_hash = hashlib.sha256(area_effect_state_bytes(battle)).hexdigest()
    actual_hash = resident.area_effect_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust area-effect hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )


def death_opcode_state_bytes(battle: Any) -> bytes:
    return json.dumps(
        death_opcode_state_rows(battle),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def compare_death_opcode_state(
    battle: Any,
    resident: ResidentRustBattle,
) -> None:
    expected = death_opcode_state_rows(battle)
    actual = json.loads(resident.death_opcode_state_bytes())
    if expected != actual:
        from .differential import first_snapshot_difference

        difference = first_snapshot_difference(expected, actual)
        if difference is None:  # pragma: no cover - defensive
            raise AssertionError("resident Rust death opcode state mismatch")
        raise AssertionError(
            "resident Rust death opcode parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )
    expected_hash = hashlib.sha256(death_opcode_state_bytes(battle)).hexdigest()
    actual_hash = resident.death_opcode_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust death opcode hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )


def compare_shield_state(
    battle: Any,
    resident: ResidentRustBattle,
) -> None:
    expected = shield_state_rows(battle)
    actual = json.loads(resident.shield_state_bytes())
    if expected != actual:
        from .differential import first_snapshot_difference

        difference = first_snapshot_difference(expected, actual)
        if difference is None:  # pragma: no cover - defensive
            raise AssertionError("resident Rust shield state mismatch")
        raise AssertionError(
            "resident Rust shield parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )
    expected_hash = hashlib.sha256(shield_state_bytes(battle)).hexdigest()
    actual_hash = resident.shield_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust shield hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )


def compare_modifier_phase(battle: Any, resident: ResidentRustBattle) -> None:
    expected = modifier_state_rows(battle)
    actual = json.loads(resident.modifier_state_bytes())
    if expected != actual:
        from .differential import first_snapshot_difference

        difference = first_snapshot_difference(expected, actual)
        if difference is None:  # pragma: no cover - defensive
            raise AssertionError("resident Rust modifier state mismatch")
        raise AssertionError(
            "resident Rust modifier parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )
    expected_hash = hashlib.sha256(modifier_state_bytes(battle)).hexdigest()
    actual_hash = resident.modifier_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust modifier hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )


def character_object_state_rows(battle: Any) -> list[dict[str, Any]]:
    return [
        {
            "death_spawn_target_immunity_elapsed_ms": int(
                entity._death_spawn_target_immunity_elapsed_ms
            ),
            "deploy_delay_remaining": _exact_scalar(
                entity.deploy_delay_remaining
            ),
            "encounter_index": encounter_index,
            "id": int(entity.id),
            "placement_pending": bool(entity.placement_pending),
            "spawn_hook_fired": bool(
                getattr(entity, "_spawn_hook_fired", False)
            ),
            "spawn_hook_pending": bool(
                getattr(entity, "_spawn_hook_pending", False)
            ),
        }
        for encounter_index, entity in enumerate(battle.entities.values())
        if entity.entity_kind in {0, 1}
    ]


def character_object_state_bytes(battle: Any) -> bytes:
    return json.dumps(
        character_object_state_rows(battle),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def compare_character_object_phase(
    battle: Any,
    resident: ResidentRustBattle,
) -> None:
    expected = character_object_state_rows(battle)
    actual = json.loads(resident.character_object_state_bytes())
    if expected != actual:
        from .differential import first_snapshot_difference

        difference = first_snapshot_difference(expected, actual)
        if difference is None:  # pragma: no cover - defensive
            raise AssertionError("resident Rust character object state mismatch")
        raise AssertionError(
            "resident Rust character object parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )
    expected_hash = hashlib.sha256(character_object_state_bytes(battle)).hexdigest()
    actual_hash = resident.character_object_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust character object hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )


def stationary_movement_state_rows(battle: Any) -> list[dict[str, Any]]:
    return [
        {
            "collision_radius": _exact_scalar(
                (
                    getattr(entity.card_stats, "collision_radius", 0.5)
                    or 0.5
                )
                if entity.entity_kind == 0
                else (
                    getattr(entity.card_stats, "collision_radius", 0.0)
                    or 0.0
                )
            ),
            "encounter_index": encounter_index,
            "id": int(entity.id),
            "native_avoidance": int(
                getattr(entity, "_native_avoidance", 0)
            ),
            "native_natural_movement_active": bool(
                getattr(entity, "_native_natural_movement_active", False)
            ),
            "pending_consumed": bool(entity._pending_movement_consumed),
            "pending_x": _exact_scalar(entity._pending_movement_x),
            "pending_y": _exact_scalar(entity._pending_movement_y),
            "position_x": _exact_scalar(entity.position.x),
            "position_y": _exact_scalar(entity.position.y),
            "unit_mass": _exact_scalar(entity._unit_mass),
            "vector_bypasses_cap": bool(
                entity._movement_vector_bypasses_cap
            ),
            "vector_count": int(entity._movement_vector_count),
            "vector_x_units": int(entity._movement_vector_x_units),
            "vector_y_units": int(entity._movement_vector_y_units),
        }
        for encounter_index, entity in enumerate(battle.entities.values())
        if entity.entity_kind in {0, 1}
    ]


def stationary_movement_state_bytes(battle: Any) -> bytes:
    return json.dumps(
        stationary_movement_state_rows(battle),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def compare_stationary_movement_phase(
    battle: Any,
    resident: ResidentRustBattle,
) -> None:
    expected = stationary_movement_state_rows(battle)
    actual = json.loads(resident.stationary_movement_state_bytes())
    if expected != actual:
        from .differential import first_snapshot_difference

        difference = first_snapshot_difference(expected, actual)
        if difference is None:  # pragma: no cover - defensive
            raise AssertionError("resident Rust stationary movement mismatch")
        raise AssertionError(
            "resident Rust stationary movement parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )
    expected_hash = hashlib.sha256(
        stationary_movement_state_bytes(battle)
    ).hexdigest()
    actual_hash = resident.stationary_movement_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust stationary movement hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )


def flying_movement_state_rows(battle: Any) -> list[dict[str, Any]]:
    from .unit_traits import is_knockback_immune

    rows: list[dict[str, Any]] = []
    for encounter_index, entity in enumerate(battle.entities.values()):
        if entity.entity_kind not in {0, 1}:
            continue
        river_origin = getattr(entity, "_river_jump_origin", None)
        river_target = getattr(entity, "_river_jump_target", None)
        death_spawn_travel_target = getattr(
            entity,
            "_death_spawn_travel_target",
            None,
        )
        knockback_target = getattr(entity, "_knockback_target", None)
        cache_key = getattr(entity, "_ground_path_cache_key", None)
        route_kind = "absent"
        route_goal: list[int] | None = None
        route_cells: list[list[int]] = []
        route_backwards = bool(
            getattr(entity, "_ground_path_cache_backwards", False)
        )
        route_lane_id = 0
        route_jump_height = False
        has_route_cells = hasattr(entity, "_native_ground_route_cells")
        if (
            isinstance(cache_key, tuple)
            and len(cache_key) == 2
            and cache_key[0] == "single"
        ):
            route_kind = "single"
            goal = cache_key[1]
            if isinstance(goal, tuple) and len(goal) == 2:
                route_goal = [int(goal[0]), int(goal[1])]
                native_route_cells = getattr(
                    entity, "_native_ground_route_cells", []
                )
                if isinstance(native_route_cells, list):
                    route_cells = [
                        [int(cell[0]), int(cell[1])]
                        for cell in native_route_cells
                    ]
        elif isinstance(cache_key, tuple) and len(cache_key) == 3:
            goal, lane_id, jump_height = cache_key
            if isinstance(goal, tuple) and len(goal) == 2:
                route_kind = "ground"
                route_goal = [int(goal[0]), int(goal[1])]
                route_lane_id = int(lane_id)
                route_jump_height = bool(jump_height)
                native_route_cells = getattr(
                    entity, "_native_ground_route_cells", []
                )
                if isinstance(native_route_cells, list):
                    route_cells = [
                        [int(cell[0]), int(cell[1])]
                        for cell in native_route_cells
                    ]
            else:
                route_kind = "unsupported"
        elif cache_key is not None or has_route_cells:
            route_kind = "unsupported"
        rows.append(
            {
                "airborne_for_projectile": bool(
                    entity.is_air_unit
                    or getattr(entity, "_river_jump_active", False)
                ),
                "building_pathing_radius": _exact_scalar(
                    float(
                        getattr(entity.card_stats, "collision_radius", 1.0)
                        or 1.0
                    )
                    if entity.entity_kind == 1
                    else 0.0
                ),
                "death_spawn_travel_target": (
                    None
                    if death_spawn_travel_target is None
                    else [
                        _exact_scalar(death_spawn_travel_target.x),
                        _exact_scalar(death_spawn_travel_target.y),
                    ]
                ),
                "death_spawn_travel_ticks": int(
                    entity._death_spawn_travel_ticks_remaining
                ),
                "encounter_index": encounter_index,
                "facing_x_units": int(entity._facing_x_units),
                "facing_y_units": int(entity._facing_y_units),
                "ground_path_backwards": bool(entity._ground_path_backwards),
                "id": int(entity.id),
                "jump_speed": _exact_scalar(
                    float(
                        getattr(entity.card_stats, "jump_speed", 0.0) or 0.0
                    )
                ),
                "knockback_immune": is_knockback_immune(entity.card_stats),
                "knockback_interrupts_combat": bool(
                    entity._knockback_interrupts_combat
                ),
                "knockback_target": (
                    None
                    if knockback_target is None
                    else [
                        _exact_scalar(knockback_target.x),
                        _exact_scalar(knockback_target.y),
                    ]
                ),
                "knockback_velocity_work": int(
                    entity._knockback_velocity_work
                ),
                "movement_phase_elapsed_ms": int(
                    getattr(entity, "movement_phase_elapsed_ms", 0)
                ),
                "native_avoidance": int(
                    getattr(entity, "_native_avoidance", 0)
                ),
                "native_lane_id": int(
                    getattr(entity, "_native_lane_id", 0)
                ),
                "native_natural_movement_active": bool(
                    getattr(entity, "_native_natural_movement_active", False)
                ),
                "pending_consumed": bool(entity._pending_movement_consumed),
                "pending_x": _exact_scalar(entity._pending_movement_x),
                "pending_y": _exact_scalar(entity._pending_movement_y),
                "position_x": _exact_scalar(entity.position.x),
                "position_y": _exact_scalar(entity.position.y),
                "route_backwards": route_backwards,
                "route_cells": route_cells,
                "route_goal": route_goal,
                "route_jump_height": route_jump_height,
                "route_kind": route_kind,
                "route_lane_id": route_lane_id,
                "river_jump_active": bool(
                    getattr(entity, "_river_jump_active", False)
                ),
                "river_jump_blocked": bool(
                    getattr(entity, "_river_jump_blocked", False)
                ),
                "river_jump_duration": _exact_scalar(
                    getattr(entity, "_river_jump_duration", 0.0)
                ),
                "river_jump_elapsed": _exact_scalar(
                    getattr(entity, "_river_jump_elapsed", 0.0)
                ),
                "river_jump_origin": (
                    None
                    if river_origin is None
                    else [
                        _exact_scalar(river_origin.x),
                        _exact_scalar(river_origin.y),
                    ]
                ),
                "river_jump_target": (
                    None
                    if river_target is None
                    else [
                        _exact_scalar(river_target.x),
                        _exact_scalar(river_target.y),
                    ]
                ),
                "special_move_active": bool(
                    getattr(entity, "_special_move_active", False)
                ),
                "special_move_consumed_tick": bool(
                    getattr(entity, "_special_move_consumed_tick", False)
                ),
                "serialized_speed": _exact_scalar(
                    float(getattr(entity.card_stats, "speed", 0.0) or 0.0)
                ),
                "stop_movement_after_ms": _exact_scalar(
                    float(
                        getattr(
                            entity.card_stats,
                            "stop_movement_after_ms",
                            0.0,
                        )
                        or 0.0
                    )
                ),
                "stun_interrupt_deferred_until_landing": bool(
                    getattr(
                        entity,
                        "_stun_interrupt_deferred_until_landing",
                        False,
                    )
                ),
                "forced_movement_active": bool(
                    entity.forced_movement_active
                ),
                "vector_bypasses_cap": bool(
                    entity._movement_vector_bypasses_cap
                ),
                "vector_count": int(entity._movement_vector_count),
                "vector_x_units": int(entity._movement_vector_x_units),
                "vector_y_units": int(entity._movement_vector_y_units),
                "wait_ms": _exact_scalar(
                    float(getattr(entity.card_stats, "wait_ms", 0.0) or 0.0)
                ),
            }
        )
        status_mechanic = next(
            (
                mechanic
                for mechanic in entity.mechanics
                if type(mechanic) is IceSpiritFreeze
            ),
            None,
        )
        if status_mechanic is not None:
            destination = entity._ice_spirit_jump_destination
            origin = getattr(entity, "_ice_spirit_jump_origin", None)
            rows[-1].update(
                {
                    "status_nova_affects_hidden": bool(
                        getattr(entity.card_stats, "projectile_data", {}).get(
                            "affectsHidden", False
                        )
                    ),
                    "status_nova_detonated": bool(entity._ice_spirit_detonated),
                    "status_nova_freeze_duration_ms": int(
                        status_mechanic.freeze_duration_ms
                    ),
                    "status_nova_freeze_radius_units": round(
                        status_mechanic.freeze_radius * 1000.0
                    ),
                    "status_nova_hits_air": bool(entity._can_attack_air_cached),
                    "status_nova_hits_ground": bool(
                        entity._can_attack_ground_cached
                    ),
                    "status_nova_hop_duration_ms": int(
                        status_mechanic.hop_duration_ms
                    ),
                    "status_nova_jump_destination": (
                        None
                        if destination is None
                        else [
                            _exact_scalar(destination[0]),
                            _exact_scalar(destination[1]),
                        ]
                    ),
                    "status_nova_jump_origin": (
                        None
                        if origin is None
                        else [_exact_scalar(origin[0]), _exact_scalar(origin[1])]
                    ),
                    "status_nova_jump_speed_units_per_tick": int(
                        status_mechanic.jump_speed_logic_units_per_tick
                    ),
                    "status_nova_jump_target_id": entity._ice_spirit_jump_target,
                    "status_nova_jump_timer_ms": _exact_scalar(
                        entity._ice_spirit_jump_timer
                    ),
                }
            )
    return rows


def flying_movement_state_bytes(battle: Any) -> bytes:
    return json.dumps(
        flying_movement_state_rows(battle),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def compare_flying_movement_phase(
    battle: Any,
    resident: ResidentRustBattle,
) -> None:
    expected = flying_movement_state_rows(battle)
    actual = json.loads(resident.flying_movement_state_bytes())
    if expected != actual:
        from .differential import first_snapshot_difference

        difference = first_snapshot_difference(expected, actual)
        if difference is None:  # pragma: no cover - defensive
            raise AssertionError("resident Rust flying movement mismatch")
        raise AssertionError(
            "resident Rust flying movement parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )
    expected_hash = hashlib.sha256(
        flying_movement_state_bytes(battle)
    ).hexdigest()
    actual_hash = resident.flying_movement_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust flying movement hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )


def compare_ground_movement_phase(
    battle: Any,
    resident: ResidentRustBattle,
) -> None:
    expected = flying_movement_state_rows(battle)
    actual = json.loads(resident.ground_movement_state_bytes())
    if expected != actual:
        from .differential import first_snapshot_difference

        difference = first_snapshot_difference(expected, actual)
        if difference is None:  # pragma: no cover - defensive
            raise AssertionError("resident Rust ground movement mismatch")
        raise AssertionError(
            "resident Rust ground movement parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )
    expected_hash = hashlib.sha256(
        flying_movement_state_bytes(battle)
    ).hexdigest()
    actual_hash = resident.ground_movement_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust ground movement hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )


def locked_direct_combat_state_rows(battle: Any) -> list[dict[str, Any]]:
    from .cards.tesla import HideWhenIdle
    from .cards.wallbreakers import WallBreakersDemolition
    from .mechanics.shared.damage_ramp import DamageRamp

    rows: list[dict[str, Any]] = []
    for encounter_index, entity in enumerate(battle.entities.values()):
        if entity.entity_kind not in {0, 1}:
            continue
        initial_position = getattr(entity, "initial_position", None)
        damage_ramp = next(
            (
                mechanic
                for mechanic in entity.mechanics
                if type(mechanic) is DamageRamp
            ),
            None,
        )
        hide_when_idle = next(
            (
                mechanic
                for mechanic in entity.mechanics
                if type(mechanic) is HideWhenIdle
            ),
            None,
        )
        demolition = next(
            (
                mechanic
                for mechanic in entity.mechanics
                if type(mechanic) is WallBreakersDemolition
            ),
            None,
        )
        rows.append(
            {
                "attack_cooldown": _exact_scalar(entity.attack_cooldown),
                "attack_preload_blocked": bool(entity._attack_preload_blocked),
                "attack_windup_active": bool(entity._attack_windup_active),
                "damage_ramp": (
                    None
                    if damage_ramp is None
                    else {
                        "current_target_id": getattr(
                            damage_ramp, "_current_target_id", None
                        ),
                        "current_target_ms": _exact_scalar(
                            getattr(damage_ramp, "_current_target_ms", 0.0)
                        ),
                        "current_target_ms_present": (
                            "_current_target_ms" in vars(damage_ramp)
                        ),
                        "current_target_present": (
                            "_current_target_id" in vars(damage_ramp)
                        ),
                        "stages": [list(stage) for stage in damage_ramp.stages],
                        "stored_original_damage": int(
                            damage_ramp.stored_original_damage
                        ),
                    }
                ),
                "encounter_index": encounter_index,
                "facing_x_units": int(entity._facing_x_units),
                "facing_y_units": int(entity._facing_y_units),
                "has_attacked_once": bool(
                    getattr(entity, "_has_attacked_once", False)
                ),
                "hide_when_idle": (
                    None
                    if hide_when_idle is None
                    else {
                        "hide_delay_ms": int(hide_when_idle.hide_delay_ms),
                        "phase_ms": _exact_scalar(hide_when_idle._phase_ms),
                        "rise_time_ms": int(hide_when_idle.rise_time_ms),
                    }
                ),
                "wall_breakers_demolition": (
                    None
                    if demolition is None
                    else {"triggered": bool(demolition._triggered)}
                ),
                "hidden_building": bool(
                    getattr(entity, "_hidden_building", False)
                ),
                "hitpoints": _exact_scalar(entity.hitpoints),
                "id": int(entity.id),
                "initial_position": (
                    None
                    if initial_position is None
                    else [
                        _exact_scalar(initial_position.x),
                        _exact_scalar(initial_position.y),
                    ]
                ),
                "is_alive": bool(entity.is_alive),
                "last_attack_time": _exact_scalar(entity.last_attack_time),
                "last_combat_target_id": getattr(
                    entity,
                    "_last_combat_target_id",
                    None,
                ),
                "movement_target_id": getattr(
                    entity,
                    "_movement_target_id",
                    None,
                ),
                "native_target_distance_discount_sq_units": int(
                    getattr(
                        entity,
                        "_native_target_distance_discount_sq_units",
                        0,
                    )
                ),
                "target_id": entity.target_id,
            }
        )
    return rows


def locked_direct_combat_state_bytes(battle: Any) -> bytes:
    return json.dumps(
        locked_direct_combat_state_rows(battle),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def compare_locked_direct_combat_phase(
    battle: Any,
    resident: ResidentRustBattle,
) -> None:
    expected = locked_direct_combat_state_rows(battle)
    actual = json.loads(resident.locked_direct_combat_state_bytes())
    if expected != actual:
        from .differential import first_snapshot_difference

        difference = first_snapshot_difference(expected, actual)
        if difference is None:  # pragma: no cover - defensive
            raise AssertionError("resident Rust locked combat state mismatch")
        raise AssertionError(
            "resident Rust locked combat parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )
    expected_hash = hashlib.sha256(
        locked_direct_combat_state_bytes(battle)
    ).hexdigest()
    actual_hash = resident.locked_direct_combat_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust locked combat hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )


def building_lifetime_state_rows(battle: Any) -> list[dict[str, Any]]:
    return [
        {
            "activation_delay_remaining": _exact_scalar(
                entity.activation_delay_remaining
            ),
            "activation_first_hit_delay_remaining": _exact_scalar(
                entity.activation_first_hit_delay_remaining
            ),
            "crown_slot": entity._crown_tower_slot,
            "encounter_index": encounter_index,
            "hitpoints": _exact_scalar(entity.hitpoints),
            "id": int(entity.id),
            "is_alive": bool(entity.is_alive),
            "lifetime_decay_work": int(entity.lifetime_decay_work),
            "lifetime_elapsed": _exact_scalar(entity.lifetime_elapsed),
            "lifetime_tick_carry_ms": _exact_scalar(
                entity.lifetime_tick_carry_ms
            ),
            "tower_active": bool(getattr(entity, "_tower_active", True)),
        }
        for encounter_index, entity in enumerate(battle.entities.values())
        if entity.entity_kind == 1
    ]


def building_lifetime_state_bytes(battle: Any) -> bytes:
    return json.dumps(
        building_lifetime_state_rows(battle),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def point_projectile_state_rows(battle: Any) -> list[dict[str, Any]]:
    from .entities import Projectile, SpawnProjectile

    group_projectile_ids: dict[int, list[int]] = {}
    for entity in battle.entities.values():
        if type(entity) is Projectile and entity.damage_group_hit_entity_ids is not None:
            group_projectile_ids.setdefault(
                id(entity.damage_group_hit_entity_ids), []
            ).append(int(entity.id))

    return [
        {
            "encounter_index": encounter_index,
            "crown_tower_damage": (
                None
                if entity.crown_tower_damage is None
                else _exact_scalar(entity.crown_tower_damage)
            ),
            "crown_tower_damage_multiplier": _exact_scalar(
                entity.crown_tower_damage_multiplier
            ),
            "damage": _exact_scalar(entity.damage),
            "damage_group_id": (
                None
                if entity.damage_group_hit_entity_ids is None
                else min(group_projectile_ids[id(entity.damage_group_hit_entity_ids)])
            ),
            "damage_wave_interval": _exact_scalar(entity.damage_wave_interval),
            "hits_air": bool(entity.hits_air),
            "hits_ground": bool(entity.hits_ground),
            "hitpoints": _exact_scalar(entity.hitpoints),
            "id": int(entity.id),
            "ignore_buildings": bool(entity.ignore_buildings),
            "pierces": bool(entity.pierces),
            "projectile_range": _exact_scalar(entity.projectile_range),
            "hit_entity_ids": sorted(int(value) for value in entity.hit_entity_ids),
            "is_alive": bool(entity.is_alive),
            "launch_delay": _exact_scalar(entity.launch_delay),
            "knockback_distance": _exact_scalar(entity.knockback_distance),
            "knockback_ignores_mass": bool(entity.knockback_ignores_mass),
            "permanent_homing_disabled_by_temporary": bool(
                getattr(
                    entity,
                    "_permanent_homing_disabled_by_temporary",
                    False,
                )
            ),
            "position_x": _exact_scalar(entity.position.x),
            "position_y": _exact_scalar(entity.position.y),
            "primary_target_id": _entity_id_or_none(entity.primary_target),
            "splash_radius": _exact_scalar(entity.splash_radius),
            "slow_duration": _exact_scalar(entity.slow_duration),
            "slow_multiplier": _exact_scalar(entity.slow_multiplier),
            "source_entity_id": _entity_id_or_none(entity.source_entity),
            "source_kind": str(
                getattr(entity, "spell_name", None) or entity.source_name
            ),
            "start_collision_resolved": bool(entity.start_collision_resolved),
            "stun_duration": _exact_scalar(entity.stun_duration),
            "target_position_x": _exact_scalar(entity.target_position.x),
            "target_position_y": _exact_scalar(entity.target_position.y),
            "tracks_target": bool(entity.tracks_target),
            "travel_speed": _exact_scalar(entity.travel_speed),
            "temporary_homing_remaining_ms": int(
                getattr(entity, "_temporary_homing_remaining_ms", 0)
            ),
            "temporary_homing_target_id": (
                _entity_id_or_none(
                    getattr(entity, "_temporary_homing_target", None)
                )
            ),
            "spawn_projectile_state": (
                None
                if type(entity) is Projectile
                else {
                    "activation_delay": _exact_scalar(entity.activation_delay),
                    "spawn_character": str(entity.spawn_character),
                    "spawn_count": int(entity.spawn_count),
                    "spawn_data_fingerprint": _normalized_sha256(
                        entity.spawn_character_data
                    ),
                    "spawn_deploy_delay": (
                        None
                        if entity.spawn_deploy_delay_override is None
                        else _exact_scalar(entity.spawn_deploy_delay_override)
                    ),
                    "spawn_radius": (
                        None
                        if entity.spawn_radius is None
                        else _exact_scalar(entity.spawn_radius)
                    ),
                    "spawn_const_priority": bool(entity.spawn_const_priority),
                    "time_alive": _exact_scalar(entity.time_alive),
                }
            ),
        }
        for encounter_index, entity in enumerate(battle.entities.values())
        if type(entity) in (Projectile, SpawnProjectile)
    ]


def point_projectile_state_bytes(battle: Any) -> bytes:
    return json.dumps(
        point_projectile_state_rows(battle),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def rolling_projectile_state_rows(battle: Any) -> list[dict[str, Any]]:
    from .entities import RollingProjectile

    return [
        {
            "crown_tower_damage": (
                None
                if entity.crown_tower_damage is None
                else _exact_scalar(entity.crown_tower_damage)
            ),
            "crown_tower_damage_multiplier": _exact_scalar(
                entity.crown_tower_damage_multiplier
            ),
            "damage": _exact_scalar(entity.damage),
            "distance_traveled": _exact_scalar(entity.distance_traveled),
            "encounter_index": encounter_index,
            "has_spawned_character": bool(entity.has_spawned_character),
            "hit_entity_ids": sorted(int(value) for value in entity.hit_entities),
            "id": int(entity.id),
            "is_alive": bool(entity.is_alive),
            "knockback_distance": _exact_scalar(entity.knockback_distance),
            "knockback_ignores_mass": bool(entity.knockback_ignores_mass),
            "player_id": int(entity.player_id),
            "position_x": _exact_scalar(entity.position.x),
            "position_y": _exact_scalar(entity.position.y),
            "projectile_range": _exact_scalar(entity.projectile_range),
            "radius_y": _exact_scalar(entity.radius_y),
            "rolling_radius": _exact_scalar(entity.rolling_radius),
            "source_kind": str(cast(Any, entity).spell_name),
            "spawn_delay": _exact_scalar(entity.spawn_delay),
            "time_alive": _exact_scalar(entity.time_alive),
            "travel_speed": _exact_scalar(entity.travel_speed),
        }
        for encounter_index, entity in enumerate(battle.entities.values())
        if type(entity) is RollingProjectile
    ]


def rolling_projectile_state_bytes(battle: Any) -> bytes:
    return json.dumps(
        rolling_projectile_state_rows(battle),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def compare_point_projectile_phase(
    battle: Any,
    resident: ResidentRustBattle,
) -> None:
    expected = point_projectile_state_rows(battle)
    actual = json.loads(resident.point_projectile_state_bytes())
    if expected != actual:
        from .differential import first_snapshot_difference

        difference = first_snapshot_difference(expected, actual)
        if difference is None:  # pragma: no cover - defensive
            raise AssertionError("resident Rust point-projectile state mismatch")
        raise AssertionError(
            "resident Rust point-projectile parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )
    expected_hash = hashlib.sha256(
        point_projectile_state_bytes(battle)
    ).hexdigest()
    actual_hash = resident.point_projectile_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust point-projectile hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )
    compare_resident_entities(battle, resident)
    compare_resident_rng(battle.rng, resident)
    if int(battle.next_entity_id) != resident.next_entity_id:
        raise AssertionError(
            "resident Rust next entity ID mismatch "
            f"expected={battle.next_entity_id} actual={resident.next_entity_id}"
        )


def compare_building_lifetime_phase(
    battle: Any,
    resident: ResidentRustBattle,
) -> None:
    expected = building_lifetime_state_rows(battle)
    actual = json.loads(resident.building_lifetime_state_bytes())
    if expected != actual:
        from .differential import first_snapshot_difference

        difference = first_snapshot_difference(expected, actual)
        if difference is None:  # pragma: no cover - defensive
            raise AssertionError("resident Rust building lifetime state mismatch")
        raise AssertionError(
            "resident Rust building lifetime parity mismatch "
            f"path={difference.path} reason={difference.reason} "
            f"expected={difference.expected!r} actual={difference.actual!r}"
        )
    expected_hash = hashlib.sha256(
        building_lifetime_state_bytes(battle)
    ).hexdigest()
    actual_hash = resident.building_lifetime_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust building lifetime hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )


def apply_idle_state(battle: Any, resident: ResidentRustBattle) -> None:
    """Publish resident idle state at one explicit Python boundary."""
    clock = resident.clock_state()
    battle.tick = clock.tick
    battle.time = clock.time
    battle.dt = clock.dt
    battle.double_elixir = clock.double_elixir
    battle.triple_elixir = clock.triple_elixir
    battle.overtime = clock.overtime
    battle.game_over = clock.game_over

    player_states = resident.player_states()
    if len(player_states) != len(battle.players):
        raise RuntimeError(
            "resident idle export has a different player count: "
            f"rust={len(player_states)} python={len(battle.players)}"
        )
    for player, player_state in zip(battle.players, player_states, strict=True):
        if int(player.player_id) != player_state.player_id:
            raise RuntimeError(
                "resident idle export changed player order: "
                f"rust={player_state.player_id} python={player.player_id}"
            )
        player.elixir = player_state.elixir
        player.max_elixir = player_state.max_elixir
        player.next_card_refill_cooldown_ms = (
            player_state.next_card_refill_cooldown_ms
        )
        player.hand[:] = player_state.hand
        player.cycle_queue = deque(player_state.cycle_queue)
        # Idle ticks never change tower HP. Keeping the Python values avoids
        # turning exact integer tower snapshots into binary64 at publication.

    towers_by_id = {
        entity.id: entity
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity._crown_tower_slot in {"left", "right", "king"}
    }
    tower_states = resident.tower_states()
    if set(towers_by_id) != {state.id for state in tower_states}:
        raise RuntimeError("resident idle export changed Crown Tower membership")
    for tower_state in tower_states:
        tower = towers_by_id[tower_state.id]
        if (
            tower.player_id != tower_state.player_id
            or tower._crown_tower_slot != tower_state.slot
        ):
            raise RuntimeError(
                "resident idle export changed Crown Tower identity "
                f"id={tower_state.id}"
            )
        # The idle path never mutates tower HP/liveness/activation. Preserve
        # their original Python scalar types and instance/class field layout;
        # only the visualization clock advances in this coherent phase.
        tower.last_attack_time = tower_state.last_attack_time

    outcome = resident.outcome_state()
    battle.sudden_death = outcome.sudden_death
    battle.game_over = outcome.game_over
    battle.winner = outcome.winner
    if (
        "_sudden_death_crowns" in battle.__dict__
        or outcome.sudden_death_crowns != (0, 0)
    ):
        battle._sudden_death_crowns = outcome.sudden_death_crowns


assert SNAPSHOT_SCHEMA_VERSION == 2
