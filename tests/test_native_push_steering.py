"""Native tick2560: retained avoidance rotates a Log push before collision."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("xy,work,expected", [
    ((3.497, 18.774), 175, (3596, 18661)),
    ((3.933, 18.510), 0, (3958, 18511)),
])
def test_native_knight_log_push_uses_retained_avoidance(fast_path, xy, work, expected):
    # Paused native reads at2559 give target4172,18959,work175,avoidance170.
    # At2560 native position is3596,18661; an unsteered push goes3641,18813.
    battle = BattleState(fast_path=fast_path)
    battle._spawn_unit_at_position(
        Position(*xy), 0, battle.card_loader.get_card("Knight"),
        deploy_delay_override=0, snap_to_valid=False,
    )
    knight = battle.entities[max(battle.entities)]
    assert knight.begin_knockback(
        Position(4.172, 18.959), 700, source_kind="Log",
        interrupts_combat=False,
    )
    knight._native_avoidance = 170
    knight._knockback_velocity_work = work

    knight.update_movement_component(battle.dt, battle)

    assert knight._native_avoidance == 170
    assert (round(knight.position.x * 1000), round(knight.position.y * 1000)) == expected
