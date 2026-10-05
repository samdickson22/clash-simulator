"""Learner-side batched inference: identical transitions and learning math.

The pilot's throughput path (admission-scope decision v1) moves the policy
forward out of the actor processes into the learner. These tests pin that it
changes nothing an admitted component decides:

* in one process it reproduces the admitted ``collect_rollout_stationary_opponents``
  bit for bit (same observations, masks, actions, log-probs, values, rewards,
  truncation bootstraps, recurrent prefixes and carry);
* the same environments split across actor processes give bit-identical
  rollouts (the partition does not matter);
* PPO losses and gradients on those rollouts are identical, batched inference
  equals per-environment inference within float tolerance, and an MPS learner
  matches the CPU learner within float tolerance.
"""

from __future__ import annotations

import copy
import json
from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest
import torch

from clasher.rl.council_opponents import (
    CouncilLeagueOpponent,
    CouncilOpponentPool,
    OpponentCheckpoint,
    policy_contract_sha256,
)
from clasher.rl.council_pilot import file_sha256, load_pilot_config
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.parallel_rollout import (
    ActorWorkerConfig,
    BatchedInferenceCollector,
    EnvSlot,
    LocalSlotBackend,
    OpponentSpec,
    ProcessSlotBackend,
    build_actor_environment,
    build_environment_opponents,
    build_policy_observation_builder,
)
from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS
from clasher.rl.train_recurrent import (
    RolloutBatch,
    _sequence_inputs,
    collect_rollout_stationary_opponents,
    compute_gae,
    ppo_update,
)

CONFIG = Path("configs/council-pilot-local.toml")
MAX_TICKS = 150  # short horizon: several truncations and resets per rollout


def _policy_config(builder) -> PolicyConfig:
    return PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=32,
        public_contract_version=4,
        public_token_names=builder.token_names,
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
        memory_kind="lstm",
        deterministic_hierarchy="slot",
    )


@pytest.fixture(scope="module")
def setup(tmp_path_factory):
    torch.set_num_threads(1)
    tmp = tmp_path_factory.mktemp("learner-inference")
    pilot = load_pilot_config(CONFIG)
    from clasher.rl.structured_obs import StructuredObservationBuilder

    probe = StructuredObservationBuilder(
        card_vocab=sorted(SUPPORTED_CARDS),
        max_entities=32,
        card_semantics_version=4,
        public_history_slots=4,
        public_seen_card_slots=8,
        public_entity_levels=True,
        public_hand_levels=True,
        canonical_lane_globals=True,
    )
    policy_config = _policy_config(probe)
    torch.manual_seed(7)
    model = ClasherPolicy(policy_config, probe.card_stat_features).eval()
    checkpoint = tmp / "initial.pt"
    data_sha = file_sha256(probe.loader.data_file)
    torch.save(
        {
            "format_version": 2,
            "model_config": policy_config.to_dict(),
            "model_state_dict": model.state_dict(),
            "token_names": probe.token_names,
            "gamedata_sha256": data_sha,
        },
        checkpoint,
    )
    pool = CouncilOpponentPool(
        generation=0,
        phase="initial",
        gamedata_sha256=data_sha,
        policy_contract_sha256=policy_contract_sha256(policy_config),
        initial=(
            OpponentCheckpoint(path=str(checkpoint), sha256=file_sha256(checkpoint)),
        ),
    )

    def worker_config(pool_dir: Path) -> ActorWorkerConfig:
        pool_dir.mkdir(parents=True, exist_ok=True)
        pool_path = pool_dir / "pool.json"
        if not pool_path.exists():
            pool_path.write_text(pool.model_dump_json())
        return ActorWorkerConfig(
            decks_path=pilot.training_decks_path,
            token_names=probe.token_names,
            model_config=policy_config.to_dict(),
            decision_interval=5,
            max_ticks=MAX_TICKS,
            mirror_match=False,
            opponent_mode="strategy",
            opponent_pool=(OpponentSpec(kind="strategy", strategy="balanced"),),
            engine_fast_path="off",
            quiet_engine=True,
            base_seed=2901,
            torch_threads=1,
            sampling_decks_path=pilot.training_decks_path,
            learner_sampling_decks_path=pilot.training_decks_path,
            opponent_sampling_decks_path=pilot.training_decks_path,
            reward_potential_scale=0.05,
            reward_shaping_gamma=1.0,
            elixir_leak_penalty_scale=0.0,
            council_opponent_pool=str(pool_path),
        )

    return {
        "tmp": tmp,
        "model": model,
        "policy_config": policy_config,
        "worker_config": worker_config,
    }


