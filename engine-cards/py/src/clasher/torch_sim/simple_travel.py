"""Dense special-travel state for the practical tensor Gym.

Setup compiles serialized movement declarations and raw balance scalars into
card-aligned tensors.  The tick kernel then operates only on numeric planes:
there are no card-name branches, Python entity objects, or device-to-host
transfers in the runtime path.

The state is bound to stable entity identities rather than physical slots.
Windups may be interrupted, while committed travel retains its destination.
Terminal damage and displacement are returned as fixed-shape commands so the
owning runtime remains the sole authority for HP and world-position mutation.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, fields
from numbers import Real

import torch

from clasher.data import CardDataLoader

from .catalog import MECHANIC_OPCODE, TensorCardCatalog
from .simple_impulse import FastRadialImpulseInputs

FAST_TRAVEL_UNSUPPORTED = -1
FAST_TRAVEL_NONE = 0
FAST_TRAVEL_DASH = 1
FAST_TRAVEL_LEAP = 2
FAST_TRAVEL_UNDERGROUND = 3

FAST_TRAVEL_IDLE = 0
FAST_TRAVEL_WINDUP = 1
FAST_TRAVEL_TRANSIT = 2
FAST_TRAVEL_LANDING = 3
FAST_TRAVEL_EMERGENCE = 4

FAST_TRAVEL_IMPACT_NONE = 0
FAST_TRAVEL_IMPACT_DIRECT = 1
FAST_TRAVEL_IMPACT_AREA = 2

LOGIC_TICK_MS = 50
DEFAULT_MINER_ORIGIN_X_UNITS = 9_000
DEFAULT_MINER_BLUE_ORIGIN_Y_UNITS = 2_500
DEFAULT_ARENA_HEIGHT_UNITS = 32_000


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _number(mapping: Mapping[str, object], name: str) -> float | None:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _positive_int(mapping: Mapping[str, object], name: str) -> int | None:
    value = _number(mapping, name)
    if value is None or value <= 0:
        return None
    rounded = round(value)
    return rounded if math.isclose(value, rounded, abs_tol=1e-6) else None


def _ticks(milliseconds: int | None) -> int | None:
    if milliseconds is None or milliseconds <= 0:
        return None
    return (milliseconds + LOGIC_TICK_MS - 1) // LOGIC_TICK_MS


def _scaled_damage(card: object, raw_damage: int | None) -> float | None:
    if raw_damage is None:
        return None
    scaler = getattr(card, "get_scaled_stat", None)
    if not callable(scaler):
        return None
    value = scaler(raw_damage)
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    result = float(value)
    return result if math.isfinite(result) and result > 0 else None


@dataclass(frozen=True)
class FastTravelCatalog:
    """Card-aligned special-travel profiles compiled at setup time."""

    device: torch.device
    kind: torch.Tensor
    declares_travel: torch.Tensor
    profile_supported: torch.Tensor
    min_range_units: torch.Tensor
    max_range_units: torch.Tensor
    windup_ticks: torch.Tensor
    speed_units_per_tick: torch.Tensor
    transit_ticks: torch.Tensor
    landing_ticks: torch.Tensor
    emergence_ticks: torch.Tensor
    post_immunity_ticks: torch.Tensor
    direct_damage: torch.Tensor
    tower_damage: torch.Tensor
    spawn_damage: torch.Tensor
    impact_radius_units: torch.Tensor
    impact_push_units: torch.Tensor

    @property
    def size(self) -> int:
        return int(self.kind.shape[0])

    @classmethod
    def compile(
        cls,
        catalog: TensorCardCatalog,
        loader: CardDataLoader,
    ) -> FastTravelCatalog:
        """Compile unique, complete profiles; malformed declarations reject.

        Operation identity comes from ``TensorCardCatalog``.  Raw balance data
        supplies authoritative logic-unit, timing, and damage scalars.  Exactly
        one travel-family opcode is required for a declared profile.
        """

        device = catalog.mechanic_opcode.device
        size = len(catalog.names)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        kind = zeros(torch.int8)
        declares = zeros(torch.bool)
        supported = torch.ones(size, dtype=torch.bool, device=device)
        minimum = zeros(torch.int32)
        maximum = zeros(torch.int32)
        windup = zeros(torch.int32)
        speed = zeros(torch.int32)
        transit = zeros(torch.int32)
        landing = zeros(torch.int32)
        emergence = zeros(torch.int32)
        immunity = zeros(torch.int32)
        direct_damage = zeros(torch.float32)
        tower_damage = zeros(torch.float32)
        spawn_damage = zeros(torch.float32)
        radius = zeros(torch.int32)
        push = zeros(torch.int32)

        dash_opcode = int(MECHANIC_OPCODE["BanditDash"])
        leap_opcode = int(MECHANIC_OPCODE["MegaKnightSlam"])
        underground_opcode = int(MECHANIC_OPCODE["UndergroundDeployment"])
        crown_opcode = int(MECHANIC_OPCODE["CrownTowerScaling"])
        travel_opcodes = (dash_opcode, leap_opcode, underground_opcode)
        crown_parameter = (
            catalog.mechanic_parameter_names.index("crown_tower_damage")
            if "crown_tower_damage" in catalog.mechanic_parameter_names
            else -1
        )

        for card_id, name in enumerate(catalog.names[1:], start=1):
            operation_count = int(catalog.mechanic_count[card_id].item())
            operations = catalog.mechanic_opcode[card_id, :operation_count]
            travel_slots = torch.stack(
                tuple(operations == opcode for opcode in travel_opcodes), dim=0
            ).any(dim=0)
            family_count = int(travel_slots.sum().item())
            if family_count == 0:
                continue
            declares[card_id] = True
            valid = family_count == 1
            slot = int(travel_slots.to(torch.int8).argmax().item())
            opcode = int(operations[slot].item())
            valid &= not bool(catalog.mechanic_nested_payload[card_id, slot].item())

            card = loader.get_card(name)
            raw = _mapping({} if card is None else getattr(card, "_raw_entry", {}))
            character = _mapping(raw.get("summonCharacterData"))
            projectile = _mapping(raw.get("projectileData"))
            valid &= card is not None

            if opcode == dash_opcode:
                min_value = _positive_int(character, "dashMinRange")
                max_value = _positive_int(character, "dashMaxRange")
                windup_value = _ticks(_positive_int(character, "dashCooldown"))
                speed_value = _positive_int(character, "jumpSpeed")
                immune_value = _ticks(
                    _positive_int(character, "dashImmuneToDamageTime")
                )
                damage_value = _scaled_damage(
                    card, _positive_int(character, "dashDamage")
                )
                valid &= (
                    min_value is not None
                    and max_value is not None
                    and max_value >= min_value
                    and windup_value is not None
                    and speed_value is not None
                    and immune_value is not None
                    and damage_value is not None
                )
                if valid:
                    assert min_value is not None
                    assert max_value is not None
                    assert windup_value is not None
                    assert speed_value is not None
                    assert immune_value is not None
                    assert damage_value is not None
                    kind[card_id] = FAST_TRAVEL_DASH
                    minimum[card_id] = min_value
                    maximum[card_id] = max_value
                    windup[card_id] = windup_value
                    speed[card_id] = speed_value
                    immunity[card_id] = immune_value
                    direct_damage[card_id] = damage_value
                    tower_damage[card_id] = damage_value
            elif opcode == leap_opcode:
                min_value = _positive_int(character, "dashMinRange")
                max_value = _positive_int(character, "dashMaxRange")
                windup_value = _ticks(_positive_int(character, "dashCooldown"))
                transit_value = _ticks(_positive_int(character, "dashConstantTime"))
                landing_value = _ticks(_positive_int(character, "dashLandingTime"))
                damage_value = _scaled_damage(
                    card, _positive_int(character, "dashDamage")
                )
                spawn_value = _scaled_damage(card, _positive_int(projectile, "damage"))
                radius_value = _positive_int(character, "dashRadius")
                projectile_radius = _positive_int(projectile, "radius")
                push_value = _positive_int(character, "dashPushBack")
                projectile_push = _positive_int(projectile, "pushback")
                valid &= (
                    min_value is not None
                    and max_value is not None
                    and max_value >= min_value
                    and windup_value is not None
                    and transit_value is not None
                    and landing_value is not None
                    and damage_value is not None
                    and spawn_value is not None
                    and radius_value is not None
                    and radius_value == projectile_radius
                    and push_value is not None
                    and push_value == projectile_push
                )
                if valid:
                    assert min_value is not None
                    assert max_value is not None
                    assert windup_value is not None
                    assert transit_value is not None
                    assert landing_value is not None
                    assert damage_value is not None
                    assert spawn_value is not None
                    assert radius_value is not None
                    assert push_value is not None
                    kind[card_id] = FAST_TRAVEL_LEAP
                    minimum[card_id] = min_value
                    maximum[card_id] = max_value
                    windup[card_id] = windup_value
                    transit[card_id] = transit_value
                    landing[card_id] = landing_value
                    direct_damage[card_id] = damage_value
                    tower_damage[card_id] = damage_value
                    spawn_damage[card_id] = spawn_value
                    radius[card_id] = radius_value
                    push[card_id] = push_value
            elif opcode == underground_opcode:
                speed_value = _positive_int(character, "spawnPathfindSpeed")
                if speed_value is None:
                    speed_value = _positive_int(raw, "spawnPathfindSpeed")
                emergence_value = _ticks(_positive_int(character, "deployTime"))
                damage_value = _scaled_damage(card, _positive_int(character, "damage"))
                crown_slots = operations == crown_opcode
                crown_count = int(crown_slots.sum().item())
                crown_value: float | None = None
                if crown_count == 1 and crown_parameter >= 0:
                    crown_slot = int(crown_slots.to(torch.int8).argmax().item())
                    candidate = float(
                        catalog.mechanic_parameters[
                            card_id, crown_slot, crown_parameter
                        ].item()
                    )
                    if math.isfinite(candidate) and candidate > 0:
                        crown_value = candidate
                valid &= (
                    speed_value is not None
                    and emergence_value is not None
                    and damage_value is not None
                    and crown_value is not None
                )
                if valid:
                    assert speed_value is not None
                    assert emergence_value is not None
                    assert damage_value is not None
                    assert crown_value is not None
                    kind[card_id] = FAST_TRAVEL_UNDERGROUND
                    speed[card_id] = speed_value
                    emergence[card_id] = emergence_value
                    direct_damage[card_id] = damage_value
                    tower_damage[card_id] = crown_value
            else:
                valid = False

            if not valid:
                supported[card_id] = False
                kind[card_id] = FAST_TRAVEL_UNSUPPORTED
                for plane in (
                    minimum,
                    maximum,
                    windup,
                    speed,
                    transit,
                    landing,
                    emergence,
                    immunity,
                    direct_damage,
                    tower_damage,
                    spawn_damage,
                    radius,
                    push,
                ):
                    plane[card_id] = 0

        return cls(
            device=device,
            kind=kind,
            declares_travel=declares,
            profile_supported=supported,
            min_range_units=minimum,
            max_range_units=maximum,
            windup_ticks=windup,
            speed_units_per_tick=speed,
            transit_ticks=transit,
            landing_ticks=landing,
            emergence_ticks=emergence,
            post_immunity_ticks=immunity,
            direct_damage=direct_damage,
            tower_damage=tower_damage,
            spawn_damage=spawn_damage,
            impact_radius_units=radius,
            impact_push_units=push,
        )


@dataclass
class FastTravelState:
    """Stable-ID-bound special-travel state, with every plane ``[B, E]``."""

    device: torch.device
    bound_stable_id: torch.Tensor
    bound_card_id: torch.Tensor
    kind: torch.Tensor
    phase: torch.Tensor
    phase_ticks: torch.Tensor
    target_stable_id: torch.Tensor
    origin_x_units: torch.Tensor
    origin_y_units: torch.Tensor
    destination_x_units: torch.Tensor
    destination_y_units: torch.Tensor
    post_immunity_ticks: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.phase.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.phase.shape[1])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_entities: int,
        device: str | torch.device = "cpu",
    ) -> FastTravelState:
        if batch_size < 1 or max_entities < 1:
            raise ValueError("batch_size and max_entities must be positive")
        tensor_device = torch.device(device)
        if tensor_device.type == "cuda" and tensor_device.index is None:
            tensor_device = torch.device("cuda", torch.cuda.current_device())
        shape = (batch_size, max_entities)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=tensor_device)

        return cls(
            device=tensor_device,
            bound_stable_id=zeros(torch.int64),
            bound_card_id=zeros(torch.int64),
            kind=zeros(torch.int8),
            phase=zeros(torch.int8),
            phase_ticks=zeros(torch.int32),
            target_stable_id=zeros(torch.int64),
            origin_x_units=zeros(torch.int32),
            origin_y_units=zeros(torch.int32),
            destination_x_units=zeros(torch.int32),
            destination_y_units=zeros(torch.int32),
            post_immunity_ticks=zeros(torch.int32),
        )

    def clone(self) -> FastTravelState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]

    def clear_(self, mask: torch.Tensor) -> None:
        _validate_plane(self, "mask", mask, torch.bool)
        for descriptor in fields(self):
            if descriptor.name != "device":
                getattr(self, descriptor.name).masked_fill_(mask, 0)

    def reset_rows_(self, reset_mask: torch.Tensor) -> None:
        if tuple(reset_mask.shape) != (self.batch_size,):
            raise ValueError("reset_mask must have shape [batch]")
        if reset_mask.device != self.device or reset_mask.dtype != torch.bool:
            raise ValueError("reset_mask must be bool on the state device")
        self.clear_(reset_mask[:, None].expand(-1, self.max_entities))


@dataclass(frozen=True)
class FastTravelView:
    current: torch.Tensor
    profile_rejected: torch.Tensor
    special_active: torch.Tensor
    target_unavailable: torch.Tensor
    immune: torch.Tensor
    combat_blocked: torch.Tensor
    movement_blocked: torch.Tensor


@dataclass(frozen=True)
class FastTravelImpactCommands:
    """One fixed impact lane per entity; invalid lanes are zero-filled."""

    valid: torch.Tensor
    kind: torch.Tensor
    source_stable_id: torch.Tensor
    source_card_id: torch.Tensor
    source_owner: torch.Tensor
    target_stable_id: torch.Tensor
    center_x_units: torch.Tensor
    center_y_units: torch.Tensor
    damage: torch.Tensor
    tower_damage: torch.Tensor
    radius_units: torch.Tensor
    push_units: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    spawn_impact: torch.Tensor


@dataclass(frozen=True)
class FastTravelStepResult:
    x_units: torch.Tensor
    y_units: torch.Tensor
    view: FastTravelView
    impact: FastTravelImpactCommands
    stale_cleared: torch.Tensor
    initialized: torch.Tensor
    profile_rejected: torch.Tensor
    started: torch.Tensor
    cancelled: torch.Tensor
    arrived: torch.Tensor
    completed: torch.Tensor


def _validate_plane(
    state: FastTravelState,
    name: str,
    value: torch.Tensor,
    dtype: torch.dtype,
) -> None:
    if tuple(value.shape) != (state.batch_size, state.max_entities):
        raise ValueError(f"{name} must have shape [batch, entities]")
    if value.device != state.device or value.dtype != dtype:
        raise ValueError(f"{name} must use {dtype} on the state device")


def fast_travel_view(
    state: FastTravelState,
    *,
    active: torch.Tensor,
    stable_id: torch.Tensor,
    card_id: torch.Tensor,
) -> FastTravelView:
    """Derive targeting, damage, combat, and movement gates without mutation."""

    for name, value, dtype in (
        ("active", active, torch.bool),
        ("stable_id", stable_id, torch.int64),
        ("card_id", card_id, torch.int64),
    ):
        _validate_plane(state, name, value, dtype)
    current = (
        active
        & (state.bound_stable_id > 0)
        & (state.bound_stable_id == stable_id)
        & (state.bound_card_id == card_id)
    )
    rejected = current & (state.kind == FAST_TRAVEL_UNSUPPORTED)
    special = current & (state.phase != FAST_TRAVEL_IDLE) & ~rejected
    protected_transit = special & (
        ((state.kind == FAST_TRAVEL_DASH) & (state.phase == FAST_TRAVEL_TRANSIT))
        | (
            (state.kind == FAST_TRAVEL_LEAP)
            & (
                (state.phase == FAST_TRAVEL_TRANSIT)
                | (state.phase == FAST_TRAVEL_LANDING)
            )
        )
        | (
            (state.kind == FAST_TRAVEL_UNDERGROUND)
            & (
                (state.phase == FAST_TRAVEL_TRANSIT)
                | (state.phase == FAST_TRAVEL_EMERGENCE)
            )
        )
    )
    immune = protected_transit | (current & (state.post_immunity_ticks > 0))
    return FastTravelView(
        current=current,
        profile_rejected=rejected,
        special_active=special,
        target_unavailable=protected_transit | rejected,
        immune=immune,
        combat_blocked=special | rejected,
        movement_blocked=special | rejected,
    )


def _move_towards(
    x_units: torch.Tensor,
    y_units: torch.Tensor,
    destination_x_units: torch.Tensor,
    destination_y_units: torch.Tensor,
    work_units: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    dx = destination_x_units.to(torch.float32) - x_units.to(torch.float32)
    dy = destination_y_units.to(torch.float32) - y_units.to(torch.float32)
    distance = torch.sqrt(dx.square() + dy.square())
    work = work_units.clamp_min(0).to(torch.float32)
    arrived = distance <= work
    scale = torch.minimum(work / distance.clamp_min(1.0), torch.ones_like(distance))
    next_x = torch.round(x_units.to(torch.float32) + dx * scale).to(torch.int32)
    next_y = torch.round(y_units.to(torch.float32) + dy * scale).to(torch.int32)
    next_x = torch.where(arrived, destination_x_units, next_x)
    next_y = torch.where(arrived, destination_y_units, next_y)
    return next_x, next_y, arrived


def _empty_impact(state: FastTravelState) -> FastTravelImpactCommands:
    shape = (state.batch_size, state.max_entities)

    def zeros(dtype: torch.dtype) -> torch.Tensor:
        return torch.zeros(shape, dtype=dtype, device=state.device)

    return FastTravelImpactCommands(
        valid=zeros(torch.bool),
        kind=zeros(torch.int8),
        source_stable_id=zeros(torch.int64),
        source_card_id=zeros(torch.int64),
        source_owner=zeros(torch.int8),
        target_stable_id=zeros(torch.int64),
        center_x_units=zeros(torch.int32),
        center_y_units=zeros(torch.int32),
        damage=zeros(torch.float32),
        tower_damage=zeros(torch.float32),
        radius_units=zeros(torch.int32),
        push_units=zeros(torch.int32),
        hits_air=zeros(torch.bool),
        hits_ground=zeros(torch.bool),
        spawn_impact=zeros(torch.bool),
    )


def advance_fast_travel_(
    catalog: FastTravelCatalog,
    state: FastTravelState,
    *,
    active: torch.Tensor,
    stable_id: torch.Tensor,
    card_id: torch.Tensor,
    owner: torch.Tensor,
    x_units: torch.Tensor,
    y_units: torch.Tensor,
    spawned: torch.Tensor,
    trigger: torch.Tensor,
    target_stable_id: torch.Tensor,
    target_x_units: torch.Tensor,
    target_y_units: torch.Tensor,
    target_distance_units: torch.Tensor,
    target_valid: torch.Tensor,
    interrupted: torch.Tensor,
    miner_origin_x_units: int = DEFAULT_MINER_ORIGIN_X_UNITS,
    miner_blue_origin_y_units: int = DEFAULT_MINER_BLUE_ORIGIN_Y_UNITS,
    arena_height_units: int = DEFAULT_ARENA_HEIGHT_UNITS,
) -> FastTravelStepResult:
    """Advance every special-travel lane by one 50 ms logic tick.

    ``target_*`` is both the acquisition input for idle lanes and the current
    target observation for a retained snapshot.  Windup cancellation therefore
    fails closed if that positive stable identity is no longer current.
    """

    if catalog.device != state.device:
        raise ValueError("catalog and travel state must share a device")
    for name, value, dtype in (
        ("active", active, torch.bool),
        ("stable_id", stable_id, torch.int64),
        ("card_id", card_id, torch.int64),
        ("owner", owner, torch.int8),
        ("x_units", x_units, torch.int32),
        ("y_units", y_units, torch.int32),
        ("spawned", spawned, torch.bool),
        ("trigger", trigger, torch.bool),
        ("target_stable_id", target_stable_id, torch.int64),
        ("target_x_units", target_x_units, torch.int32),
        ("target_y_units", target_y_units, torch.int32),
        ("target_distance_units", target_distance_units, torch.int32),
        ("target_valid", target_valid, torch.bool),
        ("interrupted", interrupted, torch.bool),
    ):
        _validate_plane(state, name, value, dtype)

    occupied = state.bound_stable_id > 0
    current_before = (
        active
        & occupied
        & (stable_id == state.bound_stable_id)
        & (card_id == state.bound_card_id)
    )
    stale = occupied & ~current_before
    state.clear_(stale)

    known = (stable_id > 0) & (card_id > 0) & (card_id < catalog.size)
    initialized = spawned & active & known
    safe_card = card_id.clamp(0, catalog.size - 1)
    selected_kind = catalog.kind[safe_card]
    owner_valid = (owner == 0) | (owner == 1)
    profile_rejected = initialized & (
        ~catalog.profile_supported[safe_card]
        | ((selected_kind == FAST_TRAVEL_UNDERGROUND) & ~owner_valid)
    )
    bound_kind = torch.where(
        profile_rejected,
        torch.full_like(selected_kind, FAST_TRAVEL_UNSUPPORTED),
        selected_kind,
    )
    state.bound_stable_id.copy_(
        torch.where(initialized, stable_id, state.bound_stable_id)
    )
    state.bound_card_id.copy_(torch.where(initialized, card_id, state.bound_card_id))
    state.kind.copy_(torch.where(initialized, bound_kind, state.kind))
    state.phase.masked_fill_(initialized, FAST_TRAVEL_IDLE)
    state.phase_ticks.masked_fill_(initialized, 0)
    state.target_stable_id.masked_fill_(initialized, 0)
    state.post_immunity_ticks.masked_fill_(initialized, 0)

    x_next = x_units.clone()
    y_next = y_units.clone()
    miner_spawn = (
        initialized & ~profile_rejected & (selected_kind == FAST_TRAVEL_UNDERGROUND)
    )
    miner_origin_x = torch.full_like(x_units, int(miner_origin_x_units))
    blue_origin_y = torch.full_like(y_units, int(miner_blue_origin_y_units))
    red_origin_y = torch.full_like(
        y_units, int(arena_height_units - miner_blue_origin_y_units)
    )
    miner_origin_y = torch.where(owner == 0, blue_origin_y, red_origin_y)
    state.origin_x_units.copy_(
        torch.where(miner_spawn, miner_origin_x, state.origin_x_units)
    )
    state.origin_y_units.copy_(
        torch.where(miner_spawn, miner_origin_y, state.origin_y_units)
    )
    state.destination_x_units.copy_(
        torch.where(miner_spawn, x_units, state.destination_x_units)
    )
    state.destination_y_units.copy_(
        torch.where(miner_spawn, y_units, state.destination_y_units)
    )
    state.phase.copy_(
        torch.where(
            miner_spawn,
            torch.full_like(state.phase, FAST_TRAVEL_TRANSIT),
            state.phase,
        )
    )
    x_next = torch.where(miner_spawn, miner_origin_x, x_next)
    y_next = torch.where(miner_spawn, miner_origin_y, y_next)

    current = (
        active
        & (state.bound_stable_id > 0)
        & (stable_id == state.bound_stable_id)
        & (card_id == state.bound_card_id)
    )
    safe_bound_card = state.bound_card_id.clamp(0, catalog.size - 1)
    snapshot_current = (
        target_valid
        & (target_stable_id > 0)
        & (target_stable_id == state.target_stable_id)
    )
    in_range = (target_distance_units >= catalog.min_range_units[safe_bound_card]) & (
        target_distance_units <= catalog.max_range_units[safe_bound_card]
    )
    winding_before = current & (state.phase == FAST_TRAVEL_WINDUP)
    cancelled = winding_before & (~snapshot_current | ~in_range | interrupted)
    state.phase.masked_fill_(cancelled, FAST_TRAVEL_IDLE)
    state.phase_ticks.masked_fill_(cancelled, 0)
    state.target_stable_id.masked_fill_(cancelled, 0)

    can_start_kind = (state.kind == FAST_TRAVEL_DASH) | (state.kind == FAST_TRAVEL_LEAP)
    started = (
        current
        & (state.phase == FAST_TRAVEL_IDLE)
        & can_start_kind
        & trigger
        & target_valid
        & (target_stable_id > 0)
        & in_range
        & ~interrupted
    )
    state.phase.copy_(
        torch.where(
            started,
            torch.full_like(state.phase, FAST_TRAVEL_WINDUP),
            state.phase,
        )
    )
    state.phase_ticks.masked_fill_(started, 0)
    state.target_stable_id.copy_(
        torch.where(started, target_stable_id, state.target_stable_id)
    )
    state.origin_x_units.copy_(torch.where(started, x_next, state.origin_x_units))
    state.origin_y_units.copy_(torch.where(started, y_next, state.origin_y_units))
    state.destination_x_units.copy_(
        torch.where(started, target_x_units, state.destination_x_units)
    )
    state.destination_y_units.copy_(
        torch.where(started, target_y_units, state.destination_y_units)
    )

    winding = current & (state.phase == FAST_TRAVEL_WINDUP)
    windup_ticks = torch.where(winding, state.phase_ticks + 1, state.phase_ticks)
    launched = winding & (
        windup_ticks >= catalog.windup_ticks[safe_bound_card].clamp_min(1)
    )
    state.phase_ticks.copy_(torch.where(launched, 0, windup_ticks))
    state.phase.copy_(
        torch.where(
            launched,
            torch.full_like(state.phase, FAST_TRAVEL_TRANSIT),
            state.phase,
        )
    )

    # A newly deployed underground traveller is first relocated to its
    # serialized arena origin.  Transit starts on the following native tick,
    # matching the deployment lifecycle and avoiding a hidden same-tick step.
    travelling = (
        current & (state.phase == FAST_TRAVEL_TRANSIT) & ~launched & ~miner_spawn
    )
    dash_travel = travelling & (state.kind == FAST_TRAVEL_DASH)
    miner_travel = travelling & (state.kind == FAST_TRAVEL_UNDERGROUND)
    vector_travel = dash_travel | miner_travel
    moved_x, moved_y, vector_arrived = _move_towards(
        x_next,
        y_next,
        state.destination_x_units,
        state.destination_y_units,
        catalog.speed_units_per_tick[safe_bound_card],
    )
    x_next = torch.where(vector_travel, moved_x, x_next)
    y_next = torch.where(vector_travel, moved_y, y_next)
    dash_arrived = dash_travel & vector_arrived
    miner_arrived = miner_travel & vector_arrived

    leap_travel = travelling & (state.kind == FAST_TRAVEL_LEAP)
    leap_tick = torch.where(leap_travel, state.phase_ticks + 1, state.phase_ticks)
    leap_total = catalog.transit_ticks[safe_bound_card].clamp_min(1)
    fraction = torch.minimum(
        leap_tick.to(torch.float32) / leap_total.to(torch.float32),
        torch.ones_like(leap_tick, dtype=torch.float32),
    )
    leap_x = torch.round(
        state.origin_x_units.to(torch.float32)
        + (
            state.destination_x_units.to(torch.float32)
            - state.origin_x_units.to(torch.float32)
        )
        * fraction
    ).to(torch.int32)
    leap_y = torch.round(
        state.origin_y_units.to(torch.float32)
        + (
            state.destination_y_units.to(torch.float32)
            - state.origin_y_units.to(torch.float32)
        )
        * fraction
    ).to(torch.int32)
    x_next = torch.where(leap_travel, leap_x, x_next)
    y_next = torch.where(leap_travel, leap_y, y_next)
    leap_arrived = leap_travel & (leap_tick >= leap_total)
    state.phase_ticks.copy_(
        torch.where(
            leap_arrived, 0, torch.where(leap_travel, leap_tick, state.phase_ticks)
        )
    )
    state.phase.copy_(
        torch.where(
            leap_arrived,
            torch.full_like(state.phase, FAST_TRAVEL_LANDING),
            state.phase,
        )
    )
    state.phase.copy_(
        torch.where(
            miner_arrived,
            torch.full_like(state.phase, FAST_TRAVEL_EMERGENCE),
            state.phase,
        )
    )
    state.phase_ticks.masked_fill_(miner_arrived, 0)

    landing_phase = current & (state.phase == FAST_TRAVEL_LANDING) & ~leap_arrived
    landing_tick = torch.where(landing_phase, state.phase_ticks + 1, state.phase_ticks)
    leap_landed = landing_phase & (
        landing_tick >= catalog.landing_ticks[safe_bound_card].clamp_min(1)
    )
    state.phase_ticks.copy_(torch.where(leap_landed, 0, landing_tick))
    state.phase.masked_fill_(leap_landed, FAST_TRAVEL_IDLE)

    emerging = current & (state.phase == FAST_TRAVEL_EMERGENCE) & ~miner_arrived
    emergence_tick = torch.where(emerging, state.phase_ticks + 1, state.phase_ticks)
    surfaced = emerging & (
        emergence_tick >= catalog.emergence_ticks[safe_bound_card].clamp_min(1)
    )
    state.phase_ticks.copy_(torch.where(surfaced, 0, emergence_tick))
    state.phase.masked_fill_(surfaced, FAST_TRAVEL_IDLE)

    state.phase.masked_fill_(dash_arrived, FAST_TRAVEL_IDLE)
    state.phase_ticks.masked_fill_(dash_arrived, 0)
    state.post_immunity_ticks.copy_(
        torch.where(
            dash_arrived,
            catalog.post_immunity_ticks[safe_bound_card],
            torch.where(
                state.post_immunity_ticks > 0,
                state.post_immunity_ticks - 1,
                state.post_immunity_ticks,
            ),
        )
    )
    completed = dash_arrived | leap_landed | surfaced

    impact = _empty_impact(state)
    leap_spawn = initialized & ~profile_rejected & (selected_kind == FAST_TRAVEL_LEAP)
    dash_hit = dash_arrived & snapshot_current
    impact_valid = leap_spawn | dash_hit | leap_landed
    area = leap_spawn | leap_landed
    impact_kind = torch.where(
        area,
        torch.full_like(state.kind, FAST_TRAVEL_IMPACT_AREA),
        torch.where(
            dash_hit,
            torch.full_like(state.kind, FAST_TRAVEL_IMPACT_DIRECT),
            torch.zeros_like(state.kind),
        ),
    )
    damage = torch.where(
        leap_spawn,
        catalog.spawn_damage[safe_bound_card],
        catalog.direct_damage[safe_bound_card],
    )
    impact = FastTravelImpactCommands(
        valid=impact_valid,
        kind=impact_kind,
        source_stable_id=torch.where(impact_valid, stable_id, impact.source_stable_id),
        source_card_id=torch.where(impact_valid, card_id, impact.source_card_id),
        source_owner=torch.where(impact_valid, owner, impact.source_owner),
        target_stable_id=torch.where(
            dash_hit | leap_landed,
            state.target_stable_id,
            impact.target_stable_id,
        ),
        center_x_units=torch.where(impact_valid, x_next, impact.center_x_units),
        center_y_units=torch.where(impact_valid, y_next, impact.center_y_units),
        damage=torch.where(impact_valid, damage, impact.damage),
        tower_damage=torch.where(
            impact_valid,
            torch.where(
                leap_spawn,
                catalog.spawn_damage[safe_bound_card],
                catalog.tower_damage[safe_bound_card],
            ),
            impact.tower_damage,
        ),
        radius_units=torch.where(
            area, catalog.impact_radius_units[safe_bound_card], impact.radius_units
        ),
        push_units=torch.where(
            area, catalog.impact_push_units[safe_bound_card], impact.push_units
        ),
        hits_air=impact.hits_air,
        hits_ground=impact_valid,
        spawn_impact=leap_spawn,
    )
    state.target_stable_id.masked_fill_(completed, 0)

    return FastTravelStepResult(
        x_units=x_next,
        y_units=y_next,
        view=fast_travel_view(
            state, active=active, stable_id=stable_id, card_id=card_id
        ),
        impact=impact,
        stale_cleared=stale,
        initialized=initialized,
        profile_rejected=profile_rejected,
        started=started,
        cancelled=cancelled,
        arrived=dash_arrived | leap_arrived | miner_arrived,
        completed=completed,
    )


def travel_impact_radial_impulse_inputs(
    commands: FastTravelImpactCommands,
    *,
    target_x_units: torch.Tensor,
    target_y_units: torch.Tensor,
    target_stable_id: torch.Tensor,
    eligible: torch.Tensor,
) -> FastRadialImpulseInputs:
    """Adapt area-impact push commands to the shared radial impulse kernel.

    ``eligible`` is caller-owned ``[B, commands, targets]`` policy (ownership,
    target plane, mass, visibility).  This adapter adds command validity and
    serialized radius geometry without knowing card identities.
    """

    command_shape = tuple(commands.valid.shape)
    if len(command_shape) != 2:
        raise ValueError("impact commands must have shape [batch, commands]")
    target_shape = tuple(target_stable_id.shape)
    if len(target_shape) != 2 or target_shape[0] != command_shape[0]:
        raise ValueError("target tensors must have shape [batch, targets]")
    if (
        tuple(target_x_units.shape) != target_shape
        or tuple(target_y_units.shape) != target_shape
    ):
        raise ValueError("target coordinate tensors must match target_stable_id")
    if tuple(eligible.shape) != (command_shape[0], command_shape[1], target_shape[1]):
        raise ValueError("eligible must have shape [batch, commands, targets]")
    dx = target_x_units[:, None, :].to(torch.int64) - commands.center_x_units[
        :, :, None
    ].to(torch.int64)
    dy = target_y_units[:, None, :].to(torch.int64) - commands.center_y_units[
        :, :, None
    ].to(torch.int64)
    radius = commands.radius_units[:, :, None].clamp_min(0).to(torch.int64)
    within_radius = dx.square() + dy.square() <= radius.square()
    active = (
        eligible
        & commands.valid[:, :, None]
        & (commands.kind[:, :, None] == FAST_TRAVEL_IMPACT_AREA)
        & within_radius
    )
    return FastRadialImpulseInputs(
        center_x_units=commands.center_x_units,
        center_y_units=commands.center_y_units,
        target_x_units=target_x_units,
        target_y_units=target_y_units,
        target_stable_id=target_stable_id,
        eligible=active,
        magnitude_units=commands.push_units,
    )
