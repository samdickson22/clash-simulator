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
from clasher.gamedata_normalization import serialized_hit_planes
from clasher.kinematics import tiles_to_logic_units
from clasher.spells import (
    SPELL_REGISTRY,
    AreaEffectSpell,
    DirectDamageSpell,
    ProjectileSpell,
    SpawnProjectileSpell,
)

from .catalog import MECHANIC_OPCODE
from .combat import CombatStepResult, StationaryCombatState
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
    duration_ms: torch.Tensor
    interval_ms: torch.Tensor
    initial_delay_ms: torch.Tensor
    max_ticks: torch.Tensor
    damage_on_spawn: torch.Tensor
    projectile_start_radius_units: torch.Tensor
    projectile_y_offset_units: torch.Tensor
    tracks_target: torch.Tensor

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
        duration_ms = zeros(torch.int32)
        interval_ms = zeros(torch.int32)
        initial_delay_ms = zeros(torch.int32)
        max_ticks = zeros(torch.int16)
        damage_on_spawn = zeros(torch.bool)
        start_radius = zeros(torch.int32)
        y_offset = zeros(torch.int32)
        tracks_target = zeros(torch.bool)
        reasons: list[str | None] = ["padding has no payload"] * size
        definitions = battles[0].card_loader.load_card_definitions()

        for card_id, name in enumerate(runtime.battle.card_names[1:], start=1):
            stats = battles[0].card_loader.get_card(name)
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
                    )
                    reason = _direct_spell_reason(operation)
                elif isinstance(spell, SpawnProjectileSpell):
                    kind[card_id] = BridgePayloadKind.UNSUPPORTED
                    reason = "character-spawn projectile payload is not retained"
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
            if (
                buff.get("speedMultiplier") == -100
                and buff.get("hitSpeedMultiplier") == -100
                and slow_ms[card_id] > 0
            ):
                stun_ms[card_id] = slow_ms[card_id]
                slow_ms[card_id] = 0
                slow_multiplier[card_id] = 1.0
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
            if reason is None and slow_ms[card_id] > 0:
                reason = "combat projectile slow-source lifetime is not retained"
            unsupported_callbacks = tuple(
                type(mechanic).__name__
                for mechanic in definitions[name].mechanics
                if type(mechanic).__name__ not in {"CrownTowerScaling", "DamageRamp"}
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
            duration_ms=duration_ms,
            interval_ms=interval_ms,
            initial_delay_ms=initial_delay_ms,
            max_ticks=max_ticks,
            damage_on_spawn=damage_on_spawn,
            projectile_start_radius_units=start_radius,
            projectile_y_offset_units=y_offset,
            tracks_target=tracks_target,
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
    if spell.knockback_distance > 0:
        return "direct spell knockback is not retained"
    if bool(getattr(spell, "affects_hidden", False)):
        return "hidden-target direct spell semantics are not retained"
    if spell.slow_duration > 0:
        return "direct spell slow-source lifetime is not retained"
    return None


def _projectile_spell_reason(spell: Any) -> str | None:
    if spell.multiple_projectiles != 1 or spell.damage_waves != 1:
        return "multi-projectile/wave RNG payload is not retained"
    if spell.knockback_distance > 0:
        return "projectile spell knockback is not retained"
    if spell.slow_duration > 0:
        return "projectile spell slow-source lifetime is not retained"
    return None


def _area_spell_reason(spell: Any) -> str | None:
    if spell.freeze_effect or spell.speed_multiplier != 1.0:
        return "continuous freeze/slow area is not retained"
    if spell.target_local_damage or spell.periodic_damage_buff_duration > 0:
        return "target-local periodic spell damage is not retained"
    if spell.effect_tick_interval > 0 and spell.effect_tick_interval < 0.05:
        return "sub-frame area effect interval is not retained"
    return None


def _combat_projectile_reason(projectile: dict[str, Any]) -> str | None:
    if projectile.get("pushback", 0):
        return "combat projectile knockback is not retained"
    if projectile.get("spawnProjectileData"):
        return "impact child projectile is not retained"
    if projectile.get("projectileStartExtraRadius", 0):
        return "piercing/start collision projectile is not retained"
    return None


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


@dataclass
class TensorResidentProjectileSpellBridge:
    catalog: TensorProjectileSpellCatalog
    blueprint_for_slot: torch.Tensor
    blueprint_stun_ms: torch.Tensor
    blueprint_slow_ms: torch.Tensor
    blueprint_slow_multiplier: torch.Tensor
    blueprint_tracks_target: torch.Tensor
    king_x_units: torch.Tensor
    king_y_units: torch.Tensor
    rng_counter: torch.Tensor

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        object_phase: TensorRuntimeObjectPhase,
        battles: Sequence[BattleState],
    ) -> TensorResidentProjectileSpellBridge:
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
            blueprint_tracks_target=torch.zeros(
                expanded.size, dtype=torch.bool, device=runtime.device
            ),
            king_x_units=king_x,
            king_y_units=king_y,
            rng_counter=torch.zeros(
                runtime.batch_size, dtype=torch.int64, device=runtime.device
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
        launch = (valid & ~direct)[:, None]
        object_supported = self._materialize_(
            runtime,
            object_phase,
            card_ids=card_ids[:, None],
            source_ids=torch.zeros(
                (batch, 1), dtype=torch.int64, device=runtime.device
            ),
            owners=player_ids[:, None],
            source_x=source_x,
            source_y=source_y,
            target_slots=torch.full(
                (batch, 1), -1, dtype=torch.int64, device=runtime.device
            ),
            target_x=target_x_units[:, None],
            target_y=target_y_units[:, None],
            damage=self.catalog.damage[card_ids][:, None],
            launch=launch,
            spell=True,
            payload_kind=payload_kind,
        )
        return direct_supported & object_supported

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
        ordered_amount = torch.gather(amount, 1, order)
        before_alive = runtime.battle.entity_active.clone()
        candidate_hp = torch.where(
            targets,
            (runtime.battle.entity_hp - amount).clamp_min(0),
            runtime.battle.entity_hp,
        )
        died = targets & before_alive & (candidate_hp <= 0)
        ordered_died = torch.gather(died, 1, order) & ordered_valid
        pair_valid = torch.stack((ordered_valid, ordered_died), dim=2).flatten(1)
        survivors = targets & ~died
        stun_seconds = self.catalog.stun_ms[card_ids].to(torch.float64) / 1_000
        status_valid = torch.gather(survivors & (stun_seconds[:, None] > 0), 1, order)
        additions = pair_valid.sum(dim=1, dtype=torch.int64) + status_valid.sum(
            dim=1, dtype=torch.int64
        )
        overflow = supported & (
            runtime.events.count.to(torch.int64) + additions > runtime.events.capacity
        )
        supported &= ~overflow
        targets &= supported[:, None]
        died &= supported[:, None]
        ordered_valid &= supported[:, None]
        ordered_died &= supported[:, None]
        pair_valid = torch.stack((ordered_valid, ordered_died), dim=2).flatten(1)
        status_valid &= supported[:, None]
        runtime.battle.entity_hp.copy_(
            torch.where(targets, candidate_hp, runtime.battle.entity_hp)
        )
        runtime.battle.entity_active &= ~died
        runtime.phases.death_pending |= died
        damage_opcode = torch.full_like(ordered_ids, RuntimeEventOpcode.DAMAGE)
        death_opcode = torch.full_like(ordered_ids, RuntimeEventOpcode.DEATH)
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
            payload=card_ids[:, None],
        )
        survivors = targets & runtime.battle.entity_active
        runtime.status.stun_timer.copy_(
            torch.where(
                survivors & (stun_seconds[:, None] > 0),
                torch.maximum(runtime.status.stun_timer, stun_seconds[:, None]),
                runtime.status.stun_timer,
            )
        )
        runtime.events.append(
            phase=TickPhase.COMMANDS,
            opcode=RuntimeEventOpcode.STATUS,
            valid=status_valid,
            target_id=ordered_ids,
            amount=stun_seconds[:, None],
            payload=card_ids[:, None],
        )
        runtime.mark_dirty(valid & supported, phase=TickPhase.COMMANDS)
        return supported

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
    ) -> torch.Tensor:
        safe_cards = card_ids.clamp_min(0)
        supported_launch = self.catalog.supported[safe_cards]
        valid_target = (
            torch.ones_like(launch)
            if spell
            else (target_slots >= 0) & (target_slots < runtime.max_entities)
        )
        row_supported = ~(launch & (~supported_launch | ~valid_target)).any(dim=1)
        counts = (launch & row_supported[:, None]).sum(dim=1, dtype=torch.int64)
        free_objects = (~object_phase.objects.allocated).sum(dim=1)
        free_entities = (~runtime.entity_pool.active).sum(dim=1)
        row_supported &= (counts <= free_objects) & (counts <= free_entities)
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
        self._install_object(
            runtime,
            object_phase,
            rows,
            object_slot,
            entity_slot,
            entity_id,
            blueprint,
            cards,
            owners[rows, source_slot],
            start_x,
            start_y,
            end_x,
            end_y,
            damage[rows, source_slot],
            target_slots[rows, source_slot],
            is_area,
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
        owners: torch.Tensor,
        start_x: torch.Tensor,
        start_y: torch.Tensor,
        end_x: torch.Tensor,
        end_y: torch.Tensor,
        damage: torch.Tensor,
        target_slots: torch.Tensor,
        is_area: torch.Tensor,
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
        self.blueprint_tracks_target[blueprints] = self.catalog.tracks_target[cards]

        _clear_runtime_slots(runtime, rows, entity_slots)
        runtime.battle.entity_id[rows, entity_slots] = entity_ids
        runtime.entity_pool.active[rows, entity_slots] = True
        runtime.battle.entity_active[rows, entity_slots] = True
        runtime.battle.entity_kind[rows, entity_slots] = torch.where(is_area, 3, 2).to(
            torch.int8
        )
        runtime.battle.entity_player[rows, entity_slots] = owners.to(torch.int8)
        runtime.battle.entity_card[rows, entity_slots] = cards.to(torch.int64)
        runtime.battle.entity_x_units[rows, entity_slots] = torch.where(
            is_area, end_x, start_x
        ).to(torch.int32)
        runtime.battle.entity_y_units[rows, entity_slots] = torch.where(
            is_area, end_y, start_y
        ).to(torch.int32)
        runtime.battle.entity_hp[rows, entity_slots] = 1
        runtime.battle.entity_max_hp[rows, entity_slots] = 1
        runtime.battle.entity_tower_slot[rows, entity_slots] = -1

    def step_objects_(
        self,
        runtime: TensorBattleRuntime,
        object_phase: TensorRuntimeObjectPhase,
    ) -> RuntimeObjectPhaseResult:
        before_count = runtime.events.count.clone()
        object_ids = object_phase.objects.object_id.clone()
        blueprint_ids = object_phase.objects.blueprint_id.clone().to(torch.int64)
        active = object_phase.objects.allocated.clone()
        self._refresh_homing_(runtime, object_phase)
        result = step_runtime_object_phase_(runtime, object_phase)
        self._apply_status_events_(
            runtime,
            before_count,
            object_ids,
            blueprint_ids,
            active,
            result.supported_batch,
        )
        return result

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
        before_count: torch.Tensor,
        object_ids: torch.Tensor,
        blueprint_ids: torch.Tensor,
        object_active: torch.Tensor,
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
        alive = torch.gather(runtime.battle.entity_active, 1, target_slot)
        apply = valid & source_found & target_found & alive
        stun = self.blueprint_stun_ms[blueprint].to(torch.float64) / 1_000
        stun = torch.where(apply, stun, 0.0)
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
