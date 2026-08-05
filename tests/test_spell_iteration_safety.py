from collections import deque

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import AreaEffect, Projectile, Troop


def _set_hand(battle: BattleState, player_id: int, cards: list[str], elixir: float = 10.0) -> None:
    player = battle.players[player_id]
    player.elixir = elixir
    player.hand = list(cards[:4])
    player.deck = list(cards[:8] if len(cards) >= 8 else cards + cards)
    player.cycle_queue = deque(player.deck[4:])


def test_direct_damage_spell_safe_when_target_death_spawns():
    battle = BattleState()
    _set_hand(
        battle,
        0,
        ["Zap", "Knight", "Archers", "Giant", "Minions", "Musketeer", "Fireball", "Cannon"],
    )
    _set_hand(
        battle,
        1,
        ["Balloon", "Knight", "Archers", "Giant", "Minions", "Musketeer", "Fireball", "Cannon"],
    )

    target_pos = Position(9.0, 22.0)
    assert battle.deploy_card(1, "Balloon", target_pos)

    balloon = next(
        e
        for e in battle.entities.values()
        if isinstance(e, Troop) and getattr(getattr(e, "card_stats", None), "name", "") == "Balloon"
    )
    # Force lethal direct-damage path so death mechanics can mutate entity dict while spell resolves.
    balloon.deploy_delay_remaining = 0.0
    balloon.placement_pending = False
    balloon.on_spawn()
    balloon.hitpoints = 1

    assert battle.deploy_card(0, "Zap", Position(9.0, 22.0))
    for _ in range(31):
        battle.step()

    # Regression assertion: no RuntimeError from dict-size mutation during spell iteration.
    assert not balloon.is_alive


def test_direct_damage_spell_does_not_damage_projectile_entities():
    battle = BattleState()
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 22.0),
        player_id=1,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=100,
        range=0,
        sight_range=0,
        target_position=Position(9.0, 10.0),
    )
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1
    _set_hand(battle, 0, ["Zap"])

    assert battle.deploy_card(0, "Zap", Position(9.0, 22.0))

    assert projectile.is_alive
    assert projectile.hitpoints == 1


def test_persistent_spells_do_not_damage_or_pull_other_spell_effects():
    battle = BattleState()
    enemy_effect = AreaEffect(
        id=battle.next_entity_id,
        position=Position(10.0, 22.0),
        player_id=1,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=1,
        range=1,
        sight_range=1,
        duration=8.0,
        radius=1.0,
    )
    battle.entities[enemy_effect.id] = enemy_effect
    battle.next_entity_id += 1
    _set_hand(battle, 0, ["Tornado"])

    assert battle.deploy_card(0, "Tornado", Position(9.0, 22.0))
    original = (enemy_effect.position.x, enemy_effect.position.y)
    battle.step()

    assert enemy_effect.is_alive
    assert enemy_effect.hitpoints == 1
    assert (enemy_effect.position.x, enemy_effect.position.y) == original
