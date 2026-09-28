from __future__ import annotations

import multiprocessing as mp
import queue
import traceback
from collections.abc import Iterable
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Literal

import numpy as np
import torch
from typing_extensions import Self

from .model import ClasherPolicy, PolicyConfig
from .reward_model import OBJECTIVE_V1
from .selfplay_env import SelfPlayBattleEnv
from .strategy_bots import STRATEGY_NAMES, StrategyBot
from .structured_obs import StructuredObservationBuilder
from .train_recurrent import (
    RolloutBatch,
    collect_rollout,
    collect_rollout_stationary_opponents,
    maybe_silence_stdio,
)


@dataclass(frozen=True)
class OpponentSpec:
    kind: Literal["noop", "random", "strategy", "checkpoint"]
    checkpoint: str | None = None
    strategy: str | None = None

    def __post_init__(self) -> None:
        if self.kind != "checkpoint" and self.checkpoint is not None:
            raise ValueError(f"{self.kind} opponent cannot have a checkpoint")
        if self.kind == "checkpoint" and not self.checkpoint:
            raise ValueError("checkpoint opponent requires a path")
        if self.kind == "strategy" and self.strategy not in STRATEGY_NAMES:
            raise ValueError("strategy opponent requires a known strategy")
        if self.kind != "strategy" and self.strategy is not None:
            raise ValueError(f"{self.kind} opponent cannot have a strategy")


@dataclass(frozen=True)
class ActorWorkerConfig:
    decks_path: str
    token_names: tuple[str, ...]
    model_config: dict[str, Any]
    decision_interval: int
    max_ticks: int
    mirror_match: bool
    opponent_mode: str
    opponent_pool: tuple[OpponentSpec, ...]
    engine_fast_path: str
    quiet_engine: bool
    base_seed: int
    torch_threads: int
    reward_profile: str = OBJECTIVE_V1
    reward_shaping_gamma: float | None = None
    elixir_leak_penalty_scale: float = 1.0
    defense_scenario_probability: float = 0.0
    defense_scenario_minimum_elixir: int = 4
    defense_scenario_maximum_elixir: int = 7
    defense_scenario_horizon_ticks: int = 240
    defense_scenario_reward_scale: float = 1.0
    sampling_decks_path: str | None = None
    learner_sampling_decks_path: str | None = None
    opponent_sampling_decks_path: str | None = None
    matchups_path: str | None = None
    matchup_probability: float = 0.0
    trim_rollout_entity_padding: bool = False
    hazard_conditioned_rollouts: bool = False


def concatenate_rollouts(rollouts: Iterable[RolloutBatch]) -> RolloutBatch:
    batches = list(rollouts)
    if not batches:
        raise ValueError("at least one rollout is required")
    sequence_length = batches[0].sequence_length
    if any(batch.sequence_length != sequence_length for batch in batches):
        raise ValueError("parallel rollout sequence lengths do not match")

    payload: dict[str, Any] = {}
    for field in fields(RolloutBatch):
        values = [getattr(batch, field.name) for batch in batches]
        if isinstance(values[0], np.ndarray):
            payload[field.name] = np.concatenate(values, axis=0)
        else:
            payload[field.name] = sum(int(value) for value in values)
    return RolloutBatch(**payload)


def _cpu_state_dict(model: ClasherPolicy) -> dict[str, torch.Tensor]:
    # Clone even for a CPU learner: Queue serialization happens on a feeder
    # thread, so views into live parameters could otherwise race an update.
    return {
        name: tensor.detach().to(device="cpu", copy=True)
        for name, tensor in model.state_dict().items()
    }


def opponent_spec_for_worker(
    config: ActorWorkerConfig, worker_id: int
) -> OpponentSpec | None:
    if config.opponent_mode == "selfplay":
        return None
    if config.opponent_mode not in {
        "noop",
        "random",
        "strategy",
        "checkpoint",
        "league",
    }:
        raise ValueError(f"unknown opponent mode {config.opponent_mode!r}")
    if not config.opponent_pool:
        raise ValueError(f"{config.opponent_mode} opponent mode requires a pool")
    return config.opponent_pool[worker_id % len(config.opponent_pool)]


