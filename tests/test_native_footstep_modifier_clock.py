"""Footstep time scales independently of the rounded stride speed."""
from clasher.arena import Position
from clasher.battle import BattleState


def test_slowed_giant_footstep_clock_uses_buff_percentage():
    battle = BattleState()
    before = set(battle.entities)
    battle._spawn_unit_at_position(Position(9,20), 1,
                                  battle.card_loader.get_card('Giant'),
                                  deploy_delay_override=0, snap_to_valid=False)
    giant = battle.entities[(set(battle.entities)-before).pop()]
    target = next(e for e in battle.entities.values()
                  if e.player_id == 0 and getattr(e, '_crown_tower_slot', None) == 'king')
    giant.apply_slow(10, .7)
    for _ in range(10):
        giant._move_towards_target(target, battle.dt, battle)
    # f66288..f663ec scales100->70, then /2. Rounded52->36 stride speed
    # must not instead produce floor(50*36/52)=34 clock units per frame.
    assert giant.movement_phase_elapsed_ms == 350
