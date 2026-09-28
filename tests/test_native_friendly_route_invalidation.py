"""The pinned routing flag limits building-change invalidation to allies."""

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.pathfinding import ground_path_waypoint


@pytest.mark.parametrize('building_owner', [0, 1], ids=['enemy', 'friendly'])
def test_building_removal_only_replans_for_its_own_side(building_owner):
    # Native forward-1 wait: Goblin5000065 retains this detour at2633 after
    # enemy Tesla5000059 dies. The friendly variant exercises the flag's
    # owner gate; it is a conditional mechanics control, not a native replay.
    battle = BattleState()
    target = next(e for e in battle.entities.values()
                  if e.player_id == 0 and e.position == Position(14.5, 6.5))
    tesla = battle._spawn_entity(
        Building, Position(14, 13), building_owner, battle.card_loader.get_card('Tesla'),
    )
    before = set(battle.entities)
    battle._spawn_unit_at_position(
        Position(14.145, 14.915), 1, battle.card_loader.get_card('Goblins'),
        deploy_delay_override=0, snap_to_valid=False,
    )
    goblin = battle.entities[(set(battle.entities) - before).pop()]
    goblin._native_lane_id = 2
    ground_path_waypoint(battle, goblin, target.position, target_entity=target)
    retained = list(goblin._native_ground_route_cells)
    assert (29, 26) in retained
    assert (28, 26) not in retained

    tesla.take_damage(tesla.hitpoints)
    ground_path_waypoint(battle, goblin, target.position, target_entity=target)

    if building_owner == goblin.player_id:
        assert (28, 26) in goblin._native_ground_route_cells
    else:
        assert goblin._native_ground_route_cells == retained
        # A changed goal still rebuilds with the complete current obstacle map.
        other_tower = next(e for e in battle.entities.values()
                           if e.player_id == 0 and e.position == Position(3.5, 6.5))
        ground_path_waypoint(battle, goblin, other_tower.position, target_entity=other_tower)
        assert goblin._native_ground_route_cells != retained
