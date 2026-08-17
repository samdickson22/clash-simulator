"""Generalized serialized combat-mechanic tensor kernels.

This module is intentionally runtime-agnostic.  It compiles mechanic payloads
from serialized definitions and exposes pure CPU/CUDA kernels for damage
scaling, continuous-damage ramps, effect targeting, chain ordering, secondary
hits, and spawn/death area events.  No operation branches on a card name.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import IntEnum
from numbers import Real
from typing import Any, cast

import torch

from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.kinematics import tiles_to_logic_units

from .catalog import MECHANIC_OPCODE


class CombatMechanicOpcode(IntEnum):
    CROWN_TOWER_SCALING = MECHANIC_OPCODE["CrownTowerScaling"]
    DAMAGE_RAMP = MECHANIC_OPCODE["DamageRamp"]
    DEATH_AREA = MECHANIC_OPCODE["DeathAreaEffect"]
    DEATH_DAMAGE = MECHANIC_OPCODE["DeathDamage"]
    ELECTRO_DRAGON_CHAIN = MECHANIC_OPCODE["ElectroDragonChainLightning"]
    ELECTRO_SPIRIT_CHAIN = MECHANIC_OPCODE["ElectroSpiritChain"]
    ICE_SPIRIT_FREEZE = MECHANIC_OPCODE["IceSpiritFreeze"]
    MULTIPLE_TARGET = MECHANIC_OPCODE["MultipleTargetAttack"]
    SPAWN_AREA = MECHANIC_OPCODE["SpawnAreaEffect"]


class MechanicEventOpcode(IntEnum):
    DAMAGE = 1
    STUN = 2
    KNOCKBACK = 3
    SECONDARY_HIT = 4
    CHAIN_LIGHTNING = 5
    SPAWN_AREA = 6
    DEATH_AREA = 7
    DAMAGE_STAGE = 8


SUPPORTED_MECHANIC_NAMES = tuple(
    name
    for name in (
        "CrownTowerScaling",
        "DamageRamp",
        "DeathAreaEffect",
        "DeathDamage",
        "ElectroDragonChainLightning",
        "ElectroSpiritChain",
        "IceSpiritFreeze",
        "MultipleTargetAttack",
        "SpawnAreaEffect",
    )
)


def _serialized_multiplier(value: object, default: float = 1.0) -> float:
    if value is None:
        return default
    number = _number(value)
    return max(0.0, (100.0 + number if number <= 0 else number) / 100.0)


def _number(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, Real):
        return float(value)
    raise TypeError(f"expected serialized number, got {type(value).__name__}")


def _first_action_spawn(value: object) -> dict[str, object] | None:
    if isinstance(value, dict):
        spawn = value.get("spawnDataData")
        if isinstance(spawn, dict):
            return spawn
        for nested in value.values():
            found = _first_action_spawn(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _first_action_spawn(nested)
            if found is not None:
                return found
    return None


def _resolved_area_data(raw: object) -> tuple[dict[str, object], int]:
    if not isinstance(raw, dict):
        return {}, 0
    action = _first_action_spawn(raw.get("onStartingActionData"))
    nested = action.get("deathAreaEffectData") if action is not None else None
    if isinstance(nested, dict):
        assert action is not None
        return nested, int(_number(action.get("deployTime", 0)))
    return raw, 0


@dataclass(frozen=True)
class TensorCombatMechanicCatalog:
    device: torch.device
    names: tuple[str, ...]
    name_to_id: dict[str, int]
    opcode: torch.Tensor
    count: torch.Tensor
    crown_multiplier: torch.Tensor
    crown_damage: torch.Tensor
    crown_damage_valid: torch.Tensor
    ramp_stage_count: torch.Tensor
    ramp_stage_time_ms: torch.Tensor
    ramp_stage_damage: torch.Tensor
    radius_units: torch.Tensor
    damage: torch.Tensor
    knockback_units: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    chain_count: torch.Tensor
    chain_range_units: torch.Tensor
    chain_damage_decay: torch.Tensor
    chain_stun_ms: torch.Tensor
    chain_speed_units: torch.Tensor
    chain_interval_ms: torch.Tensor
    multiple_target_count: torch.Tensor
    multiple_all_hit: torch.Tensor
    multiple_damage_scale: torch.Tensor
    area_duration_ms: torch.Tensor
    area_delay_ms: torch.Tensor
    area_hit_interval_ms: torch.Tensor
    area_buff_ms: torch.Tensor
    area_damage: torch.Tensor
    area_crown_multiplier: torch.Tensor
    area_movement_multiplier: torch.Tensor
    area_attack_multiplier: torch.Tensor
    area_spawn_multiplier: torch.Tensor
    area_affects_hidden: torch.Tensor

    @property
    def max_mechanics(self) -> int:
        return int(self.opcode.shape[1])

    @classmethod
    def compile(
        cls,
        loader: CardDataLoader,
        card_names: Iterable[str],
        *,
        device: str | torch.device = "cpu",
    ) -> TensorCombatMechanicCatalog:
        definitions = loader.load_card_definitions()
        resolved = tuple(
            sorted({resolve_card_name(name, definitions) for name in card_names})
        )
        names = ("", *resolved)
        name_to_id = {name: index for index, name in enumerate(names)}
        maximum = max(
            1,
            max(
                (
                    sum(
                        type(mechanic).__name__ in SUPPORTED_MECHANIC_NAMES
                        for mechanic in definitions[name].mechanics
                    )
                    for name in resolved
                ),
                default=0,
            ),
        )
        maximum_stages = max(
            1,
            max(
                (
                    len(getattr(mechanic, "stages", ()))
                    for name in resolved
                    for mechanic in definitions[name].mechanics
                    if type(mechanic).__name__ == "DamageRamp"
                ),
                default=0,
            ),
        )
        torch_device = torch.device(device)
        shape = (len(names), maximum)

        def zeros(dtype: torch.dtype, *suffix: int) -> torch.Tensor:
            return torch.zeros((*shape, *suffix), dtype=dtype, device=torch_device)

        opcode = zeros(torch.int16)
        count = torch.zeros(len(names), dtype=torch.int8, device=torch_device)
        crown_multiplier = torch.ones(shape, dtype=torch.float64, device=torch_device)
        crown_damage = zeros(torch.float64)
        crown_damage_valid = zeros(torch.bool)
        ramp_stage_count = zeros(torch.int8)
        ramp_stage_time = zeros(torch.int32, maximum_stages)
        ramp_stage_damage = zeros(torch.float64, maximum_stages)
        radius = zeros(torch.int32)
        damage = zeros(torch.float64)
        knockback = zeros(torch.int32)
        hits_air = torch.ones(shape, dtype=torch.bool, device=torch_device)
        hits_ground = torch.ones(shape, dtype=torch.bool, device=torch_device)
        chain_count = zeros(torch.int16)
        chain_range = zeros(torch.int32)
        chain_decay = torch.ones(shape, dtype=torch.float64, device=torch_device)
        chain_stun = zeros(torch.int32)
        chain_speed = zeros(torch.int32)
        chain_interval = zeros(torch.int32)
        multiple_count = torch.ones(shape, dtype=torch.int16, device=torch_device)
        multiple_all = zeros(torch.bool)
        multiple_scale = torch.ones(shape, dtype=torch.float64, device=torch_device)
        area_duration = zeros(torch.int32)
        area_delay = zeros(torch.int32)
        area_interval = zeros(torch.int32)
        area_buff = zeros(torch.int32)
        area_damage = zeros(torch.float64)
        area_crown = torch.ones(shape, dtype=torch.float64, device=torch_device)
        area_movement = torch.ones(shape, dtype=torch.float64, device=torch_device)
        area_attack = torch.ones(shape, dtype=torch.float64, device=torch_device)
        area_spawn = torch.ones(shape, dtype=torch.float64, device=torch_device)
        area_hidden = zeros(torch.bool)

        for card_id, name in enumerate(resolved, start=1):
            card = loader.get_card(name)
            scaler = getattr(card, "get_scaled_stat", None)
            slot = 0
            for mechanic in definitions[name].mechanics:
                mechanic_name = type(mechanic).__name__
                if mechanic_name not in SUPPORTED_MECHANIC_NAMES:
                    continue
                operation = cast(Any, mechanic)
                opcode[card_id, slot] = MECHANIC_OPCODE[mechanic_name]
                if mechanic_name == "CrownTowerScaling":
                    crown_multiplier[card_id, slot] = float(operation.damage_multiplier)
                    if operation.crown_tower_damage is not None:
                        crown_damage[card_id, slot] = operation.crown_tower_damage
                        crown_damage_valid[card_id, slot] = True
                elif mechanic_name == "DamageRamp":
                    stages = tuple(operation.stages)
                    ramp_stage_count[card_id, slot] = len(stages)
                    for stage, (time_ms, stage_damage) in enumerate(stages):
                        ramp_stage_time[card_id, slot, stage] = time_ms
                        ramp_stage_damage[card_id, slot, stage] = (
                            float(scaler(stage_damage))
                            if callable(scaler)
                            else stage_damage
                        )
                elif mechanic_name == "DeathDamage":
                    radius[card_id, slot] = tiles_to_logic_units(operation.radius_tiles)
                    damage[card_id, slot] = (
                        float(scaler(operation.damage))
                        if callable(scaler)
                        else operation.damage
                    )
                    knockback[card_id, slot] = tiles_to_logic_units(
                        operation.knockback_distance
                    )
                    hits_air[card_id, slot] = operation.hits_air
                    hits_ground[card_id, slot] = operation.hits_ground
                elif mechanic_name in {
                    "ElectroDragonChainLightning",
                    "ElectroSpiritChain",
                }:
                    chain_range[card_id, slot] = tiles_to_logic_units(
                        operation.chain_range
                    )
                    chain_count[card_id, slot] = int(
                        getattr(
                            operation,
                            "max_targets",
                            getattr(operation, "max_bounces", 0) + 1,
                        )
                    )
                    chain_decay[card_id, slot] = operation.damage_decay
                    chain_stun[card_id, slot] = operation.stun_duration_ms
                    chain_speed[card_id, slot] = round(
                        operation.projectile_speed_tiles_per_second * 1_000 / 20
                    )
                    chain_interval[card_id, slot] = round(
                        float(getattr(operation, "chain_interval_seconds", 0.0)) * 1_000
                    )
                elif mechanic_name == "IceSpiritFreeze":
                    radius[card_id, slot] = tiles_to_logic_units(
                        operation.freeze_radius
                    )
                    chain_stun[card_id, slot] = operation.freeze_duration_ms
                    chain_speed[card_id, slot] = (
                        operation.jump_speed_logic_units_per_tick
                    )
                elif mechanic_name == "MultipleTargetAttack":
                    multiple_count[card_id, slot] = operation.target_count
                    multiple_all[card_id, slot] = operation.all_targets_hit
                    multiple_scale[card_id, slot] = operation.damage_scale
                elif mechanic_name in {"DeathAreaEffect", "SpawnAreaEffect"}:
                    raw, delay_ms = _resolved_area_data(operation.area_data)
                    radius[card_id, slot] = int(_number(raw.get("radius", 0)))
                    area_duration[card_id, slot] = max(
                        1, int(_number(raw.get("lifeDuration", 0)))
                    )
                    area_delay[card_id, slot] = delay_ms
                    area_interval[card_id, slot] = max(
                        0, int(_number(raw.get("hitSpeed", 0)))
                    )
                    area_buff[card_id, slot] = max(
                        0, int(_number(raw.get("buffTime", 0)))
                    )
                    base_damage = _number(raw.get("damage", 0))
                    area_damage[card_id, slot] = (
                        float(scaler(base_damage)) if callable(scaler) else base_damage
                    )
                    area_crown[card_id, slot] = max(
                        0.0,
                        1.0 + _number(raw.get("crownTowerDamagePercent", 0)) / 100.0,
                    )
                    buff = raw.get("buffData") or {}
                    if isinstance(buff, dict):
                        area_movement[card_id, slot] = _serialized_multiplier(
                            buff.get("speedMultiplier")
                        )
                        area_attack[card_id, slot] = _serialized_multiplier(
                            buff.get("hitSpeedMultiplier")
                        )
                        area_spawn[card_id, slot] = _serialized_multiplier(
                            buff.get("spawnSpeedMultiplier")
                        )
                    hits_air[card_id, slot] = bool(raw.get("hitsAir", True))
                    hits_ground[card_id, slot] = bool(raw.get("hitsGround", True))
                    area_hidden[card_id, slot] = bool(raw.get("affectsHidden", False))
                slot += 1
            count[card_id] = slot

        return cls(
            device=torch_device,
            names=names,
            name_to_id=name_to_id,
            opcode=opcode,
            count=count,
            crown_multiplier=crown_multiplier,
            crown_damage=crown_damage,
            crown_damage_valid=crown_damage_valid,
            ramp_stage_count=ramp_stage_count,
            ramp_stage_time_ms=ramp_stage_time,
            ramp_stage_damage=ramp_stage_damage,
            radius_units=radius,
            damage=damage,
            knockback_units=knockback,
            hits_air=hits_air,
            hits_ground=hits_ground,
            chain_count=chain_count,
            chain_range_units=chain_range,
            chain_damage_decay=chain_decay,
            chain_stun_ms=chain_stun,
            chain_speed_units=chain_speed,
            chain_interval_ms=chain_interval,
            multiple_target_count=multiple_count,
            multiple_all_hit=multiple_all,
            multiple_damage_scale=multiple_scale,
            area_duration_ms=area_duration,
            area_delay_ms=area_delay,
            area_hit_interval_ms=area_interval,
            area_buff_ms=area_buff,
            area_damage=area_damage,
            area_crown_multiplier=area_crown,
            area_movement_multiplier=area_movement,
            area_attack_multiplier=area_attack,
            area_spawn_multiplier=area_spawn,
            area_affects_hidden=area_hidden,
        )

    def mechanic_slot(
        self, card_ids: torch.Tensor, opcode: CombatMechanicOpcode
    ) -> tuple[torch.Tensor, torch.Tensor]:
        ids = card_ids.to(device=self.device, dtype=torch.int64)
        matches = self.opcode[ids] == int(opcode)
        return matches.to(torch.int64).argmax(dim=-1), matches.any(dim=-1)


@dataclass
class TensorMechanicWorld:
    present: torch.Tensor
    entity_id: torch.Tensor
    owner: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    collision_radius_units: torch.Tensor
    distance_discount_sq_units: torch.Tensor
    hp: torch.Tensor
    alive: torch.Tensor
    airborne: torch.Tensor
    building: torch.Tensor
    crown: torch.Tensor
    targetable: torch.Tensor
    effect_receivable: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.present.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.present.shape[1])

    @property
    def device(self) -> torch.device:
        return self.present.device

    @classmethod
    def empty(
        cls,
        batch_size: int,
        max_entities: int,
        *,
        device: str | torch.device = "cpu",
    ) -> TensorMechanicWorld:
        torch_device = torch.device(device)
        shape = (batch_size, max_entities)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=torch_device)

        return cls(
            present=zeros(torch.bool),
            entity_id=zeros(torch.int64),
            owner=zeros(torch.int8),
            x_units=zeros(torch.int32),
            y_units=zeros(torch.int32),
            collision_radius_units=zeros(torch.int32),
            distance_discount_sq_units=zeros(torch.int64),
            hp=zeros(torch.float64),
            alive=zeros(torch.bool),
            airborne=zeros(torch.bool),
            building=zeros(torch.bool),
            crown=zeros(torch.bool),
            targetable=torch.ones(shape, dtype=torch.bool, device=torch_device),
            effect_receivable=torch.ones(shape, dtype=torch.bool, device=torch_device),
        )


@dataclass
class TensorDamageRampState:
    target_id: torch.Tensor
    target_time_ms: torch.Tensor
    damage: torch.Tensor

    @classmethod
    def empty(
        cls, shape: Sequence[int], *, device: str | torch.device = "cpu"
    ) -> TensorDamageRampState:
        torch_device = torch.device(device)
        return cls(
            target_id=torch.zeros(shape, dtype=torch.int64, device=torch_device),
            target_time_ms=torch.zeros(shape, dtype=torch.float64, device=torch_device),
            damage=torch.zeros(shape, dtype=torch.float64, device=torch_device),
        )


@dataclass
class TensorMechanicEvents:
    count: torch.Tensor
    opcode: torch.Tensor
    sequence: torch.Tensor
    source_id: torch.Tensor
    target_id: torch.Tensor
    amount: torch.Tensor
    duration_ms: torch.Tensor
    radius_units: torch.Tensor
    payload_opcode: torch.Tensor

    @classmethod
    def empty(
        cls,
        batch_size: int,
        capacity: int,
        *,
        device: str | torch.device = "cpu",
    ) -> TensorMechanicEvents:
        torch_device = torch.device(device)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros((batch_size, capacity), dtype=dtype, device=torch_device)

        return cls(
            count=torch.zeros(batch_size, dtype=torch.int32, device=torch_device),
            opcode=zeros(torch.int16),
            sequence=zeros(torch.int32),
            source_id=zeros(torch.int64),
            target_id=zeros(torch.int64),
            amount=zeros(torch.float64),
            duration_ms=zeros(torch.int32),
            radius_units=zeros(torch.int32),
            payload_opcode=zeros(torch.int16),
        )

    def append(
        self,
        *,
        valid: torch.Tensor,
        opcode: int | torch.Tensor,
        source_id: int | torch.Tensor = 0,
        target_id: int | torch.Tensor = 0,
        amount: float | torch.Tensor = 0.0,
        duration_ms: int | torch.Tensor = 0,
        radius_units: int | torch.Tensor = 0,
        payload_opcode: int | torch.Tensor = 0,
    ) -> None:
        selected = valid.to(dtype=torch.bool, device=self.count.device)
        width = selected.shape[1]

        def lanes(value: object, dtype: torch.dtype) -> torch.Tensor:
            return torch.broadcast_to(
                torch.as_tensor(value, dtype=dtype, device=self.count.device),
                (self.count.shape[0], width),
            )

        local = selected.cumsum(dim=1) - 1
        destinations = self.count[:, None].to(torch.int64) + local
        additions = selected.sum(dim=1, dtype=torch.int64)
        if bool(((self.count + additions) > self.opcode.shape[1]).any().item()):
            raise OverflowError("mechanic event capacity exhausted")
        rows = torch.arange(self.count.shape[0], device=self.count.device)[:, None]
        rows = rows.expand_as(selected)[selected]
        slots = destinations[selected]
        for destination, value, dtype in (
            (self.opcode, opcode, torch.int16),
            (self.source_id, source_id, torch.int64),
            (self.target_id, target_id, torch.int64),
            (self.amount, amount, torch.float64),
            (self.duration_ms, duration_ms, torch.int32),
            (self.radius_units, radius_units, torch.int32),
            (self.payload_opcode, payload_opcode, torch.int16),
        ):
            destination[rows, slots] = lanes(value, dtype)[selected]
        self.sequence[rows, slots] = slots.to(torch.int32)
        self.count += additions.to(torch.int32)


def _native_percent(damage: torch.Tensor, multiplier: torch.Tensor) -> torch.Tensor:
    base = torch.round(damage).to(torch.int64).clamp_min(0)
    percent = torch.round(multiplier * 100).to(torch.int64).clamp_min(0)
    return torch.where(
        (base > 0) & (percent > 0),
        torch.div(base * percent + 99, 100, rounding_mode="floor"),
        torch.zeros_like(base),
    ).to(torch.float64)


def apply_crown_tower_scaling(
    catalog: TensorCombatMechanicCatalog,
    card_ids: torch.Tensor,
    damage: torch.Tensor,
    is_crown: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    slot, present = catalog.mechanic_slot(
        card_ids, CombatMechanicOpcode.CROWN_TOWER_SCALING
    )
    ids = card_ids.to(device=catalog.device, dtype=torch.int64)
    multiplier = catalog.crown_multiplier[ids, slot]
    explicit = catalog.crown_damage[ids, slot]
    explicit_valid = catalog.crown_damage_valid[ids, slot]
    scaled = torch.where(
        explicit_valid,
        explicit,
        _native_percent(damage.to(torch.float64), multiplier),
    )
    applies = present & is_crown.to(device=catalog.device)
    return torch.where(applies, scaled, damage), applies


def update_damage_ramp_(
    state: TensorDamageRampState,
    catalog: TensorCombatMechanicCatalog,
    card_ids: torch.Tensor,
    observed_target_id: torch.Tensor,
    connected: torch.Tensor,
    attack_rate: torch.Tensor,
    *,
    dt_ms: int = 50,
) -> torch.Tensor:
    slot, present = catalog.mechanic_slot(card_ids, CombatMechanicOpcode.DAMAGE_RAMP)
    ids = card_ids.to(device=catalog.device, dtype=torch.int64)
    target = observed_target_id.to(device=catalog.device, dtype=torch.int64)
    connected = connected.to(device=catalog.device) & present & (target > 0)
    changed = state.target_id != target
    state.target_id.copy_(torch.where(connected, target, 0))
    next_time = torch.where(
        changed | ~connected,
        torch.zeros_like(state.target_time_ms),
        state.target_time_ms,
    )
    next_time += torch.where(
        connected,
        attack_rate.to(torch.float64).clamp_min(0) * dt_ms,
        0.0,
    )
    state.target_time_ms.copy_(next_time)
    stage_time = catalog.ramp_stage_time_ms[ids, slot]
    stage_damage = catalog.ramp_stage_damage[ids, slot]
    stage_count = catalog.ramp_stage_count[ids, slot]
    stage_index = torch.arange(stage_time.shape[-1], device=catalog.device)
    eligible = (stage_index < stage_count[..., None]) & (
        stage_time <= next_time[..., None]
    )
    chosen = eligible.to(torch.int64).sum(dim=-1).sub(1).clamp_min(0)
    damage = torch.gather(stage_damage, -1, chosen[..., None])[..., 0]
    state.damage.copy_(torch.where(present, damage, state.damage))
    return state.damage


def _distance_sq(
    world: TensorMechanicWorld, origin_x: torch.Tensor, origin_y: torch.Tensor
) -> torch.Tensor:
    dx = world.x_units.to(torch.int64) - origin_x.to(torch.int64)[:, None]
    dy = world.y_units.to(torch.int64) - origin_y.to(torch.int64)[:, None]
    return (dx * dx + dy * dy - world.distance_discount_sq_units).clamp_min(0)


def _symmetric_nearest(
    world: TensorMechanicWorld,
    valid: torch.Tensor,
    distance_sq: torch.Tensor,
    owner: torch.Tensor,
) -> torch.Tensor:
    large = torch.iinfo(torch.int64).max
    minimum = torch.where(valid, distance_sq, large).amin(dim=1)
    tied = valid & (distance_sq == minimum[:, None])
    direction = torch.where(owner == 0, 1, -1).to(torch.int64)[:, None]
    x_key = direction * (world.x_units.to(torch.int64) - 9_000)
    minimum_x = torch.where(tied, x_key, large).amin(dim=1)
    tied &= x_key == minimum_x[:, None]
    y_key = direction * (world.y_units.to(torch.int64) - 16_000)
    minimum_y = torch.where(tied, y_key, large).amin(dim=1)
    tied &= y_key == minimum_y[:, None]
    minimum_id = torch.where(tied, world.entity_id, large).amin(dim=1)
    selected = (
        (tied & (world.entity_id == minimum_id[:, None])).to(torch.int64).argmax(dim=1)
    )
    return torch.where(valid.any(dim=1), selected, torch.full_like(selected, -1))


def select_chain_targets(
    world: TensorMechanicWorld,
    *,
    owner: torch.Tensor,
    origin_x_units: torch.Tensor,
    origin_y_units: torch.Tensor,
    visited: torch.Tensor,
    chain_range_units: torch.Tensor,
    maximum_targets: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    selected_ids = torch.zeros(
        (world.batch_size, maximum_targets),
        dtype=torch.int64,
        device=world.device,
    )
    valid_output = torch.zeros_like(selected_ids, dtype=torch.bool)
    current_x = origin_x_units.clone()
    current_y = origin_y_units.clone()
    excluded = visited.clone()
    rows = torch.arange(world.batch_size, device=world.device)
    for index in range(maximum_targets):
        distance = _distance_sq(world, current_x, current_y)
        valid = (
            world.present
            & world.alive
            & world.targetable
            & world.effect_receivable
            & (world.owner != owner[:, None])
            & ~excluded
            & (distance <= chain_range_units.to(torch.int64)[:, None].square())
        )
        slot = _symmetric_nearest(world, valid, distance, owner)
        exists = slot >= 0
        safe = slot.clamp_min(0)
        selected_ids[:, index] = torch.where(exists, world.entity_id[rows, safe], 0)
        valid_output[:, index] = exists
        excluded[rows[exists], safe[exists]] = True
        current_x = torch.where(exists, world.x_units[rows, safe], current_x)
        current_y = torch.where(exists, world.y_units[rows, safe], current_y)
    return selected_ids, valid_output


def select_multiple_targets(
    world: TensorMechanicWorld,
    *,
    owner: torch.Tensor,
    origin_x_units: torch.Tensor,
    origin_y_units: torch.Tensor,
    primary_id: torch.Tensor,
    target_count: torch.Tensor,
    all_targets_hit: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    maximum = max(0, int(target_count.max().item()) - 1)
    selected = torch.zeros(
        (world.batch_size, maximum), dtype=torch.int64, device=world.device
    )
    valid = torch.zeros_like(selected, dtype=torch.bool)
    excluded = world.entity_id == primary_id[:, None]
    distance = _distance_sq(world, origin_x_units, origin_y_units)
    rows = torch.arange(world.batch_size, device=world.device)
    for index in range(maximum):
        candidates = (
            world.present
            & world.alive
            & world.targetable
            & world.effect_receivable
            & (world.owner != owner[:, None])
            & ~excluded
        )
        slot = _symmetric_nearest(world, candidates, distance, owner)
        exists = slot >= 0
        safe = slot.clamp_min(0)
        selected[:, index] = torch.where(exists, world.entity_id[rows, safe], 0)
        valid[:, index] = exists
        excluded[rows[exists], safe[exists]] = True
    needed = torch.arange(maximum, device=world.device) < (target_count - 1)[:, None]
    repeat_primary = needed & ~valid & all_targets_hit[:, None]
    selected = torch.where(repeat_primary, primary_id[:, None], selected)
    return selected, (valid | repeat_primary) & needed


def targets_in_native_area(
    world: TensorMechanicWorld,
    *,
    owner: torch.Tensor,
    center_x_units: torch.Tensor,
    center_y_units: torch.Tensor,
    radius_units: torch.Tensor,
    hits_air: torch.Tensor,
    hits_ground: torch.Tensor,
) -> torch.Tensor:
    center_x = center_x_units.to(torch.int64)[:, None]
    center_y = center_y_units.to(torch.int64)[:, None]
    radius = radius_units.to(torch.int64)[:, None]
    object_radius = world.collision_radius_units.to(torch.int64)
    dx = world.x_units.to(torch.int64) - center_x
    dy = world.y_units.to(torch.int64) - center_y
    circular = dx * dx + dy * dy < (radius + object_radius).square()
    closest_x = torch.minimum(
        world.x_units + object_radius,
        torch.maximum(world.x_units - object_radius, center_x),
    )
    closest_y = torch.minimum(
        world.y_units + object_radius,
        torch.maximum(world.y_units - object_radius, center_y),
    )
    square_dx = closest_x - center_x
    square_dy = closest_y - center_y
    square = square_dx * square_dx + square_dy * square_dy < radius.square()
    overlap = torch.where(world.building, square, circular)
    return (
        world.present
        & world.alive
        & world.effect_receivable
        & (world.owner != owner[:, None])
        & overlap
        & torch.where(world.airborne, hits_air[:, None], hits_ground[:, None])
    )


def emit_area_damage_events(
    events: TensorMechanicEvents,
    world: TensorMechanicWorld,
    *,
    source_id: torch.Tensor,
    owner: torch.Tensor,
    center_x_units: torch.Tensor,
    center_y_units: torch.Tensor,
    radius_units: torch.Tensor,
    damage: torch.Tensor,
    hits_air: torch.Tensor,
    hits_ground: torch.Tensor,
    stun_duration_ms: torch.Tensor | None = None,
    knockback_units: torch.Tensor | None = None,
    payload_opcode: int | torch.Tensor = 0,
) -> torch.Tensor:
    targets = targets_in_native_area(
        world,
        owner=owner,
        center_x_units=center_x_units,
        center_y_units=center_y_units,
        radius_units=radius_units,
        hits_air=hits_air,
        hits_ground=hits_ground,
    )
    order = torch.argsort(
        torch.where(
            targets,
            world.entity_id,
            torch.full_like(world.entity_id, torch.iinfo(torch.int64).max),
        ),
        dim=1,
        stable=True,
    )
    ordered_valid = torch.gather(targets, 1, order)
    ordered_ids = torch.gather(world.entity_id, 1, order)
    ordered_hp = torch.gather(world.hp, 1, order)
    source = source_id[:, None].expand_as(ordered_ids)
    events.append(
        valid=ordered_valid,
        opcode=MechanicEventOpcode.DAMAGE,
        source_id=source,
        target_id=ordered_ids,
        amount=damage[:, None],
        radius_units=radius_units[:, None],
        payload_opcode=payload_opcode,
    )
    if stun_duration_ms is not None:
        events.append(
            valid=ordered_valid & (ordered_hp > damage[:, None]),
            opcode=MechanicEventOpcode.STUN,
            source_id=source,
            target_id=ordered_ids,
            duration_ms=stun_duration_ms[:, None],
            radius_units=radius_units[:, None],
            payload_opcode=payload_opcode,
        )
    if knockback_units is not None:
        events.append(
            valid=(ordered_valid & (ordered_hp > damage[:, None]))
            & (knockback_units[:, None] > 0),
            opcode=MechanicEventOpcode.KNOCKBACK,
            source_id=source,
            target_id=ordered_ids,
            amount=knockback_units[:, None].to(torch.float64),
            radius_units=radius_units[:, None],
            payload_opcode=payload_opcode,
        )
    return targets


def emit_area_spawn_events(
    events: TensorMechanicEvents,
    catalog: TensorCombatMechanicCatalog,
    *,
    card_ids: torch.Tensor,
    source_id: torch.Tensor,
    trigger: CombatMechanicOpcode,
) -> torch.Tensor:
    slot, present = catalog.mechanic_slot(card_ids, trigger)
    ids = card_ids.to(device=catalog.device, dtype=torch.int64)
    opcode = (
        MechanicEventOpcode.DEATH_AREA
        if trigger == CombatMechanicOpcode.DEATH_AREA
        else MechanicEventOpcode.SPAWN_AREA
    )
    events.append(
        valid=present[:, None],
        opcode=opcode,
        source_id=source_id[:, None],
        amount=catalog.area_damage[ids, slot][:, None],
        duration_ms=catalog.area_duration_ms[ids, slot][:, None],
        radius_units=catalog.radius_units[ids, slot][:, None],
        payload_opcode=int(trigger),
    )
    return present
