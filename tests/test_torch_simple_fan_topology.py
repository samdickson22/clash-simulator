from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
import torch

from clasher.torch_sim.simple_fan_topology import (
    FAST_FAN_MAX_RAYS,
    FastFanTopologyResult,
    resolve_fast_fan_topology,
)


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _resolve(
    device_name: str,
    *,
    eligibility: list[bool] | None = None,
) -> FastFanTopologyResult:
    device = _device(device_name)
    # Five serialized rays use offsets [-40, -20, 0, 20, 40] degrees.
    # Entity slots: center, right outer, left outer, between two rays, behind,
    # ineligible center, and a large near-origin target intersecting many rays.
    x = [0, 3_857, -3_857, 1_042, 0, 0, 0]
    y = [6_000, 4_596, 4_596, 5_909, -500, 4_000, 500]
    allowed = eligibility or [True, True, True, True, True, False, True]
    return resolve_fast_fan_topology(
        launch_x_units=torch.tensor([[0]], dtype=torch.int32, device=device),
        launch_y_units=torch.tensor([[-1_000]], dtype=torch.int32, device=device),
        impact_x_units=torch.tensor([[0]], dtype=torch.int32, device=device),
        impact_y_units=torch.tensor([[0]], dtype=torch.int32, device=device),
        range_units=torch.tensor([[10_000]], dtype=torch.int32, device=device),
        radius_units=torch.tensor([[120]], dtype=torch.int32, device=device),
        spread_degrees=torch.tensor([[100.0]], dtype=torch.float32, device=device),
        ray_count=torch.tensor([[5]], dtype=torch.int16, device=device),
        eligibility=torch.tensor([[allowed]], dtype=torch.bool, device=device),
        entity_x_units=torch.tensor([x], dtype=torch.int32, device=device),
        entity_y_units=torch.tensor([y], dtype=torch.int32, device=device),
        entity_collision_radius_units=torch.tensor(
            [[0, 0, 0, 0, 0, 0, 300]], dtype=torch.int32, device=device
        ),
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_center_and_outer_rays_hit_while_between_and_behind_miss(
    device_name: str,
) -> None:
    result = _resolve(device_name)

    assert result.supported.tolist() == [[True]]
    assert result.ray_active.tolist() == [[[True] * FAST_FAN_MAX_RAYS]]
    assert result.entity_hit.tolist() == [
        [[True, True, True, False, False, False, True]]
    ]
    assert result.hit_count.dtype == torch.int32
    assert result.hit_count.tolist() == [[[1, 1, 1, 0, 0, 0, 1]]]
    assert result.targets_hit.tolist() == [[4]]

    # The wide near-origin target overlaps multiple rays geometrically, but its
    # damage multiplier remains one after identity-level deduplication.
    assert int(result.ray_entity_hit[0, 0, :, 6].sum()) > 1
    assert int(result.hit_count[0, 0, 6]) == 1


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_direction_comes_from_launch_to_impact_and_shapes_stay_fixed(
    device_name: str,
) -> None:
    device = _device(device_name)
    result = resolve_fast_fan_topology(
        launch_x_units=torch.tensor([[0, 2_000]], dtype=torch.int32, device=device),
        launch_y_units=torch.tensor([[0, 0]], dtype=torch.int32, device=device),
        impact_x_units=torch.tensor([[1_000, 1_000]], dtype=torch.int32, device=device),
        impact_y_units=torch.tensor([[0, 0]], dtype=torch.int32, device=device),
        range_units=torch.tensor([[2_000, 2_000]], dtype=torch.int32, device=device),
        radius_units=torch.tensor([[50, 50]], dtype=torch.int32, device=device),
        spread_degrees=torch.tensor([[0, 0]], dtype=torch.int32, device=device),
        ray_count=torch.tensor([[1, 1]], dtype=torch.int64, device=device),
        eligibility=torch.ones((1, 2, 3), dtype=torch.bool, device=device),
        entity_x_units=torch.tensor(
            [[2_000, 0, 1_000]], dtype=torch.int32, device=device
        ),
        entity_y_units=torch.tensor([[0, 0, 500]], dtype=torch.int32, device=device),
        entity_collision_radius_units=torch.zeros(
            (1, 3), dtype=torch.int32, device=device
        ),
    )

    assert result.ray_active.shape == (1, 2, FAST_FAN_MAX_RAYS)
    assert result.ray_entity_hit.shape == (1, 2, FAST_FAN_MAX_RAYS, 3)
    assert result.hit_count.tolist() == [[[1, 0, 0], [0, 1, 0]]]
    assert result.ray_direction_x[0, 0, 0].item() == pytest.approx(1.0)
    assert result.ray_direction_x[0, 1, 0].item() == pytest.approx(-1.0)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_unsupported_geometry_fails_closed_without_shape_changes(
    device_name: str,
) -> None:
    device = _device(device_name)
    attacks = 4
    result = resolve_fast_fan_topology(
        launch_x_units=torch.zeros((1, attacks), dtype=torch.int32, device=device),
        launch_y_units=torch.zeros((1, attacks), dtype=torch.int32, device=device),
        impact_x_units=torch.tensor(
            [[0, 1, 1, 1]], dtype=torch.int32, device=device
        ),
        impact_y_units=torch.zeros((1, attacks), dtype=torch.int32, device=device),
        range_units=torch.tensor(
            [[1_000, 0, 1_000, 1_000]], dtype=torch.int32, device=device
        ),
        radius_units=torch.tensor(
            [[10, 10, -1, 10]], dtype=torch.int32, device=device
        ),
        spread_degrees=torch.zeros(
            (1, attacks), dtype=torch.float32, device=device
        ),
        ray_count=torch.tensor([[1, 1, 1, 6]], dtype=torch.int16, device=device),
        eligibility=torch.ones((1, attacks, 2), dtype=torch.bool, device=device),
        entity_x_units=torch.ones((1, 2), dtype=torch.int32, device=device),
        entity_y_units=torch.zeros((1, 2), dtype=torch.int32, device=device),
        entity_collision_radius_units=torch.zeros(
            (1, 2), dtype=torch.int32, device=device
        ),
    )

    assert result.supported.tolist() == [[False, False, False, False]]
    assert not result.ray_active.any()
    assert not result.entity_hit.any()
    assert torch.count_nonzero(result.hit_count) == 0


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_fan_topology_replay_is_bit_stable(device_name: str) -> None:
    first = _resolve(device_name)
    second = _resolve(device_name)

    for descriptor in fields(first):
        assert torch.equal(
            getattr(first, descriptor.name), getattr(second, descriptor.name)
        )


def test_fan_topology_hot_path_has_no_sync_compaction_or_card_dispatch() -> None:
    source = inspect.getsource(resolve_fast_fan_topology)
    for forbidden in (
        ".item(",
        ".tolist(",
        ".cpu(",
        ".nonzero(",
        "masked_select(",
        "card_name",
    ):
        assert forbidden not in source
