"""Batched status-effect and intrinsic building-lifetime tensor kernels.

These kernels mirror the component boundary in ``Entity.update_status_effects``
and ``Building._update_intrinsic_lifetime``.  Status source slots are bounded
physical storage only: aggregate state is recomputed from all live slots and
periodic damage is emitted in stable insertion order.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

STATUS_EPSILON = 1e-9
NATIVE_TICK_MILLISECONDS = 50.0
_ORDER_SENTINEL = torch.iinfo(torch.int64).max


@dataclass(frozen=True)
class PeriodicDamageSchedule:
    """Padded target-local periodic hits in source insertion order.

    Consumers must resolve slots from left to right and mask later hits if an
    earlier hit kills the target.  ``hit_counts`` preserves multiple deadlines
    crossed by a large component step without expanding Python event objects.
    """

    source_slots: torch.Tensor
    source_ids: torch.Tensor
    source_kind: torch.Tensor
    hit_counts: torch.Tensor
    damage: torch.Tensor
    affects_hidden: torch.Tensor
    valid: torch.Tensor

    @property
    def total_damage_if_all_committed(self) -> torch.Tensor:
        return (self.hit_counts.to(dtype=self.damage.dtype) * self.damage).sum(dim=2)


@dataclass(frozen=True)
class BuildingLifetimeResult:
    hitpoints: torch.Tensor
    lifetime_elapsed: torch.Tensor
    lifetime_decay_work: torch.Tensor
    lifetime_tick_carry_ms: torch.Tensor
    is_alive: torch.Tensor
    native_ticks: torch.Tensor
    hitpoint_loss: torch.Tensor
    died: torch.Tensor


@dataclass
class TensorStatusState:
    """Dense status state for ``[battle, entity]`` combat objects."""

    stun_timer: torch.Tensor
    freeze_expiry_time: torch.Tensor
    slow_active: torch.Tensor
    slow_remaining: torch.Tensor
    slow_movement: torch.Tensor
    slow_attack: torch.Tensor
    slow_spawn: torch.Tensor
    slow_timer: torch.Tensor
    slow_multiplier: torch.Tensor
    attack_speed_debuff_multiplier: torch.Tensor
    spawn_speed_debuff_multiplier: torch.Tensor
    haste_active: torch.Tensor
    haste_remaining: torch.Tensor
    haste_movement: torch.Tensor
    haste_attack: torch.Tensor
    haste_spawn: torch.Tensor
    haste_timer: torch.Tensor
    movement_speed_buff_multiplier: torch.Tensor
    attack_speed_buff_multiplier: torch.Tensor
    spawn_speed_buff_multiplier: torch.Tensor
    periodic_active: torch.Tensor
    periodic_source_id: torch.Tensor
    periodic_source_kind: torch.Tensor
    periodic_remaining: torch.Tensor
    periodic_interval: torch.Tensor
    periodic_next_hit: torch.Tensor
    periodic_damage: torch.Tensor
    periodic_hard_active: torch.Tensor
    periodic_hard_remaining: torch.Tensor
    periodic_affects_hidden: torch.Tensor
    periodic_sequence: torch.Tensor
    next_periodic_sequence: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.stun_timer.device

    @property
    def entity_shape(self) -> tuple[int, int]:
        return (int(self.stun_timer.shape[0]), int(self.stun_timer.shape[1]))

    @property
    def max_slow_sources(self) -> int:
        return int(self.slow_active.shape[2])

    @property
    def max_haste_sources(self) -> int:
        return int(self.haste_active.shape[2])

    @property
    def max_periodic_sources(self) -> int:
        return int(self.periodic_active.shape[2])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        max_entities: int,
        *,
        max_slow_sources: int = 8,
        max_haste_sources: int = 8,
        max_periodic_sources: int = 8,
        device: str | torch.device = "cpu",
    ) -> TensorStatusState:
        dimensions = (
            batch_size,
            max_entities,
            max_slow_sources,
            max_haste_sources,
            max_periodic_sources,
        )
        if any(dimension < 1 for dimension in dimensions):
            raise ValueError("all status dimensions must be positive")
        torch_device = torch.device(device)
        entity_shape = (batch_size, max_entities)
        slow_shape = (*entity_shape, max_slow_sources)
        haste_shape = (*entity_shape, max_haste_sources)
        periodic_shape = (*entity_shape, max_periodic_sources)

        def zeros(shape: tuple[int, ...]) -> torch.Tensor:
            return torch.zeros(shape, dtype=torch.float64, device=torch_device)

        def ones(shape: tuple[int, ...]) -> torch.Tensor:
            return torch.ones(shape, dtype=torch.float64, device=torch_device)

        return cls(
            stun_timer=zeros(entity_shape),
            freeze_expiry_time=zeros(entity_shape),
            slow_active=torch.zeros(slow_shape, dtype=torch.bool, device=torch_device),
            slow_remaining=zeros(slow_shape),
            slow_movement=ones(slow_shape),
            slow_attack=ones(slow_shape),
            slow_spawn=ones(slow_shape),
            slow_timer=zeros(entity_shape),
            slow_multiplier=ones(entity_shape),
            attack_speed_debuff_multiplier=ones(entity_shape),
            spawn_speed_debuff_multiplier=ones(entity_shape),
            haste_active=torch.zeros(
                haste_shape, dtype=torch.bool, device=torch_device
            ),
            haste_remaining=zeros(haste_shape),
            haste_movement=ones(haste_shape),
            haste_attack=ones(haste_shape),
            haste_spawn=ones(haste_shape),
            haste_timer=zeros(entity_shape),
            movement_speed_buff_multiplier=ones(entity_shape),
            attack_speed_buff_multiplier=ones(entity_shape),
            spawn_speed_buff_multiplier=ones(entity_shape),
            periodic_active=torch.zeros(
                periodic_shape, dtype=torch.bool, device=torch_device
            ),
            periodic_source_id=torch.zeros(
                periodic_shape, dtype=torch.int64, device=torch_device
            ),
            periodic_source_kind=torch.zeros(
                periodic_shape, dtype=torch.int64, device=torch_device
            ),
            periodic_remaining=zeros(periodic_shape),
            periodic_interval=zeros(periodic_shape),
            periodic_next_hit=zeros(periodic_shape),
            periodic_damage=zeros(periodic_shape),
            periodic_hard_active=torch.zeros(
                periodic_shape, dtype=torch.bool, device=torch_device
            ),
            periodic_hard_remaining=zeros(periodic_shape),
            periodic_affects_hidden=torch.zeros(
                periodic_shape, dtype=torch.bool, device=torch_device
            ),
            periodic_sequence=torch.zeros(
                periodic_shape, dtype=torch.int64, device=torch_device
            ),
            next_periodic_sequence=torch.zeros(
                entity_shape, dtype=torch.int64, device=torch_device
            ),
        )

    def _entity_tensor(
        self,
        value: float | bool | torch.Tensor,
        *,
        dtype: torch.dtype,
        name: str,
    ) -> torch.Tensor:
        tensor = torch.as_tensor(value, dtype=dtype, device=self.device)
        try:
            return torch.broadcast_to(tensor, self.entity_shape)
        except RuntimeError as exc:
            raise ValueError(f"{name} is not broadcastable to [batch, entity]") from exc

    def _mask(self, mask: bool | torch.Tensor) -> torch.Tensor:
        return self._entity_tensor(mask, dtype=torch.bool, name="mask")

    @staticmethod
    def _first_slot(matches: torch.Tensor) -> torch.Tensor:
        return matches.to(dtype=torch.int64).argmax(dim=2)

    @staticmethod
    def _selected_index(
        mask: torch.Tensor, slots: torch.Tensor
    ) -> tuple[torch.Tensor, ...]:
        batch, entity = torch.where(mask)
        return batch, entity, slots[batch, entity]

    @staticmethod
    def _raise_if_slot_overflow(needs_new: torch.Tensor, free: torch.Tensor) -> None:
        if bool((needs_new & ~free.any(dim=2)).any().item()):
            raise OverflowError("status source slot capacity exhausted")

    def apply_stun(
        self,
        duration: float | torch.Tensor,
        *,
        mask: bool | torch.Tensor = True,
    ) -> None:
        selected = self._mask(mask)
        value = self._entity_tensor(duration, dtype=torch.float64, name="duration")
        self.stun_timer.copy_(
            torch.where(
                selected, torch.maximum(self.stun_timer, value), self.stun_timer
            )
        )

    def apply_slow(
        self,
        duration: float | torch.Tensor,
        movement_multiplier: float | torch.Tensor,
        *,
        attack_speed_multiplier: float | torch.Tensor | None = None,
        spawn_speed_multiplier: float | torch.Tensor | None = None,
        mask: bool | torch.Tensor = True,
    ) -> None:
        """Add or refresh one signature-keyed oracle slow-list entry."""

        selected = self._mask(mask)
        remaining = self._entity_tensor(duration, dtype=torch.float64, name="duration")
        movement = self._entity_tensor(
            movement_multiplier, dtype=torch.float64, name="movement_multiplier"
        ).clamp_min(0.0)
        attack = (
            movement
            if attack_speed_multiplier is None
            else self._entity_tensor(
                attack_speed_multiplier,
                dtype=torch.float64,
                name="attack_speed_multiplier",
            ).clamp_min(0.0)
        )
        spawn = (
            movement
            if spawn_speed_multiplier is None
            else self._entity_tensor(
                spawn_speed_multiplier,
                dtype=torch.float64,
                name="spawn_speed_multiplier",
            ).clamp_min(0.0)
        )
        matches = (
            self.slow_active
            & (self.slow_movement == movement[:, :, None])
            & (self.slow_attack == attack[:, :, None])
            & (self.slow_spawn == spawn[:, :, None])
        )
        found = matches.any(dim=2)
        free = ~self.slow_active
        needs_new = selected & ~found
        self._raise_if_slot_overflow(needs_new, free)
        slots = torch.where(found, self._first_slot(matches), self._first_slot(free))
        batch, entity, slot = self._selected_index(selected, slots)
        old_remaining = self.slow_remaining[batch, entity, slot]
        self.slow_active[batch, entity, slot] = True
        self.slow_remaining[batch, entity, slot] = torch.where(
            found[batch, entity],
            torch.maximum(old_remaining, remaining[batch, entity]),
            remaining[batch, entity],
        )
        self.slow_movement[batch, entity, slot] = movement[batch, entity]
        self.slow_attack[batch, entity, slot] = attack[batch, entity]
        self.slow_spawn[batch, entity, slot] = spawn[batch, entity]
        self._recompute_slow()

    def _recompute_slow(self) -> None:
        any_active = self.slow_active.any(dim=2)
        negative_infinity = torch.full_like(self.slow_remaining, -torch.inf)
        positive_infinity = torch.full_like(self.slow_remaining, torch.inf)
        timer = torch.where(
            self.slow_active, self.slow_remaining, negative_infinity
        ).amax(dim=2)
        movement = torch.where(
            self.slow_active, self.slow_movement, positive_infinity
        ).amin(dim=2)
        attack = torch.where(
            self.slow_active, self.slow_attack, positive_infinity
        ).amin(dim=2)
        spawn = torch.where(self.slow_active, self.slow_spawn, positive_infinity).amin(
            dim=2
        )
        self.slow_timer.copy_(torch.where(any_active, timer, 0.0))
        self.slow_multiplier.copy_(torch.where(any_active, movement, 1.0))
        self.attack_speed_debuff_multiplier.copy_(torch.where(any_active, attack, 1.0))
        self.spawn_speed_debuff_multiplier.copy_(torch.where(any_active, spawn, 1.0))

    def apply_haste(
        self,
        duration: float | torch.Tensor,
        movement_multiplier: float | torch.Tensor,
        attack_speed_multiplier: float | torch.Tensor,
        *,
        spawn_speed_multiplier: float | torch.Tensor | None = None,
        mask: bool | torch.Tensor = True,
    ) -> None:
        """Add or refresh one signature-keyed oracle haste-list entry."""

        remaining = self._entity_tensor(duration, dtype=torch.float64, name="duration")
        selected = self._mask(mask) & (remaining > 0.0)
        movement = self._entity_tensor(
            movement_multiplier, dtype=torch.float64, name="movement_multiplier"
        ).clamp_min(0.0)
        attack = self._entity_tensor(
            attack_speed_multiplier,
            dtype=torch.float64,
            name="attack_speed_multiplier",
        ).clamp_min(0.0)
        spawn = (
            attack
            if spawn_speed_multiplier is None
            else self._entity_tensor(
                spawn_speed_multiplier,
                dtype=torch.float64,
                name="spawn_speed_multiplier",
            ).clamp_min(0.0)
        )
        matches = (
            self.haste_active
            & (self.haste_movement == movement[:, :, None])
            & (self.haste_attack == attack[:, :, None])
            & (self.haste_spawn == spawn[:, :, None])
        )
        found = matches.any(dim=2)
        free = ~self.haste_active
        needs_new = selected & ~found
        self._raise_if_slot_overflow(needs_new, free)
        slots = torch.where(found, self._first_slot(matches), self._first_slot(free))
        batch, entity, slot = self._selected_index(selected, slots)
        old_remaining = self.haste_remaining[batch, entity, slot]
        self.haste_active[batch, entity, slot] = True
        self.haste_remaining[batch, entity, slot] = torch.maximum(
            old_remaining, remaining[batch, entity]
        )
        self.haste_movement[batch, entity, slot] = movement[batch, entity]
        self.haste_attack[batch, entity, slot] = attack[batch, entity]
        self.haste_spawn[batch, entity, slot] = spawn[batch, entity]
        self._recompute_haste()

    def _recompute_haste(self) -> None:
        any_active = self.haste_active.any(dim=2)
        negative_infinity = torch.full_like(self.haste_remaining, -torch.inf)
        timer = torch.where(
            self.haste_active, self.haste_remaining, negative_infinity
        ).amax(dim=2)
        movement = torch.where(
            self.haste_active, self.haste_movement, negative_infinity
        ).amax(dim=2)
        attack = torch.where(
            self.haste_active, self.haste_attack, negative_infinity
        ).amax(dim=2)
        spawn = torch.where(
            self.haste_active, self.haste_spawn, negative_infinity
        ).amax(dim=2)
        self.haste_timer.copy_(torch.where(any_active, timer, 0.0))
        self.movement_speed_buff_multiplier.copy_(
            torch.where(any_active, movement, 1.0)
        )
        self.attack_speed_buff_multiplier.copy_(torch.where(any_active, attack, 1.0))
        self.spawn_speed_buff_multiplier.copy_(torch.where(any_active, spawn, 1.0))

    def apply_freeze_until(
        self,
        expiry_time: float | torch.Tensor,
        current_time: float | torch.Tensor,
        *,
        mask: bool | torch.Tensor = True,
    ) -> None:
        """Apply the complete inherited Freeze buff using an absolute expiry."""

        expiry = self._entity_tensor(
            expiry_time, dtype=torch.float64, name="expiry_time"
        )
        now = self._entity_tensor(
            current_time, dtype=torch.float64, name="current_time"
        )
        remaining = (expiry - now).clamp_min(0.0)
        selected = self._mask(mask) & (remaining > STATUS_EPSILON)
        self.apply_stun(remaining, mask=selected)
        self.apply_slow(remaining, 0.0, mask=selected)
        self.freeze_expiry_time.copy_(
            torch.where(
                selected,
                torch.maximum(self.freeze_expiry_time, expiry),
                self.freeze_expiry_time,
            )
        )

    def apply_periodic_damage(
        self,
        *,
        source_id: int | torch.Tensor,
        source_kind: int | torch.Tensor,
        duration: float | torch.Tensor,
        hit_interval: float | torch.Tensor,
        damage: float | torch.Tensor,
        hard_duration: float | torch.Tensor | None = None,
        affects_hidden: bool | torch.Tensor = False,
        mask: bool | torch.Tensor = True,
    ) -> None:
        """Add or refresh a source-ID-keyed periodic target-local buff."""

        ids = self._entity_tensor(source_id, dtype=torch.int64, name="source_id")
        kinds = self._entity_tensor(source_kind, dtype=torch.int64, name="source_kind")
        remaining = self._entity_tensor(duration, dtype=torch.float64, name="duration")
        interval = self._entity_tensor(
            hit_interval, dtype=torch.float64, name="hit_interval"
        )
        hit_damage = self._entity_tensor(damage, dtype=torch.float64, name="damage")
        hidden = self._entity_tensor(
            affects_hidden, dtype=torch.bool, name="affects_hidden"
        )
        selected = (
            self._mask(mask) & (remaining > 0.0) & (interval > 0.0) & (hit_damage > 0.0)
        )
        matches = self.periodic_active & (self.periodic_source_id == ids[:, :, None])
        found = matches.any(dim=2)
        free = ~self.periodic_active
        needs_new = selected & ~found
        self._raise_if_slot_overflow(needs_new, free)
        slots = torch.where(found, self._first_slot(matches), self._first_slot(free))
        batch, entity, slot = self._selected_index(selected, slots)
        was_active = self.periodic_active[batch, entity, slot]
        old_remaining = self.periodic_remaining[batch, entity, slot]

        self.periodic_active[batch, entity, slot] = True
        self.periodic_source_id[batch, entity, slot] = ids[batch, entity]
        self.periodic_source_kind[batch, entity, slot] = kinds[batch, entity]
        self.periodic_remaining[batch, entity, slot] = torch.where(
            was_active,
            torch.maximum(old_remaining, remaining[batch, entity]),
            remaining[batch, entity],
        )
        self.periodic_interval[batch, entity, slot] = torch.where(
            was_active,
            self.periodic_interval[batch, entity, slot],
            interval[batch, entity],
        )
        self.periodic_next_hit[batch, entity, slot] = torch.where(
            was_active,
            self.periodic_next_hit[batch, entity, slot],
            interval[batch, entity],
        )
        self.periodic_damage[batch, entity, slot] = hit_damage[batch, entity]
        self.periodic_affects_hidden[batch, entity, slot] = hidden[batch, entity]

        if hard_duration is not None:
            hard = self._entity_tensor(
                hard_duration, dtype=torch.float64, name="hard_duration"
            ).clamp_min(0.0)
            old_hard_active = self.periodic_hard_active[batch, entity, slot]
            old_hard = self.periodic_hard_remaining[batch, entity, slot]
            self.periodic_hard_active[batch, entity, slot] = True
            self.periodic_hard_remaining[batch, entity, slot] = torch.where(
                was_active & old_hard_active,
                torch.minimum(old_hard, hard[batch, entity]),
                hard[batch, entity],
            )
        else:
            new = ~was_active
            self.periodic_hard_active[batch[new], entity[new], slot[new]] = False
            self.periodic_hard_remaining[batch[new], entity[new], slot[new]] = 0.0

        new = ~was_active
        self.periodic_sequence[batch[new], entity[new], slot[new]] = (
            self.next_periodic_sequence[batch[new], entity[new]]
        )
        self.next_periodic_sequence[batch[new], entity[new]] += 1

    def _periodic_order(self) -> torch.Tensor:
        keys = torch.where(
            self.periodic_active,
            self.periodic_sequence,
            torch.full_like(self.periodic_sequence, _ORDER_SENTINEL),
        )
        return torch.argsort(keys, dim=2, stable=True)

    def tick_periodic_damage(
        self,
        dt: float | torch.Tensor,
        *,
        component_mask: bool | torch.Tensor = True,
    ) -> PeriodicDamageSchedule:
        """Advance periodic clocks and emit due hits before expiry removal."""

        delta = self._entity_tensor(dt, dtype=torch.float64, name="dt")
        selected_entity = self._mask(component_mask)
        selected = self.periodic_active & selected_entity[:, :, None]
        self.periodic_remaining.copy_(
            torch.where(
                selected,
                (self.periodic_remaining - delta[:, :, None]).clamp_min(0.0),
                self.periodic_remaining,
            )
        )
        hard_selected = selected & self.periodic_hard_active
        self.periodic_hard_remaining.copy_(
            torch.where(
                hard_selected,
                (self.periodic_hard_remaining - delta[:, :, None]).clamp_min(0.0),
                self.periodic_hard_remaining,
            )
        )
        decremented_next = self.periodic_next_hit - delta[:, :, None]
        self.periodic_next_hit.copy_(
            torch.where(selected, decremented_next, self.periodic_next_hit)
        )
        due = selected & (decremented_next <= STATUS_EPSILON)
        safe_interval = torch.where(
            selected, self.periodic_interval, torch.ones_like(self.periodic_interval)
        )
        counts = torch.where(
            due,
            torch.floor((STATUS_EPSILON - decremented_next) / safe_interval).to(
                dtype=torch.int64
            )
            + 1,
            torch.zeros_like(self.periodic_source_id),
        )
        self.periodic_next_hit.add_(
            counts.to(dtype=torch.float64) * self.periodic_interval
        )

        order = self._periodic_order()
        ordered_counts = torch.gather(counts, 2, order)
        ordered_active = torch.gather(selected, 2, order)
        schedule_valid = ordered_active & (ordered_counts > 0)
        schedule = PeriodicDamageSchedule(
            source_slots=torch.where(schedule_valid, order, torch.full_like(order, -1)),
            source_ids=torch.gather(self.periodic_source_id, 2, order),
            source_kind=torch.gather(self.periodic_source_kind, 2, order),
            hit_counts=ordered_counts,
            damage=torch.gather(self.periodic_damage, 2, order),
            affects_hidden=torch.gather(self.periodic_affects_hidden, 2, order),
            valid=schedule_valid,
        )

        expired = selected & (
            (self.periodic_remaining <= STATUS_EPSILON)
            | (
                self.periodic_hard_active
                & (self.periodic_hard_remaining <= STATUS_EPSILON)
            )
        )
        self._clear_periodic(expired)
        return schedule

    def _clear_periodic(self, clear: torch.Tensor) -> None:
        self.periodic_active.masked_fill_(clear, False)
        self.periodic_source_id.masked_fill_(clear, 0)
        self.periodic_source_kind.masked_fill_(clear, 0)
        self.periodic_remaining.masked_fill_(clear, 0.0)
        self.periodic_interval.masked_fill_(clear, 0.0)
        self.periodic_next_hit.masked_fill_(clear, 0.0)
        self.periodic_damage.masked_fill_(clear, 0.0)
        self.periodic_hard_active.masked_fill_(clear, False)
        self.periodic_hard_remaining.masked_fill_(clear, 0.0)
        self.periodic_affects_hidden.masked_fill_(clear, False)
        self.periodic_sequence.masked_fill_(clear, 0)

    def expire_periodic_for_dead(self, dead: bool | torch.Tensor) -> None:
        """Mirror removal of every target-owned periodic buff after lethal hits."""

        self._clear_periodic(self.periodic_active & self._mask(dead)[:, :, None])

    def tick(
        self,
        dt: float | torch.Tensor,
        *,
        component_mask: bool | torch.Tensor = True,
    ) -> PeriodicDamageSchedule:
        """Run the oracle status component in its exact internal phase order."""

        delta = self._entity_tensor(dt, dtype=torch.float64, name="dt")
        selected = self._mask(component_mask)
        schedule = self.tick_periodic_damage(delta, component_mask=selected)

        stun_live = selected & (self.stun_timer > 0.0)
        reduced_stun = (self.stun_timer - delta).clamp_min(0.0)
        reduced_stun = torch.where(reduced_stun <= STATUS_EPSILON, 0.0, reduced_stun)
        self.stun_timer.copy_(torch.where(stun_live, reduced_stun, self.stun_timer))

        slow_selected = self.slow_active & selected[:, :, None]
        reduced_slow = self.slow_remaining - delta[:, :, None]
        keep_slow = ~slow_selected | (reduced_slow > STATUS_EPSILON)
        self.slow_remaining.copy_(
            torch.where(slow_selected, reduced_slow, self.slow_remaining)
        )
        self.slow_active.logical_and_(keep_slow)
        self.slow_remaining.masked_fill_(~self.slow_active, 0.0)
        self._recompute_slow()

        haste_selected = self.haste_active & selected[:, :, None]
        reduced_haste = self.haste_remaining - delta[:, :, None]
        keep_haste = ~haste_selected | (reduced_haste > STATUS_EPSILON)
        self.haste_remaining.copy_(
            torch.where(haste_selected, reduced_haste, self.haste_remaining)
        )
        self.haste_active.logical_and_(keep_haste)
        self.haste_remaining.masked_fill_(~self.haste_active, 0.0)
        self._recompute_haste()
        # freeze_expiry_time is absolute battle time and is deliberately not
        # decremented or cleared when its stun/slow symptoms expire.
        return schedule


def tick_building_lifetime(
    *,
    hitpoints: torch.Tensor,
    max_hitpoints: torch.Tensor,
    lifetime_ms: torch.Tensor,
    lifetime_elapsed: torch.Tensor,
    lifetime_decay_work: torch.Tensor,
    lifetime_tick_carry_ms: torch.Tensor,
    is_alive: torch.Tensor,
    dt: float | torch.Tensor,
    component_mask: bool | torch.Tensor = True,
) -> BuildingLifetimeResult:
    """Run native fixed-point building lifetime work over a whole batch."""

    device = hitpoints.device
    shape = hitpoints.shape
    tensors = {
        "max_hitpoints": max_hitpoints,
        "lifetime_ms": lifetime_ms,
        "lifetime_elapsed": lifetime_elapsed,
        "lifetime_decay_work": lifetime_decay_work,
        "lifetime_tick_carry_ms": lifetime_tick_carry_ms,
        "is_alive": is_alive,
    }
    if any(tensor.shape != shape for tensor in tensors.values()):
        raise ValueError("all building lifetime tensors must have the same shape")
    delta = torch.broadcast_to(
        torch.as_tensor(dt, dtype=torch.float64, device=device), shape
    )
    mask = torch.broadcast_to(
        torch.as_tensor(component_mask, dtype=torch.bool, device=device), shape
    )
    selected = mask & is_alive & (lifetime_ms > 0)
    elapsed = torch.where(selected, lifetime_elapsed + delta, lifetime_elapsed)
    total_ms = lifetime_tick_carry_ms + (delta * 1000.0).clamp_min(0.0)
    native_ticks = torch.where(
        selected,
        torch.floor((total_ms + STATUS_EPSILON) / NATIVE_TICK_MILLISECONDS).to(
            dtype=torch.int64
        ),
        torch.zeros_like(lifetime_decay_work),
    )
    carry = torch.where(
        selected,
        total_ms - native_ticks.to(dtype=torch.float64) * NATIVE_TICK_MILLISECONDS,
        lifetime_tick_carry_ms,
    )
    rounded_max_hp = torch.round(max_hitpoints).to(dtype=torch.int64)
    safe_lifetime = lifetime_ms.clamp_min(1).to(dtype=torch.int64)
    decay_rate = torch.div(
        5000 * rounded_max_hp,
        safe_lifetime,
        rounding_mode="floor",
    )
    accumulated = lifetime_decay_work + decay_rate * native_ticks
    hp_loss = torch.where(
        selected,
        torch.div(accumulated, 100, rounding_mode="floor"),
        torch.zeros_like(accumulated),
    )
    work = torch.where(selected, torch.remainder(accumulated, 100), lifetime_decay_work)
    hp = torch.where(
        selected,
        (hitpoints - hp_loss.to(dtype=hitpoints.dtype)).clamp_min(0.0),
        hitpoints,
    )
    alive = torch.where(selected, is_alive & (hp > 0.0), is_alive)
    died = selected & is_alive & ~alive
    return BuildingLifetimeResult(
        hitpoints=hp,
        lifetime_elapsed=elapsed,
        lifetime_decay_work=work,
        lifetime_tick_carry_ms=carry,
        is_alive=alive,
        native_ticks=native_ticks,
        hitpoint_loss=hp_loss,
        died=died,
    )
