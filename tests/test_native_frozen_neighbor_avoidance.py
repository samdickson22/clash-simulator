"""Frozen neighbors retain their direction in the avoidance dot product."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("walking", [False, True])
def test_frozen_neighbor_preserves_movement_state(fast_path, walking):
    # Expanded native seed1305001, frame2646->2647. The observer keeps
    # avoidance0; treating its frozen neighbor's direction as zero yields190.
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    for xy in ((12.599, 17.360), (13.730, 16.895)):
        battle._spawn_unit_at_position(
            Position(*xy), 1, battle.card_loader.get_card("Goblins"),
            deploy_delay_override=0, snap_to_valid=False,
        )
    observer, neighbor = battle.entities.values()
    observer._movement_target_id = 999
    observer._facing_x_units, observer._facing_y_units = 1256, -665
    neighbor._facing_x_units, neighbor._facing_y_units = 571, -1266
    neighbor._native_natural_movement_active = walking
    neighbor.apply_stun(.5)
    assert neighbor.is_stunned()
    neighbor._native_natural_movement_active = False
    neighbor.apply_stun(.7)
    assert neighbor._native_movement_component_stopped() == (not walking)

    observer._update_native_avoidance(battle)

    assert observer._native_avoidance == (0 if walking else 190)

