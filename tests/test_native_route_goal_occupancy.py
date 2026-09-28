"""Ground route goals prefer available cells over a building footprint."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.pathfinding import native_route_goal_cell


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("blocked,expected", [(False, (26, 20)), (True, (26, 18))])
def test_goblin_route_goal_respects_cannon_footprint(fast_path, blocked, expected):
    # Native reversed seed1305003 tick2981 route ends at26,18. The Cannon
    # occupies the geometrically closer26,20. Its removal is a paired control.
    battle = BattleState(fast_path=fast_path)
    for name, owner, xy in (
        ("Goblins", 0, (11.853, 11.116)),
        ("Giant", 1, (13.775, 9.435)),
    ):
        battle._spawn_unit_at_position(
            Position(*xy), owner, battle.card_loader.get_card(name),
            deploy_delay_override=0, snap_to_valid=False,
        )
    goblin, giant = list(battle.entities.values())[-2:]
    if blocked:
        battle._spawn_entity(Building, Position(13.5, 10.5), 0, battle.card_loader.get_card("Cannon"))

    assert native_route_goal_cell(goblin, giant) == expected
