"""Native removal finish requires positive hit work, not an adapter latch."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.ordinary_combat_clock import get_clock


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("timeline,finish", [(0, 0), (50, 1)])
def test_stopped_hit_does_not_arm_target_removal_finish(fast_path, timeline, finish):
    # Native expanded-deck seed1305001 tick182: a Log-stopped Musketeer
    # loses its Goblin target with timeline0 and reacquires Cannon next tick.
    battle = BattleState(fast_path=fast_path)
    battle._spawn_unit_at_position(
        Position(3.499, 13.973), 0, battle.card_loader.get_card("Musketeer"),
        deploy_delay_override=0, snap_to_valid=False,
    )
    actor = battle.entities[max(battle.entities)]
    actor.target_id = 99
    actor._attack_windup_active = True
    actor._has_attacked_once = True
    clock = get_clock(actor)
    assert clock is not None
    clock.hit_timeline_ms = timeline

    actor.on_combat_target_removed(99)

    assert actor.target_id is None
    assert actor._attack_finish_elapsed_ms == finish
    assert clock.finish_elapsed_ms == finish
