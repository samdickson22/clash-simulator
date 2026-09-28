import json
import random

import pytest

from clasher.rl.deck_pool import load_deck_pool, sample_decks
from clasher.rl.selfplay_env import SelfPlayBattleEnv


def test_sampling_deck_pool_does_not_narrow_observation_vocabulary(tmp_path):
    sampled_cards = [
        "Cannon",
        "Fireball",
        "HogRider",
        "IceGolem",
        "IceSpirit",
        "Musketeer",
        "Skeletons",
        "Log",
    ]
    sampling_path = tmp_path / "sampling-decks.json"
    sampling_path.write_text(
        json.dumps({"decks": [{"name": "focused", "cards": sampled_cards}]}),
        encoding="utf-8",
    )

    env = SelfPlayBattleEnv(
        decks_path="decks.json",
        sampling_decks_path=sampling_path,
        seed=2301,
    )
    env.reset(seed=2301)

    assert env.battle is not None
    assert set(env.battle.players[0].deck) == set(sampled_cards)
    assert set(env.battle.players[1].deck) == set(sampled_cards)
    assert "ArcherQueen" in env.structured_obs_builder.token_names
    assert env.sampling_decks_path == str(sampling_path)


def test_sampling_weights_balance_generated_deck_families(tmp_path):
    heavy = [
        "Cannon",
        "Fireball",
        "HogRider",
        "IceGolem",
        "IceSpirit",
        "Musketeer",
        "Skeletons",
        "Log",
    ]
    light = [
        "Bandit",
        "BattleRam",
        "ElectroWizard",
        "Fireball",
        "MagicArcher",
        "Pekka",
        "RoyalGhost",
        "Zap",
    ]
    sampling_path = tmp_path / "weighted.json"
    sampling_path.write_text(
        json.dumps(
            {
                "decks": [
                    {"cards": heavy, "sampling_weight": 100.0},
                    {"cards": light, "sampling_weight": 1.0},
                ]
            }
        ),
        encoding="utf-8",
    )
    pool = load_deck_pool(sampling_path)
    rng = random.Random(2301)

    sampled = [sample_decks(pool, rng)[0] for _ in range(100)]

    assert sum(set(cards) == set(heavy) for cards in sampled) >= 95


def test_asymmetric_sampling_pools_assign_each_player_independently(tmp_path):
    learner_cards = [
        "ArcherQueen",
        "Cannon",
        "Earthquake",
        "IceSpirit",
        "RoyalDelivery",
        "RoyalHogs",
        "Skeletons",
        "Log",
    ]
    opponent_cards = [
        "Bandit",
        "BattleRam",
        "ElectroWizard",
        "Fireball",
        "MagicArcher",
        "Pekka",
        "RoyalGhost",
        "Zap",
    ]
    learner_path = tmp_path / "learner.json"
    opponent_path = tmp_path / "opponent.json"
    learner_path.write_text(
        json.dumps({"decks": [{"cards": learner_cards}]}), encoding="utf-8"
    )
    opponent_path.write_text(
        json.dumps({"decks": [{"cards": opponent_cards}]}), encoding="utf-8"
    )

    env = SelfPlayBattleEnv(
        decks_path="decks.json",
        player0_sampling_decks_path=learner_path,
        player1_sampling_decks_path=opponent_path,
        seed=2301,
    )
    env.reset(seed=2301)

    assert env.battle is not None
    assert set(env.battle.players[0].deck) == set(learner_cards)
    assert set(env.battle.players[1].deck) == set(opponent_cards)
    assert "LavaHound" in env.structured_obs_builder.token_names


def test_asymmetric_sampling_pools_preserve_sampling_weights(tmp_path):
    heavy = [
        "Cannon",
        "Fireball",
        "HogRider",
        "IceGolem",
        "IceSpirit",
        "Musketeer",
        "Skeletons",
        "Log",
    ]
    light = [
        "Bandit",
        "BattleRam",
        "ElectroWizard",
        "Fireball",
        "MagicArcher",
        "Pekka",
        "RoyalGhost",
        "Zap",
    ]
    sampling_path = tmp_path / "weighted-asymmetric.json"
    sampling_path.write_text(
        json.dumps(
            {
                "decks": [
                    {"cards": heavy, "sampling_weight": 100.0},
                    {"cards": light, "sampling_weight": 1.0},
                ]
            }
        ),
        encoding="utf-8",
    )
    env = SelfPlayBattleEnv(
        decks_path="decks.json",
        player0_sampling_decks_path=sampling_path,
        player1_sampling_decks_path=sampling_path,
        seed=2301,
    )

    sampled = []
    for seed in range(100):
        env.reset(seed=seed)
        assert env.battle is not None
        sampled.extend(
            set(env.battle.players[player].deck) == set(heavy)
            for player in (0, 1)
        )

    assert sum(sampled) >= 190


@pytest.mark.parametrize("learner_player_id", [0, 1])
def test_exact_matchup_sampler_preserves_learner_and_opponent_roles(
    tmp_path, learner_player_id
):
    learner_cards = [
        "ArcherQueen",
        "Cannon",
        "Earthquake",
        "IceSpirit",
        "RoyalDelivery",
        "RoyalHogs",
        "Skeletons",
        "Log",
    ]
    opponent_cards = [
        "Bandit",
        "BattleRam",
        "ElectroWizard",
        "Fireball",
        "MagicArcher",
        "Pekka",
        "RoyalGhost",
        "Zap",
    ]
    matchups_path = tmp_path / "matchups.json"
    matchups_path.write_text(
        json.dumps(
            {
                "matchups": [
                    {
                        "learner_cards": learner_cards,
                        "opponent_cards": opponent_cards,
                        "weight": 2.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    env = SelfPlayBattleEnv(
        decks_path="decks.json",
        matchups_path=matchups_path,
        matchup_probability=1.0,
        learner_player_id=learner_player_id,
        seed=2301,
    )
    env.reset(seed=2301)

    assert env.battle is not None
    learner_deck = env.battle.players[learner_player_id].deck
    opponent_deck = env.battle.players[1 - learner_player_id].deck
    assert set(learner_deck) == set(learner_cards)
    assert set(opponent_deck) == set(opponent_cards)


def test_exact_matchup_sampler_requires_a_positive_probability(tmp_path):
    matchups_path = tmp_path / "matchups.json"
    matchups_path.write_text(json.dumps({"matchups": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="used together"):
        SelfPlayBattleEnv(decks_path="decks.json", matchups_path=matchups_path)


def test_ordered_deck_reset_preserves_hand_and_cycle() -> None:
    ordered = [
        "HogRider",
        "Musketeer",
        "Cannon",
        "Fireball",
        "Skeletons",
        "IceSpirit",
        "IceGolem",
        "Log",
    ]
    opponent_ordered = list(reversed(ordered))
    env = SelfPlayBattleEnv(decks_path="decks.json", seed=2301)
    env.reset(
        seed=2301,
        ordered_decks=(ordered, opponent_ordered),
    )
    assert env.battle is not None

    assert env.battle.players[0].deck == ordered
    assert env.battle.players[0].hand == ordered[:4]
    assert list(env.battle.players[0].cycle_queue) == ordered[4:]
    assert env.battle.players[1].deck == opponent_ordered
    assert env.battle.players[1].hand == opponent_ordered[:4]
    assert list(env.battle.players[1].cycle_queue) == opponent_ordered[4:]
