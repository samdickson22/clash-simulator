from __future__ import annotations

import inspect

import pytest
import torch

from clasher.torch_sim.simple_navigation import (
    FAST_ARENA_HEIGHT_UNITS,
    FAST_ARENA_WIDTH_UNITS,
    FAST_ROUTE_APPROACH_BANK,
    FAST_ROUTE_CROSS_BRIDGE,
    FAST_ROUTE_DIRECT,
    FastArenaNavigation,
    FastNavigationState,
)


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _inputs(
    device_name: str,
    *,
    entities: int = 1,
) -> tuple[FastArenaNavigation, dict[str, torch.Tensor]]:
    device = _device(device_name)
    navigation = FastArenaNavigation(
        FastNavigationState.empty(1, entities, device=device)
    )
    inputs = {
        "active": torch.ones((1, entities), dtype=torch.bool, device=device),
        "mover_stable_id": torch.arange(
            1, entities + 1, dtype=torch.int64, device=device
        ).view(1, -1),
        "owner": torch.zeros((1, entities), dtype=torch.int8, device=device),
        "airborne": torch.zeros((1, entities), dtype=torch.bool, device=device),
        "x_units": torch.full((1, entities), 3_500, dtype=torch.int32, device=device),
        "y_units": torch.full((1, entities), 8_000, dtype=torch.int32, device=device),
        "target_stable_id": torch.full(
            (1, entities), 100, dtype=torch.int64, device=device
        ),
        "target_owner": torch.ones((1, entities), dtype=torch.int8, device=device),
        "target_x_units": torch.full(
            (1, entities), 3_500, dtype=torch.int32, device=device
        ),
        "target_y_units": torch.full(
            (1, entities), 24_000, dtype=torch.int32, device=device
        ),
    }
    return navigation, inputs


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_same_lane_ground_route_uses_left_bridge_waypoints(device_name: str) -> None:
    navigation, inputs = _inputs(device_name)

    approach = navigation.route_(**inputs)
    assert approach.route_phase.tolist() == [[FAST_ROUTE_APPROACH_BANK]]
    assert approach.bridge_index.tolist() == [[0]]
    assert approach.waypoint_x_units.tolist() == [[3_500]]
    assert approach.waypoint_y_units.tolist() == [[14_500]]

    inputs["x_units"].fill_(3_500)
    inputs["y_units"].fill_(14_500)
    crossing = navigation.route_(**inputs)
    assert crossing.route_phase.tolist() == [[FAST_ROUTE_CROSS_BRIDGE]]
    assert crossing.waypoint_x_units.tolist() == [[3_500]]
    assert crossing.waypoint_y_units.tolist() == [[17_500]]

    inputs["y_units"].fill_(17_500)
    direct = navigation.route_(**inputs)
    assert direct.route_phase.tolist() == [[FAST_ROUTE_DIRECT]]
    assert direct.bridge_index.tolist() == [[-1]]
    assert direct.waypoint_x_units.tolist() == [[3_500]]
    assert direct.waypoint_y_units.tolist() == [[24_000]]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_cross_lane_route_chooses_shortest_valid_bridge(device_name: str) -> None:
    navigation, inputs = _inputs(device_name)
    inputs["target_x_units"].fill_(16_000)

    route = navigation.route_(**inputs)

    assert route.bridge_index.tolist() == [[1]]
    assert route.waypoint_x_units.tolist() == [[14_500]]
    assert route.waypoint_y_units.tolist() == [[14_500]]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_same_side_ground_and_air_routes_are_direct(device_name: str) -> None:
    navigation, inputs = _inputs(device_name, entities=2)
    inputs["x_units"][0] = torch.tensor([2_000, 2_000], device=navigation.state.device)
    inputs["y_units"][0] = torch.tensor([8_000, 8_000], device=navigation.state.device)
    inputs["target_x_units"][0] = torch.tensor(
        [9_000, 9_000], device=navigation.state.device
    )
    inputs["target_y_units"][0] = torch.tensor(
        [12_000, 24_000], device=navigation.state.device
    )
    inputs["airborne"][0, 1] = True

    route = navigation.route_(**inputs)

    assert route.route_phase.tolist() == [[FAST_ROUTE_DIRECT, FAST_ROUTE_DIRECT]]
    assert route.routed_via_bridge.tolist() == [[False, False]]
    assert route.waypoint_x_units.tolist() == [[9_000, 9_000]]
    assert route.waypoint_y_units.tolist() == [[12_000, 24_000]]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_owner_mirror_preserves_route_under_arena_rotation(device_name: str) -> None:
    navigation, inputs = _inputs(device_name, entities=2)
    inputs["mover_stable_id"][0] = torch.tensor([1, 2], device=navigation.state.device)
    inputs["target_stable_id"][0] = torch.tensor(
        [101, 102], device=navigation.state.device
    )
    inputs["owner"][0] = torch.tensor([0, 1], device=navigation.state.device)
    inputs["target_owner"][0] = torch.tensor([1, 0], device=navigation.state.device)
    inputs["x_units"][0] = torch.tensor(
        [9_000, FAST_ARENA_WIDTH_UNITS - 9_000], device=navigation.state.device
    )
    inputs["target_x_units"][0] = torch.tensor(
        [9_000, FAST_ARENA_WIDTH_UNITS - 9_000], device=navigation.state.device
    )
    inputs["y_units"][0] = torch.tensor(
        [8_000, FAST_ARENA_HEIGHT_UNITS - 8_000], device=navigation.state.device
    )
    inputs["target_y_units"][0] = torch.tensor(
        [24_000, FAST_ARENA_HEIGHT_UNITS - 24_000],
        device=navigation.state.device,
    )

    route = navigation.route_(**inputs)

    assert route.bridge_index.tolist() == [[0, 1]]
    assert route.waypoint_x_units[0, 1].item() == (
        FAST_ARENA_WIDTH_UNITS - route.waypoint_x_units[0, 0].item()
    )
    assert route.waypoint_y_units[0, 1].item() == (
        FAST_ARENA_HEIGHT_UNITS - route.waypoint_y_units[0, 0].item()
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_identity_changes_slot_reuse_and_explicit_reset_clear_route(
    device_name: str,
) -> None:
    navigation, inputs = _inputs(device_name)
    first = navigation.route_(**inputs)
    assert first.bridge_index.tolist() == [[0]]

    # A new stable target in the same physical target slot starts a new route.
    inputs["target_stable_id"].fill_(101)
    inputs["target_x_units"].fill_(16_000)
    second = navigation.route_(**inputs)
    assert second.bridge_index.tolist() == [[1]]

    # A changed target on the current side abandons the retained bridge route.
    inputs["target_stable_id"].fill_(102)
    inputs["target_y_units"].fill_(12_000)
    direct = navigation.route_(**inputs)
    assert direct.route_phase.tolist() == [[FAST_ROUTE_DIRECT]]
    assert direct.bridge_index.tolist() == [[-1]]

    # Reusing the mover slot must not inherit the previous occupant's lock.
    inputs["mover_stable_id"].fill_(2)
    inputs["target_stable_id"].fill_(103)
    inputs["target_x_units"].fill_(3_500)
    inputs["target_y_units"].fill_(24_000)
    reused = navigation.route_(**inputs)
    assert reused.bridge_index.tolist() == [[0]]
    assert navigation.state.mover_stable_id.tolist() == [[2]]

    navigation.state.reset_(torch.ones_like(inputs["active"]))
    assert navigation.state.route_phase.tolist() == [[FAST_ROUTE_DIRECT]]
    assert navigation.state.bridge_index.tolist() == [[-1]]
    assert navigation.state.mover_stable_id.tolist() == [[0]]
    assert navigation.state.target_stable_id.tolist() == [[0]]

    inputs["active"].zero_()
    inactive = navigation.route_(**inputs)
    assert not inactive.routed_via_bridge.any()
    assert navigation.state.target_stable_id.tolist() == [[0]]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_navigation_replay_is_deterministic(device_name: str) -> None:
    first, first_inputs = _inputs(device_name, entities=3)
    second, second_inputs = _inputs(device_name, entities=3)
    first_inputs["x_units"][0] = torch.tensor(
        [2_000, 9_000, 16_000], device=first.state.device
    )
    second_inputs["x_units"].copy_(first_inputs["x_units"])
    first_inputs["target_x_units"][0] = torch.tensor(
        [14_000, 9_000, 4_000], device=first.state.device
    )
    second_inputs["target_x_units"].copy_(first_inputs["target_x_units"])

    for y in (8_000, 14_500, 16_000, 17_500, 19_000):
        first_inputs["y_units"].fill_(y)
        second_inputs["y_units"].fill_(y)
        first_result = first.route_(**first_inputs)
        second_result = second.route_(**second_inputs)
        assert torch.equal(
            first_result.waypoint_x_units, second_result.waypoint_x_units
        )
        assert torch.equal(
            first_result.waypoint_y_units, second_result.waypoint_y_units
        )
        assert torch.equal(first_result.route_phase, second_result.route_phase)
        assert torch.equal(first_result.bridge_index, second_result.bridge_index)


def test_navigation_hot_path_is_tensor_only_and_card_agnostic() -> None:
    source = inspect.getsource(FastArenaNavigation.route_)
    for forbidden in (
        ".item(",
        ".tolist(",
        ".cpu(",
        ".numpy(",
        ".nonzero(",
        "card_id",
        "card_name",
    ):
        assert forbidden not in source
