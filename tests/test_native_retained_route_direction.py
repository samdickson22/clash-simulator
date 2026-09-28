import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop


@pytest.mark.parametrize("fast_path", [False, True])
def test_retained_node_direction_matches_native_crowded_path(fast_path):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_retained_route_direction_15_535_86.json").read_text()
    )
    expected = {row["elapsed_tick"]: row["positions"] for row in reference["frames"]}
    battle = BattleState(fast_path=fast_path)
    # Native commands1320/1380/1440, translated to this isolated timeline.
    commands = {0: "IceGolem", 60: "Skeletons", 120: "Log"}
    while battle.tick < max(expected):
        if battle.tick in commands:
            card = commands[battle.tick]
            battle.players[0].hand = [card]
            assert battle.deploy_card(0, card, Position(3.5, 13.5))
        battle.step()
        if battle.tick in expected:
            units = [e for e in battle.entities.values() if isinstance(e, Troop)]
            assert len(units) == 4
            positions = [[round(e.position.x * 1000), round(e.position.y * 1000)] for e in units]
            assert positions == expected[battle.tick], battle.tick


@pytest.mark.parametrize("walking", [False, True])
def test_unrelated_building_removal_heading_depends_on_active_movement(walking):
    from clasher.entities import Building
    from clasher.pathfinding import ground_path_waypoint

    battle = BattleState()
    target = next(e for e in battle.entities.values()
                  if e.player_id == 1 and e.position == Position(14.5, 25.5))
    building = battle._spawn_entity(
        Building, Position(3.5, 8.5), 0, battle.card_loader.get_card("Cannon"),
    )
    before = set(battle.entities)
    battle._spawn_unit_at_position(
        Position(14.1, 12.2), 0, battle.card_loader.get_card("IceGolem"),
        deploy_delay_override=0, snap_to_valid=False,
    )
    mover = battle.entities[(set(battle.entities) - before).pop()]
    ground_path_waypoint(battle, mover, target.position, target_entity=target)
    route = list(mover._native_ground_route_cells)
    direction = mover._native_ground_route_direction
    mover.position = Position(14.2, 12.3)
    mover._native_natural_movement_active = walking
    building.take_damage(building.hitpoints)
    ground_path_waypoint(battle, mover, target.position, target_entity=target)
    assert mover._native_ground_route_cells == route
    assert (mover._native_ground_route_direction == direction) is not walking
