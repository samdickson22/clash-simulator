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


def test_pytorch_on_fails_closed_to_python_for_combat_state() -> None:
    battle = BattleState()
    player = battle.players[0]
    player.elixir = 10.0
    player.hand = ["Knight", None, None, None]
    player.deck = ["Knight"]
    player.cycle_queue = deque()
    assert battle.deploy_card(0, "Knight", Position(9.0, 10.0))
    expected = battle.clone()

    expected.step_logic_ticks(3)
    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(battle, 3) == 3

    _assert_exact_battle_match(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 0
    assert executor.metrics_dict()["python_ticks"] == 3
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
