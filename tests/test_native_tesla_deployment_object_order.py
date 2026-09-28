"""Tesla's deployment attack observes earlier native projectile impacts."""

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Projectile


@pytest.mark.parametrize('fast_path', [False, True])
def test_tesla_acquires_after_lethal_arrow_on_deployment_completion(fast_path):
    # Reversed-0 seed1307002 left branch, interval3019: an Archer arrow kills
    # IceGolem5000078 before Tesla5000084 completes deployment. Native Tesla
    # acquires Goblin5000082 and starts timeline750/load700 with no finish.
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()

    def troop(name, x, y):
        before = set(battle.entities)
        battle._spawn_unit_at_position(
            Position(x, y), 0, battle.card_loader.get_card(name),
            deploy_delay_override=0, snap_to_valid=False,
        )
        entity = battle.entities[(set(battle.entities) - before).pop()]
        entity.attack_cooldown = 10
        entity.speed = 0
        return entity

    golem = troop('IceGolem', 14.925, 16.366)
    goblin = troop('Goblins', 14.276, 15.383)
    golem.hitpoints = 69
    tesla = battle._spawn_entity(
        Building, Position(14, 18), 1, battle.card_loader.get_card('Tesla'),
    )
    tesla.deploy_delay_remaining = battle.dt
    archer = battle.card_loader.get_card('Archers')
    arrow = Projectile(
        id=battle.next_entity_id, position=Position(14.925, 16.366),
        player_id=1, card_stats=archer, hitpoints=1, max_hitpoints=1,
        damage=112, range=0, sight_range=0, travel_speed=12,
        target_position=Position(14.925, 16.366), primary_target=golem,
    )
    arrow.battle_state = battle
    battle.entities[arrow.id] = arrow
    battle.next_entity_id += 1
    assert arrow.id > tesla.id
    if fast_path:
        battle._refresh_fast_path_caches()

    battle.step()

    assert not golem.is_alive
    assert tesla.target_id == goblin.id
    assert tesla._ordinary_clock.hit_timeline_ms == 750
    assert tesla._ordinary_clock.load_remaining_ms == 700
    assert tesla._attack_finish_elapsed_ms == 0
