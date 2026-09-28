"""Pending arrows survive target depletion until observer removal callbacks."""

import pytest

from clasher.arena import Position
from clasher.attack_clock import OrdinaryAttackClock
from clasher.battle import BattleState
from clasher.entities import Building, Projectile
from clasher.ordinary_combat_clock import publish


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("pending_arrows", [False, True])
def test_depletion_keeps_pending_target_removal_behavior(fast_path, pending_arrows):
    # Native2939 Archer5000052 has timeline1850/load350 and a lethal pending
    # lock on Cannon5000056. Earlier direct damage depletes the Cannon2940.
    # A Knight supplies that earlier damage in this conditional fixture.
    battle = BattleState(fast_path=fast_path)
    for name, xy in (("Knight", (3.0, 17.0)), ("Archers", (4.643, 15.859))):
        battle._spawn_unit_at_position(
            Position(*xy), 0, battle.card_loader.get_card(name),
            deploy_delay_override=0, snap_to_valid=False,
        )
    knight, archer = list(battle.entities.values())[-2:]
    target = battle._spawn_entity(
        Building, Position(2.5, 18.5), 1, battle.card_loader.get_card("Cannon")
    )
    target.hitpoints = 166
    target.attack_cooldown = 10
    knight.target_id = target.id
    knight.attack_cooldown = 0
    archer.target_id = target.id
    archer._last_combat_target_id = target.id
    archer._has_attacked_current_target = True
    archer._has_attacked_once = True
    archer._attack_windup_active = True
    archer._ordinary_clock = OrdinaryAttackClock(
        900, 400, hit_timeline_ms=1850, load_remaining_ms=350,
    )
    publish(archer, archer._ordinary_clock)
    if pending_arrows:
        for xy in ((3.982, 16.674), (2.575, 17.570)):
            projectile = Projectile(
                id=battle.next_entity_id, position=Position(*xy), player_id=0,
                card_stats=archer.card_stats, hitpoints=1, max_hitpoints=1,
                damage=112, range=0, sight_range=0,
                target_position=Position(2.5, 18.5), travel_speed=12,
                source_name="Archer", source_entity=archer, primary_target=target,
            )
            projectile.battle_state = battle
            battle.entities[projectile.id] = projectile
            battle.next_entity_id += 1
    archer._note_combat_target(target)
    assert archer._combat_target_pending_lethal == pending_arrows
    if fast_path:
        battle._refresh_fast_path_caches()

    battle.step()

    assert not target.is_alive
    assert archer.target_id is None
    assert archer._ordinary_clock.hit_timeline_ms == 1900
    assert archer._ordinary_clock.load_remaining_ms == 300
    assert archer._attack_finish_elapsed_ms == (0 if pending_arrows else 1)
    position = (archer.position.x, archer.position.y)

    battle.step()

    assert ((archer.position.x, archer.position.y) != position) == pending_arrows
    assert archer._ordinary_clock.load_remaining_ms == 250
