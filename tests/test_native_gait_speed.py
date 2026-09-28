import json
from pathlib import Path

import pytest

from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.factory.dynamic_factory import troop_from_character_data


@pytest.mark.parametrize(
    "card,expected", [("Giant", 52), ("Golem", 54), ("IceGolem", 52), ("HogRider", 120)]
)
def test_native_stride_speed_is_normalized_once_in_both_factories(card, expected):
    stats = CardDataLoader().get_card(card)
    data = stats._raw_entry["summonCharacterData"]
    serialized = data["speed"]
    assert stats.speed == expected
    assert stats._card_def.troop_stats.speed_logic_units_per_tick == expected
    dynamic = troop_from_character_data(card, data)
    assert dynamic.speed == expected
    assert dynamic._raw_entry["summonCharacterData"]["speed"] == serialized
    assert serialized == (120 if card == "HogRider" else 45)


def test_initial_crown_geometry_matches_native_world_coordinates():
    reference = json.loads(
        (
            Path(__file__).parent / "fixtures/native_crown_geometry_15_535_86.json"
        ).read_text()
    )
    battle = BattleState()
    actual = sorted(
        (
            e.player_id,
            round(e.position.x * 1000),
            round(e.position.y * 1000),
            e.hitpoints,
        )
        for e in battle.entities.values()
    )
    assert actual == sorted(tuple(row) for row in reference["towers"])
