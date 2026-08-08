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


def test_fast_target_refresh_reuses_arrays_and_updates_dynamic_values():
    battle = BattleState(fast_path=True)
    _spawn_troop(battle, 0, "Knight", 8.5, 10.5)
    battle._refresh_fast_path_caches()
    troop = battle.entities[max(battle.entities)]
    index = battle._target_index_by_id[troop.id]
    pos_x = battle._target_pos_x
    pos_y = battle._target_pos_y
    is_air = battle._target_is_air
    stealth = battle._target_stealth_until
    distance_discount = battle._target_distance_discount_sq

    troop.position.x = 9.25
    troop.position.y = 11.75
    troop._river_jump_active = True
    troop._stealth_until = 1234
    troop._native_target_distance_discount_sq_units = 250_000
    battle.sync_fast_target_static_entity(troop)
    battle._refresh_fast_path_caches()

    assert battle._target_pos_x is pos_x
    assert battle._target_pos_y is pos_y
    assert battle._target_is_air is is_air
    assert battle._target_stealth_until is stealth
    assert battle._target_distance_discount_sq is distance_discount
    assert battle._target_pos_x[index] == 9.25
    assert battle._target_pos_y[index] == 11.75
    assert battle._target_is_air[index]
    assert battle._target_stealth_until[index] == 1234
    assert battle._target_distance_discount_sq[index] == 0.25


def test_fast_target_refresh_rebuilds_for_same_size_membership_change():
    battle = BattleState(fast_path=True)
    _spawn_troop(battle, 0, "Knight", 8.5, 10.5)
    battle._refresh_fast_path_caches()
    removed = battle.entities.pop(max(battle.entities))
    old_pos_x = battle._target_pos_x

    _spawn_troop(battle, 1, "Knight", 9.5, 20.5)
    replacement = battle.entities[max(battle.entities)]
    assert len(battle.entities) == battle._target_cache_entity_count
    battle._refresh_fast_path_caches()

    assert battle._target_pos_x is not old_pos_x
    assert removed.id not in battle._target_index_by_id
    assert replacement.id in battle._target_index_by_id
