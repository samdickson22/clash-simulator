"""M0 transport and inference checks on an untrained scalar policy."""

import pickle

import numpy as np
import torch

from clasher.rl.eval import _policy_step, load_policy_checkpoint
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.parallel_rollout import (
    build_policy_observation_builder,
    concatenate_rollouts,
)
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.train_recurrent import (
    _index_policy_inputs,
    _sequence_inputs,
    collect_rollout,
)

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


def setup():
    torch.set_num_threads(1)
    torch.manual_seed(1342)
    from clasher.rl.structured_obs import StructuredObservationBuilder

    initial = StructuredObservationBuilder(
        card_vocab=DECK, max_entities=32, card_semantics_version=4
    )
    config = PolicyConfig(
        num_tokens=initial.spec.num_tokens,
        max_entities=32,
        public_contract_version=4,
        public_token_names=initial.token_names,
        public_observation_confidence=True,
        card_semantics_version=4,
        canonical_lane_globals=True,
        public_history_slots=4,
        public_seen_card_slots=8,
        d_model=32,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=48,
    )
    builder = build_policy_observation_builder(
        config,
        decks_path="decks.json",
        token_names=initial.token_names,
        card_vocab=DECK,
    )
    model = ClasherPolicy(config, builder.card_stat_features).eval()
    levels = (
        {name: 10 + i % 3 for i, name in enumerate(DECK)},
        {name: 12 - i % 3 for i, name in enumerate(DECK)},
    )
    env = SelfPlayBattleEnv(
        public_contract_version=4,
        decision_interval_ticks=5,
        max_ticks=100,
        seed=13,
        card_levels=levels,
        tower_levels=(10, 12),
    )
    env._structured_obs_builder = builder
    env.reset(ordered_decks=(DECK, DECK))
    return builder, model, env


def collect(builder, model, env):
    return collect_rollout(
        envs=[env],
        builder=builder,
        model=model,
        device=torch.device("cpu"),
        rollout_steps=3,
        recurrent_state=model.initial_state(2),
        previous_actions=np.full(2, env.action_space.no_op_action),
        previous_rewards=np.array([9, -9], dtype=np.float32),
        episode_starts=np.ones(2, dtype=bool),
        quiet_engine=True,
    )[0]


def test_actual_levels_survive_scalar_transport_and_minibatch():
    builder, model, env = setup()
    expected = [env.get_structured_observation(seat) for seat in (0, 1)]
    batch = collect(builder, model, env)
    # multiprocessing.Queue uses pickle; exercising the actual ragged payload
    # also verifies that current-weight history snapshots survive serialization.
    restored = pickle.loads(pickle.dumps(batch))
    combined = concatenate_rollouts([restored, restored])
    inputs = _sequence_inputs(combined, slice(None), torch.device("cpu"))
    selected = _index_policy_inputs(inputs, torch.tensor([2, 1]))
    for name in (
        "entity_levels",
        "entity_level_confidence",
        "hand_levels",
        "hand_level_confidence",
    ):
        actual = getattr(selected, name)
        for seat in (0, 1):
            np.testing.assert_array_equal(
                actual[seat, 0].numpy(), getattr(expected[seat], name)
            )
    assert set(batch.hand_levels[0, 0]) == {10, 11, 12}
    assert np.all(batch.previous_rewards == 0)
    assert batch.own_last_play_ids is not None
    assert combined.recurrent_prefixes == (None,) * 4


def test_checkpoint_eval_builder_and_public_inference_preserve_contract(tmp_path):
    builder, model, env = setup()
    checkpoint = tmp_path / "untrained.pt"
    torch.save(
        {
            "format_version": 2,
            "model_config": model.config.to_dict(),
            "token_names": builder.token_names,
            "model_state_dict": model.state_dict(),
        },
        checkpoint,
    )
    loaded = load_policy_checkpoint(
        checkpoint, device=torch.device("cpu"), decks_path="decks.json"
    )
    assert loaded.builder.spec.public_entity_levels
    assert loaded.builder.spec.public_hand_levels
    action, _state, mask, output = _policy_step(
        loaded,
        env,
        0,
        state=model.initial_state(1),
        previous_action=env.action_space.no_op_action,
        previous_reward=80,
        episode_start=True,
        deterministic=False,
        device=torch.device("cpu"),
    )
    assert mask[action]
    assert torch.isfinite(output.values).all()
    expected = env.get_structured_observation(0)
    assert np.all(expected.hand_level_confidence == 1)
    assert set(expected.hand_levels) == {10, 11, 12}


