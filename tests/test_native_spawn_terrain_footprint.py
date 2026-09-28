"""Native ground summons test the terrain across their anchor tile."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.placement import ground_spawn_tile_clear


@pytest.mark.parametrize('x,clear', [(2.5, False), (3.5, True), (4.5, False), (13.5, False), (14.5, True), (15.5, False)])
@pytest.mark.parametrize('y', [15.5, 16.5])
def test_bridge_spawn_footprint_requires_all_four_half_cells(x, clear, y):
    assert ground_spawn_tile_clear(Position(x, y)) is clear


@pytest.mark.parametrize('fast_path', [False, True])
def test_dark_prince_relocates_away_from_partial_bridge_tile(fast_path):
    # Opened mix1-forward3300 command: native DarkPrince5000086 is born at
    # (1499,17499). Cannon blocks the requested tile; (2.5,16.5) has water
    # under half its footprint, so the equally near left candidate wins.
    battle = BattleState(fast_path=fast_path)
    tower = next(e for e in battle.entities.values()
                 if e.player_id == 0 and getattr(e, '_crown_tower_slot', None) == 'left')
    tower.take_damage(tower.hitpoints)
    battle.step()
    battle._spawn_entity(Building, Position(3.5,18.5), 1,
                         battle.card_loader.get_card('Cannon'))
    requested = Position(2.5,17.5)
    assert battle.arena.can_deploy_at(Position(2.5,16.5), 1, battle)
    resolved = battle.resolve_ground_troop_anchor(
        requested, 1, battle.card_loader.get_card('DarkPrince'))
    assert (resolved.x, resolved.y) == (1.5,17.5)
