"""Exact retained resolution for terminal timed-explosive area hits.

The object lifecycle deliberately ends at :class:`TensorTimedTerminalEvents`.
This module consumes that immutable queue, resolves eligible character and
building hitboxes in stable object/target-ID order, and commits a battle row
only after both terminal-payload and event-capacity preflight succeeds.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum

import torch

from clasher.battle import BattleState
from clasher.mechanics.shared.shield import Shield
from clasher.unit_traits import (
    is_airborne_target,
    is_knockback_immune,
)

from .resident_timed_terminal_payloads import TensorTimedTerminalEvents
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase
from .shield_champion import apply_shield_damage_
from .special_movement import install_radial_knockback
from .tensor_ops import scatter_any_


class TimedExplosionReason(IntEnum):
    NONE = 0
    EVENT_CAPACITY = 1
    UNSUPPORTED_DEATH_PAYLOAD = 2


@dataclass
class TensorTimedExplosionTargets:
    """Dynamic target traits not retained by ``TensorBattleState`` itself.

    ``area_receivable`` and ``knockback_receivable`` are event-specific because
    both oracle predicates accept the serialized source kind.  The remaining
    planes are canonical-slot state and can be retained across ticks.
    """

    collision_radius_units: torch.Tensor
    airborne: torch.Tensor
    building: torch.Tensor
    area_receivable: torch.Tensor
    knockback_receivable: torch.Tensor
    knockback_immune: torch.Tensor
    has_shield: torch.Tensor
    shield_current: torch.Tensor
    shield_break_count: torch.Tensor
    death_payload_supported: torch.Tensor

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        terminal: TensorTimedTerminalEvents,
        *,
        source_kinds: Sequence[str | None],
    ) -> TensorTimedExplosionTargets:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match runtime batch")
        if len(source_kinds) != int(terminal.batch_index.numel()):
            raise ValueError("source_kinds must align with terminal events")
        device = runtime.device
        shape = runtime.battle.entity_id.shape
        event_shape = (len(source_kinds), runtime.max_entities)
        collision = torch.zeros(shape, dtype=torch.int64, device=device)
        airborne = torch.zeros(shape, dtype=torch.bool, device=device)
        building = runtime.battle.entity_kind == 1
        area = torch.zeros(event_shape, dtype=torch.bool, device=device)
        knockback = torch.zeros(event_shape, dtype=torch.bool, device=device)
        immune = torch.zeros(shape, dtype=torch.bool, device=device)
        has_shield = torch.zeros(shape, dtype=torch.bool, device=device)
        shield_current = torch.zeros(shape, dtype=torch.float64, device=device)
        shield_break_count = torch.zeros(shape, dtype=torch.int32, device=device)
        death_supported = torch.ones(shape, dtype=torch.bool, device=device)

        event_rows: dict[int, list[int]] = {}
        for event_index, batch_index in enumerate(terminal.batch_index.tolist()):
            event_rows.setdefault(int(batch_index), []).append(event_index)
        for batch_index, battle in enumerate(battles):
            slots = {
                int(entity_id): slot
                for slot, entity_id in enumerate(
                    runtime.battle.entity_id[batch_index].tolist()
                )
                if entity_id
            }
            if set(slots) != set(battle.entities):
                raise ValueError("runtime/oracle entity identity sets differ")
            for entity_id, entity in battle.entities.items():
                slot = slots[entity_id]
                index = (batch_index, slot)
                collision[index] = round(entity.get_collision_radius() * 1_000)
                airborne[index] = is_airborne_target(entity)
                immune[index] = is_knockback_immune(entity.card_stats)
                shield_mechanics = [
                    mechanic
                    for mechanic in entity.mechanics
                    if isinstance(mechanic, Shield)
                ]
                if len(shield_mechanics) > 1:
                    raise ValueError("multiple shields are not representable")
                if shield_mechanics:
                    has_shield[index] = True
                    shield_current[index] = float(shield_mechanics[0].current_shield)
                shield_break_count[index] = int(
                    getattr(entity, "_shield_break_count", 0)
                )
                serialized_terminal = any(
                    type(mechanic).__name__
                    in {"DeathDamage", "DeathSpawn", "DeathAreaEffect"}
                    for mechanic in entity.mechanics
                ) or bool(getattr(entity.card_stats, "death_spawn_character", None))
                death_supported[index] = not serialized_terminal
                for event_index in event_rows.get(batch_index, []):
                    source_kind = source_kinds[event_index]
                    area[event_index, slot] = entity.can_receive_area_damage(
                        source_kind
                    )
                    knockback[event_index, slot] = entity.can_receive_forced_movement(
                        source_kind, "knockback"
                    )
        return cls(
            collision,
            airborne,
            building,
            area,
            knockback,
            immune,
            has_shield,
            shield_current,
            shield_break_count,
            death_supported,
        )


@dataclass(frozen=True)
class TensorTimedKnockbackDescriptors:
    valid: torch.Tensor
    source_id: torch.Tensor
    target_id: torch.Tensor
    target_slot: torch.Tensor
    origin_units: torch.Tensor
    distance_units: torch.Tensor
    target_units: torch.Tensor
    velocity_work: torch.Tensor


@dataclass(frozen=True)
class TimedExplosionResult:
    committed: torch.Tensor
    reason: torch.Tensor
    hit: torch.Tensor
    hitpoint_damage: torch.Tensor
    died: torch.Tensor
    shield_absorbed: torch.Tensor
    shield_broken: torch.Tensor
    knockback: TensorTimedKnockbackDescriptors


def _validate(
    runtime: TensorBattleRuntime,
    terminal: TensorTimedTerminalEvents,
    targets: TensorTimedExplosionTargets,
) -> None:
    entity_shape = runtime.battle.entity_id.shape
    event_shape = (terminal.batch_index.numel(), runtime.max_entities)
    for name in (
        "collision_radius_units",
        "airborne",
        "building",
        "knockback_immune",
        "has_shield",
        "shield_current",
        "shield_break_count",
        "death_payload_supported",
    ):
        value = getattr(targets, name)
        if value.shape != entity_shape or value.device != runtime.device:
            raise ValueError(f"{name} must align with runtime entities")
    for name in ("area_receivable", "knockback_receivable"):
        value = getattr(targets, name)
        if value.shape != event_shape or value.device != runtime.device:
            raise ValueError(f"{name} must align with terminal events and entities")
    for name in terminal.__dataclass_fields__:
        if getattr(terminal, name).device != runtime.device:
            raise ValueError("terminal events and runtime must share a device")


def _native_overlap(
    terminal: TensorTimedTerminalEvents,
    runtime: TensorBattleRuntime,
    targets: TensorTimedExplosionTargets,
) -> torch.Tensor:
    x = runtime.battle.entity_x_units.to(torch.int64)[None, :, :]
    y = runtime.battle.entity_y_units.to(torch.int64)[None, :, :]
    rows = terminal.batch_index.to(torch.int64)
    x = x[0, rows]
    y = y[0, rows]
    radius = terminal.radius_units.to(torch.int64)[:, None].clamp_min(0)
    object_radius = targets.collision_radius_units[rows].to(torch.int64).clamp_min(0)
    center_x = terminal.x_units.to(torch.int64)[:, None]
    center_y = terminal.y_units.to(torch.int64)[:, None]
    dx = x - center_x
    dy = y - center_y
    circular = dx.square() + dy.square() < (radius + object_radius).square()
    closest_x = torch.minimum(
        x + object_radius, torch.maximum(x - object_radius, center_x)
    )
    closest_y = torch.minimum(
        y + object_radius, torch.maximum(y - object_radius, center_y)
    )
    square = (closest_x - center_x).square() + (
        closest_y - center_y
    ).square() < radius.square()
    return torch.where(targets.building[rows], square, circular)


def resolve_timed_terminal_explosions_(
    runtime: TensorBattleRuntime,
    terminal: TensorTimedTerminalEvents,
    targets: TensorTimedExplosionTargets,
    *,
    hits_air: torch.Tensor | bool = True,
    hits_ground: torch.Tensor | bool = True,
) -> TimedExplosionResult:
    """Resolve terminal explosions transactionally in stable ID order."""

    _validate(runtime, terminal, targets)
    batch = runtime.batch_size
    count = runtime.max_entities
    event_count = int(terminal.batch_index.numel())
    lane_width = event_count * count
    device = runtime.device
    empty_bool = torch.zeros((batch, lane_width), dtype=torch.bool, device=device)
    empty_float = torch.zeros((batch, lane_width), dtype=torch.float64, device=device)
    empty_long = torch.zeros((batch, lane_width), dtype=torch.int64, device=device)
    if event_count == 0:
        knockback = TensorTimedKnockbackDescriptors(
            empty_bool,
            empty_long,
            empty_long,
            empty_long,
            torch.zeros((batch, 0, 2), dtype=torch.int64, device=device),
            empty_long,
            torch.zeros((batch, 0, 2), dtype=torch.int64, device=device),
            empty_long,
        )
        return TimedExplosionResult(
            runtime.supported.clone(),
            torch.zeros(batch, dtype=torch.int16, device=device),
            empty_bool,
            empty_float,
            empty_bool,
            empty_bool,
            empty_bool,
            knockback,
        )

    rows = terminal.batch_index.to(torch.int64)
    kind = runtime.battle.entity_kind[rows]
    owner = runtime.battle.entity_player[rows]
    active = runtime.entity_pool.active[rows] & runtime.battle.entity_active[rows]
    air = torch.as_tensor(hits_air, dtype=torch.bool, device=device)
    ground = torch.as_tensor(hits_ground, dtype=torch.bool, device=device)
    air = torch.broadcast_to(air, (event_count,))[:, None]
    ground = torch.broadcast_to(ground, (event_count,))[:, None]
    plane = torch.where(targets.airborne[rows], air, ground)
    eligible = (
        active
        & ((kind == 0) | (kind == 1))
        & (owner != terminal.player[:, None])
        & targets.area_receivable
        & plane
        & _native_overlap(terminal, runtime, targets)
    )

    event_index = torch.arange(event_count, device=device)[:, None].expand(-1, count)
    target_slot = torch.arange(count, device=device)[None, :].expand(event_count, -1)
    flat_event = event_index.flatten()
    flat_slot = target_slot.flatten()
    flat_rows = rows[flat_event]
    flat_valid = eligible.flatten()
    flat_source = terminal.object_id[flat_event]
    flat_target = runtime.battle.entity_id[flat_rows, flat_slot]
    max_id = torch.maximum(flat_source, flat_target).amax().to(torch.int64) + 2
    lane = torch.arange(lane_width, device=device, dtype=torch.int64)
    key = (flat_source * max_id + flat_target) * (lane_width + 1) + lane
    row_grid = torch.arange(batch, device=device)[:, None]
    same_row = flat_rows[None, :] == row_grid
    padded_valid = same_row & flat_valid[None, :]
    padded_key = torch.where(
        padded_valid,
        key[None, :],
        torch.full((batch, lane_width), torch.iinfo(torch.int64).max, device=device),
    )
    order = torch.argsort(padded_key, dim=1, stable=True)
    ordered_valid = padded_valid.gather(1, order)
    ordered_event = flat_event[order]
    ordered_slot = flat_slot[order]
    ordered_source = flat_source[order]
    ordered_target = flat_target[order]

    hp = runtime.battle.entity_hp.clone()
    alive = runtime.battle.entity_active.clone()
    shield = targets.shield_current.clone()
    break_count = targets.shield_break_count.clone()
    hp_damage = torch.zeros_like(empty_float)
    died = torch.zeros_like(empty_bool)
    absorbed = torch.zeros_like(empty_bool)
    broken = torch.zeros_like(empty_bool)
    effective_hit = torch.zeros_like(empty_bool)
    rows_all = torch.arange(batch, device=device)
    for lane_index in range(lane_width):
        slot = ordered_slot[:, lane_index]
        source_event = ordered_event[:, lane_index]
        valid = ordered_valid[:, lane_index] & alive[rows_all, slot]
        damage = torch.where(
            valid,
            terminal.damage[source_event],
            torch.zeros(batch, dtype=torch.float64, device=device),
        )
        prior_shield = shield[rows_all, slot]
        lane_count = break_count[rows_all, slot]
        has_shield = targets.has_shield[rows_all, slot] & valid
        result = apply_shield_damage_(prior_shield, lane_count, damage, has_shield)
        shield[rows_all, slot] = prior_shield
        break_count[rows_all, slot] = lane_count
        before = hp[rows_all, slot]
        after = torch.clamp(before - result.hitpoint_damage, min=0.0)
        hp[rows_all, slot] = torch.where(valid, after, before)
        lane_died = valid & alive[rows_all, slot] & (after <= 0.0)
        alive[rows_all, slot] &= ~lane_died
        effective_hit[:, lane_index] = valid & (damage > 0)
        hp_damage[:, lane_index] = torch.where(valid, before - after, 0.0)
        died[:, lane_index] = lane_died
        absorbed[:, lane_index] = valid & has_shield & (result.hitpoint_damage <= 0)
        broken[:, lane_index] = valid & result.shield_broken

    unsupported_death = torch.zeros(batch, dtype=torch.bool, device=device)
    scatter_any_(
        unsupported_death,
        0,
        row_grid.expand_as(died)[died],
        (
            ~targets.death_payload_supported[
                row_grid.expand_as(ordered_slot), ordered_slot
            ]
        )[died],
    )
    additions = effective_hit.sum(dim=1, dtype=torch.int64) + died.sum(
        dim=1, dtype=torch.int64
    )
    overflow = (
        runtime.events.count.to(torch.int64) + additions > runtime.events.capacity
    )
    committed = runtime.supported & ~unsupported_death & ~overflow
    reason = torch.where(
        unsupported_death,
        int(TimedExplosionReason.UNSUPPORTED_DEATH_PAYLOAD),
        torch.where(overflow, int(TimedExplosionReason.EVENT_CAPACITY), 0),
    ).to(torch.int16)
    runtime.battle.entity_hp.copy_(
        torch.where(committed[:, None], hp, runtime.battle.entity_hp)
    )
    runtime.battle.entity_active.copy_(
        torch.where(committed[:, None], alive, runtime.battle.entity_active)
    )
    runtime.phases.death_pending |= committed[:, None] & ~alive
    targets.shield_current.copy_(
        torch.where(committed[:, None], shield, targets.shield_current)
    )
    targets.shield_break_count.copy_(
        torch.where(committed[:, None], break_count, targets.shield_break_count)
    )

    event_valid = (
        torch.stack((effective_hit, died), dim=2).flatten(1) & committed[:, None]
    )
    opcode = torch.stack(
        (
            torch.full_like(ordered_target, int(RuntimeEventOpcode.DAMAGE)),
            torch.full_like(ordered_target, int(RuntimeEventOpcode.DEATH)),
        ),
        dim=2,
    ).flatten(1)
    source_ids = torch.stack((ordered_source, ordered_source), dim=2).flatten(1)
    target_ids = torch.stack((ordered_target, ordered_target), dim=2).flatten(1)
    amounts = torch.stack((hp_damage, torch.zeros_like(hp_damage)), dim=2).flatten(1)
    slots = torch.stack((ordered_slot, ordered_slot), dim=2).flatten(1)
    x = runtime.battle.entity_x_units.gather(1, slots)
    y = runtime.battle.entity_y_units.gather(1, slots)
    runtime.events.append(
        phase=TickPhase.OBJECTS,
        opcode=opcode,
        valid=event_valid,
        source_id=source_ids,
        target_id=target_ids,
        x_units=x,
        y_units=y,
        amount=amounts,
    )

    event_rows = rows[ordered_event]
    position = torch.stack(
        (
            runtime.battle.entity_x_units.gather(1, ordered_slot),
            runtime.battle.entity_y_units.gather(1, ordered_slot),
        ),
        dim=2,
    ).to(torch.int64)
    origin = torch.stack(
        (terminal.x_units[ordered_event], terminal.y_units[ordered_event]), dim=2
    ).to(torch.int64)
    distance = terminal.knockback_units[ordered_event].to(torch.int64)
    knock_eligible = (
        effective_hit
        & ~died
        & (distance > 0)
        & ~targets.building[row_grid.expand_as(ordered_slot), ordered_slot]
        & ~targets.knockback_immune[row_grid.expand_as(ordered_slot), ordered_slot]
        & targets.knockback_receivable[ordered_event, ordered_slot]
        & committed[:, None]
        & (event_rows == row_grid)
    )
    install = install_radial_knockback(
        position,
        origin,
        distance,
        player_id=runtime.battle.entity_player.gather(1, ordered_slot),
        eligible=knock_eligible,
    )
    runtime.mark_dirty(committed & effective_hit.any(dim=1), phase=TickPhase.OBJECTS)
    knockback_result = TensorTimedKnockbackDescriptors(
        knock_eligible,
        ordered_source,
        ordered_target,
        ordered_slot,
        origin,
        distance,
        install.target_units,
        install.velocity_work,
    )
    return TimedExplosionResult(
        committed,
        reason,
        effective_hit,
        hp_damage,
        died,
        absorbed,
        broken,
        knockback_result,
    )


__all__ = [
    "TensorTimedExplosionTargets",
    "TensorTimedKnockbackDescriptors",
    "TimedExplosionReason",
    "TimedExplosionResult",
    "resolve_timed_terminal_explosions_",
]
