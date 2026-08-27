"""Fixed-shape radial displacement for the practical tensor Gym.

This module owns geometry only.  Callers resolve ownership, target planes,
visibility, mass immunity, and effect timing into ``eligible`` before invoking
the kernel.  Signed displacement is deliberately data-driven: positive values
push away from an effect center and negative values pull toward it.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch


@dataclass(frozen=True)
class FastRadialImpulseInputs:
    """Dense radial commands and their shared target pool.

    Effect tensors use shape ``[B, I]``, target tensors use ``[B, E]``, and
    ``eligible`` uses ``[B, I, E]``. ``magnitude_units`` may use either the
    shared-command shape ``[B, I]`` or a target-specific ``[B, I, E]`` shape.
    The latter keeps data-driven attraction fused without expanding every
    command-target pair into a one-hot impulse lane. ``distance_percentage`` is an integer
    percentage of the current center-to-target distance (``100`` means the
    full distance).  It is added to ``magnitude_units`` before normalization.

    ``max_displacement_units`` is optional and has shape ``[B, E]``.  It caps
    the magnitude of the *summed* simultaneous impulse for each target.  A
    negative cap disables the cap for that target; zero suppresses movement.
    """

    center_x_units: torch.Tensor
    center_y_units: torch.Tensor
    target_x_units: torch.Tensor
    target_y_units: torch.Tensor
    target_stable_id: torch.Tensor
    eligible: torch.Tensor
    magnitude_units: torch.Tensor | None = None
    distance_percentage: torch.Tensor | None = None
    max_displacement_units: torch.Tensor | None = None


@dataclass(frozen=True)
class FastRadialImpulseResult:
    """One combined signed displacement vector per target."""

    dx_units: torch.Tensor
    dy_units: torch.Tensor
    affected: torch.Tensor


def _validate(inputs: FastRadialImpulseInputs) -> tuple[int, int, int]:
    impulse_shape = tuple(inputs.center_x_units.shape)
    if len(impulse_shape) != 2:
        raise ValueError("effect tensors must have shape [batch, impulses]")
    batch, impulses = impulse_shape
    device = inputs.center_x_units.device
    for name in ("center_x_units", "center_y_units"):
        value = getattr(inputs, name)
        if tuple(value.shape) != impulse_shape:
            raise ValueError(f"{name} must have shape [batch, impulses]")
        if value.device != device:
            raise ValueError(f"{name} is on a different device")
        if value.dtype != torch.int32:
            raise ValueError(f"{name} must be int32")
    percentage = inputs.distance_percentage
    if percentage is not None:
        if tuple(percentage.shape) != impulse_shape:
            raise ValueError("distance_percentage must have shape [batch, impulses]")
        if percentage.device != device or percentage.dtype != torch.int32:
            raise ValueError("distance_percentage must be int32 on the effect device")

    target_shape = tuple(inputs.target_stable_id.shape)
    if len(target_shape) != 2 or target_shape[0] != batch:
        raise ValueError("target tensors must have shape [batch, entities]")
    _, entities = target_shape
    magnitude = inputs.magnitude_units
    if magnitude is not None:
        if tuple(magnitude.shape) not in {
            impulse_shape,
            (batch, impulses, entities),
        }:
            raise ValueError(
                "magnitude_units must have shape [batch, impulses] or "
                "[batch, impulses, entities]"
            )
        if magnitude.device != device or magnitude.dtype != torch.int32:
            raise ValueError("magnitude_units must be int32 on the effect device")
    for name in ("target_x_units", "target_y_units"):
        value = getattr(inputs, name)
        if tuple(value.shape) != target_shape:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.device != device:
            raise ValueError(f"{name} is on a different device")
        if value.dtype != torch.int32:
            raise ValueError(f"{name} must be int32")
    if inputs.target_stable_id.device != device:
        raise ValueError("target_stable_id is on a different device")
    if inputs.target_stable_id.dtype != torch.int64:
        raise ValueError("target_stable_id must be int64")

    if tuple(inputs.eligible.shape) != (batch, impulses, entities):
        raise ValueError("eligible must have shape [batch, impulses, entities]")
    if inputs.eligible.device != device or inputs.eligible.dtype != torch.bool:
        raise ValueError("eligible must be bool on the effect device")

    cap = inputs.max_displacement_units
    if cap is not None:
        if tuple(cap.shape) != target_shape:
            raise ValueError("max_displacement_units must have shape [batch, entities]")
        if cap.device != device or cap.dtype != torch.int32:
            raise ValueError(
                "max_displacement_units must be int32 on the effect device"
            )
    return batch, impulses, entities


def _integer_sqrt(values: torch.Tensor) -> torch.Tensor:
    """Exact floor square root at arena scale without host synchronization."""

    # Coordinates in the Gym are native arena units, so a float64 estimate is
    # within one integer.  Exact integer comparisons repair perfect-square
    # boundaries and make the result identical on CPU and CUDA.
    root = torch.sqrt(values.to(torch.float64)).to(torch.int64)
    for _ in range(2):
        root = torch.where(root.square() > values, root - 1, root)
        following = root + 1
        root = torch.where(following.square() <= values, following, root)
    return root


def _trunc_div(numerator: torch.Tensor, denominator: torch.Tensor) -> torch.Tensor:
    """Signed integer division truncated toward zero."""

    return torch.where(
        numerator < 0,
        -torch.div(-numerator, denominator, rounding_mode="floor"),
        torch.div(numerator, denominator, rounding_mode="floor"),
    )


def compute_fast_radial_impulse(
    inputs: FastRadialImpulseInputs,
) -> FastRadialImpulseResult:
    """Return summed and optionally capped ``int32`` target displacement.

    Exact-center commands use a stable-ID-derived cardinal direction.  This
    keeps coincident targets deterministic without relying on physical slot
    order.  Invalid/nonpositive identities fail closed even when an upstream
    eligibility lane was accidentally left enabled.
    """

    _validate(inputs)
    target_id = inputs.target_stable_id
    delta_x = inputs.target_x_units[:, None, :].to(torch.int64) - inputs.center_x_units[
        :, :, None
    ].to(torch.int64)
    delta_y = inputs.target_y_units[:, None, :].to(torch.int64) - inputs.center_y_units[
        :, :, None
    ].to(torch.int64)
    distance_sq = delta_x.square() + delta_y.square()
    distance = _integer_sqrt(distance_sq)

    # Stable identities spread exact-center lanes across cardinal axes.  The
    # signed magnitude still determines whether the lane pushes or pulls.
    fallback_sign = torch.where(
        torch.bitwise_and(target_id, 1) == 0,
        torch.ones_like(target_id),
        -torch.ones_like(target_id),
    )
    fallback_on_x = torch.bitwise_and(torch.bitwise_right_shift(target_id, 1), 1) == 0
    fallback_x = torch.where(fallback_on_x, fallback_sign, 0)[:, None, :]
    fallback_y = torch.where(fallback_on_x, 0, fallback_sign)[:, None, :]
    coincident = distance == 0
    direction_x = torch.where(coincident, fallback_x, delta_x)
    direction_y = torch.where(coincident, fallback_y, delta_y)
    denominator = torch.where(coincident, 1, distance)

    percentage = inputs.distance_percentage
    if percentage is None:
        percentage_units = torch.zeros_like(distance)
    else:
        percentage_units = _trunc_div(
            distance * percentage[:, :, None].to(torch.int64),
            torch.full_like(distance, 100),
        )
    absolute = inputs.magnitude_units
    if absolute is None:
        magnitude = percentage_units
    else:
        absolute_by_target = absolute[:, :, None] if absolute.ndim == 2 else absolute
        magnitude = absolute_by_target.to(torch.int64) + percentage_units
    active = inputs.eligible & (target_id[:, None, :] > 0) & (magnitude != 0)
    move_x = torch.where(
        active,
        _trunc_div(direction_x * magnitude, denominator),
        0,
    )
    move_y = torch.where(
        active,
        _trunc_div(direction_y * magnitude, denominator),
        0,
    )
    total_x = move_x.sum(dim=1, dtype=torch.int64)
    total_y = move_y.sum(dim=1, dtype=torch.int64)

    cap = inputs.max_displacement_units
    if cap is not None:
        total_distance = _integer_sqrt(total_x.square() + total_y.square())
        cap64 = cap.to(torch.int64)
        capped = (cap64 >= 0) & (total_distance > cap64)
        safe_distance = total_distance.clamp_min(1)
        total_x = torch.where(
            capped,
            _trunc_div(total_x * cap64.clamp_min(0), safe_distance),
            total_x,
        )
        total_y = torch.where(
            capped,
            _trunc_div(total_y * cap64.clamp_min(0), safe_distance),
            total_y,
        )

    int32 = torch.iinfo(torch.int32)
    dx = total_x.clamp(min=int32.min, max=int32.max).to(torch.int32)
    dy = total_y.clamp(min=int32.min, max=int32.max).to(torch.int32)
    return FastRadialImpulseResult(
        dx_units=dx,
        dy_units=dy,
        affected=(dx != 0) | (dy != 0),
    )


def clone_fast_radial_impulse_inputs(
    inputs: FastRadialImpulseInputs,
) -> FastRadialImpulseInputs:
    """Return an isolated input clone for deterministic replay fixtures."""

    values: dict[str, torch.Tensor | None] = {}
    for descriptor in fields(inputs):
        value = getattr(inputs, descriptor.name)
        values[descriptor.name] = None if value is None else value.clone()
    return type(inputs)(**values)  # type: ignore[arg-type]
