from __future__ import annotations

from itertools import pairwise

import pytest

from clasher.rl.counterfactual_schedule import (
    phase_balanced_query_ticks,
    should_query_phase_balanced_counterfactual,
)


def test_phase_balanced_targets_cover_every_battle_phase() -> None:
    targets = phase_balanced_query_ticks(
        minimum_tick=256,
        max_ticks=6000,
        states_per_game=16,
        decision_interval=8,
        phase_boundaries=(3600,),
    )

    assert len(targets) == 16
    assert targets[0] == 256
    assert targets[-1] == 5632
    assert targets[10] == 3600
    assert all(right > left for left, right in pairwise(targets))
    assert all(target % 8 == 0 for target in targets)
    assert any(target < 1200 for target in targets)
    assert any(2400 <= target < 3600 for target in targets)
    assert any(target >= 3600 for target in targets)


def test_phase_balanced_query_waits_for_target_playability_and_spacing() -> None:
    targets = (256, 640, 1024)
    kwargs = {
        "decision_index": 40,
        "last_query_decision": 20,
        "tick": 640,
        "collected": 1,
        "target_ticks": targets,
        "minimum_decision_spacing": 16,
        "can_play": True,
    }

    assert should_query_phase_balanced_counterfactual(**kwargs)
    assert not should_query_phase_balanced_counterfactual(
        **{**kwargs, "tick": 632}
    )
    assert not should_query_phase_balanced_counterfactual(
        **{**kwargs, "can_play": False}
    )
    assert not should_query_phase_balanced_counterfactual(
        **{**kwargs, "decision_index": 35}
    )
    assert not should_query_phase_balanced_counterfactual(
        **{**kwargs, "collected": len(targets)}
    )


def test_phase_balanced_schedule_rejects_duplicate_target_budget() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        phase_balanced_query_ticks(
            minimum_tick=0,
            max_ticks=16,
            states_per_game=8,
            decision_interval=8,
        )


def test_phase_balanced_schedule_rejects_unaligned_phase_boundary() -> None:
    with pytest.raises(ValueError, match="phase boundary"):
        phase_balanced_query_ticks(
            minimum_tick=256,
            max_ticks=6000,
            states_per_game=16,
            decision_interval=8,
            phase_boundaries=(3601,),
        )
