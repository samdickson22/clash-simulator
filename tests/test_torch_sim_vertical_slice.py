from collections import deque

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.torch_sim import (
    TensorBattleState,
    TorchBattleExecutor,
    first_divergence,
)
from clasher.torch_sim.diagnostics import battle_snapshot


def _assert_exact_battle_match(expected: BattleState, actual: BattleState) -> None:
    mismatch = first_divergence(
        battle_snapshot(expected),
        battle_snapshot(actual),
    )
    assert mismatch is None, str(mismatch)


def _battle_with_deployed_card(card_name: str) -> BattleState:
    battle = BattleState()
    player = battle.players[0]
    player.elixir = 10.0
    player.hand = [card_name, None, None, None]
    player.deck = [card_name]
    player.cycle_queue = deque()
    assert battle.deploy_card(0, card_name, Position(9.0, 10.0))
    return battle


@pytest.mark.parametrize(
    ("start_time", "ticks"),
    [
        (0.0, 1),
        (0.0, 100),
        (119.9, 5),
        (179.9, 5),
        (239.9, 5),
        (299.9, 5),
    ],
)
def test_pytorch_idle_complete_ticks_match_python_exactly(
    start_time: float,
    ticks: int,
) -> None:
    expected = BattleState()
    actual = expected.clone()
    expected.time = start_time
    actual.time = start_time

    expected.players[0].hand[1] = None
    actual.players[0].hand[1] = None
    expected.players[0].cycle_queue = deque(["Musketeer"])
    actual.players[0].cycle_queue = deque(["Musketeer"])
    expected.players[0].next_card_refill_cooldown_ms = 50
    actual.players[0].next_card_refill_cooldown_ms = 50

    expected.step_logic_ticks(ticks)
    executor = TorchBattleExecutor("pytorch")
    advanced = executor.step_logic_ticks(actual, ticks)

    _assert_exact_battle_match(expected, actual)
    assert advanced == min(ticks, expected.tick)
    assert executor.metrics_dict()["tensor_ticks"] == advanced
    assert executor.metrics_dict()["python_ticks"] == 0


def test_tensor_state_is_dense_batched_and_uses_native_coordinates() -> None:
    first = BattleState()
    second = BattleState()
    state = TensorBattleState.from_battles([first, second], max_entities=16)

    assert state.tick.shape == (2,)
    assert state.elixir.shape == (2, 2)
    assert state.entity_id.shape == (2, 16)
    assert state.entity_id[0, :6].tolist() == [1, 2, 3, 4, 5, 6]
    assert state.entity_x_units[0, :6].tolist() == [
        3500,
        14500,
        9000,
        3500,
        14500,
        9000,
    ]
    assert state.entity_y_units[0, :6].tolist() == [
        6500,
        6500,
        2500,
        25500,
        25500,
        29500,
    ]


