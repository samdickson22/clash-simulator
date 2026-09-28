"""Delayed deployments cannot extend the playable action horizon."""

import pytest

from compare_reacting_public_branches import decision_schedule


@pytest.mark.parametrize("delay", [0, 1, 30])
def test_final_playable_root_never_schedules_a_tiebreak_action(delay):
    assert decision_schedule(6000, delay) == [6000]


def test_delayed_play_on_last_playable_tick_is_retained():
    assert decision_schedule(5999, 1) == [5999, 6000]


def test_delayed_play_preserves_regular_response_cadence():
    ticks = decision_schedule(90, 1)
    assert ticks[:4] == [90, 91, 120, 150]
    assert ticks[-1] == 6000
    assert len(ticks) == len(set(ticks))
