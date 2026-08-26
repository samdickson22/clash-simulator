"""Fixed-shape projectile and area effects for the practical tensor Gym.

The production kernel needs only one small effect pool.  Card-specific code
serializes attacks into these primitive fields; this module advances every
active effect together and mutates :class:`FastGymState` directly.  Status
storage remains caller-owned so the combat state can stay backward compatible
while the unified engine is assembled.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from .simple_chain_topology import FastChainTopologyInputs, fast_chain_hit_count
from .simple_modifiers import FastModifierState, intercept_fast_shield_hits_
from .simple_state import FAST_KIND_BUILDING, FastGymState

FAST_EFFECT_PROJECTILE = 0
FAST_EFFECT_AREA = 1

FAST_STATUS_NONE = 0
FAST_STATUS_STUN = 1
FAST_STATUS_SLOW = 2
# Freeze stops the target in the fast Gym and is represented by the same
# primitive as a stun.  The alias keeps serialized card data descriptive.
FAST_STATUS_FREEZE = FAST_STATUS_STUN


@dataclass
class FastEffectState:
    """Mutable structure-of-arrays pool with shape ``[batch, effects]``."""

    device: torch.device
    active: torch.Tensor
    kind: torch.Tensor
    source_owner: torch.Tensor
    source_card_id: torch.Tensor
    source_x_units: torch.Tensor
    source_y_units: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    target_id: torch.Tensor
    target_x_units: torch.Tensor
    target_y_units: torch.Tensor
    tracks_target: torch.Tensor
    speed_units_per_tick: torch.Tensor
    damage: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    building_damage_multiplier: torch.Tensor
    radius_units: torch.Tensor
    status_kind: torch.Tensor
    status_duration_ticks: torch.Tensor
    lifetime_ticks: torch.Tensor
    damage_interval_ticks: torch.Tensor
    next_damage_tick: torch.Tensor
    damage_on_spawn: torch.Tensor
    damage_hits_remaining: torch.Tensor
    status_interval_ticks: torch.Tensor
    next_status_tick: torch.Tensor
    status_scans_remaining: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    multi_target_count: torch.Tensor
    multi_target_range_units: torch.Tensor
    multi_repeat_primary: torch.Tensor
    chain_target_count: torch.Tensor
    chain_hop_radius_units: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.active.shape[0])

    @property
    def max_effects(self) -> int:
        return int(self.active.shape[1])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_effects: int = 64,
        device: str | torch.device = "cpu",
    ) -> FastEffectState:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_effects < 1:
            raise ValueError("max_effects must be positive")
        tensor_device = torch.device(device)
        if tensor_device.type == "cuda" and tensor_device.index is None:
            tensor_device = torch.device("cuda", torch.cuda.current_device())
        shape = (batch_size, max_effects)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=tensor_device)

        return cls(
            device=tensor_device,
            active=zeros(torch.bool),
            kind=zeros(torch.int8),
            source_owner=zeros(torch.int8),
            source_card_id=zeros(torch.int64),
            source_x_units=zeros(torch.int32),
            source_y_units=zeros(torch.int32),
            x_units=zeros(torch.int32),
            y_units=zeros(torch.int32),
            target_id=zeros(torch.int64),
            target_x_units=zeros(torch.int32),
            target_y_units=zeros(torch.int32),
            tracks_target=torch.ones(shape, dtype=torch.bool, device=tensor_device),
            speed_units_per_tick=zeros(torch.int32),
            damage=zeros(torch.float32),
            tower_damage_multiplier=torch.ones(
                shape, dtype=torch.float32, device=tensor_device
            ),
            building_damage_multiplier=torch.ones(
                shape, dtype=torch.float32, device=tensor_device
            ),
            radius_units=zeros(torch.int32),
            status_kind=zeros(torch.int8),
            status_duration_ticks=zeros(torch.int32),
            lifetime_ticks=zeros(torch.int32),
            damage_interval_ticks=torch.ones(
                shape, dtype=torch.int32, device=tensor_device
            ),
            next_damage_tick=zeros(torch.int32),
            damage_on_spawn=torch.ones(shape, dtype=torch.bool, device=tensor_device),
            damage_hits_remaining=torch.ones(
                shape, dtype=torch.int32, device=tensor_device
            ),
            status_interval_ticks=torch.ones(
                shape, dtype=torch.int32, device=tensor_device
            ),
            next_status_tick=zeros(torch.int32),
            status_scans_remaining=torch.ones(
                shape, dtype=torch.int32, device=tensor_device
            ),
            hits_air=torch.ones(shape, dtype=torch.bool, device=tensor_device),
            hits_ground=torch.ones(shape, dtype=torch.bool, device=tensor_device),
            multi_target_count=torch.ones(
                shape, dtype=torch.int16, device=tensor_device
            ),
            multi_target_range_units=zeros(torch.int32),
            multi_repeat_primary=zeros(torch.bool),
            chain_target_count=zeros(torch.int16),
            chain_hop_radius_units=zeros(torch.int32),
        )

    def clone(self) -> FastEffectState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class FastEffectStepResult:
    """Fixed-shape effect telemetry; no dynamic event ledger is produced."""

    impacted: torch.Tensor
    targets_hit: torch.Tensor
    sources_consumed: torch.Tensor
    cleaned: torch.Tensor


def _validate_inputs(
    state: FastGymState,
    effects: FastEffectState,
    entity_status_kind: torch.Tensor,
    entity_status_ticks: torch.Tensor,
    consume_source_id: torch.Tensor | None,
    entity_is_air: torch.Tensor | None,
    entity_collision_radius_units: torch.Tensor | None,
) -> None:
    if effects.device != state.device:
        raise ValueError("effects and state must use the same device")
    if effects.batch_size != state.batch_size:
        raise ValueError("effects and state must use the same batch size")
    entity_shape = (state.batch_size, state.max_entities)
    if entity_status_kind.shape != entity_shape:
        raise ValueError("entity_status_kind must have shape [batch, entities]")
    if entity_status_ticks.shape != entity_shape:
        raise ValueError("entity_status_ticks must have shape [batch, entities]")
    if entity_status_kind.device != state.device:
        raise ValueError("entity_status_kind is on a different device")
    if entity_status_ticks.device != state.device:
        raise ValueError("entity_status_ticks is on a different device")
    if entity_status_kind.dtype != torch.int8:
        raise ValueError("entity_status_kind must be int8")
    if entity_status_ticks.dtype != torch.int32:
        raise ValueError("entity_status_ticks must be int32")
    effect_shape = (state.batch_size, effects.max_effects)
    for descriptor in fields(effects):
        if descriptor.name == "device":
            continue
        value = getattr(effects, descriptor.name)
        if value.shape != effect_shape:
            raise ValueError(f"{descriptor.name} must have shape [batch, effects]")
        if value.device != state.device:
            raise ValueError(f"{descriptor.name} is on a different device")
    if consume_source_id is not None:
        if consume_source_id.shape != effect_shape:
            raise ValueError("consume_source_id must have shape [batch, effects]")
        if consume_source_id.device != state.device:
            raise ValueError("consume_source_id is on a different device")
        if consume_source_id.dtype != torch.int64:
            raise ValueError("consume_source_id must be int64")
    if entity_is_air is not None:
        if entity_is_air.shape != entity_shape:
            raise ValueError("entity_is_air must have shape [batch, entities]")
        if entity_is_air.device != state.device or entity_is_air.dtype != torch.bool:
            raise ValueError("entity_is_air must be bool on the state device")
    if entity_collision_radius_units is not None:
        if entity_collision_radius_units.shape != entity_shape:
            raise ValueError(
                "entity_collision_radius_units must have shape [batch, entities]"
            )
        if (
            entity_collision_radius_units.device != state.device
            or entity_collision_radius_units.dtype != torch.int32
        ):
            raise ValueError(
                "entity_collision_radius_units must be int32 on the state device"
            )


def step_fast_effects(
    state: FastGymState,
    effects: FastEffectState,
    entity_status_kind: torch.Tensor,
    entity_status_ticks: torch.Tensor,
    *,
    consume_source_id: torch.Tensor | None = None,
    cleanup_dead: bool = True,
    modifiers: FastModifierState | None = None,
    entity_is_air: torch.Tensor | None = None,
    entity_collision_radius_units: torch.Tensor | None = None,
) -> FastEffectStepResult:
    """Advance homing effects, resolve splash, install statuses, and clean up.

    ``consume_source_id`` is an optional ``[B, P]`` stable-ID tensor.  A
    nonzero ID removes that source entity when its effect impacts, which covers
    leap-and-burst units such as Ice Spirit without guessing from owner/card.

    Simultaneous AOE damage is grouped before HP mutation.  Stun/freeze has
    precedence over slow when effects overlap; durations of the same kind use
    the longest remaining tick count.  Existing status timers advance before
    newly impacted statuses are installed.
    """

    _validate_inputs(
        state,
        effects,
        entity_status_kind,
        entity_status_ticks,
        consume_source_id,
        entity_is_air,
        entity_collision_radius_units,
    )
    batch, max_effects = effects.active.shape
    max_entities = state.max_entities

    status_running = entity_status_ticks > 0
    entity_status_ticks.sub_(status_running.to(torch.int32)).clamp_(min=0)
    entity_status_kind.masked_fill_(entity_status_ticks == 0, FAST_STATUS_NONE)

    alive = effects.active & (effects.lifetime_ticks > 0)
    valid_projectile = alive & (effects.kind == FAST_EFFECT_PROJECTILE)
    valid_area = alive & (effects.kind == FAST_EFFECT_AREA)
    tracks_entity = valid_projectile & effects.tracks_target & (effects.target_id > 0)
    target_match = (
        tracks_entity[:, :, None]
        & state.active[:, None, :]
        & (state.hp[:, None, :] > 0)
        & (effects.target_id[:, :, None] > 0)
        & (effects.target_id[:, :, None] == state.stable_id[:, None, :])
    )
    target_found = target_match.any(dim=2)
    target_slot = target_match.to(torch.int8).argmax(dim=2).to(torch.int64)
    tracked_x = state.x_units.gather(1, target_slot)
    tracked_y = state.y_units.gather(1, target_slot)
    target_x = torch.where(tracks_entity, tracked_x, effects.target_x_units)
    target_y = torch.where(tracks_entity, tracked_y, effects.target_y_units)
    destination_available = ~tracks_entity | target_found

    delta_x = target_x.to(torch.float32) - effects.x_units.to(torch.float32)
    delta_y = target_y.to(torch.float32) - effects.y_units.to(torch.float32)
    distance = torch.sqrt(delta_x.square() + delta_y.square())
    speed = effects.speed_units_per_tick.to(torch.float32).clamp(min=0.0)
    projectile_impact = valid_projectile & destination_available & (distance <= speed)
    travel = torch.minimum(speed, distance)
    moving = (
        valid_projectile & destination_available & ~projectile_impact & (travel > 0)
    )
    denominator = distance.clamp(min=1.0)
    move_x = torch.round(delta_x * travel / denominator).to(torch.int32)
    move_y = torch.round(delta_y * travel / denominator).to(torch.int32)
    effects.x_units.add_(torch.where(moving, move_x, 0))
    effects.y_units.add_(torch.where(moving, move_y, 0))
    effects.x_units.copy_(torch.where(projectile_impact, target_x, effects.x_units))
    effects.y_units.copy_(torch.where(projectile_impact, target_y, effects.y_units))

    area_damage_due = (
        valid_area
        & (effects.damage_hits_remaining > 0)
        & (effects.next_damage_tick <= 0)
    )
    area_status_due = (
        valid_area
        & (effects.status_scans_remaining > 0)
        & (effects.next_status_tick <= 0)
        & (effects.status_kind != FAST_STATUS_NONE)
    )
    damage_due = projectile_impact | area_damage_due
    status_due = projectile_impact | area_status_due
    impacted = damage_due | status_due
    dx = state.x_units[:, None, :].to(torch.int64) - effects.x_units[:, :, None].to(
        torch.int64
    )
    dy = state.y_units[:, None, :].to(torch.int64) - effects.y_units[:, :, None].to(
        torch.int64
    )
    radius_sq = effects.radius_units.to(torch.int64).clamp(min=0).square()
    if entity_is_air is None:
        entity_is_air = torch.zeros(
            (batch, max_entities), dtype=torch.bool, device=state.device
        )
    if entity_collision_radius_units is None:
        entity_collision_radius_units = torch.zeros(
            (batch, max_entities), dtype=torch.int32, device=state.device
        )
    target_plane = torch.where(
        entity_is_air[:, None, :],
        effects.hits_air[:, :, None],
        effects.hits_ground[:, :, None],
    )
    base_candidates = (
        state.active[:, None, :]
        & (state.hp[:, None, :] > 0)
        & (state.owner[:, None, :] != effects.source_owner[:, :, None])
        & target_plane
    )
    circle_candidates = base_candidates & (
        dx.square() + dy.square() <= radius_sq[:, :, None]
    )

    # Direct and projectile attacks retain their committed primary identity.
    # This makes zero-radius ordinary hits robust to target movement while
    # leaving position-targeted spells on the ordinary circle path.
    primary_match = (
        base_candidates
        & (effects.target_id[:, :, None] > 0)
        & (effects.target_id[:, :, None] == state.stable_id[:, None, :])
    )
    circle_candidates |= primary_match

    # Multi-recipient attacks remain one effect. Current serialized public
    # data has at most two recipients, so one dense nearest-secondary query is
    # both the truthful bounded primitive and substantially cheaper than an
    # every-effect sort. The catalog fails larger counts closed for training.
    source_dx = state.x_units[:, None, :].to(torch.int64) - effects.source_x_units[
        :, :, None
    ].to(torch.int64)
    source_dy = state.y_units[:, None, :].to(torch.int64) - effects.source_y_units[
        :, :, None
    ].to(torch.int64)
    source_distance_sq = source_dx.square() + source_dy.square()
    multi_reach = effects.multi_target_range_units.to(torch.int64)[:, :, None].clamp(
        min=0
    ) + entity_collision_radius_units.to(torch.int64)[:, None, :].clamp(min=0)
    multi_candidates = (
        base_candidates
        & ~primary_match
        & (source_distance_sq <= multi_reach.square())
        & (effects.multi_target_count[:, :, None] > 1)
    )
    maximum = torch.iinfo(torch.int64).max
    candidate_distance = torch.where(
        multi_candidates,
        source_distance_sq,
        torch.full_like(source_distance_sq, maximum),
    )
    nearest_distance = candidate_distance.amin(dim=2)
    nearest_at_distance = multi_candidates & (
        source_distance_sq == nearest_distance[:, :, None]
    )
    selected_id = torch.where(
        nearest_at_distance,
        state.stable_id[:, None, :],
        torch.full_like(source_distance_sq, maximum),
    ).amin(dim=2)
    selected_secondary = nearest_at_distance & (
        state.stable_id[:, None, :] == selected_id[:, :, None]
    )
    secondary_needed = effects.multi_target_count > 1
    selected_any = selected_secondary.any(dim=2)
    repeated_primary = torch.where(
        effects.multi_repeat_primary,
        secondary_needed & ~selected_any,
        False,
    )
    multi_hit_count = selected_secondary.to(torch.int16) + primary_match.to(
        torch.int16
    ) * (1 + repeated_primary[:, :, None].to(torch.int16))
    multi = effects.multi_target_count > 1
    ordinary_hit_count = torch.where(
        multi[:, :, None],
        multi_hit_count,
        circle_candidates.to(torch.int16),
    )
    chain_hit_count = fast_chain_hit_count(
        FastChainTopologyInputs(
            source_x_units=effects.source_x_units,
            source_y_units=effects.source_y_units,
            primary_target_id=effects.target_id,
            primary_x_units=effects.x_units,
            primary_y_units=effects.y_units,
            entity_stable_id=state.stable_id,
            entity_x_units=state.x_units,
            entity_y_units=state.y_units,
            eligible=base_candidates,
            hop_radius_units=effects.chain_hop_radius_units,
            target_count=effects.chain_target_count,
        )
    )
    chain = effects.chain_target_count > 1
    hit_count = torch.where(
        chain[:, :, None],
        chain_hit_count,
        ordinary_hit_count,
    )
    has_hit = hit_count > 0
    damage_targets = damage_due[:, :, None] & has_hit
    status_targets = status_due[:, :, None] & has_hit
    targets_hit = damage_targets | status_targets
    entity_slot = torch.arange(
        max_entities, dtype=torch.int64, device=state.device
    ).view(1, 1, -1)
    tower_multiplier = torch.where(
        entity_slot < 6,
        effects.tower_damage_multiplier.clamp(min=0.0)[:, :, None],
        1.0,
    )
    building_multiplier = torch.where(
        (entity_slot >= 6) & (state.kind[:, None, :] == FAST_KIND_BUILDING),
        effects.building_damage_multiplier.clamp(min=0.0)[:, :, None],
        1.0,
    )
    per_hit_damage = (
        effects.damage.clamp(min=0.0)[:, :, None]
        * tower_multiplier
        * building_multiplier
    )
    weighted_damage = per_hit_damage * hit_count.to(torch.float32)
    if modifiers is None:
        grouped_damage = (damage_targets.to(torch.float32) * weighted_damage).sum(dim=1)
    else:
        hit_target_slot = entity_slot.expand(batch, max_effects, max_entities)
        shield_result = intercept_fast_shield_hits_(
            modifiers,
            valid=damage_targets.reshape(batch, max_effects * max_entities),
            target_slot=hit_target_slot.reshape(batch, max_effects * max_entities),
            damage=weighted_damage.expand(-1, -1, max_entities).reshape(
                batch, max_effects * max_entities
            ),
        )
        grouped_damage = shield_result.hp_damage
    state.hp.sub_(grouped_damage).clamp_(min=0.0)

    duration = effects.status_duration_ticks.clamp(min=0)[:, :, None]
    stun_duration = torch.where(
        status_targets & (effects.status_kind[:, :, None] == FAST_STATUS_STUN),
        duration,
        0,
    ).amax(dim=1)
    slow_duration = torch.where(
        status_targets & (effects.status_kind[:, :, None] == FAST_STATUS_SLOW),
        duration,
        0,
    ).amax(dim=1)
    incoming_stun = stun_duration > 0
    incoming_slow = (slow_duration > 0) & ~incoming_stun
    same_stun = entity_status_kind == FAST_STATUS_STUN
    same_slow = entity_status_kind == FAST_STATUS_SLOW
    entity_status_ticks.copy_(
        torch.where(
            incoming_stun,
            torch.maximum(
                stun_duration,
                torch.where(same_stun, entity_status_ticks, 0),
            ),
            torch.where(
                incoming_slow,
                torch.maximum(
                    slow_duration,
                    torch.where(same_slow, entity_status_ticks, 0),
                ),
                entity_status_ticks,
            ),
        )
    )
    entity_status_kind.copy_(
        torch.where(
            incoming_stun,
            FAST_STATUS_STUN,
            torch.where(incoming_slow, FAST_STATUS_SLOW, entity_status_kind),
        ).to(torch.int8)
    )

    if consume_source_id is None:
        consume_source_id = torch.zeros(
            (batch, max_effects), dtype=torch.int64, device=state.device
        )
    consume_match = (
        impacted[:, :, None]
        & (consume_source_id[:, :, None] > 0)
        & state.active[:, None, :]
        & (consume_source_id[:, :, None] == state.stable_id[:, None, :])
    )
    sources_consumed = consume_match.any(dim=1)
    state.hp.masked_fill_(sources_consumed, 0.0)

    died = state.active & (state.hp <= 0)
    if cleanup_dead:
        state.active.logical_and_(~died)
        state.stable_id.masked_fill_(died, 0)
        state.target_id.masked_fill_(died, 0)
        entity_status_kind.masked_fill_(died, FAST_STATUS_NONE)
        entity_status_ticks.masked_fill_(died, 0)

    effects.damage_hits_remaining.sub_(area_damage_due.to(torch.int32)).clamp_(min=0)
    effects.status_scans_remaining.sub_(area_status_due.to(torch.int32)).clamp_(min=0)
    effects.next_damage_tick.copy_(
        torch.where(
            area_damage_due,
            effects.damage_interval_ticks,
            effects.next_damage_tick,
        )
    )
    effects.next_status_tick.copy_(
        torch.where(
            area_status_due,
            effects.status_interval_ticks,
            effects.next_status_tick,
        )
    )
    retained_area = valid_area & (effects.lifetime_ticks > 0)
    effects.next_damage_tick.sub_(
        (retained_area & (effects.next_damage_tick > 0)).to(torch.int32)
    )
    effects.next_status_tick.sub_(
        (retained_area & (effects.next_status_tick > 0)).to(torch.int32)
    )
    effects.lifetime_ticks.sub_(alive.to(torch.int32)).clamp_(min=0)
    missing_target = tracks_entity & ~target_found
    invalid_kind = alive & ~(valid_projectile | valid_area)
    cleaned = effects.active & (
        projectile_impact
        | missing_target
        | invalid_kind
        | (effects.lifetime_ticks <= 0)
    )
    effects.active.logical_and_(~cleaned)
    effects.target_id.masked_fill_(cleaned, 0)
    effects.status_kind.masked_fill_(cleaned, FAST_STATUS_NONE)
    effects.status_duration_ticks.masked_fill_(cleaned, 0)
    effects.lifetime_ticks.masked_fill_(cleaned, 0)

    return FastEffectStepResult(
        impacted=impacted,
        targets_hit=targets_hit,
        sources_consumed=sources_consumed,
        cleaned=cleaned,
    )
