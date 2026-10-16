"""Tensor-only lifetimes and generic death-spawn allocation.

The practical Gym keeps lifecycle data beside :class:`FastGymState` instead
of adding card-specific objects to the combat pool.  Every field is a dense
``[batch, entity]`` plane.  Death spawns are described entirely by data and
are allocated in parent stable-ID order into the lowest available slots.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from .simple_state import FastGymState


@dataclass
class FastLifecycleState:
    """Lifecycle descriptors aligned one-for-one with ``FastGymState`` slots.

    A lifetime of zero means that the entity has no automatic expiry.  Death
    spawn descriptors belong to the entity currently occupying the aligned
    slot and are cleared when that entity is resolved.
    """

    lifetime_ticks: torch.Tensor
    death_spawn_count: torch.Tensor
    death_spawn_card_id: torch.Tensor
    death_spawn_kind: torch.Tensor
    death_spawn_hp: torch.Tensor
    death_spawn_radius_units: torch.Tensor
    death_spawn_deploy_ticks: torch.Tensor

    @classmethod
    def empty_like(cls, state: FastGymState) -> FastLifecycleState:
        shape = state.active.shape
        device = state.device
        return cls(
            lifetime_ticks=torch.zeros(shape, dtype=torch.int32, device=device),
            death_spawn_count=torch.zeros(shape, dtype=torch.int32, device=device),
            death_spawn_card_id=torch.zeros(shape, dtype=torch.int64, device=device),
            death_spawn_kind=torch.zeros(shape, dtype=torch.int8, device=device),
            death_spawn_hp=torch.zeros(shape, dtype=torch.float32, device=device),
            death_spawn_radius_units=torch.zeros(
                shape, dtype=torch.int32, device=device
            ),
            death_spawn_deploy_ticks=torch.zeros(
                shape, dtype=torch.int32, device=device
            ),
        )

    def clone(self) -> FastLifecycleState:
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
            }
        )


@dataclass(frozen=True)
class FastLifecycleStepResult:
    """Dense lifecycle facts produced by one mutation-only step.

    ``spawned_mask`` and ``spawned_parent_ids`` are destination-slot aligned.
    Capacity rejection is parent-slot aligned: the boolean plane identifies
    parents that lost at least one requested child and the count plane records
    exactly how many children were rejected.
    """

    expired_mask: torch.Tensor
    resolved_parent_mask: torch.Tensor
    spawned_mask: torch.Tensor
    spawned_parent_ids: torch.Tensor
    capacity_rejected: torch.Tensor
    capacity_rejected_count: torch.Tensor

    @property
    def spawned(self) -> torch.Tensor:
        """Short alias for consumers that use event-style naming."""

        return self.spawned_mask

    @property
    def parent_ids(self) -> torch.Tensor:
        """Short alias for the destination-aligned parent stable IDs."""

        return self.spawned_parent_ids


def _validate_lifecycle(state: FastGymState, lifecycle: FastLifecycleState) -> None:
    expected = state.active.shape
    for descriptor in fields(lifecycle):
        value = getattr(lifecycle, descriptor.name)
        if value.shape != expected:
            raise ValueError(
                f"{descriptor.name} must have shape [batch, entities]"
            )
        if value.device != state.device:
            raise ValueError(f"{descriptor.name} must use the state device")


def step_fast_lifecycle_(
    state: FastGymState,
    lifecycle: FastLifecycleState,
    *,
    reserved_slot_floor: int = 0,
    reserved_mask: torch.Tensor | None = None,
) -> FastLifecycleStepResult:
    """Advance lifetimes, resolve deaths, and materialize generic children.

    Allocation is a fixed-shape rank operation.  It does not compact tensors,
    transfer data to the host, or dispatch on a card identity.  Parents are
    ordered by ``stable_id`` (physical slot breaks impossible/corrupt ties),
    while destinations are ordered by physical slot.  Consequently slot reuse
    never changes simulation ordering.
    """

    _validate_lifecycle(state, lifecycle)
    if not 0 <= reserved_slot_floor <= state.max_entities:
        raise ValueError("reserved_slot_floor must be within entity capacity")
    if reserved_mask is not None:
        if reserved_mask.shape != state.active.shape:
            raise ValueError("reserved_mask must have shape [batch, entities]")
        if reserved_mask.device != state.device:
            raise ValueError("reserved_mask must use the state device")
        if reserved_mask.dtype != torch.bool:
            raise ValueError("reserved_mask must be bool")

    batch, entities = state.active.shape
    slots = torch.arange(entities, dtype=torch.int64, device=state.device)
    slots_2d = slots.view(1, entities).expand(batch, -1)
    if reserved_mask is None:
        reserved = slots_2d < reserved_slot_floor
    else:
        reserved = reserved_mask | (slots_2d < reserved_slot_floor)

    has_lifetime = state.active & (lifecycle.lifetime_ticks > 0)
    lifecycle.lifetime_ticks.sub_(has_lifetime.to(torch.int32))
    expired = has_lifetime & (lifecycle.lifetime_ticks == 0)
    state.hp.copy_(torch.where(expired, torch.zeros_like(state.hp), state.hp))

    dead = state.active & (state.hp <= 0)
    parent_id = state.stable_id.clone()
    parent_owner = state.owner.clone()
    parent_x = state.x_units.clone()
    parent_y = state.y_units.clone()

    requested_count = lifecycle.death_spawn_count.clamp(min=0).to(torch.int64)
    spawn_parent = (
        dead
        & ~reserved
        & (requested_count > 0)
        & (lifecycle.death_spawn_card_id > 0)
        & (lifecycle.death_spawn_hp > 0)
    )
    requested_count = torch.where(
        spawn_parent, requested_count, torch.zeros_like(requested_count)
    )

    # For each parent i, total children requested by parents ordered before i.
    id_i = parent_id[:, :, None]
    id_j = parent_id[:, None, :]
    slot_i = slots.view(1, entities, 1)
    slot_j = slots.view(1, 1, entities)
    predecessor = spawn_parent[:, None, :] & (
        (id_j < id_i) | ((id_j == id_i) & (slot_j < slot_i))
    )
    child_start = (
        predecessor.to(torch.int64) * requested_count[:, None, :]
    ).sum(dim=2)

    # Dead slots become available in this same step. Reserved slots never do.
    free = (~state.active | dead) & ~reserved
    free_rank = free.to(torch.int64).cumsum(dim=1) - 1
    total_requested = requested_count.sum(dim=1)
    accepted_total = torch.minimum(total_requested, free.sum(dim=1).to(torch.int64))
    spawned = free & (free_rank >= 0) & (free_rank < accepted_total[:, None])

    # Map each accepted destination rank back to its stable-ordered parent.
    claims = (
        spawned[:, :, None]
        & spawn_parent[:, None, :]
        & (free_rank[:, :, None] >= child_start[:, None, :])
        & (
            free_rank[:, :, None]
            < child_start[:, None, :] + requested_count[:, None, :]
        )
    )
    source_slot = claims.to(torch.int64).argmax(dim=2)
    source_parent_id = parent_id.gather(1, source_slot)
    source_owner = parent_owner.gather(1, source_slot)
    source_x = parent_x.gather(1, source_slot)
    source_y = parent_y.gather(1, source_slot)
    source_start = child_start.gather(1, source_slot)
    source_count = requested_count.gather(1, source_slot).clamp(min=1)
    child_index = (free_rank - source_start).clamp(min=0)

    def gather_lifecycle(value: torch.Tensor) -> torch.Tensor:
        return value.gather(1, source_slot)

    child_radius = gather_lifecycle(lifecycle.death_spawn_radius_units)
    child_card_id = gather_lifecycle(lifecycle.death_spawn_card_id)
    child_kind = gather_lifecycle(lifecycle.death_spawn_kind)
    child_hp = gather_lifecycle(lifecycle.death_spawn_hp)
    child_deploy_ticks = gather_lifecycle(lifecycle.death_spawn_deploy_ticks)
    phase = (
        child_index.to(torch.float32)
        * (2.0 * torch.pi)
        / source_count.to(torch.float32)
    )
    offset_x = torch.round(torch.cos(phase) * child_radius).to(torch.int32)
    offset_y = torch.round(torch.sin(phase) * child_radius).to(torch.int32)
    single_child = source_count == 1
    offset_x = torch.where(single_child, torch.zeros_like(offset_x), offset_x)
    offset_y = torch.where(single_child, torch.zeros_like(offset_y), offset_y)

    # Resolve parents before writing children, so a dead parent's own physical
    # slot may be deterministically recycled without retaining stale fields.
    ordinary_dead = dead & ~reserved
    state.active.masked_fill_(dead, False)
    state.stable_id.masked_fill_(dead, 0)
    state.target_id.masked_fill_(dead, 0)
    state.kind.masked_fill_(ordinary_dead, 0)
    state.owner.masked_fill_(ordinary_dead, 0)
    state.card_id.masked_fill_(ordinary_dead, 0)
    state.x_units.masked_fill_(ordinary_dead, 0)
    state.y_units.masked_fill_(ordinary_dead, 0)
    state.hp.masked_fill_(ordinary_dead, 0)
    state.max_hp.masked_fill_(ordinary_dead, 0)
    state.damage.masked_fill_(ordinary_dead, 0)
    state.range_units.masked_fill_(ordinary_dead, 0)
    state.sight_range_units.masked_fill_(ordinary_dead, 0)
    state.speed_units_per_tick.masked_fill_(ordinary_dead, 0)
    state.hit_cooldown_ticks.masked_fill_(ordinary_dead, 0)
    state.deploy_ticks.masked_fill_(ordinary_dead, 0)
    state.cooldown_ticks.masked_fill_(ordinary_dead, 0)
    for descriptor in fields(lifecycle):
        getattr(lifecycle, descriptor.name).masked_fill_(dead, 0)

    child_stable_id = state.next_stable_id[:, None] + free_rank

    def write(field: torch.Tensor, value: torch.Tensor) -> None:
        field.copy_(torch.where(spawned, value.to(field.dtype), field))

    write(state.active, torch.ones_like(spawned))
    write(state.stable_id, child_stable_id)
    write(state.kind, child_kind)
    write(state.owner, source_owner)
    write(state.card_id, child_card_id)
    write(state.x_units, source_x + offset_x)
    write(state.y_units, source_y + offset_y)
    write(state.hp, child_hp)
    write(state.max_hp, child_hp)
    write(state.target_id, torch.zeros_like(source_parent_id))
    write(state.damage, torch.zeros_like(child_hp))
    write(state.range_units, torch.zeros_like(source_x))
    write(state.sight_range_units, torch.zeros_like(source_x))
    write(state.speed_units_per_tick, torch.zeros_like(source_x))
    write(state.hit_cooldown_ticks, torch.zeros_like(source_x))
    write(
        state.deploy_ticks,
        child_deploy_ticks.clamp(min=0),
    )
    write(state.cooldown_ticks, torch.zeros_like(source_x))
    for descriptor in fields(lifecycle):
        value = getattr(lifecycle, descriptor.name)
        value.masked_fill_(spawned, 0)
    state.next_stable_id.add_(spawned.sum(dim=1).to(torch.int64))

    accepted_by_parent = (
        claims.to(torch.int64).sum(dim=1)
    )
    rejected_count = (requested_count - accepted_by_parent).to(torch.int32)
    spawned_parent_ids = torch.where(
        spawned, source_parent_id, torch.zeros_like(source_parent_id)
    )
    return FastLifecycleStepResult(
        expired_mask=expired,
        resolved_parent_mask=dead,
        spawned_mask=spawned,
        spawned_parent_ids=spawned_parent_ids,
        capacity_rejected=rejected_count > 0,
        capacity_rejected_count=rejected_count,
    )


# Public spelling without punctuation remains convenient at call sites.
step_fast_lifecycle = step_fast_lifecycle_
