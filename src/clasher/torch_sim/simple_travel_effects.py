"""Allocate special-travel impacts into the shared dense effect pool.

Travel profiles already carry calibrated numeric damage, so this adapter does
not reinterpret the producing card's ordinary attack. Direct and area impacts
become one-tick ``FastEffectState`` entries; ``step_fast_effects`` remains the
only HP mutation authority.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from .simple_effects import FAST_EFFECT_AREA, FastEffectState
from .simple_state import FastGymState
from .simple_travel import (
    FAST_TRAVEL_IMPACT_AREA,
    FAST_TRAVEL_IMPACT_DIRECT,
    FastTravelImpactCommands,
)


@dataclass(frozen=True)
class FastTravelEffectAllocationResult:
    """Per-command admission and capacity telemetry on the runtime device."""

    accepted: torch.Tensor
    invalid: torch.Tensor
    capacity_rejected: torch.Tensor
    effect_slot: torch.Tensor
    direct: torch.Tensor
    area: torch.Tensor


def allocate_fast_travel_effects_(
    state: FastGymState,
    effects: FastEffectState,
    consume_source_id: torch.Tensor,
    commands: FastTravelImpactCommands,
) -> FastTravelEffectAllocationResult:
    """Materialize calibrated travel impacts as ordinary one-tick effects."""

    shape = tuple(commands.valid.shape)
    if len(shape) != 2 or shape[0] != state.batch_size:
        raise ValueError("travel effect commands must have shape [batch, commands]")
    if effects.device != state.device or effects.batch_size != state.batch_size:
        raise ValueError("state and effects must share batch size and device")
    dtypes = (
        ("valid", torch.bool),
        ("kind", torch.int8),
        ("source_stable_id", torch.int64),
        ("source_card_id", torch.int64),
        ("source_owner", torch.int8),
        ("target_stable_id", torch.int64),
        ("center_x_units", torch.int32),
        ("center_y_units", torch.int32),
        ("damage", torch.float32),
        ("tower_damage", torch.float32),
        ("radius_units", torch.int32),
        ("push_units", torch.int32),
        ("hits_air", torch.bool),
        ("hits_ground", torch.bool),
        ("spawn_impact", torch.bool),
    )
    for name, dtype in dtypes:
        value = getattr(commands, name)
        if tuple(value.shape) != shape or value.device != state.device:
            raise ValueError(f"{name} must match command shape and device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    pool_shape = (state.batch_size, effects.max_effects)
    if tuple(consume_source_id.shape) != pool_shape:
        raise ValueError("consume_source_id must have shape [batch, effects]")
    if (
        consume_source_id.device != state.device
        or consume_source_id.dtype != torch.int64
    ):
        raise ValueError("consume_source_id must be int64 on the state device")

    direct = commands.kind == FAST_TRAVEL_IMPACT_DIRECT
    area = commands.kind == FAST_TRAVEL_IMPACT_AREA
    source_match = (
        state.active[:, None, :]
        & (state.hp[:, None, :] > 0)
        & (commands.source_stable_id[:, :, None] > 0)
        & (
            commands.source_stable_id[:, :, None]
            == state.stable_id[:, None, :]
        )
        & (commands.source_card_id[:, :, None] == state.card_id[:, None, :])
        & (
            commands.source_owner[:, :, None].to(torch.int64)
            == state.owner[:, None, :].to(torch.int64)
        )
    )
    target_match = (
        state.active[:, None, :]
        & (state.hp[:, None, :] > 0)
        & (commands.target_stable_id[:, :, None] > 0)
        & (
            commands.target_stable_id[:, :, None]
            == state.stable_id[:, None, :]
        )
    )
    valid = (
        commands.valid
        & (direct | area)
        & source_match.any(dim=2)
        & (~direct | target_match.any(dim=2))
        & (commands.source_card_id > 0)
        & (commands.source_owner >= 0)
        & (commands.source_owner < 2)
        & torch.isfinite(commands.damage)
        & (commands.damage > 0)
        & torch.isfinite(commands.tower_damage)
        & (commands.tower_damage >= 0)
        & (commands.radius_units >= 0)
        & (~direct | (commands.radius_units == 0))
        & (~area | (commands.radius_units > 0))
        & ~state.game_over[:, None]
    )
    free = ~effects.active
    command_rank = valid.to(torch.int64).cumsum(dim=1) - 1
    free_rank = free.to(torch.int64).cumsum(dim=1) - 1
    available = free.sum(dim=1, dtype=torch.int64)
    accepted = valid & (command_rank < available[:, None])
    allocated = free & (free_rank < accepted.sum(dim=1, dtype=torch.int64)[:, None])
    claims = (
        allocated[:, :, None]
        & accepted[:, None, :]
        & (free_rank[:, :, None] == command_rank[:, None, :])
    )
    source_command = claims.to(torch.int64).argmax(dim=2)
    effect_slot = torch.where(
        accepted,
        (accepted[:, :, None] & claims.transpose(1, 2))
        .to(torch.int64)
        .argmax(dim=2),
        -1,
    )

    def gather(value: torch.Tensor) -> torch.Tensor:
        return value.gather(1, source_command)

    def write(field: torch.Tensor, value: torch.Tensor) -> None:
        field.copy_(torch.where(allocated, value.to(field.dtype), field))

    zeros_i64 = torch.zeros_like(free_rank)
    zeros_i32 = torch.zeros_like(free_rank, dtype=torch.int32)
    zeros_i16 = torch.zeros_like(free_rank, dtype=torch.int16)
    zeros_f32 = torch.zeros_like(free_rank, dtype=torch.float32)
    ones_i32 = torch.ones_like(free_rank, dtype=torch.int32)
    ones_i16 = torch.ones_like(free_rank, dtype=torch.int16)
    selected_direct = gather(direct)
    tower_multiplier = gather(commands.tower_damage) / gather(
        commands.damage
    ).clamp_min(torch.finfo(torch.float32).tiny)
    write(effects.active, torch.ones_like(allocated))
    write(effects.kind, torch.full_like(free_rank, FAST_EFFECT_AREA))
    write(effects.source_owner, gather(commands.source_owner))
    write(effects.source_card_id, gather(commands.source_card_id))
    write(effects.source_x_units, gather(commands.center_x_units))
    write(effects.source_y_units, gather(commands.center_y_units))
    write(effects.x_units, gather(commands.center_x_units))
    write(effects.y_units, gather(commands.center_y_units))
    write(
        effects.target_id,
        torch.where(selected_direct, gather(commands.target_stable_id), zeros_i64),
    )
    write(effects.target_x_units, gather(commands.center_x_units))
    write(effects.target_y_units, gather(commands.center_y_units))
    write(effects.tracks_target, torch.zeros_like(allocated))
    write(effects.speed_units_per_tick, zeros_i32)
    write(effects.damage, gather(commands.damage))
    write(effects.tower_damage_multiplier, tower_multiplier)
    write(effects.building_damage_multiplier, torch.ones_like(tower_multiplier))
    write(effects.radius_units, gather(commands.radius_units))
    write(effects.status_kind, torch.zeros_like(free_rank, dtype=torch.int8))
    write(effects.status_duration_ticks, zeros_i32)
    write(effects.lifetime_ticks, ones_i32)
    write(effects.damage_interval_ticks, ones_i32)
    write(effects.next_damage_tick, zeros_i32)
    write(effects.damage_on_spawn, torch.ones_like(allocated))
    write(effects.damage_hits_remaining, ones_i32)
    write(effects.status_interval_ticks, ones_i32)
    write(effects.next_status_tick, zeros_i32)
    write(effects.status_scans_remaining, zeros_i32)
    write(effects.hits_air, gather(commands.hits_air))
    write(effects.hits_ground, gather(commands.hits_ground))
    write(effects.affects_hidden, torch.zeros_like(allocated))
    write(effects.multi_target_count, ones_i16)
    write(effects.multi_target_range_units, zeros_i32)
    write(effects.multi_repeat_primary, torch.zeros_like(allocated))
    write(effects.chain_target_count, zeros_i16)
    write(effects.chain_hop_radius_units, zeros_i32)
    write(effects.line_range_units, zeros_i32)
    write(effects.line_half_width_units, zeros_i32)
    write(effects.fan_ray_count, zeros_i16)
    write(effects.fan_range_units, zeros_i32)
    write(effects.fan_radius_units, zeros_i32)
    write(effects.fan_spread_degrees, zeros_f32)
    write(consume_source_id, zeros_i64)
    return FastTravelEffectAllocationResult(
        accepted=accepted,
        invalid=commands.valid & ~valid,
        capacity_rejected=valid & ~accepted,
        effect_slot=effect_slot,
        direct=commands.valid & direct,
        area=commands.valid & area,
    )


allocate_fast_travel_effects = allocate_fast_travel_effects_


__all__ = [
    "FastTravelEffectAllocationResult",
    "allocate_fast_travel_effects",
    "allocate_fast_travel_effects_",
]
