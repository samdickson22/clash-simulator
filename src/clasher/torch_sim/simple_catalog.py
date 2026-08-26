"""Primitive card tables for the unified approximate Gym kernel.

The projection is deliberately mechanical: it consumes existing serialized
catalog tensors and never branches on card names or runtime Python classes.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from .catalog import CardKindOpcode, TensorCardCatalog
from .simple_state import FAST_KIND_BUILDING, FAST_KIND_TROOP


@dataclass(frozen=True)
class FastCardCatalog:
    """Only the ordinary deployment/combat scalars used by the fast kernel."""

    device: torch.device
    kind: torch.Tensor
    hitpoints: torch.Tensor
    damage: torch.Tensor
    range_units: torch.Tensor
    sight_range_units: torch.Tensor
    speed_units_per_tick: torch.Tensor
    hit_cooldown_ticks: torch.Tensor

    @classmethod
    def from_tensor_catalog(cls, catalog: TensorCardCatalog) -> FastCardCatalog:
        # Serialized hit speed is milliseconds; the native Gym clock is 50 ms.
        cooldown = torch.div(
            catalog.hit_speed_ms.to(torch.int32) + 49,
            50,
            rounding_mode="floor",
        ).clamp(min=1)
        cooldown[0] = 0
        ordinary_kind = torch.full_like(catalog.kind, -1, dtype=torch.int8)
        ordinary_kind = torch.where(
            (catalog.kind == int(CardKindOpcode.TROOP))
            | (catalog.kind == int(CardKindOpcode.CHAMPION)),
            FAST_KIND_TROOP,
            ordinary_kind,
        )
        ordinary_kind = torch.where(
            catalog.kind == int(CardKindOpcode.BUILDING),
            FAST_KIND_BUILDING,
            ordinary_kind,
        )
        return cls(
            device=catalog.kind.device,
            kind=ordinary_kind,
            hitpoints=catalog.hitpoints.to(torch.float32),
            damage=catalog.damage.to(torch.float32),
            range_units=catalog.range_units.to(torch.int32),
            sight_range_units=catalog.sight_range_units.to(torch.int32),
            speed_units_per_tick=catalog.speed_units_per_tick.to(torch.int32),
            hit_cooldown_ticks=cooldown,
        )

    @property
    def size(self) -> int:
        return int(self.kind.shape[0])
