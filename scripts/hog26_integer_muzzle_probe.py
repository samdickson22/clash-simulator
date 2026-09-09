"""Exact bounded integer muzzle offsets; diagnostic only, not wired into physics."""

import torch


def integer_muzzle_offsets(dx, dy, radius):
    """Truncate radial offsets exactly for deltas bounded to 32767 logic units."""
    if dx.shape != dy.shape or dx.shape != radius.shape:
        raise ValueError("muzzle geometry shapes must match")
    if any(x.dtype not in {torch.int32, torch.int64} for x in (dx, dy, radius)):
        raise ValueError("muzzle geometry must use integer logic units")
    x, y, r = dx.long(), dy.long(), radius.long()
    if ((x.abs() > 32767) | (y.abs() > 32767) | (r < 0)).any():
        raise ValueError("muzzle probe geometry is outside its exact arithmetic bound")
    r = torch.minimum(r, x.abs() + y.abs())
    distance_squared = x.square() + y.square()
    inside = r.square() >= distance_squared

    def offset(component):
        quotient = torch.div(component.square() * r.square(), distance_squared.clamp_min(1),
                             rounding_mode="floor")
        # The bounded float root supplies an estimate only. Integer comparisons
        # correct either rounding direction, including exact-square MPS drift.
        root = torch.sqrt(quotient.float()).long()
        root -= (root.square() > quotient).long()
        root += ((root + 1).square() <= quotient).long()
        value = torch.where(inside, component, component.sign() * root)
        return value.to(dx.dtype)

    return offset(x), offset(y)
