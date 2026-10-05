import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import torch

from clasher.rl.council_opponents import (
    CouncilLeagueOpponent,
    CouncilOpponentPool,
    OpponentCheckpoint,
    file_sha256,
    policy_contract_sha256,
)
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.parallel_rollout import build_policy_observation_builder
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder

DECK = (
    "HogRider",
    "Musketeer",
    "IceGolem",
    "IceSpirit",
    "Skeletons",
    "Cannon",
    "Fireball",
    "Log",
)


@pytest.fixture
def setup(tmp_path):
    torch.set_num_threads(1)
    torch.manual_seed(512)
    initial = StructuredObservationBuilder(card_vocab=DECK, card_semantics_version=4)
    config = PolicyConfig(
        num_tokens=initial.spec.num_tokens,
        max_entities=32,
        public_contract_version=4,
        public_token_names=initial.token_names,
        public_observation_confidence=True,
        card_semantics_version=4,
        public_history_slots=4,
        public_seen_card_slots=8,
        canonical_lane_globals=True,
        d_model=32,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=48,
    )
    builder = build_policy_observation_builder(
        config,
        decks_path="decks.json",
        card_vocab=DECK,
        token_names=initial.token_names,
    )
    model = ClasherPolicy(config, builder.card_stat_features).eval()
    env = SelfPlayBattleEnv(
        public_contract_version=4, decision_interval_ticks=5, seed=5
    )
    env._structured_obs_builder = builder
    env.reset(ordered_decks=(DECK, DECK))
    data_sha = file_sha256(env.battle.card_loader.data_file)
    checkpoint = tmp_path / "initial.pt"
    torch.save(
        {
            "format_version": 2,
            "model_config": config.to_dict(),
            "model_state_dict": model.state_dict(),
            "token_names": builder.token_names,
            "gamedata_sha256": data_sha,
        },
        checkpoint,
    )
    entry = OpponentCheckpoint(path=str(checkpoint), sha256=file_sha256(checkpoint))
    pool = CouncilOpponentPool(
        generation=0,
        phase="initial",
        gamedata_sha256=data_sha,
        policy_contract_sha256=policy_contract_sha256(config),
        initial=(entry,),
    )
    path = tmp_path / "pool.json"
    path.write_text(pool.model_dump_json())
    bot = CouncilLeagueOpponent(
        builder=builder,
        learner_model=model,
        pool_path=path,
        seed=19,
        assignment_log=tmp_path / "assignments.jsonl",
    )
    return env, builder, model, bot, pool, path


def act(env, bot):
    mask = env.get_action_mask(1)
    action = bot.select_action(env, 1, action_mask=mask)
    assert mask[action]
    return action


def test_current_opponent_is_frozen_until_match_boundary_and_rng_isolated(setup):
    env, _, model, bot, pool, path = setup
    path.write_text(pool.model_copy(update={"phase": "league"}).model_dump_json())
    with patch.object(bot.rng, "random", return_value=0.99):
        rng_before = torch.get_rng_state().clone()
        first_action = act(env, bot)
        torch.testing.assert_close(torch.get_rng_state(), rng_before, rtol=0, atol=0)
        episode = bot._episodes[env]
        assert episode.assignment["kind"] == "current"
        original = {
            key: value.clone() for key, value in episode.model.state_dict().items()
        }
        initial_assignment = bot.assignment_for(env)
        assert act(env, bot) == first_action  # A duplicate frame cannot advance memory.
        assert episode.decisions == 1
        with torch.no_grad():
            next(model.parameters()).add_(0.25)
        bot.set_context(policy_version=1, learner_decisions=128)
        path.write_text(
            pool.model_copy(
                update={"generation": 2, "phase": "league"}
            ).model_dump_json()
        )
        env.step({0: env.action_space.no_op_action, 1: first_action})
        act(env, bot)
        assert bot.assignment_for(env) == initial_assignment
        for key, value in episode.model.state_dict().items():
            torch.testing.assert_close(value, original[key], rtol=0, atol=0)
        env.reset(ordered_decks=(DECK, DECK))
        act(env, bot)
        assert bot.assignment_for(env)["pool_generation"] == 2
        assert bot.assignment_for(env)["kind"] == "current"
        assert (
            bot.assignment_for(env)["checkpoint_sha256"]
            != initial_assignment["checkpoint_sha256"]
        )
        assert bot._episodes[env].decisions == 1
        assert (
            bot.assignment_for(env)["assignment_id"]
            != initial_assignment["assignment_id"]
        )
    records = [
        json.loads(line)
        for line in (path.parent / "assignments.jsonl").read_text().splitlines()
    ]
    assert len(records) == 2