def _local_slots(config: ActorWorkerConfig, num_envs: int, model, *, shared_opponent):
    policy_config = PolicyConfig.from_dict(config.model_config)
    builder = build_policy_observation_builder(
        policy_config, decks_path=config.decks_path, token_names=config.token_names
    )
    envs = [
        build_actor_environment(config, index, policy_config, builder)
        for index in range(num_envs)
    ]
    if shared_opponent:
        opponent = CouncilLeagueOpponent(
            builder=builder,
            learner_model=model,
            pool_path=config.council_opponent_pool,
            seed=config.base_seed,
            assignment_log=Path(config.council_opponent_pool).parent
            / "worker-0-assignments.jsonl",
        )
        opponents = [("bot", opponent)] * num_envs
    else:
        opponents = build_environment_opponents(
            config, tuple(range(num_envs)), builder=builder, learner_model=model
        )
    slots = [
        EnvSlot(
            env_index=index,
            env=env,
            learner_player=index % 2,
            opponent_kind=kind,
            opponent=opponent,
        )
        for index, (env, (kind, opponent)) in enumerate(zip(envs, opponents))
    ]
    return builder, envs, slots


def _assert_rollouts_equal(left: RolloutBatch, right: RolloutBatch) -> None:
    for field in fields(RolloutBatch):
        a, b = getattr(left, field.name), getattr(right, field.name)
        if field.name == "recurrent_prefixes":
            assert (a is None) == (b is None)
            if a is None:
                continue
            assert len(a) == len(b)
            for prefix_a, prefix_b in zip(a, b):
                assert (prefix_a is None) == (prefix_b is None)
                if prefix_a is None:
                    continue
                for item in fields(prefix_a):
                    x, y = getattr(prefix_a, item.name), getattr(prefix_b, item.name)
                    assert (x is None) == (y is None), item.name
                    if x is not None:
                        assert torch.equal(x, y), item.name
        elif isinstance(a, np.ndarray):
            assert a.shape == b.shape, field.name
            assert np.array_equal(a, b), field.name
        else:
            assert a == b, field.name


def _collect_admitted(setup, config, num_envs, chunks, steps):
    """The admitted single-process collector (reference path)."""
    model = copy.deepcopy(setup["model"])
    builder, envs, slots = _local_slots(config, num_envs, model, shared_opponent=True)
    opponent = slots[0].opponent
    agents = num_envs
    no_op = model.num_actions - 2
    carry = (
        model.initial_state(agents),
        np.full((agents,), no_op, dtype=np.int64),
        np.zeros((agents,), dtype=np.float32),
        np.ones((agents,), dtype=np.bool_),
    )
    opponent_carry = (
        np.full((agents,), no_op, dtype=np.int64),
        np.zeros((agents,), dtype=np.float32),
        np.ones((agents,), dtype=np.bool_),
    )
    torch.manual_seed(11)
    rollouts = []
    for chunk in range(chunks):
        opponent.set_context(policy_version=chunk, learner_decisions=chunk * steps)
        for env in envs:
            env.set_learner_decisions(chunk * steps)
        result = collect_rollout_stationary_opponents(
            envs=envs,
            learner_players=tuple(index % 2 for index in range(num_envs)),
            builder=builder,
            model=model,
            device=torch.device("cpu"),
            rollout_steps=steps,
            recurrent_state=carry[0],
            previous_actions=carry[1],
            previous_rewards=carry[2],
            episode_starts=carry[3],
            opponent_model=None,
            opponent_recurrent_state=None,
            opponent_previous_actions=opponent_carry[0],
            opponent_previous_rewards=opponent_carry[1],
            opponent_episode_starts=opponent_carry[2],
            quiet_engine=True,
            opponent_bot=opponent,
        )
        rollouts.append(result[0])
        carry = result[1:5]
        opponent_carry = result[6:9]
    return rollouts, carry


