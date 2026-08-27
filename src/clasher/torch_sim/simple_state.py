"""Small, fixed-shape state for the practical tensor Gym kernel.

This state intentionally contains only tensors and stable, dense entity slots.
It is independent of the oracle event ledger and the resident mechanic-owner
graph.  Padding slots have ``active=False`` and ``stable_id=0``.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

FAST_KIND_TROOP = 0
FAST_KIND_BUILDING = 1
FAST_WINNER_IN_PROGRESS = -2


@dataclass
class FastGymState:
    """Mutable structure-of-arrays state retained across native Gym ticks."""

    device: torch.device
    tick: torch.Tensor
    game_over: torch.Tensor
    winner: torch.Tensor
    next_stable_id: torch.Tensor
    active: torch.Tensor
    stable_id: torch.Tensor
    kind: torch.Tensor
    owner: torch.Tensor
    card_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    hp: torch.Tensor
    max_hp: torch.Tensor
    target_id: torch.Tensor
    damage: torch.Tensor
    range_units: torch.Tensor
    sight_range_units: torch.Tensor
    speed_units_per_tick: torch.Tensor
    hit_cooldown_ticks: torch.Tensor
    deploy_ticks: torch.Tensor
    cooldown_ticks: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.tick.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.active.shape[1])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_entities: int = 64,
        device: str | torch.device = "cpu",
    ) -> FastGymState:
        """Create an empty fixed-capacity batch without Python battle objects."""

        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_entities < 1:
            raise ValueError("max_entities must be positive")
        tensor_device = torch.device(device)
        if tensor_device.type == "cuda" and tensor_device.index is None:
            tensor_device = torch.device("cuda", torch.cuda.current_device())

        def zeros(*shape: int, dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=tensor_device)

        entity_shape = (batch_size, max_entities)
        return cls(
            device=tensor_device,
            tick=zeros(batch_size, dtype=torch.int64),
            game_over=zeros(batch_size, dtype=torch.bool),
            winner=torch.full(
                (batch_size,),
                FAST_WINNER_IN_PROGRESS,
                dtype=torch.int8,
                device=tensor_device,
            ),
            next_stable_id=torch.ones(
                batch_size, dtype=torch.int64, device=tensor_device
            ),
            active=zeros(*entity_shape, dtype=torch.bool),
            stable_id=zeros(*entity_shape, dtype=torch.int64),
            kind=zeros(*entity_shape, dtype=torch.int8),
            owner=zeros(*entity_shape, dtype=torch.int8),
            card_id=zeros(*entity_shape, dtype=torch.int64),
            x_units=zeros(*entity_shape, dtype=torch.int32),
            y_units=zeros(*entity_shape, dtype=torch.int32),
            hp=zeros(*entity_shape, dtype=torch.float32),
            max_hp=zeros(*entity_shape, dtype=torch.float32),
            target_id=zeros(*entity_shape, dtype=torch.int64),
            damage=zeros(*entity_shape, dtype=torch.float32),
            range_units=zeros(*entity_shape, dtype=torch.int32),
            sight_range_units=zeros(*entity_shape, dtype=torch.int32),
            speed_units_per_tick=zeros(*entity_shape, dtype=torch.int32),
            hit_cooldown_ticks=zeros(*entity_shape, dtype=torch.int32),
            deploy_ticks=zeros(*entity_shape, dtype=torch.int32),
            cooldown_ticks=zeros(*entity_shape, dtype=torch.int32),
        )

    def clone(self) -> FastGymState:
        """Return an isolated tensor clone for deterministic replay checks."""

        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name == "device":
                continue
            values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]
