from __future__ import annotations

from collections import deque

import pytest

from clasher.battle import BattleState
from clasher.rl.reward_model import objective_win_prob_p0
from clasher.torch_sim import TorchBattleExecutor, first_divergence
from clasher.torch_sim.diagnostics import battle_snapshot


def _assert_exact_battle_match(expected: BattleState, actual: BattleState) -> None:
    mismatch = first_divergence(
        battle_snapshot(expected),
        battle_snapshot(actual),
    )
    assert mismatch is None, str(mismatch)


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
def test_custom_tick_and_phase_timing_match_reward_state_exactly(backend: str) -> None:
    actual = BattleState(
        dt=0.075,
        double_elixir_start_time=0.075,
        overtime_start_time=0.200,
        triple_elixir_start_time=0.300,
        tiebreaker_time=0.450,
    )
    actual.players[0].elixir = 5.0
    actual.players[0].hand[1] = None
    actual.players[0].cycle_queue = deque(["Musketeer"])
    actual.players[0].next_card_refill_cooldown_ms = 100
    expected = actual.clone()

    assert expected.step_logic_ticks(3) == 3
    executor = TorchBattleExecutor(backend)
    assert executor.step_logic_ticks(actual, 3) == 3

    _assert_exact_battle_match(expected, actual)
    assert actual.double_elixir is True
    assert actual.overtime is True
    assert actual.sudden_death is True
    assert objective_win_prob_p0(actual) == objective_win_prob_p0(expected)


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
def test_tiebreak_uses_oracle_fixed_point_hp_and_draw_reward(backend: str) -> None:
    actual = BattleState(time=299.95, sudden_death=True)
    towers = {
        (entity.player_id, entity._crown_tower_slot): entity
        for entity in actual.entities.values()
        if actual._is_static_tower_entity(entity)
    }
    towers[(0, "left")].hitpoints = 1000.0004
    towers[(1, "left")].hitpoints = 1000.00049
    actual._update_tower_hp()
    expected = actual.clone()

    assert expected.step_logic_ticks(1) == 1
    executor = TorchBattleExecutor(backend)
    assert executor.step_logic_ticks(actual, 1) == 1

    _assert_exact_battle_match(expected, actual)
    assert actual.game_over is True
    assert actual.winner is None
    assert type(actual.game_over) is bool
    assert actual.winner is expected.winner
    assert objective_win_prob_p0(actual) == objective_win_prob_p0(expected) == 0.5


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
def test_batched_rows_keep_independent_terminal_outcomes_and_types(
    backend: str,
) -> None:
    draw = BattleState(time=0.15, sudden_death=True, tiebreaker_time=0.20)
    win = BattleState(time=0.05, overtime_start_time=0.10)
    losing_tower = next(
        entity
        for entity in win.entities.values()
        if entity.player_id == 1 and entity._crown_tower_slot == "left"
    )
    losing_tower.hitpoints = 0
    win._update_tower_hp()

    actual = [draw, win]
    expected = [battle.clone() for battle in actual]
    for battle in expected:
        assert battle.step_logic_ticks(1) == 1

    executor = TorchBattleExecutor(backend)
    assert executor.step_battles(actual, 1) == [1, 1]

    for reference, candidate in zip(expected, actual):
        _assert_exact_battle_match(reference, candidate)
    assert [(battle.game_over, battle.winner) for battle in actual] == [
        (True, None),
        (True, 0),
    ]
    assert [type(battle.game_over) for battle in actual] == [bool, bool]
    assert [type(battle.winner) for battle in actual] == [type(None), int]
    assert [objective_win_prob_p0(battle) for battle in actual] == [0.5, 1.0]


def test_retained_tensor_state_reloads_after_timeline_change() -> None:
    actual = BattleState()
    expected = actual.clone()
    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(actual, 1) == 1
    assert expected.step_logic_ticks(1) == 1

    actual.double_elixir_start_time = actual.time + actual.dt
    expected.double_elixir_start_time = expected.time + expected.dt
    assert executor.step_logic_ticks(actual, 1) == 1
    assert expected.step_logic_ticks(1) == 1

    _assert_exact_battle_match(expected, actual)
    assert actual.double_elixir is True
