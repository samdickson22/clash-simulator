"""Public-only C56 placement and targeting regressions."""

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.c56_scripted import CHAMPION_ABILITY_RULE
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent


@pytest.fixture(scope="module")
def builder():
    return ContractV5ObservationBuilder()


def scene(builder, hand, owner=0):
    battle = BattleState()
    battle.players[owner].hand = list(hand)
    battle.players[owner].elixir = 10
    return battle, PublicScriptedOpponent(builder, card_scope="c56")


def spawn(battle, name, owner, xy):
    battle._spawn_unit_at_position(
        Position(*xy),
        owner,
        battle.card_loader.get_card(name),
        deploy_delay_override=0,
        snap_to_valid=False,
    )


@pytest.mark.parametrize("owner", [0, 1])
@pytest.mark.parametrize("card", ["Miner", "GoblinBarrel"])
def test_deploy_anywhere_reaches_enemy_crown(builder, owner, card):
    battle, bot = scene(builder, [card, "Skeletons", "Knight", "Cannon"], owner)
    choice = bot.decide(builder.build_public(battle, owner))
    assert choice.action_id // 576 == 0
    assert (choice.action_id % 576) // 18 + 0.5 > 20


def test_air_threat_uses_anti_air_card(builder):
    battle, bot = scene(builder, ["MiniPekka", "Musketeer", "Knight", "Cannon"])
    spawn(battle, "Balloon", 1, (3.5, 11.5))
    choice = bot.decide(builder.build_public(battle, 0))
    assert choice.action_id // 576 == 1


def test_spells_respect_air_and_lightning_target_cap(builder):
    battle, bot = scene(builder, ["Earthquake", "Lightning", "Poison", "Tornado"])
    for xy in [(3.5, 11.5), (4.5, 11.5), (5.5, 11.5), (6.5, 11.5)]:
        spawn(battle, "Balloon", 1, xy)
    choices = bot.ranked_plays(builder.build_public(battle, 0))
    assert max(c.score for c in choices if c.action_id // 576 == 0) < -1e5
    assert max(c.score for c in choices if c.action_id // 576 == 1) > 0


@pytest.mark.parametrize("card,minimum_y", [("Xbow", 13.5), ("GoblinHut", 11.5)])
def test_siege_and_spawner_have_declared_forward_placement(builder, card, minimum_y):
    battle, bot = scene(builder, [card, "Rocket", "Lightning", "Poison"])
    choices = bot.ranked_plays(builder.build_public(battle, 0))
    best = next(c for c in choices if c.action_id // 576 == 0)
    assert (best.action_id % 576) // 18 + 0.5 >= minimum_y


def test_champion_rule_masks_ability_and_handles_both_goblinstein_bodies(builder):
    battle, bot = scene(builder, ["Goblinstein", "ArcherQueen", "Skeletons", "Knight"])
    assert battle.deploy_card(0, "Goblinstein", Position(7.5, 8.5))
    for _ in range(30):
        battle.step()
    packet = builder.build_public(battle, 0)
    assert CHAMPION_ABILITY_RULE.startswith("masked:")
    assert all(c.action_id != 2305 for c in bot._ranked_actions(packet, all_plays=True))


def test_c56_decision_ignores_opponent_private_state(builder):
    battle, bot = scene(builder, ["Miner", "GoblinBarrel", "GoblinHut", "Xbow"])
    before = bot.decide(builder.build_public(battle, 0))
    battle.players[1].hand = ["Rocket"] * 4
    battle.players[1].elixir = 0
    assert bot.decide(builder.build_public(battle, 0)) == before
