import hashlib

import numpy as np
import pytest
import torch

from clasher.rl.dagger_behavior import (
    actor_policy_action,
    behavior_player_for_episode,
    parse_stationary_opponent,
    prepare_behavior_decision,
    stationary_action,
)
from clasher.rl.eval import LoadedPolicy, _policy_action
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder


def _tiny_policy(builder: StructuredObservationBuilder) -> ClasherPolicy:
    return ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=48,
        ),
        builder.card_stat_features,
    ).eval()


@pytest.mark.parametrize("player_id", [0, 1])
def test_actor_only_observation_matches_full_public_payload(player_id: int):
    env = SelfPlayBattleEnv(seed=2301, decision_interval_ticks=2, max_ticks=64)
    env.reset(seed=2301)
    assert env.battle is not None
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=32)

    full = builder.build(env.battle, player_id)
    actor = builder.build_actor(env.battle, player_id)

    for name in (
        "entity_ids",
        "entity_features",
        "entity_mask",
        "hand_ids",
        "global_features",
    ):
        np.testing.assert_array_equal(getattr(actor, name), getattr(full, name))


def test_prepared_stationary_decision_builds_one_observation_and_each_mask_once(
    monkeypatch,
):
    env = SelfPlayBattleEnv(seed=2301, max_ticks=64)
    env.reset(seed=2301)
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=32)
    build_calls: list[int] = []
    mask_calls: list[int] = []
    original_build = builder.build_actor
    original_mask = env.get_action_mask

    def counted_build(battle, player_id):
        build_calls.append(player_id)
        return original_build(battle, player_id)

    def counted_mask(player_id):
        mask_calls.append(player_id)
        return original_mask(player_id)

    monkeypatch.setattr(builder, "build_actor", counted_build)
    monkeypatch.setattr(env, "get_action_mask", counted_mask)

    prepared = prepare_behavior_decision(
        env,
        builder,
        observation_players=(1,),
    )

    assert set(prepared.observations) == {1}
    assert set(prepared.action_masks) == {0, 1}
    assert build_calls == [1]
    assert mask_calls == [0, 1]


def test_actor_only_policy_action_matches_full_deterministic_action_and_state():
    torch.manual_seed(91)
    env = SelfPlayBattleEnv(seed=2301, max_ticks=64)
    env.reset(seed=2301)
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=32)
    model = _tiny_policy(builder)
    loaded = LoadedPolicy(model=model, builder=builder, checkpoint={})
    state = model.initial_state(1)

    expected_action, expected_state, expected_mask = _policy_action(
        loaded,
        env,
        0,
        state=state,
        previous_action=env.action_space.no_op_action,
        previous_reward=0.0,
        episode_start=True,
        deterministic=True,
        device=torch.device("cpu"),
    )
    assert env.battle is not None
    actual_action, actual_state = actor_policy_action(
        model,
        builder.build_actor(env.battle, 0),
        expected_mask,
        state=state,
        previous_action=env.action_space.no_op_action,
        previous_reward=0.0,
        episode_start=True,
        deterministic=True,
        device=torch.device("cpu"),
    )

    assert actual_action == expected_action
    torch.testing.assert_close(actual_state[0], expected_state[0], rtol=0, atol=0)
    torch.testing.assert_close(actual_state[1], expected_state[1], rtol=0, atol=0)


def test_stationary_random_and_strategy_reuse_masks_exactly():
    env = SelfPlayBattleEnv(seed=2301, max_ticks=64)
    env.reset(seed=2301)
    mask = env.get_action_mask(1)
    expected_rng = np.random.default_rng(9173)
    actual_rng = np.random.default_rng(9173)
    expected_random = int(expected_rng.choice(np.flatnonzero(mask)))

    assert stationary_action(
        env,
        1,
        mask,
        rng=actual_rng,
        strategy_bot=parse_stationary_opponent("random"),
    ) == expected_random
    strategy = parse_stationary_opponent("strategy:balanced")
    assert strategy is not None
    assert stationary_action(
        env,
        1,
        mask,
        rng=np.random.default_rng(0),
        strategy_bot=strategy,
    ) == strategy.select_action(env, 1, action_mask=mask)


