"""Bounded public-effect projection prototype, separate from policy inputs."""

import torch


def project_visible_effects(positions_units, observed_owners, appearance_kind, visible):
    """Project explicitly visible appearance/position only for both player seats.

    Appearance kind is 1 for a visible projectile and 2 for a visible area sprite.
    The caller must certify appearance visibility; native effect activity alone
    is insufficient because the effect pool also holds invisible combat queues.
    No effect source-card, target, damage, lifetime, or impact schedule is accepted.
    """
    if positions_units.ndim != 3 or positions_units.shape[-1] != 2:
        raise ValueError("positions must have shape [batch, effects, 2]")
    batch, effects, _ = positions_units.shape
    if (observed_owners.shape != (batch, effects)
            or appearance_kind.shape != (batch, effects)
            or visible.shape != (batch, 2, effects) or visible.dtype != torch.bool):
        raise ValueError("public effect fields must have aligned shapes and boolean visibility")
    if ((appearance_kind < 0) | (appearance_kind > 2)).any():
        raise ValueError("unknown public appearance kind")
    if ((observed_owners < 0) | (observed_owners > 1)).any():
        raise ValueError("observed affiliation must identify one of two players")
    if not torch.isfinite(positions_units).all():
        raise ValueError("public positions must be finite")
    positions = positions_units.to(torch.float32) / positions_units.new_tensor([18000, 32000])
    positions = positions[:, None].expand(batch, 2, effects, 2)
    seat = torch.arange(2, device=positions.device)[None, :, None]
    canonical = torch.where((seat == 1)[..., None], 1 - positions, positions)
    own = observed_owners[:, None] == seat
    kinds = appearance_kind[:, None].expand(batch, 2, effects)
    mask = visible & (kinds > 0)
    features = torch.cat((canonical.clamp(0, 1), own[..., None], (~own)[..., None],
                          (kinds == 1)[..., None], (kinds == 2)[..., None]), dim=-1)
    return torch.where(mask[..., None], features, 0), mask