def _collect_learner(setup, backend, builder, chunks, steps):
    model = copy.deepcopy(setup["model"])
    collector = BatchedInferenceCollector(backend, builder=builder)
    torch.manual_seed(11)
    rollouts = [
        collector.collect(
            model=model,
            rollout_steps=steps,
            policy_version=chunk,
            learner_decisions=chunk * steps,
        )
        for chunk in range(chunks)
    ]
    carry = collector._carry
    collector.close()
    return rollouts, carry


def test_learner_inference_reproduces_admitted_collector_bit_for_bit(setup):
    chunks, steps, num_envs = 3, 24, 4
    reference, reference_carry = _collect_admitted(
        setup, setup["worker_config"](setup["tmp"] / "admitted"), num_envs, chunks, steps
    )
    config = setup["worker_config"](setup["tmp"] / "learner-local-shared")
    model = copy.deepcopy(setup["model"])
    builder, _, slots = _local_slots(config, num_envs, model, shared_opponent=True)
    candidate, carry = _collect_learner(
        setup, LocalSlotBackend(slots), builder, chunks, steps
    )
    assert sum(rollout.episodes_finished for rollout in reference) >= num_envs
    assert any(
        np.any(rollout.truncation_bootstrap_values != 0) for rollout in reference
    )
    assert any(
        prefix is not None for prefix in reference[-1].recurrent_prefixes
    )
    for left, right in zip(reference, candidate):
        _assert_rollouts_equal(left, right)
    assert torch.equal(reference_carry[0][0], carry["recurrent_state"][0])
    assert torch.equal(reference_carry[0][1], carry["recurrent_state"][1])
    for index, name in enumerate(
        ("previous_actions", "previous_rewards", "episode_starts"), start=1
    ):
        assert np.array_equal(reference_carry[index], carry[name]), name
    admitted_log = setup["tmp"] / "admitted" / "worker-0-assignments.jsonl"
    learner_log = setup["tmp"] / "learner-local-shared" / "worker-0-assignments.jsonl"
    strip = lambda path: [  # noqa: E731
        {k: v for k, v in json.loads(line).items() if k != "pool_sha256"}
        for line in path.read_text().splitlines()
    ]
    assert strip(admitted_log) == strip(learner_log)


@pytest.mark.parametrize("workers", [2, 4])
def test_environment_partition_does_not_change_trajectories(setup, workers):
    chunks, steps, num_envs = 2, 20, 4
    local_config = setup["worker_config"](setup["tmp"] / f"partition-local-{workers}")
    model = copy.deepcopy(setup["model"])
    builder, _, slots = _local_slots(local_config, num_envs, model, shared_opponent=False)
    local, local_carry = _collect_learner(
        setup, LocalSlotBackend(slots), builder, chunks, steps
    )
    remote_config = setup["worker_config"](setup["tmp"] / f"partition-remote-{workers}")
    backend = ProcessSlotBackend(
        num_workers=workers, num_envs=num_envs, config=remote_config
    )
    remote, remote_carry = _collect_learner(setup, backend, builder, chunks, steps)
    for left, right in zip(local, remote):
        _assert_rollouts_equal(left, right)
    assert torch.equal(local_carry["recurrent_state"][0], remote_carry["recurrent_state"][0])
    assert np.array_equal(local_carry["episode_starts"], remote_carry["episode_starts"])
    # Per-environment opponent logs are identical, whatever the partition.
    for index in range(num_envs):
        name = f"worker-env{index:03d}-assignments.jsonl"
        left = (setup["tmp"] / f"partition-local-{workers}" / name).read_text()
        right = (setup["tmp"] / f"partition-remote-{workers}" / name).read_text()
        assert left == right