def _behavior_trace_digest(*, engine_fast_path: str, optimized: bool) -> tuple[str, int]:
    torch.manual_seed(91)
    env = SelfPlayBattleEnv(
        seed=2301,
        decision_interval_ticks=2,
        max_ticks=64,
        engine_fast_path=engine_fast_path,
    )
    env.reset(seed=2301)
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=32)
    model = _tiny_policy(builder)
    loaded = LoadedPolicy(model=model, builder=builder, checkpoint={})
    state = model.initial_state(1)
    previous_action = env.action_space.no_op_action
    previous_reward = 0.0
    episode_start = True
    opponent_rng = np.random.default_rng(9173)
    hasher = hashlib.sha256()

    for _ in range(4):
        if optimized:
            prepared = prepare_behavior_decision(
                env,
                builder,
                observation_players=(0,),
            )
            learner_action, state = actor_policy_action(
                model,
                prepared.observations[0],
                prepared.action_masks[0],
                state=state,
                previous_action=previous_action,
                previous_reward=previous_reward,
                episode_start=episode_start,
                deterministic=True,
                device=torch.device("cpu"),
            )
            masks = prepared.action_masks
        else:
            learner_action, state, learner_mask = _policy_action(
                loaded,
                env,
                0,
                state=state,
                previous_action=previous_action,
                previous_reward=previous_reward,
                episode_start=episode_start,
                deterministic=True,
                device=torch.device("cpu"),
            )
            masks = {0: learner_mask, 1: env.get_action_mask(1)}
        opponent_action = stationary_action(
            env,
            1,
            masks[1],
            rng=opponent_rng,
            strategy_bot=None,
        )
        rewards, done, _ = env.step(
            {0: learner_action, 1: opponent_action},
            pre_action_masks=masks if optimized else None,
        )
        assert env.battle is not None
        hasher.update(np.ascontiguousarray(masks[0]).tobytes())
        hasher.update(np.ascontiguousarray(masks[1]).tobytes())
        hasher.update(
            np.asarray(
                [
                    learner_action,
                    opponent_action,
                    env.battle.tick,
                    len(env.battle.entities),
                    done,
                ],
                dtype=np.int64,
            ).tobytes()
        )
        hasher.update(np.asarray([rewards[0], rewards[1]], dtype=np.float64).tobytes())
        hasher.update(state[0].detach().numpy().tobytes())
        hasher.update(state[1].detach().numpy().tobytes())
        previous_action = learner_action
        previous_reward = float(rewards[0])
        episode_start = False

    return hasher.hexdigest(), int(env.fast_path_metrics()["mask_shadow_mismatches"])


def test_precomputed_masks_preserve_scalar_shadow_and_fast_fixed_seed_hashes():
    digests: dict[str, str] = {}
    for engine_fast_path in ("off", "shadow", "on"):
        baseline, baseline_mismatches = _behavior_trace_digest(
            engine_fast_path=engine_fast_path,
            optimized=False,
        )
        optimized, optimized_mismatches = _behavior_trace_digest(
            engine_fast_path=engine_fast_path,
            optimized=True,
        )
        assert optimized == baseline
        assert baseline_mismatches == optimized_mismatches == 0
        digests[engine_fast_path] = optimized

    assert len(set(digests.values())) == 1
    assert len(digests["on"]) == 64


def test_behavior_seats_balance_across_shards_and_episodes():
    assert [behavior_player_for_episode(0, episode) for episode in range(4)] == [
        0,
        1,
        0,
        1,
    ]
    assert [behavior_player_for_episode(1, episode) for episode in range(4)] == [
        1,
        0,
        1,
        0,
    ]
    with pytest.raises(ValueError, match="non-negative"):
        behavior_player_for_episode(-1, 0)


def test_stationary_opponent_parser_rejects_unknown_modes():
    with pytest.raises(ValueError, match="unknown stationary opponent"):
        parse_stationary_opponent("strategy:hog-rider")
