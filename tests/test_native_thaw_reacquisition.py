"""Thaw resumes nearby attacks but cannot extend them to distant targets."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.ordinary_combat_clock import get_clock, publish


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("nearby", [False, True])
def test_thaw_checks_reacquired_target_range(fast_path, nearby):
    battle = BattleState(fast_path=fast_path)
    battle._spawn_unit_at_position(
        Position(2.424, 15.544), 0, battle.card_loader.get_card("Musketeer"),
        deploy_delay_override=0, snap_to_valid=False,
    )
    actor = battle.entities[max(battle.entities)]
    if nearby:
        battle._spawn_unit_at_position(
            Position(2.424, 18.544), 1, battle.card_loader.get_card("Knight"),
            deploy_delay_override=0, snap_to_valid=False,
        )
    actor._has_attacked_once = True
    clock = get_clock(actor)
    assert clock is not None
    clock.hit_timeline_ms = 3350
    clock.load_remaining_ms = 0
    publish(actor, clock)
    actor.apply_stun(.05, interrupt_combat=False)
    battle.step()
    assert actor.position == Position(2.424, 15.544)
    assert clock.hit_timeline_ms == 3350

    battle.step()

    assert actor.target_id is not None
    if nearby:
        assert actor.position == Position(2.424, 15.544)
        assert clock.hit_timeline_ms == 3400
    else:
        assert actor.position != Position(2.424, 15.544)
        assert clock.hit_timeline_ms == 0
        assert clock.load_remaining_ms == 0
