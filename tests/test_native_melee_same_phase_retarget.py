"""Conditional native transition at ticks 4039–4040 of development seed 1293401."""

import pytest

from clasher.arena import Position
from clasher.attack_clock import OrdinaryAttackClock
from clasher.battle import BattleState
from clasher.ordinary_combat_clock import publish


@pytest.mark.parametrize("fast_path", [False, True])
def test_melee_observer_moves_after_earlier_ally_kills_its_target(fast_path):
    # Geometry and clocks come from native-driven-skeleton-finish-native-1293401.
    # This isolates the combat transition, not the full native route state.
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()

    def spawn(name, owner, x, y):
        before = set(battle.entities)
        battle._spawn_unit_at_position(
            Position(x / 1000, y / 1000), owner, battle.card_loader.get_card(name),
            deploy_delay_override=0, snap_to_valid=False,
        )
        return battle.entities[(set(battle.entities) - before).pop()]

    giant = spawn("Giant", 0, 3768, 22049)
    prince = spawn("Prince", 0, 3615, 17247)
    killer = spawn("Skeletons", 1, 4803, 22868)
    observer = spawn("Skeletons", 1, 5258, 20013)
    giant.hitpoints = 68
    for skeleton, timeline in ((killer, 6550), (observer, 1000)):
        skeleton.target_id = giant.id
        skeleton._last_combat_target_id = giant.id
        skeleton._attack_windup_active = True
        skeleton._ordinary_clock = OrdinaryAttackClock(
            1100, 600, hit_timeline_ms=timeline, load_remaining_ms=0,
        )
        publish(skeleton, skeleton._ordinary_clock)
    if fast_path:
        battle._refresh_fast_path_caches()
    start = (observer.position.x, observer.position.y)

    battle.step()

    assert not giant.is_alive
    assert observer.target_id == prince.id
    assert observer._ordinary_clock.hit_timeline_ms == 0
    assert observer._ordinary_clock.load_remaining_ms == 0
    assert observer._attack_finish_elapsed_ms == 0
    assert (observer.position.x, observer.position.y) != start
