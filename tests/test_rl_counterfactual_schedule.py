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

    assert targets == (
        256,
        608,
        968,
        1328,
        1688,
        2048,
        2400,
        2760,
        3120,
        3480,
        3600,
        4192,
        4552,
        4912,
        5272,
        5632,
    )
    assert all(right > left for left, right in pairwise(targets))
    assert all(target % 8 == 0 for target in targets)


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
    assert not should_query_phase_balanced_counterfactual(**{**kwargs, "tick": 632})
    assert not should_query_phase_balanced_counterfactual(
        **{**kwargs, "can_play": False}
    )
    assert not should_query_phase_balanced_counterfactual(
        **{**kwargs, "decision_index": 35}
    )
    assert not should_query_phase_balanced_counterfactual(
        **{**kwargs, "collected": len(targets)}
    )


def test_phase_balanced_schedule_rejects_invalid_targets() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        phase_balanced_query_ticks(
            minimum_tick=0,
            max_ticks=16,
            states_per_game=8,
            decision_interval=8,
        )
    with pytest.raises(ValueError, match="phase boundary"):
        phase_balanced_query_ticks(
            minimum_tick=256,
            max_ticks=6000,
            states_per_game=16,
            decision_interval=8,
            phase_boundaries=(3601,),
        )