def load_checkpoint_opponent(
    path: str | Path,
    *,
    device: torch.device,
    builder: StructuredObservationBuilder,
    learner_config: PolicyConfig,
    token_names: tuple[str, ...],
) -> ClasherPolicy:
    """Load an actor-compatible V2 opponent with its own model architecture."""
    payload = torch.load(path, map_location=device, weights_only=False)
    if int(payload.get("format_version", 0)) != 2:
        raise ValueError(f"not a V2 opponent checkpoint: {path}")
    if tuple(payload["token_names"]) != token_names:
        raise ValueError("opponent and learner token vocabularies differ")
    opponent_config = PolicyConfig.from_dict(payload["model_config"])
    compatibility_fields = (
        "num_tokens",
        "entity_feature_size",
        "actor_global_size",
        "critic_global_size",
    )
    incompatible = [
        name
        for name in compatibility_fields
        if getattr(opponent_config, name) != getattr(learner_config, name)
    ]
    if incompatible:
        raise ValueError(
            "opponent and learner observation schemas differ: "
            + ", ".join(incompatible)
        )
    opponent_builder = build_policy_observation_builder(
        opponent_config,
        decks_path="decks.json",
        card_vocab=builder.card_vocab,
        token_names=token_names,
    )
    model = ClasherPolicy(opponent_config, opponent_builder.card_stat_features).to(
        device
    )
    model.load_state_dict(payload["model_state_dict"])
    model.eval()
    return model


def build_policy_observation_builder(
    config: PolicyConfig,
    *,
    decks_path: str | Path,
    token_names: tuple[str, ...],
    card_vocab: tuple[str, ...] | list[str] | None = None,
) -> StructuredObservationBuilder:
    """Build the complete observation schema declared by a policy config."""
    return StructuredObservationBuilder(
        decks_path=decks_path,
        card_vocab=card_vocab,
        max_entities=config.max_entities,
        token_names=token_names,
        card_semantics_version=config.card_semantics_version,
        canonical_lane_globals=config.canonical_lane_globals,
        public_history_slots=config.public_history_slots,
        public_seen_card_slots=config.public_seen_card_slots,
    )


