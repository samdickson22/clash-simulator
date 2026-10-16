"""Device-resident ordinary attack timing and stable target locks.

This module is the data-driven combat-lock seam for the practical tensor Gym.
Setup compiles Clash's serialized ``hitSpeed``, ``loadTime``, and distinct
``loadFirstHit`` flag into card-aligned tensors.  The tick path then retains a
target by physical slot plus stable entity ID until it becomes illegal,
unavailable, dead, or leaves sight.  It contains no card-name dispatch and no
host synchronization.

The retained :class:`TensorResidentEngine` remains the exact-debug oracle.
These clocks intentionally model the production Gym's fixed 50 ms frames:

* a new source starts at its derived first-hit delay;
* a completed attack installs the complete hit-speed cycle;
* idle movement may preload that cycle only down to the first-hit delay; and
* losing or directly switching an established lock installs the serialized
  retarget delay without discarding more advanced attack work.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from numbers import Real

import torch

from clasher.data import CardDataLoader

from .catalog import CardKindOpcode, TensorCardCatalog
from .simple_state import FastGymState
from .simple_targeting import (
    FastTargetTraits,
    select_nearest_targets,
    within_edge_range,
)


def _same_device(left: torch.device, right: torch.device) -> bool:
    return left.type == right.type and (
        left.index is None or right.index is None or left.index == right.index
    )


def _ceil_milliseconds(milliseconds: torch.Tensor, tick_ms: int) -> torch.Tensor:
    return torch.div(
        milliseconds.to(torch.int64) + tick_ms - 1,
        tick_ms,
        rounding_mode="floor",
    ).to(torch.int32)


def _serialized_nonnegative_integer(value: object, field: str, card: str) -> int:
    """Validate one setup-time serialized timing scalar without coercion loss."""

    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{card} {field} must be a numeric millisecond value")
    numeric = float(value)
    integer = int(numeric)
    if numeric != float(integer) or integer < 0:
        raise ValueError(f"{card} {field} must be a non-negative integer")
    return integer


@dataclass(frozen=True)
class FastAttackTimingCatalog:
    """Card-aligned ordinary attack clocks retained on one torch device."""

    device: torch.device
    tick_ms: int
    hit_cycle_ticks: torch.Tensor
    serialized_load_ticks: torch.Tensor
    first_hit_delay_ticks: torch.Tensor
    retarget_delay_ticks: torch.Tensor
    load_first_hit: torch.Tensor
    ordinary_attack_supported: torch.Tensor

    @property
    def size(self) -> int:
        return int(self.hit_cycle_ticks.shape[0])

    @classmethod
    def compile(
        cls,
        catalog: TensorCardCatalog,
        loader: CardDataLoader,
        *,
        tick_ms: int = 50,
    ) -> FastAttackTimingCatalog:
        """Compile and audit every catalog row against serialized card data.

        Compilation is setup-time code and may materialize Python card
        wrappers.  Any missing, negative, fractional, or catalog-mismatched
        timing fails closed instead of silently producing an instant weapon.
        Runtime kernels use only the returned tensors.
        """

        if isinstance(tick_ms, bool) or not isinstance(tick_ms, int) or tick_ms <= 0:
            raise ValueError("tick_ms must be a positive integer")
        size = len(catalog.names)
        expected = (size,)
        for name in ("kind", "damage", "hit_speed_ms", "load_time_ms"):
            value = getattr(catalog, name)
            if tuple(value.shape) != expected:
                raise ValueError(f"catalog {name} must have shape [cards]")
            if not _same_device(value.device, catalog.device):
                raise ValueError(f"catalog {name} must use the catalog device")
        if catalog.names[0] != "" or catalog.card_count + 1 != size:
            raise ValueError("catalog padding/name alignment is malformed")
        if catalog.hit_speed_ms.dtype not in (torch.int16, torch.int32, torch.int64):
            raise ValueError("catalog hit_speed_ms must be an integer tensor")
        if catalog.load_time_ms.dtype not in (torch.int16, torch.int32, torch.int64):
            raise ValueError("catalog load_time_ms must be an integer tensor")

        # Read source values once at setup.  This is also an explicit audit
        # that TensorCardCatalog and CardDataLoader describe the same revision.
        hit_speed_values = [0]
        load_time_values = [0]
        load_first_hit_values = [False]
        for card_id, card_name in enumerate(catalog.names[1:], start=1):
            stats = loader.get_card(card_name)
            if stats is None:
                raise ValueError(f"missing serialized card stats for {card_name}")
            hit_speed = _serialized_nonnegative_integer(
                stats.hit_speed, "hitSpeed", card_name
            )
            load_time = _serialized_nonnegative_integer(
                stats.load_time, "loadTime", card_name
            )
            if load_time > 0 and hit_speed == 0:
                raise ValueError(f"{card_name} has loadTime without hitSpeed")
            if type(stats.load_first_hit) is not bool:
                raise TypeError(f"{card_name} loadFirstHit must be bool")
            # Tensor values are read only during compilation.  The hot path
            # below never scalarizes or transfers device data.
            if int(catalog.hit_speed_ms[card_id]) != hit_speed:
                raise ValueError(f"catalog hitSpeed mismatch for {card_name}")
            if int(catalog.load_time_ms[card_id]) != load_time:
                raise ValueError(f"catalog loadTime mismatch for {card_name}")
            hit_speed_values.append(hit_speed)
            load_time_values.append(load_time)
            load_first_hit_values.append(bool(stats.load_first_hit))

        # Tensor.device is concrete (for example cuda:0) even if catalog.device
        # was constructed from the shorthand "cuda".
        device = catalog.hit_speed_ms.device
        hit_speed_ms = torch.tensor(hit_speed_values, dtype=torch.int64, device=device)
        load_time_ms = torch.tensor(load_time_values, dtype=torch.int64, device=device)
        load_first_hit = torch.tensor(
            load_first_hit_values, dtype=torch.bool, device=device
        )
        if bool((hit_speed_ms < 0).any()) or bool((load_time_ms < 0).any()):
            raise ValueError("serialized attack timings must be non-negative")

        # Native first-hit/retarget semantics are complementary except for
        # weapons whose load exceeds the complete hit interval.  Those use a
        # full interval for the first lock and the excess as retarget delay.
        inverted = load_time_ms > hit_speed_ms
        first_hit_ms = torch.where(
            inverted,
            hit_speed_ms,
            (hit_speed_ms - load_time_ms).clamp(min=0),
        )
        retarget_ms = torch.where(
            inverted,
            load_time_ms - hit_speed_ms,
            (hit_speed_ms - load_time_ms).clamp(min=0),
        )
        ordinary_kind = (
            (catalog.kind == int(CardKindOpcode.TROOP))
            | (catalog.kind == int(CardKindOpcode.BUILDING))
            | (catalog.kind == int(CardKindOpcode.CHAMPION))
        )
        supported = ordinary_kind & (catalog.damage > 0) & (hit_speed_ms > 0)
        supported[0] = False
        return cls(
            device=device,
            tick_ms=tick_ms,
            hit_cycle_ticks=_ceil_milliseconds(hit_speed_ms, tick_ms),
            serialized_load_ticks=_ceil_milliseconds(load_time_ms, tick_ms),
            first_hit_delay_ticks=_ceil_milliseconds(first_hit_ms, tick_ms),
            retarget_delay_ticks=_ceil_milliseconds(retarget_ms, tick_ms),
            load_first_hit=load_first_hit,
            ordinary_attack_supported=supported,
        )


@dataclass
class FastAttackLockState:
    """Persistent stable-generation lock and clock planes with shape ``[B, E]``.

    ``source_stable_id`` makes source-slot reuse self-invalidating.  A retained
    target stores its slot for O(BE) lookup and its stable ID for generation
    validation, so target-slot reuse cannot inherit the old lock.
    """

    device: torch.device
    source_stable_id: torch.Tensor
    target_slot: torch.Tensor
    target_stable_id: torch.Tensor
    cooldown_ticks: torch.Tensor

    @classmethod
    def empty(
        cls,
        batch_size: int,
        max_entities: int,
        *,
        device: str | torch.device = "cpu",
    ) -> FastAttackLockState:
        if batch_size < 1 or max_entities < 1:
            raise ValueError("attack lock dimensions must be positive")
        tensor_device = torch.device(device)
        if tensor_device.type == "cuda" and tensor_device.index is None:
            tensor_device = torch.device("cuda", torch.cuda.current_device())
        shape = (batch_size, max_entities)
        zeros_i64 = torch.zeros(shape, dtype=torch.int64, device=tensor_device)
        return cls(
            device=tensor_device,
            source_stable_id=zeros_i64.clone(),
            target_slot=torch.full(shape, -1, dtype=torch.int64, device=tensor_device),
            target_stable_id=zeros_i64.clone(),
            cooldown_ticks=torch.zeros(shape, dtype=torch.int32, device=tensor_device),
        )

    def clone(self) -> FastAttackLockState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class FastAttackLockStep:
    """Dense targeting and attack-clock view produced for one native tick."""

    target_found: torch.Tensor
    target_slot: torch.Tensor
    target_stable_id: torch.Tensor
    target_in_attack_range: torch.Tensor
    attack_allowed: torch.Tensor
    cooldown_ticks: torch.Tensor
    cooldown_preload_floor_ticks: torch.Tensor
    acquired: torch.Tensor
    lost: torch.Tensor
    switched: torch.Tensor


@dataclass(frozen=True)
class FastAttackClockStep:
    """Post-movement ordinary attack-clock result for every dense source."""

    attack_allowed: torch.Tensor
    cooldown_ticks: torch.Tensor
    cooldown_preload_floor_ticks: torch.Tensor


def _validate_lock_inputs(
    locks: FastAttackLockState,
    timings: FastAttackTimingCatalog,
    state: FastGymState,
    traits: FastTargetTraits,
    source_disabled: torch.Tensor,
    target_unavailable: torch.Tensor,
    clear_source_lock: torch.Tensor,
    cooldown_decrement: torch.Tensor,
) -> None:
    if not _same_device(locks.device, state.device) or not _same_device(
        timings.device, state.device
    ):
        raise ValueError("state, locks, and attack timings must share a device")
    expected = tuple(state.active.shape)
    required_lock_dtypes = {
        "source_stable_id": torch.int64,
        "target_slot": torch.int64,
        "target_stable_id": torch.int64,
        "cooldown_ticks": torch.int32,
    }
    for name, dtype in required_lock_dtypes.items():
        value = getattr(locks, name)
        if tuple(value.shape) != expected or value.device != state.device:
            raise ValueError(f"lock {name} must have shape [batch, entities]")
        if value.dtype != dtype:
            raise ValueError(f"lock {name} must use {dtype}")
    for name, value, dtype in (
        ("source_disabled", source_disabled, torch.bool),
        ("target_unavailable", target_unavailable, torch.bool),
        ("clear_source_lock", clear_source_lock, torch.bool),
        ("cooldown_decrement", cooldown_decrement, torch.int32),
    ):
        if tuple(value.shape) != expected or value.device != state.device:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    if state.card_id.dtype != torch.int64:
        raise ValueError("state card_id must be int64")
    traits.validate_for(state)


def step_fast_attack_locks_(
    locks: FastAttackLockState,
    timings: FastAttackTimingCatalog,
    state: FastGymState,
    traits: FastTargetTraits,
    *,
    source_disabled: torch.Tensor,
    target_unavailable: torch.Tensor,
    clear_source_lock: torch.Tensor | None = None,
    cooldown_decrement: torch.Tensor | None = None,
) -> FastAttackLockStep:
    """Advance retained targeting and finite idle preload for one tick.

    A retained target wins over a newly nearer candidate.  Its recorded slot
    must still contain the same stable generation and remain legal, visible,
    alive, and in sight.  Unknown card rows fail closed. ``source_disabled``
    pauses acquisition and clock work but does not itself erase a lock; callers
    pass stun, concealment, or travel interruptions through ``clear_source_lock``
    when those mechanics explicitly break combat state.
    """

    if clear_source_lock is None:
        clear_source_lock = torch.zeros_like(state.active)
    if cooldown_decrement is None:
        cooldown_decrement = torch.ones_like(state.cooldown_ticks)
    _validate_lock_inputs(
        locks,
        timings,
        state,
        traits,
        source_disabled,
        target_unavailable,
        clear_source_lock,
        cooldown_decrement,
    )

    safe_card = state.card_id.clamp(0, timings.size - 1)
    known_card = (state.card_id > 0) & (state.card_id < timings.size)
    body_present = state.active & (state.hp > 0) & (state.stable_id > 0)
    source_ready = body_present & (state.deploy_ticks == 0)
    supported = known_card & timings.ordinary_attack_supported[safe_card]
    source_present = source_ready & supported
    same_source = source_present & (locks.source_stable_id == state.stable_id)
    new_source = source_present & ~same_source

    previous_target_id = torch.where(
        same_source, locks.target_stable_id, torch.zeros_like(locks.target_stable_id)
    )
    previous_target_slot = torch.where(
        same_source,
        locks.target_slot,
        torch.full_like(locks.target_slot, -1),
    )
    cooldown = torch.where(
        new_source,
        timings.first_hit_delay_ticks[safe_card],
        torch.where(
            same_source,
            locks.cooldown_ticks.clamp(min=0),
            torch.zeros_like(locks.cooldown_ticks),
        ),
    )

    # Retained legality mirrors ordinary acquisition. The saved slot makes the
    # lookup linear in entity count; stable-ID validation makes reuse safe.
    target_present = body_present & ~target_unavailable
    target_slot_in_bounds = (previous_target_slot >= 0) & (
        previous_target_slot < state.max_entities
    )
    retained_slot = previous_target_slot.clamp(0, state.max_entities - 1)
    retained_target_id = state.stable_id.gather(1, retained_slot)
    retained_target_airborne = traits.airborne.gather(1, retained_slot)
    retained_target_building = traits.building.gather(1, retained_slot)
    retained_plane_allowed = torch.where(
        retained_target_airborne,
        traits.attacks_air,
        traits.attacks_ground,
    )
    retained_category_allowed = ~traits.buildings_only | retained_target_building
    retained_valid = (
        source_present
        & (previous_target_id > 0)
        & target_slot_in_bounds
        & target_present.gather(1, retained_slot)
        & (retained_target_id == previous_target_id)
        & (state.owner != state.owner.gather(1, retained_slot))
        & retained_plane_allowed
        & retained_category_allowed
        & within_edge_range(
            (
                state.x_units.gather(1, retained_slot).to(torch.int64)
                - state.x_units.to(torch.int64)
            ).square()
            + (
                state.y_units.gather(1, retained_slot).to(torch.int64)
                - state.y_units.to(torch.int64)
            ).square(),
            traits.collision_radius.gather(1, retained_slot),
            state.sight_range_units,
        )
    )

    acquisition = select_nearest_targets(
        state,
        traits,
        source_disabled=(source_disabled | ~source_present | clear_source_lock),
        target_unavailable=target_unavailable,
    )
    acquisition_found = acquisition.found
    use_retained = retained_valid & ~clear_source_lock
    target_found = use_retained | (~use_retained & acquisition_found)
    target_slot = torch.where(
        use_retained,
        retained_slot,
        torch.where(acquisition_found, acquisition.target_slot, -1),
    )
    target_stable_id = torch.where(
        use_retained,
        previous_target_id,
        torch.where(acquisition_found, acquisition.target_id, 0),
    )

    had_target = previous_target_id > 0
    has_target = target_stable_id > 0
    changed = had_target & has_target & (previous_target_id != target_stable_id)
    acquired = ~had_target & has_target
    lost = had_target & ~has_target
    switched = changed
    retargeted = lost | switched
    cooldown = torch.where(
        retargeted,
        torch.maximum(cooldown, timings.retarget_delay_ticks[safe_card]),
        cooldown,
    )

    safe_target_slot = target_slot.clamp_min(0)
    target_distance_squared = (
        state.x_units.gather(1, safe_target_slot).to(torch.int64)
        - state.x_units.to(torch.int64)
    ).square() + (
        state.y_units.gather(1, safe_target_slot).to(torch.int64)
        - state.y_units.to(torch.int64)
    ).square()
    target_in_attack_range = target_found & within_edge_range(
        target_distance_squared,
        traits.collision_radius.gather(1, safe_target_slot),
        state.range_units,
    )
    can_advance = source_present & ~source_disabled & ~clear_source_lock
    decrement = cooldown_decrement.clamp(min=0)
    decremented = (cooldown - decrement).clamp(min=0)
    preload_floor = timings.first_hit_delay_ticks[safe_card]
    next_cooldown = torch.where(
        target_in_attack_range,
        decremented,
        torch.maximum(preload_floor, decremented),
    )
    cooldown = torch.where(can_advance & (cooldown > 0), next_cooldown, cooldown)
    cooldown = torch.where(source_present, cooldown, 0)
    attack_allowed = (
        can_advance & target_in_attack_range & (cooldown == 0) & (state.damage > 0)
    )

    locks.source_stable_id.copy_(torch.where(source_present, state.stable_id, 0))
    locks.target_slot.copy_(
        torch.where(
            source_present & target_found,
            target_slot,
            torch.full_like(target_slot, -1),
        )
    )
    locks.target_stable_id.copy_(torch.where(source_present, target_stable_id, 0))
    locks.cooldown_ticks.copy_(cooldown)

    return FastAttackLockStep(
        target_found=target_found,
        target_slot=target_slot,
        target_stable_id=target_stable_id,
        target_in_attack_range=target_in_attack_range,
        attack_allowed=attack_allowed,
        cooldown_ticks=cooldown,
        cooldown_preload_floor_ticks=torch.where(
            source_present, preload_floor, torch.zeros_like(preload_floor)
        ),
        acquired=acquired,
        lost=lost,
        switched=switched,
    )


def advance_fast_attack_lock_clocks_(
    locks: FastAttackLockState,
    timings: FastAttackTimingCatalog,
    state: FastGymState,
    *,
    target_in_attack_range: torch.Tensor,
    source_disabled: torch.Tensor,
    clear_source_lock: torch.Tensor | None = None,
    cooldown_decrement: torch.Tensor | None = None,
) -> FastAttackClockStep:
    """Consume post-movement attack work for already-resolved locks.

    This is the integration seam for runtimes that move between acquisition
    and combat.  Call :func:`step_fast_attack_locks_` with a zero decrement to
    resolve/retain the target, move toward its returned slot, recompute range,
    then call this function with the real rate-scaled decrement.  A runtime
    without intervening movement can use the combined step directly.
    """

    if clear_source_lock is None:
        clear_source_lock = torch.zeros_like(state.active)
    if cooldown_decrement is None:
        cooldown_decrement = torch.ones_like(state.cooldown_ticks)
    expected = tuple(state.active.shape)
    for name, value, dtype in (
        ("target_in_attack_range", target_in_attack_range, torch.bool),
        ("source_disabled", source_disabled, torch.bool),
        ("clear_source_lock", clear_source_lock, torch.bool),
        ("cooldown_decrement", cooldown_decrement, torch.int32),
    ):
        if tuple(value.shape) != expected or value.device != state.device:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    if not _same_device(locks.device, state.device) or not _same_device(
        timings.device, state.device
    ):
        raise ValueError("state, locks, and attack timings must share a device")
    if tuple(locks.cooldown_ticks.shape) != expected:
        raise ValueError("lock cooldown_ticks must have shape [batch, entities]")

    safe_card = state.card_id.clamp(0, timings.size - 1)
    known = (state.card_id > 0) & (state.card_id < timings.size)
    source_present = (
        state.active
        & (state.hp > 0)
        & (state.deploy_ticks == 0)
        & (state.stable_id > 0)
        & known
        & timings.ordinary_attack_supported[safe_card]
        & (locks.source_stable_id == state.stable_id)
    )
    has_target = source_present & (locks.target_stable_id > 0)
    in_range = has_target & target_in_attack_range
    can_advance = source_present & ~source_disabled & ~clear_source_lock
    cooldown = locks.cooldown_ticks.clamp(min=0)
    decremented = (cooldown - cooldown_decrement.clamp(min=0)).clamp(min=0)
    preload_floor = timings.first_hit_delay_ticks[safe_card]
    advanced = torch.where(
        in_range,
        decremented,
        torch.maximum(preload_floor, decremented),
    )
    cooldown = torch.where(can_advance & (cooldown > 0), advanced, cooldown)
    cooldown = torch.where(source_present, cooldown, 0)
    attack_allowed = can_advance & in_range & (cooldown == 0) & (state.damage > 0)
    locks.cooldown_ticks.copy_(cooldown)
    return FastAttackClockStep(
        attack_allowed=attack_allowed,
        cooldown_ticks=cooldown,
        cooldown_preload_floor_ticks=torch.where(
            source_present, preload_floor, torch.zeros_like(preload_floor)
        ),
    )


def commit_fast_attack_locks_(
    locks: FastAttackLockState,
    timings: FastAttackTimingCatalog,
    state: FastGymState,
    *,
    attack_allowed: torch.Tensor,
    effect_allocated: torch.Tensor,
) -> torch.Tensor:
    """Install a full hit cycle for attacks admitted by effect allocation."""

    expected = tuple(state.active.shape)
    for name, value in (
        ("attack_allowed", attack_allowed),
        ("effect_allocated", effect_allocated),
    ):
        if tuple(value.shape) != expected or value.device != state.device:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.dtype != torch.bool:
            raise ValueError(f"{name} must be bool")
    if not _same_device(locks.device, state.device) or not _same_device(
        timings.device, state.device
    ):
        raise ValueError("state, locks, and attack timings must share a device")
    safe_card = state.card_id.clamp(0, timings.size - 1)
    known = (state.card_id > 0) & (state.card_id < timings.size)
    same_source = (
        state.active
        & (state.hp > 0)
        & (state.stable_id > 0)
        & (locks.source_stable_id == state.stable_id)
    )
    committed = (
        attack_allowed
        & effect_allocated
        & known
        & timings.ordinary_attack_supported[safe_card]
        & same_source
        & (locks.target_stable_id > 0)
    )
    locks.cooldown_ticks.copy_(
        torch.where(
            committed,
            timings.hit_cycle_ticks[safe_card],
            locks.cooldown_ticks,
        )
    )
    return committed


def reset_fast_attack_locks_(
    locks: FastAttackLockState,
    rows: torch.Tensor | None = None,
) -> None:
    """Reset all lock planes, or selected batch rows, without reallocating."""

    if rows is None:
        selected = torch.ones(
            locks.source_stable_id.shape[0], dtype=torch.bool, device=locks.device
        )
    else:
        selected = torch.as_tensor(rows, dtype=torch.bool, device=locks.device)
        if tuple(selected.shape) != (locks.source_stable_id.shape[0],):
            raise ValueError("rows must have shape [batch]")
    mask = selected[:, None]
    for name in ("source_stable_id", "target_stable_id", "cooldown_ticks"):
        value = getattr(locks, name)
        value.masked_fill_(mask, 0)
    locks.target_slot.masked_fill_(mask, -1)
