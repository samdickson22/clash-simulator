from collections import deque

import numpy as np
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.model import ClasherPolicy, PolicyConfig, PolicyInputs
from clasher.rl.parallel_rollout import concatenate_rollouts
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import (
    _stack_step_inputs,
    collect_rollout,
    collect_rollout_stationary_opponents,
    compute_gae,
    ppo_update,
)


def _tiny_model(builder: StructuredObservationBuilder) -> ClasherPolicy:
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
    )


def test_structured_actor_excludes_hidden_enemy_cards_and_elixir():
    battle = BattleState()
    builder = StructuredObservationBuilder(
        card_vocab=["Knight", "Archers", "Giant", "Fireball", "Golem", "Zap"],
        max_entities=32,
    )
    before = builder.build(battle, 0)
    battle.players[1].elixir = 9.75
    battle.players[1].hand = ["Golem", "Zap", "Fireball", "Giant"]
    battle.players[1].cycle_queue = deque(["Archers", "Knight"])
    after = builder.build(battle, 0)

    np.testing.assert_array_equal(before.entity_ids, after.entity_ids)
    np.testing.assert_array_equal(before.entity_features, after.entity_features)
    np.testing.assert_array_equal(before.hand_ids, after.hand_ids)
    np.testing.assert_array_equal(before.global_features, after.global_features)
    assert not np.array_equal(before.critic_card_ids, after.critic_card_ids)
    assert before.critic_global_features[-2] != after.critic_global_features[-2]


def test_structured_entities_do_not_overwrite_same_position():
    battle = BattleState()
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    battle._spawn_troop(Position(9.0, 10.0), 0, stats)
    battle._spawn_troop(Position(9.0, 10.0), 0, stats)
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=32)
    observation = builder.build(battle, 0)

    knight_id = builder.token_id("Knight")
    matching = observation.entity_mask & (observation.entity_ids == knight_id)
    assert int(matching.sum()) == 2
    np.testing.assert_array_equal(
        observation.entity_features[matching, :2],
        np.asarray([[0.5, 10.0 / 32.0], [0.5, 10.0 / 32.0]], dtype=np.float32),
    )


def test_hierarchical_joint_distribution_is_legal_and_not_tile_count_biased():
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    model = _tiny_model(builder)
    type_logits = torch.zeros((1, 1, 6))
    location_logits = torch.zeros((1, 1, 4, 576))
    mask = torch.zeros((1, 1, 2306), dtype=torch.bool)
    mask[..., 0] = True
    mask[..., 576 : 576 + 100] = True
    mask[..., 2304] = True

    joint = model._joint_action_logits(type_logits, location_logits, mask)
    probabilities = torch.distributions.Categorical(logits=joint).probs
    assert torch.all(probabilities.masked_select(~mask) == 0)
    torch.testing.assert_close(probabilities.sum(-1), torch.ones((1, 1)))
    slot_zero = probabilities[..., :576].sum(-1)
    slot_one = probabilities[..., 576:1152].sum(-1)
    no_op = probabilities[..., 2304]
    torch.testing.assert_close(slot_zero, slot_one)
    torch.testing.assert_close(slot_zero, no_op)


