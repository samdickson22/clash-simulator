"""Pending-target removal must not leave an active hit banked while idle."""
import pytest

from clasher.arena import Position
from clasher.attack_clock import OrdinaryAttackClock
from clasher.battle import BattleState
from clasher.entities import Building, Projectile
from clasher.ordinary_combat_clock import publish


@pytest.mark.parametrize('replacement', [False, True])
def test_cannon_preserves_pending_hit_only_for_immediate_replacement(replacement):
    battle = BattleState()
    cannon = battle._spawn_entity(Building, Position(9, 10), 0, battle.card_loader.get_card('Cannon'))
    cannon.deploy_delay_remaining = 0
    cannon._ordinary_clock = OrdinaryAttackClock(1000, 100, hit_timeline_ms=2150)
    publish(cannon, cannon._ordinary_clock)
    cannon._resume_pending_hit = True
    if replacement:
        battle._spawn_unit_at_position(Position(9, 12), 1, battle.card_loader.get_card('Knight'), deploy_delay_override=0, snap_to_valid=False)
    cannon.update_combat_component(battle.dt, battle)
    assert cannon._ordinary_clock.hit_timeline_ms == (2200 if replacement else 0)
    assert cannon._ordinary_clock.load_remaining_ms == 0
    if replacement:
        return
    # Native mix1-forward3071->3072 clears2150 to0. A later target starts
    # from the loaded100ms, needing18frames to reach the1000ms deadline.
    battle._spawn_unit_at_position(Position(9, 12), 1, battle.card_loader.get_card('Knight'), deploy_delay_override=0, snap_to_valid=False)
    shots = []
    for tick in range(1, 20):
        before = set(battle.entities)
        cannon.update_combat_component(battle.dt, battle)
        if any(isinstance(battle.entities[i], Projectile) for i in set(battle.entities)-before):
            shots.append(tick)
    assert shots == [18]
