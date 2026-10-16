"""Target-local periodic buffs with one bounded ledger per source effect slot."""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch

from .simple_modifiers import FastModifierState, intercept_fast_shield_hits_
from .simple_state import FAST_KIND_BUILDING, FastGymState

if TYPE_CHECKING:
    from .simple_effects import FastEffectState


def advance_periodic_damage_(
    state: FastGymState,
    effects: FastEffectState,
    modifiers: FastModifierState | None,
    area_receivable: torch.Tensor,
    hidden_receivable: torch.Tensor,
) -> torch.Tensor:
    """Tick attached buffs before the source scans, including its expiry frame."""
    count = state.max_entities
    ids = effects.periodic_target_id[:, :, :count]
    remaining = effects.periodic_remaining_ticks[:, :, :count]
    clock = effects.periodic_next_hit_ticks[:, :, :count]
    damage = effects.periodic_damage[:, :, :count]
    live = (
        (remaining > 0)
        & (ids > 0)
        & (ids == state.stable_id[:, None, :])
        & state.active[:, None, :]
        & (state.hp[:, None, :] > 0)
        & ~state.game_over[:, None, None]
    )
    remaining.copy_(torch.where(live, (remaining - 1).clamp_min(0), 0))
    clock.copy_(torch.where(live, clock - 1, 0))
    due = live & (clock <= 0)
    eligible = torch.where(effects.affects_hidden[:, :, None],
                           hidden_receivable[:, None, :], area_receivable[:, None, :])
    hits = due & eligible
    # Preserve source identity through late impact/death hooks when the last
    # attached buff hits and expires before this frame's new allocations.
    effects.periodic_pending_hits.copy_(hits.any(dim=2))
    slots = torch.arange(count, device=state.device).view(1, 1, -1)
    if modifiers is None:
        hp_damage = (hits * damage).sum(dim=1)
    else:
        hp_damage = intercept_fast_shield_hits_(
            modifiers,
            valid=hits.flatten(1),
            target_slot=slots.expand_as(hits).flatten(1),
            damage=damage.expand_as(hits).flatten(1),
        ).hp_damage
    state.hp.sub_(hp_damage).clamp_min_(0)
    clock.add_(due.to(torch.int32) * effects.damage_interval_ticks[:, :, None])
    retained = live & (remaining > 0) & (state.hp[:, None, :] > 0)
    ids.masked_fill_(~retained, 0)
    remaining.masked_fill_(~retained, 0)
    clock.masked_fill_(~retained, 0)
    damage.masked_fill_(~retained, 0)
    return hits


def refresh_periodic_damage_(
    state: FastGymState,
    effects: FastEffectState,
    scan: torch.Tensor,
    candidates: torch.Tensor,
) -> None:
    """Refresh duration without resetting an existing target/source hit clock."""
    count = state.max_entities
    ids = effects.periodic_target_id[:, :, :count]
    remaining = effects.periodic_remaining_ticks[:, :, :count]
    clock = effects.periodic_next_hit_ticks[:, :, :count]
    attach = (scan[:, :, None] & effects.target_local_damage[:, :, None]
              & candidates & state.active[:, None, :] & (state.hp[:, None, :] > 0))
    existing = (remaining > 0) & (ids == state.stable_id[:, None, :])
    clock.copy_(torch.where(attach & ~existing, effects.damage_interval_ticks[:, :, None], clock))
    duration = effects.periodic_buff_duration_ticks[:, :, None]
    remaining.copy_(torch.where(attach, torch.maximum(remaining, duration), remaining))
    ids.copy_(torch.where(attach, state.stable_id[:, None, :], ids))
    slots = torch.arange(count, device=state.device).view(1, 1, -1)
    tower = torch.where(slots < 6, effects.tower_damage_multiplier[:, :, None], 1.0)
    building = torch.where(
        (slots >= 6) & (state.kind[:, None, :] == FAST_KIND_BUILDING),
        effects.building_damage_multiplier[:, :, None], 1.0,
    )
    damage = effects.periodic_damage[:, :, :count]
    damage.copy_(torch.where(attach, effects.damage[:, :, None].clamp_min(0) * tower * building, damage))