def test_recurrent_state_resets_inside_a_sequence():
    env = SelfPlayBattleEnv(seed=11, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    env._structured_obs_builder = builder
    model = _tiny_model(builder).eval()
    observation = builder.build(env.battle, 0)
    mask = env.get_action_mask(0)[None, :]
    single = _stack_step_inputs(
        [observation],
        mask,
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    doubled = PolicyInputs(
        **{
            name: torch.cat([getattr(single, name), getattr(single, name)], dim=1)
            for name in (
                "entity_ids",
                "entity_features",
                "entity_mask",
                "hand_ids",
                "global_features",
                "action_mask",
                "previous_actions",
                "previous_rewards",
                "episode_starts",
                "critic_entity_ids",
                "critic_entity_features",
                "critic_entity_mask",
                "critic_card_ids",
                "critic_global_features",
            )
        }
    )
    with torch.no_grad():
        standalone = model(single).next_state
        sequence = model(doubled).next_state
    torch.testing.assert_close(sequence[0], standalone[0])
    torch.testing.assert_close(sequence[1], standalone[1])


def test_recurrent_rollout_and_ppo_update_smoke():
    env = SelfPlayBattleEnv(seed=17, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    env._structured_obs_builder = builder
    model = _tiny_model(builder)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    state = model.initial_state(2)
    previous_actions = np.full((2,), env.action_space.no_op_action, dtype=np.int64)
    previous_rewards = np.zeros((2,), dtype=np.float32)
    starts = np.ones((2,), dtype=np.bool_)

    rollout, _, _, _, _ = collect_rollout(
        envs=[env],
        builder=builder,
        model=model,
        device=torch.device("cpu"),
        rollout_steps=2,
        recurrent_state=state,
        previous_actions=previous_actions,
        previous_rewards=previous_rewards,
        episode_starts=starts,
        quiet_engine=True,
    )
    advantages, returns = compute_gae(rollout, gamma=0.995, gae_lambda=0.95)
    stats = ppo_update(
        model=model,
        optimizer=optimizer,
        rollout=rollout,
        advantages=advantages,
        returns=returns,
        device=torch.device("cpu"),
        epochs=1,
        sequence_batch_size=1,
        clip_ratio=0.2,
        value_coef=0.5,
        entropy_coef=0.01,
        hand_aux_coef=0.02,
        elixir_aux_coef=0.05,
        target_kl=0.0,
    )
    assert rollout.transitions == 4
    assert np.isfinite(advantages).all()
    assert all(np.isfinite(value) for value in stats.values())

    combined = concatenate_rollouts([rollout, rollout])
    assert combined.num_sequences == 2 * rollout.num_sequences
    assert combined.transitions == 2 * rollout.transitions
    assert combined.episodes_finished == 2 * rollout.episodes_finished
    np.testing.assert_array_equal(combined.actions[:2], rollout.actions)
    np.testing.assert_array_equal(combined.actions[2:], rollout.actions)


def test_random_opponent_rollout_only_trains_balanced_learner_seats():
    envs = [SelfPlayBattleEnv(seed=31 + index, max_ticks=128) for index in range(2)]
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    for env in envs:
        env._structured_obs_builder = builder
        env.reset()
    model = _tiny_model(builder)
    state = model.initial_state(2)
    no_op = envs[0].action_space.no_op_action

    rollout, next_state, previous_actions, previous_rewards, starts, *_ = (
        collect_rollout_stationary_opponents(
            envs=envs,
            learner_players=(0, 1),
            builder=builder,
            model=model,
            device=torch.device("cpu"),
            rollout_steps=2,
            recurrent_state=state,
            previous_actions=np.full((2,), no_op, dtype=np.int64),
            previous_rewards=np.zeros((2,), dtype=np.float32),
            episode_starts=np.ones((2,), dtype=np.bool_),
            opponent_model=None,
            opponent_recurrent_state=None,
            opponent_previous_actions=np.full((2,), no_op, dtype=np.int64),
            opponent_previous_rewards=np.zeros((2,), dtype=np.float32),
            opponent_episode_starts=np.ones((2,), dtype=np.bool_),
            quiet_engine=True,
        )
    )

    assert rollout.num_sequences == 2
    assert rollout.transitions == 4
    assert rollout.actions.shape == (2, 2)
    assert rollout.bootstrap_values.shape == (2,)
    assert next_state[0].shape == (2, model.config.memory_size)
    assert previous_actions.shape == previous_rewards.shape == starts.shape == (2,)
    assert np.all(
        np.take_along_axis(
            rollout.action_masks,
            rollout.actions[..., None],
            axis=-1,
        )
    )
