"""A Cannon killed in combat remains in the current movement overlay."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.pathfinding import native_building_cost_cells, native_route_goal_cell


@pytest.mark.parametrize("fast_path", [False, True])
def test_goblin_keeps_route_when_cannon_dies_in_combat(fast_path):
    # Opened native seed1300202 wait, tick3561->3562. Keep the first two
    # observed route nodes; other troops do not touch this Goblin this frame.
    battle = BattleState(fast_path=fast_path)
    spawned = []
    for name, owner, xy in (
        ("Knight", 0, (3.278, 17.231)),
        ("Cannon", 1, (3.5, 18.5)),
        ("Goblins", 1, (.848, 18.6)),
    ):
        if name == "Cannon":
            battle._spawn_entity(
                Building, Position(*xy), owner, battle.card_loader.get_card(name),
            )
        else:
            battle._spawn_unit_at_position(
                Position(*xy), owner, battle.card_loader.get_card(name),
                deploy_delay_override=0, snap_to_valid=False,
            )
        spawned.append(battle.entities[max(battle.entities)])
    knight, cannon, goblin = spawned
    cannon.hitpoints = 135
    knight.target_id = cannon.id
    knight.attack_cooldown = 0
    goblin.target_id = knight.id
    goblin._native_avoidance = -20
    goblin._facing_x_units, goblin._facing_y_units = 509, 202
    goal = native_route_goal_cell(goblin, knight)
    goblin._native_ground_route_cells = [(3, 36), (4, 35), goal]
    goblin._native_ground_route_direction = (238, -92)
    goblin._ground_path_cache_key = (
        goal, native_building_cost_cells(battle), goblin._native_lane_id, False,
    )
    goblin._ground_path_cache_backwards = False

    battle.step()

    assert cannon.id not in battle.entities
    assert (round(goblin.position.x * 1000), round(goblin.position.y * 1000)) == (961, 18560)
    assert battle._native_building_cost_snapshot is None
    assert (5, 35) not in native_building_cost_cells(battle)