def _actor_worker_main(
    worker_id: int,
    env_indices: tuple[int, ...],
    config: ActorWorkerConfig,
    command_queue: Any,
    result_queue: Any,
) -> None:
    try:
        from . import train_recurrent as train_recurrent_module

        train_recurrent_module._USE_TRIMMED_ROLLOUT_ENTITY_PADDING = (
            config.trim_rollout_entity_padding
        )
        torch.set_num_threads(max(1, config.torch_threads))
        torch.manual_seed(config.base_seed + 1_000_003 * (worker_id + 1))
        np.random.seed(config.base_seed + 1_000_033 * (worker_id + 1))
        device = torch.device("cpu")
        policy_config = PolicyConfig.from_dict(config.model_config)
        builder = build_policy_observation_builder(
            policy_config,
            decks_path=config.decks_path,
            token_names=config.token_names,
        )
        model = ClasherPolicy(policy_config, builder.card_stat_features).to(device)
        opponent_model: ClasherPolicy | None = None
        opponent_spec = opponent_spec_for_worker(config, worker_id)
        opponent_bot: StrategyBot | None = None
        if opponent_spec is not None and opponent_spec.kind == "strategy":
            assert opponent_spec.strategy is not None
            opponent_bot = StrategyBot(opponent_spec.strategy)
        if opponent_spec is not None and opponent_spec.kind == "checkpoint":
            assert opponent_spec.checkpoint is not None
            opponent_model = load_checkpoint_opponent(
                opponent_spec.checkpoint,
                device=device,
                builder=builder,
                learner_config=policy_config,
                token_names=config.token_names,
            )

        envs: list[SelfPlayBattleEnv] = []
        with maybe_silence_stdio(config.quiet_engine):
            for env_index in env_indices:
                seed = config.base_seed + env_index * 1009
                learner_player = env_index % 2
                player_sampling_paths = (
                    (
                        config.learner_sampling_decks_path,
                        config.opponent_sampling_decks_path,
                    )
                    if learner_player == 0
                    else (
                        config.opponent_sampling_decks_path,
                        config.learner_sampling_decks_path,
                    )
                )
                env = SelfPlayBattleEnv(
                    decision_interval_ticks=config.decision_interval,
                    max_ticks=config.max_ticks,
                    decks_path=Path(config.decks_path),
                    sampling_decks_path=(
                        Path(config.sampling_decks_path)
                        if config.sampling_decks_path is not None
                        else None
                    ),
                    player0_sampling_decks_path=player_sampling_paths[0],
                    player1_sampling_decks_path=player_sampling_paths[1],
                    matchups_path=config.matchups_path,
                    matchup_probability=config.matchup_probability,
                    learner_player_id=learner_player,
                    seed=seed,
                    mirror_match=config.mirror_match,
                    canonical_perspective=True,
                    canonical_lane_globals=policy_config.canonical_lane_globals,
                    engine_fast_path=config.engine_fast_path,
                    reward_profile=config.reward_profile,
                    reward_shaping_gamma=config.reward_shaping_gamma,
                    elixir_leak_penalty_scale=config.elixir_leak_penalty_scale,
                    defense_scenario_probability=config.defense_scenario_probability,
                    defense_scenario_minimum_elixir=(
                        config.defense_scenario_minimum_elixir
                    ),
                    defense_scenario_maximum_elixir=(
                        config.defense_scenario_maximum_elixir
                    ),
                    defense_scenario_horizon_ticks=(
                        config.defense_scenario_horizon_ticks
                    ),
                    defense_scenario_reward_scale=config.defense_scenario_reward_scale,
                )
                env._structured_obs_builder = builder
                env.reset(seed=seed)
                envs.append(env)

        stationary_opponents = config.opponent_mode in {
            "noop",
            "random",
            "strategy",
            "checkpoint",
            "league",
        }
        agents = len(envs) if stationary_opponents else 2 * len(envs)
        learner_players = tuple(env_index % 2 for env_index in env_indices)
        recurrent_state = model.initial_state(agents, device=device)
        no_op = envs[0].action_space.no_op_action
        previous_actions = np.full((agents,), no_op, dtype=np.int64)
        previous_rewards = np.zeros((agents,), dtype=np.float32)
        episode_starts = np.ones((agents,), dtype=np.bool_)
        opponent_recurrent_state = (
            opponent_model.initial_state(agents, device=device)
            if opponent_model is not None
            else None
        )
        opponent_previous_actions = np.full((agents,), no_op, dtype=np.int64)
        opponent_previous_rewards = np.zeros((agents,), dtype=np.float32)
        opponent_episode_starts = np.ones((agents,), dtype=np.bool_)
        result_queue.put(("ready", worker_id, None))

        while True:
            command = command_queue.get()
            if command[0] == "close":
                return
            if command[0] != "collect":
                raise ValueError(f"unknown actor command {command[0]!r}")
            _, policy_version, rollout_steps, state_dict = command
            model.load_state_dict(state_dict)
            (
                rollout,
                recurrent_state,
                previous_actions,
                previous_rewards,
                episode_starts,
                opponent_recurrent_state,
                opponent_previous_actions,
                opponent_previous_rewards,
                opponent_episode_starts,
            ) = (
                collect_rollout_stationary_opponents(
                    envs=envs,
                    learner_players=learner_players,
                    builder=builder,
                    model=model,
                    device=device,
                    rollout_steps=int(rollout_steps),
                    recurrent_state=recurrent_state,
                    previous_actions=previous_actions,
                    previous_rewards=previous_rewards,
                    episode_starts=episode_starts,
                    opponent_model=opponent_model,
                    opponent_recurrent_state=opponent_recurrent_state,
                    opponent_previous_actions=opponent_previous_actions,
                    opponent_previous_rewards=opponent_previous_rewards,
                    opponent_episode_starts=opponent_episode_starts,
                    quiet_engine=config.quiet_engine,
                    opponent_bot=opponent_bot,
                    opponent_noop=(
                        opponent_spec is not None and opponent_spec.kind == "noop"
                    ),
                    hazard_conditioned_rollouts=(
                        config.hazard_conditioned_rollouts
                    ),
                )
                if stationary_opponents
                else collect_rollout(
                    envs=envs,
                    builder=builder,
                    model=model,
                    device=device,
                    rollout_steps=int(rollout_steps),
                    recurrent_state=recurrent_state,
                    previous_actions=previous_actions,
                    previous_rewards=previous_rewards,
                    episode_starts=episode_starts,
                    quiet_engine=config.quiet_engine,
                    hazard_conditioned_rollouts=(
                        config.hazard_conditioned_rollouts
                    ),
                )
                + (
                    opponent_recurrent_state,
                    opponent_previous_actions,
                    opponent_previous_rewards,
                    opponent_episode_starts,
                )
            )
            result_queue.put(("rollout", worker_id, policy_version, rollout))
    except BaseException:  # noqa: BLE001 - worker failures must reach the parent
        result_queue.put(("error", worker_id, traceback.format_exc()))