@pytest.mark.parametrize(
    "phase,draw,has_history,has_initial,expected,fallback",
    [
        ("initial", 0.1, False, True, "script", False),
        ("initial", 0.9, False, True, "initial", False),
        ("league", 0.1, True, True, "script", False),
        ("league", 0.3, True, True, "historical", False),
        # Initial policies count as historical opponents after the first million.
        ("league", 0.7, False, True, "historical", False),
        # Scripts fill the historical share only when no frozen policy exists.
        ("league", 0.7, False, False, "script", True),
        ("league", 0.9, True, True, "current", False),
    ],
)
def test_declared_sampling_regions_and_missing_history(
    setup, phase, draw, has_history, has_initial, expected, fallback
):
    env, _, _, bot, pool, path = setup
    pool = pool.model_copy(
        update={
            "phase": phase,
            "historical": pool.initial if has_history else (),
            "initial": pool.initial if has_initial else (),
        }
    )
    path.write_text(pool.model_dump_json())
    with patch.object(bot.rng, "random", return_value=draw):
        act(env, bot)
    assignment = bot.assignment_for(env)
    assert assignment["kind"] == expected
    assert assignment["history_fallback_to_script"] == fallback


def test_checkpoint_and_data_tampering_fail_at_new_match(setup):
    env, _, _, bot, pool, path = setup
    path.write_text(
        pool.model_copy(update={"gamedata_sha256": "0" * 64}).model_dump_json()
    )
    with pytest.raises(ValueError, match="data differs"):
        act(env, bot)
    path.write_text(pool.model_dump_json())
    Path(pool.initial[0].path).write_bytes(b"changed")
    with (
        patch.object(bot.rng, "random", return_value=0.9),
        pytest.raises(ValueError, match="checkpoint changed"),
    ):
        act(env, bot)


def test_current_snapshot_contract_and_context_guard(setup):
    env, _, _, bot, pool, path = setup
    bot.set_context(policy_version=5, learner_decisions=500)
    with pytest.raises(ValueError, match="backwards"):
        bot.set_context(policy_version=4, learner_decisions=501)
    path.write_text(
        pool.model_copy(update={"policy_contract_sha256": "0" * 64}).model_dump_json()
    )
    with pytest.raises(ValueError, match="contracts differ"):
        act(env, bot)


def test_mask_mismatch_is_not_a_tactical_fallback(setup):
    env, _, _, bot, _, _ = setup
    wrong = np.ones_like(env.get_action_mask(1))
    with pytest.raises(ValueError, match="transport mask"):
        bot.select_action(env, 1, action_mask=wrong)


def test_manifest_cannot_redefine_generation_or_initial_mixture(setup):
    env, _, _, bot, pool, path = setup
    act(env, bot)
    env.reset(ordered_decks=(DECK, DECK))
    path.write_text(pool.model_copy(update={"scripts": ("defense",)}).model_dump_json())
    with pytest.raises(ValueError, match="without a new generation"):
        act(env, bot)
    path.write_text(
        pool.model_copy(
            update={"generation": 1, "scripts": ("defense",)}
        ).model_dump_json()
    )
    with pytest.raises(ValueError, match="must remain frozen"):
        act(env, bot)


def test_league_history_share_includes_initial_policies(setup, tmp_path):
    from collections import Counter

    from clasher.rl.council_opponents import league_history_pool

    env, _, _, bot, pool, path = setup
    payload = torch.load(pool.initial[0].path, weights_only=False)
    retained = tmp_path / "policy_decisions_001000000.pt"
    torch.save(payload | {"total_transitions": 1_000_000}, retained)
    retained_entry = OpponentCheckpoint(path=str(retained), sha256=file_sha256(retained))
    league = pool.model_copy(
        update={"phase": "league", "generation": 1_000_000, "historical": (retained_entry,)}
    )
    path.write_text(league.model_dump_json())
    assert league_history_pool(league) == (pool.initial[0], retained_entry)
    # Re-listing an initial file as retained history must not double its weight.
    duplicate = league.model_copy(update={"historical": (retained_entry, pool.initial[0])})
    assert league_history_pool(duplicate) == (pool.initial[0], retained_entry)
    seen = Counter()
    with patch.object(bot.rng, "random", return_value=0.5):  # historical region
        for _ in range(24):
            env.reset(ordered_decks=(DECK, DECK))
            act(env, bot)
            assignment = bot.assignment_for(env)
            assert assignment["kind"] == "historical"
            assert not assignment["history_fallback_to_script"]
            seen[assignment["checkpoint_sha256"]] += 1
    assert set(seen) == {pool.initial[0].sha256, retained_entry.sha256}


def test_finished_match_outcome_is_logged_against_its_assignment(setup):
    env, _, _, bot, _, path = setup
    with patch.object(bot.rng, "random", return_value=0.1):
        act(env, bot)
    assignment = bot.assignment_for(env)
    env.battle.game_over = True
    env.battle.winner = 0
    record = bot.record_outcome(env, 0)
    assert record["learner_result"] == "win"
    assert record["kind"] == assignment["kind"] == "script"
    assert record["assignment_id"] == assignment["assignment_id"]
    assert bot.record_outcome(env, 0) is None  # one record per match
    lines = (path.parent / "outcomes.jsonl").read_text().splitlines()
    assert [json.loads(line)["learner_result"] for line in lines] == ["win"]