def _ppo_gradients(model, rollout, *, device, steps=1):
    model = copy.deepcopy(model).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, eps=1e-5, weight_decay=1e-5)
    advantages, returns = compute_gae(rollout, gamma=1.0, gae_lambda=0.95)
    captured = {}
    original_step = optimizer.step

    def capture_step(*args, **kwargs):
        if not captured:
            captured.update(
                {
                    name: parameter.grad.detach().cpu().clone()
                    for name, parameter in model.named_parameters()
                    if parameter.grad is not None
                }
            )
        return original_step(*args, **kwargs)

    optimizer.step = capture_step
    np.random.seed(5)
    stats = ppo_update(
        model=model,
        optimizer=optimizer,
        rollout=rollout,
        advantages=advantages,
        returns=returns,
        device=device,
        epochs=2,
        sequence_batch_size=2,
        clip_ratio=0.2,
        value_coef=0.5,
        entropy_coef=0.01,
        hand_aux_coef=0.1,
        elixir_aux_coef=0.1,
        target_kl=0.02,
    )
    weights = {name: value.detach().cpu() for name, value in model.state_dict().items()}
    return stats, captured, weights


def _assert_same_update(left, right) -> None:
    left_stats, left_grads, left_weights = left
    right_stats, right_grads, right_weights = right
    assert left_stats == right_stats
    assert left_grads.keys() == right_grads.keys()
    assert all(torch.equal(left_grads[k], right_grads[k]) for k in left_grads)
    assert all(torch.equal(left_weights[k], right_weights[k]) for k in left_weights)


def test_ppo_losses_and_gradients_match_the_admitted_path(setup):
    chunks, steps, num_envs = 2, 16, 4
    cpu = torch.device("cpu")
    # 1. Admitted single-process collector vs learner-side inference in one process.
    reference, _ = _collect_admitted(
        setup, setup["worker_config"](setup["tmp"] / "ppo-admitted"), num_envs, chunks, steps
    )
    local_config = setup["worker_config"](setup["tmp"] / "ppo-local-shared")
    builder, _, slots = _local_slots(
        local_config, num_envs, copy.deepcopy(setup["model"]), shared_opponent=True
    )
    local, _ = _collect_learner(setup, LocalSlotBackend(slots), builder, chunks, steps)
    _assert_same_update(
        _ppo_gradients(setup["model"], reference[-1], device=cpu),
        _ppo_gradients(setup["model"], local[-1], device=cpu),
    )
    # 2. All environments in one process vs split across two actor processes.
    single_config = setup["worker_config"](setup["tmp"] / "ppo-single")
    builder, _, slots = _local_slots(
        single_config, num_envs, copy.deepcopy(setup["model"]), shared_opponent=False
    )
    single, _ = _collect_learner(setup, LocalSlotBackend(slots), builder, chunks, steps)
    split_config = setup["worker_config"](setup["tmp"] / "ppo-split")
    backend = ProcessSlotBackend(num_workers=2, num_envs=num_envs, config=split_config)
    split, _ = _collect_learner(setup, backend, builder, chunks, steps)
    assert split[-1].transitions == num_envs * steps
    first = _ppo_gradients(setup["model"], single[-1], device=cpu)
    _assert_same_update(first, _ppo_gradients(setup["model"], split[-1], device=cpu))
    assert first[0]["optimizer_steps"] > 0 and first[1]


