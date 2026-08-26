"""Fixed-shape periodic-spawn scheduling for the practical tensor Gym.

The scheduler is deliberately smaller than the exact resident implementation.
It consumes only numeric setup-time spawn blueprints, retains one clock per
entity slot, and emits at most one whole-wave command per live source per Gym
tick.  Materialization remains the responsibility of the shared spawn
allocator.

Runtime work contains no card-name dispatch, host reads, or variable-length
event compaction.  Commands remain padded to ``[batch, entities]`` and are
ordered by stable source ID so allocation order is independent of entity-slot
reuse.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from .simple_spawn_blueprints import (
    FastSpawnBlueprintCatalog,
    FastSpawnTrigger,
)

FAST_PERIODIC_UNLIMITED = -1
_EMPTY_BLUEPRINT = -1
_ORDER_SENTINEL = torch.iinfo(torch.int64).max


@dataclass(frozen=True)
class FastPeriodicSpawnCatalog:
    """Numeric periodic subset of :class:`FastSpawnBlueprintCatalog`."""

    device: torch.device
    periodic_blueprint_by_card: torch.Tensor
    child_card_id: torch.Tensor
    count: torch.Tensor
    radius_units: torch.Tensor
    deploy_ticks: torch.Tensor
    first_delay_ticks: torch.Tensor
    interval_ticks: torch.Tensor
    max_waves: torch.Tensor
    pause_while_stunned: torch.Tensor
    row_supported: torch.Tensor

    @property
    def blueprint_count(self) -> int:
        return int(self.child_card_id.shape[0])

    @property
    def card_count(self) -> int:
        return int(self.periodic_blueprint_by_card.shape[0])

    @classmethod
    def from_spawn_blueprints(
        cls,
        blueprints: FastSpawnBlueprintCatalog,
        *,
        pause_while_stunned: torch.Tensor | None = None,
    ) -> FastPeriodicSpawnCatalog:
        """Compile a card-to-periodic-row lookup without card identities.

        ``pause_while_stunned`` is an optional numeric per-blueprint data
        plane.  It defaults false because stun does not pause production unless
        the serialized mechanic explicitly opts into that behavior.
        """

        row_count = blueprints.blueprint_count
        device = blueprints.device
        shape = (row_count,)
        if pause_while_stunned is None:
            pause = torch.zeros(shape, dtype=torch.bool, device=device)
        else:
            if (
                tuple(pause_while_stunned.shape) != shape
                or pause_while_stunned.dtype != torch.bool
                or pause_while_stunned.device != device
            ):
                raise ValueError(
                    "pause_while_stunned must be bool [blueprints] on the "
                    "blueprint device"
                )
            pause = pause_while_stunned.clone()

        periodic = blueprints.trigger == int(FastSpawnTrigger.PERIODIC)
        child = blueprints.child_card_id.to(torch.int64)
        known_child = (child > 0) & (child < blueprints.fast_cards.size)
        safe_child = child.clamp(0, max(0, blueprints.fast_cards.size - 1))
        child_is_entity = (blueprints.fast_cards.kind[safe_child] >= 0) & (
            blueprints.fast_cards.hitpoints[safe_child] > 0
        )
        max_waves = blueprints.max_waves.to(torch.int32)
        interval = blueprints.interval_ticks.to(torch.int32)
        valid_waves = (max_waves == FAST_PERIODIC_UNLIMITED) | (max_waves > 0)
        valid_cadence = interval > 0
        row_supported = (
            periodic
            & blueprints.blueprint_supported
            & known_child
            & child_is_entity
            & (blueprints.count > 0)
            & (blueprints.first_delay_ticks >= 0)
            & valid_waves
            & valid_cadence
        )

        card_count = len(blueprints.cards.names)
        sentinel = row_count
        row = torch.arange(row_count, dtype=torch.int64, device=device)
        candidate = torch.where(row_supported, row, sentinel)
        root = blueprints.root_card_id.clamp(0, max(0, card_count - 1))
        mapping = torch.full((card_count,), sentinel, dtype=torch.int64, device=device)
        mapping.scatter_reduce_(0, root, candidate, reduce="amin", include_self=True)

        # A fixed per-entity clock deliberately supports one periodic operation.
        # Multiple rows for one root fail closed instead of silently discarding
        # one serialized schedule.
        multiplicity = torch.zeros((card_count,), dtype=torch.int32, device=device)
        multiplicity.scatter_add_(0, root, row_supported.to(torch.int32))
        mapping = torch.where(
            (mapping < sentinel) & (multiplicity == 1),
            mapping,
            torch.full_like(mapping, _EMPTY_BLUEPRINT),
        )
        return cls(
            device=mapping.device,
            periodic_blueprint_by_card=mapping,
            child_card_id=child.clone(),
            count=blueprints.count.to(torch.int32).clone(),
            radius_units=blueprints.radius_units.to(torch.int32).clone(),
            deploy_ticks=blueprints.deploy_ticks.to(torch.int32).clone(),
            first_delay_ticks=blueprints.first_delay_ticks.to(torch.int64).clone(),
            interval_ticks=interval.to(torch.int64).clone(),
            max_waves=max_waves.clone(),
            pause_while_stunned=pause,
            row_supported=row_supported,
        )


@dataclass
class FastPeriodicSpawnState:
    """Per-entity source identity, absolute deadline, and remaining waves."""

    device: torch.device
    source_stable_id: torch.Tensor
    blueprint_row: torch.Tensor
    next_tick: torch.Tensor
    waves_remaining: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.source_stable_id.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.source_stable_id.shape[1])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        max_entities: int,
        *,
        device: str | torch.device = "cpu",
    ) -> FastPeriodicSpawnState:
        if batch_size < 1 or max_entities < 1:
            raise ValueError("batch_size and max_entities must be positive")
        torch_device = torch.device(device)
        if torch_device.type == "cuda" and torch_device.index is None:
            torch_device = torch.device("cuda", torch.cuda.current_device())
        shape = (batch_size, max_entities)
        return cls(
            device=torch_device,
            source_stable_id=torch.zeros(shape, dtype=torch.int64, device=torch_device),
            blueprint_row=torch.full(
                shape, _EMPTY_BLUEPRINT, dtype=torch.int64, device=torch_device
            ),
            next_tick=torch.zeros(shape, dtype=torch.int64, device=torch_device),
            waves_remaining=torch.zeros(shape, dtype=torch.int32, device=torch_device),
        )

    def clone(self) -> FastPeriodicSpawnState:
        return type(self)(
            device=self.device,
            source_stable_id=self.source_stable_id.clone(),
            blueprint_row=self.blueprint_row.clone(),
            next_tick=self.next_tick.clone(),
            waves_remaining=self.waves_remaining.clone(),
        )


@dataclass(frozen=True)
class FastPeriodicSpawnCommands:
    """Padded whole-wave triggers ordered by stable source ID."""

    ready: torch.Tensor
    blueprint_row: torch.Tensor
    source_slot: torch.Tensor
    source_stable_id: torch.Tensor
    child_card_id: torch.Tensor
    count: torch.Tensor
    radius_units: torch.Tensor
    deploy_ticks: torch.Tensor


def _tick_plane(
    tick: int | torch.Tensor,
    *,
    state: FastPeriodicSpawnState,
) -> torch.Tensor:
    value = torch.as_tensor(tick, dtype=torch.int64, device=state.device)
    if value.ndim == 0:
        return value.expand(state.batch_size, state.max_entities)
    if tuple(value.shape) == (state.batch_size,):
        return value[:, None].expand(-1, state.max_entities)
    if tuple(value.shape) == (state.batch_size, 1):
        return value.expand(-1, state.max_entities)
    raise ValueError("tick must be scalar, [batch], or [batch, 1]")


def step_periodic_spawns_(
    catalog: FastPeriodicSpawnCatalog,
    state: FastPeriodicSpawnState,
    *,
    tick: int | torch.Tensor,
    active: torch.Tensor,
    source_stable_id: torch.Tensor,
    source_card_id: torch.Tensor,
    stunned: torch.Tensor | None = None,
) -> FastPeriodicSpawnCommands:
    """Advance all live sources and emit one padded command plane.

    The practical Gym advances one native tick per call.  When a blueprint's
    optional pause flag is set, a stunned source shifts its deadline by one
    tick.  Without that flag, stun has no effect on the production clock.
    """

    shape = (state.batch_size, state.max_entities)
    if catalog.device != state.device:
        raise ValueError("catalog and periodic state must use the same device")
    for name, value, dtype in (
        ("active", active, torch.bool),
        ("source_stable_id", source_stable_id, torch.int64),
        ("source_card_id", source_card_id, torch.int64),
    ):
        if tuple(value.shape) != shape or value.device != state.device:
            raise ValueError(f"{name} must match periodic state shape and device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    if stunned is None:
        stunned = torch.zeros(shape, dtype=torch.bool, device=state.device)
    elif (
        tuple(stunned.shape) != shape
        or stunned.device != state.device
        or stunned.dtype != torch.bool
    ):
        raise ValueError("stunned must be bool and match periodic state")

    if catalog.blueprint_count == 0:
        state.source_stable_id.zero_()
        state.blueprint_row.fill_(_EMPTY_BLUEPRINT)
        state.next_tick.zero_()
        state.waves_remaining.zero_()
        return FastPeriodicSpawnCommands(
            ready=torch.zeros(shape, dtype=torch.bool, device=state.device),
            blueprint_row=torch.full(
                shape, _EMPTY_BLUEPRINT, dtype=torch.int64, device=state.device
            ),
            source_slot=torch.full(shape, -1, dtype=torch.int64, device=state.device),
            source_stable_id=torch.zeros(shape, dtype=torch.int64, device=state.device),
            child_card_id=torch.zeros(shape, dtype=torch.int64, device=state.device),
            count=torch.zeros(shape, dtype=torch.int32, device=state.device),
            radius_units=torch.zeros(shape, dtype=torch.int32, device=state.device),
            deploy_ticks=torch.zeros(shape, dtype=torch.int32, device=state.device),
        )

    now = _tick_plane(tick, state=state)
    known_card = (source_card_id > 0) & (source_card_id < catalog.card_count)
    safe_card = source_card_id.clamp(0, max(0, catalog.card_count - 1))
    mapped = catalog.periodic_blueprint_by_card[safe_card]
    live = active & (source_stable_id > 0) & known_card & (mapped >= 0)

    stale = ~live
    state.source_stable_id.masked_fill_(stale, 0)
    state.blueprint_row.masked_fill_(stale, _EMPTY_BLUEPRINT)
    state.next_tick.masked_fill_(stale, 0)
    state.waves_remaining.masked_fill_(stale, 0)

    fresh = live & (
        (state.source_stable_id != source_stable_id) | (state.blueprint_row != mapped)
    )
    safe_row = mapped.clamp(0, max(0, catalog.blueprint_count - 1))
    state.source_stable_id.copy_(
        torch.where(fresh, source_stable_id, state.source_stable_id)
    )
    state.blueprint_row.copy_(torch.where(fresh, mapped, state.blueprint_row))
    state.next_tick.copy_(
        torch.where(fresh, now + catalog.first_delay_ticks[safe_row], state.next_tick)
    )
    state.waves_remaining.copy_(
        torch.where(fresh, catalog.max_waves[safe_row], state.waves_remaining)
    )

    paused = live & stunned & catalog.pause_while_stunned[safe_row]
    state.next_tick.add_(paused.to(torch.int64))
    due = live & ~paused & (state.waves_remaining != 0) & (now >= state.next_tick)

    finite_due = due & (state.waves_remaining > 0)
    state.waves_remaining.sub_(finite_due.to(torch.int32))
    state.next_tick.add_(due.to(torch.int64) * catalog.interval_ticks[safe_row])

    slots = (
        torch.arange(state.max_entities, dtype=torch.int64, device=state.device)
        .view(1, -1)
        .expand(state.batch_size, -1)
    )
    order_key = torch.where(
        due, source_stable_id, torch.full_like(source_stable_id, _ORDER_SENTINEL)
    )
    order = torch.argsort(order_key, dim=1, stable=True)

    def gather(value: torch.Tensor) -> torch.Tensor:
        return value.gather(1, order)

    ordered_ready = gather(due)
    ordered_row = gather(safe_row)
    return FastPeriodicSpawnCommands(
        ready=ordered_ready,
        blueprint_row=torch.where(
            ordered_ready, ordered_row, torch.full_like(ordered_row, _EMPTY_BLUEPRINT)
        ),
        source_slot=torch.where(
            ordered_ready, gather(slots), torch.full_like(slots, -1)
        ),
        source_stable_id=torch.where(
            ordered_ready,
            gather(source_stable_id),
            torch.zeros_like(source_stable_id),
        ),
        child_card_id=torch.where(
            ordered_ready,
            catalog.child_card_id[ordered_row],
            torch.zeros_like(ordered_row),
        ),
        count=torch.where(
            ordered_ready,
            catalog.count[ordered_row],
            torch.zeros_like(ordered_row, dtype=torch.int32),
        ),
        radius_units=torch.where(
            ordered_ready,
            catalog.radius_units[ordered_row],
            torch.zeros_like(ordered_row, dtype=torch.int32),
        ),
        deploy_ticks=torch.where(
            ordered_ready,
            catalog.deploy_ticks[ordered_row],
            torch.zeros_like(ordered_row, dtype=torch.int32),
        ),
    )


__all__ = [
    "FAST_PERIODIC_UNLIMITED",
    "FastPeriodicSpawnCatalog",
    "FastPeriodicSpawnCommands",
    "FastPeriodicSpawnState",
    "step_periodic_spawns_",
]
