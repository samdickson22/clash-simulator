from dataclasses import replace

import pytest

from clasher.interaction_matrix import (
    EVENT_FAMILIES,
    enabled_troop_cards,
    iter_one_v_one_cases,
    iter_two_v_two_cases,
)
from clasher.interaction_scenarios import (
    build_interaction_battle,
    run_python_interaction_case,
)


@pytest.mark.parametrize("fast_path", [False, True])
def test_executable_one_v_one_case_is_exact_per_tick(fast_path):
    cards = enabled_troop_cards()
    case = next(
        case
        for case in iter_one_v_one_cases(cards)
        if case.fast_path is fast_path and case.mirrored
    )

    setup, result = run_python_interaction_case(case, ticks=3)

    assert len(setup.spawned_entity_ids) >= 2
    assert setup.event_applied
    assert result.expected_sha256 == result.actual_sha256


@pytest.mark.parametrize("event_family", EVENT_FAMILIES)
def test_every_systematic_event_family_builds_a_replayable_case(event_family):
    cards = enabled_troop_cards()
    base = replace(next(iter_two_v_two_cases(cards)), geometry="left_lane")
    case = replace(base, event_family=event_family)

    setup, result = run_python_interaction_case(case, ticks=2)

    assert setup.case.event_family == event_family
    assert result.expected_sha256 == result.actual_sha256


def test_spawn_order_and_lane_mirror_change_state_without_rng_drift():
    cards = enabled_troop_cards()
    base = replace(next(iter_two_v_two_cases(cards)), geometry="left_lane")
    alternate = replace(
        base,
        mirrored=not base.mirrored,
        team_0_spawn_reversed=not base.team_0_spawn_reversed,
        team_1_spawn_reversed=not base.team_1_spawn_reversed,
    )

    first = build_interaction_battle(base, seed=991)
    second = build_interaction_battle(alternate, seed=991)

    assert first.battle.rng.getstate() == second.battle.rng.getstate()
    assert [
        first.battle.entities[entity_id].position
        for entity_id in first.spawned_entity_ids
    ] != [
        second.battle.entities[entity_id].position
        for entity_id in second.spawned_entity_ids
    ]
