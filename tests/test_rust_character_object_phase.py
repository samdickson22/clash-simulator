from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.cards.electro_spirit import ElectroSpiritChain
from clasher.cards.ice_spirit import IceSpiritFreeze
from clasher.cards.tesla import HideWhenIdle
from clasher.cards.wallbreakers import WallBreakersDemolition
from clasher.entities import Building, Troop
from clasher.interaction_matrix import enabled_troop_cards
from clasher.mechanics.shared.damage_ramp import DamageRamp
from clasher.rust_core import (
    ResidentRustBattle,
    compare_character_object_phase,
    death_opcode_state_rows,
    rust_core_available,
    shield_state_rows,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _spawn(battle: BattleState, card_name: str = "Knight") -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(Position(8.0, 14.0), 0, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


def _advance_python_character_object_phase(battle: BattleState) -> None:
    for entity in list(battle.entities.values()):
        if isinstance(entity, (Troop, Building)):
            entity.tick_character_object_phase(battle.dt)


def test_character_object_phase_matches_deployment_zero_crossing() -> None:
    battle = BattleState()
    troop = _spawn(battle)
    assert not troop.mechanics
    troop.deploy_delay_remaining = battle.dt
    troop.placement_pending = True
    troop._spawn_hook_pending = True
    troop._spawn_hook_fired = False
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_character_object_phase
    resident.advance_character_object_phase()
    _advance_python_character_object_phase(battle)

    compare_character_object_phase(battle, resident)


def test_character_object_phase_matches_target_immunity_boundary() -> None:
    battle = BattleState()
    troop = _spawn(battle)
    troop.deploy_delay_remaining = 0.0
    troop._death_spawn_target_immunity_elapsed_ms = 200
    resident = ResidentRustBattle.from_battle(battle)

    for _ in range(2):
        resident.advance_character_object_phase()
        _advance_python_character_object_phase(battle)
        compare_character_object_phase(battle, resident)

    assert troop._death_spawn_target_immunity_elapsed_ms == -1


def test_character_object_phase_rejects_executable_mechanics() -> None:
    battle = BattleState()
    troop = _spawn(battle, "Balloon")
    assert troop.mechanics
    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.supports_character_object_phase
    with pytest.raises(RuntimeError, match="executable mechanics"):
        resident.advance_character_object_phase()


@pytest.mark.parametrize("card_name", enabled_troop_cards())
def test_character_object_phase_is_card_general_and_fail_closed(
    card_name: str,
) -> None:
    battle = BattleState()
    troop = _spawn(battle, card_name)
    resident = ResidentRustBattle.from_battle(battle)

    compiled_count = sum(
        row["id"] == troop.id
        for row in (
            *death_opcode_state_rows(battle),
            *shield_state_rows(battle),
        )
    )
    compiled_count += sum(
        type(mechanic)
        in (
            ElectroSpiritChain,
            IceSpiritFreeze,
            DamageRamp,
            HideWhenIdle,
            WallBreakersDemolition,
        )
        for mechanic in troop.mechanics
    )
    if compiled_count != len(troop.mechanics):
        assert not resident.supports_character_object_phase
        return
    assert resident.supports_character_object_phase
    resident.advance_character_object_phase()
    _advance_python_character_object_phase(battle)
    compare_character_object_phase(battle, resident)
