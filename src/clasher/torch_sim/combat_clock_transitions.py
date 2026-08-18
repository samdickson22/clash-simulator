"""Exact tensor transitions for externally triggered combat-clock changes.

These kernels own no phase orchestration.  They encode scalar character rules
that are triggered outside the ordinary combat component: stun interruption,
forced-movement interruption, and object-phase character birth.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass
class TensorCombatClockPlanes:
    attack_cooldown: torch.Tensor
    target_slot: torch.Tensor
    attack_windup_active: torch.Tensor
    attack_preload_blocked: torch.Tensor
    has_attacked_once: torch.Tensor

    def validate(self) -> None:
        shape = self.attack_cooldown.shape
        device = self.attack_cooldown.device
        for value in (
            self.target_slot,
            self.attack_windup_active,
            self.attack_preload_blocked,
            self.has_attacked_once,
        ):
            if value.shape != shape or value.device != device:
                raise ValueError("combat-clock planes must have one shape and device")


@dataclass(frozen=True)
class CombatClockTransitionResult:
    transitioned: torch.Tensor
    combat_blocked: torch.Tensor
    charge_reset: torch.Tensor


def _mask(
    value: torch.Tensor | bool,
    reference: torch.Tensor,
) -> torch.Tensor:
    return torch.broadcast_to(
        torch.as_tensor(value, dtype=torch.bool, device=reference.device),
        reference.shape,
    )


def _milliseconds(
    value: torch.Tensor | int,
    reference: torch.Tensor,
) -> torch.Tensor:
    return torch.broadcast_to(
        torch.as_tensor(value, dtype=torch.int64, device=reference.device),
        reference.shape,
    )


def apply_stun_interrupt_(
    clocks: TensorCombatClockPlanes,
    *,
    status_applied: torch.Tensor,
    hit_speed_ms: torch.Tensor,
    load_first_hit: torch.Tensor | bool = False,
    reset_load_first_hit_when_zapped: torch.Tensor | bool = True,
    river_jump_active: torch.Tensor | bool = False,
) -> CombatClockTransitionResult:
    """Apply ``Entity._interrupt_combat_by_stun`` in place.

    ``status_applied`` describes an accepted stun call, not merely a timer
    increase.  Reapplying a shorter stun still interrupts combat in Python.
    River jumpers retain their combat state until landing.
    """

    clocks.validate()
    applied = _mask(status_applied, clocks.attack_cooldown)
    river = _mask(river_jump_active, clocks.attack_cooldown)
    transitioned = applied & ~river
    load_first = _mask(load_first_hit, clocks.attack_cooldown)
    reset_first = _mask(reset_load_first_hit_when_zapped, clocks.attack_cooldown)
    reload_clock = transitioned & (~load_first | reset_first)
    hit_speed = _milliseconds(hit_speed_ms, clocks.attack_cooldown)
    base_interval = torch.where(
        hit_speed > 0,
        hit_speed.to(torch.float64) / 1_000.0,
        torch.ones_like(clocks.attack_cooldown),
    )
    clocks.attack_cooldown.copy_(
        torch.where(reload_clock, base_interval, clocks.attack_cooldown)
    )
    clocks.target_slot.masked_fill_(transitioned, -1)
    clocks.attack_windup_active &= ~transitioned
    clocks.has_attacked_once &= ~transitioned
    return CombatClockTransitionResult(
        transitioned=transitioned,
        combat_blocked=applied,
        charge_reset=transitioned,
    )


def apply_forced_movement_interrupt_(
    clocks: TensorCombatClockPlanes,
    *,
    movement_started: torch.Tensor,
    hit_speed_ms: torch.Tensor,
    interrupts_combat: torch.Tensor | bool = True,
    charged_attack_ready: torch.Tensor | bool = False,
) -> CombatClockTransitionResult:
    """Apply the combat portion of ``Entity.begin_knockback`` in place."""

    clocks.validate()
    started = _mask(movement_started, clocks.attack_cooldown)
    interrupts = _mask(interrupts_combat, clocks.attack_cooldown)
    transitioned = started & interrupts
    charged = transitioned & _mask(charged_attack_ready, clocks.attack_cooldown)
    ordinary = transitioned & ~charged
    hit_speed = _milliseconds(hit_speed_ms, clocks.attack_cooldown)
    base_interval = torch.where(
        hit_speed > 0,
        hit_speed.to(torch.float64) / 1_000.0,
        torch.ones_like(clocks.attack_cooldown),
    )
    clocks.attack_cooldown.copy_(
        torch.where(
            ordinary,
            torch.maximum(clocks.attack_cooldown, base_interval),
            clocks.attack_cooldown,
        )
    )
    clocks.attack_windup_active &= ~transitioned
    clocks.attack_preload_blocked |= ordinary
    clocks.has_attacked_once &= ~transitioned
    return CombatClockTransitionResult(
        transitioned=transitioned,
        combat_blocked=transitioned,
        charge_reset=transitioned,
    )


def initialize_spawned_attack_clocks_(
    clocks: TensorCombatClockPlanes,
    *,
    spawned: torch.Tensor,
    first_hit_ms: torch.Tensor,
) -> CombatClockTransitionResult:
    """Publish the character combat state installed at scalar allocation."""

    clocks.validate()
    created = _mask(spawned, clocks.attack_cooldown)
    first_hit = (
        _milliseconds(first_hit_ms, clocks.attack_cooldown).to(torch.float64) / 1_000.0
    )
    clocks.attack_cooldown.copy_(
        torch.where(
            created,
            torch.maximum(clocks.attack_cooldown, first_hit),
            clocks.attack_cooldown,
        )
    )
    clocks.target_slot.masked_fill_(created, -1)
    clocks.attack_windup_active &= ~created
    clocks.attack_preload_blocked &= ~created
    clocks.has_attacked_once &= ~created
    return CombatClockTransitionResult(
        transitioned=created,
        combat_blocked=torch.zeros_like(created),
        charge_reset=torch.zeros_like(created),
    )


__all__ = [
    "CombatClockTransitionResult",
    "TensorCombatClockPlanes",
    "apply_forced_movement_interrupt_",
    "apply_stun_interrupt_",
    "initialize_spawned_attack_clocks_",
]
