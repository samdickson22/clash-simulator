"""Bounded greedy chain targeting for the practical tensor Gym.

The helper models only attack topology. Damage, statuses, target planes, and
effect timing remain caller-owned. A committed primary hit anchors the chain;
each later hop chooses the nearest eligible, unvisited stable entity within the
serialized radius. Equal-distance targets use ascending stable identity.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

FAST_MAX_CHAIN_TARGETS = 9


@dataclass(frozen=True)
class FastChainTopologyInputs:
    """Fixed-shape chain commands and their shared entity candidate pool.

    Command tensors use shape ``[B, C]``; entity tensors use ``[B, E]`` and
    ``eligible`` uses ``[B, C, E]``. ``target_count`` includes the committed
    primary. Source coordinates provide the fail-closed fallback origin when a
    primary is absent; no secondary is selected unless that primary resolves.
    """

    source_x_units: torch.Tensor
    source_y_units: torch.Tensor
    primary_target_id: torch.Tensor
    primary_x_units: torch.Tensor
    primary_y_units: torch.Tensor
    entity_stable_id: torch.Tensor
    entity_x_units: torch.Tensor
    entity_y_units: torch.Tensor
    eligible: torch.Tensor
    hop_radius_units: torch.Tensor
    target_count: torch.Tensor


def _validate(inputs: FastChainTopologyInputs) -> tuple[int, int, int]:
    command_shape = tuple(inputs.source_x_units.shape)
    if len(command_shape) != 2:
        raise ValueError("command tensors must have shape [batch, commands]")
    batch, commands = command_shape
    device = inputs.source_x_units.device
    command_dtypes = {
        "source_x_units": torch.int32,
        "source_y_units": torch.int32,
        "primary_target_id": torch.int64,
        "primary_x_units": torch.int32,
        "primary_y_units": torch.int32,
        "hop_radius_units": torch.int32,
        "target_count": torch.int16,
    }
    for name, dtype in command_dtypes.items():
        value = getattr(inputs, name)
        if tuple(value.shape) != command_shape:
            raise ValueError(f"{name} must have shape [batch, commands]")
        if value.device != device:
            raise ValueError(f"{name} is on a different device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")

    entity_shape = tuple(inputs.entity_stable_id.shape)
    if len(entity_shape) != 2 or entity_shape[0] != batch:
        raise ValueError("entity tensors must have shape [batch, entities]")
    _, entities = entity_shape
    entity_dtypes = {
        "entity_stable_id": torch.int64,
        "entity_x_units": torch.int32,
        "entity_y_units": torch.int32,
    }
    for name, dtype in entity_dtypes.items():
        value = getattr(inputs, name)
        if tuple(value.shape) != entity_shape:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.device != device:
            raise ValueError(f"{name} is on a different device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    if tuple(inputs.eligible.shape) != (batch, commands, entities):
        raise ValueError("eligible must have shape [batch, commands, entities]")
    if inputs.eligible.device != device or inputs.eligible.dtype != torch.bool:
        raise ValueError("eligible must be bool on the command device")
    return batch, commands, entities


def fast_chain_hit_count(inputs: FastChainTopologyInputs) -> torch.Tensor:
    """Return integer per-command entity hit counts with shape ``[B, C, E]``.

    The implementation uses a constant nine-lane loop, dense reductions, and
    in-place writes to fixed-shape temporary tensors. It performs no host sync,
    dynamic compaction, or card dispatch. Counts outside the supported range
    are clamped: nonpositive commands produce no hit and values above nine use
    the first nine recipients.
    """

    _validate(inputs)
    stable_id = inputs.entity_stable_id
    valid_identity = stable_id > 0
    target_count = inputs.target_count.to(torch.int64).clamp(
        min=0, max=FAST_MAX_CHAIN_TARGETS
    )
    chain_enabled = target_count > 0

    primary_candidates = (
        inputs.eligible
        & valid_identity[:, None, :]
        & (inputs.primary_target_id[:, :, None] > 0)
        & (stable_id[:, None, :] == inputs.primary_target_id[:, :, None])
    )
    # Stable IDs are unique in a valid Gym state. The cumulative guard keeps
    # corrupt duplicate identities deterministic and prevents double damage.
    primary = primary_candidates & (
        primary_candidates.to(torch.int16).cumsum(dim=2) == 1
    )
    primary &= chain_enabled[:, :, None]
    primary_found = primary.any(dim=2)

    hit_count = primary.to(torch.int16)
    visited = primary.clone()
    current_x = torch.where(
        primary_found,
        inputs.primary_x_units,
        inputs.source_x_units,
    ).to(torch.int64)
    current_y = torch.where(
        primary_found,
        inputs.primary_y_units,
        inputs.source_y_units,
    ).to(torch.int64)
    radius_sq = inputs.hop_radius_units.to(torch.int64).clamp(min=0).square()
    maximum = torch.iinfo(torch.int64).max

    for hop in range(1, FAST_MAX_CHAIN_TARGETS):
        dx = inputs.entity_x_units[:, None, :].to(torch.int64) - current_x[:, :, None]
        dy = inputs.entity_y_units[:, None, :].to(torch.int64) - current_y[:, :, None]
        distance_sq = dx.square() + dy.square()
        needed = primary_found & (target_count > hop)
        candidates = (
            inputs.eligible
            & valid_identity[:, None, :]
            & ~visited
            & needed[:, :, None]
            & (distance_sq <= radius_sq[:, :, None])
        )
        candidate_distance = torch.where(
            candidates,
            distance_sq,
            torch.full_like(distance_sq, maximum),
        )
        nearest_distance = candidate_distance.amin(dim=2)
        nearest = candidates & (distance_sq == nearest_distance[:, :, None])
        nearest_id = torch.where(
            nearest,
            stable_id[:, None, :],
            torch.full_like(distance_sq, maximum),
        ).amin(dim=2)
        selected = nearest & (stable_id[:, None, :] == nearest_id[:, :, None])
        selected &= selected.to(torch.int16).cumsum(dim=2) == 1
        selected_found = selected.any(dim=2)
        hit_count.add_(selected.to(torch.int16))
        visited |= selected
        selected_x = torch.where(
            selected,
            inputs.entity_x_units[:, None, :],
            0,
        ).sum(dim=2, dtype=torch.int64)
        selected_y = torch.where(
            selected,
            inputs.entity_y_units[:, None, :],
            0,
        ).sum(dim=2, dtype=torch.int64)
        current_x = torch.where(selected_found, selected_x, current_x)
        current_y = torch.where(selected_found, selected_y, current_y)

    return hit_count


def clone_fast_chain_inputs(inputs: FastChainTopologyInputs) -> FastChainTopologyInputs:
    """Return an isolated input clone for deterministic replay fixtures."""

    return type(inputs)(
        **{
            descriptor.name: getattr(inputs, descriptor.name).clone()
            for descriptor in fields(inputs)
        }
    )
