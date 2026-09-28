import math

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.structured_obs import StructuredObservationBuilder


@pytest.mark.parametrize("card", ["IceSpirit", "ElectroSpirit"])
@pytest.mark.parametrize("owner", [0, 1])
def test_launched_spirit_public_row_has_projectile_identity_and_no_body_state(card, owner):
    battle = BattleState()
    battle.players[owner].hand = [card]
    before = set(battle.entities)
    assert battle.deploy_card(owner, card, Position(3.5, 12 if owner == 0 else 20))
    spirit = battle.entities[(set(battle.entities) - before).pop()]
    projectile = spirit.card_stats.projectile_data
    body_name = spirit.card_stats.name
    projectile_name = projectile["name"]
    builder = StructuredObservationBuilder(
        card_vocab=[card],
        token_names=["<pad>", "<unknown>", f"troop_body:{body_name}", f"projectile:{projectile_name}"],
    )
    token, body = builder._entity_row(spirit, owner)
    assert token == 2
    assert body[4] == 1 and body[9] == 1
    target = battle.entities[4 if owner == 0 else 1]
    for mechanic in spirit.mechanics:
        mechanic.on_attack_start(spirit, target)
    token, flight = builder._entity_row(spirit, owner)
    assert token == 3
    assert flight[6] == 1 and flight[4] == 0
    assert not flight[9:23].any()
    assert not flight[24:30].any()
    expected_speed = projectile["speed"] / 50.0
    assert flight[23] == pytest.approx(math.log1p(expected_speed) / math.log1p(1000))
    assert flight[30] > 0
    # Retained callback fields are not a health bar or character status.
    spirit.hitpoints = 1
    spirit.max_hitpoints = 999
    spirit.stun_timer = 5
    spirit.slow_timer = 4
    spirit.haste_timer = 3
    spirit.deploy_delay_remaining = 1
    spirit._attack_windup_active = True
    np.testing.assert_array_equal(builder._entity_row(spirit, owner)[1], flight)
    for perspective in [0, 1]:
        actor = builder.build_actor(battle, perspective)
        rows = actor.entity_features[actor.entity_ids == 3]
        assert len(rows) == 1
        assert rows[0, 6] == 1 and not rows[0, 9:23].any()