def test_rejected_command_is_logged_without_council_penalty():
    _, _, env = setup()
    env.reward_potential_scale = 0
    env.battle.players[0].elixir = 0
    rewards, _done, info = env.step({0: 0, 1: env.action_space.no_op_action})
    assert not info.action_success[0]
    assert rewards == {0: 0, 1: 0}


def test_real_worker_queue_preserves_levels_and_changed_weight_prefixes(tmp_path):
    import json

    from clasher.rl.parallel_rollout import ActorWorkerConfig, ParallelRolloutCollector

    builder, model, _env = setup()
    deck_path = tmp_path / "decks.json"
    deck_path.write_text(json.dumps({"decks": [{"cards": DECK}]}))
    config = ActorWorkerConfig(
        decks_path=str(deck_path),
        token_names=builder.token_names,
        model_config=model.config.to_dict(),
        decision_interval=5,
        max_ticks=100,
        mirror_match=True,
        opponent_mode="selfplay",
        opponent_pool=(),
        engine_fast_path="off",
        quiet_engine=True,
        base_seed=987,
        torch_threads=1,
        card_levels=({name: 10 for name in DECK}, {name: 12 for name in DECK}),
        tower_levels=(10, 12),
    )
    with ParallelRolloutCollector(
        num_workers=2, num_envs=2, config=config
    ) as collector:
        first = collector.collect(
            model=model, rollout_steps=2, policy_version=0, timeout=30
        )
        with torch.no_grad():
            next(model.actor_encoder.parameters()).add_(0.01)
        second = collector.collect(
            model=model, rollout_steps=2, policy_version=1, timeout=30
        )
    assert np.all(first.hand_levels[[0, 2], 0] == 10)
    assert np.all(first.hand_levels[[1, 3], 0] == 12)
    assert all(prefix.sequence_length == 2 for prefix in second.recurrent_prefixes)
    with torch.no_grad():
        output = model(
            _sequence_inputs(second, slice(None), torch.device("cpu")),
            tuple(
                torch.from_numpy(value)
                for value in (second.initial_hidden, second.initial_cell)
            ),
        )
    torch.testing.assert_close(
        output.distribution().log_prob(torch.from_numpy(second.actions)),
        torch.from_numpy(second.old_log_probs),
        atol=2e-6,
        rtol=2e-6,
    )
    from clasher.rl.rollout_audit import build_rollout_audit

    before = build_rollout_audit(second, update=2, seed=987)
    second.recurrent_prefixes[0].hand_levels[0, 0, 0] = 11
    after = build_rollout_audit(second, update=2, seed=987)
    assert before["rollout_sha256"] != after["rollout_sha256"]
    assert before["fields"]["hand_levels"] == after["fields"]["hand_levels"]


def test_collection_continuity_across_128_step_boundary():
    from dataclasses import fields

    from clasher.rl.model import PolicyInputs

    builder, model, env = setup()
    env.max_ticks = 2000
    kwargs = {
        "envs": [env],
        "builder": builder,
        "model": model,
        "device": torch.device("cpu"),
        "quiet_engine": True,
    }
    first, state, actions, rewards, starts = collect_rollout(
        **kwargs,
        rollout_steps=128,
        recurrent_state=model.initial_state(2),
        previous_actions=np.full(2, env.action_space.no_op_action),
        previous_rewards=np.zeros(2, dtype=np.float32),
        episode_starts=np.ones(2, dtype=bool),
    )
    assert first.episodes_finished == 0
    second, final_state, *_ = collect_rollout(
        **kwargs,
        rollout_steps=3,
        recurrent_state=state,
        previous_actions=actions,
        previous_rewards=rewards,
        episode_starts=starts,
    )
    one, two = (
        _sequence_inputs(batch, slice(None), torch.device("cpu"))
        for batch in (first, second)
    )
    uninterrupted = PolicyInputs(
        **{
            field.name: None
            if getattr(one, field.name) is None
            else torch.cat((getattr(one, field.name), getattr(two, field.name)), dim=1)
            for field in fields(PolicyInputs)
        }
    )
    with torch.no_grad():
        output = model(uninterrupted)
    all_actions = torch.from_numpy(
        np.concatenate((first.actions, second.actions), axis=1)
    )
    torch.testing.assert_close(
        output.distribution().log_prob(all_actions)[:, 128:],
        torch.from_numpy(second.old_log_probs),
        atol=2e-6,
        rtol=2e-6,
    )
    for actual, expected in zip(final_state, output.next_state):
        torch.testing.assert_close(actual, expected, atol=2e-6, rtol=2e-6)


