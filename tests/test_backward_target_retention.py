"""A previous backward route does not preserve a stationary ranged lock."""
import pytest

from clasher.arena import Position
from clasher.attack_clock import OrdinaryAttackClock
from clasher.battle import BattleState
from clasher.ordinary_combat_clock import publish


@pytest.mark.parametrize('fast_path', [False, True])
@pytest.mark.parametrize('walking', [False, True])
def test_distant_lock_retention_requires_actual_backward_walking(fast_path, walking):
    battle = BattleState(fast_path=fast_path)
    battle._spawn_unit_at_position(
        Position(5.684, 17.605), 1, battle.card_loader.get_card('Archers'),
        deploy_delay_override=0, snap_to_valid=False,
    )
    archer = list(battle.entities.values())[-1]
    archer.position = Position(5.684, 17.605)
    battle._spawn_unit_at_position(
        Position(4.755, 24.186), 0, battle.card_loader.get_card('Giant'),
        deploy_delay_override=0, snap_to_valid=False,
    )
    giant = list(battle.entities.values())[-1]
    archer.target_id = giant.id
    archer._last_combat_target_id = giant.id
    archer._ground_path_backwards = True
    archer._native_natural_movement_active = walking
    archer._attack_windup_active = not walking
    archer._ordinary_clock = OrdinaryAttackClock(
        900, 400, hit_timeline_ms=4500, load_remaining_ms=400,
    )
    publish(archer, archer._ordinary_clock)
    assert not archer.is_within_target_keep_reach(giant)
    assert not archer.is_within_sight(giant)
    if fast_path:
        battle._refresh_fast_path_caches()

    archer.update_combat_component(battle.dt, battle)

    if walking:
        assert archer.target_id == giant.id
    else:
        assert archer.target_id != giant.id
        assert battle.entities[archer.target_id].card_stats.name in {'Tower', 'KingTower'}
