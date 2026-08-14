from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.interaction_matrix import enabled_troop_cards
from clasher.rust_core import ResidentRustBattle, rust_core_available

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _empty_battle() -> BattleState:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    return battle


def _spawn(
    battle: BattleState,
    card_name: str,
    player_id: int = 0,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(
        Position(8.0 + player_id, 14.0),
        player_id,
        stats,
    )
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


def _reasons(resident: ResidentRustBattle) -> set[str]:
    return {
        str(reason)
        for row in resident.direct_combat_capability()
        for reason in row["reasons"]
    }


def test_direct_combat_preflight_accepts_plain_resolved_melee_state() -> None:
    battle = _empty_battle()
    _spawn(battle, "Knight", 0)
    _spawn(battle, "Knight", 1)
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_direct_combat_phase
    assert _reasons(resident) == set()


@pytest.mark.parametrize(
    ("card_name", "expected_reason"),
    [
        ("BabyDragon", "projectile_payload"),
        ("Golem", "executable_mechanics"),
        ("BattleRam", "charge_payload"),
        ("Wallbreakers", "kamikaze_payload"),
    ],
)
def test_direct_combat_preflight_rejects_unsupported_resolved_payloads(
    card_name: str,
    expected_reason: str,
) -> None:
    battle = _empty_battle()
    _spawn(battle, card_name)
    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.supports_direct_combat_phase
    assert expected_reason in _reasons(resident)


@pytest.mark.parametrize(
    ("field", "value", "expected_reason"),
    [
        ("_river_jump_active", True, "active_river_jump"),
        ("_special_move_active", True, "active_special_move"),
        ("_special_move_consumed_tick", True, "consumed_special_move_tick"),
        ("forced_movement_active", True, "interrupting_forced_movement"),
    ],
)
def test_direct_combat_preflight_rejects_active_special_state(
    field: str,
    value: object,
    expected_reason: str,
) -> None:
    battle = _empty_battle()
    troop = _spawn(battle, "Knight")
    setattr(troop, field, value)
    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.supports_direct_combat_phase
    assert expected_reason in _reasons(resident)


@pytest.mark.parametrize("card_name", enabled_troop_cards())
def test_direct_combat_preflight_is_deterministic_for_every_enabled_troop(
    card_name: str,
) -> None:
    battle = _empty_battle()
    _spawn(battle, card_name)

    first = ResidentRustBattle.from_battle(battle)
    second = ResidentRustBattle.from_battle(battle)

    assert first.supports_direct_combat_phase == second.supports_direct_combat_phase
    assert first.direct_combat_capability() == second.direct_combat_capability()