def test_council_nominal_horizon_reaches_true_tiebreaker_with_terminal_score():
    from clasher.battle import STANDARD_MATCH_TICKS
    from clasher.rl.selfplay_env import resolve_match_horizon

    assert resolve_match_horizon(STANDARD_MATCH_TICKS, 1) == STANDARD_MATCH_TICKS
    assert resolve_match_horizon(100, 4) == 100
    for damaged_seat, winner in ((None, None), (0, 1), (1, 0)):
        env = SelfPlayBattleEnv(
            public_contract_version=4,
            decision_interval_ticks=5,
            seed=74,
            reward_potential_scale=0,
        )
        assert env.max_ticks == STANDARD_MATCH_TICKS + 1
        env.reset()
        battle = env.battle
        if damaged_seat is not None:
            tower = next(
                entity
                for entity in battle.entities.values()
                if battle._is_static_tower_entity(entity)
                and entity.player_id == damaged_seat
                and entity._crown_tower_slot == "left"
            )
            tower.hitpoints -= 100
        battle.tick = STANDARD_MATCH_TICKS - 1
        battle.time = battle.tick * battle.dt
        rewards, done, info = env.step(
            {0: env.action_space.no_op_action, 1: env.action_space.no_op_action}
        )
        assert done and info.terminated and not info.truncated
        assert battle.game_over and battle.tick == STANDARD_MATCH_TICKS + 1
        assert info.ticks_advanced == 2
        assert battle.winner == winner
        assert rewards == (
            {0: 0, 1: 0} if winner is None else {winner: 1, 1 - winner: -1}
        )


def test_legacy_nominal_horizon_remains_an_explicit_truncation():
    from clasher.battle import STANDARD_MATCH_TICKS

    env = SelfPlayBattleEnv(
        seed=74,
        decision_interval_ticks=5,
        reward_potential_scale=0,
        elixir_leak_penalty_scale=0,
    )
    env.reset()
    env.battle.tick = STANDARD_MATCH_TICKS - 1
    env.battle.time = env.battle.tick * env.battle.dt
    _, done, info = env.step(
        {0: env.action_space.no_op_action, 1: env.action_space.no_op_action}
    )
    assert done and info.truncated and not info.terminated
    assert env.battle.tick == STANDARD_MATCH_TICKS and not env.battle.game_over


def test_standalone_council_evaluation_scores_nominal_clock_winner(monkeypatch):
    from pathlib import Path

    from clasher.battle import STANDARD_MATCH_TICKS
    from clasher.rl import eval as evaluation
    from clasher.rl.eval import LoadedPolicy

    builder, model, _ = setup()
    original_reset = SelfPlayBattleEnv.reset
    original_policy_step = evaluation._policy_step

    def reset_near_deadline(env, *args, **kwargs):
        original_reset(env, *args, **kwargs)
        battle = env.battle
        tower = next(
            entity
            for entity in battle.entities.values()
            if battle._is_static_tower_entity(entity)
            and entity.player_id == 1
            and entity._crown_tower_slot == "left"
        )
        tower.hitpoints -= 100
        battle.tick = STANDARD_MATCH_TICKS - 1
        battle.time = battle.tick * battle.dt

    def policy_wait(loaded, env, *args, **kwargs):
        _, state, mask, output = original_policy_step(loaded, env, *args, **kwargs)
        return env.action_space.no_op_action, state, mask, output

    monkeypatch.setattr(SelfPlayBattleEnv, "reset", reset_near_deadline)
    monkeypatch.setattr(evaluation, "_policy_step", policy_wait)
    records = []
    metrics = evaluation.evaluate(
        candidate=LoadedPolicy(model, builder, {}),
        decks_path=Path("decks.json"),
        games=1,
        seed=91,
        decision_interval=5,
        max_ticks=STANDARD_MATCH_TICKS,
        opponent_mode="noop",
        opponent=None,
        deterministic=False,
        quiet_engine=True,
        device=torch.device("cpu"),
        game_records=records,
    )
    assert metrics["wins"] == 1 and metrics["draws"] == 0
    assert metrics["score_rate"] == 1
    assert records[0]["ticks"] == STANDARD_MATCH_TICKS + 1
    assert records[0]["outcome"] == "win"
