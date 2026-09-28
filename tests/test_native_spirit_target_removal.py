"""Spirit flight keeps its carrier but removes the character's combat lock."""

import pytest

from clasher.arena import Position
from clasher.attack_clock import OrdinaryAttackClock
from clasher.battle import BattleState
from clasher.ordinary_combat_clock import publish


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("spirit_name", ["IceSpirit", "ElectroSpirit"])
def test_spirit_launch_preserves_observer_finish_while_carrier_flies(
    fast_path, spirit_name
):
    # Native Ice Spirit5000054 disappears at2790 while Archer5000053 retains
    # timeline800/load50, then800/0 on2791. Electro Spirit shares the carrier
    # transition; its observer timing here is a structural transfer control.
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    for name, owner, xy in (
        ("Archers", 0, (2.999, 14.5)),
        (spirit_name, 1, (3.03, 17.798)),
    ):
        battle._spawn_unit_at_position(
            Position(*xy), owner, battle.card_loader.get_card(name),
            deploy_delay_override=0, snap_to_valid=False,
        )
    archer, spirit = battle.entities.values()
    archer.target_id = spirit.id
    archer._last_combat_target_id = spirit.id
    archer._attack_windup_active = True
    archer._ordinary_clock = OrdinaryAttackClock(
        900, 400, hit_timeline_ms=750, load_remaining_ms=100,
    )
    publish(archer, archer._ordinary_clock)
    spirit.target_id = archer.id
    spirit.attack_cooldown = 0
    if fast_path:
        battle._refresh_fast_path_caches()

    battle.step()

    assert archer.target_id is None
    assert archer._ordinary_clock.hit_timeline_ms == 800
    assert archer._ordinary_clock.load_remaining_ms == 50
    assert archer._ordinary_clock.finish_elapsed_ms == 1
    assert spirit.is_alive and spirit.entity_kind == 2
    assert battle.entities[spirit.id] is spirit
    position = (spirit.position.x, spirit.position.y)

    battle.step()

    assert archer._ordinary_clock.hit_timeline_ms == 800
    assert archer._ordinary_clock.load_remaining_ms == 0
    assert archer._ordinary_clock.finish_elapsed_ms == 51
    assert (spirit.position.x, spirit.position.y) != position