class ParallelRolloutCollector:
    """Persistent synchronous CPU actors for an accelerator-backed learner."""

    def __init__(
        self,
        *,
        num_workers: int,
        num_envs: int,
        config: ActorWorkerConfig,
        startup_timeout: float = 120.0,
    ) -> None:
        if num_workers <= 1:
            raise ValueError("ParallelRolloutCollector requires at least two workers")
        if num_workers > num_envs:
            raise ValueError("num_workers cannot exceed num_envs")
        self.num_workers = int(num_workers)
        self._closed = False
        self._context = mp.get_context("spawn")
        self._result_queue = self._context.Queue(maxsize=2 * num_workers)
        self._command_queues: list[Any] = []
        self._processes: list[Any] = []

        assignments = [
            tuple(range(worker_id, num_envs, num_workers))
            for worker_id in range(num_workers)
        ]
        for worker_id, env_indices in enumerate(assignments):
            command_queue = self._context.Queue(maxsize=1)
            process = self._context.Process(
                target=_actor_worker_main,
                args=(
                    worker_id,
                    env_indices,
                    config,
                    command_queue,
                    self._result_queue,
                ),
                name=f"clasher-actor-{worker_id}",
                daemon=True,
            )
            process.start()
            self._command_queues.append(command_queue)
            self._processes.append(process)

        ready: set[int] = set()
        while len(ready) < num_workers:
            try:
                message = self._result_queue.get(timeout=startup_timeout)
            except queue.Empty as error:
                self.close(force=True)
                raise TimeoutError("timed out starting rollout workers") from error
            if message[0] == "error":
                self.close(force=True)
                raise RuntimeError(
                    f"rollout worker {message[1]} failed during startup:\n{message[2]}"
                )
            if message[0] != "ready":
                self.close(force=True)
                raise RuntimeError(f"unexpected startup message {message[0]!r}")
            ready.add(int(message[1]))

    def collect(
        self,
        *,
        model: ClasherPolicy,
        rollout_steps: int,
        policy_version: int,
        timeout: float = 600.0,
    ) -> RolloutBatch:
        if self._closed:
            raise RuntimeError("parallel rollout collector is closed")
        state_dict = _cpu_state_dict(model)
        for command_queue in self._command_queues:
            command_queue.put(("collect", policy_version, rollout_steps, state_dict))

        results: dict[int, RolloutBatch] = {}
        while len(results) < self.num_workers:
            try:
                message = self._result_queue.get(timeout=timeout)
            except queue.Empty as error:
                dead = [
                    process.name
                    for process in self._processes
                    if not process.is_alive()
                ]
                raise TimeoutError(
                    f"timed out waiting for rollout workers; dead={dead}"
                ) from error
            if message[0] == "error":
                raise RuntimeError(f"rollout worker {message[1]} failed:\n{message[2]}")
            if message[0] != "rollout":
                raise RuntimeError(f"unexpected rollout message {message[0]!r}")
            _, worker_id, result_version, rollout = message
            if int(result_version) != int(policy_version):
                raise RuntimeError(
                    f"actor {worker_id} returned policy version {result_version}, "
                    f"expected {policy_version}"
                )
            results[int(worker_id)] = rollout
        return concatenate_rollouts(results[index] for index in sorted(results))

    def close(self, *, force: bool = False) -> None:
        if self._closed:
            return
        self._closed = True
        if not force:
            for command_queue in self._command_queues:
                try:
                    command_queue.put_nowait(("close",))
                except queue.Full:
                    pass
        for process in self._processes:
            process.join(timeout=5.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5.0)
        for command_queue in self._command_queues:
            command_queue.close()
            command_queue.join_thread()
        self._result_queue.close()
        self._result_queue.join_thread()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()
