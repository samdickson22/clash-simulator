"""Spirit launch cannot revoke movement selected earlier in the combat phase."""

import pytest

from clasher.arena import Position
from clasher.battle import BattleState


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("spirit_name", ["IceSpirit", "ElectroSpirit"])
def test_committed_knight_step_survives_spirit_launch(fast_path, spirit_name):
    # Native seed1300201 neighbor1883 positions. Cached routes/other bodies
    # are omitted: compare against the same committed step with a live target.
    # The full replay supplies the exact native displacement check.
    positions = []
    for launch in (False, True):
        battle = BattleState(fast_path=fast_path)
        battle.entities.clear()
        for name, owner, xy in (
            ("Knight", 0, (3.889, 16.337)),
            (spirit_name, 1, (3.499, 18.499)),
        ):
            battle._spawn_unit_at_position(
                Position(*xy), owner, battle.card_loader.get_card(name),
                deploy_delay_override=0, snap_to_valid=False,
            )
        knight, spirit = battle.entities.values()
        knight.apply_slow(0.2, 0.7)
        knight.target_id = spirit.id
        if fast_path:
            battle._refresh_fast_path_caches()
        knight.update_combat_component(battle.dt, battle)
        assert knight._movement_target_id == spirit.id
        if launch:
            for mechanic in spirit.mechanics:
                mechanic.on_attack_start(spirit, knight)
            assert spirit.entity_kind == 2
            assert not knight._is_valid_target(spirit, is_current_target=True)
        start = (knight.position.x, knight.position.y)

        knight.update_movement_component(battle.dt, battle)

        positions.append((knight.position.x, knight.position.y))
        assert positions[-1] != start
    assert positions[0] == positions[1]
