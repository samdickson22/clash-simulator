"""Vectorized target acquisition for the practical tensor Gym.

The selector deliberately models the small target contract needed by ordinary
combat rather than reproducing the scalar simulator's target caches.  All
entities select at once from fixed-shape tensors; no card-name dispatch or
dynamic candidate collection is involved.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from .simple_state import FastGymState


def within_edge_range(distance_squared, target_radius, reach):
    """Compare integer-unit geometry without a rounded square root.

    Integer radii/reach use int64 throughout. Fractional trait fixtures retain
    their floating-point radius contract through a squared comparison.
    """
    if not target_radius.is_floating_point() and not reach.is_floating_point():
        limit = target_radius.to(torch.int64).clamp_min(0) + reach.to(
            torch.int64
        ).clamp_min(0)
    else:
        limit = target_radius.clamp_min(0) + reach.clamp_min(0)
    return distance_squared <= limit.square()


@dataclass(frozen=True)
class FastTargetTraits:
    """Targeting capabilities and collision geometry with shape ``[B, E]``."""

    airborne: torch.Tensor
    building: torch.Tensor
    attacks_air: torch.Tensor
    attacks_ground: torch.Tensor
    buildings_only: torch.Tensor
    collision_radius: torch.Tensor

    def validate_for(self, state: FastGymState) -> None:
        expected = tuple(state.active.shape)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if tuple(value.shape) != expected:
                raise ValueError(f"{descriptor.name} must have shape [batch, entities]")
            if value.device != state.device:
                raise ValueError(f"{descriptor.name} must use the state device")
        for name in (
            "airborne",
            "building",
            "attacks_air",
            "attacks_ground",
            "buildings_only",
        ):
            if getattr(self, name).dtype != torch.bool:
                raise ValueError(f"{name} must be bool")
        if self.collision_radius.dtype not in {
            torch.int16,
            torch.int32,
            torch.int64,
            torch.float32,
            torch.float64,
        }:
            raise ValueError("collision_radius must be a real numeric tensor")


@dataclass(frozen=True)
class FastTargetSelection:
    """One deterministic target result for every potential source entity."""

    found: torch.Tensor
    target_slot: torch.Tensor
    target_id: torch.Tensor
    center_distance: torch.Tensor
    edge_distance: torch.Tensor
    within_attack_range: torch.Tensor


def select_nearest_targets(
    state: FastGymState,
    traits: FastTargetTraits,
    *,
    source_disabled: torch.Tensor,
    target_unavailable: torch.Tensor,
) -> FastTargetSelection:
    """Select the nearest visible legal enemy, resolving ties by stable ID.

    Sight and ordinary attack range are measured from the source center to the
    edge of the target hitbox: ``center_distance - target_collision_radius``.
    This is the native ordinary-combat convention; the source radius is not
    added to serialized attack range.  Disabled sources cannot acquire, while
    disabled targets remain eligible unless explicitly marked unavailable.

    ``target_unavailable`` combines invisibility and any other fail-closed
    untargetable state.  The returned slot is ``-1`` and distances are
    positive infinity when no target exists.
    """

    traits.validate_for(state)
    expected = tuple(state.active.shape)
    for name, value in (
        ("source_disabled", source_disabled),
        ("target_unavailable", target_unavailable),
    ):
        if tuple(value.shape) != expected:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.device != state.device:
            raise ValueError(f"{name} must use the state device")
        if value.dtype != torch.bool:
            raise ValueError(f"{name} must be bool")

    # Sources index dimension 1; candidate targets index dimension 2.
    body_present = state.active & (state.hp > 0) & (state.stable_id > 0)
    # Deployment gates only the source's actions. Pending bodies already exist
    # in the arena and remain targetable/effectable under the public contract.
    source_can_act = body_present & (state.deploy_ticks == 0) & ~source_disabled
    target_present = body_present & ~target_unavailable

    target_plane_allowed = torch.where(
        traits.airborne[:, None, :],
        traits.attacks_air[:, :, None],
        traits.attacks_ground[:, :, None],
    )
    target_category_allowed = (
        ~traits.buildings_only[:, :, None] | traits.building[:, None, :]
    )

    delta_x = state.x_units[:, :, None].to(torch.int64) - state.x_units[:, None, :].to(
        torch.int64
    )
    delta_y = state.y_units[:, :, None].to(torch.int64) - state.y_units[:, None, :].to(
        torch.int64
    )
    center_distance_sq = delta_x.square() + delta_y.square()
    target_radius = traits.collision_radius.clamp(min=0).to(torch.float32)
    center_distance = torch.sqrt(center_distance_sq.to(torch.float32))
    edge_distance = (center_distance - target_radius[:, None, :]).clamp_min(0.0)

    candidate = (
        source_can_act[:, :, None]
        & target_present[:, None, :]
        & (state.owner[:, :, None] != state.owner[:, None, :])
        & target_plane_allowed
        & target_category_allowed
        & within_edge_range(
            center_distance_sq,
            traits.collision_radius[:, None, :],
            state.sight_range_units[:, :, None],
        )
    )

    infinity = torch.full_like(edge_distance, torch.inf)
    nearest_edge = torch.where(candidate, edge_distance, infinity).amin(dim=2)
    distance_tie = candidate & (edge_distance == nearest_edge[:, :, None])
    maximum_id = torch.iinfo(torch.int64).max
    candidate_id = state.stable_id[:, None, :].expand_as(center_distance_sq)
    selected_id = torch.where(
        distance_tie,
        candidate_id,
        torch.full_like(candidate_id, maximum_id),
    ).amin(dim=2)
    found = distance_tie.any(dim=2)
    selected = distance_tie & (candidate_id == selected_id[:, :, None])
    selected_slot = selected.to(torch.int64).argmax(dim=2)
    target_slot = torch.where(found, selected_slot, -1)

    selected_center = center_distance.gather(2, selected_slot[:, :, None]).squeeze(2)
    selected_edge = edge_distance.gather(2, selected_slot[:, :, None]).squeeze(2)
    selected_center = torch.where(found, selected_center, torch.inf)
    selected_edge = torch.where(found, selected_edge, torch.inf)
    selected_squared = center_distance_sq.gather(2, selected_slot[:, :, None]).squeeze(
        2
    )
    selected_radius = traits.collision_radius.gather(1, selected_slot)
    within_attack_range = found & within_edge_range(
        selected_squared, selected_radius, state.range_units
    )
    return FastTargetSelection(
        found=found,
        target_slot=target_slot,
        target_id=torch.where(found, selected_id, 0),
        center_distance=selected_center,
        edge_distance=selected_edge,
        within_attack_range=within_attack_range,
    )
