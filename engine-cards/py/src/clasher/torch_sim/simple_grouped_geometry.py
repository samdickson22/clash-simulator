"""Grouped-ring destinations from supplied cast-time angles.

The setup lookup uses scalar integer geometry. This module neither draws RNG
values nor advances projectile lifecycles; callers own cast ordering and timing.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from clasher.kinematics import normalized_vector_logic_units, trunc_div
from clasher.logic_math import rotate_logic_vector


@dataclass(frozen=True)
class FastGroupedGeometry:
    """Offsets indexed by member, randrange(359) angle, and coordinate."""

    offsets_units: torch.Tensor

    @property
    def projectile_count(self) -> int:
        return int(self.offsets_units.shape[0])

    @classmethod
    def compile(
        cls,
        *,
        pattern: str,
        projectile_count: int,
        spread_radius_units: int,
        projectile_radius_units: int,
        device: str | torch.device = "cpu",
    ) -> FastGroupedGeometry:
        if pattern != "grouped_ring":
            raise ValueError(f"unsupported grouped projectile pattern: {pattern}")
        for name, value in (
            ("projectile_count", projectile_count),
            ("spread_radius_units", spread_radius_units),
            ("projectile_radius_units", projectile_radius_units),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if projectile_count < 2:
            raise ValueError("grouped_ring requires at least two projectiles")
        jitter = trunc_div(projectile_radius_units * 60, 100)
        ring = max(0, spread_radius_units - jitter)
        clamp = trunc_div(spread_radius_units * 90, 100)
        angle_step = trunc_div(360, projectile_count - 1)
        members = []
        for member in range(projectile_count):
            base_x, base_y = (
                (0, 0)
                if member == 0
                else rotate_logic_vector(ring, 0, angle_step * (member - 1))
            )
            offsets = []
            for angle in range(359):
                jitter_x, jitter_y = rotate_logic_vector(0, jitter, angle)
                x, y = base_x + jitter_x, base_y + jitter_y
                if clamp > 0 and x * x + y * y > clamp * clamp:
                    x, y = normalized_vector_logic_units(x, y, clamp)
                offsets.append((x, y))
            members.append(offsets)
        return cls(torch.tensor(members, dtype=torch.int64, device=device))

    def destinations(
        self,
        *,
        angles: torch.Tensor,
        target_units: torch.Tensor,
        owner: torch.Tensor,
    ) -> torch.Tensor:
        """Return int64 ``[..., members, 2]`` absolute destinations.

        Angles have shape ``[..., members]``; targets ``[..., 2]`` and owners
        ``[...]`` share the leading dimensions. Validation may synchronize the
        device. This standalone correctness adapter makes no hot-path claim.
        """
        if angles.ndim < 1 or angles.shape[-1] != self.projectile_count:
            raise ValueError("angles must end with the compiled projectile count")
        leading = angles.shape[:-1]
        if target_units.shape != (*leading, 2) or owner.shape != leading:
            raise ValueError("targets and owners must match angle leading dimensions")
        for value in (angles, target_units, owner):
            if value.device != self.offsets_units.device:
                raise ValueError("all inputs must share the lookup device")
            if value.dtype not in (torch.int8, torch.int16, torch.int32, torch.int64):
                raise ValueError("geometry inputs must use signed integer tensors")
        if bool(((angles < 0) | (angles >= 359)).any().item()):
            raise ValueError("angles must be in randrange(359)")
        if bool(((owner < 0) | (owner > 1)).any().item()):
            raise ValueError("owner must be zero or one")
        members = torch.arange(self.projectile_count, device=angles.device)
        offsets = self.offsets_units[members, angles.to(torch.int64)]
        sign = (1 - 2 * owner.to(torch.int64))[..., None, None]
        return target_units.to(torch.int64)[..., None, :] + sign * offsets
