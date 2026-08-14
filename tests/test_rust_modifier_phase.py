from __future__ import annotations

from typing import cast

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import PeriodicDamageEffect, Troop
from clasher.interaction_matrix import (
    EventFamily,
    InteractionCase,
    enabled_troop_cards,
)
from clasher.interaction_scenarios import build_interaction_battle
from clasher.rust_core import (
    ResidentRustBattle,
    compare_modifier_phase,
    rust_core_available,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)
ENABLED_TROOPS = enabled_troop_cards()


def _spawn(battle: BattleState, card_name: str, player_id: int) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(Position(8.0 + player_id, 14.0), player_id, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


def _advance_python_modifier_phase(battle: BattleState) -> None:
    for entity in list(battle.entities.values()):
        if entity.entity_kind in {0, 1}:
            entity.update_buff_component(battle.dt)


def test_modifier_phase_matches_overlapping_status_sources() -> None:
    battle = BattleState()
    troop = _spawn(battle, "Knight", 0)
    troop.apply_stun(0.10, source_kind="test")
    troop.apply_slow(
        0.10,
        0.7,
        attack_speed_multiplier=0.8,
        spawn_speed_multiplier=0.9,
    )
    troop.apply_slow(
        0.20,
        0.6,
        attack_speed_multiplier=0.9,
        spawn_speed_multiplier=0.7,
    )
    troop.apply_haste(0.10, 1.2, 1.3, 1.4)
    troop.apply_haste(0.20, 1.4, 1.1, 1.2)
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_modifier_phase
    compare_modifier_phase(battle, resident)
    for _ in range(5):
        resident.advance_modifier_phase()
        _advance_python_modifier_phase(battle)
        compare_modifier_phase(battle, resident)


def test_modifier_phase_matches_legacy_haste_scalar_expiry() -> None:
    battle = BattleState()
    troop = _spawn(battle, "Knight", 0)
    troop.haste_timer = battle.dt
    troop.movement_speed_buff_multiplier = 1.3
    troop.attack_speed_buff_multiplier = 1.3
    troop.spawn_speed_buff_multiplier = 1.3
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_modifier_phase()
    _advance_python_modifier_phase(battle)

    compare_modifier_phase(battle, resident)


def test_modifier_phase_rejects_periodic_damage_fail_closed() -> None:
    battle = BattleState()
    troop = _spawn(battle, "Knight", 0)
    troop._periodic_damage_effects[91] = PeriodicDamageEffect(
        source_id=91,
        source_kind="test",
        remaining=1.0,
        hit_interval=0.5,
        time_to_next_hit=0.5,
        damage=1.0,
    )
    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.supports_modifier_phase
    with pytest.raises(RuntimeError, match="periodic damage"):
        resident.advance_modifier_phase()


def test_modifier_phase_preserves_signed_zero_bits() -> None:
    battle = BattleState()
    troop = _spawn(battle, "Knight", 0)
    troop.stun_timer = -0.0
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_modifier_phase()
    _advance_python_modifier_phase(battle)

    compare_modifier_phase(battle, resident)


@pytest.mark.parametrize("card_name", ENABLED_TROOPS)
@pytest.mark.parametrize("event_family", ["stun", "slow", "rage"])
def test_modifier_phase_covers_every_enabled_troop_without_name_branches(
    card_name: str,
    event_family: str,
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
        event_family=cast(EventFamily, event_family),
    )
    battle = build_interaction_battle(case, seed=7721).battle
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_modifier_phase
    resident.advance_modifier_phase()
    _advance_python_modifier_phase(battle)

    compare_modifier_phase(battle, resident)
