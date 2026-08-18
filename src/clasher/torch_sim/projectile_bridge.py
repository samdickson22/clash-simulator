"""Resident combat-projectile and spell-payload bridge.

The bridge reserves one catalog blueprint per battle/object slot so launch
metadata can remain immutable for the lifetime of a projectile while the
ordinary retained object phase batches travel and impacts.  Unsupported
payload families are rejected per row before entity allocation or RNG use.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum
from typing import Any, cast

import torch

from clasher.battle import BattleState
from clasher.entities import troop_from_character_data
from clasher.formations import formation_offset
from clasher.gamedata_normalization import serialized_hit_planes
from clasher.kinematics import tiles_to_logic_units
from clasher.logic_math import _SIN_TABLE
from clasher.mechanics.mechanic_base import BaseMechanic
from clasher.native_tilemap import (
    HALF_TILE_LOGIC_UNITS,
    STANDARD_PATH_HEIGHT,
    STANDARD_PATH_ROWS,
    STANDARD_PATH_WIDTH,
)
from clasher.spells import (
    SPELL_REGISTRY,
    AreaEffectSpell,
    DirectDamageSpell,
    ProjectileSpell,
    SpawnProjectileSpell,
)
from clasher.unit_traits import is_knockback_immune

from .catalog import MECHANIC_OPCODE
from .combat import CombatStepResult, StationaryCombatState
from .entity_pool import INVALID_SLOT
from .object_adapter import RuntimeObjectKind
from .objects import (
    ObjectBlueprint,
    ObjectOpcode,
    TensorObjectCatalog,
    _integer_sqrt,
    _trunc_div,
)
from .runtime_objects import (
    RuntimeObjectPhaseResult,
    TensorRuntimeObjectPhase,
    step_runtime_object_phase_,
)
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


class BridgePayloadKind(IntEnum):
    UNSUPPORTED = 0
    COMBAT_PROJECTILE = 1
    DIRECT_SPELL = 2
    PROJECTILE_SPELL = 3
    AREA_SPELL = 4
    SPAWN_PROJECTILE = 5


class ProjectilePatternOpcode(IntEnum):
    NATIVE_RADIAL = 0
    GROUPED_RING = 1


@dataclass(frozen=True)
class TensorProjectileSpellCatalog:
    device: torch.device
    kind: torch.Tensor
    supported: torch.Tensor
    unsupported_reason: tuple[str | None, ...]
    projectile_speed_units: torch.Tensor
    radius_units: torch.Tensor
    damage: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    ignore_buildings: torch.Tensor
    crown_multiplier: torch.Tensor
    crown_damage: torch.Tensor
    crown_damage_valid: torch.Tensor
    stun_ms: torch.Tensor
    slow_ms: torch.Tensor
    slow_multiplier: torch.Tensor
    slow_attack_multiplier: torch.Tensor
    slow_spawn_multiplier: torch.Tensor
    knockback_units: torch.Tensor
    knockback_ignores_mass: torch.Tensor
    duration_ms: torch.Tensor
    interval_ms: torch.Tensor
    initial_delay_ms: torch.Tensor
    max_ticks: torch.Tensor
    damage_on_spawn: torch.Tensor
    projectile_start_radius_units: torch.Tensor
    projectile_y_offset_units: torch.Tensor
    tracks_target: torch.Tensor
    card_knockback_immune: torch.Tensor
    multiple_projectiles: torch.Tensor
    damage_waves: torch.Tensor
    damage_wave_interval_ms: torch.Tensor
    spread_radius_units: torch.Tensor
    projectile_pattern: torch.Tensor
    spawn_card_id: torch.Tensor
    spawn_count: torch.Tensor
    spawn_deploy_delay_ms: torch.Tensor
    spawn_const_priority: torch.Tensor
    spawn_offsets_units: torch.Tensor
    spawn_hp_integer_kind: torch.Tensor
    spawn_hitpoints: torch.Tensor
    spawn_collision_radius_units: torch.Tensor
    spawn_is_air_unit: torch.Tensor
    spawn_lifetime_ms: torch.Tensor

    @classmethod
    def compile(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
    ) -> TensorProjectileSpellCatalog:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match runtime")
        if runtime.device.type not in {"cpu", "cuda"}:
            raise ValueError("exact projectile bridge supports CPU and CUDA only")
        size = len(runtime.battle.card_names)
        device = runtime.device

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        kind = zeros(torch.int8)
        supported = torch.zeros(size, dtype=torch.bool, device=device)
        speed = zeros(torch.int32)
        radius = zeros(torch.int32)
        damage = zeros(torch.float64)
        hits_air = torch.ones(size, dtype=torch.bool, device=device)
        hits_ground = torch.ones(size, dtype=torch.bool, device=device)
        ignore_buildings = zeros(torch.bool)
        crown_multiplier = torch.ones(size, dtype=torch.float64, device=device)
        crown_damage = zeros(torch.float64)
        crown_damage_valid = zeros(torch.bool)
        stun_ms = zeros(torch.int32)
        slow_ms = zeros(torch.int32)
        slow_multiplier = torch.ones(size, dtype=torch.float64, device=device)
        slow_attack = torch.ones(size, dtype=torch.float64, device=device)
        slow_spawn = torch.ones(size, dtype=torch.float64, device=device)
        knockback = zeros(torch.int32)
        knockback_ignores = zeros(torch.bool)
        duration_ms = zeros(torch.int32)
        interval_ms = zeros(torch.int32)
        initial_delay_ms = zeros(torch.int32)
        max_ticks = zeros(torch.int16)
        damage_on_spawn = zeros(torch.bool)
        start_radius = zeros(torch.int32)
        y_offset = zeros(torch.int32)
        tracks_target = zeros(torch.bool)
        card_knockback_immune = zeros(torch.bool)
        multiple_projectiles = torch.ones(size, dtype=torch.int16, device=device)
        damage_waves = torch.ones(size, dtype=torch.int16, device=device)
        damage_wave_interval = zeros(torch.int32)
        spread_radius = zeros(torch.int32)
        projectile_pattern = zeros(torch.int8)
        spawn_card_id = zeros(torch.int64)
        spawn_count = zeros(torch.int16)
        spawn_deploy_delay = zeros(torch.int32)
        spawn_const_priority = zeros(torch.bool)
        maximum_spawn_count = max(
            1,
            max(
                (
                    int(spell.spawn_count)
                    for spell in SPELL_REGISTRY.values()
                    if isinstance(spell, SpawnProjectileSpell)
                ),
                default=1,
            ),
        )
        spawn_offsets = torch.zeros(
            (size, 2, 2, maximum_spawn_count, 2),
            dtype=torch.int32,
            device=device,
        )
        spawn_hp_integer_kind = zeros(torch.bool)
        spawn_hitpoints = zeros(torch.float64)
        spawn_collision_radius = zeros(torch.int32)
        spawn_is_air = zeros(torch.bool)
        spawn_lifetime = zeros(torch.int64)
        reasons: list[str | None] = ["padding has no payload"] * size
        definitions = battles[0].card_loader.load_card_definitions()

        for card_id, name in enumerate(runtime.battle.card_names[1:], start=1):
            stats = battles[0].card_loader.get_card(name)
            if stats is not None:
                card_knockback_immune[card_id] = is_knockback_immune(stats)
            spell = SPELL_REGISTRY.get(name)
            if spell is not None:
                operation = cast(Any, spell)
                damage[card_id] = float(operation.damage)
                radius[card_id] = tiles_to_logic_units(operation.radius)
                if isinstance(spell, DirectDamageSpell):
                    kind[card_id] = BridgePayloadKind.DIRECT_SPELL
                    _load_direct_spell(
                        card_id,
                        operation,
                        hits_air,
                        hits_ground,
                        ignore_buildings,
                        crown_multiplier,
                        crown_damage,
                        crown_damage_valid,
                        stun_ms,
                        slow_ms,
                        slow_multiplier,
                        slow_attack,
                        slow_spawn,
                        knockback,
                        knockback_ignores,
                    )
                    reason = _direct_spell_reason(operation)
                elif isinstance(spell, SpawnProjectileSpell):
                    kind[card_id] = BridgePayloadKind.SPAWN_PROJECTILE
                    _load_projectile_spell(
                        card_id,
                        operation,
                        speed,
                        hits_air,
                        hits_ground,
                        crown_multiplier,
                        crown_damage,
                        crown_damage_valid,
                        stun_ms,
                        slow_ms,
                        slow_multiplier,
                        slow_attack,
                        slow_spawn,
                        knockback,
                        knockback_ignores,
                    )
                    child_id = runtime.battle.card_to_id.get(
                        str(operation.spawn_character), 0
                    )
                    spawn_card_id[card_id] = child_id
                    spawn_count[card_id] = max(0, int(operation.spawn_count))
                    child_data = operation.spawn_character_data or {}
                    child_stats = (
                        troop_from_character_data(
                            str(operation.spawn_character),
                            child_data,
                            elixir=0,
                            rarity=child_data.get("rarity", "Common"),
                        )
                        if child_data
                        else None
                    )
                    child_hp = (
                        None
                        if child_stats is None
                        else child_stats.scaled_hitpoints or child_stats.hitpoints
                    )
                    spawn_hp_integer_kind[card_id] = type(child_hp) is int
                    spawn_hitpoints[card_id] = float(child_hp or 100)
                    if child_stats is not None:
                        spawn_collision_radius[card_id] = tiles_to_logic_units(
                            float(child_stats.collision_radius or 0.5)
                        )
                        spawn_is_air[card_id] = bool(
                            getattr(child_stats, "is_air_unit", False)
                        )
                        spawn_lifetime[card_id] = int(child_stats.lifetime_ms or 0)
                    deploy_delay = operation.spawn_deploy_delay
                    if deploy_delay is None and child_stats is not None:
                        deploy_delay = float(child_stats.deploy_time or 0) / 1_000
                    spawn_deploy_delay[card_id] = round(
                        max(0.0, float(deploy_delay or 0.0)) * 1_000
                    )
                    spawn_const_priority[card_id] = bool(operation.spawn_const_priority)
                    if child_stats is not None:
                        spacing = (
                            float(operation.spawn_radius)
                            if operation.spawn_radius is not None
                            else float(child_stats.collision_radius or 0.5)
                        )
                        angle_shift = float(child_stats.spawn_angle_shift or 0)
                        for owner in range(2):
                            for lane_index, lane_id in enumerate((2, 1)):
                                for child_index in range(
                                    max(0, int(operation.spawn_count))
                                ):
                                    offset = formation_offset(
                                        child_index,
                                        int(operation.spawn_count),
                                        spacing,
                                        owner,
                                        angle_shift,
                                        lane_id=lane_id,
                                    )
                                    spawn_offsets[
                                        card_id, owner, lane_index, child_index
                                    ] = torch.tensor(
                                        (
                                            tiles_to_logic_units(offset[0]),
                                            tiles_to_logic_units(offset[1]),
                                        ),
                                        dtype=torch.int32,
                                        device=device,
                                    )
                    reason = _spawn_projectile_reason(
                        operation,
                        child_id,
                        child_stats,
                        _spawn_catalog_matches(runtime, child_id, child_stats),
                    )
                elif isinstance(spell, ProjectileSpell):
                    kind[card_id] = BridgePayloadKind.PROJECTILE_SPELL
                    _load_projectile_spell(
                        card_id,
                        operation,
                        speed,
                        hits_air,
                        hits_ground,
                        crown_multiplier,
                        crown_damage,
                        crown_damage_valid,
                        stun_ms,
                        slow_ms,
                        slow_multiplier,
                        slow_attack,
                        slow_spawn,
                        knockback,
                        knockback_ignores,
                    )
                    multiple_projectiles[card_id] = max(
                        1, int(operation.multiple_projectiles)
                    )
                    damage_waves[card_id] = max(1, int(operation.damage_waves))
                    damage_wave_interval[card_id] = round(
                        operation.damage_wave_interval * 1_000
                    )
                    spread_radius[card_id] = tiles_to_logic_units(
                        operation.spread_radius
                    )
                    projectile_pattern[card_id] = (
                        ProjectilePatternOpcode.GROUPED_RING
                        if operation.projectile_pattern == "grouped_ring"
                        else ProjectilePatternOpcode.NATIVE_RADIAL
                    )
                    reason = _projectile_spell_reason(operation)
                elif isinstance(spell, AreaEffectSpell):
                    kind[card_id] = BridgePayloadKind.AREA_SPELL
                    _load_area_spell(
                        card_id,
                        operation,
                        hits_air,
                        hits_ground,
                        crown_multiplier,
                        crown_damage,
                        crown_damage_valid,
                        duration_ms,
                        interval_ms,
                        initial_delay_ms,
                        max_ticks,
                        damage_on_spawn,
                    )
                    reason = _area_spell_reason(operation)
                else:
                    reason = f"spell family {type(spell).__name__} is not retained"
                reasons[card_id] = reason
                supported[card_id] = reason is None
                continue

            if stats is None or not getattr(stats, "projectile_data", None):
                reasons[card_id] = "card has no projectile payload"
                continue
            operation = cast(dict[str, Any], stats.projectile_data)
            kind[card_id] = BridgePayloadKind.COMBAT_PROJECTILE
            speed[card_id] = int(operation.get("speed", 0) or 0)
            radius[card_id] = int(operation.get("radius", 0) or 0)
            damage[card_id] = float(stats.scaled_damage or stats.damage or 0)
            air, ground = serialized_hit_planes(operation)
            hits_air[card_id] = air
            hits_ground[card_id] = ground
            crown_multiplier[card_id] = max(
                0.0,
                1.0 + float(operation.get("crownTowerDamagePercent", 0) or 0) / 100.0,
            )
            buff = operation.get("targetBuffData") or {}
            slow_ms[card_id] = int(operation.get("buffTime", 0) or 0)
            slow_multiplier[card_id] = max(
                0.0, 1.0 + float(buff.get("speedMultiplier", 0) or 0) / 100.0
            )
            slow_attack[card_id] = max(
                0.0,
                1.0 + float(buff.get("hitSpeedMultiplier", 0) or 0) / 100.0,
            )
            slow_spawn[card_id] = max(
                0.0,
                1.0 + float(buff.get("spawnSpeedMultiplier", 0) or 0) / 100.0,
            )
            knockback[card_id] = int(operation.get("pushback", 0) or 0)
            knockback_ignores[card_id] = bool(
                operation.get("ignorePushbackResistance", False)
            )
            if (
                buff.get("speedMultiplier") == -100
                and buff.get("hitSpeedMultiplier") == -100
                and slow_ms[card_id] > 0
            ):
                stun_ms[card_id] = slow_ms[card_id]
                slow_ms[card_id] = 0
                slow_multiplier[card_id] = 1.0
                slow_attack[card_id] = 1.0
                slow_spawn[card_id] = 1.0
            start_radius[card_id] = tiles_to_logic_units(
                float(getattr(stats, "projectile_start_radius", 0.0) or 0.0)
            )
            y_offset[card_id] = tiles_to_logic_units(
                float(getattr(stats, "projectile_y_offset", 0.0) or 0.0)
            )
            tracks_target[card_id] = bool(operation.get("homing", True))
            explicit_crown = _projectile_crown_damage(
                definitions, name, damage[card_id]
            )
            if explicit_crown is not None:
                crown_damage[card_id] = explicit_crown
                crown_damage_valid[card_id] = True
            reason = _combat_projectile_reason(operation)
            unsupported_callbacks = _projectile_attack_callback_names(
                definitions[name].mechanics
            )
            if reason is None and unsupported_callbacks:
                reason = "projectile impact callbacks are not retained: " + ",".join(
                    unsupported_callbacks
                )
            reasons[card_id] = reason
            supported[card_id] = reason is None

        return cls(
            device=device,
            kind=kind,
            supported=supported,
            unsupported_reason=tuple(reasons),
            projectile_speed_units=speed,
            radius_units=radius,
            damage=damage,
            hits_air=hits_air,
            hits_ground=hits_ground,
            ignore_buildings=ignore_buildings,
            crown_multiplier=crown_multiplier,
            crown_damage=crown_damage,
            crown_damage_valid=crown_damage_valid,
            stun_ms=stun_ms,
            slow_ms=slow_ms,
            slow_multiplier=slow_multiplier,
            slow_attack_multiplier=slow_attack,
            slow_spawn_multiplier=slow_spawn,
            knockback_units=knockback,
            knockback_ignores_mass=knockback_ignores,
            duration_ms=duration_ms,
            interval_ms=interval_ms,
            initial_delay_ms=initial_delay_ms,
            max_ticks=max_ticks,
            damage_on_spawn=damage_on_spawn,
            projectile_start_radius_units=start_radius,
            projectile_y_offset_units=y_offset,
            tracks_target=tracks_target,
            card_knockback_immune=card_knockback_immune,
            multiple_projectiles=multiple_projectiles,
            damage_waves=damage_waves,
            damage_wave_interval_ms=damage_wave_interval,
            spread_radius_units=spread_radius,
            projectile_pattern=projectile_pattern,
            spawn_card_id=spawn_card_id,
            spawn_count=spawn_count,
            spawn_deploy_delay_ms=spawn_deploy_delay,
            spawn_const_priority=spawn_const_priority,
            spawn_offsets_units=spawn_offsets,
            spawn_hp_integer_kind=spawn_hp_integer_kind,
            spawn_hitpoints=spawn_hitpoints,
            spawn_collision_radius_units=spawn_collision_radius,
            spawn_is_air_unit=spawn_is_air,
            spawn_lifetime_ms=spawn_lifetime,
        )


def _load_direct_spell(
    card_id: int,
    spell: Any,
    hits_air: torch.Tensor,
    hits_ground: torch.Tensor,
    ignore_buildings: torch.Tensor,
    crown_multiplier: torch.Tensor,
    crown_damage: torch.Tensor,
    crown_damage_valid: torch.Tensor,
    stun_ms: torch.Tensor,
    slow_ms: torch.Tensor,
    slow_multiplier: torch.Tensor,
    slow_attack: torch.Tensor,
    slow_spawn: torch.Tensor,
    knockback: torch.Tensor,
    knockback_ignores: torch.Tensor,
) -> None:
    hits_air[card_id] = spell.hits_air
    hits_ground[card_id] = spell.hits_ground
    ignore_buildings[card_id] = bool(getattr(spell, "ignore_buildings", False))
    crown_multiplier[card_id] = spell.crown_tower_damage_multiplier
    if spell.crown_tower_damage is not None:
        crown_damage[card_id] = spell.crown_tower_damage
        crown_damage_valid[card_id] = True
    stun_ms[card_id] = round(spell.stun_duration * 1_000)
    slow_ms[card_id] = round(spell.slow_duration * 1_000)
    slow_multiplier[card_id] = spell.slow_multiplier
    slow_attack[card_id] = spell.slow_multiplier
    slow_spawn[card_id] = spell.slow_multiplier
    knockback[card_id] = tiles_to_logic_units(spell.knockback_distance)
    knockback_ignores[card_id] = spell.knockback_ignores_mass


def _load_projectile_spell(
    card_id: int,
    spell: Any,
    speed: torch.Tensor,
    hits_air: torch.Tensor,
    hits_ground: torch.Tensor,
    crown_multiplier: torch.Tensor,
    crown_damage: torch.Tensor,
    crown_damage_valid: torch.Tensor,
    stun_ms: torch.Tensor,
    slow_ms: torch.Tensor,
    slow_multiplier: torch.Tensor,
    slow_attack: torch.Tensor,
    slow_spawn: torch.Tensor,
    knockback: torch.Tensor,
    knockback_ignores: torch.Tensor,
) -> None:
    speed[card_id] = round(spell.travel_speed * 1_000 / 20)
    hits_air[card_id] = spell.hits_air
    hits_ground[card_id] = spell.hits_ground
    crown_multiplier[card_id] = spell.crown_tower_damage_multiplier
    if spell.crown_tower_damage is not None:
        crown_damage[card_id] = spell.crown_tower_damage
        crown_damage_valid[card_id] = True
    stun_ms[card_id] = round(spell.stun_duration * 1_000)
    slow_ms[card_id] = round(spell.slow_duration * 1_000)
    slow_multiplier[card_id] = spell.slow_multiplier
    slow_attack[card_id] = spell.slow_multiplier
    slow_spawn[card_id] = spell.slow_multiplier
    knockback[card_id] = tiles_to_logic_units(spell.knockback_distance)
    knockback_ignores[card_id] = spell.knockback_ignores_mass


def _load_area_spell(
    card_id: int,
    spell: Any,
    hits_air: torch.Tensor,
    hits_ground: torch.Tensor,
    crown_multiplier: torch.Tensor,
    crown_damage: torch.Tensor,
    crown_damage_valid: torch.Tensor,
    duration_ms: torch.Tensor,
    interval_ms: torch.Tensor,
    initial_delay_ms: torch.Tensor,
    max_ticks: torch.Tensor,
    damage_on_spawn: torch.Tensor,
) -> None:
    hits_air[card_id] = spell.hits_air
    hits_ground[card_id] = spell.hits_ground
    crown_multiplier[card_id] = spell.crown_tower_damage_multiplier
    if spell.crown_tower_damage is not None:
        crown_damage[card_id] = spell.crown_tower_damage
        crown_damage_valid[card_id] = True
    duration_ms[card_id] = round(spell.duration * 1_000)
    interval_ms[card_id] = round(spell.damage_tick_interval * 1_000)
    initial = spell.initial_damage_delay
    initial_delay_ms[card_id] = round(
        (0.0 if spell.damage_on_spawn else spell.damage_tick_interval) * 1_000
        if initial is None
        else initial * 1_000
    )
    max_ticks[card_id] = spell.max_damage_ticks
    damage_on_spawn[card_id] = spell.damage_on_spawn


def _direct_spell_reason(spell: Any) -> str | None:
    if bool(getattr(spell, "affects_hidden", False)):
        return "hidden-target direct spell semantics are not retained"
    return None


def _projectile_spell_reason(spell: Any) -> str | None:
    if spell.multiple_projectiles == 1 and spell.damage_waves != 1:
        return "single-projectile deferred damage waves are not retained"
    if spell.multiple_projectiles > 1 and (
        spell.stun_duration > 0
        or spell.slow_duration > 0
        or spell.knockback_distance > 0
    ):
        return "grouped projectile status/knockback payload is not retained"
    return None


def _spawn_projectile_reason(
    spell: Any,
    child_id: int,
    child_stats: Any,
    catalog_matches: bool,
) -> str | None:
    if child_id <= 0 or child_stats is None:
        return "spawn projectile character is absent from retained card catalog"
    if not catalog_matches:
        return "spawn projectile character is absent or inexact in shared card catalog"
    if spell.multiple_projectiles != 1 or spell.damage_waves != 1:
        return "spawn projectile multi-wave payload is not retained"
    if spell.stun_duration > 0 or spell.slow_duration > 0:
        return "spawn projectile status payload is not retained"
    return None


def _spawn_catalog_matches(
    runtime: TensorBattleRuntime, child_id: int, child_stats: Any
) -> bool:
    if child_id <= 0 or child_stats is None:
        return False
    catalog_id = int(runtime.card_catalog_index[child_id].item())
    if catalog_id <= 0:
        return False
    catalog = runtime.catalog
    expected = (
        float(child_stats.scaled_hitpoints or child_stats.hitpoints or 100),
        float(child_stats.scaled_damage or child_stats.damage or 0),
        tiles_to_logic_units(float(child_stats.range or 0)),
        tiles_to_logic_units(float(child_stats.sight_range or 0)),
        tiles_to_logic_units(float(child_stats.collision_radius or 0)),
        round(float(child_stats.speed or 0)),
        round(float(child_stats.hit_speed or 0)),
        round(float(child_stats.load_time or 0)),
        round(float(child_stats.deploy_time or 0)),
    )
    actual = (
        float(catalog.hitpoints[catalog_id].item()),
        float(catalog.damage[catalog_id].item()),
        int(catalog.range_units[catalog_id].item()),
        int(catalog.sight_range_units[catalog_id].item()),
        int(catalog.collision_radius_units[catalog_id].item()),
        int(catalog.speed_units_per_tick[catalog_id].item()),
        int(catalog.hit_speed_ms[catalog_id].item()),
        int(catalog.load_time_ms[catalog_id].item()),
        int(catalog.deploy_time_ms[catalog_id].item()),
    )
    return actual == expected


def _area_spell_reason(spell: Any) -> str | None:
    if spell.freeze_effect or spell.speed_multiplier != 1.0:
        return "continuous freeze/slow area is not retained"
    if spell.target_local_damage or spell.periodic_damage_buff_duration > 0:
        return "target-local periodic spell damage is not retained"
    if spell.effect_tick_interval > 0 and spell.effect_tick_interval < 0.05:
        return "sub-frame area effect interval is not retained"
    return None


def _combat_projectile_reason(projectile: dict[str, Any]) -> str | None:
    if projectile.get("spawnProjectileData"):
        return "impact child projectile is not retained"
    if projectile.get("projectileStartExtraRadius", 0):
        return "piercing/start collision projectile is not retained"
    return None


def _projectile_attack_callback_names(mechanics: Sequence[object]) -> tuple[str, ...]:
    """Return mechanics that alter attack launch, impact, or damage semantics.

    Parent lifecycle hooks such as periodic spawning and death payloads are
    composed by separate retained owners and must not make an otherwise
    ordinary serialized projectile unsupported.  Only actual attack-payload
    hook overrides belong to the projectile bridge support decision.
    """

    represented = {"CrownTowerScaling", "DamageRamp"}
    hooks = (
        "on_attack_start",
        "on_attack_committed",
        "on_attack_hit",
        "modify_outgoing_damage",
        "projectile_crown_tower_damage",
    )
    unsupported: list[str] = []
    for mechanic in mechanics:
        mechanic_type = type(mechanic)
        name = mechanic_type.__name__
        if name in represented:
            continue
        if any(
            getattr(mechanic_type, hook, None) is not getattr(BaseMechanic, hook)
            for hook in hooks
        ):
            unsupported.append(name)
    return tuple(unsupported)


def _projectile_crown_damage(
    definitions: dict[str, Any], name: str, damage: torch.Tensor
) -> float | None:
    for mechanic in definitions[name].mechanics:
        if (
            MECHANIC_OPCODE.get(type(mechanic).__name__)
            != MECHANIC_OPCODE["CrownTowerScaling"]
        ):
            continue
        explicit = getattr(mechanic, "crown_tower_damage", None)
        if explicit is not None:
            return float(explicit)
        multiplier = float(getattr(mechanic, "damage_multiplier", 1.0))
        base = max(0, round(float(damage.item())))
        percent = max(0, round(multiplier * 100))
        return float((base * percent + 99) // 100 if base and percent else 0)
    return None


def _catalog_blueprint(catalog: TensorObjectCatalog, index: int) -> ObjectBlueprint:
    return ObjectBlueprint(
        opcode=int(catalog.opcode[index].item()),
        player_id=int(catalog.player[index].item()),
        x_units=int(catalog.x_units[index].item()),
        y_units=int(catalog.y_units[index].item()),
        target_x_units=int(catalog.target_x_units[index].item()),
        target_y_units=int(catalog.target_y_units[index].item()),
        speed_units_per_tick=int(catalog.speed_units_per_tick[index].item()),
        launch_delay_ms=int(catalog.launch_delay_ms[index].item()),
        activation_delay_ms=int(catalog.activation_delay_ms[index].item()),
        duration_ms=int(catalog.duration_ms[index].item()),
        tick_interval_ms=int(catalog.tick_interval_ms[index].item()),
        initial_tick_ms=int(catalog.initial_tick_ms[index].item()),
        max_ticks=int(catalog.max_ticks[index].item()),
        amount=float(catalog.amount[index].item()),
        payload_id=int(catalog.payload_id[index].item()),
        payload_count=int(catalog.payload_count[index].item()),
        terminal_blueprint=int(catalog.terminal_blueprint[index].item()),
        inherit_terminal_position=bool(catalog.inherit_terminal_position[index].item()),
        inherit_player=bool(catalog.inherit_player[index].item()),
        feature_mask=int(catalog.feature_mask[index].item()),
    )


def _ensure_spawn_payload_cards_(
    runtime: TensorBattleRuntime,
) -> None:
    core_names = list(runtime.battle.card_names)
    missing = sorted(
        {
            str(spell.spawn_character)
            for name in core_names[1:]
            if isinstance((spell := SPELL_REGISTRY.get(name)), SpawnProjectileSpell)
            and str(spell.spawn_character) not in runtime.battle.card_to_id
        }
    )
    if not missing:
        return
    core_names.extend(missing)
    runtime.battle.card_names = tuple(core_names)
    runtime.battle.card_to_id = {
        name: index for index, name in enumerate(runtime.battle.card_names)
    }
    runtime.card_catalog_index = torch.cat(
        (
            runtime.card_catalog_index,
            torch.tensor(
                [runtime.catalog.name_to_id.get(name, -1) for name in missing],
                dtype=torch.int64,
                device=runtime.device,
            ),
        )
    )


@dataclass
class TensorResidentProjectileSpellBridge:
    catalog: TensorProjectileSpellCatalog
    blueprint_for_slot: torch.Tensor
    blueprint_stun_ms: torch.Tensor
    blueprint_slow_ms: torch.Tensor
    blueprint_slow_multiplier: torch.Tensor
    blueprint_slow_attack_multiplier: torch.Tensor
    blueprint_slow_spawn_multiplier: torch.Tensor
    blueprint_knockback_units: torch.Tensor
    blueprint_knockback_ignores_mass: torch.Tensor
    blueprint_tracks_target: torch.Tensor
    blueprint_actual_damage: torch.Tensor
    blueprint_damage_group_slot: torch.Tensor
    blueprint_card_id: torch.Tensor
    damage_group_seen: torch.Tensor
    stun_applied: torch.Tensor
    knockback_active: torch.Tensor
    knockback_entity_id: torch.Tensor
    knockback_target_units: torch.Tensor
    knockback_velocity_work: torch.Tensor
    spawn_target_distance_discount_sq_units: torch.Tensor
    king_x_units: torch.Tensor
    king_y_units: torch.Tensor
    rng_counter: torch.Tensor
    logic_sine: torch.Tensor
    lane_candidate_x: torch.Tensor
    lane_candidate_y: torch.Tensor
    lane_candidate_id: torch.Tensor
    max_projectiles_per_action: int

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        object_phase: TensorRuntimeObjectPhase,
        battles: Sequence[BattleState],
    ) -> TensorResidentProjectileSpellBridge:
        _ensure_spawn_payload_cards_(runtime)
        payloads = TensorProjectileSpellCatalog.compile(runtime, battles)
        old_catalog = object_phase.objects.catalog
        old_size = old_catalog.size
        placeholders = runtime.batch_size * object_phase.objects.max_objects
        blueprints = [
            _catalog_blueprint(old_catalog, index) for index in range(1, old_size)
        ] + [
            ObjectBlueprint(opcode=ObjectOpcode.PROJECTILE_LAUNCH)
            for _ in range(placeholders)
        ]
        expanded = TensorObjectCatalog.compile(blueprints, device=runtime.device)
        object_phase.objects.catalog = expanded

        def expand_catalog_plane(
            value: torch.Tensor, fill: float | bool
        ) -> torch.Tensor:
            result = torch.full(
                (expanded.size,), fill, dtype=value.dtype, device=runtime.device
            )
            result[: value.shape[0]] = value
            return result

        object_phase.blueprint_kind = expand_catalog_plane(
            object_phase.blueprint_kind, int(RuntimeObjectKind.UNKNOWN)
        )
        object_phase.blueprint_payload_known = expand_catalog_plane(
            object_phase.blueprint_payload_known, False
        )
        object_phase.blueprint_primary_target_id = expand_catalog_plane(
            object_phase.blueprint_primary_target_id, 0
        )
        object_phase.blueprint_radius_units = expand_catalog_plane(
            object_phase.blueprint_radius_units, 0
        )
        object_phase.blueprint_hits_air = expand_catalog_plane(
            object_phase.blueprint_hits_air, True
        )
        object_phase.blueprint_hits_ground = expand_catalog_plane(
            object_phase.blueprint_hits_ground, True
        )
        object_phase.blueprint_ignore_buildings = expand_catalog_plane(
            object_phase.blueprint_ignore_buildings, False
        )
        object_phase.blueprint_crown_multiplier = expand_catalog_plane(
            object_phase.blueprint_crown_multiplier, 1.0
        )
        object_phase.blueprint_crown_damage = expand_catalog_plane(
            object_phase.blueprint_crown_damage, 0.0
        )
        object_phase.blueprint_crown_damage_valid = expand_catalog_plane(
            object_phase.blueprint_crown_damage_valid, False
        )
        object_phase.blueprint_building_multiplier = expand_catalog_plane(
            object_phase.blueprint_building_multiplier, 1.0
        )
        object_phase.blueprint_building_damage = expand_catalog_plane(
            object_phase.blueprint_building_damage, 0.0
        )
        object_phase.blueprint_building_damage_valid = expand_catalog_plane(
            object_phase.blueprint_building_damage_valid, False
        )
        blueprint = torch.arange(
            old_size,
            old_size + placeholders,
            dtype=torch.int64,
            device=runtime.device,
        ).reshape(runtime.batch_size, object_phase.objects.max_objects)
        king_x = torch.zeros(
            (runtime.batch_size, 2), dtype=torch.int32, device=runtime.device
        )
        king_y = torch.zeros_like(king_x)
        for batch_index, battle in enumerate(battles):
            king_x[batch_index] = torch.tensor(
                [
                    tiles_to_logic_units(battle.arena.BLUE_KING_TOWER.x),
                    tiles_to_logic_units(battle.arena.RED_KING_TOWER.x),
                ],
                dtype=torch.int32,
                device=runtime.device,
            )
            king_y[batch_index] = torch.tensor(
                [
                    tiles_to_logic_units(battle.arena.BLUE_KING_TOWER.y),
                    tiles_to_logic_units(battle.arena.RED_KING_TOWER.y),
                ],
                dtype=torch.int32,
                device=runtime.device,
            )
        return cls(
            catalog=payloads,
            blueprint_for_slot=blueprint,
            blueprint_stun_ms=torch.zeros(
                expanded.size, dtype=torch.int32, device=runtime.device
            ),
            blueprint_slow_ms=torch.zeros(
                expanded.size, dtype=torch.int32, device=runtime.device
            ),
            blueprint_slow_multiplier=torch.ones(
                expanded.size, dtype=torch.float64, device=runtime.device
            ),
            blueprint_slow_attack_multiplier=torch.ones(
                expanded.size, dtype=torch.float64, device=runtime.device
            ),
            blueprint_slow_spawn_multiplier=torch.ones(
                expanded.size, dtype=torch.float64, device=runtime.device
            ),
            blueprint_knockback_units=torch.zeros(
                expanded.size, dtype=torch.int32, device=runtime.device
            ),
            blueprint_knockback_ignores_mass=torch.zeros(
                expanded.size, dtype=torch.bool, device=runtime.device
            ),
            blueprint_tracks_target=torch.zeros(
                expanded.size, dtype=torch.bool, device=runtime.device
            ),
            blueprint_actual_damage=torch.zeros(
                expanded.size, dtype=torch.float64, device=runtime.device
            ),
            blueprint_damage_group_slot=torch.zeros(
                expanded.size, dtype=torch.int16, device=runtime.device
            ),
            blueprint_card_id=torch.zeros(
                expanded.size, dtype=torch.int64, device=runtime.device
            ),
            damage_group_seen=torch.zeros(
                (
                    runtime.batch_size,
                    object_phase.objects.max_objects,
                    runtime.max_entities,
                ),
                dtype=torch.bool,
                device=runtime.device,
            ),
            stun_applied=torch.zeros(
                (runtime.batch_size, runtime.max_entities),
                dtype=torch.bool,
                device=runtime.device,
            ),
            knockback_active=torch.zeros(
                (runtime.batch_size, runtime.max_entities),
                dtype=torch.bool,
                device=runtime.device,
            ),
            knockback_entity_id=torch.zeros(
                (runtime.batch_size, runtime.max_entities),
                dtype=torch.int64,
                device=runtime.device,
            ),
            knockback_target_units=torch.zeros(
                (runtime.batch_size, runtime.max_entities, 2),
                dtype=torch.int32,
                device=runtime.device,
            ),
            knockback_velocity_work=torch.zeros(
                (runtime.batch_size, runtime.max_entities),
                dtype=torch.int32,
                device=runtime.device,
            ),
            spawn_target_distance_discount_sq_units=torch.zeros(
                (runtime.batch_size, runtime.max_entities),
                dtype=torch.int64,
                device=runtime.device,
            ),
            king_x_units=king_x,
            king_y_units=king_y,
            rng_counter=torch.zeros(
                runtime.batch_size, dtype=torch.int64, device=runtime.device
            ),
            logic_sine=torch.tensor(
                tuple(
                    (_SIN_TABLE[angle] if angle <= 90 else _SIN_TABLE[180 - angle])
                    if angle < 180
                    else -(
                        _SIN_TABLE[angle - 180]
                        if angle - 180 <= 90
                        else _SIN_TABLE[360 - angle]
                    )
                    for angle in range(360)
                ),
                dtype=torch.int64,
                device=runtime.device,
            ),
            lane_candidate_x=torch.arange(
                STANDARD_PATH_WIDTH, device=runtime.device
            ).repeat_interleave(STANDARD_PATH_HEIGHT),
            lane_candidate_y=torch.arange(
                STANDARD_PATH_HEIGHT, device=runtime.device
            ).repeat(STANDARD_PATH_WIDTH),
            lane_candidate_id=torch.tensor(
                [
                    ord(STANDARD_PATH_ROWS[y][x]) - ord("0")
                    for x in range(STANDARD_PATH_WIDTH)
                    for y in range(STANDARD_PATH_HEIGHT)
                ],
                dtype=torch.int64,
                device=runtime.device,
            ),
            max_projectiles_per_action=max(
                1,
                max(
                    int(spell.multiple_projectiles) * max(1, int(spell.damage_waves))
                    for spell in SPELL_REGISTRY.values()
                    if isinstance(spell, ProjectileSpell)
                    and not isinstance(spell, SpawnProjectileSpell)
                ),
            ),
        )

    def materialize_combat_launches_(
        self,
        runtime: TensorBattleRuntime,
        object_phase: TensorRuntimeObjectPhase,
        combat: StationaryCombatState,
        result: CombatStepResult,
    ) -> torch.Tensor:
        launch = result.projectile_launched & combat.present & combat.alive
        identity_match = (
            combat.entity_id[:, :, None] == runtime.battle.entity_id[:, None, :]
        ) & runtime.entity_pool.active[:, None, :]
        identity_found = identity_match.any(dim=2)
        identity_supported = ~(launch & ~identity_found).any(dim=1)
        launch &= identity_supported[:, None]
        runtime_slot = identity_match.to(torch.int64).argmax(dim=2)
        card_ids = torch.gather(runtime.battle.entity_card, 1, runtime_slot)
        materialized = self._materialize_(
            runtime,
            object_phase,
            card_ids=card_ids,
            source_ids=combat.entity_id,
            owners=combat.owner,
            source_x=combat.x_units,
            source_y=combat.y_units,
            target_slots=combat.target_slot,
            target_x=torch.gather(
                combat.x_units,
                1,
                combat.target_slot.clamp(0, combat.max_entities - 1),
            ),
            target_y=torch.gather(
                combat.y_units,
                1,
                combat.target_slot.clamp(0, combat.max_entities - 1),
            ),
            damage=combat.damage * combat.outgoing_damage_multiplier,
            launch=launch,
            spell=False,
        )
        return materialized & identity_supported

    def materialize_spell_actions_(
        self,
        runtime: TensorBattleRuntime,
        object_phase: TensorRuntimeObjectPhase,
        *,
        card_ids: torch.Tensor,
        player_ids: torch.Tensor,
        target_x_units: torch.Tensor,
        target_y_units: torch.Tensor,
        valid: torch.Tensor,
    ) -> torch.Tensor:
        batch = runtime.batch_size
        if card_ids.shape != (batch,) or player_ids.shape != (batch,):
            raise ValueError("spell action tensors must have shape [batch]")
        source_x = self.king_x_units[
            torch.arange(batch, device=runtime.device), player_ids
        ][:, None]
        source_y = self.king_y_units[
            torch.arange(batch, device=runtime.device), player_ids
        ][:, None]
        payload_kind = self.catalog.kind[card_ids]
        direct = valid & (payload_kind == BridgePayloadKind.DIRECT_SPELL)
        direct_supported = self._apply_direct_spells_(
            runtime,
            object_phase,
            card_ids,
            player_ids,
            target_x_units,
            target_y_units,
            direct,
        )
        object_action = valid & ~direct
        safe_cards = card_ids.clamp_min(0)
        projectile = payload_kind == BridgePayloadKind.PROJECTILE_SPELL
        projectile_count = torch.where(
            projectile,
            self.catalog.multiple_projectiles[safe_cards].to(torch.int64),
            torch.ones_like(safe_cards),
        )
        wave_count = torch.where(
            projectile & (projectile_count > 1),
            self.catalog.damage_waves[safe_cards].to(torch.int64),
            torch.ones_like(safe_cards),
        )
        total = projectile_count * wave_count
        grouped = projectile & (projectile_count > 1)
        spawn_payload = payload_kind == BridgePayloadKind.SPAWN_PROJECTILE
        reserved_spawns = torch.where(
            spawn_payload,
            self.catalog.spawn_count[safe_cards].to(torch.int64),
            torch.zeros_like(total),
        )
        free_objects = (~object_phase.objects.allocated).sum(dim=1)
        free_entities = (~runtime.entity_pool.active).sum(dim=1)
        possible_targets = (
            runtime.entity_pool.active
            & runtime.battle.entity_active
            & (runtime.battle.entity_kind != 2)
            & (runtime.battle.entity_kind != 3)
        ).sum(dim=1)
        worst_events = total * (2 + 2 * possible_targets) + reserved_spawns
        remaining_events = runtime.events.capacity - runtime.events.count.to(
            torch.int64
        )
        preflight = self.catalog.supported[safe_cards]
        preflight &= total <= free_objects
        preflight &= total + reserved_spawns <= free_entities
        preflight &= ~(grouped & object_phase.objects.allocated.any(dim=1))
        preflight &= ~((grouped | spawn_payload) & (worst_events > remaining_events))
        admitted = object_action & preflight
        width = self.max_projectiles_per_action
        ordinal = torch.arange(width, device=runtime.device, dtype=torch.int64)[None, :]
        launch = admitted[:, None] & (ordinal < total[:, None])
        member = torch.remainder(ordinal, projectile_count[:, None].clamp_min(1))
        wave = torch.div(
            ordinal,
            projectile_count[:, None].clamp_min(1),
            rounding_mode="floor",
        )
        target_x = target_x_units[:, None].expand(batch, width).clone()
        target_y = target_y_units[:, None].expand(batch, width).clone()
        grouped_launch = launch & grouped[:, None]
        native_launch = launch & projectile[:, None] & ~grouped[:, None]
        radius = self.catalog.spread_radius_units[safe_cards].to(torch.int64)
        projectile_radius = self.catalog.radius_units[safe_cards].to(torch.int64)
        jitter = _trunc_div(projectile_radius * 60, torch.full_like(radius, 100))
        ring = (radius - jitter).clamp_min(0)
        clamp = _trunc_div(radius * 90, torch.full_like(radius, 100))
        grouped_step = _trunc_div(
            torch.full_like(projectile_count, 360),
            (projectile_count - 1).clamp_min(1),
        )
        grouped_angle = grouped_step[:, None] * (member - 1).clamp_min(0)
        base_x, base_y = _rotate_logic_tensor(
            ring[:, None].expand(batch, width),
            torch.zeros((batch, width), dtype=torch.int64, device=runtime.device),
            grouped_angle,
            self.logic_sine,
        )
        base_x = torch.where(member == 0, 0, base_x)
        base_y = torch.where(member == 0, 0, base_y)
        jitter_angle = torch.zeros(
            (batch, width), dtype=torch.int64, device=runtime.device
        )
        for launch_ordinal in range(width):
            active = grouped_launch[:, launch_ordinal]
            jitter_angle[:, launch_ordinal] = runtime.battle.rng.randrange(359, active)
        jitter_x, jitter_y = _rotate_logic_tensor(
            torch.zeros((batch, width), dtype=torch.int64, device=runtime.device),
            jitter[:, None].expand(batch, width),
            jitter_angle,
            self.logic_sine,
        )
        offset_x = base_x + jitter_x
        offset_y = base_y + jitter_y
        distance_sq = offset_x.square() + offset_y.square()
        clamp_needed = (
            grouped_launch
            & (clamp[:, None] > 0)
            & (distance_sq > clamp[:, None].square())
        )
        distance = _integer_sqrt(distance_sq).clamp_min(1)
        offset_x = torch.where(
            clamp_needed,
            _trunc_div(offset_x * clamp[:, None], distance),
            offset_x,
        )
        offset_y = torch.where(
            clamp_needed,
            _trunc_div(offset_y * clamp[:, None], distance),
            offset_y,
        )

        inner = radius >> 2
        span = (radius - inner).clamp_min(0)
        radial = torch.zeros((batch, width), dtype=torch.int64, device=runtime.device)
        for launch_ordinal in range(width):
            active = (
                native_launch[:, launch_ordinal]
                & (member[:, launch_ordinal] > 0)
                & (span > 0)
            )
            radial[:, launch_ordinal] = (
                runtime.battle.rng.randrange(span.clamp_min(1), active) + inner
            )
        native_step = _trunc_div(
            torch.full_like(projectile_count, 360), projectile_count.clamp_min(1)
        )
        native_x, native_y = _rotate_logic_tensor(
            radial,
            torch.zeros_like(radial),
            native_step[:, None] * member,
            self.logic_sine,
        )
        offset_x = torch.where(native_launch, native_x, offset_x)
        offset_y = torch.where(native_launch, native_y, offset_y)
        patterned = grouped_launch | native_launch
        offset_x = torch.where(patterned, offset_x, 0)
        offset_y = torch.where(patterned, offset_y, 0)
        reflect = torch.where(player_ids[:, None] == 0, 1, -1)
        target_x += (offset_x * reflect).to(torch.int32)
        target_y += (offset_y * reflect).to(torch.int32)
        group_source = torch.where(
            grouped[:, None],
            wave * projectile_count[:, None],
            torch.full_like(ordinal, -1),
        )
        launch_delay = wave * self.catalog.damage_wave_interval_ms[safe_cards][:, None]
        actual_damage = self.catalog.damage[safe_cards][:, None].expand(batch, width)
        materialized_damage = torch.where(
            grouped[:, None], torch.zeros_like(actual_damage), actual_damage
        )
        object_supported = self._materialize_(
            runtime,
            object_phase,
            card_ids=card_ids[:, None].expand(batch, width),
            source_ids=ordinal.expand(batch, width),
            owners=player_ids[:, None].expand(batch, width),
            source_x=source_x.expand(batch, width),
            source_y=source_y.expand(batch, width),
            target_slots=torch.full(
                (batch, width), -1, dtype=torch.int64, device=runtime.device
            ),
            target_x=target_x,
            target_y=target_y,
            damage=materialized_damage,
            launch=launch,
            spell=True,
            launch_delay_ms=launch_delay,
            damage_group_source=group_source,
            actual_damage=actual_damage,
        )
        rejected = object_action & ~preflight
        return direct_supported & object_supported & ~rejected

    def _apply_direct_spells_(
        self,
        runtime: TensorBattleRuntime,
        phase: TensorRuntimeObjectPhase,
        card_ids: torch.Tensor,
        player_ids: torch.Tensor,
        target_x: torch.Tensor,
        target_y: torch.Tensor,
        valid: torch.Tensor,
    ) -> torch.Tensor:
        supported = ~(valid & ~self.catalog.supported[card_ids])
        radius = self.catalog.radius_units[card_ids].to(torch.int64)[:, None]
        x = runtime.battle.entity_x_units.to(torch.int64)
        y = runtime.battle.entity_y_units.to(torch.int64)
        object_radius = phase.target_collision_radius_units.to(torch.int64)
        dx = x - target_x.to(torch.int64)[:, None]
        dy = y - target_y.to(torch.int64)[:, None]
        circular = dx * dx + dy * dy < (radius + object_radius).square()
        closest_x = torch.minimum(
            x + object_radius,
            torch.maximum(x - object_radius, target_x.to(torch.int64)[:, None]),
        )
        closest_y = torch.minimum(
            y + object_radius,
            torch.maximum(y - object_radius, target_y.to(torch.int64)[:, None]),
        )
        square_dx = closest_x - target_x.to(torch.int64)[:, None]
        square_dy = closest_y - target_y.to(torch.int64)[:, None]
        square = square_dx * square_dx + square_dy * square_dy < radius.square()
        targets = torch.where(phase.target_building, square, circular)
        targets &= valid[:, None] & supported[:, None]
        targets &= runtime.entity_pool.active & runtime.battle.entity_active
        targets &= runtime.battle.entity_player != player_ids[:, None]
        targets &= (runtime.battle.entity_kind != 2) & (runtime.battle.entity_kind != 3)
        targets &= torch.where(
            phase.target_airborne,
            self.catalog.hits_air[card_ids][:, None],
            self.catalog.hits_ground[card_ids][:, None],
        )
        targets &= ~(
            self.catalog.ignore_buildings[card_ids][:, None] & phase.target_building
        )
        unsupported_targets = targets & ~phase.target_payload_supported
        supported &= ~unsupported_targets.any(dim=1)
        requests_slow = self.catalog.slow_ms[card_ids] > 0
        slow_capacity = (~runtime.status.slow_active).any(dim=2)
        supported &= ~(requests_slow & (targets & ~slow_capacity).any(dim=1))
        targets &= supported[:, None]
        order = torch.argsort(
            torch.where(
                targets,
                runtime.battle.entity_id,
                torch.full_like(runtime.battle.entity_id, torch.iinfo(torch.int64).max),
            ),
            dim=1,
            stable=True,
        )
        ordered_valid = torch.gather(targets, 1, order)
        ordered_ids = torch.gather(runtime.battle.entity_id, 1, order)
        ordered_x = torch.gather(runtime.battle.entity_x_units, 1, order)
        ordered_y = torch.gather(runtime.battle.entity_y_units, 1, order)
        amount = self.catalog.damage[card_ids][:, None].expand_as(targets)
        crown = self.catalog.crown_damage[card_ids]
        native = _native_percent(
            self.catalog.damage[card_ids], self.catalog.crown_multiplier[card_ids]
        )
        crown_amount = torch.where(
            self.catalog.crown_damage_valid[card_ids], crown, native
        )
        amount = torch.where(phase.target_crown, crown_amount[:, None], amount)
        before_alive = runtime.battle.entity_active.clone()
        before_hp = runtime.battle.entity_hp.clone()
        candidate_hp = torch.where(
            targets,
            (before_hp - amount).clamp_min(0),
            before_hp,
        )
        applied_amount = torch.where(targets, before_hp - candidate_hp, 0.0)
        ordered_amount = torch.gather(applied_amount, 1, order)
        died = targets & before_alive & (candidate_hp <= 0)
        ordered_died = torch.gather(died, 1, order) & ordered_valid
        pair_valid = torch.stack((ordered_valid, ordered_died), dim=2).flatten(1)
        stun_seconds = self.catalog.stun_ms[card_ids].to(torch.float64) / 1_000
        additions = pair_valid.sum(dim=1, dtype=torch.int64)
        overflow = supported & (
            runtime.events.count.to(torch.int64) + additions > runtime.events.capacity
        )
        supported &= ~overflow
        targets &= supported[:, None]
        died &= supported[:, None]
        ordered_valid &= supported[:, None]
        ordered_died &= supported[:, None]
        pair_valid = torch.stack((ordered_valid, ordered_died), dim=2).flatten(1)
        positive_damage = targets & (amount > 0.0)
        runtime.battle.entity_hp_integer_kind &= ~positive_damage
        runtime.battle.entity_hp.copy_(
            torch.where(targets, candidate_hp, runtime.battle.entity_hp)
        )
        runtime.battle.entity_active &= ~died
        runtime.phases.death_pending |= died
        damage_opcode = torch.full_like(ordered_ids, RuntimeEventOpcode.DAMAGE)
        death_opcode = torch.full_like(ordered_ids, RuntimeEventOpcode.DEATH)
        ordered_payload = card_ids[:, None].expand_as(ordered_ids)
        runtime.events.append(
            phase=TickPhase.COMMANDS,
            opcode=torch.stack((damage_opcode, death_opcode), dim=2).flatten(1),
            valid=pair_valid,
            source_id=0,
            target_id=torch.stack((ordered_ids, ordered_ids), dim=2).flatten(1),
            x_units=torch.stack((ordered_x, ordered_x), dim=2).flatten(1),
            y_units=torch.stack((ordered_y, ordered_y), dim=2).flatten(1),
            amount=torch.stack(
                (ordered_amount, torch.zeros_like(ordered_amount)), dim=2
            ).flatten(1),
            payload=torch.stack((ordered_payload, ordered_payload), dim=2).flatten(1),
        )
        survivors = targets & runtime.battle.entity_active
        self.stun_applied |= survivors & (stun_seconds[:, None] > 0)
        runtime.status.stun_timer.copy_(
            torch.where(
                survivors & (stun_seconds[:, None] > 0),
                torch.maximum(runtime.status.stun_timer, stun_seconds[:, None]),
                runtime.status.stun_timer,
            )
        )
        slow_duration = self.catalog.slow_ms[card_ids].to(torch.float64) / 1_000
        slow_mask = survivors & (slow_duration[:, None] > 0)
        runtime.status.apply_slow(
            slow_duration[:, None],
            self.catalog.slow_multiplier[card_ids][:, None],
            attack_speed_multiplier=self.catalog.slow_attack_multiplier[card_ids][
                :, None
            ],
            spawn_speed_multiplier=self.catalog.slow_spawn_multiplier[card_ids][
                :, None
            ],
            mask=slow_mask,
        )
        self._install_knockback_(
            runtime,
            target_mask=survivors,
            center_x=target_x,
            center_y=target_y,
            fallback_x=torch.zeros_like(target_x),
            fallback_y=torch.zeros_like(target_y),
            distance_units=self.catalog.knockback_units[card_ids],
            ignores_mass=self.catalog.knockback_ignores_mass[card_ids],
        )
        runtime.mark_dirty(valid & supported, phase=TickPhase.COMMANDS)
        return supported

    def _install_knockback_(
        self,
        runtime: TensorBattleRuntime,
        *,
        target_mask: torch.Tensor,
        center_x: torch.Tensor,
        center_y: torch.Tensor,
        fallback_x: torch.Tensor,
        fallback_y: torch.Tensor,
        distance_units: torch.Tensor,
        ignores_mass: torch.Tensor,
    ) -> None:
        def entity_plane(value: torch.Tensor) -> torch.Tensor:
            return value[:, None] if value.ndim == 1 else value

        retained_identity = (
            self.knockback_entity_id == runtime.battle.entity_id
        ) & runtime.entity_pool.active
        stale = self.knockback_active & ~retained_identity
        self.knockback_active &= retained_identity
        self.knockback_entity_id.masked_fill_(stale, 0)
        self.knockback_velocity_work.masked_fill_(stale, 0)
        center_x_plane = entity_plane(center_x).to(torch.int64)
        center_y_plane = entity_plane(center_y).to(torch.int64)
        fallback_x_plane = entity_plane(fallback_x).to(torch.int64)
        fallback_y_plane = entity_plane(fallback_y).to(torch.int64)
        distance_plane = entity_plane(distance_units).to(torch.int64)
        ignores_plane = entity_plane(ignores_mass)
        eligible = (
            target_mask
            & runtime.battle.entity_active
            & (runtime.battle.entity_kind != 1)
            & ~self.knockback_active
            & (
                ignores_plane
                | ~self.catalog.card_knockback_immune[
                    runtime.battle.entity_card.clamp_min(0)
                ]
            )
            & (distance_plane > 0)
        )
        dx = runtime.battle.entity_x_units.to(torch.int64) - center_x_plane
        dy = runtime.battle.entity_y_units.to(torch.int64) - center_y_plane
        exact_center = (dx == 0) & (dy == 0)
        # Scalar radial knockback promotes the exact-center projectile fallback
        # from arena tiles to millionths before normalization.  Keeping that
        # extra three decimal digits matters for diagonal integer square roots;
        # normalizing the ordinary logic-unit vector first can overshoot one
        # component by several native units.
        dx = torch.where(exact_center, fallback_x_plane * 1_000, dx)
        dy = torch.where(exact_center, fallback_y_plane * 1_000, dy)
        still_center = (dx == 0) & (dy == 0)
        owner_direction = torch.where(
            runtime.battle.entity_player == 0,
            torch.ones_like(dx),
            -torch.ones_like(dx),
        )
        dx = torch.where(still_center, owner_direction, dx)
        distance = distance_plane.clamp(0, 10_000)
        norm = _integer_sqrt(dx * dx + dy * dy).clamp_min(1)
        move_x = _trunc_div(dx * distance, norm).to(torch.int32)
        move_y = _trunc_div(dy * distance, norm).to(torch.int32)
        self.knockback_target_units[:, :, 0] = torch.where(
            eligible,
            runtime.battle.entity_x_units + move_x,
            self.knockback_target_units[:, :, 0],
        )
        self.knockback_target_units[:, :, 1] = torch.where(
            eligible,
            runtime.battle.entity_y_units + move_y,
            self.knockback_target_units[:, :, 1],
        )
        velocity = torch.zeros_like(distance)
        work = torch.zeros_like(distance)
        for _ in range(28):
            advancing = work < distance
            velocity = torch.where(advancing, velocity + 25, velocity)
            work = torch.where(advancing, work + velocity, work)
        self.knockback_velocity_work.copy_(
            torch.where(
                eligible,
                velocity.expand_as(self.knockback_velocity_work).to(torch.int32),
                self.knockback_velocity_work,
            )
        )
        self.knockback_entity_id.copy_(
            torch.where(
                eligible,
                runtime.battle.entity_id,
                self.knockback_entity_id,
            )
        )
        self.knockback_active |= eligible

    def _materialize_(
        self,
        runtime: TensorBattleRuntime,
        object_phase: TensorRuntimeObjectPhase,
        *,
        card_ids: torch.Tensor,
        source_ids: torch.Tensor,
        owners: torch.Tensor,
        source_x: torch.Tensor,
        source_y: torch.Tensor,
        target_slots: torch.Tensor,
        target_x: torch.Tensor,
        target_y: torch.Tensor,
        damage: torch.Tensor,
        launch: torch.Tensor,
        spell: bool,
        payload_kind: torch.Tensor | None = None,
        launch_delay_ms: torch.Tensor | None = None,
        damage_group_source: torch.Tensor | None = None,
        actual_damage: torch.Tensor | None = None,
    ) -> torch.Tensor:
        safe_cards = card_ids.clamp_min(0)
        supported_launch = self.catalog.supported[safe_cards]
        valid_target = (
            torch.ones_like(launch)
            if spell
            else (target_slots >= 0) & (target_slots < runtime.max_entities)
        )
        row_supported = ~(launch & (~supported_launch | ~valid_target)).any(dim=1)
        slow_launches = (launch & (self.catalog.slow_ms[safe_cards] > 0)).sum(dim=1)
        existing_blueprints = object_phase.objects.blueprint_id.to(
            torch.int64
        ).clamp_min(0)
        existing_slow = (
            object_phase.objects.allocated
            & (self.blueprint_slow_ms[existing_blueprints] > 0)
        ).any(dim=1)
        row_supported &= (slow_launches <= 1) & ~(existing_slow & (slow_launches > 0))
        status_capacity = (~runtime.status.slow_active).any(dim=2)
        possible_targets = runtime.entity_pool.active & (
            (runtime.battle.entity_kind == 0) | (runtime.battle.entity_kind == 1)
        )
        row_supported &= ~(
            (slow_launches > 0) & (possible_targets & ~status_capacity).any(dim=1)
        )
        counts = (launch & row_supported[:, None]).sum(dim=1, dtype=torch.int64)
        free_objects = (~object_phase.objects.allocated).sum(dim=1)
        free_entities = (~runtime.entity_pool.active).sum(dim=1)
        row_supported &= (counts <= free_objects) & (counts <= free_entities)
        row_supported &= (
            runtime.events.count.to(torch.int64) + counts <= runtime.events.capacity
        )
        counts = torch.where(row_supported, counts, 0)
        object_keys = torch.where(
            ~object_phase.objects.allocated,
            torch.arange(object_phase.objects.max_objects, device=runtime.device)[
                None, :
            ],
            object_phase.objects.max_objects,
        )
        free_object_slots = torch.sort(object_keys, dim=1).values
        allocation = runtime.entity_pool.allocate(counts)
        launch_keys = torch.where(
            launch & row_supported[:, None],
            source_ids,
            torch.full_like(source_ids, torch.iinfo(torch.int64).max),
        )
        launch_order = torch.argsort(launch_keys, dim=1, stable=True)
        ordinal = torch.arange(allocation.valid.shape[1], device=runtime.device)[
            None, :
        ]
        install = allocation.valid & (ordinal < counts[:, None])
        rows, launch_ordinal = torch.where(install)
        source_slot = launch_order[rows, launch_ordinal]
        object_slot = free_object_slots[rows, launch_ordinal]
        entity_slot = allocation.slots[rows, launch_ordinal]
        entity_id = allocation.entity_ids[rows, launch_ordinal]
        cards = safe_cards[rows, source_slot]
        kind = self.catalog.kind[cards] if payload_kind is None else payload_kind[rows]
        blueprint = self.blueprint_for_slot[rows, object_slot]
        start_x = source_x[rows, source_slot]
        start_y = source_y[rows, source_slot]
        end_x = target_x[rows, source_slot]
        end_y = target_y[rows, source_slot]
        if not spell:
            start_x, start_y = _muzzle_position(
                start_x,
                start_y,
                end_x,
                end_y,
                self.catalog.projectile_start_radius_units[cards],
                self.catalog.projectile_y_offset_units[cards],
                owners[rows, source_slot],
            )
        is_area = (kind == BridgePayloadKind.DIRECT_SPELL) | (
            kind == BridgePayloadKind.AREA_SPELL
        )
        delay = (
            torch.zeros_like(cards)
            if launch_delay_ms is None
            else launch_delay_ms[rows, source_slot]
        )
        group_slot = torch.zeros_like(cards)
        if damage_group_source is not None:
            group_source_slot = damage_group_source[rows, source_slot]
            grouped = group_source_slot >= 0
            group_object_slot = free_object_slots[rows, group_source_slot.clamp_min(0)]
            group_slot = torch.where(grouped, group_object_slot + 1, 0)
            group_rows = rows[grouped]
            group_slots = group_slot[grouped] - 1
            self.damage_group_seen[group_rows, group_slots] = False
        resolved_actual_damage = (
            damage[rows, source_slot]
            if actual_damage is None
            else actual_damage[rows, source_slot]
        )
        public_cards = torch.zeros_like(cards) if spell else cards
        self._install_object(
            runtime,
            object_phase,
            rows,
            object_slot,
            entity_slot,
            entity_id,
            blueprint,
            cards,
            public_cards,
            owners[rows, source_slot],
            start_x,
            start_y,
            end_x,
            end_y,
            damage[rows, source_slot],
            target_slots[rows, source_slot],
            is_area,
            delay,
            group_slot,
            resolved_actual_damage,
        )
        spawn_source = torch.zeros_like(allocation.entity_ids)
        spawn_target = torch.zeros_like(allocation.entity_ids)
        spawn_x = torch.zeros_like(allocation.slots, dtype=torch.int32)
        spawn_y = torch.zeros_like(allocation.slots, dtype=torch.int32)
        spawn_payload = torch.zeros_like(allocation.entity_ids)
        spawn_opcode = torch.full_like(allocation.entity_ids, RuntimeEventOpcode.SPAWN)
        if spell:
            serialized_projectile = (
                kind == int(BridgePayloadKind.PROJECTILE_SPELL)
            ) | (kind == int(BridgePayloadKind.SPAWN_PROJECTILE))
            spawn_source[rows, launch_ordinal] = torch.where(
                serialized_projectile, 0, entity_id
            )
            spawn_target[rows, launch_ordinal] = torch.where(
                serialized_projectile, entity_id, 0
            )
            spawn_x[rows, launch_ordinal] = torch.where(
                serialized_projectile, start_x, 0
            ).to(torch.int32)
            spawn_y[rows, launch_ordinal] = torch.where(
                serialized_projectile, start_y, 0
            ).to(torch.int32)
            spawn_payload[rows, launch_ordinal] = torch.where(
                serialized_projectile, cards, public_cards
            )
            spawn_opcode[rows, launch_ordinal] = torch.where(
                serialized_projectile,
                int(RuntimeEventOpcode.PROJECTILE),
                int(RuntimeEventOpcode.SPAWN),
            )
        else:
            spawn_source[rows, launch_ordinal] = source_ids[rows, source_slot]
            spawn_target[rows, launch_ordinal] = entity_id
            spawn_x[rows, launch_ordinal] = start_x.to(torch.int32)
            spawn_y[rows, launch_ordinal] = start_y.to(torch.int32)
            spawn_payload[rows, launch_ordinal] = public_cards
        runtime.events.append(
            phase=TickPhase.COMMANDS if spell else TickPhase.COMBAT,
            opcode=(spawn_opcode if spell else RuntimeEventOpcode.PROJECTILE),
            valid=install,
            source_id=spawn_source,
            target_id=spawn_target,
            x_units=spawn_x,
            y_units=spawn_y,
            payload=spawn_payload,
        )
        object_phase.objects.next_object_id.copy_(runtime.entity_pool.next_entity_id)
        return row_supported

    def _install_object(
        self,
        runtime: TensorBattleRuntime,
        phase: TensorRuntimeObjectPhase,
        rows: torch.Tensor,
        object_slots: torch.Tensor,
        entity_slots: torch.Tensor,
        entity_ids: torch.Tensor,
        blueprints: torch.Tensor,
        cards: torch.Tensor,
        public_cards: torch.Tensor,
        owners: torch.Tensor,
        start_x: torch.Tensor,
        start_y: torch.Tensor,
        end_x: torch.Tensor,
        end_y: torch.Tensor,
        damage: torch.Tensor,
        target_slots: torch.Tensor,
        is_area: torch.Tensor,
        launch_delay_ms: torch.Tensor,
        damage_group_slot: torch.Tensor,
        actual_damage: torch.Tensor,
    ) -> None:
        state = phase.objects
        state.allocated[rows, object_slots] = True
        state.active[rows, object_slots] = True
        state.object_id[rows, object_slots] = entity_ids
        state.blueprint_id[rows, object_slots] = blueprints.to(torch.int32)
        state.opcode[rows, object_slots] = torch.where(
            is_area,
            torch.full_like(blueprints, ObjectOpcode.PERIODIC_AREA),
            torch.full_like(blueprints, ObjectOpcode.PROJECTILE_LAUNCH),
        ).to(torch.int16)
        state.player[rows, object_slots] = owners.to(torch.int8)
        state.x_units[rows, object_slots] = torch.where(is_area, end_x, start_x).to(
            torch.int32
        )
        state.y_units[rows, object_slots] = torch.where(is_area, end_y, start_y).to(
            torch.int32
        )
        state.target_x_units[rows, object_slots] = end_x.to(torch.int32)
        state.target_y_units[rows, object_slots] = end_y.to(torch.int32)
        state.speed_units_per_tick[rows, object_slots] = torch.where(
            is_area, 0, self.catalog.projectile_speed_units[cards]
        )
        state.launch_delay_ms[rows, object_slots] = launch_delay_ms.to(torch.int32)
        state.age_ms[rows, object_slots] = 0
        state.duration_ms[rows, object_slots] = torch.where(
            is_area,
            torch.where(
                self.catalog.kind[cards] == BridgePayloadKind.DIRECT_SPELL,
                torch.ones_like(cards),
                self.catalog.duration_ms[cards],
            ),
            0,
        ).to(torch.int32)
        state.tick_interval_ms[rows, object_slots] = torch.where(
            is_area,
            torch.where(
                self.catalog.interval_ms[cards] > 0,
                self.catalog.interval_ms[cards],
                torch.full_like(cards, 50),
            ),
            0,
        ).to(torch.int32)
        state.next_tick_ms[rows, object_slots] = torch.where(
            self.catalog.kind[cards] == BridgePayloadKind.DIRECT_SPELL,
            0,
            self.catalog.initial_delay_ms[cards],
        ).to(torch.int32)
        state.ticks_remaining[rows, object_slots] = torch.where(
            self.catalog.kind[cards] == BridgePayloadKind.DIRECT_SPELL,
            torch.ones_like(cards),
            self.catalog.max_ticks[cards].to(torch.int64),
        ).to(torch.int32)
        state.amount[rows, object_slots] = damage
        state.feature_mask[rows, object_slots] = 0

        primary_id = torch.where(
            target_slots >= 0,
            runtime.battle.entity_id[rows, target_slots.clamp_min(0)],
            0,
        )
        phase.blueprint_kind[blueprints] = torch.where(
            is_area,
            torch.full_like(blueprints, RuntimeObjectKind.AREA),
            torch.full_like(blueprints, RuntimeObjectKind.PROJECTILE),
        ).to(torch.int8)
        phase.blueprint_payload_known[blueprints] = True
        phase.blueprint_primary_target_id[blueprints] = primary_id
        phase.blueprint_radius_units[blueprints] = self.catalog.radius_units[cards]
        phase.blueprint_hits_air[blueprints] = self.catalog.hits_air[cards]
        phase.blueprint_hits_ground[blueprints] = self.catalog.hits_ground[cards]
        phase.blueprint_ignore_buildings[blueprints] = self.catalog.ignore_buildings[
            cards
        ]
        phase.blueprint_crown_multiplier[blueprints] = self.catalog.crown_multiplier[
            cards
        ]
        phase.blueprint_crown_damage[blueprints] = self.catalog.crown_damage[cards]
        phase.blueprint_crown_damage_valid[blueprints] = (
            self.catalog.crown_damage_valid[cards]
        )
        self.blueprint_stun_ms[blueprints] = self.catalog.stun_ms[cards]
        self.blueprint_slow_ms[blueprints] = self.catalog.slow_ms[cards]
        self.blueprint_slow_multiplier[blueprints] = self.catalog.slow_multiplier[cards]
        self.blueprint_slow_attack_multiplier[blueprints] = (
            self.catalog.slow_attack_multiplier[cards]
        )
        self.blueprint_slow_spawn_multiplier[blueprints] = (
            self.catalog.slow_spawn_multiplier[cards]
        )
        self.blueprint_knockback_units[blueprints] = self.catalog.knockback_units[cards]
        self.blueprint_knockback_ignores_mass[blueprints] = (
            self.catalog.knockback_ignores_mass[cards]
        )
        self.blueprint_tracks_target[blueprints] = self.catalog.tracks_target[cards]
        self.blueprint_actual_damage[blueprints] = actual_damage
        self.blueprint_damage_group_slot[blueprints] = damage_group_slot.to(torch.int16)
        self.blueprint_card_id[blueprints] = cards
        phase.blueprint_kind[blueprints] = torch.where(
            self.catalog.kind[cards] == BridgePayloadKind.SPAWN_PROJECTILE,
            torch.full_like(blueprints, RuntimeObjectKind.SPAWN_PROJECTILE),
            phase.blueprint_kind[blueprints].to(torch.int64),
        ).to(torch.int8)

        _clear_runtime_slots(runtime, rows, entity_slots)
        runtime.battle.entity_id[rows, entity_slots] = entity_ids
        runtime.entity_pool.active[rows, entity_slots] = True
        runtime.battle.entity_active[rows, entity_slots] = True
        runtime.battle.entity_kind[rows, entity_slots] = torch.where(is_area, 3, 2).to(
            torch.int8
        )
        runtime.battle.entity_player[rows, entity_slots] = owners.to(torch.int8)
        runtime.battle.entity_card[rows, entity_slots] = public_cards.to(torch.int64)
        runtime.battle.entity_x_units[rows, entity_slots] = torch.where(
            is_area, end_x, start_x
        ).to(torch.int32)
        runtime.battle.entity_y_units[rows, entity_slots] = torch.where(
            is_area, end_y, start_y
        ).to(torch.int32)
        runtime.battle.entity_hp[rows, entity_slots] = 1
        # Scalar projectile and area-container entities are born with literal
        # integer hitpoints. Preserve that externally visible kind even though
        # retained numeric storage is float64.
        runtime.battle.entity_hp_integer_kind[rows, entity_slots] = True
        runtime.battle.entity_max_hp[rows, entity_slots] = 1
        runtime.battle.entity_tower_slot[rows, entity_slots] = -1

    def step_objects_(
        self,
        runtime: TensorBattleRuntime,
        object_phase: TensorRuntimeObjectPhase,
    ) -> RuntimeObjectPhaseResult:
        self.stun_applied.zero_()
        knockback_before = self.knockback_active.clone()
        before_count = runtime.events.count.clone()
        object_ids = object_phase.objects.object_id.clone()
        blueprint_ids = object_phase.objects.blueprint_id.clone().to(torch.int64)
        active = object_phase.objects.allocated.clone()
        object_player = object_phase.objects.player.clone()
        launch_x = object_phase.objects.x_units.clone()
        launch_y = object_phase.objects.y_units.clone()
        impact_x = object_phase.objects.target_x_units.clone()
        impact_y = object_phase.objects.target_y_units.clone()
        entity_ids_before = runtime.battle.entity_id.clone()
        hitpoints_before = runtime.battle.entity_hp.clone()
        self._refresh_homing_(runtime, object_phase)
        result = step_runtime_object_phase_(runtime, object_phase)
        self._apply_spawn_impacts_(
            runtime,
            object_phase,
            before_count,
            object_ids,
            blueprint_ids,
            active,
            object_player,
            result.supported_batch,
        )
        self._apply_status_events_(
            runtime,
            object_phase,
            before_count,
            object_ids,
            blueprint_ids,
            active,
            launch_x,
            launch_y,
            impact_x,
            impact_y,
            entity_ids_before,
            hitpoints_before,
            result.supported_batch,
        )
        self._advance_knockback_(runtime, knockback_before)
        return result

    def _advance_knockback_(
        self,
        runtime: TensorBattleRuntime,
        start_of_tick: torch.Tensor,
    ) -> None:
        identity = (
            self.knockback_entity_id == runtime.battle.entity_id
        ) & runtime.entity_pool.active
        stale = self.knockback_active & ~identity
        self.knockback_active &= identity
        self.knockback_entity_id.masked_fill_(stale, 0)
        self.knockback_velocity_work.masked_fill_(stale, 0)
        active = (
            start_of_tick
            & self.knockback_active
            & runtime.battle.entity_active
            & identity
        )
        next_velocity = self.knockback_velocity_work.to(torch.int64) - 25
        dx = self.knockback_target_units[:, :, 0].to(
            torch.int64
        ) - runtime.battle.entity_x_units.to(torch.int64)
        dy = self.knockback_target_units[:, :, 1].to(
            torch.int64
        ) - runtime.battle.entity_y_units.to(torch.int64)
        remaining = _integer_sqrt(dx * dx + dy * dy)
        movement = torch.minimum(
            torch.minimum(next_velocity.clamp(0, 250), remaining),
            remaining,
        )
        denominator = remaining.clamp_min(1)
        direction_x = _trunc_div(dx << 8, denominator)
        direction_y = _trunc_div(dy << 8, denominator)
        move_x = torch.bitwise_right_shift(direction_x * movement, 8)
        move_y = torch.bitwise_right_shift(direction_y * movement, 8)
        runtime.battle.entity_x_units.copy_(
            torch.where(
                active,
                (runtime.battle.entity_x_units.to(torch.int64) + move_x).clamp(
                    250, 17_750
                ),
                runtime.battle.entity_x_units.to(torch.int64),
            ).to(torch.int32)
        )
        runtime.battle.entity_y_units.copy_(
            torch.where(
                active,
                (runtime.battle.entity_y_units.to(torch.int64) + move_y).clamp(
                    250, 31_750
                ),
                runtime.battle.entity_y_units.to(torch.int64),
            ).to(torch.int32)
        )
        self.knockback_velocity_work.copy_(
            torch.where(
                active,
                next_velocity,
                self.knockback_velocity_work.to(torch.int64),
            ).to(torch.int32)
        )
        finished = active & (next_velocity < 0)
        self.knockback_active &= ~finished
        self.knockback_entity_id.masked_fill_(finished, 0)
        self.knockback_velocity_work.masked_fill_(finished, 0)

    def _apply_spawn_impacts_(
        self,
        runtime: TensorBattleRuntime,
        phase: TensorRuntimeObjectPhase,
        before_count: torch.Tensor,
        object_ids: torch.Tensor,
        blueprint_ids: torch.Tensor,
        object_active: torch.Tensor,
        object_player: torch.Tensor,
        supported: torch.Tensor,
    ) -> None:
        capacity = runtime.events.capacity
        event_slot = torch.arange(capacity, device=runtime.device)[None, :]
        marker = (
            supported[:, None]
            & (event_slot >= before_count[:, None])
            & (event_slot < runtime.events.count[:, None])
            & (runtime.events.opcode == int(RuntimeEventOpcode.PROJECTILE))
        )
        source_match = (
            marker[:, :, None]
            & object_active[:, None, :]
            & (runtime.events.source_id[:, :, None] == object_ids[:, None, :])
        )
        source_found = source_match.any(dim=2)
        source_object = source_match.to(torch.int64).argmax(dim=2)
        blueprint = torch.gather(blueprint_ids, 1, source_object).clamp_min(0)
        spell_card = self.blueprint_card_id[blueprint]
        spawn_marker = (
            marker
            & source_found
            & (
                self.catalog.kind[spell_card.clamp_min(0)]
                == BridgePayloadKind.SPAWN_PROJECTILE
            )
        )
        maximum_children = self.catalog.spawn_offsets_units.shape[3]
        child_index = torch.arange(maximum_children, device=runtime.device)[
            None, None, :
        ]
        child_count = self.catalog.spawn_count[spell_card].to(torch.int64)
        candidates = spawn_marker[:, :, None] & (child_index < child_count[:, :, None])
        candidate_key = event_slot[:, :, None] * maximum_children + child_index
        sentinel = capacity * maximum_children
        ordered = torch.sort(
            torch.where(candidates, candidate_key, sentinel).flatten(1), dim=1
        ).values
        total = candidates.flatten(1).sum(dim=1, dtype=torch.int64)
        allocation = runtime.entity_pool.allocate(total)
        install = allocation.valid
        rows, ordinal = torch.where(install)
        selected_key = ordered[rows, ordinal]
        impact_event = torch.div(selected_key, maximum_children, rounding_mode="floor")
        spawn_index = torch.remainder(selected_key, maximum_children)
        impact_object = source_object[rows, impact_event]
        owner = object_player[rows, impact_object].to(torch.int64)
        cards = spell_card[rows, impact_event]
        child_core_card = self.catalog.spawn_card_id[cards]
        impact_x = runtime.events.x_units[rows, impact_event].to(torch.int64)
        impact_y = runtime.events.y_units[rows, impact_event].to(torch.int64)
        source_x_cell = torch.div(
            impact_x, HALF_TILE_LOGIC_UNITS, rounding_mode="trunc"
        )
        source_y_cell = torch.div(
            impact_y, HALF_TILE_LOGIC_UNITS, rounding_mode="trunc"
        )
        distance = (
            self.lane_candidate_x[None, :] - source_x_cell[:, None]
        ).square() + (self.lane_candidate_y[None, :] - source_y_cell[:, None]).square()
        lane_candidate = torch.argmin(
            torch.where(
                self.lane_candidate_id[None, :] > 0,
                distance,
                torch.iinfo(torch.int64).max,
            ),
            dim=1,
        )
        lane_id = self.lane_candidate_id[lane_candidate]
        lane_index = (lane_id == 1).to(torch.int64)
        offset = self.catalog.spawn_offsets_units[
            cards, owner, lane_index, spawn_index
        ].to(torch.int64)
        spawn_x = (impact_x + offset[:, 0]).clamp(250, 17_750).to(torch.int32)
        spawn_y = (impact_y + offset[:, 1]).clamp(250, 31_750).to(torch.int32)
        entity_slot = allocation.slots[rows, ordinal]
        entity_id = allocation.entity_ids[rows, ordinal]
        _clear_runtime_slots(runtime, rows, entity_slot)
        runtime.battle.entity_id[rows, entity_slot] = entity_id
        runtime.entity_pool.active[rows, entity_slot] = True
        runtime.battle.entity_active[rows, entity_slot] = True
        runtime.battle.entity_kind[rows, entity_slot] = 0
        runtime.battle.entity_player[rows, entity_slot] = owner.to(torch.int8)
        runtime.battle.entity_card[rows, entity_slot] = child_core_card
        runtime.battle.entity_x_units[rows, entity_slot] = spawn_x
        runtime.battle.entity_y_units[rows, entity_slot] = spawn_y
        child_hp = self.catalog.spawn_hitpoints[cards]
        runtime.battle.entity_hp[rows, entity_slot] = child_hp
        runtime.battle.entity_max_hp[rows, entity_slot] = child_hp
        runtime.battle.entity_hp_integer_kind[rows, entity_slot] = (
            self.catalog.spawn_hp_integer_kind[cards]
        )
        delay_ms = (
            self.catalog.spawn_deploy_delay_ms[cards].to(torch.int64)
            - runtime.battle.tick_milliseconds[rows].to(torch.int64)
        ).clamp_min(0)
        delay = delay_ms.to(torch.float64) / 1_000
        pending = delay > 0
        runtime.battle.entity_deploy_delay[rows, entity_slot] = delay
        runtime.battle.entity_placement_pending[rows, entity_slot] = pending
        runtime.battle.entity_spawn_hook_pending[rows, entity_slot] = pending
        runtime.battle.entity_spawn_hook_fired[rows, entity_slot] = ~pending
        lifetime = self.catalog.spawn_lifetime_ms[cards]
        runtime.battle.entity_lifetime_ms[rows, entity_slot] = lifetime
        runtime.battle.entity_tower_slot[rows, entity_slot] = -1
        const_priority = self.catalog.spawn_const_priority[cards]
        priority_offset = spawn_index * 80
        self.spawn_target_distance_discount_sq_units[rows, entity_slot] = torch.where(
            const_priority, priority_offset.square(), 0
        )
        phase.target_collision_radius_units[rows, entity_slot] = (
            self.catalog.spawn_collision_radius_units[cards]
        )
        phase.target_airborne[rows, entity_slot] = self.catalog.spawn_is_air_unit[cards]
        phase.target_building[rows, entity_slot] = False
        phase.target_crown[rows, entity_slot] = False
        phase.target_payload_supported[rows, entity_slot] = True
        spawn_source = torch.zeros_like(allocation.entity_ids)
        spawn_x_padded = torch.zeros_like(allocation.slots, dtype=torch.int32)
        spawn_y_padded = torch.zeros_like(allocation.slots, dtype=torch.int32)
        spawn_card_padded = torch.zeros_like(allocation.entity_ids)
        spawn_source[rows, ordinal] = runtime.events.source_id[rows, impact_event]
        spawn_x_padded[rows, ordinal] = spawn_x
        spawn_y_padded[rows, ordinal] = spawn_y
        spawn_card_padded[rows, ordinal] = child_core_card
        runtime.events.append(
            phase=TickPhase.OBJECTS,
            opcode=RuntimeEventOpcode.SPAWN,
            valid=allocation.valid,
            source_id=spawn_source,
            target_id=allocation.entity_ids,
            x_units=spawn_x_padded,
            y_units=spawn_y_padded,
            payload=spawn_card_padded,
        )
        phase.objects.next_object_id.copy_(runtime.entity_pool.next_entity_id)

    def _refresh_homing_(
        self,
        runtime: TensorBattleRuntime,
        phase: TensorRuntimeObjectPhase,
    ) -> None:
        state = phase.objects
        blueprints = state.blueprint_id.to(torch.int64).clamp_min(0)
        homing = state.allocated & self.blueprint_tracks_target[blueprints]
        target_id = phase.blueprint_primary_target_id[blueprints]
        matches = (
            target_id[:, :, None] == runtime.battle.entity_id[:, None, :]
        ) & runtime.entity_pool.active[:, None, :]
        found = matches.any(dim=2)
        slots = matches.to(torch.int64).argmax(dim=2)
        rows, objects = torch.where(homing & found)
        targets = slots[rows, objects]
        state.target_x_units[rows, objects] = runtime.battle.entity_x_units[
            rows, targets
        ]
        state.target_y_units[rows, objects] = runtime.battle.entity_y_units[
            rows, targets
        ]

    def _apply_status_events_(
        self,
        runtime: TensorBattleRuntime,
        phase: TensorRuntimeObjectPhase,
        before_count: torch.Tensor,
        object_ids: torch.Tensor,
        blueprint_ids: torch.Tensor,
        object_active: torch.Tensor,
        launch_x: torch.Tensor,
        launch_y: torch.Tensor,
        impact_x: torch.Tensor,
        impact_y: torch.Tensor,
        entity_ids_before: torch.Tensor,
        hitpoints_before: torch.Tensor,
        supported: torch.Tensor,
    ) -> None:
        event_slot = torch.arange(runtime.events.capacity, device=runtime.device)[
            None, :
        ]
        valid = (
            supported[:, None]
            & (event_slot >= before_count[:, None])
            & (event_slot < runtime.events.count[:, None])
            & (runtime.events.opcode == int(RuntimeEventOpcode.DAMAGE))
        )
        source_match = (
            valid[:, :, None]
            & object_active[:, None, :]
            & (runtime.events.source_id[:, :, None] == object_ids[:, None, :])
        )
        source_found = source_match.any(dim=2)
        source_object = source_match.to(torch.int64).argmax(dim=2)
        blueprint = torch.gather(blueprint_ids, 1, source_object).clamp_min(0)
        target_match = (
            valid[:, :, None]
            & runtime.entity_pool.active[:, None, :]
            & (
                runtime.events.target_id[:, :, None]
                == runtime.battle.entity_id[:, None, :]
            )
        )
        target_found = target_match.any(dim=2)
        target_slot = target_match.to(torch.int64).argmax(dim=2)
        # Entity.take_damage casts every positive incoming amount to float
        # before subtraction, so even an integral result changes an integer HP
        # scalar to float. Do this from the committed projectile event plane;
        # it also includes lethal hits whose target is no longer alive below.
        kind_changed = (
            valid & source_found & target_found & (runtime.events.amount > 0.0)
        )
        changed_by_target = torch.zeros_like(runtime.battle.entity_hp_integer_kind)
        changed_by_target.scatter_reduce_(
            1,
            target_slot,
            kind_changed,
            reduce="amax",
            include_self=True,
        )
        runtime.battle.entity_hp_integer_kind &= ~changed_by_target
        alive = torch.gather(runtime.battle.entity_active, 1, target_slot)
        apply = valid & source_found & target_found & alive
        apply = self._apply_grouped_damage_(
            runtime,
            phase,
            before_count,
            valid,
            apply,
            blueprint,
            target_slot,
        )
        stun = self.blueprint_stun_ms[blueprint].to(torch.float64) / 1_000
        stun = torch.where(apply, stun, 0.0)
        stun_event = apply & (stun > 0.0)
        self.stun_applied.scatter_reduce_(
            1,
            target_slot,
            stun_event,
            reduce="amax",
            include_self=True,
        )
        projected = torch.zeros_like(runtime.status.stun_timer)
        projected.scatter_reduce_(
            1,
            target_slot,
            stun,
            reduce="amax",
            include_self=True,
        )
        runtime.status.stun_timer.copy_(
            torch.maximum(runtime.status.stun_timer, projected)
        )
        slow_duration = self.blueprint_slow_ms[blueprint].to(torch.float64) / 1_000
        slow_event = apply & (slow_duration > 0)
        slow_duration_by_target = torch.zeros_like(runtime.status.slow_timer)
        slow_duration_by_target.scatter_reduce_(
            1,
            target_slot,
            torch.where(slow_event, slow_duration, 0.0),
            reduce="amax",
            include_self=True,
        )
        positive_infinity = torch.full_like(runtime.status.slow_timer, torch.inf)

        def projected_min(values: torch.Tensor) -> torch.Tensor:
            projected_values = positive_infinity.clone()
            projected_values.scatter_reduce_(
                1,
                target_slot,
                torch.where(slow_event, values, torch.inf),
                reduce="amin",
                include_self=True,
            )
            return torch.where(torch.isfinite(projected_values), projected_values, 1.0)

        slow_mask = slow_duration_by_target > 0
        runtime.status.apply_slow(
            slow_duration_by_target,
            projected_min(self.blueprint_slow_multiplier[blueprint]),
            attack_speed_multiplier=projected_min(
                self.blueprint_slow_attack_multiplier[blueprint]
            ),
            spawn_speed_multiplier=projected_min(
                self.blueprint_slow_spawn_multiplier[blueprint]
            ),
            mask=slow_mask,
        )

        knockback_distance = self.blueprint_knockback_units[blueprint]
        knockback_event = apply & (knockback_distance > 0)
        first_index = torch.full_like(runtime.battle.entity_id, runtime.events.capacity)
        event_indices = event_slot.expand_as(valid)
        first_index.scatter_reduce_(
            1,
            target_slot,
            torch.where(
                knockback_event,
                event_indices,
                torch.full_like(event_indices, runtime.events.capacity),
            ),
            reduce="amin",
            include_self=True,
        )
        chosen = first_index < runtime.events.capacity
        chosen_event = first_index.clamp_max(runtime.events.capacity - 1)
        chosen_source_object = torch.gather(source_object, 1, chosen_event)
        chosen_blueprint = torch.gather(blueprint, 1, chosen_event)
        center_x = torch.gather(impact_x, 1, chosen_source_object)
        center_y = torch.gather(impact_y, 1, chosen_source_object)
        fallback_x = center_x - torch.gather(launch_x, 1, chosen_source_object)
        fallback_y = center_y - torch.gather(launch_y, 1, chosen_source_object)
        self._install_knockback_(
            runtime,
            target_mask=chosen,
            center_x=center_x,
            center_y=center_y,
            fallback_x=fallback_x,
            fallback_y=fallback_y,
            distance_units=self.blueprint_knockback_units[chosen_blueprint],
            ignores_mass=self.blueprint_knockback_ignores_mass[chosen_blueprint],
        )
        self._rewrite_public_object_events_(
            runtime,
            before_count,
            object_ids,
            blueprint_ids,
            object_active,
            entity_ids_before,
            hitpoints_before,
        )

    def _rewrite_public_object_events_(
        self,
        runtime: TensorBattleRuntime,
        before_count: torch.Tensor,
        object_ids: torch.Tensor,
        blueprint_ids: torch.Tensor,
        object_active: torch.Tensor,
        entity_ids_before: torch.Tensor,
        hitpoints_before: torch.Tensor,
    ) -> None:
        """Project internal object work records onto Python's public ledger."""

        capacity = runtime.events.capacity
        slots = torch.arange(capacity, dtype=torch.int64, device=runtime.device)[
            None, :
        ]
        segment = (slots >= before_count[:, None]) & (
            slots < runtime.events.count[:, None]
        )
        source_owned = (
            segment[:, :, None]
            & object_active[:, None, :]
            & (runtime.events.source_id[:, :, None] == object_ids[:, None, :])
        ).any(dim=2)
        source_object = (
            (
                segment[:, :, None]
                & object_active[:, None, :]
                & (runtime.events.source_id[:, :, None] == object_ids[:, None, :])
            )
            .to(torch.int64)
            .argmax(dim=2)
        )
        source_blueprint = torch.gather(blueprint_ids.clamp_min(0), 1, source_object)
        source_card = self.blueprint_card_id[source_blueprint].clamp_min(0)
        combat_source = source_owned & (
            self.catalog.kind[source_card] == int(BridgePayloadKind.COMBAT_PROJECTILE)
        )
        opcode = runtime.events.opcode.to(torch.int64)
        marker = source_owned & (
            (opcode == int(RuntimeEventOpcode.PROJECTILE))
            | (opcode == int(RuntimeEventOpcode.AREA))
        )
        child_spawn = source_owned & (opcode == int(RuntimeEventOpcode.SPAWN))
        target_event = (
            source_owned
            & (runtime.events.target_id > 0)
            & (
                (opcode == int(RuntimeEventOpcode.DAMAGE))
                | (opcode == int(RuntimeEventOpcode.DEATH))
            )
        )
        object_death = (
            source_owned
            & (runtime.events.target_id == 0)
            & (opcode == int(RuntimeEventOpcode.DEATH))
        )
        known = marker | child_spawn | target_event | object_death
        unknown = segment & ~known

        original = {
            name: getattr(runtime.events, name).clone()
            for name in (
                "phase",
                "opcode",
                "source_id",
                "target_id",
                "x_units",
                "y_units",
                "amount",
                "payload",
            )
        }
        output = {name: torch.zeros_like(value) for name, value in original.items()}
        prior = slots < before_count[:, None]
        for name, value in output.items():
            value[prior] = original[name][prior]
        offset = before_count.to(torch.int64).clone()
        batch_rows = torch.arange(runtime.batch_size, device=runtime.device)[:, None]

        def append_category(
            valid: torch.Tensor,
            planes: dict[str, torch.Tensor],
        ) -> None:
            nonlocal offset
            ordinal = torch.cumsum(valid.to(torch.int64), dim=1) - 1
            destination = offset[:, None] + ordinal
            admitted = valid & (destination < capacity)
            rows = batch_rows.expand_as(valid)[admitted]
            columns = destination[admitted]
            for name, values in planes.items():
                output[name][rows, columns] = values[admitted].to(output[name].dtype)
            offset += valid.sum(dim=1, dtype=torch.int64)

        maximum_id = torch.iinfo(torch.int64).max
        combat_marker = (
            combat_source & marker & (opcode == int(RuntimeEventOpcode.PROJECTILE))
        )
        combat_target = combat_source & target_event
        combat_event = combat_marker | combat_target
        target_identity = (
            original["target_id"][:, :, None] == entity_ids_before[:, None, :]
        ) & (original["target_id"][:, :, None] > 0)
        target_found = target_identity.any(dim=2)
        target_slot = target_identity.to(torch.int64).argmax(dim=2)
        combat_damage = (
            combat_target & (opcode == int(RuntimeEventOpcode.DAMAGE)) & target_found
        )
        damage_order = torch.argsort(
            torch.where(combat_damage, original["target_id"], maximum_id),
            dim=1,
            stable=True,
        )
        sorted_damage_valid = torch.gather(combat_damage, 1, damage_order)
        sorted_damage_target = torch.gather(original["target_id"], 1, damage_order)
        sorted_damage_amount = torch.where(
            sorted_damage_valid,
            torch.gather(original["amount"], 1, damage_order),
            0.0,
        )
        cumulative_damage = sorted_damage_amount.cumsum(dim=1)
        group_start = sorted_damage_valid & (
            (slots == 0)
            | (sorted_damage_target != torch.roll(sorted_damage_target, 1, dims=1))
        )
        group_baseline = (
            torch.where(
                group_start,
                cumulative_damage - sorted_damage_amount,
                0.0,
            )
            .cummax(dim=1)
            .values
        )
        sorted_prior_damage = cumulative_damage - sorted_damage_amount - group_baseline
        prior_damage = torch.zeros_like(original["amount"])
        prior_damage.scatter_(
            1,
            damage_order,
            torch.where(sorted_damage_valid, sorted_prior_damage, 0.0),
        )
        available_hitpoints = torch.gather(hitpoints_before, 1, target_slot)
        applied_damage = torch.minimum(
            original["amount"],
            (available_hitpoints - prior_damage).clamp_min(0.0),
        )
        public_amount = torch.where(
            combat_damage,
            applied_damage,
            original["amount"],
        )
        impact_target = torch.full_like(object_ids, maximum_id)
        impact_target.scatter_reduce_(
            1,
            source_object,
            torch.where(
                combat_target & (opcode == int(RuntimeEventOpcode.DAMAGE)),
                original["target_id"],
                maximum_id,
            ),
            reduce="amin",
            include_self=True,
        )
        impact_target = torch.where(impact_target == maximum_id, 0, impact_target)
        public_target = torch.where(
            combat_marker,
            torch.gather(impact_target, 1, source_object),
            original["target_id"],
        )
        death_rank = (opcode == int(RuntimeEventOpcode.DEATH)).to(torch.int64)
        event_rank = torch.where(
            combat_marker,
            torch.zeros_like(public_target),
            1 + public_target * 2 + death_rank,
        )
        event_rank_order = torch.argsort(
            torch.where(combat_event, event_rank, maximum_id),
            dim=1,
            stable=True,
        )
        ranked_valid = torch.gather(combat_event, 1, event_rank_order)
        ranked_source = torch.gather(original["source_id"], 1, event_rank_order)
        source_rank_order = torch.argsort(
            torch.where(ranked_valid, ranked_source, maximum_id),
            dim=1,
            stable=True,
        )
        combat_order = torch.gather(event_rank_order, 1, source_rank_order)
        combat_valid = torch.gather(combat_event, 1, combat_order)
        combat_source_object = torch.gather(source_object, 1, combat_order)
        combat_card = self.blueprint_card_id[
            torch.gather(blueprint_ids.clamp_min(0), 1, combat_source_object)
        ]
        combat_id = torch.gather(original["source_id"], 1, combat_order)
        append_category(
            combat_valid,
            {
                "phase": torch.full_like(combat_id, TickPhase.OBJECTS),
                "opcode": torch.gather(original["opcode"], 1, combat_order),
                "source_id": combat_id,
                "target_id": torch.gather(public_target, 1, combat_order),
                "x_units": torch.gather(original["x_units"], 1, combat_order),
                "y_units": torch.gather(original["y_units"], 1, combat_order),
                "amount": torch.where(
                    torch.gather(combat_marker, 1, combat_order),
                    torch.zeros_like(original["amount"]),
                    torch.gather(public_amount, 1, combat_order),
                ),
                "payload": combat_card,
            },
        )

        child_spawn &= ~combat_source
        target_event &= ~combat_source
        object_death &= ~combat_source
        spawn_order = torch.argsort(
            torch.where(child_spawn, original["target_id"], maximum_id),
            dim=1,
            stable=True,
        )
        spawn_valid = torch.gather(child_spawn, 1, spawn_order)
        spawn_id = torch.gather(original["target_id"], 1, spawn_order)
        append_category(
            spawn_valid,
            {
                "phase": torch.full_like(spawn_id, TickPhase.COMMANDS),
                "opcode": torch.full_like(spawn_id, RuntimeEventOpcode.SPAWN),
                "source_id": spawn_id,
                "target_id": torch.zeros_like(spawn_id),
                "x_units": torch.gather(original["x_units"], 1, spawn_order),
                "y_units": torch.gather(original["y_units"], 1, spawn_order),
                "amount": torch.zeros_like(original["amount"]),
                "payload": torch.gather(original["payload"], 1, spawn_order),
            },
        )

        target_order = torch.argsort(
            torch.where(target_event, original["target_id"], maximum_id),
            dim=1,
            stable=True,
        )
        sorted_valid = torch.gather(target_event, 1, target_order)
        sorted_target = torch.gather(original["target_id"], 1, target_order)
        sorted_amount = torch.gather(original["amount"], 1, target_order)
        sorted_death = (
            torch.gather(opcode == int(RuntimeEventOpcode.DEATH), 1, target_order)
            & sorted_valid
        )
        previous_target = torch.roll(sorted_target, 1, dims=1)
        group_start = sorted_valid & ((slots == 0) | (sorted_target != previous_target))
        group_index = (torch.cumsum(group_start.to(torch.int64), dim=1) - 1).clamp_min(
            0
        )
        grouped_target = torch.zeros_like(sorted_target)
        grouped_amount = torch.zeros_like(sorted_amount)
        grouped_death = torch.zeros_like(sorted_death)
        grouped_target.scatter_reduce_(
            1,
            group_index,
            torch.where(group_start, sorted_target, 0),
            reduce="amax",
            include_self=True,
        )
        grouped_amount.scatter_add_(
            1,
            group_index,
            torch.where(
                sorted_valid
                & (
                    torch.gather(opcode, 1, target_order)
                    == int(RuntimeEventOpcode.DAMAGE)
                ),
                sorted_amount,
                0.0,
            ),
        )
        grouped_death.scatter_reduce_(
            1,
            group_index,
            sorted_death,
            reduce="amax",
            include_self=True,
        )
        group_count = group_start.sum(dim=1, dtype=torch.int64)
        group_valid = slots < group_count[:, None]
        target_pair_valid = torch.stack((group_valid, grouped_death), dim=2).flatten(1)
        target_pair_id = torch.stack((grouped_target, grouped_target), dim=2).flatten(1)
        target_pair_amount = torch.stack(
            (grouped_amount, torch.zeros_like(grouped_amount)), dim=2
        ).flatten(1)
        append_category(
            target_pair_valid,
            {
                "phase": torch.full_like(target_pair_id, TickPhase.COMBAT),
                "opcode": torch.stack(
                    (
                        torch.full_like(grouped_target, RuntimeEventOpcode.DAMAGE),
                        torch.full_like(grouped_target, RuntimeEventOpcode.DEATH),
                    ),
                    dim=2,
                ).flatten(1),
                "source_id": torch.zeros_like(target_pair_id),
                "target_id": target_pair_id,
                "x_units": torch.zeros_like(target_pair_id),
                "y_units": torch.zeros_like(target_pair_id),
                "amount": target_pair_amount,
                "payload": torch.zeros_like(target_pair_id),
            },
        )

        death_order = torch.argsort(
            torch.where(object_death, original["source_id"], maximum_id),
            dim=1,
            stable=True,
        )
        death_valid = torch.gather(object_death, 1, death_order)
        death_id = torch.gather(original["source_id"], 1, death_order)
        object_pair_valid = torch.stack((death_valid, death_valid), dim=2).flatten(1)
        object_pair_id = torch.stack((death_id, death_id), dim=2).flatten(1)
        append_category(
            object_pair_valid,
            {
                "phase": torch.full_like(object_pair_id, TickPhase.COMBAT),
                "opcode": torch.stack(
                    (
                        torch.full_like(death_id, RuntimeEventOpcode.DAMAGE),
                        torch.full_like(death_id, RuntimeEventOpcode.DEATH),
                    ),
                    dim=2,
                ).flatten(1),
                "source_id": torch.zeros_like(object_pair_id),
                "target_id": object_pair_id,
                "x_units": torch.zeros_like(object_pair_id),
                "y_units": torch.zeros_like(object_pair_id),
                "amount": torch.stack(
                    (
                        torch.ones_like(original["amount"]),
                        torch.zeros_like(original["amount"]),
                    ),
                    dim=2,
                ).flatten(1),
                "payload": torch.zeros_like(object_pair_id),
            },
        )
        append_category(unknown, original)

        for name, value in output.items():
            getattr(runtime.events, name).copy_(value)
        runtime.events.count.copy_(offset.clamp_max(capacity).to(torch.int32))
        runtime.events.sequence.zero_()
        valid_sequence = slots < runtime.events.count[:, None]
        runtime.events.sequence.copy_(
            torch.where(valid_sequence, slots, 0).to(torch.int32)
        )

    def _apply_grouped_damage_(
        self,
        runtime: TensorBattleRuntime,
        phase: TensorRuntimeObjectPhase,
        before_count: torch.Tensor,
        valid_damage: torch.Tensor,
        apply: torch.Tensor,
        blueprint: torch.Tensor,
        target_slot: torch.Tensor,
    ) -> torch.Tensor:
        group_slot = self.blueprint_damage_group_slot[blueprint].to(torch.int64)
        grouped = apply & (group_slot > 0)
        event_slot = torch.arange(
            runtime.events.capacity, device=runtime.device, dtype=torch.int64
        )[None, :]
        key_width = self.damage_group_seen.shape[1] * runtime.max_entities
        key = (group_slot - 1).clamp_min(0) * runtime.max_entities + target_slot
        first_by_key = torch.full(
            (runtime.batch_size, key_width),
            runtime.events.capacity,
            dtype=torch.int64,
            device=runtime.device,
        )
        first_by_key.scatter_reduce_(
            1,
            key,
            torch.where(
                grouped,
                event_slot.expand_as(grouped),
                torch.full_like(grouped, runtime.events.capacity, dtype=torch.int64),
            ),
            reduce="amin",
            include_self=True,
        )
        first = grouped & (event_slot == torch.gather(first_by_key, 1, key))
        seen = torch.gather(self.damage_group_seen.flatten(1), 1, key)
        candidate = first & ~seen
        candidate_rows, candidate_events = torch.where(candidate)
        candidate_groups = group_slot[candidate_rows, candidate_events] - 1
        candidate_targets = target_slot[candidate_rows, candidate_events]
        self.damage_group_seen[candidate_rows, candidate_groups, candidate_targets] = (
            True
        )

        actual = self.blueprint_actual_damage[blueprint]
        target_crown = torch.gather(phase.target_crown, 1, target_slot)
        crown = phase.blueprint_crown_damage[blueprint]
        native_crown = _native_percent(
            actual, phase.blueprint_crown_multiplier[blueprint]
        )
        actual = torch.where(
            target_crown,
            torch.where(
                phase.blueprint_crown_damage_valid[blueprint], crown, native_crown
            ),
            actual,
        )
        target_building = torch.gather(phase.target_building, 1, target_slot)
        building = phase.blueprint_building_damage[blueprint]
        native_building = _native_percent(
            actual, phase.blueprint_building_multiplier[blueprint]
        )
        actual = torch.where(
            target_building & ~target_crown,
            torch.where(
                phase.blueprint_building_damage_valid[blueprint],
                building,
                native_building,
            ),
            actual,
        )
        event_damage = torch.where(candidate, actual, 0.0)
        damage_by_target = torch.zeros(
            (
                runtime.batch_size,
                runtime.events.capacity,
                runtime.max_entities,
            ),
            dtype=torch.float64,
            device=runtime.device,
        )
        damage_by_target.scatter_(
            2,
            target_slot[:, :, None],
            event_damage[:, :, None],
        )
        cumulative = damage_by_target.cumsum(dim=1)
        prior_by_target = cumulative - damage_by_target
        prior = torch.gather(
            prior_by_target,
            2,
            target_slot[:, :, None],
        )[:, :, 0]
        hp = torch.gather(runtime.battle.entity_hp, 1, target_slot)
        selected = candidate & (prior < hp)
        lethal = selected & (prior + actual >= hp)
        applied_damage = torch.where(selected, actual, 0.0)
        # Grouped projectile events are initially emitted with a zero amount;
        # their serialized damage is installed here after de-duplication.
        # Match Entity.take_damage's float conversion at that commit point.
        changed_by_target = torch.zeros_like(runtime.battle.entity_hp_integer_kind)
        changed_by_target.scatter_reduce_(
            1,
            target_slot,
            selected & (actual > 0.0),
            reduce="amax",
            include_self=True,
        )
        runtime.battle.entity_hp_integer_kind &= ~changed_by_target
        total = torch.zeros_like(runtime.battle.entity_hp)
        total.scatter_add_(1, target_slot, applied_damage)
        runtime.battle.entity_hp.copy_(
            (runtime.battle.entity_hp - total).clamp_min(0.0)
        )
        lethal_targets = torch.zeros_like(runtime.battle.entity_active)
        lethal_targets.scatter_reduce_(
            1,
            target_slot,
            lethal,
            reduce="amax",
            include_self=True,
        )
        runtime.battle.entity_active &= ~lethal_targets
        runtime.phases.death_pending |= lethal_targets
        runtime.events.amount.copy_(
            torch.where(selected, actual, runtime.events.amount)
        )
        self._rewrite_grouped_events_(
            runtime,
            before_count,
            valid_damage & (group_slot > 0),
            selected,
            lethal,
        )
        return (apply & (group_slot == 0)) | (selected & ~lethal)

    def _rewrite_grouped_events_(
        self,
        runtime: TensorBattleRuntime,
        before_count: torch.Tensor,
        grouped_damage: torch.Tensor,
        selected: torch.Tensor,
        lethal: torch.Tensor,
    ) -> None:
        capacity = runtime.events.capacity
        slot = torch.arange(capacity, device=runtime.device)[None, :]
        event_valid = slot < runtime.events.count[:, None]
        in_segment = slot >= before_count[:, None]
        keep = event_valid & ~(in_segment & grouped_damage & ~selected)
        pair_valid = torch.stack((keep, lethal), dim=2).flatten(1)
        destination = torch.cumsum(pair_valid.to(torch.int64), dim=1) - 1
        rows = torch.arange(runtime.batch_size, device=runtime.device)[:, None]
        rows = rows.expand_as(pair_valid)
        admitted = pair_valid & (destination < capacity)
        row_index = rows[admitted]
        destination_index = destination[admitted]

        original_phase = runtime.events.phase.clone()
        original_opcode = runtime.events.opcode.clone()
        original_source = runtime.events.source_id.clone()
        original_target = runtime.events.target_id.clone()
        original_x = runtime.events.x_units.clone()
        original_y = runtime.events.y_units.clone()
        original_amount = runtime.events.amount.clone()
        original_payload = runtime.events.payload.clone()
        death_opcode = torch.full_like(original_opcode, RuntimeEventOpcode.DEATH)
        zero_amount = torch.zeros_like(original_amount)
        paired = (
            (runtime.events.phase, torch.stack((original_phase, original_phase), 2)),
            (
                runtime.events.opcode,
                torch.stack((original_opcode, death_opcode), 2),
            ),
            (
                runtime.events.source_id,
                torch.stack((original_source, original_source), 2),
            ),
            (
                runtime.events.target_id,
                torch.stack((original_target, original_target), 2),
            ),
            (runtime.events.x_units, torch.stack((original_x, original_x), 2)),
            (runtime.events.y_units, torch.stack((original_y, original_y), 2)),
            (
                runtime.events.amount,
                torch.stack((original_amount, zero_amount), 2),
            ),
            (
                runtime.events.payload,
                torch.stack((original_payload, original_payload), 2),
            ),
        )
        for destination_plane, source_plane in paired:
            destination_plane.zero_()
            flattened = source_plane.flatten(1)
            destination_plane[row_index, destination_index] = flattened[admitted]
        new_count = pair_valid.sum(dim=1, dtype=torch.int64).clamp_max(capacity)
        runtime.events.count.copy_(new_count.to(torch.int32))
        runtime.events.sequence.zero_()
        sequence = torch.arange(capacity, device=runtime.device)[None, :]
        sequence_valid = sequence < runtime.events.count[:, None]
        runtime.events.sequence.copy_(
            torch.where(sequence_valid, sequence, 0).to(torch.int32)
        )