def test_shadow_mode_runs_exact_differential_check() -> None:
    battle = BattleState()
    executor = TorchBattleExecutor("pytorch-shadow")

    assert executor.step_logic_ticks(battle, 8) == 8
    assert executor.metrics_dict() == {
        "tensor_ticks": 8.0,
        "python_ticks": 8.0,
        "shadow_checks": 1.0,
        "shadow_mismatches": 0.0,
        "unsupported_fallbacks": 0.0,
    }


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
def test_twelve_battles_advance_in_one_exact_tensor_batch(backend: str) -> None:
    starts = [
        0.0,
        1.25,
        119.9,
        120.0,
        179.9,
        180.0,
        239.9,
        240.0,
        299.9,
        0.05,
        42.0,
        118.0,
    ]
    actual = [BattleState() for _ in starts]
    expected = [battle.clone() for battle in actual]
    for start, reference, candidate in zip(starts, expected, actual):
        reference.time = start
        candidate.time = start
        reference.step_logic_ticks(8)

    executor = TorchBattleExecutor(backend)
    advanced = executor.step_battles(actual, 8)

    for reference, candidate in zip(expected, actual):
        _assert_exact_battle_match(reference, candidate)
    assert advanced == [8, 8, 8, 8, 8, 8, 8, 8, 2, 8, 8, 8]
    assert executor.metrics_dict()["tensor_ticks"] == sum(advanced)
    if backend == "pytorch-shadow":
        assert executor.metrics_dict()["shadow_checks"] == 12


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
def test_mechanic_free_deployment_frames_match_exactly(backend: str) -> None:
    battle = _battle_with_deployed_card("Knight")
    expected = battle.clone()
    expected.step_logic_ticks(8)

    executor = TorchBattleExecutor(backend)
    assert executor.step_logic_ticks(battle, 8) == 8

    _assert_exact_battle_match(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 8
    assert executor.metrics_dict()["unsupported_fallbacks"] == 0


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
def test_deployment_window_continues_in_python_at_first_actionable_frame(
    backend: str,
) -> None:
    battle = _battle_with_deployed_card("Knight")
    expected = battle.clone()
    expected.step_logic_ticks(25)

    executor = TorchBattleExecutor(backend)
    assert executor.step_logic_ticks(battle, 25) == 25

    _assert_exact_battle_match(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 20
    assert executor.metrics_dict()["unsupported_fallbacks"] == 1
    expected_python_ticks = 25 if backend == "pytorch-shadow" else 5
    assert executor.metrics_dict()["python_ticks"] == expected_python_ticks


def test_mixed_batch_falls_back_only_for_unsupported_member() -> None:
    idle = BattleState()
    combat = _battle_with_deployed_card("ArcherQueen")
    expected_idle = idle.clone()
    expected_combat = combat.clone()
    expected_idle.step_logic_ticks(4)
    expected_combat.step_logic_ticks(4)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_battles([idle, combat], 4) == [4, 4]

    _assert_exact_battle_match(expected_idle, idle)
    _assert_exact_battle_match(expected_combat, combat)
    assert executor.metrics_dict()["tensor_ticks"] == 4
    assert executor.metrics_dict()["python_ticks"] == 4
    assert executor.metrics_dict()["unsupported_fallbacks"] == 1


def test_pytorch_on_fails_closed_for_mechanic_bearing_deployment() -> None:
    battle = _battle_with_deployed_card("ArcherQueen")
    expected = battle.clone()

    expected.step_logic_ticks(3)
    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(battle, 3) == 3

    _assert_exact_battle_match(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 0
    assert executor.metrics_dict()["python_ticks"] == 3
    assert executor.metrics_dict()["unsupported_fallbacks"] == 1


def test_deployment_at_exact_body_contact_fails_closed() -> None:
    battle = _battle_with_deployed_card("Knight")
    knight = max(battle.entities.values(), key=lambda entity: entity.id)
    tower = battle.entities[1]
    contact_distance = knight.get_collision_radius() + tower.get_collision_radius()
    knight.position = Position(tower.position.x + contact_distance, tower.position.y)
    expected = battle.clone()
    expected.step_logic_ticks(1)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(battle, 1) == 1

    _assert_exact_battle_match(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 0
    assert executor.metrics_dict()["python_ticks"] == 1
    assert executor.metrics_dict()["unsupported_fallbacks"] == 1


@pytest.mark.parametrize("backend", ["python", "pytorch-shadow", "pytorch"])
def test_training_environment_selects_simulation_backend(backend: str) -> None:
    env = SelfPlayBattleEnv(
        decision_interval_ticks=2,
        max_ticks=4,
        simulation_backend=backend,
    )
    env.reset(seed=2301)
    no_op = env.action_space.no_op_action

    _, _, info = env.step({0: no_op, 1: no_op})

    assert info.ticks_advanced == 2
    metrics = env.simulator_backend_metrics()
    if backend == "python":
        # The existing Python idle fast-forward remains outside the executor.
        assert metrics["tensor_ticks"] == 0
    else:
        assert metrics["tensor_ticks"] == 2


def test_training_environment_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="simulation_backend must be one of"):
        SelfPlayBattleEnv(simulation_backend="unknown")
