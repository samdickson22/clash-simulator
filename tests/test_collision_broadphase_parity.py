import copy

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop


def _spawn_many(battle: BattleState, player_id: int, card_name: str, start_x: float, start_y: float) -> None:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    for i in range(6):
        battle._spawn_troop(Position(start_x + (i % 3) * 0.2, start_y + (i // 3) * 0.2), player_id, stats)


def _alive_troop_positions(battle: BattleState) -> dict[int, tuple[float, float]]:
    out = {}
    for entity in battle.entities.values():
        if isinstance(entity, Troop) and entity.is_alive:
            out[entity.id] = (entity.position.x, entity.position.y)
    return out


def test_fast_path_collision_broadphase_keeps_match_state_close():
    battle = BattleState()
    _spawn_many(battle, 0, "Skeletons", 8.2, 11.0)
    _spawn_many(battle, 1, "Skeletons", 8.2, 21.0)

    fast_battle = copy.deepcopy(battle)
    fast_battle.fast_path = True
    fast_battle._refresh_fast_path_caches()

    for _ in range(25):
        battle.step()
        fast_battle.step()

    assert battle.players[0].left_tower_hp == fast_battle.players[0].left_tower_hp
    assert battle.players[1].left_tower_hp == fast_battle.players[1].left_tower_hp
    legacy_pos = _alive_troop_positions(battle)
    fast_pos = _alive_troop_positions(fast_battle)
    assert set(legacy_pos.keys()) == set(fast_pos.keys())
    for entity_id, (lx, ly) in legacy_pos.items():
        fx, fy = fast_pos[entity_id]
        assert abs(lx - fx) < 2.0
        assert abs(ly - fy) < 2.0
