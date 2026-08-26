from __future__ import annotations

import inspect

import pytest
import torch

from clasher.battle import BattleState
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
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


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_simple_knights_acquire_move_and_emit_one_committable_attack(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    battle = BattleState()
    full_catalog = TensorCardCatalog.compile(
        battle.card_loader, ["Knight"], device=device
    )
    catalog = FastCardCatalog.from_tensor_catalog(full_catalog)
    knight = full_catalog.name_to_id["Knight"]
    state = FastGymState.empty(1, max_entities=4, device=device)
    state.active[0, :2] = True
    state.stable_id[0, :2] = torch.tensor([1, 2], device=device)
    state.next_stable_id[0] = 3
    state.owner[0, :2] = torch.tensor([0, 1], device=device)
    state.card_id[0, :2] = knight
    state.kind[0, :2] = catalog.kind[knight]
    state.x_units[0, :2] = torch.tensor([5_000, 7_000], device=device)
    state.y_units[0, :2] = 10_000
    state.hp[0, :2] = catalog.hitpoints[knight]
    state.max_hp[0, :2] = catalog.hitpoints[knight]
    state.damage[0, :2] = catalog.damage[knight]
    state.range_units[0, :2] = catalog.range_units[knight]
    state.sight_range_units[0, :2] = catalog.sight_range_units[knight]
    state.speed_units_per_tick[0, :2] = catalog.speed_units_per_tick[knight]
    state.hit_cooldown_ticks[0, :2] = catalog.hit_cooldown_ticks[knight]
    gym = FastTensorGym(state, catalog)

    before_gap = int(state.x_units[0, 1] - state.x_units[0, 0])
    gym.step_tick()
    after_gap = int(state.x_units[0, 1] - state.x_units[0, 0])
    assert state.target_id[0, :2].tolist() == [2, 1]
    assert 0 < after_gap < before_gap

    for _ in range(80):
        result = gym.step_tick()
        if bool(result.attack_ready.all()):
            break
    assert result.attack_ready[0, :2].tolist() == [True, True]
    assert not result.attack_ready[0, 2:].any()
    assert state.hp[0, :2].tolist() == state.max_hp[0, :2].tolist()
    assert state.cooldown_ticks[0, :2].tolist() == [0, 0]

    committed = gym.commit_attacks_(result.attack_ready, result.attack_ready)
    assert committed[0, :2].tolist() == [True, True]
    assert not committed[0, 2:].any()
    assert state.cooldown_ticks[0, :2].tolist() == (
        state.hit_cooldown_ticks[0, :2].tolist()
    )
    following = gym.step_tick()
    assert not bool(following.attack_ready.any())
    assert state.cooldown_ticks[0, :2].tolist() == (
        state.hit_cooldown_ticks[0, :2].sub(1).tolist()
    )


def test_simple_combat_hot_path_has_no_host_sync_or_dynamic_compaction() -> None:
    source = inspect.getsource(FastTensorGym._ordinary_troop_phase)
    source += inspect.getsource(FastTensorGym.step_tick)
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
        assert forbidden not in source


def test_simple_target_tie_uses_stable_id_not_reused_physical_slot() -> None:
    state = FastGymState.empty(1, max_entities=4)
    state.active[0, :3] = True
    state.stable_id[0, :3] = torch.tensor([1, 9, 2])
    state.next_stable_id[0] = 10
    state.owner[0, :3] = torch.tensor([0, 1, 1])
    state.x_units[0, :3] = torch.tensor([5_000, 4_000, 6_000])
    state.y_units[0, :3] = 10_000
    state.hp[0, :3] = 1_000
    state.max_hp[0, :3] = 1_000
    state.sight_range_units[0, :3] = 10_000

    FastTensorGym(state).step_tick()

    assert int(state.target_id[0, 0]) == 2
