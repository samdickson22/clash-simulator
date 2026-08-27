from __future__ import annotations

import pytest
import torch

from clasher.torch_sim.simple_state import FAST_KIND_BUILDING, FastGymState
from clasher.torch_sim.simple_targeting import (
    FastTargetTraits,
    select_nearest_targets,
)


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _state_and_traits(
    device_name: str, *, entities: int = 5
) -> tuple[FastGymState, FastTargetTraits, torch.Tensor, torch.Tensor]:
    device = _device(device_name)
    state = FastGymState.empty(1, max_entities=entities, device=device)
    state.active[0] = True
    state.stable_id[0] = torch.arange(1, entities + 1, device=device)
    state.next_stable_id[0] = entities + 1
    state.hp[0] = 1_000
    state.max_hp[0] = 1_000
    state.sight_range_units[0] = 10_000
    state.range_units[0] = 1_000
    traits = FastTargetTraits(
        airborne=torch.zeros_like(state.active),
        building=torch.zeros_like(state.active),
        attacks_air=torch.zeros_like(state.active),
        attacks_ground=torch.ones_like(state.active),
        buildings_only=torch.zeros_like(state.active),
        collision_radius=torch.zeros_like(state.x_units),
    )
    return (
        state,
        traits,
        torch.zeros_like(state.active),
        torch.zeros_like(state.active),
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_giant_buildings_only_ignores_nearer_ground_troop(device_name: str) -> None:
    state, traits, disabled, unavailable = _state_and_traits(device_name)
    state.owner[0] = torch.tensor([0, 1, 1, 0, 0], device=state.device)
    state.x_units[0] = torch.tensor([0, 500, 2_000, 0, 0], device=state.device)
    traits.buildings_only[0, 0] = True  # Giant
    traits.building[0, 2] = True
    state.kind[0, 2] = FAST_KIND_BUILDING

    selected = select_nearest_targets(
        state,
        traits,
        source_disabled=disabled,
        target_unavailable=unavailable,
    )

    assert selected.target_id[0, 0].item() == 3
    assert selected.target_slot[0, 0].item() == 2


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_baby_dragon_can_select_air_and_ground_targets(device_name: str) -> None:
    state, traits, disabled, unavailable = _state_and_traits(device_name)
    state.owner[0] = torch.tensor([0, 1, 1, 0, 0], device=state.device)
    state.x_units[0] = torch.tensor([0, 1_000, 2_000, 0, 0], device=state.device)
    traits.attacks_air[0, 0] = True  # Baby Dragon attacks both planes.
    traits.airborne[0, 1] = True

    air_selected = select_nearest_targets(
        state,
        traits,
        source_disabled=disabled,
        target_unavailable=unavailable,
    )
    unavailable[0, 1] = True
    ground_selected = select_nearest_targets(
        state,
        traits,
        source_disabled=disabled,
        target_unavailable=unavailable,
    )

    assert air_selected.target_id[0, 0].item() == 2
    assert ground_selected.target_id[0, 0].item() == 3


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_ground_only_source_ignores_air_and_disabled_source_cannot_acquire(
    device_name: str,
) -> None:
    state, traits, disabled, unavailable = _state_and_traits(device_name)
    state.owner[0] = torch.tensor([0, 1, 1, 0, 0], device=state.device)
    state.x_units[0] = torch.tensor([0, 500, 1_000, 0, 0], device=state.device)
    traits.airborne[0, 1] = True

    selected = select_nearest_targets(
        state,
        traits,
        source_disabled=disabled,
        target_unavailable=unavailable,
    )
    disabled[0, 0] = True
    blocked = select_nearest_targets(
        state,
        traits,
        source_disabled=disabled,
        target_unavailable=unavailable,
    )

    assert selected.target_id[0, 0].item() == 3
    assert not blocked.found[0, 0]
    assert blocked.target_slot[0, 0].item() == -1


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_collision_edge_controls_sight_and_attack_range(device_name: str) -> None:
    state, traits, disabled, unavailable = _state_and_traits(device_name, entities=2)
    state.owner[0] = torch.tensor([0, 1], device=state.device)
    state.x_units[0] = torch.tensor([0, 1_500], device=state.device)
    state.sight_range_units[0, 0] = 700
    state.range_units[0, 0] = 700
    traits.collision_radius[0, 1] = 800

    selected = select_nearest_targets(
        state,
        traits,
        source_disabled=disabled,
        target_unavailable=unavailable,
    )

    assert selected.found[0, 0]
    assert selected.center_distance[0, 0].item() == 1_500
    assert selected.edge_distance[0, 0].item() == 700
    assert selected.within_attack_range[0, 0]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_stable_id_breaks_equal_distance_tie_after_slot_reuse(
    device_name: str,
) -> None:
    state, traits, disabled, unavailable = _state_and_traits(device_name, entities=3)
    state.owner[0] = torch.tensor([0, 1, 1], device=state.device)
    # Slot one has been reused for a later spawn (ID 9); slot two retains ID 2.
    state.stable_id[0] = torch.tensor([1, 9, 2], device=state.device)
    state.next_stable_id[0] = 10
    state.x_units[0] = torch.tensor([5_000, 4_000, 6_000], device=state.device)

    selected = select_nearest_targets(
        state,
        traits,
        source_disabled=disabled,
        target_unavailable=unavailable,
    )

    assert selected.target_id[0, 0].item() == 2
    assert selected.target_slot[0, 0].item() == 2


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_unavailable_target_is_fail_closed_but_disabled_target_remains_visible(
    device_name: str,
) -> None:
    state, traits, disabled, unavailable = _state_and_traits(device_name, entities=3)
    state.owner[0] = torch.tensor([0, 1, 1], device=state.device)
    state.x_units[0] = torch.tensor([0, 500, 1_000], device=state.device)
    disabled[0, 1] = True

    disabled_target = select_nearest_targets(
        state,
        traits,
        source_disabled=disabled,
        target_unavailable=unavailable,
    )
    unavailable[0, 1] = True
    hidden_target = select_nearest_targets(
        state,
        traits,
        source_disabled=disabled,
        target_unavailable=unavailable,
    )

    assert disabled_target.target_id[0, 0].item() == 2
    assert hidden_target.target_id[0, 0].item() == 3


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_pending_deployment_is_targetable_but_cannot_act(device_name: str) -> None:
    state, traits, disabled, unavailable = _state_and_traits(device_name, entities=3)
    state.owner[0] = torch.tensor([0, 1, 0], device=state.device)
    state.x_units[0] = torch.tensor([0, 500, 1_000], device=state.device)
    state.deploy_ticks[0, 1] = 10
    state.deploy_ticks[0, 2] = 10

    selected = select_nearest_targets(
        state,
        traits,
        source_disabled=disabled,
        target_unavailable=unavailable,
    )

    assert selected.target_id[0, 0].item() == 2
    assert not selected.found[0, 2]
