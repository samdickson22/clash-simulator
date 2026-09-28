"""Avoidance must inspect the route selected for the new combat target."""

import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.kinematics import normalized_vector_logic_units

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/native_route_prepare_15_535_86.json")
    .read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
def test_static_archer_removes_the_new_route_node_before_goblin_travel(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    for name, owner, x, y, stagger in (
        ("Goblins", 1, *REFERENCE["xy"], 0),
        ("Archers", 0, 14000, 14500, 0),
        ("Archers", 0, 15000, 14500, 0.2),
    ):
        battle._spawn_unit_at_position(
            Position(x / 1000, y / 1000), owner,
            battle.card_loader.get_card(name),
            deploy_delay_override=0 if name == "Goblins" else 1,
            deploy_delay_offset=stagger, snap_to_valid=False,
        )
    goblin, target, _ = battle.entities.values()
    goblin.target_id = target.id
    goblin._movement_target_id = target.id
    goblin._native_natural_movement_active = True
    goblin._facing_x_units, goblin._facing_y_units = REFERENCE["facing"]
    goblin._native_avoidance = REFERENCE["avoidance"]
    if fast_path:
        battle._refresh_fast_path_caches()

    goblin.update_movement_component(battle.dt, battle)

    assert list(normalized_vector_logic_units(
        *goblin.native_facing_units(), 256
    )) == REFERENCE["expected_facing"]
    assert goblin._native_ground_route_cells == REFERENCE["expected_remaining_route"]
