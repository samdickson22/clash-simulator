from __future__ import annotations

from dataclasses import replace

import pytest

from clasher.interaction_matrix import (
    InteractionCase,
    enabled_troop_cards,
    iter_one_v_one_cases,
    iter_two_v_two_cases,
)
from clasher.interaction_scenarios import build_interaction_battle
from clasher.rust_core import (
    ResidentRustBattle,
    compare_resident_entities,
    rust_core_available,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)
ENABLED_TROOPS = enabled_troop_cards()


def test_initial_resident_entity_roster_is_exact() -> None:
    from clasher.battle import BattleState

    battle = BattleState()
    resident = ResidentRustBattle.from_battle(battle)

    compare_resident_entities(battle, resident)


@pytest.mark.parametrize("card_name", ENABLED_TROOPS)
def test_every_enabled_troop_initializes_exact_resident_state(
    card_name: str,
) -> None:
    case = InteractionCase(
        index=0,
        kind="1v1",
        team_0=(card_name,),
        team_1=(ENABLED_TROOPS[0],),
        fast_path=False,
        mirrored=False,
        geometry="center",
        team_0_spawn_reversed=False,
        team_1_spawn_reversed=False,
        event_family="ordinary",
    )
    battle = build_interaction_battle(case, seed=9920).battle
    resident = ResidentRustBattle.from_battle(battle)

    compare_resident_entities(battle, resident)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("mirrored", [False, True])
def test_one_v_one_roster_preserves_order_types_and_mechanics(
    fast_path: bool,
    mirrored: bool,
) -> None:
    cards = enabled_troop_cards()
    cases = list(iter_one_v_one_cases(cards[:4]))
    case = next(
        candidate
        for candidate in cases
        if candidate.fast_path is fast_path and candidate.mirrored is mirrored
    )
    battle = build_interaction_battle(case, seed=9921).battle
    resident = ResidentRustBattle.from_battle(battle)

    compare_resident_entities(battle, resident)


@pytest.mark.parametrize(
    "event_family",
    ["ordinary", "target_order", "stun", "slow", "rage", "allied_collision"],
)
def test_two_v_two_roster_preserves_systematic_state(event_family: str) -> None:
    cards = enabled_troop_cards()
    base = next(iter_two_v_two_cases(cards[:4]))
    case = replace(base, event_family=event_family)
    battle = build_interaction_battle(case, seed=9922).battle
    resident = ResidentRustBattle.from_battle(battle)

    compare_resident_entities(battle, resident)


def test_resident_entity_drift_reports_first_exact_path() -> None:
    battle = build_interaction_battle(
        next(iter_one_v_one_cases(ENABLED_TROOPS[:2])),
        seed=9923,
    ).battle
    resident = ResidentRustBattle.from_battle(battle)
    first_spawned = next(
        entity for entity in battle.entities.values() if entity.id > 6
    )
    first_spawned.position.x = -0.0

    with pytest.raises(
        AssertionError,
        match=r"position_x.*expected=.*8000000000000000",
    ):
        compare_resident_entities(battle, resident)
