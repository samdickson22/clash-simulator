"""Fixed-shape line and capsule hit topology for the practical tensor Gym.

The helper owns geometry only.  Callers supply their already-resolved target
eligibility mask, including ownership, visibility, air/ground, and damage
category rules.  A serialized range extends from the source in the direction
of the primary target, while ``half_width_units`` is the radius of the swept
capsule around that finite centerline.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class FastLineHitTopology:
    """Fixed-shape geometry and hit results for ``[batch, lines, entities]``."""

    hit: torch.Tensor
    hit_count: torch.Tensor
    valid_direction: torch.Tensor
    axial_distance: torch.Tensor
    distance_to_segment: torch.Tensor


def _validate_real_tensor(name: str, value: torch.Tensor) -> None:
    if value.dtype == torch.bool or value.is_complex():
        raise ValueError(f"{name} must be a real numeric tensor")


def select_line_capsule_hits(
    *,
    source_x_units: torch.Tensor,
    source_y_units: torch.Tensor,
    primary_x_units: torch.Tensor,
    primary_y_units: torch.Tensor,
    range_units: torch.Tensor,
    half_width_units: torch.Tensor,
    candidate_x_units: torch.Tensor,
    candidate_y_units: torch.Tensor,
    eligible: torch.Tensor,
) -> FastLineHitTopology:
    """Return all eligible candidates intersecting each forward capsule.

    Source, primary, range, and half-width tensors have shape ``[B, L]``.
    Candidate coordinates have shape ``[B, E]`` and ``eligible`` has shape
    ``[B, L, E]``.  The result retains that fixed ``[B, L, E]`` layout and
    reports an on-device ``[B, L]`` hit count.

    The source-to-primary vector establishes direction only; the serialized
    range controls centerline length.  The far endpoint has a round cap, but
    negative axial projection is always excluded so the source cap cannot hit
    behind the attacker.  A zero-length direction, non-positive range, or
    negative width fails closed without selecting any candidate.
    """

    line_shape = tuple(source_x_units.shape)
    if len(line_shape) != 2:
        raise ValueError("source coordinates must have shape [batch, lines]")
    for name, value in (
        ("source_x_units", source_x_units),
        ("source_y_units", source_y_units),
        ("primary_x_units", primary_x_units),
        ("primary_y_units", primary_y_units),
        ("range_units", range_units),
        ("half_width_units", half_width_units),
    ):
        if tuple(value.shape) != line_shape:
            raise ValueError(f"{name} must have shape [batch, lines]")
        if value.device != source_x_units.device:
            raise ValueError(f"{name} must use the source device")
        _validate_real_tensor(name, value)

    batch = line_shape[0]
    if (
        tuple(candidate_x_units.shape[:1]) != (batch,)
        or candidate_x_units.ndim != 2
    ):
        raise ValueError("candidate coordinates must have shape [batch, entities]")
    candidate_shape = tuple(candidate_x_units.shape)
    for name, value in (
        ("candidate_x_units", candidate_x_units),
        ("candidate_y_units", candidate_y_units),
    ):
        if tuple(value.shape) != candidate_shape:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.device != source_x_units.device:
            raise ValueError(f"{name} must use the source device")
        _validate_real_tensor(name, value)
    expected_eligible = (batch, line_shape[1], candidate_shape[1])
    if tuple(eligible.shape) != expected_eligible:
        raise ValueError("eligible must have shape [batch, lines, entities]")
    if eligible.device != source_x_units.device:
        raise ValueError("eligible must use the source device")
    if eligible.dtype != torch.bool:
        raise ValueError("eligible must be bool")

    source_x = source_x_units.to(torch.float32)
    source_y = source_y_units.to(torch.float32)
    direction_x = primary_x_units.to(torch.float32) - source_x
    direction_y = primary_y_units.to(torch.float32) - source_y
    direction_length = torch.sqrt(direction_x.square() + direction_y.square())
    safe_direction_length = direction_length.clamp_min(1.0)
    unit_x = direction_x / safe_direction_length
    unit_y = direction_y / safe_direction_length

    relative_x = (
        candidate_x_units[:, None, :].to(torch.float32) - source_x[:, :, None]
    )
    relative_y = (
        candidate_y_units[:, None, :].to(torch.float32) - source_y[:, :, None]
    )
    axial_distance = (
        relative_x * unit_x[:, :, None] + relative_y * unit_y[:, :, None]
    )

    serialized_range = range_units.to(torch.float32)
    closest_axial = torch.minimum(
        axial_distance.clamp_min(0.0),
        serialized_range.clamp_min(0.0)[:, :, None],
    )
    closest_x = unit_x[:, :, None] * closest_axial
    closest_y = unit_y[:, :, None] * closest_axial
    distance_to_segment = torch.sqrt(
        (relative_x - closest_x).square() + (relative_y - closest_y).square()
    )

    width = half_width_units.to(torch.float32)
    valid_direction = (
        (direction_length > 0.0) & (serialized_range > 0.0) & (width >= 0.0)
    )
    hit = (
        eligible
        & valid_direction[:, :, None]
        & (axial_distance >= 0.0)
        & (distance_to_segment <= width[:, :, None])
    )
    return FastLineHitTopology(
        hit=hit,
        hit_count=hit.sum(dim=2, dtype=torch.int64),
        valid_direction=valid_direction,
        axial_distance=axial_distance,
        distance_to_segment=distance_to_segment,
    )
