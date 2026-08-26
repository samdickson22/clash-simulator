"""Data-driven attack and spell command allocation for the fast Gym.

This module is the seam between combat/action selection and the fixed effect
pool.  It performs no card-name dispatch: all behavior is selected by tensors
compiled in :mod:`simple_catalog`.  Direct hits are represented as immediate
zero-radius area effects so the existing grouped-damage kernel remains the
single HP mutation path.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch
from torch.nn import functional

from .simple_catalog import (
    FAST_CARD_EFFECT_AREA,
    FAST_CARD_EFFECT_DIRECT,
    FAST_CARD_EFFECT_PROJECTILE,
    FastCardCatalog,
)
from .simple_effects import FAST_EFFECT_AREA, FAST_EFFECT_PROJECTILE, FastEffectState
from .simple_state import FastGymState


@dataclass(frozen=True)
class FastEffectCommands:
    """Fixed-shape ready attacks and spell casts with shape ``[B, C]``.

    Entity attacks provide a positive ``source_id``. Spell casts use zero and
    supply their launch position explicitly. Area effects may use target ID
    zero; direct and homing projectile primitives fail closed without a live
    target. Coordinates are absolute-world logic units.
    """

    ready: torch.Tensor
    source_id: torch.Tensor
    owner: torch.Tensor
    card_id: torch.Tensor
    source_x_units: torch.Tensor
    source_y_units: torch.Tensor
    target_id: torch.Tensor
    target_x_units: torch.Tensor
    target_y_units: torch.Tensor
    damage_multiplier: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.ready.shape[0])

    @property
    def command_count(self) -> int:
        return int(self.ready.shape[1])


@dataclass(frozen=True)
class FastEffectAllocationResult:
    """Per-command allocation telemetry, retained entirely on device."""

    accepted: torch.Tensor
    unsupported: torch.Tensor
    invalid_source: torch.Tensor
    invalid_target: torch.Tensor
    capacity_rejected: torch.Tensor
    effect_slot: torch.Tensor
    direct: torch.Tensor
    projectile: torch.Tensor
    area: torch.Tensor


def _validate(
    state: FastGymState,
    effects: FastEffectState,
    consume_source_id: torch.Tensor,
    catalog: FastCardCatalog,
    commands: FastEffectCommands,
) -> None:
    if effects.device != state.device or catalog.device != state.device:
        raise ValueError("state, effects, and catalog must use the same device")
    if effects.batch_size != state.batch_size:
        raise ValueError("state and effects must use the same batch size")
    if commands.ready.ndim != 2 or commands.batch_size != state.batch_size:
        raise ValueError("command tensors must have shape [batch, commands]")
    shape = tuple(commands.ready.shape)
    for descriptor in fields(commands):
        value = getattr(commands, descriptor.name)
        if tuple(value.shape) != shape:
            raise ValueError(f"{descriptor.name} must have shape [batch, commands]")
        if value.device != state.device:
            raise ValueError(f"{descriptor.name} is on a different device")
    if commands.ready.dtype != torch.bool:
        raise ValueError("ready must be bool")
    if commands.source_id.dtype != torch.int64:
        raise ValueError("source_id must be int64")
    if commands.card_id.dtype != torch.int64:
        raise ValueError("card_id must be int64")
    if commands.target_id.dtype != torch.int64:
        raise ValueError("target_id must be int64")
    if commands.damage_multiplier.dtype != torch.float32:
        raise ValueError("damage_multiplier must be float32")
    expected_pool = (state.batch_size, effects.max_effects)
    if tuple(consume_source_id.shape) != expected_pool:
        raise ValueError("consume_source_id must have shape [batch, effects]")
    if (
        consume_source_id.device != state.device
        or consume_source_id.dtype != torch.int64
    ):
        raise ValueError("consume_source_id must be int64 on the state device")


def allocate_fast_attack_effects_(
    state: FastGymState,
    effects: FastEffectState,
    consume_source_id: torch.Tensor,
    catalog: FastCardCatalog,
    commands: FastEffectCommands,
) -> FastEffectAllocationResult:
    """Allocate every supported ready command into deterministic low slots.

    Allocation is simultaneous and stable in command order. Existing effects
    are never overwritten. Tower scaling remains an effect field so the impact
    kernel can apply it independently to every Crown Tower in splash range.
    The hot path contains no host synchronization or dynamic compaction.
    """

    _validate(state, effects, consume_source_id, catalog, commands)
    batch = commands.ready.shape[0]
    max_effects = effects.max_effects

    known_card = (commands.card_id > 0) & (commands.card_id < catalog.size)
    safe_card = commands.card_id.clamp(0, catalog.size - 1)
    primitive = catalog.effect_kind[safe_card]
    direct = primitive == FAST_CARD_EFFECT_DIRECT
    projectile = primitive == FAST_CARD_EFFECT_PROJECTILE
    area = primitive == FAST_CARD_EFFECT_AREA
    supported = (
        known_card
        & (primitive >= 0)
        & (~projectile | (catalog.projectile_speed_units_per_tick[safe_card] > 0))
    )

    source_match = (
        state.active[:, None, :]
        & (state.hp[:, None, :] > 0)
        & (commands.source_id[:, :, None] > 0)
        & (commands.source_id[:, :, None] == state.stable_id[:, None, :])
    )
    source_found = source_match.any(dim=2)
    source_slot = source_match.to(torch.int8).argmax(dim=2).to(torch.int64)
    source_card = state.card_id.gather(1, source_slot)
    source_owner = state.owner.gather(1, source_slot).to(torch.int64)
    entity_command = commands.source_id > 0
    valid_entity_source = (
        source_found
        & (source_card == commands.card_id)
        & (source_owner == commands.owner.to(torch.int64))
    )
    valid_source = torch.where(entity_command, valid_entity_source, True)
    source_x = torch.where(
        entity_command,
        state.x_units.gather(1, source_slot),
        commands.source_x_units.to(torch.int32),
    )
    source_y = torch.where(
        entity_command,
        state.y_units.gather(1, source_slot),
        commands.source_y_units.to(torch.int32),
    )

    target_match = (
        state.active[:, None, :]
        & (state.hp[:, None, :] > 0)
        & (commands.target_id[:, :, None] > 0)
        & (commands.target_id[:, :, None] == state.stable_id[:, None, :])
    )
    target_found = target_match.any(dim=2)
    target_slot = target_match.to(torch.int8).argmax(dim=2).to(torch.int64)
    target_x = torch.where(
        target_found,
        state.x_units.gather(1, target_slot),
        commands.target_x_units.to(torch.int32),
    )
    target_y = torch.where(
        target_found,
        state.y_units.gather(1, target_slot),
        commands.target_y_units.to(torch.int32),
    )
    requires_entity_target = direct | (projectile & entity_command)
    valid_target = ~requires_entity_target | target_found

    candidate = (
        commands.ready
        & supported
        & valid_source
        & valid_target
        & (commands.owner >= 0)
        & (commands.owner < 2)
        & ~state.game_over[:, None]
    )
    free = ~effects.active
    slots = torch.arange(max_effects, dtype=torch.int64, device=state.device)
    free_slots = (
        torch.where(
            free,
            slots.view(1, -1),
            torch.full(
                (batch, max_effects),
                max_effects,
                dtype=torch.int64,
                device=state.device,
            ),
        )
        .sort(dim=1)
        .values
    )
    command_rank = candidate.to(torch.int64).cumsum(dim=1) - 1
    available = free.sum(dim=1, dtype=torch.int64)
    accepted = candidate & (command_rank < available[:, None])
    safe_rank = command_rank.clamp(0, max_effects - 1)
    allocated_slot = free_slots.gather(1, safe_rank)
    effect_slot = torch.where(accepted, allocated_slot, -1)

    destination = (
        functional.one_hot(effect_slot.clamp(min=0), num_classes=max_effects).to(
            torch.bool
        )
        & accepted[:, :, None]
    )
    written = destination.any(dim=1)

    def write(field: torch.Tensor, value: torch.Tensor) -> None:
        expanded = value[:, :, None].expand(-1, -1, max_effects)
        selected = torch.where(destination, expanded, 0).sum(dim=1).to(field.dtype)
        field.copy_(torch.where(written, selected, field))

    effect_kind = torch.where(projectile, FAST_EFFECT_PROJECTILE, FAST_EFFECT_AREA)
    center_on_source = catalog.effect_center_on_source[safe_card]
    line_range = catalog.line_range_units[safe_card]
    line = line_range > 0
    aim_dx = target_x.to(torch.float32) - source_x.to(torch.float32)
    aim_dy = target_y.to(torch.float32) - source_y.to(torch.float32)
    aim_distance = torch.sqrt(aim_dx.square() + aim_dy.square())
    aim_denominator = aim_distance.clamp_min(1.0)
    line_target_x = source_x + torch.round(
        aim_dx * line_range.to(torch.float32) / aim_denominator
    ).to(torch.int32)
    line_target_y = source_y + torch.round(
        aim_dy * line_range.to(torch.float32) / aim_denominator
    ).to(torch.int32)
    target_x = torch.where(line, line_target_x, target_x)
    target_y = torch.where(line, line_target_y, target_y)
    effect_x = torch.where(
        projectile | center_on_source,
        source_x,
        target_x,
    )
    effect_y = torch.where(
        projectile | center_on_source,
        source_y,
        target_y,
    )
    # Charge, continuous-target ramp, and future numeric modifiers are
    # composed by the runtime into this one plane.  Allocation still writes a
    # single effect payload, leaving HP mutation exclusively to the effect
    # kernel rather than adding a mechanic-specific damage path.
    damage_multiplier = torch.nan_to_num(
        commands.damage_multiplier,
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    ).clamp(min=0.0)
    damage = catalog.effect_damage[safe_card] * damage_multiplier
    dx = target_x.to(torch.float32) - source_x.to(torch.float32)
    dy = target_y.to(torch.float32) - source_y.to(torch.float32)
    distance = torch.sqrt(dx.square() + dy.square())
    speed = catalog.projectile_speed_units_per_tick[safe_card].clamp(min=1)
    projectile_lifetime = (
        torch.ceil(distance / speed.to(torch.float32)).to(torch.int32) + 1
    ).clamp(min=1)
    lifetime = torch.where(projectile, projectile_lifetime, 1)
    consumed = torch.where(
        entity_command & catalog.consume_source_on_impact[safe_card],
        commands.source_id,
        0,
    )

    write(effects.active, torch.ones_like(commands.ready))
    write(effects.kind, effect_kind)
    write(effects.source_owner, commands.owner)
    write(effects.source_card_id, commands.card_id)
    write(effects.source_x_units, source_x)
    write(effects.source_y_units, source_y)
    write(effects.x_units, effect_x)
    write(effects.y_units, effect_y)
    tracked_projectile = projectile & entity_command & ~line
    write(
        effects.target_id,
        torch.where(entity_command, commands.target_id, 0),
    )
    write(effects.target_x_units, target_x)
    write(effects.target_y_units, target_y)
    write(effects.tracks_target, tracked_projectile)
    write(
        effects.speed_units_per_tick,
        torch.where(
            projectile,
            catalog.projectile_speed_units_per_tick[safe_card],
            0,
        ),
    )
    write(effects.damage, damage)
    write(
        effects.tower_damage_multiplier,
        catalog.tower_damage_multiplier[safe_card],
    )
    write(
        effects.building_damage_multiplier,
        catalog.building_damage_multiplier[safe_card],
    )
    write(effects.radius_units, catalog.effect_radius_units[safe_card])
    write(effects.status_kind, catalog.status_kind[safe_card])
    write(effects.status_duration_ticks, catalog.status_duration_ticks[safe_card])
    write(
        effects.lifetime_ticks,
        torch.where(projectile, lifetime, catalog.effect_duration_ticks[safe_card]),
    )
    write(effects.damage_interval_ticks, catalog.damage_interval_ticks[safe_card])
    write(effects.next_damage_tick, catalog.initial_damage_delay_ticks[safe_card])
    write(effects.damage_on_spawn, catalog.damage_on_spawn[safe_card])
    write(effects.damage_hits_remaining, catalog.max_damage_hits[safe_card])
    write(effects.status_interval_ticks, catalog.status_interval_ticks[safe_card])
    write(effects.next_status_tick, catalog.initial_status_delay_ticks[safe_card])
    write(effects.status_scans_remaining, catalog.max_status_scans[safe_card])
    write(effects.hits_air, catalog.hits_air[safe_card])
    write(effects.hits_ground, catalog.hits_ground[safe_card])
    write(effects.multi_target_count, catalog.multi_target_count[safe_card])
    write(effects.multi_target_range_units, catalog.range_units[safe_card])
    write(effects.multi_repeat_primary, catalog.multi_repeat_primary[safe_card])
    write(effects.chain_target_count, catalog.chain_target_count[safe_card])
    write(effects.chain_hop_radius_units, catalog.chain_hop_radius_units[safe_card])
    write(effects.line_range_units, line_range)
    write(
        effects.line_half_width_units,
        catalog.line_half_width_units[safe_card],
    )
    write(effects.fan_ray_count, catalog.fan_ray_count[safe_card])
    write(effects.fan_range_units, catalog.fan_range_units[safe_card])
    write(effects.fan_radius_units, catalog.fan_radius_units[safe_card])
    write(effects.fan_spread_degrees, catalog.fan_spread_degrees[safe_card])
    write(consume_source_id, consumed)

    return FastEffectAllocationResult(
        accepted=accepted,
        unsupported=commands.ready & ~supported,
        invalid_source=commands.ready & supported & ~valid_source,
        invalid_target=commands.ready & supported & valid_source & ~valid_target,
        capacity_rejected=candidate & ~accepted,
        effect_slot=effect_slot,
        direct=commands.ready & supported & direct,
        projectile=commands.ready & supported & projectile,
        area=commands.ready & supported & area,
    )
