import json
import math
from collections import deque

from clasher.arena import Position
from clasher.battle import BattleState, SERVER_ACTION_DELAY_SECONDS
from clasher.card_aliases import resolve_card_name
from clasher.entities import AreaEffect, Graveyard, SpawnProjectile, Troop, Building
from clasher.paths import decks_path as resolve_decks_path
from clasher.spells import SPELL_REGISTRY


def _load_unique_sample_cards() -> list[str]:
    with resolve_decks_path("decks.json", must_exist=True).open("r", encoding="utf-8") as f:
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
    if spell is not None and not getattr(spell, "requires_territory", False):
        if getattr(spell, "requires_walkable_target", False):
            return Position(3.5, 16.0)
        return Position(9.0, 16.0)
    return Position(9.0, 10.0)


def _resolve_server_action_delay(battle: BattleState) -> None:
    for _ in range(math.ceil(SERVER_ACTION_DELAY_SECONDS / battle.dt)):
        battle.step()


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


def test_enabled_card_aliases_resolve_to_matching_canonical_card_names():
    battle = BattleState()
    mismatches = []

    def normalize(name: str) -> str:
        return "".join(ch for ch in name.casefold() if ch.isalnum())

    for card_name in _load_unique_sample_cards():
        stats = battle.card_loader.get_card(card_name)
        assert stats is not None
        canonical_name = stats.english_name or stats.name
        canonical = normalize(canonical_name)
        requested = normalize(card_name)
        if canonical not in {requested, f"the{requested}"}:
            mismatches.append((card_name, stats.name, canonical_name))

    assert not mismatches, f"Enabled card aliases resolve to the wrong cards: {mismatches}"


def test_mega_knight_deploy_projectile_is_not_used_as_basic_attack():
    battle = BattleState()
    stats = battle.card_loader.get_card("MegaKnight")
    assert stats is not None
    assert stats.projectile_data is None


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
    _resolve_server_action_delay(battle)

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
    _resolve_server_action_delay(battle)

    tornado_areas = [
        e for e in battle.entities.values()
        if isinstance(e, AreaEffect) and getattr(e, "spell_name", "") == "Tornado"
    ]
    assert len(tornado_areas) == 1
    tornado = tornado_areas[0]
    assert tornado.is_tornado
    assert tornado.attract_percentage == 360
    assert tornado.push_speed_factor == 100


def test_graveyard_spawns_graveyard_entity():
    battle = BattleState()
    _prepare_player_for_single_card(battle, 0, "Graveyard")
    assert battle.deploy_card(0, "Graveyard", Position(9.0, 16.0))
    _resolve_server_action_delay(battle)

    graveyards = [e for e in battle.entities.values() if isinstance(e, Graveyard)]
    assert len(graveyards) == 1
    assert graveyards[0].spawn_interval > 0


def test_royal_delivery_is_delayed_spawn_projectile():
    battle = BattleState()
    _prepare_player_for_single_card(battle, 0, "RoyalDelivery")
    assert battle.deploy_card(0, "RoyalDelivery", Position(9.0, 10.0))
    _resolve_server_action_delay(battle)

    delivery_projectiles = [
        e for e in battle.entities.values()
        if isinstance(e, SpawnProjectile) and getattr(e, "spell_name", "") == "RoyalDelivery"
    ]
    assert len(delivery_projectiles) == 1
    delivery = delivery_projectiles[0]
    assert delivery.activation_delay > 0
    assert delivery.spawn_count == 1
