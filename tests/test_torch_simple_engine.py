from __future__ import annotations

import pytest
import torch

from clasher.torch_sim.simple_engine import FastDeploymentRequest, FastTensorGym
from clasher.torch_sim.simple_state import FAST_KIND_TROOP, FastGymState


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_simple_noop_clock_and_deterministic_low_slot_deployment(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    state = FastGymState.empty(2, max_entities=4, device=device)
    gym = FastTensorGym(state)

    noop = gym.step_tick()
    assert noop.committed.tolist() == [True, True]
    assert noop.action_success.tolist() == [[False, False], [False, False]]
    assert noop.native_ticks.tolist() == [1, 1]
    assert state.tick.tolist() == [1, 1]

    request = FastDeploymentRequest(
        valid=torch.tensor([True, False], device=device),
        owner=torch.tensor([1, 0], device=device),
        card_id=torch.tensor([17, 17], device=device),
        kind=torch.tensor([FAST_KIND_TROOP, FAST_KIND_TROOP], device=device),
        x_units=torch.tensor([4_500, 13_500], device=device),
        y_units=torch.tensor([20_500, 11_500], device=device),
        hp=torch.tensor([720.0, 720.0], device=device),
        deploy_ticks=torch.tensor([2, 2], device=device),
    )
    deployed = gym.step_tick(request)

    assert deployed.action_success.tolist() == [[False, True], [False, False]]
    assert deployed.native_ticks.tolist() == [1, 1]
    assert state.tick.tolist() == [2, 2]
    assert state.active.tolist() == [
        [True, False, False, False],
        [False, False, False, False],
    ]
    assert state.stable_id[0].tolist() == [1, 0, 0, 0]
    assert state.card_id[0].tolist() == [17, 0, 0, 0]
    assert state.owner[0, 0].item() == 1
    assert state.deploy_ticks[0, 0].item() == 1

    state.active[0, 0] = False
    state.hp[0, 0] = 0.0
    recycled = gym.step_tick(request)
    assert recycled.action_success.tolist() == [[False, True], [False, False]]
    assert state.stable_id[0].tolist() == [2, 0, 0, 0]
    assert state.next_stable_id.tolist() == [3, 1]
