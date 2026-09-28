import json
import math

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.rl.structured_obs import StructuredObservationBuilder


def test_public_card_metadata_and_visible_hp_share_explicit_ruleset(tmp_path):
    default_loader = CardDataLoader()
    data = json.loads(default_loader.data_file.read_text())
    spirit_entry = next(c for c in data["items"]["spells"] if c["id"] == 26000030)
    assert spirit_entry["summonCharacterData"]["hitpoints"] == 90
    # The opened native15.535.86 profile has base84, yielding215 at level11.
    spirit_entry["summonCharacterData"]["hitpoints"] = 84
    profile = tmp_path / "native-profile.json"
    profile.write_text(json.dumps(data))
    loader = CardDataLoader(profile)
    builder = StructuredObservationBuilder(card_vocab=["IceSpirit"], card_loader=loader)
    battle = BattleState(card_loader=loader)
    battle.players[0].hand = ["IceSpirit"]
    before = set(battle.entities)
    assert battle.deploy_card(0, "IceSpirit", Position(3.5, 11.5))
    spirit = battle.entities[(set(battle.entities) - before).pop()]
    assert spirit.max_hitpoints == 215
    spirit.take_damage(192)
    token = builder.token_id(spirit.card_stats.name)
    assert builder.card_stat_features[token, 5] == pytest.approx(math.log1p(84) / 9)
    observation = builder.build_actor(battle, 0)
    rows = observation.entity_features[(observation.entity_ids == token) & observation.entity_mask]
    assert len(rows) == 1
    assert rows[0, 9] == pytest.approx(23 / 215)
    # Loading the pinned profile must not change the default ruleset snapshot.
    assert default_loader.get_card("IceSpirit").scaled_hitpoints == 230
