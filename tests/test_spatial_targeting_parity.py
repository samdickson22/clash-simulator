import copy

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop


def _spawn_troop(battle: BattleState, player_id: int, card_name: str, x: float, y: float) -> None:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    battle._spawn_troop(Position(x, y), player_id, stats)


def test_fast_path_target_selection_matches_legacy():
    battle = BattleState()
    _spawn_troop(battle, 0, "Knight", 8.5, 10.5)
    _spawn_troop(battle, 0, "Archers", 9.5, 9.5)
    _spawn_troop(battle, 1, "Knight", 8.5, 20.5)
    _spawn_troop(battle, 1, "Archers", 9.5, 21.5)
    _spawn_troop(battle, 1, "Cannon", 8.5, 18.5)

    fast_battle = copy.deepcopy(battle)
    fast_battle.fast_path = True
    fast_battle._refresh_fast_path_caches()

    for entity_id, entity in battle.entities.items():
        if not isinstance(entity, Troop) or not entity.is_alive:
            continue
        fast_entity = fast_battle.entities[entity_id]
        legacy_target = entity.get_nearest_target(battle.entities)
        fast_target = fast_entity.get_nearest_target(fast_battle.entities)
        legacy_target_id = None if legacy_target is None else legacy_target.id
        fast_target_id = None if fast_target is None else fast_target.id
        assert legacy_target_id == fast_target_id
