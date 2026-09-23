from __future__ import annotations

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import (
    Building,
    Troop,
    _can_attack_air_from_card_stats,
    _can_attack_ground_from_card_stats,
)


def test_cached_target_capabilities_match_all_loaded_card_data() -> None:
    battle = BattleState(fast_path=True)
    cards = battle.card_loader.load_cards()

    for card in cards.values():
        assert isinstance(_can_attack_air_from_card_stats(card), bool)
        assert isinstance(_can_attack_ground_from_card_stats(card), bool)


def test_spawned_entities_cache_exact_target_capabilities() -> None:
    battle = BattleState(fast_path=True)
    for entity_type, card_name, position in (
        (Troop, "Knight", Position(3.5, 10.5)),
        (Troop, "Musketeer", Position(4.5, 10.5)),
        (Building, "Tesla", Position(9.5, 10.5)),
    ):
        card = battle.card_loader.get_card(card_name)
        assert card is not None
        entity = battle._spawn_entity(entity_type, position, 0, card)
        assert entity._can_attack_air() is _can_attack_air_from_card_stats(card)
        assert entity._can_attack_ground() is _can_attack_ground_from_card_stats(card)
