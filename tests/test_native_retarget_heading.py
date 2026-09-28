"""Conditional regression for the opened native tick3783 steering boundary."""

import pytest

from clasher.arena import Position
from clasher.attack_clock import OrdinaryAttackClock
from clasher.battle import BattleState
from clasher.ordinary_combat_clock import publish


@pytest.mark.parametrize("fast_path", [False, True])
def test_out_of_range_retarget_preserves_heading_before_avoidance(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()

    def spawn(name, owner, x, y):
        before = set(battle.entities)
        battle._spawn_unit_at_position(
            Position(x / 1000, y / 1000), owner, battle.card_loader.get_card(name),
            deploy_delay_override=0, snap_to_valid=False,
        )
        return battle.entities[(set(battle.entities) - before).pop()]

    front = spawn("Skeletons", 0, 3126, 18994)
    rear = spawn("Skeletons", 0, 3239, 17999)
    original = spawn("Archers", 1, 4012, 19504)
    replacement = spawn("Archers", 1, 2999, 19499)
    front.target_id = original.id
    front._attack_windup_active = True
    rear.target_id = original.id
    rear._last_combat_target_id = original.id
    rear._attack_windup_active = True
    rear._facing_x_units, rear._facing_y_units = 789, 1363
    rear._ordinary_clock = OrdinaryAttackClock(
        1100, 600, hit_timeline_ms=700, load_remaining_ms=550,
    )
    publish(rear, rear._ordinary_clock)
    if fast_path:
        battle._refresh_fast_path_caches()

    rear.update_combat_component(battle.dt, battle)

    assert rear.target_id == replacement.id
    assert rear._ordinary_clock.hit_timeline_ms == 0
    assert rear._ordinary_clock.load_remaining_ms == 500
    assert rear.native_facing_units() == (789, 1363)
    # Native processes the lower-ID front body's movement before this scan.
    front.position = Position(3.162, 18.849)
    rear._update_native_avoidance(battle)
    assert rear._native_avoidance == 190
