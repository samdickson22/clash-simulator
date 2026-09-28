"""A later combat component cannot cancel an already selected movement step."""

import pytest

from clasher.arena import Position
from clasher.battle import BattleState


def boundary(fast_path):
    # Opened native seed1300202, tick2739: Goblin5000049 follows Archer5000041.
    # Other bodies are omitted to isolate whether target HP cancels travel.
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    for name, owner, x, y in (
        ("Archers", 0, 13529, 15803),
        ("Goblins", 1, 15393, 16543),
    ):
        battle._spawn_unit_at_position(
            Position(x / 1000, y / 1000), owner,
            battle.card_loader.get_card(name),
            deploy_delay_override=0, snap_to_valid=False,
        )
    target, observer = battle.entities.values()
    observer.target_id = target.id
    observer._last_combat_target_id = target.id
    observer._native_natural_movement_active = True
    observer._facing_x_units, observer._facing_y_units = -1129, -395
    observer._native_avoidance = -170
    if fast_path:
        battle._refresh_fast_path_caches()
    observer.update_combat_component(battle.dt, battle)
    assert observer._movement_target_id == target.id
    return battle, target, observer


@pytest.mark.parametrize("fast_path", [False, True])
def test_target_death_after_combat_preserves_committed_travel(fast_path):
    positions = []
    for depleted in (False, True):
        battle, target, observer = boundary(fast_path)
        start = (observer.position.x, observer.position.y)
        if depleted:
            target.take_damage(target.hitpoints)
        observer.update_movement_component(battle.dt, battle)
        positions.append((observer.position.x, observer.position.y))
        assert positions[-1] != start
    assert positions[0] == positions[1]


@pytest.mark.parametrize("fast_path", [False, True])
def test_removed_target_does_not_leave_a_persistent_movement_goal(fast_path):
    battle, target, observer = boundary(fast_path)
    del battle.entities[target.id]
    start = (observer.position.x, observer.position.y)
    observer.update_movement_component(battle.dt, battle)
    assert (observer.position.x, observer.position.y) == start
    observer.update_combat_component(battle.dt, battle)
    assert observer._movement_target_id is None
