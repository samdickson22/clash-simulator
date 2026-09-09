"""Reject unsupported primary births, including effects consumed within a tick."""

import torch


def require_supported_primary_births(allocation, effects):
    """Complement the active-pool adapter; this is not an all-pool certificate.

    Area-spell births need a separate public lifecycle. A projectile born and
    consumed before the sampled frame needs event history rather than silent
    omission. Ordinary direct-hit queue entries are not visible area sprites.
    """
    if (allocation.accepted & allocation.area).any():
        raise ValueError("unhandled primary area birth, even if consumed before observation")
    projectile = allocation.accepted & allocation.projectile
    slots = allocation.effect_slot
    valid_slot = (slots >= 0) & (slots < effects.max_effects)
    if (projectile & ~valid_slot).any():
        raise ValueError("accepted projectile has no valid allocation receipt")
    survives = effects.active.gather(1, slots.clamp(0, effects.max_effects - 1))
    if (projectile & ~survives).any():
        raise ValueError("transient projectile requires a public birth/impact event record")
    return torch.ones(effects.batch_size, dtype=torch.bool, device=effects.device)