def test_batched_inference_equals_per_environment_inference(setup):
    config = setup["worker_config"](setup["tmp"] / "batching")
    model = copy.deepcopy(setup["model"])
    builder, _, slots = _local_slots(config, 4, model, shared_opponent=False)
    rollouts, _ = _collect_learner(setup, LocalSlotBackend(slots), builder, 2, 12)
    rollout = rollouts[-1]
    inputs = _sequence_inputs(rollout, slice(None), torch.device("cpu"))
    state = (
        torch.as_tensor(rollout.initial_hidden),
        torch.as_tensor(rollout.initial_cell),
    )
    with torch.no_grad():
        batched = model(inputs, state)
        batched_log_prob = batched.distribution().log_prob(torch.as_tensor(rollout.actions))
        for row in range(rollout.num_sequences):
            single_inputs = _sequence_inputs(rollout, slice(row, row + 1), torch.device("cpu"))
            single = model(single_inputs, (state[0][row : row + 1], state[1][row : row + 1]))
            single_log_prob = single.distribution().log_prob(
                torch.as_tensor(rollout.actions[row : row + 1])
            )
            torch.testing.assert_close(single_log_prob, batched_log_prob[row : row + 1], rtol=1e-5, atol=1e-5)
            torch.testing.assert_close(single.values, batched.values[row : row + 1], rtol=1e-5, atol=1e-5)
    # The stored behavior log-probs are the batched forward's own values.
    torch.testing.assert_close(
        batched_log_prob, torch.as_tensor(rollout.old_log_probs), rtol=1e-5, atol=1e-5
    )


@pytest.mark.skipif(not torch.backends.mps.is_available(), reason="MPS unavailable")
def test_mps_learner_matches_cpu_within_tolerance(setup):
    config = setup["worker_config"](setup["tmp"] / "mps")
    model = copy.deepcopy(setup["model"])
    builder, _, slots = _local_slots(config, 4, model, shared_opponent=False)
    rollouts, _ = _collect_learner(setup, LocalSlotBackend(slots), builder, 2, 16)
    cpu_stats, cpu_grads, _ = _ppo_gradients(setup["model"], rollouts[-1], device=torch.device("cpu"))
    mps_stats, mps_grads, _ = _ppo_gradients(setup["model"], rollouts[-1], device=torch.device("mps"))
    for key in ("loss", "policy_loss", "value_loss", "entropy", "approx_kl"):
        assert mps_stats[key] == pytest.approx(cpu_stats[key], rel=1e-3, abs=1e-5), key
    assert mps_stats["optimizer_steps"] == cpu_stats["optimizer_steps"]
    for name, gradient in cpu_grads.items():
        torch.testing.assert_close(mps_grads[name], gradient, rtol=1e-3, atol=1e-5)


def test_actor_environments_match_the_admitted_worker_construction(setup):
    """Same global index -> same decks, levels, seats and first observation."""
    from clasher.rl.parallel_rollout import ParallelRolloutCollector

    num_envs = 4
    admitted_config = setup["worker_config"](setup["tmp"] / "construction-admitted")
    with ParallelRolloutCollector(
        num_workers=2, num_envs=num_envs, config=admitted_config
    ) as collector:
        admitted = collector.collect(
            model=setup["model"], rollout_steps=1, policy_version=0, timeout=120
        )
    # The admitted collector concatenates by worker: envs (0, 2) then (1, 3).
    order = np.argsort(np.asarray([0, 2, 1, 3]))
    learner_config = setup["worker_config"](setup["tmp"] / "construction-learner")
    backend = ProcessSlotBackend(num_workers=2, num_envs=num_envs, config=learner_config)
    builder = build_policy_observation_builder(
        PolicyConfig.from_dict(learner_config.model_config),
        decks_path=learner_config.decks_path,
        token_names=learner_config.token_names,
    )
    learner, _ = _collect_learner(setup, backend, builder, 1, 1)
    learner = learner[0]
    observed = [
        "entity_ids", "entity_features", "entity_mask", "hand_ids", "global_features",
        "critic_entity_ids", "critic_entity_features", "critic_card_ids",
        "critic_global_features", "action_masks", "entity_levels", "hand_levels",
        "own_last_play_ids", "episode_starts",
    ]
    for name in observed:
        assert np.array_equal(
            getattr(admitted, name)[order][:, 0], getattr(learner, name)[:, 0]
        ), name
