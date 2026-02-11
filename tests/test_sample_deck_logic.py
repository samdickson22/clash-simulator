import json
import os
import sys
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.entities import AreaEffect, Graveyard, SpawnProjectile, Troop, Building
from clasher.spells import SPELL_REGISTRY


def _load_unique_sample_cards() -> list[str]:
    with open(os.path.join(os.path.dirname(__file__), "..", "decks.json"), "r") as f:
        decks = json.load(f)["decks"]
    return sorted({card for deck in decks for card in deck["cards"]})


def _prepare_player_for_single_card(battle: BattleState, player_id: int, card_name: str) -> None:
    player = battle.players[player_id]
    player.elixir = 100.0
    player.hand = [card_name]
    player.deck = [card_name]
    player.cycle_queue = deque()


def _deployment_position(card_name: str) -> Position:
    resolved = resolve_card_name(card_name)
    spell = SPELL_REGISTRY.get(resolved)
    # Rolling projectiles follow troop deployment rules.
    if spell is not None and type(spell).__name__ not in {"RollingProjectileSpell"}:
        return Position(9.0, 16.0)
    return Position(9.0, 10.0)


def test_all_sample_deck_cards_resolve_and_deploy():
    cards = _load_unique_sample_cards()
    missing = []
    failed_deploy = []

    for card_name in cards:
        battle = BattleState()
        resolved = resolve_card_name(card_name, battle.card_loader.load_card_definitions())
        stats = battle.card_loader.get_card(card_name)
        if stats is None:
            missing.append(card_name)
            continue

        _prepare_player_for_single_card(battle, 0, card_name)
        pos = _deployment_position(card_name)
        if not battle.deploy_card(0, card_name, pos):
            failed_deploy.append((card_name, resolved))

    assert not missing, f"Missing cards: {missing}"
    assert not failed_deploy, f"Failed deploys: {failed_deploy}"


def test_archers_card_spawns_two_archers():
    battle = BattleState()
    _prepare_player_for_single_card(battle, 0, "Archers")
    assert battle.deploy_card(0, "Archers", Position(9.0, 10.0))

    archers = [
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Archer"
    ]
    assert len(archers) == 2


def test_poison_is_persistent_slowing_area():
    battle = BattleState()
    _prepare_player_for_single_card(battle, 0, "Poison")
    assert battle.deploy_card(0, "Poison", Position(9.0, 16.0))

    poison_areas = [
        e for e in battle.entities.values()
        if isinstance(e, AreaEffect) and getattr(e, "spell_name", "") == "Poison"
    ]
    assert len(poison_areas) == 1
    poison = poison_areas[0]
    assert poison.duration >= 7.5
    assert poison.damage > 0
    assert poison.freeze_effect is False
    assert poison.speed_multiplier < 1.0


def test_earthquake_deals_bonus_damage_to_buildings():
    battle = BattleState()
    _prepare_player_for_single_card(battle, 0, "Earthquake")

    cannon_stats = battle.card_loader.get_card("Cannon")
    knight_stats = battle.card_loader.get_card("Knight")
    assert cannon_stats is not None
    assert knight_stats is not None

    cannon = battle._spawn_entity(Building, Position(9.0, 16.0), 1, cannon_stats)
    battle._spawn_troop(Position(10.0, 16.0), 1, knight_stats)
    enemy_knight = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 1 and e.card_stats.name == "Knight"
    )
    cannon.deploy_delay_remaining = 0.0
    enemy_knight.deploy_delay_remaining = 0.0

    cannon_hp_before = cannon.hitpoints
    knight_hp_before = enemy_knight.hitpoints

    assert battle.deploy_card(0, "Earthquake", Position(9.0, 16.0))
    for _ in range(140):
        battle.step()

    cannon_damage_taken = cannon_hp_before - cannon.hitpoints
    knight_damage_taken = knight_hp_before - enemy_knight.hitpoints
    assert cannon_damage_taken > knight_damage_taken


def test_tornado_sets_pull_area():
    battle = BattleState()
    _prepare_player_for_single_card(battle, 0, "Tornado")
    assert battle.deploy_card(0, "Tornado", Position(9.0, 16.0))

    tornado_areas = [
        e for e in battle.entities.values()
        if isinstance(e, AreaEffect) and getattr(e, "spell_name", "") == "Tornado"
    ]
    assert len(tornado_areas) == 1
    tornado = tornado_areas[0]
    assert tornado.is_tornado
    assert tornado.pull_force > 0


def test_graveyard_spawns_graveyard_entity():
    battle = BattleState()
    _prepare_player_for_single_card(battle, 0, "Graveyard")
    assert battle.deploy_card(0, "Graveyard", Position(9.0, 16.0))

    graveyards = [e for e in battle.entities.values() if isinstance(e, Graveyard)]
    assert len(graveyards) == 1
    assert graveyards[0].spawn_interval > 0


def test_royal_delivery_is_delayed_spawn_projectile():
    battle = BattleState()
    _prepare_player_for_single_card(battle, 0, "RoyalDelivery")
    assert battle.deploy_card(0, "RoyalDelivery", Position(9.0, 16.0))

    delivery_projectiles = [
        e for e in battle.entities.values()
        if isinstance(e, SpawnProjectile) and getattr(e, "spell_name", "") == "RoyalDelivery"
    ]
    assert len(delivery_projectiles) == 1
    delivery = delivery_projectiles[0]
    assert delivery.activation_delay > 0
    assert delivery.spawn_count == 1
