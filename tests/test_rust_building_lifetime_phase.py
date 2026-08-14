from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.mechanics.shared.damage_ramp import DamageRamp
from clasher.rust_core import (
    ResidentRustBattle,
    compare_building_lifetime_phase,
    rust_core_available,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)
BUILDING_CARDS = ("BombTower", "Cannon", "InfernoTower", "Tesla", "Tombstone", "Xbow")


def _spawn(card_name: str) -> tuple[BattleState, Building]:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None and stats.lifetime_ms is not None
    building = battle._spawn_entity(
        Building,
        Position(9.0, 12.0),
        0,
        stats,
    )
    return battle, building


def _advance_python_lifetime_phase(battle: BattleState) -> None:
    for entity in list(battle.entities.values()):
        if isinstance(entity, Building):
            entity.update_hitpoint_component(battle.dt)


@pytest.mark.parametrize("card_name", BUILDING_CARDS)
def test_building_lifetime_capability_is_structural(card_name: str) -> None:
    battle, building = _spawn(card_name)
    resident = ResidentRustBattle.from_battle(battle)

    mechanics_supported = not building.mechanics or all(
        type(mechanic) is DamageRamp for mechanic in building.mechanics
    )
    assert resident.supports_building_lifetime_phase is mechanics_supported


@pytest.mark.parametrize("card_name", ["Cannon", "Xbow"])
def test_building_lifetime_matches_fixed_point_decay(card_name: str) -> None:
    battle, building = _spawn(card_name)
    assert not building.mechanics
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_building_lifetime_phase
    for _ in range(17):
        resident.advance_building_lifetime_phase()
        _advance_python_lifetime_phase(battle)
        compare_building_lifetime_phase(battle, resident)


def test_building_lifetime_matches_lethal_zero_crossing() -> None:
    battle, building = _spawn("Cannon")
    assert not building.mechanics
    building.hitpoints = 1.0
    building.lifetime_decay_work = 99
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_building_lifetime_phase()
    _advance_python_lifetime_phase(battle)

    compare_building_lifetime_phase(battle, resident)
    assert not building.is_alive
    assert building.hitpoints == 0.0


def test_building_lifetime_rejection_does_not_mutate_state() -> None:
    battle, building = _spawn("BombTower")
    assert building.mechanics
    resident = ResidentRustBattle.from_battle(battle)
    state_before = resident.building_lifetime_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_building_lifetime_phase
    with pytest.raises(RuntimeError, match="death mechanics"):
        resident.advance_building_lifetime_phase()

    assert resident.building_lifetime_state_bytes() == state_before
    assert resident.rng_state_bytes() == rng_before