def _muzzle_position(
    source_x: torch.Tensor,
    source_y: torch.Tensor,
    target_x: torch.Tensor,
    target_y: torch.Tensor,
    radius: torch.Tensor,
    y_offset: torch.Tensor,
    owner: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    dx = (target_x - source_x).to(torch.int64)
    dy = (target_y - source_y).to(torch.int64)
    distance = _integer_sqrt(dx * dx + dy * dy).clamp_min(1)
    move_x = _trunc_div(dx * radius, distance)
    move_y = _trunc_div(dy * radius, distance)
    owner_offset = torch.where(owner == 0, y_offset, -y_offset)
    return (source_x + move_x).to(torch.int32), (source_y + move_y + owner_offset).to(
        torch.int32
    )


def _rotate_logic_tensor(
    x_units: torch.Tensor,
    y_units: torch.Tensor,
    degrees: torch.Tensor,
    sine_table: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    angle = torch.remainder(degrees.to(torch.int64), 360)
    sine = sine_table[angle]
    cosine = sine_table[torch.remainder(angle + 90, 360)]
    return (
        torch.bitwise_right_shift(cosine * x_units - sine * y_units, 10),
        torch.bitwise_right_shift(sine * x_units + cosine * y_units, 10),
    )


def _native_percent(damage: torch.Tensor, multiplier: torch.Tensor) -> torch.Tensor:
    base = torch.round(damage).to(torch.int64).clamp_min(0)
    percent = torch.round(multiplier * 100).to(torch.int64).clamp_min(0)
    return torch.where(
        (base > 0) & (percent > 0),
        torch.div(base * percent + 99, 100, rounding_mode="floor"),
        torch.zeros_like(base),
    ).to(torch.float64)


def _clear_runtime_slots(
    runtime: TensorBattleRuntime, rows: torch.Tensor, slots: torch.Tensor
) -> None:
    for descriptor in fields(runtime.battle):
        value = getattr(runtime.battle, descriptor.name)
        if (
            descriptor.name.startswith("entity_")
            and descriptor.name != "entity_id"
            and isinstance(value, torch.Tensor)
            and value.ndim >= 2
            and value.shape[1] == runtime.max_entities
        ):
            value[rows, slots] = 0
    runtime.battle.entity_tower_slot[rows, slots] = -1
    for owner in (runtime.status, runtime.phases):
        for descriptor in fields(owner):
            if owner is runtime.phases and descriptor.name in {
                "phase_cursor",
                "supported",
                "dirty",
            }:
                continue
            value = getattr(owner, descriptor.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim >= 2
                and value.shape[1] == runtime.max_entities
            ):
                value[rows, slots] = 0
    # Physical slot zero is a live entity slot, not the no-target sentinel.
    # Projectiles, areas, and spawned payload characters start untargeted.
    runtime.phases.target_slot[rows, slots] = INVALID_SLOT
