import copy
import random
from types import MethodType

import numpy as np
import pytest

from clasher.battle import BattleState
from clasher.rl.oracle_planner import FixedDepthThompsonOracle
from clasher.torch_sim import TensorBattleFork, TorchBattleExecutor
from clasher.torch_sim.diagnostics import battle_snapshot, first_divergence


def _assert_exact_match(expected: BattleState, actual: BattleState) -> None:
    mismatch = first_divergence(
        battle_snapshot(expected),
        battle_snapshot(actual),
    )
    assert mismatch is None, str(mismatch)


def test_tensor_battle_fork_repeats_rows_without_aliasing_root() -> None:
    battle = BattleState()
    root = TensorBattleFork.capture([battle])

    branches = root.fork([0, 0])
    branch_state = branches.state
    root_state = root.state

    assert branches.batch_size == 2
    assert branches.matches_battles([battle.clone(), battle.clone()])
    branch_state.time[0] = 41.0
    branch_state.elixir[0, 0] = 3.0
    assert branch_state.time.tolist() == [41.0, 0.0]
    initial_elixir = float(root_state.elixir[0, 0].item())
    assert branch_state.elixir[:, 0].tolist() == [3.0, initial_elixir]
    assert root_state.time.tolist() == [0.0]
    assert root_state.elixir[:, 0].tolist() == [initial_elixir]


def test_tensor_fork_binding_rejects_mismatch_and_reencodes_post_bind_action() -> None:
    source = BattleState()
    root = TensorBattleFork.capture([source])
    mismatched = source.clone()
    mismatched.players[0].elixir = 4.0
    executor = TorchBattleExecutor("pytorch")

    with pytest.raises(ValueError, match="does not match"):
        executor.prime_tensor_fork([mismatched], root)

    actual = source.clone()
    expected = source.clone()
    executor.prime_tensor_fork([actual], root)
    # Simulate an action occurring between root fork and search advancement.
    actual.players[0].elixir = 4.0
    expected.players[0].elixir = 4.0
    expected.step_logic_ticks(3)

    assert executor.step_logic_ticks(actual, 3) == 3

    _assert_exact_match(expected, actual)
    assert executor.metrics_dict()["tensor_ticks"] == 3
    assert executor.metrics_dict()["unsupported_fallbacks"] == 0


def _no_op_oracle_trace(backend: str):
    battle = BattleState(rng=random.Random(2301))
    input_snapshot = copy.deepcopy(battle_snapshot(battle))
    input_rng = copy.deepcopy(battle.rng.getstate())
    planner = FixedDepthThompsonOracle(
        decision_interval_ticks=2,
        plan_depth=2,
        num_simulations=4,
        rollout_action_samples=8,
        seed=901,
        simulation_backend=backend,
    )
    no_op = planner.action_space.no_op_action

    def only_no_op(self, _battle, _player_id):
        return np.asarray([no_op], dtype=np.int64)

    planner._sample_legal_actions = MethodType(only_no_op, planner)
    actions = planner.select_actions(battle)
    return (
        actions,
        copy.deepcopy(planner.rng.bit_generator.state),
        planner.simulator_backend_metrics(),
        battle_snapshot(battle),
        battle.rng.getstate(),
        input_snapshot,
        input_rng,
    )


def test_oracle_tensor_fork_search_is_exactly_scalar_equivalent() -> None:
    reference = _no_op_oracle_trace("python")
    candidate = _no_op_oracle_trace("pytorch")

    assert candidate[0] == reference[0]
    assert candidate[1] == reference[1]
    assert candidate[3:] == reference[3:]
    assert candidate[2]["tensor_forks"] == 4
    assert candidate[2]["tensor_ticks"] == 16
    assert candidate[2]["python_ticks"] == 0
    assert candidate[2]["unsupported_fallbacks"] == 0


def test_oracle_tensor_search_falls_back_exactly_for_unsupported_branches() -> None:
    battle = BattleState(rng=random.Random(2301))
    input_snapshot = copy.deepcopy(battle_snapshot(battle))
    common = {
        "decision_interval_ticks": 2,
        "plan_depth": 2,
        "num_simulations": 4,
        "rollout_action_samples": 16,
        "seed": 901,
    }
    reference = FixedDepthThompsonOracle(**common, simulation_backend="python")
    candidate = FixedDepthThompsonOracle(**common, simulation_backend="pytorch")

    reference_actions = reference.select_actions(battle)
    candidate_actions = candidate.select_actions(battle)

    assert candidate_actions == reference_actions == {0: 51, 1: 52}
    assert candidate.rng.bit_generator.state == reference.rng.bit_generator.state
    assert battle_snapshot(battle) == input_snapshot
    assert candidate.simulator_backend_metrics() == {
        "tensor_ticks": 4.0,
        "python_ticks": 12.0,
        "shadow_checks": 0.0,
        "shadow_mismatches": 0.0,
        "unsupported_fallbacks": 6.0,
        "tensor_forks": 4.0,
    }
