"""Fixed-shape fan/ray hit geometry for the practical tensor Gym.

The helper models an impact that emits up to five forward rays.  The impact
position is the ray origin and the launch-to-impact vector supplies the center
direction.  Serialized range, projectile radius, and angular spread remain
tensor inputs, so callers do not need card-name dispatch in the hot path.

An entity may geometrically overlap several rays near the fan origin.  Raw
per-ray intersections are exposed for diagnostics, but ``hit_count`` is a
per-entity integer plane clamped to zero or one.  Applying damage through that
plane therefore damages every eligible entity at most once.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

FAST_FAN_MAX_RAYS = 5


@dataclass(frozen=True)
class FastFanTopologyResult:
    """Fixed-shape fan geometry and deduplicated entity hits.

    Attack tensors use shape ``[batch, attacks]``.  ``ray_active`` and ray
    directions add a fixed third dimension of length :data:`FAST_FAN_MAX_RAYS`;
    ``ray_entity_hit`` additionally appends the entity dimension.

    ``hit_count`` has shape ``[batch, attacks, entities]`` and integer values
    in ``{0, 1}``.  ``targets_hit`` sums those unique hits per attack.
    """

    supported: torch.Tensor
    ray_active: torch.Tensor
    ray_direction_x: torch.Tensor
    ray_direction_y: torch.Tensor
    ray_entity_hit: torch.Tensor
    entity_hit: torch.Tensor
    hit_count: torch.Tensor
    targets_hit: torch.Tensor


def _validate_attack_plane(
    name: str,
    value: torch.Tensor,
    *,
    shape: tuple[int, int],
    device: torch.device,
) -> None:
    if tuple(value.shape) != shape:
        raise ValueError(f"{name} must have shape [batch, attacks]")
    if value.device != device:
        raise ValueError(f"{name} must use the launch tensor device")
    if value.dtype == torch.bool or not (value.is_floating_point() or value.dtype in {
        torch.int8,
        torch.int16,
        torch.int32,
        torch.int64,
        torch.uint8,
    }):
        raise ValueError(f"{name} must be a real numeric tensor")


def _validate_entity_plane(
    name: str,
    value: torch.Tensor,
    *,
    shape: tuple[int, int],
    device: torch.device,
) -> None:
    if tuple(value.shape) != shape:
        raise ValueError(f"{name} must have shape [batch, entities]")
    if value.device != device:
        raise ValueError(f"{name} must use the launch tensor device")
    if value.dtype == torch.bool or not (value.is_floating_point() or value.dtype in {
        torch.int8,
        torch.int16,
        torch.int32,
        torch.int64,
        torch.uint8,
    }):
        raise ValueError(f"{name} must be a real numeric tensor")


def resolve_fast_fan_topology(
    *,
    launch_x_units: torch.Tensor,
    launch_y_units: torch.Tensor,
    impact_x_units: torch.Tensor,
    impact_y_units: torch.Tensor,
    range_units: torch.Tensor,
    radius_units: torch.Tensor,
    spread_degrees: torch.Tensor,
    ray_count: torch.Tensor,
    eligibility: torch.Tensor,
    entity_x_units: torch.Tensor,
    entity_y_units: torch.Tensor,
    entity_collision_radius_units: torch.Tensor,
) -> FastFanTopologyResult:
    """Resolve a serialized impact fan without compaction or host transfer.

    ``eligibility`` has shape ``[batch, attacks, entities]`` and should already
    encode owner, air/ground, visibility, and lifecycle rules.  Geometry does
    not reinterpret those policy decisions.

    Serialized spread follows the game's burst-projectile convention: ray
    ordinal ``i`` is rotated by ``(i - floor(count / 2)) * spread / count``
    degrees from the launch-to-impact direction.  Thus odd fans retain a center
    ray while their outer rays sit inside the serialized full spread value.

    Ray collision is a forward finite capsule with a hard rear plane: an
    entity is eligible only when its center projects from zero through the
    serialized range.  Its collision radius expands the ray radius, but does
    not permit a target behind the impact origin.
    """

    if launch_x_units.ndim != 2:
        raise ValueError("launch_x_units must have shape [batch, attacks]")
    attack_shape = (launch_x_units.shape[0], launch_x_units.shape[1])
    device = launch_x_units.device
    for name, value in (
        ("launch_x_units", launch_x_units),
        ("launch_y_units", launch_y_units),
        ("impact_x_units", impact_x_units),
        ("impact_y_units", impact_y_units),
        ("range_units", range_units),
        ("radius_units", radius_units),
        ("spread_degrees", spread_degrees),
        ("ray_count", ray_count),
    ):
        _validate_attack_plane(name, value, shape=attack_shape, device=device)

    if eligibility.ndim != 3 or tuple(eligibility.shape[:2]) != attack_shape:
        raise ValueError(
            "eligibility must have shape [batch, attacks, entities]"
        )
    if eligibility.device != device or eligibility.dtype != torch.bool:
        raise ValueError("eligibility must be bool on the launch tensor device")
    entity_shape = (attack_shape[0], eligibility.shape[2])
    for name, value in (
        ("entity_x_units", entity_x_units),
        ("entity_y_units", entity_y_units),
        ("entity_collision_radius_units", entity_collision_radius_units),
    ):
        _validate_entity_plane(name, value, shape=entity_shape, device=device)

    work_dtype = torch.float32
    launch_x = launch_x_units.to(work_dtype)
    launch_y = launch_y_units.to(work_dtype)
    impact_x = impact_x_units.to(work_dtype)
    impact_y = impact_y_units.to(work_dtype)
    delta_x = impact_x - launch_x
    delta_y = impact_y - launch_y
    direction_norm_sq = delta_x.square() + delta_y.square()
    direction_norm = torch.sqrt(direction_norm_sq.clamp_min(1.0))
    center_x = delta_x / direction_norm
    center_y = delta_y / direction_norm

    counts = ray_count.to(torch.int64)
    ranges = range_units.to(work_dtype)
    radii = radius_units.to(work_dtype)
    spreads = spread_degrees.to(work_dtype)
    supported = (
        (direction_norm_sq > 0)
        & (counts >= 1)
        & (counts <= FAST_FAN_MAX_RAYS)
        & (ranges > 0)
        & (radii >= 0)
        & (spreads >= 0)
        & torch.isfinite(ranges)
        & torch.isfinite(radii)
        & torch.isfinite(spreads)
    )

    ray_ordinal = torch.arange(
        FAST_FAN_MAX_RAYS, dtype=torch.int64, device=device
    ).view(1, 1, FAST_FAN_MAX_RAYS)
    safe_counts = counts.clamp(1, FAST_FAN_MAX_RAYS)
    ray_active = supported[:, :, None] & (ray_ordinal < counts[:, :, None])
    centered_ordinal = ray_ordinal - torch.div(
        safe_counts[:, :, None], 2, rounding_mode="floor"
    )
    angle_degrees = (
        centered_ordinal.to(work_dtype)
        * spreads[:, :, None]
        / safe_counts[:, :, None].to(work_dtype)
    )
    angle_radians = angle_degrees * (torch.pi / 180.0)
    cosine = torch.cos(angle_radians)
    sine = torch.sin(angle_radians)
    ray_direction_x = center_x[:, :, None] * cosine - center_y[:, :, None] * sine
    ray_direction_y = center_x[:, :, None] * sine + center_y[:, :, None] * cosine
    ray_direction_x = torch.where(ray_active, ray_direction_x, 0.0)
    ray_direction_y = torch.where(ray_active, ray_direction_y, 0.0)

    entity_delta_x = entity_x_units[:, None, None, :].to(work_dtype) - impact_x[
        :, :, None, None
    ]
    entity_delta_y = entity_y_units[:, None, None, :].to(work_dtype) - impact_y[
        :, :, None, None
    ]
    projection = (
        entity_delta_x * ray_direction_x[:, :, :, None]
        + entity_delta_y * ray_direction_y[:, :, :, None]
    )
    center_distance_sq = entity_delta_x.square() + entity_delta_y.square()
    perpendicular_sq = (center_distance_sq - projection.square()).clamp_min(0.0)
    collision_radius = (
        radii[:, :, None, None]
        + entity_collision_radius_units[:, None, None, :]
        .to(work_dtype)
        .clamp_min(0.0)
    )
    ray_entity_hit = (
        ray_active[:, :, :, None]
        & eligibility[:, :, None, :]
        & (projection >= 0.0)
        & (projection <= ranges[:, :, None, None])
        & (perpendicular_sq <= collision_radius.square())
    )
    entity_hit = ray_entity_hit.any(dim=2)
    hit_count = entity_hit.to(torch.int32)
    targets_hit = hit_count.sum(dim=2, dtype=torch.int32)
    return FastFanTopologyResult(
        supported=supported,
        ray_active=ray_active,
        ray_direction_x=ray_direction_x,
        ray_direction_y=ray_direction_y,
        ray_entity_hit=ray_entity_hit,
        entity_hit=entity_hit,
        hit_count=hit_count,
        targets_hit=targets_hit,
    )


__all__ = [
    "FAST_FAN_MAX_RAYS",
    "FastFanTopologyResult",
    "resolve_fast_fan_topology",
]
