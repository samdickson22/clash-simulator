"""Dense serialized river jumps for the practical tensor Gym.

The standard arena has two physical bridge openings and a water corridor
between the two banks.  Ground characters with serialized ``jumpHeight`` and
``jumpSpeed`` traverse an off-bridge corridor as one committed movement
phase.  This module owns that phase without owning ordinary navigation or
collision: callers offer a ground route segment, then consume the returned
position and eligibility planes.

Compilation may inspect card objects and names once.  The runtime is a fixed
``[batch, entities]`` tensor program keyed by stable entity identity; it has no
card-name branches or host synchronization.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from numbers import Real

import torch

from clasher.data import CardDataLoader
from clasher.native_tilemap import (
    HALF_TILE_LOGIC_UNITS,
    STANDARD_BLOCKED_RIVER_ROWS,
    STANDARD_BRIDGE_CELL_RANGES,
    STANDARD_PATH_WIDTH,
)

from .catalog import CardKindOpcode, TensorCardCatalog

FAST_RIVER_JUMP_TICK_MS = 50

_LOWER_RIVER_EDGE_UNITS = min(STANDARD_BLOCKED_RIVER_ROWS) * HALF_TILE_LOGIC_UNITS
_UPPER_RIVER_EDGE_UNITS = (max(STANDARD_BLOCKED_RIVER_ROWS) + 1) * HALF_TILE_LOGIC_UNITS
_LOWER_LANDING_Y_UNITS = _LOWER_RIVER_EDGE_UNITS - HALF_TILE_LOGIC_UNITS // 2
_UPPER_LANDING_Y_UNITS = _UPPER_RIVER_EDGE_UNITS + HALF_TILE_LOGIC_UNITS // 2
_ARENA_WIDTH_UNITS = STANDARD_PATH_WIDTH * HALF_TILE_LOGIC_UNITS
_BRIDGE_MIN_X_UNITS = tuple(
    start * HALF_TILE_LOGIC_UNITS for start, _ in STANDARD_BRIDGE_CELL_RANGES
)
_BRIDGE_MAX_X_UNITS = tuple(
    (end + 1) * HALF_TILE_LOGIC_UNITS for _, end in STANDARD_BRIDGE_CELL_RANGES
)


def _canonical_device(device: str | torch.device) -> torch.device:
    result = torch.device(device)
    if result.type == "cuda" and result.index is None:
        result = torch.device("cuda", torch.cuda.current_device())
    if result.type not in {"cpu", "cuda"}:
        raise ValueError("fast river jumps support CPU and CUDA only")
    return result


def _positive_int32(value: object) -> int | None:
    """Return an exact positive serialized integer, otherwise fail closed."""

    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or not numeric.is_integer():
        return None
    integer = int(numeric)
    if integer <= 0 or integer > torch.iinfo(torch.int32).max:
        return None
    return integer


@dataclass(frozen=True)
class FastRiverJumpCatalog:
    """Card-aligned serialized river-jump profiles."""

    device: torch.device
    declares_jump: torch.Tensor
    profile_supported: torch.Tensor
    jump_capable: torch.Tensor
    jump_height_units: torch.Tensor
    jump_speed_units_per_tick: torch.Tensor

    @property
    def size(self) -> int:
        return int(self.jump_capable.shape[0])

    @classmethod
    def compile(
        cls,
        catalog: TensorCardCatalog,
        loader: CardDataLoader,
    ) -> FastRiverJumpCatalog:
        """Compile raw character jump scalars into dense numeric planes.

        A partial, non-integral, non-positive, airborne, or non-character
        declaration remains declared but unsupported.  Defaults never turn a
        malformed production row into a jumper.
        """

        device = catalog.kind.device
        size = len(catalog.names)
        declares = torch.zeros(size, dtype=torch.bool, device=device)
        supported = torch.ones(size, dtype=torch.bool, device=device)
        capable = torch.zeros(size, dtype=torch.bool, device=device)
        height = torch.zeros(size, dtype=torch.int32, device=device)
        speed = torch.zeros(size, dtype=torch.int32, device=device)
        supported[0] = False

        character_kinds = {
            int(CardKindOpcode.TROOP),
            int(CardKindOpcode.CHAMPION),
        }
        for card_id, card_name in enumerate(catalog.names[1:], start=1):
            stats = loader.get_card(card_name)
            if stats is None:
                supported[card_id] = False
                continue
            raw = getattr(stats, "_raw_entry", {}) or {}
            character = (
                raw.get("summonCharacterData") or raw.get("summonSpellData") or {}
            )
            has_height = "jumpHeight" in character
            has_speed = "jumpSpeed" in character
            if not has_height and not has_speed:
                continue

            declares[card_id] = True
            raw_height = _positive_int32(character.get("jumpHeight"))
            raw_speed = _positive_int32(character.get("jumpSpeed"))
            compat_height = _positive_int32(getattr(stats, "jump_height", None))
            compat_speed = _positive_int32(getattr(stats, "jump_speed", None))
            kind = int(catalog.kind[card_id].item())
            valid = (
                has_height
                and has_speed
                and raw_height is not None
                and raw_speed is not None
                and raw_height == compat_height
                and raw_speed == compat_speed
                and kind in character_kinds
                and not bool(catalog.is_air_unit[card_id].item())
                and not bool(catalog.is_hover_unit[card_id].item())
            )
            if not valid:
                supported[card_id] = False
                continue

            assert raw_height is not None
            assert raw_speed is not None
            capable[card_id] = True
            height[card_id] = raw_height
            speed[card_id] = raw_speed

        return cls(
            device=device,
            declares_jump=declares,
            profile_supported=supported,
            jump_capable=capable,
            jump_height_units=height,
            jump_speed_units_per_tick=speed,
        )


@dataclass
class FastRiverJumpState:
    """Stable-ID-bound retained jump state with shape ``[B, E]``."""

    device: torch.device
    bound_stable_id: torch.Tensor
    bound_card_id: torch.Tensor
    active: torch.Tensor
    origin_x_units: torch.Tensor
    origin_y_units: torch.Tensor
    landing_x_units: torch.Tensor
    landing_y_units: torch.Tensor
    jump_speed_units_per_tick: torch.Tensor
    elapsed_ticks: torch.Tensor
    duration_ticks: torch.Tensor

    @property
    def shape(self) -> torch.Size:
        return self.active.shape

    @classmethod
    def empty(
        cls,
        batch_size: int,
        max_entities: int,
        *,
        device: str | torch.device = "cpu",
    ) -> FastRiverJumpState:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_entities < 1:
            raise ValueError("max_entities must be positive")
        tensor_device = _canonical_device(device)
        shape = (batch_size, max_entities)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=tensor_device)

        return cls(
            device=tensor_device,
            bound_stable_id=zeros(torch.int64),
            bound_card_id=zeros(torch.int64),
            active=zeros(torch.bool),
            origin_x_units=zeros(torch.int32),
            origin_y_units=zeros(torch.int32),
            landing_x_units=zeros(torch.int32),
            landing_y_units=zeros(torch.int32),
            jump_speed_units_per_tick=zeros(torch.int32),
            elapsed_ticks=zeros(torch.int32),
            duration_ticks=zeros(torch.int32),
        )

    def clone(self) -> FastRiverJumpState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]

    def clear_(self, mask: torch.Tensor) -> None:
        if mask.shape != self.shape:
            raise ValueError("mask must have shape [batch, entities]")
        if mask.device != self.device or mask.dtype != torch.bool:
            raise ValueError("mask must be bool on the state device")
        for descriptor in fields(self):
            if descriptor.name == "device":
                continue
            getattr(self, descriptor.name).masked_fill_(mask, 0)

    def reset_rows_(self, reset_mask: torch.Tensor) -> None:
        if reset_mask.shape != self.shape[:1]:
            raise ValueError("reset_mask must have shape [batch]")
        if reset_mask.device != self.device or reset_mask.dtype != torch.bool:
            raise ValueError("reset_mask must be bool on the state device")
        self.clear_(reset_mask[:, None].expand(self.shape))


@dataclass(frozen=True)
class FastRiverJumpStep:
    """Position plus integration planes produced by one 50 ms phase step."""

    x_units: torch.Tensor
    y_units: torch.Tensor
    started: torch.Tensor
    landed: torch.Tensor
    cancelled: torch.Tensor
    active: torch.Tensor
    airborne_target: torch.Tensor
    ground_target_unavailable: torch.Tensor
    ordinary_movement_blocked: torch.Tensor
    combat_blocked: torch.Tensor
    ground_collision_blocked: torch.Tensor
    special_consumed_tick: torch.Tensor
    profile_rejected: torch.Tensor


def _trunc_div(numerator: torch.Tensor, denominator: torch.Tensor) -> torch.Tensor:
    """Signed integer division without a data-dependent host validation."""

    safe = torch.clamp(denominator.to(torch.int64), min=1)
    numerator = numerator.to(torch.int64)
    return torch.where(
        numerator < 0,
        -torch.div(-numerator, safe, rounding_mode="floor"),
        torch.div(numerator, safe, rounding_mode="floor"),
    )


def _integer_sqrt(value: torch.Tensor) -> torch.Tensor:
    """Exact fixed-iteration integer square root with no device synchronization."""

    remainder = torch.clamp(value.to(torch.int64), min=0)
    result = torch.zeros_like(remainder)
    bit = 1 << 62
    for _ in range(32):
        trial = result + bit
        accepted = remainder >= trial
        remainder = torch.where(accepted, remainder - trial, remainder)
        result = torch.where(
            accepted,
            torch.bitwise_right_shift(result, 1) + bit,
            torch.bitwise_right_shift(result, 1),
        )
        bit >>= 2
    return result


def _line_x_at_y(
    x_units: torch.Tensor,
    y_units: torch.Tensor,
    route_x_units: torch.Tensor,
    route_y_units: torch.Tensor,
    sample_y_units: torch.Tensor,
) -> torch.Tensor:
    delta_x = route_x_units.to(torch.int64) - x_units.to(torch.int64)
    delta_y = route_y_units.to(torch.int64) - y_units.to(torch.int64)
    numerator = delta_x * (sample_y_units.to(torch.int64) - y_units.to(torch.int64))
    return x_units.to(torch.int64) + _trunc_div(
        numerator, torch.abs(delta_y)
    ) * torch.sign(delta_y)


def _same_bridge(x_at_lower: torch.Tensor, x_at_upper: torch.Tensor) -> torch.Tensor:
    via_bridge = torch.zeros_like(x_at_lower, dtype=torch.bool)
    for minimum, maximum in zip(_BRIDGE_MIN_X_UNITS, _BRIDGE_MAX_X_UNITS):
        via_bridge |= (
            (x_at_lower >= minimum)
            & (x_at_lower <= maximum)
            & (x_at_upper >= minimum)
            & (x_at_upper <= maximum)
        )
    return via_bridge


def _landing_x(
    projected_x: torch.Tensor,
    owner: torch.Tensor,
) -> torch.Tensor:
    """Snap to native half-tile centers with an owner-mirrored tie-break."""

    bounded = projected_x.clamp(0, _ARENA_WIDTH_UNITS - 1)
    canonical = torch.where(owner == 0, bounded, _ARENA_WIDTH_UNITS - bounded)
    canonical = canonical.clamp(0, _ARENA_WIDTH_UNITS - 1)
    cell = torch.div(canonical, HALF_TILE_LOGIC_UNITS, rounding_mode="floor")
    center = cell * HALF_TILE_LOGIC_UNITS + HALF_TILE_LOGIC_UNITS // 2
    return torch.where(owner == 0, center, _ARENA_WIDTH_UNITS - center)


def _validate_plane(
    state: FastRiverJumpState,
    name: str,
    value: torch.Tensor,
    dtype: torch.dtype,
) -> None:
    if value.shape != state.shape:
        raise ValueError(f"{name} must have shape [batch, entities]")
    if value.device != state.device:
        raise ValueError(f"{name} must use the jump state device")
    if value.dtype != dtype:
        raise ValueError(f"{name} must use {dtype}")


def step_fast_river_jump_(
    state: FastRiverJumpState,
    catalog: FastRiverJumpCatalog,
    *,
    entity_active: torch.Tensor,
    stable_id: torch.Tensor,
    card_id: torch.Tensor,
    owner: torch.Tensor,
    permanent_airborne: torch.Tensor,
    stunned: torch.Tensor,
    x_units: torch.Tensor,
    y_units: torch.Tensor,
    route_x_units: torch.Tensor,
    route_y_units: torch.Tensor,
    dt_ms: int = FAST_RIVER_JUMP_TICK_MS,
) -> FastRiverJumpStep:
    """Advance one committed river-jump phase.

    A start requires a complete off-bridge bank-to-bank route segment.  Once
    started, route changes and stun do not cancel flight; only entity removal
    or stable/card identity replacement does.  The start tick snapshots the
    landing without displacement.  Each later call advances exactly one
    serialized 50 ms speed quantum.
    """

    if dt_ms != FAST_RIVER_JUMP_TICK_MS:
        raise ValueError("fast river-jump phases require a 50 ms tick")
    if catalog.device != state.device:
        raise ValueError("catalog and jump state must share a device")
    for name, value, dtype in (
        ("entity_active", entity_active, torch.bool),
        ("stable_id", stable_id, torch.int64),
        ("card_id", card_id, torch.int64),
        ("owner", owner, torch.int8),
        ("permanent_airborne", permanent_airborne, torch.bool),
        ("stunned", stunned, torch.bool),
        ("x_units", x_units, torch.int32),
        ("y_units", y_units, torch.int32),
        ("route_x_units", route_x_units, torch.int32),
        ("route_y_units", route_y_units, torch.int32),
    ):
        _validate_plane(state, name, value, dtype)

    occupied = entity_active & (stable_id > 0)
    same_identity = (
        (state.bound_stable_id == stable_id)
        & (state.bound_card_id == card_id)
        & occupied
    )
    cancelled = state.active & ~same_identity
    stale = (state.bound_stable_id > 0) & ~same_identity
    state.clear_(stale)

    known_card = (card_id > 0) & (card_id < catalog.size)
    safe_card = card_id.clamp(0, catalog.size - 1)
    declares = catalog.declares_jump[safe_card] & known_card
    supported = catalog.profile_supported[safe_card] & known_card
    capable = catalog.jump_capable[safe_card] & supported
    valid_owner = (owner == 0) | (owner == 1)

    lower = torch.full_like(y_units, _LOWER_RIVER_EDGE_UNITS)
    upper = torch.full_like(y_units, _UPPER_RIVER_EDGE_UNITS)
    upward = (y_units <= lower) & (route_y_units >= upper)
    downward = (y_units >= upper) & (route_y_units <= lower)
    crosses_river = upward | downward
    x_at_lower = _line_x_at_y(x_units, y_units, route_x_units, route_y_units, lower)
    x_at_upper = _line_x_at_y(x_units, y_units, route_x_units, route_y_units, upper)
    through_bridge = _same_bridge(x_at_lower, x_at_upper)
    jump_corridor = crosses_river & ~through_bridge

    can_start = (
        occupied
        & ~state.active
        & known_card
        & capable
        & valid_owner
        & ~permanent_airborne
        & ~stunned
        & jump_corridor
    )
    landing_y = torch.where(
        upward,
        torch.full_like(y_units, _UPPER_LANDING_Y_UNITS),
        torch.full_like(y_units, _LOWER_LANDING_Y_UNITS),
    )
    projected_landing_x = _line_x_at_y(
        x_units,
        y_units,
        route_x_units,
        route_y_units,
        landing_y,
    )
    landing_x = _landing_x(projected_landing_x, owner).to(torch.int32)

    state.bound_stable_id.copy_(
        torch.where(can_start, stable_id, state.bound_stable_id)
    )
    state.bound_card_id.copy_(torch.where(can_start, card_id, state.bound_card_id))
    state.origin_x_units.copy_(torch.where(can_start, x_units, state.origin_x_units))
    state.origin_y_units.copy_(torch.where(can_start, y_units, state.origin_y_units))
    state.landing_x_units.copy_(
        torch.where(can_start, landing_x, state.landing_x_units)
    )
    state.landing_y_units.copy_(
        torch.where(can_start, landing_y, state.landing_y_units)
    )
    selected_speed = catalog.jump_speed_units_per_tick[safe_card]
    state.jump_speed_units_per_tick.copy_(
        torch.where(can_start, selected_speed, state.jump_speed_units_per_tick)
    )
    delta_x = landing_x.to(torch.int64) - x_units.to(torch.int64)
    delta_y = landing_y.to(torch.int64) - y_units.to(torch.int64)
    start_distance = _integer_sqrt(delta_x.square() + delta_y.square())
    start_duration = torch.div(
        start_distance + selected_speed.to(torch.int64) - 1,
        torch.clamp(selected_speed.to(torch.int64), min=1),
        rounding_mode="floor",
    ).clamp(min=1)
    state.duration_ticks.copy_(
        torch.where(can_start, start_duration.to(torch.int32), state.duration_ticks)
    )
    state.elapsed_ticks.copy_(
        torch.where(
            can_start, torch.zeros_like(state.elapsed_ticks), state.elapsed_ticks
        )
    )
    state.active |= can_start

    travelling = state.active & ~can_start
    next_elapsed = state.elapsed_ticks + travelling.to(torch.int32)
    origin = torch.stack((state.origin_x_units, state.origin_y_units), dim=-1).to(
        torch.int64
    )
    destination = torch.stack(
        (state.landing_x_units, state.landing_y_units), dim=-1
    ).to(torch.int64)
    delta = destination - origin
    distance = _integer_sqrt(torch.sum(delta.square(), dim=-1))
    progress = torch.minimum(
        next_elapsed.to(torch.int64) * state.jump_speed_units_per_tick.to(torch.int64),
        distance,
    )
    safe_distance = torch.clamp(distance, min=1)
    displacement = _trunc_div(
        delta * progress.unsqueeze(-1), safe_distance.unsqueeze(-1)
    )
    flight_position = origin + displacement
    finished = travelling & (
        (next_elapsed >= state.duration_ticks) | (progress >= distance)
    )
    flight_position = torch.where(finished.unsqueeze(-1), destination, flight_position)
    output_x = torch.where(travelling, flight_position[..., 0].to(torch.int32), x_units)
    output_y = torch.where(travelling, flight_position[..., 1].to(torch.int32), y_units)
    state.elapsed_ticks.copy_(
        torch.where(travelling, next_elapsed, state.elapsed_ticks)
    )
    state.active &= ~finished

    consumed = can_start | travelling
    return FastRiverJumpStep(
        x_units=output_x,
        y_units=output_y,
        started=can_start,
        landed=finished,
        cancelled=cancelled,
        active=state.active,
        airborne_target=state.active,
        ground_target_unavailable=state.active,
        ordinary_movement_blocked=consumed,
        combat_blocked=consumed,
        ground_collision_blocked=state.active,
        special_consumed_tick=finished,
        profile_rejected=occupied & declares & ~supported,
    )


def fast_river_jump_target_eligible(
    *,
    target_active: torch.Tensor,
    target_river_jump_active: torch.Tensor,
    source_hits_air: torch.Tensor,
    source_hits_ground: torch.Tensor,
) -> torch.Tensor:
    """Return serialized attack-plane eligibility for a possible jumper.

    A river jumper temporarily occupies the air target plane.  It is not
    invulnerable: attacks serialized to hit air remain eligible, while
    ground-only attacks lose it until landing.
    """

    shape = target_active.shape
    for name, value in (
        ("target_river_jump_active", target_river_jump_active),
        ("source_hits_air", source_hits_air),
        ("source_hits_ground", source_hits_ground),
    ):
        if value.shape != shape:
            raise ValueError(f"{name} must match target_active shape")
        if value.device != target_active.device:
            raise ValueError(f"{name} must use the target device")
        if value.dtype != torch.bool:
            raise ValueError(f"{name} must be bool")
    if target_active.dtype != torch.bool:
        raise ValueError("target_active must be bool")
    return target_active & torch.where(
        target_river_jump_active,
        source_hits_air,
        source_hits_ground,
    )
