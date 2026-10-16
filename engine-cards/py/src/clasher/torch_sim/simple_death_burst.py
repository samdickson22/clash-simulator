"""Fixed-shape lethal-transition bursts for the practical tensor Gym.

Death-spawn materialization is deliberately a separate primitive.  This
module emits only one-shot area-effect commands from numeric per-card data.
Runtime work is fully tensorized: there is no card-name dispatch, host read,
event list, or variable-length compaction.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from .simple_state import FastGymState


@dataclass(frozen=True)
class FastDeathBurstCatalog:
    """Dense burst descriptors indexed by numeric card ID."""

    device: torch.device
    enabled: torch.Tensor
    damage: torch.Tensor
    radius_units: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    building_damage_multiplier: torch.Tensor

    @property
    def card_count(self) -> int:
        return int(self.enabled.shape[0])

    @classmethod
    def empty(
        cls,
        card_count: int,
        *,
        device: str | torch.device = "cpu",
    ) -> FastDeathBurstCatalog:
        """Allocate a disabled numeric table ready for setup-time population."""

        if card_count < 1:
            raise ValueError("card_count must be positive")
        torch_device = torch.device(device)
        if torch_device.type == "cuda" and torch_device.index is None:
            torch_device = torch.device("cuda", torch.cuda.current_device())
        shape = (card_count,)
        return cls(
            device=torch_device,
            enabled=torch.zeros(shape, dtype=torch.bool, device=torch_device),
            damage=torch.zeros(shape, dtype=torch.float32, device=torch_device),
            radius_units=torch.zeros(shape, dtype=torch.int32, device=torch_device),
            hits_air=torch.zeros(shape, dtype=torch.bool, device=torch_device),
            hits_ground=torch.zeros(shape, dtype=torch.bool, device=torch_device),
            tower_damage_multiplier=torch.ones(
                shape, dtype=torch.float32, device=torch_device
            ),
            building_damage_multiplier=torch.ones(
                shape, dtype=torch.float32, device=torch_device
            ),
        )

    def clone(self) -> FastDeathBurstCatalog:
        return type(self)(
            device=self.device,
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
                if descriptor.name != "device"
            },
        )


@dataclass
class FastDeathBurstState:
    """Source identity already consumed in each physical entity slot."""

    device: torch.device
    emitted_source_stable_id: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.emitted_source_stable_id.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.emitted_source_stable_id.shape[1])

    @classmethod
    def empty_like(cls, state: FastGymState) -> FastDeathBurstState:
        return cls(
            device=state.device,
            emitted_source_stable_id=torch.zeros_like(
                state.stable_id, dtype=torch.int64
            ),
        )

    def clone(self) -> FastDeathBurstState:
        return type(self)(
            device=self.device,
            emitted_source_stable_id=self.emitted_source_stable_id.clone(),
        )

    def reset_rows_(self, rows: torch.Tensor) -> None:
        """Forget consumed identities for selected independently reset games."""

        expected = (self.batch_size,)
        if tuple(rows.shape) != expected:
            raise ValueError("rows must have shape [batch]")
        if rows.device != self.device or rows.dtype != torch.bool:
            raise ValueError("rows must be bool on the burst-state device")
        self.emitted_source_stable_id.masked_fill_(rows[:, None], 0)


@dataclass(frozen=True)
class FastDeathBurstCommands:
    """Padded one-shot area commands in ascending source-stable-ID order."""

    ready: torch.Tensor
    source_slot: torch.Tensor
    source_stable_id: torch.Tensor
    source_owner: torch.Tensor
    source_card_id: torch.Tensor
    source_x_units: torch.Tensor
    source_y_units: torch.Tensor
    damage: torch.Tensor
    radius_units: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    building_damage_multiplier: torch.Tensor


@dataclass(frozen=True)
class FastDeathBurstStepResult:
    """Commands plus source-aligned admission and capacity telemetry."""

    commands: FastDeathBurstCommands
    processed_source_mask: torch.Tensor
    emitted_source_mask: torch.Tensor
    capacity_rejected: torch.Tensor
    emitted_count: torch.Tensor
    capacity_rejected_count: torch.Tensor


def _validate(
    state: FastGymState,
    catalog: FastDeathBurstCatalog,
    burst_state: FastDeathBurstState,
) -> None:
    if catalog.device != state.device or burst_state.device != state.device:
        raise ValueError("state, catalog, and burst state must use the same device")
    if tuple(burst_state.emitted_source_stable_id.shape) != tuple(state.active.shape):
        raise ValueError("burst state must have shape [batch, entities]")
    if burst_state.emitted_source_stable_id.dtype != torch.int64:
        raise ValueError("emitted_source_stable_id must be int64")
    expected = (catalog.card_count,)
    expected_types = {
        "enabled": torch.bool,
        "damage": torch.float32,
        "radius_units": torch.int32,
        "hits_air": torch.bool,
        "hits_ground": torch.bool,
        "tower_damage_multiplier": torch.float32,
        "building_damage_multiplier": torch.float32,
    }
    for name, dtype in expected_types.items():
        value = getattr(catalog, name)
        if tuple(value.shape) != expected or value.device != state.device:
            raise ValueError(f"{name} must be [cards] on the state device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")


def step_fast_death_bursts_(
    state: FastGymState,
    catalog: FastDeathBurstCatalog,
    burst_state: FastDeathBurstState,
    *,
    max_commands: int | None = None,
) -> FastDeathBurstStepResult:
    """Emit each supported lethal transition exactly once.

    A source is consumed even when command capacity rejects it.  That makes
    overflow explicit and prevents an explosion from being shifted to a later
    simulation tick.  A new stable ID in a reused physical slot is a new
    source; independently reset batch rows must call :meth:`reset_rows_`.
    """

    _validate(state, catalog, burst_state)
    command_capacity = state.max_entities if max_commands is None else max_commands
    if command_capacity < 1:
        raise ValueError("max_commands must be positive")

    batch, entities = state.active.shape
    known_card = (state.card_id > 0) & (state.card_id < catalog.card_count)
    safe_card = state.card_id.clamp(0, catalog.card_count - 1)
    profile_valid = (
        catalog.enabled[safe_card]
        & (catalog.damage[safe_card] > 0)
        & (catalog.radius_units[safe_card] > 0)
        & (catalog.hits_air[safe_card] | catalog.hits_ground[safe_card])
    )

    # Vacated slots cannot carry consumption state into a later occupant.
    burst_state.emitted_source_stable_id.masked_fill_(~state.active, 0)
    candidate = (
        state.active
        & (state.hp <= 0)
        & (state.stable_id > 0)
        & known_card
        & profile_valid
        & (burst_state.emitted_source_stable_id != state.stable_id)
        & ~state.game_over[:, None]
    )

    slots = (
        torch.arange(entities, dtype=torch.int64, device=state.device)
        .view(1, entities)
        .expand(batch, -1)
    )
    sentinel = torch.iinfo(torch.int64).max
    order_key = torch.where(
        candidate, state.stable_id, torch.full_like(state.stable_id, sentinel)
    )
    order = torch.argsort(order_key, dim=1, stable=True)

    output_rank = torch.arange(
        command_capacity, dtype=torch.int64, device=state.device
    ).view(1, -1)
    source_slot = order.gather(1, output_rank.clamp(max=entities - 1).expand(batch, -1))
    candidate_count = candidate.sum(dim=1, dtype=torch.int64)
    ready = output_rank < candidate_count[:, None]

    def ordered(value: torch.Tensor) -> torch.Tensor:
        gathered = value.gather(1, source_slot)
        return torch.where(ready, gathered, torch.zeros_like(gathered))

    ordered_card = ordered(safe_card)
    commands = FastDeathBurstCommands(
        ready=ready,
        source_slot=torch.where(
            ready, ordered(slots), torch.full_like(source_slot, -1)
        ),
        source_stable_id=ordered(state.stable_id),
        source_owner=ordered(state.owner),
        source_card_id=ordered(state.card_id),
        source_x_units=ordered(state.x_units),
        source_y_units=ordered(state.y_units),
        damage=torch.where(
            ready,
            catalog.damage[ordered_card],
            torch.zeros_like(ready, dtype=torch.float32),
        ),
        radius_units=torch.where(
            ready,
            catalog.radius_units[ordered_card],
            torch.zeros_like(ready, dtype=torch.int32),
        ),
        hits_air=ready & catalog.hits_air[ordered_card],
        hits_ground=ready & catalog.hits_ground[ordered_card],
        tower_damage_multiplier=torch.where(
            ready,
            catalog.tower_damage_multiplier[ordered_card],
            torch.zeros_like(ready, dtype=torch.float32),
        ),
        building_damage_multiplier=torch.where(
            ready,
            catalog.building_damage_multiplier[ordered_card],
            torch.zeros_like(ready, dtype=torch.float32),
        ),
    )

    # Invert the already-computed ordering to get exact source-aligned
    # overflow telemetry without a second sort or pairwise comparison plane.
    source_rank = torch.empty_like(order)
    source_rank.scatter_(1, order, slots)
    emitted_source_mask = candidate & (source_rank < command_capacity)
    capacity_rejected = candidate & ~emitted_source_mask

    # Mark accepted and rejected candidates together.  Both are terminal
    # outcomes for this lethal transition and must never replay next tick.
    burst_state.emitted_source_stable_id.copy_(
        torch.where(
            candidate,
            state.stable_id,
            burst_state.emitted_source_stable_id,
        )
    )
    return FastDeathBurstStepResult(
        commands=commands,
        processed_source_mask=candidate,
        emitted_source_mask=emitted_source_mask,
        capacity_rejected=capacity_rejected,
        emitted_count=emitted_source_mask.sum(dim=1, dtype=torch.int32),
        capacity_rejected_count=capacity_rejected.sum(dim=1, dtype=torch.int32),
    )


__all__ = [
    "FastDeathBurstCatalog",
    "FastDeathBurstCommands",
    "FastDeathBurstState",
    "FastDeathBurstStepResult",
    "step_fast_death_bursts_",
]
