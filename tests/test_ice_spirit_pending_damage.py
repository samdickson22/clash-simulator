"""Ice Spirit flight reserves lethal damage without changing splash ownership."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.cards.ice_spirit import IceSpiritFreeze


def spawn(battle, name, owner, xy):
    before = set(battle.entities)
    battle._spawn_unit_at_position(
        Position(*xy), owner, battle.card_loader.get_card(name),
        deploy_delay_override=0, snap_to_valid=False,
    )
    return next(e for i, e in battle.entities.items() if i not in before)


@pytest.mark.parametrize('fast_path', [False, True])
def test_spirit_reserves_primary_after_launch_and_releases_at_impact(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    spirit = spawn(battle, 'IceSpirit', 0, (9, 14))
    primary = spawn(battle, 'Knight', 1, (9, 15.5))
    splash = spawn(battle, 'Knight', 1, (10, 15.5))
    for target in (primary, splash):
        target.hitpoints = spirit.damage
        target.apply_stun(10)
    spirit.target_id = primary.id
    spirit.attack_cooldown = 0
    assert not primary.is_expected_to_die_from_projectiles()

    battle.step()

    assert spirit._self_projectile_launched
    assert primary.is_expected_to_die_from_projectiles()
    assert not splash.is_expected_to_die_from_projectiles()
    assert primary._pending_projectile_max_duration_ms == 200
    mechanic = next(m for m in spirit.mechanics if isinstance(m, IceSpiritFreeze))
    for _ in range(8):
        battle.step()
        if not spirit.is_alive:
            break
    assert not spirit.is_alive
    assert not primary.is_alive
    assert not splash.is_alive
    assert mechanic.pending_damage_against(spirit, primary) == 0


@pytest.mark.parametrize('distance,duration,reserved', [(4.8, 600, True), (4.808, 650, False)])
def test_spirit_reservation_obeys_shared_duration_cutoff(distance, duration, reserved):
    battle = BattleState()
    spirit = spawn(battle, 'IceSpirit', 0, (9, 10))
    target = spawn(battle, 'Knight', 1, (9, 10 + distance))
    target.hitpoints = spirit.damage
    mechanic = next(m for m in spirit.mechanics if isinstance(m, IceSpiritFreeze))
    mechanic.on_attack_start(spirit, target)
    assert not target.is_expected_to_die_from_projectiles()
    mechanic.activate_pending_damage(spirit)
    assert target._pending_projectile_max_duration_ms == duration
    assert target.is_expected_to_die_from_projectiles() is reserved
    target._tick_pending_projectile_duration(.05)
    mechanic.activate_pending_damage(spirit)
    assert target._pending_projectile_max_duration_ms == duration - 50


def test_dead_primary_reservation_does_not_transfer_to_splash_target():
    battle = BattleState()
    spirit = spawn(battle, 'IceSpirit', 0, (9, 14))
    primary = spawn(battle, 'Knight', 1, (9, 15.5))
    splash = spawn(battle, 'Knight', 1, (10, 15.5))
    mechanic = next(m for m in spirit.mechanics if isinstance(m, IceSpiritFreeze))
    mechanic.on_attack_start(spirit, primary)
    mechanic.activate_pending_damage(spirit)
    primary.take_damage(primary.hitpoints)
    del battle.entities[primary.id]
    assert mechanic.pending_damage_against(spirit, splash) == 0
    assert not splash.is_expected_to_die_from_projectiles()
