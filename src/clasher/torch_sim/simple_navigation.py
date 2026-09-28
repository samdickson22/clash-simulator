"""Fixed-shape waypoint routing for the practical tensor Gym.

The production Gym does not need the resident verifier's exact A* heap on
every tick.  It does, however, need the standard arena's most important
topological constraint: ordinary ground entities cross the river through one
of its two bridge openings.  This module reduces that immutable topology to a
small state machine which is cheap to run for every dense entity slot.

All hot-path state is tensor resident.  Physical slots may be reused, so route
ownership is keyed by both the mover and target stable IDs rather than by slot
alone.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from clasher.native_tilemap import (
    HALF_TILE_LOGIC_UNITS,
    STANDARD_BLOCKED_RIVER_ROWS,
    STANDARD_BRIDGE_CELL_RANGES,
    STANDARD_PATH_HEIGHT,
    STANDARD_PATH_WIDTH,
)

FAST_ROUTE_DIRECT = 0
FAST_ROUTE_APPROACH_BANK = 1
FAST_ROUTE_CROSS_BRIDGE = 2

_BRIDGE_COUNT = len(STANDARD_BRIDGE_CELL_RANGES)
if _BRIDGE_COUNT != 2:
    raise RuntimeError("the standard arena must expose exactly two bridges")

# A cell range is inclusive.  Its geometric center therefore includes the
# right edge (end + 1), rather than averaging the two cell indices.
_BRIDGE_CENTER_UNITS = tuple(
    (start + end + 1) * HALF_TILE_LOGIC_UNITS // 2
    for start, end in STANDARD_BRIDGE_CELL_RANGES
)
_BRIDGE_MIN_X_UNITS = tuple(
    start * HALF_TILE_LOGIC_UNITS for start, _ in STANDARD_BRIDGE_CELL_RANGES
)
_BRIDGE_MAX_X_UNITS = tuple(
    (end + 1) * HALF_TILE_LOGIC_UNITS for _, end in STANDARD_BRIDGE_CELL_RANGES
)

_LOWER_RIVER_EDGE_UNITS = min(STANDARD_BLOCKED_RIVER_ROWS) * HALF_TILE_LOGIC_UNITS
_UPPER_RIVER_EDGE_UNITS = (max(STANDARD_BLOCKED_RIVER_ROWS) + 1) * HALF_TILE_LOGIC_UNITS
_RIVER_CENTER_UNITS = (_LOWER_RIVER_EDGE_UNITS + _UPPER_RIVER_EDGE_UNITS) // 2
_LOWER_BANK_WAYPOINT_UNITS = _LOWER_RIVER_EDGE_UNITS - HALF_TILE_LOGIC_UNITS
_UPPER_BANK_WAYPOINT_UNITS = _UPPER_RIVER_EDGE_UNITS + HALF_TILE_LOGIC_UNITS

FAST_ARENA_WIDTH_UNITS = STANDARD_PATH_WIDTH * HALF_TILE_LOGIC_UNITS
FAST_ARENA_HEIGHT_UNITS = STANDARD_PATH_HEIGHT * HALF_TILE_LOGIC_UNITS
# Collision uses the physical opening edges; route cells use their centre
# envelope above. A mover radius is subtracted once by the terrain resolver.
FAST_BRIDGE_MIN_X_UNITS = tuple(
    value - HALF_TILE_LOGIC_UNITS for value in _BRIDGE_MIN_X_UNITS
)
FAST_BRIDGE_MAX_X_UNITS = tuple(
    value + HALF_TILE_LOGIC_UNITS for value in _BRIDGE_MAX_X_UNITS
)
FAST_LOWER_RIVER_EDGE_UNITS = _LOWER_RIVER_EDGE_UNITS
FAST_UPPER_RIVER_EDGE_UNITS = _UPPER_RIVER_EDGE_UNITS


def _canonical_device(device: str | torch.device) -> torch.device:
    result = torch.device(device)
    if result.type == "cuda" and result.index is None:
        result = torch.device("cuda", torch.cuda.current_device())
    if result.type == "mps" and result.index is None:
        result = torch.empty(0, device=result).device
    if result.type not in {"cpu", "cuda", "mps"}:
        raise ValueError("fast arena navigation supports CPU, CUDA, and MPS only")
    return result


@dataclass
class FastNavigationState:
    """Dense retained route state for one fixed-capacity entity batch."""

    device: torch.device
    mover_stable_id: torch.Tensor
    target_stable_id: torch.Tensor
    route_phase: torch.Tensor
    bridge_index: torch.Tensor
    travel_direction: torch.Tensor

    @classmethod
    def empty(
        cls,
        batch_size: int,
        max_entities: int,
        *,
        device: str | torch.device = "cpu",
    ) -> FastNavigationState:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_entities < 1:
            raise ValueError("max_entities must be positive")
        tensor_device = _canonical_device(device)
        shape = (batch_size, max_entities)
        return cls(
            device=tensor_device,
            mover_stable_id=torch.zeros(shape, dtype=torch.int64, device=tensor_device),
            target_stable_id=torch.zeros(
                shape, dtype=torch.int64, device=tensor_device
            ),
            route_phase=torch.zeros(shape, dtype=torch.int8, device=tensor_device),
            bridge_index=torch.full(shape, -1, dtype=torch.int8, device=tensor_device),
            travel_direction=torch.zeros(shape, dtype=torch.int8, device=tensor_device),
        )

    @property
    def shape(self) -> torch.Size:
        return self.route_phase.shape

    def clone(self) -> FastNavigationState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]

    def reset_(self, mask: torch.Tensor | None = None) -> None:
        """Clear all routes, or only the selected dense entity lanes."""

        if mask is None:
            self.mover_stable_id.zero_()
            self.target_stable_id.zero_()
            self.route_phase.zero_()
            self.bridge_index.fill_(-1)
            self.travel_direction.zero_()
            return
        if mask.shape != self.shape or mask.device != self.device:
            raise ValueError("reset mask must match navigation state shape and device")
        if mask.dtype != torch.bool:
            raise ValueError("reset mask must be bool")
        self.mover_stable_id.masked_fill_(mask, 0)
        self.target_stable_id.masked_fill_(mask, 0)
        self.route_phase.masked_fill_(mask, FAST_ROUTE_DIRECT)
        self.bridge_index.masked_fill_(mask, -1)
        self.travel_direction.masked_fill_(mask, 0)


@dataclass(frozen=True)
class FastNavigationResult:
    """Destination waypoints and retained route metadata for every slot."""

    waypoint_x_units: torch.Tensor
    waypoint_y_units: torch.Tensor
    route_phase: torch.Tensor
    bridge_index: torch.Tensor
    routed_via_bridge: torch.Tensor


class FastArenaNavigation:
    """Canonical two-bridge route state machine for a dense entity batch."""

    def __init__(self, state: FastNavigationState) -> None:
        self.state = state
        device = state.device
        self._bridge_x = torch.tensor(
            _BRIDGE_CENTER_UNITS, dtype=torch.int32, device=device
        )
        self._bridge_min_x = torch.tensor(
            _BRIDGE_MIN_X_UNITS, dtype=torch.int32, device=device
        )
        self._bridge_max_x = torch.tensor(
            _BRIDGE_MAX_X_UNITS, dtype=torch.int32, device=device
        )

    def _validate_inputs(
        self,
        named: tuple[tuple[str, torch.Tensor, torch.dtype], ...],
    ) -> None:
        for name, value, dtype in named:
            if value.shape != self.state.shape:
                raise ValueError(f"{name} must match navigation state shape")
            if value.device != self.state.device:
                raise ValueError(f"{name} must use the navigation state device")
            if value.dtype != dtype:
                raise ValueError(f"{name} must use {dtype}")

    @staticmethod
    def _arena_side(y_units: torch.Tensor, owner: torch.Tensor) -> torch.Tensor:
        """Classify the centerline with the mirrored owner-relative tie-break."""

        return torch.where(
            y_units < _RIVER_CENTER_UNITS,
            torch.zeros_like(owner),
            torch.where(
                y_units > _RIVER_CENTER_UNITS,
                torch.ones_like(owner),
                owner,
            ),
        )

    def route_(
        self,
        *,
        active: torch.Tensor,
        mover_stable_id: torch.Tensor,
        owner: torch.Tensor,
        airborne: torch.Tensor,
        hover: torch.Tensor | None = None,
        x_units: torch.Tensor,
        y_units: torch.Tensor,
        target_stable_id: torch.Tensor,
        target_owner: torch.Tensor,
        target_x_units: torch.Tensor,
        target_y_units: torch.Tensor,
    ) -> FastNavigationResult:
        """Update route phases and return the next waypoint for every slot.

        Inputs and outputs have shape ``[batch, entities]``.  Inactive lanes,
        absent targets, and airborne movers have no retained bridge route.
        Ground routes lock their chosen bridge until the far-bank waypoint is
        reached or either stable identity changes.
        """

        if hover is None:
            hover = torch.zeros_like(airborne)
        named = (
            ("active", active, torch.bool),
            ("mover_stable_id", mover_stable_id, torch.int64),
            ("owner", owner, torch.int8),
            ("airborne", airborne, torch.bool),
            ("hover", hover, torch.bool),
            ("x_units", x_units, torch.int32),
            ("y_units", y_units, torch.int32),
            ("target_stable_id", target_stable_id, torch.int64),
            ("target_owner", target_owner, torch.int8),
            ("target_x_units", target_x_units, torch.int32),
            ("target_y_units", target_y_units, torch.int32),
        )
        self._validate_inputs(named)

        state = self.state
        valid = active & (mover_stable_id > 0) & (target_stable_id > 0)
        terrain_bypass = airborne | hover
        ground = valid & ~terrain_bypass
        identity_changed = (state.mover_stable_id != mover_stable_id) | (
            state.target_stable_id != target_stable_id
        )

        mover_side = self._arena_side(y_units, owner)
        target_side = self._arena_side(target_y_units, target_owner)
        needs_crossing = ground & (mover_side != target_side)
        new_route = identity_changed | (state.route_phase == FAST_ROUTE_DIRECT)
        start_crossing = needs_crossing & new_route

        upward = target_side > mover_side
        direction = torch.where(
            upward,
            torch.ones_like(state.travel_direction),
            -torch.ones_like(state.travel_direction),
        )
        near_y = torch.where(
            upward,
            torch.full_like(y_units, _LOWER_BANK_WAYPOINT_UNITS),
            torch.full_like(y_units, _UPPER_BANK_WAYPOINT_UNITS),
        )
        far_y = torch.where(
            upward,
            torch.full_like(y_units, _UPPER_BANK_WAYPOINT_UNITS),
            torch.full_like(y_units, _LOWER_BANK_WAYPOINT_UNITS),
        )

        source_x = x_units.to(torch.float32)
        source_y = y_units.to(torch.float32)
        destination_x = target_x_units.to(torch.float32)
        destination_y = target_y_units.to(torch.float32)
        bridge_x = self._bridge_x.to(torch.float32).view(1, 1, _BRIDGE_COUNT)
        near = near_y.to(torch.float32).unsqueeze(-1)
        far = far_y.to(torch.float32).unsqueeze(-1)
        near_distance = torch.sqrt(
            (bridge_x - source_x.unsqueeze(-1)).square()
            + (near - source_y.unsqueeze(-1)).square()
        )
        far_distance = torch.sqrt(
            (destination_x.unsqueeze(-1) - bridge_x).square()
            + (destination_y.unsqueeze(-1) - far).square()
        )
        route_cost = near_distance + far_distance
        left_better = route_cost[..., 0] < route_cost[..., 1]
        tied = route_cost[..., 0] == route_cost[..., 1]
        choose_left = left_better | (tied & (owner == 0))
        selected_bridge = torch.where(
            choose_left,
            torch.zeros_like(state.bridge_index),
            torch.ones_like(state.bridge_index),
        )

        clear = ~valid | terrain_bypass | (identity_changed & ~needs_crossing)
        state.route_phase.copy_(
            torch.where(clear, FAST_ROUTE_DIRECT, state.route_phase)
        )
        state.bridge_index.copy_(torch.where(clear, -1, state.bridge_index))
        state.travel_direction.copy_(torch.where(clear, 0, state.travel_direction))
        state.route_phase.copy_(
            torch.where(start_crossing, FAST_ROUTE_APPROACH_BANK, state.route_phase)
        )
        state.bridge_index.copy_(
            torch.where(start_crossing, selected_bridge, state.bridge_index)
        )
        state.travel_direction.copy_(
            torch.where(start_crossing, direction, state.travel_direction)
        )

        safe_bridge = state.bridge_index.to(torch.int64).clamp(0, _BRIDGE_COUNT - 1)
        route_bridge_x = self._bridge_x[safe_bridge]
        bridge_min_x = self._bridge_min_x[safe_bridge]
        bridge_max_x = self._bridge_max_x[safe_bridge]
        in_bridge = (x_units >= bridge_min_x) & (x_units <= bridge_max_x)

        route_upward = state.travel_direction > 0
        retained_near_y = torch.where(
            route_upward,
            torch.full_like(y_units, _LOWER_BANK_WAYPOINT_UNITS),
            torch.full_like(y_units, _UPPER_BANK_WAYPOINT_UNITS),
        )
        retained_far_y = torch.where(
            route_upward,
            torch.full_like(y_units, _UPPER_BANK_WAYPOINT_UNITS),
            torch.full_like(y_units, _LOWER_BANK_WAYPOINT_UNITS),
        )
        reached_near = in_bridge & torch.where(
            route_upward,
            y_units >= retained_near_y,
            y_units <= retained_near_y,
        )
        enter_bridge = (state.route_phase == FAST_ROUTE_APPROACH_BANK) & reached_near
        state.route_phase.copy_(
            torch.where(enter_bridge, FAST_ROUTE_CROSS_BRIDGE, state.route_phase)
        )

        reached_far = torch.where(
            route_upward,
            y_units >= retained_far_y,
            y_units <= retained_far_y,
        )
        finish_crossing = (state.route_phase == FAST_ROUTE_CROSS_BRIDGE) & reached_far
        state.route_phase.copy_(
            torch.where(finish_crossing, FAST_ROUTE_DIRECT, state.route_phase)
        )
        state.bridge_index.copy_(torch.where(finish_crossing, -1, state.bridge_index))
        state.travel_direction.copy_(
            torch.where(finish_crossing, 0, state.travel_direction)
        )

        retain_identity = valid & ~terrain_bypass
        state.mover_stable_id.copy_(torch.where(retain_identity, mover_stable_id, 0))
        state.target_stable_id.copy_(torch.where(retain_identity, target_stable_id, 0))

        approach = state.route_phase == FAST_ROUTE_APPROACH_BANK
        crossing = state.route_phase == FAST_ROUTE_CROSS_BRIDGE
        waypoint_x = torch.where(
            approach | crossing,
            route_bridge_x,
            target_x_units,
        )
        waypoint_y = torch.where(
            approach,
            retained_near_y,
            torch.where(crossing, retained_far_y, target_y_units),
        )
        return FastNavigationResult(
            waypoint_x_units=waypoint_x,
            waypoint_y_units=waypoint_y,
            route_phase=state.route_phase,
            bridge_index=state.bridge_index,
            routed_via_bridge=approach | crossing,
        )
