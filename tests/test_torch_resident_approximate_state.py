from __future__ import annotations

from collections.abc import Sequence

from clasher.battle import BattleState
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.diagnostics import first_approximate_state_divergence
from clasher.torch_sim.resident_differential import (
    ResidentEpisodeDifferential,
    ResidentValidationProfile,
    _coverage_episode_tick_budget,
    _coverage_fixture,
)


def test_policy_fidelity_keeps_material_fields_exact_and_bounds_position() -> None:
    expected = {
        "entities": (
            {
                "card": "Goblin_Stab",
                "position_units": (14_320, 13_473),
                "hitpoints": 202,
                "attack_cooldown": 0.55,
            },
        )
    }
    acceptable = {
        "entities": (
            {
                "card": "Goblin_Stab",
                "position_units": (14_070, 13_723),
                "hitpoints": 202.0,
                "attack_cooldown": 0.60,
            },
        )
    }
    assert first_approximate_state_divergence(expected, acceptable) is None

    wrong_hp = {"entities": ({**acceptable["entities"][0], "hitpoints": 201},)}
    mismatch = first_approximate_state_divergence(expected, wrong_hp)
    assert mismatch is not None
    assert mismatch.path == "battle.entities[0].hitpoints"

    too_far = {
        "entities": (
            {
                **acceptable["entities"][0],
                "position_units": (14_069, 13_723),
                "hitpoints": 202,
            },
        )
    }
    mismatch = first_approximate_state_divergence(expected, too_far)
    assert mismatch is not None
    assert mismatch.path == "battle.entities[0].position_units[0]"


def test_goblin_gang_is_policy_equivalent_through_full_deployment_window() -> None:
    episode_end = 1.8
    battle = _coverage_fixture(
        "GoblinGang",
        510_000,
        episode_end_time=episode_end,
    )

    def actions(
        tick: int, _battles: Sequence[BattleState]
    ) -> tuple[tuple[int, int], ...]:
        action = 12 * 18 + 14 if tick == 0 else NO_OP_ACTION
        return ((action, NO_OP_ACTION),)

    report = ResidentEpisodeDifferential(
        max_entities=64,
        max_objects=64,
        event_capacity=512,
        validation_profile=ResidentValidationProfile.APPROXIMATE_ORACLE_STATE,
    ).run(
        [battle],
        actions,
        max_ticks=_coverage_episode_tick_budget(episode_end, battle.dt),
        stop_on_first_divergence=False,
    )

    assert report.parity_rows == (0,)
    assert report.interaction_rows == (0,)
    assert report.fallback_only_rows == ()
    assert report.divergences == ()
